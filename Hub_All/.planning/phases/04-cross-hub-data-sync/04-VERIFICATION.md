---
phase: 04-cross-hub-data-sync
verified: 2026-05-22T00:00:00Z
status: passed
score: 5/5 must-haves verified
overrides_applied: 0
deferred:
  - truth: "Smoke E2E golden path 3 hub + central + outbox sync + cross-hub search + checksum tick + replay endpoint round-trip (runtime live verification)"
    addressed_in: "Phase 7 MIGRATE-05"
    evidence: "ROADMAP Phase 7 SC #5: 'Docker compose mở rộng up đầy đủ (1 Postgres + 1 Redis + 4 FastAPI + Caddy + frontend); golden path 3 hub con + tổng PASS (login → upload → search local + cross-hub → ask → citation)'. Pre-resolved per user decision Plan 04-07 Task 5 SKIP."
  - truth: "Cross-hub search p95 < 1.5s live benchmark (E-V3-2 threshold)"
    addressed_in: "Phase 7 MIGRATE-05"
    evidence: "ROADMAP Phase 7 SC #5: 'cross-hub p95 < 1.5s (E-V3-2)' + E-V3-2 EXIT criteria. Defer Phase 7 smoke live measure — KHÔNG đo được in-process (mock pgvector codec + asyncpg fixture KHÔNG load HNSW index thực)."
  - truth: "Sync drift < 1% rows sau 7 ngày run continuously (E-V3-5 sustained threshold)"
    addressed_in: "Phase 7 staging monitor"
    evidence: "ROADMAP E-V3-5 EXIT criteria: 'Sync drift hub con vs tổng > 1% rows sau 7 ngày run continuously trong Phase 4 staging'. Long-running staging monitor — Phase 7 MIGRATE-05 smoke E2E env + production-like deploy validates."
  - truth: "Real lifespan boot E2E verify checksum_scheduler_task spawn sequence (M-04-06-02)"
    addressed_in: "Phase 7 MIGRATE-05"
    evidence: "deferred-items.md::M-04-06-02 — full unit suite test pollution MemoryError; converted to source-inspection test in Plan 04-06. Real lifespan boot E2E defer Phase 7 với live Postgres + INTEGRATION_DB_URL env wire."
---

# Phase 4: Cross-hub Data Sync Verification Report

**Phase Goal:** Sau khi cocoindex flow hub con ingest xong → push chunks + vector (denormalized) lên `medinet_central.chunks` qua outbox + worker pattern; hub tổng KHÔNG re-embed; idempotent on retry (ON CONFLICT); cross-hub search ở central refactor 1 SQL aggregated; checksum verify periodic; admin replay endpoint.

**Verified:** 2026-05-22
**Status:** PASSED (with documented Phase 7 runtime threshold deferrals)
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths (5 Success Criteria)

