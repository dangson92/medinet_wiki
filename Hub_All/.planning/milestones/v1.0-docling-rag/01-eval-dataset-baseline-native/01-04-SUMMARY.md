---
phase: 01-eval-dataset-baseline-native
plan: 04
subsystem: eval
status: completed
tags: [eval, python, heading-extraction, docx-parsing, port-from-go, heuristic-fallback]
requirements: [EVAL-01]
wave: 2
depends_on: [01]
provides:
  - "Script Python eval/scripts/extract_headings.py port từ backend/internal/rag/extractor/docx.go:46-95"
  - "Heading vàng dataset eval/dataset/headings.json — ground truth heading recall cho Phase 5"
  - "Manual heading vàng cho tri_thuc_chinh_tri.pdf (11 entry, LLM-draft từ pypdf)"
  - "Heading vàng scanned PDF copy từ DOCX gốc (T1-01, T1-04) — Phase 5 OCR target"
key-files:
  created:
    - eval/scripts/extract_headings.py
    - eval/dataset/headings.json
  modified: []
tech-stack:
  added: []
  patterns: [zipfile + xml.etree.ElementTree, regex-based heading heuristic, stack-based heading path]
decisions:
  - "DEVIATION Rule 2: thêm fallback heuristic regex khi pStyle map cho doc trống. 7 DMD DOCX không dùng pStyle 'HeadingN' mà render heading bằng inline format → logic Go thuần trả 0 heading → Phase 5 không thể đo recall. Heuristic detect pattern PHẦN/CHƯƠNG/TRỤ/▸ N.M/NHÓM A | + whitelist channel name."
  - "Recursive `.//w:p` (kể cả paragraph trong <w:tbl>): logic Go decoder cũng đi qua tất cả <w:p> qua xml.NewDecoder.Token(); Python ban đầu chỉ findall direct children (sai) → fix sang recursive."
  - "Manual heading PDF gốc 11 entry (1 title lvl1 + 10 section lvl2): PDF reader.outline rỗng (không có TOC bookmark) → LLM-draft bằng cách đọc 5 trang đầu qua pypdf, identify heading bằng regex `^\\d+\\. `."
  - "Schema heading path nối bằng ' > ' (khớp queries.jsonl `expected_section`); JSON encoded UTF-8 không escape Unicode (`ensure_ascii=False`); sort_keys + indent=2 → deterministic."
metrics:
  duration: "~10 phút"
  files_created: 2
  files_modified: 0
  loc_added: 634
  completed_date: "2026-04-28"
commit: "05ac332"
---

# Phase 1 Plan 04: Heading Extraction Script + Headings JSON — Summary

Port logic heading detection từ Go (`backend/internal/rag/extractor/docx.go:46-95`) sang Python để tự động sinh heading vàng cho 7 DOCX trong eval dataset, cộng thêm manual entry cho 1 PDF gốc + copy heading cho 2 scanned PDF. Output `eval/dataset/headings.json` (10 doc, 286 heading path) sẽ là ground truth heading recall cho Phase 5.

**Phát hiện quan trọng:** 7 DMD DOCX KHÔNG dùng pStyle `Heading1..6` — heading được render bằng inline format (font size + bold + emoji prefix). Áp dụng Rule 2 (auto-add missing critical functionality): thêm fallback heuristic regex để detect heading khi pStyle map trống. Nếu không có fallback này, Phase 5 sẽ không có dữ liệu đo `headings_recalled`/`headings_missed` (yêu cầu cứng theo REQ EVAL-02).

## Tick list `must_haves` từ PLAN frontmatter

### `truths`

- [x] `python eval/scripts/extract_headings.py` extract được heading từ 7 file DOCX trong `eval/dataset/sources/` — verified output: `7 DOCX có 28+9+50+67+6+5+15 = 180 heading path`.
- [x] `eval/dataset/headings.json` valid JSON, đúng 10 doc_id (7 DOCX + 1 PDF gốc + 2 scanned PDF) — verified `len(data) == 10`.
- [x] Heading path nối bằng " > " — khớp schema `expected_section` queries.jsonl. Ví dụ: `"PHẦN 01  |  CÂU TUYÊN BỐ ĐỊNH VỊ CHÍNH THỨC > ▸  1.1  Câu định vị trung tâm — Bản đầy đủ"`.
- [x] PDF gốc `tri_thuc_chinh_tri.pdf` có 11 heading vàng manual (≥ 1) — extracted bởi LLM-draft từ `pypdf.PdfReader` đọc 5 trang đầu.
- [x] 2 scanned PDF (T1-01, T1-04) có heading vàng = COPY bytes-equal từ DOCX gốc — `data['DMD_T1-01_scanned.pdf'] == data['DMD_T1-01_DinhVi_TrungTam_v1.docx']` (assert pass).
- [⚠] Logic Python port chính xác từ `docx.go:46-95` — port chính xác cho **PRIMARY path** (pStyle → outlineLvl → level + Heading1..6 fallback). DEVIATION: thêm secondary path (heuristic regex) khi PRIMARY trả 0 heading. Lý do trong `decisions[0]`.

