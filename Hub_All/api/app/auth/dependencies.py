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

from app.auth._blacklist import make_blacklist_key
from app.auth.jwt import JWTError, JWTManager
from app.auth.service import AuthService
from app.db.session import get_session
from app.models.auth import User

# Phase 2 Plan 02-01 DEP-01 — get_effective_role helper từ Plan 01-02 ROLE-04.
from app.auth.role import UserNotFoundError, get_effective_role

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

    # Phase 3 Plan 03-03 Task 3 (SSO-04 E4 reinforced) — attach claims vào
    # request.state để get_current_user_for_hub_access dependency reuse
    # KHÔNG cần re-decode JWT. Cả 2 branch (central + hub con) sau verify pass
    # đều set state — pattern này cho phép defense-in-depth Layer 3 enforcement
    # ở endpoint hub-scoped sensitive (xem get_current_user_for_hub_access).
    request.state.jwt_claims = claims

    # Blacklist check — Plan 03-03 D-V3-Phase3-H key `auth:blacklist:{jti}`
    # qua helper (cross-process central + hub con cùng 1 Redis instance M2 baseline).
    if redis is not None:
        is_blacklisted = await redis.exists(make_blacklist_key(claims.jti))
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


async def require_internal_auth(
    x_internal_auth: str | None = Header(default=None, alias="X-Internal-Auth"),  # noqa: B008
) -> None:
    """Phase 6 Plan 06-03 SETTINGS-03 (D-V3-Phase6-D) — Internal-only endpoint gate.

    Verify header `X-Internal-Auth: <settings_proxy_secret>` constant-time compare
    qua `hmac.compare_digest`. 401 INTERNAL_AUTH_FAIL nếu mismatch hoặc thiếu.

    Dùng cho POST /api/api-keys/verify (Plan 06-03 Task 2 — hub con call central
    proxy). KHÔNG expose ra public internet (Caddy block /api/api-keys/verify
    nếu cần — review Plan 05-01 caddy config nếu deploy public-facing).

    Threat model:
    - T-06-03-01 Tampering — secret leak / brute force → attacker bypass.
      `hmac.compare_digest` tránh timing attack (secret entropy ≥ 128-bit
      enforce qua Settings validator Plan 06-01 length ≥ 32 char).
    - T-06-04-03 DoS rate limit — slowapi middleware 100 req/s per IP defer
      Plan 06-XX `rate_limit_internal_per_minute` Settings field nếu cần.

    Returns:
        None on success (FastAPI Depends pattern). Raise HTTPException 401
        INTERNAL_AUTH_FAIL trên mọi failure case (missing/empty/wrong).
    """
    import hmac

    from app.config import get_settings

    settings = get_settings()
    expected = settings.settings_proxy_secret
    if not x_internal_auth or not hmac.compare_digest(x_internal_auth, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "INTERNAL_AUTH_FAIL",
                "message": "Internal auth header missing or invalid",
            },
        )


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


