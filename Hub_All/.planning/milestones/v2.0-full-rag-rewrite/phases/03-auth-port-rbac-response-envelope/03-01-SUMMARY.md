---
phase: 3
plan: 01
subsystem: api/middleware + api/pkg/response + api/config
tags: [middleware, envelope, cors, request-id, security-headers, error-handler, p11, p12, d6, auth-01, auth-04]
requires: [02-05]  # Phase 2 schema done (chunks/users/refresh_tokens table exist)
provides: [middleware-chain-p11, envelope-uppercase-go-compat, cors-prod-validator-p12]
affects: [03-02, 03-03, 03-04, 03-05]
tech-stack:
  added: [starlette.middleware.base.BaseHTTPMiddleware]
  patterns: [reversed-middleware-add-order, fail-fast-validator, http-exception-passthrough]
key-files:
  created:
    - Hub_All/api/app/middleware/__init__.py
    - Hub_All/api/app/middleware/request_id.py
    - Hub_All/api/app/middleware/security_headers.py
    - Hub_All/api/app/middleware/error_handler.py
    - Hub_All/api/tests/test_middleware.py
  modified:
    - Hub_All/api/app/pkg/response.py
    - Hub_All/api/app/config.py
    - Hub_All/api/app/main.py
decisions:
  - "Error code = UPPER_SNAKE_CASE match Go pkg/response (D6 — frontend React 19 services/api.ts switch error.code, đổi lowercase break)."
  - "ErrorHandlerMiddleware add LAST (outermost) — pass-through HTTPException để Plan 03-05 exception_handler render envelope, KHÔNG mask thành INTERNAL_ERROR."
  - "CORS prod validator dùng mode='after' (info.data['app_env'] đã populate) — reject LAN/localhost fail-fast startup, KHÔNG defer runtime."
  - "cors_allowed_origins dùng Annotated[list[str], NoDecode] vì pydantic-settings v2 auto-JSON-decode complex types khiến CSV env raise SettingsError."
  - "Test KHÔNG dùng LifespanManager — asyncpg.create_pool blocking trên Windows >5s timeout. Middleware tests không cần DB → ASGITransport raw đủ."
metrics:
  duration_minutes: 9
  completed_date: "2026-05-14"
  tasks_total: 5
  tasks_completed: 5
  tests_total: 9
  tests_passed: 9
  files_created: 5
  files_modified: 3
  commits: 5
---

# Phase 3 Plan 01: Middleware Infra + Envelope Error Helpers + CORS Production Validator — Summary

**Wave 1 contracts cho Phase 3:** Dựng nền móng middleware chain (RequestId / SecurityHeaders / ErrorHandler) + chuẩn hoá envelope error code Go-compat UPPER_SNAKE_CASE + bake P12 production CORS LAN-reject validator. Tất cả 5 task hoàn thành atomic, 9/9 test PASS, sẵn sàng cho Plan 03-02 (JWT keypair) + Plan 03-04 (auth router) sử dụng `resp.unauthorized()`, `resp.forbidden()`, `resp.bad_request()`, `resp.validation_error()` ổn định.

---

## Mục tiêu (Objective)

Plan 03-01 thuộc Wave 1 ("Define contracts") của Phase 3 — sản xuất 3 hợp đồng infra mà mọi auth plan tiếp theo sẽ phụ thuộc:

1. **Response envelope error code Go-compat** — frontend React 19 (D6) switch trên `error.code` UPPER_SNAKE_CASE.
2. **Middleware chain P11-correct** — 4 middleware add đúng REVERSED order (CORS → SecurityHeaders → RequestId → ErrorHandler outermost).
3. **CORS production fail-fast** — `Settings()` raise ngay startup nếu production lọt LAN origin (P12 mitigation).

---

## Tasks hoàn thành (5/5)

| # | Task | Commit | Status |
|---|------|--------|--------|
| 01 | Tạo 4 file middleware infra (`__init__.py`, `request_id.py`, `security_headers.py`, `error_handler.py`) | `14e1e5f` | PASS |
| 02 | Sửa `pkg/response.py` — đổi 9 error code lowercase → UPPER_SNAKE_CASE + thêm `validation_error()` 422 helper | `464902b` | PASS |
| 03 | Thêm `_no_lan_in_prod` validator vào `config.py` (mode='after', kèm `Annotated[..., NoDecode]` fix) | `fb5c9e8` | PASS |
| 04 | Wire 3 middleware vào `main.py` `create_app()` theo P11 reverse order | `3bbca23` | PASS |
| 05 | Tạo `tests/test_middleware.py` — 9 test verify shape + behavior | `5a3c844` | PASS |

---

