---
phase: 04-migration-smoke-e2e
mapped: 2026-05-24
status: Ready for planning
source: CONTEXT.md (6 D-V3.1-Phase4-A..F LOCKED) + codebase audit Hub_All/api/tests/integration/ + Hub_All/api/Makefile
language: vietnamese
---

# Phase 4 v3.1: Migration + Smoke E2E — Pattern Map

> Pattern map cho 3 plan Wave (Plan 04-01 migration verify + Plan 04-02 smoke E2E 4 scenario + Plan 04-03 closeout v3.1 SHIPPED). Mỗi file Phase 4 touch → analog file thật trong `Hub_All/api/tests/integration/` + `Hub_All/api/Makefile` + `.planning/` + concrete code excerpt (line numbers).

**Mapped:** 2026-05-24
**Files analyzed:** 9 file (2 test + 1 Makefile + 4 docs + 1 git tag command + 1 SUMMARY)
**Analogs found:** 9/9 (100% coverage)

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality | Wave |
|-------------------|------|-----------|----------------|---------------|------|
| `api/Makefile` (MODIFY append `test-integration` + `test-migration` target) | task-runner shortcut | shell exec | `api/Makefile:31-35` (test + test-cov pattern) | exact (same file pattern) | Wave 1 |
| `api/tests/integration/test_migration_0006_idempotent.py` (RUN existing) | integration-test verify | live Postgres testcontainers | (file là analog của chính nó — KHÔNG code change) | exact (verify-only) | Wave 1 |
| `api/tests/integration/test_migration_upgrade_downgrade.py` (RUN existing) | integration-test regression | live Postgres testcontainers | (file là analog của chính nó — KHÔNG code change) | exact (verify-only) | Wave 1 |
| `api/tests/integration/test_smoke_e2e_v3_1_rbac.py` (CREATE) | smoke-E2E integration-test | testcontainers + asgi_lifespan + httpx.AsyncClient + audit forensic asyncpg | `api/tests/integration/test_dep_hubs_scope.py` (Plan 02-02 ship — hub_admin login + GET /api/hubs scope) + `api/tests/integration/test_audit_actor_metadata.py` (Plan 02-04 ship — audit forensic query) | role-match (composite 2 pattern) | Wave 2 |
| `.planning/STATE.md` (MODIFY frontmatter + body Phase 4 Results section) | source-of-truth state | YAML + markdown | `.planning/STATE.md` (Phase 2 Results 117-155 + Phase 3 Results section gần đây) | exact (same file pattern) | Wave 3 |
| `.planning/REQUIREMENTS.md` (MODIFY 2 dòng MIGRATE-01..02 → [x]) | source-of-truth REQ checklist | markdown checklist | `.planning/REQUIREMENTS.md:25-26` (DEP-04 + DEP-05 mark [x] format) | exact (same line pattern) | Wave 3 |
| `.planning/ROADMAP.md` (MODIFY Phase 4 row + plans checklist + milestone row v3.1 SHIPPED) | source-of-truth roadmap | markdown table + checklist | `.planning/ROADMAP.md` (Phase 1-3 row DONE pattern + milestone row v3.0 Shipped) | exact (same file pattern) | Wave 3 |
| `CLAUDE.md` (MODIFY §6 APPEND subsection + bump trailing `*Cập nhật:` line) | source-of-truth project guide | markdown subsection | `CLAUDE.md §6 Phase 3 v3.1 Frontend form refactor pattern` (Plan 03-04 ship) | exact (same file pattern + append style) | Wave 3 |
| Git tag annotated `v3.1` (BASH command) | milestone-marker | git tag -a -m | v2.0 milestone close (carry forward) + v3.0 milestone close (CLAUDE.md note) | role-match (annotated tag w/ message) | Wave 3 |

---

## Pattern Assignments

### Wave 1 (Plan 04-01 BLOCKING — migration verify + Makefile shortcut)

#### 1. `api/Makefile` (MODIFY — `test-integration` + `test-migration` target)

**Analog:** `Hub_All/api/Makefile:31-35` (test + test-cov pattern):
```makefile
test:
	$(UV) run pytest -v

test-cov:
	$(UV) run pytest --cov=app --cov-report=term-missing
```

