---
phase: 05-reverse-proxy-frontend-subpath
plan: 03
subsystem: frontend
tags: [frontend, branding, vite-glob, asset-svg, wcag, v3.0, phase5, proxy-04]

# Dependency graph
requires:
  - phase: 05-reverse-proxy-frontend-subpath
    provides: "Plan 05-02 — CURRENT_HUB export tu api.ts (FE prefix detect) + vitest infra setup (jsdom env + npm script)"
  - phase: 05-reverse-proxy-frontend-subpath
    provides: "Plan 05-01 — Caddy config dist/branding/<hub>/logo.svg serve via file_server (Vite copy public/ verbatim)"
provides:
  - "Vite eager glob branding registry frontend/src/branding/index.ts voi getBranding() fallback + getContrastTextColor() WCAG helper"
  - "BrandingConfig type contract (logo + title + tagline + themeColor) UI-SPEC §1.1 LOCKED"
  - "4 hub initial config (central indigo / yte emerald / duoc sky / hcns amber) — VN diacritics title + tagline"
  - "4 SVG placeholder asset frontend/public/branding/<hub>/logo.svg (Vite copy → Caddy serve, designer hoan doi sau KHONG can rebuild FE)"
  - "T-5-03 path traversal mitigation qua regex constrain registry build + test verify"
  - "T-5-06 XSS themeColor mitigation qua TS const hardcode (KHONG user input)"
  - "Vitest 13 test scenarios cover 4 hub + fallback + WCAG contrast + shape regex"
affects: [phase-05-04-login-layout-branding-wire, phase-05-05-hub-add-extend, phase-05-06-closeout, phase-06-settings-04-hub-registry-dynamic]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Vite import.meta.glob eager static registry (Pattern 5 RESEARCH.md)"
    - "TS as const inline literal types match interface contract (BrandingConfig)"
    - "WCAG relative luminance threshold helper (sRGB linear approx)"
    - "Regex constrain registry build (T-5-03 path traversal mitigation)"

key-files:
  created:
    - "frontend/src/branding/index.ts (84 lines — BrandingConfig type + Vite glob + getBranding fallback + getContrastTextColor WCAG)"
    - "frontend/src/branding/central/index.ts (10 lines — Medinet indigo)"
    - "frontend/src/branding/yte/index.ts (10 lines — emerald)"
    - "frontend/src/branding/duoc/index.ts (10 lines — sky)"
    - "frontend/src/branding/hcns/index.ts (11 lines — amber + WCAG note)"
    - "frontend/public/branding/central/logo.svg (~257 bytes — placeholder text 'M')"
    - "frontend/public/branding/yte/logo.svg (~255 bytes — placeholder text 'Y')"
    - "frontend/public/branding/duoc/logo.svg (~256 bytes — placeholder text 'D')"
    - "frontend/public/branding/hcns/logo.svg (~253 bytes — placeholder text 'H')"
    - "frontend/src/branding/__tests__/registry.spec.ts (110 lines — 13 vitest scenarios)"
  modified: []

key-decisions:
  - "Vite eager glob registry (D-V3-Phase5-D1) — compile-time scan + static imports inlined, KHONG lazy chunk async penalty"
  - "BrandingConfig contract LOCKED (UI-SPEC §1.1) — logo absolute path + title ≤ 24 chars + tagline ≤ 48 chars + themeColor hex 7-char"
  - "getContrastTextColor threshold 0.6 (Rule 1 fix) — design intent CHI hcns amber trigger 'slate-900', emerald/sky/indigo PASS 'white'"
  - "T-5-03 mitigation regex constrain registry build ^[a-z][a-z0-9_]{0,15}$ — path traversal '../', '/', special chars rejected"
  - "T-5-06 mitigation themeColor TS const hardcode 4 hub config — KHONG user input, KHONG dynamic interpolation"
  - "SVG placeholder text-only initial letter (M/Y/D/H) viewBox 64x64 monochrome white fill — designer hoan doi sau KHONG can rebuild FE (Vite copy public/ verbatim)"

patterns-established:
  - "Vite import.meta.glob with eager: true — registry build compile-time, KHONG lazy chunks"
  - "Silent fallback to default config (central) + dev-only console.warn for unknown key"
  - "Inline regex constrain trong loop registry build = T-XX mitigation surface"
  - "TS as const + readonly interface fields = inline literal type match contract"
  - "WCAG relative luminance helper (sRGB simplified linear) = visual contrast mitigation pattern"

requirements-completed: [PROXY-04]

# Metrics
duration: ~5min
completed: 2026-05-23
---

# Phase 5 Plan 03: Per-hub Branding Registry + SVG Assets + WCAG Helper Summary

