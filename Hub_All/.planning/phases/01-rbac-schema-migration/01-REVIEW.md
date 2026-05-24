---
phase: 01-rbac-schema-migration
status: minor
reviewed: 2026-05-24T09:15:00Z
depth: deep
files_reviewed: 4
files_reviewed_list:
  - Hub_All/api/migrations/versions/0006_role_hub_admin.py
  - Hub_All/api/app/auth/role.py
  - Hub_All/api/tests/unit/test_role_helper.py
  - Hub_All/api/tests/integration/test_migration_0006_idempotent.py
findings:
  critical: 0
  high: 0
  medium: 3
  low: 5
  info: 4
total_findings: 12
---

# Phase 1 v3.1 RBAC Schema Migration — Code Review Report

**Reviewed:** 2026-05-24T09:15:00Z
**Depth:** deep (cross-file: migration ↔ helper ↔ test ↔ baseline 0001)
**Files Reviewed:** 4
**Status:** `minor` — KHÔNG blocking; 3 medium issue NÊN fix trước Phase 2 nhưng KHÔNG ngăn ship.

## Summary

Toàn bộ 4 file Phase 1 (migration 0006 + role helper + 6 unit test + 5 integration test) đạt chất lượng production-ready cho schema migration RBAC. Logic ROLE-01..04 đúng theo D-V3.1-01/02 LOCKED, idempotent guard đầy đủ 3 STEP, downgrade defensive RuntimeError đúng E-V3.1-1 trigger, parameterized SQL ngăn SQL injection. Pattern Iter 1 fix I-01 (monkeypatch DATABASE_URL + `get_settings.cache_clear()`) áp dụng nhất quán trong fixture integration test.

**Điểm mạnh:**
- Idempotent strategy 3-layer (Python introspect + DDL `IF NOT EXISTS` + `WHERE NOT EXISTS` audit guard) — defense-in-depth chống concurrent migration race.
- Downgrade defensive RuntimeError E-V3.1-1 trigger khi có row `role='hub_admin'` — đúng intent KHÔNG auto-delete data.
- Test coverage 11 case (6 unit + 5 integration) cover đủ 4-case ROLE-04 + 5 case migration idempotent + downgrade.
- Documentation in-code đầy đủ: docstring Vietnamese, threat model T-01-01-01..05 trace, semantic D-V3.1-02 LOCKED reference.
- SQL parameterization an toàn (`text() + dict params`) — không SQL injection.

**Concerns chính (cần fix Phase 2 hoặc Phase 4 MIGRATE-01):**
1. **MR-01 (Medium):** `atexit.register(_cleanup_cache)` trong fixture pytest accumulate handler — anti-pattern nên dùng `yield` fixture.
2. **MR-02 (Medium):** Downgrade inspector cache stale sau `op.execute()` STEP 1/2 — `get_columns()` STEP 3 introspect có thể MISS column vừa drop (Postgres dialect-dependent).
3. **MR-03 (Medium):** Inconsistent error handling — upgrade raise RuntimeError khi không tìm thấy CHECK constraint, downgrade chỉ SKIP — asymmetric semantic.

## Medium Issues

### MR-01: `atexit.register` trong fixture pytest gây accumulate handler

**File:** `Hub_All/api/tests/integration/test_migration_0006_idempotent.py:101-102`

**Issue:**
```python
import atexit
atexit.register(_cleanup_cache)  # safety net — không rely (test order dependency).
```

Mỗi lần fixture `alembic_cfg` được invoke (1 lần / test), `atexit.register` thêm 1 handler. Sau N test chạy, có N handler đăng ký — chạy SAU process exit (KHÔNG giúp test isolation runtime). Inline comment đã thừa nhận "safety net — không rely" → giá trị thực bằng 0 nhưng vẫn để code → noise + memory leak nhẹ + delay process shutdown.

Pytest fixture nên dùng `yield` pattern để cleanup runtime giữa các test (đảm bảo `get_settings.cache_clear()` chạy NGAY sau test, KHÔNG defer tới process exit).

