---
phase: 05-hub-user-audit-apikey-settings-crud
plan: 06
subsystem: backend-wiring-security
tags: [router-mount, slowapi, rate-limit, hub-isolation, x-api-key, e4-exit-criteria, integration-test, fastapi]

# Dependency graph
requires:
  - phase: 05-hub-user-audit-apikey-settings-crud (plan 01)
    provides: "migration 0003 + audit_service enqueue_audit/flush_pending + audit_flush_loop lifespan"
  - phase: 05-hub-user-audit-apikey-settings-crud (plan 02)
    provides: "hub_isolation.py verify_hub_access/HubIsolationError + middleware/rate_limit.py limiter + get_current_user_with_hubs"
  - phase: 05-hub-user-audit-apikey-settings-crud (plan 03)
    provides: "routers/hubs.py"
  - phase: 05-hub-user-audit-apikey-settings-crud (plan 04)
    provides: "routers/users.py + routers/profile.py"
  - phase: 05-hub-user-audit-apikey-settings-crud (plan 05)
    provides: "routers/api_keys.py + routers/audit_logs.py + ApiKeyService.verify_key (BLOCKER 1)"
  - phase: 04-cocoindex-flow-mvp
    provides: "documents_service.delete() + documents.py DELETE endpoint"
provides:
  - "routers/__init__.py — export 6 router (documents + hubs/users/profile/api_keys/audit_logs)"
  - "main.py — mount 7 router + slowapi limiter (app.state.limiter + 429 handler) + HubIsolationError → 403 handler"
  - "auth/api_key.py — require_api_key dependency X-API-Key external auth (AUX-02)"
  - "documents_service.delete() — hub isolation enforce + audit emit (HUB-02 / E4)"
  - "documents.py DELETE endpoint — editor-eligible + viewer reject + HubIsolationError → 403"
  - "test_hub_isolation.py — E4 EXIT criteria critical suite (6 test)"
  - "test_rate_limit.py — rate-limit 429 envelope + X-API-Key 401 verify (4 test)"
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Exception handler chain — HubIsolationError → 403 envelope; RateLimitExceeded → 429 envelope"
    - "Hub isolation enforce ở service layer — verify_hub_access trước mutation, hub_id load từ DB row"
    - "Audit emit tại điểm reject — enqueue_audit security.hub_isolation_violation TRƯỚC raise"
    - "Test-only route mount lên app_with_auth — rate-limit + X-API-Key verify KHÔNG sửa production main.py"
    - "slowapi per-route key_func 0-arg — counter cô lập per-test (Redis storage share)"

key-files:
  created:
    - "api/app/auth/api_key.py"
    - "api/tests/integration/test_hub_isolation.py"
    - "api/tests/integration/test_rate_limit.py"
  modified:
    - "api/app/routers/__init__.py"
    - "api/app/main.py"
    - "api/app/auth/__init__.py"
    - "api/app/services/documents_service.py"
    - "api/app/routers/documents.py"
    - "api/tests/integration/conftest.py"
    - "api/tests/integration/test_documents_upload.py"
    - "api/tests/integration/test_ingest_e2e.py"
    - "api/tests/integration/test_rbac_dependency.py"

key-decisions:
  - "BLOCKER 1 resolved — require_api_key gọi ApiKeyService.verify_key (verify với grep: verify_key match, verify_plaintext không match)"
  - "DELETE /api/documents/:id chuyển từ admin-only → editor-eligible (get_current_user_with_hubs); viewer reject riêng"
  - "Audit security.hub_isolation_violation emit ở SERVICE layer (documents_service.delete) — main.py handler chỉ render envelope 403"
  - "documents_service.delete signature đổi deleted_by:UUID → actor:User + actor_hub_ids:Sequence[str]"
  - "actor_hub_ids dùng Sequence[str] (KHÔNG list[str]) — tránh mypy valid-type error do class có method tên list()"
  - "Rate-limit test dùng test-only route + per-route key_func 0-arg unique — slowapi gọi per-route key_func KHÔNG đối số"
  - "DEF-05-03 logged — test_ingest_e2e cần cocoindex thật, mâu thuẫn shared fixture COCOINDEX_SKIP_SETUP (pre-existing, không fix)"

