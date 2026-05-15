# Cấu Trúc Codebase

> ⚠️ **STALE — KHÔNG DÙNG LÀM REFERENCE.** Snapshot này phân tích codebase Go cũ (`backend/`) đã xóa khỏi working tree 2026-05-14 (TEARDOWN-01 pull-in). Chỉ giữ làm tư liệu lịch sử. Cấu trúc M2 hiện hành nằm ở `Hub_All/api/`. Reference cho Phase 5/6/7: `frontend/src/services/api.ts` + git tag `m1-go-archived`.

**Ngày phân tích:** 2026-04-28

## Bố Cục Thư Mục

```
Hub_All/
├── backend/                          # Go API server (Hub Tổng)
│   ├── cmd/                          # Entry points (main packages)
│   │   ├── server/                   # HTTP server chính (`main.go`)
│   │   ├── hashpw/                   # CLI: sinh Argon2 hash mật khẩu
│   │   ├── testpdf/                  # CLI: thử PDF extractor
│   │   └── testtoken/                # CLI: phát hành/verify JWT
│   ├── internal/                     # Code nội bộ (không export ra ngoài module)
│   │   ├── config/                   # Load env vars → struct Config
│   │   ├── database/                 # Postgres pool + Redis client + migrate
│   │   │   └── migrations/           # 8 file migration .up.sql/.down.sql
│   │   ├── handler/                  # HTTP handler (Gin) — 1 file/aggregate
│   │   ├── service/                  # Business logic (gọi repo, RAG, worker)
│   │   ├── repository/               # SQL thuần với pgx/v5
│   │   ├── model/                    # Domain types / DTO
│   │   ├── router/                   # `router.go` — gắn middleware + route
│   │   ├── middleware/               # auth, cors, ratelimit, recovery, security
│   │   ├── rag/                      # RAG pipeline core
│   │   │   ├── chunker/              # 9 chiến lược chunk + StrategicChunker
│   │   │   ├── extractor/            # PDF/DOCX/XLSX/PPTX/CSV/HTML/text
│   │   │   ├── augmenter/            # Auto Q&A + keyword enrichment
│   │   │   ├── pipeline.go           # Orchestrator extract→chunk→embed→upsert
│   │   │   ├── searcher.go           # Vector search single + cross-hub
│   │   │   ├── answerer.go           # LLM answer + inline citation
│   │   │   ├── scorer.go             # Rerank / scoring helpers
│   │   │   └── cache.go              # Redis result cache
│   │   ├── embedding/                # Provider abstraction (OpenAI, Gemini, Swappable)
│   │   ├── llm/                      # LLM abstraction (OpenAI, Gemini, Swappable)
│   │   ├── vectorstore/              # ChromaDB client
│   │   ├── storage/                  # File storage (local, gdrive)
│   │   ├── worker/                   # Worker pool cho ingestion async
│   │   └── pkg/                      # Shared utilities (jwt, crypto, hash, response, validator)
│   ├── scripts/                      # Seed SQL + setup script Windows + sinh khóa RSA
│   ├── keys/                         # JWT RSA key (private/public PEM) — KHÔNG commit
│   ├── chroma_data/                  # ChromaDB persistence (khi chạy local)
│   ├── uploads/                      # File upload mặc định (storage local)
│   ├── bin/                          # Binary phụ
│   ├── go.mod / go.sum               # Dependency Go
│   ├── Makefile                      # build/run/seed targets
│   ├── start.ps1                     # Khởi động Windows
│   ├── server.exe                    # Binary đã build (Windows)
│   ├── .env / .env.example           # Cấu hình runtime (KHÔNG đọc nội dung)
│   └── .gitignore
│
├── frontend/                         # React + Vite + TS SPA
│   ├── src/
│   │   ├── App.tsx                   # Router + ProtectedRoute
│   │   ├── Layout.tsx                # Shell (sidebar, topbar, dark mode)
│   │   ├── main.tsx                  # ReactDOM mount
│   │   ├── index.css                 # Tailwind v4 + token brand
│   │   ├── types.ts                  # Shared TS types
│   │   ├── mockData.ts               # Mock data cho dev/preview
│   │   ├── vite-env.d.ts             # Vite env typing
│   │   ├── pages/                    # Route components (1 file/page)
│   │   ├── components/               # UI components dùng chung
│   │   ├── contexts/                 # AuthContext, ThemeContext
│   │   ├── services/                 # `api.ts` — single API client
│   │   └── lib/                      # `utils.ts` (clsx + tw-merge)
│   ├── dist/                         # Build output (Vite)
│   ├── index.html                    # Vite entry
│   ├── package.json / package-lock.json
│   ├── tsconfig.json
│   ├── vite.config.ts                # plugin react + tailwindcss + alias `@`
│   ├── metadata.json
│   ├── README.md
│   └── .env / .env.example
│
├── chroma_data/                      # Persistence ChromaDB cấp project (khi chạy ở root)
├── documents/                        # Tài liệu thiết kế / kế hoạch
│   ├── BACKEND_DEVELOPMENT_PLAN.md   # Vector-First plan + tech stack chi tiết
│   ├── Medinet_RAG_Pipeline_v2_Full_9Levels.md
│   └── Medinet_RAG_Pipeline_v3_Refreshed.md
├── file_test/                        # File mẫu để test ingestion (PDF/DOCX/XLSX…)
└── .planning/                        # Tài liệu GSD (codebase map, plans, reviews)
    └── codebase/                     # Output của /gsd-map-codebase
```

