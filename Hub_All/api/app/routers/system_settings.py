"""System settings router — port endpoint Go-era /api/system-settings (D6).

2 endpoint khớp contract frontend React 19 (`Settings.tsx` tab Chung / Bảo mật
/ Thông báo):

    GET  /api/system-settings  — 9 key cấu hình hệ thống (authenticated)
    PUT  /api/system-settings  — update (admin-only)

NOTE — RAW JSON, KHÔNG envelope: frontend đọc `data.SYSTEM_NAME` trực tiếp
(KHÔNG `data.data.*`), và đọc `body.error` khi PUT fail. Giữ contract D6 giống
`rag_config` router → return `dict` / `JSONResponse` thuần, KHÔNG dùng
`app.pkg.response`.
"""
from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user, require_role
from app.db.session import get_session
from app.models.auth import User
from app.schemas.system_settings import TestSmtpRequest, UpdateSystemSettingsRequest
from app.services.email_service import (
    build_smtp_config_with_overrides,
    send_test_email_with_diagnostics,
)
from app.services.system_settings_service import SystemSettingsService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/system-settings", tags=["system-settings"])


@router.get("")
async def get_system_settings(
    user: User = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> dict[str, str]:
    """GET /api/system-settings — cấu hình hệ thống hiện tại. Authenticated."""
    _ = user
    return await SystemSettingsService(db=db).get_settings()


@router.put("")
async def update_system_settings(
    req: UpdateSystemSettingsRequest,
    user: User = Depends(require_role("admin")),  # noqa: B008
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> dict[str, str]:
    """PUT /api/system-settings — update settings hệ thống, admin-only."""
    return await SystemSettingsService(db=db).update_settings(
        payload=req.model_dump(exclude_none=True), updated_by=user.id
    )


@router.post("/test-smtp")
async def test_smtp(
    req: TestSmtpRequest,
    user: User = Depends(require_role("admin")),  # noqa: B008
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> dict[str, str | bool]:
    """POST /api/system-settings/test-smtp — gửi email test, admin-only.

    Build SmtpConfig từ overrides FE (form chưa save) + DB fallback. Send sync
    qua `asyncio.to_thread` tránh block event loop (smtplib timeout 15s).
    Return `{success, message}` — frontend show toast inline.
    """
    _ = user  # require_role kiểm tra role 'admin'; user dùng cho audit nếu sau này thêm.
    config = await build_smtp_config_with_overrides(db, req.overrides)
    if config is None:
        return {
            "success": False,
            "message": (
                "Chưa cấu hình đủ SMTP — cần SMTP Host + From Email tối thiểu."
            ),
        }
    success, message = await asyncio.to_thread(
        send_test_email_with_diagnostics, config, to_email=req.to_email
    )
    if success:
        return {
            "success": True,
            "message": f"Đã gửi email test tới {req.to_email}. Kiểm tra hộp thư (cả thư rác).",
        }
    logger.warning(
        "smtp_test_failed: host=%s to=%s err=%s",
        config.host,
        req.to_email,
        message,
    )
    return {"success": False, "message": message}