patterns-established:
  - "HubIsolationError exception handler — @app.exception_handler render 403 envelope D6 shape"
  - "verify_hub_access trong mutation service — hub_id resource đọc từ DB SELECT (KHÔNG payload)"
  - "Audit emit tại reject point service layer — enqueue_audit TRƯỚC re-raise cho forensic trail"

requirements-completed: [HUB-02, AUX-02, AUX-03]

# Metrics
duration: 148min
completed: 2026-05-17
---

# Phase 5 Plan 06: Wiring + Hub Isolation Enforce + E4 EXIT Criteria Test Summary

**Wave 4 khép Phase 5: mount 5 router Phase 5 vào main.py + wire slowapi limiter + HubIsolationError handler + X-API-Key auth dependency; retrofit hub isolation enforcement vào document DELETE mutation (HUB-02 / EXIT criteria E4) với audit emit tại điểm reject; E4 hub-isolation critical test suite 6 test genuinely PASS against real DB + rate-limit 429 envelope verify — 12 file (3 created + 9 modified), 3 task atomic.**

## Performance

- **Duration:** ~148 min
- **Started:** 2026-05-17T03:45:47Z
- **Completed:** 2026-05-17T06:13:50Z
- **Tasks:** 3 completed
- **Files modified:** 12 (3 created + 9 modified)

## Accomplishments

- `routers/__init__.py` — export 6 router (`documents_router` + `hubs_router`, `users_router`, `profile_router`, `api_keys_router`, `audit_logs_router`). Plan 05-03/04/05 tạo file router nhưng KHÔNG export — plan này export.
- `main.py` `create_app()` — `include_router` 5 router Phase 5 sau `documents_router` (tổng 7 router: auth + documents + 5 Phase 5). Wire slowapi: `app.state.limiter = limiter` + `add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)` → 429 envelope. Thêm `@app.exception_handler(HubIsolationError)` → 403 envelope (HUB-02 / E4).
- `auth/api_key.py` — `require_api_key` dependency X-API-Key external auth (AUX-02): thiếu header → 401 `API_KEY_MISSING`; key sai/revoked → 401 `API_KEY_INVALID`. Gọi `ApiKeyService(db=db).verify_key(x_api_key)` — tên method canonical (BLOCKER 1). `auth/__init__.py` re-export `require_api_key`.
- `documents_service.delete()` — retrofit hub isolation (HUB-02 / E4): signature đổi `deleted_by:UUID` → `actor:User` + `actor_hub_ids:Sequence[str]`. Sau SELECT `hub_id` (load TỪ DB row — T-05-06-02 KHÔNG từ payload), gọi `verify_hub_access`; cross-hub reject → `enqueue_audit(AuditEntry(action="security.hub_isolation_violation", ...))` TẠI điểm reject TRƯỚC `raise` (T-05-06-03 forensic trail). admin role bypass (T-04-05-03 preserved).
- `documents.py` DELETE endpoint — auth đổi `require_role("admin")` → `get_current_user_with_hubs` (editor-eligible). viewer → 403 reject TRƯỚC service (T-05-06-06). `HubIsolationError` bắt → `resp.forbidden` 403.
- `conftest.py` — TRUNCATE mở rộng thêm `hubs/audit_logs/api_keys/documents/chunks`; helper `_insert_hub` + `_assign_user_hub`; AES_KEY test deterministic 32-byte base64.
- `test_hub_isolation.py` — E4 EXIT criteria critical suite 6 test (mọi test `@pytest.mark.critical`): editor cross-hub DELETE → 403 + document vẫn tồn tại; audit `security.hub_isolation_violation` logged; admin bypass → 204; editor own-hub → 204; viewer → 403; `verify_hub_access` unit (editor cross-hub raise, admin bypass).
- `test_rate_limit.py` — 4 test: 429 envelope shape (`{success,data,error,meta}` + `RATE_LIMIT_EXCEEDED`); under-limit pass; X-API-Key invalid → 401 (`@critical` — chứng minh BLOCKER 1 `verify_key`); auth/me KHÔNG rate-limit.

## Task Commits

Each task was committed atomically (normal git, hooks enabled):

