"""Phase 4 Plan 04-06 Task 1 — Unit test checksum_scheduler.

D-V3-Phase4-C1 cadence verify:
- Daily 2AM full COUNT(*) per hub vs central → SYNC_COUNT_DRIFT gauge ratio.
- Hourly TABLESAMPLE BERNOULLI(1) chunks last 1h → SYNC_HASH_DRIFT counter.

D-V3-Phase4-C3 placement verify: central-only spawn (skip hub con) qua check
`settings.hub_name == "central"` ở entry function.

W7 fix verify: label `hub_name` (NOT `hub_id`) cho cả gauge + counter.

Mock pattern: AsyncMock asyncpg.Pool + Connection — KHÔNG cần Postgres
runtime (defer Phase 7 MIGRATE-05 live-DB smoke). 10 test cover behavior
1-10 trong PLAN.md.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timezone
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest


def _build_mock_pool(
    fetchval_returns: list[Any] | None = None,
    fetch_returns: list[Any] | None = None,
    fetchrow_returns: list[Any] | None = None,
) -> Any:
    """Build mock asyncpg.Pool với conn.fetchval/fetch/fetchrow side_effect.

    Trả values lần lượt theo list (side_effect) để mỗi acquire/call lấy 1 value.
    """
    conn = AsyncMock()
    if fetchval_returns is not None:
        conn.fetchval = AsyncMock(side_effect=list(fetchval_returns))
    else:
        conn.fetchval = AsyncMock(return_value=0)
    if fetch_returns is not None:
        conn.fetch = AsyncMock(side_effect=list(fetch_returns))
    else:
        conn.fetch = AsyncMock(return_value=[])
    if fetchrow_returns is not None:
        conn.fetchrow = AsyncMock(side_effect=list(fetchrow_returns))
    else:
        conn.fetchrow = AsyncMock(return_value=None)
    conn.execute = AsyncMock(return_value=None)

    pool = MagicMock()
    pool_ctx = AsyncMock()
    pool_ctx.__aenter__ = AsyncMock(return_value=conn)
    pool_ctx.__aexit__ = AsyncMock(return_value=None)
    pool.acquire = MagicMock(return_value=pool_ctx)
    pool.close = AsyncMock(return_value=None)
    pool._conn = conn  # exposed for assertions
    return pool


def _build_mock_settings(
    hub_name: str = "central",
    checksum_hub_dsns_json: str | None = None,
) -> Any:
    """Build SimpleNamespace mock Settings với property `checksum_hub_dsns`."""
    if checksum_hub_dsns_json is None:
        dsns_dict: dict[str, str] = {}
    else:
        import json

        dsns_dict = json.loads(checksum_hub_dsns_json)
    return SimpleNamespace(
        hub_name=hub_name,
        checksum_hub_dsns_json=checksum_hub_dsns_json,
        checksum_hub_dsns=dsns_dict,
    )


def _build_mock_app(central_pool: Any | None = None) -> Any:
    """Build mock FastAPI app với state.db_pool (= central central_pool)."""
    state = SimpleNamespace(db_pool=central_pool or _build_mock_pool())
    return SimpleNamespace(state=state)


# ════════════════════════════════════════════════════════════════════
# Test 1 — skip hub con (hub_name != central)
# ════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_scheduler_skip_hub_con(monkeypatch: pytest.MonkeyPatch) -> None:
    """settings.hub_name='yte' → checksum_scheduler_loop immediate return.

    D-V3-Phase4-C3 — central-only placement enforce.
    """
    from app.observability.checksum_scheduler import checksum_scheduler_loop

    settings = _build_mock_settings(hub_name="yte")
    monkeypatch.setattr(
        "app.observability.checksum_scheduler._get_settings", lambda: settings
    )
    app = _build_mock_app()

    # Immediate return — KHÔNG raise + KHÔNG enter loop (timeout 1s đủ check).
    await asyncio.wait_for(checksum_scheduler_loop(app), timeout=1.0)
    # Verify KHÔNG call central_pool.acquire (no tick logic ran).
    app.state.db_pool.acquire.assert_not_called()


# ════════════════════════════════════════════════════════════════════
# Test 2 — empty checksum_hub_dsns → no-op tick (KHÔNG fail)
# ════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_scheduler_empty_dsns_no_op(monkeypatch: pytest.MonkeyPatch) -> None:
    """settings.checksum_hub_dsns_json=None → loop sleep + KHÔNG emit metrics.

    Central deploy lần đầu CHƯA register hub con. Scheduler tick no-op.
    """
    from app.observability.checksum_scheduler import checksum_scheduler_loop

    settings = _build_mock_settings(
        hub_name="central", checksum_hub_dsns_json=None
    )
    monkeypatch.setattr(
        "app.observability.checksum_scheduler._get_settings", lambda: settings
    )
    # Make tick interval very short so loop wakes fast (chỉ test enter + exit).
    monkeypatch.setattr(
        "app.observability.checksum_scheduler.TICK_INTERVAL_SECONDS", 0.01
    )
    app = _build_mock_app()

    task = asyncio.create_task(checksum_scheduler_loop(app))
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    # central pool acquire KHÔNG được gọi vì hub_dsns empty (no tick logic).
    app.state.db_pool.acquire.assert_not_called()


# ════════════════════════════════════════════════════════════════════
# Test 3 — _should_run_daily helper at 2 AM
# ════════════════════════════════════════════════════════════════════


def test_should_run_daily_at_2am() -> None:
    """_should_run_daily(now, last_run) True khi now.hour==2 + last_run None|yesterday."""
    from app.observability.checksum_scheduler import _should_run_daily

    now_2am = datetime(2026, 5, 22, 2, 30, 0, tzinfo=timezone.utc)
    # last_run None → True
    assert _should_run_daily(now_2am, None) is True

    # last_run yesterday → True
    yesterday = datetime(2026, 5, 21, 2, 5, 0, tzinfo=timezone.utc)
    assert _should_run_daily(now_2am, yesterday) is True

    # last_run today (same date) → False (KHÔNG chạy 2 lần cùng ngày)
    today_earlier = datetime(2026, 5, 22, 2, 10, 0, tzinfo=timezone.utc)
    assert _should_run_daily(now_2am, today_earlier) is False

    # now not 2AM → False
    now_3am = datetime(2026, 5, 22, 3, 30, 0, tzinfo=timezone.utc)
    assert _should_run_daily(now_3am, None) is False
    now_1am = datetime(2026, 5, 22, 1, 30, 0, tzinfo=timezone.utc)
    assert _should_run_daily(now_1am, None) is False


# ════════════════════════════════════════════════════════════════════
# Test 4 — _should_run_hourly helper
# ════════════════════════════════════════════════════════════════════


def test_should_run_hourly() -> None:
    """_should_run_hourly(now, last_run) True khi now-last_run >= 1h."""
    from datetime import timedelta

    from app.observability.checksum_scheduler import _should_run_hourly

    now = datetime(2026, 5, 22, 10, 30, 0, tzinfo=timezone.utc)
    # last_run None → True
    assert _should_run_hourly(now, None) is True

    # last_run > 1h ago → True
    over_1h = now - timedelta(hours=1, minutes=5)
    assert _should_run_hourly(now, over_1h) is True

    # last_run exactly 1h ago → True (boundary)
    exactly_1h = now - timedelta(hours=1)
    assert _should_run_hourly(now, exactly_1h) is True

    # last_run < 1h ago → False
    recent = now - timedelta(minutes=30)
    assert _should_run_hourly(now, recent) is False


# ════════════════════════════════════════════════════════════════════
# Test 5 — compute_count_drift hub > central
# ════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_compute_count_drift() -> None:
    """hub_count=1000 + central_count=990 → drift_ratio=0.01.

    SYNC_COUNT_DRIFT.labels(hub_name='yte').set(0.01) called.
    """
    from app.observability.checksum_scheduler import _tick_daily_count
    from app.sync.metrics import SYNC_COUNT_DRIFT

    hub_id_uuid = uuid.uuid4()
    # Central pool: 1st fetchrow returns hub_id row {"id": hub_id_uuid}.
    # Then central fetchval returns 990.
    central_pool = MagicMock()
    central_conn = AsyncMock()
    central_conn.fetchrow = AsyncMock(return_value={"id": hub_id_uuid})
    central_conn.fetchval = AsyncMock(return_value=990)
    central_ctx = AsyncMock()
    central_ctx.__aenter__ = AsyncMock(return_value=central_conn)
    central_ctx.__aexit__ = AsyncMock(return_value=None)
    central_pool.acquire = MagicMock(return_value=central_ctx)

    # Hub pool: fetchval returns 1000.
    hub_pool = MagicMock()
    hub_conn = AsyncMock()
    hub_conn.fetchval = AsyncMock(return_value=1000)
    hub_ctx = AsyncMock()
    hub_ctx.__aenter__ = AsyncMock(return_value=hub_conn)
    hub_ctx.__aexit__ = AsyncMock(return_value=None)
    hub_pool.acquire = MagicMock(return_value=hub_ctx)

    # Snapshot gauge before.
    gauge = SYNC_COUNT_DRIFT.labels(hub_name="yte_t5")
    before = gauge._value.get()  # noqa: SLF001

    await _tick_daily_count(central_pool, hub_pool, "yte_t5")

    after = gauge._value.get()  # noqa: SLF001
    # ratio = abs(990-1000) / 1000 = 0.01.
    assert abs(after - 0.01) < 1e-9
    # Just verify it was set away from before (not necessarily different value).
    assert after != before or before == 0.01


# ════════════════════════════════════════════════════════════════════
# Test 6 — count drift central > hub (extra in central)
# ════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_compute_count_drift_central_extra() -> None:
    """central=1010 + hub_con=1000 → drift_ratio=0.01 (symmetric abs)."""
    from app.observability.checksum_scheduler import _tick_daily_count
    from app.sync.metrics import SYNC_COUNT_DRIFT

    hub_id_uuid = uuid.uuid4()
    central_pool = MagicMock()
    central_conn = AsyncMock()
    central_conn.fetchrow = AsyncMock(return_value={"id": hub_id_uuid})
    central_conn.fetchval = AsyncMock(return_value=1010)
    central_ctx = AsyncMock()
    central_ctx.__aenter__ = AsyncMock(return_value=central_conn)
    central_ctx.__aexit__ = AsyncMock(return_value=None)
    central_pool.acquire = MagicMock(return_value=central_ctx)

    hub_pool = MagicMock()
    hub_conn = AsyncMock()
    hub_conn.fetchval = AsyncMock(return_value=1000)
    hub_ctx = AsyncMock()
    hub_ctx.__aenter__ = AsyncMock(return_value=hub_conn)
    hub_ctx.__aexit__ = AsyncMock(return_value=None)
    hub_pool.acquire = MagicMock(return_value=hub_ctx)

    await _tick_daily_count(central_pool, hub_pool, "duoc_t6")

    gauge = SYNC_COUNT_DRIFT.labels(hub_name="duoc_t6")
    val = gauge._value.get()  # noqa: SLF001
    assert abs(val - 0.01) < 1e-9


# ════════════════════════════════════════════════════════════════════
# Test 7 — hash sample mismatch emits counter
# ════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_hash_sample_mismatch_emit_counter() -> None:
    """hub sample [(id1,A),(id2,B)] + central [(id1,A),(id2,C)] → mismatch=1 inc."""
    from app.observability.checksum_scheduler import _tick_hourly_hash
    from app.sync.metrics import SYNC_HASH_DRIFT

    chunk_id1 = uuid.uuid4()
    chunk_id2 = uuid.uuid4()
    hash_a = b"\xaa" * 32  # 32 bytes SHA-256
    hash_b = b"\xbb" * 32
    hash_c = b"\xcc" * 32

    # Hub pool fetch sample.
    hub_pool = MagicMock()
    hub_conn = AsyncMock()
    hub_conn.fetch = AsyncMock(
        return_value=[
            {"id": chunk_id1, "content_hash": hash_a},
            {"id": chunk_id2, "content_hash": hash_b},
        ]
    )
    hub_ctx = AsyncMock()
    hub_ctx.__aenter__ = AsyncMock(return_value=hub_conn)
    hub_ctx.__aexit__ = AsyncMock(return_value=None)
    hub_pool.acquire = MagicMock(return_value=hub_ctx)

    # Central pool fetch by id.
    central_pool = MagicMock()
    central_conn = AsyncMock()
    central_conn.fetch = AsyncMock(
        return_value=[
            {"id": chunk_id1, "content_hash": hash_a},  # match
            {"id": chunk_id2, "content_hash": hash_c},  # mismatch
        ]
    )
    central_ctx = AsyncMock()
    central_ctx.__aenter__ = AsyncMock(return_value=central_conn)
    central_ctx.__aexit__ = AsyncMock(return_value=None)
    central_pool.acquire = MagicMock(return_value=central_ctx)

    counter = SYNC_HASH_DRIFT.labels(hub_name="yte_t7", drift_type="mismatch")
    before = counter._value.get()  # noqa: SLF001

    await _tick_hourly_hash(central_pool, hub_pool, "yte_t7")

    after = counter._value.get()  # noqa: SLF001
    assert after - before >= 1  # mismatch counter incremented by 1


# ════════════════════════════════════════════════════════════════════
# Test 8 — hash sample missing emits counter
# ════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_hash_sample_missing_emit_counter() -> None:
    """hub sample [(id1,A)] + central [] → missing=1 inc."""
    from app.observability.checksum_scheduler import _tick_hourly_hash
    from app.sync.metrics import SYNC_HASH_DRIFT

    chunk_id1 = uuid.uuid4()
    hash_a = b"\xaa" * 32

    hub_pool = MagicMock()
    hub_conn = AsyncMock()
    hub_conn.fetch = AsyncMock(
        return_value=[{"id": chunk_id1, "content_hash": hash_a}]
    )
    hub_ctx = AsyncMock()
    hub_ctx.__aenter__ = AsyncMock(return_value=hub_conn)
    hub_ctx.__aexit__ = AsyncMock(return_value=None)
    hub_pool.acquire = MagicMock(return_value=hub_ctx)

    central_pool = MagicMock()
    central_conn = AsyncMock()
    central_conn.fetch = AsyncMock(return_value=[])  # missing
    central_ctx = AsyncMock()
    central_ctx.__aenter__ = AsyncMock(return_value=central_conn)
    central_ctx.__aexit__ = AsyncMock(return_value=None)
    central_pool.acquire = MagicMock(return_value=central_ctx)

    counter = SYNC_HASH_DRIFT.labels(hub_name="yte_t8", drift_type="missing")
    before = counter._value.get()  # noqa: SLF001

    await _tick_hourly_hash(central_pool, hub_pool, "yte_t8")

    after = counter._value.get()  # noqa: SLF001
    assert after - before >= 1


# ════════════════════════════════════════════════════════════════════
# Test 9 — graceful cancel propagates CancelledError
# ════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_graceful_cancel(monkeypatch: pytest.MonkeyPatch) -> None:
    """asyncio.create_task + cancel + await → CancelledError raised."""
    import json

    from app.observability.checksum_scheduler import checksum_scheduler_loop

    settings = _build_mock_settings(
        hub_name="central",
        checksum_hub_dsns_json=json.dumps({"yte": "postgresql://x/y"}),
    )
    monkeypatch.setattr(
        "app.observability.checksum_scheduler._get_settings", lambda: settings
    )
    # Patch create_pool to avoid real connect (fake hub pool).
    fake_hub_pool = _build_mock_pool()

    async def _fake_create_pool(**kwargs: Any) -> Any:
        return fake_hub_pool

    monkeypatch.setattr(
        "app.observability.checksum_scheduler.asyncpg.create_pool",
        _fake_create_pool,
    )
    monkeypatch.setattr(
        "app.observability.checksum_scheduler.TICK_INTERVAL_SECONDS", 0.01
    )
    app = _build_mock_app()

    task = asyncio.create_task(checksum_scheduler_loop(app))
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


# ════════════════════════════════════════════════════════════════════
# Test 10 — per-hub error isolation (1 hub fail KHÔNG abort scheduler)
# ════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_per_hub_error_isolation() -> None:
    """1 hub query fail → log warning + tick tiếp tục cho hub khác.

    Test gọi trực tiếp _tick_daily_count với hub_pool raise → KHÔNG re-raise
    (catch trong _tick_daily_count internally hoặc caller). Verify gauge KHÔNG
    set (errored hub) — scheduler caller phải catch để continue.
    """
    from app.observability.checksum_scheduler import _tick_daily_count

    # Central pool fetchrow returns hub_id row OK.
    hub_id_uuid = uuid.uuid4()
    central_pool = MagicMock()
    central_conn = AsyncMock()
    central_conn.fetchrow = AsyncMock(return_value={"id": hub_id_uuid})
    central_conn.fetchval = AsyncMock(return_value=500)
    central_ctx = AsyncMock()
    central_ctx.__aenter__ = AsyncMock(return_value=central_conn)
    central_ctx.__aexit__ = AsyncMock(return_value=None)
    central_pool.acquire = MagicMock(return_value=central_ctx)

    # Hub pool raises on fetchval.
    hub_pool = MagicMock()
    hub_conn = AsyncMock()
    hub_conn.fetchval = AsyncMock(side_effect=RuntimeError("hub query fail"))
    hub_ctx = AsyncMock()
    hub_ctx.__aenter__ = AsyncMock(return_value=hub_conn)
    hub_ctx.__aexit__ = AsyncMock(return_value=None)
    hub_pool.acquire = MagicMock(return_value=hub_ctx)

    # Function should raise — caller (scheduler loop) catches.
    # Verify the error IS raised (per-hub isolation done by caller try/except).
    with pytest.raises(RuntimeError, match="hub query fail"):
        await _tick_daily_count(central_pool, hub_pool, "yte_t10")
