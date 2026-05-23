---
phase: 06
plan: 02
subsystem: settings-sync
tags: [settings-sync, httpx-client, redis-pubsub, asyncio-task, pydantic-schema, wave-2]
status: done
date_completed: 2026-05-23
duration_minutes: 18

requires:
  - Wave 1 scaffold Plan 06-01 (keys.py constants + metrics.py 6 collector + __init__.py)
  - Settings 5 field Plan 06-01 (settings_proxy_secret + 3 TTL + subscriber_reconnect)
  - httpx 0.28.1 async pattern Phase 3 Plan 03-02 (JWKSCache fetch_initial blocking + Timeout)
  - search_cache.py M2 pub/sub subscriber loop pattern (subscribe + listen + finally aclose)
  - Pydantic v2 BaseModel + Literal enum + Field min_length/max_length (T-06-02-03 mitigation)

provides:
  - "api/app/settings_sync/client.py — 3 HTTP client class + SettingsUnavailableError"
  - "api/app/settings_sync/subscriber.py — settings_subscriber_loop + InvalidateMessage Pydantic schema + _handle_invalidate dispatcher"
  - "api/app/settings_sync/__init__.py — re-export 18 symbol public API Wave 1+2 (11 Wave 1 + 7 Wave 2)"
  - "api/tests/unit/test_settings_sync_client.py — 11 unit test mock httpx + Redis fixture"
  - "api/tests/unit/test_settings_sync_subscriber.py — 11 unit test mock pubsub + payload parse + reconnect timeout pattern"

affects:
  - Plan 06-03 Wave 3 — require_api_key refactor consume ApiKeyVerifyClient.verify() + app.state.api_key_verify_client storage
  - Plan 06-03 Wave 3 — rag_config router POST publish_invalidate dùng InvalidateMessage schema (cross-process)
  - Plan 06-04 Wave 4 — lifespan integration 3 client init + settings_subscriber_task spawn + shutdown graceful task.cancel()
  - 503 envelope SETTINGS_UNAVAILABLE — Wave 3 router catch SettingsUnavailableError

tech-stack:
  added: []  # KHÔNG dep mới — pure httpx (M2 baseline) + pydantic (M2 baseline)
  patterns:
    - "httpx.Timeout(default, connect=, read=) 4-param structure (httpx 0.28.1 requirement)"
    - "Pydantic Literal enum field — bounded enum mitigation T-06-02-03 Tampering"
    - "AsyncMock pubsub.listen async generator — yield messages + iterator drain → reconnect loop exit"
    - "asyncio.wait_for(timeout=...) test pattern thay CancelledError raise trong async gen (pytest-asyncio compat)"
    - "asyncio.create_task + task.cancel() production cancellation pattern (test 5 graceful shutdown)"
    - "_process_message + _subscribe_and_listen helper extract (C901 complexity refactor)"
    - "lifespan boot fail-loud via SettingsUnavailableError raise (uvicorn exit 1 — R-V3-6 LOW mitigation)"

key-files:
  created:
    - "api/app/settings_sync/client.py (370 LOC — 3 client class + SettingsUnavailableError + _decode_cached helper)"
    - "api/app/settings_sync/subscriber.py (209 LOC — InvalidateMessage + settings_subscriber_loop + 3 helper)"
    - "api/tests/unit/test_settings_sync_client.py (365 LOC — 11 test: 4 RagConfig + 3 HubRegistry + 4 ApiKeyVerify)"
    - "api/tests/unit/test_settings_sync_subscriber.py (290 LOC — 11 test: 3 Pydantic + 5 main + 3 extra)"

  modified:
    - "api/app/settings_sync/__init__.py (+19 LOC — re-export client.py 4 symbol + subscriber.py 2 symbol)"

