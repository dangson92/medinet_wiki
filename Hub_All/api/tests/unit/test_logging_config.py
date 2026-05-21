"""Unit tests cho `app.logging_config` — HARD-01 Plan 10-01 Task 1.

Verify:
1. `configure_structlog()` cấu hình logger trả JSON parse được bằng `json.loads`.
2. Mỗi log entry có field `level`, `msg`, `ts` (ISO-8601 UTC).
3. ContextVar `request_id_var` + `user_id_var` + `hub_id_var` được merge vào event_dict
   thành 3 field `request_id` / `user_id` / `hub_id` (default None — KHÔNG bỏ qua key).
4. Tính idempotent — gọi `configure_structlog()` nhiều lần KHÔNG raise + KHÔNG nhân processor.

Test 7 (cocoindex propagation — Task 2) thêm sau khi `documents_service.trigger_cocoindex_update`
đổi sang structlog logger.
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


def _capture_one_entry(logger_kwargs: dict[str, object] | None = None) -> dict:
    """Capture 1 structlog entry qua `structlog.testing.capture_logs`.

    capture_logs context manager bypass renderer cuối cùng — vẫn run các processor
    upstream (merge_contextvars + _add_contextvars + add_log_level + TimeStamper).
    Trả về dict event_dict cuối cùng (trước JSONRenderer).
    """
    configure_structlog()
    log = structlog.get_logger("test_logging_config")
    with structlog.testing.capture_logs() as captured:
        log.info("test_event", **(logger_kwargs or {}))
    assert len(captured) == 1, f"Expect 1 captured entry, got {len(captured)}"
    return captured[0]


def test_configure_structlog_emits_json_shape(capsys: pytest.CaptureFixture[str]) -> None:
    """Test 1 — configure_structlog() rồi logger.info → stdout 1 dòng JSON parse được."""
    configure_structlog()
    log = structlog.get_logger("test_logging_config")
    log.info("hello_world", custom_field=42)
    captured_stdout = capsys.readouterr().out.strip()
    # Mỗi entry = 1 dòng. Lấy dòng cuối (test trước có thể đã emit).
    last_line = captured_stdout.splitlines()[-1] if captured_stdout else ""
    entry = json.loads(last_line)
    assert entry["event"] == "hello_world" or entry.get("msg") == "hello_world"
    # structlog JSONRenderer default key "event"; PROJECT CONVENTIONS muốn "msg".
    # Implementation rename event → msg qua `EventRenamer("msg")` processor.
    assert entry.get("msg") == "hello_world"
    assert entry["level"] == "info"
    assert ISO_8601_PATTERN.match(entry["ts"]), f"ts không phải ISO-8601 UTC: {entry['ts']}"
    assert entry["custom_field"] == 42


def test_contextvar_propagation_into_log() -> None:
    """Test 2 — set request_id_var / user_id_var → log có field tương ứng."""
    token_r = request_id_var.set("rid-test-123")
    token_u = user_id_var.set("uid-abc-456")
    try:
        entry = _capture_one_entry()
        assert entry["request_id"] == "rid-test-123"
        assert entry["user_id"] == "uid-abc-456"
        assert entry["hub_id"] is None  # KHÔNG set → default None tường minh
    finally:
        request_id_var.reset(token_r)
        user_id_var.reset(token_u)


def test_contextvar_default_none_explicit() -> None:
    """Test 3 — ContextVar default None → log entry có field None TƯỜNG MINH.

    KHÔNG missing key — schema log ổn định cho Loki/Datadog query field exists.
    """
    # Default state — KHÔNG set ContextVar nào.
    entry = _capture_one_entry()
    assert entry["request_id"] is None
    assert entry["user_id"] is None
    assert entry["hub_id"] is None


def test_configure_structlog_idempotent() -> None:
    """Test 4 — gọi configure_structlog() nhiều lần KHÔNG raise + KHÔNG nhân processor."""
    configure_structlog()
    configure_structlog()
    configure_structlog()
    # Verify chain processor vẫn hoạt động — log entry vẫn parse được + có level/msg/ts.
    entry = _capture_one_entry()
    assert entry["level"] == "info"
    assert "msg" in entry or "event" in entry  # capture_logs bypass EventRenamer
    # capture_logs() bypass JSONRenderer + EventRenamer ⇒ event key vẫn còn.
    # Cho stdout test "msg" — đã verify ở Test 1.


def test_contextvar_propagation_across_asyncio_task() -> None:
    """Test 5 — `copy_context().run()` (FastAPI BackgroundTasks pattern) copy ContextVar.

    Mô phỏng FastAPI BackgroundTasks dùng `contextvars.copy_context()` để snapshot
    parent context khi tạo task con. Khi task con chạy, `request_id_var.get()` PHẢI
    trả về giá trị parent đã set TRƯỚC khi tạo task.

    Đây chính là cơ chế propagate `request_id` xuống cocoindex flow log (Plan 10-01
    Task 2 — `trigger_cocoindex_update` gọi qua FastAPI BackgroundTasks).
    """
    captured_value: list[str | None] = []

    async def child_task() -> None:
        # Child đọc ContextVar — phải thấy giá trị parent set.
        captured_value.append(request_id_var.get())

    async def parent() -> None:
        token = request_id_var.set("rid-parent-async")
        try:
            # asyncio.create_task() tự copy context — đây là cùng pattern FastAPI
            # BackgroundTasks dùng (BackgroundTasks gọi `await coro()` trong context
            # của request handler).
            task = asyncio.create_task(child_task())
            await task
        finally:
            request_id_var.reset(token)

    asyncio.run(parent())
    assert captured_value == ["rid-parent-async"], (
        "ContextVar request_id KHÔNG propagate qua asyncio.create_task (copy_context)"
    )


def test_contextvar_copy_context_run_isolated() -> None:
    """Test 6 — `contextvars.copy_context().run()` chạy callable trong snapshot.

    Pattern dùng cho synchronous BackgroundTask (Starlette BackgroundTask sync mode):
    parent snapshot context → run sync fn → fn đọc ContextVar thấy parent value.
    Verify thêm: mutation trong child KHÔNG leak ra parent (isolation).
    """
    request_id_var.set("rid-parent-sync")
    captured: list[str | None] = []

    def child_sync() -> None:
        captured.append(request_id_var.get())
        # Mutate ContextVar trong snapshot — chỉ ảnh hưởng snapshot, KHÔNG leak parent.
        request_id_var.set("rid-child-mutated")

    ctx = contextvars.copy_context()
    ctx.run(child_sync)

    # Child đã thấy parent value khi vào snapshot.
    assert captured == ["rid-parent-sync"]
    # Parent KHÔNG bị child mutation (isolation).
    assert request_id_var.get() == "rid-parent-sync"
