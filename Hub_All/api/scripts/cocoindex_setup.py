"""CLI entry-point chạy cocoindex setup — Plan 04-01.

Usage:
    cd Hub_All/api
    uv run python scripts/cocoindex_setup.py

Sau khi `alembic upgrade head` xong, chạy script này MỘT LẦN để cocoindex
tạo internal state tables trong schema `cocoindex` (cocoindex.medinet_prod__*).
Idempotent — chạy lại sau khi Plan 04-02 ship flow.py cũng OK.

Exit codes:
    0 — setup OK
    1 — exception (in traceback, log error)
"""
from __future__ import annotations

import logging
import sys

from app.config import get_settings
from app.rag import setup_cocoindex


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    log = logging.getLogger(__name__)
    log.info("cocoindex_setup_cli_start")
    try:
        settings = get_settings()
        setup_cocoindex(settings)
    except Exception as e:  # noqa: BLE001 — top-level CLI catch-all
        log.exception("cocoindex_setup_failed: %s", e)
        return 1
    log.info("cocoindex_setup_cli_ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
