---
phase: 03
plan: 01
wave: 1
shipped: 2026-05-24
status: DONE
commits:
  - ff24efc feat(03-01) FE-04 UserRole type alias + UserAPI.role extend + mockData hub_admin fixture
requirements_satisfied: [FE-04]
decisions_implemented:
  - D-V3.1-Phase3-B  # UserAPI.role extend (BE đã trả qua /api/auth/me Phase 2)
  - D-V3.1-Phase3-C  # mockData ADD 2 hub_admin user fixture (dmd + tdt)
  - D-V3.1-Phase3-D  # UserRole type alias centralize
  - D-V3.1-Phase3-E  # Wave 1 BLOCKING foundation
files_modified:
  created: []
  modified:
    - frontend/src/services/api.ts
    - frontend/src/mockData.ts
    - frontend/src/types.ts
  unchanged: [frontend/src/contexts/AuthContext.tsx]
tests:
  vitest_baseline: "5 file / 37 test PASS"
  typescript_build: "PASS clean"
  eslint: "PASS clean (tsc --noEmit alias)"
---

# Plan 03-01 — Summary (Wave 1 BLOCKING)

**Mục tiêu:** Foundation type contract + mock fixture cho Phase 3 v3.1 — single source-of-truth `UserRole` alias 4 value mirror BE Pydantic Literal (Plan 02-03 DEP-03) + Phase 1 migration 0006 CHECK constraint; mockData fixture cho dev test + vitest Plan 03-04 carry forward.

## Deliverable

### 1. `frontend/src/services/api.ts` (modify)

- **ADD** `export type UserRole = 'admin' | 'hub_admin' | 'editor' | 'viewer'` đặt TRƯỚC `UserAPI` interface declare (D-V3.1-Phase3-D LOCKED).
- **EXTEND** `UserAPI` interface thêm field `role: UserRole` (D-V3.1-Phase3-B LOCKED — BE Phase 2 đã trả role qua `/api/auth/me`).
- Comment trace 4 source-of-truth (BE schema, Phase 1 migration 0006, Phase 2 ship, Phase 3 CONTEXT.md).

### 2. `frontend/src/types.ts` (modify)

- **EXTEND** `User.role` từ `'admin' | 'viewer'` → `'admin' | 'hub_admin' | 'editor' | 'viewer'` (additive widening — TypeScript accept superset). Lý do: mockData hub_admin fixture compile-time reject nếu User.role chỉ 2 value.
- KHÔNG đụng các interface khác (Hub/SyncBatch/SyncPage/AuditLogEntry/APIKey/RAGDocument).

### 3. `frontend/src/mockData.ts` (modify)

- **ADD** `MOCK_HUBS` entry id=7 code='tdt' name='Thuốc Dân Tộc' (audit 2026-05-24 phát hiện thiếu — dmd + tdt là 2 hub thật DB per memory `project_real_hubs_deployment`).
- **APPEND** 2 hub_admin user fixture vào MOCK_USERS (sau u35):
  - `u-hadmin-dmd` (Nguyễn Hub Admin DMD, role='hub_admin', hubId resolve qua `MOCK_HUBS.find(h => h.code === 'dmd')?.id ?? ''`).
  - `u-hadmin-tdt` (Trần Hub Admin TDT, role='hub_admin', hubId resolve qua `MOCK_HUBS.find(h => h.code === 'tdt')?.id ?? ''`).
- Nullish coalescing `?? ''` defensive — nếu lookup fail vẫn compile.
- KHÔNG đụng 35 user existing + 6 hub existing.

### 4. `frontend/src/contexts/AuthContext.tsx` (verify-only)

- `useAuth().user?.user?.role` accessible TypeScript sau khi UserAPI.role extend ở api.ts.
- KHÔNG code change (BE Phase 2 đã trả role qua `api.me()` — type-only fix).

## Discovery findings

- **MOCK_HUBS thiếu `code='tdt'`** → ADD entry mới id=7 (decision plan-time per PATTERNS.md).
- **types.ts User.role chỉ 2 value** → EXTEND 4 value REQUIRED để fixture compile (decision plan-time, không trong CONTEXT.md gốc).
- **userHubIds derivation Option A LOCKED** — Plan 03-03 sẽ derive từ `roles: RoleAPI[]` đã có sẵn (less invasive — KHÔNG extend UserAPI.hub_ids).

## Tests

- `npx tsc --noEmit` exit 0 (TypeScript build clean — KHÔNG regression).
- `npm run lint` exit 0 (alias tsc --noEmit — same check).
- `npm run test -- --run` exit 0 — **5 baseline file PASS / 37 test:**
  - `src/services/__tests__/api.spec.ts` (11 test)
  - `src/branding/__tests__/registry.spec.ts` (13 test)
  - `src/__tests__/Layout.spec.tsx` (4 test)
  - `src/pages/__tests__/Login.spec.tsx` (6 test)
  - `src/__tests__/App.spec.tsx` (3 test)

## Carry forward cho Plan 03-02 + 03-03

- Plan 03-02 import `import type { UserRole } from '../services/api'` cho `useState<UserRole>` + form 3 option radio.
- Plan 03-03 import `import type { UserRole, HubAPI } from '../services/api'` cho HubSwitcher component + Manage modal state.
- Plan 03-04 vitest test sử dụng 2 hub_admin user fixture cho mock context scenario.

## Backward compat (Phase 3 v3.1 — Plan 03-01 KHÔNG break v3.0 + Phase 1/2)

- types.ts User.role extend additive (TypeScript widening accept 2 value cũ trong superset 4 value).
- AuthContext.tsx UNCHANGED — 11 trang React M2/v3.0 consumer KHÔNG break.
- mockData fixture 35 user + 6 hub existing preserve nguyên — chỉ APPEND mới.
- M2 envelope shape `{success, data, error, meta}` UNCHANGED.

---

**Commit:** `ff24efc feat(03-01): FE-04 UserRole type alias + UserAPI.role extend + mockData hub_admin fixture`
