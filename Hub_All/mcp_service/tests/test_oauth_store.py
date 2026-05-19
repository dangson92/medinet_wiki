"""Test cho oauth/store.py (OAuthStore) — Phase 8.3 Plan 01 (MCP-01).

Phủ CRUD roundtrip 4 bảng SQLite của OAuth state store:
- test_init_schema_idempotent     — init_schema() gọi lần 2 không lỗi.
- test_client_roundtrip           — save_client → get_client; id lạ → None.
- test_auth_code_roundtrip_single_use — save → load đủ field; delete → None.
- test_token_roundtrip            — save_token → load_token có downstream_jwt.
- test_load_token_by_refresh      — tìm token theo refresh_token.
- test_update_downstream_jwt_rotates_both — update đổi CẢ jwt + refresh (Pitfall 5).
- test_delete_token               — delete_token → load_token None (revoke).
- test_pending_roundtrip          — save_pending → load_pending; delete → None.
- test_pending_helper_seeds       — helper conftest fake_pending_authorize hoạt động.
- test_cleanup_expired            — dọn code hết hạn + pending bỏ dở >600s.
"""
from __future__ import annotations

import time

import pytest

from tests.conftest import fake_pending_authorize


async def test_init_schema_idempotent(oauth_store) -> None:
    """init_schema() gọi lần 2 không lỗi (CREATE TABLE IF NOT EXISTS)."""
    await oauth_store.init_schema()
    await oauth_store.init_schema()


async def test_client_roundtrip(oauth_store) -> None:
    """save_client → get_client trả đúng metadata; client_id lạ → None."""
    metadata = {"redirect_uris": ["https://claude.ai/cb"], "scope": "wiki"}
    await oauth_store.save_client("client-abc", metadata)

    loaded = await oauth_store.get_client("client-abc")
    assert loaded == metadata

    assert await oauth_store.get_client("không-tồn-tại") is None


async def test_auth_code_roundtrip_single_use(oauth_store) -> None:
    """save_auth_code → load_auth_code đủ field downstream; delete → None."""
    await oauth_store.save_auth_code(
        code="code-1",
        client_id="client-abc",
        code_payload={"redirect_uri": "https://claude.ai/cb", "scopes": ["wiki"]},
        downstream_jwt="jwt-access-xyz",
        downstream_refresh_token="jwt-refresh-xyz",
        user_payload={"id": 7, "email": "u@medinet.vn"},
        expires_at=int(time.time()) + 600,
    )

    loaded = await oauth_store.load_auth_code("code-1")
    assert loaded is not None
    assert loaded["client_id"] == "client-abc"
    assert loaded["downstream_jwt"] == "jwt-access-xyz"
    assert loaded["downstream_refresh_token"] == "jwt-refresh-xyz"
    assert loaded["code_payload"]["scopes"] == ["wiki"]
    assert loaded["user_payload"]["id"] == 7

    await oauth_store.delete_auth_code("code-1")
    assert await oauth_store.load_auth_code("code-1") is None


@pytest.mark.critical
async def test_token_roundtrip(oauth_store) -> None:
    """save_token → load_token trả record với downstream_jwt + expires_at."""
    await oauth_store.save_token(
        access_token="oauth-access-1",
        refresh_token="oauth-refresh-1",
        client_id="client-abc",
        scopes=["wiki"],
        downstream_jwt="jwt-access-xyz",
        downstream_refresh_token="jwt-refresh-xyz",
        user_payload={"id": 7},
        expires_at=int(time.time()) + 3600,
    )

    loaded = await oauth_store.load_token("oauth-access-1")
    assert loaded is not None
    assert loaded["downstream_jwt"] == "jwt-access-xyz"
    assert loaded["downstream_refresh_token"] == "jwt-refresh-xyz"
    assert loaded["scopes"] == ["wiki"]
    assert loaded["expires_at"] > int(time.time())

    assert await oauth_store.load_token("token-lạ") is None


async def test_load_token_by_refresh(oauth_store) -> None:
    """Lưu token có refresh → load_token_by_refresh tìm được."""
    await oauth_store.save_token(
        access_token="oauth-access-2",
        refresh_token="oauth-refresh-2",
        client_id="client-abc",
        scopes=["wiki"],
        downstream_jwt="jwt-a",
        downstream_refresh_token="jwt-r",
        user_payload={"id": 1},
        expires_at=int(time.time()) + 3600,
    )

    loaded = await oauth_store.load_token_by_refresh("oauth-refresh-2")
    assert loaded is not None
    assert loaded["access_token"] == "oauth-access-2"

    assert await oauth_store.load_token_by_refresh("refresh-lạ") is None


