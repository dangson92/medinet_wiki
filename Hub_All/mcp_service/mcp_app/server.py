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

import asyncio
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
from mcp.types import ToolAnnotations
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


# HIGH-03 (audit 2026-05-21): asyncio.Lock per OAuth access_token cho khối
# refresh JWT downstream. 2 tool song song cùng OAuth token + downstream JWT
# vừa hết hạn — không lock thì tool 1 refresh OK, tool 2 refresh với token
# đã rotate → API 401 → tool 2 fail không deterministic. Lock đảm bảo
# single-flight refresh; tool sau đọc lại record (đã update từ tool trước).
#
# Memory profile: 1 Lock ~ 56 bytes (Python 3.12 CPython), key string ~80
# byte → 1 token entry ~ 136 byte. 1000 user concurrent ~ 136 KB — chấp
# nhận được. Cleanup wire từ provider.revoke_token qua late import.
_refresh_locks: dict[str, asyncio.Lock] = {}


def _get_refresh_lock(oauth_token: str) -> asyncio.Lock:
    """Trả asyncio.Lock cho oauth_token — lazy create. Single-flight refresh JWT."""
    lock = _refresh_locks.get(oauth_token)
    if lock is None:
        lock = asyncio.Lock()
        _refresh_locks[oauth_token] = lock
    return lock


def _release_refresh_lock(oauth_token: str) -> None:
    """Xoá lock entry khỏi pool — gọi từ provider.revoke_token (qua late import)
    để tránh memory leak khi user revoke token.

    Best-effort: lock đang held → caller chờ ở `async with` ngoài → pop chỉ xoá
    reference trong dict; lock object tự GC khi không còn ref ngoài. KHÔNG raise
    nếu key không tồn tại (pop default).

    HIGH-03 cleanup: wire qua provider.revoke_token với pattern late import
    `from mcp_app.server import _release_refresh_lock` (xem
    `_close_client_atexit:439 import asyncio` cho pattern tương tự).
    """
    _refresh_locks.pop(oauth_token, None)


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

    HIGH-03 (audit 2026-05-21): khối refresh JWT bọc `async with _get_refresh_lock`
    → single-flight refresh per access_token. Tool 1 vào lock refresh + lưu;
    tool 2 chờ lock, đọc lại record (đã update) → thấy downstream JWT mới →
    KHÔNG refresh lần 2.
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
        oauth_token = cred.oauth_token or ""

        # HIGH-03: single-flight refresh per access_token. Tool 1 vào lock,
        # refresh + lưu; tool 2 chờ lock, đọc lại record (đã update) → thấy
        # downstream JWT mới → KHÔNG refresh lại lần 2.
        async with _get_refresh_lock(oauth_token):
            record = await store.load_token(oauth_token)
            if record is None:
                raise

            # Re-check: nếu tool trước đã refresh, downstream_jwt khác cred.value
            # → retry với JWT mới ngay (skip refresh).
            if record["downstream_jwt"] != cred.value:
                logger.info(
                    "Downstream JWT đã được tool song song refresh — retry "
                    "với JWT mới"
                )
                return await _do(record["downstream_jwt"])

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
                oauth_token,
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


def _read_only_annotations(title: str) -> ToolAnnotations:
    """Tool safety hints consumed by Claude/MCP clients for approval gating."""
    return ToolAnnotations(
        title=title,
        readOnlyHint=True,
        destructiveHint=False,
        openWorldHint=False,
    )


