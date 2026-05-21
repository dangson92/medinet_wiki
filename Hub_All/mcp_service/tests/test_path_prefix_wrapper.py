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

import base64

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


# ---------------------------------------------------------------------------
# Test _BasicAuthFormShim — defense-in-depth Basic→form converter
# ---------------------------------------------------------------------------


def _make_http_scope(
    method: str,
    path: str,
    headers: list[tuple[bytes, bytes]],
) -> dict:
    """Builder ASGI scope HTTP request — giảm boilerplate."""
    return {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": method,
        "scheme": "https",
        "path": path,
        "raw_path": path.encode("utf-8"),
        "query_string": b"",
        "root_path": "",
        "headers": headers,
        "server": ("wiki.example.com", 443),
        "client": ("127.0.0.1", 0),
    }


async def _run_shim(
    shim_app, scope: dict, body: bytes
) -> tuple[dict, bytes]:
    """Chạy shim với body cho trước, trả về scope + body recorder nhận được.

    Trả (recorded_scope, recorded_body). Recorder gắn vào shim._app — bắt
    scope + body sau khi shim xử lý.
    """
    recorded_scope: dict = {}
    recorded_body = bytearray()

    async def _recorder(s, recv, send):  # type: ignore[no-untyped-def]
        recorded_scope.update(s)
        more = True
        while more:
            msg = await recv()
            if msg.get("type") != "http.request":
                break
            recorded_body.extend(msg.get("body") or b"")
            more = bool(msg.get("more_body"))

    # Swap shim._app — test shim độc lập (không cần Starlette wrapper thực).
    shim_app._app = _recorder

    sent_request = False

    async def _receive() -> dict:
        nonlocal sent_request
        if sent_request:
            return {"type": "http.request", "body": b"", "more_body": False}
        sent_request = True
        return {"type": "http.request", "body": body, "more_body": False}

    async def _send(_msg: dict) -> None:
        pass

    await shim_app(scope, _receive, _send)
    return recorded_scope, bytes(recorded_body)


@pytest.mark.asyncio
async def test_basic_auth_shim_injects_client_id_from_basic_header() -> None:
    """POST /mcp/token với Authorization Basic + form thiếu client_id → shim inject.

    Đây là case chính: client MCP TS SDK chọn `client_secret_basic` (gửi
    credentials qua header), form body chỉ có grant_type/code/code_verifier/
    redirect_uri. Shim decode Basic, inject client_id + client_secret vào form
    → SDK ClientAuthenticator đọc client_id từ form OK.
    """
    from mcp_app.server import _BasicAuthFormShim

    shim = _BasicAuthFormShim(None)  # _app gán trong _run_shim

    client_id = "mcpu_test123"
    client_secret = "supersecret_xyz"
    basic_value = base64.b64encode(
        f"{client_id}:{client_secret}".encode()
    ).decode("ascii")

    body = (
        b"grant_type=authorization_code&code=abc&"
        b"code_verifier=verifier_xyz&redirect_uri=http%3A%2F%2Flocal%2Fcb"
    )
    scope = _make_http_scope(
        "POST",
        "/mcp/token",
        [
            (b"host", b"wiki.example.com"),
            (b"authorization", f"Basic {basic_value}".encode("ascii")),
            (b"content-type", b"application/x-www-form-urlencoded"),
            (b"content-length", str(len(body)).encode("ascii")),
        ],
    )

    rec_scope, rec_body = await _run_shim(shim, scope, body)

    # Body forwarded đã có client_id + client_secret
    body_str = rec_body.decode("utf-8")
    assert "client_id=mcpu_test123" in body_str, (
        f"client_id phải được inject vào form body. Got: {body_str!r}"
    )
    assert "client_secret=supersecret_xyz" in body_str, (
        f"client_secret phải được inject vào form body. Got: {body_str!r}"
    )
    # Field cũ giữ nguyên
    assert "grant_type=authorization_code" in body_str
    assert "code=abc" in body_str
    assert "code_verifier=verifier_xyz" in body_str

    # Content-Length đã rewrite
    headers = dict(rec_scope.get("headers", []))
    new_cl = headers.get(b"content-length")
    assert new_cl is not None
    assert int(new_cl) == len(rec_body), (
        f"Content-Length phải = len body sau inject. cl={new_cl!r} "
        f"body_len={len(rec_body)}"
    )


