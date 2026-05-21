---
phase: 05-hub-user-audit-apikey-settings-crud
plan: 04
subsystem: backend-crud
tags: [user, profile, crud, fastapi, pydantic, raw-sql, audit, password-reset, layered-architecture]

# Dependency graph
requires:
  - phase: 05-hub-user-audit-apikey-settings-crud (plan 01)
    provides: "migration 0003 users.phone/department/avatar_url/status + audit_service enqueue_audit/AuditEntry"
  - phase: 05-hub-user-audit-apikey-settings-crud (plan 02)
    provides: "(không dùng trực tiếp — user CRUD admin-only, hub-isolation enforce defer Plan 05-06)"
  - phase: 03-auth-port-rbac-response-envelope
    provides: "get_current_user + require_role + hash_password/verify_password (argon2) + get_redis dependency"
  - phase: 04-cocoindex-flow-mvp
    provides: "documents.py router analog + documents_service.py service-chứa-SQL + WHERE-builder pattern + response envelope"
provides:
  - "schemas/users.py — 10 Pydantic v2 schema user + profile (CreateUser/UpdateUser/ChangeRole/ChangeStatus/UpdateProfile/ChangePassword request + UserResponse/RoleAssignment/UserWithRolesResponse)"
  - "services/user_service.py — UserService 9 method CRUD + hub_assignments join + reset token log-only + self password change; UserConflictError"
  - "routers/users.py — User CRUD router 7 endpoint admin-only (update tách 3 endpoint D-07; chưa mount — wiring Plan 05-06)"
  - "routers/profile.py — Profile self-scoped router 3 endpoint KHÔNG :id (chưa mount — wiring Plan 05-06)"
affects: [05-06]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Service-chứa-SQL CRUD — raw text() + named bind params, helper _build_user_with_roles dùng chung get/create/list/update"
    - "Dynamic SET clause builder cho PUT update — _update_fields dùng chung admin update + self update_profile"
    - "user_hubs join build roles[] — mỗi assignment → RoleAssignment với role = users.role (M2 1-role-per-user)"
    - "3-state return cho self password change — None (user missing) / False (wrong old password) / True (success)"

key-files:
  created:
    - "api/app/schemas/users.py"
    - "api/app/services/user_service.py"
    - "api/app/routers/users.py"
    - "api/app/routers/profile.py"
  modified: []

key-decisions:
  - "D-07 — User update tách 3 endpoint: PUT /:id (profile fields) + PATCH /:id/role + PATCH /:id/status (frontend api.ts thắng REQUIREMENTS' single PATCH)"
  - "D-07 — Profile dùng /api/profile (KHÔNG /api/users/:id/profile); router KHÔNG nhận :id param — self-scoped"
  - "USER-02 — reset-password sinh token TTL 1h Redis ex=3600, CHỈ log console; token KHÔNG trả qua API response (T-05-04-04 — tránh account takeover); email defer v4.0"
  - "failed_login_count trả hằng 0 — KHÔNG có cột DB (M2 chưa track; defer)"
  - "UserResponse field name map từ cột DB full_name; password_hash KHÔNG bao giờ trong response schema (T-05-04-03)"
  - "Router mount vào main.py defer Plan 05-06 (Wave 4 wiring) — Plan 05-04 KHÔNG touch main.py/routers/__init__.py"

patterns-established:
  - "User CRUD service-chứa-SQL: _USER_SELECT_COLS hằng + _build_user_with_roles helper (SELECT user + user_hubs) dùng chung get/create/list/update"
  - "_update_fields helper động: build SET parts cho field không None (name→full_name/phone/department), luôn append updated_at=NOW(); dùng chung admin update + self update_profile"

requirements-completed: [USER-01, USER-02, USER-03]

# Metrics
duration: 3min
completed: 2026-05-17
---

# Phase 5 Plan 04: User Management CRUD + reset-password + Profile self-scoped Summary

**User Management CRUD (USER-01) + reset-password log-only (USER-02) + Profile self-scoped (USER-03) theo layered architecture — 4 file (schema/service/2 router) với 7 endpoint user admin-only (update tách 3 endpoint D-07) + 3 endpoint profile self-scoped KHÔNG :id; reset token chỉ log console (defer email v4.0), password luôn hash argon2, old password verify trước khi đổi.**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-05-17T03:26:44Z
- **Completed:** 2026-05-17T03:29:44Z
- **Tasks:** 3 completed
- **Files modified:** 4 (4 created + 0 modified)

## Accomplishments

