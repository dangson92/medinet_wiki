---
phase: 03-auth-sso-hub-ids-jwt
plan: 02
subsystem: auth
tags:
  - jwks-cache
  - in-process-lru
  - asyncio-refresh
  - lifespan-blocking
  - dependency-branch
  - fail-loud-boot
  - fail-quiet-runtime
  - 24h-hard-limit
  - kid-header
  - verify-token-with-key
  - d-v3-phase3-b
  - d-v3-phase3-d
  - r-v3-5
  - sso-01

# Dependency graph
requires:
  - phase: 03-auth-sso-hub-ids-jwt
    provides: "Plan 03-01 ship publish_jwks() + JWK/JWKSet TypedDict + Settings.central_jwks_url field default None (api/app/auth/jwks.py + main.py route central) — Plan 03-02 EXTEND cùng module thêm JWKSCache + consume CENTRAL_JWKS_URL"
  - phase: 02-hub-con-codebase-factor
    provides: "create_app() factory conditional mount + Starlette HTTPException 404 envelope (Plan 02-01 + 02-03) — Plan 03-02 hub con lifespan branch dùng cùng factory pattern"
  - phase: 01-multi-db-topology
    provides: "Settings.hub_name + _enforce_hub_dsn_match validator (Plan 01-02) — Plan 03-02 thêm 1 model_validator nữa enforce hub con CENTRAL_JWKS_URL required"
provides:
  - "JWKSCache class in-process LRU + asyncio refresh task + 24h hard limit (api/app/auth/jwks.py extend) — hub con consume layer"
  - "JWTManager.verify_token_with_key wrapper cho hub con verify path qua external public key (RSAPublicKey from JWKSCache)"
  - "JWT header kid auto-add ở issue_token_pair (deterministic SHA-256 PEM — match Plan 03-01 _derive_kid)"
  - "get_current_user dependency branch: central=verify_token (local pem) / hub con=JWKSCache.get_public_key(kid) → verify_token_with_key"
  - "Settings 2 field jwks_refresh_interval + jwks_max_stale_seconds (D-V3-Phase3-B defaults 3600/86400) + validator hub con required CENTRAL_JWKS_URL"
  - "Lifespan hub con: blocking fetch_initial (boot fail-loud D-V3-Phase3-B) + spawn refresh task + graceful shutdown stop_refresh_task"
  - "Escape hatch JWKS_SKIP_FETCH=1 env var (test mode bypass blocking fetch — pattern song song COCOINDEX_SKIP_SETUP)"
affects:
  - "03-03 (Wave 3) JWT iss/aud/hub_ids claim refactor — reuse Plan 03-02 kid header pattern + verify_token_with_key wrapper"
  - "03-04 hub con auth router redirect (login/refresh 307 central) — independent layer, no direct coupling"
  - "03-05 closeout smoke compose 2 service runtime (central + yte) — verify Plan 03-02 lifespan blocking thật + JWT verify hub con E2E"
  - "07 MIGRATE-04 (MCP service) — re-point sang central JWKS endpoint dùng cùng JWKSCache pattern"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "In-process LRU cache (asyncio + httpx) thay Redis cho payload < 2KB — zero latency hot path verify JWT (D-V3-Phase3-D LOCKED)"
    - "Asyncio background task refresh TTL 1h fail-quiet + 24h hard limit fail-loud delayed (R-V3-5 mitigation)"
    - "Lifespan branch hub_name != central: blocking startup fetch (5s timeout) → boot fail-loud nếu central down KHI boot (D-V3-Phase3-B)"
    - "Test-mode escape hatch env var (JWKS_SKIP_FETCH=1) song song COCOINDEX_SKIP_SETUP=1 — production KHÔNG bao giờ set, integration test bypass blocking fetch khi fake URL"
    - "Variable shadowing fix mypy: rename local shutdown var (_shutdown_jwks_cache) thay vì tái dùng tên jwks_cache khác type"
    - "C901 noqa cho get_current_user complexity 13 — branch verify path hub con thêm 5 reject path mới, acceptable vì logic linear không nest"

