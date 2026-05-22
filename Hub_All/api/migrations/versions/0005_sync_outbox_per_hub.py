"""sync_outbox_per_hub

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-22 12:00:00.000000

Phase 4 Plan 04-01 (SYNC-05 + SYNC-01 + SYNC-02) — Outbox pattern per-DB hub con.

PER-HUB ONLY: rev 0005 SKIP central (D-V3-Phase4-A2). Guard runtime check
`current_database() == 'medinet_central'` → no-op return ở upgrade(). Vẫn ghi
alembic_version row để CI head SHA uniform check R-V3-3 không break.

Schema (D-V3-Phase4-A2 LOCKED):
- sync_outbox table (11 cột + 2 CHECK + 2 partial index).
- documents.sync_status enum column (D-V3-Phase4-B2 — pending|syncing|synced|failed|partial).
- Postgres function enqueue_sync_outbox() — EXPLICIT jsonb_build_object (KHÔNG `to_jsonb` của NEW row)
  cho INSERT branch, vector cast ::float4[], content_hash encode hex;
  jsonb_build_object('id', OLD.id) cho DELETE branch.
- INSERT branch also UPDATE documents.sync_status='syncing' WHERE id=NEW.document_id
  AND sync_status='pending' (D-V3-Phase4-B2 initial lifecycle state — idempotent
  first chunk per document).
- 2 trigger AFTER INSERT/DELETE ON chunks FOR EACH ROW EXECUTE FUNCTION
  enqueue_sync_outbox() (D-V3-Phase4-A4 — atomic cùng transaction chunks INSERT).

Mitigations:
- R-V3-1 sync drift HIGH — outbox INSERT atomic cùng transaction chunks, retry
  semantics worker layer (Plan 04-03 exp backoff 1/5/30/120s max 5 attempts).
- T-04-01-03 Repudiation — sync_outbox.payload JSONB chứa toàn bộ NEW row qua
  jsonb_build_object + last_error + attempt_count audit trail rõ ràng.
- T-04-01-04 Info Disclosure — payload chỉ chứa chunk content (đã trong DB hub con),
  cross-DB write protection ở DSN credential layer (Plan 04-02 T-04-06).
- T-04-01-05 DoS — partial index `ix_sync_outbox_pending WHERE status IN
  ('pending','processing')` giữ index size nhỏ; worker update status='processed'
  để tự dọn (KHÔNG xoá — D-V3-Phase4-C2 audit trail).
- T-04-01-07 Integrity — pgvector serialization fix qua jsonb_build_object +
  cast ::float4[] + encode hex tránh trigger raise rollback chunks INSERT
  (đập cocoindex flow stall).

pgvector serialization fix (CR Iteration 1 BLOCKER 2 — lý do KHÔNG `to_jsonb` của full NEW row):
- `to_jsonb` trên full NEW row có pgvector column FAIL runtime (no jsonb cast cho
  vector type) HOẶC return opaque text Pydantic không parse được.
- Fix INSERT branch: explicit `jsonb_build_object(...)` cast `vector::float4[]`
  → pgvector hỗ trợ float4[] array → to_jsonb sau đó encode JSON array number.
- Fix INSERT branch: `content_hash` bytea → `encode(NEW.content_hash, 'hex')`
  → hex string clean (KHÔNG có `\\x` prefix) cho Pydantic ChunkPayload Plan 04-03
  parse qua `bytes.fromhex(v)`.

D-V3-Phase4-B2 lifecycle initial state fix (CR Iteration 1 BLOCKER 1):
- Trigger INSERT branch cùng transaction chunks INSERT phải UPDATE documents.sync_status
  = 'syncing' WHERE id = NEW.document_id AND sync_status = 'pending'.
- Idempotent guard `WHERE sync_status = 'pending'` đảm bảo chỉ first chunk per
  document update (subsequent chunks no-op — KHÔNG override 'failed'/'partial'
  do Plan 04-03 worker đã bump).
"""
from __future__ import annotations

