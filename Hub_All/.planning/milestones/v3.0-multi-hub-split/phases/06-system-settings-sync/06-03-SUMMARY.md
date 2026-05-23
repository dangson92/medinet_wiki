---
phase: 06
plan: 03
subsystem: settings-sync
tags: [settings-sync, refactor, router-extend, dependency, internal-auth, wave-3]
status: done
date_completed: 2026-05-23
duration_minutes: 22

requires:
  - Wave 1 scaffold Plan 06-01 (Settings.settings_proxy_secret + 6 Prometheus collector + keys constants)
  - Wave 2 client Plan 06-02 (ApiKeyVerifyClient.verify() signature ready cho app.state)
  - M2 baseline (ApiKeyService.verify_key AES-GCM + require_role admin gate + search_cache.py fail-open publish)
  - Phase 2 FACTOR-02 (api_keys_router central-only mount conditional Plan 02-01)

provides:
  - "api/app/auth/api_key.py — require_api_key branch hub_name (central=local M2 / hub con=app.state.api_key_verify_client proxy)"
  - "api/app/auth/dependencies.py — require_internal_auth dependency moi (hmac.compare_digest constant-time X-Internal-Auth check)"
  - "api/app/routers/rag_config.py — update_rag_config extend publish settings:invalidate best-effort fail-open"
  - "api/app/routers/api_keys.py — POST /api/api-keys/verify endpoint moi (central-only mount FACTOR-02)"
  - "api/app/schemas/api_keys.py — VerifyApiKeyRequest Pydantic schema (api_key min_length=1 max_length=256)"

affects:
  - Plan 06-04 Wave 4 — lifespan store app.state.api_key_verify_client (consume require_api_key hub con branch 503 fail-loud)
  - Plan 06-04 Wave 4 — lifespan settings_subscriber_loop consume settings:invalidate channel publish (Wave 3 emit cross-process)
  - Plan 06-05 Wave 5 — closeout docs update REQUIREMENTS.md SETTINGS-02 + SETTINGS-03 mark [x]
  - Hub con runtime — Phase 6 ApiKeyVerifyClient (Plan 06-02) call POST /api/api-keys/verify endpoint moi (Plan 06-03 ship server side)

tech-stack:
  added: []  # KHONG add dep moi — pure stdlib hmac + httpx (M2 baseline) + pydantic (M2 baseline)
  patterns:
    - "Branch dependency theo settings.hub_name (carry forward get_current_user Plan 03-02 Phase 3 SSO-01 pattern)"
    - "Constant-time secret compare hmac.compare_digest (T-06-03-01 timing attack mitigation)"
    - "Best-effort fail-open Redis publish try/except + log.warning (search_cache.py M2 pattern carry forward)"
    - "FACTOR-02 carry forward — endpoint moi mount qua existing api_keys_router central-only conditional"
    - "Pydantic Field min_length/max_length cho body validation (T-06-03-06 user input bounded)"
    - "FastAPI Depends(require_internal_auth) gate internal endpoint (KHONG mix admin/user-facing auth)"

key-files:
  created:
    - "api/tests/unit/test_require_api_key_hub_branch.py (177 LOC — 6 test central + hub con branch + 503 + 401 + missing header)"
    - "api/tests/unit/test_require_internal_auth.py (159 LOC — 6 test correct/wrong/missing/empty + hmac spy + dynamic secret)"
    - "api/tests/unit/test_rag_config_publish_invalidate.py (172 LOC — 4 test publish success + redis None + ConnectionError + service error)"
    - "api/tests/unit/test_api_keys_verify_endpoint.py (201 LOC — 6 test valid/wrong header/missing header/invalid key/missing body/schema validation)"

  modified:
    - "api/app/auth/api_key.py (+45 LOC — request: Request param + branch settings.hub_name central=ApiKeyService / hub con=app.state.api_key_verify_client + 503 fail-loud)"
    - "api/app/auth/dependencies.py (+38 LOC — require_internal_auth async dep + hmac.compare_digest + 401 INTERNAL_AUTH_FAIL envelope)"
    - "api/app/routers/rag_config.py (+24 LOC — request: Request param + publish settings:invalidate JSON payload best-effort fail-open + import json/time)"
    - "api/app/routers/api_keys.py (+34 LOC — POST /verify endpoint + require_internal_auth dep + Any import + verify_api_key handler raw dict return)"
    - "api/app/schemas/api_keys.py (+11 LOC — VerifyApiKeyRequest BaseModel + api_key Field min/max length)"

