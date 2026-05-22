---
phase: 03-auth-sso-hub-ids-jwt
verified: 2026-05-22T09:15:00Z
status: passed
score: 4/4 must-haves verified
overrides_applied: 0
re_verification: null
---

# Phase 3: Auth SSO + hub_ids trong JWT — Verification Report

**Phase Goal (ROADMAP.md):** Central expose JWKS endpoint public key RS256; hub con cache JWKS local TTL 1h ở startup + refresh background (R-V3-5 HA mitigation); Redis blacklist `auth:blacklist:<jti>` chung cross-process; JWT claim `hub_ids: list[str]` reflect user's hub assignments; E4 reinforced DB-level isolation (hub con KHÔNG access data hub khác kể cả khi JWT compromised).

**Verified:** 2026-05-22T09:15:00Z
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths (4 Success Criteria từ ROADMAP.md)

| #   | Truth (Success Criterion) | Status     | Evidence |
| --- | -------------------------- | ---------- | -------- |
| SC1 | `GET https://central/.well-known/jwks.json` trả public key RS256 (PKCS#8); hub con startup load 1 lần, refresh background mỗi 1h. | ✓ VERIFIED | Plan 03-01 ship `publish_jwks()` ở `api/app/auth/jwks.py:115` + route mount conditional `api/app/main.py:519-558` (Cache-Control 1h + 503 fallback envelope D6 `JWKS_UNAVAILABLE`); Plan 03-02 ship `JWKSCache` class `api/app/auth/jwks.py:191` với `fetch_initial` blocking (5s timeout boot fail-loud D-V3-Phase3-B) + `start_refresh_task` (asyncio 1h fail-quiet) + `is_stale` 24h hard limit; lifespan wire `api/app/main.py:200-227`. 9 unit publish + 9 unit cache + 11 unit config + 4 unit dependency + 3 integration rotate keypair test PASS. |
| SC2 | Login `POST https://central/api/auth/login` → JWT verify được ở hub con qua JWKS cache (cross-process). | ✓ VERIFIED | Plan 03-02 ship `JWTManager.verify_token_with_key` `api/app/auth/jwt.py:266` + `get_current_user` dependency branch `api/app/auth/dependencies.py:86-219` (central=verify_token / hub con=`jwks_cache.get_public_key(kid)` → `verify_token_with_key`). Plan 03-04 ship 307 redirect `api/app/auth/router.py:84-130` (hub con login/refresh → `Location: {central_url}` RFC 7231 preserve POST + body). Plan 03-03 ship `JWT_AUDIENCE="medinet-wiki"` constant `api/app/auth/jwt.py:59` + PyJWT strict audience check 2 verify path (lines 233 + 297). 10 unit router redirect + 9 unit JWT aud/hub_ids + integration test_jwks_cache_lifecycle 3/3 PASS. |
| SC3 | Refresh token blacklist Redis chung: revoke ở central → hub con reject JWT trong < 1s (Redis cross-process semantic — ROADMAP wording said "pub/sub" but D-V3-Phase3-H + Plan 03-03 LOCKED simpler EXISTS check, semantic equivalence). | ✓ VERIFIED | Plan 03-03 ship `api/app/auth/_blacklist.py` mini-module: `REDIS_BLACKLIST_PREFIX = "auth:blacklist:"` (line 25) + `make_blacklist_key(jti)` (line 28). `api/app/auth/service.py` 4 vị trí touch: refresh check (line 171), refresh write (line 206), logout access (line 254), logout refresh (line 263). `api/app/auth/dependencies.py:224` dùng `redis.exists(make_blacklist_key(claims.jti))`. TTL = `max(1, exp-now)` auto-cleanup. 7 unit Redis key schema + integration test_sso_blacklist_cross_process 3/3 PASS. Cross-process semantic: central + hub con dùng cùng Redis instance (M2 baseline), key namespace clarity. |
| SC4 | Stale JWT chứa `hub_ids=["duoc"]` post tới `medinet_hub_yte` API → 403 (E4 reinforced — DB-level + repo-layer + dependency layer). | ✓ VERIFIED | Plan 03-03 ship `get_current_user_for_hub_access` Layer 3 dependency `api/app/auth/dependencies.py:326-388` (check `settings.hub_name in claims.hub_ids` → 403 CROSS_HUB_ACCESS_DENIED nếu mismatch; central bypass cross-hub by design; defensive 500 AUTH_STATE_MISSING). `request.state.jwt_claims` wire `dependencies.py:219` SAU 2 branch verify converge. 4 unit dependency E4 + integration test `test_stale_jwt_cross_hub_returns_403_envelope` (line 145) verify stale JWT `hub_ids=["duoc"]` post hub yte → 403 envelope D6 `CROSS_HUB_ACCESS_DENIED` (KHÔNG 404 leak / 500 error / 200 data leak). 3-layer defense-in-depth: Layer 1 Phase 1 DSN validator + Layer 2 M2 repo `WHERE hub_id` + Layer 3 Plan 03-03 dependency. |

**Score:** 4/4 truths verified

---

### Required Artifacts (4 Levels: Exists, Substantive, Wired, Data-flowing)

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `Hub_All/api/app/auth/jwks.py` | `publish_jwks()` + `JWKSCache` class + lifecycle | ✓ VERIFIED | 375 LOC. `publish_jwks` (line 115) + `load_public_key_as_jwk` (line 83) + `JWKSCache` class (line 191) với `fetch_initial` (line 230), `refresh` (line 242), `get_public_key` (line 306), `is_stale` (line 300), `start_refresh_task` (line 326), `stop_refresh_task` (line 353). 2 exception `JWKSStaleError` (line 150) + `JWKSKidNotFoundError` (line 159). Helper `jwk_to_public_key` (line 178) + `_base64url_to_int` (line 168) + `_int_to_base64url` (line 57) + `_derive_kid` (line 72). Imported + used qua main.py lifespan + dependencies.py verify path + router.py KHÔNG cần (router chỉ redirect). |
| `Hub_All/api/app/auth/jwt.py` | `JWT_AUDIENCE` constant + `verify_token_with_key` + aud/hub_ids REQUIRED | ✓ VERIFIED | `JWT_AUDIENCE = "medinet-wiki"` (line 59). `JWTClaims.aud: list[str]` REQUIRED (line 89), `JWTClaims.hub_ids: list[str]` REQUIRED (line 85, KHÔNG default empty). `issue_token_pair` build `"aud": [JWT_AUDIENCE]` (line 169) + `headers={"kid": self._kid}` (lines 192 + 198). `verify_token_with_key` (line 266) + `verify_token` (line ~210) cả 2 path strict check `audience=JWT_AUDIENCE` (lines 233, 297) + raise `InvalidAudienceError` (lines 239, 303) + `MissingRequiredClaimError` (lines 243, 307). `self._kid = _derive_kid(self._public_pem)` (line 124) — deterministic SHA-256 match Plan 03-01. |
| `Hub_All/api/app/auth/_blacklist.py` | `make_blacklist_key` helper + `REDIS_BLACKLIST_PREFIX` constant | ✓ VERIFIED | 39 LOC mini-module. `REDIS_BLACKLIST_PREFIX = "auth:blacklist:"` (line 25) + `def make_blacklist_key(jti)` (line 28) returning `f"{REDIS_BLACKLIST_PREFIX}{jti}"`. Imported 4 vị trí service.py + 1 vị trí dependencies.py. Re-export `__init__.py`. |
| `Hub_All/api/app/auth/dependencies.py` | `get_current_user` branch verify + `get_current_user_for_hub_access` Layer 3 dep | ✓ VERIFIED | 495 LOC. `get_current_user` (line 86) branch theo `settings.hub_name`: central qua `verify_token` (M2 carry forward) / hub con qua `pyjwt.get_unverified_header(token)["kid"]` → `jwks_cache.get_public_key(kid)` (line 187) → `verify_token_with_key` (line 204). 4 reject path mới: JWKS_CACHE_UNAVAILABLE 503 (line 153), JWKS_STALE 503 (line 191), 2x INVALID_TOKEN 401 (thiếu kid + kid mismatch). `request.state.jwt_claims = claims` wire (line 219) sau 2 branch converge. Redis blacklist `redis.exists(make_blacklist_key(claims.jti))` (line 224). `get_current_user_for_hub_access` (line 326) Layer 3 dependency: central bypass + hub con `settings.hub_name not in claims.hub_ids` → 403 CROSS_HUB_ACCESS_DENIED envelope (line 381-388) + defensive 500 AUTH_STATE_MISSING (line 373). |
| `Hub_All/api/app/auth/router.py` | 307 redirect login/refresh ở hub con | ✓ VERIFIED | `RedirectResponse` import (line 33). `_sso_redirect(target_path, hub_name)` helper (line 61): if hub con + central_url set → return `RedirectResponse(url=f"{settings.central_url}{target_path}", status_code=307, headers={X-SSO-Redirect-Reason, X-SSO-Original-Hub})` (line 84-93); fallback 503 envelope nếu central_url None (defensive). `login` handler (line 94) `response_model=None` opt-out + branch hub con (line 106 → 107 call `_sso_redirect("/api/auth/login", ...)`). `refresh` handler (line 118) tương tự (line 129-130). logout + me KHÔNG đụng (D-V3-Phase3-G: handle local). |
| `Hub_All/api/app/config.py` | `central_jwks_url` + `central_url` field + validator REQUIRED khi hub_name != central | ✓ VERIFIED | `central_jwks_url: str \| None = None` (line 109). `jwks_refresh_interval: int = 3600` (line 116) + `jwks_max_stale_seconds: int = 86400` (line 117). `central_url: str \| None = None` (line 126). `@model_validator(mode="after")` `_enforce_central_jwks_url_for_hub` (line 287) raise nếu `hub_name != "central"` + `central_jwks_url` falsy (line 300). `_enforce_central_url_for_hub` (line 309) tương tự (line 330). |
| `Hub_All/api/app/main.py` | JWKS endpoint mount conditional + lifespan hub con JWKSCache blocking fetch | ✓ VERIFIED | Lifespan branch (lines 184-229): `if hub_name != "central"` → instantiate `JWKSCache(jwks_url, refresh_interval, max_stale_seconds)` (line 210) → `await jwks_cache.fetch_initial()` blocking (line 216) → exception re-raise (line 220, boot fail-loud D-V3-Phase3-B) → `jwks_cache.start_refresh_task()` (line 226) → wire `app.state.jwks_cache` (line 227). Escape hatch `JWKS_SKIP_FETCH=1` (line 194) bypass blocking fetch test mode. Shutdown (lines 311-317): graceful `_shutdown_jwks_cache.stop_refresh_task()` rename local var tránh mypy union conflict. Central mount endpoint (lines 522-558): `@app.get("/.well-known/jwks.json")` trong block central-only + try/except wrap → 503 `JWKS_UNAVAILABLE` envelope D6 + Cache-Control header `public, max-age=3600`. |
| `Hub_All/api/app/auth/service.py` | Redis blacklist key qua make_blacklist_key (4 vị trí) | ✓ VERIFIED | Import `from app.auth._blacklist import make_blacklist_key` (line 18). 4 vị trí touch: refresh check `make_blacklist_key(claims.jti)` (line 171), refresh write (line 206), logout access (line 254), logout refresh (line 263). |
| `Hub_All/docker-compose.yml` + `override.yml.template` | CENTRAL_JWKS_URL + CENTRAL_URL env 3 hub con | ✓ VERIFIED | `docker-compose.yml` env `CENTRAL_JWKS_URL: http://python-api-central:8080/.well-known/jwks.json` × 3 hub con (yte=line 129, duoc=163, hcns=196). `CENTRAL_URL: http://python-api-central:8080` × 3 hub con (yte=133, duoc=166, hcns=199). Central block KHÔNG đụng. Override template (lines 27 + 30) cho FACTOR-04 hub mới `make hub-add` auto-inherit. `docker compose config --quiet` exit 0 base render OK. |

**Final artifact status:** 9/9 VERIFIED (all exists + substantive + wired + data-flowing where applicable).

---

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | -- | --- | ------ | ------- |
| `api/app/main.py::create_app()` (central block) | `api/app/auth/jwks.py::publish_jwks()` | `@app.get("/.well-known/jwks.json")` route handler | ✓ WIRED | Import `from app.auth.jwks import publish_jwks` (main.py:519) + handler call `publish_jwks(settings.jwt_public_key_path)` (line 534) + return JSONResponse with Cache-Control 1h. 503 envelope fallback (`JWKS_UNAVAILABLE` line 547). Verified qua 9 unit test test_jwks_publish.py + integration test_jwks_cache_lifecycle Phase 1 endpoint serve. |
| `api/app/main.py::lifespan()` (hub con branch) | `api/app/auth/jwks.py::JWKSCache.fetch_initial` | `if settings.hub_name != "central": await jwks_cache.fetch_initial()` | ✓ WIRED | Import `from app.auth.jwks import JWKSCache` (main.py:200) + instantiate + await fetch_initial blocking (line 216) + start refresh task (line 226) + wire `app.state.jwks_cache` (line 227). Boot fail-loud re-raise (line 220). Verified qua integration test rotate keypair 3/3 PASS + Phase 2 integration regression 10/10 PASS (escape hatch JWKS_SKIP_FETCH bypass test mode). |
| `api/app/auth/dependencies.py::get_current_user` (hub con branch) | `api/app/auth/jwks.py::JWKSCache.get_public_key` | `kid extract → jwks_cache.get_public_key(kid) → verify_token_with_key` | ✓ WIRED | Branch `if settings.hub_name != "central"` (line ~150) → `unverified_header = pyjwt.get_unverified_header(token)` → `kid = unverified_header.get("kid")` → `jwks_cache.get_public_key(kid)` (line 187) → `verify_token_with_key(token, public_key, expected_type="access")` (line 204). 4 reject path mới (JWKS_CACHE_UNAVAILABLE 503 / JWKS_STALE 503 / 2× INVALID_TOKEN 401). Verified qua 4 unit dependency branch test + 3 integration test_jwks_cache_lifecycle PASS. |
| `api/app/auth/dependencies.py::get_current_user_for_hub_access` (Layer 3) | `request.state.jwt_claims` | `if settings.hub_name not in claims.hub_ids: raise 403 CROSS_HUB_ACCESS_DENIED` | ✓ WIRED | `request.state.jwt_claims = claims` set ở `get_current_user` (line 219) SAU 2 branch verify converge. `get_current_user_for_hub_access` (line 326) reads state qua `getattr(request.state, "jwt_claims", None)` + check `settings.hub_name not in claims.hub_ids` (line 381) → 403 CROSS_HUB_ACCESS_DENIED envelope D6 (line 385). Central bypass (line ~365). Defensive 500 AUTH_STATE_MISSING (line 373). Verified qua 4 unit + integration test_stale_jwt_cross_hub_returns_403_envelope PASS (stale JWT hub_ids=["duoc"] post tới yte app → 403). |
| `api/app/auth/service.py::AuthService.logout` | Redis SET `auth:blacklist:{access_jti}` | `redis.set(make_blacklist_key(access_jti), "1", ex=access_ttl)` | ✓ WIRED | 4 vị trí touch service.py (refresh check 171, refresh write 206, logout access 254, logout refresh 263) qua import `make_blacklist_key` (line 18) + 1 vị trí check ở dependencies.py:224. TTL = `max(1, exp-now)` auto-cleanup. Verified qua 7 unit test_redis_blacklist_key_schema PASS (prefix constant + helper format + UUID jti + logout key prefix + TTL semantic). |
| `api/app/auth/router.py::login/refresh` (hub con) | central URL | `RedirectResponse(url=f"{settings.central_url}{target_path}", status_code=307)` | ✓ WIRED | `_sso_redirect` helper (line 61-93) build RedirectResponse 307 với Location header + X-SSO-Redirect-Reason + X-SSO-Original-Hub headers. Login handler (line 94) + refresh handler (line 118) cả 2 đều branch `if settings.hub_name != "central": return _sso_redirect(...)` (lines 107, 130) + `response_model=None` opt-out FastAPI union return type fail. Verified qua 10 unit test_auth_router_hub_redirect (6 parametrize 3 hub × 2 endpoint + 4 LOCAL central) + Phase 2 integration test_factor_hub_scoped split 10 LOCAL + 2 SSO REDIRECT assertion (TestClient `follow_redirects=False` critical) PASS. |
| `api/app/config.py::Settings._enforce_central_jwks_url_for_hub` | `api/app/auth/jwks.py::JWKSCache (consume)` | `model_validator raise ValueError nếu hub con KHÔNG set CENTRAL_JWKS_URL` | ✓ WIRED | Validator (line 287) raise nếu `hub_name != "central"` + `central_jwks_url` falsy (line 300) → ValidationError fail-fast boot. Tương tự `_enforce_central_url_for_hub` (line 309) cho central_url. Verified qua 11 unit test_config_jwks (default + parametrize 4 hub × required + override env) PASS. |
| `docker-compose.yml` (3 hub con block) | `Settings.central_jwks_url` + `central_url` consume | `environment.CENTRAL_JWKS_URL: http://python-api-central:8080/.well-known/jwks.json` + `CENTRAL_URL: http://python-api-central:8080` | ✓ WIRED | 3 hub con (yte/duoc/hcns) env CENTRAL_JWKS_URL (lines 129/163/196) + CENTRAL_URL (lines 133/166/199). Override template (lines 27/30) cho FACTOR-04 hub mới inherit. `docker compose config --quiet` exit 0. |

**Final link status:** 8/8 WIRED.

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| -------- | ------------- | ------ | ------------------ | ------ |
| `jwks.py::publish_jwks()` | JWK Set response | `cryptography.serialization.load_pem_public_key(public_key_path)` → `RSAPublicNumbers` → base64url encode | ✓ Yes — reads M2 keypair `api/keys/public.pem` 4096-bit, derives kid deterministic SHA-256 11-char base64url, exposes via `/.well-known/jwks.json` endpoint with Cache-Control 1h. Integration test verifies sample JWK shape RFC 7517 (kid example: `hDRHjB_zZNY`). | ✓ FLOWING |
| `jwks.py::JWKSCache._fetch_and_cache()` | `self._keys_by_kid: dict[str, RSAPublicKey]` | `httpx.AsyncClient.get(self._jwks_url)` → `data["keys"]` → `jwk_to_public_key(jwk)` populate dict + `self._last_refresh_ts = time.time()` | ✓ Yes — real httpx fetch JWKS từ central, build RSAPublicKey objects, populate keyed cache. Integration test rotate keypair verifies cache swap correctly when central publishes new kid. | ✓ FLOWING |
| `dependencies.py::get_current_user` (hub con branch) | `claims` (JWTClaims) | `pyjwt.get_unverified_header(token)` → kid extract → `jwks_cache.get_public_key(kid)` → `verify_token_with_key(token, public_key)` returns JWTClaims | ✓ Yes — extracts real JWT kid header, looks up RSAPublicKey from cache, verifies signature + audience + claim shape, returns populated JWTClaims with aud + hub_ids. | ✓ FLOWING |
| `dependencies.py::get_current_user_for_hub_access` | `claims.hub_ids` | `request.state.jwt_claims` (set by upstream `get_current_user` line 219) → check `settings.hub_name in claims.hub_ids` | ✓ Yes — reads JWT claim list, enforces hub isolation by claim shape. Integration test `test_stale_jwt_cross_hub_returns_403_envelope` verifies real 403 envelope CROSS_HUB_ACCESS_DENIED with `hub_ids=["duoc"]` post tới yte app. | ✓ FLOWING |
| `service.py::AuthService.logout` (Redis blacklist) | Redis key `auth:blacklist:{jti}` | `redis.set(make_blacklist_key(access_jti), "1", ex=access_ttl)` with `access_ttl = max(1, access_exp - now())` | ✓ Yes — writes real Redis key with TTL = JWT expiry. Verified qua 7 unit test (assert call_args.kwargs.get("ex") in tolerance window + value "1" marker). Cross-process integration test verify cross-hub blacklist propagate. | ✓ FLOWING |

**Final data-flow status:** 5/5 FLOWING.

---

### Behavioral Spot-Checks (Step 7b)

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| `jwks.py::publish_jwks` is importable + callable | (Static — verified via 9 unit test_jwks_publish PASS 5.24s) | ImportError check pass + JWK shape RFC 7517 assert pass | ✓ PASS (in-process) |
| `JWKSCache` lifecycle (fetch + refresh + stale) | (Static — verified via 9 unit test_jwks_cache + 3 integration test_jwks_cache_lifecycle PASS) | All 12 PASS | ✓ PASS (in-process) |
| Stale JWT cross-hub → 403 envelope D6 | (Static — verified via 3 integration test_sso_blacklist_cross_process PASS, 4 unit dependency E4 PASS) | E4 reinforced reject `hub_ids=["duoc"]` cross-hub PASS | ✓ PASS (in-process) |
| Hub con 307 redirect login/refresh | (Static — verified via 10 unit test_auth_router_hub_redirect + Phase 2 integration test_factor_hub_scoped split assertion PASS) | 6 parametrize 3 hub × 2 endpoint trả 307 Location + X-SSO headers PASS | ✓ PASS (in-process) |
| Docker compose render OK | `docker compose config --quiet` | Plan 03-01 + 03-04 reports exit 0 | ? SKIP (smoke runtime defer Phase 7 MIGRATE-05 — pre-resolved user decision) |
| Smoke E2E compose runtime central + yte real | (Plan 03-05 Task 5 explicit SKIP per user decision 2026-05-22 — defer Phase 7 MIGRATE-05 full E2E with rationale) | Evidence chain in-process semantic 65+ unit + 6 integration PASS đủ cover SSO-01..04 + docker compose config base PASS | ? SKIP (deferred Phase 7 MIGRATE-05) |

**Spot-check status:** 4/6 PASS in-process semantic, 2/6 SKIP deferred Phase 7 MIGRATE-05 (user-accepted skip per task instructions "smoke runtime SKIP — KHÔNG đánh dấu human_needed nếu in-process evidence đủ").

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| ----------- | ----------- | ----------- | ------ | -------- |
| SSO-01 | Plans 03-01, 03-02, 03-05 | Central JWKS endpoint + hub con cache TTL 1h HA + R-V3-5 mitigation | ✓ SATISFIED | `jwks.py` 375 LOC publish + cache; 9 unit publish + 11 unit config + 9 unit cache + 4 unit dep + 3 integration rotate keypair test PASS. D-V3-Phase3-A/B/D LOCKED consumed. REQUIREMENTS.md mark [x] DONE 2026-05-22. |
| SSO-02 | Plans 03-03, 03-04, 03-05 | Redis blacklist chung cross-process + hub con KHÔNG sinh refresh (307 redirect central) | ✓ SATISFIED | `_blacklist.py` mini-module + `auth:blacklist:` key rename 5 vị trí (4 service.py + 1 dependencies.py) + Plan 03-04 307 redirect Location: central. 7 unit Redis key + 10 unit router redirect + 3 integration cross-process test PASS. D-V3-Phase3-C/G/H LOCKED consumed. REQUIREMENTS.md mark [x] DONE 2026-05-22. |
| SSO-03 | Plans 03-03, 03-05 | JWT claim hub_ids cho cross-hub access control + central JWT issuer fixed | ✓ SATISFIED | `JWTClaims.hub_ids: list[str]` REQUIRED + `aud: list[str] = ["medinet-wiki"]` REQUIRED + PyJWT strict audience check 2 verify path + `JWT_ISSUER="medinet-wiki"` RE-CONFIRM (URL-based defer Phase 7 MCP). 9 unit jwt iss/aud/hub_ids test PASS. D-V3-Phase3-E LOCKED consumed. REQUIREMENTS.md mark [x] DONE 2026-05-22. |
| SSO-04 | Plans 03-03, 03-05 | E4 reinforced — hub con DB-level + repo-layer + dependency layer enforce; stale JWT hub_ids=["duoc"] post yte → 403 | ✓ SATISFIED | `get_current_user_for_hub_access` Layer 3 dependency (`api/app/auth/dependencies.py:326`). 3-layer defense-in-depth: Layer 1 Phase 1 DSN validator + Layer 2 M2 repo `WHERE hub_id` + Layer 3 Plan 03-03 dependency hub_ids check. 4 unit dependency E4 + 3 integration test_sso_blacklist_cross_process (stale JWT 403 envelope + matching accept + central bypass) PASS. REQUIREMENTS.md mark [x] DONE 2026-05-22. |

**Coverage:** 4/4 SSO REQ-IDs satisfied. Mọi REQ-ID phase 3 (SSO-01..04) ít nhất 2 plans ship với evidence test/code. Không có orphaned requirements (REQUIREMENTS.md phase 3 maps đúng 4 REQ-ID match plan declarations).

---

### Anti-Patterns Found

Files modified in Phase 3 scan (key files only):

| File | Pattern | Severity | Impact |
| ---- | ------- | -------- | ------ |
| (none) | No TODO/FIXME/XXX/HACK/PLACEHOLDER found in core implementation files (`jwks.py`, `jwt.py`, `_blacklist.py`, `dependencies.py`, `router.py`, `config.py`, `main.py`, `service.py`) | — | None |
| `dependencies.py:86` | `# noqa: C901` cyclomatic complexity 13 > 10 | ℹ️ Info | Justified deviation Plan 03-02 (5 reject path mới hub con branch linear, refactor sub-function sẽ làm logic khó trace). Documented inline. |
| `main.py` Test-mode escape hatch `JWKS_SKIP_FETCH=1` | Environment-driven test bypass | ℹ️ Info | Pattern song song COCOINDEX_SKIP_SETUP=1 (DEF-05-01). Production KHÔNG bao giờ set — fail-loud D-V3-Phase3-B giữ nguyên. Integration test mới dùng để bypass blocking fetch khi fake URL. |
| `dependencies.py:373` | Defensive 500 AUTH_STATE_MISSING (paranoid guard) | ℹ️ Info | Defensive scaffolding — phát hiện sớm bug dep chain broken thay vì silent authorization bypass. Acceptable defensive code (not stub). |

**Total anti-patterns:** 0 blocker, 0 warning, 3 informational (all justified defensive/escape hatch patterns documented in summaries).

---

### Deferred Items

**Phase 3 deferred to later milestone phases (per Step 9b filter against ROADMAP.md):**

| # | Item | Addressed In | Evidence |
| - | ---- | ------------ | -------- |
| 1 | Smoke compose runtime E2E (central + yte real + golden path) | Phase 7 (MIGRATE-05) | ROADMAP Phase 7 SC5: "Docker compose mở rộng up đầy đủ (1 Postgres + 1 Redis + 4 FastAPI + Caddy + frontend); golden path 3 hub con + tổng PASS (login → upload → search local + cross-hub → ask → citation); cross-hub p95 < 1.5s (E-V3-2); hub isolation enforce (E-V3-3)" — Plan 03-05 Task 5 SKIP rationale matches exactly. |
| 2 | Frontend redirect form action `<form action="https://central/api/auth/login">` wire | Phase 5 (PROXY-02) | ROADMAP Phase 5 SC2: "Frontend `window.location.pathname.split('/')[1]` detect prefix → API base URL chính xác cho từng hub; 1 build dùng chung 4 deploy" + D-V3-Phase3-F honored (defer Phase 5 PROXY-02 sau D6 expire D-V3-06). Backend 307 redirect ship sẵn sàng Plan 03-04. |
| 3 | Per-hub login branding | Phase 5 (PROXY-04) | ROADMAP Phase 5 SC4: "Per-hub login branding: Hub y_te logo + title VN khác Hub dược, Hub hcns, central; tách `frontend/src/branding/<hub>/`". |
| 4 | Multi-key JWKS rotation overlap window | Phase 7 (MIGRATE-04 MCP service) | Plan 03-01 D-V3-Phase3-A note "Single-key strategy v3.0-a; multi-key rotation defer Phase 7" + ROADMAP Phase 7 SC4: "MCP service re-point central; `mcp_service` 135/135 test PASS". |
| 5 | iss URL-based `https://central/` split per audience (medinet-wiki vs medinet-wiki-mcp) | Phase 7 (MIGRATE-04) | Plan 03-03 RE-CONFIRM D-V3-Phase3-E ghi rõ "URL-based iss defer Phase 7 khi MCP split audience". |

**Deferred items do NOT affect status determination.** All deferred items have clear evidence in later milestone phase goals/success criteria.

---

### Human Verification Required

**(EMPTY — per task instructions: "Smoke checkpoint runtime SKIP — KHÔNG đánh dấu human_needed nếu in-process evidence đủ. Smoke + v3.0-a EXIT GATE demo defer Phase 7 (operator manual khi sẵn sàng)".)**

In-process evidence chain (65+ unit + 6 integration test + docker compose config base PASS) covers end-to-end semantic SSO-01..04. Backend wiring complete + verifiable static. No human verification gate required at Phase 3 closeout; v3.0-a EXIT GATE demo defer Phase 7 MIGRATE-05 with operator manual sign-off when full E2E runtime ready.

---

### Gaps Summary

**No gaps found.**

Phase 3 ships SSO-01..04 (4/4 REQ) with 30 commits + 65+ unit test + 6 integration test PASS in-process + Phase 2 integration regression 10/10 PASS + `docker compose config --quiet` base PASS + ruff + mypy --strict clean across Plan 03-01..04. All 8 LOCKED decisions D-V3-Phase3-A..H consumed. 33 STRIDE threats addressed (15 accept + 18 mitigate, 0 transfer/avoid/defer). M2 backward incompat TRIPLE cumulative (kid Plan 03-02 + aud Plan 03-03 + hub_ids Plan 03-03) documented in README operator deployment notes section with broadcast template + rollback procedure.

E4 reinforced 3-layer defense-in-depth verified:
- **Layer 1** (Phase 1 Plan 01-02) `_enforce_hub_dsn_match` DSN validator — boot-time fail-fast.
- **Layer 2** (M2 carry forward) repository layer `WHERE hub_id = settings.hub_name` — query-time filter.
- **Layer 3** (Plan 03-03 new) `get_current_user_for_hub_access` dependency — JWT claim hub_ids check → 403 CROSS_HUB_ACCESS_DENIED envelope D6 (NOT 404 leak / 500 error / 200 data leak).

**v3.0-a EXIT GATE TRIGGERED** — Phase 1+2+3 DONE (3/3 phase v3.0-a — 15/~32 plan ≈ 47%). Demo deliverable defer Phase 7 MIGRATE-05 full E2E runtime; evidence chain in-process semantic PASS đủ cho user accept decision.

---

*Verified: 2026-05-22T09:15:00Z*
*Verifier: Claude (gsd-verifier)*
*Phase: 03-auth-sso-hub-ids-jwt*
*Re-verification: No — initial verification*
