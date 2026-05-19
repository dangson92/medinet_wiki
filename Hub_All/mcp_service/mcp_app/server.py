"""MCP Service server — Phase 8.2 (MCP-01, MCP-02) + Phase 8.3 (MCP-01).

FastMCP Streamable HTTP server expose 3 tool read-only cho AI client:
- list_hubs   — danh sách Hub mà API key có quyền truy cập
- search_wiki — vector semantic search
- ask_wiki    — RAG ask + citation

KHÁC Phase 8.1 (`api/app/mcp/server.py`): đảo decision D-04. MCP Service nay là
process độc lập — tool KHÔNG import service layer (SearchService/AskService) mà
gọi API Service qua HTTP bằng `ApiClient`. MCP Service KHÔNG truy cập DB/Redis.
KHÔNG tự ghi usage_events — endpoint `/api/ask` của API Service đã ghi qua
BackgroundTasks (D-14 Phase 8.2).

Phase 8.3 (MCP-01): MCP Service nay đóng vai OAuth Authorization Server — wire
`FastMCP(auth_server_provider=MedinetOAuthProvider, auth=AuthSettings(...))` để SDK
tự mount route metadata/`/authorize`/`/token`/`/register`. Thêm route login form
(`/login`). OAuthStore schema khởi tạo trong lifespan startup của Starlette app
(compose với lifespan session-manager của SDK — KHÔNG ghi đè).

Auth: client gửi `X-API-Key` qua header MCP → `require_api_key` trích → forward
xuống API Service; API Service verify (trả 401 nếu sai). OAuth token (8.3) do SDK
verify qua `load_access_token` mỗi tool call.

Transport: Streamable HTTP, stateless_http=True.
"""
from __future__ import annotations

import atexit
import logging
from contextlib import asynccontextmanager
from typing import Any

from mcp.server.auth.settings import (
    AuthSettings,
    ClientRegistrationOptions,
    RevocationOptions,
)
from mcp.server.fastmcp import Context, FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from pydantic import AnyHttpUrl

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
from mcp_app.oauth import MedinetOAuthProvider, OAuthStore
from mcp_app.oauth.login import get_login_routes
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


# ---------------------------------------------------------------------------
# OAuth store + provider singleton (Phase 8.3) — lazy-init giống _get_client()
# ---------------------------------------------------------------------------
_oauth_store: OAuthStore | None = None
_oauth_provider: MedinetOAuthProvider | None = None


def _get_oauth_store() -> OAuthStore:
    """Trả OAuthStore singleton — khởi tạo lười từ config.

    `init_schema()` KHÔNG gọi ở đây — chạy trong lifespan startup (build_asgi_app).
    """
    global _oauth_store
    if _oauth_store is None:
        settings = get_settings()
        _oauth_store = OAuthStore(db_path=settings.oauth_state_db_path)
    return _oauth_store


def _get_oauth_provider() -> MedinetOAuthProvider:
    """Trả MedinetOAuthProvider singleton — inject store + api_client + settings.

    Constructor provider chỉ giữ reference (lazy-safe) → an toàn gọi lúc import.
    """
    global _oauth_provider
    if _oauth_provider is None:
        settings = get_settings()
        _oauth_provider = MedinetOAuthProvider(
            store=_get_oauth_store(),
            api_client=_get_client(),
            issuer_url=settings.oauth_issuer_url,
            access_token_ttl=settings.oauth_access_token_ttl,
            refresh_token_ttl=settings.oauth_refresh_token_ttl,
        )
    return _oauth_provider


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
#
# Phase 8.3: 3 tool nay là hàm module-level THƯỜNG (KHÔNG decorator @mcp.tool()).
# Đăng ký qua `register_tools(mcp)` trong `build_asgi_app()` — vì `build_asgi_app`
# nay là factory tạo FastMCP MỚI mỗi lần gọi (session-manager .run() chỉ chạy
# được 1 lần / instance). Body 3 tool GIỮ NGUYÊN logic Phase 8.2.
# ---------------------------------------------------------------------------
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
    """Best-effort đóng ApiClient + OAuthStore khi process thoát.

    Lifespan shutdown (build_asgi_app) đã đóng OAuthStore — atexit là lớp phòng
    vệ thêm cho trường hợp process thoát ngoài vòng đời ASGI. Nếu lỗi (loop đang
    chạy, đã đóng) → chỉ log warning, không raise lúc thoát.
    """
    global _api_client, _oauth_store
    import asyncio

    if _api_client is not None:
        try:
            asyncio.run(_api_client.aclose())
        except Exception as e:  # noqa: BLE001 — cleanup best-effort lúc thoát
            logger.warning(
                "Không đóng được ApiClient lúc thoát: %s", type(e).__name__
            )
        finally:
            _api_client = None

    if _oauth_store is not None:
        try:
            asyncio.run(_oauth_store.aclose())
        except Exception as e:  # noqa: BLE001 — cleanup best-effort lúc thoát
            logger.warning(
                "Không đóng được OAuthStore lúc thoát: %s", type(e).__name__
            )
        finally:
            _oauth_store = None


