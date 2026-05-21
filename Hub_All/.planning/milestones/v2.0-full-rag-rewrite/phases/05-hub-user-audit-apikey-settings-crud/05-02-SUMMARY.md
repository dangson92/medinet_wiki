---
phase: 05-hub-user-audit-apikey-settings-crud
plan: 02
subsystem: backend-security
tags: [hub-isolation, rate-limit, slowapi, fastapi, repository, rbac, security]

# Dependency graph
requires:
  - phase: 03-auth-port-rbac-response-envelope
    provides: "get_current_user dependency + require_role + JWTManager + response envelope"
  - phase: 05-hub-user-audit-apikey-settings-crud (plan 01)
    provides: "migration 0003 hubs.code/status + audit_service enqueue_audit + rate_limit knobs config.py"
provides:
  - "repositories/hub_isolation.py — hub_filter_clause + verify_hub_access + HubIsolationError (HUB-02 enforcement)"
  - "auth/dependencies.py — get_current_user_with_hubs + UserWithHubs (hub_ids từ user_hubs DB)"
  - "middleware/rate_limit.py — slowapi Limiter + rate_limit_exceeded_handler + SEARCH/UPLOAD/AUDIT_LOGS limit constant"
affects: [05-03, 05-04, 05-05, 05-06]

# Tech tracking
tech-stack:
  added:
    - "slowapi==0.1.9 — rate limiter cho FastAPI (Limiter + decorator + exception handler)"
  patterns:
    - "Hub isolation repository helper — pure-function WHERE-clause builder, admin bypass, empty→IN(NULL)"
    - "slowapi Limiter key_func — user_id từ JWT sub, fallback IP, try/except không raise"

key-files:
  created:
    - "api/app/repositories/__init__.py"
    - "api/app/repositories/hub_isolation.py"
    - "api/app/middleware/rate_limit.py"
    - "api/tests/unit/test_hub_isolation.py"
  modified:
    - "api/app/auth/dependencies.py"
    - "api/app/auth/__init__.py"
    - "api/app/middleware/__init__.py"
    - "api/pyproject.toml"
    - "api/uv.lock"

key-decisions:
  - "Tên file hub_isolation.py (KHÔNG hub_scope.py như PATTERNS gợi ý) — theo plan 05-02 frontmatter chỉ định rõ"
  - "hub_filter_clause hub_ids rỗng → 'hub_id IN (NULL)' luôn-false — editor/viewer chưa assign hub thấy 0 row (T-05-02-02)"
  - "verify_hub_access nhận role+user_hub_ids+resource_hub_id rời rạc (KHÔNG nhận User ORM) — test cô lập pure-Python, KHÔNG cần DB"
  - "slowapi storage = Redis (settings.redis_url) — counter share giữa worker (CONTEXT discretion)"
  - "Wiring main.py defer Plan 05-06 — tránh xung đột file main.py với plan cùng wave"

patterns-established:
  - "Repository layer mỏng — module function thuần (KHÔNG class hierarchy) chỉ cho HUB-02 isolation"
  - "Rate-limit key_func bọc try/except — decode JWT fail → fallback IP, KHÔNG raise (rate limit không được làm vỡ request)"

requirements-completed: [HUB-02, AUX-03]

# Metrics
duration: 20min
completed: 2026-05-17
---

# Phase 5 Plan 02: Hub Isolation Repository Helper + slowapi Rate-Limit Module Summary

**Hạ tầng cross-cutting cho Wave 3-4: hub-isolation repository helper (`hub_filter_clause` + `verify_hub_access`) enforce HUB-02 ở repository layer + slowapi rate-limit module (Limiter + envelope 429) cho AUX-03 — KHÔNG bao giờ tin `hub_id` trong request payload.**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-05-17T11:00:00Z
- **Completed:** 2026-05-17T11:20:00Z
- **Tasks:** 2 completed
- **Files modified:** 9 (4 created + 5 modified)

## Accomplishments