key-files:
  created:
    - "Hub_All/api/tests/unit/test_config_jwks.py — 11 unit test Settings validator + 2 field default/override (108 LOC)"
    - "Hub_All/api/tests/unit/test_jwks_cache.py — 9 unit test JWKSCache lifecycle (218 LOC) — TDD RED→GREEN gate"
    - "Hub_All/api/tests/unit/test_get_current_user_jwks_branch.py — 4 unit test dependency branch (195 LOC)"
    - "Hub_All/api/tests/integration/test_jwks_cache_lifecycle.py — 3 integration test rotate keypair + lifecycle (169 LOC)"
    - "Hub_All/.planning/phases/03-auth-sso-hub-ids-jwt/03-02-SUMMARY.md (file này)"
  modified:
    - "Hub_All/api/app/auth/jwks.py +238 LOC (JWKSCache class + JWKSStaleError + JWKSKidNotFoundError + jwk_to_public_key + _base64url_to_int helpers — extend Plan 03-01 publish layer) — 137 → 375 LOC"
    - "Hub_All/api/app/auth/jwt.py +63 LOC (verify_token_with_key wrapper + _kid derive ở __init__ + headers={kid} ở issue_token_pair access + refresh)"
    - "Hub_All/api/app/auth/dependencies.py +103 LOC (get_current_user signature thêm request: Request + branch hub_name central/hub con verify path + 4 reject path mới HTTPException JWKS_*) — 318 → 417 LOC"
    - "Hub_All/api/app/main.py +73 LOC (lifespan hub con branch + JWKS_SKIP_FETCH escape hatch + shutdown stop_refresh_task)"
    - "Hub_All/api/app/config.py +30 LOC (2 field jwks_* + @model_validator _enforce_central_jwks_url_for_hub) — 318 → 348 LOC"
    - "Hub_All/api/tests/unit/test_config_hub_name.py +8 LOC (Rule 3 regression update — 2 test set CENTRAL_JWKS_URL)"
    - "Hub_All/api/tests/unit/test_config_hub_name_dynamic.py +9 LOC (Rule 3 regression update — _set_env helper auto-set cho hub con)"
    - "Hub_All/api/tests/unit/test_jwks_publish.py +10 LOC (Rule 3 regression — _setup_env hub con CENTRAL_JWKS_URL + test default_none semantic update)"
    - "Hub_All/api/tests/unit/test_main_factory.py +6 LOC (Rule 3 regression — _setup_env hub con CENTRAL_JWKS_URL)"
    - "Hub_All/api/tests/unit/test_flow_per_hub_naming.py +2 LOC (Rule 3 regression — subprocess env yte add CENTRAL_JWKS_URL)"
    - "Hub_All/api/tests/integration/conftest.py +11 LOC (hub_app_factory fixture set CENTRAL_JWKS_URL + JWKS_SKIP_FETCH cho hub con — Phase 2 integration regression)"

key-decisions:
  - "D-V3-Phase3-B (LOCKED Plan 03-01 / consume Plan 03-02): Boot fail-loud (timeout 5s blocking startup) + runtime fail-quiet (refresh task log warning + giữ cached) + 24h hard limit (cached > limit → 503 JWKS_STALE envelope mọi JWT verify)"
  - "D-V3-Phase3-D (LOCKED Plan 03-01 / consume Plan 03-02): In-process LRU cache (dict keyed on kid + asyncio refresh task). KHÔNG Redis cache JWKS (overhead network call 0.5-1ms × hot path verify KHÔNG đáng cho payload < 2KB)"
  - "Test-mode escape hatch JWKS_SKIP_FETCH=1 (Claude's Discretion Rule 3 deviation): pattern song song COCOINDEX_SKIP_SETUP=1 DEF-05-01 — integration test factor_hub_scoped boot lifespan với fake CENTRAL_JWKS_URL KHÔNG ConnectError. Production KHÔNG bao giờ set → fail-loud D-V3-Phase3-B giữ nguyên"
  - "JWT header kid auto-add ở issue_token_pair (Plan 03-02 forward-compat) — M2 backward incompat acceptable (~15-30s downtime sau Plan 03-02 deploy — JWT cũ KHÔNG kid → hub con reject 401 → user re-login). Communicate operator README banner Plan 03-05"
  - "C901 noqa cho get_current_user — function complexity 13 > 10 chấp nhận vì branch hub con thêm 5 reject path tuyến tính (KHÔNG nest sâu); refactor split thành sub-functions sẽ làm logic khó trace hơn"
  - "Plan 03-02 KHÔNG đụng service.py (Plan 03-03 sẽ rename Redis blacklist key `blacklist:` → `auth:blacklist:`) + KHÔNG đụng router.py (Plan 03-04 sẽ thêm 307 redirect login/refresh hub con → central)"

patterns-established:
  - "Pattern 1 (Plan 03-02 - JWKSCache lifecycle 4 method): __init__ → fetch_initial (blocking raise) → start_refresh_task (asyncio.create_task) → get_public_key (sync hot path raise nếu stale) → stop_refresh_task (cancel graceful). Plan 03-03/03-04 KHÔNG cần extend; Plan 07 MIGRATE-04 MCP service re-point reuse cùng class"
  - "Pattern 2 (Plan 03-02 - dependency branch theo hub_name): if settings.hub_name == 'central' → M2 path (local pem); else → JWKSCache.get_public_key(kid) + verify_token_with_key. Pattern này có thể tổng quát hoá Plan 03-03 hub_ids claim build (central có user_hubs JOIN; hub con verify từ JWT claim only)"
  - "Pattern 3 (Plan 03-02 - test-mode escape hatch env var): COCOINDEX_SKIP_SETUP=1 (DEF-05-01) + JWKS_SKIP_FETCH=1 (Plan 03-02) — production KHÔNG set, test bypass blocking external dependency. Áp dụng được cho Plan 04 SYNC-* nếu cần bypass outbox poll, Plan 06 SETTINGS-* nếu cần bypass HTTP pull"
  - "Pattern 4 (Plan 03-02 - regression test update CENTRAL_JWKS_URL hub con): 5 file test cũ Plan 01-02/02-01/02-05 phải auto-set CENTRAL_JWKS_URL khi monkeypatch HUB_NAME=hub con. Pattern cho mọi Plan tương lai (03-03/03-04/04/05/06/07) — thêm `_common_env` helper cho test boot Settings hub con"

requirements-completed:
  - SSO-01

# Metrics
duration: 90min
completed: 2026-05-22
---

