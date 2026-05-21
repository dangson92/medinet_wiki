---
phase: 07-ask-api-litellm-citation-hot-swap-usage
plan: 02
subsystem: api
tags: [usage, token-tracking, asyncpg, pydantic, observability, ask]

# Dependency graph
requires:
  - phase: 02-database-schema-alembic-baseline
    provides: bảng usage_events (migration 0001) — user_id/hub_id/model/token cols/cost_usd/request_id
provides:
  - log_usage_event() — write path ghi 1 row usage_events mỗi LLM call (best-effort, gọi từ BackgroundTasks)
  - query_usage() / aggregate_usage() / realtime_usage() — read path cho 3 endpoint GET
  - UsageEventResponse / UsageStats / UsageRealtime — contract Pydantic v2 khớp D6 TokenUsage
  - GET /api/usage (+?group_by) + /api/usage/stats + /api/usage/realtime — endpoint admin-only
affects: [07-04 AskService, 07-05 ask integration test, 08 frontend smoke TokenUsage page]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Tách write path (BackgroundTasks-friendly, best-effort không raise) khỏi read path (3 endpoint)"
    - "Service dùng asyncpg pool raw SQL parametrized — nhất quán search_service, không AsyncSession"
    - "Field thiếu trong schema DB derive/hằng ở service layer (provider derive từ model, operation hằng)"

key-files:
  created:
    - api/app/schemas/usage.py
    - api/app/services/usage_service.py
    - api/app/routers/usage.py
    - api/tests/unit/test_usage_schema.py
  modified:
    - api/app/routers/__init__.py
    - api/app/main.py

key-decisions:
  - "D-07-02-A — usage_events thiếu provider/operation/latency_ms/status → derive/hằng ở service, KHÔNG thêm migration"
  - "D-07-02-B — GET /api/usage dùng envelope {success,data,error,meta} như port thường (chỉ /api/rag-config raw)"
  - "D-07-02-C — realtime window 60 phút best-effort từ cùng bảng usage_events, không stream"
  - "D-07-02-D — GET /api/usage?group_by= delegate aggregate_usage() y hệt /stats (ROADMAP SC5 URL literal)"

patterns-established:
  - "log_usage_event best-effort: bọc try/except Exception, log warning, KHÔNG raise (background task không làm sập request)"
  - "WHERE-builder động với placeholder $N tích luỹ — KHÔNG nối chuỗi (SQL injection mitigation)"
  - "provider filter map sang model ILIKE 'gemini%' vì bảng không có cột provider"

requirements-completed: [ASK-05]

# Metrics
duration: 14min
completed: 2026-05-18
---

# Phase 7 Plan 02: Ask API — Token Usage Write + Read Path Summary

**Lớp ghi + đọc token usage (ASK-05): `log_usage_event()` ghi 1 row best-effort vào `usage_events` cho mỗi LLM call, cùng 3 endpoint admin-only `GET /api/usage` (+`?group_by`) / `/stats` / `/realtime` trả contract `TokenUsage` D6 cho frontend.**

## Performance

- **Duration:** 14 min
- **Started:** 2026-05-18T12:01:50Z
- **Completed:** 2026-05-18T12:05:22Z
- **Tasks:** 3
- **Files modified:** 6 (4 tạo mới + 2 sửa)

## Accomplishments
- `schemas/usage.py` — 6 model Pydantic v2 (`UsageEventResponse`, `UsageGroup`, `UsageDailyPoint`, `UsageStats`, `UsageRealtimePoint`, `UsageRealtime`) khớp 1:1 contract D6 `frontend/src/services/api.ts` (`TokenUsageAPI` / `TokenUsageStatsAPI` / `TokenUsageRealtimeAPI`).
- `services/usage_service.py` — tách write path (`log_usage_event()` ghi 1 row `usage_events` best-effort, không raise — gọi từ BackgroundTasks ở Plan 07-04) khỏi read path (`query_usage()` list filter, `aggregate_usage()` by-model/provider/operation/daily, `realtime_usage()` window 60 phút). Toàn bộ query asyncpg parametrized `$N`.
- `routers/usage.py` — 3 endpoint GET admin-only; `GET /api/usage?group_by=` delegate `aggregate_usage()` (ROADMAP SC5 URL literal); `GET /api/usage` không group_by trả list `UsageEventResponse[]`.
- Wiring: `routers/__init__.py` re-export `usage_router`; `main.py create_app()` mount `app.include_router(usage_router)` cạnh `search_router`.
- `tests/unit/test_usage_schema.py` — 3 unit test pure-Python xác nhận shape 3 model chính (TDD RED → GREEN).

## Task Commits

Each task was committed atomically:

1. **Task 1: schemas/usage.py — UsageEventResponse / UsageStats / UsageRealtime** (TDD)
   - RED: `12c3a2d` (`test`) — test_usage_schema.py commit trạng thái fail (`ModuleNotFoundError`)
   - GREEN: `476b8d7` (`feat`) — schemas/usage.py implement → 3/3 test pass
