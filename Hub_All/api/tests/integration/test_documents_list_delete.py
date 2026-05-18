"""Integration test Plan 04-05 — GET /api/documents (list) + DELETE /:id.

Reuse fixtures Phase 3 Plan 03-05:
- postgres_container, redis_container, app_with_auth, auth_client
- admin_user, viewer_user, admin_token, viewer_token

Mock app.state.cocoindex_app để A4 BackgroundTask trigger_cocoindex_update Plan
04-04 REVISION 2 chạy được mà KHÔNG cần cocoindex thật (test focus router +
service layer cho INGEST-07/08).

Test cover:
1. test_list_empty — DB trống → [] + total=0.
2. test_list_pagination_cap_per_page — per_page=200 → cap=100 (T-04-05-01).
3. test_list_filter_hub_id — filter hub_id chỉ trả docs thuộc hub đó.
4. test_list_filter_search_filename — ILIKE search filename.
5. test_delete_happy_path_cascade — DELETE → 204 + row + chunks (FK CASCADE) xoá + audit_logs.
6. test_delete_viewer_403 — viewer KHÔNG được DELETE → 403 FORBIDDEN.
7. test_delete_unknown_404 — DELETE unknown UUID → 404 NOT_FOUND.
"""
from __future__ import annotations

import io
import uuid
from pathlib import Path
from typing import Any

import httpx
import pytest
from docx import Document as DocxDocument
from sqlalchemy import text


class MockCocoindexApp:
    """Mock coco.App cho test — A4 BackgroundTask sẽ call update_blocking."""

    def __init__(self) -> None:
        self.update_blocking_calls: int = 0

    def update_blocking(self) -> None:
        # Sync method (asyncio.to_thread chạy được).
        self.update_blocking_calls += 1


def _make_docx(tmp_path: Path, name: str = "test.docx") -> bytes:
    """Tạo DOCX sample → bytes."""
    doc = DocxDocument()
    doc.add_paragraph("Test content")
    path = tmp_path / name
    doc.save(str(path))
    return path.read_bytes()


async def _create_hub(app_with_auth: Any) -> uuid.UUID:
    """INSERT 1 hub row trực tiếp (Phase 4 chưa có /api/hubs endpoint)."""
    _ = app_with_auth
    from app.db.session import get_engine

    hid = uuid.uuid4()
    engine = get_engine()
    async with engine.begin() as conn:
        # Migration 0003 (Plan 05-01) thêm hubs.code / hubs.subdomain NOT NULL
        # (server_default đã drop). hubs.status NOT NULL giữ server_default 'active'.
        await conn.execute(
            text(
                "INSERT INTO hubs "
                "(id, slug, code, subdomain, name, is_active, created_at) "
                "VALUES (:id, :slug, :code, :subdomain, 'h', TRUE, NOW())"
            ),
            {
                "id": str(hid),
                "slug": f"hub-{hid.hex[:8]}",
                "code": f"hub-{hid.hex[:8]}",
                "subdomain": f"hub-{hid.hex[:8]}",
            },
        )
    return hid


@pytest.fixture
def mock_cocoindex_app(app_with_auth: Any) -> MockCocoindexApp:
    """Mock app.state.cocoindex_app cho A4 BackgroundTask Plan 04-04 REVISION 2."""
    mock = MockCocoindexApp()
    app_with_auth.state.cocoindex_app = mock
    return mock


