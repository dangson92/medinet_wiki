"""CRUD service cho bảng guides — public hướng dẫn sử dụng Medinet Wiki.

Raw SQL via SQLAlchemy text() + named bind params (carry forward Plan 01-02
v3.1 `auth/role.py` pattern — KHÔNG import ORM model tránh cycle, schema
chỉ 7 cột đơn giản KHÔNG cần full mapper).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class GuideNotFoundError(Exception):
    """Raise khi guide_id không tồn tại."""


def _serialize(row: dict[str, Any]) -> dict[str, Any]:
    """Convert UUID → str, datetime → ISO string cho json.dumps default encoder.

    Starlette JSONResponse dùng `json.dumps` chuẩn KHÔNG hỗ trợ UUID/datetime
    natively; service trả raw dict từ SQLAlchemy mappings → cần cast tường minh
    để khớp envelope `{success, data: {...}}` shape D6.
    """
    out: dict[str, Any] = {}
    for k, v in row.items():
        if isinstance(v, UUID):
            out[k] = str(v)
        elif isinstance(v, datetime):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out


async def list_guides(session: AsyncSession) -> list[dict]:
    """Trả danh sách guide sort by updated_at DESC (KHÔNG content cho tiết kiệm payload).

    Frontend list page chỉ cần meta + title; chi tiết content fetch riêng qua get_guide.
    """
    rows = (
        await session.execute(
            text(
                """
                SELECT id, title, created_by, updated_by, created_at, updated_at
                FROM guides
                ORDER BY updated_at DESC
                """
            )
        )
    ).mappings().all()
    return [_serialize(dict(r)) for r in rows]


async def get_guide(session: AsyncSession, guide_id: UUID | str) -> dict:
    """Trả 1 guide đầy đủ. Raise GuideNotFoundError nếu không có."""
    row = (
        await session.execute(
            text(
                """
                SELECT id, title, content, created_by, updated_by, created_at, updated_at
                FROM guides
                WHERE id = :guide_id
                """
            ),
            {"guide_id": str(guide_id)},
        )
    ).mappings().first()
    if row is None:
        raise GuideNotFoundError(f"guide_id={guide_id} not found")
    return _serialize(dict(row))


async def create_guide(
    session: AsyncSession,
    *,
    title: str,
    content: str,
    actor_id: UUID,
) -> dict:
    row = (
        await session.execute(
            text(
                """
                INSERT INTO guides (title, content, created_by, updated_by)
                VALUES (:title, :content, :actor, :actor)
                RETURNING id, title, content, created_by, updated_by, created_at, updated_at
                """
            ),
            {"title": title, "content": content, "actor": str(actor_id)},
        )
    ).mappings().first()
    await session.commit()
    assert row is not None  # RETURNING luôn có row sau INSERT thành công
    return _serialize(dict(row))


async def update_guide(
    session: AsyncSession,
    *,
    guide_id: UUID | str,
    title: str,
    content: str,
    actor_id: UUID,
) -> dict:
    row = (
        await session.execute(
            text(
                """
                UPDATE guides
                SET title = :title,
                    content = :content,
                    updated_by = :actor,
                    updated_at = NOW()
                WHERE id = :guide_id
                RETURNING id, title, content, created_by, updated_by, created_at, updated_at
                """
            ),
            {
                "title": title,
                "content": content,
                "actor": str(actor_id),
                "guide_id": str(guide_id),
            },
        )
    ).mappings().first()
    if row is None:
        raise GuideNotFoundError(f"guide_id={guide_id} not found")
    await session.commit()
    return _serialize(dict(row))


async def delete_guide(session: AsyncSession, *, guide_id: UUID | str) -> None:
    result = await session.execute(
        text("DELETE FROM guides WHERE id = :guide_id"),
        {"guide_id": str(guide_id)},
    )
    if result.rowcount == 0:
        raise GuideNotFoundError(f"guide_id={guide_id} not found")
    await session.commit()
