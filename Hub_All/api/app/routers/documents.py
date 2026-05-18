"""Documents router — Plan 04-04 REVISION 2 (INGEST-04, INGEST-05) + Plan 04-05 (INGEST-07, INGEST-08).

4 endpoint:
    POST   /api/documents/upload  — multipart + admin → 202 document_id
                                    + BackgroundTask trigger_cocoindex_update (A4)
    GET    /api/documents/:id     — Bearer → 200 DocumentResponse / 404
    DELETE /api/documents/:id     — admin → 204 No Content + cascade chunks + audit log (Plan 04-05)
    GET    /api/documents         — Bearer → 200 paginated list + filter (Plan 04-05)

Auth pattern:
- POST upload: require_role("admin") — chỉ admin upload (D6 frontend admin-only).
- GET :id: get_current_user — viewer/editor/admin đều xem được (RBAC khi list
  filter hub_id sẽ enforce ở Plan 04-05 — Phase 5 chính thức HUB-02).

Mitigations:
- WARNING #6 DoS: Content-Length header pre-check TRƯỚC file.read() để chống
  attacker upload 10GB buffer toàn bộ.
- BLOCKER #3 R4: UnsupportedFormatError với scanned=True attribute → 415 với
  message rõ "PDF scan chưa hỗ trợ trong M2".
- A4 (REVISION 2 — user BLOCKING confirmed): Sau service.create() OK (KHÔNG
  raise UnsupportedFormatError) → background_tasks.add_task(
  trigger_cocoindex_update, request.app.state.cocoindex_app, doc_id). Cocoindex
  1.0.3 KHÔNG support source LISTEN/NOTIFY → must trigger update_blocking
  synchronously per upload (Plan 04-03 lifespan đã setup app.state.cocoindex_app).
"""
from __future__ import annotations

import logging
from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import JSONResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import (
    UserWithHubs,
    get_current_user,
    get_current_user_with_hubs,
    require_role,
)
from app.db.session import get_session
from app.models.auth import User
from app.pkg import response as resp
from app.repositories.hub_isolation import HubIsolationError
from app.services.documents_service import (
    DocumentService,
    trigger_cocoindex_update,
)
from app.services.file_extract import UnsupportedFormatError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/documents", tags=["documents"])

# Limit upload size = 50MB (DoS mitigation T-04-02-03 + T-04-04-01 + WARNING #6).
MAX_UPLOAD_SIZE_BYTES = 50 * 1024 * 1024


