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
| .docx         | python-docx Document() | paragraphs join \n| False luôn                  |
| .txt, .md     | open + chardet detect  | full text         | False luôn                  |
| .pdf          | pypdf PdfReader        | pages join \n     | True nếu > 80% page < 30 ký |

Tham chiếu:
- PITFALLS P5 — Scanned PDF silent fail (HIGH).
- PROJECT.md R4 — whitelist `{.docx, .txt, .md, .pdf}` + enum `failed_unsupported`.
- CLAUDE.md section 3 — format hỗ trợ M2.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import chardet
from docx import Document as DocxDocument
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


def _extract_docx(file_path: Path) -> tuple[str, bool, dict[str, Any]]:
    """Extract DOCX qua python-docx — paragraphs join \\n, KHÔNG bảng (defer)."""
    doc = DocxDocument(str(file_path))
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    text = "\n".join(paragraphs)
    meta: dict[str, Any] = {
        "pages": 1,  # DOCX không có page count semantic — set 1 cho monotonic.
        "format": "docx",
        "encoding": "utf-8",
        "paragraph_count": len(paragraphs),
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