- `schemas/users.py` — 10 Pydantic v2 schema: `CreateUserRequest` (email EmailStr + name/password min_length + phone/department optional + hub_id + role), `UpdateUserRequest`/`UpdateProfileRequest` (name/phone/department optional — D-07 tách khỏi role/status), `ChangeUserRoleRequest` (hub_id+role), `ChangeUserStatusRequest` (status), `ChangePasswordRequest` (old_password min_length=1 + new_password min_length=8), `UserResponse` (= UserAPI shape — KHÔNG `password_hash`, `name` map `full_name`, `failed_login_count` hằng 0), `RoleAssignment` (= RoleAPI), `UserWithRolesResponse` (user + roles[]). `UserRole`/`UserStatus` Literal khớp CHECK constraint.
- `services/user_service.py` — `UserService` 9 method: `create` (hash password argon2 + INSERT users + INSERT user_hubs assignment + enqueue audit `user.create` payload chỉ email+role, IntegrityError→`UserConflictError`), `get`/`_build_user_with_roles` (SELECT user + user_hubs join → UserWithRolesResponse), `list` (WHERE-builder filter role/status/search ILIKE + hub_id subquery + COUNT + LIMIT/OFFSET), `update`/`update_profile`/`_update_fields` (dynamic SET clause động — D-07), `change_role` (UPDATE role + upsert user_hubs ON CONFLICT DO NOTHING), `change_status` (UPDATE status + is_active), `reset_password` (`secrets.token_urlsafe(32)` + Redis `ex=3600` + `logger.info` log-only — USER-02), `change_password_self` (verify_password old → 3-state None/False/True). Raw SQL parametrized, timestamp `NOW()` server-side.
- `routers/users.py` — User CRUD router 7 endpoint, mọi endpoint `require_role("admin")`: `GET /api/users` (list cap per_page≤100 + filter hub_id/role/status/search), `POST /api/users` (create→201, conflict→409 EMAIL_CONFLICT), `GET /api/users/{id}`, `PUT /api/users/{id}` (update profile — D-07), `PATCH /api/users/{id}/role` (D-07), `PATCH /api/users/{id}/status` (D-07), `POST /api/users/{id}/reset-password` (USER-02 — message generic, KHÔNG trả token). UUID validate → 400 `INVALID_USER_ID`; not-found → 404 `NOT_FOUND`.
- `routers/profile.py` — Profile self-scoped router 3 endpoint, mọi endpoint `get_current_user` (KHÔNG `require_role` — viewer/editor/admin tự truy cập): `GET /api/profile`, `PUT /api/profile`, `POST /api/profile/password` (verify old → 404/400 INVALID_PASSWORD/200). KHÔNG route nào có `:id` param — `user_id` LUÔN từ JWT (T-05-04-02).

## Task Commits

Each task was committed atomically (normal git, hooks enabled):

1. **Task 1: schemas/users.py — Pydantic v2 schema user + profile** - `00ff3b4` (feat)
2. **Task 2: services/user_service.py — UserService CRUD + hub_assignments + reset token** - `31b6ea5` (feat)
3. **Task 3: routers/users.py + routers/profile.py — User CRUD + Profile self-scoped** - `4192f22` (feat)

## Files Created/Modified

- `api/app/schemas/users.py` - 10 Pydantic v2 schema cho user CRUD + profile; `UserResponse` KHÔNG `password_hash`, contract field từ api.ts.
- `api/app/services/user_service.py` - `UserService` 9 method CRUD + hub_assignments join + reset token log-only + self password change; `UserConflictError`.
- `api/app/routers/users.py` - User CRUD router 7 endpoint admin-only; update tách 3 endpoint PUT/PATCH-role/PATCH-status (D-07); reset-password KHÔNG trả token.
- `api/app/routers/profile.py` - Profile self-scoped router 3 endpoint; KHÔNG :id param — user_id từ JWT.

## Verification

- **Task 1:** `ruff check` + `mypy --strict app/schemas/users.py` exit 0. Import `CreateUserRequest`/`UserWithRolesResponse`/`ChangeUserRoleRequest`/`UpdateProfileRequest` OK; 10 class present; `CreateUserRequest.email` dùng `EmailStr`, `password` `min_length=8`.
- **Task 2:** `ruff check` + `mypy --strict app/services/user_service.py` exit 0. Import `UserService`/`UserConflictError` OK; 9 method present; `user_hubs` match (INSERT + upsert + subquery); `hash_password` match (create + change_password); `reset_password` dùng `secrets.token_urlsafe` + Redis `ex=3600` + `logger.info`; `change_password_self` gọi `verify_password`.
- **Task 3:** `ruff check` + `mypy --strict app/routers/users.py app/routers/profile.py` exit 0. Route smoke test: users 7 route đúng verb (`PUT /api/users/{user_id}`, `PATCH /api/users/{user_id}/role` present); profile 3 route, KHÔNG route nào có `{` path param. `require_role("admin")` 7 endpoint.
- **Plan-level:** `ruff check` + `mypy --strict` 4 file clean (4 source). Không file nào bị xoá ngoài ý muốn (`git diff --diff-filter=D HEAD~3 HEAD` rỗng).

