"""Unit test JWTManager — Plan 03-02 (AUTH-06).

Phase 3 unit test KHÔNG cần Postgres/Redis. Load PEM thật từ keys/ Phase 1.
Override TTL ngắn cho test expired (KHÔNG dùng time.sleep — bake TTL âm).
"""
from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import Any

import jwt as pyjwt
import pytest


@pytest.fixture
def jwt_manager(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Sinh JWTManager với keys/ Phase 1 thật."""
    # CWD pytest = Hub_All/api/ — keys/ tương đối hợp lệ.
    monkeypatch.setenv("JWT_PRIVATE_KEY_PATH", "keys/private.pem")
    monkeypatch.setenv("JWT_PUBLIC_KEY_PATH", "keys/public.pem")
    monkeypatch.setenv("JWT_ACCESS_TOKEN_TTL", "900")
    monkeypatch.setenv("JWT_REFRESH_TOKEN_TTL", "604800")

    from app.auth import JWTManager
    from app.config import get_settings

    get_settings.cache_clear()
    return JWTManager(get_settings())


def test_issue_token_pair_returns_valid_rs256(jwt_manager: Any) -> None:
    pair = jwt_manager.issue_token_pair(
        user_id="11111111-1111-1111-1111-111111111111",
        email="admin@medinet.vn",
        full_name="System Admin",
        role="admin",
        hub_ids=["22222222-2222-2222-2222-222222222222"],
    )
    assert pair.access_token
    assert pair.refresh_token
    assert pair.access_jti != pair.refresh_jti

    # Decode raw cùng public key — verify RS256 đúng.
    # Plan 03-03 Rule 3 regression: JWT mới include aud claim → pyjwt strict
    # decode yêu cầu audience param match (KHÔNG là caller mismatch error).
    pub = Path("keys/public.pem").read_bytes()
    decoded = pyjwt.decode(
        pair.access_token,
        pub,
        algorithms=["RS256"],
        issuer="medinet-wiki",
        audience="medinet-wiki",  # Phase 3 Plan 03-03 SSO-02
    )
    assert decoded["sub"] == "11111111-1111-1111-1111-111111111111"
    assert decoded["role"] == "admin"
    assert decoded["token_type"] == "access"
    assert "jti" in decoded


def test_verify_token_happy_access(jwt_manager: Any) -> None:
    pair = jwt_manager.issue_token_pair(
        user_id="33333333-3333-3333-3333-333333333333",
        email="editor@medinet.vn",
        full_name="Editor User",
        role="editor",
        hub_ids=["hub-a", "hub-b"],
    )
    claims = jwt_manager.verify_token(pair.access_token, expected_type="access")
    assert claims.sub == "33333333-3333-3333-3333-333333333333"
    assert claims.role == "editor"
    assert claims.hub_ids == ["hub-a", "hub-b"]
    assert claims.token_type == "access"


def test_verify_token_rejects_wrong_type(jwt_manager: Any) -> None:
    from app.auth import JWTError

    pair = jwt_manager.issue_token_pair(
        user_id="x",
        email="x@y.vn",
        full_name=None,
        role="viewer",
        hub_ids=[],
    )
    with pytest.raises(JWTError, match="Loại token sai"):
        jwt_manager.verify_token(pair.access_token, expected_type="refresh")


def test_verify_token_rejects_expired(jwt_manager: Any) -> None:
    """Bake TTL âm để token expired ngay khi sinh."""
    from app.auth import JWTError

    jwt_manager._access_ttl = timedelta(seconds=-10)  # đã hết hạn 10s trước
    pair = jwt_manager.issue_token_pair(
        user_id="x",
        email="x@y.vn",
        full_name=None,
        role="viewer",
        hub_ids=[],
    )
    with pytest.raises(JWTError, match="hết hạn"):
        jwt_manager.verify_token(pair.access_token, expected_type="access")


def test_verify_token_rejects_tampered_signature(jwt_manager: Any) -> None:
    from app.auth import JWTError

    pair = jwt_manager.issue_token_pair(
        user_id="x",
        email="x@y.vn",
        full_name=None,
        role="admin",
        hub_ids=[],
    )
    # Sửa 5 ký tự cuối signature.
    tampered = pair.access_token[:-5] + "AAAAA"
    with pytest.raises(JWTError):
        jwt_manager.verify_token(tampered, expected_type="access")


def test_verify_token_rejects_alg_none_attack(jwt_manager: Any) -> None:
    """T-03-jwt-alg-confusion — token signed với alg=none KHÔNG được decode."""
    from app.auth import JWTError

    # PyJWT cho phép encode alg=none (xem `algorithms` list của library).
    evil_payload = {
        "sub": "attacker",
        "email": "evil@x.vn",
        "name": "evil",
        "role": "admin",
        "hub_ids": [],
        "iss": "medinet-wiki",
        "iat": 0,
        "exp": 9999999999,
        "jti": "evil-jti",
        "token_type": "access",
    }
    evil_token = pyjwt.encode(evil_payload, key="", algorithm="none")
    with pytest.raises(JWTError):
        jwt_manager.verify_token(evil_token, expected_type="access")


def test_verify_token_rejects_wrong_issuer(jwt_manager: Any) -> None:
    from app.auth import JWTError

    # Ký với private key thật nhưng issuer khác — bypass signature check, fail issuer check.
    priv = Path("keys/private.pem").read_bytes()
    evil_payload = {
        "sub": "x",
        "email": "x@y.vn",
        "name": "x",
        "role": "admin",
        "hub_ids": [],
        "iss": "evil-issuer",  # NOT medinet-wiki
        "iat": 0,
        "exp": 9999999999,
        "jti": "x-jti",
        "token_type": "access",
    }
    evil = pyjwt.encode(evil_payload, priv, algorithm="RS256")
    with pytest.raises(JWTError, match="issuer"):
        jwt_manager.verify_token(evil, expected_type="access")


def test_jwt_claims_shape_matches_spec(jwt_manager: Any) -> None:
    """AUTH-06 — claims phải có đủ 10 field cho Plan 03-04 service dùng."""
    pair = jwt_manager.issue_token_pair(
        user_id="x",
        email="x@y.vn",
        full_name="Tên có dấu",
        role="viewer",
        hub_ids=["h1"],
    )
    # Plan 03-03 Rule 3 regression: audience param required (JWT mới có aud claim).
    pub = Path("keys/public.pem").read_bytes()
    decoded = pyjwt.decode(
        pair.access_token,
        pub,
        algorithms=["RS256"],
        issuer="medinet-wiki",
        audience="medinet-wiki",  # Phase 3 Plan 03-03 SSO-02
    )
    required = {
        "sub",
        "email",
        "name",
        "role",
        "hub_ids",
        "iss",
        "aud",  # Phase 3 Plan 03-03 — REQUIRED
        "iat",
        "exp",
        "jti",
        "token_type",
    }
    assert required.issubset(decoded.keys()), (
        f"missing: {required - decoded.keys()}"
    )
