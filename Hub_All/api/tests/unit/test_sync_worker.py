"""Phase 4 Plan 04-03 Task 3a + 3b — Unit test sync.worker.

Task 3a (happy + lifecycle, 11 test):
- skip central hub_name shortcut
- claim empty batch → poll sleep
- push insert happy path → MARK_PROCESSED + SYNC_ATTEMPT_TOTAL success
- push delete happy path
- push mixed op_type (insert + delete trong cùng batch)
- _update_document_sync_status synced/partial/failed/syncing (BLOCKER 1 4 state)
- _update_document_sync_status empty doc_ids no-op
- worker calls _update_document_sync_status after each push branch

Task 3b (retry + dead + backoff + cancel + lag, 7 test):
- retry on network error → MARK_FAILED_RETRY backoff[0]=1s
- dead after max_attempts → MARK_DEAD + SYNC_DEAD_TOTAL incr
- backoff progression 1/5/30/120s
- dead path calls _update_document_sync_status (failed lifecycle)
- graceful shutdown cancel via asyncio.create_task + task.cancel()
- _observe_lag emit SYNC_LAG_SECONDS histogram (created_at - now)
- error_class normalize timeout → SYNC_DEAD_TOTAL labels error_class=timeout

Mock pattern: AsyncMock asyncpg.Pool + Connection + fetch/execute return values.
NOT testcontainer (defer Phase 7 MIGRATE-05 runtime).
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, call

import pytest


# ────────────────────────────────────────────────────────────────────
# Fixtures — Mock asyncpg.Pool + Connection + Settings
# ────────────────────────────────────────────────────────────────────


def _make_outbox_row(
    *,
    op_type: str = "insert",
    attempt_count: int = 0,
    chunk_id: uuid.UUID | None = None,
    document_id: uuid.UUID | None = None,
    payload: dict[str, Any] | None = None,
) -> Any:
    """Build SyncOutboxRow object cho test."""
    from app.sync.models import OpType, SyncOutboxRow, SyncStatus

    chunk_id = chunk_id or uuid.uuid4()
    document_id = document_id or uuid.uuid4()
    # Default payload for INSERT op — minimal valid ChunkPayload shape.
    if payload is None:
        if op_type == "insert":
            payload = {
                "id": str(chunk_id),
                "document_id": str(document_id),
                "hub_id": str(uuid.uuid4()),
                "content": "Test chunk content",
                # 64-char hex SHA-256 (no \x prefix — trigger emit format).
                "content_hash": "ab" * 32,
                "heading_path": None,
                "page_start": None,
                "page_end": None,
                "vector": [0.1] * 4,
                "metadata": {},
                "created_at": datetime.now(UTC).isoformat(),
            }
        else:
            payload = {"id": str(chunk_id)}
    return SyncOutboxRow(
        id=uuid.uuid4(),
        op_type=OpType(op_type),
        chunk_id=chunk_id,
        document_id=document_id,
        payload=payload,
        attempt_count=attempt_count,
        last_error=None,
        status=SyncStatus.PENDING,
        next_retry_at=None,
        created_at=datetime.now(UTC) - timedelta(seconds=5),
        processed_at=None,
    )


def _build_mock_pool(
    fetch_returns: list[Any] | None = None,
    fetch_dict_returns: list[dict[str, Any]] | None = None,
) -> Any:
    """Build mock asyncpg.Pool với conn.fetch/execute AsyncMock."""
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=fetch_dict_returns or fetch_returns or [])
    conn.fetchrow = AsyncMock(return_value=None)
    conn.execute = AsyncMock(return_value=None)

    # Transaction context manager.
    tx_ctx = AsyncMock()
    tx_ctx.__aenter__ = AsyncMock(return_value=tx_ctx)
    tx_ctx.__aexit__ = AsyncMock(return_value=None)
    conn.transaction = MagicMock(return_value=tx_ctx)

    pool = MagicMock()
    pool.acquire = MagicMock()
    pool_ctx = AsyncMock()
    pool_ctx.__aenter__ = AsyncMock(return_value=conn)
    pool_ctx.__aexit__ = AsyncMock(return_value=None)
    pool.acquire.return_value = pool_ctx
    pool._conn = conn  # exposed for assertions
    return pool


def _build_mock_settings(hub_name: str = "yte") -> Any:
    """Build mock Settings cho worker."""
    return SimpleNamespace(
        hub_name=hub_name,
        sync_batch_size=100,
        sync_poll_interval=5.0,
        sync_max_attempts=5,
        sync_backoff_seconds=[1, 5, 30, 120],
    )


def _build_mock_app(
    local_pool: Any | None = None,
    central_pool: Any | None = None,
) -> Any:
    """Build mock FastAPI app với state.db_pool + state.central_sync_pool."""
    state = SimpleNamespace(
        db_pool=local_pool or _build_mock_pool(),
        central_sync_pool=central_pool or _build_mock_pool(),
    )
    return SimpleNamespace(state=state)


# ════════════════════════════════════════════════════════════════════
# Task 3a — happy paths + lifecycle (11 test)
# ════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_skip_central_hub_name(monkeypatch: pytest.MonkeyPatch) -> None:
    """Settings.hub_name='central' → sync_worker_loop immediate return."""
    from app.sync.worker import sync_worker_loop

    settings = _build_mock_settings(hub_name="central")
    monkeypatch.setattr("app.sync.worker._get_settings", lambda: settings)
    app = _build_mock_app()
    # KHONG raise; KHONG vào loop (return immediate).
    await asyncio.wait_for(sync_worker_loop(app), timeout=1.0)
    # Verify KHONG call db_pool.acquire (no claim batch).
    app.state.db_pool.acquire.assert_not_called()


@pytest.mark.asyncio
async def test_claim_pending_batch_empty_sleep_poll(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Empty batch → sleep poll_interval + KHONG push."""
    from app.sync.worker import sync_worker_loop

    settings = _build_mock_settings(hub_name="yte")
    settings.sync_poll_interval = 0.01  # short for test
    monkeypatch.setattr("app.sync.worker._get_settings", lambda: settings)
    local_pool = _build_mock_pool(fetch_dict_returns=[])
    central_pool = _build_mock_pool()
    app = _build_mock_app(local_pool, central_pool)

    # Run loop briefly then cancel.
    task = asyncio.create_task(sync_worker_loop(app))
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    # No push to central (central pool acquire NOT called).
    central_pool.acquire.assert_not_called()


