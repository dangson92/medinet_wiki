# Medinet Wiki — Hub_All

**Mã dự án:** MEDWIKI
**Giai đoạn:** Post-v2.0 closeout (M2 shipped 2026-05-21) — chờ trigger `/gsd-new-milestone v3.0` Multi-Hub Split
**Shipped:** **v2.0 — Full RAG Rewrite (CocoIndex + Python FastAPI + pgvector)** ✅ 2026-05-21 (13 phase / ~75 plan / 38 REQ-ID — xem `.planning/milestones/v2.0-full-rag-rewrite/`)
**Next Milestone:** **v3.0 — Multi-Hub Split** (LOCKED 4 D-V3 + 4 GA-V3 open — seed `.planning/seeds/v3.0-multi-hub-split.md`)
**Defer:** v4.0 = Production Hardening + Advanced RAG (OCR VN, streaming SSE, cross-dim swap, coverage >80%, ...)
**Abandoned:** v1.0 = RAG Quality with Docling (2026-05-13 — xem `MILESTONES.md`)
**Ngày khởi tạo GSD:** 2026-04-28 · **Pivot 2:** 2026-05-13 · **v2.0 shipped:** 2026-05-21

---

## What This Is

Medinet Wiki là hệ thống quản lý tri thức nội bộ đa-Hub (3 Hub: y tế / dược / HCNS) của Medinet, kết hợp wiki truyền thống với RAG (Retrieval Augmented Generation) — biến mọi tài liệu y tế / dược / HCNS thành chunk semantic giàu metadata để nhân viên tra cứu bằng ngôn ngữ tự nhiên, có citation. Tương lai expose qua MCP cho AI agent.

**Hub_All** là kho chứa toàn bộ source (backend + tất cả các SPA Hub) trước khi tách deploy ở milestone v3.0.

## Core Value

> **Ingestion tri thức của Medinet phải tái hiện trung thực cấu trúc tài liệu nguồn (heading, bảng, ảnh có chú thích, công thức, OCR tiếng Việt cho scanned PDF) — biến mọi tài liệu y tế / dược / HCNS thành chunk semantic giàu metadata, để top-3 retrieval đạt ≥ 75% trên eval set thật.**

Core value không đổi qua các milestone — chỉ cách triển khai thay đổi (Go-native → Docling sidecar → CocoIndex + FastAPI). Khi RAG chất lượng ổn định, các milestone sau (Multi-subdomain SPA, MCP Server, AI Post) mới có giá trị thực tế.

## Current State: v2.0 SHIPPED ✅ 2026-05-21

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

## Next Milestone Goals: v3.0 Multi-Hub Split

**Trigger:** `/gsd-new-milestone v3.0` sau khi user verify v2.0 closeout (HUMAN UAT Phase 9 gate verdict + retrospective).

**Goal:** Tách hub con (y_te, dược, HCNS) từ multi-tenancy LOGICAL (1 DB `medinet_central` + `WHERE hub_id`) sang **multi-tenancy PHYSICAL** — mỗi hub con có **process + Postgres database riêng cùng 1 instance**, hub tổng đóng vai trò aggregator nhận chunks + vector từ hub con (sync 1 chiều) để search cross-hub tập trung. URL subpath `wiki.domain.com/<ten_hub>`.

**LOCKED architectural decisions (2026-05-21):**
- **D-V3-01:** Postgres database riêng cùng instance (`medinet_central` + `medinet_hub_yte` + `medinet_hub_duoc` + `medinet_hub_hcns`). Backup chung, network đơn giản, cocoindex flow ngắn.
- **D-V3-02:** Dataflow hub con → tổng = **chunks + vector denormalized** sync 1 chiều (cocoindex target thứ 2 / Postgres logical replication / outbox + worker — chốt ở `/gsd-discuss-phase`). Hub tổng KHÔNG re-embed.
- **D-V3-03:** Milestone-level scoping — KHÔNG nhét vào M2 dưới dạng 1 phase.
- **D-V3-04:** M2 closeout precondition — Phase 9 gate ≥75% + retrospective phải xong TRƯỚC v3.0 start.

