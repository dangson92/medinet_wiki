"""document_versions.py — Phase 5 Plan 05-03 VER-03 + VER-04 router.

4 endpoint exact match frontend api.ts:268-285:
- GET    /api/documents/{document_id}/versions                       → list DESC
- GET    /api/documents/{document_id}/versions/{version_id}          → detail + chunks=[]
- GET    /api/documents/{document_id}/versions/{version_id}/file     → StreamingResponse
- POST   /api/documents/{document_id}/versions/{version_id}/restore  → rollback + audit

Envelope M2 LOCKED: {success: true, data: {...}, error: null, meta: null}

RBAC 3-layer (D-V3.1-Phase5-C LOCKED):
- Layer 1: Settings _enforce_hub_dsn_match (Plan 04-04 v3.0 carry forward boot-time).
- Layer 2: Repository per-hub filter ở service layer (Plan 05-02 — query qua document_id;
  hub isolation enforce ở Layer 3).
- Layer 3:
  * 3 GET endpoint: Depends(get_current_user_for_hub_access) — JWT.hub_ids check
    (Plan 03-03 v3.0 carry forward SSO-04). Viewer + editor + hub_admin + super
    admin all PASS.
  * POST /restore endpoint: Depends(get_current_user) + inline assert_hub_admin_for
    sau resolve document.hub_id (Plan 02-01 v3.1 hybrid pattern). Viewer + cross-hub
    hub_admin reject 403 HUB_ADMIN_REQUIRED envelope.

D-V3.1-Phase5-I LOCKED: POST /restore SYNC block (< 5s small DOCX). Cocoindex re-extract
trigger nếu app.state.cocoindex_app tồn tại + có API update_blocking — gọi blocking
trong handler (KHÔNG BackgroundTask). Best-effort: log + continue nếu fail (KHÔNG
fail restore vì re-extract miss).

Audit emit RESPONSIBILITY ở service layer (Plan 05-02 snapshot + restore_to_version):
- POST /restore → service emit 2 action ('document.version.create' restore version
  + 'document.version.restore' rollback). Router KHÔNG gọi enqueue_audit trực tiếp.

Mount: UNIVERSAL ở main.py::create_app SAU documents_router (KHÔNG central-only —
documents per-hub data; carry forward FACTOR-01 v3.0 Phase 2 pattern).
"""
from __future__ import annotations

import logging
from typing import Any
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import (
    assert_hub_admin_for,
    get_current_user,
    get_current_user_for_hub_access,
)
from app.db.session import get_session
from app.models.auth import User
from app.services import document_version_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/documents", tags=["Document Versions"])


# === Helper: success envelope ===

def _success_envelope(data: Any) -> dict[str, Any]:
    """M2 LOCKED envelope shape — try import shared helper, else inline construct.

    Pattern carry forward documents.py + auth.py + other routers M2 baseline.
    Try import `app.pkg.response.success_envelope` first; fallback nếu KHÔNG tồn tại
    (app.pkg.response export `ok()` / `created()` JSONResponse; KHÔNG có symbol
    `success_envelope` plain-dict — fallback đảm bảo router luôn trả dict shape
    cho FastAPI auto-serialize JSON với envelope M2).
    """
    try:
        from app.pkg.response import success_envelope  # type: ignore[import-not-found,attr-defined]
        return success_envelope(data)  # type: ignore[no-any-return]
    except ImportError:
        # Fallback shape M2 LOCKED — manual construct.
        return {"success": True, "data": data, "error": None, "meta": None}


# === Helper: resolve document hub_id (raw SQL — KHÔNG ORM mới) ===

async def _resolve_document_hub_id(
    db: AsyncSession,
    document_id: UUID,
) -> tuple[str, str | None]:
    """SELECT id, hub_id FROM documents WHERE id = :id LIMIT 1.

    Returns:
        (document_id_str, hub_id_str | None nếu KHÔNG có hub_id).

    Raises:
        HTTPException(404) nếu document KHÔNG tồn tại.
    """
    result = await db.execute(
        text("SELECT id, hub_id FROM documents WHERE id = :id LIMIT 1"),
        {"id": str(document_id)},
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "DOCUMENT_NOT_FOUND",
                "message": f"Document {document_id!r} KHÔNG tồn tại",
            },
        )
    return str(row[0]), (str(row[1]) if row[1] else None)


# === Endpoint 1: GET /versions list ===

