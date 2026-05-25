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
from app.db.dsn import _to_asyncpg_dsn  # Phase 4 Plan 04-04 W3 fix — shared module
from app.middleware import (
    ErrorHandlerMiddleware,
    RequestIdMiddleware,
    SecurityHeadersMiddleware,
)
from app.pkg import response as resp

# Phase 4 Plan 04-04 — pgvector codec register cho central_sync_pool connections.
# BLOCKER 2 end-to-end serialization fix: Plan 04-03 PUSH_INSERT_CHUNK_SQL truyền
# $9 = list[float] → pgvector cần codec register per connection để encode list
# sang binary format vector. Optional import — pgvector dev dependency available
# tại runtime (pin pgvector==0.4.2 pyproject.toml).
try:
    from pgvector.asyncpg import register_vector
except ImportError:  # pgvector optional dev — KHÔNG raise import time
    register_vector = None


async def _init_central_sync_conn(conn: asyncpg.Connection) -> None:
    """Register pgvector codec cho central_sync_pool connections (BLOCKER 2 fix).

    Truyền vào `asyncpg.create_pool(init=...)` để mỗi connection trong pool có
    codec register sẵn → asyncpg encode list[float] → pgvector binary format
    khi worker push chunks qua $9 parameter (PUSH_INSERT_CHUNK_SQL Plan 04-03).
    """
    if register_vector is not None:
        await register_vector(conn)


