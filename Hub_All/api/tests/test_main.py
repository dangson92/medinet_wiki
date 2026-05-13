"""Smoke test cho FastAPI app factory + /healthz endpoint.

Phase 1 scope:
- `test_app_factory_returns_fastapi_instance`: verify factory tạo FastAPI
  instance với title đúng.
- `test_healthz_returns_200`: verify `/healthz` liveness luôn trả 200 với
  envelope `{success:true, data:{status:"ok"}}` — KHÔNG cần DB/Redis thực.

KHÔNG test `/readyz` Phase 1 (cần testcontainer Postgres + Redis — defer
sang Phase 2 khi schema migration sẵn).
"""
from __future__ import annotations

import pytest


def test_app_factory_returns_fastapi_instance() -> None:
    """Factory `create_app()` trả FastAPI instance với title chuẩn."""
    from fastapi import FastAPI

    from app.main import create_app

    app = create_app()
    assert isinstance(app, FastAPI)
    assert app.title == "Medinet Wiki API"


@pytest.mark.asyncio
async def test_healthz_returns_200() -> None:
    """GET /healthz luôn trả 200 với envelope `{success:true, data:{status:'ok'}}`.

    Dùng `ASGITransport` để gọi app trực tiếp KHÔNG cần network — vẫn skip
    lifespan vì httpx ASGITransport mặc định KHÔNG trigger lifespan.
    """
    from httpx import ASGITransport, AsyncClient

    from app.main import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/healthz")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"] == {"status": "ok"}
    assert body["error"] is None
    assert body["meta"] is None
