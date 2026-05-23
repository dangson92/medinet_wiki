---
phase: 5
plan: 02
subsystem: frontend
tags: [frontend, vitest, prefix-detect, react-router, basename, v3.0, phase5, wave2, tdd]
requirements: [PROXY-02]
wave: 2
status: DONE
date: 2026-05-23
dependency_graph:
  requires:
    - "05-01 — Caddyfile + .env.example HUBS_ALLOWLIST_REGEX source-of-truth cho fallback hardcode"
  provides:
    - "PREFIX + API_BASE + APP_BASE + CURRENT_HUB exports từ frontend/src/services/api.ts (module-level compute)"
    - "BrowserRouter basename={APP_BASE} wrap App.tsx — react-router auto prepend prefix cho mọi route"
    - "vitest 2.x infra (jsdom + RTL + jest-dom + npm run test script) cho Plan 05-03/04/05/06 tests downstream"
  affects:
    - "Plan 05-03 (branding): tiêu thụ CURRENT_HUB từ api.ts getBranding(CURRENT_HUB)"
    - "Plan 05-04 (Login.tsx useEffect + Layout.tsx + crossHubSearch absolute + tryRefresh): tiêu thụ APP_BASE + CURRENT_HUB cho redirect tới central + override absolute URL"
    - "Plan 05-06 (smoke checkpoint): kiểm tra cross-prefix routing real-browser 4 URL"
tech-stack:
  added:
    - "vitest@2.1.9 (test runner — VALIDATION rule no watch-mode flags, script `test`: `vitest run`)"
    - "@testing-library/react@16.3.2 (RTL render + cleanup)"
    - "@testing-library/jest-dom@6.9.1 (matchers DOM assertion)"
    - "jsdom@25.0.1 (browser API mock environment cho vitest)"
  patterns:
    - "TDD RED → GREEN per task (Task 1: 7 test RED → refactor api.ts → GREEN; Task 2: 3 test RED → wrap BrowserRouter basename → GREEN)"
    - "Module-level compute api.ts (KHÔNG hook/component scope — PREFIX/API_BASE/APP_BASE/CURRENT_HUB tính once tại import time)"
    - "vi.resetModules() + Object.defineProperty window.location + delete __HUB_CONFIG__ trong beforeEach để test isolation module-level singleton (Pitfall 4 RESEARCH §addressed)"
    - "Window typed declaration `declare global { interface Window { __HUB_CONFIG__?: HubConfigRuntime } }` (TS strict OK + KHÔNG (window as any) cast runtime)"
key-files:
  created:
    - "Hub_All/frontend/vitest.config.ts (29 dòng — jsdom env + globals + setupFiles + path alias @/* mirror tsconfig.json + coverage v8)"
    - "Hub_All/frontend/src/test-setup.ts (11 dòng — jest-dom/vitest import + RTL cleanup afterEach)"
    - "Hub_All/frontend/src/services/__tests__/api.spec.ts (89 dòng — 7 test scenario PREFIX/API_BASE/APP_BASE/CURRENT_HUB compute + reimportApi helper + beforeEach reset)"
    - "Hub_All/frontend/src/__tests__/App.spec.tsx (55 dòng — 3 test scenario basename per-prefix + renderAppAtPath helper)"
  modified:
    - "Hub_All/frontend/package.json (+1 script `test`: `vitest run` + 4 devDeps mới)"
    - "Hub_All/frontend/package-lock.json (94 packages added)"
    - "Hub_All/frontend/tsconfig.json (+exclude block: node_modules + dist + vitest.config.ts — Deviation Rule 3)"
    - "Hub_All/frontend/src/services/api.ts (REPLACE M2 hardcode `${hostname}:8180` (3 dòng) → prefix detect block (45 dòng) + module-level exports + JSDoc T-5-02 mitigation comment)"
    - "Hub_All/frontend/src/App.tsx (+1 import APP_BASE + 2 dòng JSDoc D-V3-Phase5-B3 + đổi `<BrowserRouter>` → `<BrowserRouter basename={APP_BASE}>`)"
