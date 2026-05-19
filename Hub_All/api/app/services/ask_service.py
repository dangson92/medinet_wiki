"""Ask service — Plan 07-04 (ASK-01/02/03/05 — lắp ráp toàn bộ Ask API).

`AskService` nối các mảnh đã định nghĩa ở Wave 1 thành luồng hỏi-đáp hoàn chỉnh:

    retrieve (tái dùng `SearchService` Phase 6)
      → bổ sung `document_id` cho từng chunk (D-07-04-C)
      → dựng prompt anti-injection (07-01 `ask_prompt.build_ask_messages`)
      → gọi `litellm.acompletion()` non-streaming
      → parse citation `[N]` → `chunk_id` (07-01 `ask_prompt.parse_citations`)
      → trả `AskOutcome(AskResponse, UsageRecord)`.

Quyết định liên quan (Plan 07-04 `<decisions>`):
- D-07-04-C — `SearchResponse.results` KHÔNG có `document_id`. Service tự query
  `SELECT id, document_id FROM chunks WHERE id = ANY($1::uuid[])` rồi bọc mỗi
  result thành `_AskChunk` đủ field `parse_citations` cần. KHÔNG sửa
  `SearchService`/`SearchResultItem` (file Phase 6 — tránh đụng ngoài scope).
- D-07-04-D — Service KHÔNG tự ghi `usage_events` (không có pool injection
  sạch cho BackgroundTasks). Trả `UsageRecord` để router
  `background_tasks.add_task(log_usage_event, ...)`.
- D-07-04-F — LLM call lỗi → raise `AskError`; router map 502/500 `LLM_FAILED`.
  Search rỗng → VẪN gọi LLM context rỗng → LLM trả câu từ chối (ASK-02).

Hot-swap (ASK-04): `_resolve_llm_model()` đọc `get_settings()` MỖI lần gọi →
admin đổi provider runtime qua `/api/rag-config` có hiệu lực ngay câu hỏi kế.

LiteLLM 1.83.14 (pin `litellm>=1.82,<2` trong `pyproject.toml` — xác nhận
BƯỚC 0 Plan 07-04): `litellm.acompletion(model=..., messages=...)` trả
`ModelResponse` object (`.choices[0].message.content`, `.usage`);
`litellm.completion_cost(completion_response=...)` trả `float` USD (có thể
raise nếu provider không có bảng giá) — chữ ký khớp `<interfaces>`.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

import litellm

from app.config import get_settings
from app.schemas.ask import AskRequest, AskResponse
from app.schemas.search import SearchRequest
from app.services.ask_prompt import build_ask_messages, parse_citations
from app.services.search_service import SearchService

logger = logging.getLogger(__name__)

__all__ = ["AskService", "AskError", "AskOutcome", "UsageRecord"]

#: Top-k mặc định khi request không gửi (D-07-01-B).
_DEFAULT_TOP_K = 6
#: Clamp top-k vào `[_MIN_TOP_K, _MAX_TOP_K]` (D-07-01-B).
_MIN_TOP_K = 1
_MAX_TOP_K = 12


class AskError(Exception):
    """LLM call fail hoặc response shape sai — router map 502/500 `LLM_FAILED`.

    Bao mọi lỗi từ provider LiteLLM (key sai, network, rate-limit provider) +
    trường hợp `acompletion` trả content rỗng/None.
    """


@dataclass
class UsageRecord:
    """Payload cho `log_usage_event` (ASK-05) — router schedule qua BackgroundTasks.

    `request_id` để None ở service — router override từ `request.state.request_id`
    trước khi `add_task` (D-07-04-D).
    """

    user_id: str | None
    hub_id: str | None
    model: str
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None
    cost_usd: float | None
    request_id: str | None


@dataclass
class AskOutcome:
    """Kết quả `AskService.ask()`/`ask_cross_hub()` trả router.

    Router lấy `response` wrap envelope + dùng `usage` cho BackgroundTasks.
    `chunks` — danh sách đoạn đã retrieve, để router `/api/search/answer` dựng
    `sources` + `search_results` cho shape `SearchAnswerAPI` (frontend D6).
    """

    response: AskResponse
    usage: UsageRecord
    chunks: list[_AskChunk]


@dataclass
class _AskChunk:
    """Wrap 1 search result + `document_id` để `parse_citations` đọc (D-07-04-C).

    `build_ask_messages`/`parse_citations` đọc field qua `getattr` — dataclass
    với đủ field là an toàn. `document_id` bổ sung từ query `chunks` (search
    Phase 6 KHÔNG trả field này).
    """

    id: str
    document_id: str
    hub_id: str
    title: str
    hub_name: str
    snippet: str
    content: str | None
    score: float


def _resolve_llm_model() -> tuple[str, str]:
    """Đọc settings → `(provider, model_for_litellm)`.

    ĐỌC `get_settings()` MỖI lần gọi → hot-swap (ASK-04) có hiệu lực ngay.

    Model PHẢI chọn theo provider — `rag_llm_model` là model OpenAI,
    `rag_gemini_llm_model` là model Gemini (2 field TÁCH BIỆT; rag-config UI chỉ
    cho đổi model Gemini, model OpenAI cố định). Provider `gemini` → thêm prefix
    `gemini/` nếu thiếu (Gemini API Google AI Studio cần prefix — cùng quy ước
    `embedder.py`). Provider khác (`openai`/`auto`) → dùng model OpenAI.
    """
    s = get_settings()
    provider = s.rag_llm_provider
    if provider == "gemini":
        model = s.rag_gemini_llm_model
        if "/" not in model:
            model = f"gemini/{model}"
        return provider, model
    return provider, s.rag_llm_model


def _resolve_top_k(raw: int | None) -> int:
    """`raw` None → `_DEFAULT_TOP_K`; clamp vào `[_MIN_TOP_K, _MAX_TOP_K]`."""
    if raw is None:
        return _DEFAULT_TOP_K
    return max(_MIN_TOP_K, min(raw, _MAX_TOP_K))


class AskService:
    """Ask engine — retrieve + LLM call + citation parse + usage record.

    Tái dùng `SearchService` (Phase 6) cho retrieval — KHÔNG nhân bản vector
    search. `pool` (asyncpg) cũng dùng để query `document_id` bổ sung (D-07-04-C).
    """

    def __init__(self, *, pool: Any, redis: Any = None) -> None:
        self.pool = pool
        self.search = SearchService(pool=pool, redis=redis)

    async def _retrieve(
        self,
        *,
        body: AskRequest,
        user: Any,
        cross_hub: bool,
    ) -> list[_AskChunk]:
        """Retrieve chunks qua `SearchService` + bổ sung `document_id` (D-07-04-C).

        - `cross_hub=True` → `search_cross_hub` với `hub_ids=body.hub_ids`;
          single-hub → `search` với `hub_ids=[body.hub_id]` (nếu có).
        - Sau search trả results: query `SELECT id, document_id FROM chunks
          WHERE id = ANY($1::uuid[])` map `chunk.id → document_id`.
        - Bọc mỗi result thành `_AskChunk` (đủ field `parse_citations` cần).
        - Results rỗng → trả `[]` (ASK-02 — vẫn gọi LLM context rỗng, D-07-04-F).
        """
        top_k = _resolve_top_k(body.top_k)
        if cross_hub:
            search_body = SearchRequest(
                query=body.query, hub_ids=body.hub_ids, top_k=top_k
            )
            result = await self.search.search_cross_hub(body=search_body, user=user)
        else:
            hub_ids = [body.hub_id] if body.hub_id else None
            search_body = SearchRequest(
                query=body.query, hub_ids=hub_ids, top_k=top_k
            )
            result = await self.search.search(body=search_body, user=user)

        results: list[dict[str, Any]] = result["results"]
        if not results:
            return []

        # D-07-04-C — search Phase 6 KHÔNG trả `document_id`; bổ sung qua query
        # `chunks`. Cast `$1::uuid[]` — `chunk.id` là string UUID.
        chunk_ids = [r["id"] for r in results]
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id, document_id FROM chunks WHERE id = ANY($1::uuid[])",
                chunk_ids,
            )
        doc_map = {str(row["id"]): str(row["document_id"]) for row in rows}

        return [
            _AskChunk(
                id=str(r["id"]),
                document_id=doc_map.get(str(r["id"]), ""),
                hub_id=str(r["hub_id"]),
                title=r["title"],
                hub_name=r["hub_name"],
                snippet=r["snippet"],
                content=r.get("content"),
                score=float(r["score"]),
            )
            for r in results
        ]

    async def _call_llm(
        self, messages: list[dict[str, str]]
    ) -> tuple[str, Any, str]:
        """Gọi `litellm.acompletion` non-streaming → `(answer, resp, model)`.

        Mọi exception LiteLLM (key sai, network, rate-limit provider) → `AskError`
        (D-07-04-F). Content None/rỗng → cũng raise `AskError` (response shape sai).
        """
        _provider, model = _resolve_llm_model()
        try:
            resp = await litellm.acompletion(model=model, messages=messages)
        except Exception as e:  # noqa: BLE001 — wrap mọi lỗi provider LiteLLM
            logger.error("ask_llm_failed: model=%s err=%s", model, e)
            raise AskError(f"LLM call fail: {e}") from e

        try:
            answer = resp.choices[0].message.content
        except (AttributeError, IndexError, KeyError) as e:
            raise AskError(f"LLM response shape sai: {e}") from e
        if not answer or not str(answer).strip():
            raise AskError("LLM trả nội dung rỗng")

        return str(answer), resp, model

    @staticmethod
    def _extract_usage(
        resp: Any, *, user_id: str | None, hub_id: str | None, model: str
    ) -> UsageRecord:
        """Dựng `UsageRecord` từ LiteLLM response — token + cost an toàn None.

        `resp.usage` có thể thiếu field; `litellm.completion_cost` có thể raise
        (provider không có bảng giá / key placeholder dev) → cost None.
        """
        usage_obj = getattr(resp, "usage", None)
        prompt_tokens = getattr(usage_obj, "prompt_tokens", None)
        completion_tokens = getattr(usage_obj, "completion_tokens", None)
        total_tokens = getattr(usage_obj, "total_tokens", None)

        cost_usd: float | None
        try:
            cost_usd = litellm.completion_cost(completion_response=resp)
        except Exception:  # noqa: BLE001 — cost không lấy được → None (D-07-04-D)
            cost_usd = None

        return UsageRecord(
            user_id=user_id,
            hub_id=hub_id,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost_usd=cost_usd,
            request_id=None,  # router override từ request.state.request_id
        )

    async def ask(self, *, body: AskRequest, user: Any) -> AskOutcome:
        """Single-hub ask (ASK-01) — retrieve 1 hub + LLM + citation + usage.

        Trả `AskOutcome` — `AskResponse` mang `answer`/`citations`/`model`/
        `query_time_ms`; `UsageRecord` cho router schedule `log_usage_event`.
        """
        t0 = time.perf_counter()
        chunks = await self._retrieve(body=body, user=user, cross_hub=False)
        messages = build_ask_messages(body.query, chunks)
        answer, resp, model = await self._call_llm(messages)
        citations = parse_citations(answer, chunks)
        usage = self._extract_usage(
            resp, user_id=str(user.user.id), hub_id=body.hub_id, model=model
        )
        query_time_ms = int((time.perf_counter() - t0) * 1000)

        logger.info(
            "ask_completed",
            extra={
                "model": model,
                "chunk_count": len(chunks),
                "citation_count": len(citations),
                "query_time_ms": query_time_ms,
            },
        )
        return AskOutcome(
            response=AskResponse(
                answer=answer,
                citations=citations,
                model=model,
                query_time_ms=query_time_ms,
            ),
            usage=usage,
            chunks=chunks,
        )

    async def ask_cross_hub(self, *, body: AskRequest, user: Any) -> AskOutcome:
        """Cross-hub ask (ASK-03) — retrieve nhiều hub + LLM + citation + usage.

        GIỐNG `ask()` nhưng `_retrieve(cross_hub=True)`; `UsageRecord.hub_id=None`
        (cross-hub không thuộc 1 hub cụ thể). Tách method riêng cho rõ ràng —
        chấp nhận lặp nhẹ (KHÔNG dùng flag).
        """
        t0 = time.perf_counter()
        chunks = await self._retrieve(body=body, user=user, cross_hub=True)
        messages = build_ask_messages(body.query, chunks)
        answer, resp, model = await self._call_llm(messages)
        citations = parse_citations(answer, chunks)
        usage = self._extract_usage(
            resp, user_id=str(user.user.id), hub_id=None, model=model
        )
        query_time_ms = int((time.perf_counter() - t0) * 1000)

        logger.info(
            "ask_cross_hub_completed",
            extra={
                "model": model,
                "chunk_count": len(chunks),
                "citation_count": len(citations),
                "query_time_ms": query_time_ms,
            },
        )
        return AskOutcome(
            response=AskResponse(
                answer=answer,
                citations=citations,
                model=model,
                query_time_ms=query_time_ms,
            ),
            usage=usage,
            chunks=chunks,
        )
