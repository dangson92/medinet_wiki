---
phase: 6
phase_name: System Settings Sync
slug: system-settings-sync
milestone: v3.0
mapped: 2026-05-23
source: gsd-pattern-mapper (Auto Mode `--auto --chain`)
status: Ready for planning
---

# Phase 6: System Settings Sync — Pattern Map

**Mapped:** 2026-05-23
**Files analyzed:** 14 (5 new module + 6 extension + 3 docker/config + N test + N docs)
**Analogs found:** 14 / 14 (100% — toàn bộ pattern carry forward từ Phase 3+4+5 + M2)

> Tham chiếu: `06-CONTEXT.md` `<domain>` 8 mục + `<code_context>` integration points. Mọi excerpt giữ tiếng Anh; mô tả tiếng Việt có dấu.

---

## File Classification

| Target File | Wave | Role | Data Flow | Closest Analog | Match |
|-------------|------|------|-----------|----------------|-------|
| `api/app/settings_sync/__init__.py` | 2 | new module (package init) | re-export | `api/app/sync/__init__.py` | exact |
| `api/app/settings_sync/keys.py` | 1 | new module (constants) | config | `api/app/sync/keys.py` + `api/app/services/search_cache.py:30-35` | exact |
| `api/app/settings_sync/client.py` | 2 | new module (3 client class) | request-response (HTTP pull) | `api/app/auth/jwks.py::JWKSCache` (httpx async client + cache lifecycle) | exact |
| `api/app/settings_sync/subscriber.py` | 2 | new module (asyncio task loop) | event-driven (pub/sub) | `api/app/services/search_cache.py::search_cache_subscriber` | exact |
| `api/app/settings_sync/metrics.py` | 1 | new module (Prometheus collectors) | metric emit | `api/app/sync/metrics.py` (module-level Counter/Histogram/Gauge + label `hub_name`) | exact |
| `api/app/auth/api_key.py::require_api_key` | 3 | refactor (branch verify) | request-response | `api/app/auth/dependencies.py::get_current_user` (Phase 3 branch central=local vs hub con=cache) | exact |
| `api/app/auth/dependencies.py::require_internal_auth` | 3 | new dependency (header check) | request-response | `api/app/auth/dependencies.py::require_role` factory pattern + `hmac.compare_digest` | role-match |
| `api/app/routers/rag_config.py::update_rag_config` | 3 | extend (publish after commit) | event-driven | `api/app/services/search_cache.py::publish_invalidate` + `documents_service.py:139-141` redis attribute | exact |
| `api/app/routers/api_keys.py` (add `POST /verify`) | 3 | extend (new endpoint) | request-response | `api/app/routers/api_keys.py::revoke_api_key` (existing POST shape) + `require_internal_auth` dep | exact |
| `api/app/main.py::lifespan` (extend hub con block) | 4 | extend lifespan | startup blocking + asyncio task | `api/app/main.py:207-248` (JWKSCache block) + `:275-323` (central_sync_pool block) | exact |
| `api/app/config.py::Settings` (5 field + 1 validator) | 1 | extend config | config | `api/app/config.py:109-117` (jwks_refresh_interval/max_stale) + `:325-345` (`_enforce_central_jwks_url_for_hub`) | exact |
| `docker-compose.yml` (`SETTINGS_PROXY_SECRET` × 4 service) | 1 | extend infra | config | `docker-compose.yml:136-152` (CENTRAL_JWKS_URL + CENTRAL_URL + HUB_ID + CENTRAL_SYNC_DSN env wire 3 hub con) | exact |
| `docker-compose.override.yml.template` (FACTOR-04 placeholder) | 1 | extend template | config | Plan 02-05 + 04-02 + 05-05 template append precedent | exact |
| `.env.example` (document 4 env mới) | 1 | extend docs | config | Phase 3+4+5 `.env.example` env doc precedent | exact |
| `api/tests/unit/test_settings_sync_*.py` (4 file) | 2 | unit test | test | `api/tests/unit/test_sync_models.py` + `test_sync_metrics.py` + `test_sync_worker.py` + `test_jwks_cache.py` | exact |
| `api/tests/integration/test_settings_sync_*.py` (1-2 file) | 4 | integration test | test (mock pub/sub + ASGI lifespan) | `api/tests/integration/test_sync_lifespan_integration.py` + `test_jwks_cache_lifecycle.py` | exact |
| Closeout docs (CLAUDE.md §6, STATE.md, REQUIREMENTS.md, ROADMAP.md, README.md) | 5 | docs | docs | Plan 03-05 + 04-07 + 05-06 closeout precedent | exact |

---

## Pattern Assignments

### Wave 1 — BLOCKING infra (parallel-able: 4 file disjoint)

#### `api/app/settings_sync/keys.py` (new module, constants)

**Analog:** `api/app/sync/keys.py` (Phase 4 SQL constants module-level) + `api/app/services/search_cache.py:30-35` (Redis channel + key prefix constants)

**Constants pattern** (`search_cache.py:29-34`):
```python
#: Pattern channel subscriber psubscribe — mọi hub publish lên `hub:{id}:invalidate`.
INVALIDATE_CHANNEL_PATTERN = "hub:*:invalidate"
#: Prefix Redis SET gắn cache key theo hub.
HUBTAG_PREFIX = "search:hubtag:"
#: TTL SET hub-tag — tự hết hạn nếu subscriber miss event (phòng rò key).
HUBTAG_TTL = 600
```

**Adapt:** Đổi sang `SETTINGS_INVALIDATE_CHANNEL = "settings:invalidate"` (1 channel duy nhất — D-V3-Phase6-C LOCKED, KHÔNG split 3 channel), 3 cache key prefix `RAG_CONFIG_KEY_PREFIX = "settings:rag_config:"`, `HUB_REGISTRY_KEY = "settings:hub_registry"` (singleton, KHÔNG per-hub), `APIKEY_VERIFY_KEY_PREFIX = "apikey:verify:"`. Thêm helper `make_apikey_cache_key(api_key: str) -> str` dùng `hashlib.sha256(api_key.encode()).hexdigest()[:16]` (T-06-04-02 — KHÔNG plaintext trong Redis key). Module-level `__all__` re-export pattern song song `sync/keys.py`.

---

#### `api/app/settings_sync/metrics.py` (new module, 6 Prometheus collectors)

**Analog:** `api/app/sync/metrics.py:32-82` (module-level Counter/Histogram/Gauge với label `hub_name` — W7 fix carry forward)