@router.get("/{document_id}/versions", response_model=None)
async def list_document_versions(
    document_id: UUID,
    user: User = Depends(get_current_user_for_hub_access),  # noqa: B008 — FastAPI pattern
    db: AsyncSession = Depends(get_session),                # noqa: B008
) -> dict[str, Any]:
    """GET versions list — viewer + editor + hub_admin + super admin PASS.

    Hub isolation: Layer 3 SSO-04 (Plan 03-03 v3.0 — JWT.hub_ids check document.hub_id).

    Returns:
        Envelope M2: {success: true, data: {versions: DocumentVersionAPI[]}, error: null, meta: null}
        Order: DESC by version_number (≤ 5 row sau retention prune D-V3.1-Phase5-E).
    """
    # Resolve document (404 nếu missing) — KHÔNG check hub_id explicit vì
    # get_current_user_for_hub_access đã enforce JWT.hub_ids ⊇ {settings.hub_name}.
    await _resolve_document_hub_id(db, document_id)

    versions = await document_version_service.list_versions(db, str(document_id))
    return _success_envelope({"versions": versions})


# === Endpoint 2: GET /versions/{vid} detail ===

@router.get("/{document_id}/versions/{version_id}", response_model=None)
async def get_document_version_detail(
    document_id: UUID,
    version_id: UUID,
    user: User = Depends(get_current_user_for_hub_access),  # noqa: B008
    db: AsyncSession = Depends(get_session),                # noqa: B008
) -> dict[str, Any]:
    """GET version detail + chunks empty array (D-V3.1-Phase5-B LOCKED).

    chunks = [] empty — FE typecheck happy (DocumentVersionChunkAPI interface
    declared nhưng BE KHÔNG snapshot chunks; restore re-extract sẽ regenerate).
    """
    await _resolve_document_hub_id(db, document_id)

    version_dict, chunks = await document_version_service.get_version_with_chunks(
        db, str(document_id), str(version_id),
    )
    if version_dict is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "VERSION_NOT_FOUND",
                "message": f"Version {version_id!r} KHÔNG thuộc document {document_id!r}",
            },
        )
    return _success_envelope({"version": version_dict, "chunks": chunks})  # D-V3.1-Phase5-B: chunks=[]


# === Endpoint 3: GET /versions/{vid}/file binary ===

@router.get("/{document_id}/versions/{version_id}/file", response_model=None)
async def download_document_version_file(
    document_id: UUID,
    version_id: UUID,
    user: User = Depends(get_current_user_for_hub_access),  # noqa: B008
    db: AsyncSession = Depends(get_session),                # noqa: B008
) -> StreamingResponse:
    """GET binary file — StreamingResponse + Content-Disposition attachment.

    FE handle download qua `<a download={...}>` attribute (DocumentVersionHistory.tsx:79
    pattern `v{version_number}_{v.name}`). BE Content-Disposition match best-practice
    nhưng FE override.

    Hub isolation Layer 3 đủ — KHÔNG cần thêm role check.
    """
    await _resolve_document_hub_id(db, document_id)

    # Resolve version metadata cho mime_type + name + version_number
    version_dict, _chunks = await document_version_service.get_version_with_chunks(
        db, str(document_id), str(version_id),
    )
    if version_dict is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "VERSION_NOT_FOUND",
                "message": f"Version {version_id!r} KHÔNG thuộc document {document_id!r}",
            },
        )

    file_path = await document_version_service.get_version_file_path(
        db, str(document_id), str(version_id),
    )
    if file_path is None or not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "VERSION_FILE_MISSING",
                "message": (
                    f"File version {version_id!r} KHÔNG tồn tại trên đĩa "
                    f"(storage cleanup may have removed)"
                ),
            },
        )

    download_filename = f"v{version_dict['version_number']}_{version_dict['name']}"
    media_type = version_dict.get("file_type") or "application/octet-stream"

    # RFC 6266 — filename* UTF-8 percent-encoded để xử lý dấu tiếng Việt an toàn
    # (header ASCII-only; tên file có ký tự non-ASCII phải percent-encode hoặc
    # browser sẽ fallback hỏng). FE `<a download>` attribute override user-visible
    # name; BE header chính tắc cho cURL/wget/non-FE consumer.
    encoded_filename = quote(download_filename)
    return StreamingResponse(
        file_path.open("rb"),
        media_type=media_type,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}",
        },
    )


# === Endpoint 4: POST /versions/{vid}/restore ===

