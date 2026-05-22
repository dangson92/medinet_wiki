---
phase: 04-cross-hub-data-sync
plan: 04
subsystem: sync
tags:
  - lifespan
  - integration
  - asyncpg-pool
  - pgvector
  - cocoindex
  - blocker-2-fix
  - w3-fix
  - w9-fix
requirements:
  - SYNC-01
  - SYNC-02
  - SYNC-05
dependency_graph:
  requires:
    - Plan 04-01 sync_outbox migration + trigger (jsonb_build_object hex + vector::float4[] cast)
    - Plan 04-02 Settings central_sync_dsn + hub_id field + validators
    - Plan 04-03 sync_worker_loop module + ChunkPayload Pydantic + 6 Prometheus collector
    - Phase 1 chunks table schema + documents.sync_status enum
    - Phase 2 hub_app_factory pattern + lifespan conditional spawn
    - Phase 3 JWKSCache lifespan pattern carry forward (graceful task cancel + timeout)
    - pgvector.asyncpg.register_vector (pgvector 0.4.2 ship M2)
  provides:
    - "app/db/dsn.py — shared _to_asyncpg_dsn helper (W3 fix circular import)"
    - "app/main.py::_init_central_sync_conn pgvector codec register callback (BLOCKER 2 fix)"
    - "app/main.py lifespan central_sync_pool init hub con với init=_init_central_sync_conn"
    - "app/main.py lifespan sync_worker_task spawn hub con SAU pool ready"
    - "app/main.py shutdown graceful: cancel worker + wait_for timeout 10s + close pool"
    - "app/rag/flow.py::index_document defensive guard hub_id mismatch skip + warning log"
    - "tests/integration/conftest.py::integration_db_pool fixture W9 fix (skipif INTEGRATION_DB_URL)"
    - "tests/integration/test_sync_lifespan_integration.py 6 mock + 1 skipif live DB"
    - "SYNC_SKIP_CENTRAL_POOL=1 escape hatch test mode (pattern song song JWKS_SKIP_FETCH)"
  affects:
    - Plan 04-05 (admin replay endpoint /api/sync/replay — central RBAC central_sync_pool re-use)
    - Plan 04-06 (checksum scheduler — KHÔNG re-use central_sync_pool; spawn pools tới hub con DSN dict)
    - Plan 04-07 closeout (REQUIREMENTS SYNC-01/02/05 mark complete sau full E2E test pass)
    - Phase 7 MIGRATE-05 (smoke E2E 3 hub con + central — wire INTEGRATION_DB_URL → enable Test 7)
tech-stack:
  added: []
  patterns:
    - "asyncpg.create_pool(init=callback) per-connection codec register (BLOCKER 2 pattern)"
    - "SELECT current_database() fail-fast verify pool target DB (T-04-04-01 mitigation)"
    - "asyncio.create_task spawn + task.cancel() + asyncio.wait_for(timeout=10s) graceful shutdown (carry forward Plan 03-02 JWKSCache pattern)"
    - "AsyncMock asyncpg.Pool + _AcquireContextMock async context manager test pattern (defer testcontainer Phase 7)"
    - "Test escape hatch env flag SYNC_SKIP_CENTRAL_POOL=1 (pattern song song JWKS_SKIP_FETCH Plan 03-02 + COCOINDEX_SKIP_SETUP DEF-05-01)"
    - "Module trung lập app/db/dsn.py shared helper tránh circular import (W3 fix pattern reusable)"
key-files:
  created:
    - api/app/db/dsn.py (45 LOC — W3 fix shared _to_asyncpg_dsn helper)
    - api/tests/integration/test_sync_lifespan_integration.py (402 LOC, 7 test — 6 mock + 1 skipif)
    - .planning/phases/04-cross-hub-data-sync/04-04-SUMMARY.md
  modified:
    - api/app/main.py (+ ~85 LOC — _init_central_sync_conn module-level + lifespan central_sync_pool + sync_worker_task + shutdown; — 7 LOC inline _to_asyncpg_dsn xoá)
    - api/app/rag/flow.py (+ ~22 LOC — D-V3-Phase4-D2 defensive guard doc_hub_id mismatch skip)
    - api/tests/integration/conftest.py (+ ~70 LOC — integration_db_pool fixture + hub_app_factory env auto-set SYNC_SKIP_CENTRAL_POOL/HUB_ID/CENTRAL_SYNC_DSN)
    - api/tests/unit/test_auth_router_hub_redirect.py (+ 5 LOC — _setup_env auto-set SYNC_SKIP_CENTRAL_POOL=1 Rule 3 regression fix)
