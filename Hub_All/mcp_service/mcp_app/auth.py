"""MCP auth — Phase 8.2 (MCP-01).

Trích xuất header `X-API-Key` từ MCP request để forward xuống API Service.

KHÁC Phase 8.1 (`api/app/mcp/auth.py`): Phase 8.2 GIỮ phần đọc header HTTP
nhưng BỎ phần verify DB. MCP Service nay là process độc lập — nó KHÔNG truy cập
DB/Redis. Việc verify API key (kiểm tra key hợp lệ, chưa thu hồi, user còn active)
do API Service đảm nhận khi nhận request qua HTTP. MCP Service chỉ trích key từ
header rồi forward — API Service trả 401 nếu key sai, tool map sang ToolError.

Bảo mật: KHÔNG bao giờ log giá trị `key` (T-08.2-03-I2).
"""
from __future__ import annotations

from mcp.server.fastmcp.exceptions import ToolError


def extract_api_key(ctx: object) -> str | None:
    """Đọc X-API-Key từ HTTP header trong MCP Context (Starlette Request).

    Khi MCP Service chạy Streamable HTTP transport, `ctx.request_context.request`
    là một Starlette `Request`. Header lowercase theo ASGI convention → dùng
    `x-api-key`.

    KHÔNG verify key — chỉ trích xuất. Verify do API Service làm khi nhận request.

    Args:
        ctx: MCP Context object (inject qua annotation `ctx: Context`).

    Returns:
        Giá trị header `x-api-key` nếu có, ngược lại `None` (không raise).
    """
    try:
        request = ctx.request_context.request  # type: ignore[attr-defined]
        if request is None:
            return None
        return request.headers.get("x-api-key")
    except (AttributeError, LookupError, TypeError):
        return None


def require_api_key(ctx: object) -> str:
    """Trích X-API-Key bắt buộc — raise ToolError nếu thiếu.

    Gọi từ đầu mỗi tool handler. Nếu client không gửi header `X-API-Key`,
    raise `ToolError(MCP_UNAUTHORIZED)` → MCP client nhận lỗi rõ ràng và tool
    KHÔNG chạy logic (T-08.2-03-S).

    KHÔNG verify key (verify thuộc API Service) — chỉ chắc chắn key tồn tại để
    forward. API Service tự trả 401 nếu key sai/thu hồi.

    Args:
        ctx: MCP Context object.

    Returns:
        Giá trị API key (chuỗi không rỗng) để forward xuống API Service.

    Raises:
        ToolError: nếu thiếu header `X-API-Key`.
    """
    key = extract_api_key(ctx)
    if not key:
        raise ToolError(
            "MCP_UNAUTHORIZED: thiếu header X-API-Key "
            "— cấu hình MCP client với header X-API-Key"
        )
    return key
