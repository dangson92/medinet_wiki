---
phase: 05-eval-compare-quality-gate
plan: 04
subsystem: eval
status: completed
tags: [eval, orchestrator, quality-gate, eval-md-generator, EVAL-04, milestone-gate]
requirements: [EVAL-04]
dependency_graph:
  requires:
    - eval/baseline_native.json (Phase 1, immutable, 75% top-3 baseline)
    - eval/baseline_docling.json (Plan 05-01 runtime artifact, defer cho user)
    - eval/run_extraction_compare.py (Plan 05-02 — sinh extraction_compare.json)
    - eval/run_retrieval_eval.py (Plan 05-03 — sinh retrieval_eval.json)
  provides:
    - eval/run_compare.py — script orchestrator + quality gate + EVAL.md generator
    - eval/EVAL.md schema (7 section, sản phẩm cuối M1)
    - evaluate_gate() public function (Plan 05-05 có thể import nếu cần)
  affects:
    - Plan 05-05 (Makefile + README) — sẽ thêm target `eval-compare` gọi script này + cập nhật section 5 EVAL.md sau khi smoke
tech_stack:
  added: []
  patterns:
    - "Subprocess orchestrate (sys.executable + cwd=REPO_ROOT) — chạy 2 script intermediate sequential, fail-loud non-zero exit"
    - "Tabulate optional fallback render Markdown thuần Python (đồng bộ Plan 05-02/03 — không block runtime khi tabulate chưa cài)"
    - "EVAL.md vẫn sinh dù FAIL — chứa số liệu debug + verdict + reason header rõ ràng"
    - "Quality gate 2-điều-kiện OR: delta ≥ +15pp HOẶC absolute ≥ 75% (CONTEXT 05 mục E)"
    - "Section 6 Conclusion phân nhánh PASS/FAIL với 3 hướng recommend khi FAIL (reranker / hybrid retrieval / data improvement — đồng bộ CONTEXT Rủi ro 4)"
    - "Section 7 Defer auto-extract query verdict REGRESSED + both_miss để debug priority"
key_files:
  created:
    - eval/run_compare.py (685 dòng)
  modified: []
decisions:
  - "Tabulate optional với fallback Python pure — đồng bộ pattern Plan 05-02/03, không break smoke khi env chưa pip install"
  - "Granular skip flag: --skip-subprocess (skip cả 2) + --skip-extraction + --skip-retrieval (control riêng) — Plan 05-05 Makefile có thể chain target linh hoạt"
  - "Section 1 Setup parse run_id thành YYYY-MM-DD thay vì giữ ISO timestamp đầy đủ — đọc dễ trong Markdown"
  - "Section 4 cell format 'N/total -> N/total' cho tables_preserved (vd '3/4 -> 4/4') — show numerator + denominator để audit-friendly"
  - "Section 6 Conclusion FAIL case liệt kê 3 hướng cụ thể từ CONTEXT Rủi ro 4 — không bỏ user trống tay nếu gate fail"
  - "Section 7 auto-extract query REGRESSED + both_miss list — không phải hardcode, đảm bảo defer section luôn cập nhật theo dữ liệu thực"
  - "_short_filename(38) helper cắt filename dài để bảng Markdown không bị wrap xấu trên GitHub render"
metrics:
  duration_minutes: 20
  completed_date: "2026-04-29"
  tasks_completed: 1
  files_changed: 1
  lines_added: 685
commit: b0de521
---

# Phase 5 Plan 04: `run_compare.py` Orchestrator + Quality Gate + EVAL.md Generator (EVAL-04) Summary

Script `eval/run_compare.py` là **gate cứng cuối cùng của milestone M1 — RAG Quality with Docling**. Orchestrate Plan 05-02 + 05-03 qua subprocess → load 4 JSON (2 snapshot + 2 intermediate) → apply quality gate (`delta_top3 ≥ +15pp HOẶC docling_top3 ≥ 75%`) → sinh `eval/EVAL.md` 7 section (Setup / Retrieval / Per-Query / Per-Doc / Smoke / Conclusion / Defer) → exit 0 (PASS) hoặc 1 (FAIL). EVAL.md vẫn được sinh dù FAIL, chứa đủ số liệu để debug + recommend 3 hướng (reranker / hybrid retrieval / data improvement).

---

## 1. Tóm tắt thực thi