def get_document_service(
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> DocumentService:
    return DocumentService(db=db)


@router.post("/upload")
async def upload(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),  # noqa: B008
    hub_id: str = Form(...),
    user: User = Depends(require_role("admin")),  # noqa: B008
    service: DocumentService = Depends(get_document_service),  # noqa: B008
) -> JSONResponse:
    """POST /api/documents/upload — multipart file + hub_id → 202.

    R4 mitigation: ext không trong whitelist → 415 UNSUPPORTED_FORMAT.
    BLOCKER #3: PDF scanned → 415 UNSUPPORTED_FORMAT + row failed_unsupported
    + KHÔNG add BackgroundTask cho row scanned (A4 — final).
    WARNING #6: Content-Length > 50MB → 400 FILE_TOO_LARGE trước khi file.read().
    A4 (REVISION 2): Sau service.create() OK → background_tasks.add_task(
    trigger_cocoindex_update, request.app.state.cocoindex_app, doc_id) — chạy
    cocoindex_app.update_blocking() trong background thread sau response 202.
    """
    # === WARNING #6 — Content-Length pre-check TRƯỚC file.read() ===
    content_length_header = request.headers.get("content-length")
    if content_length_header:
        try:
            content_length = int(content_length_header)
            if content_length > MAX_UPLOAD_SIZE_BYTES:
                return resp.bad_request(
                    message=f"File vượt quá giới hạn {MAX_UPLOAD_SIZE_BYTES // (1024*1024)}MB",
                    code="FILE_TOO_LARGE",
                )
        except (TypeError, ValueError):
            pass  # invalid header → tiếp tục, sẽ check sau read

    # Validate hub_id UUID format
    try:
        hub_uuid = UUID(hub_id)
    except ValueError:
        return resp.bad_request(
            message=f"hub_id không phải UUID hợp lệ: {hub_id!r}",
            code="INVALID_HUB_ID",
        )

    # Read file content (đã pre-check Content-Length — buffer ≤ 50MB).
    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE_BYTES:
        # Fallback nếu client KHÔNG gửi Content-Length header (defensive).
        return resp.bad_request(
            message=f"File vượt quá giới hạn {MAX_UPLOAD_SIZE_BYTES // (1024*1024)}MB",
            code="FILE_TOO_LARGE",
        )
    if len(content) == 0:
        return resp.bad_request(
            message="File rỗng — không thể upload",
            code="EMPTY_FILE",
        )

    original_filename = file.filename or "unnamed"
    mime_type = file.content_type

    try:
        result = await service.create(
            hub_id=hub_uuid,
            uploaded_by=user.id,
            file_content=content,
            original_filename=original_filename,
            mime_type=mime_type,
        )
    except UnsupportedFormatError as e:
        # BLOCKER #3 — scanned PDF: service đã INSERT row failed_unsupported.
        # A4: KHÔNG add BackgroundTask cho row scanned.
        # Trả 415 với message phù hợp (SCANNED_PDF_MESSAGE nếu scanned, else default).
        return resp.unsupported_format(message=str(e))

    # A4 REVISION 2 — sau service.create OK (status='pending'), trigger cocoindex
    # qua FastAPI BackgroundTasks. Plan 04-03 lifespan đã setup app.state.cocoindex_app.
    cocoindex_app = getattr(request.app.state, "cocoindex_app", None)
    if cocoindex_app is None:
        logger.warning(
            "upload_no_cocoindex_app_in_state: doc_id=%s — BackgroundTask sẽ set status=failed",
            result.id,
        )
    background_tasks.add_task(
        trigger_cocoindex_update,
        cocoindex_app,
        UUID(result.id),
    )

    return resp.accepted(data=result.model_dump(mode="json"))


@router.get("/{document_id}")
async def get_by_id(
    document_id: str,
    user: User = Depends(get_current_user),  # noqa: B008
    service: DocumentService = Depends(get_document_service),  # noqa: B008
) -> JSONResponse:
    """GET /api/documents/:id — Bearer → DocumentResponse.

    Plan 04-04 ship: bất kỳ user authenticated đều xem được.
    Plan 04-05 / Phase 5 HUB-02 sẽ enforce hub isolation (user.hub_assignments
    intersect document.hub_id).
    """
    _ = user  # Reserved cho Plan 04-05 hub isolation enforce.
    try:
        doc_uuid = UUID(document_id)
    except ValueError:
        return resp.bad_request(
            message=f"document_id không phải UUID hợp lệ: {document_id!r}",
            code="INVALID_DOCUMENT_ID",
        )

    doc = await service.get(doc_uuid)
    if doc is None:
        return resp.not_found(
            message=f"Document {document_id} không tồn tại",
            code="NOT_FOUND",
        )
    return resp.ok(data=doc.model_dump(mode="json"))


