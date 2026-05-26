"""document_version_service.py — Phase 5 Plan 05-02 VER-02 service layer.

5 public API:
- snapshot(*, session, document, change_type, change_note=None, actor_user_id=None,
           actor_role='admin', actor_hub_id=None) -> dict
- restore_to_version(*, session, document_id, version_id, actor_user_id,
                     actor_role='admin', actor_hub_id=None) -> dict
- list_versions(session, document_id) -> list[dict]
- get_version_with_chunks(session, document_id, version_id) -> tuple[dict, list]
- get_version_file_path(session, document_id, version_id) -> Path

2 private helper:
- _compute_file_hash(path: Path) -> str  # SHA-256 hex 64-char
- _enforce_retention(session, document_id) -> list[str]  # deleted file paths

Decisions LOCKED (05-CONTEXT.md):
- D-V3.1-Phase5-A: Dedupe-by-hash trong cùng document_id (reupload exact same file
  → reference path cũ; nếu hash mới → reference document.file_path hiện tại).
- D-V3.1-Phase5-B: chunks per-version NO snapshot — get_version_with_chunks trả
  `(version, [])` empty array (FE typecheck happy).
- D-V3.1-Phase5-D: Restore append-only — snapshot(change_type='restore') TRƯỚC
  khi UPDATE documents.
- D-V3.1-Phase5-E: Retention '3 gốc + 2 gần nhất' enforce BE write-time CTE.
- D-V3.1-Phase5-H: Audit action codes 'document.version.create' + 'document.version.restore'.
- D-V3.1-Phase5-I: Restore re-extract SYNC block endpoint (< 5s small DOCX).

Carry forward:
- audit_service.build_audit_payload + enqueue_audit (Plan 02-04 v3.1).
- FileStore.save/load/delete (M2).
- Raw SQL text() pattern Plan 01-02 v3.1 (CTE window function complex).
"""
from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.audit_service import (
    AuditEntry,
    build_audit_payload,
    enqueue_audit,
)
from app.services.file_store import FileStore

logger = logging.getLogger(__name__)

# Action codes — D-V3.1-Phase5-H LOCKED.
# NOTE: AUDIT_ACTIONS frozenset trong audit_service.py KHÔNG include 2 action mới;
# enqueue_audit KHÔNG enforce hard (caller responsibility), nhưng để forensic
# query có thể chuẩn hóa qua hằng số.
ACTION_VERSION_CREATE = "document.version.create"
ACTION_VERSION_RESTORE = "document.version.restore"

# Retention policy hardcode (D-V3.1-Phase5-E LOCKED).
# Per-hub override defer v4.0 system_settings.
RETENTION_KEEP_FIRST_N = 3   # 3 gốc đầu
RETENTION_KEEP_LAST_N = 2    # 2 gần nhất


# === Helper: SHA-256 file hash ===

def _compute_file_hash(path: Path) -> str:
    """SHA-256 hex 64-char dedupe key (D-V3.1-Phase5-A LOCKED).

    Pattern khác chunks.content_hash BYTEA (M2 model layer) — VER table dùng
    TEXT hex 64-char cho query-able simple equality `WHERE file_hash = $1`.

    Args:
        path: Path tới file binary (FileStore UUID path).

    Returns:
        SHA-256 hex string len 64.

    Raises:
        FileNotFoundError nếu path KHÔNG tồn tại (caller defensive check).
    """
    return hashlib.sha256(path.read_bytes()).hexdigest()


# === Helper: retention cleanup CTE ===