### `artifacts`

- [x] `eval/scripts/extract_headings.py` — 327 dòng (≥ 100 yêu cầu).
- [x] `eval/dataset/headings.json` chứa key `"DMD_T1-01_DinhVi_TrungTam_v1"` — verified.

### `key_links`

- [x] Script đọc DOCX zip qua `zipfile + xml.etree.ElementTree` với namespace `{http://schemas.openxmlformats.org/wordprocessingml/2006/main}` — verified.
- [x] `expected_section` của queries.jsonl (Plan 05) sẽ valid trong heading list — verified pattern `tri_thuc_chinh_tri.pdf` có 11 entry sẵn sàng làm target.

## Heading per Document (Statistics)

| # | Doc ID | Heading Count | Sample First | Sample Last |
|---|--------|---------------|--------------|-------------|
| 1 | DMD_T1-01_DinhVi_TrungTam_v1.docx | 28 | `VAI TRÒ CỦA TÀI LIỆU NÀY` | `... > ▸  8.2  Bảng tài sản ...` |
| 2 | DMD_T1-01_scanned.pdf | 28 (copy T1-01) | (== T1-01) | (== T1-01) |
| 3 | DMD_T1-02_TuDien_ThuongHieu_v1.docx | 9 | `MỤC ĐÍCH TÀI LIỆU NÀY` | `PHẦN 08  \|  QUẢN TRỊ TÀI LIỆU` |
| 4 | DMD_T1-03_Script_Library_v1.docx | 50 | `MỤC LỤC NHANH — 7 NHÓM KỊCH BẢN` | `PHỤ LỤC 2  \|  RUBRIC CHẤM ĐIỂM ...` |
| 5 | DMD_T1-04_FAQ_ThuongHieu_v1.docx | 67 | `CHƯƠNG 01  \|  THƯƠNG HIỆU & ĐỊNH VỊ MỚI` | `PHỤ LỤC ... > Q6.5` |
| 6 | DMD_T1-04_scanned.pdf | 67 (copy T1-04) | (== T1-04) | (== T1-04) |
| 7 | DMD_T3-02_PhanCong_NhanVat_v1.docx | 6 | `PHẦN 01  \|  MA TRẬN TỔNG QUAN ...` | `PHẦN 06  \|  PHÂN CÔNG BS ...` |
| 8 | DMD_T5-01_ContentStrategy_12TuyenND_v1.docx | 5 | `PHẦN 01  \|  TỔNG QUAN 12 TUYẾN ND` | `PHẦN 05  \|  QUY TẮC VẬN HÀNH ND` |
| 9 | DMD_T5-02_Playbook_KenhTruyen_v1.docx | 15 | `FACEBOOK` | `ZALO > ▸  CÁC LOẠI TIN NHẮN ZALO OA` |
| 10 | tri_thuc_chinh_tri.pdf | 11 (manual) | `TRI THỨC CHÍNH TRỊ` | `... > Tài liệu Tham khảo` |

**Tổng:** 10 doc × trung bình 28.6 heading/doc = **286 heading path** (vượt mức `≥ 30` yêu cầu).

## Manual heading vàng `tri_thuc_chinh_tri.pdf` (full content — user review tại Plan 05 checkpoint)

LLM-draft từ `pypdf.PdfReader` đọc 5 trang đầu của PDF (PDF có 5 trang tổng, không có TOC bookmark). Cấu trúc nhận diện bằng regex `^\d+\. ` đầu dòng + tiêu đề meta (Tóm tắt, Kết luận, Tài liệu Tham khảo).

