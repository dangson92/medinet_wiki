**MEDINET WIKI**

User Requirements Document

*URD v1.2  —  Mô tả hành vi người dùng theo từng tính năng*

*URD v1.2 — Cập nhật: (1) Hub Tổng chỉ có quyền Admin, không có Editor/Viewer; (2) Admin Hub Tổng có toàn quyền trên Hub Tổng, Admin Hub Dự Án có toàn quyền trên Hub Dự Án; (3) User Hub nào chỉ xem tri thức Hub đó — không có cross-hub; (4) Thêm tính năng Sync 1 chiều từ Hub Dự Án lên Hub Tổng; (5) Admin Hub Tổng duyệt từng trang trong batch sync trước khi vào DB; (6) Giảm bớt màu sắc, không dùng icon.*

## Phân quyền và Domain

Hệ thống có 2 loại domain độc lập: Hub Tổng (wiki.medinetgroup.vn) dành cho quản trị, và các Hub Dự Án (tamdao / dmd / hcns .medinetgroup.vn) dành cho nhân viên dự án. Auth độc lập — đăng nhập riêng trên từng subdomain.

*Hub Tổng không có quyền Viewer hay Editor — chỉ Admin. Việc đọc nội dung Hub Tổng (nếu có) là việc của Admin Hub Tổng. User dự án không truy cập wiki.**medinetgroup.vn**.*

## Chỉ mục Use Cases

# 1. Hub Tổng — wiki.medinetgroup.vn

Hub Tổng là điểm quản trị trung tâm. Chỉ Admin Hub Tổng mới đăng nhập vào wiki.medinetgroup.vn. Các chức năng chính: Dashboard tổng quan, cross-hub search, quản lý user Hub Dự Án, Hub Registry, Audit Log, duyệt Sync từ Hub Dự Án, cấu hình MCP.

## UC-01 — Đăng nhập Hub Tổng

## UC-02 — Xem Dashboard Hub Tổng

## UC-03 — Tìm Kiếm Cross-Hub

## UC-04 — Quan Ly User Hub Dự Án

## UC-05 — Quản Lý Hub Registry

## UC-06 — Xem Audit Log

## UC-07 — Duyệt Sync từ hub Dự Án (Batch Review)

*Sync là 1 chiều: Hub Dự Án → Hub Tổng. Khi Admin Hub Dự Án khởi tạo Sync (UC-19), trạng thái từ Hub Dự Án được gửi lên Hub Tổng để chờ duyệt. Admin Hub Tổng xem từng trang, có thể approve/reject chọn lọc trong cùng 1 batch. Chỉ những trang được approve mới vào DB Hub Tổng.*

## UC-08 — Quản lý MCP API Key

# 2. Hub Dự Án — tamdao / dmd / hcns .medinetgroup.vn

Moi Hub Dự Án la mot React SPA doc lap tren subdomain rieng. User dang nhap rieng, chi thay noi dung Hub minh. Co 2 quyen: Admin Hub Dự Án (toan quyen trong Hub do) va Viewer (chi doc). Khong co cross-hub search. Muc nay dac ta tinh nang chung — hanh vi dac thu tung Hub o muc 4.

## UC-09 — Dang Nhap Hub Dự Án

## UC-10 — Duyệt và điều hướng nội dung Hub Dự Án

## UC-11 — Tìm kiếm trong Hub Dự Án (RAG Search)

## UC-12 — Đọc Trang Wiki

## UC-13 — Tạo Trang Wiki Mới

## UC-14 — Chỉnh Sửa Trang Wiki Hiện Có

## UC-15 — Xóa Trang Wiki

## UC-16 — Quản Lý Categories & Tags

## UC-17 — Xem Lịch Sử Phiên Bản

## UC-18 — Khôi Phục Phiên Bản Cũ

## UC-19 — Khoi Tao Sync Len Hub Tổng

*Sync là quá trình 1 chiều: Admin Hub Dự Án gửi nội dung lên Hub Tổng cho Admin Hub Tổng duyệt. Không có sync tự động — mỗi lần sync là hành động chủ động của Admin Hub Dự Án.*

## UC-20 — Xem Trạng Thái Sync

# 3. AI Post — Đăng Bài Từ Claude Lên Hub

AI Post cho phép Admin Hub Dự Án đăng nội dung từ Claude trực tiếp lên Hub Wiki. Luồng: chọn response Claude → Review modal → POST lên Hub Tổng API → page tạo với status 'pending_review'. Admin Hub Dự Án tự duyệt bài AI trong Hub mình.

## UC-21 — Đăng Toàn Bộ Response Claude Lên Hub

## UC-22 — Bôi Chọn Đoạn Claude Để Đăng Wiki

## UC-23 — Duyệt Bài AI Trước Khi Publish

## UC-24 — Lưu Bài AI Dưới Dạng Draft

## UC-25 — Thêm Section Từ Claude Vào Trang Hiện Có

## UC-36 — Nhận Thông Báo Bài AI Chờ Duyệt

# 4. MCP — AI Agent Qua Hub Tổng

AI Agent (Claude Desktop, ChatGPT...) giao tiep voi Medinet Wiki duy nhat qua MCP endpoint wiki.medinetgroup.vn/mcp. Agent dung API key duoc cap boi Admin Hub Tổng (UC-08). Khong can dang nhap user session.

## UC-26 — AI Agent: Tìm Kiếm Tri Thức Qua MCP

## UC-27 — AI Agent: Tạo Trang Wiki Qua MCP

## UC-28 — AI Agent: Cập Nhật Trang Wiki Qua MCP

## UC-29 — AI Agent: Tìm Kiếm Cross-Hub Qua MCP

# 5. Hanh Vi Dac Thu Tung Hub Dự Án

Moi Hub Dự Án co domain noi dung rieng. Phan nay mo ta cac use case khai thac noi dung dac thu tung Hub — tu tra cuu bai thuoc den onboarding nhan vien moi.

## 5.1 Hub Tâm Đạo Y Quan (tamdao.medinetgroup.vn)

*Nội dung: Y học cổ truyền, danh mục dịch vụ y quán, SOP vận hành, kiến thức YHCT.*

### UC-30 — Tra Cứu Sản Phẩm / Dịch Vụ Tâm Đạo

## 5.2 Hub Đỗ Minh Đường (dmd.medinetgroup.vn)

*Nội dung: Danh mục thuốc đông y, bài thuốc đặc trị, phác đồ điều trị, quy trình bán hàng.*

### UC-31 — Tra Cứu Bài Thuốc / Phác Đồ Đỗ Minh Đường

## 5.3 Hub HCNS (hcns.medinetgroup.vn)

*Nội dung: Sơ đồ tổ chức, chính sách nhân sự, quy trình onboarding/offboarding, JD, KPI, lương thưởng.*

### UC-32 — Tra Cứu Chính Sách Nhân Sự / JD Vị Trí

### UC-33 — Onboarding Nhân Viên Mới

### UC-34 — Nhap Lieu Noi Dung Hub Dự Án

### UC-35 — Embed & Vector Hóa Tài Liệu

# Phụ Lục — Tổng Hợp & Trạng Thái

## A. Ma Trận Use Cases & Vai Trò

## B. Trạng Thái Trang Wiki

## C. Luồng

Luồng tổng quát 1 chiềuKhông cho sync ngược lại

*MEDINET WIKI URD v1.2  —  Tai lieu noi bo Medinet  |  Tháng 7 / 2025*

| Phiên bản | Cập nhật | Tổng use cases | Liên quan PRD |
| --- | --- | --- | --- |
| URD v1.2 | Tháng 7 / 2025 | 36 use cases | PRD v1.3 |

| Vai trò | Phạm vi | Mô tả | Quyền hạn | Domain |
| --- | --- | --- | --- | --- |
| Admin Hub Tổng | Hub Tổng | Quản trị toàn bộ Hub Tổng | Toan quyen Hub Tổng: quản lý user dự án, Hub Registry, Audit Log, duyệt Sync, MCP config | wiki.medinetgroup.vn |
| Admin Hub Dự Án | 1 Hub Dự Án | Quản trị Hub Dự Án (Tâm Đạo / DMD / HCNS) | Toàn quyền Hub Đó: tạo/sửa/xóa/duyệt page, quản lý category & tag, quản lý user Hub, khởi tạo Sync | tamdao / dmd / hcns .medinetgroup.vn |
| Viewer | 1 Hub Dự Án | Nhân viên đọc tài liệu | Chỉ đọc nội dung trong Hub dự án được cấp quyền — không thể xem Hub khác | tamdao / dmd / hcns .medinetgroup.vn |
| AI Agent | Toan Hub (qua Hub Tổng) | Claude, ChatGPT qua MCP | Search + tạo/cập nhật page theo API key & RBAC. Không qua user session | wiki.medinetgroup.vn/mcp |

