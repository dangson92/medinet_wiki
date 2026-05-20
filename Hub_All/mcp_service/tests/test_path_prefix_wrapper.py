"""Test build_asgi_app cho path-prefix deploy (Phase 8.3 add-on).

Khi MCP_PATH_PREFIX non-empty (vd `mcp`), build_asgi_app trả Starlette
wrapper:
- 2 route metadata RFC 8414/9728 ở root với path suffix `/<prefix>`.
- Mount inner FastMCP app dưới `/<prefix>` (transport + OAuth + login).

Khi rỗng, build_asgi_app trả inner trực tiếp (subdomain/authority-root
deploy — behavior gốc Phase 8.3).

Test cover routing structure, KHÔNG cover end-to-end OAuth flow (đã có
test khác cho flow).
"""
from __future__ import annotations

import pytest
from starlette.routing import Mount, Route


@pytest.fixture(autouse=True)
def _reset_singletons():
    """Reset module-level singletons để mỗi test build app sạch."""
    from mcp_app import server

    server._api_client = None
    server._oauth_store = None
    server._oauth_provider = None
    yield
    server._api_client = None
    server._oauth_store = None
    server._oauth_provider = None


def test_path_prefix_empty_returns_inner_directly(monkeypatch) -> None:
    """`MCP_PATH_PREFIX=""` → trả inner Starlette app (subdomain deploy)."""
    monkeypatch.setenv("MCP_PATH_PREFIX", "")
    monkeypatch.setenv("MCP_OAUTH_ISSUER_URL", "http://localhost:8190")
    from mcp_app.config import get_settings

    get_settings.cache_clear()

    from mcp_app import server

    app = server.build_asgi_app()

    # Inner app có route `/mcp` (transport mặc định) + OAuth routes.
    paths = [getattr(r, "path", None) for r in app.routes]
    assert "/mcp" in paths
    # KHÔNG có metadata path-suffixed (subdomain mode).
    assert "/.well-known/oauth-authorization-server" in paths or any(
        "oauth-authorization-server" in str(p) for p in paths
    )


def test_path_prefix_wraps_with_mount_and_metadata_routes(monkeypatch) -> None:
    """`MCP_PATH_PREFIX=mcp` + issuer .../mcp → wrapper với 2 metadata route + Mount."""
    monkeypatch.setenv("MCP_PATH_PREFIX", "mcp")
    monkeypatch.setenv("MCP_OAUTH_ISSUER_URL", "https://wiki.example.com/mcp")
    from mcp_app.config import get_settings

    get_settings.cache_clear()

    from mcp_app import server

    app = server.build_asgi_app()

    # Wrapper là Starlette mới, có 3 route ở top level:
    # 1) /.well-known/oauth-authorization-server/mcp (AS metadata RFC 8414)
    # 2) /.well-known/oauth-protected-resource/mcp   (PR metadata RFC 9728)
    # 3) Mount("/mcp", inner)
    route_specs = []
    for r in app.routes:
        if isinstance(r, Mount):
            route_specs.append(("Mount", r.path))
        elif isinstance(r, Route):
            route_specs.append(("Route", r.path))

    assert ("Route", "/.well-known/oauth-authorization-server/mcp") in route_specs
    assert ("Route", "/.well-known/oauth-protected-resource/mcp") in route_specs
    assert ("Mount", "/mcp") in route_specs


def test_path_prefix_strips_slashes(monkeypatch) -> None:
    """`MCP_PATH_PREFIX=/mcp/` strip về `mcp` (idempotent)."""
    monkeypatch.setenv("MCP_PATH_PREFIX", "/mcp/")
    monkeypatch.setenv("MCP_OAUTH_ISSUER_URL", "https://wiki.example.com/mcp")
    from mcp_app.config import get_settings

    get_settings.cache_clear()

    from mcp_app import server

    app = server.build_asgi_app()

    mount_paths = [r.path for r in app.routes if isinstance(r, Mount)]
    assert "/mcp" in mount_paths


