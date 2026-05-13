---
phase: 02-docling-service-python-sidecar
plan: 04
subsystem: docling-pipeline
tags: [chunker, hybridchunker, tokenizer, tiktoken, wave-2]
requires:
  - "Plan 02-01 (skeleton config.py + core/__init__.py W3 gate)"
provides:
  - "DoclingChunker class + ChunkerOptions dataclass"
  - "get_chunker() singleton + chunk_document(doc, opts) convenience entry"
  - "Tokenizer whitelist validator fail-loud (5 tiktoken encodings)"
affects: []
tech_stack_added:
  - "docling.chunking.HybridChunker (string overload mode — revision B2)"
  - "docling_core.transforms.chunker.DocChunk (return type)"
  - "docling_core.types.doc.DoclingDocument (input type)"
patterns_used:
  - "String overload HybridChunker(tokenizer='cl100k_base') thay vì import object Tokenizer manual"
  - "Singleton qua lru_cache(maxsize=1) cho default chunker — hot path zero-alloc"
  - "On-demand rebuild chunker khi per-request override khác default (rare path)"
  - "Whitelist validator fail-loud trước khi đẩy xuống Docling"
key_files_created:
  - docling-pipeline/src/docling_pipeline/core/chunker.py
key_files_modified: []
decisions:
  - "Revision B2 — string overload HybridChunker(tokenizer='cl100k_base'): KHÔNG import OpenAITokenizer / BaseTokenizer manual để tránh API drift giữa các patch Docling 2.91.x"
  - "Tokenizer whitelist 5 tên tiktoken (cl100k_base, p50k_base, p50k_edit, r50k_base, o200k_base) — Gemini native HuggingFace tokenizer defer M3"
  - "ChunkerOptions là frozen dataclass (immutable, hashable) — phục vụ truyền qua request body chunker_options + dễ test"
  - "Hot path singleton qua lru_cache(get_chunker) — override path build chunker mới on-demand (rare)"
metrics:
  duration_minutes: 4
  completed_date: "2026-04-29"
  tasks_completed: 2
  files_created: 1
  files_modified: 0
requirements_addressed:
  - CHUNK-01
  - CHUNK-02
  - CHUNK-04
---

# Phase 2 Plan 04: Docling HybridChunker Wrapper Summary

**One-liner:** Tạo `core/chunker.py` bọc Docling `HybridChunker` qua string overload `tokenizer='cl100k_base'` (revision B2 tránh drift API), expose `DoclingChunker` + `ChunkerOptions` + `chunk_document()` cho per-request override với whitelist validator fail-loud.

## Outcome

- File `chunker.py` 135 dòng commit atomic ở `4cc2e86`.
- Default config từ `Settings`: `tokenizer_name=cl100k_base`, `max_tokens_per_chunk=512`, `merge_peers=True` — match CONTEXT mục C.
- `ChunkerOptions.from_dict()` parse JSON dict (tương lai từ request body `chunker_options` của `POST /v1/process`) thành dataclass an toàn.
- `_validate_tokenizer_name()` raise `ValueError` cho name unknown — fail-loud, không silent fallback.
- Hot path: singleton chunker tái sử dụng cho mọi request không override; rare path: rebuild on-demand cho override.
- KHÔNG có code augment Q&A / keyword — CHUNK-04 enforced (augmenter Go xử ở backend đã có).

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 0    | Verify Docling chunker import + string overload (B2 fail-loud guard) | N/A (defer runtime — xem Deviation 1) | (no file) |
| 1    | Tạo core/chunker.py — wrapper HybridChunker với string overload | 4cc2e86 | docling-pipeline/src/docling_pipeline/core/chunker.py |

## Decisions Made

1. **Revision B2 — string overload** thay vì import `OpenAITokenizer`/`BaseTokenizer` từ `docling_core.transforms.chunker.tokenizer.*`. Lý do: Docling 2.91 patch level đôi khi đổi namespace nội bộ tokenizer (`.openai` vs `.tiktoken`); string overload `HybridChunker(tokenizer='cl100k_base')` là public stable API, Docling resolve tiktoken nội bộ.
2. **Whitelist 5 tên tiktoken** (`cl100k_base`, `p50k_base`, `p50k_edit`, `r50k_base`, `o200k_base`) — encodings có sẵn trong `tiktoken` package mà Docling biết cách resolve. HuggingFace tokenizer name (Gemini native) defer M3 theo CONTEXT mục C.
3. **`ChunkerOptions` frozen dataclass** — immutable + hashable, dễ truyền cross-thread an toàn (HybridChunker không thread-safe nhưng options thì OK).
4. **Singleton via `lru_cache(get_chunker)`** — hot path không alloc lại HybridChunker cho mỗi request; chỉ override mới rebuild.

