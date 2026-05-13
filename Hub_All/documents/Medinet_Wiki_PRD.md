**MEDINET WIKI**

Product Requirements Document

*Hệ thống Wiki nội bộ đa Hub  ·  Go  ·  ChromaDB  ·  React  ·  PostgreSQL  ·  MCP  ·  RAG*

Thay đổi v1.3 so với v1.2: (1) Mỗi Hub Dự Án có subdomain riêng (tamdao.medinet.vn, dmd.medinet.vn, hcns.medinet.vn); (2) Hub Tổng tại wiki.medinet.vn; (3) Auth độc lập từng subdomain — user đăng nhập riêng trên subdomain Hub mình; (4) User dự án chỉ thấy nội dung Hub đó — không có cross-hub search.

# 1. Tổng Quan Sản Phẩm

## 1.1 Giới Thiệu

Medinet Wiki là hệ thống quản lý tri thức nội bộ (Internal Knowledge Base) được xây dựng riêng cho Medinet, với kiến trúc đa Hub — mỗi dự án / bộ phận sở hữu không gian wiki độc lập, database riêng, nhưng vẫn kết nối với nhau qua Hub Tổng trung tâm.

Hệ thống tích hợp AI thông qua RAG (Retrieval Augmented Generation) và chuẩn MCP (Model Context Protocol), cho phép các công cụ AI như Claude, ChatGPT truy xuất và cập nhật tri thức trực tiếp vào Wiki.

v1.3: Mỗi Hub triển khai trên subdomain riêng với auth độc lập. Hub Tổng (wiki.medinet.vn) là API Gateway + Admin UI — Admin/Editor quản trị đăng nhập tại đây. Hub Dự Án (tamdao.medinet.vn, dmd.medinet.vn, hcns.medinet.vn) là React SPA độc lập — user đăng nhập riêng trên subdomain Hub mình, chỉ thấy nội dung Hub đó, không có cross-hub search. Mỗi subdomain có JWT session độc lập.

## 1.2 Mục Tiêu Kinh Doanh

- Tập trung hóa tri thức nội bộ Medinet vào một nền tảng duy nhất, có tổ chức theo từng dự án

- Giảm ≥ 40% thời gian tìm kiếm thông tin của nhân viên thông qua semantic search bằng AI

- Cho phép AI assistant (Claude, ChatGPT) truy cập và cập nhật wiki qua MCP protocol — tất cả qua Hub Tổng

- Xây dựng nền tảng mở rộng: bắt đầu 3 Hub, có thể thêm Hub mới bất kỳ lúc nào

- Lưu trữ và truyền tải kiến thức y tế, dược liệu, quy trình vận hành từng dự án

## 1.3 Phạm Vi Dự Án

## 1.4 Vai Trò Người Dùng

## 1.5 Authentication & Phân Quyền (RBAC)

*⏳  Phần này sẽ được bổ sung chi tiết ở sprint riêng. Hiện để trống — chưa đặc tả.*

**Phạm vi dự kiến (sẽ làm rõ sau):**

- Cơ chế xác thực: JWT / SSO (chưa chọn)

- RBAC per-Hub: mỗi user có thể có role khác nhau ở từng Hub

- Auth độc lập từng subdomain: user đăng nhập riêng trên tamdao.medinet.vn, dmd.medinet.vn, hcns.medinet.vn và wiki.medinet.vn — không dùng chung session

- Mỗi subdomain có JWT secret riêng, session store riêng (Redis per Hub hoặc central Redis với namespace)

- API key riêng cho AI Agent (MCP) — xác thực tại Hub Tổng API Gateway (wiki.medinet.vn) — không liên quan đến auth user

- Session management, token refresh

# 2. Non-Functional Requirements

## 2.1 Performance

## 2.2 Availability & Reliability

## 2.3 Security

## 2.4 Scalability

- Phase 1 (MVP): ChromaDB standalone — phù hợp với < 100K vectors / Hub

- Phase 2+: Đánh giá migrate sang Qdrant hoặc pgvector nếu data vượt ngưỡng hoặc cần multi-tenant production

- Horizontal scaling: Go backend stateless → dễ thêm instance phía sau load balancer tại Hub Tổng

- Database: Connection pooling riêng cho từng Hub DB để tránh contention

## 2.5 Data Privacy & Compliance

- Dữ liệu YHCT, bài thuốc, thông tin bệnh nhân (nếu có): chỉ Editor+ mới truy cập

- Dữ liệu HCNS (lương, KPI): phân quyền PostgreSQL level, HR team only

- Audit log ghi lại mọi thao tác đọc/ghi trên dữ liệu nhạy cảm

- Không lưu raw prompt người dùng quá 90 ngày (configurable)

# 3. Success Metrics & KPI

## 3.1 KPI Adoption

## 3.2 KPI Chất Lượng

## 3.3 Ghi Chú Về Scoring AI (ALG-001)

*ℹ️  Thuật toán đánh giá điểm tri thức (ALG-001) đã được định nghĩa sơ bộ nhưng sẽ được đặc tả chi tiết và tinh chỉnh trong sprint RAG. Xem tài liệu kỹ thuật riêng.*

Tóm tắt: Mỗi kết quả RAG được chấm điểm kết hợp 4 yếu tố: Cosine Similarity (60%) + Popularity (20%) + Recency (20%) + Verified Bonus (+0.05). Trọng số và ngưỡng sẽ được tinh chỉnh sau khi có dữ liệu thực.

# 4. Kiến Trúc Kỹ Thuật

## 4.1 Tech Stack

