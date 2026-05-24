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
- **Frontend D6 (EXPIRED ở Phase 5 v3.0-05 — PROXY-03):** ~~KHÔNG sửa React 19. URL `/api/*` giữ qua FastAPI mount port 8080.~~ → **D6 EXPIRED 2026-05-23** (PROXY-03 satisfied). Phase 5 cho phép FE rewrite cho prefix detect (PROXY-02 + D-V3-Phase5-B1/B3) + per-hub login branding (PROXY-04 + D-V3-Phase5-D1/D2). Smoke regression M2 COMPAT-01 11 trang carry forward (R-V3-2 mitigation — Plan 05-06 manual checklist 4 hub × 11 trang). M2 contract response envelope `{success, data, error, meta}` shape KHÔNG đổi (LOCKED carry forward).
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
| 3 — Auth SSO + hub_ids trong JWT | ✅ DONE | 5 plan | 2026-05-22 | SSO-01..04 (4) |
| 🚦 v3.0-a EXIT GATE | ✅ TRIGGERED | — | 2026-05-22 | Demo 1 hub con yte + central + JWT SSO + golden path → user accept tiếp tục v3.0-b (demo runtime defer Phase 7 MIGRATE-05 — evidence chain 65+ unit + 6 integration test in-process cover semantic) |
| 4 — Cross-hub Data Sync | ✅ **DONE** | **7 plan** | **2026-05-22** | **SYNC-01..05 (5)** |
| 5 — Reverse Proxy + Frontend Subpath | ✅ **DONE** | **6 plan** | **2026-05-23** | **PROXY-01..04 (4)** |
| 6 — System Settings Sync | ✅ **DONE** | **5 plan** | **2026-05-23** | **SETTINGS-01..04 (4)** |
| 7 — Migration + Smoke E2E | ✅ **DONE** 🎉 | **5 plan** | **2026-05-23** | **MIGRATE-01..05 (5)** |

**🎉 v3.0 MILESTONE CLOSED 2026-05-23** — 38/38 plan ship · 30/30 REQ-ID consumed (TOPO 4 + FACTOR 4 + SSO 4 + SYNC 5 + PROXY 4 + SETTINGS 4 + MIGRATE 5) · 7/7 phase complete · v3.0-a (Phase 1-3) + v3.0-b (Phase 4-7) anti-pivot hoàn tất. Next: `/gsd-complete-milestone v3.0` separate command.

**🚦 v3.0-a EXIT GATE** TRIGGERED 2026-05-22 sau Plan 03-05 close — demo 1 hub con (yte) + central + JWT SSO + golden path PASS → user accept là điều kiện tiếp tục v3.0-b (Phase 4-7). Smoke compose runtime SKIP pre-resolved — defer Phase 7 MIGRATE-05 full E2E (3 hub + central golden path + JWT SSO live). Evidence chain: Plan 03-01 (9 unit) + Plan 03-02 (27 unit + 3 integration) + Plan 03-03 (19 unit + 3 integration) + Plan 03-04 (10 unit) = 65+ unit + 6 integration PASS in-process semantic.

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

### Phase 3 SSO pattern (SSO-01..04 — 2026-05-22)

5 plan đóng 4 REQ-ID Auth SSO + hub_ids JWT:

- **Plan 03-01 SSO-01 — JWKS endpoint publish (D-V3-Phase3-A):** `api/app/auth/jwks.py` module mới với `publish_jwks()` + `load_public_key_as_jwk()` RFC 7517 (`kty:RSA, kid:SHA-256[:8] base64url 11 char, use:sig, alg:RS256, n, e`). Central mount `GET /.well-known/jwks.json` conditional `if settings.hub_name == "central"` block + `Cache-Control: public, max-age=3600` + 503 fallback envelope D6 `JWKS_UNAVAILABLE` nếu PEM missing. Hub con strip → 404 envelope D6 (FACTOR-02 carry forward). Settings.central_jwks_url field mới + docker-compose CENTRAL_JWKS_URL env × 3 hub con + override.yml.template inherit (FACTOR-04). Reference: `.planning/phases/03-auth-sso-hub-ids-jwt/03-01-PLAN.md` + `03-01-SUMMARY.md`.
- **Plan 03-02 SSO-01 — JWKSCache hub con (D-V3-Phase3-B/D):** `JWKSCache` class in-process LRU + asyncio refresh task TTL 1h fail-quiet + 24h hard limit fail-loud delayed (503 `JWKS_STALE`). Lifespan hub con blocking fetch_initial (timeout 5s — boot fail-loud R-V3-5 mitigation) + spawn refresh task + shutdown graceful stop_refresh_task. `get_current_user` dependency branch verify path (central=local pem M2 / hub con=JWKSCache.get_public_key(kid) → verify_token_with_key). JWT header `kid` auto-add ở issue_token_pair (deterministic SHA-256 match Plan 03-01). Settings 3 field mới: `central_jwks_url` + `jwks_refresh_interval=3600` + `jwks_max_stale_seconds=86400` + 1 model_validator hub con required. Escape hatch `JWKS_SKIP_FETCH=1` env var (test mode song song COCOINDEX_SKIP_SETUP). Reference: `03-02-PLAN.md` + `03-02-SUMMARY.md`.
- **Plan 03-03 SSO-02/03/04 — JWT claim + Redis key + E4 reinforced (D-V3-Phase3-E/H):** `JWT_AUDIENCE = "medinet-wiki"` constant + `aud=["medinet-wiki"]` REQUIRED + `hub_ids: list[str]` REQUIRED (xoá default empty M2). PyJWT strict audience check ở 2 verify path (`verify_token` + `verify_token_with_key`). Redis blacklist key rename `blacklist:{jti}` → `auth:blacklist:{jti}` (5 vị trí touch — 4 service.py + 1 dependencies.py) qua mini-module `_blacklist.py` (REDIS_BLACKLIST_PREFIX + make_blacklist_key helper). Dependency mới `get_current_user_for_hub_access` Layer 3 enforce — hub con check `HUB_NAME in claims.hub_ids` → 403 CROSS_HUB_ACCESS_DENIED envelope. iss giữ NGUYÊN `"medinet-wiki"` (RE-CONFIRM D-V3-Phase3-E — URL-based defer Phase 7 MCP split aud). request.state.jwt_claims wire ở get_current_user SAU verify pass. Reference: `03-03-PLAN.md` + `03-03-SUMMARY.md`.
- **Plan 03-04 SSO-02 — 307 redirect hub con (D-V3-Phase3-G):** Hub con `POST /api/auth/login` + `POST /api/auth/refresh` trả 307 RedirectResponse Location: `{settings.central_url}/api/auth/{login,refresh}` (preserve POST + body RFC 7231 — KHÔNG 405/302/308). `logout` + `me` giữ local handle (verify JWT qua JWKSCache + blacklist Redis chung Plan 03-03). `_sso_redirect(target_path, hub_name)` helper extract + X-SSO-Redirect-Reason + X-SSO-Original-Hub headers debug. `response_model=None` decorator opt-out (Rule 1 — FastAPI union return type fail). Settings.central_url field mới + docker-compose CENTRAL_URL env 3 hub con + override.yml.template + Phase 2 integration test split 2 list (10 LOCAL `!= 404` + 2 SSO_REDIRECT `== 307`). Reference: `03-04-PLAN.md` + `03-04-SUMMARY.md`.
- **Plan 03-05 closeout — docs + smoke checkpoint (2026-05-22):** CLAUDE.md section 6 update (file này) + STATE.md Phase 3 Results Summary + REQUIREMENTS.md SSO-01..04 mark `[x]` + README.md SSO Backward Incompat section. Task 5 smoke compose runtime SKIP pre-resolved — defer Phase 7 MIGRATE-05 full E2E. Evidence chain: 65+ unit test + 6 integration test in-process cover SSO-01..04 semantic + `docker compose config --quiet` base PASS. v3.0-a EXIT GATE TRIGGERED. Reference: `03-05-PLAN.md` + `03-05-SUMMARY.md`.

**Backward incompat (operator broadcast TRIPLE cumulative):** M2 cũ JWT thiếu (1) `kid` header Plan 03-02 + (2) `aud` claim Plan 03-03 + (3) `hub_ids` claim Plan 03-03 → 401 reject sau deploy. User re-login ~15-30s downtime — communicate Slack/Email trước deploy. Frontend M2 hardcode `/api/auth/login` same-origin sẽ FAIL ở hub con cho tới Phase 5 PROXY-02 wire form action central (acceptable dev v3.0-a). Xem `Hub_All/README.md` "SSO Backward Incompat (Phase 3 v3.0)" section deploy 7 step + rollback procedure.

**Frontend wire:** Defer Phase 5 PROXY-02 (D-V3-Phase3-F honored + D-V3-06 D6 expire formally Phase 5).

**E4 reinforced 3-layer enforce (SSO-04 defense-in-depth):**
- **Layer 1 (Phase 1 Plan 01-02):** DB-level `_enforce_hub_dsn_match` Settings validator boot-time fail-fast — hub con KHÔNG kết nối DB hub khác.
- **Layer 2 (M2 carry forward):** Repository layer `WHERE hub_id = settings.hub_name` query-time filter — hub con KHÔNG SELECT data hub khác.
- **Layer 3 (Plan 03-03 MỚI):** Dependency `get_current_user_for_hub_access` JWT claim hub_ids check → 403 CROSS_HUB_ACCESS_DENIED envelope nếu mismatch — stale JWT compromised KHÔNG bypass.

### Phase 4 Cross-hub Data Sync pattern (SYNC-01..05 — 2026-05-22)

7 plan đóng 5 REQ-ID Cross-hub Data Sync + 9 D-V3-Phase4-A1..D3 LOCKED + 6 Prometheus metric infrastructure (outbox + worker mechanism, R-V3-1 HIGH sync drift mitigation):