decisions:
  - "D-V3-Phase6-A LOCKED — Hub con branch verify path HTTP proxy via app.state.api_key_verify_client; central giu local M2 ApiKeyService.verify_key (KHONG dung verify_key private logic — AES-GCM at-rest M2 AUX-02 unchanged)."
  - "D-V3-Phase6-D LOCKED — Shared secret X-Internal-Auth header constant-time compare qua hmac.compare_digest (T-06-03-01 timing attack mitigation). 32 char min length enforce qua Settings validator Plan 06-01 (128-bit entropy)."
  - "D-V3-Phase6-C LOCKED — 1 channel duy nhat settings:invalidate cho ca 3 category (rag_config / hub_registry / apikey). update_rag_config payload {config_key:'rag_config', hub:'*', timestamp:int} cross-process publish."
  - "FACTOR-02 carry forward — endpoint POST /api/api-keys/verify mount via existing api_keys_router central-only (main.py:704 if settings.hub_name == 'central'). Hub con strip → 404 envelope (M2 ErrorHandlerMiddleware). KHONG can them mount logic."
  - "T-06-03-04 mitigation — publish_invalidate best-effort fail-open try/except + log.warning. Admin PUT KHONG block boi Redis down (TTL natural fallback 60s acceptable < 30s threshold E-V3-4)."
  - "Raw dict return /verify (KHONG envelope) — pattern song song /api/rag-config M2 raw dict. Hub con ApiKeyVerifyClient parse {valid: bool, principal: dict|null} structure (Plan 06-02 client consume)."

metrics:
  duration_minutes: 22
  tasks_completed: 2
  files_created: 4
  files_modified: 5
  tests_added: 22  # 6 + 6 + 4 + 6 — Plan target match exact
  tests_pass: 22
  regression_pass: 452  # 430 baseline (Plan 06-02) + 22 Wave 3
  full_unit_total: 452
  lint_pass: true
  mypy_strict_pass: true
  integration_regression_pass: 19  # 15 factor_hub_scoped + 4 rate_limit (require_api_key consumer)
  cluster_regression_pass: 50  # auth + rag_config + api_keys + sso aggregated
---

# Phase 06 Plan 06-03: Wave 3 Refactor Auth + Router Extend Summary

**Wave 3 REQUEST-RESPONSE INTEGRATION** cho Phase 6 System Settings Sync — refactor `require_api_key` dependency branch theo `settings.hub_name` (central giữ M2 local AES-GCM / hub con dùng HTTP proxy via `app.state.api_key_verify_client` Plan 06-02), tạo `require_internal_auth` dependency mới với `hmac.compare_digest` constant-time compare cho header `X-Internal-Auth` (T-06-03-01 timing attack mitigation), extend `update_rag_config` PUT publish `settings:invalidate` channel best-effort fail-open (cross-process invalidate cho Wave 2 subscriber consume), và thêm endpoint MỚI `POST /api/api-keys/verify` central-only mount (FACTOR-02 carry forward) với raw dict return `{valid: bool, principal: dict|null}` (pattern song song /api/rag-config M2 — hub con ApiKeyVerifyClient consume).

## Tasks completed

| Task | Name | Commits | Files |
|------|------|---------|-------|
| 1 | require_api_key branch hub_name + require_internal_auth dep + 12 test (TDD) | a5d9ffb RED + c26e02d GREEN | `api/app/auth/api_key.py`, `api/app/auth/dependencies.py`, `api/tests/unit/test_require_api_key_hub_branch.py`, `api/tests/unit/test_require_internal_auth.py` |
| 2 | update_rag_config publish + POST /api/api-keys/verify + 10 test (TDD) | 5e807ac RED + 803a0a3 GREEN | `api/app/routers/rag_config.py`, `api/app/routers/api_keys.py`, `api/app/schemas/api_keys.py`, `api/tests/unit/test_rag_config_publish_invalidate.py`, `api/tests/unit/test_api_keys_verify_endpoint.py` |

## Deliverables

### `api/app/auth/api_key.py` — `require_api_key` branch hub_name

