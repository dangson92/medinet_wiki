"""document_versions

Revision ID: 0007
Revises: 0006
Create Date: 2026-05-26 10:00:00.000000

Phase 5 Plan 05-01 VER-01 — Tạo bảng document_versions cho feature
version-history (frontend đã ship trước; BE catch-up gap).

Schema 15 cột match exact frontend DocumentVersionAPI interface
(frontend/src/services/api.ts:599-615) + 1 UNIQUE (document_id, version_number)
+ 1 INDEX (document_id) + 1 CHECK (change_type IN 4 value).

Idempotent strategy (D-V3.1-Phase5-G LOCKED — carry forward Plan 01-01 introspect):
- STEP 1: check document_versions table KHÔNG tồn tại (skip CREATE TABLE nếu re-run).
- STEP 2: check documents table tồn tại (precondition FK target — fail loud nếu schema baseline missing).
- STEP 3: check users table tồn tại (precondition FK target).
- STEP 4: CREATE TABLE document_versions với 15 cột + 1 UNIQUE + 1 INDEX + 1 CHECK.

Mitigations:
- T-05-01-01 Integrity — FK document_id ON DELETE CASCADE: xoá document → cascade
  xoá versions (KHÔNG orphan row). FK created_by ON DELETE SET NULL: xoá user →
  version row preserve forensic (created_by=NULL acceptable cho audit trail).
- T-05-01-02 Tampering — CHECK constraint change_type IN 4 value enforce schema
  (Plan 05-02 service raise nếu invalid; Plan 05-03 Pydantic Literal type validate).
- T-05-01-03 DoS — UNIQUE (document_id, version_number) prevent duplicate INSERT
  race condition (Plan 05-02 retry-safe atomic transaction).
- R-V3.1-1 mitigation — downgrade defensive COUNT(*) log + DROP TABLE atomic.

Carry forward Plan 01-01 v3.1 introspect + Plan 04-01 v3.0 introspect (idempotent
re-run safety + tên constraint introspect runtime).
"""
from __future__ import annotations

from typing import (  # noqa: UP035 — match Alembic baseline 0001-0006
    Sequence,
    Union,
)

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0007"
down_revision: Union[str, None] = "0006"  # noqa: UP007 — match baseline
branch_labels: Union[str, Sequence[str], None] = None  # noqa: UP007
depends_on: Union[str, Sequence[str], None] = None  # noqa: UP007