| #   | Truth (SC)                                                                                                                                                | Status     | Evidence                                                                                                                                                                                                                                                                                                                                                            |
| --- | --------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | Upload file ở hub con yte → chunks sync sang central trong < 60s (Prometheus metric `sync_lag_seconds{hub_name}`)                                          | VERIFIED   | (a) Migration 0005 Postgres trigger `enqueue_sync_outbox()` AFTER INSERT chunks atomic cùng transaction; (b) `app/sync/worker.py::sync_worker_loop` poll 5s + batch 100 + push central qua `central_sync_pool`; (c) `SYNC_LAG_SECONDS` Histogram `metrics.py:32` label `hub_name`; (d) `_observe_lag()` emits observe per row. Runtime <60s threshold defer Phase 7. |
| 2   | Cross-hub search ở central thấy chunks từ hub con yte + duoc + hcns aggregated; p95 < 1.5s (E-V3-2)                                                       | VERIFIED   | (a) `SearchService._search_cross_hub_impl` refactor 1 SQL `WHERE c.hub_id = ANY($2::uuid[]) ORDER BY vector <=> $1::vector LIMIT $3`; (b) `routers/search.py` `cross_hub_router` central-only mount; (c) HNSW `iterative_scan=relaxed_order + ef_search=200 + max_scan_tuples=20000` carry forward M2. p95 latency runtime defer Phase 7 live measure.              |
| 3   | Idempotent retry KHÔNG dup chunks (kill push mid-batch → re-run KHÔNG sai chunk_count tổng)                                                                | VERIFIED   | `keys.py::PUSH_INSERT_CHUNK_SQL` `ON CONFLICT (id) DO UPDATE SET ... WHERE chunks.content_hash IS DISTINCT FROM EXCLUDED.content_hash` 1 SQL atomic D-V3-Phase4-B1; 18/18 worker unit test PASS verify idempotent retry + concurrent SELECT FOR UPDATE SKIP LOCKED.                                                                                                  |
| 4   | Checksum verify daily metric `sync_drift_total{hub_id, drift_type}` < 1% rows (E-V3-5 threshold)                                                           | VERIFIED   | `observability/checksum_scheduler.py` central FastAPI lifespan asyncio task — daily 2AM `_tick_daily_count` → `SYNC_COUNT_DRIFT{hub_name}` gauge symmetric `abs(diff) / max(hub_count, 1)`; hourly `TABLESAMPLE BERNOULLI(1)` → `SYNC_HASH_DRIFT{hub_name, drift_type=mismatch/missing}` counter. < 1% threshold runtime defer Phase 7 staging monitoring.            |
| 5   | SYNC-05 mechanism chốt — outbox + worker (LOCKED qua D-V3-Phase4-A1)                                                                                      | VERIFIED   | D-V3-Phase4-A1 LOCKED qua `/gsd-discuss-phase 4 --chain` 2026-05-22. Implementation: `sync_outbox` table (migration 0005) + `enqueue_sync_outbox()` trigger AFTER INSERT/DELETE + `app/sync/worker.py::sync_worker_loop` in-process asyncio task hub con lifespan + REJECT cocoindex target / Postgres logical replication.                                          |

**Score:** 5/5 truths VERIFIED (3/5 with runtime metric threshold deferred to Phase 7 MIGRATE-05 — semantic implementation verified in-process).

---

## Required Artifacts (Level 1-4 verification)