v1.3: Mỗi Hub là một React SPA riêng (Vite monorepo hoặc separate apps). Nginx routing theo subdomain → đúng React app. Mỗi SPA có login form riêng, JWT session riêng — không chia sẻ auth giữa các subdomain. Tất cả SPA giao tiếp về Hub Tổng Go API backend nhưng với JWT được ký khác nhau theo Hub context.

## 4.2 Kiến Trúc Subdomain & API — Multi-Hub Deployment

📌  v1.3 — THAY ĐỔI KIẾN TRÚC: Mỗi Hub Dự Án có subdomain riêng với auth độc lập. User đăng nhập riêng trên subdomain Hub mình, chỉ thấy nội dung Hub đó, không có cross-hub search. Không SSO — session của tamdao.medinet.vn không dùng được ở dmd.medinet.vn hay wiki.medinet.vn.

Luồng request:

- wiki.medinet.vn → Nginx → Hub Tổng React SPA: Admin dashboard, cross-hub search, user management, MCP config

- tamdao.medinet.vn → Nginx → Hub Tâm Đạo React SPA: login riêng, chỉ thấy nội dung Tâm Đạo

- dmd.medinet.vn → Nginx → Hub Đỗ Minh Đường React SPA: login riêng, chỉ thấy nội dung Đỗ Minh Đường

- hcns.medinet.vn → Nginx → Hub HCNS React SPA: login riêng, chỉ thấy nội dung HCNS

- Tất cả React SPA → cùng 1 Hub Tổng Go API (port 8080): nhưng JWT payload chứa hub_id để API phân biệt context

- Auth hoàn toàn độc lập: đăng nhập tamdao.medinet.vn không có nghĩa là đã đăng nhập dmd.medinet.vn hay wiki.medinet.vn

- AI Agent / MCP → wiki.medinet.vn/mcp (Hub Tổng API, API key) — không qua user session, dùng API key riêng

- Hub con (Tâm Đạo, Đỗ Minh Đường, HCNS) KHÔNG có Go API server riêng — chỉ có React SPA frontend và internal embed worker

- Nginx wildcard cert *.medinet.vn: 1 cert SSL cover tất cả subdomain

## 4.3 Database Architecture — Per-Hub Isolation

Mỗi Hub sở hữu PostgreSQL database riêng để đảm bảo data isolation. Hub Tổng giữ Central DB cho user management, hub registry và API routing.

## 4.4 Aggregation Layer — Cross-Hub Search

Hub Tổng tìm kiếm xuyên suốt tất cả Hub thông qua fan-out query song song (goroutine per Hub) với timeout. Toàn bộ cross-hub search được expose qua Hub Tổng API.

# 5. Đặc Tả Tính Năng — Hub Tổng & Hub Dự Án

## 5.1 Hub Tổng — Medinet Central Wiki & API Gateway

Hub Tổng (wiki.medinet.vn) là trung tâm điều phối và API Gateway duy nhất: Admin dashboard, cross-hub search, quản lý user & Hub, MCP endpoint cho AI Agent. Chỉ Admin và Editor có nhu cầu quản trị mới thường xuyên vào wiki.medinet.vn. User thông thường truy cập thẳng subdomain Hub Dự Án của mình.

### Backend & Database

*📌  HT-12 (Version history): Đây là tính năng cốt lõi của wiki. Nên nâng lên 🔴 Cao khi số lượng Editor > 3 người hoặc có concurrent editing.*

### Frontend (React)

v1.3: Hub Tổng và mỗi Hub Dự Án là React SPA riêng, build & deploy độc lập. Có thể dùng Vite monorepo (shared packages: UI components, API client, auth hooks). SSO token được share qua cookie .medinet.vn — không cần redirect login khi chuyển subdomain.

→ Frontend đảm bảo mobile responsiveness và accessibility cơ bản (WCAG AA) — bổ sung vào Definition of Done

## 5.2 Hub Dự Án — Tâm Đạo Y Quán

⚠️  Rủi ro: TD-04 (YHCT) cần Domain Expert chuyên môn y học cổ truyền — xác nhận availability trước khi lên schedule.

## 5.3 Hub Dự Án — Đỗ Minh Đường

## 5.4 Hub Dự Án — HCNS (Nhân Sự)

# 6. MCP Integration — Kết Nối AI

Medinet Wiki triển khai chuẩn Model Context Protocol (MCP) phiên bản 2025-2026. Tất cả MCP endpoint được đặt tại Hub Tổng — AI tools (Claude Desktop, ChatGPT, Gemini...) giao tiếp duy nhất qua Hub Tổng API.

v1.2: MCP Server chỉ chạy tại Hub Tổng (port 8080/mcp). Hub con không có MCP endpoint riêng — dữ liệu từ Hub con được aggregate và expose qua Hub Tổng.

## 6.1 MCP Server

## 6.2 MCP Tools — Đặc Tả Đầy Đủ

## 6.3 Tích Hợp AI Clients

# 7. RAG — Retrieval Augmented Generation

Toàn bộ nội dung wiki được embedding và lưu vào ChromaDB per-Hub. RAG query được thực hiện qua Hub Tổng API — Hub con chỉ chịu trách nhiệm embed và index dữ liệu vào collection của mình.

## 7.1 RAG Pipeline

*📌  RG-08 (Auto re-embed): Bắt buộc qua Redis queue + async worker. Gọi trực tiếp từ API request sẽ gây blocking và timeout.*

## 7.2 Embedding Model — Lựa Chọn

## 7.3 Hybrid Retrieval (Phase 2)

- Vector search (ChromaDB / Qdrant) kết hợp với BM25 keyword search

- Re-ranking kết quả từ cả hai nguồn trước khi trả về