**Mode:** YOLO autonomous · **Wave:** 3 · **Tasks:** 1/1 PASS · **Commit:** `b0de521`.

| Task | Output | Lines | Verify |
|---|---|---|---|
| 1. Tạo `eval/run_compare.py` | argparse + pre-condition + subprocess orchestrate + load 4 JSON + evaluate_gate + 7-section EVAL.md generator + exit 0/1 | 685 | `ast.parse` OK + gate 7/7 unit case + E2E PASS + E2E FAIL + pre-condition fail-loud |

**Runtime real:** Defer cho user — cần `eval/baseline_docling.json` thực tế (Docling sidecar chạy thật) + `eval/extraction_compare.json` runtime (Postgres có chunks Docling đã ingest). Smoke giả lập đã chứng minh logic + EVAL.md generator hoạt động đúng.

---

## 2. Quality Gate Logic (CONTEXT 05 mục E)

```python
def evaluate_gate(native_top3: float, docling_top3: float) -> tuple[str, str]:
    delta = docling_top3 - native_top3
    if delta >= 0.15:
        return "PASS", f"top-3 cải thiện {delta*100:+.1f}pp (...)"
    if docling_top3 >= 0.75:
        return "PASS", f"top-3 đạt {docling_top3*100:.1f}% (≥75% tuyệt đối, dù delta {delta*100:+.1f}pp)"
    return "FAIL", f"top-3 chỉ {docling_top3*100:.1f}%, delta {delta*100:+.1f}pp — chưa đạt gate ≥+15pp HOẶC ≥75%"
```

**Threshold module-level:** `GATE_DELTA_THRESHOLD = 0.15`, `GATE_ABSOLUTE_THRESHOLD = 0.75` — dễ chỉnh nếu Phase 6 cần stricter/looser.

**Gate priority:** delta-rule kiểm tra **TRƯỚC** absolute-rule. Khi cả 2 cùng thoả (vd native=30%, docling=80%), reason ưu tiên show delta vì là tín hiệu mạnh hơn cho improvement.

---

## 3. EVAL.md Template — 7 Section

Đúng spec CONTEXT 05 mục F:

| # | Section | Render |
|---|---|---|
| 1 | Setup | Bullet list: dataset, queries, embedder (provider/model/dim), native run date, docling run date, min_score |
| 2 | Retrieval Comparison | Markdown table 4 row (top-1/3/5/MRR) × 4 col (Metric/Native/Docling/Delta) + counts line (FIXED/REGRESSED/IMPROVED/WORSE/unchanged/both_miss) |
| 3 | Per-Query Diff | Markdown table 5 col (Q/Expected/Native rank/Docling rank/Verdict) — 12 row |
| 4 | Per-Document Extraction Quality | Markdown table 5 col (Doc/Native chunks/Docling chunks/Heading recall N→D/Table preservation N→D) + aggregate line |
| 5 | Smoke Verification | Placeholder "deferred — Plan 05-05 sẽ thêm Makefile" |
| 6 | Conclusion | Phân nhánh PASS (khen + recommend promote production) hoặc FAIL (3 hướng: reranker / hybrid / data improvement) |
| 7 | Defer for M2/M3 | 3 deferred ideas (999.13/14/15 từ CONTEXT) + auto-extract query REGRESSED/both_miss |

**Header:** `# EVAL — M1 RAG Quality with Docling` + `**Ngày chạy:** YYYY-MM-DD` + `**Verdict:** PASS|FAIL` + `**Reason:** <gate reason>`.

**Footer:** `_Generated by eval/run_compare.py at <ISO timestamp> UTC._`

---

## 4. Verify Checklist

### Automated (PASSED)

```
$ python -c "import ast; ast.parse(open('eval/run_compare.py', encoding='utf-8').read()); print('parse OK')"
parse OK

$ wc -l eval/run_compare.py
685

$ # gate logic 7 unit case
$ python -c "from run_compare import evaluate_gate; ..."
[OK] native=0.50 docling=0.70 => PASS (delta +20pp)
[OK] native=0.50 docling=0.65 => PASS (delta +15pp boundary)
[OK] native=0.50 docling=0.64 => FAIL (delta +14pp dưới boundary, abs <75%)
[OK] native=0.75 docling=0.75 => PASS (tuyệt đối 75% boundary, delta 0)
[OK] native=0.80 docling=0.50 => FAIL (docling regress, abs <75%)
[OK] native=0.30 docling=0.80 => PASS (cả 2 thoả)
[OK] native=0.74 docling=0.74 => FAIL (cả 2 dưới 75%, delta 0)
Gate tests: PASS
```

