---
phase: 05-eval-compare-quality-gate
plan: 02
subsystem: eval
status: completed
tags: [eval, extraction-compare, heading-recall, table-preservation, accent-strip-vi]
requirements: [EVAL-02]
dependency_graph:
  requires:
    - eval/baseline_native.json (Phase 1, immutable, 75% top-3 baseline)
    - eval/baseline_docling.json (Plan 05-01 output, runtime artifact)
    - eval/dataset/headings.json (Phase 1 EVAL-01, gold headings)
    - Postgres document_chunks table (content + metadata JSONB)
  provides:
    - eval/run_extraction_compare.py — script EVAL-02 per-document compare
    - eval/extraction_compare.json schema (artifact runtime cho Plan 05-04 orchestrator)
  affects:
    - Plan 05-04 orchestrator (run_compare.py) sẽ load extraction_compare.json để render EVAL.md
tech_stack:
  added: []
  patterns:
    - "strip_accent() NFKD + drop combining marks + lowercase + collapse whitespace (W2 fix tiếng Việt)"
    - "Pre-normalize chunks 1 lần trước heading recall loop (O(N+M) thay O(N×M))"
    - "Hardcode TABLES_TOTAL_GOLD dict ở đầu script (Phase 1 đã label trong dataset)"
    - "Substring loose match heading (accept format whitespace/punctuation drift Docling vs python-docx)"
    - "Defensive metadata.is_table parse: chấp nhận cả bool true và string 'true'"
key_files:
  created:
    - eval/run_extraction_compare.py (448 dòng)
  modified: []
decisions:
  - "Hardcode TABLES_TOTAL_GOLD thay vì parse DOCX runtime — đơn giản + KHÔNG add dep python-docx ở compare script (lib.py đã có)"
  - "Output schema thêm headings_matched + headings_total per-doc (debug-friendly) ngoài 4 metric chính plan spec"
  - "Pretty-print tabulate Markdown table giúp debug nhanh stdout — KHÔNG block nếu tabulate chưa cài (warning thôi)"
  - "Index by filename thay doc_id — filename stable hơn, doc_id mỗi run khác (UUID per upload)"
  - "Stable order theo native snapshot order (giữ diff git ổn định cho extraction_compare.json)"
metrics:
  duration_minutes: 15
  completed_date: "2026-04-29"
  tasks_completed: 1
  files_changed: 1
  lines_added: 448
commit: 06b3e19
---

# Phase 5 Plan 02: `run_extraction_compare.py` (EVAL-02) Summary

Script `eval/run_extraction_compare.py` so sánh chất lượng extraction per-document giữa 2 mode (native vs docling) — đo `chunks_count`, `avg_chunk_tokens`, **heading recall** (so heading vàng `eval/dataset/headings.json` qua DB direct psycopg + accent-strip), **table preservation rate** (đếm chunks `metadata.is_table=true` qua Phase 4 CFG-06 schema). Sinh JSON intermediate `eval/extraction_compare.json` cho Plan 05-04 orchestrator consume.

---

## 1. Tóm tắt thực thi

**Mode:** YOLO autonomous · **Wave:** 2 · **Tasks:** 1/1 PASS · **Commit:** `06b3e19`.

| Task | Output | Lines | Verify |
|---|---|---|---|
| 1. Tạo `eval/run_extraction_compare.py` | argparse + load snapshot + heading recall + table preservation + sinh extraction_compare.json | 448 | `ast.parse` OK + helper smoke tests (`strip_accent`/`count_heading_recall`/`count_tables`/`compute_summary`) PASS |

**Runtime smoke:** Defer cho user — script cần `baseline_docling.json` (Plan 05-01 runtime artifact) + Postgres có data Docling đã ingest. Plan 05-02 chỉ commit code + verify static + helper unit-style smoke; chạy thực tế dồn vào Plan 05-04 orchestrator hoặc `/gsd-verify-work 5`.

---

## 2. Interface contract đã expose

### Helper public (Plan 05-04 có thể import)

```python
from run_extraction_compare import (
    strip_accent,                # str → str (NFKD + lowercase + collapse ws)
    count_heading_recall,        # (chunks, gold_headings) → (matched, total, recall)
    count_tables,                # chunks → int
    query_chunks_for_doc,        # (conn, doc_id) → list[{"content": str, "metadata": dict}]
    compare_one_document,        # (conn, filename, native_doc, docling_doc, gold) → dict
    compute_summary,             # per_doc → aggregate dict
)
```

