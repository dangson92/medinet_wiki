"""Pydantic schemas + enums cho sync_outbox + chunks push payload.

Plan 04-03 Task 1 (SYNC-01/02):

- `SyncStatus` enum 4 value khớp Plan 04-01 sync_outbox.status CHECK.
- `OpType` enum 2 value khớp Plan 04-01 sync_outbox.op_type CHECK (D-V3-Phase4-B3).
- `DocumentSyncStatus` enum 5 value khớp Plan 04-01 documents.sync_status CHECK
  (D-V3-Phase4-B2 lifecycle).
- `ChunkPayload` parse JSONB payload từ trigger Plan 04-01 INSERT branch —
  content_hash field_validator decode hex string → bytes (BLOCKER 2 fix
  end-to-end serialization với trigger `encode(NEW.content_hash, 'hex')`).
- `DeletePayload` parse JSONB DELETE branch — key 'id' (NOT 'chunk_id') khớp
  trigger jsonb_build_object('id', OLD.id) D-V3-Phase4-B3.
- `SyncOutboxRow` Pydantic mirror toàn bộ 11 cột sync_outbox row.
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SyncStatus(enum.StrEnum):
    """sync_outbox.status enum — Plan 04-01 CHECK 4 value."""

    PENDING = "pending"
    PROCESSING = "processing"
    PROCESSED = "processed"
    DEAD = "dead"


class OpType(enum.StrEnum):
    """sync_outbox.op_type enum — D-V3-Phase4-B3 INSERT/DELETE split."""

    INSERT = "insert"
    DELETE = "delete"


class DocumentSyncStatus(enum.StrEnum):
    """documents.sync_status enum — D-V3-Phase4-B2 lifecycle 5 state.

    Transitions:
        pending (initial)
          → syncing (trigger Plan 04-01 INSERT branch first chunk, idempotent)
          → synced (worker push success all chunks)
          → failed (worker dead all chunks)
          → partial (worker mixed processed + dead)
        syncing again khi new chunks INSERT (trigger idempotent guard
        WHERE sync_status='pending' chỉ first chunk update — Plan 04-01).
    """

    PENDING = "pending"
    SYNCING = "syncing"
    SYNCED = "synced"
    FAILED = "failed"
    PARTIAL = "partial"


class ChunkPayload(BaseModel):
    """Parsed JSONB payload từ trigger Plan 04-01 INSERT branch.

    BLOCKER 2 end-to-end serialization fix:
    - Trigger Plan 04-01 emit content_hash qua `encode(NEW.content_hash, 'hex')` →
      hex string KHÔNG có '\\x' prefix (encode hex emit raw hex unprefixed).
    - Trigger Plan 04-01 emit vector qua `to_jsonb(NEW.vector::float4[])` →
      JSON array float (Pydantic parse list[float] OK).
    - field_validator `_decode_content_hash` mode='before' decode hex string →
      bytes; bytes passthrough cho direct test (mock outbox row).
    """

    model_config = ConfigDict(extra="ignore")

    id: uuid.UUID
    document_id: uuid.UUID
    hub_id: uuid.UUID
    content: str
    content_hash: bytes  # decoded từ hex string của trigger payload
    heading_path: str | None = None
    page_start: int | None = None
    page_end: int | None = None
    vector: list[float] | None = None  # từ to_jsonb(NEW.vector::float4[])
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None

    @field_validator("content_hash", mode="before")
    @classmethod
    def _decode_content_hash(cls, v: Any) -> bytes:
        """Trigger Plan 04-01 dùng encode(content_hash, 'hex') — decode hex
        string → bytes.

        Hex string KHÔNG có '\\x' prefix (encode hex trả raw hex). Defensive
        strip '\\x' nếu có (backward-compat). Bytes passthrough cho direct
        test (mock outbox row).
        """
        if isinstance(v, bytes):
            return v
        if isinstance(v, str):
            # encode(.., 'hex') emits raw hex (no '\\x' prefix); strip defensive.
            hex_str = v[2:] if v.startswith("\\x") else v
            return bytes.fromhex(hex_str)
        raise ValueError(
            f"content_hash phải là bytes hoặc hex str, got {type(v).__name__}"
        )


class DeletePayload(BaseModel):
    """Parsed JSONB payload từ trigger Plan 04-01 DELETE branch.

    Key 'id' (NOT 'chunk_id') khớp jsonb_build_object('id', OLD.id) D-V3-Phase4-B3
    — unify schema giữa INSERT + DELETE branch (giảm boilerplate parsing).
    """

    model_config = ConfigDict(extra="ignore")

    id: uuid.UUID


class SyncOutboxRow(BaseModel):
    """Pydantic mirror của 1 row sync_outbox (Plan 04-01 schema — 11 cột)."""

    model_config = ConfigDict(extra="ignore")

    id: uuid.UUID
    op_type: OpType
    chunk_id: uuid.UUID
    document_id: uuid.UUID | None = None
    payload: dict[str, Any]
    attempt_count: int = 0
    last_error: str | None = None
    status: SyncStatus = SyncStatus.PENDING
    next_retry_at: datetime | None = None
    created_at: datetime
    processed_at: datetime | None = None


__all__ = [
    "ChunkPayload",
    "DeletePayload",
    "DocumentSyncStatus",
    "OpType",
    "SyncOutboxRow",
    "SyncStatus",
]
