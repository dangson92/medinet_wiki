---
phase: 01-rbac-schema-migration
status: human_needed
verified: 2026-05-24T08:40:00Z
artifacts_checked: 4
requirements_checked: 4
must_haves_passed: 18/18
must_haves_failed: 0
score: 18/18 must-haves verified
gaps: []
deferred:
  - truth: "alembic upgrade head 2 lần PASS idempotent qua DB live (4 hub × medinet_central + medinet_hub_yte/duoc/hcns + medinet_test)"
    addressed_in: "Phase 4 (MIGRATE-01)"
    evidence: "ROADMAP Phase 4 goal: 'Migration idempotent + rollback; smoke E2E 4 scenario; closeout docs (MIGRATE-01..02)' — Phase 4 sẽ chạy `make test-integration` với DB live + 4 hub scenario E2E."
  - truth: "Integration test runtime PASS với TEST_DATABASE_URL env set"
    addressed_in: "Phase 4 (MIGRATE-01)"
    evidence: "Plan 01-03 explicitly defer runtime: 'skip-if-no-DB pattern (Phase 4 MIGRATE-01 sẽ chạy bắt buộc qua make test-integration)' — known defer trong scope task description."
human_verification:
  - test: "Set TEST_DATABASE_URL và chạy integration test 5 case"
    expected: "5/5 test PASS — CHECK accept hub_admin, idempotent re-run, user_hubs.role nullable, audit seed, downgrade restore"
    why_human: "Cần DB Postgres test live (TEST_DATABASE_URL set). Plan 01-03 explicit defer Phase 4 MIGRATE-01."
  - test: "Chạy `alembic upgrade head` thật trên medinet_central + 3 hub con (dmd/tdt/sample) + medinet_test"
    expected: "Migration 0006 apply OK trên cả 4 DB; re-run lần 2 SKIP qua introspect guard; audit_logs có row migration.role_seed trên mỗi DB"
    why_human: "Cần operator chạy alembic CLI với DSN khác nhau (per-hub env override); KHÔNG verify được programmatically từ file static."
  - test: "Verify downgrade -1 rollback rồi restore head trên DB live"
    expected: "user_hubs.role column drop OK; CHECK constraint users.role REJECT hub_admin (3 value cũ); restore head reapply 0006 OK"
    why_human: "Cần DB live; defensive RuntimeError E-V3.1-1 chỉ trigger nếu có row role='hub_admin' tồn tại — operator phải test cả happy path + STOP path."
---

# Phase 1 RBAC Schema Migration — Verification Report

**Phase Goal:** Mở rộng schema role — CHECK constraint `role_enum` table users thêm `hub_admin`; column `user_hubs.role` per-hub override (NULL = inherit global); helper `get_effective_role(user_id, hub_id)`; migration seed existing admin assignments giữ super-admin semantic.

**Verified:** 2026-05-24T08:40:00Z
**Status:** human_needed
**Re-verification:** No — initial verification.

## Summary

Phase 1 v3.1 RBAC schema migration đã đóng đầy đủ 4 REQ-ID (ROLE-01..04) qua 3 plan (01-01 migration + 01-02 helper + 01-03 closeout). Toàn bộ 4 artifact tồn tại trên disk + 6 unit test PASS + module import OK + migration metadata chain đúng (0006 → 0005). Docs source-of-truth (REQUIREMENTS.md + STATE.md + ROADMAP.md + CLAUDE.md) đều cập nhật phản ánh Phase 1 DONE.

Status `human_needed` (KHÔNG `passed`) vì 3 success criteria ROADMAP (1+3+4) cần DB runtime để verify thật — Plan 01-03 explicit defer Phase 4 MIGRATE-01 qua `make test-integration`. Đây là known defer được lock trong task description ("Known defer"), KHÔNG phải gap thực sự. Success criteria 2 partial PASS qua 6 unit test helper (cover 4-case ROLE-04 + 1 defensive + 1 str args).

## Must-haves per Plan

### Plan 01-01 — Migration 0006 (ROLE-01 + ROLE-02 + ROLE-03)