## Files thay đổi (8 file)

### Created (5)

- `Hub_All/api/app/middleware/__init__.py` — re-export 3 class + `REQUEST_ID_HEADER`
- `Hub_All/api/app/middleware/request_id.py` — `RequestIdMiddleware` (UUID4 sinh/echo)
- `Hub_All/api/app/middleware/security_headers.py` — `SecurityHeadersMiddleware` (5 header match Go)
- `Hub_All/api/app/middleware/error_handler.py` — `ErrorHandlerMiddleware` (catch Exception, pass-through HTTPException)
- `Hub_All/api/tests/test_middleware.py` — 9 unit test

### Modified (3)

- `Hub_All/api/app/pkg/response.py` — 9 error code default lowercase → UPPER_SNAKE_CASE, thêm `validation_error(422)`, thêm note convention
- `Hub_All/api/app/config.py` — thêm `_no_lan_in_prod` validator + `Annotated[list[str], NoDecode]` cho `cors_allowed_origins` + import `re`, `Annotated`, `ValidationInfo`, `NoDecode`
- `Hub_All/api/app/main.py` — import 3 middleware + 3 dòng `app.add_middleware(...)` theo P11 reversed + comment block giải thích

---

## Acceptance Criteria — verification suite

| Check | Command | Kết quả |
|-------|---------|---------|
| Middleware import OK | `python -c "from app.middleware import RequestIdMiddleware, SecurityHeadersMiddleware, ErrorHandlerMiddleware, REQUEST_ID_HEADER"` | exit 0, output `imports OK` |
| Envelope unauthorized UPPER | `python -c "...resp.unauthorized().body...code==UNAUTHORIZED"` | exit 0, `OK` |
| Envelope validation_error 422 | `python -c "...validation_error()...code==VALIDATION_ERROR"` | exit 0, `OK` |
| Lowercase regression check | `grep -Pc '"(unauthorized\|forbidden\|...)"' app/pkg/response.py` | = 0 |
| CORS production reject LAN | `APP_ENV=production CORS_ALLOWED_ORIGINS='http://192.168.1.1:5173' python ... 2>&1 \| grep -c 'Production'` | ≥ 1 |
| CORS dev allow localhost | `APP_ENV=dev CORS_ALLOWED_ORIGINS='http://localhost:5173' python ...` | exit 0, list chứa localhost |
| Middleware order | `python -c "...cors < sec < rid < err..."` | exit 0, `order OK` |
| Middleware wired (4) | `python -c "...len(app.user_middleware) >= 4"` | output `['ErrorHandlerMiddleware', 'RequestIdMiddleware', 'SecurityHeadersMiddleware', 'CORSMiddleware']` |
| pytest tests/test_middleware.py | `uv run pytest tests/test_middleware.py -v` | **9 passed in 0.67s** |
| ruff app/middleware app/pkg/response.py app/main.py app/config.py tests/test_middleware.py | — | All checks passed (7 files) |
| mypy app/middleware app/pkg/response.py app/main.py app/config.py | — | Success: no issues (7 files) |

**Tổng:** 11 acceptance check 11/11 PASS.

---

## Test Suite — 9/9 PASS

```
tests/test_middleware.py::test_request_id_generated_when_missing       PASSED
tests/test_middleware.py::test_request_id_echoed_when_present          PASSED
tests/test_middleware.py::test_security_headers_set                    PASSED
tests/test_middleware.py::test_error_handler_returns_envelope_500      PASSED
tests/test_middleware.py::test_response_envelope_unauthorized_code_uppercase  PASSED
tests/test_middleware.py::test_response_envelope_forbidden_code_uppercase     PASSED
tests/test_middleware.py::test_cors_production_rejects_lan_origin      PASSED
tests/test_middleware.py::test_cors_dev_allows_localhost               PASSED
tests/test_middleware.py::test_http_exception_passes_through           PASSED
============================== 9 passed in 0.67s ==============================
```

Coverage Plan 03-01:
- **RequestId middleware** — 2 test (sinh + echo)
- **SecurityHeaders middleware** — 1 test (5 header)
- **ErrorHandler middleware** — 2 test (Exception → envelope 500, HTTPException pass-through)
- **Envelope error code Go-compat** — 2 test (UNAUTHORIZED, FORBIDDEN)
- **CORS production validator P12** — 2 test (reject LAN, allow localhost dev)

---

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] pydantic-settings v2 JSON-decode complex types break CSV env var**

