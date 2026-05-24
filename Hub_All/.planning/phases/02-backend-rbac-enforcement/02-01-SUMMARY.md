---
phase: 02-backend-rbac-enforcement
plan: 01
subsystem: backend-rbac
tags: [DEP-01, validator, hub_admin, RBAC, dependency, async, unit-test]
requirements_completed: [DEP-01]
requires:
  - 01-02 (get_effective_role helper từ app.auth.role)
provides:
  - assert_hub_admin_for validator function (BLOCKING dep cho Wave 2 Plan 02-02 + 02-03 + Wave 3 Plan 02-04)
  - Envelope code HUB_ADMIN_REQUIRED mới (D-V3.1-Phase2-B LOCKED — phân biệt với FORBIDDEN existing)
affects:
  - api/app/auth/dependencies.py (extend — KHÔNG break Phase 1 + Phase 3 SSO + Phase 6 SETTINGS chain)
tech-stack:
  added: []
  patterns:
    - "Hybrid validator function (KHÔNG Depends factory) — D-V3.1-Phase2-D LOCKED cho hub_id ở body POST/PATCH"
    - "Force keyword-only signature (Pattern G — `*` PEP 570 force named call)"
    - "AsyncMock(AsyncSession) factory carry forward Plan 01-02 test_role_helper.py"
    - "patch(\"app.auth.dependencies.get_effective_role\") tại module nơi import (NOT app.auth.role) cho Test 5"
    - "Exception chain `raise HTTPException(...) from e` preserve UserNotFoundError traceback"
key-files:
  created:
    - api/tests/unit/test_require_hub_admin_for.py (5 unit test PASS — cover D-V3.1-Phase2-D LOCKED)
  modified:
    - api/app/auth/dependencies.py (+95 lines: 1 import line + 1 async function ~80 lines)
decisions:
  - "D-V3.1-Phase2-B LOCKED: envelope code 'HUB_ADMIN_REQUIRED' mới (phân biệt với FORBIDDEN existing — cho Phase 3 FE-01 switch UX)"
  - "D-V3.1-Phase2-D LOCKED: hybrid pattern validator function (NOT Depends factory) — vì hub_id nằm trong body POST/PATCH, FastAPI Depends inject TRƯỚC body parse"
  - "Force keyword-only signature `*, user, db, target_hub_id` — caller MUST name explicit (tránh positional bug khi thêm params giữa)"
  - "Defensive UserNotFoundError → catch + raise 403 HUB_ADMIN_REQUIRED (KHÔNG leak 404 → user_id existence không leak)"
metrics:
  duration_seconds: 180
  duration_human: "~3 phút (2 atomic commit + 5 test PASS)"
  tasks_completed: 2
  files_changed: 2
  completed_at: "2026-05-24T03:30:29Z"
---

# Phase 02 Plan 01: DEP-01 assert_hub_admin_for Validator Function Summary

## One-liner

Thêm async validator function `assert_hub_admin_for(*, user, db, target_hub_id) -> None` ở `api/app/auth/dependencies.py` với 5 unit test PASS, dùng envelope D6 mới `HUB_ADMIN_REQUIRED` (BLOCKING dep cho Wave 2 Plan 02-02 + 02-03 router refactor + Wave 3 Plan 02-04 service signature).

## What Shipped

### Task 1 — `assert_hub_admin_for` validator function (commit `70c78f3`)

**File modified:** `Hub_All/api/app/auth/dependencies.py` (+95 dòng — 1 import + 1 async function)

- Thêm import `from app.auth.role import UserNotFoundError, get_effective_role` (carry forward Plan 01-02 ROLE-04 helper).
- Append `async def assert_hub_admin_for(*, user, db, target_hub_id) -> None` SAU `require_role` closure factory (line 333), TRƯỚC `class UserWithHubs` — vị trí logical: cùng nhóm dependency RBAC.
- 5 case logic D-V3.1-Phase2-D LOCKED:
  1. **CASE 1 super admin bypass** — `user.role == "admin"` → `return` ngay (KHÔNG call DB query — performance + security guarantee).
  2. **CASE 2 hub_admin đúng** — `get_effective_role(db, user.id, target_hub_id) == "hub_admin"` → return None implicit.
  3. **CASE 3 hub_admin sai hub** — effective role ≠ 'hub_admin' (vd 'viewer' fallback global) → raise 403 HUB_ADMIN_REQUIRED.
  4. **CASE 4 viewer/editor** — effective role 'viewer' / 'editor' → raise 403 HUB_ADMIN_REQUIRED (cùng branch CASE 3).
  5. **CASE 5 UserNotFoundError defensive** — `get_effective_role` raise → catch + raise 403 HUB_ADMIN_REQUIRED with `from e` exception chain (KHÔNG leak 404 → tránh information disclosure user_id existence).
