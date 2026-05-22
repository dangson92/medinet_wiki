"""Phase 3 SSO-01 — Unit test get_current_user branch JWKS (Plan 03-02 Task 4).

Verify:
- Central hub_name=central → dùng JWTManager.verify_token (M2 path), JWKSCache.verify_token_with_key KHÔNG gọi
- Hub con + JWKSCache None → 503 JWKS_CACHE_UNAVAILABLE
- Hub con + JWT thiếu kid → 401 INVALID_TOKEN ("Token thiếu kid header")
- Hub con + JWKSStaleError → 503 JWKS_STALE

Decision traceability:
- D-V3-Phase3-D — Hub con verify via JWKSCache.get_public_key(kid)
- T-03-02-06 — JWT M2 cũ thiếu kid → reject 401 (acceptable downtime ~15-30s)
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException


@pytest.fixture
def public_key_path() -> Path:
    p = Path("keys/public.pem")
    if not p.exists():
        pytest.skip("api/keys/public.pem missing — run 'make keys'")
    return p


def _make_request_with_jwks_cache(jwks_cache_or_none: object) -> MagicMock:
    """Build mock Request với app.state.jwks_cache."""
    request = MagicMock()
    request.app.state.jwks_cache = jwks_cache_or_none
    return request


def _common_hub_env(
    monkeypatch: pytest.MonkeyPatch, hub_name: str
) -> None:
    """Set env vars để get_settings() trả Settings với hub_name + DSN matching."""
    db = "medinet_central" if hub_name == "central" else f"medinet_hub_{hub_name}"
    monkeypatch.setenv("HUB_NAME", hub_name)
    monkeypatch.setenv(
        "DATABASE_URL", f"postgresql+asyncpg://u:p@localhost:5432/{db}"
    )
    monkeypatch.setenv(
        "COCOINDEX_DATABASE_URL",
        "postgresql://u:p@localhost:5432/medinet_cocoindex",
    )
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    if hub_name != "central":
        monkeypatch.setenv(
            "CENTRAL_JWKS_URL",
            "http://python-api-central:8080/.well-known/jwks.json",
        )
    from app.config import get_settings

    get_settings.cache_clear()


async def test_central_uses_jwt_manager_local_pem(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Central → dùng jwt_mgr.verify_token (M2 path) — KHÔNG đụng JWKSCache."""
    _common_hub_env(monkeypatch, "central")

    from app.auth.dependencies import get_current_user

    # Mock jwt_mgr.verify_token return JWTClaims
    claims_mock = MagicMock()
    claims_mock.sub = str(uuid4())
    claims_mock.jti = "test_jti"
    jwt_mgr = MagicMock()
    jwt_mgr.verify_token = MagicMock(return_value=claims_mock)
    jwt_mgr.verify_token_with_key = MagicMock()

    # Mock DB return user
    user_mock = MagicMock()
    user_mock.id = claims_mock.sub
    db_mock = MagicMock()
    db_mock.execute = AsyncMock()
    db_mock.execute.return_value.scalar_one_or_none = MagicMock(
        return_value=user_mock
    )

    request_mock = _make_request_with_jwks_cache(None)

    user = await get_current_user(
        request=request_mock,
        token="dummy.token.here",
        jwt_mgr=jwt_mgr,
        redis=None,
        db=db_mock,
    )
    assert user is user_mock
    jwt_mgr.verify_token.assert_called_once()
    jwt_mgr.verify_token_with_key.assert_not_called()


async def test_hub_con_jwks_cache_none_returns_503(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Hub con + app.state.jwks_cache None → HTTPException 503 JWKS_CACHE_UNAVAILABLE."""
    _common_hub_env(monkeypatch, "yte")

    from app.auth.dependencies import get_current_user

    request_mock = _make_request_with_jwks_cache(None)
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(
            request=request_mock,
            token="dummy.token.here",
            jwt_mgr=MagicMock(),
            redis=None,
            db=MagicMock(),
        )
    assert exc_info.value.status_code == 503
    assert isinstance(exc_info.value.detail, dict)
    assert exc_info.value.detail["code"] == "JWKS_CACHE_UNAVAILABLE"


async def test_hub_con_jwt_missing_kid_returns_401(
    monkeypatch: pytest.MonkeyPatch, public_key_path: Path
) -> None:
    """JWT không có kid header → 401 INVALID_TOKEN ("Token thiếu kid header")."""
    _common_hub_env(monkeypatch, "yte")

    # Sign JWT KHÔNG kid header (M2 baseline cũ — T-03-02-06)
    import jwt as pyjwt

    private_pem = Path("keys/private.pem").read_bytes()
    token_no_kid = pyjwt.encode(
        {"sub": "test", "iss": "medinet-wiki"},
        private_pem,
        algorithm="RS256",
        # KHÔNG headers={"kid": ...}
    )

    from app.auth.dependencies import get_current_user
    from app.auth.jwks import JWKSCache

    jwks_cache_mock = MagicMock(spec=JWKSCache)
    request_mock = _make_request_with_jwks_cache(jwks_cache_mock)

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(
            request=request_mock,
            token=token_no_kid,
            jwt_mgr=MagicMock(),
            redis=None,
            db=MagicMock(),
        )
    assert exc_info.value.status_code == 401
    assert isinstance(exc_info.value.detail, dict)
    assert exc_info.value.detail["code"] == "INVALID_TOKEN"
    assert "thiếu kid" in exc_info.value.detail["message"]


async def test_hub_con_jwks_stale_returns_503(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """JWKSCache stale > 24h → 503 JWKS_STALE (R-V3-5 fail-loud delayed)."""
    _common_hub_env(monkeypatch, "yte")

    import jwt as pyjwt

    private_pem = Path("keys/private.pem").read_bytes()
    token = pyjwt.encode(
        {"sub": "test", "iss": "medinet-wiki"},
        private_pem,
        algorithm="RS256",
        headers={"kid": "some_kid"},
    )

    from app.auth.dependencies import get_current_user
    from app.auth.jwks import JWKSCache, JWKSStaleError

    jwks_cache_mock = MagicMock(spec=JWKSCache)
    jwks_cache_mock.get_public_key = MagicMock(
        side_effect=JWKSStaleError("cache quá hạn 86400s")
    )
    request_mock = _make_request_with_jwks_cache(jwks_cache_mock)

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(
            request=request_mock,
            token=token,
            jwt_mgr=MagicMock(),
            redis=None,
            db=MagicMock(),
        )
    assert exc_info.value.status_code == 503
    assert isinstance(exc_info.value.detail, dict)
    assert exc_info.value.detail["code"] == "JWKS_STALE"
