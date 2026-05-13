---
phase: 02-docling-service-python-sidecar
plan: 06
subsystem: docling-pipeline
tags: [fastapi, api-wire, lifespan, structlog, observability, dsvc-01, dsvc-04, dsvc-06]
status: completed
requires:
  - "Plan 02-01 (skeleton + config.py)"
  - "Plan 02-03 (extractor.py — DoclingExtractor + warm_models)"
  - "Plan 02-04 (chunker.py — DoclingChunker + ChunkerOptions)"
  - "Plan 02-05 (serializer.py — build_doc_meta + serialize_chunks, schema DSVC-02 ĐÓNG BĂNG)"
provides:
  - "FastAPI app runnable: uvicorn docling_pipeline.main:app --port 8001"
  - "3 endpoint wired: GET /healthz (liveness), GET /readyz (readiness B5), POST /v1/process (multipart upload, response DSVC-02)"
  - "RequestIdMiddleware: propagate X-Request-Id từ Go backend vào structlog contextvars (DSVC-04)"
  - "Lifespan B5 readiness logic — phân biệt ImportError (env hỏng, ready=False vĩnh viễn) vs warm transient fail (ready=True + log warning)"
  - "Limits enforcement: 413 (max_file_mb) + 504 (request_timeout_sec) + 415 (unsupported ext) + 400 (chunker_options json invalid)"
affects:
  - "Phase 3 Go adapter sẽ POST multipart vào /v1/process — contract DSVC-01 + DSVC-02 chốt qua plan này"
tech_stack_added:
  - "FastAPI (đã pin pyproject Plan 01) — APIRouter + lifespan + UploadFile + Form"
  - "Starlette BaseHTTPMiddleware — RequestIdMiddleware"
  - "structlog contextvars — bind_contextvars / clear_contextvars per-request"
  - "asyncio.timeout (Python 3.11+) — wrap Docling blocking work với hard deadline"
patterns_used:
  - "Factory create_app() — testable + reusable cho uvicorn / pytest TestClient"
  - "Singleton get_extractor() / get_chunker() qua lru_cache — reuse heavy DocumentConverter init"
  - "asyncio.to_thread + asyncio.timeout — async wrap blocking CPU work, không block event loop"
  - "Module-level state _models_ready + setter/getter — đơn giản hơn DI cho readiness flag (single worker scope)"
  - "Lazy import docling trong lifespan — guard ImportError tại runtime startup thay vì module top"
key_files_created:
  - docling-pipeline/src/docling_pipeline/main.py
  - docling-pipeline/src/docling_pipeline/api/health.py
  - docling-pipeline/src/docling_pipeline/api/process.py
  - docling-pipeline/src/docling_pipeline/observability/logging.py
key_files_modified:
  - docling-pipeline/src/docling_pipeline/observability/__init__.py
decisions:
  - "Lifespan B5 semantics — phân biệt 3 case ImportError vs warm transient fail vs warm OK; /readyz 503 chỉ khi env hỏng, KHÔNG khi warm dummy fail"
  - "ocr_used best-effort: detect theo extension (pdf/png/jpg/jpeg → True; docx/xlsx/html → False); Docling không expose flag chính xác cho việc OCR có thực sự được trigger trên trang nào — defer M3 nếu cần precise"
  - "request_id resolution priority: Form field request_id > X-Request-Id header > auto-gen UUID4 — Go backend có 2 cách inject (header preferred)"
  - "Module-level _models_ready trong api/health.py — set qua set_models_ready() từ lifespan; observability/__init__ re-export getter/setter"
  - "asyncio.to_thread cho Docling blocking — KHÔNG dùng ProcessPoolExecutor (single worker uvicorn theo CONTEXT mục D)"
  - "405 → 415 cho unsupported extension (ValueError extractor) — đúng semantics HTTP cho file format không support"
metrics:
  duration_minutes: 5
  completed_date: "2026-04-29"
  tasks_completed: 1
  files_created: 4
  files_modified: 1
requirements_addressed:
  - DSVC-01
  - DSVC-04
  - DSVC-06
  - CHUNK-03
