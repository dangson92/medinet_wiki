"""Integration tests cho `/metrics` endpoint + middleware wiring + instrument hooks.

HARD-02 Plan 10-02 Task 2 — verify:
- Test 7: GET /metrics 200 + content-type Prometheus exposition + body chứa 5 metric name.
- Test 8: GET /healthz nhiều lần → /metrics có `requests_total{path="/healthz",status="200"} >= 3`.
- Test 9: POST /api/search body invalid (422) → /metrics có status="422" entry +
  ERRORS_TOTAL KHÔNG tăng (chỉ status>=500).
- Test 10: search_service.search → SEARCH_LATENCY histogram observe gọi 1 lần với hub_scope="single".
- Test 11: documents_service.trigger_cocoindex_update → INGEST_DURATION observe gọi 1 lần.

Note: app_with_auth fixture set COCOINDEX_SKIP_SETUP=1 → KHÔNG có cocoindex thật.
Test 11 mock cocoindex_app.update_blocking trực tiếp để verify wrap observe.
"""
from __future__ import annotations

import asyncio
import re
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from prometheus_client import REGISTRY
from prometheus_client.parser import text_string_to_metric_families


@pytest.mark.critical
@pytest.mark.integration
@pytest.mark.asyncio
async def test_metrics_endpoint_returns_prometheus_exposition_format(
    auth_client: httpx.AsyncClient,
) -> None:
    """Test 7: GET /metrics 200 + content-type + body có 5 metric name."""
    resp = await auth_client.get("/metrics")
    assert resp.status_code == 200

    ct = resp.headers["content-type"]
    # Prometheus content_type: `text/plain; version=<VERSION>; charset=utf-8`
    # Version field thay đổi giữa client versions (0.0.4 cũ vs 1.0.0+ openmetrics
    # text format trong prometheus-client>=0.21) — assert lỏng theo media_type +
    # presence của `version=`.
    assert ct.startswith("text/plain"), ct
    assert "version=" in ct, ct
    assert "charset=utf-8" in ct, ct

    body = resp.text
    # 5 metric name HARD-02 phải xuất hiện trong body (kể cả khi giá trị 0).
    assert "requests_total" in body
    assert "errors_total" in body
    assert "request_duration_seconds" in body
    assert "search_latency_seconds" in body
    assert "ingest_duration_seconds" in body

    # Body parse được bằng prometheus_client.parser (exposition format hợp lệ).
    families = list(text_string_to_metric_families(body))
    family_names = {f.name for f in families}
    # Counter `requests_total` parse ra name = "requests" (suffix _total bị strip
    # bởi parser — đối xứng với behavior Counter("requests_total") strip suffix).
    assert "requests" in family_names or "requests_total" in family_names


