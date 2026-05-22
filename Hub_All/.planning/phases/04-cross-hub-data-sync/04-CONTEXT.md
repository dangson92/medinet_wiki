---
phase: 4
phase_name: Cross-hub Data Sync
slug: cross-hub-data-sync
milestone: v3.0
gathered: 2026-05-22
source: /gsd-discuss-phase 4 --chain (interactive — 4 gray area do user selected + sub-questions)
status: Ready for planning
---

# Phase 4: Cross-hub Data Sync — Context

**Gathered:** 2026-05-22
**Status:** Ready for planning
**Source:** `/gsd-discuss-phase 4 --chain` — interactive discussion 4 gray area do user chọn (GA-V3-D part 1 SYNC-05 mechanism + SYNC-02 idempotent key & timing + SYNC-04 failure mode & checksum + SYNC-03 cross-hub search refactor). Phase 4 mở v3.0-b sau v3.0-a EXIT GATE TRIGGERED 2026-05-22 (Phase 1+2+3 DONE).

---

<domain>
## Phase Boundary

**WHAT phase 4 ships:**

1. **Outbox + worker sync mechanism** — sau cocoindex flow hub con declare_row chunks → Postgres trigger AFTER INSERT/DELETE `chunks` enqueue `sync_outbox(op_type, chunk_id, payload, attempt_count, last_error, next_retry_at, processed_at)` cùng transaction (atomic). In-process asyncio worker trong lifespan hub con (`api/app/sync/worker.py` mới) poll outbox batch 100/5s + push central qua asyncpg pool dedicated (Settings.central_sync_dsn) + exp backoff 1/5/30/120s + max 5 attempts → mark dead + Prometheus alert.
2. **Idempotent push central** — `INSERT INTO chunks (...) VALUES ... ON CONFLICT (chunk_id) DO UPDATE SET content=EXCLUDED.content, content_hash=EXCLUDED.content_hash, vector=EXCLUDED.vector, ... WHERE chunks.content_hash IS DISTINCT FROM EXCLUDED.content_hash`. chunk_id stable UUID5 (carry forward `stable_chunk_id` rag/flow.py:85) đảm bảo re-index cùng nội dung KHÔNG duplicate. DELETE event push central DELETE chunk_id IN ($1).
3. **Sync timing async decoupled** — document.status=completed ngay sau cocoindex INSERT chunks (KHÔNG block đợi central). Thêm `document.sync_status` enum (pending/syncing/synced/failed/partial) cho dashboard transparency. Cross-hub search lag tối đa = worker poll interval (5s) + central RTT (~100ms).
4. **Checksum verify periodic** — Central FastAPI lifespan asyncio task (APScheduler-style):
   - **Daily 2AM**: full count `COUNT(*)` per hub con vs central WHERE hub_id=<> → metric `sync_count_drift{hub_id}`. Alert > 1% sustained 7 ngày → E-V3-5 trigger.
   - **Hourly**: 1% rolling sample `TABLESAMPLE BERNOULLI(1)` chunks created last 1h → verify content_hash match → metric `sync_hash_drift{hub_id, drift_type=mismatch|missing}`. Alert > 0 sustained 1h.
