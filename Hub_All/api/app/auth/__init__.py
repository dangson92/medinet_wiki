"""Auth package — Phase 3 (AUTH-01..06).

Public API:
    from app.auth import (
        JWTManager,
        JWTClaims,
        JWTError,
        TokenPair,
        JWT_ISSUER,
        JWT_ALGORITHM,
    )

Plan 03-02 ships JWT layer. Plan 03-03 sẽ extend với Argon2 password hasher.
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

__all__ = [
    "JWT_ALGORITHM",
    "JWT_ISSUER",
    "JWTClaims",
    "JWTError",
    "JWTManager",
    "TokenPair",
]