Phase 6 Plan 06-03 SETTINGS-03 (D-V3-Phase6-A LOCKED) — Refactor M2 baseline `require_api_key` dependency thêm `request: Request` param + branch verify path:

**Central (`settings.hub_name == "central"`):** Carry forward M2 local `ApiKeyService(db).verify_key(x_api_key)` — AES-GCM decrypt + key_prefix match (M2 AUX-02 unchanged).

**Hub con (yte/duoc/hcns/dynamic):** Proxy qua `request.app.state.api_key_verify_client.verify(x_api_key)`. Client class `ApiKeyVerifyClient` ship Plan 06-02 (POST `/api/api-keys/verify` central + Redis cache TTL 60s); lifespan init Plan 06-04 lưu vào `app.state.api_key_verify_client`. 503 `APIKEY_VERIFY_CLIENT_UNAVAILABLE` envelope nếu client chưa init (boot fail-loud `R-V3-6 LOW` mitigation — KHÔNG silent fallback local DB).

M2 regression preserved: 401 `API_KEY_MISSING` khi missing header (pre-branch), 401 `API_KEY_INVALID` khi key sai/revoked (post-branch cả 2 path).

### `api/app/auth/dependencies.py` — `require_internal_auth` dependency mới

Phase 6 Plan 06-03 SETTINGS-03 (D-V3-Phase6-D LOCKED) — Async dependency function check header `X-Internal-Auth: <settings.settings_proxy_secret>` constant-time compare qua `hmac.compare_digest` (T-06-03-01 timing attack mitigation). 401 `INTERNAL_AUTH_FAIL` envelope khi mismatch / missing / empty.

Dùng cho endpoint internal-only `POST /api/api-keys/verify` (hub con call central proxy via Plan 06-02 `ApiKeyVerifyClient`). 32 char min secret length đã enforce qua Settings validator `_enforce_settings_proxy_secret` Plan 06-01 (128-bit entropy đủ).

### `api/app/routers/rag_config.py` — `update_rag_config` extend publish

Phase 6 Plan 06-03 SETTINGS-02 (D-V3-Phase6-C LOCKED) — Extend M2 baseline PUT handler thêm `request: Request` param + publish best-effort fail-open sau `service.update_config()` success:

```python
redis = getattr(request.app.state, "redis", None)
if redis is not None:
    try:
        payload = json.dumps({
            "config_key": "rag_config",
            "hub": "*",  # broadcast all hub con
            "timestamp": int(time.time()),
        })
        await redis.publish("settings:invalidate", payload)
        logger.info("settings_invalidate_published: ...")
    except Exception as e:  # noqa: BLE001 — best-effort fail-open
        logger.warning("settings_invalidate_publish_failed: %s", e)
```

Cross-process invalidate cho Wave 2 `settings_subscriber_loop` (Plan 06-02) consume → flush hub con local Redis cache key `settings:rag_config:<hub>` (RAG_CONFIG_KEY_PREFIX Plan 06-01) trong < 1s thực tế (E-V3-4 threshold < 30s thừa margin). Redis None / down → log warning KHÔNG block PUT (T-06-03-04 DoS mitigation — admin write KHÔNG bị block bởi Redis transient fail).

### `api/app/routers/api_keys.py` — `POST /api/api-keys/verify` endpoint MỚI

Phase 6 Plan 06-03 SETTINGS-03 (D-V3-Phase6-D LOCKED) — Endpoint mới central-only mount (FACTOR-02 carry forward — `api_keys_router` mount qua `main.py:704 if settings.hub_name == "central"` block; hub con strip → 404 envelope M2 ErrorHandlerMiddleware).

```python
@router.post("/verify", response_model=None)
async def verify_api_key(
    req: VerifyApiKeyRequest,
    _internal: None = Depends(require_internal_auth),
    service: ApiKeyService = Depends(get_api_key_service),
) -> dict[str, Any]:
    principal = await service.verify_key(req.api_key)
    if principal is None:
        return {"valid": False, "principal": None}
    return {"valid": True, "principal": principal}
```

Body `{"api_key": "mdk_..."}` (Pydantic `VerifyApiKeyRequest`), header `X-Internal-Auth: <settings_proxy_secret>` (require_internal_auth dep enforce). Return raw dict `{valid: bool, principal: dict|null}` — pattern song song /api/rag-config M2 raw dict (frontend / hub con ApiKeyVerifyClient parse trực tiếp data fields, KHÔNG dùng envelope).

