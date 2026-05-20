"""Test per-user pre-registered OAuth client + bind enforcement (Phase 8.3 add-on).

Coverage:

**get_client fallback API**
- `test_get_client_fallback_api_returns_pre_registered` — local store miss,
  API trả 200 với metadata → provider wrap thành OAuthClientInformationFull.
- `test_get_client_no_internal_token_skips_fallback` — `internal_token=""` →
  KHÔNG gọi API (tránh leak shared secret rỗng) → None.
- `test_get_client_api_404_returns_none` — API trả 404 → None (không raise).
- `test_get_client_dcr_local_takes_priority` — local hit → KHÔNG gọi API.

**complete_authorization bind cứng**
- `test_bind_allows_when_login_user_matches_owner` — owner_user_id == login
  user.id → code phát ra OK (behavior cũ giữ nguyên).
- `test_bind_rejects_when_login_user_mismatches_owner` — owner != login user
  → raise BindMismatchError, pending KHÔNG bị xoá (cho user retry login khác).
- `test_bind_skips_when_client_is_dcr` — client KHÔNG có entry ở API (DCR) →
  bind skip, code phát ra OK (legacy DCR vẫn work).
"""
from __future__ import annotations

import httpx
import pytest
import respx
from pydantic import AnyUrl

from mcp_app.api_client import ApiClient
from mcp_app.oauth.provider import BindMismatchError, MedinetOAuthProvider
from tests.conftest import fake_pending_authorize

API_BASE = "http://api-test"
INTERNAL_TOKEN = "test-internal-secret"
ISSUER = "http://localhost:8190"
REDIRECT = "https://claude.ai/api/mcp/auth_callback"
PER_USER_CLIENT_ID = "mcpu_per-user-fixture"


def _make_provider(oauth_store, api_client, *, internal_token=INTERNAL_TOKEN):
    """Provider mở rộng — kèm api_client + internal_token cho Phase 8.3 per-user."""
    return MedinetOAuthProvider(
        store=oauth_store,
        api_client=api_client,
        issuer_url=ISSUER,
        access_token_ttl=3600,
        refresh_token_ttl=2592000,
        internal_token=internal_token,
    )


def _mock_internal_lookup(
    *,
    client_id: str,
    owner_user_id: str,
    owner_email: str = "owner@medinet.vn",
    client_secret: str = "test-secret",
) -> None:
    """Cấu hình respx route trả 200 cho lookup client_id qua internal endpoint."""
    respx.get(f"{API_BASE}/api/internal/mcp/clients/{client_id}").mock(
        return_value=httpx.Response(
            200,
            json={
                "success": True,
                "data": {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "redirect_uris": [REDIRECT],
                    "owner_user_id": owner_user_id,
                    "owner_email": owner_email,
                },
                "error": None,
                "meta": None,
            },
        )
    )


def _login_data(user_id: str, email: str = "login@medinet.vn") -> dict:
    """Mô phỏng kết quả `api_client.login()` — dict downstream JWT pair."""
    import time

    return {
        "access_token": "downstream-access",
        "refresh_token": "downstream-refresh",
        "expires_at": int(time.time()) + 900,
        "user": {"id": user_id, "email": email, "role": "admin"},
    }


# ─── get_client fallback ───────────────────────────────────────────────────


@respx.mock
async def test_get_client_fallback_api_returns_pre_registered(
    oauth_store,
) -> None:
    """Local miss + API 200 → trả OAuthClientInformationFull khớp metadata."""
    _mock_internal_lookup(
        client_id=PER_USER_CLIENT_ID,
        owner_user_id="user-1",
        client_secret="secret-fallback",
    )
    async with ApiClient(API_BASE) as api_client:
        provider = _make_provider(oauth_store, api_client)
        loaded = await provider.get_client(PER_USER_CLIENT_ID)
    assert loaded is not None
    assert loaded.client_id == PER_USER_CLIENT_ID
    assert loaded.client_secret == "secret-fallback"
    assert loaded.scope == "wiki"
    assert loaded.token_endpoint_auth_method == "client_secret_post"
    assert AnyUrl(REDIRECT) in loaded.redirect_uris


@respx.mock
async def test_get_client_no_internal_token_skips_fallback(oauth_store) -> None:
    """internal_token rỗng → KHÔNG gọi API, trả None."""
    # KHÔNG mock API — nếu provider gọi sẽ là RequestError + ApiServerError.
    async with ApiClient(API_BASE) as api_client:
        provider = _make_provider(oauth_store, api_client, internal_token="")
        result = await provider.get_client("mcpu_anything")
    assert result is None
    # Đảm bảo provider KHÔNG gọi route — respx không có call nào.
    assert len(respx.calls) == 0


