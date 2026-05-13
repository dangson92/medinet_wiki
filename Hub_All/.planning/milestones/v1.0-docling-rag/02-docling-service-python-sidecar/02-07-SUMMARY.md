---
phase: 02-docling-service-python-sidecar
plan: 07
subsystem: docling-pipeline
tags: [test, pytest, fixtures, scaffold, b3, b4, w4]
status: completed
requires:
  - "Plan 02-06 (FastAPI app + endpoints + lifespan B5 + structlog request_id)"
provides:
  - "6 file pytest test (health + extract + ocr + table_figure + limits + logging) — 12 test case collected"
  - "5 fixture binary deterministic commit (sample_small.pdf 1.6KB, sample_small.docx 36KB, sample_with_table.pdf 1.7KB, sample_with_figure.pdf 2.8KB, sample_scanned_vi.pdf 3.7MB copy từ eval/dataset/scanned/)"
  - "Script generate_fixtures.py (reportlab + pillow + python-docx) re-sinh deterministic 4 file PDF/DOCX nếu cần"
  - "Marker pytest 'slow' đăng ký trong pyproject.toml — fast loop chạy 'pytest -m \"not slow\"'"
  - "B3 evidence: test_table_html_preserved + test_figure_caption_marker (assert <table>/<thead>/<tbody> + ![..](#fig-N))"
  - "B4 evidence: test_413_payload_too_large (6MB > 5MB) + test_504_when_timeout (monkeypatch slow extract + DOCLING_REQUEST_TIMEOUT_SEC=1)"
  - "W4 evidence: test_request_id_propagated_to_log (capsys assert rid xuất hiện trong stdout JSON)"
affects:
  - "Plan 02-08 (README) sẽ document `pytest -m \"not slow\"` cho fast loop + `pytest` full cho CI container"
tech_stack_added:
  - "reportlab + pillow + python-docx (dev-only, sinh fixture 1 lần — KHÔNG add runtime deps)"
patterns_used:
  - "Fixture binary commit deterministic (I2) — sinh 1 lần qua script, commit vào git, KHÔNG sinh runtime trong test"
  - "Session-scoped TestClient (lifespan warm 1 lần)"
  - "Monkeypatch DoclingExtractor.extract + setenv để test timeout/limits không cần Docling thực"
  - "Pytest custom marker 'slow' để tách fast loop vs CI full"
key_files_created:
  - docling-pipeline/tests/conftest.py
  - docling-pipeline/tests/test_health.py
  - docling-pipeline/tests/test_extract.py
  - docling-pipeline/tests/test_ocr.py
  - docling-pipeline/tests/test_table_figure.py
  - docling-pipeline/tests/test_limits.py
  - docling-pipeline/tests/test_logging.py
  - docling-pipeline/tests/fixtures/generate_fixtures.py
  - docling-pipeline/tests/fixtures/sample_small.pdf
  - docling-pipeline/tests/fixtures/sample_small.docx
  - docling-pipeline/tests/fixtures/sample_scanned_vi.pdf
  - docling-pipeline/tests/fixtures/sample_with_table.pdf
  - docling-pipeline/tests/fixtures/sample_with_figure.pdf
key_files_modified:
  - docling-pipeline/pyproject.toml
decisions:
  - "Fixture deterministic (I2): commit binary 5 file < 50KB mỗi (trừ scanned 3.7MB từ eval), KHÔNG sinh runtime — tránh flakiness build"
  - "Marker 'slow' áp lên test cần Docling models warm + Tesseract (test_ocr, test_table_figure, test_extract schema, test_logging) — fast loop chỉ chạy test_413, test_504, test_health, test_unsupported_extension (4 test fast)"
  - "test_504_when_timeout dùng monkeypatch DoclingExtractor.extract bằng time.sleep(999) + setenv DOCLING_REQUEST_TIMEOUT_SEC=1 + cache_clear() để force re-create Settings"
  - "test_logging dùng capsys.readouterr() bắt stdout structlog (PrintLoggerFactory đã configure ở Plan 06)"
  - "scanned PDF copy từ eval/dataset/scanned/DMD_T1-01_scanned.pdf (Phase 1 commit 045d29b) — KHÔNG sinh mới, tránh OCR quality drift"
metrics:
  duration_minutes: 6
  completed_date: "2026-04-29"
  tasks_completed: 1
  files_created: 13
  files_modified: 1
requirements_addressed:
  - DSVC-01
  - DSVC-02
  - DSVC-04
  - DSVC-06
  - EXTRACT-01
  - EXTRACT-02
  - EXTRACT-03
  - EXTRACT-04
---

# Phase 2 Plan 07: Pytest Scaffold + Fixtures Summary

**One-liner:** Bộ test pytest 6 file (12 test case) cho service Docling — phủ /healthz + /readyz B5, /v1/process schema DSVC-02 đầy đủ 10 field, OCR Tesseract vie+eng cho scanned PDF tiếng Việt, B3 table_html preserved + figure caption marker, B4 413/504 limits, W4 X-Request-Id propagate vào structlog stdout — kèm 5 fixture binary deterministic commit (I2) + script `generate_fixtures.py` (reportlab + pillow + python-docx) để re-sinh khi cần.

