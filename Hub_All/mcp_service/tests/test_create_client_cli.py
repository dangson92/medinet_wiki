"""Smoke test cho CLI sinh pre-registered OAuth client.

Phase 8.3 add-on (sau verification): CLI `python -m mcp_app.oauth.create_client`
sinh + đăng ký credentials thủ công cho Claude web "Add custom connector"
(Advanced). Test này phủ:

- Generator helper sinh prefix `mcp_` + đủ entropy.
- `_register()` ghi đúng row vào bảng `oauth_clients` của OAuthStore với
  metadata round-trip được vào `OAuthClientInformationFull` của SDK — đảm
  bảo provider `get_client()` sẽ load lại được mà không lỗi schema.
"""
from __future__ import annotations

from mcp.shared.auth import OAuthClientInformationFull

from mcp_app.oauth.create_client import (
    _DEFAULT_REDIRECT_URI,
    _generate_client_id,
    _generate_client_secret,
    _register,
)
from mcp_app.oauth.store import OAuthStore


def test_generate_client_id_prefixed_with_entropy() -> None:
    """`client_id` luôn bắt đầu `mcp_` + hậu tố ≥ 20 char urlsafe (~128 bit)."""
    cid = _generate_client_id()
    assert cid.startswith("mcp_")
    # secrets.token_urlsafe(16) → ≥ 22 ký tự urlsafe.
    assert len(cid) >= 4 + 20

    # Không trùng giữa 2 lần sinh — sanity check entropy.
    assert _generate_client_id() != cid


def test_generate_client_secret_high_entropy() -> None:
    """`client_secret` ≥ 32 ký tự urlsafe (~256 bit, vượt RFC 6749 §10.10)."""
    sec = _generate_client_secret()
    assert len(sec) >= 32
    # Không trùng — entropy thật chứ không hằng số.
    assert _generate_client_secret() != sec


async def test_register_writes_oauth_client_row(tmp_path) -> None:
    """`_register()` INSERT row vào oauth_clients với metadata khớp schema SDK.

    Round-trip qua `OAuthStore.get_client()` + `OAuthClientInformationFull.
    model_validate()` mô phỏng đúng đường đi của `MedinetOAuthProvider.
    get_client()` lúc Claude web exchange code → token.
    """
    db_path = str(tmp_path / "oauth.db")

    client_id, client_secret = await _register(
        db_path=db_path,
        redirect_uris=[_DEFAULT_REDIRECT_URI],
        client_name="Claude Web Connector",
    )

    assert client_id.startswith("mcp_")
    assert len(client_secret) >= 32

    # Đọc lại metadata + validate qua model SDK — provider sẽ chạy đúng
    # đường này khi get_client(); fail = CLI sinh metadata sai schema.
    store = OAuthStore(db_path)
    await store.init_schema()
    try:
        metadata = await store.get_client(client_id)
    finally:
        await store.aclose()

    assert metadata is not None
    info = OAuthClientInformationFull.model_validate(metadata)
    assert info.client_id == client_id
    assert info.client_secret == client_secret
    assert info.scope == "wiki"
    assert info.redirect_uris is not None and len(info.redirect_uris) == 1
    # AnyUrl có thể chuẩn hoá URL — so chuỗi mềm, chỉ cần chứa path callback.
    assert "claude.ai/api/mcp/auth_callback" in str(info.redirect_uris[0])
    assert "authorization_code" in info.grant_types
    assert "refresh_token" in info.grant_types
    assert info.token_endpoint_auth_method == "client_secret_post"
