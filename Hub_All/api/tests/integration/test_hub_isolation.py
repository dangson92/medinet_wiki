"""E4 EXIT criteria — hub isolation critical test suite (Plan 05-06 / HUB-02).

EXIT criteria E4 (PROJECT.md): hub isolation bug = ship-blocker. Editor của Hub A
KHÔNG được DELETE document của Hub B kể cả khi truyền explicit hub_id. Test fail
= STOP, security review (PROJECT.md E4 — bug không fixable trong 7 ngày → STOP).

MỌI test marker `@pytest.mark.critical` — CI gate `pytest -m critical` (HARD-03).
KHÔNG `pytest.skip`, KHÔNG `assert True # TODO` — E4 test phải genuinely PASS
against real DB (testcontainers Postgres) qua fixture `app_with_auth`.

Endpoint dưới test: `DELETE /api/documents/:doc_id` (ROADMAP SC2 — endpoint
editor-eligible, hub-scoped). `documents_service.delete()` gọi `verify_hub_access`
với `hub_id` resource load TỪ DB row (KHÔNG payload — T-05-06-02).

Reuse fixtures conftest: app_with_auth, auth_client, admin/editor/viewer
user+token, _insert_hub, _assign_user_hub.
"""
from __future__ import annotations

import asyncio
import io
import uuid
from pathlib import Path
from typing import Any

import httpx
import pytest
from docx import Document as DocxDocument
from sqlalchemy import text

from app.repositories.hub_isolation import HubIsolationError, verify_hub_access
from tests.integration.conftest import _assign_user_hub, _insert_hub


class MockCocoindexApp:
    """Mock coco.App — A4 BackgroundTask trigger_cocoindex_update gọi update_blocking."""

    def __init__(self) -> None:
        self.update_blocking_calls: int = 0

    def update_blocking(self) -> None:
        self.update_blocking_calls += 1


@pytest.fixture
def mock_cocoindex_app(app_with_auth: Any) -> MockCocoindexApp:
    """Mock app.state.cocoindex_app cho A4 BackgroundTask (upload không cần cocoindex thật)."""
    mock = MockCocoindexApp()
    app_with_auth.state.cocoindex_app = mock
    return mock


def _make_docx(tmp_path: Path, name: str = "test.docx") -> bytes:
    """Tạo DOCX sample → bytes."""
    doc = DocxDocument()
    doc.add_paragraph("Nội dung tài liệu test")
    path = tmp_path / name
    doc.save(str(path))
    return path.read_bytes()


async def _upload(
    client: httpx.AsyncClient,
    token: str,
    hub_id: str,
    filename: str,
    content: bytes,
) -> str:
    """POST upload (admin) + assert 202 + return doc_id."""
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
        data={"hub_id": hub_id},
    )
    assert r.status_code == 202, r.text
    return str(r.json()["data"]["id"])


async def _count(query: str, params: dict[str, Any]) -> int:
    """Helper — SELECT COUNT scalar qua engine."""
    from app.db.session import get_engine
    engine = get_engine()
    async with engine.connect() as conn:
        row = (await conn.execute(text(query), params)).fetchone()
    return int(row[0]) if row else 0


@pytest.mark.critical
@pytest.mark.integration
@pytest.mark.asyncio
async def test_editor_hub_a_cannot_delete_doc_hub_b(
    auth_client: httpx.AsyncClient,
    admin_token: str,
    editor_token: str,
    editor_user: dict[str, str],
    app_with_auth: Any,
    tmp_path: Path,
    mock_cocoindex_app: MockCocoindexApp,
) -> None:
    """E4 — editor (assigned Hub A) DELETE document Hub B → 403; document VẪN tồn tại.

    Hub isolation bug = STOP, security review (PROJECT.md E4).
    """
    _ = mock_cocoindex_app
    hub_a = await _insert_hub(name="Hub A", code="hub-a", subdomain="hub-a")
    hub_b = await _insert_hub(name="Hub B", code="hub-b", subdomain="hub-b")
    await _assign_user_hub(user_id=editor_user["id"], hub_id=hub_a)
    content = _make_docx(tmp_path)
    doc_hub_b = await _upload(auth_client, admin_token, hub_b, "b.docx", content)

    r = await auth_client.delete(
        f"/api/documents/{doc_hub_b}",
        headers={"Authorization": f"Bearer {editor_token}"},
    )
    assert r.status_code == 403, r.text
    body = r.json()
    assert body["success"] is False
    assert body["error"]["code"] == "FORBIDDEN"

    # Document Hub B PHẢI vẫn tồn tại — cross-hub DELETE bị reject.
    still = await _count(
        "SELECT COUNT(*) FROM documents WHERE id = :id", {"id": doc_hub_b}
    )
    assert still == 1, "E4 VIOLATION — document Hub B bị editor Hub A xoá"


