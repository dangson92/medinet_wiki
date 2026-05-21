"""Structured logging config — HARD-01 Plan 10-01.

`configure_structlog()` cấu hình structlog 1 lần (idempotent) ở đầu lifespan
(`app/main.py`). Output JSON ra stdout — mỗi dòng = 1 JSON object parse được.

Schema log entry match Go `log/slog` (CONVENTIONS.md Section 5 Logging Fields):

| Field | Type | Source |
|-------|------|--------|
| level | string | `add_log_level` processor |
| msg | string | `EventRenamer("msg")` rename từ `event` |
| ts | ISO-8601 UTC | `TimeStamper(fmt="iso", utc=True, key="ts")` |
| request_id | UUID/None | ContextVar `request_id_var` (set ở RequestIdMiddleware) |
| user_id | UUID/None | ContextVar `user_id_var` (set ở middleware/dependency get_current_user) |
| hub_id | UUID/None | ContextVar `hub_id_var` (set ở handler scope nếu có) |
| latency_ms | int | Middleware time.perf_counter() — log "request_completed" |
| path | string | request.url.path |
| method | string | request.method |
| status | int | response.status_code |

3 ContextVar default `None` TƯỜNG MINH — KHÔNG bỏ qua key để schema log ổn định
cho Loki/Datadog query field exists. ContextVar scoped per asyncio Task — Starlette
spawn task riêng/request → isolation tự nhiên, KHÔNG cross-request leak.

Propagation xuống FastAPI BackgroundTasks: `asyncio.create_task()` và `contextvars.
copy_context().run()` đều snapshot context cha → child thấy giá trị parent. Đây
là cơ chế propagate `request_id` xuống cocoindex flow log
(`documents_service.trigger_cocoindex_update` chạy trong BackgroundTask).

Idempotent: module-level flag `_configured` → re-call no-op. Test integration boot
LifespanManager nhiều lần phải KHÔNG nhân processor + KHÔNG raise.

Security note (CONVENTIONS DON'T): KHÔNG log raw email/password/Authorization/
X-API-Key. Email phải `sha256(email)[:8]` (Phase 3 auth service đã làm).
"""
from __future__ import annotations

import logging
from collections.abc import MutableMapping
from contextvars import ContextVar
from typing import Any

import structlog

# ---------------------------------------------------------------------------
# ContextVar — bound per asyncio Task. Default None tường minh (KHÔNG missing key).
# ---------------------------------------------------------------------------

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
user_id_var: ContextVar[str | None] = ContextVar("user_id", default=None)
hub_id_var: ContextVar[str | None] = ContextVar("hub_id", default=None)


def _add_contextvars(
    _logger: Any, _method_name: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    """Processor — đọc 3 ContextVar và inject vào event_dict.

    `event_dict.setdefault(...)`: nếu caller đã pass explicit `request_id=...`
    kwarg (vd middleware emit "request_completed" sau khi đo latency), giữ giá
    trị explicit; ngược lại lấy từ ContextVar.

    KHÔNG bỏ qua key nếu ContextVar default None — schema log ổn định, downstream
    Loki/Datadog `request_id != null` query consistent (tránh undefined behavior).
    """
    event_dict.setdefault("request_id", request_id_var.get())
    event_dict.setdefault("user_id", user_id_var.get())
    event_dict.setdefault("hub_id", hub_id_var.get())
    return event_dict


# Idempotent flag — module-level. configure_structlog() re-call no-op.
_configured: bool = False


def configure_structlog() -> None:
    """Configure structlog 1 lần lifecycle. Idempotent re-call.

    Processor chain (apply theo thứ tự cho mỗi log call):
        1. `structlog.contextvars.merge_contextvars` — merge `structlog.contextvars.
           bind_contextvars(...)` (structlog-native binding) nếu code dùng.
        2. `_add_contextvars` — inject 3 ContextVar (request_id/user_id/hub_id).
        3. `add_log_level` — gắn field `level` (`info`/`warning`/...).
        4. `TimeStamper(fmt="iso", utc=True, key="ts")` — field `ts` ISO-8601 UTC.
        5. `StackInfoRenderer` — render stack info nếu log.info(..., stack_info=True).
        6. `format_exc_info` — render exception nếu log.exception(...).
        7. `EventRenamer("msg")` — rename field `event` → `msg` match Go log/slog.
        8. `JSONRenderer` — output JSON 1 dòng.

    Logger factory `PrintLoggerFactory()` — in stdout (Docker capture). Wrapper
    class `make_filtering_bound_logger(INFO)` — DEBUG bị skip ở wrapper level
    (tránh emit DEBUG log).
    """
    global _configured
    if _configured:
        return

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            _add_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True, key="ts"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.EventRenamer("msg"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    _configured = True
