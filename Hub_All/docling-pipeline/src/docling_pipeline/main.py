"""FastAPI app entrypoint — lifespan warm models (B5 semantics) + middleware + routers.

Run local:
    uvicorn docling_pipeline.main:app --host 0.0.0.0 --port 8001

B5 lifespan semantics (Plan 06):
| Trường hợp                         | import docling | warm_models()   | _models_ready | /readyz |
|------------------------------------|----------------|-----------------|---------------|---------|
| (a) Library không cài              | ImportError    | (không chạy)    | False         | 503     |
| (b) Library OK, warm fail transient| OK             | Exception       | True          | 200     |
| (c) Library OK, warm OK            | OK             | OK              | True          | 200     |

Phân biệt rõ ràng giúp ops biết khi nào restart container (case a — env hỏng) vs để
service tự warm lazy (case b — request đầu chậm hơn).
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

import structlog
import uvicorn
from fastapi import FastAPI

from docling_pipeline.api import health, process
from docling_pipeline.config import get_settings
from docling_pipeline.observability.logging import (
    RequestIdMiddleware,
    configure_logging,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan B5 — phân biệt 3 case ImportError vs warm transient fail vs warm OK."""
    configure_logging()
    logger = structlog.get_logger(__name__)
    settings = get_settings()
    logger.info(
        "service_starting",
        ocr_engine=settings.ocr_engine,
        ocr_langs=settings.ocr_langs,
        tokenizer=settings.tokenizer_name,
        max_file_mb=settings.max_file_mb,
        timeout_sec=settings.request_timeout_sec,
        host=settings.host,
        port=settings.port,
    )

    # ── B5 readiness logic ──
    try:
        # Lazy import — guard ImportError ở lifespan thay vì module top.
        # Nếu Docling không cài được, FastAPI app vẫn start (process còn sống cho /healthz),
        # NHƯNG /readyz trả 503 → orchestrator/k8s biết container không serve được.
        from docling_pipeline.core.extractor import warm_models

        try:
            await asyncio.to_thread(warm_models)
            health.set_models_ready(True)
            logger.info("models_warmed", state="ready")
        except Exception as exc:  # noqa: BLE001
            # Case (b) transient warm fail — vẫn ready=True
            logger.warning(
                "warm_dummy_failed_but_library_ok",
                error=str(exc),
                note="service vẫn serve được, request đầu sẽ chậm hơn",
            )
            health.set_models_ready(True)
    except ImportError as exc:
        # Case (a) — fatal, ready=False vĩnh viễn cho đến khi user fix env
        logger.error(
            "docling_library_unavailable",
            error=str(exc),
            critical=True,
            note="/readyz sẽ trả 503 cho đến khi user pip install docling==2.91.0",
        )
        health.set_models_ready(False)

    yield

    logger.info("service_stopping")


def create_app() -> FastAPI:
    """Factory FastAPI app — testable + reusable cho uvicorn."""
    app = FastAPI(
        title="Medinet Docling Sidecar",
        description="Extract + chunk service cho RAG ingestion (M1 — Docling Quality)",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_middleware(RequestIdMiddleware)
    app.include_router(health.router)
    app.include_router(process.router)
    return app


app = create_app()


if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run(
        "docling_pipeline.main:app",
        host=settings.host,
        port=settings.port,
        workers=1,  # CONTEXT mục D — Docling parser KHÔNG thread-safe
        log_config=None,  # structlog đã configure ở lifespan
    )


__all__ = ["app", "create_app", "lifespan"]
