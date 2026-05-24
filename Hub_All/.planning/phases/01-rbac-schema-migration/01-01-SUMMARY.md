---
phase: 01-rbac-schema-migration
plan: 01
subsystem: db-migration
tags: [rbac, alembic, schema, role-per-hub, idempotent]
requires:
  - migration-0001-baseline (ck_users_role_enum + user_hubs composite PK + audit_logs payload jsonb)
  - migration-0005-baseline (revision chain 0005 → 0006 head SHA uniform per-hub)
  - alembic-runtime (op.execute raw SQL + sa.inspect introspect pattern carry forward Plan 04-01)
provides:
  - rbac-schema-extension (CHECK constraint users.role 4 value + user_hubs.role nullable + audit seed row)
  - downgrade-defensive (RuntimeError guard role='hub_admin' count > 0)
  - idempotent-re-run (introspect-based skip ở 3 STEP)
affects:
  - users.role CHECK constraint (3 → 4 value, mở rộng KHÔNG xoá data)
  - user_hubs schema (+1 column role TEXT NULL + 1 CHECK constraint NULL-aware)
  - audit_logs (+1 seed row action='migration.role_seed', payload jsonb)
tech-stack:
  added: []
  patterns:
    - introspect-runtime-check (sa.inspect.get_check_constraints + get_columns)
    - raw-sql-op-execute (atomic DDL DROP+ADD cùng transaction)
    - idempotent-where-not-exists (audit_logs seed guard)
    - idempotent-if-not-exists (DDL double-guard concurrent race extreme)
    - defensive-runtime-error (downgrade guard data tồn tại)
key-files:
  created:
    - api/migrations/versions/0006_role_hub_admin.py
  modified: []
decisions:
  - "D-V3.1-01 honored: GIỮ tên enum 'admin' = super-admin toàn hệ thống; THÊM 'hub_admin' mới (KHÔNG rename)"
  - "D-V3.1-02 honored: user_hubs.role nullable default NULL (NULL = inherit users.role global)"
  - "GA-V3.1-C resolved: idempotent strategy = introspect (KHÔNG PL/pgSQL DO block) — đối xứng Plan 04-01"
  - "Constraint name introspect runtime (KHÔNG hardcode 'ck_users_role_enum' hay 'role_enum') — model auth.py vs migration 0001 discrepancy"
  - "audit_logs seed KHÔNG migration column mới — payload jsonb đủ chứa count + timestamp (D-V3-Phase4-C2 carry forward Plan 04-06)"
  - "Downgrade KHÔNG xoá audit seed row — audit trail forensic preserve dù rollback schema"
metrics:
  duration: ~20 phút
  completed: "2026-05-24"
  tasks_total: 3
  tasks_completed: 3
  files_created: 1
  files_modified: 0
---

# Phase 1 Plan 01-01: Alembic migration 0006 role_hub_admin Summary

Mở rộng schema RBAC v3.1 — CHECK constraint `users.role` thêm value `'hub_admin'` + thêm column `user_hubs.role` nullable + INSERT audit seed row qua migration Alembic idempotent introspect (đối xứng pattern Plan 04-01).

## Đã làm gì

Tạo 1 file Alembic migration `api/migrations/versions/0006_role_hub_admin.py` với 3 STEP `upgrade()` + 3 STEP `downgrade()` đối xứng nghiêm ngặt thứ tự FK + dependency. Áp dụng cho CẢ central + 3 hub con (schema users + user_hubs đồng nhất mọi DB theo D-V3-01 multi-DB topology) — KHÔNG skip-guard `current_database()` như Plan 04-01 (sync_outbox per-hub-only).

### `upgrade()` — 3 STEP

| # | REQ | Mô tả | Idempotent guard |
|---|-----|-------|------------------|
| 1 | ROLE-01 | DROP + ADD CHECK constraint `users.role` mở rộng 4 value (`admin|hub_admin|editor|viewer`); giữ NGUYÊN tên constraint cũ để downgrade restore chính xác | `if "hub_admin" in role_constraint_sqltext` skip; introspect runtime `inspector.get_check_constraints("users")` tìm constraint chứa `"role"` + `"admin"` + KHÔNG chứa `"status"` (phân biệt với `user_status_enum`) |
| 2 | ROLE-02 | `ALTER TABLE user_hubs ADD COLUMN IF NOT EXISTS role TEXT NULL DEFAULT NULL` + `ADD CONSTRAINT ck_user_hubs_role_enum CHECK (role IS NULL OR role IN (...))` — NULL-aware (PostgreSQL 3-value logic) | `if "role" in inspector.get_columns("user_hubs")` skip; defensive double-guard với `IF NOT EXISTS` ở DDL level chống concurrent race edge case |
| 3 | ROLE-03 | `INSERT INTO audit_logs (action='migration.role_seed', target_type='schema', payload=jsonb_build_object(...))` ghi `admin_count` + `user_hubs_count` + `migration_revision='0006'` + `timestamp_utc` + Vietnamese note | `WHERE NOT EXISTS (SELECT 1 FROM audit_logs WHERE action='migration.role_seed' AND payload->>'migration_revision'='0006')` — re-run upgrade head lần 2 KHÔNG dup |