async def _enforce_retention(
    session: AsyncSession,
    document_id: str,
) -> list[str]:
    """Retention '3 gốc + 2 gần nhất' — DELETE middle versions + return deleted file_path list.

    D-V3.1-Phase5-E LOCKED — BE write-time enforce (DEVIATION từ ROADMAP GA-V3.1-G
    "FE filter client-side" per FE codebase audit: DocumentVersionHistory.tsx line
    158 `versions.map(...)` KHÔNG có client-side filter; hint line 146 "Lưu tối đa
    5 phiên bản" text-only).

    SQL CTE window function (raw SQL via sqlalchemy.text — KHÔNG SQLAlchemy ORM
    vì complexity DELETE + RETURNING + ROW_NUMBER):
        WITH ranked AS (
            SELECT id, version_number, file_path,
                   ROW_NUMBER() OVER (PARTITION BY document_id ORDER BY version_number) AS asc_rank,
                   ROW_NUMBER() OVER (PARTITION BY document_id ORDER BY version_number DESC) AS desc_rank
            FROM document_versions
            WHERE document_id = :doc_id
        )
        DELETE FROM document_versions
        WHERE id IN (
            SELECT id FROM ranked
            WHERE asc_rank > :keep_first AND desc_rank > :keep_last
        )
        RETURNING file_path;

    Sau DELETE, return list file_path. Caller (snapshot) check reference count
    cho mỗi path: chỉ FileStore.delete khi `SELECT COUNT(*) WHERE file_path = $1 == 0`.

    Args:
        session: AsyncSession đang mở (caller manage transaction).
        document_id: UUID str của document parent.

    Returns:
        List file_path string của row vừa DELETE (có thể duplicate nếu 2 row reference
        cùng path qua dedupe). Caller dedupe + check ref count trước FileStore.delete.
    """
    result = await session.execute(
        text(
            """
            WITH ranked AS (
                SELECT id, version_number, file_path,
                       ROW_NUMBER() OVER (PARTITION BY document_id ORDER BY version_number) AS asc_rank,
                       ROW_NUMBER() OVER (PARTITION BY document_id ORDER BY version_number DESC) AS desc_rank
                FROM document_versions
                WHERE document_id = :doc_id
            )
            DELETE FROM document_versions
            WHERE id IN (
                SELECT id FROM ranked
                WHERE asc_rank > :keep_first AND desc_rank > :keep_last
            )
            RETURNING file_path
            """
        ),
        {
            "doc_id": str(document_id),
            "keep_first": RETENTION_KEEP_FIRST_N,
            "keep_last": RETENTION_KEEP_LAST_N,
        },
    )
    rows = result.fetchall()
    return [row[0] for row in rows]


async def _cleanup_orphan_files(
    session: AsyncSession,
    deleted_paths: list[str],
) -> int:
    """Sau retention prune, FileStore.delete file vật lý chỉ khi reference count = 0.

    Cross-version dedupe safe (D-V3.1-Phase5-A): nếu file_path còn reference từ
    version khác (v1 vẫn còn) → KHÔNG delete file vật lý.

    Args:
        session: AsyncSession đang mở.
        deleted_paths: list file_path string từ _enforce_retention return.

    Returns:
        Số file vật lý đã DELETE qua FileStore.delete.
    """
    if not deleted_paths:
        return 0

    store = FileStore()
    deleted_count = 0
    seen: set[str] = set()
    for path_str in deleted_paths:
        if path_str in seen:
            continue
        seen.add(path_str)

        # Check reference count còn lại
        result = await session.execute(
            text(
                "SELECT COUNT(*) FROM document_versions WHERE file_path = :path"
            ),
            {"path": path_str},
        )
        ref_count = result.scalar() or 0

        if ref_count == 0:
            try:
                if store.delete(Path(path_str)):
                    deleted_count += 1
            except OSError as e:
                # File system error — log + continue (idempotent FileStore.delete return False)
                logger.warning(
                    "file_cleanup_failed: path=%s err=%s", path_str, e
                )
    return deleted_count


# === Public API: snapshot ===

