# Requirements: Medinet Wiki — Milestone v2.0 (Full RAG Rewrite)

**Defined:** 2026-05-13
**Milestone:** v2.0 — Full RAG Rewrite (CocoIndex + Python FastAPI + pgvector)
**Core Value:** Ingestion tri thức Medinet phải tái hiện trung thực cấu trúc tài liệu nguồn (heading, bảng, ảnh có chú thích, công thức — OCR tiếng Việt cho scanned PDF defer M2 vì D4) — biến mọi tài liệu y tế / dược / HCNS thành chunk semantic giàu metadata, để top-3 retrieval đạt ≥ 75% trên eval set thật.
**Granularity:** Large (10 phases) · **Mode:** YOLO · **Phase numbering:** Reset về 1 (--reset-phase-numbers)

> ⚠️ **REPLACE — M1 requirements (Docling) abandoned 2026-05-13.** Toàn bộ DSVC/EXTRACT/CHUNK/WIRE/CFG REQ-ID của M1 archive vào `.planning/milestones/v1.0-docling-rag/`. M2 = bộ REQ-ID mới hoàn toàn.

---

## v1 Requirements (M2 scope — 38 REQ-ID)

### CORE — Infra + Skeleton + Demolition (5 REQ)

- [ ] **CORE-01**: `Hub_All/api/` Python project skeleton (pyproject.toml + uv lockfile + Dockerfile multi-stage + ruff + mypy + pytest config). Lock-in version: `python>=3.11,<3.13`, `fastapi==0.136.1`, `cocoindex==1.0.3`, các dep khác theo `.planning/research/STACK.md`.
- [x] **CORE-02**: `docker-compose.yml` 3 services (`pgvector/pgvector:pg16` + `redis:7-alpine` + `python-api`); init script tạo 2 logical DB (`medinet_central` + `medinet_cocoindex`) + `CREATE EXTENSION vector` trên cả 2 + verify HNSW index 1536-dim build được trước khi viết flow (R1 mitigation). **Note:** Phần schema migrations (Alembic baseline) tách sang Phase 2. ✓ COMPLETE — Phase 1 Plan 02 docker-compose + Phase 2 Plan 01-05 schema baseline (10 bang + HNSW vector_cosine_ops + Vector(1536) verified runtime qua testcontainers 7/7 pytest PASS).
- [ ] **CORE-03**: Xóa code cũ — `Hub_All/docling-pipeline/`, `Hub_All/eval/`, `Hub_All/chroma_data/` (nếu còn). Cập nhật `Hub_All/.gitignore` cho `api/keys/`, `api/.venv/`, `medinet_pgdata/`. Giữ `Hub_All/backend/` đến Phase 8 (tear-down sau frontend smoke pass).
- [ ] **CORE-04**: FastAPI app factory `api/app/main.py` với `lifespan` event (init+abort `cocoindex.FlowLiveUpdater`), `pydantic-settings BaseSettings` đọc env, response envelope `{success, data, error, meta}` ở `api/app/pkg/response.py`. Healthcheck `GET /healthz` + `GET /readyz` (ready khi cocoindex flow updater started + DB pool connected).
- [ ] **CORE-05**: `.planning/CONVENTIONS.md` mới cho stack Python — test strategy (critical-path mandatory, coverage target 50%+ trên auth/ingest/search/ask), naming `snake_case` cho cocoindex flow/target (R5 mitigation), `APP_NAMESPACE=medinet_prod` cố định trong `.env.example`, middleware order (FastAPI reverse: error→security→CORS→rate-limit), logging fields match Go `log/slog` semantics.

### AUTH — JWT + Argon2 + RBAC + Response Envelope (6 REQ)

