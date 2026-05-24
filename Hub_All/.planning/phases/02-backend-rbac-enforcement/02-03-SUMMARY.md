---
phase: 02-backend-rbac-enforcement
plan: 03
subsystem: backend-rbac
tags: [DEP-03, users-CRUD, hub_admin-scope, T-02-02-E-mitigation, B1-iter-1, DELETE-branch, cross-hub-deny, integration-test]
requirements_completed: [DEP-03]
requires:
  - 01-01 (migration 0006 user_hubs.role TEXT NULL + UserRole CHECK 4 value)
  - 02-01 (assert_hub_admin_for validator — Wave 1 BLOCKING dep)
provides:
  - "routers/users.py 4 endpoint refactor (POST create + PATCH role + GET list + DELETE B1 iter 1) scope hub_admin"
  - "Pydantic UserRole Literal 4 value (admin|hub_admin|editor|viewer) match migration 0006"
  - "T-02-02-E mitigation business logic block role='admin' escalation cho non-super caller"
  - "HUB_ID_REQUIRED envelope code (400) GET list non-super-admin enforce strict scope"
  - "CROSS_HUB_USER_DELETE_DENIED envelope code (403) MỚI B1 iter 1 DELETE user thuộc nhiều hub"
  - "7 integration test scenario verify ROADMAP Phase 2 success criteria #2 + B1 iter 1"
affects:
  - "api/app/schemas/users.py (UserRole Literal extend 1 dòng + comment update)"
  - "api/app/routers/users.py (4 endpoint refactor + import block + top docstring; 4 endpoint giữ require_role)"
  - "api/tests/integration/test_dep_users_scope.py (7 scenario integration test mới, 384 lines)"
tech-stack:
  added: []
  patterns:
    - "Hybrid scope check: Depends(get_current_user) + inline assert_hub_admin_for sau body parse (hub_id trong body POST/PATCH, KHÔNG path param)"
    - "Branch DELETE single-hub vs cross-hub: query user_hubs membership (named bind param :target_id) + 3-way branch len>1/==1/==0"
    - "Business logic block escalation: check req.role + user.role TRƯỚC service.change_role (T-02-02-E inline)"
    - "Envelope code D6 phân biệt 4 case: HUB_ADMIN_REQUIRED (scope violation) vs CROSS_HUB_USER_DELETE_DENIED (B1 iter 1 multi-hub) vs HUB_ID_REQUIRED (400 missing hub_id query) vs FORBIDDEN (require_role existing)"
    - "Integration test multi-hub seed helper: _seed_user_in_hubs(hub_ids=[a,b]) extend B1 iter 1 cross-hub test #6"
key-files:
  created:
    - api/tests/integration/test_dep_users_scope.py (384 lines, 7 tests PASS runtime)
  modified:
    - api/app/schemas/users.py (+3 / -1 — UserRole Literal 4 value + comment)
    - api/app/routers/users.py (+136 / -27 — 4 endpoint refactor + imports + docstring)
decisions:
  - "D-V3.1-Phase2-D LOCKED: hybrid pattern Depends(get_current_user) + inline assert_hub_admin_for cho 3 endpoint có hub_id trong body (POST/PATCH role) HOẶC query (GET list)"
  - "D-V3.1-Phase2-E LOCKED narrowed bởi B1 iter 1: DELETE refactor sang get_current_user + branch single-hub vs cross-hub; 3 endpoint còn lại (PATCH status + GET single + PUT + reset-password) GIỮ require_role super-only"
  - "T-02-02-E mitigation: PATCH role check `req.role == 'admin' and user.role != 'admin'` → 403 HUB_ADMIN_REQUIRED (KHÔNG FORBIDDEN — frontend FE-01 UX phân biệt)"
  - "B1 iter 1 envelope: CROSS_HUB_USER_DELETE_DENIED mới (403) cho multi-hub user case; HUB_ADMIN_REQUIRED reuse cho single-hub-other-scope + orphan case"
  - "Service layer (user_service.py) UNCHANGED ở plan này — Plan 02-04 sẽ refactor signature thêm actor_role + actor_hub_id (DEP-05 audit; bao gồm DELETE handler vì B1 iter 1 đã refactor DELETE từ require_role sang get_current_user)"
