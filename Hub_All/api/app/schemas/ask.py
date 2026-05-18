"""Ask schemas — Pydantic v2 contract Phase 7 (ASK-01).

Plan 07-01 — lớp "định nghĩa hợp đồng" cho Ask API. Plan 07-04 (AskService) +
router build dựa trên các model này, KHÔNG dò codebase.

D6 contract: Plan 07-04 router map `Citation` sang `CitationRefAPI`
(`frontend/src/services/api.ts`) — mọi field `Citation` đều cần cho việc map đó.

Lưu ý chốt (xem `<decisions>` Plan 07-01):
- D-07-01-A — marker citation `[N]` (số) — LLM sinh `[N]`, parser map `[N]`
  → `chunk_id`. `Citation` mang đồng thời `marker="[N]"` (literal ROADMAP SC1)
  VÀ `chunk_id`. Router 07-04 sẽ rewrite `[N]` → `[src:<id>]` cho frontend.
- D-07-01-B — `top_k` default 6, clamp [1, 12] (xử lý ở router 07-04).
"""
from __future__ import annotations

from pydantic import BaseModel


class AskRequest(BaseModel):
    """Body POST /api/ask + /api/ask/cross-hub.

    ASK-01: {q, hub_id, top_k?}. Field tên `query` (frontend `searchAnswer()`
    gửi `query`). `hub_id` single-hub; `hub_ids` cross-hub. Một trong hai phải
    có ở router layer (validate ở Plan 07-04).
    """

    query: str
    hub_id: str | None = None
    hub_ids: list[str] | None = None
    top_k: int | None = None


class Citation(BaseModel):
    """1 trích dẫn — marker [N] map về chunk_id (ASK-01).

    Mọi field cần cho việc map sang `CitationRefAPI` ở Plan 07-04 (D6).
    """

    number: int  # số thứ tự 1-based (= N trong marker [N])
    marker: str  # literal "[N]" trong answer (ROADMAP SC1)
    chunk_id: str
    document_id: str
    hub_id: str
    document_name: str
    hub_name: str
    score: float
    content_snippet: str


class AskResponse(BaseModel):
    """Response POST /api/ask — ASK-01 shape."""

    answer: str
    citations: list[Citation]
    model: str
    query_time_ms: int
