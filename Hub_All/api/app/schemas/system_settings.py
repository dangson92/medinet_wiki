"""System settings schema — body PUT /api/system-settings.

Khớp `saveSystemSettings()` frontend Settings.tsx (tab Chung / Bảo mật /
Thông báo / MCP Connector). Frontend gửi MỌI giá trị dạng string
(`String(bool)` cho toggle) → tất cả field là `str`. Mọi field optional:
PUT là partial update — chỉ field gửi lên (non-None) mới được persist.
"""
from __future__ import annotations

from pydantic import BaseModel


class UpdateSystemSettingsRequest(BaseModel):
    """Body PUT /api/system-settings — 9 key khớp Settings.tsx."""

    SYSTEM_NAME: str | None = None
    SYSTEM_URL: str | None = None
    ADMIN_EMAIL: str | None = None
    SYSTEM_LANGUAGE: str | None = None
    SECURITY_2FA_ENABLED: str | None = None
    SECURITY_SESSION_TIMEOUT: str | None = None
    NOTIFY_EMAIL_ENABLED: str | None = None
    NOTIFY_TELEGRAM_ENABLED: str | None = None
    # MCP Connector — domain public HTTPS của MCP Service (tab MCP Connector).
    MCP_PUBLIC_URL: str | None = None
