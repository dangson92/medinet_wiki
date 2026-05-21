"""Unit test cocoindex 1.0.3 flow medinet_wiki_ingest — Plan 04-03 REVISION 2.

KHÔNG cần Postgres runtime — chỉ verify cocoindex 1.0.3 actual API surface:
- coco.App instance đăng ký với name="medinet_wiki_ingest".
- ChunkRow dataclass schema đầy đủ 10 fields match Migration 0001.
- stable_chunk_id deterministic (D-1/D-2 citation preservation).
- Source code grep KHÔNG có cocoindex 0.x deprecated patterns (revision 2 scrub).
- Setup helpers expose từ app.rag.setup (setup_cocoindex/get_cocoindex_app/stop_cocoindex).

Integration test E2E (upload → cocoindex_app.update_blocking → chunks pgvector)
thuộc Plan 04-06.
"""
from __future__ import annotations

import asyncio as _asyncio  # Plan 04-07 gap closure regression tests
import os
import uuid


def test_cocoindex_app_registered() -> None:
    """Import app.rag.flow KHÔNG raise — coco.App instance đăng ký vào registry."""
    import app.rag.flow as flow_module

    assert hasattr(flow_module, "cocoindex_app")
    assert hasattr(flow_module, "ChunkRow")
    assert hasattr(flow_module, "stable_chunk_id")
    assert hasattr(flow_module, "PG_POOL_KEY")
    assert hasattr(flow_module, "CHUNK_ID_NAMESPACE")


def test_cocoindex_app_name_snake_case() -> None:
    """R5 + P2: cocoindex_app name snake_case `medinet_<hub>_ingest`.

    v3.0 Plan 01-04 TOPO-03 — App name resolve per-hub qua Settings.hub_name.
    Default HUB_NAME=central (conftest `_env` autouse) → name='medinet_central_ingest'.
    M2 hard-code `medinet_wiki_ingest` đã bỏ — Plan 01-04 (BLOCKER 4 fix).
    """
    from app.rag.flow import cocoindex_app

    # Cocoindex 1.0.3 App instance expose .name hoặc ._name attribute.
    name = getattr(cocoindex_app, "name", None) or getattr(
        cocoindex_app, "_name", None
    )
    # Default HUB_NAME=central (tests/conftest.py `_env` autouse stub) →
    # cocoindex_app.name = 'medinet_central_ingest' (v3.0 Plan 01-04).
    assert name == "medinet_central_ingest", f"App name sai: {name!r}"


def test_cocoindex_app_is_app_class() -> None:
    """cocoindex_app phải là coco.App instance (cocoindex 1.0.3 actual API)."""
    import cocoindex as coco

    from app.rag.flow import cocoindex_app

    assert isinstance(cocoindex_app, coco.App), (
        f"cocoindex_app phải là coco.App, got {type(cocoindex_app).__name__}"
    )


def test_chunk_row_dataclass_schema() -> None:
    """ChunkRow dataclass có đủ 10 field match Migration 0001 chunks (BLOCKER #2)."""
    from app.rag.flow import ChunkRow

    assert hasattr(ChunkRow, "__dataclass_fields__"), "ChunkRow phải là @dataclass"
    fields = set(ChunkRow.__dataclass_fields__.keys())
    required = {
        "id",
        "document_id",
        "hub_id",
        "content",
        "content_hash",
        "heading_path",
        "page_start",
        "page_end",
        "vector",
        "metadata",
    }
    assert required.issubset(fields), (
        f"ChunkRow thiếu fields: missing={required - fields}, got={fields}"
    )


def test_stable_chunk_id_deterministic() -> None:
    """D-1/D-2: stable_chunk_id same input → same UUID (citation preservation)."""
    from app.rag.flow import stable_chunk_id

    doc_id = uuid.UUID("11111111-1111-1111-1111-111111111111")
    a = stable_chunk_id(doc_id, 0)
    b = stable_chunk_id(doc_id, 0)
    c = stable_chunk_id(doc_id, 1)
    d = stable_chunk_id(uuid.UUID("22222222-2222-2222-2222-222222222222"), 0)

    assert a == b, f"Same input phải same UUID: {a} vs {b}"
    assert a != c, f"Khác chunk_index phải khác UUID: {a} vs {c}"
    assert a != d, f"Khác doc_id phải khác UUID: {a} vs {d}"
    assert isinstance(a, uuid.UUID), f"Phải return uuid.UUID, got {type(a)}"


