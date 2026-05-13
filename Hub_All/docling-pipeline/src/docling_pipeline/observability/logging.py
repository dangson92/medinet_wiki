"""Structlog JSON config + propagate X-Request-Id từ Go (DSVC-04).

Trách nhiệm:
1. configure_logging(): setup structlog JSON renderer + bridge stdlib logging.
2. RequestIdMiddleware: extract X-Request-Id từ request header (auto-gen UUID nếu thiếu),
   bind vào structlog contextvars → mọi log line trong request có field request_id.

Tham chiếu:
- DSVC-04: propagate request_id từ Go backend.
- CONTEXT.md mục D (single worker, async): contextvars an toàn vì không chia sẻ giữa request.
"""

from __future__ import annotations

import logging
import sys
import uuid
from typing import Any

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from docling_pipeline.config import get_settings


def configure_logging() -> None:
    """Cấu hình structlog JSON + stdlib logging bridge.

    Gọi 1 lần ở FastAPI lifespan startup (Plan 06 main.py).
    """
    settings = get_settings()
    level = getattr(logging, settings.log_level, logging.INFO)

    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if settings.log_format == "json":
        renderer: Any = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )

    # Bridge stdlib logging → structlog format (uvicorn dùng stdlib logging)
    logging.basicConfig(
        format="%(message)s",
        level=level,
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,
    )


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Bind X-Request-Id từ header vào structlog contextvars (DSVC-04).

    - Header có sẵn → dùng (Go backend đã gen request_id, propagate sang).
    - Header thiếu → auto-gen UUID4.
    - Set response header echo lại để client trace.
    """

    HEADER = "X-Request-Id"

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        rid = request.headers.get(self.HEADER) or str(uuid.uuid4())
        # clear trước khi bind để tránh leak context giữa request (single worker async)
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=rid,
            path=request.url.path,
            method=request.method,
        )
        try:
            response: Response = await call_next(request)
        finally:
            structlog.contextvars.clear_contextvars()
        response.headers[self.HEADER] = rid
        return response


__all__ = ["configure_logging", "RequestIdMiddleware"]
