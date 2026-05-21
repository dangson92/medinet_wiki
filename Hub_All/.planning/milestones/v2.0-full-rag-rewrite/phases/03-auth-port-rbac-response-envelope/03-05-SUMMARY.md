---
phase: 3
plan: 05
subsystem: api/app/auth + api/app/main + api/tests/integration + api/tests/unit
tags: [rbac, require-role, integration-test, testcontainers, postgres, redis, asyncio-gather, p16-setnx, ac1-ac2-ac3-ac4-ac5, auth-04, jwt-decode, pkcs8, pii-log, wave4]
requires: [03-01, 03-02, 03-03, 03-04]
provides: [require-role-rbac-dep, http-exception-envelope-handler, integration-test-suite-5-ac, redis-container-fixture, seeded-users-fixture]
affects: [04-cocoindex-mvp, 05-crud-hub-user]
tech-stack:
  added: [testcontainers-redis, asgi-lifespan, httpx-asgi-transport, asyncio-to-thread-alembic, fastapi-exception-handler]
  patterns: [http-exception-envelope-mapper, test-only-router-mount-via-fixture, truncate-cascade-per-test, asyncio-gather-concurrent-race-trigger, asyncio-to-thread-alembic-migration, env-override-in-fixture-not-alembic, pyjwt-raw-decode-cross-process]
key-files:
  created:
    - Hub_All/api/tests/unit/test_require_role.py
    - Hub_All/api/tests/integration/test_auth_login.py
    - Hub_All/api/tests/integration/test_auth_refresh_race.py
    - Hub_All/api/tests/integration/test_rbac_dependency.py
    - Hub_All/api/tests/integration/test_jwt_compat.py
  modified:
    - Hub_All/api/app/auth/dependencies.py
    - Hub_All/api/app/main.py
    - Hub_All/api/tests/integration/conftest.py
    - Hub_All/api/pyproject.toml
    - Hub_All/api/uv.lock
    - Hub_All/api/scripts/verify_jwt_format.sh
decisions:
  - "require_role(*roles) factory: raise ValueError ngay khi gọi không argument (security gate — tránh route mở cho mọi role). Trả Callable inject `user = Depends(get_current_user)` rồi check `user.role in allowed` → return user. Fail → raise HTTPException 403 detail={code:FORBIDDEN, message:...}."
  - "HTTPException → envelope handler bake trong app/main.py create_app(): map exc.detail dict {code, message} → envelope shape `{success:false, data:null, error:{code, message}, meta:null}`. ErrorHandlerMiddleware Plan 03-01 pass-through StarletteHTTPException → handler này render envelope đúng cho mọi 401/403 từ dependencies."
  - "Test-only RBAC route `/test/role-check` mount qua fixture `_spawn_rbac_app()` — KHÔNG sửa production app/main.py. AC3 verify dependency contract qua test route, integration với production endpoint defer Phase 5 HUB-02 (PUT /api/hubs/:id chưa tồn tại)."
  - "TRUNCATE per-test isolation: postgres_container scope=module → data leak. Mỗi test app_with_auth fixture truncate users/refresh_tokens/user_hubs CASCADE qua sync engine TRƯỚC lifespan init (init_engine chưa chạy). Avoid duplicate-key violation khi seed admin/editor/viewer 3 user cùng plaintext."
  - "alembic command.upgrade qua asyncio.to_thread: env.py dùng asyncio.run() → call từ async fixture raise 'asyncio.run() cannot be called from a running event loop'. Wrap qua to_thread() → thread mới có event loop riêng cho alembic async migration."
  - "Env vars override IN app_with_auth fixture (KHÔNG ở auth_env riêng): alembic_cfg fixture set REDIS_URL=localhost (Phase 2 placeholder, alembic không cần Redis). Pytest fixture order không guarantee auth_env chạy SAU alembic_cfg → app lifespan đôi khi đọc REDIS_URL=localhost. Fix: chuyển env override vào app_with_auth trực tiếp với postgres+redis containers làm depend → đảm bảo set CUỐI CÙNG trước create_app + cache_clear."
  - "asyncio.gather(5 refresh calls) verify Redis SETNX atomic lock chống race: chỉ 1 task thắng lock:refresh:<jti>, 4 task còn lại nhận REFRESH_RACE 401. ASGITransport in-process KHÔNG có true parallel nhưng concurrent đủ trigger race condition trên Redis SETNX critical section."
  - "PII log regression: caplog scan messages KHÔNG chứa plain 'Admin@123' password + KHÔNG match regex eyJ[A-Za-z0-9._-]{20,} JWT base64. Plan 03-04 logger.info chỉ log user_id + role + email_present bool — verify."
