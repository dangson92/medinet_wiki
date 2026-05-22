---
phase: 02-hub-con-codebase-factor
plan: 03
subsystem: integration-test-endpoint-matrix
tags:
  - integration-test
  - endpoint-matrix
  - envelope-shape
  - hub-scoped
  - central-only
  - factor-02
  - factor-03
  - d-v3-phase2-d
  - d-v3-phase2-e
  - d-v3-phase2-h
dependency_graph:
  requires:
    - "02-01-PLAN.md (create_app() factory conditional router mount — Wave 1 BLOCKING)"
    - "01-02-PLAN.md (Settings.hub_name + _enforce_hub_dsn_match validator carry forward)"
  provides:
    - "Fixture hub_app_factory parameterized HUB_NAME (central/yte/duoc/hcns) — pattern reuse cho Phase 3+ test SSO multi-hub"
    - "Helper _phase2_build_dsn (DSN suffix endswith /medinet_central or /medinet_hub_<name>) — Settings validator pass"
    - "Starlette HTTPException handler (404 envelope D6 shape) — D-V3-Phase2-E satisfy thực tế (Rule 2 auto-add)"
    - "Endpoint matrix 12 hub-scoped + 8 central-only literal in test file — code review reference"
  affects:
    - "Plan 02-04 (closeout — verify FACTOR-02/03 ở integration level, smoke compose-level checkpoint)"
    - "Phase 3 SSO test (JWKS endpoint multi-hub) — có thể tái dùng hub_app_factory pattern"
tech_stack:
  added:
    - "starlette.exceptions.HTTPException handler (envelope wrap routing 404 — D6 shape) trong app/main.py"
  patterns:
    - "Test-level autouse cleanup CỤC BỘ (WRN-03 fix — autouse trong test file, KHÔNG ở conftest.py)"
    - "Module-global state reset trước boot mới (reset_queue + _engine/_session_factory = None) — DEF-05-01 carry forward"
    - "TestClient(app) in-process boot lifespan — Postgres fail-soft + COCOINDEX_SKIP_SETUP=1 escape hatch"
key_files:
  created:
    - "api/tests/integration/test_factor_hub_scoped.py (228 LOC, 10 test PASS)"
  modified:
    - "api/tests/integration/conftest.py (96 insertions append-only: hub_app_factory + _phase2_build_dsn + reset state defensive)"
    - "api/app/main.py (Rule 2 auto-add — 57 insertions: Starlette HTTPException handler wrap 404 envelope)"
decisions:
  - "D-V3-Phase2-D consumed: 12 endpoint hub-scoped (4 auth + 2 profile + 3 documents + search + ask + usage) — literal HUB_SCOPED_ENDPOINTS trong test"
  - "D-V3-Phase2-E satisfy thực tế: Starlette HTTPException handler wrap routing 404 → envelope shape `{success:false, data:null, error:{code:NOT_FOUND, message}, meta:null}` (Rule 2 auto-add — M2 chỉ register `fastapi.HTTPException`, NOT Starlette base class)"
  - "D-V3-Phase2-H consumed: integration test 4 service mode (central + 3 hub con) qua TestClient in-process (KHÔNG cần docker compose up — Plan 02-04 sẽ smoke compose-level)"
  - "WRN-03 fix: autouse `_phase2_clear_settings_cache_after` CỤC BỘ trong test file (KHÔNG ở conftest.py — tránh affect Phase 1 hub_isolation + Phase 3 v2.0 auth_client fixture chain)"
  - "BLK-01 fix: CENTRAL_ONLY_ENDPOINTS dùng GET /api/sync/stats (endpoint thực tế sync_router M2 compat stub) — KHÔNG legacy Go-era endpoint chưa được port"
  - "Rule 3 fix (audit queue + SQLAlchemy engine reset): hub_app_factory thêm `reset_queue()` + sentinel-None reset `_engine`/`_session_factory` TRƯỚC boot app mới — pattern carry forward từ `app_with_auth` Phase 3 Plan 05"
