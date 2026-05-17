"""API key service — Plan 05-05 (AUX-02 API key management + AES-GCM crypto).

Pattern service-chứa-SQL (Phase 4 `DocumentService`):
- Raw SQL qua `sqlalchemy.text()` + named bind params (asyncpg parametrize —
  T-05-05-05 SQL injection mitigation).
- Timestamps SQL `NOW()` server-side — KHÔNG `datetime.utcnow()`.
- JSONB column (`permissions`, `allowed_hub_ids`) cast `CAST(:x AS JSONB)`.

AES-GCM crypto (AUX-02):
- `create()` mã hóa plaintext key bằng `encrypt_secret` trước khi INSERT `key_hash`
  → at-rest encrypted (T-05-05-01).
- `verify_key()` decrypt `key_hash` so sánh exact với plaintext input — X-API-Key
  auth flow (consumer: Plan 05-05 `get_api_key_or_jwt` + Plan 05-06 `auth/api_key.py`).

DATA CONTRACT (BLOCKER 1): tên method verify = `verify_key` (KHÔNG `verify_plaintext`)
— canonical name thống nhất cho mọi consumer.

Soft revoke (D-07): `revoke()` set `is_active=FALSE` — KHÔNG DELETE row.
"""
from __future__ import annotations

import json
import logging
import secrets
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.pkg.crypto import decrypt_secret, encrypt_secret
from app.schemas.api_keys import (
    ApiKeyResponse,
    ApiKeyWithPlaintext,
    CreateApiKeyRequest,
    UpdateApiKeyRequest,
)

logger = logging.getLogger(__name__)

# Cột SELECT chuẩn cho ApiKeyResponse — dùng lại ở get/list/update.
_KEY_SELECT_COLS = (
    "id, name, key_prefix, permissions, allowed_hub_ids, rate_limit, "
    "expires_at, is_active, last_used_at, created_by, created_at"
)


def _json_list(value: object) -> list[str]:
    """Chuẩn hoá JSONB column → list[str]. asyncpg trả list/dict trực tiếp;
    nếu là str (driver khác) → json.loads."""
    if value is None:
        return []
    if isinstance(value, str):
        parsed = json.loads(value)
        return [str(x) for x in parsed] if isinstance(parsed, list) else []
    if isinstance(value, list):
        return [str(x) for x in value]
    return []


def _opt_json_list(value: object) -> list[str] | None:
    """JSONB column nullable → list[str] hoặc None (giữ None nếu cột NULL)."""
    if value is None:
        return None
    return _json_list(value)


def _map_row(row: object) -> ApiKeyResponse:
    """Map 1 row tuple (theo _KEY_SELECT_COLS) → ApiKeyResponse.

    `status` derive từ is_active (TRUE → active, FALSE → revoked). Field usage
    (requests_today/7d/bandwidth_used) + allowed_rag_configs trả default hằng số.
    """
    r = row  # Row tuple — index theo thứ tự _KEY_SELECT_COLS
    return ApiKeyResponse(
        id=str(r[0]),  # type: ignore[index]
        name=r[1],  # type: ignore[index]
        key_prefix=r[2],  # type: ignore[index]
        permissions=_json_list(r[3]),  # type: ignore[index]
        allowed_hub_ids=_opt_json_list(r[4]),  # type: ignore[index]
        rate_limit=int(r[5]),  # type: ignore[index]
        expires_at=r[6],  # type: ignore[index]
        status="active" if r[7] else "revoked",  # type: ignore[index]
        last_used_at=r[8],  # type: ignore[index]
        created_by=str(r[9]) if r[9] is not None else None,  # type: ignore[index]
        created_at=r[10],  # type: ignore[index]
    )


