# Phase 5: Reverse Proxy + Frontend Subpath — Research

**Researched:** 2026-05-22
**Domain:** Reverse proxy (Caddy 2.x) + Frontend prefix detection (Vite 6 + React Router v7) + SSO login chain + per-hub branding architecture
**Confidence:** HIGH (Caddy + Vite + React Router đều có doc chính thức verify; phần per-hub branding architecture là decision rõ ràng từ CONTEXT.md)
**Response language:** Vietnamese có dấu (technical terms + code + paths giữ English)

---

## Summary

Phase 5 ship 4 deliverable chính: (1) Caddy reverse proxy mở rộng wiki domain với `path_regexp` matcher route `/<hub>/api/*` qua `handle_path` strip prefix → upstream container `python-api-<hub>`; (2) Frontend 1 build prefix-detect runtime (Vite `base='/'` + react-router `BrowserRouter basename={APP_BASE}` + `window.location.pathname.split('/')[1]` detect logic); (3) D-V3-06 D6 expire formally — cho phép frontend rewrite với smoke regression 11 trang M2 COMPAT-01; (4) Per-hub login branding qua `frontend/src/branding/<hub>/` static config + Vite `import.meta.glob({ eager: true })` registry.

Carry-forward Phase 3 (Plan 03-04) backend 307 redirect chain hub con login/refresh → central (RFC 7231 preserve POST + body) đã LOCKED — Phase 5 KHÔNG đụng backend auth router. Frontend redirect là **FE-driven UX cleaner** (D-V3-Phase5-B4) — `Login.tsx` mount detect prefix → `window.location.replace(/login?return=/<hub>)` ở central → render branding hub con + post-login → `/<hub>/dashboard`. Backend 307 vẫn là **failsafe layer** cho `api.ts::tryRefresh()` POST `${API_BASE}/api/auth/refresh` (fetch `redirect: 'follow'` default + browser preserve POST body theo RFC 7231).

Carry-forward Phase 4 (D-V3-Phase4-D3) — hub con strip `/api/search/cross-hub` (FACTOR-02 extend). Phase 5 frontend `CrossHubSearch.tsx` page cần gọi central root `/api/search/cross-hub` (absolute path, KHÔNG `${API_BASE}` prefix khi đang ở hub con) HOẶC Caddy server-side rewrite. Recommended: api.ts `crossHubSearch()` dùng absolute `/api/search/cross-hub` + Caddy không strip (central route winning thứ tự matcher). Trade-off chi tiết Section 7.

**Primary recommendation:** Caddyfile single-file + path_regexp matcher với env `HUBS_ALLOWLIST_REGEX` + `handle_path` strip + 3 server block trong cùng file (MCP block giữ NGUYÊN từ Phase 8.3, ADD `{$WIKI_PUBLIC_DOMAIN}` block parallel). Frontend: api.ts compute `API_BASE` + `APP_BASE` ở module-level (KHÔNG hook/context — chạy 1 lần lúc bundle load) + App.tsx `<BrowserRouter basename={APP_BASE}>` + Login.tsx `useEffect` mount redirect. Branding: static glob registry `frontend/src/branding/<hub>/index.ts` + `frontend/public/branding/<hub>/logo.svg` (Vite copy public/ → dist/).

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| TLS termination + ACME | Caddy (CDN/edge) | — | Carry forward M2 Phase 8.3 — Caddy auto-TLS đã verified |
| URL path routing `/<hub>/api/*` → upstream | Caddy (reverse proxy) | — | Stripping prefix phải làm trước khi tới upstream — KHÔNG đẩy logic này vào FastAPI |
| Static asset + SPA fallback `/<hub>/...` | Caddy (file_server + try_files) | — | Caddy serve `dist/` trực tiếp, KHÔNG đi qua FastAPI (giảm Python overhead) |
| Prefix detect + API base URL compute | Frontend (browser/client) | — | Runtime detect — 1 build dùng chung mọi prefix; KHÔNG cần backend HTML render |
| Login redirect hub con → central | Frontend (Login.tsx mount) | Backend (307 failsafe) | FE-driven UX (D-V3-Phase5-B4) — backend 307 từ Phase 3 vẫn là layer 2 safety |
| Token storage cross-subpath | Frontend (localStorage same-origin) | — | `wiki.medinet.vn` root domain → localStorage share xuyên `/yte/`, `/duoc/`, `/` |
| JWT verify chain | Backend (hub con JWKSCache) | — | KHÔNG đụng Phase 3 carry forward; FE chỉ truyền `Authorization: Bearer` |
| Per-hub branding render | Frontend (Vite glob registry) | Caddy (serve `/branding/<hub>/logo.svg`) | Static config compile-time + asset serve qua Caddy file_server |
| Runtime hub config injection | Backend `/index.html` render OR Caddy `templates` | — | `replace_response` KHÔNG phải standard Caddy directive — chọn 1 trong 2 |
| Hub registry source-of-truth | Env `.env` (Phase 5) → Database (Phase 6 SETTINGS-04) | — | Phase 5 dùng env-driven `HUBS_ALLOWLIST`; defer Phase 6 cho DB-driven |

