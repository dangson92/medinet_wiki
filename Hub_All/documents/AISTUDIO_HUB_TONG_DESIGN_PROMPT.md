# PROMPT CHO AI STUDIO — THIẾT KẾ FRONTEND HUB TỔNG (wiki.medinet.vn)

> Copy toàn bộ nội dung từ dấu `═══` bên dưới vào AI Studio / Claude / Gemini để thiết kế UI/UX.

---

## PROMPT (copy từ đây)

═══════════════════════════════════════════════════════════

You are a senior UI/UX designer. Design a professional web application UI
using the following design system. Every component must strictly follow
these specifications — no improvisation.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DESIGN SYSTEM SPECIFICATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

AESTHETIC
- Apple-inspired: clean, airy, high contrast, precise spacing
- Glassmorphism surfaces: semi-transparent white (rgba 255,255,255,0.6)
  with backdrop-blur 24px
- Colored shadows on interactive elements (not plain gray shadows)
- Smooth micro-interactions on every hover/active state

─── COLORS ───────────────────────────────
Brand gradient:    linear-gradient(135deg, #6366f1 → #a855f7)  [Indigo→Purple]
Brand shadow:      rgba(99,102,241,0.30) — used as box-shadow on primary CTA
Accent (links/info): #3b82f6 (Blue 500)
Success:           #10b981
Warning:           #f59e0b
Danger:            #ef4444

Gray scale (cool-tinted, Slate-based):
  50:#f8fafc  100:#f1f5f9  200:#e2e8f0  300:#cbd5e1
  400:#94a3b8  500:#64748b  600:#475569  700:#334155
  800:#1e293b  900:#0f172a

Surface layers:
  Base white:     #ffffff
  Card:           rgba(255,255,255,0.95)
  Overlay:        rgba(255,255,255,0.60)  ← sidebar/header bg
  Sunken:         #f8fafc  ← modal footer, settings bg
  Border default: rgba(226,232,240,0.80)
  Border subtle:  rgba(226,232,240,0.50)

─── TYPOGRAPHY ───────────────────────────
Font: -apple-system, "Segoe UI", Inter, Roboto — system stack
Sizes: 10/12/14/16/18/20/24/30px
Weights: Regular 400, Medium 500, Semibold 600, Bold 700
Letter spacing: headings use -0.015em (H1) to -0.005em (H3)
H1: 24px Semibold / H2: 20px Semibold / H3: 18px Semibold
Label: 14px Medium / Caption: 10px 700 Uppercase tracking-wider

─── SPACING ──────────────────────────────
4px base grid. Use multiples: 4/6/8/10/12/16/20/24/28/32/40/48px

─── BORDER RADIUS ────────────────────────
Input/Tag: 10px  |  Button/NavItem: 16px  |  Card: 16px
Modal: 20px  |  Avatar/Badge: 9999px

─── SHADOWS ──────────────────────────────
sm:  0 1px 3px rgba(0,0,0,0.10)
md:  0 4px 6px rgba(0,0,0,0.10)
lg:  0 10px 15px rgba(0,0,0,0.10)
xl:  0 20px 25px rgba(0,0,0,0.10)
2xl: 0 25px 50px rgba(0,0,0,0.25)
primary: 0 8px 24px rgba(99,102,241,0.30)   ← on indigo buttons
accent:  0 8px 24px rgba(59,130,246,0.30)   ← on blue buttons

─── SIDEBAR ──────────────────────────────
Width: 256px expanded, 80px collapsed
Background: rgba(255,255,255,0.60) + backdrop-blur(24px)
Border-right: 1px solid rgba(226,232,240,0.50)
Nav item active: brand gradient bg + white text + shadow-primary
Nav item hover: rgba(241,245,249,0.80) bg
Nav item: 16px border-radius, px:12px py:10px, 14px Medium text
Badge on nav: red dot (18x18px) with white border 2px
Section labels: 10px, 700, uppercase, #94a3b8, tracking 0.12em

─── MODAL ────────────────────────────────
Overlay: rgba(0,0,0,0.50) + backdrop-blur(8px)
Modal bg: rgba(255,255,255,0.95) + blur
Border-radius: 20px, box-shadow: 2xl
Header: sticky, 24px padding, border-bottom border-subtle
  → Title: 18px Semibold, Close button: 32x32 ghost icon button
Body: 24px padding, scrollable
Footer: sunken bg (#f8fafc), right-aligned buttons, border-top

─── BUTTONS ──────────────────────────────
Primary:  brand gradient bg, white text, shadow-primary
          hover → shift darker + translateY(-1px) + stronger shadow
Accent:   #3b82f6 solid, white text, shadow-accent
Secondary: #f1f5f9 bg, gray-700 text, border border-default
Ghost:    transparent, gray text, hover → #f1f5f9 bg
Danger:   #ef4444 solid, white text
Border-radius: 16px on all buttons
Padding: sm=6/12px, md=10/16px, lg=12/24px

─── INPUTS ───────────────────────────────
Background: #f8fafc (slightly off-white)
Border: 1px rgba(226,232,240,0.80), radius 10px
Focus: border #3b82f6, box-shadow 0 0 0 3px rgba(59,130,246,0.12), bg white
Placeholder: #94a3b8
With icon: left-icon 40px offset, icon color #94a3b8
Error state: border #ef4444, bg rgba(239,68,68,0.06)
Search input: pill shape (9999px radius), bg rgba(241,245,249,0.80)

─── TOGGLE/SWITCH ────────────────────────
Track: 40x22px, radius 9999px
Off: #cbd5e1, On: #3b82f6
Thumb: 16x16px white circle, translateX(18px) when on
Transition: 200ms spring easing

─── CARDS ────────────────────────────────
bg: rgba(255,255,255,0.95), border: border-subtle, radius 16px
Hover: box-shadow md + border-default
Glass variant: bg rgba(255,255,255,0.60) + backdrop-blur(24px)

─── TABS ─────────────────────────────────
Underline style: 2px accent bottom indicator, animates with scaleX
Pill style: container bg #f1f5f9, active tab bg white + shadow-sm
Both: 14px Medium, inactive gray-400, active accent/primary

─── SETTINGS PAGE ────────────────────────
Layout: 220px left nav + flex-1 content area
Nav items: same style as sidebar nav items (accent active state)
Content: max-width 640px, sections separated by border-top + pt-8
Row pattern: flex justify-between, label left + control right,
             border-bottom border-subtle between rows

─── MICRO-INTERACTIONS ───────────────────
All transitions: 150ms cubic-bezier(0.4,0,0.2,1)
Hover buttons: translateY(-1px) + shadow increase
Modal appear: scale(0.96)→scale(1) + translateY(4px)→0, 200ms spring
Dropdown appear: scale(0.97)→scale(1) + translateY(-4px)→0
Toast: fade-up animation (translateY 8px → 0)
Toggle thumb: spring easing (cubic-bezier 0.34,1.56,0.64,1)
Sidebar collapse: width transition 300ms ease-in-out

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[SCREEN TO DESIGN]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Thiết kế giao diện frontend hoàn chỉnh cho ứng dụng web **Medinet Wiki — Hub Tổng** (wiki.medinet.vn).

Đây là **Admin Dashboard** quản trị trung tâm của hệ thống Wiki nội bộ đa Hub cho công ty Medinet (y tế, dược liệu). Chỉ có **một vai trò duy nhất**: Admin Hub Tổng.

---

## THÔNG TIN CHUNG

**Tên ứng dụng:** Medinet Wiki — Quản trị trung tâm
**URL:** wiki.medinet.vn
**Người dùng duy nhất:** Admin Hub Tổng (không có Viewer, không có Đăng ký)
**Ngôn ngữ UI:** Tiếng Việt

**Nguyên tắc thiết kế:**
- Giao diện quản trị chuyên nghiệp, tối giản, sạch
- **Ít màu sắc** — chủ yếu dùng trắng, xám, và 1 màu chủ đạo (indigo/xanh navy)
- **Không dùng icon decorative** — chỉ dùng text label và badge để phân biệt trạng thái
- Typography rõ ràng, hierarchy tốt
- Responsive (desktop first, hỗ trợ tablet)
- Mật độ thông tin cao nhưng không rối

**Layout tổng thể:**
- Sidebar cố định bên trái (width ~240px) + Header trên (height ~56px) + Main content
- Sidebar có thể collapse thành narrow mode (~64px) khi cần
- Content area có padding 24px

---

## CÁC TRANG CẦN THIẾT KẾ

### TRANG 1 — ĐĂNG NHẬP (UC-01)

**Mô tả:** Trang duy nhất cho Admin đăng nhập. Không có đăng ký.

**Yêu cầu UI:**
- Layout full-screen, card đăng nhập ở giữa (max-width ~400px)
- Tiêu đề card: **"Quản trị Medinet Wiki"** — hiện rõ ràng để phân biệt với các subdomain Hub khác
- Subtitle: *"Hệ thống quản trị trung tâm — chỉ dành cho quản trị viên"*
- Form: trường Email + trường Mật khẩu (có toggle ẩn/hiện) + checkbox "Ghi nhớ đăng nhập" + nút "Đăng nhập"
- **Không có** link "Đăng ký" hay "Quên mật khẩu"
- Trạng thái lỗi: inline error dưới form khi sai mật khẩu — *"Email hoặc mật khẩu không đúng"*
- Trạng thái khóa: sau 5 lần sai — *"Tài khoản bị khóa 15 phút"* + countdown
- Trang 403: khi user thường cố truy cập — *"Trang này chỉ dành cho quản trị viên hệ thống"*

---

### TRANG 2 — SIDEBAR + HEADER (Layout chung)

**Sidebar menu items (text only, không icon decorative):**
1. Dashboard
2. Tìm kiếm Cross-Hub
3. *(divider)*
4. Quản lý User
5. Hub Registry
6. *(divider)*
7. Hàng đợi Sync ← badge đỏ hiện số batch đang chờ (ví dụ: "3")
8. Audit Log
9. *(divider)*
10. MCP API Keys

**Footer sidebar:** Tên Admin + Email nhỏ + nút "Đăng xuất"

**Header:**
- Trái: Breadcrumb tự động theo route (ví dụ: "Dashboard" hoặc "Quản lý User")
- Phải: ô tìm kiếm nhanh + badge thông báo (số unread) + tên Admin (click → dropdown Đăng xuất)

---

### TRANG 3 — DASHBOARD (UC-02)

**Mô tả:** Tổng quan toàn hệ thống — Admin thấy ngay nhiệm vụ cần xử lý.

**Section 1 — Thống kê nhanh (4 ô ngang hàng):**
- Tổng trang Wiki toàn hệ thống: **270 trang**
- Hub đang hoạt động: **3 / 4 Hub**
- User active tháng này: **47 người**
- Sync chờ duyệt: **5 trang** ← ô này nổi bật hơn (border hoặc background khác) khi > 0, click → vào Hàng đợi Sync

**Section 2 — Bảng Hub Overview:**
Bảng hiện danh sách Hub, sắp xếp theo cập nhật gần nhất lên trên:

| Tên Hub | Subdomain | Số trang | Cập nhật gần nhất | Trạng thái | Sync chờ |
|---------|-----------|----------|-------------------|------------|----------|
| Tâm Đạo Y Quán | tamdao.medinet.vn | 127 trang | 2 giờ trước | Hoạt động | 3 trang |
| Đỗ Minh Đường | dmd.medinet.vn | 89 trang | 1 ngày trước | Hoạt động | — |
| HCNS | hcns.medinet.vn | 54 trang | 3 ngày trước | Hoạt động | 2 trang |
| Test Hub | test.medinet.vn | 0 trang | — | Không hoạt động | — |

- Click tên Hub hoặc subdomain → mở tab mới đến subdomain Hub đó
- Hub "Không hoạt động": hiển thị mờ, text gạch chân hoặc italic

**Section 3 — 2 cột:**

*Cột trái — "Hoạt động gần đây":*
Timeline dạng danh sách 10 entries:
- `[thời gian]` — `[Tên người dùng]` `[hành động]` trang `"[Tên trang]"` trong Hub `[Tên Hub]`
- Hành động của AI Agent: prefix **[AI Agent]** thay vì tên user, hiện khác biệt
- Ví dụ:
  - *"2 phút trước — Nguyễn Văn A tạo mới trang "Phác đồ trị đau dạ dày" trong Hub Đỗ Minh Đường"*
  - *"15 phút trước — [AI Agent] cập nhật trang "Quy trình onboarding" trong Hub HCNS"*
- Link "Xem tất cả →" ở cuối → vào Audit Log

*Cột phải — "Sync chờ duyệt":*
- Nếu có: danh sách card compact cho mỗi batch pending:
  - Hub nguồn + số trang + thời gian gửi + tên Admin Hub Dự Án gửi
  - Nút "Duyệt ngay →" → vào trang Sync Review
- Nếu không có: text *"Không có sync nào đang chờ"*

---

### TRANG 4 — QUẢN LÝ USER HUB DỰ ÁN (UC-04)

**Mô tả:** Admin Hub Tổng tạo tài khoản và phân quyền user cho từng Hub Dự Án riêng biệt.

**Layout:**
- Tabs ngang: **Tâm Đạo Y Quán** | **Đỗ Minh Đường** | **HCNS** (mỗi tab có số user, ví dụ: "Tâm Đạo (12)")
- Mỗi tab quản lý user độc lập

**Toolbar (trong mỗi tab):**
- Trái: ô tìm kiếm theo tên/email + dropdown filter "Tất cả quyền / Admin / Viewer"
- Phải: nút "Thêm User"

**Bảng danh sách user:**
| Tên | Email | Quyền | Ngày tạo | Đăng nhập cuối | Trạng thái | Thao tác |
|-----|-------|-------|----------|----------------|------------|----------|
| Nguyễn Văn A | nva@medinet.vn | Admin | 01/01/2025 | 2 giờ trước | Hoạt động | Chỉnh quyền / Vô hiệu hóa |
| Trần Thị B | ttb@medinet.vn | Viewer | 15/02/2025 | Chưa đăng nhập | Hoạt động | Chỉnh quyền / Vô hiệu hóa / Gửi lại email mời |
| Lê Minh C | lmc@medinet.vn | Viewer | 10/03/2025 | 5 ngày trước | Đã vô hiệu | Kích hoạt lại |

- Badge quyền: "Admin" (đậm hơn) / "Viewer" (nhạt hơn) — không dùng màu sắc rực rỡ
- Badge trạng thái: "Hoạt động" / "Đã vô hiệu" — text only hoặc badge nhẹ

**Modal "Thêm User Mới":**
- Tiêu đề: "Thêm user vào Hub [Tên Hub]"
- Fields: Tên đầy đủ + Email + Quyền (radio: Admin Hub Dự Án / Viewer)
- Note: *"User sẽ nhận email mời đặt mật khẩu tại [subdomain]. Link có hiệu lực 24 giờ."*
- Buttons: "Hủy" + "Tạo & Gửi Email Mời"

**Modal "Chỉnh Quyền":**
- Hiện tên + email + dropdown đổi quyền
- Confirm: *"Thay đổi quyền Nguyễn Văn A từ Viewer → Admin Hub Dự Án?"*

**Xác nhận vô hiệu hóa:**
- Dialog đơn giản: *"Vô hiệu hóa tài khoản Trần Thị B? User sẽ không thể đăng nhập Hub này, dữ liệu giữ nguyên."*
- Buttons: "Hủy" + "Vô hiệu hóa"

---

### TRANG 5 — HUB REGISTRY (UC-05)

**Mô tả:** Thêm, sửa, bật/tắt Hub Dự Án — không cần sửa code.

**Danh sách Hub:**
Bảng: Tên Hub | Mã Hub | Subdomain | Trạng thái | Số trang | Số user | Ngày tạo | Thao tác (Sửa / Tắt Hub)

**Nút "Thêm Hub Mới" → Modal form:**
Fields:
- Tên Hub (ví dụ: Tâm Đạo Y Quán)
- Mã Hub (lowercase, ví dụ: tamdao — auto sinh từ tên)
- Subdomain (auto-fill: tamdao.medinet.vn — editable)
- Mô tả
- *(Section: Kết nối Database)*
- DB Host / DB Port / DB Name / DB User / DB Password
- *(Section: ChromaDB)*
- ChromaDB Collection (auto-suggest: col:tamdao)
- Nút inline "Test Kết Nối" — hiện kết quả ngay trong form:
  - Thành công: ✓ *"Kết nối thành công — PostgreSQL 16.2"*
  - Thất bại: ✗ *"Kết nối thất bại: Connection refused (host:port)"*
- Nút "Lưu Hub" — chỉ enable sau khi test kết nối thành công

**Tắt Hub — Dialog xác nhận (nguy hiểm):**
- Cảnh báo: *"Hub Tâm Đạo sẽ không ai truy cập được. Dữ liệu vẫn được giữ nguyên."*
- Yêu cầu **gõ lại tên Hub** để xác nhận (anti-misclick)
- Nút "Tắt Hub" chỉ enable khi nhập đúng tên

---

### TRANG 6 — TÌM KIẾM CROSS-HUB (UC-03)

**Mô tả:** Admin tìm kiếm nội dung xuyên tất cả Hub — dùng chủ yếu để kiểm tra chồng lặp trước khi duyệt Sync.

**Trạng thái mặc định (chưa search):**
- Search bar lớn, nổi bật, ở giữa trang
- Placeholder: *"Tìm kiếm trên toàn bộ Wiki Medinet..."*
- Subtitle: *"Tìm kiếm ngữ nghĩa (RAG) — kết quả từ tất cả Hub"*
- Gợi ý nhanh: 3 chip text — "Quy trình vận hành" / "Bài thuốc đông y" / "Chính sách nhân sự"

**Trạng thái có kết quả:**
- Header: *"Tìm thấy 12 kết quả (0.6s)"* + dropdown filter Hub bên phải
- Danh sách kết quả (cards):
  Mỗi card:
  - Dòng 1: **[Tên Hub nguồn]** · Category
  - Dòng 2: **Tiêu đề trang** (link, click → mở tab mới sang subdomain Hub gốc)
  - Dòng 3-4: Đoạn trích 2-3 dòng, **từ khóa được in đậm/gạch chân**
  - Dòng 5: Tags · *"Cập nhật 2 ngày trước"* · Điểm liên quan: 87%
- Phân biệt Hub nguồn bằng **text label** (không dùng màu rực rỡ), ví dụ: "[Tâm Đạo]", "[HCNS]"

**Cảnh báo khi 1 Hub timeout:**
- Banner nhỏ trên kết quả: *"⚠ Hub Đỗ Minh Đường không phản hồi — kết quả có thể không đầy đủ"*

**Kết quả rỗng:**
- Text: *"Không tìm thấy nội dung phù hợp trên toàn hệ thống"*

---

### TRANG 7 — AUDIT LOG (UC-06)

**Mô tả:** Lịch sử toàn bộ thao tác hệ thống — Admin theo dõi AI Agent và Sync events.

**Filter bar (row ngang):**
- DateRange: "Từ ngày" → "Đến ngày" + presets: Hôm nay / 7 ngày / 30 ngày
- Dropdown "Người thực hiện": Tất cả / [danh sách user] / AI Agent
- Dropdown "Hành động": Tất cả / CREATE / UPDATE / DELETE / SYNC / APPROVE_SYNC / REJECT_SYNC / LOGIN / MCP_READ / MCP_WRITE
- Dropdown "Hub": Tất cả / Hub Tổng / Tâm Đạo / Đỗ Minh Đường / HCNS
- Nút "Áp dụng" + "Reset"
- Nút "Xuất CSV" (phải)

**Bảng log (50 records/trang):**
| Thời gian | Người thực hiện | Hành động | Trang bị ảnh hưởng | Hub | IP |
|-----------|-----------------|-----------|-------------------|-----|----|
| 14/03/2025 09:15:22 | Nguyễn Văn A | UPDATE | "Phác đồ trị đau dạ dày" | Đỗ Minh Đường | 192.168.1.1 |
| 14/03/2025 09:08:11 | **[AI Agent] Claude Desktop** | MCP_WRITE | "Quy trình onboarding" | HCNS | api |
| 14/03/2025 08:55:04 | Trần Thị B | SYNC | — | Tâm Đạo | 192.168.1.5 |

- Thao tác AI Agent: hiện prefix **[AI Agent]** + tên API key, **in đậm hoặc style khác** để phân biệt
- Sự kiện SYNC/APPROVE_SYNC/REJECT_SYNC: label đặc biệt dễ nhận ra
- Badge hành động dạng text nhỏ: CREATE | UPDATE | DELETE | SYNC... — có thể dùng background xám nhạt

**Click row → Expand chi tiết:**
- Request ID, Duration
- Payload trước/sau (nếu UPDATE): hiển thị dạng diff đơn giản (thêm = gạch chân, xóa = gạch ngang)

**Xuất CSV:**
- < 10.000 records: download trực tiếp
- ≥ 10.000 records: Dialog *"File quá lớn. Hệ thống sẽ tạo file và gửi email link khi hoàn tất."*

---

### TRANG 8 — HÀNG ĐỢI SYNC — DANH SÁCH BATCH (UC-07, màn hình 1/2)

**Mô tả:** Danh sách các batch Sync đang chờ và đã xử lý.

**Bảng:**
| Hub nguồn | Số trang | Thời gian gửi | Admin gửi | Trạng thái | Thao tác |
|-----------|----------|--------------|-----------|------------|----------|
| Tâm Đạo Y Quán | 8 trang | 30 phút trước | Nguyễn Admin Tâm Đạo | Chờ duyệt | Duyệt ngay |
| HCNS | 5 trang | 2 giờ trước | Trần Admin HCNS | Chờ duyệt | Duyệt ngay |
| Đỗ Minh Đường | 12 trang | 3 ngày trước | Lê Admin DMD | Đã xử lý (9 duyệt, 3 từ chối) | Xem chi tiết |

- "Chờ duyệt": nổi bật hơn
- "Đã xử lý": mờ hơn, hiện kết quả tóm tắt

---

### TRANG 9 — SYNC BATCH REVIEW — CHI TIẾT DUYỆT (UC-07, màn hình 2/2)

**Mô tả:** Admin xem và quyết định từng trang trong batch. Đây là màn hình cốt lõi của flow Sync.

**Header:**
- Breadcrumb: Hàng đợi Sync > Batch #001 — Hub Tâm Đạo
- Thông tin batch: Hub nguồn + Số trang + Ngày gửi + Admin gửi
- Thanh tiến trình: *"3 / 8 trang đã xử lý"*

**Layout 2 cột (không thể collapse):**

*Cột trái (~30%) — Danh sách trang trong batch:*
- Mỗi item: Tiêu đề trang + trạng thái
  - ○ Chưa xử lý (mặc định)
  - ✓ Đã duyệt
  - ✗ Đã từ chối
- Item đang xem: background highlight nhạt
- Click item → load preview bên phải

*Cột phải (~70%) — Preview trang đang chọn:*
- Tiêu đề (H2), Category, Tags, Ngày tạo, Tác giả
- Nội dung đầy đủ (render rich text)
- Nếu phát hiện trang tương tự trong Hub Tổng (similarity > 0.85):
  Banner cảnh báo: *"Trang tương tự đã tồn tại trong Hub Tổng: "Tên trang" (87% trùng)" — [Xem trang đó]*

*Action bar (sticky bottom dưới cột phải):*
- Nút "Duyệt" (style primary)
- Nút "Từ chối" → hiện textarea inline *"Lý do từ chối"* (bắt buộc, min 10 ký tự) → nút "Xác nhận từ chối"
- Nút "Duyệt tất cả còn lại" (ghost)
- Nút "Hoàn tất" (primary, chỉ enable khi tất cả trang đã xử lý)

**Trạng thái sau hoàn tất:**
- Toast: *"Đã xử lý batch: 6 duyệt, 2 từ chối. Admin Hub Tâm Đạo đã được thông báo."*
- Redirect về danh sách batch

---

### TRANG 10 — MCP API KEY MANAGEMENT (UC-08)

**Mô tả:** Tạo và quản lý API key cho AI Agent (Claude, ChatGPT) truy cập Wiki qua MCP protocol.

**Bảng danh sách API Keys:**
| Tên key | Quyền | Hub được phép | Ngày tạo | Dùng cuối | Requests 7 ngày | Rate limit | Trạng thái | Thao tác |
|---------|-------|---------------|----------|-----------|-----------------|------------|------------|----------|
| Claude Desktop — Team AI | Read + Write | Tất cả Hub | 01/01/2025 | 5 phút trước | 1.247 | 100/phút | Đang hoạt động | Thu hồi |
| ChatGPT Plugin | Read | Tâm Đạo, DMD | 15/02/2025 | 2 ngày trước | 89 | 50/phút | Đang hoạt động | Thu hồi |
| Test Key cũ | Read | HCNS | 10/03/2025 | 30 ngày trước | 0 | 10/phút | Đã thu hồi | — |

**Nút "Tạo API Key Mới" → Modal:**
Fields:
- Tên key (ví dụ: "Claude Desktop — Team AI")
- Mô tả (optional)
- Phạm vi quyền (checkboxes): ☑ Read (luôn bật) / ☐ Write / ☐ Cross-hub Search
- Hub được phép (multi-select hoặc checkbox "Tất cả Hub")
- Rate limit (input số, default 100) — label: "requests/phút"
- Ngày hết hạn (optional) — ghi chú: "Để trống = không hết hạn"

**Modal "Key đã tạo" — CHỈ HIỆN 1 LẦN:**
- Thiết kế nổi bật, không cho đóng bằng click ngoài
- Cảnh báo rõ: *"Key chỉ hiển thị một lần. Hãy sao chép và lưu ngay bây giờ."*
- Ô hiển thị key: monospace, toàn bộ 64 ký tự, có nút "Sao chép"
- Nút "Sao chép" → text đổi thành "Đã sao chép!" trong 2 giây
- Chỉ có nút "Đã sao chép, đóng" để đóng modal

**Thu hồi Key — Dialog:**
- *"Thu hồi key 'Claude Desktop — Team AI'? Key sẽ ngừng hoạt động ngay lập tức."*
- Buttons: "Hủy" + "Thu hồi"

---

### TRANG 11 — NOTIFICATION DROPDOWN

**Mô tả:** Thông báo realtime cho Admin — Sync mới, User đăng nhập lần đầu, API key sắp hết hạn.

**Bell icon trên Header:**
- Badge số unread (0 = không hiện, 1-99 = hiện số, 100+ = "99+")
- Click → dropdown panel

**Dropdown panel (~380px rộng):**
- Header: "Thông báo" (bold) + "Đánh dấu tất cả đã đọc" (link, phải)
- Danh sách (scroll, max 10):
  Mỗi item:
  - Tiêu đề ngắn (bold nếu chưa đọc)
  - Mô tả 1-2 dòng
  - Thời gian relative
  - Chưa đọc: background highlight nhạt
  - Click → navigate đến trang liên quan + đánh dấu đã đọc

**Ví dụ nội dung thông báo:**
- *"Sync mới từ Hub Tâm Đạo: 8 trang chờ duyệt"* → /sync-review
- *"Nguyễn Văn A đã đăng nhập Hub HCNS lần đầu"* → /users
- *"API Key 'Claude Desktop' sẽ hết hạn trong 7 ngày"* → /settings/api-keys
- *"Hub Đỗ Minh Đường không phản hồi trong 30 phút"* → /hub-registry

---

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
REQUIREMENTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

- Output clean, production-ready HTML + CSS (or Figma frames)
- Use ONLY the colors, radii, shadows, and spacing from the Design System above
- Every interactive element must have a visible hover state defined
- Sidebar must use glassmorphism (backdrop-blur + rgba(255,255,255,0.60) bg)
- Forms must follow: label → input-with-icon → hint/error pattern
- Buttons: primary action always uses the brand gradient (indigo→purple)
- No generic blue #2196f3 or material-style shadows
- Pixel-perfect alignment on 4px grid
- All 11 screens below must include:
  1. Full UI — production detail, not sketch — with real Vietnamese data (no Lorem ipsum)
  2. All states per screen — empty state, loading skeleton, error, confirmation dialogs
  3. Interaction annotations — hover, click, submit behaviors
  4. Responsive notes — desktop (≥1280px) primary, tablet (768–1279px) secondary

**Nguyên tắc bổ sung (domain-specific):**
- Đây là **công cụ làm việc hàng ngày** của Admin, ưu tiên **rõ ràng thông tin** hơn thẩm mỹ marketing
- Trạng thái phân biệt bằng **text label + weight/opacity**, không dùng màu rực rỡ tùy tiện
- AI Agent entries luôn có prefix **[AI Agent]** + style khác biệt để Admin nhận ra ngay
- Trang Sync Review (màn hình 9) là màn hình quan trọng nhất — thiết kế tối ưu cho tốc độ duyệt nhanh

## ĐẦU RA MONG MUỐN

Thiết kế **đầy đủ 11 màn hình** liệt kê bên trên, theo đúng Design System đã định nghĩa.

---

## GHI CHÚ NGHIỆP VỤ QUAN TRỌNG

1. **Sync là 1 chiều**: Hub Dự Án → Hub Tổng. Admin Hub Tổng chỉ duyệt, không bao giờ push ngược lại.
2. **Không có cross-hub search trên Hub Dự Án** — tính năng này chỉ có ở Hub Tổng.
3. **Auth độc lập**: Admin đăng nhập wiki.medinet.vn không có nghĩa đã đăng nhập tamdao.medinet.vn.
4. **AI Agent** không đăng nhập bằng user session — chỉ dùng API key do Admin cấp ở trang MCP API Keys.
5. **API key chỉ hiển thị 1 lần** khi tạo — không có nút "xem lại", nếu mất phải tạo mới.

═══════════════════════════════════════════════════════════