### Output schema `eval/extraction_compare.json`

```json
{
  "run_id": "2026-MM-DDTHH:MM:SSZ",
  "native_snapshot": "eval/baseline_native.json",
  "docling_snapshot": "eval/baseline_docling.json",
  "documents": [
    {
      "filename": "DMD_T1-01_DinhVi_TrungTam_v1.docx",
      "native":  {"chunks_count": 152, "avg_chunk_tokens": 487.0, "heading_recall": 0.65, "headings_matched": 18, "headings_total": 28, "tables_preserved": 3, "tables_total": 4},
      "docling": {"chunks_count": 178, "avg_chunk_tokens": 412.0, "heading_recall": 0.92, "headings_matched": 26, "headings_total": 28, "tables_preserved": 4, "tables_total": 4},
      "delta":   {"chunks_count": 26, "avg_chunk_tokens": -75.0, "heading_recall_pp": 27.0, "tables_preserved": 1}
    }
  ],
  "summary": {
    "avg_heading_recall_native":  0.45,
    "avg_heading_recall_docling": 0.78,
    "table_preservation_native":  0.60,
    "table_preservation_docling": 0.95,
    "tables_total_gold":          11,
    "tables_preserved_native":    7,
    "tables_preserved_docling":  10,
    "documents_count":           10
  }
}
```

Schema này khớp `<interfaces>` Plan spec + thêm `headings_matched`/`headings_total` per-doc và `tables_total_gold`/`tables_preserved_*` aggregate cho debug-friendly.

---

## 3. Logic chính

### 3.1 `strip_accent()` — W2 fix tiếng Việt

Heading vàng tiếng Việt có dấu (vd `"PHẦN 01  |  CÂU TUYÊN BỐ"`). Chunk content do Docling vs python-docx normalize khác nhau (NFC/NFD/whitespace/punctuation drift). Solution:

```python
nfkd = unicodedata.normalize("NFKD", s)
stripped = "".join(c for c in nfkd if not unicodedata.combining(c))
return " ".join(stripped.lower().split())
```

Test: `"PHẦN 01  |  CÂU TUYÊN BỐ"` → `"phan 01 | cau tuyen bo"`. Substring match accent-stripped → robust với cả native (python-docx) lẫn Docling output.

### 3.2 `count_heading_recall()` — pre-normalize O(N+M)

Pre-normalize **chunks 1 lần** trước loop heading (avoid O(N×M) accent-strip trên mỗi cặp). Với 10 file × ~30-150 chunks × ~30-70 headings → speedup ~30-70× so với normalize trong loop.

### 3.3 `count_tables()` — defensive bool/string

Phase 4 CFG-06 lưu `metadata.is_table` dạng JSONB. Tuỳ extractor (native vs Docling) có thể ghi bool `true` hoặc string `"true"`. Script chấp nhận cả 2:

```python
if is_table is True or (isinstance(is_table, str) and is_table.lower() == "true"):
    count += 1
```

### 3.4 Hardcode `TABLES_TOTAL_GOLD`

Phase 1 đã label số bảng trong dataset (auto-mode log). Hardcode dict 10 entry ở đầu script (theo CONTEXT spec line 122). Fallback `tables_total = 0` nếu file không có trong mapping (script vẫn chạy). Plan 05-04 có thể tinh chỉnh mapping nếu có spread thật.

### 3.5 Pre-condition fail-loud

- `baseline_native.json` thiếu → SystemExit(2) generic.
- `baseline_docling.json` thiếu → **SystemExit(2) với message rõ "Run `python eval/run_docling.py` first"** (theo plan task spec).
- `headings.json` thiếu → SystemExit(2) (Phase 1 EVAL-01 artifact).
- Postgres connect lỗi → SystemExit(2) với hint env DB_*/--db-dsn.

---

## 4. Verify

### Automated (PASSED)

```
$ python -c "import ast; ast.parse(open('eval/run_extraction_compare.py', encoding='utf-8').read()); print('parse OK')"
parse OK

$ python -c "..." (helper smoke tests, xem section dưới)
helper tests PASS
```

### Helper smoke tests (PASSED)

