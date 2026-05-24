# Phase 4: Migration + smoke E2E (MIGRATE) — Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-24
**Phase:** 04-migration-smoke-e2e
**Mode:** auto (no interactive AskUserQuestion — Claude picked recommended defaults từ ROADMAP gray areas + prior phase patterns)
**Areas discussed:** Migration idempotent strategy, Rollback procedure, Smoke E2E live infra, Plan count, Audit forensic query, Closeout v3.1 SHIPPED

---

## Area 1: Migration idempotent strategy (GA-V3.1-C)

| Option | Description | Selected |
|---|---|---|
| **`sa.inspect()` introspect Python pre-condition** | Sử dụng SQLAlchemy `Inspector.get_check_constraints()` + `get_columns()` + COUNT(*) audit_logs check trong `upgrade()` 3 STEP. Skip nếu đã apply. | ✓ |
| PL/pgSQL `DO $$ ... IF NOT EXISTS` block | Vendor-locked Postgres syntax + harder test + harder read Python developer | |

**Selected:** introspect (ROADMAP recommendation + Plan 01-01 đã ship pattern này 2026-05-23 — Phase 4 verify-only carry forward).

**Notes:** Plan 04-01 KHÔNG re-implement migration 0006 — chỉ chạy test integration `test_migration_0006_idempotent.py` 5 test live DB qua `make test-integration` với `TEST_DATABASE_URL` set.

---

## Area 2: Rollback procedure (ROADMAP gray area #2)

| Option | Description | Selected |
|---|---|---|
| **`downgrade()` function full implement** | Reverse upgrade 3 STEP — DROP CHECK 4 value + ADD CHECK 3 value; DROP COLUMN user_hubs.role; DELETE audit_logs seed row. Defensive RuntimeError nếu role='hub_admin' exists. | ✓ |
| Document-only "DROP COLUMN ... + ALTER CHECK" | Anti-pattern — operator dễ quên, dựa memory + risk human error production | |

**Selected:** full implement (ROADMAP recommendation + Plan 01-01 đã ship đầy đủ 2026-05-23 với defensive RuntimeError E-V3.1-1 STOP trigger — Phase 4 verify-only carry forward).

**Notes:** Plan 04-01 chạy test `test_migration_0006_idempotent.py::test_downgrade_*` (2 test verify CHECK 3 value restored + column dropped + existing data preserve).

---

## Area 3: Smoke E2E live infra

| Option | Description | Selected |
|---|---|---|
| **pytest in-process `testcontainers`** | `PostgresContainer("pgvector/pgvector:pg16")` + `RedisContainer` + `asgi_lifespan` LifespanManager + `httpx.AsyncClient` ASGITransport. Existing conftest.py infrastructure proven. | ✓ |
| Real docker compose live | Slow CI + flaky port collision + harder debug + cần Docker Desktop running | |

**Selected:** in-process testcontainers (ROADMAP recommendation + carry forward Phase 1 v3.1 + Phase 2 v2.0 + Phase 7 v3.0 + Phase 4 v3.0 pattern).

**Notes:** Plan 04-02 reuse existing `postgres_container` + `redis_container` + `hub_app_factory("central")` fixture từ `tests/integration/conftest.py`. KHÔNG cần real docker compose.

---

## Area 4: Plan count (Claude codebase audit)

| Option | Description | Selected |
|---|---|---|
| **3 plan (Wave 1 verify + Wave 2 smoke E2E + Wave 3 closeout)** | Plan 04-01 verify migration; Plan 04-02 smoke 4 scenario; Plan 04-03 closeout 4 docs + git tag. Match ROADMAP "2-3 plans estimate". | ✓ |
| 2 plan (verify + closeout, smoke combined) | Quá ít — smoke 4 scenario phức tạp + audit query merit tách riêng | |

**Selected:** 3 plan (match ROADMAP estimate + carry forward Phase 1 v3.1 3 plan + Phase 3 v3.1 4 plan pattern).

