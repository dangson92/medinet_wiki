"""Test cho oauth/provider.py (MedinetOAuthProvider) — Phase 8.3 (MCP-01).

MedinetOAuthProvider kế thừa OAuthAuthorizationServerProvider của SDK mcp 1.27.
Test phủ behavior:
- test_dcr_roundtrip: register_client -> get_client trả đúng (DCR — MCP-01).
- test_get_client_missing: get_client id lạ -> None.
- test_token_valid: token hợp lệ -> load_access_token trả AccessToken (critical).
- test_token_expired: token expires_at quá khứ -> load_access_token trả None (critical).
- test_token_wrong_scope: token không có trong store -> None.
- test_authorize_persists_pending: authorize -> URL có ?txn=, pending lưu đủ field.
- test_complete_authorization: pending -> code bind downstream JWT, pending bị xoá.
- test_exchange_authorization_code: code -> OAuthToken có refresh, code xoá sau exchange.
- test_exchange_refresh_token_rotates: refresh -> token mới, refresh cũ không dùng lại.
- test_revoke_token: revoke -> load_access_token trả None.

Phase 8.3 Plan 06 (gap closure SC3 — token lifecycle) thêm test phủ đường
replay / đồng thời / code hết hạn / PKCE cho các vá lỗi Plan 05:
- test_exchange_code_replay_rejected: dùng lại code đã exchange -> raise (CR-01).
- test_exchange_code_save_token_failure_no_replay: save_token lỗi -> code không
  còn để replay (CR-01).
- test_exchange_refresh_token_reuse_rejected: dùng lại refresh đã rotate -> raise
  (CR-02).
- test_complete_authorization_pending_expired: pending quá _PENDING_TTL -> raise.
- test_exchange_code_expired_rejected: code hết hạn -> raise (issue 3).
- test_pkce_challenge_persisted: code_challenge đi nguyên vẹn pending -> code (WR-01).
"""
from __future__ import annotations

import base64
import hashlib
import secrets
import time
from unittest.mock import patch

import pytest
from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    RefreshToken,
)
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken
from pydantic import AnyUrl

from mcp_app.oauth import MedinetOAuthProvider
from mcp_app.oauth.store import OAuthStoreError

from .conftest import fake_pending_authorize

ISSUER = "http://localhost:8190"
REDIRECT = "https://claude.ai/api/mcp/auth_callback"


def _make_provider(store, api_client=None) -> MedinetOAuthProvider:
    """Dựng provider với store thật + api_client (None khi test không gọi API)."""
    return MedinetOAuthProvider(
        store=store,
        api_client=api_client,
        issuer_url=ISSUER,
        access_token_ttl=3600,
        refresh_token_ttl=2592000,
    )


def _client_info(client_id: str = "client-test") -> OAuthClientInformationFull:
    """Dựng OAuthClientInformationFull tối thiểu cho test."""
    return OAuthClientInformationFull(
        client_id=client_id,
        redirect_uris=[AnyUrl(REDIRECT)],
        scope="wiki",
    )


def _login_data() -> dict:
    """JWT pair giả mô phỏng kết quả api_client.login()."""
    return {
        "access_token": "downstream-jwt-access",
        "refresh_token": "downstream-jwt-refresh",
        "expires_at": int(time.time()) + 900,
        "user": {"id": "u1", "email": "a@b.com", "role": "admin"},
    }


async def test_dcr_roundtrip(oauth_store) -> None:
    """register_client lưu client -> get_client đọc lại trả OAuthClientInformationFull."""
    provider = _make_provider(oauth_store)
    info = _client_info("dcr-client")
    await provider.register_client(info)

    loaded = await provider.get_client("dcr-client")
    assert loaded is not None
    assert loaded.client_id == "dcr-client"
    assert AnyUrl(REDIRECT) in loaded.redirect_uris


