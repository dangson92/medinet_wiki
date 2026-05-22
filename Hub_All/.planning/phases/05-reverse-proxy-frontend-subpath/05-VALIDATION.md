---
phase: 5
slug: reverse-proxy-frontend-subpath
status: done
nyquist_compliant: true
wave_0_complete: true
created: 2026-05-22
verified: 2026-05-23
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Source: `05-RESEARCH.md` §"Validation Architecture (Nyquist)" (Phase 5 mixes frontend + Caddy config + bash script — multi-toolchain).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Backend Framework** | pytest 8.x + httpx AsyncClient + asgi-lifespan + testcontainers (carry forward M2 Phase 10) |
| **Backend Config file** | `api/pyproject.toml` `[tool.pytest.ini_options]` |
| **Backend Quick run** | `cd api && uv run pytest tests/unit -x --tb=short` |
| **Backend Full suite** | `cd api && uv run pytest -m "critical and integration" --maxfail=5` |
| **Frontend Framework** | **Wave 0 GAP** → vitest@^2 + @testing-library/react@^16 + jsdom@^25 (Plan 05-02 Task 0 install) |
| **Frontend Config file** | `frontend/vitest.config.ts` (NEW Wave 0) + `frontend/src/test-setup.ts` (NEW Wave 0) |
| **Frontend Quick run** | `cd frontend && npx vitest run --reporter=verbose` (post Wave 0) |
| **Frontend Full suite** | `cd frontend && npm run lint && npx vitest run` |
| **Caddy validate** | `docker compose exec caddy caddy validate --config /etc/caddy/Caddyfile` |
| **Caddy reload smoke** | `docker compose exec caddy caddy reload --config /etc/caddy/Caddyfile` (idempotent) |
| **Bash syntax check** | `bash -n api/scripts/hub-add.sh` |
| **Compose validate** | `docker compose config --quiet` |
| **Estimated runtime** | FE ~5-10s, BE quick ~30s, BE full ~60-90s, compose+caddy < 5s |

---

## Sampling Rate

