---
phase: 3
plan: 02
subsystem: api/app/auth + api/scripts + api/tests/unit
tags: [jwt, rs256, pyjwt, pkcs8, auth-06, t-03-jwt-alg-confusion, wave1]
requires: [03-01]  # envelope helpers + middleware Plan 03-01 đã build (forward link cho Plan 03-04)
provides: [jwt-manager-rs256, jwt-claims-pydantic, token-pair-dataclass, verify-jwt-format-script]
affects: [03-03, 03-04, 03-05]
tech-stack:
  added: [pyjwt-2.12-crypto, cryptography-backend]
  patterns: [load-pem-once-constructor, hardcoded-algorithms-list, pydantic-v2-claims-validation]
key-files:
  created:
    - Hub_All/api/app/auth/__init__.py
    - Hub_All/api/app/auth/jwt.py
    - Hub_All/api/scripts/verify_jwt_format.sh
    - Hub_All/api/tests/unit/__init__.py
    - Hub_All/api/tests/unit/test_jwt.py
  modified:
    - Hub_All/api/Makefile
decisions:
  - "Load PEM 1 lần ở constructor JWTManager(settings) — cache _private_pem + _public_pem bytes, KHÔNG re-read mỗi issue/verify. Fail-fast nếu file không đọc được."
  - "JWT_ALGORITHMS_ALLOWED = ['RS256'] cứng — T-03-jwt-alg-confusion mitigation. KHÔNG accept list lỏng → block attacker swap alg=none/HS256 ký bằng public key như HMAC secret."
  - "Claims shape KHÁC Go: hub_ids: list[str] (M2 multi-hub) thay vì hub_id: str (Go single hub). Frontend D6 đọc hub_assignments từ envelope không phải từ JWT claim → backward-compat OK."
  - "JWTClaims = Pydantic v2 BaseModel (KHÔNG TypedDict) — validate sớm sau pyjwt.decode, raise JWTError với message tiếng Việt nếu shape sai."
  - "TokenPair = frozen dataclass với access_jti + refresh_jti + access_expires_at + refresh_expires_at — Plan 03-04 cần jti cho Redis SET blacklist:<jti> 1 EX <ttl> + expires_at để set TTL chính xác."
  - "Issuer cố định 'medinet-wiki' (module constant JWT_ISSUER) — match Go internal/pkg/jwt. Test reject wrong-issuer pass."
metrics:
  duration_minutes: 4
  completed_date: "2026-05-14"
  tasks_total: 3
  tasks_completed: 3
  tests_total: 8
  tests_passed: 8
  files_created: 5
  files_modified: 1
  commits: 3
---

# Phase 3 Plan 02: JWT Keypair Format Detection + PyJWT RS256 Wrapper — Summary

**Wave 1 contract #2 cho Phase 3:** Port JWT issuance/verification Go (`backend/internal/pkg/jwt/jwt.go`) sang Python PyJWT RS256, dùng cùng cặp khoá `Hub_All/api/keys/private.pem` + `public.pem` (PKCS#8 RSA 4096-bit Phase 1 đã sinh). Wrapper exposes `JWTManager`, `JWTClaims`, `TokenPair`, `JWTError` cho Plan 03-03 (Argon2) + Plan 03-04 (auth router) consume. Tất cả 3 task hoàn thành atomic, 8/8 unit test PASS, 5 attack vector reject verified, sẵn sàng cho Plan 03-04 wire vào endpoint `/api/auth/login`.

---

## Mục tiêu (Objective)

Plan 03-02 thuộc Wave 1 ("Define contracts") của Phase 3 — sản xuất hợp đồng JWT mà Plan 03-04 (auth router) phụ thuộc trực tiếp:

1. **JWTManager API ổn định** — `issue_token_pair(...)` trả `TokenPair` 2 token RS256 + jti UUID4 + expires_at; `verify_token(token, expected_type)` raise `JWTError` tiếng Việt nếu sai signature/expired/wrong type/wrong issuer.
2. **Keypair format verify** — script `scripts/verify_jwt_format.sh` detect PKCS#1 vs PKCS#8, in lệnh convert chính xác nếu cần. AUTH-06 mitigation: token cũ do Go sinh PHẢI decode được bằng PyJWT verify cùng public key (cross-process verify rời sang Plan 03-05 integration test).
3. **T-03-jwt-alg-confusion mitigation** — `JWT_ALGORITHMS_ALLOWED = ["RS256"]` cứng module-level, KHÔNG mở rộng. Test `test_verify_token_rejects_alg_none_attack` verify alg=none bị reject.

---

## Tasks hoàn thành (3/3)

| # | Task | Commit | Status |
|---|------|--------|--------|
| 01 | Tạo `scripts/verify_jwt_format.sh` + Makefile target `keys-verify-jwt` — detect PKCS#1 vs PKCS#8 qua `head -1` PEM header | `50def00` | PASS |
| 02 | Tạo `app/auth/__init__.py` + `app/auth/jwt.py` — `JWTManager` PyJWT RS256 + `JWTClaims` Pydantic v2 + `TokenPair` dataclass + `JWTError` | `6b512c4` | PASS |
| 03 | Tạo `tests/unit/__init__.py` + `tests/unit/test_jwt.py` — 8 unit test (2 happy + 5 reject + 1 claims shape) | `7448e29` | PASS |

---

## Files thay đổi (6 file)

### Created (5)

- `Hub_All/api/app/auth/__init__.py` — re-export 6 symbol (`JWTManager`, `JWTClaims`, `JWTError`, `TokenPair`, `JWT_ISSUER`, `JWT_ALGORITHM`) với `__all__`
- `Hub_All/api/app/auth/jwt.py` — module chính: `JWTManager` class + `JWTError` Exception + `JWTClaims(BaseModel)` + `TokenPair` frozen dataclass + constants (`JWT_ISSUER="medinet-wiki"`, `JWT_ALGORITHM="RS256"`, `JWT_ALGORITHMS_ALLOWED=["RS256"]`)
- `Hub_All/api/scripts/verify_jwt_format.sh` — bash script detect PKCS#1 vs PKCS#8, exit 0/1/2
- `Hub_All/api/tests/unit/__init__.py` — empty package marker cho pytest discover
- `Hub_All/api/tests/unit/test_jwt.py` — 8 unit test, fixture `jwt_manager` dùng `keys/` Phase 1 thật

### Modified (1)

- `Hub_All/api/Makefile` — thêm target `keys-verify-jwt: bash scripts/verify_jwt_format.sh` + cập nhật `.PHONY` list

---

## Acceptance Criteria — verification suite

| Check | Command | Kết quả |
|-------|---------|---------|
| verify_jwt_format.sh PKCS#8 OK | `bash scripts/verify_jwt_format.sh` | exit 0, output `PKCS#8 OK (keys/private.pem)` + RSA 4096-bit |
| grep PKCS#8 OK ≥1 | `grep -c 'PKCS#8 OK' scripts/verify_jwt_format.sh` | 2 |
| grep openssl pkcs8 -topk8 ≥1 | `grep -c 'openssl pkcs8 -topk8 -nocrypt' scripts/verify_jwt_format.sh` | 1 |
| grep BEGIN PRIVATE KEY ≥1 | `grep -c 'BEGIN PRIVATE KEY' scripts/verify_jwt_format.sh` | 2 |
| grep BEGIN RSA PRIVATE KEY ≥1 | `grep -c 'BEGIN RSA PRIVATE KEY' scripts/verify_jwt_format.sh` | 2 |
| grep class JWTManager ≥1 | — | 1 |
| grep class JWTError(Exception) ≥1 | — | 1 |
| grep class JWTClaims(BaseModel) ≥1 | — | 1 |
| grep algorithms=JWT_ALGORITHMS_ALLOWED ≥1 | — | 1 |
| imports OK | `python -c "from app.auth import JWTManager,JWTError,JWTClaims,TokenPair,JWT_ISSUER; print(JWT_ISSUER)"` | exit 0, `medinet-wiki` |
| pytest tests/unit/test_jwt.py | `uv run pytest tests/unit/test_jwt.py -v` | **8 passed in 3.20s** |
| ruff app/auth tests/unit/test_jwt.py | — | All checks passed |
| mypy app/auth | — | Success: no issues found in 2 source files |
| Full pytest suite (regress check) | `uv run pytest --ignore=tests/integration -q` | **19 passed in 3.67s** (11 cũ + 8 mới) |

