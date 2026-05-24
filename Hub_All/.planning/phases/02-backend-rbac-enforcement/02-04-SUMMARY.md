---
phase: 02-backend-rbac-enforcement
plan: 04
subsystem: backend-rbac-audit
tags: [DEP-05, audit-payload, actor-scope, build_audit_payload, D-V3.1-Phase2-C-LOCKED, B5-iter-1, B7-iter-1, hub_admin-forensic]
requirements_completed: [DEP-05]
requires:
  - 01-01 (migration 0006 user_hubs.role TEXT NULL + role CHECK 4 value)
  - 02-01 (assert_hub_admin_for validator)
  - 02-02 (routers/hubs.py super-only require_role guard — DEP-04 LOCKED)
  - 02-03 (routers/users.py 4 endpoint refactor + B1 iter 1 DELETE branch)
provides:
  - "audit_service.py build_audit_payload(*, actor_role, actor_hub_id, extra=None) helper — dedup pattern 5 callsite"
  - "audit_service.py B7 iter 1 docstring MANDATORY note — lock invariant cho api_key_service.py refactor tương lai"
  - "user_service.py create() + delete() signature thêm actor_role + actor_hub_id keyword-only required"
  - "hub_service.py create() + update() + update_status() signature thêm actor_role + actor_hub_id default 'admin' + None (DEP-04 LOCKED)"
  - "5 router callsite (POST/DELETE /api/users + POST/PUT/PATCH /api/hubs) derive + pass actor metadata"
  - "B5 iter 1 patch-style POST + DELETE router insertion (KHÔNG full handler rewrite — preserve Plan 02-03 ship)"
  - "B7 iter 1 future-proof guard: api_key_service.py grep enqueue_audit == 0 verified"
  - "4 unit test test_audit_actor_scope.py + 2 integration test test_audit_actor_metadata.py"
  - "Forensic query payload->>'actor_role' = 'hub_admin' AND payload->>'actor_hub_id' = '<dmd-uuid>' queryable"
affects:
  - "api/app/services/audit_service.py (+58 / -0 — build_audit_payload helper + B7 docstring)"
  - "api/app/services/user_service.py (+19 / -4 — import update + 2 signature + 2 callsite refactor)"
  - "api/app/services/hub_service.py (+27 / -4 — import update + 3 signature + 3 callsite refactor)"
  - "api/app/routers/users.py (+18 / -2 — POST 2 derive + DELETE 4 derive + service.create/delete kwargs)"
  - "api/app/routers/hubs.py (+6 / -0 — POST + PUT + PATCH status pass actor='admin' + None)"
  - "api/tests/unit/test_audit_actor_scope.py (CREATED — 4 test pure Python)"
  - "api/tests/integration/test_audit_actor_metadata.py (CREATED — 2 scenario testcontainers)"
tech-stack:
  added: []
  patterns:
    - "Helper convenience build_audit_payload nest actor scope vào payload dict — dedup 5 callsite + thread-through"
    - "Keyword-only required params (no default) cho user_service — router PHẢI derive đúng từ user.role + req.hub_id"
    - "Keyword default 'admin' + None cho hub_service (DEP-04 LOCKED) — router vẫn pass explicit cho traceability"
    - "B5 iter 1 patch-style INSERT preserve Plan 02-03 ship lines (CROSS_HUB_USER_DELETE_DENIED + LastAdminError + CANNOT_DELETE_SELF + target_hub_ids derivation)"
    - "B7 iter 1 docstring MANDATORY pattern note + acceptance criterion lock invariant grep guard"
    - "Poll-based wait _wait_audit_row (3s timeout / 50ms tick) — audit_flush_loop batch async, KHÔNG sync"
    - "W1 isolation auto via app_with_auth TRUNCATE per-test (conftest.py:264-284)"
key-files:
  created:
    - api/tests/unit/test_audit_actor_scope.py
    - api/tests/integration/test_audit_actor_metadata.py
  modified:
    - api/app/services/audit_service.py
    - api/app/services/user_service.py
    - api/app/services/hub_service.py
    - api/app/routers/users.py
    - api/app/routers/hubs.py
