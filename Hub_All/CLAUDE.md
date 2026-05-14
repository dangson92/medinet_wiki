# CLAUDE.md — Medinet Wiki (Hub_All)

> Hướng dẫn cho Claude làm việc trong repository này. Toàn bộ giao tiếp BẰNG TIẾNG VIỆT có dấu (xem `~/.claude/CLAUDE.md`). Tên kỹ thuật, REQ-ID, lệnh shell, đường dẫn file giữ nguyên tiếng Anh.

---

## 1. Tổng quan dự án

**Medinet Wiki** là hệ thống quản lý tri thức nội bộ đa-Hub cho Medinet — wiki + RAG + MCP. Codebase này (`Hub_All/`) chứa:

- `api/` — **Python 3.12 · FastAPI 0.136.1 · CocoIndex 1.0.3 · pgvector (pg16) · asyncpg · SQLAlchemy 2.0 async · Alembic · Redis 7 · LiteLLM · PyJWT RS256 · pwdlib Argon2.** Stack duy nhất M2 (in-process cocoindex, LISTEN/NOTIFY trigger).
- `backend/` — **ĐÃ XOÁ 2026-05-14** (TEARDOWN-01 pull-in sớm hơn Phase 8 theo quyết định user). Backup: git tag `m1-go-archived` (commit `72f18ef`). Recover Go source khi cần reference: `git show m1-go-archived:Hub_All/backend/<path>` hoặc `git checkout m1-go-archived -- Hub_All/backend/`.
- `frontend/` — React 19 · Vite 6 · TypeScript 5.8 · Tailwind v4. **KHÔNG sửa trong M2** (D6 — URL `/api/*` giữ nguyên, response envelope `{success, data, error, meta}` shape-identical với Go cũ — Python `api/` phải mimic surface Go cho đến khi frontend rewrite ở milestone tương lai).
- `documents/` — PRD v1.3, RAG Pipeline v3, BACKEND_DEVELOPMENT_PLAN, các prompt design.
- `.planning/` — GSD planning docs (PROJECT, REQUIREMENTS, ROADMAP, STATE, research, codebase map, CONVENTIONS sẽ tạo ở Plan 06).

**Core value (M2):** Ingestion tri thức Medinet phải tái hiện trung thực cấu trúc tài liệu nguồn (heading, bảng, ảnh có chú thích, công thức — OCR tiếng Việt defer v4.0 vì D4) — biến mọi tài liệu y tế / dược / HCNS thành chunk semantic giàu metadata, để top-3 retrieval đạt ≥ 75% trên eval set thật.

> Lịch sử pivot: 2026-04-28 pivot lần 1 (M1 Multi-subdomain SPA → M1 RAG Quality with Docling). 2026-05-13 pivot lần 2 (M1 abandoned → M2 Full RAG Rewrite). M1 archive: `.planning/milestones/v1.0-docling-rag/` (5 phase + 1 backlog 999.1, git history giữ nguyên). Source code service Docling sidecar + eval framework M1 đã xoá khỏi working tree ở Plan 05 — recover được qua git log.

## 2. Milestone hiện tại

**M2 — v2.0 Full RAG Rewrite (CocoIndex + Python FastAPI + pgvector)** · Granularity: large · Mode: YOLO · **10 phase** · **38 REQ-ID v1**.

> Pivot 2026-05-13 (lần 2 trong 15 ngày): M1 cũ (Docling RAG Quality) abandoned — 28 plans code complete nhưng chưa runtime verify. M2 = bộ REQ-ID hoàn toàn mới (CORE-01..05, AUTH-01..06, INGEST-01..08, HUB-01..03, USER-01..03, AUX-01..03, SEARCH-01..04, ASK-01..05, COMPAT-01, TEARDOWN-01, EVAL-01..04, HARD-01..04).

**M2a/M2b split (R3 anti-pivot fatigue mitigation):**

- **M2a (Phase 1-4):** Infra + Schema + Auth + CocoIndex MVP. Có thể ship standalone. Nếu user accept M2a → never pivot.
- **M2b (Phase 5-10):** CRUD + Search + Ask + Frontend smoke + Eval + Hardening. Pivot M2b OK nếu cocoindex critical fail.
- 🚦 **M2a EXIT GATE** giữa Phase 4 và 5 — demo upload DOCX → chunks pgvector → SELECT verify. User accept là điều kiện tiếp tục M2b.