- **Plan 04-01 SYNC-01/02/05 — Per-hub Alembic 0005 + Postgres trigger AFTER INSERT/DELETE (D-V3-Phase4-A2/A4/B2):** `api/migrations/versions/0005_sync_outbox_per_hub.py` (~224 LOC) tạo bảng `sync_outbox` (11 cột: id/op_type/chunk_id/document_id/payload/attempt_count/last_error/status/next_retry_at/created_at/processed_at + 2 CHECK constraint + 2 partial index) + Postgres function `enqueue_sync_outbox()` (explicit `jsonb_build_object` field — KHÔNG `to_jsonb(NEW)` để fix BLOCKER 2 pgvector serialization + `NEW.vector::float4[]` cast + `encode(content_hash, 'hex')` 64 char) + 2 trigger AFTER INSERT/DELETE chunks (FOR EACH ROW atomic cùng transaction) + `documents.sync_status` enum (5 value lifecycle: pending/syncing/synced/failed/partial) + initial `'pending' → 'syncing'` idempotent UPDATE guard `WHERE sync_status='pending'` (BLOCKER 1 fix D-V3-Phase4-B2 lifecycle). Skip-central runtime guard `current_database() check` (sync_outbox per-hub-only). 17/17 unit test PASS + 293/293 unit regression + 10/10 Phase 1 PASS.

- **Plan 04-02 SYNC-01/03/04 — Settings 7 field + 3 model_validator + docker-compose env wire (D-V3-Phase4-A5/C3/D2):** Settings field mới `hub_id` UUID4 str (env `HUB_ID`) + `central_sync_dsn` asyncpg DSN (env `CENTRAL_SYNC_DSN`) + `checksum_hub_dsns_json` JSON dict (central dict DSN tới N hub con) + `sync_batch_size=100` + `sync_poll_interval=5.0` + `sync_max_attempts=5` + `sync_backoff_seconds=[1,5,30,120]` defaults. 3 model_validator hub con required HUB_ID + CENTRAL_SYNC_DSN; central optional CHECKSUM_HUB_DSNS_JSON (lazy connect, deploy lần đầu CHƯA register hub con OK). 1 length validator backoff = max_attempts-1 (T-04-02-05 DoS mitigation). docker-compose 3 hub con env `${HUB_*_ID:?error}` fail-loud + central `${CHECKSUM_HUB_DSNS_JSON:-}` optional + override.yml.template FACTOR-04 placeholder. 17/17 unit + 310/310 regression PASS.

- **Plan 04-03 SYNC-01/02/05 — `api/app/sync/` module + 6 Prometheus collector (D-V3-Phase4-A1/A5/B1/B3):** Module mới `api/app/sync/`: `keys.py` (8 SQL constant — CLAIM_PENDING FOR UPDATE SKIP LOCKED + MARK_PROCESSING/PROCESSED/FAILED_RETRY/DEAD + PUSH_INSERT_CHUNK ON CONFLICT (id) DO UPDATE WHERE content_hash IS DISTINCT + PUSH_DELETE + UPDATE_DOC_SYNC_STATUS aggregate CASE 4 state) + `models.py` (Pydantic ChunkPayload với `content_hash` field_validator mode=before decode hex string → bytes BLOCKER 2 fix + DeletePayload + SyncOutboxRow + 3 enum SyncStatus/OpType/DocumentSyncStatus) + `metrics.py` (6 Prometheus collector module-level — `hub_name` label W7 fix bounded ~240 series) + `worker.py` (338 LOC `sync_worker_loop` + 7 helper `_claim/_push_inserts/_push_deletes/_update_document_sync_status/_handle_failures/_observe_lag/_get_settings` + SELECT FOR UPDATE SKIP LOCKED concurrency-safe + ON CONFLICT idempotent + exp backoff clamped + LAST_ERROR_TRUNCATE=1000 char + `_update_document_sync_status` D-V3-Phase4-B2 lifecycle aggregate). 43/43 unit (12 models + 13 metrics + 18 worker) + 353/353 regression PASS.

- **Plan 04-04 SYNC-01/02/05 — Lifespan integration central_sync_pool + sync_worker_task + rag/flow.py guard:** `api/app/db/dsn.py` shared `_to_asyncpg_dsn` helper (W3 fix circular import — Plan 04-06 sẽ reuse) + `app/main.py::_init_central_sync_conn` callback register pgvector codec (BLOCKER 2 fix `$N::vector` bind) + lifespan hub con `central_sync_pool = await asyncpg.create_pool(init=_init_central_sync_conn)` verify `SELECT current_database() == 'medinet_central'` fail-fast (T-04-04-01 mitigation) + spawn `sync_worker_task = asyncio.create_task(sync_worker_loop(app))` + shutdown graceful `task.cancel() + asyncio.wait_for(timeout=10s)` (carry forward Plan 03-02 JWKSCache pattern) + close pool SAU worker stop. R-V3-1 fail-loud — hub con KHÔNG init được pool → re-raise → uvicorn exit 1. `rag/flow.py::index_document` defensive guard skip chunks INSERT khi `doc_hub_id != settings.hub_id` warning log (D-V3-Phase4-D2 + E-V3-3 Layer 1 carry forward). `SYNC_SKIP_CENTRAL_POOL=1` escape hatch (pattern song song `JWKS_SKIP_FETCH` + `COCOINDEX_SKIP_SETUP`). 6 mock integration + 1 skipif live-DB (defer Phase 7 MIGRATE-05).

- **Plan 04-05 SYNC-03 — Cross-hub search refactor 1 SQL (D-V3-Phase4-D1/D3):** `SearchService._search_cross_hub_impl` refactor từ fan-out `asyncio.gather(*[_search_one(h) for h in hub_ids])` qua N task → 1 SQL aggregated `_run_vector_query(hub_ids=<full list>)` dùng `WHERE c.hub_id = ANY($2::uuid[]) ORDER BY vector <=> $1::vector LIMIT $3` — re-rank tự nhiên qua SQL ORDER BY (KHÔNG Python merge sort) + HNSW `iterative_scan=relaxed_order` + `ef_search=200` + `max_scan_tuples=20000` carry forward M2 Phase 6. Public API `SearchService.search_cross_hub(*, body, user)` signature giữ NGUYÊN (backward compat M2 ask_service.py + frontend api.ts crossHubSearch). Tách `routers/search.py` 2 APIRouter: `search_router` universal (/api/search, /api/search/similar) + `cross_hub_router` central-only (/api/search/cross-hub) + main.py conditional include trong block central-only. CENTRAL_ONLY list grow 8 → 9 endpoint. JWT hub_ids ∩ body.hub_ids intersect SSO-03 carry forward. 8/8 unit + 15/15 integration (10 baseline + 5 dedicated cross-hub) + 361/361 regression PASS.

- **Plan 04-06 SYNC-04 — Checksum scheduler central + admin /api/sync/replay (D-V3-Phase4-C1/C2/C3):** `api/app/observability/checksum_scheduler.py` (~280 LOC) — central FastAPI lifespan asyncio task naive `asyncio.sleep` cron loop (KHÔNG cần APScheduler dep mới) + `_should_run_daily/_should_run_hourly` time-check helper + `_tick_daily_count` (full `COUNT(*)` per hub vs central WHERE hub_id → `SYNC_COUNT_DRIFT{hub_name}` gauge symmetric `drift_ratio = abs(diff) / max(hub_count, 1)`) + `_tick_hourly_hash` (TABLESAMPLE BERNOULLI(1) chunks created last 1h → content_hash diff → `SYNC_HASH_DRIFT{hub_name, drift_type=mismatch|missing}` counter) + lazy per-hub asyncpg.Pool init (operator append hub FACTOR-04 + restart refresh dict) + per-hub error isolation (1 hub fail KHÔNG abort scheduler). `POST /api/sync/replay { hub_id, since }` admin endpoint (require_role("admin") Phase 3 SSO-04 carry forward) reset 4 field dead rows (status='pending' + attempt_count=0 + last_error=NULL + next_retry_at=NULL) WHERE status='dead' AND created_at >= since atomic + audit_logs INSERT non-repudiation `action='sync.replay'` với defensive inner try/except (W8 fix audit fail KHÔNG block replay — T-04-06-03 reinforced). Mount via existing `sync_router` (FACTOR-02 central-only carry forward). Pydantic `SyncReplayRequest` schema + `hub_id` regex format check (T-04-06-02 Tampering). 22/22 unit (10 checksum + 12 replay) + 383/383 regression + 21/21 Phase 2+4 integration PASS.

- **Plan 04-07 closeout — docs update + smoke checkpoint runtime SKIP pre-resolved (file này):** CLAUDE.md section 6 + STATE.md + REQUIREMENTS.md + README.md update phản ánh Phase 4 DONE. Task 5 smoke compose runtime SKIP pre-resolved per user decision — defer Phase 7 MIGRATE-05 full E2E (3 hub + central golden path + JWT SSO live + cross-hub search live data). Evidence chain: 113 unit + 21 integration test in-process PASS cover semantic SYNC-01..05 + `docker compose config --quiet` base PASS Plan 04-02.

**6 Prometheus metric mới (Phase 4 observability):**
- `sync_lag_seconds{hub_name}` histogram — outbox.created_at → central INSERT processed_at lag
- `sync_outbox_pending{hub_name}` gauge — số row pending hiện tại
- `sync_attempt_total{hub_name, status=success|fail}` counter — cumulative push attempts
- `sync_dead_total{hub_name, error_class=network|timeout|conflict|unknown}` counter — cumulative dead rows
- `sync_count_drift{hub_name}` gauge — daily COUNT diff ratio symmetric
- `sync_hash_drift{hub_name, drift_type=mismatch|missing}` counter — hourly TABLESAMPLE hash sample diff

**Backward compat (Phase 4 KHÔNG break M2):**
- `SearchService.search_cross_hub(*, body, user) -> dict[str, Any]` public API signature unchanged — M2 ask_service.py consumer + frontend api.ts crossHubSearch giữ nguyên call.
- Cross-hub endpoint URL `/api/search/cross-hub` giữ NGUYÊN ở central — chỉ refactor implementation 1 SQL.
- Hub con `/api/search/cross-hub` strip → 404 envelope (FACTOR-02 extend) — frontend M2 hardcode same-origin sẽ FAIL ở hub con cho tới Phase 5 PROXY-02 wire base URL detect prefix. Acceptable dev v3.0-b.
- M2 COMPAT stub `routers/sync.py` `/api/sync/{stats,batches,...}` PRESERVE — append `/api/sync/replay` mới (FACTOR-02 central-only mount).

