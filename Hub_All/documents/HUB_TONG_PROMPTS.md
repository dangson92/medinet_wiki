# HUB TỔNG — wiki.medinet.vn — FRONTEND BUILD PROMPTS

> Dự án standalone: Hub Tổng (wiki.medinet.vn) — Admin Dashboard quản trị trung tâm Medinet Wiki.
> Đây là 1 trong 4 dự án frontend độc lập. Xây dựng hoàn chỉnh trước, sau đó mới làm 3 Hub Dự Án.

---

## THÔNG TIN DỰ ÁN

**Tên:** Medinet Wiki — Hub Tổng
**Domain:** wiki.medinet.vn
**Vai trò duy nhất:** Admin Hub Tổng (không có Viewer, không có Editor)
**Mục đích:** Quản trị toàn bộ hệ thống Wiki đa Hub — dashboard, quản lý user, Hub Registry, cross-hub search, duyệt Sync, Audit Log, MCP API Keys.

**Tech Stack:**
- React 18 + Vite 5 + TypeScript
- React Router v6 (client-side routing)
- Zustand (global state) + TanStack Query (server state / caching)
- TailwindCSS 3 + Lucide React (icons)
- Axios (HTTP client)
- date-fns (date formatting)
- Mock API: MSW (Mock Service Worker) hoặc custom mock layer

**Design Tokens:**
- Primary: indigo-600
- Background: slate-50
- Sidebar: white, border-r slate-200
- Accent: amber-500 (warnings), emerald-500 (success), red-500 (danger)

---

## MỤC LỤC

| # | Prompt | Trang/Module | Route |
|---|--------|-------------|-------|
| 0 | Project Setup | Khởi tạo dự án | — |
| 1 | UI Component Library | Components dùng chung | — |
| 2 | Auth & Login | Đăng nhập, JWT, bảo vệ route | /login |
| 3 | App Layout | Sidebar, Header, Notification | — |
| 4 | Dashboard | Tổng quan hệ thống | /dashboard |
| 5 | Quản lý User Hub Dự Án | CRUD user theo Hub | /users |
| 6 | Hub Registry | Quản lý danh sách Hub | /hub-registry |
| 7 | Cross-Hub Search | Tìm kiếm xuyên Hub | /search |
| 8 | Audit Log | Lịch sử hoạt động | /audit-log |
| 9 | Sync Batch Review | Duyệt nội dung sync từ Hub Dự Án | /sync-review |
| 10 | MCP API Key Management | Quản lý API key cho AI Agent | /settings/api-keys |
| 11 | Notification System | Thông báo realtime | — |
| 12 | Mock API & Data Layer | Toàn bộ mock endpoints + fixtures | — |

---

<a id="prompt-0"></a>
## PROMPT 0 — Project Setup

```
Khởi tạo dự án React standalone cho Medinet Wiki Hub Tổng (wiki.medinet.vn).
Đây là Admin Dashboard quản trị trung tâm — chỉ Admin Hub Tổng truy cập.

## Cấu trúc thư mục:
hub-tong/
├── public/
│   └── favicon.svg
├── src/
│   ├── assets/                # Logo, images
│   ├── components/            # Shared UI components
│   │   ├── ui/                # Primitive: Button, Input, Modal, Badge, Toast...
│   │   ├── layout/            # AppShell, Sidebar, Header, Breadcrumb
│   │   └── common/            # Domain-specific shared: SearchBar, StatCard...
│   ├── features/              # Feature modules (mỗi feature 1 folder)
│   │   ├── auth/              # Login, auth store, guards
│   │   ├── dashboard/         # Dashboard page
│   │   ├── users/             # Quản lý user Hub Dự Án
│   │   ├── hub-registry/      # Quản lý Hub
│   │   ├── search/            # Cross-hub search
│   │   ├── audit-log/         # Audit log
│   │   ├── sync-review/       # Duyệt Sync batch
│   │   ├── api-keys/          # MCP API key management
│   │   └── notifications/     # Notification system
│   ├── hooks/                 # Custom hooks dùng chung
│   ├── lib/                   # Utilities, helpers
│   │   ├── api.ts             # Axios instance + interceptors
│   │   ├── mock/              # Mock data + handlers
│   │   └── utils.ts           # Format date, slug, etc.
│   ├── stores/                # Zustand stores
│   ├── types/                 # TypeScript types/interfaces
│   ├── routes.tsx             # React Router config
│   ├── App.tsx
│   └── main.tsx
├── index.html
├── package.json
├── tsconfig.json
├── vite.config.ts
├── tailwind.config.ts
├── postcss.config.js
└── .env

## Dependencies:
react, react-dom, react-router-dom, zustand, @tanstack/react-query,
axios, tailwindcss, postcss, autoprefixer, lucide-react, date-fns,
@tiptap/react (cài sẵn, dùng sau), clsx, tailwind-merge

Dev: typescript, @types/react, @types/react-dom, vite, @vitejs/plugin-react,
eslint, prettier, msw

## .env:
VITE_APP_NAME=Medinet Wiki - Hub Tổng
VITE_API_BASE_URL=http://localhost:8080/api
VITE_MOCK_API=true

## Routing (/src/routes.tsx):
/login              → LoginPage (public)
/dashboard          → DashboardPage (protected, default redirect)
/users              → UserManagementPage
/hub-registry       → HubRegistryPage
/search             → CrossHubSearchPage
/audit-log          → AuditLogPage
/sync-review        → SyncBatchListPage
/sync-review/:id    → SyncBatchDetailPage
/settings/api-keys  → ApiKeyManagementPage
/403                → ForbiddenPage
/404                → NotFoundPage
/*                  → redirect /404

## Scripts:
pnpm dev   → Vite dev server port 3000
pnpm build → production build
pnpm preview → preview build

Tạo đầy đủ config, placeholder pages "Coming Soon" cho mỗi route, App.tsx với Router setup.
```

---

<a id="prompt-1"></a>
## PROMPT 1 — UI Component Library

