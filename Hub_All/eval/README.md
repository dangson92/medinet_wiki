# Eval Framework — Medinet Wiki M2 RAG (Phase 9)

**Quality gate ≥ 75% top-3** trên 10 file VN medical + 12 query vàng — chứng nhận M2 ship-ready.

> Verdict FAIL < 60% → trigger E5 STOP M2b (PROJECT.md EXIT criteria).
>
> Verdict FAIL 60-75% → iterate chunker/prompt 3 vòng max trước khi STOP.

---

## 1. Tiền điều kiện

### Bắt buộc

- Python `>= 3.11, < 3.13` (khuyến nghị 3.12) — match `api/`.
- Docker stack đang chạy ở thư mục `Hub_All/`: `docker compose up -d`.
- 3 service healthy: `pgvector/pgvector:pg16` + `redis:7` + `python-api` (port host 8180 → container 8080).
- Admin account đăng nhập được. Mặc định seed: `admin@medinet.vn / Admin@123` — chỉnh trong `.env`.

### Cho gate verdict thật (Wave 4 — `make eval-all`)

- **Tài khoản OpenAI tier paid + API key.** Chunker + embedder M2 dùng `text-embedding-3-large` PIN dim 1536 (R1 mitigation pgvector 2000-dim index limit).
  - Ước tính chi phí: ~$0.02 cho 10 file × ~25 chunk × 1536 dim ≈ ~$0.20 mỗi lần `make eval-all` (acceptable cho gate verdict).
  - Set bash: `export OPENAI_API_KEY=sk-...`
  - Set PowerShell: `$env:OPENAI_API_KEY='sk-...'`
- (Tuỳ chọn) Gemini key — đổi provider qua `PUT /api/rag-config` nếu muốn A/B.

### Cho smoke regression (CI / dev quick check)

- `--mock-embed` mode KHÔNG cần API key, chạy < 60s.
- **Lưu ý:** mock embedding sinh vector ngẫu nhiên → metric retrieval KHÔNG đại diện chất lượng thật → KHÔNG dùng cho gate verdict (chỉ verify pipeline không vỡ regression).

---

## 2. Cài đặt

```bash
cd Hub_All/eval
python -m venv .venv
# bash / zsh / git bash:
source .venv/bin/activate
# Windows PowerShell:
.venv\Scripts\Activate.ps1

pip install -e ".[dev]"
cp .env.example .env
# Sửa .env: OPENAI_API_KEY (gate), ADMIN_PASSWORD, DB_*
```

Cài qua Makefile root:

```bash
cd Hub_All
make eval-install
```

---

## 3. Workflow 5 bước

### Bước 1 — Seed hub eval (chạy 1 lần duy nhất)

```bash
psql -h $DB_HOST -U $DB_USER -d $DB_NAME -f Hub_All/eval/scripts/seed_hub.sql
# hoặc qua Makefile:
make eval-seed
```

Idempotent `ON CONFLICT (code) DO NOTHING` — chạy 2 lần không gây lỗi.

### Bước 2 — Smoke regression offline (mock embedding, < 60s)

```bash
make eval-smoke
# hoặc: cd Hub_All/eval && python -m eval.run_eval --mock-embed --skip-cleanup
```

CI gate (Phase 10 HARD-03) sẽ chạy smoke trên mỗi PR. KHÔNG dùng cho gate verdict thật.

### Bước 3 — Gate verdict thật (Wave 4)

```bash
# Tiền điều kiện: OPENAI_API_KEY thật + stack Docker chạy.
make eval-all
# hoặc: cd Hub_All/eval && python -m eval.run_eval
```

Pipeline chạy 8 step: preflight → resolve hub_id → cleanup → login admin → upload 10 file → settle 2s cocoindex → run 12 query → write `results.json` + `EVAL.md` → exit code.

Output:
- `eval/results.json` (gitignored — raw schema run_metadata + upload_summary + retrieval_metrics + latency).
- `eval/EVAL.md` (commit cuối Phase 9 — Markdown 7 section).
- Exit code: `0` PASS (top-3 ≥ 75%) hoặc `1` FAIL.

