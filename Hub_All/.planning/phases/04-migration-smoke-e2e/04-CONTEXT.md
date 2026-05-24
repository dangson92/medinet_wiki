---
phase: 04-migration-smoke-e2e
gathered: 2026-05-24
status: Ready for planning
source: ROADMAP gray-area recommendations + auto-mode codebase audit (Phase 1 Plan 01-01/01-03 migration 0006 pattern + Phase 7 v3.0 MIGRATE-05 5 bash script pattern + Phase 2 Plan 02-04 audit forensic chain carry forward)
---

# Phase 4: Migration + smoke E2E (MIGRATE) — Context

**Trigger:** Phase 3 v3.1 DONE 2026-05-24 (4 plan FE-01..04 ship — UserRole type alias + UserManagement form 3 option + Layout HubSwitcher + Manage modal disabled + 3 vitest test mới / 8 file 45 test PASS). v3.1 milestone progress 12/~15 plan · 13/15 REQ-ID consumed. Phase 4 = milestone closeout BLOCKING — verify migration 0006 idempotent + downgrade rollback + smoke E2E 4 scenario (super_admin / hub_admin dmd / hub_admin tdt / viewer) + audit log forensic chain + closeout docs v3.1 SHIPPED + git tag annotated.

**Auto-mode note:** `/gsd-discuss-phase 4` chạy trong `auto` mode (system reminder "Work without stopping" + project precedent Phase 1-3 v3.1 + Phase 4-7 v3.0). 3 gray area ROADMAP §"Discuss-phase gray areas" lock theo recommendation đã có (đều có evidence carry forward Phase 1 Plan 01-01 + Phase 7 v3.0 MIGRATE-05 + existing testcontainers infrastructure). Audit codebase phát hiện 3 decision phụ (D-V3.1-Phase4-D/E/F — plan count + audit forensic query + git tag + milestone closeout pattern) lock thêm.

<domain>
## Phase Boundary

**Trong scope Phase 4 (MIGRATE):**
- **MIGRATE-01:** Migration script idempotent re-run safety + rollback procedure full implement.
  - `alembic upgrade head` 2 lần liên tiếp PASS (Plan 01-01 đã ship introspect guard `sa.inspect()` 3 STEP upgrade — Plan 04-01 verify runtime live DB).
  - `alembic downgrade -1` rollback PASS — restore CHECK constraint 3 value `('admin', 'editor', 'viewer')` + drop `user_hubs.role` column; existing data preserve.
  - Defensive RuntimeError nếu `COUNT(*) WHERE users.role='hub_admin' > 0` (Plan 01-01 đã ship E-V3.1-1 STOP trigger).
  - Test integration `tests/integration/test_migration_0006_idempotent.py` (Plan 01-03 ship 5 test) + `test_migration_upgrade_downgrade.py` (Phase 2 v2.0 ship) — Phase 4 chạy bắt buộc qua `make test-integration` với `TEST_DATABASE_URL` live.

- **MIGRATE-02:** Smoke E2E 4 scenario qua pytest httpx + audit log inspect:
  - **(1) super admin `admin@medinet.vn`:** GET /api/hubs → ALL hubs (central + dmd + tdt); POST /api/users hub_id=any → 201.
  - **(2) hub_admin dmd:** GET /api/hubs → CHỈ `dmd` (filter central + tdt qua Plan 02-02 D-V3.1-Phase2-A LOCKED); POST /api/users hub_id=`dmd` → 201; POST /api/users hub_id=`tdt` → 403 HUB_ADMIN_REQUIRED envelope; GET /api/hubs/`central` → 403 hoặc filter ra empty.
  - **(3) hub_admin tdt:** Mirror (2) với hub `tdt` — GET /api/hubs → CHỈ `tdt`; cross-hub access dmd → 403.
  - **(4) viewer `viewer.dmd@medinet.vn`:** List documents trong hub `dmd` được gán → PASS; POST/PATCH /api/users → 403 FORBIDDEN (require_role super hoặc require_hub_admin reject).
  - Audit log inspect: 4 scenario operation `audit_logs` row có `payload->>'actor_role'` + `payload->>'actor_hub_id'` đúng (Plan 02-04 DEP-05 forensic chain carry forward).
  - Test infra: `testcontainers` PostgresContainer + RedisContainer + `asgi_lifespan` LifespanManager + `httpx.AsyncClient` (pattern carry forward Phase 1 conftest.py + Phase 7 v3.0 Plan 04-01 ship).

- **Closeout docs v3.1 SHIPPED:**
  - STATE.md frontmatter `completed_phases: 4` + `completed_plans: 15` + `percent: 100` + `milestone_status: SHIPPED` + `milestone_shipped_date: 2026-05-24` + `next_action: /gsd-complete-milestone v3.1` HOẶC `/gsd-new-milestone v4.0`.
  - REQUIREMENTS.md 2 dòng `[x] **MIGRATE-XX** ... (DONE 2026-05-24 — Plan 04-XX)`.
  - ROADMAP.md Phase 4 row DONE + plans checklist + milestone row v3.1 SHIPPED 100%.
  - CLAUDE.md §6 subsection mới `### Phase 4 v3.1 Migration + Smoke E2E pattern (MIGRATE-01..02 — 2026-05-24)` + v3.1 milestone closeout note (🎉 v3.1 MILESTONE CLOSED).
  - Git tag annotated `v3.1` qua `git tag -a v3.1 -m "v3.1 RBAC hub_admin SHIPPED 2026-05-24 — 4 phase / 15 REQ-ID / 15 plan"`.

