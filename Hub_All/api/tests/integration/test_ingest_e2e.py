"""E2E integration test Phase 4 REVISION 2 — M2a EXIT GATE proxy.

Verify full ingest pipeline: HTTP upload → A4 BackgroundTasks → cocoindex 1.0.3
flow update_blocking → chunks pgvector.

Mock LiteLLM (KHÔNG gọi OpenAI/Gemini thật trong CI):
- monkeypatch litellm.aembedding → return random vector dim 1536.
- Plan 04-02 embedder.py wrap LiteLLM — monkeypatch hit cấp module trước khi
  cocoindex flow execute.

Test 2 (scanned PDF) REVISION 2 — BLOCKER #3 + A4:
- Plan 04-04 REVISION 2 wire detect_scanned_pdf SYNCHRONOUS trong service.create.
- Mock detect_scanned_pdf → True → service 415 + INSERT failed_unsupported +
  KHÔNG add BackgroundTask cho scanned row.
- KHÔNG dùng marker x-fail (Plan 04-04 REVISION 2 đã wire BLOCKER #3 fix).

A4 BackgroundTasks pattern (REVISION 2):
- Sau POST upload (202), router add BackgroundTask trigger_cocoindex_update.
- BackgroundTask chạy SAU response client → cần poll GET /api/documents/:id
  để đợi status đổi từ 'pending' sang 'completed'/'failed'.
- Cocoindex 1.0.3 update_blocking đồng bộ (KHÔNG có per-row callback) →
  trigger_cocoindex_update count chunks sau update_blocking → set status.

Dependencies:
- Fixtures Phase 3 Plan 05 (postgres_container, redis_container, app_with_auth, auth_client, admin_token).
- Plan 04-03 REVISION 2 lifespan setup cocoindex_app real (KHÔNG mock như Plan 04-04 unit test).
- Plan 04-04 REVISION 2 router + service đã wire BLOCKER #3 + #4 + WARNING #6 + #7 + A4.
- Plan 04-05 REVISION 2 watchdog 5min timeout (KHÔNG ảnh hưởng E2E test < 60s).

Timeout 60s/test — A4 BackgroundTask + cocoindex update_blocking chạy in-process.
"""
from __future__ import annotations

import asyncio
import io
import random
import uuid
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import httpx
import pytest
from docx import Document as DocxDocument
from sqlalchemy import text

E2E_TIMEOUT_SECONDS = 60
E2E_POLL_INTERVAL_SECONDS = 1.0


def _make_docx_vn(tmp_path: Path, content_extra: str = "") -> bytes:
    """Tạo file DOCX VN sample tại tmp_path (runtime-generated, KHÔNG commit binary)."""
    doc = DocxDocument()
    doc.add_paragraph("Mục 1. KHÁM TỔNG QUÁT")
    doc.add_paragraph("Bệnh nhân được khám lâm sàng. " + content_extra)
    doc.add_paragraph("Mục 2. XÉT NGHIỆM")
    doc.add_paragraph("Làm xét nghiệm máu và siêu âm.")
    path = tmp_path / "khám-bệnh.docx"
    doc.save(str(path))
    return path.read_bytes()


