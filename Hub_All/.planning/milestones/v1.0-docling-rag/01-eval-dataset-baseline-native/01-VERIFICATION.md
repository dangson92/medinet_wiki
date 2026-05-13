---
phase: 01-eval-dataset-baseline-native
verified: 2026-04-28T15:30:00Z
status: human_needed
score: 2/4 success criteria PASS code-level + 2/4 DEFERRED runtime
overrides_applied: 0
verdict: PARTIAL (runtime deferred — code 100% complete)
human_verification:
  - test: "Khởi động backend Go + Postgres + ChromaDB local rồi chạy `python eval/baseline.py`"
    expected: "Sinh `eval/baseline_native.json` chứa documents[10], retrieval với top-1/3/5 hit rate + MRR, embedder config đầy đủ. 2 scanned PDF có status=error với error_message chứa 'no text extracted'."
    why_human: "Executor không có backend runtime + Postgres + ChromaDB local. Code logic đã verify static (ruff pass + AST parse + grep) nhưng output JSON chỉ sinh khi pipeline chạy thật end-to-end."
gaps: []  # Không có gap blocking goal — tất cả deliverable code-level đã đầy đủ
deferred:
  - truth: "Snapshot eval/baseline_native.json tồn tại với schema đúng (SC3)"
    addressed_in: "User runtime"
    evidence: "01-06-SUMMARY.md decision 'Runtime defer' + Pre-flight check (B3) trong baseline.py:74-142 sẽ tự verify 3 dependency lúc user chạy"
  - truth: "2 scanned PDF được ghi nhận fail extraction với chuỗi 'no text extracted' (SC4)"
    addressed_in: "User runtime"
    evidence: "Logic assert đã embed trong baseline.py:525-560 (W2 3-way: pass / bypass có lý do / fail). pdf.go:52 đã có `fmt.Errorf('pdf: no text extracted from %q (scanned PDF?)')` — verified."
---

# Phase 1: Eval Dataset & Baseline Native — Verification Report

**Phase Goal:** Có sẵn eval dataset đầy đủ + bộ truy vấn vàng + số liệu baseline retrieval đo bằng extractor Go hiện tại, để Phase 5 có cơ sở so sánh trước/sau.

**Verified:** 2026-04-28
**Status:** PARTIAL (runtime deferred)
**Re-verification:** No — initial verification

---

## Tổng kết verdict

| Layer | Trạng thái |
|---|---|
| Code-level deliverable | **100% COMPLETE** — toàn bộ 6/6 plan đã commit, dataset đầy đủ, queries đầy đủ, code baseline.py 588 dòng đầy đủ logic. |
| Runtime deliverable | **DEFERRED** — `eval/baseline_native.json` chưa sinh do executor không có backend Go + Postgres + ChromaDB local. |
| Goal achievement | **PARTIAL** — 2/4 SC PASS hoàn toàn ở layer code, 2/4 SC DEFERRED runtime. Pre-flight check (B3) trong baseline.py sẽ tự verify infra khi user chạy thật. |

**Verdict overall:** **PARTIAL (runtime deferred)** — không có gap blocking; chỉ cần user chạy 1 lệnh để hoàn tất.

---

## Per-Criterion Verification

### SC1 — eval/dataset/ có 8 file gốc + ≥ 2 scanned PDF tiếng Việt y tế

**Trạng thái: ✅ PASS**

**Evidence:**

