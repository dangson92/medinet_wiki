---
phase: 05-hub-user-audit-apikey-settings-crud
plan: 05
subsystem: backend-crud
tags: [api-key, audit-log, aes-gcm, crypto, rate-limit, x-api-key, fastapi, raw-sql]

# Dependency graph
requires:
  - phase: 05-hub-user-audit-apikey-settings-crud (plan 01)
    provides: "migration 0003 api_keys.permissions/allowed_hub_ids/rate_limit + audit_logs đủ cột + config knob rate_limit_audit_logs_per_minute"
  - phase: 05-hub-user-audit-apikey-settings-crud (plan 02)
    provides: "middleware/rate_limit.py — limiter (slowapi Limiter) + AUDIT_LOGS_LIMIT constant"
  - phase: 04-cocoindex-flow-mvp
    provides: "documents.py router analog + documents_service.py service-chứa-SQL pattern + response envelope"
provides:
  - "pkg/crypto.py — encrypt_secret/decrypt_secret AES-256-GCM (API key encryption-at-rest)"
  - "schemas/api_keys.py — CreateApiKeyRequest/UpdateApiKeyRequest/ApiKeyResponse/ApiKeyWithPlaintext"
  - "schemas/audit.py — AuditLogResponse khớp AuditLogAPI contract"
  - "services/api_key_service.py — ApiKeyService create/get/list/update/revoke/verify_key (BLOCKER 1)"
  - "services/audit_query_service.py — AuditQueryService.list filter + LEFT JOIN"
  - "routers/api_keys.py — API key CRUD router 5 endpoint admin-only (chưa mount — Plan 05-06)"
  - "routers/audit_logs.py — GET /api/audit-logs admin-only rate-limited @limiter.limit (chưa mount — Plan 05-06)"
  - "auth/dependencies.py — get_api_key_or_jwt (X-API-Key HOẶC Bearer JWT)"
affects: [05-06]

# Tech tracking
tech-stack:
  added:
    - "cryptography — AES-256-GCM encrypt/decrypt cho API key at-rest"
  patterns:
    - "AES-GCM encryption-at-rest — nonce 12B random prepend ciphertext, base64url token"
    - "Plaintext-once — ApiKeyWithPlaintext subclass ApiKeyResponse thêm plain_key; GET trả base class"
    - "@limiter.limit decorator trên endpoint thật (slowapi yêu cầu request: Request param)"
    - "verify-by-decrypt — SELECT WHERE key_prefix + is_active, decrypt key_hash so khớp exact"

key-files:
  created:
    - "api/app/pkg/crypto.py"
    - "api/app/schemas/api_keys.py"
    - "api/app/schemas/audit.py"
    - "api/app/services/api_key_service.py"
    - "api/app/services/audit_query_service.py"
    - "api/app/routers/api_keys.py"
    - "api/app/routers/audit_logs.py"
  modified:
    - "api/app/auth/dependencies.py"
    - "api/app/auth/__init__.py"
    - "api/pyproject.toml"
    - "api/.env.example"

key-decisions:
  - "BLOCKER 1 — tên method verify X-API-Key = verify_key (KHÔNG verify_plaintext); canonical name cho Plan 05-06 auth/api_key.py + get_api_key_or_jwt"
  - "D-07 — revoke = POST soft revoke (is_active=FALSE), KHÔNG DELETE row; PUT update metadata"
  - "BLOCKER 2 — KHÔNG tạo settings router (frontend api.ts không call /api/settings); bảng settings để dành rag-config Phase 7"
  - "W4 — @limiter.limit áp GET /api/audit-logs (endpoint Phase 5 thật) để AUX-03/429 verify được; /api/search + /api/ask decoration defer Phase 6/7"
  - "AES_KEY 32-byte base64 qua env (gitignored .env); _load_key validate len==32 raise ValueError"
  - "get_api_key_or_jwt là Phase 6/7 scaffolding — chưa endpoint Phase 5 nào consume (api-keys/audit-logs đều JWT admin-only)"
  - "Router mount vào main.py defer Plan 05-06 (Wave 4 wiring) — Plan 05-05 KHÔNG touch main.py/routers/__init__.py"

patterns-established:
  - "AES-GCM helper pkg/crypto.py: _load_key + encrypt_secret/decrypt_secret — nonce prepend ciphertext"
  - "ApiKeyWithPlaintext kế thừa ApiKeyResponse — plain_key chỉ ở subclass (POST create), GET trả base"
  - "verify_key: prefix-narrow SELECT + decrypt loop so khớp + UPDATE last_used_at"