- [x] **AUTH-01**: `POST /api/auth/login` — body `{email, password}` → verify Argon2 hash (pwdlib) → return JWT RS256 access (15min) + refresh token (7d). Response envelope `{success, data: {access_token, refresh_token, user}, error, meta}`. Match contract Go cũ để frontend `services/api.ts` không cần đổi. ✓ (Plan 03-04, 2026-05-14 — `app/auth/router.py` POST /login + `app/auth/service.py` AuthService.login với anti-timing oracle dummy_password_hash, response envelope qua `resp.ok(LoginResponse.model_dump())`).
- [x] **AUTH-02**: `POST /api/auth/refresh` — body `{refresh_token}` → rotate refresh token (Redis SETNX atomic chống concurrent refresh race) → return access + refresh mới. Token cũ blacklist Redis TTL=access_token_ttl. ✓ (Plan 03-04, 2026-05-14 — `app/auth/service.py` AuthService.refresh với `redis.set(lock:refresh:<jti>, nx=True, ex=30)` P16 mitigation + blacklist old jti + UPDATE refresh_tokens.revoked_at + INSERT new token_hash SHA-256).
- [x] **AUTH-03**: `GET /api/auth/me` (Bearer) → return user info + roles + hub assignments. `POST /api/auth/logout` blacklist refresh token. ✓ (Plan 03-04, 2026-05-14 — `app/auth/router.py` GET /me + POST /logout, `get_current_user` Depends verify Bearer + Redis blacklist check, logout blacklist access JTI + optional refresh JTI với TTL từ exp claim).
- [x] **AUTH-04**: RBAC dependency `require_role("admin"|"editor"|"viewer")` qua FastAPI `Depends`. Endpoint admin-only refuse với 403 cho viewer/editor. Test integration: viewer KHÔNG thể `PUT /api/hubs/:id`. ✓ (Plan 03-05, 2026-05-14 — `app/auth/dependencies.py` require_role(*roles) factory với ValueError gate empty roles + allowed set check + HTTPException 403 FORBIDDEN; `app/main.py` thêm @app.exception_handler(HTTPException) map envelope shape `{success, data, error, meta}`; 5 unit test test_require_role.py + 6 integration test test_rbac_dependency.py PASS. AC3 reformulation note: production PUT /api/hubs/:id defer Phase 5 HUB-02 reuse cùng require_role dependency — Phase 3 verify contract qua test-only route /test/role-check mount qua fixture).
- [x] **AUTH-05**: **Argon2 cross-compat test (R6 mitigation)** — pin pwdlib params Go-compat `m=65536, t=3, p=4, saltLen=16, keyLen=32` (DOC-BUG fix: trước đó ghi `t=1, p=2` sai; Go source `backend/internal/pkg/hash/argon2.go` line 13-19 là source of truth — verified by production seed hash prefix `$argon2id$v=19$m=65536,t=3,p=4$`). Test: pwdlib `verify_password()` PASS hash do Go `alexedwards/argon2id` sinh ra (1 Go production hash từ seed.sql + 5 Python round-trip — full 5+5 bi-directional defer Phase 5/8). Fail-fast (CI error) nếu mismatch. ✓ (Plan 03-03, 2026-05-14 — `app/auth/password.py` + 4 critical integration test PASS).
- [x] **AUTH-06**: JWT keypair `Hub_All/api/keys/` (gitignored). Format compat verify: `openssl rsa -in private.pem -text -noout` xác định PKCS#1 vs PKCS#8. Convert PKCS#1→PKCS#8 nếu cần (`openssl pkcs8 -topk8 -nocrypt`). Token Go cũ (nếu có user đang đăng nhập) phải decode được bởi PyJWT. ✓ (Plan 03-02, 2026-05-14 — `scripts/verify_jwt_format.sh` + `app/auth/jwt.py` JWTManager PyJWT RS256, 8/8 unit test PASS, 5 attack vector reject verified, cross-process Go→Python defer rời Plan 03-05 integration test)

### HUB — Hub Registry CRUD + Isolation (3 REQ)

- [x] **HUB-01**: `GET/POST /api/hubs` + `GET/PUT /api/hubs/:id` + `PATCH /api/hubs/:id/status` — CRUD hub registry (D-07: PUT update KHÔNG PATCH; status endpoint riêng; D-06: KHÔNG test-connection). Schema Postgres: drop col `chroma_collection`/`db_*` (D-05). Pagination `page` + `per_page` (cap `min(per_page, 100)`). ✓ Plan 05-03 (router/service/schema).
- [x] **HUB-02**: Hub isolation enforce ở repository layer — mọi query có `WHERE hub_id = $1` từ user's hub assignment. Editor of Hub A KHÔNG thể `PATCH/DELETE` document của Hub B kể cả khi explicit `hub_id` trong payload. Test integration mandatory. ✓ (Plan 05-02 hub_isolation.py helper; Plan 05-06 enforce — documents_service.delete() gọi verify_hub_access (hub_id load từ DB row, KHÔNG payload) + enqueue_audit security.hub_isolation_violation tại điểm reject; DELETE /api/documents/:id editor-eligible; test_hub_isolation.py 6 critical test E4 PASS against real DB — editor cross-hub 403 + document tồn tại + audit logged. 2026-05-17)
- [x] **HUB-03**: `GET /api/hubs/:id/stats` — counts documents/chunks/users trong hub từ Postgres aggregate (KHÔNG từ ChromaDB). `query_count` defer Phase 6/7 (chưa có nguồn data — partial-coverage có chủ đích). ✓ Plan 05-03.

### USER — User Management + RBAC (3 REQ)

