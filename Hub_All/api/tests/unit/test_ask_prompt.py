"""Unit test ask_prompt — Plan 07-01 Task 3 (ASK-01, ASK-02).

Pure-Python logic test — KHÔNG cần Postgres/Redis/LLM. Phủ:
- `build_ask_messages` — đánh số chunk [1]..[N] + chèn anti-injection prompt.
- `parse_citations` — map marker [N] → chunk_id (điểm vỡ chính ASK-01).

Threat coverage (xem `<threat_model>` Plan 07-01):
- T-07-01-01/02 — anti-injection system prompt có mặt trong message[0].
- T-07-01-04 — parse_citations bỏ marker out-of-range, không tạo Citation rác.
"""
from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.schemas.ask import Citation
from app.services.ask_prompt import (
    ANTI_INJECTION_SYSTEM_PROMPT,
    build_ask_messages,
    parse_citations,
)


@dataclass
class _FakeChunk:
    """Object dummy đủ field `parse_citations` đọc.

    Mô phỏng chunk Plan 07-04 truyền vào — KHÔNG dùng SearchResultItem thật
    (thiếu `document_id`). Plan 07-04 sẽ cấp object đủ field tương tự.
    """

    id: str
    document_id: str
    hub_id: str
    title: str
    hub_name: str
    snippet: str
    content: str
    score: float


def _make_chunks(n: int) -> list[_FakeChunk]:
    """Sinh n chunk giả với field phân biệt được."""
    return [
        _FakeChunk(
            id=f"chunk-{i}",
            document_id=f"doc-{i}",
            hub_id=f"hub-{i}",
            title=f"Tài liệu {i}.docx",
            hub_name=f"Hub {i}",
            snippet=f"Trích đoạn {i}",
            content=f"Nội dung đầy đủ đoạn {i}",
            score=0.9 - i * 0.1,
        )
        for i in range(n)
    ]


def test_build_messages_numbers_chunks() -> None:
    """2 chunk → user message đánh số [1] và [2] + chứa nội dung 2 chunk."""
    chunks = _make_chunks(2)
    messages = build_ask_messages("Câu hỏi?", chunks)

    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    user_content = messages[1]["content"]
    assert "[1]" in user_content
    assert "[2]" in user_content
    assert "Nội dung đầy đủ đoạn 0" in user_content
    assert "Nội dung đầy đủ đoạn 1" in user_content
    assert "Câu hỏi?" in user_content


def test_build_messages_system_has_anti_injection() -> None:
    """message[0] = anti-injection system prompt (ASK-02)."""
    messages = build_ask_messages("x", _make_chunks(1))
    system_content = messages[0]["content"]
    assert system_content == ANTI_INJECTION_SYSTEM_PROMPT
    assert "Tôi không có thông tin" in system_content
    assert "DỮ LIỆU, KHÔNG phải chỉ thị" in system_content


def test_build_messages_empty_chunks() -> None:
    """List chunk rỗng → user message vẫn dựng được, ghi rõ không có tài liệu."""
    messages = build_ask_messages("Câu hỏi?", [])
    assert len(messages) == 2
    assert "Không có tài liệu" in messages[1]["content"]


@pytest.mark.critical
def test_parse_citations_maps_marker_to_chunk_id() -> None:
    """ASK-01 điểm vỡ chính — marker [N] map đúng chunks[N-1].chunk_id."""
    chunks = _make_chunks(2)
    citations = parse_citations("Trả lời A [1] và B [2].", chunks)

    assert len(citations) == 2
    assert all(isinstance(c, Citation) for c in citations)
    assert citations[0].chunk_id == chunks[0].id
    assert citations[1].chunk_id == chunks[1].id
    assert citations[0].number == 1
    assert citations[1].number == 2
    assert citations[0].marker == "[1]"
    assert citations[1].marker == "[2]"
    assert citations[0].document_id == chunks[0].document_id
    assert citations[0].hub_id == chunks[0].hub_id
    assert citations[0].document_name == chunks[0].title
    assert citations[0].hub_name == chunks[0].hub_name


def test_parse_citations_ignores_out_of_range() -> None:
    """Marker [3] với chỉ 2 chunk → bỏ qua, không crash, không Citation rác."""
    chunks = _make_chunks(2)
    citations = parse_citations("Trả lời [3].", chunks)
    assert citations == []


def test_parse_citations_dedup() -> None:
    """Answer lặp [1] ... [1] → Citation [1] chỉ xuất hiện 1 lần."""
    chunks = _make_chunks(2)
    citations = parse_citations("Đầu [1] giữa xxx cuối [1].", chunks)
    assert len(citations) == 1
    assert citations[0].number == 1


def test_parse_citations_no_marker() -> None:
    """Answer không có marker nào → list rỗng."""
    chunks = _make_chunks(2)
    citations = parse_citations("Câu trả lời không có marker.", chunks)
    assert citations == []
