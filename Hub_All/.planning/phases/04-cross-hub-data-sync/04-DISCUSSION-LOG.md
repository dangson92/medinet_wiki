# Phase 4: Cross-hub Data Sync — Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in `04-CONTEXT.md` — this log preserves the alternatives considered.

**Date:** 2026-05-22
**Phase:** 04-cross-hub-data-sync
**Command:** `/gsd-discuss-phase 4 --chain`
**Areas discussed:** Sync mechanism (SYNC-05), Idempotent key + sync timing (SYNC-02), Failure mode + checksum cadence (SYNC-04), Cross-hub search refactor (SYNC-03)

---

## Gray area selection

| Gray area | Selected |
|---|---|
| Sync mechanism (SYNC-05, GA-V3-D part 1) | ✓ |
| Idempotent key + sync timing (SYNC-02) | ✓ |
| Failure mode + checksum verify cadence (SYNC-04) | ✓ |
| Cross-hub search refactor scope (SYNC-03) | ✓ |

User chọn cả 4 gray area.

---

## Area 1 — Sync mechanism (SYNC-05)

### Q1.1 · Mechanism choice

| Option | Description | Selected |
|---|---|---|
| (c) Outbox + worker | Transactional INSERT outbox local + async worker push central + R-V3-1 mitigation | ✓ |
| (a) Cocoindex target thứ 2 | Lock-in cocoindex, multi-target same flow | |
| (b) Postgres logical replication | Native CDC, schema drift sensitive | |

**User's choice:** (c) Outbox + worker (Recommended)
**Notes:** R-V3-1 sync drift HIGH mitigation rõ nhất; sync fail KHÔNG block ingest.

### Q1.2 · Outbox table layer

| Option | Description | Selected |
|---|---|---|
| Outbox table riêng `sync_outbox` | Alembic owns DDL, full audit | ✓ |
| Reuse `chunks.sync_status` column | Mixed concern | |
| Postgres LISTEN/NOTIFY trigger | NOTIFY KHÔNG persist | |

**User's choice:** sync_outbox table riêng
**Notes:** Per-hub-con Alembic migration; central KHÔNG có outbox.

### Q1.3 · Worker placement

| Option | Description | Selected |
|---|---|---|
| In-process asyncio task hub con lifespan | Đơn giản deploy, share lifecycle | ✓ |
| Separate worker container | Over-engineer cho N hub | |
| Single central worker pull all hubs | SPOF, phá độc lập | |

**User's choice:** In-process asyncio task hub con lifespan
**Notes:** Hub con only (skip nếu hub_name == "central").

### Q1.4 · Outbox write trigger

| Option | Description | Selected |
|---|---|---|
| Postgres trigger AFTER INSERT chunks | Atomic same transaction, Alembic owns DDL | ✓ |
| Wrapper @coco.fn declare_chunk_with_outbox | Đụng cocoindex contract | |
| Hook post-flow callback | Race condition risk | |

**User's choice:** Postgres trigger AFTER INSERT chunks (+ AFTER DELETE)
**Notes:** Function `enqueue_sync_outbox()` + trigger `chunks_after_insert` + `chunks_after_delete`.

### Q1.5 · Worker loop config

| Option | Description | Selected |
|---|---|---|
| Batch 100 + poll 5s + exp backoff 1/5/30/120s + max 5 attempts | Balanced default | ✓ |
| Batch 50 + poll 2s + linear backoff max 3 attempts | Aggressive fail-fast | |
| Batch 500 + poll 30s + exp backoff max 10 attempts | Throughput cao, latency cao | |
| Settings configurable | Operator tune | |

**User's choice:** Batch 100 + poll 5s + exp backoff 1/5/30/120s + max 5 attempts (Recommended)
**Notes:** Config-driven Settings (`sync_batch_size`, `sync_poll_interval`, `sync_max_attempts`, `sync_backoff_base`) — default Recommended option 1. SELECT FOR UPDATE SKIP LOCKED concurrency-safe.

---

## Area 2 — Idempotent key + sync timing (SYNC-02)

### Q2.1 · Idempotent key + ON CONFLICT clause

| Option | Description | Selected |
|---|---|---|
| ON CONFLICT (chunk_id) DO UPDATE WHERE content_hash khác | 1 statement atomic | ✓ |
| ON CONFLICT (chunk_id) DO NOTHING + separate UPDATE | 2 statements race window | |
| ON CONFLICT (content_hash) DO NOTHING | Collision boilerplate, redundant | |

**User's choice:** ON CONFLICT (chunk_id) DO UPDATE WHERE content_hash IS DISTINCT FROM EXCLUDED.content_hash
**Notes:** chunk_id stable UUID5 carry forward stable_chunk_id (rag/flow.py:85). content_hash filter bảo vệ HNSW index từ UPDATE no-op.

### Q2.2 · Sync timing + document status

| Option | Description | Selected |
|---|---|---|
| Async outbox decoupled: document.status=completed ngay sau chunks INSERT | Latency thấp, isolate failure | ✓ |
| Synchronous: status=completed CHỈ sau push central OK | Strong consistency, latency cao | |
| Hybrid timeout fallback | Phức tạp 2 path | |

**User's choice:** Async outbox decoupled
**Notes:** Thêm `document.sync_status` enum (pending/syncing/synced/failed/partial) cho dashboard transparency.

