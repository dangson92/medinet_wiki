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

Phase 8.3 Plan 03 (MCP-02, D-03/D-04): mỗi tool call resolve credential qua
`_resolve_credential` — ưu tiên OAuth Bearer token (verify qua
`provider.load_access_token` → lấy downstream JWT của đúng user từ OAuthStore),
fallback X-API-Key cho client local. `_call_api` forward credential xuống API
Service: nhánh JWT gặp 401 → refresh JWT (`/api/auth/refresh`) → lưu rotation
vào store (Pitfall 5) → retry 1 lần. Hub isolation enforce API-side mỗi call.

Auth: client OAuth gửi `Authorization: Bearer <token>`; client local gửi
`X-API-Key` — cả hai song song. OAuth token verify qua `load_access_token`.

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
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import AnyHttpUrl

from mcp_app.api_client import (
    ApiBadRequestError,
    ApiClient,
    ApiClientError,
    ApiForbiddenError,
    ApiServerError,
    ApiUnauthorizedError,
)
from mcp_app.auth import Credential, extract_api_key, extract_oauth_token
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
            # Phase 8.3 per-user add-on — rỗng = tắt fallback API + bind enforce.
            internal_token=settings.oauth_internal_token,
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


async def _resolve_credential(ctx: Context) -> Credential:  # type: ignore[type-arg]
    """Resolve credential cho tool call — ưu tiên OAuth token, fallback X-API-Key.

    Phase 8.3 Plan 03 (D-03):
    - Có `Authorization: Bearer <token>` → verify qua `provider.load_access_token`
      (SDK kiểm `expires_at` — T-08.3-11). Hợp lệ → đọc downstream JWT của đúng
      user từ OAuthStore → `Credential(kind="jwt", ...)`. Token sai/hết hạn →
      raise ToolError MCP_UNAUTHORIZED (tool KHÔNG chạy logic).
    - Không có OAuth token → thử `X-API-Key` → `Credential(kind="api_key", ...)`
      (client local Claude Code/Desktop không vỡ).
    - Không có cả hai → raise ToolError MCP_UNAUTHORIZED.

    Bảo mật: KHÔNG log giá trị token/JWT — chỉ log `kind`.
    """
    oauth_token = extract_oauth_token(ctx)
    if oauth_token is not None:
        access = await _get_oauth_provider().load_access_token(oauth_token)
        if access is None:
            raise ToolError(
                "MCP_UNAUTHORIZED: token OAuth thiếu, sai hoặc hết hạn "
                "— kết nối lại connector"
            )
        record = await _get_oauth_store().load_token(oauth_token)
        if record is None:
            # load_access_token đã pass nhưng record biến mất — phòng vệ.
            raise ToolError(
                "MCP_UNAUTHORIZED: phiên OAuth không hợp lệ — kết nối lại connector"
            )
        logger.info("Tool call resolve credential: kind=jwt")
        return Credential(
            kind="jwt", value=record["downstream_jwt"], oauth_token=oauth_token
        )

    api_key = extract_api_key(ctx)
    if api_key:
        logger.info("Tool call resolve credential: kind=api_key")
        return Credential(kind="api_key", value=api_key, oauth_token=None)

    raise ToolError(
        "MCP_UNAUTHORIZED: thiếu header Authorization Bearer hoặc X-API-Key"
    )


async def _call_api(
    cred: Credential,
    method: str,
    path: str,
    *,
    json_body: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
) -> Any:
    """Gọi API Service với credential đã resolve. Nhánh JWT: 401 → refresh → retry.

    - `kind == "api_key"` → gọi thẳng, KHÔNG retry (X-API-Key không refresh được).
    - `kind == "jwt"` → gọi với JWT; gặp `ApiUnauthorizedError` lần đầu → refresh
      JWT downstream qua `/api/auth/refresh` → lưu rotation CẢ access + refresh
      vào store (Pitfall 5) → retry 1 lần với JWT mới. Refresh fail (None) →
      re-raise `ApiUnauthorizedError` (tool map ToolError MCP_UNAUTHORIZED).
    """
    client = _get_client()

    async def _do(credential_value: str) -> Any:
        if method == "GET":
            return await client.get(path, jwt=_jwt(cred, credential_value), api_key=_key(cred, credential_value), params=params)
        return await client.post(path, jwt=_jwt(cred, credential_value), api_key=_key(cred, credential_value), json_body=json_body)

    if cred.kind == "api_key":
        return await _do(cred.value)

    # kind == "jwt": thử với JWT hiện tại, 401 → refresh → retry 1 lần.
    try:
        return await _do(cred.value)
    except ApiUnauthorizedError:
        logger.info("Downstream JWT 401 — thử refresh JWT rồi retry")
        store = _get_oauth_store()
        record = await store.load_token(cred.oauth_token or "")
        if record is None:
            raise
        new_pair = await client.refresh_jwt(record["downstream_refresh_token"])
        if new_pair is None:
            # Refresh token cũng hết hạn → user phải re-connect.
            raise
        if not all(new_pair.get(k) for k in ("access_token", "refresh_token")):
            logger.error("refresh_jwt trả payload thiếu access/refresh token")
            raise ApiUnauthorizedError(
                "Phản hồi refresh JWT thiếu trường bắt buộc"
            ) from None
        # Pitfall 5 — lưu đè CẢ downstream JWT + refresh token mới.
        await store.update_downstream_jwt(
            cred.oauth_token or "",
            new_pair["access_token"],
            new_pair["refresh_token"],
        )
        return await _do(new_pair["access_token"])


