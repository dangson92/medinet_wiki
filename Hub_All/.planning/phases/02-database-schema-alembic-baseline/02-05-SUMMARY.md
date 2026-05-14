---
phase: 2
plan: 05
subsystem: api/tests/integration + api/Makefile
tags: [pytest, testcontainers, pgvector, alembic, integration-test, verify-suite, makefile, hnsw, cosine-ops, drift-detection, p7, p17, p20, r1, r4]
dependency_graph:
  requires:
    - Plan 02-01 (app.db.base.Base + NAMING_CONVENTION)
    - Plan 02-02 (10 ORM model class)
    - Plan 02-03 (Alembic env.py async + include_object filter)
    - Plan 02-04 (migration 0001_initial_schema.py paste-ready 494 dong)
  provides:
    - Hub_All/api/Makefile (modified — them 3 target migrate-up/down/check + migrate-history)
    - Hub_All/api/pyproject.toml (modified — dev deps testcontainers[postgres]>=4.7,<5 + psycopg2-binary>=2.9,<3)
    - Hub_All/api/tests/integration/__init__.py (created — empty package marker)
    - Hub_All/api/tests/integration/conftest.py (created — source-of-truth 2 fixture share giua 3 file test)
    - Hub_All/api/tests/integration/test_migration_upgrade_downgrade.py (created — 2 test verify Criteria #1 + #3)
    - Hub_All/api/tests/integration/test_chunks_hnsw_cosine_ops.py (created — 3 test verify Criteria #2 + #4 + R1)
    - Hub_All/api/tests/integration/test_alembic_ignores_cocoindex_schema.py (created — 2 test verify Criteria #5 + P20)
  affects:
    - Phase 3 (Auth) — schema users + refresh_tokens da verified runtime, san sang impl login/JWT.
    - Phase 4 (CocoIndex) — chunks + HNSW vector_cosine_ops + Vector(1536) da verified runtime, san sang ingest.
    - Phase 5-7 (CRUD/Search/Ask) — toan bo bang da test runtime, FK chain CASCADE/SET NULL bake.
    - Phase 10 (Hardening) — testcontainers pattern + critical-path marker san sang scale ra full integration suite ≥50% coverage (HARD-03).
tech_stack:
  added:
    - testcontainers[postgres]==4.14.2 (dev only — spawn Postgres container per-module)
    - psycopg2-binary==2.9.12 (dev only — sync driver cho fixture create_engine)
    - docker==7.1.0 (transitively via testcontainers)
    - wrapt==2.1.2 (transitively)
    - pywin32==311 (Windows-only transitively)
  patterns:
    - Pytest fixture scope module/function pattern (container per-module, alembic_cfg per-function voi monkeypatch.setenv)
    - testcontainers PostgresContainer voi image pin `pgvector/pgvector:pg16` (P17 MANDATORY — alpine se FAIL CREATE EXTENSION vector)
    - alembic.command.upgrade(cfg, "head") programmatic API thay subprocess (faster + better error context)
    - alembic.command.check(cfg) drift detection programmatic (P20 mitigation)
    - pg_indexes.indexdef raw query verify HNSW vector_cosine_ops literal (P17 hard verify)
    - pg_attribute + format_type(atttypid, atttypmod) verify vector(1536) (R1 hard verify)
    - pg_constraint filter bang conrelid + contype thay vi conname (defensive — tranh phu thuoc naming convention pattern)
key_files:
  created:
    - Hub_All/api/tests/integration/__init__.py
    - Hub_All/api/tests/integration/conftest.py
    - Hub_All/api/tests/integration/test_migration_upgrade_downgrade.py
    - Hub_All/api/tests/integration/test_chunks_hnsw_cosine_ops.py
    - Hub_All/api/tests/integration/test_alembic_ignores_cocoindex_schema.py
  modified:
    - Hub_All/api/Makefile
    - Hub_All/api/pyproject.toml
    - Hub_All/api/uv.lock
decisions:
  - D-02-05-01 testcontainers image pin `pgvector/pgvector:pg16` (KHONG postgres:16-alpine) — alpine khong co binary pgvector -> CREATE EXTENSION vector se FAIL. Image official ~200MB nhung pre-pulled 1 lan, sau do test runs 9-18s.
  - D-02-05-02 Fixture postgres_container scope=module thay vi scope=session — moi file test (module) co container rieng tranh side-effect giua module (vd test_alembic_ignores_cocoindex_schema tao schema cocoindex se leak vao module khac neu shared session). Trade-off: spin up 3 container/run thay vi 1 — chap nhan vi mỗi container ~3s spin-up tren Docker Desktop Windows.
  - D-02-05-03 Fixture alembic_cfg scope=function + monkeypatch.setenv — moi test co env vars rieng + get_settings.cache_clear() invalidate @lru_cache khi DSN doi giua test. Tranh truong hop test thu N+1 nhin thay settings cu cua test thu N.
  - D-02-05-04 Query pg_constraint filter bang conrelid + contype thay vi conname — Plan 02-01 NAMING_CONVENTION `"ck": "ck_%(table_name)s_%(constraint_name)s"` ap dung len explicit name `ck_documents_status_enum` Plan 02-04 -> double-prefix thanh `ck_documents_ck_documents_status_enum` trong DB thuc te. Test verify SPEC R4 (CHECK constraint co failed_unsupported) defensive, KHONG verify constraint name pattern.
  - D-02-05-05 Test expectation: `alembic_version` table SURVIVES `downgrade base` (behavior chuan Alembic — version tracking table cannot tu drop chinh no). Assert ['alembic_version'] + count(*)=0 thay vi 0 row total. 10 bang app PHAI bi drop sach.
  - D-02-05-06 Makefile target migrate-* dung literal `uv run alembic ...` (KHONG `$(UV) run ...`) — match acceptance criteria grep exact + plan paste-ready spec. Phase 1 target install/lint/test giu `$(UV) run` (consistency cu).
metrics:
  duration_minutes: 12
  tasks_completed: 5
  files_created: 5
  files_modified: 3
  commits: 6
  pytest_passed: 7
  completed_date: 2026-05-13
requirements_covered:
  - CORE-02 (full — 5 ROADMAP success criteria Phase 2 da verified runtime tren testcontainers pgvector pg16; xem Truths section)
---

# Phase 2 Plan 05: Verify Suite — testcontainers + Makefile migrate-* — Summary

## One-liner

7 pytest integration test (testcontainers `pgvector/pgvector:pg16`) verify 5 ROADMAP Phase 2 success criteria — Criteria #1 (10 bang baseline tao OK), #2 (HNSW vector_cosine_ops + P17 mitigation), #3 (downgrade clean — chi alembic_version survives chuan), #4 (documents.status CHECK enum bao gom failed_unsupported — R4 mitigation), #5 (P7 cocoindex schema isolation — Alembic include_object filter ignore), bonus R1 hard verify (chunks.vector la vector(1536) qua pg_attribute format_type) + P20 hard verify (alembic check no drift sau upgrade head) — 3 Makefile target migrate-up/down/check de dev shortcut + Phase 10 CI gate hook.

## What was built

5 file mới + 3 file modified trong `Hub_All/api/`:

| File | Loai | Muc dich |
|---|---|---|
| `Makefile` | modified | Them 3 target migrate-up/down/check + migrate-history (Phase 1 target install/lint/test giu nguyen) |
| `pyproject.toml` | modified | Them 2 dev deps testcontainers[postgres]>=4.7,<5 + psycopg2-binary>=2.9,<3 |
| `uv.lock` | modified | Resolved 118 packages, installed 6 new (testcontainers 4.14.2, docker 7.1.0, psycopg2-binary 2.9.12, pywin32 311, wrapt 2.1.2) |
| `tests/integration/__init__.py` | created | Empty package marker |
| `tests/integration/conftest.py` | created | Source-of-truth 2 fixture share giua 3 file test |
| `tests/integration/test_migration_upgrade_downgrade.py` | created | 2 test verify Criteria #1 + #3 |
| `tests/integration/test_chunks_hnsw_cosine_ops.py` | created | 3 test verify Criteria #2 + #4 + R1 |
| `tests/integration/test_alembic_ignores_cocoindex_schema.py` | created | 2 test verify Criteria #5 + P20 |

**Fixture architecture (conftest.py source-of-truth):**

1. **`postgres_container` (scope=module)** — `PostgresContainer("pgvector/pgvector:pg16", driver=None)` + `CREATE EXTENSION IF NOT EXISTS vector` + `CREATE EXTENSION IF NOT EXISTS pgcrypto`. Yield container — share giua test trong cung file (tranh spin-up 3s/lan).
2. **`alembic_cfg` (scope=function)** — `monkeypatch.setenv` 4 env vars (DATABASE_URL async + COCOINDEX/REDIS/APP_ENV) + `get_settings.cache_clear()` invalidate `@lru_cache` + return `alembic.config.Config("alembic.ini")`. Per-test isolation.

**Test suite breakdown (7 test, 3 file):**

| File | Test | Verifies | Mitigation |
|---|---|---|---|
| test_migration_upgrade_downgrade.py | test_upgrade_creates_10_tables | 11 bang sau upgrade head (10 app + alembic_version) | Criteria #1 |
| test_migration_upgrade_downgrade.py | test_downgrade_drops_all_clean | downgrade base xoa 10 bang app, alembic_version van con (rong) | Criteria #3 |
| test_chunks_hnsw_cosine_ops.py | test_chunks_vector_hnsw_uses_cosine_ops | indexdef contains 'USING hnsw' + 'vector_cosine_ops' | Criteria #2 + P17 |
| test_chunks_hnsw_cosine_ops.py | test_chunks_vector_column_is_1536_dim | format_type tra ve 'vector(1536)' | R1 (pgvector 2000-dim limit) |
| test_chunks_hnsw_cosine_ops.py | test_documents_status_enum_includes_failed_unsupported | CHECK constraint co ca 5 status value (incl failed_unsupported) | Criteria #4 + R4 |
| test_alembic_ignores_cocoindex_schema.py | test_upgrade_does_not_touch_cocoindex_schema | cocoindex.fake_state van nguyen sau upgrade head | Criteria #5 + P7 |
| test_alembic_ignores_cocoindex_schema.py | test_alembic_check_no_drift_after_upgrade | command.check(cfg) KHONG raise CommandError | P20 |

## Tasks executed

| # | Task | Commit | Files |
|---|---|---|---|
| 01 | Append 3 migrate-* target vao Makefile | `df2d5c9` | `Hub_All/api/Makefile` |
| 02 | conftest.py + dev deps testcontainers + psycopg2-binary + uv sync | `8092eb8` | `pyproject.toml`, `uv.lock`, `tests/integration/__init__.py`, `tests/integration/conftest.py` |
| 03 | test_migration_upgrade_downgrade.py — 2 test Criteria #1 + #3 | `888cf89` | `tests/integration/test_migration_upgrade_downgrade.py` |
| 04 | test_chunks_hnsw_cosine_ops.py — 3 test Criteria #2 + #4 + R1 | `5b278a8` | `tests/integration/test_chunks_hnsw_cosine_ops.py` |
| 05 | test_alembic_ignores_cocoindex_schema.py — 2 test Criteria #5 + P20 | `b274e32` | `tests/integration/test_alembic_ignores_cocoindex_schema.py` |
| Rule 1 fix | Fix 2 test FAIL: constraint query naming + downgrade leaves alembic_version | `adc844b` | `tests/integration/test_chunks_hnsw_cosine_ops.py`, `tests/integration/test_migration_upgrade_downgrade.py` |

Tong cong **6 commit code** atomic (5 task + 1 Rule 1 fix).

## Verification

Tat ca lenh verification cuoi plan da pass:

```bash
$ cd Hub_All/api && grep -cE "^migrate-up:$" Makefile
1
$ cd Hub_All/api && grep -cE "^migrate-down:$" Makefile
1
$ cd Hub_All/api && grep -cE "^migrate-check:$" Makefile
1

$ cd Hub_All/api && grep -c "testcontainers" pyproject.toml
3
$ cd Hub_All/api && grep -c "psycopg2-binary" pyproject.toml
1

$ ls Hub_All/api/tests/integration/
__init__.py
conftest.py
test_alembic_ignores_cocoindex_schema.py
test_chunks_hnsw_cosine_ops.py
test_migration_upgrade_downgrade.py

$ cd Hub_All/api && uv run pytest tests/integration/ -v -m critical
============================= test session starts =============================
collected 7 items

tests/integration/test_alembic_ignores_cocoindex_schema.py::test_upgrade_does_not_touch_cocoindex_schema PASSED
tests/integration/test_alembic_ignores_cocoindex_schema.py::test_alembic_check_no_drift_after_upgrade PASSED
tests/integration/test_chunks_hnsw_cosine_ops.py::test_chunks_vector_hnsw_uses_cosine_ops PASSED
tests/integration/test_chunks_hnsw_cosine_ops.py::test_chunks_vector_column_is_1536_dim PASSED
tests/integration/test_chunks_hnsw_cosine_ops.py::test_documents_status_enum_includes_failed_unsupported PASSED
tests/integration/test_migration_upgrade_downgrade.py::test_upgrade_creates_10_tables PASSED
tests/integration/test_migration_upgrade_downgrade.py::test_downgrade_drops_all_clean PASSED

======================== 7 passed, 9 warnings in 9.19s ========================

$ cd Hub_All/api && uv run ruff check tests/integration
All checks passed!
```

**7/7 test PASS in 9.19s** (lan thu 2 sau Rule 1 fix). Image `pgvector/pgvector:pg16` pre-pulled 1 lan (~200MB), test runs nhanh sau do.

## Truths achieved (6 Must-Haves)

- ✓ **Truth 1:** `make migrate-up` chay `uv run alembic upgrade head` thanh cong (Criteria #1) — verified Makefile target ton tai, grep counts pass.
- ✓ **Truth 2:** `test_upgrade_creates_10_tables` PASS — 11 row trong information_schema.tables (10 app + alembic_version), match expected list.
- ✓ **Truth 3:** `test_downgrade_drops_all_clean` PASS — public schema chi con `alembic_version` rong (behavior chuan Alembic), 10 bang app drop sach.
- ✓ **Truth 4:** `test_chunks_vector_hnsw_uses_cosine_ops` PASS — pg_indexes.indexdef contains 'USING hnsw' + 'vector_cosine_ops' (Criteria #2, P17 mitigation hard verify).
- ✓ **Truth 5:** `test_chunks_vector_column_is_1536_dim` PASS — format_type(atttypid, atttypmod) tra ve 'vector(1536)' (R1 mitigation hard verify).
- ✓ **Truth 6:** `test_documents_status_enum_includes_failed_unsupported` PASS — CHECK constraint co ca 5 status values bao gom failed_unsupported (Criteria #4, R4 mitigation).
- ✓ **Truth 7 (bonus):** `test_upgrade_does_not_touch_cocoindex_schema` PASS — cocoindex.fake_state van nguyen sau upgrade head (Criteria #5, P7 mitigation).
- ✓ **Truth 8 (bonus):** `test_alembic_check_no_drift_after_upgrade` PASS — alembic check KHONG raise CommandError sau upgrade head (P20 mitigation).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed test query for CHECK constraint naming**

- **Found during:** First pytest run sau Task 05 commit
- **Issue:** `pg_constraint WHERE conname='ck_documents_status_enum'` tra ve None vi Plan 02-01 `NAMING_CONVENTION` template `"ck": "ck_%(table_name)s_%(constraint_name)s"` ap dung len explicit name `ck_documents_status_enum` Plan 02-04 -> double-prefix thanh `ck_documents_ck_documents_status_enum` trong DB thuc te.
- **Fix:** Thay query thanh `WHERE conrelid='public.documents'::regclass AND contype='c'` + iterate de tim constraint chua 'status' va 'failed_unsupported'. Test verify SPEC R4 (CHECK exist + 5 status values), KHONG depend ten constraint cu the.
- **Files modified:** `tests/integration/test_chunks_hnsw_cosine_ops.py`
- **Commit:** `adc844b`

**2. [Rule 1 - Test Expectation] Fixed downgrade test expectation cho alembic_version**

- **Found during:** First pytest run sau Task 05 commit
- **Issue:** Test cu assert `len(rows) == 0` sau `downgrade base` — sai vi Alembic LEAVES table `alembic_version` (behavior chuan — version tracking table cannot tu drop chinh no).
- **Fix:** Assert `table_names == ['alembic_version']` + `count(*) FROM alembic_version == 0` (alembic_version rong, KHONG tracked revision). 10 bang app PHAI bi drop sach.
- **Files modified:** `tests/integration/test_migration_upgrade_downgrade.py`
- **Commit:** `adc844b`

## Deferred Issues (passed to next plan)

**Plan 02-04 migration explicit name double-prefix bug (pre-existing — NOT introduced by Plan 02-05):**

- **Issue:** Migration 0001_initial_schema.py Plan 02-04 truyen explicit name `name="ck_documents_status_enum"` + `name="ck_users_role_enum"` cho `sa.CheckConstraint(...)`. Plan 02-01 setup `NAMING_CONVENTION["ck"] = "ck_%(table_name)s_%(constraint_name)s"` tren MetaData se TIEP TUC apply prefix `ck_<table>_` len explicit name -> ket qua trong DB la `ck_documents_ck_documents_status_enum` (double prefix).
- **Impact:** Constraint VAN exist + enforce dung — chi ten dai vo nghia. KHONG ngan migration work, KHONG affect data integrity.
- **Recommended fix:** Plan 03-XX hoac next phase — sua migration 0001 explicit name thanh `name="status_enum"` + `name="role_enum"` (de NAMING_CONVENTION tu bac `ck_documents_` prefix). Sau khi sua, ten dung se la `ck_documents_status_enum` + `ck_users_role_enum`.
- **Scope reason:** Plan 02-05 muc tieu verify suite — KHONG sua migration code (out of scope). Test workaround filter bang conrelid+contype thay conname (defensive, KHONG depend ten cu the).

## Authentication Gates

KHONG co auth gate trong plan nay — testcontainers tu spawn Postgres local, KHONG can credentials/token/CLI login.

## Threat Model Bake (R1/R4 + P7/P17/P20)

| ID | Mitigation Verified | Test | Result |
|---|---|---|---|
| **R1** (HIGH pgvector 2000-dim limit) | `chunks.vector` la `vector(1536)` | `test_chunks_vector_column_is_1536_dim` | PASS — format_type tra ve 'vector(1536)' |
| **R4** (HIGH scanned PDF silent fail) | CHECK constraint co `failed_unsupported` | `test_documents_status_enum_includes_failed_unsupported` | PASS — 5/5 status values present trong constraint def |
| **P7** (MED CocoIndex schema isolation) | env.py include_object filter ignore schema 'cocoindex' | `test_upgrade_does_not_touch_cocoindex_schema` | PASS — cocoindex.fake_state row 'baseline' van nguyen sau upgrade head |
| **P17** (MED cosine vs L2 metric mismatch) | HNSW index dung `vector_cosine_ops` | `test_chunks_vector_hnsw_uses_cosine_ops` | PASS — indexdef contains 'USING hnsw' + 'vector_cosine_ops' literal |
| **P20** (MED Alembic baseline drift) | `alembic check` no drift sau upgrade head | `test_alembic_check_no_drift_after_upgrade` | PASS — command.check(cfg) KHONG raise CommandError |

## Key Decisions Made

1. **D-02-05-01 Image pin `pgvector/pgvector:pg16` (KHONG postgres:16-alpine)** — Alpine khong co binary pgvector → CREATE EXTENSION vector se fail. Image official ~200MB nhung pre-pulled 1 lan, sau do test runs 9-18s tren Docker Desktop Windows.
2. **D-02-05-02 Fixture postgres_container scope=module thay vi scope=session** — Moi file test co container rieng tranh side-effect (vd test_alembic_ignores_cocoindex_schema tao schema cocoindex se leak vao module khac neu shared session). Trade-off: 3 container/run thay vi 1.
3. **D-02-05-03 alembic_cfg scope=function + monkeypatch.setenv + get_settings.cache_clear()** — Moi test co env vars + settings rieng, tranh truong hop test thu N+1 nhin thay settings cu cua test thu N (vi `@lru_cache` tren `get_settings()`).
4. **D-02-05-04 Query pg_constraint bang conrelid+contype thay vi conname** — Defensive cho NAMING_CONVENTION double-prefix bug Plan 02-01+02-04. Verify SPEC (CHECK exists + content) thay vi name pattern.
5. **D-02-05-05 alembic_version SURVIVES downgrade base la behavior chuan Alembic** — Adjust test expectation: assert `['alembic_version']` + `count(*)=0` (rong revision tracked). 10 bang app PHAI bi drop sach.
6. **D-02-05-06 Makefile target migrate-* dung literal `uv run` thay vi `$(UV) run`** — Match acceptance criteria grep exact + plan paste-ready spec. Phase 1 target install/lint/test giu `$(UV) run` (consistency cu).

## Requirements Coverage

- **CORE-02 (Database foundation):** FULL COMPLETE — 5 ROADMAP success criteria Phase 2 da verified runtime tren testcontainers `pgvector/pgvector:pg16`:
  - Criteria #1: 10 bang baseline tao OK ✓ (test_upgrade_creates_10_tables PASS)
  - Criteria #2: HNSW `vector_cosine_ops` build OK ✓ (test_chunks_vector_hnsw_uses_cosine_ops PASS)
  - Criteria #3: downgrade clean ✓ (test_downgrade_drops_all_clean PASS — chi alembic_version survives chuan)
  - Criteria #4: documents.status enum bao gom failed_unsupported ✓ (test_documents_status_enum_includes_failed_unsupported PASS)
  - Criteria #5: Alembic KHONG touch schema cocoindex ✓ (test_upgrade_does_not_touch_cocoindex_schema PASS)
  - Bonus R1: chunks.vector la vector(1536) ✓ (test_chunks_vector_column_is_1536_dim PASS)
  - Bonus P20: alembic check no drift ✓ (test_alembic_check_no_drift_after_upgrade PASS)

## Notes for Next Plans

- **Phase 3 (Auth):**
  - Schema `users` + `refresh_tokens` da verified runtime — san sang impl login/JWT/refresh token rotation.
  - `users.password_hash` la `TEXT NOT NULL` (KHONG VARCHAR(N)) — match Argon2 variable length string.
  - `refresh_tokens.token_hash` UNIQUE — T-02-03 mitigation (KHONG luu plaintext token).
- **Phase 4 (CocoIndex Ingest):**
  - `documents.status` CHECK enum verified bao gom `failed_unsupported` — Phase 4 worker se UPDATE status nay khi gap scanned PDF.
  - `documents.last_heartbeat` san sang cho watchdog cron 1-min check (P8 mitigation).
  - `chunks.vector` la `vector(1536)` verified + HNSW vector_cosine_ops ready — embedding OpenAI text-embedding-3-small (dim=1536 param) hoac Gemini text-embedding-004 (dim=1536) hot-swap KHONG can re-embed (R7).
  - CocoIndex flow PHAI dung schema 'cocoindex' (KHONG public) — P7 verified alembic include_object filter exclude.
- **Phase 10 (Hardening + Observability):**
  - testcontainers pattern + @pytest.mark.critical marker da establish — scale ra full integration suite cho auth/ingest/search/ask/hub_isolation (HARD-03 ≥50% critical path).
  - Plan 02-05 contribute 7/N test critical-path — kiểm tra `pytest -m critical` PASS la CI gate baseline.
- **Plan 03-XX hoac next migration plan (deferred bug fix):**
  - Sua migration 0001_initial_schema.py: thay `sa.CheckConstraint(..., name="ck_documents_status_enum")` -> `name="status_enum"` va `name="ck_users_role_enum"` -> `name="role_enum"`. NAMING_CONVENTION se tu bac `ck_<table>_` prefix dung 1 lan.
  - Sau khi sua, test `test_documents_status_enum_includes_failed_unsupported` co the rerun voi query `WHERE conname='ck_documents_status_enum'` simple lai.

## Self-Check: PASSED

**Files verified exist:**
- ✓ `Hub_All/api/Makefile` (modified — 3 target migrate-* them moi)
- ✓ `Hub_All/api/pyproject.toml` (modified — 2 dev deps them moi)
- ✓ `Hub_All/api/uv.lock` (modified — 6 package install)
- ✓ `Hub_All/api/tests/integration/__init__.py` (empty package marker)
- ✓ `Hub_All/api/tests/integration/conftest.py` (88 dong, 2 fixture)
- ✓ `Hub_All/api/tests/integration/test_migration_upgrade_downgrade.py` (96 dong, 2 test)
- ✓ `Hub_All/api/tests/integration/test_chunks_hnsw_cosine_ops.py` (139 dong, 3 test)
- ✓ `Hub_All/api/tests/integration/test_alembic_ignores_cocoindex_schema.py` (92 dong, 2 test)

**Commits verified in git log:**
- ✓ `df2d5c9` — feat(phase-02): make(migrate): them 3 target migrate-up/down/check + migrate-history
- ✓ `8092eb8` — feat(phase-02): tests(integration): conftest.py share fixture postgres_container + alembic_cfg
- ✓ `888cf89` — feat(phase-02): tests(integration): test_migration_upgrade_downgrade — 2 test verify schema baseline
- ✓ `5b278a8` — feat(phase-02): tests(integration): test_chunks_hnsw_cosine_ops — 3 test verify R1/R4/P17
- ✓ `b274e32` — feat(phase-02): tests(integration): test_alembic_ignores_cocoindex_schema — 2 test verify P7+P20
- ✓ `adc844b` — fix(phase-02): tests(integration): Rule 1 fix 2 test assertion sai expectation

**Verification commands all exit 0:**
- ✓ `make migrate-up/down/check` targets ton tai + recipe dung `uv run alembic ...` literal
- ✓ `testcontainers[postgres]` + `psycopg2-binary` resolved + installed qua `uv sync --extra dev`
- ✓ 5 file tests/integration/ ton tai (init + conftest + 3 test files)
- ✓ Image `pgvector/pgvector:pg16` pin trong conftest.py (5 refs) + test_migration_upgrade_downgrade.py (1 ref) = 6 references total
- ✓ `uv run pytest tests/integration/ -v -m critical` exits 0: 7 passed in 9.19s
- ✓ `uv run ruff check tests/integration`: All checks passed
- ✓ 0 redundant fixture redeclare trong 3 test file (verified grep `def postgres_container` + `def alembic_cfg` = 0 ngoai conftest.py)
