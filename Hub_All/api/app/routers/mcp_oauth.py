"""MCP OAuth client routers — per-user pre-registered + internal lookup.

Phase 8.3 add-on: 2 router gộp 1 file (cùng domain MCP OAuth).

User-facing (authenticated, self-scoped — `user.id` lấy từ JWT):
    GET  /api/mcp/my-oauth-client         — lazy-create cặp của user logged-in
    POST /api/mcp/my-oauth-client/rotate  — xoay client_secret (giữ client_id)

Internal (shared secret env `MCP_INTERNAL_TOKEN`):
    GET  /api/internal/mcp/clients/{client_id} — tra cứu cặp + owner_user_id

T-08.3-X (Elevation of Privilege ngang Profile router): user-facing endpoint
KHÔNG nhận `:id` từ path/body — `user_id` LUÔN lấy từ JWT. User A KHÔNG thể
tạo/rotate cặp của user B.

Internal endpoint fail-closed: env rỗng → 503. Sai/thiếu Bearer → 401.
`secrets.compare_digest` chống timing attack trên so sánh token.
"""
from __future__ import annotations

import logging
import secrets

from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.config import get_settings
from app.db.session import get_session
from app.models.auth import User
from app.models.mcp_oauth import MCPOAuthClient
from app.pkg import response as resp
from app.schemas.mcp_oauth import MCPOAuthClientInternal, MCPOAuthClientResponse
from app.services.mcp_oauth_service import MCPOAuthClientService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/mcp", tags=["mcp"])
internal_router = APIRouter(prefix="/api/internal/mcp", tags=["mcp-internal"])


def _to_user_response(client: MCPOAuthClient) -> dict:
    """Serialize MCPOAuthClient → dict cho user-facing envelope."""
    return MCPOAuthClientResponse(
        client_id=client.client_id,
        client_secret=client.client_secret,
        redirect_uris=list(client.redirect_uris or []),
        created_at=client.created_at,
        rotated_at=client.rotated_at,
    ).model_dump(mode="json")


# ─── User-facing ──────────────────────────────────────────────────────────


@router.get("/my-oauth-client")
async def get_my_oauth_client(
    user: User = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> JSONResponse:
    """GET /api/mcp/my-oauth-client — trả cặp của user, lazy-create nếu chưa có."""
    service = MCPOAuthClientService(db=db)
    client = await service.get_or_create(user.id)
    return resp.ok(data=_to_user_response(client))


@router.post("/my-oauth-client/rotate")
async def rotate_my_oauth_client(
    user: User = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> JSONResponse:
    """POST /api/mcp/my-oauth-client/rotate — xoay client_secret (giữ client_id).

    Nếu user chưa có cặp → lazy-create luôn (rotate tương đương create lần đầu),
    tránh 404 gây UX bối rối.
    """
    service = MCPOAuthClientService(db=db)
    client = await service.rotate(user.id)
    if client is None:
        client = await service.get_or_create(user.id)
    return resp.ok(data=_to_user_response(client))


# ─── Internal (MCP service ↔ API) ─────────────────────────────────────────


def require_internal_token(
    authorization: str | None = Header(default=None),
) -> None:
    """Dependency: header `Authorization: Bearer <MCP_INTERNAL_TOKEN>` phải match.

    Fail-closed: env rỗng → 503 (configuration missing). Thiếu/sai header → 401.
    """
    expected = get_settings().mcp_internal_token
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "INTERNAL_AUTH_NOT_CONFIGURED",
                "message": "MCP_INTERNAL_TOKEN chưa được cấu hình ở API",
            },
        )
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "MISSING_AUTHORIZATION",
                "message": "Thiếu Bearer token cho endpoint internal",
            },
        )
    token = authorization[len("Bearer "):]
    if not secrets.compare_digest(token, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "INVALID_INTERNAL_TOKEN",
                "message": "Token internal không khớp",
            },
        )


@internal_router.get("/clients/{client_id}")
async def lookup_client(
    client_id: str,
    _auth: None = Depends(require_internal_token),  # noqa: B008
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> JSONResponse:
    """Lookup pre-registered client + owner. MCP service gọi cho bind enforcement.

    Trả full client_secret để MCP wrap thành `OAuthClientInformationFull` cho
    SDK; `owner_user_id` cho login_callback compare so với user vừa login.
    """
    service = MCPOAuthClientService(db=db)
    client = await service.get_by_client_id(client_id)
    if client is None:
        return resp.not_found(message="Client không tồn tại", code="NOT_FOUND")

    # Load email — best-effort, log/audit ở MCP nếu cần. Không fail nếu mất.
    owner = (
        await db.execute(select(User).where(User.id == client.user_id))
    ).scalar_one_or_none()

    payload = MCPOAuthClientInternal(
        client_id=client.client_id,
        client_secret=client.client_secret,
        redirect_uris=list(client.redirect_uris or []),
        owner_user_id=str(client.user_id),
        owner_email=owner.email if owner is not None else "",
    ).model_dump(mode="json")
    return resp.ok(data=payload)
