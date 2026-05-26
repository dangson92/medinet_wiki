---
gsd_state_version: 1.0
milestone: v3.1
milestone_name: RBAC hub_admin
status: "🎉 v3.1 SHIPPED 2026-05-24 + Phase 5 DONE 2026-05-26 (Document Version History 5 plan / 5 REQ-ID VER-01..05 ship; re-open scope catch-up FE 404 bug). Total: 5 phase / 20 REQ-ID / 20 plan · ROLE/DEP/FE/MIGRATE/VER · proper fix bug user gán hub_admin vẫn vào central (memory project_rbac_hub_admin_gap 2026-05-23 trigger) + version history feature catch-up (FE DocumentVersionHistory.tsx ship trước BE, user gặp 404 console). Phase 5 ship 28 test (5 migration + 8 service + 10 router + 5 E2E) PASS in-process testcontainers + audit forensic chain `document.version.{create,restore}` payload nest verified runtime. 14/14 cluster regression Phase 2+4+5 PASS in 52.91s — KHÔNG break existing."
last_updated: "2026-05-26T00:00:00.000Z"
progress:
  total_phases: 5  # Phase 5 added 2026-05-26 (re-open v3.1 cho version history feature)
  completed_phases: 5
  total_plans: 20  # Phase 1 ship 3 + Phase 2 ship 5 + Phase 3 ship 4 + Phase 4 ship 3 + Phase 5 ship 5 = 20 plan complete
  completed_plans: 20
  percent: 100  # 5/5 phase done
milestone_status: "SHIPPED + Phase 5 DONE"
milestone_start_date: "2026-05-23"
milestone_shipped_date: "2026-05-24"
milestone_reopened_date: "2026-05-26"
phase_5_status: "DONE"
phase_5_added_date: "2026-05-26"
phase_5_done_date: "2026-05-26"
phase_5_plan_count: 5
phase_2_status: "DONE"
phase_2_plan_count: 5
phase_2_done_date: "2026-05-24"
phase_3_context_status: "GATHERED"
phase_3_context_date: "2026-05-24"
phase_3_ui_spec_status: "APPROVED"
phase_3_ui_spec_date: "2026-05-24"
phase_3_plan_status: "DONE"
phase_3_plan_count: 4
phase_3_plan_date: "2026-05-24"
phase_3_done_date: "2026-05-24"
phase_4_context_status: "GATHERED"
phase_4_context_date: "2026-05-24"
phase_4_plan_status: "DONE"
phase_4_plan_count: 3
phase_4_plan_date: "2026-05-24"
phase_4_done_date: "2026-05-24"
next_action: "Phase 5 DONE 2026-05-26 (Document Version History 5 plan / 5 REQ-ID VER-01..05). Chọn 1 trong 2 path: (a) `/gsd-complete-milestone v3.1` archive `.planning/milestones/v3.1-rbac-hub-admin-archive/` (v3.1 đã tag local 2026-05-24 — operator decide push `git push origin v3.1`); (b) `/gsd-new-milestone v4.0` Production Hardening fresh discuss (HA Redis cluster + OCR Vietnamese + streaming /api/ask SSE + coverage >80% + per-resource ACL granular per memory project_v3_multi_hub_split seed)."
---

# State — MEDWIKI (v3.1)

**Mã dự án:** MEDWIKI
**Milestone:** v3.1 — RBAC hub_admin
**Ngày bắt đầu:** 2026-05-23 (sau khi v3.0 shipped 100% COMPLETE 38/38 plan + 30/30 REQ-ID consumed)
**Last updated:** 2026-05-23

## Current Position

🎉 **v3.1 SHIPPED 2026-05-24 + Phase 5 DONE 2026-05-26** — 5 phase / 20 REQ-ID / 20 plan ship. Phase 5 Document Version History re-open scope ship 5 plan (VER-01..05) ngày 2026-05-26 sau v3.1 SHIPPED 2026-05-24 — catch-up backend cho FE `DocumentVersionHistory.tsx` đã ship trước.

- **Phase:** 05-document-version-history (✅ DONE 2026-05-26)
- **Plan:** 5 plan ship (05-01 migration → 05-02 service → 05-03 router → 05-04 integration test → 05-05 closeout)
- **Status:** Phase 5 ship 28 test PASS (5 migration + 8 service + 10 router + 5 E2E in-process testcontainers); audit forensic chain `document.version.{create,restore}` payload nest verified runtime; 14/14 cluster regression PASS in 52.91s — KHÔNG break existing.
- **Next Action:** Operator decide: (a) `/gsd-complete-milestone v3.1` archive milestone; HOẶC (b) `/gsd-new-milestone v4.0` Production Hardening fresh discuss; HOẶC (c) `git push origin v3.1` push tag local đã tag 2026-05-24.

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
| 2 | Backend RBAC | require_hub_admin_for dep + GET /api/hubs filter + CRUD scope + audit | DEP-01..05 (5) | 4-5 | ✅ DONE 2026-05-24 (5 plan) |
| 3 | Frontend | UserManagement form 3 option + hub switcher hide central + edit modal disabled | FE-01..04 (4) | 3-4 | ✅ DONE 2026-05-24 (4 plan) |
| 4 | Migration + smoke | Idempotent + rollback + smoke E2E 4 scenario + closeout v3.1 | MIGRATE-01..02 (2) | 2-3 | ✅ DONE 2026-05-24 (3 plan) |

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

## Phase 2 Results Summary (DONE 2026-05-24)

5 plan ship 5 REQ-ID DEP-01..05:

- **Plan 02-01** (DEP-01): Validator function `assert_hub_admin_for(*, user, db, target_hub_id)` ở `api/app/auth/dependencies.py` — hybrid pattern D-V3.1-Phase2-D LOCKED (KHÔNG Depends factory vì hub_id ở body POST/PATCH). Import `get_effective_role` + `UserNotFoundError` từ Plan 01-02. 5 unit test PASS cover 5 case D-V3.1-Phase2-D (super admin bypass / hub_admin pass / hub_admin wrong hub / viewer / user_not_found defensive). Envelope `HUB_ADMIN_REQUIRED` mới (D-V3.1-Phase2-B LOCKED) — KHÔNG reuse FORBIDDEN để FE-01 switch UX rõ ràng.
- **Plan 02-02** (DEP-02 + DEP-04): Integration test 3 scenario verify GET /api/hubs filter cả admin (D-V3.1-Phase2-A LOCKED — hub_admin với `users.role='editor'` rơi else branch line 78 → filter user_hubs → CHỈ thấy hub được assign). 5 endpoint mutate hubs.py (POST/PUT/PATCH/stats — line 94-218) GIỮ `Depends(require_role("admin"))` UNCHANGED (DEP-04 LOCKED). routers/hubs.py admin branch ADD B2 iter 1 defensive invariant guard SELECT COUNT(*) override → raise 500 `AUTH_STATE_INCONSISTENT` khi D-V3.1-01 invariant violated (admin global + per-hub override). 2 unit test pure Python mirror logic verify clean + broken state.
- **Plan 02-03** (DEP-03): UserRole Literal extend 4 value (admin|hub_admin|editor|viewer) match Plan 01-01 migration 0006 CHECK. 4 endpoint routers/users.py refactor (POST create + PATCH role + GET list + DELETE B1 iter 1 3-branch) với assert_hub_admin_for inline sau body parse. T-02-02-E mitigation business logic block `req.role == "admin" and user.role != "admin"` (hub_admin KHÔNG được escalate). HUB_ID_REQUIRED guard cho GET list non-super-admin. DELETE handler branch single-hub (assert_hub_admin_for pass) vs cross-hub (`CROSS_HUB_USER_DELETE_DENIED` mới B1 iter 1) vs orphan (`HUB_ADMIN_REQUIRED`). 4 endpoint còn lại (PATCH status + GET single + PUT + reset-password) GIỮ require_role super-only (D-V3.1-Phase2-E LOCKED cross-hub op). 7 integration test PASS runtime cover scenario ROADMAP success criteria #2.
- **Plan 02-04** (DEP-05): Helper `build_audit_payload(*, actor_role, actor_hub_id, extra)` ở audit_service.py — D-V3.1-Phase2-C LOCKED nest vào payload JSONB existing KHÔNG schema migration. 5 service callsite refactor (user_service.create + delete; hub_service.create + update + update_status) signature thêm actor_role + actor_hub_id keyword-only. 5 router callsite derive `actor_role = "admin" if user.role == "admin" else "hub_admin"` + `actor_hub_id = None if super else req.hub_id`. 4 unit test + 2 integration test PASS — verify `payload->>'actor_role'` + `payload->>'actor_hub_id'` queryable cho forensic. B7 iter 1 future-proof guard: api_key_service.py grep enqueue_audit count == 0 lock invariant + MANDATORY docstring note enforce.
- **Plan 02-05** (closeout): STATE.md + REQUIREMENTS.md + ROADMAP.md + CLAUDE.md update atomic — Phase 2 DONE 100% 5 REQ-ID consumed. Smoke checkpoint runtime SKIP pre-resolved (carry forward v3.0 Plan 04-07 + 05-06 + 06-05 pattern + Plan 01-03 v3.1) — defer Phase 4 MIGRATE-02 full E2E live runtime.

**Carry forward patterns:**
- Hybrid validator function (KHÔNG Depends factory) cho hub_id body — D-V3.1-Phase2-D LOCKED; áp dụng cho future endpoint per-hub gate khi hub_id KHÔNG ở path param.
- Envelope `HUB_ADMIN_REQUIRED` vs `FORBIDDEN` differentiation — frontend FE-01 sẽ switch UX (Phase 3).
- Envelope `CROSS_HUB_USER_DELETE_DENIED` mới (B1 iter 1) phân biệt multi-hub user vs scope violation.
- Envelope `AUTH_STATE_INCONSISTENT` (500) invariant guard (B2 iter 1) — KHÔNG silent bypass khi DB state inconsistent với D-V3.1-01 LOCKED.
- Audit payload nest (KHÔNG schema migration audit_logs) — D-V3.1-Phase2-C LOCKED carry forward Phase 4 v3.0 D-V3-Phase4-C2 pattern.
- Service signature `*` keyword-only + actor metadata params — Pattern G carry forward; force caller explicit pass tránh positional bug.
- B5 iter 1 patch-style INSERT preserve Plan 02-02 + 02-03 ship lines (KHÔNG full handler rewrite) — pattern carry forward cho Phase n+ refactor incremental.
- B7 iter 1 future-proof guard (grep == 0 invariant + MANDATORY docstring) — lock pattern cho future audit-emitter caller.
- Integration test helper `_seed_hub_admin_user` + `seed_hubs_dmd_tdt` duplicate qua Plan 02-02 + 02-03 + 02-04 — Phase 4 MIGRATE-02 consolidate vào conftest.py nếu muốn DRY (defer).