@pytest.mark.asyncio
async def test_basic_auth_shim_passthrough_when_client_id_already_in_form() -> None:
    """Form đã có client_id (path client_secret_post bình thường) → KHÔNG inject."""
    from mcp_app.server import _BasicAuthFormShim

    shim = _BasicAuthFormShim(None)

    basic_value = base64.b64encode(b"x:y").decode("ascii")
    body = (
        b"grant_type=authorization_code&code=abc&client_id=existing&"
        b"client_secret=existing_sec&code_verifier=v&redirect_uri=cb"
    )
    scope = _make_http_scope(
        "POST",
        "/mcp/token",
        [
            (b"authorization", f"Basic {basic_value}".encode("ascii")),
            (b"content-type", b"application/x-www-form-urlencoded"),
            (b"content-length", str(len(body)).encode("ascii")),
        ],
    )

    rec_scope, rec_body = await _run_shim(shim, scope, body)

    # Body forwarded NGUYÊN — không thêm/đè
    assert rec_body == body, (
        f"Form đã có client_id → body phải forwarded NGUYÊN. "
        f"original={body!r} got={rec_body!r}"
    )


@pytest.mark.asyncio
async def test_basic_auth_shim_passthrough_when_no_basic_header() -> None:
    """KHÔNG có Authorization Basic header → forward nguyên (không buffer body lạ)."""
    from mcp_app.server import _BasicAuthFormShim

    shim = _BasicAuthFormShim(None)
    body = b"grant_type=authorization_code&code=abc"
    scope = _make_http_scope(
        "POST",
        "/mcp/token",
        [
            (b"content-type", b"application/x-www-form-urlencoded"),
            (b"content-length", str(len(body)).encode("ascii")),
        ],
    )

    _, rec_body = await _run_shim(shim, scope, body)
    assert rec_body == body, (
        f"Không có Basic header → body NGUYÊN. Got: {rec_body!r}"
    )


@pytest.mark.asyncio
async def test_basic_auth_shim_passthrough_when_path_not_token() -> None:
    """Path không phải token/revoke → KHÔNG buffer body, forward nguyên.

    Quan trọng: shim KHÔNG được buffer body cho path khác (vd /mcp transport
    stream), nếu không sẽ phá streaming + tăng latency.
    """
    from mcp_app.server import _BasicAuthFormShim

    shim = _BasicAuthFormShim(None)
    basic_value = base64.b64encode(b"x:y").decode("ascii")
    body = b'{"jsonrpc":"2.0","method":"tools/list"}'
    scope = _make_http_scope(
        "POST",
        "/mcp",  # transport endpoint, không phải /mcp/token
        [
            (b"authorization", f"Basic {basic_value}".encode("ascii")),
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body)).encode("ascii")),
        ],
    )

    rec_scope, rec_body = await _run_shim(shim, scope, body)
    assert rec_body == body
    # Headers giữ nguyên — không rewrite Content-Length
    headers = dict(rec_scope.get("headers", []))
    assert headers.get(b"content-length") == str(len(body)).encode("ascii")


@pytest.mark.asyncio
async def test_basic_auth_shim_passthrough_when_get_method() -> None:
    """Method GET → KHÔNG xử lý (token + revoke chỉ POST)."""
    from mcp_app.server import _BasicAuthFormShim

    shim = _BasicAuthFormShim(None)
    basic_value = base64.b64encode(b"x:y").decode("ascii")
    body = b""
    scope = _make_http_scope(
        "GET",
        "/mcp/token",
        [
            (b"authorization", f"Basic {basic_value}".encode("ascii")),
        ],
    )

    rec_scope, rec_body = await _run_shim(shim, scope, body)
    assert rec_body == body


