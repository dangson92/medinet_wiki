"""Integration test POST /api/auth/login — Plan 03-05 (ROADMAP AC1).

Chạy trên Postgres + Redis testcontainers thật + Alembic head migration
applied. Verify:
- AC1: login admin Go-seed hash → 200 envelope shape match Go.
- Envelope keys EXACTLY {success, data, error, meta} — byte-identical Go.
- Wrong password / unknown email → 401 INVALID_CREDENTIALS (anti-timing oracle).
- Bad email format → 422 (Pydantic v2 validation; envelope hardening defer Phase 10).
"""
from __future__ import annotations

from typing import Any

import httpx
import pytest


@pytest.mark.critical
@pytest.mark.integration
@pytest.mark.asyncio
async def test_login_happy_admin_returns_envelope(
    auth_client: httpx.AsyncClient, admin_user: dict[str, str]
) -> None:
    """AC1 — Login admin@medinet.vn / Admin@123 → 200 envelope đủ field."""
    r = await auth_client.post(
        "/api/auth/login",
        json={"email": admin_user["email"], "password": admin_user["password"]},
    )
    assert r.status_code == 200, r.text
    body: dict[str, Any] = r.json()
    # Envelope top-level shape.
    assert body["success"] is True
    assert body["error"] is None
    assert body["meta"] is None

    # Data field.
    data = body["data"]
    assert "access_token" in data
    assert "refresh_token" in data
    assert "expires_at" in data
    assert isinstance(data["expires_at"], int)
    assert isinstance(data["access_token"], str)
    assert isinstance(data["refresh_token"], str)

    # User nested — shape UserWithRoles `{user, roles}` (D6 contract frontend).
    user_with_roles = data["user"]
    user = user_with_roles["user"]
    assert user["id"] == admin_user["id"]
    assert user["email"] == admin_user["email"]
    assert user["name"] == "System Admin"
    # Chưa assign hub (test fixture không INSERT user_hubs) → roles rỗng.
    assert user_with_roles["roles"] == []


@pytest.mark.critical
@pytest.mark.integration
@pytest.mark.asyncio
async def test_login_wrong_password_returns_401_invalid_credentials(
    auth_client: httpx.AsyncClient, admin_user: dict[str, str]
) -> None:
    """AC1 — Sai password → 401 INVALID_CREDENTIALS với envelope shape."""
    r = await auth_client.post(
        "/api/auth/login",
        json={"email": admin_user["email"], "password": "WrongPassword!"},
    )
    assert r.status_code == 401, r.text
    body = r.json()
    assert body["success"] is False
    assert body["data"] is None
    assert body["error"]["code"] == "INVALID_CREDENTIALS"
    assert "Email hoặc mật khẩu" in body["error"]["message"]


@pytest.mark.critical
@pytest.mark.integration
@pytest.mark.asyncio
async def test_login_unknown_email_returns_same_shape(
    auth_client: httpx.AsyncClient, admin_user: dict[str, str]
) -> None:
    """Anti-timing oracle T-03-04-timing — response shape IDENTICAL với wrong-password.

    Frontend KHÔNG phân biệt được "email không tồn tại" vs "sai password" →
    attacker KHÔNG enumerate được email database.
    """
    _ = admin_user  # trigger fixture insert admin để DB có user khác (anti-timing)
    r = await auth_client.post(
        "/api/auth/login",
        json={"email": "nobody@medinet.vn", "password": "anything"},
    )
    assert r.status_code == 401, r.text
    body = r.json()
    # Same code → frontend không phân biệt được 2 case.
    assert body["error"]["code"] == "INVALID_CREDENTIALS"
    assert "Email hoặc mật khẩu" in body["error"]["message"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_login_validation_error_on_bad_email_format(
    auth_client: httpx.AsyncClient,
) -> None:
    """Pydantic v2 EmailStr reject "not-an-email" → 422 (validation gate)."""
    r = await auth_client.post(
        "/api/auth/login", json={"email": "not-an-email", "password": "x"}
    )
    # FastAPI Pydantic v2 raise 422 default. Plan 03-04 chưa wire envelope cho
    # 422 (defer Phase 10 hardening). Plan 03-05 chỉ assert 422 status code.
    assert r.status_code == 422


@pytest.mark.critical
@pytest.mark.integration
@pytest.mark.asyncio
async def test_login_envelope_shape_byte_identical_go(
    auth_client: httpx.AsyncClient, admin_user: dict[str, str]
) -> None:
    """AC1 — Envelope phải có EXACTLY 4 top-level key: success/data/error/meta.

    KHÔNG dư extra (request_id, version, ...) — byte-identical Go
    pkg/response/response.go APIResponse struct.
    """
    r = await auth_client.post(
        "/api/auth/login",
        json={"email": admin_user["email"], "password": admin_user["password"]},
    )
    body = r.json()
    assert set(body.keys()) == {"success", "data", "error", "meta"}, body.keys()
