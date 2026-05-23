# Medinet Wiki — Hub_All

**Mã dự án:** MEDWIKI
**Giai đoạn:** **v3.1 RBAC hub_admin STARTED** 2026-05-23 — defining requirements + roadmap
**Current Milestone:** **v3.1 — RBAC hub_admin** (started 2026-05-23, phase numbering reset về 1, granularity small ~4 phase)
**Shipped:**
- **v2.0 — Full RAG Rewrite** ✅ 2026-05-21 (13 phase / ~75 plan / 38 REQ-ID — archive `.planning/milestones/v2.0-full-rag-rewrite/`)
- **v3.0 — Multi-Hub Split** ✅ 2026-05-23 (7 phase / 38 plan / 30 REQ-ID — archive `.planning/milestones/v3.0-multi-hub-split/`)
**Next:** v3.1 = RBAC hub_admin (gap thiết kế role-per-hub user yêu cầu 2026-05-23). Memory: `project_rbac_hub_admin_gap`.
**Defer:** v4.0 = Production Hardening + Advanced RAG (OCR VN, streaming SSE, cross-dim swap, coverage >80%, ...). v4.1+ = Hybrid BM25 + reranker + local embedding (SEED-001) + version history & concurrent editing.
**Abandoned:** v1.0 = RAG Quality with Docling (2026-05-13 — xem `MILESTONES.md`)
**Ngày khởi tạo GSD:** 2026-04-28 · **Pivot 2:** 2026-05-13 · **v2.0 shipped:** 2026-05-21 · **v3.0 shipped:** 2026-05-23

---

## What This Is

Medinet Wiki là hệ thống quản lý tri thức nội bộ đa-Hub (3 Hub: y tế / dược / HCNS) của Medinet, kết hợp wiki truyền thống với RAG (Retrieval Augmented Generation) — biến mọi tài liệu y tế / dược / HCNS thành chunk semantic giàu metadata để nhân viên tra cứu bằng ngôn ngữ tự nhiên, có citation. Tương lai expose qua MCP cho AI agent.

**Hub_All** là kho chứa toàn bộ source (backend + tất cả các SPA Hub) trước khi tách deploy ở milestone v3.0.

## Core Value

> **Ingestion tri thức của Medinet phải tái hiện trung thực cấu trúc tài liệu nguồn (heading, bảng, ảnh có chú thích, công thức, OCR tiếng Việt cho scanned PDF) — biến mọi tài liệu y tế / dược / HCNS thành chunk semantic giàu metadata, để top-3 retrieval đạt ≥ 75% trên eval set thật.**

Core value không đổi qua các milestone — chỉ cách triển khai thay đổi (Go-native → Docling sidecar → CocoIndex + FastAPI). Khi RAG chất lượng ổn định, các milestone sau (Multi-subdomain SPA, MCP Server, AI Post) mới có giá trị thực tế.

## Current Milestone: v3.1 RBAC hub_admin

**Goal:** Đóng gap thiết kế role-per-hub được defer v4.0 trong M2 — thêm role `hub_admin` để user "quản lý hub" CHỈ vào và quản lý 1 hub được gán, KHÔNG bypass hub isolation (đối lập với role `admin` hiện tại = super-admin toàn hệ thống). Backend enforce hub_id ∈ JWT.hub_ids + frontend tách rõ "Admin toàn hệ thống" vs "Quản lý hub này".

**Target features (4 phase, ~15 REQ-ID đề xuất, reset numbering về 1):**

- **Phase 1 — DB schema migration (ROLE):** Mở rộng CHECK constraint `role_enum` thêm `hub_admin`; thêm column `user_hubs.role` per-hub (carry forward schema v4.0 sẵn); migration script seed existing admins giữ super-admin global.
- **Phase 2 — Backend RBAC enforcement (DEP):** Dependency `require_hub_admin_for(hub_id)` verify hub_id ∈ JWT.hub_ids; refactor `GET /api/hubs` filter cả admin theo user_hubs (super admin exempt); CRUD endpoint users filter theo hub scope; audit log tag actor.scope.
- **Phase 3 — Frontend form refactor (FE):** UserManagement form tách "Admin toàn hệ thống" vs "Quản lý hub này"; hub switcher hide central nếu non-super-admin; edit warning gán super_admin.
- **Phase 4 — Migration + smoke E2E (MIGRATE):** Migration script idempotent; smoke 4 scenario (super_admin / hub_admin dmd / hub_admin tdt / viewer); audit trail verify; closeout docs.

**Key context (LOCKED 2026-05-23):**

