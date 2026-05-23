# Milestones — MEDWIKI

Lịch sử các milestone đã chạy / abandon của dự án Medinet Wiki (Hub_All).

---

## v1.0 — RAG Quality with Docling — ❌ ABANDONED 2026-05-13

**Trạng thái khi abandon:** Code complete 100% (28 plans / 5 phase / 34 REQ), CHƯA runtime verify (chưa chạy `make eval-all`).

**Goal cũ:** Nâng chất lượng ingestion RAG bằng Docling (extract + chunk) trong service Python sidecar, gate top-3 retrieval ≥ 75% hoặc +15pp.

**Phases archive:** `.planning/milestones/v1.0-docling-rag/` chứa 5 phase + 1 backlog 999.1:

| # | Phase | Status | Commit cuối |
|---|---|---|---|
| 1 | Eval Dataset & Baseline Native | ✅ Completed | `f37cd96` |
| 2 | Docling Service (Python Sidecar) | 🟡 PARTIAL (8/8 plans code, smoke runtime defer) | — |
| 3 | Go Adapter & Pipeline Wiring | ✅ Completed (5/5 plans, 8/8 REQ) | `c7aa5b3` |
| 4 | Config Hot-Swap & Circuit Breaker | ✅ Completed (5/5 plans, 7/7 REQ) | `b52ec08` |
| 5 | Eval Compare & Quality Gate | ✅ Completed (5/5 plans, 4/4 REQ) | `3f54aee` |
| 999.1 | Incremental chunk re-embed (backlog) | Absorbed into M2 (cocoindex core value) | — |

