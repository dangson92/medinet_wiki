# CHECK Phase 5 Eval Compare Quality Gate

**Ngay check:** 2026-04-29  
**Checker:** gsd-plan-checker  
**Verdict:** **PASS** (3 warning minor, khong block execute)

---

## Tom tat dimensions

| Dimension | Ket qua |
|---|---|
| 1. Requirement Coverage | PASS — 4/4 EVAL-02..05 co plan cover |
| 2. Task Completeness | PASS — moi task co files/action/verify/done |
| 3. Dependency Correctness | PASS — DAG hop le, khong cycle |
| 4. Key Links Planned | PASS — lib.py imported day du, subprocess wiring ro |
| 5. Scope Sanity | PASS — 1-3 task/plan, files modified <= 3 |
| 6. must_haves Derivation | PASS — truths user-observable, artifacts co min_lines |
| 7. Context Compliance | PASS — 9 decision A-I cua CONTEXT deu duoc implement |
| 7b. Scope Reduction | PASS — KHONG co v1/v2/simplified/static for now |
| 7c. Architectural Tier | SKIPPED — Phase 5 la eval scripts |
| 8. Nyquist Compliance | SKIPPED — khong co VALIDATION.md |
| 9. Cross-Plan Data Contracts | PASS — 4 JSON intermediate co schema chot cung |
| 10. CLAUDE.md Compliance | PASS |
| 11. Research Resolution | SKIPPED |
| 12. Pattern Compliance | SKIPPED |

---

## Tra loi 10 cau hoi check cua user

### 1. 4/4 REQ-ID covered (EVAL-02..05)?

PASS. Mapping:

| REQ-ID | Plan | Frontmatter requirements |
|---|---|---|
| EVAL-02 | 05-02 | [EVAL-02] |
| EVAL-03 | 05-03 | [EVAL-03] |
| EVAL-04 | 05-04 | [EVAL-04] |
| EVAL-05 | 05-05 | [EVAL-05] |
| (foundation) | 05-01 | [] (DUNG — lib.py + run_docling.py la enabler) |

Plan 05-01 co requirements: [] dung — no la foundation cho 02..05, khong bind REQ chinh thuc. CONTEXT muc Implementation Tasks > Plan 05-01 ghi ro: REQ foundation cho Plan 02-04.

### 2. Wave parallel safe (Plan 05-02 + 05-03 file conflict?)

PASS. Ca 2 o Wave 2:
- Plan 05-02 chi ghi eval/run_extraction_compare.py
- Plan 05-03 chi ghi eval/run_retrieval_eval.py
- Ca 2 chi READ snapshot baseline_*.json (immutable)
- Output JSON khac ten (extraction_compare.json vs retrieval_eval.json) -> KHONG conflict
- Ca 2 depends_on: [05-01] -> thu tu dung

Parallel-safe hoan toan.

### 3. lib.py interface day du cho 4 plan downstream?

PASS voi 1 warning minor (W1). Interface contract Plan 05-01 expose:
- APIClient (login, get_hub_id, upload_and_wait, search, get_rag_config, put_rag_config, reindex)
- preflight(), get_embedder_config(), assert_embedder_match(), upload_dataset(), evaluate_queries()
- Dataclass DocResult, QueryResult, RetrievalMetrics

W1: Plan 05-02 va 05-03 KHONG from lib import gi ca — chung chi doc snapshot JSON + query Postgres. Dieu nay thuc ra DUNG (doc lap voi API client) nhung co the bi hieu lam. De xuat nhe: Plan 05-02 co the tan dung helper psycopg connection tu lib.preflight(). Khong block.

### 4. run_docling.py switch mode + restore safely (try/finally)?

PASS. Plan 05-01 Task 3 spec ro try/finally pattern:
- try: get_hub_id -> upload_dataset -> evaluate_queries
- finally: client.put_rag_config({extractor_mode: auto}) + log loud

Restore guarantee ke ca khi exception. Dap ung CONTEXT muc D Restore mode sau run.

### 5. Embedder lock verify thuc su fail loud (exit code != 0)?

