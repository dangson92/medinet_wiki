"""FastAPI app factory + lifespan — Medinet Wiki API M2.

Lifespan (in-process, single FastAPI process owns cocoindex theo
ARCHITECTURE.md Pattern 1):
  - Init `asyncpg.create_pool(DATABASE_URL)` cho app DB.
  - Init `redis.asyncio.from_url(REDIS_URL)` + PING verify connection.
  - Phase 4 Plan 04-03: setup_cocoindex() qua asyncio.to_thread (cocoindex 1.0.3
    actual API — coco.start_blocking + cocoindex_app.update_blocking initial backfill).

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
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.requests import Request as FastAPIRequest
from starlette.responses import JSONResponse as StarletteJSONResponse

from app.config import get_settings
from app.middleware import (
    ErrorHandlerMiddleware,
    RequestIdMiddleware,
    SecurityHeadersMiddleware,
)
from app.pkg import response as resp

logger = logging.getLogger(__name__)


def _to_asyncpg_dsn(sqlalchemy_dsn: str) -> str:
    """SQLAlchemy DSN `postgresql+asyncpg://...` → asyncpg DSN `postgresql://...`.

    asyncpg client KHÔNG nhận driver prefix `+asyncpg` — chỉ SQLAlchemy hiểu.
    """
    return sqlalchemy_dsn.replace("postgresql+asyncpg://", "postgresql://", 1)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:  # noqa: C901 — init sequence
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

    # 3) Cocoindex 1.0.3 init + initial backfill (Phase 4 Plan 04-03 REVISION 2 — INGEST-01..03).
    #    setup_cocoindex(settings) → register @coco.lifespan + coco.start_blocking
    #    + cocoindex_app.update_blocking() initial backfill cho mọi pending documents.
    #    KHÔNG còn live updater pattern cocoindex 0.x (Decision A4 user accepted:
    #    per-document trigger qua FastAPI BackgroundTasks ở Plan 04-04).
    #
    #    setup_cocoindex SYNC blocking — wrap asyncio.to_thread để KHÔNG block
    #    FastAPI lifespan event loop (cocoindex Rust core init + initial backfill
    #    có thể tốn vài giây nếu schema apply lần đầu hoặc nhiều pending rows).
    app.state.cocoindex_app = None
    try:
        import asyncio

        from app.rag.setup import get_cocoindex_app, setup_cocoindex

        await asyncio.to_thread(setup_cocoindex, settings)
        logger.info("cocoindex_setup_ok")
        app.state.cocoindex_app = get_cocoindex_app()
        app.state.cocoindex_ready = True
        logger.info("cocoindex_app_attached_to_app_state")
    except Exception as e:  # noqa: BLE001 — Phase 1 fail-soft pattern
        logger.warning("cocoindex_init_failed: %s", e)

    # 4) JWTManager — init khoá RS256 từ keys/private.pem + public.pem (Phase 3).
    try:
        from app.auth import JWTManager

        app.state.jwt_manager = JWTManager(settings)
        logger.info(
            "jwt_manager_ready: access_ttl=%ds refresh_ttl=%ds",
            settings.jwt_access_token_ttl,
            settings.jwt_refresh_token_ttl,
        )
    except Exception as e:  # noqa: BLE001
        app.state.jwt_manager = None
        logger.warning("jwt_manager_init_failed: %s", e)

    # 5) Anti-timing dummy hash — pre-compute 1 hash để service.login dùng
    #    khi user không tồn tại (response time KHÔNG leak email enumeration —
    #    T-03-04-timing-oracle mitigation).
    try:
        from app.auth import hash_password

        app.state.dummy_password_hash = hash_password(
            "dummy-not-a-real-password-Đ#"
        )
        logger.info("dummy_password_hash_ready (anti-timing oracle)")
    except Exception as e:  # noqa: BLE001
        # Fallback dummy hash (định dạng hợp lệ nhưng KHÔNG verify password thật).
        app.state.dummy_password_hash = (
            "$argon2id$v=19$m=65536,t=3,p=4"
            "$AAAAAAAAAAAAAAAAAAAAAAA"
            "$AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        )
        logger.warning("dummy_password_hash_fallback: %s", e)

    # 6) SQLAlchemy async engine — init cho FastAPI Depends(get_session) (Phase 3).
    try:
        from app.db.session import init_engine

        init_engine(settings)
        logger.info("sqlalchemy_engine_ready")
    except Exception as e:  # noqa: BLE001
        logger.warning("sqlalchemy_engine_init_failed: %s", e)

    # 7) Watchdog asyncio task (Plan 04-05 REVISION 2 — INGEST-06, P8 + WARNING #7 mitigation).
    #    APPEND-ONLY sau cocoindex setup (Plan 04-03 REVISION 2 step 3) +
    #    SQLAlchemy engine init (step 6 — watchdog_tick gọi get_engine()).
    #    Flip stuck `processing` rows → `failed` CHỈ nếu last_heartbeat IS NOT NULL
    #    + stale > 5 phút (WARNING #7 NOT NULL guard + REVISION 2 5min timeout
    #    cho cocoindex 1.0.3 update_blocking documents lớn).
    app.state.watchdog_task = None
    try:
        import asyncio as _asyncio_wd

        from app.services.watchdog import watchdog_loop

        app.state.watchdog_task = _asyncio_wd.create_task(watchdog_loop())
        logger.info("watchdog_task_started")
    except Exception as e:  # noqa: BLE001
        logger.warning("watchdog_task_start_failed: %s", e)

    try:
        yield
    finally:
        # Shutdown ngược thứ tự init — watchdog → sqlalchemy → jwt → cocoindex → redis → db_pool.
        # Cancel watchdog task TRƯỚC dispose_engine — watchdog_tick dùng engine,
        # cancel sớm tránh race "engine disposed mid-tick" (Plan 04-05 APPEND-ONLY).
        if getattr(app.state, "watchdog_task", None) is not None:
            app.state.watchdog_task.cancel()
            try:
                await app.state.watchdog_task
            except asyncio.CancelledError:
                pass
            except Exception as e:  # noqa: BLE001
                logger.warning("watchdog_task_stop_failed: %s", e)
            app.state.watchdog_task = None
        try:
            from app.db.session import dispose_engine

            await dispose_engine()
        except Exception as e:  # noqa: BLE001
            logger.warning("sqlalchemy_engine_dispose_failed: %s", e)
        # Reset JWT manager (defensive cho test isolation).
        app.state.jwt_manager = None
        # Phase 4 Plan 04-03 REVISION 2 — stop cocoindex 1.0.3 default env.
        if getattr(app.state, "cocoindex_app", None) is not None:
            try:
                import asyncio as _asyncio

                from app.rag.setup import stop_cocoindex

                await _asyncio.to_thread(stop_cocoindex)
            except Exception as e:  # noqa: BLE001
                logger.warning("cocoindex_stop_failed: %s", e)
            app.state.cocoindex_app = None
        if app.state.cocoindex_ready:
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


def create_app() -> FastAPI:  # noqa: C901 — readyz aggregate checks
    """Factory tạo FastAPI app — gọi 1 lần ở module-level và trong unit test."""
    settings = get_settings()
    app = FastAPI(
        title="Medinet Wiki API",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Middleware order — P11 PITFALL (FastAPI executes last-added FIRST cho
    # incoming request). Order REVERSED từ Go Gin. Outer-to-inner cho REQUEST:
    #   1) ErrorHandler   (outermost — catch mọi exception kể cả CORS leak)
    #   2) RequestId      (gắn X-Request-Id sớm để log downstream có ID)
    #   3) SecurityHeaders (X-Content-Type-Options, X-Frame-Options, ...)
    #   4) CORS           (preflight OPTIONS + Access-Control-Allow-*)
    #   5) [Phase 5 AUX-03] rate_limit (slowapi — placeholder stub Phase 3,
    #      Plan 03-04 KHÔNG wire; full enable Phase 5)
    #   6) router handler (innermost)
    #
    # Add order = REVERSED (innermost trước, outermost sau):
    #   add CORS → add SecurityHeaders → add RequestId → add ErrorHandler
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(ErrorHandlerMiddleware)  # LAST add = OUTERMOST

    # Mount auth router (Phase 3 AUTH-01..03 — login/refresh/logout/me).
    from app.auth import auth_router

    app.include_router(auth_router)

    # Mount documents router (Plan 04-04 INGEST-04..05).
    from app.routers import documents_router

    app.include_router(documents_router)

    # HTTPException → envelope handler (Plan 03-05 AUTH-04).
    # CRITICAL: Plan 03-01 ErrorHandlerMiddleware đã pass-through StarletteHTTPException
    # (isinstance check + raise). Mọi HTTPException từ dependency/route — bao gồm
    # MISSING_AUTHORIZATION/INVALID_TOKEN/TOKEN_REVOKED/USER_DISABLED từ get_current_user
    # và FORBIDDEN từ require_role — PHẢI reach handler này để envelope shape
    # {success:false, data:null, error:{code, message}, meta:null} render đúng.
    # Integration test tests/integration/test_rbac_dependency.py verify shape envelope
    # cho 401 missing-Bearer + 403 forbidden scenario.
    @app.exception_handler(HTTPException)
    async def http_exception_handler(
        request: FastAPIRequest, exc: HTTPException
    ) -> StarletteJSONResponse:
        """Map HTTPException → envelope `{success, data, error, meta}` D6 shape."""
        detail = exc.detail
        if isinstance(detail, dict) and "code" in detail and "message" in detail:
            code = str(detail["code"])
            message = str(detail["message"])
        elif isinstance(detail, str):
            code = "ERROR"
            message = detail
        else:
            code = "ERROR"
            message = str(detail)
        body = {
            "success": False,
            "data": None,
            "error": {"code": code, "message": message},
            "meta": None,
        }
        headers = exc.headers or None
        return StarletteJSONResponse(
            content=body, status_code=exc.status_code, headers=headers
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

        # JWT manager check (Phase 3).
        if getattr(app.state, "jwt_manager", None) is not None:
            checks["jwt"] = "ok"
        else:
            checks["jwt"] = "not_ready"
            all_ok = False

        if all_ok:
            return resp.ok(data=checks)
        return resp.service_unavailable(
            message=f"Dịch vụ chưa sẵn sàng: {checks}"
        )

    return app


# Module-level app instance — uvicorn `app.main:app` dùng cái này.
app = create_app()
