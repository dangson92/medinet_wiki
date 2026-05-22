"""FastAPI dependencies — Plan 03-04 (AUTH-01..03) + skeleton AUTH-04 (Plan 03-05).

Dependencies:
- get_jwt_manager       — lấy JWTManager singleton từ app.state (init lifespan).
- get_auth_service      — compose AuthService với DB session + Redis + JWT.
- get_current_user      — extract Bearer + verify + blacklist check → User.
- require_role          — gate endpoint theo role (AUTH-04).
- get_current_user_with_hubs — User + hub_assignments từ user_hubs (HUB-02).
- get_api_key_or_jwt    — auth qua X-API-Key HOẶC Bearer JWT (AUX-02 — Plan 05-05).
- get_api_key_or_jwt_with_hubs — auth X-API-Key HOặC JWT + hub_assignments (Phase 8.2).
"""
from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from redis.asyncio import Redis
from sqlalchemy import select, text
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


async def get_current_user(  # noqa: C901 — Phase 3 branch verify path hub con
    request: Request,
    token: str | None = Depends(oauth2_scheme),  # noqa: B008
    jwt_mgr: JWTManager = Depends(get_jwt_manager),  # noqa: B008
    redis: Redis | None = Depends(get_redis),  # noqa: B008
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> User:
    """Verify Bearer access token → User entity.

    Phase 3 Plan 03-02 SSO-01 (D-V3-Phase3-D) — Hub con verify qua JWKSCache:
    - central: dùng JWTManager.verify_token (local public.pem M2 carry forward)
    - hub con: dùng JWKSCache.get_public_key(kid) → verify_token_with_key

    Trình tự reject (KHÔNG đổi từ M2):
    1. Token rỗng → 401 MISSING_AUTHORIZATION
    2. Sai signature/expired/sai issuer/sai alg → 401 INVALID_TOKEN
    3. Sai type (refresh thay vì access) → 401 INVALID_TOKEN_TYPE
    4. JTI trong Redis blacklist → 401 TOKEN_REVOKED
    5. User không tồn tại / disabled → 401 USER_DISABLED

    Phase 3 Plan 03-02 thêm reject paths (hub con only):
    6. JWT thiếu kid header → 401 INVALID_TOKEN ("Token thiếu kid header")
    7. kid mismatch JWKS cache → 401 INVALID_TOKEN
    8. JWKSCache stale > 24h → 503 JWKS_STALE (R-V3-5 fail-loud delayed)
    9. JWKSCache chưa init (hub con boot fail) → 503 JWKS_CACHE_UNAVAILABLE
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

    # Phase 3 Plan 03-02 — branch verify path theo hub_name (D-V3-Phase3-D).
    from app.config import get_settings

    settings = get_settings()
    if settings.hub_name == "central":
        # Central: local public.pem M2 path (verify_token carry forward).
        try:
            claims = jwt_mgr.verify_token(token, expected_type="access")
        except JWTError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": "INVALID_TOKEN", "message": str(e)},
                headers={"WWW-Authenticate": "Bearer"},
            ) from e
    else:
        # Hub con: verify qua JWKSCache (D-V3-Phase3-D).
        import jwt as pyjwt

        from app.auth.jwks import (
            JWKSCache,
            JWKSKidNotFoundError,
            JWKSStaleError,
        )

        jwks_cache: JWKSCache | None = getattr(
            request.app.state, "jwks_cache", None
        )
        if jwks_cache is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "code": "JWKS_CACHE_UNAVAILABLE",
                    "message": "JWKSCache chưa init — hub con boot fail?",
                },
            )

        # Extract kid từ JWT header (pre-verify-by-design — kid chỉ để select
        # key; signature verify ở step verify_token_with_key sau).
        try:
            unverified_header = pyjwt.get_unverified_header(token)
        except pyjwt.InvalidTokenError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "code": "INVALID_TOKEN",
                    "message": f"JWT header invalid: {e}",
                },
                headers={"WWW-Authenticate": "Bearer"},
            ) from e

        kid = unverified_header.get("kid")
        if kid is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "code": "INVALID_TOKEN",
                    "message": (
                        "Token thiếu kid header — JWT phát hành trước Phase 3 "
                        "SSO, vui lòng đăng nhập lại"
                    ),
                },
                headers={"WWW-Authenticate": "Bearer"},
            )

        try:
            public_key = jwks_cache.get_public_key(kid)
        except JWKSStaleError as e:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"code": "JWKS_STALE", "message": str(e)},
            ) from e
        except JWKSKidNotFoundError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "code": "INVALID_TOKEN",
                    "message": f"kid không khớp JWKS cache: {e}",
                },
                headers={"WWW-Authenticate": "Bearer"},
            ) from e

        try:
            claims = jwt_mgr.verify_token_with_key(
                token, public_key, expected_type="access"
            )
        except JWTError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": "INVALID_TOKEN", "message": str(e)},
                headers={"WWW-Authenticate": "Bearer"},
            ) from e

    # Blacklist check (Plan 03-03 sẽ rename `blacklist:` → `auth:blacklist:`).
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
    """AUTH-04 — gate endpoint chỉ cho role trong `roles` được pass.

    Usage:
        @router.delete("/admin/something", dependencies=[Depends(require_role("admin"))])
        async def delete(...): ...

    Hoặc inject user trực tiếp:
        @router.put("/...")
        async def edit(user: User = Depends(require_role("admin", "editor"))):
            ...

    Behavior:
    - Tham số `*roles`: variadic string (e.g., `require_role("admin")`,
      `require_role("admin", "editor")`).
    - Return Callable mà FastAPI inject `user = Depends(get_current_user)`.
    - Nếu `user.role in roles` → return `user` (downstream handler dùng).
    - Nếu `user.role not in roles` → raise HTTPException 403 với envelope
      shape `{"code":"FORBIDDEN", "message":"..."}`.
    - Nếu authentication fail (token sai/missing) → `get_current_user`
      raise 401 trước, dependency này KHÔNG bao giờ run trong case đó.

    Raise:
    - ValueError ngay khi gọi `require_role()` không argument — guard tránh
      khai báo route mở cho mọi role (security gate).
    """
    if not roles:
        raise ValueError("require_role cần ít nhất 1 role")
    allowed = set(roles)

    async def _dependency(user: User = Depends(get_current_user)) -> User:  # noqa: B008
        if user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "FORBIDDEN",
                    "message": f"Không đủ quyền — yêu cầu một trong {sorted(allowed)}",
                },
            )
        return user

    return _dependency


class UserWithHubs:
    """User ORM + danh sách hub_id được assign (HUB-02 isolation source).

    `hub_ids` lấy từ DB `user_hubs` join table — KHÔNG tin payload. Dùng cho
    `hub_filter_clause()` / `verify_hub_access()` ở repository/service layer.
    """

    def __init__(self, user: User, hub_ids: list[str]) -> None:
        self.user = user
        self.hub_ids = hub_ids


async def get_current_user_with_hubs(
    user: User = Depends(get_current_user),  # noqa: B008 — FastAPI pattern
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> UserWithHubs:
    """User + hub_assignments từ user_hubs (HUB-02 isolation source).

    Lấy hub_ids từ DB `user_hubs` (KHÔNG tin request payload). admin role vẫn
    trả hub_ids thực tế nhưng `hub_filter_clause`/`verify_hub_access` sẽ bypass
    filter cho admin (quản trị cross-hub theo thiết kế).
    """
    from app.models.auth import UserHub

    stmt = select(UserHub.hub_id).where(UserHub.user_id == user.id)
    hub_ids = [str(h) for h in (await db.execute(stmt)).scalars().all()]
    return UserWithHubs(user=user, hub_ids=hub_ids)


async def get_api_key_or_jwt(
    request: Request,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),  # noqa: B008
    token: str | None = Depends(oauth2_scheme),  # noqa: B008
    jwt_mgr: JWTManager = Depends(get_jwt_manager),  # noqa: B008
    redis: Redis | None = Depends(get_redis),  # noqa: B008
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> User:
    """Auth qua X-API-Key HOẶC Bearer JWT (AUX-02 — Plan 05-05).

    X-API-Key ưu tiên: verify qua `ApiKeyService.verify_key` (BLOCKER 1 — tên
    method canonical) → load `api_keys.created_by` user. Nếu không có X-API-Key
    → fallback `get_current_user` (Bearer JWT logic).

    # Phase 6/7 scaffolding — chưa endpoint Phase 5 nào consume dependency này
    # (api-keys/audit-logs đều JWT admin-only). Dành cho endpoint external
    # Phase 6/7 (search/ask nhận CẢ JWT lẫn X-API-Key); smoke test qua
    # test_x_api_key_invalid_rejected ở Plan 05-06 verify cùng cơ chế verify_key.
    """
    _ = request  # chữ ký dependency — slowapi/middleware có thể cần.
    if x_api_key:
        from app.services.api_key_service import ApiKeyService

        principal = await ApiKeyService(db=db).verify_key(x_api_key)
        if principal is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "code": "INVALID_API_KEY",
                    "message": "API key không hợp lệ hoặc đã thu hồi",
                },
            )
        # principal["id"] là api_keys.id — cần created_by; query lại key row.
        key_row = (
            await db.execute(
                text(
                    "SELECT created_by FROM api_keys WHERE id = :id"
                ),
                {"id": principal["id"]},
            )
        ).fetchone()
        if key_row is None or key_row[0] is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "code": "INVALID_API_KEY",
                    "message": "API key không gắn user hợp lệ",
                },
            )
        stmt = select(User).where(
            User.id == key_row[0], User.is_active.is_(True)
        )
        user = (await db.execute(stmt)).scalar_one_or_none()
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "code": "INVALID_API_KEY",
                    "message": "User gắn API key đã bị vô hiệu hoá",
                },
            )
        return user

    # Không có X-API-Key → fallback Bearer JWT.
    # Plan 03-02 Task 4 — get_current_user signature thêm request (cần app.state
    # truy cập jwks_cache cho hub con branch).
    return await get_current_user(
        request=request,
        token=token,
        jwt_mgr=jwt_mgr,
        redis=redis,
        db=db,
    )


async def get_api_key_or_jwt_with_hubs(
    user: User = Depends(get_api_key_or_jwt),  # noqa: B008 — FastAPI pattern
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> UserWithHubs:
    """Auth X-API-Key HOặC JWT + hub_assignments từ user_hubs (Phase 8.2).

    Analog `get_current_user_with_hubs` nhưng chấp nhận X-API-Key HOặC Bearer
    JWT. Dùng cho endpoint search/ask để MCP Service (forward X-API-Key của
    client, KHÔNG có JWT) gọi được.

    Điểm KHÁC `get_current_user_with_hubs` DUY NHẤT: `user` inject qua
    `Depends(get_api_key_or_jwt)` thay vì `Depends(get_current_user)` — nhờ vậy
    đường X-API-Key được verify trước (qua `ApiKeyService.verify_key`), đường
    JWT vẫn fallback. Auth fail → `get_api_key_or_jwt` raise 401 TRƯỚC khi hàm
    này chạy (KHÔNG nuốt lỗi).

    `hub_ids` load từ DB `user_hubs` (KHÔNG tin payload) — nguồn hub isolation
    HUB-02. admin vẫn trả `hub_ids` thực tế; bypass filter cho admin xảy ra ở
    service layer (`hub_filter_clause`/`verify_hub_access`), KHÔNG ở dependency
    này — giữ đồng nhất với `get_current_user_with_hubs`.
    """
    from app.models.auth import UserHub

    stmt = select(UserHub.hub_id).where(UserHub.user_id == user.id)
    hub_ids = [str(h) for h in (await db.execute(stmt)).scalars().all()]
    return UserWithHubs(user=user, hub_ids=hub_ids)
