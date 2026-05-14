"""Vietnamese chunker — Plan 04-02 Task 02 (INGEST-02 prerequisite).

Char-based (P14 cross-provider — OpenAI cl100k_base ≠ Gemini BPE → KHÔNG token-based).
Custom regex VN heading + sentence boundary (P13 mitigation):

- Heading patterns:
  - "Mục N." (N = số nguyên) — y tế VN dùng phổ biến.
  - "Chương N." — phần lớn tài liệu cấu trúc cao.
  - "1.", "2." (numeric only) — danh sách lớn.
  - "I.", "II." (Roman) — đề mục cổ điển.
  Tất cả phải kèm VN/ASCII caps liền kề để tránh false positive (vd "1. abc" KHÔNG match).
- Sentence boundary: "." + whitespace + VN caps follow.

Lý do KHÔNG dùng cocoindex RecursiveSplitter built-in language='vietnamese':
- Cocoindex 1.0.3 KHÔNG có language Vietnamese — fallback default chunker split sai
  trên "Mục N." pattern (treat như sentence end).
- Custom regex pass vào RecursiveSplitter `separators_regex` parameter — Plan 04-03
  wrap chunker này thành cocoindex.op.function để flow gọi.

Tham chiếu:
- PITFALLS P13 — Vietnamese chunking boundary (HIGH).
- PITFALLS P14 — tokenizer cross-provider (MEDIUM).
- PROJECT.md R1/R7 — char-based để hot-swap embedding provider không rebuild chunk.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# VN caps + ASCII caps (heading first char follow phải là chữ in hoa).
_VN_CAPS = (
    r"A-Z"
    r"ĐÁÀẢÃẠÂẦẤẨẪẬĂẰẮẲẴẶ"
    r"ÔỒỐỔỖỘƠỜỚỞỠỢ"
    r"ƯỪỨỬỮỰÊỀẾỂỄỆ"
    r"ÍÌỈĨỊÚÙỦŨỤÝỲỶỸỴ"
    r"ÉÈẺẼẸÓÒỎÕỌ"
)

#: Heading patterns — bắt đầu dòng (multiline) + heading marker + caps follow.
#: Mỗi pattern capture group "h" để extract heading text cho heading_path.
HEADING_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(rf"(?m)^(?P<h>Chương\s+\d+\.\s*)[\s{_VN_CAPS}]"),
    re.compile(rf"(?m)^(?P<h>Mục\s+\d+\.\s*)[\s{_VN_CAPS}]"),
    re.compile(rf"(?m)^(?P<h>\d+\.\s+)[{_VN_CAPS}]"),
    re.compile(rf"(?m)^(?P<h>[IVX]+\.\s+)[{_VN_CAPS}]"),
)

#: Sentence boundary — "." + whitespace + VN caps follow.
SENTENCE_BOUNDARY = re.compile(rf"\.\s+(?=[{_VN_CAPS}])")


@dataclass(frozen=True)
class ChunkDraft:
    """Output chunker — Plan 04-03 sẽ map thành cocoindex chunks table row.

    Frozen=True cho immutable — test assertion equality + hash-able cho dedup.
    """

    content: str
    heading_path: str | None
    page_start: int
    page_end: int


def chunk_vietnamese(
    text: str,
    chunk_size_chars: int = 1200,
    overlap_chars: int = 120,
) -> list[ChunkDraft]:
    """Split text VN theo heading + sentence boundary. Char-based size.

    Args:
        text: input text từ extract_text.
        chunk_size_chars: target size mỗi chunk (default 1200 char ≈ 300 token VN).
        overlap_chars: số ký tự overlap giữa chunk consecutive để giữ ngữ cảnh
                       cho retrieval (default 120 = 10% chunk_size).

    Returns:
        list[ChunkDraft] — empty nếu text rỗng.

    Raises:
        ValueError: chunk_size_chars < 100 hoặc overlap >= chunk_size.
    """
    if not text or not text.strip():
        return []
    _validate_args(chunk_size_chars, overlap_chars)

    headings = _find_headings(text)
    segments = _build_segments(text, headings)

    # Step 3: trong mỗi segment, nếu > chunk_size_chars thì split theo sentence
    # boundary với greedy bundling.
    chunks: list[ChunkDraft] = []
    for seg_content, heading_path, seg_offset in segments:
        if not seg_content.strip():
            continue
        if len(seg_content) <= chunk_size_chars:
            chunks.append(
                ChunkDraft(
                    content=seg_content.strip(),
                    heading_path=heading_path,
                    page_start=_page_at(text, seg_offset),
                    page_end=_page_at(text, seg_offset + len(seg_content) - 1),
                )
            )
            continue
        # Greedy bundle sentence cho đến chunk_size_chars.
        chunks.extend(
            _split_segment(
                seg_content,
                heading_path,
                seg_offset,
                text,
                chunk_size_chars,
                overlap_chars,
            )
        )

    return chunks


def _validate_args(chunk_size_chars: int, overlap_chars: int) -> None:
    """Guard arg config — fail-fast trước khi chạy regex."""
    if chunk_size_chars < 100:
        raise ValueError(
            f"chunk_size_chars phải >= 100 (got {chunk_size_chars}) — "
            "size quá nhỏ → chunk vô nghĩa cho retrieval."
        )
    if overlap_chars < 0 or overlap_chars >= chunk_size_chars:
        raise ValueError(
            f"overlap_chars phải 0 <= overlap < chunk_size_chars "
            f"(got overlap={overlap_chars}, chunk_size={chunk_size_chars})."
        )


def _find_headings(text: str) -> list[tuple[int, str]]:
    """Tìm vị trí + text của mọi heading marker, dedup, sort theo offset."""
    headings: list[tuple[int, str]] = []
    for pat in HEADING_PATTERNS:
        for m in pat.finditer(text):
            headings.append((m.start(), m.group("h").strip()))
    headings.sort(key=lambda x: x[0])
    return _dedup_headings(headings)


def _build_segments(
    text: str, headings: list[tuple[int, str]]
) -> list[tuple[str, str | None, int]]:
    """Split text thành segments theo heading boundary.

    Returns:
        list[(seg_content, heading_path, seg_offset_trong_text)].
    """
    segments: list[tuple[str, str | None, int]] = []
    if not headings:
        segments.append((text, None, 0))
        return segments
    # Pre-content trước heading đầu tiên (nếu có).
    if headings[0][0] > 0:
        pre = text[: headings[0][0]]
        if pre.strip():
            segments.append((pre, None, 0))
    for i, (offset, heading) in enumerate(headings):
        end = headings[i + 1][0] if i + 1 < len(headings) else len(text)
        segments.append((text[offset:end], heading, offset))
    return segments


def _dedup_headings(
    headings: list[tuple[int, str]],
) -> list[tuple[int, str]]:
    """Khi 2+ pattern match cùng vị trí, giữ heading dài nhất (specific nhất)."""
    if not headings:
        return headings
    by_offset: dict[int, str] = {}
    for offset, h in headings:
        existing = by_offset.get(offset)
        if existing is None or len(h) > len(existing):
            by_offset[offset] = h
    return sorted(by_offset.items())


def _split_segment(
    seg_content: str,
    heading_path: str | None,
    seg_offset: int,
    full_text: str,
    chunk_size_chars: int,
    overlap_chars: int,
) -> list[ChunkDraft]:
    """Greedy bundle sentence trong segment > chunk_size_chars."""
    sentences = SENTENCE_BOUNDARY.split(seg_content)
    out: list[ChunkDraft] = []
    buffer = ""
    for sent in sentences:
        sent = sent.strip()
        if not sent:
            continue
        # +2 cho ". " separator giữa sentence.
        candidate_len = len(buffer) + len(sent) + 2
        if candidate_len > chunk_size_chars and buffer:
            out.append(
                ChunkDraft(
                    content=buffer.strip(),
                    heading_path=heading_path,
                    page_start=_page_at(full_text, seg_offset),
                    page_end=_page_at(full_text, seg_offset + len(buffer)),
                )
            )
            # Overlap: lấy `overlap_chars` cuối buffer làm prefix cho chunk kế.
            buffer = (buffer[-overlap_chars:] + " " + sent) if overlap_chars else sent
        else:
            buffer = (buffer + ". " + sent) if buffer else sent
    if buffer.strip():
        out.append(
            ChunkDraft(
                content=buffer.strip(),
                heading_path=heading_path,
                page_start=_page_at(full_text, seg_offset),
                page_end=_page_at(full_text, seg_offset + len(buffer)),
            )
        )
    return out


def _page_at(full_text: str, offset: int) -> int:
    """Đếm form-feed `\\f` (pypdf insert giữa pages) trước offset → page 1-based."""
    if offset < 0:
        return 1
    return full_text[:offset].count("\f") + 1