| ID | Tính năng | Vai trò | Phân hệ |
| --- | --- | --- | --- |
| UC-01 | Dang nhap Hub Tổng | Admin Hub Tổng | Hub Tổng |
| UC-02 | Xem Dashboard Hub Tổng | Admin Hub Tổng | Hub Tổng |
| UC-03 | Tìm kiếm cross-hub toàn hệ thống | Admin Hub Tổng | Hub Tổng |
| UC-04 | Quản lý user Hub Dự Án | Admin Hub Tổng | Hub Tổng |
| UC-05 | Quản lý Hub Registry | Admin Hub Tổng | Hub Tổng |
| UC-06 | Xem Audit Log hệ thống | Admin Hub Tổng | Hub Tổng |
| UC-07 | Duyệt Sync từ Hub Dự Án (batch review) | Admin Hub Tổng | Hub Tổng / Sync |
| UC-08 | Quản lý MCP API key cho AI Agent | Admin Hub Tổng | Hub Tổng / MCP |
| UC-09 | Đăng nhập Hub Dự Án | Admin / Viewer Hub Dự Án | Hub Dự Án |
| UC-10 | Duyệt và điều hướng nội dung Hub Dự Án | Admin / Viewer | Hub Dự Án |
| UC-11 | Tìm kiếm nội dung trong Hub Dự Án (RAG Search) | Admin / Viewer / AI Agent | Hub Dự Án |
| UC-12 | Đọc trang Wiki | Admin / Viewer | Hub Dự Án |
| UC-13 | Tạo trang Wiki mới | Admin Hub Dự Án | Hub Dự Án |
| UC-14 | Chỉnh sửa trang Wiki hiện có | Admin Hub Dự Án | Hub Dự Án |
| UC-15 | Xóa trang Wiki | Admin Hub Dự Án | Hub Dự Án |
| UC-16 | Quản lý categories & tags | Admin Hub Dự Án | Hub Dự Án |
| UC-17 | Xem lịch sử phiên bản trang Wiki | Admin Hub Dự Án | Hub Dự Án |
| UC-18 | Khôi phục phiên bản cũ | Admin Hub Dự Án | Hub Dự Án |
| UC-19 | Khoi tao Sync len Hub Tổng | Admin Hub Dự Án | Hub Dự Án / Sync |
| UC-20 | Xem trạng thái Sync | Admin Hub Dự Án | Hub Dự Án / Sync |
| UC-21 | Đăng bài từ Claude lên Hub (AI Post) | Admin Hub Dự Án | AI Post |
| UC-22 | Bôi chọn đoạn Claude để đăng Wiki | Admin Hub Dự Án | AI Post |
| UC-23 | Duyệt bài AI trước khi publish | Admin Hub Dự Án | AI Post |
| UC-24 | Lưu bài AI dưới dạng Draft | Admin Hub Dự Án | AI Post |
| UC-25 | Thêm section từ Claude vào trang hiện có | Admin Hub Dự Án | AI Post |
| UC-26 | AI Agent: tìm kiếm tri thức qua MCP | AI Agent | MCP |
| UC-27 | AI Agent: tạo trang Wiki mới qua MCP | AI Agent | MCP |
| UC-28 | AI Agent: cập nhật trang Wiki qua MCP | AI Agent | MCP |
| UC-29 | AI Agent: tìm kiếm cross-hub qua MCP | AI Agent | MCP |
| UC-30 | Tra cứu sản phẩm / dịch vụ Tâm Đạo Y Quán | Viewer / Admin — Hub Tâm Đạo | Hub Tâm Đạo |
| UC-31 | Tra cứu bài thuốc / phác đồ Đỗ Minh Đường | Viewer / Admin — Hub DMD | Hub Đỗ Minh Đường |
| UC-32 | Tra cứu chính sách nhân sự / JD vị trí | Viewer / Admin — Hub HCNS | Hub HCNS |
| UC-33 | Onboarding nhân viên mới đọc tài liệu HCNS | Viewer mới — Hub HCNS | Hub HCNS |
| UC-34 | Nhập liệu nội dung Hub Dự Án | Admin Hub Dự Án | Hub Dự Án |
| UC-35 | Embed & vector hóa tài liệu vào ChromaDB | Admin / System | Hub Dự Án / RAG |
| UC-36 | Nhận thông báo bài AI chờ duyệt | Admin Hub Dự Án | AI Post |

| UC-01   Dang nhap Hub Tổng (wiki.medinetgroup.vn) | UC-01   Dang nhap Hub Tổng (wiki.medinetgroup.vn) |
| --- | --- |
| Vai trò | Admin Hub Tổng |
| User Story | Là Admin quản trị Medinet Wiki, tôi muốn đăng nhập vào wiki.medinetgroup.vn bằng tài khoản Admin để truy cập các công cụ quản trị toàn hệ thống. |
| Điều kiện | Tài khoản Admin Hub Tổng đã được tạo trong hệ thống Trường hợp duy nhất truy cập wiki.medinetgroup.vn — không phải user dự án thường |
| Luồng chính | 1.  Admin mở trình duyệt, vào wiki.medinetgroup.vn 2.  Hệ thống hiện form đăng nhập với nhãn 'Quản trị Medinet Wiki' 3.  Admin nhập email + mật khẩu Admin, click 'Đăng nhập' 4.  Hub Tổng API xac thuc, tao JWT token voi role=admin_hub_tong 5.  He thong redirect den Dashboard Hub Tổng 6.  Sidebar hiển thị đầy đủ menu quản trị: Dashboard, Cross-hub Search, Quản lý User, Hub Registry, Audit Log, Sync Queue, MCP Config |
| Luật/lỗi | - Sai mật khẩu (< 5 lần): báo lỗi 'Email hoặc mật khẩu không đúng' - Sai mật khẩu >= 5 lần: khóa tài khoản 15 phút - User binh thuong (khong phai Admin Hub Tổng) thu truy cap wiki.medinetgroup.vn: trang 403 'Trang nay chi danh cho quan tri vien he thong' |
| Kết quả | Admin đã đăng nhập, có JWT token hợp lệ với scope admin_hub_tong Dashboard Hub Tổng hien thi dung du lieu toan he thong |
| UX / UI | Trang đăng nhập wiki.medinetgroup.vn hiện rõ 'Quản trị Medinet Wiki' để phân biệt với các subdomain dự án Khong co tuy chon 'Dang ky' — Admin Hub Tổng duoc tao thu cong qua script khoi tao he thong |

| UC-02   Xem Dashboard Hub Tổng | UC-02   Xem Dashboard Hub Tổng |
| --- | --- |
| Vai trò | Admin Hub Tổng |
| User Story | Là Admin, tôi muốn xem tổng quan toàn bộ hệ thống — số trang, hoạt động gần đây từ tất cả Hub, trạng thái Sync — để nắm bắt tình hình tri thức nội bộ và phát hiện bất thường. |
| Điều kiện | Admin đã đăng nhập vào wiki.medinetgroup.vn (UC-01) |
| Luồng chính | 1.  Dashboard hiển thị thống kê tổng: số trang wiki toàn hệ thống, số Hub đang active, số user active, số bài AI đang chờ duyệt Sync 2.  Danh sách Hub theo dạng bảng: tên Hub, subdomain, số trang, lần cập nhật gần nhất, trạng thái Sync (có bản Sync chờ, có không) 3.  Phiếu 'Sync chờ duyệt': số lượng trang đang chờ Admin duyệt để vào DB Hub Tổng 4.  Hoat dong gan day: 10 trang duoc tao/sua gan nhat tren tat ca Hub Dự Án 5.  Click vào Hub trong bảng → mở tab mới đến subdomain Hub Dự Án tương ứng (Admin sẽ cần đăng nhập riêng) |
| Luật/lỗi | - Hub bị tắt: hiện 'Không hoạt động', số trang giữ nguyên nhưng không cập nhật - Không có Hub nào: hướng dẫn 'Hãy thêm Hub đầu tiên trong Hub Registry' |
| Kết quả | Admin có cái nhìn tổng thể hệ thống và biết nhiệm vụ cần xử lý (Sync, bảo trì) |
| UX / UI | Phiếu 'Sync chờ duyệt' có số đếm nổi bật nếu > 0 Bảng Hub sắp xếp theo lần cập nhật gần nhất — Hub động nhất lên đầu |

| UC-03   Tìm kiếm cross-hub toàn hệ thống | UC-03   Tìm kiếm cross-hub toàn hệ thống |
| --- | --- |
| Vai trò | Admin Hub Tổng |
| User Story | Là Admin, tôi muốn tìm kiếm thông tin trên toàn bộ Wiki mà không cần biết thông tin nằm ở Hub nào, để kiểm tra chồng lặp nội dung, kiểm tra trạng thái tri thức toàn công ty trước khi duyệt Sync. |
| Điều kiện | Admin đã đăng nhập vào wiki.medinetgroup.vn Có ít nhất 1 Hub đã được index vào ChromaDB |
| Luồng chính | 1.  Admin nhập từ khóa vào Search Bar trên wiki.medinetgroup.vn 2.  Hệ thống gọi API cross-hub search, fan-out đến ChromaDB của tất cả Hub 3.  Kết quả trả về: danh sách trang xếp hạng theo relevance, mỗi kết quả có nhãn Hub nguồn 4.  Admin có thể filter theo Hub cụ thể qua dropdown 5.  Click kết quả → mở tab mới đến trang Wiki gốc trong subdomain Hub đó 6.  Admin dùng tính năng này chủ yếu để kiểm tra chồng lặp trước khi duyệt Sync |
| Luật/lỗi | - Không có kết quả: hiện 'Không tìm thấy nội dung phù hợp trên toàn hệ thống' - Một Hub timeout: kết quả Hub đó bị bỏ qua, hiện cảnh báo nhỏ 'Một Hub không phản hồi' |
| Kết quả | Admin thấy kết quả từ nhiều Hub, biết nội dung này tồn tại ở đâu trong hệ thống |
| UX / UI | Tính năng nay KHONG co tren subdomain Hub Dự Án — chi danh cho Admin Hub Tổng Mỗi kết quả hiện rõ tên Hub nguồn và URL subdomain |

