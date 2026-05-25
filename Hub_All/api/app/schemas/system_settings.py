"""System settings schema — body PUT /api/system-settings.

Khớp `saveSystemSettings()` frontend Settings.tsx (tab Chung / Bảo mật /
Thông báo / MCP Connector). Frontend gửi MỌI giá trị dạng string
(`String(bool)` cho toggle) → tất cả field là `str`. Mọi field optional:
PUT là partial update — chỉ field gửi lên (non-None) mới được persist.
"""
from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class TestSmtpRequest(BaseModel):
    """Body POST /api/system-settings/test-smtp — gửi email test.

    `overrides` (optional): admin gửi giá trị form FE chưa save để test trước
    khi commit. Empty / mask `********` cho SMTP_PASSWORD → backend fallback
    DB (preserve-on-empty). Bỏ trống → backend dùng config DB hiện tại.
    """

    to_email: EmailStr = Field(..., description="Địa chỉ email nhận test")
    overrides: dict[str, str] | None = Field(
        default=None,
        description="Override SMTP_* + SYSTEM_* keys từ form FE chưa save",
    )


class UpdateSystemSettingsRequest(BaseModel):
    """Body PUT /api/system-settings — khớp Settings.tsx."""

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
    # SMTP — cấu hình gửi email (tab Thông báo § SMTP).
    # SMTP_PASSWORD: gửi chuỗi rỗng "" → giữ password cũ trong DB (preserve-on-empty);
    # gửi chuỗi non-empty → ghi đè plain text (LƯU Ý: chưa encrypt at-rest, defer v4.0).
    SMTP_HOST: str | None = None
    SMTP_PORT: str | None = None
    SMTP_USERNAME: str | None = None
    SMTP_PASSWORD: str | None = None
    SMTP_FROM_EMAIL: str | None = None
    SMTP_FROM_NAME: str | None = None
    SMTP_USE_TLS: str | None = None