@router.post("/{document_id}/versions/{version_id}/restore", response_model=None)
async def restore_document_to_version(
    document_id: UUID,
    version_id: UUID,
    request: Request,
    user: User = Depends(get_current_user),  # noqa: B008 — hybrid pattern KHÔNG hub_access
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> dict[str, Any]:
    """POST restore — hub_admin + super admin PASS; viewer + cross-hub → 403.

    D-V3.1-Phase5-C LOCKED: POST /restore mutation requires hub_admin OR super.
    D-V3.1-Phase5-D LOCKED: append-only (snapshot TRƯỚC khi UPDATE — service layer).
    D-V3.1-Phase5-I LOCKED: SYNC block endpoint (< 5s small DOCX).

    Steps:
    1. Resolve document.hub_id từ DB (404 nếu missing).
    2. Inline assert_hub_admin_for(user, db, target_hub_id=document.hub_id) —
       reject 403 HUB_ADMIN_REQUIRED nếu viewer hoặc cross-hub hub_admin.
    3. Call service restore_to_version — atomic snapshot + UPDATE documents + audit.
    4. (Optional) Trigger cocoindex re-extract sync nếu app.state.cocoindex_app tồn tại.
    5. Return envelope refreshed document.

    Audit emit RESPONSIBILITY ở service layer (Plan 05-02) — router KHÔNG enqueue_audit.
    """
    # 1) Resolve document + extract hub_id
    doc_id_str, doc_hub_id = await _resolve_document_hub_id(db, document_id)

    # 2) Inline RBAC check (Plan 02-01 v3.1 hybrid pattern)
    if doc_hub_id is None:
        # Document KHÔNG có hub_id (legacy orphan) — reject 400 fail-loud.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "DOCUMENT_HUB_MISSING",
                "message": (
                    f"Document {document_id!r} KHÔNG có hub_id — "
                    f"KHÔNG thể determine RBAC scope"
                ),
            },
        )

    await assert_hub_admin_for(user=user, db=db, target_hub_id=doc_hub_id)

    # 3) Derive actor metadata (Plan 02-04 v3.1 pattern) — narrow tường minh để
    # tránh trường hợp assert_hub_admin_for có edge case cho viewer/editor (defense
    # in depth: chỉ admin hoặc hub_admin được tới đây).
    if user.role == "admin":
        actor_role, actor_hub_id = "admin", None
    elif user.role == "hub_admin":
        actor_role, actor_hub_id = "hub_admin", doc_hub_id
    else:
        # assert_hub_admin_for SHOULD reject role khác — defense in depth raise
        # nếu logic upstream regress, KHÔNG silently mislabel viewer là hub_admin.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "HUB_ADMIN_REQUIRED",
                "message": (
                    f"Role {user.role!r} không có quyền restore "
                    f"(defense in depth)"
                ),
            },
        )

    # 4) Call service restore (append-only D-V3.1-Phase5-D + audit emit D-V3.1-Phase5-H)
    refreshed = await document_version_service.restore_to_version(
        session=db,
        document_id=doc_id_str,
        version_id=str(version_id),
        actor_user_id=str(user.id),
        actor_role=actor_role,
        actor_hub_id=actor_hub_id,
    )

    # 5) Trigger cocoindex re-extract SYNC (D-V3.1-Phase5-I) — best effort, KHÔNG fail nếu missing
    cocoindex_app = getattr(request.app.state, "cocoindex_app", None)
    if cocoindex_app is not None:
        try:
            # Cocoindex flow trigger sync — verify API qua existing trigger_cocoindex_update
            # documents.py pattern (line 162) dùng BackgroundTasks; restore D-V3.1-Phase5-I LOCKED
            # SYNC block (< 5s small DOCX). Try sync `cocoindex_app.update_blocking()` nếu API có.
            if hasattr(cocoindex_app, "update_blocking"):
                cocoindex_app.update_blocking()
            else:
                logger.info(
                    "restore_skip_reextract: cocoindex_app missing update_blocking — "
                    "schema updated NHƯNG chunks KHÔNG re-extract, defer v4.0 async queue"
                )
        except Exception as e:  # noqa: BLE001 — log + continue, KHÔNG fail restore
            logger.warning(
                "restore_reextract_failed: doc_id=%s err=%s", doc_id_str, e
            )

    # 6) Return envelope refreshed document
    return _success_envelope(refreshed)


# Public symbol for main.py import
__all__ = ["router"]
