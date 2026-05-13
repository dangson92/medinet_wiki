---
phase: 02-docling-service-python-sidecar
plan: 03
subsystem: docling-pipeline
tags: [extractor, docling, ocr, tesseract, wave-2]
requires:
  - "Plan 02-01 W3 gate: docling_pipeline/core/__init__.py + config.py với Settings.ocr_engine + ocr_langs"
provides:
  - "DoclingExtractor wrapper — single-format-agnostic extraction (PDF/DOCX/XLSX/PPTX/HTML/PNG/JPG)"
  - "get_extractor() singleton lru_cache cho hot path"
  - "warm_models() fail-soft cho FastAPI lifespan (Plan 06)"
affects: []
tech_stack_added:
  - "docling.document_converter.DocumentConverter + PdfFormatOption + ImageFormatOption"
  - "docling.datamodel.pipeline_options.TesseractCliOcrOptions + RapidOcrOptions + PdfPipelineOptions"
  - "docling.datamodel.base_models.DocumentStream + InputFormat"
  - "docling_core.types.doc.DoclingDocument"
patterns_used:
  - "Singleton qua lru_cache(maxsize=1) — DocumentConverter heavy init reuse"
  - "Format-agnostic dispatch qua _EXT_TO_FORMAT enum mapping (KHÔNG if-else nghiệp vụ)"
  - "Fail-soft warm_models — log warning thay vì raise (service vẫn lên)"
  - "structlog structured logging với event names extract_start/extract_done/extract_fail"
key_files_created:
  - docling-pipeline/src/docling_pipeline/core/extractor.py
key_files_modified: []
decisions:
  - "W5 revision: ImageFormatOption(pipeline_options=pipe_opts) RIÊNG cho InputFormat.IMAGE — KHÔNG reuse PdfFormatOption (Docling 2.91 validator reject mismatch)"
  - "Stub PDF tối thiểu (1 trang trắng, KHÔNG raster) cho warm_models — không trigger OCR, warm models layout/parser thôi"
  - "DOCX/XLSX/PPTX/HTML KHÔNG khai báo format_options — dùng default Docling (không cần OCR cho born-digital)"
  - "RapidOcrOptions() init không lang param — RapidOCR không có concept lang per-init giống Tesseract"
metrics:
  duration_minutes: 3
  completed_date: "2026-04-29"
  tasks_completed: 1
  files_created: 1
  files_modified: 0
requirements_addressed:
  - EXTRACT-01
  - EXTRACT-02
  - DSVC-03
---

# Phase 2 Plan 03: Docling Extractor Wrapper Summary

**One-liner:** Wrapper `DoclingExtractor` bọc Docling `DocumentConverter` (164 dòng) với OCR Tesseract `vie+eng` default + RapidOCR switchable, format-agnostic 7 extension qua `_EXT_TO_FORMAT` enum mapping, ImageFormatOption riêng cho `InputFormat.IMAGE` (W5 fix).

## Outcome

- `core/extractor.py` 164 dòng commit atomic ở `faf21de`.
- Public API: `DoclingExtractor` class + `get_extractor()` singleton + `warm_models()` convenience wrapper — sẵn sàng cho Plan 04 (chunker consume `DoclingDocument` output) và Plan 06 (FastAPI lifespan call `warm_models`).
- 7 extension map: `.pdf .docx .xlsx .pptx .html .htm .png .jpg .jpeg` → `InputFormat.{PDF,DOCX,XLSX,PPTX,HTML,IMAGE}`.
- OCR Tesseract `vie+eng` default qua `TesseractCliOcrOptions(lang=["vie", "eng"])`; switch sang RapidOCR khi `DOCLING_OCR_ENGINE=rapidocr`.
- `format_options` khai báo CẢ `PdfFormatOption` (cho PDF) lẫn `ImageFormatOption` (cho IMAGE) — W5 fix tránh validator error Docling 2.91.
- Pipeline options: `do_ocr=True`, `do_table_structure=True`, `do_cell_matching=True`, `generate_picture_images=False`.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1    | Tạo core/extractor.py — wrapper DocumentConverter + OCR config + ImageFormatOption | faf21de | docling-pipeline/src/docling_pipeline/core/extractor.py |

