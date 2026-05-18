"""Ask router — Plan 07-04 (ASK-01/02/03/05 + AUX-03).

3 endpoint POST — JWT bắt buộc (viewer+), shape khớp ASK-01 contract:

    POST /api/ask             — single-hub ask (ASK-01)
    POST /api/ask/cross-hub   — cross-hub ask (ASK-03)
    POST /api/search/answer   — alias single-hub cho frontend `searchAnswer()`
                                (D-07-04-A — frontend GeminiAssistant gọi path này)

`APIRouter` KHÔNG prefix — path `/api/search/answer` khác nhánh với `/api/ask`,
nên khai báo path tuyệt đối từng endpoint.

Cả 3 endpoint decorate `limiter.limit(SEARCH_LIMIT)` (AUX-03 — 100/min/user;
`SEARCH_LIMIT = "100/minute"` đúng giá trị ask cần, tái dùng hằng). slowapi yêu
cầu endpoint function khai báo param `request: Request` (KHÔNG Depends); thứ tự
decorator: `router.post(...)` ở TRÊN, `limiter.limit(...)` ở DƯỚI (sát def) —
như search.py.

Usage logging (D-07-04-D / ASK-05): sau khi service trả `AskOutcome`, router
`background_tasks.add_task(log_usage_event, pool, **usage)` — ghi 1 row
`usage_events` non-blocking sau response. Service KHÔNG tự ghi (không có pool
injection sạch cho BackgroundTasks).

GHI CHÚ MÃ LỖI 502 (D-07-04-F): `app.pkg.response` KHÔNG có helper `bad_gateway`.
Để tránh đụng file dùng chung (`response.py`), `AskError` (LLM provider lỗi —
key sai/network/rate-limit provider) map qua `resp.internal_error(...,
code="LLM_FAILED")` → HTTP 500 với code `LLM_FAILED`. Chấp nhận M2: frontend chỉ
check `res.ok` (D6); code `LLM_FAILED` phân biệt được lỗi LLM với lỗi server khác.

DI factory `get_ask_service` đọc asyncpg pool + redis từ `request.app.state` —
AskService tái dùng SearchService (raw vector SQL), KHÔNG AsyncSession.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi.responses import JSONResponse

from app.auth.dependencies import UserWithHubs, get_current_user_with_hubs
from app.middleware import SEARCH_LIMIT, limiter
from app.pkg import response as resp
from app.schemas.ask import AskRequest
from app.services.ask_service import AskError, AskService
from app.services.embedder import EmbedderError
from app.services.usage_service import log_usage_event

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ask"])


def get_ask_service(request: Request) -> AskService:
    """DI factory — AskService cần asyncpg pool + redis từ `app.state`.

    AskService tái dùng SearchService (raw vector SQL `<=>` + `SET LOCAL
    hnsw.*`) → cần asyncpg pool, KHÔNG AsyncSession. `redis` có thể None (cache
    fail-open). `pool` None → `RuntimeError` → ErrorHandlerMiddleware map 500.
    """
    pool = getattr(request.app.state, "db_pool", None)
    redis = getattr(request.app.state, "redis", None)
    if pool is None:
        raise RuntimeError("db_pool chưa sẵn sàng — ask không khả dụng")
    return AskService(pool=pool, redis=redis)


async def _run_ask(
    *,
    body: AskRequest,
    user: UserWithHubs,
    service: AskService,
    background_tasks: BackgroundTasks,
    request: Request,
    cross_hub: bool,
) -> JSONResponse:
    """Chạy ask single/cross-hub dùng chung cho 3 endpoint — tránh lặp.

    Map lỗi:
    - `ValueError` (query rỗng) → 400 `INVALID_QUERY`.
    - `EmbedderError` (embed query lỗi) → 500 `EMBEDDING_FAILED`.
    - `AskError` (LLM provider lỗi) → 500 `LLM_FAILED` (D-07-04-F — xem docstring
      module; `resp` không có helper `bad_gateway`).

    Thành công → schedule `log_usage_event` qua BackgroundTasks (ASK-05) rồi
    trả `AskResponse` wrap envelope.
    """
    try:
        if cross_hub:
            outcome = await service.ask_cross_hub(body=body, user=user)
        else:
            outcome = await service.ask(body=body, user=user)
    except ValueError as e:
        return resp.bad_request(message=str(e), code="INVALID_QUERY")
    except EmbedderError as e:
        return resp.internal_error(
            message=f"Embedding lỗi: {e}", code="EMBEDDING_FAILED"
        )
    except AskError as e:
        # LLM provider lỗi (key sai/network/rate-limit provider). Code
        # `LLM_FAILED` phân biệt với lỗi server khác — message ngắn gọn,
        # KHÔNG leak stack trace (T-07-04-06).
        return resp.internal_error(message=f"LLM lỗi: {e}", code="LLM_FAILED")

    # Usage log qua BackgroundTasks (D-07-04-D / ASK-05) — chạy SAU response,
    # best-effort (`log_usage_event` tự bọc try/except, KHÔNG raise).
    usage = outcome.usage
    usage.request_id = getattr(request.state, "request_id", None)
    pool = request.app.state.db_pool
    background_tasks.add_task(
        log_usage_event,
        pool,
        user_id=usage.user_id,
        hub_id=usage.hub_id,
        model=usage.model,
        prompt_tokens=usage.prompt_tokens,
        completion_tokens=usage.completion_tokens,
        total_tokens=usage.total_tokens,
        cost_usd=usage.cost_usd,
        request_id=usage.request_id,
    )
    return resp.ok(data=outcome.response.model_dump())


@router.post("/api/ask")
@limiter.limit(SEARCH_LIMIT)
async def ask_endpoint(
    request: Request,
    body: AskRequest,
    background_tasks: BackgroundTasks,
    user: UserWithHubs = Depends(get_current_user_with_hubs),  # noqa: B008
    service: AskService = Depends(get_ask_service),  # noqa: B008
) -> JSONResponse:
    """POST /api/ask — single-hub ask (ASK-01)."""
    return await _run_ask(
        body=body,
        user=user,
        service=service,
        background_tasks=background_tasks,
        request=request,
        cross_hub=False,
    )


@router.post("/api/search/answer")
@limiter.limit(SEARCH_LIMIT)
async def search_answer_endpoint(
    request: Request,
    body: AskRequest,
    background_tasks: BackgroundTasks,
    user: UserWithHubs = Depends(get_current_user_with_hubs),  # noqa: B008
    service: AskService = Depends(get_ask_service),  # noqa: B008
) -> JSONResponse:
    """POST /api/search/answer — alias single-hub cho frontend (D-07-04-A)."""
    return await _run_ask(
        body=body,
        user=user,
        service=service,
        background_tasks=background_tasks,
        request=request,
        cross_hub=False,
    )


@router.post("/api/ask/cross-hub")
@limiter.limit(SEARCH_LIMIT)
async def ask_cross_hub_endpoint(
    request: Request,
    body: AskRequest,
    background_tasks: BackgroundTasks,
    user: UserWithHubs = Depends(get_current_user_with_hubs),  # noqa: B008
    service: AskService = Depends(get_ask_service),  # noqa: B008
) -> JSONResponse:
    """POST /api/ask/cross-hub — cross-hub ask (ASK-03)."""
    return await _run_ask(
        body=body,
        user=user,
        service=service,
        background_tasks=background_tasks,
        request=request,
        cross_hub=True,
    )