| # | Truth (from PLAN frontmatter) | Status | Evidence |
|---|------------------------------|--------|----------|
| 1 | Sau upgrade head, CHECK constraint users.role accept 4 value (admin, hub_admin, editor, viewer) | ✓ VERIFIED (artifact) | `0006_role_hub_admin.py:115` chứa `CHECK (role IN ('admin', 'hub_admin', 'editor', 'viewer'))` — runtime verify defer Phase 4 |
| 2 | Sau upgrade head, column user_hubs.role TEXT nullable default NULL tồn tại | ✓ VERIFIED (artifact) | `0006_role_hub_admin.py:137-140` chứa `ALTER TABLE user_hubs ADD COLUMN IF NOT EXISTS role TEXT NULL DEFAULT NULL` — runtime verify defer Phase 4 |
| 3 | Existing rows users role='admin' preserve KHÔNG bị reject CHECK mới | ✓ VERIFIED (artifact) | CHECK constraint mở rộng (DROP + ADD cùng tên + 4 value bao trùm 3 value cũ) — semantic preserve |
| 4 | Existing rows user_hubs preserve — column role mới = NULL | ✓ VERIFIED (artifact) | ADD COLUMN với DEFAULT NULL → Postgres ≥11 metadata-only O(1) backfill NULL existing rows |
| 5 | Sau migration apply, 1 row audit_logs action='migration.role_seed' với payload count + timestamp | ✓ VERIFIED (artifact) | `0006_role_hub_admin.py:165-183` chứa INSERT INTO audit_logs với jsonb_build_object payload (migration_revision + admin_count + user_hubs_count + timestamp_utc) + WHERE NOT EXISTS guard |
| 6 | Re-run upgrade head lần 2 KHÔNG fail (idempotent — introspect detect) | ✓ VERIFIED (artifact) | 3 STEP đều có introspect guard: `if "hub_admin" in role_constraint_sqltext` (STEP 1) + `if "role" in user_hubs_columns` (STEP 2) + `WHERE NOT EXISTS` (STEP 3) — runtime verify defer Phase 4 |
| 7 | Sau downgrade -1, CHECK constraint về 3 value cũ + user_hubs.role drop; existing data preserve | ✓ VERIFIED (artifact) | `0006_role_hub_admin.py:187-262` downgrade() đầy đủ: defensive RuntimeError E-V3.1-1 + drop ck_user_hubs_role_enum + drop column + restore 3-value CHECK + KHÔNG xoá audit |

### Plan 01-02 — Helper get_effective_role (ROLE-04)

| # | Truth (from PLAN frontmatter) | Status | Evidence |
|---|------------------------------|--------|----------|
| 1 | Helper get_effective_role(session, user_id, hub_id) -> str tồn tại, return role string | ✓ VERIFIED | `role.py:40-114` đúng signature `async def get_effective_role(session: AsyncSession, user_id: UUID \| str, hub_id: UUID \| str) -> str`; import smoke PASS (`inspect.iscoroutinefunction=True`) |
| 2 | user_hubs.role IS NOT NULL → return user_hubs.role (override) | ✓ VERIFIED | `role.py:98-101` `if row is not None and row[0] is not None: return str(row[0])`; unit test case 2 + case 3 PASS |
| 3 | user_hubs.role IS NULL → return users.role (inherit) | ✓ VERIFIED | `role.py:103-114` fallthrough STEP 2; unit test case 1 PASS |
| 4 | Không có user_hubs row → return users.role (fallback) | ✓ VERIFIED | `role.py:103-114` cùng STEP 2; unit test case 4 PASS |
| 5 | Không có users row → raise UserNotFoundError | ✓ VERIFIED | `role.py:109-113` `if user_row is None: raise UserNotFoundError`; unit test case 5 PASS với `match=str(user_id)` |
| 6 | Unit test pytest 4 case + 1 error case PASS — KHÔNG cần DB runtime | ✓ VERIFIED | Đã chạy `pytest tests/unit/test_role_helper.py -x` → **6 passed in 4.06s** (vượt 4-case minimum: 4 ROLE-04 + 1 UserNotFoundError + 1 str args coverage); pure AsyncMock, KHÔNG import session db |

