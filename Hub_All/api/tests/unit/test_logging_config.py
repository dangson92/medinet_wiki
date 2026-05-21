"""Unit tests cho `app.logging_config` — HARD-01 Plan 10-01 Task 1.

Verify:
1. `configure_structlog()` cấu hình logger trả JSON parse được bằng `json.loads`.
2. Mỗi log entry có field `level`, `msg`, `ts` (ISO-8601 UTC).
3. ContextVar `request_id_var` + `user_id_var` + `hub_id_var` được merge vào event_dict
   thành 3 field `request_id` / `user_id` / `hub_id` (default None — KHÔNG bỏ qua key).
4. Tính idempotent — gọi `configure_structlog()` nhiều lần KHÔNG raise + KHÔNG nhân processor.

NOTE: `structlog.testing.capture_logs()` bypass TOÀN BỘ processor chain → KHÔNG
thấy được level/ts/msg/request_id. Để test full chain, capture stdout qua
`capsys` + parse JSON (đây mới là render thực tế production).

Test 7 + 8 (cocoindex propagation + integration boot lifespan) ở Task 2 sau khi
`documents_service.trigger_cocoindex_update` đổi sang structlog.
"""
from __future__ import annotations

import asyncio
import contextvars
import json
import re

import pytest
import structlog

from app.logging_config import (
    configure_structlog,
    hub_id_var,
    request_id_var,
    user_id_var,
)

ISO_8601_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$"
)


def _emit_and_parse_last_json(
    capsys: pytest.CaptureFixture[str], event: str = "test_event", **kwargs: object
) -> dict[str, object]:
    """Emit 1 log call qua structlog production chain → capture stdout → parse JSON.

    Dùng capsys fixture của pytest. Structlog `PrintLoggerFactory` in stdout — capsys
    bắt được. Trả entry JSON parse được (dòng cuối nếu nhiều entry).
    """
    configure_structlog()
    log = structlog.get_logger("test_logging_config")
    log.info(event, **kwargs)
    captured = capsys.readouterr().out.strip()
    assert captured, "stdout trống — structlog KHÔNG emit"
    last_line = captured.splitlines()[-1]
    parsed = json.loads(last_line)
    assert isinstance(parsed, dict)
    return parsed


def test_configure_structlog_emits_json_shape(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test 1 — configure_structlog() → logger.info → stdout 1 dòng JSON đủ level/msg/ts."""
    entry = _emit_and_parse_last_json(capsys, "hello_world", custom_field=42)
    # PROJECT CONVENTIONS yêu cầu key "msg" (match Go log/slog), không phải structlog
    # default "event". Implementation rename qua `EventRenamer("msg")` processor.
    assert entry["msg"] == "hello_world"
    assert entry["level"] == "info"
    assert isinstance(entry["ts"], str)
    assert ISO_8601_PATTERN.match(str(entry["ts"])), f"ts KHÔNG ISO-8601 UTC: {entry['ts']}"
    assert entry["custom_field"] == 42


def test_contextvar_propagation_into_log(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test 2 — set request_id_var / user_id_var → log entry có 2 field tương ứng."""
    token_r = request_id_var.set("rid-test-123")
    token_u = user_id_var.set("uid-abc-456")
    try:
        entry = _emit_and_parse_last_json(capsys)
        assert entry["request_id"] == "rid-test-123"
        assert entry["user_id"] == "uid-abc-456"
        assert entry["hub_id"] is None  # KHÔNG set → default None tường minh
    finally:
        request_id_var.reset(token_r)
        user_id_var.reset(token_u)


def test_contextvar_default_none_explicit(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test 3 — ContextVar default → log entry có field None TƯỜNG MINH.

    KHÔNG missing key — schema log ổn định cho Loki/Datadog `request_id IS NULL`
    query consistent.
    """
    # Đảm bảo ContextVar default (test khác có thể leak nếu thiếu reset — phòng thủ).
    request_id_var.set(None)
    user_id_var.set(None)
    hub_id_var.set(None)
    entry = _emit_and_parse_last_json(capsys)
    assert entry["request_id"] is None
    assert entry["user_id"] is None
    assert entry["hub_id"] is None


def test_configure_structlog_idempotent(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test 4 — gọi configure_structlog() nhiều lần KHÔNG raise + KHÔNG nhân processor."""
    configure_structlog()
    configure_structlog()
    configure_structlog()
    # Verify chain processor vẫn hoạt động — log entry vẫn parse được + có level/msg/ts.
    entry = _emit_and_parse_last_json(capsys, "idempotent_check")
    assert entry["level"] == "info"
    assert entry["msg"] == "idempotent_check"
    assert ISO_8601_PATTERN.match(str(entry["ts"]))


def test_contextvar_propagation_across_asyncio_task() -> None:
    """Test 5 — `asyncio.create_task()` copy context cha → child thấy giá trị parent.

    Đây chính là cơ chế propagate `request_id` xuống cocoindex flow log (Plan 10-01
    Task 2 — `trigger_cocoindex_update` chạy qua FastAPI BackgroundTasks dùng cùng
    cơ chế asyncio Task context snapshot).
    """
    captured_value: list[str | None] = []

    async def child_task() -> None:
        captured_value.append(request_id_var.get())

    async def parent() -> None:
        token = request_id_var.set("rid-parent-async")
        try:
            # asyncio.create_task() tự copy context (Python 3.11+ default).
            task = asyncio.create_task(child_task())
            await task
        finally:
            request_id_var.reset(token)

    asyncio.run(parent())
    assert captured_value == ["rid-parent-async"], (
        "ContextVar request_id KHÔNG propagate qua asyncio.create_task (copy_context)"
    )


def test_contextvar_copy_context_run_isolated() -> None:
    """Test 6 — `contextvars.copy_context().run()` snapshot + isolation parent.

    Pattern dùng cho synchronous BackgroundTask (Starlette BackgroundTask sync mode).
    Verify: mutation trong child KHÔNG leak ra parent.
    """
    request_id_var.set("rid-parent-sync")
    captured: list[str | None] = []

    def child_sync() -> None:
        captured.append(request_id_var.get())
        # Mutate ContextVar trong snapshot — chỉ ảnh hưởng snapshot, KHÔNG leak parent.
        request_id_var.set("rid-child-mutated")

    ctx = contextvars.copy_context()
    ctx.run(child_sync)

    assert captured == ["rid-parent-sync"]
    # Parent KHÔNG bị child mutation (isolation).
    assert request_id_var.get() == "rid-parent-sync"
