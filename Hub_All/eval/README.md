# Eval Framework — Medinet Wiki M2 RAG

**Phase 9** — Quality gate ≥75% top-3 trên 10 file VN medical + 12 query vàng.

> Documentation đầy đủ workflow + troubleshooting + tiền điều kiện sẽ được hoàn thiện ở Plan 09-04 (Wave 3).

## Quickstart (tham khảo nhanh — chi tiết ở Plan 09-04)

```bash
# 1. Cài dependencies
cd Hub_All/eval && pip install -e ".[dev]"

# 2. Setup env (sửa OPENAI_API_KEY thật)
cp .env.example .env

# 3. Seed hub eval (chạy 1 lần)
psql $DB_HOST -U $DB_USER -d $DB_NAME -f scripts/seed_hub.sql

# 4. Smoke regression offline (mock embedding, < 60s)
make eval-smoke

# 5. Gate verdict (yêu cầu OPENAI_API_KEY thật + checkpoint human-verify)
make eval-all   # PASS → exit 0; FAIL → exit 1 (CI-friendly)
```

## Stack

- Python 3.12 · httpx 0.28 · psycopg 3.1+ · pytest 8+ · tabulate 0.9+ · python-dotenv
- Gọi API qua HTTP như external client (KHÔNG import `app.services.*`)
- Test pytest mock-embed cho regression; real LLM cho gate verdict

## Cấu trúc

```
eval/
├── lib.py            # APIClient + preflight (Plan 09-02)
├── metrics.py        # top-K + MRR + latency percentile (Plan 09-02)
├── report.py         # EVAL.md generator (Plan 09-03)
├── run_eval.py       # Orchestrator (Plan 09-04)
├── queries.jsonl     # 12 query vàng VN medical (port từ M1)
├── dataset/          # 10 file VN medical (restore từ M1)
├── scripts/
│   ├── seed_hub.sql  # Idempotent INSERT eval_hub
│   └── cleanup.py    # Reset state trước mỗi run (Plan 09-04)
├── results.json      # Run output (gitignored)
└── EVAL.md           # Gate verdict report (commit cuối Phase 9)
```

## Tài liệu

- `Hub_All/.planning/phases/09-eval-framework-quality-gate/09-RESEARCH.md` — Research full
- `Hub_All/.planning/REQUIREMENTS.md` — EVAL-01..04 spec