**Pattern** (`sync/metrics.py:32-46`):
```python
from prometheus_client import Counter, Gauge, Histogram

SYNC_LAG_SECONDS: Histogram = Histogram(
    "sync_lag_seconds",
    "Cross-hub sync latency: outbox.created_at → central INSERT processed_at",
    labelnames=("hub_name",),
    buckets=(0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0, 600.0),
)

SYNC_OUTBOX_PENDING: Gauge = Gauge(
    "sync_outbox_pending",
    "Số outbox rows pending hiện tại theo hub_name (worker poll mỗi tick set)",
    labelnames=("hub_name",),
)

SYNC_ATTEMPT_TOTAL: Counter = Counter(
    "sync_attempt_total",
    "Cumulative push attempts (success/fail) — Plan 04-03 worker emit per row processed",
    labelnames=("hub_name", "status"),
)
```

**Adapt:** 6 collector mới (CONTEXT.md `<domain>` §8): `SETTINGS_CACHE_HIT_TOTAL` Counter `(hub_name, key_type=rag_config|hub_registry|apikey)`, `SETTINGS_CACHE_MISS_TOTAL` Counter same labels, `SETTINGS_PULL_LATENCY_SECONDS` Histogram `(hub_name, endpoint)` buckets `(0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)` (httpx call ngắn hơn sync push), `SETTINGS_INVALIDATE_RECEIVED_TOTAL` Counter `(hub_name, key_type)`, `SETTINGS_STALE_SECONDS` Gauge `(hub_name, key_type)`, `APIKEY_VERIFY_TOTAL` Counter `(hub_name, result=valid|invalid|cached)`. Label `key_type` enum 3 value cố định = bounded cardinality (T-06-03-01 carry forward W7 fix).

---

#### `api/app/config.py::Settings` (extend — 5 field + 1 validator)

**Analog:** `api/app/config.py:109-126` (Phase 3 `central_jwks_url` + `jwks_refresh_interval` + `jwks_max_stale_seconds` + `central_url`) + `:325-345` (`_enforce_central_jwks_url_for_hub` model_validator)

**Field pattern** (`config.py:109-117`):
```python
# Phase 3 Plan 03-01 SSO-01 (D-V3-Phase3-A) — Hub con consume JWKS endpoint
# từ central qua intra-network HTTP. Default None ở central (KHÔNG cần fetch
# — central có local private.pem). Plan 03-02 add @model_validator
# `_enforce_central_jwks_url_for_hub` enforce hub con phải set field này
# KHÔNG None (fail-loud boot nếu thiếu).
# docker-compose 3 hub con set env
#   CENTRAL_JWKS_URL=http://python-api-central:8080/.well-known/jwks.json
central_jwks_url: str | None = None

# Phase 3 Plan 03-02 SSO-01 (D-V3-Phase3-B) — Hub con cache lifecycle
# 1h refresh interval matching Cache-Control max-age=3600 ở Plan 03-01.
# 24h hard limit (86400s): nếu cached value > limit → 503 JWKS_STALE
# envelope cho mọi JWT verify (R-V3-5 fail-loud delayed). Override qua env
# JWKS_REFRESH_INTERVAL + JWKS_MAX_STALE_SECONDS nếu test rotation nhanh.
jwks_refresh_interval: int = 3600
jwks_max_stale_seconds: int = 86400
```

**Validator pattern** (`config.py:325-345`):
```python
@model_validator(mode="after")
def _enforce_central_jwks_url_for_hub(self) -> Settings:
    """Phase 3 Plan 03-02 SSO-01 (D-V3-Phase3-B) — Hub con required CENTRAL_JWKS_URL.

    Central (hub_name="central") tự có private.pem local → KHÔNG cần fetch.
    Hub con (yte/duoc/hcns/dynamic) PHẢI set CENTRAL_JWKS_URL trỏ central
    endpoint để JWKSCache.fetch_initial() blocking startup. Thiếu → boot fail
    ở Settings validation (ValidationError trước khi tới lifespan).

    Threat model:
    - T-03-02-01 Tampering — env thiếu CENTRAL_JWKS_URL → hub con boot OK
      nhưng mọi JWT verify trả 500 (chưa lifespan startup). Fail-fast ở
      validator tránh production bug câm lặng.
    """
    if self.hub_name != "central" and not self.central_jwks_url:
        raise ValueError(
            f"hub_name={self.hub_name!r} (hub con) yêu cầu CENTRAL_JWKS_URL "
            f"env var. Set CENTRAL_JWKS_URL=http://python-api-central:8080"
            f"/.well-known/jwks.json (xem docker-compose.yml 3 hub con block)."
        )
    return self
```

**Adapt 5 field mới + 1 validator (CONTEXT.md `<canonical_refs>` Settings):**
- `settings_proxy_secret: str = ""` — REQUIRED cho cả central + hub con; validator length ≥ 32 char (D-V3-Phase6-D — 128-bit entropy mitigation T-06-04-01).
- `settings_cache_ttl_rag_config: int = 60` (D-V3-Phase6-B).
- `settings_cache_ttl_hub_registry: int = 300` (D-V3-Phase6-B — 5 phút rare-change).
- `settings_cache_ttl_apikey: int = 60` (D-V3-Phase6-B — AUX-02 hot revoke window).
- `settings_subscriber_reconnect_seconds: int = 5` (subscriber retry connect interval).
- Validator `_enforce_settings_proxy_secret` model_validator(mode="after") raise ValueError nếu `len(self.settings_proxy_secret) < 32` BẤT KỂ central hay hub con (KHÁC `_enforce_central_jwks_url_for_hub` — shared secret cả 2 phía cần).

---

#### `docker-compose.yml` + `docker-compose.override.yml.template` + `.env.example` (env wire 4 service)

**Analog:** `docker-compose.yml:136-152` (Phase 3+4 env wire 3 hub con) + Plan 04-02 + 05-05 template precedent.

