"""System settings service — endpoint /api/system-settings (D6).

Bối cảnh: frontend React 19 (D6 — KHÔNG sửa trong M2) tab "Cài đặt chung /
Bảo mật / Thông báo" gọi GET/PUT `/api/system-settings`. Endpoint Go-era này
chưa được port → frontend nhận 404, load về giá trị mặc định, lưu thất bại.

Persist key-value vào bảng `settings` (JSONB scalar) — DÙNG CHUNG bảng với
`rag_config_service`, nên service này CHỈ thao tác whitelist key của tab
hệ thống, KHÔNG đụng các key `RAG_*` / `LLM_*` / `*_API_KEY`.

Khác `rag_config`: settings hệ thống thuần khai báo (tên, URL, toggle) → KHÔNG
hot-swap runtime, KHÔNG mã hoá — chỉ ghi DB rồi đọc lại.

SMTP_PASSWORD: lưu plain text trong settings JSONB hiện tại (chưa AES-GCM
at-rest như `RagConfigService` cho API key). GET trả mask `********` (8 char
giả) nếu đã set, "" nếu chưa cấu hình. PUT chuỗi rỗng → giữ password cũ
(preserve-on-empty), PUT chuỗi non-empty → ghi đè plain. Encrypt at-rest +
test SMTP connection endpoint defer v4.0.
"""
from __future__ import annotations

import json
import logging
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Mask hiển thị thay password thật khi GET — frontend dùng mask này để biết
# "đã cấu hình rồi" (vs "" rỗng = chưa set). Chuỗi cố định 8 dấu sao tránh
# leak length password thật.
_PASSWORD_MASK = "********"

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
    # SMTP — rỗng = chưa cấu hình (frontend hiển thị placeholder + disable test).
    "SMTP_HOST": "",
    "SMTP_PORT": "587",
    "SMTP_USERNAME": "",
    "SMTP_PASSWORD": "",
    "SMTP_FROM_EMAIL": "",
    "SMTP_FROM_NAME": "Medinet Wiki",
    "SMTP_USE_TLS": "true",
}
_ALLOWED_KEYS = frozenset(_DEFAULTS)

# Key chứa secret — GET trả mask thay plain text; PUT "" = giữ cũ.
_SENSITIVE_KEYS = frozenset({"SMTP_PASSWORD"})


def _parse_jsonb(raw: Any) -> Any:
    """Raw JSONB column (text() query trả JSON string) → Python value."""
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except (ValueError, TypeError):
            return raw
    return raw


class SystemSettingsService:
    """CRUD settings hệ thống qua bảng `settings` (whitelist key)."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def _fetch_all(self) -> dict[str, str]:
        """Đọc raw 9+7 key từ DB (chưa mask) — dùng nội bộ cho update_settings."""
        rows = (
            await self.db.execute(text("SELECT key, value FROM settings"))
        ).fetchall()
        stored = {row[0]: _parse_jsonb(row[1]) for row in rows}
        return {
            key: str(stored.get(key, default))
            for key, default in _DEFAULTS.items()
        }

    async def get_settings(self) -> dict[str, str]:
        """GET /api/system-settings — settings hiện tại, mask secret key."""
        result = await self._fetch_all()
        # Mask SMTP_PASSWORD: non-empty plain → "********", "" → "" giữ nguyên.
        for sensitive in _SENSITIVE_KEYS:
            if result.get(sensitive):
                result[sensitive] = _PASSWORD_MASK
        return result

    async def update_settings(
        self, *, payload: dict[str, Any], updated_by: UUID
    ) -> dict[str, str]:
        """PUT /api/system-settings — UPSERT từng key (partial update).

        `payload` đã được Pydantic lọc về field whitelist + bỏ None (router
        gọi `model_dump(exclude_none=True)`).

        Sensitive key (SMTP_PASSWORD):
        - Value "" (chuỗi rỗng) → SKIP, giữ value cũ trong DB. Cho phép user
          PUT toàn bộ form mà không phải re-nhập password mỗi lần.
        - Value == _PASSWORD_MASK (frontend gửi lại mask đã hiển thị) → SKIP,
          giữ cũ. Phòng FE bug echo lại mask thay vì giữ rỗng.
        - Value khác → ghi đè plain text.
        """
        for key, value in payload.items():
            if key not in _ALLOWED_KEYS:  # phòng thủ — Pydantic đã chặn key lạ.
                continue
            if key in _SENSITIVE_KEYS:
                str_value = str(value)
                # Preserve-on-empty: rỗng hoặc mask → giữ password cũ.
                if str_value == "" or str_value == _PASSWORD_MASK:
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
        # Log key tên thôi — KHÔNG log value của sensitive key.
        logger.info(
            "system_settings_updated by=%s keys=%s",
            updated_by,
            sorted(payload),
        )
        return await self.get_settings()
