"""Phase 6 Plan 06-01 settings_sync.metrics — 6 Prometheus collector module-level.

Per analog `api/app/sync/metrics.py` Phase 4 W7 fix: label `hub_name` (KHÔNG
`hub_id` UUID — cardinality bounded ~240 series cho 1 hub_name * 3 key_type *
80 worker máy hypothetical). `key_type` enum 3 value cố định (rag_config |
hub_registry | apikey) = bounded cardinality (T-06-01-03 mitigation Prometheus
cardinality blowup).

6 collector:
1. SETTINGS_CACHE_HIT_TOTAL Counter (hub_name, key_type) — Redis local cache hit (no HTTP).
2. SETTINGS_CACHE_MISS_TOTAL Counter (hub_name, key_type) — Redis miss → HTTP fetch.
3. SETTINGS_PULL_LATENCY_SECONDS Histogram (hub_name, endpoint) — httpx pull latency.
4. SETTINGS_INVALIDATE_RECEIVED_TOTAL Counter (hub_name, key_type) — pub/sub events.
5. SETTINGS_STALE_SECONDS Gauge (hub_name, key_type) — now - last_successful_pull_ts.
6. APIKEY_VERIFY_TOTAL Counter (hub_name, result) — verify dependency emit.

Buckets choice SETTINGS_PULL_LATENCY_SECONDS: httpx call ngắn hơn sync push
(Phase 4 0.1-600s rộng vì worker batch). Phase 6 fetch_initial timeout 5s,
refresh task timeout 10s → bucket 0.05-10s cover happy (< 0.5s) → degraded
(~2.5s) → timeout boundary (5s) → slow fail (10s).
"""
from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

# ────────────────────────────────────────────────────────────────────
# 1) SETTINGS_CACHE_HIT_TOTAL — Redis local cache served, no HTTP fetch
# ────────────────────────────────────────────────────────────────────
SETTINGS_CACHE_HIT_TOTAL: Counter = Counter(
    "settings_cache_hit_total",
    "Cumulative settings cache hits (Redis local cache served, no HTTP fetch).",
    labelnames=("hub_name", "key_type"),
)

# ────────────────────────────────────────────────────────────────────
# 2) SETTINGS_CACHE_MISS_TOTAL — Redis miss → HTTP fetch central
# ────────────────────────────────────────────────────────────────────
SETTINGS_CACHE_MISS_TOTAL: Counter = Counter(
    "settings_cache_miss_total",
    "Cumulative settings cache misses (Redis miss -> HTTP fetch central).",
    labelnames=("hub_name", "key_type"),
)

# ────────────────────────────────────────────────────────────────────
# 3) SETTINGS_PULL_LATENCY_SECONDS — httpx call hub con → central
# ────────────────────────────────────────────────────────────────────
SETTINGS_PULL_LATENCY_SECONDS: Histogram = Histogram(
    "settings_pull_latency_seconds",
    "HTTP pull latency (hub con httpx call -> central response).",
    labelnames=("hub_name", "endpoint"),
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

# ────────────────────────────────────────────────────────────────────
# 4) SETTINGS_INVALIDATE_RECEIVED_TOTAL — pub/sub events received
# ────────────────────────────────────────────────────────────────────
SETTINGS_INVALIDATE_RECEIVED_TOTAL: Counter = Counter(
    "settings_invalidate_received_total",
    "Cumulative pub/sub invalidate messages received (subscriber loop emit).",
    labelnames=("hub_name", "key_type"),
)

# ────────────────────────────────────────────────────────────────────
# 5) SETTINGS_STALE_SECONDS — time since last successful pull
# ────────────────────────────────────────────────────────────────────
SETTINGS_STALE_SECONDS: Gauge = Gauge(
    "settings_stale_seconds",
    "Time since last successful pull (now - last_successful_pull_ts).",
    labelnames=("hub_name", "key_type"),
)

# ────────────────────────────────────────────────────────────────────
# 6) APIKEY_VERIFY_TOTAL — verify dependency emit (require_api_key)
# ────────────────────────────────────────────────────────────────────
APIKEY_VERIFY_TOTAL: Counter = Counter(
    "apikey_verify_total",
    "Cumulative apikey verify calls (hub con require_api_key dependency emit).",
    labelnames=("hub_name", "result"),
)

__all__ = [
    "APIKEY_VERIFY_TOTAL",
    "SETTINGS_CACHE_HIT_TOTAL",
    "SETTINGS_CACHE_MISS_TOTAL",
    "SETTINGS_INVALIDATE_RECEIVED_TOTAL",
    "SETTINGS_PULL_LATENCY_SECONDS",
    "SETTINGS_STALE_SECONDS",
]