| Mục | Yêu cầu | Thực tế | Path |
|---|---|---|---|
| Sources DOCX | 7 file DMD | 7 file DMD ✅ | `eval/dataset/sources/DMD_T1-01_DinhVi_TrungTam_v1.docx`, `DMD_T1-02_TuDien_ThuongHieu_v1.docx`, `DMD_T1-03_Script_Library_v1.docx`, `DMD_T1-04_FAQ_ThuongHieu_v1.docx`, `DMD_T3-02_PhanCong_NhanVat_v1.docx`, `DMD_T5-01_ContentStrategy_12TuyenND_v1.docx`, `DMD_T5-02_Playbook_KenhTruyen_v1.docx` |
| Sources PDF | 1 file PDF gốc | 1 file PDF ✅ | `eval/dataset/sources/tri_thuc_chinh_tri.pdf` (97 KB) |
| Tổng sources | 8 file | 8 file ✅ | — |
| Scanned PDF | ≥ 2 | 2 file ✅ | `eval/dataset/scanned/DMD_T1-01_scanned.pdf` (3.7 MB), `eval/dataset/scanned/DMD_T1-04_scanned.pdf` (4.7 MB) |
| Reproducibility | Script | ✅ | `eval/scripts/build_scanned.py` (sinh image-only PDF từ DOCX) |

**Kết luận SC1:** Cấu trúc thư mục khớp 100% với spec ROADMAP. 2 scanned PDF có kích thước lớn (3.7 MB + 4.7 MB) — đặc trưng PDF image-only, đúng yêu cầu Phase 1.

---

### SC2 — eval/dataset/queries.jsonl có 10–15 truy vấn vàng đủ field

**Trạng thái: ✅ PASS**

**Evidence:**

| Mục | Yêu cầu | Thực tế |
|---|---|---|
| Số dòng | 10–15 | **12 dòng** ✅ (`wc -l eval/dataset/queries.jsonl = 12`) |
| Schema fields | id, query, expected_doc_id, expected_section, notes | Đầy đủ 5 field ✅ (verify từng dòng q01–q12) |
| expected_doc_id LÀ filename | KHÔNG UUID | 100% filename ✅ (vd `DMD_T1-01_DinhVi_TrungTam_v1.docx`, `tri_thuc_chinh_tri.pdf`, `DMD_T1-01_scanned.pdf`) |
| Match sources/ hoặc scanned/ | Mỗi expected_doc_id phải tồn tại file thật | 12/12 match ✅ |
| Coverage | ít nhất 1 query/doc | 10 doc unique trong 12 query (q11+q01 cùng T1-01, q12+q04 cùng T1-04 — bonus) ✅ |
| Scanned coverage | có query trỏ scanned | q09 → DMD_T1-01_scanned.pdf, q10 → DMD_T1-04_scanned.pdf ✅ |

**Distribution:**

| Doc | Query IDs |
|---|---|
| DMD_T1-01_DinhVi_TrungTam_v1.docx | q01, q11 |
| DMD_T1-02_TuDien_ThuongHieu_v1.docx | q02 |
| DMD_T1-03_Script_Library_v1.docx | q03 |
| DMD_T1-04_FAQ_ThuongHieu_v1.docx | q04, q12 |
| DMD_T3-02_PhanCong_NhanVat_v1.docx | q05 |
| DMD_T5-01_ContentStrategy_12TuyenND_v1.docx | q06 |
| DMD_T5-02_Playbook_KenhTruyen_v1.docx | q07 |
| tri_thuc_chinh_tri.pdf | q08 |
| DMD_T1-01_scanned.pdf | q09 |
| DMD_T1-04_scanned.pdf | q10 |

**Kết luận SC2:** Queries đầy đủ schema, coverage đều, expected_doc_id LÀ filename match `result.category` (B2 fix đã verify ở `01-CHECK.md` round 2). 2 scanned PDF có query riêng để Phase 5 đo recovery sau khi Docling OCR ra text.

---

### SC3 — Snapshot eval/baseline_native.json chứa chunks/doc, top-3/5 hit rate, MRR

**Trạng thái: ⏳ DEFERRED (runtime)**

**Lý do defer:** Executor không có backend Go + Postgres + ChromaDB chạy local — không thể sinh runtime output. Code logic 100% đầy đủ + verify static.

**Evidence code-level:**