| # | Phase | Trọng tâm |
|---|-------|----------|
| 1 | Infra Skeleton + Demolition + EXIT Criteria | `api/` skeleton + Docker Compose 3-service + xoá M1 + CONVENTIONS.md |
| 2 | Database Schema + Alembic Baseline | 8 table (users/hubs/documents/chunks/audit_logs/usage_events/refresh_tokens/api_keys) + chunks pgvector HNSW 1536-dim |
| 3 | Auth Port + RBAC + Response Envelope | JWT RS256 + Argon2 cross-compat (Go alexedwards ↔ pwdlib) + RBAC + envelope shape-identical |
| 4 | CocoIndex Flow MVP + Document Ingest | cocoindex LISTEN/NOTIFY → extract/chunk/embed/pgvector pipeline in-process |
| 🚦 | **M2a EXIT GATE** | demo upload DOCX → chunks → SELECT verify (R3 mitigation) |
| 5 | Hub + User + Audit + APIKey + Settings CRUD | port CRUD endpoint Go → Python + hub isolation enforce + rate limit |
| 6 | Search API Single + Cross-Hub | direct pgvector + `iterative_scan=relaxed_order` + Redis cache |
| 7 | Ask API + LiteLLM + Citation + Hot-Swap + Usage | LLM answerer citation `[N]` + provider hot-swap OpenAI/Gemini |
| 8 | Frontend E2E Smoke (Go đã xoá sớm 2026-05-14) | React 19 smoke với Python `api/` — `backend/` Go ĐÃ xoá ở TEARDOWN-01 pull-in |
| 9 | Eval Framework + Quality Gate ≥75% top-3 | pytest-based eval + 10 file VN medical thật + gate enforce |
| 10 | Hardening + Observability + Docs | structlog JSON + Prometheus + integration test coverage ≥50% |

**Critical path:** 1 → 2 → 4 → 6 → 7 → 9 → 10. **Auth branch (parallel-able):** 3 → 5 → 8.

## 3. Quy tắc làm việc

### Ngôn ngữ
- Tất cả tài liệu sinh ra (PLAN.md, REVIEW.md, SPEC.md, commit message phần mô tả, PR body) viết tiếng Việt có dấu.
- KHÔNG xen đoạn tiếng Anh dài. Chỉ giữ tiếng Anh cho: tên hàm/biến, lệnh code, REQ-ID, tên thư viện, đường dẫn file, prefix commit (`feat:` `fix:` `chore:` `docs:` `test:`).

### GSD workflow
- Mỗi phase: `/gsd-discuss-phase N` → `/gsd-plan-phase N` → `/gsd-execute-phase N`. Mode YOLO → có thể chạy `/gsd-autonomous` để chuỗi tự động.
- Các tài liệu nguồn sự thật: `.planning/PROJECT.md`, `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md`, `.planning/STATE.md`, `.planning/CONVENTIONS.md` (sẽ tạo ở Plan 06).
- Không sửa REQ-ID đã commit; thay đổi requirement phải qua `/gsd-discuss-phase` hoặc commit có lý do rõ trong message.

### Constraint M2 (Full RAG Rewrite)
- **Stack đồng nhất Python:** KHÔNG mix Go cho code mới. `backend/` Go ĐÃ xoá 2026-05-14 (TEARDOWN-01 pull-in sớm hơn Phase 8 theo user decision); backup git tag `m1-go-archived` — recover qua `git checkout m1-go-archived -- Hub_All/backend/` nếu cần reference khi port CRUD Phase 5/6/7.
- **Stack pin (chống pitfall P19):** `python>=3.11,<3.13` (khuyến nghị 3.12), `fastapi==0.136.1`, `cocoindex==1.0.3`, `pgvector==0.4.2`, `asyncpg==0.30.0`. KHÔNG bump version giữa phase.
- **Postgres image:** `pgvector/pgvector:pg16` (KHÔNG `postgres:16-alpine` — sẽ FAIL `CREATE EXTENSION vector`).
- **Vector store:** pgvector trong Postgres (D3 — bớt 1 service so với ChromaDB/Qdrant, dùng Postgres sẵn có).
- **Embedding dim:** PIN 1536 cho cả OpenAI + Gemini (R1 mitigation pgvector 2000-dim index limit). Cross-dim swap REFUSE 400 (R7).
- **Embedding provider:** OpenAI / Gemini hot-swap qua **LiteLLM** (D5).
- **Indexing:** cocoindex content-hash diff (giải backlog 999.1 incremental re-embed natively — content unchanged → skip re-embed).
- **APP_NAMESPACE:** Cố định `medinet_prod` mọi env (R5 mitigation). Env separation qua database (`medinet_central` vs `medinet_cocoindex`) + container instance khác.
- **CocoIndex db_schema:** `cocoindex` (separate khỏi `public` — P7 mitigation).
- **Middleware order FastAPI:** REVERSED từ Go Gin (P11). Recovery/error_handler add CUỐI (outermost).
- **Frontend D6:** KHÔNG sửa React 19. URL `/api/*` giữ qua FastAPI mount port 8080.
- **Format hỗ trợ:** DOCX/TXT/MD/PDF text-only (D4 — gỡ Docling; scanned PDF → `failed_unsupported`, R4 mitigation). OCR Vietnamese defer v4.0.
- **EXIT criteria E1-E5:** Bake trong `.planning/PROJECT.md`. M2a EXIT GATE giữa Phase 4-5: demo upload DOCX → chunks pgvector → user accept? Reject → STOP, KHÔNG pivot lần 3.