- **Found during:** Task 03 acceptance run — `CORS_ALLOWED_ORIGINS='http://192.168.1.1:5173'` raise `SettingsError: error parsing value for field "cors_allowed_origins"` vì pydantic-settings v2 default decode complex types qua `json.loads()` TRƯỚC khi gọi `_parse_csv` mode='before' validator.
- **Issue:** Field `cors_allowed_origins: list[str]` → pydantic-settings parser thử `json.loads('http://192.168.1.1:5173')` → JSONDecodeError → SettingsError. `_parse_csv` validator KHÔNG được gọi vì raise xảy ra trong source layer.
- **Fix:** Đổi annotation `cors_allowed_origins: Annotated[list[str], NoDecode] = Field(default_factory=list)`. `NoDecode` (pydantic_settings.sources.types.NoDecode) bypass auto-JSON-decode → raw string đi thẳng vào `_parse_csv`.
- **Files modified:** `Hub_All/api/app/config.py` (+ import `Annotated`, `NoDecode`)
- **Commit:** `fb5c9e8` (gộp cùng Task 03)

**2. [Rule 3 - Blocking] LifespanManager timeout vì asyncpg block trên Windows >5s khi không có Postgres**

- **Found during:** Task 05 initial pytest run — 5 async test fail `TimeoutError` ở `LifespanManager.__aenter__`. Plan paste-ready code dùng `from asgi_lifespan import LifespanManager`.
- **Issue:** Lifespan Phase 1 thử `asyncpg.create_pool(DATABASE_URL)` — không có Postgres trong test env, asyncpg connect attempt block (Windows TCP RST retry slow) > 5s timeout của asgi-lifespan. Lifespan có try/except để KHÔNG crash app, nhưng asgi-lifespan strict timeout cho startup phase.
- **Fix:** Bỏ `LifespanManager` trong test. Middleware tests KHÔNG cần DB/Redis (chỉ verify response shape + headers). Dùng `ASGITransport` raw — pattern khớp `tests/test_main.py` đã hoạt động Phase 1. Healthz route handler không touch DB nên không cần lifespan.
- **Files modified:** `Hub_All/api/tests/test_middleware.py`
- **Commit:** `5a3c844` (đã include trong Task 05 commit)

### Plan acceptance criteria typo (NIT — không phải bug code)

- Plan acceptance task 3: `grep -F '127.0.0.1' Hub_All/api/app/config.py | wc -l` ≥ 1. Code chứa pattern `r"127\.0\.0\.1"` (regex escape dot), `grep -F` fixed-string tìm literal `127.0.0.1` (không backslash) → 0 match. Tuy nhiên intent của criteria là verify pattern handle 127.0.0.1 IP — pattern thực tế `r"127\.0\.0\.1"` match 127.0.0.1 IP đúng. Acceptance text mismatch, code đúng.

### Không deviate

- Tất cả paste-ready code trong plan apply nguyên xi (không sửa logic, chỉ thêm fix Rule 3 cho 2 blocker trên).
- KHÔNG đổi signature helper response.py — chỉ đổi default `code` value (Plan đã ghi rõ "KHÔNG đổi signature").
- KHÔNG đổi `ok()`, `created()`, `accepted()`, `paginated()` — success helpers giữ nguyên.

---

## Key Decisions

1. **Error code UPPER_SNAKE_CASE Go-compat** (Task 02): 9 helper đổi default code lowercase → UPPER (BAD_REQUEST, UNAUTHORIZED, FORBIDDEN, NOT_FOUND, CONFLICT, UNSUPPORTED_FORMAT, RATE_LIMIT_EXCEEDED, INTERNAL_ERROR, SERVICE_UNAVAILABLE). Note convention trong module docstring để Plan 03-04+ KHÔNG fallback lowercase. Frontend React 19 D6 dependency — đổi lowercase break `switch (error.code)` modal lỗi.

2. **HTTPException pass-through** (Task 01 `error_handler.py`): `isinstance(exc, StarletteHTTPException) → raise`. Lý do: FastAPI exception_handler (Plan 03-05 sẽ wire) render envelope shape khớp với endpoint raise HTTPException trực tiếp. Nếu ErrorHandlerMiddleware catch HTTPException → envelope SẼ KHÔNG match → mọi auth 401/403 trả body lạ → frontend D6 không recognize. Threat T-03-http-exception-mask mitigation.

3. **Middleware order P11 reversed** (Task 04): `add CORS → SecurityHeaders → RequestId → ErrorHandler` (LAST = outermost). FastAPI executes last-added FIRST. Outer-to-inner cho REQUEST: `ErrorHandler → RequestId → SecurityHeaders → CORS → router`. Phase 5 AUX-03 sẽ thêm slowapi rate_limit giữa CORS và router.

4. **CORS prod validator mode='after'** (Task 03): cần `info.data["app_env"]` đã populate → KHÔNG dùng mode='before'. Đặt SAU `_parse_csv` (mode='before') đã có sẵn để không xung đột thứ tự validator.

