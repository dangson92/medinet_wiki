# Phase 5: Reverse Proxy + Frontend Subpath - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in `05-CONTEXT.md` — this log preserves the alternatives considered.

**Date:** 2026-05-22
**Phase:** 5-reverse-proxy-frontend-subpath
**Areas discussed:** A · Caddy layout + dynamic hub, B · Frontend prefix detect 1 build, C · Login flow hub con → central, D · Per-hub branding architecture
**Mode:** `/gsd-discuss-phase 5 --chain` (interactive — user chose all 4 gray areas, then 4 sub-questions per area, all Recommended option)

---

## A · Caddy Layout + Dynamic Hub Routing

### A1 — Caddy config layout

| Option | Description | Selected |
|--------|-------------|----------|
| 1 Caddyfile + path_regexp matcher | Single Caddyfile cho `wiki.medinet.vn` + `path_regexp ^/(yte\|duoc\|hcns\|...)/api/(.*)$` + HUBS_ALLOWLIST env render regex | ✓ |
| Base + per-hub fragment auto-gen | `import Caddyfile.d/*.caddy` + sed-substitute per-hub fragment giống docker-compose.override.yml.template | |
| 1 Caddyfile + handle wildcard {hub} | Caddy expression `{http.request.uri.path.0}` raw — KHÔNG allowlist | |

**User's choice:** 1 Caddyfile + path_regexp matcher
**Notes:** Recommended chọn vì 1 file single source-of-truth + Caddy native regex matcher + HUBS_ALLOWLIST env-driven sync với A3 hub-add. REJECT fragment (nhiều file complex). REJECT wildcard (unknown hub forward fail DNS Docker → KHÔNG fail-fast).

### A2 — Prefix strip semantic

| Option | Description | Selected |
|--------|-------------|----------|
| Strip `/{hub}` từ path | Caddy `handle_path /<hub>/*` → upstream nhận `/api/health` KHÔNG `/yte/api/health`. M2 router code unchanged. | ✓ |
| Forward nguyên prefix (no strip) | Backend nhận `/yte/api/health` + Settings.subpath_prefix + FastAPI mount under prefix | |

**User's choice:** Strip /{hub} từ path
**Notes:** Phù hợp D-V3-Phase2 KISS 1 codebase deploy. M2 router code KHÔNG cần biết prefix. Central giữ root `/api/*` KHÔNG strip.

### A3 — FACTOR-04 `make hub-add` extend

| Option | Description | Selected |
|--------|-------------|----------|
| Append HUBS_ALLOWLIST + caddy reload | hub-add.sh thêm step sed-edit .env + `caddy reload` zero-downtime. Smoke `curl https://wiki.localhost/<new>/api/health` PASS | ✓ |
| Auto-gen Caddyfile.d/<hub>.caddy fragment | Fragment-based — chỉ chọn nếu A1 fragment | |
| Zero-touch — caddy regex generic | Chỉ chọn nếu A1 wildcard | |

**User's choice:** Append HUBS_ALLOWLIST + caddy reload
**Notes:** Consistent với A1 single Caddyfile. Caddy hot reload API zero-downtime. Smoke test pattern carry forward Plan 02-05.

### A4 — Domain placeholder dev vs prod

| Option | Description | Selected |
|--------|-------------|----------|
| WIKI_PUBLIC_DOMAIN env | Pattern song song MCP_PUBLIC_DOMAIN. `localhost` dev tự-sign / `wiki.medinet.vn` prod ACME | ✓ |
| Unified PUBLIC_DOMAIN một domain | 1 domain medinet.vn với 2 server block wiki + mcp | |
| Hardcode wiki.medinet.vn + localhost fallback | Caddyfile cứng — KHÔNG env-driven | |

**User's choice:** WIKI_PUBLIC_DOMAIN env
**Notes:** Carry forward M2 Phase 8.3 env-driven domain pattern. Minimal config. docker-compose caddy service thêm 1 env var. `.env.example` document.

---

## B · Frontend Prefix Detect 1 Build (PROXY-02 + GA-V3-C confirm)

### B1 — Prefix detect method

| Option | Description | Selected |
|--------|-------------|----------|
| pathname.split + KNOWN_HUBS allowlist | Runtime detect `window.location.pathname.split('/')[1]` + allowlist (window.__HUB_CONFIG__ injected by Caddy hoặc fallback hardcode) | ✓ |
| Cookie/header injected from server | Caddy `Set-Cookie: hub=<name>` hoặc `<meta name='hub'>` HTML rewrite | |
| Build-time injected via Vite env | `VITE_HUB_NAME=yte vite build` matrix N hub | |

**User's choice:** pathname.split + KNOWN_HUBS allowlist
**Notes:** GA-V3-C khuyến nghị seed CONFIRMED. 1 build dùng chung. Runtime config injected qua Caddy `window.__HUB_CONFIG__` sync HUBS_ALLOWLIST. Fallback hardcode 3 hub base cho dev safety.