decisions:
  - "W3 fix LOCKED: extract _to_asyncpg_dsn sang api/app/db/dsn.py — shared module tránh circular import; Plan 04-06 routers/sync.py import từ shared an toàn."
  - "BLOCKER 2 fix LOCKED: lifespan central_sync_pool create_pool(init=_init_central_sync_conn) register pgvector codec per connection cho $9::vector bind."
  - "T-04-04-01 mitigation LOCKED: SELECT current_database() fail-fast verify pool target == 'medinet_central'; KHÔNG silent corrupt nếu operator paste sai DSN."
  - "R-V3-1 fail-loud LOCKED: hub con KHÔNG init được central_sync_pool → re-raise → uvicorn exit 1; chấp nhận downtime hub con thay vì silent outbox accumulate."
  - "D-V3-Phase4-A3 LOCKED: central skip spawn sync_worker_task + skip init central_sync_pool — log evidence sync_worker_task_skipped + central_sync_pool_skipped."
  - "D-V3-Phase4-D2 LOCKED: rag/flow.py defensive guard skip chunks INSERT khi doc_hub_id != settings.hub_id (E-V3-3 isolation Layer 1 carry forward Phase 1)."
  - "Graceful shutdown pattern LOCKED: task.cancel() + asyncio.wait_for(timeout=10.0) + TimeoutError defensive log + close pool SAU worker stop (carry forward Plan 03-02 JWKSCache pattern)."
  - "W9 fix LOCKED: integration_db_pool fixture session-scope với skipif INTEGRATION_DB_URL không set — defer Phase 7 MIGRATE-05 wire URL thật."
  - "SYNC_SKIP_CENTRAL_POOL=1 test escape hatch (Rule 3 regression fix) LOCKED: pattern song song JWKS_SKIP_FETCH Plan 03-02 + COCOINDEX_SKIP_SETUP DEF-05-01; production KHÔNG bao giờ set."
  - "Implementation: pgvector import try/except module-level (optional dev defensive — pgvector 0.4.2 pin pyproject.toml nhưng try/except safe runtime)."
  - "Implementation: app.state.central_sync_pool = None default + sync_worker_task = None default trước branch — defensive cho central + skip case."
metrics:
  duration_minutes: 25
  completed_date: 2026-05-22
  task_count: 3
  commit_count: 3
  file_count: 6
  test_count: 7
  test_pass_rate: "6/6 mock PASS + 1 skipif (100% executable)"
  regression_pass_rate: "353/353 unit + 10/10 Phase 2 integration + 6/6 new sync lifespan PASS — KHÔNG break Phase 1+2+3 + Plan 04-01..03"
---

# Phase 4 Plan 04: Lifespan Integration central_sync_pool + sync_worker_task Spawn Summary

**One-liner:** Wave 3 INTEGRATION wire Plan 04-01 (sync_outbox trigger) + Plan 04-02 (Settings central_sync_dsn) + Plan 04-03 (sync_worker_loop) vào `create_app()` lifespan hub con — `app.state.central_sync_pool` qua `asyncpg.create_pool(init=_init_central_sync_conn)` register pgvector codec per connection (BLOCKER 2 fix end-to-end PUSH_INSERT_CHUNK_SQL $9 list[float]) + T-04-04-01 mitigation SELECT current_database() fail-fast + `app.state.sync_worker_task = asyncio.create_task(sync_worker_loop(app))` spawn SAU pool ready + graceful shutdown cancel worker + wait_for timeout 10s + close pool + `app/db/dsn.py` shared `_to_asyncpg_dsn` helper (W3 fix circular import) + `rag/flow.py` defensive guard hub_id mismatch + `integration_db_pool` fixture W9 fix — đóng SYNC-01/02/05 worker lifecycle Wave 3 BLOCKING cho Plan 04-05 (admin replay) + Plan 04-06 (checksum scheduler) + Plan 04-07 closeout.

---

## Files Created/Modified

### Created (3 file)

| Path | LOC | Purpose |
|------|-----|---------|
| `api/app/db/dsn.py` | 45 | W3 fix — shared `_to_asyncpg_dsn` helper module trung lập. Plan 04-06 routers/sync.py + checksum_scheduler.py import từ shared module tránh circular import qua app.main → routers chain. |
| `api/tests/integration/test_sync_lifespan_integration.py` | 402 | 7 test (6 mock-based PASS + 1 skipif live DB): boot lifespan + pool init + worker spawn + DSN mismatch fail-fast + BLOCKER 2 init kwarg verify + ChunkPayload roundtrip trigger payload shape + graceful shutdown + live-DB trigger fire skipif. |
| `.planning/phases/04-cross-hub-data-sync/04-04-SUMMARY.md` | — | This summary. |