**Pattern:** APPEND TRƯỚC `# === Alembic migration targets ===` (line 40):
```makefile
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

**Update `.PHONY` line 2:** add `test-integration test-migration`.

#### 2. `api/tests/integration/test_migration_0006_idempotent.py` (RUN existing)

**KHÔNG code change.** Plan 04-01 chỉ verify-only chạy live DB.

5 test existing cover:
- `test_check_constraint_accepts_hub_admin` — CHECK constraint 4 value PASS sau upgrade.
- `test_re_run_upgrade_head_idempotent` — `command.upgrade(cfg, "head")` 2 lần KHÔNG fail.
- `test_user_hubs_role_nullable_check_constraint` — column nullable + CHECK NULL-aware.
- `test_audit_logs_migration_seed_row_inserted` — audit_logs có row action='migration.role_seed'.
- `test_downgrade_restores_check_3_value` — downgrade -1 restore CHECK 3 value + drop user_hubs.role.

#### 3. `api/tests/integration/test_migration_upgrade_downgrade.py` (RUN existing)

**KHÔNG code change.** Plan 04-01 chỉ verify-only chạy regression baseline.

2 test existing cover:
- `test_upgrade_creates_10_tables` — upgrade head → 10 bang app + alembic_version.
- `test_downgrade_drops_all_clean` — downgrade base → 10 bang xoá clean.

---

### Wave 2 (Plan 04-02 BLOCKING — smoke E2E 4 scenario test mới)

#### 4. `api/tests/integration/test_smoke_e2e_v3_1_rbac.py` (CREATE — MIGRATE-02)

**Analog #1:** `api/tests/integration/test_dep_hubs_scope.py` (Plan 02-02 ship):
- `_seed_hub_admin_user(conn, hub_id, email, role)` helper pattern.
- `seed_hubs_dmd_tdt` fixture pattern (seed 2 hub thật).
- `login_get_token(client, email, password)` helper pattern.
- `httpx.AsyncClient` + `asgi_lifespan.LifespanManager` + `hub_app_factory("central")` pattern.

**Analog #2:** `api/tests/integration/test_audit_actor_metadata.py` (Plan 02-04 ship):
- `_wait_audit_row(conn, action, target_type, timeout=2.0)` poll helper pattern.
- `payload->>'actor_role'` + `payload->>'actor_hub_id'` JSONB query pattern.
- BackgroundTask audit emit fire-and-forget timing pattern.

**Pattern composite (4 scenario test file ~300 LOC):**

```python
"""Smoke E2E test v3.1 RBAC hub_admin — 4 scenario.

Plan 04-02 v3.1 MIGRATE-02 — verify Phase 2 + Phase 3 ship semantic E2E:
- (1) super admin: GET /api/hubs → ALL + POST user any hub → 201
- (2) hub_admin dmd: GET /api/hubs → CHỈ dmd + POST user dmd → 201 + POST user tdt → 403
- (3) hub_admin tdt: mirror (2) với hub tdt
- (4) viewer: list documents PASS + POST user 403
Audit forensic: payload->>'actor_role' + payload->>'actor_hub_id' verify 4 scenario.
"""
from __future__ import annotations

import uuid
import asyncpg
import httpx
import pytest
from asgi_lifespan import LifespanManager
from pwdlib import PasswordHash
from testcontainers.postgres import PostgresContainer
from testcontainers.redis import RedisContainer


# === Fixture: seed 2 hub thật + 4 user (super + hub_admin × 2 + viewer) ===

@pytest.fixture
async def seed_v3_1_rbac_scenario(postgres_container, alembic_cfg):
    """Seed 2 hub (dmd + tdt) + 4 user qua direct asyncpg + Argon2 hash."""
    # ... apply migration head; seed hub + user qua asyncpg.connect()
    # Return dict {'hub_dmd_id': ..., 'hub_tdt_id': ..., 'users': {...}}


# === Helper: login + audit query ===

async def _login_get_token(client, email, password):
    """POST /api/auth/login + return access_token."""