| Artifact                                                            | Expected                                                                                | Status     | Details                                                                                                                                                                                                                       |
| ------------------------------------------------------------------- | --------------------------------------------------------------------------------------- | ---------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `api/migrations/versions/0005_sync_outbox_per_hub.py`               | Alembic migration sync_outbox table + trigger + documents.sync_status + skip-central    | VERIFIED   | 225 LOC; table 11 cols + 2 CHECK + 2 partial index; `enqueue_sync_outbox()` explicit jsonb_build_object + vector::float4[] cast + content_hash hex encode; 2 trigger AFTER INSERT/DELETE; skip central `current_database()`. |
| `api/app/sync/__init__.py + keys.py + models.py + metrics.py + worker.py` | sync module ~816 LOC mới                                                                | VERIFIED   | keys.py: 8 SQL constants + CLAIM_PENDING FOR UPDATE SKIP LOCKED + PUSH_INSERT ON CONFLICT (id) DO UPDATE WHERE content_hash IS DISTINCT; models.py: OpType + ChunkPayload hex decode + SyncOutboxRow; metrics.py: 6 collector; worker.py: 338 LOC sync_worker_loop. |
| `api/app/db/dsn.py`                                                 | Shared `_to_asyncpg_dsn` helper W3 fix                                                  | VERIFIED   | `_to_asyncpg_dsn(sqlalchemy_dsn: str) -> str` strip `postgresql+asyncpg://` → `postgresql://`. Imported bởi main.py + checksum_scheduler.py + sync.py replay.                                                                |
| `api/app/observability/checksum_scheduler.py`                       | Central FastAPI lifespan daily 2AM + hourly TABLESAMPLE                                 | VERIFIED   | `checksum_scheduler_loop` skip hub con + `_should_run_daily/_should_run_hourly` + `_tick_daily_count` + `_tick_hourly_hash` TABLESAMPLE BERNOULLI(1) + lazy per-hub Pool init + per-hub error isolation.                     |
| `api/app/services/search_service.py`                                | `_search_cross_hub_impl` refactor 1 SQL aggregated                                      | VERIFIED   | Refactor `WHERE c.hub_id = ANY($2::uuid[]) ORDER BY vector <=> $1::vector` thay fan-out asyncio.gather; public API signature unchanged; HNSW tuning carry forward.                                                            |
| `api/app/routers/search.py`                                         | Router split — `cross_hub_router` central-only mount                                    | VERIFIED   | `search_router` universal + `cross_hub_router = APIRouter(prefix="/api/search", tags=["search-central"])` central-only mount; POST `/cross-hub` endpoint.                                                                     |
| `api/app/routers/sync.py`                                           | POST `/api/sync/replay` admin endpoint dead row recovery                                | VERIFIED   | `@router.post("/replay")` + `SyncReplayRequest` Pydantic + `require_role("admin")` Phase 3 SSO-04 carry forward + reset 4 field WHERE status='dead' AND created_at >= since + audit_logs INSERT defensive inner try/except W8. |
| `api/app/main.py`                                                   | Lifespan central_sync_pool + register_vector + sync_worker_task + checksum_scheduler_task | VERIFIED | `central_sync_pool = asyncpg.create_pool(init=_init_central_sync_conn)` + verify `SELECT current_database() == 'medinet_central'` fail-fast + `sync_worker_task` spawn hub con conditional + `checksum_scheduler_task` central conditional. |
| `api/app/rag/flow.py`                                               | Defensive guard `doc_hub_id != settings.hub_id`                                         | VERIFIED   | Line 193-205 `if _phase4_settings.hub_id is not None: expected_hub_id = uuid.UUID(...); if doc_hub_id != expected_hub_id: warning log + return skip` D-V3-Phase4-D2.                                                          |
| `api/app/config.py`                                                 | Settings 7 field mới + 3 model_validator + 1 length validator                           | VERIFIED   | `hub_id` UUID4 str + `central_sync_dsn` + `checksum_hub_dsns_json` + `sync_batch_size=100` + `sync_poll_interval=5.0` + `sync_max_attempts=5` + `sync_backoff_seconds=[1,5,30,120]` + 3 model_validator fail-fast + length validator. |
| `docker-compose.yml`                                                | Env wire 3 hub con HUB_ID + CENTRAL_SYNC_DSN + central CHECKSUM_HUB_DSNS_JSON           | VERIFIED   | 3 hub con: `${HUB_*_ID:?error}` fail-loud + `CENTRAL_SYNC_DSN: postgresql+asyncpg://...medinet_central`; central: `CHECKSUM_HUB_DSNS_JSON: ${CHECKSUM_HUB_DSNS_JSON:-}` optional lazy.                                       |
| `docker-compose.override.yml.template`                              | FACTOR-04 inherit Phase 4 env placeholder                                               | VERIFIED   | `HUB_ID: ${HUB_{{HUB_UPPER}}_ID:?...}` + `CENTRAL_SYNC_DSN: postgresql+asyncpg://...medinet_central` placeholder substitute qua `make hub-add HUB=<name>`.                                                                   |
| `CLAUDE.md` section 6                                               | Phase 4 DONE row + Phase 4 Cross-hub Data Sync pattern subsection                       | VERIFIED   | Line 154 table row "✅ DONE" + Phase 4 pattern subsection (lines 218+) chi tiết 7 plan + 6 metric + R-V3-1 mitigation + footer changelog.                                                                                    |
| `README.md`                                                         | Cross-hub Sync Deploy Notes section                                                     | VERIFIED   | Section "Cross-hub Sync Deploy Notes (Phase 4 v3.0)" lines 368+ — env list + Alembic migration apply + Prometheus metric + admin replay curl example + rollback procedure.                                                    |

**All artifacts pass Level 1 (exists) + Level 2 (substantive — no stubs) + Level 3 (wired — imports/usage verified) + Level 4 (data flowing — trigger → worker → central via SQL + Pydantic codec).**

---

## Key Link Verification (Wiring)