**Open questions (chốt ở `/gsd-discuss-milestone v3.0`):**
- **GA-V3-A:** Auth SSO design (JWT shared secret / OIDC / cookie domain `.medinet.vn`).
- **GA-V3-B:** System settings sync (rag-config global vs per-hub override; api_keys vs `X-API-Key` propagation).
- **GA-V3-C:** Reverse proxy frontend prefix detect (Caddy/nginx `/{ten_hub}` → đúng SPA bundle + JWT issuer per subpath).
- **GA-V3-D:** Migration data từ `medinet_central` cũ — partition table theo `hub_id` → physical split.

Seed full: `.planning/seeds/v3.0-multi-hub-split.md` (7 phase ~35 plan + 4 R-V3 risk + 4 E-V3 exit criteria)

## Requirements

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

### Active (chờ trigger v3.0 Multi-Hub Split)

Sẽ liệt kê chi tiết ở `/gsd-new-milestone v3.0` — tham chiếu seed `.planning/seeds/v3.0-multi-hub-split.md`. Tóm tắt:

- [ ] **HUB-V3-01..N**: Tách hub con (y_te, dược, HCNS) thành process + Postgres database riêng cùng instance (D-V3-01)
- [ ] **SYNC-V3**: Dataflow hub con → hub tổng = chunks + vector denormalized sync 1 chiều (D-V3-02)
- [ ] **AUTH-V3**: SSO across subpath `wiki.domain.com/<ten_hub>` (GA-V3-A chốt)
- [ ] **PROXY-V3**: Reverse proxy frontend prefix detect (GA-V3-C chốt)
- [ ] **SETTINGS-V3**: rag-config global vs per-hub override (GA-V3-B chốt)
- [ ] **MIGRATE-V3**: Data migration `medinet_central` cũ → physical split (GA-V3-D chốt)

### Validated (brownfield — đã thay thế hoàn toàn ở M2, giữ làm lịch sử)

> ⚠️ Các capability dưới đây là scope cần xây trong M2. Go backend đã xóa 2026-05-14 (TEARDOWN-01 pull-in) — **KHÔNG còn "port từ Go source"**. Contract của mỗi capability lấy từ: (1) `frontend/src/services/api.ts` (URL path + request/response types — D6 ràng buộc), (2) response envelope `{success, data, error, meta}`, (3) git tag `m1-go-archived` nếu cần tra cứu shape Go cũ. Thiết kế fresh bằng Python, KHÔNG dịch 1-1 logic Go.

- **JWT RS256 + Argon2 + refresh token** — `python-jose` + `passlib[argon2]` (đã xong Phase 3)
- **Multi-Hub theo `hub_id`** — schema Postgres mới (Phase 2) + repo `asyncpg`/SQLAlchemy
- **Provider hot-swap embedding & LLM** runtime qua `PUT /api/rag-config` — FastAPI + LiteLLM
- **Async ingestion** — cocoindex's built-in scheduler (Rust core), đã xong Phase 4
- **Async usage logging non-blocking** — asyncio/background task
- **React SPA đầy đủ** (Dashboard, HubRegistry, DocumentIngestion, SyncQueue, UserManagement, AuditLog, APIKeyManagement, CrossHubSearch, Settings, GeminiAssistant, TokenUsage, Profile) — **KHÔNG đổi frontend** (chỉ giữ tương thích URL)
- **Cross-hub search API** — FastAPI

### Out of Scope (M2)

- **Docling integration** — gỡ hoàn toàn theo quyết định D4 (xem Key Decisions). Risk: scanned PDF tiếng Việt + bảng phức tạp sẽ regress so với M1. Mitigation: M2 ship với supported formats giới hạn (DOCX/TXT/MD/PDF text-only), revisit Docling/Tesseract ở milestone hardening nếu user feedback regress.
- **Frontend rewrite / Multi-subdomain SPA** — defer sang v3.0.
- **MCP Server** — defer sang v4.0.
- **Migration data từ ChromaDB cũ** — M1 chưa production, không có user upload thật. Clean slate.
- **Test coverage tổng quát** — milestone hardening riêng. M2 chỉ test critical path (auth + ingest + search + ask).
- **Hybrid retrieval BM25** — Phase 2 PRD (defer).
- **Version history & concurrent editing** — Phase 3 PRD (defer).
- **Đổi embedding model sang local (sentence-transformers / BGE-M3)** — giữ OpenAI/Gemini.
- **Khắc phục CONCERNS bảo mật cũ** (`.gitignore` root, GCP key audit, AES_KEY rotation, XSS token storage) — hardening riêng (v4.0).