### Code conventions (chi tiết: `.planning/CONVENTIONS.md` — Plan 06)
- **Backend Python `api/` (stack duy nhất M2):** FastAPI factory + lifespan + pydantic-settings + asyncpg/SQLAlchemy 2 async + structlog JSON. Layered architecture (router → service → repository → model). Linting: `ruff` (replaces black+isort+flake8). Type-check: `mypy --strict`. Test: `pytest + httpx AsyncClient + asgi-lifespan + testcontainers`. Package manager: `uv` (Astral, Rust-based). Lệnh: `make install`, `make keys`, `make lint`, `make test`.
- **Backend Go (ARCHIVED):** Source code đã xoá khỏi working tree 2026-05-14. Khi port endpoint Phase 5/6/7 cần check shape Go cũ: `git show m1-go-archived:Hub_All/backend/internal/router/<file>.go` hoặc `git checkout m1-go-archived -- Hub_All/backend/internal/router/` (vào branch tạm rồi discard). KHÔNG khôi phục vào main.
- **Frontend React (UNCHANGED M2):** Context API (`AuthContext`, `ThemeContext`), API client tập trung `frontend/src/services/api.ts`. `npm run dev/build/lint`. Toàn bộ trang quản trị React 19 phải tương thích qua URL `/api/*` + envelope.

### Testing
- M2 critical path mandatory (P9 mitigation): pytest + testcontainers Postgres + Redis ở Phase 10. Coverage ≥50% trên auth/ingest/search/ask/hub isolation (HARD-03). Comprehensive coverage >80% defer v4.0.

### Concerns đáng nhớ (chi tiết: `.planning/research/PITFALLS.md`)
- **P1 / R1 (pgvector dim 2000):** dùng OpenAI `dimensions=1536` API param + verify HNSW build (Phase 1 init-db.sh, Phase 2 schema).
- **P4 / R2 (HNSW post-filter recall):** pgvector ≥ 0.8 + `iterative_scan=relaxed_order` + `ef_search=200` (Phase 6).
- **P5 / R4 (Scanned PDF silent fail):** whitelist `{.docx, .txt, .md, .pdf}` + detect scanned → `failed_unsupported` (Phase 4).
- **P6 / R6 (Argon2 cross-compat):** pin pwdlib params `m=65536, t=1, p=2, saltLen=16, keyLen=32` match Go alexedwards (Phase 3).
- **P8 (Stuck processing):** heartbeat column + watchdog cron (Phase 4).
- **P9 (0% test coverage carry):** mandatory test critical path mỗi phase ship.

## 4. Lệnh GSD nhanh

| Lệnh | Khi dùng |
|------|---------|
| `/gsd-progress` | Xem trạng thái milestone hiện tại |
| `/gsd-plan-phase N` | Lập plan chi tiết cho phase N |
| `/gsd-execute-phase N` | Thực thi plan đã được duyệt |
| `/gsd-verify-work N` | UAT phase N |
| `/gsd-next` | Tự động đi tiếp bước hợp lý kế tiếp |
| `/gsd-debug` | Khi gặp bug khó |
| `/gsd-help` | Bảng đầy đủ |

## 5. Cấu trúc commit

- Phần prefix tiếng Anh chuẩn: `feat:`, `fix:`, `chore:`, `docs:`, `test:`, `refactor:`.
- Phần mô tả tiếng Việt có dấu, ngắn gọn, nói "tại sao" trước "làm gì".
- Mỗi plan trong phase commit atomic — không gộp nhiều plan vào một commit.

---

*Cập nhật: 2026-05-13 (pivot M2 — Full RAG Rewrite) · Project: MEDWIKI · Phase 1 đang execute.*
