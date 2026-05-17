"""phase5_schema_reconcile

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-17 10:00:00.000000

Phase 5 — HUB-01 / USER-01 / AUX-02 prerequisite:
Reconcile schema bảng `hubs`, `users`, `api_keys` từ Phase 2 với contract
frontend `api.ts` (`HubAPI`, `UserAPI`, `APIKeyAPI`). Chỉ ADD cột — KHÔNG drop
cột nào (Phase 2 baseline giữ nguyên).

- hubs: thêm `code`, `subdomain`, `status` (W1 — `code` là field contract chính
  thức; `slug` Phase 2 giữ làm legacy NOT NULL mirror của `code`, defer dọn về
  milestone schema-cleanup tương lai).
- users: thêm `phone`, `department`, `avatar_url`, `status`.
- api_keys: thêm `permissions`, `allowed_hub_ids`, `rate_limit`.

D-05: KHÔNG thêm `chroma_collection`/`db_host`/`db_port`/`db_name`/`db_user` vào
`hubs` (di sản Go multi-DB — drop hẳn khỏi M2).
BLOCKER 2: KHÔNG touch bảng `settings` (Phase 5 không implement settings CRUD —
bảng `settings` để dành Phase 7 rag-config).

T-05-01-01 mitigation: server_default cho cột NOT NULL mới đảm bảo existing rows
không vi phạm constraint; downgrade() đảo ngược clean (alembic round-trip verify).
"""
from __future__ import annotations

from typing import (  # noqa: UP035 — match Alembic template + 0001/0002 baseline style
    Sequence,
    Union,
)

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: Union[str, None] = "0002"  # noqa: UP007 — Alembic template style (match 0001/0002)
branch_labels: Union[str, Sequence[str], None] = None  # noqa: UP007
depends_on: Union[str, Sequence[str], None] = None  # noqa: UP007


def upgrade() -> None:
    """Thêm cột Phase 5 cho hubs / users / api_keys (additive only)."""

    # === hubs — thêm code / subdomain / status ===
    op.add_column(
        "hubs",
        sa.Column("code", sa.Text(), nullable=False, server_default=sa.text("''")),
    )
    op.add_column(
        "hubs",
        sa.Column(
            "subdomain", sa.Text(), nullable=False, server_default=sa.text("''")
        ),
    )
    op.add_column(
        "hubs",
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'active'"),
        ),
    )
    # Drop server_default cho code / subdomain — chỉ cần backfill existing rows;
    # row mới phải set giá trị tường minh (HubService.create Plan 05-03).
    op.alter_column("hubs", "code", server_default=None)
    op.alter_column("hubs", "subdomain", server_default=None)
    op.create_check_constraint(
        "hub_status_enum", "hubs", "status IN ('active','inactive')"
    )
    op.create_unique_constraint("uq_hubs_code", "hubs", ["code"])

    # === users — thêm phone / department / avatar_url / status ===
    op.add_column("users", sa.Column("phone", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("department", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("avatar_url", sa.Text(), nullable=True))
    op.add_column(
        "users",
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'active'"),
        ),
    )
    op.create_check_constraint(
        "user_status_enum", "users", "status IN ('active','disabled')"
    )

    # === api_keys — thêm permissions / allowed_hub_ids / rate_limit ===
    op.add_column(
        "api_keys",
        sa.Column(
            "permissions",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "api_keys",
        sa.Column(
            "allowed_hub_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "api_keys",
        sa.Column(
            "rate_limit",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("100"),
        ),
    )


def downgrade() -> None:
    """Đảo ngược upgrade — drop constraint + cột theo thứ tự ngược (api_keys → users → hubs)."""

    # === api_keys ===
    op.drop_column("api_keys", "rate_limit")
    op.drop_column("api_keys", "allowed_hub_ids")
    op.drop_column("api_keys", "permissions")

    # === users ===
    op.drop_constraint("user_status_enum", "users", type_="check")
    op.drop_column("users", "status")
    op.drop_column("users", "avatar_url")
    op.drop_column("users", "department")
    op.drop_column("users", "phone")

    # === hubs ===
    op.drop_constraint("uq_hubs_code", "hubs", type_="unique")
    op.drop_constraint("hub_status_enum", "hubs", type_="check")
    op.drop_column("hubs", "status")
    op.drop_column("hubs", "subdomain")
    op.drop_column("hubs", "code")
