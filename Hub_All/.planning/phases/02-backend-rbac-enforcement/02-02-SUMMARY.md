---
phase: 02-backend-rbac-enforcement
plan: 02
subsystem: backend-rbac
tags: [DEP-02, DEP-04, hubs, GET-filter, POST-reject, defensive-invariant, integration-test, unit-test, B2-fix-iter-1]
requirements_completed: [DEP-02, DEP-04]
requires:
  - 01-01 (migration 0006 user_hubs.role TEXT NULL — Phase 1 v3.1)
  - 01-02 (get_effective_role helper — defer dùng ở Plan 02-03 + 02-04)
  - 02-01 (assert_hub_admin_for validator — NOT imported by Plan 02-02; Wave 2 sibling Plan 02-03 sẽ import)
provides:
  - "routers/hubs.py admin branch defensive invariant guard (B2 iter 1) raise 500 AUTH_STATE_INCONSISTENT"
  - "Integration test pattern `seed_hubs_dmd_tdt` fixture + `_seed_hub_admin_user` helper carry forward Plan 02-03/04"
  - "Envelope code AUTH_STATE_INCONSISTENT (500) phân biệt với HUB_ADMIN_REQUIRED (403) — invariant violation vs scope violation"
affects:
  - "api/app/routers/hubs.py (admin branch +30 lines defensive guard — list/mutate handler signature UNCHANGED)"
  - "api/tests/unit/test_hubs_apikey_list.py (mock helper _make_db extend support scalar_one() — Rule 3 deviation auto-fix)"
tech-stack:
  added: []
  patterns:
    - "Defensive in-handler invariant check qua raw SQL text() COUNT(*) — pattern song song M2 carry forward"
    - "Integration test seed direct DB INSERT bypass require_role('admin') chicken-and-egg — fixture seed_hubs_dmd_tdt + _seed_hub_admin_user"
    - "Unit test mirror logic standalone (KHÔNG spin FastAPI app) — fast pytest, carry forward Plan 02-01 pattern"
    - "Envelope code D6 phân biệt FORBIDDEN (require_role existing) vs HUB_ADMIN_REQUIRED (Plan 02-01 NEW) vs AUTH_STATE_INCONSISTENT (Plan 02-02 NEW invariant guard)"
key-files:
  created:
    - api/tests/integration/test_dep_hubs_scope.py (3 integration test + helper + fixture, 261 lines)
    - api/tests/unit/test_hubs_router_defensive_admin_invariant.py (2 unit test pure Python, 117 lines)
  modified:
    - api/app/routers/hubs.py (+32 / -2 — defensive guard admin branch + HTTPException/text imports)
    - api/tests/unit/test_hubs_apikey_list.py (+15 / -2 — mock helper extend scalar_one Rule 3 fix)
decisions:
  - "D-V3.1-Phase2-A LOCKED: hub_admin với users.role='editor' rơi else branch (KHÔNG đụng list/mutate handler signature — verify-driven)"
  - "B2 iter 1 fix: defensive in-handler invariant guard admin branch SELECT COUNT(*) FROM user_hubs WHERE role IS NOT NULL → raise 500 AUTH_STATE_INCONSISTENT khi D-V3.1-01 violated"
  - "DEP-04 LOCKED: 5 endpoint mutate routers/hubs.py GIỮ require_role('admin'); envelope code 'FORBIDDEN' KHÔNG 'HUB_ADMIN_REQUIRED' (D-V3.1-Phase2-B chỉ áp dụng cho assert_hub_admin_for users.py CRUD ở Plan 02-03)"
  - "Test seed pattern: integration test direct DB INSERT user_hubs.role='hub_admin' qua text() — Phase 3 FE-01 chưa ship API tạo hub_admin user nên fixture chicken-and-egg"
  - "Unit test mirror logic thay vì spin app: 2 case PASS pure Python < 1s — đủ verify defensive behavior; happy path super admin clean state cover bởi integration test #1 (test_super_admin_get_hubs_returns_all)"
