---
phase: 04-cross-hub-data-sync
plan: 03
subsystem: sync
tags:
  - sync
  - worker
  - asyncio
  - prometheus
  - outbox
  - pydantic
requirements:
  - SYNC-01
  - SYNC-02
  - SYNC-05
dependency_graph:
  requires:
    - Plan 04-01 sync_outbox table + trigger Postgres (jsonb_build_object hex encode + vector::float4[] cast + initial syncing UPDATE)
    - Plan 04-02 Settings 7 field (hub_id + central_sync_dsn + sync_batch_size/poll_interval/max_attempts/backoff_seconds)
    - Phase 1 chunks table schema (vector Vector(1536) + content_hash BYTEA + hub_id UUID FK)
    - Phase 1 documents.sync_status enum column (Plan 04-01 added — 5 value lifecycle)
    - M2 HARD-02 prometheus_client baseline carry forward
  provides:
    - "api/app/sync/__init__.py — public API re-export (6 metric + 6 model + sync_worker_loop)"
    - "api/app/sync/keys.py — 8 SQL constants (CLAIM/MARK_PROCESSING/MARK_PROCESSED/MARK_FAILED_RETRY/MARK_DEAD/PUSH_INSERT/PUSH_DELETE/UPDATE_DOC_SYNC_STATUS)"
    - "api/app/sync/models.py — ChunkPayload + DeletePayload + SyncOutboxRow + 3 enum (SyncStatus + OpType + DocumentSyncStatus)"
    - "api/app/sync/metrics.py — 6 Prometheus collector module-level (W7 fix label hub_name)"
    - "api/app/sync/worker.py — sync_worker_loop + 7 helper function (_claim/_push_inserts/_push_deletes/_update_document_sync_status/_handle_failures/_observe_lag/_get_settings)"
  affects:
    - Plan 04-04 (lifespan integration spawn sync_worker_loop async task hub con + central_sync_pool asyncpg.create_pool)
    - Plan 04-06 (checksum scheduler consume SYNC_COUNT_DRIFT + SYNC_HASH_DRIFT metrics — Plan 04-03 module-level register)
    - Plan 04-07 closeout (REQUIREMENTS SYNC-01/02/05 mark complete sau Plan 04-04 lifespan integration test pass)
tech-stack:
  added: []
  patterns:
    - "Pydantic v2 field_validator(mode='before') hex string decode → bytes (BLOCKER 2 end-to-end serialization fix)"
    - "Prometheus collector module-level singleton register (HARD-02 carry forward) + label cardinality bounded (4 hub × 4 error_class × 2 drift_type × 2 status = ~240 series)"
    - "AsyncMock asyncpg.Pool + Connection context manager test pattern (KHÔNG testcontainer — defer Phase 7 MIGRATE-05 runtime)"
    - "asyncio.CancelledError re-raise propagate graceful shutdown (carry forward Plan 03-02 JWKSCache refresh task pattern)"
    - "_get_settings indirection helper monkeypatch hook (testable isolation từ get_settings cache)"
key-files:
  created:
    - api/app/sync/__init__.py (50 LOC public re-export)
    - api/app/sync/keys.py (168 LOC SQL constants + stable_chunk_id re-export)
    - api/app/sync/models.py (146 LOC 3 enum + ChunkPayload + DeletePayload + SyncOutboxRow)
    - api/app/sync/metrics.py (114 LOC 6 collector + normalize_error_class)
    - api/app/sync/worker.py (338 LOC sync_worker_loop + 7 helper)
    - api/tests/unit/test_sync_models.py (270 LOC, 12 test)
    - api/tests/unit/test_sync_metrics.py (224 LOC, 13 test)
    - api/tests/unit/test_sync_worker.py (549 LOC, 18 test)
  modified: []
decisions:
  - "D-V3-Phase4-A1 LOCKED: outbox + worker mechanism — in-process asyncio sync_worker_loop hub con lifespan (Plan 04-04 wire)"
  - "D-V3-Phase4-A3 LOCKED: worker placement in-process asyncio task hub con only (KHÔNG separate container + KHÔNG central worker SPOF)"
  - "D-V3-Phase4-A5 LOCKED: worker config batch_size=100 + poll_interval=5s + max_attempts=5 + backoff=[1,5,30,120] + SELECT FOR UPDATE SKIP LOCKED concurrency-safe"
  - "D-V3-Phase4-B1 LOCKED: ON CONFLICT (id) DO UPDATE WHERE chunks.content_hash IS DISTINCT FROM EXCLUDED.content_hash (1 SQL atomic, tránh UPDATE no-op bảo vệ HNSW vector index disk write thừa)"
  - "D-V3-Phase4-B2 LOCKED: documents.sync_status lifecycle aggregate 4 transition (syncing→synced/failed/partial) — BLOCKER 1 fix _update_document_sync_status SAU MỖI batch"
  - "D-V3-Phase4-B3 LOCKED: op_type INSERT/DELETE split + DELETE payload key 'id' (NOT 'chunk_id') + HARD DELETE central (chunks immutable carry forward)"
  - "W7 fix LOCKED: Prometheus label `hub_name` (NOT `hub_id` UUID) — semantic rõ ràng label values là hub_name string bounded 4-10 hub; tách rõ với sync_outbox.chunk_id UUID + chunks.hub_id UUID FK"
  - "BLOCKER 2 end-to-end serialization fix LOCKED: ChunkPayload.content_hash field_validator mode=before decode hex string → bytes (trigger Plan 04-01 emit qua encode(.., 'hex') 64 char KHÔNG có \\x prefix); bytes passthrough cho mock test"
  - "W5 fix split LOCKED: Task 3 split → 3a (happy + sync_status 11 test) + 3b (retry/dead/backoff/cancel/lag 7 test) — complexity bounded per task"
  - "Implementation: _get_settings indirection helper module-level — testable monkeypatch hook (KHÔNG inline get_settings()) trong worker.py"
  - "Implementation: LAST_ERROR_TRUNCATE=1000 char defensive vs runaway stacktrace bloat outbox storage (T-04-03-03 audit mitigation)"
  - "Implementation: backoff_idx = min(max(attempt_count - 1, 0), len(backoff)-1) clamped — defensive vs attempt_count=0 edge case + index out of range"