## Mục Đích Của Từng Thư Mục

**`backend/cmd/server/`:**
- Mục đích: entry point HTTP server.
- Chứa: `main.go` (~440 dòng) wire toàn bộ dependency injection.
- Key files: `backend/cmd/server/main.go`.

**`backend/cmd/{hashpw,testpdf,testtoken}/`:**
- Mục đích: CLI nhỏ phục vụ vận hành / debug.
- Mỗi thư mục có `main.go` riêng.

**`backend/internal/config/`:**
- Mục đích: load + validate env vars, expose struct `Config`.
- Key files: `config.go` (`AppConfig`, `DBConfig`, `RedisConfig`, `ChromaConfig`, `JWTConfig`, `AESConfig`, `CORSConfig`, `RateLimitConfig`, `RAGConfig`, `StorageConfig`).

**`backend/internal/database/`:**
- Mục đích: kết nối hạ tầng + chạy migration.
- Key files: `postgres.go` (pgxpool factory), `redis.go`, `migrate.go` (golang-migrate), thư mục `migrations/` chứa `001_bootstrap` … `008_usage_rollup` (cặp up/down).

**`backend/internal/handler/`:**
- Mục đích: HTTP handler theo aggregate.
- Files: `auth_handler.go`, `hub_handler.go`, `document_handler.go`, `search_handler.go`, `sync_handler.go`, `user_handler.go`, `profile_handler.go`, `audit_handler.go`, `apikey_handler.go`, `usage_handler.go`.

**`backend/internal/service/`:**
- Mục đích: nghiệp vụ thuần.
- Files: `auth_service.go`, `hub_service.go`, `document_service.go`, `search_service.go`, `sync_service.go`, `user_service.go`, `profile_service.go`, `audit_service.go`, `apikey_service.go`, `usage_service.go`, `usage_logger` ẩn trong `usage_service.go`, `usage_realtime.go`, `usage_rollup.go`, `usage_partition.go`.

**`backend/internal/repository/`:**
- Mục đích: tầng SQL bằng pgx, không ORM.
- Files: `user_repo.go`, `hub_repo.go`, `token_repo.go`, `document_repo.go`, `sync_repo.go`, `audit_repo.go`, `apikey_repo.go`, `settings_repo.go` (AES-GCM), `usage_repo.go`.

**`backend/internal/model/`:**
- Mục đích: domain entity + DTO request/response.
- Files: `user.go`, `hub.go`, `document.go`, `page.go`, `search.go`, `sync.go`, `audit.go`, `apikey.go`, `token.go`, `usage.go`.

**`backend/internal/router/`:**
- Mục đích: dựng `gin.Engine`, gắn middleware + route group, đặt 3 inline handler đặc biệt (`/api/rag-config`, `/api/rag-config/collections`, `/api/system-settings`, `/api/ai/chat`).
- Key files: `router.go`.

