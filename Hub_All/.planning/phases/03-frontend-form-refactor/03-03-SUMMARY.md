---
phase: 03
plan: 03
wave: 2
shipped: 2026-05-24
status: DONE
commits:
  - 20fa235 feat(03-03) FE-02 hub switcher + FE-03 Manage modal disabled Admin cho hub_admin
requirements_satisfied: [FE-02, FE-03]
decisions_implemented:
  - D-V3.1-Phase3-A  # Hub switcher central detection = hardcode slug 'central'
  - D-V3.1-Phase3-B  # currentUser.role source qua useAuth
  - D-V3.1-Phase3-D  # UserRole + HubAPI type import
files_modified:
  created: []
  modified:
    - frontend/src/Layout.tsx
    - frontend/src/pages/UserManagement.tsx
    - frontend/src/__tests__/Layout.spec.tsx  # regression fix
tests:
  vitest_baseline: "5 file / 37 test PASS clean (0 unhandled rejection)"
  typescript_build: "PASS clean"
---

# Plan 03-03 — Summary (Wave 2 sequential SAU 03-02)

**Mục tiêu:** FE-02 hub switcher sidebar filter + FE-03 Manage modal disabled Admin option cho hub_admin (defense in depth UX layer trên BE Plan 02-03 T-02-02-E business logic block authoritative).

## Deliverable

### 1. `frontend/src/Layout.tsx` (modify — FE-02)

**Imports** (line 30):
- REPLACE `import { CURRENT_HUB } from './services/api'` → `import { api, CURRENT_HUB } from './services/api'` + `import type { UserRole, HubAPI } from './services/api'`.

**HubSwitcher component inline module-level** (~80 LOC inline keep — Claude discretion <80 threshold borderline OK):
- `useAuth()` consume `user` + `isLoading`; derive `currentRole: UserRole` + `userHubIds: string[]` từ `roles?.map(r => r.hub_id) ?? []` (Option A LOCKED).
- `useState<HubAPI[]>([])` + `useEffect` fetch `api.getHubs()` mount-time với cleanup `mounted` flag.
- Filter logic D-V3.1-Phase3-A LOCKED: super admin show ALL; non-super-admin `h.code !== 'central' && userHubIds.includes(h.id)`.
- 3 render branch: loading skeleton `aria-busy="true"` + empty state `role="status"` + dropdown `<select aria-label="Chọn hub đang xem">`.
- onChange → `window.location.href = /${e.target.value}/` (full reload, Phase 5 PROXY carry forward).
- Active hub = `value={CURRENT_HUB}` compare.
- Copywriting tiếng Việt exact UI-SPEC §7.2: "Hub đang xem:" + "Bạn chưa được gán hub nào — liên hệ admin."

**Render** (~line 215 area, sau sidebar header `</div>` đóng):
- `{(!collapsed || isMobileMenuOpen) && <HubSwitcher />}` — visible khi sidebar expanded.

### 2. `frontend/src/pages/UserManagement.tsx` (modify — FE-03)

**Manage modal role selector block** (~line 1025-1061 cũ → replace):
- IIFE `(() => { ... })()` wrap để derive `currentRoleInline` + `isCurrentSuper` từ `currentUser?.user?.role` once.
- 3 button-style option (preserve existing pattern CheckCircle2 indicator):
  1. **Admin toàn hệ thống** — `disabled={!isCurrentSuper}` + `aria-disabled` + native `title="Cần Admin toàn hệ thống"` (chỉ khi disabled) + `aria-describedby="manage-admin-tooltip-desc"` link sr-only helper + Tailwind `opacity-50 cursor-not-allowed` (defense in depth UX).
  2. **Quản lý hub này** (hub_admin) — luôn enable.
  3. **Viewer** — luôn enable.
- sr-only helper `<p id="manage-admin-tooltip-desc" className="sr-only">Tùy chọn này yêu cầu quyền Admin toàn hệ thống.</p>` chỉ mount khi `!isCurrentSuper`.