atexit.register(_close_client_atexit)


def register_tools(mcp: FastMCP) -> None:
    """Đăng ký 3 tool read-only lên một FastMCP instance.

    Tách khỏi định nghĩa hàm để `build_asgi_app()` tạo FastMCP mới mỗi lần gọi
    (factory) — `mcp.tool()` trả lại chính hàm gốc, không bọc, nên 3 hàm
    `list_hubs`/`search_wiki`/`ask_wiki` vẫn import trực tiếp được cho unit test.
    """
    mcp.tool()(list_hubs)
    mcp.tool()(search_wiki)
    mcp.tool()(ask_wiki)


def _build_mcp() -> FastMCP:
    """Dựng FastMCP instance MỚI wired OAuth Authorization Server (Phase 8.3).

    stateless_http=True — Streamable HTTP transport không giữ session (Pitfall 2,
    KHÔNG xung đột OAuth). `auth_server_provider` non-None → SDK tự mount route
    metadata/`/authorize`/`/token`/`/register` (create_auth_routes). AuthSettings
    issuer_url đọc từ config (default an toàn → Settings() không raise khi thiếu env).
    """
    settings = get_settings()
    mcp = FastMCP(
        "Medinet Wiki MCP Service",
        stateless_http=True,
        auth_server_provider=_get_oauth_provider(),
        auth=AuthSettings(
            issuer_url=AnyHttpUrl(settings.oauth_issuer_url),
            resource_server_url=AnyHttpUrl(settings.oauth_issuer_url),
            client_registration_options=ClientRegistrationOptions(
                enabled=True,
                valid_scopes=["wiki"],
                default_scopes=["wiki"],
            ),
            revocation_options=RevocationOptions(enabled=True),
            required_scopes=["wiki"],
        ),
    )
    register_tools(mcp)
    return mcp


def build_asgi_app() -> Any:
    """Factory tạo Starlette ASGI app cho MCP Service standalone.

    Tạo FastMCP MỚI mỗi lần gọi — `StreamableHTTPSessionManager.run()` chỉ chạy
    được 1 lần / instance, nên factory cần instance riêng cho mỗi app (Dockerfile
    CMD dùng `uvicorn ... --factory`).

    `mcp.streamable_http_app()` trả Starlette app đã tự gắn lifespan session
    manager + route OAuth do SDK mount khi `auth_server_provider` non-None
    (metadata/`/authorize`/`/token`/`/register`).

    Phase 8.3: compose lifespan — chạy `OAuthStore.init_schema()` lúc startup
    TRƯỚC khi nhận request đầu tiên, rồi mới chạy lifespan SDK lồng bên trong.
    Cách compose này bảo toàn lifespan session-manager của SDK (KHÔNG ghi đè).
    Route `/login` + `/login/callback` thêm vào app sau khi SDK đã mount route OAuth.
    """
    mcp = _build_mcp()
    app = mcp.streamable_http_app()  # Starlette app — đã có lifespan SDK
    _sdk_lifespan = app.router.lifespan_context  # giữ lifespan SDK gốc

    @asynccontextmanager
    async def _composed_lifespan(app_: Any):  # type: ignore[no-untyped-def]
        # startup: khởi tạo schema OAuth store TRƯỚC khi nhận request đầu tiên.
        await _get_oauth_store().init_schema()
        # rồi chạy lifespan SDK (session manager) lồng bên trong.
        async with _sdk_lifespan(app_):
            yield
        # shutdown: đóng store best-effort.
        await _get_oauth_store().aclose()

    app.router.lifespan_context = _composed_lifespan

    # Mount route login form custom — cạnh route OAuth do SDK tự tạo.
    for route in get_login_routes(_get_oauth_provider(), _get_client()):
        app.router.routes.append(route)

    return app


def main() -> None:
    """Entrypoint chạy MCP Service như process độc lập trên port riêng.

    `python -m mcp_app.server` → __name__ == "__main__" → main(). Lắng nghe
    host/port từ config (`MCP_SERVICE_HOST` / `MCP_SERVICE_PORT`).
    """
    import uvicorn

    logging.basicConfig(level=logging.INFO)
    settings = get_settings()
    app = build_asgi_app()
    # KHÔNG log api_key/token/signing key — chỉ log host/port/url (T-08.2-03-I2).
    # oauth_issuer_url là URL public — an toàn để log.
    logger.info(
        "MCP Service khởi động — host=%s port=%s api_base_url=%s oauth_issuer_url=%s",
        settings.service_host,
        settings.service_port,
        settings.api_base_url,
        settings.oauth_issuer_url,
    )
    uvicorn.run(app, host=settings.service_host, port=settings.service_port)


if __name__ == "__main__":
    main()
