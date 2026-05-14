"""Document service — Plan 04-04 REVISION 2 (INGEST-04, INGEST-05).

Layer between router và DB / FileStore. Hành vi chính:
- Validate ext whitelist (R4).
- save file via FileStore.
- BLOCKER #3 (R4 early-detect strategy A): nếu .pdf → detect_scanned_pdf
  SYNCHRONOUSLY; scanned → INSERT status='failed_unsupported' + raise
  UnsupportedFormatError(scanned=True). Router catch + KHÔNG add BackgroundTask
  cho row scanned (A4 — scanned final).
- INSERT documents với last_heartbeat=NOW() bootstrap (WARNING #7 — watchdog
  Plan 04-05 chỉ flip nếu NOT NULL + stale; tránh false-flip mọi processing row).
- Timestamps dùng SQL NOW() server-side (BLOCKER #4 — KHÔNG dùng deprecated
  Python utcnow API deprecated 3.12).
- A4 (REVISION 2): KHÔNG còn pg-notify('documents-notify', :doc_id) — cocoindex
  1.0.3 source `PgTableSource.fetch_rows()` KHÔNG listen NOTIFY natively
  (RESEARCH.md Section 4.4 + Open Question Q1). Trigger qua FastAPI BackgroundTasks
  ở router level (Plan 04-04 task 03 router) gọi
  `add_task(trigger_cocoindex_update, app.state.cocoindex_app, doc_id)`.
- GET single row qua id.

Module-level helper trigger_cocoindex_update (A4):
- Chạy await asyncio.to_thread(cocoindex_app.update_blocking) trong background
  (sau response 202 client trả về).
- Sau update_blocking() xong, count chunks WHERE document_id=:id → UPDATE
  documents SET status='completed' chunk_count=:count last_heartbeat=NOW()
  nếu >0; status='failed' nếu =0.
- Exception → status='failed' + error_message + last_heartbeat=NOW().

Plan 04-05 EXTEND: list + delete + watchdog logic.
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_engine
from app.schemas.documents import DocumentResponse, DocumentUploadResponse
from app.services.file_extract import (
    ALLOWED_EXTENSIONS,
    UnsupportedFormatError,
    detect_scanned_pdf,
)
from app.services.file_store import FileStore

logger = logging.getLogger(__name__)

SCANNED_PDF_MESSAGE = "PDF scan chưa hỗ trợ trong M2. Khuyến nghị: chuyển sang DOCX."


class DocumentService:
    """Plan 04-04 REVISION 2 ship create + get. Plan 04-05 sẽ extend list + delete."""

    def __init__(
        self,
        db: AsyncSession,
        file_store: FileStore | None = None,
    ) -> None:
        self.db = db
        self.file_store = file_store or FileStore()

    async def create(
        self,
        *,
        hub_id: UUID,
        uploaded_by: UUID | None,
        file_content: bytes,
        original_filename: str,
        mime_type: str | None = None,
    ) -> DocumentUploadResponse:
        """Save file + early-detect scanned PDF + INSERT documents.

        REVISION 2 A4: KHÔNG còn pg-notify — caller (router) trigger cocoindex
        qua BackgroundTasks add_task(trigger_cocoindex_update, app, doc_id).

        Raises:
            UnsupportedFormatError: ext không trong ALLOWED_EXTENSIONS HOẶC PDF scanned (BLOCKER #3).
        """
        ext = Path(original_filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise UnsupportedFormatError(ext)

        # 1) Save file → file_path UUID
        saved_path = self.file_store.save(file_content, original_filename)
        file_size = len(file_content)

        # 2) BLOCKER #3 — early-detect scanned PDF SYNCHRONOUSLY (strategy A).
        is_scanned = False
        if ext == ".pdf":
            try:
                is_scanned = detect_scanned_pdf(saved_path)
            except Exception as e:  # noqa: BLE001 — pypdf parse fail
                logger.warning(
                    "detect_scanned_pdf_failed: %s — treat as non-scanned (defensive)",
                    e,
                )
                is_scanned = False

        doc_id = uuid4()

        if is_scanned:
            # PDF scanned → INSERT status='failed_unsupported'.
            # Timestamps dùng SQL NOW() server-side (BLOCKER #4).
            # last_heartbeat=NOW() bootstrap để consistent với non-scanned path (WARNING #7).
            # A4: KHÔNG add BackgroundTask cho row scanned (router catch raise → 415).
            await self.db.execute(
                text(
                    "INSERT INTO documents "
                    "(id, hub_id, uploaded_by, filename, file_path, mime_type, "
                    "file_size_bytes, status, error_message, attempts, chunk_count, "
                    "last_heartbeat, created_at, updated_at) "
                    "VALUES (:id, :hub, :uploader, :name, :path, :mime, :size, "
                    "'failed_unsupported', :err, 0, 0, NOW(), NOW(), NOW())"
                ),
                {
                    "id": str(doc_id),
                    "hub": str(hub_id),
                    "uploader": str(uploaded_by) if uploaded_by else None,
                    "name": original_filename,
                    "path": str(saved_path),
                    "mime": mime_type,
                    "size": file_size,
                    "err": SCANNED_PDF_MESSAGE,
                },
            )
            logger.info(
                "document_failed_unsupported_scanned_pdf: id=%s hub_id=%s filename=%s",
                doc_id,
                hub_id,
                original_filename,
            )
            # Raise để router trả 415 envelope (KHÔNG add BackgroundTask cho row scanned).
            err = UnsupportedFormatError(".pdf")
            err.args = (SCANNED_PDF_MESSAGE,)
            err.ext = ".pdf"
            err.scanned = True  # type: ignore[attr-defined]
            raise err

        # 3) Non-scanned path — INSERT row status='pending' + last_heartbeat=NOW() bootstrap.
        #    Timestamps dùng SQL NOW() server-side (BLOCKER #4 — KHÔNG dùng deprecated
        #    Python utcnow API deprecated 3.12).
        #    last_heartbeat=NOW() bootstrap (WARNING #7 — watchdog query chỉ flip nếu
        #    NOT NULL + stale; tránh false-flip mọi processing row).
        #    A4 REVISION 2: KHÔNG còn pg-notify — caller (router) add BackgroundTask.
        await self.db.execute(
            text(
                "INSERT INTO documents "
                "(id, hub_id, uploaded_by, filename, file_path, mime_type, "
                "file_size_bytes, status, attempts, chunk_count, last_heartbeat, "
                "created_at, updated_at) "
                "VALUES (:id, :hub, :uploader, :name, :path, :mime, :size, "
                "'pending', 0, 0, NOW(), NOW(), NOW())"
            ),
            {
                "id": str(doc_id),
                "hub": str(hub_id),
                "uploader": str(uploaded_by) if uploaded_by else None,
                "name": original_filename,
                "path": str(saved_path),
                "mime": mime_type,
                "size": file_size,
            },
        )

        # FastAPI get_session() auto-commit on success.
        logger.info(
            "document_created: id=%s hub_id=%s filename=%s size=%d",
            doc_id,
            hub_id,
            original_filename,
            file_size,
        )

        return DocumentUploadResponse(
            document_id=str(doc_id),
            status="pending",
            filename=original_filename,
        )

    async def get(self, document_id: UUID) -> DocumentResponse | None:
        """SELECT 1 document qua id. None nếu không tồn tại."""
        row = (
            await self.db.execute(
                text(
                    "SELECT id, hub_id, uploaded_by, filename, file_path, mime_type, "
                    "file_size_bytes, status, error_message, last_heartbeat, "
                    "attempts, chunk_count, created_at, updated_at "
                    "FROM documents WHERE id = :id"
                ),
                {"id": str(document_id)},
            )
        ).fetchone()
        if row is None:
            return None
        return DocumentResponse(
            id=str(row[0]),
            hub_id=str(row[1]),
            uploaded_by=str(row[2]) if row[2] else None,
            filename=row[3],
            file_path=row[4],
            mime_type=row[5],
            file_size_bytes=row[6],
            status=row[7],
            error_message=row[8],
            last_heartbeat=row[9],
            attempts=row[10],
            chunk_count=row[11],
            created_at=row[12],
            updated_at=row[13],
        )


# === A4 helper module-level — router gọi qua FastAPI BackgroundTasks add_task ===

async def trigger_cocoindex_update(cocoindex_app: Any, doc_id: UUID) -> None:
    """A4 helper — chạy cocoindex update_blocking + set documents status sau khi xong.

    Args:
        cocoindex_app: coco.App instance (Plan 04-03 lưu ở app.state.cocoindex_app).
        doc_id: document_id vừa INSERT (router pass qua add_task args).

    Sequence:
    1. await asyncio.to_thread(cocoindex_app.update_blocking) — chạy cocoindex
       flow blocking trong background thread (KHÔNG block FastAPI event loop).
       Cocoindex re-fetch ALL documents rows + memo skip rows unchanged + process
       row mới (status='pending').
    2. SELECT COUNT(*) FROM chunks WHERE document_id=:id.
    3. Nếu count > 0 → UPDATE documents SET status='completed' chunk_count=:count
       last_heartbeat=NOW() (refresh cho watchdog NULL guard).
    4. Nếu count = 0 → UPDATE documents SET status='failed'
       error_message='cocoindex flow generated 0 chunks' last_heartbeat=NOW().
    5. Exception → UPDATE documents SET status='failed'
       error_message='cocoindex update failed: {exc}' last_heartbeat=NOW().

    Cocoindex 1.0.3 KHÔNG expose per-row callback hook → CẦN strategy này
    (post-update count chunks → set status). Documented inter-plan dependency với
    Plan 04-05 watchdog (5min timeout NULL guard).

    KHÔNG raise — exception swallowed + log + UPDATE failed status (BackgroundTask
    runs sau response client → exception KHÔNG return được lên user).
    """
    if cocoindex_app is None:
        logger.warning(
            "trigger_cocoindex_update_skip: cocoindex_app=None (lifespan setup failed?) doc_id=%s",
            doc_id,
        )
        # Set status='failed' để watchdog/UI phản ánh đúng.
        try:
            engine = get_engine()
            async with engine.begin() as conn:
                await conn.execute(
                    text(
                        "UPDATE documents SET status='failed', "
                        "error_message='cocoindex_app unavailable (lifespan failed)', "
                        "last_heartbeat=NOW(), updated_at=NOW() "
                        "WHERE id = :id"
                    ),
                    {"id": str(doc_id)},
                )
        except Exception as inner:  # noqa: BLE001
            logger.exception("trigger_cocoindex_update_status_set_failed: %s", inner)
        return

    try:
        # 1) Run cocoindex update blocking trong thread executor.
        await asyncio.to_thread(cocoindex_app.update_blocking)
        logger.info("trigger_cocoindex_update_blocking_complete: doc_id=%s", doc_id)

        # 2-4) Count chunks → set status.
        engine = get_engine()
        async with engine.begin() as conn:
            count_row = (
                await conn.execute(
                    text("SELECT COUNT(*) FROM chunks WHERE document_id = :id"),
                    {"id": str(doc_id)},
                )
            ).fetchone()
            count = int(count_row[0]) if count_row else 0

            if count > 0:
                await conn.execute(
                    text(
                        "UPDATE documents SET status='completed', "
                        "chunk_count=:count, last_heartbeat=NOW(), updated_at=NOW() "
                        "WHERE id = :id"
                    ),
                    {"count": count, "id": str(doc_id)},
                )
                logger.info(
                    "trigger_cocoindex_update_completed: doc_id=%s chunks=%d",
                    doc_id,
                    count,
                )
            else:
                await conn.execute(
                    text(
                        "UPDATE documents SET status='failed', "
                        "error_message='cocoindex flow generated 0 chunks', "
                        "last_heartbeat=NOW(), updated_at=NOW() "
                        "WHERE id = :id"
                    ),
                    {"id": str(doc_id)},
                )
                logger.warning(
                    "trigger_cocoindex_update_zero_chunks: doc_id=%s",
                    doc_id,
                )
    except Exception as exc:  # noqa: BLE001 — BackgroundTask exception swallowed
        logger.exception(
            "trigger_cocoindex_update_failed: doc_id=%s exc=%s",
            doc_id,
            exc,
        )
        try:
            engine = get_engine()
            async with engine.begin() as conn:
                await conn.execute(
                    text(
                        "UPDATE documents SET status='failed', "
                        "error_message=:err, last_heartbeat=NOW(), updated_at=NOW() "
                        "WHERE id = :id"
                    ),
                    {
                        "err": f"cocoindex update failed: {exc!s}"[:500],  # truncate long traces
                        "id": str(doc_id),
                    },
                )
        except Exception as inner:  # noqa: BLE001
            logger.exception(
                "trigger_cocoindex_update_status_set_failed: doc_id=%s inner=%s",
                doc_id,
                inner,
            )
