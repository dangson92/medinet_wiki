# Technology Stack

> ⚠️ **STALE — KHÔNG DÙNG LÀM REFERENCE.** Snapshot này phân tích codebase Go cũ (`backend/`) đã xóa khỏi working tree 2026-05-14 (TEARDOWN-01 pull-in). Chỉ giữ làm tư liệu lịch sử. Stack M2 hiện hành: `.planning/research/STACK.md` + `.planning/CONVENTIONS.md` (Python `api/`). Reference cho Phase 5/6/7: `frontend/src/services/api.ts` + git tag `m1-go-archived`.

**Analysis Date:** 2026-04-28

Repository `Hub_All` là hệ thống RAG (Retrieval-Augmented Generation) trung tâm của Medinet, gồm hai thành phần chính:
- **Backend** (Go + Gin) — REST API, RAG pipeline, quản lý Hub đa tenant.
- **Frontend** (React + Vite + TypeScript) — bảng điều khiển quản trị (Hub_All console).

## Languages

**Primary:**
- Go `1.25.0` — toàn bộ backend service (`backend/cmd/server/main.go`, `backend/internal/...`).
- TypeScript `~5.8.2` — toàn bộ frontend SPA (`frontend/src/**/*.ts(x)`).

**Secondary:**
- SQL (PostgreSQL dialect) — file migration tại `backend/internal/database/migrations/001_bootstrap.up.sql` … `008_usage_rollup.up.sql`, kèm script seed `backend/scripts/seed.sql`, `backend/scripts/seed_demo.sql`.
- Bash / PowerShell / Batch — script khởi tạo Windows: `backend/start.ps1`, `backend/scripts/setup_windows.bat`, `backend/scripts/generate_keys.sh`.

## Runtime

**Backend:**
- Go runtime `1.25.0` (theo `backend/go.mod`).
- Build artifact: `backend/server.exe` (Windows binary, `CGO_ENABLED=0`, xem `backend/Makefile` target `build`).
- Cổng mặc định: `8180` (env `APP_PORT`, file `backend/.env.example`). Lưu ý cổng `8080` trùng dải Hyper-V loại trừ trên Windows.

**Frontend:**
- Node.js (yêu cầu type `@types/node` ^22 — implicit Node 20+).
- Vite dev server cổng `3000`, host `0.0.0.0` (script `dev` trong `frontend/package.json`).

**Package Manager:**
- Backend: `go mod` — lockfile `backend/go.sum` hiện diện.
- Frontend: `npm` — lockfile `frontend/package-lock.json` hiện diện. Không dùng pnpm/yarn.

## Frameworks

**Backend Core:**
- `github.com/gin-gonic/gin` v1.12.0 — HTTP router/framework chính (`backend/internal/router/router.go`).
- `github.com/gin-contrib/cors` v1.7.2 — middleware CORS.
- `github.com/gin-contrib/gzip` (indirect) — nén response.
- `github.com/golang-jwt/jwt/v5` v5.2.1 — sinh và xác thực JWT (RS256, key load từ `backend/keys/private.pem`, `backend/keys/public.pem`).
- `github.com/jackc/pgx/v5` v5.6.0 — driver/pool PostgreSQL (`backend/internal/database/postgres.go`).
- `github.com/redis/go-redis/v9` v9.5.3 — client Redis (`backend/internal/database/redis.go`).
- `github.com/golang-migrate/migrate/v4` v4.17.1 — chạy migration tự động khi khởi động (`backend/internal/database/migrate.go`).
- `github.com/google/uuid` v1.6.0 — sinh UUID.
- `golang.org/x/crypto` v0.49.0 — bcrypt hash mật khẩu (lệnh `backend/cmd/hashpw`).
- `github.com/go-playground/validator/v10` (indirect) — validation request body cho Gin.

**Backend RAG / xử lý tài liệu:**
- `github.com/ledongthuc/pdf` — trích xuất văn bản PDF (`backend/internal/rag/extractor/pdf.go`).
- `github.com/xuri/excelize/v2` v2.10.1 — đọc XLSX (`backend/internal/rag/extractor/xlsx.go`).
- `github.com/richardlehane/mscfb`, `richardlehane/msoleps` — đọc định dạng OLE (DOCX/PPT cũ).
- `github.com/pkoukk/tiktoken-go` v0.1.8 — đếm token chuẩn OpenAI cho chunker.
- `github.com/dlclark/regexp2` — regex Unicode cho NegativeRuleExtractor / chunker.
- `github.com/gabriel-vasile/mimetype` — detect MIME khi upload.
- `google.golang.org/api/drive/v3` — SDK Google Drive cho lưu trữ file (`backend/internal/storage/gdrive.go`).
- `cloud.google.com/go/auth`, `golang.org/x/oauth2` — xác thực Google service account.

