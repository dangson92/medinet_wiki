"""B3 — Test EXTRACT-03 (table HTML preserved) + EXTRACT-04 (figure caption marker)."""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient


def _post(client: TestClient, body: bytes, filename: str):
    files = {"file": (filename, body, "application/pdf")}
    data = {"hub_code": "test", "doc_type": "test", "request_id": ""}
    return client.post("/v1/process", files=files, data=data)


@pytest.mark.slow
def test_table_html_preserved(client: TestClient, sample_with_table: bytes) -> None:
    """EXTRACT-03 — chunk có is_table=True phải kèm table_html chứa <table>/<thead>/<tbody>."""
    resp = _post(client, sample_with_table, "table.pdf")
    assert resp.status_code == 200, resp.text
    body = resp.json()

    table_chunks = [c for c in body["chunks"] if c.get("is_table")]
    assert len(table_chunks) >= 1, (
        f"Không tìm thấy chunk nào có is_table=True; chunks={body['chunks']}"
    )

    tbl = table_chunks[0]
    html = (tbl.get("table_html") or "").lower()
    assert "<table" in html, f"table_html không chứa <table>: {html[:200]!r}"
    # thead + tbody — Docling 2.91 default emit cả 2 khi có header row
    assert "<thead" in html or "<tbody" in html, (
        f"table_html thiếu thead/tbody: {html[:200]!r}"
    )


@pytest.mark.slow
def test_figure_caption_marker(client: TestClient, sample_with_figure: bytes) -> None:
    """EXTRACT-04 — chunk text chứa pattern ![<caption>](#fig-N) cho figure có caption."""
    resp = _post(client, sample_with_figure, "figure.pdf")
    assert resp.status_code == 200, resp.text
    body = resp.json()

    full_text = "\n".join(c["text"] for c in body["chunks"])
    pattern = re.compile(r"!\[[^\]]*\]\(#fig-\d+\)")
    assert pattern.search(full_text), (
        f"Không tìm thấy figure caption marker '![...](#fig-N)' trong text. "
        f"Text sample: {full_text[:500]!r}"
    )