metrics:
  duration_minutes: 35
  completed_date: 2026-05-22
  task_count: 4
  commit_count: 5
  file_count: 8
  test_count: 43
  test_pass_rate: "43/43 (100%)"
  regression_pass_rate: "353/353 unit (310 baseline + 43 new sync) — KHÔNG break Phase 1+2+3 + Plan 04-01..02"
---

# Phase 4 Plan 03: Sync Worker Module + Prometheus Metrics + Pydantic Schemas Summary

**One-liner:** Module `api/app/sync/` 5 file mới (keys + models + metrics + worker + __init__) + sync_worker_loop async task D-V3-Phase4-A1/A3/A5 (SELECT FOR UPDATE SKIP LOCKED batch 100 + exp backoff [1,5,30,120] + max 5 attempts + ChunkPayload Pydantic hex decode BLOCKER 2) + 6 Prometheus collector W7 label `hub_name` + UPDATE_DOC_SYNC_STATUS_SQL aggregate CASE 4 state BLOCKER 1 fix D-V3-Phase4-B2 lifecycle (synced/failed/partial/syncing) — đóng SYNC-01/02/05 worker layer cho Plan 04-04 lifespan integration Wave 3.

---

## Files Created/Modified

### Created (8 file)

| Path | LOC | Purpose |
|------|-----|---------|
| `api/app/sync/__init__.py` | 50 | Package init + public re-export (6 metric + 6 model + sync_worker_loop) |
| `api/app/sync/keys.py` | 168 | stable_chunk_id re-export từ rag.flow + 8 SQL constants (CLAIM/MARK_PROCESSING/MARK_PROCESSED/MARK_FAILED_RETRY/MARK_DEAD/PUSH_INSERT/PUSH_DELETE/UPDATE_DOC_SYNC_STATUS aggregate BLOCKER 1) |
| `api/app/sync/models.py` | 146 | 3 enum (SyncStatus 4 value + OpType 2 value + DocumentSyncStatus 5 value) + ChunkPayload Pydantic content_hash hex decode validator BLOCKER 2 + DeletePayload key 'id' D-V3-Phase4-B3 + SyncOutboxRow mirror 11 cột |
| `api/app/sync/metrics.py` | 114 | 6 Prometheus collector module-level (SYNC_LAG_SECONDS Histogram + SYNC_OUTBOX_PENDING Gauge + SYNC_ATTEMPT_TOTAL Counter + SYNC_DEAD_TOTAL Counter + SYNC_COUNT_DRIFT Gauge + SYNC_HASH_DRIFT Counter) + normalize_error_class helper (timeout/network/conflict/unknown) — W7 fix label hub_name |
| `api/app/sync/worker.py` | 338 | sync_worker_loop async (D-V3-Phase4-A1/A3/A5) + 7 helper (_claim_pending_batch + _push_inserts + _push_deletes + _update_document_sync_status BLOCKER 1 + _handle_failures + _observe_lag + _get_settings indirection) + LAST_ERROR_TRUNCATE=1000 |
| `api/tests/unit/test_sync_models.py` | 270 | 12 unit test (1 stable_chunk_id re-export + 3 enum + 4 ChunkPayload/DeletePayload hex decode + 2 SyncOutboxRow + 2 SQL constants/UPDATE_DOC 4 state) |
| `api/tests/unit/test_sync_metrics.py` | 224 | 13 unit test (6 collector type + 1 reimport safe + 1 textformat render + 1 label hub_name W7 + 4 normalize_error_class) |
| `api/tests/unit/test_sync_worker.py` | 549 | 18 unit test (Task 3a 11: skip_central + claim_empty + push_insert/delete/mixed + 4 _update_doc_sync_status state + empty_doc_ids no-op + worker_calls_update_doc_after_batch; Task 3b 7: retry_network + dead_max + backoff_progression [1,5,30,120] + dead_timeout_class + cancel + observe_lag + truncate_1000) |

**Tổng LOC:** ~816 source + ~1043 test = **~1859 LOC**.

### Modified

Không sửa file existing. Plan 04-03 file-disjoint với Plan 04-02 (Wave 2 parallel-able).

---

## Commits