- **D-V3.1-01:** GIỮ tên enum `admin` = super-admin toàn hệ thống (KHÔNG rename `super_admin` để tránh break v3.0 JWT/user_hubs/audit chain). Thêm `hub_admin` mới + frontend label phân biệt rõ ràng.
- **D-V3.1-02:** `user_hubs` thêm column `role` per-hub (defer v4.0 carry forward) — `users.role` giữ làm global default; nếu `user_hubs.role` non-null thì override per-hub.
- **D-V3.1-03:** Carry forward v3.0 SSO Layer 3 — JWT `hub_ids` claim đủ check membership; thêm dependency mới verify role trong hub đó.
- **D-V3.1-04:** Reset phase numbering về 1 (precedent D9 v2.0 + D-V3-05 v3.0).

**Open question (chốt ở `/gsd-discuss-phase`):**
- **GA-V3.1-A** (Phase 1): Migration backward compat — existing `users.role='admin'` map về `super_admin` (semantic) hay giữ nguyên + thêm flag `is_super_admin`? Trade-off: rename DB-wide vs flag column.
- **GA-V3.1-B** (Phase 2): Endpoint filter cho hub_admin xem `/api/hubs` — chỉ trả hub được gán (giống non-admin path hiện tại) vs trả tất cả + UI hide central?
- **GA-V3.1-C** (Phase 4): Migration idempotent strategy — re-run safety (CHECK constraint ADD nếu chưa có) + rollback procedure.

## Previous Milestone: v3.0 Multi-Hub Split (SHIPPED 2026-05-23)

## Previous Milestone: v3.0 Multi-Hub Split (SHIPPED 2026-05-23) — Carry-over context

**Goal (shipped):** Tách hub con (y_te, dược, HCNS) từ multi-tenancy LOGICAL (1 DB `medinet_central` + `WHERE hub_id`) sang **multi-tenancy PHYSICAL** — mỗi hub con có **process + Postgres database riêng cùng 1 instance**, hub tổng đóng vai trò aggregator nhận chunks + vector từ hub con (sync 1 chiều) để search cross-hub tập trung. URL subpath `wiki.domain.com/<ten_hub>`.

**Target features (7 phase, ~30 REQ-ID, phase numbering reset về 1):**

- **Phase 1 — Multi-DB topology + per-hub Alembic:** DB factory `medinet_hub_<name>` cùng instance, Alembic migration set per-hub, cocoindex flow naming per-hub (`medinet_<hub>_ingest`).
- **Phase 2 — Hub-con codebase factor:** 1 codebase deploy được nhiều lần với env `HUB_NAME=<name>`; strip system settings router (rag-config / api-keys / hub-registry) khi `HUB_NAME != "central"`.
- **Phase 3 — Auth SSO + hub_ids trong JWT (GA-V3-A):** JWT keypair share giữa central + sub-hub qua JWKS endpoint, refresh token blacklist Redis chung, E4 reinforced.
- **Phase 4 — Cross-hub data sync (D-V3-02):** Chunks + vector push từ hub con → `medinet_central.chunks` (cocoindex target thứ 2 / logical replication / outbox + worker — chốt ở `/gsd-discuss-phase 4`); idempotent on retry; checksum verify chống drift.
- **Phase 5 — Reverse proxy + frontend subpath (GA-V3-C):** Caddy route `wiki.domain.com/<hub>/api/*` → upstream container đúng, frontend detect prefix → build URL, **D6 expire chính thức** (frontend rewrite được phép).
- **Phase 6 — System settings sync (GA-V3-B):** Hub con đọc rag-config / api-keys từ central qua HTTP pull on-demand + Redis cache 60s + pub/sub invalidate (< 30s propagate).
- **Phase 7 — Migration + smoke E2E (GA-V3-D):** Split `medinet_central` cũ → DB hub con (blue/green per-hub), MCP service re-point central, full smoke 3 hub con + tổng healthy.

**Key context (LOCKED 2026-05-21, không đảo chiều mà không re-discuss):**

- **D-V3-01:** Postgres database riêng cùng instance (1 instance, N database — `medinet_central` + `medinet_hub_yte` + `medinet_hub_duoc` + `medinet_hub_hcns`). Bỏ phương án "schema riêng" (đụng R5/P7) và "instance riêng" (ops × N).
- **D-V3-02:** Dataflow hub con → tổng = **chunks + vector denormalized** sync 1 chiều. Hub tổng KHÔNG re-embed. Cost: storage 2× / benefit: cross-hub 1 DB nhanh, không federated HTTP fan-out.
- **D-V3-03:** Milestone-level scoping (KHÔNG nhét vào M2 dưới dạng 1 phase đơn lẻ — đã shipped v2.0 trước).
- **D-V3-04:** M2 closeout precondition — Phase 9 gate verdict (HUMAN UAT) + retrospective hoàn tất TRƯỚC v3.0 start. ✓ 2026-05-21: M2 100% COMPLETE, HUMAN UAT defer track standalone (KHÔNG block v3.0 start theo user trigger).

**Open gray areas (chốt ở `/gsd-discuss-phase` tương ứng):**

