"""RAG config service — port endpoint Go /api/rag-config sang Python (ASK-04).

Persist key-value vào bảng `settings` (JSONB scalar). API key mã hoá AES-GCM
at-rest (reuse `app.pkg.crypto` — cùng cơ chế `api_keys.key_hash`, T-05-05-01).

Hot-swap runtime (KHÔNG cần restart process):
- set `os.environ` — LiteLLM đọc `OPENAI_API_KEY` / `GEMINI_API_KEY` tự động.
- mutate `get_settings()` singleton — `embedder.py` đọc `rag_embedding_model` /
  `rag_embedding_provider` mỗi lần `embed_text()` nên provider mới có hiệu lực ngay.

Startup `load_persisted_into_runtime()`: đọc lại settings DB → apply env +
singleton để giá trị admin lưu giữ qua restart (lifespan main.py gọi).
"""
from __future__ import annotations

import json
import logging
import math
import os
import re
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.pkg.crypto import decrypt_secret, encrypt_secret
from app.schemas.rag_config import EmbeddingCostPreview, UpdateRagConfigRequest

logger = logging.getLogger(__name__)

# Keys lưu encrypted (AES-GCM) trong settings.value — KHÔNG plaintext at-rest.
_SECRET_KEYS = frozenset({"OPENAI_API_KEY", "GEMINI_API_KEY"})

# Placeholder mặc định trong config.py — coi như "chưa cấu hình".
_PLACEHOLDERS = frozenset({"sk-replace-me", "replace-me", ""})

_VALID_EMBEDDING_PROVIDERS = frozenset({"openai", "gemini"})
_VALID_LLM_PROVIDERS = frozenset({"openai", "gemini", "auto"})

# Default chunk config — M2 dùng vn_chunker; các giá trị này chỉ để echo cho UI.
_DEFAULT_CHUNK_SIZE = 512
_DEFAULT_CHUNK_OVERLAP = 64
_DEFAULT_BATCH_SIZE = 32
_DEFAULT_GEMINI_LLM_MODEL = "gemini-2.5-flash"

# R7 / ASK-04 — dimension guard + cost preview cho embedding hot-swap.
PINNED_DIM = 1536  # M2 pin dim 1536 cho cả OpenAI/Gemini (R1 pgvector HNSW limit).
COST_PER_CHUNK_USD = 0.000013  # ≈ text-embedding-3-small $0.02/1M token, ~650 token/chunk.
CHUNKS_PER_MINUTE = 450  # ~7-8 embed/s qua LiteLLM.


def _embedding_dim_of(model: str) -> int:
    """Dim từ model name — hậu tố '@<dim>' (vd 'gemini-embedding-001@3072')
    → dim đó; không có hậu tố → 1536 (M2 pin). Quy ước M2 (D-07-03-A)."""
    m = re.search(r"@(\d+)\s*$", model.strip())
    return int(m.group(1)) if m else PINNED_DIM


def mask_key(key: str | None) -> str:
    """Che API key — giữ 8 ký tự đầu + 4 cuối, KHÔNG bao giờ trả full key."""
    if not key:
        return ""
    if len(key) <= 12:
        return "****"
    return f"{key[:8]}****{key[-4:]}"


def _coerce_int(value: Any, default: int) -> int:
    """JSONB value → int, fallback default nếu parse fail."""
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def _parse_jsonb(raw: Any) -> Any:
    """Raw JSONB column (text() query trả JSON string) → Python value."""
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except (ValueError, TypeError):
            return raw
    return raw


def _resolve_key(stored: dict[str, Any], db_key: str, env_value: str) -> str:
    """Plaintext API key: DB encrypted ưu tiên, fallback env config.

    DB rỗng + env còn placeholder → "" (coi như chưa cấu hình).
    """
    enc = stored.get(db_key)
    if enc:
        try:
            return decrypt_secret(str(enc))
        except Exception:  # noqa: BLE001 — decrypt fail → coi như chưa có
            logger.warning("rag_config: decrypt %s thất bại", db_key)
    if env_value and env_value not in _PLACEHOLDERS:
        return env_value
    return ""


async def _read_settings(db: AsyncSession) -> dict[str, Any]:
    """SELECT toàn bộ bảng settings → dict {key: parsed_value}."""
    rows = (await db.execute(text("SELECT key, value FROM settings"))).fetchall()
    return {row[0]: _parse_jsonb(row[1]) for row in rows}