### Modified (4 file)

| Path | Change | Purpose |
|------|--------|---------|
| `api/app/main.py` | +85 LOC, –7 LOC | `_init_central_sync_conn` module-level helper (pgvector register_vector codec callback BLOCKER 2 fix) + lifespan step 4.5 hub con central_sync_pool init + T-04-04-01 SELECT current_database() verify + lifespan step 10 sync_worker_task spawn (hub con only) + shutdown ngược cancel worker + wait_for timeout 10s + close pool. Xoá inline `_to_asyncpg_dsn` + import từ `app.db.dsn` (W3 fix). Test escape hatch `SYNC_SKIP_CENTRAL_POOL=1`. |
| `api/app/rag/flow.py` | +22 LOC | D-V3-Phase4-D2 defensive guard — `doc_hub_id != Settings.hub_id` → warning log `ingest_skip_hub_id_mismatch` + return (KHÔNG declare chunk row hub_id sai). E-V3-3 isolation Layer 1 carry forward Phase 1. |
| `api/tests/integration/conftest.py` | +70 LOC | `integration_db_pool` fixture session-scope mới (W9 fix) — live asyncpg.create_pool + register_vector init callback + skipif `INTEGRATION_DB_URL`. `hub_app_factory` env auto-set `HUB_ID` + `CENTRAL_SYNC_DSN` + `SYNC_SKIP_CENTRAL_POOL=1` cho hub con (Rule 3 regression fix). |
| `api/tests/unit/test_auth_router_hub_redirect.py` | +5 LOC | `_setup_env` auto-set `SYNC_SKIP_CENTRAL_POOL=1` cho hub con — Rule 3 regression fix (8 test 307 redirect fail-loud do lifespan blocking create_pool host KHÔNG có Postgres). |

---

## Commits

| Commit | Type | Description |
|--------|------|-------------|
| `63c9d3e` | refactor | Task 1 — extract `_to_asyncpg_dsn` sang `app/db/dsn.py` (W3 fix) + main.py import từ shared module. |
| `3b202ac` | feat | Task 2 — lifespan central_sync_pool register_vector + sync_worker_task spawn (SYNC-01/02/05 BLOCKER 2 fix). Bao gồm rag/flow.py hub_id guard + Rule 3 regression auto-fix 2 file test (conftest + auth_router_hub_redirect). |
| `f3633bb` | test | Task 3 — integration test sync lifespan 7 test + `integration_db_pool` fixture (W9 fix). |

**Total:** 3 commits atomic (1 refactor + 1 feat + 1 test).

---

## Test Results

### test_sync_lifespan_integration.py — 6/6 mock PASS + 1 skipif (100% executable)

| Test | Validates |
|------|-----------|
| `test_lifespan_hub_con_init_central_sync_pool` | Hub con boot lifespan → `app.state.central_sync_pool != None` + `app.state.sync_worker_task != None` + task chưa done; SAU shutdown cả 2 = None. |
| `test_lifespan_central_skips_sync_worker` | Central boot lifespan → `central_sync_pool == None` + `sync_worker_task == None` (D-V3-Phase4-A3). |
| `test_lifespan_hub_con_fail_fast_dsn_mismatch` | Mock pool trả `current_database()` SAI ("medinet_hub_yte") → lifespan raise RuntimeError "CENTRAL_SYNC_DSN trỏ sai DB" (T-04-04-01). |
| `test_central_sync_pool_uses_pgvector_init` | **BLOCKER 2 verify** — create_pool call_args_list có ≥ 1 call với `init` kwarg set non-None + callback callable + smoke invoke với mock conn KHÔNG raise. |
| `test_chunk_payload_roundtrip_trigger_shape` | **BLOCKER 2 end-to-end** — parse trigger payload shape: content_hash hex 32 char → 16 bytes; vector 1536-dim list[float]; metadata + heading_path + page_start/end. |
| `test_graceful_shutdown_cancels_worker_within_10s` | Sau `LifespanManager` exit → `worker_task.done() == True` + `mock_pool.close.assert_awaited()`. |
| `test_outbox_trigger_fires_on_chunks_insert` | **SKIP** — `INTEGRATION_DB_URL` không set (live-DB; defer Phase 7 MIGRATE-05). |

**Duration:** 4.95s. **Pass rate:** 6/6 mock (100%) + 1 skipif.

### Regression