5. **Cross-hub search aggregated central (SYNC-03)** — Refactor `services/search_service.py::_search_cross_hub_impl` từ fan-out parallel `_search_one(hub_id)` per hub thành 1 SQL `SELECT ... FROM chunks WHERE hub_id = ANY($1::uuid[]) ORDER BY vector <=> $embedding LIMIT $k`. JWT `hub_ids` ∩ `body.hub_ids` (logic intersect SSO-03 carry forward). Public API `SearchService.search_cross_hub()` signature giữ NGUYÊN (backward compat M2 contract). Hub con strip `/api/search/cross-hub` mount (FACTOR-02 extend) — chỉ central handle aggregated query.
6. **hub_id UUID resolution** — Settings.hub_id field mới (UUID PGUUID, đọc từ env `HUB_ID` boot fail-loud). Hub con biết hub_id của chính nó cho INSERT/DELETE chunks. Operator deploy phải set HUB_ID khớp central.hubs row (carry forward M2 HUB-01).
7. **Prometheus metrics mới** — `sync_lag_seconds{hub_id}` (outbox enqueue → central processed_at), `sync_outbox_pending{hub_id}` gauge, `sync_attempt_total{hub_id, status=success|fail}` counter, `sync_dead_total{hub_id, error_class}` counter, `sync_count_drift{hub_id}` gauge, `sync_hash_drift{hub_id, drift_type}` counter.
8. **Admin replay endpoint central** — `POST /api/sync/replay { hub_id, since }` (admin RBAC + audit log) reset attempt_count + clear last_error + next_retry_at=NOW() cho dead row trong sync_outbox hub con qua remote DSN. Cho operator manual replay sau khi fix root cause.
9. **Alembic migration mới** — `chunks` table sửa schema: thêm `chunks.created_at` nếu chưa có (đã có), tạo `sync_outbox` table per-DB hub con (KHÔNG ở central), trigger `chunks_enqueue_sync_outbox` AFTER INSERT/DELETE, indexes ix_sync_outbox_pending + ix_sync_outbox_attempt. Per-hub Alembic (Phase 1 TOPO-02 carry forward) — central KHÔNG có sync_outbox.

**WHAT phase 4 KHÔNG ship:**

- **Migration data từ M2 medinet_central cũ** sang DB hub con (`pg_dump --where hub_id=`) — defer Phase 7 MIGRATE-01..03. Phase 4 chỉ handle sync forward cho chunks MỚI ingest sau deploy.
- **hub_registry sync xuống hub con** (SETTINGS-04 read-only TTL 5min) — defer Phase 6. Phase 4 dùng Settings.hub_id static env (operator deploy responsibility) thay vì pull từ central.
- **Caddy subpath routing `wiki.domain.com/<hub>/api/*`** — defer Phase 5 PROXY-01.
- **Frontend dashboard hiển thị sync_status + drift metrics** — defer Phase 5 PROXY-02 (D-V3-06 D6 expire formally).
- **MCP service re-point cross-hub aggregate** — defer Phase 7 MIGRATE-04.
- **Soft-delete chunks `deleted_at`** — KHÔNG triển khai. Chunks immutable (rag/flow.py docstring carry forward). DELETE event sync sang central HARD DELETE.
- **Smoke E2E 3 hub con + central golden path runtime** — defer Phase 7 MIGRATE-05.

</domain>

<decisions>
## Implementation Decisions

### A · Sync Mechanism (SYNC-05 / GA-V3-D part 1)

- **D-V3-Phase4-A1 · Mechanism = Outbox + worker (option c)** — REJECT (a) cocoindex target thứ 2 (lock-in + KHÔNG isolate failure khi central down → flow stall), REJECT (b) Postgres logical replication (schema drift sensitive, debug khó). Outbox = R-V3-1 sync drift HIGH mitigation rõ nhất (sync fail KHÔNG block ingest, retry exponential backoff, metrics rõ ràng).
- **D-V3-Phase4-A2 · Outbox table riêng `sync_outbox`** — per-DB hub con (KHÔNG ở central): `(id UUID PK, op_type TEXT enum 'insert'|'delete', chunk_id UUID, document_id UUID NULL, payload JSONB, attempt_count INT DEFAULT 0, last_error TEXT NULL, status TEXT enum 'pending'|'processing'|'processed'|'dead' DEFAULT 'pending', next_retry_at TIMESTAMPTZ NULL, created_at TIMESTAMPTZ DEFAULT NOW(), processed_at TIMESTAMPTZ NULL)`. Indexes: `ix_sync_outbox_pending (status, next_retry_at) WHERE status IN ('pending','processing')` partial cho worker query hot path, `ix_sync_outbox_chunk_id (chunk_id)` cho debug. Alembic migration mới (per-hub) owns DDL.
- **D-V3-Phase4-A3 · Worker placement = In-process asyncio task hub con lifespan** — KHÔNG separate worker container (over-engineer N hub), KHÔNG single central worker (SPOF). `api/app/sync/worker.py::sync_worker_loop()` spawned via `asyncio.create_task` ở lifespan startup sau cocoindex flow + graceful shutdown stop signal lifespan close. Hub con only (skip worker spawn nếu `settings.hub_name == "central"`).
- **D-V3-Phase4-A4 · Outbox write = Postgres trigger AFTER INSERT/DELETE chunks** — Alembic migration tạo function `enqueue_sync_outbox()` + trigger `chunks_after_insert` + `chunks_after_delete` (mỗi event 1 row outbox). Atomic với chunks INSERT (cùng transaction) — KHÔNG race. KHÔNG sửa cocoindex flow (`rag/flow.py` declare_row pattern giữ nguyên — Alembic owns DDL pattern Phase 1 carry forward).
- **D-V3-Phase4-A5 · Worker loop config** — `batch_size=100`, `poll_interval=5s` (idle khi outbox empty, tight loop khi batch >= 100), `backoff_seconds=[1, 5, 30, 120]` exp + 4th retry final attempt → mark dead, `max_attempts=5`. Config-driven Settings (`sync_batch_size`, `sync_poll_interval`, `sync_max_attempts`, `sync_backoff_base`) default Recommended option 1 — operator tune sau observe metrics. SELECT FOR UPDATE SKIP LOCKED (concurrency-safe).