**Pattern** (`docker-compose.yml:136-151` — yte service):
```yaml
# Phase 3 Plan 03-01 SSO-01 (D-V3-Phase3-A) — Hub con consume JWKS endpoint
# tu central qua intra-network HTTP (Docker service DNS). Plan 03-02 hub
# con JWKSCache lifespan startup blocking fetch URL nay. KHONG can TLS
# (intra-network medinet_net isolated).
CENTRAL_JWKS_URL: http://python-api-central:8080/.well-known/jwks.json
# Phase 3 Plan 03-04 SSO-02 (D-V3-Phase3-G) — Hub con redirect login/refresh
# toi central qua 307 Location. Settings._enforce_central_url_for_hub
# validator enforce hub con required (boot fail-fast neu thieu).
CENTRAL_URL: http://python-api-central:8080
# Phase 4 Plan 04-02 SYNC-01 (D-V3-Phase4-D2) — Hub con UUID identity tu
# medinet_central.hubs row. Operator export HUB_YTE_ID truoc `docker compose
# up` ... Cu phap `${VAR:?msg}` fail-loud KHONG set
# (docker-compose interpolation error truoc boot Settings).
HUB_ID: ${HUB_YTE_ID:?HUB_YTE_ID env var phai set khop central.hubs.id UUID — Plan 04-02 SYNC-01}
CENTRAL_SYNC_DSN: postgresql+asyncpg://medinet:${POSTGRES_PASSWORD:-medinet_dev_pwd}@postgres:5432/medinet_central
```

**Adapt:** Thêm 1 dòng env cho cả 4 service (`python-api-central` + 3 hub con):
```yaml
# Phase 6 Plan 06-XX SETTINGS-03 (D-V3-Phase6-D) — Shared secret cho 2 endpoint
# internal-only (POST /api/api-keys/verify hiện tai + future flush). 32 char min
# (Settings validator enforce). Operator gen: openssl rand -hex 32.
SETTINGS_PROXY_SECRET: ${SETTINGS_PROXY_SECRET:?SETTINGS_PROXY_SECRET env var phai set min 32 char — Plan 06 SETTINGS-03}
```

`.env.example` thêm 4 dòng document:
```
# Phase 6 — System Settings Sync (Plan 06 SETTINGS-01..04)
# Shared secret cho hub con call central internal endpoint. Generate:
#   openssl rand -hex 32
SETTINGS_PROXY_SECRET=replace-with-32-byte-hex-secret
SETTINGS_CACHE_TTL_RAG_CONFIG=60
SETTINGS_CACHE_TTL_HUB_REGISTRY=300
SETTINGS_CACHE_TTL_APIKEY=60
```

`docker-compose.override.yml.template` (FACTOR-04 — Plan 02-05 carry forward): thêm placeholder `SETTINGS_PROXY_SECRET: ${SETTINGS_PROXY_SECRET:?...}` ở block `python-api-${HUB_NAME}` environment.

---

### Wave 2 — Client + subscriber + tests (parallel-able, depend Wave 1)

#### `api/app/settings_sync/client.py` (new module — 3 HTTP client class)

**Analog:** `api/app/auth/jwks.py::JWKSCache` (Plan 03-02 — httpx async + fetch_initial blocking + background refresh + in-process cache + lifecycle methods)

**Class pattern** (`jwks.py` JWKSCache — Plan 03-02 PLAN excerpt):
```python
class JWKSCache:
    """In-process LRU JWKS cache cho hub con verify JWT (D-V3-Phase3-D)."""

    def __init__(
        self,
        jwks_url: str,
        *,
        refresh_interval: int = 3600,
        max_stale_seconds: int = 86400,
        timeout: float = 5.0,
    ) -> None:
        self._jwks_url = jwks_url
        self._refresh_interval = refresh_interval
        self._max_stale_seconds = max_stale_seconds
        self._timeout = timeout
        self._keys_by_kid: dict[str, RSAPublicKey] = {}
        self._last_refresh_ts: float = 0.0
        self._refresh_task: asyncio.Task[None] | None = None
        self._lock = asyncio.Lock()

    async def fetch_initial(self) -> None:
        """Blocking fetch — raise nếu fail (boot fail-loud D-V3-Phase3-B)."""
        try:
            await self._fetch_and_cache()
        except Exception as e:
            logger.critical(
                "jwks_fetch_initial_failed: url=%s error=%s — boot abort",
                self._jwks_url, e,
            )
            raise

    async def _fetch_and_cache(self) -> None:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(self._jwks_url)
            resp.raise_for_status()
            data = resp.json()
        # ... parse + cache lock ...
```

**Adapt thành 3 client class:**

1. **`RagConfigClient`** — fetch `GET {central_url}/api/rag-config` + cache Redis key `settings:rag_config:{hub_name}` TTL 60s. `fetch_initial()` blocking 5s lifespan hub con (D-V3-Phase6-A). `get()` hot path đọc Redis → miss → HTTP fetch + write Redis + emit `SETTINGS_CACHE_HIT/MISS_TOTAL` + `SETTINGS_PULL_LATENCY_SECONDS.observe()`. Fail-loud nếu Redis miss + central down → raise `SettingsUnavailableError` → 503 envelope `SETTINGS_UNAVAILABLE` qua ErrorHandlerMiddleware (CONTEXT.md `<decisions>` Claude's Discretion).

2. **`HubRegistryClient`** — fetch `GET {central_url}/api/hubs` + cache Redis key `settings:hub_registry` (singleton, KHÔNG per-hub) TTL 300s (D-V3-Phase6-B). `fetch_initial()` blocking 5s. Interface `list_hubs() -> list[HubInfo]`.

3. **`ApiKeyVerifyClient`** — fetch `POST {central_url}/api/api-keys/verify` body `{"api_key": "..."}` header `X-Internal-Auth: {settings_proxy_secret}`. Cache Redis key `apikey:verify:{sha256(key)[:16]}` TTL 60s (T-06-04-02 hash, KHÔNG plaintext). `verify(api_key: str) -> dict | None` — None nếu central reject 401. Emit `APIKEY_VERIFY_TOTAL{result=valid|invalid|cached}`. KHÔNG cache negative response (401) — fail-quiet pass-through (CONTEXT.md Claude's Discretion "no negative cache").

**Shared base:** module-level `httpx.AsyncClient` singleton qua `@lru_cache` (CONTEXT.md Claude's Discretion) + `httpx.Timeout(connect=2.0, read=5.0)` cho fetch_initial; `httpx.Timeout(connect=5.0, read=10.0)` cho refresh task.

---

#### `api/app/settings_sync/subscriber.py` (new module — asyncio task pub/sub loop)

**Analog:** `api/app/services/search_cache.py::search_cache_subscriber` (lines 98-138 — production-ready pub/sub subscriber pattern)

**Pattern** (`search_cache.py:98-138`):
```python
async def search_cache_subscriber(redis: Any) -> None:
    """Subscriber loop — lắng nghe `hub:*:invalidate` → `invalidate_hub`.

    Chạy như asyncio background task trong lifespan (`main.py`). psubscribe
    pattern `hub:*:invalidate`; mỗi pmessage tách `hub_id` (phần giữa channel)
    + validate format TRƯỚC khi invalidate — channel rác bị bỏ qua (T-06-03-01).

    `CancelledError` → log + re-raise (graceful shutdown). Lỗi khác → log warning
    (KHÔNG crash lifespan — T-06-03-04). `finally` đóng pubsub.
    """
    if redis is None:
        logger.warning(
            "search_cache_subscriber: redis None — subscriber không khởi động"
        )
        return
    pubsub = redis.pubsub()
    try:
        await pubsub.psubscribe(INVALIDATE_CHANNEL_PATTERN)
        logger.info(
            "search_cache_subscriber_started: pattern=%s",
            INVALIDATE_CHANNEL_PATTERN,
        )
        async for message in pubsub.listen():
            if message is None or message.get("type") != "pmessage":
                continue
            channel = message.get("channel", "")
            # channel dạng "hub:{hub_id}:invalidate" — tách hub_id (phần giữa).
            # Validate format chặt: chỉ invalidate khi đúng schema (T-06-03-01).
            parts = channel.split(":")
            if len(parts) == 3 and parts[0] == "hub" and parts[2] == "invalidate":
                await invalidate_hub(redis, parts[1])
    except asyncio.CancelledError:
        logger.info("search_cache_subscriber_cancelled")
        raise
    except Exception as e:  # noqa: BLE001
        logger.warning("search_cache_subscriber_error: %s", e)
    finally:
        try:
            await pubsub.aclose()
        except Exception:  # noqa: BLE001
            pass
