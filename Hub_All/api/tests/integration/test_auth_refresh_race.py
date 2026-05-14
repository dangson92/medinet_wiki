"""Integration test refresh token race — Plan 03-05 (ROADMAP AC5 / P16).

Chạy trên Postgres + Redis testcontainers thật. Concurrent 5 task asyncio
verify Redis SETNX atomic chống race condition trên jti cũ.

5 test:
1. test_refresh_happy_returns_new_pair — refresh happy path → token mới.
2. test_refresh_concurrent_5_only_one_wins — AC5 P16 — 1 PASS, 4 fail.
3. test_refresh_revoked_token_returns_401 — replay token đã refresh → 401.
4. test_refresh_invalid_jwt_returns_401 — garbage token → 401 INVALID_REFRESH_TOKEN.
5. test_refresh_with_access_token_returns_401_wrong_type — access vs refresh type.
"""
from __future__ import annotations

import asyncio
from typing import Any

import httpx
import pytest


@pytest.mark.critical
@pytest.mark.integration
@pytest.mark.asyncio
async def test_refresh_happy_returns_new_pair(
    auth_client: httpx.AsyncClient,
    admin_user: dict[str, str],
    admin_token_pair: dict[str, Any],
) -> None:
    """AUTH-02 happy path — refresh → 200 + token mới ≠ token cũ."""
    old_refresh = admin_token_pair["refresh_token"]
    old_access = admin_token_pair["access_token"]

    r = await auth_client.post(
        "/api/auth/refresh", json={"refresh_token": old_refresh}
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["success"] is True
    data = body["data"]
    assert data["access_token"] != old_access
    assert data["refresh_token"] != old_refresh
    assert data["user"]["email"] == admin_user["email"]
    assert data["user"]["role"] == "admin"


@pytest.mark.critical
@pytest.mark.integration
@pytest.mark.asyncio
async def test_refresh_concurrent_5_only_one_wins(
    auth_client: httpx.AsyncClient,
    admin_user: dict[str, str],
    admin_token_pair: dict[str, Any],
) -> None:
    """AC5 P16 — 5 asyncio.gather() refresh CÙNG token → 1 PASS, 4 fail-401.

    Verify Redis SETNX atomic lock `lock:refresh:<jti>` chống race condition:
    chỉ 1 caller thắng được lock, 4 caller còn lại nhận REFRESH_RACE 401.
    """
    _ = admin_user  # trigger fixture insert admin user
    refresh_token = admin_token_pair["refresh_token"]

    async def _do_refresh() -> int:
        r = await auth_client.post(
            "/api/auth/refresh", json={"refresh_token": refresh_token}
        )
        return r.status_code

    statuses = await asyncio.gather(*[_do_refresh() for _ in range(5)])
    success = sum(1 for s in statuses if s == 200)
    fail = sum(1 for s in statuses if s == 401)
    assert success == 1, (
        f"P16 mitigation FAIL — expected exactly 1 success, "
        f"got {success}. statuses={statuses}"
    )
    assert fail == 4, (
        f"P16 mitigation FAIL — expected exactly 4 fail-401, "
        f"got {fail}. statuses={statuses}"
    )


@pytest.mark.critical
@pytest.mark.integration
@pytest.mark.asyncio
async def test_refresh_revoked_token_returns_401(
    auth_client: httpx.AsyncClient,
    admin_user: dict[str, str],
    admin_token_pair: dict[str, Any],
) -> None:
    """Sau khi đã refresh thành công 1 lần, dùng lại refresh_token cũ → 401.

    T-03-04-refresh-replay mitigation: blacklist old jti + UPDATE refresh_tokens
    .revoked_at NOW() → replay fail.
    """
    _ = admin_user
    old_refresh = admin_token_pair["refresh_token"]

    # Refresh lần 1 — PASS.
    r1 = await auth_client.post(
        "/api/auth/refresh", json={"refresh_token": old_refresh}
    )
    assert r1.status_code == 200, r1.text

    # Refresh lần 2 với token cũ — FAIL (đã blacklist).
    r2 = await auth_client.post(
        "/api/auth/refresh", json={"refresh_token": old_refresh}
    )
    assert r2.status_code == 401, r2.text
    body = r2.json()
    # Code có thể là TOKEN_REVOKED (đã blacklist) hoặc REFRESH_RACE (nếu lock
    # còn TTL 30s) hoặc INVALID_REFRESH_TOKEN.
    assert body["error"]["code"] in {
        "TOKEN_REVOKED",
        "REFRESH_RACE",
        "INVALID_REFRESH_TOKEN",
    }, body


@pytest.mark.integration
@pytest.mark.asyncio
async def test_refresh_invalid_jwt_returns_401(
    auth_client: httpx.AsyncClient, admin_user: dict[str, str]
) -> None:
    """Garbage token → 401 INVALID_REFRESH_TOKEN."""
    _ = admin_user  # trigger fixture
    r = await auth_client.post(
        "/api/auth/refresh", json={"refresh_token": "not.a.valid.jwt"}
    )
    assert r.status_code == 401
    body = r.json()
    assert body["error"]["code"] == "INVALID_REFRESH_TOKEN"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_refresh_with_access_token_returns_401_wrong_type(
    auth_client: httpx.AsyncClient,
    admin_user: dict[str, str],
    admin_token_pair: dict[str, Any],
) -> None:
    """Gửi access_token thay vì refresh_token → 401 (verify_type fail).

    JWTManager.verify_token(expected_type="refresh") raise JWTError "Loại
    token sai" → service.refresh wrap thành AuthError INVALID_REFRESH_TOKEN.
    """
    _ = admin_user
    access = admin_token_pair["access_token"]
    r = await auth_client.post(
        "/api/auth/refresh", json={"refresh_token": access}
    )
    assert r.status_code == 401
    body = r.json()
    assert body["error"]["code"] == "INVALID_REFRESH_TOKEN"
