"""Integration test Plan 05-01 Task 4 — audit logger concurrency (AUX-01 SC4).

WARNING 2 / HARD-03: ROADMAP AUX-01 SC4 yêu cầu "100 concurrent action →
audit_logs có 100 row, request_id unique, non-blocking". Plan 05-06 chỉ test
single-row flush qua hub-isolation — task này thêm test concurrency chuyên biệt.

Fixture cô lập: `audit_db` (module-scope) chỉ chạy alembic upgrade head +
init SQLAlchemy engine — KHÔNG boot full FastAPI app. Lý do: fixture
`app_with_auth` (conftest) chạy full lifespan gồm `setup_cocoindex`, mà cocoindex
1.0.3 `Environment` KHÔNG re-open được trong cùng process → mọi test file dùng
`app_with_auth` >1 lần fail từ test thứ 2 (pre-existing limitation Phase 4).
Audit logger test chỉ cần DB engine + bảng `audit_logs` → fixture nhẹ tự cấp.

audit_logs FK `user_id`/`hub_id` nullable → dùng None tránh phụ thuộc fixture
user/hub. Setup TRUNCATE audit_logs trước mỗi test để COUNT đếm đúng.
"""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from testcontainers.postgres import PostgresContainer

from app.services.audit_service import (
    AuditEntry,
    audit_flush_loop,
    enqueue_audit,
    flush_pending,
    reset_queue,
)


@pytest.fixture
async def audit_db(
    postgres_container: PostgresContainer,
) -> AsyncIterator[None]:
    """Alembic upgrade head + init SQLAlchemy engine cho test audit logger.

    KHÔNG boot full FastAPI app (tránh cocoindex Environment re-open bug —
    cocoindex 1.0.3 Environment không re-open được trong cùng process, mọi test
    file dùng `app_with_auth` >1 lần fail từ test thứ 2). Audit logger test chỉ
    cần DB engine + bảng `audit_logs`.

    Scope function — alembic upgrade idempotent (no-op khi đã ở head),
    init_engine idempotent (return sớm nếu engine đã init). Cost re-chạy thấp.
    """
    sync_url = postgres_container.get_connection_url().replace(
        "postgresql+psycopg2://", "postgresql://"
    )
    async_url = sync_url.replace("postgresql://", "postgresql+asyncpg://")

    import os

    os.environ["DATABASE_URL"] = async_url
    os.environ["COCOINDEX_DATABASE_URL"] = sync_url
    os.environ["REDIS_URL"] = "redis://localhost:6379/0"
    os.environ["APP_ENV"] = "dev"

    from app.config import get_settings

    get_settings.cache_clear()

    cfg_path = Path(__file__).resolve().parents[2] / "alembic.ini"
    alembic_cfg = Config(str(cfg_path))
    await asyncio.to_thread(command.upgrade, alembic_cfg, "head")

    from app.db.session import dispose_engine, init_engine

    await dispose_engine()
    init_engine(get_settings())
    try:
        yield None
    finally:
        await dispose_engine()


async def _truncate_audit_logs() -> None:
    """TRUNCATE audit_logs — đảm bảo COUNT đếm đúng row test enqueue."""
    from app.db.session import get_engine

    engine = get_engine()
    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE TABLE audit_logs RESTART IDENTITY"))


async def _count_audit_logs() -> int:
    """SELECT COUNT(*) FROM audit_logs."""
    from app.db.session import get_engine

    engine = get_engine()
    async with engine.begin() as conn:
        result = await conn.execute(text("SELECT COUNT(*) FROM audit_logs"))
        return int(result.scalar_one())


async def _count_distinct_request_id() -> int:
    """SELECT COUNT(DISTINCT request_id) FROM audit_logs."""
    from app.db.session import get_engine

    engine = get_engine()
    async with engine.begin() as conn:
        result = await conn.execute(
            text("SELECT COUNT(DISTINCT request_id) FROM audit_logs")
        )
        return int(result.scalar_one())