### `downgrade()` — 3 STEP NGƯỢC + defensive check

| # | Mô tả | Defensive |
|---|-------|-----------|
| 0 | `SELECT COUNT(*) FROM users WHERE role='hub_admin'` qua `bind.execute().scalar()` (KHÔNG `op.execute` vì return None) | `RuntimeError` early-fail nếu count > 0 → E-V3.1-1 STOP trigger; operator phải clean manual (UPDATE / DELETE) trước khi rollback |
| 1 | `DROP CONSTRAINT IF EXISTS ck_user_hubs_role_enum` | IF EXISTS — idempotent re-run |
| 2 | `DROP COLUMN role` từ `user_hubs` (introspect check trước DROP) | Skip nếu column không tồn tại |
| 3 | Restore CHECK constraint `users.role` về 3 value (introspect tên hiện tại + DROP + ADD cùng tên) | Skip nếu constraint không tồn tại; KHÔNG xoá audit seed row (audit forensic preserve — D-V3-Phase4-C2 pattern) |

## Decisions Made

- **Idempotent strategy GA-V3.1-C — introspect (KHÔNG PL/pgSQL DO block):** Đối xứng Plan 04-01 (`0005_sync_outbox_per_hub.py`) — explicit raw SQL `op.execute()` cho CHECK constraint manipulation; `sa.inspect()` Python-level pre-condition check thay vì PL/pgSQL DO block (dễ debug + log Vietnamese-tagged `[0006]` operator visibility).
- **CHECK constraint name introspect runtime — model/migration discrepancy resolved:** Migration 0001 dùng `ck_users_role_enum` (source-of-truth); model SQLAlchemy `auth.py:54` dùng `role_enum` (autogenerate có thể tạo nhầm). Migration 0006 KHÔNG hardcode tên — introspect `inspector.get_check_constraints("users")` filter constraint chứa `"role"` + `"admin"` + KHÔNG chứa `"status"` (loại trừ `user_status_enum`). Giữ NGUYÊN tên gốc khi DROP + ADD → downgrade restore chính xác semantic baseline 0001.
- **audit_logs seed pattern carry forward — KHÔNG migration column mới:** `audit_logs.payload` JSONB nullable đã đủ chứa event metadata (count + timestamp + revision + note). Pattern song song Plan 04-06 (`sync.replay` audit). Re-run guard qua `WHERE NOT EXISTS` match `payload->>'migration_revision'='0006'`.
- **Downgrade KHÔNG xoá audit seed row:** Audit trail forensic preserve dù rollback schema — pattern D-V3-Phase4-C2 carry forward. Operator có thể manual `DELETE` nếu cần (out of scope migration).
- **Áp dụng CẢ central + 3 hub con (KHÔNG skip-guard):** Khác Plan 04-01 sync_outbox per-hub-only — RBAC schema cần unify mọi DB để hub con verify role local. Compatible với multi-DB topology D-V3-01.

## Verify Status — 3/3 task PASS

| # | Verify command | Result |
|---|----------------|--------|
| Task 1 | `python -c "import importlib.util; ...; assert m.revision == '0006' and m.down_revision == '0005'"` | ✅ `OK revision metadata + upgrade/downgrade present` |
| Task 1 | Acceptance: file tồn tại, revision metadata, `role IN ('admin', 'hub_admin', ...)` x2 (upgrade + downgrade comment-aware), `inspector.get_check_constraints("users")` x2 (upgrade + downgrade), `if "hub_admin" in (role_constraint_sqltext or "")` x1, `ALTER TABLE users (DROP|ADD) CONSTRAINT` x4, KHÔNG hardcode tên trong code logic (chỉ mention trong comment giải thích context), `noqa: UP` x4 ≥ 2 | ✅ PASS |
| Task 2 | `grep "ADD COLUMN IF NOT EXISTS role TEXT"` = 1, `grep "ck_user_hubs_role_enum"` = 3, `grep "role IS NULL OR role IN"` = 2, `inspector.get_columns("user_hubs")` = 2 (upgrade + downgrade), `python -c "import ast; ast.parse(...)"` | ✅ `OK ast.parse` exit 0 |
| Task 3 | `grep "migration.role_seed"` = 6, `grep "def downgrade"` = 1, `grep "WHERE NOT EXISTS"` = 3, `grep "RuntimeError"` = 5, `jsonb_build_object` = 2, `admin_count` = 5, `user_hubs_count` = 2, `ALTER TABLE user_hubs DROP COLUMN role` = 1, `CHECK (role IN ('admin', 'editor', 'viewer'))` = 1, `E-V3.1-1` = 4, `SELECT COUNT(*) FROM users WHERE role = 'hub_admin'` = 1 | ✅ PASS |