metrics:
  duration_minutes: 65
  tasks_completed: 2
  files_modified: 3
  tests_added: 10
  tests_pass: 10
  completed_date: 2026-05-22
requirements:
  - FACTOR-02
  - FACTOR-03
---

# Phase 2 Plan 03: Integration test endpoint matrix hub-scoped vs central-only Summary

**One-liner:** Integration test PASS 10/10 verify FACTOR-02 strip semantic (3 hub × 8 endpoint = 24 assertion 404 envelope) + FACTOR-03 mount semantic (3 hub × 12 endpoint = 36 assertion non-404) + central 20 endpoint backward-compat + 404 envelope shape D-V3-Phase2-E + Phase 1 DSN validator regression — đóng FACTOR-02/03 ở integration level qua TestClient in-process (KHÔNG cần docker compose up).

---

## Mục tiêu

Verify endpoint matrix D-V3-Phase2-D ở integration level:

- **12 endpoint hub-scoped MOUNT ở hub con** (yte/duoc/hcns) — status_code != 404 (FACTOR-03):
  4 auth (`/api/auth/{login,refresh,logout,me}`) + 2 profile (`GET/PATCH /api/profile`) + 3 documents (`POST/GET/DELETE /api/documents`) + `POST /api/search` + `POST /api/ask` + `GET /api/usage`.
- **8 endpoint central-only STRIP ở hub con** (yte/duoc/hcns) → 404 envelope shape D-V3-Phase2-E (FACTOR-02):
  `/api/rag-config`, `/api/api-keys`, `/api/hubs`, `/api/users`, `/api/audit-logs`, `/api/system-settings`, `/api/sync/stats` (BLK-01 fix — KHÔNG `/run`), `/api/mcp/my-oauth-client`.
- **Central giữ NGUYÊN 20 endpoint** — M2 backward-compat.
- **Envelope shape verify** D-V3-Phase2-E: `{success:false, data:null, error:{code, message}, meta:null}` — KHÔNG `{"detail":"Not Found"}` raw Starlette.
- **Phase 1 regression**: `_enforce_hub_dsn_match` carry forward — HUB_NAME=yte + DSN central → raise ValidationError.

Test in-process qua `TestClient(app)` — KHÔNG cần docker/testcontainers. Plan 02-04 sẽ smoke compose-level.

---

## Output

### Task 1 — `api/tests/integration/conftest.py` extend (commit `81543e0`)

**Diff:** 96 insertions append-only ở cuối file — KHÔNG đụng `postgres_container`, `alembic_cfg`, `redis_container`, `app_with_auth`, `auth_client`, `admin_user`/`editor_user`/`viewer_user`, `admin_token`/`editor_token`/`viewer_token`/`admin_token_pair` (Phase 1 + Phase 3 v2.0 fixture chain).

**Fixture `hub_app_factory`:**
```python
@pytest.fixture
def hub_app_factory(monkeypatch):
    def _factory(hub_name: str) -> FastAPI:
        monkeypatch.setenv("HUB_NAME", hub_name)
        monkeypatch.setenv("DATABASE_URL", _phase2_build_dsn(hub_name))
        monkeypatch.setenv("COCOINDEX_DATABASE_URL", ".../medinet_cocoindex")
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        monkeypatch.setenv("COCOINDEX_SKIP_SETUP", "1")
        monkeypatch.setenv("APP_ENV", "dev")
        get_settings.cache_clear()
        reset_queue()                         # DEF-05-01 — module-global audit queue reset
        _db_session._engine = None            # SQLAlchemy reset (defensive)
        _db_session._session_factory = None
        from app.main import create_app
        return create_app()
    return _factory
```

**Helper `_phase2_build_dsn(hub_name, async_driver=True)`:**
- `central` → `postgresql+asyncpg://u:p@localhost:5432/medinet_central`
- `<hub>` → `postgresql+asyncpg://u:p@localhost:5432/medinet_hub_<hub>`

**WRN-03 fix:** KHÔNG khai báo `@pytest.fixture(autouse=True)` ở conftest.py. Cleanup `_phase2_clear_settings_cache_after` chuyển vào file test (Task 2). Verify qua `grep -c "autouse=True" conftest.py == 0`.