- Đặc biệt quan trọng với tên thuốc, bài thuốc, ký hiệu y tế (keyword exact match quan trọng)

# 8. AI Post — Đăng Bài Từ Claude Lên Hub

AI Post cho phép người dùng đang chat với Claude chọn một đoạn (hoặc toàn bộ) response và đăng trực tiếp lên Hub Wiki thông qua Hub Tổng API.

## 8.1 UX Flow

- Người dùng chat với Claude → Claude trả lời

- Nút 'Đăng lên Wiki' xuất hiện dưới mỗi response (chỉ hiển thị khi đã login và có quyền Editor+)

- Người dùng click → Modal Review mở ra: chọn Hub đích, nhập title, chọn category & tags

- Hệ thống kiểm tra duplicate (wiki_suggest_page qua Hub Tổng API): nếu similarity > 0.85 → cảnh báo

- Preview nội dung + cho phép sửa trực tiếp trong modal trước khi đăng

- Click Confirm → POST lên Hub Tổng API → Hub Tổng route đến Hub con → tạo page với status 'pending_review'

- Toast notification (React) + link trực tiếp đến page vừa tạo

## 8.2 Backend Requirements

## 8.3 Frontend Requirements (React)

# 9. Hạ Tầng & DevOps

*📌  Docker Compose (DO-04): 4 Nginx container phục vụ React SPA (wiki, tamdao, dmd, hcns subdomain). Nginx wildcard cert *.medinet.vn. Chỉ Go API container expose port 8080 ra internal network. Redis phục vụ embed queue + JWT session store per Hub (namespace riêng để tránh session cross-Hub).*

# 10. Kiểm Thử & Triển Khai

# 11. Roadmap Gợi Ý — 3 Phases

## Phase 1 — MVP (2-3 tháng)

*Mục tiêu: Hệ thống hoạt động với 1 Hub mẫu + RAG cơ bản + MCP read-only + AI Post nền tảng + React UI cơ bản + Hub Tổng API Gateway*

## Phase 2 — Full Feature (2-3 tháng tiếp theo)

*Mục tiêu: Triển khai đủ 3 Hub + MCP write + AI Post workflow đầy đủ + Aggregation Layer + React UI hoàn thiện*

- Triển khai Hub Tâm Đạo (TD series) và Hub Đỗ Minh Đường (DM series)

- Database isolation đầy đủ cho cả 3 Hub (DB-01, DB-02, DB-05, DB-07, DB-08)

- Full MCP write tools: wiki_create_page, wiki_update_page, wiki_post_page (MC-05, MC-06, AP-03 -> AP-06) — tất cả qua Hub Tổng

- AI Post workflow: review modal, approval flow, duplicate detection (AP-01, AP-02, AP-13, AP-15)

- Aggregation Layer: cross-hub search (AG-01 -> AG-06)

- React frontend hoàn thiện: search bar, Hub pages, sidebar navigation (HT-08, HT-09, AG-09, AG-10)

- CI/CD + Backup tự động (DO-06, DO-07)

## Phase 3 — Optimization & Scale

*Mục tiêu: Tối ưu hiệu suất, monitoring, version history, đánh giá migrate Vector DB*

- Version history + concurrent editing (HT-12, tích hợp Yjs nếu cần)

- Hybrid retrieval: vector + BM25 keyword search (cải thiện tiếng Việt)

- Đánh giá migrate ChromaDB sang Qdrant hoặc pgvector nếu data > 100K vectors / Hub

- Test thêm Qwen3-Embedding cho tài liệu y khoa tiếng Việt

- Monitoring đầy đủ: Prometheus + Grafana + Loki + alerting (DO-08)

- Security audit OWASP (QA-06) + encryption at rest

- Mobile responsiveness + accessibility audit (React components)

- Training toàn team + go-live (QA-07, QA-08)

# 12. Risk Register

# 13. Tổng Hợp Tasks Theo Module

*MEDINET WIKI PRD v1.3 — Tài liệu nội bộ, không phổ biến ra ngoài  |  Cập nhật Tháng 7/2025*

| Phiên bản | Cập nhật | Tổng Tasks | Modules |
| --- | --- | --- | --- |
| v1.3 — Draft | Tháng 7 / 2025 | 122 tasks | 17 modules |

| Hub | Tên Đầy Đủ | Lĩnh Vực Chính | Database |
| --- | --- | --- | --- |
| 🌐 Hub Tổng | Medinet Central Wiki | Quản trị hệ thống, API Gateway, cross-hub search, user mgmt | central_db | wiki.medinet.vn |
| 🌿 Tâm Đạo | Tâm Đạo Y Quán | Y học cổ truyền, sản phẩm dịch vụ, SOP | tamdao_db | tamdao.medinet.vn |
| 💜 Đỗ Minh Đường | Đỗ Minh Đường | Thuốc đông y, bài thuốc, phác đồ, bán hàng | dmd_db | dmd.medinet.vn |
| 🟠 HCNS | Nhân Sự & Hành Chính | Org chart, chính sách, JD, onboarding | hcns_db | hcns.medinet.vn |

| Vai Trò | Mô Tả | Quyền Hạn |
| --- | --- | --- |
| Admin | Quản trị toàn hệ thống, quản lý user và Hub | Toàn quyền trên tất cả Hub. Truy cập qua wiki.medinet.vn |
| Editor | Biên tập viên nội dung, duyệt bài AI | Tạo, sửa, xóa, duyệt page trong Hub được phân. Truy cập qua subdomain Hub đó |
| Viewer | Nhân viên đọc tài liệu | Chỉ đọc trong Hub được cấp quyền. Truy cập qua subdomain Hub đó |
| AI Agent | Claude, ChatGPT qua MCP | Search + tạo/cập nhật page qua API key & RBAC — MCP endpoint tại wiki.medinet.vn/mcp (không cần đăng nhập user) |