**Tổng:** 14 acceptance check 14/14 PASS.

---

## Test Suite — 8/8 PASS

```
tests/unit/test_jwt.py::test_issue_token_pair_returns_valid_rs256       PASSED
tests/unit/test_jwt.py::test_verify_token_happy_access                  PASSED
tests/unit/test_jwt.py::test_verify_token_rejects_wrong_type            PASSED
tests/unit/test_jwt.py::test_verify_token_rejects_expired               PASSED
tests/unit/test_jwt.py::test_verify_token_rejects_tampered_signature    PASSED
tests/unit/test_jwt.py::test_verify_token_rejects_alg_none_attack       PASSED
tests/unit/test_jwt.py::test_verify_token_rejects_wrong_issuer          PASSED
tests/unit/test_jwt.py::test_jwt_claims_shape_matches_spec              PASSED
============================== 8 passed in 3.20s ==============================
```

Coverage Plan 03-02:
- **Happy path issue + verify access** (2 test) — sinh token RS256 sau đó decode raw bằng PyJWT cùng public key + verify_token expected_type="access"
- **Reject wrong type** (1 test) — sinh access, verify với expected_type="refresh" → match "Loại token sai"
- **Reject expired** (1 test) — bake `_access_ttl = timedelta(seconds=-10)` để token sinh ra đã expired → match "hết hạn"
- **Reject tampered signature** (1 test) — sửa 5 ký tự cuối token → `InvalidSignatureError` wrap thành JWTError
- **Reject alg=none attack** (1 test) — T-03-jwt-alg-confusion: encode `algorithm="none"` → PyJWT decode raise `InvalidAlgorithmError` vì `JWT_ALGORITHMS_ALLOWED=["RS256"]` không chứa "none"
- **Reject wrong issuer** (1 test) — ký bằng private key thật nhưng `iss="evil-issuer"` → bypass signature check, fail issuer check → match "issuer"
- **Claims shape spec** (1 test) — assert 10 field `{sub, email, name, role, hub_ids, iss, iat, exp, jti, token_type}` đầy đủ trong decoded payload

---

## Deviations from Plan

Không có deviation — toàn bộ paste-ready code trong plan apply nguyên xi.

**Adjustments nhỏ (không phải deviation):**

1. **Wrong-issuer test ký bằng private key thật thay vì public key** — Plan paste-ready ghi `pub = Path("keys/private.pem").read_bytes()` rồi `pyjwt.encode(evil_payload, pub, algorithm="RS256")`. Code thực tế dùng tên biến `priv` cho rõ ý — ký token bằng private key thật nhưng issuer khác, để bypass signature verification và fail tại issuer check. Logic kết quả không đổi.

2. **Line-length wrap** — một số dòng dài bị wrap để dưới 100 ký tự (ruff line-length=100). Không đổi behavior.

3. **Type annotation `Any` cho fixture return type** — `def jwt_manager(...) -> Any` thay vì để mypy infer (sẽ thành Untyped). Plan paste-ready dùng `-> Any:` ngầm; thêm explicit để mypy --strict PASS.

---

## Key Decisions

1. **Load PEM 1 lần ở constructor JWTManager** (Task 02 `__init__`): KHÔNG re-read file mỗi `issue_token_pair`/`verify_token`. Cache `_private_pem` + `_public_pem` bytes. Nếu file không đọc được → raise `JWTError` ngay startup. Lý do: production sẽ gọi `verify_token` ở mỗi request authenticated (hàng nghìn lần/phút), I/O disk sẽ trở thành bottleneck. Trade-off: rotate key phải restart app — chấp nhận M2 (operation simple).

