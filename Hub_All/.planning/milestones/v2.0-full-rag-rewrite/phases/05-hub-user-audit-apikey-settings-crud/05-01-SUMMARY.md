---
phase: 05-hub-user-audit-apikey-settings-crud
plan: 01
subsystem: database
tags: [alembic, migration, sqlalchemy, postgres, audit-log, asyncio, fastapi]

# Dependency graph
requires:
  - phase: 02-database-schema-alembic-baseline
    provides: "Schema baseline 10 bảng (hubs/users/api_keys/audit_logs) + alembic 0001/0002"
  - phase: 03-auth-port-rbac-response-envelope
    provides: "SQLAlchemy async engine + lifespan pattern + get_engine()"
  - phase: 04-cocoindex-flow-mvp
    provides: "watchdog asyncio task lifecycle analog + documents_service audit INSERT shape"
provides:
  - "Migration 0003 — cột Phase 5 cho hubs (code/subdomain/status), users (phone/department/avatar_url/status), api_keys (permissions/allowed_hub_ids/rate_limit)"
  - "Models Hub/User/ApiKey khớp contract frontend HubAPI/UserAPI/APIKeyAPI"
  - "audit_service.py — enqueue_audit non-blocking + audit_flush_loop batch flush 2s/128"
  - "config.py — audit + rate-limit knobs (audit_batch_size, rate_limit_*_per_minute)"
  - "Lifespan wiring audit_flush_loop task"
affects: [05-02, 05-03, 05-04, 05-05, 05-06]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "asyncio.Queue batch flush logger — module-level lazy queue + background drain loop"
    - "Migration additive với server_default backfill + alter_column drop default"

key-files:
  created:
    - "api/migrations/versions/0003_phase5_schema_reconcile.py"
    - "api/app/services/audit_service.py"
    - "api/tests/integration/test_audit_logger.py"
  modified:
    - "api/app/models/hub.py"
    - "api/app/models/auth.py"
    - "api/app/models/settings.py"
    - "api/app/config.py"
    - "api/app/main.py"

key-decisions:
  - "W1 — hubs giữ cả slug (legacy NOT NULL mirror) + code (contract frontend); defer dọn slug về milestone schema-cleanup"
  - "BLOCKER 2 — KHÔNG implement Settings CRUD: frontend zero /api/settings call; bảng settings để dành Phase 7 rag-config"
  - "D-05 — KHÔNG thêm chroma_collection/db_* vào hubs (di sản Go drop hẳn)"
  - "Task 4 fixture tự cấp audit_db (alembic + engine) thay app_with_auth — né cocoindex Environment re-open bug"

patterns-established:
  - "asyncio.Queue audit logger: lazy _get_queue() + reset_queue() test helper + enqueue non-blocking drop-on-full"
  - "Migration additive: add_column server_default → alter_column drop default → existing rows backfill an toàn"

requirements-completed: [HUB-01, AUX-01]

# Metrics
duration: 35min
completed: 2026-05-17
---

# Phase 5 Plan 01: Migration 0003 Schema Reconcile + Audit Logger asyncio.Queue Summary

**Migration 0003 thêm cột contract frontend cho hubs/users/api_keys + audit logger asyncio.Queue batch flush (2s/128) làm nền móng cho Wave 2-4 Phase 5.**

## Performance

- **Duration:** ~35 min
- **Started:** 2026-05-17T10:00:00Z
- **Completed:** 2026-05-17T10:35:00Z
- **Tasks:** 4 completed
- **Files modified:** 8 (3 created + 5 modified)

## Accomplishments

- Migration 0003 reconcile schema — 10 cột mới (additive only) cho hubs/users/api_keys khớp `HubAPI`/`UserAPI`/`APIKeyAPI` frontend; alembic round-trip upgrade→downgrade→upgrade PASS clean trên DB sạch, chỉ 1 head.
- audit_service.py — `enqueue_audit` non-blocking (drop+warning khi queue đầy, KHÔNG raise), `audit_flush_loop` batch INSERT 2s/128, `flush_pending` drain shutdown.
- Lifespan wire `audit_flush_loop` task — start lúc startup (step 8), `flush_pending`+cancel lúc shutdown TRƯỚC dispose_engine.
- test_audit_logger.py — AUX-01 SC4 concurrency phủ test critical: 100 concurrent enqueue → 100 row + request_id unique.

## Task Commits

Each task was committed atomically:

1. **Task 1: Migration 0003 + cập nhật SQLAlchemy models** - `769e0d4` (feat)
2. **Task 2: audit_service.py + config knobs** - `4e3de9b` (feat)
3. **Task 3: Wire audit_flush_loop vào main.py lifespan** - `f122b74` (feat)
4. **Task 4: test_audit_logger.py concurrency test** - `a7a3311` (test)

## Files Created/Modified

