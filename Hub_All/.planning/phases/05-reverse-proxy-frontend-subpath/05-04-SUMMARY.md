---
phase: 5
plan: 04
subsystem: frontend
tags: [frontend, login, layout, branding, sso-redirect, cross-hub, tryRefresh, v3.0, phase5, PROXY-02, PROXY-04, B-02-fix, T-5-04, D-V3-Phase5-C4]
requirements: [PROXY-02, PROXY-04]
status: DONE
completed_date: "2026-05-23"
wave: 3
depends_on: [05-02, 05-03]

dependency_graph:
  requires:
    - "Plan 05-02 exports: CURRENT_HUB + APP_BASE + API_BASE + PREFIX (api.ts) + 7 vitest test prefix detect baseline"
    - "Plan 05-03 exports: getBranding(hub) + getContrastTextColor(themeColor) + 4 hub branding (central/yte/duoc/hcns) + 13 vitest test"
    - "Plan 03-04 SSO-02 backend: hub con POST /api/auth/refresh → 307 RedirectResponse Location: ${CENTRAL_URL}/api/auth/refresh"
    - "Plan 04-05 D-V3-Phase4-D3: /api/search/cross-hub mount CENTRAL-ONLY (hub con strip → 404 envelope D6)"
    - "Plan 05-01 Caddyfile /api/* handle block → reverse_proxy python-api-central:8080 (no strip)"
  provides:
    - "Login.tsx 4 UX state machine (A/B/C/D) + branding render + themeColor inline + T-5-04 mitigation + W-05 origin-not-host"
    - "Layout.tsx sidebar header HUB_BRANDING swap + CSS var --hub-theme outermost wrapper + profile avatar hover ring themeColor"
    - "api.crossHubSearch ABSOLUTE path qua requestAbsolute helper bypass API_BASE prefix"
    - "api.tryRefresh explicit redirect: 'follow' audit (B-02 fix carry forward Plan 03-04 SSO-02)"
  affects:
    - "Frontend M2 shell: Login.tsx form (preserved) + Layout.tsx nav items (preserved active state) — UI-SPEC §1.4 minimal cascade scope LOCKED"
    - "App.spec.tsx (Rule 1 helper fix — window.location mock include replace stub vì Login useEffect mới call)"

tech_stack:
  added: []
  patterns:
    - "useSearchParams + useMemo strict 4-layer validation (T-5-04 open redirect mitigation)"
    - "window.location.replace cross-prefix navigate (KHÔNG react-router navigate vì basename scope)"
    - "CSS var --hub-theme inline + color-mix(in srgb, ...) gradient cho dynamic theme blend"
    - "Module-level branding compute (Layout.tsx HUB_BRANDING) — 1 lần per process boot"
    - "private requestAbsolute<T> helper trong APIClient cho central-only endpoint bypass baseURL"

key_files:
  created:
    - path: "Hub_All/frontend/src/pages/__tests__/Login.spec.tsx"
      purpose: "6 vitest test cover 4 state machine A/B/C/D + 2 T-5-04 mitigation reject"
    - path: "Hub_All/frontend/src/__tests__/Layout.spec.tsx"
      purpose: "4 vitest test sidebar branding render per CURRENT_HUB (central/yte/duoc) + logo src schema"
    - path: "Hub_All/.planning/phases/05-reverse-proxy-frontend-subpath/05-04-SUMMARY.md"
      purpose: "Plan 05-04 closeout artifact (file này)"
  modified:
    - path: "Hub_All/frontend/src/pages/Login.tsx"
      change: "4-state machine + branding render + T-5-04 4-layer validation + W-05 origin (not host) + themeColor inline gradient"
    - path: "Hub_All/frontend/src/Layout.tsx"
      change: "Sidebar header logo + title swap getBranding(CURRENT_HUB) module-level + outermost --hub-theme CSS var + profile hover ring inline"
    - path: "Hub_All/frontend/src/services/api.ts"
      change: "Thêm private requestAbsolute helper + crossHubSearch override absolute path + tryRefresh explicit redirect: 'follow' (B-02 fix)"
    - path: "Hub_All/frontend/src/services/__tests__/api.spec.ts"
      change: "Extend 4 vitest test mới: 2 crossHubSearch absolute + 2 tryRefresh redirect audit"
    - path: "Hub_All/frontend/src/__tests__/App.spec.tsx"
      change: "Rule 1 fix renderAppAtPath helper mock window.location include replace + assign stub (jsdom Location instance reject method qua spread copy)"