# Phase 3 Plan 02: JWKSCache Hub Con Consume Layer Summary

**Hub con cache JWKS in-process LRU + asyncio refresh TTL 1h + 24h hard limit (R-V3-5 fail-loud delayed) + lifespan blocking startup fetch (D-V3-Phase3-B boot fail-loud) + get_current_user dependency branch verify JWT qua JWKSCache.get_public_key(kid) thay local pem cho hub con — Settings 2 field config-driven (jwks_refresh_interval=3600, jwks_max_stale_seconds=86400) + validator CENTRAL_JWKS_URL required hub con + JWTManager.verify_token_with_key wrapper + JWT header kid auto-add ở issue_token_pair (deterministic SHA-256 PEM match Plan 03-01) — Plan 03-02 ship SSO-01 part 2 hoàn chỉnh hub con verify path D-V3-Phase3-D.**

## Performance

- **Duration:** ~90 phút (5 task tuần tự: Task 1 Settings 8min + Task 2 TDD RED+GREEN JWKSCache 20min + Task 3 lifespan+JWT wrapper 15min + Task 4 dependency branch 20min + Task 5 integration test + escape hatch fix 27min)
- **Started:** 2026-05-22T16:30:00Z (approximate)
- **Completed:** 2026-05-22T18:00:00Z (approximate)
- **Tasks:** 5/5 (1 Settings + 1 TDD impl + 1 lifespan+jwt + 1 dependency + 1 integration)
- **Files modified:** 14 (5 mới + 9 sửa — bao gồm 5 file test cũ Plan 01-02/02-01/02-05 update do Rule 3 deviation regression)

## Accomplishments

- **`JWKSCache` class** trong `api/app/auth/jwks.py` extend Plan 03-01 publish layer — 4 method core (fetch_initial blocking + refresh fail-quiet + get_public_key hot path + start/stop_refresh_task asyncio task lifecycle) + 2 exception (JWKSStaleError 503 / JWKSKidNotFoundError 401) + 2 helper (jwk_to_public_key RFC 7517 reverse + _base64url_to_int inverse RFC 7518)
- **`JWTManager.verify_token_with_key` wrapper** trong `api/app/auth/jwt.py` — hub con verify JWT bằng external public key (RSAPublicKey từ JWKSCache) thay self._public_pem local. Logic decode + JWTClaims validate giống verify_token, chỉ khác key source. + `_kid` derive deterministic SHA-256 ở `__init__` + `headers={kid}` ở `issue_token_pair` cả access + refresh token
- **Settings 2 field config-driven** (`api/app/config.py`): `jwks_refresh_interval=3600` (1h match Plan 03-01 Cache-Control max-age) + `jwks_max_stale_seconds=86400` (24h hard limit R-V3-5 fail-loud delayed). 1 `@model_validator(mode="after")` `_enforce_central_jwks_url_for_hub` raise ValidationError nếu hub_name != "central" + central_jwks_url None (fail-fast boot — T-03-02-01 mitigation)
- **Lifespan branch hub con** trong `api/app/main.py`: instantiate `JWKSCache(central_jwks_url, refresh_interval, max_stale_seconds)` → `fetch_initial()` blocking 5s timeout → exception re-raise (boot fail-loud D-V3-Phase3-B → uvicorn exit 1). Spawn refresh task + wire `app.state.jwks_cache`. Shutdown branch graceful `stop_refresh_task()` TRƯỚC watchdog/sqlalchemy teardown. Escape hatch `JWKS_SKIP_FETCH=1` bypass blocking fetch cho integration test mode (pattern DEF-05-01)
- **`get_current_user` dependency branch** trong `api/app/auth/dependencies.py`: signature thêm `request: Request` (cần app.state.jwks_cache). Central → `jwt_mgr.verify_token` (M2 carry forward); hub con → `pyjwt.get_unverified_header` kid extract → `jwks_cache.get_public_key(kid)` → `jwt_mgr.verify_token_with_key`. 4 HTTPException mới: 503 JWKS_CACHE_UNAVAILABLE (boot fail) + 503 JWKS_STALE (cache > 24h) + 2x 401 INVALID_TOKEN (thiếu kid header T-03-02-06 / kid mismatch JWKS)
- **27 test mới PASS**: 11 config validator + 9 cache lifecycle TDD + 4 dependency branch + 3 integration (central JWKS endpoint serve + rotate keypair detect kid mismatch + background task lifecycle)
- **Phase 1+2 regression KHÔNG break**: 237/237 unit PASS + 10/10 Phase 2 integration test_factor_hub_scoped PASS sau Rule 3 deviation auto-fix (5 file test cũ update set CENTRAL_JWKS_URL cho hub con + JWKS_SKIP_FETCH escape hatch cho integration)

## Task Commits