def register_tools(mcp: FastMCP) -> None:
    """Đăng ký 3 tool read-only lên một FastMCP instance.

    Tách khỏi định nghĩa hàm để `build_asgi_app()` tạo FastMCP mới mỗi lần gọi
    (factory) — `mcp.tool()` trả lại chính hàm gốc, không bọc, nên 3 hàm
    `list_hubs`/`search_wiki`/`ask_wiki` vẫn import trực tiếp được cho unit test.
    """
    mcp.tool(
        title="List hubs",
        annotations=_read_only_annotations("List hubs"),
    )(list_hubs)
    mcp.tool(
        title="Search wiki",
        annotations=_read_only_annotations("Search wiki"),
    )(search_wiki)
    mcp.tool(
        title="Ask wiki",
        annotations=_read_only_annotations("Ask wiki"),
    )(ask_wiki)


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

    # CORS — RFC 8414 §3.1 / RFC 9728 §3.1 yêu cầu metadata endpoint OAuth
    # support CORS để browser-based client dùng được. MCP Inspector
    # (localhost:6274) + Claude web (claude.ai) fetch cross-origin → cần
    # `Access-Control-Allow-Origin`.
    #
    # CRIT-02 (audit 2026-05-21 — đã đóng Plan 08.3-07): CHỈ add CORS Ở MỘT
    # TẦNG. Subdomain mode add ở inner (return ngay sau); path-prefix mode
    # add ở wrapper outer THÔI.
    #
    # CRIT-01 (audit 2026-05-21 — Plan 10-04): thay 1 hàm `_add_cors_middleware`
    # (allow_origins=["*"] cho TẤT CẢ route) bằng `_MultiPolicyCORSMiddleware`
    # ASGI wrapper tách 2 policy theo path — metadata wildcard `*`, sensitive
    # whitelist origin từ `settings.mcp_oauth_sensitive_allowed_origins`.

    # Subdomain/authority-root deploy → wrap inner bằng
    # _MultiPolicyCORSMiddleware (ngoài) → _BasicAuthFormShim (Basic→form
    # shim) → inner SDK app. Order: CORS chạy TRƯỚC khi Basic→form rewrite
    # path → CORS quyết định Origin ngay từ scope ban đầu (đúng path).
    if not prefix:
        cors_wrapped = _MultiPolicyCORSMiddleware(
            _BasicAuthFormShim(inner),
            settings.mcp_oauth_sensitive_allowed_origins,
        )
        return cors_wrapped

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

    # MCP SDK Python ClientAuthenticator (client_auth.py) yêu cầu `client_id`
    # XUẤT HIỆN TRONG FORM BODY — KHÔNG đọc từ Authorization Basic header.
    # Vì vậy server thực chất CHỈ support `client_secret_post`, dù SDK mặc
    # định quảng cáo CẢ `client_secret_basic`.
    #
    # Bug user gặp: MCP Inspector cho user nhập tay client_id/secret →
    # clientInformation thiếu `token_endpoint_auth_method` → MCP TS SDK
    # `selectClientAuthMethod` ưu tiên basic > post (auth.js dòng 47-51) →
    # gửi credentials qua header, form body trống `client_id` → server trả
    # 401 "Missing client_id".
    #
    # Fix: bỏ quảng cáo `client_secret_basic`. Client tự fallback sang post,
    # gửi `client_id` trong form → ClientAuthenticator pass. Claude web đã
    # dùng post (DCR/per-user response set explicit auth_method) → không
    # bị ảnh hưởng. Áp dụng CẢ token + revocation endpoint (revoke handler
    # cũng dùng cùng ClientAuthenticator).
    as_metadata.token_endpoint_auth_methods_supported = ["client_secret_post"]
    if as_metadata.revocation_endpoint_auth_methods_supported is not None:
        as_metadata.revocation_endpoint_auth_methods_supported = [
            "client_secret_post"
        ]

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
    # CORS — Plan 10-04 thay `_add_cors_middleware(wrapper)` (Starlette
    # CORSMiddleware allow_origins=["*"]) bằng `_MultiPolicyCORSMiddleware`
    # ASGI wrapper. CRIT-01: sensitive endpoint (/<prefix>/token, /<prefix>
    # /authorize, ...) chỉ echo ACAO nếu Origin trong whitelist; metadata
    # vẫn wildcard. Wrap NGOÀI wrapper để CORS xét scope.path GỐC (trước
    # khi _AsgiPathShim rewrite). Lý do: malicious browser tab gọi /token
    # với Host attacker → _AsgiPathShim sẽ rewrite thành /<prefix>/token →
    # nhưng CORS đã chặn ở scope ban đầu, request không reach inner.
    wrapper_with_cors = _MultiPolicyCORSMiddleware(
        wrapper, settings.mcp_oauth_sensitive_allowed_origins
    )
    logger.info(
        "MCP build_asgi_app — path-prefix mode prefix=%s as_metadata=%s pr_metadata=%s",
        prefix,
        as_route_suffix,
        pr_route_suffix,
    )
    # Bọc wrapper thêm shim ASGI: rewrite path 2 trường hợp NGAY TRƯỚC khi
    # Starlette Router xét routes.
    #
    # (1) `/<prefix>` exact → `/<prefix>/` — chặn 307 redirect mà Router tự
    #     phát do `redirect_slashes=True` (mặc định). Mount regex
    #     `^/<prefix>/(?P<path>.*)$` KHÔNG match exact `/<prefix>`.
    #     Tại sao 307 nguy hiểm: Claude (web) gửi POST `/<prefix>` kèm
    #     `Authorization: Bearer …` + header phiên `Mcp-Session-Id`. RFC 7231
    #     §6.4.7 quy 307 giữ method, nhưng nhiều HTTP runtime DROP
    #     `Authorization` (security default) khi follow redirect → 401 ngẫu nhiên.
    #
    # (2) `/token`, `/authorize`, `/register`, `/revoke` ở root →
    #     `/<prefix>/...` — alias cho client (vd MCP Inspector v0.21.2) khi
    #     metadata discovery fail vì lỗi nào đó (CORS, network, version cũ)
    #     → fallback default endpoint ở origin gốc thay vì path đúng theo
    #     metadata. Forward sang inner SDK qua Mount(`/<prefix>`, ...).
    #
    # Path khác (`/.well-known/*`, `/login`, `/<prefix>/...`) pass-through
    # nguyên. Lifespan/websocket scope cũng pass-through.
    #
    # Order: _AsgiPathShim (ngoài cùng) → _BasicAuthFormShim → _MultiPolicyCORS
    # → wrapper. _AsgiPathShim rewrite path (vd `/token` → `/mcp/token`)
    # TRƯỚC khi CORS kiểm path → CORS dùng path đã chuẩn hoá (sau rewrite),
    # phù hợp với policy `/mcp/token` (sensitive). _BasicAuthFormShim bridge
    # Basic→form NGAY TRƯỚC khi wrapper Router dispatch xuống inner SDK
    # ClientAuthenticator.
    #
    # CRIT-01 Plan 10-04: CORS đặt giữa _BasicAuthFormShim và wrapper (KHÔNG
    # ngoài cùng). Lý do: _AsgiPathShim rewrite path `/token` → `/mcp/token`
    # → CORS check path `/mcp/token` (sensitive whitelist). Nếu CORS ngoài
    # cùng, sẽ check path `/token` GỐC (cũng sensitive theo
    # `_SENSITIVE_PATHS`) — vẫn đúng, nhưng đặt sau path rewrite cho phép
    # path-prefix variant nhất quán.
    return _AsgiPathShim(_BasicAuthFormShim(wrapper_with_cors), prefix=prefix)