### B · Idempotent Key + Sync Timing (SYNC-02)

- **D-V3-Phase4-B1 · ON CONFLICT (chunk_id) DO UPDATE WHERE content_hash IS DISTINCT FROM EXCLUDED.content_hash** — 1 statement atomic. chunk_id stable UUID5 carry forward `stable_chunk_id(doc_id, idx)` (rag/flow.py:85) đảm bảo determinism re-index cùng content. content_hash filter tránh UPDATE no-op (bảo vệ HNSW vector index từ disk write thừa). REJECT 2-statement INSERT...DO NOTHING + UPDATE (race window). REJECT ON CONFLICT (content_hash) (collision boilerplate header + redundant với chunk_id stable).
- **D-V3-Phase4-B2 · Sync timing = Async outbox decoupled** — `document.status=completed` ngay sau cocoindex INSERT chunks (KHÔNG đợi central push). Thêm `document.sync_status` enum (`pending`/`syncing`/`synced`/`failed`/`partial`) Alembic migration cho dashboard transparency. Worker update `document.sync_status` = `synced` khi ALL chunks của doc processed thành công, `failed` khi có chunk dead, `partial` khi mixed. Latency upload thấp + isolate failure (R-V3-1).
- **D-V3-Phase4-B3 · Outbox event-typed INSERT/UPDATE/DELETE** — `op_type` enum (`insert`/`delete`) cột trong sync_outbox. Trigger AFTER INSERT chunks → enqueue `insert` op (payload đầy đủ row JSONB). Trigger AFTER DELETE chunks → enqueue `delete` op (payload chỉ `{chunk_id}`). Worker push central: `insert` → INSERT ... ON CONFLICT UPDATE; `delete` → DELETE FROM chunks WHERE chunk_id IN ($1). CASCADE doc → chunks (FK existing) trả về N DELETE event per doc → batch worker xử lý 100/batch OK. Chunks immutable hard delete (KHÔNG soft-delete `deleted_at` — bảo toàn rag/flow.py contract).

### C · Failure Mode + Checksum Verify Cadence (SYNC-04)