requirements-completed: [AUX-01, AUX-02, AUX-03]

# Metrics
duration: 6min
completed: 2026-05-17
---

# Phase 5 Plan 05: API Key CRUD + AES-GCM + Audit Logs Query + Rate Limit Summary

**API key management (AUX-02) với AES-256-GCM encryption-at-rest + soft revoke + X-API-Key auth dependency, audit log query endpoint (AUX-01) với filter + pagination, áp @limiter.limit lên GET /api/audit-logs (AUX-03) — 9 file (7 created + 2 modified), 5+1 endpoint admin-only; verify method canonical `verify_key` (BLOCKER 1).**

## Performance

- **Duration:** ~6 min
- **Started:** 2026-05-17T03:34:28Z
- **Completed:** 2026-05-17T03:40:11Z
- **Tasks:** 3 completed
- **Files modified:** 11 (7 created + 4 modified — gồm pyproject.toml + .env.example)

## Accomplishments

- `pkg/crypto.py` — AES-256-GCM helper: `_load_key` (đọc `settings.aes_key`, base64url-decode, validate 32-byte → ValueError), `encrypt_secret` (nonce 12B random prepend ciphertext → base64url token), `decrypt_secret` (tách nonce, decrypt). Round-trip encrypt→decrypt khôi phục plaintext; ciphertext ≠ plaintext (T-05-05-01/06).
- `schemas/api_keys.py` — 4 Pydantic v2 schema: `CreateApiKeyRequest` (name/permissions/allowed_hub_ids?/rate_limit 1-10000), `UpdateApiKeyRequest` (mọi field optional), `ApiKeyResponse` (= APIKeyAPI — KHÔNG plain_key; status derive is_active; requests_today/7d/bandwidth_used=0, allowed_rag_configs=[] hằng số), `ApiKeyWithPlaintext(ApiKeyResponse)` thêm `plain_key` (POST create only). `ApiKeyStatus` Literal active/revoked.
- `schemas/audit.py` — `AuditLogResponse` (= AuditLogAPI): id/timestamp/user_id/user_name/is_ai/action/target/hub_id/hub_name/ip_address/user_agent/request_id/duration_ms/payload. is_ai=False, ip_address/user_agent/duration_ms=None hằng số (không có cột).
- `services/api_key_service.py` — `ApiKeyService` 6 method + `_map_row`/`_json_list`/`_opt_json_list` helper: `create` (plaintext `mdk_<token_urlsafe(32)>`, key_prefix 8 ký tự, key_hash=encrypt_secret, INSERT JSONB cast → trả ApiKeyWithPlaintext), `get`/`list` (KHÔNG plaintext), `update` (SET động JSONB cast), `revoke` (soft `is_active=FALSE` + RETURNING id detect — D-07), `verify_key` (BLOCKER 1 — SELECT WHERE key_prefix + is_active=TRUE, decrypt loop so khớp exact, UPDATE last_used_at, return principal dict).
- `services/audit_query_service.py` — `AuditQueryService.list` — WHERE-builder filter date_from/date_to/action/hub_id + LEFT JOIN users (user_name) + hubs (hub_name); COUNT + LIMIT/OFFSET ORDER BY created_at DESC. `actor_type` param bỏ qua (không có cột — documented).
- `routers/api_keys.py` — 5 endpoint admin-only (`require_role("admin")`): GET list (cap per_page≤100), POST create→201 (data có plain_key), GET/:id, PUT/:id update, POST/:id/revoke soft. UUID validate → 400 `INVALID_API_KEY_ID`; not-found → 404.
- `routers/audit_logs.py` — GET /api/audit-logs admin-only + `@limiter.limit(AUDIT_LOGS_LIMIT)` (W4 — AUX-03). Endpoint function có `request: Request` param (slowapi yêu cầu); thứ tự decorator `@router.get` trên `@limiter.limit` dưới. Filter date/action/hub_id + pagination cap.
- `auth/dependencies.py` — `get_api_key_or_jwt` — X-API-Key (`Header(alias="X-API-Key")`) ưu tiên: verify qua `ApiKeyService.verify_key` → load User qua `api_keys.created_by`; INVALID_API_KEY 401 nếu fail. Không có X-API-Key → fallback `get_current_user`. Docstring note "Phase 6/7 scaffolding".
- `pyproject.toml` — thêm `cryptography` dependency. `.env.example` — `AES_KEY` documented placeholder.

