"""MCPOAuthClientService — per-user pre-registered OAuth client (Phase 8.3 add-on).

3 thao tác:
- `get_or_create(user_id)`: lazy-create cặp client_id/secret cho user. Idempotent.
- `rotate(user_id)`: xoay client_secret + cập nhật rotated_at; giữ client_id.
  Cặp secret cũ vô hiệu ngay (Claude sẽ dùng secret mới khi gọi /token kế tiếp).
- `get_by_client_id(client_id)`: lookup ngược cho MCP internal endpoint.

`client_id` prefix `mcpu_` (mcp user) — phân biệt với DCR (SDK sinh prefix khác)
và CLI cũ `mcp_`. Hậu tố 16 byte urlsafe ≈ 128 bit entropy → đủ chống đoán.

`client_secret` 32 byte urlsafe ≈ 256 bit entropy — vượt khuyến nghị RFC 6749
§10.10. Plaintext trong DB (xem threat model migration 0004).

`redirect_uris` mặc định canonical Claude web callback (xác nhận qua test
fixture mcp_service/tests/test_oauth_provider.py). Cố định ở iteration 1 —
nếu Claude đổi URL, admin xoá row + lazy-create lại (defer endpoint sửa URL).
"""
from __future__ import annotations

import logging
import secrets
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mcp_oauth import MCPOAuthClient

logger = logging.getLogger(__name__)

# Canonical Claude web callback — xác nhận qua test fixture
# mcp_service/tests/test_oauth_provider.py constant REDIRECT.
_DEFAULT_REDIRECT_URI = "https://claude.ai/api/mcp/auth_callback"

# Default redirect_uris cho client mới — gồm Claude web + MCP Inspector
# (dev tool chính thức của Anthropic, default callback localhost:6274).
# Inspector cần redirect_uri này để OAuth flow hoạt động, nếu không SDK
# reject InvalidRedirectUriError ("not registered for client"). Mở rộng
# tại default → mọi client mới hỗ trợ cả 2 mà không cần config riêng.
_DEFAULT_REDIRECT_URIS = [
    _DEFAULT_REDIRECT_URI,
    "http://localhost:6274/oauth/callback",
    "http://127.0.0.1:6274/oauth/callback",
]


def _generate_client_id() -> str:
    """`mcpu_` + 22 ký tự urlsafe (~128 bit entropy)."""
    return f"mcpu_{secrets.token_urlsafe(16)}"


def _generate_client_secret() -> str:
    """43 ký tự urlsafe (~256 bit entropy) — vượt RFC 6749 §10.10."""
    return secrets.token_urlsafe(32)


class MCPOAuthClientService:
    """CRUD per-user pre-registered OAuth client.

    KHÔNG commit — caller (router qua `get_session`) commit ở cuối request.
    `flush()` đảm bảo server defaults (`created_at`, `client_id` unique
    constraint) được apply trước khi `refresh()` đọc lại.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_or_create(self, user_id: uuid.UUID) -> MCPOAuthClient:
        """Trả cặp hiện có của user; nếu chưa có thì sinh + persist + trả."""
        result = await self.db.execute(
            select(MCPOAuthClient).where(MCPOAuthClient.user_id == user_id)
        )
        client = result.scalar_one_or_none()
        if client is not None:
            return client

        client = MCPOAuthClient(
            user_id=user_id,
            client_id=_generate_client_id(),
            client_secret=_generate_client_secret(),
            redirect_uris=list(_DEFAULT_REDIRECT_URIS),
        )
        self.db.add(client)
        await self.db.flush()
        await self.db.refresh(client)
        logger.info(
            "mcp_oauth_client_created user_id=%s client_id=%s",
            user_id,
            client.client_id,
        )
        return client

    async def rotate(self, user_id: uuid.UUID) -> MCPOAuthClient | None:
        """Xoay `client_secret` + set `rotated_at = NOW()`.

        Trả `None` nếu user chưa có cặp — caller có thể lazy-create rồi tự
        coi rotate tương đương create.
        """
        result = await self.db.execute(
            select(MCPOAuthClient).where(MCPOAuthClient.user_id == user_id)
        )
        client = result.scalar_one_or_none()
        if client is None:
            return None

        client.client_secret = _generate_client_secret()
        client.rotated_at = datetime.now(timezone.utc)
        await self.db.flush()
        await self.db.refresh(client)
        logger.info(
            "mcp_oauth_client_rotated user_id=%s client_id=%s",
            user_id,
            client.client_id,
        )
        return client

    async def get_by_client_id(self, client_id: str) -> MCPOAuthClient | None:
        """Lookup ngược theo `client_id` — MCP internal endpoint dùng."""
        result = await self.db.execute(
            select(MCPOAuthClient).where(MCPOAuthClient.client_id == client_id)
        )
        return result.scalar_one_or_none()