@respx.mock
async def test_get_client_api_404_returns_none(oauth_store) -> None:
    """API trả 404 (chưa registered) → provider trả None, không raise."""
    respx.get(f"{API_BASE}/api/internal/mcp/clients/mcpu_missing").mock(
        return_value=httpx.Response(
            404,
            json={
                "success": False,
                "data": None,
                "error": {"code": "NOT_FOUND", "message": "Client không tồn tại"},
                "meta": None,
            },
        )
    )
    async with ApiClient(API_BASE) as api_client:
        provider = _make_provider(oauth_store, api_client)
        result = await provider.get_client("mcpu_missing")
    assert result is None


@respx.mock
async def test_get_client_dcr_local_takes_priority(oauth_store) -> None:
    """Local store hit → trả ngay, KHÔNG gọi API (tránh lookup không cần)."""
    # Seed DCR client trong local store.
    from mcp.shared.auth import OAuthClientInformationFull

    info = OAuthClientInformationFull(
        client_id="dcr-local",
        redirect_uris=[AnyUrl(REDIRECT)],
        scope="wiki",
    )
    await oauth_store.save_client("dcr-local", info.model_dump(mode="json"))

    async with ApiClient(API_BASE) as api_client:
        provider = _make_provider(oauth_store, api_client)
        loaded = await provider.get_client("dcr-local")
    assert loaded is not None
    assert loaded.client_id == "dcr-local"
    # Đảm bảo provider KHÔNG fallback API.
    assert len(respx.calls) == 0


# ─── complete_authorization bind cứng ──────────────────────────────────────


@respx.mock
async def test_bind_allows_when_login_user_matches_owner(oauth_store) -> None:
    """Login user.id == owner_user_id → code phát ra OK."""
    _mock_internal_lookup(
        client_id=PER_USER_CLIENT_ID, owner_user_id="user-owner-1"
    )
    txn = await fake_pending_authorize(
        oauth_store, txn="txn-bind-allow", client_id=PER_USER_CLIENT_ID
    )

    async with ApiClient(API_BASE) as api_client:
        provider = _make_provider(oauth_store, api_client)
        code, redirect_uri, _state = await provider.complete_authorization(
            txn, _login_data(user_id="user-owner-1")
        )

    assert redirect_uri == REDIRECT
    record = await oauth_store.load_auth_code(code)
    assert record is not None
    assert record["client_id"] == PER_USER_CLIENT_ID


@respx.mock
async def test_bind_rejects_when_login_user_mismatches_owner(
    oauth_store,
) -> None:
    """Login user.id ≠ owner_user_id → raise BindMismatchError; KHÔNG phát code."""
    _mock_internal_lookup(
        client_id=PER_USER_CLIENT_ID, owner_user_id="user-owner-1"
    )
    txn = await fake_pending_authorize(
        oauth_store, txn="txn-bind-reject", client_id=PER_USER_CLIENT_ID
    )

    async with ApiClient(API_BASE) as api_client:
        provider = _make_provider(oauth_store, api_client)
        with pytest.raises(BindMismatchError):
            await provider.complete_authorization(
                txn, _login_data(user_id="user-attacker-2")
            )

    # Pending VẪN còn → user retry login khác (đúng tài khoản) là được.
    pending = await oauth_store.load_pending(txn)
    assert pending is not None


@respx.mock
async def test_bind_skips_when_client_is_dcr(oauth_store) -> None:
    """Client KHÔNG có entry ở API (DCR / legacy) → bind skip, code phát ra OK."""
    # API trả 404 cho client_id "dcr-legacy" → bind skip.
    respx.get(f"{API_BASE}/api/internal/mcp/clients/dcr-legacy").mock(
        return_value=httpx.Response(
            404,
            json={
                "success": False,
                "data": None,
                "error": {"code": "NOT_FOUND", "message": "Client không tồn tại"},
                "meta": None,
            },
        )
    )
    txn = await fake_pending_authorize(
        oauth_store, txn="txn-dcr-skip", client_id="dcr-legacy"
    )

    async with ApiClient(API_BASE) as api_client:
        provider = _make_provider(oauth_store, api_client)
        # User bất kỳ login OK — bind không enforce cho DCR.
        code, _, _ = await provider.complete_authorization(
            txn, _login_data(user_id="any-user")
        )
    record = await oauth_store.load_auth_code(code)
    assert record is not None