def test_flow_imports_services() -> None:
    """Flow phải import 3 service module Plan 04-02 (extract / chunk / embed) — E2 + Q4."""
    import app.rag.flow as flow_module

    with open(flow_module.__file__, encoding="utf-8") as f:
        source = f.read()
    assert "from app.services.file_extract import extract_text" in source
    assert "from app.services.vn_chunker import chunk_vietnamese" in source
    assert "from app.services.embedder import" in source
    assert "aembedding_one" in source


def test_flow_uses_cocoindex_1_0_3_api() -> None:
    """Cocoindex 1.0.3 actual API patterns — REVISION 2 verify."""
    import app.rag.flow as flow_module

    with open(flow_module.__file__, encoding="utf-8") as f:
        source = f.read()
    assert "import cocoindex as coco" in source, "Phải dùng `import cocoindex as coco` alias"
    assert "from cocoindex.connectors import postgres as pg" in source
    assert "coco.App(coco.AppConfig(name=" in source, (
        "Phải dùng coco.App + AppConfig pattern"
    )
    assert "@coco.fn" in source, "Phải dùng @coco.fn decorator"
    assert "pg.PgTableSource" in source, "Source phải là pg.PgTableSource"
    assert "pg.mount_table_target" in source, "Target phải dùng mount_table_target"
    assert "ManagedBy.USER" in source, "Decision B1 — Alembic owns DDL"
    assert "coco.mount_each" in source, "Per-row processor qua mount_each"


def test_flow_no_deprecated_cocoindex_0x_api() -> None:
    """REVISION 2 scrub — KHÔNG có cocoindex 0.x API deprecated."""
    import app.rag.flow as flow_module

    with open(flow_module.__file__, encoding="utf-8") as f:
        source = f.read()
    # Cocoindex 0.x deprecated symbols — KHÔNG được xuất hiện.
    forbidden = [
        "@cocoindex.flow_def",
        "cocoindex.sources.Postgres",
        "cocoindex.targets.Postgres",
        "PostgresNotification",
        "FlowLiveUpdater",
        "VectorIndexDef",
        "VectorSimilarityMetric",
        "@cocoindex.op.function",
        "cocoindex.FlowBuilder",
        "cocoindex.DataScope",
        "@cocoindex.main_fn",
        "documents_notify",  # KHÔNG có notification cocoindex 1.0.3
        'ordinal_column="updated_at"',
    ]
    violations = [pat for pat in forbidden if pat in source]
    assert not violations, (
        f"REVISION 2 violated — flow.py vẫn chứa cocoindex 0.x deprecated API: {violations}"
    )


def test_flow_no_declare_vector_index_b1() -> None:
    """Decision B1 — Alembic owns ix_chunks_vector_hnsw, cocoindex KHÔNG declare."""
    import app.rag.flow as flow_module

    with open(flow_module.__file__, encoding="utf-8") as f:
        source = f.read()
    # Acceptance: KHÔNG có literal `declare_vector_index` substring (cả call lẫn doc).
    # Comments dùng `declare-vector-index` (hyphen) để không match.
    assert "declare_vector_index" not in source, (
        "Decision B1 violated — flow.py có chuỗi declare_vector_index. Alembic "
        "Migration 0001 đã có ix_chunks_vector_hnsw — cocoindex KHÔNG declare để "
        "tránh duplicate."
    )


def test_chunk_row_wires_required_columns() -> None:
    """BLOCKER #2 — ChunkRow dataclass có hub_id/content_hash NOT NULL match schema."""
    import app.rag.flow as flow_module

    with open(flow_module.__file__, encoding="utf-8") as f:
        source = f.read()
    # Required columns match Migration 0001 chunks NOT NULL constraints.
    assert "hub_id: uuid.UUID" in source, (
        "hub_id NOT NULL FK CASCADE — phải khai dataclass"
    )
    assert "document_id: uuid.UUID" in source, (
        "document_id NOT NULL FK CASCADE — phải khai"
    )
    assert "content_hash: bytes" in source, (
        "content_hash NOT NULL BYTEA — phải khai"
    )
    assert "content: str" in source, "content NOT NULL TEXT — phải khai"


def test_setup_helpers_importable() -> None:
    """Plan 04-03 REVISION 2 setup helpers expose từ app.rag.setup."""
    from app.rag.setup import (
        get_cocoindex_app,
        setup_cocoindex,
        stop_cocoindex,
    )

    assert callable(setup_cocoindex)
    assert callable(get_cocoindex_app)
    assert callable(stop_cocoindex)