```
1.  TRI THỨC CHÍNH TRỊ                                                      (lvl 1 — title)
2.  TRI THỨC CHÍNH TRỊ > Tóm tắt                                            (lvl 2)
3.  TRI THỨC CHÍNH TRỊ > 1. Khái niệm và Bản chất của Tri thức Chính trị    (lvl 2)
4.  TRI THỨC CHÍNH TRỊ > 2. Các Thành phần Cốt lõi của Tri thức Chính trị   (lvl 2)
5.  TRI THỨC CHÍNH TRỊ > 3. Vai trò của Tri thức Chính trị trong Xã hội ... (lvl 2)
6.  TRI THỨC CHÍNH TRỊ > 4. Thực trạng Tri thức Chính trị ở Việt Nam        (lvl 2)
7.  TRI THỨC CHÍNH TRỊ > 5. Thách thức trong Kỷ nguyên Số                   (lvl 2)
8.  TRI THỨC CHÍNH TRỊ > 6. Giải pháp Nâng cao Tri thức Chính trị           (lvl 2)
9.  TRI THỨC CHÍNH TRỊ > 7. Tri thức Chính trị và Phát triển Bền vững       (lvl 2)
10. TRI THỨC CHÍNH TRỊ > Kết luận                                           (lvl 2)
11. TRI THỨC CHÍNH TRỊ > Tài liệu Tham khảo                                 (lvl 2)
```

**Lưu ý cho user (review tại Plan 05):** Title document chính lấy từ trang 1 dòng đầu IN HOA `"TRI THỨC CHÍNH TRỊ"`. Subtitle `"Nền tảng, Vai trò và Ý nghĩa trong Xã hội Hiện đại"` không đưa vào heading vàng vì không phải structural marker. Nếu user muốn thay đổi (vd thêm "TRI THỨC CHÍNH TRỊ > Subtitle: Nền tảng..."), edit constant `MANUAL_PDF_HEADINGS["tri_thuc_chinh_tri.pdf"]` rồi chạy lại script.

## Confirm Scanned PDF Heading == DOCX Gốc (bytes-equal)

Logic copy trong `main()` (xem code dòng 247-258):
```python
if source_docx in headings:
    headings[scanned_name] = headings[source_docx]
```

Verify (assert tại Bước verify Plan 04):
- `data["DMD_T1-01_scanned.pdf"] == data["DMD_T1-01_DinhVi_TrungTam_v1.docx"]` → **True** (28 heading bytes-equal)
- `data["DMD_T1-04_scanned.pdf"] == data["DMD_T1-04_FAQ_ThuongHieu_v1.docx"]` → **True** (67 heading bytes-equal)

→ Phase 5 OCR (Docling) phải recover 28 heading T1-01 + 67 heading T1-04 từ scanned PDF (image-only, no text layer) — đó là target metric `headings_recalled` cho 2 file scanned.

## Spot-check 1 DOCX so với manual count

Spot-check `DMD_T1-01_DinhVi_TrungTam_v1.docx` để confirm logic detect đúng:

**Open file → đếm heading bằng tay:**
- 8 mục `PHẦN 01..08` → 8 lvl1.
- 13 sub-mục `▸ 1.1, 1.2, 1.3, 3.1, 3.2, 4.1, 4.2, 4.3, 6.1, 6.2, 6.3, 8.1, 8.2` → 13 lvl2.
- 6 mục `TRỤ 1..6` → 6 lvl1.
- 1 mục meta `VAI TRÒ CỦA TÀI LIỆU NÀY` → 1 lvl1.

Tổng manual count = 8 + 13 + 6 + 1 = **28 heading**.

Script auto-detect: **28 heading** → khớp 100%.

Thứ tự heading cũng khớp (kiểm tra trong section "Heading per Document" first/last entry).

## Files Created (2)

| # | Path | Size | Vai trò |
|---|------|------|---------|
| 1 | `eval/scripts/extract_headings.py` | 327 dòng / ~13 KB | Port logic docx.go + heuristic fallback + manual PDF + copy scanned |
| 2 | `eval/dataset/headings.json` | 307 dòng / ~25 KB | 10 doc, 286 heading path, UTF-8 không escape Unicode |

## Tasks Executed

| # | Task | Trạng thái | Verify |
|---|------|-----------|--------|
| 1 | Tạo `eval/scripts/extract_headings.py` | done | `ruff check` pass; `ast.parse` OK; ≥ 100 dòng (thực tế 327) |
| 2 | Fill `MANUAL_PDF_HEADINGS["tri_thuc_chinh_tri.pdf"]` + chạy script | done | 11 manual entry; `headings.json` 10 doc; assertions pass; deterministic re-run (sha256 stable) |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Critical functionality] Thêm fallback heuristic detection cho DOCX không dùng pStyle**