@pytest.mark.critical
@pytest.mark.integration
@pytest.mark.asyncio
async def test_metrics_counts_healthz_requests(
    auth_client: httpx.AsyncClient,
) -> None:
    """Test 8: GET /healthz nhiều lần → /metrics body có dòng requests_total cho /healthz."""
    before = (
        REGISTRY.get_sample_value(
            "requests_total",
            {"method": "GET", "path": "/healthz", "status": "200"},
        )
        or 0.0
    )

    for _ in range(3):
        r = await auth_client.get("/healthz")
        assert r.status_code == 200

    metrics_resp = await auth_client.get("/metrics")
    assert metrics_resp.status_code == 200
    body = metrics_resp.text

    # Regex match dòng `requests_total{method="GET",path="/healthz",status="200"} <N>`
    # — label order theo alphabet (method/path/status) chuẩn prometheus_client output.
    line_re = re.compile(
        r'^requests_total\{method="GET",path="/healthz",status="200"\} '
        r"(\d+(?:\.\d+)?)$",
        re.MULTILINE,
    )
    m = line_re.search(body)
    assert m is not None, f"Không thấy dòng requests_total /healthz trong body:\n{body[:500]}"
    after = float(m.group(1))
    assert (after - before) >= 3.0, (
        f"healthz count delta {after} - {before} < 3 — middleware chưa wire?"
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_metrics_422_does_not_increment_errors_total(
    auth_client: httpx.AsyncClient,
    admin_token: str,
) -> None:
    """Test 9: POST /api/search body invalid 422 → status=422 đếm, errors_total KHÔNG.

    ERRORS_TOTAL chỉ tăng với status >= 500 (HARD-02 spec). 4xx (validation /
    auth / forbidden) KHÔNG đếm là error vì là lỗi client.
    """
    before_err = (
        REGISTRY.get_sample_value(
            "errors_total",
            {"method": "POST", "path": "/api/search"},
        )
        or 0.0
    )

    # POST /api/search thiếu field bắt buộc `query` → 422 ValidationError.
    resp = await auth_client.post(
        "/api/search",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"hub_ids": [str(uuid.uuid4())]},  # thiếu `query`
    )
    assert resp.status_code == 422, resp.text

    # errors_total KHÔNG tăng (4xx ≠ error).
    after_err = (
        REGISTRY.get_sample_value(
            "errors_total",
            {"method": "POST", "path": "/api/search"},
        )
        or 0.0
    )
    assert after_err == before_err, (
        f"errors_total tăng từ {before_err} → {after_err} với 422 — phải == (4xx ≠ error)"
    )

    # requests_total{status="422"} cho POST /api/search phải >= 1.
    metrics_resp = await auth_client.get("/metrics")
    body = metrics_resp.text
    line_re = re.compile(
        r'^requests_total\{method="POST",path="/api/search",status="422"\} '
        r"(\d+(?:\.\d+)?)$",
        re.MULTILINE,
    )
    m = line_re.search(body)
    assert m is not None, (
        f"Không thấy requests_total{{POST,/api/search,422}} trong body:\n{body[:500]}"
    )
    assert float(m.group(1)) >= 1.0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_search_service_observes_search_latency_histogram(
    app_with_auth: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test 10: SearchService.search → SEARCH_LATENCY{hub_scope="single"} observe count tăng 1.

    Approach: gọi service trực tiếp với pool app_with_auth.state.db_pool +
    monkeypatch embed_text để skip LiteLLM. KHÔNG cần Redis (redis=None
    fail-open). Empty hub_ids cho user non-admin → service return sớm KHÔNG
    chạm SQL — nhưng SEARCH_LATENCY phải đã wrap toàn body của search().
    """
    from app.auth.dependencies import UserWithHubs
    from app.schemas.search import SearchRequest
    from app.services import search_service as ss_module
    from app.services.search_service import SearchService

    # Mock embed_text để KHÔNG cần OpenAI key.
    async def _fake_embed(text: str) -> list[float]:
        return [0.1] * 1536

    monkeypatch.setattr(ss_module, "embed_text", _fake_embed)

    pool = app_with_auth.state.db_pool
    assert pool is not None, "db_pool chưa init — fixture broken"

    svc = SearchService(pool=pool, redis=None)

    # User non-admin chưa assign hub → search() trả empty result hợp lệ,
    # nhưng wrap SEARCH_LATENCY context manager phải vẫn observe.
    fake_user = MagicMock(spec=UserWithHubs)
    fake_user.user = MagicMock()
    fake_user.user.role = "viewer"
    fake_user.hub_ids = []

    before = (
        REGISTRY.get_sample_value(
            "search_latency_seconds_count", {"hub_scope": "single"}
        )
        or 0.0
    )

    body = SearchRequest(query="test search instrument", top_k=5)
    result = await svc.search(body=body, user=fake_user)
    assert result["results"] == []

    after = (
        REGISTRY.get_sample_value(
            "search_latency_seconds_count", {"hub_scope": "single"}
        )
        or 0.0
    )
    assert (after - before) == pytest.approx(1.0, abs=1e-6), (
        f"SEARCH_LATENCY{{hub_scope=single}}_count {before} → {after} — wrap chưa observe?"
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_trigger_cocoindex_update_observes_ingest_duration_histogram(
    app_with_auth: Any,
) -> None:
    """Test 11: trigger_cocoindex_update → INGEST_DURATION_count tăng 1 (mock cocoindex_app)."""
    # Cần seed 1 document row trước — UPDATE 'failed' trong trigger_cocoindex
    # cần row tồn tại (status='processing' default). Seed minimum: doc_id + hub_id.
    from sqlalchemy import text as sql_text

    from app.db.session import get_engine
    from app.services.documents_service import trigger_cocoindex_update

    engine = get_engine()
    hub_id = str(uuid.uuid4())
    doc_id = uuid.uuid4()
    async with engine.begin() as conn:
        await conn.execute(
            sql_text(
                "INSERT INTO hubs (id, slug, code, name, subdomain, "
                "status, is_active, created_at, updated_at) VALUES "
                "(:id, 'metric-test', 'metric-test', 'Metric Hub', "
                "'metric', 'active', TRUE, NOW(), NOW())"
            ),
            {"id": hub_id},
        )
        await conn.execute(
            sql_text(
                "INSERT INTO documents (id, hub_id, uploaded_by, filename, "
                "file_path, mime_type, file_size_bytes, status, chunk_count, "
                "attempts, created_at, updated_at, last_heartbeat) "
                "VALUES (:id, :hub_id, NULL, 'metric.docx', '/tmp/metric.docx', "
                "'application/vnd.openxmlformats-officedocument.wordprocessingml.document', "
                "100, 'processing', 0, 0, NOW(), NOW(), NOW())"
            ),
            {"id": str(doc_id), "hub_id": hub_id},
        )

    # Mock cocoindex_app — update_blocking là hàm sync; trigger gọi qua
    # asyncio.to_thread → wrap thành coroutine. Lambda trả None ngay.
    mock_cocoindex = MagicMock()
    mock_cocoindex.update_blocking = MagicMock(return_value=None)

    before = (
        REGISTRY.get_sample_value("ingest_duration_seconds_count", {}) or 0.0
    )

    # Patch _TRIGGER_INITIAL_DELAY_SECONDS để test chạy nhanh (KHÔNG sleep 0.1s).
    from app.services import documents_service as ds_module

    original_delay = ds_module._TRIGGER_INITIAL_DELAY_SECONDS
    ds_module._TRIGGER_INITIAL_DELAY_SECONDS = 0
    original_backoff = ds_module._TRIGGER_BACKOFF_BASE_SECONDS
    ds_module._TRIGGER_BACKOFF_BASE_SECONDS = 0
    try:
        await trigger_cocoindex_update(mock_cocoindex, doc_id)
    finally:
        ds_module._TRIGGER_INITIAL_DELAY_SECONDS = original_delay
        ds_module._TRIGGER_BACKOFF_BASE_SECONDS = original_backoff

    after = (
        REGISTRY.get_sample_value("ingest_duration_seconds_count", {}) or 0.0
    )
    # update_blocking gọi tối đa _TRIGGER_MAX_ATTEMPTS lần (retry loop) — mỗi
    # attempt wrap bằng INGEST_DURATION.time() observe 1 lần.
    assert (after - before) >= 1.0, (
        f"INGEST_DURATION_count {before} → {after} — wrap chưa observe?"
    )

    # Cleanup row test (best-effort).
    async with engine.begin() as conn:
        await conn.execute(
            sql_text("DELETE FROM documents WHERE id = :id"),
            {"id": str(doc_id)},
        )
        await conn.execute(
            sql_text("DELETE FROM hubs WHERE id = :id"), {"id": hub_id}
        )

    _ = AsyncMock  # silence unused import (giữ symmetry cho test imports)
    _ = asyncio  # silence unused — asyncio.to_thread thực thi qua mock chain