```
Xây dựng UI Component Library tại src/components/ui/ cho dự án Hub Tổng (wiki.medinet.vn).
React 18 + TypeScript + TailwindCSS. Tất cả components phải responsive và accessible (WCAG AA).
Sử dụng clsx + tailwind-merge cho className composition.
Design: clean, professional admin dashboard. Primary color: indigo-600.

## Components cần xây dựng:

### 1. Button
- Variants: primary (indigo), secondary (gray), danger (red), ghost (transparent)
- Sizes: sm, md, lg
- States: default, hover, active, disabled, loading (spinner)
- Props: leftIcon?, rightIcon?, isLoading?, fullWidth?
- Ví dụ: <Button variant="primary" leftIcon={<Plus />}>Thêm Hub</Button>

### 2. Input
- Types: text, password (toggle show/hide), email, number
- States: default, focus, error, disabled
- Props: label?, error?, helperText?, leftIcon?, rightIcon?
- Ví dụ: <Input label="Email" error="Email không hợp lệ" leftIcon={<Mail />} />

### 3. Select
- Single select dropdown, searchable
- Props: label?, options[], placeholder?, error?, disabled?
- Keyboard navigation: arrow keys, enter, escape
- Ví dụ: <Select label="Hub" options={hubs} placeholder="Chọn Hub..." />

### 4. MultiSelect
- Tag-style multi select
- Props: label?, options[], selected[], onChange, placeholder?
- Selected items hiện dạng badges, click X để xóa
- Searchable input phía trên

### 5. TagInput
- Input cho tags, gõ Enter hoặc comma để thêm tag
- Autocomplete dropdown từ danh sách có sẵn
- Badges cho tags đã chọn, click X xóa

### 6. TextArea
- Auto-resize theo nội dung
- Props: label?, error?, rows?, maxLength? (hiện counter)

### 7. Badge
- Variants: default (gray), success (green), warning (amber), danger (red), info (blue), purple
- Sizes: sm, md
- Props: dot? (hiện dot tròn trước text)
- Ví dụ: <Badge variant="success">Active</Badge>

### 8. Modal
- Sizes: sm (400px), md (500px), lg (640px), xl (800px), full (90vw)
- Header (title + close X) + Body (scrollable) + Footer (action buttons)
- Close: ESC key, click overlay, click X
- Animate: fade in/out + scale
- Props: isOpen, onClose, title, size?, children, footer?

### 9. ConfirmDialog
- Extends Modal (size sm)
- Props: title, message, confirmLabel, cancelLabel, variant (danger | warning | info), onConfirm, onCancel
- Variant danger: confirm button màu đỏ
- Optional: input xác nhận (gõ lại tên để confirm)
- Ví dụ: <ConfirmDialog variant="danger" title="Xóa Hub?" message="Hành động không thể hoàn tác" />

### 10. DataTable
- Props: columns[], data[], isLoading?, emptyMessage?, pagination?, rowSelection?, onRowClick?
- Features:
  - Sortable columns (click header → asc/desc/none)
  - Pagination: prev/next, page numbers, page size selector (10/25/50)
  - Row selection: checkbox column, select all, selected count
  - Loading: skeleton rows
  - Empty: EmptyState component
  - Row actions: dropdown menu (three dots) hoặc inline buttons
- Responsive: horizontal scroll trên mobile

### 11. StatCard
- Props: icon, label, value (number/string), trend? ({ value: number, isUp: boolean }), color?
- Layout: icon trái, label + value phải, trend góc dưới
- Ví dụ: <StatCard icon={<FileText />} label="Tổng trang Wiki" value={270} trend={{ value: 12, isUp: true }} />

### 12. SearchBar
- Props: placeholder?, onSearch, isLoading?, defaultValue?
- Debounce 300ms
- Icon search trái, clear button (X) phải, loading spinner
- Enter hoặc debounce trigger onSearch

### 13. Toast / Toaster
- Global toast system (Zustand store hoặc context)
- Types: success (green), error (red), warning (amber), info (blue)
- Position: top-right
- Auto-dismiss: 5 giây (configurable)
- Stack multiple toasts
- API: toast.success("Đã lưu"), toast.error("Lỗi kết nối")

### 14. EmptyState
- Props: icon?, title, description?, action? ({ label, onClick })
- Center aligned, icon lớn mờ
- Ví dụ: <EmptyState icon={<Inbox />} title="Chưa có dữ liệu" action={{ label: "Thêm mới", onClick: ... }} />

### 15. LoadingSkeleton
- Variants: text (lines), card, table-row, stat-card
- Props: variant, count? (số lượng skeleton items)
- Animate pulse

### 16. Tabs
- Props: tabs[] ({ label, value, badge?, content }), defaultValue?
- Horizontal tabs, underline active
- Badge count trên tab (ví dụ: "Chờ duyệt (5)")

### 17. Timeline
- Props: items[] ({ time, user, action, description?, icon?, color? })
- Vertical timeline, dot + line
- Icon tùy loại (user, robot, sync...)

### 18. ProgressBar
- Props: value (0-100), label?, showPercent?, color?
- Hoặc: current + total → auto tính %
- Ví dụ: <ProgressBar current={5} total={12} label="5/12 trang đã xử lý" />

### 19. DateRangePicker
- 2 input (Từ ngày — Đến ngày) với date popup
- Props: from?, to?, onChange({ from, to })
- Quick presets: Hôm nay, 7 ngày, 30 ngày, Tháng này

### 20. Dropdown Menu
- Trigger element + menu panel (absolute positioned)
- Menu items: label, icon?, onClick, divider?, danger?
- Keyboard: arrow navigation, enter, escape
- Dùng cho: row actions, user menu

### 21. Tooltip
- Props: content, position (top/bottom/left/right), children (trigger)
- Delay 300ms show, instant hide

### 22. Avatar
- Props: name, src?, size (sm/md/lg)
- Fallback: 2 chữ cái đầu tên, background random color theo tên

Tất cả components export từ src/components/ui/index.ts.
Tạo 1 trang demo /dev/components (chỉ hiện ở dev mode) hiển thị tất cả components.
```

---

<a id="prompt-2"></a>
## PROMPT 2 — Auth & Login Page

