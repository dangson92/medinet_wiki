---
phase: 10-hardening-observability-docs
plan: 04
subsystem: mcp-oauth-security
tags: [mcp, oauth, cors, security, crit-01, audit-2026-05-21, plan-10-04]

# Dependency graph
requires:
  - phase: 08.3-07
    provides: "CRIT-02 đã đóng — chỉ add CORS ở MỘT TẦNG (subdomain inner / path-prefix wrapper). Plan 10-04 build trên đó: KHÔNG vỡ regression test_cors_no_duplicate_in_path_prefix_mode."
  - phase: 08.3-audit-2026-05-21
    provides: "Audit CRIT-01 ghi nhận CORS allow_origins=* cho /token + /authorize + /revoke lỏng. Plan 08.3-07 defer fix → Plan 10-04 đóng."
provides:
  - "MultiPolicyCORSMiddleware ASGI wrapper tách 2 policy theo path"
  - "Metadata path (/.well-known/oauth-*, /.well-known/openid-configuration) → ACAO * (RFC 8414 §3.1 + RFC 9728 §3.1)"
  - "Sensitive path (/token, /authorize, /revoke, /register, /mcp[/*]) → echo whitelist origin (default claude.ai + inspector + 2 localhost dev)"
  - "Setting `mcp_oauth_sensitive_allowed_origins` env-driven comma-separated cho ops override"
  - "Defense-in-depth CRIT-02 regression guard — middleware skip inject header nếu inner đã set (SDK MetadataHandler)"
  - "CRIT-01 (Phase 8.3 audit 2026-05-21) đóng — malicious browser tab/extension KHÔNG gọi được /token từ origin lạ"
affects: [phase-10-uat]

# Tech tracking
tech-stack:
  added:
    - "pydantic_settings.NoDecode + Annotated[list[str], NoDecode] — disable JSON-decode mặc định để validator mode='before' nhận RAW string env"
  patterns:
    - "ASGI middleware tách CORS policy theo path (subdomain + path-prefix đồng nhất 1 wrapper) — Starlette CORSMiddleware KHÔNG support per-route policy native"
    - "Custom preflight handler trong middleware (KHÔNG forward xuống Router) — vì Starlette Route default KHÔNG có OPTIONS handler riêng cho metadata/transport"
    - "Existing-header check trước khi inject CORS — chống duplicate ACAO khi SDK MetadataHandler tự inject"
    - "validation_alias + NoDecode pattern cho env var prefix đặc biệt (`MCP_OAUTH_SENSITIVE_ALLOWED_ORIGINS` thay vì auto-derive `MCP_MCP_OAUTH_...`)"

key-files:
  created:
    - Hub_All/mcp_service/tests/test_cors_split_policy.py
  modified:
    - Hub_All/mcp_service/mcp_app/server.py
    - Hub_All/mcp_service/mcp_app/config.py
    - Hub_All/.planning/phases/10-hardening-observability-docs/deferred-items.md

