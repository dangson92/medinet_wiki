---
phase: 03-auth-sso-hub-ids-jwt
plan: 04
subsystem: auth
tags:
  - auth-router-refactor
  - hub-redirect-307
  - phase-2-carry-forward
  - factor-03-update
  - d-v3-phase3-g
  - settings-central-url
  - sso-02
  - rfc-7231-method-preserving

# Dependency graph
requires:
  - phase: 03-auth-sso-hub-ids-jwt
    provides: "Plan 03-03 ship JWT aud/hub_ids REQUIRED + Redis blacklist key rename `auth:blacklist:` + get_current_user_for_hub_access Layer 3 — Plan 03-04 router refactor KHÔNG đụng claim shape/service.py, chỉ thêm 307 branch ở login + refresh handler"
  - phase: 03-auth-sso-hub-ids-jwt
    provides: "Plan 03-02 ship Settings model_validator pattern `_enforce_central_jwks_url_for_hub` — Plan 03-04 add `_enforce_central_url_for_hub` cùng pattern (tách field central_url vì base URL khác full JWKS URL endpoint)"
  - phase: 02-hub-con-codebase-factor
    provides: "Plan 02-03 ship hub_app_factory fixture + 12 endpoint hub-scoped matrix assertion `!= 404` — Plan 03-04 Task 3 split assertion: 10 LOCAL `!= 404` + 2 SSO REDIRECT `== 307`"
provides:
  - "auth_router login + refresh trả 307 RedirectResponse ở hub con (preserve POST + body RFC 7231), central giữ M2 logic local handle"
  - "Settings.central_url field mới + model_validator `_enforce_central_url_for_hub` (hub con required, fail-fast boot)"
  - "Docker-compose 3 hub con + override.yml.template env CENTRAL_URL=http://python-api-central:8080"
  - "Phase 2 integration test split assertion — 10 LOCAL + 2 SSO REDIRECT (HUB_SCOPED_LOCAL_ENDPOINTS + HUB_SCOPED_SSO_REDIRECT_ENDPOINTS)"
  - "REQUIREMENTS.md FACTOR-03 note extend Plan 03-04 SSO-02 (10 LOCAL + 2 SSO REDIRECT clarify)"
  - "_sso_redirect(target_path, hub_name) helper extract pattern + defensive 503 fallback envelope nếu central_url None runtime"
  - "X-SSO-Redirect-Reason + X-SSO-Original-Hub headers cho debug + observability"
affects:
  - "03-05 (Wave 5 closeout) — smoke compose 2 service runtime (central + yte) verify Plan 03-04 redirect E2E: hub yte POST /api/auth/login → 307 → browser follow → central handle → JWT trả về; README banner backward incompat triple (kid Plan 03-02 + aud/hub_ids Plan 03-03 + redirect form Plan 03-04 — frontend M2 hardcode /api/auth/login same-origin sẽ FAIL ở hub con cho tới Phase 5 PROXY-02 wire form action)"
  - "05 PROXY-02 — frontend rewrite `<form action='https://central/api/auth/login'>` sau D6 expire — backend 307 đã sẵn sàng từ Plan 03-04"
  - "07 MIGRATE-04 — MCP service re-point central pattern KHÔNG ảnh hưởng (Phase 2 Plan 02-01 đã set MCP_API_BASE_URL=http://python-api-central:8080)"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "307 Temporary Redirect RFC 7231 method-preserving — browser auto-follow POST + body. fastapi.responses.RedirectResponse(status_code=307, url=...)"
    - "response_model=None decorator opt-out — required khi return type union JSONResponse | RedirectResponse (FastAPI cố parse thành Pydantic field → FastAPIError nếu KHÔNG opt-out)"
    - "TestClient(app, follow_redirects=False) — KHÔNG follow tự động (default follow → mất 307 status code + Location header)"
    - "Settings model_validator extend pattern — 1 validator/field tách (central_jwks_url vs central_url) thay vì gộp (clarity + extensibility cho N field tương lai)"
    - "X-SSO-Redirect-Reason + X-SSO-Original-Hub headers — debug observability convention (snake_case header value match Caddy log format)"