```

**Adapt:**
- Đổi `psubscribe(INVALIDATE_CHANNEL_PATTERN)` → `subscribe("settings:invalidate")` (1 channel cụ thể, KHÔNG pattern — D-V3-Phase6-C). Message type check `"message"` thay vì `"pmessage"`.
- Payload JSON validate qua Pydantic `InvalidateMessage(BaseModel)`: `config_key: Literal["rag_config","hub_registry","apikey"]` + `hub: str` + `key_id: str | None = None` + `timestamp: int`. Invalid → log warning skip (KHÔNG crash — T-06-03-03 carry forward).
- Phân nhánh `config_key`: rag_config → `redis.delete(f"settings:rag_config:{hub_name}")` (chỉ flush nếu `hub == "*"` HOẶC `hub == settings.hub_name`). hub_registry → `redis.delete("settings:hub_registry")`. apikey → nếu `key_id` set → `redis.delete(f"apikey:verify:{hash}")`; nếu null → SCAN + DEL all `apikey:verify:*` (full flush).
- Emit `SETTINGS_INVALIDATE_RECEIVED_TOTAL{hub_name, key_type=config_key}.inc()` mỗi event valid.
- **Reconnect logic** (Claude's Discretion): pub/sub disconnect (ConnectionError) → `await asyncio.sleep(settings.settings_subscriber_reconnect_seconds)` + retry connect (KHÔNG fail-loud — TTL natural fallback). Wrap outer `while True:` loop quanh try/except subscriber chính.

---

#### `api/app/settings_sync/__init__.py` (package init + re-export)

**Analog:** `api/app/sync/__init__.py` (Phase 4 module init pattern)

**Pattern** (Plan 04-03 PLAN excerpt):
```python
"""Phase 4 sync module — outbox worker + metrics + idempotent push (SYNC-01..05)."""
from app.sync.metrics import (
    SYNC_ATTEMPT_TOTAL, SYNC_COUNT_DRIFT, SYNC_DEAD_TOTAL,
    SYNC_HASH_DRIFT, SYNC_LAG_SECONDS, SYNC_OUTBOX_PENDING,
)
from app.sync.models import ChunkPayload, DocumentSyncStatus, OpType, SyncOutboxRow, SyncStatus
from app.sync.worker import sync_worker_loop

__all__ = [
    "ChunkPayload", "DocumentSyncStatus", "OpType",
    "SYNC_ATTEMPT_TOTAL", "SYNC_COUNT_DRIFT", "SYNC_DEAD_TOTAL",
    "SYNC_HASH_DRIFT", "SYNC_LAG_SECONDS", "SYNC_OUTBOX_PENDING",
    "SyncOutboxRow", "SyncStatus", "sync_worker_loop",
]
```

**Adapt:** Re-export `RagConfigClient`, `HubRegistryClient`, `ApiKeyVerifyClient`, `SettingsUnavailableError`, `settings_subscriber_loop`, 6 Prometheus collector + `make_apikey_cache_key`, `SETTINGS_INVALIDATE_CHANNEL`. Module docstring: `"""Phase 6 settings_sync module — HTTP pull + Redis pub/sub invalidate (SETTINGS-01..04)."""`

---

#### Unit tests `api/tests/unit/test_settings_sync_*.py` (4 file)

**Analog:** `api/tests/unit/test_jwks_cache.py:48-100` (httpx mock fixture `_make_mock_httpx_get`) + `test_sync_models.py` (Pydantic schema test) + `test_sync_metrics.py` (Prometheus label introspect)

**Mock httpx pattern** (`test_jwks_cache.py:48-71`):
```python
def _make_mock_httpx_get(
    response_data: dict,
    status_code: int = 200,
) -> MagicMock:
    """Helper build mock httpx async client trả JSON cố định."""
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.json = MagicMock(return_value=response_data)
    if status_code >= 400:
        mock_resp.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "mock 500",
                request=MagicMock(),
                response=mock_resp,
            )
        )
    else:
        mock_resp.raise_for_status = MagicMock()
    mock_get = AsyncMock(return_value=mock_resp)
    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.get = mock_get
    return mock_client
```

**Adapt 4 file:**
1. `test_settings_sync_client.py` — test RagConfigClient + HubRegistryClient + ApiKeyVerifyClient: fetch_initial happy + timeout + 500 + invalid shape; cache hit/miss qua mock Redis; TTL respect; fail-loud `SettingsUnavailableError`. Reuse `_make_mock_httpx_get` + `AsyncMock` Redis fixture.
2. `test_settings_sync_subscriber.py` — test `settings_subscriber_loop` parse valid + invalid payload; phân nhánh 3 config_key; cancel graceful (carry forward `test_jwks_cache.py` pattern asyncio.CancelledError); reconnect logic mock `redis.pubsub().subscribe` raise → sleep → retry.
3. `test_settings_sync_metrics.py` — 6 collector exist + label `hub_name` introspect + `_labelnames` check (W7 carry forward `test_sync_metrics.py::test_label_is_hub_name_not_hub_id`).
4. `test_settings_sync_keys.py` — `make_apikey_cache_key(api_key)` deterministic + sha256 prefix length + KHÔNG plaintext qua substring assertion.

---

### Wave 3 — Refactor `require_api_key` + extend central endpoints

#### `api/app/auth/api_key.py::require_api_key` (REFACTOR — branch verify path)

**Analog:** `api/app/auth/dependencies.py::get_current_user` lines 86-212 (Phase 3 Plan 03-02 — branch central=local PEM vs hub con=JWKSCache)

**Branch pattern** (`dependencies.py:122-212`):
```python
# Phase 3 Plan 03-02 — branch verify path theo hub_name (D-V3-Phase3-D).
from app.config import get_settings