**Rule 3 auto-fix (audit queue + SQLAlchemy reset):**
- Discovered khi chạy 10 test parametrize: test 2 (yte) treo vĩnh viễn sau test 1 (central) PASS.
- Root cause: `audit_service._queue` module-global bound vào event loop test 1 (TestClient context manager) — test 2 boot lifespan re-init `audit_flush_loop` dùng cùng `_queue` → `await queue.get()` treo trên dead loop.
- Fix: thêm `reset_queue()` + sentinel-None reset `_engine`/`_session_factory` TRƯỚC `create_app()`. Pattern cùng style `app_with_auth` Phase 3 Plan 05.
- Verify post-fix: 10 test PASS trong 8.13s (KHÔNG có test treo).

### Task 2 — `api/tests/integration/test_factor_hub_scoped.py` mới (commit `c5e6036`)

**File:** 228 LOC, 10 test PASS (-m "critical and integration").

| # | Test | Verify |
|---|------|--------|
| 1 | `test_central_mounts_all_endpoints` | Central giữ NGUYÊN 20 endpoint (12 hub-scoped + 8 central-only) — assert status != 404 cho mọi entry |
| 2 | `test_hub_strips_central_only[yte]` | Hub yte STRIP 8 endpoint central-only → 404 envelope (FACTOR-02) |
| 3 | `test_hub_strips_central_only[duoc]` | Hub duoc STRIP 8 endpoint central-only → 404 envelope |
| 4 | `test_hub_strips_central_only[hcns]` | Hub hcns STRIP 8 endpoint central-only → 404 envelope |
| 5 | `test_hub_mounts_hub_scoped[yte]` | Hub yte MOUNT 12 endpoint hub-scoped — status != 404 (FACTOR-03) |
| 6 | `test_hub_mounts_hub_scoped[duoc]` | Hub duoc MOUNT 12 endpoint hub-scoped — status != 404 |
| 7 | `test_hub_mounts_hub_scoped[hcns]` | Hub hcns MOUNT 12 endpoint hub-scoped — status != 404 |
| 8 | `test_404_envelope_shape_hub_strip` | Hub yte + GET /api/rag-config → verify chi tiết `{success:false, data:null, error:{code,message}, meta:null}` (D-V3-Phase2-E) |
| 9 | `test_404_envelope_unknown_route_central` | Central + path không tồn tại → 404 envelope (verify Starlette HTTPException handler wrap mọi 404) |
| 10 | `test_hub_yte_dsn_mismatch_raises` | HUB_NAME=yte + DSN trỏ /medinet_central → Settings raise ValidationError (Phase 1 regression check) |

**HUB_SCOPED_ENDPOINTS literal (D-V3-Phase2-D 12 entry):**
```python
("POST", "/api/auth/login"),
("POST", "/api/auth/refresh"),
("POST", "/api/auth/logout"),
("GET",  "/api/auth/me"),
("GET",  "/api/profile"),
("PATCH", "/api/profile"),
("POST", "/api/documents"),
("GET",  "/api/documents"),
("DELETE", "/api/documents/00000000-0000-0000-0000-000000000000"),
("POST", "/api/search"),
("POST", "/api/ask"),
("GET",  "/api/usage"),
```

**CENTRAL_ONLY_ENDPOINTS literal (D-V3-Phase2-D 8 entry, BLK-01 fix `/api/sync/stats`):**
```python
("GET", "/api/rag-config"),
("GET", "/api/api-keys"),
("GET", "/api/hubs"),
("GET", "/api/users"),
("GET", "/api/audit-logs"),
("GET", "/api/system-settings"),
("GET", "/api/sync/stats"),         # BLK-01: NOT /run (legacy chưa port)
("GET", "/api/mcp/my-oauth-client"),
```

