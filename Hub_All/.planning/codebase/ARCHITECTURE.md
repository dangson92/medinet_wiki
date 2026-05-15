# Kiến Trúc

> ⚠️ **STALE — KHÔNG DÙNG LÀM REFERENCE.** Snapshot này phân tích codebase Go cũ (`backend/`) đã xóa khỏi working tree 2026-05-14 (TEARDOWN-01 pull-in). Chỉ giữ làm tư liệu lịch sử. Stack hiện tại: Python `api/` (FastAPI + cocoindex + pgvector). Reference cho Phase 5/6/7: `frontend/src/services/api.ts` + git tag `m1-go-archived`.

**Ngày phân tích:** 2026-04-28

## Tổng Quan Pattern

**Tổng thể:** Kiến trúc Layered Monolith hướng Vector-First / RAG Pipeline cho hệ thống wiki nội bộ y tế Medinet đa-hub.

- Backend Go (`backend/`) phục vụ một single-process API duy nhất ("Hub Tổng API"), tổ chức theo các tầng `handler → service → repository` cộng với module RAG độc lập (`internal/rag`).
- Frontend SPA React + Vite + TypeScript (`frontend/`) đóng vai trò UI quản trị / tra cứu wiki cho nhiều subdomain hub (Hub Tổng, Hub Tâm Đạo, Hub DMD…).
- Vector store ChromaDB (`chroma_data/`) lưu chunk embeddings, mỗi hub một collection (mặc định `medinet_<hub_code>`).
- PostgreSQL lưu trạng thái nghiệp vụ (users, hubs, documents, sync, audit, api_keys, settings, usage…), Redis lưu cache + rate limit + token blacklist + realtime usage counters.

**Đặc điểm chính:**
- **Vector-First / RAG Pipeline làm core:** ingestion → chunking đa chiến lược → embedding swappable → ChromaDB → searcher → answerer. Xem `documents/Medinet_RAG_Pipeline_v3_Refreshed.md` và `documents/BACKEND_DEVELOPMENT_PLAN.md` để hiểu chiến lược "Vector-First" (RAG được xây ngay sau Foundation thay vì cuối cùng).
- **Hot-swap Provider:** cả Embedding (`internal/embedding/swappable.go`) và LLM (`internal/llm/swappable.go`) đều được bọc bằng wrapper có mutex để admin đổi provider/model runtime qua `PUT /api/rag-config` mà không restart server.
- **Multi-Hub theo collection:** mỗi hub trong PostgreSQL có cột `chroma_collection` trỏ tới một collection ChromaDB riêng biệt; backend tự `CreateCollection` lúc khởi động cho mọi hub `active` (xem `backend/cmd/server/main.go` dòng 211–225).
- **Async ingestion qua worker pool:** upload tài liệu chỉ enqueue job vào channel; pool goroutine (`internal/worker/manager.go`) chạy pipeline ngầm và cập nhật progress vào DB.
- **Async usage logging:** non-blocking CopyFrom batcher (`internal/service/usage_*.go`) + Redis counter realtime + continuous-aggregate rollup, để mọi lời gọi LLM/embedding không bị chậm bởi I/O ghi log.
- **JWT RS256 + RBAC + rate limit + Argon2:** middleware chain `Recovery → SecurityHeaders → CORS → RateLimit → gzip` áp ở mọi route, RBAC đặt thêm tại từng group (`middleware.RequireRole("admin")`).

## Các Tầng

**HTTP / Middleware:**
- Mục đích: cổng vào HTTP, áp các cross-cutting concerns trước khi vào handler.
- Vị trí: `backend/internal/router/router.go`, `backend/internal/middleware/`
- Chứa: `auth.go` (JWT + RBAC), `cors.go`, `ratelimit.go` (Redis-based + login-specific), `recovery.go`, `security.go`.
- Phụ thuộc: `pkg/jwt`, Redis client, repositories khi cần kiểm tra blacklist/role.
- Được dùng bởi: tất cả route trong `router.Setup()`.

**Handler (Presentation):**
- Mục đích: parse request, validate, gọi service, format response thông qua `pkg/response`.
- Vị trí: `backend/internal/handler/`
- Chứa: `auth_handler.go`, `hub_handler.go`, `document_handler.go`, `search_handler.go`, `sync_handler.go`, `user_handler.go`, `profile_handler.go`, `audit_handler.go`, `apikey_handler.go`, `usage_handler.go`.
- Phụ thuộc: services tương ứng + Gin context.
- Được dùng bởi: `router.Setup()` (gắn vào các route group).

