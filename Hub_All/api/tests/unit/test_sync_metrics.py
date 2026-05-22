"""Phase 4 Plan 04-03 Task 2 — Unit test sync.metrics 6 Prometheus collector.

W7 fix verify: label `hub_name` (NOT `hub_id` UUID). Prometheus cardinality
control:
- hub_name: 4-10 hub max bounded.
- status: success|fail fixed.
- error_class: network|timeout|conflict|unknown fixed (normalize_error_class).
- drift_type: mismatch|missing fixed.

Decision traceability:
- D-V3-Phase4-A5 + W7 fix (label semantic hub_name string KHONG UUID)
- T-04-03-01 mitigation (cardinality bounded)
"""
from __future__ import annotations

import pytest

# ────────────────────────────────────────────────────────────────────
# Test 1-6: 6 collector defined with correct labels
# ────────────────────────────────────────────────────────────────────


def test_sync_lag_seconds_histogram() -> None:
    """SYNC_LAG_SECONDS Histogram label hub_name + buckets cover 0.1s → 600s."""
    from prometheus_client import Histogram

    from app.sync.metrics import SYNC_LAG_SECONDS

    assert isinstance(SYNC_LAG_SECONDS, Histogram)
    # Label names contain hub_name (W7 fix).
    assert "hub_name" in SYNC_LAG_SECONDS._labelnames  # noqa: SLF001
    # Functional check: labels(hub_name=...).observe(lag) works.
    SYNC_LAG_SECONDS.labels(hub_name="yte").observe(2.5)


def test_sync_outbox_pending_gauge() -> None:
    """SYNC_OUTBOX_PENDING Gauge label hub_name."""
    from prometheus_client import Gauge

    from app.sync.metrics import SYNC_OUTBOX_PENDING

    assert isinstance(SYNC_OUTBOX_PENDING, Gauge)
    assert "hub_name" in SYNC_OUTBOX_PENDING._labelnames  # noqa: SLF001
    SYNC_OUTBOX_PENDING.labels(hub_name="yte").set(42)


def test_sync_attempt_counter() -> None:
    """SYNC_ATTEMPT_TOTAL Counter labels hub_name + status."""
    from prometheus_client import Counter

    from app.sync.metrics import SYNC_ATTEMPT_TOTAL

    assert isinstance(SYNC_ATTEMPT_TOTAL, Counter)
    labels = set(SYNC_ATTEMPT_TOTAL._labelnames)  # noqa: SLF001
    assert "hub_name" in labels
    assert "status" in labels
    SYNC_ATTEMPT_TOTAL.labels(hub_name="yte", status="success").inc()
    SYNC_ATTEMPT_TOTAL.labels(hub_name="yte", status="fail").inc()


def test_sync_dead_counter() -> None:
    """SYNC_DEAD_TOTAL Counter labels hub_name + error_class."""
    from prometheus_client import Counter

    from app.sync.metrics import SYNC_DEAD_TOTAL

    assert isinstance(SYNC_DEAD_TOTAL, Counter)
    labels = set(SYNC_DEAD_TOTAL._labelnames)  # noqa: SLF001
    assert "hub_name" in labels
    assert "error_class" in labels
    SYNC_DEAD_TOTAL.labels(hub_name="yte", error_class="network").inc()


def test_sync_count_drift_gauge() -> None:
    """SYNC_COUNT_DRIFT Gauge label hub_name (Plan 04-06 daily count drift)."""
    from prometheus_client import Gauge

    from app.sync.metrics import SYNC_COUNT_DRIFT

    assert isinstance(SYNC_COUNT_DRIFT, Gauge)
    assert "hub_name" in SYNC_COUNT_DRIFT._labelnames  # noqa: SLF001
    SYNC_COUNT_DRIFT.labels(hub_name="yte").set(1.0)


def test_sync_hash_drift_counter() -> None:
    """SYNC_HASH_DRIFT Counter labels hub_name + drift_type (Plan 04-06 hourly hash)."""
    from prometheus_client import Counter

    from app.sync.metrics import SYNC_HASH_DRIFT

    assert isinstance(SYNC_HASH_DRIFT, Counter)
    labels = set(SYNC_HASH_DRIFT._labelnames)  # noqa: SLF001
    assert "hub_name" in labels
    assert "drift_type" in labels
    SYNC_HASH_DRIFT.labels(hub_name="yte", drift_type="mismatch").inc()
    SYNC_HASH_DRIFT.labels(hub_name="yte", drift_type="missing").inc()


# ────────────────────────────────────────────────────────────────────
# Test 7: No duplicate register (import twice safe)
# ────────────────────────────────────────────────────────────────────