**`backend/internal/middleware/`:**
- Files: `auth.go` (JWT + RBAC + blacklist), `cors.go`, `ratelimit.go` (gồm `LoginRateLimit`), `recovery.go`, `security.go`.

**`backend/internal/rag/`:**
- Mục đích: core domain — pipeline RAG.
- Files cấp gốc: `pipeline.go`, `searcher.go`, `answerer.go`, `scorer.go`, `cache.go`.
- Subfolder: `chunker/` (`chunker.go` interface, `recursive.go`, `semantic.go`, `entity_profile.go`, `negative_rule.go`, `hierarchical.go`, `contextual.go`, `router.go`, `strategic.go`); `extractor/` (`extractor.go` interface + 1 file mỗi MIME); `augmenter/augmenter.go`.

**`backend/internal/embedding/` & `backend/internal/llm/`:**
- Cấu trúc song song: `provider.go`/`llm.go` (interface) + `openai.go` + `gemini.go` + `swappable.go` + `usage.go`.

**`backend/internal/vectorstore/`:**
- Files: `store.go` (interface `VectorStore`), `chromadb.go` (HTTP client).

**`backend/internal/storage/`:**
- Files: `storage.go` (interface), `local.go`, `gdrive.go`.

**`backend/internal/worker/`:**
- Files: `manager.go` (`WorkerManager` + `EmbedJob`).

**`backend/internal/pkg/`:**
- Subfolder + 1 file/subfolder: `jwt/jwt.go`, `crypto/aes.go`, `hash/argon2.go`, `response/response.go`, `validator/validator.go`.

**`backend/scripts/`:**
- Mục đích: thao tác vận hành.
- Files: `generate_keys.sh` (sinh RSA cho JWT), `seed.sql`, `seed_demo.sql`, `setup_windows.bat`, `setup_windows.md`.

**`backend/keys/` & `backend/uploads/` & `backend/chroma_data/`:**
- Generated/runtime: được tạo lúc setup hoặc runtime.
- Committed: KHÔNG. Đặc biệt `keys/` chứa private key — phải nằm trong `.gitignore`.

**`frontend/src/pages/`:**
- Mục đích: 1 file/route component, không chia subfolder.
- Files: `Login.tsx`, `Dashboard.tsx`, `CrossHubSearch.tsx`, `DocumentIngestion.tsx`, `UserManagement.tsx`, `HubRegistry.tsx`, `SyncQueue.tsx`, `SyncReview.tsx`, `AuditLog.tsx`, `TokenUsage.tsx`, `APIKeyManagement.tsx`, `Settings.tsx`, `Profile.tsx`.

**`frontend/src/components/`:**
- Files: `RichTextEditor.tsx` (Tiptap), `CitationText.tsx` (render `[N]` + popover snippet cho Answerer), `GeminiAssistant.tsx` (chat panel proxy `/api/ai/chat`), `Pagination.tsx`.

**`frontend/src/contexts/`:**
- Files: `AuthContext.tsx` (login/logout/refreshUser, lưu token vào `localStorage`), `ThemeContext.tsx` (dark mode, key `medinet-theme`).

**`frontend/src/services/`:**
- Files: `api.ts` — duy nhất một class `APIClient` export instance `api`. Auto-detect `VITE_API_URL` → fallback `http://${hostname}:8180`.

**`frontend/src/lib/`:**
- Files: `utils.ts` — helper `cn()` (clsx + tailwind-merge).

**`documents/`:**
- Mục đích: thiết kế kiến trúc và RAG pipeline (đầu vào cho mọi phase planning).
- Files: `BACKEND_DEVELOPMENT_PLAN.md`, `Medinet_RAG_Pipeline_v2_Full_9Levels.md`, `Medinet_RAG_Pipeline_v3_Refreshed.md`.

**`file_test/`:**
- Mục đích: file mẫu (PDF/DOCX/XLSX) để test ingestion thủ công, không vào CI.

**`chroma_data/` (cấp project):**
- Mục đích: persistence ChromaDB khi chạy server từ root.
- Generated: Có. Committed: KHÔNG nên (binary lớn).

## Vị Trí File Quan Trọng

**Entry Points:**
- `backend/cmd/server/main.go`: bootstrap toàn bộ backend.
- `frontend/src/main.tsx`: bootstrap React.
- `frontend/src/App.tsx`: định nghĩa route SPA.
- `backend/start.ps1`: script khởi động trên Windows.
- `backend/Makefile`: build/run/seed/test target.

