---
phase: 04-cross-hub-data-sync
plan: 01
subsystem: sync
tags:
  - sync
  - alembic
  - outbox
  - postgres-trigger
  - per-hub-migration
requirements:
  - SYNC-05
  - SYNC-01
  - SYNC-02
dependency_graph:
  requires:
    - Phase 1 TOPO-02 — per-hub Alembic env -x hub=<name> (parse_hub_x_arg + resolve_env_database_url)
    - Phase 1 chunks table schema (vector Vector(1536) + content_hash BYTEA + hub_id UUID FK)
    - Phase 1 documents table schema (status enum + hub_id FK CASCADE)
    - Migration 0004 mcp_oauth_clients (down_revision chain)
  provides:
    - sync_outbox table per-hub DB (11 cols + 2 CHECK + 2 partial indexes)
    - Postgres function enqueue_sync_outbox() — explicit jsonb_build_object + vector::float4[] cast + content_hash hex encode
    - 2 trigger AFTER INSERT/DELETE chunks (FOR EACH ROW)
    - documents.sync_status enum column (5 value lifecycle: pending/syncing/synced/failed/partial)
    - is_sync_outbox_rev_applicable() pure helper (env.py) — D-V3-Phase4-A2 skip-central registry
  affects:
    - Plan 04-03 worker (consume sync_outbox via SELECT FOR UPDATE SKIP LOCKED + ChunkPayload Pydantic parse hex+vector)
    - Plan 04-04 lifespan integration (verify trigger fire trên chunks INSERT runtime)
    - Plan 04-06 checksum scheduler (verify count drift + hash sample sync_outbox.processed_at)
tech-stack:
  added: []
  patterns:
    - Per-hub Alembic migration với runtime skip guard (current_database() check)
    - Postgres trigger AFTER INSERT/DELETE FOR EACH ROW (atomic cùng transaction chunks INSERT)
    - Outbox pattern (D-V3-Phase4-A1 LOCKED) — INSERT outbox cùng transaction, worker pull batch + retry
    - Explicit jsonb_build_object (pgvector serialization fix — KHÔNG to_jsonb(full NEW row))
    - Idempotent guard `WHERE sync_status='pending'` cho first-chunk-per-document UPDATE
key-files:
  created:
    - api/migrations/versions/0005_sync_outbox_per_hub.py (224 LOC)
    - api/tests/unit/test_sync_outbox_migration.py (223 LOC)
  modified:
    - api/migrations/env.py (+33 lines — _HUB_ONLY_REVS frozenset + is_sync_outbox_rev_applicable helper)
decisions:
  - "D-V3-Phase4-A2: sync_outbox table per-hub-only (skip central) — runtime guard current_database()"
  - "D-V3-Phase4-A4: Postgres trigger AFTER INSERT/DELETE chunks FOR EACH ROW enqueue (atomic transaction)"
  - "D-V3-Phase4-B2: documents.sync_status enum lifecycle 5 value (pending → syncing trigger → synced/failed/partial worker)"
  - "BLOCKER 1 fix: INSERT trigger cùng transaction UPDATE documents.sync_status='syncing' với idempotent guard WHERE sync_status='pending'"
  - "BLOCKER 2 fix: Explicit jsonb_build_object (KHÔNG to_jsonb(NEW)) + vector::float4[] cast + content_hash hex encode"
  - "DELETE branch payload key 'id' (NOT 'chunk_id') để unify ChunkPayload Plan 04-03 schema"
metrics:
  duration_minutes: 8
  completed_date: 2026-05-22
  task_count: 2
  commit_count: 3
  file_count: 3
  test_count: 17
  test_pass_rate: "17/17 (100%)"
  regression_pass_rate: "293/293 unit + 10/10 Phase 1 PASS"
---

# Phase 4 Plan 01: Per-hub Alembic 0005 Sync Outbox Summary

**One-liner:** Migration 0005 per-hub-only tạo `sync_outbox` table + Postgres trigger AFTER INSERT/DELETE chunks (explicit `jsonb_build_object` + `vector::float4[]` cast + `content_hash` hex encode) + `documents.sync_status` enum lifecycle với initial 'syncing' UPDATE idempotent — outbox pattern D-V3-Phase4-A1/A2/A4/B2 đóng R-V3-1 HIGH sync drift mitigation Wave 1 BLOCKING cho Plan 04-03 worker + Plan 04-04 lifespan integration.

---

## Files Created/Modified

### Created

