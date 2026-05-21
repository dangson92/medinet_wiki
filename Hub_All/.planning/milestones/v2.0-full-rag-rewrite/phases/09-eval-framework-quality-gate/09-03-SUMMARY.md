---
phase: 09-eval-framework-quality-gate
plan: 03
subsystem: eval
tags: [python, markdown, tabulate, quality-gate, exit-code, ci, e5-trigger, pytest]

# Dependency graph
requires:
  - phase: 09-01
    provides: eval/ skeleton + pyproject.toml + tabulate>=0.9 dep + queries.jsonl 12 dòng
provides:
  - Hub_All/eval/report.py — generate_eval_md (7 section Markdown) + gate_verdict (≥0.75 PASS, <0.60 E5) + main CLI
  - Hub_All/eval/tests/test_report.py — 17 unit test (3 @critical + 14 standard)
affects: [09-04-run-eval-orchestrator, 09-05-quality-gate-run]

# Tech tracking
tech-stack:
  added: []  # tabulate>=0.9 đã có sẵn từ Plan 09-01 pyproject.toml — KHÔNG thêm dep mới
  patterns:
    - "Threshold pin từ ROADMAP + PROJECT EXIT criteria (GATE_THRESHOLD_PASS=0.75, GATE_THRESHOLD_E5_STOP=0.60)"
    - "Verdict dict 3 trường (verdict + exit_code + trigger_e5) cho CI gate + special action"
    - "Markdown generator pure compute KHÔNG side effect — idempotent test bằng dict mock tay"
    - "tabulate tablefmt='github' render table compact đẹp trong Markdown render preview"
    - "Recommendations conditional 3 nhánh (PASS / FAIL borderline / FAIL E5) bám PROJECT EXIT"
    - "CLI exit code tri-state: 0 PASS, 1 FAIL, 2 missing file (KHÔNG raise — graceful)"
    - "tmp_path fixture pytest cho CLI file I/O test — không pollute workspace"

key-files:
  created:
    - Hub_All/eval/report.py
    - Hub_All/eval/tests/test_report.py
  modified: []

key-decisions:
  - "D-09-03-A: gate_verdict trả dict 3 field thay vì tuple — exit_code + trigger_e5 tách rời. Plan ban đầu spec `tuple[str, int]` đơn giản, NHƯNG cần thêm trigger_e5 cho E5 STOP M2b (cảnh báo CLI). Dict cho phép extension không vỡ caller signature (Plan 09-04 orchestrator chỉ đọc exit_code + verdict)."
  - "D-09-03-B: Threshold constant module-level GATE_THRESHOLD_PASS=0.75 + GATE_THRESHOLD_E5_STOP=0.60 thay vì hardcode literal — cho phép unittest override khi cần (chỉnh chỉnh threshold cho regression test khác mà KHÔNG đụng logic). Đồng thời self-document constraint từ PROJECT.md + ROADMAP."
  - "D-09-03-C: CLI default paths eval/results.json + eval/EVAL.md KHÔNG hardcode absolute — chạy từ Hub_All root. Plan 09-04 orchestrator gọi main([results_path, output_path]) tường minh, CLI fallback default cho dev convenience."
  - "D-09-03-D: Exit code 2 (missing results file) KHÔNG raise — pattern Unix utility tri-state (0 OK, 1 logic-fail, 2 usage-error). Caller (Plan 09-04 + Makefile) propagate qua `python -m eval.report || exit $?` natural."
  - "D-09-03-E: EVAL.md sinh DÙ FAIL (chứa debug data per-query Section 3 + miss analysis Section 6) — quan trọng cho iterate chunker/prompt 3 vòng PROJECT EXIT criteria. Không skip generation khi gate FAIL."
  - "D-09-03-F: Đổi 3 ký tự EN DASH `–` thành HYPHEN-MINUS `-` trong comment + string để qua ruff RUF001/003. Tiếng Việt thường dùng EN DASH cho range số (0.60-0.75), nhưng ruff RUF lint mặc định không chấp nhận. Đổi sang ASCII dash đảm bảo lint sạch và không thay đổi semantic."

patterns-established:
  - "Pattern threshold constant module-level + helper function pure compute (gate_verdict)"
  - "Pattern Markdown report idempotent — sinh hoàn toàn từ dict input, KHÔNG mutate input, KHÔNG side effect (test rất rẻ)"
  - "Pattern CLI tri-state exit code (0 OK, 1 logic-fail, 2 usage-error) — Unix utility convention"
  - "Pattern tabulate tablefmt='github' cho table render compact + GitHub Flavored Markdown compat"
  - "Pattern 7 section EVAL.md template (Setup / Metrics / Per-Query / Latency / Conclusion / Recommendations / Defer) — reusable cho v4.0 eval expansion"

