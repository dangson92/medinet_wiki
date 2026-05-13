"""B4 — Test 413 payload-too-large + 504 timeout (DSVC-06)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def _post_raw(client: TestClient, body: bytes, filename: str):
    files = {"file": (filename, body, "application/pdf")}
    data = {"hub_code": "test", "doc_type": "test", "request_id": ""}
    return client.post("/v1/process", files=files, data=data)


def test_413_payload_too_large(client: TestClient) -> None:
    """DOCLING_MAX_FILE_MB=5 trong conftest → upload 6MB phải trả 413."""
    big = b"x" * (6 * 1024 * 1024)
    resp = _post_raw(client, big, "huge.pdf")
    assert resp.status_code == 413
    body = resp.json()
    assert body["detail"]["error"] == "payload_too_large"
    assert body["detail"]["max_mb"] == 5


def test_504_when_timeout(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """B4 — Khi extract chậm hơn DOCLING_REQUEST_TIMEOUT_SEC → trả 504 Gateway Timeout.

    Monkeypatch DoclingExtractor.extract bằng hàm sleep dài;
    ép timeout = 1s qua patch get_settings cache.
    """
    from docling_pipeline.config import Settings, get_settings

    # Ép settings mới với timeout=1s (clear cache để force re-create)
    get_settings.cache_clear()
    monkeypatch.setenv("DOCLING_REQUEST_TIMEOUT_SEC", "1")

    # Slow extract — block 999s; asyncio.timeout(1) phải trigger TimeoutError
    def slow_extract(self, file_bytes, filename):  # noqa: ARG001
        import time

        time.sleep(999)
        return None

    from docling_pipeline.core.extractor import DoclingExtractor

    monkeypatch.setattr(DoclingExtractor, "extract", slow_extract)

    files = {"file": ("x.pdf", b"%PDF-1.4\n%dummy", "application/pdf")}
    data = {"hub_code": "test", "doc_type": "test", "request_id": ""}

    resp = client.post("/v1/process", files=files, data=data)
    assert resp.status_code == 504, f"expected 504, got {resp.status_code}: {resp.text}"
    body = resp.json()
    assert body["detail"]["error"] == "request_timeout"
    assert body["detail"]["timeout_sec"] == 1

    # Cleanup cache để các test sau dùng lại settings gốc
    get_settings.cache_clear()
    _ = Settings  # silence unused import (giữ để dev IDE biết import path)