- **GA-V3-A** (Phase 3): JWT shared keypair vs JWKS endpoint vs cookie domain `.medinet.vn` cho SSO.
- **GA-V3-B** (Phase 6): rag-config sync — HTTP pull / push webhook / env var local (trade-off latency vs simplicity vs consistency).
- **GA-V3-C** (Phase 5): Frontend prefix detect — 1 build dùng chung detect từ pathname vs build per-hub `VITE_HUB_NAME=yte`. D6 expire formally.
- **GA-V3-D** (Phase 4 + 7): Sync mechanism (cocoindex target thứ 2 / Postgres logical replication / outbox + worker) + migration strategy (`pg_dump` per `hub_id` vs snapshot + replay cocoindex flow).

Seed full reference: `.planning/seeds/v3.0-multi-hub-split.md` (4 R-V3 risk + 4 E-V3 exit criteria preview).

## v2.0 SHIPPED ✅ 2026-05-21 (Carry-over context)

**Status:** M2 v2.0 100% COMPLETE — 13 phase / ~75 plan / 38 REQ-ID done. Tag git `v2.0` (annotated, local — push remote defer user trigger).

**Delivered (v2.0):**

1. **Python FastAPI backend** thay thế Go hoàn toàn — auth (JWT RS256 + Argon2 cross-compat Go params `m=65536,t=3,p=4`), hub registry CRUD, user management RBAC, audit log async, document CRUD, envelope `{success,data,error,meta}`
2. **CocoIndex 1.0.3 flow** ingest extract → chunk VN → embed dim 1536 → pgvector + content-hash incremental dedup + `BackgroundTasks` trigger (cocoindex 1.0.3 KHÔNG support LISTEN/NOTIFY) + heartbeat watchdog 300s + race vá Plan 04-08
3. **pgvector schema** + HNSW `vector_cosine_ops` + `iterative_scan=relaxed_order` + ef_search=200; hub isolation enforce ở repo layer (E4 6/6 critical PASS)
4. **Embedding hot-swap** OpenAI/Gemini within dim 1536 OK, cross-dim REFUSE 400 (defer v4.0)
5. **LLM answerer LiteLLM** + citation `[N]`→`chunk_id` + anti-injection prompt + cross-hub + token usage `BackgroundTasks` ghi `usage_events`
6. **Frontend KHÔNG sửa** (D6) — Phase 8 verify-only, 0 file `frontend/` đụng; SC1/SC2-browser/SC5 HUMAN UAT defer
7. **MCP server cho AI client ngoài** — Phase 8.1 in-process → Phase 8.2 standalone process HTTP → Phase 8.3 OAuth 2.0 + DCR + Caddy auto-TLS (mcp_service 135/135 PASS)
8. **Eval framework Python pytest** — `make eval-smoke` mock <60s + `make eval-all` real LLM gate verdict + `report.py` 7 section EVAL.md + pytest smoke regression CI gate zero external dep
9. **Hardening + observability** — structlog JSON 10 field + Prometheus `/metrics` 5 metric + critical-path coverage 57.75% + GitHub Actions CI test.yml + lint.yml secret detection

**Pending HUMAN UAT (KHÔNG block v2.0 close):**
- Phase 9 Wave 4 — gate verdict ≥75% top-3 với OpenAI key thật (~$0.20/run)
- Phase 8.3 — kết nối Claude web "Add custom connector" tới domain MeWiki MCP thật
- Phase 8 — render 11 trang React + citation `[1]` clickable + docker compose 5-service healthy

Full details: `.planning/milestones/v2.0-full-rag-rewrite/ROADMAP.md`

## Requirements

### Active (v3.1 NEXT — see project_rbac_hub_admin_gap memory)

User feature request 2026-05-23 — RBAC hub_admin role thực sự (gap thiết kế defer v4.0 trong M2 trở thành block).

- **RBAC-01..04 (TBD Phase 1 v3.1):** DB migration `role_enum` thêm `hub_admin` + `UserHub.role` per-hub column carry forward M2 schema
- **RBAC-05..08 (TBD Phase 2 v3.1):** Backend `require_role()` + `require_hub_admin_for(hub_id)` dependency + filter `GET /api/hubs` cho hub_admin (KHÔNG branch admin bypass)
- **RBAC-09..12 (TBD Phase 3 v3.1):** Frontend UserManagement form tách "Admin toàn hệ thống" vs "Quản lý hub này" + hub switcher hide central nếu non-super-admin
- **RBAC-13 (TBD Phase 4 v3.1):** Migration script seed existing admins giữ super-admin role + audit trail

REQ-ID cụ thể chốt qua `/gsd-new-milestone v3.1`.

### Validated (v3.0 shipped 2026-05-23 — 30/30 REQ-ID done)