PASS. Plan 05-01 Task 1 spec assert_embedder_match: Mismatch -> raise SystemExit(EMBEDDER LOCK FAIL: ...). SystemExit voi message string -> exit code 1 (Python default). Dap ung CONTEXT muc B fairness gate tuyet doi.

### 6. Heading recall query DB direct co cover edge case?

PARTIAL PASS — Warning W2. Plan 05-02 Task 1 step 4 cover:
- Whitespace normalization (regex \s+ -> single space)
- Case insensitive (.lower())
- Substring loose match

Edge case CHUA spec ro:
- Accent comparison (tieng Viet PHAN vs PHAN do OCR sai dau) — KHONG dung unicodedata.normalize(NFD) de strip accent. Neu Docling OCR vie chinh xac thi OK; neu lech dau se false negative. Mitigation: EVAL.md Conclusion se surface cac case nay (CONTEXT Rui ro 4).
- Markdown formatting trong chunks (**PHAN 1**) — substring match VAN OK (substring phan 1 co trong **phan 1**). Khong phai bug.

### 7. EVAL.md template du 7 section?

PASS. Plan 05-04 Task 1 step 6 du 7 section khop CONTEXT muc F:
1. Setup (bullet)
2. Retrieval Comparison (tabulate github)
3. Per-Query Diff (tabulate)
4. Per-Document Extraction Quality (tabulate)
5. Smoke Verification (placeholder, Plan 05-05 update sau)
6. Conclusion (text + 3 recommendation neu FAIL)
7. Defer for M2/M3

Plus header Verdict PASS/FAIL + Reason ngay dau. Day du.

### 8. Quality gate exit code logic dung (PASS=0, FAIL=1)?

PASS. Plan 05-04 Task 1 step 11: sys.exit(0 if verdict == PASS else 1). Khop CONTEXT muc E.

Step 12 quan trong: EVAL.md VAN duoc sinh du FAIL — khong skip ghi file, chi exit 1. Dap ung CONTEXT muc E exact: EVAL.md van duoc sinh du FAIL — chua so lieu de debug.

### 9. Makefile targets co depend chain dung?

PASS. Plan 05-05 Task 1 spec 4 target:
- eval-smoke (standalone, khong depend)
- eval-baseline-docling (standalone, goi run_docling.py)
- eval-compare (standalone, goi run_compare.py — internally subprocess 05-02 + 05-03)
- eval-all: eval-baseline-docling eval-compare (DUNG depend chain)

eval-all depend dung thu tu: snapshot Docling truoc (sinh baseline_docling.json), roi compare (can file do). Khop CONTEXT muc G.

eval-compare khong depend eval-baseline-docling rieng — co y cho user tai chay compare khi da co snapshot ma khong phai re-ingest 30-60 phut. Dung UX.

### 10. Smoke is_table=true assert dung schema metadata (Phase 4 CFG-06)?

PASS voi 1 warning minor (W3). Plan 05-05 Task 1 logic:
- results = c.search(hub, ..., top_k=5)
- has_table = any((r.get(metadata) or {}).get(is_table) for r in results)
- assert has_table

Cover dung: guard metadata null, khong KeyError, any() chi can >= 1 chunk.

W3: is_table co the la bool true, hoac string true (tuy ChromaDB metadata serialization). DSVC-02 spec is_table (bool) o Python service nhung khi qua HTTP -> Go -> ChromaDB. Neu Go layer convert sang string false thi any(...) van truthy voi non-empty string -> false positive. De xuat tighten:

  has_table = any((r.get(metadata) or {}).get(is_table) in (True, true, 1) for r in results)

Khong block PASS — Phase 4 WIRE-03 (chunks metadata mapping) co the da chuan hoa thanh bool. Smoke runtime se phat hien neu lech.

CFG-06 thuc ra la extractor_used per-document — Plan 05-05 cung assert doc.get(extractor_used) == docling — DUNG khop CFG-06.

---

## Cross-Plan Data Contract Check

| Producer | Consumer | Artifact | Schema khop? |
|---|---|---|---|
| 05-01 run_docling.py | 05-02, 05-03 | eval/baseline_docling.json | OK identical schema baseline_native.json + extractor_used |
| 05-02 | 05-04 | eval/extraction_compare.json | OK schema chot cung |
| 05-03 | 05-04 | eval/retrieval_eval.json | OK schema chot cung |
| 05-04 | 05-05 | eval/EVAL.md | OK template 7 section CONTEXT muc F |
| 05-01 (lib.py) | 05-05 (Makefile inline) | APIClient + preflight | OK import path eval/lib.py |

