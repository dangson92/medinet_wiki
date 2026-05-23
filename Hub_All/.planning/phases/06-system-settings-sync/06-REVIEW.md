---
phase: 06-system-settings-sync
reviewed: 2026-05-23T00:00:00Z
depth: standard
files_reviewed: 27
files_reviewed_list:
  - api/app/auth/api_key.py
  - api/app/auth/dependencies.py
  - api/app/config.py
  - api/app/main.py
  - api/app/routers/api_keys.py
  - api/app/routers/rag_config.py
  - api/app/schemas/api_keys.py
  - api/app/settings_sync/__init__.py
  - api/app/settings_sync/client.py
  - api/app/settings_sync/keys.py
  - api/app/settings_sync/metrics.py
  - api/app/settings_sync/subscriber.py
  - api/tests/conftest.py
  - api/tests/integration/conftest.py
  - api/tests/integration/test_settings_sync_lifespan_integration.py
  - api/tests/integration/test_settings_sync_pubsub_e2e.py
  - api/tests/unit/test_api_keys_verify_endpoint.py
  - api/tests/unit/test_auth_router_hub_redirect.py
  - api/tests/unit/test_config_settings_proxy_secret.py
  - api/tests/unit/test_rag_config_publish_invalidate.py
  - api/tests/unit/test_require_api_key_hub_branch.py
  - api/tests/unit/test_require_internal_auth.py
  - api/tests/unit/test_settings_sync_client.py
  - api/tests/unit/test_settings_sync_keys.py
  - api/tests/unit/test_settings_sync_metrics.py
  - api/tests/unit/test_settings_sync_subscriber.py
  - docker-compose.override.yml.template
  - docker-compose.yml
findings:
  critical: 0
  warning: 3
  info: 6
  total: 9
status: issues_found
---

# Phase 6: Code Review Report — System Settings Sync (SETTINGS-01..04)

**Reviewed:** 2026-05-23
**Depth:** standard
**Files Reviewed:** 27
**Status:** issues_found (3 warning + 6 info, 0 critical)

## Summary

Phase 6 ship 5 plan đóng 4 REQ-ID SETTINGS-01..04 — HTTP pull + Redis pub/sub invalidate hybrid mechanism. Module mới `api/app/settings_sync/` (4 file ~750 LOC) + 1 router endpoint mới (`POST /api/api-keys/verify`) + 1 dependency mới (`require_internal_auth`) + refactor `require_api_key` branch hub_name + lifespan integration với 4 escape hatch.

**Khu vực mạnh:**
- **Secret handling đúng chuẩn:** `hmac.compare_digest` constant-time compare (T-06-03-01); SHA-256 hash 16-char prefix cho cache key apikey (T-06-04-02 — verify qua test `test_make_apikey_cache_key_does_not_contain_plaintext`); 32-char minimum entropy enforced ở Settings validator BẤT KỂ hub_name (D-V3-Phase6-D LOCKED).
- **Pub/sub gating Pydantic Literal enum reject invalid `config_key`** (T-06-02-03) — unit test verify `test_invalidate_message_rejects_invalid_config_key`.
- **Lifespan resilience:** `SETTINGS_SKIP_FETCH=1` escape hatch song song 3 flag tiền nhiệm (JWKS_SKIP_FETCH/SYNC_SKIP_CENTRAL_POOL/COCOINDEX_SKIP_SETUP); fail-loud boot raise → uvicorn exit 1; shutdown `asyncio.wait_for(timeout=10s)` + suppress CancelledError/TimeoutError; subscriber spawn guard `redis_ready` (T-06-04-04 source-of-truth).
- **Test isolation:** `conftest.py` autouse `_env` fixture set `SETTINGS_PROXY_SECRET="x"*32` default + `get_settings.cache_clear()` mỗi test — không leak giữa test.
- **Best-effort fail-open** trong `update_rag_config` publish — Redis down KHÔNG block admin PUT (carry forward search_cache.py pattern M2).
- **Backward compat M2 preserved:** `require_api_key` signature mở rộng thêm `request: Request` (FastAPI auto-inject — consumer KHÔNG cần update); `update_rag_config` PUT mở rộng `request: Request`.

**Khu vực cần lưu ý:**
- 1 vấn đề về JSON response decoding trong `_decode_cached` (chấp nhận str hoặc bytes nhưng KHÔNG validate dict shape — pub/sub poisoning có thể inject dict shape sai).
- 2 vấn đề về observability gap (latency metric KHÔNG emit trên error path; skipped invalidations KHÔNG được track).
- Vấn đề thiết kế FastAPI route ordering `POST /verify` vs `/{key_id}/...` — không phải bug nhưng có thể gây confusion cho operator.

