"""Pydantic v2 schemas — request/response cho 4 auth endpoint.

Match shape Go cũ (D6 frontend compat):
- LoginRequest  / LoginResponse  → POST /api/auth/login
- RefreshRequest                 → POST /api/auth/refresh
- LogoutRequest                  → POST /api/auth/logout (optional refresh_token body)
- UserWithRolesResponse          → embedded trong LoginResponse + GET /api/auth/me

`user` trong LoginResponse dùng `UserWithRolesResponse` (`{user, roles}`) — KHÔNG
shape phẳng. Go cũ trả `model.UserWithRoles` (xem git tag `m1-go-archived`); frontend
React `services/api.ts` (`UserWithRoles`) + `Layout.tsx` đọc `user.user.name`.

Pydantic v2 EmailStr requires `pydantic[email]` — đã có qua `pydantic>=2.7` dep.
Nếu missing, đổi `EmailStr` → `str` + validator manual (Phase 3 chấp nhận
nếu email-validator unbundle).
"""
from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field

from app.schemas.users import UserWithRolesResponse


class LoginRequest(BaseModel):
    """POST /api/auth/login request body."""

    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class LoginResponse(BaseModel):
    """Login success — data field trong envelope `{success, data, error, meta}`.

    `user` là `UserWithRolesResponse` (`{user, roles}`) — D6 contract với
    frontend `UserWithRoles`. KHÔNG flatten (sẽ break `Layout.tsx`).
    """

    access_token: str
    refresh_token: str
    expires_at: int  # Unix timestamp access token expires (frontend show countdown)
    user: UserWithRolesResponse


class RefreshRequest(BaseModel):
    """POST /api/auth/refresh request body."""

    refresh_token: str = Field(min_length=1)


class LogoutRequest(BaseModel):
    """POST /api/auth/logout — refresh_token optional (mục đích blacklist cả pair)."""

    refresh_token: str | None = None
