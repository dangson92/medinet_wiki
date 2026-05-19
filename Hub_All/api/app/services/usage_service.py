"""Usage service — Plan 07-02 (ASK-05 token usage write + read path).

Tách 2 path đứng riêng:
- WRITE PATH `log_usage_event()` — ghi 1 row `usage_events` mỗi LLM call, gọi từ
  FastAPI BackgroundTasks ở Plan 07-04 (AskService). Best-effort: bọc try/except,
  KHÔNG raise — background task lỗi KHÔNG được làm sập request đã trả answer.
- READ PATH `query_usage()` / `aggregate_usage()` / `realtime_usage()` — phục vụ
  3 endpoint `GET /api/usage(+?group_by)` / `/stats` / `/realtime`.

Dùng asyncpg pool (KHÔNG AsyncSession) — nhất quán với `search_service.py`, và
write path gọi từ BackgroundTasks không có session DI. Toàn bộ query dùng
parametrized `$N` — KHÔNG nối chuỗi (T-07-02-03 SQL injection mitigation).

T-07-02-PII: bảng `usage_events` KHÔNG có cột chứa nội dung `query`/`answer` —
`log_usage_event` chỉ ghi token count + model + id → PII-safe by schema.
"""
from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

from app.schemas.usage import (
    UsageDailyPoint,
    UsageEventResponse,
    UsageGroup,
    UsageRealtime,
    UsageRealtimePoint,
    UsageStats,
)

logger = logging.getLogger(__name__)

# Cap per_page — chống DoS query nặng (T-07-02-04).
_MAX_PER_PAGE = 100


def _provider_of(model: str) -> str:
    """Derive provider từ tên model (D-07-02-A — bảng không có cột provider)."""
    return "gemini" if "gemini" in model.lower() else "openai"


# --------------------------------------------------------------------------
# WRITE PATH — gọi từ FastAPI BackgroundTasks (Plan 07-04 AskService).
# --------------------------------------------------------------------------


async def log_usage_event(
    pool: Any,
    *,
    user_id: str | None,
    hub_id: str | None,
    model: str,
    prompt_tokens: int | None,
    completion_tokens: int | None,
    total_tokens: int | None,
    cost_usd: float | None,
    request_id: str | None,
) -> None:
    """Ghi 1 row `usage_events` cho 1 LLM call (ASK-05 write path).

    Best-effort: bọc try/except — log warning, KHÔNG raise. Background task ghi
    usage lỗi KHÔNG được làm sập request. `$1`/`$2` cast `::uuid` (None khi
    user/hub null). `cost_usd` → `Decimal(str(...))` để khớp `Numeric(10,6)`.

    T-07-02-PII: chỉ ghi token count + model + id — KHÔNG ghi `query`/`answer`.
    """
    cost = Decimal(str(cost_usd)) if cost_usd is not None else None
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO usage_events "
                "(user_id, hub_id, model, prompt_tokens, completion_tokens, "
                "total_tokens, cost_usd, request_id) "
                "VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6, $7, $8)",
                user_id,
                hub_id,
                model,
                prompt_tokens,
                completion_tokens,
                total_tokens,
                cost,
                request_id,
            )
        logger.info("usage_logged", extra={"model": model, "request_id": request_id})
    except Exception:  # noqa: BLE001 — best-effort, KHÔNG raise (ASK-05).
        logger.warning(
            "usage_log_failed",
            extra={"model": model, "request_id": request_id},
            exc_info=True,
        )


# --------------------------------------------------------------------------
# READ PATH — phục vụ 3 endpoint GET /api/usage.
# --------------------------------------------------------------------------