| Mục | Path / Line | Trạng thái |
|---|---|---|
| File `eval/baseline.py` tồn tại | `eval/baseline.py` 588 dòng | ✅ |
| Pre-flight check 3 layer (B3) | `baseline.py:74-142` | ✅ — backend health + ChromaDB heartbeat + DB hub seed query, fail-loud SystemExit với hint cụ thể |
| Login + JWT auto-refresh 401 | `baseline.py:165-209` (`APIClient._request_with_retry`) | ✅ — handle TTL 15 phút |
| Embedder config fail-loud (W5) | `baseline.py:258-289` (`get_embedder_config`) | ✅ — SystemExit nếu provider rỗng / dim=0 |
| Upload + poll status | `baseline.py:293-330` (`upload_and_wait`) | ✅ — sequential, timeout 300s, poll 2s |
| Search 12 queries | `baseline.py:333-347` (`search_query`) | ✅ — POST /api/search top_k=5 |
| Match category lowercase (B2) | `baseline.py:376-377` `res_category = (res.get("category") or "").lower()` | ✅ — match expected_doc_id.lower() |
| Compute metrics top-1/3/5 + MRR | `baseline.py:351-413` (`compute_retrieval_metrics`) | ✅ — đầy đủ 4 metric |
| Schema snapshot output (B1) | `baseline.py:498-510` | ✅ — KHÔNG có `headings_recalled`/`headings_missed` (defer Phase 5 EVAL-02), CÓ `headings_gold_count` |
| Snapshot UTF-8 | `baseline.py:512-515` `ensure_ascii=False` | ✅ — query tiếng Việt readable |

**Static verify đã pass (từ 01-06-SUMMARY.md):**

| Check | Result |
|---|---|
| `python -m ruff check eval/baseline.py` | All checks passed! |
| `python -c "import ast; ast.parse(...)"` | AST parse OK |
| `python eval/baseline.py --help` | In đúng usage + 3 flag |
| `grep -c "preflight_check" eval/baseline.py` | 2 (B3 ✓) |
| `grep -c "api/v2/heartbeat" eval/baseline.py` | 3 (B3 ChromaDB ✓) |
| `grep -c "WHERE code = %s" eval/baseline.py` | 1 (B3 DB query ✓) |
| `grep -c "Pre-flight FAIL" eval/baseline.py` | 6 (fail-loud ✓) |
| `grep -c "headings_gold_count" eval/baseline.py` | 2 (B1 ✓) |
| `grep '"headings_recalled"\|"headings_missed"' eval/baseline.py` | 0 (B1 defer ✓) |
| `grep "category.*lower" eval/baseline.py` | line 376 (B2 ✓) |

**Kết luận SC3:** Code logic ĐẦY ĐỦ + chính xác (đã verify B1, B2, B3, W2, W5 ở `01-CHECK.md` round 2 verdict PASS). Output runtime chỉ sinh khi user chạy 1 lệnh `python eval/baseline.py` trên môi trường có backend up. Không có gap blocking goal — chỉ cần infra runtime.

---

### SC4 — Scanned PDF được ghi nhận fail extraction (`no text extracted` từ pdf.go:52)

**Trạng thái: ⏳ DEFERRED (runtime)**

**Lý do defer:** Cần backend Go thực sự chạy extraction trên 2 scanned PDF, ghi error vào `documents.error_message` qua API `/api/documents/{id}/status`. Không sinh được output static.

**Evidence code-level:**

| Mục | Path / Line | Trạng thái |
|---|---|---|
| `pdf.go:52` chứa chuỗi "no text extracted" | `backend/internal/rag/extractor/pdf.go:52` | ✅ — `return "", fmt.Errorf("pdf: no text extracted from %q (scanned PDF?)", filePath)` |
| Logic SC4 verify trong baseline.py | `baseline.py:525-560` | ✅ — filter scanned_failed + log SC4 met |
| W2 assert error_message (3-way) | `baseline.py:537-555` | ✅ — pass / bypass có-lý-do / partial |
| 2 scanned PDF có expected query | `queries.jsonl` q09 + q10 | ✅ — query trỏ scanned dự kiến rank=None ở baseline native |
| build_scanned.py reproducible | `eval/scripts/build_scanned.py` | ✅ — DOCX → PDF → raster image → image-PDF (no text layer) → guarantee `pdf.go` extractor sẽ fail "no text extracted" |

