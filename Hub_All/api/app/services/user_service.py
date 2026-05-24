"""User service — Plan 05-04 (USER-01 user CRUD + USER-02 reset-password +
USER-03 profile self-scoped).

Layer giữa router và DB. Pattern service-chứa-SQL (Phase 4 `DocumentService` +
Plan 05-03 `HubService`):
- Raw SQL qua `sqlalchemy.text()` + named bind params (asyncpg parametrize —
  KHÔNG f-string nội suy giá trị; T-05-04-06 SQL injection mitigation).
- Timestamps SQL `NOW()` server-side — KHÔNG `datetime.utcnow()` (BLOCKER #4).
- `get_session()` auto-commit khi handler không raise — service KHÔNG tự commit.
- Mutation `create` enqueue audit non-blocking qua `audit_service`.

Bảo mật:
- `password` plaintext hash NGAY qua `hash_password` (argon2) — KHÔNG lưu/log
  plaintext (T-05-04 trust boundary).
- `reset_password` sinh token, lưu Redis TTL 1h, CHỈ log console (USER-02 M2 —
  email defer v4.0; T-05-04-04 — token KHÔNG trả qua API).
- `change_password_self` verify `old_password` trước khi đổi (T-05-04-05).
"""
from __future__ import annotations

import logging
import secrets
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import hash_password
from app.auth.password import verify_password
from app.schemas.users import (
    CreateUserRequest,
    RoleAssignment,
    UpdateProfileRequest,
    UpdateUserRequest,
    UserResponse,
    UserWithRolesResponse,
)
from app.services.audit_service import (
    AuditEntry,
    build_audit_payload,  # Phase 2 Plan 02-04 DEP-05 — D-V3.1-Phase2-C LOCKED.
    enqueue_audit,
)

logger = logging.getLogger(__name__)


class UserConflictError(Exception):
    """Email trùng — unique constraint `users.email` vi phạm (T-05-04-07).

    Router catch → resp.conflict 409 EMAIL_CONFLICT.
    """


class LastAdminError(Exception):
    """Xoá admin cuối cùng → 409 LAST_ADMIN.

    System phải còn ≥ 1 admin để vận hành (CRUD hubs/users/api_keys). Nếu admin
    cuối cùng bị xoá, KHÔNG ai có thể đăng nhập tạo admin mới qua UI → khoá cứng
    cần psql tay. Block ở service layer.
    """


# Cột SELECT chuẩn cho UserResponse — dùng lại ở _build_user_with_roles.
# Lưu ý: cột DB `full_name` map sang field schema `name`.
_USER_SELECT_COLS = (
    "id, email, full_name, phone, department, avatar_url, status, "
    "created_at, updated_at"
)