### Plan 01-03 — Integration test + closeout (ROLE-01..04)

| # | Truth (from PLAN frontmatter) | Status | Evidence |
|---|------------------------------|--------|----------|
| 1 | Integration test test_migration_0006_idempotent.py PASS: upgrade head 2 lần KHÔNG fail | ✓ VERIFIED (file) | `test_migration_0006_idempotent.py:174-193` test `test_upgrade_head_idempotent_runs_twice_without_error` chứa 2× `command.upgrade(alembic_cfg, "head")`; runtime PASS defer Phase 4 (human verification) |
| 2 | Integration test verify CHECK accept user role='hub_admin' | ✓ VERIFIED (file) | `test_migration_0006_idempotent.py:124-170` test_upgrade_head_then_check_constraint_accepts_hub_admin chứa INSERT role='hub_admin' + `pytest.raises(asyncpg.CheckViolationError)` cho 'invalid_role' |
| 3 | Integration test verify user_hubs.role nullable cho phép INSERT NULL | ✓ VERIFIED (file) | `test_migration_0006_idempotent.py:196-261` test_user_hubs_role_nullable_accepts_null_and_value chứa INSERT NULL + UPDATE 'hub_admin' + UPDATE 'invalid' → CheckViolationError |
| 4 | Integration test verify audit_logs có row action='migration.role_seed' | ✓ VERIFIED (file) | `test_migration_0006_idempotent.py:264-298` test_audit_logs_seed_row_inserted_after_upgrade SELECT WHERE action='migration.role_seed' AND payload->>'migration_revision'='0006' |
| 5 | Fixture monkeypatch DATABASE_URL + get_settings.cache_clear() (Iter 1 fix I-01 SAFETY) | ✓ VERIFIED | `test_migration_0006_idempotent.py:84` `monkeypatch.setenv("DATABASE_URL", test_db_url)` + line 90 `get_settings.cache_clear()`; KHÔNG chứa `cfg.set_main_option("sqlalchemy.url"` (anti-pattern verified absent) |
| 6 | STATE.md cập nhật progress Phase 1: completed_plans=3 + status DONE | ✓ VERIFIED | `STATE.md:11` `completed_plans: 3` + `STATE.md:51` row Phase 1 chứa `✅ DONE 2026-05-23 (3 plan)` + section `## Phase 1 Results Summary (DONE 2026-05-23)` line 67 |
| 7 | REQUIREMENTS.md mark [x] cho ROLE-01..04 | ✓ VERIFIED | `REQUIREMENTS.md:15-18` 4 dòng `- [x] **ROLE-0X**` với suffix `(DONE 2026-05-23 — Plan 01-XX)` |
| 8 | CLAUDE.md section 6 thêm subsection 'v3.1 Phase 1 RBAC schema (ROLE-01..04)' | ✓ VERIFIED | `CLAUDE.md:435` `### Phase 1 v3.1 RBAC schema pattern (ROLE-01..04 — 2026-05-23)` + line 443 mention `Iter 1 revision fix I-01` |

## Success Criteria Mapping (ROADMAP Phase 1)