decisions:
  - "Rule 1 fix httpx.Timeout 4-param structure — httpx 0.28.1 yêu cầu hoặc default scalar hoặc đủ connect/read/write/pool. Pass default value 5.0/10.0 + override connect/read explicitly. KHÁC Phase 3 JWKSCache pattern dùng `timeout=5.0` scalar."
  - "Pytest-asyncio + asyncio.CancelledError trong async generator → test runner treat as cancellation gây hang infinite reconnect loop. Workaround: thay vì raise CancelledError trong _listen() async gen, dùng asyncio.wait_for timeout 2s exit pattern. Test 5 (graceful shutdown) dùng task.cancel() pattern thực tế production."
  - "apikey branch full SCAN+DEL (KHÔNG dùng key_id để compute hash) — subscriber không có plaintext key, 60s TTL natural burn acceptable per CONTEXT Claude's Discretion."
  - "T-06-02-04 LOCKED — KHÔNG cache negative 401 response trong ApiKeyVerifyClient (return None + KHÔNG setex). Pattern song song M2 search_cache no negative cache."
  - "T-06-02-06 LOCKED — X-Internal-Auth header sent qua httpx kwargs.headers (constant-time check defer Plan 06-03 require_internal_auth)."
  - "C901 complexity refactor settings_subscriber_loop → _process_message + _subscribe_and_listen helper functions để pass ruff (complexity 14 → 4 mỗi function)."

metrics:
  duration_minutes: 18
  tasks_completed: 2
  files_created: 4
  files_modified: 1
  tests_added: 22  # 11 client + 11 subscriber
  tests_pass: 22
  regression_pass: 430  # 408 baseline + 22 Wave 2
  lint_pass: true
  mypy_strict_pass: true
  ruff_C901_refactor: 1  # complexity 14 → split 2 helper
---

# Phase 06 Plan 06-02: Wave 2 client.py + subscriber.py Summary

**Wave 2 BUSINESS LOGIC CORE** cho Phase 6 System Settings Sync — 3 HTTP client class (`RagConfigClient` + `HubRegistryClient` + `ApiKeyVerifyClient`) với httpx async + Redis cache TTL hybrid + Prometheus metric emit + fail-loud lifecycle, và `settings_subscriber_loop` asyncio task subscribe single channel `settings:invalidate` với Pydantic `InvalidateMessage` Literal enum validate + 3 config_key flush branch + reconnect retry + CancelledError graceful shutdown.

## Tasks completed

| Task | Name | Commits | Files |
|------|------|---------|-------|
| 1 | `client.py` 3 HTTP client class + 11 test (TDD) | 9701fda RED + 2890973 GREEN | `api/app/settings_sync/client.py`, `api/app/settings_sync/__init__.py`, `api/tests/unit/test_settings_sync_client.py` |
| 2 | `subscriber.py` asyncio loop + InvalidateMessage + 11 test (TDD) | 102b512 RED + 17ff523 GREEN | `api/app/settings_sync/subscriber.py`, `api/app/settings_sync/__init__.py`, `api/tests/unit/test_settings_sync_subscriber.py` |

## Deliverables

### Module `api/app/settings_sync/client.py` (370 LOC)

**3 HTTP client class** với shared lifecycle pattern carry forward Phase 3 JWKSCache:

- **`RagConfigClient`** (SETTINGS-01 — D-V3-Phase6-A LOCKED):
  - `fetch_initial()` blocking 5s — `SettingsUnavailableError` on fail (boot fail-loud R-V3-6 mitigation).
  - `get()` hot path — Redis cache hit > miss > HTTP fetch > setex (TTL 60s default).
  - Cache key per-hub: `settings:rag_config:<hub_name>` (RAG_CONFIG_KEY_PREFIX Wave 1).
  - Prometheus emit `SETTINGS_CACHE_HIT/MISS_TOTAL{hub_name, key_type=rag_config}` + `SETTINGS_PULL_LATENCY_SECONDS.observe()` + `SETTINGS_STALE_SECONDS.set(0)`.

- **`HubRegistryClient`** (SETTINGS-04 — D-V3-Phase6-B LOCKED TTL 300s):
  - Singleton cache key `settings:hub_registry` (HUB_REGISTRY_KEY Wave 1 — KHÔNG per-hub).
  - `list_hubs()` returns `list[dict]` (4 hub config from central GET `/api/hubs`).