key-files:
  created:
    - "Hub_All/api/tests/unit/test_auth_router_hub_redirect.py — 10 unit test 307 redirect (6 parametrize 3 hub × 2 endpoint + 4 LOCAL handle/central path)"
    - "Hub_All/.planning/phases/03-auth-sso-hub-ids-jwt/03-04-SUMMARY.md (file này)"
  modified:
    - "Hub_All/api/app/auth/router.py +90 LOC (login + refresh hub con branch 307 + _sso_redirect helper + module docstring update Plan 03-04 scope) — 115 → 205 LOC"
    - "Hub_All/api/app/config.py +27 LOC (Settings.central_url field + _enforce_central_url_for_hub model_validator) — 349 → 376 LOC"
    - "Hub_All/docker-compose.yml +9 LOC (CENTRAL_URL env × 3 hub con yte/duoc/hcns) — KHÔNG đụng central block"
    - "Hub_All/docker-compose.override.yml.template +3 LOC (CENTRAL_URL env cho FACTOR-04 hub mới inherit)"
    - "Hub_All/api/tests/unit/test_config_jwks.py +60 LOC (3 test mới Plan 03-04 + update 2 test cũ Plan 03-02 thêm CENTRAL_URL setenv) — 109 → 200+ LOC"
    - "Hub_All/api/tests/unit/test_config_hub_name.py +4 LOC Rule 3 (2 test thêm CENTRAL_URL setenv)"
    - "Hub_All/api/tests/unit/test_config_hub_name_dynamic.py +2 LOC Rule 3 (`_set_env` helper auto-set)"
    - "Hub_All/api/tests/unit/test_jwks_publish.py +3 LOC Rule 3 (`_setup_env` auto-set CENTRAL_URL)"
    - "Hub_All/api/tests/unit/test_main_factory.py +2 LOC Rule 3 (`_setup_env` auto-set CENTRAL_URL)"
    - "Hub_All/api/tests/unit/test_flow_per_hub_naming.py +2 LOC Rule 3 (subprocess env yte thêm CENTRAL_URL)"
    - "Hub_All/api/tests/unit/test_get_current_user_jwks_branch.py +2 LOC Rule 3 (`_common_hub_env` helper auto-set)"
    - "Hub_All/api/tests/integration/conftest.py +2 LOC Rule 3 (`hub_app_factory` fixture set CENTRAL_URL cho hub con)"
    - "Hub_All/api/tests/integration/test_factor_hub_scoped.py +67 LOC (split HUB_SCOPED_ENDPOINTS thành SSO_REDIRECT + LOCAL list + refactor test_hub_mounts_hub_scoped 2 sub-loop + sso_valid_bodies dict cho login/refresh body Pydantic-valid)"
    - "Hub_All/.planning/REQUIREMENTS.md +14 LOC (FACTOR-03 note extend Plan 03-04 SSO-02 — 10 LOCAL + 2 SSO REDIRECT clarify; KHÔNG đụng note WRN-05 Plan 02-04 + label gốc)"

key-decisions:
  - "D-V3-Phase3-G consumed (LOCKED CONTEXT.md): Hub con `/api/auth/login` + `/api/auth/refresh` → 307 Location: central (KHÔNG 405 Method Not Allowed). 307 vs 308: temporary by design (operator dễ switch central URL); 307 vs 302: preserve POST + body (302 lịch sử POST→GET browser quirk)"
  - "D-V3-Phase3-C re-confirm (Plan 03-03 đã consume): Hub con KHÔNG sinh refresh token — Plan 03-04 wire cuối cùng: refresh handler trả 307 thay vì handle local (Plan 03-03 đã ship blacklist key rename + service.py refactor)"
  - "D-V3-Phase3-F honored (frontend redirect defer Phase 5 PROXY-02): Plan 03-04 chỉ ship BACKEND 307 handler. Frontend M2 hiện tại hardcode `/api/auth/login` same-origin sẽ FAIL ở hub con post-Plan 03-04 deploy — acceptable trong v3.0-a dev (Phase 5 fix sau D6 expire)"
  - "Field tách central_url khỏi central_jwks_url (Claude's Discretion): central_jwks_url = full URL endpoint `/.well-known/jwks.json` (immutable path); central_url = base URL build N endpoint khác (login, refresh, future endpoints). Validator riêng từng field cho clarity + extensibility"
  - "_sso_redirect helper extract (Claude's Discretion): pattern DRY giữa login + refresh handler. Defensive 503 envelope fallback nếu central_url None ở runtime (impossible vì Settings validator Task 1 enforce required, paranoid guard cho future refactor) — KHÔNG raise (KHÔNG để Starlette HTTPException handler wrap, JWKS-specific SERVICE_UNAVAILABLE code tường minh)"
  - "response_model=None decorator opt-out (Rule 1 bug fix): FastAPI cố parse return type union `JSONResponse | RedirectResponse` thành Pydantic field → FastAPIError 'Invalid args for response field'. Opt-out qua decorator param required. Pattern này áp dụng cho mọi endpoint tương lai trả union response type"
  - "Test body Pydantic-valid cho login/refresh (Rule 1 bug fix - test): integration test Task 3 KHÔNG `json={}` vì Pydantic validation reject 422 TRƯỚC handler chạy → KHÔNG có branch redirect 307 → test fail. Pivot dùng dict sso_valid_bodies với email/password + refresh_token field hợp lệ"

patterns-established:
  - "Pattern 1 (Plan 03-04 - 307 redirect hub con): `if settings.hub_name != 'central': return RedirectResponse(url=f'{settings.central_url}{target_path}', status_code=307, headers={'X-SSO-Redirect-Reason': ..., 'X-SSO-Original-Hub': ...})`. Áp dụng được cho mọi endpoint future cần redirect hub con → central (vd cross-hub aggregation endpoint nếu cần)"
  - "Pattern 2 (Plan 03-04 - response_model=None opt-out): Endpoint trả union response type (JSONResponse | RedirectResponse | FileResponse v.v.) PHẢI có `response_model=None` ở decorator. FastAPI default cố parse Pydantic field → FastAPIError nếu union với non-Pydantic type. Pattern reuse được cho Phase 5 PROXY-02 endpoint serve frontend assets nếu cần"
  - "Pattern 3 (Plan 03-04 - TestClient follow_redirects=False): integration + unit test verify 307 PHẢI explicit `follow_redirects=False` (TestClient default follow → resolve URL → mất 307 + Location). Áp dụng được cho mọi test future verify redirect (vd test Caddy reverse proxy Phase 5)"
  - "Pattern 4 (Plan 03-04 - integration test body Pydantic-valid): khi test endpoint mount + handler logic (KHÔNG chỉ Pydantic validation), body PHẢI hợp lệ — Pydantic validation reject 422 trước handler chạy. Dict `sso_valid_bodies` map endpoint → body sample. Pattern reuse cho Phase 4 SYNC test nếu cần verify endpoint behavior sau validation"
  - "Pattern 5 (Plan 03-04 - field tách + validator riêng): Settings field tách vì semantic khác (central_jwks_url full URL endpoint vs central_url base URL build N endpoint khác). Validator riêng từng field cho fail-fast + clarity. Pattern reuse cho Phase 6 SETTINGS hub config-driven nếu thêm field"