| From                                 | To                                       | Via                                                                                            | Status   | Details                                                                                                                                                                            |
| ------------------------------------ | ---------------------------------------- | ---------------------------------------------------------------------------------------------- | -------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Postgres trigger AFTER INSERT chunks | `sync_outbox` table                      | `enqueue_sync_outbox()` PL/pgSQL function explicit jsonb_build_object                          | WIRED    | Migration 0005 lines 145-208 trigger + function atomic cùng transaction chunks INSERT.                                                                                              |
| `sync_outbox` rows                   | `sync_worker_loop` claim batch           | `CLAIM_PENDING_SQL` FOR UPDATE SKIP LOCKED batch_size=100                                      | WIRED    | `worker.py::_claim_pending_batch` + `keys.py::CLAIM_PENDING_SQL`.                                                                                                                   |
| `sync_worker_loop`                   | `medinet_central.chunks`                 | `PUSH_INSERT_CHUNK_SQL` ON CONFLICT (id) DO UPDATE WHERE content_hash IS DISTINCT              | WIRED    | `worker.py::_push_inserts` + `central_sync_pool` lifespan init.                                                                                                                    |
| `app/main.py` lifespan hub con       | `sync_worker_loop`                       | `asyncio.create_task(sync_worker_loop(app))`                                                   | WIRED    | main.py:417 spawn + shutdown graceful task.cancel() + wait_for 10s.                                                                                                                |
| `app/main.py` lifespan central       | `checksum_scheduler_loop`                | `asyncio.create_task(checksum_scheduler_loop(app))`                                            | WIRED    | main.py:416 conditional `if settings.hub_name == "central"` spawn.                                                                                                                  |
| `checksum_scheduler_loop`            | `SYNC_COUNT_DRIFT` + `SYNC_HASH_DRIFT`   | `_tick_daily_count` + `_tick_hourly_hash`                                                      | WIRED    | `checksum_scheduler.py` import from `app.sync.metrics`; label `hub_name` consistent W7 fix.                                                                                          |
| Cross-hub search request             | `SearchService.search_cross_hub`         | `routers/search.py::cross_hub_search_endpoint` (central-only mount)                            | WIRED    | `cross_hub_router.post("/cross-hub")` → `service.search_cross_hub(body=body, user=user)` → `_search_cross_hub_impl` 1 SQL.                                                          |
| Admin replay request                 | `audit_logs` non-repudiation             | `sync.py::replay_dead_outbox` INSERT audit_logs after reset 4 field                            | WIRED    | sync.py:242 `INSERT INTO audit_logs` defensive inner try/except W8 fix T-04-06-03.                                                                                                  |
| `Settings.hub_id` env HUB_ID         | `rag/flow.py::index_document` guard      | `if doc_hub_id != settings.hub_id: skip + warning`                                             | WIRED    | flow.py:193-205 D-V3-Phase4-D2 + E-V3-3 Layer 1 isolation carry forward.                                                                                                            |
| Worker fail max_attempts             | `documents.sync_status` enum lifecycle   | `_update_document_sync_status` aggregate CASE 4 state (synced/failed/partial/syncing)          | WIRED    | worker.py:236-261 BLOCKER 1 fix D-V3-Phase4-B2 aggregate update after each batch.                                                                                                    |

**All 10 critical key links verified WIRED.** No NOT_WIRED / PARTIAL gaps found.

---

## Decision Verdict (14 LOCKED D-V3-Phase4-A1..D3)