**Autouse cleanup CỤC BỘ (WRN-03 fix):**
```python
@pytest.fixture(autouse=True)
def _phase2_clear_settings_cache_after() -> Iterator[None]:
    from app.config import get_settings
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
```
Trong file test_factor_hub_scoped.py — chỉ ảnh hưởng test trong file, KHÔNG nhiễu Phase 1 hub_isolation + Phase 3 v2.0 fixture chain.

### Task 2 phụ — `api/app/main.py` Rule 2 auto-add Starlette HTTPException handler (commit `c5e6036`)

**Diff:** 57 insertions sau FastAPI HTTPException handler.

**Lý do (Rule 2 — auto-add missing critical functionality):**
- Test `test_hub_strips_central_only[yte]` ban đầu FAIL với `{"detail":"Not Found"}` thay vì envelope.
- Root cause: M2 chỉ register `@app.exception_handler(HTTPException)` cho `fastapi.HTTPException`. Starlette routing 404 raise `starlette.exceptions.HTTPException` (parent class) → KHÔNG match → fallback `{"detail":"Not Found"}` raw.
- FACTOR-02 yêu cầu (D-V3-Phase2-E) envelope shape D6 cho strip semantic — handler riêng cho Starlette base class cover (1) router không mount ở hub con (FACTOR-02 strip), (2) path không tồn tại ở central (typo URL).

**Handler logic:**
```python
@app.exception_handler(StarletteHTTPException)
async def starlette_http_exception_handler(request, exc):
    if isinstance(exc.detail, str):
        if exc.status_code == 404:
            code = "NOT_FOUND"
        elif exc.status_code == 405:
            code = "METHOD_NOT_ALLOWED"
        else:
            code = "ERROR"
        message = exc.detail
    # dict detail / fallback fallthrough
    body = {"success": False, "data": None,
            "error": {"code": code, "message": message}, "meta": None}
    return StarletteJSONResponse(content=body, status_code=exc.status_code,
                                 headers=exc.headers or None)
```

**Handler resolution:** FastAPI ưu tiên subclass-specific handler — `@app.exception_handler(fastapi.HTTPException)` vẫn win cho FastAPI raise; Starlette handler chỉ cover routing 404/405 raw từ Starlette base class.

---

## Verification

| Check | Status |
|---|---|
| `cd Hub_All/api && uv run ruff check tests/integration/conftest.py tests/integration/test_factor_hub_scoped.py app/main.py` | PASS (0 issues) |
| `cd Hub_All/api && uv run mypy tests/integration/conftest.py tests/integration/test_factor_hub_scoped.py app/main.py` | PASS (0 errors) |
| `cd Hub_All/api && uv run pytest tests/integration/test_factor_hub_scoped.py -v -m "critical and integration"` | **10/10 PASS** (6.49s) |
| Phase 1 regression: `pytest tests/unit/test_main_factory.py tests/unit/test_config_hub_name.py -v` | **20/20 PASS** (5.85s) — KHÔNG break |
| Full unit suite regression: `pytest tests/unit -v` | **175/175 PASS** (32.02s) — KHÔNG break |
| Acceptance grep `def hub_app_factory` conftest.py | 1 ✓ |
| Acceptance grep `_phase2_build_dsn` conftest.py | 2 ✓ (def + 1 call) |
| Acceptance grep `COCOINDEX_SKIP_SETUP` conftest.py | 1 ✓ |
| Acceptance grep `medinet_hub_` conftest.py | 1 ✓ |
| Acceptance grep `get_settings.cache_clear` conftest.py | ≥1 ✓ |
| Acceptance grep `FACTOR-01\|FACTOR-02\|FACTOR-03\|D-V3-Phase2` conftest.py | ≥1 ✓ |
| Acceptance grep `def postgres_container` conftest.py | 1 ✓ (KHÔNG xoá) |
| Acceptance grep `def alembic_cfg` conftest.py | 1 ✓ (KHÔNG xoá) |
| Acceptance grep `autouse=True` conftest.py | **0 ✓** (WRN-03 fix) |
| Acceptance grep `HUB_SCOPED_ENDPOINTS` test file | 1 ✓ |
| Acceptance grep `CENTRAL_ONLY_ENDPOINTS` test file | 1 ✓ |
| Acceptance grep `("GET", "/api/sync/stats")` test file | ≥1 ✓ (BLK-01 fix) |
| Acceptance grep exact `"/api/sync/run"` test file | **0 ✓** (BLK-01 grep guard) |
| Acceptance grep 6 test definitions | 6/6 ✓ |
| Acceptance grep `@pytest.fixture(autouse=True)` test file | 1 ✓ (WRN-03 cục bộ) |
| Acceptance grep `@pytest.mark.parametrize("hub_name", ["yte", "duoc", "hcns"])` test file | 2 ✓ (strip + mount) |
| Acceptance grep `pytestmark.*critical.*integration` test file | 1 ✓ (HARD-03 marker) |
| Acceptance grep `DSN mismatch hub_name` test file | 1 ✓ (Phase 1 regression) |

