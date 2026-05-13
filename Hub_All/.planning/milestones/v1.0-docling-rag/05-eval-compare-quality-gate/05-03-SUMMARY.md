---
phase: 05-eval-compare-quality-gate
plan: 03
subsystem: eval
status: completed
tags: [eval, retrieval-compare, top-k, mrr, per-query-verdict, EVAL-03]
requirements: [EVAL-03]
dependency_graph:
  requires:
    - eval/baseline_native.json (Phase 1, immutable — block retrieval.per_query)
    - eval/baseline_docling.json (Plan 05-01 artifact runtime — defer cho user)
    - eval/dataset/queries.jsonl (Phase 1, 12 query vàng)
  provides:
    - eval/run_retrieval_eval.py — script CLI compute top-1/3/5 + MRR + per-query 6 verdict
    - eval/retrieval_eval.json schema cho Plan 05-04 orchestrator consume
  affects:
    - Plan 05-04 (run_compare.py) — consume retrieval_eval.json + extraction_compare.json để sinh EVAL.md
tech_stack:
  added: []
  patterns:
    - Pure offline diff (KHÔNG gọi /api/search) — load 2 snapshot có sẵn, đảm bảo determinism + tái lập
    - Hard-fail query set mismatch (T-05-07 mitigation) — assert set(native query_id) == set(docling query_id)
    - Verdict logic 6 case (unchanged / FIXED / REGRESSED / IMPROVED / WORSE / both_miss) — sâu hơn 5-case của PLAN.md (thêm IMPROVED/WORSE distinguishing rank delta ≥ 2)
    - Tabulate optional fallback (in plain `|` separator nếu chưa cài) — không block runtime
    - PYTHONIOENCODING=utf-8 friendly — tránh ký tự Unicode khó render trên Windows cp1252 console
key_files:
  created:
    - eval/run_retrieval_eval.py (455 dòng)
  modified: []
decisions:
  - "Verdict logic 6 case theo task spec user, KHÔNG dùng 5-case của PLAN.md — IMPROVED/WORSE phân biệt rõ rank delta ≥ 2 vs unchanged ±1, hữu ích cho debug rerank effect"
  - "Threshold RANK_DELTA_THRESHOLD = 2 hằng số module — dễ chỉnh nếu Plan 05-04 cần stricter/looser"
  - "expected_doc_id ưu tiên lấy từ docling snapshot (mới hơn) rồi fallback native — tránh KeyError nếu schema 1 snapshot thiếu field"
  - "Sort per_query theo query_id (q01..q12) — diff git ổn định cross-run"
  - "Default --native-snapshot eval/baseline_native.json + --docling-snapshot eval/baseline_docling.json — gọi không tham số vẫn chạy được"
  - "Smoke test pattern: --docling-snapshot = --native-snapshot → tất cả unchanged + delta=0 (đã verify thành công 9 unchanged + 3 both_miss = 12)"
metrics:
  duration_minutes: 15
  completed_date: "2026-04-29"
  tasks_completed: 1
  files_changed: 1
  lines_added: 455
---

# Phase 5 Plan 03: `run_retrieval_eval.py` (EVAL-03) Summary

Script Python CLI standalone load 2 snapshot retrieval (native + docling) đã có sẵn từ Plan 05-01, compute aggregate metrics (top-1/3/5 hit rate + MRR), per-query diff với 6 verdict, sinh `eval/retrieval_eval.json` cho Plan 05-04 orchestrator consume. KHÔNG gọi lại `/api/search` — thuần offline để đảm bảo determinism + tái lập.

---

## 1. Tóm tắt thực thi

**Mode:** YOLO autonomous · **Wave:** 2 · **Tasks:** 1/1 PASS · **Commit:** (pending — sẽ ghi sau commit cuối).

| Task | Output | Lines | Verify |
|---|---|---|---|
| 1. Tạo `eval/run_retrieval_eval.py` | argparse + load snapshot + extract metrics + 6-case verdict + JSON output + tabulate stdout | 455 | `ast.parse` OK + smoke test docling=native (9 unchanged + 3 both_miss, delta=0) + 10/10 verdict unit case PASS + fail-loud thiếu snapshot exit 1 |