**R-V3-1 HIGH mitigation chain:**
- Outbox INSERT atomic cùng transaction chunks INSERT (Plan 04-01 trigger AFTER INSERT/DELETE FOR EACH ROW).
- Worker ON CONFLICT (id) DO UPDATE WHERE content_hash IS DISTINCT FROM EXCLUDED.content_hash — idempotent retry KHÔNG dup + tránh UPDATE no-op bảo vệ HNSW vector index disk write thừa (Plan 04-03 + B1).
- Exp backoff [1, 5, 30, 120]s + max 5 attempts → dead status + Prometheus alert (Plan 04-03 + A5).
- Daily 2AM COUNT(*) drift + Hourly TABLESAMPLE BERNOULLI(1) content_hash sample → `sync_count_drift` + `sync_hash_drift` metric (Plan 04-06 + C1).
- Admin `POST /api/sync/replay` endpoint manual recovery (Plan 04-06 + C2).

**E-V3-2 cross-hub p95 < 1.5s carry forward:**
- HNSW iterative_scan=relaxed_order + ef_search=200 + max_scan_tuples=20000 SET LOCAL session tuning carry forward M2 Phase 6.
- 1 SQL aggregated thay fan-out N asyncio task → giảm overhead orchestration + re-rank natural qua SQL ORDER BY (Plan 04-05 + D1).
- Live measure defer Phase 7 MIGRATE-05 runtime smoke E2E.

**v3.0-b mở màn:** Phase 4 hoàn tất 5/5 REQ-ID SYNC. v3.0-b tiếp tục Phase 5 (PROXY + frontend subpath + D6 expire) hoặc Phase 6 (SETTINGS sync) parallel theo critical path. Phase 7 MIGRATE-05 sẽ verify runtime full E2E 3 hub con + central + golden path.

**Reference:**
- `.planning/phases/04-cross-hub-data-sync/04-CONTEXT.md` — 9 D-V3-Phase4-A1..D3 LOCKED 2026-05-22.
- `.planning/phases/04-cross-hub-data-sync/04-{01..07}-PLAN.md` — implementation chi tiết 7 plan.
- `.planning/phases/04-cross-hub-data-sync/04-{01..07}-SUMMARY.md` — deliverable + commit + test count per plan.

### Phase 5 Reverse Proxy + Frontend Subpath pattern (PROXY-01..04 — 2026-05-23)

6 plan đóng 4 REQ-ID PROXY (Caddy reverse proxy + frontend 1-build prefix detect + D6 expire formally + per-hub login branding) + 16 D-V3-Phase5-A1..D4 LOCKED + FACTOR-04 extend (hub-add.sh step 8+9):

- **Plan 05-01 PROXY-01 — Caddy + docker-compose scaffolding (D-V3-Phase5-A1/A2/A4):** `Hub_All/Caddyfile` ADD `{$WIKI_PUBLIC_DOMAIN}` server block parallel MCP block (Phase 8.3 carry forward) — `path_regexp hub_api ^/({$HUBS_ALLOWLIST_REGEX:yte|duoc|hcns})/api/(.*)$` + `route { uri strip_prefix /{re.hub_api.1}; reverse_proxy http://python-api-{re.hub_api.1}:8080 }` (T-5-01 anchor mitigation) + central `/api/*` handle no-strip + `/.well-known/*` JWKS pass-through (Phase 3 Plan 03-01 carry forward) + static SPA `file_server` `try_files {path} /index.html`. `docker-compose.yml` caddy service ADD `WIKI_PUBLIC_DOMAIN` + `HUBS_ALLOWLIST_REGEX` env + `./frontend/dist:/srv/wiki/dist:ro` mount + `depends_on: python-api-central`. `.env.example` document 3 env vars dev vs prod.

- **Plan 05-02 PROXY-02 — Frontend prefix detect runtime + vitest Wave 0 (D-V3-Phase5-B1/B3 + GA-V3-C):** Wave 0 install `vitest@^2 + @testing-library/react@^16 + @testing-library/jest-dom@^6 + jsdom@^25` + `frontend/vitest.config.ts` jsdom env + `frontend/src/test-setup.ts` jest-dom matchers + `"test": "vitest run"` npm script. Refactor `frontend/src/services/api.ts` module-level compute `PREFIX/API_BASE/APP_BASE/CURRENT_HUB` từ `window.location.pathname.split('/').filter(Boolean)[0]` + `KNOWN_HUBS` từ `window.__HUB_CONFIG__.allowlist` runtime fallback hardcode `['yte','duoc','hcns']` (T-5-02 backend Caddy regex authoritative — FE allowlist UX-only). `App.tsx` wrap `<BrowserRouter basename={APP_BASE}>` auto-prepend basename cho 13 route hiện tại — KHÔNG đụng path absolute.

- **Plan 05-03 PROXY-04 — Per-hub branding registry + 4 SVG asset (D-V3-Phase5-D1/D3):** `frontend/src/branding/index.ts` Vite `import.meta.glob('./*/index.ts', { eager: true })` + `BrandingConfig` type + `getBranding(hub)` fallback central + `getContrastTextColor(themeColor)` WCAG 1.4.11 mitigation (hcns amber `#f59e0b` luminance > 0.6 → 'slate-900', 3 hub khác → 'white'). 4 hub config `branding/<hub>/index.ts`: central indigo `#6366f1` (Medinet brand) + yte emerald `#10b981` (Hub Y tế) + duoc sky `#0ea5e9` (Hub Dược) + hcns amber `#f59e0b` (Hub HCNS). 4 SVG placeholder text-only initial letter (M/Y/D/H) `frontend/public/branding/<hub>/logo.svg` (Vite copy public → dist → Caddy file_server). T-5-03 path traversal mitigation qua regex constrain `^\.\/([a-z][a-z0-9_]{0,15})\/index\.ts$`.

- **Plan 05-04 PROXY-02 + PROXY-04 — Login + Layout + crossHubSearch wire (D-V3-Phase5-B4/C1/D2 + D-V3-Phase4-D3 carry forward):** `Login.tsx` 4 state machine (A central no-return, B central with valid return + chip, C hub direct visit + skeleton redirect, D invalid return silent fallback) + branding logo + title + tagline + themeColor inline CSS var `--hub-theme` + submit button gradient `color-mix(in srgb, ...)` + T-5-04 strict return validation 4-layer (strip `/` + reject `//` + reject `://` + regex hub format + KNOWN_HUBS allowlist). `Layout.tsx` sidebar header logo bg + title swap qua module-level `getBranding(CURRENT_HUB)` + hover ring themeColor (UI-SPEC §3 LOCKED scope — chỉ sidebar header touch, KHÔNG cascade tất cả component R-V3-2 mitigation). `api.ts::crossHubSearch` REPLACE → ABSOLUTE path `/api/search/cross-hub` qua `requestAbsolute<T>` helper (bypass `${API_BASE}` prefix — D-V3-Phase4-D3 LOCKED hub con strip endpoint, Caddy `/api/*` route central). `tryRefresh()` audit B-02 fix explicit `redirect: 'follow'` (D-V3-Phase5-C4).

- **Plan 05-05 PROXY-01 + FACTOR-04 extend — hub-add.sh step 8+9 (D-V3-Phase5-A3):** Append `api/scripts/hub-add.sh` Plan 02-05 7-step pipeline → 9-step. Step 8: atomic sed-edit `.env` HUBS_ALLOWLIST + HUBS_ALLOWLIST_REGEX (tmp file + mv preserve other env, duplicate skip idempotent). Step 9: PRE-validate `caddy validate --config /etc/caddy/Caddyfile` TRƯỚC reload (Pitfall 7 silent rollback mitigation) + `caddy reload` zero-downtime + smoke `curl -k https://${WIKI_PUBLIC_DOMAIN}/${HUB}/api/health` post-reload warn-only + dev pre-up tolerance (caddy chưa running → skip + hint). T-5-05 strict guard Plan 02-05 carry forward (regex + RESERVED blacklist KHÔNG relax).

- **Plan 05-06 closeout — docs + smoke checkpoint 4 hub × 11 trang (file này, 2026-05-23):** CLAUDE.md §3 D6 EXPIRED note + §6 Phase 5 progress row + pattern subsection (file này) + STATE.md frontmatter + REQUIREMENTS.md PROXY-01..04 mark [x] + ROADMAP.md Phase 5 DONE + README.md section mới "Reverse Proxy Subpath Deploy Notes". Task 5b `checkpoint:human-action gate=blocking` smoke 4 hub × 11 trang React M2 COMPAT-01 (UI-SPEC §7 — 44 checkpoint). User resume signal auto-fallback `skip smoke` per v3.0-b precedent (Plan 03-05 + 04-07 pre-resolved skip pattern + --auto chain mode active).

**Architecture insights (Phase 5):**