settings = get_settings()
if settings.hub_name == "central":
    # Central: local public.pem M2 path (verify_token carry forward).
    try:
        claims = jwt_mgr.verify_token(token, expected_type="access")
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_TOKEN", "message": str(e)},
            headers={"WWW-Authenticate": "Bearer"},
        ) from e
else:
    # Hub con: verify qua JWKSCache (D-V3-Phase3-D).
    jwks_cache: JWKSCache | None = getattr(
        request.app.state, "jwks_cache", None
    )
    if jwks_cache is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "JWKS_CACHE_UNAVAILABLE",
                "message": "JWKSCache chưa init — hub con boot fail?",
            },
        )
    # ... extract kid + get_public_key + verify_token_with_key ...
```

**Current M2 `api_key.py:21-43`:**
```python
async def require_api_key(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "API_KEY_MISSING", "message": "Thiếu header X-API-Key"},
        )
    principal = await ApiKeyService(db=db).verify_key(x_api_key)
    if principal is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "API_KEY_INVALID",
                "message": "API key không hợp lệ hoặc đã thu hồi",
            },
        )
    return principal
```

**Adapt — Phase 6 branch:**
```python
async def require_api_key(
    request: Request,  # MỚI — cần app.state.api_key_verify_client cho hub con
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    if not x_api_key:
        raise HTTPException(...)  # giữ M2

    # Phase 6 Plan 06-XX SETTINGS-03 — branch verify path theo hub_name.
    from app.config import get_settings
    settings = get_settings()
    if settings.hub_name == "central":
        # Central: local ApiKeyService.verify_key (M2 carry forward).
        principal = await ApiKeyService(db=db).verify_key(x_api_key)
    else:
        # Hub con: proxy verify qua central HTTP + cache Redis TTL 60s.
        client = getattr(request.app.state, "api_key_verify_client", None)
        if client is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "code": "APIKEY_VERIFY_CLIENT_UNAVAILABLE",
                    "message": "ApiKeyVerifyClient chưa init — hub con boot fail?",
                },
            )
        principal = await client.verify(x_api_key)

    if principal is None:
        raise HTTPException(...)  # giữ M2 API_KEY_INVALID
    return principal
```

**Note:** Thêm `request: Request` parameter — caller (FastAPI Depends) auto-inject. Pattern song song `get_current_user` Phase 3 — signature mở rộng tương thích.

---

#### `api/app/auth/dependencies.py::require_internal_auth` (NEW dependency)

**Analog:** `api/app/auth/dependencies.py::require_role` (factory Callable pattern) + `hmac.compare_digest` constant-time compare

**Factory pattern** (`dependencies.py:251-294`):
```python
def require_role(
    *roles: str,
) -> Callable[[User], Awaitable[User]]:
    """AUTH-04 — gate endpoint chỉ cho role trong `roles` được pass."""
    if not roles:
        raise ValueError("require_role cần ít nhất 1 role")
    allowed = set(roles)

    async def _dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "FORBIDDEN",
                    "message": f"Không đủ quyền — yêu cầu một trong {sorted(allowed)}",
                },
            )
        return user

    return _dependency
```

**Adapt — `require_internal_auth` (NO factory, direct dependency):**
```python
async def require_internal_auth(
    x_internal_auth: str | None = Header(default=None, alias="X-Internal-Auth"),
) -> None:
    """Phase 6 Plan 06-XX SETTINGS-03 (D-V3-Phase6-D) — Internal-only endpoint gate.

    Verify header `X-Internal-Auth: <settings_proxy_secret>` constant-time
    compare. 401 INTERNAL_AUTH_FAIL nếu mismatch. Dùng cho POST /api/api-keys/verify
    (hub con call central proxy) — KHÔNG expose ra public internet (Caddy block
    qua /api/api-keys/verify route — defer Plan 05-01 carry forward review).

    Threat model:
    - T-06-04-01 Tampering — secret leak → attacker bypass. Constant-time compare
      hmac.compare_digest tránh timing attack (secret entropy 32 char ≥ 128 bit).
    - T-06-04-03 DoS rate limit — slowapi middleware 100 req/s per IP (defer
      Plan 06-XX rate_limit_internal_per_minute Settings field).
    """
    import hmac
    from app.config import get_settings

    settings = get_settings()
    expected = settings.settings_proxy_secret
    if not x_internal_auth or not hmac.compare_digest(x_internal_auth, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "INTERNAL_AUTH_FAIL",
                "message": "Internal auth header missing or invalid",
            },
        )
```

---

#### `api/app/routers/rag_config.py::update_rag_config` (EXTEND — publish after commit)

**Analog:** `api/app/services/search_cache.py::publish_invalidate` (lines 82-95) — best-effort fail-open Redis publish

**Pattern** (`search_cache.py:82-95`):
```python
async def publish_invalidate(redis: Any, hub_id: str) -> None:
    """Publish Pub/Sub channel `hub:{hub_id}:invalidate` — gọi sau document mutation.

    Best-effort fail-open — Redis None / down → log warning, KHÔNG raise
    (precedent fail-open: upload/delete vẫn thành công kể cả khi Redis chết —
    T-06-03-03).
    """
    if redis is None:
        return
    try:
        await redis.publish(invalidate_channel(hub_id), "1")
        logger.info("hub_invalidate_published: hub=%s", hub_id)
    except Exception as e:  # noqa: BLE001 — best-effort, KHÔNG raise
        logger.warning("hub_invalidate_publish_failed: hub=%s err=%s", hub_id, e)
```

**Current router** (`rag_config.py:48-60`):
```python
@router.put("", response_model=None)
async def update_rag_config(
    req: UpdateRagConfigRequest,
    user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_session),
) -> JSONResponse | dict[str, Any]:
    """PUT /api/rag-config — update + hot-swap provider/key, admin-only."""
    result = await RagConfigService(db=db).update_config(
        req=req, updated_by=user.id
    )
    if isinstance(result, str):
        return JSONResponse(status_code=400, content={"error": result})
    return result
