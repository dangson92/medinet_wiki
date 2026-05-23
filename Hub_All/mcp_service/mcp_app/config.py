"""Cấu hình runtime của MCP Service — pydantic-settings BaseSettings.

Đọc env var prefix `MCP_` từ `.env` (dev) hoặc OS env (prod). Validate sớm:
- `api_base_url` phải dùng scheme http/https (chống SSRF/misconfiguration — T-08.2-01-T).
- `oauth_issuer_url` (Phase 8.3) phải dùng scheme http/https + có host
  (issuer sai làm OAuth discovery/redirect hỏng — Pitfall 6).
- Trailing slash bị strip để nối path nhất quán.

MCP Service KHÔNG cần config DB/Redis chung — mọi data wiki đi qua API Service.
Phase 8.3 thêm field OAuth: issuer URL public + đường dẫn SQLite OAuth state store
cục bộ (clients/codes/tokens/pending) + lifetime token OAuth.
"""
from __future__ import annotations

import functools
from typing import Annotated
from urllib.parse import urlparse

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Tổng hợp config runtime của MCP Service."""

    model_config = SettingsConfigDict(
        env_prefix="MCP_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Base URL của API Service v3.0 — central aggregator (D-V3-02 LOCKED, KHÔNG fan-out N hub).
    # D-V3-Phase7-C LOCKED 2026-05-23 — MCP re-point central (carry forward Phase 2 docker-compose env wire).
    # MCP tools search_wiki + ask_wiki forward tới central; cross-hub search 1 SQL aggregated
    # (Phase 4 Plan 04-05 D-V3-Phase4-D1). Validator _validate_base_url enforce scheme http/https
    # + host required (T-08.2-01-T SSRF mitigation carry forward Phase 8.3 v2.0).
    api_base_url: str = "http://python-api-central:8080"
    # Host và port MCP Service lắng nghe.
    service_host: str = "0.0.0.0"
    service_port: int = 8190
    # Timeout (giây) cho mỗi request HTTP tới API Service.
    http_timeout: float = 30.0

    # --- OAuth (Phase 8.3) ---
    # URL public HTTPS mà Claude web truy cập — dùng làm issuer trong OAuth metadata.
    # Dev có thể để http://localhost:8190; prod PHẢI https (Pitfall 6).
    # CÓ DEFAULT cố ý: Settings() không raise khi thiếu env → well-known route trả 200
    # ngay từ lúc start (Dockerfile HEALTHCHECK Plan 04 dựa vào tính tất định này).
    oauth_issuer_url: str = "http://localhost:8190"
    # Đường dẫn file SQLite lưu OAuth state. Tương đối cho native dev,
    # override tuyệt đối (vd /app/.oauth/state.db) cho Docker volume.
    oauth_state_db_path: str = ".oauth/state.db"
    # Lifetime token OAuth do MCP Service tự phát (giây).
    oauth_access_token_ttl: int = 3600       # 1 giờ
    oauth_refresh_token_ttl: int = 2592000   # 30 ngày

    # Shared secret giữa MCP service ↔ API service cho endpoint internal
    # `GET /api/internal/mcp/clients/{id}` (per-user pre-registered OAuth).
    # MCP gửi `Authorization: Bearer <oauth_internal_token>`; API verify match
    # env `MCP_INTERNAL_TOKEN`. Rỗng = tắt fallback API → pre-registered client
    # không hoạt động (chỉ còn DCR), bind cứng cũng bị skip.
    oauth_internal_token: str = ""

    # Path prefix khi deploy MCP dưới cùng domain với app khác (vd reverse
    # proxy `wiki.example.com/mcp/*` → MCP service). Rỗng = deploy ở
    # authority root (subdomain riêng); non-empty = wrap toàn bộ FastMCP
    # app dưới prefix này + serve metadata RFC 8414/9728 với path suffix.
    # Khớp với segment cuối của `oauth_issuer_url` (vd issuer .../mcp →
    # prefix "mcp"). Sửa cả 2 cùng lúc khi đổi deploy mode.
    path_prefix: str = ""

    # CRIT-01 fix (audit 2026-05-21 — Plan 10-04): tách 2 CORS policy.
    # Metadata path (/.well-known/*) → wildcard origin "*" per RFC 8414 §3.1.
    # Sensitive path (/token, /authorize, /revoke, /register, /mcp[/*]) →
    # whitelist origin (chỉ echo Access-Control-Allow-Origin nếu match).
    # Default whitelist cover Claude web + MCP Inspector + dev localhost
    # Inspector port 6274. Ops thêm origin custom qua env
    # `MCP_OAUTH_SENSITIVE_ALLOWED_ORIGINS=https://a,https://b` comma-separated.
    #
    # `validation_alias` ép pydantic-settings đọc đúng env
    # `MCP_OAUTH_SENSITIVE_ALLOWED_ORIGINS` thay vì auto-derive từ
    # `env_prefix=MCP_` + field name (sẽ ra `MCP_MCP_OAUTH_...` sai).
    #
    # `NoDecode` annotation TẮT JSON-decode mặc định của pydantic-settings cho
    # field list[str] — cho phép validator `mode="before"` nhận RAW string env
    # và split comma-separated (pydantic-settings default cố parse JSON).
    mcp_oauth_sensitive_allowed_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: [
            "https://claude.ai",
            "https://inspector.modelcontextprotocol.io",
            "http://localhost:6274",
            "http://127.0.0.1:6274",
        ],
        validation_alias="MCP_OAUTH_SENSITIVE_ALLOWED_ORIGINS",
    )

    @field_validator("mcp_oauth_sensitive_allowed_origins", mode="before")
    @classmethod
    def _split_sensitive_origins(cls, v: object) -> object:
        """Parse env string comma-separated → list[str].

        Pydantic-settings default đọc list từ JSON. Ép parse string
        "a,b,c" → ["a", "b", "c"] cho ops set env var thuận tay.
        """
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        return v

    @field_validator("api_base_url", mode="after")
    @classmethod
    def _validate_base_url(cls, value: str) -> str:
        """Validate base URL: strip trailing slash, ép scheme http/https, bắt buộc có host."""
        stripped = value.rstrip("/")
        parsed = urlparse(stripped)
        if parsed.scheme not in ("http", "https"):
            raise ValueError(
                "MCP_API_BASE_URL phải dùng scheme http hoặc https "
                "— chống SSRF/misconfiguration"
            )
        if not parsed.netloc:
            raise ValueError("MCP_API_BASE_URL thiếu host")
        return stripped

    @field_validator("oauth_issuer_url", mode="after")
    @classmethod
    def _validate_issuer_url(cls, value: str) -> str:
        """Validate issuer URL: strip trailing slash, ép scheme http/https, bắt buộc host.

        OAuth metadata `issuer` PHẢI là URL Claude web truy cập được — issuer sai
        làm discovery + redirect hỏng (Pitfall 6).
        """
        stripped = value.rstrip("/")
        parsed = urlparse(stripped)
        if parsed.scheme not in ("http", "https"):
            raise ValueError(
                "MCP_OAUTH_ISSUER_URL phải dùng scheme http hoặc https"
            )
        if not parsed.netloc:
            raise ValueError("MCP_OAUTH_ISSUER_URL thiếu host")
        return stripped


@functools.lru_cache
def get_settings() -> Settings:
    """Trả về singleton Settings — cache để đọc env một lần."""
    return Settings()