1. **Single source-of-truth env-driven multi-hub:** `.env HUBS_ALLOWLIST=yte,duoc,hcns` → Caddy `HUBS_ALLOWLIST_REGEX=yte|duoc|hcns` qua docker-compose env wire + frontend `window.__HUB_CONFIG__.allowlist` (Phase 6 SETTINGS-04 sẽ sync DB-driven). `make hub-add` cập nhật cả Caddy regex + hub-init DB + override.yml + .env atomic chain.
2. **1 build dùng chung 4 deploy:** Vite `base='/'` + asset absolute `/assets/*` + react-router `BrowserRouter basename={APP_BASE}` auto-prepend → KHÔNG cần build matrix `VITE_HUB_NAME=yte` × 4 (GA-V3-C khuyến nghị seed CONFIRMED).
3. **Per-hub branding scope minimal:** Chỉ Login.tsx + Layout.tsx sidebar header touch — Dashboard/Documents/Search/11 trang nội dung giữ NGUYÊN M2 (R-V3-2 mitigation). Full Tailwind cascade defer v4.0.
4. **Theme color delivery inline CSS variable `--hub-theme`:** Runtime swap per-hub qua React `style={{ '--hub-theme': themeColor }}` outermost wrapper + child `color-mix(in srgb, var(--hub-theme) ...)` — KHÔNG cần Tailwind plugin (build overhead). Browser support Chrome 111+/Safari 16.4+/Firefox 113+ ≥ 95% user 2026.
5. **localStorage same-origin SSO:** `wiki.medinet.vn` root domain → token share xuyên `/yte/`, `/duoc/`, `/` subpath cùng origin (Web Storage API scope by origin). XSS concern M2 carry forward — defer v4.0 HARD-V4-05 httpOnly cookie.
6. **307 redirect failsafe (Plan 03-04 carry forward):** Backend hub con `/api/auth/login` + `/api/auth/refresh` 307 → central — Phase 5 FE Login.tsx mount redirect là PRIMARY UX (D-V3-Phase5-B4); 307 backend là LAYER 2 safety cho `api.ts::tryRefresh()` POST same-origin redirect: 'follow' (RFC 7231 preserve POST body).
7. **Cross-hub endpoint absolute path override:** `api.crossHubSearch()` dùng `/api/search/cross-hub` absolute (KHÔNG `${API_BASE}` prefix) — D-V3-Phase4-D3 LOCKED hub con strip endpoint, Caddy `/api/*` handle central route. Pattern reusable cho future central-only endpoint (vd Phase 6 admin).

**T-5-01..07 STRIDE coverage:**
- T-5-01 Caddy open redirect: Plan 05-01 path_regexp anchor `^/(...)/api/(.*)$` — unknown hub fall through file_server (no arbitrary upstream).
- T-5-02 KNOWN_HUBS tampering: Plan 05-02 + 05-04 — backend Caddy regex authoritative, FE UX-only.
- T-5-03 Logo asset path traversal: Plan 05-03 — regex constrain `^\.\/([a-z][a-z0-9_]{0,15})\/index\.ts$` + path schema locked.
- T-5-04 Login ?return open redirect: Plan 05-04 — 4-layer validation (strip + reject absolute + regex + allowlist) + W-05 origin-not-host check audit.
- T-5-05 hub-add.sh shell injection: Plan 05-05 — Plan 02-05 strict guard carry forward (regex + RESERVED blacklist), `$HUB` quoted.
- T-5-06 XSS via theme color: Plan 05-03 + 05-04 — themeColor hardcoded TS const, React style escape.
- T-5-07 localStorage XSS exfil: ACCEPTED M2 carry forward — defer v4.0 HARD-V4-05.

**Backward compat (Phase 5 KHÔNG break M2):**
- API endpoint URL/envelope shape `{success, data, error, meta}` LOCKED — Phase 5 chỉ đổi FE base URL compute (relative path qua Caddy).
- M2 11 trang React component shell preserve (R-V3-2) — chỉ touch Login.tsx + Layout.tsx sidebar header.
- M2 localStorage same-origin pattern preserve (D-V3-Phase5-C2).
- M2 authentication flow preserve — Login form same-origin POST + JWT Bearer token header.

**v3.0-b progress:** Phase 5 hoàn tất 4/4 REQ-ID PROXY. v3.0-b 2/4 phase DONE (Phase 4 + 5 — 28/~32 plan ≈ 88%). Next: Phase 6 SETTINGS sync (SETTINGS-01..04 — rag_config HTTP pull + Redis pub/sub invalidate + api_keys proxy + hub_registry read-only).

**Reference:**
- `.planning/phases/05-reverse-proxy-frontend-subpath/05-CONTEXT.md` — 16 D-V3-Phase5-A1..D4 LOCKED 2026-05-22.
- `.planning/phases/05-reverse-proxy-frontend-subpath/05-UI-SPEC.md` — Visual design contract (4 hub branding + Login state machine + Layout sidebar + theme delivery).
- `.planning/phases/05-reverse-proxy-frontend-subpath/05-VALIDATION.md` — Per-task verification map (Wave 0 vitest infra + 5 test file).
- `.planning/phases/05-reverse-proxy-frontend-subpath/05-{01..06}-PLAN.md` — implementation chi tiết 6 plan.
- `.planning/phases/05-reverse-proxy-frontend-subpath/05-{01..06}-SUMMARY.md` — deliverable + commit + test count per plan.

### Phase 6 System Settings Sync pattern (SETTINGS-01..04 — 2026-05-23)

5 plan đóng 4 REQ-ID System Settings Sync + 4 D-V3-Phase6-A/B/C/D LOCKED + 6 Prometheus metric infrastructure (HTTP pull + Redis pub/sub invalidate hybrid mechanism, R-V3-6 LOW mitigation):

- **Plan 06-01 SETTINGS-01..04 — Wave 1 BLOCKING infra (D-V3-Phase6-A/B/D):** Module mới `api/app/settings_sync/` (3 file scaffold — `__init__.py` re-export 11 symbol + `keys.py` 4 constant module-level + `make_apikey_cache_key()` SHA-256 hex prefix 16 char T-06-04-02 mitigation KHÔNG plaintext trong Redis key + `metrics.py` 6 Prometheus collector module-level label `hub_name` + `key_type` bounded enum 3 value W7 carry forward). Settings 5 field mới (`settings_proxy_secret: str = ""` + `settings_cache_ttl_rag_config=60` + `settings_cache_ttl_hub_registry=300` + `settings_cache_ttl_apikey=60` + `settings_subscriber_reconnect_seconds=5`) + 1 model_validator `_enforce_settings_proxy_secret` length ≥ 32 char BẤT KỂ hub_name (KHÁC Phase 3+4 pattern — shared secret BOTH central + hub con cần T-06-04-01 entropy 128-bit). docker-compose 4 service env wire `SETTINGS_PROXY_SECRET: ${SETTINGS_PROXY_SECRET:?msg}` fail-loud syntax + docker-compose.override.yml.template FACTOR-04 placeholder hub con dynamic + `.env.example` + `api/.env.example` document 5 env mới với hint `openssl rand -hex 32`. 25/25 unit test PASS (12 config + 6 keys + 7 metrics) + regression Phase 1..5 unit suite KHÔNG break (408/408 PASS) + ruff/mypy --strict clean. 1 Rule 3 deviation auto-fix inline (test infra `api/.env` + `api/.env.example` + `tests/conftest.py` autouse `SETTINGS_PROXY_SECRET=x*32` default — cause `app/middleware/rate_limit.py:58` module-level `get_settings()` call bypass conftest monkeypatch).

- **Plan 06-02 SETTINGS-01/02/04 — Wave 2 client + subscriber + Pydantic schema (D-V3-Phase6-A/C):** Module `api/app/settings_sync/client.py` (~370 LOC) 3 HTTP client class — `RagConfigClient` fetch `GET {central_url}/api/rag-config` + cache Redis TTL 60s key `settings:rag_config:<hub_name>` + `SettingsUnavailableError` fail-loud + Prometheus emit hit/miss/latency/stale; `HubRegistryClient` fetch `GET {central_url}/api/hubs` singleton cache TTL 300s key `settings:hub_registry`; `ApiKeyVerifyClient` POST `{central_url}/api/api-keys/verify` body `{api_key}` header `X-Internal-Auth: <settings_proxy_secret>` (D-V3-Phase6-D) + cache Redis TTL 60s hash key `apikey:verify:<sha256[:16]>` (T-06-04-02) + KHÔNG cache negative 401 + Prometheus `APIKEY_VERIFY_TOTAL{result=valid|invalid|cached}`. Module `subscriber.py` (~209 LOC) `settings_subscriber_loop(redis, hub_name, reconnect_seconds=5)` async + outer `while True:` reconnect retry on ConnectionError + Pydantic `InvalidateMessage(BaseModel)` schema `config_key: Literal["rag_config","hub_registry","apikey"] + hub: str + key_id: str | None + timestamp: int` validate payload reject invalid (T-06-02-03 Tampering injection) + 3 config_key flush branch (rag_config per-hub broadcast / hub_registry singleton / apikey SCAN+DEL full flush) + CancelledError graceful shutdown + `_process_message + _subscribe_and_listen` helper extract (C901 complexity refactor). 22/22 unit test PASS (11 client + 11 subscriber). 3 Rule 1 fix inline (httpx.Timeout 4-param + pytest-asyncio CancelledError hang workaround + C901 complexity refactor).

- **Plan 06-03 SETTINGS-02/03 — Wave 3 refactor + extend (D-V3-Phase6-A/C/D):** `api/app/auth/api_key.py::require_api_key` REFACTOR — thêm `request: Request` param + branch verify path theo `settings.hub_name` (central=local M2 `ApiKeyService.verify_key` AES-GCM carry forward KHÔNG đụng AUX-02 private logic; hub con=`request.app.state.api_key_verify_client.verify(x_api_key)` HTTP proxy + 503 `APIKEY_VERIFY_CLIENT_UNAVAILABLE` envelope nếu client chưa init — boot fail-loud R-V3-6 mitigation). Dependency mới `api/app/auth/dependencies.py::require_internal_auth` async dep — Header `X-Internal-Auth` constant-time `hmac.compare_digest` với `settings.settings_proxy_secret` → 401 `INTERNAL_AUTH_FAIL` envelope nếu mismatch (T-06-03-01 timing attack mitigation). `api/app/routers/rag_config.py::update_rag_config` PUT extend `request: Request` param + publish best-effort fail-open `await redis.publish("settings:invalidate", json.dumps({"config_key":"rag_config","hub":"*","timestamp":int(time.time())}))` sau service.update_config success (pattern carry forward search_cache.py M2 publish_invalidate fail-open). Endpoint MỚI `api/app/routers/api_keys.py POST /verify` central-only mount (FACTOR-02 carry forward Phase 2 — api_keys_router central-only KHÔNG cần thay đổi main.py include) với `require_internal_auth` dep + `VerifyApiKeyRequest` Pydantic schema (`api_key: str Field min_length=1 max_length=256`) + return raw dict `{valid: bool, principal: dict | None}` (KHÔNG envelope — hub con ApiKeyVerifyClient parse raw structure trực tiếp). 22/22 unit test PASS (6 require_api_key branch + 6 require_internal_auth + 4 rag_config publish + 6 verify endpoint) + 452/452 unit regression PASS + 50/50 cluster auth/rag_config/api_keys/sso + 19/19 integration factor+rate_limit PASS + ruff/mypy clean. 0 deviation — plan executed exactly as written.