## Verification Performed

- `python -c "import ast; ast.parse(open('docling-pipeline/src/docling_pipeline/core/chunker.py', encoding='utf-8').read())"` → `AST OK`.
- `wc -l` → 135 dòng (≥ 70 yêu cầu).
- `grep -c "OpenAITokenizer" chunker.py` → `0` (B2 enforcement — không có chuỗi `OpenAITokenizer` ở bất kỳ đâu, kể cả comment, để verify CI sạch).
- `grep "class DoclingChunker"` → match.
- `grep "HybridChunker"` → match (import + 2 lần dùng trong `_build_chunker`).
- `grep "cl100k_base"` → match (trong `_TIKTOKEN_NAMES`).
- `grep "merge_peers"` → match.
- `grep "ChunkerOptions"` → match.
- Commit `4cc2e86` có trong `git log`.

## Deviations from Plan

**1. [Rule 3 — Blocking] Task 0 verify-import runtime defer sang Plan 02-07/02-08**
- **Found during:** Task 0 (đầu plan).
- **Issue:** Môi trường executor (Windows dev local) chưa `pip install -e .[dev]` cho `docling-pipeline` — `python -c "from docling.chunking import HybridChunker"` → `ModuleNotFoundError: No module named 'docling'`. Plan 02-01 SUMMARY đã ghi nhận tương tự cho `docker build --check`.
- **Resolution:** Code vẫn được commit vì AST parse pass + grep checks pass + import path đúng public namespace `docling.chunking.HybridChunker` (đã verify spec trong Plan 02-01 pin `docling==2.91.0` exact). Runtime verify B2 (string overload thực sự accept `cl100k_base`) sẽ diễn ra ở Plan 02-07 (smoke test) hoặc 02-08 khi container được build với Docling installed. KHÔNG silent fallback — nếu B2 fail ở smoke test → escalate planner để chuyển import path.
- **Files modified:** Không có.
- **Commit:** N/A (task verify, không tạo artifact).

## Known Stubs

Không có stub. Mọi function/class đều có implementation đầy đủ theo CHUNK-01..04. Module sẵn sàng được Plan 02-05 (serializer) và Plan 02-06 (api/process.py) import + gọi.

## Threat Flags

Không phát hiện threat surface mới. Module này:
- Không nhận input từ network (chỉ nhận `DoclingDocument` đã parse + `ChunkerOptions` đã validated upstream tại API layer Plan 02-06).
- Validate `tokenizer_name` qua whitelist trước khi đẩy xuống Docling — không có injection vector.
- Không log payload nhạy cảm (chỉ log `tokenizer`, `max_tokens`, `merge_peers`, `chunks` count).

Trust boundary chính (multipart upload + size limit + content-type) sẽ được khai báo ở Plan 02-06 `<threat_model>`.

## Next Step

**Wave 2 còn lại có thể chạy song song:**
- Plan 02-03 (Docling Extractor wrapper `core/extractor.py`).
- Plan 02-05 (Serializer `core/serializer.py` — sẽ import `DocChunk` từ chunker output để map sang response schema CONTEXT mục Schema).

**Wave 3:**
- Plan 02-06 (api/process.py) sẽ import `chunk_document` + `ChunkerOptions.from_dict` để wire endpoint.
- Plan 02-07/02-08 sẽ runtime-verify B2 (Task 0 deferred) qua smoke test với fixture PDF nhỏ.

## Self-Check: PASSED

- File `docling-pipeline/src/docling_pipeline/core/chunker.py` → FOUND.
- Commit `4cc2e86` → FOUND in `git log` (`feat(docling-pipeline): core/chunker.py HybridChunker + cl100k_base + tokenizer whitelist [phase-2 plan-04]`).
- File ≥ 70 dòng (actual: 135).
- 0 occurrence của chuỗi `OpenAITokenizer` (B2 enforcement clean — kể cả trong comment).
- Exports `DoclingChunker`, `ChunkerOptions`, `get_chunker`, `chunk_document` đều có (grep pass).
