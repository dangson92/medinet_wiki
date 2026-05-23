"""X-API-Key auth dependency — AUX-02 external integration + Phase 6 hub branch.

Cho phép request mang header `X-API-Key: mdk_...` truy cập API thay vì Bearer JWT.

Phase 6 Plan 06-03 SETTINGS-03 (D-V3-Phase6-A) — Branch verify path theo
`settings.hub_name`:
- Central (hub_name="central"): M2 carry forward local `ApiKeyService.verify_key`
  (AES-GCM decrypt + key_prefix match — M2 AUX-02 unchanged).
- Hub con (yte/duoc/hcns/dynamic): HTTP proxy qua `ApiKeyVerifyClient` ở
  `app.state.api_key_verify_client` (Plan 06-02 client + Plan 06-04 lifespan).

BLOCKER 1 — `require_api_key` gọi `ApiKeyService.verify_key` (tên canonical, Plan
05-05 producer). KHÔNG dùng `verify_plaintext` (tên cũ sai — AttributeError runtime).
"""
from __future__ import annotations

from typing import Any

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.session import get_session
from app.services.api_key_service import ApiKeyService


async def require_api_key(
    request: Request,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),  # noqa: B008
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> dict[str, Any]:
    """Verify X-API-Key header → principal dict {id, permissions, allowed_hub_ids}.

    Phase 6 Plan 06-03 SETTINGS-03 (D-V3-Phase6-A) — branch verify path theo
    `settings.hub_name`:

    Central (hub_name="central"): M2 local verify carry forward (AES-GCM decrypt
        + key_prefix match — M2 AUX-02 KHÔNG đụng).
    Hub con (yte/duoc/hcns/dynamic): proxy qua `ApiKeyVerifyClient` ở
        `app.state.api_key_verify_client` (HTTP POST central + cache Redis 60s).

    Raise 401 API_KEY_MISSING nếu thiếu header (M2 regression — pre-branch).
    Raise 401 API_KEY_INVALID nếu key sai/revoked (cả 2 path).
    Raise 503 APIKEY_VERIFY_CLIENT_UNAVAILABLE nếu hub con + client chưa init
        (Plan 06-04 lifespan fail-loud → uvicorn exit 1; runtime KHÔNG silent
        fallback local DB — fail-loud rõ ràng).
    """
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "API_KEY_MISSING", "message": "Thiếu header X-API-Key"},
        )

    settings = get_settings()
    if settings.hub_name == "central":
        # Central: M2 local verify carry forward (AES-GCM decrypt + match).
        principal = await ApiKeyService(db=db).verify_key(x_api_key)
    else:
        # Hub con: proxy qua ApiKeyVerifyClient (D-V3-Phase6-A LOCKED).
        client = getattr(request.app.state, "api_key_verify_client", None)
        if client is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "code": "APIKEY_VERIFY_CLIENT_UNAVAILABLE",
                    "message": (
                        "ApiKeyVerifyClient chưa init — hub con boot fail? "
                        "Plan 06-04 lifespan SETTINGS_SKIP_FETCH=1 test mode."
                    ),
                },
            )
        principal = await client.verify(x_api_key)

    if principal is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "API_KEY_INVALID",
                "message": "API key không hợp lệ hoặc đã thu hồi",
            },
        )
    return principal