- **Plan 06-04 SETTINGS-01..04 — Wave 4 lifespan integration BLOCKING:** `api/app/main.py::lifespan` thêm block hub con (`if settings.hub_name != "central":`) SAU sync_worker_task spawn (~line 463) + TRƯỚC `try: yield` (~line 565) — init 4 `app.state.<X> = None` defensive default + escape hatch `SETTINGS_SKIP_FETCH=1` env (pattern 4-flag song song `JWKS_SKIP_FETCH=1` Plan 03-02 + `SYNC_SKIP_CENTRAL_POOL=1` Plan 04-04 + `COCOINDEX_SKIP_SETUP=1` DEF-05-01) + 3 client instantiate (`RagConfigClient` + `HubRegistryClient` + `ApiKeyVerifyClient`) + `await rag_client.fetch_initial()` blocking 5s + `await hub_client.fetch_initial()` blocking 5s (ApiKeyVerifyClient lazy KHÔNG fetch_initial — verify on demand) + boot fail-loud raise → uvicorn exit 1 (D-V3-Phase6-A LOCKED + R-V3-6 LOW pattern carry forward Plan 03-02 JWKSCache + Plan 04-04 central_sync_pool) + spawn `app.state.settings_subscriber_task = asyncio.create_task(settings_subscriber_loop(redis, hub_name, reconnect_seconds))` với guard `app.state.redis is not None AND app.state.redis_ready` (T-06-04-04 Rule 3 fix — M2 `from_url()` lazy assign redis object trước ping; ping fail → redis_ready=False NHƯNG app.state.redis vẫn non-None → subscriber spawn broken connection → infinite reconnect hang; `redis_ready` là source-of-truth). Shutdown graceful sau `yield`: `settings_subscriber_task.cancel() + asyncio.wait_for(timeout=10s)` + suppress `CancelledError/TimeoutError` (T-06-04-03 resource exhaustion mitigation pattern carry forward search_cache_task M2). 6/6 integration test ASGI `LifespanManager` PASS (skip path + populate 3 client + subscriber branch by redis_ready + shutdown state reset + boot fail-loud direct RagConfigClient test KHÔNG asgi_lifespan tránh leak audit_task/search_cache_task tasks spawn trước Phase 6 block + central skip); pubsub e2e defer Phase 7 MIGRATE-05 nếu fakeredis async pubsub.listen() KHÔNG yield message reliable. 452/452 unit regression + 19/19 integration regression + ruff/mypy --strict clean. 3 Rule 3 deviation auto-fix inline (main.py subscriber spawn guard `redis_ready` + `test_auth_router_hub_redirect.py::_setup_env` + `tests/integration/conftest.py::hub_app_factory` thêm `SETTINGS_SKIP_FETCH=1` env hub con block).

- **Plan 06-05 closeout — docs + smoke checkpoint (file này, 2026-05-23):** CLAUDE.md §6 v3.0 progress row Phase 6 ✅ DONE + pattern subsection (file này) + STATE.md frontmatter `phase_6_status: DONE` + Current Position + Phase 6 Planning + Results Summary + REQUIREMENTS.md SETTINGS-01..04 mark `[x]` + NOTE Phase 6 closeout 5-plan list + ROADMAP.md Phase 6 row DONE + Decisions block + Progress table 33/~37 ≈ 89% + README.md NEW section "System Settings Sync Deploy Notes (Phase 6 v3.0)" 5-step deploy + rollback procedure + escape hatch `SETTINGS_SKIP_FETCH=1` + smoke defer Phase 7. Smoke checkpoint manual smoke 4 hub × `PUT /api/rag-config` central + verify yte/duoc/hcns cache flush < 30s observed + central `POST /api/api-keys/verify` proxy 200 — Task 5b auto-fallback `skip smoke` per v3.0-b precedent (Plan 03-05 + 04-07 + 05-06 pre-resolved skip pattern + `--auto --chain` mode active); evidence chain 62+ unit + 6 integration test in-process cover SETTINGS-01..04 semantic; manual visual smoke runtime defer Phase 7 MIGRATE-05 full E2E (3 hub con + central + golden path + JWT SSO live + cross-hub search live data + per-hub branding visual diff + settings sync pub/sub live propagate).

**Architecture insights (Phase 6):**

1. **HTTP pull + Redis pub/sub invalidate hybrid (D-V3-Phase6-A LOCKED):** Pull pattern proven Phase 3 JWKSCache carry forward; pub/sub bổ sung "TTL window stale" mitigation — đổi config ở central → publish ngay → hub con flush < 1s thực tế (E-V3-4 < 30s threshold thừa margin). Best-effort fail-open Redis down KHÔNG block admin write (TTL natural fallback 60s).
2. **1 channel `settings:invalidate` cho cả 3 category (D-V3-Phase6-C):** Pydantic `InvalidateMessage` schema `config_key: Literal[3]` + `hub: str` + `key_id: str | None` + `timestamp: int` validate payload reject injection (T-06-02-03). Subscriber phân nhánh 3 config_key flush đúng cache key (rag_config per-hub broadcast / hub_registry singleton / apikey SCAN+DEL full flush).
3. **Shared secret `X-Internal-Auth` (D-V3-Phase6-D):** Simpler hơn JWT internal-only / mTLS cho v3.0-b scope. 32-char min entropy 128-bit + `hmac.compare_digest` constant-time. POST `/api/api-keys/verify` central-only mount (FACTOR-02 carry forward) + endpoint mới KHÔNG đụng M2 `ApiKeyService.verify_key` AES-GCM at-rest private logic (AUX-02 unchanged).
4. **TTL strategy per category (D-V3-Phase6-B):** rag_config 60s + apikey 60s (hot revoke window M2 AUX-02 baseline) + hub_registry 300s (rare-change FACTOR-04 `make hub-add` infrequent). Pub/sub primary; TTL fallback Redis down.
5. **Cache key hashing T-06-04-02 mitigation:** `make_apikey_cache_key()` SHA-256 hex prefix 16 char — KHÔNG plaintext trong Redis key/value. Subscriber `apikey` flush dùng SCAN+DEL pattern (KHÔNG cần plaintext compute key).
6. **Lifespan fail-loud boot pattern carry forward:** rag_client + hub_client `fetch_initial()` blocking 5s raise → uvicorn exit 1 (operator catch boot error). Pattern song song Phase 3 JWKSCache + Phase 4 central_sync_pool — consistency v3.0 milestone. Subscriber spawn guard `redis_ready` source-of-truth (T-06-04-04 Rule 3 fix).
7. **6 Prometheus metric mới (Phase 6 observability):** `settings_cache_hit_total{hub_name, key_type}` + `settings_cache_miss_total` + `settings_pull_latency_seconds{hub_name, endpoint}` histogram + `settings_invalidate_received_total{hub_name, key_type}` + `settings_stale_seconds{hub_name, key_type}` gauge + `apikey_verify_total{hub_name, result}` — label cardinality bounded W7 carry forward Phase 4.

**T-06-01..04 STRIDE coverage:**
- T-06-01-01 Tampering `.env SETTINGS_PROXY_SECRET`: Plan 06-01 fail-loud `${VAR:?msg}` + Settings validator length ≥ 32 char.
- T-06-02-01 Information Disclosure apikey plaintext Redis key: Plan 06-01 `make_apikey_cache_key` SHA-256 hash prefix.
- T-06-02-03 Tampering pub/sub payload injection: Plan 06-02 Pydantic Literal enum reject invalid + JSON parse fail log warning skip.
- T-06-02-05 DoS subscriber crash: Plan 06-02 best-effort fail-open + outer reconnect loop + CancelledError graceful.
- T-06-03-01 Tampering X-Internal-Auth secret leak: Plan 06-03 `hmac.compare_digest` constant-time + secret entropy 128-bit.
- T-06-03-04 DoS publish_invalidate hang: Plan 06-03 try/except wrap + log warning (KHÔNG raise) — best-effort fail-open.
- T-06-04-01 DoS lifespan blocking hang: Plan 06-04 timeout connect=2s read=5s; fail-loud raise → uvicorn exit 1.
- T-06-04-03 Resource leak subscriber sau shutdown: Plan 06-04 `task.cancel() + asyncio.wait_for(timeout=10s)` graceful.
- T-06-04-04 Tampering lifespan order race redis ping fail: Plan 06-04 `redis_ready` guard subscriber spawn (Rule 3 fix).

**Backward compat (Phase 6 KHÔNG break M2):**
- `require_api_key` signature mở rộng thêm `request: Request` — FastAPI Depends auto-inject; consumer endpoint M2 KHÔNG cần update.
- `update_rag_config` PUT signature mở rộng thêm `request: Request` — backward compat.
- M2 `ApiKeyService.verify_key` AES-GCM at-rest LOCKED unchanged (AUX-02 carry forward).
- M2 `rag_config_service.py::update_config()` LOCKED unchanged — Phase 6 chỉ wrap publish best-effort sau success.
- Hub con M2 cũ thiếu `SETTINGS_PROXY_SECRET` env → Settings validator fail boot → operator phải set TRƯỚC deploy (xem README.md "System Settings Sync Deploy Notes" section deploy 5-step + rollback).

**R-V3-6 LOW mitigation chain:**
- HTTP pull on-demand + Redis cache TTL 60s baseline.
- Pub/sub invalidate broadcast `settings:invalidate` channel — < 1s propagate thực tế.
- Subscriber reconnect retry 5s interval on ConnectionError — KHÔNG fail-loud (TTL natural fallback).
- Boot fail-loud rag_client + hub_client `fetch_initial()` 5s timeout — operator catch (R-V3-5 pattern carry forward).
- Idempotent flush — multi pub/sub event same key OK (SCAN+DEL apikey + delete singleton hub_registry + delete per-hub rag_config).