async def query_usage(
    pool: Any,
    *,
    date_from: str | None,
    date_to: str | None,
    model: str | None,
    hub_id: str | None,
    provider: str | None,
    page: int,
    per_page: int,
) -> list[UsageEventResponse]:
    """List usage event phân trang + filter — READ PATH cho `GET /api/usage`.

    WHERE-builder động với placeholder `$N` (KHÔNG nối chuỗi). `provider` filter
    map sang `model ILIKE 'gemini%'` (gemini) hoặc `NOT ILIKE` (openai) — bảng
    không có cột provider. `per_page` cap `min(per_page, 100)` (T-07-02-04).
    """
    capped_per_page = max(1, min(per_page, _MAX_PER_PAGE))
    capped_page = max(1, page)
    offset = (capped_page - 1) * capped_per_page

    clauses: list[str] = []
    params: list[Any] = []

    # `::text::timestamptz` (KHÔNG `::timestamptz`): asyncpg suy kiểu `$N` trong
    # `$N::timestamptz` thành timestamptz → ĐÒI `datetime`; `date_from`/`date_to`
    # là str query-param → asyncpg raise `DataError` → 500. `::text` ép `$N`
    # thành text (asyncpg gửi str OK), Postgres cast text→timestamptz lúc chạy.
    if date_from:
        params.append(date_from)
        clauses.append(f"created_at >= ${len(params)}::text::timestamptz")
    if date_to:
        params.append(date_to)
        clauses.append(f"created_at <= ${len(params)}::text::timestamptz")
    if model:
        params.append(model)
        clauses.append(f"model = ${len(params)}")
    if hub_id:
        params.append(hub_id)
        clauses.append(f"hub_id = ${len(params)}::uuid")
    if provider == "gemini":
        clauses.append("model ILIKE 'gemini%'")
    elif provider == "openai":
        clauses.append("model NOT ILIKE 'gemini%'")

    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(capped_per_page)
    limit_idx = len(params)
    params.append(offset)
    offset_idx = len(params)

    sql = (
        "SELECT id, user_id, hub_id, model, prompt_tokens, completion_tokens, "
        "total_tokens, cost_usd, request_id, created_at "
        f"FROM usage_events {where_sql} "
        f"ORDER BY created_at DESC LIMIT ${limit_idx} OFFSET ${offset_idx}"
    )

    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, *params)

    return [_row_to_event(row) for row in rows]


def _row_to_event(row: Any) -> UsageEventResponse:
    """Map 1 row `usage_events` → UsageEventResponse áp D-07-02-A."""
    model = str(row["model"])
    return UsageEventResponse(
        id=str(row["id"]),
        timestamp=row["created_at"].isoformat(),
        provider=_provider_of(model),
        model=model,
        operation="ask",
        source_module="ask",
        user_id=str(row["user_id"]) if row["user_id"] is not None else None,
        user_name=None,
        hub_id=str(row["hub_id"]) if row["hub_id"] is not None else None,
        request_count=1,
        prompt_tokens=row["prompt_tokens"] or 0,
        output_tokens=row["completion_tokens"] or 0,
        total_tokens=row["total_tokens"] or 0,
        latency_ms=0,
        status="success",
        error_message=None,
    )


