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
| 6 — System Settings Sync | 📋 Backlog | — | — | SETTINGS-01..04 |
| 7 — Migration + Smoke E2E | 📋 Backlog | — | — | MIGRATE-01..05 |

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

---

*Cập nhật: 2026-05-23 (Phase 5 DONE — PROXY-01..04 ship 6 plan; Caddy wiki block + path_regexp + handle_path strip + reverse_proxy hub upstream + central /api + frontend prefix detect 1 build + KNOWN_HUBS allowlist + BrowserRouter basename + Branding registry import.meta.glob 4 hub + WCAG contrast helper hcns + Login 4-state machine + Layout sidebar swap + crossHubSearch absolute path + tryRefresh redirect:'follow' + hub-add.sh 9-step pipeline. Project: MEDWIKI. M2 v2.0 done; v3.0 Multi-Hub Split — Phase 1+2+3+4+5 DONE (28/~32 plan ≈ 88%), v3.0-a EXIT GATE TRIGGERED + v3.0-b mid-flight (2/4 phase). Next: `/gsd-discuss-phase 6` System Settings Sync (SETTINGS-01..04 — rag_config HTTP pull + Redis pub/sub invalidate + api_keys proxy + hub_registry read-only).*
