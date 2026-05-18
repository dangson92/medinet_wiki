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


class EmbeddingCostPreview(BaseModel):
    """Cost preview khi swap embedding within dim 1536 (R7 / ASK-04).

    Service build nội dung rồi `.model_dump()` ghép vào response dict raw
    (giữ contract D6 — KHÔNG envelope). `message` LUÔN có 2 chữ số thập phân
    cho `est_cost_usd` (format `:.2f`) — khớp ROADMAP SC4 verbatim "$X.YZ".
    """

    n_chunks: int
    est_cost_usd: float
    est_minutes: int
    message: str  # "re-embed N chunks, est $X.YZ, est T phút" — cost LUÔN 2 chữ số