- [x] **USER-01**: `GET/POST /api/users` + `GET/PATCH/DELETE /api/users/:id` — admin-only CRUD user. Field: email, full_name, role, hub_assignments[]. (Plan 05-04 — D-07: update tách `PUT /:id` + `PATCH /:id/role` + `PATCH /:id/status`; router mount Wave 4.)
- [x] **USER-02**: `POST /api/users/:id/reset-password` — admin trigger reset, sinh token 1-time TTL 1h gửi qua email/log (defer email send v4.0, log only M2). (Plan 05-04 — token Redis ex=3600 + log console; KHÔNG trả qua API.)
- [x] **USER-03**: `GET /api/users/:id/profile` (self hoặc admin) + `PATCH /api/users/me/profile` (self only) — full_name, avatar (defer upload v4.0). (Plan 05-04 — D-07: dùng `/api/profile` self-scoped GET/PUT + POST /password; router KHÔNG :id param.)

### INGEST — CocoIndex Flow + Document Upload (8 REQ)

- [ ] **INGEST-01**: `api/app/rag/flow.py` — `@cocoindex.flow_def(name="medinet_wiki_ingest")` với source `cocoindex.sources.Postgres(table="documents", notification=PostgresNotification(channel="documents_notify"), ordinal_column="updated_at")`. Trigger: FastAPI `INSERT INTO documents` → Postgres `NOTIFY documents_notify` → cocoindex auto-pick up.
- [ ] **INGEST-02**: Flow transform chain: extract (whitelist `{.docx, .txt, .md, .pdf}`) → detect scanned PDF (heuristic: pypdf trả empty/garbage cho 80%+ pages) → set `status='failed_unsupported'` + return (R4 mitigation) → RecursiveSplitter custom regex tiếng Việt (heading patterns `Mục N.`, `Chương N.`, sentence end before VN caps) → LiteLLM `aembedding(model=cfg.embedding_model, input=chunk.text, dimensions=1536)` (R1 mitigation, PIN dim 1536 cho hot-swap).
- [ ] **INGEST-03**: Flow target `cocoindex.targets.Postgres(table="chunks")` với schema `chunks(id UUID PK, document_id UUID FK, hub_id UUID, content TEXT, content_hash BYTEA, heading_path TEXT, page_start INT, page_end INT, vector vector(1536), metadata JSONB, created_at TIMESTAMPTZ)`. HNSW cosine index trên `vector` + B-tree index `(hub_id, document_id)`. `chunk_id` stable qua re-index (D-2 differentiator preserve citation).
- [ ] **INGEST-04**: `POST /api/documents/upload` (multipart) — save file vào `file_store/` (local default, GDrive port optional defer Phase 4 quyết) → INSERT documents row `(hub_id, uploaded_by, filename, file_path, status='pending')` → return 202 + document_id. Cocoindex LISTEN/NOTIFY auto-pick up trong <1s.
- [ ] **INGEST-05**: `GET /api/documents/:id` — return document + `status` + `chunk_count` (từ `chunks` table aggregate). Frontend poll endpoint này hiển thị progress. `status` enum: `pending | processing | completed | failed | failed_unsupported` (R4 + Pitfall 8 mitigation).
- [ ] **INGEST-06**: Heartbeat columns `documents.last_heartbeat TIMESTAMPTZ`, `documents.attempts INT`. Watchdog cron (asyncio task mỗi 60s) flip `processing` rows có `last_heartbeat < NOW() - INTERVAL '2 minutes'` → `failed` với `error='timeout'`.
- [ ] **INGEST-07**: `DELETE /api/documents/:id` — delete row documents + cocoindex auto re-trigger qua LISTEN/NOTIFY → chunks tự xóa qua cocoindex tombstone hoặc explicit `DELETE FROM chunks WHERE document_id = $1`. Audit log action='document_delete'.
- [ ] **INGEST-08**: `GET /api/documents` list — pagination + filter `hub_id`, `status`, `uploaded_by`, search trong `filename`. Cap `per_page ≤ 100`.

### SEARCH — Vector Search Direct + Cross-Hub (4 REQ)

- [x] **SEARCH-01**: `GET /api/search?q=...&hub_id=X&top_k=10` — embed query qua LiteLLM (SAME provider + dimension như index) → raw SQL `SELECT id, content, metadata, 1 - (vector <=> $1) AS score FROM chunks WHERE hub_id = $2 ORDER BY vector <=> $1 LIMIT $3`. Bypass cocoindex hoàn toàn. ✓ Plan 06-01/06-02 (D-02: hiện thực bằng `POST /api/search` + body `query`/`hub_ids`/`top_k` khớp `api.ts` thay vì GET `?q=` — contract frontend là source of truth).
- [x] **SEARCH-02**: Per-query session config — `SET LOCAL hnsw.ef_search = 200` + connection-level `SET hnsw.iterative_scan = relaxed_order` + `SET hnsw.max_scan_tuples = 20000` (R2 mitigation). p95 target <800ms cho hub đơn. ✓ Plan 06-01 (`_run_vector_query` SET LOCAL trong transaction; EXPLAIN test dùng `ix_chunks_vector_hnsw`. Đo p95 trên dataset thật: 06-HUMAN-UAT.md).
- [x] **SEARCH-03**: `POST /api/search/cross-hub` body `{q, hub_ids: [...], top_k_per_hub}` — query nhiều hub song song (asyncio.gather), aggregate + re-rank theo score, return top results với `hub_id` mỗi result. User's `hub_assignments` enforce: result KHÔNG thuộc hub user không có access bị filter ở repo layer (defense in depth ngoài SQL filter). ✓ Plan 06-02 (`search_cross_hub` fan-out asyncio.gather + re-rank; `intersect_hubs` defense in depth — test_search_hub_isolation cross-hub PASS).
- [x] **SEARCH-04**: Redis cache search results — key `search:{hash(q+hub_ids+top_k)}`, TTL 5 phút. Invalidate cache khi document upload/edit/delete trong hub (Pub/Sub channel `hub:{hub_id}:invalidate`). ✓ Plan 06-01/06-03 (cache read/write sha256 TTL 300s + hub-tagged scheme + publish_invalidate trên document create/delete + subscriber lifespan task. Invalidation E2E test: 06-HUMAN-UAT.md).