| Suite | Result |
|-------|--------|
| `tests/unit/` full unit suite | **353/353 PASS** (32.7s) — KHÔNG break Phase 1+2+3 + Plan 04-01..03 |
| `tests/integration/test_factor_hub_scoped.py` (Phase 2) | **10/10 PASS** — KHÔNG break |
| `tests/integration/test_sync_lifespan_integration.py` (Plan 04-04 mới) | **6/6 mock PASS + 1 skipif** |
| Aggregate `tests/unit/ + Plan 04-04 + Phase 2 integration` | **369/369 PASS + 1 skipif** (37.9s) |
| `ruff check` 6 file changed | All checks passed |
| `mypy --strict app/db/dsn.py app/main.py app/rag/flow.py` | Success: no issues found in 3 source files |

---

## Acceptance Criteria (Plan 04-04)

### Task 1 — Extract `_to_asyncpg_dsn` sang `app/db/dsn.py`

| Criterion | Result |
|-----------|--------|
| File `api/app/db/dsn.py` exists ≥ 30 LOC | 45 LOC |
| `grep -n "def _to_asyncpg_dsn" api/app/db/dsn.py` ≥ 1 | 1 match |
| `grep -n "from app.db.dsn import _to_asyncpg_dsn" api/app/main.py` ≥ 1 | 1 match |
| `grep -c "def _to_asyncpg_dsn" api/app/main.py` = 0 (inline xoá) | 0 matches |
| `pytest tests/unit/test_main_factory.py -v` 9/9 PASS | 9/9 PASS |
| `ruff check + mypy --strict 2 file` | All PASS |

### Task 2 — Lifespan central_sync_pool + sync_worker_task

| Criterion | Result |
|-----------|--------|
| `grep -n "central_sync_pool" api/app/main.py` ≥ 4 | 18 matches |
| `grep -n "sync_worker_task" api/app/main.py` ≥ 4 | 13 matches |
| `grep -n "register_vector" api/app/main.py` ≥ 1 (BLOCKER 2) | 5 matches |
| `grep -n "_init_central_sync_conn" api/app/main.py` ≥ 2 | 3 matches |
| `grep -n "init=_init_central_sync_conn" api/app/main.py` ≥ 1 | 2 matches |
| `grep -n "await asyncpg.create_pool" api/app/main.py` ≥ 2 | 2 matches (M2 db_pool + Phase 4 central_sync_pool) |
| `grep -n 'actual_db != "medinet_central"' api/app/main.py` ≥ 1 | 1 match |
| Phase 2 unit regression 9/9 PASS | 9/9 PASS |
| `ruff + mypy --strict app/main.py` | PASS |

### Task 3 — `integration_db_pool` fixture + integration test

| Criterion | Result |
|-----------|--------|
| `grep -n "integration_db_pool" tests/integration/conftest.py` ≥ 1 | 3 matches |
| `tests/integration/test_sync_lifespan_integration.py` exists ≥ 250 LOC | 402 LOC |
| `test_lifespan_hub_con_init_central_sync_pool` ≥ 1 | 1 match |
| `test_lifespan_central_skips_sync_worker` ≥ 1 | 1 match |
| `test_lifespan_hub_con_fail_fast_dsn_mismatch` ≥ 1 | 1 match |
| `test_central_sync_pool_uses_pgvector_init` ≥ 1 (BLOCKER 2 verify) | 1 match |
| `test_chunk_payload_roundtrip_trigger_shape` ≥ 1 (BLOCKER 2 e2e) | 1 match |
| `test_graceful_shutdown_cancels_worker_within_10s` ≥ 1 | 1 match |
| Integration test PASS ≥ 6 mock + 1 skipif | 6/6 mock PASS + 1 skipif |
| Phase 2+3 integration regression | 10/10 test_factor_hub_scoped.py PASS |
| `ruff check` 2 file | All PASS |

**Tổng: 23/23 acceptance criteria PASS.**

---

## Decisions Made

### LOCKED Carry Forward (Phase Context)

- **D-V3-Phase4-A1:** Outbox + worker mechanism — `sync_worker_task = asyncio.create_task(sync_worker_loop(app))` ở hub con lifespan startup.
- **D-V3-Phase4-A3:** Worker placement = In-process asyncio task hub con only. Central skip spawn → log evidence `sync_worker_task_skipped`.
- **D-V3-Phase4-A5:** Worker config consume `Settings.sync_batch_size/poll_interval/...` (Plan 04-02 ship). Log info `sync_worker_task_started: hub=%s batch_size=%d poll_interval=%.1fs`.
- **D-V3-Phase4-B2:** documents.sync_status lifecycle — worker call `_update_document_sync_status` sau MỖI batch (Plan 04-03 ship, KHÔNG đụng ở Plan 04-04 ngoài spawn).
- **D-V3-Phase4-D2:** Hub con UUID identity từ `medinet_central.hubs.id` row. rag/flow.py defensive guard `doc_hub_id != settings.hub_id` skip ingest + warning log.

