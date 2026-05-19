"""MCP Service server — Phase 8.2 (MCP-01, MCP-02).

FastMCP Streamable HTTP server expose 3 tool read-only cho AI client:
- list_hubs   — danh sách Hub mà API key có quyền truy cập
- search_wiki — vector semantic search
- ask_wiki    — RAG ask + citation

KHÁC Phase 8.1 (`api/app/mcp/server.py`): đảo decision D-04. MCP Service nay là
process độc lập — tool KHÔNG import service layer (SearchService/AskService) mà
gọi API Service qua HTTP bằng `ApiClient`. MCP Service KHÔNG truy cập DB/Redis.
KHÔNG tự ghi usage_events — endpoint `/api/ask` của API Service đã ghi qua
BackgroundTasks (D-14 Phase 8.2).

Auth: client gửi `X-API-Key` qua header MCP → `require_api_key` trích → forward
xuống API Service; API Service verify (trả 401 nếu sai).

Transport: Streamable HTTP, stateless_http=True.
"""
from __future__ import annotations

import atexit
import logging
from typing import Any

from mcp.server.fastmcp import Context, FastMCP
from mcp.server.fastmcp.exceptions import ToolError

from mcp_app.api_client import (
    ApiBadRequestError,
    ApiClient,
    ApiClientError,
    ApiForbiddenError,
    ApiServerError,
    ApiUnauthorizedError,
)
from mcp_app.auth import require_api_key
from mcp_app.config import get_settings
from mcp_app.schemas import (
    AskAnswer,
    CitationItem,
    HubItem,
    HubList,
    SearchResult,
    SearchResultItem,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# FastMCP instance
# stateless_http=True — Streamable HTTP transport không giữ session state
# ---------------------------------------------------------------------------
mcp = FastMCP("Medinet Wiki MCP Service", stateless_http=True)

# ---------------------------------------------------------------------------
# ApiClient singleton — tái dùng 1 AsyncClient cho connection pooling
# ---------------------------------------------------------------------------
_api_client: ApiClient | None = None


def _get_client() -> ApiClient:
    """Trả về ApiClient singleton — khởi tạo lười từ config lần gọi đầu.

    Tái dùng cùng `httpx.AsyncClient` cho mọi request để giữ connection pool.
    """
    global _api_client
    if _api_client is None:
        settings = get_settings()
        _api_client = ApiClient(
            base_url=settings.api_base_url,
            timeout=settings.http_timeout,
        )
    return _api_client


def _map_api_error(e: ApiClientError) -> ToolError:
    """Map exception của ApiClient sang ToolError MCP với mã lỗi rõ ràng.

    Bảo mật (T-08.2-03-I): message ngắn gọn, KHÔNG đính kèm stack trace hay
    chi tiết exception nội bộ — chỉ dùng message từ envelope error của API.
    """
    if isinstance(e, ApiUnauthorizedError):
        return ToolError("MCP_UNAUTHORIZED: xác thực thất bại — kiểm tra X-API-Key")
    if isinstance(e, ApiForbiddenError):
        return ToolError(f"HUB_ACCESS_DENIED: {e}")
    if isinstance(e, ApiBadRequestError):
        return ToolError(f"INVALID_QUERY: {e}")
    if isinstance(e, ApiServerError):
        return ToolError(f"API_ERROR: {e}")
    return ToolError("API_ERROR: lỗi không xác định khi gọi API Service")


def _to_citations(raw: list[dict[str, Any]], *, cross_hub: bool) -> list[CitationItem]:
    """Chuyển danh sách citation thô từ API sang CitationItem.

    Hai endpoint trả citation với field khác nhau:
    - `/api/ask` (single-hub): field `chunk_id` + `content_snippet`.
    - `/api/search/answer` (cross-hub): field `id` (=chunk_id) + `snippet`.
    """
    items: list[CitationItem] = []
    for c in raw:
        if cross_hub:
            chunk_id = str(c.get("id") or c.get("chunk_id") or "")
            snippet = c.get("snippet") or c.get("content_snippet") or ""
        else:
            chunk_id = str(c.get("chunk_id") or c.get("id") or "")
            snippet = c.get("content_snippet") or c.get("snippet") or ""
        items.append(
            CitationItem(
                chunk_id=chunk_id,
                document_name=c.get("document_name") or "",
                hub_name=c.get("hub_name") or "",
                snippet=snippet,
                score=float(c.get("score") or 0.0),
            )
        )
    return items


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
    api_key = require_api_key(ctx)
    try:
        data = await _get_client().get(
            "/api/hubs", api_key=api_key, params={"per_page": 100}
        )
    except ApiClientError as e:
        raise _map_api_error(e) from e

    items = data.get("items", []) if isinstance(data, dict) else []
    return HubList(
        hubs=[
            HubItem(
                id=str(i["id"]),
                name=i["name"],
                description=i.get("description"),
            )
            for i in items
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
    api_key = require_api_key(ctx)
    top_k = max(1, min(top_k, 20))  # clamp [1, 20]

    if hub_id:
        # Single-hub: hub_ids=[hub_id] → API enforce hub isolation
        path = "/api/search"
        body: dict[str, Any] = {"query": query, "hub_ids": [hub_id], "top_k": top_k}
    else:
        # Cross-hub: hub_ids=None → API search mọi hub user được phép
        path = "/api/search/cross-hub"
        body = {"query": query, "hub_ids": None, "top_k": top_k}

    try:
        data = await _get_client().post(path, api_key=api_key, json_body=body)
    except ApiClientError as e:
        raise _map_api_error(e) from e

    raw_results = data.get("results", []) if isinstance(data, dict) else []
    items = [
        SearchResultItem(
            chunk_id=str(r.get("id") or r.get("chunk_id") or ""),
            content=r.get("content") or r.get("snippet") or "",
            score=float(r.get("score") or 0.0),
            document_name=r.get("title") or r.get("document_name") or "",
            hub_name=r.get("hub_name") or "",
            hub_id=str(r.get("hub_id") or ""),
        )
        for r in raw_results
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
        answer: Câu trả lời với marker chỉ nguồn trích dẫn.
        citations: Danh sách nguồn tương ứng với mỗi marker.

    Lưu ý: answer được trả NGUYÊN từ API Service. Single-hub (/api/ask) giữ marker
    [N]; cross-hub (/api/search/answer) answer có thể đã rewrite marker [src:<id>]
    — tool không can thiệp text answer, citations vẫn structured để client attribute.
    KHÔNG tự ghi usage_events — /api/ask đã ghi qua BackgroundTasks (D-14).
    """
    api_key = require_api_key(ctx)
    cross_hub = hub_id is None

    if cross_hub:
        # Cross-hub: /api/ask/cross-hub yêu cầu hub_ids non-rỗng → KHÔNG dùng được.
        # /api/search/answer chấp nhận hub_ids null, non-admin tự intersect hub.
        path = "/api/search/answer"
        body: dict[str, Any] = {"query": query, "hub_ids": None}
    else:
        path = "/api/ask"
        body = {"query": query, "hub_id": hub_id}

    try:
        data = await _get_client().post(path, api_key=api_key, json_body=body)
    except ApiClientError as e:
        raise _map_api_error(e) from e

    answer = data.get("answer", "") if isinstance(data, dict) else ""
    raw_citations = data.get("citations", []) if isinstance(data, dict) else []
    return AskAnswer(
        answer=answer,
        citations=_to_citations(raw_citations, cross_hub=cross_hub),
    )


# ---------------------------------------------------------------------------
# Entrypoint — chạy MCP Service standalone trên port riêng
# ---------------------------------------------------------------------------
def _close_client_atexit() -> None:
    """Best-effort đóng ApiClient khi process thoát.

    `streamable_http_app()` trả Starlette app gốc — không cho thêm on_shutdown
    handler dễ dàng. Dùng atexit best-effort: chạy aclose() trong event loop mới.
    Nếu lỗi (loop đang chạy, đã đóng) → chỉ log warning, không raise lúc thoát.
    """
    global _api_client
    if _api_client is None:
        return
    try:
        import asyncio

        asyncio.run(_api_client.aclose())
    except Exception as e:  # noqa: BLE001 — cleanup best-effort lúc thoát process
        logger.warning("Không đóng được ApiClient lúc thoát: %s", type(e).__name__)
    finally:
        _api_client = None


atexit.register(_close_client_atexit)


def build_asgi_app() -> Any:
    """Tạo Starlette ASGI app cho MCP Service standalone.

    `mcp.streamable_http_app()` trả Starlette app và tự gắn lifespan session
    manager (`StreamableHTTPSessionManager.run()`) — KHÔNG cần compose lifespan
    thủ công như `api/app/main.py` vì đây là app gốc, không phải sub-mount.
    """
    return mcp.streamable_http_app()


def main() -> None:
    """Entrypoint chạy MCP Service như process độc lập trên port riêng.

    `python -m mcp_app.server` → __name__ == "__main__" → main(). Lắng nghe
    host/port từ config (`MCP_SERVICE_HOST` / `MCP_SERVICE_PORT`).
    """
    import uvicorn

    logging.basicConfig(level=logging.INFO)
    settings = get_settings()
    app = build_asgi_app()
    # KHÔNG log api_key — chỉ log host/port/api_base_url (T-08.2-03-I2)
    logger.info(
        "MCP Service khởi động — host=%s port=%s api_base_url=%s",
        settings.service_host,
        settings.service_port,
        settings.api_base_url,
    )
    uvicorn.run(app, host=settings.service_host, port=settings.service_port)


if __name__ == "__main__":
    main()
