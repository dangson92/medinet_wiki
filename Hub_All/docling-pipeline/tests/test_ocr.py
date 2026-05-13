"""Test OCR Tesseract vie+eng cho scanned PDF tiếng Việt (DSVC-03 + EXTRACT-02).

Đảo ngược thất bại Phase 1: scanned PDF tiếng Việt phải extract được text VN qua OCR.
Marker `slow` vì cần Tesseract install + Docling models warm.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

EXPECTED_VI_TOKENS = [
    "Đỗ Minh Đường",
    "Định vị",
    "Trung tâm",
    "y học",
    "định vị",
    "đỗ minh",
]


@pytest.mark.slow
def test_ocr_scanned_vi_extracts_vietnamese(
    client: TestClient, sample_scanned_vi: bytes
) -> None:
    """Scanned PDF tiếng Việt → OCR extract được ≥ 1 token tiếng Việt nhận diện."""
    files = {"file": ("scanned.pdf", sample_scanned_vi, "application/pdf")}
    data = {"hub_code": "test", "doc_type": "scanned", "request_id": ""}
    resp = client.post("/v1/process", files=files, data=data)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["doc_meta"]["ocr_used"] is True
    assert len(body["chunks"]) > 0

    full_text = " ".join(ch["text"] for ch in body["chunks"]).lower()
    assert any(tok.lower() in full_text for tok in EXPECTED_VI_TOKENS), (
        "Không tìm thấy token tiếng Việt nào trong OCR output — Tesseract vie+eng "
        f"có thể chưa cài trong test env. Tokens checked: {EXPECTED_VI_TOKENS}. "
        f"Sample text: {full_text[:200]!r}"
    )