metrics:
  duration_seconds: 1500
  duration_human: "~25 phút (2 atomic commit + 7 integration test PASS runtime + 467 unit regression PASS)"
  tasks_completed: 2
  files_changed: 3
  completed_at: "2026-05-24T00:00:00Z"
---

# Phase 02 Plan 03: routers/users.py DEP-03 + T-02-02-E + B1 iter 1 DELETE Branch Summary

## One-liner

4 endpoint `routers/users.py` refactor scope hub_admin (DEP-03 + D-V3.1-Phase2-D/E LOCKED + B1 iter 1) — POST create + GET list + PATCH role + DELETE; thay `Depends(require_role("admin"))` bằng `Depends(get_current_user)` + inline `assert_hub_admin_for(target_hub_id)` cho 3 endpoint có hub_id; DELETE branch query `user_hubs` membership 3-way (single-own pass / cross-hub `CROSS_HUB_USER_DELETE_DENIED` mới / other-hub `HUB_ADMIN_REQUIRED`); T-02-02-E business logic block role escalation; `UserRole` Literal extend 4 value; 7 integration test PASS runtime + 467 unit regression PASS.

## What Shipped

### Task 1 — Source refactor schemas + routers (commit `2a42ad3`)

**File modified:** `Hub_All/api/app/schemas/users.py` (+3 / -1)

```python
# Phase 2 Plan 02-03 DEP-03 — extend 'hub_admin' match migration 0006 CHECK constraint
# 4 value (admin|hub_admin|editor|viewer); body validation cho PATCH role escalation.
UserRole = Literal["admin", "hub_admin", "editor", "viewer"]
```

`UserRole.__args__ == ("admin", "hub_admin", "editor", "viewer")` verified.

**File modified:** `Hub_All/api/app/routers/users.py` (+136 / -27)

**Imports extend:**
- `from app.auth.dependencies import (assert_hub_admin_for, get_current_user, get_redis, require_role,)`
- `from sqlalchemy import text` (B1 iter 1 cho DELETE membership query)

**4 endpoint refactor (Phase 2 Plan 02-03):**

1. **POST /api/users (`create_user`)** — `Depends(get_current_user)` + `db: AsyncSession` + inline `await assert_hub_admin_for(user=user, db=db, target_hub_id=req.hub_id)` TRƯỚC `service.create`. Email trùng giữ 409 EMAIL_CONFLICT.

2. **PATCH /api/users/:id/role (`change_user_role`)** — scope check + T-02-02-E mitigation business logic block:
   ```python
   await assert_hub_admin_for(user=user, db=db, target_hub_id=req.hub_id)
   if req.role == "admin" and user.role != "admin":
       return resp.forbidden(message="...", code="HUB_ADMIN_REQUIRED")
   ```

3. **GET /api/users (`list_users`)** — super admin bypass; non-super-admin BUỘC `hub_id` query (400 `HUB_ID_REQUIRED`) + `assert_hub_admin_for`:
   ```python
   if user.role != "admin":
       if hub_id is None:
           return resp.bad_request(..., code="HUB_ID_REQUIRED")
       await assert_hub_admin_for(user=user, db=db, target_hub_id=hub_id)
   ```

4. **DELETE /api/users/:id (`delete_user`) — B1 iter 1 branch single-hub vs cross-hub:**
   - Self-delete + LastAdmin guard PRESERVED.
   - Non-super-admin: query `SELECT hub_id FROM user_hubs WHERE user_id = :target_id` (named bind param T-01-02-01 mitigation):
     * `len > 1` → 403 `CROSS_HUB_USER_DELETE_DENIED` (envelope MỚI).
     * `len == 1` → `await assert_hub_admin_for(target_hub_ids[0])` — pass nếu đúng scope, raise HUB_ADMIN_REQUIRED nếu khác.
     * `len == 0` (orphan) → 403 `HUB_ADMIN_REQUIRED` (super-only).
   - NOT_FOUND + LAST_ADMIN paths PRESERVED.

**4 endpoint GIỮ `require_role("admin")` super-only (D-V3.1-Phase2-E LOCKED):**
- `GET /api/users/:id` — defer Phase 3.
- `PUT /api/users/:id` — defer Phase 3 (update profile fields KHÔNG có hub_id).
- `PATCH /api/users/:id/status` — D-V3.1-Phase2-E cross-hub op super-only.
- `POST /api/users/:id/reset-password` — USER-02 M2 carry forward, KHÔNG trong scope DEP-03.

