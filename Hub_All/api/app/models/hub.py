"""Hub registry model — REQ HUB-01.

Drop col legacy M1 (D3 — gỡ ChromaDB collection reference).
"""
from __future__ import annotations

from sqlalchemy import Boolean, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDMixin


class Hub(UUIDMixin, TimestampMixin, Base):
    """Hub registry — 3 hub mặc định: hub_y_te, hub_duoc, hub_hcns."""

    __tablename__ = "hubs"

    slug: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("TRUE")
    )