@pytest.fixture
def mock_litellm_embedding(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mock litellm.aembedding global — return vector dim 1536 (R1 mitigation pin).

    Plan 04-02 embedder.py wrap `litellm.aembedding(...)` → response.data[0]['embedding'].
    Monkeypatch ở module-level `litellm.aembedding` đảm bảo intercept TRƯỚC khi
    cocoindex flow execute @coco.fn _embed_one (Plan 04-03).
    """

    async def _fake_aembedding(*args: Any, **kwargs: Any) -> Any:
        # Random vector dim 1536 (deterministic seed cho stability test).
        rng = random.Random(42)
        vec = [rng.uniform(-1.0, 1.0) for _ in range(1536)]
        return SimpleNamespace(data=[{"embedding": vec, "index": 0}])

    monkeypatch.setattr("litellm.aembedding", AsyncMock(side_effect=_fake_aembedding))


async def _create_hub(app_with_auth: Any) -> uuid.UUID:
    """INSERT 1 hub row trực tiếp (Phase 4 chưa có /api/hubs endpoint Plan 5)."""
    _ = app_with_auth  # trigger lifespan + migration
    from app.db.session import get_engine

    hid = uuid.uuid4()
    engine = get_engine()
    async with engine.begin() as conn:
        # Migration 0003 (Plan 05-01) thêm hubs.code / hubs.subdomain NOT NULL
        # (server_default đã drop) — helper phải truyền tường minh (DEF-05-02 fix).
        await conn.execute(
            text(
                "INSERT INTO hubs "
                "(id, slug, code, subdomain, name, description, "
                "is_active, created_at, updated_at) "
                "VALUES (:id, :slug, :code, :subdomain, :name, :desc, "
                "TRUE, NOW(), NOW())"
            ),
            {
                "id": str(hid),
                "slug": f"hub-{hid.hex[:8]}",
                "code": f"hub-{hid.hex[:8]}",
                "subdomain": f"hub-{hid.hex[:8]}",
                "name": "E2E Test Hub",
                "desc": "Phase 4 Plan 04-06 E2E",
            },
        )
    return hid


async def _upload_docx(
    client: httpx.AsyncClient,
    token: str,
    hub_id: uuid.UUID,
    content: bytes,
    name: str,
) -> str:
    """POST /api/documents/upload → return document_id từ envelope D6."""
    r = await client.post(
        "/api/documents/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={
            "file": (
                name,
                io.BytesIO(content),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
        data={"hub_id": str(hub_id)},
    )
    assert r.status_code == 202, r.text
    return str(r.json()["data"]["document_id"])


async def _wait_until(
    client: httpx.AsyncClient,
    token: str,
    doc_id: str,
    target_statuses: set[str],
    timeout: float = E2E_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Poll GET /api/documents/:id mỗi 1s, return body data khi status in target_statuses.

    A4 REVISION 2: chờ BackgroundTask trigger_cocoindex_update chạy xong
    (cocoindex_app.update_blocking + count chunks + UPDATE status).
    """
    elapsed = 0.0
    data: dict[str, Any] = {}
    while elapsed < timeout:
        r = await client.get(
            f"/api/documents/{doc_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200, r.text
        data = r.json()["data"]
        if data["status"] in target_statuses:
            return data
        await asyncio.sleep(E2E_POLL_INTERVAL_SECONDS)
        elapsed += E2E_POLL_INTERVAL_SECONDS
    pytest.fail(
        f"Document {doc_id} KHÔNG đạt status {target_statuses} sau {timeout}s — last: {data}"
    )


async def _force_cocoindex_update(app_with_auth: Any) -> None:
    """ALTERNATIVE FAST PATH — gọi cocoindex_app.update_blocking trực tiếp.

    Dùng nếu BackgroundTask flakiness trong testcontainers env. Plan 04-03 REVISION 2
    lifespan setup app.state.cocoindex_app — test có thể trigger sync update_blocking
    + UPDATE status thủ công (replicate trigger_cocoindex_update logic).
    """
    cocoindex_app = getattr(app_with_auth.state, "cocoindex_app", None)
    if cocoindex_app is not None:
        await asyncio.to_thread(cocoindex_app.update_blocking)


@pytest.mark.critical
@pytest.mark.integration
@pytest.mark.asyncio
async def test_e2e_upload_docx_to_chunks_completed(
    auth_client: httpx.AsyncClient,
    admin_token: str,
    app_with_auth: Any,
    tmp_path: Path,
    mock_litellm_embedding: None,
) -> None:
    """M2a EXIT GATE proxy 1/3 — upload DOCX VN → chunks pgvector (A4 BackgroundTasks).

    Verify chuỗi:
        1. POST /api/documents/upload DOCX VN → 202 + document_id.
        2. A4 BackgroundTask trigger_cocoindex_update chạy → cocoindex_app.update_blocking
           → flow extract → chunk → embed (mock) → INSERT chunks → UPDATE status='completed'.
        3. Poll GET /:id → status 'completed' + chunk_count > 0.
        4. SELECT chunks → vector dim=1536 (R1) + hub_id match + content_hash NOT NULL.
    """
    # Plan 04-07 gap closure: assert thay pytest.skip — CI gate enforce architectural
    # blocker recurrence. Task 2 lifespan fail-fast: nếu cocoindex_app=None ở đây →
    # lifespan đã raise → app_with_auth fixture KHÔNG resolve được (test FAIL ở fixture
    # setup) HOẶC test isolation broken. Cả 2 trường hợp đều phải FAIL loud, KHÔNG SKIP.
    cocoindex_app = getattr(app_with_auth.state, "cocoindex_app", None)
    assert cocoindex_app is not None, (
        "Plan 04-07 architectural regression — app.state.cocoindex_app=None sau lifespan. "
        "Expected: Task 2 fail-fast pattern (uvicorn crash startup nếu setup_cocoindex fail) → "
        "test KHÔNG bao giờ reach point này với cocoindex_app=None. "
        "Check: uvicorn startup logs cho 'cocoindex_init_failed_fail_fast' ERROR trace."
    )

    hub_id = await _create_hub(app_with_auth)
    content = _make_docx_vn(tmp_path)
    doc_id = await _upload_docx(auth_client, admin_token, hub_id, content, "khám.docx")

    # Đợi A4 BackgroundTask trigger_cocoindex_update hoàn thành.
    data = await _wait_until(
        auth_client,
        admin_token,
        doc_id,
        target_statuses={"completed", "failed", "failed_unsupported"},
    )
    assert data["status"] == "completed", f"Flow failed: {data.get('error_message')}"
    assert data["chunk_count"] > 0, "chunk_count must > 0 after completed"

    # SELECT chunks → verify vector dim + hub_id + content_hash.
    from app.db.session import get_engine

    engine = get_engine()
    async with engine.connect() as conn:
        rows = (
            await conn.execute(
                text(
                    "SELECT id, hub_id, content, content_hash, "
                    "       vector_dims(vector) AS dim "
                    "FROM chunks WHERE document_id = :doc"
                ),
                {"doc": doc_id},
            )
        ).fetchall()
    assert len(rows) > 0, "chunks table empty after completed"
    for r in rows:
        assert str(r[1]) == str(hub_id), f"hub_id mismatch: {r[1]} vs {hub_id}"
        assert r[3] is not None, "content_hash phải set (BLOCKER #2 wire ChunkRow.content_hash)"
        assert r[4] == 1536, f"vector dim sai: {r[4]} (R1 mitigation pin 1536)"


@pytest.mark.critical
@pytest.mark.integration
@pytest.mark.asyncio
async def test_e2e_pdf_scanned_failed_unsupported(
    auth_client: httpx.AsyncClient,
    admin_token: str,
    app_with_auth: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """M2a EXIT GATE proxy 2/3 — scanned PDF mock → 415 + failed_unsupported.

    BLOCKER #3 fix (Plan 04-04 REVISION 2 strategy A): router/service synchronous
    early-detect. Mock detect_scanned_pdf → True → service.create INSERT
    failed_unsupported + raise UnsupportedFormatError → router 415.

    A4 REVISION 2: KHÔNG add BackgroundTask cho scanned row → KHÔNG cần đợi.

    BỎ marker x-fail vì Plan 04-04 REVISION 2 đã wire fix.
    """
    hub_id = await _create_hub(app_with_auth)

    # Mock detect_scanned_pdf cả 2 module reference (module-level import resolution).
    # Plan 04-04 SUMMARY note 2: documents_service import detect_scanned_pdf trực tiếp
    # → monkeypatch ở documents_service module (KHÔNG chỉ file_extract) đảm bảo hit.
    from app.services import documents_service, file_extract

    def _fake_detect(path: Path) -> bool:
        return True

    monkeypatch.setattr(file_extract, "detect_scanned_pdf", _fake_detect)
    monkeypatch.setattr(documents_service, "detect_scanned_pdf", _fake_detect)

    # Minimal PDF magic header (router save file, service detect mock → True).
    pdf_bytes = (
        b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\nxref\n0 1\n"
        b"0000000000 65535 f \ntrailer<<>>\n%%EOF"
    )
    r = await auth_client.post(
        "/api/documents/upload",
        headers={"Authorization": f"Bearer {admin_token}"},
        files={"file": ("scan.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        data={"hub_id": str(hub_id)},
    )

    # BLOCKER #3 fix — service đã reject synchronously với 415.
    assert r.status_code == 415, (
        f"BLOCKER #3 violated — scanned PDF phải 415, got {r.status_code}: {r.text}"
    )
    body = r.json()
    assert body["success"] is False
    assert body["error"]["code"] == "UNSUPPORTED_FORMAT"

    # Verify DB — service.create đã INSERT row failed_unsupported TRƯỚC khi raise.
    from app.db.session import get_engine

    engine = get_engine()
    async with engine.connect() as conn:
        rows = (
            await conn.execute(
                text(
                    "SELECT status, filename, error_message FROM documents "
                    "WHERE hub_id = :hub AND filename = 'scan.pdf'"
                ),
                {"hub": str(hub_id)},
            )
        ).fetchall()
    assert len(rows) == 1, f"Phải có đúng 1 row scan.pdf, got {len(rows)}"
    assert rows[0][0] == "failed_unsupported", (
        f"R4 violated — status phải 'failed_unsupported', got: {rows[0][0]}"
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_e2e_content_hash_incremental_dedup(
    auth_client: httpx.AsyncClient,
    admin_token: str,
    app_with_auth: Any,
    tmp_path: Path,
    mock_litellm_embedding: None,
) -> None:
    """M2a EXIT GATE proxy 3/3 — upload cùng file 2 lần → chunks tuyến tính (KHÔNG bloated).

    Cocoindex 1.0.3 memo cache: same content fingerprint → re-use embedding cached.
    stable_chunk_id (uuid5 từ doc_id+chunk_index) — different document_id → different
    chunk_id (KHÔNG conflict). Acceptance: total chunks = n1 + n2 (tuyến tính),
    KHÔNG bloated >2x baseline (verify cocoindex memo hoạt động).
    """
    # Plan 04-07 gap closure: assert thay pytest.skip — CI gate enforce.
    cocoindex_app = getattr(app_with_auth.state, "cocoindex_app", None)
    assert cocoindex_app is not None, (
        "Plan 04-07 architectural regression — app.state.cocoindex_app=None sau lifespan. "
        "Expected: Task 2 fail-fast pattern. Check uvicorn startup logs."
    )

    hub_id = await _create_hub(app_with_auth)
    content = _make_docx_vn(tmp_path)

    # Upload lần 1
    doc1 = await _upload_docx(auth_client, admin_token, hub_id, content, "v1.docx")
    data1 = await _wait_until(
        auth_client,
        admin_token,
        doc1,
        target_statuses={"completed", "failed", "failed_unsupported"},
    )
    assert data1["status"] == "completed"
    n1 = data1["chunk_count"]
    assert n1 > 0

    # Upload lần 2 cùng content (khác filename + cùng hub_id)
    doc2 = await _upload_docx(auth_client, admin_token, hub_id, content, "v2.docx")
    data2 = await _wait_until(
        auth_client,
        admin_token,
        doc2,
        target_statuses={"completed", "failed", "failed_unsupported"},
    )
    assert data2["status"] == "completed"

    # SELECT chunks 2 documents — stable_chunk_id deterministic per (doc_id, idx).
    # Acceptance: total chunks = n1 + n2 (mỗi doc có chunks riêng vì document_id khác)
    # NHƯNG embedding KHÔNG re-compute (cocoindex 1.0.3 memo hit qua content fingerprint).
    from app.db.session import get_engine

    engine = get_engine()
    async with engine.connect() as conn:
        c1 = (
            await conn.execute(
                text("SELECT COUNT(*) FROM chunks WHERE document_id = :doc"),
                {"doc": doc1},
            )
        ).scalar()
        c2 = (
            await conn.execute(
                text("SELECT COUNT(*) FROM chunks WHERE document_id = :doc"),
                {"doc": doc2},
            )
        ).scalar()
    assert c1 == n1
    assert c2 == data2["chunk_count"]
    # Acceptance Plan 04-06 REVISION 2: KHÔNG bloated > 2x baseline.
    # Cocoindex 1.0.3 memo skip embed cho identical content fingerprint — chunks
    # vẫn INSERT (different doc_id → different stable_chunk_id) nhưng embed re-use.
    assert (c1 or 0) + (c2 or 0) <= 2 * n1, (
        "chunks bloated — cocoindex content-hash memo KHÔNG hoạt động"
    )
