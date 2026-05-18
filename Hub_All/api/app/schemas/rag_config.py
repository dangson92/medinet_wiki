"""RAG config schema — port request body Go PUT /api/rag-config (ASK-04).

Mọi field optional: PUT là partial update — chỉ field gửi lên (non-None /
non-empty) mới được persist. `clear_*` flag xoá key đã lưu.
"""
from __future__ import annotations

from pydantic import BaseModel


class UpdateRagConfigRequest(BaseModel):
    """Body PUT /api/rag-config — khớp `saveRAGConfig()` frontend Settings.tsx."""

    embedding_provider: str | None = None
    embedding_model: str | None = None
    chunk_size: int | None = None
    chunk_overlap: int | None = None
    batch_size: int | None = None
    gemini_api_key: str | None = None
    openai_api_key: str | None = None
    llm_provider: str | None = None
    gemini_llm_model: str | None = None
    clear_gemini_key: bool = False
    clear_openai_key: bool = False
