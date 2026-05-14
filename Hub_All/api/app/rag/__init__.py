"""RAG package — cocoindex flow + ingest pipeline (Phase 4).

Public API:
    from app.rag import setup_cocoindex

Plan 04-01 ships scaffolding (setup helper).
Plan 04-02 thêm flow.py — @cocoindex.flow_def medinet_wiki_ingest.
Plan 04-03 thêm services (file_extract, vn_chunker, embedder).
"""
from __future__ import annotations

from app.rag.setup import setup_cocoindex

__all__ = ["setup_cocoindex"]
