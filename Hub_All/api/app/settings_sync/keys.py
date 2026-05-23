"""Phase 6 Plan 06-01 settings_sync.keys — Redis channel + cache key constants + apikey hash helper.

Per D-V3-Phase6-C LOCKED: 1 channel `settings:invalidate` cho cả 3 category
(rag_config / hub_registry / apikey). Subscriber pattern
`redis.pubsub().subscribe(channel)` (KHÔNG psubscribe pattern — 1 channel cụ thể).

Per T-06-04-02 Information Disclosure mitigation: apikey cache key SHA-256 hex
prefix 16 char (KHÔNG plaintext trong Redis key/value). 64-bit collision space
đủ unique cho ~10^9 key (operator scale realistic).

Pattern carry forward:
- `api/app/sync/keys.py` (Phase 4 SQL constants module-level pattern).
- `api/app/services/search_cache.py:30-35` (M2 pub/sub channel + key prefix).
"""
from __future__ import annotations

import hashlib

#: Phase 6 Plan 06-01 SETTINGS-02 (D-V3-Phase6-C) — Pub/sub channel duy nhất
#: cho cả 3 category settings invalidate. Subscriber `redis.pubsub().subscribe(channel)`.
SETTINGS_INVALIDATE_CHANNEL: str = "settings:invalidate"

#: Phase 6 Plan 06-01 SETTINGS-01 — Cache key prefix per-hub rag_config (TTL 60s).
#: Key full = `settings:rag_config:<hub_name>`.
RAG_CONFIG_KEY_PREFIX: str = "settings:rag_config:"

#: Phase 6 Plan 06-01 SETTINGS-04 — Cache key hub_registry singleton (TTL 300s
#: rare-change FACTOR-04 `make hub-add`). KHÔNG per-hub (global config).
HUB_REGISTRY_KEY: str = "settings:hub_registry"

#: Phase 6 Plan 06-01 SETTINGS-03 — Cache key prefix apikey verify (TTL 60s,
#: T-06-04-02 hash). Key full = `apikey:verify:<sha256(api_key)[:16]>`.
APIKEY_VERIFY_KEY_PREFIX: str = "apikey:verify:"


def make_apikey_cache_key(api_key: str) -> str:
    """Compute SHA-256 hex prefix 16 char cache key — KHÔNG plaintext (T-06-04-02).

    Deterministic: same input → same output (cache hit detection). Hex prefix
    16 char (64-bit collision space) đủ unique cho realistic operator scale
    (~10^9 key). Full SHA-256 hex = 64 char nhưng trim [:16] tiết kiệm Redis
    key length (every byte count ở high-throughput).

    Args:
        api_key: Plaintext API key user gửi qua header `X-API-Key`
            (vd "mdk_abc123..."). Hub con compute hash trước khi lookup Redis;
            central verify_key qua AES-GCM decrypt M2 AUX-02 (KHÔNG đổi).

    Returns:
        Cache key string format `apikey:verify:<sha256(api_key)[:16]>`.

    Example:
        >>> make_apikey_cache_key("mdk_abc123").startswith("apikey:verify:")
        True
    """
    digest = hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:16]
    return f"{APIKEY_VERIFY_KEY_PREFIX}{digest}"


__all__ = [
    "APIKEY_VERIFY_KEY_PREFIX",
    "HUB_REGISTRY_KEY",
    "RAG_CONFIG_KEY_PREFIX",
    "SETTINGS_INVALIDATE_CHANNEL",
    "make_apikey_cache_key",
]