- **`ApiKeyVerifyClient`** (SETTINGS-03 — D-V3-Phase6-D LOCKED X-Internal-Auth):
  - POST `/api/api-keys/verify` body `{api_key: str}` header `X-Internal-Auth: <secret>` (32 char min).
  - Cache key SHA-256 hex prefix 16 char qua `make_apikey_cache_key()` (T-06-04-02 — KHÔNG plaintext).
  - 200 + valid:true → setex positive + result=valid + return principal.
  - 401 → None + result=invalid + KHÔNG setex (T-06-02-04 no negative cache).
  - HTTP error / 5xx → None + result=invalid (fail-quiet).
  - Cache hit → result=cached + skip HTTP.

- **`SettingsUnavailableError`** exception class — RuntimeError subclass cho Wave 3 router catch → 503 envelope `SETTINGS_UNAVAILABLE`.

### Module `api/app/settings_sync/subscriber.py` (209 LOC)

**`InvalidateMessage` Pydantic schema** (D-V3-Phase6-C LOCKED — T-06-02-03 Tampering mitigation):
- `config_key: Literal["rag_config", "hub_registry", "apikey"]` — Literal enum reject invalid value.
- `hub: str` `Field(..., min_length=1, max_length=32)` — bounded length.
- `key_id: str | None = None` — optional cho apikey granular revoke.
- `timestamp: int` — unix epoch seconds.

**`settings_subscriber_loop(redis, hub_name, reconnect_seconds=5)`** asyncio task:
- Outer `while True` wrap reconnect — generic Exception → `asyncio.sleep(reconnect_seconds)` + retry (best-effort fail-open T-06-02-05 DoS mitigation).
- `CancelledError` → re-raise (graceful shutdown lifespan).
- `redis=None` → log warning + return early (KHÔNG block lifespan).

**3 config_key flush branch** (D-V3-Phase6-C LOCKED):
- `rag_config`: hub="*" broadcast HOẶC hub==hub_name match → `redis.delete(f"settings:rag_config:{hub_name}")`. Mismatch hub → skip no-op.
- `hub_registry`: any hub → `redis.delete("settings:hub_registry")` singleton.
- `apikey`: full SCAN + DEL pattern `apikey:verify:*` (subscriber không có plaintext để compute hash → 60s TTL natural burn acceptable per CONTEXT Claude's Discretion).

**Helper functions** (C901 refactor):
- `_process_message(redis, hub_name, message)` — parse + Pydantic validate + dispatch.
- `_subscribe_and_listen(redis, hub_name)` — 1 inner iteration subscribe + listen.
- `_handle_invalidate(redis, hub_name, msg)` — 3-branch dispatcher + emit `SETTINGS_INVALIDATE_RECEIVED_TOTAL`.
- `_flush_apikey_full_scan(redis)` — SCAN cursor loop + DEL batch.

### `api/app/settings_sync/__init__.py` re-export

Public API extend Wave 1 (11 symbol) → Wave 2 (18 symbol total): thêm 7 mới — `ApiKeyVerifyClient`, `HubRegistryClient`, `RagConfigClient`, `SettingsUnavailableError`, `InvalidateMessage`, `settings_subscriber_loop`.

## Tests

**Plan 06-02 tests added:** 22 unit test (11 client + 11 subscriber).

| Test file | Count | Coverage |
|-----------|-------|----------|
| `test_settings_sync_client.py` | 11 | RagConfigClient (4): fetch_initial happy + timeout + cache hit + 500 raises. HubRegistryClient (3): fetch_initial happy singleton + list_hubs cache hit + 401 raises. ApiKeyVerifyClient (4): cache miss 200 valid + 401 no cache + cache hit + X-Internal-Auth header verify. |
| `test_settings_sync_subscriber.py` | 11 | Pydantic InvalidateMessage (3): rag_config broadcast + reject INVALID + apikey key_id. Subscriber loop (5): rag_config broadcast del + mismatch skip + hub_registry singleton del + invalid JSON skip + CancelledError graceful. Extra (3): apikey SCAN+DEL + Validation skip + redis None early return. |

**Regression:** 430/430 unit Phase 1..5 + Wave 1 + Wave 2 PASS — KHÔNG break (408 baseline + 22 Wave 2 mới).

**Lint:** `ruff check` exit 0 (5 file: 2 source + 1 __init__ + 2 test).
**Type check:** `mypy --strict` exit 0 (3 source file: client + subscriber + __init__).

## Acceptance criteria (per PLAN <success_criteria>)

| Criterion | Status |
|-----------|--------|
| 3 client class (RagConfigClient + HubRegistryClient + ApiKeyVerifyClient) với httpx async + Redis cache + Prometheus emit + fail-loud lifecycle | ✅ |
| SettingsUnavailableError exception class | ✅ |
| settings_subscriber_loop async + Pydantic InvalidateMessage schema + 3 config_key flush branch + reconnect retry + CancelledError graceful | ✅ |
| 18 unit test PASS target | ✅ exceeded (22/22: 11 client + 11 subscriber) |
| `__init__.py` re-export đầy đủ public API 10+ symbol | ✅ (18 symbol total Wave 1+2) |
| Regression Phase 1..5 unit test KHÔNG break | ✅ (430/430 unit PASS) |
| ruff + mypy --strict clean | ✅ |
| grep acceptance criteria (class + async def + X-Internal-Auth + CancelledError + reconnect_seconds) | ✅ all PASS |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] httpx.Timeout(connect=, read=) 4-param structure requirement**

