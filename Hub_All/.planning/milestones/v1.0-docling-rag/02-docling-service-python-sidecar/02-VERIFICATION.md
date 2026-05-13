---
phase: 02-docling-service-python-sidecar
verified: 2026-04-29T00:00:00Z
status: human_needed
score: 5/5 must-haves verified ở mức code; 5/5 SC cần human runtime để đóng
overrides_applied: 0
verdict: PARTIAL (runtime deferred)
re_verification: false
human_verification:
  - test: "SC1 — `docker compose up -d docling-pipeline` rồi `curl http://localhost:8001/healthz` và `curl http://localhost:8001/readyz` (sau ~60s warm)"
    expected: "/healthz → 200 {\"status\":\"healthy\"}; /readyz → 200 {\"status\":\"ready\"}"
    why_human: "Cần Docker Desktop chạy + image build 5-10 phút (Tesseract + Docling models) — không thể verify từ static code"
  - test: "SC2 — `curl -X POST http://localhost:8001/v1/process -H 'X-Request-Id: smoke-pdf-1' -F 'file=@eval/dataset/sources/tri_thuc_chinh_tri.pdf' -F 'hub_code=test' -F 'doc_type=test'`"
    expected: "JSON DSVC-02 với 10 field/chunk (chunk_index, text, headers, caption, page_start, page_end, is_table, table_html, bbox, token_count) + ≥ 1 chunk"
    why_human: "Cần Docling runtime + warm models để parse PDF thật"
  - test: "SC3 — `curl -X POST http://localhost:8001/v1/process -F 'file=@eval/dataset/scanned/DMD_T1-01_scanned.pdf' -F 'hub_code=test' -F 'doc_type=scanned'`"
    expected: "Chunks chứa token tiếng Việt thật (Đỗ Minh Đường / Định vị / Trung tâm), ocr_used=true, KHÔNG có lỗi 'no text extracted'"
    why_human: "Cần Tesseract vie+eng + Docling OCR pipeline thật, OCR quality phụ thuộc binary install trong container"
  - test: "SC4 — Upload PDF có table + figure caption qua /v1/process; inspect chunks"
    expected: "≥ 1 chunk có is_table=true với table_html chứa <table>/<thead>/<tbody>/colspan/rowspan; ≥ 1 chunk text chứa pattern ![<caption>](#fig-N)"
    why_human: "Phụ thuộc Docling 2.91 thật export_to_html() preserve cấu trúc — version drift cần test runtime"
  - test: "SC5 — (a) Upload file > 50MB → 413; (b) Set DOCLING_REQUEST_TIMEOUT_SEC=1 + upload PDF lớn → 504; (c) Inspect `docker compose logs docling-pipeline` — mỗi log line JSON có field request_id khớp X-Request-Id header"
    expected: "(a) HTTP 413 + body detail.error=payload_too_large; (b) HTTP 504 + detail.error=request_timeout; (c) request_id propagate vào structlog stdout"
    why_human: "Test 504 yêu cầu service runtime + reload settings; verify log JSON cần inspect stdout container"
---

# Phase 2: Docling Service (Python Sidecar) — Verification Report

**Phase Goal:** Service `docling-pipeline/` Python FastAPI chạy ổn định trong Docker Compose, nhận file binary qua `POST /v1/process` và trả chunks giàu metadata theo Docling — sẵn sàng để Go adapter Phase 3 gọi vào.
**Verified:** 2026-04-29
**Status:** human_needed (PARTIAL — runtime deferred)
**Re-verification:** Không (initial)

---

## 1. Must-Haves từ ROADMAP Success Criteria

5 SC trong ROADMAP.md line 65-69 + 14 REQ-ID Phase 2 (sau move EXTRACT-05 sang Phase 3 theo 02-CHECK.md).

---

## 2. Per-Criterion Verification