- **After every task commit:** Run quick (FE `npx vitest run` HOẶC tsc + BE `uv run pytest tests/unit -x` nếu BE touch + bash `bash -n` nếu script touch).
- **After every plan wave:** Full FE suite + `caddy validate` + `docker compose config --quiet` + BE full (chỉ Wave 4-5 nếu touch script + closeout regression).
- **Before `/gsd-verify-work`:** Full FE suite + `caddy validate` + manual smoke 4 hub × 11 trang Plan 05-06 (D-V3-Phase5-D4).
- **Max feedback latency:** < 90 seconds end-of-task, < 5 phút end-of-wave.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 5-01-01 | 05-01 | 1 | PROXY-01 | T-5-01 (Caddyfile open redirect) | path_regexp anchor `^/<hub>/api/` + handle_path strip | unit (CLI) | `docker compose exec caddy caddy validate --config /etc/caddy/Caddyfile` | ✅ existing caddy CLI | ⬜ pending |
| 5-01-02 | 05-01 | 1 | PROXY-01 | — | WIKI_PUBLIC_DOMAIN + HUBS_ALLOWLIST_REGEX env wire | unit (CLI) | `docker compose config --quiet` exit 0 | ✅ existing | ⬜ pending |
| 5-01-03 | 05-01 | 1 | PROXY-01 | — | `.env.example` document 3 env vars | grep | `grep -q "WIKI_PUBLIC_DOMAIN" .env.example && grep -q "HUBS_ALLOWLIST" .env.example` | ❌ Wave 0 manual | ⬜ pending |
| 5-02-00 | 05-02 | 2 | (Wave 0 infra) | — | vitest framework install + config | unit (npm) | `cd frontend && npx vitest --version` exit 0 | ❌ Wave 0 install | ⬜ pending |
| 5-02-01 | 05-02 | 2 | PROXY-02 | T-5-02 (KNOWN_HUBS allowlist tampering) | hub allowlist runtime check before prefix accept | unit (FE) | `cd frontend && npx vitest run src/services/__tests__/api.spec.ts` | ❌ NEW test file Plan 05-02 | ⬜ pending |
| 5-02-02 | 05-02 | 2 | PROXY-02 | — | App.tsx BrowserRouter basename=APP_BASE | unit (FE) | `cd frontend && npx vitest run src/__tests__/App.spec.tsx` (render mock window.location) | ❌ NEW test Plan 05-02 | ⬜ pending |
| 5-03-01 | 05-03 | 2 | PROXY-04 | — | getBranding registry glob import 4 hub | unit (FE) | `cd frontend && npx vitest run src/branding/__tests__/registry.spec.ts` | ❌ NEW test Plan 05-03 | ⬜ pending |
| 5-03-02 | 05-03 | 2 | PROXY-04 | T-5-03 (logo asset path traversal) | logo path locked `/branding/<hub>/logo.svg` schema | unit (FE) | Same registry.spec.ts assert path matches regex | ❌ NEW | ⬜ pending |
| 5-03-03 | 05-03 | 2 | PROXY-04 | — | SVG placeholder × 4 hub | file exists | `test -f frontend/public/branding/yte/logo.svg` × 4 hub | ❌ NEW asset | ⬜ pending |
| 5-04-01 | 05-04 | 3 | PROXY-02 + PROXY-04 | T-5-04 (open redirect via ?return param) | Login.tsx validate return param ∈ KNOWN_HUBS | unit (FE) | `cd frontend && npx vitest run src/pages/__tests__/Login.spec.tsx` | ❌ NEW test Plan 05-04 | ⬜ pending |
| 5-04-02 | 05-04 | 3 | PROXY-04 | — | Layout.tsx render branding title + logo | unit (FE) | `cd frontend && npx vitest run src/__tests__/Layout.spec.tsx` | ❌ NEW test Plan 05-04 | ⬜ pending |
| 5-04-03 | 05-04 | 3 | PROXY-02 | — | api.crossHubSearch absolute path `/api/search/cross-hub` không prefix | unit (FE) | Same api.spec.ts append assertion | ❌ extend test | ⬜ pending |
| 5-05-01 | 05-05 | 4 | PROXY-01 + FACTOR-04 | T-5-05 (script injection HUB= input) | hub-add.sh regex validate + reserved blacklist (Plan 02-05 carry forward) | unit (bash) | `bash -n api/scripts/hub-add.sh` exit 0 | ✅ existing bash + W0 new assertion | ⬜ pending |
| 5-05-02 | 05-05 | 4 | PROXY-01 | — | step 8 sed-edit `.env` HUBS_ALLOWLIST idempotent | unit (bash) | dry-run `HUB=tmp_test bash api/scripts/hub-add.sh --dry-run` (KHÔNG side effect) | ❌ extend script + test | ⬜ pending |
| 5-05-03 | 05-05 | 4 | PROXY-01 | — | step 9 `caddy reload` zero-downtime command shape | grep | `grep -q "caddy reload" api/scripts/hub-add.sh` | ❌ NEW append | ⬜ pending |
| 5-06-01 | 05-06 | 5 | PROXY-03 | — | CLAUDE.md §3 D6 EXPIRED note | grep | `grep -q "D6 EXPIRED" Hub_All/CLAUDE.md` | ❌ NEW Plan 05-06 | ⬜ pending |
| 5-06-02 | 05-06 | 5 | PROXY-01..04 | — | docs update CLAUDE.md §6 + STATE.md + REQUIREMENTS.md + ROADMAP.md + README.md | grep | grep acceptance criteria 5 file | ❌ NEW Plan 05-06 | ⬜ pending |
| 5-06-03 | 05-06 | 5 | PROXY-03 + R-V3-2 | — | smoke regression 4 hub × 11 trang React M2 COMPAT-01 | manual | Manual checklist 4 hub × 11 trang dev local `docker compose up` + browser inspect | ❌ — Plan 05-06 checkpoint:human-action | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] **Frontend test framework setup** — Add `vitest@^2` + `@testing-library/react@^16` + `@testing-library/jest-dom@^6` + `jsdom@^25` deps via `npm install -D` ở `frontend/package.json` + NEW `frontend/vitest.config.ts` (jsdom environment + path alias) + NEW `frontend/src/test-setup.ts` (jest-dom matchers + cleanup). Ship trong Plan 05-02 Task 0 (Wave 0). Effort ~30 phút.
- [ ] `frontend/src/services/__tests__/api.spec.ts` — Plan 05-02 covers PREFIX/API_BASE/APP_BASE compute với mock `window.location.pathname` 4 scenario (central root, yte prefix, unknown prefix fallback, deep nested path).
- [ ] `frontend/src/branding/__tests__/registry.spec.ts` — Plan 05-03 covers getBranding fallback central nếu hub không có + all 4 hub config shape (logo + title + tagline + themeColor required).
- [ ] `frontend/src/pages/__tests__/Login.spec.tsx` — Plan 05-04 covers useEffect mount redirect nếu prefix !== central + branding theme color render + form submit same-origin.
- [ ] `frontend/src/__tests__/Layout.spec.tsx` — Plan 05-04 covers sidebar title từ `getBranding(CURRENT_HUB).title` + logo src match `/branding/<hub>/logo.svg`.
- [ ] `frontend/src/__tests__/App.spec.tsx` — Plan 05-02 cover `<BrowserRouter basename={APP_BASE}>` render đúng route map per-prefix.

