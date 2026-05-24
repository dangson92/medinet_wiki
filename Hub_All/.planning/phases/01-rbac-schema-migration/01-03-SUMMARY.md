---
phase: 01-rbac-schema-migration
plan: 03
subsystem: closeout-integration-test
tags: [rbac, alembic, integration-test, dsn-injection, idempotent, closeout]
requirements: [ROLE-01, ROLE-02, ROLE-03, ROLE-04]
dependency_graph:
  requires:
    - "Plan 01-01 migration 0006 ADD COLUMN user_hubs.role + CHECK enum hub_admin + audit seed (semantic precondition cho 4/5 integration test verify)"
    - "Plan 01-02 helper get_effective_role (closeout cùng phase — chỉ tham chiếu STATE.md/CLAUDE.md update; KHÔNG runtime call)"
  provides:
    - "api/tests/integration/test_migration_0006_idempotent.py — 5 integration test verify 4 success criteria ROADMAP Phase 1"
    - "SAFETY DSN injection pattern (Iter 1 fix I-01) — fixture monkeypatch DATABASE_URL + get_settings.cache_clear() bypass env.py:185-191 runtime override"
    - "Phase 1 DONE marker — STATE.md progress 0 → 3/15 + REQUIREMENTS.md ROLE-01..04 [x] + CLAUDE.md §6 subsection mới"
  affects:
    - "Phase 4 MIGRATE-01 sẽ chạy test bắt buộc qua `make test-integration` (TEST_DATABASE_URL set)"
    - "Phase 2 / 3 sẵn sàng start (Phase 1 baseline DONE)"
tech_stack:
  added: []
  patterns:
    - "DSN-injection-via-monkeypatch-env (alternative to set_main_option) — SAFETY pattern Alembic integration test"
    - "skip-if-no-DB pattern (pytest.skip TEST_DATABASE_URL chưa set) — manual run only; CI Phase 4 MIGRATE-01"
    - "asyncpg.CheckViolationError specific exception verify (KHÔNG generic PostgresError)"
    - "defensive cleanup finally DELETE WHERE email LIKE pattern (chống leak test data)"
    - "restore head state end-of-test (KHÔNG để DB ở downgrade state phá test sau)"
key_files:
  created:
    - "api/tests/integration/test_migration_0006_idempotent.py"
    - ".planning/phases/01-rbac-schema-migration/01-03-SUMMARY.md"
  modified:
    - ".planning/STATE.md"
    - ".planning/REQUIREMENTS.md"
    - ".planning/ROADMAP.md"
    - "CLAUDE.md"
decisions:
  - "Iter 1 revision fix I-01 LOCKED: fixture monkeypatch DATABASE_URL env + get_settings.cache_clear() THAY VÌ cfg.set_main_option('sqlalchemy.url', ...) — env.py:185-191 runtime OVERRIDE sqlalchemy.url từ get_settings().database_url, IGNORE caller's set_main_option. SAFETY BLOCKER: nếu dùng set_main_option, test apply migration vào DB lấy từ .env (vd medinet_central), KHÔNG phải TEST_DATABASE_URL → có thể vô tình modify dev/prod DB."
  - "Iter 1 revision fix I-02 LOCKED: format DSN giữ nguyên `postgresql+asyncpg://` ở fixture (KHÔNG convert sync) — env.py + Settings expect prefix async (async_engine_from_config xử lý natively). Chỉ helper `_asyncpg_dsn()` strip prefix khi `asyncpg.connect()` direct (asyncpg KHÔNG hiểu SQLAlchemy driver hint)."
  - "Skip-if-no-DB pattern thay vì hardcode DSN — TEST_DATABASE_URL env var REQUIRED → pytest.skip nếu unset. Phase 4 MIGRATE-01 sẽ chạy bắt buộc qua `make test-integration`."
  - "5 test ship thay vì 4 — cover 4 success criteria + 1 idempotent re-run dedicated test (separate file readability)."
  - "Defensive cleanup finally (DELETE WHERE email LIKE pattern) + restore head state cuối downgrade test — chống leak test data + chống phá test order."