### B2 — Vite `base` + static asset path

| Option | Description | Selected |
|--------|-------------|----------|
| Vite base='/' + Caddy serve dùng chung | Asset path absolute `/assets/*` work cross-prefix. Caddy file_server + try_files SPA fallback. react-router basename runtime | ✓ |
| Vite base='./' relative + per-prefix HTML | Relative path fail nested route — kết hợp <base href> | |
| Vite build runtime base injection | Caddy inject `<base href='/{hub}/'>` HTML — response rewrite | |

**User's choice:** Vite base='/' + Caddy serve dùng chung
**Notes:** Default Vite config. Absolute asset path work cross-prefix. Caddy serve dist/ + SPA fallback.

### B3 — react-router basename + WebSocket

| Option | Description | Selected |
|--------|-------------|----------|
| BrowserRouter basename + WS qua API base | `<BrowserRouter basename={APP_BASE}>` auto prepend prefix. WS path `${API_BASE}/ws` | ✓ |
| Hardcode route với prefix, KHÔNG basename | Manual prefix mỗi `<Route path>` — 13 page change | |

**User's choice:** BrowserRouter basename + WS qua API base
**Notes:** Clean 1 thay đổi App.tsx. react-router auto prepend basename. WS placeholder defer v4.0.

### B4 — Login redirect handling (UX thực tế)

| Option | Description | Selected |
|--------|-------------|----------|
| Frontend Login.tsx tự redirect window.location → central /login | useEffect detect prefix → `window.location.replace('/login?return=/' + PREFIX)` | ✓ |
| Form action POST cross-origin to central + CORS | Login.tsx POST `https://wiki.medinet.vn/api/auth/login` cross-origin | |
| Plan 03-04 307 backend transparent | Frontend POST `/<hub>/api/auth/login` → backend 307 → fetch auto-follow | |

**User's choice:** Frontend Login.tsx tự redirect window.location → central /login
**Notes:** Same-origin (wiki.medinet.vn root scope) — no CORS. Backend 307 Plan 03-04 vẫn là failsafe (LOCKED) + áp dụng cho api.ts tryRefresh().

---

## C · Login + Auth Flow

### C1 — Central /login UX khi user từ hub con redirect tới

| Option | Description | Selected |
|--------|-------------|----------|
| Central /login parse ?return + auto redirect post-login | Parse `?return=/<hub>` + branding hub con qua `getBranding(returnHub)` static + post-login redirect `/<hub>/dashboard` | ✓ |
| Central /login + 302 redirect không custom UX | UX gốc Medinet KHÔNG branding hub con | |
| Per-hub /login page — KHÔNG redirect | Mỗi hub serve /login local + cross-origin POST CORS | |

**User's choice:** Central /login parse ?return + auto redirect post-login
**Notes:** URL bar `wiki.medinet.vn/login` nhất quán entry-point SSO; branding theo hub. Token same-origin → share xuyên subpath.

### C2 — Token storage + cross-subpath auth state

| Option | Description | Selected |
|--------|-------------|----------|
| localStorage same-origin | M2 pattern carry forward UNCHANGED. wiki.medinet.vn cùng origin → share xuyên subpath | ✓ |
| httpOnly cookie path=/ Set-Cookie | An toàn XSS nhưng đổi M2 contract — defer v4.0 HARD-V4-05 | |
| sessionStorage per-tab | Phá UX 2-tab — token lifetime ngắn | |

**User's choice:** localStorage same-origin
**Notes:** Minimal change M2. XSS CONCERN M2 carry forward defer v4.0.

### C3 — Logout flow

| Option | Description | Selected |
|--------|-------------|----------|
| Hub con xuống local logout endpoint | Plan 03-04 LOCKED: logout LOCAL + Redis blacklist cross-process | ✓ |
| Hub con redirect 307 tới central /api/auth/logout | Mâu thuẫn với Plan 03-04 chọn LOCAL cho logout/me | |

**User's choice:** Hub con xuống local logout endpoint
**Notes:** Plan 03-04 D-V3-Phase3-G LOCKED. Phase 5 KHÔNG đảo chiều.

### C4 — Refresh token + token expiry flow

| Option | Description | Selected |
|--------|-------------|----------|
| Frontend fetch /api/auth/refresh → backend 307 → central | api.ts tryRefresh giữ NGUYÊN POST `${API_BASE}/api/auth/refresh` → ở hub con 307 follow | ✓ |
| Frontend trực tiếp POST central /api/auth/refresh cross-origin | Bỏ qua Plan 03-04 LOCKED 307 chain | |

**User's choice:** Frontend fetch /api/auth/refresh → backend 307 → central
**Notes:** Plan 03-04 LOCKED carry forward. Phase 5 chỉ verify FE compatible (redirect: 'follow' explicit + POST body preserve qua 307 RFC 7231).