def test_settings_has_cocoindex_lmdb_path_q5() -> None:
    """Q5: Settings có field cocoindex_lmdb_path."""
    # Defensive set env vars cho test runtime (test môi trường có thể KHÔNG load .env).
    os.environ.setdefault(
        "DATABASE_URL", "postgresql+asyncpg://x:y@localhost:5432/z"
    )
    os.environ.setdefault(
        "COCOINDEX_DATABASE_URL", "postgresql://x:y@localhost:5432/cc"
    )
    os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

    from app.config import get_settings

    settings = get_settings()
    assert hasattr(settings, "cocoindex_lmdb_path"), (
        "Q5 violated — Settings thiếu field cocoindex_lmdb_path"
    )
    # Path object hoặc str Path-castable.
    assert settings.cocoindex_lmdb_path is not None


# ===== Plan 04-07 gap closure regression tests (VectorSchemaProvider fix) =====


def test_chunk_row_vector_schema_build_no_raise() -> None:
    """Plan 04-07 gap closure regression — ChunkRow.vector phải satisfy VectorSchemaProvider.

    BEFORE fix: `await pg.TableSchema.from_class(ChunkRow, primary_key=['id'])` raise
    `ValueError: VectorSpecProvider is required for NumPy ndarray type` vì
    `Annotated[NDArray, EMBEDDER]` — EMBEDDER là @coco.fn callable KHÔNG implement
    VectorSchemaProvider Protocol.

    AFTER fix: dùng cocoindex.resources.schema.VectorSchema(dtype=np.dtype(np.float32),
    size=1536) làm provider — itself implements VectorSchemaProvider (frozen msgspec.Struct
    với __coco_vector_schema__ method). Schema build PASS exit 0.

    KHÔNG cần Postgres pool — chỉ test schema build (sync compute từ annotation).
    """
    from cocoindex.connectors import postgres as pg

    from app.rag.flow import ChunkRow

    # Build schema từ dataclass — async classmethod, run trong sync test qua asyncio.run.
    schema = _asyncio.run(pg.TableSchema.from_class(ChunkRow, primary_key=["id"]))

    # Verify vector column resolved thành pgvector type "vector(1536)".
    assert "vector" in schema.columns, "ChunkRow.vector phải thành column"
    vector_col = schema.columns["vector"]
    assert vector_col.type == "vector(1536)", (
        f"Vector dim mismatch: {vector_col.type} (expect 'vector(1536)' R1 pin)"
    )


def test_chunk_row_vector_uses_vector_schema_provider() -> None:
    """Plan 04-07 gap closure — VectorSchema constant phải implement VectorSchemaProvider."""
    import numpy as np
    from cocoindex.resources import schema as _coco_schema

    from app.rag import flow as flow_module

    # _VECTOR_SCHEMA module-level constant — must exist sau Plan 04-07.
    assert hasattr(flow_module, "_VECTOR_SCHEMA"), (
        "Plan 04-07 phải define _VECTOR_SCHEMA module-level constant"
    )
    vs = flow_module._VECTOR_SCHEMA
    assert isinstance(vs, _coco_schema.VectorSchema), (
        f"_VECTOR_SCHEMA phải là VectorSchema instance, got {type(vs).__name__}"
    )
    assert isinstance(vs, _coco_schema.VectorSchemaProvider), (
        "_VECTOR_SCHEMA phải satisfy VectorSchemaProvider Protocol (runtime_checkable)"
    )
    assert vs.size == 1536, f"Plan 04-02 R1 pin dim=1536, got {vs.size}"
    assert vs.dtype == np.dtype(np.float32), (
        f"R1 pin dtype float32, got {vs.dtype}"
    )


def test_flow_no_embedder_constant_for_vector_annotation() -> None:
    """Plan 04-07 gap closure — KHÔNG còn `EMBEDDER` annotation dùng cho vector field.

    BEFORE: `vector: Annotated[NDArray[np.float32], EMBEDDER]` (WRONG — EMBEDDER là
    @coco.fn callable).
    AFTER: `vector: Annotated[NDArray[np.float32], _VECTOR_SCHEMA]` (CORRECT —
    VectorSchema implements VectorSchemaProvider Protocol).
    """
    import app.rag.flow as flow_module

    with open(flow_module.__file__, encoding="utf-8") as f:
        source = f.read()
    assert "Annotated[NDArray[np.float32], EMBEDDER]" not in source, (
        "Plan 04-07 violated — flow.py vẫn dùng EMBEDDER (@coco.fn) làm vector provider"
    )
    assert "Annotated[NDArray[np.float32], _VECTOR_SCHEMA]" in source, (
        "Plan 04-07 phải dùng _VECTOR_SCHEMA (VectorSchema) làm vector provider"
    )
