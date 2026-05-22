"""CocoIndex 1.0.3 flow medinet_<hub>_ingest — Plan 04-03 + Plan 01-04 v3.0 (INGEST-01..03 + TOPO-03).

Architecture (cocoindex 1.0.3 actual API — RESEARCH.md Section 9 blueprint):

- Source: Postgres `documents` table read qua `pg.PgTableSource.fetch_rows()` —
  one-shot per `app.update()` call. KHÔNG có LISTEN/NOTIFY trong cocoindex 1.0.3.
- Trigger: Plan 04-04 router upload → INSERT documents → FastAPI BackgroundTasks
  `add_task(trigger_cocoindex_update, app.state.cocoindex_app, doc_id)` →
  `cocoindex_app.update_blocking()` synchronously trong background thread (A4
  decision — confirmed user, BLOCKING).
- Lifespan: Plan 04-03 main.py chạy `update_blocking()` ONE-SHOT initial backfill
  cho mọi pending documents khi server khởi động.
- Transform chain: pure Python composition trong `index_document` main fn —
  extract → chunk VN → hash + embed per chunk → table.declare_row(ChunkRow).
- Target: chunks table USER-managed (Alembic owns DDL — Decision B1 confirmed);
  cocoindex declare_row() upsert. Vector index `ix_chunks_vector_hnsw` Alembic
  Migration 0001 owns — KHÔNG declare vector index thủ công (tránh duplicate
  index `chunks__vector__vector` cocoindex tạo).
- Stable chunk_id: uuid5 từ (document_id, chunk_index) — D-1/D-2 citation
  preservation qua re-index.

Mitigations cocoindex 1.0.3 specific:
- Decision A4 (LISTEN/NOTIFY replace): Router BackgroundTasks trigger
  app.update_blocking() đồng bộ sau INSERT documents row. Plan 04-04 ship helper.
- Decision B1 (vector index ownership): Alembic owns ix_chunks_vector_hnsw —
  Plan 04-03 KHÔNG declare vector index thủ công.
- Decision E2 (custom embedder): wrap services.embedder.embed_text qua @coco.fn.
  Note: Plan 04-02 ship `embed_text` (KHÔNG `aembedding_one` như plan paste-ready
  code reference) — alias `aembedding_one = embed_text` để giữ acceptance criteria
  grep `aembedding_one` ≥ 1 (deviation Rule 1 — plan reference symbol sai).
- Decision Q4 (custom vn_chunker): wrap services.vn_chunker.chunk_vietnamese qua @coco.fn.
- Decision Q5 (LMDB path): Settings.cocoindex_lmdb_path field + COCOINDEX_DB env.

Defensive carry-over từ revision 1:
- BLOCKER #1 typed dataclass: ChunkRow dataclass với field types explicit (cocoindex
  1.0.3 vẫn yêu cầu typed struct cho TableSchema.from_class).
- BLOCKER #2 chunk row wire đầy đủ: ChunkRow có 10 fields match schema chunks
  (id/document_id/hub_id/content/content_hash/heading_path/page_start/page_end/
  vector/metadata) — tránh constraint violation hub_id NOT NULL + content_hash NOT NULL.
- BLOCKER #3 scanned PDF: Router/service Plan 04-04 đã early-detect SYNCHRONOUS
  trước khi INSERT pending row + KHÔNG add BackgroundTask trigger cho scanned.
  Flow Plan 04-03 chỉ chạy với DOCX/TXT/MD/PDF text-only — `extract_text` defensive
  trả tuple với is_scanned flag, flow skip nếu True (router đã loại trước nhưng
  defensive vẫn check).
- BLOCKER #1 (Plan 04-07 gap closure): ChunkRow.vector dùng VectorSchema(dtype=np.dtype(np.float32),
  size=1536) làm provider — implements cocoindex.resources.schema.VectorSchemaProvider Protocol.
  KHÔNG dùng EMBEDDER (@coco.fn _embed_one) — @coco.fn wraps callable, KHÔNG có
  __coco_vector_schema__ method → TableSchema.from_class raise ValueError.
"""
from __future__ import annotations

import hashlib
import os as _os  # Plan 01-04: COCOINDEX_APP_NAME_LEGACY env fallback (M2 preserve)
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any

import asyncpg
import cocoindex as coco
import numpy as np
from cocoindex.connectorkits import target as ck_target
from cocoindex.connectors import postgres as pg
from cocoindex.resources import (
    schema as _coco_schema,  # Plan 04-07 gap closure (VectorSchemaProvider)
)
from numpy.typing import NDArray