2. **Task 2: usage_service.py — log_usage_event write + query/aggregate read** - `cf3a522` (feat)
3. **Task 3: routers/usage.py — 3 endpoint GET + mount** - `634114f` (feat)

## Files Created/Modified
- `api/app/schemas/usage.py` — 6 model Pydantic v2 contract TokenUsage (created).
- `api/app/services/usage_service.py` — write `log_usage_event` + read `query_usage`/`aggregate_usage`/`realtime_usage` (created).
- `api/app/routers/usage.py` — 3 endpoint GET admin-only (created).
- `api/tests/unit/test_usage_schema.py` — 3 unit test schema (created).
- `api/app/routers/__init__.py` — re-export `usage_router` (modified).
- `api/app/main.py` — `include_router(usage_router)` trong `create_app()` (modified).

## Decisions Made
None - followed plan as specified. 4 quyết định planner đã áp dụng đúng: D-07-02-A (`provider` derive từ `model`, `operation`/`source_module` hằng `"ask"`, `latency_ms`/`status`/`error_calls`/`avg_latency_ms` hằng 0/`"success"` — KHÔNG thêm migration), D-07-02-B (envelope `{success,data,error,meta}`), D-07-02-C (realtime best-effort cùng bảng), D-07-02-D (`?group_by=` delegate `aggregate_usage()` y hệt `/stats`).

## Deviations from Plan

None - plan executed exactly as written.

**Total deviations:** 0
**Impact on plan:** Toàn bộ code từ plan apply paste-ready. Verification suite (ruff + mypy --strict + pytest + create_app mount check) pass sạch lần đầu.

## Threat Model Compliance
- **T-07-02-01 (Information Disclosure — PII):** mitigated. `log_usage_event` chỉ ghi token count + model + id; bảng `usage_events` KHÔNG có cột chứa `query`/`answer`. Acceptance grep `grep -i "query\|answer" ... | grep -i "INSERT"` → NO MATCH (PII-safe by schema).
- **T-07-02-02 (Information Disclosure — cost data):** mitigated. 3 endpoint đều `Depends(require_role("admin"))` — chỉ admin xem usage.
- **T-07-02-03 (Tampering/Injection):** mitigated. Toàn bộ query asyncpg parametrized `$N`; `group_by` chỉ chọn nhánh code (truthy/None), KHÔNG nối vào SQL.
- **T-07-02-04 (DoS):** mitigated. `query_usage` cap `per_page` về `min(per_page, 100)` qua `_MAX_PER_PAGE`.

## Issues Encountered
None. RED phase confirm `ModuleNotFoundError` đúng kỳ vọng; GREEN phase 3/3 test pass ngay lần đầu. `create_app()` mount đúng 3 path `/api/usage{,/stats,/realtime}`.

## TDD Gate Compliance
- RED gate: `12c3a2d` (`test(07-02)`) — test_usage_schema.py commit trạng thái fail (`ModuleNotFoundError: app.schemas.usage`).
- GREEN gate: `476b8d7` (`feat(07-02)`) — schemas/usage.py implement → 3/3 test pass.
- REFACTOR: không cần — code sạch (ruff + mypy --strict clean).
- Task 2/3 không TDD (`type="auto"` không `tdd="true"`) — verify qua import smoke + ruff/mypy + `create_app` mount check theo acceptance criteria của plan.

## User Setup Required
None - no external service configuration required. Plan thuần Python + SQL (không LLM call, không secret mới). Endpoint cần Postgres pool `app.state.db_pool` đã wired từ Phase 4.

## Next Phase Readiness
- Write path `log_usage_event(pool, *, user_id, hub_id, model, prompt_tokens, completion_tokens, total_tokens, cost_usd, request_id)` sẵn sàng — Plan 07-04 (AskService) gọi qua FastAPI BackgroundTasks sau mỗi LLM call thành công.
- Read path 3 endpoint mount xong — frontend TokenUsage page (Phase 8 smoke) đọc được qua URL `/api/usage*`.
- Carry-over Plan 07-05 integration test: cần seed vài row `usage_events` rồi assert `GET /api/usage` filter + `?group_by=model` trả aggregate; verify endpoint admin-only (viewer/editor → 403).
- Lưu ý DEF-05-01 (carry-over Phase 5/6): test integration phải chạy per-file (cocoindex Environment singleton) — áp dụng nếu Plan 07-05 thêm integration test usage.

## Self-Check: PASSED
- `api/app/schemas/usage.py` — FOUND
- `api/app/services/usage_service.py` — FOUND
- `api/app/routers/usage.py` — FOUND
- `api/tests/unit/test_usage_schema.py` — FOUND
- Commit `12c3a2d` — FOUND
- Commit `476b8d7` — FOUND
- Commit `cf3a522` — FOUND
- Commit `634114f` — FOUND

---
*Phase: 07-ask-api-litellm-citation-hot-swap-usage*
*Completed: 2026-05-18*
