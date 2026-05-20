"""mcp_oauth_clients — per-user pre-registered OAuth client (Phase 8.3 add-on)

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-20 12:00:00.000000

Mỗi Medinet user có 1 cặp `client_id`/`client_secret` pre-registered cho dialog
"Add custom connector" → Advanced của Claude web. Bind cứng: client_id Y ⇄
user_id Y — bước login OAuth ở MCP service từ chối nếu user login ≠ owner.

Threat model `client_secret` plaintext (đối xứng pattern rag_config):
- DB compromise = total compromise → ngang với tất cả secret/token khác trong
  bảng `settings` (RAG_*_API_KEY) + `refresh_tokens.token_hash`. Không tạo
  surface mới.
- Secret leak alone không cho phép truy cập wiki — Claude vẫn phải login
  credential Medinet ở bước /authorize. Bind cứng (login user == owner)
  thêm 1 lớp: secret của user X bị leak vẫn không dùng được nếu attacker
  không có credential user X.

Schema:
- `user_id`         — FK users.id ON DELETE CASCADE, PRIMARY KEY → 1 user 1
                      cặp; xoá user xoá luôn cặp.
- `client_id`       — UNIQUE, lookup index cho MCP internal endpoint.
- `client_secret`   — plaintext 32-byte urlsafe (~256 bit entropy).
- `redirect_uris`   — JSONB list (Claude có thể có 1-2 callback).
- `created_at`      — server NOW().
- `rotated_at`      — NULL chưa rotate; NOT NULL sau /rotate.
"""
from __future__ import annotations

from typing import (  # noqa: UP035 — match Alembic template baseline 0001-0003
    Sequence,
    Union,
)

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: Union[str, None] = "0003"  # noqa: UP007 — match baseline 0001-0003
branch_labels: Union[str, Sequence[str], None] = None  # noqa: UP007
depends_on: Union[str, Sequence[str], None] = None  # noqa: UP007


def upgrade() -> None:
    """Tạo bảng mcp_oauth_clients + index ix_mcp_oauth_clients_client_id."""
    op.create_table(
        "mcp_oauth_clients",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("client_id", sa.Text(), nullable=False, unique=True),
        sa.Column("client_secret", sa.Text(), nullable=False),
        sa.Column(
            "redirect_uris",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "rotated_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    # Lookup theo client_id — MCP service hỏi internal endpoint mỗi authorize.
    op.create_index(
        "ix_mcp_oauth_clients_client_id",
        "mcp_oauth_clients",
        ["client_id"],
    )


def downgrade() -> None:
    """Rollback — drop bảng + index."""
    op.drop_index(
        "ix_mcp_oauth_clients_client_id", table_name="mcp_oauth_clients"
    )
    op.drop_table("mcp_oauth_clients")