async def snapshot(
    *,
    session: AsyncSession,
    document: Any,  # duck-type: .id, .hub_id, .filename, .file_path, .mime_type, .file_size_bytes
    change_type: str,
    change_note: str | None = None,
    actor_user_id: str | None = None,
    actor_role: str = "admin",
    actor_hub_id: str | None = None,
) -> dict[str, Any]:
    """Tạo version snapshot cho document atomic + audit emit + retention cleanup.

    D-V3.1-Phase5-A LOCKED dedupe-by-hash:
    - Compute SHA-256 hash từ document.file_path hiện tại.
    - Query existing versions cùng (document_id, file_hash) → nếu match, reference
      file_path cũ (KHÔNG FileStore.save mới); nếu KHÔNG match → reference
      document.file_path (assume caller đã FileStore.save cho file mới trước khi
      gọi snapshot — Plan 05-03 router responsibility).

    D-V3.1-Phase5-E LOCKED retention: sau INSERT, gọi _enforce_retention CTE
    + _cleanup_orphan_files cùng transaction.

    D-V3.1-Phase5-H LOCKED audit: enqueue_audit action='document.version.create'
    payload nest actor_role + actor_hub_id + document_id + version_number + change_type.

    Args:
        session: AsyncSession đang mở (caller transaction).
        document: Document object duck-type với attributes id, hub_id, filename,
            file_path, mime_type, file_size_bytes (+ optional extractor, chunk_count).
        change_type: 'reupload' | 'reextract' | 'content_edit' | 'restore' (CHECK enforce DB).
        change_note: Optional human note.
        actor_user_id: UUID str của user trigger (None nếu system event — rare).
        actor_role: 'admin' (super) | 'hub_admin' — for audit forensic.
        actor_hub_id: None nếu super; hub_id nếu hub_admin.

    Returns:
        dict (DocumentVersionAPI shape) — id, document_id, version_number, ...

    Raises:
        ValueError nếu change_type invalid (CHECK constraint backup ở DB layer).
        FileNotFoundError nếu document.file_path KHÔNG tồn tại.
    """
    if change_type not in ("reupload", "reextract", "content_edit", "restore"):
        raise ValueError(
            f"Invalid change_type {change_type!r}; expected reupload|reextract|content_edit|restore"
        )

    # 1) Compute file hash từ current document.file_path
    current_path = Path(document.file_path)
    file_hash = _compute_file_hash(current_path)

    # 2) Dedupe-by-hash check (D-V3.1-Phase5-A) — query existing versions cùng (doc_id, hash)
    dedupe_result = await session.execute(
        text(
            "SELECT file_path FROM document_versions "
            "WHERE document_id = :doc_id AND file_hash = :hash "
            "LIMIT 1"
        ),
        {"doc_id": str(document.id), "hash": file_hash},
    )
    existing_path_row = dedupe_result.fetchone()
    if existing_path_row:
        # Reference path cũ — KHÔNG FileStore.save mới (Plan 05-03 router check trước
        # khi save nếu là reupload preview-confirm flow; snapshot reference path
        # mà document.file_path hiện tại đang trỏ tới).
        snapshot_file_path = existing_path_row[0]
    else:
        # Hash mới — reference document.file_path hiện tại (Plan 05-03 đã FileStore.save).
        snapshot_file_path = str(current_path)

    # 3) Derive version_number monotonic — SELECT MAX + 1
    max_result = await session.execute(
        text(
            "SELECT COALESCE(MAX(version_number), 0) FROM document_versions "
            "WHERE document_id = :doc_id"
        ),
        {"doc_id": str(document.id)},
    )
    next_version_number = (max_result.scalar() or 0) + 1
    is_original = (next_version_number == 1)

    # 4) INSERT version row
    extractor_used = getattr(document, "extractor", None) or getattr(document, "extractor_used", None)
    chunk_count = getattr(document, "chunk_count", 0) or 0
    name = getattr(document, "filename", None) or getattr(document, "name", "unknown")
    file_type = getattr(document, "mime_type", None) or getattr(document, "file_type", "application/octet-stream")
    file_size = getattr(document, "file_size_bytes", None) or getattr(document, "file_size", 0)

    insert_result = await session.execute(
        text(
            """
            INSERT INTO document_versions (
                document_id, version_number, is_original,
                name, file_type, file_size, file_path, file_hash,
                extractor_used, chunk_count, change_type, change_note, created_by
            ) VALUES (
                :doc_id, :version_number, :is_original,
                :name, :file_type, :file_size, :file_path, :file_hash,
                :extractor_used, :chunk_count, :change_type, :change_note, :created_by
            )
            RETURNING id, created_at
            """
        ),
        {
            "doc_id": str(document.id),
            "version_number": next_version_number,
            "is_original": is_original,
            "name": name,
            "file_type": file_type,
            "file_size": int(file_size),
            "file_path": snapshot_file_path,
            "file_hash": file_hash,
            "extractor_used": extractor_used,
            "chunk_count": int(chunk_count),
            "change_type": change_type,
            "change_note": change_note,
            "created_by": str(actor_user_id) if actor_user_id else None,
        },
    )
    inserted = insert_result.fetchone()
    version_id = str(inserted[0])
    created_at = inserted[1]

    # 5) Retention cleanup CTE cùng transaction (D-V3.1-Phase5-E)
    deleted_paths = await _enforce_retention(session, str(document.id))
    if deleted_paths:
        await _cleanup_orphan_files(session, deleted_paths)
        logger.info(
            "document_version_retention_prune: doc_id=%s deleted_versions=%d",
            document.id, len(deleted_paths),
        )

    # 6) Audit emit (D-V3.1-Phase5-H)
    payload = build_audit_payload(
        actor_role=actor_role,
        actor_hub_id=actor_hub_id,
        extra={
            "document_id": str(document.id),
            "version_number": next_version_number,
            "change_type": change_type,
        },
    )
    enqueue_audit(AuditEntry(
        action=ACTION_VERSION_CREATE,
        user_id=str(actor_user_id) if actor_user_id else None,
        target_type="document_version",
        target_id=version_id,
        hub_id=str(getattr(document, "hub_id", None)) if getattr(document, "hub_id", None) else None,
        payload=payload,
    ))

    # 7) Return DocumentVersionAPI shape dict
    return {
        "id": version_id,
        "document_id": str(document.id),
        "version_number": next_version_number,
        "is_original": is_original,
        "name": name,
        "file_type": file_type,
        "file_size": int(file_size),
        "file_path": snapshot_file_path,
        "file_hash": file_hash,
        "extractor_used": extractor_used,
        "chunk_count": int(chunk_count),
        "change_type": change_type,
        "change_note": change_note,
        "created_by": str(actor_user_id) if actor_user_id else None,
        "created_at": created_at.isoformat() if created_at else None,
    }