**Vite eager glob registry frontend/src/branding/ + 4 hub initial config (central indigo / yte emerald / duoc sky / hcns amber) + 4 SVG placeholder asset (text-only M/Y/D/H 256 bytes each) + getContrastTextColor WCAG mitigation helper (CHI hcns amber trigger 'slate-900' per UI-SPEC §1.5).**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-05-22T17:46:41Z
- **Completed:** 2026-05-22T17:51:31Z
- **Tasks:** 3/3
- **Files created:** 10 (1 registry + 4 hub config + 4 SVG + 1 vitest spec)
- **Files modified:** 0

## Accomplishments

- **PROXY-04 registry layer 1 ready cho Plan 05-04 wire UI (Login.tsx + Layout.tsx).** Vite eager glob compile-time scan `'./*/index.ts'` + helper `getBranding(hub)` silent fallback central — designer hoan doi SVG file mà KHONG can rebuild FE.
- **4 hub initial config** voi VN diacritics title + tagline preserved UTF-8 (Hub Y tế / Hub Dược / Hub HCNS — chữ có dấu giữ nguyên trong source).
- **getContrastTextColor WCAG mitigation helper** (UI-SPEC §1.5 design intent) — CHI hcns amber (#f59e0b luminance ~0.65) trigger 'slate-900' override; 3 hub còn lại central/yte/duoc PASS white overlay.
- **T-5-03 path traversal mitigation** — regex constrain `^\.\/([a-z][a-z0-9_]{0,15})\/index\.ts$` registry build loop reject `'../'`, `'/'`, special chars; asset path schema hardcode `/branding/<hub>/logo.svg`.
- **T-5-06 XSS themeColor mitigation** — themeColor TS const hardcode 4 hub config, KHONG user input. Plan 05-04 render qua React `style={{...}}` CSS escaping built-in.
- **13/13 vitest test PASS** (4 hub + 3 fallback + 5 contrast + 1 shape regex) trong 1.42s.

## Task Commits

Each task was committed atomically:

1. **Task 1: Branding registry module + WCAG contrast helper** — `550b5e0` (feat)
2. **Task 2: 4 hub branding config (central+yte+duoc+hcns)** — `9a8576a` (feat)
3. **Task 3: 4 SVG placeholder + vitest registry spec (13/13 PASS)** — `4a83ef3` (chore)

## Files Created

| File | Lines | Purpose |
|------|-------|---------|
| `frontend/src/branding/index.ts` | 84 | BrandingConfig type + Vite eager glob + getBranding fallback + getContrastTextColor WCAG helper |
| `frontend/src/branding/central/index.ts` | 10 | Medinet indigo #6366f1 (M2 brand carry forward) |
| `frontend/src/branding/yte/index.ts` | 10 | Hub Y tế emerald #10b981 (health=green) |
| `frontend/src/branding/duoc/index.ts` | 10 | Hub Dược sky #0ea5e9 (clinical=blue) |
| `frontend/src/branding/hcns/index.ts` | 11 | Hub HCNS amber #f59e0b (HR=warm) + WCAG inline note |
| `frontend/public/branding/central/logo.svg` | ~257 bytes | Placeholder text "M" viewBox 64×64 white fill |
| `frontend/public/branding/yte/logo.svg` | ~255 bytes | Placeholder text "Y" |
| `frontend/public/branding/duoc/logo.svg` | ~256 bytes | Placeholder text "D" |
| `frontend/public/branding/hcns/logo.svg` | ~253 bytes | Placeholder text "H" |
| `frontend/src/branding/__tests__/registry.spec.ts` | 110 | 13 vitest scenarios |

## Decisions Made

- **D-V3-Phase5-D1 + UI-SPEC §1.1 LOCKED carry forward:** Vite eager glob static registry, KHONG runtime API fetch, KHONG CSS injection.
- **getContrastTextColor threshold = 0.6** (Rule 1 fix — see Deviations below). Design intent UI-SPEC §1.5 row 132 mitigation: CHI hcns amber trigger 'slate-900'.
- **SVG placeholder strategy:** Text-only initial letter (M/Y/D/H) monochrome white fill viewBox 64×64. Lý do: file size minimal (~256 bytes ≪ 4KB budget), designer override file mà KHONG cần rebuild FE (Vite copy `public/` verbatim → `dist/` → Caddy `file_server`).
- **Export `_registry_internal_for_test`:** Cho phép test introspection nhưng KHONG dùng ở production component (naming convention dấu underscore + suffix `_internal_for_test`).
- **Hcns inline WCAG note:** Source file `hcns/index.ts` comment ghi `amber #f59e0b vs white = 2.07:1 FAIL` để developer touch component sau biết phải dùng `getContrastTextColor()` helper.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] getContrastTextColor threshold 0.55 → 0.6**