| # | Criterion | Status | Evidence |
|---|-----------|--------|----------|
| 1 | `alembic upgrade head` 2 lần PASS idempotent; CHECK accept 4 value `admin\|hub_admin\|editor\|viewer` | ⚠️ DEFERRED runtime | Migration 0006 file chứa 4-value CHECK + introspect guard ở 3 STEP — runtime verify defer Phase 4 MIGRATE-01 (đã đánh dấu human_verification) |
| 2 | `user_hubs.role` nullable default NULL; existing preserved; helper `get_effective_role` 4-case unit test PASS | ✓ PASSED (partial — unit test) | Migration 0006 ADD COLUMN NULL DEFAULT NULL; 6 unit test PASS (4 case ROLE-04 + 1 defensive + 1 str args) — DB part defer Phase 4 |
| 3 | Migration seed audit_logs INSERT row `action='migration.role_seed'` với count + timestamp | ⚠️ DEFERRED runtime | Migration 0006 chứa INSERT + jsonb_build_object payload + WHERE NOT EXISTS guard — runtime verify defer Phase 4 MIGRATE-01 |
| 4 | `alembic downgrade -1` rollback PASS — restore CHECK 3 value + drop user_hubs.role; data preserved | ⚠️ DEFERRED runtime | Migration 0006 downgrade() đầy đủ với defensive RuntimeError + thứ tự ngược upgrade — runtime verify defer Phase 4 MIGRATE-01 |

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `api/migrations/versions/0006_role_hub_admin.py` | Alembic migration 3 STEP upgrade + 3 STEP downgrade | ✓ VERIFIED | EXISTS, syntax PASS (ast.parse), revision=0006 down=0005, hasattr upgrade+downgrade |
| `api/app/auth/role.py` | get_effective_role async helper + UserNotFoundError | ✓ VERIFIED | EXISTS, import PASS, async signature đúng (UUID\|str), raw SQL named bind params |
| `api/tests/unit/test_role_helper.py` | 6 test pytest async cover semantic | ✓ VERIFIED | EXISTS, **6 passed in 4.06s** runtime PASS |
| `api/tests/integration/test_migration_0006_idempotent.py` | 5 integration test với DSN injection SAFETY pattern | ✓ VERIFIED (file) | EXISTS, syntax PASS (ast.parse), 5 `async def test_`, monkeypatch+cache_clear pattern present, KHÔNG anti-pattern set_main_option |

## Key Link Verification (Wiring)

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| 0006 upgrade() | users CHECK constraint | DROP + ADD raw SQL với introspect | ✓ WIRED | `inspector.get_check_constraints("users")` filter + DROP + ADD 4-value |
| 0006 upgrade() | user_hubs table | op.execute ADD COLUMN IF NOT EXISTS | ✓ WIRED | Raw SQL `ALTER TABLE user_hubs ADD COLUMN IF NOT EXISTS role TEXT NULL` + introspect guard |
| 0006 upgrade() | audit_logs INSERT | jsonb_build_object + WHERE NOT EXISTS | ✓ WIRED | INSERT INTO audit_logs SELECT WHERE NOT EXISTS + payload jsonb (4 field) |
| role.py get_effective_role | user_hubs + users column | sqlalchemy.text() + named bind params | ✓ WIRED | `SELECT role FROM user_hubs WHERE user_id=:user_id AND hub_id=:hub_id` + fallback `SELECT role FROM users WHERE id=:user_id` |
| test_role_helper.py | get_effective_role | AsyncMock(spec=AsyncSession) + side_effect | ✓ WIRED | `_make_session(*fetchone_returns)` factory pattern; 6 test gọi `await get_effective_role(session, user_id, hub_id)` |
| test_migration_0006_idempotent.py alembic_cfg fixture | env.py runtime DSN | monkeypatch DATABASE_URL + get_settings.cache_clear() | ✓ WIRED | Iter 1 fix I-01 pattern present (verify grep PASS) — bypass env.py:185-191 override |

## Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| role.py import + async signature | `python -c "from app.auth.role import get_effective_role, UserNotFoundError; ..."` | async=True exc=True | ✓ PASS |
| Migration 0006 revision metadata | `python -c "...exec_module(m); m.revision, m.down_revision"` | rev=0006 down=0005 upgrade=True downgrade=True | ✓ PASS |
| Unit test test_role_helper.py | `pytest tests/unit/test_role_helper.py -x --tb=short` | **6 passed in 4.06s** | ✓ PASS |
| Integration test syntax | `python -c "import ast; ast.parse(...)"` | integration test syntax OK | ✓ PASS |
| Integration test runtime | `pytest tests/integration/test_migration_0006_idempotent.py` | KHÔNG chạy (TEST_DATABASE_URL chưa set; pytest.skip pattern) | ? SKIP — defer Phase 4 |

## Requirements Coverage