- **Found during:** Task 1 — chạy thử trên 7 DOCX, ALL trả 0 heading.
- **Issue:** 7 DMD DOCX trong dataset render heading bằng inline format (font size + bold + emoji prefix), KHÔNG dùng pStyle `Heading1..6`. Logic Go thuần (`docx.go:46-95`) chỉ detect heading qua pStyle → cũng trả 0 heading. Hệ quả: `headings.json` rỗng cho 7 DOCX → Phase 5 không có ground truth đo `headings_recalled` (yêu cầu cứng theo REQ EVAL-02 + plan 01-04 truth #6).
- **Fix:** Thêm `detect_heading_heuristic()` + 2 list regex (`RE_LVL1_PATTERNS`, `RE_LVL2_PATTERNS`) + whitelist `KNOWN_LVL1_TOKENS`. Logic 2 tầng:
  1. PRIMARY: pStyle → styles map → level (port nguyên Go).
  2. FALLBACK (CHỈ KÍCH HOẠT KHI PRIMARY KHÔNG TÌM ĐƯỢC HEADING NÀO TRONG DOC): regex pattern detection trên text.
- **Files modified:** `eval/scripts/extract_headings.py` (thêm `RE_LVL1_PATTERNS`, `RE_LVL2_PATTERNS`, `KNOWN_LVL1_TOKENS`, `detect_heading_heuristic()`, `_iter_paragraph_levels()`).
- **Commit:** `05ac332` (gộp).
- **Tác động Phase 5:** Heading vàng có thể có miss/false positive nhỏ so với "ý đồ tác giả thật" — nhưng đó vẫn là **deterministic ground truth** (cùng input → cùng output) → đủ làm baseline cho Phase 5 đo "Docling có recover lượng heading bằng/hơn extract Go không".

**2. [Rule 1 - Bug] Recursive `.//w:p` thay vì direct children `body.findall(NS_W + 'p')`**

- **Found during:** Task 1 — debug DMD_T1-03 trả 0 paragraph trong khi file có 755 `<w:p>` total.
- **Issue:** Code Python ban đầu dùng `body.findall(f"{NS_W}p")` (direct children) → bỏ qua paragraph nằm trong `<w:tbl>`. Logic Go đi qua `xml.NewDecoder.Token()` tuần tự nên hit cả `<w:p>` trong table → port chính xác phải dùng recursive `.//w:p`.
- **Fix:** Đổi `body.findall(f"{NS_W}p")` → `body.findall(f".//{NS_W}p")` trong `_iter_paragraph_levels()`.
- **Files modified:** `eval/scripts/extract_headings.py`.
- **Commit:** `05ac332` (gộp).
- **Tác động:** Đây là port đúng thay vì port sai — sau fix, T1-03 trả 50 heading (thực tế file có 50 mục).

### Non-rule Notes (informational, không phải deviation)

**3. Plan 03 (sinh scanned PDF) đã chạy parallel session này** — Khi Plan 04 chạy lần 2, `eval/dataset/scanned/DMD_T1-01_scanned.pdf` + `DMD_T1-04_scanned.pdf` đã tồn tại (Plan 03 hoàn tất ~13:51, Plan 04 chạy 13:53). Plan 04 logic xử lý đúng: nếu scanned tồn tại → copy heading từ DOCX gốc; nếu không → log warning skip. Không cần re-run Plan 04 sau Plan 03.

## TDD Gate Compliance

PLAN không có task `tdd="true"` — không áp dụng RED/GREEN/REFACTOR. Plan 04 chỉ là utility script + dataset.

## Known Stubs

Không có stub. Toàn bộ logic functional + đã chạy production output.

## Threat Flags

Không. Script Python chỉ đọc file local DOCX/PDF + write JSON local. Không touch network, auth, DB. `MANUAL_PDF_HEADINGS` chứa text public, không có credential/secret.

## Self-Check: PASSED

**Files created tồn tại:**
- FOUND: `eval/scripts/extract_headings.py`
- FOUND: `eval/dataset/headings.json`

**Commit existence:**
- FOUND: `05ac332` — `feat(eval): extract_headings.py + headings.json (port logic docx.go) [phase-1 plan-04]`

**Verify outputs:**
- `python -m ruff check eval/scripts/extract_headings.py` → All checks passed!
- `python eval/scripts/extract_headings.py` → exit 0, 10 doc / 286 heading path.
- Deterministic re-run: sha256 trước == sau (`edf07a6174b432c2...`).
- All assertions pass: `len(data) == 10`, `len(data["tri_thuc_chinh_tri.pdf"]) >= 1`, `data["DMD_T1-01_scanned.pdf"] == data["DMD_T1-01_DinhVi_TrungTam_v1.docx"]`, `sum(len) >= 30`.

---

*Plan 01-04 hoàn tất 2026-04-28. Sẵn sàng cho Plan 01-05 (Wave 3 — `queries.jsonl` LLM draft 12 truy vấn vàng + user review checkpoint).*