### Implementation Details (Plan 04-04 specific)

- **W3 fix LOCKED:** Extract `_to_asyncpg_dsn` sang `api/app/db/dsn.py` module trung lập. Lý do: Plan 04-06 sẽ thêm `routers/sync.py` admin replay endpoint + `checksum_scheduler.py` cần `_to_asyncpg_dsn` — nếu import từ `app.main` thì circular qua `app.main → routers chain → app.routers.sync → app.main`. Shared module nằm ngoài routers chain → mọi consumer import an toàn.
- **BLOCKER 2 fix LOCKED (CR Iteration 1):** `_init_central_sync_conn(conn)` helper module-level invoke `pgvector.asyncpg.register_vector(conn)` per connection. `asyncpg.create_pool(init=_init_central_sync_conn)` register codec lúc connection accept. Worker truyền `$9 = list[float]` qua PUSH_INSERT_CHUNK_SQL → codec encode binary format → Postgres `vector(1536)` column accept. KHÔNG register → asyncpg raise `unknown protocol message type or asyncpg can't encode list to vector` runtime mid-batch.
- **T-04-04-01 mitigation LOCKED:** Sau create_pool, lifespan acquire conn + `fetchval('SELECT current_database()')` verify == 'medinet_central'. Operator paste sai DSN (vd trỏ `medinet_hub_yte` thay vì `medinet_central`) → raise RuntimeError → uvicorn exit 1. KHÔNG silent corrupt cross-hub data.
- **R-V3-1 fail-loud LOCKED:** Hub con central_sync_pool init fail → `raise` exit 1 (KHÔNG silent skip với log warning). Outbox sẽ accumulate vô tận nếu silent + central down lâu → R-V3-1 sync drift HIGH chính xác là rủi ro cần fail-loud. Operator deploy thấy lỗi ngay + fix root cause (DSN sai, central down, network firewall).
- **Graceful shutdown pattern (carry forward Plan 03-02 JWKSCache):** `task.cancel()` + `asyncio.wait_for(task, timeout=10.0)` + `TimeoutError` defensive log + `pool.close()` SAU worker stop. Worker `sync_worker_loop` đã có `asyncio.CancelledError` propagate (Plan 04-03 ship) → cancel sạch.
- **Test escape hatch `SYNC_SKIP_CENTRAL_POOL=1`:** Rule 3 regression fix — `tests/unit/test_auth_router_hub_redirect.py` + `tests/integration/test_factor_hub_scoped.py` boot hub con lifespan với fake DSN trỏ localhost:5432 (no Postgres). Lifespan blocking `asyncpg.create_pool` sẽ raise socket.gaierror → fail-loud → test crash. Flag bypass cho test mode (pattern song song JWKS_SKIP_FETCH Plan 03-02 + COCOINDEX_SKIP_SETUP DEF-05-01). Production KHÔNG bao giờ set flag này. Phase 4 dedicated test `test_sync_lifespan_integration.py` mock `asyncpg.create_pool` riêng → KHÔNG cần skip flag (Test 1-6 verify init path RAN với mock pool).
- **W9 fix LOCKED:** `integration_db_pool` fixture session-scope với `skipif INTEGRATION_DB_URL` env không set. Local dev KHÔNG cần test DB up; Phase 7 MIGRATE-05 wire pytest-docker + alembic apply 0005 trước test live-DB. Fixture register pgvector codec init callback mirror lifespan.
- **rag/flow.py hub_id guard wire qua `_get_settings()` module-level forward reference:** `_get_settings` imported ở dòng 347 sau `index_document` function (line 165) — Python global namespace lookup tại runtime → safe (function body chỉ chạy khi cocoindex flow runtime invoke). KHÔNG raise ImportError import time.
- **`asyncpg.Connection` type annotation cho `_init_central_sync_conn`:** Import `asyncpg` đã có ở main.py line 32 → annotation `conn: asyncpg.Connection` PASS mypy --strict.

### Decisions deferred to next plans

- **Admin replay endpoint** `/api/sync/replay { hub_id, since }` — defer Plan 04-05 (central RBAC + audit log, dùng `central_sync_pool` re-use hoặc spawn new pool tới hub con DSN).
- **Checksum scheduler** lifespan task central — defer Plan 04-06 (spawn pools tới N hub con DSN dict; KHÔNG re-use `central_sync_pool` — central scheduler đọc TỪ hub con).
- **Live-DB integration test smoke E2E** — defer Phase 7 MIGRATE-05 (wire `INTEGRATION_DB_URL` env qua testcontainer/pytest-docker; Test 7 sẽ enable).