```
Xây dựng hệ thống Authentication cho Hub Tổng (wiki.medinet.vn).
CHỈ Admin Hub Tổng mới đăng nhập được — không có Viewer, không có Đăng ký.

## Auth Store (src/stores/authStore.ts — Zustand):
interface AuthState {
  user: User | null;          // { id, name, email, role, avatar? }
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  loginAttempts: number;      // đếm số lần sai
  lockedUntil: Date | null;   // khóa 15 phút sau 5 lần sai
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  checkAuth: () => Promise<void>;
}

- Role duy nhất: "admin_hub_tong"
- Token lưu localStorage (mock), httpOnly cookie (production)
- JWT payload: { user_id, role: "admin_hub_tong", exp }

## Login Page (/login — src/features/auth/LoginPage.tsx):

### Layout:
- Full screen, centered card
- Background: gradient indigo-50 → slate-100
- Card trắng (max-w-md), shadow-xl, rounded-2xl

### Nội dung card:
- Logo Medinet (placeholder) + Tiêu đề: "Quản trị Medinet Wiki"
- Subtitle: "Đăng nhập vào hệ thống quản trị trung tâm"
- Form:
  - Input Email (icon Mail, type email, required)
  - Input Password (icon Lock, type password, toggle show/hide, required)
  - Checkbox "Ghi nhớ đăng nhập"
  - Button "Đăng nhập" (full width, primary, loading state khi submit)
- KHÔNG có link "Đăng ký" hay "Quên mật khẩu" (Admin tạo thủ công)
- Footer nhỏ: "© 2025 Medinet. Hệ thống nội bộ."

### Logic xử lý:
- Submit → gọi authStore.login(email, password)
- Thành công → redirect /dashboard
- Sai mật khẩu (< 5 lần): hiện error "Email hoặc mật khẩu không đúng" (shake animation trên form)
- Sai >= 5 lần: hiện error "Tài khoản bị khóa 15 phút. Vui lòng thử lại sau." + countdown timer
- Đang loading: button disabled + spinner
- Đã đăng nhập rồi vào /login: auto redirect /dashboard

## Route Guards (src/features/auth/):
- ProtectedRoute: wrap tất cả route trừ /login
  - Chưa auth → redirect /login
  - Đang check auth → full-screen loading spinner
- PublicRoute: wrap /login
  - Đã auth → redirect /dashboard

## Error Pages:
- /403 (ForbiddenPage): icon ShieldX + "Truy cập bị từ chối" + "Trang này chỉ dành cho quản trị viên hệ thống" + nút "Về trang chủ"
- /404 (NotFoundPage): icon FileQuestion + "Không tìm thấy trang" + nút "Về Dashboard"

## Mock Auth:
- Account test: admin@medinet.vn / admin123 → thành công
- Bất kỳ email/password khác → lỗi
- Mock delay 800ms để simulate network

Xây dựng đầy đủ, form validation, error handling, loading states, responsive (mobile-friendly).
```

---

<a id="prompt-3"></a>
## PROMPT 3 — App Layout (Sidebar + Header)

```
Xây dựng App Layout cho Hub Tổng (wiki.medinet.vn) — dùng cho tất cả trang sau khi đăng nhập.
Layout: Sidebar trái (cố định) + Header trên + Main Content.

## AppShell (src/components/layout/AppShell.tsx):
- Wrapper cho toàn bộ authenticated pages
- Props: children (main content)
- Layout: flex row → Sidebar (trái) + flex col → Header (trên) + Content (dưới, scrollable)

## Sidebar (src/components/layout/Sidebar.tsx):

### Header sidebar:
- Logo Medinet (icon hoặc image) + text "Medinet Wiki"
- Subtitle nhỏ: "Quản trị trung tâm"
- Divider

### Menu items (mỗi item: icon + label + optional badge):
1. Dashboard (icon LayoutDashboard) → /dashboard
2. Cross-hub Search (icon Search) → /search
3. --- divider ---
4. Quản lý User (icon Users) → /users
5. Hub Registry (icon Server) → /hub-registry
6. --- divider ---
7. Sync Queue (icon GitMerge) → /sync-review — badge đếm batch pending (ví dụ: "3")
8. Audit Log (icon ScrollText) → /audit-log
9. --- divider ---
10. API Keys (icon Key) → /settings/api-keys

### Footer sidebar:
- Divider
- User info: Avatar + Tên Admin + email (nhỏ)
- Nút Đăng xuất (icon LogOut)

### Behavior:
- Active menu item: background indigo-50, text indigo-600, left border indigo-600
- Hover: background slate-50
- Collapsible: nút toggle (ChevronLeft/Right) ở top → collapse thành icon-only mode (width 64px)
- Nhớ trạng thái collapse (localStorage)
- Mobile: sidebar ẩn, hamburger button trên header → overlay slide-in từ trái, click outside đóng

## Header (src/components/layout/Header.tsx):

### Layout: flex row, justify-between, items-center, border-b, bg-white, h-16, px-6

### Trái:
- Breadcrumb auto-generate từ route:
  - /dashboard → "Dashboard"
  - /users → "Quản lý User"
  - /sync-review/abc123 → "Sync Queue > Chi tiết Batch"
- Mobile: hamburger button (sidebar toggle)

### Phải:
- SearchBar nhỏ (compact mode, expand on focus) — placeholder "Tìm kiếm nhanh..."
- Notification Bell (icon Bell):
  - Badge đỏ với số unread (max "99+")
  - Click → Notification Dropdown (xây ở Prompt 11)
- User Dropdown (Avatar + tên):
  - Click → dropdown menu:
    - Tên + Email (header, không click được)
    - Divider
    - "Đăng xuất" (icon LogOut, click → authStore.logout())

## Responsive breakpoints:
- Desktop (>= 1024px): sidebar expanded (width 256px)
- Tablet (768-1023): sidebar collapsed (icon-only, 64px)
- Mobile (< 768): sidebar hidden, hamburger menu

## Animation:
- Sidebar collapse/expand: smooth width transition 200ms
- Mobile sidebar: slide-in from left 300ms

Xây dựng đầy đủ, intergrate với React Router (useLocation cho active menu), AuthStore (user info, logout).
```

---

<a id="prompt-4"></a>
## PROMPT 4 — Dashboard (UC-02)

