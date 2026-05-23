"""Phase 6 settings_sync module — HTTP pull + Redis pub/sub invalidate (SETTINGS-01..04).

Module roadmap:
- Wave 1 ship (Plan 06-01): `keys.py` + `metrics.py` scaffold + Settings 5 field.
- Wave 2 ship (Plan 06-02): `client.py` (RagConfigClient + HubRegistryClient +
  ApiKeyVerifyClient — httpx async + Redis cache) + `subscriber.py`
  (settings_subscriber_loop asyncio task).
- Wave 3 ship (Plan 06-03): `require_api_key` refactor + `require_internal_auth`
  dependency + `/api/api-keys/verify` endpoint + rag_config publish invalidate.
- Wave 4 ship (Plan 06-04): lifespan integration (3 client init + subscriber task spawn).
- Wave 5 ship (Plan 06-05): closeout docs + smoke checkpoint.

Public API re-export:
- Wave 1 scope (Plan 06-01): keys constants + helper + 6 metrics.
- Wave 2 scope (Plan 06-02): client.py 3 HTTP client + SettingsUnavailableError.
  Subscriber + InvalidateMessage thêm ở Task 2 cùng plan.
"""
from __future__ import annotations

from app.settings_sync.client import (
    ApiKeyVerifyClient,
    HubRegistryClient,
    RagConfigClient,
    SettingsUnavailableError,
)
from app.settings_sync.keys import (
    APIKEY_VERIFY_KEY_PREFIX,
    HUB_REGISTRY_KEY,
    RAG_CONFIG_KEY_PREFIX,
    SETTINGS_INVALIDATE_CHANNEL,
    make_apikey_cache_key,
)
from app.settings_sync.metrics import (
    APIKEY_VERIFY_TOTAL,
    SETTINGS_CACHE_HIT_TOTAL,
    SETTINGS_CACHE_MISS_TOTAL,
    SETTINGS_INVALIDATE_RECEIVED_TOTAL,
    SETTINGS_PULL_LATENCY_SECONDS,
    SETTINGS_STALE_SECONDS,
)

__all__ = [
    "APIKEY_VERIFY_KEY_PREFIX",
    "APIKEY_VERIFY_TOTAL",
    "ApiKeyVerifyClient",
    "HUB_REGISTRY_KEY",
    "HubRegistryClient",
    "RAG_CONFIG_KEY_PREFIX",
    "RagConfigClient",
    "SETTINGS_CACHE_HIT_TOTAL",
    "SETTINGS_CACHE_MISS_TOTAL",
    "SETTINGS_INVALIDATE_CHANNEL",
    "SETTINGS_INVALIDATE_RECEIVED_TOTAL",
    "SETTINGS_PULL_LATENCY_SECONDS",
    "SETTINGS_STALE_SECONDS",
    "SettingsUnavailableError",
    "make_apikey_cache_key",
]
