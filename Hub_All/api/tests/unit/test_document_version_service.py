"""Unit test document_version_service — Phase 5 Plan 05-02 VER-02.

8 test pure Python — mock AsyncSession.execute + patch enqueue_audit (KHÔNG hit Postgres/Redis).

Test cases (D-V3.1-Phase5-A/B/D/E/H LOCKED):
1. snapshot_inserts_row_atomic — dedupe query + MAX query + INSERT, version_number=1.
2. snapshot_dedupe_by_hash_reuses_path — D-V3.1-Phase5-A; mock dedupe match trả path cũ.
3. snapshot_audit_emits_create_action — D-V3.1-Phase5-H; AuditEntry action='document.version.create'.
4. snapshot_version_number_monotonic — MAX trả 3 → next = 4.
5. list_versions_returns_desc — SELECT DESC order verify.
6. get_version_with_chunks_returns_empty_chunks — D-V3.1-Phase5-B verify.
7. get_version_file_path_returns_path_object — Path object cho StreamingResponse.
8. compute_file_hash_sha256_hex_64 — SHA-256 hex 64-char exact match.

Carry forward patterns:
- `_make_session` AsyncMock factory (Plan 01-02 + 02-01 — test_role_helper.py + test_require_hub_admin_for.py).
- `with patch("app.services.document_version_service.enqueue_audit", ...)` — module-level patch.
- SimpleNamespace duck-type document object — KHÔNG full Document ORM.
"""
from __future__ import annotations

import hashlib
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.services.document_version_service import (
    ACTION_VERSION_CREATE,
    _compute_file_hash,
    get_version_file_path,
    get_version_with_chunks,
    list_versions,
    snapshot,
)


# === Helper: AsyncMock(AsyncSession) factory ===

def _make_session(
    *fetchone_returns: object,
    fetchall_returns: list | None = None,
    scalar_returns: list | None = None,
) -> AsyncMock:
    """Build AsyncMock(AsyncSession) trả về sequence fetchone + fetchall + scalar results.

    Carry forward pattern tests/unit/test_require_hub_admin_for.py + test_role_helper.py.

    Args:
        *fetchone_returns: Sequence row return cho mỗi session.execute().fetchone() call.
        fetchall_returns: List rows cho session.execute().fetchall() call (1 lần).
        scalar_returns: List scalar values cho session.execute().scalar() call.

    Example:
        >>> session = _make_session(None, (4,), ('uuid-1', datetime.now()))
        # 3 execute call: 1st fetchone None (no dedupe), 2nd scalar 4 (MAX), 3rd fetchone INSERT RETURNING
    """
    session = AsyncMock()
    result_mocks = []
    fetchone_iter = iter(fetchone_returns)
    fetchall_iter = iter([fetchall_returns] if fetchall_returns is not None else [])
    scalar_iter = iter(scalar_returns or [])

    # Determine how many execute calls expected (max of any iterator)
    expected_calls = max(
        len(fetchone_returns),
        1 if fetchall_returns is not None else 0,
        len(scalar_returns or []),
    )

    for _ in range(expected_calls + 5):  # Extra slack cho edge cases
        result = MagicMock()
        try:
            result.fetchone.return_value = next(fetchone_iter)
        except StopIteration:
            result.fetchone.return_value = None
        try:
            result.fetchall.return_value = next(fetchall_iter)
        except StopIteration:
            result.fetchall.return_value = []
        try:
            result.scalar.return_value = next(scalar_iter)
        except StopIteration:
            result.scalar.return_value = 0
        result_mocks.append(result)

    session.execute = AsyncMock(side_effect=result_mocks)
    return session


def _make_doc(file_path: str = "/tmp/test.docx", file_size: int = 1024) -> SimpleNamespace:
    """SimpleNamespace document duck-type — id, hub_id, filename, file_path, mime_type, file_size_bytes."""
    return SimpleNamespace(
        id=str(uuid4()),
        hub_id=str(uuid4()),
        filename="test.docx",
        file_path=file_path,
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        file_size_bytes=file_size,
    )


# === Test 1: snapshot inserts row atomic ===