**Ngoài scope (defer v4.0 / v4.1 backlog):**
- Role-per-resource ACL granular (documents.created_by filter cho viewer/editor read-only) — defer v4.0 per memory `project_rbac_hub_admin_gap`.
- SMTP email notification user vừa tạo (defer v4.0 per memory `project_no_smtp_v4`).
- OAuth role mapping qua SSO group claim — defer v4.0.
- Multi-role 1 user trong cùng hub (schema migration 0006 mỗi user_hubs row 1 role) — defer v4.0.
- Performance benchmark `cross-hub p95 < 1.5s` live measure — defer (carry forward v3.0 E-V3-2 mitigation; Phase 4 v3.1 chỉ check semantic 4 scenario PASS).
- Visual regression smoke 4 hub × 11 trang React (defer v4.0 ops handover carry forward Phase 5 v3.0).
- Per-hub user DELETE cascade `user_hubs` row khi DELETE user (existing M2 behavior preserve).
- `actor_hub_id` UUID resolution từ slug (hub_admin truyền `hub_id` string '<dmd-uuid>' qua body — KHÔNG slug; carry forward Plan 02-04 contract).

</domain>

<decisions>
## Implementation Decisions (LOCKED)

### D-V3.1-Phase4-A — Migration idempotent strategy = `sa.inspect()` introspect (KHÔNG PL/pgSQL `DO $$ ... IF NOT EXISTS` block)

**Recommendation từ ROADMAP §"Discuss-phase gray areas" GA-V3.1-C:** Introspect Python pre-condition (KHÔNG đụng PL/pgSQL nhiều).

**Lý do LOCKED:**
- **Plan 01-01 đã ship pattern này 2026-05-23** — migration `0006_role_hub_admin.py` upgrade() 3 STEP có introspect guard:
  - STEP 1: `sa.inspect(conn).get_check_constraints("users")` find tên constraint hiện tại (chống discrepancy `ck_users_role_enum` migration 0001 vs `role_enum` model auth.py) → DROP + ADD CHECK 4 value qua raw SQL.
  - STEP 2: `sa.inspect(conn).get_columns("user_hubs")` check `role` column tồn tại — skip ADD nếu đã có.
  - STEP 3: SELECT COUNT(*) FROM audit_logs WHERE action='migration.role_seed' → skip INSERT nếu đã chạy.
- Pattern proven: Phase 1 carry forward Plan 04-01 v3.0 ship `0005_sync_outbox_per_hub.py` (introspect column + trigger).
- PL/pgSQL `DO $$ ... IF NOT EXISTS` block khả thi NHƯNG vendor-locked Postgres syntax + harder to test + harder to read Python developer; introspect Python pattern aligned với codebase convention (CLAUDE.md §3 stack pin).
- **Phase 4 KHÔNG re-implement migration** — chỉ verify runtime live DB qua test integration `test_migration_0006_idempotent.py` chạy `alembic upgrade head` 2 lần + assert KHÔNG fail + KHÔNG duplicate audit_logs row.

**Impact downstream:**
- Plan 04-01: ADD `make test-integration` target HOẶC pytest test bắt buộc chạy `TEST_DATABASE_URL=<live> pytest tests/integration/test_migration_0006_idempotent.py -v` PASS — 5 test existing cover 4 success criteria ROADMAP Phase 1 + 1 audit seed row check.
- Plan 04-01 KHÔNG sửa migration `0006_role_hub_admin.py` (LOCKED Plan 01-01 ship).

### D-V3.1-Phase4-B — Rollback procedure = `downgrade()` function full implement (KHÔNG document-only)

**Recommendation từ ROADMAP §"Discuss-phase gray areas":** Implement (Phase 1 carry forward Alembic 0005 v3.0 Plan 04-01 pattern).

**Lý do LOCKED:**
- **Plan 01-01 đã ship downgrade() đầy đủ 2026-05-23** với defensive RuntimeError nếu `COUNT(*) FROM users WHERE role='hub_admin' > 0` (E-V3.1-1 STOP trigger — bảo vệ data loss khi production có hub_admin user).
- `downgrade()` 3 STEP reverse upgrade():
  - STEP 1: DROP CHECK constraint 4 value + RE-ADD CHECK 3 value `('admin', 'editor', 'viewer')` (introspect tên constraint giống upgrade).
  - STEP 2: DROP COLUMN `user_hubs.role` (existing rows trong `user_hubs` KHÔNG ảnh hưởng — column nullable, drop safe).
  - STEP 3: DELETE FROM audit_logs WHERE action='migration.role_seed' (idempotent cleanup — KHÔNG bắt buộc nhưng nếu downgrade chained thì OK).
- Document-only rollback (CLAUDE.md note "to drop column manually") = anti-pattern — operator dễ quên, lệ thuộc memory + risk human error production. Implementation đầy đủ + integration test verify = source-of-truth.
- **Phase 4 verify runtime** — chạy `alembic downgrade -1` qua test integration + assert CHECK 3 value restored + column dropped + existing user row preserve.

**Impact downstream:**
- Plan 04-01 chạy test `test_migration_0006_idempotent.py::test_downgrade_restores_check_3_value` + `test_migration_0006_idempotent.py::test_downgrade_drops_user_hubs_role_column` (Plan 01-03 ship 2 test này — verify-only).
- Plan 04-01 KHÔNG sửa downgrade() function (LOCKED Plan 01-01 ship).

