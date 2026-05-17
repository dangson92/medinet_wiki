"""Hub schemas — Pydantic v2 (Plan 05-03, HUB-01 + HUB-03).

Contract endpoint lấy từ `frontend/src/services/api.ts` (D-07 — frontend thắng
REQUIREMENTS.md khi mâu thuẫn verb/path/field).

D-05: `HubResponse` DROP hẳn field di sản Go multi-DB + ChromaDB —
`chroma_collection`, `db_host`, `db_port`, `db_name`, `db_user`. CHỈ trả 8 field
M2 thật: id, name, code, subdomain, description, status, created_at, updated_at.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

# Hub status enum — match hubs.status CHECK constraint `hub_status_enum`
# (migration 0003: status IN ('active','inactive')).
HubStatus = Literal["active", "inactive"]


class CreateHubRequest(BaseModel):
    """POST /api/hubs body — admin tạo hub mới.

    D-05: KHÔNG có chroma_collection / db_* (di sản Go drop hẳn).
    """

    name: str = Field(min_length=1, max_length=200)
    code: str = Field(min_length=1, max_length=50)
    subdomain: str = Field(min_length=1, max_length=100)
    description: str | None = None


class UpdateHubRequest(BaseModel):
    """PUT /api/hubs/:id body — admin cập nhật hub.

    D-07: PUT update (KHÔNG PATCH) — chỉ name/description. db_* bỏ qua (D-05).
    """

    name: str | None = Field(default=None, max_length=200)
    description: str | None = None


class UpdateHubStatusRequest(BaseModel):
    """PATCH /api/hubs/:id/status body — đổi trạng thái hub."""

    status: HubStatus


class HubResponse(BaseModel):
    """GET /api/hubs(:id) response data — HubAPI contract frontend.

    D-05: CHỈ 8 field này. KHÔNG chroma_collection / db_host / db_port /
    db_name / db_user (di sản Go multi-DB-per-hub).
    """

    id: str  # UUID string
    name: str
    code: str
    subdomain: str
    description: str | None
    status: HubStatus
    created_at: datetime
    updated_at: datetime | None


class HubStats(BaseModel):
    """GET /api/hubs/:id/stats response data — HUB-03.

    Phase 5 CHỈ ship 3 count. `query_count` defer Phase 6/7 (chưa có nguồn
    dữ liệu query — search endpoint Phase 6, usage_events data Phase 7).
    """

    hub_id: str  # UUID string
    document_count: int
    chunk_count: int
    user_count: int
