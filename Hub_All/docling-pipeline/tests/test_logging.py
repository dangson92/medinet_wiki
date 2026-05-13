"""W4 — Test X-Request-Id propagate vào structlog JSON stdout (DSVC-04 evidence end-to-end)."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient


@pytest.mark.slow
def test_request_id_propagated_to_log(
    client: TestClient,
    sample_pdf: bytes,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """RequestIdMiddleware bind_contextvars(request_id=rid) → structlog JSON line phải chứa rid."""
    rid = f"test-w4-{uuid.uuid4()}"
    files = {"file": ("sample.pdf", sample_pdf, "application/pdf")}
    data = {"hub_code": "test", "doc_type": "test", "request_id": ""}
    headers = {"X-Request-Id": rid}

    resp = client.post("/v1/process", files=files, data=data, headers=headers)
    assert resp.status_code == 200

    # structlog PrintLoggerFactory ghi ra sys.stdout (configure_logging Plan 06).
    # Phải có ít nhất 1 line JSON chứa rid (event "process_done" + middleware bind_contextvars).
    captured = capsys.readouterr()
    assert rid in captured.out, (
        f"request_id {rid!r} không xuất hiện trong stdout structlog. "
        f"Captured (first 500 chars): {captured.out[:500]!r}"
    )