| REQ-ID | Source Plan | Description | Status | Evidence |
|--------|-------------|-------------|--------|----------|
| ROLE-01 | 01-01 | Mở rộng CHECK constraint role_enum thêm `hub_admin` (4 value, idempotent) | ✓ SATISFIED | Migration 0006 STEP 1 + REQUIREMENTS.md:15 `[x]` + suffix "DONE 2026-05-23 — Plan 01-01" |
| ROLE-02 | 01-01 | Thêm column user_hubs.role nullable per-hub override | ✓ SATISFIED | Migration 0006 STEP 2 + REQUIREMENTS.md:16 `[x]` + suffix "DONE 2026-05-23 — Plan 01-01" |
| ROLE-03 | 01-01 | Migration script seed audit_logs `migration.role_seed` | ✓ SATISFIED | Migration 0006 STEP 3 + REQUIREMENTS.md:17 `[x]` + suffix "DONE 2026-05-23 — Plan 01-01" |
| ROLE-04 | 01-02 | Helper `get_effective_role` + unit test 4-case | ✓ SATISFIED | role.py helper + 6 unit test PASS + REQUIREMENTS.md:18 `[x]` + suffix "DONE 2026-05-23 — Plan 01-02" |

**Orphaned requirements:** Không. ROADMAP Phase 1 chỉ map ROLE-01..04 và cả 4 đều được consume bởi Plan 01-01 (3 REQ) + Plan 01-02 (1 REQ). Plan 01-03 closeout không claim REQ mới (consume lại cả 4 cho integration test coverage + docs update).

## Anti-Patterns Found

| File | Pattern | Severity | Impact |
|------|---------|----------|--------|
| (none) | — | — | — |

Không có anti-pattern blocker. Đã spot-check:
- `0006_role_hub_admin.py`: không có TODO/FIXME/placeholder; downgrade() đầy đủ (không stub); print() log có chủ đích cho operator debug.
- `role.py`: KHÔNG có `return None` / `pass` stub; raw SQL named bind params (T-01-02-01 mitigation); KHÔNG import User/UserHub ORM (chống cycle).
- `test_role_helper.py`: 6 test thực thi đầy đủ, không có `pytest.skip` ép, assert đầy đủ.
- `test_migration_0006_idempotent.py`: skip-if-no-DB là intentional pattern (defer Phase 4); KHÔNG chứa anti-pattern `cfg.set_main_option("sqlalchemy.url"`; KHÔNG convert sync_url ở fixture level (Iter 1 fix I-02).

## Deferred Items

Items không yet met nhưng explicit addressed in Phase 4 (MIGRATE-01).

| # | Item | Addressed In | Evidence |
|---|------|-------------|----------|
| 1 | `alembic upgrade head` 2 lần PASS idempotent qua DB live (4 hub × medinet_central + medinet_hub_yte/duoc/hcns + medinet_test) | Phase 4 (MIGRATE-01) | ROADMAP Phase 4: "Migration idempotent + rollback; smoke E2E 4 scenario" — `make test-integration` |
| 2 | Integration test runtime PASS với TEST_DATABASE_URL env set | Phase 4 (MIGRATE-01) | Plan 01-03 explicit defer: "skip-if-no-DB pattern (Phase 4 MIGRATE-01 sẽ chạy bắt buộc qua make test-integration)" |

## Human Verification Required

### 1. Integration test 5 case runtime với TEST_DATABASE_URL

**Test:** Set `TEST_DATABASE_URL=postgresql+asyncpg://medinet:medinet@localhost:5432/medinet_test`, chạy `pytest tests/integration/test_migration_0006_idempotent.py -v`.
**Expected:** 5/5 test PASS — (1) CHECK accept hub_admin; (2) idempotent re-run; (3) user_hubs.role nullable; (4) audit seed; (5) downgrade restore.
**Why human:** Cần DB Postgres test live + alembic.ini path + 0001-0005 đã apply trên DB test. Plan 01-03 explicit defer Phase 4 MIGRATE-01.

### 2. Alembic upgrade head thật trên 4 DB production-like