- **D-V3-Phase4-C1 · Checksum cadence kết hợp = Daily 2AM full count + Hourly 1% rolling sample hash** — Daily: `SELECT COUNT(*) FROM chunks WHERE hub_id = '<>'` ở hub con vs central per hub_id → metric `sync_count_drift{hub_id}` gauge ratio. Hourly: `SELECT chunk_id, content_hash FROM chunks TABLESAMPLE BERNOULLI(1) WHERE created_at > NOW() - INTERVAL '1 hour'` ở hub con → verify central có cùng content_hash → metric `sync_hash_drift{hub_id, drift_type=mismatch|missing}` counter. Alert AlertManager: `count_drift > 1%` OR `hash_drift > 0 sustained 1h` → Slack/Email.
- **D-V3-Phase4-C2 · Failure handling = Mark dead + Prometheus alert + Manual replay endpoint** — sync_outbox row attempt_count >= 5 → UPDATE status='dead' + last_error=<truncated 1000 char stacktrace>. KHÔNG xóa (audit). Metric `sync_dead_total{hub_id, error_class}` counter. Central admin endpoint `POST /api/sync/replay { hub_id, since: "2026-05-22T00:00:00Z" }` (admin RBAC) reset dead rows attempt_count=0 + clear next_retry_at → worker re-pickup. document.sync_status=`failed` propagate UI hiển thị (defer Phase 5 PROXY-02 frontend dashboard render). REJECT retry-forever (outbox bloat systematic fail). REJECT DLQ table separate (over-engineer cho v3.0-b — status='dead' enum đủ).
- **D-V3-Phase4-C3 · Checksum runner placement = Central FastAPI lifespan asyncio task** — `api/app/observability/checksum_scheduler.py` mới spawn ở central lifespan startup. Naive `asyncio.sleep` loop với cron-like time check (KHÔNG cần APScheduler dep mới — simple loop OK cho 1 daily + 1 hourly job). Central connect tới TẤT CẢ hub con DB qua `Settings.checksum_hub_dsns: dict[str, str]` (read-only role per hub) — Settings field mới + docker-compose env `CHECKSUM_HUB_DSNS_JSON`. Hub con KHÔNG spawn (lifespan conditional `settings.hub_name == "central"`).

### D · Cross-hub Search Refactor (SYNC-03)

- **D-V3-Phase4-D1 · Refactor `search_cross_hub()` in-place: 1 SQL aggregated** — Thay `services/search_service.py::_search_cross_hub_impl()` fan-out parallel `_search_one(hub_id)` qua N task bằng 1 SQL: `SELECT id, document_id, hub_id, content, vector <=> $1 AS distance FROM chunks WHERE hub_id = ANY($2::uuid[]) AND (heading_path IS NOT NULL OR TRUE) ORDER BY vector <=> $1 LIMIT $k`. JWT `hub_ids` ∩ `body.hub_ids` (logic intersect SSO-03 đã có ở Phase 3). Giữ public API `SearchService.search_cross_hub()` signature KHÔNG đổi (backward compat M2 contract). Hub con KHÔNG mount `/api/search/cross-hub` (FACTOR-02 extend strip — central-only endpoint mới). M2 ask_service.py `search_cross_hub` consumer giữ nguyên call. HNSW index `ix_chunks_vector_hnsw` (cosine) + `iterative_scan=relaxed_order` + `ef_search=200` carry forward M2 Phase 6 — verify E-V3-2 p95 < 1.5s sau refactor.
- **D-V3-Phase4-D2 · hub_id resolution = UUID từ central.hubs table** — Settings.hub_id field mới (UUID, đọc từ env `HUB_ID` boot fail-loud cho hub con). Operator deploy responsibility set HUB_ID khớp `medinet_central.hubs.id` row UUID. Hub con `services/documents_service.py` set `chunks.hub_id = settings.hub_id` khi cocoindex flow declare_row (rag/flow.py `ChunkRow(hub_id=hub_id, ...)` đã có biến local — wire qua doc_row['hub_id']). Phase 6 SETTINGS-04 sẽ pull `hub_registry` xuống hub con TTL 5min cho dynamic refresh (KHÔNG cần ở Phase 4). REJECT hub_id = HUB_NAME string (phá schema PGUUID FK). REJECT compound key (duplicate data).
- **D-V3-Phase4-D3 · Strip `/api/search/cross-hub` ở hub con** — FACTOR-02 extend list central-only routers thêm `search_router` cross-hub endpoint (KHÔNG strip cả router — chỉ endpoint cross-hub). Pattern: tách `search_router_universal` (local /api/search) + `search_router_central` (cross-hub) hoặc inline `if settings.hub_name == "central"` decorator. Plan 04 chốt approach cụ thể.

### Claude's Discretion

- Implementation chi tiết Alembic migration sync_outbox schema (CHECK constraints, default values, comment columns).
- Worker class structure (`SyncWorker` class vs functional `sync_worker_loop`).
- Settings field defaults (hardcoded vs Settings constants).
- Test fixture patterns (TestClient + dual asyncpg pool — local + central mock vs testcontainer 2 Postgres instance).
- Prometheus metric label cardinality limits (max hub_id values, error_class normalize).
- Admin replay endpoint shape (path params vs body, GET vs POST trả lại danh sách dead trước replay).
- Specific PG TABLESAMPLE seed strategy + reproducibility cho hash sample verify.

