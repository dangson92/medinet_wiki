"""RequestId middleware — sinh hoặc echo X-Request-Id header + log request_completed.

Match Go internal/middleware/request_id.go. Đặt ở vị trí gần outermost (Phase 3
add ngay trước ErrorHandler — main.py middleware chain) để mọi log downstream +
error response có request_id field.

Phase 10 HARD-01 (Plan 10-01) mở rộng:
- Set `request_id_var` (ContextVar) trước call_next → cocoindex flow log
  (BackgroundTask) propagate đúng request_id của caller.
- Đo latency qua `time.perf_counter()` — emit structlog entry "request_completed"
  với fields {path, method, status, latency_ms}. ContextVar processor tự inject
  request_id/user_id/hub_id.
- Best-effort đọc `request.state.user_id` (auth dependency set sau verify JWT) →
  set `user_id_var` cho log entry.

KHÔNG đổi signature class `RequestIdMiddleware` — main.py wiring `app.add_middleware
(RequestIdMiddleware)` giữ nguyên.
"""
from __future__ import annotations

import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.logging_config import request_id_var, user_id_var

REQUEST_ID_HEADER = "X-Request-Id"

_log = structlog.get_logger(__name__)


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Set request.state.request_id + ContextVar + echo header + emit request_completed log.

    Behavior:
    - Client gửi `X-Request-Id: <bất kỳ>` → echo nguyên trị (KHÔNG validate format).
    - Client không gửi → sinh UUID4 mới.
    - Response luôn có header `X-Request-Id`.
    - SET ContextVar `request_id_var` trước call_next → downstream log
      (cocoindex flow trong BackgroundTask) thấy request_id qua structlog
      processor `_add_contextvars`.
    - SAU call_next: log entry "request_completed" với latency_ms (int) + path
      + method + status.

    ContextVar isolation: Starlette spawn task riêng per request → ContextVar
    set trong dispatch scope KHÔNG leak sang request khác. KHÔNG cần reset
    token (request task sống ngắn — GC cleanup tự nhiên).
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        rid = request.headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())
        request.state.request_id = rid
        request_id_var.set(rid)

        start = time.perf_counter()
        response = await call_next(request)
        latency_ms = int((time.perf_counter() - start) * 1000)

        # Best-effort propagate user_id từ auth dependency (Phase 3
        # `get_current_user` set request.state.user_id sau verify JWT). Có thể
        # None nếu endpoint không cần auth (vd /healthz, /readyz).
        user_id = getattr(request.state, "user_id", None)
        if user_id is not None:
            user_id_var.set(str(user_id))

        response.headers[REQUEST_ID_HEADER] = rid

        # Emit log entry "request_completed" — ContextVar processor tự inject
        # request_id/user_id/hub_id từ ContextVar (đã set ở trên).
        _log.info(
            "request_completed",
            path=request.url.path,
            method=request.method,
            status=response.status_code,
            latency_ms=latency_ms,
        )
        return response
