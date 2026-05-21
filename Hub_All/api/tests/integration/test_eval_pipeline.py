"""Eval pipeline smoke regression (Phase 9 EVAL-04 / Plan 09-05).

Smoke test MOCK EMBED < 60s — verify eval pipeline KHÔNG vỡ regression khi
merge PR mới. **KHÔNG measure gate verdict ≥75% top-3** — đó là track standalone
``make eval-all`` (Wave 4 HUMAN UAT với OpenAI key thật ~$0.20/run).

Test này verify pipeline reachable end-to-end:
- upload 1 DOCX VN sample → cocoindex flow chunk + embed (mock) → pgvector chunks
- search 1 query → top-K result với ``title=filename`` (D-10 search_service.py:_row_to_item)
- scanned PDF → 415 ``failed_unsupported`` (R4 mitigation Phase 4)
- hub isolation (E4): chunk hub-A KHÔNG leak khi search hub-B

CI gate: ``pytest -m critical api/tests/integration/test_eval_pipeline.py`` PASS.

Reuse fixture stack:
- ``app_with_auth`` (override per-file Phase 4 pattern test_ingest_e2e.py) — real
  cocoindex_app session-scoped qua ``_cocoindex_env`` (DEF-05-01 singleton).
- ``auth_client`` httpx ASGITransport in-process.
- ``admin_token`` JWT RS256 admin.
- ``eval_hub_seeded`` + ``mock_litellm_embed`` (conftest_eval.py).

Pattern source: ``api/tests/integration/test_ingest_e2e.py`` (Phase 4 E2E).
"""
from __future__ import annotations

import asyncio
import io
import os
import sys
import time
import uuid
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
from alembic.config import Config
from asgi_lifespan import LifespanManager
from sqlalchemy import create_engine, text
from testcontainers.postgres import PostgresContainer
from testcontainers.redis import RedisContainer

# ========================================================================
# === eval.lib import + dataset path resolution ==========================
# ========================================================================
#
# Hub_All/eval/ là Python project độc lập (pyproject.toml riêng). KHÔNG
# import qua install — chỉ thêm parent của eval/ (Hub_All/) vào sys.path để
# import ``from eval.lib import upload_and_wait``. Pattern khớp Plan 09-02 lib.

_HUB_ALL_ROOT = Path(__file__).resolve().parents[3]
_EVAL_ROOT = _HUB_ALL_ROOT / "eval"
if str(_HUB_ALL_ROOT) not in sys.path:
    sys.path.insert(0, str(_HUB_ALL_ROOT))

from eval.lib import upload_and_wait  # noqa: E402 — sys.path inject ở trên

DATASET_SOURCES = _EVAL_ROOT / "dataset" / "sources"
DATASET_SCANNED = _EVAL_ROOT / "dataset" / "scanned"

SMOKE_TIMEOUT_SECONDS = 45  # tolerant Phase 4 race retry ~3.6s overhead
SMOKE_POLL_INTERVAL = 1.0


# ========================================================================
# === Override app_with_auth + _cocoindex_env (DEF-05-01 singleton) ======
# ========================================================================
#
# Pattern khớp test_ingest_e2e.py — cocoindex 1.0.3 Environment singleton:
# - _cocoindex_env: session-scoped, setup 1 lần, teardown 1 lần.
# - app_with_auth: override conftest, gắn real cocoindex_app vào app.state SAU
#   lifespan (lifespan giữ COCOINDEX_SKIP_SETUP=1).


@pytest.fixture(scope="session")
def _cocoindex_env(request: pytest.FixtureRequest) -> Iterator[Any]:
    """Setup cocoindex 1.0.3 default env ĐÚNG 1 LẦN cho session smoke test."""
    from app.config import get_settings
    from app.rag.setup import get_cocoindex_app, setup_cocoindex, stop_cocoindex

    get_settings.cache_clear()
    setup_cocoindex(get_settings())
    cocoindex_app = get_cocoindex_app()

    def _teardown() -> None:
        stop_cocoindex()

    request.addfinalizer(_teardown)
    return cocoindex_app


