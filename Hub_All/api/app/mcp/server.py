"""MCP server — Phase 8.1 (MCP-01, MCP-02).

FastMCP Streamable HTTP server expose 3 tool read-only cho AI client:
- list_hubs   — danh sách Hub user được phép (D-07)
- search_wiki — vector semantic search (D-07, D-08)
- ask_wiki    — RAG ask + citation + usage log (D-07, D-08, D-11, D-14)

Transport: Streamable HTTP, stateless_http=True (D-01)
Mount: /mcp trong FastAPI app chính (D-02)
Auth: X-API-Key qua ctx.request_context.request.headers → authenticate_mcp_request (D-05/D-06)
Service: gọi trực tiếp SearchService/AskService — KHÔNG self-call HTTP (D-04)
Pool: module-level singleton set_pool/_get_pool (RESEARCH.md Pattern 4)

Deviation từ plan — mcp==1.27.1 (không phải 1.9.4):
  - import: from mcp.server.fastmcp import FastMCP, Context
  - ToolError: from mcp.server.fastmcp.exceptions import ToolError
  - decorator: @mcp.tool() (có dấu () — bắt buộc trong 1.27.1)
  - http_app() không tồn tại → dùng FastMCP(..., stateless_http=True) + .streamable_http_app()
  - combine_lifespans không tồn tại → _compose_lifespans() viết tay trong main.py
  - authenticate_mcp_request(ctx, pool) — ctx inject qua annotation ctx: Context
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import asyncpg
from mcp.server.fastmcp import Context, FastMCP
from mcp.server.fastmcp.exceptions import ToolError

from app.mcp.auth import authenticate_mcp_request
from app.mcp.schemas import (
    AskAnswer,
    CitationItem,
    HubItem,
    HubList,
    SearchResult,
    SearchResultItem,
)
from app.repositories.hub_isolation import HubIsolationError
from app.services.ask_service import AskError, AskService
from app.services.usage_service import log_usage_event

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level pool singleton (RESEARCH.md Pattern 4)
# Không có FastAPI Request trong MCP tool → không dùng request.app.state
# ---------------------------------------------------------------------------
_pool: asyncpg.Pool | None = None
_redis: Any = None


def set_pool(pool: asyncpg.Pool, redis: Any = None) -> None:
    """Gọi từ lifespan FastAPI sau khi app.state.db_pool init.

    PHẢI gọi trước bất kỳ tool call nào — nếu quên → _get_pool() raise RuntimeError.
    """
    global _pool, _redis
    _pool = pool
    _redis = redis
    logger.info("mcp_pool_set")


def _get_pool() -> asyncpg.Pool:
    """Guard pool None → RuntimeError (tương tự ask.py line 74)."""
    if _pool is None:
        raise RuntimeError("db_pool chưa sẵn sàng — MCP không khả dụng")
    return _pool


def _get_redis() -> Any:
    """Trả redis client (có thể None — SearchService/AskService xử lý redis=None)."""
    return _redis


# Giữ strong reference tới background task usage-logging. asyncio chỉ giữ
# weak reference tới task → nếu không lưu handle, task có thể bị GC giữa chừng
# và bị drop âm thầm (CR-01). Set này giữ task sống đến khi hoàn tất.
_background_tasks: set[asyncio.Task[Any]] = set()


def _spawn_usage_log(coro: Any) -> None:
    """Chạy log_usage_event non-blocking (D-14) nhưng KHÔNG drop âm thầm.

    Giữ reference trong _background_tasks + done-callback log exception nếu có.
    Khác asyncio.create_task trần: task không bị GC giữa chừng, lỗi được log.
    """
    task = asyncio.create_task(coro)
    _background_tasks.add(task)

    def _on_done(t: asyncio.Task[Any]) -> None:
        _background_tasks.discard(t)
        exc = t.exception() if not t.cancelled() else None
        if exc is not None:
            logger.error("mcp_usage_log_failed: %s", exc)

    task.add_done_callback(_on_done)


# ---------------------------------------------------------------------------
# FastMCP instance
# mcp==1.27.1: stateless_http=True đặt trong constructor (không phải http_app())
# ---------------------------------------------------------------------------
mcp = FastMCP("Medinet Wiki MCP Server", stateless_http=True)


# ---------------------------------------------------------------------------
# Tool: list_hubs
# ---------------------------------------------------------------------------
@mcp.tool()
async def list_hubs(ctx: Context) -> HubList:  # type: ignore[type-arg]
    """Liệt kê các Hub Medinet Wiki mà API key có quyền truy cập.

    Dùng hub_id trả về để filter trong search_wiki / ask_wiki.

    Returns:
        hubs: Danh sách Hub (id, name, description) mà user của API key được phép.
    """
    pool = _get_pool()
    try:
        user = await authenticate_mcp_request(ctx=ctx, pool=pool)
    except ValueError as e:
        raise ToolError(str(e)) from e

    async with pool.acquire() as conn:
        if user.user.role == "admin":
            rows = await conn.fetch(
                "SELECT id, name, description FROM hubs WHERE status = 'active' ORDER BY name"
            )
        else:
            rows = await conn.fetch(
                "SELECT h.id, h.name, h.description "
                "FROM hubs h "
                "JOIN user_hubs uh ON h.id = uh.hub_id "
                "WHERE uh.user_id = $1 AND h.status = 'active' "
                "ORDER BY h.name",
                user.user.id,
            )

    return HubList(
        hubs=[
            HubItem(id=str(r["id"]), name=r["name"], description=r["description"])
            for r in rows
        ]
    )


# ---------------------------------------------------------------------------
# Tool: search_wiki
# ---------------------------------------------------------------------------
@mcp.tool()
async def search_wiki(  # type: ignore[type-arg]
    ctx: Context,
    query: str,
    hub_id: str | None = None,
    top_k: int = 10,
) -> SearchResult:
    """Tìm kiếm tri thức Medinet Wiki bằng vector semantic search.

    Args:
        query: Câu truy vấn tìm kiếm (tiếng Việt hoặc tiếng Anh).
        hub_id: ID Hub cụ thể (tuỳ chọn). Để trống = cross-hub tất cả Hub được phép.
        top_k: Số chunk trả về (mặc định 10, tối đa 20).

    Returns:
        results: Danh sách chunk phù hợp (content, score, document_name, hub_name).
        total: Tổng số kết quả trả về.
    """
    pool = _get_pool()
    try:
        user = await authenticate_mcp_request(ctx=ctx, pool=pool)
    except ValueError as e:
        raise ToolError(str(e)) from e

    from app.schemas.search import SearchRequest  # noqa: PLC0415
    from app.services.search_service import SearchService  # noqa: PLC0415

    svc = SearchService(pool=pool, redis=_get_redis())
    top_k = max(1, min(top_k, 20))  # clamp [1, 20]

    try:
        if hub_id:
            # Single-hub: truyền hub_ids=[hub_id] → SearchService.search enforce isolation
            result = await svc.search(
                body=SearchRequest(query=query, hub_ids=[hub_id], top_k=top_k),
                user=user,
            )
        else:
            # Cross-hub: hub_ids=None → search mọi hub user được phép (D-08)
            result = await svc.search_cross_hub(
                body=SearchRequest(query=query, hub_ids=None, top_k=top_k),
                user=user,
            )
    except HubIsolationError as e:
        raise ToolError(f"HUB_ACCESS_DENIED: {e}") from e
    except Exception as e:  # noqa: BLE001
        logger.error("search_wiki_error: %s", e)
        raise ToolError(f"Search lỗi: {e}") from e

    items = [
        SearchResultItem(
            chunk_id=str(r["id"]),
            content=r.get("snippet") or r.get("content") or "",
            score=float(r["score"]),
            document_name=r.get("title") or "",
            hub_name=r.get("hub_name") or "",
            hub_id=str(r["hub_id"]),
        )
        for r in result.get("results", [])
    ]
    return SearchResult(results=items, total=len(items))


# ---------------------------------------------------------------------------
# Tool: ask_wiki
# ---------------------------------------------------------------------------
@mcp.tool()
async def ask_wiki(  # type: ignore[type-arg]
    ctx: Context,
    query: str,
    hub_id: str | None = None,
) -> AskAnswer:
    """Hỏi-đáp RAG từ Medinet Wiki. Trả câu trả lời + danh sách trích dẫn.

    Args:
        query: Câu hỏi bằng tiếng Việt hoặc tiếng Anh.
        hub_id: ID Hub cụ thể (tuỳ chọn). Để trống = hỏi cross-hub mọi Hub được phép.

    Returns:
        answer: Câu trả lời với marker [1], [2]... chỉ nguồn trích dẫn.
        citations: Danh sách nguồn tương ứng với mỗi marker [N].
    """
    pool = _get_pool()
    try:
        user = await authenticate_mcp_request(ctx=ctx, pool=pool)
    except ValueError as e:
        raise ToolError(str(e)) from e

    from app.schemas.ask import AskRequest  # noqa: PLC0415

    ask_svc = AskService(pool=pool, redis=_get_redis())
    body = AskRequest(query=query, hub_id=hub_id)
    cross_hub = hub_id is None

    try:
        if cross_hub:
            # Cross-hub: hub_ids=None → AskService dùng tất cả hub user được phép
            outcome = await ask_svc.ask_cross_hub(body=body, user=user)
        else:
            # Single-hub: hub_id đã set trong body
            outcome = await ask_svc.ask(body=body, user=user)
    except AskError as e:
        raise ToolError(f"LLM lỗi: {e}") from e
    except HubIsolationError as e:
        raise ToolError(f"HUB_ACCESS_DENIED: {e}") from e
    except Exception as e:  # noqa: BLE001
        logger.error("ask_wiki_error: %s", e)
        raise ToolError(f"Lỗi nội bộ: {e}") from e

    # D-14: log usage_events non-blocking — qua _spawn_usage_log (giữ reference
    # + log lỗi) thay vì asyncio.create_task trần để tránh drop âm thầm (CR-01).
    _spawn_usage_log(
        log_usage_event(
            pool,
            user_id=str(user.user.id),
            hub_id=hub_id,
            model=outcome.usage.model,
            prompt_tokens=outcome.usage.prompt_tokens,
            completion_tokens=outcome.usage.completion_tokens,
            total_tokens=outcome.usage.total_tokens,
            cost_usd=outcome.usage.cost_usd,
            request_id=None,
        )
    )

    return AskAnswer(
        answer=outcome.response.answer,
        citations=[
            CitationItem(
                chunk_id=c.chunk_id,
                document_name=c.document_name,
                hub_name=c.hub_name,
                snippet=c.content_snippet,
                score=c.score,
            )
            for c in outcome.response.citations
        ],
    )
