# Phase 9: Eval Framework + Quality Gate ≥75% top-3 — Research

**Researched:** 2026-05-21
**Domain:** RAG eval framework (Python pytest-based) đo top-K recall + MRR + latency p50/p95/p99 + Markdown report gen, dữ liệu VN medical
**Confidence:** HIGH (stack hiện hữu, pattern M1 archive ÔN dụng được; dim 1536 quality VN cho gate ≥75% là EMPIRICAL — không thể research lý thuyết, chính eval framework Phase 9 sẽ trả lời)

---

## Summary

Phase 9 là phase CUỐI cùng đảm bảo chất lượng cho M2 ship-ready: build framework pytest đo retrieval top-1/3/5 + MRR + latency p50/p95/p99 trên dataset 10 file VN medical + 12 query vàng → emit `results.json` + `EVAL.md` → exit code 0/1 CI-friendly. **Gate cứng:** `top-3 ≥ 75% absolute` (KHÔNG dùng +15pp delta — M1 abandoned, không có baseline để so).

3 thuận lợi lớn:
1. **Dataset M1 ĐÃ TỒN TẠI hoàn chỉnh trong git history** (commit `0af44f0` initial repo): 7 DOCX DMD (`DMD_T1-01..04`, `DMD_T3-02`, `DMD_T5-01..02`) + 1 PDF text (`tri_thuc_chinh_tri.pdf`) + 2 scanned PDF (`DMD_T1-01_scanned.pdf`, `DMD_T1-04_scanned.pdf`) + `queries.jsonl` 12 dòng + `headings.json` + `DATASET.md` + `QUERIES_REVIEW.md`. **KHÔNG cần generate dataset mới** — restore từ git là khả thi và rẻ. [VERIFIED: git show 0af44f0 --stat | grep -E "(sources|queries|scanned)"]
2. **Pattern eval framework M1 (`eval/baseline.py` 588 dòng)** áp dụng gần như nguyên: pre-flight check, APIClient auto-refresh JWT, upload+poll, search, compute top-K + MRR, snapshot JSON. Chỉ cần adapt 4 điểm: (a) endpoint Phase 6 `POST /api/search` body (D-02 `query` không phải `q`), (b) match field `result.title = filename` (không phải `result.category` như Go cũ), (c) poll BackgroundTask trigger_cocoindex_update với race fix delay+retry, (d) thêm latency p50/p95/p99 phép đo + 415 `failed_unsupported` handling cho 2 scanned PDF. [VERIFIED: M1 baseline.py git show 0af44f0:Hub_All/eval/baseline.py; M2 schema xem `api/app/schemas/search.py` + `api/app/routers/search.py`]
3. **Stack pytest + testcontainers ĐÃ chạy thành công ở Phase 4 E2E** (`tests/integration/test_ingest_e2e.py` 580 dòng PASSED 2026-05-21 sau race fix). Phase 9 đi theo cùng pattern — `pytest -m critical -m integration` với fixture `app_with_auth` + `_cocoindex_env` session-scoped + `mock_litellm_embedding` cho CI offline. Eval thật (chạy `make eval-all` với key OpenAI thật) là track riêng ngoài pytest CI gate.

**Primary recommendation:** **Hybrid 2 track** — (1) `eval/run_eval.py` STANDALONE script Python chạy với stack docker-compose đã up (uvicorn + postgres + redis) cho dev/CI quality gate thực thi (offline mock embedding HOẶC online OpenAI thật tuỳ env `EVAL_MOCK_EMBED=1`); (2) `tests/integration/test_eval_pipeline.py` pytest+testcontainers smoke 1 file đảm bảo pipeline KHÔNG vỡ regression. Track 1 là gate chính (≥75% top-3); Track 2 là smoke CI nhanh (<60s).

---

<user_constraints>
## User Constraints (from context Phase 9)

> Phase 9 KHÔNG có file `09-CONTEXT.md` riêng (`/gsd-discuss-phase` chưa chạy) — constraints lấy từ REQUIREMENTS.md EVAL-01..04, ROADMAP.md Phase 9 SC, PROJECT.md EXIT Criteria E5, và context user cung cấp trong /research command.

### Locked Decisions (từ REQUIREMENTS.md + ROADMAP.md + user research context)

- **Quality gate:** `top-3 ≥ 75% tuyệt đối` — KHÔNG dùng +15pp delta (M1 abandoned, không có baseline native để so). PASS → exit 0; FAIL → exit 1 (CI-friendly).
- **Trigger E5 STOP M2b:** Quality gate fail < 60% top-3 dù iterate 3 vòng chunker/prompt → STOP M2b, ship M2a standalone, discuss reranker / hybrid BM25 cho v3.0.
- **Dataset:** 10 file VN medical — `Hub_All/eval/dataset/sources/` (8 file gốc: 7 DOCX DMD + `tri_thuc_chinh_tri.pdf`) + `Hub_All/eval/dataset/scanned/` (2 scanned PDF).
- **Queries:** 12 truy vấn vàng `eval/queries.jsonl` — port semantic từ M1 archive (`0af44f0:Hub_All/eval/dataset/queries.jsonl`), thêm `hub_id` per REQUIREMENTS line 9 dòng schema.
- **Endpoint đo:** `POST /api/search` (Phase 6 D-02 — body `query` không `q`) **WITH `hub_id` filter** (R2 verify thật post-filter HNSW recall — KHÔNG measure without).
- **Stack pin (KHÔNG bump):** Python ≥3.11,<3.13 (khuyến nghị 3.12) · FastAPI 0.136.1 · cocoindex 1.0.3 · pgvector 0.4.2 · asyncpg 0.30.0 · LiteLLM 1.83.14 · pytest 8.4 · httpx 0.28.1.
- **Embedding dim:** PIN 1536 cho cả OpenAI + Gemini (R1 mitigation pgvector 2000-dim index limit) — dim 1536 vs 3072 quality VN là EMPIRICAL câu hỏi chính Phase 9 trả lời.
- **HNSW tuning:** `SET LOCAL hnsw.ef_search = 200` + `iterative_scan = relaxed_order` + `max_scan_tuples = 20000` đã apply ở Phase 6 — eval chỉ verify recall WITH hub filter thật sự không vỡ.
- **Latency budget:** Search p95 <800ms single hub, <1.5s cross-hub trên 10K chunks (Phase 6 SC5 — đo trên dataset thật bị defer sang Phase 9).
- **Scanned PDF:** Format whitelist `{.docx, .txt, .md, .pdf}` — 2 scanned PDF eval sẽ trả 415 `UNSUPPORTED_FORMAT` + `documents.status='failed_unsupported'` (R4 mitigation Phase 4); eval framework PHẢI tolerant với 415 không treat as upload failure (đếm vào "intentionally failed" category).
- **Race condition Phase 4:** `trigger_cocoindex_update` có initial delay 0.1s + retry loop 3 attempts với linear backoff 0.5s/1.0s/1.5s. Eval poll timeout cần ≥30s/file để absorb worst-case race retry.

### Claude's Discretion (research recommend + planner chốt ở `/gsd-discuss-phase`)

- **LLM provider trong eval (Open Question 5):** OpenAI thật cần API key vs mock — research recommend **mock embedding default (`EVAL_MOCK_EMBED=1`)** cho CI gate + **tuỳ chọn thật via env `EVAL_USE_REAL_LLM=1`** cho developer đo VN quality. Mock embedding làm "vô nghĩa" số liệu retrieval thực (random vector không reflect semantic) → CI gate ≥75% PHẢI chạy với key thật ít nhất 1 lần trước khi declare PASS. Mock chỉ dùng cho regression smoke (KHÔNG cho gate verdict).
- **Pytest vs standalone (Open Question 8):** Recommend **hybrid** — pytest cho smoke `tests/integration/test_eval_pipeline.py` (1 file, 1 query, <60s) + standalone `eval/run_eval.py` cho full gate (12 query × 10 file × poll completion). Standalone đỡ phụ thuộc testcontainers (cần stack `make up` chạy sẵn).
- **EVAL.md generator template (Open Question 7):** Recommend **f-string + tabulate cho table phần Metrics + Per-Query Diff** — đơn giản, không cần Jinja2 dependency. Pattern M1 dùng `tabulate` (commit `0af44f0:Hub_All/.planning/milestones/v1.0-docling-rag/05-eval-compare-quality-gate/05-CONTEXT.md` mục I) — port lại tabulate >=0.9 vào `eval/pyproject.toml`.
- **Eval hub strategy (Open Question 3):** Recommend **dùng `eval_hub` riêng tách biệt** với hub dev/prod (M1 pattern) — code `eval_hub`, subdomain `eval.medinet.vn`, isolation tuyệt đối. Cleanup script `eval/scripts/cleanup.py` xoá chunks+documents+publish redis cache invalidate TRƯỚC mỗi run. `make eval-clean` target.
- **expected_doc_id field (Open Question 2):** Recommend **giữ filename string** (không phải UUID) — M1 schema, port nguyên. M2 match field: `SearchResultItem.title = filename` (xem `search_service.py:_row_to_item` line 142 `title=row["filename"]`). KHÔNG dùng `.category` (Go cũ; M2 luôn `None` per D-10).
- **Cross-AI dependency Ask (Open Question 9):** Recommend **CHỈ measure search retrieval Phase 9** — REQUIREMENTS line 9 nói rõ `/api/search`. Ask quality measurement (anti-injection LLM thật, BLEU/ROUGE answer) defer v4.0 (M2 chỉ đo retrieval — Phase 7 SC ghi nhận "anti-injection LLM hành vi thật defer Phase 9" nhưng REQUIREMENTS chỉ có 4 REQ-ID EVAL-* cho retrieval).

### Deferred Ideas (OUT OF SCOPE Phase 9)

