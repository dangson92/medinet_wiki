"""Users router — Plan 05-04 (USER-01 CRUD + USER-02 reset) + Phase 2 Plan 02-03 DEP-03.

8 endpoint — Phase 2 Plan 02-03 refactor 4 endpoint scope hub_admin (DEP-03 +
D-V3.1-Phase2-D/E LOCKED + B1 iter 1), 4 endpoint giữ super-only require_role:

    GET    /api/users                     — list (scope: get_current_user + hub_admin gate)
    POST   /api/users                     — create (scope: get_current_user + assert_hub_admin_for)
    GET    /api/users/:id                 — get single (super-only require_role — defer)
    PUT    /api/users/:id                 — update profile (super-only require_role — defer)
    PATCH  /api/users/:id/role            — đổi role (scope + T-02-02-E block escalation)
    PATCH  /api/users/:id/status          — đổi status (super-only D-V3.1-Phase2-E LOCKED)
    DELETE /api/users/:id                 — delete (B1 iter 1 branch single-hub vs cross-hub)
    POST   /api/users/:id/reset-password  — sinh reset token (super-only USER-02 carry forward)

Phase 2 Plan 02-03 envelope code:
- HUB_ADMIN_REQUIRED (403) — assert_hub_admin_for scope violation (POST/PATCH role/GET list/DELETE other-hub).
- CROSS_HUB_USER_DELETE_DENIED (403) — B1 iter 1 DELETE user thuộc nhiều hub (super only).
- HUB_ID_REQUIRED (400) — GET list non-super-admin thiếu hub_id query.
- FORBIDDEN (403) — require_role existing cho 4 endpoint giữ super-only.

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
from sqlalchemy import text  # B1 iter 1 — query user_hubs membership trong DELETE handler.
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import (
    assert_hub_admin_for,   # Phase 2 Plan 02-01 — DEP-01 validator function (D-V3.1-Phase2-B).
    get_current_user,       # Phase 2 Plan 02-03 — replace require_role cho 4 endpoint scope hub_admin.
    get_redis,
    require_role,           # GIỮ — vẫn dùng cho PATCH status + reset-password + GET single + PUT.
)
from app.db.session import get_session
from app.models.auth import User
from app.pkg import response as resp
from app.schemas.users import (
    ChangeUserRoleRequest,
    ChangeUserStatusRequest,
    CreateUserRequest,
    UpdateUserRequest,
)
from app.services.user_service import (
    LastAdminError,
    UserConflictError,
    UserService,
)

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
    user: User = Depends(get_current_user),  # noqa: B008 — Phase 2 Plan 02-03 thay require_role
    db: AsyncSession = Depends(get_session),  # noqa: B008 — Phase 2 cho assert_hub_admin_for
    service: UserService = Depends(get_user_service),  # noqa: B008
) -> JSONResponse:
    """GET /api/users — list phân trang + filter (Phase 2 DEP-03).

    Super admin → list any user (hub_id query optional). Hub_admin → REQUIRED
    hub_id query + assert_hub_admin_for gate (chỉ list user trong hub được gán
    quyền). Envelope code HUB_ID_REQUIRED phân biệt với HUB_ADMIN_REQUIRED.

    Cap per_page ≤ 100 + page ≥ 1 (DoS — pagination cap).
    """
    # DEP-03 — super admin bypass, hub_admin REQUIRED hub_id + scope check.
    if user.role != "admin":
        if hub_id is None:
            return resp.bad_request(
                message=(
                    "hub_id query REQUIRED cho non-super-admin — "
                    "hub_admin chỉ list user trong hub được gán quyền"
                ),
                code="HUB_ID_REQUIRED",
            )
        await assert_hub_admin_for(user=user, db=db, target_hub_id=hub_id)

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
    user: User = Depends(get_current_user),  # noqa: B008 — Phase 2 Plan 02-03 thay require_role("admin")
    db: AsyncSession = Depends(get_session),  # noqa: B008 — Phase 2 cho assert_hub_admin_for
    service: UserService = Depends(get_user_service),  # noqa: B008
) -> JSONResponse:
    """POST /api/users — create user, scope per role (Phase 2 DEP-03 D-V3.1-Phase2-D LOCKED).

    Super admin → tạo user any hub. Hub_admin → CHỈ tạo user trong hub được gán
    quyền (assert_hub_admin_for gate). Email trùng → 409 EMAIL_CONFLICT (T-05-04-07).
    """
    # DEP-03 — inline scope check sau body parse (hybrid pattern D-V3.1-Phase2-D LOCKED).
    await assert_hub_admin_for(user=user, db=db, target_hub_id=req.hub_id)

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
    user: User = Depends(get_current_user),  # noqa: B008 — Phase 2 Plan 02-03 thay require_role
    db: AsyncSession = Depends(get_session),  # noqa: B008 — Phase 2 cho assert_hub_admin_for
    service: UserService = Depends(get_user_service),  # noqa: B008
) -> JSONResponse:
    """PATCH /api/users/:id/role — đổi role + hub assignment (Phase 2 DEP-03 + T-02-02-E).

    Super admin → đổi role any hub any user. Hub_admin → CHỈ đổi role trong hub
    được gán quyền + KHÔNG được escalate role='admin' (T-02-02-E mitigation
    D-V3.1-Phase2-D LOCKED). Envelope code HUB_ADMIN_REQUIRED phân biệt với
    FORBIDDEN (require_role existing) cho frontend FE-01 UX.
    """
    # DEP-03 — scope check.
    await assert_hub_admin_for(user=user, db=db, target_hub_id=req.hub_id)

    # T-02-02-E mitigation — hub_admin KHÔNG được gán role='admin' (super) cho user khác.
    if req.role == "admin" and user.role != "admin":
        return resp.forbidden(
            message=(
                "Hub_admin KHÔNG được gán role 'admin' (super admin toàn hệ thống) "
                "cho user khác — chỉ super admin mới có quyền này"
            ),
            code="HUB_ADMIN_REQUIRED",
        )

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


@router.delete("/{user_id}")
async def delete_user(
    user_id: str,
    request: Request,
    user: User = Depends(get_current_user),  # noqa: B008 — B1 iter 1 thay require_role
    db: AsyncSession = Depends(get_session),  # noqa: B008 — B1 iter 1 cho query user_hubs membership
    service: UserService = Depends(get_user_service),  # noqa: B008
) -> JSONResponse:
    """DELETE /api/users/:id — Phase 2 Plan 02-03 B1 iter 1 DEP-03 spec compliance.

    Branch (D-V3.1-Phase2-E narrowed bởi B1 iter 1):
    - Super admin (user.role='admin' global) → pass (cross-hub by design).
    - Hub_admin: query user_hubs membership target user.
      * Target thuộc CHỈ 1 hub VÀ hub đó = caller's hub_admin scope
        (assert_hub_admin_for pass) → pass.
      * Target thuộc nhiều hub → 403 CROSS_HUB_USER_DELETE_DENIED.
      * Target thuộc 1 hub khác (KHÔNG phải scope mình)
        → 403 HUB_ADMIN_REQUIRED (qua assert_hub_admin_for raise).
      * Target KHÔNG có hub membership (orphan) → 403 HUB_ADMIN_REQUIRED
        (chỉ super admin được xoá orphan).

    Block:
    - Self-delete → 403 CANNOT_DELETE_SELF (self-DoS prevention).
    - Last active admin → 409 LAST_ADMIN (system phải còn ≥ 1 admin).

    Cascade (M2 carry forward):
    - refresh_tokens + user_hubs + mcp_oauth_clients ON DELETE CASCADE → cleanup.
    - documents/audit_logs/usage_events/api_keys/settings ON DELETE SET NULL →
      giữ trail, anonymize owner (compliance audit non-repudiation).
    """
    try:
        user_uuid = UUID(user_id)
    except ValueError:
        return resp.bad_request(
            message=f"user_id không hợp lệ: {user_id!r}",
            code="INVALID_USER_ID",
        )

    if user_uuid == user.id:
        return resp.forbidden(
            message=(
                "Không thể tự xoá tài khoản của chính mình. "
                "Nhờ admin khác xoá hoặc reset password."
            ),
            code="CANNOT_DELETE_SELF",
        )

    # B1 iter 1 — branch single-hub vs cross-hub (DEP-03 spec compliance +
    # D-V3.1-Phase2-E narrowing).
    if user.role != "admin":
        # Hub_admin path — query user_hubs membership target user.
        # Named bind param :target_id (T-01-02-01 mitigation Plan 01-02 carry forward).
        result = await db.execute(
            text(
                "SELECT hub_id FROM user_hubs WHERE user_id = :target_id"
            ),
            {"target_id": str(user_uuid)},
        )
        target_hub_ids = [str(h) for h in result.scalars().all()]

        if len(target_hub_ids) > 1:
            # Cross-hub user — chỉ super admin được xoá.
            return resp.forbidden(
                message=(
                    "Chỉ super admin được xoá user thuộc nhiều hub "
                    f"(user target có membership ở {len(target_hub_ids)} hub)"
                ),
                code="CROSS_HUB_USER_DELETE_DENIED",
            )

        if len(target_hub_ids) == 1:
            # Single-hub user — hub_admin của hub đó được xoá.
            # assert_hub_admin_for raise 403 HUB_ADMIN_REQUIRED nếu caller
            # KHÔNG phải hub_admin của hub đó.
            await assert_hub_admin_for(
                user=user, db=db, target_hub_id=target_hub_ids[0]
            )
        else:
            # len == 0 — orphan user, chỉ super admin được xoá.
            return resp.forbidden(
                message=(
                    "Chỉ super admin được xoá user KHÔNG có hub membership "
                    "(orphan user)"
                ),
                code="HUB_ADMIN_REQUIRED",
            )

    request_id = getattr(request.state, "request_id", None)
    try:
        deleted = await service.delete(
            user_id=user_uuid,
            deleted_by=user.id,
            request_id=request_id,
        )
    except LastAdminError as e:
        return resp.conflict(message=str(e), code="LAST_ADMIN")
    if not deleted:
        return resp.not_found(
            message=f"User {user_id} không tồn tại", code="NOT_FOUND"
        )
    return resp.ok(data={"message": "Đã xoá user"})


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
