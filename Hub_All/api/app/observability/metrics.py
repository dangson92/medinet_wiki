"""Prometheus metric instances cho HARD-02 — module-level singletons.

5 metric đăng ký vào default `prometheus_client.REGISTRY`:

- `REQUESTS_TOTAL` (Counter, label `method/path/status`) — đếm mọi request hoàn tất.
- `ERRORS_TOTAL` (Counter, label `method/path`) — đếm request status >= 500.
- `REQUEST_DURATION` (Histogram, label `method/path`) — đo latency request end-to-end.
- `SEARCH_LATENCY` (Histogram, label `hub_scope` ∈ {single, cross}) — đo
  `search_service.search()` + `search_service.search_cross_hub()`.
- `INGEST_DURATION` (Histogram, KHÔNG label per-doc — cardinality blowup) — đo
  `cocoindex_app.update_blocking()` mỗi document trigger qua FastAPI BackgroundTask.

Cardinality control: label `path` dùng route template (`/api/documents/{document_id}`)
thay vì URL thật (`/api/documents/abc-123`) — set hữu hạn O(routes) thay vì O(unique URLs).
404 / route không match → fallback `"unknown"` (xem `middleware._resolve_path`).

Buckets: tuned theo SLA Phase 6/4:
- `request_duration_seconds`: 5ms → 10s (rộng phủ healthz tới upload chậm).
- `search_latency_seconds`: 50ms → 5s (SC2 800ms target nằm giữa).
- `ingest_duration_seconds`: 0.5s → 120s (DOCX 50 trang có thể chục giây).
"""
from __future__ import annotations

from prometheus_client import Counter, Histogram

#: HTTP request total — mỗi request hoàn tất (kể cả 4xx/5xx) tăng 1.
REQUESTS_TOTAL: Counter = Counter(
    "requests_total",
    "Total HTTP requests by method/path/status",
    ["method", "path", "status"],
)

#: HTTP error total — chỉ request status >= 500 (KHÔNG đếm 4xx).
ERRORS_TOTAL: Counter = Counter(
    "errors_total",
    "Total HTTP requests with status >= 500",
    ["method", "path"],
)

#: HTTP request duration histogram — end-to-end (đo trong PrometheusMiddleware).
REQUEST_DURATION: Histogram = Histogram(
    "request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "path"],
    buckets=(
        0.005,
        0.01,
        0.025,
        0.05,
        0.1,
        0.25,
        0.5,
        1.0,
        2.5,
        5.0,
        10.0,
    ),
)

#: Search latency histogram — `hub_scope` ∈ {"single", "cross"} (cardinality 2).
#: KHÔNG label per-query hoặc per-hub (cardinality blowup).
SEARCH_LATENCY: Histogram = Histogram(
    "search_latency_seconds",
    "Search request latency in seconds (single-hub vs cross-hub fan-out)",
    ["hub_scope"],
    buckets=(0.05, 0.1, 0.2, 0.4, 0.8, 1.5, 3.0, 5.0),
)

#: Ingest duration histogram — `cocoindex_app.update_blocking()` per-document.
#: KHÔNG label per-doc (cardinality blowup theo số document).
INGEST_DURATION: Histogram = Histogram(
    "ingest_duration_seconds",
    "Cocoindex update_blocking duration per document trigger in seconds",
    buckets=(0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0),
)
