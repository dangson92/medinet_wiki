---
phase: 03-frontend-form-refactor
gathered: 2026-05-24
status: Ready for planning
source: ROADMAP gray-area recommendations + auto-mode codebase audit (Phase 5 PROXY-04 pattern carry forward + Phase 2 DEP-01..05 backend contract)
---

# Phase 3: Frontend form refactor (FE) — Context

**Trigger:** Phase 2 v3.1 DONE 2026-05-24 (5 plan DEP-01..05 ship — `assert_hub_admin_for` validator + `HUB_ADMIN_REQUIRED` envelope + `CROSS_HUB_USER_DELETE_DENIED` + audit payload `actor_role` + `actor_hub_id` nest). Backend đã enforce role `hub_admin` per-hub scope; UI vẫn dùng `users.role: 'admin' | 'viewer'` cũ → user hub_admin KHÔNG tạo được, label "Admin Hub" gây hiểu lầm (UserManagement.tsx:635 hiện chỉ 2 radio admin/viewer). Phase 3 đóng gap UI ↔ backend contract.

**Auto-mode note:** `/gsd-discuss-phase 3` chạy trong `auto` mode (system reminder "Work without stopping" + project precedent Phase 2). 3 gray area ROADMAP §"Discuss-phase gray areas" lock theo recommendation đã có; ngoài ra audit codebase phát hiện 2 decision phụ (D-V3.1-Phase3-D `UserRole` type alias + Wave order) lock thêm.

<domain>
## Phase Boundary

**Trong scope Phase 3 (FE):**
- **FE-01:** `pages/UserManagement.tsx` form tạo user — radio group "Quyền" tách 3 option (KHÔNG còn "Admin Hub" mơ hồ): "Admin toàn hệ thống" (role='admin', warning banner màu vàng), "Quản lý hub này" (role='hub_admin', scope hub được chọn), "Viewer" (role='viewer'). Description ngắn dưới mỗi option.
- **FE-02:** Hub switcher (`Layout.tsx` sidebar header — KHÔNG có `HubSwitcher` component riêng; logic inline trong Layout hoặc fetch context) — dùng `currentUser.role + currentUser.hub_ids` filter danh sách. Non-super-admin: ẩn hub `central` + chỉ show hubs trong `currentUser.hub_ids`. Super admin thấy ALL.
- **FE-03:** Edit modal "Quản lý hub & quyền" (`handleOpenManageHub` UserManagement.tsx:203) — option "Admin toàn hệ thống" disabled cho hub_admin với tooltip "Cần Admin toàn hệ thống"; hub_admin chỉ assign hub_admin/viewer cho hub được gán quyền (Layer 2 defense — backend đã enforce qua `assert_hub_admin_for` Plan 02-01 + role escalation block Plan 02-03 T-02-02-E).
- **FE-04:** `services/api.ts` `UserRole` type alias mới `'admin' | 'hub_admin' | 'editor' | 'viewer'` (match Phase 1 migration 0006 CHECK constraint + Phase 2 Pydantic Literal extend); `UserAPI` interface thêm field `role: string` (BE Phase 2 đã return — type-only change KHÔNG runtime fetch); `mockData.ts` thêm 2-3 hub_admin user fixture (1 dmd + 1 tdt) cho dev mock + vitest pattern Phase 5 carry forward.

**Ngoài scope (defer Phase 4 v3.1 hoặc v4.0):**
- MIGRATE-01..02: Smoke E2E 4 scenario pytest httpx + closeout docs (Phase 4 v3.1).
- Visual regression smoke 4 hub × 11 trang (v4.0 ops handover — Phase 5 đã defer).
- Multi-role 1 user trong cùng hub (defer v4.0 — current schema 0006 mỗi user_hubs row 1 role).
- Role-per-resource ACL granular (defer v4.0 carry forward).
- Per-hub user CRUD UI redesign rộng hơn 3 endpoint touch (chỉ refactor form tạo + edit modal + hub switcher; existing list/detail giữ pattern hiện tại).
- `Login.tsx` / `Documents.tsx` / `Search.tsx` / 11 trang nội dung khác — KHÔNG touch (R-V3-2 minimal scope carry forward Phase 5 UI-SPEC §3).
- BE schema thêm field `hubs.is_central` hoặc `hubs.parent_hub_id` (scope creep — D-V3.1-Phase3-A reject).
- Fetch `/api/profile` riêng cho currentUser.role (scope creep — `api.me()` `/api/auth/me` đã trả role qua Phase 2 ship).