| Decision           | Mechanism                                                                              | Status   | Evidence                                                                                                              |
| ------------------ | -------------------------------------------------------------------------------------- | -------- | --------------------------------------------------------------------------------------------------------------------- |
| D-V3-Phase4-A1     | Outbox + worker (REJECT cocoindex target / logical replication)                        | VERIFIED | `app/sync/worker.py::sync_worker_loop` + `sync_outbox` table migration 0005.                                          |
| D-V3-Phase4-A2     | sync_outbox table per-DB hub con (skip central)                                        | VERIFIED | Migration 0005 lines 80-86 `current_database() == 'medinet_central'` skip guard runtime + return no-op.               |
| D-V3-Phase4-A3     | In-process asyncio worker hub con lifespan                                             | VERIFIED | main.py line 417 `asyncio.create_task(sync_worker_loop(app))` conditional `settings.hub_name != "central"`.            |
| D-V3-Phase4-A4     | Postgres trigger AFTER INSERT/DELETE chunks → enqueue function                         | VERIFIED | Migration 0005 lines 199-208 `CREATE TRIGGER chunks_after_insert/delete_enqueue_sync_outbox` AFTER ROW EXECUTE FUNCTION. |
| D-V3-Phase4-A5     | batch_size=100, poll=5s, backoff=[1,5,30,120]s, max_attempts=5, SKIP LOCKED            | VERIFIED | Settings defaults config.py:157-163 + worker.py uses; `keys.py::CLAIM_PENDING_SQL` FOR UPDATE SKIP LOCKED.            |
| D-V3-Phase4-B1     | ON CONFLICT (id) DO UPDATE WHERE content_hash IS DISTINCT 1 statement atomic           | VERIFIED | `keys.py::PUSH_INSERT_CHUNK_SQL` line 89-104 `ON CONFLICT (id) DO UPDATE SET ... WHERE chunks.content_hash IS DISTINCT FROM EXCLUDED.content_hash`. |
| D-V3-Phase4-B2     | Async outbox decoupled — documents.sync_status enum lifecycle                          | VERIFIED | Migration 0005 ALTER TABLE documents ADD sync_status TEXT CHECK 5 value + trigger initial 'pending'→'syncing' idempotent + worker `_update_document_sync_status` aggregate. |
| D-V3-Phase4-B3     | op_type enum insert\|delete — DELETE event HARD DELETE central                         | VERIFIED | `models.py::OpType` enum 2 value + `keys.py::PUSH_DELETE_CHUNK_SQL` `DELETE FROM chunks WHERE id = ANY($1::uuid[])` hard delete. |
| D-V3-Phase4-C1     | Daily 2AM COUNT(*) + Hourly TABLESAMPLE BERNOULLI(1) hash                              | VERIFIED | `checksum_scheduler.py::_tick_daily_count` COUNT(*) per hub vs central + `_tick_hourly_hash` TABLESAMPLE BERNOULLI(1). |
| D-V3-Phase4-C2     | Mark dead + Prometheus alert + Admin replay endpoint                                   | VERIFIED | `worker.py::_handle_failures` MARK_DEAD + `SYNC_DEAD_TOTAL` Counter + `routers/sync.py::replay_dead_outbox` admin endpoint reset 4 field. |
| D-V3-Phase4-C3     | Checksum runner central lifespan asyncio task                                          | VERIFIED | main.py:416 + `checksum_scheduler.py::checksum_scheduler_loop` naive `asyncio.sleep` loop KHÔNG APScheduler dep.       |
| D-V3-Phase4-D1     | SearchService._search_cross_hub_impl refactor 1 SQL aggregated                         | VERIFIED | `search_service.py` line 346+ `_search_cross_hub_impl` `WHERE c.hub_id = ANY($2::uuid[]) ORDER BY vector <=> $1::vector LIMIT $3`. |
| D-V3-Phase4-D2     | hub_id UUID Settings.hub_id env HUB_ID boot fail-loud                                  | VERIFIED | config.py `_validate_hub_id_uuid` field validator + `_enforce_hub_id_for_hub_con` model_validator; rag/flow.py guard.   |
| D-V3-Phase4-D3     | Strip /api/search/cross-hub ở hub con                                                  | VERIFIED | `routers/search.py::cross_hub_router` central-only mount conditional include trong main.py block central-only.        |

**14/14 LOCKED decisions implemented and reflected in code.**

---

## Requirements Coverage

