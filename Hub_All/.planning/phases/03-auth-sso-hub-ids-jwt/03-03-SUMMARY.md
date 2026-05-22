---
phase: 03-auth-sso-hub-ids-jwt
plan: 03
subsystem: auth
tags:
  - jwt-iss-aud
  - hub-ids-required
  - redis-blacklist-key-rename
  - cross-process-blacklist
  - e4-reinforced
  - d-v3-phase3-e
  - d-v3-phase3-h
  - sso-02
  - sso-03
  - sso-04
  - layer-3-defense-in-depth

# Dependency graph
requires:
  - phase: 03-auth-sso-hub-ids-jwt
    provides: "Plan 03-02 ship JWKSCache + verify_token_with_key + dependency branch + kid header — Plan 03-03 EXTEND claim shape (aud/hub_ids REQUIRED) + Redis key rename + E4 reinforced dependency"
  - phase: 02-hub-con-codebase-factor
    provides: "create_app() factory conditional mount + hub_app_factory fixture + Starlette HTTPException 404 envelope — Plan 03-03 integration test reuse fixture"
  - phase: 01-multi-db-topology
    provides: "Settings.hub_name + _enforce_hub_dsn_match validator — Plan 03-03 E4 reinforced Layer 3 đứng cùng Layer 1 DSN validator"
provides:
  - "JWT_AUDIENCE constant + JWTClaims.aud REQUIRED + JWTClaims.hub_ids REQUIRED (xoá default []) — claim shape mới D-V3-Phase3-E"
  - "verify_token + verify_token_with_key cả 2 path strict check audience=JWT_AUDIENCE qua pyjwt.decode param"
  - "api/app/auth/_blacklist.py mini-module: REDIS_BLACKLIST_PREFIX constant + make_blacklist_key helper (D-V3-Phase3-H)"
  - "AuthService.refresh + AuthService.logout dùng key `auth:blacklist:{jti}` (4 vị trí touch)"
  - "get_current_user dependency: wire request.state.jwt_claims = claims SAU verify pass (cả 2 branch) + Redis key rename"
  - "get_current_user_for_hub_access dependency MỚI: Layer 3 E4 enforce HUB_NAME in claims.hub_ids → 403 CROSS_HUB_ACCESS_DENIED (SSO-04)"
affects:
  - "03-04 (Wave 4) hub con auth router 307 redirect — service.py + dependencies.py shape mới đã ship sẵn sàng. Login/refresh handler ở central giữ pattern aud + hub_ids REQUIRED."
  - "03-05 closeout smoke 2 service compose runtime — verify cross-process Redis blacklist `auth:blacklist:` + E4 reinforced JWT cross-hub reject ở runtime container thật. Banner README backward incompat double (kid Plan 03-02 + aud/hub_ids Plan 03-03)."
  - "05 PROXY-* — hub con dependency Layer 3 sẵn sàng wire vào endpoint sensitive (vd /api/documents upload) — Plan 03-04 chọn endpoint nào enforce."
  - "07 MIGRATE-04 (MCP service) — verify pattern reuse: JWT split audience `medinet-wiki-mcp` thêm tách aud claim từ central."

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "JWT audience strict check (RFC 7519) qua PyJWT decode `audience=JWT_AUDIENCE` param — raise InvalidAudienceError + MissingRequiredClaimError mapped sang JWTError tiếng Việt"
    - "Mini-module pattern (`_blacklist.py`) tách constant/helper cross-feature dùng cả service.py + dependencies.py — tránh circular import giữa 2 module gần nhau"
    - "request.state attach pattern — dependency upstream (get_current_user) set state SAU verify pass + dependency downstream (get_current_user_for_hub_access) read state KHÔNG re-decode JWT. Pragmatic defense-in-depth Layer 3 KHÔNG cần touch JWKS chain"
    - "FastAPI dependency override + middleware inject state pattern cho integration test — bypass JWKS+DB+Redis chain phức tạp để cô lập test logic Layer 3"

key-files:
  created:
    - "Hub_All/api/app/auth/_blacklist.py — REDIS_BLACKLIST_PREFIX + make_blacklist_key helper (D-V3-Phase3-H)"
    - "Hub_All/api/tests/unit/test_jwt_iss_aud_hub_ids.py — 9 unit test JWT iss/aud/hub_ids claim refactor (Task 1)"
    - "Hub_All/api/tests/unit/test_redis_blacklist_key_schema.py — 7 unit test Redis blacklist key schema rename (Task 2)"
    - "Hub_All/api/tests/integration/test_sso_blacklist_cross_process.py — 3 integration test E4 reinforced cross-hub JWT (Task 4)"
    - "Hub_All/.planning/phases/03-auth-sso-hub-ids-jwt/03-03-SUMMARY.md (file này)"
  modified:
    - "Hub_All/api/app/auth/jwt.py — JWT_AUDIENCE constant + JWTClaims aud REQUIRED + hub_ids REQUIRED + verify_token/verify_token_with_key strict audience check (+85 LOC: 267 → 336 — module docstring + claim model + 2 verify path)"
    - "Hub_All/api/app/auth/dependencies.py — get_current_user wire request.state.jwt_claims + Redis key rename qua helper + dependency mới get_current_user_for_hub_access (+78 LOC: 417 → 495)"
    - "Hub_All/api/app/auth/service.py — 4 vị trí dùng make_blacklist_key (refresh check + write + logout access + logout refresh) + import helper (+7 LOC: 283 → 290)"
    - "Hub_All/api/app/auth/__init__.py — re-export JWT_AUDIENCE + REDIS_BLACKLIST_PREFIX + make_blacklist_key + get_current_user_for_hub_access (+6 LOC: 83 → 89)"
    - "Hub_All/api/tests/unit/test_jwt.py — Rule 3 regression: thêm audience='medinet-wiki' param vào 2 test pyjwt.decode raw + thêm 'aud' vào required claim set (+15 LOC)"
    - "Hub_All/api/tests/unit/test_get_current_user_jwks_branch.py — append 4 test SSO-04 E4 reinforced (central bypass + hub_con reject + accept matching + state missing 500) — Task 3 (+118 LOC: 196 → 314)"
    - "Hub_All/api/tests/integration/test_jwt_compat.py — Rule 3 regression: thêm audience='medinet-wiki' param + assert decoded['aud'] (+9 LOC)"