decisions:
  - "D-V3-Phase5-B1 LOCKED implement: window.location.pathname.split('/').filter(Boolean)[0] + KNOWN_HUBS allowlist runtime"
  - "D-V3-Phase5-B3 LOCKED implement: BrowserRouter basename={APP_BASE} — 13 sub-route absolute path UNCHANGED"
  - "T-5-02 mitigation: comment in api.ts dòng 4-7 nhắc backend Caddy regex authoritative + FE allowlist UX-only"
  - "Deviation Rule 3: tsconfig.json exclude vitest.config.ts vì vitest@2.x bundle nested vite version gây dual-vite-version conflict với @vitejs/plugin-react top-level vite 6 — tsc lint scope exclude OK KHÔNG ảnh hưởng runtime vitest"
  - "Deviation Rule 1: doc comment dòng 1 api.ts đổi text 'replaces M2 hardcode `${hostname}:8180`' → 'replaces M2 absolute origin hardcode' để W-03 acceptance `! grep -q 'hostname.*:8180'` exit 0 (regression check sạch)"
metrics:
  duration_min: 22
  tasks_completed: "3/3"
  files_created: 4
  files_modified: 5
  commits: 5
  insertions: 2436
  deletions: 200
---

# Phase 5 Plan 02: Frontend Prefix Detect + Vitest Wave 0 Setup Summary

**One-liner:** Cài vitest 2.x infra (jsdom + RTL + jest-dom + test-setup) + refactor `frontend/src/services/api.ts` module-level compute PREFIX/API_BASE/APP_BASE/CURRENT_HUB từ `window.location.pathname.split('/')[1]` + KNOWN_HUBS allowlist runtime + fallback hardcode 3 hub gốc + wrap `App.tsx` `<BrowserRouter basename={APP_BASE}>` để react-router auto prepend prefix cho 13 sub-route — 1 build deploy được cross-prefix (central + yte/duoc/hcns) qua TDD RED→GREEN 5 atomic commit, 10/10 vitest test PASS.

## Objective

Wave 2 PARALLEL (file-disjoint với Plan 05-03) — Frontend prefix-detect runtime 1 build dùng chung. Cài vitest infra Wave 0 GAP từ VALIDATION.md → refactor `api.ts` thay M2 hardcode `${window.location.hostname}:8180` (Phase 5 broken assumption) → sửa `App.tsx` wrap `<BrowserRouter basename={APP_BASE}>` để react-router auto prepend prefix cho mọi route. PROXY-02 thoả qua D-V3-Phase5-B1 + B3 LOCKED + GA-V3-C confirmed. T-5-02 mitigation: client KHÔNG là authority allowlist — backend Caddy regex (Plan 05-01) là real gate; FE allowlist chỉ UX routing.

## Tasks Done

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 0 | Cài vitest infra Wave 0 PROXY-02 prereq | `ca1aaba` | `frontend/package.json`, `frontend/package-lock.json`, `frontend/vitest.config.ts`, `frontend/src/test-setup.ts`, `frontend/tsconfig.json` |
| 1 RED | Thêm api.spec.ts 7 scenario prefix detect (TDD RED) | `0b1d328` | `frontend/src/services/__tests__/api.spec.ts` |
| 1 GREEN | Refactor api.ts module-level prefix detect (TDD GREEN) | `8eb0676` | `frontend/src/services/api.ts` |
| 2 RED | Thêm App.spec.tsx 3 scenario basename (TDD RED) | `cff2137` | `frontend/src/__tests__/App.spec.tsx` |
| 2 GREEN | App.tsx wrap BrowserRouter basename={APP_BASE} (TDD GREEN) | `b39565d` | `frontend/src/App.tsx` |

5 atomic commit — TDD discipline RED commit trước GREEN commit per task.

## Acceptance Criteria (15 + 2 thừa)

| # | Criterion | Verify | Status |
|---|-----------|--------|--------|
| 1 | vitest install + version | `npx vitest --version` → `vitest/2.1.9` | PASS |
| 2 | `"test": "vitest run"` in package.json scripts | grep PASS | PASS |
| 3 | vitest in devDependencies | grep `"vitest":` PASS | PASS |
| 4 | @testing-library/react in devDependencies | grep PASS | PASS |
| 5 | @testing-library/jest-dom in devDependencies | grep PASS | PASS |
| 6 | jsdom in devDependencies | grep PASS | PASS |
| 7 | vitest.config.ts exists with `environment: 'jsdom'` | grep PASS | PASS |
| 8 | vitest.config.ts has setupFiles | grep PASS | PASS |
| 9 | test-setup.ts has `@testing-library/jest-dom/vitest` import | grep PASS | PASS |
| 10 | api.ts exports PREFIX | grep PASS | PASS |
| 11 | api.ts exports API_BASE | grep PASS | PASS |
| 12 | api.ts exports APP_BASE | grep PASS | PASS |
| 13 | api.ts exports CURRENT_HUB | grep PASS | PASS |
| 14 | api.ts references window.__HUB_CONFIG__ | grep PASS | PASS |
| 15 | api.ts fallback hardcode `['yte', 'duoc', 'hcns']` | grep PASS | PASS |
| 16 | **W-03 regression — KHÔNG còn `hostname:8180`** | `! grep -q 'hostname.*:8180'` exit 0 | PASS (doc comment đổi text Rule 1) |
| 17 | App.tsx import APP_BASE | grep `import { APP_BASE } from './services/api'` PASS | PASS |
| 18 | App.tsx wrap `<BrowserRouter basename={APP_BASE}>` | grep PASS | PASS |
| 19 | 13 sub-route giữ NGUYÊN absolute path | `grep -c '<Route '` = 15 (≥14) | PASS |
| 20 | api.spec.ts 7 test PASS | `npx vitest run src/services/__tests__/api.spec.ts` → 7/7 pass | PASS |
| 21 | App.spec.tsx 3 test PASS | `npx vitest run src/__tests__/App.spec.tsx` → 3/3 pass | PASS |
| 22 | Full vitest suite 10/10 PASS | `npx vitest run` → 10/10 pass | PASS |
| 23 | `npm run lint` (tsc --noEmit) PASS | exit 0 | PASS |