```

**Adapt — Phase 6:**
```python
import json
import time

@router.put("", response_model=None)
async def update_rag_config(
    request: Request,  # MỚI — access app.state.redis
    req: UpdateRagConfigRequest,
    user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_session),
) -> JSONResponse | dict[str, Any]:
    """PUT /api/rag-config — update + hot-swap + Phase 6 publish pub/sub invalidate."""
    result = await RagConfigService(db=db).update_config(
        req=req, updated_by=user.id
    )
    if isinstance(result, str):
        return JSONResponse(status_code=400, content={"error": result})

    # Phase 6 Plan 06-XX SETTINGS-02 (D-V3-Phase6-C) — publish invalidate
    # best-effort fail-open (Redis None / down → log warning, KHÔNG block PUT).
    redis = getattr(request.app.state, "redis", None)
    if redis is not None:
        try:
            payload = json.dumps({
                "config_key": "rag_config",
                "hub": "*",  # broadcast all hub con
                "timestamp": int(time.time()),
            })
            await redis.publish("settings:invalidate", payload)
            logger.info("settings_invalidate_published: config_key=rag_config")
        except Exception as e:  # noqa: BLE001 — best-effort fail-open
            logger.warning("settings_invalidate_publish_failed: %s", e)

    return result
```

---

#### `api/app/routers/api_keys.py` (EXTEND — add `POST /api/api-keys/verify`)

**Analog:** `api/app/routers/api_keys.py::revoke_api_key` (lines 131-154 — POST handler existing pattern) + `require_internal_auth` dep mới Wave 3

**Pattern** (`api_keys.py:131-154`):
```python
@router.post("/{key_id}/revoke")
async def revoke_api_key(
    key_id: str,
    user: User = Depends(require_role("admin")),
    service: ApiKeyService = Depends(get_api_key_service),
) -> JSONResponse:
    """POST /api/api-keys/:id/revoke — soft revoke (is_active=FALSE — D-07)."""
    _ = user
    try:
        key_uuid = UUID(key_id)
    except ValueError:
        return resp.bad_request(...)
    ok = await service.revoke(key_id=key_uuid)
    if not ok:
        return resp.not_found(...)
    return resp.ok(data={"message": "API key đã thu hồi"})
```

**Adapt — `POST /api/api-keys/verify` endpoint mới:**
```python
from app.auth.dependencies import require_internal_auth
from app.schemas.api_keys import VerifyApiKeyRequest  # NEW schema {"api_key": str}

@router.post("/verify", response_model=None)
async def verify_api_key(
    req: VerifyApiKeyRequest,
    _internal: None = Depends(require_internal_auth),  # MỚI — internal-only gate
    service: ApiKeyService = Depends(get_api_key_service),
) -> dict[str, Any]:
    """POST /api/api-keys/verify — Internal proxy cho hub con verify X-API-Key.

    Phase 6 Plan 06-XX SETTINGS-03 (D-V3-Phase6-D). Body {"api_key": "mdk_..."}.
    Header X-Internal-Auth: <settings_proxy_secret> required (require_internal_auth dep).
    Trả `{valid: bool, principal: {id, permissions, allowed_hub_ids} | null}`.
    Central giữ AES-GCM at-rest M2 AUX-02 (KHÔNG đụng verify_key private logic).

    KHÔNG dùng resp envelope helper — hub con ApiKeyVerifyClient parse raw dict
    (pattern song song /api/rag-config raw dict — frontend Settings.tsx M2 deviation).
    """
    principal = await service.verify_key(req.api_key)
    if principal is None:
        return {"valid": False, "principal": None}
    return {"valid": True, "principal": principal}
```

**Conditional mount:** Endpoint chỉ available khi `settings.hub_name == "central"` qua existing `api_keys_router` central-only mount (FACTOR-02 Phase 2 carry forward — KHÔNG cần thay đổi `main.py` router include).

---

### Wave 4 — Lifespan integration (BLOCKING — depend Wave 1+2+3)

#### `api/app/main.py::lifespan` (EXTEND — thêm block hub con settings_sync)

**Analog 1:** `api/app/main.py:207-248` (Phase 3 Plan 03-02 — JWKSCache block: fail-loud boot + asyncio task spawn + shutdown graceful)

**JWKSCache lifespan block** (`main.py:207-248`):
```python
app.state.jwks_cache = None
if settings.hub_name != "central":
    if os.environ.get("JWKS_SKIP_FETCH") == "1":
        logger.warning(
            "jwks_cache_skipped: JWKS_SKIP_FETCH=1 (test mode — "
            "lifespan bypass blocking fetch_initial)"
        )
    else:
        from app.auth.jwks import JWKSCache

        if not settings.central_jwks_url:
            raise RuntimeError(
                f"hub_name={settings.hub_name!r} thiếu CENTRAL_JWKS_URL "
                "— Settings validator phải đã raise ở boot"
            )

        jwks_cache = JWKSCache(
            jwks_url=settings.central_jwks_url,
            refresh_interval=settings.jwks_refresh_interval,
            max_stale_seconds=settings.jwks_max_stale_seconds,
        )
        try:
            await jwks_cache.fetch_initial()  # blocking, raise on fail
        except Exception as e:
            logger.critical(
                "lifespan_jwks_cache_init_failed: hub_name=%s url=%s error=%s — boot abort",
                settings.hub_name, settings.central_jwks_url, e,
            )
            raise  # boot fail-loud D-V3-Phase3-B → uvicorn exit 1

        jwks_cache.start_refresh_task()
        app.state.jwks_cache = jwks_cache
        logger.info(
            "lifespan_jwks_cache_ready: hub_name=%s url=%s refresh_interval=%ds",
            settings.hub_name, settings.central_jwks_url, settings.jwks_refresh_interval,
        )
```

**Analog 2:** `api/app/main.py:380-392` (search_cache subscriber asyncio task spawn — universal mount) + `:441-449` (sync_worker_task hub con-only spawn)

**Subscriber spawn pattern** (`main.py:380-392`):
```python
# 9) Search cache invalidation subscriber (Phase 6 SEARCH-04 — D-12).
#    Lắng nghe Redis Pub/Sub hub:*:invalidate → xoá cache key của hub đó.
app.state.search_cache_task = None
if app.state.redis is not None:
    try:
        from app.services.search_cache import search_cache_subscriber

        app.state.search_cache_task = asyncio.create_task(
            search_cache_subscriber(app.state.redis)
        )
        logger.info("search_cache_subscriber_task_started")
    except Exception as e:  # noqa: BLE001
        logger.warning("search_cache_subscriber_start_failed: %s", e)