## Deviations from Plan

None - plan executed exactly as written.

### Out-of-scope discoveries (logged, NOT fixed)

- Không có. Plan 05-04 chỉ tạo 4 file mới, không touch file pre-existing → không lộ regression mới. DEF-05-01 (cocoindex Environment re-open) + DEF-05-02 (test_watchdog.py fixture `hubs.code`) vẫn deferred — Plan 05-04 KHÔNG có integration test (test mandatory E4 ở Plan 05-06) nên không chạm DEF-05-01; KHÔNG touch `test_watchdog.py` nên không liên quan DEF-05-02.

## Threat Model Coverage

Tất cả threat `mitigate` trong `<threat_model>` của plan đã được thực thi:

- **T-05-04-01 (EoP — viewer/editor gọi user CRUD admin-only):** Mọi endpoint trong `routers/users.py` dùng `Depends(require_role("admin"))` → viewer/editor nhận 403 `FORBIDDEN`. 7 endpoint admin-only.
- **T-05-04-02 (EoP — viewer update profile user khác qua :id):** `routers/profile.py` KHÔNG nhận `:id` param — `user_id` LUÔN từ JWT (`user.id`). Route smoke test assert KHÔNG route nào có `{` path param. Viewer chỉ truy cập được profile của chính mình.
- **T-05-04-03 (Info Disclosure — password_hash leak):** `UserResponse` Pydantic schema KHÔNG có field `password_hash`; `_USER_SELECT_COLS` KHÔNG SELECT `password_hash`. Audit payload `user.create` chỉ `{email, role}` — KHÔNG password.
- **T-05-04-04 (Info Disclosure — reset token leak qua API):** `reset_password` endpoint trả message generic ("Token reset đã sinh (xem console log...)"); token CHỈ qua `logger.info` console (USER-02 M2). Service `reset_password` return token nhưng router KHÔNG đưa vào response body.
- **T-05-04-05 (Spoofing — đổi mật khẩu không biết mật khẩu cũ):** `change_password_self` gọi `verify_password(old_password, hash)` trước UPDATE — sai → return `False` → router trả 400 `INVALID_PASSWORD`.
- **T-05-04-06 (Tampering — SQL injection qua search/email/name):** Mọi raw SQL qua `text()` + named bind params; search dùng `email ILIKE :search OR full_name ILIKE :search` parametrized. WHERE-clause builder chỉ ghép fragment cố định nội bộ — KHÔNG nội suy input user.
- **T-05-04-07 (Spoofing — 2 user trùng email):** `create` catch `IntegrityError` (unique constraint `users.email` Phase 2) → raise `UserConflictError` → router trả 409 `EMAIL_CONFLICT`.

## Threat Flags

Không phát hiện threat surface mới ngoài `<threat_model>` của plan. 4 file mới đều là CRUD layer chuẩn — user router admin-only, profile router self-scoped (KHÔNG :id), service raw SQL parametrized, schema field-restricted (KHÔNG password_hash). Router CHƯA mount vào `main.py` (wiring Plan 05-06) nên chưa expose endpoint runtime.

## Known Stubs

Không có stub. Cả 4 file có data source thật: schema map đúng cột DB (migration 0003 — `users.phone/department/avatar_url/status`), service raw SQL trên bảng thật (`users`/`user_hubs`), router gọi service thật. Router chưa mount main.py là wiring defer có chủ đích (Plan 05-06 Wave 4), KHÔNG phải stub — `routers/users.py` + `routers/profile.py` export `router` sẵn sàng `include_router`.

`failed_login_count = 0` trong `UserResponse` là hằng có chủ đích (KHÔNG có cột DB — M2 chưa track failed login count; defer), KHÔNG phải stub data — ghi rõ trong plan interface note.

## TDD Gate Compliance

Plan type là `execute` (KHÔNG phải `type: tdd`); không task nào có `tdd="true"`. Verify qua `ruff check` + `mypy --strict` + route smoke test (acceptance criteria mỗi task). Integration test E4 mandatory cho mutation endpoint là scope Plan 05-06 (Wave 4). Gate RED→GREEN không áp dụng.

## Self-Check: PASSED

- FOUND: api/app/schemas/users.py
- FOUND: api/app/services/user_service.py
- FOUND: api/app/routers/users.py
- FOUND: api/app/routers/profile.py
- FOUND commit: 00ff3b4 (Task 1)
- FOUND commit: 31b6ea5 (Task 2)
- FOUND commit: 4192f22 (Task 3)
