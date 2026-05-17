"""Audit logger — asyncio.Queue batch flush (Phase 5 AUX-01).

Thay pattern INSERT synchronous trong request transaction (Phase 4
`documents_service.delete`) bằng enqueue non-blocking + background batch flush.

Luồng:
  - Caller (router/service) gọi `enqueue_audit(AuditEntry(...))` — sync, non-blocking.
    Queue đầy → drop entry + log warning (KHÔNG raise — audit log mất 1 entry tốt hơn
    block main request thread; T-05-01-03 DoS mitigation).
  - `audit_flush_loop()` chạy như asyncio background task (wire vào main.py lifespan).
    Drain queue tới `audit_batch_size` (128) HOẶC sau `audit_flush_interval_seconds` (2s);
    batch INSERT N entry trong 1 transaction qua `get_engine()`.
  - `flush_pending()` (gọi lúc shutdown) drain hết queue còn lại trước khi cancel task.

T-05-01-02: payload JSONB chứa dữ liệu do code app sinh — caller chịu trách nhiệm
redact PII/token trước khi đưa vào `payload`. KHÔNG dùng `datetime.utcnow()` — NOW()
server-side trong SQL (CONVENTIONS §"Raw SQL").
"""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text

from app.config import get_settings
from app.db.session import get_engine

logger = logging.getLogger(__name__)

# Action enum hợp lệ (AUX-01 + CONTEXT specifics — security.hub_isolation_violation
# emit khi reject cross-hub mutation).
AUDIT_ACTIONS: frozenset[str] = frozenset(
    {
        "auth.login",
        "auth.refresh",
        "document.upload",
        "document.delete",
        "rag-config.update",
        "hub.create",
        "hub.update",
        "user.create",
        "security.hub_isolation_violation",
    }
)


@dataclass
class AuditEntry:
    """1 audit record chờ flush vào bảng `audit_logs`.

    `action` nên thuộc `AUDIT_ACTIONS` — KHÔNG enforce hard ở enqueue (caller
    chịu trách nhiệm); flush vẫn INSERT mọi action để không mất audit trail.
    """

    action: str
    user_id: str | None = None
    target_type: str | None = None
    target_id: str | None = None
    hub_id: str | None = None
    payload: dict[str, Any] | None = None
    request_id: str | None = None


_queue: asyncio.Queue[AuditEntry] | None = None


def _get_queue() -> asyncio.Queue[AuditEntry]:
    """Lazy-init module-level queue (maxsize = settings.audit_queue_max_size)."""
    global _queue
    if _queue is None:
        _queue = asyncio.Queue(maxsize=get_settings().audit_queue_max_size)
    return _queue


def reset_queue() -> None:
    """Reset queue về None — test isolation helper (force re-init với settings mới)."""
    global _queue
    _queue = None


def enqueue_audit(entry: AuditEntry) -> None:
    """Đẩy 1 audit entry vào queue — non-blocking.

    Queue đầy → drop entry + log warning, KHÔNG raise. Audit log mất 1 entry
    tốt hơn block main request thread (T-05-01-03 DoS mitigation).
    """
    try:
        _get_queue().put_nowait(entry)
    except asyncio.QueueFull:
        logger.warning("audit_queue_full_dropped: action=%s", entry.action)


async def _flush_batch(entries: list[AuditEntry]) -> None:
    """Batch INSERT N entry trong 1 transaction qua get_engine().

    SQLAlchemy `conn.execute(stmt, [param_dict, ...])` → executemany.
    `payload` dict serialize JSON string, CAST sang JSONB trong SQL.
    """
    if not entries:
        return
    params = [
        {
            "user_id": e.user_id,
            "action": e.action,
            "target_type": e.target_type,
            "target_id": e.target_id,
            "hub_id": e.hub_id,
            "payload": json.dumps(e.payload) if e.payload else None,
            "request_id": e.request_id,
        }
        for e in entries
    ]
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO audit_logs "
                "(id, user_id, action, target_type, target_id, hub_id, payload, "
                "request_id, created_at) "
                "VALUES (gen_random_uuid(), :user_id, :action, :target_type, "
                ":target_id, :hub_id, CAST(:payload AS JSONB), :request_id, NOW())"
            ),
            params,
        )


async def audit_flush_loop() -> None:
    """Background loop — drain queue + batch flush.

    Flush khi đạt `audit_batch_size` HOẶC sau `audit_flush_interval_seconds`.
    Nhận `CancelledError` → flush phần còn lại rồi re-raise (graceful shutdown).
    """
    settings = get_settings()
    batch_size = settings.audit_batch_size
    flush_interval = settings.audit_flush_interval_seconds
    queue = _get_queue()
    logger.info(
        "audit_flush_loop_start: batch_size=%d flush_interval=%.1fs",
        batch_size,
        flush_interval,
    )
    while True:
        batch: list[AuditEntry] = []
        try:
            # Block tới khi có entry đầu tiên (hoặc bị cancel).
            first = await queue.get()
            batch.append(first)
            # Gom thêm tới batch_size HOẶC tới khi timeout flush_interval.
            while len(batch) < batch_size:
                try:
                    nxt = await asyncio.wait_for(
                        queue.get(), timeout=flush_interval
                    )
                    batch.append(nxt)
                except TimeoutError:
                    break
            await _flush_batch(batch)
        except asyncio.CancelledError:
            # Flush phần đã gom được trước khi dừng.
            if batch:
                try:
                    await _flush_batch(batch)
                except Exception as e:  # noqa: BLE001
                    logger.warning("audit_flush_on_cancel_failed: %s", e)
            logger.info("audit_flush_loop_cancelled")
            raise
        except Exception as e:  # noqa: BLE001 — KHÔNG crash task, log + continue
            logger.exception("audit_flush_batch_failed: %s", e)


async def flush_pending() -> None:
    """Drain toàn bộ queue hiện tại + batch flush — gọi lúc graceful shutdown."""
    queue = _get_queue()
    pending: list[AuditEntry] = []
    while True:
        try:
            pending.append(queue.get_nowait())
        except asyncio.QueueEmpty:
            break
    if pending:
        await _flush_batch(pending)
        logger.info("audit_flush_pending_drained: count=%d", len(pending))