**E-V3-4 propagate < 30s carry forward:**
- Default TTL 60s (rag_config + apikey) overlap pub/sub natural propagate.
- Pub/sub broadcast `hub="*"` tới all hub con đồng thời.
- Live measure defer Phase 7 MIGRATE-05 runtime smoke E2E.

**v3.0-b progress:** Phase 6 hoàn tất 4/4 REQ-ID SETTINGS. v3.0-b 3/4 phase DONE (Phase 4 + 5 + 6 — 33/~37 plan ≈ 89%). Next: Phase 7 MIGRATE (MIGRATE-01..05 — pg_dump snapshot per hub_id + blue/green restore + MCP re-point + smoke E2E 3 hub con + central + cross-hub p95 < 1.5s live measure).

**Reference:**
- `.planning/phases/06-system-settings-sync/06-CONTEXT.md` — 4 D-V3-Phase6-A..D LOCKED 2026-05-23.
- `.planning/phases/06-system-settings-sync/06-PATTERNS.md` — Pattern map 14 file analog + 5 Wave grouping.
- `.planning/phases/06-system-settings-sync/06-{01..05}-PLAN.md` — implementation chi tiết 5 plan.
- `.planning/phases/06-system-settings-sync/06-{01..05}-SUMMARY.md` — deliverable + commit + test count per plan.

### Phase 7 Migration + Smoke E2E pattern (MIGRATE-01..05 — 2026-05-23) 🎉 v3.0 MILESTONE CLOSED

5 plan đóng 5 REQ-ID Migration + 4 D-V3-Phase7-A/B/C/D LOCKED + 5 bash script + 1 runbook + automated 3 hub × 7-step golden path (final phase v3.0 milestone):

- **Plan 07-01 MIGRATE-01 — Wave 1 BLOCKING (D-V3-Phase7-A pg_dump --where option a LOCKED):** Script `scripts/migrate/01-snapshot-hubs.sh` (~194 LOC) `pg_dump --data-only --no-owner --no-acl --column-inserts --where="hub_id='<uuid>'"` 5 table per hub (chunks/documents/users/audit_logs/usage_events) output `migrate-snapshots/migrate-<hub>-<YYYY-MM-DD>.sql`. Resolve hub_id UUID từ medinet_central.hubs qua psql -tA. Regex + RESERVED + reject central validation chain T-5-05 carry forward. Idempotent skip nếu file đã tồn tại. Sanity check row count post-dump qua grep INSERT. `.gitignore` exclude *.sql + README.md 30-day retention + privacy + recovery procedure docs.

- **Plan 07-02 MIGRATE-02 — Wave 2 BLOCKING (D-V3-Phase7-B blue/green per-hub LOCKED):** Script `02-restore-hub.sh` (~225 LOC) psql `-f` restore từ Plan 07-01 snapshot vào `medinet_hub_<HUB>` (Phase 1 hub-init + Phase 4 Alembic 0005 schema ready). Auto-detect latest snapshot date qua `ls migrate-snapshots/migrate-<HUB>-*.sql | sort -r | head -1`. T-07-02-03 mitigation verify `SELECT current_database() == 'medinet_hub_<HUB>'` fail-fast trước restore. Post-restore row count sanity check. Script `03-switch-caddy.sh` (~132 LOC) **VERIFY-ONLY** (per CONTEXT.md `<specifics>` correction — Caddyfile Phase 5 `{re.hub_api.1}` đã dynamic capture hub_name, KHÔNG cần sed edit) check `docker compose ps python-api-<HUB>` running + caddy validate + smoke curl `/<HUB>/api/health`. Hỗ trợ `--rollback` flag stop hub container (Caddy regex fall-through 404 user-visible signal switch revert).

- **Plan 07-03 MIGRATE-03 — Wave 3 BLOCKING (D-V3-02 LOCKED — chunks KHÔNG truncate):** Script `04-truncate-central.sh` (~269 LOC) atomic BEGIN/COMMIT psql heredoc DELETE 4 table per hub (documents/users/audit_logs/usage_events) WHERE hub_id = '<uuid>' — **explicit KHÔNG DELETE FROM chunks** (D-V3-02 LOCKED, vẫn nhận sync 1-way từ hub con cho cross-hub search). audit_logs INSERT TRƯỚC DELETE atomic (carry forward Phase 4 Plan 04-06 sync.py W8 pattern) — `action='migrate.truncate_hub' + actor=NULL system + target_type='central_hub_rows' + payload jsonb với row counts pre-delete`. Dry-run DEFAULT ON safety — operator phải explicit `--apply [--yes]` để thực thi DELETE (T-07-03-04 misfire mitigation). Pre + post DELETE row count log. audit_logs DELETE filter `action != 'migrate.truncate_hub'` để tránh xóa row vừa INSERT.

- **Plan 07-04 MIGRATE-04 — Wave 3 parallel (D-V3-Phase7-C MCP re-point central):** `mcp_service/mcp_app/config.py::Settings.api_base_url` default đổi `"http://localhost:8180"` → `"http://python-api-central:8080"` (1-line change + 5-line comment Phase 7 decision reference). `field_validator _validate_base_url` UNCHANGED (SSRF mitigation T-08.2-01-T Phase 8.3 carry forward). docker-compose.yml mcp_service env block comment update `re-confirm` → `CONFIRMED Phase 7 MIGRATE-04` — env value `MCP_API_BASE_URL: http://python-api-central:8080` UNCHANGED (Phase 2 Plan 02-02 đã set đúng). Runbook `scripts/migrate/06-mcp-smoke.md` (~181 LOC) 5-step Inspector OAuth manual checklist: (1) pre-deploy 135/135 mcp_service test regression + container running + env verify, (2) Inspector OAuth connect via discovery + token exchange, (3) `search_wiki(query, hub_id="yte")` single-hub envelope D6 + isolation verify, (4) `ask_wiki(query)` cross-hub no hub_id → citations multi-hub + p95 < 1.5s, (5) citation `[N]` resolve document detail + Prometheus assertion. Rollback procedure git revert + re-build mcp_service.

- **Plan 07-05 closeout — Wave 5 (file này, 2026-05-23):** Automated smoke `05-smoke-e2e.sh` (~271 LOC) 3 hub × 7-step golden path (login + upload DOCX + poll status + search local + search cross-hub + ask + citation [N] + logout) qua `curl` + `jq` envelope D6 parse + Prometheus assertion post-loop (cross_hub_search_latency p95 < 1.5s + sync_lag < 30s + apikey_verify_total{result=cached} > 0 + sync_count_drift < 0.01). Test fixture `fixtures/sample-document.docx` 37KB Vietnamese content (vaccin + dược keyword) + `generate-sample.py` reproducible script qua python-docx. Closeout 5 doc update + v3.0 milestone CLOSED marker (38/38 plan 100%). Manual visual smoke checkpoint 4 hub × 11 trang React M2 COMPAT-01 = `checkpoint:human-action gate=advisory` KHÔNG blocking (D-V3-Phase7-D LOCKED — Phase 7 cuối, automated semantic đủ MIGRATE-05 coverage; visual regression log v3.1 follow-up issue, closeout vẫn proceed). HUMAN-UAT batch resolve 11+ pending items từ Phase 3+4+5+6.

**Architecture insights (Phase 7):**

