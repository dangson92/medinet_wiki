"""MCPOAuthClient — per-user pre-registered OAuth client (Phase 8.3 add-on).

Mỗi Medinet user có 1 cặp client_id/secret pre-registered cho dialog
"Add custom connector" → Advanced của Claude web. Bind cứng: client_id Y
gắn user_id Y — MCP service từ chối nếu user login OAuth ≠ owner cặp.

Threat model `client_secret` plaintext: xem docstring migration 0004.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MCPOAuthClient(Base):
    """Per-user pre-registered OAuth client cho Claude web Advanced.

    PRIMARY KEY = `user_id` → unique per user; xoá user qua CASCADE xoá cặp.
    `client_id` UNIQUE để lookup nhanh từ MCP service.
    """

    __tablename__ = "mcp_oauth_clients"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    client_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    client_secret: Mapped[str] = mapped_column(Text, nullable=False)
    # JSONB list[str] — Claude web có thể có 1-2 callback URL.
    redirect_uris: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )
    rotated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