key-decisions:
  - "D-10-04-A: Phương án B (1 custom MultiPolicyCORSMiddleware) thay vì A (2 Starlette CORSMiddleware) — subdomain mode chỉ có 1 app level (KHÔNG có 2-level wrapper+inner như path-prefix), Starlette CORSMiddleware KHÔNG support per-route policy native. Đơn giản hơn + deterministic test + xài chung 2 mode deploy."
  - "D-10-04-B: Middleware tự handle OPTIONS preflight (KHÔNG forward) — Starlette Route default cho metadata/transport KHÔNG có OPTIONS handler, pass-through sẽ 405/404. Build preflight response tay với ACAO + ACAM + ACAH + Max-Age."
  - "D-10-04-C: Existing-header guard skip inject ACAO nếu inner đã set — CRIT-02 regression guard (Plan 08.3-07 đã đóng). SDK MetadataHandler tự inject ACAO * cho metadata response, middleware Plan 10-04 KHÔNG được append lần 2."
  - "D-10-04-D: `_is_metadata_path` cover cả path-prefix variant `/<prefix>/.well-known/*` — substring match `.well-known/oauth-` HOẶC `.well-known/openid-configuration` thay vì chỉ startswith. Lý do: path-prefix mode forward request đến inner SDK metadata route ở path `/<prefix>/.well-known/*` (sau Mount)."
  - "D-10-04-E: Setting field name giữ `mcp_oauth_sensitive_allowed_origins` (theo plan) + dùng `validation_alias` ép env `MCP_OAUTH_SENSITIVE_ALLOWED_ORIGINS` thay vì auto-derive `MCP_MCP_OAUTH_...` (env_prefix=MCP_ + field name sẽ ra double prefix sai)."
  - "D-10-04-F: `Annotated[list[str], NoDecode]` để tắt JSON-decode mặc định pydantic-settings — cho phép validator `mode='before'` nhận RAW string env và split comma-separated. Default JSON-decode fail vì comma-separated KHÔNG phải JSON list."
  - "D-10-04-G: CORS wrap order khác nhau 2 mode: subdomain mode CORS NGOÀI _BasicAuthFormShim (path GỐC); path-prefix mode CORS giữa _BasicAuthFormShim và wrapper (path đã rewrite bởi _AsgiPathShim → CORS check `/mcp/token` thay vì `/token`). Cả 2 mode đều đúng vì policy cover cả root + prefix variant của `_SENSITIVE_PATHS`."

patterns-established:
  - "Audit security gap closure: CRIT-01 đóng theo audit Action Plan defer Phase 10 (commit prefix `fix:` tiếng Anh + mô tả tiếng Việt + Co-Authored-By)"
  - "TDD RED → GREEN sequence: 1 test commit (8 case fail vì middleware chưa tồn tại) → 1 implementation commit (middleware + setting + 2 call site)"

requirements-completed: [HARD-02]

# Metrics
duration: ~25min
completed: 2026-05-21
tasks_completed: 1
files_modified: 3
commits: 2
---

# Phase 10 Plan 04: Tách 2 CORS policy CRIT-01 Summary

**2 commit atomic vá CRIT-01 (Phase 8.3 audit 2026-05-21 defer): MultiPolicyCORSMiddleware ASGI wrapper tách metadata wildcard `*` vs sensitive whitelist origin. 8/8 test mới test_cors_split_policy.py PASS + 143/143 toàn suite mcp_service KHÔNG regression (gồm 23 test test_path_prefix_wrapper cũ + 8 mới). CRIT-02 regression `test_cors_no_duplicate_in_path_prefix_mode` PASS — middleware mới có existing-header guard chống duplicate ACAO khi SDK MetadataHandler đã set. Malicious browser tab/extension gọi /token từ origin lạ → KHÔNG có ACAO header → browser block CORS.**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-05-21
- **Completed:** 2026-05-21
- **Tasks:** 1 (TDD RED + GREEN gộp)
- **Files modified:** 3 (mcp_app/server.py + mcp_app/config.py + deferred-items.md)
- **Files created:** 1 (tests/test_cors_split_policy.py — 348 dòng)
- **Commits:** 2 atomic (b414188 RED / 82720db GREEN)

## Accomplishments

### Task 1: MultiPolicyCORSMiddleware + setting + 2 call site + 8 test (TDD RED → GREEN)

**TDD RED (commit `b414188`):** `tests/test_cors_split_policy.py` 348 dòng — 8 case:

1. `test_metadata_wildcard_subdomain_mode` — GET `/.well-known/oauth-authorization-server` (subdomain mode) với Origin `https://random-attacker.com` → 200 + `Access-Control-Allow-Origin: *` (RFC 8414 §3.1).
2. `test_metadata_wildcard_path_prefix_mode` — GET `/.well-known/oauth-authorization-server/mcp` (path-prefix mode) với Origin `https://evil.attacker.com` → 200 + ACAO `*`.
3. `test_sensitive_whitelist_allowed_origin_token` — OPTIONS `/token` (subdomain) với Origin `https://claude.ai` → 200 + ACAO `https://claude.ai` (KHÔNG wildcard).
4. `test_sensitive_whitelist_rejected_origin` — OPTIONS `/token` với Origin `https://evil.attacker.com` → response 200 KHÔNG có ACAO header → browser block CORS.
5. `test_sensitive_whitelist_path_prefix_mcp_token` — OPTIONS `/mcp/token` (path-prefix) với Origin claude.ai → ACAO echo.
6. `test_sensitive_whitelist_transport_mcp` — OPTIONS `/mcp` (transport) với Origin `http://localhost:6274` (MCP Inspector dev) → ACAO echo.
7. `test_settings_sensitive_origins_default_whitelist` — verify default 4 origin: claude.ai + inspector.modelcontextprotocol.io + localhost:6274 + 127.0.0.1:6274.
8. `test_settings_sensitive_origins_env_comma_separated` — env `MCP_OAUTH_SENSITIVE_ALLOWED_ORIGINS=https://a,https://b,http://c` parse thành list 3 phần tử.

RED phase: 6 fail (setting + middleware chưa tồn tại), 2 pass (metadata wildcard `*` đã có sẵn từ `_add_cors_middleware` cũ).

**TDD GREEN (commit `82720db`):**

**A. `mcp_service/mcp_app/config.py`:**
- Thêm `mcp_oauth_sensitive_allowed_origins: Annotated[list[str], NoDecode]` field với:
  - Default factory 4 origin whitelist
  - `validation_alias="MCP_OAUTH_SENSITIVE_ALLOWED_ORIGINS"` ép env var đúng (KHÔNG bị `env_prefix=MCP_` ép thành `MCP_MCP_OAUTH_...`)
  - `NoDecode` annotation tắt JSON-decode mặc định pydantic-settings → validator `mode="before"` nhận RAW string env
- Thêm `_split_sensitive_origins` validator `mode="before"` split comma-separated string → list[str].

**B. `mcp_service/mcp_app/server.py`:**
- Định nghĩa 2 constant: `_METADATA_PATHS_PREFIX` (3 path metadata) + `_SENSITIVE_PATHS` (9 path sensitive frozenset).
- Helper `_is_metadata_path(path)` — direct startswith match HOẶC substring `.well-known/oauth-`/`.well-known/openid-configuration` (cover path-prefix variant `/<prefix>/.well-known/*` sau Mount forward).
- Helper `_is_sensitive_path(path)` — exact match `_SENSITIVE_PATHS` HOẶC startswith `/mcp/` (transport variant).
- Class `_MultiPolicyCORSMiddleware` ASGI wrapper:
  - `__init__(app, sensitive_origins)` — frozenset whitelist O(1) lookup.
  - `__call__(scope, receive, send)` — pass-through scope khác `http`; non-OPTIONS forward xuống inner với wrapped send injecting CORS header (theo policy + skip nếu inner đã set); OPTIONS handle full response trong middleware.
  - `_build_cors_headers(path, origin)` — metadata → ACAO `*`; sensitive + whitelist match → ACAO echo origin + Vary: Origin; else → rỗng.
  - `_build_preflight_response(path, origin)` — full ACAM/ACAH/Max-Age cho whitelist match; else 200 trống (browser block).
  - `_send_preflight(response, send)` + `_extract_origin(headers)` + `__getattr__(name)` delegate.
- **Xoá** hàm `_add_cors_middleware` cũ (line ~820 — 22 dòng).
- **Thay** 2 call site:
  - **Subdomain mode** (line ~676): `cors_wrapped = _MultiPolicyCORSMiddleware(_BasicAuthFormShim(inner), settings.mcp_oauth_sensitive_allowed_origins); return cors_wrapped` — CORS NGOÀI _BasicAuthFormShim.
  - **Path-prefix mode** (line ~767): `wrapper_with_cors = _MultiPolicyCORSMiddleware(wrapper, settings.mcp_oauth_sensitive_allowed_origins)`; return `_AsgiPathShim(_BasicAuthFormShim(wrapper_with_cors), prefix=prefix)` — CORS giữa _BasicAuthFormShim và wrapper (path đã được _AsgiPathShim rewrite).

