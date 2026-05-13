"""SQLAlchemy mixin tái dùng cho mọi model M2.

Mixin pattern (Declarative + `mapped_column`):
- `UUIDMixin` — PK uuid4 với server default `gen_random_uuid()` (cần ext pgcrypto).
- `TimestampMixin` — `created_at` NOT NULL NOW(), `updated_at` nullable.

Sử dụng:
    class User(UUIDMixin, TimestampMixin, Base):
        __tablename__ = "users"
        email: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column


class UUIDMixin:
    """Primary key UUID4 — server-side default qua pgcrypto.gen_random_uuid()."""

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )


class TimestampMixin:
    """Audit timestamps — created_at NOT NULL NOW(), updated_at nullable."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
