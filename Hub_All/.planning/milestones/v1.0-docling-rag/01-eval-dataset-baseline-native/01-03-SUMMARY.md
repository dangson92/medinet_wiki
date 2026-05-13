---
phase: 01-eval-dataset-baseline-native
plan: 03
subsystem: eval
status: completed
tags: [eval, python, scanned-pdf, ocr-prep, docx2pdf, pymupdf, img2pdf]
requirements: [EVAL-01]
wave: 2
depends_on: [01]
provides:
  - "eval/scripts/build_scanned.py — pipeline DOCX → PDF text → PNG raster → PDF image-only, fallback chain 3 tầng cho Step A và 2 tầng cho Step B."
  - "eval/dataset/scanned/DMD_T1-01_scanned.pdf (21 page, 3.74 MB) — scanned từ DMD_T1-01_DinhVi_TrungTam_v1.docx, verified 0 ký tự text layer."
  - "eval/dataset/scanned/DMD_T1-04_scanned.pdf (31 page, 4.68 MB) — scanned từ DMD_T1-04_FAQ_ThuongHieu_v1.docx, verified 0 ký tự text layer."
  - "Reproducible recipe: rerun script ra output cùng nội dung (DPI 150 + img2pdf deterministic) — Phase 5 dùng cùng input."
key-files:
  created:
    - eval/scripts/build_scanned.py
    - eval/scripts/__init__.py
    - eval/dataset/scanned/DMD_T1-01_scanned.pdf
    - eval/dataset/scanned/DMD_T1-04_scanned.pdf
  modified: []
tech-stack:
  added: [docx2pdf, pymupdf, img2pdf, pdf2image, Pillow, pypdf]
  patterns:
    - "Fallback chain 3 tầng cho Step A (LibreOffice → docx2pdf → pandoc) — không phụ thuộc 1 tool duy nhất."
    - "Fallback Step B pdf2image (primary, cần Poppler) → pymupdf (pure-Python wheel) — Windows dev không phải cài Poppler."
    - "Verify invariant scanned PDF qua pypdf.PdfReader.extract_text() — assert < 50 ký tự non-whitespace."
    - "Exit code phân biệt root cause (0 OK, 1 build fail, 2 không converter, 3 text layer leak) — CI/orchestrator parse được."
    - "Output JSON 1 dòng cuối stdout cho orchestrator parse: {built: [...], verified_no_text_layer: true}."
decisions:
  - "Không dùng Git LFS — kích thước 2 PDF tổng < 9 MB, vẫn nằm trong ngưỡng commit thường (DPI 150 đủ thấp, page count vừa phải)."
  - "Thêm pymupdf làm fallback Step B (Rule 3 — blocking issue): Poppler không có sẵn trên Windows executor, pdf2image fail với `PDFInfoNotInstalledError`. PyMuPDF là pure-Python wheel — pip install xong là chạy được, đảm bảo Plan 01-03 build được runtime trên executor mà không phải cài Poppler thủ công."
  - "Cài thêm docx2pdf trong môi trường executor (Rule 3) để có converter Step A — LibreOffice không có; docx2pdf dùng MS Word automation đã cài sẵn trên Windows."
  - "Comment business logic bằng tiếng Việt (theo CLAUDE.md global rule); chỉ giữ tiếng Anh cho tên tool, lệnh shell, library name."
metrics:
  duration: "~10 phút"
  files_created: 4
  files_modified: 0
  loc_added: 400
  completed_date: "2026-04-28"
commit: "045d29b"
---

# Phase 1 Plan 03: build_scanned.py + 2 scanned PDF artifact — Summary

Pipeline tự động sinh 2 scanned PDF tiếng Việt từ DOCX gốc — giả lập input "scanned PDF" để verify gap của extractor Go hiện tại (`backend/internal/rag/extractor/pdf.go:52` trả `no text extracted`) và làm input cho Phase 2 Docling OCR `vie+eng`. Build runtime thành công trên executor: 21 page (T1-01) + 31 page (T1-04), cả 2 verified 0 ký tự text layer thực, JSON output cuối cùng `{"built":[...],"verified_no_text_layer":true}`.

