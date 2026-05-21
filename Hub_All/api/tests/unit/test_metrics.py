"""Unit tests cho `app.observability.metrics` + `PrometheusMiddleware` — HARD-02 Plan 10-02 Task 1.

Verify:
1. 5 metric instance module-level đúng tên + đúng type (Counter/Histogram) + đúng labelnames.
2. `REQUESTS_TOTAL.labels(...).inc()` rồi `generate_latest()` → output chứa
   `requests_total{method="GET",path="/healthz",status="200"} >= 1.0`.
3. `SEARCH_LATENCY.labels(hub_scope="single").time()` block sleep 10ms → histogram bucket le="0.025"
   tăng đúng 1 (rơi vào bucket 25ms).
4. PrometheusMiddleware mini Starlette app GET / 200 → REQUESTS_TOTAL tăng 1 + REQUEST_DURATION observe.
5. PrometheusMiddleware route 500 (raise HTTPException) → ERRORS_TOTAL + REQUESTS_TOTAL với status="500".
6. PrometheusMiddleware route 404 KHÔNG match → label path="unknown" (cardinality control).

Pattern: parse output `generate_latest(REGISTRY).decode()` regex tìm dòng metric + assert
delta (sau - trước) thay vì reset registry — module-level metric đăng ký vào default registry
KHÔNG dễ unregister giữa test.
"""
from __future__ import annotations

import re
import time

import pytest
from prometheus_client import REGISTRY, Counter, Histogram, generate_latest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from app.observability.metrics import (
    ERRORS_TOTAL,
    INGEST_DURATION,
    REQUEST_DURATION,
    REQUESTS_TOTAL,
    SEARCH_LATENCY,
)
from app.observability.middleware import PrometheusMiddleware


def _get_counter_value(metric_name: str, **labels: str) -> float:
    """Đọc giá trị Counter từ default REGISTRY qua regex parse generate_latest()."""
    output = generate_latest(REGISTRY).decode()
    label_pattern = ",".join(
        f'{k}="{re.escape(v)}"' for k, v in sorted(labels.items())
    )
    # Prometheus label order theo alphabet — match label set bất kỳ thứ tự.
    line_re = re.compile(
        rf"^{re.escape(metric_name)}\{{({label_pattern}|.*?)\}} (\d+\.\d+|\d+)$",
        re.MULTILINE,
    )
    best = 0.0
    for m in line_re.finditer(output):
        # Verify mọi label expected có trong line match.
        line_labels = m.group(1)
        if all(f'{k}="{v}"' in line_labels for k, v in labels.items()):
            best = max(best, float(m.group(2)))
    return best


def _get_histogram_bucket(metric_name: str, le: str, **labels: str) -> float:
    """Đọc bucket count của Histogram (`<name>_bucket{le="..."}`)."""
    output = generate_latest(REGISTRY).decode()
    bucket_metric = f"{metric_name}_bucket"
    for line in output.splitlines():
        if not line.startswith(bucket_metric):
            continue
        if f'le="{le}"' not in line:
            continue
        if not all(f'{k}="{v}"' in line for k, v in labels.items()):
            continue
        m = re.search(r"\}\s+(\d+\.\d+|\d+)$", line)
        if m:
            return float(m.group(1))
    return 0.0


@pytest.mark.critical
def test_metric_instances_have_correct_type_and_labelnames() -> None:
    """Test 1: 5 metric instance đúng tên + type + labelnames."""
    assert isinstance(REQUESTS_TOTAL, Counter)
    assert isinstance(ERRORS_TOTAL, Counter)
    assert isinstance(REQUEST_DURATION, Histogram)
    assert isinstance(SEARCH_LATENCY, Histogram)
    assert isinstance(INGEST_DURATION, Histogram)

    # Counter._name / Histogram._name = base name (không có suffix _total/_bucket).
    assert REQUESTS_TOTAL._name == "requests"  # prometheus_client tự append _total
    assert ERRORS_TOTAL._name == "errors"
    assert REQUEST_DURATION._name == "request_duration_seconds"
    assert SEARCH_LATENCY._name == "search_latency_seconds"
    assert INGEST_DURATION._name == "ingest_duration_seconds"

    assert REQUESTS_TOTAL._labelnames == ("method", "path", "status")
    assert ERRORS_TOTAL._labelnames == ("method", "path")
    assert REQUEST_DURATION._labelnames == ("method", "path")
    assert SEARCH_LATENCY._labelnames == ("hub_scope",)
    assert INGEST_DURATION._labelnames == ()