| #   | Success Criterion | Code Status | Runtime Status | Evidence |
| --- | ----------------- | ----------- | -------------- | -------- |
| SC1 | `docker compose up docling-pipeline` healthy: `/healthz` 200 + `/readyz` 200 sau warm | PASS | DEFERRED | Endpoint + lifespan B5 implement đầy đủ — `api/health.py` (200 healthy / 503 not_ready) + `main.py` lifespan 3-case (ImportError / warm transient fail / warm OK). Compose service `docling-pipeline` có healthcheck `curl /healthz` (interval 15s, start_period 60s). Cần Docker Desktop runtime để confirm container thực sự healthy. |
| SC2 | `POST /v1/process` PDF normal → schema DSVC-02 (10 field/chunk) | PASS | DEFERRED | `api/process.py` route handler đầy đủ: multipart upload + parse chunker_options + extract → chunk → serialize. `core/serializer.py` `ChunkDict` TypedDict liệt kê đúng 10 field. Test `test_extract.py::test_process_pdf_returns_schema` assert đầy đủ 10 field + types. Cần Docling runtime parse PDF thật. |
| SC3 | Scanned PDF VN → OCR text VN, KHÔNG `no text extracted` | PASS | DEFERRED | `core/extractor.py` config `TesseractCliOcrOptions(lang=["vie","eng"])` (default settings) + RapidOCR alternative qua env. Dockerfile apt-install `tesseract-ocr-vie tesseract-ocr-eng`. Test `test_ocr.py::test_ocr_scanned_vi_extracts_vietnamese` assert ocr_used=true + tokens VN. Fixture `sample_scanned_vi.pdf` (3.7MB copy từ `eval/dataset/scanned/DMD_T1-01_scanned.pdf`). Cần Tesseract trong container OCR thật. |
| SC4 | Table HTML preserved (rowspan/colspan) + figure caption marker `![..](#fig-N)` | PASS | DEFERRED | `serializer._detect_table_html()` gọi `item.export_to_html(doc=doc)` cho TableItem (preserve cấu trúc). `_inject_figure_caption_marker()` build pattern `![{cap}](#fig-{N})`. Test `test_table_figure.py` 2 case: assert `<table` + `<thead`/`<tbody` trong table_html, regex `!\[[^\]]*\]\(#fig-\d+\)` trong text. Fixture `sample_with_table.pdf` + `sample_with_figure.pdf`. Cần Docling 2.91 runtime export HTML thật. |
| SC5 | 413 (file > max) + 504 (timeout) + request_id propagate trong structured log | PASS | DEFERRED | `api/process.py` raise HTTPException 413 khi `len(body) > max_file_bytes`, raise 504 khi `asyncio.timeout(request_timeout_sec)` trigger TimeoutError. `observability/logging.py::RequestIdMiddleware` clear+bind `request_id`/`path`/`method` vào `structlog.contextvars` mỗi request, echo header response. Test `test_limits.py` (413 + 504) + `test_logging.py::test_request_id_propagated_to_log` (capsys assert rid trong stdout JSON). Cần runtime để confirm log JSON line có rid thật. |

**Code score:** 5/5 — toàn bộ logic + test scaffold + Docker assets sẵn sàng.
**Runtime score:** 0/5 — chưa có evidence container chạy thật (Docker Desktop không khả dụng + Python 3.13 host không tương thích pin `>=3.11,<3.12`).

---

## 3. Required Artifacts

