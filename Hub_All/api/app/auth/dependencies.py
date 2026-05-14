"""FastAPI dependencies — Plan 03-04 (AUTH-01..03) + skeleton AUTH-04 (Plan 03-05).

Dependencies:
- get_jwt_manager       — lấy JWTManager singleton từ app.state (init lifespan).
- get_auth_service      — compose AuthService với DB session + Redis + JWT.
- get_current_user      — extract Bearer + verify + blacklist check → User.
- require_role          — SKELETON (Plan 03-05 implement đầy đủ).
"""
from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import JWTError, JWTManager
from app.auth.service import AuthService
from app.db.session import get_session
from app.models.auth import User

logger = logging.getLogger(__name__)

# auto_error=False → 401 với code cụ thể qua HTTPException, KHÔNG để FastAPI
# raise 403 mặc định.
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/auth/login", auto_error=False
)


def get_jwt_manager(request: Request) -> JWTManager:
    """Lấy JWTManager singleton (init ở lifespan Task 05)."""
    mgr = getattr(request.app.state, "jwt_manager", None)
    if mgr is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "SERVICE_UNAVAILABLE",
                "message": "JWTManager chưa init",
            },
        )
    return mgr  # type: ignore[no-any-return]


def get_redis(request: Request) -> Redis | None:
    """Lấy Redis client (None nếu Redis down — Phase 3 fail-open)."""
    return getattr(request.app.state, "redis", None)


def get_dummy_password_hash(request: Request) -> str:
    """Lấy dummy hash pre-computed cho anti-timing — init ở lifespan."""
    h = getattr(request.app.state, "dummy_password_hash", None)
    if h is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "SERVICE_UNAVAILABLE",
                "message": "dummy_password_hash chưa init",
            },
        )
    return str(h)


def get_auth_service(
    db: AsyncSession = Depends(get_session),  # noqa: B008 — FastAPI pattern
    redis: Redis | None = Depends(get_redis),  # noqa: B008
    jwt_mgr: JWTManager = Depends(get_jwt_manager),  # noqa: B008
    dummy_hash: str = Depends(get_dummy_password_hash),  # noqa: B008
) -> AuthService:
    return AuthService(
        db=db,
        redis=redis,
        jwt_manager=jwt_mgr,
        dummy_password_hash=dummy_hash,
    )


async def get_current_user(
    token: str | None = Depends(oauth2_scheme),  # noqa: B008
    jwt_mgr: JWTManager = Depends(get_jwt_manager),  # noqa: B008
    redis: Redis | None = Depends(get_redis),  # noqa: B008
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> User:
    """Verify Bearer access token → User entity.

    Trình tự reject:
    1. Token rỗng → 401 MISSING_AUTHORIZATION
    2. Sai signature/expired/sai issuer/sai alg → 401 INVALID_TOKEN
    3. Sai type (refresh thay vì access) → 401 INVALID_TOKEN_TYPE
    4. JTI trong Redis blacklist → 401 TOKEN_REVOKED
    5. User không tồn tại / disabled → 401 USER_DISABLED
    """
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "MISSING_AUTHORIZATION",
                "message": "Yêu cầu Bearer token",
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        claims = jwt_mgr.verify_token(token, expected_type="access")
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_TOKEN", "message": str(e)},
            headers={"WWW-Authenticate": "Bearer"},
        ) from e

    # Blacklist check.
    if redis is not None:
        is_blacklisted = await redis.exists(f"blacklist:{claims.jti}")
        if is_blacklisted:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "code": "TOKEN_REVOKED",
                    "message": "Token đã bị thu hồi",
                },
                headers={"WWW-Authenticate": "Bearer"},
            )

    # Load user.
    stmt = select(User).where(
        User.id == UUID(claims.sub), User.is_active.is_(True)
    )
    user = (await db.execute(stmt)).scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "USER_DISABLED",
                "message": "Tài khoản đã bị vô hiệu hoá",
            },
        )
    return user


def require_role(
    *roles: str,
) -> Callable[[User], Awaitable[User]]:
    """Plan 03-05 sẽ implement đầy đủ.

    Hiện tại Plan 03-04 KHÔNG dùng (4 endpoint login/refresh/logout/me chỉ
    cần authenticate, không cần role-gate). Stub raise NotImplementedError
    nếu gọi để guard regression.
    """

    async def _dependency(user: User = Depends(get_current_user)) -> User:  # noqa: B008
        raise NotImplementedError(
            "require_role chưa implement — Plan 03-05 sẽ extend. "
            f"Requested roles: {roles}"
        )

    return _dependency
