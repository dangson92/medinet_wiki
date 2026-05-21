"""Test CRIT-01 (audit 2026-05-21) — tách 2 CORS policy theo path.

Plan 10-04: thay 1 hàm `_add_cors_middleware` (allow_origins=["*"] cho mọi
route) bằng `_MultiPolicyCORSMiddleware` ASGI wrapper tách 2 policy:

1. **Metadata** (`/.well-known/oauth-authorization-server[+suffix]`,
   `/.well-known/oauth-protected-resource[+suffix]`,
   `/.well-known/openid-configuration`) → `Access-Control-Allow-Origin: *`
   (RFC 8414 §3.1 / RFC 9728 §3.1 cho phép wildcard cho metadata public).

2. **Sensitive** (`/token`, `/authorize`, `/revoke`, `/register`,
   transport `/mcp` + `/mcp/*`) → ACAO chỉ echo lại nếu Origin nằm trong
   whitelist `settings.mcp_oauth_sensitive_allowed_origins` (default:
   claude.ai + inspector.modelcontextprotocol.io + localhost:6274 +
   127.0.0.1:6274).

6 case cover cả 2 mode deploy (subdomain + path-prefix):
- Test 1: metadata wildcard (subdomain) — Origin lạ → ACAO `*`.
- Test 2: metadata wildcard (path-prefix /mcp suffix) — Origin lạ → ACAO `*`.
- Test 3: sensitive whitelist allowed — Origin claude.ai → ACAO echo.
- Test 4: sensitive whitelist rejected — Origin evil.com → KHÔNG có ACAO.
- Test 5: path-prefix /mcp/token whitelist allowed — Origin claude.ai → ACAO echo.
- Test 6: transport /mcp whitelist allowed — Origin localhost:6274 → ACAO echo.
"""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _reset_singletons() -> None:
    """Reset module-level singletons để mỗi test build app sạch."""
    from mcp_app import server

    server._api_client = None
    server._oauth_store = None
    server._oauth_provider = None
    yield
    server._api_client = None
    server._oauth_store = None
    server._oauth_provider = None


def _make_http_scope(
    method: str,
    path: str,
    headers: list[tuple[bytes, bytes]],
) -> dict:
    """Builder ASGI scope HTTP request — chuẩn pattern test_path_prefix_wrapper."""
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


async def _run_app(app, scope: dict) -> list[dict]:
    """Chạy ASGI app với scope cho trước — trả về list message gửi qua send."""
    sent: list[dict] = []

    async def _receive() -> dict:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def _send(msg: dict) -> None:
        sent.append(msg)

    await app(scope, _receive, _send)
    return sent


def _headers_dict(start_msg: dict) -> dict[str, str]:
    """Convert ASGI response.start headers list → dict lower-case."""
    return {
        (k.decode("ascii") if isinstance(k, bytes) else k).lower():
        (v.decode("ascii") if isinstance(v, bytes) else v)
        for k, v in start_msg.get("headers", [])
    }


@pytest.mark.asyncio
async def test_metadata_wildcard_subdomain_mode(monkeypatch) -> None:
    """Test 1: subdomain mode + GET /.well-known/oauth-authorization-server.

    Origin malicious bất kỳ → response 200 + Access-Control-Allow-Origin: *
    (RFC 8414 §3.1 — metadata public KHÔNG cần credential, wildcard hợp lệ).
    """
    monkeypatch.setenv("MCP_PATH_PREFIX", "")
    monkeypatch.setenv("MCP_OAUTH_ISSUER_URL", "http://localhost:8190")
    from mcp_app.config import get_settings

    get_settings.cache_clear()
    from mcp_app import server

    app = server.build_asgi_app()
    scope = _make_http_scope(
        "GET",
        "/.well-known/oauth-authorization-server",
        [
            (b"host", b"localhost:8190"),
            (b"origin", b"https://random-attacker.com"),
        ],
    )
    sent = await _run_app(app, scope)
    starts = [m for m in sent if m.get("type") == "http.response.start"]
    assert starts, f"App KHÔNG emit response.start — messages={sent!r}"
    assert starts[0]["status"] == 200
    headers = _headers_dict(starts[0])
    assert headers.get("access-control-allow-origin") == "*", (
        f"Metadata endpoint phải trả ACAO * cho mọi origin (RFC 8414 §3.1). "
        f"Headers: {headers!r}"
    )


