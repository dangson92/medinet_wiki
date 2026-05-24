---
gsd_state_version: 1.0
milestone: v3.1
milestone_name: RBAC hub_admin
status: "🚧 v3.1 STARTED 2026-05-23 — defining requirements + roadmap. Trigger: user bug report 2026-05-23 sau v3.0 close — tạo user gán hub `dmd` nhưng vẫn vào được central (gap thiết kế role-per-hub defer v4.0 trong M2). Scope: 4 phase / 15 REQ-ID / phase numbering reset về 1 (D-V3.1-04). Memory reference: project_rbac_hub_admin_gap."
last_updated: "2026-05-24T09:30:00.000Z"
progress:
  total_phases: 4
  completed_phases: 1
  total_plans: 15  # estimate ~12-15 plan (Phase 1 ship 3; Phase 2 plan 5 — total 8 plan ship/planned)
  completed_plans: 3
  percent: 20
milestone_status: "STARTED"
milestone_start_date: "2026-05-23"
phase_2_status: "PLANNED"
phase_2_plan_count: 5
phase_2_planned_date: "2026-05-24"
next_action: "/gsd-execute-phase 2 — DEP backend RBAC enforcement (5 plan / 4 wave / DEP-01..05 coverage 100%, iter 2 plan-checker VERIFICATION PASSED)"
---

# State — MEDWIKI (v3.1)

**Mã dự án:** MEDWIKI
**Milestone:** v3.1 — RBAC hub_admin
**Ngày bắt đầu:** 2026-05-23 (sau khi v3.0 shipped 100% COMPLETE 38/38 plan + 30/30 REQ-ID consumed)
**Last updated:** 2026-05-23

## Current Position

🚧 **v3.1 PHASE 2 PLANNED 2026-05-24** — Phase 1 DONE (3 plan / 4 REQ-ID); Phase 2 plan files ship đầy đủ (5 plan / 4 wave / DEP-01..05 coverage 100%). Iter 2 plan-checker VERIFICATION PASSED — 7 BLOCKER + 4 WARNING iter 1 fixed.

- **Phase:** 02-backend-rbac-enforcement (PLANNED — chưa execute)
- **Plan:** 5 plan ship `.planning/phases/02-backend-rbac-enforcement/02-{01..05}-PLAN.md`
- **Status:** Ready to execute — `/gsd-execute-phase 2` will run Wave 1 (02-01 BLOCKING assert_hub_admin_for + 5 unit test) → Wave 2 (02-02 + 02-03 parallel — hubs GET defensive AUTH_STATE_INCONSISTENT + users CRUD scope DEP-03 với DELETE 3-branch logic) → Wave 3 (02-04 audit payload nest actor_role + actor_hub_id) → Wave 4 (02-05 closeout 4 docs + W5 FE breakage operator broadcast note).
- **Next Action:** `/gsd-execute-phase 2` — execute 5 plan với atomic commits per plan; expected ~12 file modified + ~25 test ship (5 unit + 20 integration); coverage ≥80% target trên auth/dependencies + routers/users + services/audit (D-V3.1-Phase2-F LOCKED).

## Phase 2 Planning Summary (PLANNED 2026-05-24)

| Plan | Wave | Objective | REQ-ID | Files modified | Tasks |
|------|------|-----------|--------|----------------|-------|
| 02-01 | 1 | assert_hub_admin_for validator function + 5-case unit test + envelope HUB_ADMIN_REQUIRED | DEP-01 | 2 | 2 |
| 02-02 | 2 | GET /api/hubs defensive AUTH_STATE_INCONSISTENT invariant + 5 mutate preserve require_role("admin") | DEP-02, DEP-04 | 3 | 2 |
| 02-03 | 2 | users.py 4 endpoint refactor (POST/PATCH role/GET list/DELETE 3-branch) + UserRole Literal extend | DEP-03 | 3 | 2 |
| 02-04 | 3 | build_audit_payload helper + 5 service callsite refactor + 5 router actor derive + api_key_service guard | DEP-05 | 7 | 2 |
| 02-05 | 4 | Closeout 4 docs (STATE/REQUIREMENTS/ROADMAP/CLAUDE) + W5 FE breakage operator broadcast | DEP-01..05 (all) | 4 | 1 |

