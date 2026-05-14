---
phase: 3
plan: 04
subsystem: api/app/auth + api/app/main
tags: [auth, jwt, argon2, redis-blacklist, p16-setnx, anti-timing, fastapi-router, auth-01, auth-02, auth-03, wave3]
requires: [03-01, 03-02, 03-03]
provides: [auth-service-4-usecase, get-current-user-bearer-dep, auth-router-4-endpoint, app-state-jwt-manager, app-state-dummy-password-hash]
affects: [03-05]
tech-stack:
  added: [email-validator-2.3.0, dnspython-2.8.0]
  patterns: [layered-router-service-repo, anti-timing-dummy-hash, redis-setnx-atomic-lock, oauth2-password-bearer-auto-error-false, app-state-singleton-from-lifespan, fail-open-redis-down]
key-files:
  created:
    - Hub_All/api/app/auth/schemas.py
    - Hub_All/api/app/auth/service.py
    - Hub_All/api/app/auth/dependencies.py
    - Hub_All/api/app/auth/router.py
  modified:
    - Hub_All/api/app/auth/__init__.py
    - Hub_All/api/app/main.py
    - Hub_All/api/pyproject.toml
    - Hub_All/api/uv.lock
decisions:
  - "P16 SETNX atomic lock: redis.set(lock:refresh:<jti>, 1, nx=True, ex=30) trước rotate — chỉ 1 caller thắng race. Concurrent 5 tab cùng refresh_token → 1 PASS, 4 lần 401 REFRESH_RACE."
  - "Anti-timing dummy_password_hash: pre-compute 1 hash ở lifespan startup. service.login LUÔN gọi verify_password kể cả user None (hash_to_check = user.password_hash if user else self.dummy_password_hash) — T-03-04-timing-oracle mitigation."
  - "Refresh token storage SHA-256 hex 64-char (T-02-03): _hash_refresh_token(plain) → DB column token_hash. Plaintext chỉ trong transit + Redis blacklist key (là JTI UUID, KHÔNG phải plaintext)."
  - "Fail-open Redis down: nếu app.state.redis = None thì blacklist + SETNX skip + log warning. Phase 3 chấp nhận risk staleness; Phase 10 HARD-04 sẽ siết Redis down → 503 toàn bộ auth."
  - "OAuth2PasswordBearer(auto_error=False) — KHÔNG để FastAPI raise 403 mặc định. get_current_user tự raise 401 với 5 code cụ thể (MISSING_AUTHORIZATION / INVALID_TOKEN / TOKEN_REVOKED / USER_DISABLED)."
  - "require_role là SKELETON ở Plan 03-04 — raise NotImplementedError nếu gọi. Plan 03-05 sẽ implement đầy đủ. 4 endpoint Plan 03-04 chỉ cần authenticate, không cần role-gate."
  - "Lifespan +3 step: JWTManager init, dummy_password_hash pre-compute, SQLAlchemy init_engine — KHÔNG fail-crash, chỉ log warning + set state=None (Phase 1 skeleton pattern)."
  - "Pydantic[email] bump (Rule 3): EmailStr cần email-validator. pyproject.toml: pydantic → pydantic[email]. uv sync install email-validator 2.3.0 + dnspython 2.8.0."
metrics:
  duration_minutes: 6
  completed_date: "2026-05-14"
  tasks_total: 5
  tasks_completed: 5
  files_created: 4
  files_modified: 4
  commits: 5
  tests_total_baseline: 36
  tests_passed: 36
---

# Phase 3 Plan 04: Auth Router + Service + Redis Blacklist + Lifespan Wire — Summary

**Wave 3 toàn flow auth cho Phase 3:** Port toàn bộ auth M2 sang Python — 4 endpoint `/api/auth/{login,refresh,logout,me}` + AuthService 4 use-case + FastAPI dependency chain `get_current_user` Bearer auth + Redis SETNX P16 race mitigation + anti-timing oracle dummy hash. Tất cả 5 task hoàn thành atomic, 36/36 pytest no regress, ruff + mypy clean 8 source file. AUTH-01/02/03 hoàn thành. Plan 03-05 (Wave 4) sẽ extend `require_role` đầy đủ + 5-AC integration test với testcontainers Postgres+Redis.

---

## Mục tiêu (Objective)

Plan 03-04 thuộc Wave 3 của Phase 3 — sản xuất hợp đồng auth runtime mà Plan 03-05 (RBAC + integration test) + Phase 5 CRUD endpoint phụ thuộc:

1. **AuthService 4 use-case** — login (anti-timing), refresh (P16 SETNX), logout (blacklist access+refresh), get_current_user_info.
2. **FastAPI dependency chain** — `get_jwt_manager`, `get_redis`, `get_dummy_password_hash`, `get_auth_service`, `get_current_user` (5 reject case 401), `require_role` skeleton.
3. **4 endpoint** — `POST /api/auth/login` + `/refresh` + `/logout` + `GET /api/auth/me`, response qua envelope `resp.ok/unauthorized` Plan 03-01.
4. **Lifespan wire** — `app.state.jwt_manager = JWTManager(settings)` + `app.state.dummy_password_hash = hash_password(...)` + `init_engine(settings)` cho SQLAlchemy async session.

---

## Tasks hoàn thành (5/5)

| # | Task | Commit | Status |
|---|------|--------|--------|
| 01 | Tạo `app/auth/schemas.py` — 5 Pydantic v2 model (LoginRequest, LoginResponse, UserPublic, RefreshRequest, LogoutRequest) + bump pyproject `pydantic` → `pydantic[email]` để EmailStr hoạt động | `c165c4d` | PASS |
| 02 | Tạo `app/auth/service.py` — AuthService 4 method + AuthError + `_hash_refresh_token` SHA-256 + anti-timing oracle + P16 SETNX | `6b7d8a6` | PASS |
| 03 | Tạo `app/auth/dependencies.py` — 5 dependency (`get_jwt_manager`, `get_redis`, `get_dummy_password_hash`, `get_auth_service`, `get_current_user`) + `require_role` skeleton + `oauth2_scheme` | `31d54fd` | PASS |
| 04 | Tạo `app/auth/router.py` (4 endpoint) + extend `app/auth/__init__.py` re-export 8 symbol mới (15 export total) | `8aaad3f` | PASS |
| 05 | Extend `app/main.py` lifespan với 3 step mới (JWTManager + dummy_password_hash + init_engine) + include_router(auth_router) + readyz check["jwt"] | `1c9237f` | PASS |

---

## Files thay đổi (8 file)

### Created (4)

- `Hub_All/api/app/auth/schemas.py` — 5 Pydantic v2 model. `LoginRequest.email: EmailStr` + password min_length=1 max_length=200. `UserPublic.hub_assignments: list[str]` (USER-03 multi-hub). `role: Literal["admin","editor","viewer"]`.
- `Hub_All/api/app/auth/service.py` — AuthService class với 4 async method (login, refresh, logout, get_current_user_info). AuthError(code, message) exception. _hash_refresh_token SHA-256 hex 64-char. Constructor injection: db, redis, jwt_manager, dummy_password_hash.
- `Hub_All/api/app/auth/dependencies.py` — 5 FastAPI dependency + oauth2_scheme + require_role stub. `get_current_user` reject 5 case 401: MISSING_AUTHORIZATION / INVALID_TOKEN / TOKEN_REVOKED / USER_DISABLED + Redis blacklist check.
- `Hub_All/api/app/auth/router.py` — APIRouter(prefix="/api/auth", tags=["auth"]) với 4 route. `_auth_error_to_response()` helper map AuthError.code → resp.unauthorized.

### Modified (4)

- `Hub_All/api/app/auth/__init__.py` — extend re-export 8 symbol mới: AuthService, AuthError, get_auth_service, get_current_user, get_jwt_manager, oauth2_scheme, require_role, auth_router. `__all__` giữ alphabetical (21 mục).
- `Hub_All/api/app/main.py` — lifespan startup +3 step (JWTManager, dummy_password_hash, init_engine), shutdown +1 step (dispose_engine + reset jwt_manager), create_app +1 dòng (include_router), readyz +1 check (jwt). noqa C901 cho lifespan/create_app vì init sequence vốn nhiều step.
- `Hub_All/api/pyproject.toml` — bump `pydantic>=2.7.0,<3` → `pydantic[email]>=2.7.0,<3` để EmailStr hoạt động.
- `Hub_All/api/uv.lock` — auto-update bởi `uv sync` thêm email-validator 2.3.0 + dnspython 2.8.0.

---

## Acceptance Criteria — verification suite

