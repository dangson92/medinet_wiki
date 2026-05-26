"""Unit test document_versions router — Phase 5 Plan 05-03 VER-03 + VER-04.

10 unit test cover 4 endpoint × happy path + RBAC reject + envelope shape + audit:
1. list_versions_returns_envelope_with_versions_array
2. list_versions_404_when_document_missing
3. get_detail_returns_chunks_empty_array (D-V3.1-Phase5-B verify)
4. get_detail_404_when_version_missing
5. get_file_streaming_response_with_attachment_header
6. get_file_404_when_path_missing_on_disk
7. restore_calls_service_with_actor_metadata_hub_admin
8. restore_super_admin_actor_metadata_null_hub
9. restore_403_when_assert_hub_admin_raises (viewer + cross-hub)
10. restore_400_when_document_hub_id_missing

Test isolation: call router handler functions DIRECTLY (KHÔNG TestClient ASGI overhead) —
mock Depends args + AsyncSession + service module functions.

Pattern: từ Plan 02-01 test_require_hub_admin_for.py + Plan 05-02 test_document_version_service.py.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.routers.document_versions import (
    _resolve_document_hub_id,  # noqa: F401 — re-export verify acceptance criterion
    download_document_version_file,
    get_document_version_detail,
    list_document_versions,
    restore_document_to_version,
)


def _make_user(role: str = "admin", user_id: object = None) -> SimpleNamespace:
    """SimpleNamespace User duck-type — .id + .role."""
    return SimpleNamespace(id=user_id or uuid4(), role=role)


def _make_session_returning(*fetchone_returns: object) -> AsyncMock:
    """AsyncMock(AsyncSession) trả sequence fetchone results.

    Mỗi item là row return cho lần `await session.execute(...)` tiếp theo.
    None = fetchone trả None (no row); tuple = row tồn tại.
    """
    session = AsyncMock()
    result_mocks = []
    for fetchone_value in fetchone_returns:
        result = MagicMock()
        result.fetchone.return_value = fetchone_value
        result_mocks.append(result)
    session.execute = AsyncMock(side_effect=result_mocks)
    return session


def _make_request_with_app_state(cocoindex_app: object = None) -> SimpleNamespace:
    """SimpleNamespace Request — .app.state.cocoindex_app."""
    state = SimpleNamespace(cocoindex_app=cocoindex_app)
    app = SimpleNamespace(state=state)
    return SimpleNamespace(app=app)


# === Test 1: list_versions happy path envelope ===

@pytest.mark.asyncio
async def test_list_versions_returns_envelope_with_versions_array() -> None:
    """GET /versions → 200 envelope {success: true, data: {versions: [3 dict]}}."""
    doc_id = uuid4()
    db = _make_session_returning((doc_id, str(uuid4())))  # _resolve_document_hub_id

    fake_versions = [
        {"id": str(uuid4()), "version_number": 3, "change_type": "reupload"},
        {"id": str(uuid4()), "version_number": 2, "change_type": "reextract"},
        {"id": str(uuid4()), "version_number": 1, "change_type": "reupload"},
    ]

    with patch(
        "app.routers.document_versions.document_version_service.list_versions",
        new=AsyncMock(return_value=fake_versions),
    ):
        result = await list_document_versions(
            document_id=doc_id,
            user=_make_user(),
            db=db,
        )

    assert result["success"] is True
    assert result["data"]["versions"] == fake_versions
    assert result["error"] is None
    assert result["meta"] is None


# === Test 2: list_versions 404 when document missing ===

@pytest.mark.asyncio
async def test_list_versions_404_when_document_missing() -> None:
    """_resolve_document_hub_id raise 404 → endpoint propagate."""
    doc_id = uuid4()
    db = _make_session_returning(None)  # fetchone None → 404

    with pytest.raises(HTTPException) as exc_info:
        await list_document_versions(
            document_id=doc_id,
            user=_make_user(),
            db=db,
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail["code"] == "DOCUMENT_NOT_FOUND"


# === Test 3: get_detail returns chunks empty array (D-V3.1-Phase5-B) ===

@pytest.mark.asyncio
async def test_get_detail_returns_chunks_empty_array() -> None:
    """D-V3.1-Phase5-B LOCKED: GET /versions/{vid} envelope data.chunks == []."""
    doc_id = uuid4()
    version_id = uuid4()
    db = _make_session_returning((doc_id, str(uuid4())))

    fake_version = {"id": str(version_id), "version_number": 1, "name": "v1.docx"}

    with patch(
        "app.routers.document_versions.document_version_service.get_version_with_chunks",
        new=AsyncMock(return_value=(fake_version, [])),
    ):
        result = await get_document_version_detail(
            document_id=doc_id,
            version_id=version_id,
            user=_make_user(),
            db=db,
        )

    assert result["success"] is True
    assert result["data"]["version"] == fake_version
    assert result["data"]["chunks"] == [], "D-V3.1-Phase5-B: chunks phải là [] empty"
    assert isinstance(result["data"]["chunks"], list)


# === Test 4: get_detail 404 when version missing ===

@pytest.mark.asyncio
async def test_get_detail_404_when_version_missing() -> None:
    """service trả (None, []) → 404 VERSION_NOT_FOUND."""
    doc_id = uuid4()
    version_id = uuid4()
    db = _make_session_returning((doc_id, str(uuid4())))

    with patch(
        "app.routers.document_versions.document_version_service.get_version_with_chunks",
        new=AsyncMock(return_value=(None, [])),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await get_document_version_detail(
                document_id=doc_id,
                version_id=version_id,
                user=_make_user(),
                db=db,
            )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail["code"] == "VERSION_NOT_FOUND"


# === Test 5: get_file streaming response with attachment header ===

@pytest.mark.asyncio
async def test_get_file_streaming_response_with_attachment_header(tmp_path: Path) -> None:
    """GET /versions/{vid}/file → StreamingResponse + Content-Disposition attachment."""
    doc_id = uuid4()
    version_id = uuid4()
    db = _make_session_returning((doc_id, str(uuid4())))

    test_file = tmp_path / "v3_test.docx"
    test_file.write_bytes(b"file content for streaming")

    fake_version = {
        "id": str(version_id),
        "version_number": 3,
        "name": "test.docx",
        "file_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }

    with patch(
        "app.routers.document_versions.document_version_service.get_version_with_chunks",
        new=AsyncMock(return_value=(fake_version, [])),
    ), patch(
        "app.routers.document_versions.document_version_service.get_version_file_path",
        new=AsyncMock(return_value=test_file),
    ):
        result = await download_document_version_file(
            document_id=doc_id,
            version_id=version_id,
            user=_make_user(),
            db=db,
        )

    # StreamingResponse import check
    from fastapi.responses import StreamingResponse
    assert isinstance(result, StreamingResponse)
    assert result.media_type == fake_version["file_type"]
    assert "attachment" in result.headers["Content-Disposition"]
    # Filename v3_test.docx ASCII-safe → percent-encode no-op (RFC 6266 filename*=UTF-8'')
    assert "v3_test.docx" in result.headers["Content-Disposition"]


# === Test 6: get_file 404 when path missing on disk ===

@pytest.mark.asyncio
async def test_get_file_404_when_path_missing_on_disk() -> None:
    """get_version_file_path trả Path KHÔNG tồn tại → 404 VERSION_FILE_MISSING."""
    doc_id = uuid4()
    version_id = uuid4()
    db = _make_session_returning((doc_id, str(uuid4())))

    fake_version = {"id": str(version_id), "version_number": 1, "name": "v1.docx", "file_type": "docx"}
    missing_path = Path("/nonexistent/path/v1.docx")

    with patch(
        "app.routers.document_versions.document_version_service.get_version_with_chunks",
        new=AsyncMock(return_value=(fake_version, [])),
    ), patch(
        "app.routers.document_versions.document_version_service.get_version_file_path",
        new=AsyncMock(return_value=missing_path),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await download_document_version_file(
                document_id=doc_id,
                version_id=version_id,
                user=_make_user(),
                db=db,
            )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail["code"] == "VERSION_FILE_MISSING"


# === Test 7: restore calls service with actor metadata (hub_admin) ===

@pytest.mark.asyncio
async def test_restore_calls_service_with_actor_metadata_hub_admin() -> None:
    """POST /restore user.role='hub_admin' → service truyền actor_role='hub_admin' + actor_hub_id=doc.hub_id."""
    doc_id = uuid4()
    version_id = uuid4()
    hub_id = str(uuid4())
    db = _make_session_returning((doc_id, hub_id))

    user = _make_user(role="hub_admin")
    request = _make_request_with_app_state(cocoindex_app=None)

    refreshed = {"id": str(doc_id), "hub_id": hub_id, "filename": "refreshed.docx"}

    with patch(
        "app.routers.document_versions.assert_hub_admin_for",
        new=AsyncMock(),  # PASS — KHÔNG raise
    ), patch(
        "app.routers.document_versions.document_version_service.restore_to_version",
        new=AsyncMock(return_value=refreshed),
    ) as mock_restore:
        result = await restore_document_to_version(
            document_id=doc_id,
            version_id=version_id,
            request=request,
            user=user,
            db=db,
        )

    assert result["success"] is True
    assert result["data"]["filename"] == "refreshed.docx"
    mock_restore.assert_awaited_once()
    call_kwargs = mock_restore.await_args.kwargs
    assert call_kwargs["actor_role"] == "hub_admin"
    assert call_kwargs["actor_hub_id"] == hub_id
    assert call_kwargs["actor_user_id"] == str(user.id)
    assert call_kwargs["document_id"] == str(doc_id)
    assert call_kwargs["version_id"] == str(version_id)


# === Test 8: restore super admin actor metadata null hub ===

@pytest.mark.asyncio
async def test_restore_super_admin_actor_metadata_null_hub() -> None:
    """POST /restore user.role='admin' → service truyền actor_role='admin' + actor_hub_id=None."""
    doc_id = uuid4()
    version_id = uuid4()
    hub_id = str(uuid4())
    db = _make_session_returning((doc_id, hub_id))

    user = _make_user(role="admin")
    request = _make_request_with_app_state(cocoindex_app=None)

    refreshed = {"id": str(doc_id), "hub_id": hub_id, "filename": "refreshed.docx"}

    with patch(
        "app.routers.document_versions.assert_hub_admin_for",
        new=AsyncMock(),
    ), patch(
        "app.routers.document_versions.document_version_service.restore_to_version",
        new=AsyncMock(return_value=refreshed),
    ) as mock_restore:
        await restore_document_to_version(
            document_id=doc_id,
            version_id=version_id,
            request=request,
            user=user,
            db=db,
        )

    call_kwargs = mock_restore.await_args.kwargs
    assert call_kwargs["actor_role"] == "admin"
    assert call_kwargs["actor_hub_id"] is None, "Super admin → actor_hub_id phải None"


# === Test 9: restore 403 when assert_hub_admin raises ===

@pytest.mark.asyncio
async def test_restore_403_when_assert_hub_admin_raises() -> None:
    """assert_hub_admin_for raise 403 HUB_ADMIN_REQUIRED → endpoint propagate."""
    doc_id = uuid4()
    version_id = uuid4()
    hub_id = str(uuid4())
    db = _make_session_returning((doc_id, hub_id))

    user = _make_user(role="viewer")
    request = _make_request_with_app_state()

    with patch(
        "app.routers.document_versions.assert_hub_admin_for",
        new=AsyncMock(side_effect=HTTPException(
            status_code=403,
            detail={"code": "HUB_ADMIN_REQUIRED", "message": "Yêu cầu hub_admin"},
        )),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await restore_document_to_version(
                document_id=doc_id,
                version_id=version_id,
                request=request,
                user=user,
                db=db,
            )

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["code"] == "HUB_ADMIN_REQUIRED"


# === Test 10: restore 400 when document hub_id missing ===

@pytest.mark.asyncio
async def test_restore_400_when_document_hub_id_missing() -> None:
    """_resolve_document_hub_id trả (doc_id, None) → 400 DOCUMENT_HUB_MISSING."""
    doc_id = uuid4()
    version_id = uuid4()
    # _resolve returns row với hub_id=None (legacy orphan document)
    db = _make_session_returning((doc_id, None))

    user = _make_user(role="hub_admin")
    request = _make_request_with_app_state()

    with pytest.raises(HTTPException) as exc_info:
        await restore_document_to_version(
            document_id=doc_id,
            version_id=version_id,
            request=request,
            user=user,
            db=db,
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["code"] == "DOCUMENT_HUB_MISSING"
