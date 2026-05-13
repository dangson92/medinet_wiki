"""Observability module — structlog JSON + request_id middleware + readiness state."""

from docling_pipeline.api.health import get_models_ready, set_models_ready
from docling_pipeline.observability.logging import (
    RequestIdMiddleware,
    configure_logging,
)

__all__ = [
    "RequestIdMiddleware",
    "configure_logging",
    "get_models_ready",
    "set_models_ready",
]