@pytest.mark.critical
async def test_update_downstream_jwt_rotates_both(oauth_store) -> None:
    """update_downstream_jwt ghi đè CẢ downstream_jwt và downstream_refresh_token.

    Regression Pitfall 5 — refresh rotation: lưu thiếu refresh mới → fail lần sau.
    """
    await oauth_store.save_token(
        access_token="oauth-access-3",
        refresh_token="oauth-refresh-3",
        client_id="client-abc",
        scopes=["wiki"],
        downstream_jwt="jwt-old",
        downstream_refresh_token="refresh-old",
        user_payload={"id": 2},
        expires_at=int(time.time()) + 3600,
    )

    await oauth_store.update_downstream_jwt(
        "oauth-access-3", new_jwt="jwt-new", new_refresh="refresh-new"
    )

    loaded = await oauth_store.load_token("oauth-access-3")
    assert loaded is not None
    assert loaded["downstream_jwt"] == "jwt-new"
    assert loaded["downstream_refresh_token"] == "refresh-new"


async def test_delete_token(oauth_store) -> None:
    """delete_token → load_token trả None (hỗ trợ revoke)."""
    await oauth_store.save_token(
        access_token="oauth-access-4",
        refresh_token=None,
        client_id="client-abc",
        scopes=["wiki"],
        downstream_jwt="jwt-a",
        downstream_refresh_token="jwt-r",
        user_payload={"id": 3},
        expires_at=int(time.time()) + 3600,
    )
    assert await oauth_store.load_token("oauth-access-4") is not None

    await oauth_store.delete_token("oauth-access-4")
    assert await oauth_store.load_token("oauth-access-4") is None


async def test_pending_roundtrip(oauth_store) -> None:
    """save_pending → load_pending trả đủ field authorize; delete → None."""
    now = int(time.time())
    await oauth_store.save_pending(
        txn="txn-1",
        client_id="client-abc",
        redirect_uri="https://claude.ai/api/mcp/auth_callback",
        code_challenge="pkce-challenge",
        code_challenge_method="S256",
        client_state="client-state-99",
        scopes=["wiki"],
        created_at=now,
    )

    loaded = await oauth_store.load_pending("txn-1")
    assert loaded is not None
    assert loaded["client_id"] == "client-abc"
    assert loaded["redirect_uri"] == "https://claude.ai/api/mcp/auth_callback"
    assert loaded["code_challenge"] == "pkce-challenge"
    assert loaded["code_challenge_method"] == "S256"
    assert loaded["client_state"] == "client-state-99"
    assert loaded["scopes"] == ["wiki"]
    assert loaded["created_at"] == now

    await oauth_store.delete_pending("txn-1")
    assert await oauth_store.load_pending("txn-1") is None


async def test_pending_helper_seeds(oauth_store) -> None:
    """Helper conftest fake_pending_authorize seed được oauth_pending (cho Plan 02)."""
    txn = await fake_pending_authorize(oauth_store)
    assert txn == "txn-test"

    loaded = await oauth_store.load_pending("txn-test")
    assert loaded is not None
    assert loaded["client_id"] == "client-test"
    assert loaded["code_challenge"] == "challenge-test"
    assert loaded["scopes"] == ["wiki"]


async def test_cleanup_expired(oauth_store) -> None:
    """cleanup_expired dọn code hết hạn + pending bỏ dở >600s, giữ phần còn hạn."""
    now = int(time.time())

    # Code hết hạn (quá khứ) + code còn hạn (tương lai).
    await oauth_store.save_auth_code(
        code="code-expired",
        client_id="c",
        code_payload={},
        downstream_jwt="j",
        downstream_refresh_token="r",
        user_payload={},
        expires_at=now - 10,
    )
    await oauth_store.save_auth_code(
        code="code-valid",
        client_id="c",
        code_payload={},
        downstream_jwt="j",
        downstream_refresh_token="r",
        user_payload={},
        expires_at=now + 600,
    )
    # Pending bỏ dở quá cũ (>600s) + pending mới.
    await fake_pending_authorize(
        oauth_store, txn="txn-old", created_at=now - 700
    )
    await fake_pending_authorize(
        oauth_store, txn="txn-fresh", created_at=now
    )

    await oauth_store.cleanup_expired(now)

    assert await oauth_store.load_auth_code("code-expired") is None
    assert await oauth_store.load_auth_code("code-valid") is not None
    assert await oauth_store.load_pending("txn-old") is None
    assert await oauth_store.load_pending("txn-fresh") is not None