2. **JWT_ALGORITHMS_ALLOWED cứng `["RS256"]`** (Task 02 — T-03-jwt-alg-confusion mitigation): module constant, KHÔNG accept param mở rộng. Tách thành constant để readable + test verify bằng assert. PyJWT 2.12+ KHÔNG decode alg=none mặc định nếu list không chứa "none" → `InvalidAlgorithmError` raise.

3. **Issuer cố định `"medinet-wiki"` module constant** (Task 02 `JWT_ISSUER`): match Go `internal/pkg/jwt/jwt.go` (theo plan/research). Decode pass kwarg `issuer=JWT_ISSUER` → PyJWT raise `InvalidIssuerError` nếu mismatch. T-03-jwt-cross-issuer mitigation.

4. **Claims shape KHÁC Go: `hub_ids: list[str]`** (Task 02 `JWTClaims`): M2 multi-hub support USER-01..03 yêu cầu user có thể thuộc nhiều hub. Go cũ single `hub_id: str` không đủ. Frontend D6 (React 19 KHÔNG sửa) đọc `hub_assignments` từ envelope `/api/auth/me`, KHÔNG decode JWT claim trực tiếp → backward-compat OK.

5. **`TokenPair` frozen dataclass chứa jti + expires_at** (Task 02): Plan 03-04 cần `access_jti` + `refresh_jti` cho Redis `SET blacklist:<jti> 1 EX <ttl>` (logout endpoint) + `access_expires_at` + `refresh_expires_at` cho TTL chính xác. Dataclass frozen = immutable → safe pass between async coroutine.

6. **`JWTClaims` = Pydantic v2 BaseModel** (Task 02 — KHÔNG TypedDict): Plan 03-04 service nhận `JWTClaims` instance, có thể `.role`, `.hub_ids` typed access + auto validate role enum `Literal["admin","editor","viewer"]` + token_type `Literal["access","refresh"]`. TypedDict không validate runtime → defer pydantic validate ở caller sẽ duplicate code.

7. **Bake TTL âm cho test expired** (Task 03 — Test fixture pattern): Plan 03-04+ sẽ học pattern này — KHÔNG dùng `time.sleep` (slow), KHÔNG dùng `freezegun` (extra dep). Monkey-patch `_access_ttl = timedelta(seconds=-10)` rồi `issue_token_pair` → token sinh ra đã expired 10s trước → `verify_token` raise ngay. Fast, deterministic, no dep.