| UC-04   Quản lý user Hub Dự Án | UC-04   Quản lý user Hub Dự Án |
| --- | --- |
| Vai trò | Admin Hub Tổng |
| User Story | La Admin Hub Tổng, toi muon tao tai khoan va gan user vao Hub Dự Án cu the voi quyen Admin hoac Viewer, de kiem soat ai duoc truy cap Hub nao. |
| Điều kiện | Admin đã đăng nhập vào wiki.medinetgroup.vn Co it nhat 1 Hub Dự Án da dang ky |
| Luồng chính | 1.   2.  Trang hien danh sach user cua Hub do: ten, email, quyen (Admin Hub Dự Án / Viewer), ngay tao, lan dang nhap cuoi 3.   4.  Hệ thống gửi email mời với link đặt mật khẩu subdomain Hub Dự Án (link valid 24h) 5.  Chỉnh quyền: chọn user → thay đổi quyền → lưu → có hiệu lực ngay 6.  Vô hiệu hóa user: bật 'Tắt tài khoản' → user không thể đăng nhập Hub Dự Án đó, dữ liệu giữ nguyên 7.  Chuyển user sang Hub khác: chuyển tab sang Hub Dự Án khác, lặp lại quy trình |
| Luật/lỗi | - Email đã tồn tại trong Hub này: báo lỗi 'Email đã được sử dụng trong Hub này' - Admin Hub Tổng tu xoa quyen cua chinh minh: he thong chan 'Khong the tu xoa quyen Admin' - Link đặt mật khẩu hết hạn: Admin gửi lại email mời |
| Kết quả | User moi nhan duoc email va co the dang nhap vao subdomain Hub Dự Án duoc phan Quyền truy cập được áp dụng ngay lập tức Mọi thay đổi quyền được ghi vào Audit Log |
| UX / UI | Moi Hub Dự Án quan ly user doc lap — user o tamdao.medinetgroup.vn khong tu dong co quyen o dmd.medinetgroup.vn Email mời ghi rõ tên Hub và subdomain đăng nhập (ví dụ: 'Bạn được mời vào Hub HCNS tại hcns.medinetgroup.vn') |

| UC-05   Quản lý Hub Registry | UC-05   Quản lý Hub Registry |
| --- | --- |
| Vai trò | Admin Hub Tổng |
| User Story | La Admin Hub Tổng, toi muon them Hub Dự Án moi vao he thong hoac tat Hub cu, de mo rong hay thu gon Wiki theo nhu cau to chuc ma khong can thay doi code. |
| Điều kiện | Admin đã đăng nhập vào wiki.medinetgroup.vn Cơ sở hạ tầng (DB, ChromaDB collection) cho Hub mới đã được DevOps chuẩn bị |
| Luồng chính | 1.  Admin vào 'Hub Registry' trên sidebar 2.  Trang hiện danh sách Hub: tên, subdomain, trạng thái, số trang, ngày tạo 3.  Thêm Hub mới: click 'Thêm Hub' → điền: Tên Hub, Mã Hub, Subdomain, DB connection string, ChromaDB collection name 4.   5.   6.  Tắt Hub: click 'Tắt Hub' → nhập lại tên Hub để xác nhận → Hub bị ẩn khỏi UI, không ai truy cập được |
| Luật/lỗi | - Test kết nối DB thất bại: hiện lỗi chi tiết, không lưu Hub mới - Subdomain đã tồn tại: báo lỗi 'Subdomain này đã được sử dụng' - Hub đang có user đang đăng nhập: cảnh báo trước khi tắt, không tự động logout ngay |
| Kết quả | Hub mới có thể được phân quyền user Hub bị tắt không còn xuất hiện trong search và dashboard |
| UX / UI | Nút test kết nối ngay trong form để kiểm tra trước khi lưu Tắt Hub yêu cầu nhập tên Hub để xác nhận tránh nhầm |

| UC-06   Xem Audit Log hoạt động hệ thống | UC-06   Xem Audit Log hoạt động hệ thống |
| --- | --- |
| Vai trò | Admin Hub Tổng |
| User Story | Là Admin, tôi muốn xem lịch sử toàn bộ thao tác đọc/ghi trên hệ thống — đặc biệt các thao tác của AI Agent và các sự kiện Sync — để đảm bảo an toàn dữ liệu và phát hiện bất thường. |
| Điều kiện | Admin đã đăng nhập vào wiki.medinetgroup.vn |
| Luồng chính | 1.  Admin vào 'Audit Log' trên sidebar 2.  Bảng log hiện: thời gian, user/AI Agent (API key), hành động, trang bị ảnh hưởng, Hub nguồn, IP 3.  Filter: theo khoảng thời gian, user, loại hành động (CREATE/UPDATE/DELETE/SYNC/APPROVE_SYNC/REJECT_SYNC), Hub 4.  Click vào log entry: xem chi tiết payload trước/sau thay đổi 5.  Xuất log CSV cho khoảng thời gian tùy chọn |
| Luật/lỗi | - Log quá lớn: phân trang 50 records/trang - Xuất CSV > 10,000 records: chạy background, gửi email link download khi xong |
| Kết quả | Admin đã xem được lịch sử thao tác theo filter mong muốn |
| UX / UI | Thao tác của AI Agent được đánh dấu rõ ràng để phân biệt với user thực Sự kiện Sync có nhãn 'SYNC' riêng biệt, dễ lọc để ra xem |

| UC-07   Duyet Sync tu Hub Dự Án — batch review | UC-07   Duyet Sync tu Hub Dự Án — batch review |
| --- | --- |
| Vai trò | Admin Hub Tổng |
| User Story | Là Admin Hub Tổng, tôi muốn xem xét từng trang Wiki được sync từ Hub Dự Án, quyết định duyệt hoặc từ chối từng trang, trước khi chúng được cập nhật vào DB Hub Tổng — để đảm bảo chất lượng nội dung ở Hub Tổng. |
| Điều kiện | Có ít nhất 1 batch Sync đang ở trạng thái 'chờ duyệt' (Admin Hub Dự Án đã khởi tạo UC-19) Admin đã đăng nhập vào wiki.medinetgroup.vn |
| Luồng chính | 1.  Dashboard Hub Tổng hiện phiếu 'Sync chờ duyệt: N trang'. Admin click vào 2.  Trang 'Hang doi Sync' hien danh sach cac batch dang cho: Hub nguon, so trang, thoi gian gui, Admin Hub Dự Án gui 3.   4.  Với mỗi trang: Admin chọn 'Duyệt' hoặc 'Từ chối'. Có thể xem full nội dung bằng nút 'Xem chi tiết' 5.  Admin có thể dùng 'Duyệt tất cả còn lại' để nhanh chóng approve những trang chưa xử lý 6.   7.  Các trang được Duyệt: cập nhật vào DB Hub Tổng và index lại ChromaDB Hub Tổng 8.  Các trang bị Từ chối: không vào DB Hub Tổng. Admin Hub Dự Án nhận thông báo 'X trang bị từ chối kèm lý do' |
| Luật/lỗi | - Trang trong batch có nội dung trùng lặp với trang Hub Tổng hiện có (similarity > 0.85): hệ thống cảnh báo 'Trang tương tự đã tồn tại' + link, Admin quyết định tiếp - Admin đóng cửa sổ giữa chừng: trạng thái các trang chưa xử lý vẫn là 'chờ duyệt', không mất |
| Kết quả | Trang được Duyệt: có mặt trong DB Hub Tổng, có thể tìm kiếm qua cross-hub search Trang bị Từ chối: không vào DB Hub Tổng, Admin Hub Dự Án được thông báo với lý do Lịch sử duyệt được ghi vào Audit Log: ai duyệt/từ chối, thời gian, lý do từ chối |
| UX / UI | Layout Batch Review: danh sách trang bên trái, preview nội dung bên phải — dễ xem và quyết định nhanh Mỗi trang có 3 trạng thái: chưa xử lý (mặc định), Đã duyệt, Đã từ chối — màu khác nhau để nhận biết Ô nhập 'Lý do từ chối' xuất hiện khi Admin chọn Từ chối — bắt buộc nhập trước khi confirm Tiến trình duyệt hiện thành progress: '5/12 trang đã xử lý' |

| UC-08   Quản lý MCP API key cho AI Agent | UC-08   Quản lý MCP API key cho AI Agent |
| --- | --- |
| Vai trò | Admin Hub Tổng |
| User Story | Là Admin Hub Tổng, tôi muốn tạo, cấp quyền và thu hồi API key cho AI Agent để kiểm soát chính xác AI nào được phép làm gì với Wiki. |
| Điều kiện | Admin đã đăng nhập vào wiki.medinetgroup.vn |
| Luồng chính | 1.  Admin vào 'Cài đặt hệ thống' → tab 'API Keys' 2.  Click 'Tạo API Key mới': đặt tên, mô tả, chọn phạm vi quyền (Read-only / Write / Cross-hub), chọn Hub được phép, đặt rate limit 3.  Hệ thống tạo API key 64 ký tự — chỉ hiện 1 lần khi tạo 4.  Admin copy key và cấp cho team AI / cấu hình Claude Desktop. Key không liên quan đến tài khoản user — AI Agent không cần đăng nhập vào bất kỳ subdomain nào 5.  Bảng API key hiện: tên, quyền, ngày tạo, lần dùng cuối, số request 7 ngày qua, trạng thái 6. |
| Luật/lỗi | - Admin quên copy key sau khi tạo: phải tạo key mới, không xem lại được - Key bị lộ: thu hồi ngay, tạo key mới cấp lại cho team |
| Kết quả | API key hoạt động, AI Agent có thể dùng ngay Key bị thu hồi không còn hoạt động dù request đang trong flight |
| UX / UI | Key chỉ hiện đúng 1 lần: modal có nút 'Sao chép' to và cảnh báo rõ ràng Có thể đặt expiry date cho API key (optional) |