- Force keyword-only signature `*, user, db, target_hub_id` (Pattern G — caller MUST name explicit).
- Docstring tiếng Việt đầy đủ: purpose, logic 5 case, args, returns, raises, usage example, threat model 3 STRIDE threat.

### Task 2 — 5 unit test PASS (commit `76629c3`)

**File created:** `Hub_All/api/tests/unit/test_require_hub_admin_for.py` (+173 dòng)

- 2 helper factory: `_make_session(*fetchone_returns)` AsyncMock(AsyncSession) builder + `_make_user(role)` SimpleNamespace fixture.
- 5 `@pytest.mark.asyncio` test cover 5 case D-V3.1-Phase2-D:
  1. `test_super_admin_bypass_returns_none_without_db_call` — verify `session.execute.call_count == 0` (bypass guarantee).
  2. `test_hub_admin_correct_hub_returns_none` — mock 1 query `('hub_admin',)` → no raise.
  3. `test_hub_admin_wrong_hub_raises_403_hub_admin_required` — mock 2 query `(None, ('editor',))` → 403 + envelope code assert.
  4. `test_viewer_not_hub_admin_raises_403_hub_admin_required` — `user.role='viewer'` + 2 query `(None, ('viewer',))` → 403.
  5. `test_user_not_found_raises_403_not_404_defensive` — `patch("app.auth.dependencies.get_effective_role", new=AsyncMock(side_effect=UserNotFoundError(...)))` → 403 + verify `exc_info.value.__cause__` là `UserNotFoundError` (exception chain preserve).
- Pure mock — KHÔNG import `from app.db.session` (T-01-03-03 mitigation tránh accidentally hit real DB).

**Verification:**
```
cd Hub_All/api && python -m pytest tests/unit/test_require_hub_admin_for.py -x --tb=short
============================== 5 passed, 1 warning in 4.55s ===========================
```

## Carry Forward Patterns

| Pattern | Source | Reuse in Plan 02-01 |
|---------|--------|---------------------|
| AsyncMock(AsyncSession) factory `_make_session` | Plan 01-02 `tests/unit/test_role_helper.py:24-42` | `test_require_hub_admin_for.py:38-55` — y nguyên signature + behavior |
| `pytest.raises(HTTPException)` + `assert exc_info.value.detail["code"]` | Plan 06-03 `tests/unit/test_require_internal_auth.py` | Test 3 + 4 + 5 assert envelope code |
| `SimpleNamespace` user duck-type | Plan 06-03 require_internal_auth test | `_make_user(role)` helper |
| Force keyword-only signature `*` (Pattern G) | Plan 04-02..06 service signatures | `assert_hub_admin_for(*, user, db, target_hub_id)` |
| Envelope D6 `detail={code, message}` | Plan 03-03 SSO-04 `CROSS_HUB_ACCESS_DENIED` + Plan 06-03 `INTERNAL_AUTH_FAIL` | `HUB_ADMIN_REQUIRED` mới (D-V3.1-Phase2-B LOCKED) |
| Exception chain `raise ... from e` | Plan 03-02 JWKSCache + Plan 04-03 sync worker | Defensive `UserNotFoundError → HTTPException 403` chain |

## Deviations from Plan

**None — plan executed exactly as written.**

Cả Task 1 và Task 2 thực hiện theo chính xác content `<action>` section của plan 02-01-PLAN.md. Function body, test code, commit message theo template plan đề xuất.

## Threat Model Coverage

