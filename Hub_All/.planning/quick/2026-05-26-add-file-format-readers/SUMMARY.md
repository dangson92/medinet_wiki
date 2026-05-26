---
title: Thêm thư viện đọc file gốc CSV / XLSX / PPTX / HTML
slug: add-file-format-readers
date: 2026-05-26
status: complete
---

# SUMMARY — Mở rộng `file_extract.py` đọc CSV / XLSX / PPTX / HTML

## Outcome

`ALLOWED_EXTENSIONS` mở rộng 4 → 8 format. User upload CSV/XLSX/PPTX/HTML qua frontend `DocumentIngestion` page hết bị 415 `UNSUPPORTED_FORMAT`. Frontend `accept=".pdf,.docx,.txt,.md,.xlsx,.pptx,.jpg,.png,.csv,.html"` ([DocumentIngestion.tsx:910](../../frontend/src/pages/DocumentIngestion.tsx#L910)) giờ đã được backend match (trừ `.jpg`/`.png` vẫn defer v4.0 cho OCR).

## Files changed (3)

| File | Change |
|------|--------|
| [api/pyproject.toml](../../api/pyproject.toml) | +4 dep (`openpyxl>=3.1,<4`, `python-pptx>=1.0,<2`, `beautifulsoup4>=4.12,<5`, `lxml>=5,<6`) + 4 mypy `ignore_missing_imports` override (openpyxl/pptx/bs4/lxml) |
| [api/app/services/file_extract.py](../../api/app/services/file_extract.py) | `ALLOWED_EXTENSIONS` 4 → 8 + dispatcher 4 branch mới + 5 hàm mới (`_decode_with_fallback` helper + `_extract_csv` + `_extract_xlsx` + `_extract_pptx` + `_extract_html`) |
| [api/tests/unit/test_file_extract.py](../../api/tests/unit/test_file_extract.py) | Update `test_allowed_extensions_pinned` assertion 8 ext + 5 fixture mới (`csv_vn` + `csv_excel_bom_semicolon` + `xlsx_two_sheets` + `pptx_three_slides` + `html_with_script`) + 6 test mới |

## Test results

- **17/17 PASS** `tests/unit/test_file_extract.py` (11 cũ + 6 mới): docx_vn, docx_tables, txt_utf8, txt_latin1, pdf_text_only, pdf_scanned_detected, detect_scanned_pdf_public_api, unsupported_extension, file_not_found, allowed_extensions_pinned, md_file, **csv_vietnamese, csv_excel_bom_semicolon, xlsx_two_sheets, pptx_three_slides, html_decompose_script_style, legacy_doc_still_rejected**.
- **495/495 PASS** full `tests/unit/` regression (KHÔNG break gì khác).
- **ruff check** clean (`app/services/file_extract.py` + `tests/unit/test_file_extract.py`).
- **mypy --strict** clean (`app/services/file_extract.py`).

## Implementation highlights

1. **`_decode_with_fallback` helper dùng chung CSV + HTML** — ưu tiên `utf-8-sig` codec stdlib (tự strip BOM), fallback chardet detect (Windows-1258 / latin-1 / etc).
2. **CSV `csv.Sniffer().sniff` auto-detect delimiter** trong `{',', ';', '\t', '|'}` — handle case CSV xuất từ Excel VN dùng `;`. Fallback `,` nếu sniff fail.
3. **XLSX `openpyxl` dùng `read_only=True, data_only=True`** — streaming parse memory-friendly + trả value công thức đã eval (KHÔNG formula string). Sheet header `--- Sheet: <name> ---` để chunker phân biệt biên sheet.
4. **PPTX duyệt `shape.has_text_frame`** — bỏ qua Picture/Chart/Table shape (defer v4.0). Slide header `--- Slide N ---` separator.
5. **HTML decompose `<script>` + `<style>` TRƯỚC `get_text`** — chống nội dung script/CSS lọt vào chunk + embedding (T-quick-html-01 mitigation). lxml parser cho HTML malformed (Word/PowerPoint export sai cấu trúc).

## Output text format consistency

Cả 4 format mới giữ pattern row/cell separator `" | "` (giống `_table_to_text` DOCX hiện hữu) → chunker `vn_chunker.chunk_vietnamese` downstream xử lý nhất quán, KHÔNG cần code path riêng.

## Commit

Atomic single commit — small scope quick task pattern. Touches `api/` chỉ (KHÔNG frontend, KHÔNG infra, KHÔNG planning historical files).

## Out of scope (defer v4.0)

- OCR cho `.jpg` / `.png` / scanned PDF → cần Tesseract VN model (D4 LOCKED M2).
- `.doc` legacy Word 97-2003 → user convert manual sang .docx (regression test `test_extract_legacy_doc_still_rejected` lock guard).
- `.odt` / `.ods` / `.rtf` → ít gặp ở docs nội bộ Medinet.
- Chunking strategy mới cho tabular data (CSV/XLSX hiện chunk như text dài) → defer khi observe quality eval.
- Cocoindex flow content-hash diff với 4 format mới — đã work natively vì `_extract_<format>` trả `(text, False, meta)` cùng signature như `extract_text` `docx/pdf/txt/md`.

## Reference

- Plan: [./PLAN.md](./PLAN.md)
- Frontend trigger: [frontend/src/pages/DocumentIngestion.tsx:910](../../frontend/src/pages/DocumentIngestion.tsx#L910)
- M2 D4 LOCKED: format hỗ trợ originally DOCX/TXT/MD/PDF text-only (CLAUDE.md §3) — quick task extend 4 format text-extractable mà KHÔNG vi phạm OCR ban (jpg/png/scanned PDF vẫn defer v4.0).