async def test_get_client_missing(oauth_store) -> None:
    """get_client với client_id không tồn tại -> None."""
    provider = _make_provider(oauth_store)
    assert await provider.get_client("khong-ton-tai") is None


@pytest.mark.critical
async def test_token_valid(oauth_store) -> None:
    """Token hợp lệ trong store -> load_access_token trả AccessToken đúng scopes."""
    provider = _make_provider(oauth_store)
    await oauth_store.save_token(
        access_token="oauth-access-valid",
        refresh_token="oauth-refresh-valid",
        client_id="client-test",
        scopes=["wiki"],
        downstream_jwt="jwt",
        downstream_refresh_token="jwt-r",
        user_payload={"id": "u1"},
        expires_at=int(time.time()) + 3600,
    )
    token = await provider.load_access_token("oauth-access-valid")
    assert isinstance(token, AccessToken)
    assert token.token == "oauth-access-valid"
    assert token.scopes == ["wiki"]
    assert token.client_id == "client-test"


@pytest.mark.critical
async def test_token_expired(oauth_store) -> None:
    """Token expires_at quá khứ -> load_access_token trả None."""
    provider = _make_provider(oauth_store)
    await oauth_store.save_token(
        access_token="oauth-access-expired",
        refresh_token="oauth-refresh-expired",
        client_id="client-test",
        scopes=["wiki"],
        downstream_jwt="jwt",
        downstream_refresh_token="jwt-r",
        user_payload={"id": "u1"},
        expires_at=int(time.time()) - 10,
    )
    assert await provider.load_access_token("oauth-access-expired") is None


@pytest.mark.critical
async def test_token_wrong_scope(oauth_store) -> None:
    """Token không có trong store -> load_access_token trả None."""
    provider = _make_provider(oauth_store)
    assert await provider.load_access_token("token-khong-ton-tai") is None


async def test_authorize_persists_pending(oauth_store) -> None:
    """authorize -> URL trả có ?txn=, store.load_pending(txn) trả bản ghi đủ field."""
    provider = _make_provider(oauth_store)
    await provider.register_client(_client_info())
    params = AuthorizationParams(
        state="client-state-xyz",
        scopes=["wiki"],
        code_challenge="challenge-abc",
        redirect_uri=AnyUrl(REDIRECT),
        redirect_uri_provided_explicitly=True,
    )
    url = await provider.authorize(_client_info(), params)
    assert url.startswith(f"{ISSUER}/login?txn=")
    txn = url.split("txn=", 1)[1]

    pending = await oauth_store.load_pending(txn)
    assert pending is not None
    assert pending["client_id"] == "client-test"
    assert pending["redirect_uri"] == REDIRECT
    assert pending["code_challenge"] == "challenge-abc"
    assert pending["client_state"] == "client-state-xyz"


async def test_complete_authorization(oauth_store) -> None:
    """complete_authorization: pending -> code bind downstream JWT, pending bị xoá."""
    provider = _make_provider(oauth_store)
    txn = await fake_pending_authorize(oauth_store, txn="txn-complete")

    code, redirect_uri, client_state = await provider.complete_authorization(
        txn, _login_data()
    )
    assert redirect_uri == REDIRECT
    assert client_state == "client-state-test"

    record = await oauth_store.load_auth_code(code)
    assert record is not None
    assert record["downstream_jwt"] == "downstream-jwt-access"
    assert record["downstream_refresh_token"] == "downstream-jwt-refresh"
    assert record["user_payload"]["email"] == "a@b.com"

    # Pending dùng 1 lần — đã xoá.
    assert await oauth_store.load_pending(txn) is None


async def test_complete_authorization_invalid_txn(oauth_store) -> None:
    """complete_authorization với txn không tồn tại -> raise OAuthStoreError."""
    provider = _make_provider(oauth_store)
    with pytest.raises(OAuthStoreError):
        await provider.complete_authorization("txn-khong-ton-tai", _login_data())