**Fix:**
```python
@pytest.fixture
def alembic_cfg(test_db_url: str, monkeypatch: pytest.MonkeyPatch) -> Config:
    monkeypatch.setenv("DATABASE_URL", test_db_url)
    from app.config import get_settings
    get_settings.cache_clear()

    cfg_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "alembic.ini")
    )
    cfg = Config(cfg_path)

    yield cfg  # ← test chạy ở đây

    # Teardown — chạy NGAY sau test, KHÔNG defer process exit.
    get_settings.cache_clear()
```

Xoá `import atexit` + `atexit.register(_cleanup_cache)` + helper `_cleanup_cache` local.

---

### MR-02: Downgrade inspector cache stale sau STEP 1/2 op.execute

**File:** `Hub_All/api/migrations/versions/0006_role_hub_admin.py:229-247`

**Issue:** Downgrade flow:
1. STEP 1 (line 224): `op.execute("ALTER TABLE user_hubs DROP CONSTRAINT IF EXISTS ck_user_hubs_role_enum")`
2. STEP 2 (line 229-231): `user_hubs_columns = {col["name"] for col in inspector.get_columns("user_hubs")}` → CÓ thể MISS phản ánh column `role` đã drop ở STEP 1 nếu SQLAlchemy inspector cache snapshot ban đầu.
3. STEP 3 (line 241-247): `inspector.get_check_constraints("users")` — tương tự, cache có thể stale sau DROP COLUMN.

`sa.inspect(bind)` trả Inspector object có thể cache results theo PostgresSQL dialect implementation (xem `sqlalchemy.dialects.postgresql.PGInspector._reflect_*` — có `cache_ok` flag). KHÔNG có refresh call giữa op.execute và introspect next.

**Impact:** Trên hot rerun, downgrade có thể FAIL detect column vừa drop → SKIP message sai. Risk thực tế thấp vì test integration không hit edge này, nhưng pattern defensive bị suy yếu.

**Fix:** Refresh inspector sau mỗi DDL operation:
```python
def downgrade() -> None:
    bind = op.get_bind()
    # ... STEP 0 defensive check
    inspector = sa.inspect(bind)  # snapshot 1

    op.execute("ALTER TABLE user_hubs DROP CONSTRAINT IF EXISTS ck_user_hubs_role_enum")

    # Re-inspect sau DDL changes (defensive — chống stale cache).
    inspector = sa.inspect(bind)  # snapshot 2 ← MỚI
    user_hubs_columns = {col["name"] for col in inspector.get_columns("user_hubs")}
    if "role" in user_hubs_columns:
        op.execute("ALTER TABLE user_hubs DROP COLUMN role")

    inspector = sa.inspect(bind)  # snapshot 3 ← MỚI
    check_constraints = inspector.get_check_constraints("users")
    # ...
```

Hoặc dùng `bind.execute(sa.text("SELECT ..."))` raw query trực tiếp (KHÔNG qua inspector cache).

---

### MR-03: Asymmetric error semantic — upgrade RAISE, downgrade SKIP

**File:** `Hub_All/api/migrations/versions/0006_role_hub_admin.py:95-100` vs `249-250`

**Issue:** Upgrade khi không tìm thấy CHECK constraint `users.role`:
```python
if role_constraint_name is None:
    raise RuntimeError(
        "Không tìm thấy CHECK constraint users.role trong DB — "
        "schema baseline 0001 có thể chưa apply hoặc đã bị drop manual. "
        "Vui lòng chạy `alembic upgrade 0001` trước rồi re-run 0006."
    )
```

Downgrade cùng case chỉ print SKIP:
```python
if role_constraint_name is None:
    print("[0006 downgrade] SKIP users.role CHECK — constraint không tồn tại")
```

**Inconsistency:** Nếu CHECK constraint missing thì:
- Upgrade: schema corrupt → STOP fail-loud (đúng).
- Downgrade: cũng schema corrupt nhưng SKIP silent (sai semantic — operator KHÔNG biết DB ở state lạ).

**Fix:** Downgrade nên cũng RAISE RuntimeError trong case schema corrupt, hoặc cả 2 cùng SKIP với clear warning log. Khuyến nghị RAISE đối xứng:
```python
if role_constraint_name is None:
    raise RuntimeError(
        "[0006 downgrade] Không tìm thấy CHECK constraint users.role để restore — "
        "schema có thể đã bị drop manual hoặc đang ở state không xác định. "
        "Inspect schema manual trước khi tiếp tục rollback."
    )
```

