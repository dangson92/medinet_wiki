# CONTEXT — Phase 2: Docling Service (Python Sidecar)

**Phase:** 2 / 5
**Milestone:** M1 — RAG Quality with Docling
**Goal:** Service `docling-pipeline/` Python FastAPI chạy ổn định trong Docker Compose, nhận file binary qua `POST /v1/process` và trả về chunks giàu metadata theo Docling — sẵn sàng để Go adapter ở Phase 3 gọi vào.
**Requirements:** DSVC-01..06, EXTRACT-01..05, CHUNK-01..04 (15 REQ)
**Ngày discuss:** 2026-04-28

---

## Decisions Locked

### A. Docker base image — `python:3.11-slim` CPU-only

- Base: `python:3.11-slim-bookworm` (~150MB).
- Tesseract OCR cài qua `apt-get install -y tesseract-ocr tesseract-ocr-vie tesseract-ocr-eng`.
- KHÔNG có CUDA/GPU — chạy CPU thuần. Phù hợp server hiện tại (Windows dev + Linux production thường).
- Single-stage build cho đơn giản (không multi-stage). Image final ~2.5GB do Docling deps + OCR languages + HuggingFace models cache lazy-load.
- `pip install --no-cache-dir docling==2.91.* fastapi uvicorn[standard] python-multipart structlog tiktoken` — pin chính xác.

**Vì sao chọn:** Production y tế Medinet không cần real-time inference; Docling CPU vẫn xử lý 1 PDF / 5-15s, đủ async qua worker pool Go. GPU thêm vận hành phức tạp + chi phí cloud, lùi nếu cần.

### B. Docker compose — root repo `docker-compose.yml`

Tạo MỚI `docker-compose.yml` ở root `Hub_All/` (chưa tồn tại) với 4 service:
- `postgres` (postgres:16-alpine, port 5432, mount volume `./postgres_data`)
- `redis` (redis:7-alpine, port 6379)
- `chroma` (chromadb/chroma:latest, port 8000, mount volume `./chroma_data`)
- `docling-pipeline` (build từ `./docling-pipeline/Dockerfile`, port 8001 internal, KHÔNG expose host)

Backend Go **vẫn chạy native** (`make run` trên host), KHÔNG dockerize trong M1. Lý do: backend đã chạy ổn local, dockerize backend là milestone hardening riêng.

Network: `medinet-net` (bridge), tất cả service join chung. Backend Go gọi `docling-pipeline` qua `http://localhost:8001` (host network) hoặc `http://docling-pipeline:8001` nếu sau này backend cũng dockerize.

Volume cho Docling model cache: `./docling_models:/root/.cache/docling` — tránh re-download HuggingFace models mỗi khi rebuild container (~vài GB).

**Vì sao chọn:** 1 lệnh `docker compose up -d` start full infra; team mới onboard 5 phút. Backend Go giữ native cho dev velocity (hot reload, dễ debug). Compose include Postgres/Chroma/Redis vì đang chạy ad-hoc → chuẩn hóa luôn.

### C. Tokenizer cho HybridChunker — `cl100k_base`

Embedding hiện tại: OpenAI `text-embedding-3-large` (3072 dim) — tokenizer `cl100k_base` (qua `tiktoken`).

- Default tokenizer cho `HybridChunker`: `cl100k_base` (env `DOCLING_TOKENIZER_NAME=cl100k_base`).
- Khi user switch sang Gemini qua `PUT /api/rag-config`, backend phải **truyền tokenizer mới qua request body** sang `docling-pipeline` (vd `chunker_options.tokenizer_name`). Service hỗ trợ override per-request.
- Nếu không truyền → dùng env default.

**Tokenizer cho Gemini:** Gemini không có public tokenizer python-installable. Workaround: dùng `cl100k_base` cho Gemini cũng OK (sai số ±10% vs Gemini real tokenizer, không phá HybridChunker logic vì merge_peers chỉ cần ≈ token count). Defer chính xác sang M3.

**Max tokens per chunk:** mặc định 512 (theo Docling HybridChunker default), phù hợp với context window text-embedding-3-large (8191 tokens).

### D. Service runtime + concurrency

