"""Unit test file_extract — Plan 04-02 Task 01 (INGEST-02 prerequisite).

Test pure Python — KHÔNG cần Postgres/Redis. Sample DOCX/TXT/PDF được
generate runtime trong tmp_path để tránh commit binary fixture vào git.

Coverage 7 case theo plan behavior matrix:
- DOCX VN có heading "Mục N." → text + is_scanned=False + meta.format=docx.
- TXT UTF-8 VN có dấu → text intact + encoding=utf-8.
- TXT non-UTF-8 (latin-1) → chardet fallback + decode.
- PDF text-only → is_scanned=False.
- PDF scanned (page text < 30 char) → is_scanned=True (R4 mitigation).
- Extension không thuộc whitelist → UnsupportedFormatError.
- File không tồn tại → FileNotFoundError.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from docx import Document as DocxDocument
from pypdf import PdfWriter

from app.services.file_extract import (
    ALLOWED_EXTENSIONS,
    UnsupportedFormatError,
    detect_scanned_pdf,
    extract_text,
)

# ---------- Fixtures ----------


@pytest.fixture
def docx_vn(tmp_path: Path) -> Path:
    """Tạo DOCX VN có 2 heading + 2 paragraph nội dung."""
    doc = DocxDocument()
    doc.add_paragraph("Mục 1. KHÁM TỔNG QUÁT")
    doc.add_paragraph("Bệnh nhân được khám lâm sàng đầy đủ.")
    doc.add_paragraph("Mục 2. XÉT NGHIỆM")
    doc.add_paragraph("Làm xét nghiệm máu và nước tiểu.")
    path = tmp_path / "khám-bệnh.docx"
    doc.save(str(path))
    return path


@pytest.fixture
def txt_utf8_vn(tmp_path: Path) -> Path:
    path = tmp_path / "khám-utf8.txt"
    path.write_text("Khám bệnh đa khoa\nLâm sàng tốt.", encoding="utf-8")
    return path


@pytest.fixture
def txt_latin1_vn(tmp_path: Path) -> Path:
    """TXT encode latin-1 — UTF-8 decode sẽ fail → chardet fallback."""
    path = tmp_path / "latin1.txt"
    # latin-1 byte sequence không phải UTF-8 valid (bytes 0xc0-0xff không follow UTF-8).
    path.write_bytes(b"H\xe0 N\xf4i\nL\xe1m s\xe0ng")  # "Hà Nội Lâm sàng" latin-1
    return path


@pytest.fixture
def pdf_text_only(tmp_path: Path) -> Path:
    """Tạo PDF có text-only — pypdf extract_text trả nội dung > 30 char/page.

    Dùng pypdf.PdfWriter.add_blank_page rồi annotate text — nhưng pypdf không
    có API thuận tiện tạo text PDF. Workaround: tạo PDF từ reportlab nếu có,
    hoặc tạo PDF tối giản từ raw bytes.

    Phương án đơn giản nhất: tạo PDF bằng pypdf merge từ existing template.
    Với plan này, để tránh thêm dependency reportlab, ta tạo PDF "minimal valid"
    với 1 page chứa 1 stream text qua dictionary direct.
    """
    # PDF tối thiểu hợp lệ (RFC PDF 1.4) với 1 page text "Khám bệnh đa khoa lâm sàng tốt"
    # Hand-crafted để đảm bảo pypdf parse được + extract_text trả > 30 char.
    pdf_bytes = (
        b"%PDF-1.4\n"
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj\n"
        b"4 0 obj << /Length 90 >> stream\n"
        b"BT\n/F1 12 Tf\n50 750 Td\n(Kham benh da khoa lam sang tot va day du noi dung text only) Tj\nET\n"
        b"endstream\nendobj\n"
        b"5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n"
        b"xref\n0 6\n0000000000 65535 f\n0000000009 00000 n\n0000000058 00000 n\n"
        b"0000000115 00000 n\n0000000232 00000 n\n0000000370 00000 n\n"
        b"trailer << /Size 6 /Root 1 0 R >>\n"
        b"startxref\n442\n%%EOF\n"
    )
    path = tmp_path / "text-only.pdf"
    path.write_bytes(pdf_bytes)
    return path


@pytest.fixture
def pdf_scanned(tmp_path: Path) -> Path:
    """Tạo PDF scanned — pypdf extract_text trả empty/garbage cho mọi page.

    Dùng pypdf.PdfWriter add_blank_page → page không có text content stream
    → extract_text() trả "" → is_scanned=True (heuristic > 80% page < 30 char).
    """
    writer = PdfWriter()
    for _ in range(5):
        writer.add_blank_page(width=612, height=792)
    path = tmp_path / "scanned.pdf"
    with path.open("wb") as f:
        writer.write(f)
    return path


# ---------- Tests ----------


def test_extract_docx_vietnamese(docx_vn: Path) -> None:
    """DOCX VN extract intact với heading + sentence."""
    text, is_scanned, meta = extract_text(docx_vn)
    assert "Mục 1. KHÁM TỔNG QUÁT" in text
    assert "Mục 2. XÉT NGHIỆM" in text
    assert "lâm sàng" in text
    assert is_scanned is False
    assert meta["format"] == "docx"
    assert meta["pages"] == 1
    assert meta["paragraph_count"] == 4


def test_extract_txt_utf8_vietnamese(txt_utf8_vn: Path) -> None:
    """TXT UTF-8 VN có dấu — intact."""
    text, is_scanned, meta = extract_text(txt_utf8_vn)
    assert "Khám bệnh" in text
    assert "Lâm sàng" in text
    assert is_scanned is False
    assert meta["format"] == "txt"
    assert meta["encoding"] == "utf-8"


def test_extract_txt_latin1_fallback(txt_latin1_vn: Path) -> None:
    """TXT non-UTF-8 → chardet fallback decode (latin-1 / Windows-1258)."""
    text, is_scanned, meta = extract_text(txt_latin1_vn)
    assert text  # KHÔNG empty
    assert is_scanned is False
    assert meta["format"] == "txt"
    # Encoding KHÔNG phải utf-8 — chardet detect được latin-1 hoặc tương đương.
    assert meta["encoding"] != "utf-8"


def test_extract_pdf_text_only(pdf_text_only: Path) -> None:
    """PDF text-only → is_scanned=False, pages > 0."""
    text, is_scanned, meta = extract_text(pdf_text_only)
    assert is_scanned is False, f"PDF text-only KHÔNG scanned. Got text: {text!r}"
    assert meta["pages"] >= 1
    assert meta["format"] == "pdf"


def test_extract_pdf_scanned_detected(pdf_scanned: Path) -> None:
    """PDF 5 page blank → > 80% page < 30 char → is_scanned=True (R4)."""
    text, is_scanned, meta = extract_text(pdf_scanned)
    assert is_scanned is True, (
        f"PDF blank PHẢI detect scanned. text={text!r} pages={meta['pages']}"
    )
    assert meta["pages"] == 5


def test_detect_scanned_pdf_public_api(pdf_scanned: Path, pdf_text_only: Path) -> None:
    """Public detect_scanned_pdf wrapper — Plan 04-04 BLOCKER #3 prerequisite.

    Router phải import detect_scanned_pdf SYNC để reject 415 sớm trước khi
    queue cocoindex flow.
    """
    assert detect_scanned_pdf(pdf_scanned) is True
    assert detect_scanned_pdf(pdf_text_only) is False


def test_extract_unsupported_extension(tmp_path: Path) -> None:
    """Extension .exe không trong whitelist → UnsupportedFormatError."""
    bad = tmp_path / "malware.exe"
    bad.write_bytes(b"MZ")
    with pytest.raises(UnsupportedFormatError) as exc:
        extract_text(bad)
    assert ".exe" in str(exc.value)
    assert exc.value.ext == ".exe"


def test_extract_file_not_found(tmp_path: Path) -> None:
    """File không tồn tại → FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        extract_text(tmp_path / "nope.docx")


def test_allowed_extensions_pinned() -> None:
    """Whitelist M2 cố định 4 ext (R4 mitigation)."""
    assert ALLOWED_EXTENSIONS == frozenset({".docx", ".txt", ".md", ".pdf"})


def test_extract_md_file(tmp_path: Path) -> None:
    """MD file extract như TXT — share code path."""
    path = tmp_path / "doc.md"
    path.write_text("# Khám bệnh\n\nNội dung markdown.", encoding="utf-8")
    text, is_scanned, meta = extract_text(path)
    assert "Khám bệnh" in text
    assert is_scanned is False
    assert meta["format"] == "md"