- **Found during:** Task 1 GREEN — 11 test fail với `ValueError: httpx.Timeout must either include a default, or set all four parameters explicitly.`
- **Issue:** httpx 0.28.1 đổi Timeout constructor — `Timeout(connect=2.0, read=5.0)` MISSING `write` + `pool` → ValueError. PLAN pseudo-code chỉ specify connect + read.
- **Fix:** Pass default scalar (5.0 cho initial, 10.0 cho refresh) → override connect/read explicitly: `httpx.Timeout(5.0, connect=2.0, read=5.0)`.
- **Files modified:** `api/app/settings_sync/client.py:51-58`.
- **Commit:** 2890973 (GREEN Task 1).

**2. [Rule 1 - Bug] Pytest-asyncio + CancelledError raise trong async generator gây hang**

- **Found during:** Task 2 GREEN — 8 subscriber tests treo vô hạn trong pytest collection/run (output buffer empty).
- **Issue:** Khi test raise `asyncio.CancelledError()` trong `_listen()` async generator, pytest-asyncio treat đó như test runner cancellation signal (KHÔNG phải test-controlled exception). Subscriber outer `while True` reconnect loop continue → infinite loop.
- **Fix:** Thay vì raise CancelledError, để async gen yield messages + drain naturally → subscriber generic Exception except catch StopAsyncIteration → reconnect sleep → `asyncio.wait_for(timeout=2.0)` exit graceful. Test 5 (graceful shutdown) dùng `asyncio.create_task + task.cancel()` pattern thực tế production cancellation.
- **Files modified:** `api/tests/unit/test_settings_sync_subscriber.py:105-280` (refactor helpers + 8 test).
- **Commit:** 17ff523 (GREEN Task 2).

**3. [Rule 1 - Lint] C901 complexity `settings_subscriber_loop` 14 > 10**

- **Found during:** Task 2 GREEN — ruff fail với C901 complexity 14 (4 trên cap 10).
- **Issue:** Single big function với 4 try/except + 1 async for + 2 inner try/except → cognitive complexity 14.
- **Fix:** Extract `_process_message(redis, hub_name, message)` + `_subscribe_and_listen(redis, hub_name)` helpers. settings_subscriber_loop chỉ giữ outer while True + 2 except branches.
- **Files modified:** `api/app/settings_sync/subscriber.py:107-180`.
- **Commit:** 17ff523 (GREEN Task 2).

### No Rule 2 / Rule 4 deviations

Wave 2 KHÔNG có Rule 2 (auto-add missing critical functionality) hay Rule 4 (architectural change). Threat model T-06-02-01..06 đã được mitigate đầy đủ trong PLAN action — KHÔNG cần thêm.

## Known Stubs