| Task | Commit | Type | Description |
|------|--------|------|-------------|
| Task 1 | `abe2e37` | feat | Settings 2 field jwks_* + validator CENTRAL_JWKS_URL hub con required + 11 unit test + Rule 3 regression 2 file test cũ |
| Task 2 RED | `f705569` | test | 9 failing test JWKSCache lifecycle ImportError verify trước impl |
| Task 2 GREEN | `895551b` | feat | JWKSCache class extend jwks.py + 2 exception + 2 helper — 9/9 cache test PASS + 9/9 publish regression PASS |
| Task 3 | `c3388aa` | feat | Lifespan hub con blocking fetch + JWTManager.verify_token_with_key wrapper + JWT header kid auto-add + Rule 3 regression test_main_factory.py |
| Task 4 | `cfd7412` | feat | get_current_user branch verify JWT qua JWKSCache cho hub con + 4 unit test + Rule 3 regression test_flow_per_hub_naming |
| Task 5 | `239d0cb` | test | 3 integration test rotate keypair lifecycle + JWKS_SKIP_FETCH escape hatch (Rule 3 fix integration conftest) |
| SUMMARY | (pending) | docs | This file |

## TDD Gate Compliance (Task 2)

| Gate | Commit | Type | Status |
|------|--------|------|--------|
| RED  | `f705569` | test | ImportError verify trước impl (cannot import JWKSCache) |
| GREEN | `895551b` | feat | 9/9 cache test PASS sau impl extend jwks.py |
| REFACTOR | (skipped) | — | KHÔNG cần — code clean ngay sau GREEN |

## Files Created/Modified

### Created (5)

- **`api/tests/unit/test_config_jwks.py`** (108 LOC) — 11 test: defaults 3600/86400 + central None OK + hub con required (parametrize 4 hub × ValidationError) + override env JWKS_REFRESH_INTERVAL/JWKS_MAX_STALE_SECONDS
- **`api/tests/unit/test_jwks_cache.py`** (218 LOC) — 9 test TDD: fetch_initial happy/timeout/500/invalid-shape + get_public_key kid not found + 24h hard limit stale + refresh fail-quiet + jwk_to_public_key roundtrip qua JWT sign/verify + base64url_to_int inverse property
- **`api/tests/unit/test_get_current_user_jwks_branch.py`** (195 LOC) — 4 test: central uses verify_token + hub con jwks_cache None 503 + hub con JWT thiếu kid 401 + hub con JWKSStaleError 503
- **`api/tests/integration/test_jwks_cache_lifecycle.py`** (169 LOC) — 3 test marker `critical and integration`: central JWKS endpoint serve real keypair shape match + rotate keypair detect kid mismatch (RSA gen tmp keypair B + simulate refresh) + background refresh task lifecycle
- **`.planning/phases/03-auth-sso-hub-ids-jwt/03-02-SUMMARY.md`** (file này)

### Modified (9)

- **`api/app/auth/jwks.py`** (+238 LOC, 137 → 375): JWKSCache class lifecycle 4 method + 2 exception JWKSStaleError/JWKSKidNotFoundError + jwk_to_public_key helper (RFC 7517 reverse) + _base64url_to_int helper (RFC 7518 inverse) + module docstring update Plan 03-02 scope + `__all__` export 6 symbol mới
- **`api/app/auth/jwt.py`** (+63 LOC): `verify_token_with_key(token, public_key, expected_type)` wrapper (decode bằng RSAPublicKey thay self._public_pem) + `_kid` derive ở `__init__` (SHA-256 8-byte public.pem) + `headers={"kid": self._kid}` ở `pyjwt.encode` cả access + refresh trong `issue_token_pair` + import `TYPE_CHECKING RSAPublicKey`
- **`api/app/auth/dependencies.py`** (+103 LOC, 318 → 417): `get_current_user` signature thêm `request: Request` đầu tiên + branch verify path theo `settings.hub_name`; central giữ `jwt_mgr.verify_token` M2 path; hub con `pyjwt.get_unverified_header → kid → jwks_cache.get_public_key(kid) → jwt_mgr.verify_token_with_key`; 4 HTTPException mới (JWKS_CACHE_UNAVAILABLE 503, JWKS_STALE 503, 2x INVALID_TOKEN 401 cho thiếu kid + kid mismatch). `get_api_key_or_jwt` update truyền `request=request` cho fallback call. `# noqa: C901` cho function complexity 13
- **`api/app/main.py`** (+73 LOC): Lifespan branch sau JWTManager init (step 4) — `if settings.hub_name != "central"` instantiate JWKSCache + blocking fetch_initial (re-raise on fail → boot exit 1) + start_refresh_task + wire app.state.jwks_cache. Escape hatch `if os.environ.get("JWKS_SKIP_FETCH") == "1"` bypass blocking fetch (test mode song song COCOINDEX_SKIP_SETUP). Shutdown branch graceful stop_refresh_task (rename local var `_shutdown_jwks_cache` tránh mypy union conflict)
- **`api/app/config.py`** (+30 LOC, 318 → 348): 2 field `jwks_refresh_interval: int = 3600` + `jwks_max_stale_seconds: int = 86400` sau central_jwks_url + 1 `@model_validator(mode="after")` `_enforce_central_jwks_url_for_hub` raise nếu hub_name != "central" + central_jwks_url falsy
- **`api/tests/unit/test_config_hub_name.py`** (+8 LOC Rule 3): 2 test (test_yte_matches_yte_dsn_ok + test_dsn_with_query_string_validates) thêm monkeypatch.setenv CENTRAL_JWKS_URL
- **`api/tests/unit/test_config_hub_name_dynamic.py`** (+9 LOC Rule 3): `_set_env` helper auto-set CENTRAL_JWKS_URL khi hub_name != "central"
- **`api/tests/unit/test_jwks_publish.py`** (+10 LOC Rule 3): `_setup_env` auto-set CENTRAL_JWKS_URL hub con + test_settings_central_jwks_url_default_none semantic update (hub yte không còn default None)
- **`api/tests/unit/test_main_factory.py`** (+6 LOC Rule 3): `_setup_env` auto-set CENTRAL_JWKS_URL hub con
- **`api/tests/unit/test_flow_per_hub_naming.py`** (+2 LOC Rule 3): subprocess env yte add CENTRAL_JWKS_URL
- **`api/tests/integration/conftest.py`** (+11 LOC Rule 3): `hub_app_factory` fixture set CENTRAL_JWKS_URL + JWKS_SKIP_FETCH=1 cho hub con