key-decisions:
  - "D-V3-Phase3-E consumed (LOCKED CONTEXT.md): aud REQUIRED + hub_ids REQUIRED + iss giữ NGUYÊN 'medinet-wiki' (RE-CONFIRM — KHÔNG URL-based, defer Phase 7 MCP split aud). PyJWT decode strict audience check 2 path. M2 cũ JWT thiếu aud/hub_ids reject 401 (backward incompat acceptable + Plan 03-02 backward incompat kid missing → double reject ~15-30s downtime communicate Plan 03-05)"
  - "D-V3-Phase3-H consumed (LOCKED CONTEXT.md): key schema `auth:blacklist:{jti}` (namespace clarity) + TTL=max(1, exp-now) (M2 carry forward guard) + value '1' marker + 1 Redis instance cross-process (M2 baseline). Tạo `_blacklist.py` mini-module để tránh circular import service↔dependencies (cả 2 cần access prefix)"
  - "SSO-04 E4 reinforced 3-layer enforce: Layer 1 (Phase 1) DSN validator + Layer 2 (M2) repository WHERE hub_id + Layer 3 (Plan 03-03 MỚI) dependency `get_current_user_for_hub_access` JWT claim hub_ids check. Central bypass (cross-hub by design) + hub con strict check → 403 CROSS_HUB_ACCESS_DENIED envelope (KHÔNG 404 leak / 500 error)"
  - "request.state.jwt_claims pattern (Plan 03-03 Task 3): set ở get_current_user SAU verify pass (cả 2 branch converge sau Plan 03-02 branch chain) + read ở get_current_user_for_hub_access. Pragmatic — tránh re-decode JWT lần 2. Defensive 500 AUTH_STATE_MISSING guard phát hiện sớm dep chain broken"
  - "Test override pattern (Task 4): `app.dependency_overrides[get_current_user]` + middleware inject state để cô lập integration test E4 logic. Full multi-process docker compose smoke defer Plan 03-05 closeout"
  - "iss URL-based deferred Phase 7: RE-CONFIRM D-V3-Phase3-E gốc đề xuất `iss='https://central/'` — analysis cho thấy chuỗi cố định `medinet-wiki` đủ cho v3.0-a (aud claim đủ phân biệt service); URL-based defer Phase 7 MCP service formal split audience tách `medinet-wiki-mcp` riêng"

patterns-established:
  - "Pattern 1 (Plan 03-03 - PyJWT audience strict check): `pyjwt.decode(..., audience=JWT_AUDIENCE)` raise InvalidAudienceError (mismatch) + MissingRequiredClaimError (missing). Wrap qua JWTError với message tiếng Việt + hint 'JWT phát hành trước Phase 3 SSO — vui lòng đăng nhập lại'. Phase 7 MIGRATE-04 MCP split audience reuse pattern"
  - "Pattern 2 (Plan 03-03 - Mini-module cross-module shared constant): tạo `_blacklist.py` module nhỏ chứa REDIS_BLACKLIST_PREFIX + make_blacklist_key. Tránh circular import service↔dependencies (cả 2 file gần nhau cùng cần helper). Pattern này áp dụng được cho Plan 04 SYNC outbox key naming nếu phát sinh shared constant"
  - "Pattern 3 (Plan 03-03 - Defense-in-depth Layer 3 dependency): dependency mới `get_current_user_for_hub_access` đứng cạnh `get_current_user` (Layer N+1). Pattern này dùng được cho mọi sensitive endpoint cần thêm authorization check (vd `get_current_user_admin_only` ở central). Plan 03-04 wire dep này vào endpoint upload sensitive nếu cần"
  - "Pattern 4 (Plan 03-03 - request.state attach claims): dependency upstream set state SAU verify pass + downstream read state. Pragmatic — tránh re-decode JWT. Pattern reuse được cho mọi dep cần access JWT claim chính (vd authorization role check based on JWT role claim mà KHÔNG cần DB query lại)"
  - "Pattern 5 (Plan 03-03 - Integration test override pattern): `app.dependency_overrides[get_current_user] = mock_fn` + `@app.middleware('http')` inject state. Cô lập test logic Layer N+1 KHÔNG đụng chain Layer 1..N phức tạp. Pattern áp dụng được cho mọi test dep chain với external IO (JWKS+DB+Redis)"

requirements-completed:
  - SSO-02
  - SSO-03
  - SSO-04

# Metrics
duration: 26min
completed: 2026-05-22
---

# Phase 3 Plan 03: JWT iss/aud/hub_ids Refactor + Redis Blacklist Rename + E4 Reinforced Summary

