"""API keys router — Plan 05-05 (AUX-02 API key management).

5 endpoint — mọi endpoint admin-only (`require_role("admin")`; T-05-05-02
Elevation of Privilege mitigation — API key CRUD là admin-only theo AUX-02):

    GET    /api/api-keys              — list phân trang (per_page cap ≤ 100)
    POST   /api/api-keys              — create → 201 (trả plaintext 1 lần)
    GET    /api/api-keys/:id          — get single (KHÔNG plaintext)
    PUT    /api/api-keys/:id          — update metadata (D-07)
    POST   /api/api-keys/:id/revoke   — soft revoke (is_active=FALSE — D-07)

D-07: revoke = POST soft revoke (KHÔNG DELETE cứng). Plaintext key chỉ xuất hiện
1 lần trong response của POST create (`ApiKeyWithPlaintext.plain_key`).

Contract verb/path lấy từ `frontend/src/services/api.ts` (D-07).
"""
from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_internal_auth, require_role
from app.db.session import get_session
from app.models.auth import User
from app.pkg import response as resp
from app.schemas.api_keys import (
    CreateApiKeyRequest,
    UpdateApiKeyRequest,
    VerifyApiKeyRequest,
)
from app.services.api_key_service import ApiKeyService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/api-keys", tags=["api-keys"])


def get_api_key_service(
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> ApiKeyService:
    return ApiKeyService(db=db)


@router.get("")
async def list_api_keys(
    page: int = 1,
    per_page: int = 20,
    user: User = Depends(require_role("admin")),  # noqa: B008
    service: ApiKeyService = Depends(get_api_key_service),  # noqa: B008
) -> JSONResponse:
    """GET /api/api-keys — list phân trang, admin-only.

    Cap per_page ≤ 100 + page ≥ 1.
    """
    _ = user  # admin-only gate qua require_role.
    capped_per_page = max(1, min(per_page, 100))
    capped_page = max(1, page)
    items, total = await service.list(
        page=capped_page, per_page=capped_per_page
    )
    return resp.paginated(
        items=[i.model_dump(mode="json") for i in items],
        page=capped_page,
        per_page=capped_per_page,
        total=total,
    )


@router.post("")
async def create_api_key(
    req: CreateApiKeyRequest,
    user: User = Depends(require_role("admin")),  # noqa: B008
    service: ApiKeyService = Depends(get_api_key_service),  # noqa: B008
) -> JSONResponse:
    """POST /api/api-keys — create API key, admin-only → 201.

    Response data chứa `plain_key` (plaintext) — frontend hiển thị 1 lần duy
    nhất; GET về sau chỉ trả `key_prefix` (T-05-05-01).
    """
    result = await service.create(req=req, created_by=user.id)
    return resp.created(data=result.model_dump(mode="json"))


@router.get("/{key_id}")
async def get_api_key(
    key_id: str,
    user: User = Depends(require_role("admin")),  # noqa: B008
    service: ApiKeyService = Depends(get_api_key_service),  # noqa: B008
) -> JSONResponse:
    """GET /api/api-keys/:id — get single API key, admin-only (KHÔNG plaintext)."""
    _ = user
    try:
        key_uuid = UUID(key_id)
    except ValueError:
        return resp.bad_request(
            message=f"key_id không hợp lệ: {key_id!r}",
            code="INVALID_API_KEY_ID",
        )
    api_key = await service.get(key_uuid)
    if api_key is None:
        return resp.not_found(
            message=f"API key {key_id} không tồn tại", code="NOT_FOUND"
        )
    return resp.ok(data=api_key.model_dump(mode="json"))


@router.put("/{key_id}")
async def update_api_key(
    key_id: str,
    req: UpdateApiKeyRequest,
    user: User = Depends(require_role("admin")),  # noqa: B008
    service: ApiKeyService = Depends(get_api_key_service),  # noqa: B008
) -> JSONResponse:
    """PUT /api/api-keys/:id — update metadata API key, admin-only."""
    _ = user
    try:
        key_uuid = UUID(key_id)
    except ValueError:
        return resp.bad_request(
            message=f"key_id không hợp lệ: {key_id!r}",
            code="INVALID_API_KEY_ID",
        )
    result = await service.update(key_id=key_uuid, req=req)
    if result is None:
        return resp.not_found(
            message=f"API key {key_id} không tồn tại", code="NOT_FOUND"
        )
    return resp.ok(data=result.model_dump(mode="json"))


@router.post("/{key_id}/revoke")
async def revoke_api_key(
    key_id: str,
    user: User = Depends(require_role("admin")),  # noqa: B008
    service: ApiKeyService = Depends(get_api_key_service),  # noqa: B008
) -> JSONResponse:
    """POST /api/api-keys/:id/revoke — soft revoke (is_active=FALSE — D-07).

    KHÔNG DELETE row — key vẫn tồn tại trong DB, chỉ vô hiệu hoá.
    """
    _ = user
    try:
        key_uuid = UUID(key_id)
    except ValueError:
        return resp.bad_request(
            message=f"key_id không hợp lệ: {key_id!r}",
            code="INVALID_API_KEY_ID",
        )
    ok = await service.revoke(key_id=key_uuid)
    if not ok:
        return resp.not_found(
            message=f"API key {key_id} không tồn tại", code="NOT_FOUND"
        )
    return resp.ok(data={"message": "API key đã thu hồi"})


@router.post("/verify", response_model=None)
async def verify_api_key(
    req: VerifyApiKeyRequest,
    _internal: None = Depends(require_internal_auth),  # noqa: B008
    service: ApiKeyService = Depends(get_api_key_service),  # noqa: B008
) -> dict[str, Any]:
    """POST /api/api-keys/verify — Internal proxy cho hub con verify X-API-Key.

    Phase 6 Plan 06-03 SETTINGS-03 (D-V3-Phase6-D). Endpoint MỚI central-only
    mount (FACTOR-02 carry forward — api_keys_router central-only ở main.py).

    Body: `{"api_key": "mdk_..."}` (Pydantic VerifyApiKeyRequest min_length=1).
    Header: `X-Internal-Auth: <settings_proxy_secret>` (require_internal_auth dep).
    Response: `{valid: bool, principal: dict | null}` raw dict (KHÔNG envelope
    — hub con ApiKeyVerifyClient parse raw, pattern song song /api/rag-config
    M2 raw dict).

    Central giữ AES-GCM at-rest M2 AUX-02 (KHÔNG đụng verify_key private logic).

    Threat model:
    - T-06-03-03 Information Disclosure plaintext api_key body — accept M2 baseline
      + intra-network medinet_net Docker isolation (mTLS defer v4.0).
    - T-06-03-05 Spoofing endpoint expose public internet — FACTOR-02 central-only
      mount + require_internal_auth dep enforce.
    - T-06-03-07 Repudiation verify audit log — accept Phase 6 (high-frequency log
      volume defer Phase 7); Prometheus APIKEY_VERIFY_TOTAL counter Plan 06-01 đủ debug.
    """
    principal = await service.verify_key(req.api_key)
    if principal is None:
        return {"valid": False, "principal": None}
    return {"valid": True, "principal": principal}