## Tick list `must_haves` từ PLAN frontmatter

### `truths`

- [x] **Lệnh `python eval/scripts/build_scanned.py` tạo được 2 file PDF image-only từ 2 DOCX gốc.**
  Đã build runtime: `DMD_T1-01_scanned.pdf` (3.74 MB) + `DMD_T1-04_scanned.pdf` (4.68 MB). Step A dùng `docx2pdf`, Step B fallback `pymupdf`, Step C `img2pdf`.
- [x] **PDF output KHÔNG có text layer** — `pypdf.PdfReader.extract_text()` trả 0 ký tự non-whitespace cho cả 2 file. `pdftotext` (Git for Windows) trả empty cho T1-01; T1-04 trả 31 ký tự = đúng số form-feed `\f` page separator của 31 page (không phải text thực).
- [x] **Mỗi page PDF là raster image 150 DPI tối thiểu.** Tham số `--dpi 150` mặc định, áp dụng qua `pymupdf.Matrix(150/72, 150/72)` (hoặc `pdf2image.convert_from_path(..., dpi=150)` ở primary path).
- [x] **Script có fallback chain.** Step A: LibreOffice → docx2pdf → pandoc (3 tầng — bất kỳ tool nào available là chạy). Step B: pdf2image → pymupdf (2 tầng — đảm bảo Windows không Poppler vẫn rasterize được).
- [x] **Output files committed vào git** — commit `045d29b` chứa cả 2 file PDF (KHÔNG dùng Git LFS).
- [x] **Chạy script lần 2 trên cùng input → output bytes-identical HOẶC có flag `--force`.**
  - Test: chạy lại không `--force` → log `"đã tồn tại — skip"` và JSON chỉ liệt kê file thực sự (re)build. Đáp ứng vế "có flag `--force`".
  - Determinism bytes-identical hoàn toàn không bảo đảm vì pymupdf/img2pdf timestamp metadata có thể khác run; flag skip-if-exists đã đủ thay thế.

### `artifacts`

- [x] `eval/scripts/build_scanned.py` — 400 dòng (≥ 120 yêu cầu); pipeline đủ 3 step + verify_no_text_layer.
- [x] `eval/dataset/scanned/DMD_T1-01_scanned.pdf` — 21 page, 3,743,132 B, scanned từ DMD_T1-01_DinhVi_TrungTam_v1.docx.
- [x] `eval/dataset/scanned/DMD_T1-04_scanned.pdf` — 31 page, 4,680,276 B, scanned từ DMD_T1-04_FAQ_ThuongHieu_v1.docx.

### `key_links`

- [x] `eval/scripts/build_scanned.py` import `pdf2image.convert_from_path` (primary), `img2pdf.convert`, `PIL` (qua Pillow). Pattern `img2pdf\.convert` xuất hiện ở dòng 199 trong `images_to_image_pdf`.

## Files Created (4)

| # | Đường dẫn | Kích thước | Vai trò |
|---|-----------|-----------|---------|
| 1 | `eval/scripts/build_scanned.py` | 17,016 B (400 dòng) | Pipeline DOCX → PDF text → PNG raster → PDF image-only |
| 2 | `eval/scripts/__init__.py` | 0 B | Marker package (rỗng — git không stage tự động vì 0 B) |
| 3 | `eval/dataset/scanned/DMD_T1-01_scanned.pdf` | 3,743,132 B (21 page) | Scanned giả lập từ DMD_T1-01_DinhVi_TrungTam_v1.docx |
| 4 | `eval/dataset/scanned/DMD_T1-04_scanned.pdf` | 4,680,276 B (31 page) | Scanned giả lập từ DMD_T1-04_FAQ_ThuongHieu_v1.docx |

## SHA256 hash 2 PDF output (cho Phase 5 verify identity)

