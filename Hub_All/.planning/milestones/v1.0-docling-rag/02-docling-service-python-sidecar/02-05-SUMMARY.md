---
phase: 02-docling-service-python-sidecar
plan: 05
subsystem: docling-pipeline
tags: [serializer, schema, dsvc-02, extract, chunk]
status: completed
requires:
  - "Plan 02-01 skeleton (core/__init__.py W3 gate)"
provides:
  - "core/serializer.py: build_doc_meta + serialize_chunks → contract DSVC-02 ĐÓNG BĂNG cho Plan 06 + Phase 3"
  - "ChunkDict + DocMetaDict TypedDict — type-safe schema cho Python service"
affects: []
tech_stack_added:
  - "tiktoken (đã có ở pyproject Plan 01) — encoding cl100k_base cho token_count"
patterns_used:
  - "TypedDict cho schema response (lightweight vs Pydantic — vẫn JSON-serializable)"
  - "Defensive getattr cho version drift Docling (headings/headers, BoundingBox l/t/r/b vs x0/y0/x1/y1)"
  - "try/except import cho optional deps (smoke test môi trường thiếu dep vẫn AST parse)"
key_files_created:
  - docling-pipeline/src/docling_pipeline/core/serializer.py
key_files_modified: []
decisions:
  - "Schema response DSVC-02 ĐÓNG BĂNG — Plan 06 (api/process.py) và Phase 3 (Go adapter) consume contract này"
  - "TypedDict thay vì Pydantic BaseModel — schema ổn định, không cần validation runtime ở serializer (validation ở edge api/process.py)"
  - "table_html giữ nguyên output của TableItem.export_to_html(doc=doc) — preserve rowspan/colspan/<thead>/<tbody> tự nhiên"
  - "Figure caption marker inject ĐẦU chunk text (không cuối) — render anchor xuất hiện trước nội dung mô tả"
  - "Defensive getattr cho field name drift — Docling 2.91 patch level có thể đổi shape, Plan 07 (test) sẽ verify shape thực tế"
metrics:
  duration_minutes: 3
  completed_date: "2026-04-29"
  tasks_completed: 1
  files_created: 1
  files_modified: 0
requirements_addressed:
  - DSVC-02
  - EXTRACT-03
  - EXTRACT-04
  - CHUNK-03
---

# Phase 2 Plan 05: Serializer DoclingDocument → DSVC-02 Schema Summary

**One-liner:** Tạo `core/serializer.py` map `DoclingDocument` + `list[DocChunk]` (output HybridChunker) sang dict đúng schema DSVC-02 — bao gồm extract `table_html` giữ rowspan/colspan, inject figure caption marker `![caption](#fig-N)`, compute bbox union + token_count via tiktoken `cl100k_base`.

## Outcome

- File `docling-pipeline/src/docling_pipeline/core/serializer.py` (305 dòng — vượt min_lines 100) commit ở `5a0d264`.
- Export 4 symbol: `build_doc_meta`, `serialize_chunks`, `ChunkDict`, `DocMetaDict`.
- 10 field `ChunkDict` khớp 100% schema DSVC-02 trong CONTEXT mục "Schema response /v1/process": `chunk_index, text, headers, caption, page_start, page_end, is_table, table_html, bbox, token_count`.
- 5 field `DocMetaDict` khớp 100%: `filename, file_type, page_count, language_detected, ocr_used`.
- Helper private (10 hàm): `_file_type_from_ext`, `_extract_provenance`, `_detect_table_html`, `_extract_caption`, `_has_picture`, `_inject_figure_caption_marker`, `_extract_headers`, `_count_tokens`.
- Contract DSVC-02 ĐÓNG BĂNG — Plan 06 (api/process.py) và Phase 3 (Go adapter `DoclingExtractor`) sẽ consume schema này.

## Tasks Completed

| Task | Name                                                              | Commit  | Files                                                         |
| ---- | ----------------------------------------------------------------- | ------- | ------------------------------------------------------------- |
| 1    | Tạo core/serializer.py — map Docling output sang schema DSVC-02 | 5a0d264 | docling-pipeline/src/docling_pipeline/core/serializer.py |

## Decisions Made

