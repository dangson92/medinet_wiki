"""Re-export stable_chunk_id + outbox SQL constants — D-V3-Phase4-A5 LOCKED queries.

Plan 04-03 Task 1 (SYNC-01/02/05):
- `stable_chunk_id` re-export từ `app.rag.flow` (KHÔNG duplicate logic) — preserve
  citation determinism qua re-index cùng (doc_id, idx).
- 7 SQL constant cover hot path worker loop (D-V3-Phase4-A5):
  - CLAIM_PENDING_SQL: SELECT FOR UPDATE SKIP LOCKED batch (concurrency-safe).
  - MARK_PROCESSING_SQL: mark batch processing + attempt_count++.
  - MARK_PROCESSED_SQL: mark success + processed_at=NOW().
  - MARK_FAILED_RETRY_SQL: backoff + last_error truncate (1000 char).
  - MARK_DEAD_SQL: attempt_count >= max → status='dead' + last_error.
  - PUSH_INSERT_CHUNK_SQL: ON CONFLICT (id) DO UPDATE WHERE content_hash IS
    DISTINCT FROM EXCLUDED.content_hash (D-V3-Phase4-B1 idempotent).
  - PUSH_DELETE_CHUNK_SQL: DELETE FROM chunks WHERE id = ANY($1).
  - UPDATE_DOC_SYNC_STATUS_SQL: D-V3-Phase4-B2 lifecycle aggregate
    (BLOCKER 1 fix — synced/failed/partial/syncing CASE branches).

KHÔNG dùng pgvector cast `$N::vector` trong PUSH_INSERT_CHUNK_SQL — central pool
phải register codec `pgvector.asyncpg.register_vector` ở Plan 04-04 lifespan;
worker chỉ truyền list[float] qua $9 parameter.
"""
from __future__ import annotations

from app.rag.flow import CHUNK_ID_NAMESPACE, stable_chunk_id

# ────────────────────────────────────────────────────────────────────
# 1) CLAIM batch — SELECT FOR UPDATE SKIP LOCKED hot path (D-V3-Phase4-A5).
# ────────────────────────────────────────────────────────────────────
# Worker pool concurrency-safe: multiple worker instance đồng thời claim batch
# disjoint row (KHÔNG block lock). next_retry_at filter cho exp backoff path.
CLAIM_PENDING_SQL = """
    SELECT id, op_type, chunk_id, document_id, payload,
           attempt_count, last_error, status, next_retry_at,
           created_at, processed_at
    FROM sync_outbox
    WHERE status = 'pending'
      AND (next_retry_at IS NULL OR next_retry_at <= NOW())
    ORDER BY created_at
    LIMIT $1
    FOR UPDATE SKIP LOCKED
"""

# ────────────────────────────────────────────────────────────────────
# 2) MARK PROCESSING — bump status + attempt_count++.
# ────────────────────────────────────────────────────────────────────
# Sau khi CLAIM thành công, mark batch 'processing' để worker khác KHÔNG re-claim
# nếu transaction rollback (defensive). attempt_count bump trước khi push central.
MARK_PROCESSING_SQL = """
    UPDATE sync_outbox
    SET status = 'processing', attempt_count = attempt_count + 1
    WHERE id = ANY($1::uuid[])
"""

# ────────────────────────────────────────────────────────────────────
# 3) MARK PROCESSED — success path (processed_at=NOW() + clear last_error).
# ────────────────────────────────────────────────────────────────────
MARK_PROCESSED_SQL = """
    UPDATE sync_outbox
    SET status = 'processed', processed_at = NOW(), last_error = NULL
    WHERE id = ANY($1::uuid[])
"""

# ────────────────────────────────────────────────────────────────────
# 4) MARK FAILED RETRY — exp backoff path (status='pending' lại + next_retry_at).
# ────────────────────────────────────────────────────────────────────
# Worker compute backoff seconds từ Settings.sync_backoff_seconds[attempt-1].
# attempt_count đã bump ở MARK_PROCESSING_SQL — last_error truncate 1000 char.
MARK_FAILED_RETRY_SQL = """
    UPDATE sync_outbox
    SET status = 'pending',
        last_error = $2,
        next_retry_at = NOW() + ($3::int * INTERVAL '1 second')
    WHERE id = $1
"""