class UserService:
    """User CRUD + hub_assignments join + reset token + self password change."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def _build_user_with_roles(
        self, user_id: UUID
    ) -> UserWithRolesResponse | None:
        """SELECT user row + user_hubs → UserWithRolesResponse.

        `roles` build từ join table `user_hubs` — mỗi row → RoleAssignment với
        role = `users.role` (M2: 1 role mặc định áp cho mọi hub assignment).
        None nếu user không tồn tại.
        """
        row = (
            await self.db.execute(
                text(
                    f"SELECT {_USER_SELECT_COLS}, role FROM users "
                    "WHERE id = :id"
                ),
                {"id": str(user_id)},
            )
        ).fetchone()
        if row is None:
            return None

        user = UserResponse(
            id=str(row[0]),
            email=row[1],
            name=row[2] or "",
            phone=row[3],
            department=row[4],
            avatar_url=row[5],
            status=row[6],
            failed_login_count=0,
            created_at=row[7],
            updated_at=row[8],
        )
        default_role = str(row[9])

        hub_rows = (
            await self.db.execute(
                text(
                    "SELECT hub_id FROM user_hubs WHERE user_id = :uid "
                    "ORDER BY assigned_at"
                ),
                {"uid": str(user_id)},
            )
        ).fetchall()
        roles = [
            RoleAssignment(
                user_id=str(user_id),
                hub_id=str(hr[0]),
                role=default_role,
            )
            for hr in hub_rows
        ]
        return UserWithRolesResponse(user=user, roles=roles)

    async def create(
        self,
        *,
        req: CreateUserRequest,
        created_by: UUID,
        actor_role: str,  # Phase 2 Plan 02-04 DEP-05 — required kwarg, router derive.
        actor_hub_id: str | None,  # Phase 2 Plan 02-04 DEP-05.
        request_id: str | None = None,
    ) -> UserWithRolesResponse:
        """INSERT user mới + INSERT user_hubs assignment → UserWithRolesResponse.

        `password` hash NGAY qua argon2 — KHÔNG lưu plaintext. Timestamps
        SQL NOW() server-side.

        Phase 2 Plan 02-04 DEP-05 — `actor_role` + `actor_hub_id` nest vào
        audit payload qua `build_audit_payload` (D-V3.1-Phase2-C LOCKED, KHÔNG
        schema migration audit_logs). Router caller derive đúng từ
        `user.role` + `req.hub_id`.

        Raises:
            UserConflictError: email trùng (unique constraint `users.email`).
        """
        user_id = uuid4()
        password_hash = hash_password(req.password)
        try:
            await self.db.execute(
                text(
                    "INSERT INTO users "
                    "(id, email, password_hash, full_name, role, phone, "
                    "department, status, is_active, created_at, updated_at) "
                    "VALUES (:id, :email, :hash, :name, :role, :phone, "
                    ":dept, 'active', TRUE, NOW(), NOW())"
                ),
                {
                    "id": str(user_id),
                    "email": req.email,
                    "hash": password_hash,
                    "name": req.name,
                    "role": req.role,
                    "phone": req.phone,
                    "dept": req.department,
                },
            )
        except IntegrityError as e:
            # unique constraint `users.email` vi phạm (T-05-04-07).
            raise UserConflictError(
                f"User với email {req.email!r} đã tồn tại"
            ) from e

        # INSERT hub assignment vào join table user_hubs.
        await self.db.execute(
            text(
                "INSERT INTO user_hubs (user_id, hub_id, assigned_at) "
                "VALUES (:uid, :hid, NOW())"
            ),
            {"uid": str(user_id), "hid": req.hub_id},
        )

        # Audit non-blocking — payload CHỈ email+role (KHÔNG password —
        # T-05-04-03 Information Disclosure mitigation).
        # Phase 2 Plan 02-04 DEP-05 — nest actor_role + actor_hub_id qua
        # build_audit_payload (D-V3.1-Phase2-C LOCKED).
        enqueue_audit(
            AuditEntry(
                action="user.create",
                user_id=str(created_by),
                target_type="user",
                target_id=str(user_id),
                hub_id=req.hub_id,
                payload=build_audit_payload(
                    actor_role=actor_role,
                    actor_hub_id=actor_hub_id,
                    extra={"email": req.email, "role": req.role},
                ),
                request_id=request_id,
            )
        )
        logger.info(
            "user_created: id=%s email=%s by=%s",
            user_id,
            req.email,
            created_by,
        )
        result = await self._build_user_with_roles(user_id)
        # result luôn non-None ngay sau INSERT thành công.
        assert result is not None  # noqa: S101 — invariant post-INSERT
        return result

    async def get(self, user_id: UUID) -> UserWithRolesResponse | None:
        """SELECT 1 user + roles qua id. None nếu không tồn tại."""
        return await self._build_user_with_roles(user_id)

    async def list(
        self,
        *,
        hub_id: str | None,
        role: str | None,
        status: str | None,
        search: str | None,
        page: int,
        per_page: int,
    ) -> tuple[list[UserWithRolesResponse], int]:
        """List user với filter + pagination. Returns (items, total).

        Filter: role / status exact; search ILIKE trên email + full_name;
        hub_id qua subquery vào user_hubs. Router cap per_page ≤ 100.
        """
        where_clauses: list[str] = []
        params: dict[str, Any] = {}
        if role is not None:
            where_clauses.append("role = :role")
            params["role"] = role
        if status is not None:
            where_clauses.append("status = :status")
            params["status"] = status
        if search:
            where_clauses.append(
                "(email ILIKE :search OR full_name ILIKE :search)"
            )
            params["search"] = f"%{search}%"
        if hub_id is not None:
            where_clauses.append(
                "id IN (SELECT user_id FROM user_hubs WHERE hub_id = :hub_id)"
            )
            params["hub_id"] = hub_id

        where_sql = (
            ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
        )

        total_row = (
            await self.db.execute(
                text(f"SELECT COUNT(*) FROM users {where_sql}"),
                params,
            )
        ).fetchone()
        total = int(total_row[0]) if total_row else 0

        offset = max(0, (page - 1) * per_page)
        params_with_pg = {**params, "limit": per_page, "offset": offset}
        rows = (
            await self.db.execute(
                text(
                    f"SELECT id FROM users {where_sql} "
                    "ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
                ),
                params_with_pg,
            )
        ).fetchall()

        items: list[UserWithRolesResponse] = []
        for r in rows:
            built = await self._build_user_with_roles(UUID(str(r[0])))
            if built is not None:
                items.append(built)
        return items, total

    async def _update_fields(
        self,
        *,
        user_id: UUID,
        name: str | None,
        phone: str | None,
        department: str | None,
    ) -> UserWithRolesResponse | None:
        """UPDATE profile fields động (name→full_name, phone, department).

        Chỉ SET field không None; luôn refresh updated_at. None nếu user
        không tồn tại. Dùng chung cho `update` (admin) + `update_profile` (self).
        """
        set_parts: list[str] = []
        params: dict[str, object] = {"id": str(user_id)}
        if name is not None:
            set_parts.append("full_name = :name")
            params["name"] = name
        if phone is not None:
            set_parts.append("phone = :phone")
            params["phone"] = phone
        if department is not None:
            set_parts.append("department = :dept")
            params["dept"] = department
        set_parts.append("updated_at = NOW()")
        set_sql = ", ".join(set_parts)

        row = (
            await self.db.execute(
                text(
                    f"UPDATE users SET {set_sql} WHERE id = :id RETURNING id"
                ),
                params,
            )
        ).fetchone()
        if row is None:
            return None
        return await self._build_user_with_roles(user_id)

    async def update(
        self,
        *,
        user_id: UUID,
        req: UpdateUserRequest,
    ) -> UserWithRolesResponse | None:
        """UPDATE profile fields user (PUT — D-07). None nếu không tồn tại."""
        return await self._update_fields(
            user_id=user_id,
            name=req.name,
            phone=req.phone,
            department=req.department,
        )

    async def update_profile(
        self,
        *,
        user_id: UUID,
        req: UpdateProfileRequest,
    ) -> UserWithRolesResponse | None:
        """UPDATE profile self-scoped (PUT /api/profile). None nếu không tồn tại."""
        return await self._update_fields(
            user_id=user_id,
            name=req.name,
            phone=req.phone,
            department=req.department,
        )

    async def change_role(
        self,
        *,
        user_id: UUID,
        hub_id: str,
        role: str,
    ) -> bool:
        """PATCH role user (D-07). UPDATE users.role + upsert user_hubs.

        Returns True nếu user tồn tại (UPDATE 1 row), False nếu không.
        """
        row = (
            await self.db.execute(
                text(
                    "UPDATE users SET role = :role, updated_at = NOW() "
                    "WHERE id = :id RETURNING id"
                ),
                {"role": role, "id": str(user_id)},
            )
        ).fetchone()
        if row is None:
            return False

        # Upsert hub assignment — đảm bảo user gắn hub_id chỉ định.
        await self.db.execute(
            text(
                "INSERT INTO user_hubs (user_id, hub_id, assigned_at) "
                "VALUES (:uid, :hid, NOW()) "
                "ON CONFLICT (user_id, hub_id) DO NOTHING"
            ),
            {"uid": str(user_id), "hid": hub_id},
        )
        logger.info(
            "user_role_changed: id=%s role=%s hub=%s",
            user_id,
            role,
            hub_id,
        )
        return True

    async def change_status(
        self,
        *,
        user_id: UUID,
        status: str,
    ) -> bool:
        """PATCH status user (D-07). UPDATE users.status + is_active.

        Returns True nếu user tồn tại (UPDATE 1 row), False nếu không.
        """
        row = (
            await self.db.execute(
                text(
                    "UPDATE users SET status = :status, is_active = :active, "
                    "updated_at = NOW() WHERE id = :id RETURNING id"
                ),
                {
                    "status": status,
                    "active": status == "active",
                    "id": str(user_id),
                },
            )
        ).fetchone()
        if row is None:
            return False
        logger.info("user_status_changed: id=%s status=%s", user_id, status)
        return True

    async def delete(
        self,
        *,
        user_id: UUID,
        deleted_by: UUID,
        actor_role: str,  # Phase 2 Plan 02-04 DEP-05 — required kwarg.
        actor_hub_id: str | None,  # Phase 2 Plan 02-04 DEP-05.
        request_id: str | None = None,
    ) -> bool:
        """Hard DELETE user (USER-04 admin-only). Returns False nếu không tồn tại.

        Phase 2 Plan 02-04 DEP-05 — `actor_role` + `actor_hub_id` nest vào
        audit payload (D-V3.1-Phase2-C LOCKED). Router derive từ
        `user.role` + (target_hub_ids[0] khi hub_admin single-hub case B1
        iter 1; None khi super admin).

        Schema FK đã thiết kế cho hard delete safe (migration 0001):
        - refresh_tokens.user_id ON DELETE CASCADE → force logout ngay
        - user_hubs.user_id ON DELETE CASCADE → gỡ tất cả hub assignment
        - mcp_oauth_clients.user_id ON DELETE CASCADE (migration 0004)
        - audit_logs.user_id ON DELETE SET NULL → giữ trail, anonymize actor
        - documents.uploaded_by ON DELETE SET NULL → giữ document, anonymize owner
        - usage_events / api_keys / settings → ON DELETE SET NULL

        Pre-conditions check ở caller (router) — service KHÔNG check self vì
        không có context request user; check last-admin TRƯỚC DELETE ở đây.

        Raises:
            LastAdminError: user là admin và là admin cuối cùng — block.
        """
        row = (
            await self.db.execute(
                text(
                    "SELECT email, role FROM users WHERE id = :id"
                ),
                {"id": str(user_id)},
            )
        ).fetchone()
        if row is None:
            return False
        email_to_delete = str(row[0])
        role_to_delete = str(row[1])

        if role_to_delete == "admin":
            admin_count_row = (
                await self.db.execute(
                    text(
                        "SELECT COUNT(*) FROM users WHERE role = 'admin' "
                        "AND status = 'active' AND id != :id"
                    ),
                    {"id": str(user_id)},
                )
            ).fetchone()
            remaining_admins = int(admin_count_row[0]) if admin_count_row else 0
            if remaining_admins == 0:
                raise LastAdminError(
                    f"Không thể xoá admin cuối cùng ({email_to_delete}). "
                    "Hãy tạo admin khác trước."
                )

        # Audit log TRƯỚC khi DELETE — ON DELETE SET NULL sẽ NULL hoá user_id của
        # row audit này luôn (deleted_by = chính user vừa xoá thì cũng vẫn được
        # ghi từ deleted_by != user_id trường hợp khác). Payload giữ email +
        # role để forensic (KHÔNG password — T-05-04-03).
        # Phase 2 Plan 02-04 DEP-05 — nest actor_role + actor_hub_id qua
        # build_audit_payload (D-V3.1-Phase2-C LOCKED).
        enqueue_audit(
            AuditEntry(
                action="user.delete",
                user_id=str(deleted_by),
                target_type="user",
                target_id=str(user_id),
                hub_id=None,
                payload=build_audit_payload(
                    actor_role=actor_role,
                    actor_hub_id=actor_hub_id,
                    extra={
                        "deleted_email": email_to_delete,
                        "deleted_role": role_to_delete,
                    },
                ),
                request_id=request_id,
            )
        )

        await self.db.execute(
            text("DELETE FROM users WHERE id = :id"),
            {"id": str(user_id)},
        )
        logger.info(
            "user_deleted: id=%s email=%s by=%s",
            user_id,
            email_to_delete,
            deleted_by,
        )
        return True

    async def reset_password(
        self,
        *,
        user_id: UUID,
        redis: Any,
    ) -> str | None:
        """USER-02 — sinh reset token TTL 1h. None nếu user không tồn tại.

        Token lưu Redis `reset:{token}` ex=3600. CHỈ log console (M2 —
        email defer v4.0). Token KHÔNG trả qua API response (T-05-04-04).
        """
        exists = (
            await self.db.execute(
                text("SELECT 1 FROM users WHERE id = :id"),
                {"id": str(user_id)},
            )
        ).fetchone()
        if exists is None:
            return None

        token = secrets.token_urlsafe(32)
        if redis is not None:
            await redis.set(f"reset:{token}", str(user_id), ex=3600)
        logger.info(
            "user_reset_password_token: user_id=%s token=%s "
            "(M2 log-only, email defer v4.0)",
            user_id,
            token,
        )
        return token

    async def change_password_self(
        self,
        *,
        user_id: UUID,
        old_password: str,
        new_password: str,
    ) -> bool | None:
        """USER-03 — đổi mật khẩu self-scoped.

        Returns:
            None  — user không tồn tại.
            False — old_password sai (T-05-04-05 Spoofing — verify trước).
            True  — đổi thành công.
        """
        row = (
            await self.db.execute(
                text("SELECT password_hash FROM users WHERE id = :id"),
                {"id": str(user_id)},
            )
        ).fetchone()
        if row is None:
            return None

        if not verify_password(old_password, str(row[0])):
            return False

        await self.db.execute(
            text(
                "UPDATE users SET password_hash = :hash, updated_at = NOW() "
                "WHERE id = :id"
            ),
            {"hash": hash_password(new_password), "id": str(user_id)},
        )
        logger.info("user_password_changed_self: user_id=%s", user_id)
        return True
