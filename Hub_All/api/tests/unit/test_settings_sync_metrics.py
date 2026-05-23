"""Unit test Phase 6 Plan 06-01 Task 2 — settings_sync.metrics 6 Prometheus collector.

7 test case (per PLAN <behavior>):
1. SETTINGS_CACHE_HIT_TOTAL Counter label (hub_name, key_type).
2. SETTINGS_CACHE_MISS_TOTAL Counter labels same as HIT.
3. SETTINGS_PULL_LATENCY_SECONDS Histogram label (hub_name, endpoint) + buckets check.
4. SETTINGS_INVALIDATE_RECEIVED_TOTAL Counter label (hub_name, key_type).
5. SETTINGS_STALE_SECONDS Gauge label (hub_name, key_type).
6. APIKEY_VERIFY_TOTAL Counter label (hub_name, result).
7. key_type label bounded enum 3 value (rag_config|hub_registry|apikey) — verify `_labelnames`.

W7 fix carry forward: label `hub_name` (KHONG hub_id UUID — cardinality bounded
~240 series). `key_type` enum 3 value cố định = bounded cardinality (T-06-01-03
mitigation).

Pattern carry forward: test_sync_metrics.py::test_label_is_hub_name_not_hub_id
introspect `_labelnames` attribute.
"""
from __future__ import annotations


def test_settings_cache_hit_total_counter() -> None:
    """SETTINGS_CACHE_HIT_TOTAL Counter labels (hub_name, key_type)."""
    from prometheus_client import Counter

    from app.settings_sync.metrics import SETTINGS_CACHE_HIT_TOTAL

    assert isinstance(SETTINGS_CACHE_HIT_TOTAL, Counter)
    labels = set(SETTINGS_CACHE_HIT_TOTAL._labelnames)  # noqa: SLF001
    assert "hub_name" in labels
    assert "key_type" in labels
    # Functional check — labels(...).inc() works.
    SETTINGS_CACHE_HIT_TOTAL.labels(hub_name="yte", key_type="rag_config").inc()


def test_settings_cache_miss_total_counter() -> None:
    """SETTINGS_CACHE_MISS_TOTAL Counter labels (hub_name, key_type) same as HIT."""
    from prometheus_client import Counter

    from app.settings_sync.metrics import SETTINGS_CACHE_MISS_TOTAL

    assert isinstance(SETTINGS_CACHE_MISS_TOTAL, Counter)
    labels = set(SETTINGS_CACHE_MISS_TOTAL._labelnames)  # noqa: SLF001
    assert "hub_name" in labels
    assert "key_type" in labels
    SETTINGS_CACHE_MISS_TOTAL.labels(hub_name="yte", key_type="apikey").inc()


def test_settings_pull_latency_seconds_histogram() -> None:
    """SETTINGS_PULL_LATENCY_SECONDS Histogram label (hub_name, endpoint) + buckets.

    Buckets cover 0.05s (httpx fast central call) → 10s (slow central degraded).
    CONTEXT.md `<decisions>` Claude's Discretion fetch_initial timeout 5s.
    """
    from prometheus_client import Histogram

    from app.settings_sync.metrics import SETTINGS_PULL_LATENCY_SECONDS

    assert isinstance(SETTINGS_PULL_LATENCY_SECONDS, Histogram)
    labels = set(SETTINGS_PULL_LATENCY_SECONDS._labelnames)  # noqa: SLF001
    assert "hub_name" in labels
    assert "endpoint" in labels
    # Verify buckets include 0.05 (fast) + 5.0 (timeout boundary).
    upper_bounds = SETTINGS_PULL_LATENCY_SECONDS._upper_bounds  # noqa: SLF001
    assert 0.05 in upper_bounds
    assert 5.0 in upper_bounds
    SETTINGS_PULL_LATENCY_SECONDS.labels(
        hub_name="yte", endpoint="rag_config"
    ).observe(0.25)