- ✓ TOPO-01..04 — Multi-DB factory `medinet_hub_<name>` + per-hub Alembic head SHA match + cocoindex flow naming per-hub + HUB_NAME DSN isolation enforce DB-level (E-V3-3) — v3.0
- ✓ FACTOR-01..04 — `create_app()` factory conditional mount (7 universal + 9 central-only router) + docker-compose YAML anchor 4 service + dynamic hub registration `make hub-add HUB=<name>` Plan 02-05 — v3.0
- ✓ SSO-01..04 — JWKS endpoint central RFC 7517 + hub con JWKSCache TTL 1h + Redis blacklist `auth:blacklist:{jti}` + JWT `aud` + `hub_ids` REQUIRED + Layer 3 `get_current_user_for_hub_access` dependency — v3.0
- ✓ SYNC-01..05 — sync_outbox table + Postgres trigger AFTER INSERT/DELETE chunks + asyncio worker SKIP LOCKED + ON CONFLICT idempotent + 1 SQL cross-hub search aggregated + checksum scheduler daily/hourly + `POST /api/sync/replay` admin endpoint — v3.0
- ✓ PROXY-01..04 — Caddy subpath route `path_regexp + uri strip_prefix + reverse_proxy` + frontend 1 build runtime detect prefix + D6 EXPIRED formally + per-hub branding registry Vite glob 4 hub — v3.0
- ✓ SETTINGS-01..04 — HTTP pull on-demand + Redis cache TTL 60s/300s/60s + pub/sub invalidate `settings:invalidate` channel + 3 client class + `X-Internal-Auth` shared secret 32-char `hmac.compare_digest` — v3.0
- ✓ MIGRATE-01..05 — `scripts/migrate/` 5 bash script blue/green per-hub + MCP re-point central aggregate + smoke E2E automated 3 hub × 7-step golden path + chunks PRESERVED D-V3-02 — v3.0

### Validated (M2 v2.0 shipped 2026-05-21 — 38/38 REQ-ID done)

- ✓ Python FastAPI backend thay Go hoàn toàn (auth + hub + user + audit + ingest + search + ask + MCP) — v2.0
- ✓ CocoIndex 1.0.3 ingest dataflow + content-hash incremental dedup + heartbeat watchdog — v2.0
- ✓ pgvector + HNSW search single-hub & cross-hub + Redis cache hub-tagged Pub/Sub invalidate — v2.0
- ✓ Ask API + LiteLLM citation `[N]`→`chunk_id` + anti-injection + hot-swap provider + token usage logging — v2.0
- ✓ MCP server (3 tool read-only) + standalone process gọi API HTTP + OAuth 2.0 + DCR + Caddy auto-TLS — v2.0 (Phase 8.1/8.2/8.3)
- ✓ Eval framework Python pytest + 10 file VN medical + queries.jsonl + gate `report.py` exit 0/1/E5 + pytest smoke regression CI gate — v2.0
- ✓ Hardening: structlog JSON 10 field + Prometheus `/metrics` + critical-path coverage 57.75% + GitHub Actions CI — v2.0
- ✓ Frontend React 19 KHÔNG sửa (D6) — verify-only smoke 11 trang + VN filename UTF-8 — v2.0 (COMPAT-01)
- ✓ TEARDOWN Go backend xoá + tag `m1-go-archived` backup — v2.0 (TEARDOWN-01, pull-in 2026-05-14)

### Validated (brownfield — đã thay thế hoàn toàn ở M2, giữ làm lịch sử)

> ⚠️ Các capability dưới đây là scope cần xây trong M2. Go backend đã xóa 2026-05-14 (TEARDOWN-01 pull-in) — **KHÔNG còn "port từ Go source"**. Contract của mỗi capability lấy từ: (1) `frontend/src/services/api.ts` (URL path + request/response types — D6 ràng buộc), (2) response envelope `{success, data, error, meta}`, (3) git tag `m1-go-archived` nếu cần tra cứu shape Go cũ. Thiết kế fresh bằng Python, KHÔNG dịch 1-1 logic Go.

- **JWT RS256 + Argon2 + refresh token** — `python-jose` + `passlib[argon2]` (đã xong Phase 3)
- **Multi-Hub theo `hub_id`** — schema Postgres mới (Phase 2) + repo `asyncpg`/SQLAlchemy
- **Provider hot-swap embedding & LLM** runtime qua `PUT /api/rag-config` — FastAPI + LiteLLM
- **Async ingestion** — cocoindex's built-in scheduler (Rust core), đã xong Phase 4
- **Async usage logging non-blocking** — asyncio/background task
- **React SPA đầy đủ** (Dashboard, HubRegistry, DocumentIngestion, SyncQueue, UserManagement, AuditLog, APIKeyManagement, CrossHubSearch, Settings, GeminiAssistant, TokenUsage, Profile) — **KHÔNG đổi frontend** (chỉ giữ tương thích URL)
- **Cross-hub search API** — FastAPI