# === Public API: list_versions ===

async def list_versions(
    session: AsyncSession,
    document_id: str,
) -> list[dict[str, Any]]:
    """SELECT * FROM document_versions WHERE document_id ORDER BY version_number DESC.

    Trả ≤ 5 row sau retention prune (D-V3.1-Phase5-E LOCKED). KHÔNG paginate.
    """
    result = await session.execute(
        text(
            """
            SELECT id, document_id, version_number, is_original,
                   name, file_type, file_size, file_path, file_hash,
                   extractor_used, chunk_count, change_type, change_note,
                   created_by, created_at
            FROM document_versions
            WHERE document_id = :doc_id
            ORDER BY version_number DESC
            """
        ),
        {"doc_id": str(document_id)},
    )
    rows = result.fetchall()
    return [_row_to_dict(row) for row in rows]


# === Public API: get_version_with_chunks ===

async def get_version_with_chunks(
    session: AsyncSession,
    document_id: str,
    version_id: str,
) -> tuple[dict[str, Any] | None, list[Any]]:
    """SELECT 1 version + return (dict, []) — chunks empty (D-V3.1-Phase5-B LOCKED).

    Returns:
        (version_dict | None nếu KHÔNG tìm thấy, []).
    """
    result = await session.execute(
        text(
            """
            SELECT id, document_id, version_number, is_original,
                   name, file_type, file_size, file_path, file_hash,
                   extractor_used, chunk_count, change_type, change_note,
                   created_by, created_at
            FROM document_versions
            WHERE document_id = :doc_id AND id = :version_id
            LIMIT 1
            """
        ),
        {"doc_id": str(document_id), "version_id": str(version_id)},
    )
    row = result.fetchone()
    if not row:
        return None, []
    return _row_to_dict(row), []  # D-V3.1-Phase5-B LOCKED: chunks = [] empty