@router.get("/{document_id}/status")
async def get_status(
    document_id: str,
    user: User = Depends(get_current_user),  # noqa: B008
    service: DocumentService = Depends(get_document_service),  # noqa: B008
) -> JSONResponse:
    """GET /api/documents/:id/status — Bearer → {status, progress}.

    Frontend poll endpoint này mỗi 1.5s cho document pending/processing để
    cập nhật progress bar (D6 — Go cũ có endpoint tương đương).
    `progress` derive từ status (xem schemas.documents.progress_for_status).
    """
    _ = user  # Reserved cho Phase 5 hub isolation enforce.
    try:
        doc_uuid = UUID(document_id)
    except ValueError:
        return resp.bad_request(
            message=f"document_id không phải UUID hợp lệ: {document_id!r}",
            code="INVALID_DOCUMENT_ID",
        )

    doc = await service.get(doc_uuid)
    if doc is None:
        return resp.not_found(
            message=f"Document {document_id} không tồn tại",
            code="NOT_FOUND",
        )
    return resp.ok(data={"status": doc.status, "progress": doc.progress})


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_by_id(
    document_id: str,
    request: Request,
    principal: UserWithHubs = Depends(get_current_user_with_hubs),  # noqa: B008
    service: DocumentService = Depends(get_document_service),  # noqa: B008
) -> Response:
    """DELETE /api/documents/:id — admin/editor → 204 + cascade chunks + audit log.

    HUB-02 / E4 — Plan 05-06: endpoint giờ editor-eligible (KHÔNG còn admin-only).
    - viewer → 403 FORBIDDEN (read-only — reject TRƯỚC verify_hub_access).
    - editor → service.delete enforce verify_hub_access (hub_id resource từ DB);
      editor cross-hub → HubIsolationError → 403 + audit security.hub_isolation_violation.
    - admin → bypass hub isolation (T-04-05-03 cross-hub DELETE preserved).
    - service.delete: SELECT exists → verify_hub_access → DELETE documents
      (chunks CASCADE FK Phase 2) → INSERT audit_logs → best-effort unlink file.
    - Return 204 No Content (KHÔNG body theo HTTP spec).
    """
    # Viewer read-only — reject TRƯỚC khi vào service layer (T-05-06-06).
    if principal.user.role == "viewer":
        return resp.forbidden(
            message="Viewer không được xoá document",
            code="FORBIDDEN",
        )

    try:
        doc_uuid = UUID(document_id)
    except ValueError:
        return resp.bad_request(
            message=f"document_id không phải UUID hợp lệ: {document_id!r}",
            code="INVALID_DOCUMENT_ID",
        )

    request_id = getattr(request.state, "request_id", None)
    try:
        deleted = await service.delete(
            doc_uuid,
            actor=principal.user,
            actor_hub_ids=principal.hub_ids,
            request_id=request_id,
        )
    except HubIsolationError as e:
        # E4 — editor cross-hub reject. Audit emit đã xảy ra ở service layer.
        return resp.forbidden(message=str(e), code="FORBIDDEN")

    if not deleted:
        return resp.not_found(
            message=f"Document {document_id} không tồn tại",
            code="NOT_FOUND",
        )
    # 204 No Content — Starlette emit empty body khi status_code=204.
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("")
async def list_documents(
    hub_id: str | None = None,
    status_filter: str | None = None,
    uploaded_by: str | None = None,
    search: str | None = None,
    page: int = 1,
    per_page: int = 20,
    user: User = Depends(get_current_user),  # noqa: B008
    service: DocumentService = Depends(get_document_service),  # noqa: B008
) -> JSONResponse:
    """GET /api/documents — list paginated (Plan 04-05 INGEST-08).

    Query params:
        hub_id: filter UUID.
        status_filter: filter status enum (pending|processing|completed|failed|failed_unsupported).
        uploaded_by: filter user upload UUID.
        search: ILIKE filename %search%.
        page: 1-based (default 1).
        per_page: 20 default, CAP min(per_page, 100) (T-04-05-01 DoS mitigation).

    Phase 5 HUB-02 sẽ thêm hub_assignments intersection (T-04-05-02 + T-04-05-06 accept).
    """
    _ = user  # Reserved cho Phase 5 hub_assignments filter.

    # Validate optional UUIDs.
    hub_uuid: UUID | None = None
    if hub_id:
        try:
            hub_uuid = UUID(hub_id)
        except ValueError:
            return resp.bad_request(
                message=f"hub_id không phải UUID hợp lệ: {hub_id!r}",
                code="INVALID_HUB_ID",
            )

    uploaded_uuid: UUID | None = None
    if uploaded_by:
        try:
            uploaded_uuid = UUID(uploaded_by)
        except ValueError:
            return resp.bad_request(
                message=f"uploaded_by không phải UUID hợp lệ: {uploaded_by!r}",
                code="INVALID_UPLOADED_BY",
            )

    # Cap per_page ≤ 100 + page ≥ 1 (INGEST-08, T-04-05-01).
    capped_per_page = max(1, min(per_page, 100))
    capped_page = max(1, page)

    items, total = await service.list(
        hub_id=hub_uuid,
        status_filter=status_filter,
        uploaded_by=uploaded_uuid,
        search=search,
        page=capped_page,
        per_page=capped_per_page,
    )

    return resp.paginated(
        items=[item.model_dump(mode="json") for item in items],
        page=capped_page,
        per_page=capped_per_page,
        total=total,
    )