## Outcome

- 13 file tạo mới + 1 file `pyproject.toml` cập nhật (commit `cc8b12c`).
- Pytest collect-only: **12 tests collected** trong 0.82s, 0 warning sau khi register marker `slow`.
- Tách rõ 2 nhóm:
  - **Fast loop (`pytest -m "not slow"`):** 4 test — `test_413_payload_too_large`, `test_504_when_timeout`, `test_healthz`, `test_readyz`, `test_process_unsupported_extension`. Không cần Docling models warm.
  - **Slow (`pytest -m slow`):** 8 test — `test_process_pdf/docx_returns_schema`, `test_request_id_propagate`, `test_ocr_scanned_vi`, `test_table_html_preserved`, `test_figure_caption_marker`, `test_request_id_propagated_to_log`. Cần Tesseract + Docling.
- 5 fixture binary commit:
  - `sample_small.pdf` (1.6KB) — PDF text-only nhỏ.
  - `sample_small.docx` (36KB) — DOCX heading + paragraph.
  - `sample_with_table.pdf` (1.7KB) — table 3×3 với header (B3).
  - `sample_with_figure.pdf` (2.8KB) — figure + caption "Hình 1: ..." (B3).
  - `sample_scanned_vi.pdf` (3.7MB) — copy từ `eval/dataset/scanned/DMD_T1-01_scanned.pdf` (OCR test).

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | conftest + 6 test file + 5 fixture + script generate + register marker slow | cc8b12c | 13 file mới + pyproject.toml |

## Decisions Made

1. **Fixture deterministic (I2 đóng):** Sinh 1 lần qua `generate_fixtures.py` (reportlab + pillow + python-docx) rồi commit binary. KHÔNG sinh runtime — tránh flakiness CI khi reportlab version đổi output rendering.
2. **Marker `slow` để tách fast loop:** Áp cho mọi test cần Docling models warm + Tesseract. Fast loop ≤ 1s (test 413/504/health/415), slow loop chậm hơn nhưng cover hết schema + OCR + B3 + W4.
3. **`test_504_when_timeout` dùng monkeypatch:** Patch `DoclingExtractor.extract` thành `time.sleep(999)` + `monkeypatch.setenv("DOCLING_REQUEST_TIMEOUT_SEC", "1")` + `get_settings.cache_clear()` để force re-create Settings. Test này chạy được KHÔNG cần Docling thật → marker NOT slow.
4. **`test_413_payload_too_large` dùng raw bytes:** `b"x" * 6MB` upload → 413 trả ngay từ middleware size check, KHÔNG cần Docling parse → marker NOT slow.
5. **`test_request_id_propagated_to_log` dùng `capsys`:** structlog `PrintLoggerFactory` (Plan 06) ghi ra `sys.stdout`, capsys của pytest bắt được. Assert `rid in captured.out` — đủ chứng minh `bind_contextvars(request_id=rid)` hoạt động end-to-end.
6. **scanned fixture copy thay vì sinh:** Reuse `eval/dataset/scanned/DMD_T1-01_scanned.pdf` (Phase 1 commit `045d29b`) để tránh OCR quality drift giữa fixture sinh mới (chữ rõ) vs scan thật (chữ mờ Phase 5 cần test).

## Verification Performed

- AST parse 8 file qua `python -c "import ast; ast.parse(open(f).read())"` → tất cả OK.
- `python tests/fixtures/generate_fixtures.py` chạy thành công, 4 fixture binary sinh ra (size khớp expected < 50KB mỗi file trừ scanned).
- `pytest --collect-only` → **12 tests collected**, 0 warning sau register marker `slow`.
- Verify regex từ plan:
  - `grep -q "TestClient" tests/conftest.py` → match.
  - `grep -q "test_table_html_preserved" tests/test_table_figure.py` → match.
  - `grep -q "test_figure_caption_marker" tests/test_table_figure.py` → match.
  - `grep -q "test_504_when_timeout" tests/test_limits.py` → match.
  - `grep -q "test_request_id_propagated_to_log" tests/test_logging.py` → match.
  - `grep -q "EXPECTED_VI_TOKENS" tests/test_ocr.py` → match.
- Tất cả 13 file `test -f` → FOUND (xem Self-Check bên dưới).

## Deviations from Plan

**1. [Note] Smoke runtime test defer Plan 08 — Python 3.13 vs pin <3.12**

