"""Auth package — Phase 3 (AUTH-01..06).

Public API:
    from app.auth import (
        # JWT (Plan 03-02)
        JWTManager, JWTClaims, JWTError, TokenPair,
        JWT_ISSUER, JWT_ALGORITHM,
        # Password (Plan 03-03)
        hash_password, verify_password,
        ARGON2_MEMORY_COST, ARGON2_TIME_COST, ARGON2_PARALLELISM,
        ARGON2_SALT_LEN, ARGON2_HASH_LEN,
        # Service + dependencies + router (Plan 03-04)
        AuthService, AuthError,
        get_auth_service, get_current_user, get_jwt_manager,
        oauth2_scheme, require_role,
        auth_router,
    )

Plan 03-02 ships JWT layer. Plan 03-03 extends với Argon2 password hasher.
Plan 03-04 thêm AuthService + dependencies + router (4 endpoint
login/refresh/logout/me).
"""
from __future__ import annotations

from app.auth.api_key import require_api_key
from app.auth.dependencies import (
    UserWithHubs,
    get_api_key_or_jwt,
    get_auth_service,
    get_current_user,
    get_current_user_with_hubs,
    get_jwt_manager,
    oauth2_scheme,
    require_role,
)
from app.auth.jwt import (
    JWT_ALGORITHM,
    JWT_ISSUER,
    JWTClaims,
    JWTError,
    JWTManager,
    TokenPair,
)
from app.auth.password import (
    ARGON2_HASH_LEN,
    ARGON2_MEMORY_COST,
    ARGON2_PARALLELISM,
    ARGON2_SALT_LEN,
    ARGON2_TIME_COST,
    hash_password,
    verify_password,
)
from app.auth.router import router as auth_router
from app.auth.service import AuthError, AuthService

__all__ = [
    "ARGON2_HASH_LEN",
    "ARGON2_MEMORY_COST",
    "ARGON2_PARALLELISM",
    "ARGON2_SALT_LEN",
    "ARGON2_TIME_COST",
    "AuthError",
    "AuthService",
    "JWT_ALGORITHM",
    "JWT_ISSUER",
    "JWTClaims",
    "JWTError",
    "JWTManager",
    "TokenPair",
    "UserWithHubs",
    "auth_router",
    "get_api_key_or_jwt",
    "get_auth_service",
    "get_current_user",
    "get_current_user_with_hubs",
    "get_jwt_manager",
    "hash_password",
    "oauth2_scheme",
    "require_api_key",
    "require_role",
    "verify_password",
]