### Folded Todos

Không có todo nào được fold vào scope Phase 4 — backlog đã review không relevant.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 4 spec & roadmap (LOCKED constraints)
- `.planning/REQUIREMENTS.md` §SYNC — 5 REQ-ID (SYNC-01..05) success criteria + GA-V3-D mechanism options.
- `.planning/ROADMAP.md` §Phase 4 — Goal, success criteria 5 SC, discuss-phase gray areas, Risk R-V3-1, Exit Criteria E-V3-2 + E-V3-5.
- `.planning/PROJECT.md` §"Key Decisions v3.0 LOCKED" D-V3-02 (chunks+vector denormalized 1 chiều, hub tổng KHÔNG re-embed).

### v3.0 milestone context
- `.planning/seeds/v3.0-multi-hub-split.md` §GA-V3-D — 2 option migration data backup; bối cảnh mechanism choice.
- `.planning/STATE.md` — v3.0-a EXIT GATE TRIGGERED 2026-05-22 (Phase 1+2+3 DONE) + Accumulated Context.

### Phase 1 (TOPO) carry forward
- `Hub_All/.planning/phases/01-multi-db-topology/01-CONTEXT.md` — Per-hub DSN validator pattern, Alembic per-hub env -x, cocoindex APP_NAMESPACE per-hub.
- `Hub_All/api/app/config.py::Settings._enforce_hub_dsn_match` — Boot-time fail-fast HUB_NAME ↔ DSN suffix match (E-V3-3 enforce).

### Phase 2 (FACTOR) carry forward
- `Hub_All/.planning/phases/02-hub-con-codebase-factor/02-CONTEXT.md` — `create_app()` conditional mount pattern, FACTOR-02 strip 9 central-only router.
- `Hub_All/api/app/main.py` — Conditional router mount + Starlette HTTPException handler 404 envelope D6.

### Phase 3 (SSO) carry forward
- `Hub_All/.planning/phases/03-auth-sso-hub-ids-jwt/03-CONTEXT.md` — JWKS + hub_ids JWT claim + E4 reinforced 3-layer.
- `Hub_All/api/app/auth/dependencies.py::get_current_user_for_hub_access` — Layer 3 enforce hub_ids check.

### Codebase artifacts (refactor targets)
- `Hub_All/api/app/rag/flow.py` — Cocoindex flow `medinet_<hub>_ingest`, ChunkRow dataclass, `stable_chunk_id` UUID5 namespace `8f1a3c6e-0000-4000-a000-0000007a3d1c`, `declare_row` pattern.
- `Hub_All/api/app/models/chunk.py` — Chunk SQLAlchemy model (vector Vector(1536), HNSW cosine index, content_hash BYTEA SHA-256).
- `Hub_All/api/app/services/search_service.py::SearchService._search_cross_hub_impl` (line 338+) — M2 fan-out logic, **refactor target SYNC-03**.
- `Hub_All/api/app/routers/sync.py` — M2 COMPAT STUB cho frontend D6 `/api/sync/*`; Plan 04 extend với endpoint replay mới (admin RBAC).
- `Hub_All/api/app/repositories/hub_isolation.py` — Hub isolation repo pattern E4.
- `Hub_All/api/alembic/` — Per-hub Alembic env-x pattern (Phase 1 Plan 01-03 carry forward).

### Risk + EXIT criteria
- `.planning/PROJECT.md` §"Risk Register v3.0" R-V3-1 HIGH (sync drift) + R-V3-2 (D6 expire defer Phase 5) + carry forward R1 (PIN 1536) + R2 (HNSW iterative_scan).
- `.planning/PROJECT.md` §"EXIT Criteria" E-V3-2 (cross-hub p95 < 1.5s) + E-V3-5 (drift > 1% sustained 7 ngày).