@pytest.mark.critical
def test_requests_total_inc_appears_in_generate_latest() -> None:
    """Test 2: REQUESTS_TOTAL inc 1 → output chứa expected line."""
    before = _get_counter_value(
        "requests_total", method="GET", path="/healthz", status="200"
    )
    REQUESTS_TOTAL.labels(method="GET", path="/healthz", status="200").inc()
    after = _get_counter_value(
        "requests_total", method="GET", path="/healthz", status="200"
    )
    assert after - before == pytest.approx(1.0, abs=1e-6)


def test_search_latency_time_observe_falls_in_25ms_bucket() -> None:
    """Test 3: SEARCH_LATENCY.time() block sleep 10ms → bucket le=0.025 tăng 1."""
    before = _get_histogram_bucket(
        "search_latency_seconds", le="0.025", hub_scope="single"
    )
    with SEARCH_LATENCY.labels(hub_scope="single").time():
        time.sleep(0.01)
    after = _get_histogram_bucket(
        "search_latency_seconds", le="0.025", hub_scope="single"
    )
    # 10ms quan sát rơi vào mọi bucket le >= 10ms — bucket le=0.025 tăng đúng 1.
    assert after - before == pytest.approx(1.0, abs=1e-6)


def _build_test_app() -> Starlette:
    """Mini Starlette app cho middleware test — 2 route 200 + 500."""

    async def ok_endpoint(_request: Request) -> PlainTextResponse:
        return PlainTextResponse("ok")

    async def fail_endpoint(_request: Request) -> JSONResponse:
        # Trả 500 trực tiếp (KHÔNG raise) — đo path status>=500 branch.
        return JSONResponse({"err": "boom"}, status_code=500)

    routes = [
        Route("/", ok_endpoint, methods=["GET"]),
        Route("/fail", fail_endpoint, methods=["GET"]),
    ]
    app = Starlette(routes=routes)
    app.add_middleware(PrometheusMiddleware)
    return app


@pytest.mark.critical
def test_middleware_request_200_increments_requests_total_and_observes_duration() -> None:
    """Test 4: GET / 200 → REQUESTS_TOTAL + REQUEST_DURATION tăng."""
    app = _build_test_app()
    before_req = _get_counter_value(
        "requests_total", method="GET", path="/", status="200"
    )
    before_dur_bucket = _get_histogram_bucket(
        "request_duration_seconds", le="+Inf", method="GET", path="/"
    )

    with TestClient(app) as client:
        resp = client.get("/")
    assert resp.status_code == 200

    after_req = _get_counter_value(
        "requests_total", method="GET", path="/", status="200"
    )
    after_dur_bucket = _get_histogram_bucket(
        "request_duration_seconds", le="+Inf", method="GET", path="/"
    )
    assert after_req - before_req == pytest.approx(1.0, abs=1e-6)
    assert after_dur_bucket - before_dur_bucket == pytest.approx(1.0, abs=1e-6)


def test_middleware_500_increments_errors_total() -> None:
    """Test 5: GET /fail 500 → ERRORS_TOTAL + REQUESTS_TOTAL với status=500."""
    app = _build_test_app()
    before_err = _get_counter_value(
        "errors_total", method="GET", path="/fail"
    )
    before_req = _get_counter_value(
        "requests_total", method="GET", path="/fail", status="500"
    )

    with TestClient(app) as client:
        resp = client.get("/fail")
    assert resp.status_code == 500

    after_err = _get_counter_value(
        "errors_total", method="GET", path="/fail"
    )
    after_req = _get_counter_value(
        "requests_total", method="GET", path="/fail", status="500"
    )
    assert after_err - before_err == pytest.approx(1.0, abs=1e-6)
    assert after_req - before_req == pytest.approx(1.0, abs=1e-6)


def test_middleware_unknown_path_uses_unknown_label() -> None:
    """Test 6: GET /not-exist 404 KHÔNG match → label path='unknown' (cardinality control)."""
    app = _build_test_app()
    before = _get_counter_value(
        "requests_total", method="GET", path="unknown", status="404"
    )
    with TestClient(app) as client:
        resp = client.get("/this-path-does-not-exist-cardinality-control")
    assert resp.status_code == 404

    after = _get_counter_value(
        "requests_total", method="GET", path="unknown", status="404"
    )
    assert after - before == pytest.approx(1.0, abs=1e-6)