</domain>

<decisions>
## Implementation Decisions (LOCKED)

### D-V3.1-Phase3-A — Hub switcher central detection = hardcode slug `'central'` (KHÔNG schema migration)

**Recommendation từ ROADMAP §"Discuss-phase gray areas" GA-FE-A:** Slug hardcode `'central'` (chứ KHÔNG `is_central` boolean / `parent_hub_id IS NULL` computed).

**Lý do LOCKED:**
- Phase 5 PROXY-04 đã ship pattern `services/api.ts:46`: `CURRENT_HUB: string = PREFIX ?? 'central'` — chuỗi `'central'` đã là special slug throughout FE (branding fallback `getBranding('central')` `branding/central/index.ts`, Caddy regex `^/(yte|duoc|hcns)/api/(.*)$` exclude central path qua fall-through file_server).
- BE schema `hubs` table KHÔNG có column `is_central` hoặc `parent_hub_id` (audit `api/app/routers/hubs.py` + `app/schemas/hubs.py` 2026-05-24); thêm column = schema migration scope creep + cần Alembic migration 0007 mới = ngoài Phase 3 scope.
- T-5-02 (Tampering hub allowlist client-side) Phase 5 carry forward: FE allowlist + slug check chỉ là UX layer; backend Caddy regex + RBAC Plan 02-02 GET /api/hubs filter là trust boundary. Hub_admin tamper `hub.slug !== 'central'` DevTools KHÔNG bypass backend filter.
- Pattern consistency: 4 hub trong DB hiện tại (1 central + dmd + tdt + 2 ghost yte/duoc/hcns decorative per memory `project_real_hubs_deployment`) — slug field stable, KHÔNG rename. Hub mới qua `make hub-add` FACTOR-04 luôn có slug ≠ 'central' (RESERVED blacklist Plan 02-05 + 05-05 enforce).

**Impact downstream:**
- Plan 03-03 hub switcher logic: `currentUser.role === 'admin' ? allHubs : allHubs.filter(h => h.code !== 'central' && currentUser.hub_ids.includes(h.id))` (note `HubAPI.code` là slug field, KHÔNG `slug` literal — audit api.ts:503).
- Plan 03-01 KHÔNG cần BE type extend `HubAPI.is_central`.

### D-V3.1-Phase3-B — `currentUser.role` source = extend `UserAPI` interface (BE Phase 2 đã trả via `/api/auth/me`)

**Recommendation từ ROADMAP §"Discuss-phase gray areas" GA-FE-B:** AuthContext extend type cho field `role` đã có sẵn từ BE response (KHÔNG fetch `/api/profile` riêng).

**Lý do LOCKED:**
- Audit `contexts/AuthContext.tsx:32` 2026-05-24: `api.me()` đã call `GET /api/auth/me` returns `UserWithRoles = {user: UserAPI, roles: RoleAPI[]}` — type-only change.
- BE Phase 2 Plan 02-03 ship `routers/users.py` + `routers/auth.py` `/api/auth/me` đã trả `users.role` global (Pydantic `UserRole` Literal 4 value) qua `me` endpoint — runtime fix KHÔNG cần.
- `UserAPI` interface (services/api.ts:481-492) hiện thiếu field `role: string` — bug type-level (BE trả nhưng FE type KHÔNG declare). Plan 03-01 fix `UserAPI` thêm `role: UserRole` field; AuthContext consume qua `user.role`.
- Fetch `/api/profile` riêng = 1 extra round-trip mỗi load + race condition (login → setState user → fetch profile → potential mismatch). Type extend = 0 runtime overhead.
- M2 + v3.0 `currentUser` consumer 3 callsite (`UserManagement.tsx` super-admin check + future hub switcher filter Plan 03-03 + future edit modal disabled Plan 03-03) — đều cần `role` global; centralize qua `useAuth().user?.user?.role`.

**Impact downstream:**
- Plan 03-01: `services/api.ts:481-492` `UserAPI` interface thêm `role: UserRole`; `UserWithRoles.user.role` accessible (path qua nested wrapper).
- Plan 03-02/03: consumer dùng `const currentRole = user?.user?.role ?? 'viewer'` defensive default (handle loading state).