**None.** Wave 2 ship business logic core đầy đủ ready Wave 3 consume — KHÔNG có placeholder data wired UI / TODO mocks. 3 client + 1 subscriber + InvalidateMessage schema fully functional với mock Redis/httpx + Prometheus emit verified qua test.

## Next: Wave 3 Plan 06-03

Wave 2 BUSINESS LOGIC CORE DONE. Plan 06-03 (Wave 3) consume:
- `RagConfigClient`, `HubRegistryClient`, `ApiKeyVerifyClient` instance lưu `app.state.<X>_client` (Wave 4 lifespan).
- `require_api_key` refactor `branch settings.hub_name`:
  - Central: M2 `ApiKeyService(db).verify_key()` (local).
  - Hub con: `app.state.api_key_verify_client.verify()` (proxy + Redis cache).
- `require_internal_auth` dependency mới (`api/app/auth/dependencies.py`) check header `X-Internal-Auth` qua `hmac.compare_digest(settings.settings_proxy_secret, header)`.
- `POST /api/api-keys/verify` endpoint mới central (mount conditional `if settings.hub_name == "central"`) wrap `ApiKeyService.verify_key()` private logic.
- `PUT /api/rag-config` extend publish `settings:invalidate` channel với `InvalidateMessage` payload `config_key="rag_config", hub="*"` best-effort fail-open.

Wave 3 ship 4 file modify + 1 schema mới — depend Wave 1 + Wave 2 public API.

## Performance Metrics

| Metric | Value |
|--------|-------|
| Duration | ~18 phút |
| Tasks completed | 2/2 |
| Files created | 4 (2 source + 2 test) |
| Files modified | 1 (__init__.py re-export) |
| Tests added | 22 (11 client + 11 subscriber) |
| Test pass rate | 22/22 (100%) |
| Phase 1..5 + Wave 1 regression | 430/430 PASS — KHÔNG break |
| Lint | ruff PASS (5 file) |
| Type check | mypy --strict PASS (3 source file) |
| Commits | 4 atomic (2 RED test + 2 GREEN feat) |
| Deviations | 3 (Rule 1 inline auto-fix; KHÔNG architectural / scope creep) |

## Self-Check: PASSED

Verification command output:

```
$ ls api/app/settings_sync/{client,subscriber,__init__}.py
api/app/settings_sync/client.py — FOUND (370 LOC)
api/app/settings_sync/subscriber.py — FOUND (209 LOC)
api/app/settings_sync/__init__.py — FOUND (64 LOC)

$ ls api/tests/unit/test_settings_sync_{client,subscriber}.py
api/tests/unit/test_settings_sync_client.py — FOUND (365 LOC, 11 test)
api/tests/unit/test_settings_sync_subscriber.py — FOUND (290 LOC, 11 test)

$ git log --oneline -4
17ff523 feat(06-02): them subscriber.py asyncio loop + Pydantic InvalidateMessage — FOUND
102b512 test(06-02): them 11 failing test subscriber.py + InvalidateMessage — FOUND
2890973 feat(06-02): them 3 HTTP client class client.py — FOUND
9701fda test(06-02): them 11 failing test client.py 3 HTTP client class — FOUND

$ grep -c "class RagConfigClient\|class HubRegistryClient\|class ApiKeyVerifyClient\|class SettingsUnavailableError" api/app/settings_sync/client.py
4

$ grep -c "class InvalidateMessage\|async def settings_subscriber_loop" api/app/settings_sync/subscriber.py
2

$ uv run pytest tests/unit/test_settings_sync_client.py tests/unit/test_settings_sync_subscriber.py --no-header
22 passed in 12.54s — FOUND

$ uv run pytest tests/unit/ -q --no-header
430 passed in 49.22s — FOUND

$ uv run ruff check app/settings_sync/ tests/unit/test_settings_sync_*.py
All checks passed!

$ uv run mypy --strict app/settings_sync/client.py app/settings_sync/subscriber.py app/settings_sync/__init__.py
Success: no issues found in 3 source files
```

All claims verified. SUMMARY.md ready cho Wave 3 dependency consume.