# OAuth endpoint path mà SDK MCP mount dưới inner — alias ở root (Fix B)
# để cover client bỏ qua metadata discovery, hard-code endpoint default
# `{origin}/token`, `{origin}/authorize`, ... Giữ exact-match frozenset
# để tra cứu O(1) + tránh false-positive với sub-path (`/tokens`, ...).
_OAUTH_ROOT_ALIAS_PATHS = frozenset(
    {"/token", "/authorize", "/register", "/revoke"}
)

# Path POST cần shim convert Basic → form (xem _BasicAuthFormShim). Cover
# cả root variant + mọi prefix variant (sau khi _AsgiPathShim rewrite,
# path luôn có prefix). Frozenset → O(1) lookup. KHÔNG include /authorize
# vì /authorize không cần client_secret (chỉ /token + /revoke dùng
# ClientAuthenticator).
_BASIC_AUTH_SHIM_PATHS = frozenset(
    {"/token", "/revoke", "/mcp/token", "/mcp/revoke"}
)


# ---------------------------------------------------------------------------
# CRIT-01 fix (audit 2026-05-21 — Plan 10-04): _MultiPolicyCORSMiddleware
# ---------------------------------------------------------------------------
# Tách 2 CORS policy theo path thay vì 1 hàm `_add_cors_middleware` cũ
# (allow_origins=["*"] cho TẤT CẢ route gồm /token + /authorize + /revoke).
#
# Path metadata (`/.well-known/*`) → wildcard origin "*" (RFC 8414 §3.1 + RFC
# 9728 §3.1 cho phép vì metadata public, không có credential).
#
# Path sensitive (/token, /authorize, /revoke, /register, /mcp[/*]) → whitelist
# origin từ `settings.mcp_oauth_sensitive_allowed_origins`. Origin không match
# → KHÔNG echo ACAO → browser block (CORS spec: response thiếu ACAO → reject).
#
# Khai thác audit ghi nhận: malicious browser extension hoặc tab compromised
# có thể gọi /token + transport tools từ origin bất kỳ chỉ cần biết Bearer
# token (vd qua XSS app khác). Phòng vệ duy nhất hiện tại là token nằm trong
# memory client OAuth — Claude/Inspector đều giữ client-side, có thể leak qua
# XSS. Tách CORS giảm bề mặt khai thác xuống còn 4 origin whitelist.

