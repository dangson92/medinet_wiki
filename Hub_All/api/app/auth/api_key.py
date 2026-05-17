"""X-API-Key auth dependency — AUX-02 external integration.

Cho phép request mang header `X-API-Key: mdk_...` truy cập API thay vì Bearer JWT.
Key verify qua ApiKeyService.verify_key (decrypt AES-GCM + match key_prefix).
Endpoint external (Phase 6/7 search/ask) opt-in Depends(require_api_key).

BLOCKER 1 — `require_api_key` gọi `ApiKeyService.verify_key` (tên canonical, Plan
05-05 producer). KHÔNG dùng `verify_plaintext` (tên cũ sai — AttributeError runtime).
"""
from __future__ import annotations

from typing import Any

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.services.api_key_service import ApiKeyService


async def require_api_key(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),  # noqa: B008
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> dict[str, Any]:
    """Verify X-API-Key header → principal dict {id, permissions, allowed_hub_ids}.

    Raise 401 API_KEY_MISSING nếu thiếu header; API_KEY_INVALID nếu key sai/revoked.
    """
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "API_KEY_MISSING", "message": "Thiếu header X-API-Key"},
        )
    principal = await ApiKeyService(db=db).verify_key(x_api_key)
    if principal is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "API_KEY_INVALID",
                "message": "API key không hợp lệ hoặc đã thu hồi",
            },
        )
    return principal
