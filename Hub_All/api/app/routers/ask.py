"""Ask router — Plan 07-04 (ASK-01/02/03/05 + AUX-03).

3 endpoint POST — JWT bắt buộc (viewer+), shape khớp ASK-01 contract:

    POST /api/ask             — single-hub ask (ASK-01)
    POST /api/ask/cross-hub   — cross-hub ask (ASK-03)
    POST /api/search/answer   — RAG answer cho frontend `searchAnswer()`
                                (D-07-04-A — `CrossHubSearch` gọi path này)

`/api/search/answer` KHÁC `/api/ask`: frontend gửi `hub_ids` (mảng, rỗng = mọi
hub) chứ KHÔNG gửi `hub_id` đơn → endpoint chạy cross-hub ask và map response
sang shape `SearchAnswerAPI` (`answer` + `sources` + `citations` +
`search_results`) mà `frontend/src/services/api.ts` khai báo. `/api/ask` +
`/api/ask/cross-hub` giữ nguyên shape `AskResponse` thuần (ASK-01/ASK-03).

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
import re
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi.responses import JSONResponse

from app.auth.dependencies import UserWithHubs, get_current_user_with_hubs
from app.middleware import SEARCH_LIMIT, limiter
from app.pkg import response as resp
from app.schemas.ask import AskRequest
from app.services.ask_service import AskError, AskOutcome, AskService
from app.services.embedder import EmbedderError
from app.services.usage_service import log_usage_event

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ask"])

#: Marker citation `[N]` trong answer LLM (cùng quy ước `ask_prompt._MARKER_RE`).
_MARKER_RE = re.compile(r"\[(\d+)\]")


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
    # WR-01/WR-02 fix — validate hub scope ở router layer (AskRequest docstring
    # yêu cầu "một trong hai phải có"). Thiếu `hub_id` → `/api/ask` âm thầm chạy
    # cross-hub toàn bộ hub user được assign; thiếu `hub_ids` → `/cross-hub`
    # fan-out mọi hub (rủi ro chi phí LLM).
    if cross_hub:
        if not body.hub_ids:
            return resp.bad_request(
                message="cross-hub ask yêu cầu hub_ids — danh sách hub không được rỗng",
                code="INVALID_QUERY",
            )
    elif not body.hub_id or not body.hub_id.strip():
        return resp.bad_request(
            message="ask yêu cầu hub_id — không được để trống",
            code="INVALID_QUERY",
        )

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


def _to_search_answer(outcome: AskOutcome) -> dict[str, Any]:
    """Map `AskOutcome` → shape `SearchAnswerAPI` (frontend `searchAnswer()`).

    Bốn việc:
    1. Rewrite marker `[N]` trong answer → `[src:<chunk_id>]` — `CitationText`
       (regex `/\\[src:id\\]/`) cần marker dạng này để render chip trích dẫn.
    2. `citations`: `Citation` → `CitationRefAPI` (`id=chunk_id`,
       `snippet=content_snippet`; `chunk_index` chưa có ở chunk → 0).
    3. `search_results`: mỗi chunk → `SearchResultAPI` (`raw_similarity=score`
       — search service Phase 6 cũng set 2 field này bằng nhau).
    4. `sources`: mỗi chunk → `{doc_name, hub_name, snippet, score}`.
    """
    r = outcome.response
    # number → chunk_id để rewrite marker (mỗi number xuất hiện 1 Citation).
    num_to_id = {c.number: c.chunk_id for c in r.citations}

    def _sub(m: re.Match[str]) -> str:
        cid = num_to_id.get(int(m.group(1)))
        return f"[src:{cid}]" if cid else m.group(0)

    answer = _MARKER_RE.sub(_sub, r.answer)

    citations = [
        {
            "id": c.chunk_id,
            "marker": f"[src:{c.chunk_id}]",
            "number": c.number,
            "document_id": c.document_id,
            "document_name": c.document_name,
            "hub_name": c.hub_name,
            "chunk_index": 0,
            "snippet": c.content_snippet,
            "score": c.score,
        }
        for c in r.citations
    ]
    search_results: list[dict[str, Any]] = [
        {
            "id": ch.id,
            "hub_id": ch.hub_id,
            "hub_name": ch.hub_name,
            "title": ch.title,
            "snippet": ch.snippet,
            "content": ch.content,
            "category": None,
            "tags": [],
            "score": ch.score,
            "raw_similarity": ch.score,
            "updated_at": None,
            "source": "document",
        }
        for ch in outcome.chunks
    ]
    sources = [
        {
            "doc_name": ch.title,
            "hub_name": ch.hub_name,
            "snippet": ch.snippet,
            "score": ch.score,
        }
        for ch in outcome.chunks
    ]
    return {
        "answer": answer,
        "sources": sources,
        "citations": citations,
        "search_results": search_results,
        "query_time_ms": r.query_time_ms,
        "model": r.model,
    }


@router.post("/api/search/answer")
@limiter.limit(SEARCH_LIMIT)
async def search_answer_endpoint(
    request: Request,
    body: AskRequest,
    background_tasks: BackgroundTasks,
    user: UserWithHubs = Depends(get_current_user_with_hubs),  # noqa: B008
    service: AskService = Depends(get_ask_service),  # noqa: B008
) -> JSONResponse:
    """POST /api/search/answer — RAG answer cho frontend `searchAnswer()`.

    KHÁC `/api/ask` (xem docstring module): frontend gửi `hub_ids` (mảng, rỗng
    = mọi hub user được phép) → chạy `ask_cross_hub`. `ask_cross_hub` →
    `search_cross_hub` đã xử lý `hub_ids` rỗng: non-admin giao với hub được
    assign, admin fan-out mọi hub active — KHÔNG cần (và KHÔNG được) validate
    `hub_ids` non-rỗng như `/api/ask/cross-hub`.

    Map lỗi giống `_run_ask`; response map sang shape `SearchAnswerAPI`.
    """
    if not body.query or not body.query.strip():
        return resp.bad_request(
            message="ask yêu cầu query — không được để trống",
            code="INVALID_QUERY",
        )

    try:
        outcome = await service.ask_cross_hub(body=body, user=user)
    except ValueError as e:
        return resp.bad_request(message=str(e), code="INVALID_QUERY")
    except EmbedderError as e:
        return resp.internal_error(
            message=f"Embedding lỗi: {e}", code="EMBEDDING_FAILED"
        )
    except AskError as e:
        return resp.internal_error(message=f"LLM lỗi: {e}", code="LLM_FAILED")

    # Usage log qua BackgroundTasks (D-07-04-D / ASK-05) — giống `_run_ask`.
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
    return resp.ok(data=_to_search_answer(outcome))


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