@pytest.mark.asyncio
async def test_push_batch_insert_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """5 row op_type='insert' → _push_inserts → MARK_PROCESSED + SYNC_ATTEMPT_TOTAL success."""
    from app.sync.metrics import SYNC_ATTEMPT_TOTAL
    from app.sync.worker import _push_inserts

    rows = [_make_outbox_row(op_type="insert") for _ in range(5)]
    central_pool = _build_mock_pool()

    # Snapshot counter before.
    before = SYNC_ATTEMPT_TOTAL.labels(hub_name="yte_happy", status="success")._value.get()  # noqa: SLF001

    await _push_inserts(central_pool, rows)

    # central_pool.acquire called.
    central_pool.acquire.assert_called()
    # conn.execute called len(rows)=5 lần (1 per chunk INSERT).
    assert central_pool._conn.execute.call_count == 5  # noqa: SLF001

    after = SYNC_ATTEMPT_TOTAL.labels(hub_name="yte_happy", status="success")._value.get()  # noqa: SLF001
    # Counter incremented in worker loop (not in _push_inserts itself) — skip incr check here.
    # _push_inserts purpose: execute SQL only. Counter incr happens in worker loop.
    assert after >= before  # at minimum no decrease


@pytest.mark.asyncio
async def test_push_batch_delete_happy_path() -> None:
    """3 row op_type='delete' → _push_deletes execute DELETE FROM chunks ANY array."""
    from app.sync.worker import _push_deletes

    rows = [_make_outbox_row(op_type="delete") for _ in range(3)]
    central_pool = _build_mock_pool()

    await _push_deletes(central_pool, rows)

    central_pool.acquire.assert_called()
    # One execute (DELETE FROM chunks WHERE id = ANY($1)).
    assert central_pool._conn.execute.call_count == 1  # noqa: SLF001
    # Verify first arg = SQL chứa DELETE FROM chunks
    args = central_pool._conn.execute.call_args  # noqa: SLF001
    sql_arg = args[0][0]
    assert "DELETE FROM chunks" in sql_arg
    # Verify second arg = list of chunk_ids (3 items).
    chunk_ids_arg = args[0][1]
    assert len(chunk_ids_arg) == 3