## Context

**Tech stack mục tiêu (M2):**
- Backend: **Python 3.11+ · FastAPI · cocoindex v1.0.3+ · asyncpg/SQLAlchemy · python-jose · passlib[argon2] · redis-py · LiteLLM**
- Vector store: **Postgres pgvector** (cùng instance Postgres 16 với hub/user/audit data)
- Frontend: **React 19 · Vite 6 · TypeScript 5.8 · Tailwind v4** (KHÔNG đổi)
- Infra: Docker Compose — `postgres+pgvector` + `redis` + `python-api` (3 service, giảm từ 4)

**Codebase cũ đã xóa khỏi working tree:**
- `Hub_All/backend/` (toàn bộ Go) — xóa 2026-05-14 (TEARDOWN-01 pull-in sớm hơn Phase 8); backup git tag `m1-go-archived`
- `Hub_All/docling-pipeline/` (Python sidecar Docling cũ) — xóa Phase 1
- `Hub_All/eval/` (eval scripts cũ) — xóa Phase 1, viết lại từ đầu ở Phase 9

**Stakeholder:** Nội bộ Medinet — Admin/Editor (vận hành), Viewer (nhân viên Hub), AI Agent (Claude/ChatGPT qua MCP — sau v4.0). User cuối là nhân viên y tế / dược / HCNS — không kỹ thuật.

**Pain points đã giải quyết tạm trong M1 (sẽ rebuild trong M2):**
- Scanned PDF tiếng Việt: M1 đã giải bằng Docling + Tesseract `vie+eng`. **M2 gỡ Docling → có risk regress.** Cần re-evaluate trong Phase ingest.
- Bảng phức tạp: M1 giải bằng Docling table HTML preservation. M2 cần giải pháp khác (camelot/pdfplumber? hoặc accept loss).
- Heading regex Go ALL CAPS dễ false positive với tiếng Việt: tự nhiên giải vì cocoindex chunker khác.

## Constraints

- **Tech stack:** Python 3.11+ (cocoindex yêu cầu) — KHÔNG Go trong code mới
- **Vector store:** Postgres pgvector — KHÔNG ChromaDB/Qdrant trong M2 (revisit sau)
- **Frontend:** KHÔNG sửa React app — chỉ giữ tương thích URL `/api/*`
- **JWT compatibility:** Token cũ (nếu có user đăng nhập) cần verify được sau khi rewrite — keypair `backend/keys/` reuse
- **Database schema:** Reuse Postgres schema sẵn có (users, hubs, documents, audit_logs) — chỉ thêm cột pgvector + drop ChromaDB-only cols (`chroma_collection`, `extractor_used`)
- **Performance:** Search Hub riêng < 800ms p95, cross-hub < 1.5s p95, CRUD < 300ms p95 (PRD v1.3 giữ nguyên)
- **OCR Vietnamese:** Đã gỡ Docling → **không hỗ trợ scanned PDF tiếng Việt trong M2** (documented risk). Format hỗ trợ ở M2: DOCX, TXT, MD, PDF text-only. Scanned PDF sẽ trả lỗi tường minh thay vì silent fail.
- **Migration window:** Pivot lần 2 trong 15 ngày — phải hoàn thành M2 trong khoảng thời gian hợp lý (4-8 tuần) để tránh thrash thêm nữa.

## Risk Register (M2)

Đăng ký rủi ro chính từ research `.planning/research/PITFALLS.md`. Mỗi risk gắn phase phụ trách + mitigation cụ thể.

