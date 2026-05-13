# Medinet Eval — Dataset & Baseline Retrieval (M1)

Thư mục này chứa **eval dataset + scripts đo retrieval** cho milestone M1 (RAG Quality with Docling) của Medinet Wiki. Phase 1 dùng để chốt **baseline native** (extractor Go hiện tại), Phase 5 sẽ chạy lại đúng quy trình với Docling rồi so sánh.

> Toàn bộ tài liệu/comment viết tiếng Việt có dấu. Tên hàm/biến/REQ-ID/đường dẫn/lệnh shell giữ tiếng Anh.

---

## 1. Mục đích

- **Phase 1 (EVAL-01):** Build dataset (8 file DMD gốc + 2 scanned PDF giả lập + 12 truy vấn vàng + heading vàng) → chạy `baseline.py` với extractor native → snapshot `baseline_native.json`.
- **Phase 5 (EVAL-02..05):** Chạy lại đúng dataset, đúng query với `RAG_EXTRACTOR=docling` → snapshot `baseline_docling.json` → diff để chứng minh ≥ +15 điểm phần trăm hoặc top-3 ≥ 75%.

Eval **chỉ đo retrieval** (top-k hit rate + MRR). Answerer quality (BLEU/ROUGE) và LLM-as-judge defer v2.

## 2. Yêu cầu môi trường

- Python ≥ 3.11.
- Backend Go đang chạy ở `http://localhost:8180` (xem `backend/.env.example`).
- PostgreSQL 16 + Redis 7 + ChromaDB đang chạy (theo `backend/docker-compose.yml`).
- LibreOffice headless (cho `eval/scripts/build_scanned.py`):
  - Linux/macOS: `apt install libreoffice` / `brew install --cask libreoffice`.
  - Windows: cài LibreOffice, thêm `soffice.exe` vào PATH; fallback `docx2pdf` (cần MS Word) hoặc `pandoc + wkhtmltopdf`.

## 3. Cài đặt

```bash
cd eval
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
cp .env.example .env
# Sửa .env theo môi trường local (đặc biệt DB_PASSWORD + ADMIN_PASSWORD)
```

Verify nhanh:

```bash
python -c "import httpx, psycopg, docx, pypdf, pdf2image, img2pdf, PIL, dotenv; print('deps OK')"
ruff check .
```

## 4. Cấu trúc thư mục

```
eval/
├── README.md                      # File này
├── pyproject.toml                 # PEP 621 + ruff config
├── .env.example                   # Template env (copy → .env)
├── .gitignore                     # Bỏ qua __pycache__, .env, *.egg-info, ...
├── __init__.py                    # Marker package
├── dataset/
│   ├── DATASET.md                 # Mô tả dataset, license, cách tái tạo (Plan 04)
│   ├── sources/                   # 8 file gốc COPY từ file_test/ (commit để eval reproducible)
│   │   ├── DMD_T1-01_DinhVi_TrungTam_v1.docx
│   │   ├── DMD_T1-02_TuDien_ThuongHieu_v1.docx
│   │   ├── DMD_T1-03_Script_Library_v1.docx
│   │   ├── DMD_T1-04_FAQ_ThuongHieu_v1.docx
│   │   ├── DMD_T3-02_PhanCong_NhanVat_v1.docx
│   │   ├── DMD_T5-01_ContentStrategy_12TuyenND_v1.docx
│   │   ├── DMD_T5-02_Playbook_KenhTruyen_v1.docx
│   │   └── tri_thuc_chinh_tri.pdf
│   ├── scanned/                   # 2 PDF image-only sinh bởi build_scanned.py (Plan 02)
│   │   ├── DMD_T1-01_scanned.pdf
│   │   └── DMD_T1-04_scanned.pdf
│   ├── queries.jsonl              # 12 truy vấn vàng (Plan 05)
│   └── headings.json              # Heading vàng per doc (Plan 04)
├── scripts/
│   ├── build_scanned.py           # DOCX → PDF → raster image → image-PDF (Plan 02)
│   ├── extract_headings.py        # Extract heading từ DOCX styles (Plan 04)
│   ├── seed_hub.sql               # SQL seed eval_hub vào Postgres (Plan 03)
│   └── cleanup.py                 # Truncate documents/chunks + drop chroma collection (Plan 03)
└── baseline.py                    # Upload all → measure → snapshot baseline_native.json (Plan 06)
```

