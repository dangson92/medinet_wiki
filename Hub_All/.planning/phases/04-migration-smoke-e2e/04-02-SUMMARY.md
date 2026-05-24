---
phase: 04
plan: 02
wave: 2
shipped: 2026-05-24
status: DONE
commits:
  - 1ed21a8 feat(04-02) MIGRATE-02 smoke E2E 4 scenario RBAC v3.1 + audit forensic chain verify
requirements_satisfied: [MIGRATE-02]
decisions_implemented:
  - D-V3.1-Phase4-C  # testcontainers in-process pattern (reuse postgres_container + redis_container session-scoped)
  - D-V3.1-Phase4-E  # Audit forensic SQL payload->>'actor_role' query via SQLAlchemy async engine
files_modified:
  created:
    - api/tests/integration/test_smoke_e2e_v3_1_rbac.py  # ~430 LOC
  modified: []
tests:
  smoke_e2e: "4 scenario PASS clean in 19.86s"
  scenarios_covered:
    - "(1) super admin full access: GET /api/hubs → ALL + POST user → 201 + audit actor_role='admin' + actor_hub_id=NULL"
    - "(2) hub_admin dmd scoped: GET /api/hubs → CHỈ dmd + POST user dmd → 201 + POST user tdt → 403 HUB_ADMIN_REQUIRED + audit actor_role='hub_admin' + actor_hub_id=<dmd-uuid>"
    - "(3) hub_admin tdt mirror: cross-hub isolation symmetric verify"
    - "(4) viewer privilege denied: POST /api/users → 403 (FORBIDDEN hoặc HUB_ADMIN_REQUIRED)"
---

# Plan 04-02 — Summary (Wave 2 BLOCKING — DONE)

**Mục tiêu:** Smoke E2E 4 scenario verify Phase 2 + Phase 3 ship semantic E2E real backend code path + audit forensic chain.

## Deliverable

### `api/tests/integration/test_smoke_e2e_v3_1_rbac.py` (CREATE ~430 LOC)

**Helper module-level:**
- `_seed_hub_admin_user(*, email, password_hash, hub_id) -> user_id` — pattern carry forward test_dep_hubs_scope.py:37-76 (Plan 02-02 ship). Seed user role='editor' global + user_hubs.role='hub_admin' per-hub override.
- `_assert_audit_actor_metadata(*, action, expected_role, expected_hub_id, timeout=3.0)` — pattern carry forward test_audit_actor_metadata.py (Plan 02-04 ship). Poll SQLAlchemy engine query `SELECT payload->>'actor_role', payload->>'actor_hub_id' FROM audit_logs WHERE action=:action ORDER BY created_at DESC LIMIT 1` với 3s timeout cho BackgroundTask fire-and-forget timing.

**Fixture:**
- `seed_hubs_dmd_tdt(app_with_auth) -> (dmd_id, tdt_id)` — pattern carry forward test_dep_hubs_scope.py:79-125 (Plan 02-02 ship). Seed 2 hub thật per memory `project_real_hubs_deployment` (dmd Đỗ Minh Đường + tdt Thuốc Dân Tộc).

**4 scenario test async:**

| # | Scenario | REQ verify | Result |
|---|----------|------------|--------|
| 1 | super admin full access | D-V3.1-Phase2-A + DEP-05 audit | GET /api/hubs → cả dmd + tdt; POST user → 201; audit `actor_role='admin'` + `actor_hub_id=NULL` |
| 2 | hub_admin dmd scoped | DEP-01..05 + T-02-02-E + envelope HUB_ADMIN_REQUIRED | GET → CHỈ dmd; POST user dmd → 201; POST user tdt → 403 HUB_ADMIN_REQUIRED; audit `actor_role='hub_admin'` + `actor_hub_id=<dmd-uuid>` |
| 3 | hub_admin tdt mirror | Symmetric verify | GET → CHỈ tdt; POST user tdt → 201; POST user dmd → 403; audit metadata correct |
| 4 | viewer privilege denied | require_role / require_hub_admin reject | POST /api/users → 403 (accept FORBIDDEN hoặc HUB_ADMIN_REQUIRED per backend ordering Plan 02-03) |