- ASGI: `uvicorn` với **1 worker** (Docling parser KHÔNG thread-safe, đặc biệt OCR Tesseract qua subprocess).
- Async: FastAPI async endpoint, internal Docling call wrap trong `asyncio.to_thread()` để không block event loop.
- Concurrency model: 1 request / lần (FIFO). Backend Go worker pool chỉ enqueue 1 job tại 1 thời điểm sang Docling — tránh OOM khi Docling load models concurrent.
- Scale horizontal nếu cần: chạy multiple container, load-balancer phía trước. Defer M3.

**Limits:** `DOCLING_MAX_FILE_MB=50`, `DOCLING_REQUEST_TIMEOUT_SEC=180` — DSVC-06.

### E. OCR engine — Tesseract default + RapidOCR alternative

- Default: Tesseract `vie+eng` (đã chốt DSVC-03). Stable, multilingual, free, pre-installed in container.
- Alternative: RapidOCR (env `DOCLING_OCR_ENGINE=rapidocr`) — nhanh hơn Tesseract ~2-3x cho scanned PDF nhưng quality tiếng Việt kém hơn.
- **NOT** include SuryaOCR trong M1 — model nặng (1GB+), defer khi có data thực tế chứng minh value.

### F. Test framework Python

- `pytest>=8` trong `docling-pipeline/tests/` — riêng biệt với `eval/`.
- 3 nhóm test:
  - `test_health.py` — health/ready endpoints.
  - `test_extract.py` — fixture 1 PDF + 1 DOCX nhỏ (< 100KB) → assert schema DSVC-02 đúng.
  - `test_ocr.py` — fixture 1 scanned PDF tiếng Việt 1 trang → assert text tiếng Việt extract được (chứa từ "Đỗ Minh Đường" hoặc tương đương).
- Lint: `ruff` (cùng convention với `eval/`).

**Mục tiêu coverage Phase 2:** 60-70% cho service Python (dễ test vì stateless). KHÔNG yêu cầu coverage backend Go (defer M2 hardening).

---

## Schema response `POST /v1/process` (DSVC-02 chốt)

```json
{
  "request_id": "<uuid từ X-Request-Id header>",
  "doc_meta": {
    "filename": "...",
    "file_type": "pdf|docx|...",
    "page_count": 12,
    "language_detected": "vi",
    "ocr_used": false
  },
  "chunks": [
    {
      "chunk_index": 0,
      "text": "...markdown...",
      "headers": ["PHẦN 01", "1.1 Câu định vị"],
      "caption": "<nếu chunk là caption của figure>",
      "page_start": 1,
      "page_end": 1,
      "is_table": false,
      "table_html": null,
      "bbox": [x0, y0, x1, y1],
      "token_count": 234
    }
  ]
}
```

Khi `is_table=true`:
- `text` chứa Markdown table flatten (compatibility).
- `table_html` chứa HTML đầy đủ với `<thead>`, `<tbody>`, `colspan/rowspan` preserved.

Khi figure có caption:
- Insert vào chunk `text` dưới dạng `![<caption>](#fig-{N})`.
- Không insert binary image — chỉ caption.

---

## Cấu trúc thư mục `docling-pipeline/` (Phase 2 deliver)

```
docling-pipeline/
├── Dockerfile                       # python:3.11-slim + tesseract-ocr-vie/eng + Docling deps
├── docker-compose.yml               # MOVED to repo root — chỉ giữ Dockerfile ở đây
├── pyproject.toml                   # PEP 621, deps pinned
├── README.md                        # Run instructions, env vars, smoke test
├── .env.example
├── .gitignore                       # __pycache__, .ruff_cache, *.egg-info
├── src/
│   ├── docling_pipeline/
│   │   ├── __init__.py
│   │   ├── main.py                  # FastAPI app + lifespan (warm Docling models on startup)
│   │   ├── config.py                # Pydantic settings từ env
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── health.py            # /healthz + /readyz
│   │   │   └── process.py           # /v1/process (multipart upload)
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── extractor.py         # Wrapper Docling DocumentConverter
│   │   │   ├── chunker.py           # Wrapper HybridChunker với tokenizer
│   │   │   └── serializer.py        # Map DoclingDocument → response schema
│   │   └── observability/
│   │       ├── __init__.py
│   │       └── logging.py           # structlog JSON logging + request_id
└── tests/
    ├── __init__.py
    ├── conftest.py                  # FastAPI TestClient + fixtures
    ├── fixtures/                    # PDF/DOCX nhỏ commit cho test
    ├── test_health.py
    ├── test_extract.py
    └── test_ocr.py
```