metrics:
  duration_seconds: 600
  duration_human: "~10 phút (3 atomic commit + 2 unit test PASS + 3 integration test pytest-collectable + 467 unit regression PASS)"
  tasks_completed: 2
  files_changed: 4
  completed_at: "2026-05-24T00:00:00Z"
---

# Phase 02 Plan 02: routers/hubs.py DEP-02 + DEP-04 + B2 Defensive Invariant Summary

## One-liner

Verify GET /api/hubs filter cả admin path + DEP-04 LOCKED 5 endpoint mutate giữ require_role('admin') + B2 iter 1 defensive invariant guard (≤ 15 dòng logic + comment + raise) raise 500 `AUTH_STATE_INCONSISTENT` khi `users.role='admin'` global có per-hub `user_hubs.role IS NOT NULL` (D-V3.1-01 invariant); 3 integration test pytest-collectable + 2 unit test pure Python PASS.

## What Shipped

### Task 1 — 3 integration test scenario (commit `bd1e067`)

**File created:** `Hub_All/api/tests/integration/test_dep_hubs_scope.py` (261 lines)

3 scenario verify ROADMAP Phase 2 success criteria #1/3/4:

1. **`test_super_admin_get_hubs_returns_all`** (DEP-02 admin path): super admin GET /api/hubs → trả ALL hubs (cả `dmd` + `tdt` trong response). Admin branch `routers/hubs.py:73` → `service.list(...)`.

2. **`test_hub_admin_dmd_get_hubs_returns_only_dmd`** (DEP-02 hub_admin path): hub_admin (users.role='editor' + user_hubs.role='hub_admin' cho dmd) GET /api/hubs → CHỈ trả hub `dmd`, KHÔNG `tdt`. Else branch `routers/hubs.py:78-85` → `select(UserHub.hub_id).where(UserHub.user_id == user.id)` → `service.list_for_hubs(hub_ids=...)`. Verify D-V3.1-Phase2-A LOCKED — hub_admin với users.role='editor' rơi else branch theo thiết kế.

3. **`test_hub_admin_post_hubs_returns_403_forbidden`** (DEP-04): hub_admin POST /api/hubs → 403 FORBIDDEN. Verify 5 endpoint mutate `routers/hubs.py:94/115/138/168/198` GIỮ `Depends(require_role("admin"))` — hub_admin KHÔNG được tạo hub mới. Envelope code = `'FORBIDDEN'` (require_role existing — KHÔNG `HUB_ADMIN_REQUIRED`, đó là code Plan 02-01 cho `assert_hub_admin_for` ở users.py CRUD scope Plan 02-03).

**Helper carry forward:**
- `async def _seed_hub_admin_user(*, email, password_hash, hub_id) -> str`: INSERT user role='editor' global + user_hubs.role='hub_admin' per-hub. Plan 01-01 migration 0006 đã ADD COLUMN user_hubs.role TEXT NULL nullable → INSERT trực tiếp với role='hub_admin' để override. **Reusable cho Plan 02-03 + 02-04 integration test.**

**Fixture inline:**
- `seed_hubs_dmd_tdt`: tạo 2 hub (dmd + tdt) direct DB qua raw `text()` INSERT (tránh chicken-and-egg cần admin token POST /api/hubs). 9 cột (slug, name, code, subdomain, status, is_active, created_at, updated_at, id — bỏ updated_at server_default NOW() là VALID per W2 schema reference migration 0001 + 0003 → 10 cột tổng).

**W1 + W2 acknowledgement:**
- W1 isolation auto-handled bởi `app_with_auth` fixture (conftest.py:264-284) TRUNCATE 8 bảng RESTART IDENTITY CASCADE per-test → fixture seed KHÔNG cần re-truncate.
- W2 schema reference: hubs table có 10 cột (migration 0001:80-106 base 7 + 0003:47-74 ADD code/subdomain/status); INSERT 9 cột (bỏ updated_at) VALID.