KHONG co conflict transformation. Snapshot Phase 1 immutable duoc ton trong (KHONG sua baseline_native.json hay baseline.py).

---

## CONTEXT.md Decisions Compliance

| Decision | Plan implement | Trang thai |
|---|---|---|
| A. Cau truc thu muc eval/ mo rong | 05-01..05 | OK tat ca file moi khop listing |
| B. Snapshot schema baseline_docling.json | 05-01 Task 3 step 8 | OK identical + extractor_used |
| C. Refactor extract eval/lib.py | 05-01 Task 1 | OK khong sua baseline.py, lib.py expose du |
| D. Run mode comparison strategy | 05-01 Task 3 (try/finally) + 05-04 | OK |
| E. Quality gate logic | 05-04 Task 1 step 5 + 11 | OK exact match function signature |
| F. EVAL.md report structure | 05-04 Task 1 step 6 | OK 7 section du |
| G. Makefile targets | 05-05 Task 1 | OK 4 target khop |
| H. Out of Scope | (KHONG plan nao violation) | OK khong A/B embedding, stats sig, CI auto, dashboard, reranker |
| I. Dependencies | 05-01 Task 2 (tabulate>=0.9) | OK |

100% decision coverage. KHONG co decision nao bi silently dropped hay scope-reduced.

---

## Scope Reduction Detection (Dimension 7b)

Quet toan bo 5 plan tim signal scope reduction:
- KHONG co v1, v2, simplified, static for now, hardcoded
- KHONG co future enhancement, placeholder (tru section 5 EVAL.md placeholder cho smoke runtime — design intent, khong phai reduction)
- KHONG co minimal, skip for now, stub
- defer cho user xuat hien nhieu — nhung day la runtime_smoke deferred da duoc CONTEXT chap nhan chinh thuc (Rui ro 1: Docling runtime can Phase 2-4 ship). Code 100% duoc commit, chi runtime execution defer cho user vi can infrastructure thật.

KHONG co scope reduction.

---

## Issues Summary

### Blockers (must fix truoc execute)

Khong co.

### Warnings (should consider, khong block execute)

W1. [key_links_planned] Plan 05-02 + 05-03 khong import lib.py — co the tan dung psycopg helper. Refactor optimization.

W2. [task_completeness] Plan 05-02 heading recall match khong cover accent-strip edge case (Vietnamese OCR sai dau). Mitigation: EVAL.md Conclusion se surface case nay.

W3. [task_completeness] Plan 05-05 smoke is_table assert dung truthy loose — neu ChromaDB metadata serialize thanh string false se false positive. De xuat tighten in (True, true, 1).

### Info (suggestions)

- Plan 05-04 EVAL.md template Section 5 Smoke Verification de placeholder — Plan 05-05 KHONG co task explicit update Section 5 sau khi smoke chay. User co the manually update hoac Plan 05-04 doc 1 file eval/.last_smoke.txt (timestamp + status). Defer optimization.

---

## Final Verdict

PASS — san sang execute.

5 plan Phase 5 cover day du 4 REQ-ID (EVAL-02..05), 100% CONTEXT decisions implement, dependency DAG dung (Wave 1: 05-01 -> Wave 2: 05-02 + 05-03 -> Wave 3: 05-04 -> Wave 4: 05-05), schema cross-plan tuong thich, KHONG scope reduction, KHONG cycle, scope nho (1-3 task/plan, 1-3 file/plan).

3 warning deu la minor optimization, co the fix incrementally sau khi runtime chay thuc te o user side. Khong can revise loop.

Khuyen nghi tiep theo: chay /gsd-execute-phase 5 — executor commit code 5 plan, runtime smoke + EVAL.md sinh defer cho user (can Docling service real tu Phase 2-4 da ship).

---

*File: .planning/phases/05-eval-compare-quality-gate/05-CHECK.md*  
*Generated: 2026-04-29 by gsd-plan-checker (auto mode)*