**Key insight:** Caddy gánh routing + TLS + static; Frontend gánh prefix detect + login UX + branding render. Backend chỉ liên quan **1 chỗ duy nhất** ở Phase 5 — nếu chọn backend HTML render thay vì Caddy templates cho `window.__HUB_CONFIG__` injection (Claude's Discretion D-V3-Phase5 unresolved).

---

## Standard Stack

### Core (carry forward, KHÔNG bump)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Caddy | `caddy:2-alpine` (current latest 2.10+) [VERIFIED: docker-compose.yml line 272] | Reverse proxy + TLS + static file_server + SPA fallback | M2 Phase 8.3 carry forward — đã production verified với auto-TLS Let's Encrypt |
| Vite | `^6.2.0` [VERIFIED: frontend/package.json line 46+55] | Build tool + dev server + import.meta.glob | M2 carry forward — KHÔNG bump (D6 expire chỉ allow code rewrite, KHÔNG version churn) |
| React | `^19.0.0` [VERIFIED: frontend/package.json line 40] | UI framework | M2 carry forward |
| react-router-dom | `^7.14.0` [VERIFIED: frontend/package.json line 43] | Client-side routing với basename support | **v7 thay vì v6** như prompt nói — basename prop semantic giữ nguyên backward compat từ v6 [CITED: reactrouter.com/api/declarative-routers/BrowserRouter] |
| TypeScript | `~5.8.2` [VERIFIED: frontend/package.json line 54] | Type safety cho prefix detect + branding registry | M2 carry forward |
| Tailwind v4 | `^4.1.14` [VERIFIED: frontend/package.json line 52] | Styling — theme color via inline style (D-V3-Phase5-D2) thay vì Tailwind theme cascade (defer v4.0) | M2 carry forward |

### Supporting (KHÔNG cần thêm dep mới)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `lucide-react` | `^0.546.0` | Icon system (FE component giữ nguyên M2 — KHÔNG đụng) | Carry forward |
| `motion` | `^12.23.24` | Animation (Login.tsx + Layout dùng) | Carry forward |
| `clsx` + `tailwind-merge` | (carry forward) | Conditional className helper | Carry forward |

### Alternatives Considered (REJECTED)

| Instead of | Could Use | Tradeoff | Rationale REJECT |
|------------|-----------|----------|------------------|
| Caddy single Caddyfile + env regex | Caddy fragments per-hub + `import` directive | Fragments scale với nhiều hub | A1 LOCKED — Single Caddyfile + env regex là D-V3-Phase5-A1 LOCKED (RECOMMENDED path); fragment auto-gen phức tạp ops |
| Vite 1 build runtime detect | Vite per-hub build matrix (`VITE_HUB_NAME=yte npm run build` × 4) | Build matrix cho phép build-time inject ENV | GA-V3-C khuyến nghị seed CONFIRMED + D-V3-Phase5-B1 LOCKED — 1 build dùng chung mọi prefix; FACTOR-04 dynamic hub mới KHÔNG cần rebuild |
| react-router basename={APP_BASE} | Hardcode prefix mỗi `<Route path="/<hub>/dashboard">` | Hardcode explicit | D-V3-Phase5-B3 LOCKED — manual 13 page change point dễ miss; basename auto-prepend reliable |
| FE-driven login redirect | Pure backend 307 transparent (browser auto-follow) | Backend redirect simpler | D-V3-Phase5-B4 LOCKED — pure backend 307 sẽ thấy form local `/yte/login` khi mount Login.tsx, branding KHÔNG nhất quán; backend 307 vẫn giữ failsafe cho `tryRefresh()` |
| Static glob branding registry | Database-driven branding (admin UI edit) | Dynamic branding | D-V3-Phase5-D1 LOCKED — static config + Vite glob acceptable Phase 5 (4 hub initial); dynamic admin UI defer v4.0 HARD-V4-XX |
| `frontend/public/branding/<hub>/logo.svg` | Inline TS SVG (`logo.tsx` export JSX) | Inline = tree-shakeable | D-V3-Phase5-D3 LOCKED — large SVG bundle bloat; designer edit-friendly external file |
| Playwright E2E smoke 4 hub | Manual checklist dev local 4 hub | Playwright automate | D-V3-Phase5-D4 LOCKED — setup overhead inconsistent với v3.0-b precedent (Plan 03-05 + 04-07 pre-resolved SKIP); manual carry forward |

**Installation:** KHÔNG cần npm install package mới — toàn bộ Phase 5 dùng dep có sẵn (`react-router-dom@7` + `vite@6` + tailwind v4 + motion). KHÔNG cần caddy plugin bên thứ 3 (giải pháp `window.__HUB_CONFIG__` injection chọn backend HTML render → 0 caddy module).

**Version verification:**
- Caddy 2-alpine image: `docker compose pull caddy` sẽ pull latest 2.x (2.10+ as of 2026 — verify `caddy version` post-up). [VERIFIED: caddyserver.com docs reflect 2.x stable APIs]
- `npm view react-router-dom version` → confirm matches `^7.14.0` đã có. Phase 5 KHÔNG bump.

---

## Architecture Patterns

### System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Browser (https://wiki.medinet.vn/yte/dashboard)                            │
│                                                                             │
│  1. URL parse → window.location.pathname.split('/')[1] = "yte"             │
│  2. api.ts module load → PREFIX="yte" → API_BASE="/yte/api" + APP_BASE="/yte" │
│  3. App.tsx <BrowserRouter basename="/yte"> → Routes prepend "/yte"        │
│  4. Login flow: Login.tsx useEffect mount → if PREFIX !== central →        │
│     window.location.replace('/login?return=/yte') (cùng domain)            │
│  5. Branding: getBranding('yte') → static glob registry → render logo + title │
└─────────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼ HTTPS request
┌─────────────────────────────────────────────────────────────────────────────┐
│ Caddy (port 443) — {$WIKI_PUBLIC_DOMAIN} server block                       │
│                                                                             │
│  Routing decision (handle blocks, ordered by matcher specificity):         │
│                                                                             │
│  ┌─ @hub_api path_regexp ^/(yte|duoc|hcns)/api/(.*)$  ─┐                   │
│  │   handle @hub_api {                                  │                   │
│  │     handle_path /yte/* { reverse_proxy python-api-yte:8080 }            │
│  │   }                                                  │                   │
│  └────────────────────────────────────────────────────┘                   │
│                                                                             │
│  ┌─ /api/*  ────────────────────────────────────────────┐                  │
│  │   handle /api/* {                                     │                  │
│  │     reverse_proxy python-api-central:8080  (no strip) │                  │
│  │   }                                                   │                  │
│  └────────────────────────────────────────────────────┘                  │
│                                                                             │
│  ┌─ /branding/<hub>/logo.svg + /assets/* + /*  ─────────┐                  │
│  │   handle {                                            │                  │
│  │     root * /srv/wiki/dist                             │                  │
│  │     try_files {path} /index.html                      │                  │
│  │     file_server                                       │                  │
│  │   }                                                   │                  │
│  └────────────────────────────────────────────────────┘                  │
└─────────────────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼────────────────────┐
              ▼               ▼                    ▼
    ┌────────────────┐ ┌──────────────────┐ ┌─────────────────┐
    │ python-api-yte │ │ python-api-central│ │ Static dist/    │
    │ :8080 receives │ │ :8080 receives    │ │ index.html +    │
    │ /api/dashboard │ │ /api/auth/login   │ │ /assets/*.js,css│
    │ (prefix stripped)│ │ + cross-hub      │ │ + /branding/*  │
    │ HUB_NAME=yte   │ │ HUB_NAME=central  │ │                 │
    └────────────────┘ └──────────────────┘ └─────────────────┘
              │
              ▼ outbox + worker → central_sync_pool
    (Phase 4 SYNC carry forward — KHÔNG đụng Phase 5)
```

**Data flow giải thích:**
1. **Entry:** Browser request HTTPS tới `wiki.medinet.vn` (port 443).
2. **TLS terminate:** Caddy validate ACME cert (auto-renew Let's Encrypt prod / self-signed localhost dev) — carry forward M2 Phase 8.3 pattern.
3. **Match phase 1 — hub API:** `@hub_api path_regexp ^/(yte|duoc|hcns)/api/(.*)$` — Caddy regex engine capture group 1 = `<hub>`, group 2 = path remainder. Hub `yte`/`duoc`/`hcns` render từ env `HUBS_ALLOWLIST_REGEX`. Khớp → `handle_path /yte/*` strip prefix → forward đến `python-api-yte:8080/api/...` (Docker DNS resolve container name).
4. **Match phase 2 — central API:** Nếu KHÔNG match hub regex + path bắt đầu `/api/*` → forward NGUYÊN tới `python-api-central:8080/api/...` (KHÔNG strip).
5. **Match phase 3 — static:** Nếu KHÔNG match API → Caddy `file_server` serve từ `/srv/wiki/dist` (volume mount `frontend/dist/`). `try_files {path} /index.html` SPA fallback — `/yte/dashboard`, `/yte/documents`, `/login`, `/duoc/search` đều fallback `/index.html` browser load React → JS bundle bootstrap → prefix detect → render đúng route.
6. **Frontend bootstrap:** Browser load `/index.html` → load `/assets/*.js` (absolute path từ `base='/'`) → React mount → api.ts compute PREFIX/API_BASE/APP_BASE → BrowserRouter render → Layout/Login conditional dispatch.

### Recommended Project Structure (Phase 5 delta)

```
Hub_All/
├── Caddyfile                         # EDIT — Add {$WIKI_PUBLIC_DOMAIN} server block parallel với MCP block
├── docker-compose.yml                # EDIT — Add WIKI_PUBLIC_DOMAIN env + frontend dist volume mount caddy service
├── docker-compose.override.yml.template  # EDIT — Inherit CADDY_RELOAD_TOKEN env nếu cần (operator-local)
├── .env.example                      # EDIT — Document WIKI_PUBLIC_DOMAIN + HUBS_ALLOWLIST + HUBS_ALLOWLIST_REGEX
├── api/scripts/hub-add.sh            # EDIT — Add step 8 (HUBS_ALLOWLIST sed update) + step 9 (caddy reload)
├── api/app/main.py                   # EDIT (chỉ nếu chọn backend HTML render) — GET / serve index.html với <script>window.__HUB_CONFIG__</script>
├── frontend/
│   ├── src/
│   │   ├── services/api.ts           # EDIT — Replace hardcode `${hostname}:8180` với PREFIX detect + API_BASE
│   │   ├── App.tsx                   # EDIT — Add basename={APP_BASE} cho <BrowserRouter>
│   │   ├── Layout.tsx                # EDIT — Replace hardcode "Medinet Wiki" với getBranding(CURRENT_HUB).title
│   │   ├── pages/Login.tsx           # EDIT — Add useEffect mount redirect + render branding hub con
│   │   ├── pages/CrossHubSearch.tsx  # EDIT — Call api.crossHubSearch() (absolute path; sẽ refactor api.ts)
│   │   ├── contexts/AuthContext.tsx  # EDIT minimal — api.login() vẫn dùng API_BASE; localStorage giữ nguyên
│   │   └── branding/                 # NEW directory
│   │       ├── index.ts              # NEW — Vite glob registry + getBranding() helper + BrandingConfig type
│   │       ├── central/index.ts      # NEW — Medinet gốc (indigo)
│   │       ├── yte/index.ts          # NEW — Hub Y tế (emerald)
│   │       ├── duoc/index.ts         # NEW — Hub Dược (sky blue)
│   │       └── hcns/index.ts         # NEW — Hub HCNS (amber)
│   ├── public/
│   │   └── branding/                 # NEW directory (Vite copy public/ → dist/)
│   │       ├── central/logo.svg      # NEW — placeholder M2 indigo
│   │       ├── yte/logo.svg          # NEW
│   │       ├── duoc/logo.svg         # NEW
│   │       └── hcns/logo.svg         # NEW
│   ├── vite.config.ts                # NO EDIT — giữ base='/' default (D-V3-Phase5-B2 LOCKED)
│   └── package.json                  # NO EDIT — dùng dep có sẵn
├── CLAUDE.md                         # EDIT — §3 D6 expire formally + §6 Phase 5 v3.0 progress row
└── .planning/
    ├── STATE.md                      # EDIT — frontmatter Phase 5 + Results Summary
    ├── REQUIREMENTS.md               # EDIT — PROXY-01..04 mark [x]
    ├── ROADMAP.md                    # EDIT — Phase 5 status DONE
    └── README.md (Hub_All/)          # EDIT — Section mới "Reverse Proxy Subpath Deploy Notes (Phase 5 v3.0)"
```

### Pattern 1: Caddy `path_regexp` + `handle_path` strip prefix (PROXY-01)

**What:** Match dynamic hub prefix qua regex capture group + strip prefix trước khi forward upstream.
**When to use:** Multi-tenant subpath routing với hub list known at deploy time (env-driven).

**Example:**
```caddyfile
# Caddyfile — Phase 5 ADD wiki block (MCP block giữ nguyên Phase 8.3)
# Source: https://caddyserver.com/docs/caddyfile/matchers#path-regexp
#         https://caddyserver.com/docs/caddyfile/directives/handle_path
#         https://caddyserver.com/docs/caddyfile/concepts (env var substitution)

# Existing MCP block (UNCHANGED — Phase 8.3 carry forward)
{$MCP_PUBLIC_DOMAIN} {
    reverse_proxy medinet-mcp:8190
}

# NEW — Wiki block với multi-hub subpath routing
{$WIKI_PUBLIC_DOMAIN:localhost} {
    # ─── Match 1: hub API ────────────────────────────────────────
    # HUBS_ALLOWLIST_REGEX="yte|duoc|hcns" (set qua .env)
    # Regex capture group 1 = hub name, group 2 = path remainder
    @hub_api path_regexp hub_api ^/({$HUBS_ALLOWLIST_REGEX})/api/(.*)$
    handle @hub_api {
        # handle_path strips matched prefix (e.g. "/yte") trước khi forward
        # Upstream nhận /api/health (KHÔNG /yte/api/health) — M2 router code unchanged
        # Pitfall: handle_path strip dùng glob pattern (/yte/*), không phải regex group
        # → cần 1 handle_path block PER HUB (manual list) HOẶC dùng route + uri strip_prefix với placeholder
        # Recommended: route + uri strip_prefix với regex capture (D-V3-Phase5-A2 implementation detail)
        route {
            uri strip_prefix /{re.hub_api.1}
            reverse_proxy http://python-api-{re.hub_api.1}:8080
        }
    }

    # ─── Match 2: central API (no strip) ─────────────────────────
    # Important: ordering KHÔNG matter cho handle (Caddy sort by matcher specificity)
    # nhưng `/api/*` glob matcher specific hơn root → tự nhiên handle TRƯỚC root fallback
    handle /api/* {
        reverse_proxy http://python-api-central:8080
    }

    # ─── Match 3: cross-hub search (carry forward Phase 4 D-V3-Phase4-D3) ─
    # Hub con KHÔNG mount /api/search/cross-hub — chỉ central handle
    # Frontend gọi absolute /api/search/cross-hub (KHÔNG ${API_BASE}) → match Match 2 ở Caddy
    # (Implementation alternative: Caddy server-side rewrite /<hub>/api/search/cross-hub → /api/search/cross-hub central)
    # Recommended FE-side gọi absolute path → KHÔNG cần Caddy rewrite phụ

    # ─── Match 4: static SPA (catch-all fallback) ────────────────
    handle {
        root * /srv/wiki/dist
        try_files {path} /index.html
        file_server
    }

    # ─── Optional: log structured ────────────────────────────────
    log {
        output stdout
        format json
    }
}
```

**Pitfall quan trọng:** `handle_path` strip dùng glob pattern (`/yte/*`), KHÔNG accept regex capture group placeholder trong path matcher của `handle_path` directive trực tiếp. **Fix:** Dùng `route` block trong `handle @hub_api` với `uri strip_prefix /{re.hub_api.1}` (placeholder support trong directive args theo Caddy convention). [CITED: caddyserver.com/docs/caddyfile/directives/handle_path comparison với uri strip_prefix] [ASSUMED: chính xác cú pháp `uri strip_prefix /{re.hub_api.1}` cần verify ở plan execution — fallback nếu fail: dùng 1 `handle_path /<hub>/*` block per hub manual list]

**Verification approach ở plan:** Plan execution Wave 1 phải `docker compose exec caddy caddy validate --config /etc/caddy/Caddyfile` + `curl localhost/yte/api/health` smoke test. Nếu placeholder fail → fallback per-hub explicit block (`handle_path /yte/* { reverse_proxy http://python-api-yte:8080 }` × N hub) — generated từ `HUBS_ALLOWLIST` env qua bash render OR Caddy `import` directive với fragment per-hub. Khuyến nghị test cả 2 approach trong Wave 1.

### Pattern 2: Frontend prefix detection module-level (PROXY-02)

**What:** Compute API_BASE + APP_BASE 1 lần khi api.ts module load, expose const cho mọi component import.
**When to use:** 1-build-many-deploy SPA với runtime URL parsing.

**Example:**
```typescript
// frontend/src/services/api.ts — Phase 5 refactor (đầu file, thay 3 dòng đầu M2)
// Source: D-V3-Phase5-B1 LOCKED implementation
// Pitfall: COMPUTE NGAY MODULE LOAD — KHÔNG dùng useState/useEffect (would race với initial render)

// Runtime hub config — Caddy/backend inject via <script>window.__HUB_CONFIG__</script>
// HOẶC fallback hardcode 3 hub gốc (Phase 5 initial). Phase 6 SETTINGS-04 sync DB-driven.
interface HubConfig {
  allowlist: readonly string[];
  current?: string; // optional — chỉ có khi backend render dynamic
}

const HUB_CONFIG: HubConfig =
  (window as unknown as { __HUB_CONFIG__?: HubConfig }).__HUB_CONFIG__ ?? {
    allowlist: ['yte', 'duoc', 'hcns'] as const, // fallback hardcode initial
  };

const KNOWN_HUBS: readonly string[] = HUB_CONFIG.allowlist;

// Detect prefix từ URL pathname segment đầu tiên
const firstSegment: string | undefined = window.location.pathname
  .split('/')
  .filter(Boolean)[0];

export const PREFIX: string | null =
  firstSegment && KNOWN_HUBS.includes(firstSegment) ? firstSegment : null;

export const API_BASE: string = PREFIX ? `/${PREFIX}/api` : '/api';
export const APP_BASE: string = PREFIX ? `/${PREFIX}` : '';
export const CURRENT_HUB: string = PREFIX ?? 'central';

// API_URL thay vì M2 hardcode `${hostname}:8180` — relative path qua Caddy
const API_URL = API_BASE; // KHÔNG cần absolute URL (Caddy same-origin gateway)

// ... rest of APIClient class giữ nguyên M2 — thay constructor argument
// export const api = new APIClient(API_URL);
```

**Side effects cần biết:**
- `window.__HUB_CONFIG__` chỉ available SAU khi `<script>` inject chạy. Vite asset script tag dùng `type="module"` (defer by default) → execute SAU inline `<script>` trong `<head>`. Cần verify ordering trong injected index.html.
- Fallback hardcode `['yte','duoc','hcns']` quan trọng cho dev (browser cache stale index.html không có inject).
- `as unknown as { __HUB_CONFIG__?: HubConfig }` cast tránh TypeScript strict `any` violation — phù hợp mypy-like enforcement của tsconfig strict.

### Pattern 3: React Router v7 BrowserRouter basename (PROXY-02)

**What:** Pass APP_BASE vào `<BrowserRouter basename={APP_BASE}>` → react-router auto-prepend basename cho mọi `<Route path>` + `<Link to>` + `useNavigate()`.

**Example:**
```typescript
// frontend/src/App.tsx — Phase 5 EDIT
// Source: https://reactrouter.com/api/declarative-routers/BrowserRouter
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { APP_BASE } from './services/api';
// ... other imports unchanged

export default function App() {
  return (
    <BrowserRouter basename={APP_BASE}>
      {/* basename='' (central) hoặc basename='/yte' (hub con) */}
      <AuthProvider>
        <Routes>
          {/* Routes giữ NGUYÊN path absolute — react-router auto prepend basename */}
          <Route path="/login" element={<Login />} />
          <Route path="/" element={<ProtectedRoute><Layout /></ProtectedRoute>}>
            <Route index element={<Dashboard />} />
            <Route path="search" element={<CrossHubSearch />} />
            <Route path="documents" element={<DocumentIngestion />} />
            {/* ... rest unchanged */}
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
```

**Semantic xác nhận** [CITED: reactrouter.com/api/declarative-routers/BrowserRouter]:
- `basename` prop type `string` — "Prefixes all route paths and Link hrefs"
- `<Route path="/dashboard">` với `basename="/yte"` → URL bar hiển thị `/yte/dashboard`
- `<Link to="/documents">` với `basename="/yte"` → renders href `/yte/documents`
- `useNavigate()('/profile')` → push history `/yte/profile`

**Pitfall quirk:** `<Navigate to="/login" replace />` (ProtectedRoute fallback) với basename="/yte" → redirect `/yte/login` (đúng). KHÔNG cần đổi component. NHƯNG `/yte/login` không match component Login mount logic — Login.tsx phải redirect ngoài react-router scope (window.location → central root) → react-router basename KHÔNG cross-prefix navigation (đó là window.location job).

### Pattern 4: Login redirect SSO chain (PROXY-02 + Phase 3 carry forward)

**What:** Login.tsx mount detect prefix; non-central → `window.location.replace` tới central với `?return=/<hub>`.

**Example:**
```typescript
// frontend/src/pages/Login.tsx — Phase 5 EDIT
// Add ngay sau imports (trước existing FEATURES const)
import { useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { CURRENT_HUB, APP_BASE } from '../services/api';
import { getBranding, type BrandingConfig } from '../branding';

const LoginPage = () => {
  // ... existing state hooks
  const [searchParams] = useSearchParams();
  const returnHub = searchParams.get('return')?.replace(/^\//, '') || null;

  // Hub con redirect tới central /login?return=/<hub> — chạy 1 lần mount
  useEffect(() => {
    if (CURRENT_HUB !== 'central') {
      const target = `${window.location.origin}/login?return=/${CURRENT_HUB}`;
      window.location.replace(target);
      // KHÔNG return JSX — page sẽ unmount sau replace
    }
  }, []); // empty deps — chỉ run once mount

  // Branding selection: central với ?return=/<hub> → hub con branding; central no return → Medinet gốc
  const branding: BrandingConfig = getBranding(returnHub || 'central');

  // Submit handler: login success → redirect về /<returnHub>/dashboard (cross-prefix qua window.location)
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    // ... existing validation
    const result = await login(email, password);
    if (result.success) {
      const dest = returnHub ? `/${returnHub}/dashboard` : '/';
      window.location.replace(dest);
      // window.location.replace cross-prefix (basename change) — KHÔNG dùng navigate() từ react-router
    }
    // ... existing error handling
  };

  // Render: thay placeholder M2 indigo/Medinet với branding.logo + branding.title + branding.themeColor inline style
  return (
    <div style={{ background: `linear-gradient(135deg, ${branding.themeColor} 0%, ...)` }}>
      <img src={branding.logo} alt={branding.title} />
      <h1>{branding.title}</h1>
      <p>{branding.tagline}</p>
      {/* ... rest of form */}
    </div>
  );
};
```

**Failsafe layer (Phase 3 Plan 03-04 carry forward):** Nếu user direct nav `/yte/api/auth/login` (browser typed URL hoặc legacy bookmark) → backend `python-api-yte` trả 307 Location: `https://wiki.medinet.vn/api/auth/login` (RFC 7231 preserve POST + body). Browser fetch `redirect: 'follow'` (default) → auto retry POST tới central. **Verify** [CITED: developer.mozilla.org/en-US/docs/Web/HTTP/Status/307]: "The method and the body of the original request are reused to perform the redirected request" — POST body bytes preserve.

### Pattern 5: Per-hub branding via Vite import.meta.glob eager (PROXY-04)

**What:** Static config per-hub + glob registry helper `getBranding(hub)`.

**Example:**
```typescript
// frontend/src/branding/index.ts — NEW Phase 5
// Source: https://vite.dev/guide/features.html#glob-import
import type { BrandingConfig } from './types';
// HOẶC inline type — quyết định ở plan (claude's discretion D-V3-Phase5)

export interface BrandingConfig {
  readonly logo: string;        // public asset path, vd '/branding/yte/logo.svg'
  readonly title: string;       // VN hub title, vd 'Hub Y tế Medinet'
  readonly tagline: string;     // VN subtitle
  readonly themeColor: string;  // hex, vd '#10b981'
}

// Vite eager glob — compile-time scan + bundle tất cả branding modules
// Output: { './central/index.ts': { branding: {...} }, './yte/index.ts': {...}, ... }
const modules = import.meta.glob<{ branding: BrandingConfig }>('./*/index.ts', {
  eager: true,
});

// Build registry keyed by hub name (strip './' và '/index.ts')
const registry: Record<string, BrandingConfig> = {};
for (const path in modules) {
  // path = './yte/index.ts' → hub = 'yte'
  const match = path.match(/^\.\/([a-z][a-z0-9_]*)\/index\.ts$/);
  if (match) {
    registry[match[1]] = modules[path].branding;
  }
}

const FALLBACK: BrandingConfig = registry['central'] ?? {
  logo: '/branding/central/logo.svg',
  title: 'Medinet Wiki',
  tagline: 'Tri thức nội bộ Medinet',
  themeColor: '#6366f1',
};

export function getBranding(hub: string): BrandingConfig {
  return registry[hub] ?? FALLBACK;
}
```

```typescript
// frontend/src/branding/yte/index.ts — NEW
export const branding = {
  logo: '/branding/yte/logo.svg',
  title: 'Hub Y tế Medinet',
  tagline: 'Tri thức y tế cho mọi nhân viên',
  themeColor: '#10b981', // emerald-500
} as const;
```

**Verify eager mode behavior** [CITED: vite.dev/guide/features.html#glob-import]: `eager: true` transform glob thành static imports `import * as __vite_glob_0_0 from './central/index.ts'` etc — module load synchronously at bundle parse time → KHÔNG có lazy chunk + KHÔNG có async penalty.

**Anti-pattern WARN:**
- KHÔNG dùng `default` export trong `branding/<hub>/index.ts` nếu glob template không chỉ định `import: 'default'` — confusing semantics. Stick với named export `branding`.
- KHÔNG nest sub-folder (`branding/yte/main/index.ts`) — glob `./*/index.ts` chỉ depth-1; thêm depth sẽ cần `./**/index.ts` + key parse phức tạp hơn.
- KHÔNG inline SVG content trong `branding/<hub>/index.ts` (bundle bloat) — đường dẫn `/branding/<hub>/logo.svg` reference public asset Caddy serve.

### Anti-Patterns to Avoid

- **HARDCODE upstream container name trong Caddyfile:** Plan execution sẽ tempting viết `reverse_proxy http://python-api-yte:8080` × 3 hub. KHÔNG SCALE FACTOR-04. Dùng placeholder `http://python-api-{re.hub_api.1}:8080`. [ASSUMED: cú pháp placeholder trong upstream address — verify ở plan; nếu Caddy reject placeholder upstream port phải static (theo doc note "When using placeholders in non-URL form addresses, a port must be included"), workaround: static port `:8080` + container name dynamic.]
- **DÙNG <base href="/<hub>/"> trong index.html dynamic:** Tempting để asset path relative work cross-prefix. NHƯNG Vite asset path đã absolute từ `base='/'` config → `<base href>` thừa + có thể break SPA routing. STICK với base='/' (D-V3-Phase5-B2 LOCKED).
- **DÙNG sessionStorage cho access_token:** Phá UX multi-tab. Stick localStorage same-origin (D-V3-Phase5-C2 LOCKED). XSS concern accept M2 carry forward — defer v4.0.
- **REDIRECT login bằng react-router `<Navigate>`:** Cross-prefix navigation cần `window.location.replace` để force full page reload + reset basename. `<Navigate>` chỉ scope basename hiện tại (`/yte/login` → `/yte/dashboard` OK; `/yte/login` → `/login` central FAIL nếu basename='/yte').
- **PARSE HUBS_ALLOWLIST từ env trong frontend at runtime:** Frontend không có process.env runtime access (Vite inject build-time qua `import.meta.env.VITE_*`). Phải qua `window.__HUB_CONFIG__` injected by Caddy/backend HOẶC fallback hardcode.
- **HARDCODE `https://wiki.medinet.vn/login` cross-origin trong Login.tsx:** Phá dev (localhost). Dùng `${window.location.origin}/login` same-origin.
- **SKIP smoke regression 11 trang M2 COMPAT-01:** R-V3-2 HIGH risk frontend rewrite regress. D-V3-Phase5-D4 chốt MANUAL checklist là minimum — KHÔNG skip pure.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| TLS cert provisioning | Custom ACME client / certbot cron | Caddy auto-TLS [CITED: caddyserver.com/docs/automatic-https] | Caddy 2.x ACME implementation production-tested, M2 Phase 8.3 verified |
| Reverse proxy with prefix strip | Nginx `rewrite` regex manual | Caddy `handle_path` + `uri strip_prefix` | Caddy syntax đơn giản hơn nginx; M2 carry forward stack |
| Hub allowlist regex validation | Custom JS regex builder | Env `HUBS_ALLOWLIST_REGEX="yte|duoc|hcns"` rendered by hub-add.sh sed | Single source-of-truth env-driven; Plan 02-05 FACTOR-04 pattern |
| Glob import branding modules | Manual `import central from './central'` × N | Vite `import.meta.glob('./*/index.ts', { eager: true })` | Auto-scan compile-time + tree-shakeable; built-in Vite feature |
| Login form post-redirect cross-prefix | History API `pushState` manual | `window.location.replace()` | pushState scope basename; replace cross-prefix force full reload reset basename |
| 307 POST body preservation | Custom fetch retry with re-send | Browser native `redirect: 'follow'` (default) [CITED: MDN HTTP Status 307] | Browser implementation RFC 7231 compliant; do NOT manually intercept |
| Zero-downtime config reload | Caddy container restart | `docker compose exec caddy caddy reload --config /etc/caddy/Caddyfile` [CITED: caddyserver.com/docs/api POST /load] | Caddy admin API atomic swap + rollback on validate fail |
| SPA fallback `/<hub>/dashboard` → index.html | Custom Caddy middleware | `try_files {path} /index.html` + `file_server` | Standard Caddy directive; no module needed |
| Hub config runtime injection | Custom JS download config endpoint | Backend `/index.html` render OR Caddy `templates` directive | Inline `<script>window.__HUB_CONFIG__</script>` simplest; `replace_response` is NOT standard Caddy directive [VERIFIED: caddyserver.com/docs/caddyfile/directives] |
| Token storage cross-subpath | Custom cookie domain logic | localStorage same-origin (`wiki.medinet.vn` root scope) | M2 carry forward; localStorage share xuyên subpath default |
| Per-hub theme cascade | Custom Tailwind plugin runtime swap | Inline `style={{ backgroundColor: branding.themeColor }}` | D-V3-Phase5-D2 scope minimal (Login + Layout); full theme defer v4.0 |

**Key insight:** Phase 5 hoàn toàn DỰA VÀO Caddy + Vite + react-router built-in features — KHÔNG ship custom proxy logic / custom router / custom build plugin. Single source-of-truth là `.env HUBS_ALLOWLIST` + `frontend/src/branding/` directory + `Caddyfile` 3 server block.

---

## Runtime State Inventory

Phase 5 KHÔNG phải rename/refactor migration phase — Phase 5 ship FE rewrite (D6 expire) + Caddy config addition (new block). Tuy nhiên có một số runtime state cần verify:

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | **None** — Phase 5 không touch DB schema / Redis key / sync_outbox state | — |
| Live service config | **Caddy admin API** (port 2019 internal — KHÔNG expose ra host) reload mechanism. M2 Phase 8.3 đã có MCP block → Phase 5 ADD wiki block; reload preserve cert + connection (atomic swap [CITED: caddyserver.com/docs/api]). | `docker compose exec caddy caddy reload --config /etc/caddy/Caddyfile` sau ship Caddyfile edit |
| OS-registered state | **None** — KHÔNG có Windows Task Scheduler / launchd / systemd unit liên quan Phase 5 | — |
| Secrets/env vars | `WIKI_PUBLIC_DOMAIN` (mới Phase 5) + `HUBS_ALLOWLIST` + `HUBS_ALLOWLIST_REGEX` (mới Phase 5) — đều ADD vào `.env.example`. KHÔNG rename existing env. | Document trong `.env.example`; operator broadcast |
| Build artifacts | **frontend/dist/** — Phase 5 sẽ rebuild với code mới (api.ts + App.tsx + Login.tsx + Layout.tsx + branding/). `docker compose build python-api-*` KHÔNG affect frontend build pipeline (frontend build outside Docker — TBD ở plan). Caddy volume mount `dist/` từ host filesystem hoặc baked vào caddy image custom — chốt ở plan (Claude's Discretion). | `cd frontend && npm run build` trước hoặc cùng plan smoke checkpoint |

**Smoke compose precedent từ Plan 03-05 + 04-07:** v3.0-b SKIP pre-resolved Phase 7 MIGRATE-05 cho runtime full E2E. Phase 5 D4 chốt manual checklist 4 hub × 11 trang — KHÔNG defer toàn bộ vì PROXY-04 + R-V3-2 cần human verify UX branding.

---

## Common Pitfalls

### Pitfall 1: Caddy regex placeholder trong upstream address không support port placeholder

**What goes wrong:** Caddy reject `reverse_proxy http://python-api-{re.hub_api.1}:{re.hub_api.2}` nếu placeholder thay vào port part.
**Why it happens:** [CITED: caddyserver.com/docs/caddyfile/directives/reverse_proxy] "Upstream addresses cannot contain paths or query strings" và "a port must be included (either by the placeholder replacement, or as a static suffix to the address)".
**How to avoid:** Giữ port `:8080` STATIC trong upstream address: `reverse_proxy http://python-api-{re.hub_api.1}:8080` (chỉ container name part dynamic). Verify ở Wave 1 smoke test.
**Warning signs:** Caddy logs "invalid upstream" hoặc config validation fail at reload.

### Pitfall 2: Vite asset absolute path `/assets/foo.js` work cross-prefix nhưng nested-route refresh fail nếu Caddy try_files thiếu

**What goes wrong:** User refresh `/yte/dashboard` → Caddy file_server lookup `/yte/dashboard` file → 404 (file không tồn tại). KHÔNG fallback `/index.html` → blank page.
**Why it happens:** `file_server` default trả 404 cho missing path; cần `try_files {path} /index.html` explicit để fallback SPA.
**How to avoid:** Caddyfile MUST có `try_files {path} /index.html` TRƯỚC `file_server` directive trong handle catch-all block. [CITED: caddyserver.com/docs/caddyfile/directives/file_server + try_files pattern]
**Warning signs:** Direct URL nav (refresh `F5`) trả 404 hoặc blank page; chỉ root `/` work.

### Pitfall 3: BrowserRouter basename mismatch với URL bar → infinite redirect

**What goes wrong:** Backend Caddy serve `/yte/dashboard` → React mount với `basename="/yte"`. Nếu basename compute SAI (vd PREFIX detect trả null khi đáng lẽ "yte") → react-router thấy URL `/yte/dashboard` không khớp `basename=''` → silently match Routes mismatch + có thể loop redirect.
**Why it happens:** `KNOWN_HUBS` fallback hardcode KHÔNG include hub dynamic mới (FACTOR-04 thêm `phap_che` nhưng `__HUB_CONFIG__` chưa update + fallback hardcode chỉ có 3 hub gốc).
**How to avoid:** (1) Ensure `__HUB_CONFIG__.allowlist` injected đúng từ backend/Caddy — verify trong dev tools `console.log(window.__HUB_CONFIG__)`; (2) Fallback hardcode reflect production minimum (Phase 5 initial 3 hub `yte/duoc/hcns`); (3) Add console warning trong api.ts nếu first segment looks like hub (4-16 char lowercase) nhưng not in allowlist.
**Warning signs:** Browser console "No routes matched location" warning từ react-router; URL bar `/yte/dashboard` nhưng Layout không render.

### Pitfall 4: window.__HUB_CONFIG__ chưa available khi api.ts module load

**What goes wrong:** Vite asset script `<script type="module" src="/assets/index-abc.js">` execute parallel với inline `<script>window.__HUB_CONFIG__=...</script>`. Browser load order: HTML parse → script execute. Inline script SYNCHRONOUS (no `type="module"`) execute IMMEDIATELY when parsed. Module script DEFER by default (execute sau DOMContentLoaded). → Inline đảm bảo execute TRƯỚC module script — OK in theory.
**Why it happens:** Nếu Caddy/backend KHÔNG inject `<script>window.__HUB_CONFIG__</script>` (ví dụ static index.html chưa render), api.ts `(window as any).__HUB_CONFIG__` = undefined → fallback hardcode kích hoạt — OK miễn là hardcode đúng.
**How to avoid:** (1) Fallback hardcode đầy đủ initial 3 hub `['yte','duoc','hcns']`; (2) Backend HTML render approach — `api/app/main.py::root_endpoint()` render index.html với env `HUBS_ALLOWLIST` interpolated qua Python template (Claude's Discretion implementation); (3) Caddy `templates` directive approach (KHÔNG có `replace_response` standard) — verify support env interpolation. [ASSUMED: backend HTML render simpler — Plan execution chọn approach cụ thể]
**Warning signs:** Dev console error "ReferenceError: __HUB_CONFIG__ is not defined" hoặc PREFIX detect = null cho URL `/duoc/...`.

### Pitfall 5: Cross-origin fetch 307 redirect strip CORS preflight body

**What goes wrong:** Nếu Login.tsx vẫn submit POST cross-origin (vd `wiki.medinet.vn/yte/login` → fetch `https://central.medinet.vn/api/auth/login`) → browser preflight OPTIONS → 307 location → preflight cho new origin → repeat → có thể strip body trong fail mode.
**Why it happens:** Phase 5 chọn FE-driven redirect (window.location.replace) ĐỂ TRÁNH cross-origin fetch — chuyển sang same-origin trước khi POST. Backend 307 chỉ kick in cho `tryRefresh()` POST `${API_BASE}/api/auth/refresh` từ hub con → 307 → central (same root domain `wiki.medinet.vn` → same-origin → no CORS).
**How to avoid:** Phase 5 ALL on `wiki.medinet.vn` root → same-origin → KHÔNG cross-origin POST. Backend 307 same-origin → browser preserve POST body theo RFC 7231 [CITED: MDN HTTP Status 307].
**Warning signs:** Network tab "CORS error" or POST body empty after 307 follow.

### Pitfall 6: localStorage subpath scope confusion

**What goes wrong:** Operator think `wiki.medinet.vn/yte/` có localStorage isolated vs `wiki.medinet.vn/duoc/`. KHÔNG ĐÚNG — localStorage SCOPE BY ORIGIN (`https://wiki.medinet.vn`), KHÔNG by path. Token share xuyên subpath cùng origin. Đây là DESIRED behavior cho SSO (D-V3-Phase5-C2 LOCKED) NHƯNG cần awareness.
**Why it happens:** Web Storage API spec scope by origin (protocol + host + port).
**How to avoid:** Document trong CLAUDE.md + README — token leak risk cross-hub user same browser; XSS in `/yte/` page có thể đọc token để truy cập `/duoc/`. Accept M2 carry forward; defer v4.0 HARD-V4-05 httpOnly cookie với Path attribute.
**Warning signs:** User báo "logged out ở hub này nhưng hub khác vẫn login" — đó là FEATURE không phải bug; reverse case (logout shouldn't isolate per-hub) là vấn đề thiết kế.

### Pitfall 7: Caddy reload silent failure khi config invalid

**What goes wrong:** `docker compose exec caddy caddy reload` chạy exit code 0 nhưng config thật KHÔNG apply (rollback to previous). hub-add.sh step 9 không catch.
**Why it happens:** [CITED: caddyserver.com/docs/api] "If a new configuration fails validation, the old config is rolled back into place without downtime" — Caddy AUTO rollback silently. Operator KHÔNG biết.
**How to avoid:** hub-add.sh step 9 PRE-validate: `docker compose exec caddy caddy validate --config /etc/caddy/Caddyfile` TRƯỚC reload; chỉ reload nếu validate PASS. Sau reload smoke `curl https://<domain>/<new_hub>/api/health` verify route work.
**Warning signs:** Hub mới add nhưng curl `/<new>/api/health` 404; check `docker compose logs caddy | grep -i "reload\|error"`.

### Pitfall 8: Vite import.meta.glob TypeScript inference fail với generic

**What goes wrong:** `import.meta.glob<{ branding: BrandingConfig }>('./*/index.ts', { eager: true })` — TypeScript có thể không infer correctly nếu Vite types không cập nhật.
**Why it happens:** Vite 6 types include `import.meta.glob<T>` generic; nhưng tsconfig.json `lib` settings hoặc `types: ["vite/client"]` thiếu sẽ fail.
**How to avoid:** Verify `frontend/tsconfig.json` có `"types": ["vite/client", "node"]` (hoặc equivalent). Fallback nếu generic fail: dùng untyped + manual narrow `const branding = modules[path].branding as BrandingConfig`.
**Warning signs:** `tsc --noEmit` lint fail với "Property 'branding' does not exist on type 'unknown'".

### Pitfall 9: HUBS_ALLOWLIST_REGEX env render escape characters

**What goes wrong:** `HUBS_ALLOWLIST=yte,duoc,hcns` → sed render `HUBS_ALLOWLIST_REGEX=yte|duoc|hcns` cho Caddyfile. Nếu hub name có `_` (vd `phap_che`) → regex OK (`_` literal). Nếu có `.` hoặc `-` → regex special char escape needed.
**Why it happens:** Settings regex Plan 02-05 chỉ accept `^[a-z][a-z0-9_]{0,15}$` → KHÔNG có `.`/`-`/`/` → an toàn. Nhưng nếu future relax regex (Phase 6 SETTINGS-04 dynamic registry), phải escape khi render.
**How to avoid:** Phase 5 strict regex match Settings — không escape needed cho `[a-z0-9_]`. Document constraint trong hub-add.sh + README.
**Warning signs:** Caddy validate fail "invalid regular expression"; logs "regexp: Compile..." error.

### Pitfall 10: Caddy directive ordering — handle vs handle_path placement

**What goes wrong:** Plan execution có thể đặt `handle /api/* { reverse_proxy central }` TRƯỚC `handle @hub_api {...}` trong file — kỳ vọng matcher order. NHƯNG Caddy auto-sort handle blocks by matcher specificity [CITED: caddyserver.com/docs/caddyfile/directives/handle "handle directives are sorted according to the directive sorting algorithm by their matchers"].
**Why it happens:** Caddy AUTOMATICALLY reorder — operator-written order KHÔNG significant cho `handle` (NHƯNG SIGNIFICANT cho `route`).
**How to avoid:** Either trust Caddy auto-sort (named matcher `@hub_api path_regexp` specific hơn glob `/api/*` → @hub_api wins khi URL match cả 2) HOẶC dùng `route` để control explicit order. Verify với `caddy adapt --config Caddyfile` print resolved JSON order.
**Warning signs:** Wrong upstream receive request — vd `/yte/api/health` đi tới central thay vì python-api-yte.

---

## Code Examples

### Caddyfile complete Phase 5 — Recommended single-file pattern

```caddyfile
# Hub_All/Caddyfile — Phase 5 (ADD wiki block parallel MCP block)
# Source: caddyserver.com/docs/caddyfile/* multiple directives verified 2026

# ─── Global options ─────────────────────────────────────────────────────────
# (M2 Phase 8.3 default — no edit)

# ─── MCP block (UNCHANGED — Phase 8.3 carry forward) ────────────────────────
{$MCP_PUBLIC_DOMAIN} {
    reverse_proxy medinet-mcp:8190
}

# ─── Wiki block (NEW Phase 5) ───────────────────────────────────────────────
# Caddy auto-TLS:
#   - WIKI_PUBLIC_DOMAIN=localhost → self-signed cert
#   - WIKI_PUBLIC_DOMAIN=wiki.medinet.vn → ACME Let's Encrypt
{$WIKI_PUBLIC_DOMAIN:localhost} {
    # ─── Hub API routing (regex + strip prefix) ────────────────────────────
    # HUBS_ALLOWLIST_REGEX="yte|duoc|hcns" rendered from HUBS_ALLOWLIST=yte,duoc,hcns
    # by hub-add.sh step 8
    @hub_api path_regexp hub_api ^/({$HUBS_ALLOWLIST_REGEX:yte|duoc|hcns})/api/(.*)$
    handle @hub_api {
        # Strip /<hub> prefix → upstream nhận /api/health
        # Cảnh báo: container name dynamic OK, port STATIC :8080
        route {
            uri strip_prefix /{re.hub_api.1}
            reverse_proxy http://python-api-{re.hub_api.1}:8080 {
                header_up Host {host}
                header_up X-Real-IP {remote_host}
                header_up X-Forwarded-For {remote_host}
                header_up X-Forwarded-Proto {scheme}
                header_up X-Forwarded-Hub {re.hub_api.1}  # debug header
            }
        }
    }

    # ─── Central API (no strip) ─────────────────────────────────────────────
    handle /api/* {
        reverse_proxy http://python-api-central:8080 {
            header_up Host {host}
            header_up X-Real-IP {remote_host}
            header_up X-Forwarded-For {remote_host}
            header_up X-Forwarded-Proto {scheme}
        }
    }

    # ─── .well-known (carry forward — central JWKS endpoint Phase 3) ───────
    # /.well-known/jwks.json forwarded NGUYÊN → central handle
    # (Already covered by /api/* if mounted at /.well-known but JWKS path = root not /api/...
    # → cần explicit handle nếu Plan 03-01 mount at /.well-known root)
    handle /.well-known/* {
        reverse_proxy http://python-api-central:8080
    }

    # ─── Static SPA (catch-all) ─────────────────────────────────────────────
    handle {
        root * /srv/wiki/dist
        try_files {path} /index.html
        file_server
    }

    # ─── Logging ────────────────────────────────────────────────────────────
    log {
        output stdout
        format json
        level INFO
    }
}
```

### docker-compose.yml caddy service Phase 5 edit

```yaml
# Hub_All/docker-compose.yml — EDIT caddy service block (line 271-286)
  caddy:
    image: caddy:2-alpine
    container_name: medinet-caddy
    restart: unless-stopped
    environment:
      MCP_PUBLIC_DOMAIN: ${MCP_PUBLIC_DOMAIN:-localhost}
      # NEW Phase 5
      WIKI_PUBLIC_DOMAIN: ${WIKI_PUBLIC_DOMAIN:-localhost}
      HUBS_ALLOWLIST_REGEX: ${HUBS_ALLOWLIST_REGEX:-yte|duoc|hcns}
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - medinet_caddy_data:/data
      - medinet_caddy_config:/config
      # NEW Phase 5 — Vite dist mount cho file_server
      - ./frontend/dist:/srv/wiki/dist:ro
    depends_on:
      - mcp_service
      - python-api-central  # NEW Phase 5 dependency
    networks: [medinet_net]
```

### hub-add.sh extension Phase 5 (step 8 + 9)

```bash
# api/scripts/hub-add.sh — APPEND sau step 7c (line 214)

# ──────────────────────────────────────────────────────────────────────────
# (8/9) Update .env HUBS_ALLOWLIST + HUBS_ALLOWLIST_REGEX
# ──────────────────────────────────────────────────────────────────────────

ENV_FILE="$COMPOSE_ROOT/.env"

# Idempotent: nếu .env không tồn tại → tạo từ .env.example
if [ ! -f "$ENV_FILE" ]; then
    if [ -f "$COMPOSE_ROOT/.env.example" ]; then
        cp "$COMPOSE_ROOT/.env.example" "$ENV_FILE"
    else
        echo "HUBS_ALLOWLIST=yte,duoc,hcns" > "$ENV_FILE"
    fi
fi

# Extract current allowlist (default empty if not present)
CURRENT_ALLOWLIST=$(grep -E "^HUBS_ALLOWLIST=" "$ENV_FILE" | head -1 | cut -d= -f2- || echo "")

# Check duplicate
if [[ ",$CURRENT_ALLOWLIST," == *",$HUB,"* ]]; then
    echo "[hub-add] (8) HUB '$HUB' đã có trong HUBS_ALLOWLIST — skip env update"
else
    NEW_ALLOWLIST="${CURRENT_ALLOWLIST:+$CURRENT_ALLOWLIST,}$HUB"
    NEW_REGEX=$(echo "$NEW_ALLOWLIST" | tr ',' '|')

    # Atomic edit qua tmp file + mv (preserve other env vars)
    TMP_ENV=$(mktemp)
    if grep -qE "^HUBS_ALLOWLIST=" "$ENV_FILE"; then
        sed "s|^HUBS_ALLOWLIST=.*|HUBS_ALLOWLIST=$NEW_ALLOWLIST|" "$ENV_FILE" > "$TMP_ENV"
    else
        cp "$ENV_FILE" "$TMP_ENV"
        echo "HUBS_ALLOWLIST=$NEW_ALLOWLIST" >> "$TMP_ENV"
    fi

    if grep -qE "^HUBS_ALLOWLIST_REGEX=" "$TMP_ENV"; then
        sed -i.bak "s|^HUBS_ALLOWLIST_REGEX=.*|HUBS_ALLOWLIST_REGEX=$NEW_REGEX|" "$TMP_ENV" \
            && rm -f "${TMP_ENV}.bak"
    else
        echo "HUBS_ALLOWLIST_REGEX=$NEW_REGEX" >> "$TMP_ENV"
    fi

    mv "$TMP_ENV" "$ENV_FILE"
    echo "[hub-add] (8) Updated .env HUBS_ALLOWLIST=$NEW_ALLOWLIST"
fi

# ──────────────────────────────────────────────────────────────────────────
# (9/9) Caddy reload (zero-downtime atomic swap)
# ──────────────────────────────────────────────────────────────────────────

# Pre-validate config trước reload (avoid silent rollback)
if docker compose ps caddy --format json 2>/dev/null | grep -q '"State":"running"'; then
    echo "[hub-add] (9) Validate + reload Caddy..."

    # Validate first — KHÔNG dùng silent rollback
    if ! docker compose exec -T caddy caddy validate --config /etc/caddy/Caddyfile; then
        echo "[hub-add] ERROR: Caddy config validate FAIL — rollback .env edit"
        # Rollback HUBS_ALLOWLIST edit (TODO: backup + restore)
        exit 4
    fi

    # Atomic reload (Caddy admin API zero-downtime)
    if ! docker compose exec -T caddy caddy reload --config /etc/caddy/Caddyfile; then
        echo "[hub-add] ERROR: Caddy reload FAIL"
        exit 4
    fi

    # Smoke checkpoint: verify hub mới route work
    sleep 1  # cho Caddy settle
    if command -v curl >/dev/null && [ -n "${WIKI_PUBLIC_DOMAIN:-}" ]; then
        SMOKE_URL="https://${WIKI_PUBLIC_DOMAIN}/${HUB}/api/health"
        echo "[hub-add] (9) Smoke check: curl -k $SMOKE_URL"
        if curl -k -sf -o /dev/null "$SMOKE_URL"; then
            echo "[hub-add] (9) Smoke PASS"
        else
            echo "[hub-add] WARN: Smoke check returned non-200 — backend container may not be up yet."
            echo "         Run: docker compose up -d python-api-$HUB && curl -k $SMOKE_URL"
        fi
    fi
else
    echo "[hub-add] (9) Caddy container chưa running — skip reload (sẽ apply khi docker compose up)"
fi
```

### Frontend prefix detect refactor api.ts (top of file)

```typescript
// frontend/src/services/api.ts — REPLACE line 1-3 với block dưới
// Phase 5 D-V3-Phase5-B1 LOCKED

// Runtime hub config — injected by backend HTML render OR Caddy templates
// (Phase 5 chốt approach ở plan — Claude's Discretion)
interface HubConfigRuntime {
  allowlist: readonly string[];
  current?: string;
}

declare global {
  interface Window {
    __HUB_CONFIG__?: HubConfigRuntime;
  }
}

const HUB_CONFIG: HubConfigRuntime = window.__HUB_CONFIG__ ?? {
  // Fallback hardcode initial 3 hub gốc Phase 5
  // Phase 6 SETTINGS-04 sẽ sync từ DB-driven hub_registry
  allowlist: ['yte', 'duoc', 'hcns'] as const,
};

const KNOWN_HUBS: readonly string[] = HUB_CONFIG.allowlist;

const firstSegment: string | undefined = window.location.pathname
  .split('/')
  .filter(Boolean)[0];

export const PREFIX: string | null =
  firstSegment && KNOWN_HUBS.includes(firstSegment) ? firstSegment : null;

export const API_BASE: string = PREFIX ? `/${PREFIX}/api` : '/api';
export const APP_BASE: string = PREFIX ? `/${PREFIX}` : '';
export const CURRENT_HUB: string = PREFIX ?? 'central';

// API_URL relative — Caddy same-origin gateway (KHÔNG cần absolute hostname:port nữa)
const API_URL = API_BASE;
// Existing APIClient class signature unchanged (constructor consume API_URL)

// IMPORTANT: api.crossHubSearch() — central-only endpoint (D-V3-Phase4-D3 LOCKED)
// Override để dùng absolute /api/search/cross-hub thay vì ${API_BASE}/search/cross-hub
// (api.ts class method override hoặc tách export function)
// → Section 7 implementation detail
```

---

## Cross-hub UI Redirect Handling (D-V3-Phase4-D3 carry forward)

**Background:** Phase 4 Plan 04-05 LOCKED — hub con strip `/api/search/cross-hub` (FACTOR-02 extend). Chỉ central mount endpoint. Frontend `CrossHubSearch.tsx` page (M2 hardcode `api.crossHubSearch()`) hiện tại gọi `${baseURL}/api/search/cross-hub` qua APIClient `request()` helper.

**Vấn đề Phase 5:** Khi user mở `wiki.medinet.vn/yte/search` (hub con với CrossHubSearch page) → `api.crossHubSearch()` resolve `${API_BASE}/search/cross-hub` = `/yte/api/search/cross-hub` → Caddy match `@hub_api` regex → strip → upstream `python-api-yte:8080/api/search/cross-hub` → **404 envelope** (FACTOR-02 strip). UX break.

**Options:**

### Option A (Recommended): Frontend api.ts override absolute path

**Implementation:**
```typescript
// frontend/src/services/api.ts — thêm method special-case
class APIClient {
  // ... existing methods

  async crossHubSearch(data: SearchRequestAPI) {
    // CRITICAL: ALWAYS gọi central absolute path /api/search/cross-hub
    // — D-V3-Phase4-D3: hub con strip endpoint, chỉ central mount
    // Override base URL từ /<hub>/api → /api absolute
    return this.requestAbsolute<SearchResponseAPI>('POST', '/api/search/cross-hub', data);
  }

  private async requestAbsolute<T>(method: string, absolutePath: string, body?: unknown) {
    // Same as request() but ignore this.baseURL prefix — use absolutePath direct
    // Caddy /api/* handle block → forward central (no strip)
    // ...
  }
}
```

**Tradeoff:**
- ✅ Đơn giản, KHÔNG cần Caddy rewrite rule mới
- ✅ Same-origin (wiki.medinet.vn) → no CORS issues
- ✅ Caddy `/api/*` handle block (existing) automatic route central
- ✅ Khi user navigate `/yte/search` → API call thấy /api/search/cross-hub trong Network tab (clear central endpoint)
- ⚠️ FE phải biết endpoint nào là "central-only" — maintain list trong api.ts. Thêm endpoint cross-hub mới (vd Phase 6 admin endpoint) → update FE same time.
- ⚠️ Inconsistent với pattern khác (mọi method khác dùng `${API_BASE}` prefix) — code review cần catch override intent.

### Option B: Caddy server-side rewrite

**Implementation:**
```caddyfile
# Thêm vào wiki block trước @hub_api matcher
@hub_cross_hub path_regexp hub_cross_hub ^/(yte|duoc|hcns)/api/search/cross-hub$
handle @hub_cross_hub {
    rewrite * /api/search/cross-hub
    reverse_proxy http://python-api-central:8080
}
```

**Tradeoff:**
- ✅ FE code KHÔNG cần special-case — vẫn dùng `${API_BASE}/search/cross-hub`
- ✅ Caddy handle routing — single source-of-truth ở reverse proxy layer
- ⚠️ Caddy config phức tạp hơn — thêm matcher + handle block per cross-hub endpoint
- ⚠️ Khi thêm cross-hub endpoint mới Phase 6/7 — phải update Caddyfile + reload (operator step)
- ⚠️ Browser DevTools Network tab thấy URL `/yte/api/search/cross-hub` (confusing — actually goes central)
- ⚠️ Audit log central sẽ thấy request path nguyên (`/yte/api/search/cross-hub` HOẶC `/api/search/cross-hub` tùy rewrite point) — semantic ambiguity

**Recommendation:** **Option A (Frontend api.ts absolute override)**. Lý do:
1. **Single source-of-truth** trong code (FE), KHÔNG split logic Caddyfile vs FE.
2. **Easier debugging** — DevTools Network tab show clear central endpoint.
3. **Scaling:** Phase 6/7 thêm cross-hub endpoint → chỉ thêm 1 method `crossHub*()` trong api.ts; Caddyfile KHÔNG cần edit + reload.
4. **Consistency với SSO pattern** Plan 03-04 — frontend Login.tsx redirect chính chủ (window.location.replace central) thay vì backend transparent — same "FE-driven cross-prefix navigation" principle.

**Documentation:** Add comment block trên `crossHubSearch()` method giải thích "central-only endpoint absolute path override — see Phase 4 D-V3-Phase4-D3 + Phase 5 RESEARCH §7".

---

## Smoke Regression Strategy

### M2 COMPAT-01 11 trang React checklist (R-V3-2 mitigation)

Carry forward từ M2 — KHÔNG break sau frontend rewrite D6 expire:

| # | Page | URL central | URL hub yte | Verify |
|---|------|-------------|-------------|--------|
| 1 | Login | `/login` | `/yte/login` (redirect central) | Form render, branding khác per-hub, theme color inline |
| 2 | Dashboard | `/` | `/yte/` | Layout sidebar title đúng hub, stats cards load |
| 3 | Documents | `/documents` | `/yte/documents` | List load via `/yte/api/documents` (Network tab verify) |
| 4 | DocumentIngestion | `/documents/new` | `/yte/documents/new` | Upload form render; submit qua `${API_BASE}/documents/upload` |
| 5 | Search / CrossHubSearch | `/search` | `/yte/search` | CrossHubSearch gọi absolute `/api/search/cross-hub` (Option A); single hub search gọi `${API_BASE}/search` |
| 6 | HubRegistry | `/registry` (central-only) | `/yte/registry` → 404 wrap envelope (FACTOR-02) | Central render hub list; hub con render error page |
| 7 | UserManagement | `/users` (central-only) | `/yte/users` → 404 | Central CRUD form |
| 8 | APIKeyManagement | `/api-keys` (central-only) | `/yte/api-keys` → 404 | Central CRUD |
| 9 | AuditLog | `/logs` (central-only) | `/yte/logs` → 404 | Central paginate |
| 10 | Profile | `/profile` | `/yte/profile` | Profile load via `${API_BASE}/profile` |
| 11 | Settings | `/settings` (central-only) | `/yte/settings` → 404 | Central settings form |

**Pages central-only (#6,7,8,9,11):** Hub con FE Layout sidebar vẫn hiển thị menu items (M2 không có hub-aware sidebar). Click → react-router navigate → Layout mount + Settings.tsx call `${API_BASE}/settings` = `/yte/api/settings` → 404 envelope (FACTOR-02 strip). FE phải render error gracefully — KHÔNG infinite spinner / blank page. **Recommendation Phase 5:** Add `<Route element={<HubGuard hubScopedOnly={['/'... etc] />}>` wrap hoặc filter sidebar items by CURRENT_HUB (claude's discretion plan).

### Manual checklist dev local 4 hub × 11 trang (D-V3-Phase5-D4)

Closeout plan task `checkpoint:human-action gate=blocking`:

**Setup:**
```bash
cd Hub_All
# .env setup
echo "WIKI_PUBLIC_DOMAIN=localhost" >> .env
echo "HUBS_ALLOWLIST=yte,duoc,hcns" >> .env
echo "HUBS_ALLOWLIST_REGEX=yte|duoc|hcns" >> .env

# Build frontend
cd frontend && npm run build && cd ..

# Up compose (Postgres + Redis + 4 python-api + Caddy)
docker compose up -d

# Wait healthy (5-10s)
sleep 8
docker compose ps
```

**Verify checklist:**
```bash
# A. Caddy routing (PROXY-01 satisfied)
curl -k -i https://localhost/api/health           # central → 200
curl -k -i https://localhost/yte/api/health       # python-api-yte → 200 (prefix stripped)
curl -k -i https://localhost/duoc/api/health      # python-api-duoc → 200
curl -k -i https://localhost/hcns/api/health      # python-api-hcns → 200
curl -k -i https://localhost/invalid/api/health   # Caddy file_server fallback → /index.html (200) hoặc 404 nếu strict

# B. Static SPA fallback
curl -k -i https://localhost/                     # index.html
curl -k -i https://localhost/dashboard            # index.html (try_files fallback)
curl -k -i https://localhost/yte/dashboard        # index.html (NESTED fallback)
curl -k -i https://localhost/yte/login            # index.html (Login.tsx mount → redirect)

# C. Asset path
curl -k -i https://localhost/assets/index-abc.js   # 200 actual asset
curl -k -i https://localhost/branding/yte/logo.svg # 200 actual SVG
```

**Browser smoke 11 trang per hub:**
```
1. Open https://localhost/login (cert warning accept)
2. Login với credential test (email/password — Plan 03-04 carry forward)
3. Verify Dashboard load + sidebar title "Medinet Wiki" (central branding)
4. Click hết 11 menu items central
5. Logout
6. Open https://localhost/yte/login
7. Verify auto redirect tới https://localhost/login?return=/yte
8. Verify Login.tsx hiển thị branding yte (emerald theme, "Hub Y tế Medinet")
9. Login → redirect /yte/dashboard
10. Verify Layout sidebar "Hub Y tế Medinet" title
11. Click 11 menu items — central-only (5 items) phải render error gracefully
12. Repeat step 6-11 cho duoc + hcns
```

**Resume signal pattern (carry forward Plan 03-05 + 04-07):**
- `approved` — manual smoke 4 hub × 11 trang PASS
- `regress in <component>` — user thấy break ở component cụ thể → plan task fix
- `skip smoke` — defer Phase 7 MIGRATE-05 (v3.0-b precedent OK NHƯNG D-V3-Phase5-D4 chốt minimum branding + 11 trang smoke required vì R-V3-2 cần human verify UX)

**Pre-resolve precedent từ v3.0-b:** Plan 03-05 + 04-07 đều có Task 5 smoke compose runtime SKIP pre-resolved (user decision rationale: in-process test cover semantic + smoke runtime defer Phase 7). **Phase 5 KHÁC** — PROXY-04 + R-V3-2 mitigation cần FE/UX human verify. Recommended cuối Plan 5-X (closeout) chốt smoke `at least branding verification 4 hub` minimum; 11 trang full regression có thể partial defer Phase 7 nếu user accept evidence chain (api.ts unit test + branding registry unit test + Caddy validate PASS).

---

## Risk + Pitfalls (cross-cutting Phase 5)

### R-V3-2 (HIGH) Frontend rewrite regress

**Severity:** HIGH (ROADMAP Risk Register)
**Trigger:** Phase 5 D6 expire → cho phép rewrite api.ts + App.tsx + Login.tsx + Layout.tsx + branding/ → có thể break 11 trang React M2 COMPAT-01.

**Mitigation chain:**
1. **Scope minimal:** D-V3-Phase5-D2 chốt branding chỉ 2 component touch (Login + Layout sidebar header) — Dashboard/Documents/Search/etc giữ NGUYÊN M2 styling.
2. **Single source-of-truth:** api.ts API_BASE compute module-level — KHÔNG hook/context (giảm re-render risk).
3. **Type safety:** TypeScript strict + tsconfig + `tsc --noEmit` lint trước commit.
4. **Manual smoke 4 hub × 11 trang:** D-V3-Phase5-D4 chốt minimum verify.
5. **Failsafe:** Backend 307 redirect Plan 03-04 carry forward — nếu FE redirect logic Login.tsx fail (bug), backend safety net.
6. **Branding fallback:** `getBranding(unknown_hub)` → central fallback (KHÔNG crash).
7. **PREFIX null safety:** `KNOWN_HUBS.includes(seg)` → null fallback central — handle dynamic hub mới chưa trong allowlist.

### Edge cases (consolidated)

1. **FACTOR-04 dynamic hub mới (vd `phap_che` add qua make hub-add):** `HUBS_ALLOWLIST` env update → Caddy reload → backend route work. NHƯNG frontend hardcode fallback `['yte','duoc','hcns']` KHÔNG có `phap_che` → PREFIX detect FAIL → render central branding. **Mitigation:** `window.__HUB_CONFIG__.allowlist` injected by backend (single source) — Caddy/backend re-render index.html sau env reload. Fallback hardcode chỉ là dev safety net.

2. **Browser direct nav `/yte/api/health` (KHÔNG qua FE):** Caddy route OK → backend respond JSON. FE không bao giờ render `/yte/api/health` path — react-router KHÔNG match (basename `/yte`, path `/api/health` → ngoài route table). Acceptable — API URL direct test for ops.

3. **`/yte/login` typed directly:** Login.tsx mount với CURRENT_HUB='yte' → useEffect fire → `window.location.replace('/login?return=/yte')` → page navigate cross-prefix → mount lại Login.tsx với CURRENT_HUB='central' + parse `?return=yte` → render yte branding + post-login → `/yte/dashboard`. Two render cycle OK; user perceive flash.

4. **Hub con FE Layout sidebar central-only menu items (HubRegistry, UserManagement, etc):** User click → navigate → mount component → API call 404 envelope. **Mitigation Phase 5 (claude's discretion):** Filter `menuItems` array in Layout.tsx by `CURRENT_HUB === 'central'` — hide central-only items at hub con. OR show + render error page. Recommend filter to match BE strip semantic.

5. **Caddy `/.well-known/jwks.json` routing:** Plan 03-01 mount endpoint ở central root `/.well-known/jwks.json` (KHÔNG qua `/api/`). Caddyfile MUST có explicit `handle /.well-known/*` block trước `handle` catch-all static — otherwise file_server lookup `dist/.well-known/jwks.json` → 404 → JWKSCache fetch fail boot. **Already covered trong Pattern 1 example.**

6. **Vite dev server (`npm run dev`) vs Caddy proxy:** Phase 5 prod path: Caddy → static dist/. Dev path: vite dev server (port 3000) — fetch `/api/*` cần proxy tới python-api host. Recommended: `vite.config.ts` add `server.proxy` config (claude's discretion plan):
   ```ts
   server: {
     proxy: {
       '/api': 'http://localhost:8180',
       '/yte/api': 'http://localhost:8181',
       // ... etc
     }
   }
   ```
   OR run Caddy in dev mode reverse proxy frontend vite dev server + backend. Defer plan implementation.

7. **HMR conflict với basename:** Vite HMR WebSocket path. Nếu Caddy proxy vite dev → HMR socket path may conflict with `/yte/` prefix. Dev workaround: skip Caddy for dev frontend, use vite dev direct on port 3000 + CORS to API.

8. **localStorage clean-up cross-hub:** User logout ở `/yte/` → `localStorage.removeItem('access_token')` → token cleared origin-wide → logged out tất cả hub. Đây là DESIRED (true SSO behavior — single logout) — accept.

9. **Multi-tab branding inconsistency:** Tab 1 `/yte/dashboard` (branding yte), Tab 2 `/duoc/dashboard` (branding duoc). Cùng origin same localStorage. OK — branding scoped to URL prefix, not localStorage. Verify trong manual smoke.

10. **MCP path `wiki.medinet.vn/mcp` future:** Defer Phase 7 MIGRATE-04. Hiện tại MCP block trên `mcp.medinet.vn` subdomain. Phase 5 KHÔNG touch.

---

## Plan Decomposition Hint

Đề xuất N plan + wave structure cho gsd-planner. Phase 5 estimate ~5 plan / 4 wave.

### Wave 1 BLOCKING — Caddy + env scaffolding

- **Plan 05-01** — Caddyfile wiki block + docker-compose caddy service edit + .env.example update
  - PROXY-01 partial
  - Files: `Hub_All/Caddyfile` (ADD wiki block), `Hub_All/docker-compose.yml` (ADD WIKI_PUBLIC_DOMAIN + HUBS_ALLOWLIST_REGEX env + frontend/dist volume mount), `Hub_All/.env.example` (document 3 env vars)
  - Tasks: 3 (1 caddyfile + 1 compose + 1 env.example)
  - Verify: `docker compose config --quiet` exit 0; `caddy validate --config Caddyfile`; smoke test pseudo `curl -k https://localhost/api/health` (manual or scripted)
  - Wave: BLOCKING — downstream plans cần Caddyfile structure đúng

### Wave 2 PARALLEL × 2 (file-disjoint)

- **Plan 05-02** — Frontend prefix detect refactor (api.ts + App.tsx)
  - PROXY-02 partial
  - Files: `frontend/src/services/api.ts` (REPLACE module-level prefix detect block), `frontend/src/App.tsx` (ADD basename={APP_BASE})
  - Tasks: 2-3 (1 api.ts refactor + 1 App.tsx edit + 1 unit test prefix detect)
  - Verify: Add `frontend/src/services/__tests__/api.spec.ts` (vitest hoặc plain) test PREFIX/API_BASE/APP_BASE compute với mock window.location.pathname; `npm run lint` (tsc --noEmit) PASS
  - Wave: Parallel với 05-03 (different files)

- **Plan 05-03** — Per-hub branding module + public assets
  - PROXY-04 partial
  - Files: NEW `frontend/src/branding/index.ts` + `branding/{central,yte,duoc,hcns}/index.ts` + NEW `frontend/public/branding/{central,yte,duoc,hcns}/logo.svg` (placeholder)
  - Tasks: 3 (1 registry helper + 1 per-hub config × 4 + 1 SVG placeholder × 4)
  - Verify: Unit test `getBranding('yte').themeColor === '#10b981'`; `getBranding('unknown') === FALLBACK`; tsc --noEmit PASS
  - Wave: Parallel với 05-02

### Wave 3 — Frontend UX integration

- **Plan 05-04** — Login.tsx + Layout.tsx integration với branding + redirect
  - PROXY-02 + PROXY-04 satisfied
  - Files: `frontend/src/pages/Login.tsx` (ADD useEffect mount redirect + branding render), `frontend/src/Layout.tsx` (REPLACE hardcode "Medinet Wiki" với getBranding(CURRENT_HUB).title + logo), `frontend/src/services/api.ts` (ADD crossHubSearch override absolute path — Section 7 Option A)
  - Tasks: 3 (1 Login refactor + 1 Layout refactor + 1 api.ts cross-hub override)
  - Verify: tsc lint; manual visual inspect dev server `npm run dev` (separate from Caddy smoke); unit test `crossHubSearch` calls absolute path
  - Wave: Depend 05-02 (CURRENT_HUB export) + 05-03 (getBranding export)

### Wave 4 — FACTOR-04 hub-add.sh extension

- **Plan 05-05** — hub-add.sh step 8 + 9 + smoke checkpoint
  - PROXY-01 + FACTOR-04 extend satisfied
  - Files: `Hub_All/api/scripts/hub-add.sh` (APPEND step 8 + 9 — Section "Code Examples"), update existing comment Step "(7/7)" → "(9/9)", `Hub_All/Makefile` (no change — `make hub-add` target carry forward)
  - Tasks: 2-3 (1 hub-add.sh edit + 1 unit/smoke test bash `bash -n` syntax check + 1 dry-run with mock hub name)
  - Verify: `bash -n api/scripts/hub-add.sh` exit 0; manual dry-run `HUB=tmp_test bash api/scripts/hub-add.sh` (cleanup after)
  - Wave: Depend 05-01 (Caddyfile env structure) — KHÔNG depend 05-02/03/04

### Wave 5 — Closeout docs + smoke checkpoint manual

- **Plan 05-06** — Docs update + manual smoke checkpoint 4 hub × 11 trang
  - PROXY-03 (D6 expire formally) + PROXY-04 verify
  - Files: `Hub_All/CLAUDE.md` (§3 D6 EXPIRED note + §6 Phase 5 progress row + Phase 5 pattern subsection — match style của Phase 2/3/4 subsection), `.planning/STATE.md` (frontmatter + Current Position + Phase 5 Planning + Results Summary table + Next Action), `.planning/REQUIREMENTS.md` (PROXY-01..04 mark [x] + NOTE Phase 5 closeout 5-step plan list), `.planning/ROADMAP.md` (Phase 5 status DONE + Progress table), `Hub_All/README.md` (section mới "Reverse Proxy Subpath Deploy Notes (Phase 5 v3.0)" với env list + Caddy reload + smoke commands)
  - Tasks: 5 (4 docs + 1 checkpoint human-action gate=blocking smoke 4 hub × 11 trang)
  - Verify: grep acceptance criteria 4 file PASS; markdown structure preserve
  - Wave: Closeout — depend tất cả 05-01..05

### Critical path + auto-chain pause

**Critical path:** 05-01 (BLOCKING) → {05-02 ⊥ 05-03} (parallel Wave 2) → 05-04 (Wave 3 depend 05-02 + 05-03) → 05-05 (Wave 4 depend 05-01) → 05-06 (Wave 5 closeout)

**Auto-chain pause expected:** Plan 05-06 Task 5 `checkpoint:human-action gate=blocking` — smoke 4 hub × 11 trang. User resume signal:
- `approved` (full smoke PASS)
- `partial: branding only` (4 hub × Login + Dashboard only — defer 9 trang Phase 7)
- `skip smoke` (full defer — chỉ chấp nhận nếu R-V3-2 trade-off OK)

**Wave 0 (test infra) — KHÔNG cần Phase 5 dedicated:** Frontend test framework (vitest hoặc jest) — package.json hiện chỉ có `tsc --noEmit` lint, KHÔNG có test runner. Decision Claude's Discretion plan: (A) ADD vitest dep + minimal config + 5-10 unit test files; HOẶC (B) keep lint-only + manual smoke. **Recommended A** vì R-V3-2 mitigation + Phase 5 logic critical. Vitest setup ~30 phút effort.

---

## Validation Architecture (Nyquist)

`workflow.nyquist_validation: true` trong config.json — include section. Nhưng Phase 5 chủ yếu frontend + Caddy config; algorithmic verification minimal.

### Test Framework

| Property | Value |
|----------|-------|
| Backend Framework | pytest 8.x + httpx AsyncClient + asgi-lifespan + testcontainers (carry forward M2 Phase 10) [VERIFIED: pyproject.toml dep] |
| Backend Config file | `api/pyproject.toml` `[tool.pytest.ini_options]` |
| Backend Quick run | `cd api && uv run pytest tests/unit -x --tb=short` |
| Backend Full suite | `cd api && uv run pytest -m "critical and integration" --maxfail=5` |
| Frontend Framework | **GAP** — chỉ có `tsc --noEmit` lint (package.json line 11). Vitest dep CHƯA install. |
| Frontend Quick run | `cd frontend && npm run lint` (tsc only) |
| Frontend Full suite | Same as quick run |
| Caddy validate | `docker compose exec caddy caddy validate --config /etc/caddy/Caddyfile` |
| Bash script syntax | `bash -n api/scripts/hub-add.sh` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| PROXY-01 | Caddy route `/<hub>/api/*` → upstream + strip prefix | smoke (manual) | `curl -k https://localhost/yte/api/health` | ❌ Wave 0 manual check |
| PROXY-01 | Caddyfile validate | unit (CLI tool) | `docker compose exec caddy caddy validate --config /etc/caddy/Caddyfile` | ✅ existing caddy CLI |
| PROXY-02 | api.ts compute PREFIX + API_BASE + APP_BASE | unit (FE) | `cd frontend && npx vitest run src/services/__tests__/api.spec.ts` (needs vitest setup Wave 0) | ❌ NEW test file Plan 05-02 |
| PROXY-02 | App.tsx renders với basename | unit (FE) | Same vitest — render `<App>` với mock window.location | ❌ NEW test Plan 05-02 |
| PROXY-02 | api.crossHubSearch absolute path | unit (FE) | vitest — assert fetch called với `/api/search/cross-hub` không prefix | ❌ NEW test Plan 05-04 |
| PROXY-03 | D6 expire formally — CLAUDE.md update | manual review | `grep "D6 EXPIRED" Hub_All/CLAUDE.md` | ❌ — manual ở Plan 05-06 |
| PROXY-03 | Smoke regression 11 trang | manual (human) | Manual checklist 4 hub × 11 trang | ❌ — Plan 05-06 checkpoint |
| PROXY-04 | getBranding returns correct config | unit (FE) | vitest — `getBranding('yte').themeColor === '#10b981'` | ❌ NEW test Plan 05-03 |
| PROXY-04 | Login renders branding theme color | unit (FE) | vitest — render `<Login>` mock searchParams + assert style attribute | ❌ NEW test Plan 05-04 |
| PROXY-04 | Layout renders branding title | unit (FE) | vitest — render `<Layout>` + assert sidebar text matches | ❌ NEW test Plan 05-04 |
| FACTOR-04 extend | hub-add.sh step 8 + 9 idempotent | smoke (bash) | `bash -n api/scripts/hub-add.sh` + dry-run | ✅ existing bash; ❌ NEW assertion ở Plan 05-05 |

### Sampling Rate

- **Per task commit:** `npm run lint` (tsc) + (if Wave 0 ships vitest) `npx vitest run` quick
- **Per wave merge:** Full FE test + `caddy validate` + `bash -n`
- **Phase gate:** Plan 05-06 manual smoke 4 hub × 11 trang (D-V3-Phase5-D4)

### Wave 0 Gaps

- [ ] **Frontend test framework setup** — Add `vitest@^2` + `@testing-library/react@^16` + `jsdom@^25` deps + `frontend/vitest.config.ts` + `frontend/src/test-setup.ts` (jsdom + cleanup). Effort: ~30min. Recommend Plan 05-02 Task 1 hoặc tách Plan 05-02a Wave 0 task.
- [ ] **`frontend/src/services/__tests__/api.spec.ts`** — Plan 05-02 covers PREFIX/API_BASE/APP_BASE compute + crossHubSearch absolute path override.
- [ ] **`frontend/src/branding/__tests__/registry.spec.ts`** — Plan 05-03 covers getBranding fallback + all 4 hub config schema.
- [ ] **`frontend/src/pages/__tests__/Login.spec.tsx`** — Plan 05-04 covers useEffect mount redirect + branding render.
- [ ] **`frontend/src/__tests__/Layout.spec.tsx`** — Plan 05-04 covers Layout title + logo render from getBranding(CURRENT_HUB).

**Alternative nếu Wave 0 SKIP vitest setup:** Plan 05-02/03/04 chỉ `tsc --noEmit` lint + manual visual inspect. Trade-off: R-V3-2 mitigation yếu — chỉ phụ thuộc D4 manual smoke checklist. Recommended **DO Wave 0 vitest setup** — effort tăng ~30-60min/plan nhưng R-V3-2 HIGH risk justify.

---

## Plan Decomposition Hint (đã consolidated trong Section 11 trên)

---

## Files to create/modify list

### NEW files (Phase 5 ship)

- `Hub_All/frontend/src/branding/index.ts` — Glob registry + `getBranding()` helper + `BrandingConfig` type
- `Hub_All/frontend/src/branding/central/index.ts` — Medinet gốc (indigo `#6366f1`)
- `Hub_All/frontend/src/branding/yte/index.ts` — Hub Y tế (emerald `#10b981`)
- `Hub_All/frontend/src/branding/duoc/index.ts` — Hub Dược (sky `#0ea5e9`)
- `Hub_All/frontend/src/branding/hcns/index.ts` — Hub HCNS (amber `#f59e0b`)
- `Hub_All/frontend/public/branding/central/logo.svg` — Placeholder M2 Medinet
- `Hub_All/frontend/public/branding/yte/logo.svg` — Placeholder yte
- `Hub_All/frontend/public/branding/duoc/logo.svg` — Placeholder duoc
- `Hub_All/frontend/public/branding/hcns/logo.svg` — Placeholder hcns
- `Hub_All/frontend/src/services/__tests__/api.spec.ts` — Unit test prefix detect (Wave 0 + Plan 05-02)
- `Hub_All/frontend/src/branding/__tests__/registry.spec.ts` — Unit test getBranding (Plan 05-03)
- `Hub_All/frontend/src/pages/__tests__/Login.spec.tsx` — Unit test Login redirect + branding (Plan 05-04)
- `Hub_All/frontend/src/__tests__/Layout.spec.tsx` — Unit test Layout branding (Plan 05-04)
- `Hub_All/frontend/vitest.config.ts` — Vitest config (Wave 0)
- `Hub_All/frontend/src/test-setup.ts` — jsdom + RTL setup (Wave 0)
- `Hub_All/.planning/phases/05-reverse-proxy-frontend-subpath/05-{01..06}-PLAN.md` — Plans 6 file
- `Hub_All/.planning/phases/05-reverse-proxy-frontend-subpath/05-{01..06}-SUMMARY.md` — Plan summaries

### MODIFIED files (Phase 5 edit)

- `Hub_All/Caddyfile` — ADD `{$WIKI_PUBLIC_DOMAIN}` server block parallel với MCP block
- `Hub_All/docker-compose.yml` — Caddy service ADD WIKI_PUBLIC_DOMAIN + HUBS_ALLOWLIST_REGEX env + `./frontend/dist:/srv/wiki/dist:ro` volume + `depends_on: python-api-central`
- `Hub_All/.env.example` — Document `WIKI_PUBLIC_DOMAIN`, `HUBS_ALLOWLIST`, `HUBS_ALLOWLIST_REGEX`
- `Hub_All/api/scripts/hub-add.sh` — APPEND step 8 + 9 (HUBS_ALLOWLIST sed update + Caddy reload + smoke)
- `Hub_All/frontend/src/services/api.ts` — REPLACE line 1-3 (hardcode hostname) với prefix detect block; ADD `crossHubSearch()` absolute override (Section 7 Option A)
- `Hub_All/frontend/src/App.tsx` — ADD `basename={APP_BASE}` cho `<BrowserRouter>`
- `Hub_All/frontend/src/pages/Login.tsx` — ADD `useEffect` mount redirect + render branding logo/title/tagline/themeColor + `useSearchParams` parse `?return=`
- `Hub_All/frontend/src/Layout.tsx` — REPLACE hardcode "Medinet Wiki" với `getBranding(CURRENT_HUB).title` + logo; menuItems filter central-only items (optional Plan 05-04)
- `Hub_All/frontend/package.json` — ADD vitest + @testing-library/react + jsdom devDeps (Wave 0)
- `Hub_All/frontend/tsconfig.json` — Verify `"types": ["vite/client"]` cho `import.meta.glob` generic
- `Hub_All/CLAUDE.md` — §3 D6 EXPIRED ở v3.0-05 + §6 Phase 5 progress row + Phase 5 pattern subsection
- `Hub_All/README.md` — NEW section "Reverse Proxy Subpath Deploy Notes (Phase 5 v3.0)"
- `Hub_All/.planning/STATE.md` — frontmatter Phase 5 + Current Position + Phase 5 Planning + Results Summary
- `Hub_All/.planning/REQUIREMENTS.md` — PROXY-01..04 mark [x] + NOTE Phase 5 closeout
- `Hub_All/.planning/ROADMAP.md` — Phase 5 status DONE + Progress table

### UNCHANGED (Phase 5 KHÔNG đụng)

- `Hub_All/api/app/auth/*.py` — Phase 3 SSO carry forward (JWT verify + JWKS + 307 redirect)
- `Hub_All/api/app/sync/*.py` — Phase 4 cross-hub data sync carry forward
- `Hub_All/api/migrations/versions/*.py` — KHÔNG DB schema change Phase 5
- `Hub_All/frontend/src/contexts/AuthContext.tsx` — Minimal touch (api.login/logout/me dùng API_BASE qua api.ts)
- `Hub_All/frontend/src/pages/Dashboard.tsx` + Documents + Search (đã có CrossHubSearch.tsx) + ... — KHÔNG touch unless smoke regression find regress
- `Hub_All/frontend/vite.config.ts` — Giữ `base: '/'` default (D-V3-Phase5-B2 LOCKED)
- `Hub_All/api/scripts/hub-init.sh` — Phase 1 carry forward (DB layer)

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Nginx reverse proxy + Let's Encrypt certbot cron | Caddy 2.x auto-TLS native | 2018+ (Caddy v2 stable) | Caddy single binary + Caddyfile syntax đơn giản hơn nginx; M2 carry forward |
| React Router v6 `BrowserRouter` | React Router v7 (current) | 2024 | API backward compat basename prop; package name vẫn `react-router-dom` cho v7 alias [VERIFIED: package.json line 43] |
| Vite 4 / 5 `import.meta.glob` lazy | Vite 6 `import.meta.glob` eager + lazy | 2024+ Vite 6 stable | Eager mode static imports — generic type inference; M2 Vite 6.2 đã có |
| Frontend per-domain build matrix | 1 build + runtime prefix detect | Standardized practice modern SPA | GA-V3-C khuyến nghị seed CONFIRMED; D-V3-Phase5-B1 LOCKED |
| Cookie domain `.medinet.vn` cross-subdomain SSO | localStorage same-origin subpath SSO | Phase 5 design choice | D-V3-Phase5-C2 LOCKED — phá subpath model nếu cookie domain |
| Backend HTML transparent 302 redirect | Backend 307 (RFC 7231) + FE-driven window.location | Phase 3 Plan 03-04 LOCKED + Phase 5 D-V3-Phase5-B4 | 307 preserve POST body modern browser standard; FE-driven cleaner UX |

**Deprecated/outdated:**
- M2 hardcode `${window.location.hostname}:8180` API URL → Phase 5 replace với prefix-aware `/${PREFIX}/api` relative. Reason: monolith single-port assumption KHÔNG scale multi-tenant.
- Caddy `replace_response` directive — NOT standard Caddy directive [VERIFIED: caddyserver.com/docs/caddyfile/directives no listing]. Implementation `window.__HUB_CONFIG__` injection chọn backend HTML render (FastAPI `GET /` endpoint serve index.html with `<script>` injected) hoặc Caddy `templates` directive (limited but standard).

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Caddy `reverse_proxy http://python-api-{re.hub_api.1}:8080` placeholder trong upstream hostname work — port STATIC | Pattern 1 Caddyfile | Plan execution Wave 1 phải fallback per-hub explicit handle_path blocks generated by sed; MEDIUM risk |
| A2 | `uri strip_prefix /{re.hub_api.1}` với regex capture placeholder work | Pattern 1 example | Plan execution Wave 1 phải verify; fallback dùng `handle_path /yte/*` per-hub explicit (manual list); MEDIUM risk |
| A3 | Caddy `templates` directive support env var injection cho HTML body rewrite | Pattern 1 + Pitfall 4 | Backend HTML render approach more reliable; LOW risk (alternative path exists) |
| A4 | Vite 6 `import.meta.glob<T>` generic inference work với `eager: true` + named export `branding` | Pattern 5 + Pitfall 8 | tsconfig.json `types: ["vite/client"]` cần verify; LOW risk (workaround manual narrow) |
| A5 | Backend FastAPI `GET /` mount conditional (central + hub con) render index.html dynamic — chưa implement Phase 5 cụ thể nào | Pitfall 4 Pattern | Plan execution claude's discretion chốt approach (Caddy templates vs backend serve); LOW risk |
| A6 | `frontend/dist/` sẽ built outside Docker (npm run build host) — Caddy volume mount `./frontend/dist:/srv/wiki/dist:ro` host filesystem | Architecture diagram + docker-compose example | Alternative: multi-stage Dockerfile build into caddy image; Plan execution chốt; LOW risk both work |
| A7 | localStorage same-origin scope share xuyên subpath same domain (RFC verified Web Storage API) | Section "Pattern 4" + Pitfall 6 | HIGH confidence — Web Storage API spec confirmed |
| A8 | React Router v7 backward compat v6 basename semantic | Pattern 3 | LOW risk — [CITED: reactrouter.com/api confirmed basename prop string type] |
| A9 | hub-add.sh `docker compose exec caddy caddy reload --config` chạy được trong Docker compose context (caddy container running) | Pattern hub-add.sh edit | LOW risk — Caddy support docker exec command; verify ở dry-run |
| A10 | Manual smoke 4 hub × 11 trang minimum required Phase 5 closeout (KHÔNG full skip pre-resolve) | Smoke Regression section | User decision claude-discretion ở Plan 05-06 checkpoint signal |

**Note:** Claims tagged `[ASSUMED]` trong text trên cũng tính. A1+A2 quan trọng nhất — plan execution Wave 1 phải verify trước khi commit.

---

## Open Questions

1. **Caddy `window.__HUB_CONFIG__` injection mechanism** — Recommended seed Caddy `templates` directive HOẶC backend `/index.html` render?
   - What we know: `replace_response` KHÔNG standard. `templates` directive support template engine với `{{env "VAR"}}` placeholder (theo Caddy docs reference).
   - What's unclear: `templates` có rewrite HTML response body từ `file_server` static file (read disk → execute template → response) hay chỉ làm `respond` inline?
   - Recommendation: **Backend FastAPI mount `GET /` central serve `index.html` template Jinja2 với `HUBS_ALLOWLIST` env**. Simpler + standard pattern + existing FastAPI/Jinja2 stack. Hub con `GET /` cũng mount same (FACTOR-01 universal endpoint). Caddy `handle /` fallback đi tới upstream `python-api-central` HOẶC `python-api-<hub>` tùy prefix.
   - Plan execution claude's discretion D-V3-Phase5.

2. **Frontend build pipeline integration với Docker compose** — `npm run build` host vs multi-stage Dockerfile?
   - What we know: docker-compose caddy volume mount `./frontend/dist:/srv/wiki/dist:ro` từ host (Plan 05-01 example).
   - What's unclear: Operator workflow — `make hub-add` không build FE; FE build độc lập (CI/CD hoặc manual `npm run build`).
   - Recommendation: Host build pattern Phase 5; document `make build-frontend` target trong `Hub_All/Makefile` chạy `cd frontend && npm install && npm run build`. CI/CD config defer v4.0.

3. **Manual smoke 4 hub × 11 trang full depth vs pre-resolved partial** — Closeout Plan 05-06 checkpoint signal expectation?
   - What we know: Plan 03-05 + 04-07 pre-resolved SKIP full E2E (defer Phase 7 MIGRATE-05).
   - What's unclear: PROXY-04 + R-V3-2 mitigation requires human UX verify branding 4 hub — KHÔNG defer toàn bộ.
   - Recommendation: Plan 05-06 task default "partial: branding + Login + Dashboard 4 hub PASS = approved" (minimum); 8 page khác có thể defer Phase 7 MIGRATE-05 nếu user resume signal `partial`.

4. **Caddy upstream placeholder semantic** — `http://python-api-{re.hub_api.1}:8080` actually work với Docker DNS resolution?
   - What we know: Docker compose service name → Docker DNS → container IP resolve. Placeholder evaluate at request time (Caddy substitute → DNS lookup `python-api-yte` → IP).
   - What's unclear: Caddy DNS cache TTL + behavior khi container restart (different IP).
   - Recommendation: Plan execution Wave 1 verify với 2 hub con — kill `python-api-yte` container, up new (different IP), curl `/yte/api/health` → expect Caddy re-resolve. Document fallback to `dynamic a` upstream module nếu native fail.

5. **Login.tsx multi-render flash UX** — Cross-prefix redirect cycle (mount hub con → useEffect → replace central → mount central → render branding) tạo perceptible flash?
   - What we know: `window.location.replace` cause full page reload — KHÔNG navigate flicker (whole page swap).
   - What's unclear: Perceived flash duration; first paint with hub con branding briefly before redirect fires.
   - Recommendation: Conditional render Login.tsx — `if (CURRENT_HUB !== 'central') return null` (KHÔNG render anything trong window between mount + redirect). useEffect race avoidance — chạy sync trong render body? KHÔNG (React rule — side effect chỉ useEffect/event). Accept flash 100-300ms acceptable UX trade-off.

6. **Hub con FE menuItems filter central-only items** — Hide vs show với 404 error page?
   - What we know: Layout.tsx menuItems hardcode 11 items M2. Hub con click `/yte/registry` → 404 envelope.
   - What's unclear: UX better — hide entirely (clean, less confusion) HOẶC show + render "feature not available in this hub" page (consistency).
   - Recommendation: Filter approach (hide). Less confusion. Implement `menuItems.filter(item => isCentralOnly(item.to) ? CURRENT_HUB === 'central' : true)` với `isCentralOnly()` helper (defer plan implementation).

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Docker | All deploy paths | Expected ✓ | (operator local) | — |
| Caddy 2-alpine | PROXY-01 + reload mechanism | ✓ pull on `docker compose pull` | 2.10+ (latest) | — |
| Node.js 18+ | Vite 6 build | Expected ✓ (frontend dev) | depends operator | `node --version` check |
| npm | `npm run build` | Expected ✓ | depends operator | — |
| curl | hub-add.sh smoke + manual verify | Expected ✓ on Unix | depends | — |
| jq | (optional debug Caddy admin API JSON) | Optional | — | python json.tool |
| openssl | Caddy TLS self-signed dev — auto-handled | ✓ via Caddy | embedded | — |

**Missing dependencies với no fallback:** None — Phase 5 dùng stack đã có sẵn (Docker + Caddy + Node + npm).

**Missing dependencies với fallback:**
- vitest (Wave 0 NEW dev dep) — Fallback: skip frontend unit test, dùng `tsc --noEmit` lint only + manual smoke. R-V3-2 mitigation weaker.

---

## Security Domain

`security_enforcement` không explicit set trong config.json — treat as enabled by default. Include section per template.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V1 Architecture | yes | Caddy reverse proxy decouple TLS from app; M2 Phase 8.3 verified |
| V2 Authentication | partial | Phase 3 carry forward (JWT RS256 + JWKSCache + Redis blacklist); Phase 5 KHÔNG đụng |
| V3 Session Management | partial | M2 carry forward localStorage + refresh token rotation Phase 3 Plan 03-04; XSS risk accept defer v4.0 HARD-V4-05 |
| V4 Access Control | yes | RBAC carry forward Phase 3 SSO-04 E4 reinforced 3-layer; Phase 5 KHÔNG đụng |
| V5 Input Validation | partial | URL prefix validate KNOWN_HUBS allowlist + Caddy regex match prevent path traversal |
| V6 Cryptography | yes | Caddy auto-TLS ACME (Let's Encrypt prod / self-signed dev); JWT crypto Phase 3 carry forward |
| V7 Error Handling | yes | Envelope shape `{success:false,data:null,error:{code,message},meta:null}` carry forward M2; 404 wrap Plan 02-03 Rule 2 Starlette handler carry forward |
| V8 Data Protection | partial | localStorage XSS concern M2 carry forward; defer v4.0 httpOnly cookie |
| V9 Communications | yes | HTTPS enforce qua Caddy auto-TLS; HSTS header carry forward M2 Phase 8.3 |
| V10 Malicious Code | low | Static frontend build — no runtime code injection unless XSS via stored DB content (M2 risk carry forward) |
| V11 Business Logic | yes | Login redirect chain — verify no open redirect (only allow `?return=/<hub>` regex match KNOWN_HUBS) |
| V12 Files & Resources | yes | Caddy file_server serve `dist/` read-only + try_files prevent path traversal |
| V13 API & Web Services | yes | RESTful API qua Caddy reverse proxy carry forward |
| V14 Configuration | yes | Env-driven WIKI_PUBLIC_DOMAIN + HUBS_ALLOWLIST; .env.example document |

### Known Threat Patterns for Phase 5 stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Open redirect `?return=//evil.com/path` | Tampering | Login.tsx validate `returnHub` regex `^[a-z][a-z0-9_]{0,15}$` match Settings regex Plan 02-05 + `KNOWN_HUBS.includes(returnHub)` allowlist before `window.location.replace` |
| Path traversal `/yte/../api/system_settings` | Tampering | Caddy `path_regexp` strict match `^/(yte|duoc|hcns)/api/(.*)$` — `..` decoded by browser → Caddy normalize → no escape outside scope |
| XSS via branding config (untrusted SVG / title) | Tampering + Elevation | Branding static config compile-time only (KHÔNG runtime user input); SVG static file Caddy serve raw — KHÔNG eval inline JS |
| `window.__HUB_CONFIG__` injection from compromised backend | Tampering | Backend render serve same-origin trusted source; CSP header strict carry forward M2 (verify chính sách) |
| Login form same-origin CSRF | Tampering | M2 carry forward — JWT Bearer header (KHÔNG cookie auth) → no automatic CSRF risk |
| Caddy reload triggered by unauth user | Elevation | Caddy admin API port 2019 internal-only (KHÔNG expose host) — `docker compose exec caddy caddy reload` requires shell access to container |
| HUBS_ALLOWLIST env tampering qua override.yml | Tampering | hub-add.sh sed edit `.env` (gitignored); operator-owned; audit log defer Phase 6 |
| Sub-resource integrity for `/branding/*/logo.svg` | Tampering | Same-origin Caddy serve trusted source; KHÔNG cross-origin asset → no SRI needed |
| Hub con direct port access `localhost:8181/api/users` bypass Caddy | Elevation | M2 Phase 2 publish 8180-8183 for dev — Phase 5 retain for ops debug; prod operator firewall block external access ports 818x (Caddy 80/443 only public) |
| Refresh token replay after logout | Tampering | Phase 3 Plan 03-04 SSO-02 Redis blacklist `auth:blacklist:<jti>` cross-process — Phase 5 KHÔNG đụng |
| Static `dist/` asset cache invalidation | DoS | Vite asset filename hash (default) `index-abc123.js` — content-addressed; Caddy Cache-Control immutable headers (carry forward) |

**Security review checklist Phase 5:**
- [ ] Login.tsx `?return=` parse + validate KNOWN_HUBS allowlist
- [ ] Caddyfile path_regexp anchored `^` + `$` (prevent partial match attack)
- [ ] `window.__HUB_CONFIG__` JSON.stringify escape (backend render safe template)
- [ ] hub-add.sh sed edit `.env` atomic (tmp + mv pattern — Section "Code Examples")
- [ ] Caddy validate gate trước reload (avoid silent rollback to malicious config)
- [ ] Container `python-api-<hub>` direct ports 818x firewall ops (prod readme note)

---

## Sources

### Primary (HIGH confidence)

- [Caddy `path_regexp` matcher](https://caddyserver.com/docs/caddyfile/matchers#path-regexp) — Verified regex named capture group `{re.<name>.<group>}` placeholder syntax
- [Caddy `handle_path` directive](https://caddyserver.com/docs/caddyfile/directives/handle_path) — Verified prefix strip semantic + comparison `uri strip_prefix` equivalent
- [Caddy `handle` directive](https://caddyserver.com/docs/caddyfile/directives/handle) — Verified mutually-exclusive group + auto-sort by matcher specificity
- [Caddy `file_server` directive](https://caddyserver.com/docs/caddyfile/directives/file_server) — Verified SPA fallback pattern với `try_files`
- [Caddy admin API `POST /load`](https://caddyserver.com/docs/api) — Verified atomic config swap + rollback on validate fail
- [Caddy Caddyfile concepts (env vars)](https://caddyserver.com/docs/caddyfile/concepts) — Verified `{$VAR:default}` syntax + parse-time substitution
- [React Router v7 BrowserRouter API](https://reactrouter.com/api/declarative-routers/BrowserRouter) — Verified basename prop signature
- [Vite `import.meta.glob`](https://vite.dev/guide/features.html) — Verified eager mode TypeScript signature + static import transform
- [Vite `base` config option](https://vite.dev/config/shared-options.html) — Verified `base='/'` default + asset URL behavior
- [MDN HTTP 307 Temporary Redirect](https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/307) — Verified method + body preservation + fetch `redirect:'follow'` behavior
- [RFC 7231 §6.4.7 Temporary Redirect](https://datatracker.ietf.org/doc/html/rfc7231#section-6.4.7) — Original spec POST body preserve

### Secondary (MEDIUM confidence)

- Project canonical refs:
  - `Hub_All/.planning/phases/05-reverse-proxy-frontend-subpath/05-CONTEXT.md` — 16 D-V3-Phase5 LOCKED decisions
  - `Hub_All/.planning/phases/03-auth-sso-hub-ids-jwt/03-04-PLAN.md` + SUMMARY — 307 redirect impl detail
  - `Hub_All/.planning/phases/04-cross-hub-data-sync/04-CONTEXT.md` D-V3-Phase4-D3 — hub con strip /api/search/cross-hub
  - `Hub_All/CLAUDE.md` §6 — Phase progress + previous phase patterns
  - `Hub_All/Caddyfile` — Existing MCP block pattern
  - `Hub_All/docker-compose.yml` line 271-286 — Caddy service definition
  - `Hub_All/api/scripts/hub-add.sh` — FACTOR-04 7-step pipeline (Phase 5 extend step 8+9)
  - `Hub_All/frontend/src/services/api.ts` — M2 APIClient class shape
  - `Hub_All/frontend/src/App.tsx` — `<BrowserRouter>` current
  - `Hub_All/frontend/src/pages/Login.tsx` + Layout.tsx — render shells
  - `Hub_All/frontend/package.json` — react-router-dom@^7.14.0 + vite@^6.2.0 + react@^19 verified

### Tertiary (LOW confidence — needs validation at plan execution)

- A1+A2 assumptions Caddy upstream placeholder + uri strip_prefix với regex capture group — verify ở Plan 05-01 Wave 1 smoke test
- A3 Caddy `templates` directive support env interpolation cho HTML body — verify nếu chọn Caddy templates approach (alternative: backend HTML render)
- Manual smoke 4 hub × 11 trang full vs partial defer Phase 7 — user decision pending

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — Caddy + Vite + React Router docs verified; M2 carry forward known stack
- Architecture: HIGH — Caddyfile pattern Phase 8.3 carry forward; frontend prefix detect explicit D-V3-Phase5 LOCKED
- Login redirect SSO chain: HIGH — Phase 3 Plan 03-04 + RFC 7231 + MDN docs verified
- Branding registry: HIGH — Vite import.meta.glob eager docs verified + 4 hub schema simple
- hub-add.sh extension: MEDIUM — bash + Caddy admin API verified; idempotency claims need dry-run test
- Caddy regex placeholder upstream: MEDIUM — assumption A1+A2 needs Wave 1 verify
- Smoke regression strategy: MEDIUM — pattern carry forward Phase 3+4 but Phase 5 D-V3-Phase5-D4 chốt FE/UX human verify
- Cross-hub UI redirect handling: HIGH — Option A frontend absolute path recommended (clear semantic)
- Security domain: MEDIUM — ASVS mapping standard; Phase 5 specific threats identified

**Research date:** 2026-05-22

**Valid until:** 2026-06-22 (30 days — Caddy + Vite + React Router stable; React Router v7 minor versions có thể release nhưng basename API stable per docs)

---

## RESEARCH COMPLETE