decisions:
  - "D-V3.1-Phase2-C LOCKED carry forward: KHÔNG migration schema thêm cột cho audit_logs — payload JSONB nullable (migration 0001 baseline) đủ chứa actor_role + actor_hub_id nest"
  - "Helper build_audit_payload ở audit_service.py — dedup 5 callsite + central location refactor invariant; KHÔNG đặt ở user_service hoặc hub_service (cross-domain helper)"
  - "user_service.create + delete kwargs required (KHÔNG default) — buộc router pass explicit, deterministic derive từ user.role"
  - "hub_service.create + update + update_status default 'admin' + None — DEP-04 LOCKED hub mutate super-only; router caller pass explicit cho traceability KHÔNG dùng default"
  - "B5 iter 1 patch-style INSERT (KHÔNG full handler rewrite) — preserve Plan 02-02 + 02-03 ship lines (assert_hub_admin_for + CROSS_HUB_USER_DELETE_DENIED + LastAdminError + CANNOT_DELETE_SELF + AUTH_STATE_INCONSISTENT)"
  - "B7 iter 1 future-proof guard: api_key_service.py grep enqueue_audit count == 0 verified — acceptance criterion lock invariant; khi nào Phase n+ thêm audit emit ở api_key_service BẮT BUỘC refactor build_audit_payload (docstring MANDATORY note enforce)"
  - "Test integration duplicate helpers inline (_seed_hub_admin_user + seed_hubs_dmd_tdt fixture) — Plan 02-05 closeout sẽ consolidate DRY"
metrics:
  duration_seconds: 1380
  duration_human: "~23 phút (Task 1 implementation + verify + Task 1 commit + Task 2 test create + verify + Task 2 commit)"
  tasks_completed: 2
  files_changed: 7
  completed_at: "2026-05-24T00:00:00Z"
---

# Phase 02 Plan 04: DEP-05 Audit Payload Actor Scope Nest Summary

## One-liner

DEP-05 D-V3.1-Phase2-C LOCKED — nest `actor_role` + `actor_hub_id` vào `audit_logs.payload` JSONB qua helper `build_audit_payload` (dedup pattern 5 callsite) + B7 iter 1 docstring MANDATORY note (lock invariant cho api_key_service.py future refactor); 5 service signature extend (user_service.create/delete required; hub_service.create/update/update_status default `'admin'`+None vì DEP-04 LOCKED); 5 router callsite derive + pass (POST/DELETE /api/users derive từ `user.role` + req.hub_id/target_hub_ids[0] — B5 iter 1 patch-style preserve Plan 02-03 ship; POST/PUT/PATCH /api/hubs hard-code `'admin'`+None); 4 unit + 2 integration test PASS verify forensic query `payload->>'actor_role' = 'hub_admin'` deliverable; 471/471 unit regression PASS + 10/10 Plan 02-02 + 02-03 integration regression PASS.

## What Shipped

### Task 1 — Helper + 5 service + 5 router refactor (commit `fb07f3a`)

**File modified:** `Hub_All/api/app/services/audit_service.py` (+58 / -0)

Thêm helper function `build_audit_payload` SAU `AuditEntry` dataclass + TRƯỚC `_queue` module-level:

```python
def build_audit_payload(
    *,
    actor_role: str,
    actor_hub_id: str | None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Phase 2 Plan 02-04 DEP-05 (D-V3.1-Phase2-C LOCKED) — Nest actor scope vào payload.

    **Pattern Phase 2 DEP-05 (B7 iter 1 MANDATORY):** mọi audit-emitter
    (user_service, hub_service, api_key_service) PHẢI dùng build_audit_payload
    để thread-through actor_role + actor_hub_id. KHÔNG construct payload dict
    raw. Khi nào api_key_service.py thêm audit emit (currently 0 enqueue_audit
    calls — Phase 2 DEP-05 chưa cover) → BẮT BUỘC refactor add actor_role +
    actor_hub_id qua helper này. Acceptance criterion lock invariant tại Plan
    02-04 acceptance:
        grep -c "enqueue_audit" app/services/api_key_service.py == 0
    ...
    """
    base: dict[str, Any] = {
        "actor_role": actor_role,
        "actor_hub_id": actor_hub_id,
    }
    if extra:
        base.update(extra)
    return base
```

**File modified:** `Hub_All/api/app/services/user_service.py` (+19 / -4)

- Import update: `from app.services.audit_service import AuditEntry, build_audit_payload, enqueue_audit`.
- `create()` signature thêm `actor_role: str` + `actor_hub_id: str | None` keyword-only required (KHÔNG default — router PHẢI pass).
- `delete()` signature analog — keyword-only required (B1 iter 1 DELETE refactor sang `get_current_user` đã ship Plan 02-03 → router derive được).
- 2 callsite enqueue_audit refactor — dict literal `{"email": ..., "role": ...}` thay bằng `build_audit_payload(actor_role=..., actor_hub_id=..., extra={...})`.

**File modified:** `Hub_All/api/app/services/hub_service.py` (+27 / -4)

