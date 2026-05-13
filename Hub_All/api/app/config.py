"""Application settings — pydantic-settings BaseSettings.

Đọc env vars từ .env file (dev) hoặc OS env (prod). Type-safe, validate sớm.

Tham chiếu:
- .env.example (Plan 02) — danh sách env vars chuẩn.
- R5 Pitfall 2 — `app_namespace` cố định "medinet_prod" mọi env.
- R1 Pitfall 1 — `rag_embedding_dim=1536` pin để pgvector HNSW index work.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Tổng hợp config runtime của Medinet Wiki API."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Runtime
    app_env: Literal["dev", "staging", "production"] = "dev"
    app_port: int = 8080
    log_level: str = "info"
    log_format: Literal["json", "console"] = "json"

    # Postgres — KHÔNG default (bắt buộc qua env)
    database_url: str = Field(...)
    cocoindex_database_url: str = Field(...)

    # Redis — KHÔNG default (bắt buộc qua env)
    redis_url: str = Field(...)

    # CocoIndex (R5 mitigation — cố định namespace để không "biến mất" bảng giữa env)
    app_namespace: str = "medinet_prod"
    cocoindex_db_schema: str = "cocoindex"

    # JWT
    jwt_private_key_path: Path = Path("./keys/private.pem")
    jwt_public_key_path: Path = Path("./keys/public.pem")
    jwt_access_token_ttl: int = 900
    jwt_refresh_token_ttl: int = 604800

    # File storage
    file_store_dir: Path = Path("./file_store")

    # RAG (Phase 4-7 wiring — pin dim 1536 cho R1 pgvector HNSW index)
    rag_embedding_provider: str = "openai"
    rag_embedding_model: str = "text-embedding-3-small"
    rag_embedding_dim: int = 1536
    rag_llm_provider: str = "openai"
    rag_llm_model: str = "gpt-4o-mini"

    # External keys (Phase 7)
    openai_api_key: str = "sk-replace-me"
    gemini_api_key: str = "replace-me"

    # Settings encryption (Phase 5)
    aes_key: str = "replace-with-32-byte-base64-key"

    # CORS (Phase 3 sẽ wire vào middleware — Phase 1 chỉ load + expose)
    cors_allowed_origins: list[str] = Field(default_factory=list)

    @field_validator("cors_allowed_origins", mode="before")
    @classmethod
    def _parse_csv(cls, v: str | list[str]) -> list[str]:
        """Parse "a,b,c" → ["a","b","c"]; cho phép pass list trực tiếp."""
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v


@lru_cache
def get_settings() -> Settings:
    """Singleton settings instance — cache để tránh re-parse env mỗi lần gọi."""
    return Settings()  # type: ignore[call-arg]