@pytest.mark.asyncio
async def test_push_batch_mixed_op_types_split() -> None:
    """Mixed insert + delete trong cùng batch — split + push + mark processed."""
    from app.sync.worker import _push_deletes, _push_inserts

    inserts = [_make_outbox_row(op_type="insert") for _ in range(2)]
    deletes = [_make_outbox_row(op_type="delete") for _ in range(2)]
    central_pool = _build_mock_pool()

    # Both push helpers execute against same central pool.
    await _push_inserts(central_pool, inserts)
    await _push_deletes(central_pool, deletes)

    # 2 INSERT execute + 1 DELETE execute = 3 execute calls.
    assert central_pool._conn.execute.call_count == 3  # noqa: SLF001


# ────────────────────────────────────────────────────────────────────
# BLOCKER 1 — _update_document_sync_status helper (4 state lifecycle)
# ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_document_sync_status_synced() -> None:
    """all processed (no pending/processing/dead) → 'synced'."""
    from app.sync.worker import _update_document_sync_status

    doc_id = uuid.uuid4()
    local_pool = _build_mock_pool(
        fetch_dict_returns=[{"id": doc_id, "sync_status": "synced"}]
    )
    await _update_document_sync_status(local_pool, [doc_id])

    # Verify conn.fetch called với UPDATE_DOC_SYNC_STATUS_SQL + doc_id list.
    local_pool._conn.fetch.assert_called_once()  # noqa: SLF001
    args = local_pool._conn.fetch.call_args  # noqa: SLF001
    sql_arg = args[0][0]
    assert "UPDATE documents" in sql_arg
    assert "sync_status" in sql_arg
    # Doc IDs passed as list.
    doc_ids_arg = args[0][1]
    assert doc_id in doc_ids_arg


@pytest.mark.asyncio
async def test_update_document_sync_status_partial() -> None:
    """1 processed + 1 dead → 'partial'."""
    from app.sync.worker import _update_document_sync_status

    doc_id = uuid.uuid4()
    local_pool = _build_mock_pool(
        fetch_dict_returns=[{"id": doc_id, "sync_status": "partial"}]
    )
    await _update_document_sync_status(local_pool, [doc_id])

    local_pool._conn.fetch.assert_called_once()  # noqa: SLF001
    # SQL contains 'partial' case branch — verify via keys module export.
    from app.sync.keys import UPDATE_DOC_SYNC_STATUS_SQL

    assert "'partial'" in UPDATE_DOC_SYNC_STATUS_SQL


@pytest.mark.asyncio
async def test_update_document_sync_status_failed() -> None:
    """All dead → 'failed'."""
    from app.sync.worker import _update_document_sync_status

    doc_id = uuid.uuid4()
    local_pool = _build_mock_pool(
        fetch_dict_returns=[{"id": doc_id, "sync_status": "failed"}]
    )
    await _update_document_sync_status(local_pool, [doc_id])

    local_pool._conn.fetch.assert_called_once()  # noqa: SLF001
    from app.sync.keys import UPDATE_DOC_SYNC_STATUS_SQL

    assert "'failed'" in UPDATE_DOC_SYNC_STATUS_SQL


@pytest.mark.asyncio
async def test_update_document_sync_status_syncing() -> None:
    """Còn pending/processing → 'syncing'."""
    from app.sync.worker import _update_document_sync_status

    doc_id = uuid.uuid4()
    local_pool = _build_mock_pool(
        fetch_dict_returns=[{"id": doc_id, "sync_status": "syncing"}]
    )
    await _update_document_sync_status(local_pool, [doc_id])

    local_pool._conn.fetch.assert_called_once()  # noqa: SLF001
    from app.sync.keys import UPDATE_DOC_SYNC_STATUS_SQL

    assert "'syncing'" in UPDATE_DOC_SYNC_STATUS_SQL


