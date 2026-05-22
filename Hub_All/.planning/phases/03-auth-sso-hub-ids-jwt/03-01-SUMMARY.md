---
phase: 03-auth-sso-hub-ids-jwt
plan: 01
subsystem: auth
tags:
  - jwks
  - rfc-7517
  - jwt-rs256
  - central-publish
  - public-key-export
  - d-v3-phase3-a
  - d-v3-phase3-d
  - r-v3-5
  - sso-01

# Dependency graph
requires:
  - phase: 01-multi-db-topology
    provides: "Settings.hub_name + _enforce_hub_dsn_match validator (Plan 01-02) — Plan 03-01 reuse Settings cho central_jwks_url field mới"
  - phase: 02-hub-con-codebase-factor
    provides: "create_app() factory conditional mount + Starlette HTTPException handler 404 envelope (Plan 02-01 + 02-03) — Plan 03-01 mount route mới TRONG block central-only; hub con strip → 404 envelope D6 inherit"
provides:
  - "GET /.well-known/jwks.json central-only RFC 7517 JWK Set + Cache-Control 1h"
  - "publish_jwks() + load_public_key_as_jwk() helpers RFC 7517 export (api/app/auth/jwks.py)"
  - "Settings.central_jwks_url field mới (default None — Plan 03-02 hub con consume + enforce validator)"
  - "Docker-compose 3 hub con env CENTRAL_JWKS_URL trỏ central intra-network (+ template inherit FACTOR-04)"
affects:
  - "03-02 (hub con JWKSCache) — BLOCKING consume endpoint này Wave 2"
  - "03-03 (JWT iss/aud/hub_ids claim refactor) — Wave 3 dùng cùng PEM/kid sign"
  - "05 PROXY-02 (frontend) — fetch JWKS qua Caddy CORS verify JWT client-side jose.js"
  - "07 MIGRATE-04 (MCP service) — re-point sang central JWKS endpoint verify token"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "RFC 7517 JWK Set manual export qua cryptography stdlib (RSAPublicNumbers → n/e base64url) — KHÔNG dep jwcrypto"
    - "kid deterministic SHA-256 8-byte base64url prefix (PEM rotation tự detect mismatch)"
    - "503 fallback envelope D6 shape khi PEM missing (caller log + JWKS_UNAVAILABLE code)"
    - "FastAPI route mount conditional `if settings.hub_name == 'central':` block (FACTOR-02 carry forward Plan 02-01)"

key-files:
  created:
    - "Hub_All/api/app/auth/jwks.py — JWKS publish module 137 LOC (publish_jwks + load_public_key_as_jwk + 2 helper + JWK/JWKSet TypedDict)"
    - "Hub_All/api/tests/unit/test_jwks_publish.py — 9 unit test (7 publish + 2 mount conditional) 228 LOC"
    - "Hub_All/.planning/phases/03-auth-sso-hub-ids-jwt/03-01-SUMMARY.md (file này)"
  modified:
    - "Hub_All/api/app/main.py +58 LOC (route /.well-known/jwks.json TRONG block central-only + 503 fallback envelope)"
    - "Hub_All/api/app/config.py +8 LOC (Settings.central_jwks_url: str | None = None)"
    - "Hub_All/docker-compose.yml +9 LOC (env CENTRAL_JWKS_URL × 3 hub con yte/duoc/hcns)"
    - "Hub_All/docker-compose.override.yml.template +2 LOC (env CENTRAL_JWKS_URL cho hub mới FACTOR-04 inherit)"

