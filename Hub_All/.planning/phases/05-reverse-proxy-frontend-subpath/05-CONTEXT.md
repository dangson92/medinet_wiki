---
phase: 5
phase_name: Reverse Proxy + Frontend Subpath
slug: reverse-proxy-frontend-subpath
milestone: v3.0
gathered: 2026-05-22
source: /gsd-discuss-phase 5 --chain (interactive — 4 gray area do user selected + 16 sub-question Recommended path)
status: Ready for planning
---

# Phase 5: Reverse Proxy + Frontend Subpath — Context

**Gathered:** 2026-05-22
**Status:** Ready for planning
**Source:** `/gsd-discuss-phase 5 --chain` — interactive discussion 4 gray area do user chọn (A Caddy layout + dynamic hub, B Frontend prefix detect 1 build, C Login flow hub con → central, D Per-hub branding architecture). 16 sub-question đều LOCKED theo Recommended option. Phase 5 mở v3.0-b sau Phase 4 DONE 2026-05-22, parallel-able với Phase 6 SETTINGS (cùng depend Phase 3).

---

<domain>
## Phase Boundary

**WHAT phase 5 ships:**

1. **Caddy reverse proxy mở rộng cho wiki domain** — Bổ sung server block `{$WIKI_PUBLIC_DOMAIN}` vào `Hub_All/Caddyfile` (song song với block MCP đã có Phase 8.3 M2). Route 3 nhóm path:
   - `path_regexp hub_api ^/(yte|duoc|hcns|...)/api/(.*)$` → `reverse_proxy http://python-api-{re.hub_api.1}:8080` + `handle_path /{re.hub_api.1}/*` strip prefix.
   - `/api/*` → `reverse_proxy http://python-api-central:8080` (KHÔNG strip).
   - `/{hub}/...` (SPA route) + `/...` (central SPA) → serve static `dist/` qua Caddy `file_server` + `try_files {path} /index.html` SPA fallback.
   - Hub allowlist render từ env `HUBS_ALLOWLIST=yte,duoc,hcns,...` (Caddy template engine `{$HUBS_ALLOWLIST}` HOẶC env-var trong path_regexp build script).
2. **Frontend 1 build prefix detect runtime** — Sửa `frontend/src/services/api.ts` + `App.tsx` để detect prefix từ `window.location.pathname.split('/')[1]` + KNOWN_HUBS allowlist (runtime config). Tính `API_BASE` (`/<hub>/api` hoặc `/api`) + `APP_BASE` (`/<hub>` hoặc `''`). Pass `APP_BASE` vào `<BrowserRouter basename={APP_BASE}>` để react-router auto prepend. Vite build với `base: '/'` — asset path absolute `/assets/*` Caddy serve dùng chung cho mọi prefix.
3. **D-V3-06 D6 expire formally** — Update `Hub_All/CLAUDE.md` §3 ghi D6 hết hiệu lực ở Phase 5 v3.0-05. Cho phép frontend rewrite cho prefix detect + login redirect + per-hub branding. M2 contract URL/envelope vẫn carry forward (KHÔNG đổi shape API response).
4. **Login redirect chain hub con → central** — Frontend `Login.tsx` mount detect prefix → nếu prefix !== central → `window.location.replace('https://wiki.medinet.vn/login?return=/' + PREFIX)`. Central `/login` parse `?return=` + render branding của hub con (qua static glob import `getBranding(returnHub)`) + sau đăng nhập thành công `localStorage.setItem('access_token', ...)` (same-origin) + `window.location.replace('/' + returnHub + '/dashboard')`. **NOTE backward compat Plan 03-04 SSO-02:** backend hub con `/api/auth/login` + `/api/auth/refresh` đã 307 → central (LOCKED Phase 3); FE Login.tsx CHỈ submit form trên central, nên 307 backend path là failsafe + áp dụng cho api.ts `tryRefresh()` (POST `${API_BASE}/api/auth/refresh` từ hub con → backend 307 → browser auto-follow).
5. **Per-hub login branding** — Tạo `frontend/src/branding/<hub>/index.ts` per-hub (4+: central, yte, duoc, hcns + dynamic FACTOR-04) export `{ logo: '/branding/<hub>/logo.svg', title: 'Hub Y tế Medinet', tagline: '...', themeColor: '#xxx' }`. Glob import: `frontend/src/branding/index.ts` dùng `import.meta.glob('./*/index.ts', { eager: true })` + helper `getBranding(hubName) → BrandingConfig`. Asset SVG: `frontend/public/branding/<hub>/logo.svg` (Vite copy → serve qua Caddy `/branding/<hub>/logo.svg`). 2 component sử dụng branding: `Login.tsx` (logo + title + tagline + theme color hex render qua inline style) + `Layout.tsx` sidebar header (logo + `${title}` thay cho "Medinet Wiki" hardcode). Các page nội dung khác (Dashboard, Documents, ...) giữ Medinet branding gốc.
6. **api.ts rewrite cho prefix-aware base URL** — Thay hardcode `${window.location.hostname}:8180` bằng runtime detect:
   ```typescript
   const KNOWN_HUBS = (window as any).__HUB_CONFIG__?.allowlist || ['yte', 'duoc', 'hcns']; // runtime config
   const seg = window.location.pathname.split('/').filter(Boolean)[0];
   const PREFIX = seg && KNOWN_HUBS.includes(seg) ? seg : null;
   const API_BASE = PREFIX ? `/${PREFIX}/api` : '/api';
   const APP_BASE = PREFIX ? `/${PREFIX}` : '';
   ```
   M2 endpoint path `/api/auth/login` → wrapper `${API_BASE}/auth/login`. Mọi `fetch(${API_BASE}/path)` đi qua Caddy strip prefix → đúng hub con backend.
