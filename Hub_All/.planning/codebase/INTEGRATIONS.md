# External Integrations

> ⚠️ **STALE — KHÔNG DÙNG LÀM REFERENCE.** Snapshot này phân tích codebase Go cũ (`backend/`) đã xóa khỏi working tree 2026-05-14 (TEARDOWN-01 pull-in). Chỉ giữ làm tư liệu lịch sử. Stack hiện tại: Python `api/` (FastAPI + cocoindex + pgvector — ChromaDB đã bỏ). Reference cho Phase 5/6/7: `frontend/src/services/api.ts` + git tag `m1-go-archived`.

**Analysis Date:** 2026-04-28

Hub_All là central hub điều phối nhiều "Hub" (mỗi hub là một wiki nội bộ) và xử lý pipeline RAG. Các tích hợp ngoài chia thành ba nhóm: nhà cung cấp LLM/Embedding (Gemini, OpenAI), hạ tầng dữ liệu (PostgreSQL, Redis, ChromaDB), lưu trữ file (Local, Google Drive).

## APIs & External Services

**LLM (Large Language Model):**
- **Google Gemini** — gọi REST trực tiếp tại `https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent`.
  - Implementation: `backend/internal/llm/gemini.go`.
  - SDK/Client: `net/http` thuần (không dùng SDK Google) — header xác thực `x-goog-api-key`.
  - Auth: env `GEMINI_API_KEY`, có thể cập nhật runtime qua Settings UI (`PUT /api/settings`) → lưu vào bảng `settings` của PostgreSQL → nạp lại env biến mỗi lần `Generate()`.
  - Model mặc định: `gemini-2.0-flash-lite` (hằng số `DefaultGeminiModel` ở `backend/internal/llm/gemini.go:17`); có thể override qua env `GEMINI_LLM_MODEL` hoặc DB key `LLM_GEMINI_MODEL`.
  - Tham số sinh: `temperature=0.3`, `maxOutputTokens=2048`.
  - Mọi lời gọi đều record qua `UsageRecorder` → bảng `usage_events` (token + latency).

- **OpenAI Chat** — gọi REST tại `https://api.openai.com/v1/...` (chat completions cho LLM, embeddings cho RAG).
  - Implementation: `backend/internal/llm/openai.go` (chat) và `backend/internal/embedding/openai.go` (embedding).
  - Auth: env `OPENAI_API_KEY` (Bearer token), tương tự Gemini cũng có thể cập nhật runtime qua Settings.
  - Model chat mặc định: `gpt-4o-mini` (hard-coded ở `backend/cmd/server/main.go:249`).
  - Model embedding mặc định: `text-embedding-3-small` (1536 chiều) hoặc `text-embedding-3-large` (3072 chiều) — xem `backend/internal/embedding/openai.go:25`.

- **Lựa chọn provider** — `SwappableLLM` (`backend/internal/llm/swappable.go`) bắt buộc một trong ba mode:
  - `gemini` → chỉ dùng Gemini.
  - `openai` → chỉ dùng OpenAI.
  - `auto` → fallback thông minh, chỉ gọi provider có key.
  - Mặc định lấy theo `RAG_EMBEDDING_PROVIDER` để tránh cross-provider call. Có thể override bằng setting DB `LLM_PROVIDER`.

**Embedding (vector hóa văn bản RAG):**
- **OpenAI Embeddings** — endpoint `https://api.openai.com/v1/embeddings`, model `text-embedding-3-small` / `text-embedding-3-large`.
- **Gemini Embeddings** — `gemini-embedding-001` (3072 chiều) hoặc legacy 768 chiều, gọi REST Gemini API. Implementation `backend/internal/embedding/gemini.go`.
- Wrapper `SwappableEmbedder` (`backend/internal/embedding/swappable.go`) cho phép admin đổi provider tại runtime qua `PUT /api/rag-config` mà không restart server.

**Frontend AI SDK (chưa kích hoạt thực sự):**
- Package `@google/genai` `^1.29.0` đã khai báo trong `frontend/package.json` nhưng `grep` toàn bộ `frontend/src/` không tìm thấy import `@google/genai` thực — file `frontend/src/components/GeminiAssistant.tsx` hiện sử dụng API backend. Giữ làm tham chiếu/dự phòng.

## Data Storage