### D-V3.1-Phase4-C — Smoke E2E live infra = pytest in-process `testcontainers` (KHÔNG real docker compose)

**Recommendation từ ROADMAP §"Discuss-phase gray areas":** in-process (faster + reproducible CI).

**Lý do LOCKED:**
- **Existing infrastructure proven 2026-05-23+** — `tests/integration/conftest.py` đã có:
  - `postgres_container` fixture với `PostgresContainer("pgvector/pgvector:pg16", driver=None)`.
  - `redis_container` fixture với `RedisContainer()`.
  - `asgi_lifespan` LifespanManager pattern.
  - `httpx.AsyncClient` pattern.
  - `hub_app_factory` fixture Phase 2 v3.0 FACTOR-01..03 cho multi-hub testing.
- Pattern carry forward Phase 7 v3.0 Plan 04-01 + 04-05 (cross-hub search refactor + sync worker integration) + Phase 1 v3.1 Plan 01-03 (migration 0006 idempotent).
- Real docker compose live = slow CI + flaky port collision + harder debug + cần Docker Desktop running. In-process testcontainers reproducible + isolated + auto-cleanup.
- **HUMAN-UAT live runtime manual smoke** defer ops handover (carry forward Phase 6 v3.0 deferred item) — Phase 4 v3.1 chỉ semantic coverage E2E pytest httpx.
- Cross-hub p95 < 1.5s performance benchmark live measure defer v4.0 (E-V3-2 mitigation v3.0 carry forward — Phase 4 chỉ check semantic 4 scenario PASS).

**Impact downstream:**
- Plan 04-02 dùng existing `postgres_container` + `redis_container` + `httpx.AsyncClient` + `hub_app_factory` (central) fixture.
- Plan 04-02 tạo test file mới `tests/integration/test_smoke_e2e_v3_1_rbac.py` với 4 scenario `@pytest.mark.critical @pytest.mark.integration` + 4 test (1 test per scenario) + audit log assertion fixture helper `_query_audit_actor_metadata`.
- Plan 04-02 KHÔNG cần docker compose live — chỉ pytest run `make test-integration` PASS.

### D-V3.1-Phase4-D — Plan count = 3 (Wave 1 migration verify + Wave 2 smoke E2E + Wave 3 closeout)

**Rationale (Claude codebase audit 2026-05-24):**
- Plan 01-01..03 (Phase 1 v3.1) ship 3 plan đóng 4 REQ-ID; Plan 02-01..05 (Phase 2 v3.1) ship 5 plan đóng 5 REQ-ID; Plan 03-01..04 (Phase 3 v3.1) ship 4 plan đóng 4 REQ-ID. Phase 4 chỉ 2 REQ-ID → 3 plan đủ (2 implementation + 1 closeout).
- Wave 1 BLOCKING Plan 04-01 (MIGRATE-01 migration verify — `make test-integration` qua test integration existing + bonus add `make test-migration` shortcut nếu cần).
- Wave 2 BLOCKING Plan 04-02 (MIGRATE-02 smoke E2E 4 scenario test mới + audit log inspect).
- Wave 3 BLOCKING Plan 04-03 closeout (4 docs + git tag v3.1 + milestone shipped marker).

**Wave critical path:** 1 (1 plan BLOCKING) → 2 (1 plan BLOCKING) → 3 (1 plan BLOCKING) = 3 plan total (KHÔNG parallel-able — migration verify enable smoke E2E; smoke E2E enable closeout).

**Impact downstream:**
- Total 3 plan estimate match ROADMAP "2-3 plans estimate".
- Plan 04-01 verify-only existing test integration (KHÔNG implement migration mới).
- Plan 04-02 implement test file mới `test_smoke_e2e_v3_1_rbac.py` (4 scenario coverage).
- Plan 04-03 docs + git tag.

### D-V3.1-Phase4-E — Audit log forensic query = SQL `payload->>'actor_role'` + `payload->>'actor_hub_id'` (carry forward Plan 02-04 contract)

**Rationale:** Plan 02-04 DEP-05 ship `build_audit_payload` helper nest `actor_role` + `actor_hub_id` vào `audit_logs.payload` JSONB (D-V3.1-Phase2-C LOCKED KHÔNG schema migration audit_logs). Plan 04-02 smoke E2E assertion query Postgres trực tiếp qua `asyncpg.fetch(...)` hoặc SQLAlchemy async select.

**Lý do LOCKED:**
- Pattern carry forward Phase 2 v3.1 conftest helper `_wait_audit_row` (line 778-806) — poll-based wait cho async audit emit fire-and-forget BackgroundTask.
- Forensic query exact: `SELECT payload->>'actor_role' AS actor_role, payload->>'actor_hub_id' AS actor_hub_id FROM audit_logs WHERE action = $1 AND target_type = $2 ORDER BY created_at DESC LIMIT 1`.
- 4 scenario expect:
  - **(1) super admin POST /api/users:** `actor_role='admin' + actor_hub_id=NULL`.
  - **(2) hub_admin dmd POST /api/users dmd:** `actor_role='hub_admin' + actor_hub_id='<dmd-uuid>'`.
  - **(3) hub_admin dmd POST /api/users tdt:** 403 reject — KHÔNG audit emit (failed request KHÔNG enqueue audit).
  - **(4) viewer:** KHÔNG có user.create audit (viewer KHÔNG được phép POST).
- Test assertion qua helper `_assert_audit_actor_metadata(action, expected_role, expected_hub_id)`.