5. **NoDecode workaround pydantic-settings v2** (Task 03 — Rule 3 deviation): `Annotated[list[str], NoDecode]` bypass auto-JSON-decode để CSV `http://a:5173,http://b:5173` env var hoạt động qua `_parse_csv` validator.

6. **Test không dùng LifespanManager** (Task 05 — Rule 3 deviation): Middleware tests dùng ASGITransport raw — pattern khớp `tests/test_main.py`. Lifespan blocking >5s khi không có Postgres trong Windows test env.

---

## Threat Model — Tracking

| Threat ID | Status | Implementation |
|-----------|--------|----------------|
| T-03-01 (I) ErrorHandler leak stack trace | **mitigated** | `error_handler.py` log `exc_info=exc` server-side; response body chỉ chứa `{code: INTERNAL_ERROR, message: "Lỗi máy chủ nội bộ"}`. Test `test_error_handler_returns_envelope_500` assert `"RuntimeError" not in r.text` PASS. |
| T-03-02 (T) X-Request-Id CRLF injection | **accepted** | Starlette `Response.headers[k]=v` đã encode safely. Documented không validate CRLF thủ công. |
| T-03-03 (E) CORS prod LAN leak | **mitigated** | `_no_lan_in_prod` field_validator reject 6 pattern (localhost/127.0.0.1/0.0.0.0/192.168./10./172.16-31.) khi `app_env=='production'`. Test `test_cors_production_rejects_lan_origin` + `test_cors_dev_allows_localhost` cover. |
| T-03-04 (S) X-Forwarded-For spoof | **accepted** | Phase 3 chưa wire rate limit Redis. Phase 5 AUX-03 sẽ add TrustedHostMiddleware + ProxyHeaders. |
| T-03-05 (I) CSP thiếu | **accepted** | M2 chấp nhận CSP defer Phase 10 HARD-04. Interim `X-Content-Type-Options: nosniff` + `X-Frame-Options: DENY`. |

---

## Forward Links (Wave 2-4 dependencies)

**Plan 03-02 (JWT keypair):**
- Sẽ dùng `resp.unauthorized()` cho token invalid/expired (code UNAUTHORIZED).
- Sẽ dùng `RequestIdMiddleware` injected `request.state.request_id` trong JWT verify log.

**Plan 03-03 (Argon2 cross-compat):**
- Sẽ dùng `resp.bad_request()` cho password format invalid.
- Sẽ dùng `resp.internal_error()` cho hash verify exception.

**Plan 03-04 (Auth router):**
- Sẽ dùng `resp.validation_error()` (422 VALIDATION_ERROR) cho pydantic body validation.
- Sẽ dùng `resp.unauthorized()` cho login fail / refresh invalid.
- Sẽ dùng `resp.too_many_requests()` cho login lockout (code RATE_LIMIT_EXCEEDED).
- Sẽ raise `HTTPException(401, ...)` — confirmed pass-through tới Plan 03-05 exception_handler.

**Plan 03-05 (RBAC + exception handler + 5-AC integration test):**
- Sẽ add `app.add_exception_handler(StarletteHTTPException, ...)` render envelope shape (do ErrorHandlerMiddleware đã pass-through).
- Sẽ dùng `resp.forbidden()` cho RBAC reject (code FORBIDDEN).
- Sẽ dùng 5 fixture auth role (super_admin/admin/editor/viewer/anonymous) + integration test mỗi endpoint.

---

## Self-Check: PASSED

**Created files (5/5):**
- FOUND: Hub_All/api/app/middleware/__init__.py
- FOUND: Hub_All/api/app/middleware/request_id.py
- FOUND: Hub_All/api/app/middleware/security_headers.py
- FOUND: Hub_All/api/app/middleware/error_handler.py
- FOUND: Hub_All/api/tests/test_middleware.py

**Modified files (3/3):**
- FOUND: Hub_All/api/app/pkg/response.py (diff: 24 insertions, 10 deletions)
- FOUND: Hub_All/api/app/config.py (diff: 39 insertions, 5 deletions)
- FOUND: Hub_All/api/app/main.py (diff: 20 insertions, 10 deletions)

**Commits (5/5):**
- FOUND: 14e1e5f feat(phase-03): middleware infra
- FOUND: 464902b feat(phase-03): envelope error code Go-compat
- FOUND: fb5c9e8 feat(phase-03): config CORS production validator
- FOUND: 3bbca23 feat(phase-03): wire middleware main.py P11
- FOUND: 5a3c844 test(phase-03): middleware unit tests 9/9 PASS