## Warnings

### WR-01: `ApiKeyVerifyClient.verify` KHÔNG validate central response shape — silent corruption nếu central trả JSON sai

**File:** `api/app/settings_sync/client.py:347-353`

**Issue:**
```python
data = resp.json()
principal = data.get("principal") if data.get("valid") else None
if principal is None:
    APIKEY_VERIFY_TOTAL.labels(
        hub_name=self._hub_name, result="invalid"
    ).inc()
    return None
```

Nếu central trả status 200 NHƯNG body shape sai (vd `data` không phải dict, hoặc `principal` là str thay vì dict), code sẽ:
1. Crash với `AttributeError: 'str' object has no attribute 'get'` (nếu data là str) — nhưng kế thừa try/except outer KHÔNG cover (try block kết thúc ở line 315 trước khi `resp.json()` được gọi line 347).
2. HOẶC cache invalid shape `principal` (vd str) qua `setex` line 356-358 → require_api_key trả dict sai shape → endpoint downstream crash khi access `principal["id"]`.

Pydantic schema validate response (giống `InvalidateMessage` ở subscriber.py) sẽ catch shape mismatch sớm và reject KHÔNG cache.

**Fix:** Wrap parse + validate trong try/except + dùng Pydantic schema cho central response:
```python
# app/settings_sync/client.py
from pydantic import BaseModel, ValidationError


class VerifyResponse(BaseModel):
    valid: bool
    principal: dict[str, Any] | None = None


# In verify():
try:
    parsed = VerifyResponse.model_validate(resp.json())
except (ValueError, ValidationError) as e:
    logger.warning(
        "apikey_verify_client_bad_response: hub=%s err=%s",
        self._hub_name, e,
    )
    APIKEY_VERIFY_TOTAL.labels(
        hub_name=self._hub_name, result="invalid"
    ).inc()
    return None

if not parsed.valid or parsed.principal is None:
    APIKEY_VERIFY_TOTAL.labels(
        hub_name=self._hub_name, result="invalid"
    ).inc()
    return None
principal = parsed.principal
```

---

### WR-02: `_decode_cached` KHÔNG validate JSON return là dict (RagConfigClient) hoặc list (HubRegistryClient) — Redis cache poisoning có thể inject sai shape

**File:** `api/app/settings_sync/client.py:75-83, 141, 221, 304`

**Issue:**
```python
def _decode_cached(value: Any) -> Any:
    if isinstance(value, bytes):
        return json.loads(value.decode("utf-8"))
    return json.loads(value)
```

`_decode_cached` chỉ decode JSON — KHÔNG validate kết quả là dict / list / dict[principal]. Nếu attacker hoặc operator nhầm `SET settings:rag_config:yte '"string-not-dict"'` qua redis-cli, hot path `RagConfigClient.get()` sẽ trả `str` thay vì `dict[str, Any]` — downstream consumer crash khi access `data["embedding_provider"]`.

Tương tự `HubRegistryClient.list_hubs()` (expect list) và `ApiKeyVerifyClient.verify()` cache hit (expect principal dict).

Threat model T-06-02-03 đã được mitigate ở subscriber.py (Pydantic InvalidateMessage validate) NHƯNG cache value chính nó KHÔNG được validate sau khi cache hit.

**Fix:** Defensive type check sau decode:
```python
# RagConfigClient.get()
if cached is not None:
    decoded = _decode_cached(cached)
    if not isinstance(decoded, dict):
        logger.warning(
            "rag_config_cache_corrupt_shape: hub=%s type=%s — flush + refetch",
            self._hub_name, type(decoded).__name__,
        )
        await self._redis.delete(self._cache_key)
    else:
        SETTINGS_CACHE_HIT_TOTAL.labels(
            hub_name=self._hub_name, key_type="rag_config"
        ).inc()
        return decoded
# fall through → cache miss path
```

Hoặc dùng Pydantic TypeAdapter cho compile-time type-safe decode.

---

### WR-03: `SETTINGS_PULL_LATENCY_SECONDS` histogram KHÔNG được emit khi httpx fetch raise — slow-fail latencies KHÔNG visible

**File:** `api/app/settings_sync/client.py:154-173, 233-252, 306-329`

