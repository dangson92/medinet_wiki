"""Phase 3 SSO-02/03 — Unit test JWT iss/aud/hub_ids claim (Plan 03-03 Task 1).

Verify (D-V3-Phase3-E):
- JWT_AUDIENCE constant = "medinet-wiki"
- JWT_ISSUER unchanged = "medinet-wiki" (RE-CONFIRM — KHÔNG URL-based, defer Phase 7)
- issue_token_pair build claim với aud + hub_ids REQUIRED
- verify_token + verify_token_with_key strict check audience
- M2 cũ JWT thiếu aud/hub_ids → JWTError reject (backward incompat acceptable
  ~15-30s downtime — communicate operator Plan 03-05 README)
- hub_ids empty list OK (user chưa assign hub — central admin onboard scenario)

Tracing: SSO-02 (Redis key rename) + SSO-03 (hub_ids claim) + D-V3-Phase3-E
(iss + aud + hub_ids REQUIRED).
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import jwt as pyjwt
import pytest


@pytest.fixture
def private_pem() -> bytes:
    p = Path("keys/private.pem")
    if not p.exists():
        pytest.skip("api/keys/private.pem missing — run 'make keys'")
    return p.read_bytes()


@pytest.fixture
def public_pem() -> bytes:
    p = Path("keys/public.pem")
    if not p.exists():
        pytest.skip("api/keys/public.pem missing — run 'make keys'")
    return p.read_bytes()


@pytest.fixture
def jwt_manager(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Boot JWTManager với env JWT_PRIVATE_KEY_PATH + JWT_PUBLIC_KEY_PATH."""
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
    monkeypatch.setenv("JWT_PRIVATE_KEY_PATH", "keys/private.pem")
    monkeypatch.setenv("JWT_PUBLIC_KEY_PATH", "keys/public.pem")
    monkeypatch.setenv("JWT_ACCESS_TOKEN_TTL", "900")
    monkeypatch.setenv("JWT_REFRESH_TOKEN_TTL", "604800")
    from app.auth.jwt import JWTManager
    from app.config import get_settings

    get_settings.cache_clear()
    return JWTManager(get_settings())


def test_jwt_audience_constant_value() -> None:
    """JWT_AUDIENCE == 'medinet-wiki' (single audience v3.0-a; split defer Phase 7)."""
    from app.auth.jwt import JWT_AUDIENCE

    assert JWT_AUDIENCE == "medinet-wiki"


def test_jwt_issuer_unchanged_medinet_wiki() -> None:
    """JWT_ISSUER GIỮ NGUYÊN 'medinet-wiki' — RE-CONFIRM D-V3-Phase3-E."""
    from app.auth.jwt import JWT_ISSUER

    assert JWT_ISSUER == "medinet-wiki"


def test_jwt_with_aud_and_hub_ids_passes(jwt_manager: Any) -> None:
    """issue_token_pair build JWT với aud + hub_ids → verify_token PASS."""
    pair = jwt_manager.issue_token_pair(
        user_id="abc",
        email="user@medinet.vn",
        full_name="Test",
        role="viewer",
        hub_ids=["yte"],
    )
    claims = jwt_manager.verify_token(pair.access_token, expected_type="access")
    assert claims.aud == ["medinet-wiki"]
    assert claims.hub_ids == ["yte"]
    assert claims.iss == "medinet-wiki"


def test_jwt_missing_aud_rejects(jwt_manager: Any, private_pem: bytes) -> None:
    """Sign JWT raw KHÔNG aud claim → verify_token raise JWTError."""
    from app.auth.jwt import JWT_ALGORITHM, JWT_ISSUER, JWTError

    now = datetime.now(tz=UTC)
    token_no_aud = pyjwt.encode(
        {
            "sub": "abc",
            "email": "u@m.vn",
            "name": "T",
            "role": "viewer",
            "hub_ids": ["yte"],
            "iss": JWT_ISSUER,
            # KHÔNG "aud"
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=15)).timestamp()),
            "jti": "test_jti",
            "token_type": "access",
        },
        private_pem,
        algorithm=JWT_ALGORITHM,
        headers={"kid": "test_kid"},
    )
    with pytest.raises(JWTError, match="audience|aud"):
        jwt_manager.verify_token(token_no_aud, expected_type="access")


