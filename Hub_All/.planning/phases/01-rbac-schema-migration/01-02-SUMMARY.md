---
phase: 01-rbac-schema-migration
plan: 02
subsystem: auth/rbac
tags: [auth, rbac, role-helper, async-sqlalchemy, pytest, asyncmock]
requirements: [ROLE-04]
dependency_graph:
  requires:
    - "Plan 01-01 migration 0006 ADD COLUMN user_hubs.role TEXT NULL + CHECK enum (semantic precondition — runtime DB column tồn tại; Plan 01-02 KHÔNG depend runtime, chỉ semantic alignment)"
  provides:
    - "api/app/auth/role.py::get_effective_role async helper (per-hub override + inherit global fallback)"
    - "api/app/auth/role.py::UserNotFoundError defensive exception"
  affects:
    - "Phase 2 dependency `require_hub_admin_for(hub_id)` (DEP-01) — import get_effective_role"
tech_stack:
  added: []
  patterns:
    - "Raw SQL via sqlalchemy.text() + named bind params `:user_id`, `:hub_id` (T-01-02-01 SQL injection mitigation — CLAUDE.md stack pin)"
    - "AsyncMock(spec=AsyncSession) + MagicMock result + fetchone() side_effect (test pattern carry forward test_require_role.py)"
    - "from __future__ import annotations để hỗ trợ `UUID | str` union syntax Python 3.10+ pin 3.12"
key_files:
  created:
    - "api/app/auth/role.py"
    - "api/tests/unit/test_role_helper.py"
  modified: []
decisions:
  - "Helper placement: module riêng `api/app/auth/role.py` (KHÔNG extend dependencies.py) — separation of concerns: role.py chứa business logic role resolution thuần KHÔNG FastAPI dep; dependencies.py chỉ chứa FastAPI dependency wrappers Depends-injected"
  - "Raw SQL `sqlalchemy.text()` + named bind params thay vì ORM model (User/UserHub) — chống dependency cycle Phase 2; KHÔNG import model attribute (model có thể lệch DB cho tới khi cần đọc qua ORM)"
  - "UserNotFoundError defensive raise (KHÔNG silent return string rỗng / role mặc định) — T-01-02-03 mitigation chống privilege escalation case stale user_id token; caller Phase 2 phải handle explicit"
  - "user_id + hub_id chấp nhận UUID hoặc str, convert str(uuid) trước khi bind — asyncpg auto-cast text→uuid trong Postgres; coverage carry forward Phase 3 SSO JWT claims.sub là str"
metrics:
  duration_seconds: 89
  completed_at: "2026-05-24T01:25:03Z"
  tasks_completed: 2
  files_created: 2
  files_modified: 0
  tests_added: 6
  tests_passing: 6
---

# Phase 1 Plan 02: get_effective_role helper + 6 unit test (ROLE-04) — Summary

One-liner: Module mới `app/auth/role.py` chứa async helper `get_effective_role(session, user_id, hub_id) → str` cover per-hub role override + inherit global fallback (D-V3.1-02 LOCKED) + 6 pytest async PASS (vượt 4-case minimum ROLE-04 với 1 defensive UserNotFoundError + 1 str args coverage).

## Mục tiêu đã đạt

ROLE-04 acceptance criteria đầy đủ:

1. ✅ Module `api/app/auth/role.py` tồn tại với `async def get_effective_role(session: AsyncSession, user_id: UUID | str, hub_id: UUID | str) -> str:` đúng signature D-V3.1-02 LOCKED.
2. ✅ Class `UserNotFoundError(Exception)` defensive exception declare top module.
3. ✅ Logic 2-step:
   - STEP 1: `SELECT role FROM user_hubs WHERE user_id=:user_id AND hub_id=:hub_id` — non-NULL → return ngay (per-hub override).
   - STEP 2: `SELECT role FROM users WHERE id=:user_id` — fallback inherit global / raise UserNotFoundError nếu missing.
4. ✅ Raw SQL `sqlalchemy.text()` + named bind params `:user_id`, `:hub_id` (T-01-02-01 SQL injection mitigation — CLAUDE.md convention).
5. ✅ KHÔNG import `User` / `UserHub` ORM model — chống dependency cycle Phase 2.
6. ✅ `from __future__ import annotations` để hỗ trợ `UUID | str` union syntax (Python 3.12 pin).
7. ✅ Docstring tiếng Việt có dấu với 4 example case minh hoạ.
8. ✅ 6 test pytest async + AsyncMock(spec=AsyncSession) PASS (vượt 4-case ROLE-04 minimum):
   - `test_super_admin_no_user_hubs_row_returns_admin` (case 4 — no membership fallback)
   - `test_super_admin_user_hubs_role_null_returns_admin` (case 1 — role NULL inherit)
   - `test_hub_admin_per_hub_override_returns_hub_admin` (case 2 — per-hub override)
   - `test_viewer_per_hub_override_returns_viewer` (case 3 — demote per-hub)
   - `test_user_not_found_raises_user_not_found_error` (case 5 — defensive)
   - `test_get_effective_role_accepts_str_uuid_args` (coverage str args)