**Issue:** Trong cả 3 client (`_fetch_and_cache` của RagConfigClient + HubRegistryClient, và `verify` của ApiKeyVerifyClient), `start = time.monotonic()` được capture nhưng nếu httpx raise (timeout, ConnectError, 5xx via raise_for_status), exception propagate qua `_fetch_and_cache` mà KHÔNG hit `SETTINGS_PULL_LATENCY_SECONDS.observe(latency)`. Trong `verify`, latency emit chỉ trên success path (sau line 326 try/except).

Hậu quả: Prometheus histogram chỉ ghi nhận thời gian của các call success, KHÔNG ghi nhận slow-fail (timeout 5s đầy đủ). SRE alert dựa trên p95 latency sẽ KHÔNG fire khi central hồi đáp chậm trước khi timeout.

**Fix:** Wrap latency observe trong try/finally:
```python
async def _fetch_and_cache(self, *, timeout: httpx.Timeout) -> dict[str, Any]:
    start = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(f"{self._central_url}{self._endpoint}")
            resp.raise_for_status()
            data = resp.json()
    finally:
        latency = time.monotonic() - start
        SETTINGS_PULL_LATENCY_SECONDS.labels(
            hub_name=self._hub_name, endpoint=self._endpoint
        ).observe(latency)
    # ... rest of success-path setex + return
```

Áp dụng tương tự cho `HubRegistryClient._fetch_and_cache` và `ApiKeyVerifyClient.verify`.

## Info

### IN-01: `subscriber.py` `_handle_invalidate` KHÔNG emit `SETTINGS_INVALIDATE_RECEIVED_TOTAL` khi hub mismatch skip

**File:** `api/app/settings_sync/subscriber.py:91-111`

**Issue:** Khi `msg.config_key == "rag_config"` và `msg.hub != "*" and msg.hub != hub_name`, hàm `return` sớm line 94 → KHÔNG đến line 109 `SETTINGS_INVALIDATE_RECEIVED_TOTAL.labels(...).inc()`. SRE KHÔNG thấy được skipped invalidations qua metrics → khó debug nếu central publish nhầm hub target.

**Fix:** Counter "received" nên đếm mọi message reach subscriber (sau Pydantic validate). Thêm 1 label `skipped` hoặc emit trước branch:
```python
async def _handle_invalidate(redis: Any, hub_name: str, msg: InvalidateMessage) -> None:
    SETTINGS_INVALIDATE_RECEIVED_TOTAL.labels(
        hub_name=hub_name, key_type=msg.config_key
    ).inc()  # ← emit FIRST
    if msg.config_key == "rag_config":
        if msg.hub != "*" and msg.hub != hub_name:
            return  # skip, but counter already incremented
        # ...
```

---

### IN-02: `subscriber.py` reconnect comment misleading — `asyncio.sleep` chạy CẢ success-drain path

**File:** `api/app/settings_sync/subscriber.py:200-203`

**Issue:**
```python
        # Reconnect delay (only reached on non-cancel exception path or natural
        # listen iterator drain — Redis pubsub thực tế listen() block vĩnh viễn).
        await asyncio.sleep(reconnect_seconds)
```

Comment nói "only reached on non-cancel exception path" nhưng control flow cho thấy `await asyncio.sleep` cũng chạy khi `_subscribe_and_listen` return normally (KHÔNG raise, KHÔNG cancel — vd test mock pubsub.listen() yield N message rồi end). Comment đúng cho production (`listen()` block forever) nhưng misleading cho người đọc code/test.

**Fix:** Update comment cho rõ:
```python
        # Reconnect delay — reached khi:
        # (1) non-cancel exception path (ConnectionError, etc — best-effort retry).
        # (2) `listen()` iterator drain natural (test mock; production listen()
        #     block vĩnh viễn cho tới khi connection close).
        # KHÔNG reached khi CancelledError (re-raise trên line 193).
        await asyncio.sleep(reconnect_seconds)
```

---

### IN-03: `_subscribe_and_listen` finally block silent swallow `pubsub.aclose()` errors

**File:** `api/app/settings_sync/subscriber.py:154-159`

**Issue:**
```python
    finally:
        if pubsub is not None:
            try:
                await pubsub.aclose()
            except Exception:  # noqa: BLE001
                pass
```

Silent swallow trên aclose error có thể hide Redis client leak (vd version mismatch redis-py async vs sync `close()`). Test KHÓ catch leak này.