| Path | LOC | Purpose |
|------|-----|---------|
| `api/migrations/versions/0005_sync_outbox_per_hub.py` | 224 | Per-hub Alembic migration — runtime skip guard central + sync_outbox 11 cols + 2 partial index + documents.sync_status enum + Postgres function + 2 trigger AFTER INSERT/DELETE + downgrade idempotent |
| `api/tests/unit/test_sync_outbox_migration.py` | 223 | 17 unit test: 4 TestSkipGuard + 12 TestMigrationStructure + 1 meta. Verify structure + jsonb_build_object/vector cast/content_hash hex (BLOCKER 2) + initial syncing UPDATE idempotent (BLOCKER 1) + DELETE payload key 'id' + downgrade idempotent |

### Modified

| Path | Change | Purpose |
|------|--------|---------|
| `api/migrations/env.py` | +33 lines | `_HUB_ONLY_REVS: frozenset[str] = frozenset({"0005"})` + `is_sync_outbox_rev_applicable(rev_id, hub_name) -> bool` pure helper. Pure-function unit testable; runtime enforcement nằm trong migration upgrade() qua current_database() check. |

---

## Commits

| Commit | Type | Description |
|--------|------|-------------|
| `761c72b` | test | Task 1 RED — failing test sync_outbox migration 0005 structure + skip-central helper (17 test, collection FAIL FileNotFoundError) |
| `98ed642` | feat | Task 1 GREEN — migration 0005 sync_outbox per-hub + trigger jsonb_build_object + documents.sync_status lifecycle (13/17 PASS, 4 skip-guard FAIL pending Task 2) |
| `9d04509` | feat | Task 2 GREEN — is_sync_outbox_rev_applicable helper env.py + _HUB_ONLY_REVS frozenset (17/17 PASS) |

**Total:** 3 commits. Task 1 split RED+GREEN (TDD); Task 2 single GREEN commit (RED visible inline trong Task 1 RED commit since same test file).

---

## Test Results

### test_sync_outbox_migration.py — 17/17 PASS (100%)

**TestSkipGuard (4):**
- `test_skip_central` — `is_sync_outbox_rev_applicable("0005", "central") → False` ✅
- `test_applies_to_yte` — `is_sync_outbox_rev_applicable("0005", "yte") → True` ✅
- `test_applies_to_dynamic_hub` — `is_sync_outbox_rev_applicable("0005", "phap_che") → True` (FACTOR-04 dynamic hub) ✅
- `test_other_revs_pass_for_central` — `is_sync_outbox_rev_applicable("0001", "central") → True` (other rev pass mọi hub) ✅

**TestMigrationStructure (12):**
- `test_revision_chain` — revision="0005" + down_revision="0004" ✅
- `test_upgrade_contains_all_columns` — 11 cột sync_outbox declared (id/op_type/chunk_id/document_id/payload/attempt_count/last_error/status/next_retry_at/created_at/processed_at) ✅
- `test_upgrade_uses_jsonb_build_object_not_to_jsonb_new` — regex `\bto_jsonb\(NEW\)` match 0 + `jsonb_build_object` count ≥ 2 ✅ (BLOCKER 2)
- `test_upgrade_vector_cast_present` — `NEW.vector::float4[]` ≥ 1 ✅ (BLOCKER 2)
- `test_upgrade_content_hash_hex_encode` — `encode(NEW.content_hash, 'hex')` ≥ 1 ✅ (BLOCKER 2)
- `test_upgrade_initial_syncing_update_present` — `UPDATE documents` + `sync_status = 'syncing'` + `AND sync_status = 'pending'` (idempotent guard) ✅ (BLOCKER 1)
- `test_delete_payload_key_id_not_chunk_id` — `jsonb_build_object('id', OLD.id)` ✅
- `test_sync_status_enum_column` — `sync_status TEXT NOT NULL DEFAULT 'pending'` + CHECK 5 value ✅
- `test_trigger_function_name` — `CREATE OR REPLACE FUNCTION enqueue_sync_outbox` + 2 trigger name match ✅
- `test_indexes_present` — `ix_sync_outbox_pending` + `ix_sync_outbox_chunk_id` ✅
- `test_central_skip_guard` — `current_db == "medinet_central"` + "SKIP central" log message ✅
- `test_downgrade_idempotent` — `IF EXISTS` count ≥ 6 (thực tế 7) ✅

**Meta (1):**
- `test_total_test_count_meets_acceptance` — total ≥ 13 (thực tế 17) ✅

**Duration:** 0.49s. **Pass rate:** 17/17 (100%).

### Regression