### E2E Smoke (PASSED)

**Smoke 1 — docling = native (cùng baseline):**

```
QUALITY GATE: PASS
Reason: top-3 đạt 75.0% (≥75% tuyệt đối, dù delta +0.0pp)
  native_top3  = 0.7500
  docling_top3 = 0.7500
  delta        = +0.0000 (+0.0pp)
EVAL.md ghi: /tmp/EVAL_smoke.md (4143 ký tự)
Exit code: 0 (PASS)
```

Đúng dự đoán task user: docling=native → top-3=75% → ≥75% tuyệt đối → PASS soft (dù delta=0pp).

**Smoke 2 — docling top-3 = 50% (FAIL case):**

```
QUALITY GATE: FAIL
Reason: top-3 chỉ 50.0%, delta -25.0pp — chưa đạt gate ≥+15pp HOẶC ≥75%
  native_top3  = 0.7500
  docling_top3 = 0.5000
  delta        = -0.2500 (-25.0pp)
EVAL.md ghi: /tmp/EVAL_fail.md (4384 ký tự)  ← VẪN sinh dù FAIL
Exit code: 1 (FAIL)
```

EVAL.md vẫn được sinh đầy đủ 7 section dù FAIL — đáp ứng CONTEXT 05 mục E "EVAL.md vẫn được sinh dù FAIL — chứa số liệu để debug".

**Smoke 3 — pre-condition fail-loud (thiếu docling snapshot):**

```
[FATAL] Thiếu snapshot bắt buộc: C:\nonexistent.json
Hint: chạy `python eval/run_docling.py` trước để sinh baseline_docling.json
Hoặc đảm bảo eval/baseline_native.json tồn tại (Phase 1 commit f37cd96)
```

Exit 1 + hint cụ thể (đáp ứng task spec "fail loud + hint chạy run_docling.py").

### Section structure (PASSED)

```
$ grep -E "^## " /tmp/EVAL_smoke.md
## 1. Setup
## 2. Retrieval Comparison
## 3. Per-Query Diff
## 4. Per-Document Extraction Quality
## 5. Smoke Verification
## 6. Conclusion
## 7. Defer for M2/M3
```

Đúng 7 section CONTEXT 05 mục F.

### Tabulate optional (PASSED)

Env hiện tại chưa `pip install tabulate` (mới add vào pyproject Plan 05-01, chưa runtime install). Script log warning + fallback Markdown table thuần Python — render OK trên GitHub:

```
| Metric | Native | Docling | Delta |
| --- | --- | --- | --- |
| top-1 | 75.0% | 75.0% | +0.0 pp |
```

Khi user `cd eval && pip install -e .` cài tabulate, script sẽ tự dùng `tabulate(tablefmt="github")` — output identical (chỉ khác cosmetic alignment).

### Runtime real (DEFERRED)

Cần `baseline_docling.json` từ Docling sidecar real → defer Plan 05-05 hoặc `/gsd-verify-work 5`.

---

## 5. Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Tabulate runtime fallback]** Tabulate chưa cài trong env Python toàn cục (mới add `tabulate>=0.9` vào `eval/pyproject.toml` Plan 05-01 nhưng chưa `pip install -e eval/`). Đồng bộ pattern Plan 05-02 + 05-03: try/except ImportError với 2 phiên bản `render_markdown_table` — output Markdown identical. **Files modified:** `eval/run_compare.py:74-92`. KHÔNG block smoke.

**2. [Rule 2 — Granular skip flag]** PLAN.md chỉ đề cập `--skip-subprocess` (boolean). Tôi thêm `--skip-extraction` + `--skip-retrieval` riêng để Plan 05-05 Makefile có thể chain `eval-baseline-docling → eval-compare --skip-extraction` linh hoạt khi user đã chạy thủ công 1 script. KHÔNG break interface đã chốt.

### Spec đồng bộ