async def _upload(
    client: httpx.AsyncClient,
    token: str,
    hub_id: uuid.UUID,
    filename: str,
    content: bytes,
) -> str:
    """POST upload + assert 202 + return doc_id."""
    r = await client.post(
        "/api/documents/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={
            "file": (
                filename,
                io.BytesIO(content),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
        data={"hub_id": str(hub_id)},
    )
    assert r.status_code == 202, r.text
    return str(r.json()["data"]["id"])


@pytest.mark.critical
@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_empty(
    auth_client: httpx.AsyncClient,
    admin_token: str,
    app_with_auth: Any,
) -> None:
    """DB trống → list trả [] + total=0."""
    _ = app_with_auth
    r = await auth_client.get(
        "/api/documents",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["success"] is True
    assert body["data"] == []
    assert body["meta"]["total"] == 0


@pytest.mark.critical
@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_pagination_cap_per_page(
    auth_client: httpx.AsyncClient,
    admin_token: str,
    app_with_auth: Any,
    tmp_path: Path,
    mock_cocoindex_app: MockCocoindexApp,
) -> None:
    """per_page=200 → cap=100 (T-04-05-01 INGEST-08)."""
    _ = mock_cocoindex_app
    hub_id = await _create_hub(app_with_auth)
    content = _make_docx(tmp_path)
    # Upload 5 rows
    for i in range(5):
        await _upload(auth_client, admin_token, hub_id, f"file-{i}.docx", content)

    r = await auth_client.get(
        "/api/documents?per_page=200&page=1",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["meta"]["per_page"] == 100, (
        f"T-04-05-01 violated — per_page=200 phải cap=100, got {body['meta']['per_page']}"
    )
    assert body["meta"]["total"] == 5
    assert len(body["data"]) == 5


@pytest.mark.critical
@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_filter_hub_id(
    auth_client: httpx.AsyncClient,
    admin_token: str,
    app_with_auth: Any,
    tmp_path: Path,
    mock_cocoindex_app: MockCocoindexApp,
) -> None:
    """Filter hub_id chỉ trả docs thuộc hub đó."""
    _ = mock_cocoindex_app
    hub_a = await _create_hub(app_with_auth)
    hub_b = await _create_hub(app_with_auth)
    content = _make_docx(tmp_path)
    await _upload(auth_client, admin_token, hub_a, "a.docx", content)
    await _upload(auth_client, admin_token, hub_a, "b.docx", content)
    await _upload(auth_client, admin_token, hub_b, "c.docx", content)

    r = await auth_client.get(
        f"/api/documents?hub_id={hub_a}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["meta"]["total"] == 2
    assert all(item["hub_id"] == str(hub_a) for item in body["data"])


@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_filter_search_filename(
    auth_client: httpx.AsyncClient,
    admin_token: str,
    app_with_auth: Any,
    tmp_path: Path,
    mock_cocoindex_app: MockCocoindexApp,
) -> None:
    """ILIKE search filename — case-insensitive partial match."""
    _ = mock_cocoindex_app
    hub_id = await _create_hub(app_with_auth)
    content = _make_docx(tmp_path)
    await _upload(auth_client, admin_token, hub_id, "Báo cáo Q1.docx", content)
    await _upload(auth_client, admin_token, hub_id, "Khám bệnh.docx", content)

    r = await auth_client.get(
        "/api/documents?search=báo",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["meta"]["total"] == 1, (
        f"ILIKE 'báo' phải match 1 file 'Báo cáo Q1.docx', got total={body['meta']['total']}"
    )
    assert "Báo cáo" in body["data"][0]["name"]


@pytest.mark.critical
@pytest.mark.integration
@pytest.mark.asyncio
async def test_delete_happy_path_cascade(
    auth_client: httpx.AsyncClient,
    admin_token: str,
    admin_user: dict[str, str],
    app_with_auth: Any,
    tmp_path: Path,
    mock_cocoindex_app: MockCocoindexApp,
) -> None:
    """DELETE → 204 + row + chunks (FK CASCADE) xoá + audit_logs entry."""
    _ = mock_cocoindex_app
    hub_id = await _create_hub(app_with_auth)
    content = _make_docx(tmp_path)
    doc_id = await _upload(auth_client, admin_token, hub_id, "x.docx", content)

    r = await auth_client.delete(
        f"/api/documents/{doc_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 204, r.text

    # Verify DB.
    from app.db.session import get_engine

    engine = get_engine()
    async with engine.connect() as conn:
        row = (
            await conn.execute(
                text("SELECT id FROM documents WHERE id=:id"),
                {"id": doc_id},
            )
        ).fetchone()
        assert row is None, "Document KHÔNG bị xoá"

        audit = (
            await conn.execute(
                text(
                    "SELECT action, target_id, user_id FROM audit_logs "
                    "WHERE action='document_delete' AND target_id=:id"
                ),
                {"id": doc_id},
            )
        ).fetchone()
        assert audit is not None, (
            "audit_logs entry document_delete KHÔNG được tạo"
        )
        assert str(audit[2]) == admin_user["id"], (
            f"user_id audit phải = admin_user.id ({admin_user['id']}), got {audit[2]}"
        )


@pytest.mark.critical
@pytest.mark.integration
@pytest.mark.asyncio
async def test_delete_viewer_403(
    auth_client: httpx.AsyncClient,
    admin_token: str,
    viewer_token: str,
    app_with_auth: Any,
    tmp_path: Path,
    mock_cocoindex_app: MockCocoindexApp,
) -> None:
    """Viewer KHÔNG được DELETE → 403 FORBIDDEN (RBAC require_role admin)."""
    _ = mock_cocoindex_app
    hub_id = await _create_hub(app_with_auth)
    content = _make_docx(tmp_path)
    doc_id = await _upload(auth_client, admin_token, hub_id, "x.docx", content)

    r = await auth_client.delete(
        f"/api/documents/{doc_id}",
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert r.status_code == 403, r.text
    body = r.json()
    assert body["success"] is False
    assert body["error"]["code"] == "FORBIDDEN"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_delete_unknown_404(
    auth_client: httpx.AsyncClient,
    admin_token: str,
    app_with_auth: Any,
) -> None:
    """DELETE unknown UUID → 404 NOT_FOUND."""
    _ = app_with_auth
    r = await auth_client.delete(
        f"/api/documents/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 404, r.text
    body = r.json()
    assert body["error"]["code"] == "NOT_FOUND"
