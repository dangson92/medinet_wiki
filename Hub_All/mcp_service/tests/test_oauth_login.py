"""Test cho oauth/login.py + wiring server.py — Phase 8.3 (MCP-01, D-02).

Phủ behavior:
- test_login_get_renders_form: GET /login?txn=x -> 200 HTML có form + email + password.
- test_login_callback_wrong_credential: POST callback, /api/auth/login 401
  -> 200 HTML lỗi "Sai tài khoản hoặc mật khẩu" (critical).
- test_login_callback_success_redirects: pending seed + /api/auth/login 200
  -> 302 redirect kèm code= + state=.
- test_lifespan_inits_schema: app start qua TestClient -> OAuthStore schema sẵn sàng.
- test_metadata_endpoint: GET /.well-known/oauth-authorization-server -> 200 JSON
  có issuer/authorization_endpoint/token_endpoint/registration_endpoint (critical).
- test_protected_resource_metadata: GET /.well-known/oauth-protected-resource -> 200.
"""
from __future__ import annotations

import json as _json

import httpx
import pytest
import respx
from starlette.testclient import TestClient

_API_BASE_URL = "http://testserver-api"
_ISSUER = "http://localhost:8190"


def _envelope_ok(data: dict) -> dict:
    return {"success": True, "data": data, "error": None, "meta": None}


def _envelope_err(code: str, message: str) -> dict:
    return {
        "success": False,
        "data": None,
        "error": {"code": code, "message": message},
        "meta": None,
    }


@pytest.fixture
def oauth_env(monkeypatch: pytest.MonkeyPatch, tmp_path):
    """Override config OAuth + API base URL, reset singleton server.

    Dùng file SQLite tạm trong tmp_path (không :memory:) để lifespan init_schema
    + handler dùng cùng một DB qua nhiều connection thực tế của test.
    """
    import mcp_app.server as server
    from mcp_app.config import get_settings

    db_path = str(tmp_path / "oauth-state.db")
    monkeypatch.setenv("MCP_API_BASE_URL", _API_BASE_URL)
    monkeypatch.setenv("MCP_OAUTH_ISSUER_URL", _ISSUER)
    monkeypatch.setenv("MCP_OAUTH_STATE_DB_PATH", db_path)
    get_settings.cache_clear()
    server._api_client = None
    server._oauth_store = None
    server._oauth_provider = None
    yield db_path
    get_settings.cache_clear()
    server._api_client = None
    server._oauth_store = None
    server._oauth_provider = None


def test_login_get_renders_form(oauth_env) -> None:
    """GET /login?txn=x -> 200 + HTML chứa form + input email + password."""
    from mcp_app.server import build_asgi_app

    app = build_asgi_app()
    with TestClient(app) as client:
        resp = client.get("/login?txn=txn-abc")
    assert resp.status_code == 200
    body = resp.text
    assert "<form" in body
    assert 'name="email"' in body
    assert 'name="password"' in body
    assert "txn-abc" in body


@pytest.mark.critical
@respx.mock
def test_login_callback_wrong_credential(oauth_env) -> None:
    """POST /login/callback, /api/auth/login 401 -> 200 HTML lỗi credential."""
    from mcp_app.server import build_asgi_app

    respx.post(f"{_API_BASE_URL}/api/auth/login").mock(
        return_value=httpx.Response(401, json=_envelope_err("INVALID", "Sai"))
    )
    app = build_asgi_app()
    with TestClient(app) as client:
        resp = client.post(
            "/login/callback",
            data={"txn": "txn-x", "email": "a@b.com", "password": "sai"},
        )
    assert resp.status_code == 200
    assert "Sai tài khoản hoặc mật khẩu" in resp.text


@respx.mock
def test_login_callback_success_redirects(oauth_env) -> None:
    """pending seed + /api/auth/login 200 -> 302 redirect kèm code= + state=."""
    import asyncio

    from mcp_app.server import _get_oauth_store, build_asgi_app

    from .conftest import fake_pending_authorize

    respx.post(f"{_API_BASE_URL}/api/auth/login").mock(
        return_value=httpx.Response(
            200,
            json=_envelope_ok(
                {
                    "access_token": "jwt-a",
                    "refresh_token": "jwt-r",
                    "expires_at": 9999999999,
                    "user": {"id": "u1", "email": "a@b.com", "role": "admin"},
                }
            ),
        )
    )
    app = build_asgi_app()
    with TestClient(app) as client:
        # Seed pending vào store mà provider dùng (lifespan đã init_schema).
        store = _get_oauth_store()
        txn = asyncio.get_event_loop().run_until_complete(
            fake_pending_authorize(store, txn="txn-success")
        )
        resp = client.post(
            "/login/callback",
            data={"txn": txn, "email": "a@b.com", "password": "pwd"},
            follow_redirects=False,
        )
    assert resp.status_code == 302
    location = resp.headers["location"]
    assert "code=" in location
    assert "state=" in location


def test_lifespan_inits_schema(oauth_env) -> None:
    """App start qua TestClient kích hoạt lifespan -> OAuthStore schema sẵn sàng."""
    import asyncio

    from mcp_app.server import _get_oauth_store, build_asgi_app

    app = build_asgi_app()
    with TestClient(app):
        # Lifespan startup đã chạy init_schema — save_client/get_client không lỗi.
        store = _get_oauth_store()

        async def _check() -> dict | None:
            await store.save_client("c1", {"client_id": "c1", "redirect_uris": ["x"]})
            return await store.get_client("c1")

        result = asyncio.get_event_loop().run_until_complete(_check())
    assert result is not None
    assert result["client_id"] == "c1"


@pytest.mark.critical
def test_metadata_endpoint(oauth_env) -> None:
    """GET /.well-known/oauth-authorization-server -> 200 JSON có endpoint chính."""
    from mcp_app.server import build_asgi_app

    app = build_asgi_app()
    with TestClient(app) as client:
        resp = client.get("/.well-known/oauth-authorization-server")
    assert resp.status_code == 200
    meta = resp.json()
    assert "issuer" in meta
    assert "authorization_endpoint" in meta
    assert "token_endpoint" in meta
    assert "registration_endpoint" in meta


def test_protected_resource_metadata(oauth_env) -> None:
    """GET /.well-known/oauth-protected-resource -> 200 JSON."""
    from mcp_app.server import build_asgi_app

    app = build_asgi_app()
    with TestClient(app) as client:
        resp = client.get("/.well-known/oauth-protected-resource")
    assert resp.status_code == 200
    assert isinstance(_json.loads(resp.text), dict)