def test_jwt_wrong_aud_rejects(jwt_manager: Any, private_pem: bytes) -> None:
    """JWT với aud=['wrong-service'] → verify_token raise JWTError."""
    from app.auth.jwt import JWT_ALGORITHM, JWT_ISSUER, JWTError

    now = datetime.now(tz=UTC)
    token_wrong_aud = pyjwt.encode(
        {
            "sub": "abc",
            "email": "u@m.vn",
            "name": "T",
            "role": "viewer",
            "hub_ids": ["yte"],
            "iss": JWT_ISSUER,
            "aud": ["wrong-service"],
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=15)).timestamp()),
            "jti": "test_jti",
            "token_type": "access",
        },
        private_pem,
        algorithm=JWT_ALGORITHM,
        headers={"kid": "test_kid"},
    )
    with pytest.raises(JWTError, match="audience|aud"):
        jwt_manager.verify_token(token_wrong_aud, expected_type="access")


def test_jwt_missing_hub_ids_rejects(
    jwt_manager: Any, private_pem: bytes
) -> None:
    """JWT KHÔNG hub_ids claim → JWTClaims.model_validate raise → JWTError."""
    from app.auth.jwt import JWT_ALGORITHM, JWT_AUDIENCE, JWT_ISSUER, JWTError

    now = datetime.now(tz=UTC)
    token_no_hub_ids = pyjwt.encode(
        {
            "sub": "abc",
            "email": "u@m.vn",
            "name": "T",
            "role": "viewer",
            # KHÔNG "hub_ids"
            "iss": JWT_ISSUER,
            "aud": [JWT_AUDIENCE],
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=15)).timestamp()),
            "jti": "test_jti",
            "token_type": "access",
        },
        private_pem,
        algorithm=JWT_ALGORITHM,
        headers={"kid": "test_kid"},
    )
    with pytest.raises(JWTError, match="Claims không hợp lệ|hub_ids"):
        jwt_manager.verify_token(token_no_hub_ids, expected_type="access")


def test_jwt_empty_hub_ids_allowed(jwt_manager: Any) -> None:
    """hub_ids=[] OK (user chưa assign hub — admin onboard scenario)."""
    pair = jwt_manager.issue_token_pair(
        user_id="abc",
        email="admin@medinet.vn",
        full_name="Admin",
        role="admin",
        hub_ids=[],  # empty allowed (REQUIRED nhưng empty list pass)
    )
    claims = jwt_manager.verify_token(pair.access_token, expected_type="access")
    assert claims.hub_ids == []
    assert claims.aud == ["medinet-wiki"]


def test_verify_token_with_key_same_strict_audience(
    jwt_manager: Any, public_pem: bytes
) -> None:
    """verify_token_with_key (hub con path) cũng strict audience."""
    from cryptography.hazmat.primitives import serialization

    pub_key = serialization.load_pem_public_key(public_pem)
    pair = jwt_manager.issue_token_pair(
        user_id="abc",
        email="u@m.vn",
        full_name="T",
        role="viewer",
        hub_ids=["yte"],
    )
    claims = jwt_manager.verify_token_with_key(
        pair.access_token, pub_key, expected_type="access"
    )
    assert claims.aud == ["medinet-wiki"]
    assert claims.hub_ids == ["yte"]


def test_verify_token_with_key_rejects_missing_aud(
    jwt_manager: Any, private_pem: bytes, public_pem: bytes
) -> None:
    """verify_token_with_key cũng reject JWT thiếu aud (hub con path strict)."""
    from cryptography.hazmat.primitives import serialization

    from app.auth.jwt import JWT_ALGORITHM, JWT_ISSUER, JWTError

    pub_key = serialization.load_pem_public_key(public_pem)
    now = datetime.now(tz=UTC)
    token_no_aud = pyjwt.encode(
        {
            "sub": "abc",
            "email": "u@m.vn",
            "name": "T",
            "role": "viewer",
            "hub_ids": ["yte"],
            "iss": JWT_ISSUER,
            # KHÔNG "aud"
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=15)).timestamp()),
            "jti": "test_jti",
            "token_type": "access",
        },
        private_pem,
        algorithm=JWT_ALGORITHM,
        headers={"kid": "test_kid"},
    )
    with pytest.raises(JWTError, match="audience|aud"):
        jwt_manager.verify_token_with_key(
            token_no_aud, pub_key, expected_type="access"
        )
