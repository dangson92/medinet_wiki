---
title: Thêm thư viện đọc file gốc CSV / XLSX / PPTX / HTML
slug: add-file-format-readers
date: 2026-05-26
status: complete
---

# Quick task — Mở rộng `file_extract.py` đọc CSV / XLSX / PPTX / HTML

## Bối cảnh

Frontend `DocumentIngestion.tsx:910` đã advertise `accept=".pdf,.docx,.txt,.md,.xlsx,.pptx,.jpg,.png,.csv,.html"` nhưng backend `ALLOWED_EXTENSIONS = frozenset({".docx", ".txt", ".md", ".pdf"})` chỉ hỗ trợ 4 format. User upload xlsx/csv/pptx/html → 415 `UNSUPPORTED_FORMAT` envelope.

Đây là khoảng trống M2 D4 LOCKED ("DOCX/TXT/MD/PDF text-only") so với UI thực tế. Quick task này thu hẹp gap cho **4 format text-extractable**:

- `.csv` — stdlib `csv` (KHÔNG cần thư viện mới)
- `.xlsx` — `openpyxl` (pure Python, mature, MIT)
- `.pptx` — `python-pptx` (mature, MIT)
- `.html` — `beautifulsoup4` + `lxml` parser (mature, MIT)

**KHÔNG trong scope** (defer v4.0 OCR — D4 LOCKED):
- `.jpg` / `.png` — yêu cầu OCR Tesseract Vietnamese
- `.doc` cũ (Word 97-2003) — định dạng binary phức tạp; user convert sang `.docx`

## Touchpoints (3 file thay đổi)

1. **`api/pyproject.toml`** — thêm 3 dep vào `dependencies`:
   ```toml
   "openpyxl>=3.1,<4",
   "python-pptx>=1.0,<2",
   "beautifulsoup4>=4.12,<5",
   "lxml>=5,<6",  # bs4 parser nhanh + handle malformed HTML tốt hơn html.parser stdlib
   ```

2. **`api/app/services/file_extract.py`** — extend:
   - `ALLOWED_EXTENSIONS` thêm 4: `.csv`, `.xlsx`, `.pptx`, `.html`.
   - `extract_text` dispatcher thêm 4 branch.
   - 4 hàm extract mới: `_extract_csv`, `_extract_xlsx`, `_extract_pptx`, `_extract_html`.
   - Pattern: trả `(text, is_scanned=False, meta_dict)` — `is_scanned` luôn False cho 4 format này (KHÔNG có ảnh quét).
   - CSV: dùng `csv.reader` + chardet detect encoding fallback (case file CSV xuất từ Excel Windows-1258); mỗi row join ` | ` (giống `_table_to_text` DOCX pattern).
   - XLSX: `openpyxl.load_workbook(read_only=True, data_only=True)` — `data_only=True` trả value của công thức thay vì formula string; duyệt từng sheet → từng row → join ` | `; meta ghi `sheet_count`.
   - PPTX: duyệt slides → `shape.has_text_frame` → `text_frame.text`; nối với heading `--- Slide N ---`; meta ghi `slide_count`.
   - HTML: `BeautifulSoup(html, "lxml")` → `.get_text(separator="\n", strip=True)` — strip tag, giữ text content.

3. **`api/tests/unit/test_file_extract.py`** — thêm 4 fixture + 4 test:
   - `csv_simple` fixture: tạo CSV 3 cột × 5 row VN bằng `csv.writer`.
   - `xlsx_simple` fixture: tạo workbook 2 sheet bằng openpyxl.
   - `pptx_simple` fixture: tạo presentation 3 slide bằng python-pptx.
   - `html_simple` fixture: write file `.html` chuỗi `<html><body><h1>...</h1>...</body></html>`.
   - Mỗi test: gọi `extract_text(path)` → assert text chứa keyword + `is_scanned=False` + `meta["format"]` đúng.
   - Test 1 case mới `UnsupportedFormatError` thêm `.doc` (Word 97-2003 vẫn out of scope) để giữ guard regression.

## Pitfall + mitigation

1. **openpyxl `read_only=True` + công thức:** Nếu workbook có công thức `=SUM(A1:A10)` nhưng cell chưa eval (mới create chưa save từ Excel), `data_only=True` trả `None`. Heuristic: nếu cell.value là `None` skip; KHÔNG raise. Test fixture dùng giá trị string/number trực tiếp (KHÔNG có công thức) để khỏi đụng edge case này.

2. **PPTX shape không phải text:** Slide có thể chứa `Picture`, `Chart`, `Table` shapes. Quick task chỉ extract `shape.has_text_frame` (paragraph text). Table trong slide → defer (rare ở docs Medinet). Image → skip (D4 — OCR defer v4.0).

3. **HTML script/style tag:** `BeautifulSoup.get_text()` mặc định trả CẢ content của `<script>` + `<style>`. Cần `soup.find_all(['script', 'style'])` decompose trước khi `get_text()`. Test fixture cố tình thêm `<script>alert("xss")</script>` để verify nó bị strip.

4. **CSV encoding BOM:** File CSV export từ Excel Windows thường có BOM `﻿` đầu file. Dùng `codecs.BOM_UTF8` detect → strip trước khi pass cho `csv.reader`. Hoặc đơn giản hơn: `text = raw.decode("utf-8-sig", errors="replace")` — `utf-8-sig` codec tự động strip BOM.

5. **CSV delimiter heuristic:** File CSV VN có thể dùng `;` (locale châu Âu/VN Excel) thay `,`. Dùng `csv.Sniffer().sniff(sample, delimiters=",;\t|")` để auto-detect; fallback `,` nếu sniff fail.

6. **lxml dep weight:** lxml là native C ext (libxml2/libxslt) — adds binary wheel ~3MB nhưng cực nhanh + parse HTML malformed (Word/Powerpoint export HTML messy). Acceptable.

## Acceptance criteria

- [ ] `pyproject.toml` thêm 4 dep (openpyxl + python-pptx + beautifulsoup4 + lxml).
- [ ] `ALLOWED_EXTENSIONS` extend từ 4 → 8 format.
- [ ] `extract_text(<.csv>)` trả text + meta.format=csv.
- [ ] `extract_text(<.xlsx>)` trả text join các sheet + meta.format=xlsx + meta.sheet_count.
- [ ] `extract_text(<.pptx>)` trả text các slide + meta.format=pptx + meta.slide_count.
- [ ] `extract_text(<.html>)` trả text strip tag + script/style bị decompose + meta.format=html.
- [ ] 4 unit test mới PASS.
- [ ] Regression: 7 test cũ PASS (KHÔNG break docx/txt/md/pdf).
- [ ] `uv run ruff check app/services/file_extract.py` clean.
- [ ] `uv run mypy --strict app/services/file_extract.py` clean (hoặc add to ignore_missing_imports nếu lib chưa có stub).

## Test command

```bash
uv sync  # install 4 new deps
uv run pytest tests/unit/test_file_extract.py -v
uv run ruff check app/services/file_extract.py
uv run mypy --strict app/services/file_extract.py
```

## Out of scope (defer v4.0)

- OCR cho `.jpg` / `.png` / scanned PDF → cần Tesseract VN model (D4 LOCKED M2).
- `.doc` legacy Word 97-2003 → user convert manual sang .docx.
- `.odt` / `.ods` OpenDocument → ít gặp ở docs nội bộ Medinet.
- `.rtf` Rich Text Format → ít gặp.
- Chunking strategy mới cho CSV/XLSX (currently chunked như text dài) → defer khi observe quality eval.
- Frontend update accept attribute hiện tại đã cover sẵn → KHÔNG cần touch.
