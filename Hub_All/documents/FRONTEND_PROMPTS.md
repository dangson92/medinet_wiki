# MEDINET WIKI — FRONTEND BUILD PROMPTS

> Tài liệu prompt để xây dựng frontend với AI. Mỗi prompt là một module/trang độc lập.
> Tech Stack: React 18 + Vite + TypeScript + React Router v6 + Zustand + TailwindCSS + TipTap Editor
> Kiến trúc: Vite Monorepo — 4 React SPA (Hub Tổng + 3 Hub Dự Án) + shared packages

---

## MỤC LỤC

1. [PROMPT 0 — Project Setup & Monorepo](#prompt-0)
2. [PROMPT 1 — Shared UI Component Library](#prompt-1)
3. [PROMPT 2 — Auth & Layout System](#prompt-2)
4. [PROMPT 3 — Hub Tổng: Dashboard](#prompt-3)
5. [PROMPT 4 — Hub Tổng: Quản Lý User Hub Dự Án](#prompt-4)
6. [PROMPT 5 — Hub Tổng: Hub Registry](#prompt-5)
7. [PROMPT 6 — Hub Tổng: Cross-Hub Search](#prompt-6)
8. [PROMPT 7 — Hub Tổng: Audit Log](#prompt-7)
9. [PROMPT 8 — Hub Tổng: Sync Batch Review](#prompt-8)
10. [PROMPT 9 — Hub Tổng: MCP API Key Management](#prompt-9)
11. [PROMPT 10 — Hub Dự Án: Layout & Navigation](#prompt-10)
12. [PROMPT 11 — Hub Dự Án: Wiki Page Reader](#prompt-11)
13. [PROMPT 12 — Hub Dự Án: Wiki Editor (Create/Edit)](#prompt-12)
14. [PROMPT 13 — Hub Dự Án: RAG Search](#prompt-13)
15. [PROMPT 14 — Hub Dự Án: Categories & Tags Management](#prompt-14)
16. [PROMPT 15 — Hub Dự Án: Version History & Restore](#prompt-15)
17. [PROMPT 16 — Hub Dự Án: Sync Management](#prompt-16)
18. [PROMPT 17 — Hub Dự Án: AI Post Review Queue](#prompt-17)
19. [PROMPT 18 — AI Post: Đăng Bài Từ Claude](#prompt-18)
20. [PROMPT 19 — Hub Dự Án: Onboarding Checklist (HCNS)](#prompt-19)
21. [PROMPT 20 — Hub Dự Án: Embed & Index Management](#prompt-20)
22. [PROMPT 21 — Notification System](#prompt-21)
23. [PROMPT 22 — Mock API & Data Layer](#prompt-22)

---

<a id="prompt-0"></a>
## PROMPT 0 — Project Setup & Vite Monorepo

```
Tạo Vite monorepo cho dự án Medinet Wiki với cấu trúc sau:

## Cấu trúc thư mục:
medinet-wiki/
├── packages/
│   ├── shared-ui/          # Shared React components (Button, Modal, Table, Toast...)
│   ├── shared-hooks/       # Shared hooks (useAuth, useApi, useDebounce, useToast...)
│   ├── shared-types/       # TypeScript types/interfaces dùng chung
│   └── api-client/         # API client wrapper (axios instance, interceptors, mock)
├── apps/
│   ├── hub-tong/           # wiki.medinet.vn — Admin dashboard
│   ├── hub-tamdao/         # tamdao.medinet.vn — Hub Tâm Đạo
│   ├── hub-dmd/            # dmd.medinet.vn — Hub Đỗ Minh Đường
│   └── hub-hcns/           # hcns.medinet.vn — Hub HCNS
├── package.json            # Workspace root
├── pnpm-workspace.yaml
├── tsconfig.base.json
└── tailwind.config.ts      # Shared Tailwind config

## Yêu cầu kỹ thuật:
- Package manager: pnpm workspaces
- Build: Vite 5+ với React 18 + TypeScript
- Styling: TailwindCSS 3+ với design tokens chung (colors, spacing, typography)
- Routing: React Router v6 (mỗi app có router riêng)
- State: Zustand (global state per app) + React Query/TanStack Query (server state)
- Icons: Lucide React
- Mỗi app build độc lập → output static files để Nginx serve

## Design Tokens (TailwindCSS):
- Hub Tổng: primary = indigo-600, bg = slate-50
- Hub Tâm Đạo: primary = emerald-600, bg = emerald-50
- Hub Đỗ Minh Đường: primary = blue-600, bg = blue-50
- Hub HCNS: primary = slate-700, bg = gray-50

## Scripts cần có:
- pnpm dev:hub-tong → chạy Hub Tổng ở port 3000
- pnpm dev:hub-tamdao → port 3001
- pnpm dev:hub-dmd → port 3002
- pnpm dev:hub-hcns → port 3003
- pnpm build:all → build tất cả apps
- pnpm dev:all → chạy tất cả cùng lúc

Tạo đầy đủ config files, README, và 1 trang placeholder "Hello [Hub Name]" cho mỗi app.
```

---

<a id="prompt-1"></a>
## PROMPT 1 — Shared UI Component Library

```
Xây dựng shared UI component library cho dự án Medinet Wiki tại packages/shared-ui/.
Sử dụng React 18 + TypeScript + TailwindCSS. Tất cả components phải responsive và accessible (WCAG AA).

## Components cần xây dựng:

### Layout
- **AppShell**: Layout chính gồm Header + Sidebar (collapsible) + Main Content + optional Right Sidebar
- **Header**: Logo (trái), Search bar (giữa), Notification bell (badge count) + User avatar dropdown (phải)
- **Sidebar**: Collapsible, hỗ trợ nested menu (expand/collapse), nhớ trạng thái theo session, có badge count
- **Breadcrumb**: Auto-generate từ route, clickable
- **PageHeader**: Title + description + action buttons

### Data Display
- **DataTable**: Sortable columns, pagination, row selection (checkbox), empty state, loading skeleton
- **StatCard**: Icon + label + value + trend (up/down %). Dùng cho dashboard
- **Badge**: Variants: default, success, warning, danger, info. Dùng cho status labels
- **Timeline**: Vertical timeline với icon, timestamp, content. Dùng cho version history, audit log
- **DiffViewer**: Side-by-side hoặc inline diff view (thêm = xanh, xóa = đỏ). Toggle mode

### Form
- **Input**: Text, password, email. Có label, error message, helper text
- **Select**: Single select, searchable dropdown
- **MultiSelect**: Tag-style multi select với autocomplete
- **TagInput**: Input cho tags, autocomplete từ danh sách có sẵn, hiện badge tag đã chọn
- **TextArea**: Auto-resize
- **SearchBar**: Input với icon search, debounce 300ms, clear button, loading spinner
- **FileUpload**: Drag & drop zone, preview ảnh

### Feedback
- **Modal**: Header + Body + Footer actions. Sizes: sm, md, lg, xl, full. Close on ESC/overlay click
- **ConfirmDialog**: Title + message + Confirm/Cancel buttons. Variant: danger (xóa), warning (khôi phục)
- **Toast**: Top-right, auto-dismiss 5s. Types: success, error, warning, info. Stack multiple
- **EmptyState**: Icon + title + description + optional CTA button
- **LoadingSkeleton**: Skeleton placeholder cho cards, tables, text blocks
- **ProgressBar**: Determinate (X/Y) + label

### Navigation
- **Tabs**: Horizontal tabs, với badge count. Controlled
- **TreeView**: Expandable/collapsible tree cho categories. Hỗ trợ drag-and-drop reorder

Mỗi component export từ index.ts, có TypeScript props interface rõ ràng.
Tạo file Storybook-style demo page hiển thị tất cả components.
```

---

<a id="prompt-2"></a>
## PROMPT 2 — Auth & Layout System

```
Xây dựng hệ thống Authentication và Layout cho Medinet Wiki.
Auth hoàn toàn độc lập từng subdomain — mỗi app có JWT session riêng, không SSO.

## Auth Flow:

### Login Page (dùng chung component, config khác nhau mỗi app):
- Form: Email + Password + nút "Đăng nhập"
- Không có nút "Đăng ký" — tài khoản do Admin Hub Tổng tạo
- Hub Tổng: tiêu đề "Quản trị Medinet Wiki", primary color indigo
- Hub Tâm Đạo: tiêu đề "Đăng nhập — Tâm Đạo Y Quán", primary color emerald
- Hub DMD: tiêu đề "Đăng nhập — Đỗ Minh Đường", primary color blue
- Hub HCNS: tiêu đề "Đăng nhập — Hành Chính Nhân Sự", primary color slate
- Sai mật khẩu < 5 lần: hiện lỗi "Email hoặc mật khẩu không đúng"
- Sai >= 5 lần: hiện "Tài khoản bị khóa 15 phút"
- User không có quyền vào Hub: trang 403 "Tài khoản này không có quyền vào Hub này"
- User thường vào wiki.medinet.vn: trang 403 "Trang này chỉ dành cho quản trị viên hệ thống"

### Auth Store (Zustand):
- State: user, token, role, hub_id, isAuthenticated, isLoading
- Actions: login(email, password), logout(), refreshToken(), checkAuth()
- JWT payload: { user_id, hub_id, role, exp }
- Roles: admin_hub_tong | admin_hub_du_an | viewer
- Token lưu httpOnly cookie (mock với localStorage cho dev)
- Auto redirect về login khi token hết hạn

### Route Protection:
- PublicRoute: chỉ Login page
- ProtectedRoute: check isAuthenticated, redirect về /login nếu chưa
- AdminRoute: check role === admin_hub_du_an hoặc admin_hub_tong
- Hiển thị/ẩn UI elements theo role (Viewer không thấy nút Tạo/Sửa/Xóa)

### Layout khác nhau theo app:
- Hub Tổng sidebar: Dashboard, Cross-hub Search, Quản lý User, Hub Registry, Audit Log, Sync Queue, MCP Config
- Hub Dự Án sidebar: Trang chủ Hub, Categories (tree), Tạo trang mới (Admin only), Hàng chờ duyệt AI (Admin, badge count), Quản lý Sync (Admin), Cài đặt Hub (Admin), Nháp (Admin)

### Error Pages:
- 403 Forbidden: với message tùy context
- 404 Not Found: với gợi ý tìm kiếm
- 500 Server Error

Xây dựng đầy đủ với mock data, có thể login bằng các test accounts:
- admin@medinet.vn / password → Admin Hub Tổng
- admin.tamdao@medinet.vn / password → Admin Hub Tâm Đạo
- viewer.tamdao@medinet.vn / password → Viewer Hub Tâm Đạo
```

---

<a id="prompt-3"></a>
## PROMPT 3 — Hub Tổng: Dashboard (UC-02)

```
Xây dựng trang Dashboard cho Hub Tổng (wiki.medinet.vn) — chỉ Admin Hub Tổng truy cập.

## Layout:
Sử dụng AppShell layout với sidebar. Route: /dashboard (default sau login).

## Nội dung Dashboard:

### Row 1 — Stat Cards (4 cards ngang hàng):
1. "Tổng trang Wiki" — số trang toàn hệ thống, trend so với tháng trước
2. "Hub đang hoạt động" — số Hub active (ví dụ: 3/4)
3. "User đang active" — MAU tháng này
4. "Sync chờ duyệt" — số trang đang chờ, nổi bật nếu > 0 (màu vàng/cam)

### Row 2 — Bảng Hub Overview:
DataTable với các cột:
- Tên Hub (link tới subdomain, mở tab mới)
- Subdomain
- Số trang wiki
- Lần cập nhật gần nhất
- Trạng thái (Active / Không hoạt động)
- Sync pending (có/không, hiện số)
Sắp xếp theo lần cập nhật gần nhất — Hub động nhất lên đầu.
Click tên Hub → window.open(subdomain URL)

### Row 3 — 2 columns:
**Cột trái — "Sync chờ duyệt" (card):**
- Nếu có: danh sách batch pending, mỗi batch hiện: Hub nguồn, số trang, thời gian gửi
- Click batch → navigate đến /sync-review/:batchId
- Nếu không có: EmptyState "Không có sync nào đang chờ"

**Cột phải — "Hoạt động gần đây" (card):**
- Timeline 10 entries gần nhất: [Thời gian] [User/AI] [Hành động] [Trang] [Hub]
- Entries AI Agent có icon robot để phân biệt
- Click entry → mở trang Wiki tương ứng (tab mới sang subdomain Hub)

## Mock Data:
Tạo mock data cho 3 Hub: Tâm Đạo (127 trang, active), Đỗ Minh Đường (89 trang, active), HCNS (54 trang, active).
2 batch sync pending. 10 activity entries gần đây.

## Responsive:
- Desktop: grid 4 cột stat cards, 2 cột row 3
- Tablet: grid 2 cột stat cards, 1 cột row 3
- Mobile: grid 1 cột
```

---

<a id="prompt-4"></a>
## PROMPT 4 — Hub Tổng: Quản Lý User Hub Dự Án (UC-04)

```
Xây dựng trang Quản Lý User Hub Dự Án cho Hub Tổng. Route: /users

## Layout:
- Tabs ngang phía trên: mỗi tab là 1 Hub Dự Án (Tâm Đạo | Đỗ Minh Đường | HCNS)
- Mỗi tab quản lý user độc lập

## Trong mỗi tab Hub:

### Toolbar:
- Nút "Thêm User" (mở modal)
- Search bar: tìm theo tên/email
- Filter dropdown: Tất cả / Admin Hub Dự Án / Viewer

### DataTable — Danh sách user:
Cột: Tên | Email | Quyền (badge: Admin/Viewer) | Ngày tạo | Đăng nhập cuối | Trạng thái (Active/Disabled)
Row actions: Chỉnh quyền | Vô hiệu hóa | Gửi lại email mời

### Modal "Thêm User Mới":
- Form: Tên, Email, Quyền (dropdown: Admin Hub Dự Án / Viewer)
- Nút "Tạo & Gửi Email Mời"
- Sau tạo: hiện thông báo "Email mời đã được gửi đến [email]. Link đặt mật khẩu có hiệu lực 24h."
- Email mời ghi rõ: "Bạn được mời vào Hub [Tên Hub] tại [subdomain]"

### Modal "Chỉnh Quyền":
- Hiện user info + dropdown chuyển quyền
- Confirm: "Thay đổi quyền [Tên] từ Viewer → Admin Hub Dự Án?"
- Có hiệu lực ngay

### Vô hiệu hóa user:
- ConfirmDialog: "Vô hiệu hóa [Tên]? User sẽ không thể đăng nhập [subdomain]."
- Soft disable: dữ liệu giữ nguyên, có thể bật lại

## Validation:
- Email trùng trong Hub: lỗi "Email đã được sử dụng trong Hub này"
- Admin tự xóa quyền mình: chặn "Không thể tự xóa quyền Admin"

## Mock Data: 8-12 users mỗi Hub, mix Admin và Viewer, một số disabled.
```

---

<a id="prompt-5"></a>
## PROMPT 5 — Hub Tổng: Hub Registry (UC-05)

```
Xây dựng trang Hub Registry cho Hub Tổng. Route: /hub-registry

## Danh sách Hub:
DataTable: Tên Hub | Mã Hub | Subdomain | Trạng thái (Active/Inactive) | Số trang | Ngày tạo
Row actions: Sửa | Test kết nối | Tắt Hub

## Nút "Thêm Hub Mới" → Modal form:
- Tên Hub (required)
- Mã Hub (required, unique, lowercase, ví dụ: "tamdao")
- Subdomain (auto-generate từ mã: [mã].medinet.vn, editable)
- DB Connection String (required)
- ChromaDB Collection Name (required, auto-suggest: col:[mã])
- Mô tả
- Nút "Test Kết Nối DB" → hiện kết quả test inline (thành công = xanh, thất bại = đỏ + chi tiết lỗi)
- Nút "Lưu Hub" (disabled nếu chưa test kết nối thành công)

## Validation:
- Subdomain trùng: "Subdomain này đã được sử dụng"
- Test DB thất bại: hiện lỗi chi tiết, không cho lưu

## Tắt Hub:
- ConfirmDialog nguy hiểm: "Tắt Hub [Tên]? Hub sẽ không ai truy cập được."
- Nhập lại tên Hub để xác nhận (type-to-confirm pattern)
- Cảnh báo nếu Hub có user đang đăng nhập

## Mock Data: 3 Hub active (Tâm Đạo, DMD, HCNS) + 1 Hub inactive (Test Hub).
```

---

<a id="prompt-6"></a>
## PROMPT 6 — Hub Tổng: Cross-Hub Search (UC-03)

```
Xây dựng trang Cross-Hub Search cho Hub Tổng. Route: /search

## Giao diện:
### Search Bar (prominent, giữa trang):
- Input lớn với placeholder "Tìm kiếm trên toàn bộ Wiki..."
- Debounce 300ms
- Nút Search hoặc Enter để trigger

### Kết quả search:
- Toolbar: Tổng số kết quả + Filter dropdown Hub (Tất cả | Tâm Đạo | DMD | HCNS)
- Danh sách kết quả (cards):
  Mỗi card hiện:
  - Badge Hub nguồn (màu theo Hub: Tâm Đạo = emerald, DMD = blue, HCNS = slate)
  - Tiêu đề trang (link, click → window.open sang subdomain Hub gốc)
  - Đoạn trích ngữ cảnh với highlight từ khóa (2-3 dòng)
  - Score indicator (thanh nhỏ hoặc %)
  - Tags (nếu có)
  - Ngày cập nhật

### States:
- Chưa search: hiện gợi ý "Nhập từ khóa để tìm kiếm trên tất cả Hub"
- Đang loading: skeleton cards
- Không có kết quả: EmptyState "Không tìm thấy nội dung phù hợp trên toàn hệ thống"
- Một Hub timeout: banner warning nhỏ "Một Hub không phản hồi — kết quả có thể không đầy đủ"

## Ghi chú:
- Tính năng này CHỈ có trên Hub Tổng — không có trên Hub Dự Án
- Admin dùng chủ yếu để kiểm tra chồng lặp trước khi duyệt Sync

## Mock Data: 15-20 kết quả từ 3 Hub, scores khác nhau.
```

---

<a id="prompt-7"></a>
## PROMPT 7 — Hub Tổng: Audit Log (UC-06)

```
Xây dựng trang Audit Log cho Hub Tổng. Route: /audit-log

## Giao diện:

### Filter Bar (trên cùng):
- DateRange picker: Từ ngày — Đến ngày
- Dropdown User/Agent: Tất cả | [danh sách user] | AI Agent
- Dropdown Hành động: Tất cả | CREATE | UPDATE | DELETE | SYNC | APPROVE_SYNC | REJECT_SYNC | LOGIN | MCP_READ | MCP_WRITE
- Dropdown Hub: Tất cả | Tâm Đạo | DMD | HCNS | Hub Tổng
- Nút "Áp dụng" + "Reset filter"
- Nút "Xuất CSV" (ở góc phải)

### DataTable — Log Entries:
Cột: Thời gian | User/Agent | Hành động (badge color-coded) | Trang bị ảnh hưởng | Hub nguồn | IP
- Phân trang 50 records/trang
- AI Agent entries có icon robot + text "AI Agent ([API key name])"
- Sync events có nhãn riêng biệt dễ nhận diện

### Click row → Expand detail panel:
- Payload chi tiết trước/sau thay đổi (JSON prettified hoặc diff view)
- Full metadata: user agent, request ID, duration

### Xuất CSV:
- < 10,000 records: download trực tiếp
- > 10,000 records: modal "File đang được tạo, sẽ gửi email khi xong"

## Mock Data: 200 log entries, mix user actions + AI Agent actions + Sync events.
```

---

<a id="prompt-8"></a>
## PROMPT 8 — Hub Tổng: Sync Batch Review (UC-07)

```
Xây dựng trang Sync Batch Review cho Hub Tổng. Route: /sync-review

## Danh sách Batch (trang chính /sync-review):
DataTable: Hub nguồn | Số trang | Thời gian gửi | Admin Hub Dự Án gửi | Trạng thái batch (Chờ duyệt / Đã xử lý)
Click batch → navigate đến /sync-review/:batchId

## Trang Review Batch (/sync-review/:batchId):
Layout 2 cột:

### Cột trái (30%) — Danh sách trang trong batch:
- Mỗi trang: Tiêu đề + trạng thái icon
- 3 trạng thái: Chưa xử lý (mặc định, trắng) | Đã duyệt (xanh ✓) | Đã từ chối (đỏ ✗)
- Click trang → preview bên phải
- Progress bar trên cùng: "5/12 trang đã xử lý"

### Cột phải (70%) — Preview nội dung trang:
- Render HTML content đầy đủ (rich text)
- Nếu trang tương tự trang Hub Tổng hiện có (similarity > 0.85): banner warning "Trang tương tự đã tồn tại" + link

### Action Bar (dưới preview):
- Nút "Duyệt" (xanh) — approve trang hiện tại, chuyển sang trang tiếp
- Nút "Từ chối" (đỏ) → mở textarea "Lý do từ chối" (bắt buộc nhập) → confirm
- Nút "Duyệt tất cả còn lại" — bulk approve trang chưa xử lý
- Nút "Hoàn tất" — submit toàn bộ decisions, quay về danh sách

## Sau hoàn tất:
- Trang Duyệt → vào DB Hub Tổng
- Trang Từ chối → Admin Hub Dự Án nhận thông báo + lý do
- Toast "Đã xử lý batch: X duyệt, Y từ chối"

## Edge cases:
- Admin đóng giữa chừng: trang chưa xử lý vẫn "chờ duyệt"
- Batch đã xử lý hết: redirect về danh sách

## Mock Data: 2 batch — 1 batch 8 trang chờ, 1 batch 5 trang đã xử lý.
```

---

<a id="prompt-9"></a>
## PROMPT 9 — Hub Tổng: MCP API Key Management (UC-08)

```
Xây dựng trang quản lý MCP API Key cho Hub Tổng. Route: /settings/api-keys

## Giao diện:

### DataTable — Danh sách API Keys:
Cột: Tên key | Quyền (badges: Read/Write/Cross-hub) | Hub được phép | Ngày tạo | Dùng cuối | Requests 7 ngày | Trạng thái | Actions
Row actions: Thu hồi

### Nút "Tạo API Key Mới" → Modal form:
- Tên key (required, ví dụ: "Claude Desktop - Team AI")
- Mô tả
- Phạm vi quyền (checkboxes): Read-only | Write | Cross-hub Search
- Hub được phép (multi-select): chọn Hub cụ thể hoặc "Tất cả"
- Rate limit: input số (default 100 requests/phút)
- Expiry date (optional date picker)
- Nút "Tạo Key"

### Modal hiển thị Key (sau khi tạo):
- QUAN TRỌNG: Hiện key đầy đủ 64 ký tự, CHỈ 1 LẦN
- Banner warning đỏ: "Hãy sao chép key ngay. Key sẽ không hiển thị lại sau khi đóng."
- Nút "Sao chép" lớn + feedback "Đã sao chép!"
- Key hiện trong monospace box, có thể select all
- Nút "Đã sao chép, đóng"

### Thu hồi Key:
- ConfirmDialog danger: "Thu hồi key [Tên]? Key sẽ ngừng hoạt động ngay lập tức."
- Sau thu hồi: row chuyển trạng thái "Đã thu hồi" (strikethrough, disabled)

## Mock Data: 3 keys — 1 active (Claude Desktop), 1 active (ChatGPT), 1 revoked.
```

---

<a id="prompt-10"></a>
## PROMPT 10 — Hub Dự Án: Layout & Navigation (UC-09, UC-10)

```
Xây dựng Layout và Navigation cho app Hub Dự Án (dùng chung cho 3 Hub: Tâm Đạo, DMD, HCNS).
Mỗi Hub có config riêng (tên, màu, subdomain) nhưng dùng chung codebase components.

## Config per Hub (env hoặc config file):
- HUB_NAME: "Tâm Đạo Y Quán" | "Đỗ Minh Đường" | "Hành Chính Nhân Sự"
- HUB_ID: "tamdao" | "dmd" | "hcns"
- PRIMARY_COLOR: emerald | blue | slate
- SUBDOMAIN: tamdao.medinet.vn | dmd.medinet.vn | hcns.medinet.vn

## Sidebar (trái, collapsible):
- Logo + Tên Hub (ở trên cùng, màu theo Hub)
- Menu items:
  1. Trang chủ Hub (icon Home)
  2. Categories (icon Folder, tree expand/collapse — TreeView component)
     - Sub-items: các category con, click → /category/:slug
  3. --- separator ---
  4. [Admin only] Tạo trang mới (icon Plus)
  5. [Admin only] Hàng chờ duyệt AI (icon CheckCircle, badge count "N")
  6. [Admin only] Nháp (icon FileText)
  7. [Admin only] Quản lý Sync (icon Upload)
  8. [Admin only] Cài đặt Hub (icon Settings)
- Sidebar nhớ expand/collapse state (localStorage)
- Viewer KHÔNG thấy menu items Admin only

## Header:
- Search bar (giữa): tìm trong Hub hiện tại
- Notification bell (badge count) + User dropdown (Tên, Role badge, Đăng xuất)

## Trang chủ Hub (/):
- Banner: "Chào mừng đến [Tên Hub]" + mô tả ngắn
- "Trang được xem nhiều nhất" — 6 cards grid
- "Cập nhật gần đây" — 5 entries timeline (tên trang, ngày sửa, người sửa)
- Categories chính — grid cards, mỗi card: tên category, số trang, icon

## URL pattern: [subdomain]/category/[slug]/[page-slug]
## Breadcrumb: Hub > Category > Tên Trang

## Mobile:
- Sidebar thành hamburger menu overlay
- Search bar collapse thành icon, expand on click

## Mock Data: 5 categories mỗi Hub, 3-5 trang mỗi category.
```

---

<a id="prompt-11"></a>
## PROMPT 11 — Hub Dự Án: Wiki Page Reader (UC-12)

```
Xây dựng trang đọc Wiki Page cho Hub Dự Án. Route: /page/:slug

## Layout 3 cột:
- Sidebar trái: navigation (đã có từ Prompt 10)
- Content chính (giữa, ~65%): nội dung Wiki
- Sidebar phải (~20%, desktop only): Table of Contents

## Content chính:

### Page Header:
- Breadcrumb: Hub > Category > Tên Trang
- Tiêu đề (H1)
- Meta row: Tác giả | Ngày tạo | Lần sửa cuối | Reading time
- Tags (badges clickable → filter pages by tag)
- Status badges:
  - "AI Generated" (tím) + tên model — nếu ai_generated=true
  - "Đã xác minh" (xanh) — nếu verified
  - "Đang chờ duyệt" (vàng) — nếu pending_review
    - Viewer thấy: "Trang này đang chờ duyệt"
    - Admin thấy thêm nút "Duyệt ngay"

### Content Body:
- Render rich HTML (output từ TipTap): headings, paragraphs, bold/italic, lists, tables, images, links
- Code blocks: syntax highlighting + nút "Copy code"
- Images: lightbox on click
- CSS print-friendly (Ctrl+P)

### Action Bar (Admin only, sticky bottom hoặc top-right):
- Nút "Chỉnh sửa" → navigate /page/:slug/edit
- Nút "Lịch sử" → navigate /page/:slug/history
- Nút "Xóa" → ConfirmDialog (nhập lại tên trang để xác nhận)

### Cuối trang:
- "Trang liên quan" — 3-5 cards gợi ý từ RAG similarity (title, snippet, score)

## Sidebar phải — Table of Contents:
- Auto-generate từ H2/H3 headings trong content
- Sticky scroll: highlight heading hiện tại khi scroll
- Click heading → smooth scroll đến section

## Trang đã xóa (404):
- "Trang này đã bị xóa hoặc không còn tồn tại"
- Search bar gợi ý tìm nội dung tương tự

## Mock Data: 3-4 trang mẫu với rich content (headings, lists, code, tables, images placeholder).
```

---

<a id="prompt-12"></a>
## PROMPT 12 — Hub Dự Án: Wiki Editor — Create & Edit (UC-13, UC-14)

```
Xây dựng Wiki Editor cho Hub Dự Án — dùng cho cả Tạo mới và Chỉnh sửa.
Route tạo mới: /page/new
Route chỉnh sửa: /page/:slug/edit (load content hiện tại)

## Layout:
Full-width (ẩn sidebar phải). Sidebar trái vẫn giữ nhưng có thể collapse.

## Form phía trên:
- **Tiêu đề** (input lớn, font-size lớn): required
  - Khi nhập → auto-suggest slug (ASCII từ tiếng Việt, hiện bên dưới input: "URL: /page/[auto-slug]")
- **Category** (Select dropdown): chọn từ danh sách category Hub
  - Có option "+ Tạo Category mới" → inline form ngay trong dropdown
- **Tags** (TagInput): autocomplete từ tags đã có, cho phép tạo tag mới
- **Trạng thái** (radio buttons, Admin only): Published | Draft

## TipTap Rich Text Editor:
Toolbar gồm:
- Text: Bold, Italic, Strikethrough, Underline
- Headings: H1, H2, H3
- Lists: Bullet list, Ordered list, Task list (checkbox)
- Insert: Link, Image (upload hoặc URL), Table, Code block, Horizontal rule, Blockquote
- History: Undo, Redo

Features:
- Placeholder text khi rỗng: "Bắt đầu viết nội dung..."
- Drag-and-drop image upload
- Paste từ Word/Google Docs: giữ heading, bold, list (strip formatting phức tạp)
- Slash commands: gõ "/" hiện menu insert nhanh (heading, list, code, image, table)
- Word count + reading time hiện cuối editor
- Markdown shortcuts: ## → H2, **text** → bold, - → bullet list

## Auto-save:
- Auto-save draft mỗi 30 giây (POST /api/pages/:id/autosave)
- Indicator: "Đã lưu tự động lúc HH:MM" hoặc "Đang lưu..." hoặc "Có thay đổi chưa lưu"
- Rời trang khi chưa lưu: browser confirm dialog "Bạn có thay đổi chưa lưu. Rời khỏi?"

## Buttons:
- "Xuất bản" (primary) — save + status published
- "Lưu nháp" (secondary) — save + status draft
- "Xem trước" — mở preview modal (render HTML như page reader)
- "Hủy" — confirm nếu có thay đổi → quay về trang trước

## Chế độ Edit (đang sửa trang hiện có):
- Load content vào editor
- Banner: "Bạn đang chỉnh sửa: [Tên trang]"
- Sau save: tạo version mới trong history, toast "Đã lưu thay đổi"
- Conflict warning (nếu có người khác đang sửa): banner "Người khác đang chỉnh sửa trang này"

## Validation:
- Tiêu đề trùng: warning (không chặn) "Có trang tương tự: [link]"
- Tiêu đề trống: block submit

## Mock: TipTap editor với đầy đủ toolbar, auto-save indicator, preview modal.
```

---

<a id="prompt-13"></a>
## PROMPT 13 — Hub Dự Án: RAG Search (UC-11)

```
Xây dựng tính năng RAG Search cho Hub Dự Án.

## Search Bar (trong Header — đã có từ Prompt 10):
- Debounce 300ms
- Loading spinner khi đang query
- Clear button (X)
- Hỗ trợ tiếng Việt có dấu và không dấu
- Enter hoặc click icon → navigate sang /search?q=[query]

## Trang Search Results (/search?q=):
### Header:
- Search bar lớn (pre-filled query)
- Tổng số kết quả + thời gian response (ví dụ: "12 kết quả trong 0.6s")

### Result List:
Mỗi result card:
- Tiêu đề (link → /page/:slug, bold)
- Category badge
- Đoạn trích 2-3 dòng với highlight từ khóa (mark tag, background yellow)
- Score indicator: progress bar nhỏ hoặc relevance dots
- Tags (nếu có)
- Meta: Ngày cập nhật | Tác giả

### Sidebar filter (desktop):
- Category filter (checkboxes)
- Tags filter (checkboxes, top 10)
- Trạng thái: Tất cả | Published | Verified

### States:
- Chưa nhập query: "Nhập từ khóa hoặc câu hỏi để tìm kiếm trong [Tên Hub]"
- Loading: skeleton cards (3-5)
- Không có kết quả (score < 0.5): EmptyState "Không tìm thấy nội dung phù hợp trong Hub này"
- ChromaDB chưa có data: "Nội dung Hub chưa được index — liên hệ Admin"

### Click kết quả:
- Navigate đến trang Wiki
- Scroll đến đoạn liên quan nhất (nếu có anchor)

## LƯU Ý: Search Hub Dự Án CHỈ tìm trong Hub đó — KHÔNG có option cross-hub cho Viewer.

## Mock Data: 15 kết quả mẫu với scores 0.95 → 0.52, mix categories và tags.
```

---

<a id="prompt-14"></a>
## PROMPT 14 — Hub Dự Án: Categories & Tags Management (UC-16)

```
Xây dựng trang quản lý Categories & Tags cho Hub Dự Án (Admin only).
Route: /settings/categories-tags

## Layout: 2 tabs — "Categories" | "Tags"

## Tab Categories:
### Cây Category (TreeView):
- Hiển thị dạng tree, expand/collapse
- Mỗi node: Tên category + số trang + actions (Sửa, Xóa)
- Drag-and-drop để sắp xếp thứ tự (reorder)
- Confirm nếu kéo thả ảnh hưởng > 10 trang

### Thêm Category:
- Nút "+ Thêm Category" → inline form hoặc modal:
  - Tên category (required)
  - Parent category (dropdown, optional → sub-category)
  - Mô tả (optional)

### Sửa Category:
- Click "Sửa" → inline edit hoặc modal
- Đổi tên, đổi parent

### Xóa Category:
- Nếu category còn trang: modal hỏi "Di chuyển trang vào category nào?" (dropdown) trước khi xóa
- Nếu rỗng: confirm đơn giản

## Tab Tags:
### Danh sách Tags:
- Grid hoặc list: Tên tag | Số trang sử dụng | Actions (Sửa tên, Xóa, Merge)
- Sắp xếp theo số trang sử dụng (nhiều nhất trên)

### Merge Tags:
- Multi-select tags → nút "Merge"
- Modal: chọn tag đích (hoặc nhập tên mới)
- Confirm: "Merge [Tag A], [Tag B] thành [Tag đích]? Tất cả X trang sẽ được cập nhật."

### Xóa Tag:
- Confirm: "Xóa tag [Tên]? Tag sẽ bị gỡ khỏi X trang."

## Mock Data: 8 categories (2 cấp), 20 tags.
```

---

<a id="prompt-15"></a>
## PROMPT 15 — Hub Dự Án: Version History & Restore (UC-17, UC-18)

```
Xây dựng trang Version History cho Wiki Page. Route: /page/:slug/history
Chỉ Admin Hub Dự Án truy cập.

## Layout:

### Timeline (cột trái, ~35%):
- Danh sách versions (mới nhất trên cùng)
- Mỗi version: Timestamp | Người sửa | Ghi chú thay đổi ngắn
- Version hiện tại có badge "Hiện tại"
- Checkbox để chọn 2 version → enable nút "So sánh"

### Content View (cột phải, ~65%):
- Default: hiện nội dung version đang chọn (read-only)
- Click version → load nội dung version đó

### So sánh 2 versions (Diff View):
- Chọn 2 versions → click "So sánh"
- DiffViewer component: toggle Side-by-side / Inline
- Thêm = highlight xanh, Xóa = highlight đỏ
- Header: "Version [A] vs Version [B]"

### Khôi phục:
- Nút "Khôi phục version này" (màu cam) khi xem 1 version cũ
- ConfirmDialog: "Khôi phục trang về version [ID] (ngày [date])? Nội dung hiện tại sẽ được lưu thành version mới trước khi khôi phục."
- Sau khôi phục: tạo version mới, re-embed ChromaDB, toast "Đã khôi phục", navigate về page reader

## Edge case:
- Trang chỉ có 1 version: "Chưa có lịch sử thay đổi"

## Mock Data: 1 trang với 5 versions, nội dung khác nhau giữa các version.
```

---

<a id="prompt-16"></a>
## PROMPT 16 — Hub Dự Án: Sync Management (UC-19, UC-20)

```
Xây dựng trang Quản lý Sync cho Hub Dự Án (Admin only). Route: /sync

## Layout: 2 tabs — "Tạo Sync mới" | "Lịch sử Sync"

## Tab "Tạo Sync mới":
### Danh sách trang đủ điều kiện sync:
- Trang published + chưa sync hoặc đã sửa từ lần sync cuối
- DataTable: Checkbox | Tiêu đề | Ngày sửa cuối | Trạng thái sync trước (badge)
- Nút "Chọn tất cả" / "Bỏ chọn tất cả"
- Selected count: "Đã chọn X trang"

### Nút "Gửi Sync lên Hub Tổng":
- ConfirmDialog: "Gửi X trang lên Hub Tổng để duyệt? Các trang sẽ bị khóa sửa cho đến khi có kết quả."
- Sau gửi: toast "Batch Sync đã gửi, đang chờ Admin Hub Tổng duyệt"

### States:
- Không có trang đủ điều kiện: EmptyState "Không có trang mới hoặc thay đổi cần sync"
- Đang có batch chờ duyệt: disable nút gửi, banner "Đang có batch chờ duyệt — không thể gửi batch mới"

## Tab "Lịch sử Sync":
### DataTable các batch đã gửi:
Cột: Ngày gửi | Số trang | Trạng thái batch (Chờ duyệt / Đã xử lý) | Admin Hub Tổng xử lý

### Click batch → expand chi tiết:
- Danh sách trang trong batch: Tiêu đề | Kết quả (Duyệt ✓ / Từ chối ✗ kèm lý do)
- Trang từ chối: hiện lý do từ chối (text đỏ) + nút "Sửa và thêm vào batch mới"

## Trạng thái sync trên mỗi trang Wiki:
- Badges: "Chưa sync" | "Đang chờ duyệt" (vàng) | "Đã duyệt" (xanh) | "Bị từ chối" (đỏ, kèm lý do)
- Trang "Đang chờ duyệt": khóa nút Chỉnh sửa

## Mock Data: 15 trang eligible, 2 batch history (1 đã xử lý mix approve/reject, 1 đang chờ).
```

---

<a id="prompt-17"></a>
## PROMPT 17 — Hub Dự Án: AI Post Review Queue (UC-23, UC-36)

```
Xây dựng trang Hàng Chờ Duyệt Bài AI cho Hub Dự Án (Admin only). Route: /ai-review

## Sidebar badge:
- "Hàng chờ duyệt AI" menu item có badge đỏ đếm số bài pending

## Layout 2 cột:

### Cột trái (~35%) — Danh sách bài chờ:
- Mỗi entry: Tiêu đề | Người đăng | Thời gian | Preview ngắn (2 dòng)
- Click → load preview bên phải
- Badge "AI Generated" trên mỗi entry

### Cột phải (~65%) — Preview bài:
- Render HTML đầy đủ
- Meta: nguồn (Claude model), ngày tạo, người đăng
- Nhãn "Đang chờ duyệt" ở header

### Action Bar (dưới preview):
3 lựa chọn:
1. **"Duyệt & Xuất bản"** (xanh): approve → status chuyển published + verified, toast thành công
2. **"Chỉnh sửa rồi Duyệt"** (vàng): navigate sang editor với content pre-loaded → sau save → published
3. **"Từ chối"** (đỏ): mở textarea nhập lý do (required) → confirm → status về draft, thông báo người tạo

## Notification:
- Header bell icon: badge count tổng (AI review + sync + ...)
- Dropdown notification list khi click bell:
  - "Có N bài AI chờ duyệt trong Hub [Tên]"
  - Click → navigate /ai-review

## Empty state: "Không có bài AI nào đang chờ duyệt"

## Mock Data: 4 bài AI pending với nội dung khác nhau (bài thuốc, chính sách, SOP...).
```

---

<a id="prompt-18"></a>
## PROMPT 18 — AI Post: Đăng Bài Từ Claude (UC-21, UC-22, UC-24, UC-25)

```
Xây dựng tính năng AI Post — đăng nội dung từ Claude lên Hub Wiki.
Đây là component/page mô phỏng giao diện chat với Claude + tính năng đăng wiki.

## Trang Chat Demo (/ai-chat):
Mô phỏng giao diện chat đơn giản để demo flow AI Post:
- Chat messages: user (phải) + Claude response (trái)
- Mỗi Claude response có:
  - Nút "Đăng lên Wiki" ở dưới response (chỉ hiện khi role = Admin)
  - Bôi chọn text → floating button "Đăng đoạn này lên Wiki" xuất hiện gần vùng chọn
    - Chọn < 50 ký tự: floating button không hiện

## Modal Review (mở khi click "Đăng lên Wiki"):
Layout modal size XL:

### Cột trái (~50%) — Preview nội dung:
- Markdown rendered thành HTML
- Editable: cho phép sửa trực tiếp trước khi đăng
- Nếu bôi chọn đoạn: chỉ hiện đoạn đã chọn

### Cột phải (~50%) — Form metadata:
- **Hub đích**: dropdown (auto-select Hub hiện tại nếu đang trong Hub)
- **Tiêu đề**: input (required)
- **Category**: dropdown (fetch từ API Hub đích)
- **Tags**: TagInput (autocomplete)

### Duplicate Detection:
- Sau nhập tiêu đề → auto-check similarity
- Nếu similarity > 0.85: banner warning
  - "Trang tương tự đã tồn tại: [Tên trang] (85% trùng khớp)"
  - 2 options: "Đăng bài mới" | "Thêm section vào trang này" (→ Append mode)

### Append Section Mode (UC-25):
- Preview side-by-side: Trang hiện có (bên trái) | Section mới (bên phải, highlight)
- Dropdown chọn vị trí: "Cuối trang" | "Sau [heading cụ thể]"
- Nút "Thêm section"

### Action Buttons:
- "Đăng bài" (primary) → POST, status pending_review, toast + link
- "Lưu nháp" (secondary) → status draft, toast "Đã lưu nháp"
- "Hủy" → confirm nếu đã nhập data

### Validation:
- Rate limit 20 bài/ngày: "Đã đạt giới hạn đăng bài hôm nay (20/20)"
- Content > 50,000 ký tự: "Nội dung quá dài, hãy chia nhỏ"
- Thiếu tiêu đề: block submit

## Mock Data: 5 chat messages, 2 Claude responses có nội dung dài.
```

---

<a id="prompt-19"></a>
## PROMPT 19 — Hub HCNS: Onboarding Checklist (UC-33)

```
Xây dựng tính năng Onboarding cho Hub HCNS (hcns.medinet.vn).

## Trang "Chào mừng" (/onboarding):
- Hiện lần đầu đăng nhập cho Viewer mới
- Có thể tìm lại qua sidebar hoặc link

### Header:
- "Chào mừng [Tên] đến với Medinet!"
- Mô tả: "Hoàn thành checklist sau để làm quen với công ty"

### Checklist (card list, mỗi item là 1 card):
1. ☐ Đọc Nội quy lao động → link /page/noi-quy-lao-dong
2. ☐ Xem Sơ đồ tổ chức → link /page/so-do-to-chuc
3. ☐ Đọc Mô tả công việc vị trí của bạn → link /page/jd-[vi-tri]
4. ☐ Xem quy trình nghỉ phép → link /page/quy-trinh-nghi-phep
5. ☐ Xem chính sách lương thưởng → link /page/chinh-sach-luong (nếu có quyền)

Mỗi card:
- Checkbox (click-to-toggle "Đã đọc")
- Tiêu đề tài liệu
- Mô tả ngắn
- Link "Đọc ngay →"
- Sau đọc + tick: check xanh, card mờ nhẹ

### Progress:
- Progress bar trên cùng: "3/5 hoàn thành"
- Khi hoàn thành 100%: confetti animation + "Onboarding hoàn tất! Chúc bạn làm việc vui vẻ"

### Admin HCNS view (/settings/onboarding):
- DataTable nhân viên mới: Tên | Ngày tạo TK | Tiến trình (3/5) | Trạng thái (Đang thực hiện / Hoàn tất)

## State: lưu per-user, không mất khi đăng xuất (persist server-side, mock với localStorage).
```

---

<a id="prompt-20"></a>
## PROMPT 20 — Hub Dự Án: Embed & Index Management (UC-35)

```
Xây dựng trang quản lý Embed & Index cho Hub Dự Án (Admin only).
Route: /settings/index-management

## Giao diện:

### Overview Cards:
- "Tổng trang đã embed": X / Y trang published
- "Lần embed cuối": timestamp
- "Trạng thái ChromaDB": Connected (xanh) / Error (đỏ)

### DataTable — Trạng thái embed từng trang:
Cột: Tiêu đề | Trạng thái (badges) | Lần embed cuối | Chunks | Actions
Trạng thái:
- "Đã embed" (xanh)
- "Chờ embed" (vàng, spinning)
- "Lỗi embed" (đỏ) + tooltip lý do lỗi
Actions: Retry (cho trang lỗi) | Re-embed (cho trang đã embed)

### Nút "Re-embed toàn bộ":
- ConfirmDialog: "Re-embed toàn bộ Y trang? Quá trình chạy background."
- Sau confirm: hiện progress bar "Đang embed: X/Y trang" + ETA
- Hoàn thành: toast "Đã embed Y/Y trang — RAG sẵn sàng"

### Auto-embed indicator:
- Banner info: "Mỗi trang tạo/sửa sẽ được embed tự động trong < 10 giây"

## Mock Data: 30 trang — 25 đã embed, 3 chờ embed, 2 lỗi.
```

---

<a id="prompt-21"></a>
## PROMPT 21 — Notification System

```
Xây dựng hệ thống Notification dùng chung cho cả Hub Tổng và Hub Dự Án.

## Header Bell Icon:
- Icon bell ở header (đã có từ layout)
- Badge đỏ hiện số thông báo chưa đọc (max hiện "99+")

## Notification Dropdown (click bell):
- Panel dropdown dưới bell icon
- Header: "Thông báo" + link "Đánh dấu tất cả đã đọc"
- List notifications (max 10, scroll):
  Mỗi notification:
  - Icon theo loại (AI = robot, Sync = upload, Page = file, User = user)
  - Nội dung ngắn (1-2 dòng)
  - Thời gian (relative: "5 phút trước", "Hôm qua")
  - Chưa đọc: background highlight nhẹ, dot xanh
  - Click → navigate đến trang liên quan + đánh dấu đã đọc

## Loại thông báo:

### Hub Dự Án (Admin):
- "Có N bài AI chờ duyệt" → /ai-review
- "Trang [Tên] đã được embed thành công" → /page/:slug
- "Sync batch [ID]: X trang duyệt, Y trang từ chối" → /sync
- "Trang [Tên] bị conflict — người khác đang sửa" → /page/:slug

### Hub Tổng (Admin):
- "Sync mới từ Hub [Tên]: N trang chờ duyệt" → /sync-review/:batchId
- "User mới [Tên] đã đặt mật khẩu và đăng nhập Hub [Tên]"
- "API Key [Tên] sắp hết hạn trong 7 ngày" → /settings/api-keys

## Zustand Store: notifications[], unreadCount, markAsRead(id), markAllRead(), fetchNotifications()

## Mock Data: 8-12 notifications, mix đã đọc/chưa đọc, các loại khác nhau.
```

---

<a id="prompt-22"></a>
## PROMPT 22 — Mock API & Data Layer

```
Xây dựng Mock API layer cho toàn bộ frontend Medinet Wiki.
Sử dụng MSW (Mock Service Worker) hoặc custom mock trong packages/api-client/.
Mục đích: frontend hoạt động hoàn chỉnh không cần backend thật.

## API Client (packages/api-client/):
- Axios instance với base URL config per app
- Request interceptor: gắn JWT token từ auth store
- Response interceptor: handle 401 → redirect login, 403 → error page
- TypeScript types cho tất cả API responses

## Mock Endpoints cần tạo:

### Auth:
- POST /api/auth/login → { token, user }
- POST /api/auth/logout
- GET /api/auth/me → { user, role, hub_id }

### Pages (Wiki):
- GET /api/hubs/:hubId/pages → paginated list
- GET /api/hubs/:hubId/pages/:slug → page detail
- POST /api/hubs/:hubId/pages → create page
- PUT /api/hubs/:hubId/pages/:id → update page
- DELETE /api/hubs/:hubId/pages/:id → soft delete
- GET /api/hubs/:hubId/pages/:id/versions → version history
- POST /api/hubs/:hubId/pages/:id/restore/:versionId → restore

### Search:
- GET /api/hubs/:hubId/search?q=&top_k= → RAG search trong Hub
- GET /api/hub-total/search?q= → cross-hub search (Hub Tổng only)

### Categories & Tags:
- GET /api/hubs/:hubId/categories → tree
- POST/PUT/DELETE /api/hubs/:hubId/categories/:id
- GET /api/hubs/:hubId/tags
- POST /api/hubs/:hubId/tags/merge

### Users (Hub Tổng):
- GET /api/hubs/:hubId/users → user list
- POST /api/hubs/:hubId/users → invite user
- PUT /api/hubs/:hubId/users/:id/role → change role
- PUT /api/hubs/:hubId/users/:id/disable → disable

### Hub Registry (Hub Tổng):
- GET /api/hubs → list hubs
- POST /api/hubs → create hub
- PUT /api/hubs/:id → update hub
- POST /api/hubs/:id/test-connection → test DB connection

### Sync:
- GET /api/hubs/:hubId/sync/eligible → eligible pages
- POST /api/hubs/:hubId/sync/batches → create batch
- GET /api/hubs/:hubId/sync/batches → batch history
- GET /api/sync-review/batches → pending batches (Hub Tổng)
- PUT /api/sync-review/batches/:id/pages/:pageId → approve/reject

### AI Post:
- POST /api/hubs/:hubId/ai-posts → create AI post (pending_review)
- GET /api/hubs/:hubId/ai-posts/pending → pending review list
- PUT /api/hubs/:hubId/ai-posts/:id/approve
- PUT /api/hubs/:hubId/ai-posts/:id/reject
- POST /api/hubs/:hubId/pages/:id/sections → append section
- GET /api/hubs/:hubId/pages/suggest?content= → duplicate detection

### MCP API Keys (Hub Tổng):
- GET /api/mcp/api-keys
- POST /api/mcp/api-keys → create (return key once)
- DELETE /api/mcp/api-keys/:id → revoke

### Audit Log (Hub Tổng):
- GET /api/audit-log?from=&to=&action=&user=&hub= → paginated

### Notifications:
- GET /api/notifications → list
- PUT /api/notifications/:id/read
- PUT /api/notifications/read-all

### Embed/Index:
- GET /api/hubs/:hubId/index/status → embed status per page
- POST /api/hubs/:hubId/index/reindex-all → trigger full re-embed

## Mock Data:
Tạo file mock data fixtures với:
- 3 Hub (Tâm Đạo, DMD, HCNS) + 5-8 categories mỗi Hub + 30-50 pages mỗi Hub
- 15 users (mix roles)
- 200 audit log entries
- 3 API keys
- 2 sync batches
- 4 AI posts pending
- Rich page content (headings, lists, tables, code blocks)

## React Query Integration:
- Custom hooks: usePages(), usePage(slug), useSearch(query), useUsers(hubId), etc.
- Proper loading/error states
- Optimistic updates cho mutations
```

---

## THỨ TỰ XÂY DỰNG GỢI Ý

| Giai đoạn | Prompts | Mô tả |
|-----------|---------|-------|
| **1. Foundation** | 0, 1, 22 | Setup monorepo, UI library, Mock API |
| **2. Auth & Layout** | 2, 10 | Login, route protection, sidebar, header |
| **3. Core Wiki** | 11, 12, 13 | Đọc trang, Editor, Search |
| **4. Hub Tổng Admin** | 3, 4, 5, 9 | Dashboard, Users, Registry, API Keys |
| **5. Hub Tổng Advanced** | 6, 7, 8 | Cross-hub Search, Audit Log, Sync Review |
| **6. Hub Dự Án Advanced** | 14, 15, 16, 17 | Categories, History, Sync, AI Review |
| **7. AI Post** | 18 | Đăng bài từ Claude |
| **8. Đặc thù** | 19, 20, 21 | Onboarding HCNS, Embed Management, Notifications |

---

> **Tips sử dụng:**
> - Copy từng prompt vào AI tool (Claude, Cursor, v0.dev, Bolt...)
> - Sau mỗi prompt, review output rồi chạy prompt tiếp theo
> - Prompt 22 (Mock API) nên chạy song song với Prompt 1 ở giai đoạn 1
> - Có thể chia nhỏ prompt nếu AI tool có giới hạn context
> - Luôn reference kết quả prompt trước khi chạy prompt sau