**Service (Business Logic):**
- Mục đích: nghiệp vụ thuần, điều phối repo + RAG + storage + worker.
- Vị trí: `backend/internal/service/`
- Chứa: `auth_service.go`, `hub_service.go`, `document_service.go` (upload + enqueue), `search_service.go` (gọi `rag.Searcher`/`rag.Answerer`), `sync_service.go`, `user_service.go`, `profile_service.go`, `audit_service.go`, `apikey_service.go`, và cụm `usage_*` (logger, realtime, rollup, partition).
- Phụ thuộc: repository, `internal/rag`, `internal/storage`, `internal/worker`, `internal/vectorstore`.
- Được dùng bởi: handler.

**Repository (Data Access):**
- Mục đích: SQL thuần với `pgx/v5` (không ORM), một file một aggregate.
- Vị trí: `backend/internal/repository/`
- Chứa: `user_repo.go`, `hub_repo.go`, `token_repo.go`, `document_repo.go`, `sync_repo.go`, `audit_repo.go`, `apikey_repo.go`, `settings_repo.go` (mã hóa AES qua `pkg/crypto`), `usage_repo.go`.
- Phụ thuộc: `*pgxpool.Pool` từ `internal/database/postgres.go`.
- Được dùng bởi: services, đôi chỗ bởi router (đọc settings).

**Model (Domain):**
- Mục đích: kiểu dữ liệu nghiệp vụ chia sẻ (DTO + entity).
- Vị trí: `backend/internal/model/`
- Chứa: `user.go`, `hub.go`, `document.go`, `page.go`, `search.go`, `sync.go`, `audit.go`, `apikey.go`, `token.go`, `usage.go`.

**RAG Pipeline (Core domain):**
- Mục đích: xương sống xử lý tri thức — extract → chunk → augment → embed → upsert ChromaDB → search → answer.
- Vị trí: `backend/internal/rag/`
- Cấu phần:
  - Orchestrator: `pipeline.go` (`Pipeline.Process` và `Pipeline.ProcessWithChunks`, có 4 stage 0→100% report progress).
  - Extractor: `rag/extractor/` (`pdf.go`, `docx.go`, `xlsx.go`, `pptx.go`, `csv.go`, `html.go`, `text.go`, `tables.go` — chọn theo MIME qua `extractor.ForType`).
  - Chunker: `rag/chunker/` (`recursive.go`, `semantic.go`, `hierarchical.go`, `entity_profile.go`, `negative_rule.go`, `contextual.go`, `router.go`, `strategic.go`). Mặc định runtime dùng `StrategicChunker` (xem `main.go` dòng 283–301): route theo doc type → L1 entity profile (BS/TTUT/BSCKII), L5 negative rules (`always_include`), Hierarchical parent-child, Contextual (LLM-generated header).
  - Augmenter: `rag/augmenter/augmenter.go` — auto Q&A + keyword enrichment kiểu RAGFlow, bật/tắt qua `RAG_AUGMENT_ENABLED`.
  - Searcher: `rag/searcher.go` (single + cross-hub vector search, có cache trong `rag/cache.go`).
  - Answerer: `rag/answerer.go` (LLM tổng hợp + inline citation `[src:<chunk_id>]`).
  - Scorer: `rag/scorer.go` (rerank/post-processing).

**Embedding & LLM (Provider Abstraction):**
- Mục đích: trừu tượng hóa OpenAI/Gemini, hỗ trợ hot-swap và usage recording.
- Vị trí: `backend/internal/embedding/` (`provider.go` interface, `openai.go`, `gemini.go`, `swappable.go`, `usage.go`); `backend/internal/llm/` (`llm.go` interface, `openai.go`, `gemini.go`, `swappable.go`, `usage.go`).
- Hành vi: `SwappableLLM` ép buộc provider exclusivity (mode `gemini` | `openai` | `auto`); `SwappableEmbedder` cho phép `SwapByConfig` runtime; cả hai đều ghi nhận token usage qua `UsageRecorder` không chặn.

**Vector Store:**
- Mục đích: client ChromaDB, ẩn chi tiết HTTP.
- Vị trí: `backend/internal/vectorstore/store.go` (interface `VectorStore`), `backend/internal/vectorstore/chromadb.go` (impl: `CreateCollection`, `Upsert`, `Query`, `Count`, `CollectionDimension`).