def upgrade() -> None:
    """VER-01 — CREATE TABLE document_versions với 15 cột + idempotent introspect."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    existing_tables = set(inspector.get_table_names())

    # ============================================================
    # STEP 1 — Idempotent guard: skip nếu document_versions đã tồn tại.
    # ============================================================
    if "document_versions" in existing_tables:
        print(
            "[0007] SKIP CREATE TABLE document_versions — table đã tồn tại "
            "(idempotent re-run safe)"
        )
        return

    # ============================================================
    # STEP 2 — Precondition: documents table tồn tại (FK target).
    # ============================================================
    if "documents" not in existing_tables:
        raise RuntimeError(
            "Migration 0007 requires documents table (FK target). "
            "Run `alembic upgrade head` sequential từ 0001 baseline."
        )

    # ============================================================
    # STEP 3 — Precondition: users table tồn tại (FK target created_by).
    # ============================================================
    if "users" not in existing_tables:
        raise RuntimeError(
            "Migration 0007 requires users table (FK target created_by). "
            "Run `alembic upgrade head` sequential từ 0001 baseline."
        )

    # ============================================================
    # STEP 4 — CREATE TABLE document_versions (15 cột + UNIQUE + INDEX + CHECK).
    # ============================================================
    op.create_table(
        "document_versions",
        # 1) id UUID PK
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        # 2) document_id UUID FK ON DELETE CASCADE
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # 3) version_number INT monotonic per document_id
        sa.Column("version_number", sa.Integer(), nullable=False),
        # 4) is_original BOOLEAN — true khi version_number == 1
        sa.Column(
            "is_original",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        # 5) name TEXT — filename snapshot
        sa.Column("name", sa.Text(), nullable=False),
        # 6) file_type TEXT — mime type or extension
        sa.Column("file_type", sa.Text(), nullable=False),
        # 7) file_size BIGINT — bytes
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        # 8) file_path TEXT — UUID-based FileStore path
        sa.Column("file_path", sa.Text(), nullable=False),
        # 9) file_hash TEXT NULL — SHA-256 hex 64-char (D-V3.1-Phase5-A dedupe key)
        sa.Column("file_hash", sa.Text(), nullable=True),
        # 10) extractor_used TEXT NULL — snapshot extractor name
        sa.Column("extractor_used", sa.Text(), nullable=True),
        # 11) chunk_count INT DEFAULT 0 — count only (D-V3.1-Phase5-B NO chunk snapshot)
        sa.Column(
            "chunk_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        # 12) change_type TEXT CHECK IN 4 value
        sa.Column("change_type", sa.Text(), nullable=False),
        # 13) change_note TEXT NULL — optional human note
        sa.Column("change_note", sa.Text(), nullable=True),
        # 14) created_by UUID FK ON DELETE SET NULL — forensic preserve
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # 15) created_at TIMESTAMPTZ DEFAULT NOW()
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        # UNIQUE (document_id, version_number) — prevent race duplicate
        sa.UniqueConstraint(
            "document_id",
            "version_number",
            name="uq_document_versions_doc_ver",
        ),
        # CHECK constraint change_type IN 4 value (D-V3.1-Phase5-H + Plan 05-02 contract)
        sa.CheckConstraint(
            "change_type IN ('reupload', 'reextract', 'content_edit', 'restore')",
            name="ck_document_versions_change_type",
        ),
    )

    # INDEX cho list query GET /versions WHERE document_id = $1 ORDER BY version_number DESC
    op.create_index(
        "ix_document_versions_document_id",
        "document_versions",
        ["document_id"],
    )

    print(
        "[0007] OK CREATE TABLE document_versions (15 cột + UNIQUE doc_ver + INDEX document_id + CHECK change_type)"
    )


def downgrade() -> None:
    """Idempotent rollback — DROP TABLE document_versions + INDEX + log COUNT(*).

    Thứ tự ngược upgrade:
    1. Defensive log COUNT(*) document_versions hiện có (operator visibility — KHÔNG raise).
    2. DROP INDEX ix_document_versions_document_id (IF EXISTS).
    3. DROP TABLE document_versions (CASCADE FK auto-drop UNIQUE + CHECK).

    Lưu ý: KHÔNG raise nếu COUNT > 0 — schema 0007 là feature-additive (KHÔNG migrate
    data từ table cũ). Operator quyết định manual review trước rollback nếu data
    valuable (production deployment chưa nên rollback nếu user đã restore version).
    Pattern khác Plan 01-01 0006 — 0006 có defensive RuntimeError vì rollback CHECK
    constraint 3-value với row role='hub_admin' sẽ FAIL; 0007 DROP TABLE atomic OK.
    """
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    existing_tables = set(inspector.get_table_names())

    # ============================================================
    # STEP 1 — Defensive log COUNT(*) (operator visibility).
    # ============================================================
    if "document_versions" in existing_tables:
        count_result = bind.execute(
            sa.text("SELECT COUNT(*) FROM document_versions")
        ).scalar()
        print(
            f"[0007 downgrade] document_versions table hiện có {count_result} row "
            f"— sẽ bị DROP. Nếu data valuable, ABORT downgrade + backup trước "
            f"khi re-run alembic downgrade."
        )
    else:
        print("[0007 downgrade] SKIP — document_versions table KHÔNG tồn tại")
        return

    # ============================================================
    # STEP 2 — DROP INDEX (IF EXISTS guard idempotent).
    # ============================================================
    op.execute(
        "DROP INDEX IF EXISTS ix_document_versions_document_id"
    )
    print("[0007 downgrade] OK DROP INDEX ix_document_versions_document_id")

    # ============================================================
    # STEP 3 — DROP TABLE (CASCADE auto-drop UNIQUE + CHECK + FK).
    # ============================================================
    op.drop_table("document_versions")
    print("[0007 downgrade] OK DROP TABLE document_versions (CASCADE auto-drop UNIQUE + CHECK + FK)")
