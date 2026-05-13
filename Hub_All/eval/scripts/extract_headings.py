"""Extract heading path từ DOCX styles — port từ backend/internal/rag/extractor/docx.go:46-95.

Thuật toán chính (port nguyên từ Go):
1. Mở DOCX (zip) → đọc word/styles.xml.
2. Với mỗi <w:style w:styleId="X">, tìm <w:outlineLvl w:val="N"/> → headingLevel = N+1.
3. Fallback hard-coded: styleId "Heading1".."Heading6" → level 1..6.
4. Đọc word/document.xml, duyệt RECURSIVE <w:p> (kể cả trong <w:tbl>), lookup pStyle.
5. Stack-based heading path: stack[level-1] = title; output " > ".join(stack).

Fallback heuristic (DEVIATION RULE 2 — Plan 04 W4):
- Đa số DMD DOCX trong dataset KHÔNG dùng pStyle "HeadingN" mà render heading bằng
  inline format (font size + bold + emoji prefix). Logic Go thuần sẽ trả 0 heading
  cho 7 file này → Phase 5 không thể đo heading recall.
- Khi pStyle map cho doc trống → áp regex pattern detection trên text:
    L1: PHẦN N |, CHƯƠNG N |, TRỤ N —, MỤC LỤC, PHỤ LỤC, MỤC ĐÍCH, VAI TRÒ CỦA, KIẾN TRÚC X —
    L2: ▸ N.M, NHÓM [A-Z] |, QN.M
- Heuristic này KHÔNG perfect (có thể miss/false positive) nhưng cover đủ cấu trúc
  rõ ràng của DMD docs để Phase 5 có ground truth đo recall.

PDF gốc + 2 scanned PDF: heading manual (extractor Go unreliable cho PDF; scanned PDF
chưa OCR).
  - PDF gốc `tri_thuc_chinh_tri.pdf` → manual entry trong code (constant
    MANUAL_PDF_HEADINGS), LLM-draft từ pypdf.
  - 2 scanned PDF → copy heading từ DOCX gốc (cùng nguồn, ground truth Phase 5 OCR).

Chạy: python eval/scripts/extract_headings.py
"""

from __future__ import annotations

import json
import logging
import re
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCES_DIR = REPO_ROOT / "eval" / "dataset" / "sources"
SCANNED_DIR = REPO_ROOT / "eval" / "dataset" / "scanned"
OUTPUT_JSON = REPO_ROOT / "eval" / "dataset" / "headings.json"

NS_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

# Mapping scanned PDF ↔ DOCX gốc (CONTEXT.md mục B).
# Heading vàng của 2 scanned PDF được COPY nguyên từ DOCX gốc tương ứng — Phase 5 OCR
# sẽ đo recall trên đúng list này (Docling phải recover heading về như DOCX gốc).
SCANNED_SOURCE_MAP = {
    "DMD_T1-01_scanned.pdf": "DMD_T1-01_DinhVi_TrungTam_v1.docx",
    "DMD_T1-04_scanned.pdf": "DMD_T1-04_FAQ_ThuongHieu_v1.docx",
}

# Manual heading vàng cho PDF gốc — extractor Go heading detection cho PDF unreliable.
# Đã được LLM-draft (Plan 04 Task 2) bằng cách đọc 5 trang đầu của PDF qua pypdf.
# Cấu trúc PDF: 1 title document (lvl1) + 10 section flat (lvl2 — đánh số 1..7,
# Tóm tắt, Kết luận, Tài liệu Tham khảo). PDF không có TOC bookmark
# (reader.outline rỗng) → nhận diện heading bằng heuristic regex `^\d+\. ` đầu dòng.
# User review trong Plan 05 checkpoint (gộp với queries review).
MANUAL_PDF_HEADINGS: dict[str, list[str]] = {
    "tri_thuc_chinh_tri.pdf": [
        "TRI THỨC CHÍNH TRỊ",
        "TRI THỨC CHÍNH TRỊ > Tóm tắt",
        "TRI THỨC CHÍNH TRỊ > 1. Khái niệm và Bản chất của Tri thức Chính trị",
        "TRI THỨC CHÍNH TRỊ > 2. Các Thành phần Cốt lõi của Tri thức Chính trị",
        "TRI THỨC CHÍNH TRỊ > 3. Vai trò của Tri thức Chính trị trong Xã hội Hiện đại",
        "TRI THỨC CHÍNH TRỊ > 4. Thực trạng Tri thức Chính trị ở Việt Nam",
        "TRI THỨC CHÍNH TRỊ > 5. Thách thức trong Kỷ nguyên Số",
        "TRI THỨC CHÍNH TRỊ > 6. Giải pháp Nâng cao Tri thức Chính trị",
        "TRI THỨC CHÍNH TRỊ > 7. Tri thức Chính trị và Phát triển Bền vững",
        "TRI THỨC CHÍNH TRỊ > Kết luận",
        "TRI THỨC CHÍNH TRỊ > Tài liệu Tham khảo",
    ],
}