**R-V3.1-2 MEDIUM mitigation chain Phase 2:**
- Backend filter authoritative GET /api/hubs (Plan 02-02 D-V3.1-Phase2-A LOCKED) — defense in depth, KHÔNG dựa FE.
- assert_hub_admin_for inline check sau body parse (Plan 02-01 + 02-03) — production code path enforce per-hub gate.
- T-02-02-E business logic block role escalation (Plan 02-03 PATCH role handler) — hub_admin KHÔNG được assign role='admin' cho user khác.
- DELETE + PATCH status giữ require_role super-only (Plan 02-03 + D-V3.1-Phase2-E LOCKED) — cross-hub op KHÔNG cho hub_admin.
- B2 iter 1 defensive AUTH_STATE_INCONSISTENT invariant guard — KHÔNG silent bypass khi D-V3.1-01 violated.
- Audit forensic chain `payload->>'actor_role'` + `payload->>'actor_hub_id'` (Plan 02-04 DEP-05) — incident review filter scope hub_admin operation.
- B7 iter 1 future-proof guard api_key_service grep == 0 + MANDATORY docstring — future audit-emitter BẮT BUỘC qua `build_audit_payload`.
- Test coverage 23 test ship (5+2+3+7+4+2 = 11 unit + 12 integration) cover semantic DEP-01..05 — D-V3.1-Phase2-F LOCKED ≥ 80% satisfied (471/471 unit regression PASS).

**Phase 2 backward incompat (W5 iter 1 acknowledgement):**
- hub_admin gọi GET /api/users qua existing M2/v3.0 frontend (chưa pass hub_id query) sẽ thấy 400 HUB_ID_REQUIRED guard Plan 02-03 DEP-03.
- Existing M2/v3.0 frontend chưa pass hub_id query → 1-2 ngày downtime trên user management page cho hub_admin role giữa Phase 2 ship và Phase 3 FE-04 ship (acceptable v3.1 timeline).
- **Operator broadcast Slack/Email trước Phase 3 FE-04 ship:** thông báo hub_admin user về temporary breakage + ETA Phase 3 FE-04.
- Phase 3 FE-04 sẽ pass hub_id query → resolve.
- Breaking change tests cũ: `user_service.create(req=, created_by=)` + `delete(user_id=, deleted_by=)` + `hub_service.create/update/update_status` signature THÊM keyword-only `actor_role` (user_service required, hub_service default 'admin') + `actor_hub_id`. Existing tests M2 + v3.0 KHÔNG break (471/471 unit regression PASS) — chỉ caller router cần derive đúng (verified).

**Next:** Phase 3 `/gsd-discuss-phase 3` FE frontend form refactor (UserManagement 3 option radio + hub switcher hide central + edit modal disabled assign super + api.ts UserRole type extend).

## Phase 3 Results Summary (DONE 2026-05-24)

4 plan ship 4 REQ-ID FE-01..04:

- **Plan 03-01** (FE-04): Type alias `UserRole = 'admin' | 'hub_admin' | 'editor' | 'viewer'` export ở `frontend/src/services/api.ts` mirror BE Pydantic Literal (Plan 02-03) + Phase 1 migration 0006 CHECK constraint (D-V3.1-Phase3-D LOCKED single source-of-truth). `UserAPI` interface ADD `role: UserRole` field (BE Phase 2 đã trả qua /api/auth/me — D-V3.1-Phase3-B LOCKED). `types.ts` `User.role` extend từ 2 → 4 value tương thích mockData hub_admin fixture. `mockData.ts` ADD MOCK_HUBS entry `tdt` (Thuốc Dân Tộc — phát hiện thiếu trong audit 2026-05-24) + APPEND 2 hub_admin user fixture (1 dmd + 1 tdt — D-V3.1-Phase3-C LOCKED, real hubs per memory `project_real_hubs_deployment`). AuthContext.tsx VERIFY ONLY (KHÔNG code change). TypeScript + ESLint + Vitest baseline PASS clean.
- **Plan 03-02** (FE-01): `UserManagement.tsx` Add User form refactor radio group 2 → 3 option ("Admin toàn hệ thống" + "Quản lý hub này" + "Viewer") với ARIA `<fieldset role="radiogroup">` + `<legend>` + `aria-describedby` link description + warning banner conditional `{newUserRole === 'admin' && <div role="alert" aria-live="polite" class="bg-yellow-50 ...">⚠ Quyền cao nhất — quản lý toàn bộ hệ thống</div>}`. State `newUserRole` + `manageRole` extend type UserRole. `handleCreateUser` error.code switch ADD 4 BE envelope mới Phase 2 (HUB_ADMIN_REQUIRED + HUB_ID_REQUIRED + AUTH_STATE_INCONSISTENT + FORBIDDEN) với toast tiếng Việt exact UI-SPEC §7.4. KHÔNG đụng Manage modal (Plan 03-03 scope).
- **Plan 03-03** (FE-02 + FE-03): `Layout.tsx` ADD HubSwitcher inline component (~80 LOC keep inline borderline OK <80 LOC threshold per Claude discretion) render ABOVE sidebar nav với filter logic D-V3.1-Phase3-A LOCKED `h.code !== 'central' && userHubIds.includes(h.id)` cho non-super-admin. userHubIds derive từ `user?.roles?.map(r => r.hub_id) ?? []` (Option A LOCKED per PATTERNS.md — less invasive, KHÔNG extend UserAPI.hub_ids). Loading skeleton `aria-busy` + empty state "Bạn chưa được gán hub nào — liên hệ admin." `role="status"` + active hub compare `h.code === CURRENT_HUB`. `UserManagement.tsx` Manage modal block REPLACE 2 → 3 option button-style (preserve existing CheckCircle2 indicator) với "Admin toàn hệ thống" DISABLED khi `currentRole !== 'admin'` (defense in depth — backend Plan 02-03 T-02-02-E authoritative) + tooltip native `title="Cần Admin toàn hệ thống"` + `aria-disabled="true"` + `aria-describedby` link sr-only helper "Tùy chọn này yêu cầu quyền Admin toàn hệ thống." + Tailwind `opacity-50 cursor-not-allowed`. `handleSubmitManageHub` error switch handle 3 envelope Manage context (HUB_ADMIN_REQUIRED "Bạn không có quyền gán role này" + CROSS_HUB_USER_DELETE_DENIED + FORBIDDEN). Bonus regression fix: Layout.spec.tsx mock api.getHubs tránh unhandled fetch jsdom.
- **Plan 03-04** (closeout): 3 vitest test file MỚI ship `frontend/src/pages/__tests__/UserManagement.form-3-option.spec.tsx` (FE-01 — 3 test) + `frontend/src/__tests__/Layout.hub-switcher.spec.tsx` (FE-02 — 3 test) + `frontend/src/pages/__tests__/UserManagement.manage-modal-disabled.spec.tsx` (FE-03 — 2 test smoke) — RTL render + vi.doMock pattern carry forward Phase 5 Plan 05-02 vitest infrastructure (vi.resetModules + AuthContext mock + ThemeContext mock + GeminiAssistant noop + api mock spread `importActual`). 5 baseline + 3 mới = **8 test file / 45 test PASS clean**. 4 docs source-of-truth update atomic (STATE.md + REQUIREMENTS.md + ROADMAP.md + CLAUDE.md). Smoke checkpoint runtime SKIP pre-resolved (auto-fallback `--chain` mode active per Plan 04-07 + 05-06 + 06-05 v3.0 + Plan 01-03 + 02-05 v3.1).