| Suite | Result |
|-------|--------|
| `test_alembic_env_hub_arg.py` (Phase 1 TOPO-02) | 10/10 PASS — KHÔNG break |
| Full unit suite (`tests/unit/`) | 293/293 PASS — KHÔNG break |
| `ruff check` migration + env.py + test | All checks passed |
| `mypy --strict migrations/env.py` | Success: no new issues found |

**Pre-existing mypy errors (out-of-scope, defer):**
- `app/services/hub_service.py:174,177` — HubService.list valid-type error (M2 legacy)
- `app/routers/mcp_oauth.py:44` — Missing type arguments for dict (M2 legacy)

Logged to `deferred-items.md` philosophy: KHÔNG fix trong scope Plan 04-01 (out-of-scope rule).

---

## Acceptance Criteria (Plan 04-01)

| Criterion | Result |
|-----------|--------|
| `revision: str = "0005"` | 1 match ✅ |
| `down_revision: Union[str, None] = "0004"` | 1 match ✅ |
| `CREATE TABLE IF NOT EXISTS sync_outbox` | 1 match ✅ |
| `CREATE TRIGGER chunks_after_insert_enqueue_sync_outbox` | 1 match ✅ |
| `CREATE TRIGGER chunks_after_delete_enqueue_sync_outbox` | 1 match ✅ |
| `CREATE OR REPLACE FUNCTION enqueue_sync_outbox` | 1 match ✅ |
| `sync_status TEXT NOT NULL DEFAULT 'pending'` | 1 match ✅ |
| `CHECK (sync_status IN ('pending','syncing','synced','failed','partial'))` | 1 match ✅ |
| `jsonb_build_object` ≥ 2 | 8 matches ✅ (INSERT + DELETE branch + comments + tests) |
| `NEW.vector::float4[]` ≥ 1 | 1 match ✅ (BLOCKER 2 fix) |
| `encode(NEW.content_hash, 'hex')` ≥ 1 | 1 match ✅ (BLOCKER 2 fix) |
| `UPDATE documents` ≥ 1 | 4 matches ✅ (BLOCKER 1 fix — D-V3-Phase4-B2) |
| `sync_status = 'syncing'` ≥ 1 | matched ✅ |
| `AND sync_status = 'pending'` ≥ 1 (idempotent guard) | matched ✅ |
| `current_db == "medinet_central"` | 1 match ✅ |
| `_HUB_ONLY_REVS` in env.py | 5 matches ✅ |
| `def is_sync_outbox_rev_applicable` in env.py | 1 match ✅ |
| `ruff check` migration + env.py + test | PASS ✅ |
| `pytest test_sync_outbox_migration.py -v` exit 0, ≥ 13 tests PASS | 17/17 PASS exit 0 ✅ |
| Phase 1 regression `test_alembic_env_hub_arg.py` | 10/10 PASS — KHÔNG break ✅ |

**All 20/20 acceptance criteria met.**

---

## Decisions Made

### LOCKED Carry Forward (Phase Context)
- **D-V3-Phase4-A1:** Outbox + worker mechanism (REJECT cocoindex target / logical replication) — R-V3-1 sync drift HIGH mitigation rõ nhất.
- **D-V3-Phase4-A2:** sync_outbox table per-DB hub con (KHÔNG ở central). Schema 11 cols + 2 partial indexes locked.
- **D-V3-Phase4-A4:** Postgres trigger AFTER INSERT/DELETE chunks enqueue (atomic cùng transaction chunks INSERT).
- **D-V3-Phase4-B2:** documents.sync_status enum 5 value (pending/syncing/synced/failed/partial). Trigger INSERT bump 'syncing' (idempotent first chunk); Plan 04-03 worker bump 'synced'/'failed'/'partial'.