# ──── Heuristic regex cho fallback detection (RULE 2 deviation) ────
# Lvl 1: section đầu mục (PHẦN/CHƯƠNG/PHỤ LỤC/MỤC LỤC/MỤC ĐÍCH/TRỤ N)
RE_LVL1_PATTERNS = [
    re.compile(r"^PHẦN\s+\d+\s*\|", re.UNICODE),
    re.compile(r"^CHƯƠNG\s+\d+\s*\|", re.UNICODE),
    re.compile(r"^TRỤ\s+\d+\s*[—-]", re.UNICODE),
    re.compile(r"^MỤC\s+LỤC\b", re.UNICODE),
    re.compile(r"^PHỤ\s+LỤC\b", re.UNICODE),
    re.compile(r"^MỤC\s+ĐÍCH\b", re.UNICODE),
    re.compile(r"^VAI\s+TRÒ\s+CỦA\b", re.UNICODE),
    re.compile(r"^KIẾN\s+TRÚC\s+\w+\s*[—-]", re.UNICODE),
]

# Lvl 2: subsection có numbering (1.1, 1.2 ...) hoặc nhóm con (NHÓM A | ..., Q3.1 ...)
# Hoặc bullet IN HOA dùng làm tiêu đề mục con trong T5-02 Playbook.
RE_LVL2_PATTERNS = [
    re.compile(r"^▸\s*\d+\.\d+\b"),
    re.compile(r"^NHÓM\s+[A-Z]\s*\|", re.UNICODE),
    re.compile(r"^Q\d+\.\d+\b"),
    re.compile(r"^▸\s+[A-ZÀ-Ỹ][A-ZÀ-Ỹ\s&]{3,}$", re.UNICODE),
]

# Channel/section names được dùng như heading lvl1 trong Playbook T5-02
# (lone token, IN HOA, không có punctuation). Whitelist để tránh false-positive.
KNOWN_LVL1_TOKENS = {
    "FACEBOOK",
    "TIKTOK",
    "YOUTUBE",
    "WEBSITE",
    "PR",
    "ZALO",
    "INSTAGRAM",
}


def detect_heading_heuristic(text: str) -> int:
    """Trả về heading level từ regex pattern (0 = không phải heading)."""
    if text in KNOWN_LVL1_TOKENS:
        return 1
    for pat in RE_LVL1_PATTERNS:
        if pat.match(text):
            return 1
    for pat in RE_LVL2_PATTERNS:
        if pat.match(text):
            return 2
    return 0


def parse_docx_styles(docx_path: Path) -> dict[str, int]:
    """Trả về map {styleId: headingLevel}. headingLevel=0 nghĩa không phải heading.

    Port từ docx.go:47-94 (parseDocxStyles):
    - Đọc word/styles.xml trong DOCX zip.
    - Với mỗi <w:style w:styleId="X">, tìm <w:outlineLvl w:val="N"/> → level = N+1
      (Word lưu 0-based: outlineLvl=0 nghĩa Heading1).
    - Fallback hard-coded: nếu styleId là "Heading1".."Heading6" và chưa có entry,
      gán level = số (1..6) — giống docx.go:88-93.
    """
    styles: dict[str, int] = {}
    tree: ET.ElementTree | None = None

    with zipfile.ZipFile(docx_path) as z:
        try:
            with z.open("word/styles.xml") as f:
                tree = ET.parse(f)
        except KeyError:
            logger.warning("%s không có word/styles.xml", docx_path.name)

    if tree is not None:
        for style_el in tree.findall(f"{NS_W}style"):
            style_id = style_el.get(f"{NS_W}styleId")
            if not style_id:
                continue
            outline = style_el.find(f".//{NS_W}outlineLvl")
            if outline is not None:
                val = outline.get(f"{NS_W}val")
                if val is not None and val.isdigit():
                    # Go: headingLevel = N + 1 (0-based → 1-based)
                    styles[style_id] = int(val) + 1

    # Fallback hard-coded (docx.go:88-93)
    for i in range(1, 7):
        styles.setdefault(f"Heading{i}", i)
    return styles


def _iter_paragraph_levels(
    body: ET.Element,
    styles: dict[str, int],
) -> list[tuple[int, str]]:
    """Duyệt RECURSIVE <w:p> (gồm cả paragraph trong table) → list (level, text).

    Logic 2 tầng:
    1. PRIMARY (port từ Go): pStyle → styles map → level. Nếu doc dùng styleId
       chuẩn (Heading1..6 hoặc style có outlineLvl), đây là path duy nhất chạy.
    2. FALLBACK heuristic (RULE 2): chỉ kích hoạt khi PRIMARY không tìm được
       heading nào → áp regex pattern trên text (DMD docs render heading bằng
       inline format, không pStyle).
    """
    primary: list[tuple[int, str]] = []
    fallback: list[tuple[int, str]] = []
    seen_text: set[str] = set()

    for para in body.findall(f".//{NS_W}p"):
        text_runs = [t.text or "" for t in para.findall(f".//{NS_W}t")]
        text = "".join(text_runs).strip()
        if not text:
            continue

        # PRIMARY: pStyle lookup
        p_style = para.find(f".//{NS_W}pStyle")
        primary_level = 0
        if p_style is not None:
            style_id = p_style.get(f"{NS_W}val")
            primary_level = styles.get(style_id, 0) if style_id else 0
        if 1 <= primary_level <= 6:
            primary.append((primary_level, text))
            continue

        # FALLBACK: heuristic regex (chỉ collect — quyết định dùng primary hay
        # fallback ở caller, sau khi đã duyệt hết doc)
        h_level = detect_heading_heuristic(text)
        if h_level > 0 and text not in seen_text:
            seen_text.add(text)
            fallback.append((h_level, text))

    if primary:
        return primary
    return fallback