- **Found during:** Task 3 (vitest run — test `returns "white" for emerald yte #10b981` FAIL)
- **Issue:** Plan ghi threshold `> 0.55` cho getContrastTextColor return 'slate-900'. Tuy nhiên relative luminance thực tế:
  - central #6366f1 ≈ 0.437 → 'white' ✓
  - yte #10b981 ≈ **0.569** > 0.55 → 'slate-900' ✗ (mâu thuẫn design intent UI-SPEC §1.5)
  - duoc #0ea5e9 ≈ 0.583 > 0.55 → 'slate-900' ✗ (mâu thuẫn)
  - hcns #f59e0b ≈ 0.651 → 'slate-900' ✓ (đúng intent)
  - Plan test cases expect emerald + sky return 'white' — chỉ hcns return 'slate-900'. Threshold 0.55 contradict cả plan test expectations VÀ UI-SPEC §1.5 design intent ("CHI hcns case mitigation").
- **Fix:** Nâng threshold `0.55` → `0.6` trong `frontend/src/branding/index.ts::getContrastTextColor`. Sau fix: central/yte/duoc luminance đều ≤ 0.6 → 'white' (PASS WCAG AA large-text trên gradient per UI-SPEC §1.5); hcns 0.651 > 0.6 → 'slate-900' (override per §1.5 mitigation).
- **Files modified:** `frontend/src/branding/index.ts` (threshold + comment + plan deviation note)
- **Verification:** 13/13 vitest PASS sau fix. Full suite 23/23 (13 branding + 7 api + 3 App) — KHONG break Plan 05-02 tests.
- **Committed in:** `4a83ef3` (Task 3 commit — bundle với SVG + test file vì fix discovered during Task 3 verification, source file change minimal 2 dòng + 1 comment block)

---

**Total deviations:** 1 auto-fixed (1 Rule 1 bug)
**Impact on plan:** Threshold adjustment essential for design intent alignment (UI-SPEC §1.5 CHI hcns trigger). KHONG scope creep — semantic identical, only threshold number change để match expected behavior. Plan test cases vẫn pass (intent đúng từ đầu, chỉ implementation number sai).

## Issues Encountered

- **Vitest test FAIL (1/13)** lần đầu chạy do bug Rule 1 threshold 0.55 — fixed inline qua Rule 1 trong cùng Task 3. KHÔNG cần checkpoint user.
- KHONG có CRLF/LF issue (git warning convert LF→CRLF expected on Windows, không ảnh hưởng test).

## User Setup Required

None — Plan 05-03 ship per-hub branding registry + 4 SVG asset placeholder. Designer có thể hoán đổi SVG file ở `frontend/public/branding/<hub>/logo.svg` sau Phase 5 ship MÀ KHÔNG cần rebuild FE (Vite copy `public/` verbatim → `dist/` → Caddy serve). Khi cần thêm hub mới sau Phase 6 SETTINGS-04 dynamic admin tool (defer v4.0): drop file `branding/<hub>/index.ts` + `public/branding/<hub>/logo.svg` rồi rebuild FE 1 lần.

## Threat Surface Audit

Plan đã thực thi 2 STRIDE mitigation per `<threat_model>` PLAN.md:

| Threat ID | Mitigation status | Verification |
|-----------|--------------------|--------------|
| T-5-03 (Tampering / path traversal asset path) | ✅ Mitigated | Regex constrain `^\.\/([a-z][a-z0-9_]{0,15})\/index\.ts$` trong registry build loop (frontend/src/branding/index.ts line 27-32). Asset path schema hardcode `/branding/<hub>/logo.svg` trong 4 hub config TS file. Test scenario 7 (`fallbacks to central for hub with special chars '../etc/passwd'`) + scenario 13 (shape regex `^\/branding\/[a-z][a-z0-9_]*\/logo\.svg$`) verify behavior. |
| T-5-06 (XSS themeColor inline CSS variable) | ✅ Mitigated | themeColor hardcoded TS const trong 4 hub config (central/yte/duoc/hcns/index.ts) — KHONG user input. Plan 05-04 sẽ render qua React `style={{...}}` (CSS escaping built-in). |
| T-5-13 (Info disclosure SVG content) | accept (no mitigation needed) | Placeholder text-only initial letter monochrome, no sensitive data. |

KHONG có threat flag mới phát sinh — Plan 05-03 chỉ động vào FE asset layer registry + static SVG, KHONG new endpoint / auth path / schema change.