metrics:
  duration_minutes: 25
  completed_date: "2026-05-14"
  tasks_total: 6
  tasks_completed: 6
  files_created: 5
  files_modified: 6
  commits: 6
  tests_total_phase3_plan05: 27
  tests_passed_phase3_plan05: 27
  tests_total_baseline: 62
  tests_passed_baseline: 62
  critical_tests_total: 29
  critical_tests_passed: 29
---

# Phase 3 Plan 05: RBAC `require_role` + 5-AC Integration Test Suite — Summary

**Wave 4 — verification gate cho Phase 3:** Implement `require_role(*roles)` dependency đầy đủ (AUTH-04 hoàn tất) + viết integration test suite verify **TẤT CẢ 5 ROADMAP success criteria** trên Postgres + Redis testcontainers thật. 27 test mới PASS (5 unit + 22 integration), 62/62 full suite no regression, 29 critical-marker test PASS cho HARD-03 CI gate. Phase 3 hoàn tất — sẵn sàng Phase 4 (CocoIndex Flow MVP).

---

## Mục tiêu (Objective)

Plan 03-05 thuộc Wave 4 của Phase 3 — sản xuất hợp đồng RBAC + verification toàn bộ auth flow end-to-end:

1. **AUTH-04 hoàn tất** — `require_role(*roles)` factory dependency: ValueError gate empty roles + check `user.role in allowed` → raise HTTPException 403 `FORBIDDEN`.
2. **HTTPException → envelope handler** — Plan 03-01 ErrorHandlerMiddleware đã pass-through HTTPException; Plan 03-05 thêm `@app.exception_handler(HTTPException)` map sang envelope shape `{success, data, error, meta}` cho mọi 401/403 từ `get_current_user` + `require_role`.
3. **5 ROADMAP success criteria verified end-to-end** trên Postgres + Redis testcontainers thật:
   - AC1 — login envelope shape byte-identical Go.
   - AC2 — JWT FastAPI decode được + PKCS#8 format.
   - AC3 — RBAC 403/200 cho viewer/editor/admin.
   - AC4 — Argon2 cross-compat (regression check chạy lại Plan 03-03 test).
   - AC5 — Concurrent refresh race 5 asyncio.gather → 1 PASS + 4 fail.

---

## Tasks hoàn thành (6/6)