1. **Task 1: wire 5 router + slowapi limiter + HubIsolationError handler + X-API-Key** - `d9e59e2` (feat)
2. **Task 2: hub isolation enforce + audit emit ở document DELETE (HUB-02 / E4)** - `e32af03` (feat)
3. **Task 3: E4 hub-isolation critical suite + rate-limit + conftest fixtures** - `5f5bfea` (test)

## Files Created/Modified

- `api/app/auth/api_key.py` - require_api_key dependency X-API-Key external auth (AUX-02), gọi verify_key.
- `api/app/routers/__init__.py` - export 6 router.
- `api/app/main.py` - mount 5 router Phase 5 + slowapi limiter + HubIsolationError handler.
- `api/app/auth/__init__.py` - re-export require_api_key.
- `api/app/services/documents_service.py` - delete() enforce verify_hub_access + audit emit (HUB-02 / E4).
- `api/app/routers/documents.py` - DELETE endpoint editor-eligible + viewer reject + HubIsolationError → 403.
- `api/tests/integration/conftest.py` - TRUNCATE mở rộng + _insert_hub/_assign_user_hub + AES_KEY test.
- `api/tests/integration/test_hub_isolation.py` - E4 critical suite 6 test.
- `api/tests/integration/test_rate_limit.py` - rate-limit 429 + X-API-Key 401 verify 4 test.
- `api/tests/integration/test_documents_upload.py` - _create_hub fix code/subdomain (DEF-05-02 leftover).
- `api/tests/integration/test_ingest_e2e.py` - _create_hub fix code/subdomain (DEF-05-02 leftover).
- `api/tests/integration/test_rbac_dependency.py` - _spawn_rbac_app set COCOINDEX_SKIP_SETUP + reset_queue (DEF-05-01 leftover).

## Verification

- **Task 1:** `ruff check` + `mypy --strict` 3 source clean. `create_app()` smoke: 5 route Phase 5 mounted + `app.state.limiter` set + `require_api_key` importable. BLOCKER 1 grep: `verify_key` match, `verify_plaintext` không match.
- **Task 2:** `ruff check` + `mypy --strict` 2 source clean. `pytest tests/integration/test_documents_list_delete.py` → 7 passed (Plan 04-05 KHÔNG regress — admin delete + viewer 403 + unknown 404).
- **Task 3:** `ruff check` clean. `pytest test_hub_isolation.py test_rate_limit.py` → 10 passed. **E4 verify:** 6 hub-isolation test genuinely PASS against real DB testcontainer — editor cross-hub → 403 + document vẫn tồn tại + audit `security.hub_isolation_violation` logged (user_id=editor, target_type=document).
- **Plan-level:** `ruff check app tests` clean. `mypy --strict app` → 62 source clean. `pytest -m critical` per-file (DEF-05-01 cocoindex Environment singleton — chạy per-file): unit 4 passed; test_argon2 4, test_audit_logger 1, test_auth_login 4, test_auth_refresh_race 3, test_chunks_hnsw 3, test_documents_list_delete 5, test_documents_upload 6, test_jwt_compat 5, test_rbac_dependency 6, test_hub_isolation 6, test_rate_limit 1 — tất cả PASS. Chỉ `test_ingest_e2e::test_e2e_upload_docx_to_chunks_completed` FAIL (DEF-05-03 — pre-existing cocoindex incompatibility).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] main.py — add_exception_handler type mismatch mypy --strict**
- **Found during:** Task 1
- **Issue:** `app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)` — mypy --strict báo handler ký kiểu `RateLimitExceeded` không khớp Starlette expect `Exception`. Block verify Task 1 (mypy --strict exit 0 là acceptance criteria).
- **Fix:** Thêm `# type: ignore[arg-type]` + comment giải thích — Starlette dispatch handler đúng loại exc runtime, an toàn.
- **Files modified:** `api/app/main.py`
- **Commit:** `d9e59e2`

**2. [Rule 3 - Blocking] documents_service.py — list[str] annotation shadow class method**
- **Found during:** Task 2
- **Issue:** Param `actor_hub_ids: list[str]` — mypy --strict báo `Function "DocumentService.list" is not valid as a type` vì class `DocumentService` có method tên `list` shadow builtin `list` trong class namespace (annotation eval lazy do `from __future__ import annotations`).
- **Fix:** Đổi annotation sang `Sequence[str]` (import `collections.abc.Sequence`); call site `verify_hub_access` convert `list(actor_hub_ids)` (helper param vẫn `list[str]`).
- **Files modified:** `api/app/services/documents_service.py`
- **Commit:** `e32af03`

