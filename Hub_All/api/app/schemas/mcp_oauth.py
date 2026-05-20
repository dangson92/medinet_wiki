"""Schemas cho MCP OAuth client endpoints — request/response shape.

User-facing: `GET/POST /api/mcp/my-oauth-client[/rotate]` → MCPOAuthClientResponse.
Internal:    `GET /api/internal/mcp/clients/{id}` → MCPOAuthClientInternal
             (kèm `owner_user_id` cho MCP bind enforcement).
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class MCPOAuthClientResponse(BaseModel):
    """Response shape user-facing endpoints — user copy dán vào dialog Claude.

    `client_secret` trả plaintext (xem threat model migration 0004). User
    rotate khi nghi rò rỉ — `client_id` giữ nguyên, secret đổi.
    """

    client_id: str
    client_secret: str
    redirect_uris: list[str]
    created_at: datetime
    rotated_at: datetime | None = None


class MCPOAuthClientInternal(BaseModel):
    """Response shape `/api/internal/mcp/clients/{id}` — chỉ MCP service gọi.

    Thêm `owner_user_id` (UUID dạng string) + `owner_email` để MCP:
    - So sánh user login OAuth ≠ owner → reject (bind cứng).
    - Log audit thao tác liên quan client.
    """

    client_id: str
    client_secret: str
    redirect_uris: list[str]
    owner_user_id: str
    owner_email: str
