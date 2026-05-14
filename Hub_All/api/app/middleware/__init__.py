"""Middleware package — request_id, security_headers, error_handler.

Sử dụng trong app/main.py (theo P11 — add CUỐI = outermost):
    from app.middleware import (
        ErrorHandlerMiddleware,
        RequestIdMiddleware,
        SecurityHeadersMiddleware,
    )
"""
from __future__ import annotations

from app.middleware.error_handler import ErrorHandlerMiddleware
from app.middleware.request_id import REQUEST_ID_HEADER, RequestIdMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware

__all__ = [
    "REQUEST_ID_HEADER",
    "ErrorHandlerMiddleware",
    "RequestIdMiddleware",
    "SecurityHeadersMiddleware",
]