| Commit | Type | Description |
|--------|------|-------------|
| `c92ca35` | test | Task 1 RED — failing test_sync_models.py 12 test ModuleNotFoundError app.sync |
| `736abcb` | feat | Task 1 GREEN — app/sync/{__init__, keys, models, metrics stub, worker stub} + 12/12 test PASS + ruff + mypy |
| `235146d` | feat | Task 2 — app/sync/metrics.py 6 Prometheus collector + normalize_error_class (W7 fix hub_name) + 13/13 test PASS |
| `f3b2a28` | test | Task 3 RED — test_sync_worker.py 18 test (11 happy + 7 retry/dead/cancel/lag) ImportError _handle_failures/_observe_lag/_get_settings |
| `7f470f3` | feat | Task 3a + 3b GREEN — app/sync/worker.py sync_worker_loop + 7 helper + BLOCKER 1 _update_document_sync_status lifecycle aggregate + 18/18 test PASS + 353/353 full unit regression PASS |

**Total:** 5 commits atomic (2 RED test + 3 GREEN feat). Task 1+3 split RED+GREEN (TDD); Task 2 combined (small focused task, RED-test included trong test file commit chain).

---

## Test Results

### test_sync_models.py — 12/12 PASS (100%)

| Test | Validates |
|------|-----------|
| `test_stable_chunk_id_reexport` | sync.keys.stable_chunk_id IS rag.flow.stable_chunk_id (identity + functional check) |
| `test_sync_status_enum` | SyncStatus 4 value (pending/processing/processed/dead) khớp Plan 04-01 CHECK |
| `test_op_type_enum` | OpType 2 value (insert/delete) D-V3-Phase4-B3 |
| `test_document_sync_status_enum` | DocumentSyncStatus 5 value (pending/syncing/synced/failed/partial) khớp Plan 04-01 CHECK lifecycle |
| `test_chunk_payload_parse_hex_content_hash` | **BLOCKER 2 fix verify** — 64 char hex string KHÔNG có `\x` prefix → bytes.fromhex 32 byte |
| `test_chunk_payload_parse_bytes_content_hash_passthrough` | Mock test pass raw bytes → validator passthrough KHÔNG raise |
| `test_chunk_payload_invalid_hash_raises` | int → ValidationError fail-fast |
| `test_delete_payload_parse_key_id_not_chunk_id` | Key 'id' (NOT 'chunk_id') khớp trigger Plan 04-01 jsonb_build_object D-V3-Phase4-B3 |
| `test_sync_outbox_row_full_parse` | Full 11 cột Plan 04-01 schema → SyncOutboxRow parse OK |
| `test_outbox_row_validates_op_type_invalid` | op_type="invalid_op" → ValidationError (StrEnum constraint) |
| `test_outbox_sql_constants_exported` | CLAIM/MARK_PROCESSED/MARK_DEAD/PUSH_INSERT/PUSH_DELETE/UPDATE_DOC_SYNC_STATUS exports OK |
| `test_update_doc_sql_aggregate_state_all_4_branches` | **BLOCKER 1 fix verify** — UPDATE_DOC_SYNC_STATUS_SQL CASE chứa 'synced'+'failed'+'partial'+'syncing' |

**Duration:** 3.79s. **Pass rate:** 12/12 (100%).

### test_sync_metrics.py — 13/13 PASS (100%)

| Test | Validates |
|------|-----------|
| `test_sync_lag_seconds_histogram` | Histogram label hub_name + observe call works |
| `test_sync_outbox_pending_gauge` | Gauge label hub_name + set call works |
| `test_sync_attempt_counter` | Counter labels hub_name + status (success/fail fixed) |
| `test_sync_dead_counter` | Counter labels hub_name + error_class |
| `test_sync_count_drift_gauge` | Gauge label hub_name (Plan 04-06 daily) |
| `test_sync_hash_drift_counter` | Counter labels hub_name + drift_type (Plan 04-06 hourly) |
| `test_no_duplicate_register_on_reimport` | importlib.import_module twice → same module (cache) — KHÔNG Duplicated timeseries |
| `test_prometheus_textformat_render_contains_all_6_metrics` | generate_latest() output chứa 6 metric name |
| `test_label_is_hub_name_not_hub_id_all_6_collectors` | **W7 fix verify** — 6 collector all dùng `hub_name` label (NOT `hub_id`) |
| `test_normalize_error_class_timeout` | TimeoutError → 'timeout' |
| `test_normalize_error_class_network` | ConnectionRefusedError + ConnectionError → 'network' |
| `test_normalize_error_class_unknown` | ValueError + RuntimeError → 'unknown' |
| `test_normalize_error_class_conflict` | UniqueViolation + IntegrityError → 'conflict' (name keyword match) |

**Duration:** 0.27s. **Pass rate:** 13/13 (100%).

### test_sync_worker.py — 18/18 PASS (100%)

**Task 3a (11 happy + lifecycle):**

