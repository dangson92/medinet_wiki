"""Pytest fixtures cho docling-pipeline service.

Cung cấp:
- TestClient duy nhất scope=session (lifespan B5 chạy 1 lần warm models).
- 5 fixture file binary (sample_pdf, sample_docx, sample_scanned_vi, sample_with_table, sample_with_figure).
- Override env vars cần thiết cho test (DOCLING_MAX_FILE_MB nhỏ + log_format=json).
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session", autouse=True)
def _set_env() -> None:
    """Override env trước khi import settings — keep file size limit nhỏ + JSON log cho W4."""
    os.environ.setdefault("DOCLING_MAX_FILE_MB", "5")
    os.environ.setdefault("DOCLING_REQUEST_TIMEOUT_SEC", "120")
    os.environ.setdefault("DOCLING_LOG_FORMAT", "json")


@pytest.fixture(scope="session")
def client() -> Iterator["object"]:
    """TestClient duy nhất cho toàn session — lifespan warm models 1 lần."""
    from fastapi.testclient import TestClient

    from docling_pipeline.main import create_app

    app = create_app()
    with TestClient(app) as c:
        yield c


@pytest.fixture
def sample_pdf() -> bytes:
    return (FIXTURES_DIR / "sample_small.pdf").read_bytes()


@pytest.fixture
def sample_docx() -> bytes:
    return (FIXTURES_DIR / "sample_small.docx").read_bytes()


@pytest.fixture
def sample_scanned_vi() -> bytes:
    return (FIXTURES_DIR / "sample_scanned_vi.pdf").read_bytes()


@pytest.fixture
def sample_with_table() -> bytes:
    return (FIXTURES_DIR / "sample_with_table.pdf").read_bytes()


@pytest.fixture
def sample_with_figure() -> bytes:
    return (FIXTURES_DIR / "sample_with_figure.pdf").read_bytes()