```

**Adapt — Phase 6 hub con block (gộp 3 client + 1 task):**
```python
# ──────────────────────────────────────────────────────────────────────
# Phase 6 Plan 06-XX (SETTINGS-01..04, D-V3-Phase6-A/B/C/D) — Hub con settings_sync
# ──────────────────────────────────────────────────────────────────────
# Hub con (settings.hub_name != "central") spawn 3 client + 1 subscriber task.
# - RagConfigClient.fetch_initial() blocking 5s (R-V3-6 LOW + D-V3-Phase6-A
#   fail-loud boot pattern song song JWKSCache Plan 03-02).
# - HubRegistryClient.fetch_initial() blocking 5s.
# - ApiKeyVerifyClient KHÔNG fetch_initial (lazy — verify on demand).
# - settings_subscriber_task asyncio.create_task spawn psubscribe settings:invalidate.
#
# Test-mode escape hatch: env `SETTINGS_SKIP_FETCH=1` bypass blocking fetch_initial
# (pattern song song COCOINDEX_SKIP_SETUP + JWKS_SKIP_FETCH + SYNC_SKIP_CENTRAL_POOL).
app.state.rag_config_client = None
app.state.hub_registry_client = None
app.state.api_key_verify_client = None
app.state.settings_subscriber_task = None

if settings.hub_name != "central":
    if os.environ.get("SETTINGS_SKIP_FETCH") == "1":
        logger.warning(
            "settings_sync_skipped: SETTINGS_SKIP_FETCH=1 (test mode)"
        )
    else:
        from app.settings_sync.client import (
            ApiKeyVerifyClient, HubRegistryClient, RagConfigClient,
        )
        from app.settings_sync.subscriber import settings_subscriber_loop

        rag_client = RagConfigClient(
            central_url=settings.central_url,
            redis=app.state.redis,
            hub_name=settings.hub_name,
            ttl=settings.settings_cache_ttl_rag_config,
        )
        hub_client = HubRegistryClient(
            central_url=settings.central_url,
            redis=app.state.redis,
            ttl=settings.settings_cache_ttl_hub_registry,
        )
        apikey_client = ApiKeyVerifyClient(
            central_url=settings.central_url,
            redis=app.state.redis,
            settings_proxy_secret=settings.settings_proxy_secret,
            hub_name=settings.hub_name,
            ttl=settings.settings_cache_ttl_apikey,
        )
        try:
            await rag_client.fetch_initial()  # blocking 5s, raise on fail
            await hub_client.fetch_initial()
        except Exception as e:
            logger.critical(
                "lifespan_settings_sync_init_failed: hub_name=%s err=%s — boot abort",
                settings.hub_name, e,
            )
            raise  # boot fail-loud D-V3-Phase6-A → uvicorn exit 1

        app.state.rag_config_client = rag_client
        app.state.hub_registry_client = hub_client
        app.state.api_key_verify_client = apikey_client

        # Spawn subscriber task (best-effort — fail-open per CONTEXT Claude's Discretion).
        if app.state.redis is not None:
            app.state.settings_subscriber_task = asyncio.create_task(
                settings_subscriber_loop(
                    redis=app.state.redis,
                    hub_name=settings.hub_name,
                    reconnect_seconds=settings.settings_subscriber_reconnect_seconds,
                )
            )
            logger.info("settings_subscriber_task_started: hub=%s", settings.hub_name)
        logger.info("lifespan_settings_sync_ready: hub=%s", settings.hub_name)
```

**Shutdown graceful** (carry forward Plan 03-02 + 04-04 pattern): sau `yield`, thêm:
```python
if app.state.settings_subscriber_task is not None:
    app.state.settings_subscriber_task.cancel()
    try:
        await asyncio.wait_for(app.state.settings_subscriber_task, timeout=10.0)
    except (asyncio.CancelledError, asyncio.TimeoutError):
        pass
    logger.info("settings_subscriber_task_stopped")
```

---

#### Integration tests `api/tests/integration/test_settings_sync_*.py`

**Analog:** `api/tests/integration/test_jwks_cache_lifecycle.py` (ASGI TestClient + lifespan mock httpx) + `test_sync_lifespan_integration.py` (mock asyncpg pool + state assert)

**Adapt 1-2 file:**
1. `test_settings_sync_lifespan_integration.py` — `LifespanManager(app_with_yte)` + `SETTINGS_SKIP_FETCH=1` escape hatch SKIP path; second pass mock httpx fetch return rag_config + hub_registry → assert `app.state.rag_config_client/hub_registry_client/api_key_verify_client` populated + `settings_subscriber_task` running.
2. `test_settings_sync_pubsub_e2e.py` (optional) — spawn central + yte qua 2 TestClient share Redis (testcontainer fakeredis pattern hoặc real Redis fixture); PUT `/api/rag-config` ở central → subscriber loop yte receive message → assert `app.state.redis` cache key `settings:rag_config:yte` đã DEL trong < 1s. Defer Phase 7 MIGRATE-05 full E2E nếu khó setup.

---

### Wave 5 — Closeout docs

**Analog:** Plan 03-05 (`03-05-PLAN.md`) + Plan 04-07 (`04-07-PLAN.md`) + Plan 05-06 (`05-06-PLAN.md`) — closeout pattern 5 doc file update + smoke checkpoint auto-fallback.

**Pattern (carry forward 3 plan):**
1. **`Hub_All/CLAUDE.md` §6 v3.0 progress row** — mark Phase 6 ✅ DONE + plan count + date 2026-05-23 + REQ-ID list `SETTINGS-01..04 (4)`. Thêm subsection mới `### Phase 6 System Settings Sync pattern (SETTINGS-01..04 — 2026-05-23)` 5-7 bullet point (carry forward Phase 4+5 subsection style).
2. **`Hub_All/.planning/STATE.md`** — frontmatter cập nhật `phases_completed`, `current_phase=7`. Thêm Phase 6 Results Summary block.
3. **`Hub_All/.planning/REQUIREMENTS.md`** — SETTINGS-01..04 mark `[x]`.
4. **`Hub_All/.planning/ROADMAP.md`** — Phase 6 row ✅ DONE 2026-05-23.
5. **`Hub_All/README.md`** — thêm section mới `"System Settings Sync Deploy Notes (Phase 6 v3.0)"` 5-step deploy + rollback procedure (carry forward Plan 03-05 SSO Backward Incompat section style + Plan 05-06 Reverse Proxy Subpath Deploy Notes).