### ASK — LLM Answerer + Citation + Hot-Swap (5 REQ)

- [x] **ASK-01**: `POST /api/ask` body `{q, hub_id, top_k?}` → SEARCH-01 lấy top-k chunks → build prompt với chunks đánh số `[1]`, `[2]`,... → `litellm.acompletion(model=cfg.llm_model, messages=[...])` **non-streaming** (streaming defer post-M2 vì citation parsing mid-stream phức tạp) → parse `[N]` markers trong response → return `{answer, citations: [{chunk_id, document_id, score, content_snippet}]}`: ✅ Plan 07-04 + 07-05 (2026-05-18 — citation map verified critical test)
- [x] **ASK-02**: System prompt anti-injection — instruct LLM "CHỈ trả lời từ context cung cấp, không suy diễn ngoài, format `[N]` cho citation". Test: user query yêu cầu bỏ qua system prompt KHÔNG bypass được: ✅ Plan 07-01 + 07-05 (2026-05-18 — anti-injection prompt được chèn verified; hành vi LLM thật defer Phase 9)
- [x] **ASK-03**: `POST /api/ask/cross-hub` body `{q, hub_ids: [...]}` — như ASK-01 nhưng dùng SEARCH-03 lấy chunks từ nhiều hub. Citation kèm `hub_id`: ✅ Plan 07-04 + 07-05 (2026-05-18 — cross-hub citation hub_id + hub isolation E4 verified)
- [x] **ASK-04**: `GET /api/rag-config` + `PUT /api/rag-config` — admin endpoint hot-swap embedding + LLM provider: ✅ Plan 07-03 (2026-05-18)
  - LLM swap: trivial config reload, không re-index
  - Embedding swap WITHIN dim 1536 (OpenAI ↔ Gemini): allowed, WARNING modal "vector hiện tại sinh bằng provider X, swap có thể giảm chất lượng — re-embed all? [yes/no]" (R7 mitigation)
  - Embedding swap CROSS-dim (1536 ↔ 3072): REFUSE 400 "dimension mismatch — defer cross-dim swap v4.0"
- [x] **ASK-05**: Token usage logging — mỗi LLM call ghi `(user_id, hub_id, model, prompt_tokens, completion_tokens, cost_usd, request_id, created_at)` vào `usage_events`. FastAPI `BackgroundTasks` async (defer Go-style batcher v4.0). `GET /api/usage` aggregate theo user/hub/model/date: ✅ Plan 07-02 + 07-04 + 07-05 (2026-05-18 — 10 ask → 10 row + aggregate verified critical test)

### AUDIT + APIKEY + AUX (3 REQ)

- [ ] **AUX-01**: Audit logger asyncio.Queue + batch flush 2s/128 → `audit_logs(user_id, action, target_type, target_id, hub_id, payload JSONB, request_id, created_at)`. Action enum: `auth.login`, `auth.refresh`, `document.upload`, `document.delete`, `rag-config.update`, `hub.create`, `hub.update`, `user.create`. `GET /api/audit-logs` admin-only.
- [x] **AUX-02**: API key management `GET/POST/DELETE /api/api-keys` — admin sinh API key cho external integration. Encrypt at rest (AES-GCM với `AES_KEY` env — schema M2 mới, không có data mã hóa cũ cần tương thích). Auth middleware accept header `X-API-Key:` ngoài JWT. ✓ (Plan 05-05 ApiKeyService CRUD + AES-GCM encrypt-at-rest + soft revoke + verify_key; Plan 05-06 router api_keys mounted main.py + auth/api_key.py require_api_key X-API-Key dependency; test_x_api_key_invalid_rejected critical PASS. 2026-05-17)
- [x] **AUX-03**: Rate limit middleware (slowapi) — 100 req/min/user trên search/ask, 30 req/min/user trên upload, KHÔNG limit trên auth/me. ✓ (Plan 05-02 slowapi Limiter + 429 envelope handler; Plan 05-05 @limiter.limit GET /api/audit-logs; Plan 05-06 app.state.limiter wired main.py + add_exception_handler(RateLimitExceeded); test_rate_limit.py 429 envelope shape + auth/me không limit PASS. /api/search + /api/ask decoration defer Phase 6/7 — endpoint chưa tồn tại. 2026-05-17)

