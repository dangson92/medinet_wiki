"""Phase 4 Plan 04-06 (SYNC-04 / D-V3-Phase4-C1+C3) — Central checksum scheduler.

Naive asyncio.sleep loop voi cron-like time check (D-V3-Phase4-C3 — KHONG can
APScheduler dep moi). Lifespan task o central only (skip hub con).

Cadence (D-V3-Phase4-C1):
- Daily 2AM: COUNT(*) per hub con vs central WHERE hub_id = <hub_uuid> →
  drift ratio gauge `sync_count_drift{hub_name}`.
- Hourly: TABLESAMPLE BERNOULLI(1) chunks created last 1h → content_hash diff
  counter `sync_hash_drift{hub_name, drift_type=mismatch|missing}`.

W7 fix: Prometheus label `hub_name` (NOT `hub_id` UUID) cho ca gauge + counter
— semantic ro rang (label values la hub_name string, KHONG UUID).

W3 fix: import `_to_asyncpg_dsn` tu `app.db.dsn` (shared helper module Plan
04-04 carry forward) — KHONG circular import qua `app.main` chain.

Alerts (defer Phase 7 deploy guide AlertManager config):
- sync_count_drift > 0.01 sustained 7 days → E-V3-5 trigger STOP v3.0-b.
- sync_hash_drift > 0 sustained 1 hour → Slack alert.

Per-hub error isolation: caller scheduler loop catch RuntimeError tu
_tick_daily_count / _tick_hourly_hash + log warning + tick tiep hub ke
(KHONG abort scheduler).
"""
from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import asyncpg

from app.db.dsn import _to_asyncpg_dsn  # W3 fix shared module — Plan 04-04 carry forward
from app.sync.metrics import SYNC_COUNT_DRIFT, SYNC_HASH_DRIFT

if TYPE_CHECKING:
    pass  # avoid runtime FastAPI import (app passed as any)

logger = logging.getLogger(__name__)

# Tick interval — check daily/hourly conditions every minute. Test patch
# overrides via monkeypatch (KHONG tight loop CPU burn in test).
TICK_INTERVAL_SECONDS: float = 60.0

# Daily run hour (UTC). 2 AM la idle window cho most timezones — minimize
# I/O contention voi ingest peak.
DAILY_RUN_HOUR: int = 2

# Hourly tick threshold seconds.
HOURLY_INTERVAL_SECONDS: float = 3600.0


def _get_settings() -> Any:
    """Indirection helper — testable monkeypatch hook (KHONG inline get_settings()).

    Test fixture monkeypatch `app.observability.checksum_scheduler._get_settings`
    de isolate scheduler logic khoi Settings cache.
    """
    from app.config import get_settings

    return get_settings()


def _should_run_daily(now: datetime, last_run: datetime | None) -> bool:
    """True khi now.hour == DAILY_RUN_HOUR + last_run None hoac yesterday.

    Idempotent — KHONG chay 2 lan cung ngay (last_run.date() == now.date() → False).
    """
    if now.hour != DAILY_RUN_HOUR:
        return False
    if last_run is None:
        return True
    return last_run.date() < now.date()


def _should_run_hourly(now: datetime, last_run: datetime | None) -> bool:
    """True khi now - last_run >= 1 hour (hoac last_run None)."""
    if last_run is None:
        return True
    return (now - last_run).total_seconds() >= HOURLY_INTERVAL_SECONDS


