# Codebase Concerns

**Analysis Date:** 2026-04-28

Tài liệu này tổng hợp các vấn đề về tech debt, bug đã biết, rủi ro bảo mật, hiệu năng, vùng code dễ vỡ và các tệp đang dở dang trong repo `Hub_All` (backend Go + frontend React/Vite/TS + ChromaDB).

---

## 1. Security Considerations

### 1.1. Thiếu `.gitignore` ở thư mục gốc — RỦI RO CAO

- **Vấn đề:** Repo chỉ có `.gitignore` riêng trong `backend/` (`backend/.gitignore`) và `frontend/` (`frontend/.gitignore`), KHÔNG có `.gitignore` ở root `Hub_All/`.
- **Hệ quả:** Các thư mục/tệp ở root sẽ bị Git track nếu vô tình `git add .`:
  - `chroma_data/` (root) — vector database SQLite (~1.3 MB, file `chroma_data/chroma.sqlite3`).
  - `file_test/tri_thuc_chinh_tri.pdf` — file PDF test.
  - `documents/*.docx` ở thư mục cha (`../DMD_T3-01_HoSo_BacSi_EEAT_v1.docx` đang untracked).
- **Bằng chứng:** `git status` cho thấy `?? chroma_data/`, `?? file_test/`, `?? backend/` — tức backend đã từng KHÔNG nằm trong tracked tree (mới được tạo lại?), và chroma_data đang trôi nổi.
- **Fix:** Tạo `.gitignore` ở root tại `d:\ChuongNV_Medinet\AI\medinet_wiki\Hub_All\.gitignore`:
  ```
  # Vector store
  chroma_data/
  # Test fixtures
  file_test/
  # IDE
  .vscode/
  .idea/
  # Build artifacts
  *.exe
  ```
- **Ưu tiên:** CAO.

### 1.2. Có file Google Cloud service account đang nằm trong `backend/keys/`

- **File nghi ngờ:** `backend/keys/backup-driver-490006-3f02ddb7e55e.json`.
- **Ngữ cảnh:** Tên file giống dạng GCP service account JSON (project-id + key-id). `backend/internal/config/config.go:175` có `GDRIVE_KEY_FILE` env var, gợi ý dùng cho Google Drive backup.
- **Tình trạng track:** Thư mục `backend/keys/` ĐƯỢC ignore qua `backend/.gitignore` (dòng `keys/`), nên về lý thuyết không lộ qua Git.
- **Rủi ro còn lại:**
  1. Nếu ai đó copy file ra ngoài `keys/` thì có thể bị commit.
  2. File khoá riêng RSA `backend/keys/private.pem` cũng nằm cùng thư mục — nếu cấu hình `JWT_PRIVATE_KEY_PATH` thay đổi, file có thể bị di chuyển ra vị trí được track.
- **Khuyến nghị:** Audit lịch sử Git (`git log --all --full-history -- backend/keys/`) để chắc chắn các secret này CHƯA TỪNG bị commit. Nếu đã commit, phải rotate ngay (tạo service account mới + JWT keypair mới).
- **Ưu tiên:** CAO.

### 1.3. AES key mặc định nguy hiểm trong `.env.example`

- **File:** `backend/.env.example:42`
  ```
  AES_KEY=0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef
  ```
- **Vấn đề:** Đây là giá trị placeholder dễ đoán. Nếu dev copy `.env.example` thành `.env` mà quên thay, mọi password Hub-DB lưu trong DB (mã hoá AES) sẽ bị decrypt được nếu attacker đọc DB.
- **Khuyến nghị:**
  1. Thay placeholder bằng ghi chú: `AES_KEY=<bắt buộc — sinh bằng: openssl rand -hex 32>`.
  2. Trong `backend/internal/config/config.go:152-154`, thêm validation: nếu `AES_KEY` rỗng hoặc bằng giá trị placeholder → fail-fast (giống cách `DB_PASSWORD` đã làm ở dòng `config.go:180-182`).
- **Ưu tiên:** CAO.

### 1.4. Access token / refresh token lưu trong `localStorage`

- **Vị trí:**
  - `frontend/src/contexts/AuthContext.tsx:53-54`: `localStorage.setItem('access_token', ...)`, `localStorage.setItem('refresh_token', ...)`
  - `frontend/src/services/api.ts:20`: đọc token từ `localStorage`.
