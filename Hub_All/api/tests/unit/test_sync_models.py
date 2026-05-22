"""Phase 4 Plan 04-03 Task 1 — Unit test sync.keys + sync.models.

Verify:
- stable_chunk_id re-export từ rag.flow (KHÔNG duplicate logic).
- SyncStatus enum 4 value (pending/processing/processed/dead).
- OpType enum 2 value (insert/delete).
- DocumentSyncStatus enum 5 value (pending/syncing/synced/failed/partial) khớp
  Plan 04-01 CHECK constraint.
- ChunkPayload Pydantic parse hex string content_hash → bytes (BLOCKER 2 fix —
  trigger Plan 04-01 emit qua encode(NEW.content_hash, 'hex') KHÔNG có \\x prefix).
- ChunkPayload passthrough bytes nếu test mock pass raw bytes.
- ChunkPayload invalid hash type → ValidationError.
- DeletePayload parse {"id": "<uuid>"} (key 'id' NOT 'chunk_id') — khớp trigger
  Plan 04-01 DELETE branch jsonb_build_object('id', OLD.id).
- SyncOutboxRow full parse 11 cột Plan 04-01 schema.
- op_type invalid → ValidationError.
- SQL constants exports (CLAIM_PENDING_SQL, MARK_PROCESSED_SQL, MARK_DEAD_SQL,
  MARK_FAILED_RETRY_SQL, PUSH_INSERT_CHUNK_SQL, PUSH_DELETE_CHUNK_SQL,
  UPDATE_DOC_SYNC_STATUS_SQL).
- UPDATE_DOC_SYNC_STATUS_SQL CASE branches cover 4 lifecycle state (synced/failed/
  partial/syncing) — BLOCKER 1 fix verify.

Decision traceability:
- D-V3-Phase4-A2 (sync_outbox schema 11 cột)
- D-V3-Phase4-A5 (worker config LOCKED)
- D-V3-Phase4-B1 (ON CONFLICT (id) DO UPDATE WHERE content_hash IS DISTINCT)
- D-V3-Phase4-B2 (documents.sync_status lifecycle 4 transition state)
- D-V3-Phase4-B3 (op_type INSERT/DELETE split + DELETE payload key 'id')
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError


# ────────────────────────────────────────────────────────────────────
# Test 1: stable_chunk_id re-export
# ────────────────────────────────────────────────────────────────────


def test_stable_chunk_id_reexport() -> None:
    """sync.keys.stable_chunk_id phải là cùng function với rag.flow.stable_chunk_id."""
    from app.rag.flow import stable_chunk_id as orig
    from app.sync.keys import stable_chunk_id as reexport

    # Identity check (same function object) — re-export not duplicate.
    assert reexport is orig
    # Functional check — output deterministic same.
    doc_id = uuid.UUID("12345678-1234-5678-1234-567812345678")
    assert reexport(doc_id, 0) == orig(doc_id, 0)
    assert reexport(doc_id, 5) == orig(doc_id, 5)


# ────────────────────────────────────────────────────────────────────
# Test 2-4: Enums
# ────────────────────────────────────────────────────────────────────


def test_sync_status_enum() -> None:
    """SyncStatus enum 4 value khớp Plan 04-01 CHECK (status)."""
    from app.sync.models import SyncStatus

    assert SyncStatus.PENDING.value == "pending"
    assert SyncStatus.PROCESSING.value == "processing"
    assert SyncStatus.PROCESSED.value == "processed"
    assert SyncStatus.DEAD.value == "dead"
    # Str enum — equals string literal.
    assert SyncStatus.PENDING == "pending"


def test_op_type_enum() -> None:
    """OpType enum 2 value khớp Plan 04-01 CHECK (op_type) + D-V3-Phase4-B3."""
    from app.sync.models import OpType

    assert OpType.INSERT.value == "insert"
    assert OpType.DELETE.value == "delete"
    assert OpType.INSERT == "insert"


def test_document_sync_status_enum() -> None:
    """DocumentSyncStatus enum 5 value khớp Plan 04-01 CHECK (sync_status)."""
    from app.sync.models import DocumentSyncStatus

    assert DocumentSyncStatus.PENDING.value == "pending"
    assert DocumentSyncStatus.SYNCING.value == "syncing"
    assert DocumentSyncStatus.SYNCED.value == "synced"
    assert DocumentSyncStatus.FAILED.value == "failed"
    assert DocumentSyncStatus.PARTIAL.value == "partial"


# ────────────────────────────────────────────────────────────────────
# Test 5-8: ChunkPayload + DeletePayload
# ────────────────────────────────────────────────────────────────────


def test_chunk_payload_parse_hex_content_hash() -> None:
    """BLOCKER 2 fix verify — trigger Plan 04-01 emit content_hash qua
    encode(.., 'hex') = 64 char hex string KHÔNG có '\\x' prefix.

    ChunkPayload field_validator decode hex string → bytes (32 bytes SHA-256).
    """
    from app.sync.models import ChunkPayload

    raw_bytes = b"\xab" * 32  # 32 byte SHA-256-style
    hex_str = raw_bytes.hex()  # 64 char hex no prefix
    assert len(hex_str) == 64
    assert "\\x" not in hex_str

    payload = ChunkPayload(
        id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        hub_id=uuid.uuid4(),
        content="Test content",
        content_hash=hex_str,  # type: ignore[arg-type]  # validator decode hex → bytes
        vector=[0.1, 0.2, 0.3],
    )
    assert payload.content_hash == raw_bytes
    assert len(payload.content_hash) == 32


def test_chunk_payload_parse_bytes_content_hash_passthrough() -> None:
    """Mock test pass raw bytes — validator passthrough KHÔNG raise."""
    from app.sync.models import ChunkPayload

    raw_bytes = b"\xcd" * 32
    payload = ChunkPayload(
        id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        hub_id=uuid.uuid4(),
        content="Test content",
        content_hash=raw_bytes,
    )
    assert payload.content_hash == raw_bytes


def test_chunk_payload_invalid_hash_raises() -> None:
    """Pass int → ValidationError fail-fast (cardinality wrong type)."""
    from app.sync.models import ChunkPayload

    with pytest.raises(ValidationError) as exc:
        ChunkPayload(
            id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            hub_id=uuid.uuid4(),
            content="Test",
            content_hash=12345,  # type: ignore[arg-type]
        )
    # Pydantic message chứa từ "bytes" hoặc "hex" hoặc "type" — không strict text
    assert "content_hash" in str(exc.value).lower() or "bytes" in str(exc.value).lower()


def test_delete_payload_parse_key_id_not_chunk_id() -> None:
    """Plan 04-01 trigger DELETE branch emit jsonb_build_object('id', OLD.id) —
    Pydantic DeletePayload parse key 'id' (NOT 'chunk_id')."""
    from app.sync.models import DeletePayload

    doc_uuid = uuid.uuid4()
    payload = DeletePayload(id=doc_uuid)
    assert payload.id == doc_uuid


# ────────────────────────────────────────────────────────────────────
# Test 9-10: SyncOutboxRow
# ────────────────────────────────────────────────────────────────────


def test_sync_outbox_row_full_parse() -> None:
    """Full 11 cột Plan 04-01 schema → SyncOutboxRow parse OK."""
    from app.sync.models import OpType, SyncOutboxRow, SyncStatus

    chunk_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    row = SyncOutboxRow.model_validate(
        {
            "id": uuid.uuid4(),
            "op_type": "insert",
            "chunk_id": chunk_id,
            "document_id": doc_id,
            "payload": {"id": str(chunk_id), "content": "x"},
            "attempt_count": 0,
            "last_error": None,
            "status": "pending",
            "next_retry_at": None,
            "created_at": datetime.now(timezone.utc),
            "processed_at": None,
        }
    )
    assert row.op_type == OpType.INSERT
    assert row.status == SyncStatus.PENDING
    assert row.chunk_id == chunk_id
    assert row.document_id == doc_id
    assert row.attempt_count == 0


def test_outbox_row_validates_op_type_invalid() -> None:
    """op_type="invalid" → ValidationError (enum constraint)."""
    from app.sync.models import SyncOutboxRow

    with pytest.raises(ValidationError):
        SyncOutboxRow.model_validate(
            {
                "id": uuid.uuid4(),
                "op_type": "invalid_op",
                "chunk_id": uuid.uuid4(),
                "payload": {},
                "created_at": datetime.now(timezone.utc),
            }
        )


# ────────────────────────────────────────────────────────────────────
# Test 11-12: SQL constants
# ────────────────────────────────────────────────────────────────────


def test_outbox_sql_constants_exported() -> None:
    """keys.py exports tất cả SQL constants với pattern phải có."""
    from app.sync import keys

    assert "FOR UPDATE SKIP LOCKED" in keys.CLAIM_PENDING_SQL
    assert "status = 'processed'" in keys.MARK_PROCESSED_SQL
    assert "status = 'dead'" in keys.MARK_DEAD_SQL
    assert "ON CONFLICT (id) DO UPDATE" in keys.PUSH_INSERT_CHUNK_SQL
    assert (
        "chunks.content_hash IS DISTINCT FROM EXCLUDED.content_hash"
        in keys.PUSH_INSERT_CHUNK_SQL
    )
    assert "DELETE FROM chunks" in keys.PUSH_DELETE_CHUNK_SQL
    # BLOCKER 1 fix — D-V3-Phase4-B2 lifecycle aggregate.
    assert "UPDATE documents" in keys.UPDATE_DOC_SYNC_STATUS_SQL
    assert "sync_status" in keys.UPDATE_DOC_SYNC_STATUS_SQL


def test_update_doc_sql_aggregate_state_all_4_branches() -> None:
    """UPDATE_DOC_SYNC_STATUS_SQL CASE phải cover all 4 lifecycle state.

    BLOCKER 1 fix verify — D-V3-Phase4-B2:
    - 'synced' (no pending/processing + no dead)
    - 'failed' (no pending/processing + all dead)
    - 'partial' (no pending/processing + mixed dead + processed)
    - 'syncing' (còn pending/processing)
    """
    from app.sync.keys import UPDATE_DOC_SYNC_STATUS_SQL

    assert "'synced'" in UPDATE_DOC_SYNC_STATUS_SQL
    assert "'failed'" in UPDATE_DOC_SYNC_STATUS_SQL
    assert "'partial'" in UPDATE_DOC_SYNC_STATUS_SQL
    assert "'syncing'" in UPDATE_DOC_SYNC_STATUS_SQL