## 5. Workflow build dataset (chạy 1 lần)

```bash
# Step 1: Sinh 2 scanned PDF từ DOCX gốc (DMD_T1-01 + DMD_T1-04)
python eval/scripts/build_scanned.py

# Step 2: Extract heading vàng từ DOCX → eval/dataset/headings.json
python eval/scripts/extract_headings.py

# Step 3: 12 queries vàng đã commit sẵn ở eval/dataset/queries.jsonl.
#         Nếu cần regen draft, xem 01-05-PLAN.md (LLM-driven gen + user review).
```

## 6. Workflow chạy baseline native (Phase 1)

```bash
# Step 1: Seed eval_hub vào Postgres (chạy 1 lần)
psql -h localhost -U medinet -d medinet_central -f eval/scripts/seed_hub.sql

# Step 2: Cleanup state cũ — idempotent, chạy MỖI lần trước baseline để tránh skew
python eval/scripts/cleanup.py
#   - DELETE FROM documents WHERE hub_id=<eval> (cascade chunks)
#   - DELETE collection medinet_eval ở ChromaDB rồi POST tạo lại với hnsw:space=cosine
#   - shutil.rmtree backend/uploads/eval/
#   - DEL key Redis prefix rag:cache:*

# Step 3: Chạy baseline — login admin → upload 10 file → poll status → search 12 query → snapshot
python eval/baseline.py
#   Output: eval/baseline_native.json
```

## 7. Định dạng output `baseline_native.json`

```json
{
  "run_id": "2026-04-28T10:30:00Z",
  "extractor_mode": "native",
  "embedder_provider": "openai",
  "embedder_model": "text-embedding-3-small",
  "embedder_dim": 1536,
  "documents": [
    {
      "doc_id": "uuid",
      "filename": "DMD_T1-01_DinhVi_TrungTam_v1.docx",
      "status": "completed",
      "error": null,
      "chunks_count": 24,
      "avg_chunk_tokens": 412.5,
      "headings_gold_count": 17
    }
  ],
  "retrieval": {
    "top_1_hit_rate": 0.0,
    "top_3_hit_rate": 0.0,
    "top_5_hit_rate": 0.0,
    "mrr": 0.0,
    "per_query": [
      {"id": "q01", "expected_doc_id": "...", "actual_top_5": [...], "rank": null}
    ]
  }
}
```

> **Lưu ý (revision 1):** Field `headings_recalled` / `headings_missed` đã được DEFER sang Phase 5 theo REQ EVAL-02. Phase 1 chỉ commit `headings_gold_count` (số heading vàng/doc) — đủ làm input cho Phase 5 đo recall.

## 8. Reproducibility cho Phase 5

- Phase 5 chạy lại đúng quy trình với `RAG_EXTRACTOR=docling` (config qua admin endpoint hoặc env) → output `eval/baseline_docling.json`.
- 12 queries + heading vàng + 8 file source + 2 scanned PDF KHÔNG đổi giữa 2 lần — chính là ground truth.
- Embedding provider/model PHẢI khớp; `baseline.py` snapshot `embedder_provider/model/dim` từ `GET /api/rag-config` + `GET /api/rag-config/collections`. Phase 5 fail loud nếu config đổi.

## 9. Troubleshooting

- **LibreOffice headless flaky (Windows):** xem fallback chain trong `build_scanned.py` (LibreOffice → docx2pdf → pandoc).
- **JWT 15 phút hết hạn khi upload kéo dài:** `baseline.py` auto-refresh qua `/api/auth/refresh` khi nhận 401.
- **ChromaDB v2 path:** `/api/v2/tenants/default_tenant/databases/default_database/collections/...`. Nếu instance cũ dùng v1, set `CHROMA_URL` đúng và sửa `cleanup.py`.
- **Worker pool race khi cleanup:** `cleanup.py` check `SELECT COUNT(*) FROM documents WHERE hub_id=<eval> AND status IN ('pending','processing')` = 0 trước khi xóa.

## 10. Convention code

