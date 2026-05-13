"""Test POST /v1/process với PDF + DOCX nhỏ + request_id propagate (DSVC-01, DSVC-02, DSVC-04)."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient


def _post_process(
    client: TestClient,
    file_bytes: bytes,
    filename: str,
    *,
    hub_code: str = "test_hub",
    doc_type: str = "test",
    request_id: str = "",
    headers: dict[str, str] | None = None,
):
    files = {"file": (filename, file_bytes, "application/octet-stream")}
    data = {
        "hub_code": hub_code,
        "doc_type": doc_type,
        "request_id": request_id,
    }
    return client.post("/v1/process", files=files, data=data, headers=headers or {})


@pytest.mark.slow
def test_process_pdf_returns_schema(client: TestClient, sample_pdf: bytes) -> None:
    """DSVC-02 — PDF nhỏ trả schema đầy đủ 10 field/chunk."""
    resp = _post_process(client, sample_pdf, "sample.pdf")
    assert resp.status_code == 200, resp.text
    body = resp.json()

    # Schema DSVC-02 top-level
    assert "request_id" in body
    assert "doc_meta" in body
    assert "chunks" in body

    # doc_meta fields
    meta = body["doc_meta"]
    assert meta["filename"] == "sample.pdf"
    assert meta["file_type"] == "pdf"
    assert isinstance(meta["page_count"], int)
    assert isinstance(meta["ocr_used"], bool)

    # chunks: ≥ 1 với đầy đủ field
    assert len(body["chunks"]) > 0
    ch0 = body["chunks"][0]
    for field in (
        "chunk_index",
        "text",
        "headers",
        "caption",
        "page_start",
        "page_end",
        "is_table",
        "table_html",
        "bbox",
        "token_count",
    ):
        assert field in ch0, f"missing field {field}"
    assert isinstance(ch0["chunk_index"], int)
    assert isinstance(ch0["headers"], list)
    assert isinstance(ch0["is_table"], bool)
    assert isinstance(ch0["token_count"], int)
    assert ch0["token_count"] > 0


@pytest.mark.slow
def test_process_docx_returns_schema(client: TestClient, sample_docx: bytes) -> None:
    """DSVC-02 — DOCX nhỏ extract OK, file_type=docx."""
    resp = _post_process(client, sample_docx, "sample.docx")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["doc_meta"]["file_type"] == "docx"
    assert len(body["chunks"]) > 0


@pytest.mark.slow
def test_request_id_propagate(client: TestClient, sample_pdf: bytes) -> None:
    """DSVC-04 — X-Request-Id từ Go backend phải echo trong body + response header."""
    rid = str(uuid.uuid4())
    resp = _post_process(client, sample_pdf, "sample.pdf", headers={"X-Request-Id": rid})
    assert resp.status_code == 200
    assert resp.json()["request_id"] == rid
    assert resp.headers.get("X-Request-Id") == rid


def test_process_unsupported_extension(client: TestClient) -> None:
    """Extension không nằm whitelist → 415 Unsupported Media Type."""
    resp = _post_process(client, b"hello", "evil.exe")
    assert resp.status_code == 415