| Check | Command | Kết quả |
|-------|---------|---------|
| Schemas import + EmailStr | `python -c "from app.auth.schemas import LoginRequest, LoginResponse, UserPublic, RefreshRequest, LogoutRequest; r = LoginRequest(email='admin@medinet.vn', password='x'); print(r.email, r.password)"` | exit 0, output `admin@medinet.vn x` |
| Service import + hash 64 char | `python -c "from app.auth.service import AuthService, AuthError, _hash_refresh_token; h = _hash_refresh_token('abc'); assert len(h)==64; print('imports + hash OK')"` | exit 0, `imports + hash OK` |
| Dependencies import | `python -c "from app.auth.dependencies import get_jwt_manager, get_auth_service, get_current_user, require_role, oauth2_scheme; print('imports OK')"` | exit 0, `imports OK` |
| Router prefix | `python -c "from app.auth import auth_router, AuthService, get_current_user, AuthError; print(auth_router.prefix)"` | exit 0, `/api/auth` |
| 4 routes mounted | `python -c "from app.main import create_app; app = create_app(); paths = {r.path for r in app.routes}; required = {'/api/auth/login','/api/auth/refresh','/api/auth/logout','/api/auth/me','/healthz','/readyz'}; missing = required - paths; assert not missing; print('all routes OK')"` | exit 0, `all routes OK` (6 path verified) |
| All exports OK | `python -c "from app.auth import auth_router, AuthService, get_current_user, AuthError, JWTManager, JWTError, hash_password, verify_password, require_role; print('all exports OK')"` | exit 0 |
| ruff app/auth + main | `uv run ruff check app/auth app/main.py` | All checks passed (8 source files) |
| mypy app/auth + main | `uv run mypy app/auth app/main.py` | Success: no issues found in 8 source files |
| Full pytest suite (regress) | `uv run pytest tests/ -q` | **36 passed in 16.95s** (25 unit + 11 integration — no regression) |
| Grep schemas — 5 class | `grep -c "^class (LoginRequest|LoginResponse|UserPublic|RefreshRequest|LogoutRequest)"` | 5 |
| Grep service — keyword | `grep -c "...23 pattern..."` | 23 occurrence (AuthError + AuthService + login/refresh/logout/get_current_user_info + dummy_password_hash + nx=True,ex=30 + 5 error code) |
| Grep dependencies — 19 marker | — | 19 |
| Grep router — 17 marker | — | 17 |
| Grep main — 8 wire | — | 8 (from app.auth import JWTManager + app.state.jwt_manager + dummy_password_hash + include_router + jwt_manager_ready + checks["jwt"]) |

**Tổng:** 13 acceptance check 13/13 PASS.

---

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] EmailStr cần `pydantic[email]` extra — bump pyproject dep**

- **Found during:** Task 01 acceptance run — `from app.auth.schemas import LoginRequest` raise `ImportError: email-validator is not installed, run pip install 'pydantic[email]'` vì `pyproject.toml` line 10 ghi `pydantic>=2.7.0,<3` (KHÔNG có `[email]` extra) → email-validator + dnspython không được install.
- **Issue:** Plan 03-04 task 01 plan paste-ready code dùng `EmailStr` cho `LoginRequest.email`. Plan đã document trước nguy cơ này ("Lưu ý: EmailStr cần pydantic[email] — kiểm tra... nếu fail, **cập nhật pyproject.toml**"). Đây là deviation **đã được anticipate trong plan** → Rule 3 apply theo plan note.
- **Fix:** `pyproject.toml` line 10: `"pydantic>=2.7.0,<3"` → `"pydantic[email]>=2.7.0,<3"`. Chạy `uv sync --extra dev` install email-validator 2.3.0 + dnspython 2.8.0. `uv.lock` auto-update.
- **Files modified:** `Hub_All/api/pyproject.toml`, `Hub_All/api/uv.lock` (auto)
- **Commit:** `c165c4d` (gộp cùng Task 01 — atomic schemas + dep bump)

**2. [Rule 3 - Blocking] ruff B008 false positive với FastAPI Depends pattern**

- **Found during:** Task 03 ruff check `app/auth/dependencies.py`.
- **Issue:** ruff rule B008 "Do not perform function call `Depends` in argument defaults". Đây là FALSE POSITIVE — FastAPI Depends() là pattern chuẩn của framework, KHÔNG phải mutable default. 7 vị trí raise B008 trong dependencies.py + router.py.
- **Fix:** Thêm `# noqa: B008` cho 7 vị trí (4 trong dependencies.py + 5 trong router.py). Alternative: cấu hình `tool.ruff.lint.extend-immutable-calls = ["fastapi.Depends"]` toàn dự án — defer Plan 06 CONVENTIONS.md cleanup commit.
- **Files modified:** `Hub_All/api/app/auth/dependencies.py`, `Hub_All/api/app/auth/router.py`
- **Commits:** `31d54fd` (dependencies), `8aaad3f` (router)

