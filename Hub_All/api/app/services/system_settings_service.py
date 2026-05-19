"""System settings service — endpoint /api/system-settings (D6).

Bối cảnh: frontend React 19 (D6 — KHÔNG sửa trong M2) tab "Cài đặt chung /
Bảo mật / Thông báo" gọi GET/PUT `/api/system-settings`. Endpoint Go-era này
chưa được port → frontend nhận 404, load về giá trị mặc định, lưu thất bại.

Persist key-value vào bảng `settings` (JSONB scalar) — DÙNG CHUNG bảng với
`rag_config_service`, nên service này CHỈ thao tác whitelist 9 key của tab
hệ thống, KHÔNG đụng các key `RAG_*` / `LLM_*` / `*_API_KEY`.

Khác `rag_config`: settings hệ thống thuần khai báo (tên, URL, toggle) → KHÔNG
hot-swap runtime, KHÔNG mã hoá — chỉ ghi DB rồi đọc lại.
"""
from __future__ import annotations

import json
import logging
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Whitelist key cho phép — chặn admin ghi đè key RAG_*/LLM_* qua endpoint này.
# Default khớp state khởi tạo trong Settings.tsx (giá trị hiển thị khi DB rỗng).
_DEFAULTS: dict[str, str] = {
    "SYSTEM_NAME": "Medinet Wiki",
    "SYSTEM_URL": "https://wiki.medinet.vn",
    "ADMIN_EMAIL": "admin@medinet.vn",
    "SYSTEM_LANGUAGE": "vi",
    "SECURITY_2FA_ENABLED": "false",
    "SECURITY_SESSION_TIMEOUT": "30",
    "NOTIFY_EMAIL_ENABLED": "true",
    "NOTIFY_TELEGRAM_ENABLED": "false",
    # Rỗng = chưa cấu hình → frontend tự suy domain từ host thật của app.
    "MCP_PUBLIC_URL": "",
}
_ALLOWED_KEYS = frozenset(_DEFAULTS)


def _parse_jsonb(raw: Any) -> Any:
    """Raw JSONB column (text() query trả JSON string) → Python value."""
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except (ValueError, TypeError):
            return raw
    return raw


class SystemSettingsService:
    """CRUD settings hệ thống qua bảng `settings` (whitelist 9 key)."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_settings(self) -> dict[str, str]:
        """GET /api/system-settings — 9 key hiện tại, fallback default nếu DB rỗng."""
        rows = (
            await self.db.execute(text("SELECT key, value FROM settings"))
        ).fetchall()
        stored = {row[0]: _parse_jsonb(row[1]) for row in rows}
        return {
            key: str(stored.get(key, default))
            for key, default in _DEFAULTS.items()
        }

    async def update_settings(
        self, *, payload: dict[str, Any], updated_by: UUID
    ) -> dict[str, str]:
        """PUT /api/system-settings — UPSERT từng key (partial update).

        `payload` đã được Pydantic lọc về 8 field whitelist + bỏ None
        (router gọi `model_dump(exclude_none=True)`).
        """
        for key, value in payload.items():
            if key not in _ALLOWED_KEYS:  # phòng thủ — Pydantic đã chặn key lạ.
                continue
            await self.db.execute(
                text(
                    "INSERT INTO settings (key, value, updated_by, updated_at) "
                    "VALUES (:key, CAST(:value AS JSONB), :by, NOW()) "
                    "ON CONFLICT (key) DO UPDATE SET "
                    "value = EXCLUDED.value, updated_by = EXCLUDED.updated_by, "
                    "updated_at = NOW()"
                ),
                {
                    "key": key,
                    "value": json.dumps(str(value)),
                    "by": str(updated_by),
                },
            )
        logger.info(
            "system_settings_updated by=%s keys=%s",
            updated_by,
            sorted(payload),
        )
        return await self.get_settings()