requirements-completed:
  - EVAL-03

# Metrics
duration: 10min
completed: 2026-05-21
---

# Phase 09 Plan 03: eval/report.py — EVAL.md generator + gate verdict

**Build `eval/report.py` — Markdown report generator 7 section (Setup + Metrics + Per-Query Diff + Latency + Conclusion + Recommendations + Defer) với tabulate render + quality gate verdict (≥0.75 PASS exit 0; <0.60 trigger E5 STOP M2b) + CLI exit code CI-friendly cho Plan 09-04 orchestrator.**

## Performance

- **Duration:** ~10 phút
- **Started:** 2026-05-21T07:05:00Z (sau Plan 09-02 metadata commit `0ff21c2`)
- **Completed:** 2026-05-21T07:15:00Z
- **Tasks:** 2/2
- **Files modified:** 0 (toàn bộ tạo mới — 2 file)

## Accomplishments

- **eval/report.py (360 dòng):** `gate_verdict(top_3)` trả dict 3 field (verdict/exit_code/trigger_e5) — pin threshold module-level 0.75 PASS + 0.60 E5 STOP. `generate_eval_md(results)` sinh Markdown UTF-8 7 section idempotent: Section 1 Setup (timestamp + backend + model + dataset + mock_embed flag); Section 2 Metrics (top-1/3/5 + MRR + upload summary failed_unsupported); Section 3 Per-Query Diff (id + query truncated 50 + expected + rank/MISS + top result truncated 40 + #results); Section 4 Latency (count + mean + p50/p95/p99 + budget 800ms compare); Section 5 Conclusion (badge ✅/❌ + rationale + exit code + E5 warning conditional); Section 6 Recommendations conditional 3 nhánh (PASS ship M2 / FAIL borderline iterate 3 vòng / FAIL E5 STOP M2b ship M2a) + latency advice + MISS analysis; Section 7 Defer (10 mục v4.0 BLEU/ROUGE, LLM-judge, A/B model, CI auto regression, etc.). `main(argv)` CLI 3 exit code: 0 PASS, 1 FAIL, 2 missing file.
- **eval/tests/test_report.py (257 dòng):** 17 unit test PASS 0.10s — 3 @critical (gate_verdict PASS 0.80 / FAIL borderline 0.70 / FAIL E5 0.50) + 14 standard. Cover boundary exact 0.75 (PASS) + 0.60 (FAIL không E5) + just-below 0.599 (E5); Markdown integrity 7 section header + MISS marker + E5 warning conditional + iterate advice borderline + latency budget pass/fail (p95 480ms vs 1500ms) + header verdict badge ✅/❌ + Exit code; CLI 4 case (main writes file + exit 0 PASS, exit 1 FAIL + TRIGGER E5 trong MD, exit 2 missing file, tự tạo parent dir nested).
- **Regression toàn eval/ 27/27 PASS** trong 0.12s (10 metrics Plan 09-02 + 17 report Plan 09-03), `ruff check eval/` PASS toàn bộ E/W/F/I/N/UP/B/SIM/RUF.

## Task Commits

Each task was committed atomically:

1. **Task 1: Build eval/report.py — generate_eval_md + gate_verdict + main CLI** — `f9f1e48` (feat)
2. **Task 2: Unit test test_report.py — 3 verdict case + Markdown integrity** — `dbd58d1` (test)

## Files Created/Modified

- `Hub_All/eval/report.py` — 360 dòng, export `gate_verdict`/`generate_eval_md`/`main`, threshold constant `GATE_THRESHOLD_PASS=0.75` + `GATE_THRESHOLD_E5_STOP=0.60`, 7 section helper `_section_setup/_section_metrics/_section_per_query/_section_latency/_section_conclusion/_section_recommendations/_section_defer`, helper `_truncate(s, n)` cho table cell.
- `Hub_All/eval/tests/test_report.py` — 257 dòng, 17 test (3 @critical marker), helper `_sample_results(top_3)` build mock dict theo schema Plan 09-04 emit.

## Sample EVAL.md output (top_3=0.83 PASS — visual check)

Generated qua `generate_eval_md(sample)` với mock data:

```markdown
# Eval Report — Phase 9 Quality Gate ≥75% top-3

> **Verdict:** ✅ PASS · top-3 hit rate `0.830` (83.0%) · Exit code `0`

---

## 1. Setup

| Key             | Value                              |
|-----------------|------------------------------------|
| Timestamp       | 2026-05-21T10:00:00Z               |
| Backend URL     | http://localhost:8180              |
| Embedding model | openai/text-embedding-3-large@1536 |
| LLM model       | openai/gpt-4o-mini                 |
| Eval hub ID     | sample-uuid                        |
| Dataset size    | 10                                 |
| Query count     | 12                                 |
| Mock embed      | NO (real LLM gate)                 |

---

## 2. Metrics

| Metric                     |   Score | Percent   |
|----------------------------|---------|-----------|
| Top-1 hit rate             |    0.67 | 67.0%     |
| Top-3 hit rate (GATE)      |    0.83 | 83.0%     |
| Top-5 hit rate             |    0.92 | 92.0%     |
| MRR (Mean Reciprocal Rank) |    0.75 | —         |

**Upload summary:** 8 completed · 2 failed_unsupported (R4 scanned PDF) · 0 failed · 0 timeout

---

## 3. Per-Query Diff

| ID   | Query             | Expected       | Rank   | Top result     |   #Results |
|------|-------------------|----------------|--------|----------------|------------|
| q-01 | DMD T1 tieu chuan | DMD_T1-01.docx | 1      | DMD_T1-01.docx |         10 |
| q-02 | Cau hoi miss      | doc-X.docx     | MISS   | doc-Y.docx     |          5 |
```

Tabulate render `tablefmt='github'` align cột tốt, padding chuẩn, MISS marker rõ ràng cho rank=None.

## pytest output

```
$ cd Hub_All && python -m pytest eval/tests/test_report.py -v --no-header
collected 17 items

eval\tests\test_report.py::test_gate_verdict_pass PASSED                                  [  5%]
eval\tests\test_report.py::test_gate_verdict_fail_borderline PASSED                       [ 11%]
eval\tests\test_report.py::test_gate_verdict_fail_critical_triggers_e5 PASSED             [ 17%]
eval\tests\test_report.py::test_gate_verdict_boundary_pass_exact_075 PASSED               [ 23%]
eval\tests\test_report.py::test_gate_verdict_boundary_e5_exact_060 PASSED                 [ 29%]
eval\tests\test_report.py::test_gate_verdict_just_below_060 PASSED                        [ 35%]
eval\tests\test_report.py::test_generate_eval_md_pass_has_all_sections PASSED             [ 41%]
eval\tests\test_report.py::test_generate_eval_md_fail_e5_warning_appears PASSED           [ 47%]
eval\tests\test_report.py::test_generate_eval_md_fail_borderline_iterate_advice PASSED    [ 52%]
eval\tests\test_report.py::test_generate_eval_md_includes_per_query_miss_marker PASSED    [ 58%]
eval\tests\test_report.py::test_generate_eval_md_latency_budget_check_pass PASSED         [ 64%]
eval\tests\test_report.py::test_generate_eval_md_latency_budget_check_fail PASSED         [ 70%]
eval\tests\test_report.py::test_generate_eval_md_header_verdict_badge PASSED              [ 76%]
eval\tests\test_report.py::test_main_writes_file_and_exits_zero_on_pass PASSED            [ 82%]
eval\tests\test_report.py::test_main_exits_one_on_fail PASSED                             [ 88%]
eval\tests\test_report.py::test_main_missing_results_returns_2 PASSED                     [ 94%]
eval\tests\test_report.py::test_main_creates_output_parent_dir PASSED                     [100%]

============================== 17 passed in 0.10s ===============================

$ python -m pytest eval/tests/test_report.py -m critical -v --no-header
collected 17 items / 14 deselected / 3 selected

eval\tests\test_report.py::test_gate_verdict_pass PASSED                       [ 33%]
eval\tests\test_report.py::test_gate_verdict_fail_borderline PASSED            [ 66%]
eval\tests\test_report.py::test_gate_verdict_fail_critical_triggers_e5 PASSED  [100%]

====================== 3 passed, 14 deselected in 0.04s ========================

$ python -m pytest eval/tests/ -v --no-header  # regression toàn eval/
collected 27 items
... (10 test_metrics + 17 test_report)
============================== 27 passed in 0.12s ==============================

$ ruff check eval/
All checks passed!
```

## Verdict logic verify khớp ROADMAP + PROJECT.md

| top_3 | verdict | exit_code | trigger_e5 | Hành động |
|-------|---------|-----------|------------|-----------|
| 0.80 | PASS | 0 | False | Ship M2 — Phase 10 hardening |
| 0.75 (boundary) | PASS | 0 | False | Ship M2 — gate đạt vừa đúng |
| 0.70 | FAIL | 1 | False | Iterate chunker/prompt 3 vòng (PROJECT EXIT) |
| 0.60 (boundary) | FAIL | 1 | False | Iterate chunker/prompt 3 vòng |
| 0.599 (just below) | FAIL | 1 | True | TRIGGER E5 — STOP M2b ship M2a standalone |
| 0.50 | FAIL | 1 | True | TRIGGER E5 — STOP M2b ship M2a standalone |

Khớp PROJECT.md EXIT criteria E5: "Quality gate Phase 9 fail (<60% top-3) DÙ đã iterate 3 vòng chunker/prompt → Stop M2b, ship M2a standalone, discuss reranker / hybrid BM25 cho v3.0".

## Lines of code

| File | Lines | Threshold | Status |
|------|-------|-----------|--------|
| `eval/report.py` | 360 | ≥180 | ✅ +100% |
| `eval/tests/test_report.py` | 257 | (17 test) | ✅ |

## Decisions Made

- **D-09-03-A: gate_verdict trả dict 3 field thay vì tuple `[str, int]`** — plan ban đầu spec tuple đơn giản, nhưng cần thêm `trigger_e5` cho cảnh báo CLI khi <0.60. Dict cho phép extension không vỡ caller signature; Plan 09-04 orchestrator chỉ đọc các key cần thiết, fwd-compatible nếu thêm field metadata tương lai.
- **D-09-03-B: Threshold constant module-level** `GATE_THRESHOLD_PASS=0.75` + `GATE_THRESHOLD_E5_STOP=0.60` thay vì hardcode literal — self-document constraint từ PROJECT.md + ROADMAP, cho phép test override khi cần regression check threshold khác.
- **D-09-03-C: CLI default paths `eval/results.json` + `eval/EVAL.md` relative** — chạy từ `Hub_All/` root. Plan 09-04 gọi `main([results_path, output_path])` tường minh, CLI default chỉ phục vụ dev convenience `python -m eval.report`.
- **D-09-03-D: Exit code 2 (missing file) KHÔNG raise** — pattern Unix utility tri-state (0 OK, 1 logic-fail, 2 usage-error). Caller propagate natural qua `python -m eval.report || exit $?`.
- **D-09-03-E: EVAL.md sinh DÙ FAIL** — chứa debug data per-query Section 3 + miss analysis Section 6, quan trọng cho iterate chunker/prompt 3 vòng theo PROJECT EXIT. KHÔNG skip generation khi gate FAIL — chính tay debug data này là input cho vòng iterate tiếp.
- **D-09-03-F: Đổi 3 ký tự EN DASH `–` → HYPHEN-MINUS `-`** trong comment + string để qua ruff RUF001/003 (ambiguous unicode). Tiếng Việt thường dùng EN DASH cho range số (0.60-0.75 / 100-150 ms), nhưng ruff RUF lint mặc định reject. Đổi ASCII dash đảm bảo lint sạch — không thay đổi semantic, chỉ thay glyph representation.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Sửa 3 ký tự EN DASH `–` thành HYPHEN-MINUS `-` trong report.py**

- **Found during:** Task 1 verify (`ruff check eval/report.py`)
- **Issue:** Plan template dùng EN DASH (`–`) ở 3 vị trí — 1 comment + 2 string literal:
  - `# FAIL borderline 0.60–0.75` (line 217)
  - `"- ⚠️ FAIL borderline (60–75% top-3) — iterate..."` (line 219)
  - `"  - Re-tune SET hnsw.ef_search xuống 100–150..."` (line 233)
- Ruff RUF001/003 cảnh báo ambiguous unicode (EN DASH có thể nhầm với HYPHEN-MINUS).
- **Fix:** Đổi `0.60–0.75` → `0.60-0.75`, `60–75%` → `60-75%`, `100–150` → `100-150`. Giữ nguyên EM DASH `—` (cấu trúc câu tiếng Việt — không vi phạm ruff).
- **Files modified:** `Hub_All/eval/report.py` (3 vị trí)
- **Verification:** `ruff check eval/report.py` PASS sau fix.
- **Commit:** `f9f1e48` (fix gộp trong commit Task 1 vì phát hiện ngay trước commit).

**2. [Rule 3 - Blocking] Ruff I001 auto-fix import order test_report.py**

- **Found during:** Task 2 verify (`ruff check eval/tests/test_report.py`)
- **Issue:** Import order chưa chuẩn (`from eval.report import gate_verdict, generate_eval_md, main` cần sắp theo alphabet).
- **Fix:** `ruff check eval/tests/test_report.py --fix` auto-sort import.
- **Files modified:** `Hub_All/eval/tests/test_report.py` (block import)
- **Verification:** Re-run pytest 17/17 PASS không đổi behavior, ruff PASS.
- **Commit:** `dbd58d1` (fix gộp trong commit Task 2).

---

**Total deviations:** 2 auto-fixed (Rule 3 ×2 — blocking lint)
**Impact on plan:** 0 architectural change. Cả 2 deviation là sửa Unicode/format để qua lint, KHÔNG đụng logic. Plan executed gần sát spec.

## Issues Encountered

- **Windows console cp1252 encoding KHÔNG render được ký tự `≥` `≤` `✅` `❌`** (cosmetic, không block) — khi dev preview EVAL.md qua `python -c "print(generate_eval_md(...))"`. Workaround: `sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')`. Plan 09-04 ghi qua file (UTF-8 explicit) nên không vướng. README Plan 09-04 sẽ document chạy `chcp 65001` trên Windows trước khi `cat eval/EVAL.md`.
- **Windows CRLF warning git** (cosmetic, không block) — git warning `LF will be replaced by CRLF` khi `git add` từ Windows. KHÔNG ảnh hưởng nội dung; commit thành công bình thường.

## User Setup Required

None — Plan 09-03 hoàn toàn local file ops + pytest, không có external service config.

(Plan 09-04..05 tiếp theo sẽ cần stack chạy thật + `OPENAI_API_KEY` paid tier cho gate verdict — sẽ được document khi tới đó.)

## Next Phase Readiness

- ✅ **Plan 09-04 (run_eval.py orchestrator — Wave 3):** Sẵn sàng — `from eval.report import generate_eval_md, gate_verdict, main` import được; CLI standalone re-generate EVAL.md từ results.json đã có (`python -m eval.report results.json EVAL.md`).
- ✅ **Plan 09-04 + 09-05:** Threshold + verdict logic stable — KHÔNG cần đổi khi run gate thật. Chỉ cần Plan 09-04 emit `eval/results.json` đúng schema (run_metadata + upload_summary + retrieval_metrics + latency) thì report.py render đẹp ngay.
- ⚠️ **Plan 09-05 (gate run thật — Wave 4):** Cần `OPENAI_API_KEY` paid tier + stack chạy thật (postgres + redis + uvicorn + cocoindex flow + ingest 10 file). Đây là Wave 4 plan thực thi cuối cùng Phase 9.

## Self-Check: PASSED

Verify claims:

**Files exist:**
- ✅ `Hub_All/eval/report.py` — FOUND (360 dòng)
- ✅ `Hub_All/eval/tests/test_report.py` — FOUND (257 dòng)

**Commits exist (git log):**
- ✅ `f9f1e48` — FOUND (feat 09-03 Task 1 report.py)
- ✅ `dbd58d1` — FOUND (test 09-03 Task 2 test_report.py)

**Acceptance criteria Plan 09-03:**
- ✅ `eval/report.py` ≥ 180 dòng (360 actual), ruff PASS, exports `generate_eval_md` + `gate_verdict` + `main`.
- ✅ `gate_verdict(0.80)={PASS,0,False}`, `gate_verdict(0.70)={FAIL,1,False}`, `gate_verdict(0.50)={FAIL,1,True}` — khớp ROADMAP + PROJECT EXIT E5.
- ✅ EVAL.md 7 section render qua `tabulate(tablefmt='github')`: Setup / Metrics / Per-Query Diff / Latency / Conclusion / Recommendations / Defer.
- ✅ Recommendations conditional 3 nhánh (PASS / FAIL borderline / FAIL E5 STOP M2b).
- ✅ EVAL.md sinh DÙ FAIL — debug data per-query + latency + miss analysis.
- ✅ CLI `python -m eval.report` 3 exit code (0 PASS / 1 FAIL / 2 missing file).
- ✅ pytest 17/17 PASS trong 0.10s (3 @critical + 14 standard); regression toàn eval/ 27/27 PASS trong 0.12s.
- ✅ KHÔNG depend `eval/lib.py` — Plan 09-03 parallel với Plan 09-02.

---
*Phase: 09-eval-framework-quality-gate*
*Completed: 2026-05-21*