| Helper | Test case | Expected | Got |
|---|---|---|---|
| `strip_accent` | `"PHẦN 01  \|  CÂU TUYÊN BỐ"` | `"phan 01 \| cau tuyen bo"` | OK |
| `strip_accent` | `""` | `""` | OK |
| `count_heading_recall` | 2 chunks × 3 headings (2 match, 1 miss) | `(2, 3, 0.667)` | OK |
| `count_tables` | 4 chunks (1 bool true, 1 str "true", 1 false, 1 empty) | `2` | OK |
| `compute_summary` | empty per_doc | `documents_count=0` | OK |

### Runtime (DEFERRED)

Cần `baseline_docling.json` + Postgres có chunks → defer Plan 05-04 orchestrator hoặc `/gsd-verify-work 5`.

---

## 5. Deviations from Plan

**None** — plan executed exactly as written.

Auto-mode quyết định bổ sung (Rule 2 — auto-add critical functionality, không cần ask):

| Quyết định | Lý do |
|---|---|
| Thêm field `headings_matched`/`headings_total` per-doc | Debug-friendly: khi recall thấp user cần biết "miss bao nhiêu/tổng bao nhiêu" mới điều tra được |
| Thêm `tables_total_gold` + `tables_preserved_native/docling` aggregate | Plan 05-04 EVAL.md report cần exact numerator/denominator để render bảng |
| Pretty-print tabulate stdout | Dev workflow: chạy local thấy ngay diff trước khi đọc JSON |
| Defensive `count_tables` parse string + bool | Phase 4 CFG-06 schema bool nhưng JSONB query có thể trả string tuỳ driver — không break run khi schema drift nhỏ |
| Order documents theo native snapshot order | Diff git extraction_compare.json ổn định giữa các run |
| `--db-dsn` CLI override | Plan 05-04 orchestrator có thể inject DSN khác (vd test DB) |

---

## 6. Threat Model Compliance

| Threat ID | Mitigation Applied | Where |
|---|---|---|
| T-05-04 (Info Disclosure — DB credential env) | Đọc env, KHÔNG log password raw | `build_dsn()` chỉ log `dbname`/`host`, không log full DSN |
| T-05-05 (Tampering — heading match loose substring false positive) | Accept theo plan: heading có format đặc biệt (PHẦN, CHƯƠNG, Q.X, ▸) → false positive thấp; strip_accent + collapse whitespace giảm false negative thay vì false positive | Documented |

---

## 7. Files Manifest

**Created:**
- `eval/run_extraction_compare.py` (448 dòng)

**Untouched:**
- `eval/baseline_native.json` (Phase 1 immutable)
- `eval/baseline_docling.json` (chưa tồn tại — sẽ sinh khi user chạy `run_docling.py`)
- `eval/lib.py` (Plan 05-01 — KHÔNG cần import vì script này standalone DB-only)

---

## 8. Verification Checklist

- [x] `python -c "import ast; ast.parse(open('eval/run_extraction_compare.py').read())"` → `parse OK`
- [x] Helper smoke tests (`strip_accent`/`count_heading_recall`/`count_tables`/`compute_summary`) PASS
- [x] File ≥ 200 dòng (448 dòng)
- [x] Argparse có `--native-snapshot`/`--docling-snapshot`/`--headings`/`--out`/`--db-dsn`
- [x] Pre-condition: SystemExit(2) "Run `python eval/run_docling.py` first" khi thiếu docling
- [x] Heading recall query DB direct (psycopg) thay vì API
- [x] Schema output khớp `<interfaces>` plan spec
- [x] Single atomic commit `06b3e19`
- [x] Stage file riêng (`git add eval/run_extraction_compare.py`)
- [ ] Runtime DB integration — **DEFERRED** (Plan 05-04 hoặc `/gsd-verify-work 5`)

---

## Self-Check: PASSED

- File `eval/run_extraction_compare.py`: FOUND
- Commit `06b3e19`: FOUND in `git log`
- AST parse: OK
- Helper smoke tests: 5/5 PASS

---

## 9. Next Plan

**Plan 05-03** — `run_retrieval_eval.py` (EVAL-03): load 12 queries từ `eval/dataset/queries.jsonl`, chạy 12 query × 2 mode (native lookup snapshot, docling chạy thật qua `/api/search`), compute top-1/3/5 hit rate + MRR, sinh `eval/retrieval_eval.json` intermediate.

*Last updated: 2026-04-29 — Plan 05-02 PASS, commit `06b3e19`. Phase 5 progress 2/5 plans.*