- **Rủi ro:** Bất kỳ XSS payload nào (qua `RichTextEditor`, `ReactMarkdown` của `GeminiAssistant`, hoặc dữ liệu hub không sanitize) đều có thể đọc token. Refresh token trong localStorage đặc biệt nguy hiểm vì TTL 7 ngày (`backend/.env.example:37`: `JWT_REFRESH_TOKEN_TTL=168h`).
- **Khuyến nghị:** Chuyển refresh token sang `httpOnly Secure SameSite=Strict cookie`, chỉ giữ access token (TTL 15 phút) trong memory hoặc `sessionStorage`. Cần thay đổi cả backend (set cookie ở `/api/auth/login`, `/api/auth/refresh`) và frontend (`api.ts` bỏ `localStorage` cho refresh).
- **Ưu tiên:** TRUNG BÌNH (giảm dần khi đã có CSP + sanitize tốt).

### 1.5. CORS dùng list origin trực tiếp + AllowCredentials

- **File:** `backend/internal/middleware/cors.go:12-26`.
- **Cấu hình:** `AllowCredentials: true` cùng list origin từ env `CORS_ALLOWED_ORIGINS`.
- **Rủi ro:**
  1. Nếu `.env` của môi trường production lỡ chứa `*` hoặc origin staging, sẽ mở rộng vector tấn công CSRF (do `AllowCredentials: true` không cho phép `*`, nhưng nếu admin set sai sẽ bị browser từ chối).
  2. Mặc định trong `backend/.env.example:45`: `CORS_ALLOWED_ORIGINS=http://localhost:5173,http://localhost:3000,http://192.168.0.113:3000,http://192.168.0.113:5173` — bao gồm cả IP LAN, có thể bị quên khi deploy.
- **Khuyến nghị:**
  - Trong `backend/internal/config/config.go` thêm validation: nếu `APP_ENV=production` thì cấm origin `localhost`/`127.0.0.1`/IP private (RFC1918).
- **Ưu tiên:** TRUNG BÌNH.

### 1.6. Auth — không tự khoá tài khoản sau N lần đăng nhập sai

- **File:** `backend/internal/service/auth_service.go:60-66`.
- **Hiện trạng:** Khi mật khẩu sai, gọi `s.userRepo.IncrementFailedLogin(ctx, user.ID)` (chỉ tăng counter), nhưng KHÔNG có logic so sánh `failed_login_count >= N` → set `LockedUntil`. Field `LockedUntil` được kiểm tra ở dòng 54, nhưng không có chỗ nào ghi vào field đó.
- **Mitigation hiện có:** Có rate-limit theo IP: `backend/internal/middleware/ratelimit.go:17-41` (5 lần / 60s / IP).
- **Hệ quả:** Attacker có thể brute-force qua nhiều IP / VPN — `failed_login_count` tăng vô hạn nhưng tài khoản không bao giờ tự khoá.
- **Fix:** Trong `auth_service.go:60-66`, sau khi `IncrementFailedLogin`, đọc `user.FailedLoginCount + 1` rồi nếu vượt ngưỡng (vd 10) → cập nhật `locked_until = NOW() + 15min`.
- **Ưu tiên:** TRUNG BÌNH.

### 1.7. `GeminiAssistant` không gọi Gemini trực tiếp từ client — TỐT, nhưng còn tàn dư

- **Kiểm chứng:** `frontend/src/components/GeminiAssistant.tsx:41-44` gọi `api.aiChat(...)` → `frontend/src/services/api.ts:275-280` → `POST /api/ai/chat` (proxy backend).
- **Backend proxy:** `backend/internal/router/router.go:562-599` giữ key trên server, không lộ ra client. ĐẠT YÊU CẦU bảo mật.
- **Tàn dư cần dọn:**
  1. `frontend/package.json:14` còn dependency `"@google/genai": "^1.29.0"` — không còn được import (kiểm tra grep `@google/genai` trong `frontend/src` không có hit) → bloat bundle, gỡ được.
  2. `frontend/.env.example:4` vẫn ghi `GEMINI_API_KEY="MY_GEMINI_API_KEY"` — sai lệch với kiến trúc proxy hiện tại, dễ làm dev mới hiểu nhầm là phải set key trên client. Cần XOÁ.
  3. `frontend/README.md:18` còn hướng dẫn `Set the GEMINI_API_KEY in .env.local` — cập nhật.