requirements-completed:
  - SSO-02

# Metrics
duration: 17min
completed: 2026-05-22
---

# Phase 3 Plan 04: Hub Con Auth Router 307 Redirect Summary

**Hub con `/api/auth/login` + `/api/auth/refresh` refactor từ "handle local" (Phase 2 M2 carry forward) → "307 Location: central" (D-V3-Phase3-G LOCKED — browser auto-follow + preserve POST + body RFC 7231). `/api/auth/logout` + `/api/auth/me` GIỮ NGUYÊN local handle (verify JWT qua JWKSCache Plan 03-02 + Redis blacklist chung Plan 03-03). Settings.central_url field mới + `_enforce_central_url_for_hub` model_validator fail-fast boot. Docker-compose 3 hub con + override.yml.template env CENTRAL_URL. Phase 2 integration test split 2 list (10 LOCAL + 2 SSO REDIRECT) + assertion update. REQUIREMENTS.md FACTOR-03 note extend Plan 03-04 SSO-02. M2 backward incompat triple cumulative (kid Plan 03-02 + aud/hub_ids Plan 03-03 + redirect frontend Plan 03-04) — frontend wire defer Phase 5 PROXY-02 sau D6 expire.**

## Performance

- **Duration:** ~17 phút (4 task tuần tự + 1 Rule 3 regression follow-up)
- **Started:** 2026-05-22T08:04:15Z
- **Completed:** 2026-05-22T08:21:14Z
- **Tasks:** 4/4 (Task 1 Settings 4min + Task 2 router refactor + 10 test 6min + Task 3 integration test split 4min + Task 4 REQUIREMENTS note 3min)
- **Files modified:** 14 (2 mới: 1 test unit + SUMMARY + 12 sửa: router.py + config.py + docker-compose × 2 + 8 test file Rule 3 regression + REQUIREMENTS.md)

## Accomplishments

- **Settings.central_url field + validator** trong `api/app/config.py`:
  - Field `central_url: str | None = None` sau `jwks_max_stale_seconds` (Plan 03-02 block).
  - Validator `_enforce_central_url_for_hub` raise ValueError nếu hub_name != "central" + central_url None — fail-fast boot (T-03-04-01/04 mitigation).
  - Field tách khỏi `central_jwks_url` (Plan 03-01) vì semantic khác: jwks_url = full endpoint URL, central_url = base URL build N endpoint.

- **auth_router.post login + refresh refactor** trong `api/app/auth/router.py`:
  - Branch `if settings.hub_name != "central"` trả `RedirectResponse(status_code=307, url=f'{settings.central_url}/api/auth/{login,refresh}')`.
  - Central path giữ NGUYÊN M2 logic (AuthService.login/refresh + AuthError handling).
  - `_sso_redirect(target_path, hub_name)` helper extract pattern DRY + defensive 503 envelope fallback (paranoid guard nếu central_url None runtime).
  - X-SSO-Redirect-Reason + X-SSO-Original-Hub headers cho debug + observability.
  - `response_model=None` decorator opt-out (Rule 1 bug fix — FastAPI parse union type fail).
  - logout + me KHÔNG đụng (D-V3-Phase3-G clarify: handle local cả hub con).

- **Docker-compose env CENTRAL_URL** cho 3 hub con (yte/duoc/hcns) + override.yml.template (FACTOR-04 hub mới inherit qua `make hub-add`).

- **Phase 2 integration test split assertion** trong `tests/integration/test_factor_hub_scoped.py`:
  - HUB_SCOPED_ENDPOINTS (12 baseline) tách thành HUB_SCOPED_SSO_REDIRECT_ENDPOINTS (2) + HUB_SCOPED_LOCAL_ENDPOINTS (10).
  - `test_hub_mounts_hub_scoped` refactor 2 sub-loop: Group 1 (10 LOCAL `!= 404`) + Group 2 (2 SSO REDIRECT `== 307` + Location header verify trỏ central).
  - TestClient `follow_redirects=False` critical.
  - sso_valid_bodies dict (login: email/password + refresh: refresh_token) — Pydantic-valid body để handler branch chạy.

- **REQUIREMENTS.md FACTOR-03 note extend** Plan 03-04 SSO-02 clarify (10 LOCAL + 2 SSO REDIRECT 307). KHÔNG đụng note WRN-05 Phase 2 + label gốc + ROADMAP.md.

- **10 unit test mới PASS** trong `tests/unit/test_auth_router_hub_redirect.py`:
  - 6 parametrize 3 hub × 2 endpoint (login + refresh) → 307 Location + headers verify.
  - 2 test hub_con local handle (logout + me KHÔNG 307).
  - 2 test central local handle (login + refresh KHÔNG 307).