**Fix:** Log warning thay vì silent `pass`:
```python
    finally:
        if pubsub is not None:
            try:
                await pubsub.aclose()
            except Exception as e:  # noqa: BLE001
                logger.warning(
                    "settings_subscriber_pubsub_close_failed: hub=%s err=%s",
                    hub_name, e,
                )
```

---

### IN-04: `api_keys.py` route ordering — `POST /verify` đặt sau parameterized routes; GET/PUT/POST `/verify` (sai method) trả 400 "INVALID_API_KEY_ID" thay vì 404/405

**File:** `api/app/routers/api_keys.py:49-192`

**Issue:** Router declaration order:
1. `GET ""` (list)
2. `POST ""` (create)
3. `GET "/{key_id}"` (get single)
4. `PUT "/{key_id}"` (update)
5. `POST "/{key_id}/revoke"` (revoke)
6. `POST "/verify"` (Phase 6 mới)

FastAPI/Starlette match exact path trước path template, NHƯNG nếu operator gửi `GET /api/api-keys/verify` (HTTP method sai), nó sẽ match `GET /{key_id}` với `key_id="verify"` → `UUID("verify")` raise → 400 `INVALID_API_KEY_ID`. Operator debug sẽ confuse vì path đúng (`/verify`) nhưng error message nói "key_id không hợp lệ".

**Fix:** Move `POST /verify` lên trước parameterized routes hoặc add explicit declare `verify` reserved:
```python
@router.post("/verify", response_model=None)
async def verify_api_key(...):
    ...


@router.get("/{key_id}")  # AFTER /verify
async def get_api_key(key_id: str, ...):
    if key_id == "verify":
        return resp.method_not_allowed(...)  # explicit
    ...
```

Hoặc đơn giản hơn — đặt `POST /verify` ngay sau `POST ""` (line 86):
```python
@router.post("/verify", response_model=None)
async def verify_api_key(...):  # move up before /{key_id}
    ...
```

---

### IN-05: `client.py` `_DEFAULT_TIMEOUT_INITIAL` default 5.0 mâu thuẫn với `connect=2.0 read=5.0`

**File:** `api/app/settings_sync/client.py:56`

**Issue:**
```python
_DEFAULT_TIMEOUT_INITIAL = httpx.Timeout(5.0, connect=2.0, read=5.0)
```

`httpx.Timeout(5.0)` đặt `write=5.0, pool=5.0` (cùng default 5.0 cho 2 timeout chưa override). Comment docstring giải thích đúng nhưng giá trị 5.0 cho write/pool có vẻ rộng so với connect=2.0. Operator đọc code sẽ confuse "tại sao initial = 5.0 mà connect = 2.0?".

**Fix:** Hoặc dùng pattern explicit cả 4 timeout:
```python
_DEFAULT_TIMEOUT_INITIAL = httpx.Timeout(
    connect=2.0, read=5.0, write=2.0, pool=2.0
)
```

Hoặc comment rõ "5.0 là default cho write/pool — chỉ override connect+read":
```python
# 5.0 = write/pool fallback (httpx requires either default OR all 4 param).
# Phase 6 chỉ care connect (network reach central) + read (central response).
# write nhỏ (POST body verify chỉ vài KB) + pool unused (1 connection per fetch).
_DEFAULT_TIMEOUT_INITIAL = httpx.Timeout(5.0, connect=2.0, read=5.0)
```

---

### IN-06: `dependencies.py` `require_internal_auth` lazy import `hmac` mỗi request — chi phí marginal nhưng KHÔNG cần thiết

**File:** `api/app/auth/dependencies.py:274`

**Issue:**
```python
async def require_internal_auth(...) -> None:
    import hmac
    from app.config import get_settings
    ...
```

`import hmac` chạy mỗi lần dependency được FastAPI invoke (Python module cache hit, nhưng vẫn có overhead). M2 pattern là lazy import để break circular deps; `hmac` là stdlib KHÔNG có circular concern.

**Fix:** Move `import hmac` lên module-level top:
```python
# app/auth/dependencies.py header
import hmac
import logging
from collections.abc import Awaitable, Callable
# ...
```

(`get_settings` lazy import có thể giữ để tránh circular nếu cần — nhưng cũng có thể move lên top vì `app.config` không depend on `app.auth`.)

---

## Coverage Summary

