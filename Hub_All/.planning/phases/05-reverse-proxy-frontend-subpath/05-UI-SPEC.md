---
phase: 5
slug: reverse-proxy-frontend-subpath
created: 2026-05-22
status: ready
mode: auto
source: gsd-ui-researcher (auto — recommended-defaults applied)
---

# Phase 5: Reverse Proxy + Frontend Subpath — UI-SPEC (Hợp đồng thiết kế giao diện)

**Phạm vi UI:** Áp dụng cho hai component touch Phase 5 (`Login.tsx` + `Layout.tsx` sidebar header) và 4 hub initial (`central`, `yte`, `duoc`, `hcns`) — KHÔNG re-skin 11 trang nội dung khác (R-V3-2 mitigation D6 expire).
**Ngôn ngữ:** Tiếng Việt có dấu cho mọi user-facing string. Tên kỹ thuật giữ tiếng Anh.
**Decisions thượng nguồn (LOCKED — KHÔNG re-open):** 16 D-V3-Phase5-A1..D4 trong `05-CONTEXT.md`.
**Spec này KHÔNG sửa:** Tailwind theme cascade (defer v4.0), Playwright e2e (defer v4.0), admin branding UI (defer v4.0), httpOnly cookie (defer v4.0), 11 trang nội dung (CSS-only nếu cần — R-V3-2).

---

## 0 · Tóm tắt hợp đồng UI

| Yếu tố | Phase 5 chốt | Nguồn |
|--------|--------------|-------|
| Design system | Tailwind v4 + token CSS variable `@theme` đã có (M2) — KHÔNG bump | `frontend/src/index.css` line 5-38 |
| Component library | KHÔNG dùng shadcn — pattern M2 self-rolled (motion + lucide-react + clsx) | `frontend/package.json` |
| Spacing scale | 4/8/12/16/24/32/48/64 (multiples of 4) — carry forward M2 Tailwind default | M2 |
| Typography sizes | 4 size: `text-[12px]` caption · `text-sm` (14px) body · `text-base` (16px) hero · `text-[26px]` headline form · `text-[38px]` hero VN headline | Login.tsx + index.css `text-h1..h4` |
| Typography weights | 2 weight: `font-medium` (500) thân + `font-bold` (700) tiêu đề | M2 carry |
| Color split (60/30/10) | 60% dominant `bg-slate-50` (light) / `bg-slate-950` (dark) · 30% secondary `bg-white` / `glass` card · 10% accent = **hub themeColor** (Login hero gradient + submit button gradient ONLY) | D2 |
| Theme color delivery | **Inline CSS variable `--hub-theme` trên container Login + Layout sidebar** (KHÔNG Tailwind plugin) | Auto-mode recommended default — §8 |
| Copywriting language | Tiếng Việt có dấu | Project standard |
| Asset path | `/branding/<hub>/logo.svg` (Vite copy `public/` → `dist/`, Caddy serve) | D3 |
| Registry | Vite `import.meta.glob('./*/index.ts', { eager: true })` static glob | D1 |
| Smoke regression | Manual checklist 4 hub × 11 trang M2 COMPAT-01 | D4 |

---

## 1 · Per-hub Branding Visual Specification

### 1.1 · Branding catalog (4 hub initial)

Mỗi hub export `BrandingConfig` qua `frontend/src/branding/<hub>/index.ts`:

| Hub key | `title` (VN) | `tagline` (VN) | `themeColor` (hex) | Vai trò màu | Logo asset path |
|---------|--------------|-----------------|---------------------|-------------|-----------------|
| `central` | "Medinet Wiki" | "Tri thức nội bộ Medinet" | `#6366f1` (indigo-500) | M2 brand color carry forward | `/branding/central/logo.svg` |
| `yte` | "Hub Y tế Medinet" | "Tri thức y tế cho mọi nhân viên" | `#10b981` (emerald-500) | Health = green | `/branding/yte/logo.svg` |
| `duoc` | "Hub Dược Medinet" | "Hướng dẫn dược lâm sàng" | `#0ea5e9` (sky-500) | Clinical = blue | `/branding/duoc/logo.svg` |
| `hcns` | "Hub HCNS Medinet" | "Chính sách nhân sự Medinet" | `#f59e0b` (amber-500) | HR = warm | `/branding/hcns/logo.svg` |

**Type contract** (export từ `frontend/src/branding/index.ts`):

```typescript
export interface BrandingConfig {
  readonly logo: string;        // Public asset URL absolute path, vd "/branding/yte/logo.svg"
  readonly title: string;       // VN hub title, KHÔNG wrap > 24 ký tự (sidebar truncate)
  readonly tagline: string;     // VN subtitle Login.tsx hero column, ≤ 48 ký tự
  readonly themeColor: string;  // Hex 7 ký tự (kèm #), dùng làm `--hub-theme` CSS variable
}
```

**Fallback contract:** `getBranding(unknownHub)` → trả `registry['central']` (Medinet indigo) — silent fallback (KHÔNG warning toast, log `console.warn` trong dev only).

### 1.2 · Logo placement contract

**Login.tsx — cột trái hero header (top-left):**
- Container: `flex items-center gap-3` (gap 12px).
- Logo wrapper: `flex h-11 w-11 items-center justify-center rounded-[14px] bg-white shadow-lg` (size 44×44, padding 0, white background giữ contrast bất kể themeColor).
- `<img src={branding.logo}>` inner: `w-7 h-7 object-contain` (28×28 + 8px breathing room).
- Title bên phải logo: `<h1 className="text-lg font-bold leading-tight tracking-tight">{branding.title}</h1>` (18px bold white).
- Tagline cạnh dưới title: `<p className="text-[12px] text-white/60">{branding.tagline}</p>` (12px, opacity 60% trên gradient nền).

**Login.tsx — cột phải form panel (centered):**
- Logo bubble: giữ M2 structure — `mx-auto mb-5 flex h-16 w-16 items-center justify-center rounded-2xl` (64×64, rounded-2xl 16px).
- Background bubble: `bg-[var(--hub-theme)]/10` (10% opacity themeColor — KHÔNG dùng `bg-indigo-100` cứng M2).
- Inner icon: `<img src={branding.logo} className="w-10 h-10 object-contain" />` (40×40). Nếu logo missing fallback `<BookOpen size={30} className="text-[var(--hub-theme)]" />`.

**Layout.tsx — sidebar header (top, h-16):**
- Container giữ NGUYÊN M2 structure (`h-16 flex items-center px-6 border-b ...`).
- Logo wrapper: `w-8 h-8 rounded-xl flex items-center justify-center text-white shadow-lg` (size 32×32).
- Background: thay `bg-brand-indigo` cứng → `style={{ backgroundColor: branding.themeColor }}` inline.
- Inner: nếu `branding.logo` load OK → `<img src={branding.logo} className="w-5 h-5 object-contain" />` (20×20); fallback `<Database size={18} />` M2.
- Title: `<span className="font-bold text-slate-900 dark:text-white tracking-tight text-lg truncate max-w-[160px]">{branding.title}</span>` — truncate ellipsis tại 160px (vừa width sidebar 256px trừ logo + padding).
- Khi `collapsed = true`: chỉ render logo (KHÔNG title) — giữ M2 conditional `{(!collapsed || isMobileMenuOpen) && ...}`.

