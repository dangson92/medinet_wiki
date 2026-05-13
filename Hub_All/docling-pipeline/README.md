# docling-pipeline — Medinet Docling Sidecar

Service Python FastAPI sidecar bọc [Docling](https://github.com/DS4SD/docling) v2.91.0 — extract + chunk tài liệu đa định dạng cho RAG ingestion (Milestone M1 — RAG Quality with Docling).

**Trách nhiệm:**

- Nhận file binary qua `POST /v1/process` (multipart upload).
- Extract: PDF / DOCX / XLSX / PPTX / HTML / PNG / JPEG → `DoclingDocument` (single-thread, OCR Tesseract `vie+eng` cho scanned PDF).
- Chunk: `HybridChunker` với tokenizer `cl100k_base` (default cho OpenAI `text-embedding-3-*`).
- Trả JSON đúng schema DSVC-02: `{request_id, doc_meta, chunks: [...]}`.

**KHÔNG làm:** embedding, ChromaDB upsert, augmenter Q&A — backend Go (`backend/internal/`) vẫn xử lý phần đó (giữ nguyên `SwappableEmbedder` + usage logging async).

---

## 1. Tổng quan kiến trúc

```
┌──────────────────────┐    HTTP multipart       ┌────────────────────────────┐
│  Backend Go          │ ──────────────────────► │  docling-pipeline (FastAPI)│
│  (worker pool +      │   POST /v1/process      │  port 8001 — single worker │
│  pipeline.go)        │   X-Request-Id: <uuid>  │                            │
│                      │ ◄────────────────────── │  ┌──────────────────────┐  │
│  SwappableEmbedder   │   JSON DSVC-02          │  │ Docling library      │  │
│  → ChromaDB upsert   │   {chunks: [...]}       │  │ DocumentConverter +  │  │
└──────────────────────┘                         │  │ HybridChunker +      │  │
                                                 │  │ Tesseract vie+eng    │  │
                                                 │  └──────────────────────┘  │
                                                 └────────────────────────────┘
```

Service nằm sau Go worker. Concurrency 1 request / lần (FIFO) — Docling parser + Tesseract subprocess KHÔNG thread-safe; scale horizontal nếu cần (defer M3).

---

## 2. Cài đặt + chạy

### 2.1 Local (dev nhanh, không Docker)

```bash
cd docling-pipeline

# 1. Tạo venv + install
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -e .[dev]

# 2. Cần Tesseract OCR ngoài pip — cài qua OS
#    Ubuntu/Debian:
sudo apt-get install -y tesseract-ocr tesseract-ocr-vie tesseract-ocr-eng
#    macOS:
brew install tesseract tesseract-lang
#    Windows: tải https://github.com/UB-Mannheim/tesseract/wiki, thêm PATH

# 3. Copy env + chỉnh (tùy chọn)
cp .env.example .env

# 4. Run
uvicorn docling_pipeline.main:app --host 0.0.0.0 --port 8001 --workers 1
```

Lần đầu start sẽ tải model Docling (~vài GB từ HuggingFace) — tốn 30-60s. `/readyz` trả 503 nếu library `docling` import fail (env hỏng); trả 200 sau khi warm xong (lifespan B5 case b/c).

### 2.2 Docker (khuyến nghị — M1 default)

```bash
# Từ ROOT repo Hub_All/
cd ..

# Build (5-10 phút lần đầu — apt install Tesseract + pip install Docling)
docker compose build docling-pipeline

# Start cùng infra (postgres + redis + chroma + docling)
docker compose up -d

# Hoặc chỉ start docling (không cần postgres/redis/chroma cho smoke)
docker compose up -d docling-pipeline

# Tail log đợi event "models_warmed" (B5 case c) hoặc "warm_dummy_failed" (B5 case b)
docker compose logs -f docling-pipeline
```

**Note port mapping:** Service KHÔNG expose port 8001 ra host theo mặc định (security — DSVC-05, chỉ join `medinet-net` internal). Để test thủ công từ host, tạo `docker-compose.override.yml` ở root:

```yaml
services:
  docling-pipeline:
    ports:
      - "8001:8001"
```

Sau đó `docker compose up -d docling-pipeline`. Khi test xong nhớ xoá file override (KHÔNG commit).

---

## 3. Cấu hình env vars

Copy từ `.env.example` (xem mục 2.1) — đầy đủ 9 biến:

| Env                            | Default       | Mô tả                                                                  |
| ------------------------------ | ------------- | ---------------------------------------------------------------------- |
| `DOCLING_OCR_ENGINE`           | `tesseract`   | `tesseract` hoặc `rapidocr` (DSVC-03)                                  |
| `DOCLING_OCR_LANGS`            | `vie+eng`     | Tesseract languages — vie cho tiếng Việt, eng cho fallback (DSVC-03)   |
| `DOCLING_TOKENIZER_NAME`       | `cl100k_base` | Tokenizer cho HybridChunker (CHUNK-01)                                 |
| `DOCLING_MAX_TOKENS_PER_CHUNK` | `512`         | Max tokens / chunk — phù hợp ctx window text-embedding-3-large (8191)  |
| `DOCLING_MAX_FILE_MB`          | `50`          | File vượt → HTTP 413 Payload Too Large (DSVC-06)                       |
| `DOCLING_REQUEST_TIMEOUT_SEC`  | `180`         | Request vượt → HTTP 504 Gateway Timeout (DSVC-06)                      |
| `DOCLING_LOG_LEVEL`            | `INFO`        | DEBUG / INFO / WARNING / ERROR                                         |
| `DOCLING_LOG_FORMAT`           | `json`        | json (production) / console (dev)                                      |
| `DOCLING_HOST`                 | `0.0.0.0`     | Bind address                                                           |
| `DOCLING_PORT`                 | `8001`        | Listen port                                                            |

---

## 4. Endpoints

### 4.1 `GET /healthz` — liveness

```bash
curl http://localhost:8001/healthz
# → {"status":"healthy"}
```

Luôn trả 200 khi process còn alive — KHÔNG phụ thuộc Docling library hay model warm.

### 4.2 `GET /readyz` — readiness (B5)

```bash
curl http://localhost:8001/readyz
# → {"status":"ready"}                                                         (200, case b/c)
# → {"status":"not_ready","reason":"docling_library_unavailable"}             (503, case a)
```

Lifespan B5 phân biệt 3 case:

- **case a** — `import docling` fail → `ready=False` vĩnh viễn (env hỏng, ops phải `pip install docling==2.91.0` rồi restart container).
- **case b** — Library OK nhưng warm dummy PDF fail (transient) → `ready=True` + log warning. Service vẫn serve, request đầu sẽ chậm vì trigger model load lúc đó.
- **case c** — Warm dummy OK → `ready=True` + log info.

### 4.3 `POST /v1/process` — extract + chunk

**Request:** `multipart/form-data`

| Field             | Type           | Required | Mô tả                                                                              |
| ----------------- | -------------- | -------- | ---------------------------------------------------------------------------------- |
| `file`            | binary         | yes      | File PDF/DOCX/XLSX/PPTX/HTML/PNG/JPEG (size ≤ `DOCLING_MAX_FILE_MB`)                |
| `hub_code`        | string (Form)  | optional | Mã hub gọi (echo lại trong log để trace)                                            |
| `doc_type`        | string (Form)  | optional | Loại tài liệu (echo lại log)                                                        |
| `request_id`      | string (Form)  | optional | UUID — ưu tiên thấp hơn header `X-Request-Id`                                       |
| `chunker_options` | string (JSON)  | optional | Override tokenizer / max_tokens per request, vd `{"tokenizer_name":"cl100k_base"}` |

**Header:** `X-Request-Id: <uuid>` — preferred (Go backend inject), echo lại response header để client trace.

**Response 200:** JSON đúng schema DSVC-02 (mục 5).

**Status codes:**

| Code | Khi nào                                                                  |
| ---- | ------------------------------------------------------------------------ |
| 200  | Extract + chunk OK                                                       |
| 400  | `chunker_options` JSON invalid hoặc `filename` thiếu                     |
| 413  | File size > `DOCLING_MAX_FILE_MB` (DSVC-06)                              |
| 415  | Extension không nằm whitelist (PDF/DOCX/XLSX/PPTX/HTML/PNG/JPEG)         |
| 504  | Extract + chunk vượt `DOCLING_REQUEST_TIMEOUT_SEC` (DSVC-06)              |
| 503  | `/readyz` only — library không import được                                |

---

## 5. Schema response `POST /v1/process` (DSVC-02 — ĐÓNG BĂNG)

```json
{
  "request_id": "uuid-từ-X-Request-Id-hoặc-form-hoặc-auto-gen",
  "doc_meta": {
    "filename": "tri_thuc_chinh_tri.pdf",
    "file_type": "pdf",
    "page_count": 12,
    "language_detected": null,
    "ocr_used": false
  },
  "chunks": [
    {
      "chunk_index": 0,
      "text": "...markdown...",
      "headers": ["PHẦN 01", "1.1 Câu định vị"],
      "caption": null,
      "page_start": 1,
      "page_end": 1,
      "is_table": false,
      "table_html": null,
      "bbox": [50.0, 60.0, 500.0, 700.0],
      "token_count": 234
    }
  ]
}
```

Khi `is_table=true` (EXTRACT-03):

- `text` chứa Markdown table flatten (compatibility cho embedder).
- `table_html` chứa HTML đầy đủ với `<thead>`, `<tbody>`, `colspan` / `rowspan` preserved.

Khi figure có caption (EXTRACT-04):

- `text` bắt đầu bằng `![<caption>](#fig-N)` marker.
- KHÔNG insert binary image — chỉ caption text.

`ocr_used` là best-effort detect theo extension (`pdf/png/jpg/jpeg → True`, `docx/xlsx/html → False`); Docling không expose flag chính xác cho việc OCR có thực sự được trigger trên trang nào — defer M3 nếu cần precise.

---

## 6. Smoke test (verify 5 SC Phase 2)

> **W6 — Verify dataset trước:** Trước khi chạy smoke, kiểm tra 2 file dataset đã có sẵn từ Phase 1:
>
> ```bash
> # Từ root Hub_All/
> ls -la eval/dataset/sources/tri_thuc_chinh_tri.pdf       # commit 1d85152 Phase 1
> ls -la eval/dataset/scanned/DMD_T1-01_scanned.pdf        # commit 045d29b Phase 1 (raster từ DOCX gốc)
> ```
>
> Nếu thiếu file: pick first PDF còn tồn tại — `ls eval/dataset/sources/*.pdf | head -1`.

Sau khi service up (Docker hoặc local) và `/readyz` trả 200, chạy 5 SC:

```bash
# SC1 — healthz + readyz
curl -f http://localhost:8001/healthz                          # → {"status":"healthy"}
curl -f http://localhost:8001/readyz                           # → {"status":"ready"} sau warm

# SC2 — PDF normal → schema DSVC-02 (W6 — explicit fixture từ Phase 1)
curl -X POST http://localhost:8001/v1/process \
  -H "X-Request-Id: smoke-test-pdf-$(date +%s)" \
  -F "file=@eval/dataset/sources/tri_thuc_chinh_tri.pdf" \
  -F "hub_code=test" -F "doc_type=test" \
  | jq '.chunks | length'
# Expected: số > 0

# SC3 — scanned PDF tiếng Việt → OCR vie+eng (W6 — đảo ngược fail Phase 1 SC4)
curl -X POST http://localhost:8001/v1/process \
  -H "X-Request-Id: smoke-test-scanned-$(date +%s)" \
  -F "file=@eval/dataset/scanned/DMD_T1-01_scanned.pdf" \
  -F "hub_code=test" -F "doc_type=scanned" \
  | jq '.chunks[0].text'
# Expected: text tiếng Việt (chứa từ "Đỗ Minh", "định vị", "trung tâm" hoặc tương đương)

# SC5 — 413 limit
# Linux/macOS:
dd if=/dev/zero of=/tmp/big.pdf bs=1M count=60 2>/dev/null
curl -i -X POST http://localhost:8001/v1/process -F "file=@/tmp/big.pdf"
# Expected: HTTP/1.1 413 Payload Too Large

# Windows PowerShell:
#   $bytes = New-Object byte[] 62914560
#   [IO.File]::WriteAllBytes("$env:TEMP\big.pdf", $bytes)
#   curl.exe -i -X POST http://localhost:8001/v1/process -F "file=@$env:TEMP\big.pdf"
```

Toàn bộ assertion logic chính thức nằm trong pytest suite (mục 7) — smoke chỉ là sanity check container thật chạy được.

---

## 7. Test suite (pytest)

```bash
cd docling-pipeline
pip install -e .[dev]

# Fast tests (KHÔNG cần OCR/Docling models warm)
pytest -m "not slow" -v

# Toàn bộ (cần Tesseract vie+eng + Docling models đã warm)
pytest -v

# Coverage
pytest --cov=docling_pipeline --cov-report=term-missing
```

6 file test commit ở Plan 02-07 — tham chiếu nhanh:

| File                          | Mục đích                                                                                        | Marker |
| ----------------------------- | ----------------------------------------------------------------------------------------------- | ------ |
| `tests/test_health.py`        | `/healthz` + `/readyz` — phân biệt 3 case lifespan B5                                           | fast   |
| `tests/test_extract.py`       | Schema DSVC-02 đầy đủ + `request_id` propagate (header → response)                              | fast   |
| `tests/test_ocr.py`           | Scanned VN PDF → OCR `vie+eng` extract được text tiếng Việt                                     | slow   |
| `tests/test_table_figure.py`  | `table_html` preserved colspan/rowspan + figure caption marker `![...](#fig-N)` (EXTRACT-03/04) | slow   |
| `tests/test_limits.py`        | 413 (max_file_mb) + 504 (timeout) — monkeypatch slow extract (DSVC-06)                          | fast   |
| `tests/test_logging.py`       | `X-Request-Id` propagate vào structlog stdout (DSVC-04)                                          | fast   |

Fixtures deterministic ở `tests/fixtures/` (5 file PDF/DOCX nhỏ + 1 scanned VN, generate qua `generate_fixtures.py`).

---

## 8. Troubleshooting

**`/readyz` luôn 503 với `reason: docling_library_unavailable`**
Docling library không import được trong container (B5 case a). Vào container check: `docker compose exec docling-pipeline pip list | grep docling`. Nếu thiếu hoặc sai version → rebuild image: `docker compose build --no-cache docling-pipeline`.

**`/readyz` 200 nhưng request đầu rất chậm (30-60s)**
B5 case b — warm dummy fail nhưng library OK. Bình thường, request đầu sẽ trigger model load. Subsequent request nhanh hơn nhiều.

**Container build chậm (~5-10 phút)**
Bình thường lần đầu (apt install Tesseract + download Docling deps). Lần sau cache layer apt + pip; chỉ rebuild khi đổi `pyproject.toml` hoặc `Dockerfile`.

**413 hoặc 504 thường xuyên**
Tăng `DOCLING_MAX_FILE_MB` hoặc `DOCLING_REQUEST_TIMEOUT_SEC` trong `.env` rồi `docker compose up -d` (recreate container). 504 với scanned PDF lớn (> 30 trang) là bình thường vì OCR chậm — cân nhắc tách file.

**Port 5432 / 8000 conflict khi `docker compose up`**
Postgres / ChromaDB local đang chạy trên cùng port. Stop service local trước, hoặc đổi port trong `.env` root (`POSTGRES_PORT=5433`, `CHROMA_PORT=8002`).

**OCR test fail tiếng Việt — text rỗng hoặc toàn ký tự lạ**
Tesseract không có language pack `vie`. Verify trong container: `docker compose exec docling-pipeline tesseract --list-langs | grep vie`. Nếu thiếu → rebuild image (Dockerfile đã apt install `tesseract-ocr-vie`).

**`docling_models/` chiếm dung lượng lớn**
Đúng — HuggingFace cache vài GB. Volume mount để khỏi re-download mỗi rebuild. Có thể move ra ổ khác qua override volume path.

**Build Docker fail: `error during connect: ... open //./pipe/dockerDesktopLinuxEngine`**
Docker Desktop chưa start (Windows). Mở Docker Desktop, đợi engine running, rồi retry `docker compose build`.

---

## 9. Cấu trúc thư mục

```
docling-pipeline/
├── Dockerfile                              # python:3.11-slim + tesseract-ocr-vie/eng
├── pyproject.toml                          # docling==2.91.0 (exact pin)
├── README.md                               # File này
├── .env.example                            # Template 9 biến DOCLING_*
├── .gitignore
├── src/docling_pipeline/
│   ├── __init__.py
│   ├── main.py                             # FastAPI app + lifespan B5
│   ├── config.py                           # Pydantic Settings + lru_cache singleton
│   ├── api/
│   │   ├── __init__.py
│   │   ├── health.py                       # /healthz + /readyz
│   │   └── process.py                      # /v1/process (multipart)
│   ├── core/
│   │   ├── __init__.py
│   │   ├── extractor.py                    # DocumentConverter wrapper (PDF/DOCX/...)
│   │   ├── chunker.py                      # HybridChunker wrapper
│   │   └── serializer.py                   # DoclingDocument → schema DSVC-02
│   └── observability/
│       ├── __init__.py
│       └── logging.py                      # structlog JSON + RequestIdMiddleware
└── tests/
    ├── __init__.py
    ├── conftest.py                         # FastAPI TestClient + fixtures
    ├── fixtures/
    │   └── generate_fixtures.py            # Sinh PDF/DOCX deterministic
    ├── test_health.py
    ├── test_extract.py
    ├── test_ocr.py                         # @slow
    ├── test_table_figure.py                # @slow (B3)
    ├── test_limits.py                      # B4
    └── test_logging.py                     # W4
```

---

## 10. Tham chiếu

- **Phase 2 plan + summary:** `.planning/phases/02-docling-service-python-sidecar/`
- **Schema DSVC-02 chốt ở:** `02-CONTEXT.md` mục "Schema response `POST /v1/process`"
- **Docling docs:** https://github.com/DS4SD/docling
- **HybridChunker:** https://github.com/DS4SD/docling-core
- **Tesseract Vietnamese:** https://github.com/tesseract-ocr/tessdata/blob/main/vie.traineddata

---

*Phase 2 deliver — M1 RAG Quality with Docling (2026-04-29).*