**Configuration:**
- `backend/.env` (production), `backend/.env.example` (mẫu).
- `backend/internal/config/config.go`: parser env → struct.
- `frontend/.env`, `frontend/.env.example`: chứa `VITE_API_URL`.
- `frontend/vite.config.ts`: alias `@` → root frontend, plugin React + Tailwind.
- `frontend/tsconfig.json`.

**Core Logic:**
- `backend/internal/router/router.go`: bản đồ tất cả route HTTP.
- `backend/internal/rag/pipeline.go`: pipeline ingestion 4 stage.
- `backend/internal/rag/searcher.go` + `answerer.go`: luồng query RAG.
- `backend/internal/rag/chunker/strategic.go`: composite chunker mặc định.
- `backend/internal/embedding/swappable.go` + `backend/internal/llm/swappable.go`: hot-swap provider.
- `backend/internal/worker/manager.go`: pool ingestion.
- `frontend/src/services/api.ts`: hợp đồng FE↔BE.

**Database:**
- `backend/internal/database/postgres.go`: pool factory.
- `backend/internal/database/migrate.go`: chạy migration lúc bootstrap.
- `backend/internal/database/migrations/`: SQL schema (`001_bootstrap` users/hubs, `002_wiki` documents/chunks/pages, `003_sync`, `004_audit`, `005_settings`, `006_add_indexes`, `007_token_usage`, `008_usage_rollup`).
- `backend/scripts/seed.sql`, `backend/scripts/seed_demo.sql`: dữ liệu mẫu.

**Security / Keys:**
- `backend/keys/` (RSA PEM cho JWT — không commit).
- `backend/internal/pkg/jwt/jwt.go`, `backend/internal/pkg/crypto/aes.go`, `backend/internal/pkg/hash/argon2.go`.

## Quy Ước Đặt Tên

**Files (Go backend):**
- snake_case theo aggregate + role: `<aggregate>_handler.go`, `<aggregate>_service.go`, `<aggregate>_repo.go`. Ví dụ: `document_handler.go`, `user_service.go`, `apikey_repo.go`.
- File concept core dùng tên đơn: `pipeline.go`, `searcher.go`, `answerer.go`, `manager.go`.
- Test file: `_test.go` (Go convention).

**Files (Frontend TS):**
- PascalCase cho component / page: `Dashboard.tsx`, `CrossHubSearch.tsx`, `RichTextEditor.tsx`, `AuthContext.tsx`.
- camelCase / kebab cho utility: `api.ts`, `utils.ts`, `mockData.ts`, `vite-env.d.ts`, `index.css`.

**Directories:**
- Lowercase, số ít: `handler/`, `service/`, `repository/`, `chunker/`, `extractor/` (không số nhiều "handlers").
- Frontend: lowercase số nhiều cho thư mục chứa nhiều thành phần cùng loại: `pages/`, `components/`, `contexts/`, `services/`, `lib/`.

**Database migration:**
- `NNN_<feature>.<up|down>.sql`, NNN bắt đầu từ 001 (3 chữ số). Ví dụ: `007_token_usage.up.sql`.

**Hub collection (ChromaDB):**
- Mặc định `medinet_<hub_code>` (xem `backend/cmd/server/main.go` dòng 218 và `backend/internal/router/router.go` dòng 330). Có thể override bằng cột `chroma_collection` trong bảng `hubs`.

**Settings keys (Postgres `settings` table):**
- UPPER_SNAKE_CASE, prefix theo nhóm: `RAG_*` (`RAG_EMBEDDING_PROVIDER`, `RAG_CHUNK_SIZE`...), `LLM_*` (`LLM_PROVIDER`, `LLM_GEMINI_MODEL`), `SYSTEM_*`, `SECURITY_*`, `NOTIFY_*`. Secret keys (`GEMINI_API_KEY`, `OPENAI_API_KEY`) có flag `secret=true` được mã hóa AES.