Central giữ `ApiKeyService.verify_key` M2 AUX-02 AES-GCM at-rest private logic unchanged.

### `api/app/schemas/api_keys.py` — `VerifyApiKeyRequest` Pydantic schema

Phase 6 Plan 06-03 SETTINGS-03 — Pydantic v2 BaseModel cho body POST /api/api-keys/verify:

```python
class VerifyApiKeyRequest(BaseModel):
    api_key: str = Field(..., min_length=1, max_length=256)
```

`min_length=1` reject empty string, `max_length=256` bounded length (T-06-03-06 user input cap defense-in-depth).

## Tests

**Plan 06-03 tests added:** 22 unit test (6 + 6 + 4 + 6 — exact match Plan target).

| Test file | Count | Coverage |
|-----------|-------|----------|
| `test_require_api_key_hub_branch.py` | 6 | central local ApiKeyService.verify_key / hub con app.state.api_key_verify_client.verify / 503 missing client / 401 invalid / 401 missing header (M2 regression) / 401 invalid central |
| `test_require_internal_auth.py` | 6 | correct secret no raise / wrong 401 / missing header 401 / empty header 401 / hmac.compare_digest invoked (spy via monkeypatch) / settings_proxy_secret dynamic read (KHÔNG hardcoded) |
| `test_rag_config_publish_invalidate.py` | 4 | publish success channel + payload assertion / redis None fail-open / publish ConnectionError fail-open (KHÔNG block 200) / service error skip publish (early return 400) |
| `test_api_keys_verify_endpoint.py` | 6 | valid key 200 {valid:true} / wrong X-Internal-Auth 401 / missing header 401 / invalid key {valid:false, principal:null} / missing body field 422 Pydantic / VerifyApiKeyRequest schema min_length=1 ValidationError |

**Regression:**
- 452/452 unit Phase 1..6 PASS (430 baseline Plan 06-02 + 22 Wave 3 mới).
- 50/50 cluster regression PASS (`-k "auth or rag_config or api_keys or sso"` per PLAN verification).
- 19/19 integration test PASS (15 `test_factor_hub_scoped.py` Phase 2+3+4+5 + 4 `test_rate_limit.py` Phase 5 require_api_key consumer).

**Lint:** `ruff check` exit 0 (5 source + 4 test file).
**Type check:** `mypy --strict` exit 0 (5 source file).

## Acceptance criteria (per PLAN <success_criteria>)

| Criterion | Status |
|-----------|--------|
| `require_api_key` branch verify path central / hub con với 503 fail-loud nếu client missing | ✅ |
| `require_internal_auth` dependency mới với constant-time hmac.compare_digest secret check | ✅ |
| `update_rag_config` PUT extend publish `settings:invalidate` best-effort fail-open sau success | ✅ |
| `POST /api/api-keys/verify` endpoint mới central-only mount (FACTOR-02) với require_internal_auth + VerifyApiKeyRequest schema | ✅ |
| ≥ 22 unit test PASS (6 + 6 + 4 + 6) | ✅ exact match 22/22 |
| Regression M2 auth + Phase 3 SSO + Phase 4 sync + Phase 5 PROXY auth test KHÔNG break | ✅ (50/50 cluster + 19/19 integration + 452/452 full unit) |
| ruff + mypy --strict clean trên 5 file source modified | ✅ |
| grep acceptance — `settings.hub_name` ≥ 1, `api_key_verify_client` ≥ 1, `APIKEY_VERIFY_CLIENT_UNAVAILABLE` ≥ 1, `request: Request` ≥ 1 (api_key.py) | ✅ all PASS |
| grep acceptance — `async def require_internal_auth`, `hmac.compare_digest`, `INTERNAL_AUTH_FAIL`, `settings_proxy_secret` (dependencies.py) | ✅ all PASS |
| grep acceptance — `settings:invalidate`, `config_key.*rag_config`, `request: Request`, `noqa: BLE001` (rag_config.py) | ✅ all PASS |
| grep acceptance — `async def verify_api_key`, `/verify`, `require_internal_auth`, `VerifyApiKeyRequest` (api_keys.py) | ✅ all PASS |
| grep acceptance — `class VerifyApiKeyRequest` (schemas/api_keys.py) | ✅ |

