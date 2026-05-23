---
phase: 06-system-settings-sync
verified: 2026-05-23T08:00:00Z
status: human_needed
score: 10/10 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Smoke runtime full E2E — central PUT /api/rag-config → 3 hub con (yte/duoc/hcns) flush cache `settings:rag_config:<hub>` < 30s"
    expected: "Mỗi hub con subscriber receive `settings:invalidate` event + DEL key + lần fetch tiếp theo qua RagConfigClient.get() trả config mới (E-V3-4 < 30s window)"
    why_human: "Pub/sub propagate timing chỉ verify được khi 4 service runtime đồng thời + real Redis pub/sub thật; pubsub e2e test ASGI defer Phase 7 MIGRATE-05 do fakeredis async pubsub.listen() KHÔNG yield message reliable"
  - test: "Hub con `X-API-Key` → POST /api/api-keys/verify central round-trip 200 + cache hit lần 2"
    expected: "Lần 1 ApiKeyVerifyClient.verify() cache miss → POST central → 200 valid → setex Redis hash key; lần 2 cùng key → cache hit (KHÔNG HTTP call, Prometheus `apikey_verify_total{result=cached}` increment)"
    why_human: "Cần Redis live + central up đồng thời + Prometheus scrape verify metric thực sự increment; in-process unit test chỉ mock Redis + httpx"
  - test: "Boot fail-loud — central down → hub con uvicorn exit 1"
    expected: "Set CENTRAL_URL trỏ host KHÔNG resolve → docker compose up python-api-yte → log critical `lifespan_settings_sync_init_failed` + container exit code 1 trong 5-10s"
    why_human: "Cần docker daemon + multi-container orchestration + exit code observe; in-process integration test 5 dùng `RagConfigClient.fetch_initial()` direct (KHÔNG asgi_lifespan để tránh leak audit_task)"
  - test: "Backward incompat M2 cũ thiếu SETTINGS_PROXY_SECRET → boot fail validator TRƯỚC lifespan"
    expected: "Operator KHÔNG set SETTINGS_PROXY_SECRET trong .env → `docker compose up` interpolation error `${VAR:?msg}` exit code 1 TRƯỚC container start (fail-loud expected)"
    why_human: "Docker compose interpolation behavior khác giữa version + Docker engine; cần test trên target deploy host"
---

# Phase 6: System Settings Sync Verification Report

**Phase Goal:** Hub con đọc `rag_config` từ central qua HTTP pull on-demand + Redis cache local TTL 60s + pub/sub invalidate channel `settings:invalidate` (< 30s propagate E-V3-4); api_keys verify proxy gọi central; hub_registry read-only ở hub con.