**Impact downstream:**
- Plan 04-02 ADD helper `_assert_audit_actor_metadata` ở test file mới HOẶC reuse `_wait_audit_row` từ conftest.py.
- Plan 04-02 import `asyncpg` cho direct DB query (KHÔNG cần spin up SQLAlchemy session — connection sẵn qua postgres_container).
- Forensic chain pattern carry forward v4.0 per-resource ACL audit (defer).

### D-V3.1-Phase4-F — Closeout v3.1 SHIPPED = git tag annotated `v3.1` + CLAUDE.md §6 milestone close note + STATE.md percent=100 + REQUIREMENTS.md all REQ-ID [x] + ROADMAP.md Shipped marker

**Rationale (Claude pattern audit 2026-05-24):**
- Carry forward v2.0 milestone shipped 2026-05-21 + v3.0 milestone shipped 2026-05-23 pattern (CLAUDE.md §6 cuối file đã ghi nhận precedent).
- Git tag annotated format: `git tag -a v3.1 -m "v3.1 RBAC hub_admin SHIPPED 2026-05-24 — 4 phase / 15 REQ-ID / 15 plan · ROLE/DEP/FE/MIGRATE · proper fix bug user gán hub_admin vẫn vào central"`.
- KHÔNG push tag (operator decide qua `/gsd-complete-milestone v3.1` future command HOẶC manual `git push origin v3.1`).
- 4 docs update atomic — pattern Phase 2 Plan 02-05 + Phase 3 Plan 03-04 carry forward.

**Lý do LOCKED:**
- Trailing CLAUDE.md `*Cập nhật:` line (line 503 hiện tại) update reflect v3.1 SHIPPED — KHÔNG xoá v3.0 milestone close note (giữ history).
- STATE.md frontmatter `milestone_status: SHIPPED` + `milestone_shipped_date: 2026-05-24` + `next_action: /gsd-complete-milestone v3.1 hoặc /gsd-new-milestone v4.0`.
- REQUIREMENTS.md 2 dòng MIGRATE-XX mark `[x]` + suffix `(DONE 2026-05-24 — Plan 04-XX)`.
- ROADMAP.md milestone row v3.1: `🚧 v3.1 RBAC hub_admin` → `✅ v3.1 RBAC hub_admin — Shipped 2026-05-24, 4 phase / 15 REQ-ID`.

**Impact downstream:**
- Plan 04-03 task atomic: (1) test integration full run final assertion all 15 REQ-ID covered + (2) 4 docs update + (3) git tag annotated + (4) Plan 04-03 SUMMARY.md.
- Plan 04-03 SKIP smoke checkpoint runtime manual visual (carry forward auto-fallback `--chain` mode active per Phase 1-3 v3.1 precedent + v3.0 Plan 04-07 + 05-06 + 06-05).
- v3.1 milestone CLOSED — Next: user decide `/gsd-complete-milestone v3.1` (archive `.planning/milestones/v3.1-rbac-hub-admin-archive/`) HOẶC `/gsd-new-milestone v4.0` (Production Hardening + Advanced RAG backlog per memory `project_v3_multi_hub_split` seed).

### Claude's Discretion

Plan-phase agent quyết định:
- Tên test file mới Plan 04-02: `test_smoke_e2e_v3_1_rbac.py` HOẶC `test_v3_1_rbac_smoke.py` (depends naming convention conftest.py).
- Test fixture scope: `session` HOẶC `module` cho postgres_container (depends test isolation requirement — existing conftest dùng `session` cho speed).
- Audit log assertion fixture: inline trong test_smoke_e2e file HOẶC extract helper `tests/integration/_helpers/audit.py` (extract nếu reuse > 4 lần).
- Pytest marker `@pytest.mark.critical` HOẶC `@pytest.mark.integration` HOẶC cả 2 (carry forward existing tests pattern).
- Plan 04-01 có cần thêm `make test-migration` target Makefile shortcut HOẶC reuse `make test-integration` existing (depends Makefile structure).
- Test seed data: hub `dmd` (id='<dmd-uuid>') + hub `tdt` (id='<tdt-uuid>') + 4 user (super_admin / hub_admin_dmd / hub_admin_tdt / viewer_dmd) — Plan 04-02 seed inline HOẶC fixture helper `_seed_v3_1_rbac_scenario`.
- Git tag push command — chỉ tag local KHÔNG push (let operator review trước qua `git tag -ln v3.1` + `git push origin v3.1` manual).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### v3.1 Phase 4 prior artifacts (Phase 1 + Phase 2 + Phase 3 carry forward)