# Path metadata (wildcard origin OK per RFC 8414 §3.1 / RFC 9728 §3.1).
# Suffix path (vd /mcp) thêm động ở build_asgi_app (issuer path component).
_METADATA_PATHS_PREFIX = (
    "/.well-known/oauth-authorization-server",
    "/.well-known/oauth-protected-resource",
    "/.well-known/openid-configuration",
)

# Path sensitive (whitelist origin). Cover root variant + prefix variant.
_SENSITIVE_PATHS = frozenset(
    {
        "/token",
        "/authorize",
        "/revoke",
        "/register",
        "/mcp/token",
        "/mcp/authorize",
        "/mcp/revoke",
        "/mcp/register",
        "/mcp",  # transport endpoint root
    }
)


def _is_metadata_path(path: str) -> bool:
    """Check path khớp prefix metadata (cover cả suffix /mcp + variant).

    Cover 3 dạng path metadata gặp trong cả 2 mode deploy:
    1. Root suffix RFC 8414 §3 — `/.well-known/oauth-*` (subdomain mode +
       path-prefix wrapper level).
    2. Path-prefix mode forward đến inner SDK — `/<prefix>/.well-known/oauth-*`
       (SDK mount metadata route ở inner, sau khi wrapper Mount forward).
    3. OIDC alias — `/.well-known/openid-configuration` + path-prefix variant.
    """
    # Direct match (subdomain mode + wrapper level path-prefix).
    if any(path.startswith(p) for p in _METADATA_PATHS_PREFIX):
        return True
    # Path-prefix mode: `/<prefix>/.well-known/...` (sau khi wrapper Mount
    # forward request xuống inner SDK metadata route). Cover bằng substring
    # match `.well-known/oauth-` HOẶC `.well-known/openid-configuration`.
    return "/.well-known/oauth-" in path or "/.well-known/openid-configuration" in path


def _is_sensitive_path(path: str) -> bool:
    """Check path là sensitive OAuth endpoint hoặc transport /mcp[/*].

    KHÔNG bao gồm path metadata — metadata được _is_metadata_path xét TRƯỚC
    (caller `_build_cors_headers` check metadata trước sensitive).
    """
    if path in _SENSITIVE_PATHS:
        return True
    # /mcp/<anything> = transport stream hoặc OAuth path-prefix variant.
    return path == "/mcp" or path.startswith("/mcp/")


