---
phase: 02-docling-service-python-sidecar
plan: 01
subsystem: docling-pipeline
tags: [skeleton, python, fastapi, docling, dockerfile]
requires: []
provides:
  - "docling-pipeline/ skeleton (Dockerfile + pyproject + config + cấu trúc package)"
  - "W3 gate: api/core/observability package markers cho Wave 2"
affects: []
tech_stack_added:
  - "Python 3.11"
  - "docling==2.91.0 (pin exact — revision B2)"
  - "fastapi, uvicorn[standard], python-multipart"
  - "structlog, tiktoken, pydantic-settings, pydantic"
  - "ruff, pytest, pytest-asyncio, httpx (dev)"
  - "Tesseract OCR vie+eng (Debian bookworm package)"
patterns_used:
  - "PEP 621 pyproject.toml + setuptools.packages.find"
  - "Pydantic Settings BaseSettings + lru_cache singleton"
  - "Docker single-stage CPU-only base python:3.11-slim-bookworm"
key_files_created:
  - docling-pipeline/Dockerfile
  - docling-pipeline/pyproject.toml
  - docling-pipeline/.gitignore
  - docling-pipeline/.env.example
  - docling-pipeline/src/docling_pipeline/__init__.py
  - docling-pipeline/src/docling_pipeline/config.py
  - docling-pipeline/src/docling_pipeline/api/__init__.py
  - docling-pipeline/src/docling_pipeline/core/__init__.py
  - docling-pipeline/src/docling_pipeline/observability/__init__.py
  - docling-pipeline/tests/__init__.py
  - docling-pipeline/tests/fixtures/.gitkeep
key_files_modified: []
decisions:
  - "Pin docling==2.91.0 exact (KHÔNG wildcard 2.91.*) để khoá patch level — revision B2 từ 02-CHECK.md"
  - "Single-stage Dockerfile thay vì multi-stage để đơn giản hoá build (CONTEXT mục A)"
  - "Cài libpoppler-cpp-dev + poppler-utils + libjpeg-dev + zlib1g-dev cho pillow/pdf2image (Rủi ro 3)"
  - "Singleton Settings qua lru_cache(maxsize=1) — hot path không phải re-parse env"
metrics:
  duration_minutes: 5
  completed_date: "2026-04-29"
  tasks_completed: 2
  files_created: 11
  files_modified: 0
requirements_addressed:
  - DSVC-05
  - DSVC-06
---

# Phase 2 Plan 01: Skeleton Python Sidecar Summary

**One-liner:** Khởi tạo `docling-pipeline/` Python service skeleton với Dockerfile CPU-only (Tesseract vie+eng), pyproject.toml pin `docling==2.91.0` exact, và cấu trúc package `api/core/observability` sẵn sàng làm W3 gate cho Wave 2.

## Outcome

- Toàn bộ 11 file skeleton đã commit atomic ở `79134f3`.
- 3 package marker `api/__init__.py`, `core/__init__.py`, `observability/__init__.py` tồn tại — Wave 2 (Plan 02-03 extractor, 02-04 chunker, 02-05 serializer) có thể chạy song song không conflict cấu trúc package.
- `config.py` expose `Settings` class + `get_settings()` lru_cache; load đầy đủ 9 env vars `DOCLING_*` (ocr_engine, ocr_langs, tokenizer_name, max_tokens_per_chunk, max_file_mb, request_timeout_sec, log_level, log_format, host, port).
- `.env.example` chốt 4 nhóm env: OCR / Tokenizer / Limits / Logging — khớp 100% với CONTEXT mục D + E + Schema.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1    | Tạo Dockerfile + pyproject + .gitignore + .env.example | 79134f3 | Dockerfile, pyproject.toml, .gitignore, .env.example |
| 2    | Skeleton src/ + tests/ + config.py | 79134f3 | 7 file Python + .gitkeep |

(Hai task gộp 1 commit atomic theo yêu cầu task spec — toàn bộ skeleton là 1 đơn vị logic.)

## Decisions Made

