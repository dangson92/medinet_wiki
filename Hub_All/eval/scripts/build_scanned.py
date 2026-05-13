"""Build 2 scanned PDF từ DOCX gốc — phục vụ eval OCR vie+eng (M1 RAG Quality).

Pipeline 3 bước:

  Step A: DOCX → PDF (có text layer)
          Fallback chain: LibreOffice headless → docx2pdf (Word automation) → pandoc.

  Step B: PDF → list[PIL.Image] @ 150 DPI (mặc định)
          Primary:  pdf2image.convert_from_path (yêu cầu Poppler binary).
          Fallback: PyMuPDF (`pymupdf`) — pure-Python wheel, KHÔNG cần Poppler.
                    Thêm vào để Windows executor không có Poppler vẫn build được
                    (deviation Rule 3 — blocking environment).

  Step C: list[PIL.Image] → PDF image-only (không có text layer)
          img2pdf.convert([png_bytes, ...]).

  Verify: dùng `pypdf.PdfReader.extract_text()` cho cả 2 file output — assert
          tổng số ký tự non-whitespace < 50 (img2pdf đôi khi sinh whitespace
          artifact rất nhỏ, vẫn được coi là "không có text layer thực").

Output:
  eval/dataset/scanned/DMD_T1-01_scanned.pdf   (từ DMD_T1-01_DinhVi_TrungTam_v1.docx)
  eval/dataset/scanned/DMD_T1-04_scanned.pdf   (từ DMD_T1-04_FAQ_ThuongHieu_v1.docx)

Sử dụng:
  python eval/scripts/build_scanned.py                     # build cả 2 file (skip nếu đã có)
  python eval/scripts/build_scanned.py --force             # rebuild kể cả khi đã có output
  python eval/scripts/build_scanned.py --dpi 200           # đổi DPI rasterize
  python eval/scripts/build_scanned.py --only DMD_T1-01_DinhVi_TrungTam_v1.docx

Output cuối cùng (stdout, JSON 1 dòng) để CI/eval orchestrator parse:
  {"built": ["DMD_T1-01_scanned.pdf", "DMD_T1-04_scanned.pdf"],
   "verified_no_text_layer": true}

Tham chiếu:
- CONTEXT.md mục B (decision dùng pipeline DOCX → PDF text → raster → PDF image-only).
- backend/internal/rag/extractor/pdf.go:52 (lỗi "no text extracted" mà file output PHẢI
  trigger được — bằng chứng cho gap mà Docling OCR đóng ở Phase 2).
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import subprocess
import sys
import tempfile
from io import BytesIO
from pathlib import Path

# ─── Logger setup ────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("build_scanned")

# ─── Path constants ──────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCES_DIR = REPO_ROOT / "eval" / "dataset" / "sources"
OUTPUT_DIR = REPO_ROOT / "eval" / "dataset" / "scanned"

# Map DOCX gốc → tên PDF scanned output. Đã chốt ở CONTEXT.md mục B.
SCANNED_SOURCE_MAP: dict[str, str] = {
    "DMD_T1-01_DinhVi_TrungTam_v1.docx": "DMD_T1-01_scanned.pdf",
    "DMD_T1-04_FAQ_ThuongHieu_v1.docx": "DMD_T1-04_scanned.pdf",
}

# Mã exit chuẩn — giúp CI phân biệt root cause.
EXIT_OK = 0
EXIT_BUILD_FAIL = 1
EXIT_NO_CONVERTER = 2  # không có công cụ DOCX → PDF nào (LibreOffice/docx2pdf/pandoc)
EXIT_TEXT_LAYER_LEAK = 3  # output có text layer — fail invariant scanned PDF


# ────────────────────────────────────────────────────────────────────────────
# Step A: DOCX → PDF (có text layer) — fallback chain
# ────────────────────────────────────────────────────────────────────────────


def _try_libreoffice(docx: Path, out_dir: Path) -> Path | None:
    """Chạy LibreOffice headless để convert DOCX → PDF. Trả Path nếu OK, None nếu fail."""
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        logger.debug("LibreOffice không có trong PATH — bỏ qua")
        return None

    expected = out_dir / (docx.stem + ".pdf")
    logger.info("Step A [LibreOffice]: %s → %s", docx.name, expected.name)
    try:
        subprocess.run(
            [
                soffice,
                "--headless",
                "--convert-to",
                "pdf",
                "--outdir",
                str(out_dir),
                str(docx),
            ],
            check=True,
            timeout=180,
            capture_output=True,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        logger.warning("LibreOffice fail (%s) — thử fallback tiếp", e)
        return None

    if expected.exists() and expected.stat().st_size > 0:
        return expected
    logger.warning("LibreOffice chạy xong nhưng không sinh file %s", expected)
    return None


def _try_docx2pdf(docx: Path, out_dir: Path) -> Path | None:
    """Dùng docx2pdf (Windows + MS Word, hoặc macOS). Trả Path nếu OK, None nếu fail."""
    try:
        from docx2pdf import convert  # type: ignore[import-not-found]
    except ImportError:
        logger.debug("docx2pdf chưa cài — bỏ qua")
        return None

    expected = out_dir / (docx.stem + ".pdf")
    logger.info("Step A [docx2pdf]: %s → %s", docx.name, expected.name)
    try:
        convert(str(docx), str(expected))
    except Exception as e:  # docx2pdf raise nhiều loại lỗi COM, bắt rộng cho an toàn
        logger.warning("docx2pdf fail (%s) — thử fallback tiếp", e)
        return None

    if expected.exists() and expected.stat().st_size > 0:
        return expected
    return None


def _try_pandoc(docx: Path, out_dir: Path) -> Path | None:
    """Dùng pandoc + wkhtmltopdf. Trả Path nếu OK, None nếu fail."""
    pandoc = shutil.which("pandoc")
    if not pandoc:
        logger.debug("pandoc không có trong PATH — bỏ qua")
        return None

    expected = out_dir / (docx.stem + ".pdf")
    logger.info("Step A [pandoc]: %s → %s", docx.name, expected.name)
    try:
        subprocess.run(
            [pandoc, str(docx), "-o", str(expected), "--pdf-engine=wkhtmltopdf"],
            check=True,
            timeout=180,
            capture_output=True,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        logger.warning("pandoc fail (%s)", e)
        return None

    if expected.exists() and expected.stat().st_size > 0:
        return expected
    return None


def convert_docx_to_pdf(docx: Path, out_dir: Path) -> Path:
    """Convert DOCX → PDF qua fallback chain. Raise RuntimeError nếu cả 3 đều fail."""
    for attempt in (_try_libreoffice, _try_docx2pdf, _try_pandoc):
        result = attempt(docx, out_dir)
        if result is not None:
            return result

    raise RuntimeError(
        f"Không có converter DOCX → PDF nào hoạt động cho {docx.name}.\n"
        "  Cài 1 trong 3 giải pháp:\n"
        "    1) LibreOffice (khuyến nghị — cross-platform): "
        "thêm `soffice` vào PATH.\n"
        "       Windows mặc định: C:\\Program Files\\LibreOffice\\program\\soffice.exe\n"
        "    2) docx2pdf (Windows + MS Word, hoặc macOS): pip install docx2pdf\n"
        "    3) pandoc + wkhtmltopdf"
    )


# ────────────────────────────────────────────────────────────────────────────
# Step B: PDF → list[PNG bytes] @ DPI
# ────────────────────────────────────────────────────────────────────────────


def _rasterize_with_pdf2image(pdf: Path, dpi: int) -> list[bytes]:
    """Primary: pdf2image (cần Poppler binary trong PATH)."""
    from pdf2image import convert_from_path  # type: ignore[import-not-found]

    logger.info("Step B [pdf2image]: %s @ %d DPI", pdf.name, dpi)
    images = convert_from_path(str(pdf), dpi=dpi)
    out: list[bytes] = []
    for img in images:
        # Đảm bảo mode RGB cho img2pdf (img2pdf không nhận RGBA/CMYK trực tiếp).
        if img.mode != "RGB":
            img = img.convert("RGB")
        buf = BytesIO()
        img.save(buf, format="PNG")
        out.append(buf.getvalue())
    logger.info("  → %d page rasterized", len(out))
    return out


def _rasterize_with_pymupdf(pdf: Path, dpi: int) -> list[bytes]:
    """Fallback: PyMuPDF (pure-Python wheel, KHÔNG cần Poppler).

    Lý do thêm: Windows executor thường không có Poppler. Giữ pdf2image
    primary để khớp PLAN; fallback này đảm bảo build chạy được trên
    môi trường dev Windows mà không phải cài Poppler thủ công.
    """
    import pymupdf  # type: ignore[import-not-found]

    logger.info("Step B [pymupdf]: %s @ %d DPI", pdf.name, dpi)
    # PyMuPDF default 72 DPI; scale matrix theo DPI yêu cầu.
    zoom = dpi / 72.0
    matrix = pymupdf.Matrix(zoom, zoom)
    out: list[bytes] = []
    with pymupdf.open(str(pdf)) as doc:
        for page in doc:
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            out.append(pix.tobytes("png"))
    logger.info("  → %d page rasterized", len(out))
    return out


def pdf_to_images(pdf: Path, dpi: int) -> list[bytes]:
    """Render mỗi page PDF thành PNG bytes, in-memory. Primary pdf2image, fallback pymupdf."""
    # Primary path: pdf2image (PLAN mặc định).
    try:
        # pdf2image require Poppler — nếu Poppler không có nó raise PDFInfoNotInstalledError.
        return _rasterize_with_pdf2image(pdf, dpi)
    except Exception as e:  # bắt rộng để fallback pymupdf an toàn
        logger.warning(
            "pdf2image fail (%s) — thử fallback pymupdf (cài Poppler để dùng pdf2image)",
            e,
        )

    # Fallback: pymupdf — pure Python.
    try:
        return _rasterize_with_pymupdf(pdf, dpi)
    except ImportError as e:
        raise RuntimeError(
            "Cả pdf2image lẫn pymupdf đều không khả dụng. "
            "Cài Poppler (cho pdf2image) HOẶC `pip install pymupdf`."
        ) from e


# ────────────────────────────────────────────────────────────────────────────
# Step C: list[PNG bytes] → PDF image-only
# ────────────────────────────────────────────────────────────────────────────


def images_to_image_pdf(png_list: list[bytes], out_pdf: Path) -> None:
    """Ghép list PNG bytes thành PDF image-only (KHÔNG có text layer)."""
    import img2pdf  # type: ignore[import-not-found]

    if not png_list:
        raise ValueError("Không có page nào để ghép — kiểm tra step B")

    logger.info("Step C [img2pdf]: %d page → %s", len(png_list), out_pdf.name)
    out_pdf.parent.mkdir(parents=True, exist_ok=True)
    pdf_bytes = img2pdf.convert(png_list)
    out_pdf.write_bytes(pdf_bytes)


# ────────────────────────────────────────────────────────────────────────────
# Verify: PDF không có text layer
# ────────────────────────────────────────────────────────────────────────────


def verify_no_text_layer(pdf: Path, max_chars: int = 50) -> int:
    """Đọc text layer bằng pypdf — assert tổng ký tự non-whitespace < max_chars.

    Trả về số ký tự non-whitespace thực tế (để log).
    Raise AssertionError nếu vượt ngưỡng — nghĩa là output VẪN có text layer thật,
    pipeline build_scanned bị bug và phải fix trước khi commit.
    """
    from pypdf import PdfReader  # type: ignore[import-not-found]

    reader = PdfReader(str(pdf))
    text = "".join((p.extract_text() or "") for p in reader.pages)
    char_count = len(text.strip())
    if char_count >= max_chars:
        raise AssertionError(
            f"{pdf.name} CÒN text layer ({char_count} ký tự non-whitespace) — "
            "pipeline build_scanned không tạo ra image-only PDF như kỳ vọng."
        )
    logger.info(
        "✓ %s không có text layer thực (text non-whitespace = %d chars, ngưỡng < %d)",
        pdf.name,
        char_count,
        max_chars,
    )
    return char_count


# ────────────────────────────────────────────────────────────────────────────
# Build orchestration
# ────────────────────────────────────────────────────────────────────────────


def build_one(docx_name: str, out_name: str, dpi: int, force: bool) -> bool:
    """Build 1 file. Trả True nếu file output tồn tại (mới build hoặc đã có sẵn)."""
    docx_path = SOURCES_DIR / docx_name
    out_path = OUTPUT_DIR / out_name

    if not docx_path.exists():
        raise FileNotFoundError(
            f"Không tìm thấy DOCX nguồn: {docx_path}. "
            "Plan 01-01 phải copy 8 file source vào eval/dataset/sources/ trước."
        )

    if out_path.exists() and not force:
        logger.info(
            "✓ %s đã tồn tại (%d bytes) — skip (dùng --force để rebuild)",
            out_path.name,
            out_path.stat().st_size,
        )
        return True

    with tempfile.TemporaryDirectory(prefix="eval_scanned_") as tmp:
        tmp_dir = Path(tmp)
        text_pdf = convert_docx_to_pdf(docx_path, tmp_dir)
        png_list = pdf_to_images(text_pdf, dpi)
        images_to_image_pdf(png_list, out_path)

    verify_no_text_layer(out_path)
    logger.info(
        "Build hoàn tất: %s (%d bytes)", out_path.name, out_path.stat().st_size
    )
    return out_path.exists()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build scanned PDF giả lập từ DOCX gốc cho eval RAG.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Rebuild kể cả khi file output đã tồn tại.",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=150,
        help="DPI rasterize mỗi page (mặc định 150).",
    )
    parser.add_argument(
        "--only",
        type=str,
        default=None,
        metavar="DOCX_NAME",
        help=(
            "Chỉ build 1 file (truyền tên DOCX gốc, ví dụ "
            "DMD_T1-01_DinhVi_TrungTam_v1.docx)."
        ),
    )
    args = parser.parse_args(argv)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if args.only:
        if args.only not in SCANNED_SOURCE_MAP:
            logger.error(
                "--only %s không có trong SCANNED_SOURCE_MAP. Hợp lệ: %s",
                args.only,
                ", ".join(SCANNED_SOURCE_MAP.keys()),
            )
            return EXIT_BUILD_FAIL
        targets = [(args.only, SCANNED_SOURCE_MAP[args.only])]
    else:
        targets = list(SCANNED_SOURCE_MAP.items())

    built: list[str] = []
    for docx_name, out_name in targets:
        try:
            if build_one(docx_name, out_name, args.dpi, args.force):
                built.append(out_name)
        except RuntimeError as e:
            # Không có converter DOCX → PDF nào — exit code riêng.
            logger.error("%s", e)
            return EXIT_NO_CONVERTER
        except AssertionError as e:
            logger.error("%s", e)
            return EXIT_TEXT_LAYER_LEAK
        except Exception as e:  # bắt rộng để CI nhận exit code 1 + log nguyên nhân
            logger.error("Build %s thất bại: %s", out_name, e)
            return EXIT_BUILD_FAIL

    # Output JSON 1 dòng cuối — CI/eval orchestrator có thể parse.
    summary = {"built": built, "verified_no_text_layer": True}
    print(json.dumps(summary, ensure_ascii=False))
    logger.info("Hoàn tất: %d/%d file ở %s", len(built), len(targets), OUTPUT_DIR)
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