**Frontend Core:**
- React `^19.0.0` + `react-dom` `^19.0.0` (`frontend/src/main.tsx`).
- `react-router-dom` `^7.14.0` — routing SPA (`frontend/src/App.tsx`, `frontend/src/Layout.tsx`).
- Vite `^6.2.0` — dev server + bundler (`frontend/vite.config.ts`).
- `@vitejs/plugin-react` `^5.0.4` — plugin React cho Vite.

**Frontend UI / styling:**
- Tailwind CSS `^4.1.14` qua plugin `@tailwindcss/vite` `^4.1.14` (cấu hình trong `frontend/vite.config.ts`, không dùng `tailwind.config.js` truyền thống).
- `autoprefixer` `^10.4.21` — postcss.
- `lucide-react` `^0.546.0` — bộ icon.
- `clsx` `^2.1.1` + `tailwind-merge` `^3.5.0` — gộp className có điều kiện.
- `motion` `^12.23.24` — animation.

**Frontend rich-text editor:**
- TipTap `^3.22.1` (`@tiptap/react`, `@tiptap/starter-kit`, kèm các extension: `link`, `table`, `task-list`, `text-align`, `underline`, `highlight`, `placeholder`, `character-count`, `subscript`, `superscript`) — dùng trong `frontend/src/components/RichTextEditor.tsx`.

**Frontend markdown/AI:**
- `react-markdown` `^10.1.0` + `rehype-sanitize` `^6.0.0` — render câu trả lời từ LLM (`frontend/src/components/CitationText.tsx`, `frontend/src/components/GeminiAssistant.tsx`).
- `@google/genai` `^1.29.0` — SDK chính thức cho Gemini API; xuất hiện trong `frontend/package.json` nhưng phần lớn lời gọi Gemini hiện nằm ở backend (`backend/internal/llm/gemini.go`). Frontend chỉ tham chiếu `mockData` cho demo.

**Build/Dev tooling:**
- `tsx` `^4.21.0` — chạy TypeScript trực tiếp khi cần (devDeps).
- `tsc --noEmit` — script `lint` trong `frontend/package.json` (type-check thuần, không có ESLint riêng).
- `dotenv` `^17.2.3` — nạp biến môi trường (cho lệnh phụ trợ chạy bằng `tsx`).
- `express` `^4.21.2` (+ `@types/express`) — dependency phụ, hiện chưa dùng trong `frontend/src` (có thể phục vụ preview server tương lai).

**Testing:**
- Backend: chỉ có `go test ./...` (target `test` trong `backend/Makefile`); chưa thấy framework bổ sung như `testify`. File `*_test.go` không hiện diện trong `backend/internal/...` ở thời điểm phân tích.
- Frontend: chưa cấu hình framework test (không có `vitest`/`jest` trong `frontend/package.json`).

## Key Dependencies

**Critical (backend):**
- `gin` — đường dẫn HTTP duy nhất; thay đổi sẽ ảnh hưởng toàn bộ handler.
- `pgx/v5` — mọi truy vấn PostgreSQL đi qua `db.Pool` (`backend/internal/database/postgres.go`).
- `go-redis/v9` — cache, rate limit, realtime usage counter (`backend/internal/database/redis.go`, `backend/internal/service/usage_realtime.go`).
- `golang-jwt/jwt/v5` — sinh access/refresh token RS256.
- `golang-migrate/migrate/v4` — migration chạy tự động lúc start, không có cơ chế rollback an toàn nếu thất bại giữa chừng.

**Critical (frontend):**
- `react` 19 + `react-router-dom` 7 — phiên bản mới, lưu ý API breaking so với React 18 / RR 6.
- `@tailwindcss/vite` 4 — Tailwind v4 dùng cấu hình trong CSS (`frontend/src/index.css`), không có `tailwind.config.js`.

**Infrastructure:**
- `chromadb` — chạy ngoài process Go, gọi qua HTTP REST v2 tại `CHROMA_URL` (mặc định `http://localhost:8000`). Dữ liệu persistent tại `chroma_data/` ở root repo và `backend/chroma_data/`.
- `PostgreSQL` 16 — DB nghiệp vụ, kết nối qua DSN dạng `postgres://user:pass@host:port/db?sslmode=...`.
- `Redis` (hoặc Memurai trên Windows) — tùy chọn; nếu thiếu thì server vẫn chạy nhưng tắt rate limit và token cache (xem `backend/cmd/server/main.go` line 64-75).

## Configuration