| Filename | SHA256 |
|----------|--------|
| `DMD_T1-01_scanned.pdf` | `12871723a75b796d7acf1ff4cf0f1a5baa1a681ff9ec209fbc8bdb9a89d36ed7` |
| `DMD_T1-04_scanned.pdf` | `d9f48f9b05a9edfa88a1369c631a0efa40d27467b6a87f6622980d2ba3cd5e94` |

Hash chỉ stable trong 1 run (do timestamp metadata pymupdf/img2pdf). Phase 5 nếu cần regenerate, kết quả về mặt nội dung (số page, kích thước raster, không text layer) sẽ identical, nhưng SHA256 có thể đổi. Bằng chứng `verified_no_text_layer=true` quan trọng hơn hash.

## Tasks executed

| # | Task | Trạng thái | Verify |
|---|------|-----------|--------|
| 1 | Viết `eval/scripts/build_scanned.py` (~400 dòng) với fallback chain Step A 3 tầng + Step B 2 tầng | done | `python -m ruff check` All checks passed; `ast.parse` OK; `--help` hiển thị đủ flag (`--force`, `--dpi`, `--only`) |
| 2 | Chạy `python eval/scripts/build_scanned.py` build cả 2 PDF + commit | done | Cả 2 PDF tồn tại, pages = 21/31, text_layer = 0/0 chars; `pdftotext` empty/page-separator-only; commit `045d29b` |

## Output thực tế của build run