**Smoke task auto-fallback** (CONTEXT.md `<specifics>`): Task closeout `checkpoint:human-action gate=blocking` auto-resolve `skip smoke` per v3.0-b precedent (Plan 03-05 + 04-07 + 05-06 pre-resolved skip pattern + `--auto --chain` mode active). Full E2E defer Phase 7 MIGRATE-05 runtime smoke (3 hub + central + golden path live).

---

## Shared Patterns

### Best-effort fail-open Redis publish (cross-cutting Wave 2 subscriber + Wave 3 rag_config publish)

**Source:** `api/app/services/search_cache.py::publish_invalidate` (lines 82-95) + `documents_service.py:139-141` `redis=None` default constructor

**Apply to:** `subscriber.py` reconnect logic + `routers/rag_config.py::update_rag_config` publish_invalidate call + future flush endpoint.

**Excerpt** (`search_cache.py:82-95`):
```python
async def publish_invalidate(redis: Any, hub_id: str) -> None:
    if redis is None:
        return
    try:
        await redis.publish(invalidate_channel(hub_id), "1")
        logger.info("hub_invalidate_published: hub=%s", hub_id)
    except Exception as e:  # noqa: BLE001 — best-effort, KHÔNG raise
        logger.warning("hub_invalidate_publish_failed: hub=%s err=%s", hub_id, e)
```

---

### Lifespan blocking fetch_initial + asyncio task spawn (Wave 4 integration)

**Source:** `api/app/main.py:207-248` (JWKSCache) + `:275-323` (central_sync_pool) + `:441-449` (sync_worker_task spawn)

**Apply to:** Phase 6 lifespan hub con block 3 client init + 1 subscriber task spawn + shutdown graceful task.cancel() + asyncio.wait_for(timeout=10.0).

**Pattern (carry forward):**
- Init `app.state.<X> = None` outside conditional → defensive default.
- `if settings.hub_name != "central":` block + `os.environ.get("<SKIP_FLAG>") == "1"` test escape hatch.
- `try: await client.fetch_initial()` (blocking 5s) → `except Exception as e: logger.critical(...) raise` (boot fail-loud).
- Spawn `asyncio.create_task(...)` SAU fetch_initial OK + log `<X>_task_started`.
- Shutdown: `task.cancel() + await asyncio.wait_for(task, timeout=10.0)` graceful.

---

### Settings field + model_validator hub con required (Wave 1)

**Source:** `api/app/config.py:325-345` (`_enforce_central_jwks_url_for_hub`) + `:347-375` (`_enforce_central_url_for_hub`) + `:394-440` (Phase 4 SYNC validators)

**Apply to:** Phase 6 `_enforce_settings_proxy_secret` validator (KHÁC: required BOTH central + hub con — KHÔNG branch hub_name).

**Pattern:**
```python
@model_validator(mode="after")
def _enforce_settings_proxy_secret(self) -> Settings:
    """Phase 6 SETTINGS-03 (D-V3-Phase6-D) — Shared secret required both sides.

    Central + hub con đều cần (central verify header; hub con gửi header).
    Length ≥ 32 char enforce 128-bit entropy (T-06-04-01 mitigation).
    """
    if len(self.settings_proxy_secret) < 32:
        raise ValueError(
            f"SETTINGS_PROXY_SECRET phải ≥ 32 char (entropy 128-bit). "
            f"Generate: openssl rand -hex 32. Phase 6 SETTINGS-03 D-V3-Phase6-D."
        )
    return self
```

---

### Prometheus collector module-level + label `hub_name` (W7 fix carry forward)

**Source:** `api/app/sync/metrics.py:32-114` (6 collector + `normalize_error_class` helper)

**Apply to:** Phase 6 `settings_sync/metrics.py` 6 collector mới — label `hub_name` + `key_type` bounded enum 3 value (rag_config|hub_registry|apikey).

**Pattern (excerpt above).**

---

### Test-mode escape hatch env flag (Wave 4 + integration test enablement)

**Source:** `api/app/main.py:159` (`COCOINDEX_SKIP_SETUP=1`) + `:209` (`JWKS_SKIP_FETCH=1`) + `:276` (`SYNC_SKIP_CENTRAL_POOL=1`)

**Apply to:** Phase 6 `SETTINGS_SKIP_FETCH=1` env flag bypass blocking fetch_initial cho integration test ASGI lifespan in-process (fake CENTRAL_URL OK).

**Pattern (carry forward):**
```python
if settings.hub_name != "central":
    if os.environ.get("SETTINGS_SKIP_FETCH") == "1":
        logger.warning("settings_sync_skipped: SETTINGS_SKIP_FETCH=1 (test mode)")
    else:
        # ... blocking fetch + asyncio task spawn ...
```

---

## No Analog Found

(empty)

Toàn bộ pattern Phase 6 carry forward được từ Phase 3 (JWKSCache lifecycle), Phase 4 (sync module + Prometheus metrics + Settings validator), M2 (`search_cache.py` pub/sub subscriber + `documents_service.py` fail-open publish + `api_key.py` X-API-Key dependency). KHÔNG có file nào ở Phase 6 chưa có analog trong codebase — minh chứng v3.0 milestone pattern consistency.

---

## Metadata

**Analog search scope:**
- `Hub_All/api/app/sync/` (5 file)
- `Hub_All/api/app/auth/{jwks,dependencies,api_key,jwt}.py`
- `Hub_All/api/app/routers/{rag_config,api_keys}.py`
- `Hub_All/api/app/services/{search_cache,documents_service,rag_config_service,api_key_service}.py`
- `Hub_All/api/app/{main,config}.py`
- `Hub_All/api/tests/unit/{test_sync_*,test_jwks_*,test_config_*}.py`
- `Hub_All/api/tests/integration/{test_sync_lifespan_integration,test_jwks_cache_lifecycle}.py`
- `Hub_All/docker-compose.yml` + `.env.example` + `docker-compose.override.yml.template`
- `Hub_All/.planning/phases/{02-05}/02-05-PLAN.md` + `03-02-PLAN.md` + `04-03-PLAN.md` + `04-04-PLAN.md`

**Files scanned:** ~35 file (read targeted ranges, non-overlapping).

**Pattern extraction date:** 2026-05-23

**Auto-chain active → next:** `gsd-planner` consume `06-PATTERNS.md` + `06-CONTEXT.md` → generate `06-{01..NN}-PLAN.md` theo Wave 1→5 sequencing.