**JWT claim refactor `aud` REQUIRED + `hub_ids` REQUIRED (D-V3-Phase3-E) + Redis blacklist key rename `auth:blacklist:` (D-V3-Phase3-H) + SSO-04 E4 reinforced dependency `get_current_user_for_hub_access` Layer 3 defense-in-depth — Plan 03-03 đóng 3 REQ (SSO-02/03/04) tightly-coupled refactor 3 file (`jwt.py` + `service.py` + `dependencies.py`) trong single plan tránh merge conflict. M2 backward incompat double (kid Plan 03-02 + aud/hub_ids Plan 03-03) → user re-login ~15-30s downtime acceptable, communicate operator README Plan 03-05.**

## Performance

- **Duration:** ~26 phút (4 task tuần tự + 1 Rule 3 regression fix tự động)
- **Started:** 2026-05-22T07:32:13Z
- **Completed:** 2026-05-22T07:58:24Z
- **Tasks:** 4/4 (Task 1 TDD JWT claim 9min + Task 2 TDD Redis key rename 4min + Task 3 E4 dependency 5min + Task 4 integration test 8min)
- **Files modified:** 8 (4 mới: 1 module nhỏ `_blacklist.py` + 3 test file mới — 2 unit + 1 integration + 4 sửa: jwt.py + dependencies.py + service.py + __init__.py + 2 test regression update Rule 3 fix)

## Accomplishments

- **JWT claim refactor (D-V3-Phase3-E)** trong `api/app/auth/jwt.py`:
  - `JWT_AUDIENCE = "medinet-wiki"` constant — single audience v3.0-a (split per-service defer Phase 7 MIGRATE-04).
  - `JWTClaims.aud: list[str]` REQUIRED (RFC 7519) — Pydantic ValidationError nếu thiếu.
  - `JWTClaims.hub_ids: list[str]` REQUIRED (xoá default `[]` M2) — Pydantic ValidationError nếu thiếu.
  - `issue_token_pair` build `base["aud"] = [JWT_AUDIENCE]` cùng `hub_ids` caller-provided.
  - `verify_token` + `verify_token_with_key` cả 2 path strict check `audience=JWT_AUDIENCE` qua `pyjwt.decode` param — raise `InvalidAudienceError` / `MissingRequiredClaimError` map sang `JWTError` tiếng Việt.
  - `JWT_ISSUER` giữ NGUYÊN `"medinet-wiki"` (RE-CONFIRM — KHÔNG URL-based; defer Phase 7 khi MCP split audience).

- **Redis blacklist key rename (D-V3-Phase3-H)** trong `api/app/auth/_blacklist.py` (mới):
  - `REDIS_BLACKLIST_PREFIX = "auth:blacklist:"` constant — namespace clarity tránh collision future feature (vd `apikey:blacklist:`).
  - `make_blacklist_key(jti)` helper → `auth:blacklist:{jti}`.
  - `service.py` 4 vị trí touch: refresh blacklist check (line ~168) + refresh write (line ~200) + logout access (line ~247) + logout refresh (line ~255).
  - `dependencies.py::get_current_user` 1 vị trí touch (line ~217).
  - TTL semantic giữ M2: `max(1, exp - now)` — auto-expire, KHÔNG cần cron cleanup.

- **SSO-04 E4 reinforced (D-V3-Phase3-E)** dependency mới trong `api/app/auth/dependencies.py`:
  - `get_current_user_for_hub_access` — Layer 3 defense-in-depth bên cạnh Layer 1 (Phase 1 DSN validator) + Layer 2 (M2 repo WHERE hub_id).
  - Central: bypass check (`hub_name == "central"` cross-hub by design).
  - Hub con: `settings.hub_name in claims.hub_ids` → return user; mismatch → `403 CROSS_HUB_ACCESS_DENIED` envelope.
  - Defensive `500 AUTH_STATE_MISSING` nếu `request.state.jwt_claims=None` (bug guard).

- **request.state.jwt_claims wire** ở `get_current_user`:
  - SAU 2 branch verify (central qua `verify_token` / hub con qua `verify_token_with_key`) converge → set state TRƯỚC blacklist check.
  - Cho phép `get_current_user_for_hub_access` read state KHÔNG re-decode JWT (pragmatic performance + cleanness).

- **19 unit test mới PASS:**
  - 9 test JWT iss/aud/hub_ids (Task 1): JWT_AUDIENCE constant + JWT_ISSUER unchanged + aud/hub_ids REQUIRED + 2 verify path strict + empty hub_ids OK + M2 cũ JWT reject.
  - 7 test Redis blacklist key (Task 2): prefix constant + helper format + UUID jti + logout key prefix + TTL semantic + TTL min 1s + get_current_user renamed key.
  - 4 test E4 dependency (Task 3 append vào test_get_current_user_jwks_branch.py): central bypass + hub_con reject cross-hub + accept matching + state missing 500.

- **3 integration test PASS critical+integration marker** (`test_sso_blacklist_cross_process.py`):
  - Stale JWT hub_ids=['duoc'] post tới hub yte → 403 CROSS_HUB_ACCESS_DENIED envelope (T-03-03-01 SSO-04).
  - Matching JWT hub_ids=['yte'] post tới hub yte → 200 (Layer 3 pass).
  - Central JWT hub_ids=['yte'] post tới central → 200 (bypass check cross-hub by design).
  - Override `get_current_user` qua `app.dependency_overrides` + middleware inject `request.state.jwt_claims` — cô lập test Layer 3 logic khỏi JWKS+DB+Redis chain.

