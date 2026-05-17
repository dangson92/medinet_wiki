"""Hub service — Plan 05-03 (HUB-01 hub registry CRUD + HUB-03 stats).

Layer giữa router và DB. Pattern service-chứa-SQL (Phase 4 `DocumentService`):
- Raw SQL qua `sqlalchemy.text()` + named bind params (asyncpg parametrize —
  KHÔNG f-string nội suy giá trị; T-05-03-02 SQL injection mitigation).
- Timestamps SQL `NOW()` server-side — KHÔNG `datetime.utcnow()` (BLOCKER #4).
- `get_session()` auto-commit khi handler không raise — service KHÔNG tự commit.
- Mutation (create/update) enqueue audit non-blocking qua `audit_service`
  (T-05-03-05 Repudiation mitigation).

W1 (Plan 05-01): bảng `hubs` có cả `slug` (Phase 2 NOT NULL unique mirror) +
`code` (contract frontend). `create()` set `slug = code.lower()`.
"""
from __future__ import annotations

import logging
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.hubs import (
    CreateHubRequest,
    HubResponse,
    HubStats,
    UpdateHubRequest,
)
from app.services.audit_service import AuditEntry, enqueue_audit

logger = logging.getLogger(__name__)


class HubConflictError(Exception):
    """Hub code/slug trùng — unique constraint vi phạm (T-05-03-04).

    Router catch → resp.conflict 409 HUB_CODE_CONFLICT.
    """


# Cột SELECT chuẩn cho HubResponse — dùng lại ở get/update/list.
_HUB_SELECT_COLS = (
    "id, name, code, subdomain, description, status, created_at, updated_at"
)


def _row_to_response(row: object) -> HubResponse:
    """Map 1 row tuple (theo _HUB_SELECT_COLS) → HubResponse."""
    r = row  # row là Row tuple — index theo thứ tự _HUB_SELECT_COLS
    return HubResponse(
        id=str(r[0]),  # type: ignore[index]
        name=r[1],  # type: ignore[index]
        code=r[2],  # type: ignore[index]
        subdomain=r[3],  # type: ignore[index]
        description=r[4],  # type: ignore[index]
        status=r[5],  # type: ignore[index]
        created_at=r[6],  # type: ignore[index]
        updated_at=r[7],  # type: ignore[index]
    )


