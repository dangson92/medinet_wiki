"""Search service — core vector query engine Phase 6 + Plan 04-05 refactor.

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

Cross-hub (`search_cross_hub`) — Phase 4 Plan 04-05 (SYNC-03 / D-V3-Phase4-D1)
refactor: 1 SQL aggregated `WHERE hub_id = ANY($1::uuid[])` thay fan-out
parallel `_search_one(hub_id)` per hub qua asyncio.gather. Re-rank tự nhiên qua
ORDER BY vector <=> embedding LIMIT $k. HNSW iterative_scan=relaxed_order +
ef_search=200 + max_scan_tuples=20000 carry forward M2 Phase 6 (_run_vector_query
SET LOCAL session tuning). Cache cross-hub tách namespace `search:cross:` (06-03
invalidation xử lý chung prefix `search:`). Public API
`SearchService.search_cross_hub()` signature giữ NGUYÊN (backward compat M2
contract — ask_service.py consumer + frontend client).

`find_similar` (D-04) — find-similar không có REQ-ID, KHÔNG cache.
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import TYPE_CHECKING, Any

from app.observability.metrics import SEARCH_LATENCY
from app.repositories.hub_isolation import HubIsolationError
from app.schemas.search import (
    SearchRequest,
    SearchResponse,
    SearchResultItem,
    SimilarMatch,
    SimilarRequest,
    SimilarResponse,
)
from app.services.embedder import embed_text
from app.services.search_cache import tag_cache_key

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


def _cross_cache_key(
    query: str,
    hub_ids: list[str],
    top_k: int,
    min_score: float | None,
) -> str:
    """Cache key cross-hub `search:cross:<sha256>` — tách namespace khỏi
    single-hub `search:` để 06-03 invalidation xử lý chung prefix `search:`."""
    raw = f"{query}|{sorted(hub_ids)}|{top_k}|{min_score}"
    return "search:cross:" + hashlib.sha256(raw.encode()).hexdigest()


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

        Plan 10-02 HARD-02: wrap toàn body bằng `SEARCH_LATENCY` histogram
        (label `hub_scope="single"`) đo thời gian thực sự bao gồm cả empty-result
        early-return + cache hit + SQL query.
        """
        with SEARCH_LATENCY.labels(hub_scope="single").time():
            return await self._search_single_impl(body=body, user=user)

    async def _search_single_impl(
        self,
        *,
        body: SearchRequest,
        user: UserWithHubs,
    ) -> dict[str, Any]:
        """Implementation `search()` — tách để wrap SEARCH_LATENCY ở public method."""
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

        # Cache ghi — fail-open. tag_cache_key gắn cache key vào SET hub-tag
        # (06-03 / D-12) NẰM TRONG cùng block try/except fail-open với redis.set.
        if self.redis is not None:
            try:
                await self.redis.set(
                    cache_key, json.dumps(result), ex=CACHE_TTL_SECONDS
                )
                await tag_cache_key(self.redis, cache_key, hub_ids)
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

    async def search_cross_hub(
        self,
        *,
        body: SearchRequest,
        user: UserWithHubs,
    ) -> dict[str, Any]:
        """Cross-hub aggregated search (SEARCH-03 / D-06 + Plan 04-05 D-V3-Phase4-D1).

        Phase 4 Plan 04-05 refactor — 1 SQL aggregated `WHERE c.hub_id = ANY`
        thay fan-out per-hub. Re-rank tự nhiên qua ORDER BY vector <=> embedding
        LIMIT $k của SQL (KHÔNG cần Python merge sort). Public API signature
        giữ NGUYÊN — backward compat M2 contract.

        Plan 10-02 HARD-02: wrap toàn body bằng `SEARCH_LATENCY` histogram
        (label `hub_scope="cross"`).

        Trả dict (`SearchResponse.model_dump(mode="json")`) — router wrap envelope.
        """
        with SEARCH_LATENCY.labels(hub_scope="cross").time():
            return await self._search_cross_hub_impl(body=body, user=user)

    async def _search_cross_hub_impl(
        self,
        *,
        body: SearchRequest,
        user: UserWithHubs,
    ) -> dict[str, Any]:
        """Implementation `search_cross_hub()` — tách để wrap SEARCH_LATENCY ở public method.

        Phase 4 Plan 04-05 (SYNC-03 / D-V3-Phase4-D1) — Refactor 1 SQL aggregated
        thay fan-out parallel per-hub. Single `_run_vector_query(hub_ids=[<all>])`
        dùng `WHERE c.hub_id = ANY($2::uuid[])` + ORDER BY vector <=> embedding
        LIMIT $k → re-rank tự nhiên + giảm N connection acquire + N HNSW seek
        về 1.

        Public API `SearchService.search_cross_hub()` signature KHÔNG đổi —
        backward compat M2 contract (ask_service.py consumer + frontend client).
        HNSW iterative_scan=relaxed_order + ef_search=200 + max_scan_tuples=20000
        carry forward (M2 Phase 6 `_run_vector_query` SET LOCAL session tuning).

        E-V3-2: cross-hub p95 < 1.5s — single SQL avoid concurrent gather
        overhead + N-times re-rank merge. Khác `_search_single_impl` ở chỗ admin
        no-filter cần query danh sách hub `is_active = TRUE` rồi pass vào
        `_run_vector_query` với `all_hubs=False` (KHÔNG dùng `all_hubs=True`
        branch của single search để giữ total_hubs_searched semantic = số hub
        fan-in thực sự).
        """
        t0 = time.perf_counter()
        top_k = _resolve_top_k(body.top_k)
        hub_ids = intersect_hubs(body.hub_ids, user.hub_ids, user.user.role)

        # admin không filter: cần danh sách hub cụ thể để pass vào aggregated SQL
        # với `WHERE c.hub_id = ANY` + giữ total_hubs_searched = len(hub_ids).
        # Predicate `is_active = TRUE` NHẤT QUÁN branch admin-all của
        # `_run_vector_query` (06-01). TUYỆT ĐỐI KHÔNG dùng cột `status`.
        if user.user.role == "admin" and not body.hub_ids:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch("SELECT id FROM hubs WHERE is_active = TRUE")
            hub_ids = [str(r["id"]) for r in rows]

        # Không hub nào để query (non-admin chưa assign / không hub active) →
        # empty result hợp lệ.
        if not hub_ids:
            return SearchResponse(
                results=[],
                total_hubs_searched=0,
                query_time_ms=int((time.perf_counter() - t0) * 1000),
                cache_hit=False,
            ).model_dump(mode="json")

        # Cache đọc (D-11) — namespace `search:cross:`, fail-open.
        cache_key = _cross_cache_key(body.query, hub_ids, top_k, body.min_score)
        if self.redis is not None:
            try:
                cached = await self.redis.get(cache_key)
            except Exception as exc:  # noqa: BLE001 — fail-open, KHÔNG raise
                logger.warning("cross-hub cache get thất bại: %s", exc)
            else:
                if cached:
                    result: dict[str, Any] = json.loads(cached)
                    result["cache_hit"] = True
                    return result

        # Embed query 1 lần (D-09) — ValueError / EmbedderError tự bubble lên
        # router để map 400 / 502 (KHÔNG catch ở service).
        query_vector = await embed_text(body.query)

        # Phase 4 Plan 04-05 (SYNC-03 / D-V3-Phase4-D1) — 1 SQL aggregated thay
        # fan-out per-hub. `_run_vector_query` đã handle `hub_ids: list[str]`
        # multi-element qua `WHERE c.hub_id = ANY($2::uuid[])` (M2 Phase 6 carry
        # forward). ORDER BY vector <=> $1::vector LIMIT $3 trim global top-k tự
        # nhiên — KHÔNG cần Python re-rank merge sort.
        rows, _hubs_queried = await self._run_vector_query(
            query_vector=query_vector,
            hub_ids=hub_ids,  # ALL hubs in 1 list — ANY($1::uuid[])
            top_k=top_k,
            all_hubs=False,
        )
        items = [_row_to_item(r) for r in rows]

        # min_score filter (D-14) — categories/tags/date_* accept-but-noop M2.
        if body.min_score is not None:
            items = [it for it in items if it.score >= body.min_score]

        # total_hubs_searched = số hub fan-in thực sự (với admin-all `hub_ids`
        # đã = danh sách hub `is_active = TRUE` từ SELECT trên).
        result = SearchResponse(
            results=items,
            total_hubs_searched=len(hub_ids),
            query_time_ms=int((time.perf_counter() - t0) * 1000),
            cache_hit=False,
        ).model_dump(mode="json")

        # Cache ghi — fail-open. tag_cache_key gắn cache key cross-hub vào SET
        # hub-tag cho TỪNG hub queried (06-03 / D-12) — NẰM TRONG cùng block
        # try/except fail-open với redis.set.
        if self.redis is not None:
            try:
                await self.redis.set(
                    cache_key, json.dumps(result), ex=CACHE_TTL_SECONDS
                )
                await tag_cache_key(self.redis, cache_key, hub_ids)
            except Exception as exc:  # noqa: BLE001 — fail-open, KHÔNG raise
                logger.warning("cross-hub cache set thất bại: %s", exc)

        logger.info(
            "cross_hub_search_completed",
            extra={"hub_count": len(hub_ids), "result_count": len(items)},
        )
        return result

    async def find_similar(
        self,
        *,
        body: SimilarRequest,
        user: UserWithHubs,
    ) -> dict[str, Any]:
        """Find-similar (D-04 — không có REQ-ID, KHÔNG cache D-11).

        Nhận `{content, hub_id?, threshold?}` → embed `content` rồi vector query
        trả `SimilarResponse`. Empty result hợp lệ (KHÔNG raise).
        """
        top_k = DEFAULT_TOP_K  # frontend không gửi top_k cho similar.
        requested = [body.hub_id] if body.hub_id else None
        hub_ids = intersect_hubs(requested, user.hub_ids, user.user.role)
        is_admin_all = user.user.role == "admin" and not body.hub_id

        # Non-admin chưa assign hub (intersect rỗng) → empty result hợp lệ.
        if not is_admin_all and not hub_ids:
            return SimilarResponse(matches=[]).model_dump(mode="json")

        # Embed content (D-09) — ValueError / EmbedderError tự bubble lên router.
        query_vector = await embed_text(body.content)

        rows, _ = await self._run_vector_query(
            query_vector=query_vector,
            hub_ids=hub_ids,
            top_k=top_k,
            all_hubs=is_admin_all,
        )

        # threshold filter — giữ row có score >= threshold (mặc định 0.0).
        threshold = body.threshold if body.threshold is not None else 0.0
        matches = [
            SimilarMatch(
                page_id=str(r["document_id"]),
                page_title=r["filename"],
                similarity_score=float(r["score"]),
                hub_name=r["hub_name"],
            )
            for r in rows
            if float(r["score"]) >= threshold
        ]

        logger.info(
            "find_similar_completed",
            extra={"hub_count": len(hub_ids), "result_count": len(matches)},
        )
        return SimilarResponse(matches=matches).model_dump(mode="json")
