"""LiteLLM embedding wrapper — Plan 04-02 Task 03 (INGEST-02 prerequisite).

PIN dimensions=1536 cho cả OpenAI + Gemini (R1 mitigation pgvector HNSW index
2000-dim limit + R7 hot-swap WITHIN cùng dim không cần re-embed corpus).

Cocoindex flow Plan 04-03 wrap function này thành cocoindex.op.function để flow
gọi async. Settings hot-swap qua get_settings().rag_embedding_provider /
rag_embedding_model — Plan 07 (ASK-04) UI cho phép admin đổi runtime.

LiteLLM 1.82+ API:
    response = await litellm.aembedding(
        model="text-embedding-3-small",   # hoặc "gemini/embedding-001"
        input=[text],                     # list để batch (M2 chỉ pass 1)
        dimensions=1536,                  # PIN R1
    )
    vector = response.data[0]["embedding"]  # list[float] length 1536

Tham chiếu:
- PROJECT.md R1 — pgvector dim 2000 limit, pin 1536.
- PROJECT.md R7 — hot-swap dim cùng → KHÔNG re-embed.
- CLAUDE.md section 3 — embedding dim PIN 1536, refuse cross-dim swap (R7).
"""
from __future__ import annotations

import logging
from typing import Any

import litellm

from app.config import get_settings

logger = logging.getLogger(__name__)

#: PIN dimension cho mọi provider (R1 mitigation).
EMBEDDING_DIM: int = 1536


class EmbedderError(Exception):
    """LiteLLM call fail hoặc response shape sai.

    Plan 04-03 cocoindex flow catch exception này → set
    document.status='failed' + lưu error_message.
    """


async def embed_text(text: str, model: str | None = None) -> list[float]:
    """Embed 1 text → vector dim 1536.

    Args:
        text: nội dung chunk (UTF-8 string, < 8000 char để < 8000 token cho mọi tokenizer).
        model: override model name (default settings.rag_embedding_model).
               Plan 07 ASK-04 dùng arg này để hot-swap test provider.

    Returns:
        list[float] length EMBEDDING_DIM (1536).

    Raises:
        EmbedderError: LiteLLM exception, response thiếu data, hoặc dim sai.
        ValueError: text rỗng / chỉ whitespace.
    """
    if not text or not text.strip():
        raise ValueError("text rỗng — không embed được")

    settings = get_settings()
    model_name = model or settings.rag_embedding_model

    try:
        response: Any = await litellm.aembedding(
            model=model_name,
            input=[text],
            dimensions=EMBEDDING_DIM,
        )
    except Exception as e:  # noqa: BLE001 — wrap mọi LiteLLM exception
        logger.error("litellm_embed_failed: model=%s err=%s", model_name, e)
        raise EmbedderError(f"LiteLLM embed fail: {e}") from e

    return _extract_vector(response)


def _extract_vector(response: Any) -> list[float]:
    """Parse LiteLLM response → vector list[float] dim EMBEDDING_DIM.

    LiteLLM 1.82+ response: response.data = [{"embedding": [...], "index": 0}]
    hoặc response.data = [obj.embedding] cho 1 số provider.

    Raises:
        EmbedderError: response thiếu data hoặc dim sai.
    """
    if not response or not getattr(response, "data", None):
        raise EmbedderError(f"LiteLLM response thiếu data: {response!r}")

    first = response.data[0]
    vector_raw = first.get("embedding") if isinstance(first, dict) else first.embedding
    if not isinstance(vector_raw, list) or len(vector_raw) != EMBEDDING_DIM:
        actual = len(vector_raw) if isinstance(vector_raw, list) else type(vector_raw)
        raise EmbedderError(
            f"Vector dim sai: expected {EMBEDDING_DIM}, got {actual}"
        )
    return [float(x) for x in vector_raw]