### EVAL — Quality Gate ≥75% top-3 (4 REQ)

- [ ] **EVAL-01**: `Hub_All/eval/dataset/sources/` chứa 10 file VN medical (port từ M1 archive `.planning/milestones/v1.0-docling-rag/01-eval-dataset-baseline-native/` nếu có, hoặc dựng mới). `eval/queries.jsonl` 12 truy vấn vàng (port semantic từ M1) — mỗi dòng `{query, expected_doc_id, expected_section, hub_id, notes}`.
- [ ] **EVAL-02**: `eval/run_eval.py` pytest-based — login admin → seed eval_hub (DELETE chunks/documents trước) → upload 10 file → wait completion → run 12 queries qua `/api/search` (WITH `hub_id` filter để measure recall thật, R2 verify) → compute top-1/3/5 + MRR + latency p50/p95/p99 → emit `eval/results.json`.
- [ ] **EVAL-03**: `eval/EVAL.md` generator — Markdown report 7 section (Setup + Metrics table + Per-Query Diff + Latency + Conclusion PASS/FAIL + Recommendations + Defer ideas). Verdict logic: **PASS nếu top-3 ≥ 75% tuyệt đối** (KHÔNG có +15pp delta vì M1 abandoned). Exit code 0 PASS, 1 FAIL (CI-friendly).
- [ ] **EVAL-04**: `Makefile` root target `make eval-all`, `make eval-clean`, `make eval-smoke`. Smoke: upload 1 sample DOCX → search → assert ≥1 chunk return + chunk content match heading. `eval/README.md` workflow 3 bước + troubleshooting + tiền điều kiện.

### FRONTEND-COMPAT — Verify React 19 Vẫn Hoạt Động (1 REQ)

- [ ] **COMPAT-01**: Boot stack mới (FastAPI + pgvector + redis + frontend dev `npm run dev`), smoke từng trang React (Dashboard, HubRegistry, DocumentIngestion, UserManagement, AuditLog, APIKeyManagement, CrossHubSearch, Settings, GeminiAssistant, TokenUsage, Profile) — golden path mỗi trang PASS. **Ngoại lệ: trang `SyncQueue`** — feature sync queue đã loại khỏi M2 (Phase 5 CONTEXT D-01), `/api/sync/*` KHÔNG implement; trang này dự kiến lỗi API, KHÔNG tính vào golden-path PASS, dọn ở frontend rewrite v3.0. Replay test: so response envelope shape FastAPI mới vs router signature `git show m1-go-archived` + frontend types (Go runtime đã teardown). Vietnamese filename UTF-8 test ("Khám bệnh đa khoa.docx") upload + display preserve.

### TEARDOWN — Xóa Go Backend (1 REQ)

- [ ] **TEARDOWN-01**: Sau COMPAT-01 PASS, xóa `Hub_All/backend/` (toàn bộ Go), update `Hub_All/docker-compose.yml` + `Hub_All/Makefile` root remove Go references. Update CLAUDE.md (root + Hub_All) reflect stack Python. Backup tag git `git tag m1-go-archived` trước khi xóa.

### HARDENING — Observability + Production Ready (4 REQ)

- [ ] **HARD-01**: structlog JSON output với fields match Go `log/slog` (`level`, `msg`, `ts`, `request_id`, `user_id`, `hub_id`, `latency_ms`). `X-Request-Id` middleware sinh UUID4 nếu thiếu, propagate xuống cocoindex flow logs.
- [ ] **HARD-02**: Prometheus metrics placeholder — `/metrics` endpoint với counter (requests_total, errors_total) + histogram (request_duration_seconds, search_latency_seconds, ingest_duration_seconds). Defer Grafana dashboard v4.0.
- [ ] **HARD-03**: Integration test suite ≥50% critical path coverage (auth, hub, user, ingest, search, ask). pytest + testcontainers Postgres + Redis. CI gate: tests PASS trên GitHub Actions.
- [ ] **HARD-04**: `README.md` + `DEPLOY.md` cập nhật cho stack Python. Backup script documented: `pg_dump --schema=public --schema=cocoindex medinet_central > backup.sql` + `pg_dump medinet_cocoindex > backup_cocoindex.sql`. `.env.example` đủ mọi key (DATABASE_URL, COCOINDEX_DATABASE_URL, REDIS_URL, OPENAI_API_KEY, GEMINI_API_KEY, JWT_PRIVATE_KEY_PATH, AES_KEY, APP_NAMESPACE...).

---

## v2 Requirements (defer sang v3.0 / v4.0)