**Coverage:** 5/5 REQ-ID DEP-01..05 mapped. Wave 1 BLOCKING (1) + Wave 2 parallel (2) + Wave 3 sequential (1) + Wave 4 closeout (1).

## Phase 2 Key Design Decisions (LOCKED 2026-05-24 từ ROADMAP gray areas + Iter 1 revision)

| # | Decision | Rationale |
|---|---|---|
| **D-V3.1-Phase2-A** | Backend filter cho GET /api/hubs (defense in depth) — KHÔNG dựa vào FE hide central | Stale JWT / FE bug / direct API call KHÔNG bypass; đối xứng `get_current_user_for_hub_access` Phase 3 v3.0 SSO-04 Layer 3 |
| **D-V3.1-Phase2-B** | 403 envelope `HUB_ADMIN_REQUIRED` riêng (KHÔNG reuse `FORBIDDEN`) + `CROSS_HUB_USER_DELETE_DENIED` mới (B1 iter 1 DELETE branch) | FE Phase 3 FE-01 có thể switch trên error.code; pattern Phase 3 SSO-04 + Phase 6 SETTINGS-03 carry forward |
| **D-V3.1-Phase2-C** | Audit log payload nest `actor_role` + `actor_hub_id` (KHÔNG schema migration audit_logs) | audit_logs.payload đã JSONB nullable đủ chứa; đối xứng pattern Plan 04-01 migration.role_seed nest |
| **D-V3.1-Phase2-D** | Hybrid dependency design — `assert_hub_admin_for(*, user, db, hub_id)` validator function (KHÔNG Depends factory) | Body param case (POST/PATCH với hub_id trong body) cần parse body trước check → inline validator linh hoạt hơn Depends factory |
| **D-V3.1-Phase2-E** | DELETE branch 3 trường hợp (B1 iter 1) — single-hub user-of-own → hub_admin pass; cross-hub user → super-only `CROSS_HUB_USER_DELETE_DENIED`; user-of-other-hub → `HUB_ADMIN_REQUIRED` | REQUIREMENTS.md DEP-03 literal text "Cross-hub admin operation chỉ super admin" honor đúng — single-hub DELETE hub_admin pass |
| **D-V3.1-Phase2-F** | Test coverage ≥ 80% trên file thay đổi (`--cov-fail-under=80`) | ROADMAP success criterion 5; pattern Phase 1 carry forward |
| **D-V3.1-Phase2-G** (B2 iter 1) | Defensive AUTH_STATE_INCONSISTENT invariant guard ở GET /api/hubs admin branch (≤15 line insert) | REQUIREMENTS DEP-02 literal "bỏ branch" honor qua defensive invariant — user role='admin' global + per-hub override = inconsistent state, 500 fail-loud |

## Trigger context (2026-05-23)

User bug report ngay sau `/gsd-complete-milestone v3.0`:
> "Tôi tạo user với quyền quản lý hub và select hub đỗ minh đường nhưng user đó lại vào được hub central và quản lý cả hub central. Tôi muốn user được gán hub nào thì chỉ vào được hub đó và quyền quản lý của hub con đó thôi."

Investigation finding (2026-05-23):
- `users.role` GLOBAL `admin | editor | viewer` (CHECK constraint `role_enum`) — không có `hub_admin` scope.
- Label UI "Admin Hub" (UserManagement.tsx:636) gây hiểu lầm — thực ra `role='admin'` = super-admin toàn hệ thống.
- `routers/hubs.py:73-77` bypass `user_hubs` filter cho admin → super admin thấy mọi hub.
- Mọi endpoint admin CRUD dùng `require_role("admin")` mà KHÔNG check hub scope.

Decision (2026-05-23 user accept): Proper fix thêm role `hub_admin` (option proper fix).

## v3.1 Planning Summary