def extract_heading_paths(docx_path: Path) -> list[str]:
    """Duyệt body paragraphs, build heading path nối bằng " > ".

    Port từ docx.go:97-265 (parseDocxStructured) — chỉ giữ phần heading:
    - Recursive `.//<w:p>` (Go decoder cũng đi qua tất cả <w:p>, gồm trong table).
    - PRIMARY: pStyle → styles map → level (port chính xác từ Go).
    - FALLBACK heuristic khi doc không có pStyle heading nào (RULE 2 deviation).
    - Stack-based heading path: stack[level-1] = title; output " > ".join(stack).

    Path nối bằng " > " — khớp schema queries.jsonl `expected_section` (CONTEXT mục A).
    """
    styles = parse_docx_styles(docx_path)

    with zipfile.ZipFile(docx_path) as z, z.open("word/document.xml") as f:
        tree = ET.parse(f)

    body = tree.getroot().find(f"{NS_W}body")
    if body is None:
        logger.warning("%s không có <w:body>", docx_path.name)
        return []

    leveled = _iter_paragraph_levels(body, styles)
    paths: list[str] = []
    stack: list[str] = []  # stack[i] = title của heading level (i+1)

    for level, title in leveled:
        # Truncate stack về đúng độ sâu (level-1) rồi push title mới
        del stack[level - 1 :]
        stack.append(title)
        paths.append(" > ".join(stack))

    return paths


def main() -> int:
    """Entry point CLI: extract auto từ DOCX + manual cho PDF + copy cho scanned PDF."""
    if not SOURCES_DIR.exists():
        logger.error("Không tìm thấy %s — chạy Plan 01 trước", SOURCES_DIR)
        return 1

    headings: dict[str, list[str]] = {}

    # 1. Extract auto từ tất cả DOCX trong sources/
    for docx in sorted(SOURCES_DIR.glob("*.docx")):
        try:
            paths = extract_heading_paths(docx)
            headings[docx.name] = paths
            logger.info("OK %s: %d heading", docx.name, len(paths))
        except Exception as e:
            logger.error("FAIL %s: %s", docx.name, e)
            return 2

    # 2. Manual cho PDF gốc — REVISION 1 (W4): bắt buộc có ≥ 1 entry
    for pdf_name, manual_paths in MANUAL_PDF_HEADINGS.items():
        pdf_path = SOURCES_DIR / pdf_name
        if pdf_path.exists():
            headings[pdf_name] = manual_paths
            if not manual_paths:
                logger.error(
                    "FAIL %s có entry manual nhưng list rỗng — Plan 04 Task 2 phải fill "
                    "MANUAL_PDF_HEADINGS trước khi chạy lại.",
                    pdf_name,
                )
                return 3
            logger.info("OK %s (manual): %d heading", pdf_name, len(manual_paths))
        else:
            logger.warning("Bỏ qua %s — file không tồn tại", pdf_name)

    # 3. Scanned PDF — copy heading từ DOCX gốc tương ứng (ground truth Phase 5 OCR)
    for scanned_name, source_docx in SCANNED_SOURCE_MAP.items():
        scanned_path = SCANNED_DIR / scanned_name
        if not scanned_path.exists():
            logger.warning(
                "Bỏ qua %s — file chưa tồn tại (Plan 03 chưa chạy?). "
                "Sau khi Plan 03 sinh scanned PDF, chạy lại script để bổ sung.",
                scanned_name,
            )
            continue
        if source_docx in headings:
            headings[scanned_name] = headings[source_docx]
            logger.info(
                "OK %s (copy từ %s): %d heading",
                scanned_name,
                source_docx,
                len(headings[scanned_name]),
            )

    # 4. Sanity check: phải có ≥ 7 DOCX
    docx_count = sum(1 for k in headings if k.endswith(".docx"))
    if docx_count < 7:
        logger.error("Chỉ có %d DOCX có heading — kỳ vọng ≥ 7", docx_count)
        return 4

    # 5. Sanity: mỗi DOCX nên có ≥ 3 heading (nếu không, có thể style chưa cover)
    weak_docs = [k for k, v in headings.items() if k.endswith(".docx") and len(v) < 3]
    if weak_docs:
        logger.warning(
            "Các DOCX có < 3 heading — có thể logic detect chưa cover hết: %s",
            weak_docs,
        )

    # 6. Write JSON (UTF-8, không escape Unicode tiếng Việt)
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(
        json.dumps(headings, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    logger.info(
        "Đã ghi %s — %d doc, tổng %d heading path",
        OUTPUT_JSON,
        len(headings),
        sum(len(v) for v in headings.values()),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