@pytest.fixture
async def app_with_auth(  # noqa: F811 — shadow conftest cho file smoke này
    postgres_container: PostgresContainer,
    redis_container: RedisContainer,
    alembic_cfg: Config,
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
) -> AsyncIterator[Any]:
    """Override conftest — app + migration + real cocoindex_app session-scoped."""
    sync_url = postgres_container.get_connection_url().replace(
        "postgresql+psycopg2://", "postgresql://"
    )
    async_url = sync_url.replace("postgresql://", "postgresql+asyncpg://")
    redis_host = redis_container.get_container_host_ip()
    redis_port = redis_container.get_exposed_port(6379)

    monkeypatch.setenv("DATABASE_URL", async_url)
    monkeypatch.setenv("COCOINDEX_DATABASE_URL", sync_url)
    monkeypatch.setenv("REDIS_URL", f"redis://{redis_host}:{redis_port}/0")
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("JWT_PRIVATE_KEY_PATH", "keys/private.pem")
    monkeypatch.setenv("JWT_PUBLIC_KEY_PATH", "keys/public.pem")
    monkeypatch.setenv("JWT_ACCESS_TOKEN_TTL", "900")
    monkeypatch.setenv("JWT_REFRESH_TOKEN_TTL", "604800")
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "http://localhost:5173")
    monkeypatch.setenv(
        "AES_KEY", "bWVkaW5ldC10ZXN0LWFlcy1rZXktMzJieXRlcyEhMDA="
    )
    monkeypatch.setenv("COCOINDEX_SKIP_SETUP", "1")

    from app.config import get_settings
    get_settings.cache_clear()

    from alembic import command
    await asyncio.to_thread(command.upgrade, alembic_cfg, "head")

    from app.db.session import dispose_engine
    await dispose_engine()

    from app.services.audit_service import reset_queue
    reset_queue()

    sync_dsn = os.environ["DATABASE_URL"].replace(
        "postgresql+asyncpg://", "postgresql://"
    )
    sync_eng = create_engine(sync_dsn)
    with sync_eng.begin() as conn:
        conn.execute(
            text(
                "TRUNCATE TABLE users, refresh_tokens, user_hubs, hubs, "
                "audit_logs, api_keys, documents, chunks "
                "RESTART IDENTITY CASCADE"
            )
        )
    sync_eng.dispose()

    cocoindex_app = request.getfixturevalue("_cocoindex_env")

    from app.main import create_app
    app = create_app()
    async with LifespanManager(app):
        app.state.cocoindex_app = cocoindex_app
        app.state.cocoindex_ready = True
        try:
            yield app
        finally:
            # CRITICAL: clear cocoindex_app TRƯỚC LifespanManager shutdown.
            # Owner DUY NHẤT của stop_cocoindex là _cocoindex_env finalizer
            # (DEF-05-01 singleton — không re-open được sau stop).
            app.state.cocoindex_app = None
            app.state.cocoindex_ready = False


# ========================================================================
# === Helper functions ===================================================
# ========================================================================


def _pick_sample_docx() -> Path:
    """Pick file DOCX nhỏ nhất từ ``eval/dataset/sources/`` để smoke nhanh.

    Skip nếu dataset trống — Plan 09-01 đã restore từ commit ``0af44f0``,
    nhưng trong CI clean checkout cần ``git checkout 0af44f0 -- eval/dataset/``
    (xem ``make eval-restore``).
    """
    if not DATASET_SOURCES.is_dir():
        pytest.skip(
            f"Dataset sources thư mục không tồn tại {DATASET_SOURCES}. "
            f"Restore: cd Hub_All && make eval-restore"
        )
    candidates = sorted(DATASET_SOURCES.glob("*.docx"), key=lambda p: p.stat().st_size)
    if not candidates:
        pytest.skip(
            f"Dataset sources trống tại {DATASET_SOURCES}. "
            f"Restore: cd Hub_All && make eval-restore"
        )
    return candidates[0]


def _pick_scanned_pdf() -> Path:
    """Pick file scanned PDF từ ``eval/dataset/scanned/`` (R4 test 415)."""
    if not DATASET_SCANNED.is_dir():
        pytest.skip(f"Dataset scanned thư mục không tồn tại {DATASET_SCANNED}.")
    candidates = sorted(DATASET_SCANNED.glob("*.pdf"))
    if not candidates:
        pytest.skip(f"Dataset scanned trống tại {DATASET_SCANNED}.")
    return candidates[0]