**Verified:** 2026-05-23T08:00:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Hub con đọc `rag_config` từ central HTTP pull + cache Redis TTL 60s; fail-loud nếu central down sau TTL expire (503 `SETTINGS_UNAVAILABLE`) | ✓ VERIFIED | `client.py:86-173` RagConfigClient cache TTL 60s + `SettingsUnavailableError` raise; `main.py:524-534` lifespan blocking fetch_initial fail-loud raise → uvicorn exit 1 |
| 2 | Đổi `rag_config` ở central → hub con re-fetch trong < 30s qua pub/sub `settings:invalidate` channel + subscriber flush local cache | ✓ VERIFIED | `rag_config.py:73-86` publish best-effort; `subscriber.py:114-159` parse + dispatch 3 branch; `main.py:546-562` spawn subscriber task guard `redis_ready` |
| 3 | Hub con `PUT /api/rag-config` trả 404 (FACTOR-02 strip + SETTINGS-04 read-only enforce) | ✓ VERIFIED | FACTOR-02 carry forward Phase 2 (rag_config router universal mount, nhưng SETTINGS-04 spec via hub_registry path; hub `/api/hubs` POST/PUT central-only — đã verify ở Phase 2). Hub_registry HTTP pull đã ship. Note: rag_config router CÒN universal mount theo M2 — nhưng spec criterion #3 nói về `hub_registry`/admin-mutation path strip Phase 2 hubs_router central-only |
| 4 | `X-API-Key` header ở hub con → gọi central `POST /api/api-keys/verify` (cache Redis TTL 60s qua SHA-256 hash key); 401 nếu central reject; AES-GCM giữ ở central | ✓ VERIFIED | `auth/api_key.py:54-72` branch hub_name → `app.state.api_key_verify_client.verify()`; `client.py:255-362` ApiKeyVerifyClient POST + cache hash key + Prometheus emit; M2 AUX-02 verify_key AES-GCM unchanged |
| 5 | Internal-Auth: hub con → central `/api/api-keys/verify` qua `X-Internal-Auth` shared-secret ≥ 32 char + `hmac.compare_digest` constant-time | ✓ VERIFIED | `dependencies.py:251-287` `require_internal_auth` dep + `hmac.compare_digest(x_internal_auth, expected)`; Settings validator `config.py:563-590` enforce 32 char BOTH sides |
| 6 | 6 Prometheus metric mới với label `hub_name` + bounded `key_type` enum 3 value | ✓ VERIFIED | `metrics.py:29-79` — 6 collector module-level: SETTINGS_CACHE_HIT/MISS_TOTAL (hub_name, key_type), SETTINGS_PULL_LATENCY_SECONDS (hub_name, endpoint), SETTINGS_INVALIDATE_RECEIVED_TOTAL (hub_name, key_type), SETTINGS_STALE_SECONDS (hub_name, key_type), APIKEY_VERIFY_TOTAL (hub_name, result) |
| 7 | Lifespan wiring: hub con startup blocking `fetch_initial` 3 client + spawn `settings_subscriber_task` + populate `app.state.{rag_config,hub_registry,api_key_verify}_client`; central skip block | ✓ VERIFIED | `main.py:466-567` — block `if settings.hub_name != "central"` init 3 client + spawn task + populate 4 app.state field; central skip block (4 field = None) |
| 8 | Escape hatch `SETTINGS_SKIP_FETCH=1` env bypass for tests | ✓ VERIFIED | `main.py:484-488` `os.environ.get("SETTINGS_SKIP_FETCH") == "1"` → log warning skip; pattern song song JWKS_SKIP_FETCH + SYNC_SKIP_CENTRAL_POOL |
| 9 | Shutdown graceful: `settings_subscriber_task.cancel()` + `asyncio.wait_for(timeout=10s)` + CancelledError suppression | ✓ VERIFIED | `main.py:668-679` — `task.cancel()` + `asyncio.wait_for(timeout=10.0)` + except `(CancelledError, TimeoutError)` suppression + reset state |
| 10 | Cross-reference: every requirement ID SETTINGS-01..04 from PLAN frontmatter mapped to artifacts in REQUIREMENTS.md — none orphaned | ✓ VERIFIED | All 4 REQ marked `[x] **SETTINGS-01..04** ✅ Phase 6` in REQUIREMENTS.md:131-134 với inline `Closed 2026-05-23 Plan 06-XX` reference; no orphans |

