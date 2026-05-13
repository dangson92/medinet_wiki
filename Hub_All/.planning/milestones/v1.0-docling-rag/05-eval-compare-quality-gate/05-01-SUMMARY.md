---
phase: 05-eval-compare-quality-gate
plan: 01
subsystem: eval
status: completed
tags: [eval, foundation, shared-lib, docling-mode-runner]
requirements: []
dependency_graph:
  requires:
    - eval/baseline.py (Phase 1 — pattern source, KHÔNG sửa)
    - eval/baseline_native.json (Phase 1 — embedder lock reference)
    - /api/rag-config PUT (CFG-03 hot-swap, Phase 4)
    - documents.extractor_used VARCHAR(20) (CFG-06, Phase 4 plan-05)
    - /api/documents/{id}/reindex (CFG-07, Phase 4 plan-05)
  provides:
    - eval/lib.py — shared APIClient + helper cho Plan 05-02..05
    - eval/run_docling.py — input chính cho Plan 05-02 (extraction compare) + Plan 05-03 (retrieval eval)
    - eval/baseline_docling.json schema (artifact runtime user chạy)
  affects:
    - eval/pyproject.toml (thêm tabulate>=0.9 dep cho Plan 05-04)
tech_stack:
  added:
    - tabulate>=0.9 (Markdown table generator cho EVAL.md)
  patterns:
    - APIClient sync wrapper (đơn giản hoá so với async baseline.py — script eval chạy sequential)
    - Try/finally restore mode auto (T-05-01 mitigation — đảm bảo dev mode không stuck ở docling)
    - Hard-fail embedder lock verify (gate fairness tuyệt đối cho compare Phase 5)
key_files:
  created:
    - eval/lib.py (707 dòng)
    - eval/run_docling.py (260 dòng)
  modified:
    - eval/pyproject.toml (+1 dòng dep tabulate)
decisions:
  - "APIClient sync (httpx.Client) thay vì async — script eval Phase 5 chạy sequential, giảm complexity"
  - "Helper get_rag_collections() tách riêng để get_embedder_config có thể compose flexible"
  - "make_snapshot() helper dùng chung schema cho baseline_docling.json + future native re-run nếu cần"
  - "assert_embedder_match raise SystemExit thay vì return bool — fail-fast force user fix env trước khi run"
metrics:
  duration_minutes: 25
  completed_date: "2026-05-04"
  tasks_completed: 3
  files_changed: 3
  lines_added: 968
commit: bc606be
---

# Phase 5 Plan 01: Foundation `lib.py` + `run_docling.py` Summary

Tạo nền tảng Phase 5 — module `eval/lib.py` shared API client + helper, script `eval/run_docling.py` chạy ingestion mode docling runtime với try/finally restore + embedder lock verify. Toàn bộ Plan 05-02..05 sẽ `from lib import ...` và đọc `eval/baseline_docling.json` snapshot.

---

## 1. Tóm tắt thực thi

**Mode:** YOLO autonomous · **Wave:** 1 · **Tasks:** 3/3 PASS · **Commit:** `bc606be`.

| Task | Output | Lines | Verify |
|---|---|---|---|
| 1. Tạo `eval/lib.py` shared module | APIClient + 5 helper + 3 dataclass | 707 | `ast.parse` OK + `from lib import ...` OK toàn bộ symbol |
| 2. Update `eval/pyproject.toml` | +tabulate>=0.9 | +1 | `grep tabulate` PASS |
| 3. Tạo `eval/run_docling.py` | Orchestrator switch mode docling + snapshot | 260 | `ast.parse` OK + `import run_docling` OK |

**Runtime smoke:** Defer cho user — script `run_docling.py` cần Docling sidecar real (Phase 2-4) chạy ở `http://localhost:8081` + backend Go up + hub `eval` đã seed. Plan 05-01 chỉ commit code + verify static (parse + import); chạy thực tế dồn vào Plan 05-04 orchestrator hoặc khi user gọi `/gsd-verify-work 5`.

---