### D-V3.1-Phase3-C — Mock data ADD 2 hub_admin user fixture (1 dmd + 1 tdt) + vitest pattern carry forward

**Recommendation từ ROADMAP §"Discuss-phase gray areas" GA-FE-C:** Thêm sample hub_admin user vào `mockData.ts` cho dev test + vitest fixture.

**Lý do LOCKED:**
- `mockData.ts` audit 2026-05-24: 35 user MOCK_USERS hiện tại chỉ có role `'admin'` hoặc `'viewer'` (line 78-115) — KHÔNG có fixture `hub_admin` để dev test form 3-option + edit modal disabled + hub switcher filter scenario.
- Phase 5 vitest infrastructure ship (`frontend/src/__tests__/` + `frontend/src/services/__tests__/api.spec.ts` + `frontend/src/__tests__/Layout.spec.tsx`) — pattern carry forward Plan 03-04 closeout cho 3 component test (form 3 option + hub switcher filter + edit modal disabled). Cần fixture role mới.
- 2 user fixture đủ cover 2 real hub thật (`dmd` Đỗ Minh Đường + `tdt` Thuốc Dân Tộc per memory `project_real_hubs_deployment`); ghost hub `yte/duoc/hcns` không cần (D-V3.1-Phase3-A carry forward — UI hide central, ghost hub treat như real per allowlist).
- KHÔNG thêm user fixture role `'editor'` (defer — không có scenario UI Phase 3 touch).

**Impact downstream:**
- Plan 03-01: `mockData.ts` thêm `{id, name, email, role: 'hub_admin', hubId: '<dmd-uuid|tdt-uuid>', ...}` × 2 + JSDoc comment "v3.1 Phase 3 fixture — RBAC hub_admin scope".
- Plan 03-04: vitest test cover (1) form 3 option submit `role: 'hub_admin'` body, (2) hub switcher hub_admin user → filter central + chỉ thấy hub gán, (3) edit modal hub_admin user → admin option disabled với tooltip.

### D-V3.1-Phase3-D — `UserRole` type alias export central + 4 value match Phase 1 CHECK constraint

**Rationale (Claude codebase audit 2026-05-24):** UserManagement.tsx:37 hiện dùng inline literal `useState<'admin' | 'viewer'>('viewer')` — DUPLICATE type string, KHÔNG centralize. Phase 2 backend đã ship `UserRole = Literal["admin", "hub_admin", "editor", "viewer"]` (Pydantic `schemas/users.py` Plan 02-03); FE phải mirror chính xác.

**Lý do LOCKED:**
- Single source of truth tránh drift (Phase 1 migration 0006 CHECK constraint `('admin', 'hub_admin', 'editor', 'viewer')` ↔ BE Pydantic Literal ↔ FE type alias). Sai 1 chỗ → request POST `role='hub_admin'` qua FE bị BE 422 reject HOẶC BE accept role mới mà FE không hiển thị.
- `services/api.ts` ADD `export type UserRole = 'admin' | 'hub_admin' | 'editor' | 'viewer'` near `UserAPI` interface (line ~480); consumer import `import type { UserRole } from '../services/api'`.
- Phase 3 chỉ touch 3 component (UserManagement form state `newUserRole` + edit modal state `manageRole` + Layout hub switcher) — KHÔNG refactor toàn bộ M2/v3.0 callsite (scope minimal R-V3-2 carry forward).

**Impact downstream:**
- Plan 03-01: define `UserRole` + extend `UserAPI` + replace UserManagement.tsx:37 `useState<'admin' | 'viewer'>` → `useState<UserRole>`.
- Plan 03-02 + 03-03: import `UserRole` type ở 2 component khác (form + edit modal).

### D-V3.1-Phase3-E — Wave order = Plan 03-01 BLOCKING Wave 1 → Plan 03-02 + 03-03 parallel Wave 2 → Plan 03-04 closeout Wave 3

**Rationale:**
- Plan 03-01 ship `UserRole` type + `UserAPI.role` field + mockData fixture + AuthContext verify — type contract foundation; Plan 03-02 + 03-03 import từ Plan 03-01.
- Plan 03-02 (UserManagement form 3 option + warning banner) + Plan 03-03 (hub switcher filter + edit modal disabled) touch 2 file độc lập (`UserManagement.tsx` vs `Layout.tsx`) — parallel-able KHÔNG file conflict.
- Plan 03-04 closeout BLOCKING sau cả 2 (vitest test cover 3 component + docs update).