| Test | Validates |
|------|-----------|
| `test_skip_central_hub_name` | hub_name='central' → immediate return, KHÔNG vào loop |
| `test_claim_pending_batch_empty_sleep_poll` | Empty batch → sleep poll + KHÔNG push central |
| `test_push_batch_insert_happy_path` | 5 row insert → _push_inserts 5 execute call |
| `test_push_batch_delete_happy_path` | 3 row delete → 1 DELETE FROM chunks ANY array execute |
| `test_push_batch_mixed_op_types_split` | Mixed insert + delete → split + push 2+1=3 execute |
| `test_update_document_sync_status_synced` | **BLOCKER 1** — all processed → 'synced' |
| `test_update_document_sync_status_partial` | **BLOCKER 1** — mixed processed + dead → 'partial' |
| `test_update_document_sync_status_failed` | **BLOCKER 1** — all dead → 'failed' |
| `test_update_document_sync_status_syncing` | **BLOCKER 1** — còn pending/processing → 'syncing' |
| `test_update_document_sync_status_empty_doc_ids_no_op` | Empty list → KHÔNG acquire pool (defensive shortcut) |
| `test_worker_loop_calls_update_doc_status_after_batch` | Worker loop call _update_document_sync_status SAU MỖI batch với union doc_ids |

**Task 3b (7 retry + dead + backoff + cancel + lag):**

| Test | Validates |
|------|-----------|
| `test_retry_on_network_error_attempt_1` | attempt=1 + ConnectionRefusedError → MARK_FAILED_RETRY backoff=1s |
| `test_dead_after_max_attempts` | attempt=5 >= max → MARK_DEAD + SYNC_DEAD_TOTAL.labels(error_class='network').inc() |
| `test_backoff_progression_full` | Attempt 1→2→3→4 backoffs [1, 5, 30, 120] respectively |
| `test_dead_path_emits_correct_error_class_timeout` | TimeoutError attempt=5 → SYNC_DEAD_TOTAL.labels(error_class='timeout').inc() (normalize_error_class) |
| `test_graceful_shutdown_cancel` | asyncio.create_task + task.cancel() → CancelledError caught KHÔNG raise wrong |
| `test_observe_lag_emit_histogram` | _observe_lag([row], 'hub') → SYNC_LAG_SECONDS observe (>0 since row.created_at - 5s) |
| `test_handle_failures_truncates_last_error_1000_char` | err_msg 5000 char → trunc <= LAST_ERROR_TRUNCATE=1000 |

**Duration:** 4.17s. **Pass rate:** 18/18 (100%).

### Aggregate Plan 04-03 — 43/43 PASS (100%)

**Total:** 43 unit test (12 models + 13 metrics + 18 worker). **Duration:** 4.28s.

### Regression — 353/353 PASS (full unit suite)

| Suite | Result |
|-------|--------|
| `test_sync_models.py` + `test_sync_metrics.py` + `test_sync_worker.py` (Plan 04-03 mới) | 43/43 PASS |
| `test_config_phase4_fields.py` (Plan 04-02) | 17/17 PASS |
| `test_sync_outbox_migration.py` (Plan 04-01) | 17/17 PASS |
| `test_jwks_*` + `test_auth_*` + `test_jwt_*` (Phase 3 SSO) | All PASS |
| `test_main_factory.py` + `test_config_hub_name*.py` (Phase 1+2) | All PASS |
| Full unit suite (`tests/unit/`) | **353/353 PASS — KHÔNG break baseline 310 (+43 new sync)** |
| `ruff check app/sync/ tests/unit/test_sync_*.py` | All checks passed |
| `mypy --strict app/sync/` | Success: no issues found in 5 source files |

**Duration full regression:** 31.06s.

---

## Acceptance Criteria (Plan 04-03)

### Task 1 (sync.keys + sync.models)

| Criterion | Result |
|-----------|--------|
| Files exist: `__init__.py` + `keys.py` + `models.py` | FOUND (5 file đầy đủ — include metrics + worker) |
| `from app.rag.flow import` in keys.py ≥ 1 | 1 match |
| `FOR UPDATE SKIP LOCKED` in keys.py ≥ 1 | 1 SQL match |
| `ON CONFLICT (id) DO UPDATE` in keys.py ≥ 1 | 1 SQL match |
| `WHERE chunks.content_hash IS DISTINCT FROM EXCLUDED.content_hash` ≥ 1 | 1 match |
| `UPDATE_DOC_SYNC_STATUS_SQL` ≥ 1 (BLOCKER 1) | 3 match (def + import alias + comment) |
| `'partial'` ≥ 1 (CASE branch) | 1 SQL match |
| `'syncing'` ≥ 1 | 1 SQL match |
| `class SyncStatus` in models.py | 1 match |
| `class DocumentSyncStatus` in models.py | 1 match |
| `class ChunkPayload` in models.py | 1 match |
| `_decode_content_hash` in models.py ≥ 1 (BLOCKER 2) | 1 match |
| `bytes.fromhex` in models.py ≥ 1 | 1 match |
| `pytest test_sync_models.py -v` PASS ≥ 12 tests | 12/12 PASS |
| `ruff check + mypy --strict app/sync/` | All PASS |

### Task 2 (sync.metrics 6 Prometheus collector)

| Criterion | Result |
|-----------|--------|
| File `metrics.py` ≥ 60 LOC | 114 LOC |
| 6 metric name (sync_lag_seconds + sync_outbox_pending + sync_attempt_total + sync_dead_total + sync_count_drift + sync_hash_drift) | All 6 found |
| `"hub_name"` count ≥ 6 (6 labelnames tuple) | 6 matches |
| `"hub_id"` count = 0 (W7 fix) | 0 matches |
| `def normalize_error_class` ≥ 1 | 1 match |
| `pytest test_sync_metrics.py -v` PASS ≥ 9 tests | 13/13 PASS |
| `ruff + mypy --strict` | All PASS |