decisions:
  - "D-V3-Phase5-C4 LOCKED — tryRefresh fetch options explicit redirect: 'follow' carry forward Plan 03-04 SSO-02 307 chain RFC 7231 §6.4.7 (B-02 fix)"
  - "D-V3-Phase4-D3 carry forward — crossHubSearch ABSOLUTE path '/api/search/cross-hub' KHÔNG API_BASE prefix (hub con strip → 404)"
  - "T-5-04 mitigation 4-layer validation chain (reject //, reject ://, regex hub format, KNOWN_HUBS allowlist) — defense-in-depth open redirect mitigation"
  - "W-05 use window.location.origin (not host) — inherit protocol HTTP/HTTPS dev mismatch safe"
  - "UI-SPEC §1.4 LOCKED minimal scope — Layout.tsx chỉ sidebar header touch, KHÔNG cascade Tailwind brand-indigo nav active (defer v4.0)"

metrics:
  duration_minutes: ~12
  tasks_completed: 4
  files_modified: 5
  files_created: 3
  tests_added: 14
  tests_pass_rate: "37/37 (100%) full vitest suite"
  commits: 4
  lint_status: "tsc --noEmit PASS"
---

# Phase 5 Plan 04: Login + Layout + crossHubSearch + tryRefresh Wire Summary

**One-liner:** Wire branding + SSO redirect + cross-hub absolute path + tryRefresh `redirect: 'follow'` audit vào Login.tsx (4-state machine A/B/C/D + T-5-04 mitigation), Layout.tsx (sidebar HUB_BRANDING swap), api.ts (requestAbsolute helper + crossHubSearch absolute path override + tryRefresh B-02 fix) — consume getBranding + CURRENT_HUB từ Plan 05-02/03 + carry forward Phase 3 SSO-02 307 chain + Phase 4 D-V3-Phase4-D3 cross-hub strip.

## Tasks ship

| Task | Mục tiêu | File touch | Commit | Tests |
|------|----------|------------|--------|-------|
| 1 | Login.tsx 4-state machine A/B/C/D + branding render + T-5-04 + W-05 | Login.tsx + Login.spec.tsx | `54fc315` | 6/6 PASS |
| 2 | Layout.tsx sidebar header swap getBranding(CURRENT_HUB) | Layout.tsx + Layout.spec.tsx | `ca6f4e4` | 4/4 PASS |
| 3 | api.crossHubSearch ABSOLUTE path qua requestAbsolute helper | api.ts + api.spec.ts | `ed721fd` | 9/9 PASS (7 baseline + 2 mới) |
| 4 | tryRefresh explicit `redirect: 'follow'` audit (B-02 fix) | api.ts + api.spec.ts + App.spec.tsx | `61ac731` | 11/11 PASS (9 + 2 mới) |

## Test coverage

| Test File | Tests | Pass | Coverage Domain |
|-----------|-------|------|-----------------|
| `src/pages/__tests__/Login.spec.tsx` | 6 | 6/6 | 4 state A/B/C/D + 2 T-5-04 (absolute URL inject + reserved name reject) |
| `src/__tests__/Layout.spec.tsx` | 4 | 4/4 | 3 hub title render (central/yte/duoc) + logo src schema |
| `src/services/__tests__/api.spec.ts` | 11 | 11/11 | 7 prefix detect (Plan 05-02 baseline) + 2 crossHubSearch absolute + 2 tryRefresh redirect audit |
| `src/__tests__/App.spec.tsx` | 3 | 3/3 | BrowserRouter basename baseline (Rule 1 fix helper mock window.location.replace) |
| `src/branding/__tests__/registry.spec.ts` | 13 | 13/13 | Plan 05-03 baseline (no regression) |
| **Total full suite** | **37** | **37/37 (100%)** | Phase 5 cumulative Wave 0-3 |

## Acceptance Criteria PASS table