### Out of Scope (v3.0)

- **OCR Vietnamese revisit (Docling/Tesseract)** — defer v4.0. v3.0 vẫn dùng whitelist `{.docx, .txt, .md, .pdf text-only}` + `failed_unsupported` (R4 carry forward).
- **Cross-dim embedding swap (1536 ↔ 3072)** — defer v4.0. v3.0 vẫn PIN dim 1536 (R1 + R7 carry forward).
- **Streaming `/api/ask` SSE** — defer v4.0.
- **Comprehensive coverage >80%** — defer v4.0. v3.0 giữ gate ≥50% critical-path (HARD-03 carry forward).
- **Hybrid retrieval BM25 + reranker** — defer v4.1.
- **Local embedding model (sentence-transformers / BGE-M3)** — defer v4.1 (SEED-001 dormant).
- **Version history & concurrent editing** — defer v4.1.
- **Khắc phục CONCERNS bảo mật cũ** (.gitignore root, GCP key audit, AES_KEY rotation, XSS token storage) — defer v4.0.
- **Branch protection rule GitHub repo enforce 2 workflow trước merge main** — admin permission, defer v4.0.
- **Schema riêng per hub trong cùng DB** — bỏ phương án này (đụng R5/P7 — cocoindex `db_schema_name` cố định). Locked D-V3-01.
- **Instance Postgres riêng per hub** — bỏ phương án này (ops × N). Locked D-V3-01.
- **Federated HTTP fan-out cho cross-hub search** — bỏ phương án này (latency × N hub). Locked D-V3-02 (chunks+vector denormalized).
- **Hub tổng re-embed chunks từ hub con** — KHÔNG re-embed; lưu sẵn vector 1536-dim từ hub con. Locked D-V3-02.

### Out of Scope (M2 — đã đóng, giữ làm lịch sử)

- **Docling integration** — gỡ hoàn toàn ở v2.0 (D4). Risk regress scanned PDF tiếng Việt đã accept (R4 mitigation: `failed_unsupported` enum).
- **Frontend rewrite / Multi-subdomain SPA** — defer sang v3.0 (đang scope ở Phase 5).
- **MCP Server** — đã ship trong v2.0 (Phase 8.1/8.2/8.3).
- **Migration data từ ChromaDB cũ** — M1 chưa production, clean slate (đã thực thi).
- **Test coverage tổng quát** — defer v4.0 (v2.0 chỉ test critical path 57.75%).
- **Hybrid retrieval BM25 + version history** — defer v4.0/v4.1.
- **Local embedding model** — defer v4.1 (SEED-001).

## Context

**Tech stack v3.0 (kế thừa v2.0 — KHÔNG đổi runtime):**
- Backend: **Python 3.12 · FastAPI 0.136.1 · cocoindex 1.0.3 · asyncpg/SQLAlchemy 2 async · pwdlib Argon2 · PyJWT RS256 · redis-py · LiteLLM**
- Vector store: **Postgres pgvector pg16** — multi-DB cùng instance (`medinet_central` + `medinet_hub_<name>` × N)
- Frontend: **React 19 · Vite 6 · TypeScript 5.8 · Tailwind v4** — **D6 expire ở Phase 5** (frontend rewrite được phép cho prefix detect + per-hub branding)
- Infra: Docker Compose mở rộng — 1 Postgres (multi-DB) + 1 Redis + N+1 process FastAPI (1 central + N hub con) + Caddy reverse proxy subpath + MCP service re-point central
- Reverse proxy: **Caddy auto-TLS** (đã ship v2.0 Phase 8.3) — extend route `wiki.domain.com/<hub>/api/*` (Phase 5)

**Codebase cũ đã xóa khỏi working tree:**
- `Hub_All/backend/` (toàn bộ Go) — xóa 2026-05-14 (TEARDOWN-01 pull-in sớm hơn Phase 8); backup git tag `m1-go-archived`
- `Hub_All/docling-pipeline/` (Python sidecar Docling cũ) — xóa Phase 1
- `Hub_All/eval/` (eval scripts cũ) — xóa Phase 1, viết lại từ đầu ở Phase 9

**Stakeholder:** Nội bộ Medinet — Admin/Editor (vận hành), Viewer (nhân viên Hub), AI Agent (Claude/ChatGPT qua MCP — sau v4.0). User cuối là nhân viên y tế / dược / HCNS — không kỹ thuật.

**Pain points đã giải quyết tạm trong M1 (sẽ rebuild trong M2):**
- Scanned PDF tiếng Việt: M1 đã giải bằng Docling + Tesseract `vie+eng`. **M2 gỡ Docling → có risk regress.** Cần re-evaluate trong Phase ingest.
- Bảng phức tạp: M1 giải bằng Docling table HTML preservation. M2 cần giải pháp khác (camelot/pdfplumber? hoặc accept loss).
- Heading regex Go ALL CAPS dễ false positive với tiếng Việt: tự nhiên giải vì cocoindex chunker khác.