**3. [Rule 1 - Bug] test infra — _create_hub thiếu cột NOT NULL migration 0003 (DEF-05-02 leftover)**
- **Found during:** Task 3 (chạy `pytest -m critical`)
- **Issue:** `test_documents_upload.py` + `test_ingest_e2e.py` có helper `_create_hub` INSERT `hubs` KHÔNG truyền `code`/`subdomain` → `NotNullViolationError` (migration 0003 thêm 2 cột NOT NULL). DEF-05-02 fix trước CHỈ sửa `test_watchdog.py` + `test_documents_list_delete.py` — 2 file này sót. Block HARD-03 critical gate.
- **Fix:** Cập nhật `_create_hub` 2 file truyền `code` + `subdomain` (giá trị unique `test-hub-{hex}` / `hub-{hex}`).
- **Files modified:** `api/tests/integration/test_documents_upload.py`, `api/tests/integration/test_ingest_e2e.py`
- **Commit:** `5f5bfea`

**4. [Rule 3 - Blocking] test_rbac_dependency.py — _spawn_rbac_app cocoindex + audit queue leak (DEF-05-01 leftover)**
- **Found during:** Task 3 (chạy `pytest -m critical test_rbac_dependency.py`)
- **Issue:** `_spawn_rbac_app` (Phase 3 helper) KHÔNG set `COCOINDEX_SKIP_SETUP=1` → test thứ 2 crash `environment already open` (DEF-05-01). Sau khi thêm flag, lifespan hoàn tất + start `audit_flush_loop` → module-global `audit_service._queue` bound vào event loop test trước → shutdown `await queue.get()` treo vĩnh viễn. Block HARD-03 critical gate.
- **Fix:** `_spawn_rbac_app` set `COCOINDEX_SKIP_SETUP=1` + gọi `reset_queue()` (mirror `app_with_auth` fixture conftest).
- **Files modified:** `api/tests/integration/test_rbac_dependency.py`
- **Commit:** `5f5bfea`

### Out-of-scope discoveries (logged, NOT fixed)

- **DEF-05-03** — `test_ingest_e2e::test_e2e_upload_docx_to_chunks_completed` FAIL: test assert `app.state.cocoindex_app is not None` nhưng shared fixture `app_with_auth` set `COCOINDEX_SKIP_SETUP=1` (DEF-05-01 fix) → `cocoindex_app=None`. Pre-existing incompatibility — `COCOINDEX_SKIP_SETUP` env đã có trong conftest TRƯỚC Plan 05-06. Fix cần thay đổi kiến trúc test-infra (fixture riêng / pytest-forked / chuyển eval suite) — quyết định cấu trúc, KHÔNG fix tại Plan 05-06 (Rule 4 territory). Logged `deferred-items.md` DEF-05-03 — đề xuất Phase 10 hardening.

## Threat Model Coverage

Tất cả threat `mitigate` trong `<threat_model>` của plan đã được thực thi:

