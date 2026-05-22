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

    # 0) Plan 10-01 HARD-01: structlog JSON output — gọi configure_structlog()
    #    TRƯỚC mọi step init khác để log của các step sau (db_pool_ready /
    #    redis_ready / cocoindex_setup_ok) cũng đã JSON-formatted với schema
    #    chuẩn (level/msg/ts/request_id/user_id/hub_id). Idempotent — re-call
    #    no-op (test boot LifespanManager nhiều lần KHÔNG nhân processor).
    from app.logging_config import configure_structlog

    configure_structlog()

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

    # 2.5) RAG config — load settings DB đã persist → apply os.environ + singleton.
    #      PHẢI chạy TRƯỚC setup_cocoindex (step 3): initial backfill embed mọi
    #      pending document và CẦN đúng provider/model admin đã lưu. Nếu load sau,
    #      backfill dùng config .env cũ (vd OPENAI_API_KEY placeholder) → embed fail.
    #      Best-effort: lỗi chỉ log, KHÔNG crash lifespan.
    if app.state.db_pool is not None:
        try:
            from app.services.rag_config_service import (
                load_persisted_into_runtime,
            )

            await load_persisted_into_runtime(app.state.db_pool)
            logger.info("rag_config_runtime_loaded")
        except Exception as e:  # noqa: BLE001
            logger.warning("rag_config_load_failed: %s", e)

    # 3) Cocoindex 1.0.3 init + initial backfill (Phase 4 Plan 04-03 REVISION 2 — INGEST-01..03).
    #    setup_cocoindex(settings) → register @coco.lifespan + coco.start_blocking
    #    + cocoindex_app.update_blocking() initial backfill cho mọi pending documents.
    #    KHÔNG còn live updater pattern cocoindex 0.x (Decision A4 user accepted:
    #    per-document trigger qua FastAPI BackgroundTasks ở Plan 04-04).
    #
    #    setup_cocoindex SYNC blocking — wrap asyncio.to_thread để KHÔNG block
    #    FastAPI lifespan event loop (cocoindex Rust core init + initial backfill
    #    có thể tốn vài giây nếu schema apply lần đầu hoặc nhiều pending rows).
    #
    #    Plan 04-07 gap closure: FAIL-FAST pattern thay fail-soft. Nếu setup_cocoindex
    #    raise (VectorSchemaProvider sai, Postgres không lên, schema build fail) →
    #    lifespan re-raise → uvicorn crash startup → operator phải fix root cause.
    #    KHÔNG mask architectural blocker bằng silent warning + cocoindex_app=None.
    app.state.cocoindex_app = None
    import asyncio
    import os

    # Test-mode escape hatch (DEF-05-01): cocoindex 1.0.3 `core.Environment` là
    # process-global singleton — KHÔNG re-open được sau khi đã open + close.
    # Integration test dùng fixture `app_with_auth` cho >1 test sẽ FAIL từ test
    # thứ 2 với `environment already open`. CRUD test (hub/user/apikey) KHÔNG
    # cần cocoindex ingestion flow — chỉ cần app + DB + auth. Khi env var
    # `COCOINDEX_SKIP_SETUP=1` set, bỏ qua setup_cocoindex() hoàn toàn; test cấp
    # mock `app.state.cocoindex_app` sau lifespan nếu cần (test_documents_list_delete).
    # Production KHÔNG bao giờ set flag này → behavior fail-fast giữ nguyên.
    if os.environ.get("COCOINDEX_SKIP_SETUP") == "1":
        logger.warning(
            "cocoindex_setup_skipped: COCOINDEX_SKIP_SETUP=1 (test mode — "
            "cocoindex Environment singleton không re-open được)"
        )
    else:
        from app.rag.setup import get_cocoindex_app, setup_cocoindex

        try:
            await asyncio.to_thread(setup_cocoindex, settings)
        except Exception as exc:
            logger.error(
                "cocoindex_init_failed_fail_fast: %s", exc, exc_info=True
            )
            raise  # ← Plan 04-07: fail-fast — KHÔNG mask blocker
        logger.info("cocoindex_setup_ok")
        app.state.cocoindex_app = get_cocoindex_app()
        app.state.cocoindex_ready = True
        logger.info("cocoindex_app_attached_to_app_state")

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

    # ──────────────────────────────────────────────────────────────────────
    # Phase 3 Plan 03-02 (SSO-01, D-V3-Phase3-B/D) — Hub con JWKS cache
    # ──────────────────────────────────────────────────────────────────────
    # Boot fail-loud nếu central JWKS endpoint down (D-V3-Phase3-B): timeout
    # 5s, exception → re-raise → uvicorn exit 1 (operator deploy thấy ngay).
    # Runtime fail-quiet (refresh task log warning + giữ cached). 24h hard
    # limit ở JWKSCache.get_public_key (R-V3-5 fail-loud delayed).
    # Central KHÔNG cần cache (verify JWT bằng local pem qua JWTManager).
    #
    # Test-mode escape hatch: env `JWKS_SKIP_FETCH=1` bypass blocking startup
    # cho integration test factor_hub_scoped boot lifespan với fake URL trỏ
    # central KHÔNG có (TestClient in-process, CENTRAL_JWKS_URL fake để pass
    # Settings validator — pattern song song COCOINDEX_SKIP_SETUP DEF-05-01).
    # Production KHÔNG bao giờ set flag này → fail-loud behavior giữ nguyên.
    app.state.jwks_cache = None
    if settings.hub_name != "central":
        if os.environ.get("JWKS_SKIP_FETCH") == "1":
            logger.warning(
                "jwks_cache_skipped: JWKS_SKIP_FETCH=1 (test mode — "
                "lifespan bypass blocking fetch_initial)"
            )
        else:
            from app.auth.jwks import JWKSCache

            if not settings.central_jwks_url:
                # Settings validator Plan 03-02 Task 1 đã enforce — defensive
                # bao thêm tránh race khi Settings cache override runtime.
                raise RuntimeError(
                    f"hub_name={settings.hub_name!r} thiếu CENTRAL_JWKS_URL "
                    "— Settings validator phải đã raise ở boot"
                )

            jwks_cache = JWKSCache(
                jwks_url=settings.central_jwks_url,
                refresh_interval=settings.jwks_refresh_interval,
                max_stale_seconds=settings.jwks_max_stale_seconds,
            )
            try:
                await jwks_cache.fetch_initial()  # blocking, raise on fail
            except Exception as e:
                logger.critical(
                    "lifespan_jwks_cache_init_failed: hub_name=%s url=%s error=%s — boot abort",
                    settings.hub_name,
                    settings.central_jwks_url,
                    e,
                )
                raise  # boot fail-loud D-V3-Phase3-B → uvicorn exit 1

            jwks_cache.start_refresh_task()
            app.state.jwks_cache = jwks_cache
            logger.info(
                "lifespan_jwks_cache_ready: hub_name=%s url=%s refresh_interval=%ds",
                settings.hub_name,
                settings.central_jwks_url,
                settings.jwks_refresh_interval,
            )

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

    # 8) Audit flush task (Phase 5 AUX-01 — asyncio.Queue batch flush 2s/128).
    app.state.audit_task = None
    try:
        from app.services.audit_service import audit_flush_loop

        app.state.audit_task = asyncio.create_task(audit_flush_loop())
        logger.info("audit_flush_task_started")
    except Exception as e:  # noqa: BLE001
        logger.warning("audit_flush_task_start_failed: %s", e)

    # 9) Search cache invalidation subscriber (Phase 6 SEARCH-04 — D-12).
    #    Lắng nghe Redis Pub/Sub hub:*:invalidate → xoá cache key của hub đó.
    app.state.search_cache_task = None
    if app.state.redis is not None:
        try:
            from app.services.search_cache import search_cache_subscriber

            app.state.search_cache_task = asyncio.create_task(
                search_cache_subscriber(app.state.redis)
            )
            logger.info("search_cache_subscriber_task_started")
        except Exception as e:  # noqa: BLE001
            logger.warning("search_cache_subscriber_start_failed: %s", e)

    try:
        yield
    finally:
        # Shutdown ngược thứ tự init — jwks_cache → watchdog → sqlalchemy → jwt → cocoindex → redis → db_pool.
        # Phase 3 Plan 03-02 — graceful shutdown JWKS cache asyncio task TRƯỚC
        # các shutdown khác (refresh task chỉ dùng httpx KHÔNG dùng DB/Redis,
        # cancel sớm để asyncio.sleep wake fast — KHÔNG block teardown khác).
        _shutdown_jwks_cache = getattr(app.state, "jwks_cache", None)
        if _shutdown_jwks_cache is not None:
            try:
                await _shutdown_jwks_cache.stop_refresh_task()
            except Exception as e:  # noqa: BLE001
                logger.warning("jwks_cache_stop_failed: %s", e)
            app.state.jwks_cache = None
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
        # Audit flush task (Phase 5 AUX-01) — flush_pending + cancel TRƯỚC
        # dispose_engine vì flush_pending dùng engine để batch INSERT audit_logs.
        if getattr(app.state, "audit_task", None) is not None:
            try:
                from app.services.audit_service import flush_pending

                await flush_pending()
            except Exception as e:  # noqa: BLE001
                logger.warning("audit_flush_pending_failed: %s", e)
            app.state.audit_task.cancel()
            try:
                await app.state.audit_task
            except asyncio.CancelledError:
                pass
            except Exception as e:  # noqa: BLE001
                logger.warning("audit_task_stop_failed: %s", e)
            app.state.audit_task = None
        # Search cache subscriber task (Phase 6 SEARCH-04) — cancel TRƯỚC redis
        # aclose (subscriber dùng redis connection). Đặt trước dispose_engine là
        # an toàn vì redis aclose ở cuối shutdown.
        if getattr(app.state, "search_cache_task", None) is not None:
            app.state.search_cache_task.cancel()
            try:
                await app.state.search_cache_task
            except asyncio.CancelledError:
                pass
            except Exception as e:  # noqa: BLE001
                logger.warning("search_cache_task_stop_failed: %s", e)
            app.state.search_cache_task = None
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
    """Factory tạo FastAPI app — gọi 1 lần ở module-level và trong unit test.

    v3.0 Phase 2 FACTOR-01..03 (D-V3-Phase2-A/B):
    Factory đọc settings.hub_name (Phase 1 TOPO-04 Literal central|yte|duoc|hcns)
    → conditional mount router. KHÔNG đổi signature no-arg để giữ uvicorn
    `app.main:app` entrypoint M2 compat. Test override qua monkeypatch.setenv
    + get_settings.cache_clear() trước khi gọi create_app().
    """
    settings = get_settings()

    # Phase 8.2 (đảo D-04): MCP server KHÔNG còn mount in-process. MCP là process
    # độc lập (`mcp_service/`) gọi API Service qua HTTP. App dùng trực tiếp
    # `lifespan` module-level — không còn compose lifespan MCP.
    app = FastAPI(
        title="Medinet Wiki API",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Middleware order — P11 PITFALL (FastAPI executes last-added FIRST cho
    # incoming request). Order REVERSED từ Go Gin. Outer-to-inner cho REQUEST:
    #   1) ErrorHandler   (outermost — catch mọi exception kể cả CORS leak)
    #   2) Prometheus     (Plan 10-02 HARD-02 — đo latency + count metric.
    #      Wrap toàn bộ middleware downstream + router. Đặt giữa RequestId
    #      và ErrorHandler — request_id đã set khi metric ghi, exception
    #      re-raise lên ErrorHandler render envelope sau khi metric ghi xong)
    #   3) RequestId      (gắn X-Request-Id sớm để log downstream có ID)
    #   4) SecurityHeaders (X-Content-Type-Options, X-Frame-Options, ...)
    #   5) CORS           (preflight OPTIONS + Access-Control-Allow-*)
    #   6) [Phase 5 AUX-03] rate_limit (slowapi — placeholder stub Phase 3,
    #      Plan 03-04 KHÔNG wire; full enable Phase 5)
    #   7) router handler (innermost)
    #
    # Add order = REVERSED (innermost trước, outermost sau):
    #   add CORS → add SecurityHeaders → add RequestId → add Prometheus → add ErrorHandler
    from app.observability import PrometheusMiddleware

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(PrometheusMiddleware)
    app.add_middleware(ErrorHandlerMiddleware)  # LAST add = OUTERMOST

    # ──────────────────────────────────────────────────────────────────────
    # v3.0 Phase 2 Plan 02-01 — Conditional router mount theo settings.hub_name
    # (FACTOR-01 1-codebase + FACTOR-02 strip central-only ở hub con).
    # Decision traceability: D-V3-Phase2-A (no-arg factory) + D-V3-Phase2-B
    # (inline conditional) + D-V3-Phase2-E (404 shape, KHÔNG 403) +
    # D-V3-Phase2-G (lifespan universal).
    # ──────────────────────────────────────────────────────────────────────

    # ──────────────────────────────────────────────────────────────────────
    # Tier 1 — Universal routers (mount ở MỌI process: central + hub con)
    # FACTOR-03 hub-scoped: auth/documents/profile/search/ask/usage + ai_chat
    # ──────────────────────────────────────────────────────────────────────
    # Note WRN-02 (Plan 02-01): ask_router + search_router universal mount —
    # cross-hub alias /api/ask/cross-hub + /api/search/answer hiện expose
    # ở hub con runtime (sẽ trả 500/local-fallback do DB hub con không có
    # data hub khác). KHÔNG có lỗ hổng leak data (DB-level isolation E-V3-3
    # Phase 1 enforce). Strip cross-hub variant defer Phase 4 SYNC-03.
    from app.auth import auth_router
    from app.routers import (
        ai_chat_router,
        ask_router,
        documents_router,
        profile_router,
        search_router,
        usage_router,
    )

    app.include_router(auth_router)
    app.include_router(documents_router)
    app.include_router(profile_router)
    app.include_router(search_router)
    app.include_router(ask_router)
    app.include_router(usage_router)
    app.include_router(ai_chat_router)

    # ──────────────────────────────────────────────────────────────────────
    # Tier 2 — Central-only routers (FACTOR-02 strip ở hub con)
    # 9 router admin/system mount CHỈ khi process = central.
    # Hub con (yte/duoc/hcns) nhận request central-only → 404 envelope
    # (ErrorHandlerMiddleware M2 wrap built-in 404 — D-V3-Phase2-E).
    # ──────────────────────────────────────────────────────────────────────
    if settings.hub_name == "central":
        from app.routers import (
            api_keys_router,
            audit_logs_router,
            hubs_router,
            mcp_oauth_internal_router,
            mcp_oauth_router,
            rag_config_router,
            sync_router,
            system_settings_router,
            users_router,
        )

        app.include_router(hubs_router)
        app.include_router(users_router)
        app.include_router(api_keys_router)
        app.include_router(audit_logs_router)
        app.include_router(rag_config_router)
        app.include_router(system_settings_router)
        app.include_router(sync_router)
        app.include_router(mcp_oauth_router)
        app.include_router(mcp_oauth_internal_router)

        # ──────────────────────────────────────────────────────────────────
        # Phase 3 Plan 03-01 (SSO-01, D-V3-Phase3-A) — JWKS endpoint RFC 7517
        # Central publish public RS256 key cho hub con + frontend Phase 5 + MCP
        # Phase 7 verify JWT. Endpoint PUBLIC (KHÔNG auth) + Cache-Control 1h
        # match Plan 03-02 hub con TTL. Single-key strategy v3.0-a; multi-key
        # rotation defer Phase 7.
        #
        # 503 fallback envelope khi PEM read fail (`make keys` missing) — shape
        # D6 chuẩn `{success:false, data:null, error:{code, message}, meta:null}`.
        # Mount TRONG block central-only (FACTOR-02 enforce) — hub con KHÔNG
        # mount -> 404 envelope D6 qua Starlette HTTPException handler (Plan
        # 02-03 Rule 2 fix carry forward).
        # ──────────────────────────────────────────────────────────────────
        from app.auth.jwks import publish_jwks

        @app.get(
            "/.well-known/jwks.json",
            tags=["jwks"],
            summary="JWK Set RFC 7517 — public key RS256 verify JWT",
        )
        async def jwks_endpoint() -> StarletteJSONResponse:
            """Trả JWK Set cho hub con/frontend/MCP verify JWT RS256.

            Plan 03-01 / SSO-01 / D-V3-Phase3-A. Public endpoint — KHÔNG auth.
            Cache 1h (matching hub con TTL Plan 03-02). Key rotation: `make keys`
            overwrite -> kid đổi tự nhiên qua _derive_kid SHA-256 PEM.
            """
            try:
                jwks = publish_jwks(settings.jwt_public_key_path)
            except (OSError, ValueError) as e:
                logger.error(
                    "jwks_publish_failed: path=%s error=%s",
                    settings.jwt_public_key_path,
                    e,
                )
                return StarletteJSONResponse(
                    status_code=503,
                    content={
                        "success": False,
                        "data": None,
                        "error": {
                            "code": "JWKS_UNAVAILABLE",
                            "message": (
                                "Không đọc được JWT public key. "
                                "Chạy 'make keys' để sinh lại."
                            ),
                        },
                        "meta": None,
                    },
                )
            return StarletteJSONResponse(
                content=jwks,
                headers={"Cache-Control": "public, max-age=3600"},
            )
    else:
        logger.info(
            "central_only_routers_skipped: hub_name=%s — 9 routers stripped "
            "(FACTOR-02 enforce)",
            settings.hub_name,
        )

    # Rate limiter (Phase 5 AUX-03 — slowapi). Plan 05-02 tạo module; wiring tại đây.
    # Endpoint Phase 5 decorate @limiter.limit = GET /api/audit-logs (Plan 05-05 W4).
    # search/ask 100/min Phase 6, upload 30/min Phase 4 — decoration defer.
    # KHÔNG cần add_middleware — handler đủ render 429 envelope.
    from slowapi.errors import RateLimitExceeded

    from app.middleware import limiter, rate_limit_exceeded_handler

    app.state.limiter = limiter
    # mypy --strict: Starlette add_exception_handler ký kiểu handler nhận
    # `Exception` chung; rate_limit_exceeded_handler hẹp hơn (RateLimitExceeded).
    # An toàn runtime — Starlette chỉ dispatch handler cho đúng loại exc.
    app.add_exception_handler(
        RateLimitExceeded,
        rate_limit_exceeded_handler,  # type: ignore[arg-type]
    )

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

    # v3.0 Plan 02-03 (D-V3-Phase2-E) — Starlette HTTPException handler wrap
    # built-in 404 routing-not-matched → envelope shape `{success:false,
    # data:null, error:{code:"NOT_FOUND", message}, meta:null}`.
    #
    # Lý do: handler `@app.exception_handler(HTTPException)` phía trên đăng ký
    # cho `fastapi.HTTPException` — KHÔNG match `starlette.exceptions.HTTPException`
    # mà Starlette routing raise khi path không match (router không mount). Hậu
    # quả: client nhận `{"detail":"Not Found"}` raw thay vì envelope D6.
    #
    # FACTOR-02 (Phase 2) yêu cầu hub con trả 404 envelope cho 8 router
    # central-only đã strip — D-V3-Phase2-E lock NOT_FOUND code (KHÔNG 403).
    # Handler riêng cho Starlette base class cover cả 2 trường hợp:
    # (1) router không mount ở hub con (FACTOR-02 strip), (2) path không tồn
    # tại ở central (typo URL). Cả 2 đều render envelope D6 shape.
    from starlette.exceptions import HTTPException as StarletteHTTPException

    @app.exception_handler(StarletteHTTPException)
    async def starlette_http_exception_handler(
        request: FastAPIRequest, exc: StarletteHTTPException
    ) -> StarletteJSONResponse:
        """Map Starlette HTTPException (routing 404, ...) → envelope D6.

        Plan 02-03 Task 2 / D-V3-Phase2-E — FACTOR-02 enforce 404 envelope
        khi router central-only strip ở hub con. KHÔNG dùng 403 (leak endpoint
        existence). Tận dụng `resp.not_found` helper để giữ đúng shape.
        """
        detail = exc.detail
        if isinstance(detail, dict) and "code" in detail and "message" in detail:
            code = str(detail["code"])
            message = str(detail["message"])
        elif isinstance(detail, str):
            # Starlette routing 404 set detail="Not Found" — map sang code
            # NOT_FOUND chuẩn (resp.not_found default). Code tường minh giúp
            # frontend switch trên error.code thay vì status_code thuần.
            if exc.status_code == 404:
                code = "NOT_FOUND"
            elif exc.status_code == 405:
                code = "METHOD_NOT_ALLOWED"
            else:
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

    # HubIsolationError → 403 envelope handler (HUB-02 / E4).
    from app.repositories.hub_isolation import HubIsolationError

    @app.exception_handler(HubIsolationError)
    async def hub_isolation_handler(
        request: FastAPIRequest, exc: HubIsolationError
    ) -> StarletteJSONResponse:
        """HubIsolationError → 403 envelope (HUB-02 / E4).

        Handler CHỈ render envelope 403. Audit 'security.hub_isolation_violation'
        do documents_service.delete() enqueue tại điểm reject (Task 2).
        """
        body = {
            "success": False,
            "data": None,
            "error": {"code": "FORBIDDEN", "message": str(exc)},
            "meta": None,
        }
        return StarletteJSONResponse(content=body, status_code=403)

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

    @app.get("/metrics")
    async def metrics_endpoint() -> Any:
        """Prometheus scrape endpoint (HARD-02 Plan 10-02).

        Outside `/api/*` namespace per Prometheus convention (cùng cấp `/healthz`).
        KHÔNG protect bằng JWT — Prometheus scrape internal network; production
        deploy đặt sau reverse proxy/firewall whitelist IP scrape server.
        Content-Type: `text/plain; version=0.0.4; charset=utf-8` (Prometheus
        exposition format chuẩn — `prometheus_client.CONTENT_TYPE_LATEST`).
        """
        from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
        from starlette.responses import Response as StarletteResponse

        return StarletteResponse(
            content=generate_latest(),
            media_type=CONTENT_TYPE_LATEST,
        )

    return app


# Module-level app instance — uvicorn `app.main:app` dùng cái này.
app = create_app()
