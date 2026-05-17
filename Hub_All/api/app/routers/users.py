"""Users router — Plan 05-04 (USER-01 user CRUD + USER-02 reset-password).

7 endpoint — mọi endpoint admin-only (`require_role("admin")`; T-05-04-01
Elevation of Privilege mitigation — user CRUD là admin-only theo USER-01):

    GET    /api/users                     — list phân trang + filter
    POST   /api/users                     — create → 201
    GET    /api/users/:id                 — get single
    PUT    /api/users/:id                 — update profile fields (D-07)
    PATCH  /api/users/:id/role            — đổi role + hub assignment (D-07)
    PATCH  /api/users/:id/status          — đổi status active/disabled (D-07)
    POST   /api/users/:id/reset-password  — sinh reset token (USER-02)

D-07: update tách 3 endpoint (PUT profile / PATCH role / PATCH status) —
frontend api.ts thắng REQUIREMENTS' single `PATCH /api/users/:id`.

Contract verb/path lấy từ `frontend/src/services/api.ts` (D-07).
"""
from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_redis, require_role
from app.db.session import get_session
from app.models.auth import User
from app.pkg import response as resp
from app.schemas.users import (
    ChangeUserRoleRequest,
    ChangeUserStatusRequest,
    CreateUserRequest,
    UpdateUserRequest,
)
from app.services.user_service import UserConflictError, UserService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/users", tags=["users"])


def get_user_service(
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> UserService:
    return UserService(db=db)


@router.get("")
async def list_users(
    hub_id: str | None = None,
    role: str | None = None,
    status: str | None = None,
    search: str | None = None,
    page: int = 1,
    per_page: int = 20,
    user: User = Depends(require_role("admin")),  # noqa: B008
    service: UserService = Depends(get_user_service),  # noqa: B008
) -> JSONResponse:
    """GET /api/users — list phân trang + filter, admin-only.

    Cap per_page ≤ 100 + page ≥ 1 (DoS — pagination cap).
    """
    _ = user  # admin-only gate qua require_role.
    capped_per_page = max(1, min(per_page, 100))
    capped_page = max(1, page)
    items, total = await service.list(
        hub_id=hub_id,
        role=role,
        status=status,
        search=search,
        page=capped_page,
        per_page=capped_per_page,
    )
    return resp.paginated(
        items=[i.model_dump(mode="json") for i in items],
        page=capped_page,
        per_page=capped_per_page,
        total=total,
    )


@router.post("")
async def create_user(
    req: CreateUserRequest,
    request: Request,
    user: User = Depends(require_role("admin")),  # noqa: B008
    service: UserService = Depends(get_user_service),  # noqa: B008
) -> JSONResponse:
    """POST /api/users — create user, admin-only → 201.

    Email trùng → 409 EMAIL_CONFLICT (T-05-04-07).
    """
    request_id = getattr(request.state, "request_id", None)
    try:
        result = await service.create(
            req=req, created_by=user.id, request_id=request_id
        )
    except UserConflictError as e:
        return resp.conflict(message=str(e), code="EMAIL_CONFLICT")
    return resp.created(data=result.model_dump(mode="json"))


@router.get("/{user_id}")
async def get_user(
    user_id: str,
    user: User = Depends(require_role("admin")),  # noqa: B008
    service: UserService = Depends(get_user_service),  # noqa: B008
) -> JSONResponse:
    """GET /api/users/:id — get single user + roles, admin-only."""
    _ = user
    try:
        user_uuid = UUID(user_id)
    except ValueError:
        return resp.bad_request(
            message=f"user_id không hợp lệ: {user_id!r}",
            code="INVALID_USER_ID",
        )
    result = await service.get(user_uuid)
    if result is None:
        return resp.not_found(
            message=f"User {user_id} không tồn tại", code="NOT_FOUND"
        )
    return resp.ok(data=result.model_dump(mode="json"))


@router.put("/{user_id}")
async def update_user(
    user_id: str,
    req: UpdateUserRequest,
    user: User = Depends(require_role("admin")),  # noqa: B008
    service: UserService = Depends(get_user_service),  # noqa: B008
) -> JSONResponse:
    """PUT /api/users/:id — update profile fields (D-07), admin-only."""
    _ = user
    try:
        user_uuid = UUID(user_id)
    except ValueError:
        return resp.bad_request(
            message=f"user_id không hợp lệ: {user_id!r}",
            code="INVALID_USER_ID",
        )
    result = await service.update(user_id=user_uuid, req=req)
    if result is None:
        return resp.not_found(
            message=f"User {user_id} không tồn tại", code="NOT_FOUND"
        )
    return resp.ok(data=result.model_dump(mode="json"))


@router.patch("/{user_id}/role")
async def change_user_role(
    user_id: str,
    req: ChangeUserRoleRequest,
    user: User = Depends(require_role("admin")),  # noqa: B008
    service: UserService = Depends(get_user_service),  # noqa: B008
) -> JSONResponse:
    """PATCH /api/users/:id/role — đổi role + hub assignment (D-07), admin-only."""
    _ = user
    try:
        user_uuid = UUID(user_id)
    except ValueError:
        return resp.bad_request(
            message=f"user_id không hợp lệ: {user_id!r}",
            code="INVALID_USER_ID",
        )
    ok = await service.change_role(
        user_id=user_uuid, hub_id=req.hub_id, role=req.role
    )
    if not ok:
        return resp.not_found(
            message=f"User {user_id} không tồn tại", code="NOT_FOUND"
        )
    return resp.ok(data={"message": "Cập nhật vai trò thành công"})


@router.patch("/{user_id}/status")
async def change_user_status(
    user_id: str,
    req: ChangeUserStatusRequest,
    user: User = Depends(require_role("admin")),  # noqa: B008
    service: UserService = Depends(get_user_service),  # noqa: B008
) -> JSONResponse:
    """PATCH /api/users/:id/status — đổi status active/disabled (D-07), admin-only."""
    _ = user
    try:
        user_uuid = UUID(user_id)
    except ValueError:
        return resp.bad_request(
            message=f"user_id không hợp lệ: {user_id!r}",
            code="INVALID_USER_ID",
        )
    ok = await service.change_status(user_id=user_uuid, status=req.status)
    if not ok:
        return resp.not_found(
            message=f"User {user_id} không tồn tại", code="NOT_FOUND"
        )
    return resp.ok(data={"message": "Cập nhật trạng thái thành công"})


@router.post("/{user_id}/reset-password")
async def reset_user_password(
    user_id: str,
    redis: Redis | None = Depends(get_redis),  # noqa: B008
    user: User = Depends(require_role("admin")),  # noqa: B008
    service: UserService = Depends(get_user_service),  # noqa: B008
) -> JSONResponse:
    """POST /api/users/:id/reset-password — sinh reset token (USER-02), admin-only.

    Token CHỈ log console (M2 — email defer v4.0). KHÔNG trả token trong
    response body (T-05-04-04 — tránh leak qua API cho phép account takeover).
    """
    _ = user
    try:
        user_uuid = UUID(user_id)
    except ValueError:
        return resp.bad_request(
            message=f"user_id không hợp lệ: {user_id!r}",
            code="INVALID_USER_ID",
        )
    token = await service.reset_password(user_id=user_uuid, redis=redis)
    if token is None:
        return resp.not_found(
            message=f"User {user_id} không tồn tại", code="NOT_FOUND"
        )
    return resp.ok(
        data={
            "message": "Token reset đã sinh (xem console log — email defer v4.0)"
        }
    )
