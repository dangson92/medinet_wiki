---
phase: 05-document-version-history
plan: 01
subsystem: backend
tags: [backend, alembic, migration, schema, version-history, introspect, idempotent]
requires:
  - 0006_role_hub_admin.py (Plan 01-01 v3.1 — down_revision chain)
  - documents table (Plan 04-01 v2.0 0001_initial_schema — FK target document_id CASCADE)
  - users table (Plan 04-01 v2.0 0001_initial_schema — FK target created_by SET NULL)
  - DocumentVersionAPI interface (frontend/src/services/api.ts:599-615 — schema contract)
provides:
  - document_versions table (15 cột + UNIQUE doc_ver + INDEX document_id + CHECK change_type 4 value)
  - 0007 revision chain head sau 0006 (alembic upgrade head ship migration mới)
  - Schema contract BE ↔ FE LOCKED — Plan 05-02 service INSERT/SELECT/DELETE + Plan 05-03 router serialize response
affects:
  - Plan 05-02 service layer (snapshot + retention cleanup unblocked)
  - Plan 05-03 router 4 endpoint (response shape exact match DocumentVersionAPI)
  - Plan 05-04 RBAC test (test data fixture document_versions row seed)
  - Plan 05-05 closeout (STATE.md + REQUIREMENTS.md + ROADMAP.md + CLAUDE.md update)
tech-stack:
  added: []
  patterns:
    - "Alembic migration introspect (sa.inspect 3-STEP upgrade + defensive downgrade) — carry forward Plan 01-01 v3.1 0006"
    - "DSN injection SAFETY pattern (monkeypatch env DATABASE_URL + get_settings.cache_clear) — carry forward Plan 01-03 v3.1 Iter 1 fix I-01/I-02"
    - "testcontainers in-process integration test (Postgres pgvector/pgvector:pg16) — carry forward Plan 04-02 v3.1"
key-files:
  created:
    - Hub_All/api/migrations/versions/0007_document_versions.py
    - Hub_All/api/tests/integration/test_migration_0007_idempotent.py
  modified: []
decisions:
  - "D-V3.1-Phase5-G LOCKED: revision='0007' down_revision='0006' chain sau Plan 01-01 v3.1 ROLE-01..03"
  - "D-V3.1-Phase5-A LOCKED: file_hash TEXT nullable (SHA-256 hex 64-char) — Plan 05-02 dedupe key trong cùng document_id"
  - "D-V3.1-Phase5-B LOCKED: KHÔNG bảng document_version_chunks (defer v4.0); chunk_count INT cột metadata only"
  - "D-V3.1-Phase5-H LOCKED: CHECK change_type IN 4 value ('reupload','reextract','content_edit','restore')"
  - "Rule 1 Bug auto-fix: Test 1 CHECK constraint name lookup LIKE '%ck_document_versions_change_type' (naming convention app/db/base.py double-prefix runtime — pattern song song Plan 01-01 0006 ck_users_ck_users_role_enum)"
metrics:
  duration_min: ~18
  completed_date: 2026-05-26
  tasks_completed: 3
  files_created: 2
  files_modified: 0
  tests_added: 5
  tests_passed: 5
  test_duration_seconds: 6.54
---

# Phase 5 Plan 05-01: Document Versions Migration Summary

**One-liner:** Alembic 0007 ship bảng `document_versions` 15 cột exact match
frontend `DocumentVersionAPI` interface + 5 integration test PASS idempotent
+ DSN injection SAFETY pattern — Plan 05-02 service unblocked cho snapshot
semantics + retention CTE.

## Mục tiêu đạt được

VER-01 Phase 5 v3.1 — schema migration đầu tiên cho feature version-history.
Frontend `DocumentVersionHistory.tsx` đã ship trước (commit lịch sử),
user mở tab "Lịch sử phiên bản" trong DocumentPreview gặp `404` console
error vì BE chưa có endpoint `/api/documents/{id}/versions*`. Plan 05-01
= bước đầu BE catch-up; tạo schema sẵn sàng cho Plan 05-02 service +
Plan 05-03 router để FE typecheck pass khi BE response trả về.

