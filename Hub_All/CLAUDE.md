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

> **M2 — v2.0 Full RAG Rewrite ✅ COMPLETE** (10/10 phase done — xem `.planning/STATE.md`) · Granularity: large · Mode: YOLO · **10 phase** · **38 REQ-ID v1**.

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

## 6. M2 closeout — Pivot tới v3.0 Multi-Hub Split

M2 hoàn tất toàn bộ 38 REQ-ID v1 trên 10 phase (xem `.planning/STATE.md`).
Critical path test ≥50% coverage (HARD-03 thực đo 57.75%), structlog JSON +
Prometheus `/metrics` endpoint (HARD-01 Plan 10-01 + HARD-02 Plan 10-02),
README + DEPLOY + 2 .env.example đầy đủ (HARD-04 Plan 10-05). MCP CRIT-01
(CORS sensitive split) đã đóng — Phase 10 Plan 10-04 ship MultiPolicyCORSMiddleware
tách metadata wildcard (RFC 8414 §3.1) vs sensitive whitelist (claude.ai +
Inspector + 2 localhost dev). Backend Go cũ ARCHIVED qua git tag `m1-go-archived`
(2026-05-14 TEARDOWN-01 pull-in) — stack hiện tại Python ONLY.

**Next milestone:** **v3.0 — Multi-Hub Split** (subpath routing `wiki.domain.com/<hub>`,
multi-DB Postgres riêng cùng instance, cocoindex flow per-hub đẩy chunks+vector
lên hub tổng làm read replica). Architectural decision LOCKED 2026-05-21:

- **D-V3-01:** DB topology = Postgres database riêng cùng instance (`medinet_central` +
  `medinet_hub_yte` + `medinet_hub_duoc` + `medinet_hub_hcns`)
- **D-V3-02:** Dataflow hub con → hub tổng = chunks + vector (denormalized read
  replica, sync 1 chiều — KHÔNG re-embed ở hub tổng)
- **D-V3-03:** Scoping = milestone-level (KHÔNG nhét vào M2 dưới dạng phase đơn lẻ)
- **D-V3-04:** M2 closeout = bắt buộc trước v3.0 (Phase 10 done là tiền đề)

**Trigger v3.0:** `/gsd-new-milestone v3.0` sau khi Phase 10 ship full (HARD-04 +
Plan 10-06 CI workflow) + human UAT pass + retrospective ghi nhận.

**Reference:** `.planning/seeds/v3.0-multi-hub-split.md` (7 phase đề xuất ~35 plan,
4 risk register R-V3-1..4, 4 EXIT criteria E-V3-1..4 preview).

**Open question chốt ở `/gsd-discuss-milestone v3.0`:**

- **GA-V3-A** Auth SSO design — JWT keypair share giữa central + sub-hubs qua JWKS endpoint từ hub tổng? Refresh token blacklist Redis chung?
- **GA-V3-B** System settings sync — `rag_config` / `api_keys` / `hub_registry` ở tổng, hub con đọc qua HTTP pull on-demand vs push webhook?
- **GA-V3-C** Reverse proxy + frontend prefix detect — Caddy strip `/<hub>` prefix? Frontend 1 build dùng chung detect prefix qua `window.location.pathname.split('/')[1]` vs build per-hub `VITE_HUB_NAME=yte`? D6 ("KHÔNG sửa frontend") expire chính thức ở v3.0-05.
- **GA-V3-D** Migration data từ `medinet_central` cũ split sang DB hub con — `pg_dump` per `WHERE hub_id` HOẶC snapshot + replay cocoindex flow rebuild từ `file_store`?

### v3.0 progress (cập nhật khi mỗi Phase ship)

| Phase | Status | Plan count | Date | REQ-ID |
|-------|--------|------------|------|--------|
| 1 — Multi-DB Topology + Per-hub Alembic | ✅ DONE | 5 plan | 2026-05-21 | TOPO-01..04 (4) |
| 2 — Hub-con Codebase Factor | ✅ DONE | 5 plan | 2026-05-22 | FACTOR-01..04 (4 — FACTOR-04 added 2026-05-22 Plan 02-05) |
| 3 — Auth SSO + hub_ids trong JWT | 📋 Next | — | — | SSO-01..04 |
| 4 — Cross-hub Data Sync | 📋 | — | — | SYNC-01..05 |
| 5 — Reverse Proxy + Frontend Subpath | 📋 | — | — | PROXY-01..04 |
| 6 — System Settings Sync | 📋 | — | — | SETTINGS-01..04 |
| 7 — Migration + Smoke E2E | 📋 | — | — | MIGRATE-01..05 |

**🚦 v3.0-a EXIT GATE** giữa Phase 3 và Phase 4 — demo 1 hub con (yte) + central + JWT SSO + golden path PASS → user accept là điều kiện tiếp tục v3.0-b (Phase 4-7).

### Phase 2 pattern (FACTOR-01..03 — 2026-05-22)

1 codebase deploy được nhiều lần với env `HUB_NAME=<central|yte|duoc|hcns>`:

- **`api/app/main.py::create_app()`** — factory no-arg đọc `settings.hub_name`, conditional mount:
  - **7 router universal** (mount mọi process): `auth_router`, `documents_router`, `profile_router`, `search_router`, `ask_router`, `usage_router`, `ai_chat_router`.
  - **9 router central-only** (chỉ mount khi `settings.hub_name == "central"`): `hubs_router`, `users_router`, `api_keys_router`, `audit_logs_router`, `rag_config_router`, `system_settings_router`, `sync_router`, `mcp_oauth_router`, `mcp_oauth_internal_router`.
- **`docker-compose.yml`** — 4 service dedicated FastAPI:
  - `python-api-central` (HUB_NAME=central, DB `medinet_central`, port host 8180 — M2 backward-compat).
  - `python-api-yte` (HUB_NAME=yte, DB `medinet_hub_yte`, port host 8181).
  - `python-api-duoc` (HUB_NAME=duoc, DB `medinet_hub_duoc`, port host 8182).
  - `python-api-hcns` (HUB_NAME=hcns, DB `medinet_hub_hcns`, port host 8183).
  - YAML anchor `x-api-template: &api-template` dedupe shared config (build / env_file / volumes keys ro / depends_on / network). Mỗi service inherit qua `<<: *api-template`.
  - Cocoindex LMDB volume per-hub (`medinet_cocoindex_<hub>`) — 1.0.3 Environment singleton isolation.
  - `mcp_service.MCP_API_BASE_URL` re-point `http://python-api-central:8080` (KHÔNG fan-out — LOCKED D-V3-02).
- **Endpoint contract:**
  - Hub con expose **12 endpoint hub-scoped specific** (FACTOR-03 — implementation count; ROADMAP/REQUIREMENTS label "10 collective endpoint group" gộp `/api/auth/*` + `/api/profile` + `/api/documents` thành nhóm): `/api/auth/{login,refresh,logout,me}`, `/api/profile` (GET/PATCH), `/api/documents` (POST/GET/DELETE), `/api/search`, `/api/ask`, `/api/usage`.
  - Hub con STRIP **8 endpoint central-only** (FACTOR-02) → 404 envelope `{success:false, data:null, error:{code, message}, meta:null}` (KHÔNG 403 — endpoint không exist mới đúng strip semantic).
- **Cross-hub alias defer:** `/api/ask/cross-hub` + `/api/search/answer` vẫn mount universal ở Phase 2 (router universal mount nguyên). Phase 4 SYNC-03 sẽ tách hoặc dùng dependency reject. Hub con runtime endpoint cross-hub trả 500/empty (DB không có data hub khác — KHÔNG leak vì E-V3-3 isolation Phase 1).
- **Phase 1 Settings._enforce_hub_dsn_match validator** carry forward — boot-time fail-fast nếu HUB_NAME ↔ DSN suffix mismatch (E-V3-3 enforce).

**Reference:**
- `.planning/phases/02-hub-con-codebase-factor/02-CONTEXT.md` — 9 D-V3-Phase2 decision LOCKED 2026-05-22.
- `.planning/phases/02-hub-con-codebase-factor/02-{01..05}-PLAN.md` — implementation chi tiết 5 plan.
- `.planning/phases/02-hub-con-codebase-factor/02-{01..05}-SUMMARY.md` — deliverable + commit + test count per plan.

### Phase 2 FACTOR-04 dynamic hub registration (added 2026-05-22 — user direction B)

Operator thêm hub mới không sửa code:

- **`Settings.hub_name`** đổi `Literal[4]` → `str` + regex `^[a-z][a-z0-9_]{0,15}$` + reserved blacklist 6 name (`postgres`, `cocoindex`, `template0`, `template1`, `public`, `medinet`) ở `RESERVED_HUB_NAMES` constant module-level `api/app/config.py`.
- **`make hub-add HUB=<name> [PORT=<port>]`** → `scripts/hub-add.sh` 7-step pipeline: regex validate + reserved blacklist + duplicate detect + auto-detect port (max+1) + call `hub-init.sh` (DB layer Phase 1) + sed substitute `docker-compose.override.yml.template` → append `docker-compose.override.yml` (gitignored, operator-local) + `docker compose config --quiet` post-write verify merge.
- **Auto-detect port** = max ports hiện hữu + 1 trong base + override (scan regex `"NNNN:8080"`), fallback 8184 nếu base parse fail. User truyền explicit `PORT=<port>` thì skip auto-detect; validate range 1024-65535 + port conflict check.
- **Quick start operator:** xem `Hub_All/README.md` section "Add a new hub (dynamic registration — FACTOR-04 Plan 02-05)".
- **Hub registry source-of-truth defer Phase 6 SETTINGS-04** — long-term sẽ ship `hub_registry` table ở `medinet_central`; central admin CRUD; hub con đọc TTL cache. Plan 02-05 chỉ validate format Settings + sinh compose block.

Reference: `.planning/phases/02-hub-con-codebase-factor/02-05-PLAN.md`.

---

*Cập nhật: 2026-05-22 (Phase 2 DONE — FACTOR-01..04 ship 5 plan; Plan 02-05 FACTOR-04 dynamic hub registration). Project: MEDWIKI. M2 v2.0 done; v3.0 Multi-Hub Split — Phase 1+2 DONE (10/~32 plan ≈ 31%), Next: `/gsd-discuss-phase 3` Auth SSO.*