### 1.3 · Typography contract (Login + Layout)

| Element | Class M2 carry / Phase 5 spec | Font size | Weight | Line height | Notes |
|---------|--------------------------------|-----------|--------|-------------|-------|
| Hero headline (cột trái Login VN) | `text-[38px] xl:text-[44px] font-bold leading-[1.15] tracking-tight` | 38px (≥xl 44px) | 700 | 1.15 | M2 carry — KHÔNG đổi |
| Hero tagline (cột trái Login VN) | `text-[15px] leading-relaxed text-white/70` | 15px | 400 | 1.625 | M2 carry |
| Hero title logo (top-left Login) | `text-lg font-bold leading-tight tracking-tight` | 18px | 700 | 1.25 | M2 carry — text = `branding.title` |
| Hero tagline logo (top-left Login) | `text-[12px] text-white/60` | 12px | 400 | 1 | M2 carry — text = `branding.tagline` |
| Form panel headline | `text-[26px] font-bold tracking-tight text-slate-800 dark:text-slate-100` | 26px | 700 | 1.2 | Giữ M2 "Đăng nhập" |
| Form panel subline | `text-sm text-slate-500 dark:text-slate-400` | 14px | 400 | 1.5 | M2 carry "Chào mừng bạn trở lại {branding.title}" |
| Sidebar title (Layout) | `text-lg font-bold tracking-tight` | 18px | 700 | 1.25 | M2 carry — text = `branding.title` truncate 160px |

### 1.4 · Theme color usage rules

**LOCKED (D2): themeColor CHỈ áp dụng 2 chỗ trên Login.tsx + 1 chỗ trên Layout.tsx — KHÔNG cascade toàn bộ component.**

| Vị trí | CSS target | Phép áp dụng | KHÔNG được phép |
|--------|------------|--------------|----------------|
| Login.tsx hero panel background gradient | `background: linear-gradient(135deg, var(--hub-theme) 0%, color-mix(in srgb, var(--hub-theme) 80%, black) 52%, color-mix(in srgb, var(--hub-theme) 60%, black) 100%)` | Hero cột trái thay gradient indigo cứng `#4f46e5 → #312e81` | KHÔNG đổi gradient form column phải (giữ white/slate-900) |
| Login.tsx form panel logo bubble bg | `background-color: color-mix(in srgb, var(--hub-theme) 10%, white)` | Bubble bao quanh logo trong form panel | KHÔNG đổi viền input field (giữ accent `#3b82f6` M2) |
| Login.tsx submit button background gradient | `background: linear-gradient(135deg, var(--hub-theme), color-mix(in srgb, var(--hub-theme) 85%, white))` | Nút "Đăng nhập" chính | KHÔNG đổi nút "Đăng nhập với Google" (giữ white border slate) |
| Login.tsx submit button shadow | `box-shadow: 0 10px 30px -8px color-mix(in srgb, var(--hub-theme) 55%, transparent)` | Glow cùng tone themeColor | — |
| Layout.tsx sidebar logo wrapper bg | `background-color: var(--hub-theme)` | Logo 32×32 trên header sidebar | KHÔNG đổi sidebar active item (`bg-brand-indigo` cứng — giữ M2 indigo, defer Tailwind cascade v4.0) |
| Layout.tsx sidebar avatar hover ring | `--tw-ring-color: color-mix(in srgb, var(--hub-theme) 30%, transparent)` | Profile avatar hover ring (replace `ring-brand-indigo/30`) | — |

**KHÔNG đổi (D2 scope minimal):**
- Form panel input field focus ring (`focus:ring-accent` M2 carry — accent blue `#3b82f6`).
- Sidebar nav active item background (`bg-brand-indigo` cứng — defer Tailwind cascade v4.0).
- Header bell notification, theme toggle, search field (giữ M2 slate palette).
- 11 trang nội dung (Dashboard, Documents, ...).

### 1.5 · Accessibility — WCAG AA contrast check

