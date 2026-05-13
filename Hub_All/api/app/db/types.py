"""Custom SQLAlchemy types — re-export pgvector cho consistent import path.

Plan 02 models dùng `from app.db.types import Vector` thay vì
`from pgvector.sqlalchemy import Vector` trực tiếp — tách logic versioning lib.
"""
from __future__ import annotations

from pgvector.sqlalchemy import Vector

__all__ = ["Vector"]
