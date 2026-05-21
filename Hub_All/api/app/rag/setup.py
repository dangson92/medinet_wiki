"""Cocoindex 1.0.3 setup helper — Plan 04-03 REVISION 2 (INGEST-01 prerequisite).

REWRITE từ Plan 04-01 skeleton (cocoindex.start_blocking() trống) sang đầy đủ
cocoindex 1.0.3 lifespan + initial backfill pattern (RESEARCH.md Section 9.2).

Sequence (cocoindex 1.0.3 actual API):
    1. Set os.environ["COCOINDEX_DB"] = settings.cocoindex_lmdb_path (Q5).
    2. Register @coco.lifespan provide asyncpg.Pool to PG_POOL_KEY (cho mount_table_target).
    3. Import app.rag.flow → side-effect register coco.App vào _default_env._info.
    4. coco.start_blocking() — enter lifespan + start default env (sync).
    5. cocoindex_app.update_blocking() — apply chunks schema diff + initial
       backfill cho mọi pending documents rows.

Idempotent: chạy nhiều lần OK. Cocoindex 1.0.3 schema apply diff-only.

Decision A4 forward reference:
    Plan 04-04 router upload → INSERT documents row → FastAPI BackgroundTasks
    add_task(trigger_cocoindex_update, app.state.cocoindex_app, doc_id) →
    `cocoindex_app.update_blocking()` chạy lại trong background thread → cocoindex
    memo skip rows unchanged + process row mới (status='pending').

Replace toàn bộ revision 1 paste-ready (deprecated 0.x init helpers / flow setup
helpers / live updater) — các API này KHÔNG tồn tại cocoindex 1.0.3.
"""
from __future__ import annotations

import logging
import os
from typing import Any

import asyncpg
import cocoindex as coco

from app.config import Settings

logger = logging.getLogger(__name__)


def _to_asyncpg_dsn(sqlalchemy_dsn: str) -> str:
    """SQLAlchemy DSN `postgresql+asyncpg://...` → asyncpg DSN `postgresql://...`."""
    return sqlalchemy_dsn.replace("postgresql+asyncpg://", "postgresql://", 1)