| Chỉ Số | Mục Tiêu | Ghi Chú |
| --- | --- | --- |
| Search latency (Hub riêng) | < 800ms (p95) | Bao gồm RAG retrieval + ranking |
| Search latency (cross-hub) | < 1.5s (p95) | Fan-out goroutine + merge + cache |
| API response Hub Tổng (CRUD thông thường) | < 300ms (p95) | Không bao gồm embedding — đo tại Hub Tổng API Gateway |
| Auto-embed sau khi tạo page | < 10s (async) | Qua Redis queue, không block API |
| Concurrent users hỗ trợ | Tối thiểu 100 | Load test với QA-05 |

| Chỉ Số | Mục Tiêu | Ghi Chú |
| --- | --- | --- |
| Uptime SLA | 99.5% / tháng | Cho phép ~3.6h downtime/tháng |
| Backup PostgreSQL | Mỗi 24h, giữ 30 ngày | Cronjob per Hub DB + Central DB |
| Backup ChromaDB | Mỗi 24h, giữ 14 ngày | Snapshot collection riêng từng Hub |
| Recovery Time Objective (RTO) | < 2 giờ | Restore từ backup gần nhất |
| Recovery Point Objective (RPO) | < 24 giờ | Mất tối đa 1 ngày data |

| Yêu Cầu | Mô Tả |
| --- | --- |
| API Gateway tập trung | Tất cả request từ client/AI đều đi qua Hub Tổng API — Hub con không expose port |
| Data isolation | Mỗi Hub DB hoàn toàn tách biệt, PostgreSQL user/password riêng |
| Encryption in transit | HTTPS/TLS cho tất cả traffic (Let's Encrypt) |
| Encryption at rest | PostgreSQL & ChromaDB data được mã hóa trên disk |
| MCP Security | API key auth + rate limiting + audit log cho mọi write operation — tại Hub Tổng |
| Content sanitization | Lọc XSS trước khi lưu HTML (bluemonday Go) |
| Security audit | OWASP Top 10: SQL injection, XSS, CSRF (QA-06) |

| Chỉ Số | Mục Tiêu 3T | Mục Tiêu 6T | Cách Đo |
| --- | --- | --- | --- |
| Monthly Active Users (MAU) | > 30 users | > 60 users | Log hệ thống |
| Tổng số Wiki page active | > 100 pages | > 300 pages | DB count |
| Tỷ lệ page AI được duyệt | > 60% | > 75% | Audit log AI Post |
| Nhân viên dùng search ≥ 1 lần/tuần | > 40% | > 65% | Search log |

| Chỉ Số | Mục Tiêu | Cách Đo |
| --- | --- | --- |
| Giảm thời gian tìm kiếm thông tin | >= 40% | Survey nhân viên trước/sau 3 tháng |
| RAG accuracy (top-3 relevant) | >= 75% | Test set 20 câu hỏi / Hub (QA) |
| Search response time p95 (Hub Tổng API) | < 800ms | APM monitoring |
| Uptime hệ thống | >= 99.5% | Monitoring Prometheus/Grafana |

| Layer | Technology | Mô Tả | Ghi Chú |
| --- | --- | --- | --- |
| Frontend | React 18 + Vite | Hub Tổng (wiki.medinet.vn) + Hub Dự Án mỗi Hub 1 SPA riêng (tamdao/dmd/hcns.medinet.vn) | React Router + Zustand/Jotai |
| Rich Text Editor | TipTap (ProseMirror) | Soạn thảo wiki, Markdown, collaboration-ready | Tích hợp tốt với React |
| API Gateway | Go (Gin / Fiber) | RESTful API + MCP Server — CHỈ tại Hub Tổng, port 8080 | Stateless, tập trung |
| Hub Con Service | Go (internal) | Internal service: nhận webhook từ Hub Tổng, cập nhật DB Hub riêng, trigger embed — không expose API public | Không có public port |
| Authentication | TBD (JWT / SSO) | Phân quyền RBAC per Hub — xử lý tại API Gateway | Sprint riêng |
| Primary DB | PostgreSQL 16 | Wiki pages, categories, users, versions — riêng từng Hub |  |
| Vector DB | ChromaDB (Phase 1) | Embeddings cho RAG, per-Hub collection | Migrate Phase 2+ |
| Embedding Model | BGE-M3 / OpenAI | Embedding tiếng Việt — BGE-M3 ưu tiên | Test Qwen3 2026 |
| RAG Engine | Go service | Query ChromaDB, scoring, top-K retrieval (ALG-001) |  |
| MCP Server | Go (SSE / HTTP) | Kết nối Claude AI, ChatGPT — endpoint tại Hub Tổng | MCP spec 2025 |
| Async Queue | Redis + Worker | Auto-embed job sau khi tạo/sửa page | Không block API |
| Cache | Redis | Aggregation Layer cache, giảm latency cross-hub |  |
| Infrastructure | Docker Compose | Tất cả services trong container | Dev & Production |
| Reverse Proxy | Nginx | SSL termination + subdomain routing + static files React per Hub. Wildcard cert *.medinet.vn | Let's Encrypt wildcard |
| CI/CD | GitHub Actions | Auto deploy khi push main branch |  |
| Monitoring | Prometheus + Grafana | Metrics, alerting, APM | Phase 2+ |

| Mã | Task | Database / Scope | Ưu Tiên |
| --- | --- | --- | --- |
| DB-01 | Schema PostgreSQL riêng cho Hub Tâm Đạo | tamdao_db | 🔴 Cao |
| DB-02 | Schema PostgreSQL riêng cho Hub Đỗ Minh Đường | dmd_db | 🔴 Cao |
| DB-03 | Schema PostgreSQL riêng cho Hub HCNS | hcns_db | 🔴 Cao |
| DB-04 | Central DB: users, roles, hub_registry, audit_log, API routing config | central_db | 🔴 Cao |
| DB-05 | Go: connection pool riêng từng Hub (multi-datasource) — Hub Tổng manage | Go config | 🔴 Cao |
| DB-06 | ChromaDB collection riêng: col:tamdao, col:dmd, col:hcns | ChromaDB | 🔴 Cao |
| DB-07 | Middleware routing tại Hub Tổng: tự chọn đúng DB theo Hub context | Backend | 🔴 Cao |
| DB-08 | Migration tool: quản lý schema version riêng từng Hub | DevOps | 🟡 TB |
| DB-09 | Backup/restore độc lập từng Hub DB (cronjob per DB) | DevOps | 🟡 TB |
| DB-10 | Phân quyền PostgreSQL: user/password riêng từng Hub | Security | 🔴 Cao |

| Mã | Task | Ưu Tiên |
| --- | --- | --- |
| AG-01 | Thiết kế kiến trúc Aggregation Layer (Go service / internal package) | 🔴 Cao |
| AG-02 | Fan-out query song song (goroutine per Hub) với timeout | 🔴 Cao |
| AG-03 | Merge & rank kết quả cross-hub (relevance score + dedup) | 🔴 Cao |
| AG-04 | Gắn nhãn Hub nguồn (source_hub) vào từng kết quả | 🔴 Cao |
| AG-05 | API: GET /api/hub-total/search?q= (cross-hub search) — tại Hub Tổng | 🔴 Cao |
| AG-06 | Aggregation RAG: fan-out đến tất cả ChromaDB collections song song | 🔴 Cao |
| AG-07 | Merge vector search results từ nhiều collections (normalize scores) | 🟡 TB |
| AG-08 | Cache layer (Redis): giảm latency cho Aggregation cross-hub | 🟡 TB |
| AG-09 | UI Hub Tổng: hiển thị kết quả cross-hub với badge Hub nguồn | 🟡 TB |
| AG-10 | UI: click kết quả -> navigate đúng Hub gốc + page | 🟡 TB |
| AG-11 | MCP Tool: wiki_search_all — search toàn Hub qua Aggregation Layer (Hub Tổng endpoint) | 🟡 TB |
| AG-12 | Test cross-hub query: đo latency fan-out, accuracy merge, edge cases | 🟡 TB |
| AG-13 | Phân quyền: chỉ Hub Tổng Admin mới query cross-hub | 🔴 Cao |

| Mã | Task | Module | Ưu Tiên |
| --- | --- | --- | --- |
| HT-01 | Thiết kế database schema PostgreSQL (wiki_pages, categories, tags, users, projects) | Architecture | 🔴 Cao |
| HT-02 | Thiết kế sitemap & subdomain routing map: wiki.medinet.vn, tamdao/dmd/hcns.medinet.vn + Nginx config | Architecture | 🔴 Cao |
| HT-03 | Implement database schema (sau thiết kế HT-01) | Backend-DB | 🔴 Cao |
| HT-04 | Setup môi trường Go backend (Go modules, folder structure, Gin/Fiber) — API Gateway Hub Tổng | Backend-API | 🔴 Cao |
| HT-05 | Xây dựng API CRUD cho Wiki Pages (Hub Tổng) — endpoint duy nhất cho tất cả Hub | Backend-API | 🔴 Cao |
| HT-06 | Xây dựng hệ thống phân quyền RBAC (chi tiết ở sprint Auth) | Backend-Auth | 🔴 Cao |
| HT-11 | Hệ thống tags & categories toàn Wiki | Backend-API | 🟡 TB |
| HT-12 | Version history cho Wiki pages | Backend-API | 🟡 TB |

| Mã | Task | Ưu Tiên |
| --- | --- | --- |
| HT-07 | Setup React monorepo: Hub Tổng app (wiki.medinet.vn) + shared component lib — Vite + React 18 + React Router v6 + Zustand/Jotai | 🔴 Cao |
| HT-08 | Dashboard tổng Hub (Overview page — React component) | 🟡 TB |
| HT-09 | Hub Tổng: sidebar navigation + link điều hướng sang subdomain Hub Dự Án (mở tab cùng, SSO cookie đã sẵn) | 🟡 TB |
| HT-10 | Rich Text Editor tích hợp TipTap vào React component | 🟡 TB |

| Mã | Task | Module | Scope | Ưu Tiên |
| --- | --- | --- | --- | --- |
| TD-01 | Xác định cấu trúc nội dung Wiki Tâm Đạo (outline) | Content | Internal | 🔴 Cao |
| TD-02 | Nhập liệu: Danh mục sản phẩm / dịch vụ y quán | Content | Internal | 🔴 Cao |
| TD-03 | Nhập liệu: Quy trình vận hành (SOP) y quán | Content | Internal | 🔴 Cao |
| TD-04 | Nhập liệu: Kiến thức y học cổ truyền (YHCT) | Content | Internal | 🔴 Cao |
| TD-05 | Xây dựng React SPA cho Hub Tâm Đạo (tamdao.medinet.vn): layout, sidebar, search bar riêng Hub | Frontend | tamdao.medinet.vn | 🟡 TB |
| TD-06 | Cấu hình ChromaDB collection cho Tâm Đạo | RAG | Internal | 🟡 TB |
| TD-07 | Embedding & index toàn bộ tài liệu Tâm Đạo vào ChromaDB | RAG | Internal | 🟡 TB |
| TD-08 | Test RAG query cho nội dung Tâm Đạo Y Quán | RAG | Internal | 🟡 TB |
| TD-09 | MCP connector: data Tâm Đạo expose qua Hub Tổng MCP endpoint | MCP | Qua Hub Tổng | 🟢 Thấp |

| Mã | Task | Module | Scope | Ưu Tiên |
| --- | --- | --- | --- | --- |
| DM-01 | Xác định cấu trúc nội dung Wiki Đỗ Minh Đường (outline) | Content | Internal | 🔴 Cao |
| DM-02 | Nhập liệu: Danh mục sản phẩm / thuốc đông y | Content | Internal | 🔴 Cao |
| DM-03 | Nhập liệu: Bài thuốc, phác đồ điều trị đặc trưng | Content | Internal | 🔴 Cao |
| DM-04 | Nhập liệu: Quy trình vận hành, chính sách bán hàng | Content | Internal | 🟡 TB |
| DM-05 | Xây dựng React SPA cho Hub Đỗ Minh Đường (dmd.medinet.vn): layout, sidebar, search bar riêng Hub | Frontend | dmd.medinet.vn | 🟡 TB |
| DM-06 | Cấu hình ChromaDB collection cho Đỗ Minh Đường | RAG | Internal | 🟡 TB |
| DM-07 | Embedding & index toàn bộ tài liệu Đỗ Minh Đường | RAG | Internal | 🟡 TB |
| DM-08 | Test RAG query cho nội dung Đỗ Minh Đường | RAG | Internal | 🟡 TB |
| DM-09 | MCP connector: data Đỗ Minh Đường expose qua Hub Tổng MCP endpoint | MCP | Qua Hub Tổng | 🟢 Thấp |

| Mã | Task | Module | Scope | Ưu Tiên |
| --- | --- | --- | --- | --- |
| HC-01 | Xác định cấu trúc nội dung Wiki HCNS (outline) | Content | Internal | 🔴 Cao |
| HC-02 | Nhập liệu: Sơ đồ tổ chức (Org Chart) toàn công ty | Content | Internal | 🔴 Cao |
| HC-03 | Nhập liệu: Chính sách nhân sự, nội quy lao động | Content | Internal | 🔴 Cao |
| HC-04 | Nhập liệu: Quy trình onboarding, offboarding | Content | Internal | 🔴 Cao |
| HC-05 | Nhập liệu: Mô tả công việc (JD) từng vị trí | Content | Internal | 🟡 TB |
| HC-06 | Nhập liệu: Quy trình đánh giá KPI, chính sách lương thưởng | Content | Internal | 🟡 TB |
| HC-07 | Xây dựng React SPA cho Hub HCNS (hcns.medinet.vn): layout, sidebar, search bar riêng Hub | Frontend | hcns.medinet.vn | 🟡 TB |
| HC-08 | Cấu hình ChromaDB collection cho HCNS | RAG | Internal | 🟡 TB |
| HC-09 | Embedding & index toàn bộ tài liệu HCNS | RAG | Internal | 🟡 TB |
| HC-10 | MCP connector: data HCNS expose qua Hub Tổng MCP endpoint | MCP | Qua Hub Tổng | 🟢 Thấp |

| Mã | Task | Ưu Tiên |
| --- | --- | --- |
| MC-01 | Thiết kế kiến trúc MCP Server trên Go — chạy tại Hub Tổng (theo MCP spec 2025-2026) | 🔴 Cao |
| MC-02 | Xây dựng MCP Server: endpoint /mcp/query (SSE + HTTP) tại Hub Tổng | 🔴 Cao |
| MC-09 | Bảo mật MCP: API key auth, rate limiting, RBAC cho write ops — tại Hub Tổng API Gateway | 🔴 Cao |
| MC-10 | Documentation MCP API cho team và AI tools sử dụng | 🟡 TB |

| Tool Name | Loại | Chức Năng | Input Chính | Mã |
| --- | --- | --- | --- | --- |
| wiki_search | Read | Tìm kiếm ngữ nghĩa qua RAG trong Hub chỉ định | query, hub_id, top_k | MC-03 |
| wiki_get_page | Read | Lấy nội dung đầy đủ 1 trang wiki | page_id hoặc slug | MC-04 |
| wiki_search_all | Read | Search cross-hub qua Aggregation Layer (Hub Tổng) | query, top_k | AG-11 |
| wiki_create_page | Write | Tạo page mới trong Hub từ AI content | title, content, hub_id, category, tags | MC-05 |
| wiki_update_page | Write | Cập nhật page đã có | page_id, content | MC-06 |
| wiki_post_page | Write | POST content + metadata lên Hub, qua review flow | title, content, hub_id, category, tags | AP-03 |
| wiki_post_draft | Write | Lưu nháp, status=draft, chưa publish | title, content, hub_id | AP-04 |
| wiki_append_section | Write | Thêm section H2/H3 vào page đã có | page_id, section_content | AP-05 |
| wiki_suggest_page | Read+AI | Đề xuất page phù hợp để gắn nội dung mới | content hoặc title | AP-06 |

| Mã | Task | Ưu Tiên |
| --- | --- | --- |
| MC-07 | Tích hợp MCP với Claude AI — test end-to-end trên Claude Desktop (Hub Tổng endpoint) | 🟡 TB |
| MC-08 | Tích hợp MCP với ChatGPT / Gemini (nếu cần) | 🟢 Thấp |

| Mã | Task | Ưu Tiên |
| --- | --- | --- |
| RG-01 | Setup ChromaDB server (Docker standalone) | 🔴 Cao |
| RG-02 | Lựa chọn Embedding Model: BGE-M3 (ưu tiên tiếng Việt) hoặc OpenAI | 🔴 Cao |
| RG-03 | Pipeline: Wiki content -> Semantic Chunking -> Embedding -> ChromaDB (trigger từ Hub con) | 🔴 Cao |
| RG-04 | Go service: Embedding API wrapper | 🔴 Cao |
| RG-05 | Go service: ChromaDB client (insert, query, delete) | 🔴 Cao |
| RG-06 | API endpoint: /api/search?q= với kết quả RAG — expose tại Hub Tổng | 🔴 Cao |
| RG-07 | Tích hợp RAG search vào giao diện React Wiki (search bar) | 🟡 TB |
| RG-08 | Auto-sync qua Redis queue: tạo/sửa wiki page -> re-embed async (Hub con trigger) | 🟡 TB |
| RG-09 | Đánh giá chất lượng RAG: test set 20 câu hỏi / Hub | 🟡 TB |
| RG-10 | Tối ưu chunk size, overlap (20-30%), top-k riêng từng Hub | 🟢 Thấp |

| Model | Ưu Điểm | Nhược Điểm | Khuyến Nghị |
| --- | --- | --- | --- |
| BGE-M3 | Mạnh tiếng Việt, self-hosted, miễn phí | Cần GPU/RAM server đủ mạnh | Ưu tiên dùng |
| OpenAI text-embedding-3-small | Dễ tích hợp, chất lượng tốt | Chi phí API, data ra ngoài | Fallback nếu không có GPU |
| Qwen3-Embedding | Benchmark multilingual 2026 tốt hơn BGE-M3 | Mới, cần evaluation | Test thêm ở Phase 2 |

| Mã | Task | Ưu Tiên |
| --- | --- | --- |
| AP-07 | API: POST /api/hubs/{hub_id}/pages — tạo page mới từ AI content (Hub Tổng endpoint) | 🔴 Cao |
| AP-08 | API: PATCH /api/hubs/{hub_id}/pages/{id}/sections — append section | 🟡 TB |
| AP-09 | Auto-format: Markdown Claude -> HTML lưu DB (goldmark hoặc blackfriday Go) | 🔴 Cao |
| AP-10 | Auto-slug: sinh URL slug từ title tiếng Việt -> ASCII slug | 🟡 TB |
| AP-11 | Lưu metadata: ai_generated=true, source_prompt, claude_model, created_via=mcp | 🟡 TB |
| AP-12 | Auto re-embed qua Redis queue: POST page mới -> chunk & embed ChromaDB Hub | 🔴 Cao |
| AP-13 | Workflow duyệt bài: AI-page -> pending_review -> Editor duyệt -> published | 🟡 TB |
| AP-14 | Notification: email / in-app khi có page AI chờ duyệt | 🟢 Thấp |
| AP-15 | Duplicate detection: kiểm tra similarity > 0.85 trước khi POST (Hub Tổng API) | 🟡 TB |
| AP-21 | Rate limiting: giới hạn 20 AI pages / ngày / user | 🟡 TB |
| AP-22 | Content sanitize: lọc XSS — bluemonday Go (bắt buộc) | 🔴 Cao |
| AP-23 | Audit log: mọi page tạo/sửa bởi AI lưu vào Central DB | 🟡 TB |

| Mã | Task | Ưu Tiên |
| --- | --- | --- |
| AP-01 | Thiết kế UX flow: Claude reply -> chọn đoạn -> review -> POST lên Hub Tổng API | 🔴 Cao |
| AP-02 | Màn hình Review & Edit (React component): chỉnh title, hub, category, tags trước khi đăng | 🔴 Cao |
| AP-16 | UI: nút 'Đăng lên Wiki' dưới mỗi response Claude (Editor+ mới thấy) — React button | 🔴 Cao |
| AP-17 | UI: bôi chọn đoạn text để chỉ POST phần được chọn (React floating action button) | 🟡 TB |
| AP-18 | UI Review modal (React): dropdown Hub đích, title, category & tags (từ API Hub Tổng) | 🔴 Cao |
| AP-19 | UI: sau đăng thành công -> toast notification (React) + link trực tiếp đến page mới | 🟡 TB |
| AP-20 | Badge 'AI Generated' trên trang wiki tạo từ Claude (ẩn được sau khi Editor review) | 🟢 Thấp |

| Mã | Task | Ưu Tiên |
| --- | --- | --- |
| DO-01 | Setup server / VPS (Linux, Docker Compose) | 🔴 Cao |
| DO-02 | Dockerfile cho Go backend Hub Tổng (multi-stage build) + Go service Hub con (internal) | 🔴 Cao |
| DO-03 | Dockerfile mỗi React app (Hub Tổng + 3 Hub Dự Án): Vite build → Nginx static. 4 container frontend riêng | 🔴 Cao |
| DO-04 | Docker Compose: 1 Go API + 4 React Nginx (wiki/tamdao/dmd/hcns) + 4 PostgreSQL + ChromaDB + Redis | 🔴 Cao |
| DO-05 | Setup domain + wildcard SSL *.medinet.vn (Let's Encrypt) — Nginx routing theo subdomain đến đúng React app | 🔴 Cao |
| DO-06 | CI/CD pipeline (GitHub Actions: test -> build -> deploy) | 🟡 TB |
| DO-07 | Backup tự động PostgreSQL (per Hub) + ChromaDB (per collection) | 🟡 TB |
| DO-08 | Monitoring & logging: Prometheus + Grafana + Loki (alerting) | 🟢 Thấp |

| Mã | Task | Phụ Trách | Ưu Tiên |
| --- | --- | --- | --- |
| QA-01 | Unit test Go backend — Hub Tổng API endpoints | Backend Dev | 🟡 TB |
| QA-02 | Integration test: Hub Tổng API + Database + ChromaDB + Redis | Backend Dev | 🟡 TB |
| QA-03 | UAT: Team nội bộ test từng Hub dự án qua React UI | PM | 🔴 Cao |
| QA-04 | UAT: Test MCP với Claude AI end-to-end (Hub Tổng endpoint) | AI Engineer | 🔴 Cao |
| QA-05 | Performance test: load 100 concurrent users — đo tại Hub Tổng API | DevOps | 🟡 TB |
| QA-06 | Security audit: OWASP Top 10 — SQL injection, XSS, CSRF | Backend Dev | 🔴 Cao |
| QA-07 | Go live: Deploy production + thông báo team | PM | 🔴 Cao |
| QA-08 | Training: Hướng dẫn sử dụng cho từng team (tài liệu + session) | PM | 🟡 TB |

| Nhóm Task | Tasks Cần Hoàn Thành | Người Thực Hiện |
| --- | --- | --- |
| Infrastructure | DO-01, DO-02, DO-03, DO-04 (incl. Redis), DO-05 | DevOps |
| Hub Tổng API Gateway | HT-01 -> HT-05 (schema, API CRUD, routing) | Backend Dev |
| Auth (khung) | HT-06 (tạm thời basic auth, chi tiết ở sprint Auth) | Backend Dev |
| RAG Foundation | RG-01 -> RG-06 (ChromaDB + embed pipeline) | AI Engineer |
| MCP Read-only (Hub Tổng) | MC-01, MC-02, MC-03, MC-04 (search + get_page) | AI Engineer |
| AI Post Core | AP-07, AP-09, AP-22, AP-12 (via queue) | Backend Dev |
| Hub mẫu (HCNS) | HC-01 -> HC-04, DB-03, DB-04 | Content + Backend |
| Database Isolation | DB-04, DB-06, DB-10 (Central DB + security) | Backend Dev |
| React Frontend MVP | HT-07, HT-10: Setup Vite monorepo + Hub Tổng SPA (wiki.medinet.vn) + 1 Hub Dự Án SPA mẫu (hcns.medinet.vn) với auth độc lập. | Frontend Dev |

| Rủi Ro | Xác Suất | Tác Động | Mitigation |
| --- | --- | --- | --- |
| ChromaDB scale kém khi data lớn (> 100K vectors/Hub) | Trung bình | Cao | Thiết kế abstraction layer (interface) để dễ swap Vector DB. Đánh giá migrate Phase 3. |
| MCP write bị lạm dụng / spam page | Thấp | Cao | RBAC nghiêm ngặt + rate limiting (20 pages/ngày/user) + approval workflow + audit log tại Hub Tổng API. |
| Domain Expert (YHCT, dược liệu) không available | Cao | Cao | Xác nhận availability trước Phase 1. Tách content tasks khỏi critical path kỹ thuật. |
| Auto-embed blocking API response | Cao (nếu không queue) | Trung bình | Bắt buộc dùng Redis async queue từ Phase 1. |
| Concurrent editing conflict (nhiều Editor cùng sửa) | Trung bình | Trung bình | Version history (HT-12) + optimistic locking. Yjs Phase 3. |
| Data privacy vi phạm (dữ liệu y tế, lương HCNS) | Thấp | Rất Cao | Encryption at rest, phân quyền PostgreSQL level, audit log đầy đủ, review compliance. |
| Team content quá tải với 14 content tasks ưu tiên cao | Cao | Trung bình | Phase 1 chỉ tập trung 1 Hub (HCNS). Phân bổ Domain Expert rõ ràng trước khi bắt đầu. |
| Multi-SPA subdomain — auth độc lập, UX login nhiều lần | Trung bình | Thấp | v1.3: Kiến trúc multi-SPA, auth độc lập — 4 React app riêng, mỗi app login form riêng, JWT secret riêng. Rủi ro: user nhầm lẫn khi phải đăng nhập nhiều lần ở nhiều subdomain. Mitigation: UX rõ ràng, mỗi subdomain branding màu riêng, thông báo 'Bạn đang ở Hub [Tên]'. |

| Module | Tổng Tasks | 🔴 Cao | 🟡 TB | 🟢 Thấp |
| --- | --- | --- | --- | --- |
| Architecture | 2 | 2 | 0 | 0 |
| Backend-DB | 1 | 1 | 0 | 0 |
| Backend-API | 6 | 4 | 2 | 0 |
| Backend-Auth | 1 | 1 | 0 | 0 |
| Frontend (React) | 9 | 2 | 7 | 0 |
| Content | 14 | 10 | 4 | 0 |
| RAG | 10 | 6 | 3 | 1 |
| MCP (Hub Tổng only) | 9 | 4 | 4 | 1 |
| MCP-Security | 1 | 1 | 0 | 0 |
| Infra / DevOps | 8 | 5 | 2 | 1 |
| QA / Testing | 8 | 4 | 3 | 1 |
| Security | 1 | 1 | 0 | 0 |
| Docs / Training | 2 | 0 | 2 | 0 |
| Backend-DB (Hub DBs) | 10 | 8 | 2 | 0 |
| Aggregation Layer | 13 | 7 | 5 | 1 |
| AI Post to Hub | 24 | 10 | 11 | 3 |
| TỔNG CỘNG | 122 | 68 | 49 | 5 |
