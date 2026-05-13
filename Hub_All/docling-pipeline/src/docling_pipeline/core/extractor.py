"""Wrapper Docling DocumentConverter — single-format-agnostic extraction.

Trách nhiệm:
1. Nhận file_bytes + filename → trả về DoclingDocument.
2. Config OCR Tesseract vie+eng mặc định (DSVC-03 + EXTRACT-02), switch RapidOCR
   qua env DOCLING_OCR_ENGINE=rapidocr.
3. Bật table_structure preservation (EXTRACT-03 — table_html sẽ serialize ở Plan 05).
4. Expose warm_models() cho FastAPI lifespan pre-load (Plan 06).

Tham chiếu:
- CONTEXT.md mục E (OCR engine choice).
- DSVC-03, EXTRACT-01, EXTRACT-02 trong REQUIREMENTS.md.
- Revision W5: format_options dùng ImageFormatOption riêng cho InputFormat.IMAGE
  (Docling 2.91 validator reject mismatch PdfFormatOption + InputFormat.IMAGE).
"""

from __future__ import annotations

import io
from functools import lru_cache
from pathlib import Path

import structlog
from docling.datamodel.base_models import DocumentStream, InputFormat
from docling.datamodel.document import ConversionResult
from docling.datamodel.pipeline_options import (
    PdfPipelineOptions,
    RapidOcrOptions,
    TesseractCliOcrOptions,
)
from docling.document_converter import (
    DocumentConverter,
    ImageFormatOption,
    PdfFormatOption,
)
from docling_core.types.doc import DoclingDocument

from docling_pipeline.config import Settings, get_settings

logger = structlog.get_logger(__name__)

# Mapping extension → InputFormat enum của Docling.
# EXTRACT-01: 1 luồng, KHÔNG if-else nghiệp vụ — chỉ map enum để Docling tự dispatch.
_EXT_TO_FORMAT: dict[str, InputFormat] = {
    ".pdf": InputFormat.PDF,
    ".docx": InputFormat.DOCX,
    ".xlsx": InputFormat.XLSX,
    ".pptx": InputFormat.PPTX,
    ".html": InputFormat.HTML,
    ".htm": InputFormat.HTML,
    ".png": InputFormat.IMAGE,
    ".jpg": InputFormat.IMAGE,
    ".jpeg": InputFormat.IMAGE,
}


def _build_ocr_options(settings: Settings):
    """Build OCR options theo env DOCLING_OCR_ENGINE."""
    langs = [lang.strip() for lang in settings.ocr_langs.split("+") if lang.strip()]
    if settings.ocr_engine == "rapidocr":
        # RapidOCR không có concept lang per-init giống Tesseract; vẫn để default.
        return RapidOcrOptions()
    # Default Tesseract — DSVC-03 + EXTRACT-02.
    return TesseractCliOcrOptions(lang=langs)


def _build_pipeline_options(settings: Settings) -> PdfPipelineOptions:
    """PdfPipelineOptions chung cho PDF + image (Docling dùng cùng pipeline class)."""
    opts = PdfPipelineOptions()
    opts.do_ocr = True                        # EXTRACT-02
    opts.do_table_structure = True            # EXTRACT-03 — preserve table HTML
    opts.table_structure_options.do_cell_matching = True
    opts.generate_picture_images = False      # Không nhúng binary image vào response
    opts.ocr_options = _build_ocr_options(settings)
    return opts


class DoclingExtractor:
    """Wrapper DocumentConverter — single instance reuse, KHÔNG concurrent.

    Docling parser KHÔNG thread-safe (CONTEXT mục D). Service chạy uvicorn 1 worker
    + asyncio.to_thread serialize đảm bảo FIFO 1 request / lần.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._converter = self._build_converter()

    def _build_converter(self) -> DocumentConverter:
        pipe_opts = _build_pipeline_options(self.settings)
        # W5: ImageFormatOption RIÊNG cho IMAGE — KHÔNG dùng PdfFormatOption cho IMAGE.
        # Docling 2.91 validator reject mismatch (PdfFormatOption + InputFormat.IMAGE → ValueError).
        return DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipe_opts),
                InputFormat.IMAGE: ImageFormatOption(pipeline_options=pipe_opts),
                # DOCX/XLSX/PPTX/HTML dùng default options của Docling — không cần OCR.
            }
        )

    def extract(self, file_bytes: bytes, filename: str) -> DoclingDocument:
        """Extract file binary → DoclingDocument.

        Raises:
            ValueError: extension không support.
            RuntimeError: Docling convert fail.
        """
        ext = Path(filename).suffix.lower()
        if ext not in _EXT_TO_FORMAT:
            raise ValueError(
                f"unsupported file extension {ext!r} — supported: {sorted(_EXT_TO_FORMAT)}"
            )

        stream = DocumentStream(name=filename, stream=io.BytesIO(file_bytes))
        logger.info(
            "extract_start",
            filename=filename,
            ext=ext,
            size_bytes=len(file_bytes),
            ocr_engine=self.settings.ocr_engine,
        )
        try:
            result: ConversionResult = self._converter.convert(stream)
        except Exception as exc:
            logger.error("extract_fail", filename=filename, error=str(exc))
            raise RuntimeError(f"docling convert failed for {filename}: {exc}") from exc

        doc = result.document
        page_count = len(doc.pages) if hasattr(doc, "pages") and doc.pages else 0
        logger.info("extract_done", filename=filename, pages=page_count)
        return doc

    def warm_models(self) -> None:
        """Pre-load Docling models bằng cách convert 1 stub PDF tối thiểu.

        Gọi từ FastAPI lifespan (Plan 06) để /readyz pass sau khi models warm.
        Fail soft — service vẫn lên, request đầu sẽ chậm hơn.
        """
        # Stub PDF tối thiểu — 1 trang trắng. KHÔNG trigger OCR (không có raster).
        stub_pdf = (
            b"%PDF-1.4\n"
            b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
            b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
            b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]>>endobj\n"
            b"xref\n0 4\n0000000000 65535 f\n"
            b"0000000009 00000 n\n0000000053 00000 n\n0000000098 00000 n\n"
            b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n149\n%%EOF\n"
        )
        try:
            self.extract(stub_pdf, "_warmup.pdf")
            logger.info("warm_models_done")
        except Exception as exc:
            logger.warning("warm_models_fail", error=str(exc))


@lru_cache(maxsize=1)
def get_extractor() -> DoclingExtractor:
    """Singleton extractor — DocumentConverter heavy init, reuse instance."""
    return DoclingExtractor()


def warm_models() -> None:
    """Convenience wrapper cho FastAPI lifespan."""
    get_extractor().warm_models()