- `Hub_All/.planning/phases/01-rbac-schema-migration/01-01-PLAN.md` — Migration 0006_role_hub_admin upgrade()/downgrade() introspect pattern + defensive RuntimeError E-V3.1-1 STOP (Plan 04-01 verify-only carry forward).
- `Hub_All/.planning/phases/01-rbac-schema-migration/01-02-PLAN.md` — Helper `get_effective_role` ship (Phase 2 + Phase 4 reuse).
- `Hub_All/.planning/phases/01-rbac-schema-migration/01-03-PLAN.md` — Integration test `test_migration_0006_idempotent.py` 5 test + SAFETY-CRITICAL DSN injection fix I-01 + I-02 (Plan 04-01 chạy bắt buộc qua make test-integration).
- `Hub_All/.planning/phases/02-backend-rbac-enforcement/02-CONTEXT.md` — 7 D-V3.1-Phase2-A..G LOCKED 2026-05-24.
- `Hub_All/.planning/phases/02-backend-rbac-enforcement/02-01-PLAN.md` — `assert_hub_admin_for` validator + envelope HUB_ADMIN_REQUIRED (Plan 04-02 smoke E2E consume).
- `Hub_All/.planning/phases/02-backend-rbac-enforcement/02-02-PLAN.md` — GET /api/hubs filter cả admin (D-V3.1-Phase2-A LOCKED — Plan 04-02 scenario #2/#3 verify).
- `Hub_All/.planning/phases/02-backend-rbac-enforcement/02-03-PLAN.md` — users.py 4 endpoint scope + DELETE B1 iter 1 3-branch + envelope CROSS_HUB_USER_DELETE_DENIED (Plan 04-02 verify).
- `Hub_All/.planning/phases/02-backend-rbac-enforcement/02-04-PLAN.md` — audit payload `actor_role` + `actor_hub_id` nest (Plan 04-02 forensic chain query D-V3.1-Phase4-E carry forward).
- `Hub_All/.planning/phases/02-backend-rbac-enforcement/02-05-PLAN.md` — Closeout pattern (Plan 04-03 mirror 4 docs update atomic).
- `Hub_All/.planning/phases/03-frontend-form-refactor/03-CONTEXT.md` — 5 D-V3.1-Phase3-A..E LOCKED 2026-05-24.
- `Hub_All/.planning/phases/03-frontend-form-refactor/03-04-PLAN.md` — Closeout 4 docs pattern (Plan 04-03 mirror — append CLAUDE.md §6 subsection Phase 4 v3.1 + git tag v3.1).

### v3.0 Phase 7 MIGRATE pattern (carry forward)

- `Hub_All/.planning/phases/07-migration-smoke-e2e/07-CONTEXT.md` — 4 D-V3-Phase7-A..D LOCKED 2026-05-23 (blue/green per-hub + automated smoke pattern).
- `Hub_All/.planning/phases/07-migration-smoke-e2e/07-05-PLAN.md` — Automated 3 hub × 7-step golden path script (Plan 04-02 v3.1 smoke E2E semantic 4 scenario simplification — KHÔNG cần bash automated).
- `Hub_All/.planning/phases/07-migration-smoke-e2e/07-{01..05}-SUMMARY.md` — v3.0 closeout 5 plan + git tag pattern reference.

### v3.0 Phase 4 SYNC + Phase 1 TOPO migration pattern (carry forward Alembic 0005)

- `Hub_All/.planning/phases/04-cross-hub-data-sync/04-01-PLAN.md` v3.0 — Alembic 0005 introspect pattern + per-hub trigger AFTER INSERT/DELETE (D-V3.1-Phase4-A carry forward `sa.inspect()` reference).

### v3.1 milestone-level

- `Hub_All/.planning/ROADMAP.md` — v3.1 RBAC hub_admin milestone (Phase 4 §"Phase 4 — Migration + smoke E2E (MIGRATE)" + 3 Discuss-phase gray areas + 4 success criteria + Plans checklist).
- `Hub_All/.planning/REQUIREMENTS.md` — MIGRATE-01 + MIGRATE-02 (2 REQ-ID) + 13/15 đã consumed Phase 1-3.
- `Hub_All/.planning/STATE.md` — v3.1 progress 12/~15 plan + 13/15 REQ-ID; Phase 3 Results Summary ship 2026-05-24; phase_3_done_date + next_action /gsd-discuss-phase 4.
- `Hub_All/CLAUDE.md` — §2 milestone hiện tại v3.1 + §6 v3.0 + v3.1 Phase 1..3 patterns subsection (Plan 04-03 APPEND subsection mới Phase 4 + milestone close note).

### Backend + test infrastructure existing (Phase 1 + v3.0 carry forward)

- `Hub_All/api/migrations/versions/0006_role_hub_admin.py` — Migration ship 2026-05-23 (Plan 04-01 verify-only, KHÔNG modify).
- `Hub_All/api/tests/integration/conftest.py` — postgres_container + redis_container + asgi_lifespan + httpx.AsyncClient + hub_app_factory fixture (Plan 04-02 reuse).
- `Hub_All/api/tests/integration/test_migration_0006_idempotent.py` — 5 test cover 4 success criteria Phase 1 + SAFETY DSN injection pattern (Plan 04-01 chạy bắt buộc — TEST_DATABASE_URL live).
- `Hub_All/api/tests/integration/test_migration_upgrade_downgrade.py` — Phase 2 v2.0 ship 2 test upgrade head 10 table + downgrade base clean (Plan 04-01 chạy regression).
- `Hub_All/api/tests/integration/test_audit_actor_metadata.py` — Phase 2 v3.1 Plan 02-04 ship audit forensic test pattern (Plan 04-02 forensic query carry forward).
- `Hub_All/api/tests/integration/test_dep_hubs_scope.py` — Phase 2 v3.1 Plan 02-02 ship GET /api/hubs filter test (Plan 04-02 scenario #2/#3 hub_admin verify carry forward).
- `Hub_All/api/tests/conftest.py` — `_wait_audit_row` poll helper line 778-806 (audit emit fire-and-forget BackgroundTask carry forward Plan 04-02).
- `Hub_All/api/Makefile` — `make test-integration` target (Plan 04-01 + 04-02 chạy bắt buộc).

### Memory references (user-level cross-session)

- `memory/project_rbac_hub_admin_gap.md` — v3.1 milestone trigger 2026-05-23 + invariant LOCKED 'admin' = GLOBAL super-admin bypass.
- `memory/project_real_hubs_deployment.md` — 2 hub thật DB (dmd Đỗ Minh Đường + tdt Thuốc Dân Tộc); yte/duoc/hcns decorative ghost — Plan 04-02 smoke 4 scenario seed 2 hub thật.
- `memory/project_no_smtp_v4.md` — KHÔNG SMTP email reset-password chỉ log console; Phase 4 smoke E2E user seed inline password fixture (KHÔNG test SMTP).
- `memory/project_v3_milestone_started.md` — v3.0 milestone 2026-05-21 reference pattern (15 REQ-ID v1 v3.0 carry forward formula).
- `memory/project_v3_multi_hub_split.md` — v3.0 Multi-Hub Split seed (Phase 4 v3.1 closeout sẽ defer v4.0 backlog).
- `memory/feedback_d6_css_deviation.md` — D6 CSS bug frontend (KHÔNG áp dụng Phase 4 — backend smoke E2E scope).
- `memory/project_phase083_oauth_gaps.md` — v3.0 Phase 8.3 OAuth gaps history (KHÔNG áp dụng Phase 4 v3.1 — MCP OAuth defer).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets (Phase 1 + v3.0 + v3.1 carry forward)

- **`tests/integration/conftest.py` fixtures (Phase 2 v3.0 + v3.1 ship):**
  - `postgres_container` (PostgresContainer pgvector/pgvector:pg16) — session-scoped.
  - `redis_container` (RedisContainer) — session-scoped.
  - `alembic_cfg` (Config với DSN injection từ postgres_container) — module-scoped.
  - `hub_app_factory(hub_name)` — Phase 2 v3.0 FACTOR-01..03 ship; mount FastAPI app với `HUB_NAME=central` cho Plan 04-02 smoke E2E.
  - `asgi_lifespan` LifespanManager wrap app context.
  - `_wait_audit_row(...)` poll helper line 778-806 — BackgroundTask audit emit (Plan 02-04 carry forward).
- **`tests/integration/test_migration_0006_idempotent.py` 5 test** — Plan 04-01 chạy bắt buộc với `TEST_DATABASE_URL` live DB.
- **`tests/integration/test_migration_upgrade_downgrade.py` 2 test** — Phase 2 v2.0 ship; Plan 04-01 chạy regression cover 11 table baseline + downgrade clean.
- **`tests/integration/test_dep_hubs_scope.py`** — Plan 02-02 ship DEP-02 GET /api/hubs filter test; Plan 04-02 reuse helper `_seed_hub_admin_user` + `seed_hubs_dmd_tdt`.
- **`tests/integration/test_audit_actor_metadata.py`** — Plan 02-04 ship DEP-05 audit forensic test; Plan 04-02 reuse query pattern `payload->>'actor_role'`.
- **`api/migrations/versions/0006_role_hub_admin.py`** — Plan 01-01 ship migration verify-only Plan 04-01 (KHÔNG modify).
- **`api/app/auth/role.py::get_effective_role`** — Plan 01-02 ship helper (Plan 04-02 import indirectly qua dependency chain).
- **`api/app/auth/dependencies.py::assert_hub_admin_for`** — Plan 02-01 ship validator (Plan 04-02 verify runtime envelope HUB_ADMIN_REQUIRED).
- **`api/app/services/audit_service.py::build_audit_payload`** — Plan 02-04 ship helper (Plan 04-02 verify forensic query).

### Established Patterns

- **`testcontainers` in-process (D-V3.1-Phase4-C LOCKED)** — Pattern carry forward Phase 1 v3.1 Plan 01-03 + Phase 2 v2.0 + Phase 7 v3.0 Plan 04-01..05. KHÔNG real docker compose live.
- **`asgi_lifespan` LifespanManager + `httpx.AsyncClient`** — Pattern Phase 2 v3.0 conftest + Phase 4 v3.0 SYNC integration test. Plan 04-02 mirror.
- **`@pytest.mark.critical + @pytest.mark.integration` marker** — Pattern Phase 2 v2.0 existing test files. Plan 04-02 apply cả 2 marker cho smoke E2E (critical path).
- **DSN injection SAFETY pattern (Plan 01-03 Iter 1 fix I-01)** — `monkeypatch.setenv('DATABASE_URL', test_db_url)` + `get_settings.cache_clear()` TRƯỚC `command.upgrade()`. Plan 04-01 verify-only chạy existing test.
- **Audit emit fire-and-forget BackgroundTask + `_wait_audit_row` poll** — Pattern Plan 02-04 Phase 2 v3.1 + memory `project_fastapi_bgtask_commit`. Plan 04-02 reuse.
- **`asyncpg.connect()` direct query** — Pattern Plan 04-01 v3.0 + Plan 01-03 v3.1. Plan 04-02 audit forensic query direct asyncpg (KHÔNG cần SQLAlchemy session overhead).
- **`make test-integration` target Makefile** — Pattern existing. Plan 04-01 + 04-02 chạy bắt buộc.
- **Git tag annotated** — Pattern v2.0 + v3.0 milestone close. Plan 04-03 `git tag -a v3.1 -m "..."` (KHÔNG push — operator decide).
- **4 docs update atomic** — Pattern Plan 02-05 + 03-04 v3.1 + Plan 04-07 + 05-06 + 06-05 + 07-05 v3.0. Plan 04-03 mirror.
- **CLAUDE.md §6 subsection APPEND** — Pattern carry forward Phase 1..3 v3.1. Plan 04-03 APPEND `### Phase 4 v3.1 Migration + Smoke E2E pattern (MIGRATE-01..02 — 2026-05-24)` + milestone close note `**🎉 v3.1 MILESTONE CLOSED 2026-05-24**`.

### Integration Points

- **Migration 0006 → integration test 0006_idempotent** — Plan 04-01 verify-only chạy test existing với TEST_DATABASE_URL live.
- **HUB_ADMIN_REQUIRED envelope → smoke E2E scenario #2/#3** — Plan 04-02 assert response 403 + `error.code === 'HUB_ADMIN_REQUIRED'`.
- **Audit payload `actor_role` + `actor_hub_id` → smoke E2E audit inspect** — Plan 04-02 query Postgres trực tiếp sau scenario step + assert metadata correct.
- **STATE.md frontmatter + body Phase 4 Results Summary** — Plan 04-03 update atomic carry forward Phase 3 Plan 03-04 pattern.
- **ROADMAP.md milestone row + Plans checklist + progress table** — Plan 04-03 update atomic.
- **CLAUDE.md §6 subsection mới + trailing `*Cập nhật:` line update** — Plan 04-03 APPEND + bump line cuối reflect v3.1 SHIPPED.

### Constraint (R-V3.1-1 HIGH + R-V3.1-2 MEDIUM mitigation Phase 4 verify final)

- **R-V3.1-1 mitigation chain final (migration rollback unsafe data loss):**
  - Plan 04-01 chạy test `test_migration_0006_idempotent.py` 5 test PASS (re-run idempotent + downgrade rollback + audit seed + CHECK constraint restore).
  - Plan 04-01 chạy test `test_migration_upgrade_downgrade.py` 2 test PASS (baseline regression).
  - Defensive RuntimeError downgrade nếu role='hub_admin' exists (Plan 01-01 LOCKED carry forward — production safeguard).
- **R-V3.1-2 mitigation chain final (frontend role check bypass):**
  - Plan 04-02 smoke E2E scenario #2/#3 verify backend filter authoritative (D-V3.1-Phase2-A LOCKED carry forward) — KHÔNG dựa FE.
  - Plan 04-02 verify T-02-02-E business logic block role escalation (POST role='admin' qua hub_admin → 403 HUB_ADMIN_REQUIRED).
  - Plan 04-02 audit forensic query — incident review filter `actor_role` + `actor_hub_id` (Plan 02-04 LOCKED carry forward).

</code_context>

<specifics>
## Specific Ideas

### Plan 04-01 — Migration verify approach

- Chạy `pytest tests/integration/test_migration_0006_idempotent.py tests/integration/test_migration_upgrade_downgrade.py -v --tb=short` qua `make test-integration` HOẶC ad-hoc `TEST_DATABASE_URL=<live> pytest ...`.
- Expected: 5 + 2 = 7 test PASS clean. Nếu fail → fix root cause TRƯỚC khi tiếp tục Plan 04-02.
- Bonus task: ADD `make test-migration` shortcut Makefile target `pytest tests/integration/test_migration*.py -v` (depends Makefile structure — Claude discretion plan time).
- KHÔNG sửa migration `0006_role_hub_admin.py` (LOCKED Plan 01-01 ship 2026-05-23).

### Plan 04-02 — Smoke E2E 4 scenario test file mới

File mới `tests/integration/test_smoke_e2e_v3_1_rbac.py` (estimate ~300 LOC):

```python
"""Smoke E2E test v3.1 RBAC hub_admin — 4 scenario.

Plan 04-02 v3.1 MIGRATE-02 — verify Phase 2 + Phase 3 ship semantic E2E:
- (1) super admin: GET /api/hubs → ALL + POST user any hub → 201
- (2) hub_admin dmd: GET /api/hubs → CHỈ dmd + POST user dmd → 201 + POST user tdt → 403
- (3) hub_admin tdt: mirror (2) với hub tdt
- (4) viewer: list documents PASS + POST user 403

Audit log inspect: 4 scenario verify payload->>'actor_role' + payload->>'actor_hub_id'.
"""
import asyncpg
import httpx
import pytest
from asgi_lifespan import LifespanManager

@pytest.fixture
async def seed_v3_1_rbac_scenario(postgres_container, alembic_cfg):
    """Seed 2 hub (dmd + tdt) + 4 user (super + hub_admin × 2 + viewer)."""
    # ... seed via direct asyncpg + Argon2 password hash

@pytest.mark.critical
@pytest.mark.integration
async def test_scenario_1_super_admin(hub_app_factory, seed_v3_1_rbac_scenario, redis_container):
    app = hub_app_factory("central")
    async with LifespanManager(app), httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # login super admin → get JWT
        # GET /api/hubs → assert ALL 3 hub
        # POST /api/users hub_id=<dmd> → 201
        # POST /api/users hub_id=<tdt> → 201
        # audit_logs assert actor_role='admin' + actor_hub_id=NULL

# ... mirror scenarios 2, 3, 4
```

Helper `_assert_audit_actor_metadata(conn, action, expected_role, expected_hub_id)` inline file (extract conftest.py defer nếu reuse > 4 lần).

### Plan 04-03 — Closeout v3.1 SHIPPED

1. STATE.md frontmatter `completed_phases: 4` + `completed_plans: 15` + `percent: 100` + `milestone_status: SHIPPED` + `milestone_shipped_date: 2026-05-24` + `next_action: /gsd-complete-milestone v3.1 hoặc /gsd-new-milestone v4.0` + body Phase 4 Results Summary section.
2. REQUIREMENTS.md 2 dòng MIGRATE-01 + MIGRATE-02 mark `[x]` với suffix.
3. ROADMAP.md Phase 4 row DONE + Plans checklist + milestone row v3.1 `✅ Shipped 2026-05-24`.
4. CLAUDE.md §6 APPEND subsection mới + bump trailing `*Cập nhật:` line reflect v3.1 SHIPPED.
5. `git tag -a v3.1 -m "v3.1 RBAC hub_admin SHIPPED 2026-05-24 — 4 phase / 15 REQ-ID / 15 plan · ROLE/DEP/FE/MIGRATE · proper fix bug user gán hub_admin vẫn vào central (per memory project_rbac_hub_admin_gap)"` (KHÔNG push — operator decide).
6. Plan 04-03 SUMMARY.md ship.

### Test seed data fixture (Plan 04-02)

```python
# Seed 2 hub thật (per memory project_real_hubs_deployment)
HUBS = [
    {"id": "<dmd-uuid>", "code": "dmd", "name": "Đỗ Minh Đường", "status": "active"},
    {"id": "<tdt-uuid>", "code": "tdt", "name": "Thuốc Dân Tộc", "status": "active"},
    # central hub seed bởi migration 0001 (KHÔNG seed lại)
]

# Seed 4 user qua direct asyncpg INSERT + pwdlib Argon2 hash
USERS = [
    {"email": "super@medinet.vn", "role": "admin", "user_hubs": []},
    {"email": "hadmin.dmd@medinet.vn", "role": "hub_admin", "user_hubs": [{"hub_id": "<dmd-uuid>", "role": None}]},
    {"email": "hadmin.tdt@medinet.vn", "role": "hub_admin", "user_hubs": [{"hub_id": "<tdt-uuid>", "role": None}]},
    {"email": "viewer.dmd@medinet.vn", "role": "viewer", "user_hubs": [{"hub_id": "<dmd-uuid>", "role": None}]},
]
PASSWORD = "Test1234!"  # All users
```

### Git tag command

```bash
git tag -a v3.1 -m "v3.1 RBAC hub_admin SHIPPED 2026-05-24

4 phase / 15 REQ-ID / 15 plan ship:
- Phase 1 ROLE: migration 0006 + helper get_effective_role
- Phase 2 DEP: assert_hub_admin_for + GET /api/hubs filter + CRUD scope + audit
- Phase 3 FE: UserRole alias + form 3 option + HubSwitcher + Manage modal disabled
- Phase 4 MIGRATE: idempotent + downgrade + smoke E2E 4 scenario + audit forensic

Proper fix bug user gán hub_admin vẫn vào central (memory project_rbac_hub_admin_gap)."
```

KHÔNG push tag — operator decide qua `git push origin v3.1` manual hoặc `/gsd-complete-milestone v3.1` future command.

</specifics>

<deferred>
## Deferred Ideas

- **HUMAN-UAT live runtime manual smoke 4 scenario** (defer ops handover carry forward Phase 6 v3.0 + Plan 04-07 v3.0 + 05-06 v3.0 + 06-05 v3.0 + Plan 03-04 v3.1 precedent) — automated semantic coverage E2E pytest đủ MIGRATE-02 scope; manual smoke live BE defer.
- **Performance benchmark cross-hub p95 < 1.5s live measure** — E-V3-2 mitigation v3.0 carry forward defer v4.0 (HARD-04 production hardening backlog).
- **Visual regression smoke 4 hub × 11 trang React M2 COMPAT-01** — defer v4.0 ops handover carry forward Phase 5 v3.0 + Phase 3 v3.1 Plan 03-04.
- **OAuth role mapping qua SSO group claim** — defer v4.0 (per ROADMAP backlog).
- **Multi-role 1 user trong cùng hub** — schema migration 0006 mỗi `user_hubs` row 1 role; defer v4.0 per-resource ACL.
- **Per-resource ACL granular (documents.created_by filter cho viewer/editor read-only)** — defer v4.0 carry forward backlog v3.1 deferred items.
- **SMTP email reset-password** — defer v4.0 per memory `project_no_smtp_v4` (Phase 4 fixture seed inline password).
- **`actor_hub_id` UUID resolution từ slug** — hub_admin truyền `hub_id` UUID string qua body (KHÔNG slug); carry forward Plan 02-04 contract LOCKED.
- **Push git tag v3.1 auto** — Plan 04-03 chỉ tag local; operator quyết định `git push origin v3.1` manual (defer auto qua future `/gsd-complete-milestone v3.1` command).
- **Archive `.planning/milestones/v3.1-rbac-hub-admin-archive/`** — defer `/gsd-complete-milestone v3.1` separate command sau v3.1 SHIPPED.
- **v4.0 milestone start** — defer `/gsd-new-milestone v4.0` sau user retrospective + decide ưu tiên backlog (sub-hub split per memory `project_v3_multi_hub_split` seed + HA Redis cluster + OCR Vietnamese + streaming `/api/ask` + coverage >80% + per-resource ACL).

</deferred>

---

*Phase: 04-migration-smoke-e2e*
*Context gathered: 2026-05-24 via /gsd-discuss-phase 4 auto-mode (3 gray area ROADMAP recommendation LOCKED + 3 decision phụ codebase audit — D-V3.1-Phase4-D plan count + D-V3.1-Phase4-E audit forensic query + D-V3.1-Phase4-F git tag closeout)*