| Requirement | Source Plan          | Description                                                                         | Status      | Evidence                                                                                                                                                                                                                                                          |
| ----------- | -------------------- | ----------------------------------------------------------------------------------- | ----------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| SYNC-01     | 04-01, 04-02, 04-03, 04-04 | Push chunks+vector hub con → central (denormalized, KHÔNG re-embed)                  | SATISFIED   | Migration 0005 trigger + Settings.hub_id + central_sync_dsn + `app/sync/worker.py::_push_inserts` + lifespan central_sync_pool init register_vector codec. REQUIREMENTS.md line 82 `[x] SYNC-01 ✅ Phase 4`.                                                       |
| SYNC-02     | 04-01, 04-03         | ON CONFLICT idempotent retry                                                        | SATISFIED   | `keys.py::PUSH_INSERT_CHUNK_SQL` `ON CONFLICT (id) DO UPDATE WHERE chunks.content_hash IS DISTINCT FROM EXCLUDED.content_hash` + 18/18 worker unit test idempotent + concurrent SKIP LOCKED. REQUIREMENTS.md line 83 `[x] SYNC-02 ✅ Phase 4`.                       |
| SYNC-03     | 04-05                | Cross-hub search aggregated central (KHÔNG fan-out HTTP)                            | SATISFIED   | `_search_cross_hub_impl` refactor 1 SQL `WHERE c.hub_id = ANY` + router split central-only; backward compat public API unchanged. REQUIREMENTS.md line 84 `[x] SYNC-03 ✅ Phase 4`.                                                                                |
| SYNC-04     | 04-06                | Checksum verify periodic + admin replay                                             | SATISFIED   | `checksum_scheduler.py` daily 2AM COUNT + hourly TABLESAMPLE + `POST /api/sync/replay` reset 4 field WHERE status='dead' + audit_logs INSERT. REQUIREMENTS.md line 85 `[x] SYNC-04 ✅ Phase 4`.                                                                    |
| SYNC-05     | 04-01..07            | Sync mechanism chốt (outbox + worker via D-V3-Phase4-A1)                            | SATISFIED   | D-V3-Phase4-A1 LOCKED `/gsd-discuss-phase 4 --chain` 2026-05-22; full implementation across 7 plans. REQUIREMENTS.md line 85 `[x] SYNC-05 ✅ Phase 4`.                                                                                                            |

**5/5 SYNC requirements SATISFIED. No orphaned requirements.**

---

## Data-Flow Trace (Level 4)

| Artifact                                    | Data Variable          | Source                                                                  | Produces Real Data | Status   |
| ------------------------------------------- | ---------------------- | ----------------------------------------------------------------------- | ------------------ | -------- |
| `app/sync/worker.py::sync_worker_loop`      | `batch` (SyncOutboxRow)| `CLAIM_PENDING_SQL` FOR UPDATE SKIP LOCKED `local_pool` asyncpg          | YES (real DB query)| FLOWING  |
| `_push_inserts`                             | `payload` (ChunkPayload)| Pydantic model_validate(row.payload) hex decode content_hash             | YES (decoded bytes)| FLOWING  |
| `cross_hub_search_endpoint`                 | `result` (search rows) | `SearchService.search_cross_hub` → `_search_cross_hub_impl` real SQL    | YES (real DB query)| FLOWING  |
| `checksum_scheduler_loop`                   | `count_hub`, `count_central` | `SELECT COUNT(*)` per hub vs central                            | YES (real DB query)| FLOWING  |
| `replay_dead_outbox`                        | `rows_replayed` (int)  | UPDATE sync_outbox SET status='pending', attempt_count=0, ... RETURNING | YES (real DB query)| FLOWING  |
| `rag/flow.py::index_document` guard         | `doc_hub_id`, `expected_hub_id` | `doc_row["hub_id"]` Postgres SELECT + `settings.hub_id` env    | YES (real DB row + env)| FLOWING |

**All 6 traced data flows produce real data from DB queries or env config. No HOLLOW props, STATIC fallbacks, or DISCONNECTED sources.**

---

## Behavioral Spot-Checks