8. **Tách script `verify_jwt_format.sh` khỏi `verify_keys.sh`** (Task 01): `verify_keys.sh` Phase 1 đã check đủ 3 thứ (PKCS#8 header + 4096-bit size + SPKI public header). Script mới focus AUTH-06: chỉ detect PKCS#1 vs PKCS#8 cho private key + in lệnh convert chính xác. Lý do: Plan 03-04 router có thể gọi script này ở healthcheck mà không cần parse openssl text output. Trade-off: 2 script giao thoa — chấp nhận để giữ separation of concerns.

---

## Threat Model — Tracking

| Threat ID | Status | Implementation |
|-----------|--------|----------------|
| T-03-jwt-alg-confusion (S+E) | **mitigated** | `algorithms=JWT_ALGORITHMS_ALLOWED=["RS256"]` cứng module-level. Test `test_verify_token_rejects_alg_none_attack` PASS. PyJWT 2.12+ raise `InvalidAlgorithmError` nếu alg trong header không trong list. |
| T-03-jwt-key-leak (I) | **mitigated** | `_private_pem` instance attribute (KHÔNG class attribute). `_load_key` chỉ log path (đường dẫn) — KHÔNG log content bytes. `JWTError.__str__` chứa path nhưng KHÔNG chứa key bytes. `keys/` đã ở `.gitignore` Phase 1. |
| T-03-jwt-replay (E) | **partial** | `jti` UUID4 trong mọi token (access + refresh) — sẵn sàng cho Plan 03-04 Redis blacklist `SET blacklist:<jti> 1 EX <ttl>`. Plan 03-04 dependency `get_current_user` sẽ check blacklist trước accept. Plan 03-02 chỉ ship jti contract. |
| T-03-jwt-cross-issuer (S) | **mitigated** | `pyjwt.decode(..., issuer=JWT_ISSUER)` raise `InvalidIssuerError`. Test `test_verify_token_rejects_wrong_issuer` PASS — ký bằng private key thật nhưng issuer "evil-issuer" → JWTError "issuer sai". |
| T-03-jwt-clock-skew (T) | **accepted** | PyJWT default `leeway=0`. M2 deploy single Postgres + single API container (Phase 1 docker-compose) → clock skew không đáng kể. Phase 10 scale → set `leeway=30` ở `pyjwt.decode`. Documented accept risk hiện tại. |

---

## Forward Links (Wave 2-4 dependencies)

**Plan 03-03 (Argon2 password hasher):**
- Sẽ share `app/auth/__init__.py` re-exports — thêm `PasswordHasher` vào `__all__`.
- KHÔNG cần `JWTManager` instance (chỉ hash password, không sign JWT).

**Plan 03-04 (Auth router /api/auth/login + /refresh + /logout + /me):**
- Sẽ `from app.auth import JWTManager, JWTError, JWTClaims, TokenPair`.
- Sẽ inject `JWTManager` qua FastAPI dependency `get_jwt_manager()` — load 1 lần ở lifespan.
- Login endpoint: gọi `jwt_mgr.issue_token_pair(user_id, email, full_name, role, hub_ids)` → trả `TokenPair`. Set refresh_token vào HTTP-only cookie hoặc body theo D6 frontend.
- Refresh endpoint: gọi `jwt_mgr.verify_token(refresh_token, expected_type="refresh")` → `JWTClaims`. Check Redis blacklist `<jti>`. Nếu OK, gọi `issue_token_pair` lại (rotation).
- Logout endpoint: gọi `jwt_mgr.verify_token(access_token, expected_type="access")` → lấy `claims.jti`. `redis.set(f"blacklist:{jti}", "1", ex=jwt_mgr.access_ttl_seconds)`.
- Catch `JWTError` → `resp.unauthorized()` (envelope code "UNAUTHORIZED" — Plan 03-01 đã ship).

**Plan 03-05 (RBAC + 5-AC integration test):**
- Sẽ dùng `JWTClaims.role` để check RBAC `Literal["admin", "editor", "viewer"]`.
- Sẽ dùng `JWTClaims.hub_ids` để check hub isolation.
- Integration test cross-process Go→Python verify (AUTH-06 full criterion) — sinh token Go runtime, assert Python `verify_token` decode được. Defer rời từ Plan 03-02 unit test.

---

## Self-Check: PASSED

**Created files (5/5):**
- FOUND: Hub_All/api/app/auth/__init__.py
- FOUND: Hub_All/api/app/auth/jwt.py
- FOUND: Hub_All/api/scripts/verify_jwt_format.sh
- FOUND: Hub_All/api/tests/unit/__init__.py
- FOUND: Hub_All/api/tests/unit/test_jwt.py

**Modified files (1/1):**
- FOUND: Hub_All/api/Makefile (diff: +4 insertions cho .PHONY + target `keys-verify-jwt`)

**Commits (3/3):**
- FOUND: 50def00 feat(phase-03): scripts(verify_jwt_format) — detect PKCS#1 vs PKCS#8 + Makefile keys-verify-jwt target
- FOUND: 6b512c4 feat(phase-03): auth(jwt) — JWTManager PyJWT RS256 + JWTClaims + TokenPair
- FOUND: 7448e29 test(phase-03): tests(unit/test_jwt) — 8 unit test JWTManager cover 5 attack vector