- **Regression KHÔNG break:**
  - 276/276 unit test PASS (full suite — 10 mới Plan 03-04 + 266 baseline Phase 1+2+M2+Plan 03-01/02/03).
  - 16/16 integration critical+integration marker PASS (10 Phase 2 + 3 Plan 03-02 + 3 Plan 03-03).
  - 7 file test Rule 3 fix tự động auto-set CENTRAL_URL cho hub con scenario.
  - Lint clean (`ruff check app/auth/router.py app/config.py + 5 test file` exit 0).
  - Type clean (`mypy --strict app/auth/router.py app/config.py`).
  - Docker compose config render OK.

## Task Commits

| Task | Commit | Type | Description |
|------|--------|------|-------------|
| Task 1 | `86d58c6` | feat | Settings.central_url + validator hub con required + docker-compose CENTRAL_URL env (3 hub con + override template) + 3 test mới + 5 file test Rule 3 regression |
| Task 2 | `e3ea667` | feat | auth_router login + refresh 307 redirect hub con (SSO-02) + _sso_redirect helper + response_model=None opt-out + 10 unit test mới |
| Task 3 | `c862148` | test | factor_hub_scoped assertion 307 cho login + refresh hub con (split 2 list + 2 sub-loop + sso_valid_bodies dict) |
| Task 4 | `48549ee` | docs | REQUIREMENTS.md FACTOR-03 note extend Plan 03-04 SSO-02 (10 LOCAL + 2 SSO REDIRECT clarify) |
| Rule 3 follow-up | `2372747` | test | test_get_current_user_jwks_branch _common_hub_env thêm CENTRAL_URL (Plan 03-02/03 regression fix) |
| SUMMARY | (pending) | docs | This file |

## Files Created/Modified

### Created (2)

- **`api/tests/unit/test_auth_router_hub_redirect.py`** (190 LOC) — 10 test:
  - 6 parametrize 3 hub × 2 endpoint → 307 redirect to central + headers verify.
  - 2 hub_con local handle (logout + me KHÔNG 307; 401 vì thiếu Bearer).
  - 2 central local handle (login + refresh KHÔNG 307; 401/422/500/503).
- **`.planning/phases/03-auth-sso-hub-ids-jwt/03-04-SUMMARY.md`** (file này)

### Modified (12)

- **`api/app/auth/router.py`** (+90 LOC, 115 → 205): module docstring update Plan 03-04 scope + import `RedirectResponse` + import `get_settings` + `_sso_redirect` helper + login + refresh branch 307 hub con (`if settings.hub_name != "central": return _sso_redirect(...)`) + `response_model=None` opt-out 2 decorator + central path giữ nguyên M2 logic.
- **`api/app/config.py`** (+27 LOC, 349 → 376): Settings field `central_url: str | None = None` sau jwks_max_stale_seconds + `@model_validator(mode="after")` `_enforce_central_url_for_hub` raise nếu hub_name != "central" + central_url falsy. Comment docstring trace D-V3-Phase3-G + threat T-03-04-01/04.
- **`docker-compose.yml`** (+9 LOC): env `CENTRAL_URL: http://python-api-central:8080` × 3 hub con (yte/duoc/hcns) ngay sau CENTRAL_JWKS_URL. Central block KHÔNG sửa.
- **`docker-compose.override.yml.template`** (+3 LOC): env CENTRAL_URL cho hub mới `make hub-add` inherit (FACTOR-04 Plan 02-05 carry forward).
- **`api/tests/unit/test_config_jwks.py`** (+60 LOC, 109 → 169): 3 test mới Task 1 (default None central + parametrize 4 hub con required + parametrize 4 hub với cả 2 URL set OK) + update 2 test cũ Plan 03-02 thêm CENTRAL_URL setenv. 20 test PASS.
- **`api/tests/unit/test_config_hub_name.py`** (+4 LOC Rule 3): 2 test (test_yte + test_dsn_with_query) thêm CENTRAL_URL setenv.
- **`api/tests/unit/test_config_hub_name_dynamic.py`** (+2 LOC Rule 3): `_set_env` helper auto-set CENTRAL_URL khi hub_name != "central".
- **`api/tests/unit/test_jwks_publish.py`** (+3 LOC Rule 3): `_setup_env` auto-set CENTRAL_URL.
- **`api/tests/unit/test_main_factory.py`** (+2 LOC Rule 3): `_setup_env` auto-set CENTRAL_URL.
- **`api/tests/unit/test_flow_per_hub_naming.py`** (+2 LOC Rule 3): subprocess env yte thêm CENTRAL_URL.
- **`api/tests/unit/test_get_current_user_jwks_branch.py`** (+2 LOC Rule 3 follow-up): `_common_hub_env` helper auto-set.
- **`api/tests/integration/conftest.py`** (+2 LOC Rule 3): `hub_app_factory` fixture set CENTRAL_URL cho hub con (Plan 03-04 Task 3 integration test depend).
- **`api/tests/integration/test_factor_hub_scoped.py`** (+67 LOC): split HUB_SCOPED_ENDPOINTS → HUB_SCOPED_SSO_REDIRECT_ENDPOINTS (2) + HUB_SCOPED_LOCAL_ENDPOINTS (10) + refactor `test_hub_mounts_hub_scoped` 2 sub-loop + `TestClient(follow_redirects=False)` + sso_valid_bodies dict.
- **`.planning/REQUIREMENTS.md`** (+14 LOC): FACTOR-03 note extend Plan 03-04 SSO-02 clarify 10 LOCAL + 2 SSO REDIRECT + traceability test_auth_router_hub_redirect.py + frontend defer Phase 5 PROXY-02.