key-decisions:
  - "D-V3-Phase3-A (LOCKED): JWKS endpoint RFC 7517 — KHÔNG shared keypair file mount / KHÔNG cookie domain .medinet.vn (rotation phức tạp + subpath Phase 5 conflict)"
  - "D-V3-Phase3-D (LOCKED): publish layer KHÔNG cache in-process (central rebuild ~1ms mỗi request acceptable + simpler + key rotation hot-reload tự nhiên qua container restart). Cache là concern hub con Plan 03-02"
  - "Claude's Discretion: cryptography stdlib (M2 PyJWT[crypto] baseline) ~10 LOC manual JWK export thay vì jwcrypto (~500KB LGPL dep mới) — tránh dep ngoài cho 10 LOC math"
  - "Cache-Control: public, max-age=3600 — matching Plan 03-02 hub con TTL 1h. KHÔNG ETag vì kid mismatch tự nhiên trigger cache miss khi verify JWT"
  - "Single-key strategy v3.0-a (1 active key + manual rotation `make keys` overwrite → restart central). Multi-key rotation overlap window defer Phase 7 MCP service"

patterns-established:
  - "Pattern 1 (JWK manual export): RSAPublicKey.public_numbers() → int big-endian → base64url unpadded; e=65537 → 'AQAB' constant. Áp dụng lại Phase 7 nếu thêm key rotation/overlap"
  - "Pattern 2 (kid deterministic): hashlib.sha256(pem_bytes).digest()[:8] → base64url unpadded → 11 char. Hub con cache Plan 03-02 dùng kid này làm cache key + mismatch trigger refresh"
  - "Pattern 3 (mount conditional + 503 fallback): route mount trong `if settings.hub_name == 'central':` + try/except OSError/ValueError trong handler → 503 envelope D6 shape (KHÔNG raise — JWKS endpoint là dependency Plan 03-02 phải tường minh fail)"
  - "Pattern 4 (env intra-network Docker DNS): CENTRAL_JWKS_URL=http://python-api-central:8080/.well-known/jwks.json — Docker service DNS resolve trong network medinet_net, KHÔNG cần TLS intra-network"

requirements-completed:
  - SSO-01

# Metrics
duration: 18min
completed: 2026-05-22
---

# Phase 3 Plan 01: JWKS Publish Layer Summary

**Central FastAPI expose `GET /.well-known/jwks.json` RFC 7517 JWK Set qua module `app/auth/jwks.py` mới (publish_jwks + load_public_key_as_jwk helpers cryptography stdlib) — hub con strip endpoint 404 envelope D6 + Settings.central_jwks_url field mới cho Plan 03-02 consume; docker-compose 3 hub con + FACTOR-04 template thêm env CENTRAL_JWKS_URL intra-network.**

## Performance

- **Duration:** ~18 phút (TDD RED + GREEN + Task 2 docker-compose + SUMMARY)
- **Started:** 2026-05-22T15:45:00Z
- **Completed:** 2026-05-22T16:03:00Z
- **Tasks:** 2/2 (Task 1 TDD RED+GREEN + Task 2 docker-compose)
- **Files modified:** 6 (3 mới + 3 sửa)

## Accomplishments

- Module `api/app/auth/jwks.py` mới với 4 export công khai (`publish_jwks`, `load_public_key_as_jwk`, `JWK`, `JWKSet` TypedDict) + 2 helper nội bộ (`_derive_kid`, `_int_to_base64url`) RFC 7517/7518 compliant
- Central FastAPI mount `GET /.well-known/jwks.json` route trong block central-only (FACTOR-02 enforce); response shape `{"keys":[<JWK>]}` + header `Cache-Control: public, max-age=3600` + 503 fallback envelope D6 nếu PEM missing
- Hub con (yte/duoc/hcns) strip endpoint tự động → 404 envelope D6 `{success:false, error:{code:"NOT_FOUND",...}}` qua Starlette HTTPException handler Plan 02-03 carry forward — KHÔNG cần code mới
- Settings field `central_jwks_url: str | None = None` (default None ở central + hub con) — Plan 03-02 sẽ add `@model_validator` enforce hub con required
- Docker-compose `CENTRAL_JWKS_URL=http://python-api-central:8080/.well-known/jwks.json` env cho 3 hub con + `docker-compose.override.yml.template` (FACTOR-04 hub mới `make hub-add` auto-inherit)
- 9 unit test PASS (5.24s) — 7 publish layer (shape RFC 7517 + auto-kid + deterministic + reject non-RSA/missing-file) + 2 mount conditional + Settings default

## Task Commits