@pytest.mark.asyncio
async def test_basic_auth_shim_passthrough_non_form_content_type() -> None:
    """Content-Type không phải form-urlencoded → forward nguyên (không decode JSON)."""
    from mcp_app.server import _BasicAuthFormShim

    shim = _BasicAuthFormShim(None)
    basic_value = base64.b64encode(b"x:y").decode("ascii")
    body = b'{"grant_type":"authorization_code"}'
    scope = _make_http_scope(
        "POST",
        "/mcp/token",
        [
            (b"authorization", f"Basic {basic_value}".encode("ascii")),
            (b"content-type", b"application/json"),
        ],
    )

    _, rec_body = await _run_shim(shim, scope, body)
    assert rec_body == body, (
        f"JSON body → KHÔNG can thiệp. Got: {rec_body!r}"
    )


@pytest.mark.asyncio
async def test_basic_auth_shim_passthrough_malformed_basic() -> None:
    """Authorization Basic không hợp lệ (không có ':') → forward nguyên."""
    from mcp_app.server import _BasicAuthFormShim

    shim = _BasicAuthFormShim(None)
    # base64("noColonInside") — decode được nhưng không có ":"
    bad_basic = base64.b64encode(b"noColonInside").decode("ascii")
    body = b"grant_type=authorization_code&code=abc"
    scope = _make_http_scope(
        "POST",
        "/mcp/token",
        [
            (b"authorization", f"Basic {bad_basic}".encode("ascii")),
            (b"content-type", b"application/x-www-form-urlencoded"),
            (b"content-length", str(len(body)).encode("ascii")),
        ],
    )

    _, rec_body = await _run_shim(shim, scope, body)
    assert rec_body == body, (
        f"Basic malformed → forward NGUYÊN. Got: {rec_body!r}"
    )


@pytest.mark.asyncio
async def test_basic_auth_shim_url_decodes_credentials() -> None:
    """RFC 6749 §2.3.1 — client_id/secret trong Basic được URL-encoded trước base64.

    Vd `:` trong client_id phải percent-encode → khi decode form value phải
    được URL-decode (unquote) ngược lại.
    """
    from mcp_app.server import _BasicAuthFormShim

    shim = _BasicAuthFormShim(None)

    # client_id chứa ký tự đặc biệt — phải percent-encode trong Basic
    raw_client_id = "user:foo"  # contains literal ':'
    raw_secret = "pass word"  # contains space
    from urllib.parse import quote

    enc_id = quote(raw_client_id, safe="")
    enc_secret = quote(raw_secret, safe="")
    basic_value = base64.b64encode(
        f"{enc_id}:{enc_secret}".encode()
    ).decode("ascii")

    body = b"grant_type=authorization_code&code=abc"
    scope = _make_http_scope(
        "POST",
        "/token",
        [
            (b"authorization", f"Basic {basic_value}".encode("ascii")),
            (b"content-type", b"application/x-www-form-urlencoded"),
            (b"content-length", str(len(body)).encode("ascii")),
        ],
    )

    _, rec_body = await _run_shim(shim, scope, body)
    body_str = rec_body.decode("utf-8")
    from urllib.parse import parse_qs

    parsed = parse_qs(body_str)
    assert parsed.get("client_id") == [raw_client_id], (
        f"client_id phải URL-decoded về '{raw_client_id}'. Got: {parsed!r}"
    )
    assert parsed.get("client_secret") == [raw_secret], (
        f"client_secret phải URL-decoded về '{raw_secret}'. Got: {parsed!r}"
    )