# ────────────────────────────────────────────────────────────────────
# 5) MARK DEAD — attempt_count >= max_attempts → status='dead' (D-V3-Phase4-C2).
# ────────────────────────────────────────────────────────────────────
# KHÔNG xoá row (audit trail D-V3-Phase4-C2). processed_at=NOW() cho dead time.
MARK_DEAD_SQL = """
    UPDATE sync_outbox
    SET status = 'dead', last_error = $2, processed_at = NOW()
    WHERE id = ANY($1::uuid[])
"""

# ────────────────────────────────────────────────────────────────────
# 6) PUSH INSERT — ON CONFLICT (id) DO UPDATE idempotent (D-V3-Phase4-B1).
# ────────────────────────────────────────────────────────────────────
# WHERE content_hash IS DISTINCT FROM EXCLUDED tránh UPDATE no-op (bảo vệ HNSW
# vector index disk write thừa). chunk_id stable UUID5 đảm bảo deterministic.
# Worker truyền $9 = list[float] vector (pgvector codec đã register Plan 04-04).
PUSH_INSERT_CHUNK_SQL = """
    INSERT INTO chunks (id, document_id, hub_id, content, content_hash,
                        heading_path, page_start, page_end, vector, metadata, created_at)
    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10::jsonb, COALESCE($11, NOW()))
    ON CONFLICT (id) DO UPDATE SET
        content = EXCLUDED.content,
        content_hash = EXCLUDED.content_hash,
        heading_path = EXCLUDED.heading_path,
        page_start = EXCLUDED.page_start,
        page_end = EXCLUDED.page_end,
        vector = EXCLUDED.vector,
        metadata = EXCLUDED.metadata
    WHERE chunks.content_hash IS DISTINCT FROM EXCLUDED.content_hash
"""

# ────────────────────────────────────────────────────────────────────
# 7) PUSH DELETE — HARD DELETE chunks (D-V3-Phase4-B3 + chunks immutable).
# ────────────────────────────────────────────────────────────────────
# Chunks immutable (KHÔNG soft-delete `deleted_at` — rag/flow.py docstring).
PUSH_DELETE_CHUNK_SQL = """
    DELETE FROM chunks WHERE id = ANY($1::uuid[])
"""

# ────────────────────────────────────────────────────────────────────
# 8) UPDATE_DOC_SYNC_STATUS — BLOCKER 1 fix (D-V3-Phase4-B2 lifecycle aggregate).
# ────────────────────────────────────────────────────────────────────
# Aggregate sync_outbox state per document → UPDATE documents.sync_status:
#   - 'synced':  KHÔNG còn pending/processing + KHÔNG dead → all processed
#   - 'failed':  KHÔNG còn pending/processing + có dead + KHÔNG processed
#   - 'partial': KHÔNG còn pending/processing + có cả dead + processed
#   - 'syncing': còn pending/processing (worker đang chạy)
#
# Plan 04-01 trigger handle initial 'pending'→'syncing'; worker (Plan 04-03)
# handle 'syncing'→'synced'/'failed'/'partial' transitions sau MỖI batch.
# Idempotent — re-call cùng document_ids → re-aggregate state mới.
UPDATE_DOC_SYNC_STATUS_SQL = """
    UPDATE documents
    SET sync_status = (
        CASE
            WHEN NOT EXISTS (
                SELECT 1 FROM sync_outbox
                WHERE document_id = documents.id
                  AND status IN ('pending', 'processing')
            ) THEN
                CASE
                    WHEN EXISTS (
                        SELECT 1 FROM sync_outbox
                        WHERE document_id = documents.id AND status = 'dead'
                    ) THEN
                        CASE
                            WHEN EXISTS (
                                SELECT 1 FROM sync_outbox
                                WHERE document_id = documents.id AND status = 'processed'
                            ) THEN 'partial'
                            ELSE 'failed'
                        END
                    ELSE 'synced'
                END
            ELSE 'syncing'
        END
    )
    WHERE id = ANY($1::uuid[])
    RETURNING id, sync_status
"""

__all__ = [
    "CHUNK_ID_NAMESPACE",
    "CLAIM_PENDING_SQL",
    "MARK_DEAD_SQL",
    "MARK_FAILED_RETRY_SQL",
    "MARK_PROCESSED_SQL",
    "MARK_PROCESSING_SQL",
    "PUSH_DELETE_CHUNK_SQL",
    "PUSH_INSERT_CHUNK_SQL",
    "UPDATE_DOC_SYNC_STATUS_SQL",
    "stable_chunk_id",
]
