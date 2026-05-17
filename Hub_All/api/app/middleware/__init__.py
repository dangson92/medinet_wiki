"""Middleware package — request_id, security_headers, error_handler, rate_limit.

Sử dụng trong app/main.py (theo P11 — add CUỐI = outermost):
    from app.middleware import (
        ErrorHandlerMiddleware,
        RequestIdMiddleware,
        SecurityHeadersMiddleware,
    )

Rate limit (AUX-03) — slowapi Limiter + 429 handler; wiring Plan 05-06:
    from app.middleware import limiter, rate_limit_exceeded_handler
"""
from __future__ import annotations

from app.middleware.error_handler import ErrorHandlerMiddleware
from app.middleware.rate_limit import (
    AUDIT_LOGS_LIMIT,
    SEARCH_LIMIT,
    UPLOAD_LIMIT,
    limiter,
    rate_limit_exceeded_handler,
)
from app.middleware.request_id import REQUEST_ID_HEADER, RequestIdMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware

__all__ = [
    "AUDIT_LOGS_LIMIT",
    "REQUEST_ID_HEADER",
    "SEARCH_LIMIT",
    "UPLOAD_LIMIT",
    "ErrorHandlerMiddleware",
    "RequestIdMiddleware",
    "SecurityHeadersMiddleware",
    "limiter",
    "rate_limit_exceeded_handler",
]