1. **Pin docling==2.91.0 exact** thay vì `2.91.*` — revision B2 trong `02-CHECK.md`. Lý do: Docling minor patch đôi khi đổi import path tokenizer; pin patch level đảm bảo executor luôn test trên cùng API surface đã verify ở Plan 04 Task 0.
2. **Single-stage Dockerfile** — CONTEXT mục A. Đơn giản hơn multi-stage, image cuối ~2.5GB chấp nhận được vì models cache lazy-load qua volume mount.
3. **`docling_models/` trong `.gitignore`** — HuggingFace cache lazy-load, KHÔNG commit (vài GB).
4. **`.env` thêm vào `.gitignore`** — đề phòng dev tạo `.env` local có secret tương lai.

## Verification Performed

- `python -c "import ast; ast.parse(open('docling-pipeline/src/docling_pipeline/config.py', encoding='utf-8').read())"` → `OK`.
- `grep "tesseract-ocr-vie" docling-pipeline/Dockerfile` → match.
- `grep "docling==2.91.0" docling-pipeline/pyproject.toml` → match.
- `grep -E "docling==2\.91\.\*" docling-pipeline/pyproject.toml` → exit code 1 (KHÔNG match wildcard — đúng).
- `grep "DOCLING_OCR_LANGS=vie+eng" docling-pipeline/.env.example` → match (gián tiếp qua `grep` trong verify Task 1).
- 3 file `api/__init__.py`, `core/__init__.py`, `observability/__init__.py` tồn tại ở filesystem (W3 gate ✓).

## Deviations from Plan

**1. [Skip] `docker build --check docling-pipeline/`**
- **Found during:** Verification step.
- **Issue:** Docker daemon không sẵn sàng trên môi trường dev Windows hiện tại (chưa khởi động Docker Desktop), không thể chạy `docker build --check`.
- **Resolution:** Defer verify image build sang Plan 02-08 smoke test (đã ghi nhận trong CONTEXT mục Rủi ro 1 + plan output gốc đã note "có thể defer verify này nếu mạng yếu"). KHÔNG ảnh hưởng skeleton — Dockerfile syntax đã review tay đúng spec CONTEXT mục A.
- **Files modified:** Không có.
- **Commit:** N/A.

**2. [Note] Encoding khi verify config.py trên Windows**
- **Found during:** Verification step.
- **Issue:** `python -c "open('config.py').read()"` mặc định Windows dùng cp1252 → UnicodeDecodeError vì comment tiếng Việt trong `config.py`.
- **Resolution:** Thêm `encoding='utf-8'` vào lệnh verify. KHÔNG đổi file — file đã chuẩn UTF-8 (Docling service deploy trong Docker Linux luôn UTF-8 default).
- **Files modified:** Không có (chỉ đổi câu lệnh verify).

## Known Stubs

Không có stub. Toàn bộ file skeleton đều có chức năng rõ ràng — `__init__.py` rỗng là chuẩn Python package marker, không phải stub.

## Threat Flags

Không phát hiện threat surface mới. Skeleton chưa có endpoint, chưa nhận input — toàn bộ trust boundary surface sẽ xuất hiện ở Plan 02-06 (api/process.py) và sẽ được khai báo `<threat_model>` trong plan đó.

## Next Step

Wave 2: Plan 02-03 (Docling Extractor wrapper), Plan 02-04 (HybridChunker wrapper), Plan 02-05 (Serializer DoclingDocument → response schema) có thể chạy song song. Trước đó: Plan 02-02 (docker-compose.yml root + README) là Wave 1 còn lại.

## Self-Check: PASSED

- File `docling-pipeline/Dockerfile` → FOUND.
- File `docling-pipeline/pyproject.toml` → FOUND.
- File `docling-pipeline/.gitignore` → FOUND.
- File `docling-pipeline/.env.example` → FOUND.
- File `docling-pipeline/src/docling_pipeline/config.py` → FOUND.
- File `docling-pipeline/src/docling_pipeline/api/__init__.py` → FOUND (W3 gate ✓).
- File `docling-pipeline/src/docling_pipeline/core/__init__.py` → FOUND (W3 gate ✓).
- File `docling-pipeline/src/docling_pipeline/observability/__init__.py` → FOUND (W3 gate ✓).
- File `docling-pipeline/tests/__init__.py` → FOUND.
- File `docling-pipeline/tests/fixtures/.gitkeep` → FOUND.
- Commit `79134f3` → FOUND in `git log`.