- **Ưu tiên:** TRUNG BÌNH (security hygiene).

---

## 2. Tech Debt

### 2.1. File quá lớn — vi phạm SRP

| File | Số dòng |
|------|---------|
| `frontend/src/pages/Settings.tsx` | 1360 |
| `frontend/src/pages/DocumentIngestion.tsx` | 995 |
| `frontend/src/mockData.ts` | 827 |
| `backend/internal/router/router.go` | 602 |
| `frontend/src/services/api.ts` | 605 |
| `backend/internal/rag/searcher.go` | 554 |
| `backend/internal/rag/pipeline.go` | 534 |

- **Vấn đề:**
  - `router.go` chứa cả handler logic (RAG config GET/PUT, system-settings GET/PUT, AI chat proxy) — không thuần "router". Phải tách ra `internal/handler/rag_config_handler.go`, `internal/handler/system_settings_handler.go`, `internal/handler/ai_handler.go`.
  - `Settings.tsx` 1360 dòng — chắc chắn gộp nhiều tab (general, security, RAG config, notification) vào 1 component. Cần tách thành `pages/Settings/index.tsx` + sub-component theo tab.
  - `DocumentIngestion.tsx` 995 dòng — xử lý 3 mode (upload / compose / url) trong một component; cần tách.
- **Ưu tiên:** TRUNG BÌNH.

### 2.2. Mock data còn lẫn trong source — `frontend/src/mockData.ts` (827 dòng)

- **File:** `frontend/src/mockData.ts:1-50` định nghĩa `MOCK_HUBS`, `MOCK_USERS`, etc. — có vẻ là tàn dư từ giai đoạn frontend chạy độc lập.
- **Trạng thái:** File đang `M` (modified) trong git. Cần xác định page nào còn import nó để dọn.
- **Khuyến nghị:** `grep -r "mockData" frontend/src` để liệt kê chỗ dùng → thay bằng API thật → xoá file.
- **Ưu tiên:** THẤP-TRUNG.

### 2.3. Dependency thừa trong `frontend/package.json`

- **File:** `frontend/package.json:13-44`.
- **Thừa nghi vấn:**
  - `"@google/genai": "^1.29.0"` — không có import (đã chuyển sang backend proxy). XOÁ.
  - `"express": "^4.21.2"` + `"@types/express"` + `"dotenv": "^17.2.3"` + `"tsx"` — Vite project không cần Express server. Đây có thể là tàn dư từ template AI Studio. Cần kiểm tra `vite.config.ts` (đã đọc — không dùng) và xoá nếu không có script nào dùng.
- **Ưu tiên:** THẤP (chỉ ảnh hưởng install size, không ảnh hưởng bundle do tree-shaking).

### 2.4. TODO chưa giải quyết

| File:line | Nội dung |
|-----------|----------|
| `backend/internal/service/hub_service.go:134` | `// TODO: implement actual DB connection test with 5s timeout` — endpoint `POST /api/hubs/:id/test-connection` chưa thật sự test, có thể trả về fake-OK. |
| `frontend/src/pages/DocumentIngestion.tsx:43-45` | Hard-code `IS_HUB_TONG = false` ("DEBUG: set false tạm để test nạp tri thức trên Hub Tổng"). Phải chuyển sang feature flag từ backend hoặc env. |

- **Ưu tiên:** TRUNG BÌNH (hub_service); CAO (DocumentIngestion — flag debug rò ra production).

### 2.5. Hot-swap config qua env — tiềm ẩn race condition

- **File:** `backend/internal/router/router.go:148-225`.
- **Vấn đề:** Endpoint `PUT /api/rag-config` dùng `os.Setenv("GEMINI_API_KEY", req.GeminiAPIKey)` để hot-swap. `os.Setenv` KHÔNG thread-safe trên một số platform (đặc biệt khi đọc đồng thời qua `os.Getenv` ở các goroutine khác — pipeline ingestion, searcher). `GET /api/rag-config` cũng đọc `os.Getenv("GEMINI_API_KEY")` ở dòng 79 → đua dữ liệu với ghi.
- **Mitigation hiện có:** `swappableEmbedder.SwapByConfig(...)` ở dòng 198 dùng atomic pointer (giả định). Nhưng env vẫn là global state.
- **Khuyến nghị:** Bỏ `os.Setenv`, lưu key chỉ trong `cfg.RAG.EmbeddingAPIKey` được bảo vệ bằng `sync.RWMutex`, hoặc trong `settingsRepo` + `swappableEmbedder` (nguồn duy nhất).
- **Ưu tiên:** TRUNG BÌNH.