### Implementation Details (Plan 04-01 specific)
- **BLOCKER 1 fix (D-V3-Phase4-B2 initial lifecycle):** Trigger INSERT branch cùng transaction chunks INSERT phải UPDATE `documents.sync_status='syncing' WHERE id=NEW.document_id AND sync_status='pending'`. Idempotent guard chỉ first chunk per document update — subsequent chunks no-op (KHÔNG override 'failed'/'partial' do worker đã bump).
- **BLOCKER 2 fix (pgvector serialization):** Explicit `jsonb_build_object(...)` thay vì `to_jsonb(NEW)`. Cast `NEW.vector::float4[]` để pgvector serialize float array sang JSONB clean (KHÔNG opaque vector text). Encode `content_hash` bytea qua `encode(.., 'hex')` cho hex string clean (Pydantic ChunkPayload Plan 04-03 parse qua `bytes.fromhex(v)` — KHÔNG có `\x` prefix).
- **DELETE branch unified key 'id':** `jsonb_build_object('id', OLD.id)` thay vì `'chunk_id'` để Plan 04-03 worker `ChunkPayload` Pydantic schema unified single key `id` cho cả INSERT + DELETE branch (giảm boilerplate parsing).
- **Runtime skip guard central:** `current_db = bind.execute("SELECT current_database()").scalar()` + early return nếu `== "medinet_central"`. Log thân thiện cho operator debug. alembic_version row vẫn ghi rev 0005 để CI head SHA uniform check R-V3-3 KHÔNG break giữa 4 DB.
- **Helper `is_sync_outbox_rev_applicable` pure-function:** Phục vụ unit test + tài liệu hóa intent. **KHÔNG** được alembic runtime dùng trực tiếp (dual-source-of-truth pitfall) — runtime check nằm trong migration module để chống bug "operator quên `-x hub=<name>`".

---

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Test regex `\bto_jsonb\(NEW\)` ban đầu false-positive trên doc reference**
- **Found during:** Task 1 GREEN — test_upgrade_uses_jsonb_build_object_not_to_jsonb_new FAIL khi migration docstring + comment thân thiện đề cập "KHÔNG to_jsonb(NEW)" làm regex match doc text.
- **Issue:** `inspect.getsource(mig.upgrade)` trả về toàn bộ function source bao gồm comments inline; regex catch literal `to_jsonb(NEW)` substring mọi nơi.
- **Fix:** Rephrase comment/docstring cụm "to_jsonb(NEW)" thành "`to_jsonb` của NEW row" / "`to_jsonb` của full NEW row" — semantic giữ nguyên ý "không dùng" nhưng KHÔNG match regex test. Test vẫn catch dùng SQL thực tế (literal `to_jsonb(NEW)` chỉ xuất hiện trong code SQL).
- **Files modified:** `api/migrations/versions/0005_sync_outbox_per_hub.py` (4 vị trí comment/docstring).
- **Commit:** `98ed642` (gộp với Task 1 GREEN — fix inline trong commit cùng tạo migration).
- **Rationale:** Đây là quyết định wording — Rule 1 minor adjustment. KHÔNG đổi code SQL semantic, chỉ đổi text comment cho regex test work đúng intent.

**2. [Rule 1 - Bug] Test file unused `pytest` import**
- **Found during:** Task 1 GREEN — `ruff check` báo `F401 unused import: pytest`.
- **Issue:** Test file initial draft import `pytest` cho `pytest.raises` nhưng tất cả test dùng `assert` thay vì `pytest.raises` → import unused.
- **Fix:** Xóa `import pytest` line.
- **Files modified:** `api/tests/unit/test_sync_outbox_migration.py`.
- **Commit:** `98ed642` (gộp với Task 1 GREEN).

### Plan-strict adherence
- KHÔNG bump stack version (Python 3.12, FastAPI 0.136.1, cocoindex 1.0.3, pgvector 0.4.2, asyncpg 0.30.0, Alembic 1.18.4).
- KHÔNG sửa `frontend/`, `api/app/rag/flow.py`, `STATE.md`, `ROADMAP.md`, `REQUIREMENTS.md` (out-of-scope cho executor).
- KHÔNG dùng `--no-verify` cho commit (sequential mode, pre-commit hooks run).
- Commit message prefix tiếng Anh (`test:`/`feat:`) + body tiếng Việt theo CLAUDE.md §5.

---

## Authentication Gates

**None.** Plan 04-01 thuần code/migration — KHÔNG cần auth setup. Migration apply runtime defer Plan 04-04 lifespan integration test với 2 DB testcontainer (cần Postgres + asyncpg pool dedicated).

---

## Known Stubs

**None.** Plan 04-01 không tạo UI/data flow stub. Migration 0005 là schema-only foundation cho Plan 04-03 worker (consume) + Plan 04-04 wire (integration).

---

## Threat Flags

**Không phát hiện threat surface mới ngoài `<threat_model>` của Plan 04-01.** 7 threat (T-04-01-01..07) trong plan đã cover toàn bộ surface migration touch (Alembic CLI → DB + Postgres trigger → chunks + documents). Plan 04-02 (Settings central_sync_dsn) sẽ cover credential layer threats.

---

## Verification Status