### Q2.3 · DELETE handling

| Option | Description | Selected |
|---|---|---|
| Outbox event-typed INSERT/UPDATE/DELETE | Hard delete central, audit | ✓ |
| Soft-delete chunks deleted_at | Phá chunks immutability | |
| Bỏ qua DELETE ở v3.0-b | Stale chunks bloat, citation broken | |

**User's choice:** Outbox event-typed (op_type enum) + trigger AFTER DELETE chunks
**Notes:** Chunks immutable carry forward; HARD DELETE central.

---

## Area 3 — Failure mode + checksum cadence (SYNC-04)

### Q3.1 · Checksum verify cadence

| Option | Description | Selected |
|---|---|---|
| Daily 2AM full count + Hourly 1% rolling sample hash | Broad coverage + targeted | ✓ |
| Hourly 1% rolling sample only | Miss bulk drift | |
| Daily 2AM full count + hash diff | I/O cao, miss 24h window | |
| Cho Claude quyết định Settings configurable | Default option 1 | |

**User's choice:** Daily 2AM full count + Hourly 1% rolling sample hash (Recommended)
**Notes:** Metric `sync_count_drift{hub_id}` + `sync_hash_drift{hub_id, drift_type}`. Alert > 1% sustained 7 ngày → E-V3-5 trigger.

### Q3.2 · Failure mode + DLQ

| Option | Description | Selected |
|---|---|---|
| Mark dead + Prometheus alert + manual replay endpoint | Audit, ops control | ✓ |
| Retry-forever (no DLQ) | Outbox bloat, CPU waste | |
| DLQ table separate + auto-replay weekly | Over-engineer | |

**User's choice:** Mark dead + Prometheus alert + manual replay endpoint
**Notes:** Status='dead' enum trong sync_outbox (KHÔNG separate DLQ table). Central admin endpoint `POST /api/sync/replay { hub_id, since }`.

### Q3.3 · Checksum runner placement

| Option | Description | Selected |
|---|---|---|
| Central FastAPI lifespan asyncio task | 1 entrypoint, central visibility | ✓ |
| Per-hub-con self-verify push report | Trust hub con report | |
| Separate scheduler container | Over-engineer | |

**User's choice:** Central FastAPI lifespan asyncio task
**Notes:** Naive asyncio.sleep loop với cron time check (KHÔNG cần APScheduler dep mới). Settings.checksum_hub_dsns dict per hub read-only DSN.

---

## Area 4 — Cross-hub search refactor (SYNC-03)

### Q4.1 · Refactor scope

| Option | Description | Selected |
|---|---|---|
| Refactor search_cross_hub() in-place 1 SQL aggregated | Latency thấp, backward compat API | ✓ |
| Strip cross-hub khỏi hub con + endpoint mới /api/search/aggregated | 2 endpoint confusing | |
| Giữ fan-out + _search_one gọi central pool | Redundant overhead | |

**User's choice:** Refactor `_search_cross_hub_impl()` in-place — 1 SQL aggregated central.chunks
**Notes:** `SELECT ... FROM chunks WHERE hub_id = ANY($1::uuid[]) ORDER BY vector <=> $embedding LIMIT $k`. Public API `SearchService.search_cross_hub()` signature giữ NGUYÊN. HNSW iterative_scan + ef_search=200 carry forward.

### Q4.2 · hub_id resolution source

| Option | Description | Selected |
|---|---|---|
| hub_id UUID từ central.hubs table (Settings.hub_id env) | Central authority, UUID schema | ✓ |
| hub_id = HUB_NAME string | Phá schema PGUUID FK | |
| Compound key (hub_name, doc_id) | Duplicate data, drift risk | |

**User's choice:** hub_id UUID từ central.hubs table; Settings.hub_id field mới đọc env HUB_ID boot fail-loud
**Notes:** Operator deploy set HUB_ID khớp `medinet_central.hubs.id` row. Phase 6 SETTINGS-04 sẽ pull hub_registry TTL 5min sau.

---

## Claude's Discretion

- Alembic migration sync_outbox schema chi tiết (CHECK constraints, defaults, column comments).
- Worker class structure (`SyncWorker` class vs functional `sync_worker_loop`).
- Settings field defaults (hardcoded constants vs config).
- Test fixture patterns (TestClient dual asyncpg pool vs testcontainer 2 Postgres).
- Prometheus metric label cardinality limits + error_class normalize.
- Admin replay endpoint shape (path params vs body, GET list dead trước replay).
- PG TABLESAMPLE seed strategy + reproducibility cho hash sample verify.

## Deferred Ideas

- Soft-delete chunks deleted_at — REJECTED chunks immutable
- DLQ table separate + auto-replay weekly — REJECTED over-engineer
- Per-hub-con self-verify push checksum report — REJECTED trust risk
- Separate python-checksum-scheduler container — REJECTED over-engineer
- hub_registry pull-down sang hub con — Defer Phase 6 SETTINGS-04
- Frontend dashboard sync_status badge — Defer Phase 5 PROXY-02
- /api/search/aggregated separate endpoint — REJECTED refactor in-place
- MCP service re-point cross-hub aggregate — Defer Phase 7 MIGRATE-04
- Smoke E2E runtime — Defer Phase 7 MIGRATE-05
- Migration v2.0 existing central chunks — Defer Phase 7 MIGRATE-01..03
