# Requirements: Medinet Wiki — Milestone v3.0 (Multi-Hub Split)

**Defined:** 2026-05-21
**Milestone:** v3.0 — Multi-Hub Split (subpath routing + multi-DB physical isolation)
**Core Value:** Ingestion tri thức Medinet phải tái hiện trung thực cấu trúc tài liệu nguồn — biến mọi tài liệu y tế / dược / HCNS thành chunk semantic giàu metadata. v3.0 mở rộng theo trục tách hub vật lý (process + DB riêng cùng instance) + cross-hub aggregation tại central, top-3 retrieval vẫn ≥75% trên eval set thật.
**Granularity:** Large (7 phases) · **Mode:** YOLO · **Phase numbering:** Reset về 1 (D-V3-05)

> ⚠️ **REPLACE — M2 requirements (v2.0 Full RAG Rewrite) shipped 2026-05-21.** Toàn bộ 38 REQ-ID của M2 archive vào `.planning/milestones/v2.0-full-rag-rewrite/REQUIREMENTS.md`. v3.0 = bộ REQ-ID mới hoàn toàn (7 category: TOPO/FACTOR/SSO/SYNC/PROXY/SETTINGS/MIGRATE).

---

## v1 Requirements (v3.0 scope — 29 REQ-ID)

### TOPO — Multi-DB Topology + Per-hub Alembic (4 REQ)

- [x] **TOPO-01** ✅ Phase 1: Postgres init script idempotent tạo N+1 logical DB cùng instance — `medinet_central` (đã có từ M2) + `medinet_hub_yte` + `medinet_hub_duoc` + `medinet_hub_hcns`. Mỗi DB có `CREATE EXTENSION vector` + HNSW index 1536-dim verify build được. Khả năng thêm hub động (`medinet_hub_<new>`) qua make target `make hub-init HUB=<name>` mà KHÔNG cần down instance.
- [x] **TOPO-02** ✅ Phase 1: Per-hub Alembic migration set — mỗi DB hub con có `alembic_version` table riêng, head revision khớp giữa các DB. Make target `make migrate-all` apply migrations tuần tự N database + verify version match. CI lint check `alembic current` returns cùng head SHA cho tất cả DB sau migration (R-V3-3 mitigation).
- [x] **TOPO-03** ✅ Phase 1: Cocoindex flow naming per-hub — `medinet_<hub>_ingest` (`medinet_yte_ingest`, `medinet_duoc_ingest`, ...). APP_NAMESPACE per-hub `medinet_<hub>_prod` đảm bảo cocoindex internal tables không đụng nhau giữa các DB. `db_schema_name="cocoindex"` giữ nguyên (R5 carry forward).
- [x] **TOPO-04** ✅ Phase 1: Per-hub Postgres connection pool + isolation env — `HUB_NAME=yte` → kết nối `medinet_hub_yte` (KHÔNG fallback central). Helper `get_engine(hub_name)` resolve URL từ env + connection pool size config-driven. Test integration: `HUB_NAME=yte` deploy KHÔNG truy cập được `medinet_hub_duoc` qua DB connection (R-V3-3 + E-V3-3 enforce).

### FACTOR — Hub-con Codebase Factor (3 REQ)

