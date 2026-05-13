---
phase: 05-eval-compare-quality-gate
verified: 2026-04-29T00:00:00Z
status: human_needed
score: 4/4 must-haves verified (code-level)
overrides_applied: 0
re_verification: # Initial verification — chưa có VERIFICATION.md trước đó
human_verification:
  - test: "Khởi động full stack (backend Go + Postgres + Redis + ChromaDB + docling-pipeline) → chạy `make eval-all` → review `eval/EVAL.md` verdict"
    expected: "EVAL.md commit với bảng số liệu cụ thể, verdict PASS (top-3 docling ≥75% HOẶC delta ≥+15pp so với baseline native 75%)"
    why_human: "Cần Docling sidecar real (Phase 2 runtime defer — Docker stack user chưa setup được) + 30-60 phút ingest 10 file × 12 query × OpenAI embedding API"
  - test: "Chạy `make eval-smoke` (sau khi stack UP)"
    expected: "Output `SMOKE OK: Docling extractor used + (table chunk indexed HOAC defensive skip)` + exit code 0"
    why_human: "Cần Docling sidecar UP + backend Go UP + admin login thật + upload 1 file end-to-end"
  - test: "Verify `eval/EVAL.md` chứa số liệu cụ thể (không từ định tính chung chung) đủ 7 section sau khi sinh real"
    expected: "Section 1 Setup + 2 Retrieval (4 metric × 4 col) + 3 Per-Query (12 row) + 4 Per-Document + 5 Smoke + 6 Conclusion + 7 Defer — tất cả có số thật, không placeholder"
    why_human: "EVAL.md hiện chưa tồn tại trên disk — chỉ template trong `run_compare.py:build_eval_md()` đã verify code-level (smoke test PASS+FAIL E2E unit), runtime real chờ user"
---

# Phase 5: Eval Compare & Quality Gate — Verification Report

**Phase Goal:** Có báo cáo định lượng `eval/EVAL.md` so sánh extraction + retrieval giữa `RAG_EXTRACTOR=native` và `=docling`; gate milestone PASS khi top-3 hit rate **tăng ≥ 15pp** HOẶC đạt **≥ 75% tuyệt đối**. Smoke test `make eval-smoke` đảm bảo Docling thực sự được dùng.

**Verified:** 2026-04-29
**Status:** human_needed (code 100% PASS, runtime defer cùng Phase 2-4 — cần Docling Docker stack)
**Re-verification:** No — initial verification.

---

## 1. Goal Achievement

### Per Success Criterion (4/4 ROADMAP)

| # | Success Criterion | Status | Evidence (code-level) |
|---|-------------------|--------|------------------------|
| 1 | `python eval/run_extraction_compare.py` chạy hết dataset 2 mode → per-doc metrics (chunks, avg_tokens, heading recall, table preservation) | ✓ VERIFIED | `eval/run_extraction_compare.py` 448 dòng — argparse 5 flag + `strip_accent` NFKD VN + `count_heading_recall` substring loose + `count_tables` defensive bool/string + psycopg DB query + JSON output `extraction_compare.json`. Smoke test 5/5 helper PASS (commit `06b3e19`). |
| 2 | `python eval/run_retrieval_eval.py` 12 query × 2 mode → top-1/3/5 + MRR | ✓ VERIFIED | `eval/run_retrieval_eval.py` 455 dòng — argparse 3 flag + `assert_query_sets_match` hard fail + `classify_verdict` 6 case (FIXED/REGRESSED/IMPROVED/WORSE/unchanged/both_miss) + `RANK_DELTA_THRESHOLD=2` + smoke test docling=native = 9 unchanged + 3 both_miss PASS (commit `b7d2768`). |
| 3 | `eval/EVAL.md` commit với bảng số liệu cụ thể + verdict gate | ✓ VERIFIED (code), ⚠️ HUMAN (runtime artifact) | `eval/run_compare.py:build_eval_md` (line 261/302/333/397/413/467/487 — đủ 7 section markers) + `evaluate_gate` line 159 + `GATE_DELTA_THRESHOLD=0.15` line 73 + `GATE_ABSOLUTE_THRESHOLD=0.75` line 74 + `sys.exit(0 if verdict == "PASS" else 1)` line 679. E2E smoke 2 case PASS (PASS verdict 4143 chars + FAIL verdict 4384 chars vẫn sinh) + gate unit 7/7 (commit `b0de521`). **Runtime EVAL.md chưa tồn tại** trên disk — defer user. |
| 4 | `make eval-smoke` chạy 1 file e2e + assert `is_table=true` | ✓ VERIFIED (code) | `Makefile:48` `eval-smoke` target — Python inline 1453 chars compile() OK: pre-flight → login → upload `DMD_T1-01_DinhVi_TrungTam_v1.docx` timeout 300s → assert `extractor_used=='docling'` (CFG-06) → search → `bool((r.get('metadata') or {}).get('is_table'))` explicit cho ≥1 chunk HOẶC defensive skip (file_has_no_table guard). Env override BACKEND_URL/CHROMA_URL/ADMIN_*/EVAL_HUB_CODE/DB_DSN. Commit `3f54aee`. |