```
Xây dựng trang Dashboard cho Hub Tổng. Route: /dashboard (default sau login).
Đây là trang tổng quan toàn bộ hệ thống Medinet Wiki — chỉ Admin Hub Tổng thấy.

## Layout: sử dụng AppShell. Content padding 24px.

## Section 1 — Stat Cards (grid 4 cột):
4 StatCard components ngang hàng:

1. "Tổng trang Wiki" — icon FileText, value: 270, trend +12% so tháng trước (xanh ↑)
2. "Hub hoạt động" — icon Server, value: "3/4", không trend
3. "User active tháng này" — icon Users, value: 47, trend +8% (xanh ↑)
4. "Sync chờ duyệt" — icon GitMerge, value: 5
   - Nếu value > 0: card có border-left amber-500, value màu amber-600, nhấn mạnh
   - Click card → navigate /sync-review

Responsive: 4 cột → 2 cột (tablet) → 1 cột (mobile)

## Section 2 — Bảng Hub Overview:
Card white với header "Danh sách Hub" + badge "3 Hub active".

DataTable:
| Cột | Mô tả |
|-----|-------|
| Tên Hub | Text + badge màu (Tâm Đạo = emerald, DMD = blue, HCNS = slate) |
| Subdomain | Link, click → window.open(url) mở tab mới |
| Số trang | Number |
| Cập nhật gần nhất | Relative time ("2 giờ trước") |
| Trạng thái | Badge: Active (green) / Inactive (gray) |
| Sync pending | Badge amber nếu có, "-" nếu không |

Sắp xếp mặc định: cập nhật gần nhất → Hub động nhất lên đầu.
Click row → window.open(subdomain URL)

## Section 3 — 2 cột (grid 7/5 hoặc 3/2):

### Cột trái — Card "Hoạt động gần đây":
Timeline component, 10 entries mới nhất:
- Mỗi entry: [Icon loại] [Thời gian relative] — [User hoặc "AI Agent"] [hành động] "[Tên trang]" trong [Hub]
- Icon theo loại: FilePlus (tạo), FileEdit (sửa), Trash2 (xóa), Bot (AI), GitMerge (sync)
- AI Agent entries có icon Bot + text "AI Agent" thay vì tên user
- Click entry → window.open(URL trang wiki trên subdomain Hub)
- Nút "Xem tất cả" → navigate /audit-log

### Cột phải — Card "Sync chờ duyệt":
- Nếu có batch pending:
  Danh sách cards nhỏ, mỗi batch:
  - Hub nguồn (badge màu) + số trang + thời gian gửi + tên Admin gửi
  - Nút "Duyệt ngay →" → navigate /sync-review/:batchId
- Nếu không có:
  EmptyState icon CheckCircle "Không có sync nào đang chờ"

Responsive: 2 cột → 1 cột (mobile, Hoạt động trên, Sync dưới)

## Mock Data (hardcoded trong file mock):
- 3 Hub: Tâm Đạo (127 trang, active, 2 sync pending), DMD (89 trang, active), HCNS (54 trang, active)
- 1 Hub inactive: "Test Hub" (0 trang)
- 10 activity entries (mix create, edit, delete, AI, sync)
- 2 sync batches pending (Tâm Đạo 3 trang, HCNS 2 trang)

Xây dựng đầy đủ với loading skeleton khi fetch data, error state, responsive.
```

---

<a id="prompt-5"></a>
## PROMPT 5 — Quản Lý User Hub Dự Án (UC-04)

```
Xây dựng trang Quản Lý User Hub Dự Án cho Hub Tổng. Route: /users
Admin Hub Tổng tạo/quản lý user cho từng Hub Dự Án. User Hub nào chỉ truy cập Hub đó.

## Layout: AppShell + PageHeader "Quản lý User Hub Dự Án"

## Tabs — Mỗi Hub Dự Án 1 tab:
Tabs component: "Tâm Đạo Y Quán" | "Đỗ Minh Đường" | "HCNS"
Mỗi tab có badge đếm số user (ví dụ: "Tâm Đạo Y Quán (12)")

## Nội dung mỗi tab:

### Toolbar (flex row, justify-between):
- Trái: SearchBar "Tìm theo tên hoặc email..." + Select filter "Tất cả quyền" / "Admin Hub Dự Án" / "Viewer"
- Phải: Button primary "Thêm User" (icon UserPlus)

### DataTable — Danh sách user:
| Cột | Mô tả |
|-----|-------|
| Tên | Avatar + tên |
| Email | text |
| Quyền | Badge: "Admin" (indigo) hoặc "Viewer" (gray) |
| Ngày tạo | date format dd/MM/yyyy |
| Đăng nhập cuối | relative time hoặc "Chưa đăng nhập" (italic gray) |
| Trạng thái | Badge: "Active" (green) / "Đã vô hiệu" (red) |
| Actions | DropdownMenu: Chỉnh quyền, Vô hiệu hóa / Kích hoạt lại, Gửi lại email mời |

Sort mặc định: đăng nhập cuối (gần nhất lên trên).
Pagination: 10 users/trang.

## Modal "Thêm User Mới" (Modal size md):
- Form fields:
  - Tên đầy đủ (Input, required)
  - Email (Input type email, required)
  - Quyền (Select: "Admin Hub Dự Án" / "Viewer", required)
- Info box: "User sẽ nhận email mời đăng nhập tại [subdomain Hub hiện tại]. Link đặt mật khẩu có hiệu lực 24 giờ."
- Buttons: "Hủy" (secondary) + "Tạo & Gửi Email Mời" (primary, loading)
- Thành công: toast success "Đã gửi email mời đến [email]", modal đóng, table refresh
- Lỗi email trùng: error trên field "Email đã được sử dụng trong Hub này"

## Modal "Chỉnh Quyền" (ConfirmDialog):
- Nội dung: Avatar + Tên + Email + Select đổi quyền
- Message: "Thay đổi quyền [Tên] từ [Viewer] sang [Admin Hub Dự Án]?"
- Buttons: "Hủy" + "Xác nhận thay đổi"
- Thành công: toast "Đã cập nhật quyền", table refresh

## Vô hiệu hóa user (ConfirmDialog variant danger):
- Message: "Vô hiệu hóa tài khoản [Tên]? User sẽ không thể đăng nhập vào [subdomain]."
- Nếu user đó là chính Admin đang login: CHẶN, hiện error "Không thể tự vô hiệu hóa tài khoản của mình"
- Thành công: toast warning "Đã vô hiệu hóa [Tên]", row đổi trạng thái

## Kích hoạt lại (ConfirmDialog):
- Message: "Kích hoạt lại tài khoản [Tên]?"
- Thành công: row đổi trạng thái Active

## Mock Data: Mỗi Hub 8-12 users, mix Admin/Viewer, 2 user disabled mỗi Hub.
```