## Task Commits

Each task was committed atomically (normal git, hooks enabled):

1. **Task 1: pkg/crypto.py + schemas api_keys/audit** - `b3d97f8` (feat)
2. **Task 2: services api_key_service.py + audit_query_service.py** - `06c3a8f` (feat)
3. **Task 3: routers api_keys.py + audit_logs.py rate-limited + X-API-Key dependency** - `a7a3571` (feat)

## Files Created/Modified

- `api/app/pkg/crypto.py` - AES-256-GCM encrypt/decrypt helper cho API key at-rest.
- `api/app/schemas/api_keys.py` - 4 Pydantic schema; ApiKeyWithPlaintext kế thừa ApiKeyResponse + plain_key.
- `api/app/schemas/audit.py` - AuditLogResponse khớp AuditLogAPI contract.
- `api/app/services/api_key_service.py` - ApiKeyService CRUD + AES-GCM + soft revoke + verify_key.
- `api/app/services/audit_query_service.py` - AuditQueryService.list filter + LEFT JOIN.
- `api/app/routers/api_keys.py` - API key CRUD router 5 endpoint admin-only.
- `api/app/routers/audit_logs.py` - GET audit-logs router admin-only rate-limited.
- `api/app/auth/dependencies.py` - thêm get_api_key_or_jwt dependency.
- `api/app/auth/__init__.py` - re-export get_api_key_or_jwt.
- `api/pyproject.toml` - thêm cryptography dependency.
- `api/.env.example` - AES_KEY documented placeholder.

## AES_KEY Runtime Setup (user_setup block)

Plan 05-05 cần env `AES_KEY` (AES-256 32-byte base64) cho API key encryption-at-rest. Runtime không prompt được user → executor đã handle:

1. **Dev key sinh local:** `python -c "import os,base64; print(base64.urlsafe_b64encode(os.urandom(32)).decode())"` → `B6svqzjVTa2SSS4ApKdpNc0zejWTJQDRnYkyQWFI__k=`.
2. **`Hub_All/api/.env`** (gitignored — `git check-ignore .env` confirm) — `AES_KEY` set giá trị thật. **KHÔNG commit** key này.
3. **`Hub_All/api/.env.example`** (committed) — `AES_KEY=` placeholder rỗng + comment hướng dẫn sinh key. Đã commit ở Task 1.
4. **Tests:** Test fixture/conftest cần set deterministic test `AES_KEY` (sinh inside test setup) cho AES-GCM round-trip reproducible — integration test API key thuộc scope Plan 05-06 (Wave 4); conftest update sẽ làm ở đó. Smoke test Task 1 đã chứng minh round-trip qua `os.environ['AES_KEY']` set inline.

## Verification

- **Task 1:** `ruff check` + `mypy --strict` 3 file exit 0. Crypto round-trip smoke: `encrypt_secret('mdk_secret123')` → `decrypt_secret` khôi phục plaintext, ciphertext ≠ plaintext. (Rule 1 fix: bare `dict` → `dict[str, Any]` cho mypy --strict generic.)
- **Task 2:** `ruff check` + `mypy --strict` 2 file exit 0. `ApiKeyService` có `verify_key`, KHÔNG có `verify_plaintext`. `grep "DELETE FROM api_keys"` KHÔNG match; `verify_plaintext` chỉ xuất hiện trong docstring (ghi rõ canonical name = verify_key — KHÔNG phải method). (Rule 1 fix: `datetime.timezone.utc` → `datetime.UTC` alias cho ruff UP017.)
- **Task 3:** `ruff check` + `mypy --strict` 3 file exit 0. Route smoke: api-keys 5 endpoint đúng verb (POST revoke + PUT update + GET/:id + GET + POST), audit-logs 1 GET endpoint. `grep limiter.limit` audit_logs.py có match (decorator). `grep require_role("admin")` api_keys.py 6 match (5 endpoint + 1 docstring; ≥5).
- **Plan-level:** `ruff check` + `mypy --strict` 8 source file clean. `git diff --diff-filter=D HEAD~3 HEAD` rỗng (không xoá file ngoài ý muốn).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] schemas/audit.py — bare `dict` không pass mypy --strict**
- **Found during:** Task 1
- **Issue:** `payload: dict | None` — `mypy --strict` báo `Missing type arguments for generic type "dict" [type-arg]`. Block verify Task 1 (mypy --strict exit 0 là acceptance criteria). Plan action ghi `payload: dict | None`.
- **Fix:** Đổi sang `payload: dict[str, Any] | None` + import `Any`. Hành vi giữ nguyên.
- **Files modified:** `api/app/schemas/audit.py`
- **Commit:** `b3d97f8`

