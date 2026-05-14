---
phase: 3
plan: 03
subsystem: api/app/auth + api/tests/unit + api/tests/integration
tags: [argon2, password-hash, pwdlib, cross-compat-go, auth-05, r6, doc-bug, wave2]
requires: [03-02]  # JWTManager + app/auth/__init__.py từ Plan 03-02
provides: [argon2-password-hasher, verify-password-helper, cross-compat-go-proof]
affects: [03-04, 03-05]
tech-stack:
  added: [pwdlib-0.3.0-argon2hasher, argon2-cffi-backend]
  patterns: [bake-params-constants, wrap-unknownhasherror-as-false, go-source-as-truth]
key-files:
  created:
    - Hub_All/api/app/auth/password.py
    - Hub_All/api/tests/unit/test_password.py
    - Hub_All/api/tests/integration/test_argon2_cross_compat.py
  modified:
    - Hub_All/api/app/auth/__init__.py
decisions:
  - "Argon2 params lấy từ Go SOURCE CODE (backend/internal/pkg/hash/argon2.go line 13-19): m=65536, t=3, p=4, salt_len=16, hash_len=32 — KHÔNG từ REQUIREMENTS.md / PITFALLS.md / CLAUDE.md (3 doc đều ghi `t=1, p=2` sai). Seed.sql production hash prefix `$argon2id$v=19$m=65536,t=3,p=4$` confirm Go source là single source of truth."
  - "verify_password wrap try/except để KHÔNG raise UnknownHashError khi hash format sai — trả False. Plan 03-04 router chỉ cần True/False, KHÔNG handle pwdlib exception."
  - "5 ARGON2_* module-level constants (MEMORY_COST, TIME_COST, PARALLELISM, SALT_LEN, HASH_LEN) bake explicit + test guard regression `test_params_constants_match_go_source` — đổi 1 const = re-hash toàn bộ user → R6 risk re-emerge."
  - "Scope AC4 trade-off: 1 Go production hash (admin@medinet.vn từ seed.sql) + 5 Python round-trip (round-trip + format prefix + 5 plaintext variants). Full 5+5 bi-directional Python↔Go verify defer Phase 5/8 (cần backend/cmd/hashgen CLI hoặc Go-side test — backend/ giữ đến Phase 8 TEARDOWN-01)."
  - "Tests integration KHÔNG cần testcontainers Postgres — pure cryptography test với hash string literal. Đặt trong tests/integration/ + marker @pytest.mark.critical + @pytest.mark.integration cho CI gate HARD-03 `pytest -m critical`."
metrics:
  duration_minutes: 3
  completed_date: "2026-05-14"
  tasks_total: 3
  tasks_completed: 3
  tests_total: 10
  tests_passed: 10
  files_created: 3
  files_modified: 1
  commits: 3
---

# Phase 3 Plan 03: Argon2 Password Module + Cross-Compat Go↔Python Test — Summary

**Wave 2 contract cho Phase 3:** Port Argon2id password hashing Go (`backend/internal/pkg/hash/argon2.go`) sang Python `pwdlib[argon2]==0.3.0`. Pin params **m=65536, t=3, p=4, salt_len=16, hash_len=32** — **LẤY TỪ GO SOURCE CODE**, KHÔNG từ doc (REQUIREMENTS.md/PITFALLS.md/CLAUDE.md ghi `t=1, p=2` là **doc-bug**). R6 mitigation verified: pwdlib `verify_password("Admin@123", <go_seed_hash>)` → True. Tất cả 3 task hoàn thành atomic, 10/10 test PASS (6 unit + 4 critical cross-compat), sẵn sàng cho Plan 03-04 router login wire `verify_password` để check credentials.

---

## Mục tiêu (Objective)

Plan 03-03 thuộc Wave 2 của Phase 3 — sản xuất hợp đồng password hashing mà Plan 03-04 (auth router login) phụ thuộc trực tiếp:

1. **Argon2PasswordHasher tương thích Go** — `hash_password(plain)` sinh hash string format `$argon2id$v=19$m=65536,t=3,p=4$...` byte-identical Go. `verify_password(plain, hash)` chấp nhận hash do Go alexedwards sinh ra (seed.sql production).
2. **R6 cross-compat mitigation verified** — Integration test bake hash thật từ `Hub_All/backend/scripts/seed.sql` line 13 (admin@medinet.vn, plaintext "Admin@123") + assert pwdlib verify True.
3. **DOC-BUG document explicit** — REQUIREMENTS.md AUTH-05 + PITFALLS.md P6 + CLAUDE.md ghi `t=1, p=2` sai. Implementation theo Go source (`t=3, p=4`) là correct. Follow-up commit sẽ fix 3 doc — out of Plan 03-03 scope.