class HubService:
    """Hub registry CRUD + stats — HUB-01, HUB-03."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(
        self,
        *,
        req: CreateHubRequest,
        created_by: UUID,
        request_id: str | None = None,
    ) -> HubResponse:
        """INSERT hub mới → HubResponse.

        W1: set `slug = code.lower()` (cột Phase 2 NOT NULL unique).
        Timestamps SQL NOW() server-side.

        Raises:
            HubConflictError: code/slug trùng (unique constraint).
        """
        hub_id = uuid4()
        slug = req.code.lower()
        try:
            row = (
                await self.db.execute(
                    text(
                        "INSERT INTO hubs "
                        "(id, slug, name, code, subdomain, description, status, "
                        "is_active, created_at, updated_at) "
                        "VALUES (:id, :slug, :name, :code, :subdomain, :desc, "
                        "'active', TRUE, NOW(), NOW()) "
                        f"RETURNING {_HUB_SELECT_COLS}"
                    ),
                    {
                        "id": str(hub_id),
                        "slug": slug,
                        "name": req.name,
                        "code": req.code,
                        "subdomain": req.subdomain,
                        "desc": req.description,
                    },
                )
            ).fetchone()
        except IntegrityError as e:
            # unique constraint code/slug vi phạm (T-05-03-04).
            raise HubConflictError(
                f"Hub với code {req.code!r} đã tồn tại"
            ) from e

        # Sau INSERT thành công — enqueue audit non-blocking (T-05-03-05).
        enqueue_audit(
            AuditEntry(
                action="hub.create",
                user_id=str(created_by),
                target_type="hub",
                target_id=str(hub_id),
                hub_id=str(hub_id),
                payload={"code": req.code, "name": req.name},
                request_id=request_id,
            )
        )
        logger.info(
            "hub_created: id=%s code=%s by=%s", hub_id, req.code, created_by
        )
        # row luôn non-None sau INSERT ... RETURNING thành công.
        assert row is not None  # noqa: S101 — invariant INSERT RETURNING
        return _row_to_response(row)

    async def get(self, hub_id: UUID) -> HubResponse | None:
        """SELECT 1 hub qua id. None nếu không tồn tại."""
        row = (
            await self.db.execute(
                text(f"SELECT {_HUB_SELECT_COLS} FROM hubs WHERE id = :id"),
                {"id": str(hub_id)},
            )
        ).fetchone()
        if row is None:
            return None
        return _row_to_response(row)

    async def list(
        self,
        *,
        page: int,
        per_page: int,
    ) -> tuple[list[HubResponse], int]:
        """List hub phân trang. Returns (items, total).

        Router cap per_page ≤ 100 — service KHÔNG cap.
        """
        total_row = (
            await self.db.execute(text("SELECT COUNT(*) FROM hubs"))
        ).fetchone()
        total = int(total_row[0]) if total_row else 0

        offset = max(0, (page - 1) * per_page)
        rows = (
            await self.db.execute(
                text(
                    f"SELECT {_HUB_SELECT_COLS} FROM hubs "
                    "ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
                ),
                {"limit": per_page, "offset": offset},
            )
        ).fetchall()
        items = [_row_to_response(r) for r in rows]
        return items, total

    async def update(
        self,
        *,
        hub_id: UUID,
        req: UpdateHubRequest,
        updated_by: UUID,
        request_id: str | None = None,
    ) -> HubResponse | None:
        """UPDATE hub (PUT — D-07). None nếu hub không tồn tại.

        Build SET clause động chỉ cho field không None (name/description);
        cả 2 None → chỉ refresh updated_at.
        """
        set_parts: list[str] = []
        params: dict[str, object] = {"id": str(hub_id)}
        if req.name is not None:
            set_parts.append("name = :name")
            params["name"] = req.name
        if req.description is not None:
            set_parts.append("description = :desc")
            params["desc"] = req.description
        set_parts.append("updated_at = NOW()")
        set_sql = ", ".join(set_parts)

        row = (
            await self.db.execute(
                text(
                    f"UPDATE hubs SET {set_sql} WHERE id = :id "
                    f"RETURNING {_HUB_SELECT_COLS}"
                ),
                params,
            )
        ).fetchone()
        if row is None:
            return None

        enqueue_audit(
            AuditEntry(
                action="hub.update",
                user_id=str(updated_by),
                target_type="hub",
                target_id=str(hub_id),
                hub_id=str(hub_id),
                payload={"changed": req.model_dump(exclude_none=True)},
                request_id=request_id,
            )
        )
        logger.info("hub_updated: id=%s by=%s", hub_id, updated_by)
        return _row_to_response(row)

    async def update_status(
        self,
        *,
        hub_id: UUID,
        status: str,
        updated_by: UUID,
        request_id: str | None = None,
    ) -> bool:
        """PATCH status hub. Returns True nếu update 1 row, False nếu không.

        Dùng `RETURNING id` thay `.rowcount` — phát hiện row tồn tại qua
        fetchone() (SQLAlchemy `Result` type stub không expose `rowcount`).
        """
        row = (
            await self.db.execute(
                text(
                    "UPDATE hubs SET status = :status, updated_at = NOW() "
                    "WHERE id = :id RETURNING id"
                ),
                {"status": status, "id": str(hub_id)},
            )
        ).fetchone()
        if row is None:
            return False

        enqueue_audit(
            AuditEntry(
                action="hub.update",
                user_id=str(updated_by),
                target_type="hub",
                target_id=str(hub_id),
                hub_id=str(hub_id),
                payload={"status": status},
                request_id=request_id,
            )
        )
        logger.info(
            "hub_status_updated: id=%s status=%s by=%s",
            hub_id,
            status,
            updated_by,
        )
        return True

    async def stats(self, hub_id: UUID) -> HubStats | None:
        """HUB-03 — counts từ Postgres aggregate. None nếu hub không tồn tại.

        3 count: document_count / chunk_count / user_count. `query_count`
        defer Phase 6/7 (chưa có nguồn data — ghi rõ trong plan objective).
        """
        # Verify hub tồn tại trước khi aggregate.
        exists = (
            await self.db.execute(
                text("SELECT 1 FROM hubs WHERE id = :id"),
                {"id": str(hub_id)},
            )
        ).fetchone()
        if exists is None:
            return None

        row = (
            await self.db.execute(
                text(
                    "SELECT "
                    "(SELECT COUNT(*) FROM documents WHERE hub_id = :hub_id) "
                    "AS document_count, "
                    "(SELECT COUNT(*) FROM chunks WHERE hub_id = :hub_id) "
                    "AS chunk_count, "
                    "(SELECT COUNT(*) FROM user_hubs WHERE hub_id = :hub_id) "
                    "AS user_count"
                ),
                {"hub_id": str(hub_id)},
            )
        ).fetchone()
        assert row is not None  # noqa: S101 — aggregate luôn trả 1 row
        return HubStats(
            hub_id=str(hub_id),
            document_count=int(row[0]),
            chunk_count=int(row[1]),
            user_count=int(row[2]),
        )