**Reuse fixture từ conftest.py existing** (KHÔNG redeclare):
- `app_with_auth` — testcontainer Postgres + Redis + alembic upgrade head + LifespanManager + auto-truncate 8 bảng RESTART IDENTITY CASCADE per-test.
- `auth_client` — httpx.AsyncClient + ASGITransport.
- `admin_user` + `admin_token` — super admin fixture.
- `viewer_user` + `viewer_token` — viewer fixture.
- `_login_get_token` — login helper.
- `GO_SEED_HASH` + `GO_SEED_HASH_PLAINTEXT` — Argon2 hash + plaintext "Admin@123".

## Tests

`uv run pytest tests/integration/test_smoke_e2e_v3_1_rbac.py -v --tb=short` →
**4 passed, 5 warnings in 19.86s** — clean.

```
tests/integration/test_smoke_e2e_v3_1_rbac.py::test_scenario_1_super_admin_full_access PASSED [ 25%]
tests/integration/test_smoke_e2e_v3_1_rbac.py::test_scenario_2_hub_admin_dmd_scoped PASSED [ 50%]
tests/integration/test_smoke_e2e_v3_1_rbac.py::test_scenario_3_hub_admin_tdt_scoped PASSED [ 75%]
tests/integration/test_smoke_e2e_v3_1_rbac.py::test_scenario_4_viewer_post_user_forbidden PASSED [100%]
```

## Deviation ghi nhận

Plan 04-02 template ban đầu dùng `full_name` field trong POST /api/users body. Pydantic
schema `CreateUserRequest` (api/app/schemas/users.py) require `name` field (KHÔNG `full_name`).
Fixed inline — 4 occurrence `full_name:` → `name:` qua single Edit replace_all.

Plan 04-02 template `hub_app_factory("central")` reference KHÔNG đúng — đó là Phase 2 v3.0
FACTOR test pattern với FAKE DSN (chỉ verify router mount config, KHÔNG kết nối real DB).
Adapted: dùng `auth_client` (testcontainer-backed `app_with_auth`) thay vì `hub_app_factory`.
Pattern correct sống động trong test_dep_hubs_scope.py + test_audit_actor_metadata.py.

## Backward compat (Plan 04-02 KHÔNG break existing)

- 1 file mới ADD — KHÔNG modify existing test suite (200+ unit + integration test
  regression preserve).
- KHÔNG đụng conftest.py fixture infrastructure.
- KHÔNG đụng backend code (routers/users.py + routers/hubs.py + auth/dependencies.py +
  services/audit_service.py + migration 0006).
- Reuse pattern test_dep_hubs_scope.py (Plan 02-02) + test_audit_actor_metadata.py
  (Plan 02-04) carry forward — extract chung sang helper module defer Phase 5+ nếu reuse
  > 4 file.

## Audit forensic chain verified (D-V3.1-Phase4-E + D-V3.1-Phase2-C carry forward)

Plan 02-04 build_audit_payload helper nest `actor_role` + `actor_hub_id` vào audit_logs.payload
JSONB — Plan 04-02 verify runtime end-to-end:

- Scenario 1 super admin POST /api/users → audit row `action='user.create'` payload có
  `actor_role='admin'` + `actor_hub_id=NULL`.
- Scenario 2 hub_admin dmd POST /api/users (dmd) → audit row payload `actor_role='hub_admin'`
  + `actor_hub_id=<dmd-uuid>`.
- Scenario 3 hub_admin tdt POST /api/users (tdt) → mirror với tdt UUID.

Forensic query pattern:
```python
SELECT payload->>'actor_role' AS actor_role, payload->>'actor_hub_id' AS actor_hub_id
FROM audit_logs WHERE action = :action ORDER BY created_at DESC LIMIT 1
```

Carry forward v4.0 per-resource ACL audit (extend payload nest pattern).

## Carry forward cho Plan 04-03

- ROADMAP Phase 4 success criterion #2 + #3 satisfied (4 scenario PASS + audit metadata verified).
- Plan 04-03 closeout: 4 docs atomic update + git tag annotated v3.1 LOCAL (KHÔNG push).
- v3.1 milestone CLOSEOUT sau Plan 04-03 ship: 15/15 plan · 15/15 REQ-ID · 🎉 SHIPPED 2026-05-24.

---

**Commit:** `1ed21a8 feat(04-02): MIGRATE-02 smoke E2E 4 scenario RBAC v3.1 + audit forensic chain verify`