---

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Test regression] 2 file test fixture cần auto-set SYNC_SKIP_CENTRAL_POOL=1**

- **Found during:** Task 2 GREEN (sau khi main.py landed) — full unit suite chạy báo 8 test failure trong `test_auth_router_hub_redirect.py`. Pattern song song Plan 03-02 (JWKS_SKIP_FETCH added) + Plan 04-02 (HUB_ID/CENTRAL_SYNC_DSN added).
- **Issue:** Lifespan central_sync_pool init blocking `asyncpg.create_pool` với DSN trỏ `localhost:5432/medinet_central` → `socket.gaierror getaddrinfo failed` runtime (no Postgres trên host test). Plan 04-04 fail-loud re-raise → uvicorn boot abort → TestClient lifespan startup fail → test crash.
- **Fix:** Add escape hatch env var `SYNC_SKIP_CENTRAL_POOL=1` ở lifespan main.py (bypass blocking create_pool cho test mode). Update 2 file test fixture auto-set flag cho hub con scenario.
- **Files modified:** 
  - `api/app/main.py` — add `elif os.environ.get("SYNC_SKIP_CENTRAL_POOL") == "1"` branch logging warning + skip.
  - `api/tests/unit/test_auth_router_hub_redirect.py::_setup_env` — set `SYNC_SKIP_CENTRAL_POOL=1` cho hub con.
  - `api/tests/integration/conftest.py::hub_app_factory` — set `SYNC_SKIP_CENTRAL_POOL=1` + `HUB_ID` + `CENTRAL_SYNC_DSN` cho hub con.
- **Commit:** `3b202ac` (gộp với Task 2 GREEN — logically là 1 unit Rule 3 regression auto-fix).
- **Rationale:** Pattern Rule 3 đã được Plan 03-02 + 03-04 + 04-02 thiết lập (test fixture auto-set hub con required env mỗi khi validator/lifespan blocking added). KHÔNG đổi semantic test, chỉ thêm setenv setup cho hub con scenario.

**2. [Rule 1 - Mypy hint] Unused type: ignore comment cho `register_vector = None`**

- **Found during:** Task 2 mypy --strict — `app\main.py:56: error: Unused "type: ignore" comment [unused-ignore]`.
- **Issue:** Initial draft import block dùng `register_vector = None  # type: ignore[assignment]` (Python 3.12 inferred type). Mypy --strict đủ thông minh để biết hint không cần thiết vì cả 2 branch return cùng type tương thích.
- **Fix:** Xoá `# type: ignore[assignment]` comment.
- **Files modified:** `api/app/main.py`.
- **Commit:** `3b202ac` (inline trong Task 2 GREEN).
- **Rationale:** Rule 1 minor — mypy strict cleanliness.

### Plan-strict adherence

- KHÔNG bump stack version (Python 3.12, FastAPI 0.136.1, pgvector 0.4.2, asyncpg 0.30.0).
- KHÔNG sửa `frontend/`, `STATE.md`, `ROADMAP.md`, `REQUIREMENTS.md` (out-of-scope cho executor).
- KHÔNG dùng `--no-verify` cho commit (sequential mode, pre-commit hooks run).
- KHÔNG đụng `api/migrations/` directory (Plan 04-01 file-disjoint).
- KHÔNG đụng `api/app/config.py` (Plan 04-02 file-disjoint).
- KHÔNG đụng `api/app/sync/` directory (Plan 04-03 file-disjoint).
- KHÔNG xoá inline `_to_asyncpg_dsn` trong `app/rag/setup.py` (duplicate tồn tại — out-of-scope; setup.py KHÔNG circular import nên Plan 04-04 KHÔNG fix).
- Commit message prefix tiếng Anh + body tiếng Việt theo CLAUDE.md §5.

---

## Authentication Gates

**None.** Plan 04-04 thuần lifespan integration + integration test mock-based — KHÔNG cần auth setup. Runtime end-to-end test với live Postgres defer Phase 7 MIGRATE-05 (Test 7 `test_outbox_trigger_fires_on_chunks_insert` skipif `INTEGRATION_DB_URL`).

---

## Known Stubs

**None.** Plan 04-04 ship lifespan integration đầy đủ — `central_sync_pool` real init với mock-able codec callback + `sync_worker_task` real spawn với module-level `sync_worker_loop` consume (Plan 04-03 ship). KHÔNG có data UI stub.