| # | Check | Cmd | Status |
|---|-------|-----|--------|
| 1 | Login useEffect import | `grep "useEffect" Login.tsx` | PASS (line 10 + 151 + 173) |
| 2 | Login useMemo import | `grep "useMemo" Login.tsx` | PASS |
| 3 | Login CURRENT_HUB + APP_BASE import | `grep "import { CURRENT_HUB, APP_BASE }"` | PASS |
| 4 | Login getBranding import | `grep "import { getBranding"` | PASS |
| 5 | Login useSearchParams | `grep "useSearchParams"` | PASS |
| 6 | Login window.location.replace | `grep "window.location.replace"` | PASS (3 vị trí: useEffect State C + handleSubmit success + post-auth redirect) |
| 7 | W-05 origin not host | `grep "window.location.origin"` | PASS (KHÔNG dùng `.host` bare — chỉ trong comment giải thích) |
| 8 | W-05 explanatory comment | `grep "Use origin (not host)"` | PASS |
| 9 | State C skeleton text | `grep "Đang chuyển đến trang đăng nhập trung tâm"` | PASS |
| 10 | State B chip text | `grep "Sau đăng nhập sẽ vào"` | PASS |
| 11 | color-mix theme blend | `grep "color-mix(in srgb"` | PASS |
| 12 | CSS var --hub-theme | `grep "'--hub-theme'"` | PASS |
| 13 | T-5-04 allowlist | `grep "knownHubs.includes(candidate)"` | PASS |
| 14 | T-5-04 absolute URL reject | `grep "raw.startsWith('//') \|\| raw.includes('://')"` | PASS |
| 15 | Layout getBranding import | `grep "import { getBranding"` | PASS |
| 16 | Layout CURRENT_HUB import | `grep "import { CURRENT_HUB }"` | PASS |
| 17 | Layout HUB_BRANDING module const | `grep "const HUB_BRANDING = getBranding(CURRENT_HUB)"` | PASS |
| 18 | Layout dynamic title | `grep "HUB_BRANDING.title"` | PASS |
| 19 | Layout logo bg inline | `grep "backgroundColor: HUB_BRANDING.themeColor"` | PASS |
| 20 | Layout img src wire | `grep "src={HUB_BRANDING.logo}"` | PASS |
| 21 | Layout outermost --hub-theme | `grep "'--hub-theme'"` | PASS |
| 22 | Layout KHÔNG hardcode Medinet Wiki | `grep -c "Medinet Wiki"` | PASS (count = 0) |
| 23 | api requestAbsolute helper | `grep "requestAbsolute"` | PASS |
| 24 | api crossHubSearch method | `grep "async crossHubSearch"` | PASS |
| 25 | api absolute path literal | `grep "'/api/search/cross-hub'"` | PASS |
| 26 | api D-V3-Phase4-D3 ref | `grep "D-V3-Phase4-D3"` | PASS |
| 27 | api redirect follow explicit | `grep -E "redirect:\s*['\"]follow['\"]"` | PASS |
| 28 | api D-V3-Phase5-C4 ref | `grep "D-V3-Phase5-C4"` | PASS |
| 29 | api B-02 comment | `grep "preserve POST body through 307 redirect"` | PASS |
| 30 | Login.spec.tsx exists | `test -f` | PASS |
| 31 | Layout.spec.tsx exists | `test -f` | PASS |
| 32 | Login vitest PASS | `npx vitest run Login.spec.tsx` | PASS (6/6) |
| 33 | Layout vitest PASS | `npx vitest run Layout.spec.tsx` | PASS (4/4) |
| 34 | api vitest PASS | `npx vitest run api.spec.ts` | PASS (11/11) |
| 35 | Full vitest suite | `npx vitest run` | PASS (37/37) |
| 36 | tsc --noEmit | `npm run lint` | PASS |

## Decisions Made