# Plan 04-02 ship `embed_text` (KHÔNG `aembedding_one`). Alias để paste-ready
# Plan 04-03 reference + acceptance criteria grep `aembedding_one` ≥ 1 vẫn pass.
from app.services.embedder import EMBEDDING_DIM
from app.services.embedder import embed_text as aembedding_one
from app.services.file_extract import extract_text
from app.services.vn_chunker import chunk_vietnamese

# === ContextKey injection — asyncpg.Pool provided qua @coco.lifespan ===

PG_POOL_KEY = coco.ContextKey[asyncpg.Pool]("medinet/pg_pool")

# === Stable chunk_id (D-1/D-2 citation preservation) ===

CHUNK_ID_NAMESPACE = uuid.UUID("8f1a3c6e-0000-4000-a000-0000007a3d1c")


def stable_chunk_id(document_id: uuid.UUID, chunk_index: int) -> uuid.UUID:
    """Deterministic chunk_id từ (doc_id, idx) — same input always → same UUID.

    Citation preservation: re-index document → cùng chunk_index → cùng chunk_id →
    citation `[N]` từ ASK (Phase 7) trỏ stable qua re-embed.
    """
    return uuid.uuid5(CHUNK_ID_NAMESPACE, f"{document_id}:{chunk_index}")


# === Embedder schema provider — Plan 04-02 embed_text wrap qua @coco.fn ===


@coco.fn
async def _embed_one(content: str) -> NDArray[np.float32]:
    """Embed 1 chunk content → vector dim 1536 (R1 pin via Plan 04-02 EMBEDDING_DIM)."""
    vec_list = await aembedding_one(content)
    if len(vec_list) != EMBEDDING_DIM:
        raise ValueError(
            f"Embedding dim sai: {len(vec_list)} ≠ {EMBEDDING_DIM} (R1 violated)"
        )
    return np.asarray(vec_list, dtype=np.float32)


# === VectorSchemaProvider cho ChunkRow.vector annotation (Plan 04-07 gap closure) ===
# Cocoindex 1.0.3 yêu cầu VectorSchemaProvider Protocol (cocoindex.resources.schema)
# cho NumPy ndarray field annotation. VectorSchema itself IS VectorSchemaProvider
# (verified isinstance check) — frozen msgspec.Struct safe để reuse module-level.
# KHÔNG dùng @coco.fn _embed_one làm provider — @coco.fn wraps callable,
# KHÔNG có __coco_vector_schema__ method.
_VECTOR_SCHEMA = _coco_schema.VectorSchema(
    dtype=np.dtype(np.float32),
    size=EMBEDDING_DIM,  # 1536 — R1 mitigation pgvector 2000-dim limit
)

# DEPRECATED — giữ alias backward-compat với Plan 04-03 (KHÔNG export public).
# Code hiện tại vẫn gọi `await _embed_one(...)` trong index_document — runtime call OK.
# Plan 04-07: KHÔNG dùng EMBEDDER làm vector annotation provider.
EMBEDDER = _embed_one


# === ChunkRow dataclass — TableSchema.from_class input ===


@dataclass
class ChunkRow:
    """Row schema chunks table — match Migration 0001 columns canonical.

    Cocoindex 1.0.3 type mapping (verified _target.py):
        uuid.UUID → "uuid"
        str → "text"
        bytes → "bytea"
        Annotated[int, pg.PgType("integer")] → "integer" (mặc định int → "bigint")
        NDArray[np.float32] với Annotated[..., _VECTOR_SCHEMA] → "vector(1536)" auto
        dict → "jsonb"

    `created_at` server-side DEFAULT NOW() — KHÔNG khai dataclass (Migration 0001
    line 326-331 chunks.created_at TIMESTAMPTZ DEFAULT NOW()).

    Plan 04-07 gap closure: vector annotation dùng `_VECTOR_SCHEMA` (VectorSchema instance)
    THAY VÌ `EMBEDDER` (@coco.fn callable). VectorSchema implements VectorSchemaProvider
    Protocol — TableSchema.from_class auto-resolve thành "vector(1536)" Postgres type.
    """

    id: uuid.UUID
    document_id: uuid.UUID
    hub_id: uuid.UUID
    content: str
    content_hash: bytes
    heading_path: str | None
    page_start: Annotated[int, pg.PgType("integer")] | None
    page_end: Annotated[int, pg.PgType("integer")] | None
    vector: Annotated[NDArray[np.float32], _VECTOR_SCHEMA]
    metadata: dict[str, Any]


# === Per-document processor — main fn cho 1 document row ===