---

<a id="prompt-6"></a>
## PROMPT 6 — Hub Registry (UC-05)

```
Xây dựng trang Hub Registry cho Hub Tổng. Route: /hub-registry
Quản lý danh sách Hub Dự Án — thêm, sửa, tắt Hub.

## Layout: AppShell + PageHeader "Hub Registry" + Button "Thêm Hub Mới" (phải)

## DataTable — Danh sách Hub:
| Cột | Mô tả |
|-----|-------|
| Tên Hub | Text + color dot theo Hub |
| Mã Hub | monospace text (tamdao, dmd, hcns) |
| Subdomain | Link clickable → mở tab mới |
| Trạng thái | Badge: Active (green) / Inactive (gray strikethrough) |
| Số trang | Number |
| Số user | Number |
| Ngày tạo | date |
| Actions | DropdownMenu: Sửa, Test kết nối, Tắt Hub |

## Modal "Thêm Hub Mới" (Modal size lg):
Form fields:
1. Tên Hub (Input, required) — ví dụ: "Tâm Đạo Y Quán"
2. Mã Hub (Input, required, lowercase, auto-generate từ tên nếu để trống) — ví dụ: "tamdao"
3. Subdomain (Input, auto-fill: "[mã].medinet.vn", editable) — readonly prefix hiện ".medinet.vn"
4. Mô tả (TextArea, optional)
5. --- divider "Kết nối Database" ---
6. DB Host (Input, required)
7. DB Port (Input, default 5432)
8. DB Name (Input, required)
9. DB User (Input, required)
10. DB Password (Input type password, required)
11. --- divider "ChromaDB" ---
12. ChromaDB Collection (Input, auto-suggest "col:[mã]", editable)

### Nút "Test Kết Nối" (secondary, inline):
- Click → loading 1-2s → kết quả inline:
  - Thành công: icon CheckCircle green + "Kết nối thành công — PostgreSQL 16.2, 0 tables"
  - Thất bại: icon XCircle red + "Kết nối thất bại: Connection refused (host:port)" (chi tiết lỗi)

### Buttons footer:
- "Hủy" (secondary)
- "Lưu Hub" (primary) — DISABLED nếu chưa test kết nối thành công
  - Thành công: toast "Hub [Tên] đã được thêm", redirect /hub-registry

## Modal "Sửa Hub" (Modal size lg):
- Giống form thêm, pre-fill data hiện tại
- Mã Hub và Subdomain readonly (không đổi được sau khi tạo)

## Tắt Hub (ConfirmDialog variant danger, type-to-confirm):
- Title: "Tắt Hub [Tên Hub]?"
- Message: "Hub sẽ không ai truy cập được. Dữ liệu vẫn được giữ."
- Input xác nhận: "Nhập tên Hub để xác nhận" → so sánh exact match
  - Nếu Hub có user đang đăng nhập: banner warning "Hub này đang có N user đăng nhập"
- Button "Tắt Hub" enable khi nhập đúng tên
- Thành công: toast warning, row đổi trạng thái Inactive

## Mock Data: 3 Hub active + 1 Hub inactive "Test Hub" (0 trang, 0 user).
```

---

<a id="prompt-7"></a>
## PROMPT 7 — Cross-Hub Search (UC-03)

```
Xây dựng trang Cross-Hub Search cho Hub Tổng. Route: /search
Admin tìm kiếm nội dung xuyên suốt tất cả Hub — dùng để kiểm tra chồng lặp trước khi duyệt Sync.

## Layout: AppShell + content centered max-w-4xl.

## Khi chưa search (trạng thái mặc định):
- SearchBar lớn (height 48px, font-size lg) giữa trang, icon Search
- Placeholder: "Tìm kiếm trên toàn bộ Wiki..."
- Dưới search bar: text muted "Tìm kiếm ngữ nghĩa trên tất cả Hub Dự Án"
- 3 suggestion chips: "Quy trình vận hành", "Bài thuốc đông y", "Chính sách nhân sự"
  Click chip → fill search bar + trigger search

## Khi đang loading:
- Search bar giữ query
- Skeleton: 5 result cards placeholder

## Khi có kết quả:
### Toolbar (dưới search bar):
- Trái: "Tìm thấy X kết quả trong 0.6s"
- Phải: Select filter Hub: "Tất cả Hub" / "Tâm Đạo" / "Đỗ Minh Đường" / "HCNS"

### Result List (cards, gap 12px):
Mỗi result card (border-l-4 màu theo Hub):
- **Dòng 1:** Badge Hub nguồn (Tâm Đạo = emerald, DMD = blue, HCNS = slate) + Category badge (gray)
- **Dòng 2:** Tiêu đề trang (font-medium, link → window.open subdomain URL)
- **Dòng 3-4:** Đoạn trích 2-3 dòng, từ khóa highlight (background yellow-200)
- **Dòng 5:** Tags (badge nhỏ) + "Cập nhật: 2 ngày trước"
- **Phải:** Score indicator — circular badge (85%) hoặc relevance dots

### Click kết quả → window.open(subdomain + /page/slug) — mở tab mới đến Hub gốc

## Khi không có kết quả:
- EmptyState: icon SearchX + "Không tìm thấy nội dung phù hợp trên toàn hệ thống"
- Gợi ý: "Thử tìm với từ khóa khác hoặc kiểm tra Hub cụ thể"

## Khi 1 Hub timeout:
- Banner warning (amber) nhỏ dưới toolbar: "⚠ Hub [Tên] không phản hồi — kết quả có thể không đầy đủ"
- Kết quả các Hub khác vẫn hiển thị bình thường

## URL: /search?q=keyword&hub=tamdao (search params để có thể share/bookmark)

## Mock Data: 15 kết quả từ 3 Hub, scores 0.95 → 0.51, categories khác nhau.
```

---

<a id="prompt-8"></a>
## PROMPT 8 — Audit Log (UC-06)

