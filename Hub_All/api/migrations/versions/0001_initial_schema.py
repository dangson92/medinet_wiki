"""initial_schema

Revision ID: 0001
Revises:
Create Date: 2026-05-13 22:30:00.000000

Migration baseline Phase 2 — tao 10 bang cho stack M2:
- users, hubs, documents, chunks, audit_logs, usage_events
- refresh_tokens, api_keys, settings, user_hubs (join)

Mitigations:
- R1/R7: chunks.vector Vector(1536) — pin dim cho hot-swap khong re-embed.
- R4: documents.status CHECK enum bao gom 'failed_unsupported'.
- P17: HNSW index tren chunks.vector dung vector_cosine_ops (KHONG L2).
- P7: KHONG touch schema 'cocoindex' (env.py include_object filter).
- T-02-01,02,03,04: FK NOT NULL CASCADE/SET NULL theo threat model Plan 01.

Yeu cau prereq:
- ext `vector` enable (Phase 1 init-db.sh).
- ext `pgcrypto` enable (migration nay tu goi CREATE EXTENSION).
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Tao schema baseline M2 — 10 bang + HNSW vector_cosine_ops + indexes."""

    # === Extensions (defensive — Phase 1 init-db.sh da enable `vector`) ===
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # === 1. users ===
    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("full_name", sa.Text(), nullable=True),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("TRUE"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "role IN ('admin', 'editor', 'viewer')",
            name="ck_users_role_enum",
        ),
        sa.UniqueConstraint("email", name="uq_users_email"),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
    )

    # === 2. hubs ===
    op.create_table(
        "hubs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("TRUE"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("slug", name="uq_hubs_slug"),
        sa.PrimaryKeyConstraint("id", name="pk_hubs"),
    )

    # === 3. refresh_tokens (FK -> users CASCADE) ===
    op.create_table(
        "refresh_tokens",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
            name="fk_refresh_tokens_user_id_users",
        ),
        sa.UniqueConstraint("token_hash", name="uq_refresh_tokens_token_hash"),
        sa.PrimaryKeyConstraint("id", name="pk_refresh_tokens"),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])
    op.create_index("ix_refresh_tokens_expires_at", "refresh_tokens", ["expires_at"])

    # === 4. user_hubs (composite PK, FK -> users + hubs CASCADE) ===
    op.create_table(
        "user_hubs",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("hub_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "assigned_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
            name="fk_user_hubs_user_id_users",
        ),
        sa.ForeignKeyConstraint(
            ["hub_id"],
            ["hubs.id"],
            ondelete="CASCADE",
            name="fk_user_hubs_hub_id_hubs",
        ),
        sa.PrimaryKeyConstraint("user_id", "hub_id", name="pk_user_hubs"),
    )

    # === 5. settings (PK = key, FK updated_by -> users SET NULL) ===
    op.create_table(
        "settings",
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("value", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"],
            ["users.id"],
            ondelete="SET NULL",
            name="fk_settings_updated_by_users",
        ),
        sa.PrimaryKeyConstraint("key", name="pk_settings"),
    )

    # === 6. api_keys (FK created_by -> users SET NULL, hub_id -> hubs CASCADE) ===
    op.create_table(
        "api_keys",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("key_hash", sa.Text(), nullable=False),
        sa.Column("key_prefix", sa.Text(), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("hub_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("TRUE"),
        ),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            ondelete="SET NULL",
            name="fk_api_keys_created_by_users",
        ),
        sa.ForeignKeyConstraint(
            ["hub_id"],
            ["hubs.id"],
            ondelete="CASCADE",
            name="fk_api_keys_hub_id_hubs",
        ),
        sa.UniqueConstraint("key_hash", name="uq_api_keys_key_hash"),
        sa.PrimaryKeyConstraint("id", name="pk_api_keys"),
    )

    # === 7. documents (FK uploaded_by -> users SET NULL, hub_id -> hubs CASCADE) ===
    op.create_table(
        "documents",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("hub_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("uploaded_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("mime_type", sa.Text(), nullable=True),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("last_heartbeat", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "attempts",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "chunk_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["hub_id"],
            ["hubs.id"],
            ondelete="CASCADE",
            name="fk_documents_hub_id_hubs",
        ),
        sa.ForeignKeyConstraint(
            ["uploaded_by"],
            ["users.id"],
            ondelete="SET NULL",
            name="fk_documents_uploaded_by_users",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'processing', 'completed', 'failed', 'failed_unsupported')",
            name="ck_documents_status_enum",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_documents"),
    )
    op.create_index(
        "ix_documents_hub_id_status",
        "documents",
        ["hub_id", "status"],
    )
    op.create_index(
        "ix_documents_uploaded_by",
        "documents",
        ["uploaded_by"],
    )

    # === 8. chunks (FK document_id CASCADE, hub_id CASCADE) ===
    op.create_table(
        "chunks",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("hub_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.LargeBinary(), nullable=False),
        sa.Column("heading_path", sa.Text(), nullable=True),
        sa.Column("page_start", sa.Integer(), nullable=True),
        sa.Column("page_end", sa.Integer(), nullable=True),
        sa.Column("vector", Vector(1536), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            ondelete="CASCADE",
            name="fk_chunks_document_id_documents",
        ),
        sa.ForeignKeyConstraint(
            ["hub_id"],
            ["hubs.id"],
            ondelete="CASCADE",
            name="fk_chunks_hub_id_hubs",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_chunks"),
    )
    op.create_index(
        "ix_chunks_hub_id_document_id",
        "chunks",
        ["hub_id", "document_id"],
    )
    op.create_index(
        "ix_chunks_content_hash",
        "chunks",
        ["content_hash"],
    )

    # HNSW index — RAW SQL vi autogenerate emit `postgresql_using` OK nhung
    # `postgresql_ops` mapping vector_cosine_ops khong reliable moi version.
    # P17 mitigation: CO DINH vector_cosine_ops (KHONG l2_ops / ip_ops).
    op.execute(
        "CREATE INDEX ix_chunks_vector_hnsw "
        "ON chunks USING hnsw (vector vector_cosine_ops)"
    )

    # === 9. audit_logs (FK user_id + hub_id SET NULL) ===
    op.create_table(
        "audit_logs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("target_type", sa.Text(), nullable=True),
        sa.Column("target_id", sa.Text(), nullable=True),
        sa.Column("hub_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("request_id", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="SET NULL",
            name="fk_audit_logs_user_id_users",
        ),
        sa.ForeignKeyConstraint(
            ["hub_id"],
            ["hubs.id"],
            ondelete="SET NULL",
            name="fk_audit_logs_hub_id_hubs",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_audit_logs"),
    )
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])
    op.create_index(
        "ix_audit_logs_user_id_created_at",
        "audit_logs",
        ["user_id", "created_at"],
    )
    op.create_index(
        "ix_audit_logs_hub_id_created_at",
        "audit_logs",
        ["hub_id", "created_at"],
    )

    # === 10. usage_events (FK user_id + hub_id SET NULL) ===
    op.create_table(
        "usage_events",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("hub_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column("cost_usd", sa.Numeric(10, 6), nullable=True),
        sa.Column("request_id", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="SET NULL",
            name="fk_usage_events_user_id_users",
        ),
        sa.ForeignKeyConstraint(
            ["hub_id"],
            ["hubs.id"],
            ondelete="SET NULL",
            name="fk_usage_events_hub_id_hubs",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_usage_events"),
    )
    op.create_index("ix_usage_events_created_at", "usage_events", ["created_at"])
    op.create_index(
        "ix_usage_events_user_id_model_created_at",
        "usage_events",
        ["user_id", "model", "created_at"],
    )


def downgrade() -> None:
    """Drop toan bo 10 bang theo thu tu NGUOC FK dependency."""

    # Drop indexes truoc cho clean (KHONG strict can — DROP TABLE cascade).
    op.execute("DROP INDEX IF EXISTS ix_chunks_vector_hnsw")

    # Drop tables theo thu tu nguoc FK
    op.drop_index("ix_usage_events_user_id_model_created_at", table_name="usage_events")
    op.drop_index("ix_usage_events_created_at", table_name="usage_events")
    op.drop_table("usage_events")

    op.drop_index("ix_audit_logs_hub_id_created_at", table_name="audit_logs")
    op.drop_index("ix_audit_logs_user_id_created_at", table_name="audit_logs")
    op.drop_index("ix_audit_logs_created_at", table_name="audit_logs")
    op.drop_table("audit_logs")

    op.drop_index("ix_chunks_content_hash", table_name="chunks")
    op.drop_index("ix_chunks_hub_id_document_id", table_name="chunks")
    op.drop_table("chunks")

    op.drop_index("ix_documents_uploaded_by", table_name="documents")
    op.drop_index("ix_documents_hub_id_status", table_name="documents")
    op.drop_table("documents")

    op.drop_table("api_keys")
    op.drop_table("settings")
    op.drop_table("user_hubs")

    op.drop_index("ix_refresh_tokens_expires_at", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_user_id", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")

    op.drop_table("hubs")
    op.drop_table("users")

    # KHONG drop ext vector / pgcrypto (defensive — co the app khac dung).
    # KHONG drop schema cocoindex (P7 — khong touch cocoindex).