## Threat Model Coverage

6 STRIDE threat (T-01-01-01..06) trong Plan 01-01 đã mitigate:

| Threat ID | Disposition | Implementation |
|-----------|-------------|----------------|
| T-01-01-01 Tampering (CHECK DROP+ADD) | mitigate | Atomic transaction Alembic wrap BEGIN/COMMIT; introspect runtime tên constraint; RuntimeError early fail nếu DB state corrupt (constraint không tồn tại) |
| T-01-01-02 Integrity (user_hubs.role ADD COLUMN) | mitigate | NULL DEFAULT NULL → existing rows backfill NULL atomic Postgres ≥11 metadata-only O(1); CHECK constraint NULL-aware (`role IS NULL OR role IN ...`) |
| T-01-01-03 Repudiation (migration không trace) | mitigate | audit_logs seed row `action='migration.role_seed'` với jsonb_build_object payload (migration_revision + admin_count + user_hubs_count + timestamp_utc + note); idempotent WHERE NOT EXISTS guard |
| T-01-01-04 DoS (re-run upgrade head fail/loop) | mitigate | Introspect-based idempotent guard ở 3 STEP — re-run an toàn; print() log `[0006]` operator visibility step nào skip/apply |
| T-01-01-05 EoP (downgrade phá CHECK với role='hub_admin' tồn tại) | mitigate | Defensive RuntimeError ở downgrade() nếu COUNT(*) > 0 → E-V3.1-1 STOP trigger; operator phải clean manual; KHÔNG auto-delete data |
| T-01-01-06 Info Disclosure (audit seed leak count) | accept | count chỉ là số đếm KHÔNG PII; payload chỉ visible admin role qua audit_logs API (Phase 5 require_role("admin") guard carry forward) |

## Carry Forward Pattern (từ Plan 04-01)

- Explicit raw SQL `op.execute()` cho CHECK constraint manipulation — Alembic `op.create_check_constraint` tên không reliable across Postgres versions.
- `sa.inspect()` introspect runtime — Python-level pre-condition check + log Vietnamese-tagged operator debug.
- Vietnamese docstring threat model + idempotent semantic note rõ ràng cho operator + reviewer.
- `noqa: UP035 / UP007` typing imports baseline match Alembic template 0001-0005 (KHÔNG migrate sang `from typing import ... | ...`).

## Deviations from Plan

None — plan executed exactly as written. 3 task complete, tất cả acceptance criteria + verify command PASS.

## Stub Tracking

Không có stub. File 0006 là migration thuần — KHÔNG có placeholder UI / mock data / empty value.

## Phase 4 MIGRATE-01 follow-up

Phase 4 MIGRATE-01 sẽ verify runtime upgrade/downgrade idempotent:
- `alembic upgrade head` lần 1 → PASS apply 3 STEP.
- `alembic upgrade head` lần 2 → PASS skip 3 STEP (idempotent).
- `alembic downgrade -1` → PASS restore CHECK 3 value + drop column (audit row preserve).
- `alembic downgrade -1` với row `role='hub_admin'` tồn tại → RuntimeError E-V3.1-1 STOP.
- 4 DB (medinet_central + 3 hub con dmd/tdt + sample) đều apply migration 0006 thành công.

## Self-Check: PASSED

- File created: `Hub_All/api/migrations/versions/0006_role_hub_admin.py` — FOUND.
- Module import + revision metadata + upgrade/downgrade present — PASS (`python -c "import importlib.util; ..."` exit 0).
- AST parse — PASS (`python -c "import ast; ast.parse(...)"` exit 0).
- Tất cả grep checks (acceptance criteria Task 1+2+3) — PASS ≥ 1 occurrence mỗi pattern.
- KHÔNG hardcode tên constraint trong code logic (chỉ trong comment giải thích context model/migration discrepancy) — PASS.
- Commit hash sẽ điền sau khi commit (do flow `Write before commit`).