async def _tick_daily_count(
    central_pool: Any,
    hub_pool: Any,
    hub_name: str,
) -> None:
    """Daily count drift per hub_name — set SYNC_COUNT_DRIFT gauge.

    Steps:
    1. Resolve hub_id UUID tu central.hubs WHERE name = hub_name.
    2. Central COUNT(*) WHERE hub_id = $1 (denormalized aggregate).
    3. Hub con COUNT(*) FROM chunks (entire hub DB).
    4. drift_ratio = abs(central - hub) / max(hub, 1) — symmetric.
    5. SYNC_COUNT_DRIFT.labels(hub_name=hub_name).set(drift_ratio).

    Caller responsibility: try/except RuntimeError de skip hub failed + tick
    tiep hub ke (per-hub error isolation in scheduler loop).
    """
    # Resolve hub_id from central.hubs registry.
    async with central_pool.acquire() as conn:
        hub_id_row = await conn.fetchrow(
            "SELECT id FROM hubs WHERE name = $1", hub_name
        )
        if hub_id_row is None:
            logger.warning("checksum_daily_hub_not_in_registry: hub=%s", hub_name)
            return
        hub_id = hub_id_row["id"]
        central_count = await conn.fetchval(
            "SELECT COUNT(*) FROM chunks WHERE hub_id = $1", hub_id
        )
    # Hub con count.
    async with hub_pool.acquire() as conn:
        hub_count = await conn.fetchval("SELECT COUNT(*) FROM chunks")

    # Symmetric drift ratio — abs(diff) / max(hub_count, 1).
    diff = abs(int(central_count) - int(hub_count))
    ratio = diff / max(int(hub_count), 1)
    SYNC_COUNT_DRIFT.labels(hub_name=hub_name).set(ratio)
    logger.info(
        "checksum_daily_tick: hub=%s central=%d hub_con=%d drift_ratio=%.4f",
        hub_name,
        central_count,
        hub_count,
        ratio,
    )


async def _tick_hourly_hash(
    central_pool: Any,
    hub_pool: Any,
    hub_name: str,
) -> None:
    """Hourly TABLESAMPLE 1% hash diff — emit SYNC_HASH_DRIFT counter.

    Steps:
    1. Sample 1% chunks tu hub con WHERE created_at > NOW() - INTERVAL '1 hour'.
       Empty sample → no-op (no recent ingest).
    2. Fetch central content_hash cho cac id sampled.
    3. So sanh:
       - hub_id NOT IN central → drift_type=missing.
       - hash khac → drift_type=mismatch.
    4. SYNC_HASH_DRIFT.labels(hub_name, drift_type).inc(count).

    Caller responsibility: try/except RuntimeError de skip + tick tiep.
    """
    # Sample from hub con (TABLESAMPLE BERNOULLI(1) ~ 1% rows).
    async with hub_pool.acquire() as conn:
        sample = await conn.fetch(
            """
            SELECT id, content_hash FROM chunks
            TABLESAMPLE BERNOULLI(1)
            WHERE created_at > NOW() - INTERVAL '1 hour'
            """
        )
    if not sample:
        return  # empty sample — no recent chunks

    chunk_ids = [row["id"] for row in sample]
    hub_hashes = {row["id"]: bytes(row["content_hash"]) for row in sample}

    # Fetch central by sampled IDs.
    async with central_pool.acquire() as conn:
        central_rows = await conn.fetch(
            "SELECT id, content_hash FROM chunks WHERE id = ANY($1::uuid[])",
            chunk_ids,
        )
    central_hashes = {row["id"]: bytes(row["content_hash"]) for row in central_rows}

    # Compare per-chunk.
    mismatch_count = 0
    missing_count = 0
    for chunk_id, hub_hash in hub_hashes.items():
        if chunk_id not in central_hashes:
            missing_count += 1
        elif central_hashes[chunk_id] != hub_hash:
            mismatch_count += 1

    if mismatch_count > 0:
        SYNC_HASH_DRIFT.labels(hub_name=hub_name, drift_type="mismatch").inc(
            mismatch_count
        )
    if missing_count > 0:
        SYNC_HASH_DRIFT.labels(hub_name=hub_name, drift_type="missing").inc(
            missing_count
        )
    logger.info(
        "checksum_hourly_tick: hub=%s sampled=%d mismatch=%d missing=%d",
        hub_name,
        len(sample),
        mismatch_count,
        missing_count,
    )