from typing import (  # noqa: UP035 — match Alembic template baseline 0001-0004
    Sequence,
    Union,
)

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005"
down_revision: Union[str, None] = "0004"  # noqa: UP007 — match baseline 0001-0004
branch_labels: Union[str, Sequence[str], None] = None  # noqa: UP007
depends_on: Union[str, Sequence[str], None] = None  # noqa: UP007


def upgrade() -> None:
    """sync_outbox + trigger + documents.sync_status — per-hub-only (skip central).

    Runtime skip guard D-V3-Phase4-A2: central KHÔNG có sync_outbox. Khi caller
    chạy `alembic upgrade head` trên DB medinet_central (vd CI head SHA check R-V3-3),
    function này return no-op TRƯỚC mọi DDL — alembic_version vẫn ghi rev 0005
    để head SHA uniform giữa 4 DB (medinet_central + 3 hub con).
    """
    # D-V3-Phase4-A2 skip guard runtime — central KHÔNG có sync_outbox.
    bind = op.get_bind()
    current_db = bind.execute(sa.text("SELECT current_database()")).scalar()
    if current_db == "medinet_central":
        # Log thân thiện cho operator debug `alembic -x hub=central upgrade head`.
        print(f"[0005] SKIP central DB ({current_db}) — sync_outbox per-hub-only")
        return

    # ============================================================
    # 1) sync_outbox table — D-V3-Phase4-A2 LOCKED schema (11 cột).
    # ============================================================
    op.execute("""
        CREATE TABLE IF NOT EXISTS sync_outbox (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            op_type TEXT NOT NULL CHECK (op_type IN ('insert','delete')),
            chunk_id UUID NOT NULL,
            document_id UUID NULL,
            payload JSONB NOT NULL,
            attempt_count INTEGER NOT NULL DEFAULT 0,
            last_error TEXT NULL,
            status TEXT NOT NULL DEFAULT 'pending'
                CHECK (status IN ('pending','processing','processed','dead')),
            next_retry_at TIMESTAMPTZ NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            processed_at TIMESTAMPTZ NULL
        )
    """)

    # ============================================================
    # 2) Indexes — partial cho worker hot path + debug.
    # ============================================================
    # ix_sync_outbox_pending: partial index theo D-V3-Phase4-A2 — chỉ index row
    # đang chờ/processing, giảm index bloat khi processed/dead row tích lũy.
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_sync_outbox_pending
        ON sync_outbox (status, next_retry_at)
        WHERE status IN ('pending','processing')
    """)
    # ix_sync_outbox_chunk_id: lookup debug + Plan 04-03 worker replay endpoint.
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_sync_outbox_chunk_id
        ON sync_outbox (chunk_id)
    """)

    # ============================================================
    # 3) documents.sync_status enum column — D-V3-Phase4-B2 lifecycle.
    # ============================================================
    # 5 value (pending/syncing/synced/failed/partial) — initial 'pending',
    # trigger INSERT bump 'syncing' (idempotent first chunk), Plan 04-03 worker
    # bump 'synced'/'failed'/'partial' sau push central.
    op.execute("""
        ALTER TABLE documents
        ADD COLUMN IF NOT EXISTS sync_status TEXT NOT NULL DEFAULT 'pending'
            CHECK (sync_status IN ('pending','syncing','synced','failed','partial'))
    """)

    # ============================================================
    # 4) Function enqueue_sync_outbox() — EXPLICIT jsonb_build_object.
    # ============================================================
    # BLOCKER 2 fix: KHÔNG dùng `to_jsonb` của full NEW row (FAIL trên pgvector column).
    # Explicit field list + vector cast ::float4[] + content_hash encode hex.
    #
    # BLOCKER 1 fix: INSERT branch also UPDATE documents.sync_status='syncing'
    # cùng transaction (atomic) với idempotent guard `WHERE sync_status='pending'`
    # — D-V3-Phase4-B2 lifecycle initial state first-chunk-per-document.
    op.execute("""
        CREATE OR REPLACE FUNCTION enqueue_sync_outbox()
        RETURNS TRIGGER
        LANGUAGE plpgsql
        AS $$
        DECLARE
            payload_jsonb JSONB;
        BEGIN
            IF TG_OP = 'INSERT' THEN
                -- Explicit field list — vector cast float4[] (pgvector hỗ trợ),
                -- content_hash bytea → encode hex string clean JSON.
                payload_jsonb := jsonb_build_object(
                    'id', NEW.id,
                    'document_id', NEW.document_id,
                    'hub_id', NEW.hub_id,
                    'content', NEW.content,
                    'content_hash', encode(NEW.content_hash, 'hex'),
                    'heading_path', NEW.heading_path,
                    'page_start', NEW.page_start,
                    'page_end', NEW.page_end,
                    'vector', CASE
                        WHEN NEW.vector IS NULL THEN NULL
                        ELSE to_jsonb(NEW.vector::float4[])
                    END,
                    'metadata', NEW.metadata,
                    'created_at', NEW.created_at
                );
                INSERT INTO sync_outbox (op_type, chunk_id, document_id, payload, status)
                VALUES ('insert', NEW.id, NEW.document_id, payload_jsonb, 'pending');

                -- D-V3-Phase4-B2 lifecycle initial state — idempotent guard
                -- chỉ first chunk per document update; subsequent chunks no-op.
                UPDATE documents
                SET sync_status = 'syncing'
                WHERE id = NEW.document_id AND sync_status = 'pending';

                RETURN NEW;
            ELSIF TG_OP = 'DELETE' THEN
                -- Key 'id' khớp ChunkPayload Plan 04-03 (NOT 'chunk_id' để unify schema).
                payload_jsonb := jsonb_build_object('id', OLD.id);
                INSERT INTO sync_outbox (op_type, chunk_id, document_id, payload, status)
                VALUES ('delete', OLD.id, OLD.document_id, payload_jsonb, 'pending');
                RETURN OLD;
            END IF;
            RETURN NULL;
        END;
        $$
    """)

    # ============================================================
    # 5) 2 trigger AFTER INSERT + AFTER DELETE — D-V3-Phase4-A4.
    # ============================================================
    # AFTER (KHÔNG BEFORE) đảm bảo NEW.* / OLD.* đã commit row chunks; FOR EACH ROW
    # đảm bảo mỗi chunk 1 outbox event (NOT batched FOR EACH STATEMENT).
    op.execute("""
        CREATE TRIGGER chunks_after_insert_enqueue_sync_outbox
        AFTER INSERT ON chunks
        FOR EACH ROW EXECUTE FUNCTION enqueue_sync_outbox()
    """)
    op.execute("""
        CREATE TRIGGER chunks_after_delete_enqueue_sync_outbox
        AFTER DELETE ON chunks
        FOR EACH ROW EXECUTE FUNCTION enqueue_sync_outbox()
    """)


def downgrade() -> None:
    """Idempotent rollback — IF EXISTS guard cho mọi object (chống partial state).

    Thứ tự nguợc upgrade: trigger → function → column → index → table.
    Skip central no-op (đối xứng upgrade) — nếu central chưa apply upgrade thì
    downgrade cũng no-op IF EXISTS (KHÔNG raise).
    """
    op.execute("DROP TRIGGER IF EXISTS chunks_after_delete_enqueue_sync_outbox ON chunks")
    op.execute("DROP TRIGGER IF EXISTS chunks_after_insert_enqueue_sync_outbox ON chunks")
    op.execute("DROP FUNCTION IF EXISTS enqueue_sync_outbox()")
    op.execute("ALTER TABLE documents DROP COLUMN IF EXISTS sync_status")
    op.execute("DROP INDEX IF EXISTS ix_sync_outbox_chunk_id")
    op.execute("DROP INDEX IF EXISTS ix_sync_outbox_pending")
    op.execute("DROP TABLE IF EXISTS sync_outbox")