---

## Decisions Made

1. **D-V3-Phase2-D consumed** — 12 endpoint hub-scoped literal trong `HUB_SCOPED_ENDPOINTS`. DELETE endpoint dùng UUID dummy `00000000-...` để route resolve đúng pattern path param. Số liệu chính xác (KHÔNG đếm collective "10 endpoint" từ FACTOR-03 wildcard mô tả — đếm specific 12).

2. **D-V3-Phase2-E satisfy thực tế (Rule 2 auto-add)** — Starlette HTTPException handler wrap routing 404 → envelope D6 shape. M2 documentation claim "ErrorHandlerMiddleware wrap built-in 404" KHÔNG chính xác — M2 chỉ wrap exception raise từ middleware downstream (NOT routing-not-matched 404). Plan 02-03 fix thực tế: register handler riêng cho `starlette.exceptions.HTTPException` (parent class) cover (1) FACTOR-02 strip ở hub con, (2) typo URL ở central.

3. **D-V3-Phase2-H consumed (integration scope)** — Test in-process qua `TestClient(app)` thay vì 4 service docker compose up. Lý do: TestClient boot lifespan synchronously với asyncpg pool fail-soft (Phase 1 skeleton) + `COCOINDEX_SKIP_SETUP=1` escape hatch → đủ verify FACTOR-02/03 ở route-table level. Plan 02-04 sẽ smoke compose-level (curl matrix 2 service central + yte) với Docker thật.

4. **WRN-03 fix (autouse cleanup CỤC BỘ)** — `_phase2_clear_settings_cache_after` autouse khai báo TRONG `test_factor_hub_scoped.py` (NOT conftest.py). Lý do: autouse ở conftest.py sẽ chạy cho mọi test trong `tests/integration/` (bao gồm Phase 1 `test_hub_isolation_db_level.py` + Phase 3 v2.0 `auth_client` chain) → clear lru_cache singleton giữa assert → flaky risk.

5. **BLK-01 fix (`/api/sync/stats` thay `/api/sync/run`)** — Verify từ source `api/app/routers/sync.py` line 39: `@router.get("/stats")` thực sự tồn tại; `/api/sync/run` chỉ có ở backend Go cũ (archived `m1-go-archived` tag), KHÔNG bao giờ được port sang M2. Endpoint matrix dùng đúng endpoint thực tế.

6. **Rule 3 auto-fix (audit queue + SQLAlchemy engine reset)** — `hub_app_factory` thêm `reset_queue()` + sentinel-None reset cho `_engine`/`_session_factory`. Pattern carry forward từ `app_with_auth` Phase 3 Plan 05. Lý do: `TestClient(app)` context manager mỗi test tạo event loop riêng — module-global `_queue` bound vào loop cũ → `audit_flush_loop` test sau treo vĩnh viễn.

---

## Deviations from Plan

**3 deviations áp dụng (Rule 2 + Rule 3):**

### Rule 2 — Auto-add Starlette HTTPException handler

