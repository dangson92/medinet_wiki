---
phase: 03
plan: 02
wave: 2
shipped: 2026-05-24
status: DONE
commits:
  - 9b2fa86 feat(03-02) FE-01 UserManagement form 3 option radio + warning banner + error envelope switch
requirements_satisfied: [FE-01]
decisions_implemented:
  - D-V3.1-Phase3-B  # UserAPI.role consume qua useAuth (Plan 03-01 ship)
  - D-V3.1-Phase3-D  # UserRole type alias import (Plan 03-01 ship)
files_modified:
  created: []
  modified:
    - frontend/src/pages/UserManagement.tsx
tests:
  vitest_baseline: "5 file / 37 test PASS"
  typescript_build: "PASS clean"
---

# Plan 03-02 — Summary (Wave 2 sequential)

**Mục tiêu:** FE-01 — UserManagement Add User form refactor radio group 2 → 3 option rõ ràng (Admin toàn hệ thống / Quản lý hub này / Viewer) + warning banner conditional + error envelope handle 4 code mới Phase 2 v3.1.

## Deliverable

### 1. `frontend/src/pages/UserManagement.tsx` (modify)

**Imports** (line 1-15):
- ADD `import type { UserRole } from '../services/api'` (Plan 03-01 ship type contract).

**State type** (line 37 + line 44):
- `newUserRole` state: `useState<'admin' | 'viewer'>` → `useState<UserRole>` (4 value).
- `manageRole` state: extend tương tự (Plan 03-03 cũng consume — preempt một lần).

**Add User form radio block** (~line 631-643 cũ → replace):
- Native HTML `<fieldset role="radiogroup">` + `<legend id="role-group-label">` + 3 `<label>` wrap radio + description.
- 3 option visible:
  1. **Admin toàn hệ thống** (value='admin') — description "Có thể quản lý tất cả hub, user, settings. Cảnh báo: gán cho user TIN CẬY."
  2. **Quản lý hub này** (value='hub_admin') — description "Quản lý user + document trong hub được chỉ định. KHÔNG vào hub khác."
  3. **Viewer** (value='viewer') — description "Xem document + search trong hub được gán. KHÔNG quản lý user."
- Mỗi radio `aria-describedby="role-{X}-desc"` link tới description id.
- **Warning banner conditional render** `{newUserRole === 'admin' && <div role="alert" aria-live="polite" class="bg-yellow-50 border-yellow-200 text-yellow-800 dark:bg-yellow-900/20 ...">⚠  Quyền cao nhất — quản lý toàn bộ hệ thống</div>}` — chỉ mount khi admin selected.

**handleCreateUser error switch** (~line 374-377 cũ → replace):
- Extract `const code = createRes.error?.code`.
- `switch (code)` 4 case → set `msg` exact UI-SPEC §7.4:
  - `HUB_ADMIN_REQUIRED` → "Bạn không có quyền tạo user với role Admin toàn hệ thống. Liên hệ Super Admin."
  - `HUB_ID_REQUIRED` → "Vui lòng chọn hub trước khi tạo user."
  - `AUTH_STATE_INCONSISTENT` → "Lỗi hệ thống xác thực — liên hệ admin. Mã: AUTH_STATE_INCONSISTENT"
  - `FORBIDDEN` → "Bạn không có quyền thực hiện thao tác này."
- Generic fallback `createRes.error?.message ?? 'Tạo user thất bại.'` preserve (BE message override khi code KHÔNG match — defensive).

**KHÔNG đụng:**
- Manage modal block (Plan 03-03 scope).
- List table, search, pagination, delete confirm dialog (existing M2/v3.0 carry forward).
- `api.createUser(...)` signature — body shape preserve (BE Phase 2 đã accept role='hub_admin').
- Pre-submit validation `if (!newUserEmail || !newUserPassword) ...`.
- Show-password-one-time modal logic.

## Tests

- `npx tsc --noEmit` exit 0 (TypeScript build clean).
- `npm run test -- --run` exit 0 — **5 baseline file PASS / 37 test:** regression unchanged.

Manual smoke (optional): mở dev server `npm run dev` → /users → Add modal → verify 3 radio + click admin → warning banner mount + click viewer → warning unmount. Plan 03-04 vitest tự động verify scenario này.

## Carry forward cho Plan 03-03

- `import type { UserRole }` đã ADD ở top — Plan 03-03 reuse cùng import.
- `manageRole` state đã extend `UserRole` — Plan 03-03 chỉ cần REPLACE Manage modal radio block (state type unchanged).

## Backward compat (Plan 03-02 KHÔNG break M2/v3.0)

- Envelope shape `{success, data, error, meta}` LOCKED — chỉ extend error code consume (4 envelope mới Phase 2).
- `api.createUser` body shape preserve (BE Phase 2 accept role='hub_admin' qua Pydantic Literal extend).
- Generic fallback preserve cho BE envelope code chưa biết (defensive).

---

**Commit:** `9b2fa86 feat(03-02): FE-01 UserManagement form 3 option radio + warning banner + error envelope switch`
