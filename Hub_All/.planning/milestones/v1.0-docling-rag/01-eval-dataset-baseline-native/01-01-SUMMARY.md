---
phase: 01-eval-dataset-baseline-native
plan: 01
subsystem: eval
status: completed
tags: [eval, python, skeleton, pep621, ruff, dataset]
requirements: [EVAL-01]
wave: 1
depends_on: []
provides:
  - "Thư mục eval/ Python skeleton ở root repo Hub_All"
  - "Convention Python chuẩn (PEP 621 + ruff E/W/F/I/N/UP/B/SIM/RUF + Python>=3.11) — Phase 2 docling-pipeline kế thừa"
  - "8 file source dataset (7 DMD docx + 1 PDF chữ Việt) commit byte-identical với file_test/"
  - "Hướng dẫn install + workflow build dataset + chạy baseline (README 164 dòng)"
key-files:
  created:
    - eval/pyproject.toml
    - eval/README.md
    - eval/.gitignore
    - eval/__init__.py
    - eval/.env.example
    - eval/dataset/sources/DMD_T1-01_DinhVi_TrungTam_v1.docx
    - eval/dataset/sources/DMD_T1-02_TuDien_ThuongHieu_v1.docx
    - eval/dataset/sources/DMD_T1-03_Script_Library_v1.docx
    - eval/dataset/sources/DMD_T1-04_FAQ_ThuongHieu_v1.docx
    - eval/dataset/sources/DMD_T3-02_PhanCong_NhanVat_v1.docx
    - eval/dataset/sources/DMD_T5-01_ContentStrategy_12TuyenND_v1.docx
    - eval/dataset/sources/DMD_T5-02_Playbook_KenhTruyen_v1.docx
    - eval/dataset/sources/tri_thuc_chinh_tri.pdf
  modified: []
tech-stack:
  added: [Python>=3.11, PEP 621, ruff, setuptools, httpx, psycopg, python-docx, pypdf, pdf2image, img2pdf, Pillow, python-dotenv]
  patterns: [PEP 621 pyproject, ruff lint-format, snake_case file naming, Google docstring style]
decisions:
  - "Copy (KHÔNG symlink) 8 file source từ file_test/ → eval/dataset/sources/: file_test/ có thể đổi tương lai, eval cần snapshot bất biến."
  - "Chốt convention Python ngay từ skeleton (ruff target py311, rule set E/W/F/I/N/UP/B/SIM/RUF, line-length 100): Phase 2 docling-pipeline cùng convention."
  - "Bao gồm pypdf>=5.0 trong runtime deps (revision 1 trong PLAN): Plan 03 task 2 verify cần `from pypdf import PdfReader`."
metrics:
  duration: "~12 phút"
  files_created: 13
  files_modified: 0
  loc_added: 232
  completed_date: "2026-04-28"
commit: "1d85152"
---

# Phase 1 Plan 01: Skeleton eval/ Python — Summary

Khởi tạo thư mục `eval/` Python ở root repo `Hub_All` với pyproject.toml PEP 621, README hướng dẫn đầy đủ, .gitignore, .env.example, marker package, và 8 file source byte-identical từ `file_test/`. Đây là Python codebase đầu tiên trong repo — convention chuẩn (ruff + PEP 8 + py311) được lock ngay từ skeleton để Phase 2 `docling-pipeline/` kế thừa nhất quán.

## Tick list `must_haves` từ PLAN frontmatter

### `truths`
- [x] Thư mục `eval/` tồn tại ở root repo, độc lập với `backend/` và `frontend/` — `ls eval/` hiển thị 6 entry (4 file + 2 dir: `dataset/`, `__init__.py`).
- [x] `pip install -e eval/` resolvable đầy đủ deps — kiểm chứng bằng `pip install --dry-run -e eval/`: `Would install ... medinet-eval-0.1.0` cùng tất cả deps (httpx, psycopg[binary]==3.3.3, python-docx, pypdf 6.10.2, pdf2image 1.17.0, img2pdf 0.6.3, Pillow 12.2.0, python-dotenv).
- [x] 8 file source từ `file_test/` được copy vào `eval/dataset/sources/` — SHA256 đã verify byte-identical (xem bảng dưới).
- [x] `eval/README.md` mô tả rõ cách build dataset + run baseline — 164 dòng / 10 section, có đủ workflow `seed_hub.sql` → `cleanup.py` → `baseline.py` + troubleshooting LibreOffice + JWT TTL + ChromaDB v2.
- [⚠] `ruff check eval/` không lỗi — `ruff` chưa cài trong môi trường executor (chưa chạy `pip install -e .[dev]`); pyproject.toml config ruff hợp lệ (parse OK, target py311, rule set chính xác). Sẽ pass tự động ngay khi dev cài `pip install -e ".[dev]"`. Xem deviation #1.