- **Found during:** Task 2, pytest `test_hub_strips_central_only[yte]` FAIL ban đầu với `{"detail":"Not Found"}` thay vì envelope.
- **Issue:** Plan giả định "ErrorHandlerMiddleware M2 wrap 404 envelope" (CONTEXT.md D-V3-Phase2-E + Plan 02-01 docstring) — verify thực tế **SAI**. M2 chỉ register `@app.exception_handler(HTTPException)` cho `fastapi.HTTPException`. Starlette routing 404 raise `starlette.exceptions.HTTPException` (parent class) — KHÔNG match handler.
- **Fix:** Thêm `@app.exception_handler(StarletteHTTPException)` cover routing 404 → render envelope D6 shape qua `JSONResponse` raw. Code `NOT_FOUND` (status 404), `METHOD_NOT_ALLOWED` (status 405), `ERROR` (fallback).
- **Files modified:** `api/app/main.py` (57 insertions).
- **Commit:** `c5e6036`.

### Rule 3 — Auto-fix audit queue cross-loop hang

- **Found during:** Task 2, pytest full run treo vĩnh viễn ở test 2 (yte) sau test 1 (central) PASS.
- **Issue:** `audit_service._queue` module-global `asyncio.Queue` bound vào event loop test 1 (TestClient context manager). Test 2 boot lifespan re-tạo `audit_flush_loop` dùng cùng `_queue` → `await queue.get()` treo vĩnh viễn trên dead loop. Pattern này đã được biết ở Phase 3 Plan 05 (`app_with_auth` fixture có `reset_queue()`).
- **Fix:** `hub_app_factory` thêm `reset_queue()` + sentinel-None reset cho `_engine`/`_session_factory` TRƯỚC `create_app()`.
- **Files modified:** `api/tests/integration/conftest.py` (8 insertions trong factory).
- **Commit:** `c5e6036`.

### Rule 3 — Comment refactor BLK-01 grep guard

- **Found during:** Acceptance grep verify `grep -c '"/api/sync/run"' == 0` initially returned 1 (false positive — comment chứa exact string).
- **Issue:** Documentation comment dùng exact `"/api/sync/run"` string làm warning — vô tình trigger grep guard.
- **Fix:** Rewrite comment để mô tả endpoint legacy mà KHÔNG dùng exact-string `"/api/sync/run"`. Logic test KHÔNG đổi.
- **Files modified:** `api/tests/integration/test_factor_hub_scoped.py` (4 line comment rewrite).
- **Commit:** `c5e6036`.

---

## Authentication Gates

**None.** Test integration boot app in-process qua `TestClient(app)` — lifespan asyncpg.create_pool fail-soft (Phase 1 skeleton), cocoindex skip qua `COCOINDEX_SKIP_SETUP=1`. KHÔNG cần Postgres/Redis thật, KHÔNG cần JWT token.

---

## Notable Implementation Details

### `TestClient(app)` boot lifespan in-process

`fastapi.testclient.TestClient` (httpx-based + Starlette) — `with TestClient(app) as client:` block trigger lifespan startup TRƯỚC khi yield client, shutdown SAU khi exit block. Plan 02-03 consume pattern này thay vì `asgi-lifespan.LifespanManager` (async fixture) — đơn giản hơn cho test sync.

Lifespan startup ở mỗi test:
1. asyncpg.create_pool → fail-soft warning (DSN trỏ `localhost:5432/medinet_hub_yte` KHÔNG có DB thật).
2. redis.from_url + ping → fail-soft (`localhost:6379/0` KHÔNG có Redis thật).
3. `cocoindex_setup_skipped` (COCOINDEX_SKIP_SETUP=1).
4. JWT manager init (keys/private.pem + public.pem từ M2 dev).
5. SQLAlchemy `init_engine` create engine.
6. Watchdog asyncio task start (CHỈ tick mỗi 60s — KHÔNG block startup).
7. Audit flush task start (`audit_flush_loop` blocked ở `queue.get()`).
8. Search cache subscriber skip (redis fail-soft → `app.state.redis = None`).

Toàn bộ chuỗi này hoàn thành <1s mặc dù connection fail (asyncpg timeout fast).

### Event loop binding `audit_service._queue`

