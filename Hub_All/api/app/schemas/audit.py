"""Audit log schemas — Pydantic v2 (Plan 05-05, AUX-01).

Contract endpoint lấy từ `frontend/src/services/api.ts` (D-07).

`AuditLogAPI` (api.ts ~578): id, timestamp, user_id?, user_name?, is_ai, action,
target?, hub_id?, hub_name?, ip_address?, user_agent?, request_id?, duration_ms?,
payload?.

LƯU Ý — field không có cột `audit_logs` (M2 schema tối thiểu):
- `ip_address` / `user_agent` / `duration_ms` → trả None hằng số.
- `is_ai` → trả False hằng số (M2 chưa phân biệt actor AI vs người).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class AuditLogResponse(BaseModel):
    """GET /api/audit-logs response item — AuditLogAPI contract frontend."""

    id: str  # UUID string
    timestamp: datetime  # map từ audit_logs.created_at
    user_id: str | None
    user_name: str | None  # map từ users.full_name (LEFT JOIN)
    is_ai: bool = False
    action: str
    target: str | None  # map từ audit_logs.target_id
    hub_id: str | None
    hub_name: str | None  # map từ hubs.name (LEFT JOIN)
    ip_address: str | None = None
    user_agent: str | None = None
    request_id: str | None
    duration_ms: int | None = None
    payload: dict[str, Any] | None