| Threat ID | Description | Mitigation | Status |
|-----------|-------------|------------|--------|
| T-02-01-01 | Spoofing user object giả | `user` từ `Depends(get_current_user)` trusted chain | ✓ Mitigated (upstream contract) |
| T-02-01-02 | SQL injection hub_id body input | `get_effective_role` named bind params (T-01-02-01 carry forward Plan 01-02) | ✓ Mitigated (Plan 01-02 helper) |
| T-02-01-03 | Information Disclosure user_id qua 404 | UserNotFoundError → catch + 403 HUB_ADMIN_REQUIRED (KHÔNG 404) | ✓ Mitigated (Test 5) |
| T-02-01-04 | Elevation super admin bypass abuse | M2 baseline 15min JWT expiry + admin demote qua admin CRUD UPDATE | ✓ Mitigated (M2 + v3.1 D-V3.1-01 LOCKED) |
| T-02-01-05 | DoS get_effective_role DB load mỗi request | pgvector index user_hubs composite PK + M2 baseline tolerate | accept (defer v4.0 cache) |

## Wave 2 + Wave 3 Consumption Ready

Plan 02-01 ship HOÀN TẤT — Wave 2 (Plan 02-02 + 02-03) và Wave 3 (Plan 02-04) có thể IMPORT:
```python
from app.auth.dependencies import assert_hub_admin_for
```

5 router endpoint users.py (POST create / GET list / PATCH role / PATCH status / DELETE) ở Plan 02-03 sẽ refactor:
```python
async def create_user(req, user=Depends(get_current_user), db=Depends(get_session), ...):
    await assert_hub_admin_for(user=user, db=db, target_hub_id=req.hub_id)  # DEP-03 inline
    # ... rest of handler
```

3 service signature (user_service.create + user_service.delete + hub_service callsites) ở Plan 02-04 sẽ thêm `actor_role: str + actor_hub_id: str | None` params (Pattern G), inject vào `build_audit_payload(...)`.

## Self-Check: PASSED

**Files exist:**
- `Hub_All/api/app/auth/dependencies.py`: FOUND (+95 lines change, syntax valid)
- `Hub_All/api/tests/unit/test_require_hub_admin_for.py`: FOUND (173 lines, 5 tests PASS)

**Commits verified:**
- `70c78f3`: FOUND `feat(02-01): assert_hub_admin_for validator function (DEP-01)`
- `76629c3`: FOUND `test(02-01): 5 unit test assert_hub_admin_for D-V3.1-Phase2-D LOCKED`

**Acceptance criteria (Task 1):**
- `async def assert_hub_admin_for(*` keyword-only signature: VERIFIED grep line 339-340
- Import `from app.auth.role import UserNotFoundError, get_effective_role`: VERIFIED
- `"HUB_ADMIN_REQUIRED"` ≥ 2 lần: VERIFIED (5 occurrences total)
- `if user.role == "admin": return` (CASE 1 bypass): VERIFIED
- `except UserNotFoundError as e:` (CASE 5 defensive): VERIFIED
- `if effective != "hub_admin":` (CASE 3-4 reject): VERIFIED
- `D-V3.1-Phase2-D` mention docstring (traceability): VERIFIED
- Syntax Python valid: VERIFIED (ast.parse exit 0)
- Importable async coroutine runtime: VERIFIED

**Acceptance criteria (Task 2):**
- 5 `@pytest.mark.asyncio` async test: VERIFIED
- `from app.auth.dependencies import assert_hub_admin_for`: VERIFIED
- `from app.auth.role import UserNotFoundError`: VERIFIED
- `def _make_session(` factory: VERIFIED
- `pytest.raises(HTTPException)` ≥ 3 lần: VERIFIED (Test 3 + 4 + 5)
- `"HUB_ADMIN_REQUIRED"` ≥ 3 lần assert: VERIFIED
- `session.execute.call_count == 0` (Test 1 bypass guarantee): VERIFIED
- `with patch(` (Test 5 force UserNotFoundError): VERIFIED
- `exc_info.value.__cause__` (Test 5 exception chain): VERIFIED
- `from app.db.session` NOT imported (T-01-03-03 mitigation): VERIFIED
- 5 tests PASS pytest exit 0: VERIFIED (`5 passed, 1 warning in 4.55s`)

---

*Plan 02-01 ship: 2026-05-24 — Phase 02-backend-rbac-enforcement Wave 1 BLOCKING done. Next: Wave 2 parallel (Plan 02-02 + 02-03).*