## Decisions Made

- **D-V3-Phase3-G consumed** (LOCKED CONTEXT.md): Hub con `/api/auth/login` + `/api/auth/refresh` → 307 Location: central. Plan 03-04 chọn 307 (Temporary Redirect, RFC 7231) thay vì:
  - **308** (Permanent Redirect): cache aggressive — operator switch central URL phức tạp.
  - **302** (Found): lịch sử POST→GET browser quirk — mất body LoginRequest JSON.
  - **405** (Method Not Allowed): browser form re-render fail, KHÔNG có Location.
  - 307 preserve POST + body (RFC 7231 method-preserving) + browser auto-follow tự nhiên.

- **D-V3-Phase3-C re-confirm** (Plan 03-03 đã consume): Hub con KHÔNG sinh refresh token — Plan 03-04 wire cuối cùng. Service refresh logic (Plan 03-03 service.py refactor blacklist key) ở central only; hub con refresh handler trả 307 thay vì gọi service local.

- **D-V3-Phase3-F honored** (frontend redirect defer Phase 5 PROXY-02): Plan 03-04 chỉ ship BACKEND 307 handler. Frontend M2 hiện tại hardcode `/api/auth/login` same-origin → POST tới hub con sẽ FAIL trong v3.0-a dev mode (acceptable). Phase 5 PROXY-02 wire `<form action="https://central/api/auth/login">` sau D-V3-Phase3-F + D-V3-06 D6 expire.

