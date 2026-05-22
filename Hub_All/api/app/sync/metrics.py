"""Phase 4 Plan 04-03 Task 2 stub — 6 Prometheus collectors for cross-hub sync.

Real implementation lands ở Task 2 GREEN commit. Stub này tránh import error
cho Task 1 test (test_sync_models.py).
"""
from __future__ import annotations

from typing import Any


def normalize_error_class(exc: BaseException) -> str:
    """Stub — real impl Task 2."""
    return "unknown"


SYNC_LAG_SECONDS: Any = None
SYNC_OUTBOX_PENDING: Any = None
SYNC_ATTEMPT_TOTAL: Any = None
SYNC_DEAD_TOTAL: Any = None
SYNC_COUNT_DRIFT: Any = None
SYNC_HASH_DRIFT: Any = None