- `repositories/hub_isolation.py` — `hub_filter_clause()` sinh SQL fragment `WHERE hub_id IN (...)` từ user's hub assignments (admin bypass `("", {})`; hub_ids rỗng → `hub_id IN (NULL)` luôn-false); `verify_hub_access()` raise `HubIsolationError` khi resource's hub_id ∉ assignment; `HubIsolationError` lưu `resource_hub_id` cho audit payload. Docstring ghi rõ defense-in-depth 3 lớp + "KHÔNG tin hub_id payload".
- `auth/dependencies.py` — `UserWithHubs` (User + hub_ids) + dependency `get_current_user_with_hubs` lấy hub_ids từ DB `user_hubs` join table (verified source, KHÔNG payload).
- `middleware/rate_limit.py` — slowapi `Limiter` key=user_id (JWT `sub`, fallback IP qua try/except không raise), Redis storage; `rate_limit_exceeded_handler` map `RateLimitExceeded` → envelope 429 `RATE_LIMIT_EXCEEDED`; constant `SEARCH_LIMIT`/`UPLOAD_LIMIT`/`AUDIT_LOGS_LIMIT` cho router decorator.
- `tests/unit/test_hub_isolation.py` — 14 unit test pure-Python phủ E4 EXIT criteria (TDD RED→GREEN): admin bypass, hub_ids rỗng→IN(NULL), cross-hub raise, viewer enforce, HubIsolationError carry resource_hub_id.

## Task Commits

Each task was committed atomically (normal git, hooks enabled):

1. **Task 1: hub isolation repository helper + get_current_user_with_hubs (TDD)** - `3710b00` (feat)
2. **Task 2: slowapi rate-limit module — Limiter + envelope 429 handler** - `a42e3d4` (feat)

## Files Created/Modified

- `api/app/repositories/__init__.py` - Package docstring — repository layer mỏng chỉ cho HUB-02 isolation.
- `api/app/repositories/hub_isolation.py` - `HubIsolationError`, `hub_filter_clause`, `verify_hub_access` — HUB-02 enforcement.
- `api/app/middleware/rate_limit.py` - slowapi `limiter` + `_rate_limit_key` + `rate_limit_exceeded_handler` + limit constants.
- `api/tests/unit/test_hub_isolation.py` - 14 unit test (RED→GREEN) phủ hub-isolation logic.
- `api/app/auth/dependencies.py` - Thêm `UserWithHubs` class + `get_current_user_with_hubs` dependency.
- `api/app/auth/__init__.py` - Re-export `UserWithHubs`, `get_current_user_with_hubs`.
- `api/app/middleware/__init__.py` - Re-export `limiter`, `rate_limit_exceeded_handler`, 3 limit constant.
- `api/pyproject.toml` - Thêm dependency `slowapi==0.1.9`.
- `api/uv.lock` - Lock file cập nhật (slowapi + transitive deprecated, limits).

## Verification

- **Task 1:** `pytest tests/unit/test_hub_isolation.py` → 14 passed. `ruff check` (4 file) + `mypy --strict app/repositories app/auth/dependencies.py` exit 0. Smoke test logic `hub_filter_clause`/`verify_hub_access`/`HubIsolationError` + import `get_current_user_with_hubs`/`UserWithHubs` exit 0.
- **Task 2:** `ruff check` + `mypy --strict app/middleware/rate_limit.py` exit 0. Import smoke test `from app.middleware import limiter, rate_limit_exceeded_handler; isinstance(limiter, Limiter)` exit 0. `grep RATE_LIMIT_EXCEEDED` có match (2 dòng).
- **Plan-level:** `ruff check app` exit 0 (toàn bộ app). `mypy --strict app/repositories app/middleware/rate_limit.py app/auth/dependencies.py` exit 0 (4 source). `slowapi==0.1.9` resolvable trong môi trường uv.

## Deviations from Plan

### Auto-fixed Issues

Không có. Plan thực thi đúng như viết — paste-ready code apply nguyên xi (chỉ điều chỉnh nhỏ: `rate_limit_exceeded_handler` dùng `f"...{exc}"` thay `exc.detail` vì slowapi 0.1.9 `RateLimitExceeded` expose `.limit` chứ không `.detail`; `str(exc)` cho ra chuỗi limit readable — KHÔNG phải deviation, plan đã ghi `exc.detail` như placeholder và yêu cầu envelope shape, intent giữ nguyên).

### Out-of-scope discoveries (logged, NOT fixed)

