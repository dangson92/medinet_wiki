"""Auth service layer — Plan 03-04 (AUTH-01..03).

Logic 4 use-case + Redis blacklist + anti-timing oracle (Pitfall 6 + T-03-pw-timing).
P16 mitigation: SETNX atomic lock trên jti cũ trước khi rotate refresh token.
"""
from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy import update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import JWTError, JWTManager
from app.auth.password import verify_password
from app.auth.schemas import (
    LoginRequest,
    LoginResponse,
    RefreshRequest,
    UserPublic,
)
from app.models.auth import RefreshToken, User, UserHub

logger = logging.getLogger(__name__)


class AuthError(Exception):
    """Auth-specific error → router map sang envelope error response."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"[{code}] {message}")


def _hash_refresh_token(token: str) -> str:
    """T-02-03 mitigation — store SHA-256 thay vì plaintext refresh token."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class AuthService:
    """4 use-case: login, refresh, logout, get_current_user_info."""

    def __init__(
        self,
        db: AsyncSession,
        redis: Redis | None,
        jwt_manager: JWTManager,
        dummy_password_hash: str,
    ) -> None:
        self.db = db
        self.redis = redis
        self.jwt_manager = jwt_manager
        self.dummy_password_hash = dummy_password_hash

    async def login(self, req: LoginRequest) -> LoginResponse:
        """AUTH-01 — verify credential, issue tokens, store refresh hash."""
        # Anti-timing — luôn verify_password kể cả user không tồn tại.
        stmt = select(User).where(
            User.email == str(req.email), User.is_active.is_(True)
        )
        user = (await self.db.execute(stmt)).scalar_one_or_none()
        hash_to_check = user.password_hash if user else self.dummy_password_hash
        ok = verify_password(req.password, hash_to_check)
        if user is None or not ok:
            logger.info(
                "auth_login_failed",
                extra={"email_present": user is not None, "reason": "credential"},
            )
            raise AuthError(
                "INVALID_CREDENTIALS", "Email hoặc mật khẩu không đúng"
            )

        # Hub assignments (USER-03 multi-hub).
        hub_stmt = select(UserHub.hub_id).where(UserHub.user_id == user.id)
        hub_ids = [
            str(h) for h in (await self.db.execute(hub_stmt)).scalars().all()
        ]

        pair = self.jwt_manager.issue_token_pair(
            user_id=str(user.id),
            email=user.email,
            full_name=user.full_name,
            role=user.role,
            hub_ids=hub_ids,
        )

        # Lưu refresh hash (T-02-03 mitigation — KHÔNG plaintext).
        rt = RefreshToken(
            user_id=user.id,
            token_hash=_hash_refresh_token(pair.refresh_token),
            expires_at=pair.refresh_expires_at,
        )
        self.db.add(rt)
        await self.db.flush()

        logger.info(
            "auth_login_success",
            extra={"user_id": str(user.id), "role": user.role},
        )
        return LoginResponse(
            access_token=pair.access_token,
            refresh_token=pair.refresh_token,
            expires_at=int(pair.access_expires_at.timestamp()),
            user=UserPublic(
                id=str(user.id),
                email=user.email,
                full_name=user.full_name,
                role=user.role,
                hub_assignments=hub_ids,
            ),
        )

    async def refresh(self, req: RefreshRequest) -> LoginResponse:
        """AUTH-02 — rotate refresh token với SETNX atomic lock (P16)."""
        try:
            claims = self.jwt_manager.verify_token(
                req.refresh_token, expected_type="refresh"
            )
        except JWTError as e:
            raise AuthError("INVALID_REFRESH_TOKEN", str(e)) from e

        # P16 mitigation — SETNX atomic lock 30s trên jti cũ.
        if self.redis is not None:
            lock_key = f"lock:refresh:{claims.jti}"
            acquired = await self.redis.set(lock_key, "1", nx=True, ex=30)
            if not acquired:
                raise AuthError(
                    "REFRESH_RACE",
                    "Refresh token đang được xử lý — vui lòng thử lại",
                )
            # Check blacklist NGAY SAU lock acquired (case: refresh đã hoàn tất
            # trước khi lock TTL expire — old jti đã trong blacklist).
            already_revoked = await self.redis.exists(f"blacklist:{claims.jti}")
            if already_revoked:
                raise AuthError("TOKEN_REVOKED", "Refresh token đã bị thu hồi")
        else:
            logger.warning(
                "auth_refresh_no_redis_lock — P16 race protection disabled"
            )

        # Load user.
        stmt = select(User).where(
            User.id == UUID(claims.sub), User.is_active.is_(True)
        )
        user = (await self.db.execute(stmt)).scalar_one_or_none()
        if user is None:
            raise AuthError("USER_DISABLED", "Tài khoản đã bị vô hiệu hoá")

        # Hub assignments fresh.
        hub_stmt = select(UserHub.hub_id).where(UserHub.user_id == user.id)
        hub_ids = [
            str(h) for h in (await self.db.execute(hub_stmt)).scalars().all()
        ]

        pair = self.jwt_manager.issue_token_pair(
            user_id=str(user.id),
            email=user.email,
            full_name=user.full_name,
            role=user.role,
            hub_ids=hub_ids,
        )

        # Blacklist old jti + revoke DB row.
        if self.redis is not None:
            await self.redis.set(
                f"blacklist:{claims.jti}",
                "1",
                ex=self.jwt_manager.refresh_ttl_seconds,
            )
        old_hash = _hash_refresh_token(req.refresh_token)
        await self.db.execute(
            sa_update(RefreshToken)
            .where(RefreshToken.token_hash == old_hash)
            .values(revoked_at=datetime.now(tz=UTC))
        )

        # INSERT new refresh hash.
        rt = RefreshToken(
            user_id=user.id,
            token_hash=_hash_refresh_token(pair.refresh_token),
            expires_at=pair.refresh_expires_at,
        )
        self.db.add(rt)
        await self.db.flush()

        logger.info(
            "auth_refresh_success",
            extra={"user_id": str(user.id), "old_jti": claims.jti},
        )
        return LoginResponse(
            access_token=pair.access_token,
            refresh_token=pair.refresh_token,
            expires_at=int(pair.access_expires_at.timestamp()),
            user=UserPublic(
                id=str(user.id),
                email=user.email,
                full_name=user.full_name,
                role=user.role,
                hub_assignments=hub_ids,
            ),
        )

    async def logout(
        self,
        *,
        access_jti: str,
        access_exp: int,
        refresh_token: str | None,
    ) -> None:
        """AUTH-03 — blacklist access (và refresh nếu body cung cấp)."""
        if self.redis is None:
            logger.warning(
                "auth_logout_no_redis — blacklist disabled, defer Phase 10"
            )
            return
        now_ts = int(datetime.now(tz=UTC).timestamp())
        access_ttl = max(1, access_exp - now_ts)
        await self.redis.set(f"blacklist:{access_jti}", "1", ex=access_ttl)

        if refresh_token:
            try:
                claims = self.jwt_manager.verify_token(
                    refresh_token, expected_type="refresh"
                )
                await self.redis.set(
                    f"blacklist:{claims.jti}",
                    "1",
                    ex=self.jwt_manager.refresh_ttl_seconds,
                )
                old_hash = _hash_refresh_token(refresh_token)
                await self.db.execute(
                    sa_update(RefreshToken)
                    .where(RefreshToken.token_hash == old_hash)
                    .values(revoked_at=datetime.now(tz=UTC))
                )
            except JWTError:
                logger.info("auth_logout_invalid_refresh — bỏ qua")

    async def get_current_user_info(self, user_id: str) -> UserPublic:
        """AUTH-03 — GET /api/auth/me data."""
        stmt = select(User).where(
            User.id == UUID(user_id), User.is_active.is_(True)
        )
        user = (await self.db.execute(stmt)).scalar_one_or_none()
        if user is None:
            raise AuthError("USER_NOT_FOUND", "Không tìm thấy tài khoản")
        hub_stmt = select(UserHub.hub_id).where(UserHub.user_id == user.id)
        hub_ids = [
            str(h) for h in (await self.db.execute(hub_stmt)).scalars().all()
        ]
        return UserPublic(
            id=str(user.id),
            email=user.email,
            full_name=user.full_name,
            role=user.role,
            hub_assignments=hub_ids,
        )