## 2. Interface contract đã expose

`eval/lib.py` cung cấp cho Plan 05-02..05:

### Dataclass

```python
@dataclass
class DocResult:
    doc_id: str; filename: str; status: str
    chunks_count: int; avg_chunk_tokens: float
    extractor_used: str  # "docling" | "native" | ""
    error: str | None = None

@dataclass
class QueryResult:
    query_id: str; query: str; expected_doc_id: str
    top_rank: int | None
    actual_top_5: list[str]

@dataclass
class RetrievalMetrics:
    top_1_hit_rate: float; top_3_hit_rate: float; top_5_hit_rate: float
    mrr: float
    per_query: list[QueryResult]
```

### APIClient (sync)

```python
client = APIClient(base_url, email, password)
client.login()                                          # access + refresh token
client.refresh_if_expired()                             # auto retry on 401
client.get_hub_id(code) -> str
client.upload_and_wait(hub_id, file_path, timeout=300) -> dict  # poll status + GET detail (extractor_used)
client.search(hub_id, query, top_k=5, min_score=0.0) -> list[dict]
client.get_rag_config() -> dict                         # public
client.get_rag_collections() -> dict                    # admin
client.put_rag_config(payload) -> dict                  # admin (CFG-03 hot-swap)
client.update_rag_config(payload) -> dict               # alias put_rag_config
client.reindex(doc_id, extractor) -> dict               # CFG-07
```

### Module-level helper

```python
preflight(backend_url, db_dsn, chroma_url, hub_code) -> None  # 3 check fail-loud
get_embedder_config(client) -> dict                            # provider + model + dim
assert_embedder_match(current, baseline_native_path) -> None   # SystemExit nếu lệch
upload_dataset(client, hub_id, dataset_dir, timeout=300) -> list[DocResult]
evaluate_queries(client, hub_id, queries_path, top_k=5) -> RetrievalMetrics
make_snapshot(extractor_mode, embedder, eval_hub_id, docs, metrics, queries_count, extra=None) -> dict
```

---

## 3. Snapshot schema `baseline_docling.json`

Identical schema với `baseline_native.json` (Phase 1) + thêm field `extractor_used` per-document và `extractor_used_summary` aggregate:

```json
{
  "run_id": "2026-05-XXTHH:MM:SSZ",
  "extractor_mode": "docling",
  "embedder_provider": "openai",
  "embedder_model": "text-embedding-3-large",
  "embedder_dim": 3072,
  "chunker": "...",
  "eval_hub_id": "...",
  "documents": [
    {
      "id": "...", "filename": "...",
      "status": "completed|error|timeout",
      "chunks_count": N, "avg_chunk_tokens": F,
      "extractor_used": "docling|native|",
      "error_message": null
    }
  ],
  "retrieval": {
    "top_1_hit_rate": 0.xxx, "top_3_hit_rate": 0.xxx, "top_5_hit_rate": 0.xxx,
    "mrr": 0.xxx,
    "per_query": [...]
  },
  "queries_count": 12,
  "files_count": 10,
  "min_score_used": 0.0,
  "extractor_used_summary": {"docling": N, "native": N, "unknown": N}
}
```

---

## 4. Pipeline `run_docling.py`

```
0. preflight() — backend Go + ChromaDB + hub seed
1. APIClient.login()
2. embedder = get_embedder_config(client)        ← capture TRƯỚC switch
3. assert_embedder_match(embedder, "baseline_native.json")  ← gate fairness, SystemExit nếu lệch
4. run_cleanup() (subprocess eval/scripts/cleanup.py)       ← --skip-cleanup nếu cần
5. original_mode = current_cfg["extractor_mode"]            ← log để debug
6. client.put_rag_config({"extractor_mode": "docling"})     ← log loud "SWITCH"
7. try:
     docs = upload_dataset(client, hub_id, "eval/dataset", timeout=300)
     log distribution: docling=N native=N unknown=N
     metrics = evaluate_queries(client, hub_id, queries.jsonl, top_k=5)
     snapshot = make_snapshot(...)
     write eval/baseline_docling.json
   finally:
     client.put_rag_config({"extractor_mode": "auto"})  ← restore (T-05-01 mitigation)
     log RESTORE FAIL nếu exception
8. close client + exit 0/1
```