## Constraints (v3.0)

- **Tech stack:** giữ nguyên v2.0 — Python 3.12 · FastAPI 0.136.1 · cocoindex 1.0.3 · pgvector pg16. KHÔNG bump version giữa milestone.
- **Multi-DB cùng instance:** N+1 database trên 1 Postgres instance (`medinet_central` + `medinet_hub_<name>`). KHÔNG schema riêng (đụng cocoindex `db_schema_name` fixed — R5/P7). KHÔNG instance riêng (ops × N).
- **Embedding dim:** vẫn PIN 1536 cho cả OpenAI + Gemini (R1 carry forward). Hub tổng KHÔNG re-embed — nhận sẵn vector từ hub con.
- **Dataflow direction:** Hub con → tổng 1 chiều (chunks + vector denormalized). Hub tổng KHÔNG ghi ngược về hub con. D-V3-02.
- **D6 expire ở Phase 5:** Frontend rewrite được phép — prefix detect, per-hub login branding, base URL detect từ `window.location.pathname.split('/')[1]`.
- **Hub isolation E4 reinforced:** DB-level isolation (hub con CHỈ có data của chính nó). Cross-hub search ở central qua aggregated chunks + `hub_ids` JWT claim.
- **Performance carry forward:** Search hub đơn < 800ms p95, cross-hub < 1.5s p95 (E-V3-2 — KHÔNG regress so với Phase 6 M2).
- **Settings sync propagation:** Đổi rag-config ở central → hub con propagate < 30s (E-V3-4).
- **Migration window:** Mỗi hub blue/green deploy — KHÔNG full downtime (R-V3-4 mitigation).
- **OCR Vietnamese:** Vẫn `failed_unsupported` cho scanned PDF (R4 carry forward — defer revisit v4.0).
- **OAuth + JWKS:** Reuse JWT RS256 keypair v2.0 `api/keys/`. JWKS endpoint mới ở central exposing public key (Phase 3).
- **MCP service:** Re-point gọi central cho cross-hub aggregate (Phase 7). KHÔNG fan-out N hub con.

## Risk Register (v3.0)

Đăng ký rủi ro chính cho v3.0 Multi-Hub Split. Mỗi risk gắn phase phụ trách + mitigation cụ thể.

| # | Risk | Severity | Phase address | Mitigation cụ thể |
|---|---|---|---|---|
| **R-V3-1** | Sync chunks + vector 2 lần (hub con + tổng) gây drift → cross-hub query mismatch hub-con-local | HIGH | Phase 4 | Outbox pattern (transactional INSERT outbox + worker push idempotent ON CONFLICT (content_hash)) + checksum verify periodic (daily count + sample hash diff hub con vs tổng). Track sync lag metric Prometheus. |
| **R-V3-2** | D6 expire — frontend rewrite cho prefix detect + per-hub branding → risk regress 11 trang React đã ship M2 | HIGH | Phase 5 | D6 expire formally ở v3.0-05. Smoke test 11 trang React (M2 COMPAT-01 carry forward) cho mỗi hub con + tổng sau khi đổi base URL. Per-hub branding tách `frontend/src/branding/<hub>/` thay vì sửa core. |
| **R-V3-3** | Per-hub Alembic drift — mỗi DB tự upgrade → schema mismatch giữa các hub | MEDIUM | Phase 1 | CI lint check Alembic head revision khớp giữa N DB sau migration. Make target `make migrate-all` apply N database tuần tự + verify version. |
| **R-V3-4** | Migration data từ `medinet_central` cũ — downtime cần thiết | MEDIUM | Phase 7 | Blue/green per-hub — clone `medinet_central` cũ → DB hub con NEW (parallel), test smoke trên DB NEW, switch traffic, truncate hub_id rows khỏi central sau khi accept. KHÔNG full stack downtime. |
| **R-V3-5** | JWKS endpoint xuống → hub con KHÔNG verify được JWT → users logged out toàn bộ | MEDIUM | Phase 3 | Hub con cache JWKS local TTL 1h + fallback static keypair embedded ở deploy time (rotation manual). Central JWKS endpoint high-availability (read-only, KHÔNG DB query mỗi request — load 1 lần lifespan). |
| **R-V3-6** | Settings sync race — hub con đang xử lý request cũ rag-config khi central đã đổi → response inconsistent | LOW | Phase 6 | Redis pub/sub invalidate channel `settings:invalidate` + hub con re-fetch trong < 30s + idempotent settings application. Accept eventual consistency trong window 30s (E-V3-4). |