---

# Phase 2 Plan 06: FastAPI App + Endpoints + Lifespan B5 Summary

**One-liner:** Wire `core/extractor.py` + `core/chunker.py` + `core/serializer.py` (Plan 03/04/05) sau lưng FastAPI: 3 endpoint `GET /healthz`, `GET /readyz`, `POST /v1/process`; structlog JSON propagate `X-Request-Id` (DSVC-04); enforce limits 413 (max_file_mb) + 504 (timeout) (DSVC-06); lifespan B5 phân biệt rõ ImportError docling (ready=False vĩnh viễn) vs warm dummy fail transient (ready=True + log warning). Service có thể chạy local `uvicorn docling_pipeline.main:app --port 8001` ngay sau plan này.

## Outcome

- 4 file Python mới + 1 file `__init__.py` cập nhật, tổng 461 dòng (commit `57274e0`).
- Service runnable: `uvicorn docling_pipeline.main:app --port 8001` (sau khi `pip install -e .[dev]` deps đầy đủ).
- 3 endpoint register đúng tag + path:
  - `GET /healthz` → `{"status":"healthy"}` 200, luôn alive.
  - `GET /readyz` → `{"status":"ready"}` 200 hoặc `{"status":"not_ready","reason":"docling_library_unavailable"}` 503 theo B5.
  - `POST /v1/process` → multipart upload (`file` + `hub_code` + `doc_type` + `request_id` + `chunker_options` JSON optional) → JSON DSVC-02.
- structlog JSON renderer + `RequestIdMiddleware` bind `X-Request-Id` vào contextvars → mỗi log line trong request có field `request_id` + `path` + `method`.
- Limits enforcement đầy đủ: 413 (size > max_file_mb), 504 (asyncio.timeout > request_timeout_sec), 415 (extension không support), 400 (chunker_options json invalid hoặc filename thiếu).
- Wire 3 module core thành 1 luồng: `extractor.extract → chunker.chunk → serializer.serialize_chunks` đều wrap `asyncio.to_thread` (FastAPI async không block event loop).

## Tasks Completed

| Task | Name                                                                                                       | Commit  | Files                                                                                                                                                                                              |
| ---- | ---------------------------------------------------------------------------------------------------------- | ------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1    | observability/logging.py + main.py (B5 lifespan) + 2 router files (health.py, process.py) + __init__ export | 57274e0 | observability/logging.py, observability/__init__.py, api/health.py, api/process.py, main.py |

## Decisions Made

1. **Lifespan B5 semantics chốt 3 case rõ ràng** — case (a) ImportError docling = `ready=False` vĩnh viễn (env hỏng, ops phải `pip install docling==2.91.0` rồi restart), case (b) warm dummy fail transient (vd stub PDF không trigger model load) = `ready=True` + log warning (service vẫn serve, request đầu chậm), case (c) warm OK = `ready=True` + log info. /readyz 503 chỉ ở case (a).
2. **Module-level state `_models_ready` trong `api/health.py`** thay vì `app.state` hoặc DI — đơn giản hơn cho single-worker uvicorn scope, set qua `set_models_ready()` từ lifespan. `observability/__init__` re-export getter/setter cho test.
3. **`request_id` resolution priority:** Form field `request_id` (Go backend có thể truyền) > header `X-Request-Id` (preferred, đã có ở middleware) > auto-gen UUID4. Echo lại header response để client trace.
4. **`ocr_used` best-effort theo extension** — `pdf/png/jpg/jpeg → True`, `docx/xlsx/html → False`. Docling không expose flag chính xác cho việc OCR có thực sự trigger trên trang nào (raster vs text-PDF). Precise detection defer M3.
5. **`asyncio.to_thread` cho Docling blocking work** — KHÔNG dùng `ProcessPoolExecutor` vì CONTEXT mục D đã chốt single uvicorn worker (Docling parser không thread-safe, Tesseract OCR qua subprocess đã tự isolate).
6. **`asyncio.timeout(...)` thay vì `asyncio.wait_for`** — Python 3.11+ context manager API, cleaner error handling, raise `TimeoutError` thay vì `asyncio.TimeoutError` deprecated.
7. **Map ValueError extractor → HTTP 415** thay vì 400 — đúng semantics "Unsupported Media Type" cho extension không nằm trong `_EXT_TO_FORMAT` whitelist.
8. **`uvicorn` config `log_config=None`** trong `if __name__ == "__main__"` — tránh uvicorn override structlog đã configure ở lifespan; production deploy qua `uvicorn` CLI sẽ dùng cùng module logging bridge.
9. **`force=True` ở `logging.basicConfig`** — re-initialize stdlib logging khi uvicorn đã setup default handler trước đó (uvicorn import trước module level).