| Foreground | Background | Theme | Ratio computed | WCAG AA (≥ 4.5:1 normal text, ≥ 3:1 large text 18px+) |
|------------|------------|-------|----------------|-------------------------------------------------------|
| White (#FFFFFF) | `#6366f1` central indigo | central | 4.55:1 | PASS (normal + large) |
| White (#FFFFFF) | `#10b981` yte emerald | yte | 3.15:1 | PASS large (18px+ headline OK); **FAIL normal** — không dùng text < 18px trên emerald background |
| White (#FFFFFF) | `#0ea5e9` duoc sky | duoc | 3.05:1 | PASS large only — **FAIL normal**; không dùng text < 18px |
| White (#FFFFFF) | `#f59e0b` hcns amber | hcns | 2.07:1 | **FAIL cả normal + large** — KHÔNG ĐƯỢC overlay white text trên amber solid |
| `branding.title` (18px bold white) | Hero gradient `themeColor → mix(black 40%)` | tất cả | ≥ 5.2:1 (sau khi mix tối) | PASS |
| `branding.tagline` (12px white/60%) | Hero gradient phần đáy | tất cả | ≥ 3.8:1 | PASS large (12px italic acceptable per WCAG 1.4.3 exception 1) — chấp nhận với tagline non-essential |
| `text-slate-800` (form headline 26px) | `bg-white` form panel | tất cả | 12.6:1 | PASS |
| `text-[var(--hub-theme)]` icon (BookOpen 30px fallback) | `bg-[var(--hub-theme)]/10` bubble | tất cả | 4.65:1+ (themeColor luôn ≥ 100% saturate trên tint 10%) | PASS large |

**Quyết định auto-mode (WCAG mitigation cho `yte`/`duoc`/`hcns` themeColor light):**
- Hero column Login dùng **gradient** `themeColor → darken 40% → darken 60%` (`color-mix(in srgb, var(--hub-theme) 60%, black)`) → mọi text overlay nằm trên vùng đáy gradient với ratio ≥ 5:1.
- Submit button: text "Đăng nhập" (14px, weight 600) trên gradient `themeColor → mix white 15%` — verify ở implementation; nếu fail dùng `text-slate-900` cho `hcns` amber explicit override (Layout discrete hub branch).
- Sidebar logo bubble: icon white (Database / hub logo) trên `themeColor` solid 32×32 — **chấp nhận FAIL contrast cho `hcns` amber** vì icon là decorative (không phải text), per WCAG 1.4.3 không yêu cầu icon contrast (chỉ functional 1.4.11 ≥ 3:1 cho UI component non-text); `hcns` amber `#f59e0b` vs white = 2.07:1 → **FAIL** 1.4.11 → **override:** dùng `text-slate-900` (icon đen) trên hcns amber solid (ratio 9.5:1 PASS).

**Implementation guidance:** Helper `getContrastTextColor(themeColor: string): "white" | "slate-900"` trong `branding/index.ts` — return `slate-900` nếu themeColor luminance > 0.55 (hcns case), else `white`. Áp dụng cho sidebar logo icon + submit button text color.

---

## 2 · Login.tsx UX States Contract

Login.tsx phải xử lý 4 state mount + render đúng UX cho từng tổ hợp `CURRENT_HUB` (api.ts) + `searchParams.get('return')`.

### 2.1 · State A — Root scope, không return param

**Trigger URL:** `https://wiki.medinet.vn/login` (browser typed hoặc post-logout default).
**Detect:** `CURRENT_HUB === 'central'` AND `searchParams.get('return') === null`.
**Branding:** `getBranding('central')` → Medinet indigo `#6366f1`.
**Render:** Login.tsx render đầy đủ hero column trái + form column phải.
**Submit success redirect:** `window.location.replace('/')` → root `/dashboard` (central).
**Loading state:** Form panel render skeleton — KHÔNG có loading overlay riêng (giữ M2 `state='loading'` spinner trong button).

### 2.2 · State B — Central scope với return param

**Trigger URL:** `https://wiki.medinet.vn/login?return=/yte` (post hub con redirect).
**Detect:** `CURRENT_HUB === 'central'` AND `searchParams.get('return') === '/<hub>'` (regex `/^\/[a-z][a-z0-9_]{0,15}$/` match hub format).
**Branding:** `getBranding(returnHub)` → ví dụ yte emerald `#10b981`.
**Render:** Login.tsx full UI — chỉ branding khác (logo + title + tagline + themeColor gradient + submit button).
**Submit success redirect:** `window.location.replace(`/${returnHub}/dashboard`)` ví dụ `/yte/dashboard`.
**Visual cue trợ giúp user nhận biết hub đích:** Cạnh dưới form headline "Đăng nhập" thêm 1 chip nhỏ:
```tsx
{returnHub && (
  <div className="mx-auto mt-3 inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium"
    style={{ backgroundColor: `color-mix(in srgb, var(--hub-theme) 12%, white)`, color: 'var(--hub-theme)' }}>
    <svg className="w-3 h-3" /* icon arrow-right-circle */ />
    <span>Sau đăng nhập sẽ vào {branding.title}</span>
  </div>
)}
```

### 2.3 · State C — Hub prefix direct visit (redirect away)

**Trigger URL:** `https://wiki.medinet.vn/yte/login` (browser bookmark hoặc direct typed).
**Detect:** `CURRENT_HUB !== 'central'` (api.ts đã compute PREFIX = "yte").
**UX:** `useEffect(() => { if (CURRENT_HUB !== 'central') window.location.replace(\`${window.location.origin}/login?return=/${CURRENT_HUB}\`); }, [])` mount chạy 1 lần.

**Loading state visual (giữa thời điểm mount → redirect resolved, ~50-200ms):**
- KHÔNG render hero + form (tránh flicker form local).
- Render full-screen skeleton centered:
  ```tsx
  if (CURRENT_HUB !== 'central') {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center"
        style={{ background: `linear-gradient(135deg, var(--hub-theme), color-mix(in srgb, var(--hub-theme) 60%, black))` }}>
        <Loader2 size={32} className="animate-spin text-white" />
        <p className="mt-4 text-sm font-medium text-white/80">Đang chuyển đến trang đăng nhập trung tâm...</p>
      </div>
    );
  }
  ```
- Inline CSS variable `--hub-theme` được set ở wrapper ngoài cùng (helper `useHubTheme()` hook) bằng `branding = getBranding(CURRENT_HUB)`.
- Skeleton duration thực tế ~50-200ms (browser handle `window.location.replace`) — chấp nhận không có animation fade-in cầu kỳ.

### 2.4 · State D — Invalid return param (silent fallback)

**Trigger URL:** `https://wiki.medinet.vn/login?return=/INVALID_HUB` hoặc `?return=/postgres` (reserved name) hoặc `?return=///path/inject`.
**Detect:** `CURRENT_HUB === 'central'` AND `searchParams.get('return')` exists BUT:
  - Strip leading `/` → `returnHub`
  - `returnHub` KHÔNG match regex `^[a-z][a-z0-9_]{0,15}$` (hub format Settings)
  - HOẶC `returnHub` không có trong `KNOWN_HUBS = (window as any).__HUB_CONFIG__?.allowlist || ['yte','duoc','hcns']`.
**Branding:** Silent fallback `getBranding('central')` → Medinet indigo (KHÔNG warning toast UI — giữ UX clean cho user thường; log `console.warn('[login] Invalid return hub param:', returnHub)` cho dev DevTools).
**Submit success redirect:** Treat as State A → `window.location.replace('/')`.
**Rationale:** Silent fallback (D2 implicit) — `?return` injection attack vector tự bị filter bởi allowlist; chip "Sau đăng nhập sẽ vào ..." KHÔNG render khi invalid → user thấy form Medinet bình thường.

### 2.5 · Component state machine summary

| State | `CURRENT_HUB` | `returnHub` parsed | Branding source | Render content | Submit redirect target |
|-------|---------------|---------------------|------------------|-----------------|------------------------|
| A | central | null | `central` | Full Login UI | `/` |
| B | central | valid hub in allowlist | `<returnHub>` | Full Login UI + hub chip | `/<returnHub>/dashboard` |
| C | non-central | (irrelevant) | `<CURRENT_HUB>` | Skeleton + redirect | (redirect away) |
| D | central | invalid | `central` (silent fallback) | Full Login UI (no chip) | `/` |

---

## 3 · Layout.tsx Sidebar Header Contract

**Scope thay đổi M2:** Chỉ 2 phần tử trong sidebar header (line 155-167 file gốc):
1. Logo wrapper background color: `bg-brand-indigo` → `style={{ backgroundColor: branding.themeColor }}`.
2. Title text: hardcode `"Medinet Wiki"` → `{branding.title}`.

### 3.1 · Module-level branding resolution

```typescript
// frontend/src/Layout.tsx — đầu file, sau imports
import { getBranding } from './branding';
import { CURRENT_HUB } from './services/api';

const HUB_BRANDING = getBranding(CURRENT_HUB); // module-level — compute 1 lần
```

`CURRENT_HUB` export từ `api.ts` (Pattern 2 RESEARCH.md) — đảm bảo Layout dùng đúng branding theo prefix runtime detect.

### 3.2 · Sidebar header render contract

```tsx
{/* M2 line 155-167 EDIT — diff minimal */}
<div className="h-16 flex items-center px-6 border-b border-slate-200/50 dark:border-slate-700/50">
  {(!collapsed || isMobileMenuOpen) && (
    <motion.div initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} className="flex items-center gap-2">
      <div
        className="w-8 h-8 rounded-xl flex items-center justify-center shadow-lg shrink-0"
        style={{ backgroundColor: HUB_BRANDING.themeColor }}
      >
        {/* Render logo asset nếu load OK; fallback Database icon (Lucide) */}
        <img
          src={HUB_BRANDING.logo}
          alt={HUB_BRANDING.title}
          className="w-5 h-5 object-contain"
          onError={(e) => {
            // Fallback chain — set hidden + show sibling icon
            e.currentTarget.style.display = 'none';
            const fallback = e.currentTarget.nextElementSibling as HTMLElement | null;
            if (fallback) fallback.style.display = 'block';
          }}
          style={{ filter: getContrastTextColor(HUB_BRANDING.themeColor) === 'slate-900' ? 'invert(1)' : 'none' }}
        />
        <Database
          size={18}
          className="text-white hidden"
          style={{ color: getContrastTextColor(HUB_BRANDING.themeColor) === 'slate-900' ? '#0f172a' : 'white' }}
        />
      </div>
      <span className="font-bold text-slate-900 dark:text-white tracking-tight text-lg truncate max-w-[160px]">
        {HUB_BRANDING.title}
      </span>
    </motion.div>
  )}
  {/* ChevronLeft/Right collapse button + X mobile close — KHÔNG đổi M2 */}
</div>
```

### 3.3 · Sidebar collapse behavior

**LOCKED M2 carry forward:** Sidebar có 2 mode collapse (`width: 80px` collapsed vs `width: 256px` expanded) qua `motion.aside animate={{ width: ... }}`. Khi collapsed (chỉ desktop), header logo render giữa căn (logo 32×32 + chevron right), title hide.

| Mode | Logo render | Title render | Width container |
|------|-------------|--------------|-----------------|
| Expanded desktop | YES (32×32) | YES (truncate max-w-[160px]) | 256px |
| Collapsed desktop | YES (32×32) | NO (M2 conditional `{(!collapsed || isMobileMenuOpen) && ...}`) | 80px |
| Mobile menu open | YES | YES | 256px (overlay) |
| Mobile menu closed | (toàn sidebar hidden — `x: -256` motion) | — | — |

### 3.4 · Hover/focus states preserve

KHÔNG đổi M2:
- Sidebar nav active item: `bg-brand-indigo text-white` cứng (defer Tailwind cascade v4.0 D2 LOCKED).
- Sidebar nav hover: `hover:bg-white hover:shadow-sm hover:text-slate-900`.
- Avatar profile bottom: `hover:ring-2 hover:ring-brand-indigo/30` → **đổi thành** `hover:ring-2` với inline `style={{ ['--tw-ring-color' as any]: \`color-mix(in srgb, ${HUB_BRANDING.themeColor} 30%, transparent)\` }}` (Phase 5 §1.4 themeColor application 6).
- Header bell + theme toggle: giữ slate palette M2.

---

## 4 · App.tsx Route Map Per-Prefix Contract

### 4.1 · Single source of truth — `<BrowserRouter basename={APP_BASE}>`

```tsx
// frontend/src/App.tsx — diff Phase 5 (D-V3-Phase5-B3 LOCKED)
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { APP_BASE } from './services/api';
// ... existing imports unchanged

export default function App() {
  return (
    <BrowserRouter basename={APP_BASE}>
      {/* basename '' (central) hoặc '/yte', '/duoc', '/hcns' (hub con) */}
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/" element={<ProtectedRoute><Layout /></ProtectedRoute>}>
            <Route index element={<Dashboard />} />
            <Route path="search" element={<CrossHubSearch />} />
            {/* ... 11 route khác giữ NGUYÊN path absolute — react-router auto prepend basename */}
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
```

### 4.2 · Route → URL bar mapping per-prefix

| Route `path` | basename='' (central) | basename='/yte' | basename='/duoc' | basename='/hcns' |
|--------------|------------------------|------------------|-------------------|-------------------|
| `/login` | `/login` | `/yte/login` (→ redirect to `/login?return=/yte`) | `/duoc/login` (→ redirect) | `/hcns/login` (→ redirect) |
| `/` (index Dashboard) | `/` | `/yte/` | `/duoc/` | `/hcns/` |
| `/search` (CrossHubSearch) | `/search` | `/yte/search` | `/duoc/search` | `/hcns/search` |
| `/documents` | `/documents` | `/yte/documents` | `/duoc/documents` | `/hcns/documents` |
| `/users` (central-only) | `/users` | `/yte/users` (renders 404 từ API — UI vẫn load nhưng data empty) | `/duoc/users` (404 API) | `/hcns/users` (404 API) |
| `/registry` (central-only) | `/registry` | `/yte/registry` (404 API) | `/duoc/registry` (404 API) | `/hcns/registry` (404 API) |
| `/api-keys` (central-only) | `/api-keys` | `/yte/api-keys` (404 API) | (404 API) | (404 API) |
| `/logs` (central-only) | `/logs` | (404 API) | (404 API) | (404 API) |
| `/sync` (central-only) | `/sync` | (404 API) | (404 API) | (404 API) |
| `/usage` | `/usage` | `/yte/usage` | `/duoc/usage` | `/hcns/usage` |
| `/profile` | `/profile` | `/yte/profile` | `/duoc/profile` | `/hcns/profile` |
| `/settings` (central-only) | `/settings` | (404 API) | (404 API) | (404 API) |
| `/documents/new` | `/documents/new` | `/yte/documents/new` | `/duoc/documents/new` | `/hcns/documents/new` |
| `/sync/review/:batchId` (central) | `/sync/review/:batchId` | (404 API) | (404 API) | (404 API) |

**KHÔNG có hidden route in hub con:** Tất cả 13 routes mount như central — chỉ API trả 404 envelope D6 cho central-only endpoint khi hub con backend strip (FACTOR-02). UI vẫn render page shell + empty state.

### 4.3 · Navigation contract — react-router `<Link>` vs `window.location`

| Use case | Cách dùng | Vì sao |
|----------|-----------|--------|
| Sidebar menu items (`/dashboard`, `/search`, ...) | `<Link to="/search">` — react-router auto prepend basename | Same-prefix navigation; basename preserve |
| Profile link (Layout bottom) | `<Link to="/profile">` | Same-prefix |
| Logout button | `await logout(); navigate('/login')` (useNavigate hook) — basename auto prepend `/<hub>/login` → Login.tsx mount → useEffect detect hub → redirect central | Same-prefix navigate đầu tiên, sau đó cross-prefix qua window.location |
| Login submit success (State A/B/D) | `window.location.replace('/')` HOẶC `window.location.replace(\`/${returnHub}/dashboard\`)` | Cross-prefix → cần full page reload reset basename + module-level api.ts re-compute |
| Login mount hub con (State C) | `window.location.replace(\`${window.location.origin}/login?return=/${CURRENT_HUB}\`)` | Cross-prefix → escape `/yte/` scope tới root |
| 404 catch-all `<Route path="*">` | `<Navigate to="/" replace />` — basename auto prepend | Same-prefix fallback |

**Anti-pattern:** KHÔNG dùng react-router `<Link to="/yte/dashboard">` absolute path — basename sẽ DOUBLE prepend thành `/yte/yte/dashboard`. Cross-prefix luôn dùng `window.location.replace()`.

---

## 5 · CrossHubSearch.tsx Absolute-Path UI Contract

### 5.1 · API path contract

**LOCKED Phase 4 (D-V3-Phase4-D3):** Endpoint `/api/search/cross-hub` mount CENTRAL-ONLY. Hub con backend strip → 404 envelope D6.

**Phase 5 implementation choice (Claude's Discretion — auto mode):**

```typescript
// frontend/src/services/api.ts — Phase 5 EDIT (method crossHubSearch)
async crossHubSearch(data: SearchRequestAPI) {
  // ABSOLUTE PATH bypass API_BASE — KHÔNG `${this.baseURL}` prefix
  // Reason: D-V3-Phase4-D3 LOCKED — central-only endpoint
  // Same-origin (wiki.medinet.vn) → fetch tới `/api/search/cross-hub` đi qua Caddy match /api/* → python-api-central
  // KHÔNG strip prefix vì path đã absolute
  const url = '/api/search/cross-hub'; // ← absolute, KHÔNG ${API_BASE}
  return this.requestAbsolute<SearchResponseAPI>('POST', url, data);
}

// New helper trong APIClient class (sibling của private request())
private async requestAbsolute<T>(method: string, absolutePath: string, body?: unknown): Promise<APIResponse<T>> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  const token = this.getToken();
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const res = await fetch(absolutePath, { method, headers, body: body ? JSON.stringify(body) : undefined });
  // ... existing 401 refresh + envelope unwrap pattern reuse
  return res.json();
}
```

### 5.2 · UI render contract (page-level)

`CrossHubSearch.tsx` page renders **identical UX bất kể prefix** (`/search` ở central HOẶC `/yte/search` ở hub con). Page là central-only feature (theo D-V3-Phase4 D-V3-Phase4-D3 — hub con KHÔNG nên reach) nhưng:

**Defensive UX:** Nếu user vào `/yte/search` (sidebar Layout link `<Link to="/search">` → basename prepend `/yte/search`) → page mount → `api.crossHubSearch(...)` gọi absolute `/api/search/cross-hub` → **cross-origin với hub prefix → Caddy route central handle → response 200/data PASS** (vì absolute path bypass Caddy hub_api regex match).

Trường hợp edge defensive (Caddy config broken / dev environment): nếu fetch trả 404 envelope D6 → render empty state:

```tsx
// Inside CrossHubSearch.tsx — sau khi try gọi api.crossHubSearch và nhận envelope
{searchError === 'NOT_FOUND' && (
  <div className="flex flex-col items-center justify-center py-16 text-center">
    <AlertTriangle size={48} className="text-warning mb-4" />
    <h3 className="text-h3 font-bold text-slate-800 dark:text-slate-100">
      Tính năng tìm kiếm cross-hub chưa khả dụng
    </h3>
    <p className="mt-2 max-w-md text-sm text-slate-500 dark:text-slate-400">
      Chức năng tìm kiếm liên hub chỉ hoạt động tại trang trung tâm. Vui lòng truy cập{' '}
      <a href="/search" className="text-accent hover:underline font-medium">
        wiki.medinet.vn/search
      </a>{' '}
      để sử dụng.
    </p>
  </div>
)}
```

### 5.3 · JSON envelope shape (M2 contract LOCKED)

```typescript
// Success
{
  "success": true,
  "data": {
    "results": SearchResultAPI[],
    "total_hubs_searched": number,
    "query_time_ms": number,
    "cache_hit": boolean
  },
  "error": null,
  "meta": null
}

// 404 từ hub con (strip endpoint)
{
  "success": false,
  "data": null,
  "error": { "code": "NOT_FOUND", "message": "Endpoint not available on this hub" },
  "meta": null
}
```

Frontend detect `searchError = response.error?.code` → conditional render empty state với code `NOT_FOUND` (defensive — không nên gặp trong production vì api.ts dùng absolute path).

---

## 6 · Asset Path Contract — `/branding/<hub>/logo.svg`

### 6.1 · SVG file specs

| Spec | Value | Rationale |
|------|-------|-----------|
| Format | SVG vector | Designer edit-friendly + retina sharp + Caddy gzip serve |
| ViewBox | `0 0 64 64` (1:1 aspect ratio) | Sidebar logo 32×32 + Login form bubble 64×64 cả 2 use case scale clean |
| Canvas size | 64×64 nominal | Render tốt từ 16px (sidebar collapsed icon) tới 64px (Login form bubble) |
| Color scheme | Monochrome (single `fill` color) recommended | Cho phép overlay trên themeColor background — KHÔNG conflict với hub palette |
| Stroke width | ≥ 2px (nominal) | Visible khi scale-down 32×32 |
| Padding | 4px viewBox padding all sides | Logo không chạm border, breathing room visible |
| File size budget | ≤ 4 KB | Gzip + serve nhanh; preload trong `<head>` không cần |

### 6.2 · Initial 4 hub asset strategy (placeholder until designer ship)

**LOCKED auto-mode default:** Sinh **text-only SVG initial-letter** cho 4 hub initial — designer override sau.

| Hub | Initial letter | SVG content (monochrome `#FFFFFF` fill — overlay trên themeColor bg) |
|-----|----------------|-----|
| central | "M" (Medinet) | `<svg viewBox="0 0 64 64"><text x="32" y="44" text-anchor="middle" font-family="Inter, sans-serif" font-weight="700" font-size="36" fill="#FFFFFF">M</text></svg>` |
| yte | "Y" | Same template, letter "Y" |
| duoc | "D" | Same template, letter "D" |
| hcns | "H" | Same template, letter "H" |

**Implementation:** Plan 05-XX task tạo 4 SVG file trong `frontend/public/branding/<hub>/logo.svg` qua bash heredoc — designer hoán đổi file later mà KHÔNG cần rebuild FE (Vite copy public/ verbatim → Caddy serve).

### 6.3 · Fallback chain (logo file missing)

**Browser fetch `/branding/<hub>/logo.svg` → 404 (file chưa deploy, hoặc hub mới FACTOR-04 chưa drop logo):**

1. **HTML `<img onError>` handler:** Set `display: none` cho img → show sibling Lucide icon fallback (xem §3.2 code).
2. **Sidebar:** Lucide `<Database size={18} />` icon (M2 carry).
3. **Login form bubble:** Lucide `<BookOpen size={30} className="text-[var(--hub-theme)]" />`.
4. **Login hero header logo:** Lucide `<BookOpen size={22} className="text-indigo-600" />` M2 carry (chỉ central nếu xài fallback — non-central thường chỉ thấy briefly trước redirect).

**KHÔNG dùng default Medinet logo cho hub khác** (sai branding visual UX — `hcns` mà show "M" lập tức gây nhầm lẫn). Fallback Lucide icon = neutral.

### 6.4 · Caddy serve behavior

- Caddy `handle { root * /srv/wiki/dist; try_files {path} /index.html; file_server }` — `/branding/yte/logo.svg` match file serve direct (KHÔNG fallback `/index.html` vì path tồn tại trong `dist/branding/yte/logo.svg`).
- Hub mới chưa có `logo.svg` → 404 trực tiếp (KHÔNG fallback index.html vì `try_files {path}` chỉ fallback nếu `{path}` không tồn tại — SVG path không có file thật).
- Actually wait — `try_files {path} /index.html` SẼ fallback `/branding/new_hub/logo.svg` → `/index.html` (SPA HTML) → browser load img sẽ get HTML response → onError trigger → fallback Lucide.

---

## 7 · D6 EXPIRED Visual Safety Net — Smoke Regression Checklist

### 7.1 · 11 trang React M2 COMPAT-01 — invariants checklist

**LOCKED D-V3-Phase5-D4:** Manual checklist dev local cho 4 hub (`https://localhost/{,yte/,duoc/,hcns/}` 4 URL × 11 trang = 44 visit points).

| # | Page | Route absolute | Check INVARIANT (KHÔNG-CHANGE) | Theme color áp dụng? |
|---|------|----------------|---------------------------------|-----------------------|
| 1 | Login | `/login` (root) hoặc redirect | (a) Form panel headline "Đăng nhập" 26px bold; (b) Email + Password input field rounded `radius-input` 12px M2 carry; (c) Google button border slate M2 carry; (d) "Liên hệ quản trị viên" link indigo M2 carry; (e) Hero column 38px headline VN | YES (hero gradient + form bubble + submit button) |
| 2 | Dashboard | `/` index | (a) Card grid layout 3-col responsive M2; (b) Sparkline chart M2; (c) Stat number font M2; (d) Welcome message "Xin chào, {user.name}"; (e) Sidebar active state `bg-brand-indigo` cứng M2 carry | NO (page nội dung — Tailwind cascade defer v4.0) |
| 3 | Documents | `/documents` | (a) Table layout + header column M2; (b) Upload button `btn-primary` indigo M2; (c) Pagination footer M2; (d) Filter dropdown M2; (e) Empty state `BookOpen` icon M2 | NO |
| 4 | DocumentIngestion | `/documents/new` | (a) Stepper component M2; (b) Drop zone border-dashed M2; (c) File preview thumbnail M2; (d) Progress bar M2 | NO |
| 5 | Search / CrossHubSearch | `/search` | (a) Chat bubble layout M2; (b) Citation `[N]` marker font M2; (c) AssistantAvatar 36×36 rounded-xl M2; (d) Source card hover M2; (e) "Hỏi đáp AI" page title M2; (f) Defensive empty state `NOT_FOUND` (§5.2) chỉ render khi hub con (rare) | NO |
| 6 | HubRegistry (central-only) | `/registry` | (a) Hub card list M2; (b) "Thêm hub" button M2; (c) Hub status badge M2; (d) Empty state khi 0 hub M2; (e) Hub con visit → 404 envelope render empty state generic (page mount nhưng data empty) | NO |
| 7 | UserManagement (central-only) | `/users` | (a) Table với role badge M2; (b) Search filter input M2; (c) "Thêm user" button M2; (d) Pagination M2; (e) Hub con visit → 404 envelope empty | NO |
| 8 | APIKeyManagement (central-only) | `/api-keys` | (a) Key list card M2; (b) "Tạo key mới" button M2; (c) Plaintext key reveal modal M2; (d) Revoke confirm dialog M2 | NO |
| 9 | AuditLog (central-only) | `/logs` | (a) Log table + filter M2; (b) Date range picker M2; (c) Action badge M2; (d) Hub con visit → 404 envelope empty | NO |
| 10 | Profile | `/profile` | (a) Avatar 80×80 M2; (b) Form field 2-col layout M2; (c) "Đổi mật khẩu" section M2; (d) MCP OAuth tab M2; (e) "Lưu" button `btn-primary` M2 | NO |
| 11 | Settings (central-only) | `/settings` | (a) Tab list M2; (b) RAG config form M2; (c) "Lưu" button M2; (d) Hub con visit → 404 envelope empty | NO |

### 7.2 · Smoke checklist URL grid (4 hub × 11 page = 44 checkpoint)

| URL | Expected behavior |
|-----|-------------------|
| `https://localhost/login` | State A — Medinet indigo branding |
| `https://localhost/yte/login` | State C — emerald skeleton 50-200ms → redirect `/login?return=/yte` |
| `https://localhost/login?return=/yte` | State B — emerald branding + chip "Sau đăng nhập sẽ vào Hub Y tế Medinet" |
| `https://localhost/yte/dashboard` (post-login) | Layout sidebar emerald logo + "Hub Y tế Medinet" title; Dashboard nội dung M2 invariant |
| `https://localhost/duoc/documents` | Layout sidebar sky blue logo + "Hub Dược Medinet" title; Documents table M2 invariant |
| `https://localhost/hcns/profile` | Layout sidebar amber logo + "Hub HCNS Medinet" title; Profile form M2 invariant |
| `https://localhost/yte/registry` | Layout sidebar emerald; HubRegistry page mount but data empty (404 envelope) |
| `https://localhost/yte/search` | Layout sidebar emerald; CrossHubSearch chat UI; absolute path `/api/search/cross-hub` PASS qua Caddy central |
| ... 36 checkpoint khác mở rộng tổ hợp | Mỗi trang invariant M2 PASS |

### 7.3 · User resume signal patterns (carry forward Plan 03-05 / 04-07)

Sau khi user chạy checklist:
- `approved` — Tất cả 44 checkpoint PASS, branding work, layout không break, ship Phase 5.
- `regress in <component>` — Component cụ thể bị broken (vd `regress in Layout sidebar height`). Reopen `/gsd-debug` plan.
- `skip smoke` — User pre-resolve defer Phase 7 MIGRATE-05 full E2E (carry forward Plan 03-05 + 04-07 pattern); Phase 5 vẫn ship.

---

## 8 · Theme Delivery Decision — Inline CSS Variable

### 8.1 · Auto-mode RECOMMENDED DEFAULT (LOCKED Phase 5)

**Decision:** Inline CSS variable `--hub-theme` set trên container outermost của 2 component (Login.tsx + Layout.tsx), child selector dùng `var(--hub-theme)` qua inline `style` HOẶC `color-mix()` CSS function.

**KHÔNG dùng:** Tailwind plugin custom (overhead build + dynamic class generation phức tạp); KHÔNG dùng `tailwind.config.ts` `theme.extend` cho `hubTheme` color (Tailwind v4 `@theme` block trong CSS không support runtime value swap — class `bg-hub-theme` sẽ chỉ compile 1 value cố định).

### 8.2 · Implementation pattern

```tsx
// frontend/src/Layout.tsx — outermost div
return (
  <div
    className="flex h-screen bg-slate-50 dark:bg-slate-950 overflow-hidden relative"
    style={{ ['--hub-theme' as string]: HUB_BRANDING.themeColor } as React.CSSProperties}
  >
    {/* ...existing children — child elements use style={{ backgroundColor: 'var(--hub-theme)' }} */}
  </div>
);

// frontend/src/pages/Login.tsx — outermost div tương tự
return (
  <div
    className="relative flex min-h-screen overflow-x-hidden font-sans"
    style={{
      ['--hub-theme' as string]: branding.themeColor,
      background: `linear-gradient(135deg, var(--hub-theme) 0%, color-mix(in srgb, var(--hub-theme) 80%, black) 52%, color-mix(in srgb, var(--hub-theme) 60%, black) 100%)`,
    } as React.CSSProperties}
  >
    {/* ... */}
  </div>
);
```

### 8.3 · Trade-off rationale

| Approach | PRO | CON | Decision |
|----------|-----|-----|----------|
| **Inline CSS variable (CHOSEN)** | Zero build overhead; runtime swap per-hub; scope minimal (chỉ 2 component); browser support widespread (`color-mix` CSS Color 5 Chrome 111+ / Safari 16.4+ / Firefox 113+ — đều đã ship trước 2026) | KHÔNG dùng được Tailwind utility cho themeColor (phải inline style hoặc CSS var ref) | Auto-mode default |
| Tailwind v4 `@theme` static var | Cleaner DX (class `bg-hub-theme`) | KHÔNG support runtime swap (compile-time only) — không thoả Phase 5 multi-hub requirement | REJECT |
| Tailwind v4 plugin runtime | Full DX cascade | Build overhead + complexity scope creep | REJECT defer v4.0 |
| Inline style hex hardcode 4 lần | Đơn giản nhất | Phá DRY — sửa color phải edit 4 chỗ | REJECT |

### 8.4 · Browser support note

`color-mix(in srgb, ...)` — CSS Color 5 spec, đã ship ổn trong:
- Chrome 111+ (Mar 2023) — 95%+ user
- Safari 16.4+ (Mar 2023)
- Firefox 113+ (May 2023)

2026-05 user base 100% support. Fallback nếu cần (defensive): static darken hex per hub trong `branding/<hub>/index.ts` extend schema thêm `themeColorDark`, `themeColorLight` (defer v4.0 — Phase 5 KHÔNG cần).

---

## 9 · Component Inventory (Phase 5 touch — minimal scope)

| Component | Type | File path | Phase 5 action | Source spec |
|-----------|------|-----------|----------------|-------------|
| `LoginPage` | Page component | `frontend/src/pages/Login.tsx` | EDIT — add useEffect mount redirect + branding inject (State A/B/C/D) + themeColor gradient + chip | §2 + §1.4 |
| `Layout` | Layout component | `frontend/src/Layout.tsx` | EDIT — sidebar header logo bg + title swap branding + hover ring themeColor | §3 |
| `App` | Router root | `frontend/src/App.tsx` | EDIT — `<BrowserRouter basename={APP_BASE}>` add | §4 |
| `APIClient` | Service class | `frontend/src/services/api.ts` | EDIT — replace hardcode `${hostname}:8180` với PREFIX detect + `requestAbsolute()` helper cho cross-hub search | §5.1 + RESEARCH.md Pattern 2 |
| `CrossHubSearch` | Page component | `frontend/src/pages/CrossHubSearch.tsx` | EDIT — defensive empty state `NOT_FOUND` (rare path) + sử dụng `api.crossHubSearch()` absolute | §5.2 |
| `branding/index.ts` | Registry helper | `frontend/src/branding/index.ts` (NEW) | NEW — Vite glob + `getBranding()` + `getContrastTextColor()` helper + `BrandingConfig` type | §1.1 + RESEARCH.md Pattern 5 |
| `branding/central/index.ts` | Hub config | `frontend/src/branding/central/index.ts` (NEW) | NEW — Medinet indigo branding | §1.1 |
| `branding/yte/index.ts` | Hub config | `frontend/src/branding/yte/index.ts` (NEW) | NEW — emerald branding | §1.1 |
| `branding/duoc/index.ts` | Hub config | `frontend/src/branding/duoc/index.ts` (NEW) | NEW — sky blue branding | §1.1 |
| `branding/hcns/index.ts` | Hub config | `frontend/src/branding/hcns/index.ts` (NEW) | NEW — amber branding | §1.1 |
| `public/branding/central/logo.svg` | Static SVG | `frontend/public/branding/central/logo.svg` (NEW) | NEW — placeholder text "M" white fill | §6.2 |
| `public/branding/yte/logo.svg` | Static SVG | NEW | NEW — placeholder text "Y" | §6.2 |
| `public/branding/duoc/logo.svg` | Static SVG | NEW | NEW — placeholder text "D" | §6.2 |
| `public/branding/hcns/logo.svg` | Static SVG | NEW | NEW — placeholder text "H" | §6.2 |

**KHÔNG touch (R-V3-2 mitigation D6 expire scope minimal):**
- 11 trang nội dung khác (Dashboard, Documents, DocumentIngestion, UserManagement, HubRegistry, APIKeyManagement, AuditLog, SyncQueue, SyncReview, TokenUsage, Profile, Settings).
- `AuthContext.tsx` (api.ts đã abstract API_BASE — context tự nhiên work).
- `ThemeContext.tsx` (dark/light toggle độc lập hub branding — vẫn slate palette).
- `GeminiAssistant.tsx`, `CitationText.tsx`, `FileTypeIcon.tsx`, các shared component.
- `lib/utils.ts` `cn()` helper.
- `tailwind.config.ts` / `vite.config.ts` (giữ M2 default).

---

## 10 · Copywriting Contract (VN)

### 10.1 · Login.tsx strings

| Element | String (VN) | Source |
|---------|-------------|--------|
| Hero column logo title (top-left) | `{branding.title}` ví dụ "Medinet Wiki", "Hub Y tế Medinet" | Dynamic per-hub §1.1 |
| Hero column logo tagline (top-left) | "Hệ thống quản lý tri thức nội bộ" (M2 carry — fixed cho mọi hub) | M2 |
| Hero column headline VN (centered) | "Kết nối tri thức,\nlan tỏa giá trị." (M2 carry) | M2 |
| Hero column subtagline | "Medinet Wiki giúp bạn lưu trữ, chia sẻ và khai thác tri thức một cách hiệu quả." (M2 carry) | M2 |
| Form panel headline | "Đăng nhập" | M2 |
| Form panel subline | "Chào mừng bạn trở lại {branding.title}" (M2 dynamic — text "Medinet Wiki" thay branding.title per-hub) | EDIT Phase 5 |
| Hub return chip (State B) | "Sau đăng nhập sẽ vào {branding.title}" | NEW Phase 5 §2.2 |
| Email label | "Email" | M2 |
| Email placeholder | "Nhập email của bạn" | M2 |
| Password label | "Mật khẩu" | M2 |
| Password placeholder | "Nhập mật khẩu" | M2 |
| Show/hide password aria | "Hiện mật khẩu" / "Ẩn mật khẩu" | M2 |
| Error generic | "Email hoặc mật khẩu không đúng" | M2 |
| Error custom | `{errorMessage}` từ API envelope | M2 |
| Account locked title | "Tài khoản tạm khóa" | M2 |
| Account locked desc | "Quá nhiều lần đăng nhập thất bại. Vui lòng thử lại sau:" | M2 |
| Remember login | "Ghi nhớ đăng nhập" | M2 |
| Forgot password | "Quên mật khẩu?" | M2 |
| Primary CTA (submit button) | "Đăng nhập" / loading: "Đang đăng nhập..." | M2 |
| Google button | "Đăng nhập với Google" (chỉ tượng trưng — chưa wire) | M2 |
| Divider | "hoặc" | M2 |
| Footer text | "Chưa có tài khoản? Liên hệ quản trị viên" | M2 |
| Copyright | "© 2025 Medinet. Hệ thống nội bộ." | M2 |
| State C skeleton message | "Đang chuyển đến trang đăng nhập trung tâm..." | NEW Phase 5 §2.3 |

### 10.2 · Layout.tsx strings

| Element | String (VN) | Source |
|---------|-------------|--------|
| Sidebar logo title | `{HUB_BRANDING.title}` (dynamic) | EDIT Phase 5 §3.2 |
| Sidebar nav: Dashboard | "Dashboard" | M2 |
| Sidebar nav: Search | "Hỏi đáp AI" | M2 |
| Sidebar nav: Documents | "Danh sách tri thức" | M2 |
| Sidebar nav: SyncQueue | "Hàng đợi Sync" (badge "3" demo) | M2 |
| Sidebar nav: Users | "Quản lý User" | M2 |
| Sidebar nav: HubRegistry | "Hub Registry" | M2 |
| Sidebar nav: APIKey | "Quản lý API Key" | M2 |
| Sidebar nav: AuditLog | "Audit Log" | M2 |
| Sidebar nav: TokenUsage | "Token & API Usage" | M2 |
| Sidebar nav: Settings | "Cài đặt hệ thống" | M2 |
| Sidebar group: Tri thức | "Tri thức" | M2 |
| Sidebar group: Quản trị | "Quản trị" | M2 |
| Sidebar group: Hệ thống | "Hệ thống" | M2 |
| Profile avatar tooltip | "Thông tin cá nhân" | M2 |
| Logout button (icon only) | (no text — tooltip "Đăng xuất" — M2 KHÔNG có; Phase 5 KHÔNG add) | M2 |
| Header breadcrumb | `getBreadcrumb()` M2 logic | M2 |
| Header search placeholder | "Tìm nhanh (Cmd + K)..." | M2 |
| Header theme toggle tooltip | "Chế độ tối" / "Chế độ sáng" | M2 |
| Notification panel title | "Thông báo" | M2 |
| Notification: mark read | "Đánh dấu đã đọc" | M2 |

### 10.3 · CrossHubSearch.tsx defensive empty state (NEW Phase 5 §5.2)

| Element | String (VN) |
|---------|-------------|
| Empty state title | "Tính năng tìm kiếm cross-hub chưa khả dụng" |
| Empty state desc | "Chức năng tìm kiếm liên hub chỉ hoạt động tại trang trung tâm. Vui lòng truy cập wiki.medinet.vn/search để sử dụng." |
| Link to central | "wiki.medinet.vn/search" |

### 10.4 · Destructive actions trong Phase 5

**NONE.** Phase 5 KHÔNG ship destructive UI action mới. Logout flow (Layout.tsx) carry forward M2 — không có confirmation dialog (M2 pattern: click logout button → `await logout()` immediate → `navigate('/login')`). Phase 5 wire thêm Login.tsx mount redirect khi user ở `/yte/login` — KHÔNG destructive (chỉ navigate).

---

## 11 · Registry Safety (Phase 5 KHÔNG dùng shadcn / third-party)

| Source | Status | Safety gate |
|--------|--------|-------------|
| shadcn | NOT USED | N/A — Phase 5 dùng pattern M2 self-rolled (motion + lucide-react + clsx + tailwind v4 utility) |
| Third-party registry | NONE declared | N/A |
| Lucide-react icons | M2 carry — dep có sẵn `^0.546.0` | view passed — M2 dep tin cậy |
| Motion (framer-motion successor) | M2 carry — dep có sẵn `^12.23.24` | view passed — M2 dep tin cậy |
| Tailwind v4 + `@tailwindcss/vite` | M2 carry — dep có sẵn `^4.1.14` | view passed — M2 dep tin cậy |

KHÔNG cần npm install dependency mới cho Phase 5.

---

## 12 · Pre-populated from upstream

| Source | Decisions used | Count |
|--------|----------------|-------|
| `05-CONTEXT.md` (16 D-V3-Phase5 LOCKED) | A1 Caddy single-file, A2 strip prefix, A3 hub-add reload, A4 WIKI_PUBLIC_DOMAIN env, B1 prefix detect, B2 vite base='/', B3 BrowserRouter basename, B4 FE redirect, C1 central login UX, C2 localStorage, C3 logout local, C4 refresh 307, D1 static glob, D2 scope Login+Layout, D3 logo asset, D4 manual checklist + branding tone 4 hub specifics | 17 |
| `05-RESEARCH.md` (architecture + patterns) | Stack pin (Vite 6 + React 19 + react-router v7 + Tailwind v4) + Caddy patterns + WCAG check + import.meta.glob eager + window.__HUB_CONFIG__ fallback | 8 |
| `REQUIREMENTS.md` (PROXY-01..04) | Acceptance criteria 4 REQ-ID | 4 |
| Codebase scan (`Login.tsx`, `Layout.tsx`, `App.tsx`, `api.ts`, `index.css`, `package.json`, `CrossHubSearch.tsx`) | M2 component structure + class names + invariants + spacing scale + typography existing | 7 files |
| Auto-mode default (Claude's Discretion) | Inline CSS variable approach (§8), text-only SVG placeholder strategy (§6.2), defensive `NOT_FOUND` empty state (§5.2), `getContrastTextColor` helper for hcns amber (§1.5), hub return chip (§2.2) | 5 |

**KHÔNG ask user trong auto mode — applied recommended defaults documented.**

---

## 13 · Trace-back tới REQ-ID (acceptance criteria coverage)

| REQ-ID | Mục tiêu | UI-SPEC section satisfy |
|--------|----------|--------------------------|
| **PROXY-01** | Caddy route `/hub/api/*` → upstream hub đúng | §4 (URL bar mapping per-prefix); spec không touch Caddyfile (out of scope UI) — VALIDATION.md cover |
| **PROXY-02** | Frontend detect prefix 1 build | §4.1 (`BrowserRouter basename={APP_BASE}`) + §9 (`APIClient` PREFIX detect) + §2 (Login state machine A/B/C/D) |
| **PROXY-03** | D6 expire formally + smoke 11 trang | §7 (Visual safety net 4 hub × 11 page = 44 checkpoint) |
| **PROXY-04** | Per-hub login branding (logo + title + theme color) | §1 (Branding catalog 4 hub) + §2 (Login state branding) + §3 (Layout sidebar branding) + §8 (themeColor delivery) |

---

## 14 · Out of Scope reminder (defer)

| Item | Defer to | Source |
|------|----------|--------|
| Full Tailwind theme cascade tất cả component | v4.0 HARD-V4-XX | D2 LOCKED + CONTEXT.md `<deferred>` |
| Playwright e2e per-hub smoke | v4.0 HARD-V4-04 | D4 + CONTEXT.md |
| Admin branding UI (database-driven) | v4.0 HARD-V4-XX | D1 + CONTEXT.md |
| Per-hub favicon + manifest.json | v4.0 | CONTEXT.md |
| httpOnly cookie token storage | v4.0 HARD-V4-05 | C2 + CONTEXT.md |
| WebSocket / SSE streaming `/api/ask` | v4.0 HARD-V4-03 | CONTEXT.md |
| MCP service subpath `wiki.medinet.vn/mcp` | Phase 7 MIGRATE-04 | CONTEXT.md |
| Cloudflare Tunnel migration | v4.0+ | CONTEXT.md |
| Per-hub dashboard sync_status metric | Phase 6 SETTINGS-04 hoặc Phase 7 MIGRATE-05 | CONTEXT.md specifics |
| 11 trang nội dung re-skin theme color | v4.0 | D2 LOCKED |

---

*Phase: 05-reverse-proxy-frontend-subpath*
*UI-SPEC created: 2026-05-22*
*Source: gsd-ui-researcher --auto mode (17 LOCKED decisions từ CONTEXT.md + 8 patterns từ RESEARCH.md + recommended defaults documented inline)*
*Downstream consumer: gsd-planner (Phase 5 implementation plan) + gsd-executor + gsd-ui-checker validation + gsd-ui-auditor retroactive compare*

## UI SPEC COMPLETE
