"""Unit tests cho RequestIdMiddleware mở rộng — HARD-01 Plan 10-01 Task 1.

Verify:
- Client không gửi `X-Request-Id` → middleware sinh UUID4 (regex format chuẩn).
- Client gửi `X-Request-Id: <bất kỳ>` → middleware echo nguyên trị (KHÔNG validate).
- Sau `call_next`, middleware emit 1 structlog entry "request_completed" với
  field `{request_id, path, method, status, latency_ms}` — `latency_ms` >= 0 int.
- ContextVar `request_id_var` được SET trước call_next (endpoint đọc + bind vào response).

NOTE: `structlog.testing.capture_logs()` bypass processor chain → KHÔNG kiểm được
request_id/level/ts. Capture stdout qua capsys + parse JSON là cách verify full
processor chain production.

Test dùng `httpx.AsyncClient + ASGITransport` boot mini Starlette app chỉ với
RequestIdMiddleware + 1 route GET / — KHÔNG cần DB/Redis.
"""
from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator

import httpx
import pytest
import pytest_asyncio
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from app.logging_config import configure_structlog, request_id_var
from app.middleware.request_id import REQUEST_ID_HEADER, RequestIdMiddleware

UUID4_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)


async def _endpoint(request: Request) -> JSONResponse:
    """Endpoint mini — bind state.request_id + ContextVar.get() vào response."""
    rid_state = getattr(request.state, "request_id", None)
    rid_ctx = request_id_var.get()
    return JSONResponse({"rid_state": rid_state, "rid_ctx": rid_ctx})


def _build_mini_app() -> Starlette:
    """Build Starlette app chỉ với RequestIdMiddleware + GET /."""
    app = Starlette(routes=[Route("/", _endpoint, methods=["GET"])])
    app.add_middleware(RequestIdMiddleware)
    return app


@pytest_asyncio.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    configure_structlog()
    app = _build_mini_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c


@pytest.mark.asyncio
async def test_missing_header_generates_uuid4(client: httpx.AsyncClient) -> None:
    """Test — không gửi X-Request-Id → middleware sinh UUID4 valid + echo header."""
    resp = await client.get("/")
    assert resp.status_code == 200
    rid = resp.headers.get(REQUEST_ID_HEADER)
    assert rid is not None, "Response thiếu header X-Request-Id"
    assert UUID4_PATTERN.match(rid), f"X-Request-Id KHÔNG phải UUID4: {rid!r}"
    body = resp.json()
    assert body["rid_state"] == rid
    assert body["rid_ctx"] == rid, "ContextVar request_id_var KHÔNG được set bởi middleware"


@pytest.mark.asyncio
async def test_existing_header_echoed_verbatim(client: httpx.AsyncClient) -> None:
    """Test — client gửi X-Request-Id tuỳ ý → middleware echo nguyên trị (KHÔNG validate)."""
    custom = "custom-rid-not-a-uuid"
    resp = await client.get("/", headers={REQUEST_ID_HEADER: custom})
    assert resp.status_code == 200
    assert resp.headers[REQUEST_ID_HEADER] == custom
    body = resp.json()
    assert body["rid_state"] == custom
    assert body["rid_ctx"] == custom


@pytest.mark.asyncio
async def test_request_completed_log_emitted(
    client: httpx.AsyncClient, capsys: pytest.CaptureFixture[str]
) -> None:
    """Test — sau call_next, middleware emit log entry 'request_completed' đủ field.

    Verify qua capsys + parse JSON stdout (production processor chain — bypass
    KHÔNG được dùng vì cần check field request_id từ ContextVar merge).
    """
    # Clear bất kỳ stdout pending từ fixture/test khác.
    capsys.readouterr()

    resp = await client.get("/")
    assert resp.status_code == 200
    rid = resp.headers[REQUEST_ID_HEADER]

    captured_stdout = capsys.readouterr().out.strip()
    assert captured_stdout, "Middleware KHÔNG emit log gì lên stdout"

    # Tìm dòng "request_completed" — middleware emit, có thể có log khác trộn.
    matching: list[dict] = []
    for line in captured_stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if obj.get("msg") == "request_completed":
            matching.append(obj)

    assert matching, (
        f"KHÔNG thấy log 'request_completed' trong stdout. "
        f"Lines: {captured_stdout.splitlines()}"
    )
    entry = matching[-1]
    assert entry["request_id"] == rid
    assert entry["path"] == "/"
    assert entry["method"] == "GET"
    assert entry["status"] == 200
    assert isinstance(entry["latency_ms"], int)
    assert entry["latency_ms"] >= 0
    assert entry["level"] == "info"