Module entry points hoàn tất cho Plan 04-05 (admin replay) + Plan 04-06 (checksum scheduler) + Plan 04-07 (closeout):
- `app.state.central_sync_pool` — hub con asyncpg.Pool tới central, available cho admin endpoint Plan 04-05.
- `app.state.sync_worker_task` — async task reference, available cho admin "pause worker" Plan 04-05.

---

## Threat Flags

**Không phát hiện threat surface mới ngoài `<threat_model>` của Plan 04-04.** 7 threat (T-04-04-01..07) trong plan đã cover toàn bộ surface:

- T-04-04-01 (Spoofing operator paste sai DSN) → mitigated bởi `SELECT current_database() == 'medinet_central'` fail-fast.
- T-04-04-02 (Tampering doc_hub_id legacy mismatch) → mitigated bởi rag/flow.py defensive guard skip.
- T-04-04-03 (Repudiation lifespan startup/shutdown audit) → mitigated bởi structlog `central_sync_pool_ready` + `sync_worker_task_started` + `sync_worker_task_shutdown_timeout` evidence.
- T-04-04-04 (Info Disclosure DSN credentials log) → mitigated bởi logger chỉ log `hub_name + target_db + pgvector_codec` (KHÔNG full DSN).
- T-04-04-05 (DoS worker hang shutdown) → mitigated bởi `asyncio.wait_for(task, timeout=10.0)` + log warning.
- T-04-04-06 (Integrity pgvector codec NOT register) → **BLOCKER 2 FIX** — `init=_init_central_sync_conn` + Task 4 test verify init param.
- T-04-04-07 (Integrity circular import) → **W3 FIX** — Task 1 extract sang `app/db/dsn.py`.

---

## Verification Status

### Automated (in-process)

- 6/6 mock integration test PASS `test_sync_lifespan_integration.py` (4.95s)
- 1 skipif test (live-DB) — `test_outbox_trigger_fires_on_chunks_insert` defer Phase 7 MIGRATE-05
- 353/353 full unit suite regression PASS (32.7s) — KHÔNG break Phase 1+2+3 + Plan 04-01..03
- 10/10 Phase 2 integration `test_factor_hub_scoped.py` regression PASS
- 369/369 aggregate (unit + Plan 04-04 integration + Phase 2 integration) PASS + 1 skipif (37.9s)
- `ruff check` 6 file changed — All checks passed
- `mypy --strict app/db/dsn.py app/main.py app/rag/flow.py` Success no issues found

### Deferred (cần Postgres runtime + alembic apply 0005)

- Live-DB trigger fire `INSERT INTO chunks` → `sync_outbox` enqueue end-to-end — defer Phase 7 MIGRATE-05 wire `INTEGRATION_DB_URL` env.
- Multi-batch worker push concurrent với 2 worker instance + SELECT FOR UPDATE SKIP LOCKED — defer Phase 7 load test.
- ON CONFLICT (id) DO UPDATE WHERE content_hash IS DISTINCT runtime verify (HNSW vector index disk write thừa avoid) — defer Phase 7.
- documents.sync_status UPDATE end-to-end (trigger 'syncing' + worker 'synced'/'failed'/'partial' multi-chunk-per-document) — defer Phase 7.
- `central_sync_pool` real `pgvector.asyncpg.register_vector` codec runtime với chunks.vector cast `$9::vector` — defer Phase 7 smoke E2E.

---

## Self-Check

### Files Created/Modified Verification

| Claim | Verified |
|-------|----------|
| `api/app/db/dsn.py` exists (45 LOC) | FOUND |
| `api/tests/integration/test_sync_lifespan_integration.py` exists (402 LOC) | FOUND |
| `api/app/main.py` modified — central_sync_pool 18 grep + sync_worker_task 13 grep + register_vector 5 grep + init=_init_central_sync_conn 2 grep + actual_db != medinet_central 1 grep | FOUND all 5 grep PASS |
| `api/app/rag/flow.py` modified — `_phase4_settings = _get_settings` 1 grep + `ingest_skip_hub_id_mismatch` 1 grep | FOUND |
| `api/tests/integration/conftest.py` modified — `integration_db_pool` 3 grep + `hub_app_factory` auto-set `SYNC_SKIP_CENTRAL_POOL` | FOUND |
| `api/tests/unit/test_auth_router_hub_redirect.py` modified — `_setup_env` auto-set `SYNC_SKIP_CENTRAL_POOL=1` | FOUND |

### Commit Verification