| # | Task | Commit | Status |
|---|------|--------|--------|
| 01 | `require_role(*roles)` đầy đủ trong `dependencies.py` (replace stub NotImplementedError) + `@app.exception_handler(HTTPException)` map envelope trong `main.py` + 5 unit test ValueError gate | `010c8a1` | PASS (5/5 unit) |
| 02 | Extend `tests/integration/conftest.py` với 10 fixture Plan 03-05 (redis_container, app_with_auth, auth_client, 3 seeded user, 3 token, admin_token_pair) + bump pyproject `testcontainers[postgres,redis]` | `29d4edf` | PASS (fixture infrastructure ready) |
| 03 | `tests/integration/test_auth_login.py` — 5 critical test AC1 (happy admin / wrong password / unknown email anti-timing / bad email format 422 / envelope shape) | `a01b7d1` | PASS (5/5) |
| 04 | `tests/integration/test_auth_refresh_race.py` — 5 critical test AC5 (happy refresh / concurrent 5 only-one-wins / revoked replay / garbage JWT / access_token wrong type) | `41b8d5c` | PASS (5/5) |
| 05 | `tests/integration/test_rbac_dependency.py` — 6 critical test AC3 (anonymous 401 / viewer 403 / editor 403 / admin 200 / multi-role admin pass / multi-role viewer rejected) | `0f1fdc6` | PASS (6/6) |
| 06 | `tests/integration/test_jwt_compat.py` — 5 critical test AC2 + AUTH-06 (decode public key / /me / logout blacklist / PKCS#8 script verify / PII log no leak) + fix script CRLF Windows | `6e178e4` | PASS (5/5) |

---

## Files thay đổi (11 file)

### Created (5)

- `Hub_All/api/tests/unit/test_require_role.py` — 5 unit test pure Python (KHÔNG cần Postgres/Redis): ValueError empty roles / Callable single / Callable multi / Callable 3-role / closure isolation.
- `Hub_All/api/tests/integration/test_auth_login.py` — 5 integration test AC1 envelope shape + anti-timing oracle.
- `Hub_All/api/tests/integration/test_auth_refresh_race.py` — 5 integration test AC5 P16 SETNX atomic lock với asyncio.gather concurrent 5.
- `Hub_All/api/tests/integration/test_rbac_dependency.py` — 6 integration test AC3 require_role dependency contract.
- `Hub_All/api/tests/integration/test_jwt_compat.py` — 5 integration test AC2 JWT decode + /me + logout blacklist + PKCS#8 script + PII log regression.

### Modified (6)

- `Hub_All/api/app/auth/dependencies.py` — replace `require_role` stub NotImplementedError → implementation đầy đủ (ValueError gate empty roles + allowed set check + HTTPException 403 FORBIDDEN).
- `Hub_All/api/app/main.py` — thêm `@app.exception_handler(HTTPException)` trong `create_app()` map exc.detail dict {code, message} → envelope `{success:false, error:{code, message}}`.
- `Hub_All/api/tests/integration/conftest.py` — extend với 10 fixture: redis_container (scope=module), auth_env (set env vars — legacy không dùng nữa, giữ backward-compat), app_with_auth (alembic upgrade head + truncate cascade + lifespan), auth_client (httpx ASGITransport), 3 seeded user (admin/editor/viewer cùng plaintext "Admin@123"), 3 token, admin_token_pair.
- `Hub_All/api/pyproject.toml` — bump `testcontainers[postgres]` → `testcontainers[postgres,redis]`.
- `Hub_All/api/uv.lock` — auto-update sau uv sync.
- `Hub_All/api/scripts/verify_jwt_format.sh` — Rule 1 fix: strip `\r` ở HEADER (Windows CRLF line ending) trước case match. `head -1 "$KEY" | tr -d '\r'`.

---

## Acceptance Criteria — verification suite

| Check | Command | Kết quả |
|-------|---------|---------|
| All 6 task PASS | git log --oneline | 6 commits atomic |
| `require_role` implementation | `grep -c 'allowed = set(roles)' app/auth/dependencies.py` | 1 |
| `require_role` 403 FORBIDDEN | `grep -c '"code": "FORBIDDEN"' app/auth/dependencies.py` | 1 |
| `require_role` stub removed | `grep -c 'raise NotImplementedError' app/auth/dependencies.py` | 0 |
| HTTPException handler | `grep -c '@app.exception_handler(HTTPException)' app/main.py` | 1 |
| Envelope shape mapper | `grep -c '"success": False' app/main.py` | 1 |
| Unit test require_role | `pytest tests/unit/test_require_role.py -v` | **5/5 PASS** |
| Integration test login | `pytest tests/integration/test_auth_login.py -v` | **5/5 PASS** |
| Integration test refresh race | `pytest tests/integration/test_auth_refresh_race.py -v` | **5/5 PASS** |
| Integration test RBAC | `pytest tests/integration/test_rbac_dependency.py -v` | **6/6 PASS** |
| Integration test JWT compat | `pytest tests/integration/test_jwt_compat.py -v` | **5/5 PASS** |
| Full pytest suite | `uv run pytest tests/ -v` | **62/62 PASS** (27 cũ + 27 mới + 8 Phase 1-2 middleware/main) |
| Critical-marker suite | `uv run pytest -m critical -v` | **29 PASS, 33 deselected** (HARD-03 CI gate) |
| AUTH-04 exports | `python -c "from app.auth import require_role, get_current_user, auth_router; print('OK')"` | exit 0, `AUTH-04 exports OK` |
| ruff app + tests | `uv run ruff check app tests` | All checks passed |
| mypy strict | `uv run mypy app` | Success: no issues found in 29 source files |
| verify_jwt_format.sh | `bash scripts/verify_jwt_format.sh` | exit 0, "PKCS#8 OK (keys/private.pem)" + 4096-bit |

**Tổng:** 17 acceptance check 17/17 PASS.

---

## ROADMAP Success Criteria — verified end-to-end

| AC | Test | File | Status |
|----|------|------|--------|
| **AC1** | Login envelope shape byte-identical Go | `test_auth_login.py::test_login_happy_admin_returns_envelope` + `test_login_envelope_shape_byte_identical_go` | **PASS** — envelope keys EXACTLY `{success, data, error, meta}`, không dư extra. User dict đầy đủ id/email/full_name/role/hub_assignments. |
| **AC2** | JWT FastAPI decode + PKCS#8 format | `test_jwt_compat.py::test_login_token_decodable_with_public_key` + `test_pkcs8_key_format_verified` | **PASS** — pyjwt.decode access_token với keys/public.pem RS256 → 10 claim spec (sub/email/role/hub_ids/iss=medinet-wiki/iat/exp/jti/token_type=access/name). scripts/verify_jwt_format.sh exit 0 "PKCS#8 OK" 4096-bit. |
| **AC3** | RBAC 403/200 cho viewer/editor/admin | `test_rbac_dependency.py` 6 test | **PASS** — anonymous 401 MISSING_AUTHORIZATION, viewer/editor → require_role('admin') → 403 FORBIDDEN, admin → 200, multi-role (admin OR editor) admin PASS + viewer REJECT 403. |
| **AC4** | Argon2 cross-compat | `tests/integration/test_argon2_cross_compat.py` (Plan 03-03 — chạy lại) | **PASS (regression)** — 4/4 critical test cross-compat Go seed hash production: pwdlib verify `Admin@123` đối với `$argon2id$v=19$m=65536,t=3,p=4$...` → True. KHÔNG regress sau Plan 03-04 + Plan 03-05. |
| **AC5** | Concurrent refresh race 5→1 PASS | `test_auth_refresh_race.py::test_refresh_concurrent_5_only_one_wins` | **PASS** — asyncio.gather(5 calls) cùng refresh_token → exactly 1 status 200 + 4 status 401 (REFRESH_RACE/TOKEN_REVOKED/INVALID_REFRESH_TOKEN). P16 SETNX `lock:refresh:<jti>` atomic mitigation verified. |

**5/5 ROADMAP success criteria VERIFIED end-to-end** — Phase 3 hoàn tất.

---

## Deviations from Plan

### Auto-fixed Issues (Rule 1 + Rule 3)

**1. [Rule 3 - Blocking] alembic.command.upgrade trong async fixture raise 'asyncio.run() cannot be called from a running event loop'**

- **Found during:** Task 03 initial run — `app_with_auth` fixture gọi `command.upgrade(alembic_cfg, "head")` trực tiếp. `migrations/env.py` line 105: `def run_migrations_online(): asyncio.run(run_async_migrations())`. asyncio.run() reject khi đã trong event loop (async fixture).
- **Fix:** Wrap `command.upgrade` qua `await asyncio.to_thread(command.upgrade, alembic_cfg, "head")` → thread mới tạo event loop riêng. Add `import asyncio` vào conftest.
- **Files modified:** `tests/integration/conftest.py`
- **Commit:** `a01b7d1` (gộp Task 03 với Rule 1 + Rule 3 fix bên dưới)

**2. [Rule 1 - Bug] postgres_container scope=module → data leak giữa tests trong cùng module → duplicate-key violation**

- **Found during:** Task 03 — test thứ 2 trong file fail `IntegrityError: duplicate key value violates unique constraint "uq_users_email"` vì `admin_user` fixture INSERT cùng email vào DB persistent.
- **Issue:** Phase 2 `postgres_container` fixture scope=module → tất cả test trong cùng module share container. Plan 03-05 cần fresh state mỗi test vì seed cùng email 3 user.
- **Fix:** Thêm `TRUNCATE TABLE users, refresh_tokens, user_hubs RESTART IDENTITY CASCADE` qua sync engine trong `app_with_auth` fixture TRƯỚC `init_engine` (lifespan chưa chạy). Per-test isolation.
- **Files modified:** `tests/integration/conftest.py`
- **Commit:** `a01b7d1` (gộp Task 03)

**3. [Rule 1 - Bug] Lifespan đọc REDIS_URL=localhost thay vì testcontainer port**

- **Found during:** Task 04 initial run — refresh test 500 INTERNAL_ERROR vì `service.refresh` connect Redis fail `ConnectionError: Error 22 connecting to localhost:6379`.
- **Issue:** `alembic_cfg` fixture (Phase 2) setEnv `REDIS_URL=redis://localhost:6379/0` (placeholder — migration không cần Redis). Plan 03-05 `auth_env` fixture muốn override với testcontainer port. Pytest fixture resolution order không guarantee `auth_env` chạy SAU `alembic_cfg` → lifespan đôi khi đọc cache_clear sau localhost setEnv.
- **Fix:** Chuyển env vars override (DATABASE_URL + REDIS_URL + JWT keys + CORS) trực tiếp vào `app_with_auth` fixture (với postgres_container + redis_container làm depend) — đảm bảo set CUỐI CÙNG + cache_clear ngay TRƯỚC `command.upgrade` và `create_app`. `auth_env` fixture giữ làm legacy backward-compat nhưng không còn dùng.
- **Files modified:** `tests/integration/conftest.py`
- **Commit:** `41b8d5c` (gộp Task 04 với Rule 1 fix bên dưới)

**4. [Rule 1 - Bug] verify_jwt_format.sh fail trên Windows do CRLF**

- **Found during:** Task 06 — `test_pkcs8_key_format_verified` fail exit 2 "format không hỗ trợ" mặc dù `keys/private.pem` header THẬT là `-----BEGIN PRIVATE KEY-----` (PKCS#8 đúng).
- **Issue:** Trên Windows git bash, `head -1 "$KEY"` return string trailing `\r` (CRLF line ending). Bash `case` so sánh string literal → `"-----BEGIN PRIVATE KEY-----\r"` ≠ `"-----BEGIN PRIVATE KEY-----"` → fall vào default case (format không hỗ trợ).
- **Fix:** Strip CR trong HEADER: `HEADER=$(head -1 "$KEY" | tr -d '\r')`.
- **Files modified:** `scripts/verify_jwt_format.sh`
- **Commit:** `6e178e4` (gộp Task 06)

### Plan adjustments nhỏ (không phải deviation logic)

1. **auth_env fixture được giữ làm "legacy backward-compat"** — Plan paste-ready code ban đầu dùng fixture này. Sau khi phát hiện deviation 3, chuyển logic vào app_with_auth direct. auth_env vẫn có thể được fixture khác gọi (test future) nên KHÔNG xoá. Documented trong conftest comment.

2. **test_rbac_dependency.py dùng helper `_spawn_rbac_app()` thay vì fixture override `auth_env, alembic_cfg`** — vì rbac test cần mount thêm router stub, không thể reuse `app_with_auth` (đã yield app sau lifespan start). Helper `_spawn_rbac_app` duplicate logic env-override + truncate + create_app + include_router. Trade-off: code duplicate ~30 dòng vs. cleaner test isolation. Chọn duplicate để rbac test KHÔNG ảnh hưởng app_with_auth contract.

3. **5 unit test test_require_role.py thay vì 3 plan-ghi** — thêm 2 test: `test_require_role_returns_callable_with_three_roles` + `test_require_role_different_calls_return_different_callables` (closure isolation regression guard). Vẫn pass acceptance "≥3 test PASS".

---

## Key Decisions

1. **require_role(*roles) factory với ValueError gate empty roles** (Task 01): `if not roles: raise ValueError("require_role cần ít nhất 1 role")` — security gate. Tránh future contributor gọi `require_role()` (rỗng) khiến route mở cho mọi role (tất cả authenticated user pass — không phải intent). Test guard `test_require_role_raises_value_error_on_empty_roles` regression.

2. **HTTPException → envelope handler trong create_app()** (Task 01): `@app.exception_handler(HTTPException)` map `exc.detail` dict `{code, message}` → envelope `{success:false, data:null, error:{code, message}, meta:null}`. Plan 03-01 `ErrorHandlerMiddleware` đã có `isinstance(exc, StarletteHTTPException): raise` pass-through → handler này render envelope đúng cho mọi 401 từ `get_current_user` (MISSING_AUTHORIZATION/INVALID_TOKEN/TOKEN_REVOKED/USER_DISABLED) + 403 từ `require_role` (FORBIDDEN).

3. **TRUNCATE CASCADE per-test isolation** (Task 03 Rule 1): `postgres_container` scope=module → data leak. Mỗi test `app_with_auth` fixture truncate `users, refresh_tokens, user_hubs RESTART IDENTITY CASCADE` qua sync engine TRƯỚC lifespan `init_engine`. Tránh duplicate-key violation khi seed `admin@medinet.vn / editor@medinet.vn / viewer@medinet.vn` cùng plaintext.

4. **asyncio.to_thread cho alembic migration** (Task 03 Rule 3): `migrations/env.py` line 105 `asyncio.run(run_async_migrations())` reject khi gọi từ async fixture (đã trong event loop). Wrap `command.upgrade` qua `asyncio.to_thread()` → thread executor pool → thread mới có event loop riêng cho asyncio.run.

5. **Env override IN app_with_auth fixture trực tiếp** (Task 04 Rule 1): `alembic_cfg` fixture (Phase 2) set REDIS_URL=localhost (placeholder — alembic không cần Redis). Pytest fixture resolution order không guarantee `auth_env` chạy SAU `alembic_cfg` → lifespan đôi khi đọc cache REDIS_URL=localhost. Fix: chuyển env override (DATABASE_URL + REDIS_URL + JWT + CORS) vào `app_with_auth` trực tiếp với postgres_container + redis_container làm depend → set CUỐI CÙNG + cache_clear NGAY TRƯỚC `command.upgrade` và `create_app`.

6. **Test-only RBAC route mount qua fixture helper** (Task 05): `_spawn_rbac_app(*roles)` helper spawn FastAPI app + `app.include_router(_make_test_rbac_router(*roles))` — KHÔNG sửa production `app/main.py`. Test fixture 2 variant: `rbac_client_admin_only` (`require_role("admin")`) + `rbac_client_admin_or_editor` (`require_role("admin", "editor")`). AC3 verify dependency contract qua route stub, integration với production `PUT /api/hubs/:id` defer Phase 5 HUB-02 (chưa tồn tại).

7. **asyncio.gather 5 concurrent refresh trigger race condition** (Task 04 AC5): `httpx.ASGITransport` in-process KHÔNG có true thread-parallel, nhưng `asyncio.gather(*[_do_refresh() for _ in range(5)])` chạy concurrent đủ trigger race trên Redis SETNX `lock:refresh:<jti>` — chỉ 1 task vào critical section trước khi SETNX commit. Assert exactly 1 success + 4 fail-401. P16 mitigation verified end-to-end.

8. **verify_jwt_format.sh strip CR cho Windows compat** (Task 06 Rule 1): git for Windows mặc định checkout LF script như CRLF nếu .gitattributes không pin. `head -1 "$KEY"` return string trailing `\r` invisible → bash `case` so sánh literal fail. Strip `\r` với `tr -d '\r'` để cross-platform. Defensive script — KHÔNG yêu cầu .gitattributes pin script LF.

9. **PII log regression test với caplog scan** (Task 06): `caplog.set_level(DEBUG)` → login + logout sequence. Scan `r.message for r in caplog.records` cho:
   - Plain password "Admin@123" KHÔNG xuất hiện → password not logged.
   - Regex `eyJ[A-Za-z0-9._-]{20,}` KHÔNG match → JWT token (access + refresh) not logged.
   - Plan 03-04 `logger.info("auth_login_success", extra={"user_id":..., "role":...})` chỉ log non-sensitive field — verify pass.

10. **PyJWT raw decode cross-process verify** (Task 06 AC2): KHÔNG dùng `JWTManager.verify_token()` (cùng instance đã issue token) — `pyjwt.decode(token, public_pem, algorithms=["RS256"], issuer="medinet-wiki")` từ scratch với key file. Proof cross-process verify: token issued bởi FastAPI lifespan JWTManager → decode được bởi PyJWT khác instance với cùng public.pem. Khẳng định Phase 5 frontend D6 (React 19 hoặc client khác có public key) decode được.

---

## Threat Model — Tracking

| Threat ID | Status | Implementation |
|-----------|--------|----------------|
| T-03-05-rbac-bypass-claim-injection (E) | **mitigated** | `get_current_user` verify RS256 signature với public key (Plan 03-02). Forged token với role:admin ký bằng key khác → `verify_token` raise JWTError → 401 INVALID_TOKEN trước khi reach `require_role`. Test Plan 03-02 `test_verify_token_rejects_tampered_signature` cover. |
| T-03-05-rbac-role-tampering-db (E) | **accepted** | M2 chấp nhận risk DB-level UPDATE attacker với DB access. Phase 5 USER-* sẽ thêm audit_log trigger on UPDATE users (defer). Phase 3 KHÔNG mitigate. |
| T-03-05-bypass-via-disabled-user (E) | **mitigated** | `get_current_user` query `WHERE is_active.is_(True)` → user disabled trả None → 401 USER_DISABLED. Token cũ unexpired vẫn fail khi user vừa bị disable. |
| T-03-05-test-leak-prod (I) | **mitigated** | Plan 03-05 KHÔNG sửa `backend/scripts/seed.sql` (legacy Go). `Hub_All/api/migrations` KHÔNG seed user. Production cần manual INSERT qua admin tool Phase 5. Documented. |
| T-03-05-pii-log (I) | **mitigated** | `test_log_no_password_leak` regression check: caplog.records KHÔNG chứa plain password hoặc JWT base64 pattern. Plan 03-04 logger.info chỉ log user_id/role. **Verified**. |
| T-03-04-timing-oracle (I) | **mitigated** (regression) | `test_login_unknown_email_returns_same_shape`: nobody@medinet.vn → 401 INVALID_CREDENTIALS shape identical với wrong-password admin → frontend KHÔNG enumerate được email. Anti-timing oracle dummy_password_hash (Plan 03-04) verified end-to-end. |
| T-03-04-refresh-race (E+T, P16) | **mitigated** (regression) | `test_refresh_concurrent_5_only_one_wins` asyncio.gather 5 → 1 PASS + 4 fail → Redis SETNX `lock:refresh:<jti>` atomic verified. |
| T-03-04-refresh-replay (E) | **mitigated** (regression) | `test_refresh_revoked_token_returns_401`: refresh lần 1 PASS → refresh lần 2 cùng token → 401 (TOKEN_REVOKED/REFRESH_RACE/INVALID_REFRESH_TOKEN). Blacklist + UPDATE refresh_tokens.revoked_at verified. |
| T-03-04-logout-incomplete (E) | **mitigated** (regression) | `test_logout_blacklists_access_token`: logout → /me với token cũ → 401 TOKEN_REVOKED. Plan 03-04 logout blacklist access JTI verified. |

---

## Phase 5 Carry-Over

**Reminder cho Phase 5 (HUB-02 + USER-02):**

1. **Integration test AC3 endpoints production** — Plan 03-05 verify `require_role()` dependency contract qua test-only route `/test/role-check`. Phase 5 HUB-02 implement `PUT /api/hubs/:id` + `DELETE /api/users/:id` PHẢI:
   - Dùng `Depends(require_role("admin"))` (cùng dependency Plan 03-05).
   - Thêm integration test verify viewer/editor → 403 FORBIDDEN, admin → 200 với production endpoint thật (KHÔNG phải test route stub).
   - Test fixture reuse `admin_token` / `editor_token` / `viewer_token` từ conftest Plan 03-05.

2. **Production user seed** — Plan 03-05 KHÔNG sửa `backend/scripts/seed.sql` (legacy Go). Phase 5 USER-01 (CRUD /api/users) sẽ implement admin endpoint để INSERT user production qua API. Migration KHÔNG seed user. Documented.

3. **Audit log trigger** — T-03-05-rbac-role-tampering-db threat accepted M2. Phase 5 USER-* nên thêm Postgres trigger AFTER UPDATE users → INSERT audit_logs nếu `role` thay đổi. Defense-in-depth ngoài application layer.

---

## DOC-BUG cleanup (carry từ Plan 03-03)

Plan 03-03 phát hiện 3 doc ghi Argon2 params `t=1, p=2` SAI (Go source `t=3, p=4`):
- `.planning/REQUIREMENTS.md` AUTH-05 — ✓ đã fix Plan 03-03.
- `.planning/research/PITFALLS.md` Pitfall #6 — chưa fix (cần follow-up commit).
- `Hub_All/CLAUDE.md` Section 3 Concerns đáng nhớ P6/R6 — chưa fix.

Plan 03-05 KHÔNG xử lý DOC-BUG này (out of scope — focus integration test). Defer cleanup Phase 4 hoặc commit docs riêng.

---

## Forward Links

**Phase 4 (CocoIndex Flow MVP):**
- `Depends(get_current_user)` cho mọi upload endpoint protected (ingest).
- `current_user.id` filter hub_isolation upload — chỉ user có access hub mới upload được vào hub đó.

**Phase 5 (Hub + User + Audit + APIKey CRUD):**
- `Depends(require_role("admin"))` cho admin-only endpoint (USER-01 CRUD, HUB-01 CRUD, AUDIT-01).
- Integration test AC3 production endpoint (xem Phase 5 Carry-Over).

**Phase 6 (Search):**
- `current_user.role` check super_admin cross-hub search.
- `claims.hub_ids` filter WHERE hub_id IN ... .

**Phase 7 (Ask + LiteLLM):**
- `Depends(get_current_user)` cho /api/ask.
- Usage tracking dùng `current_user.id`.

**Phase 10 (Hardening + Observability):**
- HARD-03: chạy `pytest -m critical` trong CI gate (29 test hiện tại + bổ sung Phase 5-7).
- HARD-01: structlog JSON output — Plan 03-05 PII log verify đã set baseline.

---

## Self-Check: PASSED

**Created files (5/5):**
- FOUND: Hub_All/api/tests/unit/test_require_role.py
- FOUND: Hub_All/api/tests/integration/test_auth_login.py
- FOUND: Hub_All/api/tests/integration/test_auth_refresh_race.py
- FOUND: Hub_All/api/tests/integration/test_rbac_dependency.py
- FOUND: Hub_All/api/tests/integration/test_jwt_compat.py

**Modified files (6/6):**
- FOUND: Hub_All/api/app/auth/dependencies.py (require_role implementation)
- FOUND: Hub_All/api/app/main.py (HTTPException envelope handler)
- FOUND: Hub_All/api/tests/integration/conftest.py (10 fixture extension)
- FOUND: Hub_All/api/pyproject.toml (testcontainers[postgres,redis])
- FOUND: Hub_All/api/uv.lock (auto-update)
- FOUND: Hub_All/api/scripts/verify_jwt_format.sh (CRLF fix)

**Commits (6/6):**
- FOUND: 010c8a1 feat(phase-03): auth(dependencies+main) — require_role(*roles) đầy đủ + HTTPException envelope handler
- FOUND: 29d4edf feat(phase-03): tests(integration/conftest) — RedisContainer + httpx + 3 seeded user fixtures
- FOUND: a01b7d1 feat(phase-03): tests(integration/test_auth_login) — AC1 envelope shape 5 test PASS
- FOUND: 41b8d5c feat(phase-03): tests(integration/test_auth_refresh_race) — AC5 concurrent refresh 5/5 PASS
- FOUND: 0f1fdc6 feat(phase-03): tests(integration/test_rbac_dependency) — AC3 RBAC 6/6 PASS
- FOUND: 6e178e4 feat(phase-03): tests(integration/test_jwt_compat) — AC2 JWT decode + /me + logout + PII 5/5 PASS

**Tests (62/62 baseline + 29/29 critical):**
- Plan 03-05 mới: 5 unit + 22 integration = 27 test PASS
- Phase 3 cũ: 25 unit (JWT 8 + password 6 + middleware 9 + main 2) + 4 integration cross-compat
- Phase 2 cũ: 7 integration (3 migration + 3 chunks HNSW + 1 alembic ignore cocoindex)
- Total: 62/62 PASS — no regression.
- Critical: 29 PASS (cho CI gate HARD-03).

**ROADMAP success criteria (5/5):**
- FOUND AC1: test_login_envelope_shape_byte_identical_go PASS
- FOUND AC2: test_login_token_decodable_with_public_key + test_pkcs8_key_format_verified PASS
- FOUND AC3: test_admin_returns_200 + test_viewer_returns_403_forbidden + test_editor_returns_403_forbidden PASS
- FOUND AC4: test_pwdlib_verify_go_seed_admin_hash PASS (regression check Plan 03-03)
- FOUND AC5: test_refresh_concurrent_5_only_one_wins PASS

**AUTH-04 requirement (1/1):**
- AUTH-04: `require_role("admin"|"editor"|"viewer")` qua FastAPI Depends ✓ Done 2026-05-14 (app/auth/dependencies.py + 5 unit test + 6 integration test verify viewer/editor/admin pattern).

**Phase 3 COMPLETE:** AUTH-01 (Plan 03-04) + AUTH-02 (Plan 03-04) + AUTH-03 (Plan 03-04) + AUTH-04 (Plan 03-05) + AUTH-05 (Plan 03-03) + AUTH-06 (Plan 03-02) — **6/6 AUTH requirements done**.

---

*Plan 03-05 hoàn tất — 2026-05-14. Phase 3 COMPLETE. Next: `/gsd-execute-phase 4` (CocoIndex Flow MVP + Document Ingest).*