**3. [Rule 3 - Blocking] mypy unused type:ignore + ruff C901 complexity**

- **Found during:** Task 02 + Task 05 mypy strict.
- **Issue:**
  - Task 02 service.py: 3 vị trí `# type: ignore[arg-type]` cho `user.role` (Literal type from User.role str column) — mypy báo Unused. SQLAlchemy `user.role: Mapped[str]` đã đủ rộng để gán vào Literal field.
  - Task 05 main.py: lifespan + create_app vượt ngưỡng complexity 10 (lifespan=13, create_app=11) vì init sequence 6 step + readyz aggregate 4 check.
- **Fix:**
  - service.py: bỏ 3 `# type: ignore[arg-type]` (commit Task 02 đã hợp nhất).
  - main.py: `# noqa: C901 — init sequence` + `# noqa: C901 — readyz aggregate checks` cho 2 function. Logic là sequence init/check naturally, không phải logic phức tạp.
- **Commits:** `6b7d8a6` (service fix gộp), `1c9237f` (main noqa gộp)

### Không deviate logic-wise

- Toàn bộ paste-ready code paste nguyên xi từ plan.
- Service code, dependency code, router code KHÔNG đổi behavior — chỉ tinh chỉnh để pass mypy strict + ruff.

---

## Key Decisions

1. **P16 SETNX atomic lock** (Task 02 — refresh race mitigation): `redis.set(lock:refresh:<old_jti>, "1", nx=True, ex=30)`. Return False = lock đã thuộc caller khác → raise AuthError("REFRESH_RACE", "Refresh token đang được xử lý — vui lòng thử lại") → 401. Sau khi lock acquired, double-check blacklist: nếu old jti đã trong blacklist (rotate hoàn tất trước khi lock TTL expire) → raise TOKEN_REVOKED. Lock auto-expire 30s — đủ rotate hoàn tất + KHÔNG block lâu.

2. **Anti-timing oracle dummy hash** (Task 02 + Task 05 — T-03-04-timing-oracle mitigation): service.login LUÔN gọi `verify_password(req.password, hash_to_check)` kể cả user None. `hash_to_check = user.password_hash if user else self.dummy_password_hash`. dummy_password_hash pre-compute 1 lần ở lifespan startup với `hash_password("dummy-not-a-real-password-Đ#")` — chứa ký tự Tiếng Việt + ký tự đặc biệt + 30 char để hash time tương đương real user. Fallback nếu hash_password lỗi: hardcode dummy hex hash hợp lệ format (sẽ luôn verify False).

3. **Refresh token storage SHA-256** (Task 02 — T-02-03 mitigation): `_hash_refresh_token(plain) = sha256(plain.encode()).hexdigest()` → DB column token_hash 64-char. SHA-256 KHÔNG phải Argon2 — lý do: cần lookup nhanh by hash (Argon2 mỗi verify ~100ms = unacceptable cho refresh path). Plaintext refresh_token chỉ trong transit (HTTPS) + Redis blacklist key (là JTI UUID, KHÔNG phải plaintext). Login + refresh + logout đều dùng cùng helper.

4. **Fail-open Redis down** (Task 02 + Task 03 — Phase 3 design choice): `if self.redis is None: log.warning + continue`. Blacklist + SETNX skip nếu Redis down — KHÔNG block toàn bộ auth path. Phase 3 chấp nhận risk staleness (revoked token vẫn pass đến khi exp expired) vì Redis là cache, KHÔNG primary security. Phase 10 HARD-04 sẽ siết: Redis down → 503 toàn bộ auth endpoint.

5. **OAuth2PasswordBearer auto_error=False** (Task 03): `OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)`. Mặc định FastAPI auto_error=True → raise 403 nếu thiếu Bearer (KHÔNG phải 401). Set False để get_current_user tự raise 401 với 5 code cụ thể: MISSING_AUTHORIZATION (rỗng) / INVALID_TOKEN (decode fail) / TOKEN_REVOKED (blacklist) / USER_DISABLED (user None hoặc is_active=False).