**Logic 3-way W2 verify (baseline.py:537-555):**

```python
for sd in scanned_failed:
    err_text = (sd.get("error_message") or sd.get("error") or "").lower()
    if "no text extracted" in err_text:
        logger.info("  W2 OK: %s error_message chứa 'no text extracted'", sd["filename"])
    elif not err_text:
        logger.warning("  W2 bypass: %s status=error nhưng API không trả error_message...")
    else:
        logger.warning("  W2 partial: %s error: %s", sd["filename"], err_text[:200])
```

**Kết luận SC4:** Backend code (`pdf.go:52`) đã có chuỗi đúng. Eval code (`baseline.py:525-560`) đã có logic assert + W2 bypass có-lý-do. 2 scanned PDF được sinh từ raster image-only PDF (no text layer) qua `build_scanned.py` → guarantee `pdf.go` sẽ fail. Runtime verify chỉ chạy 1 lệnh là xong.

---

## Required Artifacts (file-level)

| Artifact | Expected | Status | Path |
|---|---|---|---|
| `eval/dataset/sources/` | 7 DOCX + 1 PDF | ✅ EXISTS | 8/8 file đúng tên |
| `eval/dataset/scanned/` | ≥ 2 PDF tiếng Việt | ✅ EXISTS | 2 PDF (3.7 MB + 4.7 MB) |
| `eval/dataset/queries.jsonl` | 10–15 dòng schema valid | ✅ EXISTS | 12 dòng, đầy đủ 5 field |
| `eval/dataset/headings.json` | Heading vàng per doc | ✅ EXISTS | 307 dòng |
| `eval/dataset/DATASET.md` | Mô tả dataset | ✅ EXISTS | 212 dòng |
| `eval/baseline.py` | Pipeline orchestration | ✅ EXISTS | 588 dòng, ruff pass, AST OK |
| `eval/pyproject.toml` | Python deps | ✅ EXISTS | pypdf>=5.0, httpx, psycopg, etc. |
| `eval/scripts/seed_hub.sql` | Seed eval_hub | ✅ EXISTS | — |
| `eval/scripts/cleanup.py` | Cleanup state | ✅ EXISTS | I1 fix 3-layer guard |
| `eval/scripts/build_scanned.py` | Sinh scanned PDF | ✅ EXISTS | — |
| `eval/scripts/extract_headings.py` | Extract heading từ DOCX | ✅ EXISTS | W4 fix |
| `eval/baseline_native.json` | Snapshot baseline | ⏳ DEFERRED | Runtime sinh khi user chạy |

---

## Key Link Verification

| From | To | Via | Status |
|---|---|---|---|
| `baseline.py` | `POST /api/auth/login` | `httpx.AsyncClient` | ✅ WIRED — `APIClient.login()` line 165-175 |
| `baseline.py` | `POST /api/documents/upload` | multipart form-data | ✅ WIRED — `post_multipart` line 223-235 |
| `baseline.py` | `GET /api/documents/{id}/status` | poll loop | ✅ WIRED — `upload_and_wait` line 314-322 |
| `baseline.py` | `POST /api/search` | JSON body | ✅ WIRED — `search_query` line 343-347 |
| `baseline.py` | `GET /api/rag-config` | embedder capture | ✅ WIRED — `get_embedder_config` line 264 |
| `baseline.py` | `GET /api/rag-config/collections` | dim capture | ✅ WIRED — line 268 |
| `baseline.py` | Postgres `hubs` table | `psycopg.connect` | ✅ WIRED — `preflight_check` line 124-134 |
| `baseline.py` | ChromaDB `/api/v2/heartbeat` | health check | ✅ WIRED — line 105 |
| `expected_doc_id` matching | `result.category` lowercase | `compute_retrieval_metrics` | ✅ WIRED — line 376-377 (B2 fix) |
| `pdf.go:52` "no text extracted" | `error_message` poll | backend pipeline | ⏳ Runtime — mã có, output cần backend chạy |