---

## 5. Deviations from Plan

**None** — plan executed exactly as written.

Auto-mode decisions log:

| Quyết định | Lý do |
|---|---|
| APIClient sync thay vì async | Script eval Phase 5 chạy sequential, giảm complexity httpx.Client + asyncio.run wrap |
| `make_snapshot` helper tách riêng | Plan 05-04 orchestrator có thể gọi nếu re-run native dùng chung lib.py |
| `update_rag_config` alias `put_rag_config` | Đồng bộ 2 tên trong task description Plan 05-01 (line 28 vs CONTEXT) |
| `get_rag_collections` tách method riêng | Cho phép `get_embedder_config` compose linh hoạt + plan 05-03/04 có thể gọi trực tiếp |
| `--skip-cleanup` CLI arg | Plan 05-04 orchestrator có thể gọi `run_docling.py` sau khi đã cleanup riêng — tránh double-cleanup |

---

## 6. Threat Model Compliance

| Threat ID | Mitigation Applied | Where |
|---|---|---|
| T-05-01 (Tampering — extractor_mode corrupt) | Try/finally restore về `auto` cuối run; nếu restore fail vẫn log RESTORE FAIL với manual recovery hint | `run_docling.py` `finally` block |
| T-05-02 (Info Disclosure — admin token) | Đọc từ env, không log token raw | `lib.py` ADMIN_PASSWORD via `os.getenv` |
| T-05-03 (DoS — switch mode khi worker đang process) | `run_cleanup()` reset state trước khi switch — Plan 05-04 orchestrator sẽ wait workers idle (nhiệm vụ Plan 05-04) | `run_docling.py` step 4 |

---

## 7. Files Manifest

**Created:**
- `eval/lib.py` (707 dòng) — shared module
- `eval/run_docling.py` (260 dòng) — orchestrator docling mode

**Modified:**
- `eval/pyproject.toml` (+1 dòng) — `tabulate>=0.9` dep

**Untouched (immutable):**
- `eval/baseline.py` — Phase 1 pattern source
- `eval/baseline_native.json` — Phase 1 baseline 75% top-3

---

## 8. Verification Checklist

- [x] `python -c "import ast; ast.parse(open('eval/lib.py').read())"` → `lib.py parse OK`
- [x] `python -c "import ast; ast.parse(open('eval/run_docling.py').read())"` → `run_docling.py parse OK`
- [x] `cd eval && python -c "from lib import APIClient, preflight, ..."` → `lib.py import OK — all symbols expose`
- [x] `cd eval && python -c "import run_docling"` → `run_docling.py import OK`
- [x] `grep tabulate eval/pyproject.toml` → `"tabulate>=0.9",` line 15
- [x] `eval/baseline.py` không bị sửa (Phase 1 immutable)
- [x] `eval/baseline_native.json` không bị sửa (Phase 1 immutable)
- [x] Single atomic commit: `bc606be`
- [x] Stage từng file riêng (KHÔNG `git add .`)
- [ ] Runtime smoke chạy thật — **DEFERRED** (Plan 05-04 orchestrator hoặc `/gsd-verify-work 5`)

---

## Self-Check: PASSED

- File `eval/lib.py`: FOUND
- File `eval/run_docling.py`: FOUND
- File `eval/pyproject.toml`: tabulate FOUND
- Commit `bc606be`: FOUND in `git log`
- 3 verify automated PASS

---

## 9. Next Plan

**Plan 05-02** — `run_extraction_compare.py` (EVAL-02): load 2 snapshot, compare per-document `chunks_count` + `avg_chunk_tokens`, compute heading recall + table preservation. `from lib import ...` đã sẵn sàng.

*Last updated: 2026-05-04 — Plan 05-01 PASS, commit `bc606be`.*