- Format: `ruff format eval/`
- Lint: `ruff check eval/` (rule set `E,W,F,I,N,UP,B,SIM,RUF`)
- Type check: `mypy eval/` (optional Phase 1, mandatory Phase 2 cho `docling-pipeline/`)
- Test: `pytest eval/` (chỉ Phase 5 mới có test)
- Commit message tiếng Việt có dấu, prefix tiếng Anh chuẩn (`feat:`, `fix:`, `chore:`, `docs:`, `test:`).

---

*Skeleton được khởi tạo ở Phase 1 / Plan 01. Các script `build_scanned.py`, `extract_headings.py`, `cleanup.py`, `baseline.py` sẽ được implement ở các plan 02–06 theo thứ tự.*

---

## 11. Phase 5 — Eval Compare & Quality Gate (M1)

Phase 5 so sánh chất lượng RAG giữa 2 mode `RAG_EXTRACTOR=native` (baseline Phase 1) và `RAG_EXTRACTOR=docling` (sản phẩm M1) trên cùng dataset + cùng 12 truy vấn vàng + cùng embedder, để **gate milestone M1**.

### 11.1. Tiền điều kiện

1. Phase 1 đã chạy xong: `eval/baseline_native.json` tồn tại (commit `f37cd96`, top-3 = 75%).
2. Phase 2-4 đã ship: service `docling-pipeline/` chạy được, `RAG_EXTRACTOR=docling` switch được runtime qua `PUT /api/rag-config` (CFG-03).
3. Stack đầy đủ UP — backend Go + PostgreSQL 16 + Redis 7 + ChromaDB + `docling-pipeline`:
   ```bash
   docker compose up -d
   ```
4. State sạch trước mỗi run baseline-docling:
   ```bash
   make eval-clean
   # hoặc: python eval/scripts/cleanup.py
   ```
5. `eval/.env` đã copy + sửa từ `eval/.env.example` (đặc biệt `DB_PASSWORD`, `ADMIN_PASSWORD`).

### 11.2. Workflow chạy end-to-end (3 bước, theo thứ tự)

```bash
# === Bước 1: Snapshot mode Docling (~30-60 phút, vì Docling extract chậm hơn native 5-10×) ===
make eval-baseline-docling
#   → eval/baseline_docling.json
#   Bên trong: pre-flight → embedder lock verify → cleanup → PUT mode=docling
#               → upload 10 file + poll 300s/file → 12 query → snapshot
#               → finally restore mode=auto.

# === Bước 2: Compare + sinh EVAL.md (verdict PASS/FAIL, exit 0/1) ===
make eval-compare
#   → eval/extraction_compare.json   (per-doc heading recall + table preservation)
#   → eval/retrieval_eval.json       (per-query verdict 6-case + top-K + MRR)
#   → eval/EVAL.md                   (báo cáo cuối M1, 7 section, commit gate)

# === Bước 3: Smoke verify Docling thực sự được dùng (~30s) ===
make eval-smoke
#   Expected stdout cuối: "SMOKE OK: Docling extractor used + (table chunk indexed HOAC defensive skip)"

# === Hoặc chạy gọn 2 bước đầu một lần (hữu ích trong CI): ===
make eval-all
```

### 11.3. Smoke test chi tiết (`make eval-smoke`)

`eval-smoke` là gate cuối cùng đảm bảo **Docling thực sự được dùng** (không fallback ngầm sang native):

1. Pre-flight (`lib.preflight`): backend Go + ChromaDB + hub `eval` đã seed.
2. Login admin → lấy hub_id `eval`.
3. Upload 1 file `eval/dataset/sources/DMD_T1-01_DinhVi_TrungTam_v1.docx` (timeout 300s).
4. **Assert** `documents.extractor_used == "docling"` (CFG-06 — chứng minh Docling thật, không circuit breaker fallback).
5. Search "tom tat dinh vi thuong hieu" → kiểm tra chunks trả về.
6. **Assert** ≥ 1 chunk có `metadata.is_table == true` (dùng `bool(...)` explicit, không truthy loose), HOẶC chấp nhận skip nếu file không có table (defensive — file dataset có thể không chứa table tuỳ phiên bản).
7. In `SMOKE OK` nếu pass.

