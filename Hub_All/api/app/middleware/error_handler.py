"""ErrorHandler middleware — catch exception, return envelope chuẩn.

Outermost middleware (add LAST trong app.add_middleware). Mọi exception
không-HTTPException từ handler/downstream middleware sẽ bị catch ở đây →
log structured (level=error) + return envelope `{success:false, error:{code,
message}, meta:null}` 500 status.

P11 mitigation: PHẢI add CUỐI cùng để wrap toàn bộ chain (CORS, security_headers,
request_id). Nếu add ĐẦU → exception từ CORS middleware không được catch.

KHÔNG leak stack trace vào response body — chỉ log server-side.
"""
from __future__ import annotations

import logging

from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.pkg import response as resp

logger = logging.getLogger(__name__)


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """Catch unhandled exception → log + return envelope 500.

    KHÔNG catch starlette.exceptions.HTTPException (FastAPI tự handle qua
    exception_handler) — nếu catch ở đây thì shape envelope sẽ KHÔNG match
    với raise HTTPException ở handler.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        try:
            return await call_next(request)
        except Exception as exc:  # noqa: BLE001 — catch-all là chủ đích của middleware này.
            # HTTPException pass-through — để FastAPI exception_handler (Plan 03-05)
            # render envelope shape khớp với endpoint raise HTTPException trực tiếp.
            # Nếu catch ở đây thì envelope SẼ KHÔNG match (T-03-http-exception-mask).
            if isinstance(exc, StarletteHTTPException):
                raise
            request_id = getattr(request.state, "request_id", "unknown")
            logger.error(
                "unhandled_exception",
                exc_info=exc,
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                },
            )
            return resp.internal_error(message="Lỗi máy chủ nội bộ")
