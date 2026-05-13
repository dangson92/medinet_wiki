"""Document model — REQ INGEST-04..06 + R4 mitigation (scanned PDF failed_unsupported).

Status enum (CHECK constraint, R4 + Pitfall #P8 watchdog):
- pending: vừa INSERT chưa xử lý
- processing: cocoindex đang chạy
- completed: xong, chunks ready
- failed: error tổng quát (timeout, embed fail, ...)
- failed_unsupported: format không support (scanned PDF, file > 50MB, ...)
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDMixin

DOCUMENT_STATUS_VALUES: tuple[str, ...] = (
    "pending",
    "processing",
    "completed",
    "failed",
    "failed_unsupported",
)


class Document(UUIDMixin, TimestampMixin, Base):
    """File upload — INGEST-04 + status enum (R4 + Pitfall #P8 mitigation)."""

    __tablename__ = "documents"

    hub_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("hubs.id", ondelete="CASCADE"),
        nullable=False,
    )
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    mime_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'pending'")
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_heartbeat: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    chunk_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'processing', 'completed', 'failed', 'failed_unsupported')",
            name="status_enum",
        ),
        Index("ix_documents_hub_id_status", "hub_id", "status"),
        Index("ix_documents_uploaded_by", "uploaded_by"),
    )