class _MultiPolicyCORSMiddleware:
    """ASGI middleware tách CORS policy theo path (CRIT-01 fix audit 2026-05-21).

    - Metadata path (`/.well-known/*`) → wildcard origin (`*`) per RFC 8414 §3.1.
    - Sensitive path (`/token`, `/authorize`, `/revoke`, `/register`, `/mcp[/*]`)
      → whitelist origin từ `settings.mcp_oauth_sensitive_allowed_origins`.
    - Path khác (vd `/login`) → KHÔNG inject CORS header (Starlette router
      handle default; login form trả HTML cho user, không cần CORS).

    Defense in depth chống malicious browser extension/tab compromised gọi
    /token + transport tools từ origin bất kỳ chỉ cần biết Bearer token leak
    qua XSS app khác.

    Implementation: ASGI wrapper (giống `_BasicAuthFormShim`), KHÔNG dùng
    Starlette `add_middleware`. Lý do: subdomain mode chỉ có 1 app level
    (KHÔNG có 2-level wrapper+inner như path-prefix), Starlette CORSMiddleware
    KHÔNG support per-route policy native — phải custom logic chọn policy
    theo path. Wrap chung 1 middleware cho cả 2 mode (đơn giản, deterministic).

    Phương pháp OPTIONS preflight: trả full response trong middleware (status
    200 + ACAO + ACAM + ACAH + Max-Age). KHÔNG forward xuống inner — Starlette
    router default không có handler OPTIONS riêng cho route metadata/transport,
    sẽ trả 405 hoặc 404 nếu pass-through.

    Bảo mật: KHÔNG log giá trị Origin header → grep audit-clean.
    """

    def __init__(self, app: Any, sensitive_origins: list[str]) -> None:
        self._app = app
        # frozenset → O(1) lookup, immutable.
        self._sensitive_origins = frozenset(sensitive_origins)

    async def __call__(
        self, scope: Any, receive: Any, send: Any
    ) -> None:
        if scope.get("type") != "http":
            await self._app(scope, receive, send)
            return

        path = scope.get("path", "")
        method = scope.get("method", "").upper()
        request_origin = self._extract_origin(scope.get("headers", []))

        if method == "OPTIONS":
            # Preflight — handle full response trong middleware.
            # Starlette router KHÔNG có default OPTIONS handler cho route
            # metadata/transport → pass-through sẽ 405/404. Build response
            # với CORS header tay theo policy.
            response = self._build_preflight_response(path, request_origin)
            await self._send_preflight(response, send)
            return

        # Non-OPTIONS request: forward xuống inner app, intercept response.start
        # để inject CORS header theo policy.
        #
        # CRIT-02 regression guard (Plan 08.3-07 đã đóng): KHÔNG append header
        # nếu inner đã set sẵn (vd MetadataHandler của SDK MCP tự inject ACAO).
        # Duplicate ACAO → browser reject (CORS spec). Check existing header
        # tên case-insensitive trước khi append.
        cors_headers = self._build_cors_headers(path, request_origin)

        async def _wrapped_send(message: dict[str, Any]) -> None:
            if message.get("type") == "http.response.start" and cors_headers:
                headers = list(message.get("headers", []))
                # Build set tên header đã tồn tại (lower-case bytes).
                existing_names = {
                    (name if isinstance(name, bytes) else name.encode("latin-1")).lower()
                    for name, _ in headers
                }
                for name, value in cors_headers.items():
                    name_b = name.encode("ascii")
                    # Skip nếu inner đã set — tránh duplicate header
                    # (đặc biệt access-control-allow-origin).
                    if name_b.lower() in existing_names:
                        continue
                    headers.append((name_b, value.encode("ascii")))
                message = dict(message, headers=headers)
            await send(message)

        await self._app(scope, receive, _wrapped_send)

    def _extract_origin(
        self, headers: list[tuple[bytes, bytes]]
    ) -> str | None:
        """Trích Origin header từ scope headers (case-insensitive)."""
        for name, value in headers:
            name_b = name if isinstance(name, bytes) else name.encode("latin-1")
            if name_b.lower() == b"origin":
                value_b = (
                    value if isinstance(value, bytes) else value.encode("latin-1")
                )
                return value_b.decode("latin-1")
        return None

    def _build_cors_headers(
        self, path: str, origin: str | None
    ) -> dict[str, str]:
        """Trả CORS header cho response thật (non-OPTIONS) theo policy path.

        - Metadata: ACAO `*` (RFC 8414 §3.1 — KHÔNG cần Origin trong request).
        - Sensitive + origin trong whitelist: ACAO echo origin + Vary: Origin.
        - Còn lại: rỗng (KHÔNG inject CORS header).
        """
        if _is_metadata_path(path):
            return {
                "access-control-allow-origin": "*",
                "access-control-expose-headers": "Mcp-Session-Id, WWW-Authenticate",
            }
        if _is_sensitive_path(path) and origin and origin in self._sensitive_origins:
            return {
                "access-control-allow-origin": origin,
                "vary": "Origin",
                "access-control-expose-headers": "Mcp-Session-Id, WWW-Authenticate",
            }
        return {}

    def _build_preflight_response(
        self, path: str, origin: str | None
    ) -> dict[str, Any]:
        """Build preflight response (status + headers) theo policy path.

        Origin/path không match whitelist → trả 200 KHÔNG có CORS header →
        browser block CORS (response thiếu ACAO). Origin match → full
        preflight headers (ACAO + ACAM + ACAH + Max-Age + Vary).
        """
        cors = self._build_cors_headers(path, origin)
        if not cors:
            # Origin không match hoặc path không trong policy → 200 trống,
            # browser block CORS preflight.
            return {"status": 200, "headers": []}

        # Preflight full headers — bổ sung ACAM + ACAH + Max-Age.
        cors["access-control-allow-methods"] = "GET, POST, OPTIONS, DELETE"
        cors["access-control-allow-headers"] = (
            "Authorization, Content-Type, Mcp-Session-Id, X-API-Key"
        )
        cors["access-control-max-age"] = "86400"
        return {"status": 200, "headers": list(cors.items())}

    async def _send_preflight(
        self, response: dict[str, Any], send: Any
    ) -> None:
        """Gửi preflight response qua ASGI send (response.start + body rỗng)."""
        headers_list = [
            (k.encode("ascii"), v.encode("ascii"))
            for k, v in response["headers"]
        ]
        await send(
            {
                "type": "http.response.start",
                "status": response["status"],
                "headers": headers_list,
            }
        )
        await send(
            {
                "type": "http.response.body",
                "body": b"",
                "more_body": False,
            }
        )

    def __getattr__(self, name: str) -> Any:
        """Delegate attr về inner app — uvicorn introspect không vỡ."""
        return getattr(self._app, name)