@pytest.mark.asyncio
async def test_snapshot_inserts_row_atomic(tmp_path: Path) -> None:
    """snapshot(change_type='reupload') → dedupe query + MAX query + INSERT, version_number=1."""
    # Tạo real tempfile cho _compute_file_hash đọc bytes
    test_file = tmp_path / "test.docx"
    test_file.write_bytes(b"document content v1")
    doc = _make_doc(file_path=str(test_file))

    # Mock session — call order trong snapshot():
    #   #1 dedupe SELECT → fetchone None (no match)
    #   #2 MAX SELECT → scalar 0
    #   #3 INSERT RETURNING → fetchone (uuid, datetime)
    #   #4 _enforce_retention CTE → fetchall []
    # Factory build mock theo thứ tự — fetchone_returns iter advance per-mock,
    # placeholder None ở vị trí #2 để fetchone iter align với INSERT ở #3.
    inserted_id = uuid4()
    created_at = datetime.now(timezone.utc)
    session = _make_session(
        None,                           # mock #1 dedupe fetchone None
        None,                           # mock #2 placeholder (MAX dùng scalar, fetchone unused)
        (inserted_id, created_at),      # mock #3 INSERT RETURNING fetchone
        fetchall_returns=[],            # _enforce_retention DELETE RETURNING empty
        scalar_returns=[0],             # MAX returns 0 (mock #2)
    )

    with patch("app.services.document_version_service.enqueue_audit"):
        result = await snapshot(
            session=session,
            document=doc,
            change_type="reupload",
            actor_user_id=str(uuid4()),
            actor_role="admin",
            actor_hub_id=None,
        )

    assert session.execute.call_count >= 3, (
        f"Expect >= 3 execute calls (dedupe + MAX + INSERT + retention), got {session.execute.call_count}"
    )
    assert result["version_number"] == 1
    assert result["is_original"] is True
    assert result["change_type"] == "reupload"
    assert result["file_hash"] == hashlib.sha256(b"document content v1").hexdigest()
    assert result["document_id"] == doc.id


# === Test 2: snapshot dedupe by hash reuses path ===

@pytest.mark.asyncio
async def test_snapshot_dedupe_by_hash_reuses_path(tmp_path: Path) -> None:
    """D-V3.1-Phase5-A: existing version cùng file_hash → reference path cũ."""
    test_file = tmp_path / "test.docx"
    test_file.write_bytes(b"identical content")
    doc = _make_doc(file_path=str(test_file))

    old_path = "/old/storage/abc-uuid.docx"
    inserted_id = uuid4()
    created_at = datetime.now(timezone.utc)
    # Mock: #1 dedupe HIT (old_path,) | #2 MAX scalar 0 placeholder fetchone None
    # | #3 INSERT RETURNING (uuid, datetime) | #4 retention fetchall []
    session = _make_session(
        (old_path,),                    # mock #1 dedupe fetchone HIT
        None,                           # mock #2 placeholder (MAX dùng scalar)
        (inserted_id, created_at),      # mock #3 INSERT RETURNING fetchone
        fetchall_returns=[],
        scalar_returns=[0],
    )

    with patch("app.services.document_version_service.enqueue_audit"):
        result = await snapshot(
            session=session,
            document=doc,
            change_type="reupload",
        )

    assert result["file_path"] == old_path, (
        f"Dedupe should reference old path, got {result['file_path']!r}"
    )


# === Test 3: snapshot audit emits create action with metadata nest ===

@pytest.mark.asyncio
async def test_snapshot_audit_emits_create_action(tmp_path: Path) -> None:
    """D-V3.1-Phase5-H: enqueue_audit action='document.version.create' + payload nest."""
    test_file = tmp_path / "test.docx"
    test_file.write_bytes(b"audit test content")
    doc = _make_doc(file_path=str(test_file))

    inserted_id = uuid4()
    created_at = datetime.now(timezone.utc)
    # Mock align: #1 dedupe None | #2 MAX placeholder | #3 INSERT RETURNING | #4 retention []
    session = _make_session(
        None,                           # mock #1 dedupe
        None,                           # mock #2 MAX placeholder
        (inserted_id, created_at),      # mock #3 INSERT RETURNING
        fetchall_returns=[],
        scalar_returns=[0],
    )

    hub_id = str(uuid4())
    actor_user_id = str(uuid4())

    with patch("app.services.document_version_service.enqueue_audit") as mock_enqueue:
        await snapshot(
            session=session,
            document=doc,
            change_type="reupload",
            actor_user_id=actor_user_id,
            actor_role="hub_admin",
            actor_hub_id=hub_id,
        )

    assert mock_enqueue.call_count == 1, "enqueue_audit phải gọi 1 lần"
    entry = mock_enqueue.call_args.args[0]
    assert entry.action == ACTION_VERSION_CREATE
    assert entry.action == "document.version.create"
    assert entry.payload["actor_role"] == "hub_admin"
    assert entry.payload["actor_hub_id"] == hub_id
    assert entry.payload["document_id"] == doc.id
    assert entry.payload["version_number"] == 1
    assert entry.payload["change_type"] == "reupload"
    assert entry.user_id == actor_user_id
    assert entry.target_type == "document_version"


