"""Phase 4 sync module — outbox worker + metrics + idempotent push (SYNC-01..05).

Module entry point Plan 04-03 (Wave 2):
- `keys.py` — Re-export `stable_chunk_id` từ rag.flow + SQL constants
  (CLAIM_PENDING_SQL + MARK_PROCESSED_SQL + MARK_DEAD_SQL + MARK_FAILED_RETRY_SQL +
  MARK_PROCESSING_SQL + PUSH_INSERT_CHUNK_SQL + PUSH_DELETE_CHUNK_SQL +
  UPDATE_DOC_SYNC_STATUS_SQL — BLOCKER 1 fix D-V3-Phase4-B2 lifecycle aggregate).
- `models.py` — Pydantic schemas (ChunkPayload + DeletePayload + SyncOutboxRow +
  SyncStatus enum + OpType enum + DocumentSyncStatus enum); ChunkPayload
  content_hash field_validator decode hex string → bytes (BLOCKER 2 fix
  end-to-end serialization, trigger Plan 04-01 emit qua encode(.., 'hex')).
- `metrics.py` — 6 Prometheus collector module-level với label `hub_name`
  (W7 fix — KHÔNG `hub_id` UUID; semantic rõ ràng hub_name string "yte"/"duoc").
- `worker.py` — `sync_worker_loop` async task (D-V3-Phase4-A1/A3/A5);
  `_update_document_sync_status` helper aggregate D-V3-Phase4-B2 lifecycle
  (BLOCKER 1 fix — UPDATE documents.sync_status SAU MỖI batch).

Public API (re-export below).
"""
from __future__ import annotations

from app.sync.metrics import (
    SYNC_ATTEMPT_TOTAL,
    SYNC_COUNT_DRIFT,
    SYNC_DEAD_TOTAL,
    SYNC_HASH_DRIFT,
    SYNC_LAG_SECONDS,
    SYNC_OUTBOX_PENDING,
    normalize_error_class,
)
from app.sync.models import (
    ChunkPayload,
    DeletePayload,
    DocumentSyncStatus,
    OpType,
    SyncOutboxRow,
    SyncStatus,
)
from app.sync.worker import sync_worker_loop

__all__ = [
    "SYNC_ATTEMPT_TOTAL",
    "SYNC_COUNT_DRIFT",
    "SYNC_DEAD_TOTAL",
    "SYNC_HASH_DRIFT",
    "SYNC_LAG_SECONDS",
    "SYNC_OUTBOX_PENDING",
    "ChunkPayload",
    "DeletePayload",
    "DocumentSyncStatus",
    "OpType",
    "SyncOutboxRow",
    "SyncStatus",
    "normalize_error_class",
    "sync_worker_loop",
]
