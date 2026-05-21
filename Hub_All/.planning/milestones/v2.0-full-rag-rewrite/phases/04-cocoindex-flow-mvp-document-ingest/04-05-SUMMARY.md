---
phase: 04
plan: 05
subsystem: api/services + api/routers + api/main + api/config
tags: [INGEST-06, INGEST-07, INGEST-08, P8, WARNING-7, REVISION-2, watchdog, delete, list, audit]
revision: 2
requirements:
  - INGEST-06
  - INGEST-07
  - INGEST-08
dependency_graph:
  requires:
    - 04-01 (alembic 0002 watchdog index ix_documents_status_last_heartbeat + cocoindex setup)
    - 04-02 (DocumentService base + FileStore + file_extract)
    - 04-03 (cocoindex 1.0.3 setup_cocoindex + app.state.cocoindex_app + lifespan step 3)
    - 04-04 (DocumentService.create + trigger_cocoindex_update + last_heartbeat=NOW() bootstrap + documents_router include + WARNING #6 DoS guard)
  provides:
    - DocumentService.list (paginated + filter hub_id/status/uploaded_by/search ILIKE)
    - DocumentService.delete (cascade chunks + audit_logs entry + best-effort unlink)
    - watchdog_loop asyncio task (60s tick, 5min timeout, NULL guard)
    - DELETE /api/documents/:id (admin-only, 204 No Content)
    - GET /api/documents (paginated, cap per_page=100)
    - Settings.watchdog_timeout_seconds field (env configurable, default 300)
  affects:
    - app/services/documents_service.py (EXTEND — Plan 04-04 base + 2 method mới)
    - app/services/watchdog.py (NEW)
    - app/routers/documents.py (EXTEND — Plan 04-04 base + 2 endpoint mới)
    - app/main.py (EXTEND lifespan APPEND-ONLY step 7 + shutdown cancel)
    - app/config.py (EXTEND Settings — 1 field mới)
    - tests/unit/test_watchdog.py (NEW — 6 test)
    - tests/unit/conftest.py (NEW — re-export integration fixtures)
    - tests/integration/test_documents_list_delete.py (NEW — 7 test)
tech_stack:
  added: []  # KHÔNG thêm dependency mới
  patterns:
    - "watchdog asyncio.create_task() lifespan-managed (start cuối startup, cancel đầu shutdown)"
    - "Postgres make_interval(secs => :timeout) bind parameter cho configurable timeout (KHÔNG hardcode INTERVAL string)"
    - "NULL guard `last_heartbeat IS NOT NULL` trong UPDATE WHERE — accept leak ngắn ngủi processing rows chưa có heartbeat"
    - "ILIKE search bind param `:search` qua asyncpg → an toàn SQL injection"
    - "DELETE cascade chunks qua FK Phase 2 + audit_logs INSERT đồng bộ + best-effort filesystem unlink (try/except)"
    - "tests/unit/conftest.py re-export integration fixtures (postgres_container, alembic_cfg, redis_container) cho test_watchdog.py technically integration nhưng đặt unit/"
key_files:
  created:
    - Hub_All/api/app/services/watchdog.py
    - Hub_All/api/tests/unit/test_watchdog.py
    - Hub_All/api/tests/unit/conftest.py
    - Hub_All/api/tests/integration/test_documents_list_delete.py
  modified:
    - Hub_All/api/app/services/documents_service.py (EXTEND — list + delete)
    - Hub_All/api/app/routers/documents.py (EXTEND — DELETE + GET list + status import)
    - Hub_All/api/app/main.py (EXTEND lifespan APPEND-ONLY step 7 + shutdown cancel)
    - Hub_All/api/app/config.py (EXTEND Settings — watchdog_timeout_seconds)
key_decisions:
  - "Watchdog timeout 5 phút (REVISION 2) — tăng từ 2 phút headroom cho cocoindex 1.0.3 update_blocking documents lớn (DOCX 50 trang + N×embed LiteLLM có thể chạy >2 phút bình thường). Configurable env WATCHDOG_TIMEOUT_SECONDS."
  - "NULL guard `last_heartbeat IS NOT NULL` (WARNING #7 fix combo (b)+(c)) — chỉ flip rows có heartbeat NOT NULL + stale; accept leak ngắn ngủi processing nếu cocoindex worker chưa update heartbeat lần đầu."
  - "Status update cocoindex completion KHÔNG ở watchdog — đã ở Plan 04-04 trigger_cocoindex_update helper (count chunks > 0 → 'completed', =0 → 'failed'). Watchdog chỉ phát hiện crash giữa chừng."
  - "DELETE cascade chunks qua FK Phase 2 (KHÔNG dựa cocoindex tombstone vì cocoindex 1.0.3 schema-managed by USER, không expose row delete API)."
  - "Audit log INSERT đồng bộ trong service.delete (defer batch flush AUX-01 Phase 5)."
  - "Best-effort filesystem unlink (try/except + log warning) — orphaned file_store cleanup defer Phase 10 HARD-04 cron (T-04-05-05 accept)."
  - "main.py lifespan APPEND-ONLY step 7 watchdog SAU step 3 cocoindex setup + step 6 SQLAlchemy engine init (WARNING #5 — KHÔNG đụng setup_cocoindex hoặc include_router Plan 04-04)."
  - "Watchdog cancel TRƯỚC dispose_engine ở shutdown — tránh race 'engine disposed mid-tick'."
  - "tests/unit/conftest.py re-export integration fixtures — Rule 3 fix vì pytest fixtures KHÔNG inherit qua sibling directories. test_watchdog.py technically integration nhưng đặt unit/ vì isolated query logic."
metrics:
  duration_minutes: 35
  completed_date: "2026-05-14"
  task_count: 4
  commit_count: 4
  test_count: 13
  lines_added_approx: 920
threat_model_entries: 8
---

# Phase 04 Plan 05: Watchdog asyncio task + DELETE + LIST endpoints (REVISION 2) — Summary

**One-liner:** Hoàn thiện 3 INGEST requirements cuối Phase 4 — watchdog asyncio task lifespan-managed flip stuck `processing > 5 phút last_heartbeat IS NOT NULL` → `failed` (REVISION 2 timeout configurable, WARNING #7 NULL guard), DELETE /api/documents/:id admin-only cascade chunks + audit log, GET /api/documents paginated + filter hub_id/status/uploaded_by/search ILIKE filename + cap per_page ≤ 100.

## Tổng quan thực thi

Plan 04-05 thực thi đầy đủ 4 task atomic, mỗi task 1 commit. Tổng cộng:

- **4 commit:** `e69f9ea` → `388b79d` → `14c4785` → `b685e85`.
- **7 file** created/modified (5 production code + 3 test files, gồm 1 NEW conftest unit).
- **13 test mới** PASS (6 unit watchdog + 7 integration list/delete).
- **132 test full suite** PASS (no regression Phase 1-3 + Plan 04-01..05).
- **47 critical test** PASS (HARD-03 CI gate).
- **0 blocker, 1 deviation Rule 3** (re-export integration fixtures cho unit conftest).

## Tasks executed

### Task 01 — `documents_service.py` EXTEND `list` + `delete`

**Commit:** `e69f9ea`

EXTEND class `DocumentService` (Plan 04-04 đã ship `create` + `get` + module-level `trigger_cocoindex_update` A4) thêm 2 method:

- **`list(*, hub_id?, status_filter?, uploaded_by?, search?, page=1, per_page=20)`** → tuple `(items: list[DocumentListItem], total: int)`. Build WHERE clauses dynamic + bind params dict an toàn (asyncpg parametrize → no SQL injection). Search ILIKE filename. ORDER BY created_at DESC stable. LIMIT + OFFSET pagination. Cap per_page do router enforce (KHÔNG cap ở service layer).
- **`delete(document_id, *, deleted_by, request_id?)`** → `bool` (False nếu không tồn tại). Sequence: SELECT exists + lấy hub_id + file_path → DELETE FROM documents (chunks CASCADE qua FK Phase 2 migration 0001 line 332-336) → INSERT audit_logs (action='document_delete', target_type='document', target_id, hub_id, request_id) → best-effort `FileStore().delete(Path(file_path))` try/except + log warning.

Thêm import `DocumentListItem` từ schemas. KHÔNG đổi signature `create` / `get` / `trigger_cocoindex_update` Plan 04-04.

**Acceptance criteria PASS:** 9/9 grep + ruff + mypy strict + DocumentService methods discovery `['create', 'delete', 'get', 'list']`.

### Task 02 — `watchdog.py` NEW + `config.py` ADD field + `main.py` lifespan APPEND-ONLY

**Commit:** `388b79d`

**File 1 `app/config.py` ADD field:**
- `Settings.watchdog_timeout_seconds: int = 300` (REVISION 2 — 5 phút thay 2 phút headroom cho cocoindex 1.0.3 `update_blocking()` documents lớn). Configurable env `WATCHDOG_TIMEOUT_SECONDS`.

**File 2 `app/services/watchdog.py` NEW:**
- `WATCHDOG_INTERVAL_SECONDS = 60` const.
- `get_watchdog_timeout_seconds() -> int` helper (return Settings field, tách để test mock).
- `async watchdog_tick() -> int` — 1 lần tick. UPDATE documents SET status='failed' WHERE `status='processing' AND last_heartbeat IS NOT NULL AND last_heartbeat < NOW() - make_interval(secs => :timeout_secs)`. Bind parameter cho configurable timeout (KHÔNG hardcode INTERVAL string). Trả `result.rowcount`. Log info nếu count > 0. Try/except RuntimeError nếu engine chưa init (lifespan startup chưa xong / shutdown đã chạy) → skip + log warning.
- `async watchdog_loop()` — forever-running loop. Cancel-safe (nhận `asyncio.CancelledError` → return gracefully). Exception khác → `logger.exception` + tiếp tục (defensive, KHÔNG crash task).

**File 3 `app/main.py` lifespan EXTEND APPEND-ONLY (WARNING #5):**
- Sau step 6 (SQLAlchemy engine init) thêm step 7: `app.state.watchdog_task = asyncio.create_task(watchdog_loop())` + log "watchdog_task_started". Try/except → log warning nếu fail. KHÔNG đổi setup_cocoindex (Plan 04-03 step 3) hoặc include_router (Plan 04-04 create_app).
- Shutdown — thêm block đầu finally (TRƯỚC dispose_engine) cancel watchdog_task: `app.state.watchdog_task.cancel()` + `await app.state.watchdog_task` + suppress `asyncio.CancelledError`. Cancel TRƯỚC dispose_engine để tránh race "engine disposed mid-tick".

**Acceptance criteria PASS:** all grep ≥ thresholds (`make_interval(secs` ≥1, `watchdog_timeout_seconds` ≥3, `asyncio.CancelledError` ≥1, `create_task(watchdog_loop` ≥1, `app.state.watchdog_task` ≥3) + ruff + mypy strict + runtime verify `WATCHDOG_INTERVAL_SECONDS=60` + `watchdog_timeout_seconds=300`.

### Task 03 — `routers/documents.py` EXTEND DELETE + GET list

**Commit:** `14c4785`

EXTEND existing router (Plan 04-04 ship `POST /upload` + `GET /:id`) thêm:

- **`DELETE /api/documents/{document_id}`** — `status_code=204` + `Depends(require_role("admin"))` + `Request` cho request_id từ `RequestIdMiddleware`. Validate UUID format (400 INVALID_DOCUMENT_ID nếu sai). `service.delete(uuid, deleted_by=user.id, request_id=...)` → False → 404 NOT_FOUND, True → return `Response(status_code=204)` (Starlette emit empty body theo HTTP spec).
- **`GET /api/documents`** (path empty `""` sau prefix `/api/documents`) — `Depends(get_current_user)` (any authenticated). Query params: `hub_id?, status_filter?, uploaded_by?, search?, page=1, per_page=20`. Validate optional UUIDs (400 INVALID_HUB_ID / INVALID_UPLOADED_BY). **Cap `max(1, min(per_page, 100))`** + `max(1, page)` (T-04-05-01 DoS mitigation). `service.list(...)` → `resp.paginated(items, page, per_page, total)` envelope.

Thêm import `status` + `Response` từ `fastapi`. KHÔNG đổi POST /upload + GET /:id (Plan 04-04 BackgroundTasks A4 vẫn còn). KHÔNG đổi middleware order P11.

**Acceptance criteria PASS:** route inspection — 4 endpoint `/api/documents` (POST upload, GET, GET /:id, DELETE /:id), all grep + ruff + mypy strict.

### Task 04 — Tests `unit/test_watchdog.py` (6) + `integration/test_documents_list_delete.py` (7) + `unit/conftest.py` (Rule 3 deviation)

**Commit:** `b685e85`

**File 1 `tests/unit/test_watchdog.py` — 6 test PASS:**

| Test | Status | Mô tả |
|---|---|---|
| `test_watchdog_flips_stuck_processing` | critical | Row `processing` last_heartbeat=NOW()-6min → `watchdog_tick()` → 1 row flip 'failed' + error_message chứa "timeout"+"heartbeat". |
| `test_watchdog_skips_recent_processing` | critical | last_heartbeat=NOW()-1min (< 5min) → KHÔNG flip; status giữ processing. |
| `test_watchdog_respects_5min_timeout` (REVISION 2 NEW) | critical | Boundary 3min KHÔNG flip + 6min flip. Verify cả 2 row status final. |
| `test_watchdog_skips_pending` | integration | Row pending stale 10min → KHÔNG flip (status ≠ processing). |
| `test_watchdog_skips_null_heartbeat_processing` (WARNING #7 fix) | critical | Row processing last_heartbeat=NULL → KHÔNG flip + status giữ processing + last_heartbeat vẫn NULL. |
| `test_watchdog_empty_db` | integration | DB không có rows → return 0. |

Fixture `watchdog_db` (function-scope): alembic upgrade head qua `asyncio.to_thread` + `init_engine(get_settings())` + cleanup `dispose_engine()`. Helper `_seed_hub_document(status, last_heartbeat_offset_minutes)` INSERT 1 hub + 1 documents row với offset minutes (None → NULL).

**File 2 `tests/integration/test_documents_list_delete.py` — 7 test PASS:**

| Test | Status | Mô tả |
|---|---|---|
| `test_list_empty` | critical | DB trống → data=[], meta.total=0. |
| `test_list_pagination_cap_per_page` (T-04-05-01) | critical | Upload 5 rows + GET ?per_page=200 → meta.per_page=100 (cap), total=5, len(data)=5. |
| `test_list_filter_hub_id` | critical | 2 hub × 3 doc → GET ?hub_id=hub_a → total=2 + tất cả items có hub_id=hub_a. |
| `test_list_filter_search_filename` | integration | ILIKE 'báo' → match 1 file 'Báo cáo Q1.docx', KHÔNG match 'Khám bệnh.docx'. |
| `test_delete_happy_path_cascade` | critical | DELETE → 204 + row documents xoá + audit_logs entry action='document_delete' + user_id=admin.id. |
| `test_delete_viewer_403` | critical | Viewer DELETE → 403 FORBIDDEN (RBAC require_role admin). |
| `test_delete_unknown_404` | integration | DELETE unknown UUID → 404 NOT_FOUND. |

`MockCocoindexApp` class (sync `update_blocking()` count) bind vào `app.state.cocoindex_app` qua fixture `mock_cocoindex_app` để A4 BackgroundTask Plan 04-04 chạy được mà KHÔNG cần cocoindex thật. Reuse fixtures Phase 3 `auth_client/admin_token/viewer_token/admin_user/app_with_auth` từ `tests/integration/conftest.py`.

**File 3 `tests/unit/conftest.py` NEW (Rule 3 deviation):**

Re-export 3 fixture từ `tests/integration/conftest.py`: `postgres_container`, `alembic_cfg`, `redis_container`. Lý do: pytest fixtures KHÔNG inherit qua sibling directories — `tests/integration/conftest.py` fixtures chỉ visible cho file trong `tests/integration/`. test_watchdog.py technically integration (cần Postgres testcontainer) nhưng plan đặt `tests/unit/` vì test query logic isolated KHÔNG cần FastAPI app/lifespan/auth router. Re-import noqa F401.

**Acceptance criteria PASS:** all grep targets + lint + 13/13 tests PASS + 132/132 full suite no regress + 47/47 critical PASS.

## Verification kết quả

| Lệnh | Kết quả |
|---|---|
| `pytest tests/unit/test_watchdog.py -v` | 6 PASS / 9.11s |
| `pytest tests/integration/test_documents_list_delete.py -v` | 7 PASS / 22.59s |
| `pytest tests/` (full suite) | 132 PASS / 87.23s — KHÔNG regression |
| `pytest -m critical` | 47 PASS / 71.93s — HARD-03 CI gate clean |
| `ruff check` (5 source + 3 test files + conftest) | All checks passed |
| `mypy --strict` (5 source files) | Success: no issues found |
| `python -c "from app.services.watchdog import ..."` | `60 300` (interval=60s, timeout=300s REVISION 2) |
| `python -c "from app.main import create_app; ..."` | 4 endpoints `/api/documents` (POST upload, GET, GET /:id, DELETE /:id) |
| `grep -c 'IS NOT NULL' app/services/watchdog.py` | 3 ≥ 1 PASS |
| `grep -c 'make_interval(secs' app/services/watchdog.py` | 2 ≥ 1 PASS |
| `grep -c 'watchdog_timeout_seconds' app/{config,services/watchdog,main}.py` | 1+7+0 → tổng 8 ≥ 3 (config + watchdog + main lifespan import indirect) |
| `grep -c 'asyncio.create_task(watchdog_loop' app/main.py` | 1 ≥ 1 PASS |

## Threat Model

8 entry STRIDE — 4 mitigate + 4 accept (defer Phase 5 HUB-02 / Phase 10 HARD-04):

| ID | Category | Component | Disposition | Mitigation |
|---|---|---|---|---|
| T-04-05-01 | D (DoS) | LIST per_page=10000 → DB OOM | mitigate | `max(1, min(per_page, 100))` cap router-side. Test `test_list_pagination_cap_per_page` verify 200 → 100. |
| T-04-05-02 | I (Info disclosure) | LIST KHÔNG enforce hub isolation | accept | Phase 5 HUB-02 hub_assignments intersect document.hub_id. M2a EXIT GATE single-tenant test OK. |
| T-04-05-03 | T (Tampering) | DELETE cross-hub destruction | accept | `require_role("admin")` admin có quyền cross-hub. Phase 5 HUB-02 thêm hub_id check cho editor. |
| T-04-05-04 | I (Info disclosure) | Watchdog log row count → ops dashboard leak | accept | logger.info chỉ count number (KHÔNG IDs). Standard ops metric. |
| T-04-05-05 | R (Repudiation) | service.delete unlink file fail silent | accept | Best-effort try/except + log warning. Cleanup script defer Phase 10 HARD-04 cron. |
| T-04-05-06 | E (Elevation) | LIST endpoint dùng `get_current_user` viewer thấy mọi docs | accept | Phase 5 HUB-02 filter ở repo layer. Documented inter-phase dependency. |
| T-04-05-07 | D (DoS) | Watchdog flip mọi row processing với last_heartbeat=NULL → false-flip race window | mitigate | WARNING #7 fix combo (b)+(c): Plan 04-04 bootstrap last_heartbeat=NOW() atomic INSERT + watchdog NOT NULL guard. Test `test_watchdog_skips_null_heartbeat_processing` verify. |
| T-04-05-08 (REVISION 2 NEW) | D (DoS) | Watchdog timeout 2 phút false-flip cocoindex update_blocking documents lớn | mitigate | REVISION 2 timeout 2 phút → 5 phút (Settings.watchdog_timeout_seconds=300). Test `test_watchdog_respects_5min_timeout` verify boundary 3min vs 6min. |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking] Tạo `tests/unit/conftest.py` re-export integration fixtures**
- **Found during:** Task 04 (lần đầu chạy `pytest tests/unit/test_watchdog.py`)
- **Issue:** `fixture 'alembic_cfg' not found` — pytest fixtures KHÔNG inherit qua sibling directories (`tests/integration/conftest.py` chỉ visible cho file trong `tests/integration/`). Plan 04-05 task 04 đặt `test_watchdog.py` ở `tests/unit/` vì query logic isolated.
- **Fix:** Tạo `tests/unit/conftest.py` re-import 3 fixture (`postgres_container`, `alembic_cfg`, `redis_container`) từ `tests.integration.conftest` với `noqa: F401`.
- **Files modified:** `tests/unit/conftest.py` (NEW).
- **Commit:** `b685e85` (cùng commit Task 04).

**2. [Rule 3 — Blocking] Bỏ module-level `import asyncio` từ `main.py`**
- **Found during:** Task 02 (lần đầu lint sau khi thêm watchdog vào lifespan)
- **Issue:** Ruff F401 — `asyncio imported but unused` ở module level. Lý do: existing pattern lifespan dùng `import asyncio` LOCAL bên trong block (line 105 cocoindex setup, 202 cocoindex shutdown), reference `asyncio.CancelledError` line 186 của shutdown watchdog cancel block sẽ dùng cùng local scope.
- **Fix:** Bỏ module-level import; giữ pattern existing — local import trong each block đã đủ (line 167 watchdog `import asyncio as _asyncio_wd` + line 105 `import asyncio` bên trong cocoindex block satisfies CancelledError reference line 186).
- **Files modified:** `app/main.py`.
- **Commit:** `388b79d`.

### Auth Gates / Manual Steps

Không có. Toàn bộ test chạy với testcontainers Docker Desktop (Postgres pgvector pg16 + Redis 7-alpine).

### Architectural Changes

Không. Toàn bộ code follow plan đúng nguyên xi.

## Carry-Over / Forward-Linked Items

- **Phase 5 HUB-02:** GET /api/documents enforce hub_assignments intersection (T-04-05-02 + T-04-05-06 accept). DELETE editor role hub_id permission check (T-04-05-03 accept).
- **Phase 5 AUX-01:** Audit log batch flush (Plan 04-05 hiện INSERT đồng bộ — defer batch tới Phase 5).
- **Phase 10 HARD-04:** Cleanup cron tìm orphan files file_store/ vs documents.file_path (T-04-05-05 accept — best-effort unlink).
- **Plan 04-06 (M2a EXIT GATE):** E2E demo upload DOCX VN → cocoindex flow extract/chunk/embed → SELECT chunks pgvector verify. Manual checkpoint user accept để tiếp tục M2b. Sẽ verify integration của 04-01..05 chạy thật end-to-end (chưa mock cocoindex).

## Status hoàn thành

- [x] 4/4 task atomic commit (`e69f9ea`, `388b79d`, `14c4785`, `b685e85`).
- [x] 7 file modified/created đúng spec (5 production code + 2 NEW test files + 1 NEW conftest).
- [x] 3/3 INGEST requirements complete: INGEST-06 (heartbeat watchdog 5min NULL guard), INGEST-07 (DELETE admin cascade audit), INGEST-08 (LIST paginated filter cap 100).
- [x] **8/8 INGEST requirements** Phase 4 complete (INGEST-01..05 đã ship Plan 04-01..04 + INGEST-06..08 ship Plan 04-05).
- [x] WARNING #5 main.py overlap: APPEND-ONLY step 7 SAU step 3/6 (KHÔNG đụng cocoindex setup hoặc include_router).
- [x] WARNING #7 NULL guard combo (b)+(c): bootstrap last_heartbeat=NOW() Plan 04-04 + refresh trong trigger_cocoindex_update + watchdog NOT NULL guard query.
- [x] REVISION 2 ripple: timeout 2min → 5min configurable + Settings.watchdog_timeout_seconds=300 default + test_watchdog_respects_5min_timeout boundary 3min vs 6min.
- [x] 13/13 test mới PASS (6 unit watchdog + 7 integration list/delete).
- [x] 132/132 test full suite PASS — KHÔNG regression Phase 1-3.
- [x] 47/47 critical test PASS — HARD-03 CI gate clean.
- [x] Sẵn sàng Plan 04-06 — M2a EXIT GATE E2E demo + scanned PDF test BỎ xfail + A4 BackgroundTasks E2E verify.

## Self-Check: PASSED

Files verified existence:
- FOUND: `Hub_All/api/app/services/watchdog.py`
- FOUND: `Hub_All/api/tests/unit/test_watchdog.py`
- FOUND: `Hub_All/api/tests/unit/conftest.py`
- FOUND: `Hub_All/api/tests/integration/test_documents_list_delete.py`
- FOUND: `Hub_All/api/app/services/documents_service.py` (modified — `list` + `delete` methods)
- FOUND: `Hub_All/api/app/routers/documents.py` (modified — DELETE + GET list)
- FOUND: `Hub_All/api/app/main.py` (modified — lifespan APPEND-ONLY step 7)
- FOUND: `Hub_All/api/app/config.py` (modified — Settings.watchdog_timeout_seconds)

Commits verified existence:
- FOUND: `e69f9ea` (Task 01 — service list + delete)
- FOUND: `388b79d` (Task 02 — watchdog + config + main lifespan)
- FOUND: `14c4785` (Task 03 — router DELETE + GET list)
- FOUND: `b685e85` (Task 04 — tests 13 PASS + unit conftest)