**Relational Database:**
- **PostgreSQL 16** — DB nghiệp vụ trung tâm `medinet_central`.
  - Connection: env `DB_HOST` `DB_PORT` `DB_NAME` `DB_USER` `DB_PASSWORD` `DB_SSL_MODE` (DSN built ở `backend/internal/config/config.go:57`).
  - Client: `github.com/jackc/pgx/v5` với pool (`MaxOpenConns=25`, `MaxIdleConns=5`) — `backend/internal/database/postgres.go`.
  - Migrations: `backend/internal/database/migrations/001_bootstrap.up.sql` … `008_usage_rollup.up.sql`, chạy tự động lúc start qua `golang-migrate/migrate/v4`.
  - Bảng tiêu biểu: `users`, `hubs`, `documents`, `sync_jobs`, `audit_logs`, `api_keys`, `settings`, `usage_events` (partition theo tháng), `usage_rollup_5min/hourly/daily`.
  - Mã hóa: cột password của Hub DB external được mã hóa AES-256 với `AES_KEY` (hex 32 byte) — xem `backend/internal/repository/settings_repo` (truyền `cfg.AES.Key`).

**Vector Database:**
- **ChromaDB** — chạy ngoài process tại `CHROMA_URL` (mặc định `http://localhost:8000`).
  - Implementation: `backend/internal/vectorstore/chromadb.go`.
  - API: REST v2, base path `/api/v2/tenants/default_tenant/databases/default_database`.
  - Auth: `Authorization: Bearer {CHROMA_TOKEN}` nếu set; dev mode bỏ trống.
  - Distance metric: `hnsw:space=cosine`.
  - Mỗi Hub có một collection riêng theo pattern `medinet_{hub.Code}` (hoặc `hub.ChromaCollection` nếu set), tự tạo lúc start nếu hub `active` (xem `backend/cmd/server/main.go:210-225`).
  - Persistent data: thư mục `chroma_data/` ở root repo và `backend/chroma_data/`.

**Cache / Realtime:**
- **Redis (hoặc Memurai trên Windows)** — `REDIS_URL` mặc định `redis://localhost:6379/0`.
  - Client: `github.com/redis/go-redis/v9` (`backend/internal/database/redis.go`).
  - Mục đích:
    - Rate limiting (middleware `backend/internal/middleware/ratelimit.go`).
    - Cache JWT/refresh token revocation (`tokenRepo` + `authService`).
    - Realtime token usage counter per-minute (`backend/internal/service/usage_realtime.go`).
    - Stats cache với version-bump (`backend/internal/service/usage_*.go`, `StatsCache`).
    - Search result cache (`backend/internal/rag/cache.go` — `NewSearchCache(rdb)`).
  - Server vẫn chạy nếu Redis không available — ghi log warn và tắt rate limit + token cache (`backend/cmd/server/main.go:64-75`).

**File Storage:**
- **Local filesystem** — mặc định, thư mục `RAG_UPLOAD_DIR=./uploads` (`backend/uploads/`).
  - Implementation: `backend/internal/storage/local.go`.
- **Google Drive** — kích hoạt khi `STORAGE_PROVIDER=gdrive`.
  - Implementation: `backend/internal/storage/gdrive.go`.
  - SDK: `google.golang.org/api/drive/v3` + `google.golang.org/api/option`.
  - Auth: Service Account JSON tại `GDRIVE_KEY_FILE`; folder gốc `GDRIVE_FOLDER_ID`.
  - Lưu ý: file service account JSON là secret — KHÔNG commit.

## Authentication & Identity

**Người dùng nội bộ (Hub_All console):**
- Tự xây — không tích hợp IdP/OAuth ngoài.
- JWT RS256 với keypair RSA tại `backend/keys/private.pem` và `backend/keys/public.pem` (sinh bằng `bash backend/scripts/generate_keys.sh`).
- Implementation: `backend/internal/pkg/jwt/` + `backend/internal/service/auth_service.go`.
- TTL: access token 15 phút (`JWT_ACCESS_TOKEN_TTL`), refresh token 168h = 7 ngày (`JWT_REFRESH_TOKEN_TTL`).
- Mật khẩu lưu dạng bcrypt (`golang.org/x/crypto/bcrypt`); helper sinh hash: `backend/cmd/hashpw/`.
- Frontend lưu `access_token` + `refresh_token` trong `localStorage` (xem `frontend/src/services/api.ts`); auto refresh khi gặp 401 rồi retry request.