**File ROOT repo MỚI:**
- `docker-compose.yml` (4 service: postgres, redis, chroma, docling-pipeline).

---

## Ngữ cảnh từ Phase 1 (đừng quên)

- Baseline native: top-3 = **75%** sau fix `min_score`. Phase 5 phải đẩy lên ≥ 91.7% (≥ 11/12 hit) để pass gate.
- 3 query Docling phải fix: q05 (table T3-02 vs T1-01), q09 + q10 (scanned PDF OCR).
- 2 scanned PDF (`DMD_T1-01_scanned.pdf`, `DMD_T1-04_scanned.pdf`) trong `eval/dataset/scanned/` đã có sẵn — dùng làm smoke test cho SC3 (OCR vie+eng).
- Backend Go đã fix `min_score=0` → khi Phase 3 wire, search vẫn hoạt động đúng.

---

## Out of Scope Phase 2 (defer)

- ❌ GPU/CUDA support — defer M3 nếu cần performance.
- ❌ Multi-worker uvicorn / horizontal scaling — defer M3.
- ❌ MCP endpoint trong Docling service — milestone MCP riêng.
- ❌ Caching DoclingDocument JSON ở Redis (re-chunk không cần re-extract) — defer v2 backlog.
- ❌ Augmenter Q&A trong Python service — giữ ở Go (đã có augmenter Go chạy ổn).
- ❌ Dockerize backend Go — defer hardening milestone.
- ❌ Tokenizer Gemini chính xác — workaround dùng `cl100k_base` cho cả 2.

## Gray Areas đã decide bằng default (không thảo luận sâu)

- Tokenizer (mục C) — chốt cl100k_base.
- Concurrency model (mục D) — single worker uvicorn.
- OCR alternative (mục E) — Tesseract default, RapidOCR option.
- Test framework (mục F) — pytest riêng `docling-pipeline/tests/`.

## Deferred Ideas (cho roadmap backlog)

- 999.3 — DoclingDocument cache ở Redis để re-chunk không cần re-extract khi tune chunker params.
- 999.4 — Multi-worker / queue-based scaling cho Docling khi traffic > 10 docs/min.
- 999.5 — SuryaOCR layer cho ngôn ngữ Á đông phức tạp (Trung, Nhật, Hàn).

## Rủi ro & Câu hỏi mở

- **Rủi ro 1:** Docling lần đầu start sẽ tải HuggingFace models (~vài GB) — chậm. Mitigation: volume mount cache + retry logic + healthcheck readiness phải kiểm tra models loaded.
- **Rủi ro 2:** Tesseract `vie+eng` quality cho scanned PDF tiếng Việt cũ (chữ mờ) có thể không tốt. Smoke test với 2 file `DMD_T1-01_scanned.pdf` + `DMD_T1-04_scanned.pdf` (do `build_scanned.py` từ DOCX gốc → quality cao) — chấp nhận trong M1, đánh giá lại với data thực tế Phase 5.
- **Rủi ro 3:** `python:3.11-slim` thiếu binary deps cho một số Python wheel (vd `pillow`, `pdf2image` cần `libpoppler`, `libjpeg`, `zlib`). Dockerfile phải `apt-get install` đầy đủ — sẵn sàng debug nếu install fail.
- **Câu hỏi mở:** Phase 3 wire khi mock service hay đợi Phase 2 done? **Default:** Phase 2-3 chạy song song, Phase 3 dùng mock JSON response trong unit test, integration test cuối Phase 3 phải đợi Phase 2 ready.

---

## Downstream

**gsd-planner Phase 2 sẽ đọc CONTEXT này để biết:**
- Base image + deps cụ thể → Dockerfile có template ngay.
- Cấu trúc thư mục `docling-pipeline/` → tạo skeleton plan đầu tiên.
- Schema response chốt → service code có signature rõ ràng.
- 3 nhóm test → planner chia plan test riêng.
- Docker compose root → 1 plan riêng cho compose file.

**gsd-phase-researcher có thể skip** nếu plan-checker phase 1 đã verify đủ. Hoặc spawn researcher minimal để fetch ví dụ Docling official về `HybridChunker` config + `DocumentConverter` API signatures.

---

*Last updated: 2026-04-28*