## Decisions Made

1. **W5 revision: ImageFormatOption riêng cho IMAGE** — Docling 2.91 validator reject `PdfFormatOption + InputFormat.IMAGE` pair. Khai báo cả 2 entry trong `format_options` dict.
2. **Stub PDF tối thiểu trong warm_models** — 1 trang trắng PDF spec minimum, KHÔNG có raster → không trigger OCR. Mục đích: warm Docling parser/layout models, KHÔNG warm Tesseract subprocess (Tesseract spawn trên demand mỗi request, không cần warm).
3. **Fail-soft warm_models** — log warning, không raise. Service vẫn lên ngay cả khi warm fail; request đầu sẽ chậm hơn (lazy load HuggingFace models).
4. **DOCX/XLSX/PPTX/HTML KHÔNG khai báo format_options** — born-digital, không cần OCR + table_structure (Docling default đã tốt cho các format này). Chỉ override PDF + IMAGE vì cần OCR config.
5. **RapidOcrOptions() không lang param** — Docling 2.91 RapidOCR API chưa support lang per-init. Future v2 backlog nếu cần Vietnamese-tuned RapidOCR model.

## Verification Performed

- `python -c "import ast; ast.parse(open('docling-pipeline/src/docling_pipeline/core/extractor.py', encoding='utf-8').read()); print('AST OK')"` → `AST OK`.
- `wc -l` → `164` dòng (≥ 80 yêu cầu min_lines).
- `grep` 8 symbols required: `class DoclingExtractor`, `TesseractCliOcrOptions`, `def warm_models`, `_EXT_TO_FORMAT`, `ImageFormatOption`, `PdfFormatOption`, `RapidOcrOptions`, `get_extractor` → tất cả match.
- Verify automated từ plan: `grep -q "class DoclingExtractor" && grep -q "TesseractCliOcrOptions" && grep -q "def warm_models" && grep -q "_EXT_TO_FORMAT" && grep -q "ImageFormatOption"` → tất cả pass.

## Deviations from Plan

**1. [Rule 3 - Defer] Runtime import verify deferred**
- **Found during:** Verification step.
- **Issue:** `python -c "from docling_pipeline.core.extractor import get_extractor; e = get_extractor(); print(type(e))"` không thể chạy trên môi trường executor hiện tại — `docling==2.91.0` chưa pip install (Plan 02-01 chỉ commit `pyproject.toml` pin version, chưa `pip install -e .[dev]` thực tế trong venv).
- **Resolution:** Defer runtime import test sang Plan 02-07 (`test_extract.py`) khi pytest run trong venv có Docling installed. AST parse OK + 8/8 symbol checks pass đảm bảo file syntactically valid và public API đúng spec.
- **Files modified:** Không có.
- **Commit:** N/A.

## Known Stubs

Không có stub. Hàm `warm_models` dùng stub PDF binary nhưng đó là đầu vào TEST có chủ đích cho convert flow, không phải stub data thay thế logic.

## Threat Flags

Không phát hiện threat surface mới. Extractor chưa expose endpoint — chỉ là internal library function. Trust boundary cho file binary input sẽ xuất hiện ở Plan 02-06 (`api/process.py` multipart upload) với `<threat_model>` riêng (file size limit, MIME validation, path traversal qua filename).

## Next Step

Wave 2 song song:
- Plan 02-04: HybridChunker wrapper (`core/chunker.py`) — consume `DoclingDocument` từ extractor.
- Plan 02-05: Serializer (`core/serializer.py`) — map `DoclingDocument` + chunks → response schema DSVC-02.

Wave 3 sequential sau Wave 2:
- Plan 02-06: FastAPI app + endpoints (`main.py` + `api/process.py` + `api/health.py`) — gọi `warm_models()` trong lifespan, `get_extractor()` trong handler.
- Plan 02-07: Tests (sẽ cover runtime import + extract thật với fixture).

## Self-Check: PASSED

- File `docling-pipeline/src/docling_pipeline/core/extractor.py` → FOUND (164 dòng).
- Commit `faf21de` → FOUND in `git log`.
- AST parse `extractor.py` → OK.
- 8/8 symbol grep checks → pass.