| Behavior                                                                | Command/Evidence                                                                | Result                                                  | Status |
| ----------------------------------------------------------------------- | ------------------------------------------------------------------------------- | ------------------------------------------------------- | ------ |
| `sync_outbox` migration syntax + structure                              | Plan 04-01: 17/17 unit + 293/293 + 10/10 Phase 1 regression PASS               | All test PASS                                           | PASS   |
| Settings 7 field + 3 model_validator + 1 length validator               | Plan 04-02: 17/17 unit + 310/310 regression PASS                               | All test PASS                                           | PASS   |
| sync module worker + ChunkPayload + 6 Prometheus collector              | Plan 04-03: 43/43 unit (12 models + 13 metrics + 18 worker) + 353/353 PASS     | All test PASS + idempotent + lifecycle + retry + dead verified | PASS   |
| Lifespan central_sync_pool + sync_worker_task spawn                     | Plan 04-04: 6/6 mock integration + 1 skipif live-DB + 369/369 regression PASS  | All test PASS                                           | PASS   |
| Cross-hub search refactor 1 SQL aggregated + router split central-only  | Plan 04-05: 8/8 unit + 15/15 integration + 361/361 regression PASS             | All test PASS + backward compat verified                | PASS   |
| Checksum scheduler + admin /api/sync/replay + audit_logs                | Plan 04-06: 22/22 unit (10 checksum + 12 replay) + 21/21 integration + 383/383 | All test PASS                                           | PASS   |
| Docker compose config syntax validate                                   | Plan 04-02: `docker compose config --quiet` exit 0                             | PASS                                                    | PASS   |
| Full E2E golden path 3 hub + central live runtime                       | Plan 04-07 Task 5 SKIP pre-resolved per user decision — defer Phase 7          | SKIP — runtime verification deferred                    | SKIP   |

**Aggregate: 113 unit + 21 integration test PASS in-process. 1 skipif live-DB integration test deferred Phase 7 MIGRATE-05.**

---

## Anti-Patterns Found

| File                                  | Line  | Pattern                                                       | Severity | Impact                                                                                          |
| ------------------------------------- | ----- | ------------------------------------------------------------- | -------- | ----------------------------------------------------------------------------------------------- |
| `api/app/main.py`                     | 108   | `redis_asyncio.from_url(...)` untyped call (pre-existing)     | Info     | Pre-existing M2 — out of scope Phase 4. Documented `deferred-items.md::M-04-06-01`. Defer chore. |
| `api/app/sync/worker.py`              | 75    | `# noqa: C901,PLR0912` monolithic loop intentional            | Info     | Documented design — D-V3-Phase4-A5 single loop function intentional readability vs flake8 metric. |
| `api/app/observability/checksum_scheduler.py` | 198 | `# noqa: C901` naive cron loop intentional                    | Info     | Documented design — D-V3-Phase4-C3 KHÔNG APScheduler dep, single-purpose loop intentional.       |

**No blocker anti-patterns. No TODO/FIXME/PLACEHOLDER stubs in Phase 4 code. No empty return `[]/{}/null` from API endpoints. No hardcoded empty props.**

---

## Deferred Items (Addressed in Later Milestone Phases)

Per Step 9b filtering — items addressed by later phases of v3.0 milestone are documented and do NOT block phase status. All 4 deferred items below are explicitly part of Phase 7 MIGRATE-05's scope per v3.0 ROADMAP critical path (1 → 2 → 3 → 4 → 7).

| #   | Item                                                                                                                                                                                  | Addressed In       | Evidence                                                                                                                       |
| --- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------ | ------------------------------------------------------------------------------------------------------------------------------ |
| 1   | Smoke E2E golden path 3 hub con + central + outbox sync + cross-hub search + checksum tick + replay endpoint round-trip                                                               | Phase 7 MIGRATE-05 | ROADMAP Phase 7 SC #5 "Docker compose mở rộng up đầy đủ; golden path 3 hub con + tổng PASS (login → upload → search local + cross-hub → ask → citation)". |
| 2   | Cross-hub search p95 < 1.5s live benchmark (E-V3-2 threshold)                                                                                                                          | Phase 7 MIGRATE-05 | ROADMAP Phase 7 SC #5 "cross-hub p95 < 1.5s (E-V3-2)" + E-V3-2 EXIT criteria.                                                  |
| 3   | Sync drift < 1% rows sau 7 ngày run continuously (E-V3-5 sustained threshold)                                                                                                          | Phase 7 staging    | ROADMAP E-V3-5 EXIT criteria "Sync drift > 1% rows sau 7 ngày run continuously trong Phase 4 staging" — long-running monitor.   |
| 4   | Real lifespan boot E2E verify `checksum_scheduler_task` spawn sequence (M-04-06-02)                                                                                                    | Phase 7 MIGRATE-05 | `deferred-items.md::M-04-06-02` — full unit suite test pollution MemoryError; converted to source-inspection test in Plan 04-06. |