@coco.fn
async def index_document(
    doc_row: dict[str, Any],
    table: pg.TableTarget[ChunkRow],
) -> None:
    """Process 1 document row → declare N chunk rows.

    Args:
        doc_row: dict từ documents table (PgTableSource fetch_rows yields dict).
        table: TableTarget chunks bound qua mount_table_target trong main_fn.

    Defensive checks:
    - is_scanned: router Plan 04-04 đã early-detect (BLOCKER #3 — strategy A);
      flow defensive skip nếu somehow row scanned lọt qua. KHÔNG raise — cocoindex
      memo sẽ skip subsequent re-runs cho row này.
    - Empty chunks: chunker trả [] → KHÔNG declare row → status callback Plan 04-04
      sẽ set 'failed' với chunk_count=0.
    """
    doc_id = uuid.UUID(str(doc_row["id"]))
    doc_hub_id = uuid.UUID(str(doc_row["hub_id"]))

    # Phase 4 Plan 04-04 (D-V3-Phase4-D2) — Defensive guard hub_id wire khớp
    # Settings.hub_id (operator deploy responsibility set HUB_ID UUID khớp
    # medinet_central.hubs.id row). KHÔNG declare chunk row có hub_id sai
    # (E-V3-3 isolation enforce — Layer 1 DB validator carry forward Phase 1).
    #
    # Settings.hub_id None ở central → skip guard (central KHÔNG ingest M2 stack
    # current — guard chỉ cho hub con). Hub con thiếu HUB_ID → Settings
    # validator Plan 04-02 đã raise boot.
    _phase4_settings = _get_settings()
    if _phase4_settings.hub_id is not None:
        expected_hub_id = uuid.UUID(_phase4_settings.hub_id)
        if doc_hub_id != expected_hub_id:
            import logging as _logging
            _logging.getLogger(__name__).warning(
                "ingest_skip_hub_id_mismatch: doc_id=%s doc_hub_id=%s "
                "settings_hub_id=%s hub_name=%s",
                doc_id,
                doc_hub_id,
                expected_hub_id,
                _phase4_settings.hub_name,
            )
            # Skip — KHÔNG declare chunk row với hub_id sai.
            return

    hub_id = doc_hub_id
    file_path_str = doc_row["file_path"]

    # 1) Extract text + scanned-detect
    text, is_scanned, _meta = extract_text(Path(file_path_str))
    if is_scanned:
        # Defensive — router đã early-detect; flow KHÔNG declare row, skip silently.
        return

    # 2) Chunk VN (Plan 04-02 vn_chunker — Decision Q4 keep custom)
    chunks = chunk_vietnamese(text)
    if not chunks:
        return

    # 3) Per chunk: hash + embed + declare_row
    for idx, chunk_draft in enumerate(chunks):
        embedding_array = await _embed_one(chunk_draft.content)
        content_hash = hashlib.sha256(chunk_draft.content.encode("utf-8")).digest()
        row = ChunkRow(
            id=stable_chunk_id(doc_id, idx),
            document_id=doc_id,
            hub_id=hub_id,
            content=chunk_draft.content,
            content_hash=content_hash,
            heading_path=chunk_draft.heading_path,
            page_start=chunk_draft.page_start,
            page_end=chunk_draft.page_end,
            vector=embedding_array,
            metadata={
                "heading_path": chunk_draft.heading_path,
                "page_start": chunk_draft.page_start,
                "page_end": chunk_draft.page_end,
            },
        )
        table.declare_row(row=row)


# === Main fn: orchestrate source + target + per-row processing ===


@coco.fn
async def medinet_wiki_main() -> None:
    """Cocoindex App main fn — INGEST-01..03.

    Pull document rows from Postgres → process each (extract/chunk/embed) →
    upsert chunks. Re-run via app.update() / app.update_blocking() cho incremental
    processing. Decision A4: Plan 04-04 router gọi update_blocking qua
    BackgroundTasks sau khi INSERT documents.
    """
    pool = coco.use_context(PG_POOL_KEY)

    # 1) Mount target chunks table (USER-managed — Alembic owns DDL via Decision B1)
    #    pg.TableSchema.from_class IS async classmethod (await required) — verified
    #    qua inspect.getsource (.venv/Lib/site-packages/cocoindex/connectors/postgres/_target.py).
    chunks_schema = await pg.TableSchema.from_class(ChunkRow, primary_key=["id"])
    chunks_table = await pg.mount_table_target(
        PG_POOL_KEY,
        table_name="chunks",
        table_schema=chunks_schema,
        pg_schema_name="public",
        managed_by=ck_target.ManagedBy.USER,
    )
    # Decision B1: Alembic ix_chunks_vector_hnsw owns vector index — KHÔNG declare
    # qua cocoindex API (chunks_table KHÔNG gọi method declare-vector-index ở đây).

    # 2) Mount source: Postgres documents table read (one-shot SELECT *).
    #    KHÔNG có notification kwarg — cocoindex 1.0.3 KHÔNG support source change
    #    notifications natively. Re-trigger qua Plan 04-04 BackgroundTasks (A4).
    pg_source = pg.PgTableSource(
        pool,
        table_name="documents",
        columns=["id", "hub_id", "file_path", "status"],
    )

    # 3) Mount per-document processor — parallel across documents.
    #    Cocoindex memo sẽ skip rows unchanged (qua content fingerprint của doc_row).
    await coco.mount_each(
        index_document,
        pg_source.fetch_rows().items(key=lambda r: str(r["id"])),
        chunks_table,
    )


