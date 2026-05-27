"""Routers package — APIRouter modular cho mỗi domain.

Phase 4 ship documents_router (INGEST-04, INGEST-05).
Phase 5 thêm hubs_router, users_router, profile_router, api_keys_router,
audit_logs_router (HUB-01..03, USER-01..03, AUX-01..03).
rag_config_router — port endpoint Go /api/rag-config (ASK-04, build sớm Phase 7).
Phase 6 thêm search_router (SEARCH-01..03 — 3 endpoint POST).
Phase 7 thêm usage_router (ASK-05 — 3 endpoint GET token usage) +
ask_router (ASK-01/02/03 — POST /api/ask + /cross-hub + alias /api/search/answer).
Phase 8 thêm ai_chat_router (COMPAT-01 — POST /api/ai/chat proxy LLM cho
GeminiAssistant, BLOCKER 08-CONTRACT-DIFF).
sync_router — compat stub cho endpoint Go-era /api/sync/* (D6 — frontend React
chưa sửa vẫn gọi; M2 không port feature sync queue).
system_settings_router — port endpoint Go-era /api/system-settings (D6 —
Settings.tsx tab Chung/Bảo mật/Thông báo gọi; persist key-value bảng settings).

v3.0 Phase 4 Plan 04-05 (SYNC-03 / D-V3-Phase4-D3) — thêm
`search_cross_hub_router` re-export từ `app.routers.search.cross_hub_router`.
Universal `search_router` mount mọi process; `search_cross_hub_router` chỉ mount
ở central (main.py block central-only). Hub con strip → 404 envelope D6.
"""
from __future__ import annotations

from app.routers.ai_chat import router as ai_chat_router
from app.routers.api_keys import router as api_keys_router
from app.routers.ask import router as ask_router
from app.routers.audit_logs import router as audit_logs_router
from app.routers.documents import router as documents_router
from app.routers.guides import router as guides_router
from app.routers.hubs import router as hubs_router
from app.routers.mcp_oauth import internal_router as mcp_oauth_internal_router
from app.routers.mcp_oauth import router as mcp_oauth_router
from app.routers.profile import router as profile_router
from app.routers.rag_config import router as rag_config_router
from app.routers.search import cross_hub_router as search_cross_hub_router
from app.routers.search import router as search_router
from app.routers.sync import router as sync_router
from app.routers.system_settings import router as system_settings_router
from app.routers.usage import router as usage_router
from app.routers.users import router as users_router

__all__ = [
    "ai_chat_router",
    "api_keys_router",
    "ask_router",
    "audit_logs_router",
    "documents_router",
    "guides_router",
    "hubs_router",
    "mcp_oauth_internal_router",
    "mcp_oauth_router",
    "profile_router",
    "rag_config_router",
    "search_cross_hub_router",
    "search_router",
    "sync_router",
    "system_settings_router",
    "usage_router",
    "users_router",
]