**Score code-level:** 4/4 SC. **Score runtime:** 0/4 SC (defer user — cùng tình trạng Phase 2-4).

---

## 2. Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `eval/lib.py` | Shared module APIClient + helpers | ✓ VERIFIED | 707 dòng — `class APIClient` (line 198) + `preflight` (106) + `get_embedder_config` (440) + `assert_embedder_match` (467) + `upload_dataset` (516) + `evaluate_queries` (582) + `make_snapshot` (656) (commit `bc606be`). |
| `eval/run_docling.py` | Orchestrator snapshot mode docling | ✓ VERIFIED | 260 dòng — pre-flight + embedder lock + cleanup + PUT `/api/rag-config` mode=docling + try/finally restore auto + snapshot `baseline_docling.json` (commit `bc606be`). |
| `eval/run_extraction_compare.py` | Per-doc compare metrics | ✓ VERIFIED | 448 dòng (commit `06b3e19`). |
| `eval/run_retrieval_eval.py` | 12 query × 2 mode + top-K + MRR | ✓ VERIFIED | 455 dòng (commit `b7d2768`). |
| `eval/run_compare.py` | Orchestrator + gate + EVAL.md generator | ✓ VERIFIED | 685 dòng + 7 section EVAL.md + gate logic + exit 0/1 (commit `b0de521`). |
| `Makefile` (root) | 5 target eval-* + help + 3 backend proxy | ✓ VERIFIED | 86 dòng — `eval-smoke` (48) + `eval-baseline-docling` (76) + `eval-compare` (79) + `eval-all` (82, depend chain đúng) + `eval-clean` (84) + `help` (default) (commit `3f54aee`). |
| `eval/README.md` Section 11 | Hướng dẫn workflow Phase 5 + troubleshooting | ✓ VERIFIED | +117 dòng — 7 sub-section (tiền điều kiện / workflow 3 bước / smoke / gate / outputs / troubleshooting 4 case / liên kết) (commit `3f54aee`). |
| `eval/baseline_docling.json` | Snapshot mode docling | ✗ MISSING (expected) | Defer runtime — sinh khi user chạy `make eval-baseline-docling`. |
| `eval/EVAL.md` | Final report commit | ✗ MISSING (expected) | Defer runtime — sinh khi user chạy `make eval-compare`. |

**Lưu ý:** 2 artifact MISSING là **runtime output** (không phải code) — chấp nhận theo CONTEXT mục Rủi ro 1 + Plan 05-05 SUMMARY mục 8.

---

## 3. Quality Gate Logic Verification

| Check | Expected | Actual | Status |
|-------|----------|--------|--------|
| Threshold hằng số module-level | `GATE_DELTA_THRESHOLD=0.15`, `GATE_ABSOLUTE_THRESHOLD=0.75` | Line 73-74 đúng | ✓ |
| Gate logic 3 case | delta ≥+15pp PASS / absolute ≥75% PASS / else FAIL | `evaluate_gate` line 159-180 đúng | ✓ |
| Exit code | PASS=0, FAIL=1 | Line 679 `exit_code = 0 if verdict == "PASS" else 1` | ✓ |
| EVAL.md sinh dù FAIL | Ghi file trước exit | Line 672-676 ghi file trước line 678 exit | ✓ |
| 7 section EVAL.md | Setup/Retrieval/Per-Query/Per-Doc/Smoke/Conclusion/Defer | Line 261/302/333/397/413/467/487 grep PASS | ✓ |
| Pre-condition fail-loud | Thiếu snapshot → SystemExit(1) + hint | Line 114/125/134/146/152 | ✓ |
| Unit test gate | 7/7 case (boundary +15pp + 75% + cross-thoả + 3 FAIL) | SUMMARY 05-04 verify section | ✓ |
| E2E smoke gate | PASS (docling=native) + FAIL (docling 50%) | EVAL.md 4143 + 4384 chars vẫn sinh, exit 0/1 | ✓ |