**Notes:** Wave critical path linear (1 → 2 → 3) — KHÔNG parallel-able vì migration verify enable smoke E2E; smoke E2E enable closeout.

---

## Area 5: Audit forensic query approach (D-V3.1-Phase4-E)

| Option | Description | Selected |
|---|---|---|
| **SQL `payload->>'actor_role'` + `payload->>'actor_hub_id'` direct asyncpg** | Query Postgres trực tiếp sau scenario step qua `asyncpg.fetch(...)` — KHÔNG cần SQLAlchemy session overhead. Reuse `_wait_audit_row` poll helper conftest.py. | ✓ |
| SQLAlchemy ORM async session select | Overhead spin up session + transactional context; KHÔNG cần thiết cho assertion query đơn giản | |

**Selected:** direct asyncpg (carry forward Plan 02-04 + Plan 01-03 + Plan 04-01 v3.0 pattern).

**Notes:** Helper `_assert_audit_actor_metadata(conn, action, expected_role, expected_hub_id)` inline test file (extract conftest defer nếu reuse > 4 lần).

---

## Area 6: Closeout v3.1 SHIPPED (D-V3.1-Phase4-F)

| Option | Description | Selected |
|---|---|---|
| **git tag annotated `v3.1` local + 4 docs update atomic + CLAUDE.md milestone close note** | Carry forward v2.0 + v3.0 milestone close pattern. `git tag -a v3.1 -m "..."` KHÔNG push (operator decide). 4 docs: STATE + REQUIREMENTS + ROADMAP + CLAUDE. | ✓ |
| Auto push git tag + auto archive milestone | Premature — user retrospective + ưu tiên backlog quyết định trước `/gsd-complete-milestone v3.1` | |

**Selected:** local tag + 4 docs (pattern Phase 2 Plan 02-05 + Phase 3 Plan 03-04 + v3.0 Plan 07-05 carry forward).

**Notes:** Trailing CLAUDE.md `*Cập nhật:` line bump reflect v3.1 SHIPPED + 🎉 milestone close note. Archive `.planning/milestones/v3.1-rbac-hub-admin-archive/` defer `/gsd-complete-milestone v3.1` separate command. v4.0 milestone start defer user retrospective.

---

## Claude's Discretion

Plan-phase agent quyết định:
- Tên test file mới Plan 04-02: `test_smoke_e2e_v3_1_rbac.py` HOẶC `test_v3_1_rbac_smoke.py`.
- Fixture scope: `session` HOẶC `module` cho postgres_container (depends test isolation).
- Audit log assertion fixture: inline HOẶC extract `tests/integration/_helpers/audit.py` (reuse > 4 lần threshold).
- Pytest marker `@pytest.mark.critical` HOẶC `@pytest.mark.integration` HOẶC cả 2.
- Bonus `make test-migration` shortcut Makefile target — depends Makefile structure.
- Test seed inline trong file HOẶC fixture helper `_seed_v3_1_rbac_scenario`.

## Deferred Ideas

- HUMAN-UAT live runtime manual smoke 4 scenario → defer ops handover (carry forward Phase 6 v3.0 + Phase 3 Plan 03-04 v3.1 precedent).
- Performance benchmark cross-hub p95 < 1.5s live measure → defer v4.0 (E-V3-2 carry forward).
- Visual regression smoke 4 hub × 11 trang React → defer v4.0 ops handover.
- Push git tag v3.1 auto → defer operator decide (`git push origin v3.1` manual).
- Archive `.planning/milestones/v3.1-rbac-hub-admin-archive/` → defer `/gsd-complete-milestone v3.1` separate command.
- v4.0 milestone start → defer `/gsd-new-milestone v4.0` sau user retrospective.
- OAuth role mapping qua SSO group claim → defer v4.0.
- Multi-role 1 user trong cùng hub → defer v4.0 per-resource ACL.
- Per-resource ACL granular → defer v4.0.
- SMTP email reset-password → defer v4.0 (memory project_no_smtp_v4).