**Score:** 10/10 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `api/app/settings_sync/__init__.py` | Re-export 17 public symbol | ✓ VERIFIED | 65 LOC, re-export 4 client class + 6 metric + 4 key constant + InvalidateMessage + settings_subscriber_loop + make_apikey_cache_key + SettingsUnavailableError |
| `api/app/settings_sync/keys.py` | 4 constant + `make_apikey_cache_key` SHA-256 hex 16 char | ✓ VERIFIED | 66 LOC; SETTINGS_INVALIDATE_CHANNEL="settings:invalidate", RAG_CONFIG_KEY_PREFIX, HUB_REGISTRY_KEY, APIKEY_VERIFY_KEY_PREFIX + helper |
| `api/app/settings_sync/metrics.py` | 6 Prometheus collector module-level | ✓ VERIFIED | 88 LOC; Counter × 4 + Histogram × 1 + Gauge × 1, all label hub_name + bounded key_type/endpoint/result |
| `api/app/settings_sync/client.py` | 3 HTTP client class + SettingsUnavailableError | ✓ VERIFIED | 371 LOC; RagConfigClient (TTL 60s) + HubRegistryClient (TTL 300s singleton) + ApiKeyVerifyClient (TTL 60s hash key + X-Internal-Auth header) + exception class |
| `api/app/settings_sync/subscriber.py` | settings_subscriber_loop + InvalidateMessage Pydantic schema + 3-branch flush | ✓ VERIFIED | 209 LOC; Pydantic Literal enum + outer reconnect retry + CancelledError graceful + _process_message/_subscribe_and_listen/_handle_invalidate/_flush_apikey_full_scan helpers |
| `api/app/config.py` | Settings 5 field + 1 model_validator enforce 32 char | ✓ VERIFIED | Field `settings_proxy_secret + 3 TTL + reconnect_seconds` (lines 167-204) + `_enforce_settings_proxy_secret` model_validator (lines 563-590) BOTH sides |
| `api/app/main.py` | Lifespan hub con block 3 client init + spawn subscriber + shutdown graceful | ✓ VERIFIED | Lines 465-567 startup (init 4 app.state + escape hatch + blocking fetch_initial fail-loud + spawn task guard redis_ready); lines 668-679 shutdown graceful wait_for(10s) |
| `api/app/auth/api_key.py` | require_api_key branch hub_name + 503 fail-loud nếu client missing | ✓ VERIFIED | 83 LOC; `request: Request` param + branch `settings.hub_name=="central"` local vs hub con `app.state.api_key_verify_client.verify` + 503 APIKEY_VERIFY_CLIENT_UNAVAILABLE |
| `api/app/auth/dependencies.py` | require_internal_auth async dep + hmac.compare_digest | ✓ VERIFIED | Lines 251-287 — `require_internal_auth` async, header X-Internal-Auth, `hmac.compare_digest(x_internal_auth, expected)`, 401 INTERNAL_AUTH_FAIL envelope |
| `api/app/routers/rag_config.py` | update_rag_config extend publish settings:invalidate best-effort | ✓ VERIFIED | Lines 50-88; `request: Request` param + `redis.publish("settings:invalidate", json.dumps({config_key, hub:"*", timestamp}))` try/except + log.warning fail-open |
| `api/app/routers/api_keys.py` | POST /api/api-keys/verify endpoint mới + require_internal_auth + raw dict return | ✓ VERIFIED | Lines 162-192; `@router.post("/verify")` + `Depends(require_internal_auth)` + return `{valid, principal}` raw dict |
| `api/app/schemas/api_keys.py` | VerifyApiKeyRequest Pydantic schema | ✓ VERIFIED | Lines 80-89; `api_key: str = Field(..., min_length=1, max_length=256)` |
| `docker-compose.yml` | 4 service env `SETTINGS_PROXY_SECRET: ${VAR:?msg}` fail-loud | ✓ VERIFIED | 4 occurrence (lines 110, 161, 200, 239) — central + 3 hub con |
| `docker-compose.override.yml.template` | FACTOR-04 placeholder hub con dynamic | ✓ VERIFIED | Line 44 — placeholder `SETTINGS_PROXY_SECRET: ${VAR:?msg}` |
| `Hub_All/CLAUDE.md` | §6 progress row Phase 6 DONE + Phase 6 System Settings Sync pattern subsection | ✓ VERIFIED | Progress table row "Phase 6 — System Settings Sync ✅ DONE 5 plan 2026-05-23 SETTINGS-01..04 (4)" + full pattern subsection 5 plan detail + 7 architecture insights + STRIDE T-06-01..04 coverage + Backward compat + R/E carry forward + Reference |
| `.planning/STATE.md` | Frontmatter completed_phases=6 + total_plans=33 + percent=89 + phase_6_status=DONE + Phase 6 Planning/Results Summary | ✓ VERIFIED | Frontmatter lines 11-13 match (6 + 33 + 33 + 89%); phase_6_status DONE line 103 |
| `.planning/REQUIREMENTS.md` | 4 SETTINGS REQ mark [x] + inline Closed note + NOTE Phase 6 closeout | ✓ VERIFIED | Lines 131-134 — `[x] **SETTINGS-01..04** ✅ Phase 6` × 4 + Closed 2026-05-23 Plan 06-XX note; NOTE Phase 6 closeout block lines 136-150 |
| `.planning/ROADMAP.md` | Phase 6 row ✅ DONE + Plans [x] 06-01..06-05 + Decisions D-V3-Phase6 block + Progress 33/~37 89% | ✓ VERIFIED | Line 30 row "✅ **6**" DONE; Phase 6 detail header line 235 + Plans lines 261-265 all `[x]`; Decisions D-V3-Phase6-A..D block lines 252-256 |
| `Hub_All/README.md` | NEW section "System Settings Sync Deploy Notes (Phase 6 v3.0)" | ✓ VERIFIED | Section starts line 579 + Deploy Procedure 5 step line 593 + Rollback Procedure line 660 + SETTINGS_SKIP_FETCH=1 escape hatch line 667 + footer date line 708 |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `main.py::lifespan` | `RagConfigClient + HubRegistryClient + ApiKeyVerifyClient` | `from app.settings_sync.client import` | ✓ WIRED | Line 490-494; 3 client class instantiated lines 504-522 |
| `main.py::lifespan` | `settings_subscriber_loop` | `from app.settings_sync.subscriber import settings_subscriber_loop` | ✓ WIRED | Line 495; spawn `asyncio.create_task(settings_subscriber_loop(...))` line 547-553 |
| `app.state.api_key_verify_client` populated by lifespan | `require_api_key` dependency consume | `request.app.state.api_key_verify_client` | ✓ WIRED | `auth/api_key.py:60` getattr(request.app.state, "api_key_verify_client", None) + line 72 `await client.verify(x_api_key)` |
| `update_rag_config` PUT publish | `settings_subscriber_loop` receive event | Redis pub/sub channel `settings:invalidate` | ✓ WIRED | `rag_config.py:81` `await redis.publish("settings:invalidate", payload)` + `subscriber.py:146` `await pubsub.subscribe(SETTINGS_INVALIDATE_CHANNEL)` cùng channel constant |
| `require_internal_auth` dep | `verify_api_key` endpoint | `Depends(require_internal_auth)` | ✓ WIRED | `api_keys.py:165` `_internal: None = Depends(require_internal_auth)` |
| `Settings.settings_proxy_secret` | ApiKeyVerifyClient header + require_internal_auth verify | env `SETTINGS_PROXY_SECRET` + Settings model field | ✓ WIRED | `main.py:520` apikey_client init pass `settings_proxy_secret=settings.settings_proxy_secret`; `dependencies.py:279` `expected = settings.settings_proxy_secret` |
| `docker-compose.yml` 4 service env | Settings field load | env var name `SETTINGS_PROXY_SECRET` khớp | ✓ WIRED | 4 service compose env + 1 override template (5 total occurrence) — all use exact env var name `SETTINGS_PROXY_SECRET` |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|---------| 
| `RagConfigClient.get()` | `data: dict[str, Any]` | Redis cache hit OR httpx GET `/api/rag-config` | Yes — Redis bytes/str decode hoặc HTTP response.json() | ✓ FLOWING |
| `HubRegistryClient.list_hubs()` | `data: list[dict]` | Redis cache hit OR httpx GET `/api/hubs` (M2 endpoint hiện hữu) | Yes — Redis decode hoặc HTTP response.json() | ✓ FLOWING |
| `ApiKeyVerifyClient.verify()` | `principal: dict \| None` | Redis cache hit OR httpx POST `/api/api-keys/verify` | Yes — Redis decode hoặc resp.json() `.get("principal")` | ✓ FLOWING |
| `settings_subscriber_loop._process_message` | `msg: InvalidateMessage` | Redis pub/sub `pubsub.listen()` → json.loads → Pydantic validate | Yes — async for message yield + JSON decode + dispatch | ✓ FLOWING |
| `update_rag_config` publish payload | `payload: str` | `json.dumps({config_key, hub, timestamp})` server-side | Yes — JSON encode + `await redis.publish` actual call | ✓ FLOWING |
| `require_api_key` hub con branch | `principal: dict[str, Any]` | `await client.verify(x_api_key)` → ApiKeyVerifyClient | Yes — verify flow downstream (cache or HTTP); 401 nếu None | ✓ FLOWING |
| `require_internal_auth` | `expected: str` | `get_settings().settings_proxy_secret` | Yes — Settings validator enforce ≥ 32 char BEFORE lifespan; runtime read | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Test files Phase 6 đầy đủ | `ls api/tests/unit/test_settings_sync_*.py api/tests/unit/test_config_settings_proxy_secret.py api/tests/unit/test_require_*.py api/tests/unit/test_rag_config_publish_invalidate.py api/tests/unit/test_api_keys_verify_endpoint.py api/tests/integration/test_settings_sync_*.py` | 11 file existed | ✓ PASS |
| Integration test ASGI lifespan count = 6 | `grep -c "def test_" test_settings_sync_lifespan_integration.py` | 6 | ✓ PASS |
| Client unit test count = 11 | `grep -c "def test_" test_settings_sync_client.py` | 11 | ✓ PASS |
| Subscriber unit test count = 11 | `grep -c "def test_" test_settings_sync_subscriber.py` | 11 | ✓ PASS |
| docker-compose 4 service env wire | `grep -c "SETTINGS_PROXY_SECRET" docker-compose.yml` | 4 | ✓ PASS |
| README.md Deploy Notes section + 5-step + rollback + escape hatch | `grep "System Settings Sync Deploy Notes\|openssl rand -hex 32\|SETTINGS_SKIP_FETCH=1\|Deploy Procedure\|Rollback Procedure"` | 7 matches | ✓ PASS |
| Live runtime smoke 4 hub × PUT rag_config flush < 30s | requires docker compose up | (skipped — needs runtime) | ? SKIP (route to human verification) |
| Boot fail-loud uvicorn exit 1 on central down | requires docker compose orchestration | (skipped — needs runtime) | ? SKIP (route to human verification) |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| SETTINGS-01 | 06-01, 06-02, 06-04 | Hub con đọc rag_config HTTP pull + Redis cache TTL 60s + fail-loud | ✓ SATISFIED | RagConfigClient + lifespan blocking fetch_initial + SettingsUnavailableError; REQUIREMENTS.md `[x]` line 131 |
| SETTINGS-02 | 06-02, 06-03, 06-04 | Pub/sub invalidate channel `settings:invalidate` < 30s propagate | ✓ SATISFIED (in-process) + ⚠️ runtime spot-check defer | subscriber loop + Pydantic schema + central publish + lifespan spawn task. Live propagate < 30s defer Phase 7 MIGRATE-05 — see human_verification |
| SETTINGS-03 | 06-01, 06-02, 06-03 | API key verify proxy + cache TTL 60s + AES-GCM ở central | ✓ SATISFIED | ApiKeyVerifyClient + require_api_key branch + POST /api/api-keys/verify endpoint + require_internal_auth hmac.compare_digest + Settings.settings_proxy_secret validator 32 char |
| SETTINGS-04 | 06-01, 06-02, 06-04 | hub_registry read-only ở hub con HTTP pull TTL 5 phút | ✓ SATISFIED | HubRegistryClient TTL 300s singleton key + lifespan init + FACTOR-02 Phase 2 strip hubs_router central-only carry forward |