**Wave critical path:** 1 (1 plan BLOCKING) → 2 (2 plan parallel) → 3 (1 plan BLOCKING) = 4 plan total (match ROADMAP estimate "3-4 plan").

### Claude's Discretion

Plan-phase agent quyết định:
- File-level Plan 03-02 vs 03-03 split exact boundary (eg Plan 03-03 có thể split nhỏ hơn nếu Layout.tsx + UserManagement.tsx Manage modal cùng file modification thì gộp 1 plan; nếu separate file thì split — depends pattern).
- Test count / scenario chi tiết (vitest 6-10 test khuyến nghị; rộng hơn cũng OK).
- Error envelope handling FE side khi BE trả `HUB_ADMIN_REQUIRED` / `CROSS_HUB_USER_DELETE_DENIED` / `HUB_ID_REQUIRED` envelope (toast + form-level error + 403 redirect) — Phase 2 backend đã ship envelope; Plan 03-02 hoặc 03-03 add error.code switch UX.
- `Layout.tsx` hub switcher có cần extract thành `<HubSwitcher>` component riêng hay inline trong Layout — depend complexity.
- Loading state trong AuthContext (`isLoading`) handling khi `currentUser.role` chưa fetch — defensive default `?? 'viewer'` hay skeleton spinner.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### v3.1 Phase 3 prior artifacts (Phase 1 + Phase 2 carry forward)

- `Hub_All/.planning/phases/01-rbac-schema-migration/01-01-PLAN.md` — Migration 0006_role_hub_admin CHECK constraint `('admin', 'hub_admin', 'editor', 'viewer')` ship 2026-05-23 (Plan 01-01 ROLE-01..03).
- `Hub_All/.planning/phases/01-rbac-schema-migration/01-02-PLAN.md` — Helper `get_effective_role(user_id, hub_id)` ship 2026-05-23 (Plan 01-02 ROLE-04).
- `Hub_All/.planning/phases/02-backend-rbac-enforcement/02-CONTEXT.md` — 7 D-V3.1-Phase2-A..G LOCKED 2026-05-24.
- `Hub_All/.planning/phases/02-backend-rbac-enforcement/02-01-PLAN.md` — `assert_hub_admin_for` validator + envelope `HUB_ADMIN_REQUIRED` ship (Plan 02-01 DEP-01).
- `Hub_All/.planning/phases/02-backend-rbac-enforcement/02-03-PLAN.md` — users.py 4 endpoint scope + UserRole Literal extend + DELETE B1 iter 1 3-branch + envelope `CROSS_HUB_USER_DELETE_DENIED` (Plan 02-03 DEP-03 — Phase 3 FE consume).
- `Hub_All/.planning/phases/02-backend-rbac-enforcement/02-04-PLAN.md` — audit payload `actor_role` + `actor_hub_id` nest (Plan 02-04 DEP-05 — Phase 3 FE pass current role context).
- `Hub_All/.planning/phases/02-backend-rbac-enforcement/02-05-PLAN.md` — Closeout + W5 iter 1 FE breakage operator broadcast note (hub_admin GET /api/users yêu cầu hub_id query Phase 3 FE-04 đóng gap).

### v3.0 Phase 5 PROXY pattern (carry forward Frontend infrastructure)

- `Hub_All/.planning/phases/05-reverse-proxy-frontend-subpath/05-CONTEXT.md` — 16 D-V3-Phase5-A1..D4 LOCKED 2026-05-22 (frontend 1-build prefix detect + branding registry).
- `Hub_All/.planning/phases/05-reverse-proxy-frontend-subpath/05-UI-SPEC.md` — Visual design contract (4 hub branding + theme color delivery + Login state machine + Layout sidebar minimal scope R-V3-2).
- `Hub_All/.planning/phases/05-reverse-proxy-frontend-subpath/05-02-PLAN.md` — vitest Wave 0 install + `services/api.ts` prefix detect (`CURRENT_HUB = PREFIX ?? 'central'` line 46).
- `Hub_All/.planning/phases/05-reverse-proxy-frontend-subpath/05-03-PLAN.md` — Branding registry `branding/index.ts` + fallback `getBranding('central')` (D-V3.1-Phase3-A reference).

### v3.1 milestone-level