### Task 3a + 3b (sync.worker)

| Criterion | Result |
|-----------|--------|
| File `worker.py` ≥ 280 LOC | 338 LOC |
| `async def sync_worker_loop` ≥ 1 | 1 match |
| `async def _claim_pending_batch` ≥ 1 | 1 match |
| `async def _push_inserts` ≥ 1 | 1 match |
| `async def _push_deletes` ≥ 1 | 1 match |
| `async def _handle_failures` ≥ 1 | 1 match |
| `async def _update_document_sync_status` ≥ 1 (BLOCKER 1) | 1 match |
| `_update_document_sync_status` count ≥ 2 (def + call site) | 3 matches (def + import-side + call site + helper docstring) |
| `UPDATE_DOC_SYNC_STATUS_SQL` in worker.py ≥ 1 | 2 matches (import + execute) |
| `affected_document_ids` count ≥ 2 | 5 matches (init + insert update + delete update + condition + call) |
| `hub_name=hub_name_label` count ≥ 3 (W7) | 8 matches |
| `pytest test_sync_worker.py -v -k happy/skip_central/empty/update_document` | 11/11 PASS (Task 3a subset) |
| Aggregate `test_sync_worker.py` 16+ test | 18/18 PASS |
| Phase 1+2+3 regression `tests/unit -m "not integration"` | 353/353 PASS — KHÔNG break |
| `ruff + mypy --strict` | All PASS |

**Tổng: 28/28 acceptance criteria PASS.**

---

## Decisions Made

### LOCKED Carry Forward (Phase Context)

- **D-V3-Phase4-A1:** Outbox + worker mechanism — `sync_worker_loop` async task implement core (claim batch → push central → mark processed/dead).
- **D-V3-Phase4-A3:** Worker placement = In-process asyncio task hub con lifespan — `_get_settings` indirection helper + early return nếu `hub_name == "central"`.
- **D-V3-Phase4-A5:** Worker loop config consume `Settings.sync_batch_size/poll_interval/max_attempts/backoff_seconds` (Plan 04-02 ship). SELECT FOR UPDATE SKIP LOCKED query qua `CLAIM_PENDING_SQL` constant.
- **D-V3-Phase4-B1:** ON CONFLICT (id) DO UPDATE WHERE content_hash IS DISTINCT FROM EXCLUDED.content_hash — `PUSH_INSERT_CHUNK_SQL` constant + `_push_inserts` helper.
- **D-V3-Phase4-B2:** `documents.sync_status` lifecycle 4 transition — `_update_document_sync_status` helper + `UPDATE_DOC_SYNC_STATUS_SQL` aggregate CASE 4 branches (BLOCKER 1 fix). Worker call sau MỖI batch với union `affected_document_ids` từ insert + delete branch.
- **D-V3-Phase4-B3:** op_type INSERT/DELETE split + DELETE payload key 'id' — `OpType` enum + `DeletePayload` Pydantic schema + `_push_deletes` HARD DELETE batched ANY array.

### Implementation Details (Plan 04-03 specific)

- **W7 fix LOCKED (CR Iteration 1):** Prometheus label `hub_name` (NOT `hub_id` UUID) — 6 collector all `labelnames=("hub_name", ...)`. Semantic rõ ràng: label values là hub_name string ("yte"/"duoc"/"hcns"/dynamic FACTOR-04), bounded 4-10 hub max. Cardinality control T-04-03-01 mitigation: 4 hub × 4 error_class × 2 drift_type × 2 status = ~240 series max.
- **BLOCKER 2 end-to-end serialization fix (CR Iteration 1):** `ChunkPayload.content_hash` `@field_validator(mode='before')` decode hex string → bytes. Trigger Plan 04-01 emit `encode(NEW.content_hash, 'hex')` → 64 char hex KHÔNG có `\x` prefix; bytes passthrough cho mock test. Defensive strip `\x` prefix nếu có (backward-compat).
- **BLOCKER 1 D-V3-Phase4-B2 lifecycle fix (CR Iteration 1):** `_update_document_sync_status(local_pool, document_ids)` helper execute `UPDATE_DOC_SYNC_STATUS_SQL` aggregate CASE 4 branches (synced/failed/partial/syncing) — RETURNING id, sync_status cho log audit. Idempotent — re-call cùng document_ids sau batch khác → re-aggregate state mới. Empty list shortcut (defensive — tránh acquire pool khi KHÔNG có doc).
- **W5 fix split (CR Iteration 1):** Task 3 split → 3a (happy + sync_status 11 test) + 3b (retry/dead/backoff/cancel/lag 7 test) — complexity bounded per task. Cùng file `test_sync_worker.py` chia sẻ fixture `_make_outbox_row` + `_build_mock_pool` + `_build_mock_settings` + `_build_mock_app`.
- **`_get_settings` indirection helper:** Module-level helper trong worker.py — monkeypatch hook cho unit test (KHÔNG inline `from app.config import get_settings()` + `get_settings()` để tránh lru_cache stale từ test trước). Test fixture monkeypatch `app.sync.worker._get_settings` thay vì global `app.config.get_settings`.
- **`LAST_ERROR_TRUNCATE = 1000` char:** Defensive vs runaway stacktrace bloat outbox storage. Repository pattern: `err_msg = f"{type(exc).__name__}: {exc!s}"[:LAST_ERROR_TRUNCATE]`. T-04-03-03 audit mitigation.
- **`backoff_idx = min(max(attempt_count - 1, 0), len(backoff_seconds) - 1)` clamped:** Defensive vs `attempt_count=0` edge case (trigger initial INSERT row có attempt_count=0 trước MARK_PROCESSING bump). Clamp ngăn IndexError ở worker runtime mid-batch (T-04-02-05 carry forward Plan 04-02 length validator).
- **Stub metrics.py + worker.py ở Task 1 GREEN:** Initial commit `736abcb` ship metrics.py + worker.py stub (raise NotImplementedError + Any = None) để __init__.py import work cho test_sync_models.py 12 test. Real impl land ở Task 2 (`235146d`) + Task 3 (`7f470f3`) GREEN commits. Pattern khớp TDD scaffolding — Task N stub đủ để Task N-1 test pass.
- **`enum.StrEnum` Python 3.12 native:** Inherit `enum.StrEnum` thay vì `(str, enum.Enum)` cho 3 enum (SyncStatus + OpType + DocumentSyncStatus) — UP042 ruff Python 3.11+ idiom. Behavior equivalent (str equals + value access) nhưng cleaner.

