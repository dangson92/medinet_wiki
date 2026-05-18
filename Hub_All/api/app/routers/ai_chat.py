"""AI chat router — Plan 08-02 (COMPAT-01, BLOCKER /api/ai/chat).

1 endpoint proxy LLM tối giản cho component `GeminiAssistant` (trợ lý chat tự
do trên Dashboard) — KHÁC `/api/ask`: KHÔNG RAG retrieval, KHÔNG citation, chỉ
forward hội thoại tới LLM:

    POST /api/ai/chat   — chat trợ lý (JWT bắt buộc, viewer+)

Frontend `api.ts` `aiChat()` gọi path này, kỳ vọng envelope
`{success, data: {response: string}, error, meta}` (D6 contract). Component
gửi role `model` (quy ước Gemini) cho lượt trợ lý — router chuẩn hoá thành
`assistant` để LiteLLM/OpenAI chấp nhận.

`APIRouter` KHÔNG prefix — khai báo path tuyệt đối `/api/ai/chat` như `ask.py`.
`limiter.limit(SEARCH_LIMIT)` (100/min/user) chống abuse đẩy chi phí LLM
(T-08-02-03). JWT bắt buộc qua `get_current_user` (T-08-02-02).

Hot-swap provider (ASK-04): tái dùng `_resolve_llm_model()` từ `ask_service`
— đọc `get_settings()` mỗi lần gọi nên admin đổi provider runtime có hiệu lực
ngay. KHÔNG copy logic resolve model.

Containment lỗi (T-08-02-04): try/except quanh `litellm.acompletion` — mọi lỗi
provider → envelope `LLM_FAILED` message generic; log KHÔNG chứa nội dung
message người dùng (PII-safe).

Hàm lõi `run_ai_chat(body)` tách khỏi endpoint FastAPI để unit test thuần
Python mock `litellm.acompletion` không cần ASGI app/DB.
"""
from __future__ import annotations

import logging

import litellm
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.auth.dependencies import get_current_user
from app.middleware import SEARCH_LIMIT, limiter
from app.models.auth import User
from app.pkg import response as resp
from app.services.ask_service import _resolve_llm_model

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ai"])


class AiChatMessage(BaseModel):
    """1 lượt hội thoại — `role` frontend gửi `user`/`model` (quy ước Gemini)."""

    role: str
    content: str


class AiChatRequest(BaseModel):
    """Body POST /api/ai/chat — lịch sử hội thoại + system instruction tuỳ chọn."""

    messages: list[AiChatMessage] = Field(default_factory=list)
    system_instruction: str | None = None


class AiChatResponse(BaseModel):
    """Envelope `data` — frontend `api.ts` đọc `res.data.response`."""

    response: str


def _normalize_role(role: str) -> str:
    """Chuẩn hoá role frontend → role LiteLLM/OpenAI chấp nhận.

    GeminiAssistant gửi `model` cho lượt trợ lý (quy ước Gemini API). LiteLLM
    chuẩn OpenAI dùng `assistant` — map để tránh provider reject. Role khác
    giữ nguyên (`user`, `system`).
    """
    return "assistant" if role == "model" else role


async def run_ai_chat(body: AiChatRequest) -> JSONResponse:
    """Lõi xử lý /api/ai/chat — tách khỏi endpoint để unit test thuần Python.

    Trình tự:
    1. `messages` rỗng → 400 `INVALID_REQUEST`.
    2. Dựng `llm_messages`: prepend `system` nếu có `system_instruction`; map
       từng message + chuẩn hoá role (`model` → `assistant`).
    3. Resolve model qua `_resolve_llm_model()` (hot-swap ASK-04).
    4. `litellm.acompletion` non-streaming, bọc try/except → lỗi provider trả
       envelope `LLM_FAILED` message generic (T-08-02-04 — KHÔNG leak trace,
       log KHÔNG chứa nội dung message).
    5. Trích `choices[0].message.content` an toàn (getattr phòng None).
    6. `resp.ok({response: answer})`.
    """
    if not body.messages:
        return resp.bad_request(
            message="messages không được rỗng",
            code="INVALID_REQUEST",
        )

    llm_messages: list[dict[str, str]] = []
    if body.system_instruction:
        llm_messages.append(
            {"role": "system", "content": body.system_instruction}
        )
    llm_messages.extend(
        {"role": _normalize_role(m.role), "content": m.content}
        for m in body.messages
    )

    _provider, model = _resolve_llm_model()
    try:
        completion = await litellm.acompletion(
            model=model, messages=llm_messages
        )
    except Exception as e:  # noqa: BLE001 — bọc mọi lỗi provider LiteLLM
        # KHÔNG log nội dung message (PII); chỉ model + loại lỗi.
        logger.error(
            "ai_chat_llm_failed", extra={"model": model, "error": str(e)}
        )
        return resp.internal_error(
            message="LLM gọi thất bại", code="LLM_FAILED"
        )

    # Trích text an toàn — completion shape có thể thiếu field.
    answer = ""
    try:
        choices = getattr(completion, "choices", None) or []
        if choices:
            message = getattr(choices[0], "message", None)
            answer = getattr(message, "content", None) or ""
    except (AttributeError, IndexError, KeyError):
        answer = ""

    return resp.ok(data=AiChatResponse(response=str(answer)).model_dump())


@router.post("/api/ai/chat")
@limiter.limit(SEARCH_LIMIT)
async def ai_chat(
    request: Request,
    body: AiChatRequest,
    user: User = Depends(get_current_user),  # noqa: B008 — FastAPI pattern
) -> JSONResponse:
    """POST /api/ai/chat — proxy LLM cho GeminiAssistant (COMPAT-01).

    JWT bắt buộc (`get_current_user` → 401 nếu thiếu/sai token). `request` cần
    cho slowapi rate-limit. Logic ở `run_ai_chat` để unit test tách biệt.
    """
    _ = (request, user)  # chữ ký dependency — slowapi + auth gate.
    return await run_ai_chat(body)
