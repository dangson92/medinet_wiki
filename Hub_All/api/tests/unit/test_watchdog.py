"""Unit test watchdog — Plan 04-05 REVISION 2 (INGEST-06, P8 + WARNING #7 + 5min timeout).

Lưu ý: technically là integration (cần Postgres testcontainer) nhưng đặt unit/
vì test query logic isolated KHÔNG cần FastAPI app/lifespan/auth router.

Reuse fixtures Phase 3 Plan 03-05:
- postgres_container (scope=module)
- alembic_cfg

Test cover:
1. test_watchdog_flips_stuck_processing — 6 min stale → flip (REVISION 2 — 5min threshold).
2. test_watchdog_skips_recent_processing — 1 min recent → KHÔNG flip.
3. test_watchdog_respects_5min_timeout — REVISION 2 NEW — boundary 3min vs 6min.
4. test_watchdog_skips_pending — pending status → KHÔNG flip.
5. test_watchdog_skips_null_heartbeat_processing — WARNING #7 NULL guard.
6. test_watchdog_empty_db — DB trống → return 0.
"""
from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from typing import Any

import pytest
from alembic.config import Config
from sqlalchemy import text


@pytest.fixture
async def watchdog_db(
    alembic_cfg: Config,
) -> AsyncIterator[None]:
    """Setup DB + alembic upgrade + init_engine cho watchdog_tick.

    alembic_cfg đã setEnv DATABASE_URL/COCOINDEX_DATABASE_URL từ postgres_container.
    Function-scope: re-init engine mỗi test để cô lập state.
    """
    from alembic import command

    # alembic upgrade qua to_thread (env.py dùng asyncio.run nội bộ).
    await asyncio.to_thread(command.upgrade, alembic_cfg, "head")

    # Init engine cho watchdog_tick gọi get_engine().
    from app.config import get_settings
    from app.db.session import dispose_engine, init_engine

    await dispose_engine()  # reset state nếu test trước có init
    get_settings.cache_clear()
    init_engine(get_settings())

    yield

    await dispose_engine()


async def _seed_hub_document(
    *,
    status: str,
    last_heartbeat_offset_minutes: int | None,
) -> str:
    """INSERT 1 hub + 1 document. Return document_id (string UUID).

    Args:
        status: 'pending' | 'processing' | 'completed' | 'failed' | 'failed_unsupported'.
        last_heartbeat_offset_minutes:
            None → INSERT với last_heartbeat=NULL (WARNING #7 test case).
            int → INSERT với last_heartbeat = NOW() - INTERVAL '<offset> minutes'.
    """
    from app.db.session import get_engine

    engine = get_engine()
    hub_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO hubs (id, slug, name, is_active, created_at) "
                "VALUES (:id, :slug, 'h', TRUE, NOW())"
            ),
            {"id": str(hub_id), "slug": f"hub-{hub_id.hex[:8]}"},
        )
        hb_clause = (
            f"NOW() - INTERVAL '{last_heartbeat_offset_minutes} minutes'"
            if last_heartbeat_offset_minutes is not None
            else "NULL"
        )
        await conn.execute(
            text(
                f"INSERT INTO documents "
                f"(id, hub_id, filename, file_path, status, attempts, chunk_count, "
                f"last_heartbeat, created_at, updated_at) "
                f"VALUES (:id, :hub, 'x.docx', '/tmp/x.docx', :status, 0, 0, "
                f"{hb_clause}, NOW(), NOW())"
            ),
            {"id": str(doc_id), "hub": str(hub_id), "status": status},
        )
    return str(doc_id)


@pytest.mark.critical
@pytest.mark.integration
@pytest.mark.asyncio
async def test_watchdog_flips_stuck_processing(watchdog_db: Any) -> None:
    """Row processing với last_heartbeat=6 min ago → flip thành failed (REVISION 2 — 5min threshold)."""
    _ = watchdog_db
    from app.db.session import get_engine
    from app.services.watchdog import watchdog_tick

    doc_id = await _seed_hub_document(
        status="processing", last_heartbeat_offset_minutes=6
    )
    count = await watchdog_tick()
    assert count == 1, f"6min stale processing phải bị flip, got count={count}"

    engine = get_engine()
    async with engine.connect() as conn:
        row = (
            await conn.execute(
                text("SELECT status, error_message FROM documents WHERE id=:id"),
                {"id": doc_id},
            )
        ).fetchone()
    assert row is not None
    assert row[0] == "failed", f"status phải 'failed', got {row[0]}"
    assert "timeout" in row[1], f"error_message phải chứa 'timeout', got {row[1]!r}"
    assert "heartbeat" in row[1], f"error_message phải chứa 'heartbeat', got {row[1]!r}"