- `Hub_All/.planning/ROADMAP.md` — v3.1 RBAC hub_admin milestone (Phase 3 §"Phase 3 — Frontend form refactor (FE)" + Discuss-phase gray areas).
- `Hub_All/.planning/REQUIREMENTS.md` — FE-01..04 (4 REQ-ID) + DEP-01..05 backend contract Phase 2 carry forward.
- `Hub_All/.planning/STATE.md` — v3.1 progress (Phase 1 + Phase 2 DONE; Phase 3 next action).
- `Hub_All/CLAUDE.md` §3 D6 EXPIRED Phase 5 PROXY-03 (Frontend rewrite cho FE giờ acceptable).

### Frontend source files (audit 2026-05-24)

- `Hub_All/frontend/src/services/api.ts` — `UserAPI` interface (line 481-492 — THIẾU `role` field, Plan 03-01 fix); `UserWithRoles` interface (line 476-479); `api.me()` (line 168); `api.createUser` body shape (line 357); `CURRENT_HUB` (line 46); `HUB_CONFIG.allowlist` (line 23-28).
- `Hub_All/frontend/src/contexts/AuthContext.tsx` — `refreshUser()` line 25-43 call `api.me()`; AuthContext consume `user: UserWithRoles | null`.
- `Hub_All/frontend/src/pages/UserManagement.tsx` — Form line 322 + 372 + 635 + 639 (2 radio admin/viewer); Manage modal line 200-210 `handleOpenManageHub`; `newUserRole` state line 37; `manageRole` state line ~200.
- `Hub_All/frontend/src/Layout.tsx` — Sidebar header line 1-65; KHÔNG có HubSwitcher inline yet (Plan 03-03 add); `getBranding(CURRENT_HUB)` line 34; `useAuth()` import line 28.
- `Hub_All/frontend/src/mockData.ts` — `MOCK_USERS` line 78-115 (35 user role admin|viewer); `Hub`/`User` type import line 1.
- `Hub_All/frontend/src/__tests__/Layout.spec.tsx` + `frontend/src/services/__tests__/api.spec.ts` — vitest Phase 5 pattern carry forward Plan 03-04.
- `Hub_All/frontend/vitest.config.ts` — jsdom env + `frontend/src/test-setup.ts` jest-dom matchers (Phase 5 Plan 05-02 ship).

### Backend source files (Phase 2 ship — FE consume contract)

- `Hub_All/api/app/schemas/users.py` — `UserRole = Literal["admin", "hub_admin", "editor", "viewer"]` Plan 02-03 ship (FE mirror Plan 03-01).
- `Hub_All/api/app/routers/users.py` — 4 endpoint refactor scope (POST create + PATCH role + GET list HUB_ID_REQUIRED + DELETE 3-branch); error envelope code list.
- `Hub_All/api/app/auth/dependencies.py` — `assert_hub_admin_for` validator Plan 02-01 ship; envelope `HUB_ADMIN_REQUIRED` body shape (FE error.code switch consume).

### Memory references (user-level cross-session)

- `memory/project_rbac_hub_admin_gap.md` — v3.1 milestone trigger 2026-05-23 + 'admin' = GLOBAL super-admin bypass invariant.
- `memory/project_real_hubs_deployment.md` — 2 hub thật DB (dmd Đỗ Minh Đường + tdt Thuốc Dân Tộc); yte/duoc/hcns decorative ghost (D-V3.1-Phase3-C mockData fixture chỉ 2 user thật).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets (Phase 5 PROXY pattern carry forward)

- **`useAuth()` hook (`contexts/AuthContext.tsx:80`)** — Đã expose `user: UserWithRoles | null` + `isAuthenticated` + `isLoading`. Plan 03-02/03 consume `useAuth().user?.user?.role` (path nested) cho currentRole check.
- **`getBranding(CURRENT_HUB)` (`branding/index.ts`)** — Phase 5 PROXY-04 ship; Plan 03-03 hub switcher KHÔNG đụng (branding scope ≠ filter scope).
- **`CURRENT_HUB` const (`services/api.ts:46`)** — `PREFIX ?? 'central'` runtime resolve; Plan 03-03 dùng compare `h.code === CURRENT_HUB` highlight active hub trong switcher.
- **vitest infrastructure (`frontend/vitest.config.ts`)** — Phase 5 Plan 05-02 install (`vitest@^2 + @testing-library/react@^16 + @testing-library/jest-dom@^6 + jsdom@^25`); Plan 03-04 add 3 test file mới cùng pattern.
- **`MOCK_USERS` (`mockData.ts`)** — 35 user fixture; Plan 03-01 append 2 hub_admin user (KHÔNG modify existing 35).

