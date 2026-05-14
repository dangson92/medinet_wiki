"""Integration test JWT compat + log PII check — Plan 03-05 (ROADMAP AC2 + AUTH-06).

Verify:
- AC2: FastAPI-issued JWT decode được với keys/public.pem.
- AUTH-06: keypair PKCS#8 format verified qua scripts/verify_jwt_format.sh.
- AUTH-03 /me happy path.
- Logout blacklist access token (T-03-04-refresh-replay mitigation).
- T-03-04-pii-log: password + refresh_token KHÔNG leak vào log.

5 test:
1. test_login_token_decodable_with_public_key — AC2 core.
2. test_me_endpoint_returns_user_info_via_token — AUTH-03 /me happy.
3. test_logout_blacklists_access_token — blacklist verify.
4. test_pkcs8_key_format_verified — AUTH-06 keypair format.
5. test_log_no_password_leak — PII regression check.
"""
from __future__ import annotations

import logging
import re
import subprocess
from pathlib import Path
from typing import Any

import httpx
import jwt as pyjwt
import pytest


@pytest.mark.critical
@pytest.mark.integration
@pytest.mark.asyncio
async def test_login_token_decodable_with_public_key(
    auth_client: httpx.AsyncClient, admin_user: dict[str, str]
) -> None:
    """AC2 — Login admin → decode access_token bằng keys/public.pem PyJWT.

    Assert đủ 10 claim spec: sub, email, name, role, hub_ids, iss, iat, exp,
    jti, token_type.
    """
    r = await auth_client.post(
        "/api/auth/login",
        json={"email": admin_user["email"], "password": admin_user["password"]},
    )
    assert r.status_code == 200, r.text
    token = r.json()["data"]["access_token"]

    # Decode RAW bằng PyJWT — KHÔNG qua JWTManager (verify cross-process).
    pub = Path("keys/public.pem").read_bytes()
    decoded: dict[str, Any] = pyjwt.decode(
        token, pub, algorithms=["RS256"], issuer="medinet-wiki"
    )

    # Claims layout — match Plan 03-02 JWTClaims spec.
    assert decoded["sub"] == admin_user["id"]
    assert decoded["email"] == admin_user["email"]
    assert decoded["role"] == "admin"
    assert decoded["token_type"] == "access"
    assert decoded["iss"] == "medinet-wiki"
    assert "jti" in decoded
    assert "exp" in decoded
    assert "iat" in decoded
    assert "hub_ids" in decoded
    assert isinstance(decoded["hub_ids"], list)


@pytest.mark.critical
@pytest.mark.integration
@pytest.mark.asyncio
async def test_me_endpoint_returns_user_info_via_token(
    auth_client: httpx.AsyncClient,
    admin_user: dict[str, str],
    admin_token: str,
) -> None:
    """AUTH-03 — GET /api/auth/me với Bearer admin → 200 + UserPublic shape."""
    r = await auth_client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["success"] is True
    data = body["data"]
    assert data["id"] == admin_user["id"]
    assert data["email"] == admin_user["email"]
    assert data["role"] == "admin"
    assert "hub_assignments" in data
    assert data["full_name"] == "System Admin"


@pytest.mark.critical
@pytest.mark.integration
@pytest.mark.asyncio
async def test_logout_blacklists_access_token(
    auth_client: httpx.AsyncClient,
    admin_user: dict[str, str],
    admin_token: str,
) -> None:
    """Logout → blacklist access JTI → /me với token cũ → 401 TOKEN_REVOKED.

    T-03-04-refresh-replay mitigation: dùng access token sau logout sẽ bị
    Redis blacklist check trong get_current_user reject.
    """
    _ = admin_user
    # /me trước logout — 200.
    r1 = await auth_client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert r1.status_code == 200

    # Logout.
    r2 = await auth_client.post(
        "/api/auth/logout",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r2.status_code == 200, r2.text

    # /me sau logout — 401 TOKEN_REVOKED.
    r3 = await auth_client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert r3.status_code == 401, r3.text
    assert r3.json()["error"]["code"] == "TOKEN_REVOKED"


@pytest.mark.critical
@pytest.mark.integration
def test_pkcs8_key_format_verified() -> None:
    """AUTH-06 — keypair PKCS#8 format verified qua scripts/verify_jwt_format.sh.

    Bake AUTH-06 verify vào test suite — KHÔNG chỉ là manual plan task.
    Script exit 0 + stdout chứa "PKCS#8 OK" → format đúng.

    NOTE: script là bash — trên Windows cần git bash (đã có với git for windows).
    """
    result = subprocess.run(
        ["bash", "scripts/verify_jwt_format.sh"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"verify_jwt_format.sh fail (rc={result.returncode}). "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert "PKCS#8 OK" in result.stdout, (
        f"stdout không chứa 'PKCS#8 OK': {result.stdout!r}"
    )


@pytest.mark.critical
@pytest.mark.integration
@pytest.mark.asyncio
async def test_log_no_password_leak(
    auth_client: httpx.AsyncClient,
    admin_user: dict[str, str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """T-03-04-pii-log regression — password + refresh_token KHÔNG vào log.

    Sau khi login + logout, scan toàn bộ caplog records:
    - Plain password "Admin@123" KHÔNG xuất hiện.
    - Pattern JWT base64 "eyJ..." KHÔNG xuất hiện (refresh token leak).
    """
    caplog.set_level(logging.DEBUG)

    plain = admin_user["password"]
    # Login.
    r = await auth_client.post(
        "/api/auth/login",
        json={"email": admin_user["email"], "password": plain},
    )
    assert r.status_code == 200
    rt = r.json()["data"]["refresh_token"]
    access = r.json()["data"]["access_token"]

    # Logout (gửi cả refresh_token body để service blacklist cả 2).
    await auth_client.post(
        "/api/auth/logout",
        headers={"Authorization": f"Bearer {access}"},
        json={"refresh_token": rt},
    )

    # Aggregate tất cả log message.
    all_logs = " ".join(r.message for r in caplog.records)

    # Password plaintext KHÔNG được leak.
    assert plain not in all_logs, (
        f"PII leak — password '{plain}' xuất hiện trong log. "
        f"Snippet: {all_logs[:300]}"
    )
    # JWT token (eyJ... base64) KHÔNG được leak.
    jwt_pattern = re.compile(r"eyJ[A-Za-z0-9._-]{20,}")
    matches = jwt_pattern.findall(all_logs)
    assert not matches, (
        f"PII leak — JWT token xuất hiện trong log: {matches[:3]}"
    )