---

## Tasks hoàn thành (3/3)

| # | Task | Commit | Status |
|---|------|--------|--------|
| 01 | Tạo `app/auth/password.py` (Argon2PasswordHasher wrap pwdlib) + extend `app/auth/__init__.py` re-export 7 symbol | `e205920` | PASS |
| 02 | Tạo `tests/unit/test_password.py` — 6 unit test hash/verify + params guard | `a4f5203` | PASS |
| 03 | Tạo `tests/integration/test_argon2_cross_compat.py` — 4 critical test R6 mitigation | `b68e4d9` | PASS |

---

## Files thay đổi (4 file)

### Created (3)

- `Hub_All/api/app/auth/password.py` — module chính: `hash_password()` + `verify_password()` + 5 `ARGON2_*` constants. Wrap `pwdlib.PasswordHash` với `Argon2Hasher(memory_cost=65536, time_cost=3, parallelism=4, salt_len=16, hash_len=32)`. Docstring document DOC-BUG explicit.
- `Hub_All/api/tests/unit/test_password.py` — 6 unit test pure Python (KHÔNG cần Postgres).
- `Hub_All/api/tests/integration/test_argon2_cross_compat.py` — 4 critical integration test với fixture hash thật từ Go seed.sql.

### Modified (1)

- `Hub_All/api/app/auth/__init__.py` — extend re-export thêm 7 symbol: `hash_password`, `verify_password`, `ARGON2_MEMORY_COST`, `ARGON2_TIME_COST`, `ARGON2_PARALLELISM`, `ARGON2_SALT_LEN`, `ARGON2_HASH_LEN`. `__all__` giữ alphabetical order.

---

## Acceptance Criteria — verification suite

| Check | Command | Kết quả |
|-------|---------|---------|
| password module imports OK | `python -c "from app.auth import hash_password, verify_password, ARGON2_*"` | exit 0, consts `65536 3 4 16 32` |
| Hash format Go-compat | hash prefix `$argon2id$v=19$m=65536,t=3,p=4$` | PASS |
| Round-trip Python→Python | `verify_password(p, hash_password(p))` is True | PASS |
| R6 cross-compat (CORE) | `verify_password("Admin@123", <go_seed_hash>)` is True | **R6 cross-compat OK** |
| Reject wrong password | `verify_password("wrong", <go_seed_hash>)` is False | PASS |
| pytest combined 10 test | `uv run pytest tests/unit/test_password.py tests/integration/test_argon2_cross_compat.py -v` | **10 passed in 1.89s** |
| pytest -m critical | `uv run pytest -m critical -v` | **11 passed, 25 deselected** (4 mới + 7 Phase 2 chunks/migration — no regress) |
| ruff app/auth + tests | `uv run ruff check app/auth tests/unit/test_password.py tests/integration/test_argon2_cross_compat.py` | All checks passed |
| mypy app/auth strict | `uv run mypy app/auth` | Success: no issues found in 3 source files |
| Full unit suite regress | `uv run pytest --ignore=tests/integration -q` | **25 passed in 3.86s** (19 cũ + 6 mới — no regress) |

**Tổng:** 10 acceptance check 10/10 PASS.

---

## Test Suite — 10/10 PASS

```
tests/unit/test_password.py::test_hash_password_returns_argon2id_prefix        PASSED
tests/unit/test_password.py::test_round_trip_verify_true                       PASSED
tests/unit/test_password.py::test_verify_rejects_wrong_password                PASSED
tests/unit/test_password.py::test_verify_returns_false_on_garbage_hash         PASSED
tests/unit/test_password.py::test_hash_is_different_each_call                  PASSED
tests/unit/test_password.py::test_params_constants_match_go_source             PASSED
tests/integration/test_argon2_cross_compat.py::test_pwdlib_verify_go_seed_admin_hash       PASSED
tests/integration/test_argon2_cross_compat.py::test_pwdlib_reject_go_seed_with_wrong_password  PASSED
tests/integration/test_argon2_cross_compat.py::test_round_trip_python_to_python_5_samples  PASSED
tests/integration/test_argon2_cross_compat.py::test_python_generated_hash_format_matches_go PASSED
============================== 10 passed in 1.89s ==============================
```