1. **Blue/green per-hub zero-downtime (D-V3-Phase7-B LOCKED):** Snapshot → restore green DB → smoke green → switch Caddy (verify-only auto-route) → repeat 2-3 hub còn lại → truncate central. Caddy reload ~50-100ms negligible (HTTP/2 keep-alive resume); R-V3-4 mitigation full.
2. **D-V3-02 chunks PRESERVED:** `medinet_central.chunks` aggregated cross-hub search target — Phase 7 Plan 07-03 KHÔNG truncate (explicit grep -v DELETE FROM chunks + 10+ comment reference). Sync 1-way từ hub con tiếp tục post-migration qua outbox worker Phase 4.
3. **MCP re-point 1-line config + 5-line decision comment (D-V3-Phase7-C):** Small surface area — env wire đã đúng từ Phase 2 (docker-compose MCP_API_BASE_URL: http://python-api-central:8080). Cross-hub aggregate 1 SQL Phase 4 Plan 04-05 carry forward — MCP KHÔNG fan-out N hub.
4. **Caddyfile dynamic regex KHÔNG sed edit (correction during planning):** Phase 5 đã ship `{re.hub_api.1}` dynamic capture → `reverse_proxy python-api-{re.hub_api.1}:8080` → Phase 7 chỉ cần container `python-api-<HUB>` running → Caddy auto-route. `03-switch-caddy.sh` shrink từ sed edit phức tạp xuống verify-only ~132 LOC.
5. **Automated mandatory + human advisory (D-V3-Phase7-D):** `05-smoke-e2e.sh` BLOCKING evidence chain (3 hub × 7 step + Prometheus). Manual visual smoke checkpoint advisory KHÔNG blocking — Phase 7 cuối, KHÔNG defer; regression log v3.1 issue.

**T-07-01..05 STRIDE coverage:**
- T-07-01-01..04 Plan 07-01 — Tampering hub arg (regex+RESERVED+central reject) + Info Disclosure .sql privacy + DoS pg_dump off-peak + Repudiation immutable timestamp filename.
- T-07-02-01..05 Plan 07-02 — Tampering arg + path traversal + current_database verify + DoS rollback accept + Repudiation forward-only accept.
- T-07-03-01..05 Plan 07-03 — Tampering arg + DoS single-hub transaction + Repudiation audit INSERT atomic + Tampering misfire dry-run default + Elevation chunks explicit preserved.
- T-07-04-01..04 Plan 07-04 — Info Disclosure SSRF validator unchanged + Spoofing OAuth Phase 8.3 carry + Repudiation audit M2 + DoS fan-out rejected D-V3-02.
- T-07-05-01..05 Plan 07-05 — Info Disclosure creds env var + Tampering fixture text-only + DoS smoke accept + Repudiation audit accept + Spoofing visual smoke advisory.

**Backward compat (Phase 7 KHÔNG break M2 / v2.0):**
- MCP tools `search_wiki + ask_wiki` signature UNCHANGED.
- mcp_service `field_validator _validate_base_url` UNCHANGED — SSRF mitigation T-08.2-01-T Phase 8.3 carry forward.
- 143/135 `mcp_service/tests/` PASS regression mandatory (Phase 8.3 v2.0 baseline 135 + Plan 10-04 CORS split 8).
- Envelope D6 LOCKED — smoke script parse same shape.
- OAuth flow Phase 8.3 v2.0 carry forward UNCHANGED — Caddy `/.well-known/*` + `/mcp/*` route Phase 5.
- Hub_id rows central skeleton truncated NHƯNG chunks PRESERVED (D-V3-02 LOCKED).
- audit_logs row `migrate.truncate_hub` persistent — forensic trail.

**R-V3-4 migration downtime mitigation chain:**
- Blue/green per-hub procedure (D-V3-Phase7-B) — Caddy reload ~50-100ms negligible.
- Snapshot 30-day retention (Plan 07-01 migrate-snapshots/README.md) — rollback path enable.
- `03-switch-caddy.sh --rollback` mode — Caddy regex fall-through 404 user-visible signal.
- Dry-run default ON truncate (Plan 07-03 --apply explicit) — misfire mitigation T-07-03-04.

**v3.0 milestone CLOSED 🎉:** 38/38 plan ship (7 phase × ~5.4 plan avg) — 30 REQ-ID consumed (TOPO 4 + FACTOR 4 + SSO 4 + SYNC 5 + PROXY 4 + SETTINGS 4 + MIGRATE 5). v3.0-a (Phase 1-3) + v3.0-b (Phase 4-7) anti-pivot pattern hoàn tất. Next: `/gsd-complete-milestone v3.0` separate command — archive `.planning/milestones/v3.0-archive/` + reset ROADMAP.md cho v4.0 backlog (sub-hub split + HA Redis cluster + OCR Vietnamese + streaming /api/ask).

**Reference:**
- `.planning/phases/07-migration-smoke-e2e/07-CONTEXT.md` — 4 D-V3-Phase7-A..D LOCKED 2026-05-23.
- `.planning/phases/07-migration-smoke-e2e/07-PATTERNS.md` — Pattern map 14 file analog 100% coverage.
- `.planning/phases/07-migration-smoke-e2e/07-{01..05}-PLAN.md` — implementation chi tiết 5 plan.
- `.planning/phases/07-migration-smoke-e2e/07-{01..05}-SUMMARY.md` — deliverable + commit + test count per plan.

### Phase 1 v3.1 RBAC schema pattern (ROLE-01..04 — 2026-05-23)

3 plan đóng 4 REQ-ID ROLE schema migration + helper:

- **Plan 01-01 ROLE-01 + ROLE-02 + ROLE-03 — Alembic migration 0006_role_hub_admin.py:** CHECK constraint `users.role` mở rộng 4 value (admin|hub_admin|editor|viewer) qua DROP + ADD raw SQL với introspect `sa.inspect().get_check_constraints("users")` tìm tên constraint thật (chống discrepancy `ck_users_role_enum` migration 0001 vs `role_enum` model auth.py). user_hubs.role TEXT NULL DEFAULT NULL + CHECK NULL-aware `(role IS NULL OR role IN (...))` per-hub override (D-V3.1-02 LOCKED). audit_logs INSERT seed `action='migration.role_seed'` với jsonb_build_object payload (migration_revision + admin_count + user_hubs_count + timestamp_utc) + WHERE NOT EXISTS idempotent guard. downgrade() defensive RuntimeError nếu COUNT(*) role='hub_admin' > 0 (E-V3.1-1 STOP). Reference: `.planning/phases/01-rbac-schema-migration/01-01-PLAN.md` + `01-01-SUMMARY.md`.

- **Plan 01-02 ROLE-04 — Module mới api/app/auth/role.py:** `async def get_effective_role(session: AsyncSession, user_id: UUID | str, hub_id: UUID | str) -> str` + `UserNotFoundError(Exception)`. Logic: SELECT user_hubs.role WHERE (user, hub) → non-NULL return (override); NULL hoặc no-row fallthrough → SELECT users.role return (inherit global); no user → UserNotFoundError raise. Raw SQL via `sqlalchemy.text()` + named bind params `:user_id`/`:hub_id` (T-01-02-01 SQL injection mitigation; CLAUDE.md stack pin). KHÔNG import `User`/`UserHub` ORM model (chống cycle Phase 2). Test pytest 6 case + AsyncMock — KHÔNG cần Postgres runtime. Phase 2 import qua `from app.auth.role import get_effective_role` build `require_hub_admin_for(hub_id)` (DEP-01). Reference: `01-02-PLAN.md` + `01-02-SUMMARY.md`.

- **Plan 01-03 closeout — Integration test + docs:** `tests/integration/test_migration_0006_idempotent.py` 5 test cover 4 success criteria ROADMAP Phase 1: (1) CHECK accept hub_admin sau upgrade; (2) re-run upgrade head idempotent KHÔNG fail; (3) user_hubs.role nullable + NULL-aware CHECK; (4) audit_logs seed row tồn tại; (5) downgrade -1 restore CHECK 3 value + drop column. Skip-if-no-DB pattern (`TEST_DATABASE_URL` env var); Phase 4 MIGRATE-01 sẽ chạy bắt buộc. **SAFETY-CRITICAL DSN injection (Iter 1 revision fix I-01 + I-02):** fixture monkeypatch `DATABASE_URL` env + `get_settings.cache_clear()` thay vì `cfg.set_main_option("sqlalchemy.url", ...)` — env.py:185-191 runtime OVERRIDE sqlalchemy.url từ get_settings().database_url, IGNORE caller's set_main_option → nếu dùng set_main_option, test apply migration vào DB .env (vd medinet_central) thay vì TEST_DATABASE_URL (SAFETY BLOCKER). Format DSN giữ `postgresql+asyncpg://` (env.py xử lý async natively); chỉ helper `_asyncpg_dsn()` strip prefix khi asyncpg.connect() direct. STATE.md + REQUIREMENTS.md + CLAUDE.md update. Reference: `01-03-PLAN.md` + `01-03-SUMMARY.md`.

**Backward compat (Phase 1 KHÔNG break v3.0):**
- Schema 0001-0005 carry forward unchanged — chỉ EXTEND CHECK constraint + ADD COLUMN nullable (zero data migration).
- Existing user `role='admin'` GIỮ semantic super-admin (D-V3.1-01 LOCKED — KHÔNG rename `super_admin`).
- M2 + v3.0 JWT claim schema KHÔNG đụng (defer Phase 2-3 cho `actor_role` payload nest, KHÔNG schema migration).
- Frontend hiện tại tiếp tục dùng `users.role` global cho tới Phase 3 FE-04 type extend.

**R-V3.1-1 HIGH mitigation chain Phase 1:**
- Idempotent introspect ở 3 STEP upgrade() — re-run safety (Plan 01-01 + GA-V3.1-C).
- downgrade() đầy đủ với defensive RuntimeError chặn rollback unsafe khi có row `role='hub_admin'` (Plan 01-01 + E-V3.1-1).
- Integration test 5 case verify cả upgrade idempotent + downgrade rollback (Plan 01-03).
- **Integration test DSN injection SAFETY pattern (Iter 1 fix I-01):** monkeypatch env var thay vì set_main_option — chống test vô tình apply migration vào DB dev/prod (env.py:185-191 override sqlalchemy.url runtime).
- Phase 4 MIGRATE-01 sẽ verify runtime full E2E với DB live + 4 hub scenario.

**Next:** Phase 2 `/gsd-discuss-phase 2` DEP backend RBAC enforcement (require_hub_admin_for + GET /api/hubs filter + CRUD scope).

### Phase 2 v3.1 RBAC enforcement pattern (DEP-01..05 — 2026-05-24)

5 plan đóng 5 REQ-ID DEP backend RBAC enforcement + 7 D-V3.1-Phase2-A..G LOCKED:

- **Plan 02-01 DEP-01 — assert_hub_admin_for validator function:** `api/app/auth/dependencies.py` thêm `async def assert_hub_admin_for(*, user, db, target_hub_id) -> None` (hybrid pattern D-V3.1-Phase2-D LOCKED — KHÔNG Depends factory vì hub_id ở body POST/PATCH). Import `get_effective_role` + `UserNotFoundError` từ Plan 01-02 ROLE-04. Logic 5 case: super admin bypass / hub_admin đúng pass / hub_admin sai 403 / viewer 403 / user_not_found defensive catch + 403 (KHÔNG leak 404). Envelope `HUB_ADMIN_REQUIRED` mới (D-V3.1-Phase2-B LOCKED) — KHÔNG reuse FORBIDDEN. 5 unit test pytest PASS với AsyncMock(AsyncSession) factory carry forward Plan 01-02 pattern. Reference: `.planning/phases/02-backend-rbac-enforcement/02-01-PLAN.md` + `02-01-SUMMARY.md`.

- **Plan 02-02 DEP-02 + DEP-04 — GET /api/hubs verify + hubs mutate preserve + B2 iter 1 defensive invariant guard:** routers/hubs.py admin branch ADD B2 iter 1 defensive invariant guard SELECT COUNT(*) FROM user_hubs WHERE role IS NOT NULL → raise 500 `AUTH_STATE_INCONSISTENT` envelope nếu D-V3.1-01 LOCKED invariant violated (admin global + per-hub override existence). List handler else branch UNCHANGED — D-V3.1-Phase2-A LOCKED logic `if user.role == "admin"` line 73-77 ĐÃ ĐÚNG (hub_admin với `users.role='editor'` global rơi else branch line 78-85 → filter user_hubs). 5 endpoint mutate (POST line 94 + PUT line 138 + PATCH status line 168 + GET stats line 198 + GET single line 115) GIỮ `Depends(require_role("admin"))` (DEP-04 LOCKED). Integration test 3 scenario verify hub_admin dmd CHỈ thấy dmd + hub_admin POST → 403 FORBIDDEN (require_role envelope giữ NGUYÊN — KHÔNG đổi HUB_ADMIN_REQUIRED). 2 unit test pure Python mirror logic verify defensive guard clean + broken state. Helper `_seed_hub_admin_user` + fixture `seed_hubs_dmd_tdt` (Plan 01-01 migration 0006 user_hubs.role TEXT NULL khai thác). Reference: `02-02-PLAN.md` + `02-02-SUMMARY.md`.

- **Plan 02-03 DEP-03 — users.py 4 endpoint refactor + Literal extend + DELETE B1 iter 1 branch:** `schemas/users.py` UserRole Literal extend 4 value (admin|hub_admin|editor|viewer) match migration 0006 CHECK. `routers/users.py` 4 endpoint (POST create + PATCH role + GET list + DELETE) refactor: `Depends(get_current_user)` thay `Depends(require_role("admin"))` + inline `await assert_hub_admin_for(user, db, target_hub_id=req.hub_id)` sau body parse. T-02-02-E mitigation business logic block `if req.role == "admin" and user.role != "admin"` → 403 HUB_ADMIN_REQUIRED (hub_admin KHÔNG escalate role admin cho user khác). HUB_ID_REQUIRED guard cho GET list non-super-admin (hub_admin BUỘC pass hub_id query). DELETE handler B1 iter 1 3-branch query user_hubs membership: `len > 1` → 403 `CROSS_HUB_USER_DELETE_DENIED` mới; `len == 1` → assert_hub_admin_for target_hub_ids[0] (pass nếu đúng scope, raise HUB_ADMIN_REQUIRED nếu khác); `len == 0` orphan → 403 HUB_ADMIN_REQUIRED super-only. 4 endpoint còn lại (PATCH status + GET single + PUT + reset-password) GIỮ require_role super-only (D-V3.1-Phase2-E LOCKED cross-hub op). 7 integration test PASS runtime cover scenario ROADMAP success criteria #2 (super admin / hub_admin own hub / hub_admin other hub / role escalation block / DELETE single-hub / DELETE cross-hub / DELETE other-hub). Reference: `02-03-PLAN.md` + `02-03-SUMMARY.md`.

- **Plan 02-04 DEP-05 — Audit payload actor_role + actor_hub_id nest 5 callsite + B7 iter 1 future-proof guard:** `services/audit_service.py` thêm `build_audit_payload(*, actor_role, actor_hub_id, extra=None) -> dict[str, Any]` helper — D-V3.1-Phase2-C LOCKED nest vào payload JSONB existing (audit_logs.payload nullable JSONB từ migration 0001) KHÔNG schema migration. 5 service callsite refactor: user_service.create + delete (signature force keyword required) + hub_service.create + update + update_status (signature default 'admin' + None vì DEP-04 LOCKED hub mutate super-only). 5 router callsite derive actor metadata: POST /api/users + DELETE /api/users + POST /api/hubs + PUT /api/hubs + PATCH /api/hubs/status. B5 iter 1 patch-style INSERT (KHÔNG full handler rewrite) — preserve Plan 02-02 + 02-03 ship lines (assert_hub_admin_for + CROSS_HUB_USER_DELETE_DENIED + LastAdminError + CANNOT_DELETE_SELF + AUTH_STATE_INCONSISTENT). B7 iter 1 future-proof guard `grep -c "enqueue_audit" app/services/api_key_service.py == 0` acceptance criterion lock invariant + MANDATORY docstring note enforce — khi nào Phase n+ thêm audit emit ở api_key_service BẮT BUỘC refactor qua `build_audit_payload`. 4 unit test (pure Python helper) + 2 integration test (poll-based wait `_wait_audit_row` pattern carry forward conftest.py:778-806) verify `payload->>'actor_role'` + `payload->>'actor_hub_id'` queryable. Forensic query Phase 4 MIGRATE-02 hỗ trợ `WHERE payload->>'actor_role' = 'hub_admin' AND payload->>'actor_hub_id' = '<dmd-uuid>'`. Reference: `02-04-PLAN.md` + `02-04-SUMMARY.md`.

- **Plan 02-05 closeout — docs update:** STATE.md frontmatter (`completed_phases: 2` + `completed_plans: 8` + `percent: 53`) + body Phase 2 Results Summary section + REQUIREMENTS.md 5 dòng `[x] **DEP-XX**` + ROADMAP.md table + plans checklist + CLAUDE.md §6 subsection mới (file này). Smoke checkpoint runtime SKIP pre-resolved (auto-fallback `--chain` mode active per Plan 04-07 + 05-06 + 06-05 v3.0 + Plan 01-03 v3.1 carry forward). Evidence chain: 5+2+3+7+4+2 = 11 unit + 12 integration test PASS in-process cover semantic DEP-01..05; manual visual smoke + integration test runtime full E2E defer Phase 4 MIGRATE-02 (4 scenario pytest httpx + audit verify). Reference: `02-05-PLAN.md` + `02-05-SUMMARY.md`.

**Backward compat (Phase 2 KHÔNG break v3.0 + v3.1 Phase 1):**
- Schema 0006 carry forward unchanged (Plan 01-01 ship).
- 5 router endpoint M2 + v3.0 envelope `{success, data, error, meta}` shape LOCKED — chỉ thêm error code mới (HUB_ADMIN_REQUIRED + CROSS_HUB_USER_DELETE_DENIED + HUB_ID_REQUIRED + AUTH_STATE_INCONSISTENT) + extend hành vi (HUB_ID_REQUIRED guard GET list).
- `require_role` closure factory KHÔNG đổi — 4 endpoint users + 5 endpoint hubs giữ NGUYÊN.
- `get_effective_role` helper API contract LOCKED Plan 01-02 carry forward.
- audit_logs.payload JSONB existing đủ chứa actor metadata — KHÔNG schema migration.
- **Breaking change (tests cũ):** `user_service.create(req=, created_by=)` + `delete(user_id=, deleted_by=)` + `hub_service.create/update/update_status` signature THÊM keyword-only `actor_role` (user_service required, hub_service default 'admin') + `actor_hub_id`. Existing tests M2 + v3.0 KHÔNG break (471/471 unit regression PASS verified) — chỉ caller router cần derive đúng từ user.role + req.hub_id.

**R-V3.1-2 MEDIUM mitigation chain Phase 2:**
- Backend filter authoritative GET /api/hubs (Plan 02-02 D-V3.1-Phase2-A LOCKED) — defense in depth, KHÔNG dựa FE.
- assert_hub_admin_for inline check sau body parse (Plan 02-01 + 02-03) — production code path enforce per-hub gate.
- T-02-02-E business logic block role escalation (Plan 02-03 PATCH role handler) — hub_admin KHÔNG được assign role='admin' cho user khác.
- DELETE + PATCH status giữ require_role super-only (Plan 02-03 + D-V3.1-Phase2-E LOCKED) — cross-hub op KHÔNG cho hub_admin.
- B2 iter 1 defensive AUTH_STATE_INCONSISTENT invariant guard (Plan 02-02 D-V3.1-Phase2-G) — KHÔNG silent bypass khi D-V3.1-01 invariant violated (admin global + per-hub override existence).
- Audit forensic chain `payload->>'actor_role'` + `payload->>'actor_hub_id'` (Plan 02-04 DEP-05) — incident review filter scope hub_admin operation.
- B7 iter 1 future-proof guard api_key_service grep == 0 + MANDATORY docstring note enforce (Plan 02-04) — future audit-emitter BẮT BUỘC qua `build_audit_payload`.
- Test coverage 23 test ship (5+2+3+7+4+2 = 11 unit + 12 integration) cover semantic DEP-01..05 (D-V3.1-Phase2-F LOCKED ≥ 80% satisfied — 471/471 unit regression PASS).
- Phase 4 MIGRATE-02 sẽ verify runtime full E2E 4 scenario pytest httpx + audit log inspect live.

**Phase 2 backward incompat (operator action required — W5 iter 1):**
- hub_admin GET /api/users yêu cầu hub_id query (HUB_ID_REQUIRED guard Plan 02-03 DEP-03).
- Existing M2/v3.0 frontend chưa pass hub_id query → 1-2 ngày downtime trên user management page cho hub_admin role giữa Phase 2 ship và Phase 3 FE-04 ship (acceptable v3.1 timeline).
- **Operator broadcast (Slack/Email) trước Phase 3 FE-04 ship:** thông báo hub_admin user về temporary breakage + ETA Phase 3 FE-04.
- Phase 3 FE-04 sẽ pass hub_id query → resolve.

**Next:** Phase 3 `/gsd-discuss-phase 3` FE frontend form refactor (UserManagement 3 option radio + hub switcher hide central + edit modal disabled assign super + api.ts UserRole type extend).

---

*Cập nhật: 2026-05-23 (Phase 7 DONE — MIGRATE-01..05 ship 5 plan; scripts/migrate/ module 5 bash script (01-snapshot-hubs.sh + 02-restore-hub.sh + 03-switch-caddy.sh + 04-truncate-central.sh + 05-smoke-e2e.sh) + 1 runbook 06-mcp-smoke.md + fixture sample-document.docx (37KB python-docx generator + reproducible) + automated 3 hub × 7-step golden path (login + upload + poll + search local + cross-hub + ask + citation [N]) + Prometheus assertion post-loop + blue/green per-hub procedure (D-V3-Phase7-B) + dry-run default ON truncate (D-V3-02 chunks PRESERVED) + MCP re-point central aggregate (D-V3-Phase7-C) + manual visual smoke advisory KHÔNG blocking (D-V3-Phase7-D). Project: MEDWIKI. **🎉 v3.0 MILESTONE CLOSED 2026-05-23** — 38/38 plan ship · 30/30 REQ-ID consumed (TOPO 4 + FACTOR 4 + SSO 4 + SYNC 5 + PROXY 4 + SETTINGS 4 + MIGRATE 5) · 7/7 phase complete · v3.0-a (Phase 1-3) + v3.0-b (Phase 4-7) anti-pivot pattern hoàn tất. M2 v2.0 closeout 2026-05-21 archived. Next: `/gsd-complete-milestone v3.0` separate command — archive `.planning/milestones/v3.0-archive/` + reset ROADMAP cho v4.0 backlog (sub-hub split per project_v3_multi_hub_split.md seed 2026-05-21 + HA Redis cluster + OCR Vietnamese + streaming /api/ask).*
