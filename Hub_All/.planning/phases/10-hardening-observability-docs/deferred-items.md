# Deferred Items — Phase 10

Items discovered during Phase 10 execution that are out of scope for the
current plan but should be tracked for future resolution.

## DEF-10-01-A: `tests/integration/test_eval_pipeline.py` collect error — missing `psycopg`

**Discovered:** 2026-05-21 trong Plan 10-01 Task 2 regression check.

**Symptom:**
```
ImportError while importing test module 'tests/integration/test_eval_pipeline.py'.
File "...api/.venv/Lib/site-packages/...":
File "...eval/lib.py":19: in <module>
    import psycopg
E   ModuleNotFoundError: No module named 'psycopg'
```

**Root cause:** `tests/integration/test_eval_pipeline.py` (Plan 09-05) inject
`sys.path` để import `eval.lib`. `eval/lib.py` import `psycopg` (Plan 09-02) —
nhưng `psycopg` chỉ install trong `eval/.venv` (eval project độc lập với
`api/.venv`). Khi `api/.venv` collect test → ImportError.

**Pre-existing — KHÔNG do Plan 10-01.** Verify: `git log --oneline --
tests/integration/test_eval_pipeline.py` → file thêm bởi Plan 09-05 (`717b53b`).

**Workaround dùng tạm:** `pytest --ignore=tests/integration/test_eval_pipeline.py`.

**Resolution options:**
1. Thêm `psycopg[binary]>=3,<4` vào `api/pyproject.toml` `[project.optional-dependencies].dev`
   — đơn giản nhất, install thêm 1 dep vào api/.venv.
2. Tách `test_eval_pipeline.py` ra ngoài `tests/` thường — chỉ chạy qua
   `make eval-smoke` thay vì `pytest -m critical`.
3. Lazy import `psycopg` trong `eval/lib.py` (chỉ khi gọi function nào dùng nó).

**Phase target:** Plan 10-03 (HARD-03 — integration test suite ≥50% coverage) —
sẽ phải fix vì Plan 10-03 chạy pytest -m critical đủ collection để đo coverage.

## DEF-10-01-B: Các service module khác trong `api/app/services/` vẫn dùng `logging.getLogger`

**Discovered:** 2026-05-21 trong Plan 10-01 Task 2 refactor `documents_service.trigger_cocoindex_update`.

**Scope HARD-01 Plan 10-01:** CHỈ propagate request_id xuống cocoindex flow
(`trigger_cocoindex_update` — function chạy trong FastAPI BackgroundTask cần
ContextVar carry sang). Các function khác trong `documents_service.py` (service
method synchronous gọi từ router scope) + các module `app/services/*.py` khác
vẫn dùng `logger = logging.getLogger(__name__)` — log entry KHÔNG có request_id
field qua structlog ContextVar processor.

**Tác động:** Log entry từ service method (vd `document_delete`, `audit_flush`)
ra stdout dạng stdlib logging format (KHÔNG JSON, KHÔNG request_id). Vẫn được
Docker capture nhưng ops dashboard Loki/Datadog parse được sẽ thiếu correlation.

**Resolution:** Migrate dần các module service sang `structlog.get_logger`
trong v4.0 (defer trong M2 — comprehensive coverage out of scope theo PROJECT).
Phase 10 chỉ cần verify cocoindex BackgroundTask carry request_id (đã DONE).

**Workaround dùng tạm:** structlog ProcessorAdapter wrap stdlib logger nếu cần
migrate full (out of scope Plan 10-01).