async def checksum_scheduler_loop(app: Any) -> None:  # noqa: C901 — naive cron loop intentional
    """Main scheduler loop — spawn o central lifespan (Plan 04-06 lifespan integration).

    Args:
        app: FastAPI app instance (app.state.db_pool = central asyncpg pool).

    Skip hub con (settings.hub_name != "central") — central-only placement
    (D-V3-Phase4-C3). Hub con KHONG own checksum scheduler — Settings validator
    Plan 04-02 _enforce_checksum_hub_dsns_for_central skip cho hub con.

    Cancellation: asyncio.CancelledError propagate → caller graceful shutdown
    via task.cancel() + await task.

    Empty hub_dsns dict → loop tick no-op (KHONG fail) — central deploy lan dau
    CHUA register hub con.
    """
    settings = _get_settings()
    if settings.hub_name != "central":
        logger.info(
            "checksum_scheduler_skip_hub_con: hub_name=%s", settings.hub_name
        )
        return

    central_pool = app.state.db_pool

    last_daily_run: datetime | None = None
    last_hourly_run: datetime | None = None

    # Lazy per-hub pool dict — init on demand mỗi tick (KHONG block lifespan).
    hub_pools: dict[str, asyncpg.Pool] = {}

    try:
        while True:
            try:
                now = datetime.now(UTC)
                # Re-read hub_dsns mỗi tick — operator có thể append hub mới
                # (FACTOR-04 dynamic hub registration) + restart scheduler refresh.
                hub_dsns: dict[str, str] = settings.checksum_hub_dsns

                # Lazy init per-hub pool.
                for hub_name, dsn in hub_dsns.items():
                    if hub_name not in hub_pools:
                        try:
                            hub_pools[hub_name] = await asyncpg.create_pool(
                                dsn=_to_asyncpg_dsn(dsn),
                                min_size=1,
                                max_size=2,
                            )
                            logger.info(
                                "checksum_pool_ready: hub=%s", hub_name
                            )
                        except Exception as e:  # noqa: BLE001 — log + skip hub fail
                            logger.warning(
                                "checksum_pool_init_failed: hub=%s err=%s",
                                hub_name,
                                e,
                            )

                # Daily tick (2AM UTC).
                if hub_dsns and _should_run_daily(now, last_daily_run):
                    logger.info(
                        "checksum_daily_tick_start: now=%s", now.isoformat()
                    )
                    for hub_name in hub_dsns:
                        hub_pool = hub_pools.get(hub_name)
                        if hub_pool is None:
                            continue  # skip hub failed init
                        try:
                            await _tick_daily_count(
                                central_pool, hub_pool, hub_name
                            )
                        except Exception as e:  # noqa: BLE001 — per-hub error isolation
                            logger.warning(
                                "checksum_daily_hub_failed: hub=%s err=%s",
                                hub_name,
                                e,
                            )
                    last_daily_run = now

                # Hourly tick.
                if hub_dsns and _should_run_hourly(now, last_hourly_run):
                    logger.info(
                        "checksum_hourly_tick_start: now=%s", now.isoformat()
                    )
                    for hub_name in hub_dsns:
                        hub_pool = hub_pools.get(hub_name)
                        if hub_pool is None:
                            continue
                        try:
                            await _tick_hourly_hash(
                                central_pool, hub_pool, hub_name
                            )
                        except Exception as e:  # noqa: BLE001 — per-hub error isolation
                            logger.warning(
                                "checksum_hourly_hub_failed: hub=%s err=%s",
                                hub_name,
                                e,
                            )
                    last_hourly_run = now

                await asyncio.sleep(TICK_INTERVAL_SECONDS)
            except asyncio.CancelledError:
                raise
            except Exception as e:  # noqa: BLE001 — defensive degrade-gracefully
                logger.exception(
                    "checksum_scheduler_iteration_failed: err=%s", e
                )
                await asyncio.sleep(TICK_INTERVAL_SECONDS)
    except asyncio.CancelledError:
        logger.info("checksum_scheduler_cancelled")
        raise
    finally:
        # Cleanup per-hub pools (best-effort).
        for hub_name, pool in hub_pools.items():
            try:
                await pool.close()
            except Exception as e:  # noqa: BLE001
                logger.warning(
                    "checksum_pool_close_failed: hub=%s err=%s", hub_name, e
                )


__all__ = [
    "DAILY_RUN_HOUR",
    "HOURLY_INTERVAL_SECONDS",
    "TICK_INTERVAL_SECONDS",
    "_should_run_daily",
    "_should_run_hourly",
    "_tick_daily_count",
    "_tick_hourly_hash",
    "checksum_scheduler_loop",
]
