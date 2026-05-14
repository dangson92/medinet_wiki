"""Unit test vn_chunker — Plan 04-02 Task 02 (INGEST-02 prerequisite).

Char-based chunker (P14 cross-provider) custom regex VN heading + sentence boundary
(P13 mitigation). Test 8 case theo plan behavior.
"""
from __future__ import annotations

import pytest

from app.services.vn_chunker import ChunkDraft, chunk_vietnamese


def test_chunk_vietnamese_mucn_heading() -> None:
    """Split theo 'Mục N.' heading — mỗi heading riêng 1 segment."""
    text = (
        "Mục 1. KHÁM TỔNG QUÁT\nBN khám lâm sàng.\n\n"
        "Mục 2. XÉT NGHIỆM\nXét nghiệm máu."
    )
    chunks = chunk_vietnamese(text)
    assert len(chunks) >= 2
    headings = [c.heading_path for c in chunks]
    assert any("Mục 1." in (h or "") for h in headings)
    assert any("Mục 2." in (h or "") for h in headings)


def test_chunk_vietnamese_chuong_heading() -> None:
    """Split theo 'Chương N.' heading."""
    text = (
        "Chương 1. GIỚI THIỆU\nNội dung chương 1.\n\n"
        "Chương 2. CHI TIẾT\nNội dung chi tiết của chương."
    )
    chunks = chunk_vietnamese(text)
    assert len(chunks) >= 2
    assert any("Chương 1." in (c.heading_path or "") for c in chunks)
    assert any("Chương 2." in (c.heading_path or "") for c in chunks)


def test_chunk_vietnamese_no_heading() -> None:
    """Text không heading → 1 chunk, heading_path=None."""
    text = "Đây là đoạn văn ngắn không có heading nào cả."
    chunks = chunk_vietnamese(text)
    assert len(chunks) == 1
    assert chunks[0].heading_path is None
    assert "không có heading" in chunks[0].content


def test_chunk_vietnamese_empty_returns_empty_list() -> None:
    """Empty / whitespace-only → []."""
    assert chunk_vietnamese("") == []
    assert chunk_vietnamese("   \n\n  ") == []


def test_chunk_vietnamese_chunk_size_too_small() -> None:
    """chunk_size < 100 → ValueError (guard against degenerate config)."""
    with pytest.raises(ValueError, match="chunk_size_chars"):
        chunk_vietnamese("text", chunk_size_chars=50)


def test_chunk_vietnamese_overlap_invalid() -> None:
    """overlap >= chunk_size → ValueError."""
    with pytest.raises(ValueError, match="overlap"):
        chunk_vietnamese("text" * 500, chunk_size_chars=200, overlap_chars=200)


def test_chunk_vietnamese_long_text_splits() -> None:
    """Text > chunk_size split thành nhiều chunk, cùng heading_path."""
    long_content = "Đây là một câu rất dài cần phải được chia nhỏ. " * 60  # ~2880 chars
    text = "Mục 1. INTRO\n" + long_content
    chunks = chunk_vietnamese(text, chunk_size_chars=600, overlap_chars=60)
    assert len(chunks) >= 3
    # Tất cả chunk phải có cùng heading_path 'Mục 1.'
    assert all((c.heading_path or "").startswith("Mục 1.") for c in chunks)
    # Mỗi chunk content KHÔNG vượt quá chunk_size_chars + overlap_chars buffer
    for c in chunks:
        assert len(c.content) <= 600 + 60 + 100  # +100 slack cho greedy bundle edge


def test_chunk_draft_immutable() -> None:
    """frozen=True dataclass — KHÔNG cho phép set attribute."""
    from dataclasses import FrozenInstanceError

    c = ChunkDraft(content="x", heading_path=None, page_start=1, page_end=1)
    with pytest.raises(FrozenInstanceError):
        c.content = "y"  # type: ignore[misc]


def test_chunk_vietnamese_numeric_heading() -> None:
    """Heading dạng '1.', '2.' + VN caps cũng split."""
    text = "1. KHÁM\nNội dung khám.\n\n2. ĐIỀU TRỊ\nNội dung điều trị."
    chunks = chunk_vietnamese(text)
    assert len(chunks) >= 2
    headings = [c.heading_path for c in chunks]
    assert any("1." in (h or "") for h in headings)
    assert any("2." in (h or "") for h in headings)


def test_chunk_vietnamese_preserves_vn_diacritics() -> None:
    """VN diacritics được preserve trong content."""
    text = "Mục 1. KHÁM\nBệnh nhân Đỗ Thị Hồng được điều trị thành công."
    chunks = chunk_vietnamese(text)
    assert len(chunks) >= 1
    full = " ".join(c.content for c in chunks)
    assert "Đỗ Thị Hồng" in full
    assert "điều trị" in full
