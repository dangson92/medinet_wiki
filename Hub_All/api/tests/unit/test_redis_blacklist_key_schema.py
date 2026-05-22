"""Phase 3 SSO-02 — Unit test Redis blacklist key schema (Plan 03-03 Task 2).

Verify (D-V3-Phase3-H):
- REDIS_BLACKLIST_PREFIX constant = "auth:blacklist:" (namespace clarity)
- make_blacklist_key("jti_xyz") → "auth:blacklist:jti_xyz"
- AuthService.logout dùng renamed key (key prefix + value "1" marker)
- TTL = exp - now() với min 1s guard (M2 carry forward `max(1, exp-now)`)
- get_current_user dependency dùng renamed key

Tracing: SSO-02 (Redis blacklist key cross-process) + D-V3-Phase3-H
(key schema `auth:blacklist:{jti}` + TTL auto-expire).
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest


def test_blacklist_key_prefix_constant_exposed() -> None:
    """REDIS_BLACKLIST_PREFIX = 'auth:blacklist:' (D-V3-Phase3-H)."""
    from app.auth import REDIS_BLACKLIST_PREFIX

    assert REDIS_BLACKLIST_PREFIX == "auth:blacklist:"


def test_make_blacklist_key_format() -> None:
    """make_blacklist_key('jti_xyz') → 'auth:blacklist:jti_xyz'."""
    from app.auth import make_blacklist_key

    assert make_blacklist_key("jti_xyz") == "auth:blacklist:jti_xyz"
    assert make_blacklist_key("abc-123") == "auth:blacklist:abc-123"


def test_make_blacklist_key_uuid_format() -> None:
    """UUID4 jti → key chứa uuid string."""
    from app.auth import make_blacklist_key

    jti = str(uuid4())
    assert make_blacklist_key(jti) == f"auth:blacklist:{jti}"


@pytest.mark.asyncio
async def test_logout_blacklist_key_prefix_auth() -> None:
    """AuthService.logout call redis.set với key 'auth:blacklist:{jti}'."""
    from app.auth.service import AuthService

    redis_mock = AsyncMock()
    db_mock = AsyncMock()
    jwt_mock = MagicMock()
    jwt_mock.refresh_ttl_seconds = 604800
    service = AuthService(
        db=db_mock,
        redis=redis_mock,
        jwt_manager=jwt_mock,
        dummy_password_hash="dummy",
    )
    now_ts = int(datetime.now(tz=UTC).timestamp())
    await service.logout(
        access_jti="jti_abc",
        access_exp=now_ts + 100,
        refresh_token=None,
    )
    # Assert set called với key prefix đúng
    redis_mock.set.assert_called_once()
    call_args = redis_mock.set.call_args
    key = call_args.args[0] if call_args.args else call_args.kwargs.get("name")
    assert key == "auth:blacklist:jti_abc"
    # Value "1" marker
    value = (
        call_args.args[1]
        if len(call_args.args) > 1
        else call_args.kwargs.get("value")
    )
    assert value == "1"


@pytest.mark.asyncio
async def test_logout_blacklist_ttl_matches_exp_minus_now() -> None:
    """TTL ≈ access_exp - now() (±5s tolerance for wall-clock test runtime)."""
    from app.auth.service import AuthService

    redis_mock = AsyncMock()
    db_mock = AsyncMock()
    jwt_mock = MagicMock()
    service = AuthService(
        db=db_mock,
        redis=redis_mock,
        jwt_manager=jwt_mock,
        dummy_password_hash="dummy",
    )
    now_ts = int(datetime.now(tz=UTC).timestamp())
    await service.logout(
        access_jti="abc",
        access_exp=now_ts + 100,
        refresh_token=None,
    )
    call_args = redis_mock.set.call_args
    ttl = call_args.kwargs.get("ex")
    assert ttl is not None
    assert 95 <= ttl <= 100  # tolerance ±5s for test wall-clock


@pytest.mark.asyncio
async def test_logout_blacklist_ttl_min_1_second_for_expired() -> None:
    """Token đã expired → TTL = max(1, exp - now) = 1s (M2 guard carry forward)."""
    from app.auth.service import AuthService

    redis_mock = AsyncMock()
    db_mock = AsyncMock()
    jwt_mock = MagicMock()
    service = AuthService(
        db=db_mock,
        redis=redis_mock,
        jwt_manager=jwt_mock,
        dummy_password_hash="dummy",
    )
    now_ts = int(datetime.now(tz=UTC).timestamp())
    await service.logout(
        access_jti="abc",
        access_exp=now_ts - 100,  # đã expired
        refresh_token=None,
    )
    call_args = redis_mock.set.call_args
    assert call_args.kwargs.get("ex") == 1


@pytest.mark.asyncio
async def test_get_current_user_uses_renamed_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """get_current_user query redis.exists('auth:blacklist:jti') → 1 → 401 TOKEN_REVOKED.

    Verify key prefix renamed `auth:blacklist:` (KHÔNG `blacklist:`).
    """
    from fastapi import HTTPException

    monkeypatch.setenv("HUB_NAME", "central")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+asyncpg://u:p@localhost:5432/medinet_central",
    )
    monkeypatch.setenv(
        "COCOINDEX_DATABASE_URL",
        "postgresql://u:p@localhost:5432/medinet_cocoindex",
    )
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    from app.config import get_settings

    get_settings.cache_clear()

    from app.auth.dependencies import get_current_user

    claims_mock = MagicMock()
    claims_mock.sub = "user_abc"
    claims_mock.jti = "jti_xyz"
    jwt_mgr = MagicMock()
    jwt_mgr.verify_token = MagicMock(return_value=claims_mock)
    redis_mock = AsyncMock()
    redis_mock.exists = AsyncMock(return_value=1)  # blacklisted
    db_mock = AsyncMock()
    request_mock = MagicMock()
    request_mock.app.state.jwks_cache = None

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(
            request=request_mock,
            token="dummy.token.here",
            jwt_mgr=jwt_mgr,
            redis=redis_mock,
            db=db_mock,
        )
    assert exc_info.value.status_code == 401
    detail: Any = exc_info.value.detail
    assert isinstance(detail, dict)
    assert detail["code"] == "TOKEN_REVOKED"
    # Verify key prefix renamed `auth:blacklist:` (KHÔNG còn `blacklist:`)
    redis_mock.exists.assert_called_once_with("auth:blacklist:jti_xyz")
