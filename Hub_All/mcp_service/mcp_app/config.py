"""Cấu hình runtime của MCP Service — pydantic-settings BaseSettings.

Đọc env var prefix `MCP_` từ `.env` (dev) hoặc OS env (prod). Validate sớm:
- `api_base_url` phải dùng scheme http/https (chống SSRF/misconfiguration — T-08.2-01-T).
- Trailing slash bị strip để nối path nhất quán.

MCP Service KHÔNG cần config DB/Redis — mọi data đi qua API Service.
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


@functools.lru_cache
def get_settings() -> Settings:
    """Trả về singleton Settings — cache để đọc env một lần."""
    return Settings()