def _jwt(cred: Credential, value: str) -> str | None:
    """Trả `value` làm JWT nếu credential là nhánh jwt, ngược lại None."""
    return value if cred.kind == "jwt" else None


def _key(cred: Credential, value: str) -> str | None:
    """Trả `value` làm api_key nếu credential là nhánh api_key, ngược lại None."""
    return value if cred.kind == "api_key" else None


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
    cred = await _resolve_credential(ctx)
    try:
        data = await _call_api(
            cred, "GET", "/api/hubs", params={"per_page": 100}
        )
    except ApiClientError as e:
        raise _map_api_error(e) from e

    # API service `/api/hubs` (resp.paginated) trả envelope `{data:[...], meta:{...}}`
    # → `data` đã unwrap là LIST hub. Fallback `dict.get("items")` cho format cũ
    # phòng khi API đổi shape; cuối cùng default `[]`.
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        items = data.get("items", [])
    else:
        items = []
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
    cred = await _resolve_credential(ctx)
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
        data = await _call_api(cred, "POST", path, json_body=body)
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
    cred = await _resolve_credential(ctx)
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
        data = await _call_api(cred, "POST", path, json_body=body)
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

    `streamable_http_path` đặt theo `path_prefix`:
    - rỗng → mặc định `/mcp` (subdomain/authority-root deploy).
    - non-empty (vd `mcp`) → `/` (transport ở root của inner app); wrapper
      ở `build_asgi_app` mount inner dưới `/<prefix>` → external = `/<prefix>`.
    """
    settings = get_settings()
    prefix = settings.path_prefix.strip("/")
    streamable_path = "/" if prefix else "/mcp"

    # SDK auto-bật DNS rebinding protection khi `host` mặc định ("127.0.0.1")
    # với allowed_hosts chỉ gồm localhost. Khi MCP đứng sau reverse proxy
    # public (Cloudflare Tunnel) Host header sẽ là domain public → SDK reject
    # 421 Misdirected Request. Whitelist tường minh: issuer's host + localhost.
    from urllib.parse import urlparse

    issuer_host = urlparse(settings.oauth_issuer_url).netloc
    allowed_hosts = ["127.0.0.1:*", "localhost:*", "[::1]:*"]
    if issuer_host and issuer_host not in allowed_hosts:
        # Exact match — domain public không có port suffix (qua proxy HTTPS 443).
        allowed_hosts.append(issuer_host)
    transport_security = TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=allowed_hosts,
        # allowed_origins rỗng → SDK validate Origin chỉ pass khi Origin absent
        # (server-to-server fetch của Claude — quan sát log không thấy warning
        # Invalid Origin). Nếu sau này Claude/MCP Inspector gửi Origin, thêm
        # `f"https://{issuer_host}"` + `"https://claude.ai"` vào danh sách.
        allowed_origins=[],
    )

    mcp = FastMCP(
        "Medinet Wiki MCP Service",
        stateless_http=True,
        streamable_http_path=streamable_path,
        transport_security=transport_security,
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

    Khi `MCP_PATH_PREFIX` non-empty (path-based deploy dưới cùng domain với
    app khác qua reverse proxy không rewrite path — vd Cloudflare Tunnel):
    wrap inner app dưới Mount(`/<prefix>`, ...) + add 2 route metadata
    RFC 8414/9728 ở root với suffix path (Claude tự fetch ở đường này).
    """
    settings = get_settings()
    prefix = settings.path_prefix.strip("/")

    mcp = _build_mcp()
    inner = mcp.streamable_http_app()  # Starlette app — đã có lifespan SDK
    _sdk_lifespan = inner.router.lifespan_context  # giữ lifespan SDK gốc

    @asynccontextmanager
    async def _composed_lifespan(app_: Any):  # type: ignore[no-untyped-def]
        # startup: khởi tạo schema OAuth store TRƯỚC khi nhận request đầu tiên.
        await _get_oauth_store().init_schema()
        # rồi chạy lifespan SDK (session manager) lồng bên trong.
        async with _sdk_lifespan(app_):
            yield
        # shutdown: đóng store best-effort.
        await _get_oauth_store().aclose()

    inner.router.lifespan_context = _composed_lifespan

    # Mount route login form custom — cạnh route OAuth do SDK tự tạo.
    for route in get_login_routes(_get_oauth_provider(), _get_client()):
        inner.router.routes.append(route)

    # Subdomain/authority-root deploy → trả inner trực tiếp.
    if not prefix:
        return inner

    # Path-based deploy: wrap inner dưới Mount(`/<prefix>`, ...) + add 2
    # route metadata RFC 8414/9728 ở root với suffix path. Claude fetch
    # metadata theo issuer_url (RFC 8414 §3, RFC 9728 §3.1) — path suffix
    # bằng path component của issuer (vd issuer `.../mcp` → metadata path
    # `/.well-known/oauth-*/mcp`).
    from urllib.parse import urlparse

    from mcp.server.auth.handlers.metadata import (
        MetadataHandler,
        ProtectedResourceMetadataHandler,
    )
    from mcp.server.auth.routes import build_metadata
    from mcp.shared.auth import ProtectedResourceMetadata
    from starlette.applications import Starlette
    from starlette.routing import Mount, Route

    issuer = AnyHttpUrl(settings.oauth_issuer_url)
    client_reg = ClientRegistrationOptions(
        enabled=True, valid_scopes=["wiki"], default_scopes=["wiki"]
    )
    revoke = RevocationOptions(enabled=True)
    as_metadata = build_metadata(issuer, None, client_reg, revoke)

    pr_metadata = ProtectedResourceMetadata(
        resource=issuer,
        authorization_servers=[issuer],
        scopes_supported=["wiki"],
    )

    issuer_path = (urlparse(str(issuer)).path or "").rstrip("/")
    as_route_suffix = f"/.well-known/oauth-authorization-server{issuer_path}"
    pr_route_suffix = f"/.well-known/oauth-protected-resource{issuer_path}"
    # Một số client (vd MCP Inspector v0.21.2) KHÔNG follow RFC 8414 §3 cho
    # non-root issuer — chỉ thử `/.well-known/oauth-authorization-server`
    # (no suffix) thay vì có suffix `/mcp`. Serve metadata Ở CẢ 2 vị trí
    # (suffix per RFC + no-suffix dạng "legacy") để tương thích rộng. Cùng
    # content qua cùng handler — không thêm storage / branch.
    as_route_root = "/.well-known/oauth-authorization-server"
    pr_route_root = "/.well-known/oauth-protected-resource"
    # OIDC discovery alias — Inspector + một số client probe `openid-configuration`
    # ngay cả khi server không phải OIDC provider. Serve cùng OAuth metadata
    # (OIDC = superset của OAuth, client OIDC tự ignore field thiếu). Tránh
    # 404 trong log + giúp Inspector hoàn tất discovery loop.
    oidc_route_root = "/.well-known/openid-configuration"
    as_handler = MetadataHandler(as_metadata).handle
    pr_handler = ProtectedResourceMetadataHandler(pr_metadata).handle

    wrapper = Starlette(
        routes=[
            Route(as_route_suffix, endpoint=as_handler, methods=["GET", "OPTIONS"]),
            Route(pr_route_suffix, endpoint=pr_handler, methods=["GET", "OPTIONS"]),
            Route(as_route_root, endpoint=as_handler, methods=["GET", "OPTIONS"]),
            Route(pr_route_root, endpoint=pr_handler, methods=["GET", "OPTIONS"]),
            Route(oidc_route_root, endpoint=as_handler, methods=["GET", "OPTIONS"]),
            Mount(f"/{prefix}", app=inner),
        ],
    )
    # Forward lifespan từ inner (đã compose lifespan SDK + OAuth store) lên
    # wrapper — nếu không, Starlette wrapper start không trigger lifespan
    # của inner → session manager SDK không khởi tạo → transport 500.
    wrapper.router.lifespan_context = inner.router.lifespan_context
    logger.info(
        "MCP build_asgi_app — path-prefix mode prefix=%s as_metadata=%s pr_metadata=%s",
        prefix,
        as_route_suffix,
        pr_route_suffix,
    )
    return wrapper


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