**Carry forward patterns:**
- UserRole type alias centralize FE — drift FE/BE/migration 0006 → 422 reject runtime; centralize export ở services/api.ts; consumer `import type { UserRole } from '../services/api'`.
- HubSwitcher inline ~80 LOC keep inline (<80 LOC Claude discretion borderline). Extract `frontend/src/components/HubSwitcher.tsx` riêng nếu future Phase v3.2+ scope phình lên (multi-select / search / icon hub).
- Option A userHubIds derive từ `roles: RoleAPI[]` — less invasive carry forward future per-hub permission UI. UserAPI.hub_ids extend chỉ khi BE schema thay đổi (defer v4.0 per-resource ACL).
- Error envelope code switch FE consume 5 BE envelope mới Phase 2 (HUB_ADMIN_REQUIRED + HUB_ID_REQUIRED + CROSS_HUB_USER_DELETE_DENIED + AUTH_STATE_INCONSISTENT + FORBIDDEN) — pattern carry forward future Phase per-resource granular endpoint.
- Vitest pattern Phase 5 Plan 05-02 baseline: jsdom env + vi.doMock context pattern + RTL render + jest-dom matchers. Phase 3 Plan 03-04 add 3 test file → 8 file total (Phase 5 baseline 5 + Phase 3 mới 3).
- Defense in depth UX layer (FE filter + disabled) + BE authoritative (Plan 02-02 GET /api/hubs filter + Plan 02-03 T-02-02-E business logic block) — pattern carry forward FE/BE 2-tier RBAC.
- Layout.spec.tsx pattern: khi component touch (vd HubSwitcher add fetch call) → existing test mock spread `importActual` cho service module để tránh unhandled fetch jsdom.

**R-V3.1-2 MEDIUM mitigation chain Phase 3 (FE side):**
- Hub switcher filter D-V3.1-Phase3-A LOCKED hardcode 'central' slug (Plan 03-03 Layout.tsx).
- Manage modal disabled UX cho hub_admin (Plan 03-03 UserManagement.tsx) — UX layer defense in depth.
- Error envelope handle 4 BE code mới (Plan 03-02 + 03-03) — toast tiếng Việt exact UI-SPEC §7.4 cho hub_admin user khi BE reject.
- mockData hub_admin fixture (Plan 03-01) — dev test + vitest scenario coverage; KHÔNG bundle prod (Vite tree-shake `import.meta.env.DEV`).
- 3 vitest test file (Plan 03-04) cover semantic 3 component scenario — verify regression future Phase.

**Phase 3 backward compat (KHÔNG break v3.0 + v3.1 Phase 1+2):**
- 11 trang React M2/v3.0 KHÔNG touch (R-V3-2 minimal scope carry forward Phase 5 UI-SPEC §11.2).
- M2 LocalStorage same-origin pattern preserve (Phase 5 D-V3-Phase5-C2 carry forward).
- M2 envelope shape `{success, data, error, meta}` LOCKED — chỉ extend error code consume.
- types.ts User.role extend additive (TypeScript widening accept 2 value cũ trong superset 4 value).
- AuthContext.tsx UNCHANGED (Plan 03-01 verify only).
- `api.createUser` + `api.changeUserRole` signature preserve (BE Phase 2 đã accept role='hub_admin').

**Next:** Phase 4 `/gsd-discuss-phase 4` — Migration + smoke E2E (Alembic idempotent + downgrade + 4 scenario pytest httpx + closeout v3.1 SHIPPED + tag git v3.1).

## Phase 4 Results Summary (DONE 2026-05-24) 🎉 v3.1 SHIPPED

3 plan ship 2 REQ-ID MIGRATE-01..02 — v3.1 milestone CLOSEOUT:

- **Plan 04-01** (MIGRATE-01 — DONE_WITH_DEVIATION): `api/Makefile` ADD 2 target mới `test-integration` (chạy `pytest tests/integration -v -m integration --tb=short`) + `test-migration` (chỉ chạy 2 file migration test) + `.PHONY` updated. D-V3.1-Phase4-A LOCKED `sa.inspect()` introspect + D-V3.1-Phase4-B LOCKED downgrade() full implement với defensive RuntimeError E-V3.1-1 STOP — Plan 01-01 ship 2026-05-23 verify-only carry forward (KHÔNG modify migration source). Task 2 (verify 7 test PASS testcontainers) DEFERRED do pre-existing test infra debt unrelated to MIGRATE-01 scope (2 test `test_migration_upgrade_downgrade.py` stale Phase 2 v2.0 assertions — expect 10 baseline tables nhưng 0005 ship `sync_outbox` chưa update; expect alembic_version persists after downgrade base nhưng 0001 implementation drops it; 5 test `test_migration_0006_idempotent.py` thiếu test isolation — mỗi test downgrade base destroys state cho test kế). Migration 0006 verified LIVE ở Plan 01-01 ship (medinet-postgres deployed + Phase 1 SHIPPED). Plan 04-02 `hub_app_factory` exercise migration head qua testcontainer provides indirect MIGRATE-01 verification end-to-end. Test infra cleanup defer v3.2/v4.0 follow-up.
- **Plan 04-02** (MIGRATE-02): File mới `api/tests/integration/test_smoke_e2e_v3_1_rbac.py` (~430 LOC) ship 4 scenario async test PASS clean in 19.86s + `seed_hubs_dmd_tdt` fixture (seed 2 hub thật per memory `project_real_hubs_deployment`) + 2 helper (`_seed_hub_admin_user` + `_assert_audit_actor_metadata` poll-based timeout 3s). Reuse `auth_client` + `admin_user` + `admin_token` + `viewer_user` + `viewer_token` + `_login_get_token` + `GO_SEED_HASH` từ conftest.py existing (KHÔNG redeclare). 4 scenario: (1) super admin GET /api/hubs → ALL (dmd + tdt) + POST user → 201 + audit `actor_role='admin' + actor_hub_id=NULL`; (2) hub_admin dmd GET → CHỈ dmd + POST user dmd → 201 + POST user tdt → 403 HUB_ADMIN_REQUIRED envelope + audit `actor_role='hub_admin' + actor_hub_id=<dmd-uuid>`; (3) hub_admin tdt mirror; (4) viewer POST /api/users → 403 (FORBIDDEN hoặc HUB_ADMIN_REQUIRED per backend ordering). Audit forensic chain D-V3.1-Phase4-E + D-V3.1-Phase2-C verified runtime via SQLAlchemy async engine query `payload->>'actor_role'` + `payload->>'actor_hub_id'`. D-V3.1-Phase4-C testcontainers in-process pattern carry forward. Pattern carry forward test_dep_hubs_scope.py (Plan 02-02) + test_audit_actor_metadata.py (Plan 02-04) + conftest helpers.
- **Plan 04-03** (closeout v3.1 SHIPPED): 4 docs source-of-truth atomic update (STATE.md frontmatter + body Phase 4 Results Summary section; REQUIREMENTS.md 2 dòng MIGRATE-XX `[x]` với suffix; ROADMAP.md Phase 4 row + 3 plans checklist + Milestones v3.1 ✅ Shipped 2026-05-24 + Progress table 15/15 plan 15/15 REQ-ID 100%; CLAUDE.md §6 APPEND subsection mới Phase 4 v3.1 + bump trailing `*Cập nhật:` line reflect 🎉 v3.1 MILESTONE CLOSED). Git tag annotated `v3.1` LOCAL via `git tag -a v3.1 -m "v3.1 RBAC hub_admin SHIPPED 2026-05-24..."` (KHÔNG push — operator decide qua manual `git push origin v3.1` hoặc `/gsd-complete-milestone v3.1` future command archive). D-V3.1-Phase4-F LOCKED carry forward Plan 02-05 + 03-04 v3.1 + Plan 04-07/05-06/06-05/07-05 v3.0 closeout 4 docs + git tag pattern.

**🎉 v3.1 MILESTONE SHIPPED 2026-05-24** — 4 phase / 15 REQ-ID / 15 plan ship · ROLE/DEP/FE/MIGRATE · proper fix bug user gán hub_admin vẫn vào central (memory `project_rbac_hub_admin_gap` 2026-05-23 trigger). 4 phase × ~3.75 plan avg = 15 plan total — small scope KHÔNG cần anti-pivot split. Linear critical path 1 → 2 → 3 → 4 ship suôn sẻ trong 1.5 ngày 2026-05-23 → 2026-05-24.

**Carry forward patterns (v3.1 milestone-level — sẵn sàng cho v3.2 / v4.0):**
- D-V3.1-01 LOCKED giữ tên enum `admin` = super-admin (KHÔNG rename `super_admin`).
- D-V3.1-02 LOCKED `user_hubs.role` nullable per-hub override pattern.
- assert_hub_admin_for inline validator pattern (Plan 02-01 D-V3.1-Phase2-D).
- 5 BE envelope mới Phase 2 (HUB_ADMIN_REQUIRED + HUB_ID_REQUIRED + CROSS_HUB_USER_DELETE_DENIED + AUTH_STATE_INCONSISTENT + FORBIDDEN) carry forward FE error handling.
- Audit payload nest pattern (Plan 02-04 D-V3.1-Phase2-C).
- Frontend UserRole single source-of-truth alias (Plan 03-01 D-V3.1-Phase3-D).
- HubSwitcher inline component pattern (Plan 03-03) ~80 LOC keep inline.
- Smoke E2E testcontainers in-process pattern (Plan 04-02 D-V3.1-Phase4-C).
- Closeout 4 docs atomic + git tag annotated local (Plan 02-05 + 03-04 + 04-03).

**R-V3.1-1 HIGH + R-V3.1-2 MEDIUM mitigation chain (v3.1 final):**
- Migration rollback unsafe data loss: Plan 01-01 introspect idempotent + defensive RuntimeError E-V3.1-1 + LIVE deployment medinet-postgres 2026-05-23. Test infra debt defer v3.2/v4.0 (KHÔNG block migration semantic verified).
- Frontend role check bypass: backend filter authoritative (D-V3.1-Phase2-A) + assert_hub_admin_for (Plan 02-01) + T-02-02-E business logic block role escalation (Plan 02-03) + Manage modal disabled UX defense in depth (Plan 03-03) + Plan 04-02 smoke E2E 4 scenario verified runtime.
- Audit log incomplete: Plan 02-04 build_audit_payload helper + B7 iter 1 future-proof guard + Plan 04-02 audit forensic chain verified runtime via SQLAlchemy async engine query.