Each task was committed atomically (TDD pattern Task 1):

1. **Task 1 RED — Failing test** — `7a963c2` (test: 9 unit test JWKS publish layer)
2. **Task 1 GREEN — Implementation** — `d8cc3e5` (feat: jwks.py + main.py route + config field)
3. **Task 2 — Docker compose env** — `e3b72be` (feat: docker-compose CENTRAL_JWKS_URL env 3 hub con + template)

**Plan metadata:** sẽ commit cùng SUMMARY.md (`docs(03-01): them SUMMARY.md JWKS publish layer ship`)

_Note: Task 1 TDD compliant — RED (test commit `7a963c2`) → GREEN (impl commit `d8cc3e5` — gate verify `test(...)` trước `feat(...)` ✓). REFACTOR phase KHÔNG cần (code clean ngay)._

## TDD Gate Compliance

| Gate | Commit | Type | Status |
|------|--------|------|--------|
| RED  | `7a963c2` | test | ✓ ImportError verify trước impl |
| GREEN | `d8cc3e5` | feat | ✓ 9/9 PASS sau impl |
| REFACTOR | (skipped) | — | KHÔNG cần — code clean ngay sau GREEN |

## Files Created/Modified

### Created

- **`Hub_All/api/app/auth/jwks.py`** (137 LOC) — JWKS publish module
  - `_KID_BYTE_LENGTH = 8` constant
  - `JWK` + `JWKSet` TypedDict (RFC 7517 strict typing)
  - `_int_to_base64url(n)` — big-int → base64url unpadded RFC 7518 §6.3.1
  - `_derive_kid(pem_bytes)` — SHA-256 8-byte prefix base64url 11 char (deterministic rotation detect)
  - `load_public_key_as_jwk(pem_path, kid=None)` — PEM RSAPublicKey → JWK dict; raise OSError/ValueError defensive
  - `publish_jwks(public_key_path)` → JWKSet single-key strategy v3.0-a
- **`Hub_All/api/tests/unit/test_jwks_publish.py`** (228 LOC) — 9 unit test (7 publish + 2 mount)
- **`Hub_All/.planning/phases/03-auth-sso-hub-ids-jwt/03-01-SUMMARY.md`** (file này)

### Modified

- **`Hub_All/api/app/main.py`** (+58 LOC) — Thêm route `@app.get("/.well-known/jwks.json")` TRONG block central-only sau 9 router `include_router(...)`. Handler `jwks_endpoint()` async wrap try/except `(OSError, ValueError)` → 503 envelope D6 `{success:false, error:{code:"JWKS_UNAVAILABLE", ...}}`. Success path return `StarletteJSONResponse(content=jwks, headers={"Cache-Control": "public, max-age=3600"})`.
- **`Hub_All/api/app/config.py`** (+8 LOC) — Settings field `central_jwks_url: str | None = None` sau JWT block (line ~102). Comment ghi rõ Plan 03-02 sẽ add `@model_validator` enforce hub con required.
- **`Hub_All/docker-compose.yml`** (+9 LOC) — env `CENTRAL_JWKS_URL: http://python-api-central:8080/.well-known/jwks.json` × 3 hub con (yte/duoc/hcns). Central block KHÔNG sửa.
- **`Hub_All/docker-compose.override.yml.template`** (+2 LOC) — env CENTRAL_JWKS_URL cho hub mới `make hub-add` auto-inherit (FACTOR-04 Plan 02-05 carry forward).

## JWK Set Sample Response (RFC 7517)

`GET /.well-known/jwks.json` trên central (live verify Plan 03-01 với keypair M2 4096-bit):