- **D-V3-Phase5-C4 LOCKED carry forward** — tryRefresh fetch options explicit `redirect: 'follow'` cho audit + clarity, mặc dù browser default đã 'follow'. B-02 BLOCKER fix per plan-checker iteration 1 closed.
- **D-V3-Phase4-D3 carry forward** — crossHubSearch ABSOLUTE path `/api/search/cross-hub` (KHÔNG `${API_BASE}` prefix) vì hub con strip endpoint → 404 envelope D6. FE phải bypass để reach central qua Caddy /api/* handle block (Plan 05-01).
- **T-5-04 mitigation 4-layer chain** — reject absolute URL injection (`//`, `://`) BEFORE strip + strip leading `/` + regex hub format `^[a-z][a-z0-9_]{0,15}$` + KNOWN_HUBS allowlist intersect. Defense-in-depth open redirect mitigation; 3 test verify behavior (`State D + 2 T-5-04 explicit`).
- **W-05 origin not host** — Login.tsx useEffect dùng `window.location.origin` (gồm protocol) thay vì `.host` (chỉ hostname) — inherit protocol HTTP/HTTPS dev mismatch safe. Code comment giải thích rationale.
- **UI-SPEC §1.4 LOCKED minimal scope** — Layout.tsx chỉ sidebar header touch (logo bg + title text + profile avatar hover ring). KHÔNG cascade Tailwind brand-indigo nav active state (defer v4.0 Tailwind theme cascade refactor). Hero gradient indigo cứng M2 ở Login.tsx đã replace bằng dynamic themeColor.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] App.spec.tsx renderAppAtPath helper window.location mock thiếu replace stub**

- **Found during:** Task 4 full vitest suite run (App.spec.tsx Test 2 `/yte/login` failed với `TypeError: 'replace' called on an object that is not a valid instance of Location`).
- **Root cause:** Login.tsx mới có useEffect call `window.location.replace(target)` khi `CURRENT_HUB !== 'central'`. App.spec.tsx test path `/yte/login` trigger State C → useEffect fire → jsdom reject method call vì `Object.defineProperty(window, 'location', { value: { ...window.location, ... } })` spread copy mất Location prototype method binding.
- **Fix:** Helper `renderAppAtPath` thêm `replace: vi.fn()` + `assign: vi.fn()` + `search: ''` vào mock value (pattern song song với Login.spec.tsx helper).
- **Files modified:** `frontend/src/__tests__/App.spec.tsx` (helper update + NOTE comment giải thích Plan 05-04 dependency).
- **Commit:** Bundled với Task 4 commit `61ac731`.

### No Critical Adjustments

KHÔNG cần Rule 2 (missing critical functionality) hay Rule 3 (blocking issues). Plan executed exactly as written với 1 micro-adjustment scope test helper.

### No Architectural Deviations (Rule 4)

Plan structure honored — 4 task sequential, 4 atomic commit. KHÔNG đụng backend (Phase 3 LOCKED), KHÔNG đổi M2 endpoint URL `/api/*` shape.

## Authentication Gates

Không gặp authentication gate trong execution (Plan 05-04 thuần frontend wire — không touch deployment/secrets).

## Backward Compatibility Notes

- **Login.tsx form shell M2 preserved:** email + password input + validation + account locked state + error handling + Google button shell + footer copy GIỮ NGUYÊN.
- **Layout.tsx M2 preserved:** nav items active state `bg-brand-indigo` cứng (UI-SPEC §1.4 LOCKED defer v4.0), header bell/theme toggle/search field, sidebar collapse motion.aside spring animation, 11 trang route children.
- **api.ts public surface unchanged:** `crossHubSearch` signature giữ NGUYÊN — chỉ refactor internal `request` → `requestAbsolute`. Frontend consumer code (CrossHubSearch.tsx) KHÔNG cần đổi.
- **api.ts tryRefresh:** signature + return type + behavior contract giữ NGUYÊN — chỉ thêm `redirect: 'follow'` explicit options + 3 dòng comment D-V3-Phase5-C4 reference.

## Threat Mitigations

| Threat ID | Status | Verify |
|-----------|--------|--------|
| T-5-04 (Login ?return open redirect) | MITIGATED | 4-layer validation chain + 3 vitest test reject (//, INVALID_HUB, postgres reserved) |
| T-5-06 (themeColor XSS via inline style) | MITIGATED | themeColor sourced compile-time registry Plan 05-03 hardcoded TS const, KHÔNG user input + React style={{}} CSS auto-escape |
| T-5-09 (Layout title tampering CURRENT_HUB) | MITIGATED | CURRENT_HUB Plan 05-02 KNOWN_HUBS validated module-level + fallback central nếu unknown |
| T-5-12 (tryRefresh 307 infinite redirect) | MITIGATED | `redirect: 'follow'` explicit D-V3-Phase5-C4 + backend 307 chain bounded (hub con → central 1 hop only, central handles directly) + RFC 7231 preserve POST body |

## Next Plan Handoff

- **Plan 05-05 (Wave 4):** `hub-add.sh` dynamic operator script — depend Plan 05-01 (Caddyfile env) only, có thể chạy parallel với Plan 05-04 (Wave 3 đã DONE).
- **Plan 05-06 (Wave 5 closeout):** Manual smoke test 4 hub × 11 trang + docs update — depend tất cả Plan 05-01..05.
- **Frontend Phase 5 progress:** Wave 0 (vitest infra) ✅ Wave 1 (Caddy) ✅ Wave 2 (api.ts prefix + branding registry) ✅ **Wave 3 (Login + Layout + cross-hub + tryRefresh) ✅ — file này**. Remaining: Wave 4 + Wave 5 = 2 plan.

## Self-Check: PASSED

- [x] `Hub_All/frontend/src/pages/Login.tsx` exists + modified (line 156 `window.location.replace` + line 142 T-5-04 validation)
- [x] `Hub_All/frontend/src/pages/__tests__/Login.spec.tsx` exists (created)
- [x] `Hub_All/frontend/src/Layout.tsx` exists + modified (HUB_BRANDING module-level + sidebar header swap)
- [x] `Hub_All/frontend/src/__tests__/Layout.spec.tsx` exists (created)
- [x] `Hub_All/frontend/src/services/api.ts` exists + modified (requestAbsolute helper + crossHubSearch override + tryRefresh redirect)
- [x] `Hub_All/frontend/src/services/__tests__/api.spec.ts` exists + extended (+4 tests)
- [x] `Hub_All/frontend/src/__tests__/App.spec.tsx` exists + Rule 1 fix
- [x] 4 commits exist: `54fc315`, `ca6f4e4`, `ed721fd`, `61ac731` (verified via `git log --oneline -5`)
- [x] Full vitest 37/37 PASS + tsc --noEmit PASS