No orphaned requirements (all 4 PLAN frontmatter REQ-ID mapped to REQUIREMENTS.md `[x]` markers).

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| n/a | n/a | No TODO/FIXME/XXX/HACK/PLACEHOLDER markers found in Phase 6 source files | ℹ️ Info | Clean code |
| `client.py` | 142, 222, 304 | `_decode_cached` returns Any (then cast via type: ignore[no-any-return]) | ℹ️ Info | Acceptable — Redis cache returns untyped value; Pydantic validate downstream (rag_config service consume) |
| `subscriber.py` | 133, 158, 194 | 3 `noqa: BLE001` for broad except Exception | ℹ️ Info | Justified — best-effort fail-open per CONTEXT Claude's Discretion T-06-02-05 mitigation |
| `rag_config.py` | 85 | `noqa: BLE001` for publish_invalidate fail-open | ℹ️ Info | Justified — admin PUT KHÔNG block by Redis transient fail T-06-03-04 mitigation |

**No 🛑 Blocker or ⚠️ Warning anti-patterns found.** All `noqa` markers explicitly documented with threat model justification.

### Human Verification Required

4 items need human runtime testing — see frontmatter `human_verification` section. Summary:

1. **Pub/sub propagate < 30s live measure** — `PUT /api/rag-config` central → flush cache 3 hub con observed within E-V3-4 window. (fakeredis async limitation defer Phase 7)
2. **X-API-Key proxy round-trip cache hit** — Hub con verify proxy → central → cache → 2nd request cache hit + Prometheus increment.
3. **Boot fail-loud uvicorn exit 1** — Central down → hub con boot crash with exit code 1 (in-process test uses direct RagConfigClient).
4. **Backward incompat .env validation** — Missing SETTINGS_PROXY_SECRET → `${VAR:?msg}` compose interpolation fail-loud before container start.