## Deliverables

### 1. `Hub_All/api/migrations/versions/0007_document_versions.py` (~220 LOC)

**Header + metadata:**
- `revision: str = "0007"` + `down_revision: Union[str, None] = "0006"`
  (D-V3.1-Phase5-G LOCKED — chain sau Plan 01-01 v3.1 ship 0006_role_hub_admin).
- Docstring tiếng Việt nêu rõ purpose + 4 STEP upgrade + 5 mitigation
  (T-05-01-01..03 + R-V3.1-1 + carry forward Plan 01-01 v3.1 + Plan 04-01 v3.0).

**`upgrade()` — 4 STEP introspect:**
1. STEP 1 idempotent guard `sa.inspect().get_table_names()` skip CREATE TABLE
   nếu `document_versions` đã tồn tại.
2. STEP 2 precondition `RuntimeError` nếu `documents` table chưa tồn tại
   (fail loud, hint operator chạy `alembic upgrade head` sequential từ 0001).
3. STEP 3 precondition `RuntimeError` nếu `users` table chưa tồn tại.
4. STEP 4 `op.create_table("document_versions", ...)` 15 cột:
   - **PK + FK + monotonic + flag**: `id` UUID PK gen_random_uuid +
     `document_id` UUID FK CASCADE + `version_number` INT + `is_original` BOOL.
   - **File metadata snapshot**: `name` + `file_type` + `file_size` BIGINT +
     `file_path` + `file_hash` (NULL hex 64-char) + `extractor_used` (NULL) +
     `chunk_count` INT DEFAULT 0.
   - **Change tracking**: `change_type` TEXT + `change_note` (NULL) +
     `created_by` UUID FK SET NULL + `created_at` TIMESTAMPTZ NOW().
   - **Constraints**: UNIQUE `(document_id, version_number)` name
     `uq_document_versions_doc_ver` + CHECK `change_type IN (4 value)` name
     `ck_document_versions_change_type`.
   - **Index**: `ix_document_versions_document_id` cho list query GET
     /versions WHERE document_id = $1.

**`downgrade()` — 3 STEP defensive:**
1. STEP 1 introspect guard + log `SELECT COUNT(*) FROM document_versions`
   trước DROP (operator visibility — KHÔNG raise vì 0007 feature-additive).
2. STEP 2 `DROP INDEX IF EXISTS ix_document_versions_document_id` idempotent.
3. STEP 3 `op.drop_table("document_versions")` CASCADE auto-drop UNIQUE +
   CHECK + FK.

### 2. `Hub_All/api/tests/integration/test_migration_0007_idempotent.py` (~360 LOC)

**SAFETY DSN injection fixture `alembic_isolated_dsn`** (Plan 01-03 v3.1 Iter 1
fix I-01 + I-02 carry forward):
- `monkeypatch.setenv("DATABASE_URL", async_dsn)` + `get_settings.cache_clear()`
  — KHÔNG dùng `Config.set_main_option("sqlalchemy.url", ...)` vì env.py:185-191
  runtime override sqlalchemy.url từ `get_settings().database_url` → caller's
  set_main_option BỊ IGNORE → test apply migration vào DB `.env` (vd
  medinet_central thật) thay vì testcontainer, SAFETY BLOCKER data loss risk.
- DSN swap sang `/medinet_central` để pass Phase 1 v3.0 `_enforce_hub_dsn_match`
  validator (HUB_NAME=central default).

**5 test PASS in 6.54s** (testcontainers pgvector/pgvector:pg16 session-scope
reuse từ `conftest.py::postgres_container`):
1. `test_upgrade_creates_table_with_15_columns` — alembic upgrade head + assert
   table tồn tại + 15 cột exact match `DocumentVersionAPI` interface + UNIQUE
   constraint + INDEX + CHECK constraint.