| UC-09   Đăng nhập Hub Dự Án (doc lap tung subdomain) | UC-09   Đăng nhập Hub Dự Án (doc lap tung subdomain) |
| --- | --- |
| Vai trò | Admin Hub Dự Án / Viewer |
| User Story | Là nhân viên Medinet thuộc dự án Tâm Đạo (hoặc DMD / HCNS), tôi muốn đăng nhập vào subdomain Hub mình bằng tài khoản được cấp, để truy cập nội dung và công cụ quản trị Hub đó. |
| Điều kiện | Tai khoan da duoc Admin Hub Tổng tao va phan Hub (UC-04) Người dùng biết subdomain Hub mình (ví dụ: tamdao.medinetgroup.vn) |
| Luồng chính | 1.  Người dùng mở trình duyệt, vào subdomain Hub mình (ví dụ: tamdao.medinetgroup.vn) 2.  Trang đăng nhập hiện rõ tên Hub: 'Đăng nhập — Tâm Đạo Y Quán' 3.  Người dùng nhập email + mật khẩu, click 'Đăng nhập' 4.  Hub Tổng API xac thuc, tao JWT token voi payload: hub_id, user_id, role (admin_hub_du_an hoac viewer) 5.  Cookie được set cho subdomain hiện tại (không dùng chung với subdomain khác) 6.  He thong redirect den Dashboard Hub Dự Án: sidebar hien noi dung Hub, khong hien Hub khac |
| Luật/lỗi | - User thử vào subdomain Hub không được phân quyền: đăng nhập thành công nhưng thấy trang 403 'Tài khoản này không có quyền vào Hub này' - User thử vào wiki.medinetgroup.vn: trang 403 'Trang này chỉ dành cho quản trị viên hệ thống' - Session hết hạn: redirect về trang đăng nhập của subdomain hiện tại |
| Kết quả | Người dùng đăng nhập thành công, JWT token scope theo Hub Sidebar chỉ hiện nội dung Hub mình — không thấy Hub khác, không có cross-hub search |
| UX / UI | Trang đăng nhập hiện rõ tên Hub và màu chủ đạo của Hub đó để phân biệt (Tâm Đạo = xanh lá, DMD = xanh dương, HCNS = xanh tối) Khong co link 'Dang ky' — tai khoan do Admin Hub Tổng cap |

| UC-10   Duyệt và điều hướng nội dung Hub Dự Án | UC-10   Duyệt và điều hướng nội dung Hub Dự Án |
| --- | --- |
| Vai trò | Admin Hub Dự Án / Viewer |
| User Story | Là nhân viên, tôi muốn duyệt qua cây category của Hub, xem danh sách trang, di chuyển giữa các trang để tìm thông tin cần thiết mà không cần nhớ tên chính xác. |
| Điều kiện | Nguoi dung da dang nhap vao Hub Dự Án (UC-09) Hub có ít nhất 1 category và 1 trang |
| Luồng chính | 1.  Sau đăng nhập, trang chủ Hub hiện: tóm tắt Hub, các category chính, trang được xem nhiều nhất 2.  Sidebar trái: cây category có thể expand/collapse 3.  Click category → vùng chính hiện danh sách trang trong category đó 4.  Click tên trang → navigate đến trang Wiki (UC-12) 5.  Breadcrumb tren dau trang: Hub Dự Án > Category > Ten Trang |
| Luật/lỗi | - Hub chua co trang nao: hien 'Hub nay chua co noi dung' — Admin Hub Dự Án thay nut 'Tao trang dau tien', Viewer khong thay |
| Kết quả | Người dùng đang xem đúng Hub, có thể navigate đến bất kỳ trang nào trong Hub |
| UX / UI | Sidebar nhớ trạng thái expand/collapse theo session URL dạng: tamdao.medinetgroup.vn/category/ten-trang |

| UC-11   Tim kiem noi dung trong Hub Dự Án bang RAG | UC-11   Tim kiem noi dung trong Hub Dự Án bang RAG |
| --- | --- |
| Vai trò | Admin Hub Dự Án / Viewer / AI Agent |
| User Story | Là nhân viên, tôi muốn đặt câu hỏi tự nhiên hoặc nhập từ khóa để tìm tài liệu trong Hub mình đang xem, nhận kết quả liên quan nhất theo ngữ nghĩa — không chỉ tìm từ khóa cứng. |
| Điều kiện | Nguoi dung dang trong Hub Dự Án Hub đã có tài liệu được embed vào ChromaDB |
| Luồng chính | 1.  Nguoi dung nhap tu khoa hoac cau hoi vao Search Bar cua Hub Dự Án 2.  Hệ thống gọi API search với hub_id tương ứng, query ChromaDB collection của Hub này 3.  Kết quả trả về <= 800ms: danh sách trang xếp hạng theo score (ALG-001) 4.  Mỗi kết quả: tiêu đề, đoạn trích ngữ cảnh liên quan (highlight từ khóa), score indicator 5.  Click kết quả → mở trang Wiki, scroll đến đoạn liên quan nhất |
| Luật/lỗi | - Không có kết quả (score < 0.5): hiện 'Không tìm thấy nội dung phù hợp trong Hub này' - ChromaDB chưa có data: hiện 'Nội dung Hub chưa được index — liên hệ Admin' |
| Kết quả | Người dùng đến được trang Wiki phù hợp Search query ghi vào log để cải thiện RAG |
| UX / UI | Search bar cua Hub Dự Án chi tim trong Hub do — KHONG co option tim cross-hub cho Viewer Hỗ trợ tiếng Việt có dấu và không dấu Debounce 300ms |

| UC-12   Đọc trang Wiki | UC-12   Đọc trang Wiki |
| --- | --- |
| Vai trò | Admin Hub Dự Án / Viewer |
| User Story | Là nhân viên, tôi muốn đọc nội dung một trang Wiki rõ ràng, biết trang này đã được xác minh chưa, và xem gợi ý trang liên quan. |
| Điều kiện | Nguoi dung dang trong Hub Dự Án va click vao mot trang Wiki |
| Luồng chính | 1.  He thong load trang Wiki qua Hub Tổng API 2.  Trang hiện: Tiêu đề, breadcrumb, meta (tác giả, ngày tạo, lần sửa cuối, tags) 3.  Nếu trang được tạo bởi AI: hiện nhãn 'AI Generated' + tên model 4.  Nếu trang đã được Admin duyệt: nhãn chuyển thành 'Đã xác minh' 5.  Nội dung render dạng Rich Text (HTML từ TipTap) 6.  Sidebar phải (màn hình rộng): mục lục tự động từ headings H2/H3 7.  Cuối trang: danh sách 'Trang liên quan' gợi ý từ RAG similarity 8. |
| Luật/lỗi | - Trang 'pending_review': Viewer thấy 'Trang này đang chờ duyệt'; Admin thấy thêm nút 'Duyệt ngay' - Trang bị xóa: 404 + gợi ý tìm kiếm nội dung tương tự |
| Kết quả | Trang Wiki hiển thị đầy đủ Người dùng thấy trạng thái trang (draft/pending/published/verified) |
| UX / UI | Mục lục sticky scroll Code block có syntax highlighting và nút copy Hỗ trợ in ấn (CSS print-friendly) |

| UC-13   Tạo trang Wiki mới | UC-13   Tạo trang Wiki mới |
| --- | --- |
| Vai trò | Admin Hub Dự Án |
| User Story | La Admin Hub Dự Án, toi muon tao trang Wiki moi bang editor truc quan, chon category, them tags va publish ngay hoac luu draft, de bo sung tri thuc vao Hub. |
| Điều kiện | Nguoi dung co role Admin Hub Dự Án Dang o trong Hub Dự Án |
| Luồng chính | 1.  Admin click 'Tạo trang mới' trên sidebar 2.  Trang soạn thảo hiện: form (Tiêu đề, Category, Tags) + TipTap Editor bên dưới 3.  Nhập tiêu đề → hệ thống tự gợi ý slug (ASCII) từ tiêu đề tiếng Việt 4.  Chọn Category từ dropdown (có thể tạo Category mới ngay tại đây) 5.  Chọn Tags bằng tag input có autocomplete 6.  Soạn nội dung trong TipTap: heading, bold/italic, list, link, bảng, code block, ảnh 7.   8.  Hệ thống queue embed job: nội dung được vector hóa vào ChromaDB (async, < 10s) 9.  Toast 'Trang đã được tạo' + link trực tiếp đến trang mới |
| Luật/lỗi | - Tiêu đề trùng với trang đã có: cảnh báo 'Có trang tương tự' + link, không chặn tạo mới - Rời khỏi trang khi có thay đổi chưa lưu: confirm dialog - Mất kết nối mạng khi đang soạn: auto-save draft mỗi 30 giây |
| Kết quả | Trang mới được tạo với trạng thái published hoặc draft Nội dung được embed vào ChromaDB trong vòng 10 giây (async) |
| UX / UI | Auto-save draft mỗi 30 giây (lưu server-side) Word count và reading time hiện cuối editor Viewer không thấy nút 'Tạo trang mới' |