Smoke FAIL → đọc section Troubleshooting bên dưới.

### 11.4. Quality gate (xem `eval/run_compare.py`)

Exit code:

| Exit | Nghĩa | Điều kiện |
|---|---|---|
| **0 (PASS)** | M1 đủ chất lượng promote production | top-3 hit rate Docling cải thiện **≥ 15 điểm phần trăm** so với baseline native, **HOẶC** top-3 đạt **≥ 75% tuyệt đối** |
| **1 (FAIL)** | Chưa đạt — đọc EVAL.md section 6 để biết next step | Không thoả cả hai điều kiện trên |

`EVAL.md` **vẫn được sinh đầy đủ** dù FAIL — chứa số liệu để debug + 3 hướng recommend (reranker / hybrid retrieval / data improvement).

### 11.5. File outputs Phase 5

| File | Mô tả | Tình trạng commit |
|---|---|---|
| `eval/baseline_native.json` | Phase 1 snapshot (immutable, top-3 = 75%) | ✅ Có (`f37cd96`) |
| `eval/baseline_docling.json` | Phase 5 snapshot mode Docling | Optional commit (artifact reproducible từ runtime) |
| `eval/extraction_compare.json` | Per-document extraction quality (chunks count, heading recall, table preservation) | Optional |
| `eval/retrieval_eval.json` | Retrieval metrics + per-query verdict 6-case (FIXED/REGRESSED/IMPROVED/WORSE/unchanged/both_miss) | Optional |
| `eval/EVAL.md` | **Báo cáo cuối M1** — verdict + bảng số liệu + recommend | **Bắt buộc commit (gate milestone)** |

### 11.6. Troubleshooting Phase 5

- **`EMBEDDER LOCK FAIL: cấu hình embedding hiện tại lệch ...`** → Provider/model/dim trong `backend/.env` khác `baseline_native.json`. Khôi phục `RAG_EMBEDDING_PROVIDER` + `RAG_EMBEDDING_MODEL` + dimension đúng baseline (Phase 1 dùng `openai`/`text-embedding-3-large` 3072d). Lý do: gate fairness tuyệt đối.

- **`Docling unhealthy` / smoke FAIL `Expected docling, got native`** → service `docling-pipeline` chưa UP hoặc circuit breaker đang OPEN (Phase 4 CFG-04). Khởi động Docker stack trước (`docker compose up -d docling-pipeline`). Check `GET /api/rag-config` xem `docling_service_status`. Reset breaker bằng `PUT /api/rag-config` `{"extractor_mode": "auto"}` rồi chờ 1 phút.

- **`Empty docling snapshot` / `run_compare.py` báo thiếu `baseline_docling.json`** → chưa chạy `make eval-baseline-docling` lần nào. Chạy nó trước rồi mới `make eval-compare`.

- **Docling extract chậm > 5 phút/file** → chấp nhận. Docling đa cấp + OCR `vie+eng` chậm hơn native 5-10×. Nếu cần, override timeout: `python eval/run_docling.py --upload-timeout 600`.

- **Verdict FAIL** → đọc `EVAL.md`:
  - Section 3 (Per-Query Diff) — query nào REGRESSED / WORSE.
  - Section 4 (Per-Document) — doc nào table preservation rớt.
  - Section 6 (Conclusion) — 3 hướng cụ thể: reranker (999.2 backlog), hybrid retrieval (BM25 + dense), data improvement (gap content như BS Lê Phương Phase 1).
  - Section 7 (Defer) — auto-extract REGRESSED + both_miss query để priority debug.

### 11.7. Liên kết

- Báo cáo cuối: [`EVAL.md`](./EVAL.md) (sinh sau khi `make eval-compare` lần đầu).
- Plan tham chiếu: `.planning/phases/05-eval-compare-quality-gate/05-CONTEXT.md` (mục E gate logic + mục F EVAL.md schema).

---

*Phase 5 hoàn tất ở plan 05-05 (Makefile + README + close M1). Sau khi user chạy runtime end-to-end và `EVAL.md` verdict = PASS, milestone M1 được close qua `/gsd-verify-work 5` hoặc `/gsd-complete-milestone`.*