6. **require_role là SKELETON** (Task 03 — Plan 03-05 sẽ implement): Plan 03-04 KHÔNG dùng require_role (4 endpoint login/refresh/logout/me chỉ cần authenticate, không cần role-gate). Stub raise NotImplementedError("require_role chưa implement — Plan 03-05 sẽ extend") nếu gọi để guard regression. Plan 03-05 sẽ implement đầy đủ check `user.role in roles` raise resp.forbidden() nếu không match.

7. **Lifespan +3 step + readyz +1 check** (Task 05): startup order — DB pool → Redis → CocoIndex → **JWTManager** → **dummy_password_hash** → **SQLAlchemy engine init_engine**. Mỗi step try/except với log warning + state=None nếu fail — KHÔNG crash app (Phase 1 skeleton pattern, fail-fast siết Phase 2+ nếu cần). Shutdown ngược: dispose_engine + reset jwt_manager (test isolation defensive).

8. **Pydantic[email] bump** (Task 01 — Rule 3 deviation đã anticipate): plan đã ghi rõ "nếu pyproject.toml line 10 `pydantic>=2.7.0,<3` không có [email], **cập nhật pyproject.toml** thay → `pydantic[email]>=2.7.0,<3`". Đây không phải deviation logic-wise, mà là plan pre-emptive flag → executor apply.

9. **`# noqa: B008` cho FastAPI Depends** (Task 03 + Task 04): ruff B008 false positive vì coi `Depends()` là mutable default. Inline `# noqa: B008` cho 9 vị trí (dependencies.py + router.py). Alternative tốt hơn: `[tool.ruff.lint] extend-immutable-calls = ["fastapi.Depends"]` toàn dự án — defer Plan 06 CONVENTIONS cleanup commit.

10. **`# noqa: C901` cho lifespan + create_app** (Task 05): ruff C901 complexity 13 (lifespan) + 11 (create_app) vượt ngưỡng 10. Init sequence vốn nhiều step (DB → Redis → CocoIndex → JWT → dummy_hash → SQLAlchemy = 6 step), readyz aggregate 4 check — KHÔNG phải logic phức tạp mà sequence linear. noqa pragma chính đáng + comment giải thích.

---

## Threat Model — Tracking

| Threat ID | Status | Implementation |
|-----------|--------|----------------|
| T-03-04-timing-oracle (I) | **mitigated** | `service.login` LUÔN gọi `verify_password(req.password, hash_to_check)` với `hash_to_check = user.password_hash if user else self.dummy_password_hash`. dummy_password_hash pre-compute ở lifespan startup. Plan 03-05 sẽ có integration test đo response time delta (optional load test). |
| T-03-04-refresh-race (P16, E+T) | **mitigated** | `service.refresh`: `redis.set(f"lock:refresh:{claims.jti}", "1", nx=True, ex=30)`. Return False → raise AuthError REFRESH_RACE 401. Plan 03-05 sẽ có integration test concurrent 5 call verify chỉ 1 thắng. |
| T-03-04-token-fixation (E) | **mitigated** | `JWTManager.issue_token_pair` sinh `access_jti = str(uuid.uuid4())` + `refresh_jti = str(uuid.uuid4())` MỚI mỗi call (đã có sẵn từ Plan 03-02). Sau rotate, old jti immediately blacklisted (TTL = refresh_ttl). Attacker pre-issue không inject được vào session. |
| T-03-04-refresh-replay (E) | **mitigated** | `service.refresh`: sau verify + rotate, `redis.set(f"blacklist:{claims.jti}", "1", ex=self.jwt_manager.refresh_ttl_seconds)`. Replay old refresh → check blacklist → 401 TOKEN_REVOKED. DB column `refresh_tokens.revoked_at = NOW()` cũng update song song. |
| T-03-04-logout-incomplete (E) | **mitigated** | `router.logout`: accept optional `LogoutRequest.refresh_token` body. Nếu có → service.logout blacklist CẢ access JTI + refresh JTI + UPDATE refresh_tokens.revoked_at. Frontend D6 PHẢI gửi cả 2 khi logout (defer Phase 5 USER document). Backend đã hỗ trợ đầy đủ. |
| T-03-04-pii-log (I) | **mitigated** | `service.py` 4 logger.info chỉ log `user_id, role, email_present` (bool). KHÔNG bao giờ log `req.password`, `req.refresh_token`, `token_hash`, `claims.jti` (jti log có thể accept vì là UUID không-sensitive). Convention CONVENTIONS.md section 5 (defer Plan 06). |
| T-03-04-redis-down-fail-open (E) | **accepted** | Phase 3 fail-open: Redis None → `log.warning + continue`. Blacklist + SETNX skip. M2 accept risk vì Redis là cache. Phase 10 HARD-04 sẽ siết Redis down → 503. |