| UC-14   Chỉnh sửa trang Wiki hiện có | UC-14   Chỉnh sửa trang Wiki hiện có |
| --- | --- |
| Vai trò | Admin Hub Dự Án |
| User Story | La Admin Hub Dự Án, toi muon chinh sua noi dung mot trang Wiki da co — cap nhat thong tin, sua loi, them noi dung moi — va luu lai voi version moi. |
| Điều kiện | Admin đang xem một trang Wiki (UC-12) Co quyen Admin Hub Dự Án |
| Luồng chính | 1.  Admin click 'Chỉnh sửa' trên trang Wiki đang xem 2.  Trang chuyển sang chế độ edit: TipTap editor load nội dung hiện tại 3.  Admin chỉnh sửa nội dung, cập nhật tiêu đề / category / tags nếu cần 4.   5.  Hệ thống lưu version mới vào version history 6.  Queue re-embed job: nội dung mới được vector hóa lại vào ChromaDB (async) 7.  Toast 'Đã lưu thay đổi' + trang quay về chế độ đọc |
| Luật/lỗi | - Hai Admin cùng sửa một trang: người sau nhận cảnh báo conflict, phải merge thủ công - Admin hủy chỉnh sửa: confirm dialog nếu có thay đổi |
| Kết quả | Trang cập nhật với nội dung mới, version mới trong history ChromaDB re-embed, Audit Log ghi nhận |
| UX / UI | Nut 'Chinh sua' chi hien voi Admin Hub Dự Án — Viewer khong thay Có nút 'Xem trước' (preview) trước khi lưu |

| UC-15   Xóa trang Wiki | UC-15   Xóa trang Wiki |
| --- | --- |
| Vai trò | Admin Hub Dự Án |
| User Story | La Admin Hub Dự Án, toi muon xoa mot trang Wiki loi thoi hoac khong can thiet, voi xac nhan ro rang truoc khi xoa, de tranh xoa nham. |
| Điều kiện | Admin đang xem trang Wiki cần xóa |
| Luồng chính | 1.  Admin click 'Xóa trang' trong menu action của trang 2.  Modal xác nhận: tên trang, cảnh báo 'Hành động này không thể hoàn tác ngay' 3.  Admin gõ lại tên trang để xác nhận → click 'Xác nhận xóa' 4.  Hub Tổng API soft-delete (danh dau deleted, khong xoa vat ly ngay) 5.  ChromaDB: xóa vector embedding của trang khỏi collection 6.  Sidebar cập nhật, trang biến mất khỏi danh sách 7.  Toast 'Trang đã xóa' + option 'Hoàn tác' (có thể restore trong 30 ngày qua Audit Log) |
| Luật/lỗi | - Viewer click URL trang đã xóa: 404 'Trang này đã bị xóa hoặc không còn tồn tại' |
| Kết quả | Trang không hiển thị, vector embedding đã xóa Audit Log ghi nhận thao tác xóa |
| UX / UI | Yêu cầu gõ lại tên trang là cơ chế chống xóa nhầm Nut Xoa chi hien voi Admin Hub Dự Án |

| UC-16   Quản lý categories & tags | UC-16   Quản lý categories & tags |
| --- | --- |
| Vai trò | Admin Hub Dự Án |
| User Story | La Admin Hub Dự Án, toi muon tao va quan ly categories va tags de to chuc noi dung co cau truc, de tim kiem va duyet theo chu de. |
| Điều kiện | Admin dang trong Hub Dự Án |
| Luồng chính | 1.  Admin vào 'Cài đặt Hub' → tab 'Categories & Tags' 2.  Trang hiện cây category và danh sách tags phổ biến kèm số lượng trang dùng 3.  Tạo category mới: nhập tên, chọn parent (nếu muốn sub-category), lưu 4.  Kéo-thả để sắp xếp lại thứ tự category trong sidebar 5.  Merge tags trùng: chọn các tag muốn merge → nhập tag đích → confirm → tất cả trang dùng tag cũ sẽ cập nhật |
| Luật/lỗi | - Xóa category còn chứa trang: hỏi 'Di chuyển trang vào category nào?' trước khi xóa - Tên category trùng: cảnh báo, cho phép tiếp tục hoặc hủy |
| Kết quả | Cây category cập nhật hiện trên sidebar Tags đồng bộ với tất cả trang liên quan |
| UX / UI | Tags hiện số trang sử dụng giúp Admin quản lý Drag & drop category cần confirm nếu ảnh hưởng > 10 trang |

| UC-17   Xem lịch sử phiên bản trang Wiki | UC-17   Xem lịch sử phiên bản trang Wiki |
| --- | --- |
| Vai trò | Admin Hub Dự Án |
| User Story | La Admin Hub Dự Án, toi muon xem lich su cac phien ban cua mot trang — ai sua, khi nao, sua gi — de theo doi su thay doi noi dung. |
| Điều kiện | Đang xem một trang Wiki có ít nhất 2 phiên bản |
| Luồng chính | 1.  Admin click 'Lịch sử' trên trang Wiki 2.  Timeline hiện các version (mới nhất trên cùng): timestamp, người sửa, ghi chú thay đổi 3.  Click version → xem nội dung tại thời điểm đó (read-only) 4.  So sánh 2 version: tích chọn 2 → 'So sánh' → diff view (thêm xanh, xóa đỏ) |
| Luật/lỗi | - Trang chỉ có 1 version: hiện 'Chưa có lịch sử thay đổi' |
| Kết quả | Admin thấy được lịch sử và diff giữa các phiên bản |
| UX / UI | Diff view dạng side-by-side hoặc inline, toggle được Mỗi save tự động tạo version mới |

| UC-18   Khôi phục phiên bản cũ | UC-18   Khôi phục phiên bản cũ |
| --- | --- |
| Vai trò | Admin Hub Dự Án |
| User Story | La Admin Hub Dự Án, toi muon khoi phuc trang Wiki ve phien ban cu khi noi dung bi sua sai hoac xoa nham. |
| Điều kiện | Admin đang xem lịch sử phiên bản (UC-17) |
| Luồng chính | 1.   2.  Hệ thống tạo version mới từ nội dung version cũ (không overwrite history) 3.  Trang cập nhật với nội dung version cũ, re-embed vào ChromaDB 4.  Audit Log ghi: Admin [tên] khôi phục trang về version [ID] |
| Luật/lỗi | - Hủy khôi phục: không có thay đổi nào |
| Kết quả | Trang hiện nội dung version được khôi phục History giữ nguyên |
| UX / UI | Nút 'Khôi phục' màu cam, cần confirm tránh nhầm |

| UC-19   Khoi tao Sync noi dung len Hub Tổng | UC-19   Khoi tao Sync noi dung len Hub Tổng |
| --- | --- |
| Vai trò | Admin Hub Dự Án |
| User Story | Là Admin Hub Dự Án, khi nội dung đã ổn định và đủ chất lượng, tôi muốn gửi một số trang (hoặc tất cả trang mới/cập nhật) lên Hub Tổng để Admin Hub Tổng xem xét, nhằm xây dựng kho tri thức toàn công ty. |
| Điều kiện | Admin da dang nhap vao subdomain Hub Dự Án Có ít nhất 1 trang với status 'published' chưa được sync (hoặc đã sửa kể từ lần sync cuối) |
| Luồng chính | 1.  Admin vao 'Quan ly Sync' tren sidebar Hub Dự Án 2.  Trang hiện: danh sách trang đủ điều kiện sync (đã published, chưa sync hoặc đã thay đổi kể từ lần sync cuối). Mỗi trang hiện: tiêu đề, ngày sửa cuối, trạng thái sync trước (nếu có) 3.  Admin tích chọn trang muốn sync (hoặc 'Chọn tất cả') 4.   5.  Batch được gửi lên Hub Tổng với trạng thái 'chờ duyệt' 6.  Admin Hub Tổng nhận thông báo (UC-07) 7.  Trang da gui: hien trang thai 'Dang cho duyet Hub Tổng' — khong the sua trang nay cho den khi co ket qua |
| Luật/lỗi | - Không có trang đủ điều kiện: hiện 'Không có trang mới hoặc thay đổi cần sync' - Trang đang được Admin khác sửa: không thể thêm vào batch, hiện cảnh báo - Kết nối đến Hub Tổng thất bại: hiện lỗi, batch chưa được tạo, Admin thử lại sau |
| Kết quả | Batch Sync được tạo, đang chờ Admin Hub Tổng duyệt Các trang trong batch bị khóa sửa cho đến khi có kết quả duyệt Trạng thái sync hien tren trang quan ly Sync cua Hub Dự Án |
| UX / UI | Mỗi trang có nhãn trạng thái sync: 'Chưa sync' / 'Đang chờ duyệt' / 'Đã duyệt' / 'Bị từ chối' (kèm lý do) Lịch sử sync: xem các batch đã gửi trước đó, ai duyệt, kết quả Admin không thể gửi batch mới khi còn batch cũ đang chờ duyệt (tránh spam) |

| UC-20   Xem trạng thái Sync | UC-20   Xem trạng thái Sync |
| --- | --- |
| Vai trò | Admin Hub Dự Án |
| User Story | La Admin Hub Dự Án, toi muon biet trang Thai cua cac batch Sync da gui — dang cho, da duyet, bi tu choi — va biet ly do tu choi de chinh sua noi dung. |
| Điều kiện | Admin đã gửi ít nhất 1 batch Sync (UC-19) |
| Luồng chính | 1.  Admin vao 'Quan ly Sync' tren sidebar 2.  Tab 'Lịch sử Sync' hiện danh sách các batch: ngày gửi, số trang, trạng thái batch, Admin Hub Tổng đã xử lý (nếu có) 3.  Click vào batch → xem từng trang: Đã duyệt / Bị từ chối + lý do từ chối 4.  Với trang bị từ chối: Admin Hub Dự Án có thể sửa nội dung rồi thêm vào batch sync mới |
| Luật/lỗi | - Chưa gửi batch nào: hiện 'Chưa có lịch sử Sync' |
| Kết quả | Admin nắm rõ kết quả sync và biết cần chỉnh sửa gì |
| UX / UI | Lý do từ chối hiện rõ với màu cảnh báo để Admin chú ý và sửa Nút 'Thêm vào batch mới' ngay tại trang bị từ chối để tiện hành động nhanh |