## Low Issues

### LR-01: `payload->>'migration_revision'` JSONB lookup KHÔNG có index

**File:** `Hub_All/api/migrations/versions/0006_role_hub_admin.py:178-182`

**Issue:** `WHERE NOT EXISTS` guard SELECT FROM `audit_logs WHERE action='migration.role_seed' AND payload->>'migration_revision' = '0006'`. Bảng `audit_logs` chỉ có index `(action)` qua `ix_audit_logs_user_id_created_at` (composite) — KHÔNG có index trên `payload->>'migration_revision'`. JSONB lookup → seq scan.

**Impact:** Khi audit_logs nhỏ (Phase 1) — negligible. Khi audit_logs grow lên triệu row (production sau N tháng) → re-run idempotent check slow.

**Fix:** Migration KHÔNG cần fix (out of scope). Note cho Phase 4 MIGRATE-01: thêm partial index `CREATE INDEX ix_audit_logs_migration_seed ON audit_logs ((payload->>'migration_revision')) WHERE action LIKE 'migration.%'` nếu cần.

---

### LR-02: `NOW()` redundant với server_default

**File:** `Hub_All/api/migrations/versions/0006_role_hub_admin.py:177`

**Issue:** Bảng `audit_logs.created_at` có `server_default=sa.text("NOW()")` (xem baseline 0001 line 381-385). INSERT statement explicit dùng `NOW()` cho `created_at` — redundant với column default.

```sql
INSERT INTO audit_logs (action, target_type, payload, created_at)
SELECT
    'migration.role_seed',
    'schema',
    jsonb_build_object(...),
    NOW()  -- ← redundant; bỏ → dùng server_default
WHERE NOT EXISTS (...)
```

**Fix:** Bỏ `created_at` khỏi column list + value list:
```sql
INSERT INTO audit_logs (action, target_type, payload)
SELECT
    'migration.role_seed',
    'schema',
    jsonb_build_object(...)
WHERE NOT EXISTS (...)
```

Hoặc giữ explicit nếu intent là document — không bug, chỉ noise.

---

### LR-03: AsyncMock thiếu `spec=AsyncSession` — brittle test

**File:** `Hub_All/api/tests/unit/test_role_helper.py:35`

**Issue:** `session = AsyncMock()` không có `spec=AsyncSession` → test KHÔNG catch nếu helper gọi sai method (vd `session.exec` thay vì `session.execute`) — test pass nhầm.

**Fix:**
```python
from sqlalchemy.ext.asyncio import AsyncSession

def _make_session(*fetchone_returns: object) -> AsyncMock:
    session = AsyncMock(spec=AsyncSession)  # ← thêm spec
    # ...
```

---

### LR-04: Assertion `session.execute.call_count` brittle khi refactor

**File:** `Hub_All/api/tests/unit/test_role_helper.py:60, 77, 93, 111, 129`

**Issue:** 5 test assertion `assert session.execute.call_count == N`. Nếu refactor helper sang 1-shot SQL (`SELECT ... JOIN user_hubs LEFT ...` UNION ALL pattern) — semantically đúng nhưng call_count = 1 → test FAIL.

**Fix:** Thay assertion implementation-detail bằng assertion behavior. Acceptable trade-off cho v3.1 (helper KHÔNG dự định refactor); note nếu Phase 4+ tối ưu query.

---

### LR-05: Cleanup `DELETE FROM users WHERE email LIKE '...test.local'` chưa transaction-wrap

**File:** `Hub_All/api/tests/integration/test_migration_0006_idempotent.py:167-169, 254-260, 346-348`

**Issue:** Cleanup `DELETE FROM users WHERE email LIKE 'hubadmin_%@test.local'` chạy trong `finally` block — nếu test fail sau INSERT trước DELETE → leftover data. Pattern dùng `try/finally` đã defensive nhưng nếu connection bị drop (transaction roll back) thì DELETE KHÔNG chạy.

**Fix:** Acceptable cho v3.1 (test DB isolated, leftover data không ảnh hưởng production). Phase 4 MIGRATE-01 nên dùng pytest fixture `yield` pattern + transaction-wrap test data setup hoặc dùng `testcontainers` để fresh DB mỗi test.