### Bước 4 — Re-generate EVAL.md từ results.json (không re-run pipeline)

```bash
make eval-report
# hoặc: python -m eval.report eval/results.json eval/EVAL.md
```

Hữu ích khi sửa template `report.py` mà không muốn chạy lại 10 file upload + 12 query.

### Bước 5 — Lưu lịch sử run + iterate

EVAL.md commit 1 version cuối Phase 9. Mỗi iteration sau (Phase 10+ tuning) sinh `EVAL-${date}.md` gitignored làm baseline so sánh:

```bash
cp eval/EVAL.md eval/EVAL-$(date +%Y-%m-%d).md
# Sửa chunker/prompt → make eval-all → so diff
```

---

## 4. Cấu trúc thư mục

```
Hub_All/eval/
├── pyproject.toml
├── .env.example
├── .env                # gitignored
├── .gitignore
├── README.md           # bạn đang đọc
├── __init__.py
├── lib.py              # APIClient + preflight + upload+poll (Plan 09-02)
├── metrics.py          # top-K + MRR + latency percentile (Plan 09-02)
├── report.py           # EVAL.md generator + gate verdict (Plan 09-03)
├── run_eval.py         # Orchestrator end-to-end 8 step (Plan 09-04)
├── queries.jsonl       # 12 query vàng VN medical (port từ M1 + hub_id)
├── dataset/
│   ├── DATASET.md
│   ├── QUERIES_REVIEW.md
│   ├── headings.json
│   ├── sources/        # 8 file (7 DOCX DMD + tri_thuc_chinh_tri.pdf)
│   └── scanned/        # 2 scanned PDF (R4 expected 415 failed_unsupported)
├── scripts/
│   ├── seed_hub.sql    # Idempotent INSERT eval_hub (Plan 09-01)
│   └── cleanup.py      # Mixed reset (API + Postgres + Redis) — Plan 09-04
├── tests/
│   ├── __init__.py
│   ├── test_metrics.py # 10 unit test (4 critical)
│   └── test_report.py  # 17 unit test (3 critical)
├── results.json        # gitignored — run output
└── EVAL.md             # commit cuối Phase 9 — Markdown report
```

---

## 5. Troubleshooting

### `Pre-flight FAIL: backend healthz trả 5xx`

- Stack chưa khởi động: `cd Hub_All && docker compose up -d`.
- Check log `python-api`: `docker compose logs python-api | tail -50`.
- Tìm log `cocoindex_init_failed_fail_fast` → fix cocoindex setup TRƯỚC.
- Verify port: `curl http://localhost:8180/healthz` phải trả 200.

### `Pre-flight FAIL: hub code='eval' chưa seed`

- Chạy `make eval-seed` hoặc `psql ... -f Hub_All/eval/scripts/seed_hub.sql`.
- Verify: `psql ... -c "SELECT id FROM hubs WHERE code='eval';"`.

### Poll timeout 60s mỗi file

- Phase 4 race fix `trigger_cocoindex_update` delay 0.1s + 3 retry × 0.5/1.0/1.5s backoff → worst-case ~3.6s overhead trên top extract/chunk/embed thật.
- File DOCX lớn (>10MB hoặc bảng phức tạp VN) có thể cần `EVAL_UPLOAD_TIMEOUT_SEC=120` trong `.env`.

### Scanned PDF trả 415 — KHÔNG phải lỗi

- R4 mitigation: 2 file `dataset/scanned/*.pdf` expected 415 `failed_unsupported`.
- Đếm vào `upload_summary.failed_unsupported`, KHÔNG vào `failed`.
- Defer OCR Vietnamese v4.0 (D4 PROJECT.md — Docling gỡ ở M2).

### JWT 15 phút hết hạn giữa upload 10 file

- `APIClient` auto-refresh on 401 (Plan 09-02 Task 1).
- Refresh token hết hạn (7 ngày) → fallback re-login tự động (admin credential có sẵn trong env).