**Top docstring update** ghi rõ 8 endpoint state mới + envelope code differentiation.

**Verification:**
```
cd Hub_All/api && python -c "from app.schemas.users import UserRole; assert UserRole.__args__ == ('admin', 'hub_admin', 'editor', 'viewer')"
OK UserRole 4 value

cd Hub_All/api && python -c "from app.routers.users import router; print('routes:', len(router.routes))"
OK router importable
routes: 8

cd Hub_All/api && python -m pytest tests/unit -q --tb=short
467 passed, 7 warnings in 49.79s
```

Grep counts:
- `await assert_hub_admin_for` = 4 (POST + PATCH role + GET list + DELETE single-hub branch).
- `HUB_ADMIN_REQUIRED` = 3 (PATCH role escalation + DELETE orphan + via assert_hub_admin_for raise reference).
- `CROSS_HUB_USER_DELETE_DENIED` = 1 (DELETE multi-hub case).
- `HUB_ID_REQUIRED` = 1 (GET list non-super-admin).
- `Depends(get_current_user)` = 4 (4 endpoint refactor).
- `require_role("admin")` = 4 (PATCH status + GET single + PUT + reset-password GIỮ).

### Task 2 — 7 integration test scenario (commit `e039573`)

**File created:** `Hub_All/api/tests/integration/test_dep_users_scope.py` (384 lines)

7 `@pytest.mark.critical @pytest.mark.integration @pytest.mark.asyncio` test:

| # | Test | Scenario | Expected | Envelope |
|---|------|----------|----------|----------|
| 1 | `test_super_admin_create_user_any_hub_returns_201` | Super admin POST hub_id=dmd | 201 | n/a (success) |
| 2 | `test_hub_admin_create_user_in_own_hub_returns_201` | Hub_admin dmd POST hub_id=dmd | 201 | n/a (success) |
| 3 | `test_hub_admin_create_user_in_other_hub_returns_403_hub_admin_required` | Hub_admin dmd POST hub_id=tdt | 403 | `HUB_ADMIN_REQUIRED` |
| 4 | `test_hub_admin_patch_role_admin_escalation_blocked_403` | Hub_admin dmd PATCH role='admin' | 403 | `HUB_ADMIN_REQUIRED` (T-02-02-E) |
| 5 | `test_hub_admin_delete_single_hub_user_of_own_hub_passes_200` | Hub_admin dmd DELETE user-thuộc-CHỈ-dmd | 200 | n/a (success B1 iter 1) |
| 6 | `test_hub_admin_delete_cross_hub_user_returns_403_cross_hub_denied` | Hub_admin dmd DELETE user-thuộc-dmd+tdt | 403 | `CROSS_HUB_USER_DELETE_DENIED` (B1 iter 1 mới) |
| 7 | `test_hub_admin_delete_user_in_other_hub_returns_403_hub_admin_required` | Hub_admin dmd DELETE user-thuộc-CHỈ-tdt | 403 | `HUB_ADMIN_REQUIRED` (assert_hub_admin_for raise) |

**Helper inline (carry forward Plan 02-02 — Plan 02-05 closeout có thể consolidate vào `conftest.py`):**
- `_seed_user_in_hubs(email, hub_ids: list[str], role)` — multi-hub variant cho B1 iter 1 cross-hub test #6.
- `_seed_user_in_hub(email, hub_id, role)` — shortcut single-hub.
- `_seed_hub_admin_user(email, hub_id)` — users.role='editor' global + user_hubs.role='hub_admin' per-hub.
- `_login(client, email, password)` — POST /api/auth/login + return access_token.

**Fixture inline:**
- `seed_hubs_dmd_tdt(app_with_auth)` — 2 hub (dmd + tdt) direct DB qua raw `text()` INSERT 9 cột (bỏ updated_at server_default NOW() — W2 valid).