@pytest.mark.critical
@pytest.mark.integration
@pytest.mark.asyncio
async def test_watchdog_skips_recent_processing(watchdog_db: Any) -> None:
    """last_heartbeat=1 min ago (< 5 min REVISION 2 threshold) → KHÔNG flip."""
    _ = watchdog_db
    from app.db.session import get_engine
    from app.services.watchdog import watchdog_tick

    doc_id = await _seed_hub_document(
        status="processing", last_heartbeat_offset_minutes=1
    )
    count = await watchdog_tick()
    assert count == 0, f"1min recent KHÔNG được flip (< 5min), got count={count}"

    engine = get_engine()
    async with engine.connect() as conn:
        row = (
            await conn.execute(
                text("SELECT status FROM documents WHERE id=:id"),
                {"id": doc_id},
            )
        ).fetchone()
    assert row is not None
    assert row[0] == "processing", f"status phải GIỮ 'processing', got {row[0]}"


@pytest.mark.critical
@pytest.mark.integration
@pytest.mark.asyncio
async def test_watchdog_respects_5min_timeout(watchdog_db: Any) -> None:
    """REVISION 2 NEW — Test 5min timeout boundary.

    Cocoindex 1.0.3 update_blocking documents lớn (>2 phút) bình thường — watchdog
    timeout 2 phút sẽ false-flip. REVISION 2 tăng lên 5 phút headroom.

    Verify boundary:
    - last_heartbeat=NOW()-3min → KHÔNG flip (3 < 5 phút).
    - last_heartbeat=NOW()-6min → flip (6 > 5 phút).
    """
    _ = watchdog_db
    from app.db.session import get_engine
    from app.services.watchdog import watchdog_tick

    # 3 min ago — KHÔNG flip (REVISION 2 — under 5min threshold).
    doc_id_3min = await _seed_hub_document(
        status="processing", last_heartbeat_offset_minutes=3
    )
    count = await watchdog_tick()
    assert count == 0, (
        f"REVISION 2 violated — 3min last_heartbeat KHÔNG được flip "
        f"(< 5min threshold), got count={count}"
    )

    # 6 min ago — flip (over threshold).
    doc_id_6min = await _seed_hub_document(
        status="processing", last_heartbeat_offset_minutes=6
    )
    count = await watchdog_tick()
    assert count == 1, (
        f"REVISION 2 violated — 6min last_heartbeat phải bị flip "
        f"(> 5min threshold), got count={count}"
    )

    # Verify 3min row vẫn processing, 6min row đã failed.
    engine = get_engine()
    async with engine.connect() as conn:
        row3 = (
            await conn.execute(
                text("SELECT status FROM documents WHERE id=:id"),
                {"id": doc_id_3min},
            )
        ).fetchone()
        row6 = (
            await conn.execute(
                text("SELECT status FROM documents WHERE id=:id"),
                {"id": doc_id_6min},
            )
        ).fetchone()
    assert row3 is not None and row3[0] == "processing", (
        "3min row phải GIỮ status processing"
    )
    assert row6 is not None and row6[0] == "failed", (
        "6min row phải đổi status failed"
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_watchdog_skips_pending(watchdog_db: Any) -> None:
    """Row pending KHÔNG bị flip (status ≠ processing) — kể cả heartbeat stale."""
    _ = watchdog_db
    from app.services.watchdog import watchdog_tick

    await _seed_hub_document(status="pending", last_heartbeat_offset_minutes=10)
    count = await watchdog_tick()
    assert count == 0, f"pending row KHÔNG được flip, got count={count}"


@pytest.mark.critical
@pytest.mark.integration
@pytest.mark.asyncio
async def test_watchdog_skips_null_heartbeat_processing(
    watchdog_db: Any,
) -> None:
    """WARNING #7 FIX — Row processing với last_heartbeat=NULL KHÔNG bị flip.

    Watchdog query CHỈ flip nếu `last_heartbeat IS NOT NULL` + stale. Accept
    leak ngắn ngủi processing nếu cocoindex worker chưa update heartbeat lần
    đầu (Plan 04-04 REVISION 2 đã bootstrap last_heartbeat=NOW() lúc INSERT —
    case NULL chỉ xảy ra với rows legacy hoặc bug).
    """
    _ = watchdog_db
    from app.db.session import get_engine
    from app.services.watchdog import watchdog_tick

    doc_id = await _seed_hub_document(
        status="processing", last_heartbeat_offset_minutes=None
    )
    count = await watchdog_tick()
    assert count == 0, (
        "WARNING #7 violated — watchdog flip NULL heartbeat (must skip)"
    )

    engine = get_engine()
    async with engine.connect() as conn:
        row = (
            await conn.execute(
                text("SELECT status, last_heartbeat FROM documents WHERE id=:id"),
                {"id": doc_id},
            )
        ).fetchone()
    assert row is not None
    assert row[0] == "processing", (
        "row processing với NULL heartbeat phải GIỮ status"
    )
    assert row[1] is None, "last_heartbeat phải vẫn NULL (KHÔNG bị update)"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_watchdog_empty_db(watchdog_db: Any) -> None:
    """DB không có rows processing → return 0."""
    _ = watchdog_db
    from app.services.watchdog import watchdog_tick

    count = await watchdog_tick()
    assert count == 0