- **Regression KHÔNG break:**
  - 257/257 unit test PASS (full suite — 61 Phase 3 plan 03-01/02/03 + 196 Phase 1/2/M2).
  - 16/16 integration critical+integration marker PASS (3 Plan 03-03 + 3 Plan 03-02 + 10 Phase 2).
  - 2 file test Rule 3 fix tự động: test_jwt.py + test_jwt_compat.py thêm `audience='medinet-wiki'` param vào `pyjwt.decode` raw (JWT mới có aud claim → strict mode require).
  - Lint clean (`ruff check app/auth/ + 4 test file` exit 0).
  - Type clean (`mypy --strict app/auth/` 10 source files exit 0).
  - Docker compose config render OK (KHÔNG đụng compose).

## Task Commits

| Task | Commit | Type | Description |
|------|--------|------|-------------|
| Task 1 RED | `e49aa3e` | test | 9 failing test JWT_AUDIENCE+aud/hub_ids REQUIRED claim |
| Task 1 GREEN | `705baa0` | feat | JWT_AUDIENCE constant + aud/hub_ids REQUIRED claim refactor + audience strict check 2 path + __init__.py re-export + Rule 3 regression fix test_jwt.py |
| Task 1 Rule 3 | `bae5f17` | test | test_jwt_compat audience param + aud claim assertion (Rule 3 regression integration test) |
| Task 2 RED | `08f5523` | test | 7 failing test Redis blacklist key schema rename |
| Task 2 GREEN | `2d913ac` | feat | _blacklist.py mini-module + service.py 4 vị trí refactor + dependencies.py 1 vị trí + __init__.py re-export |
| Task 3 | `a8b347e` | feat | get_current_user_for_hub_access dependency Layer 3 + wire request.state.jwt_claims + 4 unit test append |
| Task 4 | `0f96bf2` | test | 3 integration test SSO-02/03/04 E4 reinforced cross-hub JWT (override dependency + middleware pattern) |
| SUMMARY | (pending) | docs | This file |

## TDD Gate Compliance (Task 1 + Task 2)

| Task | Gate | Commit | Type | Status |
|------|------|--------|------|--------|
| Task 1 | RED  | `e49aa3e` | test | 7/9 fail (chưa impl JWT_AUDIENCE/aud/hub_ids REQUIRED) — gate đúng kỳ vọng |
| Task 1 | GREEN | `705baa0` | feat | 9/9 unit test PASS sau impl |
| Task 1 | REFACTOR | (skipped) | — | KHÔNG cần — code clean ngay sau GREEN |
| Task 2 | RED  | `08f5523` | test | 5/7 fail (chưa impl helper + rename) — gate đúng kỳ vọng |
| Task 2 | GREEN | `2d913ac` | feat | 7/7 unit test PASS sau impl |
| Task 2 | REFACTOR | (skipped) | — | KHÔNG cần — code clean ngay sau GREEN |

## Files Created/Modified

### Created (5)

- **`api/app/auth/_blacklist.py`** (39 LOC) — Mini-module `REDIS_BLACKLIST_PREFIX` constant + `make_blacklist_key(jti)` helper. Tránh circular import service↔dependencies (cả 2 cần access prefix).
- **`api/tests/unit/test_jwt_iss_aud_hub_ids.py`** (243 LOC) — 9 test: JWT_AUDIENCE constant + JWT_ISSUER unchanged + aud/hub_ids happy + 2 path strict audience + missing aud reject + wrong aud reject + missing hub_ids reject + empty hub_ids OK + verify_token_with_key missing aud reject.
- **`api/tests/unit/test_redis_blacklist_key_schema.py`** (181 LOC) — 7 test: prefix constant + helper format + UUID jti + logout key prefix + TTL semantic happy path + TTL min 1s expired guard + get_current_user renamed key.
- **`api/tests/integration/test_sso_blacklist_cross_process.py`** (265 LOC) — 3 critical+integration test: stale JWT 403 envelope + matching JWT accept 200 + central bypass 200.
- **`.planning/phases/03-auth-sso-hub-ids-jwt/03-03-SUMMARY.md`** (file này)

### Modified (5)

- **`api/app/auth/jwt.py`** (+85 LOC, 267 → 336): JWT_AUDIENCE constant + module docstring update Plan 03-03 scope + JWTClaims aud REQUIRED + hub_ids REQUIRED (xoá default) + issue_token_pair build aud + 2 verify path strict audience check (InvalidAudienceError + MissingRequiredClaimError mapped sang JWTError tiếng Việt).
- **`api/app/auth/dependencies.py`** (+78 LOC, 417 → 495): import make_blacklist_key + Redis key rename 1 vị trí get_current_user + wire request.state.jwt_claims SAU 2 branch converge + dependency mới get_current_user_for_hub_access (Layer 3 E4 enforce hub_ids check) + central bypass + defensive AUTH_STATE_MISSING 500.
- **`api/app/auth/service.py`** (+7 LOC, 283 → 290): import make_blacklist_key + 4 vị trí refactor f-string `blacklist:{jti}` → `make_blacklist_key(jti)`.
- **`api/app/auth/__init__.py`** (+6 LOC, 83 → 89): re-export JWT_AUDIENCE + REDIS_BLACKLIST_PREFIX + make_blacklist_key + get_current_user_for_hub_access (4 symbol mới).
- **`api/tests/unit/test_jwt.py`** (+15 LOC Rule 3): 2 test thêm `audience="medinet-wiki"` param vào `pyjwt.decode` raw + thêm `"aud"` vào required claim set (JWT mới có aud → pyjwt strict decode require audience param caller).
- **`api/tests/unit/test_get_current_user_jwks_branch.py`** (+118 LOC, 196 → 314 — Task 3 extend): 4 test mới append (central bypass + hub_con reject cross-hub + accept matching + state missing 500).
- **`api/tests/integration/test_jwt_compat.py`** (+9 LOC Rule 3): thêm audience param vào pyjwt.decode raw + assertion `decoded["aud"] == ["medinet-wiki"]`.