### 2.6. Inline handler rất dài trong router

- **File:** `backend/internal/router/router.go:106-243` (PUT /api/rag-config — 138 dòng inline).
- **Vấn đề:** Logic phức tạp (clear key, save key, hot-swap embedder + LLM, persist settings) lồng trong closure → không testable.
- **Fix:** Tách thành `RAGConfigHandler.Update` ở `internal/handler/rag_config_handler.go`.
- **Ưu tiên:** TRUNG BÌNH.

---

## 3. Performance Bottlenecks

### 3.1. Bundle frontend lớn do mockData + tiptap full

- **Số liệu ước:** `frontend/src/` tổng ~9846 dòng `.ts/.tsx`, riêng `mockData.ts` 827 dòng (~45 KB) sẽ bị tree-shake một phần nhưng `import { MOCK_HUBS } from './mockData'` ở bất kỳ đâu sẽ kéo cả module.
- **Tiptap:** 14 extension trong `frontend/package.json:14-31` đều là dependency runtime, sẽ vào bundle ngay cả khi RichTextEditor chỉ render trong 1 trang (`DocumentIngestion`). Cần dynamic-import RichTextEditor.
- **Khuyến nghị:**
  - `const RichTextEditor = React.lazy(() => import('../components/RichTextEditor'))`.
  - Xoá `mockData.ts` khi tất cả page đã dùng API thật.
- **Ưu tiên:** TRUNG BÌNH.

### 3.2. Chroma query timeout cứng 30s + không có circuit breaker

- **File:** `backend/internal/vectorstore/chromadb.go:35`: `client: &http.Client{Timeout: 30 * time.Second}`.
- **Vấn đề:** Mỗi request tới Chroma (search, count, dimension probe) đợi tối đa 30s. Endpoint `GET /api/rag-config/collections` (router.go:293) lặp `vectorStore.CollectionDimension` + `vectorStore.Count` cho TẤT CẢ hub trong vòng for tuần tự → nếu N hub × 2 call × 30s = potential 1 phút khoá user. Không có goroutine concurrent.
- **Khuyến nghị:**
  1. Parallelize bằng `errgroup` với concurrency limit.
  2. Cache kết quả `dimension` & `count` (TTL 60s) trong Redis.
- **Ưu tiên:** TRUNG BÌNH.

### 3.3. Rate-limit window 1 giây — burst quá hẹp

- **File:** `backend/internal/middleware/ratelimit.go:55-79`.
- **Vấn đề:** Window key dùng `time.Now().Unix()` (giây). Nếu request rơi vào ranh giới giây, burst hiệu dụng có thể bằng `2 × burst`. Đây là sliding window NAIVE.
- **Mitigation:** Với `RATE_LIMIT_BURST=20` (`.env.example:49`), ảnh hưởng nhỏ trong dev. Production cần đổi sang `redis_rate` package hoặc Lua sliding-window thật.
- **Ưu tiên:** THẤP-TRUNG.

### 3.4. Không có pagination ngưỡng tối đa

- **File:** `frontend/src/services/api.ts:112` (getDocuments), `200` (getUsers), v.v. truyền thẳng `per_page` từ UI.
- **Backend:** Trong `backend/internal/handler/document_handler.go:114-115`: `perPage, _ := strconv.Atoi(c.DefaultQuery("per_page", "20"))` — KHÔNG cap max.
- **Rủi ro:** Client gọi `?per_page=100000` → DB load nặng.
- **Fix:** Cap ở handler `if perPage > 100 { perPage = 100 }`.
- **Ưu tiên:** TRUNG BÌNH.

---

## 4. Fragile Areas

### 4.1. `frontend/src/services/api.ts` — single-file API client 605 dòng