| Artifact                                                                | Expected                                                              | Status     | Details |
| ----------------------------------------------------------------------- | --------------------------------------------------------------------- | ---------- | ------- |
| `docling-pipeline/Dockerfile`                                           | python:3.11-slim + tesseract-ocr-vie/eng + Docling deps               | VERIFIED   | 36 dòng, base `python:3.11-slim-bookworm`, apt install `tesseract-ocr-vie tesseract-ocr-eng libpoppler-cpp-dev poppler-utils`, single-stage, EXPOSE 8001, CMD uvicorn workers=1 |
| `docling-pipeline/pyproject.toml`                                       | docling==2.91.0 exact + fastapi + uvicorn + structlog + tiktoken      | VERIFIED   | 49 dòng, pin `docling==2.91.0`, fastapi 0.115.x, uvicorn 0.32.x, structlog ≥24.4, tiktoken ≥0.8, pydantic-settings ≥2.6, dev deps pytest/httpx/ruff. Marker `slow` registered. |
| `docling-pipeline/src/docling_pipeline/main.py`                         | FastAPI app + lifespan B5 (3 case)                                    | VERIFIED   | 113 dòng, lifespan phân biệt rõ ImportError vs warm transient fail vs warm OK; create_app factory + RequestIdMiddleware; uvicorn entry workers=1 + log_config=None |
| `docling-pipeline/src/docling_pipeline/api/health.py`                   | /healthz + /readyz B5 semantics                                       | VERIFIED   | 53 dòng, /healthz luôn 200, /readyz 503 với reason=docling_library_unavailable khi ready=False, set_models_ready/get_models_ready cho lifespan + test |
| `docling-pipeline/src/docling_pipeline/api/process.py`                  | /v1/process multipart upload + 413/504/415 + schema DSVC-02           | VERIFIED   | 190 dòng, multipart upload, 413 size limit, 504 asyncio.timeout, 415 unsupported extension, 400 invalid chunker_options JSON, asyncio.to_thread wrap blocking work |
| `docling-pipeline/src/docling_pipeline/core/extractor.py`               | DocumentConverter + Tesseract vie+eng + table_structure preservation  | VERIFIED   | 6.5KB, mapping 9 extension → InputFormat, ImageFormatOption (W5) cho IMAGE riêng, Tesseract default + RapidOCR alternative, warm_models() cho lifespan |
| `docling-pipeline/src/docling_pipeline/core/chunker.py`                 | HybridChunker tokenizer cl100k_base + per-request override            | VERIFIED   | 4.9KB, HybridChunker(tokenizer="cl100k_base", max_tokens=512, merge_peers=True) string overload (B2), ChunkerOptions.from_dict cho CHUNK-02/03 override |
| `docling-pipeline/src/docling_pipeline/core/serializer.py`              | DoclingDocument → schema DSVC-02 (10 field) + table_html + figure marker | VERIFIED | 306 dòng, ChunkDict TypedDict đúng 10 field, _detect_table_html() gọi export_to_html, _inject_figure_caption_marker() pattern `![..](#fig-N)`, defensive getattr cho version drift |
| `docling-pipeline/src/docling_pipeline/observability/logging.py`        | structlog JSON + RequestIdMiddleware bind X-Request-Id                | VERIFIED   | 94 dòng, JSON renderer khi log_format=json, PrintLoggerFactory(file=sys.stdout), RequestIdMiddleware clear+bind contextvars (request_id+path+method), echo header response |
| `docling-pipeline/tests/conftest.py` + 6 file test                      | TestClient session + 12 test case (4 fast + 8 slow)                   | VERIFIED   | conftest 1.7KB session-scoped TestClient + 5 fixture binary; test_health (2) + test_extract (4) + test_ocr (1) + test_table_figure (2) + test_limits (2) + test_logging (1) = 12 test |
| `docling-pipeline/tests/fixtures/` (5 fixture binary + script)          | sample_small.pdf/docx + sample_scanned_vi + with_table + with_figure  | VERIFIED   | 5 file binary commit (1.6KB / 36KB / 3.7MB / 1.7KB / 2.8KB) + generate_fixtures.py reportlab+pillow+python-docx |
| `docling-pipeline/README.md`                                            | Install + env + endpoints + schema + smoke 5 SC + troubleshoot        | VERIFIED   | 372 dòng tiếng Việt; chứa DSVC-02, vie+eng, docker compose build, tri_thuc_chinh_tri.pdf, DMD_T1-01_scanned.pdf; smoke commands cho 5 SC explicit |
| `docker-compose.yml` (root)                                             | 4 service: postgres + redis + chroma + docling-pipeline + medinet-net | VERIFIED   | 112 dòng, postgres:16-alpine + redis:7-alpine + chromadb/chroma:latest + docling-pipeline build từ ./docling-pipeline; healthcheck đủ 4 service; depends_on chuỗi đúng; volume `./docling_models` cho HuggingFace cache |

**Tổng: 13/13 artifacts VERIFIED ở mức code.**

---

## 4. Key Link Verification