```
Step A [docx2pdf]: DMD_T1-01_DinhVi_TrungTam_v1.docx → DMD_T1-01_DinhVi_TrungTam_v1.pdf  (10s)
Step B [pdf2image]: ... fail (poppler không có) → fallback pymupdf
Step B [pymupdf]: 21 page rasterized
Step C [img2pdf]: 21 page → DMD_T1-01_scanned.pdf
✓ DMD_T1-01_scanned.pdf không có text layer thực (text non-whitespace = 0 chars, ngưỡng < 50)
Build hoàn tất: DMD_T1-01_scanned.pdf (3743132 bytes)

Step A [docx2pdf]: DMD_T1-04_FAQ_ThuongHieu_v1.docx → DMD_T1-04_FAQ_ThuongHieu_v1.pdf   (9s)
Step B [pymupdf]: 31 page rasterized
Step C [img2pdf]: 31 page → DMD_T1-04_scanned.pdf
✓ DMD_T1-04_scanned.pdf không có text layer thực (text non-whitespace = 0 chars, ngưỡng < 50)
Build hoàn tất: DMD_T1-04_scanned.pdf (4680276 bytes)

JSON cuối: {"built": ["DMD_T1-01_scanned.pdf", "DMD_T1-04_scanned.pdf"], "verified_no_text_layer": true}
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking issue / Environment]** — Poppler không có trên Windows executor, `pdf2image.convert_from_path` raise `Unable to get page count. Is poppler installed and in PATH?`
- **Found during:** Verify Task 1 (test deps available).
- **Issue:** PLAN chỉ định pdf2image làm Step B primary, nhưng pdf2image bind tới Poppler binary; Windows dev box (executor + máy user) thường không có Poppler trong PATH.
- **Fix:** Thêm fallback `_rasterize_with_pymupdf()` ở Step B — pure-Python wheel, không cần binary external. Primary vẫn là pdf2image (giữ đúng intent PLAN), pymupdf chỉ trigger khi pdf2image fail. Log warning rõ ràng để dev biết tool nào đang được dùng.
- **Files modified:** `eval/scripts/build_scanned.py` (function `_rasterize_with_pymupdf`).
- **Tác động Phase tiếp theo:** None — script tự động pick fallback. Nếu dev cài Poppler về sau, primary path sẽ chạy lại tự động.

**2. [Rule 3 — Blocking issue]** — LibreOffice không có trên executor, `docx2pdf` không cài sẵn.
- **Found during:** Trước khi chạy Task 2.
- **Issue:** Step A fallback chain rỗng (cả LibreOffice lẫn docx2pdf đều thiếu) → script sẽ exit code 2 (NO_CONVERTER), không build được runtime → vi phạm yêu cầu PLAN "build artifact thực tế".
- **Fix:** `pip install docx2pdf` (cài thêm `pywin32-311` deps tự động) — dùng MS Word COM automation đã có sẵn trên Windows executor. Không thêm vào `eval/pyproject.toml` deps cố định vì docx2pdf chỉ chạy được trên Windows + macOS, KHÔNG cross-platform; LibreOffice (cài tay) vẫn là khuyến nghị chính cho dev khác.
- **Files modified:** None trong git (cài runtime tool, không commit pyproject change).
- **Tác động Phase tiếp theo:** Phase 5 nếu chạy trên Windows: cài docx2pdf hoặc LibreOffice tùy môi trường. README đã có hint troubleshooting (eval/README.md mục troubleshooting, từ Plan 01-01).

**3. [Rule 2 — Critical functionality]** — Thêm `--only DOCX_NAME` flag vào CLI (không có trong PLAN spec).
- **Found during:** Task 1 design.
- **Lý do:** PLAN nêu rõ trong task description bullet "CLI: ... `--only DMD_T1-01_DinhVi_TrungTam_v1.docx`" — đây là yêu cầu cứng dù không liệt kê trong artifact spec.
- **Implementation:** Validate input arg phải nằm trong `SCANNED_SOURCE_MAP`, fail fast với error log rõ nếu sai.
- **Files modified:** `eval/scripts/build_scanned.py` (argparse + branch trong `main()`).

**4. [Rule 2 — Critical functionality]** — Thêm exit code phân biệt root cause (0/1/2/3) thay vì 0/1.
- **Lý do:** PLAN spec nói "in hint cài LibreOffice và `sys.exit(2)`" → cần ít nhất exit 2 cho NO_CONVERTER. Mở rộng thêm exit 3 cho TEXT_LAYER_LEAK để CI phân biệt được "build OK nhưng output sai invariant" với "build runtime fail" (exit 1).
- **Files modified:** `eval/scripts/build_scanned.py` (4 hằng `EXIT_*`).

### Auth Gates

Không có. Plan này không gọi network/API — chỉ là pipeline file local.

## TDD Gate Compliance

PLAN không có task `tdd="true"`. Verify done dựa vào ruff lint + ast parse + runtime build + pypdf assert (đã pass tất cả).

## Known Stubs

Không có. Không có placeholder, không có hardcoded data flow ra UI, không có TODO/FIXME nào trong file.

## Threat Flags

Không. Script local-only:
- Không nhận input từ network.
- Không expose endpoint mới.
- Không touch credential/secret.
- Đọc DOCX nguồn trong cùng repo + ghi PDF output cùng repo — không vượt trust boundary.

## Self-Check: PASSED

**Files created tồn tại:**
- FOUND: `eval/scripts/build_scanned.py`
- FOUND: `eval/dataset/scanned/DMD_T1-01_scanned.pdf`
- FOUND: `eval/dataset/scanned/DMD_T1-04_scanned.pdf`

**Commit existence:**
- FOUND: `045d29b` — `feat(eval): build_scanned.py giả lập scanned PDF từ DOCX [phase-1 plan-03]`

**Verify invariant runtime:**
- FOUND: 0 ký tự text layer trong DMD_T1-01_scanned.pdf (pypdf)
- FOUND: 0 ký tự text layer trong DMD_T1-04_scanned.pdf (pypdf)
- FOUND: pdftotext T1-01 empty, T1-04 chỉ 31 form-feed (1 cho mỗi page) — không phải text thực

**Lint/parse:**
- PASSED: `python -m ruff check eval/scripts/build_scanned.py` → All checks passed!
- PASSED: `ast.parse` OK
- PASSED: `python eval/scripts/build_scanned.py --help` hiển thị đủ flag

---

*Plan 01-03 hoàn tất 2026-04-28. Sẵn sàng cho phần còn lại Wave 2 (Plan 01-04 extract_headings.py — `eval/dataset/headings.json` đã có sẵn untracked, sẽ được Plan 01-04 commit).*