- **File:** `frontend/src/services/api.ts:12-306`.
- **Tại sao dễ vỡ:**
  1. Mỗi method định nghĩa thủ công query string (`Object.entries(params).forEach...`) — copy-paste 6 lần (lines 113-117, 175-179, 202-207, 244-249, 252-256, 287-292, 295-301). Một thay đổi convention sẽ phải sửa 6 chỗ.
  2. Type `APIResponse<T>` được trả về thẳng từ `res.json()` mà KHÔNG validate runtime — nếu backend đổi shape sẽ runtime-error sâu trong UI.
  3. Logic refresh token (lines 34-46) chỉ xử lý 1 retry; nếu refresh đang chạy đồng thời với 5 request 401 song song → 5 lần refresh đua nhau → invalidate lẫn nhau.
- **Khuyến nghị:**
  - Dùng helper `buildQuery(params)` chung.
  - Thêm AbortController + dedup refresh token call (singleton promise).
- **Ưu tiên:** TRUNG BÌNH.

### 4.2. AuthContext — race khi `refreshUser` chạy lúc mount mà `getToken` race với login concurrent

- **File:** `frontend/src/contexts/AuthContext.tsx:25-47`.
- **Kịch bản:** User mở 2 tab; tab A logout → xoá `localStorage`; tab B đang fetch `/api/auth/me` → 401 → infinite-loop redirect.
- **Khuyến nghị:** Lắng nghe `storage` event trên window để sync state giữa tabs.
- **Ưu tiên:** THẤP.

### 4.3. Inline handler hot-swap embedder không rollback khi DB persist fail

- **File:** `backend/internal/router/router.go:171-174`:
  ```go
  os.Setenv("GEMINI_API_KEY", req.GeminiAPIKey)
  if cfg.RAG.EmbeddingProvider == "gemini" { cfg.RAG.EmbeddingAPIKey = req.GeminiAPIKey }
  if settingsRepo != nil { _ = settingsRepo.Set(...) }
  ```
- **Vấn đề:** Nếu `settingsRepo.Set` fail (lỗi DB), env đã set rồi → in-memory và DB lệch nhau. Restart server sẽ load DB cũ → mất key.
- **Khuyến nghị:** Persist DB TRƯỚC, set env SAU; nếu DB fail thì fail request.
- **Ưu tiên:** TRUNG BÌNH.

### 4.4. Document upload lưu file system local — không scale ngang

- **File:** `backend/internal/handler/document_handler.go:42-74` + `backend/uploads/{hub_code}/{doc_id}` (đã observe `bvyhct/`, `tamdao/`).
- **Vấn đề:** Khi deploy >1 instance backend, instance A upload, instance B `GET /api/documents/:id/file` không tìm thấy file.
- **Mitigation hiện có:** Có `STORAGE_PROVIDER=gdrive` config (`config.go:174`) — chưa rõ implement.
- **Ưu tiên:** TRUNG BÌNH (chỉ cấp thiết khi scale).

---

## 5. Files đang dở dang (M / ?? trong git status)

Theo `git status` ban đầu:

### 5.1. Files MODIFIED chưa commit (`M`)

```
frontend/package-lock.json
frontend/package.json
frontend/src/App.tsx
frontend/src/Layout.tsx
frontend/src/components/GeminiAssistant.tsx
frontend/src/components/Pagination.tsx
frontend/src/components/RichTextEditor.tsx
frontend/src/index.css
frontend/src/main.tsx
frontend/src/mockData.ts
frontend/src/pages/APIKeyManagement.tsx
frontend/src/pages/AuditLog.tsx
frontend/src/pages/CrossHubSearch.tsx
frontend/src/pages/Dashboard.tsx
frontend/src/pages/DocumentIngestion.tsx
frontend/src/pages/HubRegistry.tsx
frontend/src/pages/Login.tsx
frontend/src/pages/Settings.tsx
frontend/src/pages/SyncQueue.tsx
frontend/src/pages/SyncReview.tsx
frontend/src/pages/UserManagement.tsx
frontend/src/types.ts
frontend/vite.config.ts
```

- **Đánh giá:** 23 file frontend đang sửa dở. Nhiều trong số đó (App.tsx, Layout.tsx, mockData.ts, các page) liên quan tới refactor "wire frontend với backend API thật". Cần commit hoặc rollback rõ ràng.

### 5.2. Files/dirs UNTRACKED (`??`) đáng chú ý