**Carry forward từ v2.0 (vẫn áp dụng):** R1 (pgvector 2000-dim → PIN 1536), R2 (HNSW post-filter → ef_search=200 + iterative_scan), R4 (scanned PDF → failed_unsupported), R6 (Argon2 cross-compat — không còn relevant vì Go đã teardown nhưng pwdlib params vẫn pin), R7 (cross-dim swap REFUSE 400 — defer v4.0). Chi tiết: `.planning/research/PITFALLS.md`.

## EXIT Criteria (v3.0)

Nếu một trong các điều kiện sau xảy ra, **DỪNG v3.0** và discuss với user trước khi tiếp tục.

| # | Trigger | Action |
|---|---|---|
| **E-V3-1** | 3 hub con + tổng KHÔNG healthy trên Docker Compose sau Phase 7; HOẶC golden path `wiki.domain.com/yte` FAIL (login → upload → search local + cross-hub) | STOP, root-cause: process model issue / proxy config / DB topology — discuss revert sang multi-tenancy logical |
| **E-V3-2** | Cross-hub search latency p95 ≥ 1.5s ở Phase 4/7 dù đã tune (denormalized chunks index + ef_search + connection pool) | STOP, discuss giảm hub_count concurrent / dim reduce thêm / fan-out federated thay vì denormalized |
| **E-V3-3** | Hub isolation bug DB-level **không fixable trong 7 ngày** sau khi phát hiện (hub con truy cập được data hub khác qua DB connection / JWT bypass) | STOP, security review — không ship v3.0 có data leak |
| **E-V3-4** | System settings change ở central KHÔNG propagate xuống hub con trong < 60s sau 3 vòng iterate Phase 6 | STOP, discuss push webhook thay HTTP pull / accept eventual consistency window lớn hơn |
| **E-V3-5** | Sync drift hub con vs tổng > 1% rows sau 7 ngày run continuously trong Phase 4 staging | STOP, replace outbox/replication mechanism — chốt lại GA-V3-D ở re-discuss |

**v3.0-a / v3.0-b split (anti-pivot mitigation, kế thừa pattern R3 v2.0):**

- **v3.0-a = Phase 1-3** — Topology + codebase factor + auth SSO. Có thể ship đứng độc lập (demo: 1 hub con đứng riêng, login chéo central PASS, KHÔNG sync). **Nếu user accept v3.0-a → never pivot multi-DB topology.**
- **v3.0-b = Phase 4-7** — Sync + proxy + settings + migration. Pivot v3.0-b OK nếu sync mechanism (GA-V3-D) chốt sai — v3.0-a giữ nguyên reusable.
- 🚦 **v3.0-a EXIT GATE** giữa Phase 3 và 4 — demo 1 hub con + tổng + JWT SSO PASS → user accept là điều kiện tiếp tục v3.0-b.

**Weekly check-in:**

| Day | Checkpoint |
|---|---|
| Day 7 | Phase 1 done? `medinet_hub_yte` DB created + Alembic migration head match central? |
| Day 14 | Phase 2-3 done? Hub con deploy với `HUB_NAME=yte` + JWT SSO PASS (login central, verify hub con qua JWKS)? |
| Day 21 | **v3.0-a EXIT GATE** — 1 hub con + tổng + JWT SSO + golden path PASS → user accept? |
| Day 28 | Phase 4-5 done? Chunks sync hub con → tổng + cross-hub search PASS? Caddy subpath + frontend prefix detect PASS? |
| Day 35 | Phase 6-7 done? Settings sync < 30s + migration data full + smoke E2E 3 hub PASS? |

## Key Decisions

### v3.0 LOCKED (2026-05-21)

| # | Decision | Rationale | Outcome |
|---|---|---|---|
| **D-V3-01** | Multi-tenancy PHYSICAL = Postgres database riêng cùng instance (`medinet_central` + `medinet_hub_<name>` × N trên 1 instance) | Backup chung + network đơn giản + cocoindex flow ngắn; bỏ schema riêng (đụng cocoindex `db_schema_name` fixed R5/P7) + bỏ instance riêng (ops × N) | LOCKED 2026-05-21 (chốt qua AskUserQuestion seed) |
| **D-V3-02** | Dataflow hub con → tổng = chunks + vector denormalized sync 1 chiều; hub tổng KHÔNG re-embed | Cross-hub search 1 DB nhanh, KHÔNG federated HTTP fan-out; cost storage 2× chấp nhận được | LOCKED 2026-05-21 |
| **D-V3-03** | Scoping = milestone v3.0 mới (KHÔNG nhét vào M2 dưới dạng 1 phase) | Scope quá lớn — 7 phase ~30 REQ; nhét M2 phá EXIT criteria + R3 anti-pivot fatigue | LOCKED 2026-05-21 (M2 đã shipped 2026-05-21 trước v3.0 start) |
| **D-V3-04** | M2 closeout precondition — HUMAN UAT Phase 9 gate verdict + retrospective xong TRƯỚC v3.0 start | RAG chưa chứng minh ≥75% top-3 sẽ propagate bug × N hub khi split | LOCKED 2026-05-21; HUMAN UAT track standalone defer KHÔNG block v3.0 start theo user trigger |
| **D-V3-05** | Phase numbering reset về 1 cho v3.0 (continuation từ v2.0 hết Phase 10 KHÔNG phù hợp) | Milestone-level scoping (D-V3-03); seed labels v3.0-01..07; precedent D9 v2.0 reset | LOCKED 2026-05-21 |
| **D-V3-06** | D6 expire formally ở Phase 5 — frontend rewrite được phép cho prefix detect + per-hub branding | URL subpath `wiki.domain.com/<hub>` cần frontend đổi base URL detect prefix; "fix CSS được phép sửa React" feedback đã chuẩn bị | LOCKED 2026-05-21 (re-confirm ở Phase 5 discuss-phase) |