**C. Deviation runtime: Existing-header guard (Rule 1 - Bug)**

**Found during:** chạy regression test_path_prefix_wrapper.py — test `test_cors_no_duplicate_in_path_prefix_mode` FAIL với 2 ACAO header (1 từ SDK MetadataHandler + 1 từ middleware Plan 10-04).

**Issue:** SDK MCP Python tự inject `Access-Control-Allow-Origin: *` vào response metadata khi request có Origin header. Middleware Plan 10-04 áp dụng metadata policy lại inject ACAO lần 2 → duplicate → CRIT-02 vỡ.

**Fix:** Trong `_wrapped_send`, build set tên header đã tồn tại (lower-case bytes) trước khi append CORS header — skip nếu inner đã set. Áp dụng cho mọi CORS header (đặc biệt `access-control-allow-origin`).

**Files modified:** `mcp_service/mcp_app/server.py` (block `_wrapped_send`).

**Commit:** `82720db` (gộp vào Task 1 GREEN — fix DURING task, không tách commit riêng).

## Audit gap closure tracking

Map audit 2026-05-21 finding CRIT-01 → Plan 10-04 fix:

| Audit ID | Severity | Status trước Plan 10-04 | Trạng thái sau Plan 10-04 | Fix ở |
|---|---|---|---|---|
| CRIT-01 | Critical | DEFER (Plan 08.3-07 đã ghi defer Phase 10) | **ĐÓNG** | Task 1 server.py + config.py (MultiPolicyCORSMiddleware + setting + 2 call site) |

**Acceptance criteria Plan 10-04 verify:**

- [x] Endpoint metadata `/.well-known/*` trả ACAO `*` (RFC 8414 §3.1) — 2/2 test PASS (subdomain + path-prefix mode)
- [x] Endpoint nhạy cảm `/token, /authorize, /revoke, /register, /mcp` trả ACAO chỉ với whitelist origin — 3/3 test PASS (claude.ai allowed + Inspector localhost:6274 + path-prefix /mcp/token)
- [x] Browser POST /token từ origin lạ → preflight FAIL hoặc CORS reject — 1/1 test PASS (Origin evil.attacker.com → KHÔNG có ACAO header)
- [x] CRIT-02 regression test enforce — KHÔNG double-add CORS path-prefix mode (Plan 08.3-07 đã đóng) — test_cors_no_duplicate_in_path_prefix_mode PASS (sau existing-header guard)
- [x] Regression: `cd Hub_All/mcp_service && uv run pytest -q` exits 0 — 143/143 PASS (cao hơn baseline 135 yêu cầu)
- [x] Ruff sạch — `uv run ruff check mcp_app/ tests/test_cors_split_policy.py` PASS
- [x] mypy strict KHÔNG thêm error mới — 6 pre-existing errors (DEF-10-04-A defer); 0 new errors do Plan 10-04 sau khi fix `_wrapped_send` dict[str, Any]
- [x] SUMMARY.md 10-04-SUMMARY.md — file này
- [x] STATE.md + ROADMAP.md updated với 10-04 — bước final commit

## Sample CORS behavior verification (manual curl)