## Info Items

### IR-01: Magic string `'hub_admin'` lặp lại nhiều nơi

**Files:** `0006_role_hub_admin.py:115, 149, 212`, `role.py:64`, test files

**Issue:** Role value `'admin'`, `'hub_admin'`, `'editor'`, `'viewer'` hardcode trong 4+ file. Nếu add role mới (vd `'auditor'`) phải sửa N nơi.

**Suggestion (defer v3.2):** Centralize trong module `app/auth/roles.py`:
```python
ROLES = ("admin", "hub_admin", "editor", "viewer")
ROLE_ADMIN = "admin"
ROLE_HUB_ADMIN = "hub_admin"
# ...
```

Migration vẫn phải hardcode SQL string (không thể import Python const vào DDL) — nhưng test + helper có thể reference constant.

---

### IR-02: `print()` thay vì structlog trong migration

**File:** `0006_role_hub_admin.py:104, 117, 129, 152, 184, 232, 234, 250, 257`

**Issue:** Migration dùng `print()` cho log operator visibility. Stack pin nói "structlog JSON" (CLAUDE.md §3 code conventions). Migration runtime CHƯA setup structlog → fallback `print()` reasonable.

**Suggestion:** Acceptable — migration là one-shot context, structlog overhead không cần thiết. Pattern carry forward Plan 04-01 (0005 cũng dùng print).

---

### IR-03: `UUID | str` type hint chỉ partial — thiếu `bytes`

**File:** `Hub_All/api/app/auth/role.py:41-43`

**Issue:** `user_id: UUID | str` — chấp nhận UUID hoặc str. Postgres asyncpg UUID column có thể trả về `uuid.UUID` instance qua `row[0]`. Test case 6 verify str — OK. Nhưng nếu caller pass `bytes` (vd from JWT base64-decoded) → `str(bytes_obj)` cho ra `b'...'` literal — sai.

**Suggestion:** Acceptable v3.1 — caller convention sử dụng UUID hoặc str từ JWT `sub` claim. Defensive: thêm `isinstance(user_id, (UUID, str))` assert hoặc dùng `TypeAlias`. Defer Phase 2 DEP-01 khi build dependency wrapper.

---

### IR-04: `UserNotFoundError` message expose `user_id` UUID

**File:** `Hub_All/api/app/auth/role.py:110-113`

**Issue:**
```python
raise UserNotFoundError(
    f"User {user_id_str!r} không tồn tại trong table users — "
    f"defensive guard (caller phải handle stale user_id token)"
)
```

Message log UUID user_id. UUID KHÔNG nhạy cảm (không phải PII) nhưng có thể log vào structlog → operator search forensic dễ. Caller phải đảm bảo KHÔNG echo exception message ra HTTP response (Phase 2 dependency sẽ catch + return generic 401).

**Suggestion:** Acceptable — UUID exposure low risk. Phase 2 DEP-01 wrapper PHẢI translate `UserNotFoundError` → generic 401 envelope `{success:false, data:null, error:{code:"AUTH_USER_NOT_FOUND"}, meta:null}` KHÔNG leak UUID ra response body (chỉ log server-side).

## File-by-file Notes

### `Hub_All/api/migrations/versions/0006_role_hub_admin.py` (270 LOC)

**Strengths:**
- 3 STEP idempotent guard đầy đủ (introspect Python + DDL `IF NOT EXISTS` + audit `WHERE NOT EXISTS`).
- Carry forward đúng pattern 0005 (raw SQL + introspect + Vietnamese print log tagged `[0006]`).
- Downgrade defensive RuntimeError E-V3.1-1 đúng intent.
- Threat model T-01-01-01..05 trace đầy đủ trong docstring.

**Issues:** MR-02 (inspector cache stale), MR-03 (asymmetric error), LR-01 (JSONB index), LR-02 (NOW redundant).

**Verdict:** Production-ready cho ship Phase 1. MR-02 + MR-03 fix khuyến nghị trước Phase 4 MIGRATE-01 (runtime exercise downgrade).

---

### `Hub_All/api/app/auth/role.py` (115 LOC)