---

## D · Per-hub Login Branding

### D1 — Branding source-of-truth

| Option | Description | Selected |
|--------|-------------|----------|
| Static FE config + glob import | `frontend/src/branding/<hub>/index.ts` + Vite `import.meta.glob` eager + helper `getBranding(hub)` | ✓ |
| Runtime API fetch /api/hubs/branding/<hub> | Backend central trả từ DB hubs.branding_json + Redis cache | |
| CSS custom properties injected qua HTML <style> | Caddy/backend inject `<style>:root{--brand-...}` | |

**User's choice:** Static FE config + glob import
**Notes:** Zero backend call + instant load + version control. FACTOR-04 dynamic hub mới phải rebuild FE (acceptable v3.0-b). Admin UI database-driven defer v4.0.

### D2 — Branding scope (số component)

| Option | Description | Selected |
|--------|-------------|----------|
| Login.tsx + Layout sidebar header | 2 component touch: Login (logo+title+tagline+themeColor) + Layout sidebar (logo+title) | ✓ |
| Theme color tất cả component qua CSS variables | Full re-skin Tailwind cascade — scope creep R-V3-2 risk | |
| Chỉ Login.tsx — KHÔNG đụng Layout | M2 Layout giữ Medinet branding — nhưng PROXY-04 spec mâu thuẫn | |

**User's choice:** Login.tsx + Layout sidebar header
**Notes:** PROXY-04 satisfied. Smoke regression M2 COMPAT-01 11 trang giảm thiểu risk (R-V3-2). Page nội dung giữ Medinet styling.

### D3 — Asset logo storage

| Option | Description | Selected |
|--------|-------------|----------|
| frontend/public/branding/<hub>/logo.svg | Static asset Vite copy → dist + Caddy serve | ✓ |
| Inline SVG TypeScript trong branding/<hub>/index.ts | 1 file SoT — large SVG bundle bloat | |
| External CDN URL config-driven | Dynamic update no rebuild — external dep | |

**User's choice:** frontend/public/branding/<hub>/logo.svg
**Notes:** Standard Vite practice. Easy designer edit. Git track Yes.

### D4 — Smoke regression strategy cho M2 COMPAT-01

| Option | Description | Selected |
|--------|-------------|----------|
| Manual checklist + dev local 4 hub | Human visit 4 URL × 11 trang + screenshot diff M2 baseline | ✓ |
| Playwright e2e per-hub | Add test suite — setup overhead inconsistent v3.0-b | |
| Skip smoke runtime — in-process only | Defer Phase 7 MIGRATE-05 — KHÔNG đủ cho UX branding | |

**User's choice:** Manual checklist + dev local 4 hub
**Notes:** Phase 5 cần human verify UX branding + 11 trang KHÔNG break. KHÔNG defer toàn bộ smoke (PROXY-04 + R-V3-2 mandatory).

---

## Claude's Discretion (areas user deferred)

- Caddy `replace_response` HTML rewrite chi tiết vs backend serve index.html dynamic.
- Caddyfile fragment structure (header global directives placement).
- Login.tsx file structure (single vs split components).
- KNOWN_HUBS fallback hardcode source location.
- `<base href>` HTML inclusion (chỉ nếu B2 follow-up cần).
- Caddy `respond` directive cho unknown hub URL.
- branding schema extensibility (favicon, OG meta, manifest.json per-hub).
- Cookie Path attribute (M2 KHÔNG dùng cookie auth).
- Caddy access log format + label hub_name.
- HMR dev workflow với Caddy reverse proxy.
- Tailwind theme.extend cho themeColor.
- M2 mockData.ts cleanup.
- WS path (defer v4.0).
- /branding/<hub>/logo.svg fallback nếu file missing.

## Deferred Ideas

Xem `05-CONTEXT.md` §deferred section đầy đủ:
- Per-hub admin branding UI database-driven → v4.0 admin tool
- Tailwind theme cascade toàn bộ → v4.0 re-skin
- Playwright e2e per-hub → v4.0 HARD-V4-04
- HMR dev workflow → Claude's Discretion plan
- Cloudflare Tunnel migration → v4.0+
- MCP subpath migration → defer Phase 7 MIGRATE-04
- httpOnly cookie → v4.0 HARD-V4-05
- WS/SSE → v4.0 HARD-V4-03
- Per-hub favicon + manifest → v4.0
- Hub config DB-driven → Phase 6 SETTINGS-04
- Cross-hub UI redirect implementation → Claude's Discretion plan

---

*Audit log generated: 2026-05-22 sau /gsd-discuss-phase 5 --chain — 4 area × 4 sub-question = 16 decision LOCKED Recommended path. Source-of-truth: 05-CONTEXT.md.*