async def _reconcile_status(app: Any, doc_id: str) -> None:
    """Re-trigger cocoindex update_blocking + reconcile documents.status.

    Phase 4 "New Gap A" (test_ingest_e2e.py:_reconcile_document_status pattern).
    A4 BackgroundTask có thể chạy TRƯỚC khi transaction INSERT documents commit
    visible cho cocoindex asyncpg pool → flow fetch 0 rows → 0 chunks → STUCK.
    Helper này gọi SAU upload đã return (row commit visible) → re-trigger
    update_blocking + UPDATE status.
    """
    cocoindex_app = getattr(app.state, "cocoindex_app", None)
    if cocoindex_app is None:
        return

    from app.db.session import get_engine

    await asyncio.to_thread(cocoindex_app.update_blocking)

    engine = get_engine()
    async with engine.begin() as conn:
        count = (
            await conn.execute(
                text("SELECT COUNT(*) FROM chunks WHERE document_id = :id"),
                {"id": doc_id},
            )
        ).scalar() or 0
        new_status = "completed" if count > 0 else "failed"
        await conn.execute(
            text(
                "UPDATE documents SET status=:st, chunk_count=:cnt, "
                "error_message=:err, last_heartbeat=NOW(), updated_at=NOW() "
                "WHERE id = :id AND status NOT IN "
                "('completed', 'failed_unsupported')"
            ),
            {
                "st": new_status,
                "cnt": count,
                "err": None if count > 0 else "cocoindex flow generated 0 chunks",
                "id": doc_id,
            },
        )


async def _upload_file(
    client: httpx.AsyncClient,
    token: str,
    hub_id: str,
    file_path: Path,
    *,
    content_type: str = "application/octet-stream",
) -> tuple[int, dict[str, Any]]:
    """POST /api/documents/upload (multipart) — trả (status_code, body)."""
    content = file_path.read_bytes()
    r = await client.post(
        "/api/documents/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": (file_path.name, io.BytesIO(content), content_type)},
        data={"hub_id": hub_id},
    )
    try:
        body: dict[str, Any] = r.json()
    except ValueError:
        body = {"raw": r.text}
    return r.status_code, body


