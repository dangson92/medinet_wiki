"""System settings schema — body PUT /api/system-settings.

Khớp `saveSystemSettings()` frontend Settings.tsx (tab Chung / Bảo mật /
Thông báo / MCP Connector). Frontend gửi MỌI giá trị dạng string
(`String(bool)` cho toggle) → tất cả field là `str`. Mọi field optional:
PUT là partial update — chỉ field gửi lên (non-None) mới được persist.
"""
from __future__ import annotations

from pydantic import BaseModel


class UpdateSystemSettingsRequest(BaseModel):
    """Body PUT /api/system-settings — 11 key khớp Settings.tsx."""

    SYSTEM_NAME: str | None = None
    SYSTEM_URL: str | None = None
    ADMIN_EMAIL: str | None = None
    SYSTEM_LANGUAGE: str | None = None
    SECURITY_2FA_ENABLED: str | None = None
    SECURITY_SESSION_TIMEOUT: str | None = None
    NOTIFY_EMAIL_ENABLED: str | None = None
    NOTIFY_TELEGRAM_ENABLED: str | None = None
    # MCP Connector (tab MCP Connector trong Settings.tsx).
    # MCP_PUBLIC_URL    — domain public HTTPS của MCP Service.
    # MCP_OAUTH_CLIENT_ID / MCP_OAUTH_CLIENT_SECRET — pre-registered OAuth
    #   client (sinh qua `python -m mcp_app.oauth.create_client` trong
    #   container mcp_service), admin dán vào Settings để tiện copy lại
    #   khi thêm connector trong Claude web.
    MCP_PUBLIC_URL: str | None = None
    MCP_OAUTH_CLIENT_ID: str | None = None
    MCP_OAUTH_CLIENT_SECRET: str | None = None
