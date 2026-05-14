"""Unit test middleware infra Phase 3 Plan 01.

Test in-process (httpx AsyncClient + ASGITransport) — KHÔNG cần Postgres/Redis,
KHÔNG dùng LifespanManager vì lifespan Phase 1 thử connect Postgres (asyncpg
create_pool) blocking trên Windows hơn 5s timeout của asgi-lifespan trong test
env không có Postgres. Pattern matches tests/test_main.py.

Conftest autouse fixture `_env` set DATABASE_URL/COCOINDEX_DATABASE_URL/REDIS_URL
placeholder để Settings load — middleware tests KHÔNG dùng DB/Redis nên placeholder
là đủ.
"""
from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    """In-process FastAPI client via ASGITransport (no lifespan).

    Import `create_app` BÊN TRONG fixture (KHÔNG top-level) để conftest
    autouse `_env` fixture set env vars TRƯỚC khi Settings parse — tránh
    pytest collect-time ValidationError (database_url required).
    """
    from app.main import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_request_id_generated_when_missing(client: AsyncClient) -> None:
    """Client KHÔNG gửi X-Request-Id → response header có UUID4 mới sinh."""
    r = await client.get("/healthz")
    assert "x-request-id" in r.headers
    # UUID4 format pattern
    assert re.fullmatch(
        r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}",
        r.headers["x-request-id"],
    ), r.headers["x-request-id"]


@pytest.mark.asyncio
async def test_request_id_echoed_when_present(client: AsyncClient) -> None:
    """Client gửi X-Request-Id custom → echo nguyên trị (KHÔNG validate format)."""
    r = await client.get(
        "/healthz", headers={"X-Request-Id": "custom-trace-abc-123"}
    )
    assert r.headers["x-request-id"] == "custom-trace-abc-123"


@pytest.mark.asyncio
async def test_security_headers_set(client: AsyncClient) -> None:
    """Mọi response có 5 security header cố định match Go security.go."""
    r = await client.get("/healthz")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["x-xss-protection"] == "1; mode=block"
    assert r.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert "camera=()" in r.headers["permissions-policy"]


@pytest.mark.asyncio
async def test_error_handler_returns_envelope_500() -> None:
    """Mount route stub raise RuntimeError → envelope 500 KHÔNG leak stack."""
    from app.main import create_app

    app = create_app()

    @app.get("/test/boom")
    async def boom() -> None:
        raise RuntimeError("intentional explosion for test")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/test/boom")
    assert r.status_code == 500
    body = r.json()
    assert body["success"] is False
    assert body["data"] is None
    assert body["error"]["code"] == "INTERNAL_ERROR"
    assert body["error"]["message"] == "Lỗi máy chủ nội bộ"
    assert body["meta"] is None
    # Stack trace KHÔNG leak vào body
    assert "RuntimeError" not in r.text
    assert "intentional explosion" not in r.text


def test_response_envelope_unauthorized_code_uppercase() -> None:
    """AUTH-01 D6 — error code = UPPER_SNAKE_CASE match Go."""
    from app.pkg import response as resp

    r = resp.unauthorized()
    body = json.loads(r.body)
    assert body["success"] is False
    assert body["error"]["code"] == "UNAUTHORIZED"
    assert r.status_code == 401


def test_response_envelope_forbidden_code_uppercase() -> None:
    """forbidden helper → 403 + code FORBIDDEN."""
    from app.pkg import response as resp

    r = resp.forbidden()
    body = json.loads(r.body)
    assert body["error"]["code"] == "FORBIDDEN"
    assert r.status_code == 403


def test_cors_production_rejects_lan_origin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """P12 mitigation — production env reject LAN origin ngay startup."""
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "http://192.168.1.5:5173")
    from app.config import get_settings

    get_settings.cache_clear()
    with pytest.raises(Exception) as exc_info:  # pydantic.ValidationError
        get_settings()
    msg = str(exc_info.value)
    # Pydantic core JSON-escape Unicode trong msg → check cả raw `cấm` lẫn
    # escape `ấm` + IP literal `192.168` + keyword `P12`.
    assert (
        "192.168" in msg
        or "P12" in msg
        or "cấm" in msg
        or "c\\u1ea5m" in msg
    )


def test_cors_dev_allows_localhost(monkeypatch: pytest.MonkeyPatch) -> None:
    """Dev env chấp nhận localhost — chỉ production strict."""
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "http://localhost:5173")
    from app.config import get_settings

    get_settings.cache_clear()
    s = get_settings()
    assert "http://localhost:5173" in s.cors_allowed_origins


@pytest.mark.asyncio
async def test_http_exception_passes_through() -> None:
    """ErrorHandlerMiddleware KHÔNG catch HTTPException → pass-through tới
    FastAPI exception_handler (Plan 03-05). Plan 03-01 chỉ verify status code
    đúng 401 và response body KHÔNG bị mask thành INTERNAL_ERROR envelope.
    """
    from fastapi import HTTPException

    from app.main import create_app

    app = create_app()

    @app.get("/test/raise-http")
    async def raise_http() -> None:
        raise HTTPException(
            status_code=401,
            detail={"code": "TEST_CUSTOM", "message": "test"},
        )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/test/raise-http")
    assert r.status_code == 401, r.text
    # ErrorHandlerMiddleware KHÔNG được mask HTTPException thành INTERNAL_ERROR
    assert "INTERNAL_ERROR" not in r.text, (
        f"HTTPException bị catch nhầm — body: {r.text}"
    )
