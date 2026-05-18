"""Usage router — Plan 07-02 (ASK-05 token usage GET endpoint).

3 endpoint GET — admin-only (`require_role("admin")`; token usage là dữ liệu
chi phí → chỉ admin xem, nhất quán audit-logs — T-07-02-02):

    GET /api/usage           — list usage event + filter; ?group_by= → aggregate
    GET /api/usage/stats     — aggregate theo provider/model/operation/daily
    GET /api/usage/realtime  — window 60 phút group theo phút

D-07-02-D: `GET /api/usage?group_by=model` → DELEGATE sang `aggregate_usage()`
(ROADMAP SC5 verify URL literal). `UsageStats` đã chứa cả by_model/by_provider/
by_operation → 1 lần aggregate đủ bất kể `group_by` là gì. `group_by` chỉ chọn
nhánh code (truthy/None) — KHÔNG nối vào SQL (T-07-02-03). `GET /api/usage` không
truyền `group_by` → trả list `UsageEventResponse[]` như cũ.

3 endpoint READ-only nhẹ — KHÔNG cần `@limiter.limit` (rate-limit dành cho
/ask + /search tốn LLM/vector).

DI factory `get_db_pool` đọc asyncpg pool từ `app.state.db_pool` — usage dùng
raw SQL parametrized, KHÔNG AsyncSession.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse

from app.auth.dependencies import require_role
from app.models.auth import User
from app.pkg import response as resp
from app.services.usage_service import aggregate_usage, query_usage, realtime_usage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/usage", tags=["usage"])


def get_db_pool(request: Request) -> object:
    """DI factory — asyncpg pool từ `app.state.db_pool`.

    Pool None → `RuntimeError` → ErrorHandlerMiddleware map 500 envelope (pool
    down = service unavailable thực sự). Nhất quán `get_search_service`.
    """
    pool = getattr(request.app.state, "db_pool", None)
    if pool is None:
        raise RuntimeError("db_pool chưa sẵn sàng — usage không khả dụng")
    return pool


@router.get("")
async def list_usage(
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    provider: str | None = Query(None),
    model: str | None = Query(None),
    hub_id: str | None = Query(None),
    group_by: str | None = Query(None),
    page: int = Query(1),
    per_page: int = Query(50),
    user: User = Depends(require_role("admin")),  # noqa: B008
    pool: object = Depends(get_db_pool),  # noqa: B008
) -> JSONResponse:
    """GET /api/usage — list usage event; `?group_by=` → aggregate (D-07-02-D).

    `group_by` có giá trị → DELEGATE `aggregate_usage()` (ROADMAP SC5 URL
    literal `?group_by=model`). `group_by` None → list `UsageEventResponse[]`.
    """
    _ = user  # gate qua require_role.
    if group_by:
        stats = await aggregate_usage(pool, date_from=date_from, date_to=date_to)
        return resp.ok(data=stats.model_dump())
    events = await query_usage(
        pool,
        date_from=date_from,
        date_to=date_to,
        model=model,
        hub_id=hub_id,
        provider=provider,
        page=page,
        per_page=per_page,
    )
    return resp.ok(data=[e.model_dump() for e in events])


@router.get("/stats")
async def usage_stats(
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    user: User = Depends(require_role("admin")),  # noqa: B008
    pool: object = Depends(get_db_pool),  # noqa: B008
) -> JSONResponse:
    """GET /api/usage/stats — aggregate provider/model/operation/daily.

    Cùng gọi `aggregate_usage()` với `GET /api/usage?group_by=` → kết quả nhất
    quán. Frontend D6 dùng endpoint này.
    """
    _ = user
    stats = await aggregate_usage(pool, date_from=date_from, date_to=date_to)
    return resp.ok(data=stats.model_dump())


@router.get("/realtime")
async def usage_realtime(
    user: User = Depends(require_role("admin")),  # noqa: B008
    pool: object = Depends(get_db_pool),  # noqa: B008
) -> JSONResponse:
    """GET /api/usage/realtime — window 60 phút group theo phút (D-07-02-C)."""
    _ = user
    rt = await realtime_usage(pool)
    return resp.ok(data=rt.model_dump())