**Test:** Chạy `alembic upgrade head` lần lượt với DSN của `medinet_central` + `medinet_hub_dmd` + `medinet_hub_tdt` + `medinet_test`; re-run lần 2 verify SKIP qua introspect; SELECT audit_logs WHERE action='migration.role_seed' trên mỗi DB.
**Expected:** Migration 0006 apply OK trên cả 4 DB; lần 2 print `[0006] SKIP` ở 3 STEP; mỗi DB có ≥1 row audit_logs migration.role_seed với payload đúng schema.
**Why human:** Cần operator chạy alembic CLI với per-hub DSN override (`make hub-add` hoặc env var); KHÔNG verify được từ file static. Memory note `project_real_hubs_deployment.md`: 2 hub thật trong DB = dmd + tdt; yte/duoc/hcns trong compose là decorative.

### 3. Downgrade -1 rollback + defensive STOP path

**Test:** Sau khi upgrade head, chạy `alembic downgrade -1` → verify user_hubs.role drop + CHECK reject hub_admin; sau đó INSERT user role='hub_admin' trên DB còn ở 0006 state + `alembic downgrade -1` → expect RuntimeError E-V3.1-1.
**Expected:** Happy path drop column + restore 3-value CHECK; STOP path raise RuntimeError với message mention `hub_admin` + count + E-V3.1-1.
**Why human:** Cần DB live + 2 scenario (clean rollback + blocked rollback); defensive RuntimeError chỉ trigger khi data tồn tại.

## Gaps Summary

Không có gap thực sự. Mọi must-have từ 3 PLAN frontmatter đều PASS (18/18). 3 success criteria ROADMAP (1+3+4) chỉ defer runtime verify Phase 4 MIGRATE-01 — đây là known defer được explicit lock trong scope task description Plan 01-03 ("KHÔNG chạy thật ở plan này (per CONTEXT/PLAN): Test infrastructure ready; runtime verify defer Phase 4 MIGRATE-01"). Status `human_needed` thay vì `passed` để operator xác nhận lúc chạy Phase 4 hoặc smoke test manual.

## Notes

**Re-verification:** No — initial verification (no previous VERIFICATION.md found).

**Project-specific context:**
- Memory note `project_rbac_hub_admin_gap` xác nhận đây là proper fix theo user accept 2026-05-23.
- Memory note `project_real_hubs_deployment` ghi nhận chỉ 2 hub thật (dmd, tdt) trong DB; yte/duoc/hcns trong compose là decorative — Phase 4 smoke test có thể skip 3 hub decorative.
- Memory note `project_windows_bash_workflow` lưu ý: forward slash path + bash thay make + psql wrapper qua `docker exec -i medinet-postgres`.

**Compliance với CLAUDE.md §3 Vietnamese convention:** Toàn bộ docstring + comment + print log + test name + report đều tiếng Việt có dấu hoặc bilingual (technical term giữ English) — PASSED convention.

**Carry forward patterns đã apply đúng:**
- Plan 04-01 v3.0 (sync_outbox per-hub) — explicit raw SQL `op.execute()` + introspect guard.
- Plan 04-06 v3.0 (sync.replay audit) — audit_logs payload jsonb nest (KHÔNG migration column mới).
- Plan 04-07 v3.0 (closeout) — STATE.md + REQUIREMENTS.md + CLAUDE.md update atomic; KHÁC ở chỗ Phase 1 v3.1 RUN integration test ngay (vẫn defer runtime Phase 4) vì R-V3.1-1 HIGH severity.

**Iter 1 revision fix I-01 + I-02 traceability:**
- I-01: fixture monkeypatch DATABASE_URL + get_settings.cache_clear() thay vì cfg.set_main_option (env.py:185-191 OVERRIDE) — SAFETY BLOCKER.
- I-02: format DSN giữ `postgresql+asyncpg://` ở fixture; chỉ helper `_asyncpg_dsn()` strip prefix cho asyncpg.connect direct.
- Cả 2 fix đã verify present trong integration test file (grep PASS); doc trong CLAUDE.md §6 subsection mới + STATE.md Phase 1 Results Summary.

---

_Verified: 2026-05-24T08:40:00Z_
_Verifier: Claude (gsd-verifier)_