## Next Plan Readiness

- **Plan 05-04 (Wave 3):** Wire `getBranding(CURRENT_HUB)` + `getContrastTextColor()` ở `Login.tsx` (logo + title + tagline + themeColor gradient + submit button per UI-SPEC §1.2-§1.5) + `Layout.tsx` sidebar header (logo + title swap branding + hover ring themeColor per UI-SPEC §3). Plan 05-04 deps cả 05-02 (CURRENT_HUB) + 05-03 (registry) — Wave 3 sẵn sàng sau khi Plan 05-03 ship.
- **Plan 05-05 (Wave 4 — independent):** Extend `scripts/hub-add.sh` với caddy reload + HUBS_ALLOWLIST update — Wave 4 sẵn sàng (KHONG depend 05-03).
- **Phase 6 SETTINGS-04** (defer v4.0): hub_registry central table source-of-truth — sẽ replace fallback hardcode `KNOWN_HUBS` trong `api.ts` + branding registry hiện tại sẽ stay as static glob (designer admin UI defer v4.0).
- **R-V3-2 mitigation (D6 expire frontend rewrite regress):** Plan 05-03 chỉ ADD new files (KHONG touch 11 trang nội dung), R-V3-2 risk ≈ 0 cho plan này. Wave 3 Plan 05-04 sẽ là plan đầu tiên touch existing React component (Login.tsx + Layout.tsx) — R-V3-2 sẽ được smoke regression manual checklist Plan 05-06 closeout.

## Self-Check: PASSED

**1. Created files exist (10/10):**
- FOUND: `frontend/src/branding/index.ts`
- FOUND: `frontend/src/branding/central/index.ts`
- FOUND: `frontend/src/branding/yte/index.ts`
- FOUND: `frontend/src/branding/duoc/index.ts`
- FOUND: `frontend/src/branding/hcns/index.ts`
- FOUND: `frontend/public/branding/central/logo.svg`
- FOUND: `frontend/public/branding/yte/logo.svg`
- FOUND: `frontend/public/branding/duoc/logo.svg`
- FOUND: `frontend/public/branding/hcns/logo.svg`
- FOUND: `frontend/src/branding/__tests__/registry.spec.ts`

**2. Commits exist (3/3):**
- FOUND: `550b5e0` (Task 1 — feat branding registry module)
- FOUND: `9a8576a` (Task 2 — feat 4 hub branding config)
- FOUND: `4a83ef3` (Task 3 — chore 4 SVG + vitest spec 13/13 PASS + Rule 1 fix)

**3. Acceptance criteria PASS table:**

| Criterion | Status | Evidence |
|-----------|--------|----------|
| `BrandingConfig` interface exported | ✅ | `grep "export interface BrandingConfig" frontend/src/branding/index.ts` |
| `getBranding` function exported | ✅ | `grep "export function getBranding"` |
| `getContrastTextColor` function exported | ✅ | `grep "export function getContrastTextColor"` |
| Vite `import.meta.glob` used | ✅ | `grep "import.meta.glob"` |
| Eager mode `eager: true` | ✅ | `grep "eager: true"` |
| 4 hub config exist | ✅ | central/yte/duoc/hcns each with `as const` |
| themeColor values correct (4 hub) | ✅ | #6366f1, #10b981, #0ea5e9, #f59e0b |
| 4 SVG files exist | ✅ | All 4 with viewBox 0 0 64 64 + fill #FFFFFF |
| SVG size ≤ 4 KB each | ✅ | ~253-257 bytes each (well under budget) |
| Vitest spec file exists | ✅ | `frontend/src/branding/__tests__/registry.spec.ts` |
| 13/13 vitest test PASS | ✅ | 1.42s duration, 0 failure (after Rule 1 fix) |
| Full vitest suite PASS | ✅ | 23/23 (13 branding + 7 api + 3 App) — KHONG break Plan 05-02 |
| `npm run lint` (tsc --noEmit) PASS | ✅ | exit 0 |
| T-5-03 path traversal regex in test | ✅ | Test scenario 7 `'../etc/passwd'` + scenario 13 regex `/^\/branding\/[a-z][a-z0-9_]*\/logo\.svg$/` |
| T-5-06 themeColor hardcode (no user input) | ✅ | All 4 hub config themeColor literal hex string |
| VN diacritics preserve | ✅ | "Hub Y tế", "Hub Dược", "Chính sách nhân sự" — UTF-8 source |
| 3 atomic commits with VN messages | ✅ | All 3 commits VN prose + Co-Authored-By trailer |

---

*Phase: 05-reverse-proxy-frontend-subpath*
*Plan: 03*
*Completed: 2026-05-23*
