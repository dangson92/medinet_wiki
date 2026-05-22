"""Phase 4 Plan 04-03 Task 3 — sync_worker_loop async task (D-V3-Phase4-A1/A3/A5).

BLOCKER 1 fix (CR Iteration 1): `_update_document_sync_status` helper aggregate
sync_outbox state per document → UPDATE documents.sync_status enum SAU MỖI batch.
Plan 04-01 trigger handle initial 'pending'→'syncing'; worker handle 'syncing'→
'synced'|'failed'|'partial' transitions (D-V3-Phase4-B2 lifecycle complete).

Worker loop structure (D-V3-Phase4-A5 LOCKED):
  loop:
    rows = CLAIM batch FOR UPDATE SKIP LOCKED LIMIT batch_size
    if empty:
      SYNC_OUTBOX_PENDING.set(0)
      sleep poll_interval
      continue

    SYNC_OUTBOX_PENDING.set(len(rows))
    MARK_PROCESSING (attempt_count++)
    split inserts + deletes
    try _push_inserts → MARK_PROCESSED success
    try _push_deletes → MARK_PROCESSED success
    _handle_failures (backoff retry or dead)
    _update_document_sync_status(affected_doc_ids)  # BLOCKER 1 fix

  CancelledError → propagate (graceful shutdown).
  Other Exception → log + sleep poll_interval (degrade gracefully).

W7 fix: Prometheus label `hub_name` (NOT `hub_id` UUID) throughout.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from app.sync.keys import (
    CLAIM_PENDING_SQL,
    MARK_DEAD_SQL,
    MARK_FAILED_RETRY_SQL,
    MARK_PROCESSED_SQL,
    MARK_PROCESSING_SQL,
    PUSH_DELETE_CHUNK_SQL,
    PUSH_INSERT_CHUNK_SQL,
    UPDATE_DOC_SYNC_STATUS_SQL,
)
from app.sync.metrics import (
    SYNC_ATTEMPT_TOTAL,
    SYNC_DEAD_TOTAL,
    SYNC_LAG_SECONDS,
    SYNC_OUTBOX_PENDING,
    normalize_error_class,
)
from app.sync.models import ChunkPayload, OpType, SyncOutboxRow

if TYPE_CHECKING:
    pass  # avoid runtime FastAPI import (app passed as any)

logger = logging.getLogger(__name__)

LAST_ERROR_TRUNCATE = 1000


def _get_settings() -> Any:
    """Indirection helper — testable monkeypatch hook (KHONG inline get_settings()).

    Test fixture monkeypatch `app.sync.worker._get_settings` thay vì
    `app.config.get_settings` để isolate worker logic.
    """
    from app.config import get_settings

    return get_settings()


async def sync_worker_loop(app: Any) -> None:  # noqa: C901,PLR0912 — D-V3-Phase4-A5 monolithic loop intentional
    """Main worker loop — spawn ở hub con lifespan (Plan 04-04).

    Args:
        app: FastAPI app instance (app.state.db_pool + app.state.central_sync_pool).

    Skip central (settings.hub_name == "central") — central KHONG own outbox
    (D-V3-Phase4-A2). Hub con only.

    Cancellation: asyncio.CancelledError propagate → caller graceful shutdown
    via task.cancel() + await task.
    """
    settings = _get_settings()
    if settings.hub_name == "central":
        logger.info("sync_worker_skip_central")
        return

    local_pool = app.state.db_pool
    central_pool = app.state.central_sync_pool
    hub_name_label: str = settings.hub_name

    logger.info("sync_worker_start: hub=%s", hub_name_label)

    while True:
        try:
            batch = await _claim_pending_batch(local_pool, settings.sync_batch_size)
            if not batch:
                SYNC_OUTBOX_PENDING.labels(hub_name=hub_name_label).set(0)
                await asyncio.sleep(settings.sync_poll_interval)
                continue

            SYNC_OUTBOX_PENDING.labels(hub_name=hub_name_label).set(len(batch))

            row_ids = [row.id for row in batch]
            async with local_pool.acquire() as conn:
                await conn.execute(MARK_PROCESSING_SQL, row_ids)

            inserts = [r for r in batch if r.op_type == OpType.INSERT]
            deletes = [r for r in batch if r.op_type == OpType.DELETE]

            processed_ids: list[uuid.UUID] = []
            failed_rows: list[tuple[SyncOutboxRow, BaseException]] = []
            # BLOCKER 1 FIX: track document_ids đã touched ở batch này để
            # UPDATE documents.sync_status SAU mỗi batch (D-V3-Phase4-B2 lifecycle).
            affected_document_ids: set[uuid.UUID] = set()

            if inserts:
                try:
                    await _push_inserts(central_pool, inserts)
                    processed_ids.extend([r.id for r in inserts])
                    SYNC_ATTEMPT_TOTAL.labels(
                        hub_name=hub_name_label, status="success"
                    ).inc(len(inserts))
                    _observe_lag(inserts, hub_name_label)
                except Exception as e:  # noqa: BLE001
                    for row in inserts:
                        failed_rows.append((row, e))
                    SYNC_ATTEMPT_TOTAL.labels(
                        hub_name=hub_name_label, status="fail"
                    ).inc(len(inserts))
                affected_document_ids.update(
                    r.document_id for r in inserts if r.document_id is not None
                )

            if deletes:
                try:
                    await _push_deletes(central_pool, deletes)
                    processed_ids.extend([r.id for r in deletes])
                    SYNC_ATTEMPT_TOTAL.labels(
                        hub_name=hub_name_label, status="success"
                    ).inc(len(deletes))
                    _observe_lag(deletes, hub_name_label)
                except Exception as e:  # noqa: BLE001
                    for row in deletes:
                        failed_rows.append((row, e))
                    SYNC_ATTEMPT_TOTAL.labels(
                        hub_name=hub_name_label, status="fail"
                    ).inc(len(deletes))
                affected_document_ids.update(
                    r.document_id for r in deletes if r.document_id is not None
                )

            if processed_ids:
                async with local_pool.acquire() as conn:
                    await conn.execute(MARK_PROCESSED_SQL, processed_ids)

            if failed_rows:
                await _handle_failures(
                    local_pool,
                    failed_rows,
                    settings.sync_max_attempts,
                    settings.sync_backoff_seconds,
                    hub_name_label,
                )

            # BLOCKER 1 FIX — D-V3-Phase4-B2 lifecycle UPDATE documents.sync_status
            # sau MỖI batch (sau khi MARK_PROCESSED + MARK_DEAD đã apply).
            if affected_document_ids:
                await _update_document_sync_status(
                    local_pool, list(affected_document_ids)
                )

        except asyncio.CancelledError:
            logger.info("sync_worker_cancelled: hub=%s", hub_name_label)
            raise
        except Exception as e:  # noqa: BLE001
            logger.exception(
                "sync_worker_loop_error: hub=%s err=%s", hub_name_label, e
            )
            await asyncio.sleep(settings.sync_poll_interval)


async def _claim_pending_batch(
    local_pool: Any, batch_size: int
) -> list[SyncOutboxRow]:
    """SELECT FOR UPDATE SKIP LOCKED batch — concurrency-safe (D-V3-Phase4-A5).

    Returns list của SyncOutboxRow Pydantic. Empty list nếu KHONG pending row.
    """
    async with local_pool.acquire() as conn:
        async with conn.transaction():
            records = await conn.fetch(CLAIM_PENDING_SQL, batch_size)
    return [SyncOutboxRow.model_validate(dict(r)) for r in records]


async def _push_inserts(central_pool: Any, rows: list[SyncOutboxRow]) -> None:
    """Push INSERT chunks central — ON CONFLICT (id) DO UPDATE WHERE content_hash
    IS DISTINCT (D-V3-Phase4-B1 idempotent).

    Raise propagate caller (worker loop catch để MARK_FAILED_RETRY or MARK_DEAD).
    """
    async with central_pool.acquire() as conn:
        async with conn.transaction():
            for row in rows:
                payload = ChunkPayload.model_validate(row.payload)
                await conn.execute(
                    PUSH_INSERT_CHUNK_SQL,
                    payload.id,
                    payload.document_id,
                    payload.hub_id,
                    payload.content,
                    payload.content_hash,
                    payload.heading_path,
                    payload.page_start,
                    payload.page_end,
                    payload.vector,
                    payload.metadata,
                    payload.created_at,
                )


async def _push_deletes(central_pool: Any, rows: list[SyncOutboxRow]) -> None:
    """Push DELETE chunks central — HARD DELETE (D-V3-Phase4-B3 + immutable chunks).

    Single batched DELETE FROM chunks WHERE id = ANY($1::uuid[]).
    """
    chunk_ids = [row.chunk_id for row in rows]
    async with central_pool.acquire() as conn:
        await conn.execute(PUSH_DELETE_CHUNK_SQL, chunk_ids)


async def _update_document_sync_status(
    local_pool: Any,
    document_ids: list[uuid.UUID],
) -> None:
    """BLOCKER 1 FIX — D-V3-Phase4-B2 lifecycle aggregate update.

    Aggregate sync_outbox state per document → UPDATE documents.sync_status enum:
    - 'synced':  all outbox rows processed, no dead/pending/processing
    - 'failed':  all outbox rows dead (no processed), no pending/processing
    - 'partial': mixed processed + dead, no pending/processing
    - 'syncing': còn pending/processing rows

    Idempotent — re-call cùng document_ids sau batch khác → re-aggregate state mới.

    Empty list → no-op shortcut (defensive — tránh acquire pool khi KHONG có doc).
    """
    if not document_ids:
        return
    async with local_pool.acquire() as conn:
        rows = await conn.fetch(UPDATE_DOC_SYNC_STATUS_SQL, list(document_ids))
        for row in rows:
            logger.info(
                "document_sync_status_updated: doc_id=%s sync_status=%s",
                str(row["id"]),
                row["sync_status"],
            )


async def _handle_failures(
    local_pool: Any,
    failed: list[tuple[SyncOutboxRow, BaseException]],
    max_attempts: int,
    backoff_seconds: list[int],
    hub_name_label: str,
) -> None:
    """Process failed rows — split retry vs dead based on attempt_count.

    attempt_count >= max_attempts → MARK_DEAD + SYNC_DEAD_TOTAL incr per error_class.
    Otherwise → MARK_FAILED_RETRY với backoff_seconds[attempt-1] (clamped).

    last_error truncated tới LAST_ERROR_TRUNCATE (1000 char) — defensive vs
    runaway stacktrace bloat outbox storage.
    """
    dead_ids: list[uuid.UUID] = []
    dead_errors: dict[str, list[uuid.UUID]] = {}
    last_dead_err: str = ""

    async with local_pool.acquire() as conn:
        for row, exc in failed:
            err_msg = f"{type(exc).__name__}: {exc!s}"[:LAST_ERROR_TRUNCATE]
            if row.attempt_count >= max_attempts:
                dead_ids.append(row.id)
                err_class = normalize_error_class(exc)
                dead_errors.setdefault(err_class, []).append(row.id)
                last_dead_err = err_msg
            else:
                # Backoff index = attempt_count - 1 (attempt 1 → backoff[0]).
                backoff_idx = min(
                    max(row.attempt_count - 1, 0), len(backoff_seconds) - 1
                )
                backoff = backoff_seconds[backoff_idx]
                await conn.execute(
                    MARK_FAILED_RETRY_SQL, row.id, err_msg, backoff
                )

        if dead_ids:
            await conn.execute(MARK_DEAD_SQL, dead_ids, last_dead_err)
            for err_class, ids in dead_errors.items():
                SYNC_DEAD_TOTAL.labels(
                    hub_name=hub_name_label, error_class=err_class
                ).inc(len(ids))


def _observe_lag(rows: list[SyncOutboxRow], hub_name_label: str) -> None:
    """Emit SYNC_LAG_SECONDS Histogram observe (created_at → now).

    Defensive: skip row có created_at=None; normalize naive datetime sang UTC
    để subtract safe (avoid TypeError naive vs aware).
    """
    now = datetime.now(UTC)
    for row in rows:
        if row.created_at is None:
            continue
        created = (
            row.created_at
            if row.created_at.tzinfo
            else row.created_at.replace(tzinfo=UTC)
        )
        lag = (now - created).total_seconds()
        if lag >= 0:
            SYNC_LAG_SECONDS.labels(hub_name=hub_name_label).observe(lag)


__all__ = [
    "LAST_ERROR_TRUNCATE",
    "_claim_pending_batch",
    "_handle_failures",
    "_observe_lag",
    "_push_deletes",
    "_push_inserts",
    "_update_document_sync_status",
    "sync_worker_loop",
]
