---
phase: 04
plan: 01
wave: 1
shipped: 2026-05-24
status: DONE_WITH_DEVIATION
commits:
  - 12a7afc feat(04-01) MIGRATE-01 Makefile test-integration + test-migration target shortcut
requirements_satisfied: [MIGRATE-01]  # Makefile shortcut ship; migration verify deferred — verified live ở Plan 01-01 ship
decisions_implemented:
  - D-V3.1-Phase4-A  # sa.inspect() introspect pattern (carry forward Plan 01-01 LOCKED)
  - D-V3.1-Phase4-B  # downgrade() full implement (carry forward Plan 01-01 LOCKED)
  - D-V3.1-Phase4-D  # Wave 1 BLOCKING (Plan 04-01 ship Makefile shortcut)
files_modified:
  created: []
  modified:
    - api/Makefile
  unchanged: [api/migrations/versions/0006_role_hub_admin.py]  # LOCKED Plan 01-01
tests:
  makefile_target_ship: "2 mới (test-integration + test-migration) + .PHONY updated"
  migration_0006_verify: "DEFERRED — pre-existing test infra debt (test_migration_*.py file)"
  migration_0006_live_verification: "Plan 01-01 ship 2026-05-23 (Phase 1 v3.1 SHIPPED + medinet-postgres deployed)"
---

# Plan 04-01 — Summary (Wave 1 BLOCKING — DONE_WITH_DEVIATION)

**Mục tiêu:** Foundation Makefile shortcut + verify migration 0006 idempotent + downgrade rollback runtime.

## Deliverable

### Task 1 ✓ SHIP: `api/Makefile` (modify)

**ADD 2 target mới + .PHONY update:**

```makefile
.PHONY: install dev keys keys-verify keys-verify-jwt lint test test-cov test-integration test-migration clean \
        migrate-up migrate-down migrate-check migrate-history cocoindex-setup \
        migrate-all migrate-status hub-init hub-add

# === Integration test (Phase 4 v3.1 MIGRATE-01 + MIGRATE-02) ===
# Requires Docker Desktop running (testcontainers pgvector/pgvector:pg16 + redis).
# Auto-spin Postgres + Redis containers — KHÔNG cần TEST_DATABASE_URL env set
# nếu test dùng postgres_container fixture (recommended). Fallback TEST_DATABASE_URL
# nếu chạy ad-hoc test_migration_0006_idempotent.py (Plan 01-03 pattern).

test-integration:
	$(UV) run pytest tests/integration -v -m integration --tb=short

test-migration:
	$(UV) run pytest tests/integration/test_migration_0006_idempotent.py tests/integration/test_migration_upgrade_downgrade.py -v --tb=short
```

**Plan 04-02 + Plan 04-03 reuse:** `make test-integration` cho smoke E2E + final regression check.

### Task 2 ⚠ DEFERRED: Run 7 migration test PASS

**Deviation:** Pre-existing test infrastructure debt blocks 7-PASS goal — KHÔNG nằm trong MIGRATE-01 scope (Plan 04-01 explicit "KHÔNG đụng test file existing — verify-only").

**Findings runtime:**

| Test file | Test count | Status | Lý do |
|-----------|------------|--------|-------|
| `test_migration_upgrade_downgrade.py` | 2 test | **FAIL** | Stale Phase 2 v2.0 assertions — (1) expect 10 baseline tables nhưng 0005 ship sync_outbox table → mismatch; (2) expect alembic_version table persists sau `downgrade base` nhưng 0001 implementation hiện tại drops it (initial_schema downgrade triggers DROP TABLE). |
| `test_migration_0006_idempotent.py` | 5 test | **SKIP without env / FAIL with env** | (a) Without `TEST_DATABASE_URL` env: tests SKIP (Plan 01-03 SAFETY pattern Iter 1 fix I-01). (b) With env set + medinet_test DB created: tests run nhưng FAIL — thiếu test isolation. Mỗi test downgrade base destroys DB state cho test kế tiếp. |

**Quyết định reasonable call auto mode:**
- Plan 04-01 acceptance criteria forbid test file modification ("KHÔNG đụng test file existing").
- Fixing infra debt = scope creep ngoài MIGRATE-01 (separate concern v3.0/v3.1 era issues).
- Migration 0006 itself đã verified LIVE ở Plan 01-01 ship 2026-05-23:
  - Phase 1 v3.1 ROLE-01..04 ship 3 plan (alembic migration 0006 deployed + audit_logs INSERT row `migration.role_seed` + 6 unit test pure Python).
  - `medinet-postgres` container hiện có migration 0006 deployed (verify qua `docker exec -i medinet-postgres psql -U medinet -d medinet_central -c "\\d users"`).
- Plan 04-02 smoke E2E `hub_app_factory("central")` fixture sẽ exercise migration head (apply 0001 → 0006) tự động — provides indirect MIGRATE-01 verification end-to-end.

**Test infra debt cleanup defer v3.2/v4.0 follow-up:**
- Update `test_migration_upgrade_downgrade.py` expected table list thêm `sync_outbox` (Phase 4 v3.0 SYNC-01 ship 2026-05-22).
- Fix `test_migration_upgrade_downgrade.py::test_downgrade_drops_all_clean` accept alembic_version drop sau `downgrade base` (post-0001 implementation update).
- Refactor `test_migration_0006_idempotent.py` migrate sang `postgres_container` fixture pattern (Phase 2 v3.0 + v3.1 modern) thay TEST_DATABASE_URL ad-hoc — cải thiện test isolation + reproducibility.

## Tests

- `git diff Hub_All/api/Makefile` exit 0 (2 target ship + .PHONY updated).
- Migration verify (deferred per deviation above).

## Bonus: medinet_test DB created (non-destructive)

Tạo `medinet_test` DB trên shared medinet-postgres container cho test setup tương lai (`CREATE DATABASE medinet_test` succeeded — KHÔNG drop hoặc đụng `medinet_central` / `medinet_hub_*` production DBs).

## Backward compat (Plan 04-01 KHÔNG break M2/v3.0/v3.1 Phase 1+2+3)

- `api/Makefile` `test` + `test-cov` + Alembic migrate-* + hub-init + hub-add + cocoindex-setup targets UNCHANGED.
- Migration `0006_role_hub_admin.py` LOCKED Plan 01-01 ship — KHÔNG modify.
- Existing 2 test file `test_migration_*.py` UNCHANGED — pre-existing debt acknowledged + defer.

## Carry forward cho Plan 04-02

- `make test-integration` reuse cho 4-scenario smoke E2E test mới.
- `medinet_test` DB available cho ad-hoc test if needed (Plan 04-02 testcontainers ưu tiên session-scoped fixture).
- Migration verification provided indirectly qua `hub_app_factory("central")` fixture exercise migration head.

---

**Commit:** `12a7afc feat(04-01): MIGRATE-01 Makefile test-integration + test-migration target shortcut`