**Strengths:**
- Parameterized SQL `text() + dict params` — không SQL injection (T-01-02-01 satisfied).
- Logic ROLE-04 đúng D-V3.1-02 LOCKED 4 case (override / NULL inherit / no-membership / not_found).
- Module separation đúng (KHÔNG mix FastAPI dep vào business logic).
- Docstring example đầy đủ 4 case + reference D-V3.1-02.
- `from __future__ import annotations` + Python 3.10+ type hint syntax — match stack pin.

**Issues:** IR-03 (UUID | str partial), IR-04 (message expose UUID — low risk).

**Verdict:** Production-ready. Cleanest file trong batch.

---

### `Hub_All/api/tests/unit/test_role_helper.py` (150 LOC)

**Strengths:**
- 6 test case cover đủ 4 ROLE-04 + 1 defensive + 1 str args.
- `_make_session()` builder helper clean (sequence side_effect pattern).
- `pytest.mark.asyncio` decorator đúng mọi test.
- `pytest.raises(UserNotFoundError, match=str(user_id))` verify message format.

**Issues:** LR-03 (missing spec=AsyncSession), LR-04 (call_count brittle).

**Verdict:** Production-ready unit test. 6/6 PASS đã verified (xem 01-VERIFICATION.md).

---

### `Hub_All/api/tests/integration/test_migration_0006_idempotent.py` (354 LOC)

**Strengths:**
- 5 test case cover đủ 4 success criteria ROADMAP + downgrade.
- Fixture pattern Iter 1 fix I-01 đúng (monkeypatch DATABASE_URL + cache_clear).
- `_asyncpg_dsn()` helper strip prefix đúng (asyncpg KHÔNG hiểu `+asyncpg`).
- `_reset_settings_cache()` defensive giữa upgrade/downgrade.
- Restore head state ở `finally` test cuối (KHÔNG để DB ở 0005 state phá test sau).
- `pytest.skip` gracefully khi TEST_DATABASE_URL chưa set.

**Issues:** MR-01 (`atexit.register` anti-pattern), LR-05 (cleanup transaction-wrap).

**Verdict:** Production-ready PRE-Phase-4. MR-01 fix khuyến nghị trước Phase 4 MIGRATE-01 (test sẽ chạy bắt buộc với fresh DB scenario).

## Recommended Actions

**Trước Phase 2 (Plan 02-01 dependency `require_hub_admin_for`):**
- KHÔNG action bắt buộc — Phase 1 ship được nguyên trạng cho Phase 2 build dependency.

**Trước Phase 4 MIGRATE-01 (integration test runtime live):**
1. **MR-01** — Refactor `atexit.register` → `yield` fixture pattern (effort: 10 phút).
2. **MR-02** — Refresh inspector sau mỗi `op.execute()` downgrade (effort: 15 phút).
3. **MR-03** — Symmetric error semantic upgrade/downgrade (effort: 5 phút).

**Defer v3.2+ (out of v3.1 scope):**
4. **IR-01** — Centralize role constants `app/auth/roles.py`.
5. **LR-01** — Partial index `audit_logs((payload->>'migration_revision'))` — chỉ khi audit grow lên triệu row.

**KHÔNG action — acceptable as-is:**
- LR-02 (NOW redundant), LR-03 (spec=AsyncSession), LR-04 (call_count brittle), LR-05 (cleanup transaction), IR-02 (print log), IR-03 (UUID | str), IR-04 (UUID expose).

## Status Justification

**Status `minor`** vì:
- 0 critical (không có security vulnerability, data loss risk, schema corruption).
- 0 high (không có logic bug runtime error, missing error handling defensive critical).
- 3 medium (MR-01 anti-pattern fixture, MR-02 inspector cache, MR-03 asymmetric error) — NÊN fix nhưng KHÔNG blocking ship Phase 1; reasonable defer trước Phase 4 MIGRATE-01.
- 5 low + 4 info — code quality + defensive improvement, KHÔNG blocking.

Phase 1 ship được nguyên trạng cho Phase 2 dependency build. KHÔNG cần `/gsd-code-review-fix` chạy ngay; có thể fix MR-01..03 batch chung với Phase 4 MIGRATE-01 task list.

---

_Reviewed: 2026-05-24T09:15:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
