"""Search service — core vector query engine Phase 6.

`SearchService.search()` chạy single-hub union search (SEARCH-01) trên pgvector
qua asyncpg pool: embed query (D-09), set HNSW session tuning (SEARCH-02 / D-08),
raw vector SQL, đọc/ghi Redis cache (SEARCH-04 / D-11).

Defense in depth (D-07):
  - Lớp 1 (service): `intersect_hubs()` giao `request.hub_ids` với hub user được
    assign TRƯỚC khi vào SQL — hub user không quyền bị silent-drop, KHÔNG raise.
  - Lớp 2 (SQL): `WHERE c.hub_id = ANY($N::uuid[])` filter lại ở DB.

Predicate "tập hub admin search" = `is_active = TRUE` — NHẤT QUÁN với 06-02
`search_cross_hub` (`SELECT id FROM hubs WHERE is_active = TRUE`). KHÔNG dùng
predicate cột `status` ở bất kỳ đâu (chỉ `is_active`).

Cross-hub fan-out (`search_cross_hub`) + `find_similar` thêm ở 06-02.
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import TYPE_CHECKING, Any

from app.repositories.hub_isolation import HubIsolationError
from app.schemas.search import SearchRequest, SearchResponse, SearchResultItem
from app.services.embedder import embed_text

if TYPE_CHECKING:
    from app.auth.dependencies import UserWithHubs

logger = logging.getLogger(__name__)

#: Top-k mặc định khi request không gửi.
DEFAULT_TOP_K = 10
#: Trần top-k chống DoS request top_k khổng lồ (T-06-01-03).
MAX_TOP_K = 50
#: Độ dài tối đa snippet (cắt theo word boundary).
SNIPPET_MAX_CHARS = 300
#: TTL cache search results (SEARCH-04 / D-11).
CACHE_TTL_SECONDS = 300

# HubIsolationError re-export để 06-02 import từ service layer nếu cần.
__all__ = [
    "CACHE_TTL_SECONDS",
    "DEFAULT_TOP_K",
    "MAX_TOP_K",
    "SNIPPET_MAX_CHARS",
    "HubIsolationError",
    "SearchService",
    "intersect_hubs",
]


def _to_pgvector_literal(vec: list[float]) -> str:
    """list[float] → pgvector literal string `'[0.1,0.2,...]'` cho cast `$1::vector`."""
    return "[" + ",".join(repr(float(x)) for x in vec) + "]"


def _truncate_snippet(content: str, limit: int = SNIPPET_MAX_CHARS) -> str:
    """Cắt content tối đa `limit` ký tự theo word boundary, append `…`.

    `len(content) <= limit` → trả nguyên; ngược lại cắt `content[:limit]`,
    rsplit theo space lấy phần trước space cuối + `"…"`.
    """
    if len(content) <= limit:
        return content
    head = content[:limit]
    cut = head.rsplit(" ", 1)[0]
    return f"{cut}…"


def _cache_key(
    query: str,
    hub_ids: list[str],
    top_k: int,
    min_score: float | None,
) -> str:
    """Cache key `search:<sha256>` — hub_ids đã intersect nên cache hub-scoped."""
    raw = f"{query}|{sorted(hub_ids)}|{top_k}|{min_score}"
    return "search:" + hashlib.sha256(raw.encode()).hexdigest()


def _resolve_top_k(raw: int | None) -> int:
    """`raw` None → DEFAULT_TOP_K; clamp vào `[1, MAX_TOP_K]` (T-06-01-03)."""
    if raw is None:
        return DEFAULT_TOP_K
    return max(1, min(raw, MAX_TOP_K))


def intersect_hubs(
    requested: list[str] | None,
    user_hub_ids: list[str],
    role: str,
) -> list[str]:
    """Defense in depth lớp 1 (D-07) — giao hub request với hub user được assign.

    - admin: `requested` None → trả `[]` (sentinel "mọi hub" — caller branch
      admin-all); `requested` có giá trị → trả `list(requested)`.
    - editor/viewer: `base = requested or user_hub_ids`; trả phần giao với
      `user_hub_ids` đã sort. Hub user không quyền bị LOẠI (silent-drop, KHÔNG
      raise).
    """
    if role == "admin":
        return list(requested) if requested else []
    base = set(requested) if requested else set(user_hub_ids)
    return sorted(base & set(user_hub_ids))


def _row_to_item(row: Any) -> SearchResultItem:
    """Map 1 asyncpg Record → SearchResultItem (D-10)."""
    updated_at = row["updated_at"]
    return SearchResultItem(
        id=str(row["id"]),
        hub_id=str(row["hub_id"]),
        hub_name=row["hub_name"],
        title=row["filename"],
        snippet=_truncate_snippet(row["content"]),
        content=row["content"],
        category=None,
        tags=[],
        score=float(row["score"]),
        raw_similarity=float(row["score"]),
        updated_at=updated_at.isoformat() if updated_at else None,
        source="document",
    )


class SearchService:
    """Vector search engine — single-hub union search + HNSW tuning + cache."""

    def __init__(self, *, pool: Any, redis: Any = None) -> None:
        self.pool = pool  # asyncpg pool — raw vector SQL
        self.redis = redis  # redis.asyncio client — cache (có thể None, fail-open)

    async def _run_vector_query(
        self,
        *,
        query_vector: list[float],
        hub_ids: list[str],
        top_k: int,
        all_hubs: bool,
    ) -> tuple[list[Any], int]:
        """Raw vector SQL + HNSW session tuning (D-08 / D-09).

        Trả `(rows, hubs_queried)` — `hubs_queried` là SỐ HUB THỰC SỰ query, dùng
        làm `total_hubs_searched` (D-05):
          - `all_hubs=True` (admin không filter): SQL filter `h.is_active = TRUE`,
            đếm `count(*) FROM hubs WHERE is_active = TRUE` (cùng predicate →
            populace query KHỚP count).
          - ngược lại: filter `c.hub_id = ANY($2::uuid[])`, count = `len(hub_ids)`.
        """
        vec_literal = _to_pgvector_literal(query_vector)
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute("SET LOCAL hnsw.ef_search = 200")
                await conn.execute("SET LOCAL hnsw.iterative_scan = relaxed_order")
                await conn.execute("SET LOCAL hnsw.max_scan_tuples = 20000")
                if all_hubs:
                    # Branch admin-all: SQL `AND h.is_active = TRUE` giới hạn
                    # vector query CHỈ scan chunk thuộc hub active. count(*) FROM
                    # hubs WHERE is_active = TRUE dùng CÙNG predicate → populace
                    # query KHỚP count → total_hubs_searched đúng D-05.
                    sql = (
                        "SELECT c.id, c.document_id, c.hub_id, c.content, "
                        "c.heading_path, c.metadata, d.filename, d.updated_at, "
                        "h.name AS hub_name, "
                        "1 - (c.vector <=> $1::vector) AS score "
                        "FROM chunks c "
                        "JOIN documents d ON d.id = c.document_id "
                        "JOIN hubs h ON h.id = c.hub_id "
                        "WHERE c.vector IS NOT NULL AND h.is_active = TRUE "
                        "ORDER BY c.vector <=> $1::vector LIMIT $2"
                    )
                    hubs_queried = await conn.fetchval(
                        "SELECT count(*) FROM hubs WHERE is_active = TRUE"
                    )
                    rows = await conn.fetch(sql, vec_literal, top_k)
                    return rows, int(hubs_queried)
                sql = (
                    "SELECT c.id, c.document_id, c.hub_id, c.content, "
                    "c.heading_path, c.metadata, d.filename, d.updated_at, "
                    "h.name AS hub_name, "
                    "1 - (c.vector <=> $1::vector) AS score "
                    "FROM chunks c "
                    "JOIN documents d ON d.id = c.document_id "
                    "JOIN hubs h ON h.id = c.hub_id "
                    "WHERE c.hub_id = ANY($2::uuid[]) AND c.vector IS NOT NULL "
                    "ORDER BY c.vector <=> $1::vector LIMIT $3"
                )
                rows = await conn.fetch(sql, vec_literal, hub_ids, top_k)
                return rows, len(hub_ids)

    async def search(
        self,
        *,
        body: SearchRequest,
        user: UserWithHubs,
    ) -> dict[str, Any]:
        """Single-hub union vector search (SEARCH-01 / SEARCH-02 / SEARCH-04).

        Trả dict (`SearchResponse.model_dump(mode="json")`) — router wrap envelope.
        Empty result (user chưa assign hub / hub chưa có chunk) → `results: []`,
        KHÔNG raise.
        """
        t0 = time.perf_counter()
        top_k = _resolve_top_k(body.top_k)
        hub_ids = intersect_hubs(body.hub_ids, user.hub_ids, user.user.role)
        is_admin_all = user.user.role == "admin" and not body.hub_ids

        # Non-admin chưa assign hub (intersect rỗng) → empty result hợp lệ.
        if not is_admin_all and not hub_ids:
            return SearchResponse(
                results=[],
                total_hubs_searched=0,
                query_time_ms=int((time.perf_counter() - t0) * 1000),
                cache_hit=False,
            ).model_dump(mode="json")

        # Cache đọc (SEARCH-04 / D-11) — fail-open khi Redis None hoặc lỗi.
        cache_key = _cache_key(body.query, hub_ids, top_k, body.min_score)
        if self.redis is not None:
            try:
                cached = await self.redis.get(cache_key)
            except Exception as exc:  # noqa: BLE001 — fail-open, KHÔNG raise
                logger.warning("search cache get thất bại: %s", exc)
            else:
                if cached:
                    result: dict[str, Any] = json.loads(cached)
                    result["cache_hit"] = True
                    return result

        # Embed query (D-09) — ValueError (text rỗng) / EmbedderError tự bubble
        # lên router để map 400 / 502 (KHÔNG catch ở service).
        query_vector = await embed_text(body.query)

        rows, hubs_queried = await self._run_vector_query(
            query_vector=query_vector,
            hub_ids=hub_ids,
            top_k=top_k,
            all_hubs=is_admin_all,
        )
        items = [_row_to_item(r) for r in rows]

        # min_score filter (D-14) — categories/tags/date_* accept-but-noop M2.
        if body.min_score is not None:
            items = [it for it in items if it.score >= body.min_score]

        # total_hubs_searched = số hub THỰC SỰ query (D-05) — KHÔNG phải số hub
        # xuất hiện trong top-k rows.
        result = SearchResponse(
            results=items,
            total_hubs_searched=hubs_queried,
            query_time_ms=int((time.perf_counter() - t0) * 1000),
            cache_hit=False,
        ).model_dump(mode="json")

        # Cache ghi — fail-open.
        if self.redis is not None:
            try:
                await self.redis.set(
                    cache_key, json.dumps(result), ex=CACHE_TTL_SECONDS
                )
            except Exception as exc:  # noqa: BLE001 — fail-open, KHÔNG raise
                logger.warning("search cache set thất bại: %s", exc)

        logger.info(
            "search_completed",
            extra={
                "hub_count": hubs_queried,
                "result_count": len(items),
                "query_time_ms": result["query_time_ms"],
            },
        )
        return result