| # | Risk | Severity | Phase address | Mitigation cụ thể |
|---|---|---|---|---|
| **R1** | pgvector index 2000-dim limit → HNSW FAIL → Seq Scan → p95 vỡ | HIGH | Phase 1, 4 | OpenAI `dimensions=1536` API param. Verify Phase 1 bằng `CREATE INDEX USING hnsw (vector vector_cosine_ops)` trên `vector(1536)` TRƯỚC khi viết flow. |
| **R2** | HNSW post-filter recall collapse khi filter `hub_id` → hub leak hoặc results trống | HIGH | Phase 6, 9 | Pin `pgvector ≥0.8` + `SET hnsw.iterative_scan = relaxed_order` + `SET hnsw.max_scan_tuples = 20000`. Eval Phase 9 measure recall WITH `hub_id` filter (KHÔNG without). |
| **R3** | **Pivot fatigue → pivot 3 trong 30 ngày** — M1 abandoned 2026-05-13, pivot 2 trong 15 ngày | **CRITICAL** | Phase 1 (bake) | Bake **EXIT criteria** (xem dưới) + **split M2a / M2b** + weekly check-in day 7/14/21/28. NO new tool adoption mid-flight. |
| **R4** | Scanned PDF tiếng Việt silent fail (D4 gỡ Docling) → status='completed' nhưng chunk_count=0 | HIGH | Phase 4, 8 | Explicit format whitelist `{.docx, .txt, .md, .pdf}` + detect scanned PDF post-extract → enum `failed_unsupported` (khác `failed`) + frontend message "chuyển sang DOCX" thay vì retry. |
| R5 | CocoIndex naming + APP_NAMESPACE prefix → bảng "biến mất" pgAdmin | MEDIUM | Phase 1, 4 | Tên flow snake_case (`name="medinet_wiki_ingest"`), `APP_NAMESPACE=medinet_prod` trong `.env.example`, `db_schema_name="cocoindex"`, alembic include_object filter ignore cocoindex tables, document tên thực tế trong CONVENTIONS.md. |
| R6 | Argon2 hash cross-compat Go↔Python — pwdlib verify hash do `alexedwards/argon2id` tạo | MEDIUM | Phase 3 | Mandatory integration test với Go params `m=65536, t=1, p=2, saltLen=16, keyLen=32`. Pin pwdlib params Go-compat; fail-fast nếu mismatch. |
| R7 | Embedding model swap = full re-embed delta (~$6.50 cho 100K chunks) | MEDIUM | Phase 7 | Pin dim 1536 cho cả OpenAI/Gemini → swap không cần re-embed. UI WARNING modal "re-embed N chunks, est $X, est T phút" khi đổi provider khác dim. Defer cross-dim swap v4.0. |

**16 pitfall còn lại (P5-P20):** chi tiết + prevention checklist trong `.planning/research/PITFALLS.md`.

## EXIT Criteria (anti-pivot fatigue — R3 mitigation)

Nếu một trong các điều kiện sau xảy ra, **DỪNG M2** và discuss với user trước khi tiếp tục — KHÔNG tự pivot sang stack khác.

| # | Trigger | Action |
|---|---|---|
| **E1** | CocoIndex critical bug không có fix trong **14 ngày** (upstream issue mở >14 days, không có workaround) | STOP, mở `/gsd-discuss-milestone` re-evaluate (giữ pgvector + thay cocoindex bằng custom Python flow, hoặc rollback M1 Docling) |
| **E2** | pgvector p95 search latency >2000ms ở 50K chunks DÙ đã tune (HNSW + iterative_scan + connection pool + worker count) | STOP, discuss Qdrant migration hoặc dim reduce thêm |
| **E3** | Phase 1-3 (Infra + Schema + Auth) vượt **21 ngày calendar** | STOP, scope review — cắt feature hay người |
| **E4** | Hub isolation bug **không fixable trong 7 ngày** sau khi phát hiện (test fail, hub_A leak vào hub_B query) | STOP, security review — không ship M2 có data leak |
| **E5** | Quality gate Phase 9 fail (<60% top-3) DÙ đã iterate 3 vòng chunker/prompt | Stop M2b, ship M2a standalone, discuss reranker / hybrid BM25 cho v3.0 |

**M2a/M2b split (R3 mitigation):**

- **M2a = Phase 1-4** — Backend foundation + cocoindex MVP. Có thể ship đứng độc lập (demo upload DOCX → chunks trong pgvector → SELECT verify). **Nếu user accept M2a → never pivot.**
- **M2b = Phase 5-10** — RAG completion (CRUD + Search + Ask + Eval + Hardening). Pivot M2b OK nếu cocoindex critical fail — M2a giữ nguyên reusable.