@pytest.mark.asyncio
async def test_path_prefix_no_307_on_exact_match(monkeypatch) -> None:
    """`GET /mcp` (exact, KHÔNG trailing slash) KHÔNG trả 307 redirect.

    Regression Phase 8.3 add-on: Starlette `Mount('/mcp')` compile regex
    `^/mcp/(?P<path>.*)$` — KHÔNG match exact `/mcp`. Router với
    `redirect_slashes=True` (mặc định) phát 307 → `/mcp/`. MCP client
    (Claude web) gửi POST kèm `Authorization: Bearer …`; nhiều HTTP runtime
    drop Authorization khi follow 307 → 401 ngẫu nhiên + session lệch.

    Shim `_AsgiPathShim` rewrite scope.path SỚM trước Router → Mount khớp
    trực tiếp, không 307 emitted. Test này gọi shim với ASGI scope giả lập
    + ghi nhận message gửi qua `send` — assert KHÔNG có
    `http.response.start` với status 307.
    """
    monkeypatch.setenv("MCP_PATH_PREFIX", "mcp")
    monkeypatch.setenv("MCP_OAUTH_ISSUER_URL", "https://wiki.example.com/mcp")
    from mcp_app.config import get_settings

    get_settings.cache_clear()

    from mcp_app import server

    app = server.build_asgi_app()

    # Ghi nhận message ASGI app emit. Quan tâm `http.response.start` đầu tiên.
    sent: list[dict] = []

    async def _receive() -> dict:
        # Trả body rỗng — chỉ cần đủ để app emit response start. Không cần
        # full request lifecycle (test này chỉ assert status code đầu tiên).
        return {"type": "http.request", "body": b"", "more_body": False}

    async def _send(message: dict) -> None:
        sent.append(message)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "https",
        "path": "/mcp",  # ← exact, không trailing slash — case gây 307
        "raw_path": b"/mcp",
        "query_string": b"",
        "root_path": "",
        "headers": [(b"host", b"wiki.example.com")],
        "server": ("wiki.example.com", 443),
        "client": ("127.0.0.1", 0),
    }

    await app(scope, _receive, _send)

    # Tìm response start đầu tiên (có thể có vài http.response.body theo sau).
    starts = [m for m in sent if m.get("type") == "http.response.start"]
    assert starts, f"App KHÔNG emit http.response.start nào — messages={sent!r}"
    assert starts[0]["status"] != 307, (
        f"Regression: app phát 307 redirect trên /mcp exact. "
        f"Headers={dict(starts[0].get('headers', []))!r}. Shim phải rewrite "
        f"scope.path='/mcp/' trước Router để Mount khớp trực tiếp."
    )


@pytest.mark.asyncio
async def test_path_prefix_shim_passes_through_other_paths(monkeypatch) -> None:
    """Shim CHỈ rewrite exact `/<prefix>` — các path khác (well-known, /<prefix>/...) giữ nguyên.

    Đảm bảo shim không over-reach: `/mcp/authorize`, `/mcp/`, `/.well-known/...`
    đều phải pass-through scope.path KHÔNG đổi. Verify bằng cách inject app
    giả ghi nhận scope nhận được, rồi gọi shim với từng path mẫu.
    """
    monkeypatch.setenv("MCP_PATH_PREFIX", "mcp")
    monkeypatch.setenv("MCP_OAUTH_ISSUER_URL", "https://wiki.example.com/mcp")
    from mcp_app.config import get_settings

    get_settings.cache_clear()

    from mcp_app import server

    # Build app rồi thay underlying wrapper bằng recorder để cô lập shim.
    app = server.build_asgi_app()
    recorded_paths: list[str] = []

    async def _recorder(scope, receive, send):  # type: ignore[no-untyped-def]
        recorded_paths.append(scope.get("path", ""))

    # `app` là _AsgiPathShim — swap `_app` private để test shim độc lập.
    app._app = _recorder  # type: ignore[attr-defined]

    async def _noop_receive() -> dict:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def _noop_send(msg: dict) -> None:
        pass

    cases = [
        # (1) exact prefix rewrite (chặn 307)
        ("/mcp", "/mcp/"),                      # ← rewrite
        ("/mcp/", "/mcp/"),                     # already slash — không đổi
        ("/mcp/authorize", "/mcp/authorize"),   # sub-path — không đổi
        # (2) OAuth root alias (Fix B) — rewrite về /<prefix>/...
        ("/token", "/mcp/token"),
        ("/authorize", "/mcp/authorize"),
        ("/register", "/mcp/register"),
        ("/revoke", "/mcp/revoke"),
        # Path lân cận KHÔNG được alias (false-positive guard):
        ("/tokens", "/tokens"),                 # ≠ /token exact
        ("/authorize-x", "/authorize-x"),
        # Path khác giữ nguyên:
        ("/.well-known/oauth-authorization-server", "/.well-known/oauth-authorization-server"),
        ("/.well-known/oauth-authorization-server/mcp", "/.well-known/oauth-authorization-server/mcp"),
        ("/login", "/login"),                   # OAuth login form route
    ]
    for input_path, expected in cases:
        recorded_paths.clear()
        await app(
            {
                "type": "http",
                "method": "GET",
                "path": input_path,
                "raw_path": input_path.encode("utf-8"),
                "headers": [],
            },
            _noop_receive,
            _noop_send,
        )
        assert recorded_paths == [expected], (
            f"Path '{input_path}' phải pass-through thành '{expected}', "
            f"nhận được {recorded_paths!r}"
        )


