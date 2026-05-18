"""File extract service — Plan 04-02 Task 01 (INGEST-02 prerequisite).

Hỗ trợ 4 format whitelist (R4 mitigation): DOCX, TXT, MD, PDF text-only.
KHÔNG OCR (D4 — defer v4.0). Scanned PDF → is_scanned=True (R4 mitigation).

Public API ổn định cho:
- Plan 04-03 cocoindex flow wrap thành cocoindex.op.function (extract step).
- Plan 04-04 router /api/documents/upload import detect_scanned_pdf để reject 415
  TRƯỚC KHI queue ingest job (BLOCKER #3 strategy A — router-side sync detection).

Quy tắc xử lý theo extension:

| Extension     | Library                | Output            | is_scanned                  |
|---------------|------------------------|-------------------|-----------------------------|
| .docx         | python-docx Document() | paragraph + bảng  | False luôn                  |
| .txt, .md     | open + chardet detect  | full text         | False luôn                  |
| .pdf          | pypdf PdfReader        | pages join \n     | True nếu > 80% page < 30 ký |

Tham chiếu:
- PITFALLS P5 — Scanned PDF silent fail (HIGH).
- PROJECT.md R4 — whitelist `{.docx, .txt, .md, .pdf}` + enum `failed_unsupported`.
- CLAUDE.md section 3 — format hỗ trợ M2.
"""
from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import chardet
from docx import Document as DocxDocument
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph
from pypdf import PdfReader

#: Whitelist extension hỗ trợ M2 — KHÔNG đổi giữa phase (R4 mitigation).
ALLOWED_EXTENSIONS: frozenset[str] = frozenset({".docx", ".txt", ".md", ".pdf"})

#: Threshold heuristic detect scanned PDF (P5 / R4):
#: page có < 30 ký tự non-whitespace coi là "không có text"; > 80% page như vậy
#: → toàn document scanned. 30 ký tự cover edge case "Trang 1" + page number.
_SCANNED_PAGE_CHAR_THRESHOLD: int = 30
_SCANNED_RATIO_THRESHOLD: float = 0.8


class UnsupportedFormatError(Exception):
    """Raise khi extension không nằm trong ALLOWED_EXTENSIONS.

    Plan 04-04 router catch exception này → trả 415 Unsupported Media Type
    với message tiếng Việt khuyến nghị format thay thế.
    """

    def __init__(self, ext: str) -> None:
        super().__init__(
            f"Định dạng {ext!r} không hỗ trợ trong M2. "
            f"Khuyến nghị: chuyển sang một trong {sorted(ALLOWED_EXTENSIONS)}."
        )
        self.ext = ext


def extract_text(file_path: Path) -> tuple[str, bool, dict[str, Any]]:
    """Extract text + scanned-detect + metadata từ 1 file.

    Args:
        file_path: Path tuyệt đối hoặc tương đối đến file.

    Returns:
        text: str — full text extracted (\\n separator giữa pages/paragraphs).
        is_scanned: bool — True nếu PDF scanned (heuristic > 80% page < 30 ký tự).
        metadata: dict — {pages: int, format: str, encoding: str, ...}.

    Raises:
        UnsupportedFormatError: ext không trong ALLOWED_EXTENSIONS.
        FileNotFoundError: file không tồn tại.
    """
    if not file_path.exists():
        raise FileNotFoundError(f"File không tồn tại: {file_path}")
    ext = file_path.suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise UnsupportedFormatError(ext)

    if ext == ".docx":
        return _extract_docx(file_path)
    if ext in (".txt", ".md"):
        return _extract_text_file(file_path, ext)
    if ext == ".pdf":
        return _extract_pdf(file_path)
    # Defensive — không reach do guard ALLOWED_EXTENSIONS phía trên.
    raise UnsupportedFormatError(ext)


def detect_scanned_pdf(file_path: Path) -> bool:
    """Public wrapper cho heuristic _is_pdf_scanned.

    Plan 04-04 BLOCKER #3 mitigation: router import detect_scanned_pdf để
    reject scanned PDF SYNCHRONOUSLY trước khi queue cocoindex flow
    (tránh persist document status='processing' rồi flow fail muộn).

    Args:
        file_path: Path tới PDF file.

    Returns:
        True nếu PDF scanned (> 80% page < 30 ký tự text).
        False nếu PDF text-only hoặc file không có page nào (defensive False).

    Raises:
        FileNotFoundError: file không tồn tại.
        UnsupportedFormatError: file không phải .pdf.
    """
    if not file_path.exists():
        raise FileNotFoundError(f"File không tồn tại: {file_path}")
    if file_path.suffix.lower() != ".pdf":
        raise UnsupportedFormatError(file_path.suffix.lower())
    reader = PdfReader(str(file_path))
    return _is_pdf_scanned(reader)


def _iter_block_items(parent: Any) -> Iterator[Paragraph | Table]:
    """Yield Paragraph / Table theo đúng thứ tự xuất hiện trong document body.

    python-docx KHÔNG expose thứ tự xen kẽ paragraph↔table sẵn — phải duyệt
    XML `<w:body>` children. Cần thiết để "tái hiện trung thực cấu trúc"
    (core value M2): tài liệu nội bộ Medinet thường xen kẽ đoạn văn + bảng.
    """
    body = parent.element.body
    for child in body.iterchildren():
        if child.tag == qn("w:p"):
            yield Paragraph(child, parent)
        elif child.tag == qn("w:tbl"):
            yield Table(child, parent)


