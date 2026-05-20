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
from urllib.parse import urlparse

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Tổng hợp config runtime của MCP Service."""

    model_config = SettingsConfigDict(
        env_prefix="MCP_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Base URL của API Service (KHÔNG kèm /api).
    api_base_url: str = "http://localhost:8180"
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