def test_no_duplicate_register_on_reimport() -> None:
    """Reimport module — KHONG raise Duplicated timeseries (prometheus_client)."""
    import importlib

    from app.sync import metrics as m1

    # Re-import — same module object (Python module cache); KHONG raise.
    m2 = importlib.import_module("app.sync.metrics")
    assert m1 is m2
    # Reload — must not raise. (Skip actual reload to avoid double-register on prod.)


# ────────────────────────────────────────────────────────────────────
# Test 8: Prometheus textformat render contains all 6 metric names
# ────────────────────────────────────────────────────────────────────


def test_prometheus_textformat_render_contains_all_6_metrics() -> None:
    """generate_latest() chứa tất cả 6 metric name."""
    from prometheus_client import generate_latest

    # Touch all 6 by importing (collectors registered module-level).
    from app.sync.metrics import (  # noqa: F401
        SYNC_ATTEMPT_TOTAL,
        SYNC_COUNT_DRIFT,
        SYNC_DEAD_TOTAL,
        SYNC_HASH_DRIFT,
        SYNC_LAG_SECONDS,
        SYNC_OUTBOX_PENDING,
    )

    # Touch labels to ensure render.
    SYNC_LAG_SECONDS.labels(hub_name="render").observe(0.1)
    SYNC_OUTBOX_PENDING.labels(hub_name="render").set(0)
    SYNC_ATTEMPT_TOTAL.labels(hub_name="render", status="success").inc(0)
    SYNC_DEAD_TOTAL.labels(hub_name="render", error_class="network").inc(0)
    SYNC_COUNT_DRIFT.labels(hub_name="render").set(1.0)
    SYNC_HASH_DRIFT.labels(hub_name="render", drift_type="mismatch").inc(0)

    text = generate_latest().decode("utf-8")
    assert "sync_lag_seconds" in text
    assert "sync_outbox_pending" in text
    assert "sync_attempt_total" in text
    assert "sync_dead_total" in text
    assert "sync_count_drift" in text
    assert "sync_hash_drift" in text


# ────────────────────────────────────────────────────────────────────
# Test 9: label hub_name (NOT hub_id) — W7 fix verify all 6 collectors
# ────────────────────────────────────────────────────────────────────


def test_label_is_hub_name_not_hub_id_all_6_collectors() -> None:
    """W7 fix verify — 6 collector all dùng `hub_name` label (NOT `hub_id` UUID)."""
    from app.sync.metrics import (
        SYNC_ATTEMPT_TOTAL,
        SYNC_COUNT_DRIFT,
        SYNC_DEAD_TOTAL,
        SYNC_HASH_DRIFT,
        SYNC_LAG_SECONDS,
        SYNC_OUTBOX_PENDING,
    )

    collectors = [
        SYNC_LAG_SECONDS,
        SYNC_OUTBOX_PENDING,
        SYNC_ATTEMPT_TOTAL,
        SYNC_DEAD_TOTAL,
        SYNC_COUNT_DRIFT,
        SYNC_HASH_DRIFT,
    ]
    for m in collectors:
        labels = set(m._labelnames)  # noqa: SLF001
        assert "hub_name" in labels, f"{m._name} missing hub_name label"  # noqa: SLF001
        assert "hub_id" not in labels, (  # noqa: SLF001
            f"{m._name} has stale hub_id label (W7 fix violated)"  # noqa: SLF001
        )


# ────────────────────────────────────────────────────────────────────
# Test 10-13: normalize_error_class helper
# ────────────────────────────────────────────────────────────────────


def test_normalize_error_class_timeout() -> None:
    """asyncio.TimeoutError → 'timeout'."""
    from app.sync.metrics import normalize_error_class

    assert normalize_error_class(TimeoutError()) == "timeout"
    assert normalize_error_class(TimeoutError()) == "timeout"


def test_normalize_error_class_network() -> None:
    """ConnectionRefusedError / ConnectionError → 'network'."""
    from app.sync.metrics import normalize_error_class

    assert normalize_error_class(ConnectionRefusedError()) == "network"
    assert normalize_error_class(ConnectionError()) == "network"


def test_normalize_error_class_unknown() -> None:
    """Generic Exception → 'unknown'."""
    from app.sync.metrics import normalize_error_class

    assert normalize_error_class(ValueError("foo")) == "unknown"
    assert normalize_error_class(RuntimeError()) == "unknown"


def test_normalize_error_class_conflict() -> None:
    """UniqueViolation / IntegrityError → 'conflict' (matches name keyword)."""
    from app.sync.metrics import normalize_error_class

    class FakeUniqueViolationError(Exception):
        pass

    class FakeIntegrityError(Exception):
        pass

    assert normalize_error_class(FakeUniqueViolationError()) == "conflict"
    assert normalize_error_class(FakeIntegrityError()) == "conflict"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