def _table_to_text(table: Table) -> str:
    """Table → text: mỗi hàng = các ô join ' | ', các hàng join '\\n'.

    Đệ quy vào bảng lồng trong ô (`_Cell.text` KHÔNG bao gồm bảng lồng). Ô
    gộp (merged cell) lặp text — chấp nhận, đa số bảng layout tài liệu Medinet
    là 1×1 / không gộp.
    """
    lines: list[str] = []
    for row in table.rows:
        cells: list[str] = []
        for cell in row.cells:
            cell_text = cell.text.strip()
            for nested in cell.tables:  # bảng lồng — gom thêm
                nested_text = _table_to_text(nested)
                if nested_text:
                    cell_text = f"{cell_text}\n{nested_text}".strip()
            if cell_text:
                cells.append(cell_text)
        line = " | ".join(cells)
        if line.strip():
            lines.append(line)
    return "\n".join(lines)


def _header_footer_parts(doc: Any) -> list[str]:
    """Text header/footer mọi section — dedupe nội bộ (header lặp mỗi section)."""
    seen: set[str] = set()
    parts: list[str] = []
    for section in doc.sections:
        for hf in (section.header, section.footer):
            for para in hf.paragraphs:
                t = para.text.strip()
                if t and t not in seen:
                    seen.add(t)
                    parts.append(t)
            for tbl in hf.tables:
                t = _table_to_text(tbl)
                if t and t not in seen:
                    seen.add(t)
                    parts.append(t)
    return parts


def _extract_docx(file_path: Path) -> tuple[str, bool, dict[str, Any]]:
    """Extract DOCX qua python-docx — duyệt body theo đúng thứ tự tài liệu.

    Đọc paragraph + table cell (gồm bảng lồng) theo thứ tự xuất hiện, cộng
    header/footer (dedupe vì lặp mỗi section). Tài liệu nội bộ Medinet thường
    dựng layout bằng bảng → bỏ bảng = mất nội dung (core value M2 yêu cầu tái
    hiện "bảng").
    """
    doc = DocxDocument(str(file_path))

    parts: list[str] = []
    paragraph_count = 0
    table_count = 0
    for block in _iter_block_items(doc):
        if isinstance(block, Table):
            table_count += 1
            block_text = _table_to_text(block)
            if block_text:
                parts.append(block_text)
        else:  # Paragraph
            para_text = block.text.strip()
            if para_text:
                paragraph_count += 1
                parts.append(para_text)

    parts.extend(_header_footer_parts(doc))
    text = "\n\n".join(parts)
    meta: dict[str, Any] = {
        "pages": 1,  # DOCX không có page count semantic — set 1 cho monotonic.
        "format": "docx",
        "encoding": "utf-8",
        "paragraph_count": paragraph_count,
        "table_count": table_count,
    }
    return text, False, meta


def _extract_text_file(file_path: Path, ext: str) -> tuple[str, bool, dict[str, Any]]:
    """Extract TXT/MD — UTF-8 trước, chardet fallback nếu fail."""
    raw = file_path.read_bytes()
    # Thử UTF-8 trước (case common cho VN medical doc trên web/docx-export).
    try:
        text = raw.decode("utf-8")
        encoding = "utf-8"
    except UnicodeDecodeError:
        # Fallback chardet detect (Windows-1258 / latin-1 / GB2312 / etc).
        detected = chardet.detect(raw)
        encoding = detected.get("encoding") or "latin-1"
        text = raw.decode(encoding, errors="replace")
    meta: dict[str, Any] = {
        "pages": 1,
        "format": ext.lstrip("."),
        "encoding": encoding,
    }
    return text, False, meta


def _extract_pdf(file_path: Path) -> tuple[str, bool, dict[str, Any]]:
    """Extract PDF qua pypdf text-only + scanned-detect heuristic."""
    reader = PdfReader(str(file_path))
    pages_text: list[str] = []
    for page in reader.pages:
        page_text = page.extract_text() or ""
        pages_text.append(page_text)
    text = "\n".join(pages_text)
    is_scanned = _is_pdf_scanned(reader)
    meta: dict[str, Any] = {
        "pages": len(reader.pages),
        "format": "pdf",
        "encoding": "utf-8",  # pypdf decode ra str unicode nội bộ.
    }
    return text, is_scanned, meta


def _is_pdf_scanned(reader: PdfReader) -> bool:
    """Heuristic: PDF scanned nếu > 80% page có < 30 ký tự text non-whitespace.

    pypdf trả empty/whitespace cho scanned PDF (R4 mitigation — gỡ Docling khỏi M2).
    Threshold 30 ký tự cover edge case "Trang 1" / page number tự render.

    Edge case: PDF 0 page → coi là scanned (defensive — Plan 04-04 sẽ trả 415
    với cùng error code `failed_unsupported`).
    """
    if len(reader.pages) == 0:
        return True
    empty_pages = 0
    for page in reader.pages:
        text = page.extract_text() or ""
        if len(text.strip()) < _SCANNED_PAGE_CHAR_THRESHOLD:
            empty_pages += 1
    return (empty_pages / len(reader.pages)) > _SCANNED_RATIO_THRESHOLD
