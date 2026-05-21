"""Observability package — HARD-02 Plan 10-02 Prometheus metrics + middleware.

Re-export 5 metric instance module-level (Counter/Histogram đăng ký vào
default `prometheus_client.REGISTRY`) + `PrometheusMiddleware` để
`app/main.py` wire (innermost — add đầu tiên trước CORS).

Module-level metric: gọi `from app.observability import REQUESTS_TOTAL` từ
mọi nơi (service/middleware/router) — đều update CÙNG instance.
"""
from __future__ import annotations

from app.observability.metrics import (
    ERRORS_TOTAL,
    INGEST_DURATION,
    REQUEST_DURATION,
    REQUESTS_TOTAL,
    SEARCH_LATENCY,
)
from app.observability.middleware import PrometheusMiddleware

__all__ = [
    "ERRORS_TOTAL",
    "INGEST_DURATION",
    "REQUEST_DURATION",
    "REQUESTS_TOTAL",
    "SEARCH_LATENCY",
    "PrometheusMiddleware",
]
