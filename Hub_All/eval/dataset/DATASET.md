# Eval Dataset — M1 RAG Quality with Docling

**Phase:** 1 / 5
**Ngày tạo:** 2026-04-28
**Version:** 1.0

## Mục đích

Dataset đo baseline retrieval cho Medinet Wiki RAG, dùng cho cả:

- **Phase 1**: baseline với extractor Go native → snapshot `eval/baseline_native.json`.
- **Phase 5**: compare với extractor Docling → snapshot `eval/baseline_docling.json`.

Gate milestone M1: top-3 hit rate **tăng ≥ 15 điểm phần trăm** HOẶC đạt **≥ 75% tuyệt đối**
(xem `.planning/ROADMAP.md` mục Phase 5).

## Cấu trúc thư mục

```
eval/dataset/
├── DATASET.md            (file này — mô tả dataset)
├── sources/              (8 file gốc copy từ file_test/)
│   ├── DMD_T1-01_DinhVi_TrungTam_v1.docx
│   ├── DMD_T1-02_TuDien_ThuongHieu_v1.docx
│   ├── DMD_T1-03_Script_Library_v1.docx
│   ├── DMD_T1-04_FAQ_ThuongHieu_v1.docx
│   ├── DMD_T3-02_PhanCong_NhanVat_v1.docx
│   ├── DMD_T5-01_ContentStrategy_12TuyenND_v1.docx
│   ├── DMD_T5-02_Playbook_KenhTruyen_v1.docx
│   └── tri_thuc_chinh_tri.pdf
├── scanned/              (2 file PDF image-only sinh bởi build_scanned.py)
│   ├── DMD_T1-01_scanned.pdf
│   └── DMD_T1-04_scanned.pdf
├── queries.jsonl         (12 truy vấn vàng tiếng Việt — Plan 05 user-approved)
├── headings.json         (heading vàng per doc — 286 heading path / 10 doc)
└── QUERIES_REVIEW.md     (bảng review user approve, Plan 05)
```

## Phân loại 10 file

| # | Filename | Loại | Nguồn | Đặc điểm |
|---|----------|------|-------|----------|
| 1 | DMD_T1-01_DinhVi_TrungTam_v1.docx | DOCX | DMD nội bộ | Định vị thương hiệu — text-heavy, 28 heading |
| 2 | DMD_T1-02_TuDien_ThuongHieu_v1.docx | DOCX | DMD nội bộ | Từ điển thương hiệu — definition-style, 9 heading |
| 3 | DMD_T1-03_Script_Library_v1.docx | DOCX | DMD nội bộ | Script library — 50 heading |
| 4 | DMD_T1-04_FAQ_ThuongHieu_v1.docx | DOCX | DMD nội bộ | FAQ Q&A có cấu trúc — 67 heading |
| 5 | DMD_T3-02_PhanCong_NhanVat_v1.docx | DOCX | DMD nội bộ | Phân công nhân vật — table-heavy, 6 heading |
| 6 | DMD_T5-01_ContentStrategy_12TuyenND_v1.docx | DOCX | DMD nội bộ | Content strategy 12 tuyến nội dung, 5 heading |
| 7 | DMD_T5-02_Playbook_KenhTruyen_v1.docx | DOCX | DMD nội bộ | Playbook kênh truyền, 15 heading |
| 8 | tri_thuc_chinh_tri.pdf | PDF | Public | PDF gốc có text layer, 11 heading manual |
| 9 | DMD_T1-01_scanned.pdf | PDF (image-only) | Tự sinh | Scanned từ DMD_T1-01 (test OCR Phase 5), 28 heading copy |
| 10 | DMD_T1-04_scanned.pdf | PDF (image-only) | Tự sinh | Scanned từ DMD_T1-04 (test OCR Phase 5), 67 heading copy |

**Tổng:** 286 heading path / 10 doc. Trung bình ~28.6 heading/doc.

## Cách tái tạo

```bash
# Bước 1: Cài deps Python
cd eval && pip install -e ".[dev]"

# Bước 2: Build scanned PDF từ DOCX gốc (idempotent — script skip nếu đã tồn tại)
python scripts/build_scanned.py

# Bước 3: Extract heading vàng từ DOCX (PDF gốc đã LLM-draft hard-coded trong code)
python scripts/extract_headings.py

# Bước 4: Sinh queries.jsonl (Plan 05 — LLM draft + user review trong checkpoint)
# Hiện đã commit version đã user-approved, không cần regenerate.

# Bước 5: Seed eval_hub vào Postgres
psql -h localhost -U medinet -d medinet_central -f scripts/seed_hub.sql

# Bước 6: Cleanup state cũ + run baseline (Pre-flight tự verify)
python scripts/cleanup.py
python ../baseline.py
```

## Schema queries.jsonl

```json
{
  "id": "q01",
  "query": "<câu hỏi tiếng Việt>",
  "expected_doc_id": "<filename>",
  "expected_section": "<heading path nối bằng ' > '>",
  "notes": "<context tại sao expected>"
}
```