---

## 4. Requirements Coverage

| REQ | Plan | Description | Status | Evidence |
|-----|------|-------------|--------|----------|
| EVAL-02 | 05-02 | `run_extraction_compare.py` per-doc heading recall + table preservation | ✓ SATISFIED | 448 dòng + frontmatter `requirements: [EVAL-02]` |
| EVAL-03 | 05-03 | `run_retrieval_eval.py` 12 query × 2 mode top-K + MRR | ✓ SATISFIED | 455 dòng + frontmatter `requirements: [EVAL-03]` |
| EVAL-04 | 05-04 | `run_compare.py` orchestrator + quality gate + EVAL.md generator | ✓ SATISFIED | 685 dòng + frontmatter `requirements: [EVAL-04]` |
| EVAL-05 | 05-05 | Makefile + `make eval-smoke` + README | ✓ SATISFIED | Makefile 86 dòng + README +117 dòng + frontmatter `requirements: [EVAL-05]` |

**Coverage:** 4/4 REQ-ID (100%). Plan 05-01 không bind REQ chính thức — đúng vai trò foundation enabler cho Plan 02-04.

---

## 5. Anti-Patterns Scan

| File | Pattern | Severity | Note |
|------|---------|----------|------|
| `Makefile:eval-smoke` | `os.getenv('ADMIN_PASSWORD', 'Admin@123')` default credential | ℹ️ Info | Threat T-05-11 documented — accept với env override pattern; production CI set ENV thật. |
| `eval/run_compare.py:413` | Section 5 Smoke Verification placeholder text | ℹ️ Info | Design intent — Plan 05-04 CHECK W3 đã ghi nhận; user/Plan tương lai update sau khi smoke chạy real. |
| `eval/run_extraction_compare.py` | `TABLES_TOTAL_GOLD` hardcode dict 10 entry | ℹ️ Info | Phase 1 đã label dataset — chấp nhận, không phải stub. |

**KHÔNG có blocker, không có warning.** Toàn bộ pattern phát hiện đều documented + có lý do.

---

## 6. Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| 5 file Python compile OK | `python -m py_compile eval/{lib,run_docling,run_extraction_compare,run_retrieval_eval,run_compare}.py` | ast.parse PASS (per SUMMARY mỗi plan) | ✓ PASS |
| Makefile target syntax | `grep -E "^(eval-smoke\|eval-baseline-docling\|eval-compare\|eval-all\|eval-clean\|help):"` | 6/6 target FOUND | ✓ PASS |
| Gate threshold constants | `grep -nE "GATE_(DELTA\|ABSOLUTE)_THRESHOLD"` | Line 73-74 PASS | ✓ PASS |
| 7 section EVAL.md template | `grep -nE "^## [1-7]\."` trong build_eval_md | 7/7 marker PASS | ✓ PASS |
| Exit code logic | `grep "sys.exit(0 if verdict"` | Line 679 PASS | ✓ PASS |
| `make eval-all` end-to-end | `make eval-all` | N/A — cần Docling stack UP | ? SKIP (human) |
| `make eval-smoke` runtime | `make eval-smoke` | N/A — cần backend + Docling UP | ? SKIP (human) |

---

## 7. Human Verification Required

Xem section frontmatter `human_verification:` ở đầu file. Tóm tắt 3 item:

1. **Khởi động full stack + chạy `make eval-all`** → review `eval/EVAL.md` verdict (PASS/FAIL).
2. **Chạy `make eval-smoke`** (sau khi stack UP) — verify `extractor_used=='docling'` + `is_table` chunk thật.
3. **Verify `eval/EVAL.md`** chứa số liệu cụ thể (không placeholder) đủ 7 section.

---

## 8. Conclusion

### Phase 5: ✅ COMPLETED (code 100%) + 🟡 PENDING_RUNTIME (defer user)

