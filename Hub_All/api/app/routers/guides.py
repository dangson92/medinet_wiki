"""Router /api/guides — tài liệu hướng dẫn sử dụng Medinet Wiki public.

Mount central-only (FACTOR-02 carry forward — xem `app/main.py`). Hub con
strip → 404 envelope D6 (frontend dùng `requestAbsolute('/api/guides')`
qua Caddy `/api/*` → python-api-central).

Permission:
- Read (list + get): `get_current_user` — mọi user đã đăng nhập đều xem được
  (yêu cầu "tất cả user đều xem được", scope toàn hệ thống).
- Write (create/update/delete): `require_role("admin")` — chỉ super-admin
  toàn hệ thống mới được sửa hướng dẫn chung.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user, require_role
from app.db.session import get_session
from app.models.auth import User
from app.pkg import response as resp
from app.schemas.guides import GuideCreateRequest, GuideUpdateRequest
from app.services.guide_service import (
    GuideNotFoundError,
    create_guide,
    delete_guide,
    get_guide,
    list_guides,
    update_guide,
)

router = APIRouter(prefix="/api/guides", tags=["guides"])


@router.get("")
async def list_guides_endpoint(
    _user: User = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> JSONResponse:
    items = await list_guides(db)
    return resp.ok(data=items)


@router.get("/{guide_id}")
async def get_guide_endpoint(
    guide_id: UUID,
    _user: User = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> JSONResponse:
    try:
        guide = await get_guide(db, guide_id)
    except GuideNotFoundError:
        return resp.not_found(message="Không tìm thấy bài hướng dẫn")
    return resp.ok(data=guide)


@router.post("")
async def create_guide_endpoint(
    req: GuideCreateRequest,
    user: User = Depends(require_role("admin")),  # noqa: B008
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> JSONResponse:
    guide = await create_guide(
        db, title=req.title, content=req.content, actor_id=user.id
    )
    return resp.created(data=guide)


@router.put("/{guide_id}")
async def update_guide_endpoint(
    guide_id: UUID,
    req: GuideUpdateRequest,
    user: User = Depends(require_role("admin")),  # noqa: B008
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> JSONResponse:
    try:
        guide = await update_guide(
            db,
            guide_id=guide_id,
            title=req.title,
            content=req.content,
            actor_id=user.id,
        )
    except GuideNotFoundError:
        return resp.not_found(message="Không tìm thấy bài hướng dẫn")
    return resp.ok(data=guide)


@router.delete("/{guide_id}")
async def delete_guide_endpoint(
    guide_id: UUID,
    _user: User = Depends(require_role("admin")),  # noqa: B008
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> JSONResponse:
    try:
        await delete_guide(db, guide_id=guide_id)
    except GuideNotFoundError:
        return resp.not_found(message="Không tìm thấy bài hướng dẫn")
    return resp.ok(data={"deleted": True})