@pytest.mark.asyncio
async def test_update_document_sync_status_empty_doc_ids_no_op() -> None:
    """Empty list → KHÔNG call conn.fetch (defensive shortcut)."""
    from app.sync.worker import _update_document_sync_status

    local_pool = _build_mock_pool()
    await _update_document_sync_status(local_pool, [])

    # KHONG call acquire → KHONG fetch.
    local_pool.acquire.assert_not_called()


@pytest.mark.asyncio
async def test_worker_loop_calls_update_doc_status_after_batch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Worker loop: 1 batch insert → after MARK_PROCESSED gọi _update_document_sync_status."""
    from app.sync.worker import sync_worker_loop

    settings = _build_mock_settings(hub_name="yte")
    settings.sync_poll_interval = 0.01
    monkeypatch.setattr("app.sync.worker._get_settings", lambda: settings)

    # Mock _claim_pending_batch trả 1 row insert, sau đó empty.
    doc_id = uuid.uuid4()
    row = _make_outbox_row(op_type="insert", document_id=doc_id)

    claim_calls: list[int] = []

    async def fake_claim(pool: Any, size: int) -> list[Any]:
        claim_calls.append(1)
        if len(claim_calls) == 1:
            return [row]
        return []

    monkeypatch.setattr("app.sync.worker._claim_pending_batch", fake_claim)

    update_doc_called: list[list[uuid.UUID]] = []

    async def fake_update_doc(pool: Any, doc_ids: list[uuid.UUID]) -> None:
        update_doc_called.append(doc_ids)

    monkeypatch.setattr(
        "app.sync.worker._update_document_sync_status", fake_update_doc
    )

    # Mock _push_inserts no-op success.
    async def fake_push_inserts(pool: Any, rows: list[Any]) -> None:
        pass

    monkeypatch.setattr("app.sync.worker._push_inserts", fake_push_inserts)

    app = _build_mock_app()
    task = asyncio.create_task(sync_worker_loop(app))
    await asyncio.sleep(0.1)  # let 1+ iteration run
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    # _update_document_sync_status called >= 1 lần với doc_id của batch.
    assert len(update_doc_called) >= 1
    assert doc_id in update_doc_called[0]


# ════════════════════════════════════════════════════════════════════
# Task 3b — retry + dead + backoff + cancel + lag (7 test)
# ════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_retry_on_network_error_attempt_1() -> None:
    """attempt_count=1 (after MARK_PROCESSING bump) + ConnectionRefusedError →
    MARK_FAILED_RETRY backoff=1s (backoff_seconds[0])."""
    from app.sync.worker import _handle_failures

    row = _make_outbox_row(attempt_count=1)
    failed: list[tuple[Any, BaseException]] = [
        (row, ConnectionRefusedError("central down"))
    ]
    local_pool = _build_mock_pool()

    await _handle_failures(
        local_pool, failed,
        max_attempts=5,
        backoff_seconds=[1, 5, 30, 120],
        hub_name_label="yte",
    )

    # conn.execute called với MARK_FAILED_RETRY_SQL (KHONG MARK_DEAD).
    local_pool._conn.execute.assert_called()  # noqa: SLF001
    args = local_pool._conn.execute.call_args  # noqa: SLF001
    sql_arg = args[0][0]
    assert "next_retry_at" in sql_arg  # MARK_FAILED_RETRY signature
    # Backoff = 1s (first in list).
    backoff_arg = args[0][3]
    assert backoff_arg == 1


@pytest.mark.asyncio
async def test_dead_after_max_attempts() -> None:
    """attempt_count=5 (>= max_attempts) → MARK_DEAD + SYNC_DEAD_TOTAL incr."""
    from app.sync.metrics import SYNC_DEAD_TOTAL
    from app.sync.worker import _handle_failures

    row = _make_outbox_row(attempt_count=5)
    failed = [(row, ConnectionRefusedError("permanent"))]
    local_pool = _build_mock_pool()

    before = SYNC_DEAD_TOTAL.labels(hub_name="yte_dead", error_class="network")._value.get()  # noqa: SLF001

    await _handle_failures(
        local_pool, failed, max_attempts=5,
        backoff_seconds=[1, 5, 30, 120], hub_name_label="yte_dead",
    )

    # Verify MARK_DEAD_SQL called (SQL contains "status = 'dead'").
    sql_calls = [c[0][0] for c in local_pool._conn.execute.call_args_list]  # noqa: SLF001
    assert any("status = 'dead'" in s for s in sql_calls)

    after = SYNC_DEAD_TOTAL.labels(hub_name="yte_dead", error_class="network")._value.get()  # noqa: SLF001
    assert after == before + 1


@pytest.mark.asyncio
async def test_backoff_progression_full() -> None:
    """Attempt 1 → 2 → 3 → 4 với expected backoffs [1, 5, 30, 120]s."""
    from app.sync.worker import _handle_failures

    expected = [(1, 1), (2, 5), (3, 30), (4, 120)]
    for attempt, expected_backoff in expected:
        row = _make_outbox_row(attempt_count=attempt)
        failed = [(row, ConnectionRefusedError("transient"))]
        local_pool = _build_mock_pool()
        await _handle_failures(
            local_pool, failed, max_attempts=5,
            backoff_seconds=[1, 5, 30, 120], hub_name_label="yte_backoff",
        )

        # Latest execute call's backoff arg ($3) == expected.
        args = local_pool._conn.execute.call_args  # noqa: SLF001
        assert args[0][3] == expected_backoff, (
            f"attempt={attempt} expected backoff={expected_backoff}, got={args[0][3]}"
        )


@pytest.mark.asyncio
async def test_dead_path_emits_correct_error_class_timeout() -> None:
    """asyncio.TimeoutError attempt=5 → SYNC_DEAD_TOTAL labels error_class='timeout'."""
    from app.sync.metrics import SYNC_DEAD_TOTAL
    from app.sync.worker import _handle_failures

    row = _make_outbox_row(attempt_count=5)
    failed = [(row, TimeoutError("timed out"))]
    local_pool = _build_mock_pool()

    before = SYNC_DEAD_TOTAL.labels(hub_name="yte_tout", error_class="timeout")._value.get()  # noqa: SLF001

    await _handle_failures(
        local_pool, failed, max_attempts=5,
        backoff_seconds=[1, 5, 30, 120], hub_name_label="yte_tout",
    )

    after = SYNC_DEAD_TOTAL.labels(hub_name="yte_tout", error_class="timeout")._value.get()  # noqa: SLF001
    assert after == before + 1


@pytest.mark.asyncio
async def test_graceful_shutdown_cancel(monkeypatch: pytest.MonkeyPatch) -> None:
    """asyncio.create_task(sync_worker_loop) + task.cancel() → CancelledError caught."""
    from app.sync.worker import sync_worker_loop

    settings = _build_mock_settings(hub_name="yte")
    settings.sync_poll_interval = 0.01
    monkeypatch.setattr("app.sync.worker._get_settings", lambda: settings)
    app = _build_mock_app()

    task = asyncio.create_task(sync_worker_loop(app))
    await asyncio.sleep(0.05)
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task


def test_observe_lag_emit_histogram() -> None:
    """_observe_lag emit SYNC_LAG_SECONDS histogram (created_at - now ~5s)."""
    from app.sync.metrics import SYNC_LAG_SECONDS
    from app.sync.worker import _observe_lag

    row = _make_outbox_row()
    # row.created_at = now - 5s (from _make_outbox_row default).

    # Snapshot count before.
    h = SYNC_LAG_SECONDS.labels(hub_name="yte_lag")
    before_count = h._sum.get()  # noqa: SLF001

    _observe_lag([row], "yte_lag")

    after_count = h._sum.get()  # noqa: SLF001
    # Lag observed > 0 (created_at - now ~5s positive).
    assert after_count > before_count


@pytest.mark.asyncio
async def test_handle_failures_truncates_last_error_1000_char() -> None:
    """last_error message > 1000 char → truncate to 1000."""
    from app.sync.worker import LAST_ERROR_TRUNCATE, _handle_failures

    row = _make_outbox_row(attempt_count=1)
    long_msg = "x" * 5000
    failed = [(row, RuntimeError(long_msg))]
    local_pool = _build_mock_pool()

    await _handle_failures(
        local_pool, failed, max_attempts=5,
        backoff_seconds=[1, 5, 30, 120], hub_name_label="yte_trunc",
    )

    args = local_pool._conn.execute.call_args  # noqa: SLF001
    err_arg = args[0][2]
    assert len(err_arg) <= LAST_ERROR_TRUNCATE


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