| UC-21   Đăng bài từ Claude lên Hub — toàn bộ response | UC-21   Đăng bài từ Claude lên Hub — toàn bộ response |
| --- | --- |
| Vai trò | Admin Hub Dự Án |
| User Story | La Admin Hub Dự Án dang chat voi Claude, toi muon dang toan bo response cua Claude len Hub Wiki chi voi vai click, de luu tri thuc nhanh chong. |
| Điều kiện | Admin da dang nhap vao Hub Dự Án Đang chat với Claude trong interface tích hợp Co quyen Admin Hub Dự Án |
| Luồng chính | 1.  Claude trả lời xong 1 response 2.  Nút 'Đăng lên Wiki' xuất hiện phía dưới response 3.  Admin click 'Đăng lên Wiki' → Modal Review mở ra 4.  Modal hiện: preview nội dung (Markdown render HTML), form nhập Title, dropdown Category, input Tags 5.   6.  Admin review, chỉnh sửa nội dung trực tiếp trong modal nếu cần 7.   8.  Toast 'Bài đã được đăng, đang chờ duyệt' + link trang mới |
| Luật/lỗi | - Có trang trùng lặp (> 0.85): chọn 'Đăng bài mới' hoặc 'Thêm section vào trang cũ' (UC-25) - Rate limit 20 bài/ngày: thông báo 'Đã đạt giới hạn đăng bài hôm nay (20/20)' - Nội dung quá dài (> 50,000 ký tự): cảnh báo và gợi ý chia nhỏ |
| Kết quả | Page tạo với status 'pending_review', nhãn 'AI Generated' Metadata: ai_generated=true, claude_model, created_via=ai_post Re-embed job được queue vào Redis |
| UX / UI | Modal đủ rộng để xem preview đầy đủ Nút 'Đăng lên Wiki' không hiện với Viewer |

| UC-22   Bôi chọn đoạn text Claude để đăng lên Wiki | UC-22   Bôi chọn đoạn text Claude để đăng lên Wiki |
| --- | --- |
| Vai trò | Admin Hub Dự Án |
| User Story | Là Admin, đôi khi tôi chỉ muốn lưu một đoạn cụ thể trong response Claude, không phải toàn bộ. |
| Điều kiện | Admin đang xem response Claude Co quyen Admin Hub Dự Án |
| Luồng chính | 1.  Admin bôi chọn đoạn text trong response Claude 2.  Floating button 'Đăng đoạn này lên Wiki' xuất hiện gần vùng chọn 3.  Admin click floating button → Modal Review mở với chỉ đoạn đã chọn làm nội dung 4.  Luồng tiếp theo giống UC-21 từ bước 4 |
| Luật/lỗi | - Chọn quá ít text (< 50 ký tự): floating button không hiện |
| Kết quả | Chỉ đoạn text được chọn được POST lên Hub, không phải toàn bộ response |
| UX / UI | Floating button xuất hiện ngay khi bôi xong, không cần right-click |

| UC-23   Duyệt bài AI trước khi publish (trong Hub Dự Án) | UC-23   Duyệt bài AI trước khi publish (trong Hub Dự Án) |
| --- | --- |
| Vai trò | Admin Hub Dự Án |
| User Story | La Admin Hub Dự Án, toi muon xem xet cac trang Wiki do AI tao dang cho duyet trong Hub minh, chinh sua neu can va quyet dinh publish hay tu choi, dam bao chat luong noi dung Hub. |
| Điều kiện | Co it nhat 1 trang AI dang o trang thai 'pending_review' trong Hub Dự Án |
| Luồng chính | 1.  Admin nhận thông báo 'Có N bài AI chờ duyệt trong Hub [Tên]' (UC-36) 2.  Admin vao 'Hang cho duyet' trong sidebar Hub Dự Án 3.  Danh sách trang pending: tiêu đề, người đăng, thời gian, preview ngắn 4.  Admin click trang → xem toàn bộ nội dung với nhãn 'Đang chờ duyệt' 5.  Ba lựa chọn: (A) Duyệt & Publish — trang published, nhãn chuyển 'Đã xác minh'; (B) Chỉnh sửa rồi Duyệt — mở editor, sửa, publish; (C) Từ chối — nhập lý do, trang về draft |
| Luật/lỗi | - Trang bị người tạo xóa trước khi duyệt: hàng chờ tự cập nhật, loại trang này |
| Kết quả | Trang published hoặc từ chối Người tạo nhận notification kết quả Audit Log ghi nhận |
| UX / UI | Hàng chờ có badge đếm số trên sidebar: 'N bài chờ duyệt' Layout 2 cột: danh sách bên trái, preview bên phải |

| UC-24   Lưu bài AI dưới dạng Draft | UC-24   Lưu bài AI dưới dạng Draft |
| --- | --- |
| Vai trò | Admin Hub Dự Án |
| User Story | Là Admin, đôi khi nội dung Claude chưa hoàn chỉnh. Tôi muốn lưu nháp để hoàn thiện sau. |
| Điều kiện | Admin đang trong Modal Review của AI Post (UC-21 hoặc UC-22) |
| Luồng chính | 1.  Trong Modal Review, Admin click 'Lưu nháp' thay vì 'Đăng bài' 2.  Trang tao voi status 'draft' — chi Admin Hub Dự Án moi thay 3.  Toast 'Đã lưu nháp' + link đến trang draft 4.  Admin có thể vào trang draft sau, chỉnh sửa và publish |
| Luật/lỗi | - Admin đóng Modal mà không lưu: confirm 'Bỏ bài này?' để tránh mất nội dung |
| Kết quả | Trang draft được lưu, Viewer không thấy trong sidebar hoặc search |
| UX / UI | Draft được liệt kê trong tab 'Nháp' của Hub, dễ tìm lại |

| UC-25   Thêm section từ Claude vào trang Wiki hiện có | UC-25   Thêm section từ Claude vào trang Wiki hiện có |
| --- | --- |
| Vai trò | Admin Hub Dự Án |
| User Story | Là Admin, khi Claude tạo nội dung bổ sung cho chủ đề đã có trang Wiki, tôi muốn gắn thêm phần đó vào trang hiện có thay vì tạo trang trùng lặp. |
| Điều kiện | Admin đang trong Modal Review AI Post Hệ thống phát hiện trang tương tự (similarity > 0.85) hoặc Admin chủ động chọn |
| Luồng chính | 1.  Trong Modal Review, hệ thống gợi ý 'Trang tương tự: [Tên Trang]' + score 2.  Admin click 'Thêm vào trang này' → modal chuyển sang chế độ Append Section 3.  Nội dung Claude đặt vào ô 'Nội dung section mới', có thể chỉnh sửa 4.  Admin chọn vị trí thêm: cuối trang hoặc sau heading cụ thể 5. |
| Luật/lỗi | - Admin bỏ qua gợi ý và vẫn tạo trang mới: click 'Tạo trang mới thay thế' |
| Kết quả | Section mới được thêm vào trang hiện có, không tạo trang trùng lặp |
| UX / UI | Preview trang hiện có + section mới side-by-side giúp Admin hình dung kết quả |

| UC-36   Nhận thông báo bài AI chờ duyệt | UC-36   Nhận thông báo bài AI chờ duyệt |
| --- | --- |
| Vai trò | Admin Hub Dự Án |
| User Story | La Admin Hub Dự Án, toi muon duoc thong bao khi co bai AI moi can duyet trong Hub minh, de khong bo sot va duyet kip thoi. |
| Điều kiện | Admin co quyen Admin Hub Dự Án trong it nhat 1 Hub |
| Luồng chính | 1.  Khi trang AI được POST với status 'pending_review', hệ thống trigger notification 2.  In-app: badge đếm trên icon thông báo trên header tăng lên 3.   4.  Click thông báo → đến thẳng trang pending_review (UC-23) 5.  Email notification (nếu bật): gửi digest hàng ngày lúc 8h sáng |
| Luật/lỗi | - Admin tắt email notification: chỉ nhận in-app |
| Kết quả | Admin biết có bài cần duyệt và đến được trang review nhanh |
| UX / UI | Badge số trên icon không vượt quá '99+' để tránh layout break |

| UC-26   AI Agent tìm kiếm tri thức qua MCP (wiki_search) | UC-26   AI Agent tìm kiếm tri thức qua MCP (wiki_search) |
| --- | --- |
| Vai trò | AI Agent (Claude / ChatGPT) |
| User Story | Là AI Agent đang trả lời câu hỏi người dùng, tôi muốn tìm kiếm trong Medinet Wiki để lấy thông tin chính xác và cập nhật. |
| Điều kiện | AI Agent đã được cấu hình MCP Server URL và API key hợp lệ Hub Tổng API dang chay va ChromaDB da co du lieu |
| Luồng chính | 1.  Agent gọi MCP tool: wiki_search { query, hub_id, top_k } 2.   3.  Trả về top-K kết quả: page_id, title, snippet, score, hub_id, url 4.  Agent đọc kết quả và tích hợp vào response cho người dùng 5.  Nếu cần đọc toàn bộ trang: Agent gọi tiếp wiki_get_page với page_id |
| Luật/lỗi | - API key không hợp lệ: HTTP 401 - Hub không tồn tại hoặc Agent không có quyền: HTTP 403 - Không có kết quả phù hợp: trả về mảng rỗng, Agent thông báo 'Không tìm thấy thông tin' |
| Kết quả | Agent nhận được kết quả search để trả lời người dùng Search query ghi vào Audit Log |
| UX / UI | Rate limit: 100 request/phút/API key |