### `EVAL.md` verdict FAIL < 60%

- TRIGGER E5 — STOP M2b (PROJECT.md EXIT criteria).
- Ship M2a standalone (Phase 1-4 đã PASS EXIT GATE 2026-05-21).
- Discuss với user các option:
  - Hybrid BM25 + dense vector (recall boost VN medical jargon).
  - Reranker Cohere rerank-3 hoặc local cross-encoder.
  - Embedding dim 3072 (text-embedding-3-large full).
  - Semantic chunker mới + sentence-window retrieval.
- Xem section 6 `Recommendations` trong EVAL.md cụ thể.

### `EVAL.md` verdict FAIL 60-75% (borderline)

- Iterate chunker/prompt 3 vòng max trước khi trigger E5:
  - Vòng 1: tune `RecursiveSplitter` regex VN heading (Mục/Chương boundary).
  - Vòng 2: prompt expansion (query rewrite cho VN medical jargon).
  - Vòng 3: tăng `--top-k 15` (post-filter sau retrieval).
- Mỗi vòng `make eval-all` + ghi `EVAL-${date}.md` (gitignored).

### `OPENAI_API_KEY chưa set` (real LLM gate)

- Bash: `export OPENAI_API_KEY=sk-...`.
- PowerShell: `$env:OPENAI_API_KEY='sk-...'`.
- HOẶC chạy smoke mock: `python -m eval.run_eval --mock-embed`.

### Cocoindex memo cache hit incorrect (defer Plan 10)

- Edge case khi đổi prompt KHÔNG re-embed: defer Phase 10 (RESEARCH Open Q5).
- Workaround: `make eval-clean` trước `make eval-all` để force re-embed.

### Windows PowerShell console cp1252 không render `≥` `≤` `✅` `❌`

- Set encoding trước: `chcp 65001` hoặc `$env:PYTHONIOENCODING='utf-8'`.
- Hoặc xem trực tiếp EVAL.md qua editor (VS Code) thay vì `cat` console.

---

## 6. Reproducibility

- Dataset restore từ commit `0af44f0` (M1 archive) — byte-identical SHA256 ghi `09-01-SUMMARY.md`.
- 12 queries.jsonl port semantic từ M1 + patch thêm `hub_id="eval_hub"` (M2 schema).
- Phase 9 ship 1 EVAL.md trong git. Phase 10+ re-run sinh history gitignored.
- Seed hub idempotent — eval_hub luôn cùng UUID nếu seed 1 lần.

---

## 7. Tài liệu liên quan

- `.planning/phases/09-eval-framework-quality-gate/09-RESEARCH.md` — Research full.
- `.planning/phases/09-eval-framework-quality-gate/09-0[1-4]-PLAN.md` — Plan chi tiết wave 1-3.
- `.planning/phases/09-eval-framework-quality-gate/09-0[1-3]-SUMMARY.md` — Executed summary wave 1-2.
- `.planning/REQUIREMENTS.md` — EVAL-01..04 spec.
- `.planning/ROADMAP.md` — Phase 9 SC + EXIT E5.
- `.planning/PROJECT.md` — EXIT criteria, M2a/M2b split.

---

## 8. Makefile targets

Từ thư mục `Hub_All/`:

| Target | Mô tả |
|--------|-------|
| `make eval-install` | `cd eval && pip install -e ".[dev]"` |
| `make eval-seed` | psql -f eval/scripts/seed_hub.sql (idempotent INSERT eval_hub) |
| `make eval-clean` | python -m eval.scripts.cleanup (API DELETE + Postgres + Redis) |
| `make eval-smoke` | python -m eval.run_eval --mock-embed --skip-cleanup (< 60s) |
| `make eval-all` | cleanup + run_eval real LLM (yêu cầu OPENAI_API_KEY) |
| `make eval-report` | python -m eval.report eval/results.json eval/EVAL.md |
| `make eval-readme` | In quick start workflow (snippet) |
| `make eval-restore` | git checkout 0af44f0 -- Hub_All/eval/dataset/ (restore dataset M1) |
