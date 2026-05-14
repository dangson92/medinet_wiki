"""phase4_documents_indexes

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-14 12:00:00.000000

Phase 4 — INGEST-06 (watchdog) prerequisite:
- Thêm composite index `ix_documents_status_last_heartbeat` trên (status, last_heartbeat)
  để watchdog Plan 04-05 query `WHERE status='processing' AND last_heartbeat < NOW() - INTERVAL '2 minutes'`
  có thể dùng index scan thay vì seq scan trên bảng documents (P8 mitigation).

KHÔNG add columns (Phase 2 baseline đã có last_heartbeat, attempts, error_message).
"""
from __future__ import annotations

from typing import Sequence, Union  # noqa: UP035 — match Alembic template + 0001 baseline style

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: Union[str, None] = "0001"  # noqa: UP007 — Alembic template style (match 0001)
branch_labels: Union[str, Sequence[str], None] = None  # noqa: UP007
depends_on: Union[str, Sequence[str], None] = None  # noqa: UP007


def upgrade() -> None:
    """Thêm index composite cho watchdog query."""
    op.create_index(
        "ix_documents_status_last_heartbeat",
        "documents",
        ["status", "last_heartbeat"],
        unique=False,
    )


def downgrade() -> None:
    """Drop index composite."""
    op.drop_index("ix_documents_status_last_heartbeat", table_name="documents")
