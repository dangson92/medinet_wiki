"""POST /v1/process — multipart upload, trả schema DSVC-02.

Trách nhiệm:
1. Accept multipart/form-data: field `file` (binary) + metadata fields
   (hub_code, doc_type, request_id) + chunker_options (JSON string) optional.
2. Enforce limits:
   - Vượt DOCLING_MAX_FILE_MB → 413 Payload Too Large.
   - Vượt DOCLING_REQUEST_TIMEOUT_SEC → 504 Gateway Timeout (asyncio.timeout wrap).
3. Wire extractor.extract → chunker.chunk → serialize_chunks → trả ProcessResponse.
4. Wrap blocking Docling work qua asyncio.to_thread() (FastAPI async, không block loop).
5. Log JSON với request_id mỗi step (structlog contextvars đã bind ở middleware).

Tham chiếu:
- DSVC-01 (endpoint contract), DSVC-02 (response schema), DSVC-06 (limits).
- CHUNK-03 (per-request chunker_options override).
"""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

import structlog
from fastapi import APIRouter, Form, HTTPException, Request, UploadFile

from docling_pipeline.config import get_settings
from docling_pipeline.core.chunker import ChunkerOptions, get_chunker
from docling_pipeline.core.extractor import get_extractor
from docling_pipeline.core.serializer import build_doc_meta, serialize_chunks

router = APIRouter(prefix="/v1", tags=["process"])
logger = structlog.get_logger(__name__)


@router.post("/process")
async def process_document(
    request: Request,
    file: UploadFile,
    hub_code: str = Form(default=""),
    doc_type: str = Form(default=""),
    request_id: str = Form(default=""),
    chunker_options: str = Form(default=""),
) -> dict[str, Any]:
    """Extract + chunk file binary → JSON DSVC-02."""
    settings = get_settings()
    rid = (
        request_id
        or request.headers.get("X-Request-Id")
        or str(uuid.uuid4())
    )

    # ── Validate filename ──
    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail={"error": "missing_filename"},
        )

    # ── Đọc body + check size limit (DSVC-06 → 413) ──
    body = await file.read()
    if len(body) > settings.max_file_bytes:
        logger.warning(
            "payload_too_large",
            request_id=rid,
            filename=file.filename,
            size_bytes=len(body),
            max_bytes=settings.max_file_bytes,
        )
        raise HTTPException(
            status_code=413,
            detail={
                "error": "payload_too_large",
                "max_mb": settings.max_file_mb,
                "received_mb": round(len(body) / 1024 / 1024, 2),
            },
        )

    # ── Parse chunker_options JSON (CHUNK-03 per-request override) ──
    chunk_opts = ChunkerOptions()
    if chunker_options:
        try:
            opts_dict = json.loads(chunker_options)
            chunk_opts = ChunkerOptions.from_dict(opts_dict)
        except (json.JSONDecodeError, TypeError) as exc:
            logger.warning(
                "invalid_chunker_options",
                request_id=rid,
                error=str(exc),
            )
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "invalid_chunker_options_json",
                    "message": str(exc),
                },
            ) from exc

    extractor = get_extractor()
    chunker = get_chunker()

    logger.info(
        "process_start",
        request_id=rid,
        filename=file.filename,
        hub_code=hub_code,
        doc_type=doc_type,
        size_bytes=len(body),
    )

    # ── Async wrap Docling blocking work + timeout (DSVC-06 → 504) ──
    async def _run() -> tuple[Any, list[Any]]:
        doc = await asyncio.to_thread(extractor.extract, body, file.filename)
        chunks = await asyncio.to_thread(chunker.chunk, doc, chunk_opts)
        return doc, chunks

    try:
        async with asyncio.timeout(settings.request_timeout_sec):
            doc, chunks = await _run()
    except TimeoutError as exc:
        logger.error(
            "request_timeout",
            request_id=rid,
            timeout_sec=settings.request_timeout_sec,
            filename=file.filename,
        )
        raise HTTPException(
            status_code=504,
            detail={
                "error": "request_timeout",
                "timeout_sec": settings.request_timeout_sec,
            },
        ) from exc
    except ValueError as exc:
        # Unsupported extension từ extractor → 415
        logger.warning(
            "unsupported_media_type",
            request_id=rid,
            filename=file.filename,
            error=str(exc),
        )
        raise HTTPException(
            status_code=415,
            detail={"error": "unsupported_media_type", "message": str(exc)},
        ) from exc
    except Exception as exc:
        logger.error(
            "process_fail",
            request_id=rid,
            error=str(exc),
            filename=file.filename,
        )
        raise HTTPException(
            status_code=500,
            detail={"error": "process_fail", "message": str(exc)},
        ) from exc

    # ── ocr_used: best-effort detect ──
    # PDF có thể trigger OCR (Docling do_ocr=True), image luôn OCR. DOCX/XLSX/HTML không OCR.
    ext = (
        file.filename.rsplit(".", 1)[-1].lower()
        if "." in file.filename
        else ""
    )
    ocr_used = ext in {"png", "jpg", "jpeg", "pdf"}

    tokenizer_name = chunk_opts.tokenizer_name or settings.tokenizer_name
    doc_meta = build_doc_meta(doc, file.filename, ocr_used=ocr_used)
    chunks_dict = serialize_chunks(doc, chunks, tokenizer_name=tokenizer_name)

    logger.info(
        "process_done",
        request_id=rid,
        filename=file.filename,
        hub_code=hub_code,
        doc_type=doc_type,
        chunks=len(chunks_dict),
        pages=doc_meta["page_count"],
    )

    return {
        "request_id": rid,
        "doc_meta": doc_meta,
        "chunks": chunks_dict,
    }


__all__ = ["router"]