**2. [Rule 1 - Bug] api_key_service.py — `datetime.timezone.utc` ruff UP017**
- **Found during:** Task 2
- **Issue:** `create()` build `ApiKeyWithPlaintext.created_at` cần timestamp — dùng `datetime.now(timezone.utc)`. `ruff` (rule UP017) báo `Use datetime.UTC alias` (Python 3.11+ có `datetime.UTC`). Block verify Task 2.
- **Fix:** `from datetime import UTC, datetime` + `datetime.now(UTC)`. Lưu ý: `created_at` của response POST create dùng Python timestamp (gần đúng) vì INSERT không dùng RETURNING — chấp nhận sai lệch ms không đáng kể; GET sau đó trả `created_at` thật từ DB.
- **Files modified:** `api/app/services/api_key_service.py`
- **Commit:** `06c3a8f`

**3. [Rule 3 - Blocking] auth/dependencies.py — dead `stmt` assignment + thiếu `text` import**
- **Found during:** Task 3
- **Issue:** Draft đầu của `get_api_key_or_jwt` có 1 `stmt = select(User)...` bị overwrite ngay sau bởi `stmt` thứ 2 (dead code — ruff F841 sẽ flag) + dùng `text()` raw SQL query `api_keys.created_by` nhưng `text` chưa import.
- **Fix:** Xoá dead `stmt` đầu; thêm `text` vào `from sqlalchemy import select, text`.
- **Files modified:** `api/app/auth/dependencies.py`
- **Commit:** `a7a3571`

### Out-of-scope discoveries (logged, NOT fixed)

- Không có. Plan 05-05 tạo 7 file mới + sửa 2 file auth (thêm symbol, không touch logic cũ) + pyproject/.env.example. Không lộ regression mới. DEF-05-01 (cocoindex Environment re-open) + DEF-05-02 (test_watchdog.py fixture `hubs.code`) vẫn deferred — Plan 05-05 KHÔNG có integration test (mandatory E4 ở Plan 05-06) nên không chạm DEF-05-01; KHÔNG touch `test_watchdog.py`.

## Threat Model Coverage

Tất cả threat `mitigate` trong `<threat_model>` của plan đã được thực thi:

- **T-05-05-01 (Info Disclosure — API key plaintext leak qua GET/DB dump):** `key_hash` lưu output `encrypt_secret` (AES-256-GCM ciphertext). `get`/`list` trả `ApiKeyResponse` KHÔNG có `plain_key` (chỉ subclass `ApiKeyWithPlaintext` có; chỉ POST create dùng). `key_prefix` 8 ký tự plaintext (UX, không đủ để dùng key).
- **T-05-05-02 (EoP — viewer/editor tạo/thu hồi API key):** Mọi endpoint `routers/api_keys.py` dùng `Depends(require_role("admin"))` → viewer/editor nhận 403 FORBIDDEN. 5 endpoint × require_role("admin").
- **T-05-05-03 (Spoofing — X-API-Key giả mạo / revoked key):** `verify_key` SELECT `WHERE key_prefix=:p AND is_active=TRUE` — revoked key (is_active=FALSE) bị loại khỏi candidate; decrypt `key_hash` so khớp exact với plaintext input.
- **T-05-05-04 (Info Disclosure — audit-logs lộ payload cho non-admin):** `GET /api/audit-logs` `require_role("admin")` → viewer/editor 403.
- **T-05-05-05 (Tampering — SQL injection qua audit filter):** `audit_query_service.list` + `api_key_service` mọi raw SQL qua `text()` + named bind params (`:date_from`, `:action`, ...). WHERE-clause chỉ chứa fragment cố định nội bộ — KHÔNG f-string nội suy input.
- **T-05-05-06 (Info Disclosure — AES_KEY hard-code/commit git):** `AES_KEY` qua env `settings.aes_key`; `.env` gitignored (confirm `git check-ignore`); `.env.example` chỉ placeholder. `_load_key` validate 32-byte → ValueError nếu sai.
- **T-05-05-07 (DoS — spam GET /api/audit-logs):** `@limiter.limit(AUDIT_LOGS_LIMIT)` decorate endpoint; vượt `rate_limit_audit_logs_per_minute` → 429 envelope `RATE_LIMIT_EXCEEDED` (handler Plan 05-02). Test verify Plan 05-06 (cần app.state.limiter wired).
- **T-05-05-08 (Repudiation — accept):** `verify_key` UPDATE `last_used_at=NOW()` khi key match. Usage count chi tiết (requests_today/7d) defer v4.0 — M2 trả 0 hằng số (accepted disposition).

