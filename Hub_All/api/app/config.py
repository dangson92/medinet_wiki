"""Application settings — pydantic-settings BaseSettings.

Đọc env vars từ .env file (dev) hoặc OS env (prod). Type-safe, validate sớm.

Tham chiếu:
- .env.example (Plan 02) — danh sách env vars chuẩn.
- R5 Pitfall 2 — `app_namespace` cố định "medinet_prod" mọi env.
- R1 Pitfall 1 — `rag_embedding_dim=1536` pin để pgvector HNSW index work.
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, ValidationInfo, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


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
    # 8180 — frontend api.ts hardcode (Hyper-V excluded range 8038-8137 Windows).
    app_port: int = 8180
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

    # Cocoindex 1.0.3 LMDB path (Q5 — replace COCOINDEX_DATABASE_URL Postgres
    # cocoindex 0.x assumption sai). Cocoindex internal state (memo cache,
    # fingerprint, lineage) lưu LMDB local filesystem. Default tương đối project root.
    # Default TƯƠNG ĐỐI `.cocoindex/` (không tiền tố `Hub_All/`) — writable trong
    # mọi cwd: chạy native uvicorn (cwd `api/`) hoặc container override env tuyệt đối.
    # Gap SC5 fix — Hub_All/ prefix gây Permission denied trong container.
    cocoindex_lmdb_path: Path = Path(".cocoindex/state.lmdb")

    # Watchdog timeout — Plan 04-05 REVISION 2 NEW (INGEST-06, P8 mitigation).
    # 5 phút headroom cho `cocoindex_app.update_blocking()` documents lớn (DOCX 50
    # trang + N×embed LiteLLM có thể chạy >2 phút). Tránh false-flip processing
    # rows. Configurable qua env `WATCHDOG_TIMEOUT_SECONDS`.
    watchdog_timeout_seconds: int = 300

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
    # Model OpenAI — dùng khi rag_llm_provider != "gemini".
    rag_llm_model: str = "gpt-4o-mini"
    # Model Gemini — field RIÊNG, dùng khi rag_llm_provider == "gemini".
    # Tách khỏi rag_llm_model để rag-config đổi model Gemini KHÔNG ghi đè model
    # OpenAI (xem rag_config_service._apply_runtime / load_persisted_into_runtime).
    rag_gemini_llm_model: str = "gemini-2.5-flash"

    # External keys (Phase 7)
    openai_api_key: str = "sk-replace-me"
    gemini_api_key: str = "replace-me"

    # Settings encryption (Phase 5)
    aes_key: str = "replace-with-32-byte-base64-key"

    # Audit logger (Phase 5 AUX-01 — asyncio.Queue batch flush)
    audit_batch_size: int = 128
    audit_flush_interval_seconds: float = 2.0
    audit_queue_max_size: int = 10000
    # Rate limit (Phase 5 AUX-03 — slowapi; Plan 05-02 consume)
    rate_limit_search_per_minute: int = 100
    rate_limit_upload_per_minute: int = 30
    rate_limit_audit_logs_per_minute: int = 60
    rate_limit_enabled: bool = True

    # CORS (Phase 3 wire vào middleware — Phase 1 đã load + expose)
    # NoDecode: pydantic-settings v2 mặc định JSON-decode complex type → CSV
    # `http://a:5173,http://b:5173` raise SettingsError. NoDecode để raw string
    # đi thẳng vào `_parse_csv` validator (mode="before").
    cors_allowed_origins: Annotated[list[str], NoDecode] = Field(default_factory=list)

    @field_validator("cors_allowed_origins", mode="before")
    @classmethod
    def _parse_csv(cls, v: str | list[str]) -> list[str]:
        """Parse "a,b,c" → ["a","b","c"]; cho phép pass list trực tiếp."""
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    @field_validator("cors_allowed_origins", mode="after")
    @classmethod
    def _no_lan_in_prod(cls, v: list[str], info: ValidationInfo) -> list[str]:
        """Reject LAN/localhost origin trong production env (P12 mitigation).

        Nếu deploy production mà CORS list lọt `http://192.168.x.x` hoặc `localhost`,
        attacker trong cùng LAN có thể bypass CORS gọi API → leak credentials.
        Fail-fast ngay startup, KHÔNG defer runtime.

        Dev/staging chấp nhận localhost — chỉ reject khi `app_env=="production"`.
        """
        if info.data.get("app_env") != "production":
            return v
        forbidden_patterns = [
            r"localhost",
            r"127\.0\.0\.1",
            r"0\.0\.0\.0",
            r"192\.168\.",
            r"\b10\.",
            r"172\.(1[6-9]|2[0-9]|3[01])\.",
        ]
        for origin in v:
            for pat in forbidden_patterns:
                if re.search(pat, origin):
                    raise ValueError(
                        f"Production cấm CORS origin LAN/localhost: {origin!r} "
                        f"(match pattern {pat!r}). P12 mitigation."
                    )
        return v


@lru_cache
def get_settings() -> Settings:
    """Singleton settings instance — cache để tránh re-parse env mỗi lần gọi."""
    return Settings()