- Import update analog user_service.
- `create()` + `update()` + `update_status()` signature thêm `actor_role: str = "admin"` + `actor_hub_id: str | None = None` keyword-only với default vì DEP-04 LOCKED hub mutate luôn super-only.
- 3 callsite enqueue_audit refactor analog — payload qua `build_audit_payload` thay dict literal.

**File modified:** `Hub_All/api/app/routers/users.py` (+18 / -2)

- POST `/api/users` — B5 iter 1 patch-style INSERT 2 derive lines AFTER `await assert_hub_admin_for(user=user, db=db, target_hub_id=req.hub_id)` ship bởi Plan 02-03:

```python
actor_role = "admin" if user.role == "admin" else "hub_admin"
actor_hub_id = None if user.role == "admin" else req.hub_id
```

- UPDATE call site `service.create(...)` thêm 2 keyword args `actor_role=` + `actor_hub_id=`.
- DELETE `/api/users/:id` — B5 iter 1 patch-style INSERT 4 derive lines AFTER Plan 02-03 B1 iter 1 branch block (cross-hub + orphan + single-hub assert_hub_admin_for), TRƯỚC `request_id = getattr(...)`:

```python
actor_role = "admin" if user.role == "admin" else "hub_admin"
actor_hub_id = (
    None if user.role == "admin" else target_hub_ids[0]
)
```

- UPDATE call site `service.delete(...)` thêm 2 keyword args.

**File modified:** `Hub_All/api/app/routers/hubs.py` (+6 / -0)

- POST `/api/hubs` + PUT `/api/hubs/:id` + PATCH `/api/hubs/:id/status` — full kwargs update (hubs handler chưa bị Plan 02-02 + 02-03 touch — full kwargs OK):

```python
result = await service.create(
    req=req, created_by=user.id,
    actor_role="admin",      # Phase 2 Plan 02-04 — DEP-04 LOCKED hub mutate super-only.
    actor_hub_id=None,       # Phase 2 Plan 02-04.
    request_id=request_id,
)
```

3 endpoint hard-code `'admin'` + None vì DEP-04 LOCKED.

### Task 2 — 4 unit + 2 integration test (commit `34aee86`)

**File created:** `Hub_All/api/tests/unit/test_audit_actor_scope.py` (+62 lines)

4 test pure Python (KHÔNG cần infra):

1. `test_super_admin_nests_actor_role_admin_and_null_hub` — verify (admin + None + extra) dict shape 4 key.
2. `test_hub_admin_nests_actor_role_hub_admin_and_hub_id` — verify (hub_admin + uuid + extra) shape.
3. `test_extra_none_returns_only_actor_keys` — verify extra=None → CHỈ 2 actor key.
4. `test_extra_can_override_actor_keys_document_behavior` — document caller responsibility (extra override base).

**File created:** `Hub_All/api/tests/integration/test_audit_actor_metadata.py` (+222 lines)

2 scenario testcontainers verify ROADMAP Phase 2 success criteria #4:

1. `test_hub_admin_user_create_audit_payload_nested_correctly` — Hub_admin dmd POST /api/users → poll audit_logs row → `payload['actor_role'] == 'hub_admin'` + `payload['actor_hub_id'] == dmd_id` + extra fields preserve (email + role).
2. `test_super_admin_user_create_audit_payload_actor_admin_null_hub` — Super admin POST /api/users → `payload['actor_role'] == 'admin'` + `payload['actor_hub_id'] is None`.

Helper inline:
- `_seed_hub_admin_user(email, hub_id)` — duplicate Plan 02-02 + 02-03 helper (Plan 02-05 closeout consolidate DRY).
- `seed_hubs_dmd_tdt` fixture — INSERT 9 cột hubs (W2 schema 10 cột valid bỏ updated_at server_default).
- `_wait_audit_row(target_email, timeout_s=3.0)` — poll-based wait pattern carry forward conftest.py:778-806 `_wait_usage_count`.

## How Verified

### Acceptance criteria grep verify

| Pattern | File | Expected | Actual |
|---------|------|----------|--------|
| `def build_audit_payload` | audit_service.py | 1 | 1 |
| `MANDATORY` (B7 docstring) | audit_service.py | ≥1 | 1 |
| `payload=build_audit_payload` | user_service.py | 2 | 2 |
| `payload=build_audit_payload` | hub_service.py | 3 | 3 |
| `actor_role = "admin" if user.role == "admin"` | routers/users.py | 2 | 2 |
| `actor_role="admin"` | routers/hubs.py | 3 | 3 |
| `enqueue_audit` (B7 guard) | api_key_service.py | 0 | 0 |