- **T-05-06-01 (EoP — editor Hub A xoá document Hub B, DATA LEAK cross-tenant — E4):** `documents_service.delete()` gọi `verify_hub_access(role, user_hub_ids, resource_hub_id)` — `resource_hub_id` load từ `SELECT hub_id FROM documents WHERE id`; editor cross-hub → `HubIsolationError` → 403. `test_editor_hub_a_cannot_delete_doc_hub_b` (`@critical`) verify 403 + document Hub B `COUNT=1` (vẫn tồn tại).
- **T-05-06-02 (Tampering — client truyền explicit hub_id bypass):** `delete()` lấy `hub_id` từ DB row, KHÔNG từ payload. DELETE endpoint `DELETE /api/documents/:doc_id` KHÔNG nhận body — chỉ path param doc_id.
- **T-05-06-03 (Repudiation — tấn công cross-hub không dấu vết):** reject → `enqueue_audit(AuditEntry(action="security.hub_isolation_violation", user_id=actor.id, target_id, hub_id, request_id, payload))` emit Ở SERVICE LAYER TẠI điểm reject TRƯỚC `raise`. `test_hub_isolation_violation_audit_logged` (`@critical`) verify row có user_id=editor + target_type=document.
- **T-05-06-04 (Spoofing — X-API-Key giả mạo):** `require_api_key` verify qua `ApiKeyService.verify_key` (BLOCKER 1) — decrypt AES-GCM + match; revoked key (is_active=FALSE) loại; key sai → 401 `API_KEY_INVALID`. `test_x_api_key_invalid_rejected` (`@critical`) verify.
- **T-05-06-05 (DoS — spam endpoint):** slowapi limiter wired (`app.state.limiter` + `add_exception_handler(RateLimitExceeded)`); `test_rate_limit_returns_429_envelope` verify 429 envelope shape.
- **T-05-06-06 (EoP — viewer xoá document):** DELETE endpoint reject `role=="viewer"` → 403 TRƯỚC khi vào service. `test_viewer_cannot_delete_any_doc` (`@critical`) verify.
- **T-05-06-07 (Info Disclosure — admin bypass — accept):** admin cross-hub theo thiết kế quản trị (T-04-05-03 precedent); `verify_hub_access(role="admin")` return None. `test_admin_can_delete_doc_any_hub` verify 204. Accept disposition — admin account compromise ngoài scope Phase 5.

## Threat Flags

Không phát hiện threat surface mới ngoài `<threat_model>` của plan. Plan này chủ yếu wiring (mount router đã tạo) + retrofit isolation vào endpoint sẵn có. `auth/api_key.py` thêm X-API-Key auth path nhưng đã nằm trong threat register (T-05-06-04). HubIsolationError handler + slowapi handler là render envelope thuần — không truy cập DB.

## E4 EXIT Criteria — VERIFIED

EXIT criteria E4 (PROJECT.md — hub isolation bug = ship-blocker): `test_hub_isolation.py` 6 critical test genuinely PASS against real DB (testcontainer Postgres) qua fixture `app_with_auth`. KHÔNG skip, KHÔNG xfail, KHÔNG stub. Editor Hub A cross-hub DELETE → 403 + document Hub B vẫn tồn tại + audit `security.hub_isolation_violation` ghi. HUB-02 enforce hoàn tất. E4 KHÔNG trigger STOP — Phase 5 đủ điều kiện ship M2 về mặt hub isolation.

## HARD-03 Critical Gate

`pytest -m critical` toàn bộ PASS khi chạy per-file (DEF-05-01 — cocoindex 1.0.3 `core.Environment` process-global singleton KHÔNG cho phép chạy nhiều integration file boot cocoindex trong 1 process; chạy `pytest -m critical` 1 lệnh sẽ treo). Per-file: 4 unit + 44 integration critical PASS. Ngoại lệ DUY NHẤT: `test_ingest_e2e::test_e2e_upload_docx_to_chunks_completed` (DEF-05-03 — pre-existing, KHÔNG do Plan 05-06). E4 hub-isolation suite (mục tiêu chính plan) genuinely PASS.

## Known Stubs

Không có stub chặn mục tiêu plan. `require_api_key` là dependency sẵn sàng cho endpoint external Phase 6/7 (search/ask) opt-in — chưa endpoint Phase 5 nào consume (api-keys/audit-logs đều JWT admin-only); đây là forward-scaffolding documented, KHÔNG phải stub bug. `@limiter.limit` áp `/api/search` + `/api/ask` defer Phase 6/7 (endpoint chưa tồn tại) — cơ chế limiter + 429 envelope đã verify Phase 5 qua `/api/audit-logs` + test-only route.

## TDD Gate Compliance

Plan type là `execute` (KHÔNG `type: tdd`); không task nào có `tdd="true"`. Task 3 viết test sau implementation (Task 1+2) — verify qua `ruff` + `mypy --strict` + integration test PASS (acceptance criteria mỗi task). Gate RED→GREEN không áp dụng plan-level.

## Self-Check: PASSED

- FOUND: api/app/auth/api_key.py
- FOUND: api/tests/integration/test_hub_isolation.py
- FOUND: api/tests/integration/test_rate_limit.py
- FOUND commit: d9e59e2 (Task 1)
- FOUND commit: e32af03 (Task 2)
- FOUND commit: 5f5bfea (Task 3)