| From                             | To                              | Via                                          | Status | Details |
| -------------------------------- | ------------------------------- | -------------------------------------------- | ------ | ------- |
| `main.py` lifespan               | `core/extractor.warm_models`    | Lazy import + asyncio.to_thread              | WIRED  | line 56-69, try/except ImportError → set_models_ready(False); except generic → set_models_ready(True) + log warning |
| `main.py` create_app             | `RequestIdMiddleware`           | `app.add_middleware`                         | WIRED  | line 93 |
| `main.py` create_app             | `health.router` + `process.router` | `app.include_router`                       | WIRED  | line 94-95 |
| `api/process.py` handler         | `core/extractor.get_extractor`  | Singleton lru_cache + asyncio.to_thread      | WIRED  | line 100, 114 — extract trong _run() |
| `api/process.py` handler         | `core/chunker.get_chunker`      | Singleton lru_cache + asyncio.to_thread      | WIRED  | line 101, 115 — chunk trong _run() |
| `api/process.py` handler         | `core/serializer.serialize_chunks` | Direct call                               | WIRED  | line 170 — pass tokenizer_name từ chunk_opts hoặc settings |
| `RequestIdMiddleware` dispatch   | structlog contextvars           | bind_contextvars(request_id=...)             | WIRED  | logging.py line 80-84 |
| `compose docling-pipeline` build | `./docling-pipeline/Dockerfile` | build context + dockerfile                   | WIRED  | docker-compose.yml line 69-71 |
| `compose docling-pipeline` healthcheck | `curl /healthz`           | CMD test                                     | WIRED  | line 94-99 (start_period 60s — đủ thời gian warm) |

**9/9 key links WIRED ở mức code.** Runtime confirm cần container live.

---

## 5. Requirements Coverage (14 REQ Phase 2)

| Requirement | Source Plan(s)            | Description                                        | Status     | Evidence |
| ----------- | ------------------------- | -------------------------------------------------- | ---------- | -------- |
| DSVC-01     | 02-06, 02-07, 02-08       | Endpoint `POST /v1/process` multipart contract     | SATISFIED  | api/process.py route + test_extract |
| DSVC-02     | 02-05, 02-07, 02-08       | Response schema 10 field/chunk                     | SATISFIED  | serializer.ChunkDict + test_extract field assertion |
| DSVC-03     | 02-03, 02-08              | OCR Tesseract vie+eng default                      | SATISFIED  | extractor _build_ocr_options + Dockerfile apt install |
| DSVC-04     | 02-06, 02-07, 02-08       | Propagate X-Request-Id structlog                   | SATISFIED  | RequestIdMiddleware + test_logging capsys assert |
| DSVC-05     | 02-01, 02-02, 02-08       | Single uvicorn worker + container internal port    | SATISFIED  | Dockerfile CMD --workers 1 + compose expose-only |
| DSVC-06     | 02-01, 02-06, 02-07, 02-08| 413 max_file_mb + 504 request_timeout              | SATISFIED  | api/process raise 413/504 + test_limits 2 case |
| EXTRACT-01  | 02-03, 02-07              | DocumentConverter 1 luồng cho mọi format           | SATISFIED  | _EXT_TO_FORMAT mapping 9 ext → InputFormat |
| EXTRACT-02  | 02-03, 02-07, 02-08       | OCR vie+eng cho scanned PDF                        | SATISFIED  | TesseractCliOcrOptions + test_ocr |
| EXTRACT-03  | 02-05, 02-07, 02-08       | Table HTML preserve rowspan/colspan                | SATISFIED  | serializer._detect_table_html → export_to_html + test_table_html_preserved |
| EXTRACT-04  | 02-05, 02-07, 02-08       | Figure caption marker `![..](#fig-N)`              | SATISFIED  | serializer._inject_figure_caption_marker + test_figure_caption_marker |
| CHUNK-01    | 02-04                     | HybridChunker tokenizer default cl100k_base        | SATISFIED  | chunker.py HybridChunker(tokenizer="cl100k_base") |
| CHUNK-02    | 02-04                     | Per-request chunker options override               | SATISFIED  | ChunkerOptions.from_dict |
| CHUNK-03    | 02-05, 02-06              | Token count via tiktoken theo tokenizer_name       | SATISFIED  | serializer._count_tokens(text, encoding) + endpoint truyền tokenizer_name |
| CHUNK-04    | 02-04                     | KHÔNG augment Q&A trong chunker (pristine)         | SATISFIED  | chunker.py docstring + KHÔNG có augmentation logic |

**Coverage:** 14/14 REQ SATISFIED ở mức code. EXTRACT-05 đã được move sang Phase 3 (orphan B1 đã đóng theo 02-CHECK.md).

**Orphan check:** Không có orphan — REQUIREMENTS.md ánh xạ Phase 2 chính xác 14 REQ này.

---

## 6. Anti-Patterns Scan

| File                                            | Severity | Issue | Note |
| ----------------------------------------------- | -------- | ----- | ---- |
| (none)                                          | -        | -     | KHÔNG phát hiện TODO/FIXME/PLACEHOLDER nào trong source. KHÔNG có handler trả static `[]`/`{}` ngụy tạo. KHÔNG có endpoint chỉ `console.log`/`print`. Tất cả 12 test case có assertion thực, không skip/pass placeholder. |

