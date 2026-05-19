"""Sync router — COMPAT STUB cho endpoint Go-era `/api/sync/*` (D6).

Bối cảnh: frontend React 19 (D6 — KHÔNG sửa trong M2) vẫn gọi nhóm endpoint
`/api/sync/*` của backend Go cũ (hàng đợi duyệt batch đồng bộ tri thức từ Hub
Dự Án). M2 Full RAG Rewrite KHÔNG port feature này — ROADMAP M2 (10 phase,
38 REQ-ID) không có sync-queue, ingestion M2 = upload document trực tiếp →
cocoindex. Không route `/api/sync/*` → frontend nhận 404 → Dashboard.tsx +
SyncQueue.tsx log lỗi `Failed to fetch`.

Stub này trả envelope hợp lệ với dữ liệu RỖNG (hàng đợi vĩnh viễn trống vì M2
không có nguồn sync) → Dashboard + SyncQueue render trạng thái empty bình
thường, KHÔNG còn 404. Endpoint thao tác (submit/approve/reject) + xem chi
tiết batch trả `404 NOT_FOUND` envelope sạch — không có batch nào để thao tác.

Khi M2 (hoặc milestone sau) thật sự cần sync queue: thay stub này bằng router
+ service + bảng `sync_batches`/`sync_pages` qua `/gsd-discuss-phase` (thêm
REQ-ID mới — KHÔNG sửa lén ở đây).
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from app.auth.dependencies import get_current_user
from app.models.auth import User
from app.pkg import response as resp

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sync", tags=["sync"])

_STUB_MSG = (
    "Hàng đợi Sync không khả dụng ở M2 — feature chưa được port từ backend Go cũ."
)


@router.get("/stats")
async def sync_stats(
    user: User = Depends(get_current_user),  # noqa: B008
) -> JSONResponse:
    """GET /api/sync/stats — compat stub. Hàng đợi luôn trống ở M2.

    Dashboard.tsx gọi endpoint này cho mọi user đã đăng nhập → chỉ yêu cầu
    authenticated (KHÔNG admin-only) để không sinh lỗi 403 ở trang landing.
    """
    _ = user
    return resp.ok(data={"pending_batches": 0, "pending_pages": 0})


@router.get("/batches")
async def list_sync_batches(
    hub_id: str | None = Query(None),
    status: str | None = Query(None),
    page: int = Query(1),
    per_page: int = Query(20),
    user: User = Depends(get_current_user),  # noqa: B008
) -> JSONResponse:
    """GET /api/sync/batches — compat stub. Trả list rỗng + meta.total=0."""
    _ = (user, hub_id, status)
    return resp.paginated(items=[], page=page, per_page=per_page, total=0)


@router.get("/batches/{batch_id}")
async def get_sync_batch(
    batch_id: str,
    user: User = Depends(get_current_user),  # noqa: B008
) -> JSONResponse:
    """GET /api/sync/batches/{id} — compat stub. Không có batch nào → 404."""
    _ = (user, batch_id)
    return resp.not_found(_STUB_MSG, code="SYNC_NOT_AVAILABLE")


@router.post("/batches")
async def submit_sync_batch(
    user: User = Depends(get_current_user),  # noqa: B008
) -> JSONResponse:
    """POST /api/sync/batches — compat stub. M2 không nhận batch sync mới."""
    _ = user
    return resp.not_found(_STUB_MSG, code="SYNC_NOT_AVAILABLE")


@router.post("/batches/{batch_id}/pages/{page_id}/approve")
async def approve_sync_page(
    batch_id: str,
    page_id: str,
    user: User = Depends(get_current_user),  # noqa: B008
) -> JSONResponse:
    """POST .../approve — compat stub. Không có batch/page nào để duyệt → 404."""
    _ = (user, batch_id, page_id)
    return resp.not_found(_STUB_MSG, code="SYNC_NOT_AVAILABLE")


@router.post("/batches/{batch_id}/pages/{page_id}/reject")
async def reject_sync_page(
    batch_id: str,
    page_id: str,
    user: User = Depends(get_current_user),  # noqa: B008
) -> JSONResponse:
    """POST .../reject — compat stub. Không có batch/page nào để từ chối → 404."""
    _ = (user, batch_id, page_id)
    return resp.not_found(_STUB_MSG, code="SYNC_NOT_AVAILABLE")
