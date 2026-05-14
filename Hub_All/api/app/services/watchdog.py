"""Watchdog asyncio task — Plan 04-05 REVISION 2 (INGEST-06, P8 mitigation).

Mỗi WATCHDOG_INTERVAL_SECONDS (60s), UPDATE documents SET status='failed' WHERE:
    status='processing'
    AND last_heartbeat IS NOT NULL          -- WARNING #7 fix (NOT NULL guard)
    AND last_heartbeat < NOW() - INTERVAL settings.watchdog_timeout_seconds
                                            -- (300s default = 5 phút REVISION 2)

Mitigation P8 + WARNING #7 + REVISION 2 5min:
- P8: stuck processing forever khi cocoindex worker crash giữa flow.
- WARNING #7 fix combo (b)+(c):
  (b) Plan 04-04 REVISION 2 đã bootstrap `last_heartbeat=NOW()` lúc INSERT documents
      row → mọi processing row CÓ initial heartbeat NOT NULL.
      Plus trigger_cocoindex_update refresh `last_heartbeat=NOW()` sau update_blocking.
  (c) Query CHỈ flip nếu NOT NULL + stale > 5 phút → KHÔNG flip rows mới INSERT
      mà cocoindex worker chưa chạy xong (accept leak ngắn ngủi processing nếu
      chưa có heartbeat update từ flow / trigger_cocoindex_update vẫn đang chạy).
- REVISION 2: Timeout 2 phút → 5 phút (configurable Settings.watchdog_timeout_seconds=300).
  Cocoindex 1.0.3 update_blocking cho document lớn (DOCX 50 trang, N×embed LiteLLM)
  có thể chạy >2 phút bình thường. 5 phút headroom an toàn.

Lifespan integration (Plan 04-05 task 02 step 3 — main.py APPEND-ONLY):
- startup: APPEND-ONLY sau cocoindex setup (Plan 04-03 step 3 — WARNING #5):
    app.state.watchdog_task = asyncio.create_task(watchdog_loop())
- shutdown: app.state.watchdog_task.cancel() + await với suppress(CancelledError)

Status update cocoindex completion KHÔNG ở watchdog — đã ở Plan 04-04
trigger_cocoindex_update helper (count chunks > 0 → 'completed', =0 → 'failed').
Watchdog chỉ phát hiện crash giữa chừng (BackgroundTask thread killed / cocoindex_app
crash) → row vẫn `status='processing'` nhưng heartbeat KHÔNG refresh > 5 phút.
"""
from __future__ import annotations

import asyncio
import logging

from sqlalchemy import text

from app.config import get_settings
from app.db.session import get_engine

logger = logging.getLogger(__name__)

# Tick interval — chạy 1 lần mỗi 60s. Đặt const để test patch được nếu cần.
WATCHDOG_INTERVAL_SECONDS: int = 60


def get_watchdog_timeout_seconds() -> int:
    """Return watchdog timeout từ Settings (default 300s = 5 phút — REVISION 2).

    Tách helper để test mock + giảm coupling cứng vào get_settings ở watchdog_tick.
    """
    return get_settings().watchdog_timeout_seconds


async def watchdog_tick() -> int:
    """1 lần tick: flip stuck processing → failed. Return số rows update.

    Idempotent — chạy nhiều lần OK. Test chạy 1 tick → assert count.

    WARNING #7 fix — CHỈ flip nếu `last_heartbeat IS NOT NULL` AND stale.
    Rows processing với last_heartbeat=NULL KHÔNG flip (accept leak ngắn ngủi).

    REVISION 2 — Timeout 5 phút (Settings.watchdog_timeout_seconds default 300).
    Dùng Postgres `make_interval(secs => :timeout_secs)` để bind parameter
    timeout (KHÔNG hardcode INTERVAL string — configurable env).

    Returns:
        Số rows bị flip thành 'failed' (≥0).
    """
    try:
        engine = get_engine()
    except RuntimeError:
        # Engine chưa init (lifespan startup chưa xong / shutdown đã chạy) — skip tick.
        logger.warning("watchdog_skip: DB engine chưa init")
        return 0

    timeout_secs = get_watchdog_timeout_seconds()
    error_msg = f"timeout: no heartbeat for >{timeout_secs}s"

    async with engine.begin() as conn:
        result = await conn.execute(
            text(
                "UPDATE documents "
                "SET status='failed', "
                "    error_message=:error_msg, "
                "    updated_at=NOW() "
                "WHERE status='processing' "
                "  AND last_heartbeat IS NOT NULL "  # WARNING #7 — NOT NULL guard
                "  AND last_heartbeat < NOW() - make_interval(secs => :timeout_secs)"
            ),
            {"error_msg": error_msg, "timeout_secs": timeout_secs},
        )
        count = result.rowcount or 0

    if count > 0:
        logger.info(
            "watchdog_flipped_stuck_processing: count=%d timeout_secs=%d",
            count,
            timeout_secs,
        )
    return int(count)


async def watchdog_loop() -> None:
    """Forever-running loop — tick mỗi WATCHDOG_INTERVAL_SECONDS.

    Cancel-safe: nhận CancelledError → return gracefully.
    Exception khác → log + tiếp tục (KHÔNG crash task — defensive).
    """
    timeout_secs = get_watchdog_timeout_seconds()
    logger.info(
        "watchdog_loop_start: interval=%ds timeout=%ds (REVISION 2 — 5min default)",
        WATCHDOG_INTERVAL_SECONDS,
        timeout_secs,
    )
    while True:
        try:
            await asyncio.sleep(WATCHDOG_INTERVAL_SECONDS)
            await watchdog_tick()
        except asyncio.CancelledError:
            logger.info("watchdog_loop_cancelled")
            return
        except Exception as e:  # noqa: BLE001 — KHÔNG crash task, log + continue
            logger.exception("watchdog_tick_failed: %s", e)
            # tiếp tục loop, không break.