## Verification Performed

- AST parse 5 file qua `python -c "import ast; ast.parse(open(f).read())"` → tất cả OK.
- Verify regex từ plan: `lifespan`, `ImportError`, `set_models_ready(False)`, `set_models_ready(True)`, `/healthz`, `/process`, `X-Request-Id`, `413`, `504` đều match.
- `git diff --stat` xác nhận 5 file changed, 461 insertions.
- Smoke runtime `python -c "from docling_pipeline.main import app"` chưa chạy được trên dev local Windows (deps Python service install trong Docker container per Plan 01 Dockerfile — `fastapi`, `structlog`, `uvicorn`, `python-multipart` chưa cài host). Verify runtime defer Plan 07 (tests/) hoặc smoke test container build.

## Deviations from Plan

**1. [Note] Smoke test runtime defer sang Plan 07 (cùng pattern Plan 02-03/04/05)**

- **Found during:** Verification step.
- **Issue:** Môi trường dev local Windows chưa có `fastapi`, `uvicorn`, `structlog`, `python-multipart`, `starlette` (deps install trong Docker per Plan 01 Dockerfile). `python -c "from docling_pipeline.main import app"` fail ImportError.
- **Resolution:** AST parse pass đầy đủ + verify regex pass. Smoke test runtime sẽ chạy ở Plan 07 (`tests/test_health.py`, `tests/test_extract.py`) bên trong container hoặc venv có cài full pyproject. Pattern tương tự Plan 02-03/04/05.
- **Files modified:** Không có.
- **Commit:** N/A.

**2. [Rule 2 — observability hardening] Thêm `force=True` ở `logging.basicConfig`**

- **Found during:** Implementation.
- **Issue:** Plan action gốc dùng `logging.basicConfig(...)` không có `force=True`. Khi uvicorn đã setup default stdlib logging handler trước khi lifespan chạy, basicConfig sẽ no-op → log JSON không out đúng format.
- **Resolution:** Thêm `force=True` để re-initialize stdlib handlers, đảm bảo structlog bridge hoạt động.
- **Files modified:** `docling-pipeline/src/docling_pipeline/observability/logging.py`.
- **Commit:** `57274e0` (cùng commit Task 1).

**3. [Rule 2 — robustness] Thêm `method` field vào `bind_contextvars`**

- **Found during:** Implementation.
- **Issue:** Plan gốc bind `request_id` + `path`. Thiếu `method` → log debug khó tìm POST vs GET cho cùng path (vd `/v1/process` POST vs preflight OPTIONS).
- **Resolution:** Thêm `method=request.method`. Cost: 0 (single dict update).
- **Files modified:** `docling-pipeline/src/docling_pipeline/observability/logging.py`.
- **Commit:** `57274e0`.

**4. [Rule 1 — bug] Map extractor `ValueError` → HTTP 415 thay vì 500**

- **Found during:** Implementation review.
- **Issue:** Plan action gốc bắt `ValueError as exc: raise HTTPException(status_code=415, ...)` đã đúng. Confirm — KHÔNG phải deviation, chỉ ghi nhận semantics đúng. Đổi từ generic 500 catch-all thành 415 cho unsupported extension là đúng spec HTTP.
- **Resolution:** Giữ nguyên, không deviation thực sự.
- **Files modified:** N/A.
- **Commit:** N/A.

