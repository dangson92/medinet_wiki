"""Response envelope helpers — chuẩn hoá shape {success, data, error, meta} match Go cũ.

Mọi handler PHẢI return qua helper này (KHÔNG return Pydantic model raw) để giữ
contract D6 với frontend React 19 hiện hữu — frontend không sửa, URL `/api/*`
giữ nguyên payload shape.

NOTE: Error code convention = UPPER_SNAKE_CASE match Go pkg/response (Phase 3
AUTH-01). Frontend React 19 `services/api.ts` switch trên `error.code` —
đổi sang lowercase sẽ break D6.
"""
from __future__ import annotations

from typing import Any

from fastapi import status
from fastapi.responses import JSONResponse


def _envelope(
    *,
    success: bool,
    data: Any = None,
    error: dict[str, Any] | None = None,
    meta: dict[str, Any] | None = None,
    status_code: int,
) -> JSONResponse:
    """Bao envelope chuẩn `{success, data, error, meta}` — internal helper."""
    body: dict[str, Any] = {
        "success": success,
        "data": data,
        "error": error,
        "meta": meta,
    }
    return JSONResponse(content=body, status_code=status_code)


# ----------------------------- Success helpers -----------------------------


def ok(data: Any = None, meta: dict[str, Any] | None = None) -> JSONResponse:
    """200 OK — response thành công chuẩn."""
    return _envelope(success=True, data=data, meta=meta, status_code=status.HTTP_200_OK)


def created(data: Any = None, meta: dict[str, Any] | None = None) -> JSONResponse:
    """201 Created — resource vừa được tạo."""
    return _envelope(success=True, data=data, meta=meta, status_code=status.HTTP_201_CREATED)


def accepted(data: Any = None, meta: dict[str, Any] | None = None) -> JSONResponse:
    """202 Accepted — request đã nhận, xử lý async (ingestion qua cocoindex)."""
    return _envelope(success=True, data=data, meta=meta, status_code=status.HTTP_202_ACCEPTED)


def paginated(items: list[Any], page: int, per_page: int, total: int) -> JSONResponse:
    """200 OK — list response kèm phân trang `{page, per_page, total}` trong meta."""
    return _envelope(
        success=True,
        data=items,
        meta={"page": page, "per_page": per_page, "total": total},
        status_code=status.HTTP_200_OK,
    )


# ------------------------------ Error helpers ------------------------------


def _error(
    code: str,
    message: str,
    status_code: int,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    """Bao error envelope `{code, message, details?}` — internal helper."""
    err: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        err["details"] = details
    return _envelope(success=False, error=err, status_code=status_code)


def bad_request(
    message: str,
    code: str = "BAD_REQUEST",
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    """400 Bad Request — payload không hợp lệ."""
    return _error(code, message, status.HTTP_400_BAD_REQUEST, details)


def unauthorized(
    message: str = "Yêu cầu đăng nhập",
    code: str = "UNAUTHORIZED",
) -> JSONResponse:
    """401 Unauthorized — chưa có hoặc JWT không hợp lệ."""
    return _error(code, message, status.HTTP_401_UNAUTHORIZED)


def forbidden(
    message: str = "Không đủ quyền",
    code: str = "FORBIDDEN",
) -> JSONResponse:
    """403 Forbidden — RBAC reject (hub_id không thuộc user, role không cho phép...)."""
    return _error(code, message, status.HTTP_403_FORBIDDEN)


def not_found(
    message: str = "Không tìm thấy",
    code: str = "NOT_FOUND",
) -> JSONResponse:
    """404 Not Found — resource không tồn tại hoặc bị ẩn do RBAC."""
    return _error(code, message, status.HTTP_404_NOT_FOUND)


def conflict(message: str, code: str = "CONFLICT") -> JSONResponse:
    """409 Conflict — duplicate (unique constraint, state machine vi phạm)."""
    return _error(code, message, status.HTTP_409_CONFLICT)


def unsupported_format(
    message: str,
    code: str = "UNSUPPORTED_FORMAT",
) -> JSONResponse:
    """415 Unsupported Media Type — scanned PDF tiếng Việt (R4 Phase 4 mitigation)."""
    return _error(code, message, status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)


def validation_error(
    message: str = "Dữ liệu không hợp lệ",
    code: str = "VALIDATION_ERROR",
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    """422 Unprocessable Entity — Pydantic v2 validation fail.

    Phase 3 router login/refresh dùng để trả lỗi validation request body.
    """
    return _error(code, message, status.HTTP_422_UNPROCESSABLE_ENTITY, details)


def too_many_requests(
    message: str = "Quá nhiều request",
    code: str = "RATE_LIMIT_EXCEEDED",
) -> JSONResponse:
    """429 Too Many Requests — vượt rate-limit Phase 3."""
    return _error(code, message, status.HTTP_429_TOO_MANY_REQUESTS)


def internal_error(
    message: str = "Lỗi máy chủ",
    code: str = "INTERNAL_ERROR",
) -> JSONResponse:
    """500 Internal Server Error — exception ngoài kiểm soát."""
    return _error(code, message, status.HTTP_500_INTERNAL_SERVER_ERROR)


def service_unavailable(
    message: str = "Dịch vụ chưa sẵn sàng",
    code: str = "SERVICE_UNAVAILABLE",
) -> JSONResponse:
    """503 Service Unavailable — readiness chưa pass (DB/Redis/cocoindex chưa up)."""
    return _error(code, message, status.HTTP_503_SERVICE_UNAVAILABLE)
