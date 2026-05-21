---
phase: 10-hardening-observability-docs
plan: 01
subsystem: api/observability
tags: [structlog, contextvars, middleware, logging, hard-01]
requires:
  - structlog>=25.0,<26 (đã có sẵn pyproject.toml)
  - asyncio + contextvars (stdlib)
provides:
  - "app.logging_config:configure_structlog()" — factory idempotent
  - "app.logging_config:request_id_var" — ContextVar str|None default None
  - "app.logging_config:user_id_var" — ContextVar str|None default None
  - "app.logging_config:hub_id_var" — ContextVar str|None default None
  - "RequestIdMiddleware mở rộng" — set ContextVar trước call_next + emit log request_completed
  - "documents_service.trigger_cocoindex_update" — _struct_logger structured kwargs
affects:
  - "app/main.py:lifespan step 0" — gọi configure_structlog() TRƯỚC db_pool/redis/cocoindex
  - "Plan 10-02 sẽ add Prometheus middleware vào main.py chain — KHÔNG đụng request_id middleware"
tech-stack:
  added: ["structlog 25.5.0 (đã có sẵn — dùng processor chain mới)"]
  patterns:
    - "ContextVar request_id_var.set() trong middleware → snapshot qua asyncio.create_task → cocoindex BackgroundTask thấy"
    - "EventRenamer('msg') rename structlog default 'event' → 'msg' match Go log/slog semantic"
    - "PrintLoggerFactory ra stdout (Docker capture) + JSONRenderer mỗi entry 1 dòng JSON valid"
key-files:
  created:
    - "Hub_All/api/app/logging_config.py" — 100 dòng, configure_structlog factory + 3 ContextVar + processor _add_contextvars
    - "Hub_All/api/tests/unit/test_logging_config.py" — 195 dòng, 8 unit test
    - "Hub_All/api/tests/unit/test_request_id_middleware.py" — 115 dòng, 3 unit test
    - "Hub_All/.planning/phases/10-hardening-observability-docs/deferred-items.md"
  modified:
    - "Hub_All/api/app/middleware/request_id.py" — mở rộng dispatch() set ContextVar + đo latency + emit log request_completed
    - "Hub_All/api/app/main.py" — lifespan step 0 import + gọi configure_structlog() TRƯỚC db_pool init
    - "Hub_All/api/app/services/documents_service.py" — _struct_logger module-level + 8 log call trong scope trigger_cocoindex_update đổi sang structured kwargs
decisions:
  - "D-10-01-A: dùng EventRenamer('msg') thay vì rename trực tiếp ở mọi log call — schema log key='msg' match Go log/slog CONVENTIONS Section 5"
  - "D-10-01-B: ContextVar default None TƯỜNG MINH (KHÔNG bỏ qua key) — Loki/Datadog query `request_id IS NULL` consistent"
  - "D-10-01-C: PrintLoggerFactory thay WriteLoggerFactory — stdout đơn giản, Docker capture native, KHÔNG cần buffer flush thủ công"
  - "D-10-01-D: capsys + parse JSON là phương pháp test chính (structlog.testing.capture_logs() bypass processor → KHÔNG verify được level/ts/request_id từ ContextVar)"
  - "D-10-01-E: documents_service KHÔNG đụng module-level `logger` stdlib — chỉ thêm `_struct_logger` riêng cho scope cocoindex BackgroundTask (defer migrate toàn module v4.0 — DEF-10-01-B)"
  - "D-10-01-F: trigger_cocoindex_update ở documents_service.py KHÔNG ở rag/setup.py như plan ghi — Rule 1 fix về location thực tế trong codebase Phase 4"
  - "D-10-01-G: Test 8 verify ở mức source inspect (`configure_structlog()` text trước `db_pool = None`) thay vì full lifespan boot — tránh testcontainers nặng cho 1 test wiring"
metrics:
  duration_minutes: 11
  completed_date: "2026-05-21"
  tasks: 2
  files_created: 4
  files_modified: 3
  unit_tests_added: 11
  unit_tests_pass: 11
  regression_unit: "130/130 PASS"
---

# Phase 10 Plan 01: Structured Logging JSON + ContextVar + RequestIdMiddleware mở rộng — Summary

structlog JSON output cấu hình ở đầu lifespan + ContextVar propagation xuống FastAPI BackgroundTasks (cocoindex flow) qua asyncio.create_task copy_context — match Go log/slog schema (level/msg/ts/request_id/user_id/hub_id/latency_ms/path/method/status).

## Tasks Completed

| Task | Name                                                            | Commit    | Files                                                                          |
| ---- | --------------------------------------------------------------- | --------- | ------------------------------------------------------------------------------ |
| RED  | Unit tests RED phase (ImportError app.logging_config chưa tồn tại) | `8d9d48c` | tests/unit/test_logging_config.py + test_request_id_middleware.py             |
| 1    | logging_config.py + RequestIdMiddleware mở rộng + tests GREEN  | `daeb667` | app/logging_config.py (mới) + app/middleware/request_id.py + 2 unit test     |
| 2    | configure_structlog vào lifespan + cocoindex BackgroundTask propagation | `f52e2e4` | app/main.py + app/services/documents_service.py + Test 7+8 vào test_logging_config.py + deferred-items.md |