async def _assert_audit_actor_metadata(conn, action, target_type, expected_role, expected_hub_id):
    """Query audit_logs WHERE action + target_type, assert payload->>'actor_role' + 'actor_hub_id'."""


# === Scenario 1: super admin ===

@pytest.mark.critical
@pytest.mark.integration
async def test_scenario_1_super_admin_full_access(
    hub_app_factory, seed_v3_1_rbac_scenario, redis_container
):
    """Super admin: GET /api/hubs → ALL + POST user dmd + POST user tdt → 201."""
    app = hub_app_factory("central")
    async with LifespanManager(app), httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        token = await _login_get_token(client, "super@medinet.vn", "Test1234!")
        headers = {"Authorization": f"Bearer {token}"}

        # GET /api/hubs → ALL (central + dmd + tdt)
        res = await client.get("/api/hubs", headers=headers)
        assert res.status_code == 200
        hubs = res.json()["data"]
        codes = [h["code"] for h in hubs]
        assert "central" in codes and "dmd" in codes and "tdt" in codes

        # POST /api/users hub_id=<dmd> → 201
        res = await client.post(
            "/api/users",
            headers=headers,
            json={"email": "newuser1@test.vn", "name": "New 1", "password": "Pass1234!",
                  "hub_id": seed_v3_1_rbac_scenario["hub_dmd_id"], "role": "viewer"},
        )
        assert res.status_code == 201

        # Audit forensic verify
        async with asyncpg.connect(_test_dsn(postgres_container)) as conn:
            await _assert_audit_actor_metadata(
                conn, "user.create", "users", expected_role="admin", expected_hub_id=None
            )


# === Scenario 2: hub_admin dmd ===

@pytest.mark.critical
@pytest.mark.integration
async def test_scenario_2_hub_admin_dmd_scoped(
    hub_app_factory, seed_v3_1_rbac_scenario, redis_container
):
    """Hub_admin dmd: GET /api/hubs → CHỈ dmd + POST user dmd → 201 + POST user tdt → 403."""
    # Similar pattern...


# === Scenario 3: hub_admin tdt (mirror) ===

@pytest.mark.critical
@pytest.mark.integration
async def test_scenario_3_hub_admin_tdt_scoped(...):
    """Mirror scenario 2 với hub tdt."""


# === Scenario 4: viewer ===

@pytest.mark.critical
@pytest.mark.integration
async def test_scenario_4_viewer_read_only(
    hub_app_factory, seed_v3_1_rbac_scenario, redis_container
):
    """Viewer: list documents PASS + POST user → 403 FORBIDDEN."""
```

**Lưu ý implementation:**
- 4 test function async (asyncio_mode=auto trong pyproject.toml).
- Reuse `_seed_hub_admin_user` từ `test_dep_hubs_scope.py` HOẶC inline (depends consolidate decision Claude discretion).
- `asyncpg.connect()` direct cho audit query — KHÔNG cần SQLAlchemy session overhead.
- Password hash: `pwdlib.PasswordHash` (Argon2 cross-compat M2 Phase 3 ship per memory).

---

### Wave 3 (Plan 04-03 BLOCKING — closeout 4 docs + git tag v3.1)

#### 5. `.planning/STATE.md` (MODIFY frontmatter + body)

**Analog:** Plan 03-04 ship pattern (Phase 3 Results Summary append):
- Frontmatter: `completed_phases: 4` + `completed_plans: 15` + `percent: 100` + `milestone_status: SHIPPED` + `milestone_shipped_date: 2026-05-24` + `phase_4_done_date: 2026-05-24` + `next_action: /gsd-complete-milestone v3.1 hoặc /gsd-new-milestone v4.0`.
- Body: v3.1 Planning Summary table Phase 4 row → `✅ DONE 2026-05-24 (3 plan)`.
- Body: APPEND `## Phase 4 Results Summary (DONE 2026-05-24)` section với 3 plan bullet + carry forward + 🎉 v3.1 SHIPPED note.

#### 6. `.planning/REQUIREMENTS.md` (MODIFY 2 dòng MIGRATE-01..02 → [x])