`ocr_used` best-effort theo extension là **design choice đã document** (Decision #4 Plan 06) không phải stub. `language_detected=None` là M1 scope chốt (không cần precise language detection). 5 fixture binary commit deterministic.

---

## 7. Behavioral Spot-Checks

| Behavior                                       | Command                                                                | Result                       | Status |
| ---------------------------------------------- | ---------------------------------------------------------------------- | ---------------------------- | ------ |
| Pytest collect 12 test case                    | `pytest --collect-only`                                                | 12 collected (per Plan 07 SUMMARY) | PASS  |
| AST parse 13 file Python                       | `python -c "import ast; ast.parse(open(f).read())"` cho mỗi file       | All OK (per Plan 06+07 SUMMARY) | PASS  |
| `from docling_pipeline.main import create_app` host                     | `python -c ...`                                       | ImportError fastapi/structlog (host không cài deps + Python 3.13 vs pin <3.12) | SKIP — đã document, runtime trong Docker container |
| `docker compose config` validate compose schema | `docker compose -f docker-compose.yml config`                         | Cần Docker daemon            | SKIP — Docker Desktop không khả dụng |
| `curl http://localhost:8001/healthz`           | `curl -f http://localhost:8001/healthz`                                | Cần container running        | SKIP — defer user smoke |

**Spot-check status:** 2/5 PASS, 3/5 SKIP do constraint runtime (Docker Desktop + Python 3.13 host). Đã document trong Plan 07/08 SUMMARY (Deviation #1 ở mỗi plan).

---

## 8. Human Verification Required

Xem section frontmatter `human_verification:` ở đầu file. 5 SC cần user chạy local sau khi start Docker Desktop:

### 1. SC1 — healthz/readyz container healthy

**Test:**
```bash
docker compose build docling-pipeline           # 5-10 phút lần đầu
docker compose up -d docling-pipeline
docker compose logs -f docling-pipeline         # đợi event "models_warmed" state=ready (~30-60s)
curl -f http://localhost:8001/healthz           # → 200 {"status":"healthy"}
sleep 60
curl -f http://localhost:8001/readyz            # → 200 {"status":"ready"}
```
**Expected:** /healthz 200 ngay lập tức, /readyz 200 sau warm.

### 2. SC2 — Schema DSVC-02 với PDF normal

**Test:**
```bash
curl -X POST http://localhost:8001/v1/process \
  -H "X-Request-Id: smoke-pdf-1" \
  -F "file=@eval/dataset/sources/tri_thuc_chinh_tri.pdf" \
  -F "hub_code=test" -F "doc_type=test" -o /tmp/smoke_pdf.json
python -c "import json; d=json.load(open('/tmp/smoke_pdf.json')); ch=d['chunks'][0]; assert all(k in ch for k in ['chunk_index','text','headers','caption','page_start','page_end','is_table','table_html','bbox','token_count'])"
```
**Expected:** JSON với `request_id`, `doc_meta` (filename, file_type, page_count, language_detected, ocr_used), `chunks[]` mỗi chunk đủ 10 field.

### 3. SC3 — OCR scanned PDF tiếng Việt

**Test:**
```bash
curl -X POST http://localhost:8001/v1/process \
  -F "file=@eval/dataset/scanned/DMD_T1-01_scanned.pdf" \
  -F "hub_code=test" -F "doc_type=scanned" -o /tmp/smoke_scanned.json
python -c "import json; d=json.load(open('/tmp/smoke_scanned.json')); txt=' '.join(c['text'] for c in d['chunks']).lower(); assert any(t in txt for t in ['đỗ minh','định vị','trung tâm']), 'OCR VN fail'"
```
**Expected:** ocr_used=true, ≥ 1 chunk text chứa từ tiếng Việt nhận diện.

### 4. SC4 — Table HTML + figure caption

**Test:** Upload `tests/fixtures/sample_with_table.pdf` (qua container hoặc copy ra host) → response phải có chunk is_table=true với table_html chứa `<table`/`<thead`/`<tbody`. Upload `sample_with_figure.pdf` → text chunks chứa pattern `![...](#fig-N)`.
**Expected:** Pattern HTML preserved + figure marker.

### 5. SC5 — Limits 413 + 504 + request_id log

**Test (Linux):**
```bash
dd if=/dev/zero of=/tmp/big.pdf bs=1M count=60   # tạo file 60MB > 50MB default
curl -i -X POST http://localhost:8001/v1/process -F "file=@/tmp/big.pdf"
# → HTTP/1.1 413 Payload Too Large
docker compose logs docling-pipeline | grep smoke-pdf-1     # phải thấy request_id trong JSON line
```
**Test (Windows PowerShell):**
```powershell
$bytes = New-Object byte[] 62914560; [IO.File]::WriteAllBytes("$env:TEMP\big.pdf", $bytes)
curl.exe -i -X POST http://localhost:8001/v1/process -F "file=@$env:TEMP\big.pdf"
```
504 test cần restart container với `DOCLING_REQUEST_TIMEOUT_SEC=1` rồi upload PDF bất kỳ.
**Expected:** 413 response cho file lớn; 504 response khi timeout; log JSON line chứa `request_id` khớp X-Request-Id header.

---

## 9. Overall Verdict — PARTIAL (runtime deferred)

**Code Verdict: COMPLETE.** 13/13 artifacts có thật, 14/14 REQ-ID Phase 2 SATISFIED ở mức code, 9/9 key link WIRED, 12 pytest test scaffold (collect-only PASS). KHÔNG có stub, KHÔNG có TODO/FIXME, KHÔNG có anti-pattern blocker.

**Runtime Verdict: DEFERRED.** 5/5 SC chưa có evidence container chạy thật vì:
- Docker Desktop không khả dụng trên dev environment hiện tại (`docker ps` fail, đã document Plan 08 SUMMARY Deviation #1).
- Host Python 3.13.4 không tương thích `requires-python = ">=3.11,<3.12"` (Plan 07 SUMMARY Deviation #1).
- Decision: defer Option B đã pre-approve trong Plan 02-08 objective — KHÔNG retry vô hạn, mark Phase 2 PARTIAL chờ user smoke.

**Tác động xuống Phase 3:** **KHÔNG bị block.** Contract DSVC-01 (endpoint signature multipart upload với field `file` + form data + X-Request-Id header) và DSVC-02 (response schema 10 field chốt qua `ChunkDict` TypedDict + tài liệu `02-CONTEXT.md` mục Schema + README mục 5) đã đóng băng qua code + docs. Phase 3 Go adapter `DoclingExtractor` có thể implement với mock JSON response cho unit test ngay; integration test cuối Phase 3 chờ user confirm smoke Phase 2 pass.

---

## 10. User Must Do — 5 lệnh để hoàn tất runtime

```bash
# 0. Start Docker Desktop trên Windows (mở app, đợi engine running)

# 1. Build container (5-10 phút lần đầu — download Tesseract + Docling models)
cd D:/ChuongNV_Medinet/AI/medinet_wiki/Hub_All
docker compose build docling-pipeline

# 2. (Optional) override expose port 8001 ra host để smoke từ host
cat > docker-compose.override.yml <<'EOF'
services:
  docling-pipeline:
    ports:
      - "8001:8001"
    depends_on: []
EOF

# 3. Start service (một mình, không cần postgres/chroma cho smoke)
docker compose up -d docling-pipeline
docker compose logs -f docling-pipeline    # đợi event "models_warmed" state=ready (~30-60s)

# 4. Verify 5 SC theo `docling-pipeline/README.md` mục 6 hoặc `02-08-SUMMARY.md` mục "Checklist user chạy local"

# 5. Cleanup
docker compose down
rm docker-compose.override.yml
```

Sau khi smoke pass đủ 5 SC → mark Phase 2 COMPLETE qua `/gsd-mark-phase 2 complete` (hoặc command tương đương). Nếu fail bất kỳ SC nào → paste log + status code để re-route fix theo Plan 02-08 task 2 resume signal.

---

## 11. Gaps Summary

Không có gap blocker ở mức code. Toàn bộ 5 SC, 14 REQ, 13 artifacts, 9 key link, 12 test case, README + Docker assets đều có thật và đúng spec. Gap duy nhất là **runtime confirmation** — yêu cầu chạy Docker Desktop + container thật, không thể verify từ static code/grep.

---

*Verified: 2026-04-29 · Verifier: Claude (gsd-verifier, Opus 4.7 1M)*
