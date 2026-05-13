"""Serialize Docling output → response dict đúng schema DSVC-02.

Schema chốt trong CONTEXT.md mục "Schema response /v1/process".
Plan 06 (API endpoint) dùng và Phase 3 (Go adapter) deserialize — contract ĐÓNG BĂNG.

Trách nhiệm:
1. build_doc_meta(doc, filename, ocr_used) → dict doc_meta.
2. serialize_chunks(doc, chunks, tokenizer_name) → list dict đúng schema DSVC-02.
3. Detect is_table + extract table_html giữ rowspan/colspan (EXTRACT-03).
4. Inject caption figure dạng ![<caption>](#fig-N) vào text (EXTRACT-04).
5. Compute page_start/end + bbox union từ chunk.meta.doc_items[].prov.

Lưu ý version drift Docling 2.91:
- `headings` có thể nằm ở `chunk.meta.headings` hoặc `chunk.meta.headers` tùy build.
- bbox có thể là `BoundingBox` với `l/t/r/b` hoặc `x0/y0/x1/y1`.
- Code dùng `getattr` defensive để handle cả 2. Plan 07 (test) sẽ verify shape thực tế.
- Import Docling wrap trong try/except để smoke test không cần dep cài sẵn.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, TypedDict

import structlog

try:
    import tiktoken
except ImportError:  # pragma: no cover
    tiktoken = None  # type: ignore[assignment]

try:
    from docling_core.transforms.chunker import DocChunk  # type: ignore
    from docling_core.types.doc import DoclingDocument  # type: ignore
except ImportError:  # pragma: no cover
    # Cho phép import module trong môi trường chưa cài Docling (smoke test, lint).
    DocChunk = Any  # type: ignore[assignment,misc]
    DoclingDocument = Any  # type: ignore[assignment,misc]

logger = structlog.get_logger(__name__)


class DocMetaDict(TypedDict):
    """doc_meta dict đúng schema DSVC-02."""

    filename: str
    file_type: str
    page_count: int
    language_detected: str | None
    ocr_used: bool


class ChunkDict(TypedDict):
    """chunk dict đúng schema DSVC-02 — 10 field cố định."""

    chunk_index: int
    text: str
    headers: list[str]
    caption: str | None
    page_start: int | None
    page_end: int | None
    is_table: bool
    table_html: str | None
    bbox: list[float] | None
    token_count: int


def _file_type_from_ext(filename: str) -> str:
    """Suy ra file_type từ extension (pdf, docx, ...)."""
    ext = Path(filename).suffix.lower().lstrip(".")
    return ext or "unknown"


def build_doc_meta(
    doc: Any,
    filename: str,
    ocr_used: bool,
    language_detected: str | None = None,
) -> DocMetaDict:
    """Build doc_meta dict đúng schema DSVC-02.

    Args:
        doc: DoclingDocument đã extract xong.
        filename: tên file gốc (suy ra file_type).
        ocr_used: có dùng OCR không (extractor báo về).
        language_detected: best-effort, M1 có thể None (Docling không expose detect).
    """
    pages = getattr(doc, "pages", None)
    if pages is None:
        page_count = 0
    else:
        try:
            page_count = len(pages)
        except TypeError:
            page_count = 0

    return DocMetaDict(
        filename=filename,
        file_type=_file_type_from_ext(filename),
        page_count=page_count,
        language_detected=language_detected,
        ocr_used=ocr_used,
    )


def _extract_provenance(
    chunk: Any,
) -> tuple[int | None, int | None, list[float] | None]:
    """Lấy page_start, page_end, bbox (union) từ chunk.meta.doc_items[].prov.

    Returns:
        (page_start, page_end, bbox_union) — None nếu chunk không có prov.
    """
    pages: list[int] = []
    bboxes: list[tuple[float, float, float, float]] = []

    meta = getattr(chunk, "meta", None)
    items = getattr(meta, "doc_items", None) or []
    for item in items:
        prov_list = getattr(item, "prov", None) or []
        for prov in prov_list:
            page_no = getattr(prov, "page_no", None)
            if page_no is not None:
                try:
                    pages.append(int(page_no))
                except (TypeError, ValueError):
                    pass
            bbox = getattr(prov, "bbox", None)
            if bbox is not None:
                # bbox có shape l/t/r/b hoặc x0/y0/x1/y1 tùy version Docling
                try:
                    coords = (
                        float(getattr(bbox, "l", getattr(bbox, "x0", 0.0))),
                        float(getattr(bbox, "t", getattr(bbox, "y0", 0.0))),
                        float(getattr(bbox, "r", getattr(bbox, "x1", 0.0))),
                        float(getattr(bbox, "b", getattr(bbox, "y1", 0.0))),
                    )
                    bboxes.append(coords)
                except (TypeError, ValueError) as exc:
                    logger.warning("bbox_parse_fail", error=str(exc))

    page_start = min(pages) if pages else None
    page_end = max(pages) if pages else None

    if bboxes:
        # Union bbox: min(l,t), max(r,b) — đủ cho citation rendering ở UI.
        bbox_union: list[float] | None = [
            min(b[0] for b in bboxes),
            min(b[1] for b in bboxes),
            max(b[2] for b in bboxes),
            max(b[3] for b in bboxes),
        ]
    else:
        bbox_union = None

    return page_start, page_end, bbox_union


def _detect_table_html(doc: Any, chunk: Any) -> tuple[bool, str | None]:
    """Detect chunk có chứa table → trả (is_table, table_html).

    Logic: duyệt chunk.meta.doc_items, nếu có item label TABLE thì lấy
    item.export_to_html(doc=doc) (Docling 2.x TableItem có method này, giữ
    nguyên rowspan/colspan/<thead>/<tbody>).
    """
    meta = getattr(chunk, "meta", None)
    items = getattr(meta, "doc_items", None) or []
    for item in items:
        label_str = str(getattr(item, "label", "")).lower()
        if "table" in label_str:
            if hasattr(item, "export_to_html"):
                try:
                    html = item.export_to_html(doc=doc)
                except TypeError:
                    # Một số version không nhận arg `doc`
                    try:
                        html = item.export_to_html()
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("table_html_extract_fail", error=str(exc))
                        return True, None
                except Exception as exc:  # noqa: BLE001
                    logger.warning("table_html_extract_fail", error=str(exc))
                    return True, None
                if html:
                    return True, str(html)
                return True, None
            return True, None
    return False, None


def _extract_caption(chunk: Any) -> str | None:
    """Lấy caption đầu tiên trong chunk.meta.captions (EXTRACT-04)."""
    meta = getattr(chunk, "meta", None)
    captions = getattr(meta, "captions", None) or []
    if captions:
        return str(captions[0])
    return None


def _has_picture(chunk: Any) -> bool:
    """Chunk có chứa figure/picture item không."""
    meta = getattr(chunk, "meta", None)
    items = getattr(meta, "doc_items", None) or []
    return any("picture" in str(getattr(it, "label", "")).lower() for it in items)


def _inject_figure_caption_marker(text: str, caption: str | None, fig_index: int) -> str:
    """Inject ![caption](#fig-N) vào ĐẦU chunk text (EXTRACT-04).

    KHÔNG insert binary image — chỉ caption marker cho UI render anchor.
    """
    cap = caption or "figure"
    marker = f"![{cap}](#fig-{fig_index})"
    if text:
        return f"{marker}\n\n{text}"
    return marker


def _extract_headers(chunk: Any) -> list[str]:
    """Lấy heading path. Defensive cho cả `headings` lẫn `headers` field name."""
    meta = getattr(chunk, "meta", None)
    headers = getattr(meta, "headings", None)
    if not headers:
        headers = getattr(meta, "headers", None)
    return [str(h) for h in (headers or [])]


def _count_tokens(text: str, encoding: Any) -> int:
    """Đếm token, fallback len(text)//4 nếu tokenizer không khả dụng."""
    if encoding is not None:
        try:
            return len(encoding.encode(text))
        except Exception as exc:  # noqa: BLE001
            logger.warning("token_encode_fail", error=str(exc))
    return max(1, len(text) // 4)


def serialize_chunks(
    doc: Any,
    chunks: list[Any],
    tokenizer_name: str = "cl100k_base",
) -> list[ChunkDict]:
    """Map list DocChunk (output HybridChunker) → list ChunkDict đúng schema DSVC-02.

    Args:
        doc: DoclingDocument đã extract.
        chunks: list[DocChunk] từ HybridChunker.chunk(doc).
        tokenizer_name: tên encoding cho tiktoken (default cl100k_base — OpenAI 3-large).

    Returns:
        list[ChunkDict] — mỗi dict đúng 10 field schema DSVC-02.
    """
    encoding: Any = None
    if tiktoken is not None:
        try:
            encoding = tiktoken.get_encoding(tokenizer_name)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "tokenizer_load_fail_fallback_estimate",
                name=tokenizer_name,
                error=str(exc),
            )

    out: list[ChunkDict] = []
    fig_counter = 0

    for idx, ch in enumerate(chunks):
        page_start, page_end, bbox = _extract_provenance(ch)
        is_table, table_html = _detect_table_html(doc, ch)
        caption = _extract_caption(ch)

        text = getattr(ch, "text", "") or ""

        # Inject figure marker nếu chunk chứa picture (EXTRACT-04)
        if _has_picture(ch):
            fig_counter += 1
            text = _inject_figure_caption_marker(text, caption, fig_counter)

        token_count = _count_tokens(text, encoding)
        headers = _extract_headers(ch)

        out.append(
            ChunkDict(
                chunk_index=idx,
                text=text,
                headers=headers,
                caption=caption,
                page_start=page_start,
                page_end=page_end,
                is_table=is_table,
                table_html=table_html,
                bbox=bbox,
                token_count=token_count,
            )
        )

    return out


__all__ = [
    "ChunkDict",
    "DocMetaDict",
    "build_doc_meta",
    "serialize_chunks",
]
