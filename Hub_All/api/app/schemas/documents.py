"""Document schemas — Pydantic v2.

Plan 04-04 ship:
- DocumentStatus Literal — match documents.status CHECK enum (R4 + P8).
- DocumentResponse — GET /api/documents/:id payload.
- DocumentListItem — GET /api/documents list item (Plan 04-05).
- DocumentUploadResponse — POST upload 202 response.

INGEST-05: status enum đúng 5 giá trị: pending | processing | completed |
failed | failed_unsupported.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

DocumentStatus = Literal[
    "pending",
    "processing",
    "completed",
    "failed",
    "failed_unsupported",
]

DOCUMENT_STATUS_VALUES: tuple[DocumentStatus, ...] = (
    "pending",
    "processing",
    "completed",
    "failed",
    "failed_unsupported",
)


class DocumentResponse(BaseModel):
    """Single document detail — GET /api/documents/:id response data."""

    id: str  # UUID string
    hub_id: str  # UUID string
    uploaded_by: str | None  # UUID string hoặc None nếu user bị xoá (FK SET NULL)
    filename: str
    file_path: str
    mime_type: str | None
    file_size_bytes: int | None
    status: DocumentStatus
    error_message: str | None
    last_heartbeat: datetime | None
    attempts: int
    chunk_count: int
    created_at: datetime
    updated_at: datetime | None


class DocumentListItem(BaseModel):
    """List item — GET /api/documents (Plan 04-05). Compact subset."""

    id: str
    hub_id: str
    filename: str
    status: DocumentStatus
    chunk_count: int
    created_at: datetime
    updated_at: datetime | None


class DocumentUploadResponse(BaseModel):
    """POST /api/documents/upload response data — 202 Accepted."""

    document_id: str
    status: DocumentStatus
    filename: str
