"""Rate limit — slowapi Limiter + envelope 429 handler (AUX-03).

Limit: search/ask 100/min, upload 30/min (theo `settings.rate_limit_*_per_minute`).
auth + `/me` KHÔNG limit — KHÔNG decorate auth router.

slowapi dùng `Limiter` + per-route `@limiter.limit(...)` decorator +
`add_exception_handler(RateLimitExceeded, ...)` — KHÔNG phải BaseHTTPMiddleware.

Rate-limit key = user_id (JWT `sub` claim) — request cùng user share counter
giữa nhiều IP; fallback IP khi request chưa auth / token không decode được.
Storage = Redis (qua `settings.redis_url`) để counter share giữa worker.

Wiring vào main.py (Plan 05-06 thực hiện — tránh xung đột file main.py với
plan cùng wave):
    from app.middleware import limiter, rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
Router search/ask/upload dùng `@limiter.limit(SEARCH_LIMIT)` / `UPLOAD_LIMIT`.
"""
from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.config import get_settings
from app.pkg import response as resp


def _rate_limit_key(request: Request) -> str:
    """Khóa rate-limit — user_id từ JWT `sub`, fallback IP nếu chưa auth.

    Đọc header `Authorization: Bearer <token>`, decode lấy claim `sub` qua
    `app.state.jwt_manager`. Bọc try/except — decode fail KHÔNG raise, chỉ
    fallback `get_remote_address` (T-05-02-05: IP fallback chấp nhận cho
    request chưa auth; auth/me KHÔNG limit nên ảnh hưởng nhỏ).
    """
    try:
        auth_header = request.headers.get("Authorization", "")
        scheme, _, token = auth_header.partition(" ")
        if scheme.lower() == "bearer" and token:
            jwt_manager = getattr(request.app.state, "jwt_manager", None)
            if jwt_manager is not None:
                claims = jwt_manager.verify_token(token, expected_type="access")
                return f"user:{claims.sub}"
    except Exception:  # noqa: BLE001 — bất kỳ lỗi decode → fallback IP, KHÔNG raise
        pass
    return get_remote_address(request)


# Storage = Redis để counter share giữa worker (CONTEXT discretion → Redis vì
# app.state.redis sẵn có). slowapi nhận `redis://` URI trực tiếp qua `limits`.
limiter = Limiter(
    key_func=_rate_limit_key,
    storage_uri=get_settings().redis_url,
    default_limits=[],
)

# Decorator-string constant — router search/ask/upload import dùng
# `@limiter.limit(SEARCH_LIMIT)`. KHÔNG decorate auth router (auth/me unlimited).
SEARCH_LIMIT = f"{get_settings().rate_limit_search_per_minute}/minute"
UPLOAD_LIMIT = f"{get_settings().rate_limit_upload_per_minute}/minute"
AUDIT_LOGS_LIMIT = f"{get_settings().rate_limit_audit_logs_per_minute}/minute"


async def rate_limit_exceeded_handler(
    request: Request,  # noqa: ARG001 — chữ ký bắt buộc cho exception handler
    exc: RateLimitExceeded,
) -> JSONResponse:
    """Map `RateLimitExceeded` → envelope 429 `RATE_LIMIT_EXCEEDED` (D6 shape)."""
    return resp.too_many_requests(
        message=f"Vượt giới hạn request: {exc}",
        code="RATE_LIMIT_EXCEEDED",
    )