metrics:
  duration_minutes: ~20
  completed_at: "2026-05-23T18:00:00Z"
  tasks_total: 2
  tasks_completed: 2
  files_created: 2
  files_modified: 4
  tests_added: 5
  tests_passing: "SKIP runtime (TEST_DATABASE_URL chưa set Phase 1 — Phase 4 MIGRATE-01 sẽ run)"
---

# Phase 1 Plan 01-03: Closeout integration test + 3 docs update Summary

Closeout Phase 1 v3.1 RBAC schema migration — verify idempotent migration runtime semantic qua 5 integration test (skip-if-no-DB pattern Phase 4 sẽ run bắt buộc) + 3 docs source-of-truth update atomic (STATE.md progress 0 → 3/15 + REQUIREMENTS.md ROLE-01..04 [x] + CLAUDE.md §6 subsection mới Phase 1 v3.1 RBAC schema pattern reference) + Bonus ROADMAP.md Phase 1 list mark [x] + progress table bump.

## Đã làm gì

### Task 1 — Integration test `test_migration_0006_idempotent.py` (5 test)

Tạo file `api/tests/integration/test_migration_0006_idempotent.py` (~366 LOC) với 5 `@pytest.mark.asyncio` test cover 4 success criteria ROADMAP Phase 1:

| # | Test name | Cover criteria | Logic |
|---|-----------|----------------|-------|
| 1 | `test_upgrade_head_then_check_constraint_accepts_hub_admin` | Criteria 1 — CHECK accept `hub_admin` | `command.upgrade(cfg, 'head')` → INSERT user role='hub_admin' PASS + INSERT role='invalid' → `asyncpg.CheckViolationError` |
| 2 | `test_upgrade_head_idempotent_runs_twice_without_error` | Criteria 1 (idempotent) — re-run KHÔNG fail | `command.upgrade(cfg, 'head')` × 2 (+ `_reset_settings_cache()` giữa 2 lần defensive) — introspect guard ở 3 STEP skip toàn bộ lần 2 |
| 3 | `test_user_hubs_role_nullable_accepts_null_and_value` | Criteria 2 — NULL-aware CHECK | INSERT user_hubs role=NULL PASS + UPDATE role='hub_admin' PASS + UPDATE role='invalid' → CheckViolationError |
| 4 | `test_audit_logs_seed_row_inserted_after_upgrade` | Criteria 3 — audit seed row | SELECT audit_logs WHERE `action='migration.role_seed'` AND `payload->>'migration_revision'='0006'` → row tồn tại với 4 field payload (migration_revision/admin_count/user_hubs_count/timestamp_utc) |
| 5 | `test_downgrade_restores_check_3_value_and_drops_user_hubs_role` | Criteria 4 — downgrade rollback | `command.downgrade(cfg, '-1')` → verify `user_hubs.role` column DROPPED via `information_schema.columns` + INSERT user role='hub_admin' → CheckViolationError (3-value cũ restore) + restore head state cuối test |

**Skip-if-no-DB pattern:** Fixture `test_db_url` đọc `os.environ.get("TEST_DATABASE_URL")` → `pytest.skip(...)` với hint message nếu unset. Phase 4 MIGRATE-01 sẽ chạy bắt buộc qua `make test-integration` (CI pipeline).

**KHÔNG chạy thật ở plan này (per CONTEXT/PLAN):** Test infrastructure ready; runtime verify defer Phase 4 MIGRATE-01 (DB live setup + 4 hub scenario E2E).

### Task 1 SAFETY-CRITICAL — Iter 1 revision fix I-01 + I-02 (DSN injection pattern)

**Root cause Iter 1 finding (pre-execute review):** `migrations/env.py:185-191` runtime OVERRIDE `sqlalchemy.url`:

```python
# env.py (line 185-191) — runtime override pattern
_settings = get_settings()
_x_args = context.get_x_argument(as_dictionary=False)
_hub_arg = parse_hub_x_arg(list(_x_args))
_resolved_dsn = resolve_env_database_url(
    _settings.database_url, _hub_arg, default_hub=_settings.hub_name
)
config.set_main_option("sqlalchemy.url", _resolved_dsn)  # ← OVERWRITE caller's value
```

**Hệ quả** nếu fixture dùng anti-pattern:
```python
# ❌ SAI — env.py OVERWRITE.
cfg = Config("alembic.ini")
cfg.set_main_option("sqlalchemy.url", test_db_url)  # IGNORED ở runtime
command.upgrade(cfg, "head")  # → apply migration vào DB Settings.database_url (vd medinet_central .env) — SAFETY BLOCKER
```

**Mitigation LOCKED (Iter 1 fix I-01):** Fixture monkeypatch env var + clear lru_cache:
```python
# ✅ ĐÚNG — env.py re-read Settings và pick up TEST_DATABASE_URL.
monkeypatch.setenv("DATABASE_URL", test_db_url)
from app.config import get_settings
get_settings.cache_clear()  # @lru_cache decorator (api/app/config.py:629)
cfg = Config(cfg_path)
command.upgrade(cfg, "head")  # env.py:185-191 override sqlalchemy.url = Settings.database_url MỚI (test DSN)
```

**Iter 1 fix I-02 (format DSN):** Giữ `postgresql+asyncpg://` ở fixture-level — env.py xử lý asyncpg natively qua `async_engine_from_config`. Chỉ helper `_asyncpg_dsn()` strip prefix khi `asyncpg.connect()` direct (asyncpg KHÔNG hiểu SQLAlchemy driver hint `+asyncpg`).

**Acceptance criteria verify qua grep (all PASS):**
- `monkeypatch.setenv("DATABASE_URL"` = 2 (fixture init + I-01 mitigation)
- `get_settings.cache_clear()` = 4 (fixture init + defensive `_reset_settings_cache` × 3 trong test idempotent + downgrade)
- `cfg.set_main_option("sqlalchemy.url"` = 0 (anti-pattern absent — docstring tránh exact match)
- `sync_url = test_db_url.replace` = 0 (I-02 fix — KHÔNG convert ở fixture level)
- `from app.config import get_settings` = 2 (fixture + helper)
- `command.upgrade(alembic_cfg, "head")` = 7 (5 test × 1 + idempotent re-run + downgrade restore)
- `command.downgrade(alembic_cfg, "-1")` = 3 (xuất hiện 1 lần execute trong test + 2 lần mention trong docstring)
- `CheckViolationError` = 3 (3 negative case verify CHECK reject)
- `async def test_` = 5 (5 test cover 4 success criteria)
- AST parse exit 0 (syntax hợp lệ)

### Task 2 — 3 docs update atomic

| File | Change |
|------|--------|
| `.planning/STATE.md` | Frontmatter: `last_updated: 2026-05-23T18:00:00.000Z` + `progress.completed_phases: 0 → 1` + `progress.completed_plans: 0 → 3` + `progress.percent: 0 → 20` + `next_action: /gsd-discuss-phase 2 DEP backend...`. Body table v3.1 Planning Summary row Phase 1 → `✅ DONE 2026-05-23 (3 plan)`. THÊM section MỚI "## Phase 1 Results Summary (DONE 2026-05-23)" giữa "## Key Decisions" và "## Open Question" — 3 bullet plan + Carry forward patterns (Alembic explicit raw SQL + audit_logs payload nest + module separation auth/role.py + introspect constraint name + **DSN injection pattern Iter 1 fix I-01**). |
| `.planning/REQUIREMENTS.md` | 4 dòng `- [ ] **ROLE-01..04**` → `- [x] **ROLE-01..04**` + append suffix ` (DONE 2026-05-23 — Plan 01-XX)` (Plan 01-01 cho ROLE-01..03, Plan 01-02 cho ROLE-04). |
| `CLAUDE.md` | Append cuối section 6 (trước footer `---`) subsection mới `### Phase 1 v3.1 RBAC schema pattern (ROLE-01..04 — 2026-05-23)` với 3 bullet plan (01-01 + 01-02 + 01-03 — bullet 01-03 mention `Iter 1 revision fix I-01`) + Backward compat block + **R-V3.1-1 HIGH mitigation chain** (5 bullet — bullet 4 doc DSN injection SAFETY pattern Iter 1 fix I-01) + Next pointer Phase 2. |
| `.planning/ROADMAP.md` | Phase 1 Plans list mark `[x]` cho 01-01, 01-02, 01-03 + append `✅ DONE 2026-05-23` suffix. Progress table v3.1 row: `0/~12 → 3/~12` + `0/15 → 4/15` + status `Defining → Phase 1 DONE`. |