@pytest.mark.asyncio
async def test_path_prefix_shim_passes_through_lifespan(monkeypatch) -> None:
    """Shim KHÔNG đụng scope `lifespan` — uvicorn startup/shutdown phải xuyên suốt.

    Lifespan scope không có 'path'; shim chỉ branch khi `type=='http'`. Nếu
    branch nhầm, lifespan event mất → session manager SDK không khởi tạo →
    transport 500. Test cô lập shim với lifespan scope giả.
    """
    monkeypatch.setenv("MCP_PATH_PREFIX", "mcp")
    monkeypatch.setenv("MCP_OAUTH_ISSUER_URL", "https://wiki.example.com/mcp")
    from mcp_app.config import get_settings

    get_settings.cache_clear()

    from mcp_app import server

    app = server.build_asgi_app()
    received_scope: dict = {}

    async def _recorder(scope, receive, send):  # type: ignore[no-untyped-def]
        received_scope.update(scope)

    app._app = _recorder  # type: ignore[attr-defined]

    lifespan_scope = {"type": "lifespan", "asgi": {"version": "3.0"}}

    async def _r() -> dict:
        return {"type": "lifespan.startup"}

    async def _s(msg: dict) -> None:
        pass

    await app(lifespan_scope, _r, _s)
    assert received_scope.get("type") == "lifespan", (
        "Shim phải pass-through lifespan scope nguyên vẹn — nếu can thiệp "
        f"sẽ làm session manager SDK không khởi tạo. Nhận: {received_scope!r}"
    )


@pytest.mark.asyncio
async def test_cors_preflight_metadata_endpoint(monkeypatch) -> None:
    """OPTIONS preflight tới `/.well-known/oauth-authorization-server` trả CORS headers.

    Regression Phase 8.3 add-on: MCP Inspector (localhost:6274) fetch metadata
    cross-origin. Thiếu `Access-Control-Allow-Origin` → browser block → Inspector
    fallback default endpoint root → POST /token 404. Test giả lập preflight
    CORS request + assert response có `access-control-allow-origin: *` +
    `access-control-allow-methods` cover GET/POST/OPTIONS.
    """
    monkeypatch.setenv("MCP_PATH_PREFIX", "mcp")
    monkeypatch.setenv("MCP_OAUTH_ISSUER_URL", "https://wiki.example.com/mcp")
    from mcp_app.config import get_settings

    get_settings.cache_clear()

    from mcp_app import server

    app = server.build_asgi_app()

    sent: list[dict] = []

    async def _receive() -> dict:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def _send(message: dict) -> None:
        sent.append(message)

    # CORS preflight: OPTIONS + Origin + Access-Control-Request-Method
    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": "OPTIONS",
        "scheme": "https",
        "path": "/.well-known/oauth-authorization-server",
        "raw_path": b"/.well-known/oauth-authorization-server",
        "query_string": b"",
        "root_path": "",
        "headers": [
            (b"host", b"wiki.example.com"),
            (b"origin", b"http://localhost:6274"),
            (b"access-control-request-method", b"GET"),
            (b"access-control-request-headers", b"authorization"),
        ],
        "server": ("wiki.example.com", 443),
        "client": ("127.0.0.1", 0),
    }

    await app(scope, _receive, _send)

    starts = [m for m in sent if m.get("type") == "http.response.start"]
    assert starts, f"App KHÔNG emit response — messages={sent!r}"
    # CORSMiddleware trả 200 cho preflight hợp lệ.
    assert starts[0]["status"] == 200, (
        f"Preflight phải trả 200, nhận {starts[0]['status']}"
    )
    headers = {k.decode().lower(): v.decode() for k, v in starts[0].get("headers", [])}
    assert headers.get("access-control-allow-origin") == "*", (
        f"Thiếu Access-Control-Allow-Origin — headers={headers!r}"
    )
    allow_methods = headers.get("access-control-allow-methods", "")
    # `allow_methods=*` — Starlette CORSMiddleware echo lại method client request.
    assert "GET" in allow_methods or "*" in allow_methods, (
        f"Access-Control-Allow-Methods phải include GET — got {allow_methods!r}"
    )