| UC-27   AI Agent tạo trang Wiki mới qua MCP (wiki_create_page) | UC-27   AI Agent tạo trang Wiki mới qua MCP (wiki_create_page) |
| --- | --- |
| Vai trò | AI Agent |
| User Story | Là AI Agent, sau khi tổng hợp tri thức, tôi muốn lưu nội dung đó vào Medinet Wiki như một trang mới để tái sử dụng. |
| Điều kiện | API key có quyền write Agent biết hub_id và category đích |
| Luồng chính | 1.  Agent gọi wiki_create_page: { title, content (Markdown), hub_id, category, tags, status: 'pending_review' } 2.  Hub Tổng API xac thuc API key + RBAC write permission 3.  Sanitize nội dung (bluemonday): lọc XSS 4.   5.  Tạo page với status 'pending_review', metadata: ai_generated=true, claude_model, created_via=mcp 6.  Queue embed job vào Redis 7.  Trả về: { page_id, url, status: 'pending_review' } 8.  Admin Hub Dự Án nhận thông báo 'Có bài AI mới cần duyệt' (UC-36) |
| Luật/lỗi | - Không có quyền write vào Hub đó: HTTP 403 - Rate limit 20 trang/ngày: HTTP 429 - Content có XSS bị lọc: lưu nhưng nội dung nguy hiểm bị remove, trả về warning |
| Kết quả | Trang tạo với status pending_review Admin Hub Dự Án duoc thong bao Audit Log ghi: API key nào, trang nào, thời gian |
| UX / UI | Agent nen luon tao voi status 'pending_review' — khong tu publish tru khi Admin Hub Tổng cau hinh cho phep |

| UC-28   AI Agent cập nhật trang Wiki qua MCP (wiki_update_page / wiki_append_section) | UC-28   AI Agent cập nhật trang Wiki qua MCP (wiki_update_page / wiki_append_section) |
| --- | --- |
| Vai trò | AI Agent |
| User Story | Là AI Agent, tôi muốn cập nhật hoặc bổ sung nội dung vào trang Wiki hiện có khi phát hiện thông tin cần thêm. |
| Điều kiện | Agent biết page_id API key có quyền write |
| Luồng chính | 1.  Agent chọn phương thức: wiki_append_section (thêm section mới) hoặc wiki_update_page (thay toàn bộ) 2.  wiki_append_section: Agent gửi { page_id, section_content (Markdown), position: 'end' } 3.   4.  Queue re-embed job 5.  Trả về: { page_id, version_id, url } |
| Luật/lỗi | - Trang đang được Admin sửa (lock): HTTP 409 Conflict — Agent retry sau 30s - page_id không tồn tại: HTTP 404 |
| Kết quả | Trang cập nhật, version mới trong history, re-embed job được queue |
| UX / UI | Agent nên ưu tiên wiki_append_section để tránh mất nội dung người dùng đã thêm |

| UC-29   AI Agent tìm kiếm cross-hub qua MCP (wiki_search_all) | UC-29   AI Agent tìm kiếm cross-hub qua MCP (wiki_search_all) |
| --- | --- |
| Vai trò | AI Agent |
| User Story | Là AI Agent, khi câu hỏi liên quan nhiều Hub, tôi muốn tìm kiếm trên toàn bộ Wiki mà không cần chỉ định Hub cụ thể. |
| Điều kiện | API key co quyen cross-hub search (Admin Hub Tổng cap loai quyen nay) |
| Luồng chính | 1.  Agent gọi wiki_search_all: { query, top_k } 2.  Hub Tổng fan-out query song song den tat ca ChromaDB collections dang active 3.  Merge và normalize kết quả, xếp hạng theo score tổng hợp 4.  Trả về: danh sách kết quả kèm source_hub, title, snippet, score |
| Luật/lỗi | - API key không có quyền cross-hub: HTTP 403 - Một Hub timeout: kết quả Hub đó bị bỏ qua, flag 'partial_results: true' trong response |
| Kết quả | Agent nhận kết quả từ nhiều Hub, biết kết quả đến từ Hub nào |
| UX / UI | Response bao gồm: số Hub được query, Hub nào timeout (nếu có) |

| UC-30   Tra cứu sản phẩm / dịch vụ Tâm Đạo Y Quán | UC-30   Tra cứu sản phẩm / dịch vụ Tâm Đạo Y Quán |
| --- | --- |
| Vai trò | Viewer / Admin Hub Tâm Đạo |
| User Story | Là tư vấn viên Tâm Đạo, tôi muốn tra cứu nhanh thông tin về dịch vụ (thành phần, chỉ định, chống chỉ định, giá) để tư vấn khách hàng chính xác. |
| Điều kiện | Nhân viên đã đăng nhập vào tamdao.medinetgroup.vn |
| Luồng chính | 1.  Nhân viên nhập tên dịch vụ vào search bar (ví dụ: 'cấy chỉ', 'xoa bóp bấm huyệt') 2.  RAG search trả về các trang liên quan theo ngữ nghĩa 3.  Click trang dịch vụ: xem mô tả, thành phần, thời gian, chống chỉ định, giá niêm yết 4.  Trang có section 'Hỏi đáp thường gặp' liên quan đến dịch vụ |
| Luật/lỗi | - Tên dịch vụ nhập không dấu: RAG vẫn tìm được nhờ embedding ngữ nghĩa - Dịch vụ chưa có trang Wiki: kết quả rỗng, Admin thấy gợi ý 'Tạo trang cho dịch vụ này' |
| Kết quả | Nhân viên có đủ thông tin để tư vấn khách hàng |
| UX / UI | Trang sản phẩm có bảng 'Phù hợp với ai / Không phù hợp với ai' Nút 'In phiếu tư vấn' để in thông tin cho khách |

| UC-31   Tra cứu bài thuốc / phác đồ điều trị Đỗ Minh Đường | UC-31   Tra cứu bài thuốc / phác đồ điều trị Đỗ Minh Đường |
| --- | --- |
| Vai trò | Viewer / Admin Hub Đỗ Minh Đường |
| User Story | Là dược sĩ Đỗ Minh Đường, tôi muốn tra cứu bài thuốc hoặc phác đồ điều trị theo triệu chứng hoặc tên bệnh để tư vấn khách hàng nhanh và chính xác. |
| Điều kiện | Dược sĩ đã đăng nhập vào dmd.medinetgroup.vn |
| Luồng chính | 1.  Dược sĩ nhập từ khóa vào search: 'đau dạ dày' hoặc 'phác đồ điều trị viêm khớp' 2.  RAG search trả về bài thuốc, phác đồ liên quan 3.  Click bài thuốc: xem thành phần, liều dùng, chống chỉ định, tương tác thuốc, giá tham khảo 4.  Mỗi bài thuốc có tag chỉ định (bệnh lý), thành phần chính, phác đồ cha 5.  Cuối trang: 'Bài thuốc liên quan' (gợi ý từ similarity search) |
| Luật/lỗi | - Tìm theo tên vị thuốc (ví dụ: 'hoàng kỳ') → trả về tất cả bài thuốc chứa vị thuốc đó - Bài thuốc có cảnh báo đặc biệt (phụ nữ có thai, trẻ em): banner cảnh báo hiện đầu trang |
| Kết quả | Dược sĩ có đủ thông tin chuẩn để tư vấn |
| UX / UI | Thành phần bài thuốc dạng bảng: vị thuốc | liều lượng | vai trò Cảnh báo chống chỉ định ở đầu trang, không chỉ ở cuối Nút 'Sao chép phác đồ' để dán vào phần mềm tư vấn |

| UC-32   Tra cứu chính sách nhân sự / mô tả công việc | UC-32   Tra cứu chính sách nhân sự / mô tả công việc |
| --- | --- |
| Vai trò | Viewer / Admin Hub HCNS |
| User Story | Là nhân viên Medinet, tôi muốn tra cứu chính sách nghỉ phép, quy trình đề nghị tăng lương hoặc mô tả công việc một vị trí nào đó mà không cần hỏi phòng HCNS. |
| Điều kiện | Nhân viên đã đăng nhập vào hcns.medinetgroup.vn |
| Luồng chính | 1.  Nhân viên nhập câu hỏi: 'Quy trình xin nghỉ phép?' hoặc 'JD vị trí Dược sĩ' 2.  RAG search trả về trang chính sách hoặc JD liên quan 3.  Đọc trang: quy trình, biểu mẫu kèm theo (link), thời hạn, người phê duyệt 4.  Cuối trang có thông tin liên hệ phòng HCNS nếu cần hỗ trợ thêm |
| Luật/lỗi | - Chính sách có phần mật (lương, KPI cá nhân): Viewer chỉ thấy trang công khai; trang mật cần quyền đặc biệt |
| Kết quả | Nhân viên tự trả lời được câu hỏi nhân sự không cần hỏi trực tiếp HCNS |
| UX / UI | Trang chinh sach co 'Ngay hieu luc' va 'Phiên bản' ro rang Badge 'Cập nhật [Thang/Nam]' dau trang chinh sach |

