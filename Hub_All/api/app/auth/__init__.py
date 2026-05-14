"""Auth package — Phase 3 (AUTH-01..06).

Public API:
    from app.auth import (
        # JWT (Plan 03-02)
        JWTManager,
        JWTClaims,
        JWTError,
        TokenPair,
        JWT_ISSUER,
        JWT_ALGORITHM,
        # Password (Plan 03-03)
        hash_password,
        verify_password,
        ARGON2_MEMORY_COST,
        ARGON2_TIME_COST,
        ARGON2_PARALLELISM,
        ARGON2_SALT_LEN,
        ARGON2_HASH_LEN,
    )

Plan 03-02 ships JWT layer. Plan 03-03 extends với Argon2 password hasher.
Plan 03-04 sẽ extend với auth router (login/refresh/logout/me).
"""
from __future__ import annotations

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

__all__ = [
    "ARGON2_HASH_LEN",
    "ARGON2_MEMORY_COST",
    "ARGON2_PARALLELISM",
    "ARGON2_SALT_LEN",
    "ARGON2_TIME_COST",
    "JWT_ALGORITHM",
    "JWT_ISSUER",
    "JWTClaims",
    "JWTError",
    "JWTManager",
    "TokenPair",
    "hash_password",
    "verify_password",
]
