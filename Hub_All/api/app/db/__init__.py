"""Database layer — SQLAlchemy 2.0 async + pgvector.

Public API:
    from app.db import Base, UUIDMixin, TimestampMixin, Vector, get_session
"""
from __future__ import annotations

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDMixin
from app.db.session import (
    dispose_engine,
    get_engine,
    get_session,
    init_engine,
)
from app.db.types import Vector

__all__ = [
    "Base",
    "TimestampMixin",
    "UUIDMixin",
    "Vector",
    "dispose_engine",
    "get_engine",
    "get_session",
    "init_engine",
]