## Deviations from Plan

**None.** Plan executed exactly as written — KHÔNG có Rule 1 (auto-fix bug) / Rule 2 (auto-add missing functionality) / Rule 3 (auto-fix blocking issue) / Rule 4 (architectural change).

2 task atomic commit per task (RED test + GREEN feat); TDD cycle clean. Lint ruff auto-fix 2 unused import (`MagicMock` test_require_internal_auth.py + `pytest` test_rag_config_publish_invalidate.py) sau khi viết test — pure cleanup KHÔNG ảnh hưởng test semantic.

## Threat Model Coverage

| Threat ID | Category | Mitigation | Status |
|-----------|----------|------------|--------|
| T-06-03-01 | Tampering | `hmac.compare_digest` constant-time compare cho `X-Internal-Auth` secret (entropy 128-bit qua Settings validator 32 char min Plan 06-01) | ✅ mitigate |
| T-06-03-02 | Elevation of Privilege | Hub con boot fail-loud lifespan Plan 06-04 — `app.state.api_key_verify_client = None` → 503 `APIKEY_VERIFY_CLIENT_UNAVAILABLE` (KHÔNG silent fallback local DB) | ✅ mitigate |
| T-06-03-03 | Information Disclosure | api_key plaintext qua POST body — accept M2 baseline + intra-network medinet_net Docker isolation (mTLS defer v4.0 HARD-V4-05) | ⚠️ accept defer |
| T-06-03-04 | DoS | publish_invalidate Redis hang block admin PUT — try/except wrap + log warning best-effort fail-open (KHÔNG raise) | ✅ mitigate |
| T-06-03-05 | Spoofing | api_keys/verify endpoint expose public internet — FACTOR-02 carry forward central-only mount + require_internal_auth dep enforce | ✅ mitigate |
| T-06-03-06 | Tampering | rag_config publish payload manipulation — JSON encode server-side (KHÔNG user input pass-through); Wave 2 subscriber Pydantic Literal enum reject | ✅ mitigate |
| T-06-03-07 | Repudiation | api_keys verify audit log granular — accept Phase 6 (high-frequency log volume defer Phase 7); Prometheus `APIKEY_VERIFY_TOTAL` counter Plan 06-01 đủ debug | ⚠️ accept defer |

5 mitigate + 2 accept (defer documented). Coverage 7/7 STRIDE registry per PLAN `<threat_model>` table.

## Known Stubs

**None.** Wave 3 ship full integration logic — KHÔNG có placeholder data wired UI / TODO mocks. `require_api_key` hub con branch consume `app.state.api_key_verify_client` (Plan 06-02 client ready); endpoint `/api/api-keys/verify` consume `ApiKeyService.verify_key` (M2 baseline ready). Wave 4 Plan 06-04 sẽ lưu client vào `app.state` qua lifespan integration.

## Next: Wave 4 Plan 06-04

Wave 3 REQUEST-RESPONSE INTEGRATION DONE. Plan 06-04 (Wave 4) lifespan integration BLOCKING depend Wave 1+2+3:

- Init `app.state.rag_config_client = RagConfigClient(...)` + `app.state.hub_registry_client = HubRegistryClient(...)` + `app.state.api_key_verify_client = ApiKeyVerifyClient(...)` ở lifespan hub con block `if settings.hub_name != "central"`.
- `await rag_client.fetch_initial()` + `await hub_client.fetch_initial()` blocking 5s — boot fail-loud `R-V3-6` mitigation (`apikey_client` KHÔNG fetch_initial — lazy on demand verify).
- Spawn `settings_subscriber_task = asyncio.create_task(settings_subscriber_loop(...))` consume `settings:invalidate` channel (Wave 3 publish source).
- Shutdown graceful — `task.cancel() + asyncio.wait_for(timeout=10s)` pattern carry forward Plan 03-02 + 04-04.
- Escape hatch `SETTINGS_SKIP_FETCH=1` test mode bypass blocking fetch (pattern song song `JWKS_SKIP_FETCH` + `COCOINDEX_SKIP_SETUP` + `SYNC_SKIP_CENTRAL_POOL`).
- Hub con boot integration test ASGI `LifespanManager` — verify `app.state.<X>_client` populated + subscriber task running.