### v3.0 — Multi-subdomain SPA (defer từ trước, PRD v1.3)

- **SPA-01**: Tách frontend thành 4 SPA build độc lập (Hub Tổng + 3 Hub Dự Án)
- **SPA-02**: Mỗi SPA có entry, route, login form, branding, theme riêng (không share session)
- **SPA-03**: Backend phát hành JWT mang `hub_id` từ subdomain context — middleware verify khớp
- **SPA-04**: CORS + cookie domain cấu hình đúng từng subdomain
- **SPA-05**: Hub Dự Án SPA chỉ expose route Hub-scoped — ẩn admin, ẩn cross-hub search
- **SPA-06**: Nginx config routing wildcard `*.medinet.vn` → đúng SPA bundle, kèm SSL wildcard cert
- **SPA-07**: Smoke test e2e: đăng nhập tamdao không có session ở dmd / wiki

### v4.0 — MCP Server + Production Hardening

- **MCP-01**: MCP Server expose RAG/Wiki cho Claude/ChatGPT agent
- **MCP-02**: Tool exposure: search, ask, list_documents, get_document — scoped theo hub_id
- **HARD-V4-01**: OCR Vietnamese (revisit cocoindex custom function wrap pytesseract nếu user feedback regress)
- **HARD-V4-02**: Cross-dim embedding swap (dim 3072 cho text-embedding-3-large full quality)
- **HARD-V4-03**: Streaming `/api/ask` qua SSE với citation injection mid-stream (buffer parse `[N]`)
- **HARD-V4-04**: Token usage Go-style batcher (CopyFrom-equivalent qua asyncpg COPY)
- **HARD-V4-05**: Email send cho password reset (defer M2)
- **HARD-V4-06**: Avatar upload + S3/GCS file storage
- **HARD-V4-07**: GDrive file storage backend port
- **HARD-V4-08**: Cocoindex augmenter (Q&A pair generation) — thiết kế mới (Go source đã archive ở tag `m1-go-archived`)
- **HARD-V4-09**: Postgres pg16 → pg17 upgrade
- **HARD-V4-10**: Comprehensive test coverage >80% (M2 chỉ 50%+ critical path)
- **HARD-V4-11**: Khắc phục CONCERNS bảo mật cũ (`.gitignore` root, GCP key audit, AES_KEY rotation, XSS token storage migration httpOnly cookie)

### v4.1+ — Advanced RAG

- **RAG-V4-01**: Hybrid retrieval BM25 + dense vector (Phase 2 PRD original)
- **RAG-V4-02**: Reranker (Cohere rerank-3 hoặc local cross-encoder)
- **RAG-V4-03**: Version history & concurrent editing (Phase 3 PRD original)
- **RAG-V4-04**: Local embedding model (sentence-transformers, BGE-M3 cho on-prem)

---

## Out of Scope (M2)

Loại trừ tường minh — ghi vào đây để chống scope creep + tham chiếu khi reject phụ thuộc tương lai.

| Feature | Reason |
|---|---|
| **OCR Vietnamese cho scanned PDF** | D4 gỡ Docling. M2 ship với enum `failed_unsupported` cho scanned PDF. Revisit v4.0 nếu user feedback regress. |
| **Table preservation phức tạp (merged cells, rowspan/colspan)** | Không có Python lib battle-tested cho VN medical PDF. Camelot/pdfplumber test Phase 4, ship M2 với accept-loss warning UI. Defer v4.0. |
| **Frontend rewrite / Multi-subdomain SPA** | D6 — defer v3.0. M2 giữ React 19 đơn-SPA không sửa. |
| **MCP Server** | Defer v4.0. |
| **Data migration từ ChromaDB cũ** | M1 chưa production, không có user upload thật. Clean slate pgvector. |
| **Test coverage tổng quát (>80%)** | Hardening v4.0. M2 chỉ critical path 50%+ (auth/ingest/search/ask/hub isolation). |
| **Hybrid retrieval BM25 + dense** | Phase 2 PRD original — defer v4.1. |
| **Reranker (Cohere / cross-encoder)** | Defer v4.1. |
| **Version history & concurrent editing** | Phase 3 PRD original — defer v4.1. |
| **Local embedding model (sentence-transformers/BGE-M3)** | Giữ OpenAI/Gemini hot-swap. Defer v4.1 cho on-prem use case. |
| **Streaming `/api/ask` qua SSE** | Citation parsing mid-stream phức tạp (buffer `[N]` cross chunks). Non-streaming match M1 contract. Defer v4.0. |
| **Cocoindex augmenter (Q&A pair gen)** | Go có, cocoindex equivalent unclear. Default skip M2, RTFM Phase 4 chỉ nếu dễ thêm. Defer v4.0. |
| **Cross-dim embedding swap (1536 ↔ 3072)** | Triggers full re-embed (~$6.50/100K chunks). M2 PIN 1536 cả 2 provider. Defer v4.0. |
| **Cocoindex worker tách container** | M2 in-process đủ cho 100 docs/day. Defer >1k docs/day (v4.0). |
| **Avatar upload + S3/GCS** | Defer v4.0. |
| **Email send (password reset, notification)** | M2 log only. Defer v4.0. |
| **Khắc phục CONCERNS bảo mật cũ** | Hardening v4.0 (`.gitignore` root, GCP key audit, AES_KEY rotation, XSS token storage). |
| **WebSocket job progress** | Frontend poll `/api/documents/:id` đủ M2. Defer v4.0. |
| **GraphQL** | REST/JSON đủ. Không thêm tầng abstract. |
| **LangChain / LlamaIndex** | CocoIndex + LiteLLM trực tiếp đủ. Tránh abstraction lock-in. |