**Storage (File Layer):**
- Mục đích: lưu file gốc upload (PDF, DOCX, XLSX...).
- Vị trí: `backend/internal/storage/storage.go` (interface), `local.go` (mặc định, vào `backend/uploads/`), `gdrive.go` (Google Drive service-account).

**Worker (Async Ingestion):**
- Mục đích: pool goroutine chạy pipeline ngầm cho mỗi document upload.
- Vị trí: `backend/internal/worker/manager.go` (`WorkerManager` với buffered channel `jobs` size = workers*10).
- Số worker mặc định cấu hình qua `cfg.RAG.WorkerCount`.

**Database Layer:**
- Mục đích: kết nối + migration + Redis client.
- Vị trí: `backend/internal/database/postgres.go` (pgxpool), `redis.go`, `migrate.go` (chạy `golang-migrate` lúc bootstrap), thư mục `backend/internal/database/migrations/` chứa 8 migration `.up.sql`/`.down.sql` từ `001_bootstrap` tới `008_usage_rollup`.

**Pkg (Shared utilities):**
- Vị trí: `backend/internal/pkg/`
- Chứa: `jwt/jwt.go` (RS256 manager), `crypto/aes.go` (encrypt secrets trong settings), `hash/argon2.go` (password hash), `response/response.go` (chuẩn hóa envelope `{success, data, error, meta}`), `validator/validator.go`.

**Frontend (SPA):**
- Vị trí: `frontend/src/`
- Tầng: `App.tsx` (router) → `Layout.tsx` (chrome) → `pages/*.tsx` (route components) → `services/api.ts` (single API client) → `contexts/AuthContext.tsx`, `contexts/ThemeContext.tsx`.
- Components dùng chung: `components/RichTextEditor.tsx` (Tiptap), `components/CitationText.tsx` (render citation số `[N]` từ Answerer), `components/GeminiAssistant.tsx` (proxy `POST /api/ai/chat`), `components/Pagination.tsx`.

## Luồng Dữ Liệu

**Luồng 1 — Ingestion tài liệu (Document → ChromaDB):**

1. Admin upload file qua UI `frontend/src/pages/DocumentIngestion.tsx` → `POST /api/documents/upload` (multipart).
2. `DocumentHandler.Upload` → `DocumentService` lưu metadata vào `documents` (Postgres), lưu file vật lý qua `storage.FileStorage` (local hoặc Google Drive), set status `pending`.
3. Service đẩy `EmbedJob` vào `WorkerManager.Enqueue` (channel buffered).
4. Worker goroutine gọi `rag.Pipeline.ProcessWithChunks`:
   - Stage 1 (0–10%): `extractor.ForType(fileType).Extract` → text thô → `sanitizeText` chuẩn hóa tiếng Việt (regex `reTrailing`, `reJoinedOx`…).
   - Stage 2 (10–40%): `StrategicChunker.Chunk` route theo doc type, áp L1/L5/Hierarchical/Contextual.
   - Stage 2.5: nếu `augmenter` được bật → auto Q&A + keywords song song (`MaxParallel: 4`).
   - Stage 3 (40–80%): pre-flight `CollectionDimension` check, `embedder.Embed(batch)` với retry+backoff (10 lần, sleep 30s khi gặp 429), batch size theo `cfg.RAG.BatchSize`.
   - Stage 4 (80–100%): `vectorstore.Upsert` vào ChromaDB collection của hub; chunk metadata lưu nhỏ vào Postgres bảng `chunks` (xem migration `002_wiki`).
5. Worker cập nhật `documents.status = completed` và `progress = 100`. Frontend poll `GET /api/documents/:id/status`.

**Luồng 2 — Search ngữ nghĩa (User → Answer):**

1. User nhập query trong `frontend/src/pages/CrossHubSearch.tsx` → `POST /api/search` hoặc `/api/search/cross-hub` hoặc `/api/search/answer`.
2. `SearchHandler` → `SearchService.Search/Answer` → `rag.Searcher`:
   - Build cache key (`BuildCacheKey(query, hubIDs, filters)`); tra `SearchCache` (Redis).
   - Nếu miss: `embedder.Embed([query])` → `vectorStore.Query(collection, vector, topK)` → filter `min_score` (mặc định 0.3) → cache lại.
3. Với endpoint `/answer`: `rag.Answerer` build prompt với các snippet kèm `[src:<chunk_id>]` → `llm.Generate` → parse marker, map về `CitationRef` có `Number` 1-based + snippet → trả response cho frontend.
4. Frontend `components/CitationText.tsx` render `[N]` superscript có popover snippet.