```
Xây dựng trang Audit Log cho Hub Tổng. Route: /audit-log
Hiển thị lịch sử toàn bộ hoạt động hệ thống — đặc biệt AI Agent và Sync events.

## Layout: AppShell + PageHeader "Audit Log" + Button "Xuất CSV" (phải, icon Download)

## Filter Bar (card, dưới PageHeader):
Flex row wrap, gap 12px:
1. DateRangePicker: "Từ ngày" — "Đến ngày" + quick presets (Hôm nay, 7 ngày, 30 ngày)
2. Select "Người thực hiện": Tất cả | [danh sách user names] | AI Agent
3. Select "Hành động": Tất cả | CREATE | UPDATE | DELETE | SYNC | APPROVE_SYNC | REJECT_SYNC | LOGIN | MCP_READ | MCP_WRITE
4. Select "Hub": Tất cả | Hub Tổng | Tâm Đạo | Đỗ Minh Đường | HCNS
5. Button "Áp dụng" (primary, icon Filter) + Button "Reset" (ghost)

## DataTable:
| Cột | Mô tả |
|-----|-------|
| Thời gian | datetime format "dd/MM/yyyy HH:mm:ss" |
| User/Agent | Avatar+tên hoặc icon Bot + "AI Agent ([key name])" |
| Hành động | Badge color-coded: CREATE=green, UPDATE=blue, DELETE=red, SYNC=amber, APPROVE=emerald, REJECT=rose, LOGIN=gray, MCP_READ=indigo, MCP_WRITE=purple |
| Trang bị ảnh hưởng | Tên trang (link, click → window.open subdomain URL) hoặc "—" |
| Hub | Badge màu theo Hub |
| IP | monospace text nhỏ |

Pagination: 50 records/trang, hiện tổng records.
Sort mặc định: thời gian mới nhất.

## Expand Row Detail (click row → expand panel dưới):
- Request ID, User Agent, Duration
- Payload trước/sau thay đổi:
  - JSON prettified trong code block
  - Hoặc diff view nếu có before/after (thêm = green, xóa = red)

## Xuất CSV:
- Click "Xuất CSV":
  - Nếu < 10,000 records (theo filter): download trực tiếp, toast "Đang tải xuống..."
  - Nếu >= 10,000 records: Modal thông báo "File quá lớn (X records). Hệ thống sẽ tạo file và gửi email khi hoàn tất." + Button "OK"

## Mock Data:
200 log entries, 30 ngày gần nhất:
- Mix: 40% UPDATE, 20% CREATE, 10% DELETE, 15% SYNC/APPROVE/REJECT, 10% MCP, 5% LOGIN
- 15% entries là AI Agent
- Mỗi entry có payload before/after (cho UPDATE)
```

---

<a id="prompt-9"></a>
## PROMPT 9 — Sync Batch Review (UC-07)

```
Xây dựng tính năng Sync Batch Review cho Hub Tổng.
Sync là 1 chiều: Hub Dự Án → Hub Tổng. Admin Hub Tổng duyệt từng trang trong batch.

## Trang danh sách batch (/sync-review):

### PageHeader: "Hàng đợi Sync" + badge đếm batch pending

### DataTable — Danh sách batches:
| Cột | Mô tả |
|-----|-------|
| Hub nguồn | Badge màu Hub |
| Số trang | Number |
| Thời gian gửi | relative time |
| Admin gửi | Avatar + tên Admin Hub Dự Án |
| Trạng thái | Badge: "Chờ duyệt" (amber) / "Đã xử lý" (green) |
| Actions | Button "Duyệt" (nếu pending) hoặc "Xem chi tiết" (nếu đã xử lý) |

Click row hoặc button → navigate /sync-review/:batchId

## Trang chi tiết batch (/sync-review/:batchId):

### Header:
- Breadcrumb: Sync Queue > Batch #[ID]
- Info: Hub nguồn (badge) + Số trang + Ngày gửi + Admin gửi
- ProgressBar: "X/Y trang đã xử lý"

### Layout 2 cột:

**Cột trái (width 35%, border-r, scroll riêng):** Danh sách trang trong batch
- Mỗi item: Tiêu đề + icon trạng thái
  - ○ Chưa xử lý (gray, mặc định)
  - ✓ Đã duyệt (green)
  - ✗ Đã từ chối (red)
- Click item → load preview bên phải
- Item active: background indigo-50

**Cột phải (width 65%, scroll riêng):** Preview trang đang chọn
- Tiêu đề (H2), Category, Tags, Ngày tạo, Tác giả
- Render HTML content đầy đủ (headings, lists, tables, images)
- Nếu phát hiện trang tương tự trong Hub Tổng (similarity > 0.85):
  Banner amber: "⚠ Trang tương tự đã tồn tại: [Tên trang] (87% trùng)" + link xem

### Action Bar (sticky bottom, dưới preview):
Flex row, gap 12px:
- Button "Duyệt" (green, icon Check) → approve trang hiện tại, auto select trang tiếp
- Button "Từ chối" (red, icon X) → mở textarea "Lý do từ chối" (required, min 10 ký tự) → confirm
- Divider
- Button "Duyệt tất cả còn lại" (outline green) → ConfirmDialog "Duyệt X trang còn lại?"
- Button "Hoàn tất" (primary) → chỉ enable khi tất cả trang đã xử lý
  → ConfirmDialog: "Kết quả: X duyệt, Y từ chối. Xác nhận gửi?"
  → Submit → toast "Đã xử lý batch: X duyệt, Y từ chối" → redirect /sync-review

### Batch đã xử lý (xem lại):
- Readonly mode: không có action bar
- Mỗi trang hiện kết quả: Duyệt hoặc Từ chối + lý do

## Edge cases:
- Admin đóng tab giữa chừng: trang chưa xử lý vẫn pending (persist decisions server-side)
- Batch 0 trang pending: redirect về danh sách

## Mock Data:
- Batch 1: Hub Tâm Đạo, 8 trang chờ (1 trang có duplicate warning)
- Batch 2: Hub HCNS, 5 trang đã xử lý (3 duyệt, 2 từ chối)
```

---

<a id="prompt-10"></a>
## PROMPT 10 — MCP API Key Management (UC-08)