7. **Runtime hub config injection** — Caddy serve `index.html` với `<script>window.__HUB_CONFIG__ = { allowlist: ['yte','duoc','hcns'], current: 'yte' }</script>` injected via `replace_response` directive HOẶC backend `/index.html` endpoint dynamic render. Recommended A1 chọn 1 Caddyfile + path_regexp → injection qua Caddy `replace` directive đọc env `HUBS_ALLOWLIST`. (Implementation chốt cụ thể ở plan — Claude's Discretion).
8. **make hub-add extend FACTOR-04** — `scripts/hub-add.sh` thêm 2 step sau khi DB tạo + override.yml append (Plan 02-05 carry forward):
   - Step 8: cập nhật `.env` HUBS_ALLOWLIST=`<old>,<new>` (sed-edit hoặc rewrite).
   - Step 9: `docker compose exec caddy caddy reload --config /etc/caddy/Caddyfile` (zero-downtime reload).
   - Smoke checkpoint Task: `curl https://wiki.localhost/<new>/api/health` PASS sau reload.

**WHAT phase 5 KHÔNG ship:**

- **System settings sync (rag-config + api_keys + hub_registry HTTP pull TTL)** — defer Phase 6 SETTINGS-01..04.
- **Migration data từ M2 medinet_central cũ** sang DB hub con — defer Phase 7 MIGRATE-01..03.
- **Smoke E2E 3 hub con + central golden path runtime DOCKER PROD** — defer Phase 7 MIGRATE-05 (Phase 5 chỉ smoke local checklist dev D4).
- **httpOnly cookie token storage migration** — defer v4.0 HARD-V4-05 (M2 carry forward localStorage XSS concern accept).
- **Theme color cascade toàn bộ component qua Tailwind config dynamic** — Phase 5 chỉ apply theme color ở Login.tsx + Layout sidebar header (D2 chọn). Full re-skin defer v4.0.
- **Playwright E2E per-hub smoke** — D4 chọn manual checklist dev local.
- **Cloudflare Tunnel / alternative reverse proxy** — Caddy auto-TLS pattern carry forward M2 Phase 8.3 (KHÔNG re-evaluate).
- **MCP service migrate sang subpath `wiki.medinet.vn/mcp`** — defer Phase 7 MIGRATE-04 (giữ `mcp.medinet.vn` subdomain riêng).

</domain>

<decisions>
## Implementation Decisions

### A · Caddy Layout + Dynamic Hub Routing (PROXY-01 + FACTOR-04 extend)

- **D-V3-Phase5-A1 · Caddy config = 1 Caddyfile + path_regexp matcher với HUBS_ALLOWLIST env** — Mở rộng `Hub_All/Caddyfile` thêm server block `{$WIKI_PUBLIC_DOMAIN}` (song song MCP block đã có Phase 8.3 M2). Dùng `path_regexp hub_api ^/({$HUBS_ALLOWLIST_REGEX})/api/(.*)$` (env render regex `(yte|duoc|hcns)`). `reverse_proxy http://python-api-{re.hub_api.1}:8080` + `handle_path /{re.hub_api.1}/*` strip prefix. REJECT fragment-based (nhiều file + reload phức tạp). REJECT wildcard `{hub}` raw (unknown hub forward DNS fail Docker network, KHÔNG fail-fast).
- **D-V3-Phase5-A2 · Prefix strip semantic = Caddy strip /{hub} từ path** — `handle_path /<hub>/*` HOẶC `uri strip_prefix /<hub>` (Caddy idiom). Upstream backend hub con nhận `/api/health` (KHÔNG `/yte/api/health`) → M2 router code unchanged + Phase 2 create_app() pattern carry forward. Central `wiki.medinet.vn/api/*` → upstream `python-api-central:8080/api/*` KHÔNG strip. REJECT forward nguyên prefix (phá D-V3-Phase2 KISS 1 codebase deploy).
- **D-V3-Phase5-A3 · FACTOR-04 `make hub-add` extend = Append HUBS_ALLOWLIST + caddy reload** — `scripts/hub-add.sh` thêm step (1) sed-edit `.env` HUBS_ALLOWLIST + (2) `docker compose exec caddy caddy reload --config /etc/caddy/Caddyfile`. Zero-downtime reload không restart container. Smoke checkpoint Task: `curl https://wiki.localhost/<new>/api/health` PASS sau reload. REJECT fragment auto-gen (A1 đã chọn single Caddyfile). REJECT zero-touch (A1 không phải wildcard).
- **D-V3-Phase5-A4 · Domain placeholder dev vs prod = WIKI_PUBLIC_DOMAIN env** — Pattern song song MCP_PUBLIC_DOMAIN (M2 Phase 8.3 carry forward). Caddyfile `{$WIKI_PUBLIC_DOMAIN}` block + Caddy auto-TLS based on domain (`localhost` → self-signed; `wiki.medinet.vn` → ACME Let's Encrypt). docker-compose.yml caddy service add `WIKI_PUBLIC_DOMAIN: ${WIKI_PUBLIC_DOMAIN:-localhost}` env. `.env.example` document `WIKI_PUBLIC_DOMAIN=localhost` (dev) → `wiki.medinet.vn` (prod). REJECT unified PUBLIC_DOMAIN (scope creep). REJECT hardcode (phá env-driven M2 pattern).

### B · Frontend Prefix Detect 1 Build (PROXY-02 + GA-V3-C confirm)

- **D-V3-Phase5-B1 · Prefix detect = pathname.split + KNOWN_HUBS allowlist runtime config** — GA-V3-C khuyến nghị seed CONFIRMED: 1 build dùng chung, runtime detect. Implementation:
  ```typescript
  // frontend/src/services/api.ts (refactor)
  const KNOWN_HUBS = (window as any).__HUB_CONFIG__?.allowlist || ['yte', 'duoc', 'hcns']; // fallback hardcode 3 hub base
  const seg = window.location.pathname.split('/').filter(Boolean)[0];
  const PREFIX: string | null = seg && KNOWN_HUBS.includes(seg) ? seg : null;
  export const API_BASE = PREFIX ? `/${PREFIX}/api` : '/api';
  export const APP_BASE = PREFIX ? `/${PREFIX}` : '';
  export const CURRENT_HUB: string = PREFIX || 'central';
  ```
  KNOWN_HUBS source: (1) `window.__HUB_CONFIG__.allowlist` runtime injected by Caddy (preferred — sync với HUBS_ALLOWLIST env A3); (2) fallback hardcode 3 hub base `['yte','duoc','hcns']` cho dev safety. REJECT build matrix (phá GA-V3-C khuyến nghị + FACTOR-04 rebuild loop). REJECT cookie/header injected (Caddy HTML rewrite phức tạp + tighten coupling).
- **D-V3-Phase5-B2 · Vite base config = base='/' + Caddy serve dùng chung dist/** — `vite.config.ts` giữ default `base: '/'`. Asset path absolute `/assets/foo.js` work cross-prefix. Caddy `file_server` directive + `try_files {path} /index.html` SPA fallback. Cụ thể: `dist/index.html` serve từ root + `/yte/`, `/duoc/`, ... đều fallback cùng file (browser bootstrap React → prefix detect → render đúng). REJECT base='./' relative (fail nested route). REJECT runtime injection `<base href>` (Caddy response rewrite complex unless needed).
- **D-V3-Phase5-B3 · react-router config = BrowserRouter basename={APP_BASE}** — `App.tsx` đổi `<BrowserRouter>` → `<BrowserRouter basename={APP_BASE}>`. Tất cả `<Route path="/dashboard">` ... giữ NGUYÊN — react-router auto prepend basename. Login route `/login` cũng prepend → `<hub>/login` (URL bar) nhưng C1 chốt login phải redirect window.location → central /login (basename không apply vì cross-prefix navigation). WS path (M2 chưa có, defer v4.0 streaming SSE) note placeholder: `${API_BASE}/ws/...` nếu thêm. REJECT hardcode prefix mỗi `<Route>` (manual 13 page change point dễ miss).
- **D-V3-Phase5-B4 · Login redirect = Frontend Login.tsx tự redirect window.location → central /login + ?return=/<hub>** — `Login.tsx` `useEffect()` mount detect prefix → nếu `CURRENT_HUB !== 'central'` → `window.location.replace(\`https://\${window.location.host}/login?return=/\${CURRENT_HUB}\`)`. Central `/login` page (cùng Login.tsx component vì 1 build) parse `?return=` + render branding của hub con (qua `getBranding(returnHub)` D1) + sau auth thành công `window.location.replace(\`/\${returnHub}/dashboard\`)`. Same-origin (wiki.medinet.vn) → localStorage share xuyên subpath. Plan 03-04 backend 307 redirect là FAILSAFE (vẫn LOCKED nhưng FE-driven UX cleaner). REJECT cross-origin POST CORS (overkill same-origin). REJECT pure backend 307 transparent (FE Login.tsx mount ở `/yte/login` sẽ thấy form local — không nhất quán branding).

### C · Login + Auth Flow (PROXY-02 + SSO carry forward Phase 3)

- **D-V3-Phase5-C1 · Central /login UX = Parse ?return + render branding hub con + auto redirect post-login** — Login.tsx (cùng component, 1 build):
  - Mount detect: nếu URL `/login?return=/<hub>` → set state `returnHub = <hub>` + `branding = getBranding(<hub>)` (static glob import D1).
  - Render: logo + title + tagline + themeColor của hub con (Hub Y tế Medinet, Hub Dược Medinet, ...). User THẤY URL `wiki.medinet.vn/login` (root domain — nhất quán entry-point SSO) nhưng branding theo hub.
  - Submit: form POST same-origin `wiki.medinet.vn/api/auth/login` (central → no CORS).
  - Success: `localStorage.setItem('access_token', ...)` (origin `wiki.medinet.vn` root scope) + `window.location.replace('/' + returnHub + '/dashboard')`. Token same-origin với hub con subpath → share đầy đủ.
  - Nếu KHÔNG có `?return=` (user vào trực tiếp wiki.medinet.vn/login): branding mặc định Medinet (central) + redirect post-login về `/dashboard` (central).
- **D-V3-Phase5-C2 · Token storage = localStorage same-origin (M2 carry forward)** — Wiki + all hub con trên `wiki.medinet.vn` cùng origin → localStorage `access_token` + `refresh_token` share xuyên `/yte/`, `/duoc/`, `/`. M2 `AuthContext.tsx` + `api.ts` pattern UNCHANGED. XSS risk (M2 CONCERN carry forward) — defer v4.0 HARD-V4-05 migrate httpOnly cookie. REJECT httpOnly cookie path=/ Phase 5 (scope creep). REJECT sessionStorage (phá UX 2-tab).
- **D-V3-Phase5-C3 · Logout flow = Hub con local logout endpoint (Plan 03-04 LOCKED carry forward)** — `useAuth().logout()` gọi `${API_BASE}/api/auth/logout` (= `/<hub>/api/auth/logout` HOẶC `/api/auth/logout` cho central). Backend hub con handle LOCAL (verify JWT qua JWKSCache + insert Redis blacklist `auth:blacklist:<jti>` — cross-process visible Plan 03-03). Frontend clear localStorage + `window.location.replace(\`\${APP_BASE}/login\`)` (về login page của prefix hiện tại — Login.tsx mount → detect → redirect central). REJECT 307 → central logout (Plan 03-04 LOCKED local — đổi sẽ mâu thuẫn).
- **D-V3-Phase5-C4 · Refresh token flow = Frontend fetch /api/auth/refresh → backend 307 → central (Plan 03-04 carry forward)** — `api.ts::tryRefresh()` giữ NGUYÊN POST `${API_BASE}/api/auth/refresh`. Ở hub con → backend 307 → fetch `redirect: 'follow'` (default) auto-follow → central handle. Verify `redirect: 'follow'` explicit khi build fetch options + ensure POST body preserve qua 307 (RFC 7231 + browser implementation modern). Plan 03-04 D-V3-Phase3-G LOCKED 307 chain — Phase 5 chỉ verify FE compatible. REJECT absolute URL hardcode central (bỏ qua Plan 03-04 LOCKED + tạo path dependency).

### D · Per-hub Login Branding (PROXY-04)

- **D-V3-Phase5-D1 · Branding source = Static FE config + Vite glob import** — Tạo `frontend/src/branding/<hub>/index.ts` mỗi hub export:
  ```typescript
  // frontend/src/branding/yte/index.ts
  export const branding = {
    logo: '/branding/yte/logo.svg',      // public asset path
    title: 'Hub Y tế Medinet',
    tagline: 'Tri thức y tế cho mọi nhân viên',
    themeColor: '#10b981',                // emerald-500
  } as const;
  ```
  Helper `frontend/src/branding/index.ts`:
  ```typescript
  const modules = import.meta.glob<{ branding: BrandingConfig }>('./*/index.ts', { eager: true });
  const registry: Record<string, BrandingConfig> = {};
  for (const path in modules) {
    const hub = path.replace('./', '').replace('/index.ts', '');
    registry[hub] = modules[path].branding;
  }
  export function getBranding(hub: string): BrandingConfig {
    return registry[hub] || registry['central']; // fallback central
  }
  ```
  Initial 4 hub: central, yte, duoc, hcns. FACTOR-04 dynamic hub mới: phải drop file + rebuild FE (acceptable Phase 5 v3.0-b — dynamic branding admin UI defer v4.0). REJECT runtime API fetch (extra request + schema change scope creep). REJECT CSS injection (logo flex kém).
- **D-V3-Phase5-D2 · Branding scope = Login.tsx + Layout.tsx sidebar header** — Chỉ 2 component touch:
  - `Login.tsx`: logo (top-left, `<img src={branding.logo}>`), title (`<h1>{branding.title}</h1>`), tagline (`<p>{branding.tagline}</p>`), themeColor (inline style `style={{ backgroundColor: branding.themeColor }}` cho hero/accent).
  - `Layout.tsx` sidebar header: logo + `${branding.title}` thay "Medinet Wiki" hardcode. Page nội dung (Dashboard, Documents, Search, ...) GIỮ NGUYÊN M2 styling (R-V3-2 mitigation — smoke regression 11 trang KHÔNG break).
  - PROXY-04 satisfied: "logo + title VN khác" + theme color (Login). Full Tailwind theme cascade defer v4.0.
  REJECT theme color cascade toàn bộ component (scope creep + R-V3-2 risk 11 trang regress). REJECT chỉ Login.tsx (Layout sidebar = identifier persistent, user logged-in ở `/yte/` thấy "Medinet Wiki" sẽ nhầm).
- **D-V3-Phase5-D3 · Asset logo storage = frontend/public/branding/<hub>/logo.svg** — Static asset Vite copy `public/branding/<hub>/logo.svg` → `dist/branding/<hub>/logo.svg`. Caddy serve qua `file_server` (same dist/). Initial 4 hub: central (Medinet logo gốc, có thể tạm placeholder), yte, duoc, hcns. SVG vector preferred (size + Retina). Designer edit-friendly (không inline TS). REJECT inline TS (large SVG bundle bloat). REJECT external CDN (extra dep + ops).
- **D-V3-Phase5-D4 · Smoke regression strategy = Manual checklist dev local 4 hub** — Closeout Plan 05-XX Task `checkpoint:human-action`:
  - Setup: `docker compose up` 4 service + Caddy. WIKI_PUBLIC_DOMAIN=localhost.
  - Manual check 4 URL: `https://localhost/login`, `https://localhost/yte/login` (→ redirect central), `https://localhost/duoc/dashboard` (post-login redirect), `https://localhost/hcns/documents`.
  - Verify: Login branding khác per-hub, Layout sidebar title khác, react-router basename work (URL không double prefix), api.ts gọi đúng `/<hub>/api/*` qua Network DevTools.
  - Smoke regression M2 COMPAT-01 11 trang: visit (1) Login (2) Dashboard (3) Documents (4) DocumentIngestion (5) Search/CrossHubSearch (6) HubRegistry [central-only] (7) UserManagement [central-only] (8) APIKeyManagement [central-only] (9) AuditLog [central-only] (10) Profile (11) Settings — verify không broken layout, không 404 asset.
  - User resume signal: `approved` / `regress in <component>` / `skip smoke` (carry forward pattern Plan 03-05/04-07 nếu user pre-resolve defer Phase 7 MIGRATE-05).
  REJECT Playwright e2e (setup overhead inconsistent với v3.0-b precedent). REJECT skip smoke pure (PROXY-04 + R-V3-2 cần human verify UX branding + 11 trang KHÔNG break).

### Claude's Discretion

- Implementation cụ thể Caddy `replace_response` inject `window.__HUB_CONFIG__` (HTML rewrite directive vs backend serve index.html dynamic).
- Caddyfile fragment structure (header global directives placement vs server block scope).
- Login.tsx file structure (single file vs split components: `LoginForm` + `BrandingHeader`).
- KNOWN_HUBS fallback hardcode source (TS const vs build-time inject Vite env vs runtime fetch).
- `<base href>` HTML inclusion (chỉ nếu B2 follow-up cần — không nếu base='/' work clean).
- Caddy `respond` directive cho unknown hub URL (404 page custom vs default 404).
- branding/<hub>/index.ts schema extensibility (favicon, OG meta, manifest.json per-hub) — chỉ logo + title + tagline + themeColor cần thiết Phase 5; mở rộng v4.0.
- Cookie `Path` attribute nếu cần (M2 KHÔNG dùng cookie auth; localStorage same-origin scope).
- Caddy access log format + label hub_name (observability defer Phase 6 SETTINGS hoặc inline).
- HMR dev workflow với Caddy reverse proxy (vite dev server port + Caddy upstream switch dev vs prod).
- Tailwind theme.extend cho `themeColor` (kept inline CSS variable HOẶC Tailwind plugin custom).
- M2 mockData.ts cleanup (KHÔNG cần — D6 expire allow rewrite, nhưng scope tối thiểu).
- WS path (defer v4.0 streaming SSE — chưa cần Phase 5).
- /branding/<hub>/logo.svg fallback nếu file missing (Caddy 404 placeholder vs default Medinet logo).

### Folded Todos

Không có todo nào được fold vào scope Phase 5 — đã review backlog không relevant. Backlog 999.x items đều thuộc v4.0/v4.1 scope.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 5 spec & roadmap (LOCKED constraints)

- `.planning/REQUIREMENTS.md` §PROXY — 4 REQ-ID (PROXY-01..04) success criteria + GA-V3-C confirm 1 build + D-V3-06 D6 expire formally + per-hub branding `frontend/src/branding/<hub>/`.
- `.planning/ROADMAP.md` §Phase 5 — Goal, success criteria 4 SC, discuss-phase gray areas, Risk R-V3-2 (D6 expire frontend rewrite regress), Exit Criteria N/A trực tiếp (E-V3-1 indirect smoke E2E).
- `.planning/PROJECT.md` §Constraints — D-V3-06 D6 expire formally Phase 5; Caddy auto-TLS carry forward M2 Phase 8.3; performance carry forward search hub đơn < 800ms + cross-hub < 1.5s (E-V3-2).
- `.planning/seeds/v3.0-multi-hub-split.md` — Original v3.0 seed (4 GA-V3-A..D + R-V3 risk register + E-V3 exit criteria preview).

### Prior phase context (carry-forward decisions)

- `.planning/phases/02-hub-con-codebase-factor/02-CONTEXT.md` — 9 D-V3-Phase2 LOCKED + FACTOR-04 dynamic hub (Plan 02-05). Phase 5 Caddy + hub-add tích hợp pattern.
- `.planning/phases/02-hub-con-codebase-factor/02-05-PLAN.md` — `scripts/hub-add.sh` 7-step pipeline + docker-compose.override.yml.template + Settings regex `^[a-z][a-z0-9_]{0,15}$` + RESERVED_HUB_NAMES blacklist. Phase 5 extend hub-add.sh với caddy reload + HUBS_ALLOWLIST update.
- `.planning/phases/03-auth-sso-hub-ids-jwt/03-CONTEXT.md` — 8 D-V3-Phase3-A..H LOCKED. Đặc biệt D-V3-Phase3-F (frontend redirect defer Phase 5) + D-V3-Phase3-G (hub con 307 redirect login/refresh) — Phase 5 wire FE.
- `.planning/phases/03-auth-sso-hub-ids-jwt/03-04-PLAN.md` — Auth router 307 redirect implementation + `_sso_redirect` helper + X-SSO-Redirect-Reason headers + Phase 2 integration test split 10 LOCAL + 2 SSO_REDIRECT.
- `.planning/phases/03-auth-sso-hub-ids-jwt/03-04-SUMMARY.md` — Backward incompat operator broadcast TRIPLE cumulative: kid + aud + hub_ids → M2 frontend hardcode same-origin FAIL ở hub con cho tới Phase 5 PROXY-02. Phase 5 FIXES this.
- `.planning/phases/04-cross-hub-data-sync/04-CONTEXT.md` — D-V3-Phase4-D3: hub con strip `/api/search/cross-hub` (FACTOR-02 extend). Phase 5 frontend `CrossHubSearch.tsx` page phải gọi central root `/api/search/cross-hub` (KHÔNG `<hub>/api/search/cross-hub`).

### Codebase entry points (Phase 5 touch)

- `Hub_All/Caddyfile` — Existing MCP block (M2 Phase 8.3); Phase 5 ADD wiki server block + path_regexp matcher.
- `Hub_All/docker-compose.yml` §caddy service (line 271) — `MCP_PUBLIC_DOMAIN` env + ports 80/443 + volume Caddyfile mount; Phase 5 ADD `WIKI_PUBLIC_DOMAIN` env.
- `Hub_All/docker-compose.override.yml.template` (FACTOR-04) — Per-hub python-api service block; Phase 5 KHÔNG cần edit (Caddy serve qua container name `python-api-{hub}` resolve qua Docker DNS).
- `Hub_All/api/scripts/hub-add.sh` (Plan 02-05) — 7-step pipeline; Phase 5 extend step 8 (HUBS_ALLOWLIST env edit) + step 9 (caddy reload).
- `Hub_All/api/scripts/hub-init.sh` (Phase 1) — DB layer create/extension; Phase 5 KHÔNG touch.
- `Hub_All/frontend/src/services/api.ts` — M2 hardcode `${hostname}:8180`; Phase 5 rewrite prefix detect.
- `Hub_All/frontend/src/App.tsx` — `<BrowserRouter>`; Phase 5 add `basename={APP_BASE}`.
- `Hub_All/frontend/src/contexts/AuthContext.tsx` — `localStorage.setItem` + `api.login`/`logout`/`me`; Phase 5 minimal touch (api.ts đã abstract API_BASE).
- `Hub_All/frontend/src/pages/Login.tsx` — Render branding + redirect logic Phase 5 thêm `useEffect` mount detect + window.location.replace nếu non-central.
- `Hub_All/frontend/src/Layout.tsx` — Sidebar header logo + title; Phase 5 đổi `getBranding(CURRENT_HUB).title`.
- `Hub_All/frontend/src/branding/` (NEW) — Tạo mới `<hub>/index.ts` × 4 hub + `index.ts` glob helper.
- `Hub_All/frontend/public/branding/` (NEW) — Tạo mới `<hub>/logo.svg` × 4 hub.
- `Hub_All/frontend/vite.config.ts` — Giữ `base: '/'` (M2 default).
- `Hub_All/CLAUDE.md` §3 (Quy tắc làm việc) — Update D6 EXPIRED ở Phase 5; section 6 v3.0 progress Phase 5 row.

### M2 carry-forward (KHÔNG đổi nhưng cần biết)

- `Hub_All/CLAUDE.md` §1 (D6 constraint cũ) — Frontend KHÔNG sửa trong M2 → EXPIRED Phase 5 v3.0-05.
- `Hub_All/frontend/src/pages/*.tsx` × 13 page — M2 COMPAT-01 11 trang React smoke regression target (R-V3-2 mitigation).
- M2 response envelope `{success, data, error, meta}` — Phase 5 KHÔNG đổi shape API contract.

### External docs (Caddy + Vite + React Router)

- Caddy `path_regexp` matcher: https://caddyserver.com/docs/caddyfile/matchers#path-regexp
- Caddy `handle_path` strip prefix: https://caddyserver.com/docs/caddyfile/directives/handle_path
- Caddy `reverse_proxy` + env var template: https://caddyserver.com/docs/caddyfile/directives/reverse_proxy
- Caddy auto-TLS: https://caddyserver.com/docs/automatic-https
- Vite `base` config: https://vitejs.dev/config/shared-options.html#base
- Vite `import.meta.glob`: https://vitejs.dev/guide/features.html#glob-import
- react-router `BrowserRouter basename`: https://reactrouter.com/en/main/router-components/browser-router
- HTTP 307 Temporary Redirect (preserve POST): RFC 7231 §6.4.7

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- **`Hub_All/Caddyfile` (M2 Phase 8.3 MCP block)** — Caddy auto-TLS pattern `{$MCP_PUBLIC_DOMAIN}` + reverse_proxy MCP. Phase 5 reuse pattern: thêm `{$WIKI_PUBLIC_DOMAIN}` server block parallel.
- **`Hub_All/docker-compose.yml` caddy service (line 271)** — Image `caddy:2-alpine` + ports 80/443 + Caddyfile mount + medinet_caddy_data/config volumes. Phase 5 reuse (KHÔNG đụng service def — chỉ thêm WIKI_PUBLIC_DOMAIN env).
- **`Hub_All/api/scripts/hub-add.sh` Plan 02-05 (FACTOR-04)** — 7-step pipeline + auto-detect port + duplicate detect + sed substitute. Phase 5 extend step 8+9 (HUBS_ALLOWLIST + caddy reload) cùng error handling pattern.
- **`Hub_All/api/scripts/hub-init.sh` Phase 1 Plan 01-05** — DB create/extension idempotent. Phase 5 KHÔNG touch (DB layer separate).
- **`Hub_All/frontend/src/services/api.ts` APIClient class** — Centralized API wrapper với `request()` helper + auth header + retry refresh. Phase 5 reuse class shape, chỉ đổi `baseURL` computation.
- **`Hub_All/frontend/src/contexts/AuthContext.tsx`** — useAuth() hook + login/logout/refreshUser. Phase 5 minimal touch (api.ts đã abstract).
- **`Hub_All/frontend/src/pages/Login.tsx`** — Existing render shell (logo placeholder, form, features list). Phase 5 inject `branding` prop + useEffect mount redirect.
- **`Hub_All/frontend/src/Layout.tsx`** — Sidebar component. Phase 5 đổi title + logo.
- **`docker compose exec caddy caddy reload`** — Caddy support hot reload qua API (zero-downtime). Phase 5 dùng trong hub-add.sh step 9.

### Established Patterns

- **Env-driven domain (M2 Phase 8.3):** `MCP_PUBLIC_DOMAIN` pattern → Phase 5 `WIKI_PUBLIC_DOMAIN` parallel. `.env.example` document cả 2 cho prod vs dev.
- **FACTOR-04 sed-substitute template (Plan 02-05):** `{{HUB}}` + `{{PORT}}` + `{{HUB_UPPER}}` pattern. Phase 5 nếu cần per-hub Caddy fragment (KHÔNG cần — A1 single Caddyfile + env-driven regex).
- **localStorage same-origin auth (M2):** `localStorage.setItem('access_token', ...)` + `'Authorization': Bearer ${token}` header. Phase 5 carry forward — wiki.medinet.vn subpath share origin.
- **JWT 307 redirect chain (Plan 03-04):** Hub con `/api/auth/login` + `/refresh` → 307 → central. Phase 5 verify FE compatible (fetch redirect: 'follow').
- **Cocoindex KHÔNG đụng (Phase 5 frontend-focused):** rag/flow.py + sync/worker.py KHÔNG touch (Phase 4 territory).
- **Response envelope `{success, data, error, meta}`:** M2 contract LOCKED. Phase 5 không đổi shape. Frontend api.ts unwrap pattern carry forward.
- **Atomic commits per task (GSD pattern):** Plan 04 carry forward — mỗi task 1 commit + git log clean.

### Integration Points

- **Caddy → docker-compose network `medinet_net`:** Caddy service expose 80/443, internal route tới `python-api-central:8080` + `python-api-yte:8080` + ... qua Docker DNS. KHÔNG cần publish python-api ports ra host (M2 đã publish 8180-8183 chỉ cho dev direct access — Phase 5 vẫn giữ để debug, sản phẩm prod sẽ hide qua Caddy gateway).
- **Frontend dist/ serve qua Caddy `file_server`:** Phase 5 thêm directive `root * /dist` + `file_server` + `try_files {path} /index.html`. Build pipeline: `npm run build` → `dist/` → Caddy mount volume HOẶC backend serve static (chốt ở plan — Recommended Caddy serve static độc lập).
- **HUBS_ALLOWLIST → Caddy `path_regexp` + Frontend `__HUB_CONFIG__`:** Single source-of-truth `.env` `HUBS_ALLOWLIST=yte,duoc,hcns`. Caddy đọc env → path_regexp; FE đọc qua runtime config inject HOẶC fallback hardcode. `make hub-add` extend cập nhật 1 chỗ.
- **`wiki.medinet.vn/api/search/cross-hub` → central only:** D-V3-Phase4-D3 LOCKED — hub con strip endpoint. Phase 5 frontend `CrossHubSearch.tsx` page (M2 hardcode `/api/search/cross-hub`) phải redirect/proxy về central root khi prefix detect hub con. Implementation: `fetch('/api/search/cross-hub')` (KHÔNG `${API_BASE}` prefix) HOẶC server-side Caddy `handle_path /<hub>/api/search/cross-hub` rewrite tới central (Claude's Discretion plan).
- **Per-hub asset path `/branding/<hub>/logo.svg`:** Caddy serve từ dist/branding/ (Vite copy public/). Frontend img src path khớp.
- **JWT verify chain:** Phase 3 đã LOCKED — Phase 5 KHÔNG touch backend auth code. FE chỉ wire redirect URL + localStorage scope.
- **Phase 1 `_enforce_hub_dsn_match` validator:** Settings boot fail-fast. Phase 5 frontend assume backend DB isolation đã enforce — KHÔNG cần FE-level guard.

</code_context>

<specifics>
## Specific Ideas

- **Branding tone cho 4 hub initial (designer guidance, chốt thêm khi pull request):**
  - Central (Medinet Wiki gốc): indigo `#6366f1` (M2 brand color), title "Medinet Wiki", tagline "Tri thức nội bộ Medinet".
  - yte (Hub Y tế): emerald `#10b981` (green = health), title "Hub Y tế Medinet", tagline "Tri thức y tế cho mọi nhân viên".
  - duoc (Hub Dược): sky/blue `#0ea5e9` (blue = clinical), title "Hub Dược Medinet", tagline "Hướng dẫn dược lâm sàng".
  - hcns (Hub HCNS): amber `#f59e0b` (warm = HR), title "Hub HCNS Medinet", tagline "Chính sách nhân sự Medinet".
- **User UX note:** Khi user vào `wiki.medinet.vn/yte/` lần đầu chưa login → Login.tsx mount → useEffect detect prefix = yte → `window.location.replace('/login?return=/yte')`. URL bar chuyển sang `/login?return=/yte`, branding hiển thị yte (logo emerald + title VN). Sau login thành công → `/yte/dashboard`. Smooth UX.
- **Caddy `handle_path` precedence:** Đặt cross-hub central endpoint route TRƯỚC hub regex để central wins khi path `/api/...` (không có hub prefix). Caddy matcher order matters trong same server block.
- **Per-hub frontend dashboard hiển thị sync_status + drift metric (Phase 4 SYNC-04 fortune):** Out of scope Phase 5 — defer Phase 6 SETTINGS-04 hoặc Phase 7 MIGRATE-05 admin dashboard.
- **JWT iss URL-based:** Plan 03-03 D-V3-Phase3-E LOCKED iss=`"medinet-wiki"` (KHÔNG URL-based). Phase 7 MCP MIGRATE-04 mới split aud. Phase 5 KHÔNG đổi.

</specifics>

<deferred>
## Deferred Ideas

- **Per-hub admin branding UI** — Branding edit từ central admin dashboard (database-driven thay vì static config) — defer v4.0 HARD-V4-XX (FACTOR-04 dynamic admin tool).
- **Tailwind theme cascade toàn bộ component qua CSS variables** — Phase 5 chỉ apply themeColor ở Login + Layout sidebar. Full re-skin defer v4.0.
- **Playwright e2e per-hub smoke automation** — Phase 5 chốt manual checklist (carry forward pattern v3.0-b). Playwright defer v4.0 HARD-V4-04 comprehensive coverage.
- **HMR dev workflow với Caddy reverse proxy** — Claude's Discretion — vite dev server port + Caddy upstream switch dev vs prod. Có thể setup `make dev-proxy` target ở plan nếu cần.
- **Cloudflare Tunnel migration** — defer v4.0+ (Caddy auto-TLS hiện ổn từ Phase 8.3).
- **MCP service subpath `wiki.medinet.vn/mcp`** — Giữ `mcp.medinet.vn` subdomain riêng (Phase 8.3 M2 carry forward) — defer Phase 7 MIGRATE-04 evaluation.
- **httpOnly cookie token storage** — M2 CONCERN XSS carry forward — defer v4.0 HARD-V4-05.
- **WebSocket / streaming `/api/ask` SSE** — defer v4.0 HARD-V4-03 với prefix-aware WS path.
- **Per-hub favicon + manifest.json** — Branding extensibility. Phase 5 chỉ logo + title + tagline + themeColor. Defer v4.0.
- **Hub config Database-driven** — `hub_registry` central table (Phase 6 SETTINGS-04) sẽ là source-of-truth cho HUBS_ALLOWLIST runtime; Phase 5 hiện dùng env (`.env`). Phase 6 sẽ sync.
- **Cross-hub UI redirect logic chốt cụ thể** — Claude's Discretion — `CrossHubSearch.tsx` gọi central root `/api/search/cross-hub` (D-V3-Phase4-D3 LOCKED). Implementation: api.ts có `crossHubSearch` method dùng absolute path `/api/search/cross-hub` KHÔNG prefix HOẶC Caddy server-side rewrite cross-prefix.

### Reviewed Todos (not folded)

Không có — backlog review không match Phase 5 scope.

</deferred>

---

*Phase: 05-reverse-proxy-frontend-subpath*
*Context gathered: 2026-05-22*
*Source: /gsd-discuss-phase 5 --chain (interactive 4 area × 4 sub-question = 16 D-V3-Phase5-A1..D4 LOCKED + Recommended path)*