## Files tạo mới

| File | Mục đích | LOC |
|------|---------|-----|
| `api/app/auth/role.py` | Module mới chứa `get_effective_role` async helper + `UserNotFoundError` exception. Raw SQL named bind params (T-01-02-01 mitigation). | ~110 |
| `api/tests/unit/test_role_helper.py` | 6 test pytest async — mock AsyncSession.execute với MagicMock result + fetchone() side_effect; KHÔNG cần DB runtime. | ~150 |

## Verification result

```bash
$ cd Hub_All/api && python -m pytest tests/unit/test_role_helper.py -x -v --tb=short
============================= test session starts =============================
platform win32 -- Python 3.12.9, pytest-8.4.2, pluggy-1.6.0
plugins: anyio-4.13.0, asyncio-0.26.0, cov-5.0.0, respx-0.23.1
asyncio: mode=Mode.AUTO
collecting ... collected 6 items

tests/unit/test_role_helper.py::test_super_admin_no_user_hubs_row_returns_admin PASSED [ 16%]
tests/unit/test_role_helper.py::test_super_admin_user_hubs_role_null_returns_admin PASSED [ 33%]
tests/unit/test_role_helper.py::test_hub_admin_per_hub_override_returns_hub_admin PASSED [ 50%]
tests/unit/test_role_helper.py::test_viewer_per_hub_override_returns_viewer PASSED [ 66%]
tests/unit/test_role_helper.py::test_user_not_found_raises_user_not_found_error PASSED [ 83%]
tests/unit/test_role_helper.py::test_get_effective_role_accepts_str_uuid_args PASSED [100%]

======================== 6 passed, 1 warning in 4.25s =========================
```

Smoke import verify:

```bash
$ cd Hub_All/api && python -c "from app.auth.role import get_effective_role, UserNotFoundError; import inspect; assert inspect.iscoroutinefunction(get_effective_role); assert issubclass(UserNotFoundError, Exception); print('OK')"
OK helper imports + async signature
```

## Decisions Made

### D-1: Helper placement — module riêng `api/app/auth/role.py`

Tách helper sang module mới thay vì append vào `dependencies.py`:

- **`dependencies.py`** giữ vai trò FastAPI dependency wrappers (Depends-injected — `get_current_user`, `require_role`, `get_current_user_for_hub_access`...).
- **`role.py`** chứa business logic role resolution thuần — KHÔNG biết FastAPI Request/Depends; chỉ nhận `AsyncSession` + 2 UUID; trả `str` hoặc raise.
- **Phase 2 DEP-01** sẽ `from app.auth.role import get_effective_role` để build dependency `require_hub_admin_for(hub_id)` — dependency layer wrap helper bằng Depends + HTTPException 403 envelope.

Lợi ích:
- Test helper KHÔNG cần FastAPI TestClient — pure AsyncMock.
- Reusable từ background task / CLI script / migration data fixer (KHÔNG bị trói vào HTTP request lifecycle).
- Tránh `dependencies.py` phình to (đã 535 LOC).

### D-2: Raw SQL `text()` thay vì ORM model

KHÔNG import `User` / `UserHub` SQLAlchemy ORM model:

- **Chống dependency cycle** — Phase 2 dependency có thể tạo cycle nếu helper import model (model → Base → engine → settings → ...).
- **Schema decouple** — Plan 01-01 đã add column `user_hubs.role TEXT NULL` qua migration 0006, nhưng SQLAlchemy `UserHub` model chưa update attribute (sẽ defer cho tới khi cần đọc qua ORM ở Phase 5+ admin CRUD per-hub role assign). Helper dùng raw SQL `text()` KHÔNG depend ORM attribute → an toàn lệch schema.
- **Named bind params** `:user_id`, `:hub_id` qua dict thay vì f-string concat → T-01-02-01 SQL injection mitigation (CLAUDE.md stack pin convention).
- **`str(uuid)` cast** — asyncpg auto-cast text → uuid trong Postgres khi compare với column `user_id UUID` / `id UUID`. Coverage carry forward Phase 3 SSO pattern: JWT `claims.sub` là str, KHÔNG UUID object.

### D-3: `UserNotFoundError` defensive raise

KHÔNG silent return string rỗng / role mặc định khi `users` row missing:

- **T-01-02-03 mitigation** — privilege escalation case stale user_id token (admin disable user nhưng JWT chưa expire; helper KHÔNG được phép default `'viewer'` vì có thể thành `'admin'` nếu downstream invert check).
- **Caller (Phase 2 `require_hub_admin_for`) phải handle explicit** — wrap thành 403 FORBIDDEN envelope (T-01-02-02 accept: KHÔNG leak user_id existence bằng 404 distinct từ 403).
- **Exception class** export top module — Phase 2 sẽ `from app.auth.role import UserNotFoundError` để catch riêng (KHÔNG bắt `Exception` chung).
- Message tiếng Việt mention `user_id_str` để debug log dễ trace.