- **Code-level:** 4/4 SC + 4/4 REQ + 7/9 artifact (2 còn lại là runtime output expected MISSING) + gate logic 7/7 unit + 2/2 E2E smoke + Makefile 5 target + README +117 dòng. Không blocker, không scope reduction.
- **Runtime defer:** `eval/baseline_docling.json` + `eval/EVAL.md` chỉ sinh được khi user khởi động Docling sidecar (Phase 2 runtime defer cùng nguyên nhân — Docker/Podman/WSL stack chưa setup).

### M1 Close Summary

**Milestone:** M1 — RAG Quality with Docling
**Trạng thái:** `m1_complete_pending_runtime`

| Phase | Code | Runtime | Status |
|-------|------|---------|--------|
| 1. Eval Dataset & Baseline Native | ✅ 100% | ✅ Done (baseline 75% commit `f37cd96`) | ✅ COMPLETED |
| 2. Docling Service (Python Sidecar) | ✅ 8/8 plans | 🟡 Smoke runtime defer user | 🟡 PARTIAL |
| 3. Go Adapter & Pipeline Wiring | ✅ 5/5 plans | 🟡 Defer (cần Phase 2 stack) | ✅ Code COMPLETED |
| 4. Config Hot-Swap & Circuit Breaker | ✅ 5/5 plans | 🟡 Defer (cần Phase 2 stack) | ✅ Code COMPLETED |
| 5. Eval Compare & Quality Gate | ✅ 5/5 plans | 🟡 EVAL.md runtime defer user | ✅ Code COMPLETED |

**Tổng:** 5 phase / 28 plans / 34 REQ — code 100% complete. Phase 1 runtime done; Phase 2-5 runtime defer chung do thiếu Docling Docker stack.

### Blocker close M1 chính thức

Cần user setup Docker/Podman/WSL stack đầy đủ:
1. PostgreSQL 16 + Redis 7 + ChromaDB + backend Go + `docling-pipeline` Python sidecar.
2. Chạy `make eval-all` (~30-60 phút) → review `eval/EVAL.md` verdict.

---

## 9. Hành động next cho user

### Option A — Setup stack + chạy runtime (recommended)
1. `docker compose up -d postgres redis chroma docling-pipeline backend`
2. Verify health: `curl http://localhost:8180/api/health` + `curl http://localhost:8001/healthz` (docling)
3. `make eval-clean && make eval-all` (~30-60 phút)
4. Review `eval/EVAL.md` verdict:
   - **Nếu PASS:** `git add eval/EVAL.md && git commit -m "docs(eval): EVAL.md M1 verdict PASS"` → `/gsd-complete-milestone` close M1 → advance M2 (Multi-subdomain SPA defer trước đó).
   - **Nếu FAIL:** đọc `EVAL.md` section 6 chọn 1 trong 3 hướng (reranker 999.2 / hybrid retrieval BM25+dense / data improvement) → tạo M1.5 hoặc thêm vào backlog M2.

### Option B — Accept code-level + close M1 với caveat
Nếu user chấp nhận M1 close ở mức **code 100% + runtime defer documented** (giống Phase 2-4 đã chấp nhận):
1. Chạy `/gsd-complete-milestone --accept-pending-runtime` (nếu lệnh hỗ trợ flag) hoặc cập nhật STATE.md status `m1_complete` thủ công với note "runtime EVAL.md defer M1.5 hardening khi Docker stack ready".
2. Advance M2 — quay lại runtime EVAL ở milestone hardening.

### Option C — Tạo override nếu xác nhận intentional
Nếu user xác định code-level + Phase 1 baseline 75% + smoke tests E2E (PASS+FAIL gate verified) là đủ bằng chứng cho M1, thêm override vào VERIFICATION.md frontmatter:

```yaml
overrides:
  - must_have: "eval/EVAL.md commit với số liệu thật"
    reason: "Runtime defer chung Phase 2-4 — cần Docker stack user setup. Code path 100% verified qua E2E smoke (PASS+FAIL 2 case + gate 7/7 unit)."
    accepted_by: "quangkhuupham@gmail.com"
    accepted_at: "2026-04-29T00:00:00Z"
```

---

*Verified: 2026-04-29 by Claude (gsd-verifier)*