| Path | Đánh giá |
|------|----------|
| `backend/` | **Lạ** — backend chưa từng được commit? Dòng `?? backend/` cho thấy không file Go nào trong index. Cần commit toàn bộ backend hoặc kiểm tra xem có nhánh khác không. |
| `chroma_data/` | Không nên commit — cần thêm vào `.gitignore`. |
| `documents/BACKEND_DEVELOPMENT_PLAN.md` | Tài liệu dev — nên commit. |
| `documents/Medinet_RAG_Pipeline_v2_Full_9Levels.md` | Tài liệu thiết kế RAG — commit. |
| `documents/Medinet_RAG_Pipeline_v3_Refreshed.md` | Tài liệu thiết kế RAG — commit. |
| `file_test/` | Dữ liệu test — không commit. |
| `frontend/src/components/CitationText.tsx` | Component mới — commit. |
| `frontend/src/contexts/` | Toàn bộ context (AuthContext, ThemeContext) chưa track. **Quan trọng** — cần commit. |
| `frontend/src/pages/Profile.tsx` | Page mới — commit. |
| `frontend/src/pages/TokenUsage.tsx` | Page mới — commit. |
| `frontend/src/services/` | API client chưa track. **Quan trọng**. |
| `frontend/src/vite-env.d.ts` | Type def — commit. |
| `../DMD_T3-01_HoSo_BacSi_EEAT_v1.docx` | Nằm ở thư mục cha repo — kệ, không liên quan. |

- **Rủi ro tổng thể:** Nếu CI/CD checkout từ remote, backend hoàn toàn không tồn tại → build fail. Cần verify ngay tình trạng remote bằng `git ls-remote` hoặc kiểm tra bằng `git log --all` xem backend đã được commit ở branch khác chưa.
- **Ưu tiên:** CAO.

### 5.3. Hai bản chroma_data trùng lặp

- `d:\ChuongNV_Medinet\AI\medinet_wiki\Hub_All\chroma_data\` (1.3 MB)
- `d:\ChuongNV_Medinet\AI\medinet_wiki\Hub_All\backend\chroma_data\` (~20 MB, bản đang dùng — `Apr 28 09:44`)

- **Vấn đề:** Bản root có vẻ là tàn dư test cũ (mtime Apr 8). Nên xoá để tránh nhầm lẫn.

---

## 6. Test Coverage Gaps

- **Hiện trạng:** Không tìm thấy thư mục `*_test.go` nào ở backend khi grep nhanh, cũng không có `vitest.config` / `jest.config` ở frontend.
- **Rủi ro:** Toàn bộ logic hot-swap embedder, JWT auth flow, RAG pipeline, sync queue đều chưa có test → bất kỳ refactor nào (như các đề xuất phía trên) đều có nguy cơ vỡ ngầm.
- **Ưu tiên:** CAO (cần ít nhất unit test cho `auth_service`, `jwt manager`, `chromadb client`, `rag pipeline`).

---

## 7. Tóm tắt theo độ ưu tiên

### CAO
1. Tạo `.gitignore` ở root (mục 1.1).
2. Audit `backend/keys/backup-driver-*.json` xem đã từng bị commit chưa (mục 1.2).
3. Validate `AES_KEY` ≠ placeholder + bắt buộc (mục 1.3).
4. Đảm bảo `backend/` được tracked trong Git (mục 5.2) — đây là vấn đề blocker.
5. Bỏ `IS_HUB_TONG = false` debug flag hard-code (mục 2.4).
6. Bổ sung test backend (mục 6).

### TRUNG BÌNH
- Lockout tài khoản khi `failed_login_count` vượt ngưỡng (1.6).
- Refresh token sang httpOnly cookie (1.4).
- Giới hạn `per_page` tối đa (3.4).
- Race condition `os.Setenv` (2.5).
- Tách handler ra khỏi `router.go` (2.6, 4.3).
- Cache + parallel hoá `GET /api/rag-config/collections` (3.2).
- Validate CORS theo `APP_ENV` (1.5).
- Dọn `mockData.ts`, `@google/genai`, `express` khỏi frontend deps (1.7, 2.2, 2.3).

### THẤP
- Sliding window rate-limit chính xác hơn (3.3).
- Cross-tab logout sync (4.2).
- Lazy-load `RichTextEditor` (3.1).
- Xoá bản `chroma_data/` ở root trùng lặp (5.3).

---

*Concerns audit: 2026-04-28*
