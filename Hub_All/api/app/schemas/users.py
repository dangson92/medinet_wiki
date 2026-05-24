"""User + Profile schemas — Pydantic v2 (Plan 05-04, USER-01/02/03).

Contract endpoint + field name lấy từ `frontend/src/services/api.ts` (D-07 —
frontend thắng REQUIREMENTS.md khi mâu thuẫn verb/path/field).

Lưu ý mapping:
- `UserResponse` field `name` map từ cột DB `users.full_name`.
- `failed_login_count` KHÔNG có cột DB — trả hằng `0` (M2 chưa track; defer).
- `password_hash` KHÔNG bao giờ xuất hiện trong response schema
  (T-05-04-03 Information Disclosure mitigation).
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field

# Role enum — 4 value match Plan 01-01 migration 0006 CHECK constraint (D-V3.1-01 LOCKED).
# Phase 2 Plan 02-03 DEP-03 — extend 'hub_admin' match migration 0006 CHECK constraint
# 4 value (admin|hub_admin|editor|viewer); body validation cho PATCH role escalation.
UserRole = Literal["admin", "hub_admin", "editor", "viewer"]
# Status enum — match users.status CHECK constraint `user_status_enum`.
UserStatus = Literal["active", "disabled"]


class CreateUserRequest(BaseModel):
    """POST /api/users body — admin tạo user mới.

    `password` plaintext trong body — service hash NGAY qua argon2
    (T-05-04 trust boundary; KHÔNG lưu/log plaintext).
    """

    email: EmailStr
    name: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=8, max_length=128)
    phone: str | None = None
    department: str | None = None
    hub_id: str
    role: UserRole


class UpdateUserRequest(BaseModel):
    """PUT /api/users/:id body — admin cập nhật profile fields.

    D-07: tách khỏi role/status — chỉ name/phone/department.
    """

    name: str | None = Field(default=None, max_length=200)
    phone: str | None = None
    department: str | None = None


class ChangeUserRoleRequest(BaseModel):
    """PATCH /api/users/:id/role body — D-07 endpoint riêng."""

    hub_id: str
    role: UserRole


class ChangeUserStatusRequest(BaseModel):
    """PATCH /api/users/:id/status body — D-07 endpoint riêng."""

    status: UserStatus


class UpdateProfileRequest(BaseModel):
    """PUT /api/profile body — user tự cập nhật profile (self-scoped)."""

    name: str | None = Field(default=None, max_length=200)
    phone: str | None = None
    department: str | None = None


class ChangePasswordRequest(BaseModel):
    """POST /api/profile/password body — user tự đổi mật khẩu.

    `old_password` verify qua argon2 trước khi đổi (T-05-04-05 Spoofing).
    """

    old_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8, max_length=128)


class UserResponse(BaseModel):
    """User payload — UserAPI contract frontend (api.ts ~373).

    `name` map từ cột `full_name`. `failed_login_count` hằng 0 (M2 defer).
    KHÔNG có field `password_hash` (T-05-04-03 Information Disclosure).
    """

    id: str  # UUID string
    email: str
    name: str
    phone: str | None
    department: str | None
    avatar_url: str | None
    status: UserStatus
    failed_login_count: int = 0
    created_at: datetime
    updated_at: datetime | None


class RoleAssignment(BaseModel):
    """1 hub-role assignment — RoleAPI contract frontend (api.ts ~386)."""

    user_id: str
    hub_id: str
    role: str


class UserWithRolesResponse(BaseModel):
    """User + danh sách hub-role — UserWithRolesAPI contract frontend.

    `roles` build từ join table `user_hubs` (mỗi row → 1 RoleAssignment).
    """

    user: UserResponse
    roles: list[RoleAssignment]
