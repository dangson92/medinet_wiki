"""RequestId middleware — sinh hoặc echo X-Request-Id header.

Match Go internal/middleware/request_id.go. Đặt sớm trong chain (gần outermost)
để mọi log downstream + error response có request_id field.

Phase 3: chỉ gắn vào request.state. Phase 10 (HARD-01) sẽ propagate vào structlog
context vars cho cocoindex flow logs.
"""
from __future__ import annotations

import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

REQUEST_ID_HEADER = "X-Request-Id"


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Set request.state.request_id + echo header response.

    Behavior:
    - Client gửi `X-Request-Id: <bất kỳ>` → echo nguyên trị (KHÔNG validate format).
    - Client không gửi → sinh UUID4 mới.
    - Response luôn có header `X-Request-Id`.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        rid = request.headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())
        request.state.request_id = rid
        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = rid
        return response