---

## Traceability

Mapping REQ-ID → Phase (final, confirmed bởi gsd-roadmapper 2026-05-13). 38/38 REQ mapped, 0 orphan.

| Requirement | Phase | Status |
|---|---|---|
| CORE-01 | Phase 1 (Infra Skeleton + Demolition + EXIT Criteria) | Pending |
| CORE-02 | Phase 1 (docker-compose 3-service + HNSW 1536-dim verify) + Phase 2 (schema migrations Alembic baseline) | ✓ Complete (2026-05-13) |
| CORE-03 | Phase 1 (xóa code M1 cũ) | Pending |
| CORE-04 | Phase 1 (FastAPI app factory + lifespan + envelope + healthz) | Pending |
| CORE-05 | Phase 1 (CONVENTIONS.md) | Pending |
| AUTH-01 | Phase 3 Plan 03-04 (login) | ✓ Done 2026-05-14 (POST /api/auth/login + AuthService.login với anti-timing dummy_password_hash) |
| AUTH-02 | Phase 3 Plan 03-04 (refresh) | ✓ Done 2026-05-14 (POST /api/auth/refresh + Redis SETNX P16 lock + blacklist old jti) |
| AUTH-03 | Phase 3 Plan 03-04 (me + logout) | ✓ Done 2026-05-14 (GET /api/auth/me + POST /api/auth/logout + get_current_user Bearer auth) |
| AUTH-04 | Phase 3 Plan 03-05 (RBAC dependency + integration test) | ✓ Done 2026-05-14 (require_role(*roles) factory + HTTPException envelope handler + 5 unit + 6 integration test PASS, 5/5 ROADMAP AC verified end-to-end) |
| AUTH-05 | Phase 3 Plan 03-03 (Argon2 cross-compat test) | ✓ Done 2026-05-14 (10/10 unit+critical PASS, R6 cross-compat verified: pwdlib verify Go seed hash) |
| AUTH-06 | Phase 3 Plan 03-02 (JWT keypair format + PyJWT RS256 wrapper) | ✓ Done 2026-05-14 (8/8 unit test PASS, T-03-jwt-alg-confusion mitigated) |
| INGEST-01 | Phase 4 (cocoindex flow Postgres source LISTEN/NOTIFY) | Pending |
| INGEST-02 | Phase 4 (extract + scanned detect + chunk VN + embed dim 1536) | Pending |
| INGEST-03 | Phase 4 (cocoindex target chunks + HNSW + stable chunk_id) | Pending |
| INGEST-04 | Phase 4 (POST /api/documents/upload) | Pending |
| INGEST-05 | Phase 4 (GET /api/documents/:id + status enum) | Pending |
| INGEST-06 | Phase 4 (heartbeat + watchdog) | Pending |
| INGEST-07 | Phase 4 (DELETE /api/documents/:id) | Pending |
| INGEST-08 | Phase 4 (GET /api/documents list + filter) | Pending |
| HUB-01 | Phase 5 (hubs CRUD) | Done (05-01: migration 0003 schema; 05-03: router/service/schema 6 endpoint) |
| HUB-02 | Phase 5 (hub isolation repo layer) | Done (05-02 helper; 05-06 enforce documents_service.delete + audit emit; test_hub_isolation.py 6 critical test E4 PASS) |
| HUB-03 | Phase 5 (hubs/:id/stats) | Done (05-03: stats Postgres aggregate 3 count; query_count defer Phase 6/7) |
| USER-01 | Phase 5 (users CRUD) | Done (Plan 05-04) |
| USER-02 | Phase 5 (reset password) | Done (Plan 05-04) |
| USER-03 | Phase 5 (profile) | Done (Plan 05-04) |
| AUX-01 | Phase 5 (audit logger + GET audit-logs) | In Progress (05-01: audit_service asyncio.Queue + lifespan wire + SC4 test; 05-05: AuditQueryService + GET /api/audit-logs router; router mount + integration test Plan 05-06) |
| AUX-02 | Phase 5 (API key management) | Done (05-05 ApiKeyService CRUD + AES-GCM + verify_key; 05-06 router mounted + auth/api_key.py require_api_key X-API-Key; test_x_api_key_invalid_rejected critical PASS) |
| AUX-03 | Phase 5 (rate limit middleware slowapi) | Done (05-02 Limiter + 429 handler; 05-05 @limiter.limit audit-logs; 05-06 app.state.limiter wired main.py + test_rate_limit.py 429 envelope PASS) |
| SEARCH-01 | Phase 6 (POST /api/search single-hub — D-02) | Done (06-01/06-02) |
| SEARCH-02 | Phase 6 (per-query session config HNSW) | Done (06-01; p95 đo dataset thật → 06-HUMAN-UAT) |
| SEARCH-03 | Phase 6 (POST /api/search/cross-hub) | Done (06-02) |
| SEARCH-04 | Phase 6 (Redis cache + invalidate) | Done (06-01/06-03; invalidation E2E test → 06-HUMAN-UAT) |
| ASK-01 | Phase 7 (POST /api/ask + citation) | ✅ Done (Plan 07-04 AskService + endpoint; 07-05 citation map `[N]`→chunk_id critical test verified) |
| ASK-02 | Phase 7 (anti-injection system prompt) | ✅ Done (Plan 07-01 ANTI_INJECTION_SYSTEM_PROMPT; 07-05 prompt được chèn verified — hành vi LLM thật defer Phase 9) |
| ASK-03 | Phase 7 (POST /api/ask/cross-hub) | ✅ Done (Plan 07-04 ask_cross_hub + endpoint; 07-05 cross-hub citation hub_id + hub isolation E4 verified) |
| ASK-04 | Phase 7 (GET/PUT /api/rag-config hot-swap) | ✅ Done (Plan 07-03 dimension guard; 07-05 hot-swap LLM + cross-dim 400 verified) |
| ASK-05 | Phase 7 (token usage logging) | ✅ Done (Plan 07-02 write/read path + 07-04 BackgroundTasks; 07-05 10 ask → 10 row + aggregate verified) |
| COMPAT-01 | Phase 8 (frontend smoke 12 pages + replay test + VN filename) | 🔄 In progress — Plan 08-01 done (contract diff + replay test tĩnh, SC3 thoả) + 08-02 done (fix api-side: BLOCKER /api/ai/chat + port 8180); còn 08-03 test suite + 08-04 smoke 11 trang |
| TEARDOWN-01 | Phase 8 (xóa Hub_All/backend/ + git tag m1-go-archived) | Pending |
| EVAL-01 | Phase 9 (dataset 10 file VN + queries.jsonl) | Pending |
| EVAL-02 | Phase 9 (run_eval.py pytest) | Pending |
| EVAL-03 | Phase 9 (EVAL.md generator + verdict gate ≥75%) | Pending |
| EVAL-04 | Phase 9 (Makefile + eval-smoke + README) | Pending |
| HARD-01 | Phase 10 (structlog JSON + X-Request-Id) | Pending |
| HARD-02 | Phase 10 (Prometheus /metrics) | Pending |
| HARD-03 | Phase 10 (integration test ≥50% critical path + CI) | Pending |
| HARD-04 | Phase 10 (README + DEPLOY + backup script + .env.example) | Pending |