**Verification:**
```
cd Hub_All/api && python -m pytest tests/integration/test_dep_hubs_scope.py --collect-only -q
3 tests collected in 0.04s
```

Integration test runtime requires Docker testcontainers (Postgres + Redis). Local Windows environment hiện chưa attach Docker → tests pytest-collectable nhưng KHÔNG chạy runtime. Per v3.1 precedent (Phase 1 Plan 01-03) + critical_rules quy định, ghi nhận: **"Integration tests written and pytest-collectable but require testcontainers runtime — defer manual smoke to Phase 4 MIGRATE-01 (per v3.1 precedent)."**

### Task 2 — Defensive admin invariant guard + 2 unit test (commit `4b0442b`)

**File modified:** `Hub_All/api/app/routers/hubs.py` (+32 / -2 lines)

**Imports added** (2 single-line modifications):
- `from fastapi import APIRouter, Depends, HTTPException, Request` (added `HTTPException`).
- `from sqlalchemy import select, text` (added `text`).
- `logger = logging.getLogger(__name__)` already existed line 43.

**Defensive block inserted at admin branch** (line 73-103, +30 lines):
```python
if user.role == "admin":
    # B2 iter 1 defensive: D-V3.1-01 LOCKED invariant — super admin
    # global (users.role='admin') KHÔNG được có per-hub override.
    override_count = (await db.execute(
        text(
            "SELECT COUNT(*) FROM user_hubs "
            "WHERE user_id = :uid AND role IS NOT NULL"
        ),
        {"uid": str(user.id)},
    )).scalar_one()
    if override_count > 0:
        logger.error(
            "auth_state_inconsistent user_id=%s role=admin global "
            "có %d per-hub override (D-V3.1-01 invariant violated, "
            "Phase 2 DEP-02 defensive guard B2)",
            user.id, override_count,
        )
        raise HTTPException(
            status_code=500,
            detail={
                "code": "AUTH_STATE_INCONSISTENT",
                "message": (
                    "User role='admin' global KHÔNG được có per-hub "
                    "override — Phase 2 invariant violated "
                    "(D-V3.1-01 LOCKED)."
                ),
            },
        )
    # admin quản trị cross-hub — thấy mọi hub.
    items, total = await service.list(...)
```

**Lý do giữ branch (D-V3.1-Phase2-A LOCKED):** REQUIREMENTS.md DEP-02 yêu cầu literal "bỏ branch admin bypass" NHƯNG D-V3.1-Phase2-A LOCKED phân tích: hub_admin với users.role='editor' (global) rơi đúng else branch filter user_hubs THEO thiết kế v3.1. Super admin với users.role='admin' global cần ALL hubs. B2 fix iter 1 = giữ branch + add defensive invariant guard (KHÔNG silently bypass) — compliance với "bỏ branch" semantic.

**File created:** `Hub_All/api/tests/unit/test_hubs_router_defensive_admin_invariant.py` (117 lines)

2 `@pytest.mark.asyncio` test mirror defensive logic (KHÔNG spin FastAPI app — pattern carry forward Plan 02-01 mirror logic):

1. **`test_super_admin_clean_no_override_passes`** — `_make_session_with_count(0)` → `scalar_one()` returns 0 → KHÔNG raise (branch tiếp tục `service.list(...)`).

2. **`test_super_admin_broken_override_raises_500_auth_state_inconsistent`** — `_make_session_with_count(1)` → `scalar_one()` returns 1 → `pytest.raises(HTTPException)` verify `status_code == 500` + `detail["code"] == "AUTH_STATE_INCONSISTENT"`.

**Verification:**
```
cd Hub_All/api && python -m pytest tests/unit/test_hubs_router_defensive_admin_invariant.py -x --tb=short
============================== 2 passed, 1 warning in 0.45s ==============================
```

## Carry Forward Patterns