2. `test_upgrade_idempotent_re_run` — alembic upgrade head × 2 lần → lần 2 PASS
   (introspect skip-guard idempotent).
3. `test_downgrade_drops_table` — alembic upgrade head + downgrade -1 → table +
   index bị DROP (assert `to_regclass IS NULL` + `pg_indexes` empty).
4. `test_unique_constraint_enforces_doc_ver` — INSERT 2 row cùng `(document_id,
   version_number)` → `asyncpg.exceptions.UniqueViolationError` raise.
5. `test_check_constraint_rejects_invalid_change_type` — INSERT row với
   `change_type='invalid_value'` → `asyncpg.exceptions.CheckViolationError` raise.

Mọi test `@pytest.mark.critical @pytest.mark.integration` — chạy qua
`make test-integration` (Plan 04-01 v3.1 ship).

## Commits

| Task | Commit  | Message                                                                                                       |
| ---- | ------- | ------------------------------------------------------------------------------------------------------------- |
| 1    | 5b73187 | feat(05-01): Alembic 0007 document_versions upgrade() — 15 cột + UNIQUE + INDEX + CHECK (VER-01 Task 1)       |
| 2    | 687dcfb | feat(05-01): Alembic 0007 document_versions downgrade() — defensive COUNT log + DROP atomic (VER-01 Task 2)   |
| 3    | eb903e2 | test(05-01): 5 integration test cho migration 0007 document_versions PASS (VER-01 Task 3)                    |

## Schema contract BE ↔ FE LOCKED

15 cột schema match exact `DocumentVersionAPI` interface
(`frontend/src/services/api.ts:599-615`):

| # | Cột BE (Postgres) | Type | NULL | Match FE field |
|---|-------------------|------|------|----------------|
| 1 | id | UUID PK | NOT NULL | id: string |
| 2 | document_id | UUID FK CASCADE | NOT NULL | document_id: string |
| 3 | version_number | INTEGER | NOT NULL | version_number: number |
| 4 | is_original | BOOLEAN DEFAULT false | NOT NULL | is_original: boolean |
| 5 | name | TEXT | NOT NULL | name: string |
| 6 | file_type | TEXT | NOT NULL | file_type: string |
| 7 | file_size | BIGINT | NOT NULL | file_size: number |
| 8 | file_path | TEXT | NOT NULL | file_path: string |
| 9 | file_hash | TEXT | NULL | file_hash?: string |
| 10 | extractor_used | TEXT | NULL | extractor_used?: string |
| 11 | chunk_count | INTEGER DEFAULT 0 | NOT NULL | chunk_count: number |
| 12 | change_type | TEXT CHECK 4 value | NOT NULL | change_type: Literal[4] |
| 13 | change_note | TEXT | NULL | change_note?: string |
| 14 | created_by | UUID FK SET NULL | NULL | created_by?: string |
| 15 | created_at | TIMESTAMPTZ DEFAULT NOW() | NOT NULL | created_at: string |

Plan 05-03 router serialize BE row → FE response shape exact match (KHÔNG cần
field renaming hoặc casing transform).

## Threat Model Coverage