class _BasicAuthFormShim:
    """ASGI shim convert `Authorization: Basic` header → form `client_id`/`client_secret`.

    Lý do: MCP SDK Python ClientAuthenticator (client_auth.py:55-58) yêu cầu
    `client_id` xuất hiện TRONG FORM BODY — KHÔNG bao giờ đọc từ Authorization
    Basic header. Nhưng MCP TS SDK `applyBasicAuth` (auth.js:92-98) khi chọn
    method `client_secret_basic` CHỈ set Authorization header, KHÔNG add
    `client_id` vào form. Mismatch → server fail 401 "Missing client_id".

    Server đã bỏ quảng cáo `client_secret_basic` ở metadata để client mới
    fallback sang post. Shim này là defense-in-depth: cover client còn cache
    metadata cũ (trước fix), hoặc client hard-code chọn basic ngoài luồng
    metadata. Bridge gap để OAuth flow hoạt động với MỌI client tuân thủ
    RFC 6749 §2.3.1 (chấp nhận credentials qua HEADER hoặc BODY).

    Pass-through (KHÔNG can thiệp):
    - Scope khác `http` (lifespan, websocket).
    - Method != POST.
    - Path không thuộc `_BASIC_AUTH_SHIM_PATHS`.
    - Không có Authorization Basic header.
    - Content-Type không phải form-urlencoded.
    - Form body đã có `client_id` (client_secret_post bình thường).
    - Basic header malformed (decode fail) → forward nguyên (SDK xử lý lỗi).

    Inject:
    - Nếu form thiếu `client_id` → thêm từ Basic (URL-decoded per RFC 6749 §2.3.1).
    - Nếu form thiếu `client_secret` → thêm từ Basic (URL-decoded).
    - Đè Content-Length header (kích thước body đã đổi).

    Bảo mật: KHÔNG log nội dung body / header Authorization / client_secret.
    Decode Basic bọc try/except chống malformed input → forward as-is khi fail.

    Delegate attr qua `__getattr__` giống `_AsgiPathShim` để uvicorn introspect
    không vỡ.
    """

    def __init__(self, app: Any) -> None:
        self._app = app

    async def __call__(  # noqa: C901 — nhiều nhánh fast-fail pass-through tường minh
        self, scope: Any, receive: Any, send: Any
    ) -> None:
        if scope.get("type") != "http":
            await self._app(scope, receive, send)
            return

        method = scope.get("method", "").upper()
        path = scope.get("path", "")
        if method != "POST" or path not in _BASIC_AUTH_SHIM_PATHS:
            await self._app(scope, receive, send)
            return

        # Trích Authorization + Content-Type từ scope headers.
        auth_header: str | None = None
        content_type = b""
        for name, value in scope.get("headers", []):
            lname = name.lower() if isinstance(name, bytes) else name.lower().encode()
            if lname == b"authorization":
                auth_header = (
                    value if isinstance(value, str) else value.decode("latin-1")
                )
            elif lname == b"content-type":
                content_type = (
                    value if isinstance(value, bytes) else value.encode("latin-1")
                )

        if not auth_header or not auth_header.startswith("Basic "):
            await self._app(scope, receive, send)
            return

        # Chỉ rewrite form-urlencoded. JSON body / multipart không phải case
        # OAuth /token + /revoke (RFC 6749 quy form-urlencoded), nhưng phòng vệ.
        if b"application/x-www-form-urlencoded" not in content_type.lower():
            await self._app(scope, receive, send)
            return

        # Buffer toàn bộ request body.
        body_parts: list[bytes] = []
        more_body = True
        while more_body:
            message = await receive()
            mtype = message.get("type")
            if mtype == "http.disconnect":
                # Client cắt — nothing to forward.
                return
            if mtype != "http.request":
                continue
            body_parts.append(message.get("body", b"") or b"")
            more_body = bool(message.get("more_body"))
        body = b"".join(body_parts)

        # Parse form hiện tại. Nếu đã có client_id → forward nguyên (path
        # client_secret_post bình thường, không cần shim).
        from urllib.parse import parse_qsl, unquote, urlencode

        try:
            body_str = body.decode("utf-8")
        except UnicodeDecodeError:
            await self._forward_with_body(scope, body, receive, send)
            return

        pairs = parse_qsl(body_str, keep_blank_values=True)
        keys = {k for k, _ in pairs}
        if "client_id" in keys:
            await self._forward_with_body(scope, body, receive, send)
            return

        # Decode Authorization Basic. Bọc try/except chống malformed.
        import base64
        import binascii

        try:
            encoded = auth_header[6:].strip()
            decoded = base64.b64decode(encoded, validate=True).decode("utf-8")
        except (binascii.Error, ValueError, UnicodeDecodeError):
            await self._forward_with_body(scope, body, receive, send)
            return

        if ":" not in decoded:
            await self._forward_with_body(scope, body, receive, send)
            return

        basic_client_id, basic_client_secret = decoded.split(":", 1)
        # RFC 6749 §2.3.1 — URL-decode mỗi phần (vì colon trong client_id/secret
        # bị percent-encode trước khi base64).
        basic_client_id = unquote(basic_client_id)
        basic_client_secret = unquote(basic_client_secret)
        if not basic_client_id:
            await self._forward_with_body(scope, body, receive, send)
            return

        # Inject client_id (luôn) + client_secret (nếu form thiếu).
        new_pairs = list(pairs)
        new_pairs.append(("client_id", basic_client_id))
        if "client_secret" not in keys:
            new_pairs.append(("client_secret", basic_client_secret))
        new_body = urlencode(new_pairs).encode("utf-8")

        # Rewrite Content-Length — drop old, append new.
        new_headers: list[tuple[bytes, bytes]] = []
        for name, value in scope.get("headers", []):
            name_b = name if isinstance(name, bytes) else name.encode("latin-1")
            value_b = value if isinstance(value, bytes) else value.encode("latin-1")
            if name_b.lower() == b"content-length":
                continue
            new_headers.append((name_b, value_b))
        new_headers.append(
            (b"content-length", str(len(new_body)).encode("latin-1"))
        )

        new_scope = dict(scope)
        new_scope["headers"] = new_headers

        logger.info(
            "BasicAuthFormShim — convert Basic→form cho path=%s (client_id "
            "thiếu trong form)",
            path,
        )
        await self._forward_with_body(new_scope, new_body, receive, send)

    async def _forward_with_body(
        self, scope: Any, body: bytes, receive: Any, send: Any
    ) -> None:
        """Replay buffered body cho inner app. Receive tiếp theo trả empty more_body=False.

        `receive` gốc đã được consume cho việc buffer. Cần wrap thành receive
        mới phát message chứa toàn bộ body, sau đó tiếp tục forward các message
        khác (vd http.disconnect) qua receive gốc.
        """
        sent = False

        async def _receive() -> dict:
            nonlocal sent
            if not sent:
                sent = True
                return {
                    "type": "http.request",
                    "body": body,
                    "more_body": False,
                }
            # Sau khi gửi body, delegate về receive gốc — cho phép app nhận
            # http.disconnect nếu client cắt giữa chừng.
            return await receive()

        await self._app(scope, _receive, send)

    def __getattr__(self, name: str) -> Any:
        # Delegate giống _AsgiPathShim — uvicorn / test introspect không vỡ.
        return getattr(self._app, name)