### v2.0 Carry forward (đã shipped — giữ làm lịch sử)

| # | Decision | Rationale | Outcome |
|---|---|---|---|
| D1 | **Toàn bộ backend Go → Python FastAPI** | Codebase đồng nhất Python với cocoindex; tránh boundary Go↔Python phức tạp; LiteLLM/asyncpg trưởng thành | ✅ Shipped v2.0 |
| D2 | **CocoIndex v1.0.3+ làm indexing layer** | Incremental diff content-hash + LMDB fingerprint = giải quyết backlog 999.1 sẵn; lineage chunk→source built-in; Rust core production-grade | ✅ Shipped v2.0 |
| D3 | **Postgres pgvector** thay ChromaDB | Bớt 1 service; dùng Postgres sẵn có; pgvector là cocoindex flagship target battle-tested hơn ChromaDB target (recent 2025) | ✅ Shipped v2.0 |
| D4 | **Gỡ Docling hoàn toàn** | Codebase đồng nhất, không phụ thuộc binary Tesseract/Docling model 2GB | ⚠️ Risk regress scanned PDF tiếng Việt + bảng — documented |
| D5 | **LLM answerer giữ hot-swap OpenAI/Gemini** (port sang LiteLLM) | Đã work tốt với tiếng Việt; KHÔNG thêm local model trong M2 | ✅ Shipped v2.0 |
| D6 | **Frontend KHÔNG sửa trong M2** | Risk giảm; URL `/api/*` giữ qua nginx/FastAPI cùng port :8080 | ✅ Shipped v2.0 |
| D7 | **Abandon M1 hoàn toàn** | M1 chưa runtime verify (chưa chạy `make eval-all`), chưa production → mất ít công sức nhất khi pivot bây giờ thay vì sau | — Logged (xem `MILESTONES.md`) |
| D8 | **Eval framework làm lại từ đầu** | `eval/` Go-style queries hardcoded path; M2 dùng Python pytest + queries.jsonl giữ semantic + dataset 10 file gold giữ | ✅ Shipped v2.0 |
| D9 | **Phase numbering reset về 1** (--reset-phase-numbers) | M2 = rewrite full, không tiếp nối M1 logic; archive M1 phases vào `.planning/milestones/v1.0-docling-rag/` | — Logged |
| ~~M1 cũ: Multi-subdomain SPA~~ → Pivot 1: RAG Quality with Docling | (2026-04-28 — đã abandoned) | ❌ Abandoned 2026-05-13 |
| Sử dụng Docling thay vì MarkItDown | (Decision của M1, không còn áp dụng) | ❌ Reverted by D4 |
| Service split Python sidecar chỉ Extract+Chunk | (Decision của M1, không còn áp dụng) | ❌ Reverted by D1 |
| Embedding giữ OpenAI/Gemini hot-swap | Hot-swap đã có, tránh thêm dependency local model | ✓ Carried forward (D5) |
| Granularity: Large (10-15 phases) | M2 scope rất lớn (backend rewrite + RAG rewrite + eval + integration) | ✅ Shipped v2.0 |
| Mode: YOLO | Tài liệu PRD/RAG/Backend Plan rất chi tiết; tin context có sẵn | ✅ Shipped v2.0 |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-05-23 sau `/gsd-complete-milestone v3.0` — Multi-Hub Split SHIPPED ✅. 7 phase / 38 plan / 30 REQ-ID (TOPO 4 + FACTOR 4 + SSO 4 + SYNC 5 + PROXY 4 + SETTINGS 4 + MIGRATE 5). v3.0-a (Phase 1-3) + v3.0-b (Phase 4-7) anti-pivot pattern hoàn tất. Archive: `.planning/milestones/v3.0-multi-hub-split/`. RBAC hub_admin gap phát hiện sau close → v3.1 next milestone (user request memory `project_rbac_hub_admin_gap`). Next command: `/gsd-new-milestone v3.1`.*
