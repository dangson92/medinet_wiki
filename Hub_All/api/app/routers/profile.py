"""Profile router — Plan 05-04 (USER-03 profile self-scoped).

3 endpoint self-scoped — `Depends(get_current_user)` (viewer/editor/admin đều
truy cập CHO CHÍNH MÌNH; KHÔNG `require_role`):

    GET    /api/profile           — lấy profile của chính mình
    PUT    /api/profile           — cập nhật profile của chính mình
    POST   /api/profile/password  — đổi mật khẩu của chính mình

T-05-04-02 (Elevation of Privilege): router KHÔNG nhận `:id` param — `user_id`
LUÔN lấy từ JWT (`user.id`), KHÔNG từ path/payload. Viewer KHÔNG THỂ update
profile của user khác (SC3 CONTEXT).

D-07: dùng `/api/profile` (frontend api.ts thắng REQUIREMENTS' `/api/users/:id/profile`).
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.db.session import get_session
from app.models.auth import User
from app.pkg import response as resp
from app.schemas.users import ChangePasswordRequest, UpdateProfileRequest
from app.services.user_service import UserService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/profile", tags=["profile"])


def get_user_service(
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> UserService:
    return UserService(db=db)


@router.get("")
async def get_profile(
    user: User = Depends(get_current_user),  # noqa: B008
    service: UserService = Depends(get_user_service),  # noqa: B008
) -> JSONResponse:
    """GET /api/profile — lấy profile của chính mình (user.id từ JWT)."""
    result = await service.get(user.id)
    if result is None:
        return resp.not_found(
            message="Không tìm thấy profile", code="NOT_FOUND"
        )
    return resp.ok(data=result.model_dump(mode="json"))


@router.put("")
async def update_profile(
    req: UpdateProfileRequest,
    user: User = Depends(get_current_user),  # noqa: B008
    service: UserService = Depends(get_user_service),  # noqa: B008
) -> JSONResponse:
    """PUT /api/profile — cập nhật profile của chính mình (user.id từ JWT)."""
    result = await service.update_profile(user_id=user.id, req=req)
    if result is None:
        return resp.not_found(
            message="Không tìm thấy profile", code="NOT_FOUND"
        )
    return resp.ok(data=result.model_dump(mode="json"))


@router.post("/password")
async def change_password(
    req: ChangePasswordRequest,
    user: User = Depends(get_current_user),  # noqa: B008
    service: UserService = Depends(get_user_service),  # noqa: B008
) -> JSONResponse:
    """POST /api/profile/password — đổi mật khẩu của chính mình.

    Verify `old_password` trước khi đổi (T-05-04-05 Spoofing). Sai → 400.
    """
    result = await service.change_password_self(
        user_id=user.id,
        old_password=req.old_password,
        new_password=req.new_password,
    )
    if result is None:
        return resp.not_found(
            message="Không tìm thấy profile", code="NOT_FOUND"
        )
    if result is False:
        return resp.bad_request(
            message="Mật khẩu cũ không đúng", code="INVALID_PASSWORD"
        )
    return resp.ok(data={"message": "Đổi mật khẩu thành công"})