```
# (1) Metadata wildcard — Origin lạ vẫn echo *
curl -X GET https://wiki.example.com/.well-known/oauth-authorization-server \
  -H "Origin: https://random-attacker.com" -I
# → Access-Control-Allow-Origin: *

# (2) Sensitive whitelist match — Origin claude.ai → echo
curl -X OPTIONS https://wiki.example.com/token \
  -H "Origin: https://claude.ai" \
  -H "Access-Control-Request-Method: POST" -I
# → Access-Control-Allow-Origin: https://claude.ai
# → Vary: Origin

# (3) Sensitive whitelist rejected — Origin evil.com → KHÔNG có ACAO
curl -X OPTIONS https://wiki.example.com/token \
  -H "Origin: https://evil.attacker.com" \
  -H "Access-Control-Request-Method: POST" -I
# → (response 200 KHÔNG có Access-Control-Allow-Origin header)
# → browser block CORS request
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Existing-header guard chống duplicate ACAO khi SDK MetadataHandler đã inject**

- **Found during:** Task 1 GREEN — regression test_path_prefix_wrapper.py `test_cors_no_duplicate_in_path_prefix_mode` FAIL với 2 ACAO header trong path-prefix mode response (1 từ SDK MetadataHandler + 1 từ middleware Plan 10-04).
- **Issue:** Plan ban đầu KHÔNG dự đoán SDK MCP Python tự inject ACAO `*` vào response metadata khi Origin header có mặt. Middleware Plan 10-04 áp dụng metadata policy lại inject ACAO lần 2 → duplicate → CRIT-02 vỡ.
- **Fix:** Trong `_wrapped_send`, build set tên header đã tồn tại trước khi append → skip nếu inner đã set. Pattern defense-in-depth chống duplicate (CRIT-02 regression guard built-in middleware).
- **Files modified:** `Hub_All/mcp_service/mcp_app/server.py` (block `_wrapped_send`)
- **Commit:** `82720db` (gộp vào Task 1 GREEN — fix DURING task)

**2. [Rule 1 - Bug] `_is_metadata_path` cover path-prefix variant `/<prefix>/.well-known/*`**

- **Found during:** Task 1 GREEN — cùng test_cors_no_duplicate_in_path_prefix_mode failure analysis.
- **Issue:** Plan định nghĩa `_METADATA_PATHS_PREFIX = ("/.well-known/oauth-authorization-server", ...)` chỉ startswith match → path `/mcp/.well-known/oauth-authorization-server` (path-prefix mode forward đến inner SDK) KHÔNG match → fall through sensitive policy → middleware echo whitelist origin THAY VÌ wildcard → duplicate với SDK ACAO `*`.
- **Fix:** `_is_metadata_path` thêm fallback substring `.well-known/oauth-` HOẶC `.well-known/openid-configuration` để cover cả prefix variant.
- **Files modified:** Cùng commit `82720db`.

**3. [Rule 3 - Blocking] `validation_alias` + `NoDecode` cho env var parse comma-separated**

- **Found during:** Task 1 GREEN — test `test_settings_sensitive_origins_env_comma_separated` FAIL initially vì:
  1. Field name `mcp_oauth_sensitive_allowed_origins` + `env_prefix=MCP_` → pydantic-settings derive env `MCP_MCP_OAUTH_SENSITIVE_ALLOWED_ORIGINS` (double prefix sai)
  2. Pydantic-settings cố parse list từ env như JSON → comma-separated string FAIL với SettingsError
- **Fix:**
  1. `Field(validation_alias="MCP_OAUTH_SENSITIVE_ALLOWED_ORIGINS")` ép env name đúng.
  2. `Annotated[list[str], NoDecode]` tắt JSON-decode → validator `mode="before"` nhận RAW string và split comma.
- **Files modified:** `Hub_All/mcp_service/mcp_app/config.py`
- **Commit:** Cùng `82720db`.

### Deferred (Out-of-scope)

**1. Pre-existing mypy --strict errors trong `mcp_service/mcp_app/server.py` — 6 errors**

- Verify: `git stash` rồi mypy → 6 errors như trên trước Plan 10-04 (Context type-arg + _receive return type Phase 8.3).
- Plan 10-04 KHÔNG thêm error mới (đã fix `_wrapped_send: dict[str, Any]`).
- Log vào `Hub_All/.planning/phases/10-hardening-observability-docs/deferred-items.md` (DEF-10-04-A).
- Resolution: migrate khi SDK MCP upstream expose proper `Context[T]` generic. Defer v4.0.

**2. Pre-existing ruff E402 + UP012 trong `tests/test_path_prefix_wrapper.py` — 4 errors**

- Source: Plan 08.3-07 SUMMARY note. Plan 10-04 KHÔNG đụng file này.
- Log vào deferred-items.md (DEF-10-04-B).
- Resolution: chore commit riêng.

## Self-Check: PASSED

### Files created/modified verify

- FOUND: Hub_All/mcp_service/mcp_app/server.py (modified — MultiPolicyCORSMiddleware + 2 call site, +295/-46 LOC)
- FOUND: Hub_All/mcp_service/mcp_app/config.py (modified — mcp_oauth_sensitive_allowed_origins setting + validator, +27 LOC)
- FOUND: Hub_All/mcp_service/tests/test_cors_split_policy.py (created — 348 dòng, 8 test case)
- FOUND: Hub_All/.planning/phases/10-hardening-observability-docs/deferred-items.md (modified — DEF-10-04-A + DEF-10-04-B)

### Commits verify

- FOUND: `b414188` test(10-04): thêm test_cors_split_policy.py 8 case cho CRIT-01 (TDD RED)
- FOUND: `82720db` fix(10-04): tách 2 CORS policy CRIT-01 — metadata wildcard + sensitive whitelist

### Regression verify

- `uv run pytest -q` exits 0 — **143/143 PASS** trong 3.18s (cao hơn baseline plan ≥135)
- `uv run pytest tests/test_cors_split_policy.py -v` — 8/8 PASS
- `uv run pytest tests/test_path_prefix_wrapper.py -v` — 23/23 PASS (gồm `test_cors_no_duplicate_in_path_prefix_mode` CRIT-02 regression)
- `uv run ruff check mcp_app/server.py mcp_app/config.py tests/test_cors_split_policy.py` exits 0
- `uv run mypy --strict mcp_app/config.py` exits 0
- `uv run mypy --strict mcp_app/server.py` — 6 errors pre-existing (DEF-10-04-A), 0 new errors

### Acceptance criteria Plan 10-04 verify

- `_add_cors_middleware` cũ đã xoá ✓
- `_MultiPolicyCORSMiddleware` ASGI wrapper tồn tại ✓
- Setting `mcp_oauth_sensitive_allowed_origins` default 4 origin whitelist + env override comma-separated ✓
- Metadata path (5 route /.well-known/*) → ACAO `*` ✓
- Sensitive path (/token, /authorize, /revoke, /register, /mcp[/*]) → echo whitelist match, KHÔNG match → KHÔNG echo ✓
- 6 test critical case PASS — cover cả 2 mode (subdomain + path-prefix) ✓ (+ 2 test setting parse)
- Suite mcp_service không regression sau fix ✓ (143/143)
- CRIT-01 (Phase 8.3 audit) closed — document mapping ✓

Toàn bộ acceptance criteria của Plan 10-04 PASS.

## Threat Flags

Không có threat surface mới ngoài audit. Plan 10-04 ĐÓNG threat đã registered trong `<threat_model>`:

- T-10-04-01 (Information Disclosure — malicious tab/extension gọi /token từ origin lạ) — **mitigate ĐẠT** Task 1.
- T-10-04-02 (Spoofing — malicious server fake Origin header server-to-server) — **accept** (CORS chỉ relevant browser SOP; defense thật là auth/PKCE/client_id mismatch Plan 08.3-07).
- T-10-04-03 (Tampering — ops thêm origin malicious vào whitelist) — **accept** (env-driven, ops trách nhiệm; defer document trong DEPLOY.md Plan 10-05).
- T-10-04-04 (Denial of Service — preflight flood probe whitelist) — **accept** (defer rate limit Caddy/Cloudflare hardening v4.0).