### D-4: 6 test cover 4-case ROLE-04 + 1 defensive + 1 str args

Plan acceptance yêu cầu 4-case minimum; ship 6 case mạnh hơn:

- 4 case ROLE-04 chính: super_admin no-membership + super_admin role=NULL + hub_admin override + viewer demote.
- 1 case defensive: `UserNotFoundError` raise khi users row missing.
- 1 case coverage: str args (KHÔNG chỉ UUID object) — Phase 3 SSO carry forward.

Pattern test:
- `_make_session(*fetchone_returns)` helper factory — 1-liner build AsyncMock với sequence multiple execute() call (side_effect list).
- `@pytest.mark.asyncio` REQUIRED (pytest-asyncio đã cài Phase 3+ baseline).
- Assert `session.execute.call_count` để verify branch path (override case = 1 call; fallback case = 2 calls).
- Case 5 dùng `pytest.raises(UserNotFoundError, match=str(user_id))` verify error message contain user_id.

## Carry forward Phase 2 (DEP-01)

Phase 2 sẽ build dependency `require_hub_admin_for(hub_id)`:

```python
# Tham khảo Phase 2 (CHƯA implement — chỉ mô tả contract):
from app.auth.role import UserNotFoundError, get_effective_role

def require_hub_admin_for(
    hub_id_path: str,
) -> Callable[..., Awaitable[User]]:
    async def _dep(
        user: User = Depends(get_current_user_for_hub_access),
        db: AsyncSession = Depends(get_session),
    ) -> User:
        try:
            effective_role = await get_effective_role(db, user.id, hub_id_path)
        except UserNotFoundError as e:
            raise HTTPException(403, {"code": "FORBIDDEN", ...}) from e
        if effective_role not in ("admin", "hub_admin"):
            raise HTTPException(403, {"code": "FORBIDDEN", ...})
        return user
    return _dep
```

Phase 2 input contract:
- `user.id` lấy từ `get_current_user` (JWT verified, USER_DISABLED check).
- `hub_id_path` từ URL path param (untrusted query — KHÔNG fan-out cross-hub).
- Helper trả `str` → dependency check `in ("admin", "hub_admin")` → 403 nếu mismatch.
- `UserNotFoundError` → 403 FORBIDDEN (KHÔNG 404 — T-01-02-02 accept không leak existence).

## Deviations from Plan

None - plan executed exactly as written.

Plan 01-02 cung cấp đầy đủ code sample chi tiết (Task 1 + Task 2 block code complete) — executor chỉ paste-and-verify. KHÔNG có bug/scope creep/architectural decision phát sinh.

## Threat model verification

| Threat ID | Mitigation status |
|-----------|-------------------|
| T-01-02-01 (Tampering — SQL injection) | ✅ Raw SQL via `sqlalchemy.text()` + named bind params `:user_id`, `:hub_id`; KHÔNG f-string concat user input. Verify qua acceptance criteria "File chứa `:user_id` + `:hub_id`". |
| T-01-02-02 (Information Disclosure — user existence leak) | ⏸️ Accept — UserNotFoundError raise → Phase 2 dependency wrap thành 403 FORBIDDEN (KHÔNG 404 distinct). Phase 1 layer KHÔNG enforce; defer Phase 2 dependency. |
| T-01-02-03 (Elevation of Privilege — stale token) | ✅ UserNotFoundError raise (KHÔNG silent return); caller phải handle explicit. Verify qua case 5 test. |
| T-01-02-04 (Repudiation — no audit) | ⏸️ Accept — helper read-only; Phase 2 dependency layer audit ở `actor_role` payload (DEP-05). |

## Phase 1 progress

| Plan | Status | Date | REQ-ID |
|------|--------|------|--------|
| 01-01 — Alembic migration 0006 ADD COLUMN user_hubs.role | ✅ DONE | 2026-05-23 | ROLE-01..03 |
| 01-02 — get_effective_role helper + 6 unit test | ✅ **DONE** | **2026-05-24** | **ROLE-04** |
| 01-03 — Closeout docs (STATE/ROADMAP/REQUIREMENTS/CLAUDE.md) | ⏳ pending | — | — |

Phase 1 còn 1 plan (01-03 closeout) trước khi đóng phase. Plan 01-03 sẽ:
- Update `.planning/STATE.md` Phase 1 progress (2/3 → 3/3).
- Update `.planning/ROADMAP.md` v3.1 Phase 1 status DONE.
- Update `.planning/REQUIREMENTS.md` ROLE-01..04 mark `[x]`.
- Update `CLAUDE.md` v3.1 section reflect Phase 1 close + hub_admin role available.

## Self-Check: PASSED

- ✅ FOUND: `Hub_All/api/app/auth/role.py`
- ✅ FOUND: `Hub_All/api/tests/unit/test_role_helper.py`
- ✅ pytest 6/6 PASS (verified `tail -40` output above)
- ✅ Smoke import verify PASS (`python -c "from app.auth.role import ..."` exit 0)
- ✅ Commit hash sẽ ghi nhận sau khi `git commit` executed (commit step kế tiếp).