Wave 4 ship: `api/app/main.py` extend lifespan + integration test `test_settings_sync_lifespan_integration.py` — depend Wave 1+2+3 public API + Plan 06-03 endpoint server side ready (Wave 3 ApiKeyVerifyClient consume).

## Performance Metrics

| Metric | Value |
|--------|-------|
| Duration | ~22 phút (2 task TDD RED→GREEN cycle, 0 deviation) |
| Tasks completed | 2/2 |
| Files created | 4 (4 test file) |
| Files modified | 5 (2 auth + 2 router + 1 schema) |
| Tests added | 22 (6 + 6 + 4 + 6 — match Plan exact target) |
| Test pass rate | 22/22 (100%) |
| Phase 1..5 + Wave 1+2 regression | 452/452 unit PASS — KHÔNG break (430 baseline + 22 new) |
| Cluster regression (auth/rag_config/api_keys/sso) | 50/50 PASS |
| Integration regression (factor_hub_scoped + rate_limit) | 19/19 PASS |
| Lint | ruff PASS (5 source + 4 test file) |
| Type check | mypy --strict PASS (5 source file) |
| Commits | 4 atomic (2 RED test + 2 GREEN feat) |
| Deviations | 0 (plan executed exactly as written) |

## Self-Check: PASSED

Verification command output:

```
$ ls api/app/auth/api_key.py api/app/auth/dependencies.py api/app/routers/rag_config.py api/app/routers/api_keys.py api/app/schemas/api_keys.py
5 source file — FOUND

$ ls api/tests/unit/test_require_api_key_hub_branch.py api/tests/unit/test_require_internal_auth.py api/tests/unit/test_rag_config_publish_invalidate.py api/tests/unit/test_api_keys_verify_endpoint.py
4 test file — FOUND

$ git log --oneline -4
803a0a3 feat(06-03): rag_config publish + POST /api/api-keys/verify endpoint — FOUND
5e807ac test(06-03): them 10 failing test rag_config publish + api_keys/verify endpoint — FOUND
c26e02d feat(06-03): require_api_key branch hub_name + require_internal_auth dep — FOUND
a5d9ffb test(06-03): them 12 failing test require_api_key branch + require_internal_auth — FOUND

$ grep -c "settings.hub_name\|api_key_verify_client\|APIKEY_VERIFY_CLIENT_UNAVAILABLE\|request: Request" api/app/auth/api_key.py
6 — FOUND ≥ 4 acceptance markers

$ grep -c "async def require_internal_auth\|hmac.compare_digest\|INTERNAL_AUTH_FAIL\|settings_proxy_secret" api/app/auth/dependencies.py
8 — FOUND ≥ 4 acceptance markers

$ grep -c "settings:invalidate\|config_key.*rag_config\|request: Request\|noqa: BLE001" api/app/routers/rag_config.py
8 — FOUND ≥ 4 acceptance markers

$ grep -c "async def verify_api_key\|/verify\|require_internal_auth\|VerifyApiKeyRequest" api/app/routers/api_keys.py
10 — FOUND ≥ 4 acceptance markers

$ grep -c "class VerifyApiKeyRequest" api/app/schemas/api_keys.py
1 — FOUND

$ uv run pytest tests/unit/test_require_api_key_hub_branch.py tests/unit/test_require_internal_auth.py tests/unit/test_rag_config_publish_invalidate.py tests/unit/test_api_keys_verify_endpoint.py --no-header
22 passed in 4.46s — FOUND

$ uv run pytest tests/unit/ -k "auth or rag_config or api_keys or sso" --no-header -q
50 passed — FOUND

$ uv run pytest tests/unit/ --no-header -q
452 passed — FOUND

$ uv run ruff check app/auth/api_key.py app/auth/dependencies.py app/routers/rag_config.py app/routers/api_keys.py app/schemas/api_keys.py
All checks passed!

$ uv run mypy --strict app/auth/api_key.py app/auth/dependencies.py app/routers/rag_config.py app/routers/api_keys.py app/schemas/api_keys.py
Success: no issues found in 5 source files
```

All claims verified. SUMMARY.md ready cho Wave 4 dependency consume.
