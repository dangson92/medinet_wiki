"""Document schemas — Pydantic v2.

D6 contract: payload documents PHẢI shape-identical với Go `model.Document`
(field `name` / `file_type` / `file_size` / `progress` / `uploaded_at` /
`processed_at`). Frontend React 19 `services/api.ts` interface `DocumentAPI`
đọc đúng các field này — đổi tên field sẽ break frontend (KHÔNG sửa frontend M2).

Phase 4 trước đây trả `filename` / `mime_type` / `file_size_bytes` / `created_at`
→ lệch contract → frontend crash `doc.name.toLowerCase()`. Bản này đưa shape về
đúng Go cũ.

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

# Bảng `documents` Python KHÔNG có cột `progress` (khác Go cũ). Derive progress
# 0-100 từ status để giữ field `progress` trong contract D6 — frontend hiển thị
# progress bar + getPipelineStage() dựa trên số này.
_PROGRESS_BY_STATUS: dict[str, int] = {
    "pending": 0,
    "processing": 50,
    "completed": 100,
    "failed": 0,
    "failed_unsupported": 0,
}

# Status coi như đã xử lý xong → processed_at có giá trị (= updated_at).
TERMINAL_STATUSES: frozenset[str] = frozenset(
    {"completed", "failed", "failed_unsupported"}
)


def progress_for_status(status: str) -> int:
    """Derive progress 0-100 từ status (documents không có cột progress)."""
    return _PROGRESS_BY_STATUS.get(status, 0)


class DocumentResponse(BaseModel):
    """Document payload — shape-identical Go `model.Document` (D6).

    Dùng chung cho 3 endpoint: POST /upload (202), GET /:id (200),
    GET / list (200). Frontend `DocumentAPI` đọc trực tiếp shape này.
    """

    id: str  # UUID string
    name: str  # = documents.filename
    file_type: str  # derive từ đuôi file (vd "docx", "pdf")
    file_size: int  # = documents.file_size_bytes
    file_path: str
    hub_id: str  # UUID string
    status: DocumentStatus
    progress: int  # derive từ status (xem progress_for_status)
    error_message: str | None = None
    chunk_count: int
    uploaded_by: str | None  # UUID string hoặc None nếu user bị xoá (FK SET NULL)
    uploaded_at: datetime  # = documents.created_at
    processed_at: datetime | None = None  # = updated_at khi status terminal
