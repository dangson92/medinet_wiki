"""Chunk model — REQ INGEST-03 + R1/R7/P17 mitigations.

Schema choice:
- vector Vector(1536) — pin dim 1536 cho hot-swap OpenAI/Gemini không re-embed (R7).
- content_hash BYTEA — cocoindex content-hash diff (incremental re-embed, D-1).
- HNSW index USING hnsw (vector vector_cosine_ops) — P17 mandatory cosine (KHÔNG L2).
- FK CASCADE chain: hubs -> documents -> chunks (T-02-01, T-02-02 mitigations).
- Chỉ inherit UUIDMixin (KHÔNG dùng audit timestamps mixin): chunks immutable,
  content đổi = chunk_id mới qua cocoindex generate_id, chỉ cần created_at thủ công.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import UUIDMixin
from app.db.types import Vector


class Chunk(UUIDMixin, Base):
    """Chunk semantic của document — pgvector(1536) + HNSW cosine index.

    Immutable: nội dung đổi = chunk_id mới (cocoindex generate_id determinism).
    """

    __tablename__ = "chunks"

    document_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    hub_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("hubs.id", ondelete="CASCADE"),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    heading_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    page_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    vector: Mapped[list[float] | None] = mapped_column(Vector(1536), nullable=True)
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )

    __table_args__ = (
        Index(
            "ix_chunks_vector_hnsw",
            "vector",
            postgresql_using="hnsw",
            postgresql_ops={"vector": "vector_cosine_ops"},
        ),
        Index("ix_chunks_hub_id_document_id", "hub_id", "document_id"),
        Index("ix_chunks_content_hash", "content_hash"),
    )
