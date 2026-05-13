"""FastAPI app factory + lifespan — Medinet Wiki API M2.

Lifespan (in-process, single FastAPI process owns cocoindex theo
ARCHITECTURE.md Pattern 1):
  - Init `asyncpg.create_pool(DATABASE_URL)` cho app DB.
  - Init `redis.asyncio.from_url(REDIS_URL)` + PING verify connection.
  - Verify `import cocoindex` được (Phase 4 sẽ thay bằng FlowLiveUpdater thực).

Phase 1 skeleton design: nếu một dependency fail (e.g., Postgres chưa lên),
LOG warning + đánh dấu state ready=False — KHÔNG raise/crash. App vẫn start;
`/healthz` (liveness) luôn 200; `/readyz` (readiness) trả 503 cho đến khi
dependency lên. Phase 2+ sẽ siết chặt fail-fast nếu cần.

Middleware order — P11 PITFALL: FastAPI thực thi middleware add CUỐI CÙNG
TRƯỚC. Order REVERSED từ Go Gin. Phase 1 chỉ wire CORS (placeholder, cors
list empty default). Phase 3 (Auth) sẽ add (theo thứ tự add từ TRƯỚC ra
NGOÀI): gzip → rate_limit → CORS → security_headers → request_id →
error_handler (LAST = outermost wrap). Comment kế bên `add_middleware`.

Healthcheck:
  - GET /healthz  — liveness (luôn 200 khi app run, KHÔNG check dependency).
  - GET /readyz   — readiness (200 nếu db+redis+cocoindex ready, 503 ngược lại).
"""
from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import asyncpg
import redis.asyncio as redis_asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.pkg import response as resp

logger = logging.getLogger(__name__)


def _to_asyncpg_dsn(sqlalchemy_dsn: str) -> str:
    """SQLAlchemy DSN `postgresql+asyncpg://...` → asyncpg DSN `postgresql://...`.

    asyncpg client KHÔNG nhận driver prefix `+asyncpg` — chỉ SQLAlchemy hiểu.
    """
    return sqlalchemy_dsn.replace("postgresql+asyncpg://", "postgresql://", 1)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Async context manager quản lý startup/shutdown của FastAPI app."""
    settings = get_settings()

    # Khởi tạo state mặc định = chưa ready. Mỗi step set True khi thành công.
    app.state.db_pool = None
    app.state.db_ready = False
    app.state.redis = None
    app.state.redis_ready = False
    app.state.cocoindex_ready = False

    # 1) asyncpg pool — không crash nếu Postgres chưa lên (Phase 1 skeleton).
    try:
        app.state.db_pool = await asyncpg.create_pool(
            dsn=_to_asyncpg_dsn(settings.database_url),
            min_size=2,
            max_size=10,
        )
        app.state.db_ready = True
        logger.info("db_pool_ready: min_size=2 max_size=10")
    except Exception as e:  # noqa: BLE001 — Phase 1 không crash; log + tiếp tục.
        logger.warning("db_pool_init_failed: %s", e)

    # 2) redis client + PING verify.
    try:
        app.state.redis = redis_asyncio.from_url(
            settings.redis_url, decode_responses=True
        )
        await app.state.redis.ping()
        app.state.redis_ready = True
        logger.info("redis_ready")
    except Exception as e:  # noqa: BLE001 — Phase 1 không crash.
        logger.warning("redis_init_failed: %s", e)

    # 3) cocoindex import verify (Phase 1 chỉ verify package import được;
    #    FlowLiveUpdater + cocoindex.init() khởi tạo Phase 4 cùng flow định nghĩa).
    try:
        import cocoindex  # noqa: F401 — verify import path resolves

        app.state.cocoindex_ready = True
        logger.info("cocoindex_skeleton_ready (Phase 4 sẽ init FlowLiveUpdater)")
    except ImportError as e:
        logger.warning("cocoindex_import_failed: %s", e)

    try:
        yield
    finally:
        # Shutdown ngược thứ tự init — cocoindex updater → redis → db_pool.
        if app.state.cocoindex_ready:
            # Phase 4: app.state.cocoindex_updater.abort() ở đây.
            app.state.cocoindex_ready = False
        if app.state.redis is not None:
            try:
                await app.state.redis.aclose()
            except Exception as e:  # noqa: BLE001
                logger.warning("redis_close_failed: %s", e)
        if app.state.db_pool is not None:
            try:
                await app.state.db_pool.close()
            except Exception as e:  # noqa: BLE001
                logger.warning("db_pool_close_failed: %s", e)
        logger.info("lifespan_shutdown_complete")


def create_app() -> FastAPI:
    """Factory tạo FastAPI app — gọi 1 lần ở module-level và trong unit test."""
    settings = get_settings()
    app = FastAPI(
        title="Medinet Wiki API",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Middleware Phase 1 — chỉ CORS placeholder (config rỗng default trong dev).
    # NOTE P11: FastAPI executes last-added middleware FIRST cho incoming
    # request. Order REVERSED từ Go Gin. Phase 3 (Auth) sẽ add theo thứ tự
    # (TRƯỚC ra NGOÀI):
    #   1) gzip          (add đầu tiên = innermost — chạy cuối cùng cho request)
    #   2) rate_limit
    #   3) CORS          ← Phase 1 đang ở đây
    #   4) security_headers
    #   5) request_id
    #   6) error_handler (add cuối cùng = outermost wrap, bắt mọi exception).
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/healthz")
    async def healthz() -> Any:
        """Liveness probe — luôn 200 khi app run. KHÔNG check dependency."""
        return resp.ok(data={"status": "ok"})

    @app.get("/readyz")
    async def readyz() -> Any:
        """Readiness probe — 200 nếu db+redis+cocoindex đều ready, 503 ngược lại."""
        checks: dict[str, str] = {}
        all_ok = True

        # DB check (chỉ chạy SELECT 1 nếu pool đã init).
        if app.state.db_ready and app.state.db_pool is not None:
            try:
                async with app.state.db_pool.acquire() as conn:
                    await conn.fetchval("SELECT 1")
                checks["db"] = "ok"
            except Exception as e:  # noqa: BLE001
                checks["db"] = f"fail: {e}"
                all_ok = False
        else:
            checks["db"] = "not_ready"
            all_ok = False

        # Redis check.
        if app.state.redis_ready and app.state.redis is not None:
            try:
                pong = await app.state.redis.ping()
                if pong:
                    checks["redis"] = "ok"
                else:
                    checks["redis"] = "fail: no pong"
                    all_ok = False
            except Exception as e:  # noqa: BLE001
                checks["redis"] = f"fail: {e}"
                all_ok = False
        else:
            checks["redis"] = "not_ready"
            all_ok = False

        # CocoIndex check.
        if app.state.cocoindex_ready:
            checks["cocoindex"] = "ok"
        else:
            checks["cocoindex"] = "not_ready"
            all_ok = False

        if all_ok:
            return resp.ok(data=checks)
        return resp.service_unavailable(
            message=f"Dịch vụ chưa sẵn sàng: {checks}"
        )

    return app


# Module-level app instance — uvicorn `app.main:app` dùng cái này.
app = create_app()