async def test_exchange_authorization_code(oauth_store) -> None:
    """exchange_authorization_code: code -> OAuthToken có refresh; code xoá sau exchange."""
    provider = _make_provider(oauth_store)
    txn = await fake_pending_authorize(oauth_store, txn="txn-exchange")
    code, _redirect, _state = await provider.complete_authorization(txn, _login_data())

    auth_code = await provider.load_authorization_code(_client_info(), code)
    assert isinstance(auth_code, AuthorizationCode)

    oauth_token = await provider.exchange_authorization_code(_client_info(), auth_code)
    assert isinstance(oauth_token, OAuthToken)
    assert oauth_token.access_token
    assert oauth_token.refresh_token

    # Code single-use — đã xoá khỏi store.
    assert await oauth_store.load_auth_code(code) is None
    # Token mới load được.
    loaded = await provider.load_access_token(oauth_token.access_token)
    assert loaded is not None


async def test_exchange_refresh_token_rotates(oauth_store) -> None:
    """exchange_refresh_token rotate token — refresh cũ không dùng lại được."""
    provider = _make_provider(oauth_store)
    txn = await fake_pending_authorize(oauth_store, txn="txn-refresh")
    code, _r, _s = await provider.complete_authorization(txn, _login_data())
    auth_code = await provider.load_authorization_code(_client_info(), code)
    first = await provider.exchange_authorization_code(_client_info(), auth_code)

    refresh_obj = await provider.load_refresh_token(_client_info(), first.refresh_token)
    assert isinstance(refresh_obj, RefreshToken)

    second = await provider.exchange_refresh_token(
        _client_info(), refresh_obj, ["wiki"]
    )
    assert second.access_token != first.access_token
    assert second.refresh_token != first.refresh_token

    # Refresh cũ không còn load được (đã rotate).
    assert await provider.load_refresh_token(_client_info(), first.refresh_token) is None
    # Access token cũ không còn hợp lệ.
    assert await provider.load_access_token(first.access_token) is None


async def test_revoke_token(oauth_store) -> None:
    """revoke_token -> load_access_token trả None."""
    provider = _make_provider(oauth_store)
    await oauth_store.save_token(
        access_token="oauth-access-revoke",
        refresh_token="oauth-refresh-revoke",
        client_id="client-test",
        scopes=["wiki"],
        downstream_jwt="jwt",
        downstream_refresh_token="jwt-r",
        user_payload={"id": "u1"},
        expires_at=int(time.time()) + 3600,
    )
    token = await provider.load_access_token("oauth-access-revoke")
    assert token is not None
    await provider.revoke_token(token)
    assert await provider.load_access_token("oauth-access-revoke") is None


async def test_exchange_code_replay_rejected(oauth_store) -> None:
    """Dùng lại authorization code đã exchange → raise OAuthStoreError (CR-01)."""
    provider = _make_provider(oauth_store)
    txn = await fake_pending_authorize(oauth_store, txn="txn-replay")
    code, _r, _s = await provider.complete_authorization(txn, _login_data())
    auth_code = await provider.load_authorization_code(_client_info(), code)
    await provider.exchange_authorization_code(_client_info(), auth_code)
    # Lần 2 cùng code — code đã bị claim nguyên tử.
    with pytest.raises(OAuthStoreError):
        await provider.exchange_authorization_code(_client_info(), auth_code)


async def test_exchange_code_save_token_failure_no_replay(oauth_store) -> None:
    """save_token lỗi giữa chừng → code đã bị claim, KHÔNG replay được (CR-01)."""
    provider = _make_provider(oauth_store)
    txn = await fake_pending_authorize(oauth_store, txn="txn-savefail")
    code, _r, _s = await provider.complete_authorization(txn, _login_data())
    auth_code = await provider.load_authorization_code(_client_info(), code)

    async def _boom(*args, **kwargs):
        raise OAuthStoreError("save_token lỗi mô phỏng")

    with patch.object(oauth_store, "save_token", side_effect=_boom):
        with pytest.raises(OAuthStoreError):
            await provider.exchange_authorization_code(_client_info(), auth_code)
    # Code đã bị claim_auth_code xoá TRƯỚC save_token — không còn để replay.
    assert await oauth_store.load_auth_code(code) is None
    with pytest.raises(OAuthStoreError):
        await provider.exchange_authorization_code(_client_info(), auth_code)