### v2.0 carry forward (search infrastructure)
- `Hub_All/.planning/milestones/v2.0-full-rag-rewrite/phases/06-search-api-single-cross-hub/` — Phase 6 M2 cross-hub fan-out pattern + Redis cache search_cache.py + HNSW iterative_scan + ef_search=200.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`stable_chunk_id(doc_id, idx) -> UUID5`** (rag/flow.py:85) — Deterministic chunk_id namespace fixed. Re-export sang `sync/keys.py` để worker dùng chung khi sinh INSERT payload.
- **`Chunk` model + `content_hash` BYTEA** (models/chunk.py:54) — SHA-256 hash field đã có; trigger `enqueue_sync_outbox` chỉ cần copy NEW.* hoặc OLD.* row JSONB.
- **`Settings._enforce_hub_dsn_match` validator** (config.py — Phase 1) — Pattern fail-fast boot mismatch. Phase 4 sẽ thêm tương tự `_enforce_hub_id_for_hub_con` + `_enforce_central_sync_dsn_for_hub` + `_enforce_checksum_hub_dsns_for_central` model_validator.
- **`get_current_user_for_hub_access` dependency** (auth/dependencies.py — Phase 3) — Layer 3 enforce hub_ids check. Reuse cho admin `/api/sync/replay` (chỉ central, admin role check).
- **`SearchService.search_cross_hub` public API** (services/search_service.py:319) — Signature giữ KHÔNG đổi (backward compat); only `_search_cross_hub_impl` private được refactor 1 SQL aggregated.
- **Alembic per-hub env-x pattern** (alembic/env.py — Phase 1 Plan 01-03) — Carry forward cho migration sync_outbox per-DB hub con (KHÔNG ở central).
- **`make migrate-all` target** (Hub_All/Makefile — Phase 1) — Apply migrations tuần tự N DB; Plan 04 migration thêm vào set.
- **Prometheus `/metrics` endpoint** (observability/metrics.py — M2 HARD-02) — Reuse cho 6 metric mới (sync_lag_seconds, sync_outbox_pending, sync_attempt_total, sync_dead_total, sync_count_drift, sync_hash_drift).
- **`asyncpg.Pool` lifecycle pattern** (db/session.py + main.py lifespan) — Reuse cho central_sync_pool (hub con pool tới central) + checksum_hub_pools (central pools tới N hub con).

### Established Patterns
- **In-process asyncio worker spawn ở lifespan** (cocoindex update_blocking pattern Plan 04-03 v2.0 + JWKSCache refresh task Plan 03-02) — `asyncio.create_task` + graceful shutdown signal.
- **Cocoindex 1.0.3 declare_row contract** — Flow KHÔNG sửa (`rag/flow.py:index_document` giữ nguyên); trigger Postgres làm sync hook outbox.
- **Conditional router mount theo `settings.hub_name`** (Phase 2 create_app pattern) — Phase 4 extend cho strip `/api/search/cross-hub` ở hub con + mount `/api/sync/replay` admin ở central only.
- **Envelope D6 `{success, data, error, meta}`** (pkg/response.py) — `POST /api/sync/replay` response shape + 503 fallback envelope nếu central pool down (carry forward Phase 3 JWKS_UNAVAILABLE pattern).
- **Settings model_validator pattern** (config.py — Phase 1/3 carry forward) — Boot-time fail-fast cho hub con required field.
- **TestClient + asgi-lifespan testing pattern** (tests/integration/conftest.py — Phase 2 hub_app_factory) — Reuse cho integration test sync flow E2E in-process (2 DSN mock central + hub con qua asyncpg fixture).
- **`request.state.jwt_claims` wire** (auth/dependencies.py — Phase 3 Plan 03-03) — Reuse cho audit log replay endpoint.