async def aggregate_usage(
    pool: Any,
    *,
    date_from: str | None,
    date_to: str | None,
) -> UsageStats:
    """Aggregate usage — READ PATH cho `GET /api/usage/stats` VÀ `?group_by=...`.

    D-07-02-D: cùng hàm phục vụ `/stats` và `GET /api/usage?group_by=` → kết quả
    nhất quán. `error_calls`/`avg_latency_ms` hằng 0 (D-07-02-A — không có cột).
    """
    clauses: list[str] = []
    params: list[Any] = []
    # `::text::timestamptz` — xem chú thích `query_usage`: tránh asyncpg
    # `DataError` khi `date_from`/`date_to` là str (asyncpg suy `$N::timestamptz`
    # thành timestamptz → đòi `datetime`).
    if date_from:
        params.append(date_from)
        clauses.append(f"created_at >= ${len(params)}::text::timestamptz")
    if date_to:
        params.append(date_to)
        clauses.append(f"created_at <= ${len(params)}::text::timestamptz")
    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    async with pool.acquire() as conn:
        totals = await conn.fetchrow(
            "SELECT count(*) AS calls, "
            "COALESCE(sum(total_tokens), 0) AS total_tokens, "
            "COALESCE(sum(prompt_tokens), 0) AS prompt_tokens, "
            "COALESCE(sum(completion_tokens), 0) AS completion_tokens "
            f"FROM usage_events {where_sql}",
            *params,
        )
        model_rows = await conn.fetch(
            "SELECT model AS key, count(*) AS calls, "
            "COALESCE(sum(total_tokens), 0) AS total_tokens "
            f"FROM usage_events {where_sql} "
            "GROUP BY model ORDER BY total_tokens DESC",
            *params,
        )
        provider_rows = await conn.fetch(
            "SELECT CASE WHEN model ILIKE 'gemini%' THEN 'gemini' "
            "ELSE 'openai' END AS key, count(*) AS calls, "
            "COALESCE(sum(total_tokens), 0) AS total_tokens "
            f"FROM usage_events {where_sql} "
            "GROUP BY 1 ORDER BY total_tokens DESC",
            *params,
        )
        daily_rows = await conn.fetch(
            "SELECT created_at::date AS day, count(*) AS calls, "
            "COALESCE(sum(total_tokens), 0) AS total_tokens "
            f"FROM usage_events {where_sql} "
            "GROUP BY 1 ORDER BY 1",
            *params,
        )

    total_calls = int(totals["calls"])
    total_tokens = int(totals["total_tokens"])

    return UsageStats(
        total_calls=total_calls,
        total_tokens=total_tokens,
        total_prompt_tokens=int(totals["prompt_tokens"]),
        total_output_tokens=int(totals["completion_tokens"]),
        error_calls=0,
        avg_latency_ms=0.0,
        by_provider=[
            UsageGroup(
                key=str(r["key"]),
                calls=int(r["calls"]),
                total_tokens=int(r["total_tokens"]),
            )
            for r in provider_rows
        ],
        by_model=[
            UsageGroup(
                key=str(r["key"]),
                calls=int(r["calls"]),
                total_tokens=int(r["total_tokens"]),
            )
            for r in model_rows
        ],
        # M2 chỉ có operation "ask" — gộp toàn bộ vào 1 nhóm.
        by_operation=[
            UsageGroup(key="ask", calls=total_calls, total_tokens=total_tokens)
        ],
        daily=[
            UsageDailyPoint(
                date=r["day"].isoformat(),
                calls=int(r["calls"]),
                total_tokens=int(r["total_tokens"]),
            )
            for r in daily_rows
        ],
    )


async def realtime_usage(pool: Any) -> UsageRealtime:
    """Usage realtime window 60 phút group theo phút — `GET /api/usage/realtime`.

    D-07-02-C: best-effort từ cùng bảng `usage_events` — KHÔNG stream.
    `avg_latency_ms`/`errors` hằng 0 (D-07-02-A).
    """
    async with pool.acquire() as conn:
        point_rows = await conn.fetch(
            "SELECT to_char(created_at, 'YYYY-MM-DD HH24:MI') AS minute, "
            "count(*) AS calls, "
            "COALESCE(sum(total_tokens), 0) AS total_tokens, "
            "COALESCE(sum(prompt_tokens), 0) AS prompt_tokens, "
            "COALESCE(sum(completion_tokens), 0) AS completion_tokens "
            "FROM usage_events "
            "WHERE created_at > NOW() - INTERVAL '60 minutes' "
            "GROUP BY 1 ORDER BY 1"
        )
        provider_rows = await conn.fetch(
            "SELECT CASE WHEN model ILIKE 'gemini%' THEN 'gemini' "
            "ELSE 'openai' END AS key, count(*) AS calls "
            "FROM usage_events "
            "WHERE created_at > NOW() - INTERVAL '60 minutes' "
            "GROUP BY 1"
        )

    points = [
        UsageRealtimePoint(
            minute=str(r["minute"]),
            calls=int(r["calls"]),
            total_tokens=int(r["total_tokens"]),
            prompt_tokens=int(r["prompt_tokens"]),
            output_tokens=int(r["completion_tokens"]),
            avg_latency_ms=0.0,
            errors=0,
            by_provider={},
            by_operation={},
        )
        for r in point_rows
    ]

    by_provider = {str(r["key"]): int(r["calls"]) for r in provider_rows}
    totals = UsageRealtimePoint(
        minute="totals",
        calls=sum(p.calls for p in points),
        total_tokens=sum(p.total_tokens for p in points),
        prompt_tokens=sum(p.prompt_tokens for p in points),
        output_tokens=sum(p.output_tokens for p in points),
        avg_latency_ms=0.0,
        errors=0,
        by_provider=by_provider,
        by_operation={"ask": sum(p.calls for p in points)},
    )

    return UsageRealtime(window_minutes=60, points=points, totals=totals)