- `api/migrations/versions/0003_phase5_schema_reconcile.py` - Migration thêm 10 cột Phase 5; downgrade đảo ngược clean.
- `api/app/services/audit_service.py` - Audit logger asyncio.Queue: `AuditEntry`, `enqueue_audit`, `audit_flush_loop`, `flush_pending`, `AUDIT_ACTIONS`, `reset_queue`.
- `api/tests/integration/test_audit_logger.py` - 3 test (1 critical) phủ AUX-01 SC4.
- `api/app/models/hub.py` - Thêm `code`/`subdomain`/`status` + CheckConstraint `hub_status_enum`.
- `api/app/models/auth.py` - Thêm `phone`/`department`/`avatar_url`/`status` + CheckConstraint `user_status_enum`.
- `api/app/models/settings.py` - ApiKey thêm `permissions`/`allowed_hub_ids`/`rate_limit`.
- `api/app/config.py` - Thêm audit knobs + rate-limit knobs.
- `api/app/main.py` - Lifespan start/stop `audit_flush_loop` task.

## Verification

- `alembic heads` → đúng 1 head (`0003`).
- `alembic upgrade head` → `downgrade base` → `upgrade head` PASS clean trên DB testcontainer-style sạch (`medinet_mig0003_test`, đã drop sau test).
- `ruff check app` exit 0 (44 source); `mypy --strict app` exit 0 (44 source).
- `python -c "from app.main import create_app; create_app()"` không raise.
- `pytest tests/integration/test_audit_logger.py` → 3 passed.
- `pytest -m critical -k audit_logger` → 1 passed (HARD-03 — SC4 concurrency phủ test critical).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Task 4 fixture thay app_with_auth bằng audit_db tự cấp**
- **Found during:** Task 4
- **Issue:** Fixture `app_with_auth` (conftest) chạy full lifespan gồm `setup_cocoindex()`. Cocoindex 1.0.3 `Environment` là process-global singleton — KHÔNG re-open được sau open+close → mọi test file dùng `app_with_auth` cho >1 test FAIL từ test thứ 2 (`RuntimeError: environment already open`). Đây là pre-existing limitation Phase 4 — `test_documents_list_delete.py` cũng fail giống hệt (1 passed, 6 errors). Plan 05-01 Task 4 cần chạy 3 test → bị block.
- **Fix:** Viết fixture `audit_db` tự cấp trong test file — chỉ chạy alembic upgrade head + init SQLAlchemy engine, KHÔNG boot full FastAPI app/cocoindex. Audit logger test chỉ cần DB engine + bảng `audit_logs`.
- **Files modified:** `api/tests/integration/test_audit_logger.py`
- **Commit:** `a7a3311`

### Out-of-scope discoveries (logged, NOT fixed)

- **DEF-05-01** — cocoindex `Environment` không re-open được trong cùng process. Pre-existing Phase 4, KHÔNG do Plan 05-01 gây ra. Logged tại `deferred-items.md`. Wave 3-4 Phase 5 (hub/user/apikey CRUD integration test dùng `app_with_auth`) sẽ cần giải pháp chung — đề xuất Plan 05-06 hoặc Phase 10 thêm fixture mock cocoindex.

## Settings CRUD — Omission có chủ đích (BLOCKER 2)

Phase title nhắc "Settings CRUD" nhưng frontend `api.ts` có ZERO call `/api/settings` → KHÔNG implement settings endpoint trong Phase 5. Bảng `settings` (Phase 2 model) để dành Phase 7 rag-config (D-03). Plan 05-01 KHÔNG migration cho `settings` table — auditable omission.

## Known Stubs

Không có stub. Tất cả cột migration + audit logger có data source thật; test critical PASS.

## Threat Flags

Không phát hiện threat surface mới ngoài `<threat_model>` của plan. Migration additive + audit logger nội bộ — T-05-01-01..04 đã được mitigate đúng (server_default backfill, payload từ code app, queue cap + drop-on-full, flush_pending graceful shutdown).

## TDD Gate Compliance

Plan type là `execute` (KHÔNG phải `type: tdd`). Task 2 có `tdd="true"` nhưng dedicated concurrency test của AUX-01 SC4 nằm ở Task 4 (test-only task — WARNING 2). audit_service.py implement ở Task 2 (`feat`), test phủ ở Task 4 (`test`). Gate sequence không áp dụng dạng RED→GREEN cho từng task vì test SC4 được tách riêng theo revision instruction WARNING 2.

## Self-Check: PASSED

- FOUND: api/migrations/versions/0003_phase5_schema_reconcile.py
- FOUND: api/app/services/audit_service.py
- FOUND: api/tests/integration/test_audit_logger.py
- FOUND commit: 769e0d4 (Task 1)
- FOUND commit: 4e3de9b (Task 2)
- FOUND commit: f122b74 (Task 3)
- FOUND commit: a7a3311 (Task 4)