async def _set(
    db: AsyncSession, key: str, value: str, updated_by: UUID | None
) -> None:
    """UPSERT 1 setting key (value lưu dạng JSONB scalar string)."""
    await db.execute(
        text(
            "INSERT INTO settings (key, value, updated_by, updated_at) "
            "VALUES (:key, CAST(:value AS JSONB), :by, NOW()) "
            "ON CONFLICT (key) DO UPDATE SET "
            "value = EXCLUDED.value, updated_by = EXCLUDED.updated_by, "
            "updated_at = NOW()"
        ),
        {
            "key": key,
            "value": json.dumps(value),
            "by": str(updated_by) if updated_by else None,
        },
    )


async def _delete(db: AsyncSession, key: str) -> None:
    """Xoá 1 setting key (clear API key)."""
    await db.execute(
        text("DELETE FROM settings WHERE key = :key"), {"key": key}
    )


def _apply_runtime(req: UpdateRagConfigRequest) -> None:
    """Hot-swap: mutate get_settings() singleton + os.environ ngay sau khi persist."""
    s = get_settings()
    if req.embedding_provider:
        s.rag_embedding_provider = req.embedding_provider
    if req.embedding_model:
        s.rag_embedding_model = req.embedding_model
    if req.llm_provider:
        s.rag_llm_provider = req.llm_provider
    # Hot-swap LLM model (ASK-04): `ask_service._resolve_llm_model()` đọc
    # `s.rag_llm_model` mỗi lần gọi. KHÔNG mutate field này thì admin đổi
    # `gemini_llm_model` qua /api/rag-config sẽ KHÔNG có hiệu lực — model cũ
    # `gpt-4o-mini` vẫn được gửi cho LiteLLM (chỉ prefix `gemini/` đổi).
    if req.gemini_llm_model:
        s.rag_llm_model = req.gemini_llm_model
    if req.clear_openai_key:
        os.environ.pop("OPENAI_API_KEY", None)
        s.openai_api_key = "sk-replace-me"
    if req.clear_gemini_key:
        os.environ.pop("GEMINI_API_KEY", None)
        s.gemini_api_key = "replace-me"
    if req.openai_api_key:
        os.environ["OPENAI_API_KEY"] = req.openai_api_key
        s.openai_api_key = req.openai_api_key
    if req.gemini_api_key:
        os.environ["GEMINI_API_KEY"] = req.gemini_api_key
        s.gemini_api_key = req.gemini_api_key


