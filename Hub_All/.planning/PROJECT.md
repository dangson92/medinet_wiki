# Medinet Wiki — Hub_All

**Mã dự án:** MEDWIKI
**Giai đoạn:** Brownfield · Pivot lần 2 (full rewrite RAG)
**Current Milestone:** **v2.0 — Full RAG Rewrite (CocoIndex + Python FastAPI + pgvector)**
**Defer:** v3.0 = Multi-subdomain SPA · v4.0 = MCP Server + Hardening
**Abandoned:** v1.0 = RAG Quality with Docling (2026-05-13 — xem `MILESTONES.md`)
**Ngày khởi tạo GSD:** 2026-04-28 · **Pivot 2:** 2026-05-13

---

## What This Is

Medinet Wiki là hệ thống quản lý tri thức nội bộ đa-Hub (3 Hub: y tế / dược / HCNS) của Medinet, kết hợp wiki truyền thống với RAG (Retrieval Augmented Generation) — biến mọi tài liệu y tế / dược / HCNS thành chunk semantic giàu metadata để nhân viên tra cứu bằng ngôn ngữ tự nhiên, có citation. Tương lai expose qua MCP cho AI agent.

**Hub_All** là kho chứa toàn bộ source (backend + tất cả các SPA Hub) trước khi tách deploy ở milestone v3.0.

## Core Value

> **Ingestion tri thức của Medinet phải tái hiện trung thực cấu trúc tài liệu nguồn (heading, bảng, ảnh có chú thích, công thức, OCR tiếng Việt cho scanned PDF) — biến mọi tài liệu y tế / dược / HCNS thành chunk semantic giàu metadata, để top-3 retrieval đạt ≥ 75% trên eval set thật.**

Core value không đổi qua các milestone — chỉ cách triển khai thay đổi (Go-native → Docling sidecar → CocoIndex + FastAPI). Khi RAG chất lượng ổn định, các milestone sau (Multi-subdomain SPA, MCP Server, AI Post) mới có giá trị thực tế.

## Current Milestone: v2.0 Full RAG Rewrite (CocoIndex + Python FastAPI + pgvector)

**Goal:** Xóa toàn bộ stack RAG + backend Go hiện hữu, viết lại bằng **Python FastAPI + cocoindex v1.0.3+ + Postgres pgvector**. CocoIndex sở hữu indexing dataflow (extract → chunk → embed → upsert) + incremental diff theo content-hash; FastAPI handle auth (JWT RS256 + Argon2), hub registry, user management, audit log, search, answer. ChromaDB và toàn bộ Go backend bị xóa.

**Target features:**

1. **Python FastAPI backend** thay thế Go — auth (JWT RS256 + Argon2 + refresh token), hub registry, user management, audit log, document CRUD, search/ask API
2. **CocoIndex flow** ingest documents → chunks → pgvector (incremental diff content-hash khi user sửa nội dung — hợp nhất backlog 999.1)
3. **pgvector schema** chunks + metadata + isolation theo `hub_id`
4. **Embedding hot-swap** OpenAI / Gemini qua LiteLLM (transform function trong cocoindex flow)
5. **LLM answerer hot-swap** OpenAI / Gemini + citation `[src:<chunk_id>]` + cross-hub (FastAPI handler)
6. **Frontend tương thích** — React 19 hiện tại KHÔNG sửa (URL `/api/*` giữ nguyên qua nginx hoặc FastAPI mount cùng port `:8080`)
7. **Eval framework mới** đo retrieval + extraction quality trên stack mới (queries.jsonl + dataset 10 file y tế tiếng Việt)
8. **Quality gate** ≥ 75% top-3 trên dataset y tế tiếng Việt

## Requirements

### Validated (đã có trong codebase brownfield — sẽ thay thế hoàn toàn ở M2)

> ⚠️ Các capability dưới đây đang HOẠT ĐỘNG bằng Go nhưng sẽ bị **xóa và viết lại bằng Python** trong M2. Liệt kê ở đây để xác định scope rewrite, KHÔNG phải để giữ.

- **JWT RS256 + Argon2 + refresh token** — port sang `python-jose` + `passlib[argon2]`
- **Multi-Hub theo `hub_id`** — schema Postgres giữ, port repo sang `asyncpg`/SQLAlchemy
- **Provider hot-swap embedding & LLM** runtime qua `PUT /api/rag-config` — port sang FastAPI + LiteLLM
- **Async ingestion qua worker pool** — thay bằng cocoindex's built-in scheduler (Rust core)
- **Async usage logging non-blocking** — port sang asyncio/background task
- **React SPA đầy đủ** (Dashboard, HubRegistry, DocumentIngestion, SyncQueue, UserManagement, AuditLog, APIKeyManagement, CrossHubSearch, Settings, GeminiAssistant, TokenUsage, Profile) — **KHÔNG đổi frontend** (chỉ giữ tương thích URL)
- **Cross-hub search API** — port sang FastAPI

### Active (M2 — Full RAG Rewrite)

Sẽ liệt kê chi tiết trong `REQUIREMENTS.md`. Tóm tắt 8 nhóm:

- [ ] **CORE** — FastAPI app skeleton, Postgres schema migrate (drop chunks Chroma-only fields, add pgvector cols), Docker Compose mới (postgres + redis + python-api, bỏ chromadb)
- [ ] **AUTH** — JWT RS256 + Argon2 + login/refresh/me/logout, RBAC middleware
- [ ] **HUB** — hub registry CRUD, isolation theo `hub_id` trên mọi endpoint
- [ ] **USER** — user management CRUD + RBAC
- [ ] **INGEST** — cocoindex flow: source (file_store) → extract (TBD parser, OCR tiếng Việt = open question) → chunk → embed → pgvector
- [ ] **SEARCH** — `/api/search` hybrid query (vector + metadata filter), top-k pgvector
- [ ] **ASK** — `/api/ask` LLM answerer với citation + cross-hub option
- [ ] **EVAL** — eval framework Python mới + queries.jsonl + dataset 10 file + gate ≥75% top-3

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

**Codebase hiện tại sẽ bị xóa toàn phần trong M2 Phase 1:**
- `Hub_All/backend/` (toàn bộ Go) sau khi port logic
- `Hub_All/docling-pipeline/` (Python sidecar Docling cũ)
- `Hub_All/eval/` (eval scripts cũ — viết lại từ đầu)

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
*Last updated: 2026-05-13 (Pivot lần 2 — M1 Docling abandoned, M2 Full RAG Rewrite với CocoIndex + Python FastAPI + pgvector khởi tạo)*