| UC-33   Onboarding nhân viên mới đọc tài liệu HCNS | UC-33   Onboarding nhân viên mới đọc tài liệu HCNS |
| --- | --- |
| Vai trò | Viewer moi (nhan vien moi gia nhap) |
| User Story | Là nhân viên mới vào Medinet, tôi muốn có lộ trình đọc tài liệu onboarding rõ ràng để hòa nhập nhanh mà không cần ai hướng dẫn từng bước. |
| Điều kiện | Tai khoan nhan vien moi da duoc Admin Hub Tổng tao va phan Hub HCNS (Viewer) Admin HCNS đã gửi link hcns.medinetgroup.vn + username + mật khẩu tạm |
| Luồng chính | 1.  Nhân viên mới mở hcns.medinetgroup.vn → đăng nhập (auth riêng của Hub HCNS) 2.  Sau đăng nhập, hiện trang 'Chào mừng' với checklist onboarding 3.  Checklist: Đọc Nội quy lao động, Xem Sơ đồ tổ chức, Đọc JD vị trí của bạn, Xem quy trình nghỉ phép, Xem chính sách lương thưởng (nếu có quyền) 4.  Nhân viên click từng mục → đến trang Wiki tương ứng 5.  Sau khi đọc: tick 'Đã đọc' → tiến trình checklist cập nhật 6.  Hoàn thành toàn bộ checklist: hiện thông báo 'Onboarding hoàn tất' |
| Luật/lỗi | - Nhân viên bỏ qua checklist: vẫn dùng Wiki bình thường, checklist còn hiện ở sidebar như reminder |
| Kết quả | Nhân viên nắm được thông tin cần thiết trong tuần đầu Admin HCNS thấy tiến trình onboarding của từng nhân viên mới |
| UX / UI | Checklist lưu trạng thái per-user, không mất khi đăng xuất Trang 'Chào mừng' chỉ hiện lần đầu đăng nhập, có thể tìm lại trong Hub |

| UC-34   Nhập liệu nội dung Hub Dự Án boi Content Team | UC-34   Nhập liệu nội dung Hub Dự Án boi Content Team |
| --- | --- |
| Vai trò | Admin Hub Dự Án |
| User Story | La thanh vien Content Team, toi muon nhap hang loat tai lieu vao Hub Dự Án moi mot cach co he thong de san sang cho viec index RAG. |
| Điều kiện | Hub moi da duoc Admin Hub Tổng dang ky (UC-05) Admin Hub Dự Án da co tai khoan va quyen |
| Luồng chính | 1.  Admin vào Hub mới → trang trống với hướng dẫn 'Bắt đầu bằng việc tạo Category đầu tiên' 2.  Admin tạo cấu trúc category theo outline (UC-16) 3.   4.  Có thể paste từ Google Docs / Word vào TipTap (giữ heading, bold, list) 5.  Sau khi nhập đủ nội dung, Admin trigger batch embed (UC-35) |
| Luật/lỗi | - Paste từ Word: giữ heading, bold, list; mất một số định dạng phức tạp (bảng phức tạp cần format lại thủ công) |
| Kết quả | Hub có đủ nội dung cơ bản theo outline Sẵn sàng cho bước embed và RAG testing |
| UX / UI | Progress indicator 'Đã nhập X / Y trang theo kế hoạch' |

| UC-35   Embed & vector hóa tài liệu vào ChromaDB | UC-35   Embed & vector hóa tài liệu vào ChromaDB |
| --- | --- |
| Vai trò | Admin Hub Dự Án / System (tu dong) |
| User Story | La Admin Hub Dự Án, sau khi noi dung Hub duoc nhap day du, toi muon trigger embed toan bo tai lieu vao ChromaDB de RAG search hoat dong chinh xac. |
| Điều kiện | Hub có ít nhất 1 trang đã published ChromaDB collection đã cấu hình |
| Luồng chính | 1.  LUỒNG TỰ ĐỘNG: Mỗi khi trang được tạo/sửa → hệ thống tự queue embed job vào Redis. Worker xử lý: chunk nội dung → Embedding Model (BGE-M3) → insert vector vào ChromaDB Hub. Hoàn thành trong < 10s sau khi publish 2.  LUỒNG THỦ CÔNG (Admin): Vào 'Cài đặt Hub' → 'Quản lý Index' → 'Re-embed toàn bộ' 3.  Batch re-embed chạy background: Admin thấy tiến trình (X/Y trang), ETA 4.  Hoàn thành: thông báo 'Đã embed Y/Y trang — RAG sẵn sàng' |
| Luật/lỗi | - Embedding Model không khả dụng: job retry tối đa 3 lần, sau đó alert Admin - Trang quá dài (> 10,000 từ): chia thành nhiều chunk nhỏ hơn |
| Kết quả | Tất cả trang published có vector trong ChromaDB RAG search trả về kết quả chính xác |
| UX / UI | Admin thấy trạng thái embed từng trang: Đã embed / Chờ embed / Lỗi embed Trang lỗi embed có nút 'Retry' để trigger lại thủ công |

| ID | Tính năng | Admin HT | Admin HDA | Viewer | Phase |
| --- | --- | --- | --- | --- | --- |
| UC-01 | Dang nhap Hub Tổng | Chỉ Admin HT | - | - | P1 |
| UC-02 | Dashboard Hub Tổng | x | - | - | P1 |
| UC-03 | Cross-hub search | x | - | - | P2 |
| UC-04 | Quản lý user Hub Dự Án | x | - | - | P1 |
| UC-05 | Hub Registry | x | - | - | P2 |
| UC-06 | Audit Log | x | - | - | P2 |
| UC-07 | Duyet Sync batch (Hub Tổng) | x | - | - | P2 |
| UC-08 | Quan ly MCP API Key | x | - | - | P1 |
| UC-09 | Đăng nhập Hub Dự Án | - | x | x | P1 |
| UC-10 | Điều hướng Hub Dự Án | - | x | x | P1 |
| UC-11 | RAG Search trong Hub | - | x | x | P1 |
| UC-12 | Đọc trang Wiki | - | x | x | P1 |
| UC-13 | Tao trang Wiki | - | x | - | P1 |
| UC-14 | Chỉnh sửa trang Wiki | - | x | - | P1 |
| UC-15 | Xóa trang Wiki | - | x | - | P1 |
| UC-16 | Quản lý categories & tags | - | x | - | P2 |
| UC-17-18 | Version history & Khôi phục | - | x | - | P2 |
| UC-19-20 | Sync len Hub Tổng | - | x | - | P2 |
| UC-21-25 | AI Post (đăng bài, duyệt, draft, append) | - | x | - | P1/2 |
| UC-26-29 | MCP AI Agent tools | - | - | - | P1/2 |
| UC-30-33 | Tra cứu đặc thù từng Hub (Tâm Đạo, DMD, HCNS) | - | x | x | P2 |
| UC-34-36 | Nhập liệu, Embed, Thông báo AI | - | x | - | P1/2 |

| Trạng thái | Ai tạo ra | Mô tả | Ai thấy |
| --- | --- | --- | --- |
| draft | Admin Hub Dự Án / AI Post | Nháp chưa gửi duyệt, chưa public | Chi Admin Hub Dự Án trong Hub do |
| pending_review | AI Post / MCP write | Da POST len Hub, cho Admin Hub Dự Án duyet | Admin Hub Dự Án thay va co the duyet; Viewer khong thay |
| published | Admin Hub Dự Án publish / duyet AI Post | Công khai trong Hub, Viewer đọc được | Tất cả user có quyền vào Hub dự án đó |
| verified | Admin Hub Dự Án duyet bai AI | Published + đã xác minh bởi Admin, nhãn 'Đã xác minh' | Tất cả user có quyền vào Hub dự án đó |
| sync_pending | Admin Hub Dự Án khoi tao Sync (UC-19) | Đã gửi lên Hub Tổng, chờ Admin Hub Tổng duyệt | Admin Hub Dự Án thay trang thai; trang bi khoa sua |
| sync_approved | Admin Hub Tổng duyệt Sync (UC-07) | Đã vào DB Hub Tổng, có thể tìm qua cross-hub search | Admin Hub Tổng qua cross-hub; AI Agent qua MCP |
| sync_rejected | Admin Hub Tổng từ chối Sync (UC-07) | Bị từ chối kèm lý do, trang giữ nguyên trong Hub Dự Án | Admin Hub Dự Án thấy kết quả và lý do từ chối |
| deleted | Admin Hub Dự Án xoa (UC-15) | Soft-delete: ẩn khỏi UI, giữ 30 ngày để restore | Chỉ Admin Hub Tổng thấy trong Audit Log |

| Bước | Người thực hiện | Hành động | Kết quả |
| --- | --- | --- | --- |
| 1 | Admin Hub Dự Án | Chọn trang, khởi tạo Sync (UC-19) | Batch Sync tạo với trạng thái 'chờ duyệt'. Trang bị khóa sửa. |
| 2 | He thong | Gửi batch lên Hub Tổng, thông báo Admin Hub Tổng | Admin Hub Tổng nhận thông báo trên wiki.medinetgroup.vn |
| 3 | Admin Hub Tổng | Vào Batch Review (UC-07), xem từng trang, Duyệt / Từ chối | Mỗi trang có kết quả riêng. Từ chối kèm lý do. |
| 4a | He thong (neu Duyet) | Cập nhật trang vao DB Hub Tổng + re-embed ChromaDB Hub Tổng | Trang xuất hiện trong cross-hub search. Trang mở khóa sửa trong Hub Dự Án. |
| 4b | He thong (neu Tu choi) | Thông báo Admin Hub Dự Án + lý do từ chối | Trang không vào DB Hub Tổng. Trang mở khóa sửa. Admin Hub Dự Án có thể chỉnh sửa và gửi lại. |