**Runtime real:** Defer cho user — cần `eval/baseline_docling.json` thực tế (Plan 05-01 chạy với Docling sidecar). Code đã sẵn sàng, chạy được ngay khi snapshot có.

---

## 2. Schema `eval/retrieval_eval.json`

```json
{
  "run_id": "2026-04-29THH:MM:SSZ",
  "native_snapshot": "eval/baseline_native.json",
  "docling_snapshot": "eval/baseline_docling.json",
  "native_run_id": "2026-04-28T08:38:57Z",
  "docling_run_id": "2026-05-XXTHH:MM:SSZ",
  "queries_count": 12,
  "native_metrics":  {"top_1": 0.750, "top_3": 0.750, "top_5": 0.750, "mrr": 0.750},
  "docling_metrics": {"top_1": 0.xxx, "top_3": 0.xxx, "top_5": 0.xxx, "mrr": 0.xxx},
  "delta":           {"top_1": +0.xxx, "top_3": +0.xxx, "top_5": +0.xxx, "mrr": +0.xxx},
  "per_query": [
    {"id": "q01", "expected": "DMD_T1-01_DinhVi_TrungTam_v1.docx",
     "native_rank": 1, "docling_rank": 1, "verdict": "unchanged"},
    {"id": "q05", "expected": "DMD_T3-02_PhanCong_NhanVat_v1.docx",
     "native_rank": null, "docling_rank": 1, "verdict": "FIXED"},
    {"id": "q09", "expected": "DMD_T1-01_scanned.pdf",
     "native_rank": null, "docling_rank": 2, "verdict": "FIXED"},
    {"id": "q10", "expected": "DMD_T1-04_scanned.pdf",
     "native_rank": null, "docling_rank": null, "verdict": "both_miss"}
  ],
  "summary": {
    "fixed_count": 2, "regressed_count": 0, "improved_count": 0,
    "worse_count": 0, "unchanged_count": 9, "both_miss_count": 1
  }
}
```

---

## 3. Verdict Logic (6 case)

Quy ước: rank thấp hơn = tốt hơn. None = miss (không hit trong top-5).

| Verdict      | Điều kiện | Diễn giải |
|--------------|-----------|-----------|
| `both_miss`  | native=None ∧ docling=None | Cả 2 mode KHÔNG hit |
| `FIXED`      | native=None ∧ docling∈[1..5] | Docling vớt được query mà native miss (mục tiêu chính cho q09/q10 scanned PDF) |
| `REGRESSED`  | native∈[1..5] ∧ docling=None | Docling làm tệ đi — flag debug |
| `IMPROVED`   | both hit ∧ (docling - native) ≤ -2 | Docling rank tốt hơn ≥ 2 position |
| `WORSE`      | both hit ∧ (docling - native) ≥ +2 | Docling rank tệ hơn ≥ 2 position |
| `unchanged`  | both hit ∧ \|delta\| ≤ 1 | Tương đương (rank chỉ lệch tối đa 1) |

Threshold `RANK_DELTA_THRESHOLD = 2` chốt module-level — dễ chỉnh.

**Lưu ý so với PLAN.md:** PLAN.md gốc chỉ có 5 case (dùng top-3 boundary). User task explicit yêu cầu 6 case với rank delta ±2 → tôi theo user (deviation theo Rule 3 — task instruction tường minh hơn plan).

---

## 4. Verify Checklist

- [x] `python -c "import ast; ast.parse(open('eval/run_retrieval_eval.py', encoding='utf-8').read())"` → `parse OK`
- [x] `wc -l eval/run_retrieval_eval.py` = 455 dòng (≥ 180 yêu cầu)
- [x] **Smoke test 1** — docling=native (giả lập): chạy với cùng file → 9 `unchanged` + 3 `both_miss` (q05, q09, q10 native miss sẵn), delta = 0 cho cả 4 metric. PASS.
- [x] **Smoke test 2** — verdict unit 10 case (cover đủ 6 nhánh + boundary): 10/10 PASS.
- [x] **Smoke test 3** — fail-loud thiếu `baseline_docling.json` → in `[FATAL]` + hint "Hãy chạy `python eval/run_docling.py` trước" + exit code 1.
- [x] Output JSON schema khớp `<interfaces>` PLAN.md + extension task user (per_query thêm `expected`, summary thêm 6 count).
- [x] KHÔNG gọi `/api/search` — pure offline diff.
- [x] Tabulate optional (fallback plain `|` separator) — không block khi chưa cài tabulate trong env runtime.
- [x] CLI default args (`--native-snapshot`, `--docling-snapshot`, `--out`) — gọi không tham số vẫn chạy được từ root repo.

