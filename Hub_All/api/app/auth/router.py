"""Auth router — Plan 03-04 (AUTH-01..03 + SSO-02 hub con 307 redirect).

4 endpoint, hành vi tuỳ `settings.hub_name`:

    POST /api/auth/login
      - central: handle local AuthService.login → 200 LoginResponse / 401
      - hub con: 307 Location: {central_url}/api/auth/login (D-V3-Phase3-G)

    POST /api/auth/refresh
      - central: handle local AuthService.refresh → 200 LoginResponse / 401
      - hub con: 307 Location: {central_url}/api/auth/refresh (D-V3-Phase3-C/G)

    POST /api/auth/logout
      - cả central + hub con handle local — verify JWT + Redis blacklist chung
        Plan 03-03. KHÔNG redirect (giảm latency logout).

    GET  /api/auth/me
      - cả central + hub con handle local — verify JWT qua JWKSCache Plan 03-02
        (hub con) / local pem (central) + load user.

Mọi response qua `app.pkg.response.ok/error_*` envelope (Plan 03-01) — KHÔNG
return Pydantic model raw để D6 frontend compat.

Phase 3 Plan 03-04 SSO-02 D-V3-Phase3-G: 307 redirect preserve POST method +
body (RFC 7231 method-preserving). Browser auto-follow tới central. Frontend
wire redirect form defer Phase 5 PROXY-02 (D-V3-Phase3-F D6 expire).
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, RedirectResponse

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
from app.config import get_settings
from app.models.auth import User
from app.pkg import response as resp

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _auth_error_to_response(e: AuthError) -> JSONResponse:
    """Map AuthError.code → 401 envelope với code Go-compat."""
    return resp.unauthorized(message=e.message, code=e.code)


def _sso_redirect(target_path: str, hub_name: str) -> JSONResponse | RedirectResponse:
    """Build 307 RedirectResponse tới central cho hub con login/refresh.

    Phase 3 Plan 03-04 SSO-02 (D-V3-Phase3-G):
    - 307 Temporary Redirect preserve POST method + body (RFC 7231).
    - Browser auto-follow tới `{settings.central_url}{target_path}`.
    - Defensive 503 envelope nếu central_url None ở runtime (impossible vì
      Settings validator Task 1 enforce required, nhưng paranoid guard).

    X-SSO-Redirect-Reason + X-SSO-Original-Hub headers cho debug + observability
    (T-03-04-02 accept — hub_name đã expose qua subpath URL Phase 5).
    """
    settings = get_settings()
    if not settings.central_url:
        # Settings validator Plan 03-04 Task 1 enforce — impossible reach
        # ở runtime nhưng paranoid defensive (KHÔNG redirect URL rỗng).
        return resp.service_unavailable(
            message=(
                "Hub con KHÔNG configure CENTRAL_URL env var — "
                "vui lòng liên hệ admin."
            ),
            code="CENTRAL_URL_UNAVAILABLE",
        )
    return RedirectResponse(
        url=f"{settings.central_url}{target_path}",
        status_code=307,
        headers={
            "X-SSO-Redirect-Reason": f"hub_con_no_local_{target_path.rsplit('/', 1)[-1]}",
            "X-SSO-Original-Hub": hub_name,
        },
    )


@router.post("/login", response_model=None)
async def login(
    req: LoginRequest,
    service: AuthService = Depends(get_auth_service),  # noqa: B008
) -> JSONResponse | RedirectResponse:
    """Login endpoint — hub con redirect 307 tới central; central handle local.

    Phase 3 Plan 03-04 SSO-02 (D-V3-Phase3-G): Hub con KHÔNG sinh JWT/refresh
    token — 100% session lifecycle ở central. Hub con trả 307 Location: central
    để browser auto-follow + preserve POST method + body (RFC 7231).
    """
    settings = get_settings()
    if settings.hub_name != "central":
        return _sso_redirect("/api/auth/login", settings.hub_name)

    # Central path — M2 logic carry forward
    try:
        result = await service.login(req)
    except AuthError as e:
        return _auth_error_to_response(e)
    # mode="json" — serialize datetime trong user.created_at/updated_at sang ISO.
    return resp.ok(data=result.model_dump(mode="json"))


@router.post("/refresh", response_model=None)
async def refresh(
    req: RefreshRequest,
    service: AuthService = Depends(get_auth_service),  # noqa: B008
) -> JSONResponse | RedirectResponse:
    """Refresh endpoint — hub con redirect 307 tới central (D-V3-Phase3-C/G).

    Hub con KHÔNG sinh refresh token (D-V3-Phase3-C LOCKED — 100% refresh ở
    central). Plan 03-04 wire cuối cùng: hub con trả 307 thay vì handle local.
    """
    settings = get_settings()
    if settings.hub_name != "central":
        return _sso_redirect("/api/auth/refresh", settings.hub_name)

    # Central path — M2 logic carry forward
    try:
        result = await service.refresh(req)
    except AuthError as e:
        return _auth_error_to_response(e)
    return resp.ok(data=result.model_dump(mode="json"))


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
    return resp.ok(data=public.model_dump(mode="json"))
