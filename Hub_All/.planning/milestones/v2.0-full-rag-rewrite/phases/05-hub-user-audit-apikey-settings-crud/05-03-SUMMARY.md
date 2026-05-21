---
phase: 05-hub-user-audit-apikey-settings-crud
plan: 03
subsystem: backend-crud
tags: [hub, crud, fastapi, pydantic, raw-sql, audit, stats, layered-architecture]

# Dependency graph
requires:
  - phase: 05-hub-user-audit-apikey-settings-crud (plan 01)
    provides: "migration 0003 hubs.code/subdomain/status + audit_service enqueue_audit/AuditEntry"
  - phase: 05-hub-user-audit-apikey-settings-crud (plan 02)
    provides: "(không dùng trực tiếp — hub CRUD admin-only, hub-isolation enforce defer Plan 05-06)"
  - phase: 04-cocoindex-flow-mvp
    provides: "documents.py router analog + documents_service.py service-chứa-SQL pattern + response envelope"
provides:
  - "schemas/hubs.py — CreateHubRequest/UpdateHubRequest/UpdateHubStatusRequest/HubResponse/HubStats (D-05 8 field)"
  - "services/hub_service.py — HubService 6 method CRUD+stats + HubConflictError"
  - "routers/hubs.py — Hub CRUD router 6 endpoint admin-only (chưa mount — wiring Plan 05-06)"
affects: [05-06]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Service-chứa-SQL CRUD — raw text() + named bind params, INSERT/UPDATE ... RETURNING map row→Pydantic"
    - "Dynamic SET clause builder cho PUT update — chỉ field không None + updated_at=NOW()"
    - "rowcount-free row-exists detect — UPDATE ... RETURNING id + fetchone() (Result type stub không expose rowcount)"

key-files:
  created:
    - "api/app/schemas/hubs.py"
    - "api/app/services/hub_service.py"
    - "api/app/routers/hubs.py"
  modified: []

key-decisions:
  - "D-05 — HubResponse CHỈ 8 field M2 thật; KHÔNG chroma_collection/db_* (di sản Go drop hẳn)"
  - "D-07 — Hub update = PUT (KHÔNG PATCH); PATCH /:id/status là endpoint riêng"
  - "D-06 — KHÔNG implement endpoint kiểm tra kết nối per-hub DB (M2 dùng 1 Postgres chung)"
  - "HUB-03 stats CHỈ 3 count (document/chunk/user); query_count defer Phase 6/7 — chưa có nguồn data (partial-coverage SC1 có chủ đích)"
  - "update_status dùng UPDATE ... RETURNING id thay .rowcount — SQLAlchemy Result type stub không expose rowcount (mypy --strict)"
  - "Router mount vào main.py defer Plan 05-06 (Wave 4 wiring) — Plan 05-03 KHÔNG touch main.py/routers/__init__.py"

patterns-established:
  - "Hub CRUD service-chứa-SQL: _HUB_SELECT_COLS hằng + _row_to_response helper dùng chung get/update/list"
  - "PUT update động: build SET parts cho field không None, luôn append updated_at=NOW()"

requirements-completed: [HUB-01, HUB-03]

# Metrics
duration: 5min
completed: 2026-05-17
---

# Phase 5 Plan 03: Hub Registry CRUD — Router + Service + Schema + Stats Summary

**Hub registry CRUD (HUB-01) + hub stats (HUB-03) theo layered architecture — 3 file (schema/service/router) với 6 endpoint admin-only; HubResponse drop hẳn field di sản Go (D-05), update = PUT (D-07), stats từ Postgres aggregate 3 count.**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-05-17T03:19:19Z
- **Completed:** 2026-05-17T03:22:30Z
- **Tasks:** 3 completed
- **Files modified:** 3 (3 created + 0 modified)

## Accomplishments