Coverage Plan 03-03:
- **Unit happy path** (3 test) — hash prefix Go-compat, round-trip True với Tiếng Việt + ký tự đặc biệt, reject wrong password
- **Unit defensive** (2 test) — garbage hash → False (KHÔNG raise), 2 hash cùng plaintext khác nhau (salt random)
- **Unit regression guard** (1 test) — 5 ARGON2_* constants assert match Go source value
- **Integration R6 CORE** (1 test) — pwdlib verify Go-generated seed.sql hash → True (proof cross-compat)
- **Integration phản chứng** (1 test) — WrongPassword / case-sensitive / empty → False
- **Integration round-trip 5 samples** (1 test) — 5 plaintext khác nhau (Editor@Pass123, Viewer@2026, Tiếng Việt có dấu, P@ssw0rd ký tự đặc biệt, 64-char stress) → format prefix + verify True + reject mutated
- **Integration format byte-identical** (1 test) — Hash split $ → 6 segment với parts[1]='argon2id', parts[3]='m=65536,t=3,p=4'

---

## Deviations from Plan

Không có deviation Rules 1-4. Toàn bộ paste-ready code trong plan apply nguyên xi.

**Adjustments nhỏ (không phải deviation):**

1. **Bỏ `import pytest` trong test_password.py unit** — Plan paste-ready có `import pytest` nhưng test functions KHÔNG dùng marker hay fixture nào → ruff F401 báo unused. Bỏ import này để pass ruff. Logic test không đổi.

2. **API verify trước implementation** — Trước khi viết `password.py`, đã chạy `python -c "from pwdlib.hashers.argon2 import Argon2Hasher; import inspect; print(inspect.signature(Argon2Hasher.__init__))"` để confirm pwdlib 0.3.0 API constructor signature đúng `(time_cost=3, memory_cost=65536, parallelism=4, hash_len=32, salt_len=16, type=Type.ID)`. Defaults match Go source nguyên xi — pwdlib đã chọn cùng giá trị Go alexedwards. Tuy nhiên implementation vẫn pass keyword args explicit để bake constant + guard nếu pwdlib bump default trong future.

---

## ⚠ DOC-BUG Discovery — REQUIREMENTS.md / PITFALLS.md / CLAUDE.md sai params Argon2

**Vấn đề phát hiện trong Plan 03-03:**

3 doc trong `.planning/` ghi Argon2 params `t=1, p=2`:

| File | Vị trí | Nội dung sai |
|---|---|---|
| `.planning/REQUIREMENTS.md` | AUTH-05 | `m=65536, t=1, p=2, saltLen=16, keyLen=32` |
| `.planning/research/PITFALLS.md` | Pitfall #6 | `m=65536, t=1, p=2, saltLen=16, keyLen=32` |
| `Hub_All/CLAUDE.md` | Section 3 Concerns đáng nhớ P6/R6 | `m=65536, t=1, p=2, saltLen=16, keyLen=32` |
| `Hub_All/.planning/PROJECT.md` | Risk Register R6 | (KHÔNG ghi chi tiết params — chỉ ghi "Go params") |
| `Hub_All/.planning/ROADMAP.md` | (KHÔNG ghi chi tiết params) | — |

**Source of truth — Go code:**

```go
// Hub_All/backend/internal/pkg/hash/argon2.go line 13-19
const (
    argonMemory     = 64 * 1024 // 64MB → m=65536
    argonIterations = 3         // t=3 (KHÔNG phải 1)
    argonParallel   = 4         // p=4 (KHÔNG phải 2)
    argonSaltLen    = 16
    argonKeyLen     = 32
)
```

**Verification — Production seed hash prefix:**

```
$argon2id$v=19$m=65536,t=3,p=4$gpKFndFoG6bcXrx7R60sag$uhxmJMX03O6QlL0WZS+WdRhCOnGEoIpzUrL2vBzRN+c
                       ^^^^^
                       t=3, p=4 — KHÔNG phải t=1, p=2
```

Hash trong `Hub_All/backend/scripts/seed.sql` line 13 (production admin@medinet.vn) **prefix `t=3, p=4`** — confirm Go source là single source of truth, KHÔNG phải doc.