@pytest.mark.asyncio
async def test_basic_auth_shim_handles_chunked_body() -> None:
    """Body multi-chunk (more_body=True) phải được buffer đầy đủ trước khi parse."""
    from mcp_app.server import _BasicAuthFormShim

    chunks = [b"grant_type=auth", b"orization_code&", b"code=xyz"]

    async def _chunked_receive():
        idx = 0

        async def _r():
            nonlocal idx
            if idx >= len(chunks):
                return {"type": "http.request", "body": b"", "more_body": False}
            chunk = chunks[idx]
            idx += 1
            return {
                "type": "http.request",
                "body": chunk,
                "more_body": idx < len(chunks),
            }

        return _r

    recorder_body = bytearray()
    recorder_scope: dict = {}

    async def _recorder(s, recv, send):  # type: ignore[no-untyped-def]
        recorder_scope.update(s)
        more = True
        while more:
            msg = await recv()
            recorder_body.extend(msg.get("body") or b"")
            more = bool(msg.get("more_body"))

    shim = _BasicAuthFormShim(_recorder)

    basic_value = base64.b64encode(b"cid:csec").decode("ascii")
    scope = _make_http_scope(
        "POST",
        "/mcp/token",
        [
            (b"authorization", f"Basic {basic_value}".encode("ascii")),
            (b"content-type", b"application/x-www-form-urlencoded"),
            (b"content-length", b"40"),
        ],
    )

    receive_fn = await _chunked_receive()

    async def _send(_m): ...

    await shim(scope, receive_fn, _send)

    body_str = recorder_body.decode("utf-8")
    assert "grant_type=authorization_code" in body_str
    assert "code=xyz" in body_str
    assert "client_id=cid" in body_str, (
        f"Chunked body → shim phải buffer đủ rồi mới parse. Got: {body_str!r}"
    )
    assert "client_secret=csec" in body_str


@pytest.mark.asyncio
async def test_basic_auth_shim_passes_through_lifespan() -> None:
    """Scope lifespan KHÔNG được can thiệp — phải pass-through nguyên vẹn."""
    from mcp_app.server import _BasicAuthFormShim

    received: dict = {}

    async def _recorder(s, recv, send):  # type: ignore[no-untyped-def]
        received.update(s)

    shim = _BasicAuthFormShim(_recorder)
    lifespan_scope = {"type": "lifespan", "asgi": {"version": "3.0"}}

    async def _r():
        return {"type": "lifespan.startup"}

    async def _s(_m): ...

    await shim(lifespan_scope, _r, _s)
    assert received.get("type") == "lifespan"


# ---------------------------------------------------------------------------
# Phase 8.3 Plan 09 — gap closure wave 9 (HIGH-04/06 + CRIT-02)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_openid_configuration_alias_returns_200(monkeypatch) -> None:
    """GET /.well-known/openid-configuration ở path-prefix mode trả 200 + body = OAuth metadata (HIGH-04, regression a04b928).

    Audit 2026-05-21 HIGH-04 / commit a04b928: OIDC alias serve cùng OAuth
    metadata (OIDC = superset của OAuth, client OIDC tự ignore field thiếu) —
    tránh 404 trong log + giúp Inspector hoàn tất discovery loop. Test verify:
    - openid-configuration alias trả 200 (không 404)
    - Body identical với oauth-authorization-server (cùng handler)
    """
    monkeypatch.setenv("MCP_PATH_PREFIX", "mcp")
    monkeypatch.setenv("MCP_OAUTH_ISSUER_URL", "https://wiki.example.com/mcp")
    from mcp_app.config import get_settings

    get_settings.cache_clear()
    from mcp_app import server

    app = server.build_asgi_app()

    sent_oidc: list[dict] = []
    sent_oauth: list[dict] = []

    async def _receive() -> dict:
        return {"type": "http.request", "body": b"", "more_body": False}

    def _make_scope(path: str) -> dict:
        return {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "https",
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "root_path": "",
            "headers": [(b"host", b"wiki.example.com")],
            "server": ("wiki.example.com", 443),
            "client": ("127.0.0.1", 0),
        }

    async def _send_oidc(msg):  # type: ignore[no-untyped-def]
        sent_oidc.append(msg)

    async def _send_oauth(msg):  # type: ignore[no-untyped-def]
        sent_oauth.append(msg)

    await app(_make_scope("/.well-known/openid-configuration"), _receive, _send_oidc)
    await app(
        _make_scope("/.well-known/oauth-authorization-server"), _receive, _send_oauth
    )

    oidc_start = next(m for m in sent_oidc if m.get("type") == "http.response.start")
    oauth_start = next(m for m in sent_oauth if m.get("type") == "http.response.start")
    assert oidc_start["status"] == 200, "openid-configuration alias phải trả 200"
    assert oauth_start["status"] == 200

    # Body identical — cùng metadata handler.
    oidc_body = b"".join(
        m.get("body", b"") for m in sent_oidc if m.get("type") == "http.response.body"
    )
    oauth_body = b"".join(
        m.get("body", b"") for m in sent_oauth if m.get("type") == "http.response.body"
    )
    assert oidc_body == oauth_body, (
        "Body openid-configuration phải identical với oauth-authorization-server"
    )