| Phase | Wave | Objective | REQ-ID | Plans (estimate) | Status |
|-------|------|-----------|--------|------------------|--------|
| 1 | DB schema | role_enum mở rộng + user_hubs.role column + helper + seed migration | ROLE-01..04 (4) | 3-4 | ✅ DONE 2026-05-23 (3 plan) |
| 2 | Backend RBAC | require_hub_admin_for dep + GET /api/hubs filter + CRUD scope + audit | DEP-01..05 (5) | 4-5 | Not started |
| 3 | Frontend | UserManagement form 3 option + hub switcher hide central + edit modal disabled | FE-01..04 (4) | 3-4 | Not started |
| 4 | Migration + smoke | Idempotent + rollback + smoke E2E 4 scenario + closeout v3.1 | MIGRATE-01..02 (2) | 2-3 | Not started |

**Coverage:** 4/4 phase × ≥1 REQ; 15 REQ map 100% phase.

## Key Decisions (LOCKED 2026-05-23)

| # | Decision | Rationale |
|---|---|---|
| **D-V3.1-01** | GIỮ tên enum `admin` = super-admin toàn hệ thống (KHÔNG rename `super_admin`) | Tránh break v3.0 JWT chain + user_hubs + audit logs; thêm `hub_admin` mới + frontend label phân biệt |
| **D-V3.1-02** | `user_hubs.role` column nullable (NULL = inherit `users.role` global) | Per-hub override pattern; carry forward v4.0 schema sẵn; backward compat — existing rows preserve |
| **D-V3.1-03** | Carry forward v3.0 SSO Layer 3 — JWT hub_ids check đủ membership; thêm dependency mới verify role | KHÔNG đụng JWT schema (v3.0 SSO-03 LOCKED); dependency layer thêm role check |
| **D-V3.1-04** | Reset phase numbering về 1 | Precedent D9 v2.0 + D-V3-05 v3.0; milestone-level scoping clean |

## Phase 1 Results Summary (DONE 2026-05-23)

3 plan ship 4 REQ-ID ROLE-01..04:

- **Plan 01-01** (ROLE-01 + ROLE-02 + ROLE-03): Alembic migration `0006_role_hub_admin.py` mở rộng CHECK constraint `users.role` thêm `'hub_admin'` (4 value) + thêm column `user_hubs.role TEXT NULL` (per-hub override; NULL = inherit global) + audit_logs INSERT row `action='migration.role_seed'` với jsonb_build_object payload (migration_revision + admin_count + user_hubs_count + timestamp_utc). Idempotent qua introspect (`sa.inspect()`) — 3 STEP có guard skip-if-applied. downgrade() đầy đủ với defensive `RuntimeError` nếu có row `role='hub_admin'` tồn tại (E-V3.1-1 STOP trigger).
- **Plan 01-02** (ROLE-04): Module mới `api/app/auth/role.py` chứa `async def get_effective_role(session, user_id, hub_id) -> str` + `UserNotFoundError` defensive exception. Logic: SELECT user_hubs.role override → fallback users.role inherit global. Raw SQL via `sqlalchemy.text()` + named bind params (T-01-02-01 SQL injection mitigation). 6 unit test pytest PASS (4-case ROLE-04 + 1 defensive + 1 str args coverage). Phase 2 sẽ import để build `require_hub_admin_for(hub_id)` dependency (DEP-01).
- **Plan 01-03** (closeout): Integration test `tests/integration/test_migration_0006_idempotent.py` (5 test) cover 4 success criteria ROADMAP Phase 1 — runtime skip-if-no-DB pattern (Phase 4 MIGRATE-01 sẽ chạy bắt buộc). **SAFETY-CRITICAL DSN injection pattern (Iter 1 revision fix I-01 + I-02):** fixture monkeypatch `DATABASE_URL` env + `get_settings.cache_clear()` thay vì `cfg.set_main_option("sqlalchemy.url", ...)` (bị env.py:185-191 runtime OVERRIDE từ get_settings().database_url → caller's set_main_option BỊ IGNORE → test apply migration vào DB .env vd medinet_central, SAFETY BLOCKER). STATE.md + REQUIREMENTS.md + CLAUDE.md update.

**Carry forward patterns:**
- Alembic explicit raw SQL `op.execute()` + introspect guard (pattern Plan 04-01 v3.0).
- Audit_logs payload nest (KHÔNG migration column mới) — D-V3-Phase4-C2 v3.0 carry forward.
- Module separation: `api/app/auth/role.py` business logic role thuần; `dependencies.py` FastAPI wrapper (Phase 2 sẽ extend).
- Tên CHECK constraint introspect runtime (chống model/migration discrepancy `ck_users_role_enum` vs `role_enum`).
- **Alembic integration test DSN injection pattern (Iter 1 fix I-01):** monkeypatch env `DATABASE_URL` + `get_settings.cache_clear()` thay vì `Config.set_main_option("sqlalchemy.url", ...)` — bypass env.py:185-191 runtime override. Áp dụng cho mọi integration test Alembic Phase 4+ MIGRATE-01.

## Open Question (chốt ở /gsd-discuss-phase tương ứng)

- **GA-V3.1-A** (Phase 1): Migration backward compat — `users.role='admin'` map về super-admin semantic (KHÔNG rename) vs flag column `is_super_admin`. Khuyến nghị: giữ tên (D-V3.1-01 LOCKED carry forward).
- **GA-V3.1-B** (Phase 2): GET /api/hubs filter cho hub_admin — backend filter authoritative vs frontend UI hide central. Khuyến nghị: backend (defense in depth).
- **GA-V3.1-C** (Phase 4): Migration idempotent strategy — Alembic introspect via `sa.inspect()` vs PL/pgSQL DO block. Khuyến nghị: introspect.

## Accumulated Context (carry forward từ v3.0 + earlier)

**v3.0 shipped 2026-05-23:**
- 7 phase / 38 plan / 30 REQ-ID consumed (TOPO/FACTOR/SSO/SYNC/PROXY/SETTINGS/MIGRATE).
- Multi-DB physical topology + per-hub Alembic + cocoindex flow naming per-hub.
- Codebase factor 1 deploy nhiều lần với HUB_NAME + dynamic hub registration.
- Auth SSO JWKS + JWT `hub_ids` REQUIRED + `auth:blacklist:{jti}` + Layer 3 dependency.
- Cross-hub sync outbox + worker + 1 SQL aggregated + 6 Prometheus metric + admin replay.
- Caddy subpath route + frontend 1 build prefix detect + D6 EXPIRED + per-hub branding 4 hub.
- System settings sync HTTP pull + Redis pub/sub invalidate + X-Internal-Auth proxy.
- Migration blue/green per-hub + MCP re-point central aggregate + smoke E2E automated.

**Deferred items (v3.0 close):**
- podman-init-admin-issue (WSL Windows env-specific)
- Phase 06 HUMAN-UAT partial + VERIFICATION human_needed (visual smoke runtime defer ops handover)
- SEED-001 local embedding model (dormant v4.1)
- Visual regression smoke 4 hub × 11 trang React M2 COMPAT-01 (defer ops handover post-v3.0)

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-05-23 v3.1 milestone start) + `.planning/REQUIREMENTS.md` (v3.1 — 15 REQ-ID v1) + `.planning/ROADMAP.md` (v3.1 — 4 phase reset numbering)

**Core value (unchanged from v2.0/v3.0):** Ingestion tri thức Medinet phải tái hiện trung thực cấu trúc tài liệu nguồn — biến mọi tài liệu y tế / dược / HCNS thành chunk semantic giàu metadata. v3.1 đóng gap RBAC role-per-hub được defer v4.0 trong M2 — thêm role `hub_admin` để user "quản lý hub" CHỈ vào hub được gán.

**Mode:** YOLO · **Granularity:** Small (4 phase) · **Phase numbering:** Reset về 1 (D-V3.1-04)

**Carry forward triệt để v3.0:**
- Multi-DB topology + SSO JWKS + cross-hub sync + Caddy proxy + settings sync — UNCHANGED.
- JWT claim schema `aud + hub_ids` — UNCHANGED (D-V3-Phase3-E LOCKED carry forward).
- Audit log schema — extend payload, KHÔNG migration column mới (DEP-05 payload nest).
- MCP service / OAuth flow Phase 8.3 — UNCHANGED.
- Frontend per-hub branding + Caddy subpath route + 1 build prefix detect — UNCHANGED.

---

*State khởi tạo 2026-05-23 ở milestone v3.1 sau khi v3.0 shipped 100% COMPLETE. Phase 1 chưa start. Tham chiếu PROJECT.md + REQUIREMENTS.md + ROADMAP.md cùng commit.*