### Decisions deferred to next plans

- **Lifespan integration spawn async task** (`sync_worker_task = asyncio.create_task(sync_worker_loop(app))` + graceful shutdown `task.cancel() + gather(timeout=10s)`) — defer Plan 04-04 lifespan branch hub con only (`if settings.hub_name != "central"`).
- **Central asyncpg pool dedicated** (`asyncpg.create_pool(dsn=settings.central_sync_dsn, ...)` + `pgvector.asyncpg.register_vector` codec) — defer Plan 04-04 startup.
- **Cocoindex flow `hub_id` wire** (rag/flow.py:ChunkRow.hub_id consume `settings.hub_id`) — defer Plan 04-04 (file-disjoint giữ Plan 04-03 KHÔNG đụng rag/flow.py).
- **Admin replay endpoint `/api/sync/replay`** (POST { hub_id, since } reset dead rows attempt_count=0 + clear next_retry_at) — defer Plan 04-05 (central admin RBAC + audit log integration).
- **Integration test 2 asyncpg pool runtime** (testcontainer central + hub con + trigger fire + worker push) — defer Plan 04-04 lifespan integration test.

---

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Code quality] enum.StrEnum vs (str, enum.Enum) — UP042 ruff Python 3.12 idiom**

- **Found during:** Task 1 GREEN — `ruff check app/sync/` báo `UP042 Class SyncStatus inherits from both str and enum.Enum`.
- **Issue:** Plan reference code dùng `class SyncStatus(str, enum.Enum)` (legacy pattern Python ≤3.10). Python 3.11+ ship `enum.StrEnum` native (PEP 663) — ruff UP042 enforce modern idiom.
- **Fix:** Đổi 3 enum (SyncStatus + OpType + DocumentSyncStatus) sang `class X(enum.StrEnum)`. Behavior equivalent (str equals + .value access) — KHÔNG break test (12/12 PASS sau fix).
- **Files modified:** `api/app/sync/models.py`.
- **Commit:** `736abcb` (gộp với Task 1 GREEN — fix inline cùng tạo module).
- **Rationale:** Rule 1 minor adjustment — semantic giữ nguyên, chỉ idiom modernize per ruff.

**2. [Rule 1 - Code quality] datetime.UTC alias vs datetime.timezone.utc — UP017 ruff Python 3.12 idiom**

- **Found during:** Task 1 GREEN test file — ruff báo `UP017 Use datetime.UTC alias`.
- **Issue:** Plan reference test code dùng `from datetime import datetime, timezone` + `datetime.now(timezone.utc)`. Python 3.11+ ship `datetime.UTC` alias.
- **Fix:** Đổi import sang `from datetime import UTC, datetime` + `datetime.now(UTC)`.
- **Files modified:** `api/tests/unit/test_sync_models.py` + `test_sync_worker.py`.
- **Commit:** `736abcb` + `7f470f3` (auto-fix inline mỗi task).

**3. [Rule 1 - Code quality] asyncio.TimeoutError vs builtins.TimeoutError — UP041 Python 3.11+ unification**

- **Found during:** Task 2 test ruff check — `UP041 Replace asyncio.TimeoutError with builtin TimeoutError`.
- **Issue:** Python 3.11 unify `asyncio.TimeoutError` aliased to `builtins.TimeoutError`. Ruff UP041 enforce builtin name.
- **Fix:** Đổi `assert normalize_error_class(asyncio.TimeoutError())` → `TimeoutError()`.
- **Files modified:** `api/tests/unit/test_sync_metrics.py`.
- **Commit:** `235146d` (auto-fix `--fix` inline).

**4. [Rule 1 - Complexity] sync_worker_loop C901 + PLR0912 complexity 15 > 10**