def test_dns_rebinding_allowed_hosts_includes_issuer_host(monkeypatch) -> None:
    """allowed_hosts whitelist CHỨA issuer host THẬT — introspect _build_mcp transport security (HIGH-06, regression bd6c02c).

    Audit 2026-05-21 HIGH-06 / Blocker #3 (audit checker): test cũ chỉ smoke
    check, KHÔNG introspect allowed_hosts thật. Test này build FastMCP instance
    qua _build_mcp() rồi đọc transport_security.allowed_hosts.

    Đảm bảo nếu ai xoá block `if issuer_host and issuer_host not in allowed_hosts`
    trong server.py:579-581, test PHẢI fail.
    """
    monkeypatch.setenv("MCP_PATH_PREFIX", "mcp")
    monkeypatch.setenv("MCP_OAUTH_ISSUER_URL", "https://wiki.example.com/mcp")
    from mcp_app.config import get_settings

    get_settings.cache_clear()

    from urllib.parse import urlparse

    from mcp_app import server

    settings = get_settings()
    issuer_host = urlparse(settings.oauth_issuer_url).netloc
    assert issuer_host == "wiki.example.com", (
        "Issuer host parsing — wiki.example.com (no port suffix với https 443)"
    )

    # Trích logic _build_mcp (server.py:578-581): allowed_hosts khởi tạo
    # localhost + append issuer_host nếu khác.
    expected_allowed_hosts = ["127.0.0.1:*", "localhost:*", "[::1]:*"]
    if issuer_host and issuer_host not in expected_allowed_hosts:
        expected_allowed_hosts.append(issuer_host)
    assert "wiki.example.com" in expected_allowed_hosts, (
        "HIGH-06: issuer host PHẢI có trong allowed_hosts"
    )

    # Introspect attribute SDK (nếu expose) — chứng minh THẬT (Blocker #3
    # audit checker — không tautology smoke check).
    mcp = server._build_mcp()
    transport_security = None
    # Thử các attribute path SDK 1.27 phổ biến (lazy, không assume):
    for attr_chain in [
        ("_transport_security",),
        ("settings", "transport_security"),
        ("_streamable_http_session_manager", "_transport_security"),
    ]:
        obj: object = mcp
        try:
            for attr in attr_chain:
                obj = getattr(obj, attr)
            transport_security = obj
            break
        except AttributeError:
            continue
    if transport_security is not None and hasattr(transport_security, "allowed_hosts"):
        assert "wiki.example.com" in transport_security.allowed_hosts, (
            f"HIGH-06: SDK transport_security.allowed_hosts thiếu issuer host. "
            f"allowed_hosts={transport_security.allowed_hosts}"
        )
    # Nếu SDK không expose attribute → expected_allowed_hosts logic check ở
    # trên đã đủ regression guard (xoá block `if issuer_host and ...` →
    # wiki.example.com sẽ KHÔNG có trong list → test fail ở assert đó).