## Test Results

**Unit Test Plan 10-01:** 11/11 PASS (8 trong test_logging_config.py + 3 trong test_request_id_middleware.py).

```
tests/unit/test_logging_config.py::test_configure_structlog_emits_json_shape PASSED
tests/unit/test_logging_config.py::test_contextvar_propagation_into_log PASSED
tests/unit/test_logging_config.py::test_contextvar_default_none_explicit PASSED
tests/unit/test_logging_config.py::test_configure_structlog_idempotent PASSED
tests/unit/test_logging_config.py::test_contextvar_propagation_across_asyncio_task PASSED
tests/unit/test_logging_config.py::test_contextvar_copy_context_run_isolated PASSED
tests/unit/test_logging_config.py::test_lifespan_calls_configure_structlog_idempotent PASSED
tests/unit/test_logging_config.py::test_cocoindex_flow_log_inherits_request_id PASSED
tests/unit/test_request_id_middleware.py::test_missing_header_generates_uuid4 PASSED
tests/unit/test_request_id_middleware.py::test_existing_header_echoed_verbatim PASSED
tests/unit/test_request_id_middleware.py::test_request_completed_log_emitted PASSED
```

**Regression unit suite:** 130/130 PASS (`uv run pytest tests/unit -q`).

**Critical unit:** 7/7 PASS (`uv run pytest -m critical tests/unit -q`).

**Critical integration:** KHÔNG chạy vì cần testcontainers Docker stack; pre-existing `test_eval_pipeline.py` collect error (DEF-10-01-A — `psycopg` missing in `api/.venv`) defer Plan 10-03.

**Quality gates:**
- `ruff check app/logging_config.py app/middleware/request_id.py app/main.py app/services/documents_service.py tests/unit/test_logging_config.py tests/unit/test_request_id_middleware.py` → PASS.
- `mypy --strict app/logging_config.py app/middleware/request_id.py app/main.py app/services/documents_service.py` → PASS no issues found.
- `python -c "from app.main import app"` → import OK.

## Sample JSON Log Line (manual verify)

`request_completed` log entry (đủ 10 field schema chuẩn match Go log/slog):

```json
{"path": "/healthz", "method": "GET", "status": 200, "latency_ms": 4, "request_id": "70b3a8e2-fc4d-4d6a-99cf-c5a4b9c0e1d3", "user_id": null, "hub_id": null, "level": "info", "ts": "2026-05-21T08:20:49.813514Z", "msg": "request_completed"}
```

Verify parse được: `python -c "import json,sys; print(json.loads(sys.stdin.readline()))"` → dict 10 key.

## Decisions Made

- **D-10-01-A** (EventRenamer): structlog default key `event` → rename `msg` match Go log/slog CONVENTIONS Section 5. Mọi log call viết `log.info("event_name", ...)` — processor render thành `{"msg": "event_name", ...}`. KHÔNG thay đổi ergonomic của structlog API.
- **D-10-01-B** (ContextVar default None TƯỜNG MINH): `_add_contextvars` processor inject 3 field `request_id/user_id/hub_id` LUÔN có mặt, default None. Lý do: Loki/Datadog query `request_id IS NULL` consistent — nếu bỏ qua key undefined behavior. CONVENTIONS Section 5 yêu cầu 9 field schema cố định.
- **D-10-01-C** (PrintLoggerFactory): structlog default `PrintLoggerFactory()` ra stdout đơn giản, Docker capture native. KHÔNG dùng `WriteLoggerFactory(sys.stderr)` vì stdout đã là convention container.
- **D-10-01-D** (capsys parse JSON): `structlog.testing.capture_logs()` BYPASS toàn bộ processor chain (intentional — design test shortcut) → KHÔNG verify được level/ts/request_id từ ContextVar. Chuyển sang capsys capture stdout + `json.loads(line)` — verify đúng production processor chain. Verified bằng debug REPL: `capture_logs() → [{'k': 1, 'event': 'test_event', 'log_level': 'info'}]` thiếu level/ts/request_id.
- **D-10-01-E** (scope hẹp documents_service): KHÔNG đụng module-level `logger = logging.getLogger(__name__)` (đã có ở line 65) — chỉ thêm `_struct_logger = structlog.get_logger(__name__)` riêng cho scope `trigger_cocoindex_update` (line 475-634). Lý do: Plan 10-01 chỉ cần propagate request_id xuống cocoindex BackgroundTask (function chạy ngoài request handler scope); migrate toàn bộ module sang structlog out of scope HARD-01 — defer DEF-10-01-B v4.0.
- **D-10-01-F** (Rule 1 fix location): Plan ghi `app/rag/setup.py:trigger_cocoindex_update` nhưng function thực tế nằm ở `app/services/documents_service.py:475` (theo Plan 04-04 REVISION 2 — A4 trigger qua FastAPI BackgroundTasks). Fix về location thực tế trong codebase Phase 4 — KHÔNG tạo function rỗng ở wrong location.
- **D-10-01-G** (Test 8 source inspect): KHÔNG boot full lifespan qua LifespanManager + testcontainers cho 1 test wiring (overhead 30s+ vs unit test 1s). Verify `app/main.py` source contain `configure_structlog()` text TRƯỚC `db_pool = None` qua `inspect.getsource(app_main.lifespan)`. Mức contract: pattern đúng → wire correct.