### Automated (in-process, KHÔNG cần Postgres runtime)
- ✅ 17/17 unit test PASS (4 skip-guard + 12 structure + 1 meta)
- ✅ ruff check PASS toàn bộ file changed (3 file)
- ✅ mypy --strict env.py PASS no new errors
- ✅ Phase 1 regression 10/10 PASS (test_alembic_env_hub_arg.py)
- ✅ Full unit suite regression 293/293 PASS (KHÔNG break Phase 1+2+3)
- ✅ `inspect.getsource(mig.upgrade)` source contain check toàn bộ 12 acceptance pattern

### Deferred (cần Postgres runtime)
- Migration apply runtime trên `medinet_hub_yte` qua `alembic -x hub=yte upgrade head` — defer Plan 04-04 lifespan integration test (2 DB testcontainer central + hub con).
- Trigger fire runtime trên `INSERT INTO chunks` — defer Plan 04-04 integration test.
- documents.sync_status UPDATE idempotent runtime verify multi-chunk-per-document — defer Plan 04-04.
- alembic head SHA uniform check 4 DB sau apply — defer Plan 04-07 closeout.

---

## Self-Check

### Files Created/Modified Verification

| Claim | Verified |
|-------|----------|
| `api/migrations/versions/0005_sync_outbox_per_hub.py` exists | ✅ FOUND (224 LOC) |
| `api/tests/unit/test_sync_outbox_migration.py` exists | ✅ FOUND (223 LOC) |
| `api/migrations/env.py` modified với is_sync_outbox_rev_applicable | ✅ FOUND (5 matches `_HUB_ONLY_REVS`) |

### Commit Verification

| Hash | Verified |
|------|----------|
| `761c72b` (test RED) | ✅ FOUND in git log |
| `98ed642` (feat GREEN Task 1) | ✅ FOUND in git log |
| `9d04509` (feat GREEN Task 2) | ✅ FOUND in git log |

## Self-Check: PASSED

---

## Performance Metrics

| Metric | Value |
|--------|-------|
| Duration | ~8 phút (3 commit atomic — 1 RED + 2 GREEN) |
| Tasks completed | 2/2 |
| Files created | 2 (migration 0005 + test file) |
| Files modified | 1 (env.py helper) |
| LOC added | 224 (migration) + 223 (test) + 33 (env.py helper) = 480 LOC |
| Tests added | 17 (4 skip-guard + 12 structure + 1 meta) |
| Test pass rate | 17/17 (100%) — 0.49s |
| Acceptance criteria | 20/20 PASS |
| Regression | 10/10 Phase 1 + 293/293 full unit suite — KHÔNG break |
| Lint | ruff + mypy --strict PASS no new errors |
| Commits | 3 (atomic: RED + GREEN Task 1 + GREEN Task 2) |
| Deviations | 2 (Rule 1 minor — regex doc-text false-positive + ruff unused import) |

---

## Next: Plan 04-02 + 04-03 Parallel Wave 2

Plan 04-01 đã đóng Wave 1 BLOCKING. Wave 2 mở:

1. **Plan 04-02 (Settings + central_sync_dsn)** — Settings field `central_sync_dsn` + `_enforce_central_sync_dsn_for_hub` model_validator hub con required; asyncpg pool dedicated lifespan; T-04-06 credential layer threat mitigation.
2. **Plan 04-03 (Sync worker)** — `api/app/sync/worker.py` mới: SELECT FOR UPDATE SKIP LOCKED batch 100 + ChunkPayload Pydantic parse (hex+vector) + `INSERT INTO chunks ... ON CONFLICT (chunk_id) DO UPDATE WHERE content_hash IS DISTINCT FROM EXCLUDED` (D-V3-Phase4-B1) + exp backoff [1,5,30,120]s max 5 attempts + mark dead status + Prometheus metrics 4 (sync_lag_seconds + sync_outbox_pending + sync_attempt_total + sync_dead_total).

Plan 04-02 + 04-03 có thể parallel (independent file/dir). Plan 04-04 (lifespan integration) phụ thuộc cả 2 → Wave 3.

**Phase 4 progress:** 1/7 plan complete (~14%). SYNC-05 đóng. SYNC-01/02 cấu trúc nền sẵn — đóng formally khi worker Plan 04-03 ship.

---

*Plan 04-01 ship 2026-05-22 sau ~8 phút thực thi. Wave 1 BLOCKING DONE. 3 commit atomic (1 RED test + 2 GREEN feat). 17/17 test PASS + 20/20 acceptance + 0 regression. Next: Plan 04-02 + 04-03 parallel Wave 2.*