**handleSubmitManageHub error switch** (~line 208-210 cũ → replace):
- Extract `const code = failed[0].error?.code`.
- Switch 3 envelope Manage context exact UI-SPEC §7.4 (KHÁC form context Plan 03-02):
  - `HUB_ADMIN_REQUIRED` → "Bạn không có quyền gán role này. Liên hệ Super Admin."
  - `CROSS_HUB_USER_DELETE_DENIED` → "Không thể xóa user thuộc nhiều hub. Liên hệ Super Admin để xử lý."
  - `FORBIDDEN` → "Bạn không có quyền thực hiện thao tác này."
- Generic fallback `${failed.length}/${results.length} cập nhật thất bại.` preserve.

### 3. `frontend/src/__tests__/Layout.spec.tsx` (regression fix)

- ADD `vi.doMock('../services/api', ...)` mock `api.getHubs` return empty array — HubSwitcher mới mount gọi `api.getHubs()` gây unhandled fetch jsdom KHÔNG resolve relative URL `/yte/api/hubs`. Mock đủ giữ Phase 5 baseline 4 test PASS clean (0 unhandled rejection).
- Preserve actual `CURRENT_HUB` const compute từ `window.location` (qua `importActual` spread).

**KHÔNG đụng:**
- Add User form (Plan 03-02 ship).
- List table, search, pagination, delete confirm dialog.
- Sidebar logo + branding header line 166-215 (Phase 5 PROXY-04 carry forward).
- Nav items list logic, logout/theme/notification button.
- handleOpenManageHub, handleDeleteUser, handleEditUser khác.

## Tests

- `npx tsc --noEmit` exit 0.
- `npm run test -- --run` exit 0 — **5 baseline file / 37 test PASS clean** (0 unhandled rejection sau regression fix Layout.spec.tsx).

## Architecture insights

- **HubSwitcher inline ~80 LOC borderline OK** — Plan-time estimate ~60 LOC; thực tế ~85 LOC (3 render branch loading/empty/dropdown). Vẫn keep inline (extract `frontend/src/components/HubSwitcher.tsx` defer khi future v3.2+ scope phình lên: multi-select / search / icon hub).
- **Option A userHubIds derive (roles[].hub_id)** — less invasive carry forward future per-hub permission UI. UserAPI.hub_ids extend chỉ khi BE schema thay đổi (defer v4.0 per-resource ACL).
- **Defense in depth Manage modal disabled UX** — UX layer; BE Plan 02-03 T-02-02-E business logic block role escalation authoritative (PATCH /api/users/{id}/role với role='admin' qua hub_admin → 403 HUB_ADMIN_REQUIRED envelope).
- **CheckCircle2 indicator preserve existing pattern** — KHÔNG ngắt visual consistency M2 UserManagement modal pattern hiện hữu (giữ ring-1 ring-brand-indigo cho selected state).

## Carry forward cho Plan 03-04

- 3 vitest test file mới sẽ verify scenario:
  - `UserManagement.form-3-option.spec.tsx` (Plan 03-02 FE-01 form 3 option + warning conditional + error envelope).
  - `Layout.hub-switcher.spec.tsx` (Plan 03-03 FE-02 hub switcher filter logic: super/hub_admin/empty).
  - `UserManagement.manage-modal-disabled.spec.tsx` (Plan 03-03 FE-03 Manage modal disabled per role).

## Backward compat (Plan 03-03 KHÔNG break M2/v3.0)

- 11 trang React M2/v3.0 KHÔNG touch (R-V3-2 minimal scope carry forward Phase 5 UI-SPEC §11.2).
- M2 envelope shape `{success, data, error, meta}` LOCKED — chỉ extend error code consume.
- Manage modal hub picker UX preserve (existing `manageHubIds` Set + `existingHubIds` lookup unchanged).
- `api.changeUserRole(...)` signature preserve (BE Phase 2 đã accept role='hub_admin').
- Sidebar logo + branding header line 166-215 Phase 5 PROXY-04 UNCHANGED.
- `useAuth()` hook contract LOCKED carry forward.

---

**Commit:** `20fa235 feat(03-03): FE-02 hub switcher + FE-03 Manage modal disabled Admin cho hub_admin`