**API key cho external Hub:**
- Bảng `api_keys` (migration 001/006) + service `backend/internal/service/apikey_service.go` + handler `backend/internal/handler/apikey_handler.go`.
- Dùng cho Hub con gọi sang Hub_All.

## Monitoring & Observability

**Structured Logging:**
- `log/slog` chuẩn thư viện Go, JSON handler, level `Debug` khi `APP_ENV=development`, `Info` khi production (`backend/cmd/server/main.go:33-38`).

**Token / API Usage Tracking:**
- Async batched logger với CopyFrom Postgres (`backend/internal/service/usage_*.go`):
  - Buffer 16 384 entries, flush khi đủ 128 hoặc mỗi 2 giây, threshold CopyFrom 32.
  - Realtime counter per-minute trên Redis.
  - Rollup worker: 5 phút / hourly / daily continuous aggregates.
  - Partition theo tháng, drop sau 365 ngày.

**OpenTelemetry (indirect deps):**
- `go.opentelemetry.io/otel` v1.43.0, `otelhttp` instrumentation — hiện diện qua dependency của Google API client; chưa thấy code instrument tự bổ sung trong `backend/internal/`.

**Error Tracking:**
- Không có Sentry / Rollbar / Datadog SDK trong `go.mod` hoặc `package.json`.

## CI/CD & Deployment

**Hosting:**
- Không có Dockerfile, docker-compose, Kubernetes manifest, Procfile, Vercel/Netlify config trong repo.
- Triển khai thủ công: build binary `make build` → chạy `bin/server.exe` (Windows) hoặc `go build` cho Linux. Frontend build qua `npm run build` rồi deploy `frontend/dist/`.

**CI Pipeline:**
- Không có thư mục `.github/workflows/`, `.gitlab-ci.yml`, `azure-pipelines.yml` ở root `Hub_All/`.
- Lint local: `make lint` dùng `golangci-lint` (chưa có file `.golangci.yml`); frontend chỉ có `npm run lint` = `tsc --noEmit`.

## Environment Configuration

**Required env vars (backend):**
- Bắt buộc: `DB_PASSWORD` (thiếu sẽ panic ngay khi load config — `backend/internal/config/config.go:181`).
- Khuyến nghị: `AES_KEY`, `JWT_PRIVATE_KEY_PATH`, `JWT_PUBLIC_KEY_PATH`, `OPENAI_API_KEY` hoặc `GEMINI_API_KEY` (ít nhất một).
- Toàn bộ danh mục biến: xem `backend/.env.example`.

**Required env vars (frontend):**
- `VITE_API_URL` — URL backend (tùy chọn; nếu thiếu, frontend fallback `http://{hostname}:8180`).
- `DISABLE_HMR` — chỉ dùng trong môi trường AI Studio.

**Secrets location (KHÔNG đọc nội dung):**
- `backend/.env` — environment file thực tế.
- `backend/keys/private.pem`, `backend/keys/public.pem` — keypair JWT.
- `GDRIVE_KEY_FILE` (đường dẫn tự cấu hình) — JSON service account Google Drive.
- Bảng `settings` PostgreSQL — chứa `OPENAI_API_KEY`, `GEMINI_API_KEY` đã mã hóa khi admin lưu qua UI.

## Webhooks & Callbacks

**Incoming:**
- Không phát hiện webhook receiver từ bên thứ ba (Stripe/GitHub/Slack…).

**Outgoing:**
- Không phát hiện outgoing webhook chủ động (Slack/Teams/Discord notifier…). Chỉ gọi REST đến Gemini, OpenAI, Google Drive như đã liệt kê.

## Hub Federation (gọi sang DB khác)

- Mỗi Hub đăng ký trong bảng `hubs` có thể bao gồm thông tin DB riêng; password được mã hóa AES-256 trước khi lưu (`backend/internal/repository/settings_repo`).
- `hub_service.go` (`backend/internal/service/hub_service.go`) và `sync_service.go` chịu trách nhiệm sync dữ liệu giữa Hub_All và Hub con — đây là tích hợp inter-service nội bộ Medinet, không phải SaaS bên thứ ba.

---

*Integration audit: 2026-04-28*