- [ ] **FACTOR-01**: 1 codebase deploy được nhiều lần với env `HUB_NAME=<name>` (`central` vs `yte` vs `duoc` vs `hcns`). App factory `create_app(hub_name)` đọc env, mount router phù hợp, khởi tạo cocoindex flow đúng tên (TOPO-03). Docker compose mở rộng từ 3 service (M2) sang 1 Postgres + 1 Redis + N+1 process FastAPI.
- [ ] **FACTOR-02**: Strip system settings router khi `HUB_NAME != "central"` — hub con KHÔNG mount `/api/rag-config` (GET/PUT), `/api/api-keys` (GET/POST/DELETE), `/api/hubs` (POST/PUT/PATCH), `/api/users` (admin CRUD), `/api/audit-logs` (GET). Test integration: `GET /api/rag-config` ở hub con trả 404 (KHÔNG 403 — endpoint không exist). Central giữ nguyên 100% endpoint M2.
- [ ] **FACTOR-03**: Hub con expose endpoint hạn chế (10 endpoint hub-scoped) — `POST/GET /api/auth/*`, `GET/PATCH /api/profile`, `POST/GET/DELETE /api/documents/*`, `POST /api/search`, `POST /api/ask`, `GET /api/usage`. KHÔNG expose cross-hub search (đó là endpoint central). Smoke test mỗi endpoint trả 200 hoặc lỗi đúng shape envelope.

### SSO — Auth SSO + hub_ids trong JWT (4 REQ — GA-V3-A chốt ở `/gsd-discuss-phase 3`)