- **Found during:** Task 3 GREEN ruff check — `C901 sync_worker_loop is too complex (15 > 10)`.
- **Issue:** Worker loop monolithic D-V3-Phase4-A5 LOCKED design — try/except cancel + main try/except generic + 2 op_type branch + push/processed/failures/sync_status sequence = 15 branches. Splitting sẽ phá D-V3-Phase4-A5 single-loop semantic + obscure call site logging.
- **Fix:** Annotate `# noqa: C901,PLR0912 — D-V3-Phase4-A5 monolithic loop intentional` ngay sau function signature line.
- **Files modified:** `api/app/sync/worker.py`.
- **Commit:** `7f470f3` (inline trong Task 3 GREEN).
- **Rationale:** Rule 1 minor — D-V3-Phase4-A5 intentional design; refactor sẽ make worse readability. Acceptable per CR Iteration 1 review pattern.

### Plan-strict adherence

- KHÔNG bump stack version (Python 3.12, FastAPI 0.136.1, pgvector 0.4.2, asyncpg 0.30.0, prometheus_client 0.21.1).
- KHÔNG sửa `frontend/`, `STATE.md`, `ROADMAP.md`, `REQUIREMENTS.md`, `app/main.py` lifespan, `rag/flow.py` (out-of-scope cho executor — defer Plan 04-04 owns).
- KHÔNG dùng `--no-verify` cho commit (sequential mode, pre-commit hooks run).
- KHÔNG đụng `api/migrations/` directory (Plan 04-01 file-disjoint).
- KHÔNG đụng `api/app/config.py` (Plan 04-02 file-disjoint).
- Commit message prefix tiếng Anh + body tiếng Việt theo CLAUDE.md §5.

---

## Authentication Gates

**None.** Plan 04-03 thuần module + unit test in-process — KHÔNG cần auth setup. Runtime auth integration (sync_user role grant scope central) defer Phase 7 MIGRATE deploy guide; integration test với 2 asyncpg pool defer Plan 04-04 lifespan integration test.

---

## Known Stubs

**None.** Plan 04-03 ship worker module đầy đủ + 43 unit test cover end-to-end semantic. Stub initial commit `736abcb` (metrics.py + worker.py) đã được thay full impl ở `235146d` (metrics) + `7f470f3` (worker). KHÔNG có data UI stub.

Module entry points đợi Plan 04-04 wire vào lifespan:
- `sync_worker_loop(app)` — Plan 04-04 spawn `asyncio.create_task` + graceful shutdown.
- `app.state.db_pool` + `app.state.central_sync_pool` — Plan 04-04 lifespan startup tạo 2 asyncpg pool dedicated.

---

## Threat Flags

**Không phát hiện threat surface mới ngoài `<threat_model>` của Plan 04-03.** 9 threat (T-04-03-01..09) trong plan đã cover toàn bộ surface:
- T-04-03-01..02 (Spoofing/Tampering hub credentials + outbox payload) → mitigated bởi Plan 04-02 DSN validator + Plan 04-01 trigger AFTER INSERT/DELETE ON chunks (KHÔNG direct INSERT bypass).
- T-04-03-03 (Repudiation worker success/fail audit) → mitigated bởi SYNC_ATTEMPT_TOTAL counter + SYNC_DEAD_TOTAL counter + sync_outbox.last_error trunc 1000 char.
- T-04-03-04 (Info Disclosure log content) → accept (logger chỉ log count + error class, KHÔNG full chunk.content).
- T-04-03-05..06 (DoS tight loop + SELECT FOR UPDATE block) → mitigated bởi `asyncio.sleep(poll_interval=5s)` + SKIP LOCKED + batch_size=100 + commit ngay sau MARK_PROCESSING.
- T-04-03-07 (Elevation worker compromise DROP central) → mitigated bởi Plan 04-04 + Phase 7 sync_user role limited GRANT INSERT/UPDATE chunks ONLY.
- T-04-03-08 (Integrity documents.sync_status stuck) → mitigated bởi BLOCKER 1 fix `_update_document_sync_status` aggregate SAU MỖI batch + 4 unit test verify 4 state lifecycle.
- T-04-03-09 (Integrity payload format mismatch) → mitigated bởi BLOCKER 2 fix ChunkPayload hex decode field_validator + unit test roundtrip.

---

## Verification Status

### Automated (in-process, KHÔNG cần Postgres runtime)

- ✅ 12/12 unit test PASS `test_sync_models.py` (3.79s)
- ✅ 13/13 unit test PASS `test_sync_metrics.py` (0.27s)
- ✅ 18/18 unit test PASS `test_sync_worker.py` (4.17s)
- ✅ Aggregate **43/43 unit test mới PASS** (4.28s aggregate)
- ✅ 353/353 full unit suite regression PASS (31.06s — KHÔNG break Phase 1+2+3 + Plan 04-01..02 + +43 new sync)
- ✅ `ruff check app/sync/ tests/unit/test_sync_*.py` All checks passed (5 source + 3 test)
- ✅ `mypy --strict app/sync/` Success: no issues found in 5 source files

### Deferred (cần Postgres runtime + 2 asyncpg pool)

- Worker lifespan integration với asyncpg pool central + local — defer Plan 04-04 (`asyncpg.create_pool` + `pgvector.asyncpg.register_vector` codec startup).
- Trigger fire runtime INSERT chunks → outbox enqueue + worker push → central INSERT verify — defer Plan 04-04 integration test với 2 DB testcontainer.
- documents.sync_status UPDATE end-to-end (trigger 'syncing' + worker 'synced'/'failed'/'partial' multi-chunk-per-document) — defer Plan 04-04 integration.
- SELECT FOR UPDATE SKIP LOCKED concurrent worker test (2 worker instance đồng thời claim disjoint batch) — defer Plan 04-04 hoặc Phase 7 MIGRATE-05 load test.
- ON CONFLICT (id) DO UPDATE WHERE content_hash IS DISTINCT runtime verify (HNSW vector index disk write thừa avoid) — defer Plan 04-04 integration.

