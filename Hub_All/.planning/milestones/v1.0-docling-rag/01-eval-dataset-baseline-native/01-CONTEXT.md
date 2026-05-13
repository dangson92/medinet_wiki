# CONTEXT — Phase 1: Eval Dataset & Baseline Native

**Phase:** 1 / 5
**Milestone:** M1 — RAG Quality with Docling
**Goal:** Có sẵn eval dataset đầy đủ + bộ truy vấn vàng + số liệu baseline retrieval đo bằng extractor Go hiện tại, để Phase 5 có cơ sở so sánh trước/sau.
**Requirements:** EVAL-01
**Ngày discuss:** 2026-04-28
**Cập nhật:** 2026-04-28 (revision round 1 — defer heading_recall sang Phase 5 theo REQ EVAL-02)

---

## Decisions Locked

### A. Queries + Heading vàng — Labeling

**Cách tạo:**
- **Tôi (Claude) sinh draft 12 truy vấn vàng** bằng LLM, đọc 10 file dataset (8 từ `file_test/` + 2 scanned tự tạo). User review trước khi commit.
- **Heading vàng cho file DOCX**: extract auto từ DOCX styles (`pStyle` + `outlineLvl`) qua script Python `eval/scripts/extract_headings.py` — tận dụng cùng logic [docx.go:46-95](backend/internal/rag/extractor/docx.go#L46-L95).
- **Heading vàng cho PDF (1 file gốc + 2 scanned)**: manual liệt kê (extractor Go hiện tại unreliable cho PDF; scanned PDF chưa có OCR nên không tự extract được).
- Output cuối:
  - `eval/dataset/queries.jsonl` — 12 dòng JSON.
  - `eval/dataset/headings.json` — map `{doc_id: [heading_path, ...]}`.

**Schema queries.jsonl:**
```json
{"id": "q01", "query": "<câu hỏi tiếng Việt>", "expected_doc_id": "<filename>", "expected_section": "<heading path>", "notes": "<context tại sao expected>"}
```

- **`expected_doc_id` LÀ filename** (vd `"DMD_T1-01_DinhVi_TrungTam_v1.docx"`), KHÔNG phải UUID. Lý do: backend Go gán document name (= filename gốc) vào field `Category` của `model.SearchResult` (xem `backend/internal/rag/searcher.go:131`) — đây là field duy nhất stable để match ngược về document gốc; `result.id` là **chunk_id** (vector ID trong ChromaDB), không phải document_id.
- KHÔNG bao gồm `expected_answer_span` (defer v2; Phase 5 chỉ đo retrieval, không đo answerer quality).
- `expected_section` là **heading path** từ root đến section chứa answer (vd `"Định vị thương hiệu > Thông điệp cốt lõi"`).

**Vì sao chọn:** LLM gen draft + user review nhanh hơn nhiều so với manual full type, vẫn giữ chất lượng vì user là gatekeeper cuối. 8/10 file thuộc DMD nội bộ — user hiểu rõ kiến thức nhất.

### B. Scanned PDF — Nguồn

**Tự tạo giả lập từ DOCX hiện có** trong `file_test/`:
- Chọn 2 file: `DMD_T1-01_DinhVi_TrungTam_v1.docx` (định vị thương hiệu — text-heavy) + `DMD_T1-04_FAQ_ThuongHieu_v1.docx` (FAQ — Q&A có cấu trúc).
- Pipeline tạo: DOCX → PDF (qua LibreOffice headless `soffice --headless --convert-to pdf` hoặc `docx2pdf`) → raster mỗi page thành PNG 150 DPI (qua `pdf2image.convert_from_path`) → ghép lại PDF image-only (qua `img2pdf`).
- Output:
  - `eval/dataset/scanned/DMD_T1-01_scanned.pdf` (image-only, no text layer)
  - `eval/dataset/scanned/DMD_T1-04_scanned.pdf`
- Script: `eval/scripts/build_scanned.py` — reproducible, commit để Phase 5 cũng dùng đúng cùng input.

**Vì sao chọn:** Reproducible (script regenerate được), không có vấn đề privacy data thật, mỗi file scanned có "ground truth" là DOCX gốc → dễ verify OCR có ra text đúng không. Đủ thử thách: page là raster image, [pdf.go:52](backend/internal/rag/extractor/pdf.go#L52) sẽ trả `no text extracted` ngay (chứng minh gap cho Docling).

### C. Hub + Collection — eval sandbox

**Tạo hub mới `eval_hub`** + collection ChromaDB riêng theo run:
- SQL seed: `eval/scripts/seed_hub.sql` insert vào bảng `hubs` (theo schema `001_bootstrap.up.sql:11-23` — bảng dùng `status` chứ KHÔNG có `is_active`, và `subdomain` là `UNIQUE NOT NULL`):
  ```sql
  INSERT INTO hubs (id, code, name, subdomain, chroma_collection, status, created_at)
  VALUES (gen_random_uuid(), 'eval', 'Eval Sandbox (M1 RAG Quality)', 'eval.medinet.vn', 'medinet_eval', 'active', now())
  ON CONFLICT (code) DO NOTHING;
  ```
- Mỗi run baseline KHÔNG tạo collection mới — dùng `medinet_eval` ổn định, nhưng **trước mỗi run** script `eval/scripts/cleanup.py` xóa toàn bộ:
  - Rows trong `documents` (và cascade `chunks`) thuộc `hub_id = eval_hub.id`.
  - Drop + tạo lại collection `medinet_eval` qua `ChromaDB API DELETE /collections/medinet_eval` rồi gọi backend healthcheck để re-create (backend tự `CreateCollection` lúc khởi động cho mọi hub `active` — xem [main.go:211-225](backend/cmd/server/main.go#L211-L225)).
- Sau khi M1 hoàn tất: giữ `eval_hub` (set `status='inactive'`) để có thể chạy lại eval khi cần regression test.

**Vì sao chọn:** Sandbox tuyệt đối — không lẫn data dev/prod. Cleanup script reusable cho Phase 5 (chạy lại 2 lần với mode khác nhau).

### D. Embedding + Script Language

**Giữ embedding provider hiện tại** (lock theo `.env` của backend):
- KHÔNG đổi `EMBEDDING_PROVIDER` env giữa baseline (Phase 1) và compare (Phase 5). Phase 5 verify provider khớp.
- Script `eval/baseline.py` **gọi `GET /api/rag-config` đầu tiên**, ghi `embedder_provider`, `embedder_model`, `embedder_dim` vào snapshot output → Phase 5 fail loud nếu config đổi.
- User confirm: "Embedding đã chạy ổn rồi, chỉ cần chunking cho chuẩn" → không đầu tư thêm vào embedding selection.

**Script eval = Python:**
- Cấu trúc `eval/` ở root repo (không nằm trong `backend/` hay `docling-pipeline/`).
- Deps: `httpx` (gọi API Go), `python-docx` (extract heading từ DOCX), `pypdf` (PDF text-layer verify), `pdf2image` + `img2pdf` + `Pillow` (build_scanned), `pytest` (smoke test trong Phase 5).
- File `eval/pyproject.toml` riêng — `pip install -e eval/` để chạy độc lập.

**Vì sao chọn:** Giữ scope chunking-focus, không mở thêm mặt trận embedding. Python script khớp với `docling-pipeline/` ở Phase 2 (cùng hệ sinh thái).

---

## Cấu trúc thư mục eval/ (Phase 1 deliver)

```
eval/
├── README.md                      # Hướng dẫn chạy: build dataset, run baseline
├── pyproject.toml                 # Python deps
├── __init__.py
├── dataset/
│   ├── DATASET.md                 # Mô tả dataset, license, cách tái tạo
│   ├── sources/                   # 8 file gốc COPY từ file_test/ (commit để eval reproducible)
│   │   ├── DMD_T1-01_DinhVi_TrungTam_v1.docx
│   │   ├── DMD_T1-02_TuDien_ThuongHieu_v1.docx
│   │   ├── ... (5 file DMD còn lại)
│   │   └── tri_thuc_chinh_tri.pdf
│   ├── scanned/                   # 2 file PDF giả lập sinh bởi build_scanned.py
│   │   ├── DMD_T1-01_scanned.pdf
│   │   └── DMD_T1-04_scanned.pdf
│   ├── queries.jsonl              # 12 truy vấn vàng (LLM draft + user review)
│   └── headings.json              # Heading vàng per doc
├── scripts/
│   ├── build_scanned.py           # DOCX → PDF → raster image → image-PDF
│   ├── extract_headings.py        # Extract heading từ DOCX styles
│   ├── seed_hub.sql               # SQL tạo eval_hub
│   └── cleanup.py                 # Truncate documents + chunks + drop chroma collection
└── baseline.py                    # Upload all → measure → snapshot baseline_native.json
```

**Snapshot output** (Phase 1 commit):
- `eval/baseline_native.json` chứa:
  ```json
  {
    "run_id": "2026-04-28T<timestamp>",
    "extractor_mode": "native",
    "embedder_provider": "<từ /api/rag-config>",
    "embedder_model": "<từ /api/rag-config>",
    "embedder_dim": <int>,
    "documents": [
      {"doc_id": "...", "filename": "...", "status": "completed|failed", "error": "...", "chunks_count": <int>, "avg_chunk_tokens": <float>, "headings_gold_count": <int>}
    ],
    "retrieval": {
      "top_1_hit_rate": 0.xxx,
      "top_3_hit_rate": 0.xxx,
      "top_5_hit_rate": 0.xxx,
      "mrr": 0.xxx,
      "per_query": [
        {"id": "q01", "expected_doc_id": "...", "actual_top_5": [...], "rank": <int|null>}
      ]
    }
  }
  ```

**Lưu ý quan trọng (revision 1):** Trường `headings_recalled` và `headings_missed` **đã được DEFER sang Phase 5** theo REQ EVAL-02 (REQUIREMENTS.md). Phase 1 chỉ commit `headings_gold_count` (số heading vàng/doc) — đủ làm input cho Phase 5 đo recall. Lý do: Phase 5 mới cần diff "trước/sau Docling" về heading recall; Phase 1 đo placeholder rỗng sẽ misleading. Heading vàng vẫn được sinh đầy đủ ở `eval/dataset/headings.json` (Plan 04) — Phase 5 dùng đúng file đó để compute recalled/missed.

---

## Out of Scope Phase 1 (defer)

- ❌ Đo answerer quality (BLEU/ROUGE) — defer v2; chỉ đo retrieval.
- ❌ Eval trên cross-hub search — milestone hiện tại không đụng tới cross-hub.
- ❌ Eval trên RAG cache hit — Redis cache có thể skew kết quả; baseline phải clear cache trước mỗi run (`cleanup.py` flush cache key liên quan).
- ❌ A/B với multiple embedding model — provider lock theo `.env` hiện tại.
- ❌ Auto-grading bằng LLM judge — defer; queries vàng đủ ground truth.
- ❌ **Heading recall metric (`headings_recalled` / `headings_missed`) — defer Phase 5 theo REQ EVAL-02.** Phase 1 chỉ commit `headings_gold_count`.

## Gray Areas đã decide bằng default (không thảo luận sâu)

Không có — toàn bộ 4 gray area đều có decision rõ ở mục Decisions Locked.

## Deferred Ideas (cho roadmap backlog)

- LLM-as-judge tự động đánh giá top-3 retrieval chất lượng (semantic match thay vì exact doc match).
- Eval thêm metric: chunk overlap với expected_section (chunk có chứa heading đúng hay chỉ doc đúng?).
- Public eval set tiếng Việt y tế reproducible cho cộng đồng (sau khi đã sạch privacy).
- Auto regression run trong CI khi thay đổi extractor/chunker/embedder.

## Rủi ro & Câu hỏi mở

- **Rủi ro 1**: LibreOffice headless trên Windows có thể flaky. Mitigation: thử `docx2pdf` (Word automation) hoặc `pandoc` làm backup; build_scanned.py có retry logic.
- **Rủi ro 2**: 12 queries có thể không cover hết edge case (table-heavy doc, scanned PDF). Mitigation: queries phân bố theo doc — ít nhất 1 query trỏ vào mỗi file.
- **Rủi ro 3**: Embedding provider đang config có thể chậm/timeout với batch upload 10 file × N chunks → baseline run mất nhiều thời gian. Mitigation: script chạy sequential với progress bar; cho phép resume.
- **Câu hỏi mở**: User có muốn baseline lưu cả raw chunks text để debug không (tốn dung lượng JSON)? **Default**: KHÔNG lưu raw chunks (chỉ count + token avg) để JSON nhỏ; nếu cần debug, có log Go riêng.

---

## Downstream

**gsd-planner sẽ đọc CONTEXT này để biết:**
- Cấu trúc `eval/` đã chốt — không cần research kiến trúc.
- Schema queries + headings cụ thể — không cần ask user lại.
- Nguồn 2 scanned PDF: tự tạo bằng pipeline DOCX→PDF→image — task cụ thể trong plan.
- Hub `eval_hub` + collection `medinet_eval` đã chốt — script SQL ready để code.
- Snapshot format `baseline_native.json` chốt — implement đúng schema (KHÔNG có `headings_recalled`/`headings_missed` ở Phase 1).

**gsd-phase-researcher có thể skip** vì decisions đã rõ, codebase đã map (`.planning/codebase/`), endpoint backend đã verify trong session discuss này.

---

*Last updated: 2026-04-28 (revision 1: defer heading_recall metric Phase 5, clarify expected_doc_id = filename matching `result.category`)*
