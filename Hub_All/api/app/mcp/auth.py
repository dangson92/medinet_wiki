"""MCP authentication — Phase 8.1 (MCP-01, D-05/D-06/D-12).

`authenticate_mcp_request()` — xác thực MCP client qua header X-API-Key.

Tái dùng luồng `get_api_key_or_jwt` (app/auth/dependencies.py lines 222–288)
nhưng KHÔNG có FastAPI DI context — 3 khác biệt then chốt:
1. Header đọc qua `ctx.request_context.request.headers` (Starlette Request trong
   MCP Context — `mcp==1.9.4` tích hợp FastMCP, không có module `fastmcp` riêng;
   tool handler nhận `ctx: Context` → truy cập HTTP headers)
2. Lỗi auth → raise ValueError (KHÔNG HTTPException — không có FastAPI error context trong MCP tool)
3. await db.commit() bắt buộc sau verify_key (MEMORY: project_fastapi_bgtask_commit —
   ApiKeyService.verify_key ghi last_used_at=NOW(), PHẢI commit trước session close)

Caller (tool handler) bắt ValueError → raise ToolError (KHÔNG để tool chạy nếu auth fail — D-06).
"""
from __future__ import annotations

import asyncpg
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import UserWithHubs
from app.db.session import get_engine
from app.models.auth import User, UserHub
from app.services.api_key_service import ApiKeyService


def _get_api_key_from_ctx(ctx: object) -> str | None:
    """Đọc X-API-Key từ HTTP headers trong MCP Context (Starlette Request).

    `mcp==1.9.4`: `ctx.request_context.request` là Starlette `Request` object
    khi dùng Streamable HTTP transport (`stateless_http=True`).
    Headers lowercase theo ASGI convention → dùng `x-api-key`.
    """
    try:
        request = ctx.request_context.request  # type: ignore[attr-defined]
        if request is None:
            return None
        return request.headers.get("x-api-key")
    except (AttributeError, LookupError):
        return None


async def authenticate_mcp_request(
    ctx: object,
    pool: asyncpg.Pool,  # noqa: ARG001 — reserve param cho tương lai, giữ nhất quán với RESEARCH.md Pattern 4
) -> UserWithHubs:
    """Xác thực MCP client qua header X-API-Key → dựng UserWithHubs.

    Gọi từ đầu mỗi tool handler. Raise ValueError nếu auth fail → tool handler
    map sang ToolError → client nhận MCP error (isError: true).

    Analog: `get_api_key_or_jwt` (app/auth/dependencies.py lines 222–288).
    Khác: không Depends, HTTPException → ValueError, ctx.request_context.request.headers.

    Args:
        ctx: MCP Context object (inject tự động qua `ctx: Context` annotation).
        pool: asyncpg.Pool (reserve param — chưa dùng trực tiếp; giữ nhất quán
              với RESEARCH.md Pattern 4 để sau này inject qua _get_pool()).

    Returns:
        UserWithHubs với user ORM + danh sách hub_id từ user_hubs.

    Raises:
        ValueError: nếu header thiếu, key không hợp lệ/thu hồi, user bị vô hiệu.
    """
    # Bước 1: đọc X-API-Key từ HTTP header (Starlette Request qua MCP Context)
    api_key = _get_api_key_from_ctx(ctx)
    if not api_key:
        raise ValueError("MCP_UNAUTHORIZED: thiếu header X-API-Key")

    # Bước 2: verify qua ApiKeyService (SQLAlchemy session thủ công — không có Depends)
    engine = get_engine()
    async with AsyncSession(engine) as db:
        svc = ApiKeyService(db=db)
        principal = await svc.verify_key(api_key)
        if principal is None:
            raise ValueError("MCP_UNAUTHORIZED: API key không hợp lệ hoặc đã thu hồi")

        # Bước 3: load created_by user_id từ api_keys table (giống dependencies.py lines 255–269)
        key_row = (
            await db.execute(
                text("SELECT created_by FROM api_keys WHERE id = :id"),
                {"id": principal["id"]},
            )
        ).fetchone()
        if key_row is None or key_row[0] is None:
            raise ValueError("MCP_UNAUTHORIZED: API key không gắn user hợp lệ")

        # Bước 4: load User ORM — phải is_active=True
        stmt = select(User).where(User.id == key_row[0], User.is_active.is_(True))
        user = (await db.execute(stmt)).scalar_one_or_none()
        if user is None:
            raise ValueError("MCP_UNAUTHORIZED: User gắn API key đã bị vô hiệu hoá")

        # Bước 5: load hub_ids từ user_hubs (giống get_current_user_with_hubs dependencies.py lines 215–218)
        stmt_hubs = select(UserHub.hub_id).where(UserHub.user_id == user.id)
        hub_ids = [str(h) for h in (await db.execute(stmt_hubs)).scalars().all()]

        # CRITICAL: commit TRƯỚC khi AsyncSession close
        # ApiKeyService.verify_key ghi last_used_at=NOW() → nếu không commit → bị rollback
        # MEMORY: project_fastapi_bgtask_commit.md — commit SAU background writes
        await db.commit()

    return UserWithHubs(user=user, hub_ids=hub_ids)