- `schemas/hubs.py` — 5 Pydantic v2 schema: `CreateHubRequest` (name/code/subdomain + description optional), `UpdateHubRequest` (name/description optional — D-07 PUT chỉ 2 field), `UpdateHubStatusRequest` (status), `HubResponse` (CHỈ 8 field M2 — D-05 drop `chroma_collection`/`db_*`), `HubStats` (3 count). `HubStatus` Literal active/inactive khớp CHECK constraint `hub_status_enum`.
- `services/hub_service.py` — `HubService` 6 method: `create` (INSERT ... RETURNING, slug=code.lower() W1, IntegrityError→`HubConflictError`), `get`, `list` (COUNT + LIMIT/OFFSET, KHÔNG cap ở service), `update` (dynamic SET clause PUT — D-07), `update_status` (UPDATE ... RETURNING id), `stats` (verify exists + aggregate 3 subquery COUNT documents/chunks/user_hubs — HUB-03). Raw SQL `text()` + named params (T-05-03-02 SQL injection mitigation); timestamp `NOW()` server-side. `enqueue_audit` non-blocking ở create + update + update_status (T-05-03-05 Repudiation mitigation).
- `routers/hubs.py` — Hub CRUD router 6 endpoint: `GET /api/hubs` (list cap per_page≤100), `POST /api/hubs` (create→201), `GET /api/hubs/{id}`, `PUT /api/hubs/{id}` (update — D-07), `PATCH /api/hubs/{id}/status`, `GET /api/hubs/{id}/stats` (HUB-03). Mọi endpoint `require_role("admin")` (T-05-03-01 EoP mitigation). KHÔNG endpoint test-connection (D-06). UUID validate → 400 `INVALID_HUB_ID`; not-found → 404 `NOT_FOUND`; conflict → 409 `HUB_CODE_CONFLICT`.

## Task Commits

Each task was committed atomically (normal git, hooks enabled):

1. **Task 1: schemas/hubs.py — Pydantic v2 schemas** - `c90ce1b` (feat)
2. **Task 2: services/hub_service.py — HubService CRUD + stats** - `cf1ffb9` (feat)
3. **Task 3: routers/hubs.py — Hub CRUD router** - `4b60e28` (feat)

## Files Created/Modified

- `api/app/schemas/hubs.py` - 5 Pydantic v2 schema cho Hub CRUD; `HubResponse` CHỈ 8 field (D-05).
- `api/app/services/hub_service.py` - `HubService` 6 method CRUD+stats + `HubConflictError`; raw SQL parametrized, audit non-blocking, stats Postgres aggregate.
- `api/app/routers/hubs.py` - Hub CRUD router 6 endpoint admin-only; `get_hub_service` factory; PUT update + PATCH status + GET stats.

## Verification

- **Task 1:** `ruff check` + `mypy --strict app/schemas/hubs.py` exit 0. Smoke: `HubResponse.model_fields` == đúng 8 field; KHÔNG chứa `chroma_collection`/`db_host`/`db_port`/`db_name`/`db_user` (D-05).
- **Task 2:** `ruff check` + `mypy --strict app/services/hub_service.py` exit 0. Import `HubService`/`HubConflictError` OK; 6 method present; `enqueue_audit` 4 match (≥2 yêu cầu — create + update + update_status); `NOW()` 5 match; `datetime.utcnow` chỉ xuất hiện trong docstring ghi rule (KHÔNG phải usage).
- **Task 3:** `ruff check` + `mypy --strict app/routers/hubs.py` exit 0. Route smoke test xác nhận đủ 6 path đúng verb (PUT update, PATCH status); KHÔNG `test-connection` (grep 0 match cả route lẫn chuỗi text). `require_role("admin")` 7 match (≥6 yêu cầu — 6 endpoint, mọi endpoint admin-only).
- **Plan-level:** `ruff check` + `mypy --strict` 3 file clean (3 source). Không file nào bị xoá ngoài ý muốn (`git diff --diff-filter=D HEAD~3 HEAD` rỗng).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] update_status dùng RETURNING id thay .rowcount**
- **Found during:** Task 2
- **Issue:** Plan action ghi `update_status` dùng `result.rowcount > 0` để phát hiện row tồn tại. `mypy --strict` báo lỗi `"Result[Any]" has no attribute "rowcount"` — SQLAlchemy 2.0 async `AsyncSession.execute()` type stub trả `Result` (không expose `rowcount`; `rowcount` chỉ ở `CursorResult`). Block verify Task 2 (mypy --strict exit 0 là acceptance criteria).
- **Fix:** Đổi sang `UPDATE hubs SET ... WHERE id = :id RETURNING id` + `.fetchone()` → `None` nghĩa là 0 row (hub không tồn tại). Cùng idiom đã dùng ở `create`/`update` (INSERT/UPDATE ... RETURNING). Hành vi giữ nguyên — `update_status` vẫn return `bool`.
- **Files modified:** `api/app/services/hub_service.py`
- **Commit:** `cf1ffb9`

### Out-of-scope discoveries (logged, NOT fixed)