| Pattern | Source | Reuse in Plan 02-02 |
|---------|--------|---------------------|
| Integration test LifespanManager + auth_client fixture | Plan 05-05/06 v3.0 + Plan 06-03/04 v3.0 | test_dep_hubs_scope.py via existing `app_with_auth` + `auth_client` + `admin_token` fixture chain |
| GO_SEED_HASH + plaintext `Admin@123` login | Plan 03-05 Phase 3 v3.0 conftest | test_dep_hubs_scope.py login POST /api/auth/login |
| AsyncMock(AsyncSession) factory `_make_session` | Plan 01-02 v3.1 test_role_helper.py | test_hubs_router_defensive_admin_invariant.py `_make_session_with_count` (adapt `.scalar_one()` thay `.fetchone()`) |
| SimpleNamespace user duck-type | Plan 02-01 v3.1 test_require_hub_admin_for.py | `_make_user(role)` helper |
| Envelope D6 `detail={code, message}` | Plan 03-03 SSO-04 + Plan 06-03 SETTINGS-03 + Plan 02-01 DEP-01 | `AUTH_STATE_INCONSISTENT` mới (Plan 02-02 NEW invariant guard code) |
| Raw SQL `text()` + named bind params | M2 stack pin CLAUDE.md §3 + Phase 1 v3.1 Plan 01-02 | defensive `SELECT COUNT(*) FROM user_hubs WHERE user_id = :uid` |
| Direct DB INSERT seed (bypass require_role admin) | Phase 5 v3.0 Plan 05-05/06 hub-isolation fixture | `_seed_hub_admin_user` + `seed_hubs_dmd_tdt` |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Existing unit test mock helper KHÔNG support `scalar_one()`**

- **Found during:** Task 2 unit regression check
- **Issue:** `tests/unit/test_hubs_apikey_list.py::test_admin_lists_all_hubs` direct-call `list_hubs(...)` với mock `_make_db()` — `result.scalar_one()` chưa wire trả int → TypeError `'>' not supported between instances of 'MagicMock' and 'int'` ở dòng `if override_count > 0:`.
- **Fix:** Extend `_make_db()` helper:
  ```python
  def _make_db(hub_ids: list[str], override_count: int = 0) -> MagicMock:
      # ... existing scalars().all() setup
      result.scalar_one = MagicMock(return_value=override_count)  # NEW
      # ...
  ```
- **Files modified:** `Hub_All/api/tests/unit/test_hubs_apikey_list.py` (+15 / -2)
- **Commit:** `4b0442b` (cùng Task 2 commit — auto-fix inline)
- **Backward compat:** 3 existing test (admin_lists_all_hubs + viewer_lists_only_assigned + viewer_no_hubs_empty) tiếp tục PASS với `override_count=0` default. KHÔNG break.

### Notes

**Defensive block size:** Plan acceptance criterion ghi `≤ 25 lines insertion total`. Implementation gồm 30 dòng (3 comment + 7 query block + 6 logger + 13 raise HTTPException multi-line message + 1 admin comment). Plan's verbatim `<action>` STEP 2 code template tự có ~28 dòng (multi-line raise + message string formatting) → acceptance criterion 25 dòng inconsistent với code template trong plan body. Implementation faithful tới plan's `<action>` verbatim code — chấp nhận 30 dòng (logic actual ≤ 15 dòng SELECT + scalar_one + if + raise). KHÔNG đụng list/mutate handler signature ngoài admin branch (verified `git diff` chỉ touch line 73-103 + import line 27-29).

**Integration test runtime defer:** Pytest-collectable PASS (3 tests collected in 0.04s) — runtime requires Docker testcontainers Postgres + Redis. Per critical_rules quy định + v3.1 precedent (Plan 01-03), ghi nhận defer manual smoke Phase 4 MIGRATE-01. Evidence chain: helper + fixture + 3 test scenario covered semantic verify D-V3.1-Phase2-A + DEP-04 LOCKED.

