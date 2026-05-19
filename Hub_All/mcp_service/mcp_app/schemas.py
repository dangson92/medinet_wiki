"""Pydantic output schema cho 3 tool MCP — port nguyên từ Phase 8.1.

6 model định nghĩa structured output cho 3 tool MCP:
- `AskAnswer` — output tool ask_wiki (answer giữ marker [N] + citations).
- `SearchResult` — output tool search_wiki.
- `HubList` — output tool list_hubs.

Port nguyên từ `api/app/mcp/schemas.py` (Phase 8.1) — giữ field + type chính xác để
MCP tool trả cùng shape dù MCP Service nay là process độc lập gọi API qua HTTP.
"""
from __future__ import annotations

from pydantic import BaseModel


class CitationItem(BaseModel):
    """Một trích dẫn trong câu trả lời của tool ask_wiki."""

    chunk_id: str
    document_name: str
    hub_name: str
    snippet: str
    score: float


class AskAnswer(BaseModel):
    """Output tool ask_wiki.

    `answer` giữ nguyên marker [N] — LLM client đọc trực tiếp.
    `citations` structured để client attribute nguồn.
    """

    answer: str
    citations: list[CitationItem]


class SearchResultItem(BaseModel):
    """Một chunk kết quả tìm kiếm từ tool search_wiki."""

    chunk_id: str
    content: str
    score: float
    document_name: str
    hub_name: str
    hub_id: str


class SearchResult(BaseModel):
    """Output tool search_wiki."""

    results: list[SearchResultItem]
    total: int


class HubItem(BaseModel):
    """Một Hub mà API key có quyền truy cập."""

    id: str
    name: str
    description: str | None = None


class HubList(BaseModel):
    """Output tool list_hubs."""

    hubs: list[HubItem]