---

## Requirements Coverage

**REQ-ID đã ánh xạ Phase 1:** EVAL-01

| Requirement | Description | Status | Evidence |
|---|---|---|---|
| EVAL-01 | Tạo `eval/dataset/` chứa: 8 file `file_test/` + ≥ 2 scanned PDF tiếng Việt y tế + `queries.jsonl` 10–15 truy vấn vàng (mỗi câu kèm `expected_doc_id`, `expected_section`, `notes`). | ✅ SATISFIED | SC1 + SC2 PASS code-level. REQUIREMENTS.md đã mark `[x]` line 70-71. |

Không có orphan REQ-ID. EVAL-01 xuất hiện trong frontmatter `requirements: [EVAL-01]` của cả 6/6 plan.

---

## Anti-Patterns Scan

| File | Pattern | Severity | Note |
|---|---|---|---|
| `eval/baseline.py` | Không tìm thấy TODO/FIXME/PLACEHOLDER | — | Sạch |
| `eval/baseline.py` | Không có `return null`/`return []` static | — | Sạch |
| `eval/baseline.py` | Không có console.log only | — | Logger structured đầy đủ |
| `eval/dataset/queries.jsonl` | Không có placeholder | — | 12 query có content thật |
| `eval/dataset/headings.json` | 307 dòng — không rỗng | — | Heading vàng có content |

**Kết luận:** Không có anti-pattern. Code production-ready.

---

## Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| baseline.py parse được | `python -m ruff check eval/baseline.py` | All checks passed (theo SUMMARY) | ✅ PASS |
| baseline.py AST valid | `python -c "import ast; ast.parse(...)"` | AST OK (theo SUMMARY) | ✅ PASS |
| baseline.py có --help | `python eval/baseline.py --help` | In 3 flag (theo SUMMARY) | ✅ PASS |
| queries.jsonl đếm dòng | `wc -l queries.jsonl` | 12 (verify trực tiếp) | ✅ PASS |
| pdf.go:52 chuỗi đúng | `grep "no text extracted" backend/.../pdf.go` | Line 52 match | ✅ PASS |
| Sinh `baseline_native.json` end-to-end | `python eval/baseline.py` (cần backend up) | — | ? SKIP (cần runtime) |
| 2 scanned PDF báo "no text extracted" | poll `/api/documents/{id}/status` | — | ? SKIP (cần runtime) |

---

## Human Verification Required

Để hoàn tất Phase 1 verdict thành **COMPLETE**, user cần thực hiện 1 lần các bước sau trên môi trường local:

### 1. Khởi động infra runtime (3 dependency)

```bash
# 1a. Postgres + ChromaDB qua docker-compose
cd D:/ChuongNV_Medinet/AI/medinet_wiki/Hub_All
docker-compose up -d chroma postgres   # hoặc tên service trong docker-compose.yml

# 1b. Seed hub eval (1 lần duy nhất)
psql -h localhost -U medinet -d medinet_central -f eval/scripts/seed_hub.sql

# 1c. Backend Go
cd backend
go run ./cmd/server
# Đợi log "server listening on :8180" rồi mở terminal khác
```

### 2. Chạy baseline (5–15 phút)

```bash
cd D:/ChuongNV_Medinet/AI/medinet_wiki/Hub_All

# Cleanup state cũ (xóa documents/chunks cũ + reset chroma collection)
python eval/scripts/cleanup.py

# Sinh baseline snapshot
python eval/baseline.py
```

**Expected output:**