**Weekly check-in (R3 mitigation):**

| Day | Checkpoint |
|---|---|
| Day 7 | Phase 1-2 done? Schema migration applied? Docker compose 3-service up? |
| Day 14 | Phase 3 (auth) PASS Argon2 cross-compat test? Phase 4 (cocoindex flow) MVP ingest 1 file? |
| Day 21 | **M2a EXIT GATE** — demo upload DOCX → chunks pgvector → user accept? |
| Day 28 | Phase 6-7 (search + ask) wire? Phase 8 frontend smoke pass? |

## Key Decisions

| # | Decision | Rationale | Outcome |
|---|---|---|---|
| D1 | **Toàn bộ backend Go → Python FastAPI** | Codebase đồng nhất Python với cocoindex; tránh boundary Go↔Python phức tạp; LiteLLM/asyncpg trưởng thành | — Pending (2026-05-13 pivot) |
| D2 | **CocoIndex v1.0.3+ làm indexing layer** | Incremental diff content-hash + LMDB fingerprint = giải quyết backlog 999.1 sẵn; lineage chunk→source built-in; Rust core production-grade | — Pending |
| D3 | **Postgres pgvector** thay ChromaDB | Bớt 1 service; dùng Postgres sẵn có; pgvector là cocoindex flagship target battle-tested hơn ChromaDB target (recent 2025) | — Pending |
| D4 | **Gỡ Docling hoàn toàn** | Codebase đồng nhất, không phụ thuộc binary Tesseract/Docling model 2GB | ⚠️ Risk regress scanned PDF tiếng Việt + bảng — documented |
| D5 | **LLM answerer giữ hot-swap OpenAI/Gemini** (port sang LiteLLM) | Đã work tốt với tiếng Việt; KHÔNG thêm local model trong M2 | — Pending |
| D6 | **Frontend KHÔNG sửa trong M2** | Risk giảm; URL `/api/*` giữ qua nginx/FastAPI cùng port :8080 | — Pending |
| D7 | **Abandon M1 hoàn toàn** | M1 chưa runtime verify (chưa chạy `make eval-all`), chưa production → mất ít công sức nhất khi pivot bây giờ thay vì sau | — Logged (xem `MILESTONES.md`) |
| D8 | **Eval framework làm lại từ đầu** | `eval/` Go-style queries hardcoded path; M2 dùng Python pytest + queries.jsonl giữ semantic + dataset 10 file gold giữ | — Pending |
| D9 | **Phase numbering reset về 1** (--reset-phase-numbers) | M2 = rewrite full, không tiếp nối M1 logic; archive M1 phases vào `.planning/milestones/v1.0-docling-rag/` | — Logged |
| ~~M1 cũ: Multi-subdomain SPA~~ → Pivot 1: RAG Quality with Docling | (2026-04-28 — đã abandoned) | ❌ Abandoned 2026-05-13 |
| Sử dụng Docling thay vì MarkItDown | (Decision của M1, không còn áp dụng) | ❌ Reverted by D4 |
| Service split Python sidecar chỉ Extract+Chunk | (Decision của M1, không còn áp dụng) | ❌ Reverted by D1 |
| Embedding giữ OpenAI/Gemini hot-swap | Hot-swap đã có, tránh thêm dependency local model | ✓ Carried forward (D5) |
| Granularity: Large (10-15 phases) | M2 scope rất lớn (backend rewrite + RAG rewrite + eval + integration) | — Pending |
| Mode: YOLO | Tài liệu PRD/RAG/Backend Plan rất chi tiết; tin context có sẵn | — Pending |

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
*Last updated: 2026-05-21 after v2.0 milestone close (`/gsd-complete-milestone v2.0`). M2 v2.0 100% COMPLETE — 13 phase / ~75 plan / 38 REQ-ID. Tag `v2.0` (local). Archive `.planning/milestones/v2.0-full-rag-rewrite/`. Pending HUMAN UAT (Phase 9 gate verdict + 8.3 Claude web + 8 docker compose) KHÔNG block close — ghi nhận retrospective. Next: `/gsd-new-milestone v3.0` Multi-Hub Split sau khi user verify v2.0.)*