@pytest.mark.critical
@pytest.mark.integration
@pytest.mark.asyncio
async def test_hub_isolation_violation_audit_logged(
    auth_client: httpx.AsyncClient,
    admin_token: str,
    editor_token: str,
    editor_user: dict[str, str],
    app_with_auth: Any,
    tmp_path: Path,
    mock_cocoindex_app: MockCocoindexApp,
) -> None:
    """E4 — cross-hub reject → audit security.hub_isolation_violation logged.

    Audit là async batch flush — gọi flush_pending() force drain trước assert.
    Hub isolation bug = STOP, security review (PROJECT.md E4).
    """
    _ = mock_cocoindex_app
    hub_a = await _insert_hub(name="Hub A", code="hub-a", subdomain="hub-a")
    hub_b = await _insert_hub(name="Hub B", code="hub-b", subdomain="hub-b")
    await _assign_user_hub(user_id=editor_user["id"], hub_id=hub_a)
    content = _make_docx(tmp_path)
    doc_hub_b = await _upload(auth_client, admin_token, hub_b, "b.docx", content)

    r = await auth_client.delete(
        f"/api/documents/{doc_hub_b}",
        headers={"Authorization": f"Bearer {editor_token}"},
    )
    assert r.status_code == 403, r.text

    # Audit async batch flush — entry có thể đang nằm trong batch buffer của
    # audit_flush_loop (flush sau audit_flush_interval_seconds=2s) HOẶC còn
    # trong queue. Poll-with-timeout tới khi row xuất hiện trong DB (KHÔNG
    # sleep cứng cố định) — bao quát >2s flush interval. flush_pending() drain
    # phần còn trong queue; background loop flush phần đang buffer.
    from app.services.audit_service import flush_pending
    count = 0
    for _attempt in range(60):
        await flush_pending()
        count = await _count(
            "SELECT COUNT(*) FROM audit_logs "
            "WHERE action = 'security.hub_isolation_violation'",
            {},
        )
        if count >= 1:
            break
        await asyncio.sleep(0.15)
    assert count >= 1, (
        "E4 — audit security.hub_isolation_violation KHÔNG được ghi"
    )

    # Row mới nhất phải có user_id = editor + target_type = document.
    from app.db.session import get_engine
    engine = get_engine()
    async with engine.connect() as conn:
        row = (
            await conn.execute(
                text(
                    "SELECT user_id, target_type, target_id FROM audit_logs "
                    "WHERE action = 'security.hub_isolation_violation' "
                    "ORDER BY created_at DESC LIMIT 1"
                ),
            )
        ).fetchone()
    assert row is not None
    assert str(row[0]) == editor_user["id"], (
        f"audit user_id phải = editor.id ({editor_user['id']}), got {row[0]}"
    )
    assert row[1] == "document"
    assert str(row[2]) == doc_hub_b


