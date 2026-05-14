"""Auth router — Plan 03-04 (AUTH-01..03).

4 endpoint:
    POST /api/auth/login    — body {email, password} → 200 LoginResponse / 401
    POST /api/auth/refresh  — body {refresh_token} → 200 LoginResponse / 401
    POST /api/auth/logout   — Bearer + optional body {refresh_token} → 200
    GET  /api/auth/me       — Bearer → 200 UserPublic / 401 INVALID_TOKEN

Mọi response qua `app.pkg.response.ok/error_*` envelope (Plan 03-01) — KHÔNG
return Pydantic model raw để D6 frontend compat.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.auth.dependencies import (
    get_auth_service,
    get_current_user,
    get_jwt_manager,
)
from app.auth.jwt import JWTManager
from app.auth.schemas import (
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
)
from app.auth.service import AuthError, AuthService
from app.models.auth import User
from app.pkg import response as resp

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _auth_error_to_response(e: AuthError) -> JSONResponse:
    """Map AuthError.code → 401 envelope với code Go-compat."""
    return resp.unauthorized(message=e.message, code=e.code)


@router.post("/login")
async def login(
    req: LoginRequest,
    service: AuthService = Depends(get_auth_service),  # noqa: B008
) -> JSONResponse:
    try:
        result = await service.login(req)
    except AuthError as e:
        return _auth_error_to_response(e)
    return resp.ok(data=result.model_dump())


@router.post("/refresh")
async def refresh(
    req: RefreshRequest,
    service: AuthService = Depends(get_auth_service),  # noqa: B008
) -> JSONResponse:
    try:
        result = await service.refresh(req)
    except AuthError as e:
        return _auth_error_to_response(e)
    return resp.ok(data=result.model_dump())


@router.post("/logout")
async def logout(
    request: Request,
    body: LogoutRequest | None = None,
    user: User = Depends(get_current_user),  # noqa: B008
    service: AuthService = Depends(get_auth_service),  # noqa: B008
    jwt_mgr: JWTManager = Depends(get_jwt_manager),  # noqa: B008
) -> JSONResponse:
    # Lấy access token + jti từ header (verify lại để có jti + exp).
    auth_header = request.headers.get("authorization", "")
    parts = auth_header.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return resp.unauthorized(
            message="Sai format Authorization header",
            code="INVALID_AUTHORIZATION_FORMAT",
        )
    token = parts[1]
    try:
        claims = jwt_mgr.verify_token(token, expected_type="access")
    except Exception:  # noqa: BLE001
        return resp.unauthorized(
            message="Token không hợp lệ", code="INVALID_TOKEN"
        )

    refresh_token = body.refresh_token if body else None
    try:
        await service.logout(
            access_jti=claims.jti,
            access_exp=claims.exp,
            refresh_token=refresh_token,
        )
    except AuthError as e:
        return _auth_error_to_response(e)
    return resp.ok(data={"message": "Đăng xuất thành công"})


@router.get("/me")
async def me(
    user: User = Depends(get_current_user),  # noqa: B008
    service: AuthService = Depends(get_auth_service),  # noqa: B008
) -> JSONResponse:
    try:
        public = await service.get_current_user_info(str(user.id))
    except AuthError as e:
        return _auth_error_to_response(e)
    return resp.ok(data=public.model_dump())