`asyncio.Queue` instance bound vào event loop tạo nó. `TestClient` mỗi test tạo loop mới (Starlette `anyio` portal). Module-global `_queue` từ test trước vẫn point vào loop cũ → khi `audit_flush_loop` ở loop mới gọi `await _queue.get()` → treo vĩnh viễn (waiting for future bound to dead loop).

`reset_queue()` set `_queue = None`; `_get_queue()` lazy-init queue mới trên loop hiện tại. Pattern bắt buộc cho mọi test boot app nhiều lần. Đã có ở Phase 3 Plan 05 `app_with_auth`; Plan 02-03 carry forward cho factory pattern.

### Starlette vs FastAPI HTTPException

```python
# Starlette (base class, raised by routing)
class StarletteHTTPException(Exception):
    def __init__(self, status_code, detail=None, headers=None): ...

# FastAPI (subclass, raised by handler-explicit raise)
class HTTPException(StarletteHTTPException):
    def __init__(self, status_code, detail=None, headers=None): ...
```

FastAPI handler `@app.exception_handler(fastapi.HTTPException)` match CHỈ subclass. Starlette routing 404 raise parent class instance. Plan 02-03 register handler riêng cho Starlette base class — FastAPI subclass-specific handler vẫn ưu tiên cho explicit raise.

---

## Next Steps

**Plan 02-03 đóng FACTOR-02 + FACTOR-03 ở integration level (TestClient in-process).** Wave 2 hoàn thành.

- **Plan 02-04 (Wave 3 closeout, NEXT):**
  - Task 1 `checkpoint:human-action` — smoke compose 2 service central + yte (`docker compose up python-api-central python-api-yte`) + curl matrix verify endpoint thật. Cần Docker Desktop running.
  - Task 2-4 closeout: CLAUDE.md section 2 update Phase 2 DONE + STATE.md move + REQUIREMENTS.md mark FACTOR-01/02/03 ✓.

**FACTOR-03 wildcard "10 endpoint" vs specific 12:** Coverage hoàn chỉnh — verify 12 specific endpoint mount ở hub con (4 auth + 2 profile + 3 documents + search + ask + usage). REQUIREMENTS.md FACTOR-03 mô tả "10 collective" wildcard nhóm — implementation thực tế là 12 specific. Plan 02-04 sẽ update REQUIREMENTS.md docs "10 collective / 12 specific" để traceability.

---

## Self-Check: PASSED

**Files verified exist:**
- `Hub_All/api/tests/integration/test_factor_hub_scoped.py` — FOUND (created, 228 LOC, 10 test)
- `Hub_All/api/tests/integration/conftest.py` — FOUND (modified, +96 insertions append-only)
- `Hub_All/api/app/main.py` — FOUND (modified, +57 insertions Rule 2 fix)

**Commits verified exist:**
- `81543e0` — `test(02-03): extend integration conftest với hub_app_factory fixture` — FOUND
- `c5e6036` — `test(02-03): integration test endpoint matrix FACTOR-02/03 + 404 envelope` — FOUND

**Test results verified:**
- `tests/integration/test_factor_hub_scoped.py` — **10/10 PASS** (-m "critical and integration", 6.49s)
- Phase 1 + Plan 02-01 regression — `tests/unit/test_main_factory.py` + `tests/unit/test_config_hub_name.py` — **20/20 PASS** (5.85s)
- Full unit suite — **175/175 PASS** (32.02s) — KHÔNG break

**Acceptance criteria verified:** Tất cả grep + smoke check trong `<acceptance_criteria>` block của Task 1 + Task 2 PASS. Specific gate:
- `grep -c '"/api/sync/run"' == 0` ✓ (BLK-01 fix)
- `grep -c "autouse=True" conftest.py == 0` ✓ (WRN-03 fix)
- `grep -c "@pytest.fixture(autouse=True)" test_factor_hub_scoped.py == 1` ✓ (autouse CỤC BỘ)

---

*Plan 02-03 completed 2026-05-22. Wave 2 FINAL ✅ — Plan 02-04 (Wave 3 closeout) sẵn sàng execute với 1 checkpoint:human-action gate cho smoke compose.*