@pytest.mark.critical
@pytest.mark.integration
@pytest.mark.asyncio
async def test_audit_logger_100_concurrent(audit_db: Any) -> None:
    """AUX-01 SC4 — 100 concurrent enqueue → 100 row audit_logs, request_id unique.

    Mô phỏng 100 action đồng thời: 100 coroutine gather, mỗi cái gọi
    enqueue_audit (sync non-blocking). flush_pending drain toàn bộ → batch INSERT.
    Assert COUNT(*)==100 (không mất) VÀ COUNT(DISTINCT request_id)==100 (không trùng).
    """
    _ = audit_db
    reset_queue()
    await _truncate_audit_logs()

    entries = [
        AuditEntry(
            action="auth.login",
            user_id=None,
            target_type="user",
            target_id=None,
            hub_id=None,
            payload={"i": i},
            request_id=str(uuid4()),
        )
        for i in range(100)
    ]

    async def _enqueue_one(entry: AuditEntry) -> None:
        enqueue_audit(entry)

    # 100 enqueue đồng thời (mô phỏng concurrency thật).
    await asyncio.gather(*(_enqueue_one(e) for e in entries))

    # Drain toàn bộ queue → batch INSERT.
    await flush_pending()

    assert await _count_audit_logs() == 100, "Phải có đúng 100 row — không mất entry"
    assert await _count_distinct_request_id() == 100, (
        "Mọi request_id phải unique — không trùng, không mất"
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_enqueue_non_blocking_when_queue_full(audit_db: Any) -> None:
    """enqueue_audit KHÔNG raise khi queue đầy — drop + warning (T-05-01-03).

    Force queue maxsize nhỏ → enqueue vượt ngưỡng. enqueue_audit phải nuốt
    asyncio.QueueFull, KHÔNG ném exception ra caller (audit log mất 1 entry tốt
    hơn block main request thread).
    """
    _ = audit_db
    import app.services.audit_service as audit_mod

    reset_queue()
    # Thay queue bằng instance maxsize nhỏ để dễ làm đầy.
    audit_mod._queue = asyncio.Queue(maxsize=5)

    # Enqueue 20 entry vào queue maxsize 5 — 15 entry bị drop, KHÔNG raise.
    for i in range(20):
        enqueue_audit(
            AuditEntry(action="auth.login", payload={"i": i}, request_id=str(uuid4()))
        )

    # Không có exception → test pass. Queue chỉ giữ tối đa 5 entry.
    assert audit_mod._queue.qsize() == 5, "Queue đầy giữ đúng maxsize, phần dư drop"

    reset_queue()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_audit_flush_loop_batches(audit_db: Any) -> None:
    """audit_flush_loop flush theo batch threshold — 130 entry (> batch_size 128).

    Start audit_flush_loop task (bind queue fresh sau reset_queue), enqueue 130
    entry, poll-with-timeout tới khi COUNT(*) >= 130, cancel task. Verify loop
    drain + INSERT đủ — flush theo batch_size HOẶC flush_interval.
    """
    _ = audit_db
    reset_queue()
    await _truncate_audit_logs()

    # Start loop SAU reset_queue → loop bind vào queue fresh của test.
    loop_task = asyncio.create_task(audit_flush_loop())
    try:
        for i in range(130):
            enqueue_audit(
                AuditEntry(
                    action="document.upload",
                    payload={"i": i},
                    request_id=str(uuid4()),
                )
            )

        # Poll-with-timeout (KHÔNG sleep cứng) tới khi đủ 130 row.
        deadline = asyncio.get_event_loop().time() + 15.0
        count = 0
        while asyncio.get_event_loop().time() < deadline:
            count = await _count_audit_logs()
            if count >= 130:
                break
            await asyncio.sleep(0.2)

        assert count >= 130, f"audit_flush_loop phải flush đủ 130 row, có {count}"
    finally:
        loop_task.cancel()
        try:
            await loop_task
        except asyncio.CancelledError:
            pass
        reset_queue()