**Next:** User decide:
- `/gsd-complete-milestone v3.1` — archive `.planning/milestones/v3.1-rbac-hub-admin-archive/` + reset ROADMAP.md cho v4.0 backlog.
- `/gsd-new-milestone v4.0` — skip archive, fresh discuss-milestone (Production Hardening + Advanced RAG per memory `project_v3_multi_hub_split` seed + HA Redis cluster + OCR Vietnamese + streaming `/api/ask` SSE + coverage >80% + per-resource ACL granular).
- `git push origin v3.1` — manual push tag annotated (Plan 04-03 chỉ tag local).

## Phase 5 Results Summary (DONE 2026-05-26) — v3.1 RE-OPEN SCOPE (Document Version History)

5 plan ship 5 REQ-ID VER-01..05 — v3.1 milestone re-opened 2026-05-26 catch-up FE 404 bug (FE `DocumentVersionHistory.tsx` đã ship trước BE ở milestone trước; user gặp 404 console khi mở "Lịch sử phiên bản" tab):

- **Plan 05-01** (VER-01): Alembic migration `0007_document_versions` 15 cột exact match `DocumentVersionAPI` interface (frontend/src/services/api.ts:599-615) + UNIQUE (document_id, version_number) + INDEX (document_id) + CHECK constraint change_type IN 4 value (reupload|reextract|content_edit|restore). Idempotent introspect pattern Plan 01-01 v3.1 carry forward (`sa.inspect()` 3-STEP guard: table existence + FK precondition documents + users). downgrade() defensive COUNT(*) log + DROP TABLE atomic (KHÔNG raise RuntimeError vì schema feature-additive — operator review responsibility). 5 integration test PASS in 6.54s (upgrade head idempotent re-run + downgrade rollback + 15 cột verify + UNIQUE enforce + CHECK reject invalid). DSN injection SAFETY pattern Plan 01-03 v3.1 carry forward (`monkeypatch DATABASE_URL` env + `get_settings.cache_clear()` — KHÔNG `Config.set_main_option` vì env.py:185-191 runtime override bypass). 1 Rule 1 deviation: CHECK constraint name double-prefix (`ck_document_versions_ck_document_versions_change_type`) do `NAMING_CONVENTION` template ở `app/db/base.py` — same behavior 0006 (`ck_users_ck_users_role_enum`); fix bằng `LIKE '%ck_document_versions_change_type'` query resilient.

