"""Services package — Phase 4 INGEST-02 (extract / chunk / embed / file_store).

Plan 04-03 cocoindex flow wrap các function này thành cocoindex.op.function.
Plan 04-04 router /api/documents/upload import detect_scanned_pdf + FileStore.

Public API ổn định cho downstream Plan 04-03 / 04-04 / 04-05 / 04-06 import.
"""
from __future__ import annotations

from app.services.embedder import EMBEDDING_DIM, EmbedderError, embed_text
from app.services.file_extract import (
    ALLOWED_EXTENSIONS,
    UnsupportedFormatError,
    detect_scanned_pdf,
    extract_text,
)
from app.services.file_store import FileStore
from app.services.vn_chunker import ChunkDraft, chunk_vietnamese

__all__ = [
    "ALLOWED_EXTENSIONS",
    "ChunkDraft",
    "EMBEDDING_DIM",
    "EmbedderError",
    "FileStore",
    "UnsupportedFormatError",
    "chunk_vietnamese",
    "detect_scanned_pdf",
    "embed_text",
    "extract_text",
]