async def _poll_until_terminal(
    client: httpx.AsyncClient,
    token: str,
    doc_id: str,
    timeout: float = SMOKE_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Poll GET /api/documents/:id đến terminal status hoặc timeout.

    Terminal: ``{completed, failed, failed_unsupported}``.
    """
    elapsed = 0.0
    data: dict[str, Any] = {}
    while elapsed < timeout:
        r = await client.get(
            f"/api/documents/{doc_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        if r.status_code == 200:
            data = r.json()["data"]
            if data["status"] in ("completed", "failed", "failed_unsupported"):
                return data
        await asyncio.sleep(SMOKE_POLL_INTERVAL)
        elapsed += SMOKE_POLL_INTERVAL
    pytest.fail(
        f"Document {doc_id} KHÔNG đạt terminal status sau {timeout}s — last: {data}"
    )


async def _search_query(
    client: httpx.AsyncClient,
    token: str,
    query: str,
    hub_id: str,
    top_k: int = 5,
) -> tuple[list[dict[str, Any]], float]:
    """POST /api/search body {query, hub_ids, top_k} (D-02 Phase 6).

    Trả (results, latency_ms). result.title = filename (D-10).
    """
    t0 = time.perf_counter()
    r = await client.post(
        "/api/search",
        headers={"Authorization": f"Bearer {token}"},
        json={"query": query, "hub_ids": [hub_id], "top_k": top_k},
    )
    t1 = time.perf_counter()
    r.raise_for_status()
    results = r.json()["data"]["results"]
    return list(results), (t1 - t0) * 1000.0


# Verify eval.lib.upload_and_wait import — không call (chỉ assert reachable)
# vì smoke pytest dùng helper in-process ở trên, không gọi standalone CLI.
assert callable(upload_and_wait), "eval.lib.upload_and_wait phải import được"


# ========================================================================
# === Tests ==============================================================
# ========================================================================


@pytest.mark.critical
@pytest.mark.integration
@pytest.mark.asyncio
async def test_eval_smoke_upload_search_pipeline(
    auth_client: httpx.AsyncClient,
    admin_token: str,
    app_with_auth: Any,
    eval_hub_seeded: str,
    mock_litellm_embed: None,
) -> None:
    """Smoke pipeline 1/3 — upload 1 DOCX VN sample → search → assert reachable.

    Pipeline 8-step end-to-end:
    1. Login admin (đã ở fixture admin_token)
    2. Pick 1 sample DOCX nhỏ nhất từ eval/dataset/sources/
    3. Upload qua POST /api/documents/upload + hub_id=eval_hub_seeded
    4. Poll status đến completed (max 45s)
    5. Assert status='completed' + chunk_count > 0
    6. Search 1 query VN → POST /api/search top_k=5
    7. Assert ≥1 result có ``title`` field set + ``hub_id`` matches
    8. Assert latency < 5000ms (sanity, KHÔNG strict budget vì mock embed)

    KHÔNG verify retrieval semantic (mock embed deterministic hash) — đó là
    Wave 4 HUMAN UAT với OpenAI key thật.
    """
    # Architectural guard (khớp test_ingest_e2e.py:test_e2e_upload_docx_to_chunks)
    cocoindex_app = getattr(app_with_auth.state, "cocoindex_app", None)
    assert cocoindex_app is not None, (
        "Plan 09-05 regression — app.state.cocoindex_app=None sau lifespan. "
        "Expected: _cocoindex_env session fixture đã setup. "
        "Check: uvicorn startup logs cho 'cocoindex_init_failed_fail_fast'."
    )

    sample = _pick_sample_docx()
    hub_id = eval_hub_seeded

    # Upload
    status_code, body = await _upload_file(
        auth_client,
        admin_token,
        hub_id,
        sample,
        content_type=(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ),
    )
    assert status_code == 202, f"Upload trả {status_code}: {body}"
    doc_id = str(body["data"]["id"])

    # A4 race fix — re-trigger update_blocking sau khi row chắc chắn commit
    await _reconcile_status(app_with_auth, doc_id)

    # Poll terminal
    data = await _poll_until_terminal(auth_client, admin_token, doc_id)
    assert data["status"] == "completed", (
        f"Upload status: {data['status']} err={data.get('error_message')}"
    )
    assert data.get("chunk_count", 0) > 0, "chunk_count phải > 0 sau cocoindex flow"

    # Search 1 query VN (semantic không quan trọng — mock embed deterministic)
    results, latency_ms = await _search_query(
        auth_client, admin_token, "định vị trung tâm", hub_id, top_k=5
    )
    assert isinstance(results, list), "results phải là list"
    assert len(results) >= 1, f"Phải có ≥1 result, got {len(results)}"

    # D-10 M2: result.title = filename
    for r in results:
        assert "title" in r, f"result thiếu field 'title' (D-10): {r}"
        assert r["title"], f"title không được rỗng: {r}"
        # E4 hub isolation
        assert str(r.get("hub_id")) == hub_id, (
            f"Result leak hub khác: {r.get('hub_id')} != {hub_id}"
        )

    # Sanity latency (mock embed thường < 1000ms in-process)
    assert latency_ms < 5000, f"Latency {latency_ms}ms quá lâu cho smoke (mock embed)"


@pytest.mark.critical
@pytest.mark.integration
@pytest.mark.asyncio
async def test_eval_smoke_scanned_pdf_failed_unsupported(
    auth_client: httpx.AsyncClient,
    admin_token: str,
    app_with_auth: Any,
    eval_hub_seeded: str,
    mock_litellm_embed: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Smoke pipeline 2/3 — scanned PDF → 415 ``failed_unsupported`` (R4).

    BLOCKER #3 fix (Plan 04-04 REVISION 2): router/service synchronous early-detect
    qua ``detect_scanned_pdf``. Mock → True → service.create INSERT
    ``failed_unsupported`` + raise UnsupportedFormatError → router 415.

    Test scanned PDF thật từ ``eval/dataset/scanned/`` (M1 restore commit 0af44f0).
    Mock ``detect_scanned_pdf`` để khỏi phụ thuộc binary phân tích PDF — chỉ
    verify pipeline route 415 + status enum đúng (R4 contract).
    """
    cocoindex_app = getattr(app_with_auth.state, "cocoindex_app", None)
    assert cocoindex_app is not None, "Plan 09-05 regression — cocoindex_app None"

    scanned = _pick_scanned_pdf()
    hub_id = eval_hub_seeded

    # Mock detect_scanned_pdf → True (force 415 path).
    # Plan 04-04 SUMMARY note 2: documents_service import detect_scanned_pdf
    # trực tiếp → monkeypatch CẢ 2 module reference đảm bảo hit
    # (module-level import resolution snapshot ở thời điểm import).
    from app.services import documents_service, file_extract

    def _fake_detect(*_a: Any, **_kw: Any) -> bool:
        return True

    monkeypatch.setattr(file_extract, "detect_scanned_pdf", _fake_detect)
    monkeypatch.setattr(documents_service, "detect_scanned_pdf", _fake_detect)

    status_code, body = await _upload_file(
        auth_client,
        admin_token,
        hub_id,
        scanned,
        content_type="application/pdf",
    )

    # Service.create raise UnsupportedFormatError → router map 415
    assert status_code == 415, (
        f"Scanned PDF phải trả 415 (R4 whitelist), got {status_code}: {body}"
    )
    # Envelope D6: {success: false, error: {code, message}, data: null, meta: ...}
    assert body.get("success") is False, f"Envelope success phải False: {body}"
    err = body.get("error") or {}
    assert err, f"Envelope error phải có content: {body}"

    # Verify DB row đã INSERT failed_unsupported (Plan 04-04 strategy A)
    from app.db.session import get_engine
    engine = get_engine()
    async with engine.connect() as conn:
        rows = (
            await conn.execute(
                text(
                    "SELECT status FROM documents WHERE hub_id = :hub "
                    "AND filename = :fn"
                ),
                {"hub": hub_id, "fn": scanned.name},
            )
        ).fetchall()
    assert len(rows) == 1, (
        f"Phải có 1 documents row failed_unsupported, got {len(rows)} rows"
    )
    assert rows[0][0] == "failed_unsupported", (
        f"Status enum sai (R4): {rows[0][0]}"
    )


@pytest.mark.critical
@pytest.mark.integration
@pytest.mark.asyncio
async def test_eval_smoke_hub_isolation_no_leak(
    auth_client: httpx.AsyncClient,
    admin_token: str,
    app_with_auth: Any,
    eval_hub_seeded: str,
    mock_litellm_embed: None,
) -> None:
    """Smoke pipeline 3/3 — E4 hub isolation: chunk hub-A KHÔNG leak search hub-B.

    Quy trình:
    1. Upload 1 file vào ``eval_hub_seeded`` (hub-A).
    2. Tạo thêm hub-B (eval-smoke-b) qua INSERT trực tiếp.
    3. Search query với ``hub_ids=[hub_b_id]`` → assert kết quả KHÔNG chứa
       chunk hub-A (filter hub_id ở search_service post-filter HNSW).

    Đây là regression sanity cho Phase 6 SEARCH-03 hub isolation (đã có
    test_search_hub_isolation.py — smoke chỉ verify pipeline cuối E2E).
    """
    cocoindex_app = getattr(app_with_auth.state, "cocoindex_app", None)
    assert cocoindex_app is not None, "Plan 09-05 regression — cocoindex_app None"

    sample = _pick_sample_docx()
    hub_a_id = eval_hub_seeded

    # Tạo hub-B
    from app.db.session import get_engine
    engine = get_engine()
    hub_b_id = str(uuid.uuid4())
    hub_b_code = "eval-smoke-b"
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO hubs "
                "(id, slug, code, subdomain, name, description, status, "
                "is_active, created_at, updated_at) "
                "VALUES (:id, :slug, :code, :subdomain, :name, NULL, 'active', "
                "TRUE, NOW(), NOW())"
            ),
            {
                "id": hub_b_id,
                "slug": hub_b_code,
                "code": hub_b_code,
                "subdomain": "eval-smoke-b.medinet.vn",
                "name": "Eval Hub B (isolation test)",
            },
        )

    try:
        # Upload vào hub-A
        status_code, body = await _upload_file(
            auth_client,
            admin_token,
            hub_a_id,
            sample,
            content_type=(
                "application/vnd.openxmlformats-officedocument."
                "wordprocessingml.document"
            ),
        )
        assert status_code == 202, f"Upload hub-A {status_code}: {body}"
        doc_id = str(body["data"]["id"])

        # Race fix
        await _reconcile_status(app_with_auth, doc_id)

        # Poll terminal
        data = await _poll_until_terminal(auth_client, admin_token, doc_id)
        assert data["status"] == "completed"
        assert data.get("chunk_count", 0) > 0

        # Search HUB-B — KHÔNG có data → expected 0 results HOẶC results không
        # chứa hub_id=hub_a_id.
        results, _ = await _search_query(
            auth_client, admin_token, "định vị trung tâm", hub_b_id, top_k=5
        )

        for r in results:
            assert str(r.get("hub_id")) != hub_a_id, (
                f"E4 LEAK: chunk hub-A xuất hiện trong search hub-B: "
                f"hub_id={r.get('hub_id')} title={r.get('title')}"
            )
    finally:
        # Cleanup hub-B
        async with engine.begin() as conn:
            await conn.execute(
                text("DELETE FROM hubs WHERE id = :hid"), {"hid": hub_b_id}
            )