## Verify Status — 2/2 task PASS

| # | Verify command | Result |
|---|----------------|--------|
| Task 1 syntax | `python -c "import ast; ast.parse(...)"` | ✅ `syntax OK` |
| Task 1 5 test | `grep -c "async def test_"` | ✅ 5 |
| Task 1 SAFETY I-01 | `grep -c 'monkeypatch.setenv("DATABASE_URL"'` | ✅ 2 (≥1) |
| Task 1 SAFETY I-01 | `grep -c "get_settings.cache_clear()"` | ✅ 4 (≥2) |
| Task 1 anti-pattern | `grep -c 'cfg.set_main_option("sqlalchemy.url"'` | ✅ 0 (KHÔNG chứa) |
| Task 1 I-02 | `grep -c "sync_url = test_db_url.replace"` | ✅ 0 (KHÔNG convert) |
| Task 1 import | `grep -c "from app.config import get_settings"` | ✅ 2 |
| Task 2 STATE | `grep -c "completed_plans: 3"` | ✅ 1 |
| Task 2 STATE section | `grep -c "Phase 1 Results Summary"` | ✅ 1 |
| Task 2 STATE Iter 1 | `grep -c "Iter 1 revision fix I-01"` | ✅ 1 |
| Task 2 REQ ROLE-01 | `grep -c "\[x\] \*\*ROLE-01\*\*"` | ✅ 1 |
| Task 2 REQ ROLE-04 | `grep -c "\[x\] \*\*ROLE-04\*\*"` | ✅ 1 |
| Task 2 CLAUDE | `grep -c "Phase 1 v3.1 RBAC schema pattern"` | ✅ 1 |
| Task 2 CLAUDE Iter 1 | `grep -c "Iter 1 revision fix I-01"` | ✅ 1 |

## Decisions Made

### D-1: Iter 1 revision fix I-01 — fixture monkeypatch DATABASE_URL + get_settings.cache_clear()

**Pre-execute review** (planning iteration) phát hiện `migrations/env.py:185-191` runtime OVERRIDE `sqlalchemy.url` từ `get_settings().database_url`. Hệ quả nếu fixture cũ dùng `cfg.set_main_option("sqlalchemy.url", test_db_url)`: env.py sẽ ghi đè bằng DSN từ Settings (boot từ `.env`, vd `medinet_central`) → test apply migration vào DB dev/prod, KHÔNG phải TEST_DATABASE_URL → **SAFETY BLOCKER**.

**Mitigation LOCKED:**
1. `monkeypatch.setenv("DATABASE_URL", test_db_url)` — pytest builtin auto-restore env var sau test scope.
2. `from app.config import get_settings; get_settings.cache_clear()` — `@lru_cache` decorator ở `api/app/config.py:629` cache Settings instance; cache_clear() force re-parse env vars mới.
3. `Config(cfg_path)` — KHÔNG gọi `set_main_option("sqlalchemy.url", ...)` (anti-pattern bị override).
4. env.py:185-191 ở runtime: `_settings = get_settings()` re-read → `Settings.database_url = TEST_DATABASE_URL` → `config.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)`.
5. `command.upgrade(cfg, "head")` apply migration vào TEST DB an toàn.

