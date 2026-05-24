---
status: partial
phase: 01-rbac-schema-migration
source: [01-VERIFICATION.md]
started: 2026-05-24T08:50:00Z
updated: 2026-05-24T08:50:00Z
---

## Current Test

[awaiting human testing — defer Phase 4 MIGRATE-01 per ROADMAP scope]

## Tests

### 1. Integration test 5 case runtime với TEST_DATABASE_URL set
expected: 5/5 test PASS — CHECK accept hub_admin, idempotent re-run, user_hubs.role nullable, audit seed, downgrade restore CHECK 3 value
result: [pending — defer Phase 4 MIGRATE-01]

### 2. Alembic upgrade head live trên 4 DB (medinet_central + medinet_hub_dmd + medinet_hub_tdt + medinet_test)
expected: Migration 0006 apply OK trên cả 4 DB; re-run lần 2 SKIP qua introspect guard print log; audit_logs có row `action='migration.role_seed'` trên mỗi DB với payload migration_revision='0006' + admin_count + user_hubs_count + timestamp_utc
result: [pending — defer Phase 4 MIGRATE-01]

### 3. Downgrade -1 rollback + defensive RuntimeError E-V3.1-1 STOP path
expected: user_hubs.role column DROP OK; CHECK constraint users.role REJECT hub_admin (3 value cũ); restore head reapply 0006 OK. STOP path: INSERT user role='hub_admin' rồi downgrade → expect RuntimeError với message mention E-V3.1-1.
result: [pending — defer Phase 4 MIGRATE-01]

## Summary

total: 3
passed: 0
issues: 0
pending: 3
skipped: 0
blocked: 0

## Gaps

(Tất cả 3 item đều là known defer Phase 4 MIGRATE-01 theo ROADMAP scope — KHÔNG phải gap thực sự. Plan 01-03 explicit defer trong task description: "skip-if-no-DB pattern (Phase 4 MIGRATE-01 sẽ chạy bắt buộc qua make test-integration)".)

## Notes

- Carry forward pattern Plan 04-07 v3.0 (smoke checkpoint runtime SKIP pre-resolved — defer Phase 7 MIGRATE-05 full E2E). v3.1 áp dụng tương tự: integration test runtime defer Phase 4 MIGRATE-01.
- 18/18 must_haves từ 3 PLAN frontmatter ĐÃ VERIFY (xem `01-VERIFICATION.md`). 6 unit test pytest PASS (4-case ROLE-04 + 1 defensive + 1 str args coverage).
- Phase 4 (MIGRATE-01..02) sẽ chạy: idempotent verify + downgrade + smoke E2E 4 scenario (super_admin / hub_admin dmd / hub_admin tdt / viewer) + audit trail per-DB inspect.
- Operator có thể chạy ngay nếu muốn: `cd Hub_All/api && TEST_DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/medinet_test python -m pytest tests/integration/test_migration_0006_idempotent.py -x -v --tb=short`.