@pytest.mark.asyncio
async def test_metadata_wildcard_path_prefix_mode(monkeypatch) -> None:
    """Test 2: path-prefix mode + GET /.well-known/oauth-authorization-server/mcp.

    Origin malicious → ACAO `*` (RFC 8414 §3.1 áp dụng cho mọi metadata path
    bất kể suffix path component của issuer).
    """
    monkeypatch.setenv("MCP_PATH_PREFIX", "mcp")
    monkeypatch.setenv("MCP_OAUTH_ISSUER_URL", "https://wiki.example.com/mcp")
    from mcp_app.config import get_settings

    get_settings.cache_clear()
    from mcp_app import server

    app = server.build_asgi_app()
    scope = _make_http_scope(
        "GET",
        "/.well-known/oauth-authorization-server/mcp",
        [
            (b"host", b"wiki.example.com"),
            (b"origin", b"https://evil.attacker.com"),
        ],
    )
    sent = await _run_app(app, scope)
    starts = [m for m in sent if m.get("type") == "http.response.start"]
    assert starts and starts[0]["status"] == 200, (
        f"Path-prefix metadata phải 200, nhận {starts!r}"
    )
    headers = _headers_dict(starts[0])
    assert headers.get("access-control-allow-origin") == "*", (
        f"Metadata path-prefix mode phải trả ACAO * cho mọi origin. "
        f"Headers: {headers!r}"
    )


@pytest.mark.asyncio
async def test_sensitive_whitelist_allowed_origin_token(monkeypatch) -> None:
    """Test 3: OPTIONS /token (subdomain) với Origin claude.ai → ACAO echo.

    Sensitive endpoint chỉ echo ACAO khi Origin nằm trong whitelist
    `mcp_oauth_sensitive_allowed_origins`. KHÔNG wildcard (CRIT-01 fix).
    """
    monkeypatch.setenv("MCP_PATH_PREFIX", "")
    monkeypatch.setenv("MCP_OAUTH_ISSUER_URL", "http://localhost:8190")
    from mcp_app.config import get_settings

    get_settings.cache_clear()
    from mcp_app import server

    app = server.build_asgi_app()
    scope = _make_http_scope(
        "OPTIONS",
        "/token",
        [
            (b"host", b"localhost:8190"),
            (b"origin", b"https://claude.ai"),
            (b"access-control-request-method", b"POST"),
            (b"access-control-request-headers", b"authorization, content-type"),
        ],
    )
    sent = await _run_app(app, scope)
    starts = [m for m in sent if m.get("type") == "http.response.start"]
    assert starts, f"Preflight phải emit response.start — sent={sent!r}"
    assert starts[0]["status"] == 200, (
        f"Preflight whitelist origin phải trả 200, nhận {starts[0]['status']}. "
        f"Sent: {sent!r}"
    )
    headers = _headers_dict(starts[0])
    assert headers.get("access-control-allow-origin") == "https://claude.ai", (
        f"Sensitive endpoint phải echo origin claude.ai (KHÔNG wildcard). "
        f"Headers: {headers!r}"
    )


@pytest.mark.asyncio
async def test_sensitive_whitelist_rejected_origin(monkeypatch) -> None:
    """Test 4: OPTIONS /token với Origin evil.com → KHÔNG có ACAO header.

    Origin không match whitelist → middleware KHÔNG inject ACAO →
    browser block (CORS spec: response thiếu ACAO → request blocked).
    """
    monkeypatch.setenv("MCP_PATH_PREFIX", "")
    monkeypatch.setenv("MCP_OAUTH_ISSUER_URL", "http://localhost:8190")
    from mcp_app.config import get_settings

    get_settings.cache_clear()
    from mcp_app import server

    app = server.build_asgi_app()
    scope = _make_http_scope(
        "OPTIONS",
        "/token",
        [
            (b"host", b"localhost:8190"),
            (b"origin", b"https://evil.attacker.com"),
            (b"access-control-request-method", b"POST"),
        ],
    )
    sent = await _run_app(app, scope)
    starts = [m for m in sent if m.get("type") == "http.response.start"]
    assert starts, f"Phải có response.start — sent={sent!r}"
    headers = _headers_dict(starts[0])
    # KHÔNG có ACAO header → browser block CORS.
    # CRIT-01 fix: sensitive endpoint KHÔNG echo origin nếu không match whitelist.
    assert "access-control-allow-origin" not in headers, (
        f"CRIT-01: sensitive endpoint KHÔNG được trả ACAO cho origin lạ "
        f"(evil.attacker.com). Headers: {headers!r}"
    )


