"""guides

Revision ID: 0008
Revises: 0007
Create Date: 2026-05-27 10:00:00.000000

Tạo bảng `guides` chứa tài liệu hướng dẫn sử dụng Medinet Wiki — public
read cho mọi user đã đăng nhập, write admin-only. Persist ở central
(router mount conditional ở `app/main.py`), bảng tạo ở mọi DB cho đồng
nhất schema (carry forward pattern Plan 04-01 sync_outbox — tồn tại
trên mọi DB, chỉ hub con dùng; ở đây chỉ central dùng).

Idempotent introspect carry forward Plan 01-01 + Plan 05-01 v3.1:
- STEP 1: skip nếu bảng đã tồn tại (re-run safe).
- STEP 2: precondition users table (FK target created_by/updated_by).
- STEP 3: CREATE TABLE guides 7 cột.
"""
from __future__ import annotations

from typing import (  # noqa: UP035 — match Alembic baseline 0001-0007
    Sequence,
    Union,
)

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008"
down_revision: Union[str, None] = "0007"  # noqa: UP007
branch_labels: Union[str, Sequence[str], None] = None  # noqa: UP007
depends_on: Union[str, Sequence[str], None] = None  # noqa: UP007


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = set(inspector.get_table_names())

    if "guides" in existing:
        print("[0008] SKIP CREATE TABLE guides — table đã tồn tại (idempotent)")
        return

    if "users" not in existing:
        raise RuntimeError(
            "Migration 0008 requires users table (FK target). "
            "Run `alembic upgrade head` sequential từ 0001 baseline."
        )

    op.create_table(
        "guides",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "updated_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )

    op.create_index("ix_guides_updated_at", "guides", ["updated_at"])
    print("[0008] OK CREATE TABLE guides (7 cột + INDEX updated_at)")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = set(inspector.get_table_names())

    if "guides" not in existing:
        print("[0008 downgrade] SKIP — guides table KHÔNG tồn tại")
        return

    count = bind.execute(sa.text("SELECT COUNT(*) FROM guides")).scalar()
    print(
        f"[0008 downgrade] guides table có {count} row — sẽ bị DROP. "
        f"Backup trước nếu data valuable."
    )

    op.execute("DROP INDEX IF EXISTS ix_guides_updated_at")
    op.drop_table("guides")
    print("[0008 downgrade] OK DROP TABLE guides")
