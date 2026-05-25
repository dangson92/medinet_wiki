"""Phase 6 settings_sync — 3 HTTP client class cho hub con (D-V3-Phase6-A LOCKED).

- RagConfigClient: GET {central_url}/api/rag-config + Redis cache TTL 60s.
- HubRegistryClient: GET {central_url}/api/hubs + Redis cache TTL 300s.
- ApiKeyVerifyClient: POST {central_url}/api/api-keys/verify + Redis cache TTL 60s
  + header X-Internal-Auth=<settings_proxy_secret> (D-V3-Phase6-D).

Lifecycle song song Phase 3 JWKSCache (Plan 03-02 carry forward):
- fetch_initial(): blocking 5s — raise SettingsUnavailableError on fail
  (boot fail-loud R-V3-6 LOW mitigation; uvicorn exit 1).
- get/list_hubs/verify(): hot path — Redis cache hit > miss > HTTP fetch > Redis setex.

Threat model (per PLAN <threat_model>):
- T-06-02-01 Information Disclosure: apikey cache key hash (KHONG plaintext) qua
  make_apikey_cache_key (T-06-04-02 carry forward).
- T-06-02-02 DoS: fetch_initial timeout connect=2s/read=5s; refresh task timeout
  connect=5s/read=10s relax.
- T-06-02-03 Tampering: ApiKeyVerifyClient send X-Internal-Auth header secret
  (constant-time compare ở central — Plan 06-03 require_internal_auth dep).
- T-06-02-04 Information Disclosure: KHONG cache 401 negative response
  (return None + KHONG setex).

Pattern carry forward:
- `api/app/auth/jwks.py::JWKSCache` Plan 03-02 — fetch_initial blocking +
  background refresh + httpx.AsyncClient(timeout=...) context manager.
- `api/app/services/search_cache.py` M2 — Redis bytes decode pattern.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any

import httpx

from app.settings_sync.keys import (
    HUB_REGISTRY_KEY,
    RAG_CONFIG_KEY_PREFIX,
    make_apikey_cache_key,
)
from app.settings_sync.metrics import (
    APIKEY_VERIFY_TOTAL,
    SETTINGS_CACHE_HIT_TOTAL,
    SETTINGS_CACHE_MISS_TOTAL,
    SETTINGS_PULL_LATENCY_SECONDS,
    SETTINGS_STALE_SECONDS,
)

logger = logging.getLogger(__name__)

#: Boot fail-loud timeout — connect 2s + read 5s đủ cho httpx tới central
#: intra-network Docker DNS (~ms latency). Vượt → lifespan raise → uvicorn exit 1.
#: Pass `5.0` default (write/pool fallback) + override connect/read explicitly —
#: httpx.Timeout yêu cầu hoặc default hoặc cả 4 param (connect/read/write/pool).
_DEFAULT_TIMEOUT_INITIAL = httpx.Timeout(5.0, connect=2.0, read=5.0)

#: Refresh task / hot path timeout — connect 5s + read 10s relax cho background
#: refresh KHÔNG block request user (best-effort fail-quiet).
_DEFAULT_TIMEOUT_REFRESH = httpx.Timeout(10.0, connect=5.0, read=10.0)


class SettingsUnavailableError(RuntimeError):
    """Phase 6 SETTINGS-01 — fail-loud khi central down + Redis cache empty/expired.

    Raised qua RagConfigClient.get() + HubRegistryClient.list_hubs() khi:
    1. Redis cache miss (TTL expire HOẶC chưa fetch_initial).
    2. httpx fetch central fail (timeout / 5xx / connection error).

    ErrorHandlerMiddleware wrap thành 503 envelope code=SETTINGS_UNAVAILABLE
    (Plan 06-03 router consume — Wave 3).
    """


def _decode_cached(value: Any) -> Any:
    """Decode Redis cached value (bytes hoặc str) → JSON object.

    Redis client `decode_responses=True` (M2 main.py setup) → str; nhưng support
    cả raw bytes fallback (test fixture có thể return bytes).
    """
    if isinstance(value, bytes):
        return json.loads(value.decode("utf-8"))
    return json.loads(value)


class RagConfigClient:
    """SETTINGS-01 — fetch rag_config từ central + cache Redis TTL 60s.

    Cache key per-hub: `settings:rag_config:<hub_name>` (RAG_CONFIG_KEY_PREFIX
    Plan 06-01). TTL default 60s (D-V3-Phase6-B LOCKED — pub/sub PRIMARY <30s
    propagate, TTL FALLBACK Redis down recovery).

    Hot path `get()`: Redis hit > miss → fetch + setex + Prometheus emit.
    Boot path `fetch_initial()`: blocking 5s → SettingsUnavailableError on fail.
    """

    def __init__(
        self,
        *,
        central_url: str,
        redis: Any,
        hub_name: str,
        ttl: int = 60,
    ) -> None:
        self._central_url = central_url.rstrip("/")
        self._redis = redis
        self._hub_name = hub_name
        self._ttl = ttl
        self._cache_key = f"{RAG_CONFIG_KEY_PREFIX}{hub_name}"
        self._endpoint = "/api/rag-config"
        self._last_pull_ts: float = 0.0

    async def fetch_initial(self) -> None:
        """Blocking fetch — raise SettingsUnavailableError on fail (boot fail-loud).

        D-V3-Phase6-A boot fail-loud: hub con boot KHÔNG kết nối được central
        → lifespan raise → uvicorn exit 1 (operator catch boot error rõ ràng).
        """
        try:
            await self._fetch_and_cache(timeout=_DEFAULT_TIMEOUT_INITIAL)
        except Exception as e:
            logger.critical(
                "rag_config_client_fetch_initial_failed: hub=%s url=%s%s err=%s",
                self._hub_name,
                self._central_url,
                self._endpoint,
                e,
            )
            raise SettingsUnavailableError(
                f"RagConfigClient fetch_initial failed: {e}"
            ) from e

    async def get(self) -> dict[str, Any]:
        """Hot path — Redis cache hit > miss > HTTP fetch > Redis setex."""
        if self._redis is not None:
            cached = await self._redis.get(self._cache_key)
            if cached is not None:
                SETTINGS_CACHE_HIT_TOTAL.labels(
                    hub_name=self._hub_name, key_type="rag_config"
                ).inc()
                return _decode_cached(cached)  # type: ignore[no-any-return]
        # Cache miss — fetch + cache
        SETTINGS_CACHE_MISS_TOTAL.labels(
            hub_name=self._hub_name, key_type="rag_config"
        ).inc()
        try:
            data = await self._fetch_and_cache(timeout=_DEFAULT_TIMEOUT_REFRESH)
        except Exception as e:
            raise SettingsUnavailableError(
                f"RagConfigClient.get failed: {e}"
            ) from e
        return data

    async def _fetch_and_cache(self, *, timeout: httpx.Timeout) -> dict[str, Any]:
        """Internal — httpx GET + raise_for_status + setex + emit metric."""
        start = time.monotonic()
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(f"{self._central_url}{self._endpoint}")
            resp.raise_for_status()
            data = resp.json()
        latency = time.monotonic() - start
        SETTINGS_PULL_LATENCY_SECONDS.labels(
            hub_name=self._hub_name, endpoint=self._endpoint
        ).observe(latency)
        if self._redis is not None:
            await self._redis.setex(
                self._cache_key, self._ttl, json.dumps(data)
            )
        self._last_pull_ts = time.time()
        SETTINGS_STALE_SECONDS.labels(
            hub_name=self._hub_name, key_type="rag_config"
        ).set(0)
        return data  # type: ignore[no-any-return]


class HubRegistryClient:
    """SETTINGS-04 — fetch hub_registry từ central + cache Redis TTL 300s.

    Singleton cache key `settings:hub_registry` (HUB_REGISTRY_KEY Plan 06-01)
    — KHÔNG per-hub vì hub_registry là global config (operator add hub qua
    `make hub-add` rare-change). TTL 300s (5 phút) D-V3-Phase6-B LOCKED.

    Hot-fix 2026-05-25: gửi header `X-Internal-Auth: <settings_proxy_secret>`
    để central authenticate request internal (Plan 06-03 pattern). Trước hot-fix,
    HubRegistryClient gọi `GET /api/hubs` KHÔNG header → central trả 401 (endpoint
    yêu cầu JWT/X-API-Key) → hub-con boot fail-loud. Central /api/hubs giờ accept
    X-Internal-Auth alternative qua dep `get_internal_auth_or_jwt_or_apikey`.
    """

    def __init__(
        self,
        *,
        central_url: str,
        redis: Any,
        hub_name: str,
        internal_auth_secret: str,
        ttl: int = 300,
    ) -> None:
        self._central_url = central_url.rstrip("/")
        self._redis = redis
        self._hub_name = hub_name
        self._internal_auth_secret = internal_auth_secret
        self._ttl = ttl
        self._cache_key = HUB_REGISTRY_KEY  # singleton, KHÔNG per-hub
        # Hot-fix 2026-05-25: dùng endpoint internal-only `/api/hubs/_internal`
        # (Plan 06-03 pattern). Endpoint cũ `/api/hubs` yêu cầu JWT/X-API-Key →
        # hub-con boot fail-loud 401. Internal endpoint gate qua require_internal_auth
        # + trả raw list (KHÔNG envelope unwrap cần thiết — defensive vẫn handle).
        self._endpoint = "/api/hubs/_internal"

    async def fetch_initial(self) -> None:
        """Blocking fetch — raise SettingsUnavailableError on fail (boot fail-loud)."""
        try:
            await self._fetch_and_cache(timeout=_DEFAULT_TIMEOUT_INITIAL)
        except Exception as e:
            logger.critical(
                "hub_registry_client_fetch_initial_failed: hub=%s err=%s",
                self._hub_name,
                e,
            )
            raise SettingsUnavailableError(
                f"HubRegistryClient fetch_initial failed: {e}"
            ) from e

    async def list_hubs(self) -> list[dict[str, Any]]:
        """Hot path — Redis cache hit > miss > HTTP fetch > Redis setex."""
        if self._redis is not None:
            cached = await self._redis.get(self._cache_key)
            if cached is not None:
                SETTINGS_CACHE_HIT_TOTAL.labels(
                    hub_name=self._hub_name, key_type="hub_registry"
                ).inc()
                return _decode_cached(cached)  # type: ignore[no-any-return]
        SETTINGS_CACHE_MISS_TOTAL.labels(
            hub_name=self._hub_name, key_type="hub_registry"
        ).inc()
        try:
            data = await self._fetch_and_cache(timeout=_DEFAULT_TIMEOUT_REFRESH)
        except Exception as e:
            raise SettingsUnavailableError(
                f"HubRegistryClient.list_hubs failed: {e}"
            ) from e
        return data

    async def _fetch_and_cache(
        self, *, timeout: httpx.Timeout
    ) -> list[dict[str, Any]]:
        start = time.monotonic()
        # Hot-fix 2026-05-25: gửi X-Internal-Auth header để central authenticate.
        # /api/hubs trả envelope `{success, data: [items], meta}` (resp.paginated)
        # — unwrap `data` field; fallback raw nếu shape khác (legacy/test mock).
        headers = {"X-Internal-Auth": self._internal_auth_secret}
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(
                f"{self._central_url}{self._endpoint}", headers=headers
            )
            resp.raise_for_status()
            raw = resp.json()
        data = raw["data"] if isinstance(raw, dict) and "data" in raw else raw
        latency = time.monotonic() - start
        SETTINGS_PULL_LATENCY_SECONDS.labels(
            hub_name=self._hub_name, endpoint=self._endpoint
        ).observe(latency)
        if self._redis is not None:
            await self._redis.setex(
                self._cache_key, self._ttl, json.dumps(data)
            )
        SETTINGS_STALE_SECONDS.labels(
            hub_name=self._hub_name, key_type="hub_registry"
        ).set(0)
        return data  # type: ignore[no-any-return]


class ApiKeyVerifyClient:
    """SETTINGS-03 — proxy verify X-API-Key qua central + cache Redis TTL 60s.

    Cache key hash SHA-256 prefix 16 char (T-06-04-02 — KHÔNG plaintext qua
    `make_apikey_cache_key()` helper Plan 06-01).
    KHÔNG cache negative response (401) — Claude's Discretion (T-06-02-04).

    Pattern:
    - Cache hit → return cached principal + emit `result=cached`.
    - Cache miss → POST central với header X-Internal-Auth → 200 valid
      → setex + emit `result=valid` + return principal; 401 → None + emit
      `result=invalid` + KHÔNG setex.
    """

    def __init__(
        self,
        *,
        central_url: str,
        redis: Any,
        hub_name: str,
        settings_proxy_secret: str,
        ttl: int = 60,
    ) -> None:
        self._central_url = central_url.rstrip("/")
        self._redis = redis
        self._hub_name = hub_name
        self._secret = settings_proxy_secret
        self._ttl = ttl
        self._endpoint = "/api/api-keys/verify"

    async def verify(self, api_key: str) -> dict[str, Any] | None:
        """Verify plaintext X-API-Key → principal dict hoặc None.

        Flow:
        1. Compute cache key SHA-256 hex prefix 16 char (T-06-04-02 hash).
        2. Redis hit → return cached principal + APIKEY_VERIFY_TOTAL{cached}.
        3. Miss → POST central với X-Internal-Auth header → 200 + valid:true
           → setex positive + APIKEY_VERIFY_TOTAL{valid}; 401 → None +
           APIKEY_VERIFY_TOTAL{invalid} (KHÔNG setex T-06-02-04).
        4. HTTP error / 5xx → None + APIKEY_VERIFY_TOTAL{invalid} (fail-quiet).
        """
        cache_key = make_apikey_cache_key(api_key)
        # Cache hit check
        if self._redis is not None:
            cached = await self._redis.get(cache_key)
            if cached is not None:
                APIKEY_VERIFY_TOTAL.labels(
                    hub_name=self._hub_name, result="cached"
                ).inc()
                return _decode_cached(cached)  # type: ignore[no-any-return]
        # HTTP fetch
        start = time.monotonic()
        try:
            async with httpx.AsyncClient(
                timeout=_DEFAULT_TIMEOUT_REFRESH
            ) as client:
                resp = await client.post(
                    f"{self._central_url}{self._endpoint}",
                    json={"api_key": api_key},
                    headers={"X-Internal-Auth": self._secret},
                )
        except Exception as e:
            logger.warning(
                "apikey_verify_client_http_error: hub=%s err=%s",
                self._hub_name,
                e,
            )
            APIKEY_VERIFY_TOTAL.labels(
                hub_name=self._hub_name, result="invalid"
            ).inc()
            return None
        latency = time.monotonic() - start
        SETTINGS_PULL_LATENCY_SECONDS.labels(
            hub_name=self._hub_name, endpoint=self._endpoint
        ).observe(latency)

        if resp.status_code == 401:
            APIKEY_VERIFY_TOTAL.labels(
                hub_name=self._hub_name, result="invalid"
            ).inc()
            return None  # KHÔNG cache negative (T-06-02-04)
        if resp.status_code != 200:
            logger.warning(
                "apikey_verify_client_unexpected_status: hub=%s status=%d",
                self._hub_name,
                resp.status_code,
            )
            APIKEY_VERIFY_TOTAL.labels(
                hub_name=self._hub_name, result="invalid"
            ).inc()
            return None

        data = resp.json()
        principal = data.get("principal") if data.get("valid") else None
        if principal is None:
            APIKEY_VERIFY_TOTAL.labels(
                hub_name=self._hub_name, result="invalid"
            ).inc()
            return None
        # Cache positive only (T-06-02-04 — KHÔNG cache negative)
        if self._redis is not None:
            await self._redis.setex(
                cache_key, self._ttl, json.dumps(principal)
            )
        APIKEY_VERIFY_TOTAL.labels(
            hub_name=self._hub_name, result="valid"
        ).inc()
        return principal  # type: ignore[no-any-return]


__all__ = [
    "ApiKeyVerifyClient",
    "HubRegistryClient",
    "RagConfigClient",
    "SettingsUnavailableError",
]