**Endpoint:**
- REST + kebab/lowercase: `/api/auth/login`, `/api/rag-config`, `/api/api-keys`, `/api/audit-logs`, `/api/system-settings`. Resource số nhiều: `/api/users`, `/api/hubs`, `/api/documents`.
- Action subroute dùng động từ: `POST /api/sync/batches/:id/pages/:pid/approve`, `POST /api/api-keys/:id/revoke`.

## Nơi Đặt Code Mới

**Thêm endpoint REST mới:**
- Model DTO: `backend/internal/model/<aggregate>.go`.
- Repo (nếu chạm DB): `backend/internal/repository/<aggregate>_repo.go`, kèm migration mới ở `backend/internal/database/migrations/NNN_<feature>.up.sql` (+ down).
- Service: `backend/internal/service/<aggregate>_service.go`.
- Handler: `backend/internal/handler/<aggregate>_handler.go`.
- Wire dependency: thêm constructor + binding trong `backend/cmd/server/main.go`.
- Đăng ký route: `backend/internal/router/router.go` (group + middleware RBAC nếu cần).

**Thêm chiến lược chunker mới:**
- File: `backend/internal/rag/chunker/<name>.go` implement interface `chunker.Chunker`.
- Tích hợp: cập nhật `StrategicChunker` ở `backend/internal/rag/chunker/strategic.go` hoặc đổi default trong `backend/cmd/server/main.go` dòng 283–301.

**Thêm extractor cho định dạng file mới:**
- File: `backend/internal/rag/extractor/<format>.go` implement interface trong `extractor.go`.
- Đăng ký trong `extractor.ForType` (`extractor/extractor.go`).

**Thêm provider Embedding/LLM mới:**
- File: `backend/internal/embedding/<provider>.go` (impl `EmbeddingProvider`) hoặc `backend/internal/llm/<provider>.go` (impl `llm.LLM`).
- Cập nhật `swappable.go` để chấp nhận provider mode mới + handler trong `router.go` (`PUT /api/rag-config`).

**Thêm migration:**
- File: `backend/internal/database/migrations/NNN_<feature>.up.sql` + `.down.sql`. Số tiếp theo sau `008_usage_rollup`.

**Thêm page mới ở frontend:**
- File: `frontend/src/pages/<PageName>.tsx`.
- Đăng ký route: `frontend/src/App.tsx` bên trong `<Route path="/" element={<Layout/>}>`.
- Thêm link nav trong `frontend/src/Layout.tsx`.
- API call: thêm method vào class `APIClient` ở `frontend/src/services/api.ts`.

**Thêm shared component:**
- File: `frontend/src/components/<Component>.tsx`. Tránh chia subfolder trừ khi nhóm > 5 file cùng họ.

**Thêm shared util TS:**
- File: `frontend/src/lib/<name>.ts`. Hiện chỉ có `utils.ts`.

**Thêm shared util Go:**
- Subfolder tại `backend/internal/pkg/<name>/<name>.go` (ví dụ `pkg/jwt/jwt.go`). Mỗi util một subfolder, một file chính.

## Thư Mục Đặc Biệt

**`backend/keys/`:**
- Mục đích: chứa RSA private/public PEM cho JWT RS256.
- Generated: Có (qua `backend/scripts/generate_keys.sh`).
- Committed: KHÔNG (private key).

**`backend/uploads/`:**
- Mục đích: file upload gốc khi `STORAGE_PROVIDER=local`.
- Generated: Có (lúc runtime).
- Committed: KHÔNG.

**`backend/chroma_data/` & `chroma_data/` (root):**
- Mục đích: persistence ChromaDB.
- Generated: Có.
- Committed: KHÔNG.

**`frontend/dist/`:**
- Mục đích: build output từ `vite build`.
- Generated: Có.
- Committed: KHÔNG.

**`frontend/node_modules/`:**
- Mục đích: dependency npm.
- Generated: Có. Committed: KHÔNG.

**`file_test/`:**
- Mục đích: file mẫu để test ingestion bằng tay.
- Generated: Không (lưu thủ công).
- Committed: tùy nhu cầu (file lớn nên cân nhắc Git LFS).

**`.planning/codebase/`:**
- Mục đích: tài liệu được sinh bởi `/gsd-map-codebase` (chính tài liệu này).
- Generated: Có (qua agent GSD).
- Committed: NÊN commit để team chia sẻ context.

---

*Phân tích cấu trúc: 2026-04-28*
