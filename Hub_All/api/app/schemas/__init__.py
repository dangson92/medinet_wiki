"""Schemas package — Pydantic v2 request/response models cho REST API."""
from __future__ import annotations

from app.schemas.documents import (
    DOCUMENT_STATUS_VALUES,
    DocumentResponse,
    DocumentStatus,
    progress_for_status,
)
from app.schemas.search import (
    SearchFilters,
    SearchRequest,
    SearchResponse,
    SearchResultItem,
    SimilarMatch,
    SimilarRequest,
    SimilarResponse,
)

__all__ = [
    "DOCUMENT_STATUS_VALUES",
    "DocumentResponse",
    "DocumentStatus",
    "SearchFilters",
    "SearchRequest",
    "SearchResponse",
    "SearchResultItem",
    "SimilarMatch",
    "SimilarRequest",
    "SimilarResponse",
    "progress_for_status",
]