## Decisions Made

- **D-V3-Phase3-E consumed** (LOCKED 03-CONTEXT.md): JWT claim shape aud REQUIRED + hub_ids REQUIRED + iss RE-CONFIRM giữ `"medinet-wiki"` (KHÔNG URL-based, defer Phase 7 MCP MIGRATE-04 split audience `medinet-wiki-mcp`). PyJWT decode strict audience check 2 path (`verify_token` + `verify_token_with_key`) — InvalidAudienceError + MissingRequiredClaimError raise → JWTError tiếng Việt với hint user re-login.

- **D-V3-Phase3-H consumed** (LOCKED 03-CONTEXT.md): Redis blacklist key schema `auth:blacklist:{jti}` + TTL=`max(1, exp-now)` + value `"1"` marker. Tạo `_blacklist.py` mini-module để tránh circular import giữa `service.py` + `dependencies.py` — cả 2 cùng cần access constant + helper format.

- **SSO-04 E4 reinforced** (LOCKED REQUIREMENTS.md line 50): 3-layer defense-in-depth enforce hub isolation:
  - Layer 1 (Phase 1 Plan 01-02): DB-level `_enforce_hub_dsn_match` validator boot-time fail-fast.
  - Layer 2 (M2 carry forward): repository `WHERE hub_id = settings.hub_name` query-time filter.
  - Layer 3 (Plan 03-03 MỚI): dependency `get_current_user_for_hub_access` JWT claim hub_ids check → 403 CROSS_HUB_ACCESS_DENIED envelope nếu mismatch.

- **request.state.jwt_claims pattern** (Plan 03-03 Task 3 wiring): `get_current_user` set state SAU 2 branch converge (central qua `verify_token` / hub con qua `verify_token_with_key` cùng converge ở step `request.state.jwt_claims = claims`). `get_current_user_for_hub_access` read state KHÔNG re-decode — pragmatic performance + cleanness. Defensive 500 AUTH_STATE_MISSING guard phát hiện sớm bug dep chain broken thay vì silent bypass authorization.

- **Test override pattern** (Plan 03-03 Task 4): `app.dependency_overrides[get_current_user] = mock` + `@app.middleware("http")` inject state. Cô lập test logic Layer 3 khỏi JWKS+DB+Redis chain phức tạp (KHÔNG cần testcontainers Postgres/Redis cho integration test E4). Full multi-process docker compose smoke defer Plan 03-05 closeout.

- **iss URL-based defer Phase 7** (RE-CONFIRM D-V3-Phase3-E): gốc đề xuất `iss='https://central/'` URL-based — analysis cho thấy:
  - Chuỗi cố định `medinet-wiki` đủ cho v3.0-a (aud claim đã phân biệt service).
  - URL-based thêm complexity (Settings field central_url + dynamic build) mà KHÔNG add value cho v3.0-a.
  - M2 baseline `iss="medinet-wiki"` đã ship → đổi iss = thêm 1 backward incompat (đã có aud+hub_ids+kid reject ở Plan 03-02/03).
  - URL-based defer Phase 7 MIGRATE-04 khi MCP service formal split audience `medinet-wiki-mcp` — lúc đó iss URL-based + multi-aud có ý nghĩa.

- **KHÔNG đụng `lock:refresh:` key** (P16 SETNX lock M2 — KHÔNG related blacklist) + **KHÔNG đụng `service.py::login`** (KHÔNG ghi blacklist — chỉ refresh + logout ghi) — minimal touch surface.

- **KHÔNG đụng router.py** (Plan 03-04 sẽ refactor 307 redirect login/refresh hub con → central — defer Wave 4).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] M2 test_jwt.py + test_jwt_compat.py raw `pyjwt.decode` thiếu audience param**

- **Found during:** Task 1 GREEN gate verify run pytest tests/unit/test_jwt.py
- **Issue:** Plan 03-03 Task 1 add `aud` claim vào JWT mới issued. M2 test 2 chỗ (`test_issue_token_pair_returns_valid_rs256` + `test_jwt_claims_shape_matches_spec` ở test_jwt.py + 1 chỗ `test_jwt_login_format` ở test_jwt_compat.py) dùng `pyjwt.decode(..., issuer="medinet-wiki")` KHÔNG truyền audience param → pyjwt strict mode default `audience=None` + payload có aud → `InvalidAudienceError: Invalid audience`.
- **Fix:** Thêm `audience="medinet-wiki"` param vào 3 `pyjwt.decode` raw call + thêm `"aud"` vào required claim set + assertion `decoded["aud"] == ["medinet-wiki"]`. Semantic test KHÔNG đổi — chỉ thêm audience matching new contract.
- **Files modified:** `tests/unit/test_jwt.py`, `tests/integration/test_jwt_compat.py`.
- **Commits:** `705baa0` (test_jwt.py cùng Task 1 GREEN), `bae5f17` (test_jwt_compat.py).

**2. [Rule 3 - Blocking] Integration test override pattern KHÔNG hoạt động với function dependency `request: Request` param**

