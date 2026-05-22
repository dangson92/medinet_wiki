"""JWT RS256 issuance & verification — port từ Go internal/pkg/jwt/jwt.go.

Stack: PyJWT[crypto] 2.12+, cryptography backend.
AUTH-06 mitigation: load PKCS#8 PEM (Phase 1 đã sinh). Khoá KHÔNG được hardcode,
luôn đọc từ `settings.jwt_private_key_path` + `jwt_public_key_path`.

Claims shape (KHÁC Go điểm `hub_ids` array thay vì `hub_id` single):
    sub        — user UUID string
    email      — email người dùng
    name       — full name (có thể null)
    role       — "admin" | "editor" | "viewer"
    hub_ids    — list[str] UUID hub assignments (M2 multi-hub) — Phase 3 Plan
                 03-03 REQUIRED (M2 cũ JWT thiếu → 401 reject, user re-login)
    iss        — "medinet-wiki" (cố định — RE-CONFIRM D-V3-Phase3-E, KHÔNG URL)
    aud        — list[str] — Phase 3 Plan 03-03 REQUIRED (D-V3-Phase3-E, RFC 7519)
                 single value ["medinet-wiki"] v3.0-a; split per-service defer
                 Phase 7 MCP MIGRATE-04
    iat/exp    — Unix timestamp
    jti        — UUID4 (cho Redis blacklist Plan 03-04)
    token_type — "access" | "refresh"

T-03-jwt-alg-confusion mitigation: `verify_token` cứng `algorithms=["RS256"]`,
KHÔNG list lỏng — tránh attacker swap alg=HS256 ký bằng public key.

Phase 3 Plan 03-03 (SSO-02/03, D-V3-Phase3-E): JWT claim refactor add `aud`
REQUIRED + `hub_ids` REQUIRED. PyJWT decode strict check `audience=JWT_AUDIENCE`
cả 2 path (verify_token + verify_token_with_key) — InvalidAudienceError raise
nếu aud sai hoặc MissingRequiredClaimError nếu thiếu aud claim.

M2 backward incompat (Plan 03-03 deploy):
- JWT cũ KHÔNG có aud → MissingRequiredClaimError → 401 INVALID_TOKEN
- JWT cũ KHÔNG có hub_ids → pydantic ValidationError → 401 INVALID_TOKEN
- Combine với Plan 03-02 backward incompat (JWT cũ KHÔNG có kid header hub con
  reject) → user re-login required (~15-30s downtime acceptable, communicate
  operator qua Plan 03-05 README banner).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

import jwt as pyjwt
from pydantic import BaseModel

from app.config import Settings

if TYPE_CHECKING:
    from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey

JWT_ISSUER = "medinet-wiki"
# Phase 3 Plan 03-03 (D-V3-Phase3-E SSO-02) — single audience cho v3.0-a.
# Split per-service (vd "medinet-wiki-mcp") defer Phase 7 MIGRATE-04 khi MCP
# tách thành audience riêng. RE-CONFIRM D-V3-Phase3-E gốc đề xuất URL-based
# iss "https://central/" — analysis cho thấy chuỗi cố định đủ, URL-based defer
# Phase 7 MCP split aud. Giữ iss "medinet-wiki" M2 baseline carry forward.
JWT_AUDIENCE = "medinet-wiki"
JWT_ALGORITHM = "RS256"
JWT_ALGORITHMS_ALLOWED = [JWT_ALGORITHM]  # cứng, KHÔNG mở rộng — T-03-jwt-alg-confusion


class JWTError(Exception):
    """JWT-related error — wrap PyJWT exception để caller có thông báo VI."""


class JWTClaims(BaseModel):
    """Pydantic v2 model cho claims đã decode (validate sớm sau verify).

    Phase 3 Plan 03-03 (SSO-02/03, D-V3-Phase3-E):
    - `hub_ids`: REQUIRED (xoá default `[]` M2 baseline). M2 cũ JWT thiếu claim
      → pydantic ValidationError → JWTError 401 INVALID_TOKEN. Empty list `[]`
      OK (admin chưa assign hub onboard scenario).
    - `aud`: REQUIRED list[str] (RFC 7519 audience). PyJWT decode strict check
      `audience=JWT_AUDIENCE` raise InvalidAudienceError nếu mismatch.
    """

    sub: str
    email: str
    name: str | None = None
    role: Literal["admin", "editor", "viewer"]
    # Phase 3 Plan 03-03 — hub_ids REQUIRED (D-V3-Phase3-E + SSO-03).
    # M2 cũ JWT default [] → bỏ default → JWT thiếu claim raise ValidationError.
    hub_ids: list[str]
    iss: str
    # Phase 3 Plan 03-03 — aud REQUIRED (D-V3-Phase3-E + RFC 7519). Single value
    # ["medinet-wiki"] v3.0-a; PyJWT decode strict check qua audience param.
    aud: list[str]
    iat: int
    exp: int
    jti: str
    token_type: Literal["access", "refresh"]


@dataclass(frozen=True)
class TokenPair:
    """Cặp access + refresh token sinh ra từ `JWTManager.issue_token_pair()`."""

    access_token: str
    refresh_token: str
    access_jti: str
    refresh_jti: str
    access_expires_at: datetime
    refresh_expires_at: datetime


class JWTManager:
    """Quản lý sign/verify JWT RS256 cho Medinet Wiki M2.

    Load PEM 1 lần ở constructor (raise nếu fail) — KHÔNG re-read mỗi call.
    """

    def __init__(self, settings: Settings) -> None:
        self._private_pem = self._load_key(settings.jwt_private_key_path)
        self._public_pem = self._load_key(settings.jwt_public_key_path)
        self._access_ttl = timedelta(seconds=settings.jwt_access_token_ttl)
        self._refresh_ttl = timedelta(seconds=settings.jwt_refresh_token_ttl)
        # Phase 3 Plan 03-02 SSO-01 — kid derive deterministic SHA-256 public.pem
        # (cùng pattern jwks.py::_derive_kid). Hub con JWKSCache match qua kid
        # ở JWT header để chọn đúng public key verify (Task 4 get_current_user).
        from app.auth.jwks import _derive_kid

        self._kid = _derive_kid(self._public_pem)

    @staticmethod
    def _load_key(path: Path) -> bytes:
        """Đọc PEM bytes; raise JWTError với message VI nếu fail."""
        try:
            return path.read_bytes()
        except OSError as e:
            raise JWTError(
                f"Không đọc được khoá JWT tại {path!s}: {e}. "
                f"Chạy 'make keys' để sinh hoặc kiểm tra "
                f"JWT_PRIVATE_KEY_PATH/JWT_PUBLIC_KEY_PATH."
            ) from e

    def issue_token_pair(
        self,
        *,
        user_id: str,
        email: str,
        full_name: str | None,
        role: str,
        hub_ids: list[str],
    ) -> TokenPair:
        """Sinh cặp access + refresh JWT RS256.

        access TTL = settings.jwt_access_token_ttl (default 900s = 15min).
        refresh TTL = settings.jwt_refresh_token_ttl (default 604800s = 7d).
        Cả 2 token có jti UUID4 riêng cho Redis blacklist Plan 03-04.
        """
        now = datetime.now(tz=UTC)
        access_jti = str(uuid.uuid4())
        refresh_jti = str(uuid.uuid4())
        access_exp = now + self._access_ttl
        refresh_exp = now + self._refresh_ttl

        base: dict[str, Any] = {
            "sub": user_id,
            "email": email,
            "name": full_name,
            "role": role,
            "hub_ids": hub_ids,
            "iss": JWT_ISSUER,
            # Phase 3 Plan 03-03 (D-V3-Phase3-E SSO-02) — aud REQUIRED list[str]
            # ["medinet-wiki"]. PyJWT decode verify_token + verify_token_with_key
            # strict check qua audience=JWT_AUDIENCE param.
            "aud": [JWT_AUDIENCE],
            "iat": int(now.timestamp()),
        }
        access_claims = {
            **base,
            "exp": int(access_exp.timestamp()),
            "jti": access_jti,
            "token_type": "access",
        }
        refresh_claims = {
            **base,
            "exp": int(refresh_exp.timestamp()),
            "jti": refresh_jti,
            "token_type": "refresh",
        }
        # Phase 3 Plan 03-02 SSO-01 — Header kid để hub con JWKSCache match
        # public key (Task 4 get_current_user). M2 backward incompat note:
        # JWT cũ KHÔNG có kid → hub con reject 401 sau Plan 03-02 deploy
        # (acceptable downtime 15-30s — Plan 03-05 README banner).
        access_token = pyjwt.encode(
            access_claims,
            self._private_pem,
            algorithm=JWT_ALGORITHM,
            headers={"kid": self._kid},
        )
        refresh_token = pyjwt.encode(
            refresh_claims,
            self._private_pem,
            algorithm=JWT_ALGORITHM,
            headers={"kid": self._kid},
        )

        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
            access_jti=access_jti,
            refresh_jti=refresh_jti,
            access_expires_at=access_exp,
            refresh_expires_at=refresh_exp,
        )

    def verify_token(
        self,
        token: str,
        *,
        expected_type: Literal["access", "refresh"],
    ) -> JWTClaims:
        """Decode + validate. Raise JWTError với message tiếng Việt nếu fail.

        Validate:
        - alg=RS256 (KHÔNG mở rộng — T-03-jwt-alg-confusion).
        - issuer="medinet-wiki".
        - exp chưa expired.
        - token_type khớp `expected_type`.
        """
        try:
            decoded = pyjwt.decode(
                token,
                self._public_pem,
                algorithms=JWT_ALGORITHMS_ALLOWED,
                issuer=JWT_ISSUER,
                # Phase 3 Plan 03-03 (D-V3-Phase3-E SSO-02) — audience strict check.
                # PyJWT raise InvalidAudienceError nếu aud claim mismatch hoặc
                # MissingRequiredClaimError nếu thiếu aud (M2 cũ JWT reject).
                audience=JWT_AUDIENCE,
            )
        except pyjwt.ExpiredSignatureError as e:
            raise JWTError("Token đã hết hạn") from e
        except pyjwt.InvalidIssuerError as e:
            raise JWTError("Token không hợp lệ (issuer sai)") from e
        except pyjwt.InvalidAudienceError as e:
            raise JWTError(
                f"Token không hợp lệ (audience sai — yêu cầu {JWT_AUDIENCE!r})"
            ) from e
        except pyjwt.MissingRequiredClaimError as e:
            raise JWTError(
                f"Token thiếu claim bắt buộc: {e}. "
                "JWT phát hành trước Phase 3 SSO — vui lòng đăng nhập lại."
            ) from e
        except pyjwt.InvalidTokenError as e:
            raise JWTError(f"Token không hợp lệ: {e}") from e

        try:
            claims = JWTClaims.model_validate(decoded)
        except Exception as e:  # pydantic.ValidationError (hub_ids missing)
            raise JWTError(
                f"Claims không hợp lệ: {e}. "
                "JWT có thể phát hành trước Phase 3 SSO — vui lòng đăng nhập lại."
            ) from e

        if claims.token_type != expected_type:
            raise JWTError(
                f"Loại token sai: yêu cầu {expected_type!r}, "
                f"nhận {claims.token_type!r}"
            )
        return claims

    def verify_token_with_key(
        self,
        token: str,
        public_key: bytes | RSAPublicKey,
        *,
        expected_type: Literal["access", "refresh"],
    ) -> JWTClaims:
        """Verify JWT bằng public key external (Plan 03-02 hub con JWKS cache).

        Phase 3 Plan 03-02 SSO-01 (D-V3-Phase3-D). Hub con verify JWT bằng
        public key từ JWKSCache (KHÔNG dùng self._public_pem — local pem
        chỉ có ở central). Logic decode + validate giống `verify_token`,
        chỉ khác key source.

        Args:
            token: JWT string.
            public_key: RSAPublicKey object (từ JWKSCache.get_public_key)
                hoặc PEM bytes (backward compat).
            expected_type: "access" | "refresh".

        Raises:
            JWTError với message tiếng Việt (alg/issuer/exp/type mismatch).
        """
        try:
            decoded = pyjwt.decode(
                token,
                public_key,
                algorithms=JWT_ALGORITHMS_ALLOWED,
                issuer=JWT_ISSUER,
                # Phase 3 Plan 03-03 (D-V3-Phase3-E SSO-02) — audience strict
                # check ở hub con path (cùng semantic verify_token).
                audience=JWT_AUDIENCE,
            )
        except pyjwt.ExpiredSignatureError as e:
            raise JWTError("Token đã hết hạn") from e
        except pyjwt.InvalidIssuerError as e:
            raise JWTError("Token không hợp lệ (issuer sai)") from e
        except pyjwt.InvalidAudienceError as e:
            raise JWTError(
                f"Token không hợp lệ (audience sai — yêu cầu {JWT_AUDIENCE!r})"
            ) from e
        except pyjwt.MissingRequiredClaimError as e:
            raise JWTError(
                f"Token thiếu claim bắt buộc: {e}. "
                "JWT phát hành trước Phase 3 SSO — vui lòng đăng nhập lại."
            ) from e
        except pyjwt.InvalidTokenError as e:
            raise JWTError(f"Token không hợp lệ: {e}") from e

        try:
            claims = JWTClaims.model_validate(decoded)
        except Exception as e:  # pydantic.ValidationError (hub_ids missing)
            raise JWTError(
                f"Claims không hợp lệ: {e}. "
                "JWT có thể phát hành trước Phase 3 SSO — vui lòng đăng nhập lại."
            ) from e

        if claims.token_type != expected_type:
            raise JWTError(
                f"Loại token sai: yêu cầu {expected_type!r}, "
                f"nhận {claims.token_type!r}"
            )
        return claims

    @property
    def access_ttl_seconds(self) -> int:
        return int(self._access_ttl.total_seconds())

    @property
    def refresh_ttl_seconds(self) -> int:
        return int(self._refresh_ttl.total_seconds())