### Established Patterns

- **State-by-page** — UserManagement.tsx line 37 inline `useState<'admin' | 'viewer'>('viewer')` per-component; KHÔNG dùng Zustand/Redux. Plan 03-01 + 03-02 mirror pattern qua `useState<UserRole>('viewer')`.
- **Form error envelope handle** — Phase 5 Plan 05-04 ship Login.tsx error toast; UserManagement existing `handleCreateUser` error path qua `.error?.message` (KHÔNG switch `.error?.code` — Plan 03-02 add code switch cho 4 envelope mới Phase 2: HUB_ADMIN_REQUIRED + HUB_ID_REQUIRED + CROSS_HUB_USER_DELETE_DENIED + AUTH_STATE_INCONSISTENT).
- **Type imports** — `services/api.ts` exports `Hub`, `User`, `UserWithRoles`, `UserAPI`, `RoleAPI`, `HubAPI` etc.; centralize Plan 03-01 thêm `UserRole` export.
- **Radio group HTML** — UserManagement.tsx:635 + 639 inline `<input type="radio" name="role" value="admin">` Tailwind class `text-accent focus:ring-accent`; Plan 03-02 mở rộng 3 option + warning banner cùng pattern (KHÔNG dùng shadcn/ui RadioGroup component — KHÔNG có).
- **Hub list fetch** — `services/api.ts:listHubs` callsite trong UserManagement.tsx (for hub_id select dropdown); Plan 03-03 hub switcher Layout.tsx reuse `api.listHubs()` HOẶC fetch context (depends complexity).

### Integration Points

- **`AuthContext` → `UserAPI.role`** — Plan 03-01 type extend; AuthContext.tsx:32 KHÔNG cần code change (BE đã trả role qua `/api/auth/me`).
- **`UserManagement.tsx` form → BE POST `/api/users`** — Body `{email, name, password, hub_id, role: UserRole}`; Phase 2 Plan 02-03 đã accept `role='hub_admin'` runtime (Pydantic Literal extend ship). Plan 03-02 chỉ đổi UI label + radio group, body shape KHÔNG đổi.
- **`Layout.tsx` sidebar → `api.listHubs()`** — Plan 03-03 fetch hub list (đã có endpoint Phase 2 Plan 02-02 filter cả admin), filter qua `currentUser.hub_ids` (super-admin bypass).
- **Edit modal `handleOpenManageHub` → BE PATCH `/api/users/{id}/role`** — Phase 2 Plan 02-03 endpoint scope; FE Plan 03-03 chặn UI assign admin (defense in depth — BE đã block T-02-02-E role escalation).
- **vitest test files → mock `MOCK_USERS` + mock `api.*`** — Phase 5 Plan 05-02 pattern carry forward; Plan 03-04 3 test file (form-3-option.spec.tsx + hub-switcher-filter.spec.tsx + edit-modal-disabled.spec.tsx).

### Constraint (R-V3-2 carry forward Phase 5 minimal scope)

- **CHỈ touch 3 component** — `UserManagement.tsx` form + Manage modal, `Layout.tsx` sidebar, `services/api.ts` + `mockData.ts` + `AuthContext.tsx` (verify only). KHÔNG cascade tất cả M2/v3.0 component (R-V3-2 mitigation — visual regression risk control).
- **KHÔNG đụng** Dashboard / Documents / Search / Ask / Settings / Login / 11 trang nội dung khác.
- **Tailwind class consistency** — Reuse `text-accent focus:ring-accent` cho radio; warning banner pattern `bg-yellow-50 border-yellow-200 text-yellow-800` (Phase 5 Login.tsx Plan 05-04 carry forward `bg-{themeColor}-50` analog).
- **vitest jsdom env LOCKED** — Plan 03-04 KHÔNG switch test runner.

</code_context>

<specifics>
## Specific Ideas

### Form 3 option layout (Plan 03-02 ref UI-SPEC.md Phase 5 §5 pattern)

```
○ Admin toàn hệ thống      [⚠ Quyền cao nhất — quản lý toàn bộ hệ thống]
  Có thể quản lý tất cả hub, user, settings. Cảnh báo: gán cho user TIN CẬY.

○ Quản lý hub này          [Chỉ trong hub được chọn]
  Quản lý user + document trong hub được chỉ định. KHÔNG vào hub khác.

● Viewer                   [Chỉ đọc]
  Xem document + search trong hub được gán. KHÔNG quản lý user.
```