- [ ] **SSO-01**: Central expose JWKS endpoint `GET /.well-known/jwks.json` public key RS256 (PKCS#8). Hub con cache JWKS local TTL 1h ở startup + refresh background (R-V3-5 mitigation HA). Hub con verify JWT bằng JWKS đã cache thay vì shared keypair file. Test integration: rotate central keypair → hub con detect mới trong TTL window.
- [ ] **SSO-02**: Refresh token blacklist Redis chung — central + hub con cùng kết nối 1 Redis instance, blacklist key `auth:blacklist:<jti>` valid cross-process. Hub con KHÔNG sinh refresh token (login + refresh chỉ ở central qua `POST /api/auth/login` central URL). User login 1 lần ở central → JWT valid trên tất cả hub con qua subpath redirect.
- [ ] **SSO-03**: JWT claim `hub_ids: list[str]` reflect user's hub assignments — central verify access cross-hub search dùng `hub_ids` (intersection với requested `hub_ids` body). Hub con verify access local hub bằng so sánh `current_user.hub_ids` chứa `HUB_NAME` của process. JWT issuer URL cố định central (KHÔNG đổi per-hub).
- [ ] **SSO-04**: E4 reinforced — hub con KHÔNG truy cập được data hub khác kể cả khi JWT compromised (DB-level isolation từ TOPO-04 + repository layer vẫn enforce `WHERE hub_id = settings.hub_name`). Test integration: stale JWT chứa `hub_ids=["duoc"]` post tới `medinet_hub_yte` API → 403 (không phải 404 hay data leak).

### SYNC — Cross-hub Data Sync (5 REQ — GA-V3-D mechanism chốt ở `/gsd-discuss-phase 4`)

- [ ] **SYNC-01**: Sau khi cocoindex flow hub con ingest xong → push chunks + vector (denormalized) lên `medinet_central.chunks` với cùng `chunk_id` + `document_id` + `hub_id` + `content` + `content_hash` + `vector` (1536-dim). Hub tổng KHÔNG re-embed (D-V3-02). Push trigger: cocoindex post-process hook hoặc outbox worker (chốt ở discuss-phase 4).
- [ ] **SYNC-02**: Push idempotent on retry — `INSERT ... ON CONFLICT (chunk_id) DO UPDATE SET content_hash, vector, ... WHERE central.content_hash != hub.content_hash`. Multi-retry KHÔNG dup. Test integration: kill push mid-batch → re-run KHÔNG sai chunk_count tổng.
- [ ] **SYNC-03**: Cross-hub search ở central dùng aggregated `medinet_central.chunks` — query SQL `WHERE hub_id = ANY($1::uuid[])` với `hub_ids` từ JWT claim + intersect với `body.hub_ids`. KHÔNG fan-out HTTP tới hub con (latency × N). Re-rank theo score (carry forward Phase 6 v2.0 cross-hub logic).
- [ ] **SYNC-04**: Checksum verify periodic chống drift (R-V3-1 mitigation) — daily cron Prometheus metric `sync_drift_total{hub_id, drift_type}` đếm row count + sample content_hash diff giữa `medinet_hub_<name>.chunks` và `medinet_central.chunks WHERE hub_id = <hub>`. Alert nếu drift > 1% (E-V3-5 trigger nếu sustained 7 ngày).
- [ ] **SYNC-05**: Sync mechanism chốt ở `/gsd-discuss-phase 4` — 3 option đánh giá: (a) cocoindex target thứ 2 (Postgres target trỏ central — chỉ activate sau ingest local), (b) Postgres logical replication (publication `chunks_hub_yte_pub` ở hub con + subscription `chunks_hub_yte_sub` ở central), (c) outbox + worker (transactional INSERT outbox table local + worker async push central với ack). Trade-off: (a) lock-in cocoindex / (b) Postgres native nhưng schema drift sensitive / (c) flexible nhưng phải tự maintain worker.

### PROXY — Reverse Proxy + Frontend Subpath (4 REQ — GA-V3-C chốt ở `/gsd-discuss-phase 5`, D-V3-06 D6 expire)

- [ ] **PROXY-01**: Caddy route `wiki.domain.com/<hub>/api/*` → upstream container hub đúng (`http://hub-<hub>:8180/api/*`) với strip prefix `/<hub>`. Central route `wiki.domain.com/api/*` → `http://central:8180/api/*` (KHÔNG strip). Caddy auto-TLS tiếp tục từ v2.0 Phase 8.3. Test smoke: `curl https://wiki.domain.com/yte/api/health` PASS + `curl https://wiki.domain.com/api/health` PASS (central).
- [ ] **PROXY-02**: Frontend detect prefix từ URL (1 build dùng chung — option a GA-V3-C khuyến nghị seed) — `frontend/src/services/api.ts` đổi base URL: `const PREFIX = window.location.pathname.split('/')[1]; const API_BASE = PREFIX && KNOWN_HUBS.includes(PREFIX) ? '/' + PREFIX + '/api' : '/api';`. Per-hub build (`VITE_HUB_NAME=yte`) bỏ — đỡ build matrix. Re-confirm option ở discuss-phase 5.
- [ ] **PROXY-03**: D6 expire formally — `Hub_All/CLAUDE.md` section 3 cập nhật ghi D6 hết hiệu lực ở v3.0-05. Frontend rewrite được phép cho prefix detect (PROXY-02) + per-hub login branding (PROXY-04). Smoke regression 11 trang React M2 COMPAT-01 carry forward (R-V3-2 mitigation).
- [ ] **PROXY-04**: Per-hub login branding — hub con render logo + tiêu đề khác nhau (Hub y_te = phòng y tế Medinet, Hub dược = phòng dược, ...). Tách `frontend/src/branding/<hub>/` config (logo URL + title VN + theme color) thay vì sửa core component. Central giữ branding gốc Medinet Wiki. Login form ở hub con redirect về central `/api/auth/login` (SSO-02).

### SETTINGS — System Settings Sync (4 REQ — GA-V3-B chốt ở `/gsd-discuss-phase 6`)

- [ ] **SETTINGS-01**: Hub con đọc `rag_config` (LLM/embedding provider + model + dim) từ central qua HTTP pull on-demand `GET https://central/api/rag-config` (cache Redis local TTL 60s). Cache key `settings:rag_config:<hub>`. Fallback: nếu central down, dùng cached value cho tới TTL expire — sau đó fail-loud nếu vẫn không reach (KHÔNG silent degrade).
- [ ] **SETTINGS-02**: Push invalidate qua Redis pub/sub channel `settings:invalidate` — khi central `PUT /api/rag-config` → publish `{config_key: "rag_config", timestamp}` → hub con subscriber flush local cache trong < 30s (E-V3-4). Test integration: đổi `rag_config` ở central → hub con phải re-fetch trong window.
- [ ] **SETTINGS-03**: API key verification proxy — khi hub con nhận `X-API-Key:` header → gọi central `POST /api/api-keys/verify` (cache Redis TTL 60s key `apikey:<hash>`) thay vì lưu plaintext key cục bộ. Trả 401 nếu central reject. Central giữ AES-GCM encrypt-at-rest từ M2 AUX-02.
- [ ] **SETTINGS-04**: `hub_registry` read-only ở hub con — hub con load `hub_registry` (list hub_id + subpath + active) từ central qua HTTP pull TTL 5 phút (rare-change). Hub con KHÔNG ghi (PUT/POST trả 404 do FACTOR-02 strip). Central giữ nguyên CRUD M2 HUB-01.

### MIGRATE — Migration + Smoke E2E (5 REQ — GA-V3-D strategy chốt ở `/gsd-discuss-phase 7`)

- [ ] **MIGRATE-01**: Snapshot data `medinet_central.{chunks, documents, users, audit_logs, usage_events}` per `hub_id` qua `pg_dump --data-only --table=... --where="hub_id = '<uuid>'"` (option a GA-V3-D khuyến nghị seed; option b "snapshot + replay cocoindex flow rebuild từ file_store" backup). File output `migrate-<hub>-<date>.sql` lưu vào `migrate-snapshots/`.
- [ ] **MIGRATE-02**: Restore snapshot vào `medinet_hub_<name>` qua `psql -d medinet_hub_<name> -f migrate-<hub>.sql` (blue/green per-hub — R-V3-4 mitigation). Test trên DB NEW trước khi switch traffic. Sau verify smoke PASS → switch Caddy upstream `hub-<hub>:8180` từ central proxy sang hub con dedicated.
- [ ] **MIGRATE-03**: Truncate `hub_id` rows khỏi central post-migration — giữ skeleton aggregate. Central `medinet_central.{documents, users, audit_logs, usage_events}` chỉ giữ rows `hub_id IS NULL` (system-level — admin, audit, settings change). `medinet_central.chunks` KHÔNG truncate (D-V3-02 — vẫn nhận sync từ hub con cho cross-hub search).
- [ ] **MIGRATE-04**: MCP service re-point gọi central cho cross-hub aggregate (`mcp_service/config.py` đổi `API_BASE_URL` sang `https://central/api`). MCP tools `search_wiki(hub_id?)` + `ask_wiki(hub_id?)` vẫn hoạt động với `hub_id` parameter optional (cross-hub khi omit). OAuth flow Phase 8.3 carry forward — KHÔNG fan-out N hub con. Smoke MCP qua Claude Inspector PASS sau re-point.
- [ ] **MIGRATE-05**: Smoke E2E sau migration — Docker compose mở rộng up đầy đủ (1 Postgres + 1 Redis + 4 FastAPI process: central + 3 hub con + Caddy + frontend). Golden path mỗi hub: `wiki.domain.com/yte` → login (qua central SSO) → upload DOCX → poll status `completed` → search local hub → search cross-hub (qua central) → ask → citation `[N]` → logout. 3 hub con + central PASS hết. Cross-hub search latency p95 < 1.5s (E-V3-2). Hub con KHÔNG access được data hub khác (E-V3-3).

---

## v2 Requirements (defer sang v4.0 / v4.1)

### v4.0 — Production Hardening + Advanced RAG

- **HARD-V4-01**: OCR Vietnamese revisit (Docling/Tesseract optional sidecar) nếu user feedback regress scanned PDF.
- **HARD-V4-02**: Cross-dim embedding swap (1536 ↔ 3072) cho `text-embedding-3-large` full quality.
- **HARD-V4-03**: Streaming `/api/ask` qua SSE với citation injection mid-stream.
- **HARD-V4-04**: Comprehensive coverage >80% (v2.0 dừng ở 57.75% critical-path).
- **HARD-V4-05**: Khắc phục CONCERNS bảo mật cũ — `.gitignore` root + GCP key audit + AES_KEY rotation + XSS token storage migration httpOnly cookie.
- **HARD-V4-06**: Branch protection rule GitHub repo enforce 2 workflow trước merge main.
- **HARD-V4-07**: Postgres pg17 upgrade.
- **HARD-V4-08**: Email send (M2 user reset password chỉ log console).
- **HARD-V4-09**: Avatar upload S3/GCS.
- **HARD-V4-10**: GDrive file storage backend (M2 chỉ local `file_store/`).
- **HARD-V4-11**: cocoindex augmenter Q&A pair gen.

### v4.1 — Advanced Retrieval

- **RAG-V41-01**: Hybrid retrieval BM25 + reranker (Cohere / cross-encoder).
- **RAG-V41-02**: Local embedding model (sentence-transformers / BGE-M3 cho on-prem) — SEED-001.
- **RAG-V41-03**: Version history & concurrent editing.

---

## Out of Scope (v3.0)

- **OCR Vietnamese revisit** — defer v4.0. v3.0 vẫn dùng whitelist `{.docx, .txt, .md, .pdf text-only}` + `failed_unsupported` (R4 carry forward).
- **Cross-dim embedding swap** — defer v4.0. v3.0 vẫn PIN dim 1536 (R1 + R7 carry forward).
- **Streaming `/api/ask`** — defer v4.0.
- **Coverage >80%** — defer v4.0. v3.0 giữ gate ≥50% critical-path (HARD-03 carry forward).
- **Hybrid BM25 + reranker** — defer v4.1.
- **Local embedding model** — defer v4.1 (SEED-001 dormant).
- **Schema riêng per hub trong cùng DB** — bỏ phương án này (đụng R5/P7 — cocoindex `db_schema_name` cố định). LOCKED D-V3-01.
- **Instance Postgres riêng per hub** — bỏ phương án này (ops × N). LOCKED D-V3-01.
- **Federated HTTP fan-out cho cross-hub search** — bỏ phương án này (latency × N hub). LOCKED D-V3-02 (chunks+vector denormalized).
- **Hub tổng re-embed chunks từ hub con** — KHÔNG re-embed; lưu sẵn vector 1536-dim từ hub con. LOCKED D-V3-02.
- **Per-hub `VITE_HUB_NAME` build matrix** — bỏ option b GA-V3-C; chọn 1 build detect prefix (PROXY-02). Re-confirm ở discuss-phase 5.

---

## Traceability

100% coverage REQ → phase. Mapping 1-to-1 (mỗi REQ map đúng 1 phase, không có REQ orphan).

| REQ-ID | Phase | Confirm |
|---|---|---|
| TOPO-01..04 | Phase 1 | Multi-DB topology + per-hub Alembic |
| FACTOR-01..03 | Phase 2 | Hub-con codebase factor |
| SSO-01..04 | Phase 3 | Auth SSO + hub_ids trong JWT (GA-V3-A chốt) |
| SYNC-01..05 | Phase 4 | Cross-hub data sync (GA-V3-D part 1 chốt) |
| PROXY-01..04 | Phase 5 | Reverse proxy + frontend subpath (GA-V3-C chốt, D-V3-06 D6 expire) |
| SETTINGS-01..04 | Phase 6 | System settings sync (GA-V3-B chốt) |
| MIGRATE-01..05 | Phase 7 | Migration + smoke E2E (GA-V3-D part 2 chốt) |

**Tổng:** 4 + 3 + 4 + 5 + 4 + 4 + 5 = **29 REQ-ID v1**. 100% coverage qua 7 phase. Full mapping chi tiết: `.planning/ROADMAP.md` Traceability section.

---

*Last updated: 2026-05-21 sau `/gsd-new-milestone v3.0`. Pre-roadmap snapshot. REQ-ID có thể refine sau khi `/gsd-discuss-phase 1` chốt gray area Phase 1.*