async def assert_hub_admin_for(
    *,
    user: User,
    db: AsyncSession,
    target_hub_id: str,
) -> None:
    """Phase 2 Plan 02-01 DEP-01 (D-V3.1-Phase2-D LOCKED) — Inline validator function.

    Pure async function (KHÔNG phải FastAPI dependency factory). Gọi INLINE
    trong handler SAU khi parse body — vì hub_id nằm trong BODY POST/PATCH
    (KHÔNG path param), pattern Depends factory `require_role(*roles)` không
    khả thi (FastAPI Depends inject TRƯỚC body parse).

    Logic 5 case (D-V3.1-Phase2-D LOCKED):
    1. Super admin (`user.role == 'admin'`) → bypass (no DB call, return None).
    2. Hub_admin của hub đúng (`get_effective_role == 'hub_admin'`) → return None.
    3. Hub_admin của hub khác (`get_effective_role` trả về role khác) → raise 403.
    4. Viewer / editor không phải hub_admin → raise 403.
    5. User KHÔNG tồn tại (UserNotFoundError) → catch + raise 403 (KHÔNG leak 404).

    Args:
        user: User ORM object (đã verify JWT qua `get_current_user`).
        db: AsyncSession đang mở (caller manage lifecycle qua Depends(get_session)).
        target_hub_id: hub_id ở body request (POST/PATCH) — UNTRUSTED user input,
            nhưng KHÔNG dùng làm SQL value trực tiếp (qua get_effective_role
            named bind params — T-01-02-01 mitigation Plan 01-02 carry forward).

    Returns:
        None nếu pass (super admin bypass HOẶC hub_admin của hub đúng).

    Raises:
        HTTPException(403): với envelope D6 `detail={"code": "HUB_ADMIN_REQUIRED",
            "message": "..."}` cho mọi case fail (D-V3.1-Phase2-B LOCKED).

    Usage (Plan 02-03 sẽ refactor 5 router endpoint):
        @router.post("")
        async def create_user(
            req: CreateUserRequest,
            request: Request,
            user: User = Depends(get_current_user),
            db: AsyncSession = Depends(get_session),
            service: UserService = Depends(get_user_service),
        ) -> JSONResponse:
            # DEP-03 — inline scope check sau body parse.
            await assert_hub_admin_for(user=user, db=db, target_hub_id=req.hub_id)
            # ... rest of handler

    Threat model:
        - T-02-01-E Elevation: hub_admin tạo hub mới → KHÔNG mitigated ở dep này
          (DEP-04 require_role("admin") giữ NGUYÊN cho hubs.py mutate endpoints).
        - T-02-02-E Elevation: hub_admin gán role='admin' cho user khác → MỘT PHẦN
          mitigated ở dep này; Plan 02-03 sẽ add business logic block role transition
          'admin' khi caller KHÔNG phải super admin.
        - T-02-05-T Tampering: stale JWT hub_admin sau bị demote → mitigated bởi
          `get_effective_role` query DB live mỗi request (KHÔNG cache role trong JWT).
    """
    # CASE 1 — Super admin bypass (cross-hub by design, D-V3.1-01 LOCKED).
    if user.role == "admin":
        return

    # CASE 2-5 — Hub_admin gate qua get_effective_role per-hub override.
    try:
        effective = await get_effective_role(db, user.id, target_hub_id)
    except UserNotFoundError as e:
        # CASE 5 — Defensive: stale JWT user_id → reject như hub_admin fail.
        # KHÔNG leak existence của user_id (KHÔNG raise 404).
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "HUB_ADMIN_REQUIRED",
                "message": (
                    "Token user không tồn tại — vui lòng đăng nhập lại "
                    "(stale JWT defensive guard)."
                ),
            },
        ) from e

    if effective != "hub_admin":
        # CASE 3-4 — Hub_admin của hub khác / viewer / editor → reject.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "HUB_ADMIN_REQUIRED",
                "message": (
                    f"Yêu cầu hub_admin của hub {target_hub_id!r} — "
                    f"effective role hiện tại: {effective!r}"
                ),
            },
        )
    # CASE 2 — hub_admin đúng → pass (return None implicit).


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


async def get_current_user_for_hub_access(
    request: Request,
    user: User = Depends(get_current_user),  # noqa: B008 — FastAPI pattern
) -> User:
    """Phase 3 Plan 03-03 SSO-04 — Hub con verify HUB_NAME in JWT.hub_ids (E4 reinforced).

    Defense-in-depth Layer 3 bên cạnh:
    - Layer 1: Phase 1 `_enforce_hub_dsn_match` DB-level isolation (Settings validator)
    - Layer 2: repository `WHERE hub_id = settings.hub_name` (M2 carry forward)
    - Layer 3 (MỚI Phase 3 Plan 03-03): JWT claim hub_ids enforcement ở dependency

    Central (hub_name="central"): bypass check — cross-hub by design (admin
        endpoint + cross-hub search expose ở central).
    Hub con (yte/duoc/hcns/dynamic): claims.hub_ids load từ JWT (verified
        signature qua JWKSCache Plan 03-02). Check HUB_NAME in claims.hub_ids
        → reject 403 CROSS_HUB_ACCESS_DENIED nếu mismatch.

    Usage:
        @router.post("/api/documents",
                     dependencies=[Depends(get_current_user_for_hub_access)])
        async def upload(user=Depends(get_current_user_for_hub_access)): ...

    Behavior:
        - get_current_user fail (401) → exception raise trước, dep này KHÔNG run.
        - Central: return user (bypass — cross-hub by design).
        - Hub con + HUB_NAME in claims.hub_ids: return user.
        - Hub con + HUB_NAME not in claims.hub_ids: raise 403 CROSS_HUB_ACCESS_DENIED.

    Threat model (T-03-03-01 SSO-04):
        - Stale JWT cross-hub access — JWT issued cho user duoc với
          hub_ids=["duoc"] post tới hub yte → settings.hub_name="yte" NOT IN
          ["duoc"] → 403 CROSS_HUB_ACCESS_DENIED envelope. KHÔNG 404 (leak hub
          existence) / 500 (server error) / 200 (data leak).
    """
    from app.config import get_settings

    settings = get_settings()
    if settings.hub_name == "central":
        return user  # cross-hub by design

    claims = getattr(request.state, "jwt_claims", None)
    if claims is None:
        # Defensive — get_current_user phải set claims; bug nếu missing
        # (vi phạm dependency contract — phát hiện sớm thay vì silent pass).
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "AUTH_STATE_MISSING",
                "message": (
                    "request.state.jwt_claims không set — internal bug "
                    "(get_current_user dependency chain broken)"
                ),
            },
        )

    if settings.hub_name not in claims.hub_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "CROSS_HUB_ACCESS_DENIED",
                "message": (
                    f"Token KHÔNG có quyền truy cập hub "
                    f"{settings.hub_name!r} (hub_ids JWT = {claims.hub_ids!r})"
                ),
            },
        )
    return user


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