- Không có. Plan 05-03 chỉ tạo 3 file mới, không touch file pre-existing → không lộ regression mới. DEF-05-01 (cocoindex Environment re-open) + DEF-05-02 (test_watchdog.py fixture `hubs.code`) vẫn deferred — Plan 05-03 KHÔNG có integration test (test mandatory E4 ở Plan 05-06) nên không chạm DEF-05-01; KHÔNG touch `test_watchdog.py` nên không liên quan DEF-05-02.

## Threat Model Coverage

Tất cả threat `mitigate` trong `<threat_model>` của plan đã được thực thi:

- **T-05-03-01 (EoP — viewer/editor gọi POST/PUT/PATCH hub):** Mọi endpoint trong `routers/hubs.py` dùng `Depends(require_role("admin"))` → viewer/editor nhận 403 `FORBIDDEN`. 7 match `require_role("admin")` (6 endpoint).
- **T-05-03-02 (Tampering — SQL injection qua name/code/subdomain):** Mọi raw SQL trong `hub_service.py` qua `text()` + named bind params (`:name`, `:code`, ...) — asyncpg parametrize. KHÔNG f-string nội suy giá trị (chỉ `_HUB_SELECT_COLS` hằng nội bộ + `set_sql` từ danh sách clause cố định nội bộ — KHÔNG nhận input user).
- **T-05-03-03 (Info Disclosure — HubResponse leak field di sản Go):** `HubResponse` Pydantic schema CHỈ 8 field (D-05); smoke test assert `model_fields` KHÔNG chứa `chroma_collection`/`db_host`/`db_port`/`db_name`/`db_user`. Cột db_* không tồn tại trong bảng `hubs` (Plan 05-01 KHÔNG thêm).
- **T-05-03-04 (Spoofing — 2 hub trùng code):** `create` catch `IntegrityError` (unique constraint `uq_hubs_code` từ Plan 05-01) → raise `HubConflictError` → router trả 409 `HUB_CODE_CONFLICT`.
- **T-05-03-05 (Repudiation — không truy được ai tạo/sửa hub):** `enqueue_audit` với `AuditEntry(action="hub.create"/"hub.update", user_id, target_id, hub_id, payload, request_id)` ở create + update + update_status — non-blocking qua audit_service asyncio.Queue (Plan 05-01).

## Threat Flags

Không phát hiện threat surface mới ngoài `<threat_model>` của plan. 3 file mới đều là CRUD layer chuẩn — router admin-only, service raw SQL parametrized, schema field-restricted. Router CHƯA mount vào `main.py` (wiring Plan 05-06) nên chưa expose endpoint runtime.

## HUB-03 stats — Partial coverage có chủ đích

`HubStats` Phase 5 CHỈ ship 3 count: `document_count`, `chunk_count`, `user_count`. ROADMAP SC1 + HUB-03 nêu stats gồm "documents/chunks/**queries**/users" — `query_count` **defer Phase 6/7**: search endpoint là Phase 6, `usage_events` chỉ có data từ Phase 7 (D-04 — token usage logging defer Phase 7). Đây là partial-coverage HUB-03/SC1 CÓ CHỦ ĐÍCH (ghi rõ trong plan objective), KHÔNG phải omission quên — work-verifier Phase 5 KHÔNG nên flag SC1 sai.

## Known Stubs

Không có stub. Cả 3 file có data source thật: schema map đúng cột DB (migration 0003), service raw SQL trên bảng thật (`hubs`/`documents`/`chunks`/`user_hubs`), router gọi service thật. Router chưa mount main.py là wiring defer có chủ đích (Plan 05-06 Wave 4), KHÔNG phải stub — `routers/hubs.py` export `router` sẵn sàng `include_router`.

## TDD Gate Compliance

Plan type là `execute` (KHÔNG phải `type: tdd`); không task nào có `tdd="true"`. Verify qua `ruff check` + `mypy --strict` + route smoke test (acceptance criteria mỗi task). Integration test E4 mandatory cho mutation endpoint là scope Plan 05-06 (Wave 4). Gate RED→GREEN không áp dụng.

## Self-Check: PASSED

- FOUND: api/app/schemas/hubs.py
- FOUND: api/app/services/hub_service.py
- FOUND: api/app/routers/hubs.py
- FOUND commit: c90ce1b (Task 1)
- FOUND commit: cf1ffb9 (Task 2)
- FOUND commit: 4b60e28 (Task 3)