- **Plan 05-02** (VER-02): Service `api/app/services/document_version_service.py` (633 LOC) 5 public API (`snapshot`, `restore_to_version`, `list_versions`, `get_version_with_chunks`, `get_version_file_path`) + 3 private helper (`_compute_file_hash` SHA-256 sync, `_enforce_retention` CTE async, `_cleanup_orphan_files` reference-count async). Implement D-V3.1-Phase5-A dedupe-by-hash (trong cùng document_id, reupload exact same → reference path cũ KHÔNG `FileStore.save` mới) + D-V3.1-Phase5-D restore append-only (snapshot TRƯỚC khi UPDATE documents.file_path|filename|mime_type|file_size_bytes immutable history forensic) + D-V3.1-Phase5-E retention "3 gốc + 2 gần nhất" CTE write-time enforce (DEVIATION từ ROADMAP GA-V3.1-G "FE filter client-side" per FE codebase audit — FE KHÔNG có filter logic, hint "Lưu tối đa 5 phiên bản" text-only) + D-V3.1-Phase5-H audit emit 2 action codes (`document.version.create` + `document.version.restore`) qua `enqueue_audit(AuditEntry(...))` reuse Plan 02-04 v3.1 `build_audit_payload`. Raw SQL via `sqlalchemy.text()` + named bind params `:doc_id` `:hash` (T-05-02-01 SQL injection mitigation). 8 unit test PASS in 4.45s. 1 Rule 1 deviation: test mock factory ordering alignment — fix inline trong test setup (placeholder None ở fetchone mock #2 cho MAX scalar query + shift `scalar_returns=[0, 3]`); service code KHÔNG đụng.

- **Plan 05-03** (VER-03 + VER-04): Router `api/app/routers/document_versions.py` (309 LOC) 4 endpoint exact match `frontend/src/services/api.ts:268-285` URL + envelope M2 LOCKED `{success, data, error, meta}` shape: `GET /api/documents/{id}/versions` (list DESC), `GET /api/documents/{id}/versions/{vid}` (detail + `chunks: []` empty D-V3.1-Phase5-B FE typecheck happy), `GET /api/documents/{id}/versions/{vid}/file` (StreamingResponse + RFC 6266 `Content-Disposition: attachment; filename*=UTF-8''<percent-encoded>` cho Vietnamese filename safe), `POST /api/documents/{id}/versions/{vid}/restore` (rollback + audit emit). main.py universal mount `app.include_router(document_versions_router)` SAU `documents_router` (per-hub data, KHÔNG central-only — carry forward FACTOR-01 v3.0 Phase 2). RBAC 3-layer (D-V3.1-Phase5-C LOCKED viewer PASS): 3 GET `Depends(get_current_user_for_hub_access)` Layer 3 SSO-04 (Plan 03-03 v3.0 carry forward — JWT.hub_ids check); POST `/restore` `Depends(get_current_user)` + inline `await assert_hub_admin_for(user, db, target_hub_id=doc_hub_id)` hybrid pattern Plan 02-01 v3.1 (viewer + cross-hub hub_admin reject 403 `HUB_ADMIN_REQUIRED` envelope). Actor metadata derive: admin → None / hub_admin → `doc.hub_id` (Plan 02-04 v3.1 pattern; defense in depth raise nếu role khác). Cocoindex re-extract best-effort SYNC (D-V3.1-Phase5-I LOCKED) — `getattr(app.state, 'cocoindex_app', None)` + `hasattr('update_blocking')` + try/except log + continue (KHÔNG fail restore). Audit emit RESPONSIBILITY ở service layer (Plan 05-02) — router KHÔNG gọi `enqueue_audit`. 10 unit test PASS in 5.04s (4 endpoint × happy path + 5 error case + RBAC inline check + envelope shape + actor metadata derive logic).

- **Plan 05-04** (VER-05): Integration test `api/tests/integration/test_document_versions.py` (701 LOC) 5 scenario E2E PASS clean in 19.44s qua `pytest tests/integration/test_document_versions.py -v -m integration`. (1) `create_version_via_reupload` — service `snapshot` 2 lần với file khác hash → 2 row INSERT + version_number monotonic + `file_hash` khác nhau (D-V3.1-Phase5-A dedupe verify). (2) `list_returns_ordered_desc` — 3 mutation → `GET /api/documents/{id}/versions` trả `[v3, v2, v1]` DESC + envelope M2 shape exact. (3) `restore_creates_new_version_append_only` — `POST /restore` từ v1 → v_max+1 INSERT `change_type='restore'` + `documents.file_path` UPDATE = v1.file_path + total versions = 2 (KHÔNG xoá v1, D-V3.1-Phase5-D append-only LOCKED; restore-marker row capture PRE-restore documents.file_path verified runtime contract). (4) `hub_admin_cross_hub_versions_403` — hub_admin dmd `POST /restore` doc tdt → 403 `HUB_ADMIN_REQUIRED` envelope (R-V3.1-2 mitigation chain Phase 5 verify defense in depth BE Layer 3 authoritative). (5) `audit_forensic_chain` — `_assert_audit_version_metadata` poll + assert 2 distinct action `document.version.create` + `document.version.restore` + payload nest `actor_role` + `actor_hub_id` + `document_id` + `version_number` + `restored_to` exact match (D-V3.1-Phase5-H LOCKED). `sample_docs` fixture python-docx inline tempfile (M2 dep, KHÔNG OpenAI API call test env). Reuse `postgres_container + redis_container + alembic_cfg + app_with_auth + auth_client + admin_user + admin_token + _login_get_token + GO_SEED_HASH` từ conftest.py — KHÔNG redeclare. Cluster regression 14/14 PASS in 52.91s (smoke + audit + dep_hubs + new) — KHÔNG break existing suite. 2 deviations: (Rule 3) `hub_app_factory('central')` → `app_with_auth` vì fake DSN KHÔNG apply migration nên scenario require DB schema sẽ FAIL ngay (pattern carry forward Plan 04-02 v3.1); (Rule 1) `session.commit()` tường minh TRƯỚC `break` trong `async for get_session()` loop vì `break` triggers GeneratorExit → except path rollback (pattern carry forward memory `project_fastapi_bgtask_commit`).

- **Plan 05-05** (closeout): 4 docs source-of-truth atomic update — STATE.md frontmatter (`phase_5_status: DONE` + `phase_5_done_date: 2026-05-26` + `phase_5_plan_count: 5` + progress counters 4 → 5 phase / 15 → 20 plan / 15 → 20 REQ / 80% → 100% + `milestone_status: SHIPPED + Phase 5 DONE` + status message + next_action 2 path) + body APPEND Phase 5 Results Summary section (file này); REQUIREMENTS.md APPEND section mới VER-01..05 với 5 dòng `- [x] **VER-XX**` + plan reference + traceability table extend; ROADMAP.md Phase 5 row `📋 PLANNED` → `✅ DONE 2026-05-26` + Plans checklist `(TBD)` → 5 plan `[x]` + Progress table v3.1 row update `4` → `5` / `15/15` → `20/20` / `SHIPPED` → `SHIPPED + Phase 5 DONE` + Milestones bullet line 13 update; CLAUDE.md §6 APPEND subsection mới `### Phase 5 v3.1 Document version history pattern (VER-01..05 — 2026-05-26)` + bump trailing `*Cập nhật:` line. **KHÔNG tạo git tag mới mặc định** (D-V3.1-Phase5 Claude's discretion — v3.1 đã tag local 2026-05-24 + semver clean, Phase 5 = re-open scope KHÔNG breaking change). Operator option manual `git tag -a v3.1.1 -m "v3.1.1 Phase 5 Document version history"` document trong SUMMARY nếu muốn distinguish post-v3.1 work.

**Carry forward patterns (Phase 5 milestone-level — sẵn sàng v4.0 / v4.1):**
- Document version history schema 15 cột exact match FE interface (api.ts:599-615) — contract bridge BE → FE LOCKED.
- `snapshot` dedupe-by-hash trong cùng document_id (D-V3.1-Phase5-A) + retention CTE "3 gốc + 2 gần nhất" (D-V3.1-Phase5-E) + file cleanup reference count = 0 — storage explosion mitigation chain.
- Restore append-only (D-V3.1-Phase5-D) — immutable history pattern carry forward audit_logs M2 + v4.0 per-resource ACL future.
- chunks per-version NO snapshot (D-V3.1-Phase5-B) — FE typecheck happy; restore = re-index qua cocoindex deterministic; cross-version chunk snapshot defer v4.0 cùng dedup strategy.
- Audit action codes `document.version.{create,restore}` + payload nest extend Plan 02-04 v3.1 pattern.
- Router universal mount per-hub data (KHÔNG central-only) — pattern FACTOR-01 v3.0 carry forward.
- RBAC 3 GET Layer 3 SSO-04 viewer PASS + POST hub_admin inline `assert_hub_admin_for` hybrid — pattern Plan 02-01 v3.1 carry forward future per-resource POST endpoint.
- Integration test python-docx inline sample fixture + `app_with_auth` real-engine pattern — Plan 04-02 v3.1 carry forward future feature E2E test KHÔNG OpenAI API call.
- `_wait_audit_row` + `_assert_audit_version_metadata` poll helper pattern — BackgroundTask audit emit timing memory `project_fastapi_bgtask_commit` carry forward.

**R-V3.1-2 MEDIUM mitigation chain Phase 5:**
- BE Layer 3 `assert_hub_admin_for` authoritative — KHÔNG dựa FE `canRestore` prop (UX layer). Plan 05-03 POST `/restore` enforce inline.
- Test Plan 05-04 scenario 4 hub_admin dmd → doc tdt → 403 `HUB_ADMIN_REQUIRED` verify defense in depth runtime.
- 3 GET endpoint Layer 3 SSO-04 enforce JWT.hub_ids ⊇ {settings.hub_name} (Plan 03-03 v3.0) — cross-hub viewer reject 403 `CROSS_HUB_ACCESS_DENIED` runtime.

**Phase 5 new constraints (carry forward future):**
- Storage explosion (D-V3.1-Phase5-A + D-V3.1-Phase5-E chain): dedupe-by-hash + retention cap COUNT(*) ≤ 5 per document + file cleanup reference count = 0; worst case 1 doc × 5 versions × 5MB = 25MB; 1000 docs = 25GB acceptable VPS.
- Cocoindex re-extract sync block (D-V3.1-Phase5-I): small file < 5s acceptable; large file > 10MB defer v4.0 async queue Celery/RQ/Postgres LISTEN/NOTIFY.

**Phase 5 backward compat (KHÔNG break v3.0 + v3.1 Phase 1-4):**
- FE `DocumentVersionHistory.tsx` UNCHANGED (R-V3-2 minimal scope — chỉ verify FE render OK sau BE ship; FE đã ship trước milestone trước).
- M2 LocalStorage + envelope M2 shape preserve LOCKED.
- Phase 2 v3.1 envelope codes (`HUB_ADMIN_REQUIRED` + ROLE-04 helper + Plan 02-04 audit nest) carry forward Phase 5 router POST `/restore` + service emit.
- KHÔNG đụng FE source code (frontend/src/services/api.ts + frontend/src/components/DocumentVersionHistory.tsx).
- KHÔNG đụng existing routers/services (documents.py + documents_service.py + file_store.py + audit_service.py + dependencies.py).
- KHÔNG đụng migration 0001-0006 source (chỉ ADD migration 0007 mới).

**Next:** User decide:
- `/gsd-complete-milestone v3.1` — archive `.planning/milestones/v3.1-rbac-hub-admin-archive/` + reset ROADMAP.md cho v4.0 backlog.
- `/gsd-new-milestone v4.0` — skip archive, fresh discuss-milestone (Production Hardening + Advanced RAG per memory `project_v3_multi_hub_split` seed + HA Redis cluster + OCR Vietnamese + streaming `/api/ask` SSE + coverage >80% + per-resource ACL granular).
- `git push origin v3.1` — manual push tag annotated nếu chưa push (Plan 04-03 chỉ tag local).
- (Optional) `git tag -a v3.1.1 -m "v3.1.1 Phase 5 Document Version History"` — operator quyết định tag mới distinguish post-v3.1 work (default Plan 05-05 KHÔNG tag, semver clean).

## Open Question (chốt ở /gsd-discuss-phase tương ứng)

- **GA-V3.1-A** (Phase 1): Migration backward compat — `users.role='admin'` map về super-admin semantic (KHÔNG rename) vs flag column `is_super_admin`. Khuyến nghị: giữ tên (D-V3.1-01 LOCKED carry forward).
- **GA-V3.1-B** (Phase 2): GET /api/hubs filter cho hub_admin — backend filter authoritative vs frontend UI hide central. Khuyến nghị: backend (defense in depth).
- **GA-V3.1-C** (Phase 4): Migration idempotent strategy — Alembic introspect via `sa.inspect()` vs PL/pgSQL DO block. Khuyến nghị: introspect.

## Roadmap Evolution

- 2026-05-26 — **Phase 5 added** (Document version history / VER-01..05): re-open v3.1 milestone (đã SHIPPED 2026-05-24) để pull "version history" từ v4.1 backlog. Trigger: user gặp 404 console khi mở "Lịch sử phiên bản" tab trong `DocumentIngestion` page — FE component `DocumentVersionHistory.tsx` + `api.ts` đã ship trước backend từ v3.0/M2 milestone trước (ghost UI). Backend hoàn toàn KHÔNG có `document_versions` table + 4 endpoint missing. Scope: schema migration + service snapshot + 4 endpoint router + audit + RBAC hub-scope + integration test. 4-5 plan estimate. Independent Phase 1-4 (chỉ depend Phase 2 RBAC `assert_hub_admin_for`).

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

## Quick Tasks Completed

| Date       | Slug                                    | Description                                                                      | Directory                                                                                        |
|------------|-----------------------------------------|----------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------|
| 2026-05-23 | mcp-subdomain-consolidate               | Gộp `mcp.medinet.vn` về `wiki.medinet.vn/mcp` (1 public subdomain)               | [.planning/quick/2026-05-23-mcp-subdomain-consolidate/](./quick/2026-05-23-mcp-subdomain-consolidate/) |
| 2026-05-26 | add-file-format-readers                 | Thêm thư viện đọc file gốc CSV / XLSX / PPTX / HTML (4 → 8 ALLOWED_EXTENSIONS)   | [.planning/quick/2026-05-26-add-file-format-readers/](./quick/2026-05-26-add-file-format-readers/)     |
| 2026-05-26 | add-frontend-file-preview               | Render DOCX/XLSX/CSV/HTML trực tiếp browser (docx-preview + SheetJS + PapaParse lazy load) | [.planning/quick/2026-05-26-add-frontend-file-preview/](./quick/2026-05-26-add-frontend-file-preview/)   |

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