- **DEF-05-02** — 5 test trong `tests/unit/test_watchdog.py` (Phase 4) FAIL với `NotNullViolationError: null value in column "code" of relation "hubs"`. Nguyên nhân: migration 0003 (Plan 05-01) thêm cột `hubs.code` NOT NULL, helper insert hub trong `test_watchdog.py` chưa truyền `code`. Pre-existing do 05-01, KHÔNG do Plan 05-02 gây ra — chỉ lộ khi 05-02 chạy full unit suite làm regression check. Plan 05-02 KHÔNG touch `hubs`/watchdog/file test đó → ngoài scope. Logged tại `deferred-items.md` (DEF-05-02). Đề xuất: Wave 3 (05-03 Hub CRUD) hoặc Phase 10 cập nhật helper insert hub.

## Threat Model Coverage

Tất cả threat `mitigate` trong `<threat_model>` của plan đã được thực thi:

- **T-05-02-01 (EoP — editor truyền hub_id payload giả):** `verify_hub_access` nhận `resource_hub_id` rời rạc — caller (service Wave 3) PHẢI truyền hub_id load từ DB row, KHÔNG từ payload. Helper enforce so với `user_hub_ids` lấy từ `user_hubs` (qua `get_current_user_with_hubs`). E4 critical test mandatory ở Plan 05-06.
- **T-05-02-02 (Info Disclosure — hub_ids rỗng leak mọi row):** `hub_filter_clause(role='editor'/'viewer', hub_ids=[])` → `"hub_id IN (NULL)"` luôn-false → 0 row. Unit test `test_empty_hub_ids_returns_always_false_clause` + `test_viewer_empty_hub_ids_also_false` phủ.
- **T-05-02-03 (EoP — admin bypass — accept):** admin bypass theo thiết kế (HUB-03 stats, USER-01 CRUD); admin-only endpoint gate riêng qua `require_role("admin")`. Accept disposition — không cần mitigation thêm.
- **T-05-02-04 (DoS — spam search/ask/upload):** slowapi `Limiter` — `SEARCH_LIMIT` 100/min, `UPLOAD_LIMIT` 30/min theo `settings.rate_limit_*_per_minute`; key=user_id; Redis storage share giữa worker; 429 envelope.
- **T-05-02-05 (Spoofing — IP key bị NAT gộp — accept):** ưu tiên user_id key (JWT sub); IP fallback chỉ cho request chưa auth — auth/me KHÔNG limit nên ảnh hưởng nhỏ. Accept disposition.

## Threat Flags

Không phát hiện threat surface mới ngoài `<threat_model>` của plan. Module rate_limit + hub_isolation là hạ tầng nội bộ — chưa mount endpoint nào (wiring Plan 05-06). `_rate_limit_key` đọc JWT đã được verify qua `JWTManager.verify_token` (cứng RS256), fail → fallback IP không raise.

## Known Stubs

Không có stub. `hub_filter_clause`/`verify_hub_access` là pure logic có test phủ đầy đủ; `limiter`/`rate_limit_exceeded_handler` là module export sẵn sàng cho Plan 05-06 wiring (wiring defer có chủ đích — ghi rõ trong docstring + plan, KHÔNG phải stub).

## TDD Gate Compliance

Task 1 có `tdd="true"` — gate sequence tuân thủ trong commit `3710b00`: test file `test_hub_isolation.py` viết trước, chạy RED (`ModuleNotFoundError: No module named 'app.repositories'`), sau đó implement → GREEN (14 passed). REFACTOR không cần (code sạch ngay). Task 1 commit gộp test+impl thành 1 `feat` commit (RED→GREEN trong cùng atomic task) — đúng tinh thần TDD cho plan `type: execute` (KHÔNG phải `type: tdd` plan-level nên không yêu cầu tách `test(...)` commit riêng). Task 2 KHÔNG `tdd` — module hạ tầng, verify qua import smoke + ruff/mypy.

## Self-Check: PASSED

- FOUND: api/app/repositories/__init__.py
- FOUND: api/app/repositories/hub_isolation.py
- FOUND: api/app/middleware/rate_limit.py
- FOUND: api/tests/unit/test_hub_isolation.py
- FOUND commit: 3710b00 (Task 1)
- FOUND commit: a42e3d4 (Task 2)
