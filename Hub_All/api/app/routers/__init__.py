"""Routers package — APIRouter modular cho mỗi domain.

Phase 4 ship documents_router (INGEST-04, INGEST-05).
Phase 5 thêm hubs_router, users_router, profile_router, api_keys_router,
audit_logs_router (HUB-01..03, USER-01..03, AUX-01..03).
rag_config_router — port endpoint Go /api/rag-config (ASK-04, build sớm Phase 7).
"""
from __future__ import annotations

from app.routers.api_keys import router as api_keys_router
from app.routers.audit_logs import router as audit_logs_router
from app.routers.documents import router as documents_router
from app.routers.hubs import router as hubs_router
from app.routers.profile import router as profile_router
from app.routers.rag_config import router as rag_config_router
from app.routers.users import router as users_router

__all__ = [
    "api_keys_router",
    "audit_logs_router",
    "documents_router",
    "hubs_router",
    "profile_router",
    "rag_config_router",
    "users_router",
]