**Environment (backend):**
- File mẫu: `backend/.env.example` (đã commit).
- File thực tế: `backend/.env` (tồn tại tại workspace, KHÔNG được đọc nội dung — có thể chứa secret).
- Nạp env: do `os.Getenv` trực tiếp trong `backend/internal/config/config.go`. Không dùng `godotenv`; biến phải được export bởi shell hoặc `start.ps1`.
- Một số khóa nhạy cảm (`GEMINI_API_KEY`, `OPENAI_API_KEY`, `LLM_PROVIDER`, `LLM_GEMINI_MODEL`, `RAG_EMBEDDING_PROVIDER/MODEL/CHUNK_SIZE/CHUNK_OVERLAP/BATCH_SIZE`) được lưu trong bảng `settings` của PostgreSQL và nạp lại ở `backend/cmd/server/main.go` (block "Load persisted settings from DB"). Ghi đè giá trị `.env` ở runtime.

**Khóa env quan trọng:**
- `APP_ENV`, `APP_PORT` (default `8180`).
- `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` (BẮT BUỘC), `DB_SSL_MODE`, `DB_MAX_OPEN_CONNS=25`, `DB_MAX_IDLE_CONNS=5`.
- `REDIS_URL` (default `redis://localhost:6379/0`), `REDIS_PASSWORD`.
- `CHROMA_URL` (default `http://localhost:8000`), `CHROMA_TOKEN` (rỗng cho dev).
- `JWT_PRIVATE_KEY_PATH=./keys/private.pem`, `JWT_PUBLIC_KEY_PATH=./keys/public.pem`, `JWT_ACCESS_TOKEN_TTL=15m`, `JWT_REFRESH_TOKEN_TTL=168h`.
- `AES_KEY` (hex 32 byte) — mã hóa password Hub DB lưu trong DB.
- `CORS_ALLOWED_ORIGINS` (CSV).
- `RATE_LIMIT_RPS=10`, `RATE_LIMIT_BURST=20`.
- `RAG_EMBEDDING_PROVIDER` (`openai` | `gemini`), `RAG_EMBEDDING_MODEL`, `RAG_CHUNK_SIZE=512`, `RAG_CHUNK_OVERLAP=50`, `RAG_BATCH_SIZE=100`, `RAG_WORKER_COUNT=3`, `RAG_MAX_FILE_SIZE=52428800` (50 MB), `RAG_UPLOAD_DIR=./uploads`.
- `RAG_AUGMENT_ENABLED` — bật/tắt augmenter Q&A (mặc định bật khi có LLM).
- `OPENAI_API_KEY`, `GEMINI_API_KEY` — key cho LLM/embedding.
- `STORAGE_PROVIDER` (`local` | `gdrive`), `GDRIVE_KEY_FILE`, `GDRIVE_FOLDER_ID`.
- `LLM_PROVIDER` (`gemini` | `openai` | `auto`), `LLM_GEMINI_MODEL` (default `gemini-2.0-flash-lite`).

**Environment (frontend):**
- Biến runtime: `VITE_API_URL` (xem `frontend/src/services/api.ts` line 3) — nếu không set thì auto suy ra từ `window.location.hostname:8180`.
- `DISABLE_HMR` — tắt HMR khi chạy trong AI Studio (xem `frontend/vite.config.ts`).

**Build (frontend):**
- TypeScript: `frontend/tsconfig.json` — target `ES2022`, module `ESNext`, JSX `react-jsx`, `moduleResolution: bundler`, `noEmit: true`, alias `@/* → ./*`.
- Vite: `frontend/vite.config.ts` — plugin `react()` + `tailwindcss()`, alias `@` trỏ về thư mục `frontend/`.

**Build (backend):**
- `backend/Makefile`: `make dev` (go run), `make build` (binary `bin/server.exe`), `make migrate`, `make seed`, `make keys`, `make test`, `make lint` (golangci-lint — chưa thấy file `.golangci.yml`).
- Script Windows: `backend/start.ps1`, `backend/scripts/setup_windows.bat`.

## Platform Requirements

**Development:**
- Windows 10/11 (chính), có cài đặt sẵn cho Memurai (Redis thay thế) qua `setup_windows.bat`.
- Go `1.25.0`, Node 20+ (cho Vite 6), PostgreSQL 16, ChromaDB (`pip install chromadb && chroma run --host localhost --port 8000`), Redis hoặc Memurai.
- OpenSSL/`openssl rand -hex 32` để sinh `AES_KEY`; `bash scripts/generate_keys.sh` để sinh keypair RS256.

**Production:**
- Triển khai dạng binary tự đứng (`bin/server.exe`) + reverse proxy (chưa có Dockerfile/Helm trong repo).
- Tài liệu kế hoạch: `documents/BACKEND_DEVELOPMENT_PLAN.md`, `documents/Medinet_RAG_Pipeline_v3_Refreshed.md`.

---

*Stack analysis: 2026-04-28*
