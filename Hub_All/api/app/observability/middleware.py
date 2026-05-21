"""PrometheusMiddleware — HARD-02 Plan 10-02.

Đo latency mỗi request (REQUEST_DURATION histogram) + đếm request hoàn tất
(REQUESTS_TOTAL counter) + đếm error >= 500 (ERRORS_TOTAL counter).

Vị trí trong middleware chain (xem `app/main.py:create_app`):
  add_middleware order: PrometheusMiddleware → CORS → SecurityHeaders → RequestId → ErrorHandler.
  Tức Prometheus là INNERMOST (add đầu tiên) — bao quanh router handler, đo
  latency thật của business logic + downstream middleware. ErrorHandler vẫn là
  outermost — exception trong handler được PrometheusMiddleware catch + re-raise
  để ghi metric trước khi ErrorHandler render envelope.

Cardinality control: label `path` dùng `request.scope["route"].path` (Starlette
resolved route template) thay vì URL thật. Route không match (404 trước khi
router resolve) → fallback `"unknown"`.
"""
from __future__ import annotations

import time

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Match

from app.observability.metrics import (
    ERRORS_TOTAL,
    REQUEST_DURATION,
    REQUESTS_TOTAL,
)


class PrometheusMiddleware(BaseHTTPMiddleware):
    """Middleware đo latency + đếm request/error metrics (HARD-02)."""

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        """Bao quanh router handler — đo `elapsed = time.perf_counter() - start`."""
        start = time.perf_counter()
        method = request.method
        # Resolve route template TRƯỚC call_next vì Starlette KHÔNG set
        # `scope["route"]`; chỉ set `scope["endpoint"]/path_params` SAU resolve.
        # Walk app.routes match scope là pattern chuẩn middleware-level resolve.
        path = _resolve_path(request)
        try:
            response = await call_next(request)
        except Exception:
            # Ghi metric TRƯỚC khi re-raise — ErrorHandler (outer) render envelope
            # nhưng exception bypass PrometheusMiddleware nếu KHÔNG catch ở đây.
            elapsed = time.perf_counter() - start
            REQUESTS_TOTAL.labels(method=method, path=path, status="500").inc()
            REQUEST_DURATION.labels(method=method, path=path).observe(elapsed)
            ERRORS_TOTAL.labels(method=method, path=path).inc()
            raise

        elapsed = time.perf_counter() - start
        status = response.status_code
        REQUESTS_TOTAL.labels(method=method, path=path, status=str(status)).inc()
        REQUEST_DURATION.labels(method=method, path=path).observe(elapsed)
        if status >= 500:
            ERRORS_TOTAL.labels(method=method, path=path).inc()
        return response


def _resolve_path(request: Request) -> str:
    """Trả route template (vd `/api/documents/{document_id}`) thay URL thật.

    Cardinality control: route không match (404) → `"unknown"`. Cố định set
    label space O(routes) thay vì O(unique URLs).

    Starlette KHÔNG set `scope["route"]` — phải walk `request.app.routes`
    + dùng `route.matches(scope)` (trả `Match.FULL/PARTIAL/NONE`) để resolve
    template path từ middleware level (TRƯỚC khi router resolve).
    """
    app = request.scope.get("app")
    if app is None:
        return "unknown"
    routes = getattr(app, "routes", None)
    if not routes:
        return "unknown"
    for route in routes:
        try:
            match, _scope = route.matches(request.scope)
        except Exception:  # noqa: BLE001 — defensive: route subtype lạ
            continue
        if match == Match.FULL:
            template = getattr(route, "path", None)
            if template is not None:
                return str(template)
    return "unknown"
