"""Models package — re-export mọi ORM class cho Alembic autogenerate.

Plan 03 (Alembic env.py) import * từ module này để target_metadata pick up
đủ 10 bảng. KHÔNG bỏ sót class — nếu thiếu, autogenerate sinh migration empty.

Tables:
    users, hubs, documents, chunks, audit_logs, usage_events,
    refresh_tokens, api_keys, settings, user_hubs (join)
"""
from __future__ import annotations

from app.models.audit import AuditLog
from app.models.auth import RefreshToken, User, UserHub
from app.models.chunk import Chunk
from app.models.document import DOCUMENT_STATUS_VALUES, Document
from app.models.hub import Hub
from app.models.settings import ApiKey, Setting
from app.models.usage import UsageEvent

__all__ = [
    "DOCUMENT_STATUS_VALUES",
    "ApiKey",
    "AuditLog",
    "Chunk",
    "Document",
    "Hub",
    "RefreshToken",
    "Setting",
    "UsageEvent",
    "User",
    "UserHub",
]
