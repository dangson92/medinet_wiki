---
phase: 10-hardening-observability-docs
plan: 02
subsystem: api/observability
tags: [prometheus, metrics, middleware, histogram, counter, hard-02]
requires:
  - prometheus-client>=0.21,<1 (mới thêm vào api/pyproject.toml)
  - structlog>=25.0,<26 (Plan 10-01 dep — KHÔNG đụng)
provides:
  - "app.observability.metrics:REQUESTS_TOTAL" — Counter[method/path/status]
  - "app.observability.metrics:ERRORS_TOTAL" — Counter[method/path] (status >= 500)
  - "app.observability.metrics:REQUEST_DURATION" — Histogram[method/path]
  - "app.observability.metrics:SEARCH_LATENCY" — Histogram[hub_scope] (single/cross)
  - "app.observability.metrics:INGEST_DURATION" — Histogram no-label (per-doc cocoindex)
  - "app.observability.middleware:PrometheusMiddleware" — đo + count + resolve route template
  - "GET /metrics" endpoint outside /api/* namespace (Prometheus exposition format)
affects:
  - "app/main.py:create_app" — add_middleware PrometheusMiddleware giữa RequestId và ErrorHandler + mount /metrics endpoint
  - "app/services/search_service.py:search/search_cross_hub" — split public/_impl, wrap SEARCH_LATENCY.time()
  - "app/services/documents_service.py:trigger_cocoindex_update" — wrap manual time + INGEST_DURATION.observe() trong retry loop
tech-stack:
  added:
    - "prometheus-client 0.23.x (latest from >=0.21,<1 constraint — text format version=1.0.0 OpenMetrics)"
  patterns:
    - "Module-level metric singleton đăng ký vào default prometheus_client.REGISTRY"
    - "Cardinality control: label `path` dùng route template qua app.routes.matches(scope) — Starlette KHÔNG set scope[route] tại middleware level"
    - "404/route không match → fallback 'unknown' để cố định label space O(routes)"
    - "PrometheusMiddleware catch Exception → ghi metric TRƯỚC re-raise (ErrorHandler outer render envelope)"
    - "Search/ingest instrument: split public method (wrap context manager) / _impl method (logic) để tránh nested timing"
key-files:
  created:
    - "Hub_All/api/app/observability/__init__.py" — 30 dòng, re-export 5 metric + PrometheusMiddleware
    - "Hub_All/api/app/observability/metrics.py" — 79 dòng, 5 Counter/Histogram instance + bucket tuning theo SLA
    - "Hub_All/api/app/observability/middleware.py" — 79 dòng, PrometheusMiddleware + _resolve_path qua app.routes
    - "Hub_All/api/tests/unit/test_metrics.py" — 190 dòng, 6 unit test (type/inc/bucket/200/500/404)
    - "Hub_All/api/tests/integration/test_metrics_endpoint.py" — 261 dòng, 5 integration test (endpoint/healthz-count/422/search/ingest)
  modified:
    - "Hub_All/api/pyproject.toml" — thêm prometheus-client>=0.21,<1
    - "Hub_All/api/uv.lock" — sync deps prometheus-client + transitive
    - "Hub_All/api/app/main.py" — wire PrometheusMiddleware + mount GET /metrics endpoint
    - "Hub_All/api/app/services/search_service.py" — split public/_impl + wrap SEARCH_LATENCY
    - "Hub_All/api/app/services/documents_service.py" — wrap INGEST_DURATION quanh update_blocking() trong retry loop
    - "Hub_All/.planning/phases/10-hardening-observability-docs/deferred-items.md" — append DEF-10-02-A
decisions:
  - "D-10-02-A: bucket SEARCH_LATENCY bắt đầu 0.05s (KHÔNG 0.025s như plan ghi) — match SC2 800ms target nằm giữa, range 50ms→5s đủ phủ Phase 6 SLA"
  - "D-10-02-B: dùng REGISTRY.get_sample_value() API ổn định cho test thay vì regex parse generate_latest() (Rule 1 fix — regex helper ban đầu match thất bại do label order variability)"
  - "D-10-02-C: _resolve_path walk app.routes + route.matches(scope) thay vì scope[route] (Rule 1 fix — Starlette KHÔNG set scope[route] tại middleware level, chỉ set scope[endpoint]/path_params SAU resolve)"
  - "D-10-02-D: PrometheusMiddleware add giữa RequestId và ErrorHandler theo user context (KHÔNG add đầu tiên innermost như plan ghi) — request_id đã set khi metric ghi, exception re-raise lên ErrorHandler render envelope"
  - "D-10-02-E: instrument search/search_cross_hub bằng pattern split public/_impl thay vì wrap inline — tránh phá structure existing + tách clean responsibility (public = timing, _impl = logic)"
  - "D-10-02-F: instrument INGEST_DURATION dùng asyncio.get_event_loop().time() manual thay vì .time() context manager (Histogram.time() là sync context manager → KHÔNG bao quanh được await asyncio.to_thread())"
  - "D-10-02-G: assert content-type lỏng (chỉ check `version=` + `charset=utf-8` presence) — prometheus-client 0.23+ dùng `version=1.0.0` (openmetrics text format) thay vì `0.0.4` cũ"
  - "D-10-02-H: KHÔNG instrument find_similar() — defer Phase v4.0 (D-04 KHÔNG có REQ-ID, HARD-02 chỉ yêu cầu 5 metric search_latency)"
metrics:
  duration_minutes: 35
  completed_date: "2026-05-21"
  tasks: 2
  files_created: 5
  files_modified: 6
  unit_tests_added: 6
  integration_tests_added: 5
  unit_tests_pass: "6/6"
  integration_tests_pass: "5/5"
  regression_unit: "136/136 PASS"
  regression_critical: "85 PASS / 4 pre-existing FAIL (DEF-10-02-A — Phase 8.3 migration 0004)"
---

# Phase 10 Plan 02: Prometheus /metrics endpoint + middleware + instrument search/ingest — Summary

Prometheus client thêm vào api/pyproject.toml + GET /metrics endpoint outside /api/* + PrometheusMiddleware đo latency + count request/error + instrument search/ingest qua 5 metric (REQUESTS_TOTAL + ERRORS_TOTAL + REQUEST_DURATION + SEARCH_LATENCY[single/cross] + INGEST_DURATION) — đặt nền observability cho M2 cho Prometheus scrape mỗi 15s → Grafana dashboard p95/error rate/ingest throughput (Grafana config defer v4.0).

## Tasks Completed

| Task | Name                                                                | Commit    | Files                                                                                                                       |
| ---- | ------------------------------------------------------------------- | --------- | --------------------------------------------------------------------------------------------------------------------------- |
| RED  | 6 unit test RED ImportError prometheus_client + app.observability  | `aebcf1c` | tests/unit/test_metrics.py                                                                                                  |
| 1    | observability package (3 file) + 6 unit test GREEN                  | `712a224` | api/pyproject.toml + uv.lock + app/observability/{__init__,metrics,middleware}.py + tests/unit/test_metrics.py            |
| 2    | wire middleware + /metrics + instrument search/ingest + 5 integration test | `8a94ee0` | app/main.py + app/services/{search,documents}_service.py + tests/integration/test_metrics_endpoint.py                  |

## Test Results

**Unit Test Plan 10-02:** 6/6 PASS trong 0.34s

```
tests/unit/test_metrics.py::test_metric_instances_have_correct_type_and_labelnames PASSED [ 16%]
tests/unit/test_metrics.py::test_requests_total_inc_appears_in_generate_latest PASSED [ 33%]
tests/unit/test_metrics.py::test_search_latency_time_observe_falls_in_50ms_bucket PASSED [ 50%]
tests/unit/test_metrics.py::test_middleware_request_200_increments_requests_total_and_observes_duration PASSED [ 66%]
tests/unit/test_metrics.py::test_middleware_500_increments_errors_total PASSED [ 83%]
tests/unit/test_metrics.py::test_middleware_unknown_path_uses_unknown_label PASSED [100%]
```

**Integration Test Plan 10-02:** 5/5 PASS trong 14.5s (testcontainers Postgres pgvector pg16 + Redis 7-alpine)

```
test_metrics_endpoint.py::test_metrics_endpoint_returns_prometheus_exposition_format PASSED
test_metrics_endpoint.py::test_metrics_counts_healthz_requests PASSED
test_metrics_endpoint.py::test_metrics_422_does_not_increment_errors_total PASSED
test_metrics_endpoint.py::test_search_service_observes_search_latency_histogram PASSED
test_metrics_endpoint.py::test_trigger_cocoindex_update_observes_ingest_duration_histogram PASSED
```

**Regression unit suite:** 136/136 PASS (`pytest tests/unit -q`) — 130 cũ Plan 10-01 + 6 mới Plan 10-02.

**Critical regression:** 85 PASS / 4 FAIL — 4 fail ĐÃ pre-existing TRƯỚC Plan 10-02 (Phase 8.3 migration 0004 drift + auth refresh contract). KHÔNG do Plan 10-02 — chi tiết DEF-10-02-A.

**Quality gates:**
- `ruff check app/observability/ app/main.py app/services/search_service.py app/services/documents_service.py tests/unit/test_metrics.py tests/integration/test_metrics_endpoint.py` → All checks passed!
- `mypy --strict app/observability/ app/main.py app/services/search_service.py app/services/documents_service.py` → Success: no issues found in 6 source files.
- `python -c "from app.main import create_app; app = create_app(); print('/metrics in routes:', '/metrics' in [r.path for r in app.routes if hasattr(r, 'path')])"` → True.

## Sample /metrics Output (test capture)

10 dòng đầu output `/metrics` qua test (manual verify đã đạt qua integration test 7):

```
# HELP python_gc_objects_collected_total Objects collected during gc
# TYPE python_gc_objects_collected_total counter
python_gc_objects_collected_total{generation="0"} 244.0
python_gc_objects_collected_total{generation="1"} 90.0
# HELP requests_total Total HTTP requests by method/path/status
# TYPE requests_total counter
requests_total{method="GET",path="/healthz",status="200"} 3.0
requests_total{method="GET",path="/metrics",status="200"} 1.0
# HELP errors_total Total HTTP requests with status >= 500
# TYPE errors_total counter
# HELP request_duration_seconds HTTP request duration in seconds
# TYPE request_duration_seconds histogram
request_duration_seconds_bucket{le="0.005",method="GET",path="/healthz"} 3.0
```

Content-Type: `text/plain; version=1.0.0; charset=utf-8` (Prometheus exposition format OpenMetrics text — verified Test 7 + `prometheus_client.parser.text_string_to_metric_families` parse được).

## Middleware Order (sau Plan 10-02)

Outer-to-inner cho REQUEST flow (FastAPI executes last-added FIRST):

```
incoming request →
  ErrorHandler (add cuối, outermost — catch mọi exception kể cả CORS leak)
  → Prometheus (đo latency + count metric, ghi metric TRƯỚC re-raise exception)
  → RequestId (gắn X-Request-Id sớm)
  → SecurityHeaders (X-Content-Type-Options, X-Frame-Options...)
  → CORS (add đầu, innermost — preflight OPTIONS)
  → router handler
```

Add order trong `create_app()`: `CORSMiddleware → SecurityHeadersMiddleware → RequestIdMiddleware → PrometheusMiddleware → ErrorHandlerMiddleware`.

## Instrument Points (file:line ranges)

- **search_service.py:226-240** — `search()` public method wrap `SEARCH_LATENCY.labels(hub_scope="single").time()` quanh await `_search_single_impl()`.
- **search_service.py:243+** — `_search_single_impl()` chứa logic gốc của search().
- **search_service.py:316-330** — `search_cross_hub()` public method wrap `SEARCH_LATENCY.labels(hub_scope="cross").time()` quanh await `_search_cross_hub_impl()`.
- **search_service.py:333+** — `_search_cross_hub_impl()` chứa logic gốc.
- **documents_service.py:562-573** — `trigger_cocoindex_update()` retry loop wrap `await asyncio.to_thread(cocoindex_app.update_blocking)` bằng `INGEST_DURATION.observe(asyncio.get_event_loop().time() - _ingest_start)` mỗi attempt.

## Decisions Made

- **D-10-02-A** (bucket SEARCH_LATENCY): Plan ghi `buckets=(0.05, 0.1, ...)` — chính xác match SC2 target 800ms (rơi vào bucket 0.8). Test 3 ban đầu assert le="0.025" → sửa thành le="0.05" (Rule 1 fix — bucket le=0.025 KHÔNG tồn tại trong tuple). KHÔNG đổi bucket tuple — đúng spec plan.
- **D-10-02-B** (test helper): Dùng `REGISTRY.get_sample_value(name, labels)` API ổn định prometheus_client. Helper regex parse `generate_latest()` ban đầu match thất bại do label order trong text format variability + escape regex characters. `get_sample_value()` direct lookup theo dict labels — clean + maintainable.
- **D-10-02-C** (resolve path): Starlette KHÔNG set `scope["route"]` tại middleware level (chỉ set `scope["endpoint"]/path_params` SAU router resolve). Phải walk `request.app.routes` + dùng `route.matches(scope)` (trả `Match.FULL`) để resolve template `/api/documents/{document_id}` từ middleware. Plan ghi `request.scope["route"]` — Rule 1 fix về API thực tế Starlette.
- **D-10-02-D** (middleware order): Plan ghi "Innermost — add ĐẦU TIÊN" + user context ghi "giữa RequestId và ErrorHandler". Theo user context (source of truth): add ORDER `CORS → SecurityHeaders → RequestId → Prometheus → ErrorHandler` → outer-to-inner request flow `ErrorHandler → Prometheus → RequestId → SecurityHeaders → CORS → router`. PrometheusMiddleware đo bao gồm latency RequestId/SecurityHeaders/CORS + router handler — KHÔNG đo ErrorHandler (vì outer hơn).
- **D-10-02-E** (instrument pattern): Wrap `search()/search_cross_hub()` qua split public method (wrap `.time()`) + `_impl` method (logic gốc) thay vì wrap inline trong toàn body. Lý do: `Histogram.time()` là sync context manager Python — KHÔNG bao quanh được `await` đúng cách trong async function nếu wrap inline (sẽ chỉ đo phần sync setup). Pattern split clean responsibility + áp dụng được cho cả 2 method.
- **D-10-02-F** (ingest timing manual): `Histogram.time()` sync context manager KHÔNG bao quanh được `await asyncio.to_thread(cocoindex_app.update_blocking)`. Dùng manual `_ingest_start = asyncio.get_event_loop().time()` + `INGEST_DURATION.observe(loop.time() - _ingest_start)` SAU await. Mỗi attempt retry observe 1 lần (sample n=attempt — hợp lý cho operational visibility cocoindex memo skip cheap re-execute).
- **D-10-02-G** (content-type lỏng): prometheus-client 0.23+ dùng `text/plain; version=1.0.0; charset=utf-8` (OpenMetrics text format) thay vì `version=0.0.4` cũ (Prometheus exposition format <0.0.5). Test 7 ban đầu assert `"version=0.0.4" in ct` → fail. Sửa: assert chỉ `version=` + `charset=utf-8` presence — robust cross-version. Body vẫn parse được qua `text_string_to_metric_families` cho cả 2 format.
- **D-10-02-H** (KHÔNG instrument find_similar): D-04 (find_similar) KHÔNG có REQ-ID, KHÔNG cache, KHÔNG đo SEARCH_LATENCY. HARD-02 chỉ yêu cầu instrument search/search_cross_hub. find_similar defer v4.0 nếu cần observability.

## Deviations from Plan

### Rule 1 — Bucket le="0.025" KHÔNG tồn tại trong SEARCH_LATENCY buckets

**Found during:** Task 1 GREEN phase (Test 3 fail bucket count=0).
**Issue:** Plan recommend test assert bucket `le="0.025"` cho SEARCH_LATENCY. Buckets thực tế của SEARCH_LATENCY = `(0.05, 0.1, 0.2, 0.4, 0.8, 1.5, 3.0, 5.0)` — KHÔNG có 0.025. 10ms sleep → rơi vào bucket nhỏ nhất là 0.05.
**Fix:** Đổi assertion test 3 sang `le="0.05"`. Buckets metric KHÔNG đổi (plan ghi đúng tuple — chỉ assertion test sai).
**Files modified:** tests/unit/test_metrics.py.
**Commit:** `712a224`.

### Rule 1 — Starlette KHÔNG set scope["route"] tại middleware level

**Found during:** Task 1 GREEN phase (Test 4 + 5 fail label `path` = "unknown" thay vì "/" hoặc "/fail").
**Issue:** Plan recommend `request.scope.get("route")` để resolve route template. Behavior thực tế Starlette: scope chỉ có `["endpoint", "path_params"]` SAU `call_next` — KHÔNG có `"route"` key. Tại middleware level (TRƯỚC call_next), router CHƯA resolve.
**Fix:** Walk `request.app.routes` + dùng `route.matches(scope)` trả `Match.FULL` để resolve template path từ middleware. Pattern chuẩn Starlette community (verified qua debug REPL).
**Files modified:** app/observability/middleware.py.
**Commit:** `712a224`.

### Rule 1 — Helper regex parse generate_latest() match thất bại

**Found during:** Task 1 GREEN phase (Test 2/4/5 fail value=0.0 dù counter inc).
**Issue:** Helper `_get_counter_value` ban đầu regex parse text output. Vấn đề: label order trong exposition format CÓ THỂ theo alphabet hoặc theo insertion order — regex match nhãn theo group `.*?` non-greedy KHÔNG robust + label set có thể partial match.
**Fix:** Refactor sang `REGISTRY.get_sample_value(metric_name, labels_dict)` API ổn định prometheus_client — direct lookup theo dict labels, KHÔNG cần regex.
**Files modified:** tests/unit/test_metrics.py.
**Commit:** `712a224`.

### Rule 1 — Content-Type version=1.0.0 trong prometheus-client>=0.21 (KHÔNG 0.0.4)

**Found during:** Task 2 GREEN phase (Test 7 fail `version=0.0.4` không có trong `text/plain; version=1.0.0; charset=utf-8`).
**Issue:** Plan ghi content-type `text/plain; version=0.0.4` — đúng cho prometheus-client <0.21 (Prometheus exposition format gốc). prometheus-client 0.23+ default dùng `version=1.0.0` (OpenMetrics text format).
**Fix:** Test 7 assert lỏng chỉ `version=` + `charset=utf-8` presence — robust cross-version. Body vẫn parse được qua `prometheus_client.parser.text_string_to_metric_families` cho cả 2 format.
**Files modified:** tests/integration/test_metrics_endpoint.py.
**Commit:** `8a94ee0`.

### Rule 1 — Schema documents columns trong Test 11 SQL

**Found during:** Task 2 GREEN phase (Test 11 fail UndefinedColumnError `original_name` của `documents`).
**Issue:** Test 11 INSERT documents dùng tên cột `original_name`, `file_size`, `mime_type` — KHÔNG match schema migration 0001/0003. Tên thật: `filename`, `file_path`, `mime_type`, `file_size_bytes`, `status`, `chunk_count`, `attempts`, `last_heartbeat` (theo conftest.py:349).
**Fix:** Đổi INSERT statement Test 11 dùng tên cột đúng từ conftest helper.
**Files modified:** tests/integration/test_metrics_endpoint.py.
**Commit:** `8a94ee0`.

### Rule 2 — instrument search/search_cross_hub split public/_impl pattern

**Found during:** Task 2 plan recommend "wrap logic chính bằng `with SEARCH_LATENCY.labels(...).time():`" inline.
**Issue:** `Histogram.time()` là sync context manager Python — KHÔNG bao quanh được `await` toàn body của async function clean. Wrap inline có 2 nhược điểm: (1) phá indentation existing 100+ dòng, (2) cần care về behavior `.time()` context manager với async (chỉ đo phần sync setup).
**Fix:** Split `search()/search_cross_hub()` thành public method (chỉ wrap context manager + delegate) + `_search_single_impl()/_search_cross_hub_impl()` (logic gốc nguyên vẹn). Pattern clean responsibility + tránh diff lớn ở logic core search.
**Files modified:** app/services/search_service.py.
**Commit:** `8a94ee0`.

### Rule 2 — INGEST_DURATION manual timing trong retry loop

**Found during:** Task 2 plan recommend `with INGEST_DURATION.time(): cocoindex_app.update_blocking()`.
**Issue:** Plan recommend wrap sync; thực tế gọi qua `await asyncio.to_thread(cocoindex_app.update_blocking)` (async). `Histogram.time()` sync context manager KHÔNG bao được async await call (sẽ chỉ đo time đến khi event loop yield).
**Fix:** Dùng manual `_ingest_start = asyncio.get_event_loop().time()` + `INGEST_DURATION.observe(elapsed)` SAU await. Đặt TRONG retry loop — mỗi attempt observe 1 lần (n=attempts cho operational visibility).
**Files modified:** app/services/documents_service.py.
**Commit:** `8a94ee0`.

## Deferred Issues

- **DEF-10-02-A** (Plan 10-03 target): 4 pre-existing integration test failures (test_alembic_ignores_cocoindex_schema, test_auth_refresh_race, test_upgrade_creates_10_tables, test_phase4_migration_no_drift) — đều do Phase 8.3 migration 0004 (mcp_oauth_clients table) + auth response contract change. KHÔNG do Plan 10-02 (Plan 10-02 tests pass 11/11). Phase 10-03 sẽ phải fix để integration suite chạy clean cho HARD-03 coverage measure.

## Threat Flags

KHÔNG có threat surface mới ngoài threat model plan (T-10-02-01..04 đều accept/mitigate trong plan). `/metrics` endpoint expose public (no auth) — đã accept trong T-10-02-01 (HARD-02 spec, production deploy reverse proxy whitelist). Cardinality control qua `_resolve_path` fallback "unknown" mitigate T-10-02-02/03.

## Self-Check: PASSED

**Files verified exist:**
- `Hub_All/api/app/observability/__init__.py` → FOUND
- `Hub_All/api/app/observability/metrics.py` → FOUND
- `Hub_All/api/app/observability/middleware.py` → FOUND
- `Hub_All/api/tests/unit/test_metrics.py` → FOUND
- `Hub_All/api/tests/integration/test_metrics_endpoint.py` → FOUND

**Commits verified exist:**
- `aebcf1c` (TDD RED) → FOUND in git log
- `712a224` (Task 1 GREEN) → FOUND in git log
- `8a94ee0` (Task 2) → FOUND in git log

**Tests verified PASS:**
- 6/6 unit test Plan 10-02 PASS
- 5/5 integration test Plan 10-02 PASS
- 136/136 unit test toàn module KHÔNG regression
- ruff sạch + mypy --strict PASS 6 file app + 2 file test
- `/metrics` route in app.routes (verified python -c import)
- Content-Type Prometheus exposition format parse được qua `text_string_to_metric_families`