class _AsgiPathShim:
    """ASGI wrapper rewrite path ở 2 trường hợp trước khi Starlette Router xét.

    (1) `/<prefix>` exact → `/<prefix>/` — chặn 307 redirect (xem comment ở
        `build_asgi_app`).
    (2) `/token`, `/authorize`, `/register`, `/revoke` ở root → `/<prefix>/...`
        — alias cho client bỏ qua metadata discovery (Fix B Phase 8.3).

    Delegate `.routes` / `.router` / `.url_path_for` qua `__getattr__` để code
    bên ngoài (uvicorn host=..., test introspect) thấy giống Starlette wrapper.
    """

    def __init__(self, app: Any, *, prefix: str) -> None:
        self._app = app
        self._prefix = prefix
        self._prefix_with_slash = f"/{prefix}/"
        self._prefix_no_slash = f"/{prefix}"

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        if scope.get("type") == "http":
            path = scope.get("path")
            new_path: str | None = None
            if path == self._prefix_no_slash:
                # (1) exact prefix → add trailing slash để Mount match.
                new_path = self._prefix_with_slash
            elif path in _OAUTH_ROOT_ALIAS_PATHS:
                # (2) OAuth endpoint ở root → forward vào inner qua Mount prefix.
                new_path = f"/{self._prefix}{path}"
            if new_path is not None:
                scope = dict(scope)
                scope["path"] = new_path
                scope["raw_path"] = new_path.encode("utf-8")
        await self._app(scope, receive, send)

    def __getattr__(self, name: str) -> Any:
        # Delegate truy cập attr không có sẵn về Starlette wrapper (vd `.routes`,
        # `.router`, `.url_path_for`) — giữ tương thích test/inspect hiện hữu.
        return getattr(self._app, name)


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