async def test_exchange_refresh_token_reuse_rejected(oauth_store) -> None:
    """Dùng lại refresh token đã rotate → raise OAuthStoreError reuse (CR-02)."""
    provider = _make_provider(oauth_store)
    txn = await fake_pending_authorize(oauth_store, txn="txn-reuse")
    code, _r, _s = await provider.complete_authorization(txn, _login_data())
    auth_code = await provider.load_authorization_code(_client_info(), code)
    first = await provider.exchange_authorization_code(_client_info(), auth_code)
    refresh_obj = await provider.load_refresh_token(
        _client_info(), first.refresh_token
    )
    # Rotate lần 1 — OK.
    await provider.exchange_refresh_token(_client_info(), refresh_obj, ["wiki"])
    # Rotate lần 2 với refresh_obj CŨ — reuse, phải raise.
    with pytest.raises(OAuthStoreError):
        await provider.exchange_refresh_token(_client_info(), refresh_obj, ["wiki"])


async def test_complete_authorization_pending_expired(oauth_store) -> None:
    """Pending transaction quá _PENDING_TTL → complete_authorization từ chối (WR-02)."""
    provider = _make_provider(oauth_store)
    txn = await fake_pending_authorize(
        oauth_store, txn="txn-expired", created_at=int(time.time()) - 700
    )
    with pytest.raises(OAuthStoreError):
        await provider.complete_authorization(txn, _login_data())


async def test_exchange_code_expired_rejected(oauth_store) -> None:
    """Authorization code hết hạn → exchange_authorization_code raise (issue 3)."""
    provider = _make_provider(oauth_store)
    expired_at = int(time.time()) - 10
    await oauth_store.save_auth_code(
        code="code-expired",
        client_id="client-test",
        code_payload={
            "scopes": ["wiki"],
            "redirect_uri": REDIRECT,
            "code_challenge": "challenge-test",
            "code_challenge_method": "S256",
        },
        downstream_jwt="jwt-a",
        downstream_refresh_token="jwt-r",
        user_payload={"id": 1, "email": "u@medinet.vn"},
        expires_at=expired_at,
    )
    auth_code = AuthorizationCode(
        code="code-expired",
        scopes=["wiki"],
        expires_at=float(expired_at),
        client_id="client-test",
        code_challenge="challenge-test",
        redirect_uri=AnyUrl(REDIRECT),
        redirect_uri_provided_explicitly=True,
    )
    with pytest.raises(OAuthStoreError):
        await provider.exchange_authorization_code(_client_info(), auth_code)


async def test_pkce_challenge_persisted(oauth_store) -> None:
    """code_challenge đi nguyên vẹn pending → authorization code — đầu vào PKCE verify của SDK (WR-01)."""
    verifier = secrets.token_urlsafe(32)
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .rstrip(b"=")
        .decode()
    )
    provider = _make_provider(oauth_store)
    txn = await fake_pending_authorize(
        oauth_store, txn="txn-pkce", code_challenge=challenge
    )
    code, _r, _s = await provider.complete_authorization(txn, _login_data())
    auth_code = await provider.load_authorization_code(_client_info(), code)
    # code_challenge phải đi nguyên vẹn pending → authorization code.
    # SDK mcp 1.27 (mcp.server.auth.handlers.token) verify base64url(sha256(
    # code_verifier)) == auth_code.code_challenge ở route /token — xác nhận
    # bằng inspect. Test này guard đầu vào cho bước verify đó.
    assert auth_code.code_challenge == challenge