# === Public API: get_version_file_path ===

async def get_version_file_path(
    session: AsyncSession,
    document_id: str,
    version_id: str,
) -> Path | None:
    """SELECT file_path WHERE id — return Path object cho StreamingResponse Plan 05-03."""
    result = await session.execute(
        text(
            "SELECT file_path FROM document_versions "
            "WHERE document_id = :doc_id AND id = :version_id LIMIT 1"
        ),
        {"doc_id": str(document_id), "version_id": str(version_id)},
    )
    row = result.fetchone()
    if not row:
        return None
    return Path(row[0])


# === Public API: restore_to_version (D-V3.1-Phase5-D append-only) ===

async def restore_to_version(
    *,
    session: AsyncSession,
    document_id: str,
    version_id: str,
    actor_user_id: str | None = None,
    actor_role: str = "admin",
    actor_hub_id: str | None = None,
) -> dict[str, Any]:
    """Rollback document về trạng thái version target — APPEND-ONLY (D-V3.1-Phase5-D LOCKED).

    Atomic steps:
    1. Resolve target version từ document_versions (raise ValueError nếu KHÔNG tìm thấy).
    2. Resolve current document từ documents.
    3. snapshot(change_type='restore', change_note=f'Restore to v{N}') — version mới
       INSERT TRƯỚC khi UPDATE documents (append-only history preserve).
    4. UPDATE documents.file_path|filename|mime_type|file_size_bytes = giá trị target version.
    5. (D-V3.1-Phase5-I LOCKED SYNC) Re-extract trigger — cocoindex flow hoặc service
       layer existing nếu có. Plan 05-02 skip re-extract trigger trong service (caller
       Plan 05-03 router responsibility — gọi sau khi restore_to_version return).
    6. Audit emit action='document.version.restore' với payload nest restored_to=version_id.

    Args:
        session: AsyncSession đang mở (caller transaction — restore phải atomic).
        document_id: UUID str.
        version_id: UUID str của target version để rollback.
        actor_user_id: UUID str của user trigger.
        actor_role, actor_hub_id: forensic audit metadata.

    Returns:
        dict shape DocumentAPI (document refreshed sau UPDATE).

    Raises:
        ValueError nếu version_id KHÔNG thuộc document_id (cross-document attack).
        LookupError nếu document_id KHÔNG tồn tại.
    """
    # 1) Resolve target version
    target_result = await session.execute(
        text(
            """
            SELECT id, name, file_type, file_size, file_path, file_hash, version_number
            FROM document_versions
            WHERE document_id = :doc_id AND id = :version_id
            LIMIT 1
            """
        ),
        {"doc_id": str(document_id), "version_id": str(version_id)},
    )
    target = target_result.fetchone()
    if not target:
        raise ValueError(
            f"Version {version_id!r} KHÔNG thuộc document {document_id!r} — "
            f"cross-document restore reject"
        )

    target_name = target[1]
    target_file_type = target[2]
    target_file_size = target[3]
    target_file_path = target[4]
    target_version_number = target[6]

    # 2) Resolve current document (cho snapshot trước UPDATE)
    doc_result = await session.execute(
        text(
            "SELECT id, hub_id, filename, file_path, mime_type, file_size_bytes "
            "FROM documents WHERE id = :doc_id LIMIT 1"
        ),
        {"doc_id": str(document_id)},
    )
    current_doc_row = doc_result.fetchone()
    if not current_doc_row:
        raise LookupError(f"Document {document_id!r} KHÔNG tồn tại")

    # Build duck-type document object cho snapshot()
    class _CurrentDoc:
        id = str(current_doc_row[0])
        hub_id = str(current_doc_row[1]) if current_doc_row[1] else None
        filename = current_doc_row[2]
        file_path = current_doc_row[3]
        mime_type = current_doc_row[4]
        file_size_bytes = current_doc_row[5]

    # 3) Snapshot current state TRƯỚC khi UPDATE (append-only D-V3.1-Phase5-D)
    await snapshot(
        session=session,
        document=_CurrentDoc,
        change_type="restore",
        change_note=f"Restore to v{target_version_number}",
        actor_user_id=actor_user_id,
        actor_role=actor_role,
        actor_hub_id=actor_hub_id,
    )

    # 4) UPDATE documents = giá trị target version
    await session.execute(
        text(
            """
            UPDATE documents
            SET file_path = :file_path,
                filename = :filename,
                mime_type = :mime_type,
                file_size_bytes = :file_size,
                updated_at = NOW()
            WHERE id = :doc_id
            """
        ),
        {
            "file_path": target_file_path,
            "filename": target_name,
            "mime_type": target_file_type,
            "file_size": int(target_file_size),
            "doc_id": str(document_id),
        },
    )

    # 5) Audit emit restore action (D-V3.1-Phase5-H)
    restore_payload = build_audit_payload(
        actor_role=actor_role,
        actor_hub_id=actor_hub_id,
        extra={
            "document_id": str(document_id),
            "version_number": target_version_number,
            "restored_to": str(version_id),
        },
    )
    enqueue_audit(AuditEntry(
        action=ACTION_VERSION_RESTORE,
        user_id=str(actor_user_id) if actor_user_id else None,
        target_type="document",
        target_id=str(document_id),
        hub_id=str(_CurrentDoc.hub_id) if _CurrentDoc.hub_id else None,
        payload=restore_payload,
    ))

    # 6) Re-fetch document refreshed (return shape DocumentAPI)
    refreshed_result = await session.execute(
        text(
            "SELECT id, hub_id, filename, file_path, mime_type, file_size_bytes, "
            "status, created_at, updated_at "
            "FROM documents WHERE id = :doc_id LIMIT 1"
        ),
        {"doc_id": str(document_id)},
    )
    refreshed = refreshed_result.fetchone()
    return {
        "id": str(refreshed[0]),
        "hub_id": str(refreshed[1]) if refreshed[1] else None,
        "filename": refreshed[2],
        "file_path": refreshed[3],
        "mime_type": refreshed[4],
        "file_size_bytes": refreshed[5],
        "status": refreshed[6],
        "created_at": refreshed[7].isoformat() if refreshed[7] else None,
        "updated_at": refreshed[8].isoformat() if refreshed[8] else None,
    }


# === Helper: row → dict ===

def _row_to_dict(row: Any) -> dict[str, Any]:
    """Convert SQLAlchemy Row → dict shape DocumentVersionAPI (15 field explicit)."""
    return {
        "id": str(row[0]),
        "document_id": str(row[1]),
        "version_number": row[2],
        "is_original": row[3],
        "name": row[4],
        "file_type": row[5],
        "file_size": row[6],
        "file_path": row[7],
        "file_hash": row[8],
        "extractor_used": row[9],
        "chunk_count": row[10],
        "change_type": row[11],
        "change_note": row[12],
        "created_by": str(row[13]) if row[13] else None,
        "created_at": row[14].isoformat() if row[14] else None,
    }