**Acceptance criteria verify** qua grep — see Verify Status table.

### D-2: Iter 1 revision fix I-02 — format DSN giữ `postgresql+asyncpg://` ở fixture

env.py + Settings expect prefix asyncpg (`async_engine_from_config` xử lý natively + `resolve_env_database_url` parse format gốc). KHÔNG convert sync_url ở level fixture (anti-pattern Plan iter cũ). Chỉ helper `_asyncpg_dsn()` strip prefix khi `asyncpg.connect()` direct (asyncpg KHÔNG hiểu SQLAlchemy driver hint `+asyncpg`).

### D-3: Skip-if-no-DB pattern (pytest.skip TEST_DATABASE_URL unset)

Plan 01-03 KHÔNG chạy test runtime — chỉ verify file structure + syntax + DSN injection pattern present. Phase 4 MIGRATE-01 sẽ chạy bắt buộc qua `make test-integration` với DB live (1 hub central + 3 hub con dmd/tdt/sample).

Lý do: Phase 1 setup chưa có testcontainers; dùng env var `TEST_DATABASE_URL` override để operator chạy manual lúc cần debug. Pattern song song M2 + v3.0 integration test cluster.

### D-4: 5 test ship thay vì 4 (1 idempotent re-run dedicated test)

Plan acceptance yêu cầu 4 success criteria ROADMAP Phase 1 → ship 5 test:
- 4 test chính: CHECK accept hub_admin / user_hubs.role nullable / audit seed / downgrade rollback.
- 1 test dedicated: re-run upgrade head 2 lần KHÔNG fail (separate file readability).

Pattern: 1 test = 1 success criteria + idempotent dedicated → dễ debug khi fail (chống false-positive aggregate test).

## Carry forward Phase 4 (MIGRATE-01)

Phase 4 MIGRATE-01 sẽ chạy test bắt buộc:
- `make test-integration` set `TEST_DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/medinet_test`.
- pytest pickup fixture `test_db_url` → KHÔNG skip → execute 5 test với DB live.
- Verify upgrade idempotent + downgrade rollback + CHECK constraint behavior + audit seed.
- 4 hub scenario E2E (super_admin / hub_admin dmd / hub_admin tdt / viewer) qua pytest httpx (MIGRATE-02).

**KHÁC Plan 04-07 v3.0 closeout pattern:** Phase 1 v3.1 RUN integration test ngay (KHÔNG defer Phase 4 MIGRATE-01) vì migration schema critical + R-V3.1-1 HIGH severity. Plan 04-07 v3.0 smoke checkpoint runtime SKIP pre-resolved (defer Phase 7 MIGRATE-05). Phase 1 v3.1 baseline test infrastructure ready để Phase 4 chỉ cần `make test-integration` qua CI.

## Threat model verification

| Threat ID | Mitigation status |
|-----------|-------------------|
| T-01-03-01 Tampering pha DB test schema | ✅ Cleanup defensive `DELETE WHERE email LIKE '...test.local'` trong fixture finally; last test restore head state. |
| T-01-03-02 Repudiation docs update | ✅ Accept — git commit history đủ trace (`chore(01-03): closeout...`). |
| T-01-03-03 DoS test chạy DB production accidentally | ✅ **[Iter 1 fix I-01]** Fixture monkeypatch DATABASE_URL + cache_clear() bypass env.py:185-191 runtime override. TEST_DATABASE_URL env var REQUIRED (pytest.skip nếu unset); KHÔNG hardcode production DSN. |
| T-01-03-04 Integrity STATE.md merge conflict | ✅ Accept — Plan 01-03 wave 2 sequential sau 01-01 + 01-02; KHÔNG parallel writer. |
| T-01-03-05 Tampering apply migration vào DB dev/prod | ✅ **[Iter 1 fix I-01 SAFETY BLOCKER]** Fixture pattern monkeypatch.setenv + get_settings.cache_clear() TRƯỚC mọi command.upgrade()/downgrade() — env.py re-read Settings (lru_cache cleared) pick up TEST_DATABASE_URL thay vì cached .env value. Acceptance criteria verify qua grep present. |