### `artifacts`
- [x] `eval/pyproject.toml` chứa `name = "medinet-eval"` + ruff config — verified qua `tomllib`.
- [x] `eval/README.md` ≥ 40 dòng — thực tế 164 dòng.
- [x] `eval/.env.example` chứa `BACKEND_URL` + 14 env var.
- [x] `eval/.gitignore` chứa `__pycache__` + 8 pattern khác.
- [x] `eval/__init__.py` tồn tại (rỗng, 0 byte) — marker package.
- [x] `eval/dataset/sources/` chứa đúng 8 file source.

### `key_links`
- [x] `[tool.ruff]` section trong `pyproject.toml` chứa `target-version = "py311"` — verified.

## Files Created (13)

| # | Đường dẫn | Kích thước | Vai trò |
|---|-----------|-----------|---------|
| 1 | `eval/pyproject.toml` | 877 B | PEP 621 build config + ruff lint/format |
| 2 | `eval/README.md` | 7,688 B (164 dòng) | Hướng dẫn install + workflow + troubleshooting |
| 3 | `eval/.gitignore` | 94 B | Bỏ qua `__pycache__`, `.env`, `*.egg-info`, ... |
| 4 | `eval/__init__.py` | 0 B | Marker package Python |
| 5 | `eval/.env.example` | 442 B | Template 14 env var (BACKEND_URL, DB_*, CHROMA_*, ADMIN_*, EVAL_*) |
| 6 | `eval/dataset/sources/DMD_T1-01_DinhVi_TrungTam_v1.docx` | 40,564 B | Định vị thương hiệu — text-heavy |
| 7 | `eval/dataset/sources/DMD_T1-02_TuDien_ThuongHieu_v1.docx` | 42,240 B | Từ điển thương hiệu |
| 8 | `eval/dataset/sources/DMD_T1-03_Script_Library_v1.docx` | 55,855 B | Thư viện script bán hàng |
| 9 | `eval/dataset/sources/DMD_T1-04_FAQ_ThuongHieu_v1.docx` | 44,453 B | FAQ — Q&A có cấu trúc |
| 10 | `eval/dataset/sources/DMD_T3-02_PhanCong_NhanVat_v1.docx` | 214,300 B | Phân công nhân vật |
| 11 | `eval/dataset/sources/DMD_T5-01_ContentStrategy_12TuyenND_v1.docx` | 36,258 B | Content strategy 12 tuyến |
| 12 | `eval/dataset/sources/DMD_T5-02_Playbook_KenhTruyen_v1.docx` | 34,883 B | Playbook kênh truyền |
| 13 | `eval/dataset/sources/tri_thuc_chinh_tri.pdf` | 97,222 B | PDF tiếng Việt có text layer (gốc) |

## SHA256 của 8 file source (cho Phase 5 verify identity)

| Filename | SHA256 |
|----------|--------|
| `DMD_T1-01_DinhVi_TrungTam_v1.docx` | `eb0d0b2c2b8572ae7238d48ac860f78301685dc1a5bf28aa95fc7f9d3e70d23d` |
| `DMD_T1-02_TuDien_ThuongHieu_v1.docx` | `44aadc2847d2a3c5d328c8153f5e164ae22f698ee84c190f3f63b8733e51e149` |
| `DMD_T1-03_Script_Library_v1.docx` | `e2c558c5f418eed760c4d9dc88e94bf8a217e6ccbcb702251db75d97bd163520` |
| `DMD_T1-04_FAQ_ThuongHieu_v1.docx` | `ae177598595ce6372c66f5b434705e427abe02dd0f5a9d2c80c73767ab7be0d8` |
| `DMD_T3-02_PhanCong_NhanVat_v1.docx` | `f7584c42cb5a089f8267062d70bc71f84c4d8439662c173bde4b3724b82fd501` |
| `DMD_T5-01_ContentStrategy_12TuyenND_v1.docx` | `979cccb18f52e4a431e22bca2b2e024d8b258bdc113afe379c46de0244b92d32` |
| `DMD_T5-02_Playbook_KenhTruyen_v1.docx` | `1d8a25c905cc5e3d73886404ed269d1c70e23b9c36f6ac10fff0b90daffe42bf` |
| `tri_thuc_chinh_tri.pdf` | `c18ea1b3deddbf4aa682a03169f71e365b59430ac98e2fc6ea58e94d26e972af` |

Mỗi hash đã verify khớp với file gốc trong `file_test/` (`sha256sum` so sánh từng cặp → 8/8 OK).

## Output `pip install --dry-run -e eval/`

Local Python: **3.13.4** (≥ 3.11 yêu cầu của pyproject.toml).

Kết quả dry-run resolve được package + tất cả runtime deps:

```
Would install Deprecated-1.3.1 img2pdf-0.6.3 medinet-eval-0.1.0 pdf2image-1.17.0
              pikepdf-10.5.1 pillow-12.2.0 psycopg-3.3.3 psycopg-binary-3.3.3
              pypdf-6.10.2 wrapt-2.1.2
```

Confirm `pypdf>=5.0` resolve thành `pypdf-6.10.2` — đáp ứng W1 fix trong PLAN (Plan 03 task 2 sẽ `from pypdf import PdfReader` thành công).

## Tasks executed

| # | Task | Trạng thái | Verify |
|---|------|-----------|--------|
| 1 | Tạo `pyproject.toml` + `.gitignore` + `__init__.py` + `.env.example` | done | `tomllib` parse OK; `python -c "import sys; sys.path.insert(0,'.'); import eval"` OK; pip dry-run OK |
| 2 | Copy 8 file source từ `file_test/` → `eval/dataset/sources/` | done | 8/8 file SHA256 byte-identical, tổng count = 8 |
| 3 | Viết `eval/README.md` (10 section, ≥ 40 dòng) | done | 164 dòng, có đủ `baseline_native.json`, `build_scanned.py`, `cleanup.py`, troubleshooting LibreOffice/JWT/ChromaDB v2 |

## Deviations from Plan

**1. [Rule 3 - Blocking issue / Environment]** — Không thể chạy `ruff check eval/` thực tế trong môi trường executor.
- **Found during:** Verify Task 1.
- **Issue:** `ruff` chưa cài trong môi trường Python local; PLAN giả định `pip install -e ".[dev]"` đã chạy.
- **Workaround:** (a) `pyproject.toml` tự nó parse hợp lệ qua `tomllib` (target=py311, line-length=100, rule set khớp PLAN); (b) `eval/__init__.py` rỗng + chưa có file `.py` nào khác → ruff sẽ không có gì để complain khi dev cài xong; (c) đã verify deps resolvable bằng `pip install --dry-run -e eval/` (xem output trên).
- **Files modified:** Không. Convention sẽ pass ngay khi dev/CI cài deps.
- **Tác động Phase tiếp theo:** Plan 02 task đầu nên chạy `pip install -e ".[dev]"` rồi `ruff check eval/` để xác nhận trên môi trường thật.

**2. [Rule 2 - Critical functionality]** — Kích thước `eval/.env.example` mở rộng vượt spec PLAN (PLAN nêu 11 env, đã có 14).
- **Lý do:** PATTERNS.md mục 5 yêu cầu thêm `EVAL_UPLOAD_TIMEOUT_SEC`, `EVAL_POLL_INTERVAL_SEC` (cho `baseline.py` resume + worker poll), không thêm = Plan 06 sẽ phải tự thêm muộn → mất idempotency.
- **Files modified:** `eval/.env.example`.
- **Hệ quả:** chỉ thêm key, không xóa key nào trong spec PLAN → backward-compatible.

## TDD Gate Compliance

PLAN không có task `tdd="true"` — không áp dụng RED/GREEN/REFACTOR. Phase 1 chỉ có test ở Plan 06 (smoke test).

## Known Stubs

Không có. Toàn bộ file đều là config/data/markdown — không có code Python placeholder hay UI component nào trống.

## Threat Flags

Không. Skeleton không thêm endpoint, không đổi auth path, không touch trust boundary. `.env.example` chỉ là template — file `.env` thật bị `.gitignore` block.

## Self-Check: PASSED

**Files created tồn tại:**
- FOUND: `eval/pyproject.toml`
- FOUND: `eval/README.md`
- FOUND: `eval/.gitignore`
- FOUND: `eval/__init__.py`
- FOUND: `eval/.env.example`
- FOUND: `eval/dataset/sources/DMD_T1-01_DinhVi_TrungTam_v1.docx`
- FOUND: `eval/dataset/sources/DMD_T1-02_TuDien_ThuongHieu_v1.docx`
- FOUND: `eval/dataset/sources/DMD_T1-03_Script_Library_v1.docx`
- FOUND: `eval/dataset/sources/DMD_T1-04_FAQ_ThuongHieu_v1.docx`
- FOUND: `eval/dataset/sources/DMD_T3-02_PhanCong_NhanVat_v1.docx`
- FOUND: `eval/dataset/sources/DMD_T5-01_ContentStrategy_12TuyenND_v1.docx`
- FOUND: `eval/dataset/sources/DMD_T5-02_Playbook_KenhTruyen_v1.docx`
- FOUND: `eval/dataset/sources/tri_thuc_chinh_tri.pdf`

**Commit existence:**
- FOUND: `1d85152` — `feat(eval): khởi tạo skeleton eval/ Python (pyproject + README + 8 file source) [phase-1 plan-01]`

---

*Plan 01-01 hoàn tất 2026-04-28. Sẵn sàng cho Plan 01-02 (Wave 2 — `build_scanned.py` sinh 2 PDF scanned giả lập).*