**Plan 03-03 chọn:** Implement theo Go source (`t=3, p=4`). Bake docstring `password.py` document doc-bug + bake `test_params_constants_match_go_source` unit test guard regression.

**Follow-up action (out of Plan 03-03 scope, defer Plan 03-04 hoặc Plan 03-05):**

```bash
# Sửa 3 doc cho consistent với code:
sed -i 's/t=1, p=2/t=3, p=4/g' Hub_All/.planning/REQUIREMENTS.md
sed -i 's/t=1, p=2/t=3, p=4/g' Hub_All/.planning/research/PITFALLS.md
sed -i 's/t=1, p=2/t=3, p=4/g' Hub_All/CLAUDE.md
git commit -m "docs(phase-03): fix Argon2 params doc-bug — t=3,p=4 match Go source (discovered Plan 03-03)"
```

**Rationale chọn Go source thay vì doc:**
1. Doc-bug verifiable bằng production seed hash prefix → bằng chứng vật lý mạnh hơn doc.
2. Đổi params từ `t=3,p=4` xuống `t=1,p=2` = security regress (giảm computational cost cho attacker brute force).
3. Đổi params = re-hash toàn bộ user existing → cascade failure (R6 trigger). Giữ params Go-compat là an toàn nhất.

---

## Key Decisions

1. **Argon2 params lấy từ Go SOURCE CODE** (Task 01 — DOC-BUG resolution): Đọc trực tiếp `backend/internal/pkg/hash/argon2.go` line 13-19 thay vì tin doc. Verify bằng seed hash production prefix. Bake 5 module-level constants `ARGON2_MEMORY_COST=65_536`, `ARGON2_TIME_COST=3`, `ARGON2_PARALLELISM=4`, `ARGON2_SALT_LEN=16`, `ARGON2_HASH_LEN=32`. Test guard `test_params_constants_match_go_source` để regression future contributor đọc doc sai sẽ FAIL test → biết.

2. **verify_password wrap try/except → False** (Task 01 `password.py`): `pwdlib.verify()` raise `pwdlib.exceptions.UnknownHashError` khi prefix KHÔNG phải Argon2id (e.g., bcrypt, garbage). Plan 03-04 router login KHÔNG cần biết chi tiết format — chỉ cần True/False. Catch broad `Exception` (`# noqa: BLE001`) + log nothing (T-03-pw-log-leak mitigation Plan threat model).

3. **API verify trước implementation** (Task 01 discovery step): Plan ghi rõ "nếu pwdlib 0.3.0 API constructor khác signature đoạn paste-ready, điều chỉnh". Chạy `inspect.signature(Argon2Hasher.__init__)` confirm signature `(time_cost=3, memory_cost=65536, parallelism=4, hash_len=32, salt_len=16, type=Type.ID)` — defaults match Go source nguyên xi. Tuy nhiên vẫn pass keyword args explicit để guard nếu pwdlib bump default trong future + đọc code dễ hiểu hơn.

4. **Scope AC4 trade-off: 1 Go + 5 Python** (Task 03 — Plan 03-03 Scope Note): ROADMAP AC4 yêu cầu "5 sample Go hash + bi-directional Python↔Go verify". Plan 03-03 ship 1 Go production hash (admin@medinet.vn seed.sql) + 5 Python round-trip. Phần còn lại (4 Go hash sinh ra runtime qua `cmd/hashgen` CLI + Python→Go verify direction) defer Phase 5/8 — cần backend/ Go còn runtime. Risk mitigation: nếu Go production phát hành hash với params khác (e.g., bump iterations), AUTH-05 acceptance test sẽ FAIL fast trigger re-pin.

5. **Integration test KHÔNG cần testcontainers Postgres** (Task 03 design): Argon2 cross-compat test pure cryptography — chỉ cần Python pwdlib + hash string literal. Postgres KHÔNG involve. Tuy nhiên ĐẶT trong `tests/integration/` + marker `@pytest.mark.integration` + `@pytest.mark.critical` để chạy chung với CI gate HARD-03 `pytest -m critical`. Lý do: critical path là "Go-issued hash phải verify được" — đây là integration (cross-stack) chứ KHÔNG phải unit (test 1 function pure). Marker semantic > vị trí folder.

6. **Test plaintext 64-char stress** (Task 03): 5 sample plaintext include `"x" * 64` để verify pwdlib KHÔNG silently truncate. Argon2 không có max length theo spec (binding bằng memory cost) nhưng kiểm tra để chắc.