| Threat ID | Disposition | Mitigation Ship |
|-----------|-------------|------------------|
| T-05-01-01 (Integrity FK orphan) | mitigate | FK document_id ON DELETE CASCADE + FK created_by ON DELETE SET NULL — verify runtime qua Plan 05-04 RBAC test (cross-hub document delete cascade clean). |
| T-05-01-02 (Tampering invalid change_type) | mitigate | CHECK constraint `change_type IN ('reupload','reextract','content_edit','restore')` enforce DB layer — Test 5 verified runtime asyncpg.CheckViolationError. |
| T-05-01-03 (DoS race condition duplicate version_number) | mitigate | UNIQUE `(document_id, version_number)` reject duplicate — Test 4 verified runtime asyncpg.UniqueViolationError. |
| T-05-01-04 (Repudiation migration audit) | accept | Plan 05-01 schema thuần — KHÔNG cần audit migration row (khác Plan 01-01 0006 có audit `migration.role_seed` vì RBAC milestone-level). Operator `alembic history` đủ. |
| T-05-01-05 (Info Disclosure COUNT log) | accept | Local dev terminal log — KHÔNG production logs. Count nguyên KHÔNG PII. Severity: VERY LOW. |
| T-05-01-06 (Elevation test DSN bypass) | mitigate | Plan 01-03 SAFETY pattern carry forward — monkeypatch env DATABASE_URL + get_settings.cache_clear() — KHÔNG dùng Config.set_main_option vì env.py:185-191 runtime override bypass. |
| R-V3.1-1 (downgrade safety) | mitigate | downgrade() defensive COUNT log + DROP atomic — Test 3 verified runtime upgrade + downgrade -1 round-trip. |

## Deviations from Plan

### Rule 1 — Bug auto-fix: CHECK constraint name lookup runtime double-prefix

**Found during:** Task 3 — Test 1 run 1 lần fail trên assertion CHECK constraint
name lookup `WHERE conname = 'ck_document_versions_change_type'` → row None.

**Root cause:** `Hub_All/api/app/db/base.py::NAMING_CONVENTION` định nghĩa
`"ck": "ck_%(table_name)s_%(constraint_name)s"`. Khi `op.create_table()` chạy
qua Alembic env.py với `target_metadata = Base.metadata`, SQLAlchemy áp dụng
naming convention lên tham số `name=` của `CheckConstraint`. Source migration
dùng `name="ck_document_versions_change_type"` → convention treat my name là
`%(constraint_name)s` token → final runtime conname là
`ck_document_versions_ck_document_versions_change_type` (double prefix).

**Evidence:** Pattern này song song Plan 01-01 0006 — log output show
`ck_users_ck_users_role_enum` thay vì `ck_users_role_enum` declared trong
0001 source code. Test 4 + 5 PASS confirm CHECK constraint thật sự được
apply runtime (chỉ tên là khác — semantic OK).

**Fix:** Test 1 đổi assertion từ `conname = '...'` → `conname LIKE
'%ck_document_versions_change_type'` resilient với cả 2 form (with/without
naming convention double prefix). Migration source giữ NGUYÊN `name="ck_..."`
theo plan acceptance criteria + consistency với 0001 + 0006 pattern.

**Files modified:** `Hub_All/api/tests/integration/test_migration_0007_idempotent.py`
(Test 1 line ~167-180 assertion update + comment giải thích naming convention
behavior).

**Commit:** eb903e2 (Task 3 ship gồm fix inline).

## Self-Check: PASSED

**Files created:**
- FOUND: `Hub_All/api/migrations/versions/0007_document_versions.py` (220 LOC).
- FOUND: `Hub_All/api/tests/integration/test_migration_0007_idempotent.py` (360 LOC).

**Commits:**
- FOUND: 5b73187 (Task 1 upgrade).
- FOUND: 687dcfb (Task 2 downgrade).
- FOUND: eb903e2 (Task 3 tests + Rule 1 fix).

**Test runtime:** 5 passed, 8 warnings, 6.54s (testcontainers
pgvector/pgvector:pg16 session-scope reuse).

**Success criteria satisfied:**
1. File 0007 compile Python OK (ast.parse exit 0). ✓
2. revision='0007', down_revision='0006' đúng chain sau Plan 01-01 v3.1. ✓
3. upgrade() CREATE TABLE 15 cột + UNIQUE + INDEX + CHECK. ✓
4. downgrade() DROP TABLE + DROP INDEX + defensive COUNT log. ✓
5. 5 integration test PASS. ✓
6. Schema exact match `DocumentVersionAPI` interface. ✓
7. Plan 05-02 service unblocked. ✓