@pytest.mark.asyncio
async def test_cors_actual_get_metadata(monkeypatch) -> None:
    """GET thật `/.well-known/oauth-authorization-server` có ACAO header.

    Phân biệt với preflight: GET thật trả body metadata, KHÔNG phải 200 rỗng.
    Browser kiểm `Access-Control-Allow-Origin` trên response thật trước khi
    expose body cho JS. Assert header tồn tại trên response GET 200.
    """
    monkeypatch.setenv("MCP_PATH_PREFIX", "mcp")
    monkeypatch.setenv("MCP_OAUTH_ISSUER_URL", "https://wiki.example.com/mcp")
    from mcp_app.config import get_settings

    get_settings.cache_clear()

    from mcp_app import server

    app = server.build_asgi_app()

    sent: list[dict] = []

    async def _receive() -> dict:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def _send(message: dict) -> None:
        sent.append(message)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "https",
        "path": "/.well-known/oauth-authorization-server",
        "raw_path": b"/.well-known/oauth-authorization-server",
        "query_string": b"",
        "root_path": "",
        "headers": [
            (b"host", b"wiki.example.com"),
            (b"origin", b"http://localhost:6274"),
        ],
        "server": ("wiki.example.com", 443),
        "client": ("127.0.0.1", 0),
    }

    await app(scope, _receive, _send)

    starts = [m for m in sent if m.get("type") == "http.response.start"]
    assert starts, f"App KHÔNG emit response — messages={sent!r}"
    assert starts[0]["status"] == 200, (
        f"GET metadata phải 200, nhận {starts[0]['status']}"
    )
    headers = {k.decode().lower(): v.decode() for k, v in starts[0].get("headers", [])}
    assert headers.get("access-control-allow-origin") == "*", (
        f"GET thật cũng phải có Access-Control-Allow-Origin — headers={headers!r}"
    )


@pytest.mark.asyncio
async def test_metadata_advertises_only_client_secret_post(monkeypatch) -> None:
    """Metadata CHỈ quảng cáo `client_secret_post`, KHÔNG có `client_secret_basic`.

    Regression: MCP SDK Python ClientAuthenticator (client_auth.py) yêu cầu
    `client_id` trong FORM BODY — KHÔNG đọc từ Authorization Basic header.
    Server thực chất chỉ support `client_secret_post`. Nếu metadata vẫn
    quảng cáo `client_secret_basic`, MCP TS SDK chọn basic cho client
    không có hint `token_endpoint_auth_method` (vd MCP Inspector user nhập
    tay credentials) → gửi credential qua header, form body trống → 401
    "Missing client_id".

    Áp dụng cho cả token + revocation endpoint (revoke handler dùng cùng
    ClientAuthenticator).
    """
    import json

    monkeypatch.setenv("MCP_PATH_PREFIX", "mcp")
    monkeypatch.setenv("MCP_OAUTH_ISSUER_URL", "https://wiki.example.com/mcp")
    from mcp_app.config import get_settings

    get_settings.cache_clear()

    from mcp_app import server

    app = server.build_asgi_app()

    sent: list[dict] = []
    body_chunks: list[bytes] = []

    async def _receive() -> dict:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def _send(message: dict) -> None:
        sent.append(message)
        if message.get("type") == "http.response.body":
            body_chunks.append(message.get("body") or b"")

    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "https",
        "path": "/.well-known/oauth-authorization-server",
        "raw_path": b"/.well-known/oauth-authorization-server",
        "query_string": b"",
        "root_path": "",
        "headers": [(b"host", b"wiki.example.com")],
        "server": ("wiki.example.com", 443),
        "client": ("127.0.0.1", 0),
    }

    await app(scope, _receive, _send)

    starts = [m for m in sent if m.get("type") == "http.response.start"]
    assert starts and starts[0]["status"] == 200, (
        f"GET metadata phải 200, nhận {starts!r}"
    )
    body = b"".join(body_chunks).decode("utf-8")
    metadata = json.loads(body)
    assert metadata.get("token_endpoint_auth_methods_supported") == [
        "client_secret_post"
    ], (
        f"token_endpoint_auth_methods_supported phải CHỈ ['client_secret_post'] "
        f"— nếu có basic, MCP TS SDK ưu tiên basic → 'Missing client_id'. "
        f"Got: {metadata.get('token_endpoint_auth_methods_supported')!r}"
    )
    assert metadata.get("revocation_endpoint_auth_methods_supported") == [
        "client_secret_post"
    ], (
        f"revocation_endpoint_auth_methods_supported phải CHỈ "
        f"['client_secret_post']. Got: "
        f"{metadata.get('revocation_endpoint_auth_methods_supported')!r}"
    )