**Deferred items do NOT affect status — they are addressed by Phase 7 MIGRATE-05 per v3.0 ROADMAP design.**

---

## Gaps Summary

**No blocking gaps found.** Phase 4 ships Cross-hub Data Sync infrastructure complete:

1. **Goal achievement:** 5/5 Success Criteria semantic verified in-process; runtime metric thresholds (sync_lag < 60s, p95 < 1.5s, drift < 1%) explicitly deferred Phase 7 MIGRATE-05 per pre-resolved user decision (consistent with Phase 2/3 closeout pattern).
2. **Decision implementation:** 14/14 LOCKED D-V3-Phase4-A1..D3 reflected in code with concrete evidence — outbox + worker mechanism (A1), table per-hub skip central (A2), in-process asyncio (A3), trigger AFTER INSERT/DELETE (A4), batch 100/poll 5s/backoff (A5), ON CONFLICT idempotent (B1), documents.sync_status lifecycle (B2), op_type insert/delete hard delete (B3), daily 2AM + hourly TABLESAMPLE (C1), mark dead + replay endpoint (C2), central lifespan task (C3), 1 SQL aggregated (D1), Settings.hub_id env (D2), strip cross-hub hub con (D3).
3. **Requirement coverage:** 5/5 SYNC-01..05 SATISFIED; REQUIREMENTS.md marked `[x]`.
4. **Backward compat:** M2 unchanged — `SearchService.search_cross_hub()` signature preserved; `/api/sync/*` M2 COMPAT stubs preserved; new `/api/sync/replay` appended.
5. **Test evidence:** 113 unit + 21 integration test PASS in-process + 383/383 unit regression + Phase 1+2+3 regression PASS (no break).
6. **Observability:** 6 Prometheus metrics shipped (sync_lag_seconds, sync_outbox_pending, sync_attempt_total, sync_dead_total, sync_count_drift, sync_hash_drift) with `hub_name` label bounded ~240 series.
7. **STRIDE mitigations:** ~36 threats addressed per CR Iteration 1 — BLOCKER 1 lifecycle (D-V3-Phase4-B2 first-chunk-per-document idempotent UPDATE), BLOCKER 2 pgvector serialization end-to-end (trigger jsonb_build_object + vector::float4[] cast + content_hash hex encode + ChunkPayload field_validator hex decode + register_vector codec lifespan).

**Final status:** PASSED. Runtime threshold verification (latency, drift ratio, smoke E2E) is part of Phase 7 MIGRATE-05's design scope per v3.0 ROADMAP — these are deferred items per Step 9b filtering, not gaps.

---

## Verification Recommendation

**Phase 4 PASSED.** Ready to proceed to:
- `/gsd-discuss-phase 5` Reverse Proxy + Frontend Subpath (PROXY-01..04) — parallel-able branch.
- `/gsd-discuss-phase 6` System Settings Sync (SETTINGS-01..04) — parallel-able branch.
- `/gsd-code-review 4` (optional advisory) — code review trên ~30 commits Phase 4 covering 7 plan ship + 14 decision LOCKED + ~36 STRIDE threat + 6 Prometheus metric infrastructure.

Phase 4 ships complete cross-hub data sync infrastructure with no functional gaps. All Success Criteria, decisions, and requirements traceable to concrete code artifacts with substantive implementation, proper wiring, and verified data flow. Runtime threshold measurement (latency, drift) intentionally deferred to Phase 7 MIGRATE-05 per pre-resolved user decision and v3.0 ROADMAP critical path.

---

_Verified: 2026-05-22_
_Verifier: Claude (gsd-verifier)_