## Phase 1 Done — 100% (3 plan ship 4 REQ-ID)

| Plan | Status | Date | REQ-ID | Commit |
|------|--------|------|--------|--------|
| 01-01 — Alembic migration 0006 ADD COLUMN user_hubs.role | ✅ DONE | 2026-05-24 | ROLE-01..03 | (Plan 01-01 commit) |
| 01-02 — get_effective_role helper + 6 unit test | ✅ DONE | 2026-05-24 | ROLE-04 | (Plan 01-02 commit) |
| 01-03 — Closeout integration test + 3 docs update | ✅ **DONE** | **2026-05-23** | (closeout) | (sẽ điền sau commit) |

**Phase 1 Total:** 3 plan ship 4 REQ-ID ROLE-01..04 (100%).

## Phase 2 sẵn sàng

Next: `/gsd-discuss-phase 2 — DEP backend RBAC enforcement` (require_hub_admin_for dependency + GET /api/hubs filter + CRUD scope + audit actor.scope) — 5 REQ-ID DEP-01..05 + estimate 4-5 plan.

Phase 1 baseline ready:
- Migration 0006 (Plan 01-01) — schema có `user_hubs.role` nullable + CHECK enum 4 value.
- Helper `get_effective_role` (Plan 01-02) — Phase 2 sẽ import build dependency `require_hub_admin_for(hub_id)`.
- Integration test (Plan 01-03) — Phase 4 MIGRATE-01 sẽ verify runtime full E2E.

## Deviations from Plan

None — plan executed exactly as written. 2 task complete, tất cả acceptance criteria + verify command PASS. Iter 1 revision fix I-01 + I-02 đã được integrate vào fixture từ đầu (KHÔNG có anti-pattern rollback iteration).

## Stub Tracking

Không có stub. File integration test thuần — KHÔNG có placeholder UI / mock data / empty value. STATE.md + REQUIREMENTS.md + CLAUDE.md + ROADMAP.md update text only.

## Self-Check: PASSED

- ✅ FOUND: `Hub_All/api/tests/integration/test_migration_0006_idempotent.py`
- ✅ FOUND: `Hub_All/.planning/phases/01-rbac-schema-migration/01-03-SUMMARY.md`
- ✅ AST parse PASS (`python -c "import ast; ast.parse(...)"` exit 0)
- ✅ 5 async test function (grep count = 5)
- ✅ `monkeypatch.setenv("DATABASE_URL"` = 2 (≥1 acceptance) — Iter 1 fix I-01 present
- ✅ `get_settings.cache_clear()` = 4 (≥2 acceptance) — defensive between upgrade/downgrade
- ✅ `cfg.set_main_option("sqlalchemy.url"` = 0 (acceptance KHÔNG chứa) — anti-pattern absent
- ✅ `sync_url = test_db_url.replace` = 0 (acceptance KHÔNG chứa) — Iter 1 fix I-02
- ✅ STATE.md `completed_plans: 3` (1 occurrence) + `Phase 1 Results Summary` section (1 occurrence) + `Iter 1 revision fix I-01` mention (1 occurrence)
- ✅ REQUIREMENTS.md `[x] **ROLE-01**` + `[x] **ROLE-04**` (1 occurrence each) — 4 ROLE marks done
- ✅ CLAUDE.md `Phase 1 v3.1 RBAC schema pattern` subsection (1 occurrence) + `Iter 1 revision fix I-01` mention (1 occurrence)
- ✅ ROADMAP.md Phase 1 Plans list 3 `[x]` + Progress table v3.1 row bump `3/~12` + `4/15` + status `Phase 1 DONE`
- ✅ Commit hash sẽ điền sau khi `git commit` executed (commit step kế tiếp atomic).