- **Found during:** Task 4 verify run pytest tests/integration/test_sso_blacklist_cross_process.py
- **Issue:** Lần thử đầu override `get_current_user` với async function `_mock_get_current_user(request: Request)`. FastAPI dependency override KHÔNG inherit signature từ original function → resolve `request` parameter như query param → 422 "Field required: query.request". Re-try với `fastapi.Request` vs `starlette.requests.Request` import KHÔNG khắc phục.
- **Fix:** Tách logic: (a) override `get_current_user` thành function KHÔNG có `request: Request` param (chỉ return mock user); (b) wire `request.state.jwt_claims` qua `@app.middleware("http")` decorator. Middleware chạy TRƯỚC mọi dependency resolve → state đã có sẵn khi `get_current_user_for_hub_access` read.
- **Files modified:** `tests/integration/test_sso_blacklist_cross_process.py` helper `_make_test_endpoint_app`.
- **Commit:** `0f96bf2` (cùng Task 4).
- **Trade-off:** Middleware-based state inject HƠI khác với production path (production set state qua `get_current_user` dependency SAU verify). Test verify behavior Layer 3 dependency, KHÔNG verify state-set timing — acceptable cho integration scope. Full multi-process docker compose smoke ở Plan 03-05 sẽ verify production path real.

**3. [Rule 1 - Lint] mypy `untyped-decorator` cho `@app.middleware("http")`**

- **Found during:** Task 4 mypy check
- **Issue:** FastAPI `app.middleware("http")` decorator untyped trong stub → mypy `--strict` raise error.
- **Fix:** Thêm `# type: ignore[untyped-decorator]` comment với error code cụ thể (`[misc]` initial guess WRONG).
- **Files modified:** `tests/integration/test_sso_blacklist_cross_process.py` line 126.
- **Commit:** `0f96bf2` (cùng Task 4).

**Total deviations: 3 (2 Rule 3 blocking + 1 Rule 1 lint)** — KHÔNG Rule 4 architectural (scope ràng buộc D-V3-Phase3-E/H LOCKED).

**Impact on plan:** Plan executed đúng intent (D-V3-Phase3-E/H consumed + 19 test mới + 257 unit regression PASS); 3 deviation đều downstream của claim shape mới + FastAPI override pattern caveat + ruff lint convention — KHÔNG thay đổi architectural decision hoặc API contract.

## Authentication Gates

None - Plan 03-03 ship verify path mới (claim shape + Redis key + E4 dependency). KHÔNG cần auth qua provider ngoài. Integration test dùng `api/keys/{private,public}.pem` M2 baseline đã ship + mock user qua override dependency.

## Issues Encountered