class ApiKeyService:
    """API key CRUD + AES-GCM crypto + soft revoke + X-API-Key verify (AUX-02)."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(
        self,
        *,
        req: CreateApiKeyRequest,
        created_by: UUID,
    ) -> ApiKeyWithPlaintext:
        """INSERT API key mới → ApiKeyWithPlaintext (plaintext trả 1 lần duy nhất).

        Plaintext `mdk_<random>`; `key_hash` = AES-GCM encrypt (at-rest);
        `key_prefix` = 8 ký tự đầu (UX hiển thị, lưu plaintext).
        """
        plain_key = f"mdk_{secrets.token_urlsafe(32)}"
        key_prefix = plain_key[:8]
        key_hash = encrypt_secret(plain_key)
        key_id = uuid4()

        await self.db.execute(
            text(
                "INSERT INTO api_keys "
                "(id, name, key_hash, key_prefix, permissions, allowed_hub_ids, "
                "rate_limit, created_by, is_active, created_at, updated_at) "
                "VALUES (:id, :name, :hash, :prefix, CAST(:perms AS JSONB), "
                "CAST(:hubs AS JSONB), :rate, :by, TRUE, NOW(), NOW())"
            ),
            {
                "id": str(key_id),
                "name": req.name,
                "hash": key_hash,
                "prefix": key_prefix,
                "perms": json.dumps(req.permissions),
                "hubs": (
                    json.dumps(req.allowed_hub_ids)
                    if req.allowed_hub_ids is not None
                    else None
                ),
                "rate": req.rate_limit,
                "by": str(created_by),
            },
        )
        logger.info(
            "api_key_created: id=%s name=%s by=%s", key_id, req.name, created_by
        )
        # Build response từ giá trị vừa INSERT — plaintext CHỈ trả lần này.
        return ApiKeyWithPlaintext(
            id=str(key_id),
            name=req.name,
            key_prefix=key_prefix,
            permissions=req.permissions,
            allowed_hub_ids=req.allowed_hub_ids,
            rate_limit=req.rate_limit,
            expires_at=None,
            status="active",
            last_used_at=None,
            created_by=str(created_by),
            created_at=datetime.now(UTC),
            plain_key=plain_key,
        )

    async def get(self, key_id: UUID) -> ApiKeyResponse | None:
        """SELECT 1 API key qua id. None nếu không tồn tại.

        KHÔNG trả plaintext — chỉ key_prefix (T-05-05-01).
        """
        row = (
            await self.db.execute(
                text(
                    f"SELECT {_KEY_SELECT_COLS} FROM api_keys WHERE id = :id"
                ),
                {"id": str(key_id)},
            )
        ).fetchone()
        if row is None:
            return None
        return _map_row(row)

    async def list(
        self,
        *,
        page: int,
        per_page: int,
    ) -> tuple[list[ApiKeyResponse], int]:
        """List API key phân trang. Returns (items, total).

        Router cap per_page ≤ 100 — service KHÔNG cap.
        """
        total_row = (
            await self.db.execute(text("SELECT COUNT(*) FROM api_keys"))
        ).fetchone()
        total = int(total_row[0]) if total_row else 0

        offset = max(0, (page - 1) * per_page)
        rows = (
            await self.db.execute(
                text(
                    f"SELECT {_KEY_SELECT_COLS} FROM api_keys "
                    "ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
                ),
                {"limit": per_page, "offset": offset},
            )
        ).fetchall()
        return [_map_row(r) for r in rows], total

    async def update(
        self,
        *,
        key_id: UUID,
        req: UpdateApiKeyRequest,
    ) -> ApiKeyResponse | None:
        """UPDATE metadata API key (PUT — D-07). None nếu key không tồn tại.

        Build SET clause động chỉ cho field không None.
        """
        set_parts: list[str] = []
        params: dict[str, Any] = {"id": str(key_id)}
        if req.name is not None:
            set_parts.append("name = :name")
            params["name"] = req.name
        if req.permissions is not None:
            set_parts.append("permissions = CAST(:perms AS JSONB)")
            params["perms"] = json.dumps(req.permissions)
        if req.allowed_hub_ids is not None:
            set_parts.append("allowed_hub_ids = CAST(:hubs AS JSONB)")
            params["hubs"] = json.dumps(req.allowed_hub_ids)
        if req.rate_limit is not None:
            set_parts.append("rate_limit = :rate")
            params["rate"] = req.rate_limit
        set_parts.append("updated_at = NOW()")
        set_sql = ", ".join(set_parts)

        row = (
            await self.db.execute(
                text(
                    f"UPDATE api_keys SET {set_sql} WHERE id = :id "
                    f"RETURNING {_KEY_SELECT_COLS}"
                ),
                params,
            )
        ).fetchone()
        if row is None:
            return None
        logger.info("api_key_updated: id=%s", key_id)
        return _map_row(row)

    async def revoke(self, *, key_id: UUID) -> bool:
        """Soft revoke API key — set `is_active=FALSE` (D-07, KHÔNG DELETE row).

        Returns True nếu update 1 row, False nếu key không tồn tại. Dùng
        `RETURNING id` thay `.rowcount` (SQLAlchemy `Result` stub không expose
        rowcount).
        """
        row = (
            await self.db.execute(
                text(
                    "UPDATE api_keys SET is_active = FALSE, updated_at = NOW() "
                    "WHERE id = :id RETURNING id"
                ),
                {"id": str(key_id)},
            )
        ).fetchone()
        if row is None:
            return False
        logger.info("api_key_revoked: id=%s", key_id)
        return True

    async def verify_key(self, plain_key: str) -> dict[str, Any] | None:
        """Verify X-API-Key plaintext → principal dict, hoặc None nếu invalid.

        BLOCKER 1 — tên method canonical = `verify_key`. Consumer: Plan 05-05
        `get_api_key_or_jwt` + Plan 05-06 `auth/api_key.py`.

        Flow: SELECT mọi api_keys WHERE `key_prefix = :prefix AND is_active=TRUE`
        (revoked key is_active=FALSE bị loại — T-05-05-03); với mỗi row decrypt
        `key_hash` so sánh exact với `plain_key`. Match → UPDATE `last_used_at`
        + return principal dict.
        """
        prefix = plain_key[:8]
        rows = (
            await self.db.execute(
                text(
                    "SELECT id, key_hash, permissions, allowed_hub_ids "
                    "FROM api_keys WHERE key_prefix = :prefix "
                    "AND is_active = TRUE"
                ),
                {"prefix": prefix},
            )
        ).fetchall()
        for row in rows:
            try:
                if decrypt_secret(row[1]) != plain_key:
                    continue
            except Exception:  # noqa: BLE001 — decrypt fail → key không match
                continue
            # Match — cập nhật last_used_at (T-05-05-08 Repudiation mitigation).
            await self.db.execute(
                text(
                    "UPDATE api_keys SET last_used_at = NOW() WHERE id = :id"
                ),
                {"id": str(row[0])},
            )
            return {
                "id": str(row[0]),
                "permissions": _json_list(row[2]),
                "allowed_hub_ids": _opt_json_list(row[3]),
            }
        return None
