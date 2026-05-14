"""Pydantic v2 schemas — request/response cho 4 auth endpoint.

Match shape Go cũ (D6 frontend compat):
- LoginRequest  / LoginResponse  → POST /api/auth/login
- RefreshRequest                 → POST /api/auth/refresh
- LogoutRequest                  → POST /api/auth/logout (optional refresh_token body)
- UserPublic                     → embedded trong LoginResponse + GET /api/auth/me

Pydantic v2 EmailStr requires `pydantic[email]` — đã có qua `pydantic>=2.7` dep.
Nếu missing, đổi `EmailStr` → `str` + validator manual (Phase 3 chấp nhận
nếu email-validator unbundle).
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    """POST /api/auth/login request body."""

    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class UserPublic(BaseModel):
    """Public user info — KHÔNG bao gồm password_hash hoặc bất kỳ sensitive field."""

    id: str  # UUID string
    email: str
    full_name: str | None
    role: Literal["admin", "editor", "viewer"]
    hub_assignments: list[str] = Field(
        default_factory=list,
        description="List UUID hub_id user có quyền truy cập (USER-03 multi-hub).",
    )


class LoginResponse(BaseModel):
    """Login success — data field trong envelope `{success, data, error, meta}`."""

    access_token: str
    refresh_token: str
    expires_at: int  # Unix timestamp access token expires (frontend show countdown)
    user: UserPublic


class RefreshRequest(BaseModel):
    """POST /api/auth/refresh request body."""

    refresh_token: str = Field(min_length=1)


class LogoutRequest(BaseModel):
    """POST /api/auth/logout — refresh_token optional (mục đích blacklist cả pair)."""

    refresh_token: str | None = None