- 2 M2 test (test_jwt.py + test_jwt_compat.py) regress sau Task 1 thêm aud claim (Rule 3 #1) — auto-fix update audience param + aud assertion, regression PASS.
- FastAPI dependency override với `request: Request` param không inherit signature (Rule 3 #2) — auto-fix pivot sang middleware-based state inject, 3 integration test PASS.
- mypy strict untyped-decorator (Rule 1 #3) — auto-fix `# type: ignore[untyped-decorator]`.

## Verification Results

### Lint + Type

| Tool | Files | Result |
|------|-------|--------|
| `ruff check` | `app/auth/_blacklist.py app/auth/jwt.py app/auth/dependencies.py app/auth/service.py app/auth/__init__.py tests/unit/test_jwt_iss_aud_hub_ids.py tests/unit/test_redis_blacklist_key_schema.py tests/unit/test_get_current_user_jwks_branch.py tests/integration/test_sso_blacklist_cross_process.py` | All checks passed |
| `mypy --strict` | `app/auth/` (10 source files) | Success: no issues |
| `mypy --strict` | `tests/integration/test_sso_blacklist_cross_process.py` | Success: no issues |

### Unit Tests (Plan 03-03 new + regression)

| Suite | Tests | PASS | Time |
|-------|-------|------|------|
| `test_jwt_iss_aud_hub_ids.py` (Plan 03-03 mới Task 1) | 9 | 9/9 (100%) | bao gồm |
| `test_redis_blacklist_key_schema.py` (Plan 03-03 mới Task 2) | 7 | 7/7 (100%) | bao gồm |
| `test_get_current_user_jwks_branch.py` (Plan 03-02 4 + Plan 03-03 Task 3 append 4) | 8 | 8/8 (100%) | bao gồm |
| `test_jwt.py` (M2 baseline regression sau Rule 3 fix) | 8 | 8/8 (100%) | bao gồm |
| `test_jwks_publish.py` (Plan 03-01 regression) | 9 | 9/9 (100%) | bao gồm |
| `test_jwks_cache.py` (Plan 03-02 regression) | 9 | 9/9 (100%) | bao gồm |
| `test_config_jwks.py` (Plan 03-02 regression) | 11 | 11/11 (100%) | bao gồm |
| **Full unit suite** | **257** | **257/257 (100%)** | **37.42s** |

### Integration Tests

| Suite | Tests | PASS | Time |
|-------|-------|------|------|
| `test_sso_blacklist_cross_process.py` (Plan 03-03 mới Task 4 — critical+integration) | 3 | 3/3 (100%) | bao gồm |
| `test_jwks_cache_lifecycle.py` (Plan 03-02 regression — critical+integration) | 3 | 3/3 (100%) | bao gồm |
| `test_factor_hub_scoped.py` (Phase 2 regression — critical+integration) | 10 | 10/10 (100%) | bao gồm |
| **Tổng integration critical+integration marker** | **16** | **16/16 (100%)** | **9.82s** |

### Docker Compose

```bash
cd Hub_All && docker compose config --quiet
# exit=0 — base render OK (Plan 03-03 KHÔNG đụng compose)
```

## E4 Reinforced Dependency Chain Sample (test_sso_blacklist_cross_process.py Task 4)

`test_stale_jwt_cross_hub_returns_403_envelope` integration sample:

```python
# Setup: hub yte app + stale JWT hub_ids=["duoc"]
stale_token = _build_jwt(private_pem, public_pem, hub_ids=["duoc"])
yte_app = hub_app_factory("yte")
stale_claims = MagicMock()
stale_claims.hub_ids = ["duoc"]  # cross-hub forge scenario
_make_test_endpoint_app(yte_app, jwt_claims=stale_claims)

# Test request → dependency chain:
# 1. Middleware inject request.state.jwt_claims = stale_claims (mock)
# 2. get_current_user override → mock user (bypass JWKS+DB verify)
# 3. get_current_user_for_hub_access:
#    - settings.hub_name = "yte"
#    - claims.hub_ids = ["duoc"]
#    - "yte" NOT IN ["duoc"] → raise HTTPException 403 CROSS_HUB_ACCESS_DENIED
# 4. ErrorHandlerMiddleware wrap → envelope D6 shape
#    {"success": false, "data": null,
#     "error": {"code": "CROSS_HUB_ACCESS_DENIED",
#               "message": "Token KHÔNG có quyền truy cập hub 'yte' (hub_ids JWT = ['duoc'])"},
#     "meta": null}

resp = client.get("/api/test/hub-access", headers={"Authorization": f"Bearer {stale_token}"})
assert resp.status_code == 403
assert resp.json()["error"]["code"] == "CROSS_HUB_ACCESS_DENIED"
assert "yte" in resp.json()["error"]["message"]
```

Pattern này verify Layer 3 enforce đúng spec — 403 envelope KHÔNG 404 leak / 500 error / 200 data leak.

## Threat Model Results (8 STRIDE threat từ Plan 03-03)

| Threat ID | Category | Severity | Disposition | Status |
|-----------|----------|----------|-------------|--------|
| **T-03-03-01** | Spoofing (Stale JWT hub_ids=["duoc"] forge bởi attacker compromise user duoc → post tới hub yte) | high | mitigate | ✓ MITIGATED — Layer 3 `get_current_user_for_hub_access` enforce `settings.hub_name in claims.hub_ids` → 403 CROSS_HUB_ACCESS_DENIED envelope. Integration test `test_stale_jwt_cross_hub_returns_403_envelope` verify (D6 shape KHÔNG 404 leak / 500 error). Layer 1 DSN validator + Layer 2 repo WHERE = defense-in-depth. |
| **T-03-03-02** | Tampering (Attacker thay JWT aud claim từ ["medinet-wiki"] → ["wrong-service"]) | high | mitigate | ✓ MITIGATED — PyJWT decode strict `audience=JWT_AUDIENCE` raise InvalidAudienceError. Test `test_jwt_wrong_aud_rejects` verify. Sign valid bằng public key central — KHÔNG forge được aud + giữ signature valid. |
| **T-03-03-03** | Information Disclosure (Logout central → Redis blacklist key visible cross-tenant nếu Redis shared với other services) | low | mitigate | ✓ MITIGATED — Key prefix `auth:blacklist:` namespace clarity. Redis instance dedicated medinet-wiki M2. Future MCP/other services dùng prefix khác (vd `mcp:blacklist:`). |
| **T-03-03-04** | Repudiation (Logout race condition — user logout đồng thời với refresh → 2 jti khác nhau, audit miss) | low | accept | ✓ ACCEPTED — Audit logger M2 ghi mọi auth event qua background task — race window < 100ms acceptable. Plan 10 v2.0 audit pipeline carry forward. |
| **T-03-03-05** | DoS (Redis instance xuống → blacklist check silent skip → revoked JWT vẫn pass verify) | medium | accept | ✓ ACCEPTED — M2 fail-open carry forward (defer Redis HA cluster Phase 7). Acceptable risk: rare Redis downtime + short window (15min access token expire). Defense: refresh token rotation 7d. |
| **T-03-03-06** | Elevation of Privilege (M2 cũ JWT thiếu aud/hub_ids → post Plan 03-03 deploy bypass nếu validator/decode silently default) | high | mitigate | ✓ MITIGATED — PyJWT decode `audience` mandatory check raise InvalidAudienceError nếu thiếu. JWTClaims hub_ids REQUIRED (Pydantic ValidationError). Task 1 9 test verify (M2 cũ JWT reject). |
| **T-03-03-07** | Tampering (Operator manually flush Redis `FLUSHDB` → mọi blacklist key xoá → revoked JWT pass verify trong window TTL) | low | accept | ✓ ACCEPTED — Ops-level action — KHÔNG attack vector external. Defense: audit log ghi flush event qua Redis ACL log (defer Phase 7 ACL hardening). |
| **T-03-03-08** | Information Disclosure (`request.state.jwt_claims` JWTClaims chứa email + role → exposed qua FastAPI debug mode) | low | accept | ✓ ACCEPTED — `request.state` accessible only ở dependency chain — KHÔNG render ra response body. Debug mode chỉ dev/staging (P12 mitigation). |

**Tổng:** 8/8 threat addressed (4 accept + 4 mitigate, KHÔNG transfer/avoid/defer). KHÔNG ship threat mới phát sinh.

## Threat Flags

(scan files modified — không có surface mới ngoài threat_model đã liệt kê)

None - new surface area khớp 100% threat_model Plan 03-03.

## Self-Check

### Created Files Exist

| File | Status |
|------|--------|
| `Hub_All/api/app/auth/_blacklist.py` | FOUND |
| `Hub_All/api/tests/unit/test_jwt_iss_aud_hub_ids.py` | FOUND |
| `Hub_All/api/tests/unit/test_redis_blacklist_key_schema.py` | FOUND |
| `Hub_All/api/tests/integration/test_sso_blacklist_cross_process.py` | FOUND |
| `Hub_All/.planning/phases/03-auth-sso-hub-ids-jwt/03-03-SUMMARY.md` | FOUND (file này) |

### Modified Files Verified (grep evidence)

| File | Verify | Status |
|------|--------|--------|
| `api/app/auth/jwt.py` | grep `JWT_AUDIENCE\s*=\s*.medinet-wiki.` ≥ 1 | OK |
| `api/app/auth/jwt.py` | grep `audience=JWT_AUDIENCE` ≥ 2 (verify_token + verify_token_with_key) | OK |
| `api/app/auth/jwt.py` | grep `aud: list\[str\]` ≥ 1 (REQUIRED) | OK |
| `api/app/auth/_blacklist.py` | grep `REDIS_BLACKLIST_PREFIX\s*=\s*.auth:blacklist:.` ≥ 1 | OK |
| `api/app/auth/_blacklist.py` | grep `def make_blacklist_key` ≥ 1 | OK |
| `api/app/auth/service.py` | grep `make_blacklist_key` ≥ 4 (4 vị trí touch) | OK |
| `api/app/auth/dependencies.py` | grep `make_blacklist_key` ≥ 1 | OK |
| `api/app/auth/dependencies.py` | grep `def get_current_user_for_hub_access` ≥ 1 | OK |
| `api/app/auth/dependencies.py` | grep `request\.state\.jwt_claims` ≥ 2 (set + read) | OK |
| `api/app/auth/dependencies.py` | grep `CROSS_HUB_ACCESS_DENIED\|AUTH_STATE_MISSING` ≥ 2 | OK |
| `api/app/auth/__init__.py` | grep `JWT_AUDIENCE` ≥ 1 (re-export) | OK |
| `api/app/auth/__init__.py` | grep `make_blacklist_key\|REDIS_BLACKLIST_PREFIX` ≥ 2 (re-export) | OK |
| `api/app/auth/__init__.py` | grep `get_current_user_for_hub_access` ≥ 1 (re-export) | OK |

### Commits Exist (git log --oneline)

| Commit | Verify | Status |
|--------|--------|--------|
| `e49aa3e` test(03-03) Task 1 RED | `git log \| grep e49aa3e` | FOUND |
| `705baa0` feat(03-03) Task 1 GREEN | `git log \| grep 705baa0` | FOUND |
| `bae5f17` test(03-03) Rule 3 fix | `git log \| grep bae5f17` | FOUND |
| `08f5523` test(03-03) Task 2 RED | `git log \| grep 08f5523` | FOUND |
| `2d913ac` feat(03-03) Task 2 GREEN | `git log \| grep 2d913ac` | FOUND |
| `a8b347e` feat(03-03) Task 3 | `git log \| grep a8b347e` | FOUND |
| `0f96bf2` test(03-03) Task 4 | `git log \| grep 0f96bf2` | FOUND |

## Self-Check: PASSED

## Next Phase Readiness

### Plan 03-04 (Wave 4 — UNBLOCKED) — Hub con auth router 307 redirect login/refresh

- ✅ JWT claim shape mới (aud + hub_ids REQUIRED) + service.py shape mới (Redis key rename) đã ship — Plan 03-04 router refactor KHÔNG đụng service.py internal, chỉ thêm conditional return 307 ở `auth_router.post("/login")` + `/refresh` hub con.
- ✅ Settings validator pattern carry forward (Plan 03-02 `_enforce_central_jwks_url_for_hub`) — Plan 03-04 có thể thêm field `central_url` cho hub con redirect target với pattern tương tự.
- 📋 Plan 03-04 ship: hub con login/refresh trả 307 Location: `{settings.central_url}/api/auth/{login,refresh}` (browser auto-follow) + update Phase 2 endpoint matrix test `test_factor_hub_scoped` assert 307 thay vì 200/401/422 cho 2 endpoint.

### Plan 03-05 (Wave 5 closeout) — Phase 3 closeout smoke + docs

- Depends Plan 03-02 + 03-03 + 03-04 — defer sau Wave 2/3/4 close
- 📋 Smoke 2 service compose runtime (central + yte) real: boot central + yte → fetch JWKS thật → JWT issue có aud + hub_ids → verify cross-process PASS. Verify Redis blacklist `auth:blacklist:` propagate < 1s.
- 📋 README backward incompat DOUBLE banner — communicate operator:
  - kid header missing reject (Plan 03-02 hub con only).
  - aud claim missing + hub_ids missing reject (Plan 03-03 central + hub con).
  - Combine: M2 cũ JWT post-Plan 03-03 deploy KHÔNG dùng được, user re-login (~15-30s downtime acceptable).

### v3.0-a EXIT GATE (giữa Phase 3-4)

- 🚦 Demo 1 hub con (yte) + central + JWT SSO + golden path PASS → user accept là điều kiện tiếp tục v3.0-b (Phase 4-7)
- Plan 03-03 đóng góp 3/5 plan Phase 3 (Plan 03-01 + 03-02 + 03-03 = 60% Phase 3 close); 2 plan còn lại (03-04 router redirect + 03-05 closeout) sẽ unblock theo wave.

---

*Phase: 03-auth-sso-hub-ids-jwt*
*Plan: 03 (SSO-02/03/04 — Wave 3 BLOCKED 03-02)*
*Completed: 2026-05-22*
*Test result: 19/19 unit mới PASS (9+7+4) + 3/3 integration mới PASS + 257/257 unit regression PASS + 16/16 integration critical+integration regression PASS — KHÔNG break*