| Quyết định bổ sung | Lý do |
|---|---|
| Format date `YYYY-MM-DD` thay vì ISO timestamp đầy đủ | Header EVAL.md đọc dễ hơn, audit log đã có run_id đầy đủ trong intermediate JSON |
| `_short_filename(38)` helper | Filename DMD dài (~50 char), bảng Markdown trên GitHub bị wrap xấu nếu không cắt |
| Section 7 auto-extract REGRESSED + both_miss | Defer section luôn cập nhật theo dữ liệu thực thay vì hardcode — debug priority list real-time |
| Counts line section 2 | Show 6 verdict count cùng lúc với metric table — debug nhanh không cần scroll xuống section 3 |
| Conclusion FAIL liệt kê 3 hướng cụ thể CONTEXT Rủi ro 4 | Không bỏ user trống tay khi gate fail — họ biết next step ngay |

---

## 6. Threat Model Compliance

| Threat ID | Mitigation Applied | Where |
|---|---|---|
| T-05-08 (Tampering EVAL.md edit thủ công sau commit) | Accept — gate enforce qua exit code 0/1 từ script (CI), git history audit từng commit. EVAL.md có footer timestamp + commit hash trong git diff đủ traceability | Documented |
| T-05-09 (Repudiation verdict không có chữ ký) | Accept — `run_id` UTC + commit hash trong `git log` + footer `_Generated by eval/run_compare.py at <ISO> UTC._` đủ truy vết | `build_eval_md` footer |

---

## 7. Files Manifest

**Created:**
- `eval/run_compare.py` (685 dòng) — orchestrator + gate + EVAL.md generator

**Untouched:**
- `eval/baseline_native.json` (Phase 1 immutable)
- `eval/baseline_docling.json` (Plan 05-01 runtime artifact — chưa tồn tại runtime)
- `eval/run_extraction_compare.py` + `eval/run_retrieval_eval.py` (Plan 05-02/03)
- `eval/lib.py` (Plan 05-01 — không cần import vì run_compare.py orchestrate qua subprocess)

---

## 8. Verification Checklist

- [x] `python -c "import ast; ast.parse(open('eval/run_compare.py', encoding='utf-8').read())"` → `parse OK`
- [x] `wc -l eval/run_compare.py` = 685 dòng (≥ 250 yêu cầu)
- [x] `evaluate_gate()` 7/7 unit case PASS (delta boundary +15pp, absolute boundary 75%, FAIL cases, cross-thoả)
- [x] E2E smoke docling=native → PASS reason "≥75% tuyệt đối" + exit 0 + EVAL.md 4143 chars
- [x] E2E smoke docling top-3=50% → FAIL exit 1 + EVAL.md 4384 chars (vẫn sinh)
- [x] Pre-condition fail-loud thiếu snapshot → [FATAL] log + hint cụ thể
- [x] EVAL.md có đủ 7 section (`grep -E "^## "` thấy section 1..7)
- [x] Header có `**Ngày chạy:**` + `**Verdict:**` + `**Reason:**`
- [x] Tabulate optional fallback render OK (env hiện tại chưa cài tabulate)
- [x] CLI default args (`--native-snapshot`, `--docling-snapshot`, `--out`, `--skip-subprocess`) — gọi không tham số chạy được
- [x] Single atomic commit `b0de521`
- [x] Stage file riêng (`git add eval/run_compare.py`)
- [ ] Runtime real EVAL.md (Docling sidecar) — **DEFERRED** Plan 05-05 hoặc `/gsd-verify-work 5`

---

## Self-Check: PASSED

- File `eval/run_compare.py`: FOUND (685 dòng)
- Commit `b0de521`: FOUND in `git log`
- AST parse: OK
- Gate logic 7/7 unit case PASS
- E2E smoke 3 case (PASS / FAIL / pre-condition fail-loud) all PASS

---

## 9. Next Plan

**Plan 05-05** — `make eval-smoke` Makefile + README update + final commit (EVAL-05):

- Thêm Makefile root targets: `eval-smoke`, `eval-baseline-docling`, `eval-compare`, `eval-all`.
- `eval-smoke`: 1-file e2e test verify Docling extractor + has_table chunk indexed (CONTEXT mục G).
- `eval-compare`: gọi `python eval/run_compare.py` (script Plan 05-04 này).
- Update `eval/README.md` với hướng dẫn workflow đầy đủ Phase 5.
- Smoke test code path cuối cùng → đóng Phase 5 + close M1.

*Last updated: 2026-04-29 — Plan 05-04 PASS, commit `b0de521`. Phase 5 progress 4/5 plans.*