- **Field tách `central_url` khỏi `central_jwks_url`** (Claude's Discretion): semantic khác nhau:
  - `central_jwks_url`: full URL endpoint `/.well-known/jwks.json` (immutable path).
  - `central_url`: base URL không suffix — dùng build N endpoint khác (login, refresh, future endpoints như profile sync Phase 6).
  - Validator riêng từng field cho clarity + extensibility. Plan 03-04 KHÔNG default `central_jwks_url = f"{central_url}/.well-known/jwks.json"` — operator có thể override riêng (vd JWKS endpoint qua CDN khác URL).

- **`_sso_redirect` helper extract** (Claude's Discretion): pattern DRY giữa login + refresh handler. Defensive 503 envelope fallback (impossible reach runtime vì validator Task 1 enforce required, nhưng paranoid guard cho future refactor). 503 KHÔNG raise (KHÔNG để Starlette HTTPException handler wrap thành NOT_FOUND code) — JWKS-specific CENTRAL_URL_UNAVAILABLE code tường minh.

- **`response_model=None` decorator opt-out** (Rule 1 bug fix): FastAPI cố parse return type union `JSONResponse | RedirectResponse` thành Pydantic field → FastAPIError "Invalid args for response field". Opt-out qua decorator param. Pattern reuse cho mọi endpoint future trả union response type.

- **TestClient `follow_redirects=False`** (Critical pattern): default TestClient follow tự động sẽ resolve URL → mất 307 status code + Location header. Cả unit + integration test phải explicit opt-out follow.

- **Integration test body Pydantic-valid** (Rule 1 bug fix - test): `_dispatch` cũ gửi `json={}` → Pydantic validation 422 trước handler chạy → KHÔNG có branch redirect. Plan 03-04 Task 3 thêm `sso_valid_bodies` dict (login: email/password + refresh: refresh_token) — Pydantic-valid để handler branch hub_con chạy + trả 307.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Validator hub con CENTRAL_URL required phá 21 test cũ Plan 01-02/02-05/03-02**

- **Found during:** Task 1 verify run pytest sau khi thêm validator
- **Issue:** Plan 03-04 Task 1 add `@model_validator _enforce_central_url_for_hub` → 21 test boot Settings với HUB_NAME hub con mà KHÔNG set CENTRAL_URL → all fail ValidationError.
- **Fix:** Update 7 file test cũ auto-set `CENTRAL_URL` cho mọi hub con scenario (helper `_set_env`/`_setup_env`/`_common_hub_env` thêm conditional + 2 file individual monkeypatch.setenv). Semantic test KHÔNG đổi — chỉ thêm env setup matching new validator contract.
- **Files modified:** `tests/unit/test_config_hub_name.py` (2 test explicit setenv), `tests/unit/test_config_hub_name_dynamic.py` (`_set_env` helper), `tests/unit/test_jwks_publish.py` (`_setup_env`), `tests/unit/test_main_factory.py` (`_setup_env`), `tests/unit/test_flow_per_hub_naming.py` (subprocess env), `tests/unit/test_get_current_user_jwks_branch.py` (`_common_hub_env`), `tests/integration/conftest.py` (`hub_app_factory` fixture), `tests/unit/test_config_jwks.py` (2 test cũ Plan 03-02 thêm CENTRAL_URL).
- **Commits:** `86d58c6` (Task 1 batch 6 file), `2372747` (test_get_current_user_jwks_branch follow-up).

**2. [Rule 1 - Bug] FastAPI parse union return type `JSONResponse | RedirectResponse` fail (FastAPIError)**

- **Found during:** Task 2 verify run pytest test_auth_router_hub_redirect.py
- **Issue:** Plan 03-04 Task 2 đổi return type login + refresh từ `JSONResponse` → `JSONResponse | RedirectResponse`. FastAPI default cố parse return type annotation thành Pydantic response_model → `FastAPIError: Invalid args for response field! ... starlette.responses.JSONResponse | starlette.responses.RedirectResponse is a valid Pydantic field type`.
- **Fix:** Thêm `response_model=None` ở 2 decorator (`@router.post("/login", response_model=None)` + `@router.post("/refresh", response_model=None)`). Opt-out generate response model từ type annotation. 10 test PASS sau fix.
- **Files modified:** `api/app/auth/router.py` (2 decorator).
- **Commit:** `e3ea667` (cùng Task 2).

**3. [Rule 1 - Bug] Integration test send `json={}` cho login/refresh → 422 trước handler branch chạy**

- **Found during:** Task 3 verify run pytest test_factor_hub_scoped.py
- **Issue:** `_dispatch` helper gửi `json={}` cho POST endpoint → Pydantic validation reject 422 TRƯỚC handler branch hub_con chạy → KHÔNG có 307. 3 hub fail assertion.
- **Fix:** Thêm `sso_valid_bodies` dict (login: email/password + refresh: refresh_token) trong sub-loop SSO REDIRECT — gửi body Pydantic-valid để handler chạy + trả 307.
- **Files modified:** `tests/integration/test_factor_hub_scoped.py` (test_hub_mounts_hub_scoped Group 2 loop).
- **Commit:** `c862148` (cùng Task 3).

**Total deviations: 3 (1 Rule 3 blocking + 2 Rule 1 bug)** — KHÔNG Rule 4 architectural (scope ràng buộc D-V3-Phase3-G LOCKED).

**Impact on plan:** Plan executed đúng intent (D-V3-Phase3-G consumed + 10 test mới + 276 unit regression PASS); 3 deviation đều downstream của validator/union return type/test body Pydantic — KHÔNG thay đổi architectural decision hoặc API contract.

## Authentication Gates

None - Plan 03-04 ship router refactor (Settings validator + auth_router login + refresh 307 + Phase 2 integration test split + REQUIREMENTS.md note). KHÔNG cần auth qua provider ngoài (OpenAI/Gemini/MCP).

## Issues Encountered

- 21 test cũ Phase 1+2+Plan 03-02 fail sau Task 1 validator add (Rule 3 deviation #1) — auto-fix update 7 file test, regression PASS 276/276.
- FastAPI union return type parse fail (Rule 1 deviation #2) — auto-fix `response_model=None`, 10 unit test PASS sau opt-out.
- Integration test body Pydantic-invalid (Rule 1 deviation #3) — auto-fix sso_valid_bodies dict, 10 integration test PASS.

## Verification Results

### Lint + Type

| Tool | Files | Result |
|------|-------|--------|
| `ruff check` | `app/auth/router.py app/config.py tests/unit/test_auth_router_hub_redirect.py tests/unit/test_config_jwks.py tests/integration/test_factor_hub_scoped.py tests/integration/conftest.py` | All checks passed |
| `mypy --strict` | `app/auth/router.py app/config.py` | Success: no issues |

### Unit Tests (Plan 03-04 new + regression)

| Suite | Tests | PASS | Time |
|-------|-------|------|------|
| `test_auth_router_hub_redirect.py` (Plan 03-04 mới Task 2) | 10 | 10/10 (100%) | bao gồm |
| `test_config_jwks.py` (3 mới Plan 03-04 Task 1 + 17 cũ Plan 03-02 sau Rule 3 fix) | 20 | 20/20 (100%) | bao gồm |
| `test_config_hub_name.py` (Phase 1 regression sau Rule 3 fix) | 11 | 11/11 (100%) | bao gồm |
| `test_config_hub_name_dynamic.py` (Phase 2 FACTOR-04 regression sau Rule 3 fix) | 29 | 29/29 (100%) | bao gồm |
| `test_jwks_publish.py` (Plan 03-01 regression sau Rule 3 fix) | 9 | 9/9 (100%) | bao gồm |
| `test_main_factory.py` (Phase 2 Plan 02-01 regression sau Rule 3 fix) | 9 | 9/9 (100%) | bao gồm |
| `test_flow_per_hub_naming.py` (Phase 1 Plan 01-04 regression sau Rule 3 fix) | 9 | 9/9 (100%) | bao gồm |
| `test_get_current_user_jwks_branch.py` (Plan 03-02/03 regression sau Rule 3 fix) | 8 | 8/8 (100%) | bao gồm |
| `test_jwt_iss_aud_hub_ids.py` (Plan 03-03 regression) | 9 | 9/9 (100%) | bao gồm |
| `test_redis_blacklist_key_schema.py` (Plan 03-03 regression) | 7 | 7/7 (100%) | bao gồm |
| `test_jwks_cache.py` (Plan 03-02 regression) | 9 | 9/9 (100%) | bao gồm |
| **Full unit suite** | **276** | **276/276 (100%)** | **33.35s** |

### Integration Tests (critical+integration marker)

| Suite | Tests | PASS | Time |
|-------|-------|------|------|
| `test_factor_hub_scoped.py` (Phase 2 + Plan 03-04 Task 3 assertion update) | 10 | 10/10 (100%) | bao gồm |
| `test_sso_blacklist_cross_process.py` (Plan 03-03 regression) | 3 | 3/3 (100%) | bao gồm |
| `test_jwks_cache_lifecycle.py` (Plan 03-02 regression) | 3 | 3/3 (100%) | bao gồm |
| **Tổng integration critical+integration marker** | **16** | **16/16 (100%)** | **7.94s** |

### Docker Compose

```bash
cd Hub_All && docker compose config --quiet
# exit=0 — base + override render OK

grep -c CENTRAL_URL Hub_All/docker-compose.yml
# 3 (yte + duoc + hcns)

grep -c CENTRAL_URL Hub_All/docker-compose.override.yml.template
# 1 (FACTOR-04 hub mới inherit)
```

## 307 Redirect Sample (test pattern Plan 03-04 Task 2)

`test_hub_con_login_returns_307_redirect_to_central[yte]` unit sample:

```python
# Setup hub yte env
_setup_env(monkeypatch, "yte")
from app.main import create_app
app = create_app()

# TestClient với follow_redirects=False critical
with TestClient(app, follow_redirects=False) as client:
    resp = client.post(
        "/api/auth/login",
        json={"email": "u@m.vn", "password": "secret"},
    )

# Verify behavior:
# 1. Status 307 Temporary Redirect (RFC 7231 method-preserving)
assert resp.status_code == 307

# 2. Location header trỏ central /api/auth/login (preserve path)
assert resp.headers["location"] == "http://python-api-central:8080/api/auth/login"

# 3. SSO debug headers (observability)
assert resp.headers["x-sso-redirect-reason"] == "hub_con_no_local_login"
assert resp.headers["x-sso-original-hub"] == "yte"
```

Browser thực sẽ:
1. Nhận 307 + Location header → auto-follow.
2. POST `http://python-api-central:8080/api/auth/login` với CÙNG body JSON (preserve method + body RFC 7231).
3. Central handle local AuthService.login → trả JWT.
4. Phase 5 PROXY-02 wire frontend `<form action="https://central/api/auth/login">` để FAILED tránh — Plan 03-04 chỉ ship backend.

## Threat Model Results (6 STRIDE threat từ Plan 03-04)

| Threat ID | Category | Severity | Disposition | Status |
|-----------|----------|----------|-------------|--------|
| **T-03-04-01** | Spoofing (attacker thay Settings.central_url qua env override → redirect 307 trỏ malicious URL → phishing login) | high | mitigate | ✓ MITIGATED — CENTRAL_URL set qua docker-compose env (KHÔNG runtime override). Settings validator Task 1 enforce hub con required → boot fail-fast nếu thiếu. Production deploy Phase 7 sẽ có Secret management. Defense-in-depth Phase 5 PROXY-01 Caddy TLS. |
| **T-03-04-02** | Information Disclosure (X-SSO-Original-Hub header leak hub identity ra browser) | low | accept | ✓ ACCEPTED — hub_name đã expose qua subpath URL Phase 5 (wiki.medinet.vn/yte/api/*). KHÔNG bí mật. Header X-SSO-Original-Hub chỉ debug + observability — Caddy strip nếu cần Phase 5 PROXY-01. |
| **T-03-04-03** | Tampering (Body JSON LoginRequest bị attacker thay qua 307 redirect intercept) | medium | accept | ✓ ACCEPTED — RFC 7231 307 preserve body. Phase 5 Caddy TLS termination chống intercept. v3.0-a intra-network HTTP — inherit threat T-03-01-02 (Plan 03-01). |
| **T-03-04-04** | DoS (Hub con KHÔNG có CENTRAL_URL → mọi login request silent fail) | medium | mitigate | ✓ MITIGATED — Settings validator Task 1 enforce CENTRAL_URL required → boot fail-fast (raise ValidationError). Hub con KHÔNG start được nếu thiếu — KHÔNG có scenario silent failure. Defensive runtime fallback router handler trả 503 envelope nếu central_url None (paranoid). |
| **T-03-04-05** | Repudiation (Logout LOCAL ở hub con nhưng central KHÔNG biết → audit log lost cross-tenant) | low | accept | ✓ ACCEPTED — M2 audit logger ghi event local DB (hub con audit_logs table). Cross-hub audit aggregation defer Phase 6 SETTINGS-04 + Phase 7 MIGRATE. Hub con logout event vẫn ghi local audit (đủ traceability per-hub). |
| **T-03-04-06** | Elevation of Privilege (Hub con redirect login → central → JWT trả về user kèm hub_ids đầy đủ → user post tới hub khác bypass) | medium | mitigate | ✓ MITIGATED — Plan 03-03 SSO-04 E4 reinforced dependency `get_current_user_for_hub_access` reject 403 nếu HUB_NAME not in claims.hub_ids. Hub con isolation Plan 03-03 đã ship — Plan 03-04 chỉ ship redirect mechanism, KHÔNG mở rộng attack surface. |

**Tổng:** 6/6 threat addressed (3 accept + 3 mitigate, KHÔNG transfer/avoid/defer). KHÔNG ship threat mới phát sinh.

## Threat Flags

(scan files modified — không có surface mới ngoài threat_model đã liệt kê)

None - new surface area khớp 100% threat_model Plan 03-04.

## Self-Check

### Created Files Exist

| File | Status |
|------|--------|
| `Hub_All/api/tests/unit/test_auth_router_hub_redirect.py` | FOUND |
| `Hub_All/.planning/phases/03-auth-sso-hub-ids-jwt/03-04-SUMMARY.md` | FOUND (file này) |

### Modified Files Verified (grep evidence)

| File | Verify | Status |
|------|--------|--------|
| `api/app/auth/router.py` | grep `RedirectResponse` ≥ 2 | OK |
| `api/app/auth/router.py` | grep `status_code=307` ≥ 1 | OK |
| `api/app/auth/router.py` | grep `settings.hub_name != "central"` ≥ 2 | OK |
| `api/app/auth/router.py` | grep `_sso_redirect` ≥ 3 (1 def + 2 call) | OK |
| `api/app/auth/router.py` | grep `X-SSO-Redirect-Reason\|X-SSO-Original-Hub` ≥ 2 | OK |
| `api/app/auth/router.py` | grep `response_model=None` ≥ 2 | OK |
| `api/app/config.py` | grep `central_url` ≥ 5 (1 field + 4 validator/comment reference) | OK |
| `api/app/config.py` | grep `_enforce_central_url_for_hub` ≥ 1 | OK |
| `docker-compose.yml` | grep `CENTRAL_URL` = 3 (yte + duoc + hcns) | OK |
| `docker-compose.override.yml.template` | grep `CENTRAL_URL` = 1 | OK |
| `tests/integration/test_factor_hub_scoped.py` | grep `HUB_SCOPED_SSO_REDIRECT_ENDPOINTS\|HUB_SCOPED_LOCAL_ENDPOINTS` ≥ 4 | OK |
| `tests/integration/test_factor_hub_scoped.py` | grep `follow_redirects=False` ≥ 1 | OK |
| `Hub_All/.planning/REQUIREMENTS.md` | grep `Plan 03-04` ≥ 4 | OK |
| `Hub_All/.planning/REQUIREMENTS.md` | grep `307 Location: central` ≥ 2 | OK |
| `Hub_All/.planning/REQUIREMENTS.md` | grep `10 endpoint handle LOCAL\|2 endpoint SSO REDIRECT` ≥ 2 | OK |

### Commits Exist (git log --oneline)

| Commit | Verify | Status |
|--------|--------|--------|
| `86d58c6` feat(03-04) Task 1 | `git log \| grep 86d58c6` | FOUND |
| `e3ea667` feat(03-04) Task 2 | `git log \| grep e3ea667` | FOUND |
| `c862148` test(03-04) Task 3 | `git log \| grep c862148` | FOUND |
| `48549ee` docs(03-04) Task 4 | `git log \| grep 48549ee` | FOUND |
| `2372747` test(03-04) Rule 3 follow-up | `git log \| grep 2372747` | FOUND |

## Self-Check: PASSED

## Next Phase Readiness

### Plan 03-05 (Wave 5 closeout — UNBLOCKED) — Phase 3 closeout smoke + docs

- ✅ All 4 plan đóng (03-01 publish + 03-02 cache consume + 03-03 claim refactor + 03-04 router redirect) — Wave 5 closeout sẵn sàng.
- 📋 Plan 03-05 ship:
  - Smoke 2 service compose runtime (central + yte) real: boot central + yte → fetch JWKS thật → JWT issue có aud + hub_ids + kid → verify cross-process PASS. Verify hub yte login → 307 → central handle → JWT trả về. Verify Redis blacklist `auth:blacklist:` propagate < 1s.
  - README backward incompat TRIPLE banner — communicate operator:
    - kid header missing reject (Plan 03-02 hub con only).
    - aud claim missing + hub_ids missing reject (Plan 03-03 central + hub con).
    - login/refresh redirect form action (Plan 03-04 hub con only — frontend M2 hardcode same-origin sẽ FAIL ở hub con cho tới Phase 5 PROXY-02).
    - Combine: M2 cũ JWT post-Plan 03-03 deploy KHÔNG dùng được, user re-login ~15-30s downtime acceptable. Frontend hub con login form FAIL cho tới Phase 5 — accept dev mode trong v3.0-a.
  - CLAUDE.md section 6 update Phase 3 progress (DONE 5/5 plan + SSO-01..04 đóng + carry forward pattern cho v3.0-a EXIT GATE).

### v3.0-a EXIT GATE (giữa Phase 3-4)

- 🚦 Demo 1 hub con (yte) + central + JWT SSO + golden path PASS → user accept là điều kiện tiếp tục v3.0-b (Phase 4-7).
- Plan 03-04 đóng góp 4/5 plan Phase 3 (Plan 03-01 + 03-02 + 03-03 + 03-04 = 80% Phase 3 close); 1 plan còn lại (03-05 closeout) sẽ unblock Wave 5.
- Golden path post-Plan 03-04:
  1. User POST `wiki.medinet.vn/yte/api/auth/login` (Phase 5 Caddy strip /yte → hub-yte:8180/api/auth/login).
  2. Hub yte trả 307 Location: central (Plan 03-04 SSO-02 D-V3-Phase3-G).
  3. Browser auto-follow → POST `https://central/api/auth/login` với body preserved.
  4. Central AuthService.login → JWT issue có aud=["medinet-wiki"] + hub_ids=["yte"] + kid header (Plan 03-02/03 ship).
  5. Browser redirect back `wiki.medinet.vn/yte` với JWT.
  6. Subsequent request hub yte → verify JWT qua JWKSCache.get_public_key(kid) → verify_token_with_key → check audience + hub_ids — Layer 3 E4 reinforced (Plan 03-03 SSO-04).
  7. Plan 03-05 smoke verify golden path runtime.

---

*Phase: 03-auth-sso-hub-ids-jwt*
*Plan: 04 (SSO-02 hub con router redirect — Wave 4 BLOCKED 03-03)*
*Completed: 2026-05-22*
*Test result: 10/10 unit mới PASS + 276/276 unit regression PASS + 16/16 integration critical+integration regression PASS — KHÔNG break*
