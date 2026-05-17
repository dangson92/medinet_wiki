"""Hubs router — Plan 05-03 (HUB-01 hub registry CRUD + HUB-03 stats).

6 endpoint — mọi endpoint admin-only (`require_role("admin")`; T-05-03-01
Elevation of Privilege mitigation — hub CRUD là admin-only theo HUB-01):

    GET    /api/hubs              — list phân trang (per_page cap ≤ 100)
    POST   /api/hubs              — create → 201
    GET    /api/hubs/:id          — get single
    PUT    /api/hubs/:id          — update (PUT KHÔNG PATCH — D-07)
    PATCH  /api/hubs/:id/status   — đổi status active/inactive
    GET    /api/hubs/:id/stats    — counts Postgres aggregate (HUB-03)

D-06: KHÔNG implement endpoint kiểm tra kết nối per-hub DB — M2 dùng 1 Postgres
chung, không có per-hub DB để test.

Contract verb/path lấy từ `frontend/src/services/api.ts` (D-07).
"""
from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_role
from app.db.session import get_session
from app.models.auth import User
from app.pkg import response as resp
from app.schemas.hubs import (
    CreateHubRequest,
    UpdateHubRequest,
    UpdateHubStatusRequest,
)
from app.services.hub_service import HubConflictError, HubService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/hubs", tags=["hubs"])


def get_hub_service(
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> HubService:
    return HubService(db=db)


@router.get("")
async def list_hubs(
    page: int = 1,
    per_page: int = 20,
    user: User = Depends(require_role("admin")),  # noqa: B008
    service: HubService = Depends(get_hub_service),  # noqa: B008
) -> JSONResponse:
    """GET /api/hubs — list phân trang, admin-only.

    Cap per_page ≤ 100 + page ≥ 1 (T-05-03 DoS — pagination cap).
    """
    _ = user  # admin-only gate qua require_role.
    capped_per_page = max(1, min(per_page, 100))
    capped_page = max(1, page)
    items, total = await service.list(
        page=capped_page, per_page=capped_per_page
    )
    return resp.paginated(
        items=[i.model_dump(mode="json") for i in items],
        page=capped_page,
        per_page=capped_per_page,
        total=total,
    )


@router.post("")
async def create_hub(
    req: CreateHubRequest,
    request: Request,
    user: User = Depends(require_role("admin")),  # noqa: B008
    service: HubService = Depends(get_hub_service),  # noqa: B008
) -> JSONResponse:
    """POST /api/hubs — create hub, admin-only → 201.

    Code/slug trùng → 409 HUB_CODE_CONFLICT (T-05-03-04).
    """
    request_id = getattr(request.state, "request_id", None)
    try:
        result = await service.create(
            req=req, created_by=user.id, request_id=request_id
        )
    except HubConflictError as e:
        return resp.conflict(message=str(e), code="HUB_CODE_CONFLICT")
    return resp.created(data=result.model_dump(mode="json"))


@router.get("/{hub_id}")
async def get_hub(
    hub_id: str,
    user: User = Depends(require_role("admin")),  # noqa: B008
    service: HubService = Depends(get_hub_service),  # noqa: B008
) -> JSONResponse:
    """GET /api/hubs/:id — get single hub, admin-only."""
    _ = user
    try:
        hub_uuid = UUID(hub_id)
    except ValueError:
        return resp.bad_request(
            message=f"hub_id không hợp lệ: {hub_id!r}",
            code="INVALID_HUB_ID",
        )
    hub = await service.get(hub_uuid)
    if hub is None:
        return resp.not_found(
            message=f"Hub {hub_id} không tồn tại", code="NOT_FOUND"
        )
    return resp.ok(data=hub.model_dump(mode="json"))


@router.put("/{hub_id}")
async def update_hub(
    hub_id: str,
    req: UpdateHubRequest,
    request: Request,
    user: User = Depends(require_role("admin")),  # noqa: B008
    service: HubService = Depends(get_hub_service),  # noqa: B008
) -> JSONResponse:
    """PUT /api/hubs/:id — update hub (PUT KHÔNG PATCH — D-07), admin-only."""
    try:
        hub_uuid = UUID(hub_id)
    except ValueError:
        return resp.bad_request(
            message=f"hub_id không hợp lệ: {hub_id!r}",
            code="INVALID_HUB_ID",
        )
    request_id = getattr(request.state, "request_id", None)
    result = await service.update(
        hub_id=hub_uuid,
        req=req,
        updated_by=user.id,
        request_id=request_id,
    )
    if result is None:
        return resp.not_found(
            message=f"Hub {hub_id} không tồn tại", code="NOT_FOUND"
        )
    return resp.ok(data=result.model_dump(mode="json"))


@router.patch("/{hub_id}/status")
async def update_hub_status(
    hub_id: str,
    req: UpdateHubStatusRequest,
    request: Request,
    user: User = Depends(require_role("admin")),  # noqa: B008
    service: HubService = Depends(get_hub_service),  # noqa: B008
) -> JSONResponse:
    """PATCH /api/hubs/:id/status — đổi status active/inactive, admin-only."""
    try:
        hub_uuid = UUID(hub_id)
    except ValueError:
        return resp.bad_request(
            message=f"hub_id không hợp lệ: {hub_id!r}",
            code="INVALID_HUB_ID",
        )
    request_id = getattr(request.state, "request_id", None)
    ok = await service.update_status(
        hub_id=hub_uuid,
        status=req.status,
        updated_by=user.id,
        request_id=request_id,
    )
    if not ok:
        return resp.not_found(
            message=f"Hub {hub_id} không tồn tại", code="NOT_FOUND"
        )
    return resp.ok(data={"message": "Cập nhật trạng thái hub thành công"})


@router.get("/{hub_id}/stats")
async def get_hub_stats(
    hub_id: str,
    user: User = Depends(require_role("admin")),  # noqa: B008
    service: HubService = Depends(get_hub_service),  # noqa: B008
) -> JSONResponse:
    """GET /api/hubs/:id/stats — counts Postgres aggregate (HUB-03), admin-only."""
    _ = user
    try:
        hub_uuid = UUID(hub_id)
    except ValueError:
        return resp.bad_request(
            message=f"hub_id không hợp lệ: {hub_id!r}",
            code="INVALID_HUB_ID",
        )
    stats = await service.stats(hub_uuid)
    if stats is None:
        return resp.not_found(
            message=f"Hub {hub_id} không tồn tại", code="NOT_FOUND"
        )
    return resp.ok(data=stats.model_dump(mode="json"))