```json
{
  "keys": [
    {
      "kty": "RSA",
      "kid": "hDRHjB_zZNY",
      "use": "sig",
      "alg": "RS256",
      "n": "nUcYYPvWB96umJIA0EBs3JvSC2LRjmJFf-N-LNUE9AZ9viXuvFGVxh277uWRG2YRNErVfjNqZ2_Yvo-318HyaZCLkLu7S0VKCFoMQiAdAboP8qhTghRPIBXm1DDQLDkhaF1m_5nzdV2o8IDWzfengIi5x2BdAaYjqXpyeNsFFPaE0hZbjd0zh_5VpW600gMgw_Gy0oHlQSdQmKV7FPbDWkiSY4KHP9iVjlmJm16xindWMkJ2uCHDRxpitcypZaQOtSG-grHQG-ewNLrRSEa95v9v8wMdoYUH0SKqN329sLRJGjcb7hOtyLTltnqhBBXm-JuZK_80N3J73mG7Wl-Y2M61QcLLPOG2JIPXdwYp2l8aYW-_5nOIQ-e-tx ... (modulus 683 char total cho 4096-bit RSA)",
      "e": "AQAB"
    }
  ]
}
```

**Headers:**
```
HTTP/1.1 200 OK
Content-Type: application/json
Cache-Control: public, max-age=3600
```

**Kid format:** `hDRHjB_zZNY` = base64url(SHA-256(public.pem)[:8]) — 11 char unpadded. Khi `make keys` overwrite PEM → kid mới tự nhiên → hub con cache Plan 03-02 phát hiện qua kid mismatch khi verify JWT.

**Hub con (yte/duoc/hcns) response:**
```json
HTTP/1.1 404 Not Found
Content-Type: application/json

{
  "success": false,
  "data": null,
  "error": {"code": "NOT_FOUND", "message": "Not Found"},
  "meta": null
}
```

## Decisions Made