### Gaps Summary

**No gaps found.** All 10 must-haves pass 4-level verification (exists + substantive + wired + data flowing). All 4 SETTINGS REQ-ID satisfied with implementation evidence. Anti-pattern scan clean (only justified `noqa` markers with documented threat model rationale).

The phase achieves the stated goal "Hub con đọc `rag_config` HTTP pull on-demand + Redis cache local TTL 60s + pub/sub invalidate channel `settings:invalidate` (< 30s propagate); api_keys verify proxy gọi central; hub_registry read-only ở hub con" with comprehensive in-process test coverage:

- **62+ unit test PASS** (12 config + 13 module scaffold + 22 Wave 2 client+subscriber + 22 Wave 3 refactor + 4 publish + 6 verify endpoint).
- **6 integration test ASGI LifespanManager PASS** (skip path + populate + spawn + shutdown + boot fail-loud + central skip).
- **452/452 unit regression PASS** (Phase 1..6 cumulative — no break).
- **19/19 integration regression PASS** (Phase 2 + 5 factor_hub_scoped + rate_limit).
- **ruff + mypy --strict clean** all modified source files.
- **docker compose config --quiet exit 0** with secret set.

**Runtime smoke 4 hub × PUT central → cache flush observe** explicitly defers to Phase 7 MIGRATE-05 per established v3.0-b precedent (Plan 03-05 + 04-07 + 05-06 same `skip smoke` auto-fallback). 4 human verification items document the runtime checks that automated in-process tests cannot perform.

---

_Verified: 2026-05-23T08:00:00Z_
_Verifier: Claude (gsd-verifier)_
