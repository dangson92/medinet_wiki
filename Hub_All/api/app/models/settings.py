"""Settings + API key model — REQ ASK-04 (rag-config) + AUX-02 (api key mgmt).

T-02-04 mitigation: api_keys.key_hash (AES-GCM encrypted at rest, KHÔNG plaintext).
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    PrimaryKeyConstraint,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDMixin


class Setting(Base):
    """Key-value config table — ASK-04 hot-swap rag-config + system settings.

    Keys ví dụ:
    - `rag.llm_provider` = `{"provider": "openai", "model": "gpt-4o-mini"}`
    - `rag.embedding_provider` = `{"provider": "openai", "model": "text-embedding-3-small", "dim": 1536}`
    """

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(Text, nullable=False)
    value: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )

    __table_args__ = (PrimaryKeyConstraint("key", name="pk_settings"),)


class ApiKey(UUIDMixin, TimestampMixin, Base):
    """API key cho external integration (AUX-02) — T-02-04 hash + prefix UX."""

    __tablename__ = "api_keys"

    name: Mapped[str] = mapped_column(Text, nullable=False)
    key_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    key_prefix: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    hub_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("hubs.id", ondelete="CASCADE"),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("TRUE")
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Phase 5 (migration 0003) — contract frontend APIKeyAPI.
    permissions: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    allowed_hub_ids: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True
    )
    rate_limit: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("100")
    )