**Lý do abandon (2026-05-13):**
- User quyết định pivot toàn bộ RAG sang **cocoindex** ([github.com/cocoindex-io/cocoindex](https://github.com/cocoindex-io/cocoindex)) v1.0.3+ thay vì Docling+Go tự build.
- Đi kèm rewrite backend Go → Python FastAPI (mục tiêu codebase đồng nhất).
- Migrate vector store ChromaDB → Postgres pgvector (bớt service, dùng Postgres sẵn có).
- M1 chưa chạy production (chỉ commit code, chưa user upload thật), không cần data migration.

**Code sẽ bị xóa trong M2 Phase 1:**
- `Hub_All/docling-pipeline/` (Python sidecar Docling)
- `Hub_All/eval/` (eval scripts cũ)
- `Hub_All/backend/internal/rag/`
- `Hub_All/backend/internal/embedding/`
- `Hub_All/backend/internal/llm/`
- `Hub_All/backend/internal/vectorstore/`
- `Hub_All/backend/internal/worker/`
- `Hub_All/backend/internal/storage/`
- Toàn bộ backend Go sau khi đã port logic sang FastAPI (M2 Phase cuối)

**Giá trị giữ lại từ M1:**
- Decision log + research Docling vs alternatives (lưu trong git history)
- Schema documents/hubs/users/audit_logs Postgres (giữ + migrate)
- Frontend React 19 (KHÔNG đổi)
- Knowledge: yêu cầu OCR tiếng Việt + table preservation cho scanned PDF y tế (sẽ ghi vào REQUIREMENTS M2 dưới dạng risk + open question)

**Pivot lần thứ 2:** Trước đó M1 đã pivot một lần từ "Multi-subdomain SPA" sang "RAG Quality with Docling" (2026-04-28). Lần này (2026-05-13) là pivot thứ 2 trong vòng 15 ngày — cần lưu ý về tốc độ thay đổi định hướng và rủi ro thrash.

---

## v2.0 — Full RAG Rewrite (CocoIndex + Python FastAPI + pgvector) — ✅ SHIPPED 2026-05-21

**Status:** 100% COMPLETE — 13 phase / ~75 plan / 38/38 REQ-ID done. Tag `v2.0` (annotated, local — push remote defer user trigger). Archive: `.planning/milestones/v2.0-full-rag-rewrite/`.

**Goal:** Xóa toàn bộ stack RAG + backend Go hiện hữu, viết lại bằng **Python FastAPI + cocoindex v1.0.3+ + pgvector**. CocoIndex sở hữu indexing dataflow; FastAPI handle auth/hub/user/audit/search/ask; MCP server expose RAG tool cho AI client ngoài.

**Calendar:** Created 2026-05-13 → Shipped 2026-05-21 (~8 ngày calendar AI-assisted; M2a Phase 1-4 trong 2 ngày 13-14/05, M2b Phase 5-10 + 8.1/8.2/8.3 trong 5 ngày 17-21/05).

**Git range:** `db30528` (08.3 audit seed) → `2669cd4` (Plan 10-06 ship) — 55 commits trong session closeout cuối. Tổng commit M2 nhiều hơn (full range từ 2026-05-13).

### Phases shipped (13/13 ✅)

| # | Phase | Plans | Status | Completed |
|---|---|---|---|---|
| 1 | Infra Skeleton + Demolition + EXIT Criteria | 6/6 | ✅ | 2026-05-13 |
| 2 | Database Schema + Alembic Baseline | 5/5 | ✅ | 2026-05-13 |
| 3 | Auth Port + RBAC + Response Envelope | 5/5 | ✅ | 2026-05-14 |
| 4 | CocoIndex Flow MVP + Document Ingest | 8/8 | ✅ M2a EXIT GATE PASSED | 2026-05-21 |
| 5 | Hub + User + Audit + APIKey + Settings CRUD | 6/6 | ✅ | 2026-05-17 |
| 6 | Search API Single + Cross-Hub | 4/4 | ✅ | 2026-05-18 |
| 7 | Ask API + LiteLLM + Citation + Hot-Swap + Usage | 5/5 | ✅ | 2026-05-18 |
| 8 | Frontend E2E Smoke (TEARDOWN-01 pull-in 2026-05-14) | 5/5 | ✅ (human UAT 3 SC) | 2026-05-19 |
| 8.1 | MCP Server — Expose Wiki Tools | 3/3 | ✅ (human UAT SC1/SC5) | 2026-05-19 |
| 8.2 | MCP Service — Tách Process Độc Lập | 5/5 | ✅ (human UAT SC4) | 2026-05-19 |
| 8.3 | MCP OAuth 2.0 + Deploy Public HTTPS | 9/9 | ✅ (human UAT domain thật) | 2026-05-21 |
| 9 | Eval Framework + Quality Gate ≥75% top-3 | 5/5 | ✅ (gate verdict OpenAI key thật = human UAT) | 2026-05-21 |
| 10 | Hardening + Observability + Docs | 6/6 | ✅ | 2026-05-21 |

### Key accomplishments

1. **Backend rewrite Go → Python FastAPI** — JWT RS256 (PKCS#8) + Argon2 cross-compat Go params `m=65536,t=3,p=4` (DOC-BUG fix: prev REQUIREMENTS ghi `t=1,p=2` SAI; Go source là source of truth) + envelope `{success,data,error,meta}` + RBAC `require_role` + Redis SETNX refresh-race lock + async session pool lifespan-managed.
2. **CocoIndex 1.0.3 ingest dataflow** — extract whitelist + scanned PDF → `failed_unsupported` (R4) + chunk VN regex + LiteLLM embed dim 1536 (R1 + R7 hot-swap) + pgvector HNSW + content-hash incremental dedup + `BackgroundTasks` thay LISTEN/NOTIFY (cocoindex 1.0.3 KHÔNG support) + heartbeat watchdog 300s + race pool A/B vá Plan 04-08; M2a EXIT GATE demo PASS.
3. **pgvector + HNSW search single + cross-hub** — `vector_cosine_ops` + `ef_search=200` + `iterative_scan=relaxed_order` + Redis cache TTL 5' hub-tagged Pub/Sub invalidate; E4 hub-isolation 6/6 critical PASS Phase 5/6.
4. **Ask API + LiteLLM citation** — `[N]` map deterministic chunk_id + anti-injection prompt + cross-hub + hot-swap within dim 1536 (cross-dim REFUSE 400) + token usage `BackgroundTasks` ghi `usage_events`; integration 18 test / 11 critical PASS.
5. **MCP server cho AI client ngoài** — Phase 8.1 in-process FastMCP 3 tool `search_wiki`/`ask_wiki`/`list_hubs` → Phase 8.2 đảo D-04 tách process `mcp_service/` gọi API HTTP → Phase 8.3 OAuth 2.0 + DCR + Caddy auto-TLS + 9 plan (4 gốc + 5 gap closure audit 2026-05-21 đóng CRIT-01 CORS split + HIGH-02 refresh-family revoke + HIGH-03 concurrency lock); mcp_service 135/135 PASS.
6. **Eval framework Python pytest** — `make eval-smoke` mock <60s + `make eval-all` real LLM gate verdict + `report.py` 7 section EVAL.md + `gate_verdict(top_3)` dict 3 field (≥0.75 PASS / 0.60-0.75 FAIL / <0.60 trigger E5) + pytest smoke regression CI gate `pytest -m critical api/tests/integration/test_eval_pipeline.py` < 60s zero external dep.
7. **Hardening + observability + docs** — structlog JSON 10 field match Go log/slog + ContextVar `request_id` propagate qua `asyncio.create_task` copy_context + Prometheus `/metrics` 5 metric + critical-path coverage 57.75% ≥50% gate + GitHub Actions `test.yml` 7 step `--cov-fail-under=50` hardcode + `lint.yml` secret detection guard 3 pattern + README + DEPLOY 7 section backup 6 artifact + 2 .env.example + CLAUDE.md M2 closeout section + CONVENTIONS Plan 10-01 note.
8. **Demolition M1 (TEARDOWN-01)** — `Hub_All/backend/` Go pull-in xoá sớm 2026-05-14 theo user decision (git tag `m1-go-archived` backup); `docling-pipeline/` + `eval/` cũ xoá Phase 1; ChromaDB hoàn toàn không reference.

### Issues encountered & resolutions

- **Argon2 doc-bug** (Plan 03-03): REQUIREMENTS/PITFALLS/CLAUDE ghi `t=1,p=2` SAI; Go source `backend/internal/pkg/hash/argon2.go:13-19` là source of truth `t=3,p=4` → fix in-place + production seed hash verify prefix `$argon2id$v=19$m=65536,t=3,p=4$`.
- **CocoIndex 1.0.3 actual API khác research** (Phase 4): `cocoindex.sources.Postgres(notification=PostgresNotification(...))` không tồn tại → REVISION 2 dùng `coco.App + VectorSchema + mount_table_target` + `BackgroundTasks trigger_cocoindex_update` chạy `cocoindex_app.update_blocking()` ngay sau response 202.
- **Race pool A/pool B** (Plan 04-08, debug session 2026-05-21 `cocoindex-zero-chunks-docx-vn`): SQLAlchemy commit pool A vs cocoindex asyncpg pool B REPEATABLE READ snapshot → initial delay 0.1s + retry loop max 3 attempts linear backoff trong `trigger_cocoindex_update`.
- **mcp 1.27.1 thay 1.9.4** (Phase 8.1 LANDMINE): `combine_lifespans` không tồn tại upstream → tự viết `_composed_lifespan`; pin `mcp>=1.27.0,<1.28`.
- **OAuth audit 2026-05-21** (Phase 8.3): sau 12 hot-fix phát hiện 3 Critical mới (CORS double-add path-prefix + cross-client code exchange + DCR redirect_uri whitelist) → 3 plan gap closure 08.3-07/08/09 đóng tất cả, mcp_service 135/135 PASS, pytest -m critical 17/17 PASS.
- **CRIT-01 CORS allow_origins=`*` cho /token /authorize /revoke** (Phase 8.3 audit): tách `MultiPolicyCORSMiddleware` ASGI metadata wildcard `*` vs sensitive whitelist origin từ `mcp_oauth_sensitive_allowed_origins` (default 4 origin: claude.ai + Inspector + 2 localhost:6274); Plan 10-04 đóng.

### Known deferred items (recorded — KHÔNG block close)

| Type | Item | Tracker |
|---|---|---|
| HUMAN UAT | Phase 9 gate verdict ≥75% top-3 với OpenAI key thật (~$0.20/run) | Track standalone `make eval-all` |
| HUMAN UAT | Phase 8.3 — kết nối Claude web "Add custom connector" tới domain MeWiki MCP thật | `08.3-HUMAN-UAT.md` |
| HUMAN UAT | Phase 8 — render 11 trang React + citation `[1]` clickable + docker compose 5-service healthy | `08-HUMAN-UAT.md` |
| HUMAN UAT | Phase 8.1 SC1/SC5 + Phase 8.2 SC4 (`usage_events` E2E thật) | `08.1-HUMAN-UAT.md` + mcp_service README |
| Tech debt | Migrate service module log cũ sang `structlog.get_logger` (Plan 10-01 chỉ HARD-01 ship) | DEF-10-01-B → v4.0 |
| Tech debt | Branch protection rule GitHub repo enforce 2 workflow trước merge main | Cần admin permission → v4.0 |
| Tech debt | Push tag `v2.0` lên remote | Defer user trigger sau verify |

> **CRIT-01 status:** ✅ Đã ĐÓNG Plan 10-04 (2026-05-21) — KHÔNG còn defer.

### Key decisions (carry forward to v3.0)

- **D-V3-01..04 LOCKED 2026-05-21:** Multi-DB cùng instance + chunks+vector sync 1 chiều + milestone-level scoping + M2 closeout precondition.
- **Anti-pivot R3 mitigation success:** E1-E5 EXIT criteria không trigger; M2a EXIT GATE PASSED; weekly check-in (day 7/14/21/28) achieve trước thời hạn.

Full archive: `.planning/milestones/v2.0-full-rag-rewrite/ROADMAP.md` + `REQUIREMENTS.md`.

---

## v3.0 — Multi-Hub Split — ✅ SHIPPED 2026-05-23

**Status:** 100% COMPLETE — 7 phase / 38 plan / 30 REQ-ID consumed (TOPO 4 + FACTOR 4 + SSO 4 + SYNC 5 + PROXY 4 + SETTINGS 4 + MIGRATE 5). Tag `v3.0` annotated. Archive: `.planning/milestones/v3.0-multi-hub-split/`.

**Goal:** Tách hub con (y_te, dược, HCNS) từ multi-tenancy LOGICAL → PHYSICAL — mỗi hub có process + Postgres database riêng cùng instance; central aggregator nhận chunks + vector qua outbox sync 1 chiều; URL subpath `wiki.domain.com/<hub>`.

**Calendar:** Started 2026-05-21 → Shipped 2026-05-23 (~3 ngày calendar AI-assisted; v3.0-a Phase 1-3 trong 2 ngày 21-22/05, v3.0-b Phase 4-7 trong 2 ngày 22-23/05).

### Phases shipped (7/7 ✅)

| # | Phase | Plans | REQ-ID | Completed |
|---|---|---|---|---|
| 1 | Multi-DB Topology + Per-hub Alembic | 5/5 | TOPO-01..04 | 2026-05-21 |
| 2 | Hub-con Codebase Factor | 5/5 | FACTOR-01..04 (+04 added 2026-05-22) | 2026-05-22 |
| 3 | Auth SSO + hub_ids trong JWT | 5/5 | SSO-01..04 | 2026-05-22 |
| 🚦 | **v3.0-a EXIT GATE** | — | — | TRIGGERED 2026-05-22 → user accept tiếp tục v3.0-b |
| 4 | Cross-hub Data Sync | 7/7 | SYNC-01..05 | 2026-05-22 |
| 5 | Reverse Proxy + Frontend Subpath | 6/6 | PROXY-01..04 | 2026-05-23 |
| 6 | System Settings Sync | 5/5 | SETTINGS-01..04 | 2026-05-23 |
| 7 | Migration + Smoke E2E | 5/5 | MIGRATE-01..05 | 2026-05-23 |

### Key accomplishments

1. **Multi-DB topology** — Postgres init script idempotent tạo N+1 logical DB cùng instance (`medinet_central` + `medinet_hub_<name>`) + per-hub Alembic migration set khớp head SHA + cocoindex flow naming per-hub + HUB_NAME env DSN isolation enforce DB-level (E-V3-3).
2. **Codebase factor 1 deploy nhiều lần** — `create_app()` factory no-arg đọc `settings.hub_name` conditional mount (7 universal + 9 central-only router) + docker-compose YAML anchor 4 service dedicated + dynamic hub registration (FACTOR-04) `make hub-add HUB=<name>` regex + RESERVED blacklist + override.yml.template sed substitute zero-downtime caddy reload.
3. **Auth SSO + JWKS + Layer 3 enforcement** — central JWKS endpoint RFC 7517 + hub con JWKSCache in-process LRU TTL 1h refresh + 24h hard limit fail-loud + JWT `aud=["medinet-wiki"]` + `hub_ids: list[str]` REQUIRED + `auth:blacklist:{jti}` Redis chung + `get_current_user_for_hub_access` dependency 403 CROSS_HUB_ACCESS_DENIED stale JWT.
4. **Cross-hub data sync outbox + worker** — `sync_outbox` table per-hub + Postgres trigger AFTER INSERT/DELETE chunks atomic + asyncio worker hub con `SELECT FOR UPDATE SKIP LOCKED` batch 100/5s + `ON CONFLICT (id) DO UPDATE WHERE content_hash IS DISTINCT` idempotent + exp backoff [1,5,30,120]s + 6 Prometheus metric (`sync_lag_seconds/outbox_pending/attempt_total/dead_total/count_drift/hash_drift`) + admin `POST /api/sync/replay` recovery + checksum scheduler daily/hourly.
5. **Cross-hub search 1 SQL aggregated** — `_search_cross_hub_impl` refactor từ fan-out `asyncio.gather` → 1 SQL `WHERE c.hub_id = ANY($2::uuid[]) ORDER BY vector <=> $1::vector` re-rank tự nhiên + HNSW `iterative_scan=relaxed_order` + `ef_search=200` + `max_scan_tuples=20000` carry forward M2. Public API signature unchanged backward compat M2.
6. **Reverse proxy subpath + frontend 1 build** — Caddy `path_regexp hub_api ^/({HUBS}|)/api/(.*)$` + `uri strip_prefix /{re.hub_api.1}` + `reverse_proxy http://python-api-{re.hub_api.1}:8080` (port STATIC anti SSRF) + frontend module-level runtime detect `window.location.pathname` → `PREFIX/API_BASE/APP_BASE/CURRENT_HUB` + `BrowserRouter basename` auto-prepend. D6 EXPIRED formally. Per-hub branding registry Vite glob 4 hub + inline CSS var `--hub-theme` + WCAG 1.4.11 mitigation hcns amber.
7. **System settings sync hybrid** — HTTP pull on-demand + Redis cache TTL 60s/300s/60s + pub/sub invalidate channel `settings:invalidate` Pydantic Literal enum payload (< 1s thực tế propagate vs E-V3-4 < 30s threshold) + 3 client class (RagConfigClient + HubRegistryClient + ApiKeyVerifyClient) + shared secret header `X-Internal-Auth` 32-char `hmac.compare_digest` constant-time + 6 Prometheus metric mới.
8. **Migration blue/green per-hub** — `scripts/migrate/` 5 bash script (01-snapshot pg_dump --where + 02-restore + 03-switch-caddy verify-only + 04-truncate dry-run default + 05-smoke-e2e automated 3 hub × 7-step golden path) + 06-mcp-smoke runbook 5-step Inspector OAuth + fixture sample-document.docx 37KB Vietnamese y tế (python-docx reproducible). MCP re-point central aggregate 1-line config + 143/135 mcp_service test regression. D-V3-02 chunks PRESERVED invariant strict (10+ explicit reference truncate script).

### Issues encountered & resolutions

- **BLOCKER 1 (Plan 04-01):** `documents.sync_status` initial state `'pending' → 'syncing'` không idempotent — fix UPDATE guard `WHERE sync_status='pending'` D-V3-Phase4-B2 lifecycle.
- **BLOCKER 2 (Plan 04-01/03):** Postgres trigger `to_jsonb(NEW)` fail pgvector serialization — fix explicit `jsonb_build_object` field + `NEW.vector::float4[]` cast + `encode(content_hash, 'hex')` 64 char; ChunkPayload `content_hash` field_validator mode=before decode hex string → bytes.
- **T-06-04-04 race redis lazy init (Plan 06-04):** M2 `from_url()` lazy assign object trước ping; ping fail → `app.state.redis` non-None NHƯNG `redis_ready=False` → subscriber spawn broken connection infinite reconnect hang — fix subscriber spawn guard `redis is not None AND redis_ready` (Rule 3 inline auto-fix).
- **Caddyfile dynamic regex Plan 07-02 correction:** Phase 5 đã ship `{re.hub_api.1}` dynamic capture → Phase 7 chỉ cần container `python-api-<HUB>` running → Caddy auto-route. `03-switch-caddy.sh` shrink từ sed edit phức tạp → verify-only ~132 LOC.

### Known deferred items (recorded — KHÔNG block close)

| Type | Item | Tracker |
|---|---|---|
| Debug | podman-init-admin-issue (WSL Windows env-specific) | STATE.md Deferred Items |
| UAT | Phase 06 HUMAN-UAT partial — visual smoke runtime | Defer ops handover |
| Verification | Phase 06 VERIFICATION human_needed | Defer ops handover |
| Seed | SEED-001 local embedding model (HuggingFace sentence-transformers) | v4.1 backlog dormant |
| Tech debt | RBAC role-per-hub (gap thiết kế — user request fix 2026-05-23) | **v3.1 next milestone** |
| Tech debt | Visual regression smoke 4 hub × 11 trang React M2 COMPAT-01 | Defer ops handover post-v3.0 |

> **RBAC hub_admin gap:** Phát hiện 2026-05-23 sau v3.0 close — `users.role` GLOBAL super-admin bypass hub isolation; user yêu cầu proper fix thêm role `hub_admin`. Phase v3.1 next.

### Key decisions (carry forward to v3.1)

- **6 D-V3-01..06 LOCKED 2026-05-21** carry forward — multi-DB cùng instance + chunks+vector sync 1 chiều + milestone-level scoping + M2 closeout precondition + phase numbering reset + D6 expire formally Phase 5.
- **38 D-V3-Phase{2..7}-X LOCKED 2026-05-22..23** documented in archive `milestones/v3.0-multi-hub-split/ROADMAP.md`.
- **Anti-pivot pattern success:** v3.0-a/v3.0-b split + EXIT GATE giữa Phase 3-4 user accept → never pivot multi-DB topology. R-V3-1..6 mitigation effective; E-V3-1..5 không trigger.

Full archive: `.planning/milestones/v3.0-multi-hub-split/ROADMAP.md` + `REQUIREMENTS.md`.

---

## Milestones tương lai (sau v3.0)

### v3.1 — RBAC hub_admin (NEXT 2026-05-23 — user request)

**Goal:** Đóng gap RBAC role-per-hub được defer v4.0 trong M2. Thêm role `hub_admin` quản lý 1 hub cụ thể (không phải super-admin toàn hệ thống). User được assign hub nào CHỈ quản lý hub đó.

**Trigger:** `/gsd-new-milestone v3.1` (user đã accept 2026-05-23).

**Scope estimate:** ~4 phase / ~12-18 plan — DB migration `role_enum` + backend `require_hub_admin_for(hub_id)` dependency + frontend form refactor + migration script seed existing admin.

Memory reference: `project_rbac_hub_admin_gap.md`.

### v3.0 — Multi-Hub Split (SEEDED 2026-05-21 — chờ trigger)

> **NOTE:** Section này là seed cũ trước khi v3.0 chạy. Giữ làm lịch sử. v3.0 đã SHIPPED 2026-05-23 (xem section trên).


**Goal redefine:** Tách hub con (y_te, dược, HCNS) sang multi-tenancy PHYSICAL — mỗi hub con có process + Postgres database riêng cùng 1 instance, hub tổng aggregator nhận chunks + vector sync 1 chiều. URL subpath `wiki.domain.com/<ten_hub>` thay subdomain (đảo PRD v1.3 cũ).

**Trigger condition:** `/gsd-new-milestone v3.0` sau khi user verify v2.0 closeout (HUMAN UAT Phase 9 gate verdict ≥75% + retrospective).

**4 D-V3 LOCKED 2026-05-21:** multi-DB cùng instance + chunks+vector denormalized sync 1 chiều + milestone-level scoping + M2 closeout precondition.

**4 GA-V3 open question:** Auth SSO design + system settings sync + reverse proxy prefix detect + migration data từ `medinet_central` cũ.

Seed full: `.planning/seeds/v3.0-multi-hub-split.md` (7 phase ~35 plan + 4 R-V3 risk + 4 E-V3 exit criteria).

### v4.0 — Production Hardening + Advanced RAG (Backlog)

MCP Server đã ship trong v2.0 (Phase 8.1/8.2/8.3) → v4.0 còn lại: OCR Vietnamese revisit nếu user feedback regress + cross-dim embedding swap 1536↔3072 + streaming `/api/ask` SSE + comprehensive coverage >80% + cocoindex augmenter Q&A pair gen + Postgres pg17 upgrade + email send + avatar upload S3/GCS + GDrive file storage backend + khắc phục CONCERNS bảo mật cũ (`.gitignore` root, GCP key audit, AES_KEY rotation, XSS token storage migration httpOnly cookie) + branch protection GitHub repo.

### v4.1+ — Advanced RAG

Hybrid retrieval BM25 + reranker (Cohere / cross-encoder) + version history & concurrent editing + local embedding model (sentence-transformers / BGE-M3 cho on-prem).

---

*Last updated: 2026-05-21 (M2 v2.0 SHIPPED 100% COMPLETE 38/38 REQ-ID; v3.0 SEEDED chờ trigger)*