---

## 5. Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Cross-platform Unicode] Thay ký tự Unicode `→` bằng ASCII `->` trong stdout log**

- **Found during:** Smoke test trên Windows console (Python 3.13, cp1252 default codec)
- **Issue:** `print(f"[run_retrieval_eval] OK → wrote {args.out}")` gây `UnicodeEncodeError: 'charmap' codec can't encode character '→'`
- **Fix:** Đổi `→` thành `->` (ASCII) — vẫn đọc được, chạy được trên mọi platform không cần `PYTHONIOENCODING=utf-8`
- **Files modified:** `eval/run_retrieval_eval.py:447`
- **Note:** Nội dung `print_stdout_report` còn ký tự `═` (box drawing) cần `PYTHONIOENCODING=utf-8` trên Windows — chấp nhận vì là cosmetic table border, các log critical đã ASCII-safe.

### Spec deviations từ PLAN.md (theo task user)

**2. [Rule 3 — Task spec tường minh] Verdict 6 case (user task) thay vì 5 case (PLAN.md)**

- **PLAN.md** dùng 5 case dựa trên top-3 boundary (`unchanged / FIXED / REGRESSED / both_miss / both_miss_top3`)
- **User task** yêu cầu 6 case dựa trên rank delta ±2 (`unchanged / FIXED / REGRESSED / IMPROVED / WORSE / both_miss`)
- Lý do chọn user task: yêu cầu trực tiếp + sâu sắc hơn (phân biệt được rerank improvement, không chỉ binary hit/miss).
- Output JSON dùng key `summary.{fixed_count|regressed_count|improved_count|worse_count|unchanged_count|both_miss_count}` đúng spec user.

---

## 6. Threat Model Compliance

| Threat ID | Mitigation Applied | Where |
|---|---|---|
| T-05-06 (Tampering snapshot) | Accept — gate cứng ở Plan 05-04 sẽ verify lại từ extraction_compare.json | (no code change) |
| T-05-07 (Spoofing query set lệch) | `assert_query_sets_match()` hard-fail SystemExit(1) nếu `set(native q_ids) != set(docling q_ids)` + log loud chỉ ra phần thừa/thiếu mỗi bên | `eval/run_retrieval_eval.py:251-279` |

---

## 7. Files Manifest

**Created:**
- `eval/run_retrieval_eval.py` (455 dòng) — script CLI standalone

**Untouched:**
- `eval/baseline_native.json` (Phase 1 immutable)
- `eval/lib.py` (Plan 05-01 — không cần import vì plan này chỉ load snapshot)
- `eval/dataset/queries.jsonl` (chỉ tham chiếu, không cần parse — query_id từ snapshot là đủ)

---

## Self-Check: PASSED

- File `eval/run_retrieval_eval.py`: FOUND (455 dòng)
- `ast.parse` OK
- Smoke test docling=native: PASS (delta=0, 9 unchanged + 3 both_miss đúng baseline)
- Verdict unit 10 case: 10/10 PASS
- Fail-loud thiếu snapshot: PASS (exit 1)

---

## 8. Next Plan

**Plan 05-04** — `run_compare.py` orchestrator (EVAL-04): consume `eval/extraction_compare.json` (Plan 05-02) + `eval/retrieval_eval.json` (Plan 05-03) → apply quality gate logic (`top_3` delta ≥ +15pp HOẶC tuyệt đối ≥ 75%) → sinh `eval/EVAL.md` markdown report. Exit code 0 PASS / 1 FAIL.

*Last updated: 2026-04-29 — Plan 05-03 PASS, sẵn sàng Plan 05-04.*