**Secret Handling (focus area):**
- `settings_proxy_secret` validator: ✅ Enforce length ≥ 32 char BOTH central + hub con (`_enforce_settings_proxy_secret` config.py:564-590); test coverage 4 boundary case (32-char accept, 31-char fail, empty fail, hub_name parametrize).
- `require_internal_auth`: ✅ `hmac.compare_digest` constant-time compare (dependencies.py:280); test verify qua `test_uses_hmac_compare_digest_constant_time` spy.
- `make_apikey_cache_key` SHA-256 prefix 16-char: ✅ Test verify `test_make_apikey_cache_key_does_not_contain_plaintext` + deterministic check.
- KHÔNG plaintext leak: ✅ `subscriber.py` apikey flush dùng SCAN+DEL pattern (KHÔNG cần plaintext).

**Pub/Sub Correctness (focus area):**
- `InvalidateMessage` Pydantic Literal enum gating: ✅ Test reject invalid `config_key` qua `test_invalidate_message_rejects_invalid_config_key`.
- Reconnect loop graceful CancelledError: ✅ Re-raise line 191-193 + test `test_subscriber_cancelled_error_reraises_graceful`.
- Cache flush branch by `config_key`: ✅ 3 branch verified qua 5 subscriber test (rag_config broadcast/mismatch + hub_registry singleton + apikey full flush + invalid skip).

**Lifespan Resilience (focus area):**
- `SETTINGS_SKIP_FETCH=1` escape hatch: ✅ Test `test_skip_fetch_flag_bypasses_settings_clients` (4 state = None).
- Fail-loud `fetch_initial` boot: ✅ Test `test_lifespan_fetch_initial_fail_raises` direct + main.py grep assert.
- Shutdown `asyncio.wait_for(timeout=10s)` + CancelledError/TimeoutError suppress: ✅ main.py:668-679; test `test_lifespan_shutdown_resets_subscriber_state`.
- `redis_ready` guard subscriber spawn: ✅ main.py:546 + test `test_lifespan_subscriber_branch_by_redis_ready` (T-06-04-04 mitigation).

**httpx Client Safety (focus area):**
- Timeout structure: ⚠️ IN-05 minor confusion về `httpx.Timeout(5.0, connect=2.0, read=5.0)`.
- Error wrapping `SettingsUnavailableError`: ✅ RagConfigClient + HubRegistryClient wrap exception with `from e`; raise chỉ ở `fetch_initial` + `get`/`list_hubs` (KHÔNG ở ApiKeyVerifyClient — đúng intent T-06-02-04 fail-quiet apikey verify).
- Retry/cache semantics: ✅ Cache hit > miss > HTTP > setex; KHÔNG cache negative 401 (T-06-02-04).
- Shape validation: ⚠️ WR-01, WR-02 (KHÔNG validate response shape qua Pydantic).

**FastAPI DI (focus area):**
- `request: Request` correctness: ✅ `api_key.py::require_api_key` line 28 — wired đúng.
- `request.app.state.*` access: ✅ Defensive `getattr(request.app.state, "api_key_verify_client", None)` line 60 — KHÔNG raise AttributeError nếu chưa init.

**Test Isolation (focus area):**
- `conftest.py` autouse `_env`: ✅ `SETTINGS_PROXY_SECRET="x"*32` default + `get_settings.cache_clear()` line 38-43.
- Integration conftest `hub_app_factory` Plan 06-04 update: ✅ `SETTINGS_SKIP_FETCH=1` env hub con block.
- `test_auth_router_hub_redirect.py` `_setup_env`: ✅ Plan 06-04 update line 66 thêm `SETTINGS_SKIP_FETCH=1`.

**Backward Compat:**
- ✅ `require_api_key` signature mở rộng `request: Request` (FastAPI auto-inject — consumer KHÔNG cần update).
- ✅ `update_rag_config` PUT signature mở rộng `request: Request`.
- ✅ M2 `ApiKeyService.verify_key` AES-GCM at-rest LOCKED unchanged.
- ✅ M2 `rag_config_service.py::update_config()` LOCKED unchanged — Phase 6 chỉ wrap publish best-effort sau success.

**Docker Compose Wiring:**
- ✅ 4 service (central + 3 hub con) env `SETTINGS_PROXY_SECRET: ${VAR:?msg}` fail-loud syntax.
- ✅ `docker-compose.override.yml.template` FACTOR-04 placeholder cho hub con dynamic (Plan 02-05 carry forward).

---

_Reviewed: 2026-05-23_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
_Project: MEDWIKI v3.0 Multi-Hub Split — Phase 6 System Settings Sync (SETTINGS-01..04)_
