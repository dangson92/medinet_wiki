"""Settings load từ env vars qua pydantic-settings.

Đọc tất cả env DOCLING_* và provide qua get_settings() lru_cache.
Tham chiếu CONTEXT.md mục D + E + Schema response cho semantics từng field.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Cấu hình runtime — đọc từ env DOCLING_* (case-insensitive)."""

    model_config = SettingsConfigDict(
        env_prefix="DOCLING_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ─── OCR ───
    ocr_engine: Literal["tesseract", "rapidocr"] = "tesseract"
    ocr_langs: str = "vie+eng"

    # ─── Tokenizer cho HybridChunker ───
    tokenizer_name: str = "cl100k_base"
    max_tokens_per_chunk: int = Field(default=512, gt=0)

    # ─── Limits ───
    max_file_mb: int = Field(default=50, gt=0)
    request_timeout_sec: int = Field(default=180, gt=0)

    # ─── Logging ───
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_format: Literal["json", "console"] = "json"

    # ─── Service ───
    host: str = "0.0.0.0"
    port: int = 8001

    @property
    def max_file_bytes(self) -> int:
        return self.max_file_mb * 1024 * 1024


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Singleton settings — cache cho hot path."""
    return Settings()