- **JWKS endpoint pattern RFC 7517** (D-V3-Phase3-A LOCKED 2026-05-22 ở `/gsd-discuss-phase 3`) — chống shared keypair file mount (rotation phức tạp + secret leak surface area lớn) + cookie domain `.medinet.vn` (subpath Phase 5 conflict).
- **KHÔNG cache JWK in-process ở publish layer** (D-V3-Phase3-D LOCKED) — central rebuild mỗi request ~1ms acceptable; cache là concern hub con (Plan 03-02 in-process LRU). Restart central → key rotation tự nhiên active ngay.
- **`cryptography` stdlib thay vì `jwcrypto`** (Claude's Discretion overruling 03-CONTEXT.md initial suggestion) — analysis post-decision cho thấy 10 LOC manual (`RSAPublicNumbers` → `_int_to_base64url`) rẻ hơn dep mới ~500KB LGPL. M2 PyJWT[crypto] đã pull `cryptography` baseline.
- **Cache-Control: public, max-age=3600** — matching Plan 03-02 hub con TTL 1h. KHÔNG ETag vì key rotation → kid đổi → cache miss tự nhiên khi verify JWT thấy kid mismatch.
- **`central_jwks_url` default None** (KHÔNG enforce required ở Plan 03-01) — Plan 03-02 sẽ add `@model_validator(mode="after")` raise ValueError nếu `hub_name != "central"` + `central_jwks_url is None` (fail-loud boot startup).
- **503 fallback envelope D6 `JWKS_UNAVAILABLE` code** — `try/except (OSError, ValueError)` trong handler thay vì raise. Lý do: KHÔNG để Starlette HTTPException handler bọc lại (Plan 02-03 carry forward chỉ render `NOT_FOUND` cho 404); JWKS-specific code tường minh giúp hub con + frontend differentiate "endpoint không exist" vs "endpoint xuống tạm thời".

## Deviations from Plan

**None - plan executed exactly as written.**

1 ruff F401 minor fix-up trong commit GREEN (`d8cc3e5`) — remove `JWK` import unused trong test file (test chỉ dùng `JWKSet`; `JWK` được dùng implicit qua `jwks["keys"][0]` dict access). Đây là post-write cleanup KHÔNG phải deviation rule — plan ghi rõ `__all__` export `JWK` + `JWKSet` + 2 function, test file chỉ cần `JWKSet` cho type hint thực tế. Đã commit cùng GREEN.

---

**Total deviations:** 0 deviation rule
**Impact on plan:** Plan executed exactly as written. 9/9 unit test PASS RED→GREEN gate hoàn chỉnh.

## Authentication Gates

None - JWKS endpoint là public (KHÔNG auth). Plan 03-02 hub con consume endpoint cũng KHÔNG cần auth (intra-network Docker DNS).

## Issues Encountered

None - TDD RED gate (`7a963c2`) verify ImportError chính xác trước impl; GREEN gate (`d8cc3e5`) 9/9 PASS lần đầu. Docker compose render exit 0 lần đầu.

## Verification Results

### Lint + Type

| Tool | Files | Result |
|------|-------|--------|
| `ruff check` | `app/auth/jwks.py app/main.py app/config.py tests/unit/test_jwks_publish.py` | All checks passed |
| `mypy --strict` | `app/auth/jwks.py app/config.py` | Success: no issues |
| `mypy --strict` | `app/main.py` | Success: no issues |

### Unit Tests

| Suite | Tests | PASS | Time |
|-------|-------|------|------|
| `test_jwks_publish.py` (Plan 03-01 mới) | 9 | 9/9 (100%) | 5.24s |
| `test_main_factory.py` (Phase 2 regression) | 9 | 9/9 | bao gồm |
| `test_config_hub_name.py` (Phase 1 regression) | 11 | 11/11 | bao gồm |
| `test_config_hub_name_dynamic.py` (Phase 2 FACTOR-04 regression) | 29 | 29/29 | bao gồm |
| **Phase 1+2 regression (toàn bộ liên quan)** | **49** | **49/49 (100%)** | **5.16s** |
| **Tổng (regression + mới)** | **58** | **58/58 (100%)** | — |

### Docker Compose

```bash
cd Hub_All && docker compose config --quiet
# exit=0

grep -c CENTRAL_JWKS_URL Hub_All/docker-compose.yml
# 3 (yte + duoc + hcns)

grep -c CENTRAL_JWKS_URL Hub_All/docker-compose.override.yml.template
# 1 (FACTOR-04 hub mới inherit)
```

## Threat Model Results (6 STRIDE threat từ Plan 03-01)

| Threat ID | Category | Severity | Disposition | Status |
|-----------|----------|----------|-------------|--------|
| **T-03-01-01** | Information Disclosure (public modulus + exponent leak) | low | accept | ✓ ACCEPTED — RFC 7517 by-design; attacker chỉ verify JWT, KHÔNG forge (cần private.pem) |
| **T-03-01-02** | Tampering (MITM thay JWKS intra-network → hub con cache fake key) | medium | accept | ✓ ACCEPTED — v3.0-a deploy cùng Docker network medinet_net; cache TTL 1h hard limit Plan 03-02; Phase 5 PROXY-01 add TLS cross-host nếu cần |
| **T-03-01-03** | DoS (attacker spam endpoint → central CPU spike) | low | mitigate | ✓ MITIGATED — Cache-Control 1h cho Caddy + browser cache; KHÔNG hit DB/cocoindex; Caddy WAF rate limit defer v4.0 |
| **T-03-01-04** | Information Disclosure (logger error leak file system path) | low | accept | ✓ ACCEPTED — path `api/keys/public.pem` đã expose qua Settings default + repo public; KHÔNG chứa secret |
| **T-03-01-05** | Tampering (operator `make keys` overwrite trong khi serve JWT → window mismatch) | medium | mitigate | ✓ MITIGATED — JWTManager load PEM 1 lần ở constructor (M2); overwrite → cần restart central; JWT cũ vẫn pass verify ở hub con TTL 1h; Plan 03-03 blacklist jti logout. Proper rotation overlap defer Phase 7 |
| **T-03-01-06** | EoP (hub con tự publish JWKS bypass FACTOR-02) | medium | mitigate | ✓ MITIGATED — D-V3-Phase3-A LOCKED + route mount TRONG `if settings.hub_name == "central":` block; unit test `test_jwks_endpoint_mount_central_only` verify hub yte → 404 envelope D6 |

**Tổng:** 6/6 threat addressed (3 accept + 3 mitigate, KHÔNG transfer/avoid/defer). KHÔNG ship threat mới phát sinh.

## Threat Flags

(scan files modified — không có surface mới ngoài threat_model đã liệt kê)

None - new surface area khớp 100% threat_model Plan 03-01.

## Self-Check

### Created Files Exist

| File | Status |
|------|--------|
| `Hub_All/api/app/auth/jwks.py` | FOUND |
| `Hub_All/api/tests/unit/test_jwks_publish.py` | FOUND |
| `Hub_All/.planning/phases/03-auth-sso-hub-ids-jwt/03-01-SUMMARY.md` | FOUND (file này) |

### Modified Files Verified

| File | Verify | Status |
|------|--------|--------|
| `Hub_All/api/app/main.py` | grep `/.well-known/jwks.json` ≥ 1 | OK |
| `Hub_All/api/app/main.py` | grep `JWKS_UNAVAILABLE` ≥ 1 | OK |
| `Hub_All/api/app/main.py` | grep `Cache-Control` ≥ 1 | OK |
| `Hub_All/api/app/config.py` | grep `central_jwks_url` ≥ 1 | OK |
| `Hub_All/docker-compose.yml` | grep `CENTRAL_JWKS_URL` = 3 | OK |
| `Hub_All/docker-compose.override.yml.template` | grep `CENTRAL_JWKS_URL` = 1 | OK |

### Commits Exist

| Commit | Verify | Status |
|--------|--------|--------|
| `7a963c2` test(03-01) RED | `git log --oneline \| grep 7a963c2` | FOUND |
| `d8cc3e5` feat(03-01) GREEN | `git log --oneline \| grep d8cc3e5` | FOUND |
| `e3b72be` feat(03-01) docker compose | `git log --oneline \| grep e3b72be` | FOUND |

## Self-Check: PASSED

## Next Phase Readiness

### Plan 03-02 (Wave 2 — UNBLOCKED) — Hub con JWKSCache

- ✅ Central `/.well-known/jwks.json` ship → hub con consume endpoint này blocking startup
- ✅ Settings.central_jwks_url field exist (default None) — Plan 03-02 add `@model_validator(mode="after")` enforce hub con required
- ✅ docker-compose CENTRAL_JWKS_URL env wire-up cho 3 hub con sẵn sàng
- 📋 Plan 03-02 ship: `JWKSCache` class trong CÙNG `api/app/auth/jwks.py` (D-V3-Phase3-D in-process LRU `functools.lru_cache(maxsize=2)` + asyncio refresh task TTL 1h)
- 📋 Plan 03-02 ship: lifespan startup blocking fetch (R-V3-5 fail-loud boot — process exit 1 nếu central down KHI boot)
- 📋 Plan 03-02 ship: `get_current_user` dependency branch verify path (central dùng local private.pem; hub con dùng JWKS cache)

### Plan 03-03 (Wave 3) — JWT iss/aud/hub_ids claim refactor

- 🔓 KHÔNG block trên Plan 03-01 (kid + PEM keypair shared) — có thể bắt đầu song song Plan 03-02
- 📋 JWT_ISSUER đổi `"medinet-wiki"` → `"https://central/"` + `aud=["medinet-wiki"]` + `hub_ids` REQUIRED claim

### Plan 03-04 (Wave 4) + Plan 03-05 (Wave 5 closeout)

- Depends Plan 03-02 + 03-03 — defer sau Wave 2/3 close

### v3.0-a EXIT GATE (giữa Phase 3-4)

- 🚦 Demo 1 hub con (yte) + central + JWT SSO + golden path PASS → user accept là điều kiện tiếp tục v3.0-b (Phase 4-7)
- Plan 03-01 đóng góp 1/5 plan Phase 3; 4 plan còn lại (03-02..05) sẽ unblock theo wave

---

*Phase: 03-auth-sso-hub-ids-jwt*
*Plan: 01 (SSO-01 publish layer — BLOCKING Wave 1)*
*Completed: 2026-05-22*
*Test result: 9/9 PASS unit (test_jwks_publish.py) + 49/49 Phase 1+2 regression PASS — KHÔNG break*