**W1 + W2 + W4 + W5 acknowledgement:**
- W1 isolation auto-handled bởi `app_with_auth` fixture (conftest.py:264-284) TRUNCATE 8 bảng RESTART IDENTITY CASCADE per-test.
- W2 schema reference: hubs 10 cột (migration 0001:80-106 base 7 + 0003:47-74 ADD code/subdomain/status); INSERT 9 cột VALID.
- W4 coverage: integration runtime PASS 7/7; `--cov` flag triggered pre-existing numpy reload conflict (testcontainers re-execution env quirk) → defer coverage measurement explicit cho Plan 02-05 closeout.
- W5 FE breakage: GET /api/users non-super-admin → 400 HUB_ID_REQUIRED → Phase 3 FE-04 sequential dep; Plan 02-05 operator broadcast Slack/Email.

**Verification (runtime PASS Postgres + Redis testcontainers local):**
```
cd Hub_All/api && python -m pytest tests/integration/test_dep_users_scope.py -x --tb=short
============================== 7 passed, 8 warnings in 21.15s ==============================
```

## Carry Forward Patterns

| Pattern | Source | Reuse in Plan 02-03 |
|---------|--------|---------------------|
| Hybrid scope check (Depends + inline assert) | Plan 02-01 D-V3.1-Phase2-D LOCKED | 3 endpoint refactor (POST + PATCH role + GET list) |
| Branch query user_hubs membership | Phase 5 v3.0 + Plan 01-02 v3.1 named bind param | DELETE handler 3-way branch B1 iter 1 |
| Business logic block escalation TRƯỚC service | M2 baseline LastAdmin guard pattern | PATCH role T-02-02-E inline block |
| Integration test seed_hubs_dmd_tdt + _seed_hub_admin_user | Plan 02-02 test_dep_hubs_scope.py | Duplicate inline (Plan 02-05 consolidate option) |
| _seed_user_in_hubs multi-hub variant | NEW Plan 02-03 cho B1 iter 1 test #6 | Carry forward Plan 02-04 nếu cần test cross-hub khác |
| Envelope D6 differentiation | Plan 02-01 + 02-02 | `CROSS_HUB_USER_DELETE_DENIED` MỚI (B1 iter 1) |
| Raw SQL text() + named bind params | M2 CLAUDE.md §3 + Plan 01-02 v3.1 | DELETE membership query `:target_id` |

## Deviations from Plan

### Auto-fixed Issues

None — plan executed exactly as written.

### Notes

**1. [Note - Coverage measurement] `--cov` flag + numpy reload conflict**

- **Found during:** Task 2 acceptance criterion W4 coverage measurement
- **Issue:** `python -m pytest tests/integration/test_dep_users_scope.py tests/unit/test_require_hub_admin_for.py --cov=...` triggers numpy `ImportError: cannot load module more than once per process` khi mixed unit + integration với testcontainers re-execution under coverage plugin.
- **Fix attempted:** Run integration alone with `--cov` → same numpy conflict (testcontainers spawns sub-process re-import).
- **Resolution:** 7 integration test PASS standalone runtime; defer coverage measurement explicit cho Plan 02-05 closeout (Phase 4 MIGRATE-01 precedent — coverage tooling stabilization).
- **Evidence:** `pytest tests/integration/test_dep_users_scope.py -x --tb=short` PASS 7/7 in 21.15s; pre-existing env quirk, KHÔNG do plan code.

**2. [Note - Top docstring update]** Updated `routers/users.py` module docstring để reflect 8 endpoint state mới + envelope code differentiation (3 sub-bullet per phase scope). KHÔNG ảnh hưởng runtime behavior — chỉ documentation hygiene.

## Threat Model Coverage