## Test Results

### vitest Suite (10/10 PASS — 3.26s tổng)

| Test File | Tests | Runtime | Status |
|-----------|-------|---------|--------|
| `src/services/__tests__/api.spec.ts` | 7 | 58ms | ✅ 7/7 PASS |
| `src/__tests__/App.spec.tsx` | 3 | 1818ms | ✅ 3/3 PASS |
| **TOTAL** | **10** | **~1.88s tests + 1.36s env** | **10/10 PASS** |

### api.spec.ts scenario detail

| # | Scenario | Pathname | Expected | Actual |
|---|----------|----------|----------|--------|
| 1 | central root | `/` | PREFIX=null, API_BASE=/api, APP_BASE='', CURRENT_HUB=central | PASS |
| 2 | hub prefix | `/yte/dashboard` | PREFIX=yte, API_BASE=/yte/api, APP_BASE=/yte, CURRENT_HUB=yte | PASS |
| 3 | trailing slash | `/duoc/` | PREFIX=duoc, APP_BASE=/duoc | PASS |
| 4 | unknown hub T-5-02 fallback | `/unknown_hub/x` | PREFIX=null (fallback central) | PASS |
| 5 | runtime __HUB_CONFIG__ override | `/custom_hub/dashboard` + allowlist:[yte,custom_hub] | PREFIX=custom_hub | PASS |
| 6 | fallback hardcode yte | `/yte/profile` (no __HUB_CONFIG__) | PREFIX=yte | PASS |
| 7 | fallback hardcode hcns | `/hcns/` | PREFIX=hcns | PASS |

### App.spec.tsx scenario detail

| # | Scenario | Pathname | Behavior | Status |
|---|----------|----------|----------|--------|
| 1 | central /login | `/login` (basename empty) | Login mount KHÔNG crash | PASS |
| 2 | hub con /yte/login | `/yte/login` (basename /yte) | react-router treat as basename + path /login → Login mount | PASS |
| 3 | api module wire | (regression) | apiModule.APP_BASE typeof string | PASS |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] tsconfig.json exclude vitest.config.ts**
- **Found during:** Task 0 verify step (`npm run lint` after dep install)
- **Issue:** vitest@2.x bundle nested vite version (qua node_modules/vitest/node_modules/vite) gây dual-vite-version conflict với top-level vite 6 (`@vitejs/plugin-react` pull qua peer dep). `defineConfig({ plugins: [react()] })` throw TS2769 vì `Plugin<any>` type mismatch giữa 2 vite copy.
- **Fix:** tsconfig.json thêm `exclude: ["node_modules", "dist", "vitest.config.ts"]` block — exclude file ra khỏi tsc lint scope. KHÔNG ảnh hưởng runtime vitest (vitest runs config qua vite-node ESM resolver riêng — TS check chỉ là editor/IDE concern).
- **Files modified:** `frontend/tsconfig.json`
- **Commit:** `ca1aaba` (cùng Task 0)
- **Alternative considered:** (a) `npm install -D vitest@latest` (v3.x) — REJECT plan pin `vitest@^2`; (b) cast `plugins: [react() as any]` — REJECT type unsafe; (c) `npm dedupe` — REJECT không stable vì vitest 2 hardcode nested vite.