---

## Threat Model — Tracking

| Threat ID | Status | Implementation |
|-----------|--------|----------------|
| T-03-pw-timing (I) | **partial** | pwdlib + argon2-cffi dùng `constant_time_compare` internal khi compare hash bytes — pwdlib `verify()` runtime KHÔNG vary theo password content. Tuy nhiên timing oracle enumerate email vẫn possible nếu router login `if not user: return 401` sớm hơn `verify_password()` call. Plan 03-04 sẽ bake dummy hash compare cho user-not-found case — out of Plan 03-03 scope. Documented forward link. |
| T-03-pw-param-downgrade (E) | **accepted** | DB-level constraint (CHECK regex) phức tạp + brittle. Attacker đã có DB write access = compromised toàn bộ. M2 chấp nhận risk. Documented Out of Scope. |
| T-03-pw-pepper-missing (T) | **accepted** | Go cũ KHÔNG dùng pepper. Adding pepper sẽ break R6 cross-compat (existing user phải re-hash). Defer v4.0. Interim mitigation: Argon2id m=64MB + t=3 + p=4 đủ chống GPU brute force trong scope M2. |
| T-03-pw-log-leak (I) | **mitigated** | `app/auth/password.py` `hash_password` + `verify_password` KHÔNG log gì cả (KHÔNG dùng `structlog.get_logger`). Plan 03-04 router login PHẢI: `log.info("auth_attempt", email=email)` — KHÔNG log password kể cả debug level. Convention bake CONVENTIONS.md section 5. |
| T-03-pw-doc-bug (T process tampering) | **mitigated** | (a) `password.py` docstring DOC-BUG note bake rõ + nêu Go source là source of truth. (b) `test_params_constants_match_go_source` test guard regression — sửa const = test FAIL. (c) SUMMARY.md document doc-bug + suggest follow-up commit fix REQUIREMENTS.md + PITFALLS.md + CLAUDE.md (out of Plan 03-03 scope). |

---

## Forward Links (Wave 3-4 dependencies)

**Plan 03-04 (Auth router /api/auth/login + /refresh + /logout + /me):**
- Sẽ `from app.auth import hash_password, verify_password` để check credential trong login service.
- Login flow: `user = await user_repo.find_by_email(email); if not user: ...dummy_verify... raise 401; if not verify_password(req.password, user.password_hash): raise 401`.
- **T-03-pw-timing dummy compare** — Plan 03-04 PHẢI bake dummy hash constant + verify_password với dummy khi user-not-found để timing tương tự user-exists path. Pattern reference từ Go cũ `backend/internal/auth/service.go` (xem khi port).
- Register endpoint (nếu có, defer Phase 5/M2b USER-01..03): sẽ gọi `hash_password(plain)` để store DB.

**Plan 03-05 (RBAC + 5-AC integration test):**
- 5-AC fixture sẽ gọi `hash_password("Test@Pass123")` để seed test user vào testcontainers Postgres → login flow E2E.
- KHÔNG cần re-verify cross-compat — đã proof trong Plan 03-03.

**Follow-up doc fix (defer Plan 03-04 hoặc cleanup commit riêng):**
- REQUIREMENTS.md AUTH-05: `t=1, p=2` → `t=3, p=4`
- PITFALLS.md Pitfall #6: `t=1, p=2` → `t=3, p=4`
- CLAUDE.md Section 3 P6/R6: `t=1, p=2` → `t=3, p=4`

---

## Self-Check: PASSED

**Created files (3/3):**
- FOUND: Hub_All/api/app/auth/password.py
- FOUND: Hub_All/api/tests/unit/test_password.py
- FOUND: Hub_All/api/tests/integration/test_argon2_cross_compat.py

**Modified files (1/1):**
- FOUND: Hub_All/api/app/auth/__init__.py (diff: +14 insertions for 7 symbol re-export + docstring update)

**Commits (3/3):**
- FOUND: e205920 feat(phase-03): auth(password) — Argon2id wrapper pwdlib + cross-compat Go params
- FOUND: a4f5203 test(phase-03): tests(unit/test_password) — 6 unit test hash/verify + params guard
- FOUND: b68e4d9 test(phase-03): tests(integration/test_argon2_cross_compat) — R6 mitigation 4 test critical