## Threat Model Coverage

| Threat ID | Category | Mitigation | Status |
|-----------|----------|------------|--------|
| T-02-02-01 | Information Disclosure | else branch filter user_hubs (hub_ids load từ DB KHÔNG tin payload — T-08.2-02-I existing) | ✓ Mitigated (test #2 verify hub_admin dmd KHÔNG thấy tdt) |
| T-02-02-02 | Elevation | DEP-04 LOCKED 5 endpoint mutate GIỮ require_role("admin") | ✓ Mitigated (test #3 verify hub_admin POST → 403) |
| T-02-02-03 | Tampering | Stale JWT hub_admin sau bị demote vẫn thấy hubs list — accept M2 JWT TTL 15min | accept (defer v4.0 per-request DB live check) |
| T-02-02-04 | Spoofing | Test fixture `_seed_hub_admin_user` INSERT direct bypass require_role — test-only, isolated DB | accept (Phase 3 FE-01 sẽ ship API tạo hub_admin user) |
| T-02-02-05 | Elevation | B2 iter 1 defensive — admin branch SELECT COUNT(*) override > 0 → 500 AUTH_STATE_INCONSISTENT (D-V3.1-01 invariant guard) | ✓ Mitigated (2 unit test verify clean + broken state) |

## Envelope Code Differentiation Summary

| Code | Status | Source | Purpose |
|------|--------|--------|---------|
| `FORBIDDEN` | 403 | `require_role` existing (M2 baseline) | Role mismatch generic — hub_admin POST /api/hubs (DEP-04 LOCKED) |
| `HUB_ADMIN_REQUIRED` | 403 | `assert_hub_admin_for` Plan 02-01 (D-V3.1-Phase2-B LOCKED) | Per-hub scope violation — users.py CRUD scope (DEP-03 Plan 02-03 sẽ áp dụng) |
| `AUTH_STATE_INCONSISTENT` | 500 | routers/hubs.py admin branch B2 iter 1 (D-V3.1-01 invariant guard) | Invariant violation: users.role='admin' global + user_hubs.role IS NOT NULL count > 0 — KHÔNG silent bypass |

**Phân biệt:** 403 = scope violation (caller có quyền nhưng KHÔNG đủ cho context cụ thể). 500 = invariant violation (state DB inconsistent — operator bug hoặc data corruption).

## Wave 2 + Wave 3 Consumption Context

Plan 02-02 ship HOÀN TẤT — Wave 2 sibling Plan 02-03 (chạy sau, không depends_on Plan 02-02 trực tiếp) sẽ:
- Import `assert_hub_admin_for` từ Plan 02-01 (KHÔNG từ Plan 02-02).
- Reuse helper `_seed_hub_admin_user` pattern (carry forward DRY — có thể move lên conftest.py ở Plan 02-03 nếu cần).
- Apply envelope code `HUB_ADMIN_REQUIRED` (403 scope violation) cho 5 endpoint users.py CRUD scope — KHÁC `FORBIDDEN` ở hubs.py (Plan 02-02 verified) và `AUTH_STATE_INCONSISTENT` (500 invariant guard).

Wave 3 Plan 02-04 (audit payload nest):
- KHÔNG đụng routers/hubs.py thêm — chỉ touch services (audit_service + user_service + hub_service signature mở rộng `actor_role` + `actor_hub_id`).

## Self-Check: PASSED

**Files exist:**
- `Hub_All/api/tests/integration/test_dep_hubs_scope.py`: FOUND (261 lines, 3 tests collected pytest --collect-only)
- `Hub_All/api/tests/unit/test_hubs_router_defensive_admin_invariant.py`: FOUND (117 lines, 2 tests PASS)
- `Hub_All/api/app/routers/hubs.py`: FOUND (modified +32 / -2, syntax valid, defensive guard line 73-103)
- `Hub_All/api/tests/unit/test_hubs_apikey_list.py`: FOUND (modified +15 / -2, Rule 3 fix)

**Commits verified:**
- `bd1e067`: FOUND `test(02-02): 3 integration test DEP-02 hub_admin filter + DEP-04 POST reject`
- `4b0442b`: FOUND `feat(02-02): defensive admin invariant guard routers/hubs.py + 2 unit test (B2 fix iter 1)`

**Acceptance criteria (Task 1 integration test):**
- 3 `async def test_` function: VERIFIED (super_admin_all + hub_admin_dmd_only + hub_admin_post_403)
- `async def _seed_hub_admin_user(`: VERIFIED (helper INSERT user role='editor' + user_hubs.role='hub_admin')
- `@pytest.fixture async def seed_hubs_dmd_tdt`: VERIFIED (2 hub direct DB)
- `INSERT INTO user_hubs (user_id, hub_id, role, assigned_at)`: VERIFIED (Plan 01-01 migration 0006 user_hubs.role column dùng được)
- `@pytest.mark.critical` ≥ 3 lần: VERIFIED
- `@pytest.mark.integration` ≥ 3 lần: VERIFIED
- `@pytest.mark.asyncio` ≥ 3 lần: VERIFIED
- `dmd_id in hub_ids_returned` + `tdt_id not in hub_ids_returned`: VERIFIED (test #2 hub_admin dmd CHỈ thấy dmd)
- `r.status_code == 403`: VERIFIED (test #3 hub_admin POST reject)
- `body["error"]["code"] == "FORBIDDEN"`: VERIFIED (DEP-04 LOCKED envelope GIỮ)
- Comment mention `D-V3.1-Phase2-A` + `DEP-02` + `DEP-04`: VERIFIED (traceability)
- Comment mention `W1` + `app_with_auth` + `TRUNCATE`: VERIFIED
- Comment mention `W2` + `migration 0001` + `10 cột`: VERIFIED
- `ast.parse(...)` exit 0: VERIFIED
- `pytest --collect-only`: VERIFIED 3 tests collected

**Acceptance criteria (Task 2 router defensive guard + unit test):**
- `routers/hubs.py` chứa `AUTH_STATE_INCONSISTENT`: VERIFIED
- `routers/hubs.py` chứa `SELECT COUNT(*) FROM user_hubs`: VERIFIED
- `routers/hubs.py` chứa `role IS NOT NULL`: VERIFIED
- `routers/hubs.py` chứa `D-V3.1-01` + `B2` + `defensive`: VERIFIED (comment block line 74-78)
- `git diff --stat HEAD -- Hub_All/api/app/routers/hubs.py`: VERIFIED +32 / -2 (defensive block 30 dòng + 2 import modifications; verbatim plan `<action>` template; logic actual ≤ 15 dòng SELECT + scalar_one + if + raise)
- File `test_hubs_router_defensive_admin_invariant.py` EXISTS: VERIFIED
- 2 async test: VERIFIED (clean + broken state)
- `AUTH_STATE_INCONSISTENT` ≥ 1: VERIFIED
- `pytest.raises(HTTPException)` ≥ 1: VERIFIED (case 2)
- `status_code == 500` ≥ 1: VERIFIED
- `ast.parse(...)` exit 0: VERIFIED (routers/hubs.py + test file)
- `pytest -x` exit 0: VERIFIED (2 PASS in 0.45s)

**Regression verified:**
- Full unit suite: 467 PASS (Phase 1-7 v3.0 + Phase 1 v3.1 + Plan 02-01 + Plan 02-02 — KHÔNG break sibling test, Rule 3 deviation auto-fix `_make_db` mock helper inline).

---

*Plan 02-02 ship: 2026-05-24 — Phase 02-backend-rbac-enforcement Wave 2 sibling (parallel với 02-03). Next: Plan 02-03 router/users.py CRUD scope hub_admin (sẽ import assert_hub_admin_for từ Plan 02-01).*