**Luồng 3 — Hot-swap Provider:**

1. Admin sửa cấu hình ở `frontend/src/pages/Settings.tsx` → `PUT /api/rag-config` (router inline handler `backend/internal/router/router.go` dòng 106–243).
2. Router cập nhật `cfg.RAG`, persist vào `settings_repo` (mã hóa AES nếu `secret=true`), set env vars trong process.
3. Gọi `swappableEmbedder.SwapByConfig(provider, key, model)` và `llmClient.SwapByMode(mode)` → mọi caller giữ pointer interface tự động dùng provider mới ở lần `Embed/Generate` kế tiếp, không cần restart.

**Luồng 4 — Auth + JWT refresh:**

1. `POST /api/auth/login` (rate-limit riêng `LoginRateLimit`) → `AuthService` xác thực Argon2 → cấp access (RS256, TTL `cfg.JWT.AccessTokenTTL`) + refresh token, lưu refresh hash vào `tokens` (Postgres).
2. Frontend `services/api.ts` lưu cả 2 token vào `localStorage`. Khi gặp 401 thì gọi `tryRefresh` → `POST /api/auth/refresh`.
3. `POST /api/auth/logout` → blacklist JWT vào Redis với TTL = thời gian còn lại.

**State Management:**
- Frontend: React Context (`AuthContext`, `ThemeContext`) cho global state; mỗi page tự quản local state qua `useState`/`useEffect`. Không có Redux/Zustand.
- Backend: stateless HTTP, state thật sự nằm ở Postgres + Redis + ChromaDB.

## Abstraction Chính

**`embedding.EmbeddingProvider`:**
- Mục đích: hợp đồng cho mọi nhà cung cấp embedding (Embed nhiều text, trả `Dimension`, `ModelName`).
- Ví dụ: `backend/internal/embedding/openai.go`, `backend/internal/embedding/gemini.go`, wrap bởi `swappable.go`.
- Pattern: Strategy + Decorator (`SwappableEmbedder` wrap inner provider, mutex bảo vệ swap).

**`llm.LLM`:**
- Mục đích: hợp đồng cho text generation, hỗ trợ usage recorder.
- Ví dụ: `backend/internal/llm/gemini.go`, `backend/internal/llm/openai.go`, `swappable.go` ép mode `gemini|openai|auto`.

**`vectorstore.VectorStore`:**
- Mục đích: trừu tượng vector DB (CreateCollection, Upsert, Query, CollectionDimension, Count).
- Ví dụ: `backend/internal/vectorstore/chromadb.go`.

**`chunker.Chunker`:**
- Mục đích: chiến lược cắt chunk; mặc định chạy `StrategicChunker` (composite) gồm Recursive, EntityProfile, NegativeRule, Hierarchical, ContextualEnricher.
- Ví dụ: `backend/internal/rag/chunker/strategic.go`.

**`storage.FileStorage`:**
- Mục đích: trừu tượng nơi lưu file gốc (local FS hoặc Google Drive).
- Ví dụ: `backend/internal/storage/local.go`, `backend/internal/storage/gdrive.go`.

**`Pipeline` / `Searcher` / `Answerer`:**
- Mục đích: orchestrator cho 3 luồng RAG cốt lõi (ingest, retrieve, generate).
- Vị trí: `backend/internal/rag/pipeline.go`, `searcher.go`, `answerer.go`.

## Entry Points

**Backend HTTP server:**
- Vị trí: `backend/cmd/server/main.go` (`func main`) → dựng config, DB, Redis, JWT, repos, embedder, ChromaDB, LLM, RAG pipeline, worker manager, search engine, services, handlers → `router.Setup` → `http.Server.ListenAndServe` trên `cfg.App.Port` (mặc định 8180 vì 8080 nằm trong dải excluded của Hyper-V trên Windows; xem `frontend/src/services/api.ts` dòng 1–3).
- Graceful shutdown: nghe `SIGINT/SIGTERM`, `Shutdown` HTTP với 10s, rồi dừng `WorkerManager`.

**Backend CLI utilities:**
- `backend/cmd/hashpw/` — sinh Argon2 hash cho seed user.
- `backend/cmd/testpdf/` — kiểm tra PDF extractor.
- `backend/cmd/testtoken/` — phát hành / verify JWT thủ công.

