"""Audit query service — Plan 05-05 (AUX-01 GET /api/audit-logs query).

Read-only SELECT trên bảng `audit_logs` (append-only — KHÔNG mutation ở đây;
INSERT qua `audit_service.audit_flush_loop`).

Pattern WHERE-clause builder + LEFT JOIN (Phase 4 `DocumentService.list`):
- Raw SQL `text()` + named bind params (T-05-05-05 SQL injection mitigation).
- LEFT JOIN `users` lấy `user_name` (full_name), LEFT JOIN `hubs` lấy `hub_name`.

LƯU Ý: param `actor_type` (api.ts) — bảng `audit_logs` M2 KHÔNG có cột `actor_type`
→ filter này bị bỏ qua (documented; router vẫn nhận param để giữ contract).
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.audit import AuditLogResponse

logger = logging.getLogger(__name__)


class AuditQueryService:
    """Audit log query — read-only filter + pagination (AUX-01)."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list(
        self,
        *,
        date_from: str | None,
        date_to: str | None,
        action: str | None,
        hub_id: str | None,
        page: int,
        per_page: int,
    ) -> tuple[list[AuditLogResponse], int]:
        """List audit log với filter + pagination. Returns (items, total).

        Filter: created_at >= date_from, created_at <= date_to, action, hub_id.
        Router cap per_page ≤ 100 — service KHÔNG cap.
        """
        # Build WHERE clauses + bind params (asyncpg parametrize an toàn).
        where_clauses: list[str] = []
        params: dict[str, Any] = {}
        if date_from:
            where_clauses.append("al.created_at >= :date_from")
            params["date_from"] = date_from
        if date_to:
            where_clauses.append("al.created_at <= :date_to")
            params["date_to"] = date_to
        if action:
            where_clauses.append("al.action = :action")
            params["action"] = action
        if hub_id:
            where_clauses.append("al.hub_id = :hub_id")
            params["hub_id"] = hub_id

        where_sql = (
            ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
        )

        # Count tổng số rows match.
        total_row = (
            await self.db.execute(
                text(f"SELECT COUNT(*) FROM audit_logs al {where_sql}"),
                params,
            )
        ).fetchone()
        total = int(total_row[0]) if total_row else 0

        # Page rows — LEFT JOIN users + hubs lấy tên hiển thị.
        offset = max(0, (page - 1) * per_page)
        params_with_pg = {**params, "limit": per_page, "offset": offset}
        rows = (
            await self.db.execute(
                text(
                    "SELECT al.id, al.created_at, al.user_id, u.full_name, "
                    "al.action, al.target_id, al.hub_id, h.name, "
                    "al.request_id, al.payload "
                    "FROM audit_logs al "
                    "LEFT JOIN users u ON al.user_id = u.id "
                    "LEFT JOIN hubs h ON al.hub_id = h.id "
                    f"{where_sql} "
                    "ORDER BY al.created_at DESC LIMIT :limit OFFSET :offset"
                ),
                params_with_pg,
            )
        ).fetchall()
        items = [
            AuditLogResponse(
                id=str(r[0]),
                timestamp=r[1],
                user_id=str(r[2]) if r[2] is not None else None,
                user_name=r[3],
                is_ai=False,
                action=r[4],
                target=r[5],
                hub_id=str(r[6]) if r[6] is not None else None,
                hub_name=r[7],
                ip_address=None,
                user_agent=None,
                request_id=r[8],
                duration_ms=None,
                payload=r[9],
            )
            for r in rows
        ]
        return items, total
