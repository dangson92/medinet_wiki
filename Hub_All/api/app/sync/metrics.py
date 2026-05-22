"""Phase 4 Plan 04-03 Task 2 — 6 Prometheus collectors for cross-hub sync observability.

W7 fix (CR Iteration 1): label `hub_name` (NOT `hub_id`) — Prometheus label values là
hub_name string ("yte"/"duoc"/"hcns"/dynamic), KHÔNG UUID. Tách rõ semantic với
sync_outbox.chunk_id (UUID) + chunks.hub_id (UUID FK).

Cardinality control (T-04-03-01 mitigation):
- hub_name label = settings.hub_name (4-10 hub max → bounded).
- error_class label normalize (network/timeout/conflict/unknown — 4 class).
- drift_type label fixed (mismatch|missing).
- status label fixed (success|fail).

6 collectors:
- SYNC_LAG_SECONDS Histogram (outbox enqueue → central INSERT processed_at lag).
- SYNC_OUTBOX_PENDING Gauge (pending row count cho hub_name, worker set mỗi tick).
- SYNC_ATTEMPT_TOTAL Counter (push attempts, status=success|fail).
- SYNC_DEAD_TOTAL Counter (rows marked dead, error_class normalize).
- SYNC_COUNT_DRIFT Gauge (Plan 04-06 daily count drift ratio).
- SYNC_HASH_DRIFT Counter (Plan 04-06 hourly TABLESAMPLE BERNOULLI(1) hash mismatch).

Buckets choice SYNC_LAG_SECONDS: SLA Phase 4 — worker poll 5s + central RTT
~100ms; bucket 0.1s → 600s rộng phủ healthy (< 30s) → degraded (~300s) → broken
(> 600s) cho AlertManager dashboard.
"""
from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

# ────────────────────────────────────────────────────────────────────
# 1) SYNC_LAG_SECONDS Histogram — outbox enqueue → central processed_at
# ────────────────────────────────────────────────────────────────────
SYNC_LAG_SECONDS: Histogram = Histogram(
    "sync_lag_seconds",
    "Cross-hub sync latency: outbox.created_at → central INSERT processed_at",
    labelnames=("hub_name",),
    buckets=(0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0, 600.0),
)

# ────────────────────────────────────────────────────────────────────
# 2) SYNC_OUTBOX_PENDING Gauge — pending row count theo hub_name
# ────────────────────────────────────────────────────────────────────
SYNC_OUTBOX_PENDING: Gauge = Gauge(
    "sync_outbox_pending",
    "Số outbox rows pending hiện tại theo hub_name (worker poll mỗi tick set)",
    labelnames=("hub_name",),
)

# ────────────────────────────────────────────────────────────────────
# 3) SYNC_ATTEMPT_TOTAL Counter — push attempts success|fail
# ────────────────────────────────────────────────────────────────────
SYNC_ATTEMPT_TOTAL: Counter = Counter(
    "sync_attempt_total",
    "Cumulative push attempts (success/fail) — Plan 04-03 worker emit per row processed",
    labelnames=("hub_name", "status"),
)

# ────────────────────────────────────────────────────────────────────
# 4) SYNC_DEAD_TOTAL Counter — rows marked dead per error_class
# ────────────────────────────────────────────────────────────────────
SYNC_DEAD_TOTAL: Counter = Counter(
    "sync_dead_total",
    "Cumulative dead rows (attempt_count >= max_attempts) — per error class normalized",
    labelnames=("hub_name", "error_class"),
)

# ────────────────────────────────────────────────────────────────────
# 5) SYNC_COUNT_DRIFT Gauge — Plan 04-06 daily COUNT(*) ratio drift
# ────────────────────────────────────────────────────────────────────
SYNC_COUNT_DRIFT: Gauge = Gauge(
    "sync_count_drift",
    "COUNT(*) hub con vs central WHERE hub_id ratio (1.0 = perfect)",
    labelnames=("hub_name",),
)

# ────────────────────────────────────────────────────────────────────
# 6) SYNC_HASH_DRIFT Counter — Plan 04-06 hourly TABLESAMPLE hash mismatch
# ────────────────────────────────────────────────────────────────────
SYNC_HASH_DRIFT: Counter = Counter(
    "sync_hash_drift",
    "Cumulative hash mismatches từ Hourly TABLESAMPLE BERNOULLI(1) verify — Plan 04-06",
    labelnames=("hub_name", "drift_type"),
)


def normalize_error_class(exc: BaseException) -> str:
    """Normalize Exception type name → bounded label value (cardinality control).

    Class set: timeout|network|conflict|unknown (4 fixed labels).

    Decision: name-substring match thay vì isinstance check để cover:
    - asyncio.TimeoutError vs builtins.TimeoutError (Python 3.11+ same class)
    - asyncpg.exceptions.* network errors (ConnectionRefusedError, ConnectionDoesNotExistError)
    - asyncpg.exceptions.UniqueViolationError + IntegrityConstraintViolationError
    - Generic Exception → 'unknown'
    """
    name = type(exc).__name__.lower()
    if "timeout" in name:
        return "timeout"
    if "connection" in name or "network" in name or "socket" in name:
        return "network"
    if "unique" in name or "conflict" in name or "integrity" in name:
        return "conflict"
    return "unknown"


__all__ = [
    "SYNC_ATTEMPT_TOTAL",
    "SYNC_COUNT_DRIFT",
    "SYNC_DEAD_TOTAL",
    "SYNC_HASH_DRIFT",
    "SYNC_LAG_SECONDS",
    "SYNC_OUTBOX_PENDING",
    "normalize_error_class",
]