def setup_cocoindex(settings: Settings) -> None:
    """Init cocoindex 1.0.3 default env + apply chunks schema + initial backfill.

    Sequence:
        0. (v3.0 TOPO-03) Set APP_NAMESPACE env per-hub — `medinet_<hub>_prod`.
        1. Set COCOINDEX_DB env var (LMDB filesystem path) — Q5.
        2. Register @coco.lifespan provide asyncpg.Pool cho PG_POOL_KEY.
        3. Import app.rag.flow → register coco.App vào registry.
        4. coco.start_blocking() — enter lifespan + start default env.
        5. cocoindex_app.update_blocking() — apply schema + initial backfill.

    Idempotent: chạy nhiều lần OK. App.update_blocking() là delta-only.

    Caller (FastAPI lifespan trong main.py) PHẢI wrap qua
    `await asyncio.to_thread(setup_cocoindex, settings)` để KHÔNG block event loop.

    Raises:
        RuntimeError: cocoindex.start_blocking fail (Postgres không lên / DSN sai).
    """
    # 0) Set APP_NAMESPACE per-hub — v3.0 Plan 01-04 TOPO-03 (R5 scale per-hub).
    #    Format: `medinet_<hub_name>_prod`. Trước v3.0 cố định "medinet_prod" cho
    #    mọi env (M2 R5 mitigation); v3.0 mỗi hub có namespace riêng để cocoindex
    #    internal tables `cocoindex.medinet_<hub>_prod__*` không đụng nhau giữa
    #    các DB hub (4 process cùng instance).
    #    P7 carry forward: `Settings.cocoindex_db_schema="cocoindex"` cố định
    #    (KHÔNG đổi schema name) — chỉ scale namespace prefix.
    #
    #    M2 State Migration Note (BLOCKER 4): Sau Plan 04 ship + deploy default
    #    HUB_NAME=central, APP_NAMESPACE đổi từ "medinet_prod" (M2) →
    #    "medinet_central_prod" (Phase 1) → orphan toàn bộ cocoindex.medinet_prod__*
    #    schema M2. Mitigation: post-deploy re-ingest từ documents table
    #    (idempotent via content_hash); Phase 7 migrate data formally qua pg_dump.
    #
    #    Settings.app_namespace field default "medinet_prod" KHÔNG xoá — backward-compat
    #    nếu deployer set env APP_NAMESPACE manually thì pydantic load; setup_cocoindex
    #    GHI ĐÈ qua os.environ["APP_NAMESPACE"] ngay trước start_blocking deterministic.
    namespaced = f"medinet_{settings.hub_name}_prod"
    os.environ["APP_NAMESPACE"] = namespaced
    logger.info(
        "cocoindex_app_namespace_set: hub=%s namespace=%s",
        settings.hub_name,
        namespaced,
    )

    # 1) Set COCOINDEX_DB (LMDB path) — Q5.
    #    Cocoindex 1.0.3 đọc env tại default_env() init time — set trước import flow.
    #    GÁN trực tiếp (không setdefault) để Settings.cocoindex_lmdb_path là single
    #    source of truth — `.env` COCOINDEX_DB chỉ còn vai trò feed pydantic-settings,
    #    không bypass. Gap SC5 fix.
    os.environ["COCOINDEX_DB"] = str(settings.cocoindex_lmdb_path)
    logger.info(
        "cocoindex_setup_start: lmdb=%s asyncpg_dsn=%s",
        settings.cocoindex_lmdb_path,
        "<redacted>",
    )

    # 2) Register lifespan — provide asyncpg.Pool cho mount_table_target.
    #    Import PG_POOL_KEY trước import cocoindex_app để @coco.lifespan có thể
    #    reference key.
    from app.rag.flow import PG_POOL_KEY

    asyncpg_dsn = _to_asyncpg_dsn(settings.database_url)

    @coco.lifespan
    async def _lifespan(env_builder: Any) -> Any:
        pool = await asyncpg.create_pool(
            dsn=asyncpg_dsn,
            min_size=2,
            max_size=10,
        )
        env_builder.provide(PG_POOL_KEY, pool)
        try:
            yield
        finally:
            await pool.close()

    # 3) Import flow → register coco.App vào registry (side-effect tại import time).
    from app.rag.flow import cocoindex_app

    app_name = getattr(cocoindex_app, "name", None) or getattr(
        cocoindex_app, "_name", "<unknown>"
    )
    logger.info("cocoindex_app_registered: %s", app_name)

    # 4) Start env + apply schema (sync — Rust core init).
    coco.start_blocking()
    logger.info("cocoindex_default_env_started")

    # 5) One-shot update — apply chunks schema diff + initial backfill cho mọi
    #    pending documents rows. Idempotent — chạy nhiều lần OK (memo skip).
    cocoindex_app.update_blocking()
    logger.info("cocoindex_initial_backfill_complete")


def get_cocoindex_app() -> Any:
    """Return registered cocoindex_app instance.

    Plan 04-04 router truy cập trong BackgroundTasks (A4 trigger update_blocking).

    KHÔNG re-import nếu đã import sẵn — module-level import idempotent. Caller
    (main.py lifespan) gọi sau setup_cocoindex để lưu app.state.cocoindex_app.

    Returns:
        cocoindex_app: coco.App instance (opaque type — KHÔNG type-annotate vì
        cocoindex 1.0.3 wheel có thể chưa export type stub đầy đủ).
    """
    from app.rag.flow import cocoindex_app

    return cocoindex_app


def stop_cocoindex() -> None:
    """Clean shutdown cocoindex (call ở lifespan finally).

    Cocoindex 1.0.3 stop_blocking() exit lifespan + close asyncpg.Pool +
    teardown default env. Try/except để KHÔNG block FastAPI shutdown.
    """
    try:
        coco.stop_blocking()
        logger.info("cocoindex_default_env_stopped")
    except Exception as e:  # noqa: BLE001
        logger.warning("cocoindex_stop_failed: %s", e)