**Analog:** Plan 03-04 ship pattern (4 dòng FE-XX [x] + suffix):
```markdown
- [x] **MIGRATE-01** Phase 4: Migration smoke test idempotent ... (DONE 2026-05-24 — Plan 04-01)
- [x] **MIGRATE-02** Phase 4: Smoke E2E 4 scenario qua pytest httpx ... (DONE 2026-05-24 — Plan 04-02)
```

#### 7. `.planning/ROADMAP.md` (MODIFY Phase 4 row + plans + milestone)

**Analog:** Plan 03-04 ship pattern + v3.0 milestone shipped marker:
- Phase 4 table row: `Migration + smoke E2E (MIGRATE) ✅ DONE 2026-05-24`.
- 3 plans checklist `[ ] 04-0X-PLAN.md ...` → `[x] 04-0X-PLAN.md ... ✅ DONE 2026-05-24`.
- Milestones section: `🚧 v3.1 RBAC hub_admin` → `✅ v3.1 RBAC hub_admin — Shipped 2026-05-24, 4 phase / 15 REQ-ID`.
- Progress table row v3.1: `15/15 plan · 15/15 REQ-ID · ✅ SHIPPED 2026-05-24`.

#### 8. `CLAUDE.md` §6 APPEND subsection mới + bump trailing line

**Analog:** Plan 03-04 ship pattern (`### Phase 3 v3.1 Frontend form refactor pattern (FE-01..04 — 2026-05-24)`):
- APPEND subsection `### Phase 4 v3.1 Migration + Smoke E2E pattern (MIGRATE-01..02 — 2026-05-24)` SAU Phase 3 v3.1 subsection (TRƯỚC `---` separator line 501).
- 3 bullet plan với pattern + file path + decision reference.
- Architecture insights (5 điểm — testcontainers pattern + audit forensic chain + migration verify carry forward + closeout pattern + git tag annotated).
- 🎉 v3.1 MILESTONE CLOSED note + Next pointer v4.0 backlog.
- BUMP trailing `*Cập nhật:` line (line 503) reflect v3.1 SHIPPED 2026-05-24 — `*Cập nhật: 2026-05-24 (Phase 4 DONE — MIGRATE-01..02 ship 3 plan; ... **🎉 v3.1 MILESTONE CLOSED 2026-05-24** — 15/15 plan ship · 15/15 REQ-ID consumed ...)*`.

#### 9. Git tag annotated `v3.1` (BASH command — KHÔNG push)

**Analog:** v2.0 + v3.0 milestone close pattern (CLAUDE.md §6 reference):
```bash
git tag -a v3.1 -m "v3.1 RBAC hub_admin SHIPPED 2026-05-24

4 phase / 15 REQ-ID / 15 plan ship:
- Phase 1 ROLE: migration 0006 + helper get_effective_role
- Phase 2 DEP: assert_hub_admin_for + GET /api/hubs filter + CRUD scope + audit
- Phase 3 FE: UserRole alias + form 3 option + HubSwitcher + Manage modal disabled
- Phase 4 MIGRATE: idempotent + downgrade + smoke E2E 4 scenario + audit forensic

Proper fix bug user gán hub_admin vẫn vào central (memory project_rbac_hub_admin_gap)."
```

**KHÔNG push tag** — operator decide qua `git push origin v3.1` manual hoặc `/gsd-complete-milestone v3.1` future command.

---

## Wave Grouping

| Wave | Plan | Files | Critical Path | Parallel-able |
|------|------|-------|---------------|---------------|
| **1** | 04-01 (BLOCKING) | api/Makefile + 2 test existing run | Verify migration enable smoke E2E | KHÔNG |
| **2** | 04-02 (BLOCKING) | 1 test file mới create | Smoke E2E enable closeout | KHÔNG |
| **3** | 04-03 (BLOCKING) | 4 docs + 1 git tag + 1 SUMMARY | Closeout SHIPPED marker | KHÔNG |

**Total:** 3 plan / 8 file touch / 9 analog 100% coverage.

---

*Generated by Claude auto-mode pattern audit 2026-05-24 — CONTEXT.md 6 decision LOCKED + existing tests/integration/ infrastructure + Plan 03-04 closeout pattern carry forward.*