**Coverage:**
- v1 requirements: **38 total** (CORE 5, AUTH 6, HUB 3, USER 3, INGEST 8, SEARCH 4, ASK 5, AUX 3, EVAL 4, COMPAT 1, TEARDOWN 1, HARD 4)
- Phase mapping: **38/38 mapped** ✓ (0 orphan)
- Phase distribution: Phase 1 (5 REQ) + Phase 2 (CORE-02 split) + Phase 3 (6 REQ) + Phase 4 (8 REQ) + Phase 5 (9 REQ HUB+USER+AUX) + Phase 6 (4 REQ) + Phase 7 (5 REQ) + Phase 8 (2 REQ COMPAT+TEARDOWN) + Phase 9 (4 REQ) + Phase 10 (4 REQ)

---

## Open Questions (cần resolve trước hoặc trong phase tương ứng)

1. **Storage backend** (Phase 4) — local default, GDrive port optional. Confirm với user trước Phase 4 start.
2. **JWT keypair format** (Phase 3) — verify PKCS#1 vs PKCS#8, convert nếu cần.
3. **PDF table extraction lib** (Phase 4) — pdfplumber vs camelot vs accept loss. Empirical test 3 VN medical PDF.
4. **Cocoindex augmenter** (Phase 4) — RTFM, default skip M2.
5. **Embedding dim 1536 vs 3072 quality** (Phase 9) — empirical eval gate ≥75%.

---

*Requirements defined: 2026-05-13 (REPLACE M1 — Docling abandoned)*
*Last updated: 2026-05-13 (Traceability final confirmed bởi gsd-roadmapper — 38/38 REQ mapped vào 10 phase)*