| Hash | Verified |
|------|----------|
| `63c9d3e` (refactor Task 1 — extract _to_asyncpg_dsn W3) | FOUND in git log |
| `3b202ac` (feat Task 2 — lifespan central_sync_pool + sync_worker_task + Rule 3 regression fix) | FOUND in git log |
| `f3633bb` (test Task 3 — integration test sync lifespan + integration_db_pool fixture W9) | FOUND in git log |

## Self-Check: PASSED

---

## Performance Metrics

| Metric | Value |
|--------|-------|
| Duration | ~25 phút (3 commit atomic — 1 refactor + 1 feat + 1 test) |
| Tasks completed | 3/3 (Task 1 dsn.py W3 + Task 2 lifespan + Task 3 integration test W9) |
| Files created | 3 (app/db/dsn.py + test_sync_lifespan_integration.py + SUMMARY.md) |
| Files modified | 4 (app/main.py + app/rag/flow.py + tests/integration/conftest.py + tests/unit/test_auth_router_hub_redirect.py) |
| LOC added | ~85 main.py + ~22 flow.py + ~70 conftest + 402 test + 45 dsn.py + 5 fix = **~629 LOC source/test** |
| Tests added | **7** (6 mock-based PASS + 1 skipif live DB) |
| Test pass rate | **6/6 mock PASS (100%)** + 1 skipif — 4.95s aggregate |
| Acceptance criteria | **23/23 PASS** (6 Task 1 + 8 Task 2 + 9 Task 3) |
| Regression | **353/353 unit + 10/10 Phase 2 integration + 6/6 new sync lifespan PASS** — KHÔNG break Phase 1+2+3 + Plan 04-01..03 |
| Lint | ruff + mypy --strict PASS all touched file |
| Commits | 3 atomic (refactor W3 + feat lifespan + test integration W9) |
| Deviations | 2 (Rule 3 regression — 2 file test fixture auto-set SYNC_SKIP_CENTRAL_POOL; Rule 1 mypy minor — xoá unused type: ignore comment) |

---

## Next: Plan 04-05 (Admin Replay Endpoint) + Plan 04-06 (Checksum Scheduler) Wave 4 Parallel

Plan 04-04 đã ship lifespan integration Wave 3. Plan 04-05 + 04-06 mở (file-disjoint):

1. **Plan 04-05 SYNC-02/04 — Admin replay endpoint:** `POST /api/sync/replay { hub_id, since }` central RBAC admin. Reset sync_outbox rows attempt_count=0 + clear next_retry_at → worker re-pickup. Audit log entry. Re-use `app.state.central_sync_pool`? KHÔNG — admin replay manipulate dead row Ở HUB CON DSN (central spawn new pool tới hub con `CHECKSUM_HUB_DSNS_JSON` dict — Plan 04-06 share infrastructure).
2. **Plan 04-06 SYNC-04 — Checksum scheduler:** Central lifespan asyncio task. Daily 2AM count drift + Hourly 1% sample hash drift. Consume `Settings.checksum_hub_dsns` dict (Plan 04-02 ship). Spawn N asyncpg.Pool tới hub con DB (read-only role grant). 2 Prometheus metric ship Plan 04-03 module-level (sync_count_drift + sync_hash_drift).
3. **Plan 04-07 closeout:** Mark SYNC-01..05 complete REQUIREMENTS.md sau Plan 04-04..06 ship. Defer Phase 7 MIGRATE-05 full E2E smoke (3 hub + central + golden path).

Plan 04-04 phụ thuộc Plan 04-01 (sync_outbox schema) + Plan 04-02 (Settings) + Plan 04-03 (worker module) — 3 dependency Wave 1+2 đã ship. Plan 04-05 + 04-06 parallel sau Plan 04-04 ship.

**Phase 4 progress:** 4/7 plan complete (~57%). SYNC-05 đóng (Plan 04-01). SYNC-01/02 worker lifecycle ship end-to-end (Plan 04-02 + 04-03 + 04-04); formally đóng SYNC-01..02 khi Phase 7 MIGRATE-05 full live-DB smoke pass.

---

*Plan 04-04 ship 2026-05-22 sau ~25 phút thực thi. Wave 3 INTEGRATION DONE — lifespan central_sync_pool + sync_worker_task spawn + rag/flow.py hub_id guard + integration_db_pool fixture. 3 commit atomic (1 refactor W3 + 1 feat lifespan + 1 test integration W9). 6/6 mock test PASS + 1 skipif + 353/353 unit + 10/10 Phase 2 integration regression PASS + 23/23 acceptance + ruff + mypy --strict PASS. Next: Plan 04-05 + 04-06 Wave 4 parallel (file-disjoint app/routers/sync.py + app/observability/checksum_scheduler.py).*
