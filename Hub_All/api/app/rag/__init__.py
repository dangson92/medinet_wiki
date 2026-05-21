"""RAG package — cocoindex 1.0.3 flow + ingest pipeline (Phase 4).

Public API:
    from app.rag import setup_cocoindex

Plan 04-01 ships scaffolding (setup helper + alembic migration 0002 watchdog index).
Plan 04-02 ships services (file_extract, vn_chunker, embedder, file_store).
Plan 04-03 ships flow.py — cocoindex 1.0.3 `coco.App(coco.AppConfig(name="medinet_<hub>_ingest"), main_fn)`
    pattern với mount_table_target + PgTableSource + ChunkRow dataclass schema.
    KHÔNG dùng deprecated `flow_def` decorator (cocoindex 0.x API — không tồn tại trong 1.0.3).
Plan 04-07 gap closure: ChunkRow.vector dùng VectorSchema (cocoindex.resources.schema)
    làm VectorSchemaProvider — fix architectural blocker SC2/SC5 ROADMAP.
Plan 01-04 TOPO-03 (v3.0): App name resolve per-hub `medinet_<hub>_ingest` qua
    Settings.hub_name (4 hub: central/yte/duoc/hcns); M2 hard-code 'medinet_wiki_ingest'
    đã bỏ — BLOCKER 4 fix accept state reset cho v3.0-a (re-ingest documents
    table idempotent via content_hash; Phase 7 migrate formally qua pg_dump).
"""
from __future__ import annotations

from app.rag.setup import setup_cocoindex

__all__ = ["setup_cocoindex"]