**Frontend:**
- Vị trí: `frontend/src/main.tsx` (mount React) → `frontend/src/App.tsx` (`BrowserRouter` + `AuthProvider`).
- Trigger: truy cập subdomain `wiki.medinet.vn`, `tamdao.medinet.vn`… (nginx route theo PRD, xem `documents/BACKEND_DEVELOPMENT_PLAN.md` mục 1.3).
- Trách nhiệm: route guarding (`ProtectedRoute`), gọi API qua `services/api.ts`, render layout + pages.

**Migration:**
- Chạy tự động lúc bootstrap qua `database.RunMigrations(cfg.DB.DSN())` (file `backend/internal/database/migrate.go`), nguồn `backend/internal/database/migrations/*.up.sql`.

**Worker (cùng process):**
- `WorkerManager.Start(ctx)` được gọi trong `main.go` ngay sau khi pipeline sẵn sàng. Không có process riêng — tất cả nằm trong cùng binary `server.exe`.

**Background services khác:**
- `service.UsageLogger` — flush usage event theo batch (16384 buffer, 128 flush size, 2s flush interval, threshold 32 chuyển sang `CopyFrom`).
- `service.UsageRollup.Start(ctx)` — rollup 5min / hourly / daily.
- `service.UsagePartitionMgr.Start(ctx)` — tạo partition tháng kế tiếp + drop > 365 ngày.

## Xử Lý Lỗi

**Chiến lược:** mọi tầng trả `error` Go thuần, log có cấu trúc bằng `slog` (JSON), handler chuyển thành response chuẩn hóa qua `internal/pkg/response`.

**Pattern:**
- HTTP error envelope: `{success: false, error: {code, message}}` (`pkg/response/response.go`).
- Pipeline RAG: `fmt.Errorf("stage: %w", err)` để giữ wrap chain; lỗi 429 từ provider được nhận diện qua `strings.Contains(errMsg, "429" / "RESOURCE_EXHAUSTED")` → backoff 30s (xem `pipeline.go` `retryWithBackoff`).
- Pre-flight dimension check trong `pipeline.go` Stage 3 → fail fast với thông điệp tiếng Việt hướng dẫn admin vào Settings → Vector hóa.
- Recovery middleware (`middleware/recovery.go`) bắt panic, log, trả 500 chuẩn hóa.
- Frontend: `services/api.ts` xử lý 401 với auto-refresh; lỗi khác trả về `APIResponse<T>` để page tự hiển thị.

## Cross-Cutting Concerns

**Logging:** `log/slog` với JSON handler ở stdout, level `Debug` khi `APP_ENV=development`, mặc định `Info`. Mọi service dùng `slog.Info/Warn/Error` kèm key-value.

**Validation:** `internal/pkg/validator` (wrap `go-playground/validator`) áp ở handler khi binding JSON; thêm `c.ShouldBindJSON` của Gin.

**Authentication:** JWT RS256 (`internal/pkg/jwt/jwt.go`), khóa nằm ở `backend/keys/` (private/public PEM, sinh bằng `scripts/generate_keys.sh`). Refresh token lưu hash trong Postgres, blacklist trong Redis.

**Authorization:** RBAC qua `middleware.RequireRole("admin")`, role thuộc bảng `users`/`user_roles`. Một số route admin còn cộng kiểm tra hub scope (xem `hub_handler.go`).

**Rate limiting:** `middleware.RateLimit(rdb, cfg.RateLimit.RPS, cfg.RateLimit.Burst)` toàn cục dùng Redis token bucket, riêng `/api/auth/login` áp `LoginRateLimit` chặt hơn.

**Security headers + CORS:** `middleware/security.go`, `middleware/cors.go` đọc `cfg.CORS.AllowedOrigins`.

**Settings encryption:** `repository.SettingsRepo` mã hóa giá trị secret bằng AES-GCM (`pkg/crypto/aes.go`) trước khi lưu Postgres; key đến từ `cfg.AES.Key`.

**Telemetry / usage:** ghi nhận token & API usage không chặn qua `service.UsageLogger`, đếm realtime/phút trên Redis qua `UsageRealtime`, rollup 5m/1h/1d, drop partition > 1 năm.

**Internationalization:** UI mặc định tiếng Việt; các thông điệp lỗi RAG quan trọng cũng tiếng Việt (xem `pipeline.go` "Go to Settings → Khi nạp tài liệu → Vector hóa").

---

*Phân tích kiến trúc: 2026-04-28*
