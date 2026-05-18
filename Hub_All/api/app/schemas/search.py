"""Search schemas — Pydantic v2 contract Phase 6.

D6 contract: shape khớp `frontend/src/services/api.ts` (`SearchRequestAPI`,
`SearchResultAPI`, `SearchResponseAPI`, `SimilarResponseAPI`) 1:1 — đổi tên field
sẽ break frontend (KHÔNG sửa React M2).

Lưu ý chốt:
- D-02: request body field tên `query` (KHÔNG `q`).
- D-10: `category`/`tags` schema M2 chưa có nguồn data → luôn `None`/`[]`;
  `source` hằng `"document"`; `raw_similarity == score` (M2 chưa rerank).
- D-14: `filters.categories`/`tags`/`date_*` accept-but-noop ở M2.
"""
from __future__ import annotations

from pydantic import BaseModel


class SearchFilters(BaseModel):
    """Filter object trong `SearchRequestAPI.filters` (api.ts:495).

    D-14: `categories`/`tags` accept-but-noop M2 (parse OK, không filter).
    """

    categories: list[str] | None = None
    tags: list[str] | None = None
    date_from: str | None = None
    date_to: str | None = None


class SearchRequest(BaseModel):
    """Body POST /api/search + /api/search/cross-hub — = `SearchRequestAPI`."""

    query: str  # D-02 — field tên `query` KHÔNG `q`
    hub_ids: list[str] | None = None
    top_k: int | None = None
    min_score: float | None = None
    filters: SearchFilters | None = None


class SimilarRequest(BaseModel):
    """Body POST /api/search/similar — `findSimilar()` frontend."""

    content: str
    hub_id: str | None = None
    threshold: float | None = None


class SearchResultItem(BaseModel):
    """1 kết quả search — = `SearchResultAPI` (api.ts:498)."""

    id: str
    hub_id: str
    hub_name: str
    title: str
    snippet: str
    content: str | None = None
    category: str | None = None  # D-10 — M2 luôn None
    tags: list[str] = []  # D-10 — M2 luôn []
    score: float
    raw_similarity: float  # D-10 — = score (M2 chưa rerank)
    updated_at: str | None = None
    source: str  # D-10 — hằng "document"


class SearchResponse(BaseModel):
    """Response POST /api/search + /api/search/cross-hub — = `SearchResponseAPI`."""

    results: list[SearchResultItem]
    total_hubs_searched: int
    query_time_ms: int
    cache_hit: bool


class SimilarMatch(BaseModel):
    """1 match trong `SimilarResponseAPI.matches` (api.ts:521)."""

    page_id: str
    page_title: str
    similarity_score: float
    hub_name: str


class SimilarResponse(BaseModel):
    """Response POST /api/search/similar — = `SimilarResponseAPI`."""

    matches: list[SimilarMatch]