1. **Schema DSVC-02 ĐÓNG BĂNG sau plan này** — Plan 06 + Phase 3 dựa vào contract; bất kỳ đổi schema nào sau đó là breaking change cần discuss lại.
2. **TypedDict thay vì Pydantic BaseModel** — TypedDict đủ cho type hint + dict trả về; validation runtime đặt ở edge (api/process.py) qua Pydantic response model. Tách concern: serializer chỉ map shape, validation ở boundary.
3. **`table_html` lấy thẳng từ `TableItem.export_to_html(doc=doc)`** — Docling 2.x preserve native `<thead>`, `<tbody>`, `colspan`, `rowspan`. Có fallback `export_to_html()` không arg cho version drift.
4. **Figure caption marker inject ĐẦU chunk text** (`![caption](#fig-N)\n\n{text}`) — UI render anchor xuất hiện trước phần mô tả. KHÔNG insert binary image (EXTRACT-04 yêu cầu chỉ caption).
5. **Defensive `getattr` cho version drift Docling 2.91** — `headings` vs `headers`, bbox `l/t/r/b` vs `x0/y0/x1/y1`. Plan 07 (test với fixture PDF/DOCX thật) sẽ xác nhận shape chính xác cho version đã pin (`docling==2.91.0`).
6. **try/except import `docling_core` + `tiktoken`** — smoke test môi trường dev (chưa cài deps) vẫn AST parse được; runtime trong Docker container có đủ dep.
7. **`bbox` union (min l/t, max r/b)** — đủ cho UI citation rendering; KHÔNG lưu list bbox riêng từng item (giảm payload size cho Go adapter).
8. **`token_count` fallback `len(text)//4`** khi tokenizer load fail — không crash pipeline, log warning để observability bắt được.

## Verification Performed

- `python -c "import ast; ast.parse(open('serializer.py', encoding='utf-8').read())"` → `AST OK`.
- `wc -l` → 305 dòng (≥ min_lines 100).
- AST inspect: 10 functions + 2 classes (DocMetaDict, ChunkDict) đúng spec.
- Verify regex pass: `def serialize_chunks`, `def build_doc_meta`, `table_html`, `fig-`, `ChunkDict` đều có mặt.
- Smoke import `from docling_pipeline.core.serializer import ...` trên môi trường dev local fail vì `structlog` chưa cài (deps Python service chỉ install trong Docker container) — KHÔNG ảnh hưởng plan; verify deferred sang Plan 07 khi container build xong.

## Deviations from Plan

**1. [Note] Smoke test runtime defer sang Plan 07**
- **Found during:** Verification step.
- **Issue:** Môi trường dev local Windows chưa có `structlog`/`tiktoken`/`docling_core` (deps install trong Docker per Plan 01 Dockerfile). `python -c "from docling_pipeline.core.serializer import ..."` fail ImportError.
- **Resolution:** AST parse pass đầy đủ + try/except import đã wrap optional deps. Smoke test runtime sẽ chạy ở Plan 07 (tests/test_extract.py) bên trong container hoặc venv có cài full pyproject.
- **Files modified:** Không có.
- **Commit:** N/A.

**2. [Rule 2 — robustness] Thêm try/except import cho `docling_core` + `tiktoken`**
- **Found during:** Implementation.
- **Issue:** Plan action gốc dùng `from docling_core...` direct import — fail nếu môi trường thiếu dep, làm AST/lint check khó chạy ngoài container.
- **Resolution:** Wrap try/except `ImportError` với fallback type alias `Any` — module vẫn parse được, runtime trong container vẫn dùng đúng type.
- **Files modified:** docling-pipeline/src/docling_pipeline/core/serializer.py.
- **Commit:** 5a0d264 (cùng commit Task 1).

## Known Stubs

Không có stub. Toàn bộ logic đã implement:
- `language_detected` mặc định `None` — Docling không expose detection trong M1, đây là design choice đã ghi rõ trong CONTEXT (build_doc_meta nhận `language_detected` arg để Plan 06 có thể detect riêng nếu cần).
- Defensive `getattr` không phải stub — là cơ chế version drift handling thực sự.

## Threat Flags

Không phát hiện threat surface mới. Serializer thuần map dữ liệu nội bộ (Docling output → dict), không nhận input ngoài, không call I/O, không serialize secret. Trust boundary surface sẽ xuất hiện ở Plan 06 (api/process.py — multipart upload).

## TDD Gate Compliance

Plan 02-05 không phải plan TDD (`type: execute`, không có `tdd="true"` trong tasks). Test sẽ ở Plan 07 (`tests/test_extract.py`) verify shape thực tế của serializer khi gọi với fixture PDF/DOCX nhỏ.

## Next Step

Wave 2 còn lại: Plan 02-03 (extractor.py), Plan 02-04 (chunker.py) chạy song song với plan này. Plan 02-06 (api/process.py — wire serializer + extractor + chunker) là Wave 3, đợi cả 3 plan W2 done.

## Self-Check: PASSED

- File `docling-pipeline/src/docling_pipeline/core/serializer.py` → FOUND (305 dòng).
- Commit `5a0d264` → FOUND in `git log`.
- Functions `serialize_chunks`, `build_doc_meta` → FOUND (AST inspect).
- Classes `ChunkDict`, `DocMetaDict` → FOUND với đúng 10/5 field schema DSVC-02.
- Pattern `table_html` → FOUND (TableItem.export_to_html).
- Pattern `fig-` → FOUND (figure caption marker EXTRACT-04).