**2. [Rule 1 - Bug] Doc comment rewording for W-03 acceptance**
- **Found during:** Task 1 verify step (grep -q "hostname.*:8180" sau khi commit GREEN)
- **Issue:** Comment dòng 1 `api.ts` ban đầu viết `"(replaces M2 hardcode \`${hostname}:8180\`)"` chứa exact regex pattern → `grep -q "hostname.*:8180"` exit 0 (match) → W-03 acceptance `!` negation FAIL.
- **Fix:** Đổi text comment thành `"(replaces M2 absolute origin hardcode)"` — giữ ý nghĩa documentation nhưng KHÔNG trigger regex.
- **Files modified:** `frontend/src/services/api.ts` (line 1 comment only)
- **Commit:** `8eb0676` (cùng GREEN commit Task 1 — đã rewrite TRƯỚC khi commit GREEN)

## Threat Mitigation Status

| Threat ID | Status | Evidence |
|-----------|--------|----------|
| T-5-02 (Tampering KNOWN_HUBS client-side) | mitigated (defense-in-depth) | Comment dòng 4-7 api.ts documenting backend Caddy `path_regexp ^/(yte\|duoc\|hcns)/api/(.*)$` (Plan 05-01) authoritative; FE allowlist tamper KHÔNG bypass backend strip — Test 4 verify unknown hub fall through central. |
| T-5-07 (localStorage XSS exfil — M2 carry forward) | accept | KHÔNG change Phase 5 — defer v4.0 HARD-V4-05 httpOnly cookie migration. |
| T-5-12 (basename mismatch infinite redirect) | mitigated | Test 1 + Test 2 App.spec.tsx verify basename resolve correct cho 2 prefix scenario (central + yte) — Pitfall 3 RESEARCH.md addressed qua KNOWN_HUBS fallback hardcode. |

## Next Plan Handoff

- **Plan 05-03 (branding registry)** — Có thể start Wave 2 parallel (file-disjoint với 05-02). Tiêu thụ `CURRENT_HUB` từ `services/api.ts` qua import → `getBranding(CURRENT_HUB)`. Plan 05-03 độc lập về file (`frontend/src/branding/` + `frontend/public/branding/`).
- **Plan 05-04 (Login.tsx useEffect + Layout.tsx + crossHubSearch absolute + tryRefresh redirect: follow audit)** — Depend cả Plan 05-02 (APP_BASE + CURRENT_HUB export) + Plan 05-03 (getBranding helper). Wave 3 sau khi 02+03 ship.
- **Plan 05-05 (hub-add.sh extend HUBS_ALLOWLIST + caddy reload)** — Chỉ depend Plan 05-01 (`.env.example` HUBS_ALLOWLIST_REGEX). Wave 4 parallel-able với Plan 05-04.
- **Plan 05-06 (closeout docs + smoke checkpoint manual 4 URL)** — Depend toàn bộ 05-01..05. Wave 5 closeout.

## Self-Check: PASSED

**Files created (verified exist):**
- `frontend/vitest.config.ts` → FOUND
- `frontend/src/test-setup.ts` → FOUND
- `frontend/src/services/__tests__/api.spec.ts` → FOUND
- `frontend/src/__tests__/App.spec.tsx` → FOUND

**Files modified (verified content):**
- `frontend/package.json` → contains `"test": "vitest run"` + 4 devDeps
- `frontend/package-lock.json` → 94 packages added
- `frontend/tsconfig.json` → exclude block present
- `frontend/src/services/api.ts` → exports PREFIX/API_BASE/APP_BASE/CURRENT_HUB, KHÔNG còn `hostname:8180`
- `frontend/src/App.tsx` → import APP_BASE + `<BrowserRouter basename={APP_BASE}>`

**Commits (verified in git log):**
- `ca1aaba` chore(05-02) Task 0 vitest infra → FOUND
- `0b1d328` test(05-02) Task 1 RED api.spec.ts → FOUND
- `8eb0676` feat(05-02) Task 1 GREEN api.ts refactor → FOUND
- `cff2137` test(05-02) Task 2 RED App.spec.tsx → FOUND
- `b39565d` feat(05-02) Task 2 GREEN App.tsx basename → FOUND

**TDD Gate Compliance:** PASS
- Task 1 (api.ts): `test(...)` commit `0b1d328` (RED) → `feat(...)` commit `8eb0676` (GREEN) sequence verified.
- Task 2 (App.tsx): `test(...)` commit `cff2137` (RED) → `feat(...)` commit `b39565d` (GREEN) sequence verified.
- REFACTOR phase: KHÔNG cần — code minimal + idiom đã clean ở GREEN commit (per RED→GREEN→REFACTOR optional convention).
