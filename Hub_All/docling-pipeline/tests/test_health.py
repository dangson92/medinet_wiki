"""Test /healthz + /readyz endpoints (DSVC-04 + B5 lifespan)."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_healthz_returns_ok(client: TestClient) -> None:
    """Liveness — luôn trả 200 nếu process còn sống."""
    resp = client.get("/healthz")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] in {"ok", "healthy"}


def test_readyz_returns_ready_or_not_ready(client: TestClient) -> None:
    """B5: 200 ready (lib OK) hoặc 503 not_ready (ImportError docling)."""
    resp = client.get("/readyz")
    assert resp.status_code in (200, 503)
    body = resp.json()
    assert body["status"] in {"ready", "not_ready"}
    if resp.status_code == 503:
        # Khi not_ready phải kèm reason để ops debug
        assert "reason" in body