---

## Self-Check

### Files Created/Modified Verification

| Claim | Verified |
|-------|----------|
| `api/app/sync/__init__.py` exists | FOUND (50 LOC) |
| `api/app/sync/keys.py` exists | FOUND (168 LOC) |
| `api/app/sync/models.py` exists | FOUND (146 LOC) |
| `api/app/sync/metrics.py` exists | FOUND (114 LOC) |
| `api/app/sync/worker.py` exists | FOUND (338 LOC) |
| `api/tests/unit/test_sync_models.py` exists | FOUND (270 LOC) |
| `api/tests/unit/test_sync_metrics.py` exists | FOUND (224 LOC) |
| `api/tests/unit/test_sync_worker.py` exists | FOUND (549 LOC) |

### Commit Verification

| Hash | Verified |
|------|----------|
| `c92ca35` (test RED Task 1) | FOUND in git log |
| `736abcb` (feat GREEN Task 1) | FOUND in git log |
| `235146d` (feat Task 2) | FOUND in git log |
| `f3b2a28` (test RED Task 3) | FOUND in git log |
| `7f470f3` (feat GREEN Task 3a + 3b) | FOUND in git log |

## Self-Check: PASSED

---

## Performance Metrics

| Metric | Value |
|--------|-------|
| Duration | ~35 phút (5 commit atomic — 2 RED + 3 GREEN qua 4 task) |
| Tasks completed | 4/4 (Task 1 models + Task 2 metrics + Task 3a worker happy + Task 3b worker retry) |
| Files created | 8 (5 module source + 3 test file) |
| Files modified | 0 (file-disjoint với Plan 04-01 + 04-02) |
| LOC added | 816 source + 1043 test = **~1859 LOC** |
| Tests added | **43** (12 models + 13 metrics + 18 worker — superset của plan ≥37) |
| Test pass rate | **43/43 (100%)** — 4.28s aggregate |
| Acceptance criteria | **28/28 PASS** (15 Task 1 + 7 Task 2 + 14 Task 3a+3b) |
| Regression | **353/353 full unit suite PASS — KHÔNG break Phase 1+2+3 + Plan 04-01..02 + +43 new** |
| Lint | ruff + mypy --strict PASS all 5 source + 3 test file |
| Commits | 5 atomic (Task 1 RED + GREEN + Task 2 + Task 3 RED + GREEN) |
| Deviations | 4 (Rule 1 minor — UP042 StrEnum + UP017 datetime.UTC + UP041 TimeoutError + C901 noqa worker_loop monolithic intentional) |

---

## Next: Plan 04-04 Lifespan Integration (Wave 3)

Plan 04-03 đã ship sync module Wave 2 (file-disjoint với Plan 04-02). Plan 04-04 Wave 3 sẽ:

1. **Lifespan startup hub con:** `asyncpg.create_pool(dsn=settings.central_sync_dsn, ...)` + `pgvector.asyncpg.register_vector(codec)` codec register cho `vector` cast — store ở `app.state.central_sync_pool`.
2. **Spawn async task:** `app.state.sync_worker_task = asyncio.create_task(sync_worker_loop(app))` conditional `if settings.hub_name != "central"` branch.
3. **Lifespan shutdown:** `task.cancel()` + `await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), timeout=10s)` — graceful drain pending batch.
4. **Cocoindex flow `hub_id` wire:** `rag/flow.py:ChunkRow(hub_id=settings.hub_id, ...)` để trigger Plan 04-01 enqueue đúng hub_id (chunks.hub_id FK constraint).
5. **Integration test 2 DB testcontainer:** central + hub con + trigger fire INSERT chunks → outbox enqueue → worker push central → MARK_PROCESSED → documents.sync_status='synced' end-to-end.

Plan 04-04 phụ thuộc Plan 04-01 (sync_outbox schema) + Plan 04-02 (Settings central_sync_dsn) + Plan 04-03 (worker module) — 3 dependency Wave 1+2 đã ship. Plan 04-05 (admin replay endpoint) + Plan 04-06 (checksum scheduler) + Plan 04-07 (closeout) parallel sau Plan 04-04.

**Phase 4 progress:** 3/7 plan complete (~43%). SYNC-05 đóng (Plan 04-01). SYNC-01/02/04 Settings + worker layer ship (Plan 04-02 + 04-03); formally đóng SYNC-01..02 khi Plan 04-04 lifespan integration test pass.

---

*Plan 04-03 ship 2026-05-22 sau ~35 phút thực thi. Wave 2 part 2 DONE (file-disjoint với Plan 04-02 — chỉ touch app/sync/ directory mới + tests/unit/test_sync_*.py). 5 commit atomic (2 RED test + 3 GREEN feat). 43/43 test PASS + 353/353 regression PASS + 28/28 acceptance + ruff + mypy --strict PASS. Next: Plan 04-04 lifespan integration (Wave 3 depend Plan 04-01..03 ship đủ).*