logger = logging.getLogger(__name__)


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

    # ──────────────────────────────────────────────────────────────────────
    # Phase 4 Plan 04-04 (SYNC-01, D-V3-Phase4-A1/A3) — Hub con central_sync_pool
    # ──────────────────────────────────────────────────────────────────────
    # Hub con (settings.hub_name != "central") spawn dedicated asyncpg pool trỏ
    # medinet_central — worker (Plan 04-03 sync_worker_loop) push chunks ON
    # CONFLICT (id) DO UPDATE qua pool này.
    #
    # T-04-04-01 Spoofing mitigation: SELECT current_database() == 'medinet_central'
    # fail-fast nếu operator paste sai DSN (trỏ medinet_hub_yte thay vì
    # medinet_central) → boot raise → uvicorn exit 1. KHÔNG silent corrupt.
    #
    # BLOCKER 2 fix: create_pool(init=_init_central_sync_conn) register pgvector
    # codec per connection. KHÔNG register → worker truyền list[float] qua $9
    # parameter sẽ fail runtime mid-batch.
    #
    # R-V3-1 fail-loud — hub con KHÔNG init được central_sync_pool → re-raise
    # exit 1. Outbox accumulate vô tận nếu silent skip; chấp nhận downtime hub
    # con thay vì silent data loss.
    #
    # Test-mode escape hatch: env `SYNC_SKIP_CENTRAL_POOL=1` bypass blocking
    # create_pool cho integration test factor_hub_scoped boot lifespan với
    # fake URL trỏ medinet_hub_<hub> KHÔNG có Postgres thật (pattern song song
    # COCOINDEX_SKIP_SETUP DEF-05-01 + JWKS_SKIP_FETCH Plan 03-02). Phase 4
    # dedicated test (test_sync_lifespan_integration) mock asyncpg.create_pool
    # riêng — KHÔNG cần skip flag. Production KHÔNG bao giờ set flag này.
    app.state.central_sync_pool = None
    if settings.hub_name != "central" and os.environ.get("SYNC_SKIP_CENTRAL_POOL") == "1":
        logger.warning(
            "central_sync_pool_skipped: SYNC_SKIP_CENTRAL_POOL=1 (test mode — "
            "lifespan bypass blocking create_pool)"
        )
    elif settings.hub_name != "central":
        try:
            if not settings.central_sync_dsn:
                # Defensive guard — Settings validator (_enforce_central_sync_dsn_for_hub
                # Plan 04-02) đã raise nếu thiếu. Bao thêm tránh race khi Settings
                # cache override runtime.
                raise RuntimeError(
                    f"hub_name={settings.hub_name!r} thiếu CENTRAL_SYNC_DSN — "
                    "Settings validator phải đã raise ở boot."
                )
            app.state.central_sync_pool = await asyncpg.create_pool(
                dsn=_to_asyncpg_dsn(settings.central_sync_dsn),
                init=_init_central_sync_conn,  # BLOCKER 2 fix — pgvector codec per conn
                min_size=1,
                max_size=5,
                command_timeout=30,
            )
            # T-04-04-01 mitigation — verify pool kết nối ĐÚNG medinet_central
            async with app.state.central_sync_pool.acquire() as _verify_conn:
                actual_db = await _verify_conn.fetchval("SELECT current_database()")
            if actual_db != "medinet_central":
                raise RuntimeError(
                    f"CENTRAL_SYNC_DSN trỏ sai DB: expected 'medinet_central', "
                    f"got {actual_db!r}. Operator paste sai env — T-04-04-01."
                )
            logger.info(
                "central_sync_pool_ready: hub=%s target_db=%s pgvector_codec=%s",
                settings.hub_name,
                actual_db,
                register_vector is not None,
            )
        except Exception as exc:
            logger.critical(
                "central_sync_pool_init_failed_fail_fast: hub=%s err=%s",
                settings.hub_name,
                exc,
            )
            raise  # R-V3-1 fail-loud — hub con boot abort
    else:
        logger.info(
            "central_sync_pool_skipped: hub_name=central (D-V3-Phase4-A3 — "
            "central KHÔNG self-push)"
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

    # ──────────────────────────────────────────────────────────────────────
    # 9.5) Phase 4 Plan 04-06 (SYNC-04 / D-V3-Phase4-C3) — Central checksum scheduler
    # ──────────────────────────────────────────────────────────────────────
    # Central FastAPI lifespan asyncio task (naive asyncio.sleep loop — KHONG
    # can APScheduler dep moi). Daily 2AM COUNT(*) drift + Hourly TABLESAMPLE
    # BERNOULLI(1) hash drift → emit SYNC_COUNT_DRIFT + SYNC_HASH_DRIFT
    # Prometheus metrics (Plan 04-03 collectors).
    #
    # Central-only spawn — D-V3-Phase4-C3 LOCKED. Hub con KHONG own checksum
    # scheduler (Settings._enforce_checksum_hub_dsns_for_central validator
    # skip cho hub con — Plan 04-02 carry forward).
    #
    # KHONG fail-loud — checksum_scheduler_task la observability concern, fail
    # spawn → log warning + tiep tuc lifespan (R-V3-1 critical worker la
    # sync_worker_task hub con, KHONG phai scheduler central).
    app.state.checksum_scheduler_task = None
    if settings.hub_name == "central":
        try:
            from app.observability.checksum_scheduler import (
                checksum_scheduler_loop,
            )

            app.state.checksum_scheduler_task = asyncio.create_task(
                checksum_scheduler_loop(app)
            )
            logger.info("checksum_scheduler_task_started")
        except Exception as e:  # noqa: BLE001
            logger.warning("checksum_scheduler_task_start_failed: %s", e)
    else:
        logger.info(
            "checksum_scheduler_task_skipped: hub_name=%s (D-V3-Phase4-C3 — "
            "central-only)",
            settings.hub_name,
        )

    # ──────────────────────────────────────────────────────────────────────
    # 10) Phase 4 Plan 04-04 (SYNC-01/02/05, D-V3-Phase4-A1/A3/A5) — Hub con
    #     sync_worker_task spawn SAU central_sync_pool ready (step 4.5 trên).
    # ──────────────────────────────────────────────────────────────────────
    # In-process asyncio task (D-V3-Phase4-A3 LOCKED) — KHÔNG separate worker
    # container, KHÔNG central worker SPOF. Worker poll local sync_outbox →
    # push central qua app.state.central_sync_pool.
    #
    # Central skip spawn (D-V3-Phase4-A3) — log evidence sync_worker_skipped.
    # KHÔNG fail-loud worker (warning) vì Plan 04-03 worker logic đã defensive
    # skip nếu pool None; nếu spawn fail → log warning, lifespan tiếp tục
    # (R-V3-1 pool đã fail-loud ở step trên — KHÔNG cần double fail).
    app.state.sync_worker_task = None
    if settings.hub_name == "central":
        logger.info("sync_worker_task_skipped: hub_name=central (D-V3-Phase4-A3)")
    elif os.environ.get("SYNC_SKIP_CENTRAL_POOL") == "1":
        # Test mode — central_sync_pool đã skip, worker KHÔNG có pool acquire.
        logger.warning(
            "sync_worker_task_skipped: SYNC_SKIP_CENTRAL_POOL=1 (test mode)"
        )
    else:
        try:
            from app.sync import sync_worker_loop

            app.state.sync_worker_task = asyncio.create_task(
                sync_worker_loop(app)
            )
            logger.info(
                "sync_worker_task_started: hub=%s batch_size=%d poll_interval=%.1fs",
                settings.hub_name,
                settings.sync_batch_size,
                settings.sync_poll_interval,
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("sync_worker_task_start_failed: %s", e)

    # ──────────────────────────────────────────────────────────────────────
    # Phase 6 Plan 06-04 (SETTINGS-01..04, D-V3-Phase6-A/B/C/D) — Hub con settings_sync
    # ──────────────────────────────────────────────────────────────────────
    # Hub con (settings.hub_name != "central") spawn 3 client + 1 subscriber task.
    # - RagConfigClient.fetch_initial() blocking 5s (R-V3-6 LOW + D-V3-Phase6-A
    #   fail-loud boot pattern song song JWKSCache Plan 03-02).
    # - HubRegistryClient.fetch_initial() blocking 5s.
    # - ApiKeyVerifyClient KHÔNG fetch_initial (lazy — verify on demand qua
    #   require_api_key dependency Plan 06-03).
    # - settings_subscriber_task asyncio.create_task spawn subscribe settings:invalidate.
    #
    # Test-mode escape hatch: env `SETTINGS_SKIP_FETCH=1` bypass blocking fetch_initial
    # (pattern song song COCOINDEX_SKIP_SETUP + JWKS_SKIP_FETCH + SYNC_SKIP_CENTRAL_POOL).
    app.state.rag_config_client = None
    app.state.hub_registry_client = None
    app.state.api_key_verify_client = None
    app.state.settings_subscriber_task = None

    if settings.hub_name != "central":
        if os.environ.get("SETTINGS_SKIP_FETCH") == "1":
            logger.warning(
                "settings_sync_skipped: SETTINGS_SKIP_FETCH=1 (test mode — "
                "lifespan bypass blocking fetch_initial)"
            )
        else:
            from app.settings_sync.client import (
                ApiKeyVerifyClient,
                HubRegistryClient,
                RagConfigClient,
            )
            from app.settings_sync.subscriber import settings_subscriber_loop

            if not settings.central_url:
                raise RuntimeError(
                    f"hub_name={settings.hub_name!r} thiếu CENTRAL_URL — "
                    "Settings validator phải đã raise ở boot (Phase 3 Plan 03-04 "
                    "_enforce_central_url_for_hub)."
                )

            rag_client = RagConfigClient(
                central_url=settings.central_url,
                redis=app.state.redis,
                hub_name=settings.hub_name,
                ttl=settings.settings_cache_ttl_rag_config,
            )
            hub_client = HubRegistryClient(
                central_url=settings.central_url,
                redis=app.state.redis,
                hub_name=settings.hub_name,
                internal_auth_secret=settings.settings_proxy_secret,
                ttl=settings.settings_cache_ttl_hub_registry,
            )
            apikey_client = ApiKeyVerifyClient(
                central_url=settings.central_url,
                redis=app.state.redis,
                hub_name=settings.hub_name,
                settings_proxy_secret=settings.settings_proxy_secret,
                ttl=settings.settings_cache_ttl_apikey,
            )
            try:
                await rag_client.fetch_initial()  # blocking 5s, raise on fail
                await hub_client.fetch_initial()
            except Exception as e:
                logger.critical(
                    "lifespan_settings_sync_init_failed: hub_name=%s "
                    "central_url=%s err=%s — boot abort",
                    settings.hub_name,
                    settings.central_url,
                    e,
                )
                raise  # boot fail-loud D-V3-Phase6-A → uvicorn exit 1

            app.state.rag_config_client = rag_client
            app.state.hub_registry_client = hub_client
            app.state.api_key_verify_client = apikey_client

            # Spawn subscriber task (best-effort — Redis NOT ready KHÔNG fail-loud
            # per CONTEXT Claude's Discretion fail-quiet subscriber). Check
            # `app.state.redis_ready` (PING xác nhận live) thay vì only `redis is
            # not None` — `from_url()` lazy KHÔNG verify connection; ping() là
            # nguồn truth duy nhất xác định Redis usable (T-06-04-04 carry forward
            # M2 main.py:107-115 try/except pattern).
            if app.state.redis is not None and app.state.redis_ready:
                app.state.settings_subscriber_task = asyncio.create_task(
                    settings_subscriber_loop(
                        app.state.redis,
                        hub_name=settings.hub_name,
                        reconnect_seconds=settings.settings_subscriber_reconnect_seconds,
                    )
                )
                logger.info(
                    "settings_subscriber_task_started: hub=%s",
                    settings.hub_name,
                )
            else:
                logger.warning(
                    "settings_subscriber_skipped: redis_ready=%s — TTL natural fallback",
                    app.state.redis_ready,
                )
            logger.info(
                "lifespan_settings_sync_ready: hub=%s central_url=%s",
                settings.hub_name,
                settings.central_url,
            )

    try:
        yield
    finally:
        # ──────────────────────────────────────────────────────────────────
        # Phase 4 Plan 04-04 — Shutdown sync_worker_task + central_sync_pool
        # TRƯỚC mọi shutdown khác (worker chỉ dùng asyncpg + Pydantic — KHÔNG
        # dùng SQLAlchemy engine + Redis + cocoindex; cancel sớm tránh hold
        # outbox lock khi local db_pool đang shutdown).
        # ──────────────────────────────────────────────────────────────────
        # Graceful cancel — set_event đầu tiên KHÔNG có (worker dùng
        # CancelledError propagate); task.cancel() + wait_for timeout 10s.
        # Sau timeout 10s force re-cancel (defensive vs worker hang push
        # central runtime).
        if getattr(app.state, "sync_worker_task", None) is not None:
            app.state.sync_worker_task.cancel()
            try:
                await asyncio.wait_for(
                    app.state.sync_worker_task, timeout=10.0
                )
            except asyncio.CancelledError:
                pass
            except TimeoutError:
                logger.warning(
                    "sync_worker_task_shutdown_timeout: hub=%s — forcing exit",
                    settings.hub_name,
                )
            except Exception as e:  # noqa: BLE001
                logger.warning("sync_worker_task_stop_failed: %s", e)
            app.state.sync_worker_task = None

        # Close central_sync_pool SAU khi worker đã cancel (KHÔNG release pool
        # khi còn task acquire connection — asyncpg sẽ warn + block).
        if getattr(app.state, "central_sync_pool", None) is not None:
            try:
                await app.state.central_sync_pool.close()
            except Exception as e:  # noqa: BLE001
                logger.warning("central_sync_pool_close_failed: %s", e)
            app.state.central_sync_pool = None

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

        # ──────────────────────────────────────────────────────────────────
        # Phase 6 Plan 06-04 (SETTINGS-01..04 / D-V3-Phase6-C) — Graceful
        # shutdown settings_subscriber_task. Pattern song song sync_worker_task
        # Plan 04-04 + search_cache_task M2 — cancel + wait_for timeout 10s.
        # Subscriber finally block `pubsub.aclose()` đảm bảo Redis connection
        # close (T-06-04-03 resource exhaustion mitigation). Đặt TRƯỚC redis
        # aclose vì subscriber dùng redis connection.
        # ──────────────────────────────────────────────────────────────────
        if getattr(app.state, "settings_subscriber_task", None) is not None:
            app.state.settings_subscriber_task.cancel()
            try:
                await asyncio.wait_for(
                    app.state.settings_subscriber_task, timeout=10.0
                )
            except (asyncio.CancelledError, TimeoutError):
                pass
            except Exception as e:  # noqa: BLE001
                logger.warning("settings_subscriber_task_stop_failed: %s", e)
            app.state.settings_subscriber_task = None
            logger.info("settings_subscriber_task_stopped")

        # ──────────────────────────────────────────────────────────────────
        # Phase 4 Plan 04-06 (SYNC-04 / D-V3-Phase4-C3) — Graceful shutdown
        # checksum_scheduler_task (central-only). Pattern song song
        # sync_worker_task Plan 04-04: cancel + wait_for timeout 10s +
        # TimeoutError defensive log. Scheduler dung asyncpg pool acquire
        # per-hub (close trong finally cua checksum_scheduler_loop) — cancel
        # truoc dispose_engine an toan.
        # ──────────────────────────────────────────────────────────────────
        if getattr(app.state, "checksum_scheduler_task", None) is not None:
            app.state.checksum_scheduler_task.cancel()
            try:
                await asyncio.wait_for(
                    app.state.checksum_scheduler_task, timeout=10.0
                )
            except asyncio.CancelledError:
                pass
            except TimeoutError:
                logger.warning(
                    "checksum_scheduler_shutdown_timeout — forcing exit"
                )
            except Exception as e:  # noqa: BLE001
                logger.warning("checksum_scheduler_stop_failed: %s", e)
            app.state.checksum_scheduler_task = None
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
            search_cross_hub_router,
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
        # Phase 4 Plan 04-05 (SYNC-03 / D-V3-Phase4-D3) — Cross-hub aggregated
        # search central-only. Tách khỏi universal `search_router` (vẫn mount
        # mọi process cho local /api/search + /api/search/similar). Hub con
        # strip /api/search/cross-hub → 404 envelope D6 (FACTOR-02 extend).
        #
        # Public API `SearchService.search_cross_hub()` signature KHÔNG đổi —
        # backward compat M2 contract (ask_service.py consumer + frontend
        # api.ts crossHubSearch). Refactor Plan 04-05 chỉ chạm `_search_cross_hub_impl`
        # private + tách router cross-hub endpoint.
        # ──────────────────────────────────────────────────────────────────
        app.include_router(search_cross_hub_router)

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