class RagConfigService:
    """CRUD rag-config qua bảng `settings` + hot-swap runtime (ASK-04)."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_config(self) -> dict[str, Any]:
        """GET /api/rag-config — config hiện tại (key MASKED, không leak plaintext)."""
        s = get_settings()
        stored = await _read_settings(self.db)
        openai_key = _resolve_key(stored, "OPENAI_API_KEY", s.openai_api_key)
        gemini_key = _resolve_key(stored, "GEMINI_API_KEY", s.gemini_api_key)
        return {
            "embedding_provider": stored.get(
                "RAG_EMBEDDING_PROVIDER", s.rag_embedding_provider
            ),
            "embedding_model": stored.get(
                "RAG_EMBEDDING_MODEL", s.rag_embedding_model
            ),
            "embedding_dim": s.rag_embedding_dim,
            "chunk_size": _coerce_int(
                stored.get("RAG_CHUNK_SIZE"), _DEFAULT_CHUNK_SIZE
            ),
            "chunk_overlap": _coerce_int(
                stored.get("RAG_CHUNK_OVERLAP"), _DEFAULT_CHUNK_OVERLAP
            ),
            "batch_size": _coerce_int(
                stored.get("RAG_BATCH_SIZE"), _DEFAULT_BATCH_SIZE
            ),
            "llm_provider": stored.get("LLM_PROVIDER", s.rag_llm_provider),
            "gemini_llm_model": stored.get(
                "LLM_GEMINI_MODEL", _DEFAULT_GEMINI_LLM_MODEL
            ),
            "openai_key_mask": mask_key(openai_key),
            "gemini_key_mask": mask_key(gemini_key),
            "openai_key_saved": bool(openai_key),
            "gemini_key_saved": bool(gemini_key),
        }

    async def _embedding_cost_preview(self) -> dict[str, Any]:
        """Cost preview re-embed toàn corpus khi swap embedding (D-07-03-B).

        Echo cho UI WARNING modal — KHÔNG cần chính xác tuyệt đối. Query
        `count(*)` bọc try/except → fallback n=0 nếu lỗi (T-07-03-04).
        `est_cost_usd` LUÔN render 2 chữ số trong `message` (format `:.2f`).
        """
        try:
            n = int(
                (
                    await self.db.execute(text("SELECT count(*) FROM chunks"))
                ).scalar_one()
            )
        except Exception as exc:  # noqa: BLE001 — best-effort, fallback n=0
            logger.warning("rag_config cost preview count(*) thất bại: %s", exc)
            n = 0
        cost = round(n * COST_PER_CHUNK_USD, 2)
        minutes = max(1, math.ceil(n / CHUNKS_PER_MINUTE))
        message = f"re-embed {n} chunks, est ${cost:.2f}, est {minutes} phút"
        return EmbeddingCostPreview(
            n_chunks=n,
            est_cost_usd=cost,
            est_minutes=minutes,
            message=message,
        ).model_dump()

    async def update_config(  # noqa: C901 — chuỗi if guard partial-update phẳng
        self, *, req: UpdateRagConfigRequest, updated_by: UUID
    ) -> dict[str, Any] | str:
        """PUT /api/rag-config — persist + hot-swap. Trả str = error message (→ 400)."""
        if (
            req.embedding_provider
            and req.embedding_provider not in _VALID_EMBEDDING_PROVIDERS
        ):
            return "embedding_provider không hợp lệ — chỉ chấp nhận: openai, gemini"
        if req.llm_provider and req.llm_provider not in _VALID_LLM_PROVIDERS:
            return "llm_provider không hợp lệ — chỉ chấp nhận: openai, gemini, auto"

        # R7 / ASK-04 — dimension guard + cost preview cho embedding swap.
        cost_preview: dict[str, Any] | None = None
        if req.embedding_model:
            new_dim = _embedding_dim_of(req.embedding_model)
            current_dim = get_settings().rag_embedding_dim  # 1536 pin
            if new_dim != current_dim:
                # Cross-dim swap → REFUSE 400 (R7). str = error → router map 400.
                return (
                    "dimension mismatch — defer cross-dim swap v4.0 "
                    f"(model yêu cầu dim {new_dim}, hệ thống pin dim {current_dim})"
                )
        # Within-dim swap: cho phép, tính cost preview WARNING khi đổi embedding.
        if req.embedding_provider or req.embedding_model:
            cost_preview = await self._embedding_cost_preview()

        if req.embedding_provider:
            await _set(
                self.db, "RAG_EMBEDDING_PROVIDER", req.embedding_provider, updated_by
            )
        if req.embedding_model:
            await _set(
                self.db, "RAG_EMBEDDING_MODEL", req.embedding_model, updated_by
            )
        if req.chunk_size is not None and req.chunk_size > 0:
            await _set(self.db, "RAG_CHUNK_SIZE", str(req.chunk_size), updated_by)
        if req.chunk_overlap is not None and req.chunk_overlap >= 0:
            await _set(
                self.db, "RAG_CHUNK_OVERLAP", str(req.chunk_overlap), updated_by
            )
        if req.batch_size is not None and req.batch_size > 0:
            await _set(self.db, "RAG_BATCH_SIZE", str(req.batch_size), updated_by)
        if req.llm_provider:
            await _set(self.db, "LLM_PROVIDER", req.llm_provider, updated_by)
        if req.gemini_llm_model:
            await _set(
                self.db, "LLM_GEMINI_MODEL", req.gemini_llm_model, updated_by
            )

        # Clear trước khi save (admin clear + set lại trong cùng request).
        if req.clear_gemini_key:
            await _delete(self.db, "GEMINI_API_KEY")
        if req.clear_openai_key:
            await _delete(self.db, "OPENAI_API_KEY")
        if req.gemini_api_key:
            await _set(
                self.db,
                "GEMINI_API_KEY",
                encrypt_secret(req.gemini_api_key),
                updated_by,
            )
        if req.openai_api_key:
            await _set(
                self.db,
                "OPENAI_API_KEY",
                encrypt_secret(req.openai_api_key),
                updated_by,
            )

        _apply_runtime(req)
        logger.info("rag_config_updated by=%s", updated_by)

        s = get_settings()
        result: dict[str, Any] = {
            "message": "config updated",
            "active_embedding": s.rag_embedding_provider,
            "active_llm_provider": s.rag_llm_provider,
        }
        if cost_preview is not None:
            # Within-dim embedding swap → WARNING + cost preview (R7).
            result["warning"] = (
                "Đổi embedding provider có thể giảm chất lượng vector hiện tại. "
                "Vector cũ KHÔNG tự động re-embed — chỉ document upload mới dùng "
                "provider mới. Cân nhắc re-embed thủ công."
            )
            result["cost_preview"] = cost_preview
        return result

    async def get_provider_key(self, provider: str) -> str:
        """Plaintext API key của provider (gemini|openai) — dùng cho /test."""
        stored = await _read_settings(self.db)
        s = get_settings()
        if provider == "gemini":
            return _resolve_key(stored, "GEMINI_API_KEY", s.gemini_api_key)
        return _resolve_key(stored, "OPENAI_API_KEY", s.openai_api_key)

    async def collections(self) -> dict[str, Any]:
        """GET /api/rag-config/collections — inventory vector store theo hub.

        M2 pin dim 1536 (R1) → `mismatch` luôn False, `dimension` = 1536 nếu hub
        đã có chunk, 0 nếu rỗng.
        """
        s = get_settings()
        out: dict[str, Any] = {
            "current_dimension": s.rag_embedding_dim,
            "current_provider": s.rag_embedding_provider,
            "current_model": s.rag_embedding_model,
            "collections": [],
        }
        try:
            rows = (
                await self.db.execute(
                    text(
                        "SELECT h.code, h.name, "
                        "COALESCE(d.cnt, 0) AS doc_count, "
                        "COALESCE(c.cnt, 0) AS chunk_count "
                        "FROM hubs h "
                        "LEFT JOIN (SELECT hub_id, COUNT(*) cnt FROM documents "
                        "GROUP BY hub_id) d ON d.hub_id = h.id "
                        "LEFT JOIN (SELECT hub_id, COUNT(*) cnt FROM chunks "
                        "GROUP BY hub_id) c ON c.hub_id = h.id "
                        "ORDER BY h.code"
                    )
                )
            ).fetchall()
        except Exception as exc:  # noqa: BLE001 — best-effort như Go cũ
            logger.warning("rag_config collections query thất bại: %s", exc)
            return out

        out["collections"] = [
            {
                "hub_code": code,
                "hub_name": name,
                "collection": f"medinet_{code}",
                "dimension": s.rag_embedding_dim if int(chunk_count) > 0 else 0,
                "doc_count": int(doc_count),
                "mismatch": False,
            }
            for code, name, doc_count, chunk_count in rows
        ]
        return out


async def load_persisted_into_runtime(pool: Any) -> None:
    """Startup: đọc settings DB qua asyncpg pool → apply env + singleton.

    Giữ giá trị admin lưu (provider, model, API key) qua restart. Best-effort —
    lỗi (DB chưa lên, decrypt fail) chỉ log, KHÔNG crash lifespan.
    """
    s = get_settings()
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT key, value FROM settings")
    except Exception as exc:  # noqa: BLE001
        logger.warning("rag_config startup load thất bại: %s", exc)
        return

    for row in rows:
        key = row["key"]
        val = _parse_jsonb(row["value"])
        if key == "RAG_EMBEDDING_PROVIDER":
            s.rag_embedding_provider = str(val)
        elif key == "RAG_EMBEDDING_MODEL":
            s.rag_embedding_model = str(val)
        elif key == "LLM_PROVIDER":
            s.rag_llm_provider = str(val)
        elif key == "LLM_GEMINI_MODEL":
            # Hot-swap LLM model giữ qua restart (ASK-04) — `_resolve_llm_model`
            # đọc `s.rag_llm_model`.
            s.rag_llm_model = str(val)
        elif key in _SECRET_KEYS:
            try:
                plain = decrypt_secret(str(val))
            except Exception:  # noqa: BLE001
                logger.warning("rag_config startup: decrypt %s thất bại", key)
                continue
            os.environ[key] = plain
            if key == "OPENAI_API_KEY":
                s.openai_api_key = plain
            else:
                s.gemini_api_key = plain
    logger.info("rag_config_persisted_loaded: %d key", len(rows))