@pytest.mark.critical
@pytest.mark.integration
@pytest.mark.asyncio
async def test_admin_can_delete_doc_any_hub(
    auth_client: httpx.AsyncClient,
    admin_token: str,
    app_with_auth: Any,
    tmp_path: Path,
    mock_cocoindex_app: MockCocoindexApp,
) -> None:
    """E4 — admin bypass hub isolation: DELETE document bất kỳ hub → 204.

    Admin cross-hub theo thiết kế quản trị (T-04-05-03 precedent preserved).
    Hub isolation bug = STOP, security review (PROJECT.md E4).
    """
    _ = mock_cocoindex_app
    hub_b = await _insert_hub(name="Hub B", code="hub-b", subdomain="hub-b")
    content = _make_docx(tmp_path)
    doc_hub_b = await _upload(auth_client, admin_token, hub_b, "b.docx", content)

    r = await auth_client.delete(
        f"/api/documents/{doc_hub_b}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 204, r.text

    gone = await _count(
        "SELECT COUNT(*) FROM documents WHERE id = :id", {"id": doc_hub_b}
    )
    assert gone == 0, "admin DELETE phải xoá document"


@pytest.mark.critical
@pytest.mark.integration
@pytest.mark.asyncio
async def test_editor_can_delete_doc_own_hub(
    auth_client: httpx.AsyncClient,
    admin_token: str,
    editor_token: str,
    editor_user: dict[str, str],
    app_with_auth: Any,
    tmp_path: Path,
    mock_cocoindex_app: MockCocoindexApp,
) -> None:
    """E4 — editor xoá document thuộc hub MÌNH được assign → 204 (isolation cho phép).

    Hub isolation bug = STOP, security review (PROJECT.md E4).
    """
    _ = mock_cocoindex_app
    hub_a = await _insert_hub(name="Hub A", code="hub-a", subdomain="hub-a")
    await _assign_user_hub(user_id=editor_user["id"], hub_id=hub_a)
    content = _make_docx(tmp_path)
    doc_hub_a = await _upload(auth_client, admin_token, hub_a, "a.docx", content)

    r = await auth_client.delete(
        f"/api/documents/{doc_hub_a}",
        headers={"Authorization": f"Bearer {editor_token}"},
    )
    assert r.status_code == 204, r.text

    gone = await _count(
        "SELECT COUNT(*) FROM documents WHERE id = :id", {"id": doc_hub_a}
    )
    assert gone == 0, "editor DELETE document hub mình phải thành công"


@pytest.mark.critical
@pytest.mark.integration
@pytest.mark.asyncio
async def test_viewer_cannot_delete_any_doc(
    auth_client: httpx.AsyncClient,
    admin_token: str,
    viewer_token: str,
    app_with_auth: Any,
    tmp_path: Path,
    mock_cocoindex_app: MockCocoindexApp,
) -> None:
    """E4 — viewer read-only: DELETE document → 403 FORBIDDEN (reject trước verify_hub_access).

    Hub isolation bug = STOP, security review (PROJECT.md E4).
    """
    _ = mock_cocoindex_app
    hub_a = await _insert_hub(name="Hub A", code="hub-a", subdomain="hub-a")
    content = _make_docx(tmp_path)
    doc_id = await _upload(auth_client, admin_token, hub_a, "a.docx", content)

    r = await auth_client.delete(
        f"/api/documents/{doc_id}",
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert r.status_code == 403, r.text
    assert r.json()["error"]["code"] == "FORBIDDEN"

    still = await _count(
        "SELECT COUNT(*) FROM documents WHERE id = :id", {"id": doc_id}
    )
    assert still == 1, "viewer KHÔNG được xoá document"


@pytest.mark.critical
@pytest.mark.integration
@pytest.mark.asyncio
async def test_verify_hub_access_unit(
    app_with_auth: Any,
) -> None:
    """E4 — verify_hub_access logic: editor cross-hub raise; admin bypass.

    Unit-style verify hub isolation helper trực tiếp (KHÔNG qua HTTP) — đảm bảo
    primitive enforce đúng. Hub isolation bug = STOP, security review (PROJECT.md E4).
    """
    _ = app_with_auth
    hub_a = str(uuid.uuid4())
    hub_b = str(uuid.uuid4())

    # editor cross-hub → raise HubIsolationError.
    with pytest.raises(HubIsolationError):
        verify_hub_access(
            role="editor",
            user_hub_ids=[hub_a],
            resource_hub_id=hub_b,
        )

    # admin → KHÔNG raise (bypass) kể cả hub_ids rỗng.
    verify_hub_access(role="admin", user_hub_ids=[], resource_hub_id=hub_b)

    # editor own-hub → KHÔNG raise.
    verify_hub_access(
        role="editor", user_hub_ids=[hub_a], resource_hub_id=hub_a
    )