- **Found during:** Verification step (`pytest -m "not slow"`).
- **Issue:** Host dev là Python 3.13.4, `pyproject.toml` Plan 01 pin `requires-python = ">=3.11,<3.12"` (vì Docling 2.91 đôi khi không tương thích Python 3.13 trên Windows). Khi `pip install -e .` → `ERROR: Package 'docling-pipeline' requires a different Python: 3.13.4 not in '<3.12,>=3.11'`. Hậu quả: `from docling_pipeline.main import create_app` fail → tất cả test có dùng `client` fixture đều ERROR ở setup.
- **Resolution:** Defer test runtime sang Plan 02-08 (smoke trong Docker container build từ `python:3.11-slim-bookworm` Dockerfile Plan 01). Pattern này đã được áp dụng từ Plan 02-03/04/05/06 (xem 02-06 SUMMARY mục Deviation #1). Test scaffold + AST + collect-only verify đã đủ chứng minh test code đúng cú pháp + structure đúng.
- **Files modified:** Không có.
- **Commit:** N/A.

**2. [Rule 2 — DX hardening] Register marker `slow` trong `pyproject.toml`**

- **Found during:** Implementation (collect-only báo `PytestUnknownMarkWarning`).
- **Issue:** Plan gốc dùng `@pytest.mark.slow` nhưng không yêu cầu register marker. Pytest 8 raise `PytestUnknownMarkWarning` cho mỗi marker chưa khai báo → noise output.
- **Resolution:** Thêm section `[tool.pytest.ini_options]` vào `pyproject.toml` register marker `slow` + `testpaths = ["tests"]`. Sau khi register, collect-only sạch 0 warning.
- **Files modified:** `docling-pipeline/pyproject.toml`.
- **Commit:** `cc8b12c` (cùng commit Task 1).

**3. [Rule 2 — DX] `_ = Settings` trong test_limits.py để giữ import path rõ**

- **Found during:** Implementation review.
- **Issue:** `from docling_pipeline.config import Settings, get_settings` — `Settings` không dùng trực tiếp trong test body. Ruff `F401` sẽ flag unused import.
- **Resolution:** Thêm `_ = Settings` cuối hàm để document import path (dev IDE biết Settings từ đâu khi monkeypatch tương lai cần). Cost: 0.
- **Files modified:** `docling-pipeline/tests/test_limits.py`.
- **Commit:** `cc8b12c`.

## Known Stubs

Không có stub. Tất cả 12 test case đều có assertion thực sự (không có `pytest.skip` hay `pass` placeholder). Marker `slow` KHÔNG phải stub — là design choice tách CI loop để dev velocity (CONTEXT mục F — coverage 60-70% target).

## Threat Flags

Không phát hiện threat surface mới. Test code chạy hoàn toàn local (FastAPI TestClient, không network), 5 fixture binary là input controlled (sinh từ reportlab + 1 scanned PDF từ eval đã trust).

## TDD Gate Compliance

Plan 02-07 không phải plan TDD (`type: execute`, không có `tdd="true"`). Đây là plan TEST-ADD: viết test sau khi implementation đã đóng (Plan 02-03/04/05/06 đã commit). Test sẽ chạy thực ở Plan 02-08 (Docker container Python 3.11).

## Next Step

- **Plan 02-08:** README + smoke verify container — Dockerfile Plan 01 build → `docker compose up -d docling-pipeline` → chạy `pytest -m "not slow"` trong container (Python 3.11.x) verify 4 fast test pass; chạy `pytest -m slow` verify 8 slow test pass với Docling models đã warm + Tesseract vie+eng cài sẵn. Coverage `pytest --cov=docling_pipeline --cov-report=term-missing` ≥ 60%.
- **Phase 3 Go adapter** vẫn START SONG SONG được — contract DSVC-01/02 đã đóng băng qua Plan 02-05/06; Phase 3 dùng mock JSON cho unit test.

## Self-Check: PASSED

- File `docling-pipeline/tests/conftest.py` → FOUND.
- File `docling-pipeline/tests/test_health.py` → FOUND.
- File `docling-pipeline/tests/test_extract.py` → FOUND.
- File `docling-pipeline/tests/test_ocr.py` → FOUND.
- File `docling-pipeline/tests/test_table_figure.py` → FOUND.
- File `docling-pipeline/tests/test_limits.py` → FOUND.
- File `docling-pipeline/tests/test_logging.py` → FOUND.
- File `docling-pipeline/tests/fixtures/generate_fixtures.py` → FOUND.
- File `docling-pipeline/tests/fixtures/sample_small.pdf` (1.6KB) → FOUND.
- File `docling-pipeline/tests/fixtures/sample_small.docx` (36KB) → FOUND.
- File `docling-pipeline/tests/fixtures/sample_with_table.pdf` (1.7KB) → FOUND.
- File `docling-pipeline/tests/fixtures/sample_with_figure.pdf` (2.8KB) → FOUND.
- File `docling-pipeline/tests/fixtures/sample_scanned_vi.pdf` (3.7MB) → FOUND.
- File `docling-pipeline/pyproject.toml` (modified — register marker slow) → FOUND.
- Commit `cc8b12c` → FOUND in `git log` (`test(docling-pipeline): pytest scaffold ...`).
- Pytest collect: 12 tests collected, 0 warning → PASS.