def test_settings_invalidate_received_total_counter() -> None:
    """SETTINGS_INVALIDATE_RECEIVED_TOTAL Counter label (hub_name, key_type)."""
    from prometheus_client import Counter

    from app.settings_sync.metrics import SETTINGS_INVALIDATE_RECEIVED_TOTAL

    assert isinstance(SETTINGS_INVALIDATE_RECEIVED_TOTAL, Counter)
    labels = set(SETTINGS_INVALIDATE_RECEIVED_TOTAL._labelnames)  # noqa: SLF001
    assert "hub_name" in labels
    assert "key_type" in labels
    SETTINGS_INVALIDATE_RECEIVED_TOTAL.labels(
        hub_name="yte", key_type="rag_config"
    ).inc()


def test_settings_stale_seconds_gauge() -> None:
    """SETTINGS_STALE_SECONDS Gauge label (hub_name, key_type) — now - last_pull_ts."""
    from prometheus_client import Gauge

    from app.settings_sync.metrics import SETTINGS_STALE_SECONDS

    assert isinstance(SETTINGS_STALE_SECONDS, Gauge)
    labels = set(SETTINGS_STALE_SECONDS._labelnames)  # noqa: SLF001
    assert "hub_name" in labels
    assert "key_type" in labels
    SETTINGS_STALE_SECONDS.labels(hub_name="yte", key_type="rag_config").set(120)


def test_apikey_verify_total_counter() -> None:
    """APIKEY_VERIFY_TOTAL Counter label (hub_name, result).

    `result` label enum 3 value (valid|invalid|cached) — bounded cardinality.
    Emit per call require_api_key dependency (Wave 3 hub con).
    """
    from prometheus_client import Counter

    from app.settings_sync.metrics import APIKEY_VERIFY_TOTAL

    assert isinstance(APIKEY_VERIFY_TOTAL, Counter)
    labels = set(APIKEY_VERIFY_TOTAL._labelnames)  # noqa: SLF001
    assert "hub_name" in labels
    assert "result" in labels
    APIKEY_VERIFY_TOTAL.labels(hub_name="yte", result="valid").inc()
    APIKEY_VERIFY_TOTAL.labels(hub_name="yte", result="cached").inc()


def test_key_type_label_bounded_enum_3_values() -> None:
    """key_type label sample 3 enum value (rag_config|hub_registry|apikey) — bounded.

    T-06-01-03 mitigation cardinality blowup — `key_type` enum 3 value cố định
    (KHONG free-form). Verify 4 collector dùng pair (hub_name, key_type) accept
    inc với 3 enum value KHONG raise.
    """
    from app.settings_sync.metrics import (
        SETTINGS_CACHE_HIT_TOTAL,
        SETTINGS_CACHE_MISS_TOTAL,
        SETTINGS_INVALIDATE_RECEIVED_TOTAL,
        SETTINGS_STALE_SECONDS,
    )

    # 4 collector dùng pair (hub_name, key_type) — verify labels chứa key_type.
    for collector in [
        SETTINGS_CACHE_HIT_TOTAL,
        SETTINGS_CACHE_MISS_TOTAL,
        SETTINGS_INVALIDATE_RECEIVED_TOTAL,
        SETTINGS_STALE_SECONDS,
    ]:
        labels = set(collector._labelnames)  # noqa: SLF001
        assert "key_type" in labels, (
            f"{collector._name} thiếu label key_type — bounded cardinality required"  # noqa: SLF001
        )

    # Functional inc/set với 3 enum value — verify KHONG raise.
    for key_type in ("rag_config", "hub_registry", "apikey"):
        SETTINGS_CACHE_HIT_TOTAL.labels(hub_name="yte", key_type=key_type).inc()
        SETTINGS_CACHE_MISS_TOTAL.labels(hub_name="yte", key_type=key_type).inc()
        SETTINGS_INVALIDATE_RECEIVED_TOTAL.labels(
            hub_name="yte", key_type=key_type
        ).inc()
        SETTINGS_STALE_SECONDS.labels(hub_name="yte", key_type=key_type).set(0)
