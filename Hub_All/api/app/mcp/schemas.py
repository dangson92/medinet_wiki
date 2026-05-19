"""MCP output schemas — Phase 8.1 (MCP-02).

Pydantic models định nghĩa structured output cho 3 tool MCP:
- `AskAnswer` — output tool ask_wiki (D-11: answer giữ marker [N] + citations structured)
- `SearchResult` — output tool search_wiki
- `HubList` — output tool list_hubs

FastMCP tự generate `structuredContent` + `outputSchema` từ return type Pydantic model
(RESEARCH.md Pattern 3 — KHÔNG viết JSON Schema tay).
"""
from __future__ import annotations

from pydantic import BaseModel


class CitationItem(BaseModel):
    """1 trích dẫn trong câu trả lời ask_wiki (D-11)."""

    chunk_id: str
    document_name: str
    hub_name: str
    snippet: str
    score: float


class AskAnswer(BaseModel):
    """Output tool ask_wiki (D-11).

    `answer` giữ nguyên marker [N] — LLM client đọc trực tiếp.
    `citations` structured để client attribute nguồn.
    """

    answer: str
    citations: list[CitationItem]


class SearchResultItem(BaseModel):
    """1 chunk kết quả tìm kiếm từ search_wiki."""

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
    """1 Hub mà API key có quyền truy cập."""

    id: str
    name: str
    description: str | None = None


class HubList(BaseModel):
    """Output tool list_hubs (D-07)."""

    hubs: list[HubItem]