### Integration Points
- **Postgres trigger `enqueue_sync_outbox` function** — Alembic migration mới ở **hub con DB only** (`medinet_hub_<name>`), NOT central. Function INSERT INTO sync_outbox với row_to_json(NEW) payload + op_type=TG_OP.
- **`api/app/sync/` directory mới** — `worker.py` (loop), `keys.py` (re-export stable_chunk_id + outbox query helpers), `metrics.py` (Prometheus collectors), `models.py` (SyncOutbox SQLAlchemy + Pydantic schemas).
- **`api/app/observability/checksum_scheduler.py` mới** — Central only lifespan task.
- **`docker-compose.yml` env mới** — Hub con thêm `HUB_ID` + `CENTRAL_SYNC_DSN`; central thêm `CHECKSUM_HUB_DSNS_JSON`. `docker-compose.override.yml.template` (FACTOR-04) inherit qua sed substitute.
- **`Hub_All/Makefile` target mới** — `make sync-worker-run HUB=<name>` (dev standalone worker mode debug), `make sync-replay HUB=<name> SINCE=<iso>` (CLI admin replay).
- **`api/app/main.py::create_app` lifespan** — Conditional spawn:
  - Hub con: `sync_worker_task = asyncio.create_task(sync_worker_loop(app))`.
  - Central: `checksum_task = asyncio.create_task(checksum_scheduler_loop(app))`.
  - Shutdown: cancel tasks + await gather (KHÔNG block forever, timeout 10s).

</code_context>

<specifics>
## Specific Ideas

- **"Outbox + worker" naming convention** — table `sync_outbox` (KHÔNG `chunk_sync_queue` hay `sync_events`) để khớp với industry "outbox pattern" Lit reference (Microservices Patterns Chris Richardson).
- **"chunks immutable" preserve** — rag/flow.py docstring đã LOCK chunks immutable. Phase 4 KHÔNG add `deleted_at` soft-delete; DELETE event sync HARD DELETE central.
- **"document.sync_status" enum cho dashboard** — `pending` (chunks chưa ingest), `syncing` (chunks ingested local nhưng worker chưa push central), `synced` (all chunks confirmed central), `partial` (mixed), `failed` (1+ chunk dead). Dashboard hiển thị badge color (Phase 5 PROXY-02 frontend).
- **"Manual replay" thay vì auto-retry-forever** — Operator có visibility (Slack alert) + control (replay endpoint). Dead row giữ audit trail KHÔNG xóa.
- **"Central as scheduler authority"** — Checksum scheduler ở central tránh duplicate runs khi N hub con (KHÔNG cron per-hub-con — over-engineer).
- **"Outbox table per-hub-con (KHÔNG central)"** — Mỗi hub con maintain outbox riêng (pending data của chính mình). Central KHÔNG có outbox (KHÔNG re-export ra hub khác — D-V3-02 sync 1 chiều).

</specifics>

<deferred>
## Deferred Ideas

- **Soft-delete chunks `deleted_at`** — REJECTED. Chunks immutable.
- **DLQ table `sync_outbox_dlq` + auto-replay weekly** — REJECTED Phase 4 (over-engineer). Có thể revisit v4.0 nếu observe systematic fail patterns.
- **Per-hub-con worker self-verify push checksum report** — REJECTED (trust hub con report, cần endpoint mới). Central pull DSN model OK cho v3.0.
- **Separate `python-checksum-scheduler` container** — REJECTED (over-engineer 4 hub). In-process central OK.
- **hub_registry pull-down sang hub con TTL 5min** — Defer Phase 6 SETTINGS-04. Plan 04 dùng Settings.hub_id static.
- **Frontend dashboard sync_status badge + drift metrics chart** — Defer Phase 5 PROXY-02 sau D6 expire formally.
- **`/api/search/aggregated` endpoint mới tách khỏi `/api/search/cross-hub`** — REJECTED (refactor in-place giữ M2 API). Có thể revisit v4.0.
- **MCP service re-point cross-hub aggregate** — Defer Phase 7 MIGRATE-04.
- **Smoke E2E 3 hub con + central golden path runtime** — Defer Phase 7 MIGRATE-05 (carry forward pattern Phase 3 Plan 03-05 Task 5 SKIP pre-resolved).
- **Migration data v2.0 medinet_central existing chunks** — Defer Phase 7 MIGRATE-01..03 (`pg_dump --where hub_id`). Phase 4 chỉ handle sync forward chunks MỚI.

### Reviewed Todos (not folded)

Không có todo nào được review-but-deferred — backlog đã clean.

</deferred>

---

*Phase: 04-cross-hub-data-sync*
*Context gathered: 2026-05-22 qua `/gsd-discuss-phase 4 --chain` — 4 gray area do user select, 9 sub-decision D-V3-Phase4-A1..D3 LOCKED. Next: auto-advance `/gsd-plan-phase 4 --auto`.*