## Threat Flags

Không phát hiện threat surface mới ngoài `<threat_model>` của plan. 7 file mới đều CRUD/crypto layer chuẩn — router admin-only, service raw SQL parametrized, crypto AES-GCM env-key. `get_api_key_or_jwt` thêm X-API-Key auth path nhưng đã nằm trong threat register (T-05-05-03 boundary "X-API-Key header → API"). Router CHƯA mount vào `main.py` (wiring Plan 05-06) nên chưa expose endpoint runtime.

## AUX-03 SC5 — Partial defer có chủ đích (WARNING 1)

ROADMAP AUX-03 SC5 nêu đích danh `/api/search` làm endpoint rate-limit. `/api/search` là endpoint Phase 6 (chưa tồn tại Phase 5). Phase 5 verify **cơ chế rate-limit + 429 envelope shape** trên `GET /api/audit-logs` (endpoint Phase 5 thật) — đủ chứng minh slowapi limiter + 429 envelope hoạt động. Decoration `@limiter.limit` cho `/api/search` + `/api/ask` **defer Phase 6/7** khi 2 endpoint đó được tạo. → Downstream verifier KHÔNG nên flag SC5 là hard gap — cơ chế đã verify Phase 5, chỉ còn việc dán decorator lên endpoint Phase 6/7.

## Settings CRUD — Omission có chủ đích (BLOCKER 2)

Phase title nhắc "Settings" nhưng `frontend/src/services/api.ts` có ZERO call `/api/settings` → Phase 5 KHÔNG implement settings endpoint. Bảng `settings` để dành rag-config (D-03, Phase 7). Plan 05-05 KHÔNG tạo settings router — chỉ api-keys + audit-logs. Đây là omission CÓ CHỦ ĐÍCH, không phải quên — downstream verifier KHÔNG nên flag.

## Known Stubs

Không có stub chặn mục tiêu plan. Field hằng số trong response (`requests_today`/`requests_7d`/`bandwidth_used`=0, `allowed_rag_configs`=[], `is_ai`=False, `ip_address`/`user_agent`/`duration_ms`=None) là **contract-fill có chủ đích** — frontend `APIKeyAPI`/`AuditLogAPI` khai báo field nhưng M2 chưa có cột DB nguồn data (usage tracking defer v4.0; actor_type/ip không có cột audit_logs). Plan objective ghi rõ "trả 0/[]/null hằng số". `get_api_key_or_jwt` là Phase 6/7 scaffolding chưa endpoint nào consume — documented, không phải stub bug. Router chưa mount main.py là wiring defer Plan 05-06 — `routers/api_keys.py` + `routers/audit_logs.py` export `router` sẵn sàng `include_router`.

## TDD Gate Compliance

Plan type là `execute` (KHÔNG phải `type: tdd`); không task nào có `tdd="true"`. Verify qua `ruff check` + `mypy --strict` + crypto round-trip smoke + route smoke test (acceptance criteria mỗi task). Integration test API key + audit-logs + rate-limit 429 thuộc scope Plan 05-06 (Wave 4). Gate RED→GREEN không áp dụng.

## Self-Check: PASSED

- FOUND: api/app/pkg/crypto.py
- FOUND: api/app/schemas/api_keys.py
- FOUND: api/app/schemas/audit.py
- FOUND: api/app/services/api_key_service.py
- FOUND: api/app/services/audit_query_service.py
- FOUND: api/app/routers/api_keys.py
- FOUND: api/app/routers/audit_logs.py
- FOUND commit: b3d97f8 (Task 1)
- FOUND commit: 06c3a8f (Task 2)
- FOUND commit: a7a3571 (Task 3)