## Decisions Made

- **D-V3-Phase3-B consumed** (LOCKED 03-CONTEXT.md): Boot fail-loud + runtime fail-quiet + 24h hard limit — JWKSCache implement đúng spec qua try/except split (fetch_initial raise vs refresh catch + log warning) + is_stale() guard ở get_public_key hot path
- **D-V3-Phase3-D consumed** (LOCKED 03-CONTEXT.md): In-process LRU storage (dict keyed on kid + asyncio task) — KHÔNG Redis (payload < 2KB + zero latency hot path). Restart hub con = re-fetch (KHÔNG persist disk LMDB/file)
- **JWT header kid auto-add ở issue_token_pair** (Plan 03-02 forward-compat): pattern Plan 03-01 `_derive_kid` reuse — `self._kid` derive 1 lần ở `__init__` (KHÔNG re-compute mỗi sign), set qua `headers={"kid": self._kid}` ở `pyjwt.encode`. Phase 7 MCP service tái dùng cùng pattern
- **JWKS_SKIP_FETCH=1 escape hatch** (Claude's Discretion Rule 3 deviation): pattern song song COCOINDEX_SKIP_SETUP=1 DEF-05-01 — integration test factor_hub_scoped (Phase 2 Plan 02-03) boot lifespan với fake CENTRAL_JWKS_URL → fetch_initial blocking fail ConnectError. Cần escape hatch tránh test cascade fail. Production KHÔNG bao giờ set flag này — fail-loud D-V3-Phase3-B giữ nguyên
- **C901 complexity 13 noqa** cho `get_current_user`: branch hub con thêm 5 reject path tuyến tính (kid extract → public_key lookup → verify) — refactor split sub-function sẽ làm logic khó trace. Acceptable vì KHÔNG nest sâu, control flow rõ ràng
- **Rename local var `_shutdown_jwks_cache`** tránh mypy union conflict: biến `jwks_cache` ở init branch type `JWKSCache`, tái dùng tên ở shutdown branch với `getattr(..., None)` type `Any | None` → mypy strict reject (Plan đã document)
- **KHÔNG đụng `service.py` (blacklist key rename)**: defer Plan 03-03 — coupled write `auth:blacklist:` rename + hub_ids claim build trong cùng commit set Wave 3
- **KHÔNG đụng `router.py` (hub con 307 redirect login/refresh)**: defer Plan 03-04 — independent layer KHÔNG block Plan 03-02 verify path

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Validator hub con CENTRAL_JWKS_URL required phá 22 test cũ Plan 01-02/02-01/02-05**

- **Found during:** Task 1 verify run pytest sau khi thêm validator
- **Issue:** Plan 03-02 Task 1 add `@model_validator _enforce_central_jwks_url_for_hub` → 11 test test_config_hub_name*.py + 2 test test_jwks_publish.py + 7 test test_main_factory.py + 1 test test_flow_per_hub_naming.py boot `Settings(hub_name="<hub con>", ...)` mà KHÔNG set CENTRAL_JWKS_URL → all fail ValidationError
- **Fix:** Update 5 file test cũ auto-set `CENTRAL_JWKS_URL` cho mọi hub con scenario (helper `_set_env`/`_setup_env` thêm conditional, hoặc test individual monkeypatch.setenv). Semantic test KHÔNG đổi — chỉ thêm env setup matching new validator contract
- **Files modified:** `tests/unit/test_config_hub_name.py`, `tests/unit/test_config_hub_name_dynamic.py`, `tests/unit/test_jwks_publish.py`, `tests/unit/test_main_factory.py`, `tests/unit/test_flow_per_hub_naming.py`
- **Commits:** `abe2e37` (test_config_hub_name + dynamic), `895551b` (test_jwks_publish), `c3388aa` (test_main_factory), `cfd7412` (test_flow_per_hub_naming)

**2. [Rule 3 - Blocking] Integration test factor_hub_scoped boot lifespan hub con với fake CENTRAL_JWKS_URL → ConnectError**

- **Found during:** Task 5 verify run integration test
- **Issue:** Plan 03-02 Task 3 thêm lifespan blocking `await jwks_cache.fetch_initial()` cho hub con → integration test `test_factor_hub_scoped` boot via `with TestClient(app)` trigger lifespan → fake URL `http://python-api-central:8080` resolve fail → getaddrinfo error → 7 integration test fail
- **Fix:** Thêm escape hatch env var `JWKS_SKIP_FETCH=1` trong main.py lifespan branch (pattern song song `COCOINDEX_SKIP_SETUP=1` DEF-05-01). Production KHÔNG bao giờ set → fail-loud D-V3-Phase3-B giữ nguyên. Integration test fixture `hub_app_factory` set flag + CENTRAL_JWKS_URL fake
- **Files modified:** `app/main.py` (+8 LOC escape hatch logic), `tests/integration/conftest.py` (+1 LOC `monkeypatch.setenv("JWKS_SKIP_FETCH", "1")`)
- **Commit:** `239d0cb`

**3. [Rule 1 - Bug] mypy union conflict shutdown branch biến `jwks_cache` re-shadow**

- **Found during:** Task 3 mypy app/main.py
- **Issue:** Biến local `jwks_cache` ở init branch type `JWKSCache` (line 199), tái dùng tên ở shutdown branch `getattr(app.state, "jwks_cache", None)` type `Any | None` (line 299) → mypy strict reject "Incompatible types in assignment"
- **Fix:** Rename local var shutdown `_shutdown_jwks_cache` tránh shadowing
- **Files modified:** `app/main.py` (line 299-305)
- **Commit:** `c3388aa` (cùng Task 3)

**4. [Rule 1 - Lint] ruff C901 complexity 13 > 10 cho `get_current_user`**

- **Found during:** Task 4 ruff check
- **Issue:** `get_current_user` thêm branch hub con với 5 reject path mới → cyclomatic complexity 13 vượt limit 10 → ruff C901 reject
- **Fix:** Thêm `# noqa: C901` với comment giải thích (branch verify linear không nest, refactor sub-function sẽ làm logic khó trace)
- **Files modified:** `app/auth/dependencies.py` (line 85)
- **Commit:** `cfd7412` (cùng Task 4)

**Total deviations: 4 (3 Rule 3 + 1 Rule 1)** — KHÔNG Rule 4 architectural (toàn bộ scope ràng buộc D-V3-Phase3-B/D LOCKED).

**Impact on plan:** Plan executed đúng intent (D-V3-Phase3-B/D consumed + 27 test mới + 237 unit regression PASS); 4 deviation đều downstream của validator/lifespan thay đổi behavior + ruff lint convention — KHÔNG thay đổi architectural decision hoặc API contract.

## Authentication Gates

None - Plan 03-02 ship verify path mới cho hub con (Settings validator + JWKSCache lifecycle + dependency branch). KHÔNG cần auth qua provider ngoài (OpenAI/Gemini/MCP). Integration test dùng `api/keys/{private,public}.pem` M2 baseline đã ship + tmp_path RSA generate cho rotate scenario.

## Issues Encountered

- 22 test cũ Phase 1+2 fail sau Task 1 validator add (Rule 3 deviation #1) — auto-fix update _set_env helper cho 5 file test, regression PASS 237/237.
- 7 integration test fail sau Task 3 lifespan blocking fetch add (Rule 3 deviation #2) — auto-fix escape hatch JWKS_SKIP_FETCH=1 + conftest update, regression PASS 10/10.
- mypy union conflict variable shadowing (Rule 1 deviation #3) — auto-fix rename local var.
- ruff C901 complexity (Rule 1 deviation #4) — auto-fix `# noqa: C901` với comment justify.

## Verification Results

### Lint + Type

| Tool | Files | Result |
|------|-------|--------|
| `ruff check` | `app/auth/jwks.py app/auth/jwt.py app/auth/dependencies.py app/main.py app/config.py tests/unit/test_jwks_cache.py tests/unit/test_config_jwks.py tests/unit/test_get_current_user_jwks_branch.py tests/integration/test_jwks_cache_lifecycle.py` | All checks passed |
| `mypy --strict` | `app/auth/jwks.py app/auth/jwt.py app/auth/dependencies.py app/main.py app/config.py` | Success: no issues |
| `mypy --strict` | `tests/integration/test_jwks_cache_lifecycle.py` | Success: no issues |

### Unit Tests (Plan 03-02 new + regression)

| Suite | Tests | PASS | Time |
|-------|-------|------|------|
| `test_config_jwks.py` (Plan 03-02 mới Task 1) | 11 | 11/11 (100%) | bao gồm |
| `test_jwks_cache.py` (Plan 03-02 mới Task 2) | 9 | 9/9 (100%) | bao gồm |
| `test_get_current_user_jwks_branch.py` (Plan 03-02 mới Task 4) | 4 | 4/4 (100%) | bao gồm |
| `test_jwks_publish.py` (Plan 03-01 regression sau Rule 3 fix) | 9 | 9/9 (100%) | bao gồm |
| `test_config_hub_name.py` (Phase 1 regression sau Rule 3 fix) | 11 | 11/11 (100%) | bao gồm |
| `test_config_hub_name_dynamic.py` (Phase 2 FACTOR-04 regression sau Rule 3 fix) | 29 | 29/29 (100%) | bao gồm |
| `test_main_factory.py` (Phase 2 Plan 02-01 regression sau Rule 3 fix) | 9 | 9/9 (100%) | bao gồm |
| `test_jwt.py` (M2 baseline regression — JWT kid header KHÔNG break) | 8 | 8/8 (100%) | bao gồm |
| **Full unit suite** | **237** | **237/237 (100%)** | **28.04s** |

### Integration Tests

| Suite | Tests | PASS | Time |
|-------|-------|------|------|
| `test_jwks_cache_lifecycle.py` (Plan 03-02 mới Task 5) | 3 | 3/3 (100%) | bao gồm |
| `test_factor_hub_scoped.py` (Phase 2 Plan 02-03 regression sau Rule 3 fix) | 10 | 10/10 (100%) | bao gồm |
| **Tổng integration Plan 03-02 critical+integration marker** | **13** | **13/13 (100%)** | **~7s** |

### Docker Compose

```bash
cd Hub_All && docker compose config --quiet
# exit=0 — base + override render OK (Plan 03-02 KHÔNG đụng compose)
```

## JWKSCache Lifecycle Sample (test flow integration)

`test_jwks_cache_rotate_keypair_detects_new_kid` (Plan 03-02 Task 5 integration):

```python
# Setup
jwks_a = publish_jwks(api/keys/public.pem)   # M2 keypair kid="hDRHjB_zZNY" (4096-bit)
new_priv = rsa.generate_private_key(...)     # Simulate central make keys rotate
jwks_b = publish_jwks(tmp_path/"public_b.pem")  # kid mới khác hoàn toàn

# Phase 1: fetch_initial JWK A
with patch("app.auth.jwks.httpx.AsyncClient") as mock:
    mock.return_value = _mock_httpx_for_response(jwks_a)
    await cache.fetch_initial()
pub_a = cache.get_public_key(kid_a)  # OK — RSAPublicKey object

# Phase 2: refresh JWK B (rotate scenario)
with patch("app.auth.jwks.httpx.AsyncClient") as mock:
    mock.return_value = _mock_httpx_for_response(jwks_b)
    await cache.refresh()

# Phase 3: verify rotation effect
with pytest.raises(JWKSKidNotFoundError):
    cache.get_public_key(kid_a)  # Cache đã swap sang B → A reject 401
pub_b = cache.get_public_key(kid_b)  # OK — kid mới active
```

Pattern này verify: Plan 03-01 `_derive_kid` deterministic → keypair rotate đổi kid tự nhiên → Plan 03-02 JWKSCache.refresh detect mismatch + cache hoán đổi đúng key set.

## Threat Model Results (8 STRIDE threat từ Plan 03-02)

| Threat ID | Category | Severity | Disposition | Status |
|-----------|----------|----------|-------------|--------|
| **T-03-02-01** | Tampering (env thiếu CENTRAL_JWKS_URL → hub con boot OK nhưng JWT verify 500 silent) | high | mitigate | ✓ MITIGATED — Settings `@model_validator _enforce_central_jwks_url_for_hub` (Task 1) raise ValidationError fail-fast boot. Test parametrize 4 hub × required check (test_hub_con_requires_central_jwks_url) PASS |
| **T-03-02-02** | DoS (Central JWKS xuống lâu → lifespan hang) | medium | mitigate | ✓ MITIGATED — JWKSCache enforce `timeout=5.0` mặc định ở `httpx.AsyncClient(timeout=self._timeout)`. Test `test_jwks_cache_fetch_initial_timeout_raises` verify exception raise → process exit 1 (lifespan startup) |
| **T-03-02-03** | Tampering (MITM thay JWKS response intra-network → hub con cache fake key) | medium | accept | ✓ ACCEPTED — Intra-network HTTP v3.0-a (Plan 03-01 T-03-01-02 inherit). Production Caddy TLS + medinet_net isolation. R-V3-5 24h hard limit minimize window fake key. Defense-in-depth Phase 5 PROXY-01 cross-host |
| **T-03-02-04** | Information Disclosure (logger leak public key bytes hoặc kid) | low | accept | ✓ ACCEPTED — KHÔNG log raw key bytes; chỉ kid string (public identifier RFC 7517 BY DESIGN). structlog JSON internal |
| **T-03-02-05** | EoP (Hub con cache key cũ stale + central rotated → JWT attacker-signed key compromise cũ vẫn pass) | medium | mitigate | ✓ MITIGATED — Background refresh 1h + 24h hard limit. Manual rotation flow: central revoke key cũ → admin invalidate Redis blacklist (Plan 03-03 wire). Multi-key overlap window defer Phase 7 |
| **T-03-02-06** | Tampering (JWT thiếu kid header M2 cũ → bypass JWKS verify) | medium | mitigate | ✓ MITIGATED — Task 4 reject 401 INVALID_TOKEN "Token thiếu kid header — JWT phát hành trước Phase 3 SSO, vui lòng đăng nhập lại". Test `test_hub_con_jwt_missing_kid_returns_401` PASS. Acceptable downtime ~15-30s sau deploy — communicate operator Plan 03-05 README |
| **T-03-02-07** | Repudiation (Hub con verify JWT pass nhưng cached kid là từ ATTACKER compromise central → audit log không trace key version) | low | accept | ✓ ACCEPTED — Audit log M2 chỉ user_id + action + timestamp. v3.0-a accept. Phase 7 multi-key + kid log defer khi audit trail SSO formal |
| **T-03-02-08** | DoS (Asyncio refresh task panic chết → sau 24h KHÔNG fetch lại → 503 mọi request) | high | mitigate | ✓ MITIGATED — `_refresh_loop` wrap try/except global (Task 2) catch Exception ngoài CancelledError + log error + continue. 24h hard limit guarantee fail-loud delayed nếu task chết. Operator alert qua Prometheus metric defer Plan 03-05 observability |

**Tổng:** 8/8 threat addressed (3 accept + 5 mitigate, KHÔNG transfer/avoid/defer). KHÔNG ship threat mới phát sinh.

## Threat Flags

(scan files modified — không có surface mới ngoài threat_model đã liệt kê)

None - new surface area khớp 100% threat_model Plan 03-02.

## Self-Check

### Created Files Exist

| File | Status |
|------|--------|
| `Hub_All/api/tests/unit/test_config_jwks.py` | FOUND |
| `Hub_All/api/tests/unit/test_jwks_cache.py` | FOUND |
| `Hub_All/api/tests/unit/test_get_current_user_jwks_branch.py` | FOUND |
| `Hub_All/api/tests/integration/test_jwks_cache_lifecycle.py` | FOUND |
| `Hub_All/.planning/phases/03-auth-sso-hub-ids-jwt/03-02-SUMMARY.md` | FOUND (file này) |

### Modified Files Verified (grep evidence)

| File | Verify | Status |
|------|--------|--------|
| `api/app/auth/jwks.py` | grep `class JWKSCache` ≥ 1 | OK |
| `api/app/auth/jwks.py` | grep `JWKSStaleError\|JWKSKidNotFoundError` ≥ 2 | OK |
| `api/app/auth/jwt.py` | grep `def verify_token_with_key` ≥ 1 | OK |
| `api/app/auth/jwt.py` | grep `headers={"kid"` ≥ 2 | OK |
| `api/app/auth/dependencies.py` | grep `jwks_cache.get_public_key` ≥ 1 | OK |
| `api/app/main.py` | grep `jwks_cache.fetch_initial` ≥ 1 | OK |
| `api/app/main.py` | grep `JWKS_SKIP_FETCH` ≥ 1 | OK |
| `api/app/config.py` | grep `_enforce_central_jwks_url_for_hub` ≥ 1 | OK |

### Commits Exist (git log --oneline)

| Commit | Verify | Status |
|--------|--------|--------|
| `abe2e37` feat(03-02) Task 1 | `git log \| grep abe2e37` | FOUND |
| `f705569` test(03-02) Task 2 RED | `git log \| grep f705569` | FOUND |
| `895551b` feat(03-02) Task 2 GREEN | `git log \| grep 895551b` | FOUND |
| `c3388aa` feat(03-02) Task 3 | `git log \| grep c3388aa` | FOUND |
| `cfd7412` feat(03-02) Task 4 | `git log \| grep cfd7412` | FOUND |
| `239d0cb` test(03-02) Task 5 | `git log \| grep 239d0cb` | FOUND |

## Self-Check: PASSED

## Next Phase Readiness

### Plan 03-03 (Wave 3 — UNBLOCKED) — JWT iss/aud/hub_ids claim refactor + Redis blacklist key rename

- ✅ JWKSCache + verify_token_with_key + kid header — JWT claim shape mới (`iss="https://central/"` + `aud=["medinet-wiki"]` + `hub_ids` REQUIRED) sẽ verify cùng đường hub con qua cùng JWKSCache.get_public_key(kid) → verify_token_with_key
- ✅ Settings validator pattern — Plan 03-03 nếu cần thêm `central_url` field cho hub con redirect (login/refresh 307) có precedent `_enforce_central_jwks_url_for_hub`
- 📋 Plan 03-03 ship: Redis blacklist key rename `blacklist:` → `auth:blacklist:` (cross-process central + hub con) + `hub_ids` claim build từ `user_hubs` JOIN ở `AuthService.login/refresh` + `iss`/`aud` strict validate ở JWTClaims model

### Plan 03-04 (Wave 4) — Hub con router 307 redirect login/refresh

- 🔓 Plan 03-04 KHÔNG block trên 03-02 (independent layer router refactor) — có thể bắt đầu song song 03-03
- 📋 `auth_router.post("/login")` ở hub con detect `settings.hub_name != "central"` → return 307 Location `{settings.central_url}/api/auth/login`

### Plan 03-05 (Wave 5 closeout) — Phase 3 closeout smoke + docs

- Depends Plan 03-02 + 03-03 + 03-04 — defer sau Wave 2/3/4 close
- 📋 Smoke 2 service compose runtime (central + yte) real: boot central + yte → fetch JWKS thật → JWT issue+verify cross-process PASS

### v3.0-a EXIT GATE (giữa Phase 3-4)

- 🚦 Demo 1 hub con (yte) + central + JWT SSO + golden path PASS → user accept là điều kiện tiếp tục v3.0-b (Phase 4-7)
- Plan 03-02 đóng góp 2/5 plan Phase 3 (Plan 03-01 + 03-02 = 40% Phase 3 close); 3 plan còn lại (03-03..05) sẽ unblock theo wave

---

*Phase: 03-auth-sso-hub-ids-jwt*
*Plan: 02 (SSO-01 part 2 consume layer — Wave 2 BLOCKED 03-01)*
*Completed: 2026-05-22*
*Test result: 27/27 mới PASS (11+9+4+3) + 237/237 unit regression PASS + 10/10 Phase 2 integration regression PASS — KHÔNG break*
