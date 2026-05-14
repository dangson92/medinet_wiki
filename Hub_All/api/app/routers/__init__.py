"""Routers package — APIRouter modular cho mỗi domain.

Phase 4 ship documents_router (INGEST-04, INGEST-05).
Phase 5 sẽ thêm hubs_router, users_router, audit_router.
"""
from __future__ import annotations

from app.routers.documents import router as documents_router

__all__ = ["documents_router"]