```
Xây dựng trang quản lý MCP API Key cho Hub Tổng. Route: /settings/api-keys
Quản lý API key cho AI Agent (Claude, ChatGPT) truy cập Wiki qua MCP protocol.

## Layout: AppShell + PageHeader "MCP API Keys" + subtitle "Quản lý API key cho AI Agent truy cập Wiki"

### Nút "Tạo API Key Mới" (primary, icon Plus)

## DataTable — Danh sách API Keys:
| Cột | Mô tả |
|-----|-------|
| Tên key | Text + mô tả nhỏ (gray) dưới |
| Quyền | Badges inline: "Read" (blue) "Write" (amber) "Cross-hub" (purple) |
| Hub được phép | Badge(s) hoặc "Tất cả Hub" |
| Ngày tạo | date |
| Dùng cuối | relative time hoặc "Chưa sử dụng" |
| Requests 7 ngày | Number + mini sparkline chart (optional) |
| Rate limit | "100 req/phút" |
| Trạng thái | Badge: "Active" (green) / "Đã thu hồi" (red strikethrough) / "Hết hạn" (gray) |
| Actions | Button "Thu hồi" (danger, chỉ active keys) |

## Modal "Tạo API Key Mới" (Modal size lg):
Form fields:
1. Tên key (Input, required) — ví dụ: "Claude Desktop — Team AI"
2. Mô tả (TextArea, optional)
3. --- divider "Phạm vi quyền" ---
4. Checkboxes:
   - ☑ Read (mặc định checked, disabled — luôn có)
   - ☐ Write (tạo/sửa page qua MCP)
   - ☐ Cross-hub Search
5. Hub được phép (MultiSelect): chọn Hub cụ thể hoặc checkbox "Tất cả Hub"
6. Rate limit (Input number, default 100) — label: "requests/phút"
7. Ngày hết hạn (DatePicker, optional) — label: "Để trống = không hết hạn"

Buttons: "Hủy" + "Tạo Key" (primary, loading)

## Modal "API Key đã tạo" (Modal size md, KHÔNG cho đóng bằng overlay click):

### Quan trọng — thiết kế nổi bật:
- Icon Key lớn + màu green
- Title: "API Key đã được tạo thành công"
- Banner danger (red background): "⚠ Hãy sao chép key ngay bây giờ. Key sẽ KHÔNG hiển thị lại sau khi đóng."
- Key display: monospace box, full 64 ký tự, border dashed, background gray-50
  - Có thể select all text
- Button "Sao chép" (lớn, primary, icon Copy):
  - Click → copy to clipboard
  - Text đổi thành "✓ Đã sao chép!" (green, 2 giây rồi về "Sao chép")
- Divider
- Button "Đã sao chép, đóng" (secondary) → đóng modal, refresh table

## Thu hồi Key (ConfirmDialog variant danger):
- Title: "Thu hồi API Key?"
- Message: "Key '[Tên]' sẽ ngừng hoạt động ngay lập tức. Mọi AI Agent đang dùng key này sẽ bị từ chối."
- Buttons: "Hủy" + "Thu hồi" (red)
- Thành công: toast warning "Đã thu hồi key [Tên]", row đổi trạng thái

## Mock Data:
- Key 1: "Claude Desktop — Team AI" — Read+Write, Tất cả Hub, active, 1,247 requests 7 ngày
- Key 2: "ChatGPT Plugin" — Read only, Tâm Đạo + DMD, active, 89 requests
- Key 3: "Test Key" — Read, đã thu hồi
```

---

<a id="prompt-11"></a>
## PROMPT 11 — Notification System

```
Xây dựng hệ thống Notification cho Hub Tổng.

## Notification Store (src/stores/notificationStore.ts — Zustand):
interface Notification {
  id: string;
  type: "sync" | "user" | "api_key" | "system";
  title: string;
  message: string;
  link?: string;          // navigate khi click
  isRead: boolean;
  createdAt: Date;
  icon: "GitMerge" | "UserPlus" | "Key" | "AlertTriangle" | "Bot";
}

interface NotificationState {
  notifications: Notification[];
  unreadCount: number;
  isOpen: boolean;          // dropdown open/close
  toggleDropdown: () => void;
  markAsRead: (id: string) => void;
  markAllRead: () => void;
  fetchNotifications: () => Promise<void>;
}

## Header Bell Icon (trong Header component):
- Icon Bell (Lucide)
- Badge đỏ góc trên phải: số unread
  - 0 unread: không hiện badge
  - 1-99: hiện số
  - 100+: hiện "99+"
- Click → toggle notification dropdown

## Notification Dropdown:
- Position: absolute, dưới bell icon, phải align
- Width: 380px, max-height: 480px, scroll
- Shadow-xl, rounded-xl, border

### Header dropdown:
- "Thông báo" (bold) + link "Đánh dấu tất cả đã đọc" (text-sm, indigo, right)

### List notifications:
Mỗi notification item (padding 12px, hover bg-slate-50):
- Trái: Icon circle (color theo type: sync=amber, user=blue, api_key=purple, system=red)
- Giữa:
  - Title (font-medium, 1 line truncate)
  - Message (text-sm gray, 2 lines max)
  - Time relative (text-xs gray, "5 phút trước")
- Phải (nếu unread): dot xanh 8px
- Chưa đọc: background indigo-50/50
- Click → navigate(link) + markAsRead(id) + đóng dropdown

### Empty state: "Không có thông báo mới" (icon BellOff)

### Footer: Link "Xem tất cả thông báo" (center, text-sm) — có thể navigate đến /notifications page (optional)

## Loại thông báo Hub Tổng:
1. Sync: "Sync mới từ Hub Tâm Đạo: 5 trang chờ duyệt" → /sync-review/:id
2. User: "Nguyễn Văn A đã đăng nhập Hub HCNS lần đầu" → /users
3. API Key: "API Key 'Claude Desktop' sắp hết hạn trong 7 ngày" → /settings/api-keys
4. System: "Hub Đỗ Minh Đường không phản hồi — kiểm tra kết nối" → /hub-registry

## Mock Data: 12 notifications, 5 unread, mix types, thời gian 5 phút → 3 ngày trước.
```

---

<a id="prompt-12"></a>
## PROMPT 12 — Mock API & Data Layer