- **Answer quality (BLEU/ROUGE):** defer v4.0 — Phase 9 chỉ đo retrieval (`/api/search`), không đo `/api/ask` answer.
- **LLM-as-judge auto-grading:** defer v4.0 — 12 query vàng có expected_doc_id đủ ground truth.
- **Statistical significance test:** defer v4.0 — 12 query quá ít cho t-test, chỉ trình bày diff thô.
- **A/B với multiple embedding model:** defer v4.1 — M2 PIN 1536 OpenAI/Gemini, không A/B với BGE-M3 / sentence-transformers.
- **Visual dashboard eval (Streamlit/web UI):** defer v4.0.
- **Auto regression CI (GitHub Actions chạy mỗi PR):** defer Phase 10 HARD-03 (CI gate test PASS).
- **Heading recall metric:** M1 defer Phase 5 (compare native vs docling) — M2 KHÔNG có baseline compare → defer hẳn v4.1 (cocoindex chunker khác Go ALL CAPS regex, không có ground truth).
- **Larger eval dataset (100+ queries từ prod logs):** defer khi có data thật từ Medinet (post-M2 deploy).
- **Cross-hub search eval:** defer — REQUIREMENTS line 9 chỉ nói `/api/search` (single-hub WITH `hub_id` filter). Cross-hub eval defer v4.0.
- **Eval với RAG cache hit:** cleanup PHẢI flush Redis cache trước mỗi run; KHÔNG measure cache hit rate (skew kết quả retrieval thật).
- **Eval `/api/ask` end-to-end với citation correctness:** defer v4.0 (anti-injection prompt thật, LLM key thật, response parse `[N]`).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| EVAL-01 | `Hub_All/eval/dataset/sources/` 10 file VN medical + `eval/queries.jsonl` 12 query (port semantic từ M1 archive). Schema mỗi dòng: `{id, query, expected_doc_id, expected_section, hub_id, notes}`. | **Restore từ git history** commit `0af44f0` — toàn bộ 8 sources + 2 scanned + queries.jsonl + headings.json + DATASET.md đã có. **Patch schema:** thêm field `hub_id` (M2 mới). Code restore: `git show 0af44f0:Hub_All/eval/dataset/queries.jsonl > eval/queries.jsonl` + `git checkout 0af44f0 -- Hub_All/eval/dataset/sources/ Hub_All/eval/dataset/scanned/`. Pattern reproducibility xem `M1 01-CONTEXT.md` section B. |
| EVAL-02 | `eval/run_eval.py` pytest-based — login admin → seed `eval_hub` (DELETE chunks/documents trước) → upload 10 file → wait completion (heartbeat <2min/file) → run 12 queries qua `POST /api/search` WITH `hub_id` filter → emit `eval/results.json` (top-1/3/5 + MRR + latency p50/p95/p99). | Pattern `M1 baseline.py` (588 dòng, commit `0af44f0:Hub_All/eval/baseline.py`) — 90% reusable. 4 thay đổi: (a) endpoint `POST /api/search` body `{query, hub_ids:[X], top_k}` thay GET `?q=...&hub_id=X&top_k=10` (D-02), (b) match field `title=filename` thay `category`, (c) poll 30s+ tolerant race retry (Phase 4 race fix delay 0.1s + 3 attempts × 0.5s/1.0s/1.5s = ~3.6s overhead), (d) thêm percentile lib `numpy` HOẶC `statistics.quantiles(n=100)` (stdlib Python 3.8+, NO new dep). Emit `eval/results.json` schema xem mục "Output Schemas" dưới. |
| EVAL-03 | `eval/EVAL.md` generator — Markdown 7 section (Setup + Metrics + Per-Query Diff + Latency + Conclusion + Recommendations + Defer). Verdict PASS nếu top-3 ≥ 75% absolute; exit 0/1 CI-friendly. | Pattern `M1 05-CONTEXT.md mục F`. Template engine: f-string + `tabulate>=0.9` (thêm vào `eval/pyproject.toml` dev dep). Verdict logic Python: `if top_3 >= 0.75: verdict, exit_code = "PASS", 0 else: verdict, exit_code = "FAIL", 1`. EVAL.md sinh dù FAIL (chứa debug data). |
| EVAL-04 | Makefile `make eval-all`/`eval-clean`/`eval-smoke` + `eval/README.md` workflow. Smoke: upload 1 sample DOCX → search → assert ≥1 chunk return + chunk content match heading. | Makefile root pattern hiện hữu (`Hub_All/Makefile`) — proxy thêm 4 target eval. Smoke `<60s` end-to-end. README pattern M1 `eval/README.md` (commit `0af44f0`) — 40+ dòng, 10 section, troubleshooting LibreOffice (defer M2 — KHÔNG cần OCR/scanned regen), JWT TTL refresh, ChromaDB v2 (defer M2 — pgvector). |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Eval script orchestration | **Standalone Python tool (`eval/`)** | — | Eval không phải feature của API service — đó là build-time/CI tool kiểm tra chất lượng. Tách hẳn khỏi `api/app/` (KHÔNG mount endpoint `/api/eval`). |
| HTTP client gọi API (login, upload, poll, search) | **Eval script (`eval/lib.py`)** | API Service (port 8180) | `httpx.AsyncClient` với JWT auto-refresh — pattern M1 `baseline.py` `APIClient` class. KHÔNG gọi service layer in-process (tránh coupling — eval phải work như external client thật). |
| Cleanup state (xoá chunks + documents + Redis cache + cocoindex memo) | **Eval script (`eval/scripts/cleanup.py`)** | API Service (DELETE endpoints) + Postgres direct (psycopg) | Cleanup trước mỗi run = idempotent reset. Mix: `DELETE /api/documents/:id` cho 10 file (qua API → cocoindex tombstone clean), Postgres direct cho TRUNCATE chunks (defensive nếu API stuck), Redis `FLUSHDB` cho search cache. |
| Embedding mock vs real | **Eval script env switch** (`EVAL_MOCK_EMBED=1`) | API Service env (`OPENAI_API_KEY`) | Mock embedding (`monkeypatch litellm.aembedding`) chỉ hợp lý cho smoke regression (pytest). Gate verdict ≥75% PHẢI dùng key thật (env mọi máy dev cần `OPENAI_API_KEY` hoặc `GEMINI_API_KEY`). |
| Metrics compute (top-K hit rate, MRR, latency percentile) | **Eval script (`eval/metrics.py`)** | — | Pure Python, không phụ thuộc API. `statistics.quantiles(latencies, n=100)` cho p50/p95/p99 (stdlib Python 3.8+ — NO new dep). |
| Markdown report gen | **Eval script (`eval/report.py`)** | — | f-string + `tabulate` >=0.9 (new dep `eval/pyproject.toml` only). Emit `eval/EVAL.md`. |
| Quality gate verdict + exit code | **Eval script `run_eval.py` `__main__`** | CI (Makefile chain `make eval-all`) | `sys.exit(0)` PASS / `sys.exit(1)` FAIL. Makefile `make eval-all: eval-clean eval-run eval-report` chain với `|| exit 1` propagate. |
| Smoke test regression (CI gate KHÔNG vỡ pipeline) | **pytest (`api/tests/integration/test_eval_pipeline.py`)** | testcontainers Postgres+Redis | Pattern Phase 4 `test_ingest_e2e.py`. Smoke 1 file + 1 query, mock embedding, <60s. KHÔNG verdict ≥75% (đó là track standalone). |
| Dataset storage | **Git (`eval/dataset/`)** | — | Restore từ commit `0af44f0` initial. Binary DOCX + PDF commit thẳng vào repo (M1 pattern — reproducibility). Tổng size ~5MB acceptable. |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | >=3.11,<3.13 (rec. 3.12) | Runtime | Match `api/pyproject.toml` line 5 [VERIFIED: file read 2026-05-21] |
| pytest | 8.4.2 | Smoke test framework | Match `api/.venv` installed [VERIFIED: `uv pip show pytest`] |
| pytest-asyncio | 0.26.0 | Async test runner | Match `api/.venv` + `pyproject.toml` dev dep [VERIFIED] |
| httpx | 0.28.1 | HTTP client async | Match `api/.venv` [VERIFIED]; same dep API service dùng — đảm bảo compat |
| tabulate | >=0.9,<1 | Markdown table gen cho EVAL.md | M1 pattern (`05-CONTEXT.md` mục I); industry standard cho ASCII/Markdown tables [CITED: https://pypi.org/project/tabulate/] |
| python-dotenv | >=1.0 | Đọc `eval/.env` config | M1 pattern (`baseline.py` line 35); avoid hardcode credentials |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| psycopg | >=3.1 | Postgres direct query (cleanup script TRUNCATE chunks) | Defensive cleanup khi API endpoint stuck — bypass API layer |
| numpy | (optional) >=1.26 | Percentile compute alternative | `statistics.quantiles(n=100)` stdlib đủ — chỉ thêm numpy nếu eval scale >1K query (KHÔNG cần M2) |
| python-docx | >=1.1 | (defer) DOCX heading extract regen | M1 dùng cho `extract_headings.py` — M2 không cần vì dataset restore từ git có sẵn `headings.json` |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Custom pytest + httpx | **ragas** (RAG eval framework reference-free) [CITED: https://github.com/explodinggradients/ragas] | ragas trade-off: reference-free LLM-as-judge (KHÔNG cần ground truth) — nhưng M2 ĐÃ có 12 query vàng + expected_doc_id; ragas thừa cho retrieval gate đơn giản. ragas thêm dep nặng (langchain stack), KHÔNG cần. Custom pytest đủ cho 12 query × 5 metric. |
| Custom pytest + httpx | **DeepEval** [CITED: https://deepeval.com] | DeepEval = pytest-style RAG eval với metrics catalog phong phú + CI/CD. M2 chỉ cần 5 metric đơn giản — DeepEval over-engineering. Reconsider khi scale lên 100+ query (v4.0). |
| Standalone script | **FutureAGI / Braintrust** | SaaS — phụ thuộc cloud, không phù hợp medical data privacy (Medinet nội bộ). |
| f-string + tabulate | **Jinja2 template engine** | Jinja2 mạnh cho template phức tạp; EVAL.md 7 section đơn giản → f-string sufficient, KHÔNG thêm dep. |
| `statistics.quantiles` | numpy `np.percentile` | numpy nặng (15MB) — stdlib `statistics.quantiles(n=100)` Python 3.8+ đủ cho 12 query latency [VERIFIED: Python 3.12 docs https://docs.python.org/3/library/statistics.html#statistics.quantiles] |
| Hardcode HTTP base URL | pytest-vcr / responses replay | Eval cần stack thật chạy (uvicorn + postgres + redis + cocoindex flow) — replay không cover được race condition + embedding API thật. |

**Installation:**

```bash
# Tạo eval/ skeleton Python ở root Hub_All/ (KHÔNG nằm trong api/)
cd Hub_All
mkdir -p eval/{dataset/{sources,scanned},scripts,tests}
cat > eval/pyproject.toml <<'EOF'
[project]
name = "medinet-eval"
version = "0.1.0"
requires-python = ">=3.11,<3.13"
dependencies = [
    "httpx>=0.28",
    "psycopg[binary]>=3.1",
    "python-dotenv>=1.0",
    "tabulate>=0.9,<1",
]

[project.optional-dependencies]
dev = ["pytest>=8,<9", "pytest-asyncio>=0.24,<1", "ruff>=0.6,<1"]
EOF

# Install
cd eval && uv pip install -e ".[dev]"
```

**Version verification:** Verified 2026-05-21 via `uv pip show` trong `api/.venv`. tabulate hiện CHƯA cài (cần add `eval/pyproject.toml`). [VERIFIED: terminal output 2026-05-21]

## Architecture Patterns

### System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      Phase 9 Eval Pipeline                              │
└─────────────────────────────────────────────────────────────────────────┘

     ┌─────────────────┐
     │  Developer /CI  │
     │  make eval-all  │
     └────────┬────────┘
              │
              ▼
     ┌────────────────────────┐         ┌───────────────────────────────┐
     │  eval/scripts/         │ TRUNCATE│  Postgres pgvector pg16       │
     │  cleanup.py            │────────►│  chunks, documents,           │
     │  (Postgres + Redis)    │ FLUSHDB │  search_cache:* (Redis)       │
     └────────┬───────────────┘         └───────────────────────────────┘
              │ stack clean
              ▼
     ┌─────────────────────────┐
     │  eval/run_eval.py       │
     │  (orchestrator)         │
     └──┬──────────────────────┘
        │
        │ 1. Pre-flight check
        │    (healthz + readyz + eval_hub exist)
        │
        │ 2. APIClient.login(admin) ──────────► POST /api/auth/login
        │                                       (Phase 3 — JWT RS256 15min)
        │
        │ 3. Upload 10 file (sequential)
        │    ┌──────────────────────────────┐
        │    │ FOR each file in dataset/:   │
        │    │   POST /api/documents/upload │──► api service → DocumentService.create
        │    │   (202 + document_id)        │       │
        │    │                              │       ▼
        │    │ POLL GET /api/documents/:id  │   BackgroundTask
        │    │ every 1s (max 30s)           │   trigger_cocoindex_update
        │    │ until status ∈                │   (Phase 4 race fix:
        │    │   {completed, failed,        │    initial 0.1s + 3 retry
        │    │    failed_unsupported}       │    backoff 0.5/1.0/1.5s)
        │    └──────────────────────────────┘       │
        │                                            ▼
        │  Scanned PDF (2 file) → 415 expected     CocoIndex Flow:
        │  → status='failed_unsupported'           extract → chunk VN
        │  (R4 mitigation, NOT a hit)              → embed (LiteLLM 1536d)
        │                                          → INSERT chunks pgvector
        │
        │ 4. Run 12 queries qua POST /api/search
        │    ┌──────────────────────────────┐
        │    │ FOR each q in queries.jsonl: │
        │    │   t0 = perf_counter()        │
        │    │   POST /api/search           │──► SearchService.search()
        │    │   body={query, hub_ids:[H]}  │       │
        │    │                              │       ▼
        │    │   results = res["results"]   │   pgvector HNSW
        │    │   latency = (t1-t0)*1000     │   (ef_search=200,
        │    │   match expected_doc_id      │    iterative_scan=relaxed)
        │    │     vs result.title          │   WITH hub_id filter
        │    │   record rank | None         │
        │    └──────────────────────────────┘
        │
        │ 5. compute metrics
        │    top_1/3/5_hit_rate, mrr, p50/p95/p99 latency
        │
        │ 6. emit eval/results.json
        │
        ▼
     ┌──────────────────────┐
     │  eval/report.py      │
     │  → eval/EVAL.md      │  Markdown 7 section (Setup, Metrics,
     │                      │   Per-Query Diff, Latency, Conclusion,
     │                      │   Recommendations, Defer)
     └──────────────────────┘
              │
              ▼
        verdict = "PASS" if top_3 >= 0.75 else "FAIL"
        sys.exit(0 if PASS else 1)
              │
              ▼
        ┌─────────────────┐
        │  CI: green/red  │
        └─────────────────┘
```

### Component Responsibilities

| File / Module | Responsibility |
|---------------|----------------|
| `Hub_All/eval/pyproject.toml` | PEP 621 + deps (httpx, psycopg, tabulate, python-dotenv) + dev deps (pytest, ruff) |
| `Hub_All/eval/.env.example` | Template env: `BACKEND_URL=http://localhost:8180`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `DB_*`, `EVAL_HUB_CODE=eval`, `EVAL_MOCK_EMBED=0`, `OPENAI_API_KEY=` |
| `Hub_All/eval/README.md` | Workflow 3 bước + troubleshooting + tiền điều kiện + reproducibility |
| `Hub_All/eval/lib.py` | Shared `APIClient` (login, refresh-on-401, upload, poll, search), `preflight_check()`, `get_eval_hub_id()` — extract pattern M1 baseline.py |
| `Hub_All/eval/metrics.py` | `compute_retrieval_metrics(queries, per_query_results)` → top-K + MRR; `compute_latency_percentiles(latencies)` → p50/p95/p99 (statistics.quantiles) |
| `Hub_All/eval/report.py` | `generate_eval_md(results) -> str` template f-string + tabulate; `gate_verdict(top_3) -> tuple[str, int]` (PASS/FAIL + exit code) |
| `Hub_All/eval/run_eval.py` | `__main__` orchestrator: preflight → login → upload all → search all → compute metrics → emit results.json + EVAL.md → sys.exit |
| `Hub_All/eval/scripts/seed_hub.sql` | INSERT hubs (code='eval', subdomain='eval.medinet.vn', is_active=TRUE) — idempotent `ON CONFLICT DO NOTHING` |
| `Hub_All/eval/scripts/cleanup.py` | DELETE chunks WHERE document_id IN (SELECT id FROM documents WHERE hub_id=eval); DELETE documents; Redis FLUSHDB (search cache) |
| `Hub_All/eval/queries.jsonl` | 12 dòng JSON: `{id, query, expected_doc_id, expected_section, hub_id, notes}` — port từ `0af44f0:Hub_All/eval/dataset/queries.jsonl` + thêm `hub_id` |
| `Hub_All/eval/dataset/sources/*.docx` (7 file) + `tri_thuc_chinh_tri.pdf` | Restore từ git `0af44f0:Hub_All/eval/dataset/sources/` |
| `Hub_All/eval/dataset/scanned/*.pdf` (2 file) | Restore từ git `0af44f0:Hub_All/eval/dataset/scanned/` |
| `Hub_All/eval/results.json` | Output artifact (gitignored) — schema xem "Output Schemas" |
| `Hub_All/eval/EVAL.md` | Output artifact (committed cuối Phase) — Markdown report |
| `Hub_All/Makefile` | Thêm 4 target: `eval-install`, `eval-clean`, `eval-run`, `eval-smoke`, `eval-all` (chain) |
| `Hub_All/api/tests/integration/test_eval_pipeline.py` | pytest smoke 1 file + 1 query mock embedding (<60s); KHÔNG verdict gate, chỉ assert pipeline reachable |

### Recommended Project Structure

```
Hub_All/
├── eval/                              # NEW — Phase 9 deliverable
│   ├── pyproject.toml
│   ├── .env.example
│   ├── .gitignore                     # .env, results.json, __pycache__, .venv
│   ├── README.md
│   ├── __init__.py                    # marker package
│   ├── lib.py                         # APIClient + preflight
│   ├── metrics.py                     # top-K + MRR + latency percentile
│   ├── report.py                      # EVAL.md generator + gate verdict
│   ├── run_eval.py                    # __main__ orchestrator
│   ├── dataset/
│   │   ├── DATASET.md                 # Restored từ git history (M1 commit 0af44f0)
│   │   ├── QUERIES_REVIEW.md          # Restored
│   │   ├── headings.json              # Restored (optional — defer compute heading recall)
│   │   ├── sources/                   # Restored 8 file
│   │   └── scanned/                   # Restored 2 file
│   ├── queries.jsonl                  # Port từ M1 + thêm hub_id
│   ├── scripts/
│   │   ├── seed_hub.sql               # NEW
│   │   └── cleanup.py                 # NEW (psycopg + Redis FLUSHDB)
│   ├── results.json                   # GITIGNORE — run output
│   └── EVAL.md                        # COMMIT cuối phase
├── api/                               # existing
│   └── tests/integration/
│       └── test_eval_pipeline.py      # NEW — pytest smoke
└── Makefile                           # UPDATE — thêm 4 target eval
```

### Pattern 1: pre-flight check fail-fast

**What:** Verify backend + DB + eval_hub seed TRƯỚC khi chạy upload — fail loud với hint khắc phục.
**When to use:** Mọi entry point script eval (`run_eval.py`, `cleanup.py`).
**Example:**

```python
# Source: pattern M1 baseline.py git show 0af44f0:Hub_All/eval/baseline.py:60-110
async def preflight_check() -> None:
    """Verify backend + Postgres + hub seed — fail loud nếu thiếu."""
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            r = await client.get(f"{BACKEND_URL}/healthz")
            if r.status_code != 200:
                raise SystemExit(
                    f"Pre-flight FAIL: backend healthz {BACKEND_URL} trả {r.status_code}.\n"
                    f"Khởi động: cd Hub_All && docker compose up -d + (cd api && make dev)"
                )
            r = await client.get(f"{BACKEND_URL}/readyz")
            if r.status_code != 200:
                raise SystemExit(
                    f"Pre-flight FAIL: backend KHÔNG ready (cocoindex flow + DB pool).\n"
                    f"Check uvicorn logs cho 'cocoindex_init_failed_fail_fast' ERROR."
                )
        except httpx.RequestError as e:
            raise SystemExit(f"Pre-flight FAIL: không kết nối backend: {e}") from e

    dsn = f"host={DB_HOST} port={DB_PORT} dbname={DB_NAME} user={DB_USER} password={DB_PASSWORD}"
    with psycopg.connect(dsn, connect_timeout=5) as conn, conn.cursor() as cur:
        cur.execute("SELECT id FROM hubs WHERE code = %s", (EVAL_HUB_CODE,))
        if not cur.fetchone():
            raise SystemExit(
                f"Pre-flight FAIL: hub code='{EVAL_HUB_CODE}' chưa seed.\n"
                f"Chạy: psql -f eval/scripts/seed_hub.sql"
            )
```

### Pattern 2: APIClient JWT auto-refresh

**What:** httpx client tự refresh access token khi gặp 401 (TTL 15min, upload 10 file có thể vượt).
**When to use:** Mọi HTTP request gọi API thuộc eval pipeline.
**Example:**

```python
# Source: pattern M1 baseline.py git show 0af44f0:Hub_All/eval/baseline.py:150-220
# Adapt: Phase 6 D-02 POST /api/search body {query, hub_ids, top_k}
class APIClient:
    def __init__(self, base_url: str, email: str, password: str):
        self.base_url = base_url
        self.email, self.password = email, password
        self.access_token: str | None = None
        self.refresh_token: str | None = None
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(120.0))

    async def login(self) -> None:
        r = await self._client.post(
            f"{self.base_url}/api/auth/login",
            json={"email": self.email, "password": self.password},
        )
        r.raise_for_status()
        data = r.json()["data"]
        self.access_token = data["access_token"]
        self.refresh_token = data["refresh_token"]

    async def _request_with_retry(self, method: str, url: str, **kw):
        kw.setdefault("headers", {})["Authorization"] = f"Bearer {self.access_token}"
        r = await self._client.request(method, url, **kw)
        if r.status_code == 401:
            await self.refresh()  # rotate refresh → re-set headers → retry 1 lần
            kw["headers"]["Authorization"] = f"Bearer {self.access_token}"
            r = await self._client.request(method, url, **kw)
        return r

    async def search(self, query: str, hub_id: str, top_k: int = 10) -> list[dict]:
        # D-02: POST với body, KHÔNG GET ?q=...
        r = await self._request_with_retry(
            "POST",
            f"{self.base_url}/api/search",
            json={"query": query, "hub_ids": [hub_id], "top_k": top_k},
        )
        r.raise_for_status()
        return r.json()["data"]["results"]
```

### Pattern 3: Upload + poll Phase 4 race-tolerant

**What:** Upload file → poll status với timeout 30s+ để absorb cocoindex race retry (initial 0.1s + 3 attempts × 0.5s/1.0s/1.5s backoff).
**When to use:** Mỗi file upload trong `upload_dataset()`.
**Example:**

```python
# Source: adapt từ Phase 4 test_ingest_e2e.py + M1 baseline.py upload_and_wait
# Plan 04-08 race fix: trigger_cocoindex_update delay 0.1s + retry 3x → poll budget ≥30s
async def upload_and_wait(
    api: APIClient,
    file_path: Path,
    hub_id: str,
    timeout_sec: int = 60,  # increased từ M1 30s vì Phase 4 race retry
    poll_sec: float = 1.0,
) -> dict:
    # M2 endpoint: POST /api/documents/upload (multipart)
    with file_path.open("rb") as f:
        files = {"file": (file_path.name, f.read(), "application/octet-stream")}
        r = await api._request_with_retry(
            "POST", f"{api.base_url}/api/documents/upload",
            files=files, data={"hub_id": hub_id},
        )

    # R4 mitigation — scanned PDF expected 415
    if r.status_code == 415:
        body = r.json()
        return {
            "filename": file_path.name,
            "status": "failed_unsupported",
            "error_message": body["error"]["message"],
            "id": None,
            "chunk_count": 0,
        }
    r.raise_for_status()
    doc = r.json()["data"]
    doc_id = doc["id"]

    deadline = time.time() + timeout_sec
    last_status = doc["status"]
    while time.time() < deadline:
        await asyncio.sleep(poll_sec)
        r = await api._request_with_retry(
            "GET", f"{api.base_url}/api/documents/{doc_id}",
        )
        r.raise_for_status()
        s = r.json()["data"]
        last_status = s["status"]
        # Phase 4 status enum: pending → processing → {completed, failed, failed_unsupported}
        if last_status in ("completed", "failed", "failed_unsupported"):
            return {"id": doc_id, "filename": file_path.name, **s}
    return {
        "id": doc_id,
        "filename": file_path.name,
        "status": "timeout",
        "error_message": f"Poll timeout {timeout_sec}s — last status: {last_status}",
        "chunk_count": 0,
    }
```

### Pattern 4: Metrics compute với match field `title=filename` (M2-specific)

**What:** Hit = `result.title.lower() == expected_doc_id.lower()` — KHÔNG dùng `result.category` (Go cũ; M2 D-10 luôn `None`).
**When to use:** `compute_retrieval_metrics()` core logic.
**Example:**

```python
# Source: adapt từ M1 baseline.py compute_retrieval_metrics
# M2 thay đổi: result.title (= filename, search_service.py:_row_to_item line 142)
def compute_retrieval_metrics(queries: list[dict], per_query_results: list[dict]) -> dict:
    n = len(queries)
    hits_at_1 = hits_at_3 = hits_at_5 = 0
    rr_sum = 0.0
    per_query: list[dict] = []

    for q, r in zip(queries, per_query_results, strict=True):
        expected = q["expected_doc_id"].lower()
        results = r["results"]
        rank: int | None = None
        for idx, res in enumerate(results, 1):
            # M2: title = filename (search_service.py:_row_to_item line 142)
            # KHÔNG dùng category (D-10 luôn None M2)
            if (res.get("title") or "").lower() == expected:
                rank = idx
                break

        if rank == 1: hits_at_1 += 1
        if rank and rank <= 3: hits_at_3 += 1
        if rank and rank <= 5: hits_at_5 += 1
        if rank: rr_sum += 1.0 / rank
        per_query.append({
            "id": q["id"], "query": q["query"],
            "expected_doc_id": q["expected_doc_id"],
            "rank": rank,
            "actual_top_5": [
                {"chunk_id": res.get("id"), "title": res.get("title"),
                 "score": res.get("score")} for res in results[:5]
            ],
        })

    return {
        "top_1_hit_rate": hits_at_1 / n if n else 0.0,
        "top_3_hit_rate": hits_at_3 / n if n else 0.0,
        "top_5_hit_rate": hits_at_5 / n if n else 0.0,
        "mrr": rr_sum / n if n else 0.0,
        "per_query": per_query,
    }
```

### Pattern 5: Latency percentile stdlib

**What:** Đo wall-clock latency cho mỗi search call, compute p50/p95/p99 qua `statistics.quantiles(n=100)`.
**When to use:** `run_queries_with_latency()` — wrap mỗi `api.search()` với `time.perf_counter()`.
**Example:**

```python
# Source: Python 3.12 stdlib https://docs.python.org/3/library/statistics.html#statistics.quantiles
# n=100 → percentile, lấy index 49/94/98 cho p50/p95/p99
import statistics
import time

async def run_queries_with_latency(
    api: APIClient, queries: list[dict], hub_id: str, top_k: int = 10
) -> tuple[list[dict], dict]:
    per_q: list[dict] = []
    latencies_ms: list[float] = []
    for q in queries:
        t0 = time.perf_counter()
        results = await api.search(query=q["query"], hub_id=hub_id, top_k=top_k)
        latency_ms = (time.perf_counter() - t0) * 1000
        latencies_ms.append(latency_ms)
        per_q.append({"results": results, "latency_ms": latency_ms})

    # p50/p95/p99 — quantiles(n=100) trả 99 cut points → [49] = p50, [94] = p95, [98] = p99
    qs = statistics.quantiles(latencies_ms, n=100) if len(latencies_ms) > 1 else [latencies_ms[0]] * 99
    return per_q, {
        "p50_ms": qs[49] if len(qs) >= 50 else latencies_ms[0],
        "p95_ms": qs[94] if len(qs) >= 95 else max(latencies_ms),
        "p99_ms": qs[98] if len(qs) >= 99 else max(latencies_ms),
        "min_ms": min(latencies_ms),
        "max_ms": max(latencies_ms),
        "mean_ms": statistics.mean(latencies_ms),
    }
```

### Anti-Patterns to Avoid

- **Import service layer in-process (`from app.services.search_service import SearchService`):** ❌ Eval phải work như external HTTP client. Import in-process bypass middleware (auth, rate-limit, audit) → eval kết quả KHÔNG reflect production behaviour. Dùng `httpx` qua HTTP.
- **Hardcode `OPENAI_API_KEY` trong code:** ❌ Đọc qua `python-dotenv` từ `eval/.env` (gitignored).
- **Mock embedding cho gate verdict:** ❌ Random vector → top-3 hit rate random ~10% (12 query × top-3 / 10 file = baseline noise). Mock CHỈ cho smoke regression; gate verdict ≥75% PHẢI dùng key thật. Document rõ trong `EVAL.md` section Setup: `embedder_used = "mock" | "openai-text-embedding-3-small@1536" | "gemini-embedding-001@1536"`.
- **Cleanup chunks bằng `TRUNCATE chunks` raw:** ❌ Cocoindex flow tracking state riêng (LMDB fingerprint trong `cocoindex` schema). TRUNCATE chunks không clear cocoindex memo → upload lại file giống nhau, cocoindex skip embed → 0 chunk mới. Cleanup ĐÚNG: `DELETE FROM documents WHERE hub_id=eval` (FK CASCADE chunks) + `cocoindex_app.update_blocking()` trigger lại memo recompute.
- **Poll status timeout <30s/file:** ❌ Phase 4 race fix delay 0.1s + 3 attempts × 0.5/1.0/1.5s backoff = ~3.6s overhead + cocoindex update_blocking() time per file (1-10s với mock embed, 30-60s với OpenAI thật cho file 100+ chunks). Timeout 30s/file MIN, recommend 60s/file để absorb worst-case.
- **Đo recall WITHOUT `hub_id` filter:** ❌ R2 mitigation — pgvector HNSW post-filter recall collapse khi filter `hub_id`. Eval PHẢI có `hub_ids=[eval_hub_id]` trong body — recall thật trên production scenario.
- **Quên Redis cache flush:** ❌ Search cache TTL 300s — 2 lần chạy eval trong 5 phút sẽ hit cache → latency p95 unreal <50ms. `cleanup.py` PHẢI `await redis.flushdb()` HOẶC `redis.delete("search:*")` pattern.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTTP client với retry + auth refresh | Raw `urllib.request` + try/except | `httpx.AsyncClient` + custom `_request_with_retry` (M1 pattern) | httpx có timeout config + connection pool + cookie jar; tránh re-invent. Pattern M1 đã test thực tế 588 dòng. |
| Percentile compute | Sort + manual index pickup | `statistics.quantiles(data, n=100)` | Stdlib Python 3.8+. Edge case n=1 và n<99 đã handle. |
| Markdown table | Build string concat từng row | `tabulate(data, headers=..., tablefmt='pipe')` | tabulate handle alignment, cell escape, header style. M1 đã chốt. |
| JWT decode để check expiry | Manual base64 + JSON parse | (KHÔNG cần) — chỉ trap 401 + refresh | KISS — eval không cần check expiry, để API trả 401 rồi refresh. |
| Postgres cleanup | Raw psycopg query strings rải rác | `eval/scripts/cleanup.py` 1 file orchestrate đủ 3 thao tác (DELETE docs, FLUSHDB Redis, optional cocoindex memo clear) | Idempotent + reusable cho smoke test. |
| Markdown report generator | Jinja2 template engine | f-string + tabulate | M2 chỉ 7 section đơn giản, KHÔNG cần Jinja2 control flow. |
| Async parallel upload 10 file | `asyncio.gather(*[upload(f) for f in files])` | **Sequential** (M1 pattern) | Parallel upload overload cocoindex worker (in-process update_blocking đồng bộ) + race window mở rộng (Phase 4 vừa fix). Sequential đảm bảo deterministic + race-free. |
| Mock embedding for tests | Custom embedding service stub | `monkeypatch litellm.aembedding` return random vector dim 1536 (Phase 4 pattern) | Đã test ở `test_ingest_e2e.py:206-220` PASS. Reuse pattern. |
| Cleanup file_store/ orphan files | Manual `os.remove()` loop | DELETE /api/documents/:id (Phase 4 INGEST-07 — best-effort file cleanup trong service) | Phase 4 đã implement; KHÔNG cần ghi đè ở eval. |
| RAG eval metrics framework | Manual top-K + MRR + Recall@K + NDCG | (Decision) Custom `metrics.py` đủ — KHÔNG cần ragas/DeepEval | 12 query × 4 metric quá đơn giản. ragas/DeepEval over-engineering cho M2 scope. Reconsider v4.0 nếu scale 100+ query. [VERIFIED: ragas requires langchain dep] |

**Key insight:** Phase 9 KHÔNG cần thư viện RAG eval phức tạp (ragas/DeepEval/FutureAGI). Custom 4 metric (top-1/3/5, MRR) + 3 latency percentile = ~150 dòng Python. Pattern M1 baseline.py 588 dòng đã prove khả thi. Over-engineering với ragas thêm 50MB+ dep + langchain stack lock-in — không phù hợp M2 minimalist + Medinet on-prem privacy.

## Runtime State Inventory

> Phase 9 là phase NEW (greenfield within M2) — KHÔNG rename/refactor/migration. KHÔNG có runtime state cũ cần migrate. Để completeness vẫn check 5 categories:

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | **None** — eval framework là tool standalone read-only against existing DB (Postgres pgvector + Redis). Không tạo bảng/collection mới. Eval ghi vào `chunks/documents` qua API như user thường, cleanup giữa các run. | None — verified by grep `CREATE TABLE` trong `eval/` (sẽ là empty Phase 9). |
| Live service config | **eval_hub seed** — INSERT 1 row vào bảng `hubs` (code='eval', subdomain='eval.medinet.vn', is_active=TRUE). Idempotent qua `ON CONFLICT (code) DO NOTHING`. Sau Phase 9 hoàn tất, hub này GIỮ LẠI (status có thể flip `inactive`) cho regression rerun. | Seed script `eval/scripts/seed_hub.sql` — chạy 1 lần. Cleanup KHÔNG drop hub (giữ cho rerun). |
| OS-registered state | **None** — không Windows Task Scheduler / systemd / pm2 / cron. Chạy thủ công qua `make eval-*`. Auto regression CI defer Phase 10. | None. |
| Secrets/env vars | **OPENAI_API_KEY** + **GEMINI_API_KEY** + **ADMIN_PASSWORD** đọc từ `eval/.env` (gitignored). Pattern M1 `.env.example` đã có. Phase 9 dev cần tạo `.env` local từ template. **JWT_PRIVATE_KEY_PATH** đã có ở `api/keys/` — eval KHÔNG đụng (chỉ login qua admin password). | None — `.env.example` template provide đầy đủ. Document rõ trong `eval/README.md`. |
| Build artifacts | **`eval/.venv/`** (Python venv riêng cho eval, gitignored), **`eval/results.json`** (run output, gitignored), **`eval/EVAL.md`** (committed cuối phase artifact). | `.gitignore` thêm `eval/.venv/`, `eval/results.json`, `eval/__pycache__/`, `eval/*.egg-info/`. `eval/EVAL.md` COMMIT (artifact ship). |

**Nothing else found:** Verified by grep `eval/` trong tree hiện tại — directory chưa tồn tại (M1 đã xoá Phase 1 teardown). Tạo fresh từ template.

## Common Pitfalls

### Pitfall 1: Phase 4 race condition + cocoindex memo cache làm eval flaky

**What goes wrong:** Upload file → BackgroundTask `trigger_cocoindex_update` chạy SAU response — cocoindex asyncpg pool dùng REPEATABLE READ snapshot tại BEGIN time → có thể TRƯỚC khi SQLAlchemy COMMIT visible → fetch_rows trả 0 rows → 0 chunk → status='failed' false-positive.
**Why it happens:** Pool A (FastAPI SQLAlchemy) và Pool B (cocoindex asyncpg) tách biệt — commit propagation latency non-zero. Phase 4 đã fix bằng initial delay 0.1s + retry 3 attempts với backoff 0.5/1.0/1.5s (Plan 04-08 debug session).
**How to avoid:** Eval poll timeout **≥30s/file** (recommend 60s) — absorb race retry overhead (~3.6s) + cocoindex update_blocking() time per file. KHÔNG dùng timeout 5s như M1 (M1 chạy với cocoindex 1.0.3 pre-race-fix HOẶC Go backend khác cơ chế).
**Warning signs:** Eval run failed_status >0 ngay cả với DOCX hợp lệ. Check log `trigger_cocoindex_update_retry: doc_id=X attempt=N count=0 backoff=Ys` → tăng poll timeout.

### Pitfall 2: Quên Redis cache flush → latency p95 unreal

**What goes wrong:** Lần đầu chạy `make eval-all` latency p95=600ms; lần 2 trong 5 phút latency p95=30ms (hit cache). Verdict latency SLA pass false-positive.
**Why it happens:** Phase 6 `SEARCH-04` cache TTL 300s — key `search:<sha256(query|hub_ids|top_k)>`. 2 lần gọi same query → 2nd lần hit Redis.
**How to avoid:** `cleanup.py` PHẢI `await redis.flushdb()` HOẶC pattern delete `await redis.delete(*await redis.keys("search:*"))` TRƯỚC mỗi `make eval-all` run. Make target `eval-clean` invoke cleanup.py.
**Warning signs:** `results.json.cache_hit_rate > 0` (eval CHECK assert == 0). Latency p95 < 100ms với key OpenAI thật (network latency embed ≥150ms typical).

### Pitfall 3: Mock embedding làm gate verdict vô nghĩa

**What goes wrong:** CI chạy với `EVAL_MOCK_EMBED=1` → `litellm.aembedding` return random vector (seed=42) → top-3 hit rate ~10% (random noise baseline = 3/10 file × 12 query / random) → gate FAIL liên tục dù hệ thống thật tốt.
**Why it happens:** Random vector không có semantic relationship với query → pgvector cosine similarity meaningless.
**How to avoid:** Mock CHỈ dùng cho `tests/integration/test_eval_pipeline.py` smoke (1 file, assert chunk_count > 0, KHÔNG verdict gate). Gate verdict chạy STANDALONE `make eval-all` với key OpenAI thật. Document rõ trong `EVAL.md` Setup section: `embedder_used = "openai-text-embedding-3-small@1536"`.
**Warning signs:** EVAL.md ghi `embedder_used = "mock"` + verdict FAIL — KHÔNG trigger E5, document rõ "mock mode KHÔNG đủ cơ sở declare gate FAIL".

### Pitfall 4: Match field sai (`category` thay vì `title`)

**What goes wrong:** Eval port nguyên M1 logic `result.category.lower() == expected_doc_id.lower()` → M2 `category` luôn `None` (D-10) → 0% hit rate → verdict FAIL 100%.
**Why it happens:** M1 Go backend gán filename vào `result.category` (xem `backend/internal/rag/searcher.go:131` cũ); M2 Python `SearchResultItem.category` luôn `None` (`search_service.py:_row_to_item` line 145).
**How to avoid:** Match field M2: `result.title.lower() == expected_doc_id.lower()` (search_service.py:_row_to_item line 142: `title=row["filename"]`). Document rõ trong `metrics.py` docstring.
**Warning signs:** top-1/3/5 hit rate = 0.0% trên TẤT CẢ query (kể cả query đơn giản q01 expected DMD_T1-01). Debug: print `result.title` và `result.category` trong 1 query đầu.

### Pitfall 5: Scanned PDF 415 treat as upload failure → gate báo sai

**What goes wrong:** 2 scanned PDF (q09, q10) trả 415 `UNSUPPORTED_FORMAT` (Phase 4 R4 mitigation) — eval count vào "upload failed" → metrics báo "8/10 uploads succeeded" (sai semantic).
**Why it happens:** 415 là INTENTIONAL outcome cho scanned PDF (M2 không support OCR — defer v4.0). KHÔNG phải lỗi.
**How to avoid:** Eval phân biệt 3 outcome: `completed`, `failed_unsupported` (expected for scanned), `failed` (unexpected — alert). `results.json` ghi `documents[i].status = "failed_unsupported"` + `documents[i].is_expected_failure = True`. Per-query metrics: q09/q10 expected_doc_id là scanned PDF → rank PHẢI = None (chunks không tồn tại) → đếm vào "no chunks expected" category KHÔNG phải miss.
**Warning signs:** Eval báo "upload success rate 80%" → user nghĩ pipeline broken; thực ra 2 scanned PDF là expected fail. EVAL.md Setup phải document rõ.

### Pitfall 6: VN filename UTF-8 mojibake trong upload

**What goes wrong:** Upload "Khám bệnh đa khoa.docx" qua `httpx` files param không set encoding → filename in document.filename = "KhÃ¡m bá»‡nh..." mojibake → match expected_doc_id fail.
**Why it happens:** Pattern Phase 8 đã test VN filename UTF-8 PASS — frontend `api.ts` dùng `multipart/form-data` đúng UTF-8. Eval phải dùng `httpx` files= param same way.
**How to avoid:** Pass filename string ngay (`files={"file": (file_path.name, ...)}`) — httpx encode UTF-8 đúng. KHÔNG `encode('latin-1')` workaround.
**Warning signs:** result.title hiển thị mojibake trong `eval/results.json`. So với git pretty-print `git show 0af44f0:Hub_All/eval/dataset/queries.jsonl | head -2` để verify UTF-8 source.

### Pitfall 7: cocoindex memo skip làm eval lần 2 trả 0 chunk

**What goes wrong:** Eval run 1 PASS top-3 80%. Run 2 (cleanup chạy đúng) — top-3 0%. Investigate: `chunks` table có dữ liệu (verify ngay khi `_reconcile_document_status` complete) nhưng cocoindex `update_blocking()` skip embed vì content_hash đã memo (xem `cocoindex` schema state).
**Why it happens:** Cocoindex 1.0.3 LMDB fingerprint cache (memo) — same content fingerprint → skip re-embed → embeddings KHÔNG inserted nếu chunks rows đã DELETE.
**How to avoid:** Cleanup phải clear cocoindex memo state HOẶC trigger force re-index. 2 strategy:
  - **A (recommended):** DELETE FROM documents WHERE hub_id=eval → cocoindex tự cleanup memo (theo lineage) qua next update_blocking. Verify bằng `SELECT COUNT(*) FROM cocoindex.lineage_documents`.
  - **B (heavy hammer):** Stop cocoindex → drop `cocoindex` schema → restart cocoindex (re-setup). Defer rare debug case.
**Warning signs:** Lần 2 run top-K = 0 dù file giống nhau. Check `SELECT count(*) FROM chunks WHERE hub_id=eval` ngay sau upload. Nếu = 0 → cocoindex memo issue.

### Pitfall 8: Eval bị block bởi Phase 4 watchdog (5min timeout)

**What goes wrong:** File upload lớn (PDF 3MB scan) + race retry max-out → cocoindex `update_blocking` chạy >5 phút → Phase 4 watchdog flip status='failed' với error 'timeout'.
**Why it happens:** Phase 4 watchdog `Settings.watchdog_timeout_seconds=300` (5 phút) — flip stale processing rows. Mock embedding fast, real embedding chậm (10-30s/file × 50 chunk = 8 phút worst case).
**How to avoid:** Eval run KHÔNG nên trigger watchdog. 2 mitigation:
  - Document `make eval-all` với `EVAL_USE_REAL_LLM=1` cần dataset nhỏ (10 file × 50 chunks = 500 embeddings = 50s typical với OpenAI batch).
  - Tăng `watchdog_timeout_seconds=600` qua env trong `eval/.env` (override `api/.env` runtime) — KHÔNG sửa Phase 4 default.
**Warning signs:** `documents[i].status = 'failed'` + `error_message = 'timeout: no heartbeat for >300s'`. Tăng timeout hoặc dataset nhỏ hơn.

### Pitfall 9: Pgvector HNSW recall vỡ với hub filter nhỏ (R2 mitigation defective)

**What goes wrong:** Eval hub có 10 file × 50 chunk = 500 chunks. Query với `WHERE hub_id=eval_hub_id ORDER BY vector <=> $1 LIMIT 10` → HNSW post-filter scan only 500/500K chunks → vector_cosine quality khác production scenario.
**Why it happens:** HNSW build trên TOÀN BỘ chunks table (R2 mitigation `iterative_scan=relaxed_order` + `max_scan_tuples=20000`). Hub filter 500/500K = 0.1% selectivity → HNSW visit ít node → recall ~95% (vs 99% no filter). M2 fix với `ef_search=200` + `iterative_scan=relaxed_order` (Phase 6 SEARCH-02).
**How to avoid:** Phase 9 chấp nhận measure recall trong scenario thật (eval_hub = 500 chunks isolated, mỗi query match đúng 1 file). KHÔNG inflate hub size để fake recall — eval phải reflect production worst case (small hub). Verify EXPLAIN ANALYZE trong eval_hub thật sự dùng `ix_chunks_vector_hnsw` (Phase 6 SC3 — defer Phase 9 confirm).
**Warning signs:** EXPLAIN trả `Seq Scan` thay `Index Scan using ix_chunks_vector_hnsw` → R1 mitigation broken → ESCALATE E2 STOP discuss Qdrant migration.

### Pitfall 10: M1 dataset binary commit size + git LFS

**What goes wrong:** Restore 8 DOCX (~470KB tổng) + 2 scanned PDF (~8.4MB tổng) + 1 PDF text (~100KB) = ~9MB binary commit vào repo → git history bloat.
**Why it happens:** M1 commit `0af44f0` đã có toàn bộ 10 file ~9MB. Restore = git checkout = commit lại 9MB.
**How to avoid:** Acceptable cho M2 (one-time restore, scanned PDF sẽ KHÔNG được edit lại). Git LFS over-engineering cho 9MB. Khi dataset >50MB → reconsider LFS. Document trong `eval/dataset/DATASET.md` size + restore command.
**Warning signs:** `git clone` chậm hơn. Acceptable trade-off cho reproducibility.

## Code Examples

Verified patterns from official sources và codebase hiện hữu.

### Restore dataset từ git history

```bash
# Source: git history commit 0af44f0 (initial repo) — verified `git show 0af44f0 --stat`
cd Hub_All
mkdir -p eval/dataset/sources eval/dataset/scanned eval/scripts

# Restore 8 sources (7 DOCX + 1 PDF text)
git show 0af44f0:Hub_All/eval/dataset/sources/DMD_T1-01_DinhVi_TrungTam_v1.docx > eval/dataset/sources/DMD_T1-01_DinhVi_TrungTam_v1.docx
git show 0af44f0:Hub_All/eval/dataset/sources/DMD_T1-02_TuDien_ThuongHieu_v1.docx > eval/dataset/sources/DMD_T1-02_TuDien_ThuongHieu_v1.docx
git show 0af44f0:Hub_All/eval/dataset/sources/DMD_T1-03_Script_Library_v1.docx > eval/dataset/sources/DMD_T1-03_Script_Library_v1.docx
git show 0af44f0:Hub_All/eval/dataset/sources/DMD_T1-04_FAQ_ThuongHieu_v1.docx > eval/dataset/sources/DMD_T1-04_FAQ_ThuongHieu_v1.docx
git show 0af44f0:Hub_All/eval/dataset/sources/DMD_T3-02_PhanCong_NhanVat_v1.docx > eval/dataset/sources/DMD_T3-02_PhanCong_NhanVat_v1.docx
git show 0af44f0:Hub_All/eval/dataset/sources/DMD_T5-01_ContentStrategy_12TuyenND_v1.docx > eval/dataset/sources/DMD_T5-01_ContentStrategy_12TuyenND_v1.docx
git show 0af44f0:Hub_All/eval/dataset/sources/DMD_T5-02_Playbook_KenhTruyen_v1.docx > eval/dataset/sources/DMD_T5-02_Playbook_KenhTruyen_v1.docx
git show 0af44f0:Hub_All/eval/dataset/sources/tri_thuc_chinh_tri.pdf > eval/dataset/sources/tri_thuc_chinh_tri.pdf

# Restore 2 scanned PDF
git show 0af44f0:Hub_All/eval/dataset/scanned/DMD_T1-01_scanned.pdf > eval/dataset/scanned/DMD_T1-01_scanned.pdf
git show 0af44f0:Hub_All/eval/dataset/scanned/DMD_T1-04_scanned.pdf > eval/dataset/scanned/DMD_T1-04_scanned.pdf

# Restore meta (queries + headings + DATASET.md + QUERIES_REVIEW.md)
git show 0af44f0:Hub_All/eval/dataset/queries.jsonl > eval/queries.jsonl
git show 0af44f0:Hub_All/eval/dataset/headings.json > eval/dataset/headings.json
git show 0af44f0:Hub_All/eval/dataset/DATASET.md > eval/dataset/DATASET.md
git show 0af44f0:Hub_All/eval/dataset/QUERIES_REVIEW.md > eval/dataset/QUERIES_REVIEW.md

# Verify SHA256 hashes match M1 (optional)
sha256sum eval/dataset/sources/*.docx eval/dataset/sources/*.pdf eval/dataset/scanned/*.pdf
```

### Patch queries.jsonl schema thêm hub_id

```python
# Plan task: port M1 queries.jsonl + thêm hub_id field
# Source: M1 queries.jsonl schema {id, query, expected_doc_id, expected_section, notes}
#         + REQUIREMENTS line 9 mandate hub_id

import json
from pathlib import Path

queries_path = Path("eval/queries.jsonl")
lines = queries_path.read_text(encoding="utf-8").splitlines()

patched = []
for line in lines:
    if not line.strip():
        continue
    q = json.loads(line)
    # Tất cả 12 query đều dùng eval_hub (single-hub eval)
    q["hub_id"] = "eval_hub"  # placeholder — runtime resolve sang UUID qua get_eval_hub_id()
    patched.append(json.dumps(q, ensure_ascii=False))

queries_path.write_text("\n".join(patched) + "\n", encoding="utf-8")
```

### Pre-flight check fail-fast (M2 healthz/readyz)

```python
# Source: M1 baseline.py preflight + Phase 1 CORE-04 healthz/readyz contract
import os
import httpx
import psycopg

async def preflight_check() -> None:
    backend_url = os.getenv("BACKEND_URL", "http://localhost:8180")
    db_dsn = (
        f"host={os.getenv('DB_HOST', 'localhost')} "
        f"port={os.getenv('DB_PORT', '5432')} "
        f"dbname={os.getenv('DB_NAME', 'medinet_central')} "
        f"user={os.getenv('DB_USER', 'medinet')} "
        f"password={os.getenv('DB_PASSWORD', '')}"
    )

    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(f"{backend_url}/healthz")
        if r.status_code != 200:
            raise SystemExit(f"backend KHÔNG up @ {backend_url}/healthz: {r.status_code}")
        r = await client.get(f"{backend_url}/readyz")
        if r.status_code != 200:
            raise SystemExit(
                f"backend KHÔNG ready @ {backend_url}/readyz: {r.status_code}\n"
                f"check 'cocoindex_init_failed_fail_fast' trong uvicorn logs"
            )

    with psycopg.connect(db_dsn, connect_timeout=5) as conn, conn.cursor() as cur:
        cur.execute("SELECT id FROM hubs WHERE code = %s", ("eval",))
        if not cur.fetchone():
            raise SystemExit(
                "hub code='eval' chưa seed. Chạy: psql -f eval/scripts/seed_hub.sql"
            )
```

### Seed hub SQL (idempotent)

```sql
-- Source: M1 pattern adapted cho M2 schema (Phase 5 Plan 05-01 migration 0003)
-- hubs.code + hubs.subdomain UNIQUE NOT NULL; KHÔNG còn chroma_collection (Phase 2)
INSERT INTO hubs (
    id, slug, code, subdomain, name, description, is_active, created_at, updated_at
)
VALUES (
    gen_random_uuid(),
    'eval',
    'eval',
    'eval.medinet.vn',
    'Eval Sandbox (M2 Quality Gate)',
    'Hub dành riêng cho eval framework Phase 9 — gate ≥75% top-3',
    TRUE,
    NOW(),
    NOW()
)
ON CONFLICT (code) DO NOTHING;
```

### Cleanup script (Postgres + Redis)

```python
# Source: M1 cleanup.py pattern + M2 redis + cocoindex memo awareness
import asyncio
import os

import psycopg
import redis.asyncio as redis_async
from dotenv import load_dotenv

load_dotenv(".env")

async def cleanup_eval_hub() -> None:
    db_dsn = (
        f"host={os.getenv('DB_HOST')} port={os.getenv('DB_PORT')} "
        f"dbname={os.getenv('DB_NAME')} user={os.getenv('DB_USER')} "
        f"password={os.getenv('DB_PASSWORD')}"
    )
    eval_code = os.getenv("EVAL_HUB_CODE", "eval")

    # 1. DELETE documents WHERE hub_id=eval (chunks CASCADE qua FK Phase 2)
    with psycopg.connect(db_dsn) as conn, conn.cursor() as cur:
        cur.execute(
            """
            DELETE FROM documents
            WHERE hub_id = (SELECT id FROM hubs WHERE code = %s)
            """,
            (eval_code,),
        )
        conn.commit()
        print(f"deleted {cur.rowcount} documents trong hub '{eval_code}'")

    # 2. Redis FLUSHDB OR delete search:* pattern (giữ keys khác)
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    r = redis_async.from_url(redis_url)
    try:
        keys = await r.keys("search:*")
        if keys:
            await r.delete(*keys)
            print(f"deleted {len(keys)} search cache keys")
    finally:
        await r.aclose()

    # 3. (optional) Force cocoindex update_blocking để clear LMDB memo
    # Defer: chỉ cần nếu Pitfall 7 trigger. Comment-out default.

if __name__ == "__main__":
    asyncio.run(cleanup_eval_hub())
```

### EVAL.md report generator (tabulate)

```python
# Source: tabulate 0.9 docs https://pypi.org/project/tabulate/
# Pattern M1 05-CONTEXT.md mục F (EVAL.md template)
from tabulate import tabulate

def generate_eval_md(results: dict) -> str:
    setup = results["setup"]
    retrieval = results["retrieval"]
    latency = results["latency"]
    documents = results["documents"]

    verdict, exit_code = ("PASS", 0) if retrieval["top_3_hit_rate"] >= 0.75 else ("FAIL", 1)
    reason = (
        f"top-3 đạt {retrieval['top_3_hit_rate']*100:.1f}% — ≥75% threshold"
        if verdict == "PASS"
        else f"top-3 chỉ {retrieval['top_3_hit_rate']*100:.1f}% — dưới 75% threshold"
    )

    # Metrics table
    metrics_rows = [
        ["top-1 hit rate", f"{retrieval['top_1_hit_rate']*100:.1f}%"],
        ["top-3 hit rate", f"{retrieval['top_3_hit_rate']*100:.1f}%", "🎯 GATE"],
        ["top-5 hit rate", f"{retrieval['top_5_hit_rate']*100:.1f}%"],
        ["MRR",            f"{retrieval['mrr']:.3f}"],
    ]
    metrics_table = tabulate(metrics_rows, headers=["Metric", "Value", "Note"], tablefmt="pipe")

    # Per-query diff
    per_q_rows = [
        [pq["id"], pq["expected_doc_id"][:30], pq["rank"] or "MISS",
         pq["actual_top_5"][0]["title"][:30] if pq["actual_top_5"] else "—"]
        for pq in retrieval["per_query"]
    ]
    per_q_table = tabulate(
        per_q_rows, headers=["ID", "Expected", "Rank", "Top-1 Actual"], tablefmt="pipe"
    )

    return f"""# EVAL — M2 Phase 9 Quality Gate

**Ngày chạy:** {setup['run_id']}
**Verdict:** **{verdict}**
**Reason:** {reason}
**Exit code:** {exit_code}

## 1. Setup
- Dataset: 10 file (8 sources + 2 scanned PDF expected fail)
- Queries: 12 truy vấn vàng (port từ M1, semantic VN medical)
- Hub: eval (code='{setup['hub_code']}')
- Embedder: `{setup['embedder_provider']}/{setup['embedder_model']}` dim={setup['embedder_dim']}
- LLM: KHÔNG dùng (eval chỉ đo retrieval `/api/search`)
- Mock embed: `{setup['mock_embedding']}` ({'⚠️ verdict KHÔNG đủ cơ sở declare gate' if setup['mock_embedding'] else '✓ key thật'})

## 2. Retrieval Metrics

{metrics_table}

## 3. Per-Query Diff

{per_q_table}

## 4. Latency

| Percentile | Value (ms) |
|---|---|
| p50 | {latency['p50_ms']:.1f} |
| p95 | {latency['p95_ms']:.1f} |
| p99 | {latency['p99_ms']:.1f} |
| min | {latency['min_ms']:.1f} |
| max | {latency['max_ms']:.1f} |
| mean | {latency['mean_ms']:.1f} |

**Budget:** p95 <800ms single hub (Phase 6 SLA). {'✓ PASS' if latency['p95_ms'] < 800 else '✗ FAIL'}

## 5. Conclusion

{reason}.

{'M2 ship-ready cho retrieval. Tiếp Phase 10 hardening.' if verdict == "PASS" else
 f'**TRIGGER E5** nếu sau iterate 3 vòng vẫn fail <60%. Hiện tại top-3={retrieval["top_3_hit_rate"]*100:.1f}% — '
 + ('STOP M2b, ship M2a, discuss reranker/BM25 v3.0.' if retrieval["top_3_hit_rate"] < 0.60 else
    'CÓ thể iterate chunker/prompt 1 vòng nữa trước khi declare E5.')}

## 6. Recommendations

- (placeholder — fill theo per-query miss analysis)

## 7. Defer

- Answer quality (BLEU/ROUGE `/api/ask`) defer v4.0
- LLM-as-judge auto-grading defer v4.0
- Heading recall metric defer v4.1
- Hybrid retrieval BM25 + reranker (Cohere) defer v4.1
"""
```

### Pytest smoke test (regression CI gate)

```python
# Source: pattern adapt từ test_ingest_e2e.py — 1 file + 1 query, mock embedding
# api/tests/integration/test_eval_pipeline.py

import io
import json
import uuid
from pathlib import Path

import httpx
import pytest
from docx import Document as DocxDocument


@pytest.mark.critical
@pytest.mark.integration
@pytest.mark.asyncio
async def test_eval_pipeline_smoke(
    auth_client: httpx.AsyncClient,
    admin_token: str,
    app_with_auth,
    tmp_path: Path,
    mock_litellm_embedding,  # fixture từ test_ingest_e2e
) -> None:
    """Smoke: upload 1 DOCX → wait completed → search trả ≥1 chunk.

    KHÔNG verdict gate (đó là standalone `make eval-all`). Chỉ assert
    pipeline reachable end-to-end với mock embedding. CI run <30s.
    """
    # 1. Create eval_hub via test helper
    from app.db.session import get_engine
    from sqlalchemy import text
    hid = uuid.uuid4()
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO hubs (id, slug, code, subdomain, name, "
                "is_active, created_at, updated_at) "
                "VALUES (:id, 'eval-smoke', 'eval-smoke', 'eval-smoke.test', "
                "'Eval Smoke', TRUE, NOW(), NOW())"
            ),
            {"id": str(hid)},
        )

    # 2. Tạo DOCX VN sample
    doc = DocxDocument()
    doc.add_paragraph("PHẦN 01 | CÂU TUYÊN BỐ ĐỊNH VỊ CHÍNH THỨC")
    doc.add_paragraph("Đỗ Minh Đường là trung tâm y học cổ truyền hàng đầu Việt Nam.")
    path = tmp_path / "sample.docx"
    doc.save(str(path))

    # 3. Upload + poll (race-tolerant)
    with path.open("rb") as f:
        r = await auth_client.post(
            "/api/documents/upload",
            headers={"Authorization": f"Bearer {admin_token}"},
            files={"file": ("sample.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
            data={"hub_id": str(hid)},
        )
    assert r.status_code == 202
    doc_id = r.json()["data"]["id"]

    # 4. Poll → completed (reuse pattern test_ingest_e2e._reconcile + _wait_until)
    # (omit for brevity — pattern Phase 4 _reconcile_document_status + _wait_until)

    # 5. Search → assert ≥1 chunk
    r = await auth_client.post(
        "/api/search",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"query": "định vị thương hiệu", "hub_ids": [str(hid)], "top_k": 5},
    )
    assert r.status_code == 200
    results = r.json()["data"]["results"]
    assert len(results) > 0, "search trả 0 chunk — pipeline broken"
    # KHÔNG assert chính xác content match (mock embedding random — semantic meaningless)
```

### Makefile target chain

```makefile
# Source: M1 05-CONTEXT mục G + M2 stack pattern (Hub_All/Makefile root)
# Thêm 5 target vào Hub_All/Makefile

eval-install: ## Install eval/ deps (uv pip install -e eval)
	cd eval && uv pip install -e ".[dev]"

eval-clean: ## Xoá chunks/documents eval_hub + flush Redis search cache
	cd eval && uv run python scripts/cleanup.py

eval-smoke: ## Smoke 1 file end-to-end (<60s) — assert ≥1 chunk
	cd eval && uv run python -c "import asyncio; from run_eval import smoke_one_file; asyncio.run(smoke_one_file())"

eval-run: ## Run full eval 12 queries — emit results.json
	cd eval && uv run python run_eval.py

eval-report: ## Sinh EVAL.md từ results.json (KHÔNG re-run)
	cd eval && uv run python -c "import json; from report import generate_eval_md; \
		print(generate_eval_md(json.load(open('results.json'))))" > eval/EVAL.md

eval-all: eval-clean eval-run eval-report ## Full pipeline (clean → run → report)
	@echo "EVAL.md generated. Verdict in EVAL.md line 'Verdict:'"
```

## State of the Art

| Old Approach (M1) | Current Approach (M2) | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Match field `result.category` | Match field `result.title` | Phase 6 D-10 (`SearchResultItem.category=None` luôn ở M2) | Eval port phải đổi field — Pitfall 4 |
| GET `/api/search?q=...&hub_id=X&top_k=10` | POST `/api/search` body `{query, hub_ids, top_k}` | Phase 6 D-02 (D6 frontend contract) | Eval HTTP method + body shape thay đổi |
| Backend Go (port 8180) | FastAPI Python (port 8180) | Phase 1-7 M2 rewrite | API surface giữ envelope `{success, data, error, meta}` — eval shape parse giữ nguyên |
| ChromaDB collection `medinet_eval` | pgvector chunks table với `hub_id` filter | Phase 2 D3 (drop ChromaDB) | Cleanup KHÔNG còn ChromaDB DELETE — chỉ Postgres DELETE + Redis flush |
| LISTEN/NOTIFY trigger native cocoindex | A4 BackgroundTask `trigger_cocoindex_update` (Plan 04-08 race fix) | Phase 4 REVISION 2 | Eval poll timeout ≥30s/file để absorb race retry |
| Heading recall metric (Phase 5 M1) | Defer v4.1 | M2 không có baseline compare (M1 abandoned) | Phase 9 chỉ đo top-K + MRR + latency, KHÔNG heading recall |
| Quality gate: +15pp delta OR ≥75% absolute | **≥75% absolute ONLY** | M2 abandoned M1 baseline | Verdict logic đơn giản hơn |

**Deprecated/outdated:**

- **`embedder_dim` 3072** (M1 OpenAI `text-embedding-3-large@3072`): M2 PIN 1536 (R1 + R7 cross-dim swap). Cross-dim swap REFUSE 400 (Phase 7 ASK-04).
- **scripts `build_scanned.py` + `extract_headings.py`** (M1 Plan 02-04): KHÔNG cần regen (M2 restore từ git history). Defer hẳn khỏi M2 — chỉ dataset restore-once.
- **LibreOffice headless dep** (M1 build_scanned): KHÔNG cần M2.
- **CFG-03 mode swap runtime** (M1 PUT `/api/rag-config extractor_mode=docling`): KHÔNG còn (Phase 7 ASK-04 chỉ swap LLM/embedding provider, KHÔNG extractor mode — D4 gỡ Docling).

## Output Schemas

### `eval/results.json`

```json
{
  "setup": {
    "run_id": "2026-05-21T10:30:00Z",
    "hub_code": "eval",
    "hub_id": "<uuid resolved runtime>",
    "embedder_provider": "openai",
    "embedder_model": "text-embedding-3-small",
    "embedder_dim": 1536,
    "mock_embedding": false,
    "backend_url": "http://localhost:8180",
    "stack_versions": {
      "python": "3.12.7",
      "fastapi": "0.136.1",
      "cocoindex": "1.0.3",
      "litellm": "1.83.14"
    }
  },
  "documents": [
    {
      "doc_id": "<uuid>",
      "filename": "DMD_T1-01_DinhVi_TrungTam_v1.docx",
      "status": "completed",
      "chunk_count": 28,
      "is_expected_failure": false,
      "elapsed_seconds": 8.4
    },
    {
      "doc_id": null,
      "filename": "DMD_T1-01_scanned.pdf",
      "status": "failed_unsupported",
      "chunk_count": 0,
      "is_expected_failure": true,
      "error_message": "PDF scan chưa hỗ trợ trong M2..."
    }
  ],
  "retrieval": {
    "top_1_hit_rate": 0.667,
    "top_3_hit_rate": 0.833,
    "top_5_hit_rate": 0.833,
    "mrr": 0.722,
    "per_query": [
      {
        "id": "q01",
        "query": "...",
        "expected_doc_id": "DMD_T1-01_DinhVi_TrungTam_v1.docx",
        "expected_section": "PHẦN 01 > 1.2 Bốn thành tố cốt lõi",
        "hub_id": "<uuid>",
        "rank": 1,
        "latency_ms": 245.3,
        "actual_top_5": [
          {"chunk_id": "<uuid>", "title": "DMD_T1-01_DinhVi...", "score": 0.87}
        ]
      }
    ]
  },
  "latency": {
    "p50_ms": 280.1,
    "p95_ms": 612.7,
    "p99_ms": 890.4,
    "min_ms": 180.0,
    "max_ms": 920.5,
    "mean_ms": 320.8
  },
  "gate": {
    "verdict": "PASS",
    "reason": "top-3 hit rate 83.3% ≥ 75% threshold",
    "exit_code": 0,
    "trigger_e5": false
  }
}
```

### `eval/queries.jsonl` (1 dòng = 1 query)

```json
{"id":"q01","query":"Câu tuyên bố định vị chính thức của Đỗ Minh Đường gồm bốn thành tố cốt lõi nào?","expected_doc_id":"DMD_T1-01_DinhVi_TrungTam_v1.docx","expected_section":"PHẦN 01  |  CÂU TUYÊN BỐ ĐỊNH VỊ CHÍNH THỨC > ▸  1.2  Bốn thành tố cốt lõi không thể thiếu","hub_id":"eval_hub","notes":"Q definition cụ thể, trỏ tới sub-section 1.2 trong PHẦN 01"}
```

**Note `hub_id`:** Field placeholder string `"eval_hub"` resolve runtime sang UUID qua `get_eval_hub_id(api)` (query API `GET /api/hubs` → match `code='eval'`). KHÔNG hardcode UUID trong queries.jsonl (dev local UUID khác CI UUID).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | top-3 ≥ 75% là khả thi với dim 1536 OpenAI cho VN medical dataset M1 | Standard Stack | **HIGH** — nếu thực tế <60% trigger E5 STOP M2b. Đây là câu hỏi chính Phase 9 trả lời, không thể research lý thuyết. Mitigation: chấp nhận như HYPOTHESIS, đo thực, document FAIL nếu xảy ra. |
| A2 | Match field `result.title = filename` exact case-insensitive đủ chính xác (không cần fuzzy match) | Pattern 4 | LOW — M1 đã prove pattern. Edge case: filename có ký tự đặc biệt VN ("đ", "ư") → `.lower()` xử lý đúng. Nếu sai → switch sang `unicodedata.normalize('NFC', ...)` |
| A3 | Phase 4 race fix (delay 0.1s + 3 retry) đủ cho eval 10 file upload sequential | Common Pitfalls | LOW — Phase 4 E2E test PASS 2026-05-21. Eval upload sequential giảm áp lực race window. Nếu sai → tăng `_TRIGGER_INITIAL_DELAY_SECONDS=0.5` qua env override eval/.env |
| A4 | `OPENAI_API_KEY` thật có sẵn cho dev/CI khi cần verdict ≥75% | Pitfall 3 | MEDIUM — REQUIREMENTS.md ASK-04 mention `OPENAI_API_KEY` placeholder. Dev cần tự cung cấp key thật khi chạy `make eval-all` thật. CI gate chỉ regression smoke (mock OK). |
| A5 | `eval_hub` 500 chunks đủ để HNSW recall measurement reflect production (R2 mitigation) | Pitfall 9 | MEDIUM — Hub nhỏ có thể inflate recall (HNSW visit ít node). Mitigation Phase 6 đã apply `ef_search=200` + `iterative_scan=relaxed_order` → recall thấp nhất ~95% bất kể hub size. Eval báo cáo thật, không inflate. |
| A6 | Cocoindex LMDB memo clear tự động khi DELETE documents qua FK CASCADE | Pitfall 7 | MEDIUM — chưa verify thực nghiệm. Nếu sai → cần script B (drop schema `cocoindex` + re-setup) như fallback. Plan task: empirical verify "upload 2 lần liên tiếp same content có generate chunks ko" — đã có test `test_e2e_content_hash_incremental_dedup` Phase 4 PASS → memo có hiệu lực, DELETE documents → next upload sẽ re-embed (chứng minh memo clear OK). |
| A7 | tabulate >=0.9 stable cho Vietnamese unicode (UTF-8 column align) | EVAL.md generator | LOW — tabulate là pure Python, không phụ thuộc terminal encoding. tablefmt='pipe' (Markdown) escape an toàn. |
| A8 | `statistics.quantiles(n=100)` Python 3.12 stdlib chính xác cho percentile latency | Pattern 5 | LOW — Python 3.8+ stable, verified [CITED: https://docs.python.org/3/library/statistics.html#statistics.quantiles]. Edge case n<99: fallback `max(latencies)`. |
| A9 | Endpoint `POST /api/documents/upload` chấp nhận `data={"hub_id": str(uuid)}` multipart form field (đã verified ở Phase 4 test_ingest_e2e PASS) | Pattern 3 | LOW — Phase 4 E2E test PASS 2026-05-21 với pattern này. |
| A10 | `eval/` directory ở root `Hub_All/` (KHÔNG nằm trong `api/`) — separation concern eval tool vs API service | Project Structure | LOW — M1 pattern. Phase 9 KHÔNG cần share code với `api/`. |

**This table is NOT empty:** A1 và A4 cần user confirm trong `/gsd-discuss-phase`. A1 là core uncertainty của Phase 9 — không thể giải bằng research, chỉ chạy thật mới biết.

## Open Questions

1. **Quality gate ≥75% top-3 đạt được với dim 1536 OpenAI cho VN medical?**
   - What we know: M1 baseline native (`baseline_native.json` commit `f37cd96`) đạt 75% top-3 với dim 3072 + Go chunker + ChromaDB. M2 dùng dim 1536 + cocoindex VN chunker + pgvector — KHÁC HẲN M1.
   - What's unclear: Dim 1536 vs 3072 quality drop có ≥15pp không. Cocoindex VN chunker boundary có tốt hơn Go regex ALL CAPS không.
   - Recommendation: KHÔNG cố đoán trước. Run Phase 9 với key thật → đo → document. Nếu fail <60% trigger E5 → discuss reranker (Cohere rerank-3) hoặc fallback dim 3072 (chấp nhận cross-dim refuse Phase 7).

2. **Có cần stress test với hub lớn (10K+ chunks) để verify HNSW recall scaling không?**
   - What we know: Phase 6 SC5 yêu cầu p95 <800ms ở 10K chunks. Eval default 500 chunks.
   - What's unclear: Eval framework có cần dataset synthetic 10K chunks (clone 10 file × 20 lần) để measure p95 thật?
   - Recommendation: Phase 9 ship với 10 file dataset (500 chunks) — đủ verify gate verdict. 10K stress test defer Phase 10 hardening HARD-02 Prometheus metrics monitoring sample production thật.

3. **`make eval-all` chạy bao lâu với key OpenAI thật?**
   - What we know: 8 file × 50 chunks = 400 embedding × ~150ms = ~60s upload + 12 query × ~300ms = ~4s search. Tổng ~65s + overhead.
   - What's unclear: OpenAI rate limit `text-embedding-3-small` (5000 RPM tier 1 paid) — eval 400 embedding/min OK. Tier free 200 RPM → có thể throttle.
   - Recommendation: Document trong `eval/README.md` "yêu cầu tier paid OpenAI cho `make eval-all` < 2 phút; tier free có thể 5-10 phút".

4. **Cấu trúc cocoindex `cocoindex` schema state có cần check sau cleanup không?**
   - What we know: Cocoindex 1.0.3 LMDB fingerprint trong path `Settings.cocoindex_lmdb_path`. Phase 4 `test_e2e_content_hash_incremental_dedup` PASS chứng minh memo hoạt động và clear OK qua DELETE documents.
   - What's unclear: Edge case cleanup script crash giữa chừng → orphan memo state. Recovery procedure.
   - Recommendation: Defer Phase 10 backup/restore. Phase 9 chỉ document trong README "nếu eval báo 0 chunk dù file mới, thử `docker compose restart python-api` để reload cocoindex".

5. **Ai cập nhật `eval/EVAL.md` (artifact ship) sau mỗi lần chạy?**
   - What we know: `make eval-all` overwrite `eval/EVAL.md`. Git commit cuối Phase 9 ship 1 version.
   - What's unclear: Re-run trong Phase 10 hardening có nên overwrite? Lưu history `EVAL.md.YYYY-MM-DD`?
   - Recommendation: COMMIT `eval/EVAL.md` cuối Phase 9 với verdict cuối. Phase 10 trở đi: KHÔNG overwrite committed — generate `eval/EVAL.md` ra `.gitignored` (dev local) hoặc `eval/EVAL-${date}.md` nếu cần history.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | Eval script runtime | ✓ | 3.12 (in `api/.venv`) | Tạo `eval/.venv` riêng cho separation |
| uv | Package manager (install eval/) | ✓ | (used by `api/Makefile`) | `pip install -e .` thay thế |
| Docker compose | Stack up (postgres + redis + python-api) | ✓ | (used Phase 1-8) | None |
| Postgres pgvector pg16 | Database backend | ✓ (docker compose) | pg16 + pgvector ≥0.8 | None |
| Redis 7 | Search cache + audit queue | ✓ (docker compose) | 7-alpine | None |
| OpenAI API key | Embedding real (gate verdict) | ⚠️ user provide | N/A | Mock embedding (`EVAL_MOCK_EMBED=1`) — chỉ smoke regression |
| Gemini API key | Embedding alternative | ⚠️ user provide (optional) | N/A | OpenAI primary |
| `tabulate` Python lib | EVAL.md table gen | ✗ chưa cài | N/A → install `>=0.9,<1` | Manual string build (over-engineering) |
| `python-docx` | (defer) DOCX heading regen | Có sẵn `api/.venv` | 1.2.0 | Không cần — dataset restore từ git |
| `pypdf` | (defer) PDF heading verify | Có sẵn `api/.venv` | 5.x | Không cần — dataset restore |
| `psycopg` v3 | Cleanup script direct DB | ✗ chưa cài (eval/) | N/A → install `>=3.1` | asyncpg (đã có `api/.venv`) — heavier dep cho script đơn giản |
| `LibreOffice headless` | (defer) Scanned PDF regen | N/A | N/A | Không cần — restore từ git |

**Missing dependencies with no fallback:** None blocking.

**Missing dependencies with fallback:**
- `OPENAI_API_KEY`: Plan PHẢI document trong `eval/README.md` mục tiền điều kiện. Dev không có key → chạy `EVAL_MOCK_EMBED=1 make eval-smoke` regression OK; gate verdict skip.
- `tabulate` + `psycopg`: install qua `cd eval && uv pip install -e .` (Plan task 1).

## Validation Architecture

> `workflow.nyquist_validation: true` ở `.planning/config.json` — section bắt buộc.

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.4.2 + pytest-asyncio 0.26.0 |
| Config file | `Hub_All/api/pyproject.toml` `[tool.pytest.ini_options]` (existing) + `Hub_All/eval/pyproject.toml` (NEW) |
| Quick run command (smoke) | `cd Hub_All/api && uv run pytest tests/integration/test_eval_pipeline.py -v -x` |
| Full suite command (gate verdict) | `cd Hub_All && make eval-all` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| EVAL-01 | 10 file dataset + queries.jsonl restored từ git có schema đúng (12 dòng JSON valid + hub_id field) | unit | `cd Hub_All/eval && uv run python -c "import json; [json.loads(l) for l in open('queries.jsonl')]"` | ❌ Wave 0 — file chưa restore |
| EVAL-01 | 12 query mỗi dòng có 6 field (id, query, expected_doc_id, expected_section, hub_id, notes) | unit | `cd Hub_All/eval && uv run python -m pytest tests/test_queries_schema.py -v` | ❌ Wave 0 |
| EVAL-02 | `run_eval.py` orchestrator chạy end-to-end mock embed trong testcontainers | integration | `cd Hub_All/api && uv run pytest tests/integration/test_eval_pipeline.py::test_eval_pipeline_smoke -v` | ❌ Wave 0 |
| EVAL-02 | `metrics.compute_retrieval_metrics()` đúng top-1/3/5 + MRR với fixture data | unit | `cd Hub_All/eval && uv run pytest tests/test_metrics.py -v` | ❌ Wave 0 |
| EVAL-02 | `latency` percentile compute đúng với fixture latencies | unit | `cd Hub_All/eval && uv run pytest tests/test_metrics.py::test_latency_percentile -v` | ❌ Wave 0 |
| EVAL-03 | `report.generate_eval_md()` emit 7 section + verdict PASS/FAIL đúng theo top_3 | unit | `cd Hub_All/eval && uv run pytest tests/test_report.py -v` | ❌ Wave 0 |
| EVAL-03 | `gate_verdict()` exit code 0 (top_3=0.75) / 1 (top_3=0.749) | unit | `cd Hub_All/eval && uv run pytest tests/test_report.py::test_gate_verdict_boundary -v` | ❌ Wave 0 |
| EVAL-04 | `make eval-smoke` chạy <60s end-to-end + assert ≥1 chunk | smoke (manual) | `cd Hub_All && make eval-smoke` (stack up trước) | ❌ Wave 0 — Makefile chưa update |
| EVAL-04 | `make eval-all` chain cleanup→run→report → emit results.json + EVAL.md | manual-only (cần OpenAI key + ≥2min run) | `cd Hub_All && OPENAI_API_KEY=... make eval-all` | manual-only — gate verdict track |
| (Gate verdict) | top-3 ≥ 75% trên dataset thật với key OpenAI | manual-only | `make eval-all && cat eval/EVAL.md \| grep "Verdict:"` | manual-only |

### Sampling Rate

- **Per task commit:** `cd Hub_All/eval && uv run pytest -v -x` (unit test metrics + report + queries schema — <10s)
- **Per wave merge:** `cd Hub_All/api && uv run pytest tests/integration/test_eval_pipeline.py -v` (smoke testcontainers — <60s)
- **Phase gate:** `cd Hub_All && make eval-all` với OpenAI key thật → verdict ≥75% PASS → `git add eval/EVAL.md && git commit` ship

### Wave 0 Gaps

- [ ] `Hub_All/eval/pyproject.toml` — PEP 621 + deps (httpx, psycopg, tabulate, python-dotenv)
- [ ] `Hub_All/eval/tests/__init__.py`
- [ ] `Hub_All/eval/tests/test_queries_schema.py` — verify 12 queries valid JSON + 6 field per row
- [ ] `Hub_All/eval/tests/test_metrics.py` — fixture data → assert top-K + MRR + percentile
- [ ] `Hub_All/eval/tests/test_report.py` — fixture results → assert EVAL.md 7 section + gate verdict boundary
- [ ] `Hub_All/api/tests/integration/test_eval_pipeline.py` — smoke 1 file mock embed (reuse fixtures `app_with_auth`, `mock_litellm_embedding`)
- [ ] `Hub_All/eval/README.md` — workflow + tiền điều kiện + troubleshooting (M1 pattern adapt)
- [ ] `Hub_All/Makefile` — thêm 5 target `eval-install`, `eval-clean`, `eval-smoke`, `eval-run`, `eval-report`, `eval-all`
- [ ] Framework install: `cd Hub_All/eval && uv pip install -e ".[dev]"` (auto qua Makefile `eval-install`)

## Security Domain

> `security_enforcement` không set explicit `false` → enable.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | Eval login admin qua existing Phase 3 JWT RS256 + Argon2 (KHÔNG hardcode token). `eval/.env` chứa `ADMIN_PASSWORD` (dev), production KHÔNG có admin user this way — eval CHỈ chạy dev/CI. |
| V3 Session Management | no | Eval tool short-lived process — không cần session. |
| V4 Access Control | yes | Eval dùng admin role login → có quyền upload/delete docs. RBAC enforce ở API service (Phase 3 require_role). Hub isolation enforce qua repo layer (Phase 5 HUB-02) — eval chỉ touch `eval_hub`. |
| V5 Input Validation | yes | Queries.jsonl mỗi dòng PHẢI parse JSON valid + 6 field present. `test_queries_schema.py` enforce. |
| V6 Cryptography | no | Eval KHÔNG mã hoá data. Mọi crypto (JWT, AES-GCM API keys, Argon2) đã ở API service. |
| V8 Sensitive Data | yes | `eval/.env` gitignored — KHÔNG commit `OPENAI_API_KEY`, `ADMIN_PASSWORD`. `eval/.env.example` template KHÔNG có giá trị thật. |
| V12 Files & Resources | yes | Eval upload binary file via multipart. Phase 4 service `file_extract.ALLOWED_EXTENSIONS` enforce whitelist `.docx/.txt/.md/.pdf` → eval scanned PDF tự nhiên reject (415) — KHÔNG bypass. |
| V14 Configuration | yes | `eval/.env.example` template chuẩn; `eval/.gitignore` block `.env`, `.venv`, `results.json`, `__pycache__`. |

### Known Threat Patterns for Python eval stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Hardcoded credentials trong eval script | Information Disclosure | python-dotenv load từ `.env` (gitignored); CI inject env vars qua secrets manager |
| Eval ghi `results.json` chứa user query + chunk content snippet (medical data) → leak | Information Disclosure | `eval/.gitignore` block `results.json` — chỉ EVAL.md commit (aggregate metrics, KHÔNG raw content) |
| Privilege escalation: eval admin login → mutate prod data | Elevation of Privilege | Eval CHỈ chạy với `eval_hub` (code='eval'); cleanup script verify hub code TRƯỚC delete. Production eval cấm (document trong README). |
| Eval bypass rate limit (slowapi 100/min) khi upload 10 file + 12 query | Denial of Service | Sequential upload + search → ~22 request total. Rate limit 100/min cover thoải mái. Nếu rate limit hit → eval poll backoff. |
| Eval phơi key OpenAI qua log | Information Disclosure | Logger format MASK key: `OPENAI_API_KEY=sk-***` — KHÔNG log full key. `_TRIGGER_BACKOFF_BASE_SECONDS` log không leak. |
| JWT replay attack từ eval token sang client khác | Spoofing | Phase 3 JWT short TTL 15 phút + refresh rotation (Redis SETNX). Eval tự refresh không tái sử dụng token cross-process. |

## Sources

### Primary (HIGH confidence)

- **Codebase hiện hữu** Phase 1-8.2 implementation:
  - `Hub_All/api/app/routers/search.py` — POST /api/search shape (D-02) [VERIFIED 2026-05-21 file read]
  - `Hub_All/api/app/services/search_service.py` — `_row_to_item` line 142 `title=row["filename"]` [VERIFIED]
  - `Hub_All/api/app/services/documents_service.py` — `trigger_cocoindex_update` race fix Plan 04-08 [VERIFIED]
  - `Hub_All/api/tests/integration/test_ingest_e2e.py` — pattern fixture session-scoped cocoindex + mock_litellm_embedding [VERIFIED]
  - `Hub_All/api/app/schemas/search.py` — SearchRequest body `{query, hub_ids, top_k}` [VERIFIED]
  - `Hub_All/api/pyproject.toml` — stack versions pin [VERIFIED 2026-05-21]
- **M1 archive (git history commit 0af44f0):**
  - `Hub_All/eval/baseline.py` 588 dòng — APIClient, upload+poll, compute_retrieval_metrics, snapshot pattern [VERIFIED `git show 0af44f0:Hub_All/eval/baseline.py`]
  - `Hub_All/eval/dataset/queries.jsonl` — 12 query VN medical [VERIFIED `git show 0af44f0:Hub_All/eval/dataset/queries.jsonl`]
  - `Hub_All/eval/dataset/sources/*.docx` + `scanned/*.pdf` — 10 file dataset [VERIFIED `git show 0af44f0 --stat`]
  - `Hub_All/eval/dataset/DATASET.md` + `QUERIES_REVIEW.md` + `headings.json` [VERIFIED]
- **M1 milestones planning:**
  - `.planning/milestones/v1.0-docling-rag/01-eval-dataset-baseline-native/01-CONTEXT.md` — decision rationale (filename match, eval_hub strategy, Python script lang) [VERIFIED file read]
  - `.planning/milestones/v1.0-docling-rag/05-eval-compare-quality-gate/05-CONTEXT.md` — quality gate logic + EVAL.md 7 section template [VERIFIED]
- **M2 planning docs:**
  - `Hub_All/.planning/PROJECT.md` line 125-137 — EXIT criteria E5 [VERIFIED]
  - `Hub_All/.planning/REQUIREMENTS.md` line 79-83 — EVAL-01..04 spec [VERIFIED]
  - `Hub_All/.planning/ROADMAP.md` line 413-433 — Phase 9 SC + risks [VERIFIED]
  - `Hub_All/CLAUDE.md` — stack constraint + naming conventions [VERIFIED]

### Secondary (MEDIUM confidence)

- **Python statistics quantiles** [CITED: https://docs.python.org/3/library/statistics.html#statistics.quantiles] — `n=100` percentile computation, verified Python 3.12 stdlib stable
- **tabulate >=0.9** [CITED: https://pypi.org/project/tabulate/] — Markdown table generation, pure Python no deps
- **PostgreSQL pgvector HNSW** [CITED: https://github.com/pgvector/pgvector] — `iterative_scan=relaxed_order` + `ef_search` tuning verified via Phase 6 implementation

### Tertiary (LOW confidence)

- **Industry RAG eval benchmarks 2026** [VERIFIED WebSearch 2026-05-21]:
  - "Precision@5 ≥0.7 narrow-domain KB" benchmark — single source claim, not authoritative for medical VN domain
  - "Recall@20 ≥0.8 broad corpus" — irrelevant cho M2 (top-K=10, not 20)
  - Sources: [blog.premai.io/rag-evaluation-metrics-frameworks-testing-2026](https://blog.premai.io/rag-evaluation-metrics-frameworks-testing-2026/), [labelyourdata.com/articles/llm-fine-tuning/rag-evaluation](https://labelyourdata.com/articles/llm-fine-tuning/rag-evaluation)
- **ragas / DeepEval** [CITED: https://github.com/explodinggradients/ragas, https://deepeval.com]: alternative frameworks evaluated; M2 chọn custom pytest sau cân nhắc (dep weight + over-engineering cho 12 query)

## Metadata

**Confidence breakdown:**

- **Dataset restore (EVAL-01):** HIGH — Verified git commit `0af44f0` chứa đủ 10 file + queries + meta. Restore command đơn giản, deterministic.
- **Standard stack:** HIGH — Toàn bộ versions pin verified runtime trong `api/.venv` 2026-05-21. Pattern M1 baseline.py prove khả thi 588 dòng.
- **Architecture (run_eval.py orchestrator):** HIGH — Pattern M1 + Phase 4 E2E test PASS làm reference. 3 thay đổi nhỏ (POST body, title field, race timeout) đã document rõ.
- **Pitfalls:** HIGH — 10 pitfall đã có root cause + mitigation từ Phase 4-7 implementation actual.
- **Quality gate verdict (≥75% top-3):** **LOW confidence on outcome** (HIGH confidence on framework correctness). Verdict thực tế là EMPIRICAL — không thể research. Document A1 trong Assumptions Log.
- **Security domain:** HIGH — ASVS chỉ V2/V4/V5/V8/V12/V14 apply, all mitigations standard và đã apply ở phase trước.

**Research date:** 2026-05-21
**Valid until:** 2026-06-21 (1 month — stack ổn định Phase 1-8.2 hoàn tất, không có dep upgrade dự kiến)

---

*Phase 9 RESEARCH viết bởi gsd-phase-researcher. Spawned by `/gsd-research-phase 9` (standalone). Consumed by `/gsd-discuss-phase 9` + `/gsd-plan-phase 9`.*