Warning banner color yellow (Tailwind `bg-yellow-50 border-yellow-200 text-yellow-800`) — chỉ hiển thị khi `newUserRole === 'admin'`.

### Edit modal disabled UX (Plan 03-03)

Khi `currentUser.role !== 'admin'` (currentUser là hub_admin) mở Manage modal cho user khác:
- Option "Admin toàn hệ thống" disabled với attribute `disabled` + Tailwind `opacity-50 cursor-not-allowed`.
- Tooltip pattern `title="Cần Admin toàn hệ thống"` (hoặc Tailwind tooltip plugin nếu có — defer Claude discretion).

### Hub switcher (Plan 03-03 Layout.tsx sidebar)

Vị trí: ABOVE sidebar nav (giữa logo branding + nav items list). Pattern dropdown chứa list hub được filter:
- Super admin: ALL hubs từ `api.listHubs()`.
- Hub_admin / viewer: `hubs.filter(h => h.code !== 'central' && currentUser.hub_ids.includes(h.id))`.
- Active hub highlighted (compare `h.code === CURRENT_HUB`).
- Click → navigate `window.location.href = '/${h.code}/'` (full reload — Phase 5 PROXY pattern carry forward, KHÔNG SPA navigate vì cần re-fetch BE với hub_name khác).

### mockData hub_admin fixture (Plan 03-01)

```typescript
// v3.1 Phase 3 fixture — RBAC hub_admin scope (project_real_hubs_deployment: dmd + tdt)
{ id: 'u-hadmin-dmd', name: 'Nguyễn Hub Admin DMD', email: 'hadmin.dmd@medinet.vn', role: 'hub_admin', hubId: '<dmd-uuid>', createdAt: '01/05/2026', lastLogin: '1 giờ trước', status: 'active' },
{ id: 'u-hadmin-tdt', name: 'Trần Hub Admin TDT', email: 'hadmin.tdt@medinet.vn', role: 'hub_admin', hubId: '<tdt-uuid>', createdAt: '01/05/2026', lastLogin: '30 phút trước', status: 'active' },
```

UUID placeholder dmd/tdt — Plan 03-01 resolve qua `MOCK_HUBS` lookup `code === 'dmd'` → `id`.

</specifics>

<deferred>
## Deferred Ideas

- **`HubSwitcher` extract component** — Nếu Plan 03-03 Layout.tsx sidebar logic complex hơn ~30 LOC, extract `<HubSwitcher>` riêng `frontend/src/components/HubSwitcher.tsx`. Claude discretion plan time.
- **Loading skeleton AuthContext** — Hiện `useAuth().isLoading` boolean; UI cảnh hiện cho consumer treat `isLoading` UNCHANGED Phase 3 (Login redirect + spinner thấy bằng Layout đã có). Skeleton refinement defer v4.0 UX polish.
- **`role='editor'` UI fixture** — Không có scenario UI Phase 3 touch; defer khi v4.0 per-resource ACL ship (editor write access granular).
- **Per-resource ACL fine-grained** — `documents.created_by` filter cho viewer/editor read-only scope (defer v4.0 carry forward backlog).
- **i18n EN/VN switch UI** — Hiện tất cả label tiếng Việt hardcode; defer v4.0 i18n framework.
- **Tooltip plugin Tailwind** — Phase 3 dùng native `title="..."` attribute (default browser tooltip); defer v4.0 nếu cần custom tooltip styling.
- **Form validation client-side rich** — Phase 3 reuse pattern hiện tại (basic HTML `required` + browser validation + server error envelope). Rich validation (formik / react-hook-form) defer v4.0.
- **Multi-role 1 user trong cùng hub** — Schema migration 0006 mỗi `user_hubs` row 1 role override; multi-role defer v4.0.
- **Visual regression smoke 4 hub × 11 trang** — Phase 7 v3.0 carry forward defer v4.0 ops handover.

</deferred>

---

*Phase: 03-frontend-form-refactor*
*Context gathered: 2026-05-24 via /gsd-discuss-phase 3 auto-mode (3 gray area ROADMAP recommendation LOCKED + 2 decision phụ codebase audit)*