# === Test 4: snapshot version_number monotonic increment ===

@pytest.mark.asyncio
async def test_snapshot_version_number_monotonic(tmp_path: Path) -> None:
    """SELECT MAX(version_number) trả 3 → next version = 4 + is_original=False."""
    test_file = tmp_path / "test.docx"
    test_file.write_bytes(b"v4 content")
    doc = _make_doc(file_path=str(test_file))

    inserted_id = uuid4()
    created_at = datetime.now(timezone.utc)
    # MAX trả 3 → next = 4
    # Mock align: #1 dedupe None | #2 MAX scalar=3 | #3 INSERT RETURNING | #4 retention []
    # scalar_returns iter advance per-mock — placeholder 0 ở #1 để align MAX=3 vào mock #2.
    session = _make_session(
        None,                           # mock #1 dedupe
        None,                           # mock #2 MAX placeholder fetchone
        (inserted_id, created_at),      # mock #3 INSERT RETURNING
        fetchall_returns=[],
        scalar_returns=[0, 3],          # mock #1 scalar 0 (unused), mock #2 scalar 3 (MAX)
    )

    with patch("app.services.document_version_service.enqueue_audit"):
        result = await snapshot(
            session=session,
            document=doc,
            change_type="content_edit",
        )

    assert result["version_number"] == 4
    assert result["is_original"] is False


# === Test 5: list_versions returns DESC order ===

@pytest.mark.asyncio
async def test_list_versions_returns_desc() -> None:
    """SELECT * ORDER BY version_number DESC; trả 3 row order [3, 2, 1]."""
    doc_id = str(uuid4())
    now = datetime.now(timezone.utc)
    rows = [
        (uuid4(), doc_id, 3, False, "v3.docx", "docx", 3000, "/path/v3", "hash3", None, 5, "reupload", None, None, now),
        (uuid4(), doc_id, 2, False, "v2.docx", "docx", 2000, "/path/v2", "hash2", None, 4, "reextract", None, None, now),
        (uuid4(), doc_id, 1, True, "v1.docx", "docx", 1000, "/path/v1", "hash1", None, 3, "reupload", None, None, now),
    ]
    session = _make_session(fetchall_returns=rows)

    result = await list_versions(session, doc_id)

    assert len(result) == 3
    assert [r["version_number"] for r in result] == [3, 2, 1]
    assert result[2]["is_original"] is True
    assert result[0]["version_number"] == 3
    assert result[0]["change_type"] == "reupload"


# === Test 6: get_version_with_chunks returns empty chunks array ===

@pytest.mark.asyncio
async def test_get_version_with_chunks_returns_empty_chunks() -> None:
    """D-V3.1-Phase5-B LOCKED: chunks = [] empty array (FE typecheck happy)."""
    doc_id = str(uuid4())
    version_id = str(uuid4())
    now = datetime.now(timezone.utc)
    row = (uuid4(), doc_id, 1, True, "v1.docx", "docx", 1000, "/path/v1", "hash1", None, 3, "reupload", None, None, now)
    session = _make_session(row)

    version_dict, chunks = await get_version_with_chunks(session, doc_id, version_id)

    assert version_dict is not None
    assert version_dict["version_number"] == 1
    assert chunks == [], f"D-V3.1-Phase5-B: chunks phải là [], got {chunks!r}"
    assert isinstance(chunks, list)


# === Test 7: get_version_file_path returns Path object ===

@pytest.mark.asyncio
async def test_get_version_file_path_returns_path_object() -> None:
    """SELECT file_path → return Path object cho StreamingResponse Plan 05-03."""
    doc_id = str(uuid4())
    version_id = str(uuid4())
    session = _make_session(("/tmp/storage/abc.docx",))

    result = await get_version_file_path(session, doc_id, version_id)

    assert result == Path("/tmp/storage/abc.docx")
    assert isinstance(result, Path)


# === Test 8: _compute_file_hash returns SHA-256 hex 64-char ===

def test_compute_file_hash_returns_sha256_hex_64() -> None:
    """D-V3.1-Phase5-A: SHA-256 hex 64-char exact match hashlib stdlib."""
    with tempfile.NamedTemporaryFile(delete=False) as f:
        f.write(b"hello")
        tmp_path = Path(f.name)

    try:
        result = _compute_file_hash(tmp_path)
        expected = hashlib.sha256(b"hello").hexdigest()

        assert len(result) == 64, f"SHA-256 hex phải 64 char, got {len(result)}"
        assert result == expected
        # Verify hex chars only (0-9, a-f)
        assert all(c in "0123456789abcdef" for c in result)
    finally:
        tmp_path.unlink(missing_ok=True)
