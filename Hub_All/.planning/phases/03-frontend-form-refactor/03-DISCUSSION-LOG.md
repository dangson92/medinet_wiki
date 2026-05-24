# Phase 3: Frontend form refactor (FE) — Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-24
**Phase:** 03-frontend-form-refactor
**Mode:** auto (system reminder "Work without stopping for clarifying questions" + v3.1 Phase 2 precedent)
**Areas discussed:** GA-FE-A (Hub switcher central detection) · GA-FE-B (currentUser.role source) · GA-FE-C (mockData hub_admin fixture) · +2 phụ from codebase audit (UserRole type alias + Wave order)

---

## GA-FE-A — Hub switcher central detection logic

| Option | Description | Selected |
|--------|-------------|----------|
| Slug hardcode `'central'` | Phase 5 PROXY-04 đã ship pattern `CURRENT_HUB = PREFIX ?? 'central'`; branding fallback `getBranding('central')`; FE allowlist UX-only T-5-02. Type-only check. | ✓ |
| API field `is_central` boolean | Cần BE schema migration 0007 (add column hubs.is_central). Scope creep ngoài Phase 3. | |
| Computed `parent_hub_id IS NULL` | Cần BE schema migration 0007 (add column hubs.parent_hub_id). Scope creep + complexity hierarchy navigation. | |

**Auto-selected (recommended):** Slug hardcode `'central'`
**Rationale:** ROADMAP §"Discuss-phase gray areas" GA-FE-A đã có recommendation rõ; Phase 5 pattern carry forward consistency; KHÔNG schema migration; backend Caddy regex + RBAC GET /api/hubs filter là trust boundary (FE chỉ UX). Locked as **D-V3.1-Phase3-A**.

---

## GA-FE-B — AuthContext currentUser.role source

| Option | Description | Selected |
|--------|-------------|----------|
| Extend UserAPI interface thêm `role: string` (type-only) | AuthContext.tsx:32 đã call api.me() returns UserWithRoles; BE Phase 2 đã trả role qua /api/auth/me. Type bug fix, 0 runtime overhead. | ✓ |
| Fetch /api/profile riêng | 1 extra round-trip mỗi load + race condition (login → setState user → fetch profile → potential mismatch). Pattern phức tạp hơn. | |
| Server-side render role vào HTML | KHÔNG có SSR setup hiện tại (React 19 SPA); cần Next.js migration scope creep. | |

**Auto-selected (recommended):** Extend UserAPI interface
**Rationale:** ROADMAP §"GA-FE-B" recommendation; audit AuthContext.tsx:32 confirm api.me() đã return UserWithRoles object (chỉ thiếu type declare). BE Phase 2 Plan 02-03 ship `/api/auth/me` trả `users.role` global. Locked as **D-V3.1-Phase3-B**.

---

## GA-FE-C — Mock data hub_admin fixture

| Option | Description | Selected |
|--------|-------------|----------|
| ADD 2 hub_admin fixture (1 dmd + 1 tdt) | 2 hub thật DB per memory project_real_hubs_deployment; đủ cover vitest test scenario form/switcher/edit modal. | ✓ |
| ADD 4-5 hub_admin fixture (cover all hubs trong allowlist) | Ghost hub yte/duoc/hcns decorative — KHÔNG cần fixture user (Plan 03-04 test KHÔNG touch ghost hub scenario). | |
| KHÔNG thêm fixture, dùng inline mock trong test file | Drift risk — mỗi test file tự define user → inconsistent. Phase 5 vitest pattern carry forward fixture-based. | |

**Auto-selected (recommended):** ADD 2 hub_admin fixture (1 dmd + 1 tdt)
**Rationale:** ROADMAP §"GA-FE-C" recommendation; audit mockData.ts confirm hiện 35 user chỉ admin|viewer; Phase 5 vitest infrastructure ship pattern carry forward; 2 fixture đủ cho scenario thật (dmd + tdt). Locked as **D-V3.1-Phase3-C**.

---

## D-V3.1-Phase3-D — UserRole type alias export (codebase audit deriv)

| Option | Description | Selected |
|--------|-------------|----------|
| Export `UserRole` type alias từ services/api.ts | Single source of truth; mirror BE Pydantic Literal; consumer import via `import type { UserRole }`. | ✓ |
| Inline literal mỗi component (status quo) | Drift risk (UserManagement.tsx:37 + future edit modal + Layout filter — 3+ chỗ DUPLICATE). | |
| `enum UserRole { ... }` TypeScript enum | TS enum runtime cost + interop awkward với Pydantic Literal string; type alias literal đủ. | |

**Auto-selected (recommended):** Export `UserRole` type alias
**Rationale:** Audit confirm UserManagement.tsx:37 inline literal — drift risk. Phase 1 migration 0006 CHECK constraint + Phase 2 Pydantic Literal đã LOCKED 4 value; FE type-only mirror. Locked as **D-V3.1-Phase3-D**.

---

## D-V3.1-Phase3-E — Wave order

| Option | Description | Selected |
|--------|-------------|----------|
| Wave 1 Plan 03-01 BLOCKING → Wave 2 Plan 03-02 + 03-03 parallel → Wave 3 Plan 03-04 closeout | Type contract foundation trước; UserManagement + Layout 2 file độc lập parallel-able; closeout sau. | ✓ |
| All 4 plan sequential (Wave 1-2-3-4) | Bỏ lỡ parallel opportunity (Plan 03-02 + 03-03 KHÔNG conflict file). | |
| Wave 1 Plan 03-01 + 03-02 parallel → Wave 2 Plan 03-03 → Wave 3 Plan 03-04 | Plan 03-02 cần UserRole type Plan 03-01 ship → dependency conflict (KHÔNG parallel-able). | |

**Auto-selected (recommended):** Wave 1 BLOCKING → Wave 2 parallel × 2 → Wave 3 closeout
**Rationale:** Phase 2 wave order pattern carry forward (BLOCKING dependency Plan 02-01 → parallel Plan 02-02/02-03 → sequential 02-04 → closeout 02-05). Locked as **D-V3.1-Phase3-E**.

---

## Claude's Discretion (Plan-phase agent decides)

- File-level Plan 03-02 vs 03-03 split exact boundary (extract `<HubSwitcher>` component riêng nếu logic >30 LOC).
- Test count/scenario chi tiết (vitest 6-10 test khuyến nghị baseline).
- Error envelope handling FE side khi BE trả 4 envelope mới Phase 2 (toast + form-level error + 403 redirect pattern).
- AuthContext loading state defensive default (`?? 'viewer'`) vs skeleton spinner.
- Tooltip implementation (native `title="..."` attribute vs custom Tailwind tooltip plugin).

## Deferred Ideas (noted for future phases)

- `HubSwitcher` extract component (Plan-phase Claude discretion nếu complexity warrant).
- Loading skeleton AuthContext refinement (defer v4.0 UX polish).
- `role='editor'` UI fixture (defer v4.0 per-resource ACL).
- Per-resource ACL fine-grained (defer v4.0 backlog).
- i18n EN/VN switch UI (defer v4.0).
- Tooltip plugin Tailwind custom (defer v4.0).
- Form validation client-side rich (formik/react-hook-form, defer v4.0).
- Multi-role 1 user trong cùng hub (defer v4.0).
- Visual regression smoke 4 hub × 11 trang (defer v4.0 ops handover — Phase 7 v3.0 carry forward).

---

*Generated 2026-05-24 via `/gsd-discuss-phase 3` auto-mode. 5 decision LOCKED (3 from ROADMAP gray-area + 2 from codebase audit).*