⚠ **Quan trọng:** `expected_doc_id` LÀ filename (không phải UUID) — match với
`result.category` từ backend SearchResult (xem `backend/internal/rag/searcher.go:131`).
Lý do: backend Go gán document name (= filename gốc) vào `Category` field — đây là
field duy nhất stable để match ngược về document gốc; `result.id` là **chunk_id**
(vector ID trong ChromaDB), không phải document_id.

12 query phân bố tối thiểu 1 query / file (10 file × 1 + 2 query bonus cho edge case).
2 query (q09, q10) trỏ scanned PDF — dự kiến baseline native FAIL = 0% top-3 cho 2 query này
(extractor pdf.go:52 trả `no text extracted` cho image-only PDF).

## Schema headings.json

```json
{
  "<filename>": ["<heading path 1>", "<heading path 2>", ...]
}
```

- 7 DOCX: extract auto từ `pStyle` + `outlineLvl` (port từ Go `docx.go:46-95`) +
  fallback heuristic regex khi pStyle map trống (Plan 04 deviation Rule 2).
- 1 PDF gốc: manual entry trong `extract_headings.py:MANUAL_PDF_HEADINGS`
  (LLM-draft từ pypdf đọc 5 trang đầu, user review Plan 05).
- 2 scanned PDF: copy heading từ DOCX gốc tương ứng — chính là ground truth,
  Docling OCR ở Phase 5 phải recover đúng heading này.

## Schema baseline_native.json (output `eval/baseline.py`)

```json
{
  "run_id": "2026-04-28T...Z",
  "extractor_mode": "native",
  "embedder_provider": "openai|gemini|...",
  "embedder_model": "text-embedding-3-small|...",
  "embedder_dim": <int>,
  "chunker": "...",
  "chunk_size": <int>,
  "chunk_overlap": <int>,
  "eval_hub_id": "<uuid>",
  "documents": [
    {
      "id": "<doc_uuid>",
      "filename": "<filename>",
      "status": "completed|error|timeout",
      "progress": 100,
      "chunk_count": <int>,
      "error_message": "<...?>",
      "headings_gold_count": <int>
    }
  ],
  "retrieval": {
    "top_1_hit_rate": <float 0-1>,
    "top_3_hit_rate": <float 0-1>,
    "top_5_hit_rate": <float 0-1>,
    "mrr": <float 0-1>,
    "per_query": [
      {
        "id": "q01",
        "query": "...",
        "expected_doc_id": "<filename>",
        "expected_section": "...",
        "actual_top_5": [
          {"chunk_id": "...", "category": "<filename>", "title": "...", "score": <float>}
        ],
        "rank": <int|null>
      }
    ]
  },
  "queries_count": 12,
  "files_count": 10,
  "_note_heading_recall_deferred": "heading_recall measured in Phase 5 per REQ EVAL-02"
}
```

⚠ **Phase 1 KHÔNG có `headings_recalled` / `headings_missed`** — defer Phase 5 theo REQ EVAL-02.
Phase 1 chỉ ghi `headings_gold_count` (số heading vàng/doc). Lý do: Phase 5 mới cần diff
"trước/sau Docling" về heading recall; Phase 1 đo placeholder rỗng sẽ misleading.

## License

- 7 file DMD: nội bộ Medinet, **KHÔNG public**, dùng nội bộ M1 development.
- `tri_thuc_chinh_tri.pdf`: public domain (xem comment trong file gốc).
- 2 scanned PDF: derived từ DOCX nội bộ → cùng license nội bộ.
- `queries.jsonl` + `headings.json`: derived từ dataset trên → cùng license.

⚠ **Không commit dataset này vào public repo / không gửi qua email không mã hóa.**
Chỉ dùng nội bộ Medinet team M1.

## Versioning

- **v1.0** (2026-04-28): khởi tạo cho M1 Phase 1 baseline native.
  - 8 sources + 2 scanned PDF.
  - 12 queries (LLM draft + user review).
  - 286 heading path / 10 doc.
- Khi sửa queries hoặc thêm file: bump version + ghi changelog ở mục dưới.

## Reproducibility check

Sau khi sinh dataset:

```bash
# Hash check (cùng input -> cùng hash output)
sha256sum eval/dataset/sources/*.docx
sha256sum eval/dataset/sources/*.pdf
sha256sum eval/dataset/scanned/*.pdf
sha256sum eval/dataset/queries.jsonl
sha256sum eval/dataset/headings.json
```

Phase 5 chạy script trên cùng input phải ra cùng hash (trừ scanned PDF có thể khác do
timestamp metadata trong PDF — chấp nhận diff metadata, content-equal phải đảm bảo).

`extract_headings.py` đảm bảo deterministic: cùng DOCX input → sha256 `headings.json`
ổn định (verified Plan 04 self-check).

## Changelog

- **v1.0 — 2026-04-28** — khởi tạo dataset Phase 1 (8 sources + 2 scanned + 12 queries +
  286 heading). User review approved trong Plan 05 checkpoint.

---

*Last updated: 2026-04-28 (Plan 01-06 — kèm DATASET.md + baseline.py).*