---

## Forward Links (Wave 4 dependencies)

**Plan 03-05 (RBAC `require_role` + integration test suite):**

- Sẽ EXTEND `dependencies.py` `require_role(*roles)` từ stub NotImplementedError → check `user.role in roles raise resp.forbidden()`. Pattern dependency factory return Callable.
- Sẽ tạo `tests/integration/test_auth_*.py` với fixture testcontainers Postgres + Redis. Test login happy + invalid password + refresh rotate + blacklist + me Bearer + concurrent refresh race + email enumeration timing.
- Sẽ test `test_login_validation_error_on_bad_email_format` — POST `/api/auth/login` với `email='not-an-email'` → 422 (FastAPI default Pydantic validation). Plan 03-04 chỉ ship schema; runtime EmailStr reject verify ở Plan 03-05.
- Sẽ wire FastAPI exception_handler cho HTTPException → render envelope shape khớp với raise HTTPException trong get_current_user dependency (Plan 03-01 đã pass-through HTTPException qua ErrorHandlerMiddleware).
- Sẽ test cross-process Go→Python JWT verify (AUTH-06 full criterion — sinh token Go runtime, assert Python verify_token decode OK). Defer rời từ Plan 03-02 unit test.

**Phase 5 (Hub + User + Audit + APIKey CRUD):**

- Sẽ dùng `Depends(get_current_user)` cho mọi endpoint protected — Bearer auth.
- Sẽ dùng `Depends(require_role("admin"))` cho admin-only endpoint (sau khi Plan 03-05 implement).
- Sẽ dùng `current_user.id` từ User entity để filter hub_isolation qua JOIN user_hubs.

**Phase 6 (Search):**

- Sẽ dùng `current_user.role` để check super_admin có quyền cross-hub search hay không.
- Sẽ dùng `claims.hub_ids` (qua get_current_user) để filter hub WHERE clause.

---

## Self-Check: PASSED

**Created files (4/4):**
- FOUND: Hub_All/api/app/auth/schemas.py
- FOUND: Hub_All/api/app/auth/service.py
- FOUND: Hub_All/api/app/auth/dependencies.py
- FOUND: Hub_All/api/app/auth/router.py

**Modified files (4/4):**
- FOUND: Hub_All/api/app/auth/__init__.py (extend 8 export → 21 export total)
- FOUND: Hub_All/api/app/main.py (lifespan +3 step, shutdown +1, create_app +1, readyz +1)
- FOUND: Hub_All/api/pyproject.toml (pydantic → pydantic[email])
- FOUND: Hub_All/api/uv.lock (auto-update — email-validator 2.3.0 + dnspython 2.8.0)

**Commits (5/5):**
- FOUND: c165c4d feat(phase-03): auth(schemas) — Pydantic v2 models cho 4 endpoint login/refresh/logout/me
- FOUND: 6b7d8a6 feat(phase-03): auth(service) — AuthService 4 use-case + Redis blacklist + P16 SETNX
- FOUND: 31d54fd feat(phase-03): auth(dependencies) — FastAPI Depends chain + Bearer auth + blacklist
- FOUND: 8aaad3f feat(phase-03): auth(router) — 4 endpoint login/refresh/logout/me + envelope D6-compat
- FOUND: 1c9237f feat(phase-03): main(lifespan+router) — wire JWTManager + dummy_password_hash + auth router

**Routes (4 auth + 2 health):**
- FOUND: POST /api/auth/login
- FOUND: POST /api/auth/refresh
- FOUND: POST /api/auth/logout
- FOUND: GET  /api/auth/me
- FOUND: GET  /healthz
- FOUND: GET  /readyz

**Tests baseline (36/36 PASS — no regression):**
- 25 unit (Phase 3 Plan 02 JWT 8 + Plan 03 Argon2 6 + Plan 01 middleware 9 + Phase 2 unit 2)
- 11 integration (Phase 2 Plan 05 testcontainers 7 + Phase 3 Plan 03 cross-compat 4)