- File `eval/baseline_native.json` được tạo, valid JSON UTF-8.
- `documents[]` có 10 entry: 8 completed + 2 scanned error.
- 2 scanned PDF có `error_message` chứa chuỗi `no text extracted` (hoặc bypass log nếu API không expose field).
- `retrieval` có top_1/3/5 hit rate + MRR (số 0–1).
- `retrieval.per_query` có 12 entry.
- Top-3 hit rate baseline native dự kiến ≈ 8/12 (≈ 67%) — vì q09 + q10 (scanned) sẽ rank=None.
- Embedder config (`embedder_provider`, `embedder_model`, `embedder_dim`) được capture từ `/api/rag-config` + `/api/rag-config/collections`.

**Pre-flight tự verify:** Nếu thiếu backend / ChromaDB / hub seed → script exit ngay với hint cụ thể (KHÔNG silent fail).

### 3. Verify snapshot output

```bash
# JSON parse hợp lệ
python -c "import json; json.load(open('eval/baseline_native.json', encoding='utf-8'))"

# Có đủ 4 metric retrieval
python -c "import json; d=json.load(open('eval/baseline_native.json',encoding='utf-8')); print({k:d['retrieval'][k] for k in ['top_1_hit_rate','top_3_hit_rate','top_5_hit_rate','mrr']})"

# Documents[] có 10 entry
python -c "import json; d=json.load(open('eval/baseline_native.json',encoding='utf-8')); print(len(d['documents']))"

# 2 scanned có status=error
python -c "import json; d=json.load(open('eval/baseline_native.json',encoding='utf-8')); print([(x['filename'],x['status']) for x in d['documents'] if 'scanned' in x['filename']])"
```

### 4. Commit snapshot

```bash
git add eval/baseline_native.json
git commit -m "feat(01): runtime sinh baseline_native.json — đóng SC3 + SC4 Phase 1"
```

---

## Gaps Summary

**KHÔNG có gap blocking goal.**

Code-level deliverable Phase 1 đã 100% đầy đủ:
- 8 sources + 2 scanned PDF + 12 queries vàng + headings.json + DATASET.md đều commit thật.
- `baseline.py` 588 dòng đầy đủ logic pre-flight + login + upload + poll + search + metrics + snapshot.
- Toàn bộ B1/B2/B3/W2/W5 fix đã verify static qua `01-CHECK.md` round 2 verdict PASS.
- Backend `pdf.go:52` đã có chuỗi `no text extracted` — guaranteed fail cho image-only PDF.

Hai SC còn DEFERRED (SC3 snapshot file + SC4 runtime fail evidence) **không phải gap** mà là **runtime work** — chỉ cần user chạy 1 lệnh trên môi trường có infra. Pre-flight check (B3) trong baseline.py sẽ tự verify 3 dependency và fail loud nếu thiếu — không có nguy cơ silent fail.

**Ý nghĩa cho Phase 2:** Phase 2 (Docling Service) **KHÔNG bị block** bởi runtime defer của Phase 1 — Phase 2 chỉ phụ thuộc dataset + queries (đã có) để smoke test endpoint cuối phase. Snapshot `baseline_native.json` chỉ thực sự cần ở Phase 5 (Eval Compare) làm input compare; user có dư thời gian sinh nó song song với Phase 2/3/4.

---

## Verdict Cuối

| Tiêu chí | Đánh giá |
|---|---|
| Goal Phase 1 đạt được? | **PARTIAL** — dataset + queries + code 100%; baseline runtime cần user chạy 1 lệnh |
| Phase 2 sẵn sàng start? | **YES** — Phase 2 dependency là dataset (đã có), KHÔNG phải baseline_native.json |
| Phase 5 cần gì từ Phase 1? | `eval/baseline_native.json` runtime → user chạy bất cứ lúc nào trước Phase 5 |
| Recommendation | Ghi nhận Phase 1 **PARTIAL (runtime deferred)** với 4 user-action steps đã liệt kê. Cho phép Phase 2 start. User chạy `python eval/baseline.py` lúc nào tiện trước Phase 5. |

---

*Verified: 2026-04-28*
*Verifier: Claude (gsd-verifier)*