*Wave 0 deliverable: vitest infra + 5 new test file + 1 npm script `"test": "vitest run"` ở package.json.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Caddy auto-TLS handshake `wiki.medinet.vn` ACME flow | PROXY-01 | ACME issuance cần DNS public + Let's Encrypt rate limit — KHÔNG automate được local CI | Plan 05-06 Task 5 checkpoint:human-action — operator deploy prod + verify cert valid 90 ngày `openssl s_client -connect wiki.medinet.vn:443`. Dev local `localhost` → self-signed acceptable. |
| Manual smoke 4 hub × 11 trang React COMPAT-01 | PROXY-03 + R-V3-2 mitigation | Visual regression 11 page React (Dashboard, Documents, Login, Search, ...) — human eye verify layout không break sau D6 expire + prefix rewrite | Plan 05-06 Task 5 checkpoint:human-action — `docker compose up` 4 service + browser visit 11 URL × 4 hub = 44 page-load check. User resume signal: `approved` / `partial: <list>` / `skip smoke` (carry forward Plan 03-05/04-07 pattern). |
| FACTOR-04 hub-add.sh end-to-end live (DB create + compose append + Caddy reload + smoke `curl /<new>/api/health`) | PROXY-01 + FACTOR-04 extend | Live operator workflow — testcontainers KHÔNG mô phỏng `docker compose exec caddy caddy reload` (Caddy admin API in-container) | Plan 05-05 Task 3 manual dry-run (`HUB=tmp_test` cleanup after) + Plan 05-06 closeout checkpoint optional smoke step. |
| Login → branding render → submit → cross-prefix redirect `/yte/dashboard` | PROXY-02 + PROXY-04 | UX flow human verify — vitest cover unit behavior nhưng `window.location.replace` cross-origin redirect cần browser engine | Plan 05-06 Task 5 smoke checklist — visit `https://localhost/yte/login` → assert redirect `https://localhost/login?return=/yte` → assert branding emerald `#10b981` + title "Hub Y tế Medinet" → submit valid credentials → assert URL bar `https://localhost/yte/dashboard`. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies (5-06-03 manual gate flagged explicitly)
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify (verify Plan 05-06 docs tasks have grep verify)
- [ ] Wave 0 covers all MISSING references (vitest infra + 5 new test files)
- [ ] No watch-mode flags (`vitest run` không `vitest watch`)
- [ ] Feedback latency < 90 seconds end-of-task
- [ ] `nyquist_compliant: true` set in frontmatter sau khi planner ship Plan 05-02 Wave 0 task

**Approval:** pending — sẽ flip `nyquist_compliant: true` sau khi planner verify Plan 05-02 ship Wave 0 vitest infra (Task 0).