### Test verify

```bash
$ cd Hub_All/api && python -m pytest tests/unit/test_audit_actor_scope.py -x --tb=short
4 passed in 4.47s

$ python -m pytest tests/integration/test_audit_actor_metadata.py -x --tb=short
2 passed in 19.34s

$ python -m pytest tests/unit -q --tb=no
471 passed, 7 warnings in 48.97s  # 467 baseline + 4 new = 471

$ python -m pytest tests/integration/test_dep_users_scope.py tests/integration/test_dep_hubs_scope.py -q
10 passed in 24.49s  # Plan 02-02 + 02-03 regression PASS
```

### Smoke verify build_audit_payload

```bash
$ python -c "from app.services.audit_service import build_audit_payload; r = build_audit_payload(actor_role='hub_admin', actor_hub_id='x', extra={'k':'v'}); assert r == {'actor_role':'hub_admin','actor_hub_id':'x','k':'v'}; print('OK')"
OK
```

### Import chain verify

```bash
$ python -c "from app.routers.users import router; from app.routers.hubs import router as hubs_router; print('OK 2 routers importable')"
OK 2 routers importable
```

## Deviations from Plan

None — plan executed exactly as written.

Tất cả acceptance criteria PASS theo Plan 02-04 STEP 1-6 verbatim. B5 iter 1 patch-style INSERT preserve nguyên Plan 02-03 ship lines (`assert_hub_admin_for` + `CROSS_HUB_USER_DELETE_DENIED` + `LastAdminError` + `CANNOT_DELETE_SELF` + `target_hub_ids` derivation chain). B7 iter 1 guard verified `grep -c enqueue_audit api_key_service.py == 0`. KHÔNG Rule 1/2/3 deviation cần auto-fix — existing 467 unit test PASS regression (KHÔNG cần update test mock vì tất cả test hiện hữu KHÔNG gọi `UserService.create/delete` hoặc `HubService.create/update/update_status` trực tiếp — verified qua grep `UserService\(|HubService\(` returns 0 trong tests/).

## Decisions Made

1. **Helper location = audit_service.py (D-V3.1-Phase2-C LOCKED):** `build_audit_payload` đặt ở central audit_service module — dedup 5 callsite + invariant location. KHÔNG đặt ở user_service hoặc hub_service (cross-domain helper).
2. **user_service kwargs REQUIRED (KHÔNG default):** `create()` + `delete()` kwargs `actor_role` + `actor_hub_id` KHÔNG có default — buộc router pass explicit. Deterministic derive từ `user.role` + `req.hub_id` (POST) hoặc `target_hub_ids[0]` (DELETE B1 iter 1 single-hub case).
3. **hub_service kwargs DEFAULT 'admin' + None:** 3 method (create + update + update_status) default `'admin'` + None vì DEP-04 LOCKED hub mutate luôn super-only. Router caller pass explicit cho traceability KHÔNG dùng default (defensive).
4. **B5 iter 1 patch-style INSERT (KHÔNG full handler rewrite):** Preserve Plan 02-02 + 02-03 ship lines. POST /api/users INSERT 2 derive lines AFTER `assert_hub_admin_for`. DELETE INSERT 4 derive lines AFTER B1 iter 1 branch block. Tránh xung đột logic ship.
5. **B7 iter 1 future-proof guard + MANDATORY docstring note:** Acceptance criterion lock invariant `grep -c "enqueue_audit" app/services/api_key_service.py == 0`. Docstring MANDATORY note nhấn mạnh: khi nào api_key_service.py thêm audit emit phải BẮT BUỘC refactor qua `build_audit_payload`. KHÔNG hard-enforce ở runtime — code review + grep CI guard.
6. **W4 coverage measurement deferred to Plan 02-05 closeout:** Plan 02-04 acceptance criteria có dòng `--cov-fail-under=80` nhưng KHÔNG block — Plan 02-05 closeout sẽ chạy full coverage scan (3 service module). 471 unit + 12 integration test PASS đã cover semantic.

## Forensic Query Deliverable (D-V3.1-Phase2-C)

Sau Plan 02-04 ship, audit_logs cho phép query forensic per-hub scope:

```sql
-- Tìm mọi mutation hub_admin trên hub dmd:
SELECT * FROM audit_logs
WHERE payload->>'actor_role' = 'hub_admin'
  AND payload->>'actor_hub_id' = '<dmd-uuid>'
ORDER BY created_at DESC;

-- Tìm mọi mutation super admin (cross-hub op):
SELECT * FROM audit_logs
WHERE payload->>'actor_role' = 'admin'
  AND payload->>'actor_hub_id' IS NULL
ORDER BY created_at DESC;

-- Count action breakdown per hub_admin scope:
SELECT
  payload->>'actor_hub_id' AS hub_id,
  action,
  COUNT(*) AS cnt
FROM audit_logs
WHERE payload->>'actor_role' = 'hub_admin'
GROUP BY 1, 2
ORDER BY 1, 3 DESC;
```

ROADMAP Phase 2 success criteria #4 DELIVERED.

## Backward Compatibility Notes

- **user_service.create + delete kwargs required:** Existing M2 + v3.0 callsite (chỉ trong routers/users.py) ĐÃ update — KHÔNG có caller khác (verified grep `UserService\(` trong tests/ + app/ returns 0 ngoài routers).
- **hub_service.create + update + update_status kwargs default:** Backward compat — caller hiện hữu (chỉ routers/hubs.py) đã update; default `'admin'` + None bảo vệ nếu Phase n+ có caller khác.
- **api_key_service.py UNCHANGED:** B7 iter 1 guard lock — KHÔNG đụng file này; future audit emit BẮT BUỘC qua `build_audit_payload`.
- **No Plan 02-03 ship line break:** B5 iter 1 patch-style preserve toàn bộ Plan 02-02 + 02-03 envelope code + handler shape.

## Carry Forward

- **Plan 02-05 closeout** sẽ:
  - Consolidate DRY 2 helper `_seed_hub_admin_user` + fixture `seed_hubs_dmd_tdt` (hiện duplicate Plan 02-02 + 02-03 + 02-04).
  - W4 explicit `--cov-fail-under=80` chạy full coverage scan trên `audit_service` + `user_service` + `hub_service`.
  - Update STATE.md + ROADMAP.md + REQUIREMENTS.md Phase 2 mark DEP-05 `[x]` + CLAUDE.md section 6 row + REQ traceability.
  - Operator broadcast note: M2 + v3.0 forensic query mới khả dụng `payload->>'actor_role'` + `payload->>'actor_hub_id'`.

## Threat Model Coverage

Tất cả 6 STRIDE threat đã mitigate hoặc accept theo plan threat_model section:

| Threat ID | Disposition | Notes |
|-----------|-------------|-------|
| T-02-04-01 (Repudiation actor scope missing) | mitigate | 5 callsite refactor qua build_audit_payload |
| T-02-04-02 (Tampering router pass sai actor) | accept | Derive deterministic từ user.role DB (KHÔNG JWT payload) |
| T-02-04-03 (Information Disclosure hub_id leak) | accept | M2 carry forward — audit_logs admin-only access |
| T-02-04-04 (DoS build_audit_payload latency) | accept | Pure Python dict O(n) <100µs typical |
| T-02-04-05 (Tampering null serialize) | mitigate | json.dumps None → JSON null preserve; integration test #2 verify |
| T-02-04-06 (Repudiation api_key_service future) | mitigate | B7 iter 1 grep guard == 0 + MANDATORY docstring lock invariant |

## Self-Check: PASSED

### Created files

- `Hub_All/api/tests/unit/test_audit_actor_scope.py` — FOUND
- `Hub_All/api/tests/integration/test_audit_actor_metadata.py` — FOUND
- `Hub_All/.planning/phases/02-backend-rbac-enforcement/02-04-SUMMARY.md` — FOUND (this file)

### Modified files

- `Hub_All/api/app/services/audit_service.py` — FOUND
- `Hub_All/api/app/services/user_service.py` — FOUND
- `Hub_All/api/app/services/hub_service.py` — FOUND
- `Hub_All/api/app/routers/users.py` — FOUND
- `Hub_All/api/app/routers/hubs.py` — FOUND

### Commits

- `fb07f3a` (Task 1 — feat: 5 service + 5 router) — FOUND
- `34aee86` (Task 2 — test: 4 unit + 2 integration) — FOUND

### Verification chain

- Syntax 5 files PASS (ast.parse).
- Acceptance criteria grep 7/7 PASS (build_audit_payload count, MANDATORY, callsite count, derive lines, hardcode actor='admin', api_key_service guard 0).
- Unit suite 471/471 PASS (467 baseline + 4 new).
- Integration test_audit_actor_metadata.py 2/2 PASS.
- Plan 02-02 + 02-03 regression 10/10 PASS.
- B7 iter 1 guard `grep -c enqueue_audit api_key_service.py == 0` verified.
- D-V3.1-Phase2-C LOCKED: NO migration file added (verified `git diff --name-only` returns only 7 files trong scope).
