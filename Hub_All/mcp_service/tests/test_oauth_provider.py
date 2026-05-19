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
"""
from __future__ import annotations

import time

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