@pytest.mark.asyncio
async def test_sensitive_whitelist_path_prefix_mcp_token(monkeypatch) -> None:
    """Test 5: path-prefix mode + OPTIONS /mcp/token với Origin claude.ai → ACAO echo.

    Sensitive endpoint cover cả path-prefix variant /mcp/token (CRIT-01 fix
    áp dụng đồng nhất 2 mode deploy).
    """
    monkeypatch.setenv("MCP_PATH_PREFIX", "mcp")
    monkeypatch.setenv("MCP_OAUTH_ISSUER_URL", "https://wiki.example.com/mcp")
    from mcp_app.config import get_settings

    get_settings.cache_clear()
    from mcp_app import server

    app = server.build_asgi_app()
    scope = _make_http_scope(
        "OPTIONS",
        "/mcp/token",
        [
            (b"host", b"wiki.example.com"),
            (b"origin", b"https://claude.ai"),
            (b"access-control-request-method", b"POST"),
            (b"access-control-request-headers", b"authorization, content-type"),
        ],
    )
    sent = await _run_app(app, scope)
    starts = [m for m in sent if m.get("type") == "http.response.start"]
    assert starts and starts[0]["status"] == 200, (
        f"Preflight path-prefix /mcp/token phải 200, nhận {starts!r}"
    )
    headers = _headers_dict(starts[0])
    assert headers.get("access-control-allow-origin") == "https://claude.ai", (
        f"Path-prefix /mcp/token whitelist allowed phải echo claude.ai. "
        f"Headers: {headers!r}"
    )


@pytest.mark.asyncio
async def test_sensitive_whitelist_transport_mcp(monkeypatch) -> None:
    """Test 6: OPTIONS /mcp transport (subdomain) với Origin localhost:6274 → ACAO echo.

    Transport endpoint /mcp + /mcp/* được phân loại sensitive (MCP Inspector
    + Claude Desktop dùng để tools/list, tools/call) — whitelist cover dev
    Inspector port 6274.
    """
    monkeypatch.setenv("MCP_PATH_PREFIX", "")
    monkeypatch.setenv("MCP_OAUTH_ISSUER_URL", "http://localhost:8190")
    from mcp_app.config import get_settings

    get_settings.cache_clear()
    from mcp_app import server

    app = server.build_asgi_app()
    scope = _make_http_scope(
        "OPTIONS",
        "/mcp",
        [
            (b"host", b"localhost:8190"),
            (b"origin", b"http://localhost:6274"),
            (b"access-control-request-method", b"POST"),
            (b"access-control-request-headers", b"authorization, mcp-session-id"),
        ],
    )
    sent = await _run_app(app, scope)
    starts = [m for m in sent if m.get("type") == "http.response.start"]
    assert starts and starts[0]["status"] == 200, (
        f"Preflight /mcp transport whitelist allowed phải 200, nhận {starts!r}"
    )
    headers = _headers_dict(starts[0])
    assert headers.get("access-control-allow-origin") == "http://localhost:6274", (
        f"Transport /mcp whitelist allowed Inspector port 6274 phải echo origin. "
        f"Headers: {headers!r}"
    )


# ---------------------------------------------------------------------------
# Setting parse env comma-separated test
# ---------------------------------------------------------------------------


def test_settings_sensitive_origins_default_whitelist() -> None:
    """Setting default chứa 4 origin whitelist: claude.ai + inspector + 2 localhost."""
    import os

    # Đảm bảo env không set (test default thuần).
    os.environ.pop("MCP_OAUTH_SENSITIVE_ALLOWED_ORIGINS", None)
    from mcp_app.config import get_settings

    get_settings.cache_clear()
    settings = get_settings()
    assert hasattr(settings, "mcp_oauth_sensitive_allowed_origins"), (
        "Settings phải có field mcp_oauth_sensitive_allowed_origins (CRIT-01)"
    )
    origins = settings.mcp_oauth_sensitive_allowed_origins
    assert "https://claude.ai" in origins
    assert "https://inspector.modelcontextprotocol.io" in origins
    assert "http://localhost:6274" in origins
    assert "http://127.0.0.1:6274" in origins


def test_settings_sensitive_origins_env_comma_separated(monkeypatch) -> None:
    """Env `MCP_OAUTH_SENSITIVE_ALLOWED_ORIGINS=a,b,c` parse thành list 3 phần tử."""
    monkeypatch.setenv(
        "MCP_OAUTH_SENSITIVE_ALLOWED_ORIGINS",
        "https://a.example.com,https://b.example.com,http://localhost:9999",
    )
    from mcp_app.config import get_settings

    get_settings.cache_clear()
    settings = get_settings()
    origins = settings.mcp_oauth_sensitive_allowed_origins
    assert origins == [
        "https://a.example.com",
        "https://b.example.com",
        "http://localhost:9999",
    ], f"Env comma-separated phải parse thành list 3 phần tử. Got: {origins!r}"