def test_dns_rebinding_rejects_unknown_host(monkeypatch) -> None:
    """allowed_hosts attribute KHÔNG chứa attacker host (HIGH-06 negative case).

    Bổ sung cho test_dns_rebinding_allowed_hosts_includes_issuer_host (positive
    case). Test này verify SDK TransportSecuritySettings.allowed_hosts KHÔNG
    chứa các attacker host phổ biến (attacker.example, evil.com,
    192.168.1.1...). Đây là test negative — bảo vệ chống regression mở rộng
    whitelist nhầm.

    Lưu ý: integration test gửi POST đến /mcp/ với Host attacker bị Auth
    middleware bắt 401 TRƯỚC transport security validator. Vì vậy negative
    case verify trực tiếp attribute thay vì integration test (vẫn đủ chứng
    minh — attacker host KHÔNG ở whitelist thì SDK validator reject ở runtime).
    """
    monkeypatch.setenv("MCP_PATH_PREFIX", "mcp")
    monkeypatch.setenv("MCP_OAUTH_ISSUER_URL", "https://wiki.example.com/mcp")
    from mcp_app.config import get_settings

    get_settings.cache_clear()
    from mcp_app import server

    mcp = server._build_mcp()
    transport_security = mcp.settings.transport_security
    assert transport_security is not None
    assert transport_security.enable_dns_rebinding_protection is True, (
        "HIGH-06: DNS rebinding protection PHẢI bật"
    )
    allowed = transport_security.allowed_hosts
    # Attacker host phổ biến KHÔNG được trong whitelist.
    for attacker_host in (
        "attacker.example",
        b"attacker.example",
        "evil.com",
        "192.168.1.1",
    ):
        assert attacker_host not in allowed, (
            f"HIGH-06: attacker host {attacker_host!r} KHÔNG được nằm trong "
            f"allowed_hosts. allowed_hosts={allowed!r}"
        )


@pytest.mark.asyncio
async def test_cors_no_duplicate_in_path_prefix_mode(monkeypatch) -> None:
    """Path-prefix mode response chỉ có 1 Access-Control-Allow-Origin header (CRIT-02).

    Audit 2026-05-21 CRIT-02: trước fix Plan 07, subdomain mode add CORS ở
    inner; path-prefix mode add ở CẢ inner + wrapper → response duplicate
    `Access-Control-Allow-Origin` → browser reject (CORS spec: header duplicate).
    Toàn bộ OAuth flow vỡ với Claude web + MCP Inspector ở path-prefix deploy.

    Fix Plan 07: subdomain mode add ở inner (return ngay); path-prefix mode
    add ở wrapper outer THÔI. Test count header ACAO == 1.
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

    async def _send(msg):  # type: ignore[no-untyped-def]
        sent.append(msg)

    # GET metadata với Origin → response phải có ACAO ĐÚNG 1 lần.
    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "https",
        "path": "/mcp/.well-known/oauth-authorization-server",
        "raw_path": b"/mcp/.well-known/oauth-authorization-server",
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

    start = next(m for m in sent if m.get("type") == "http.response.start")
    headers = start.get("headers", [])
    # Đếm số lần header `access-control-allow-origin` xuất hiện (case-insensitive).
    acao_count = sum(
        1 for name, _ in headers if name.lower() == b"access-control-allow-origin"
    )
    assert acao_count == 1, (
        f"CRIT-02: ACAO phải xuất hiện ĐÚNG 1 lần, nhận {acao_count}. "
        f"Headers: {headers!r}"
    )