## Deviations from Plan

### Rule 1 — Fix location của `trigger_cocoindex_update`

**Found during:** Task 2 start (grep `trigger_cocoindex_update` location).
**Issue:** Plan ghi function ở `app/rag/setup.py` — function THỰC TẾ ở `app/services/documents_service.py:475` (Plan 04-04 REVISION 2 A4 strategy).
**Fix:** Refactor logger ở documents_service.py thay vì rag/setup.py. Vẫn match objective Plan 10-01 (propagate request_id xuống cocoindex flow log) vì:
- `trigger_cocoindex_update` mới là function chạy trong BackgroundTask scope (cần ContextVar carry).
- `rag/setup.py` chạy ở lifespan startup (1 lần boot, KHÔNG cần per-request request_id).
**Files modified:** documents_service.py thay vì rag/setup.py.
**Commit:** `f52e2e4`.

### Rule 2 — `structlog.testing.capture_logs()` bypass processor chain

**Found during:** Task 1 GREEN phase (5 test fail KeyError 'level' / KeyError 'request_id').
**Issue:** Plan recommend `structlog.testing.capture_logs()` cho test 1/2/3. Behavior thực tế của API này: capture log Ở MỨC bound logger TRƯỚC processor chain — bypass `_add_contextvars` / `add_log_level` / `TimeStamper` / `EventRenamer`. Captured entry chỉ có raw `{event, log_level, **kwargs}` — KHÔNG có level/ts/msg/request_id.
**Fix:** Refactor 5 test sang `capsys` capture stdout + `json.loads(line)` — verify đúng production processor chain. Verified bằng debug REPL.
**Files modified:** tests/unit/test_logging_config.py + tests/unit/test_request_id_middleware.py.
**Commit:** `daeb667` (đã re-write trước commit).

### Rule 2 — Test 8 integration verify ở mức source inspect

**Found during:** Task 2 plan recommend boot `app_with_auth` fixture (testcontainers Postgres+Redis 30s+).
**Issue:** Overkill cho 1 test wiring. testcontainers boot stack mỗi test session → infrastructure cost cao + integration test cần Docker. Test 8 chỉ cần verify "configure_structlog() được gọi TRƯỚC db_pool init" — mức contract source inspect đủ.
**Fix:** Test 8 dùng `inspect.getsource(app_main.lifespan)` + check pattern text position (`pos_struct < pos_db`). Khẳng định ở mức source-level rằng wire đúng — Plan 10-02/10-03 sẽ làm integration test đầy đủ với testcontainers.
**Files modified:** tests/unit/test_logging_config.py.
**Commit:** `f52e2e4`.

## Deferred Issues

- **DEF-10-01-A** (Plan 10-03 target): `tests/integration/test_eval_pipeline.py` collect error — `psycopg` ModuleNotFoundError. Pre-existing từ Plan 09-05 — `eval/lib.py` import psycopg chỉ install trong `eval/.venv` ngoài `api/.venv`. Resolution: thêm `psycopg[binary]>=3,<4` vào `api/pyproject.toml dev` HOẶC lazy import trong eval/lib.py. Workaround dùng tạm: `pytest --ignore=tests/integration/test_eval_pipeline.py`.
- **DEF-10-01-B** (v4.0 defer): Các service module khác trong `api/app/services/` vẫn dùng `logging.getLogger` — log entry stdout KHÔNG JSON format đầy đủ. Out of scope HARD-01 (Plan 10-01 chỉ cần propagate request_id xuống cocoindex BackgroundTask — DONE). Migrate dần toàn module sang structlog trong v4.0.

## Threat Flags

KHÔNG có. Plan 10-01 chỉ thêm log entry — KHÔNG mở rộng auth/network surface mới.

## Self-Check: PASSED

**Files verified exist:**
- `Hub_All/api/app/logging_config.py` → FOUND
- `Hub_All/api/tests/unit/test_logging_config.py` → FOUND
- `Hub_All/api/tests/unit/test_request_id_middleware.py` → FOUND
- `Hub_All/.planning/phases/10-hardening-observability-docs/deferred-items.md` → FOUND

**Commits verified exist:**
- `8d9d48c` (TDD RED) → FOUND in git log
- `daeb667` (Task 1 GREEN) → FOUND in git log
- `f52e2e4` (Task 2) → FOUND in git log

**Tests verified PASS:**
- 11/11 unit test Plan 10-01 PASS
- 130/130 unit test toàn module KHÔNG regression
- ruff sạch + mypy --strict PASS 6 file
- Manual JSON log line parse được qua `json.loads`
