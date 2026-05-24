---
gsd_state_version: 1.0
milestone: v3.1
milestone_name: RBAC hub_admin
status: "🚧 v3.1 STARTED 2026-05-23 — defining requirements + roadmap. Trigger: user bug report 2026-05-23 sau v3.0 close — tạo user gán hub `dmd` nhưng vẫn vào được central (gap thiết kế role-per-hub defer v4.0 trong M2). Scope: 4 phase / 15 REQ-ID / phase numbering reset về 1 (D-V3.1-04). Memory reference: project_rbac_hub_admin_gap."
last_updated: "2026-05-23T18:00:00.000Z"
progress:
  total_phases: 4
  completed_phases: 1
  total_plans: 15  # estimate ~12-15 plan
  completed_plans: 3
  percent: 20
milestone_status: "STARTED"
milestone_start_date: "2026-05-23"
next_action: "/gsd-discuss-phase 2 — DEP backend RBAC enforcement (require_hub_admin_for dependency + GET /api/hubs filter + CRUD scope)"
---

# State — MEDWIKI (v3.1)

**Mã dự án:** MEDWIKI
**Milestone:** v3.1 — RBAC hub_admin
**Ngày bắt đầu:** 2026-05-23 (sau khi v3.0 shipped 100% COMPLETE 38/38 plan + 30/30 REQ-ID consumed)
**Last updated:** 2026-05-23

## Current Position

🚧 **v3.1 STARTED 2026-05-23** — Defining requirements + roadmap. 4 phase / 15 REQ-ID v1 / phase numbering reset về 1 (precedent D9 v2.0 + D-V3-05 v3.0).

- **Phase:** Not started (defining requirements)
- **Plan:** — (sẽ tạo qua `/gsd-plan-phase 1`)
- **Status:** Requirements + roadmap defined; awaiting `/gsd-discuss-phase 1` ROLE migration.
- **Next Action:** `/gsd-discuss-phase 1` ROLE — Alembic migration 0006_role_hub_admin + user_hubs.role column + helper get_effective_role + migration seed.

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