```
Xây dựng Mock API layer cho toàn bộ Hub Tổng frontend.
Frontend phải hoạt động hoàn chỉnh không cần backend thật.

## API Client (src/lib/api.ts):
- Axios instance: baseURL từ VITE_API_BASE_URL
- Request interceptor: gắn Authorization: Bearer [token] từ authStore
- Response interceptor:
  - 401 → authStore.logout() + redirect /login
  - 403 → redirect /403
  - 5xx → toast.error("Lỗi hệ thống")
- export default apiClient

## Mock Layer (src/lib/mock/):
Khi VITE_MOCK_API=true: intercept axios requests, trả mock data + delay 300-800ms.

### Cấu trúc:
src/lib/mock/
├── index.ts            # Setup mock interceptor
├── data/               # Mock data fixtures
│   ├── hubs.ts         # 4 Hub objects
│   ├── users.ts        # 40 users (mix Hub, role, status)
│   ├── pages.ts        # 50 page summaries (cho search results)
│   ├── activities.ts   # 10 recent activities
│   ├── audit-logs.ts   # 200 audit log entries
│   ├── sync-batches.ts # 4 batches (2 pending, 2 processed)
│   ├── api-keys.ts     # 3 API keys
│   └── notifications.ts # 12 notifications
├── handlers/           # Request handlers (match URL → return data)
│   ├── auth.ts
│   ├── hubs.ts
│   ├── users.ts
│   ├── search.ts
│   ├── audit-log.ts
│   ├── sync.ts
│   ├── api-keys.ts
│   └── notifications.ts

## Mock Endpoints:

### Auth:
POST /api/auth/login        → { token, user } (admin@medinet.vn / admin123)
POST /api/auth/logout       → { success: true }
GET  /api/auth/me           → { user: { id, name, email, role, avatar } }

### Dashboard:
GET /api/dashboard/stats    → { totalPages, activeHubs, activeUsers, syncPending }
GET /api/dashboard/activities → Activity[] (10 items)

### Hubs:
GET    /api/hubs                    → Hub[] (4 Hubs)
POST   /api/hubs                    → Hub (create)
PUT    /api/hubs/:id                → Hub (update)
POST   /api/hubs/:id/test-connection → { success: boolean, message: string }
PUT    /api/hubs/:id/deactivate     → Hub

### Users:
GET    /api/hubs/:hubId/users       → paginated { data: User[], total, page }
POST   /api/hubs/:hubId/users       → User (invite)
PUT    /api/hubs/:hubId/users/:id/role    → User (change role)
PUT    /api/hubs/:hubId/users/:id/disable → User
PUT    /api/hubs/:hubId/users/:id/enable  → User
POST   /api/hubs/:hubId/users/:id/resend-invite → { success }

### Search:
GET /api/search?q=&hub=&page=&limit= → { results: SearchResult[], total, took_ms }

### Audit Log:
GET /api/audit-log?from=&to=&action=&user=&hub=&page=&limit= → paginated
GET /api/audit-log/export?from=&to=&... → { downloadUrl } hoặc { jobId } (> 10k)

### Sync:
GET  /api/sync/batches                    → SyncBatch[]
GET  /api/sync/batches/:id                → SyncBatch with pages[]
PUT  /api/sync/batches/:id/pages/:pageId  → { action: "approve" | "reject", reason? }
POST /api/sync/batches/:id/complete       → { approved: N, rejected: N }

### API Keys:
GET    /api/mcp/api-keys     → ApiKey[]
POST   /api/mcp/api-keys     → { apiKey: ApiKey, rawKey: "sk-..." } (rawKey chỉ 1 lần)
DELETE /api/mcp/api-keys/:id  → { success }

### Notifications:
GET  /api/notifications           → Notification[]
PUT  /api/notifications/:id/read  → { success }
PUT  /api/notifications/read-all  → { success }

## TanStack Query Hooks (src/hooks/):
Mỗi feature tạo custom hooks:
- useDashboardStats() → useQuery
- useHubs() → useQuery
- useCreateHub() → useMutation + invalidate useHubs
- useUsers(hubId, filters) → useQuery
- useInviteUser(hubId) → useMutation
- useSearchResults(query, hubFilter) → useQuery (enabled khi query !== "")
- useAuditLogs(filters) → useQuery
- useSyncBatches() → useQuery
- useSyncBatchDetail(batchId) → useQuery
- useApproveSyncPage() → useMutation
- useRejectSyncPage() → useMutation
- useApiKeys() → useQuery
- useCreateApiKey() → useMutation
- useRevokeApiKey() → useMutation
- useNotifications() → useQuery (refetchInterval: 30s)

## Mock Data yêu cầu chất lượng:
- Tên tiếng Việt thực tế: Nguyễn Văn A, Trần Thị B, Lê Minh C...
- Nội dung trang Wiki tiếng Việt: bài thuốc, chính sách HR, SOP...
- Timestamps realistic: 30 ngày gần nhất, giờ làm việc
- Hub data nhất quán: users thuộc đúng Hub, pages thuộc đúng Hub

Xây dựng đầy đủ, sẵn sàng cho tất cả features sử dụng.
```

---

## THỨ TỰ XÂY DỰNG

```
Phase 1 — Nền tảng (phải làm trước):
  Prompt 0  → Project Setup
  Prompt 1  → UI Components
  Prompt 12 → Mock API & Data (chạy song song với Prompt 1)

Phase 2 — Auth & Shell:
  Prompt 2  → Login + Auth
  Prompt 3  → App Layout (Sidebar + Header)

Phase 3 — Core Pages:
  Prompt 4  → Dashboard
  Prompt 5  → User Management
  Prompt 6  → Hub Registry

Phase 4 — Advanced Features:
  Prompt 7  → Cross-Hub Search
  Prompt 8  → Audit Log
  Prompt 9  → Sync Batch Review
  Prompt 10 → API Key Management

Phase 5 — Polish:
  Prompt 11 → Notifications
  Review + fix integration issues
```

---

## GHI CHÚ KHI SỬ DỤNG

1. **Copy từng prompt** vào AI tool (Claude, Cursor, Bolt, v0.dev...)
2. **Chạy theo thứ tự Phase** — mỗi prompt phụ thuộc vào output của prompt trước
3. **Sau mỗi prompt**: review code, test UI, sửa lỗi trước khi tiến tiếp
4. **Prompt 12 (Mock API)** rất quan trọng — nên làm sớm để tất cả page có data
5. **Nếu AI tool giới hạn context**: chia nhỏ prompt (ví dụ: Prompt 1 chia thành 2-3 lần, mỗi lần 7-8 components)
6. **Khi chuyển sang Hub Dự Án**: nhiều components từ Hub Tổng có thể copy & adapt (Auth, Layout, DataTable, Search...)