| Threat ID | Category | Mitigation | Status |
|-----------|----------|------------|--------|
| T-02-03-01 | Elevation | PATCH role check `req.role == "admin" and user.role != "admin"` → 403 HUB_ADMIN_REQUIRED | ✓ Mitigated (test #4) |
| T-02-03-02 | Information Disclosure | GET list non-super-admin BUỘC hub_id query (400 HUB_ID_REQUIRED) + assert_hub_admin_for | ✓ Mitigated (handler logic verified) |
| T-02-03-03 | Tampering | M2 baseline KHÔNG có API direct edit user_hubs.role; production via PATCH /api/users/:id/role | accept (defer v4.0 explicit API) |
| T-02-03-04 | Elevation | B1 iter 1 DELETE branch: target multi-hub → 403 CROSS_HUB_USER_DELETE_DENIED; target other-hub → 403 HUB_ADMIN_REQUIRED | ✓ Mitigated (test #6 + #7) |
| T-02-03-05 | Elevation | D-V3.1-Phase2-E LOCKED: PATCH status GIỮ require_role("admin") super-only | ✓ Mitigated (require_role existing) |
| T-02-03-06 | Information Disclosure | Pydantic Literal extend 'hub_admin' backward compat (existing role values vẫn accept) | accept (Phase 3 FE-04 sẽ extend frontend type) |
| T-02-03-07 | Tampering | DELETE membership query named bind param `:target_id` (T-01-02-01 carry forward) | ✓ Mitigated (verified text() + dict params) |

## Envelope Code Differentiation Summary

| Code | Status | Source | Purpose |
|------|--------|--------|---------|
| `HUB_ADMIN_REQUIRED` | 403 | `assert_hub_admin_for` Plan 02-01 + Plan 02-03 PATCH role T-02-02-E + DELETE orphan | Per-hub scope violation HOẶC role escalation block |
| `CROSS_HUB_USER_DELETE_DENIED` | 403 | Plan 02-03 NEW B1 iter 1 DELETE handler | Target user thuộc nhiều hub → super admin only (KHÁC scope violation) |
| `HUB_ID_REQUIRED` | 400 | Plan 02-03 NEW GET list handler | Non-super-admin BUỘC pass hub_id query (DEP-03 enforce strict scope) |
| `FORBIDDEN` | 403 | `require_role` existing (M2) | 4 endpoint giữ super-only (PATCH status + GET single + PUT + reset-password) |
| `AUTH_STATE_INCONSISTENT` | 500 | Plan 02-02 routers/hubs.py B2 iter 1 | Invariant violation (KHÔNG áp dụng cho routers/users.py Plan 02-03) |
| `CANNOT_DELETE_SELF` | 403 | M2 carry forward (USER-04) | Self-DoS prevention DELETE handler |
| `LAST_ADMIN` | 409 | M2 carry forward (LastAdminError) | System phải còn ≥ 1 admin |

**Phân biệt clean:** 400 = client missing required param (HUB_ID_REQUIRED). 403 = scope/permission violation (HUB_ADMIN_REQUIRED / CROSS_HUB_USER_DELETE_DENIED / FORBIDDEN / CANNOT_DELETE_SELF). 409 = state conflict (EMAIL_CONFLICT / LAST_ADMIN). 500 = invariant violation (AUTH_STATE_INCONSISTENT — Plan 02-02 only).

## Wave 3 Consumption Context

Plan 02-03 ship HOÀN TẤT — Wave 3 Plan 02-04 (audit payload nest) sẽ:
- Refactor `user_service.py` signature thêm `actor_role` + `actor_hub_id` cho `create` + `change_role` + `delete` + `list` (DEP-05 audit traceability).
- DELETE handler đã refactor từ `require_role` sang `get_current_user` ở Plan 02-03 → Plan 02-04 service signature update applicable cho cả DELETE (KHÔNG riêng POST/PATCH).
- Helper `_seed_user_in_hubs` + `_seed_hub_admin_user` + `seed_hubs_dmd_tdt` có thể consolidate lên `conftest.py` ở Plan 02-04 hoặc 02-05 closeout (DRY refactor).

## Temporary FE Breakage (W5)

Non-super-admin users gọi `GET /api/users` qua existing M2/v3.0 frontend (chưa pass `hub_id` query) sẽ thấy 400 HUB_ID_REQUIRED. Acceptable per Phase 2 → Phase 3 sequential dep (FE-04 Phase 3 sẽ pass hub_id query). Plan 02-05 closeout sẽ update CLAUDE.md note operator broadcast Slack/Email trước Phase 3 FE-04 ship.

## Self-Check: PASSED

**Files exist:**
- `Hub_All/api/app/schemas/users.py`: FOUND (modified +3 / -1, UserRole 4 value)
- `Hub_All/api/app/routers/users.py`: FOUND (modified +136 / -27, 4 endpoint refactor + docstring)
- `Hub_All/api/tests/integration/test_dep_users_scope.py`: FOUND (384 lines, 7 tests PASS runtime)

**Commits verified:**
- `2a42ad3`: FOUND `feat(02-03): users.py 4 endpoint refactor hub_admin scope + DELETE branch single-hub vs cross-hub (DEP-03 + B1 iter 1)`
- `e039573`: FOUND `test(02-03): 7 integration test DEP-03 hub_admin CRUD scope + B1 iter 1 DELETE branch`

**Acceptance criteria (Task 1 source refactor):**
- `UserRole = Literal["admin", "hub_admin", "editor", "viewer"]`: VERIFIED
- Import `assert_hub_admin_for` + `get_current_user` + `text`: VERIFIED
- `await assert_hub_admin_for(...)` ≥ 4 lần (4 endpoint refactor): VERIFIED
- `if req.role == "admin" and user.role != "admin"` (T-02-02-E PATCH role): VERIFIED
- `"HUB_ADMIN_REQUIRED"` ≥ 2 lần: VERIFIED (3 occurrences)
- `"CROSS_HUB_USER_DELETE_DENIED"` ≥ 1 lần: VERIFIED (1 occurrence)
- `"HUB_ID_REQUIRED"` ≥ 1 lần: VERIFIED
- `Depends(get_current_user)` ≥ 4 lần: VERIFIED (exact 4)
- `Depends(require_role("admin"))` ≥ 3 lần: VERIFIED (4 occurrences — 4 endpoint giữ)
- `SELECT hub_id FROM user_hubs WHERE user_id`: VERIFIED (DELETE B1 iter 1 query)
- Comment mention DEP-03 + D-V3.1-Phase2-D/E + T-02-02-E + B1 iter 1: VERIFIED traceability
- `ast.parse(...)` exit 0: VERIFIED both files
- `UserRole.__args__ == ('admin', 'hub_admin', 'editor', 'viewer')`: VERIFIED
- `from app.routers.users import router`: VERIFIED (8 routes)

**Acceptance criteria (Task 2 integration test):**
- 7 `async def test_` function: VERIFIED (super_admin + own_hub + other_hub + escalation + del_single + del_cross + del_other)
- `_seed_hub_admin_user` + `_seed_user_in_hub` + `_seed_user_in_hubs`: VERIFIED 3 helper
- `seed_hubs_dmd_tdt` fixture: VERIFIED
- `@pytest.mark.critical/integration/asyncio` mỗi 7 lần: VERIFIED
- `r.status_code == 201` ≥ 2 (test #1 + #2): VERIFIED
- `r.status_code == 200` ≥ 1 (test #5 B1 iter 1): VERIFIED
- `r.status_code == 403` ≥ 4 (test #3 + #4 + #6 + #7): VERIFIED
- `body["error"]["code"] == "HUB_ADMIN_REQUIRED"` ≥ 3: VERIFIED (test #3 + #4 + #7)
- `body["error"]["code"] == "CROSS_HUB_USER_DELETE_DENIED"` ≥ 1: VERIFIED (test #6 B1 iter 1)
- `"role": "admin"` JSON body (test #4 escalation): VERIFIED
- `hub_ids=[dmd_id, tdt_id]` multi-hub seed (test #6): VERIFIED
- Comment mention T-02-02-E + D-V3.1-Phase2-E + DEP-03 + B1 iter 1: VERIFIED
- Comment mention W1 + app_with_auth + TRUNCATE: VERIFIED
- Comment mention W5 + FE breakage + HUB_ID_REQUIRED: VERIFIED
- `ast.parse(...)` exit 0: VERIFIED
- `pytest --collect-only`: VERIFIED 7 tests collected in 0.05s
- `pytest -x --tb=short` runtime: VERIFIED 7 PASS in 21.15s

**Regression verified:**
- Full unit suite: 467 PASS (KHÔNG break sibling test).

---

*Plan 02-03 ship: 2026-05-24 — Phase 02-backend-rbac-enforcement Wave 2 sibling (parallel với 02-02). Next: Plan 02-04 service layer signature refactor (DEP-05 audit actor_role + actor_hub_id) sẽ áp dụng cho cả DELETE handler vì Plan 02-03 đã refactor DELETE sang get_current_user theo B1 iter 1.*
