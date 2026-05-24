"""Role resolution helper — Phase 1 Plan 01-02 (ROLE-04).

Module mới tách khỏi `dependencies.py` (separation of concerns):
- `dependencies.py`: FastAPI dependency wrappers (Depends-injected).
- `role.py`: business logic role resolution thuần (KHÔNG FastAPI dep).

Phase 2 sẽ import `from app.auth.role import get_effective_role` để build
dependency `require_hub_admin_for(hub_id)` (DEP-01).

Logic ROLE-04 (D-V3.1-02 LOCKED):
1. SELECT user_hubs.role WHERE user=$1 AND hub=$2 → non-NULL → return (override).
2. user_hubs row tồn tại + role=NULL → return users.role (inherit global).
3. KHÔNG có user_hubs row → return users.role (fallback no-membership).
4. KHÔNG có users row → raise UserNotFoundError (defensive — caller handle).

Mitigations:
- T-01-02-01 SQL injection — raw SQL via sqlalchemy.text() + named bind params
  `:user_id`, `:hub_id` (CLAUDE.md stack pin convention).
- T-01-02-02 Type coercion — user_id + hub_id chấp nhận UUID hoặc str, convert
  về str(uuid) trước khi bind (asyncpg auto-cast text→uuid trong Postgres).
- T-01-02-03 Race condition — async function single-shot read, KHÔNG transaction
  scope (caller chịu trách nhiệm session lifecycle); idempotent read-only.
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class UserNotFoundError(Exception):
    """User_id không tồn tại trong table users — defensive exception.

    Caller (Phase 2 dependency) phải handle riêng — KHÔNG silent return string
    rỗng / role mặc định (tránh privilege escalation case stale user_id token).
    """


async def get_effective_role(
    session: AsyncSession,
    user_id: UUID | str,
    hub_id: UUID | str,
) -> str:
    """Trả về effective role của user trong hub cụ thể (per-hub override aware).

    Logic ROLE-04 (D-V3.1-02 LOCKED — D-V3.1-02 "user_hubs.role nullable;
    NULL = inherit users.role global"):

    1. SELECT user_hubs.role WHERE user_id=:uid AND hub_id=:hid
       - Row tồn tại + role IS NOT NULL → return user_hubs.role (per-hub override).
       - Row tồn tại + role IS NULL → fallthrough STEP 2.
       - Row KHÔNG tồn tại → fallthrough STEP 2 (no-membership fallback global).
    2. SELECT users.role WHERE id=:uid
       - Row tồn tại → return users.role (inherit global).
       - Row KHÔNG tồn tại → raise UserNotFoundError.

    Args:
        session: AsyncSession đang mở (caller manage lifecycle).
        user_id: UUID hoặc str — converted về str(uuid) trước bind.
        hub_id: UUID hoặc str — converted về str(uuid) trước bind.

    Returns:
        Role string: 'admin' | 'hub_admin' | 'editor' | 'viewer' (theo CHECK
        constraint Plan 01-01 migration 0006).

    Raises:
        UserNotFoundError: Nếu user_id không tồn tại trong table users.

    Example:
        >>> # super admin (users.role='admin', user_hubs.role=NULL)
        >>> role = await get_effective_role(db, super_admin_id, dmd_hub_id)
        >>> assert role == 'admin'

        >>> # hub_admin per-hub (users.role='editor', user_hubs.role='hub_admin')
        >>> role = await get_effective_role(db, hub_admin_user_id, dmd_hub_id)
        >>> assert role == 'hub_admin'

        >>> # viewer per-hub (users.role='admin', user_hubs.role='viewer')
        >>> role = await get_effective_role(db, demoted_admin_id, dmd_hub_id)
        >>> assert role == 'viewer'

        >>> # no membership fallback (users.role='admin', không có user_hubs row)
        >>> role = await get_effective_role(db, super_admin_id, unassigned_hub_id)
        >>> assert role == 'admin'  # fallback global
    """
    user_id_str = str(user_id)
    hub_id_str = str(hub_id)

    # STEP 1 — Check user_hubs.role override.
    result = await session.execute(
        text(
            "SELECT role FROM user_hubs "
            "WHERE user_id = :user_id AND hub_id = :hub_id"
        ),
        {"user_id": user_id_str, "hub_id": hub_id_str},
    )
    row = result.fetchone()
    if row is not None and row[0] is not None:
        # Per-hub override → return ngay (KHÔNG cần check users.role).
        return str(row[0])

    # STEP 2 — Inherit global (row IS NULL hoặc row KHÔNG tồn tại).
    result = await session.execute(
        text("SELECT role FROM users WHERE id = :user_id"),
        {"user_id": user_id_str},
    )
    user_row = result.fetchone()
    if user_row is None:
        raise UserNotFoundError(
            f"User {user_id_str!r} không tồn tại trong table users — "
            f"defensive guard (caller phải handle stale user_id token)"
        )
    return str(user_row[0])