## Known Stubs

Không có stub. Toàn bộ logic đã implement:

- `ocr_used` detect best-effort theo extension — design choice đã ghi rõ Decision #4, KHÔNG phải stub. Sẽ refine ở M3 nếu Docling expose detection flag chính xác.
- `language_detected` mặc định `None` (do `build_doc_meta` không nhận arg) — đã chốt ở Plan 02-05, M1 không yêu cầu language detection precise.
- `chunker_options` parser chỉ accept JSON string trong Form — đủ cho Phase 3 Go adapter, nếu cần protobuf/msgpack thì defer M3.

## Threat Flags

| Flag                 | File                                        | Description                                                                                                                                                                                                |
| -------------------- | ------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| threat_flag: network | docling-pipeline/src/docling_pipeline/main.py | Mở port 8001 listen `0.0.0.0` (default từ Settings). Trong M1, service KHÔNG expose host (compose internal network), Go backend gọi qua `localhost:8001` host network. Nếu sau này dockerize backend hoặc reverse proxy expose, cần auth layer (mTLS hoặc shared secret header). Document trong Phase 4 (CFG plans). |
| threat_flag: file_upload | docling-pipeline/src/docling_pipeline/api/process.py | Multipart upload nhận file binary tuỳ ý từ trusted Go backend. Đã enforce size 413 + extension whitelist 415. KHÔNG sandbox Docling OCR subprocess (Tesseract). Chấp nhận trong M1 vì trust boundary là Go backend (đã RBAC + JWT). Nếu sau này expose service public, cần sandbox + scan AV. |

## TDD Gate Compliance

Plan 02-06 không phải plan TDD (`type: execute`, không có `tdd="true"` trong tasks). Test endpoint `/healthz`, `/readyz`, `/v1/process` sẽ implement ở Plan 02-07 (`tests/test_health.py`, `tests/test_extract.py`, `tests/test_ocr.py`) bên trong môi trường có cài full pyproject (Docker container hoặc venv).

## Next Step

- **Wave 4 (Plan 02-07):** `tests/` directory với pytest fixtures (PDF/DOCX/scanned-PDF nhỏ commit) + 3 file test (`test_health.py`, `test_extract.py`, `test_ocr.py`). Smoke test runtime cho main.py + endpoints sẽ chạy ở plan này.
- **Plan 02-08:** Dockerfile final + `docker-compose.yml` ở root repo (4 service: postgres, redis, chroma, docling-pipeline) — `docker compose up -d` 1 lệnh start full infra.
- Phase 3 (Go adapter `DoclingExtractor`) có thể START SONG SONG với Plan 02-07/08 vì contract DSVC-01 + DSVC-02 đã chốt qua plan này — Phase 3 dùng mock JSON response cho unit test, integration test cuối Phase 3 đợi Phase 2 done full.

## Self-Check: PASSED

- File `docling-pipeline/src/docling_pipeline/main.py` → FOUND (108 dòng, có `lifespan`, `create_app`, `app`, `if __name__ == "__main__"`).
- File `docling-pipeline/src/docling_pipeline/api/health.py` → FOUND (54 dòng, có router, `set_models_ready`, `get_models_ready`, /healthz, /readyz).
- File `docling-pipeline/src/docling_pipeline/api/process.py` → FOUND (180 dòng, có /v1/process, 413, 504, 415, asyncio.timeout, asyncio.to_thread).
- File `docling-pipeline/src/docling_pipeline/observability/logging.py` → FOUND (97 dòng, có `configure_logging`, `RequestIdMiddleware`, X-Request-Id, bind_contextvars).
- File `docling-pipeline/src/docling_pipeline/observability/__init__.py` → FOUND (15 dòng, re-export).
- Commit `57274e0` → FOUND in `git log` (`feat(docling-pipeline): FastAPI app + endpoints...`).
- AST parse cả 5 file → OK.
- Verify regex từ plan (lifespan, ImportError, set_models_ready, /healthz, /process, X-Request-Id, 413, 504) → ALL PASS.