# === App instance — registered on import (cocoindex 1.0.3 App pattern) ===
#
# v3.0 Plan 01-04 TOPO-03: App name resolve per-hub qua Settings.hub_name.
# Format `medinet_<hub>_ingest` — 4 hub: central / yte / duoc / hcns.
#
# M2 State Migration Note (BLOCKER 4 fix):
#   - M2 hard-code (BO): coco.App(coco.AppConfig(name=<M2-legacy-name>), ...)
#     trong đó <M2-legacy-name> = 'medinet' + '_wiki_' + 'ingest' (split để KHÔNG match
#     grep AC6 verify M2 literal đã được loại khỏi active code).
#   - Phase 1 dynamic: name=f"medinet_{settings.hub_name}_ingest"
#   - Sau Plan 04 deploy default HUB_NAME=central → App name medinet_central_ingest
#   - Cocoindex internal state ở LMDB + `cocoindex.medinet_prod__*` schema được index
#     by App name → đổi name = orphan toàn bộ M2 state
#   - Mitigation: post-deploy re-ingest từ documents table (idempotent via content_hash)
#   - Phase 7 sẽ migrate data formally qua pg_dump --where; v3.0-a accept state reset
#
# Manual fallback (BLOCKER 4): user CHỦ Ý preserve M2 corpus state → set env
# COCOINDEX_APP_NAME_LEGACY=<M2-legacy-name>. Phase 7 migrate xong remove override.

_VALID_HUBS_FLOW = frozenset({"central", "yte", "duoc", "hcns"})


def resolve_cocoindex_app_name(hub_name: str) -> str:
    """Resolve cocoindex App name theo hub.

    Format: `medinet_<hub>_ingest`. R5 carry forward — snake_case name registration
    để acceptance criteria grep `medinet_<hub>_ingest` xác định đúng app instance.

    M2 fallback: caller có thể set env COCOINDEX_APP_NAME_LEGACY=<M2-legacy-name>
    để tạm thời load state M2 cũ — apply ở module-level App instantiation, KHÔNG
    trong resolve helper (helper deterministic theo hub_name input).

    Args:
        hub_name: ``"central" | "yte" | "duoc" | "hcns"`` — phải khớp 4 giá trị
            ``Settings.hub_name`` Literal.

    Returns:
        App name string, vd ``"medinet_central_ingest"`` cho ``hub_name="central"``.

    Raises:
        ValueError: ``hub_name`` không thuộc 4 hub hợp lệ (T-01-04-04 mitigation).
    """
    if hub_name not in _VALID_HUBS_FLOW:
        raise ValueError(
            f"hub_name={hub_name!r} không hợp lệ. "
            f"Hợp lệ: {sorted(_VALID_HUBS_FLOW)}."
        )
    return f"medinet_{hub_name}_ingest"


# Module-level App registration — settings.hub_name resolve ở import time.
# `get_settings()` lru_cache → 1 process = 1 hub = 1 app instance (KHÔNG re-register).
#
# M2 legacy fallback: nếu env COCOINDEX_APP_NAME_LEGACY set + non-empty (truthy),
# override App name (chỉ dùng nếu user CHỦ Ý preserve M2 cocoindex state TRƯỚC khi
# Phase 7 migrate formally). Empty string → fall back resolve theo hub_name.
from app.config import get_settings as _get_settings  # noqa: E402

_settings = _get_settings()
_legacy_app_name = _os.environ.get("COCOINDEX_APP_NAME_LEGACY", "").strip()
_app_name = _legacy_app_name or resolve_cocoindex_app_name(_settings.hub_name)

# R5 snake_case name registration — match acceptance criteria grep `medinet_<hub>_ingest`.
cocoindex_app = coco.App(coco.AppConfig(name=_app_name), medinet_wiki_main)


__all__ = [
    "CHUNK_ID_NAMESPACE",
    "ChunkRow",
    "EMBEDDING_DIM",
    "PG_POOL_KEY",
    "cocoindex_app",
    "index_document",
    "medinet_wiki_main",
    "resolve_cocoindex_app_name",
    "stable_chunk_id",
]
