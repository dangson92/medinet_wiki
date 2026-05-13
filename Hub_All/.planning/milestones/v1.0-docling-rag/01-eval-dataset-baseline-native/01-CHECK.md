# Plan Check — Phase 1: Eval Dataset & Baseline Native

**Phase:** 1 / 5
**Round:** 2 (re-verify sau revision round 1)
**Ngày check:** 2026-04-28
**Plans verified:** 6 (01..06)
**Verdict:** **PASS** — toàn bộ 9 issue (3 blocker + 5 warning + 1 info) đã được fix đúng

---

## Tóm tắt

Round 1 phát hiện 3 blocker (B1, B2, B3) + 5 warning (W1-W5) + 1 info (I1). Planner đã revise toàn bộ 6 plan + CONTEXT.md. Round 2 verify từng issue theo gốc plan (không chỉ dựa trên claim của planner) — tất cả đều fix đúng theo spec round 1. Không phát sinh regression mới. Plans sẵn sàng để chạy /gsd-execute-phase 1.

| Success Criterion (ROADMAP) | Plans cover | Trạng thái |
|---|---|---|
| SC1 — eval/dataset/ có 8 file gốc + ≥ 2 scanned PDF | Plan 01 (8 sources) + Plan 03 (2 scanned) | COVERED |
| SC2 — eval/dataset/queries.jsonl có 10-15 truy vấn vàng đủ field | Plan 05 (W3 schema valid + W4 heading vàng PDF gốc) | COVERED |
| SC3 — Snapshot eval/baseline_native.json chứa chunks/doc, top-3/5, MRR | Plan 06 (B1 schema clean + B2 matching đúng + W5 fail-loud) | COVERED |
| SC4 — Scanned PDF ghi nhận fail extraction (no text extracted) | Plan 06 Task 3 (W2 assert error_message + bypass có-lý-do) | COVERED |

REQ-ID EVAL-01 xuất hiện trong frontmatter requirements của cả 6 plan → **REQUIREMENT COVERAGE PASS**.

---

## Round 2 — Verify từng issue

### B1 — heading_recall metric (BLOCKER) → FIXED

**Yêu cầu round 1:**
- CONTEXT.md mục Snapshot output: chỉ còn headings_gold_count (không còn headings_recalled/headings_missed).
- Plan 06: annotate_heading_gold_count thay cho compute_heading_metrics, snapshot không có 2 field defer.

**Kiểm tra thực tế:**
- 01-CONTEXT.md:116 schema documents: chỉ có `headings_gold_count: <int>` — KHÔNG có 2 field defer.
- 01-CONTEXT.md:130-131 revision note: defer Phase 5 theo REQ EVAL-02, ghi rõ lý do Phase 1 đo placeholder rỗng sẽ misleading.
- 01-CONTEXT.md:141 Out of Scope: ghi Heading recall metric ... defer Phase 5 theo REQ EVAL-02.
- 01-06-PLAN.md:577-591 hàm annotate_heading_gold_count: tên hàm đã đổi, chỉ ghi `d[headings_gold_count] = len(gold)`, comment ghi rõ heading_recall measured in Phase 5 (REQ EVAL-02).
- 01-06-PLAN.md:645 snapshot: comment KHÔNG có headings_recalled/headings_missed (B1).
- 01-06-PLAN.md:649-650 comment + _note field: ghi rõ defer.
- 01-06-PLAN.md:713 verify automated: grep negative cho headings_recalled/headings_missed trong baseline.py.
- 01-06-PLAN.md:965-969 Task 3 verify: assert KHÔNG có 2 field + assert có headings_gold_count.

**Kết luận:** B1 fix triệt để. Schema CONTEXT.md ↔ implementation Plan 06 ↔ verify Task 3 — cả 3 layer khớp nhau.

### B2 — Search result matching qua filename (BLOCKER) → FIXED

**Yêu cầu round 1:**
- CONTEXT.md clarify expected_doc_id = filename, match result.category (từ searcher.go:131).
- Plan 06 compute_retrieval_metrics match expected_doc_id.lower() == result[category].lower().
- Plan 05 schema queries dùng filename.

**Kiểm tra thực tế:**
- 01-CONTEXT.md:29 ghi rõ: expected_doc_id LÀ filename, lý do match result.category (searcher.go:131), result.id là chunk_id.
- 01-06-PLAN.md:535,540-541 compute_retrieval_metrics:
    - expected_filename = q[expected_doc_id].lower()
    - res_category = (res.get(category) or empty).lower()
    - if res_category == expected_filename: ...
    - Lowercase 2 phía + handle None an toàn.
- 01-06-PLAN.md:557-558 per_query output rename rõ: chunk_id: res.get(id) + category: res.get(category) — tránh nhầm lẫn id/category.
- 01-06-PLAN.md:42-43 frontmatter key_links ghi rõ matching dùng category lowercase.
- 01-05-PLAN.md:19,46,108-110 schema queries:
    - Truth: expected_doc_id LÀ filename ... match result.category.
    - Schema: expected_doc_id chú thích FILENAME, không phải UUID ... match với SearchResult.Category (searcher.go:131).
- 01-05-PLAN.md:174 done: Tất cả expected_doc_id LÀ filename ... KHÔNG có UUID.
- 01-06-PLAN.md:713 verify: grep category.*lower HOẶC lower.*category.

**Kết luận:** B2 fix triệt để. CONTEXT → schema queries → matching code → verify đều nhất quán.

### B3 — Pre-flight check (BLOCKER) → FIXED

**Yêu cầu round 1:**
- Plan 06 có Task 0 với 3 check: backend health, ChromaDB heartbeat, DB query SELECT id FROM hubs WHERE code=eval.

**Kiểm tra thực tế:**
- 01-06-PLAN.md:135-224 Task 0 Pre-flight check tồn tại đầy đủ:
    - Check 1 backend (L153-168): GET /api/health, fallback /api/rag-config nếu trả 404 (đề phòng endpoint chưa tồn tại). Fail → SystemExit với hint cd backend && go run ./cmd/server.
    - Check 2 ChromaDB (L171-184): GET /api/v2/heartbeat, fail → hint docker-compose up -d chroma.
    - Check 3 DB hub seed (L187-204): SELECT id FROM hubs WHERE code = %s, fail → hint psql -f eval/scripts/seed_hub.sql.
- 01-06-PLAN.md:301-358 hàm preflight_check() cũng được implement nguyên trong baseline.py code Task 1 (đảm bảo không bị quên).
- 01-06-PLAN.md:597 run_baseline(): await preflight_check() gọi TRƯỚC api.login() — đúng yêu cầu round 1.
- 01-06-PLAN.md:217 verify automated: grep preflight_check, api/health, api/v2/heartbeat, WHERE code = %s, Pre-flight FAIL.
- 01-06-PLAN.md:16 must_haves.truths đầu tiên ghi rõ pre-flight check là điều kiện bắt buộc.

**Kết luận:** B3 fix triệt để. Task 0 tách riêng + integrate vào Task 1 + truths frontmatter + verify command. Có cả fallback /api/rag-config nếu /api/health chưa tồn tại — bonus tốt.

### W1 — pypdf trong pyproject.toml (WARNING) → FIXED

**Yêu cầu round 1:** Plan 01 pyproject.toml có pypdf>=5.0.

**Kiểm tra thực tế:**
- 01-01-PLAN.md:98 dependencies: pypdf>=5.0. (Round 1 đề xuất >=4.0; planner upgrade lên >=5.0 — chấp nhận, version mới hơn đáp ứng tốt hơn.)
- 01-01-PLAN.md:27 truths: cài đầy đủ deps Python (httpx, psycopg, python-docx, pypdf, ...).
- 01-01-PLAN.md:172 verify automated: python -c import pypdf.
- 01-01-PLAN.md:177 done: python -c import pypdf không lỗi (W1 fix).
- 01-03-PLAN.md:317 Plan 03 verify Task 2: from pypdf import PdfReader — sẽ chạy được vì pypdf đã có trong pyproject.toml.

**Kết luận:** W1 fix.

### W2 — Verify SC4 assert error message (WARNING) → FIXED

**Yêu cầu round 1:** Plan 06 verify task assert no text extracted trong error_message của 2 scanned PDF; có bypass có-lý-do nếu API không expose field.

**Kiểm tra thực tế:**
- 01-06-PLAN.md:937-962 Task 3 verify (block Python embed trong action):
    - Vòng for duyệt scanned_failed, kiểm tra err_text = d.get(error_message) or d.get(error) or empty.
    - if no text extracted in err_text.lower(): no_text_count += 1
    - elif not err_text: no_msg_count += 1 (bypass log).
    - if no_text_count >= 2: W2 met
    - elif no_msg_count == len(scanned_failed): W2 bypassed (lý do rõ)
    - else: raise AssertionError.
    - Logic 3-way: pass / bypass có lý do / fail.
- 01-06-PLAN.md:1019-1022 verify automated:
    - no_text = sum(...), no_field = sum(...), assert no_text >= 2 or no_field == len(scanned_err).
    - Đúng spec round 1.
- 01-06-PLAN.md:990-994 action ghi rõ lý do bypass + đề xuất Phase 5 fix backend trả error_message.
- 01-06-PLAN.md:20 truths: ghi rõ 2 scanned PDF có status=error với error_message chứa no text extracted.
- 01-06-PLAN.md:1031 done: W2 fix: hoặc 2 scanned có error_message chứa no text extracted, HOẶC bypass với log rõ lý do.

**Kết luận:** W2 fix. Logic check cả error_message lẫn error (backend có thể trả 1 trong 2) — robust hơn yêu cầu round 1.

### W3 — Plan 05 verify command syntax (WARNING) → FIXED

**Yêu cầu round 1:** Plan 05 phải dùng Python loop hợp lệ (for q in queries: ... assert).

**Kiểm tra thực tế:**
- 01-05-PLAN.md:146-153 smoke check trong action (Python valid):
    - queries = [json.loads(line) for line in open(path) if line.strip()]
    - assert 10 <= len(queries) <= 15
    - required_fields = {id, query, expected_doc_id, expected_section, notes}
    - for q in queries: missing = required_fields - q.keys(); assert not missing, ...
    - For-loop chuẩn, assert chuẩn. KHÔNG còn assert_(...) if False else None cú pháp sai.
- 01-05-PLAN.md:158-167 verify automated (cùng pattern):
    - Cùng pattern for q in queries: missing = ...; assert not missing.
    - Bonus: docs = {q[expected_doc_id] for q in queries}; assert len(docs) >= 10 — coverage check.
    - Python valid.

**Kết luận:** W3 fix. Bonus: verify thêm coverage check (không yêu cầu round 1 nhưng tốt).

### W4 — Heading vàng cho PDF gốc + 2 scanned (WARNING) → FIXED

**Yêu cầu round 1:** Plan 04 Task 2 có instruction LLM-draft heading cho tri_thuc_chinh_tri.pdf; 2 scanned heading copy từ DOCX gốc.

**Kiểm tra thực tế:**
- 01-04-PLAN.md:300-334 Task 2 Bước A LLM-draft heading vàng cho tri_thuc_chinh_tri.pdf:
    - Hướng dẫn cụ thể: mở PDF qua pypdf, đọc TOC reader.outline, đọc 10 trang đầu (reader.pages[:10]).
    - Heuristic phát hiện heading nếu PDF không có TOC (IN HOA, dòng đầu trang, prefix Phần/Chương/Mục/I./1./A.).
    - Format final cụ thể với ví dụ.
    - Đủ chi tiết để executor LLM thực thi không cần hỏi lại.
- 01-04-PLAN.md:130-141 MANUAL_PDF_HEADINGS[tri_thuc_chinh_tri.pdf]: TODO marker với hướng dẫn fill.
- 01-04-PLAN.md:236-241 main() fail-loud: nếu list rỗng → return 3 với message ép Task 2 phải fill — KHÔNG cho phép commit list rỗng.
- 01-04-PLAN.md:122-125 SCANNED_SOURCE_MAP map scanned ↔ DOCX gốc:
    - DMD_T1-01_scanned.pdf -> DMD_T1-01_DinhVi_TrungTam_v1.docx
    - DMD_T1-04_scanned.pdf -> DMD_T1-04_FAQ_ThuongHieu_v1.docx
- 01-04-PLAN.md:244-255 main() copy heading scanned từ DOCX gốc tự động.
- 01-04-PLAN.md:18-19 truths:
    - PDF gốc tri_thuc_chinh_tri.pdf có heading vàng manual >= 1 entry.
    - 2 scanned PDF có heading vàng = COPY từ DOCX gốc.
- 01-04-PLAN.md:378 verify automated: assert len(data[tri_thuc_chinh_tri.pdf]) >= 1 + data[DMD_T1-01_scanned.pdf] == data[DMD_T1-01_DinhVi_TrungTam_v1.docx].
- 01-05-PLAN.md:280-305 checkpoint Task 3: gộp review heading vàng PDF gốc với queries (giữ nguyên W4 fix flow đã đề xuất round 1).

**Kết luận:** W4 fix triệt để. Bonus: main() raise return code 3 nếu list rỗng — fail-loud chặn commit dataset không hoàn chỉnh.

### W5 — Embedder fail loud (WARNING) → FIXED

**Yêu cầu round 1:** Plan 06 get_embedder_config raise SystemExit nếu provider rỗng / dim=0.

**Kiểm tra thực tế:**
- 01-06-PLAN.md:451-478 get_embedder_config:
    - if not config.get(embedder_provider) or config.get(embedder_dim, 0) == 0: raise SystemExit(Embedding config invalid: ...).
    - Đúng spec round 1.
- 01-06-PLAN.md:19 truths: fail loud (SystemExit) nếu provider rỗng hoặc dim=0.
- 01-06-PLAN.md:602 run_baseline() gọi get_embedder_config ngay sau login() → fail nhanh.
- 01-06-PLAN.md:711 action notes: Embedder config invalid → SystemExit ngay sau login (W5).

**Kết luận:** W5 fix. Hint message chi tiết (chỉ rõ check .env backend + /api/rag-config/collections).

### I1 — shutil.rmtree guard 3-layer (INFO) → FIXED

**Yêu cầu round 1:** Plan 02 cleanup.py có guard 3-layer (DANGEROUS_HUB_CODES + subdir check + path string contains eval).

**Kiểm tra thực tế:**
- 01-02-PLAN.md:194-195 constant: DANGEROUS_HUB_CODES = {empty, dot, slash, star, double-dot, backslash}.
- 01-02-PLAN.md:286-319 cleanup_uploads_dir():
    - Guard 1 (L295-300): check EVAL_HUB_CODE in DANGEROUS_HUB_CODES → sys.exit(99) với log Refusing rmtree.
    - Guard 2 (L302-311): target tồn tại + is_dir() (không phải symlink/file) → exit 99 nếu sai.
    - Guard 3 (L313-316): if eval not in str(target): exit 99 — sanity cuối.
- 01-02-PLAN.md:357 verify automated: grep DANGEROUS_HUB_CODES + Refusing rmtree.
- 01-02-PLAN.md:365 done: ghi rõ 3 guard.
- 01-02-PLAN.md:22 truths: cleanup_uploads_dir() an toàn — fail loud khi EVAL_HUB_CODE rỗng/dangerous, KHÔNG bao giờ rmtree thư mục root backend/uploads/.
- 01-02-PLAN.md:376 verification step 5: test guard với EVAL_HUB_CODE rỗng → expect exit code 99.

**Kết luận:** I1 fix triệt để. Round 1 chỉ là info (không bắt buộc) nhưng planner đã implement đầy đủ 3 layer + test command.

---

## Regression Check (round 2 không tạo issue mới)

### Wave + Dependency Graph (giữ nguyên)

- Wave 1: [01] — skeleton + 8 sources
- Wave 2: [02, 03, 04] parallel
- Wave 3: [05] depends_on=[01,04]
- Wave 4: [06] depends_on=[01,02,03,04,05]

Acyclic, không forward-reference. **DEPENDENCY CORRECTNESS PASS**.

### Wave 2 file overlap

- 02 viết: eval/scripts/__init__.py, seed_hub.sql, cleanup.py
- 03 viết: eval/scripts/build_scanned.py + 2 PDF
- 04 viết: eval/scripts/extract_headings.py + eval/dataset/headings.json

__init__.py chỉ Plan 02 viết. mkdir -p eval/scripts/ idempotent. **WAVE PARALLELIZATION SAFE**.

### Scope Sanity (giữ nguyên — không phát sinh task mới)

| Plan | Tasks | Files | Wave | Đánh giá |
|------|-------|-------|------|----------|
| 01 | 3 | 13 | 1 | OK |
| 02 | 2 | 3 | 2 | OK (cleanup.py tăng ~30 dòng do guard) |
| 03 | 2 | 3 | 2 | OK |
| 04 | 2 | 2 | 2 | OK (logic copy scanned + fail-loud manual) |
| 05 | 3 (1 checkpoint) | 2 | 3 | OK |
| 06 | **4** (Task 0 + 1 + 2 + 3) | 3 | 4 | OK — Task 0 ngắn (~60 dòng pre-flight), Task 1 dùng lại logic Task 0 nên không nhân đôi context |

Plan 06 từ 3 task → 4 task vì có Task 0 mới (B3). Vẫn ≤ 4 → **SCOPE SANITY PASS** (4 task biên giới warning round 1, nhưng chấp nhận vì Task 0 đơn giản và độc lập).

### Coverage Audit

| Gate-prompt | Trạng thái |
|---|---|
| Mỗi success criterion có ≥ 1 plan task tạo deliverable đáp ứng? | PASS — 4 SC cover (SC3 fix B1+B2+W5, SC4 fix W2) |
| Wave parallelization an toàn? | PASS |
| Checkpoint user review ở Plan 05 rõ ràng? | PASS — gộp queries + heading PDF gốc trong 1 review |
| Plan 06 đủ logic: pre-flight → login → upload → poll → search → metrics → snapshot? | PASS — đủ flow + B3 + B2 + B1 + W2 + W5 |
| Có giả định nào không nói rõ? | PASS — pre-flight verify cả 3 dependency runtime |
| Schema hubs đúng? | PASS |
| ChromaDB v2 path đúng? | PASS |
| Embedding lock — fail loud nếu dim=0? | PASS (W5 fix) |
| Có plan trùng lặp công việc? | PASS |
| REQ-ID EVAL-01 cover full? | PASS |
| Heading recall metric — defer Phase 5 nhất quán? | PASS — CONTEXT.md + Plan 06 + Plan 04 truths đều ghi rõ |
| Filename matching dùng result.category? | PASS (B2 fix) |

### Context Compliance (revision 1 thêm decision: defer heading_recall)

CONTEXT.md ## Decisions Locked mục đã được cập nhật round 1:
- A. Queries + Heading vàng — Plan 04 (extract DOCX auto + manual PDF gốc + copy scanned) + Plan 05 (LLM draft + user review).
- B. Scanned PDF — Plan 03 pipeline DOCX → PDF → raster → image-PDF.
- C. Hub + Collection eval sandbox — Plan 02 seed_hub.sql + cleanup.py.
- D. Embedding + Script Language Python — Plan 01 pyproject.toml (pypdf>=5.0) + Plan 06 baseline.py.
- **E (mới revision 1): defer headings_recalled/missed Phase 5** — Plan 06 chỉ ghi headings_gold_count, snapshot không có 2 field defer.

**Out of Scope** L141: Heading recall metric ... defer Phase 5. → KHÔNG có plan nào implement → **PASS**.

**Deferred Ideas** không bị plan nào implement (LLM judge, hybrid retrieval, public eval set, CI auto regression) → **PASS**.

---

## Recommendation

**Verdict: PASS** — toàn bộ 9 issue đã fix đúng. Không phát hiện regression.

Plans đã sẵn sàng để chạy /gsd-execute-phase 1. Lưu ý cho executor:

1. **Wave 2 (Plan 02 + 03 + 04) chạy parallel được** — không file overlap.
2. **Plan 04 Task 2 BẮT BUỘC fill MANUAL_PDF_HEADINGS[tri_thuc_chinh_tri.pdf]** — nếu rỗng, extract_headings.py return code 3 và fail. Executor LLM phải đọc PDF qua pypdf rồi liệt kê heading thật.
3. **Plan 05 Task 3 là checkpoint:human-verify** — phải đợi user reply approved mới commit queries + heading vàng.
4. **Plan 06 cần 3 dependency runtime trước khi chạy:** backend Go up + ChromaDB up + hub eval đã seed. Pre-flight (Task 0) sẽ tự verify; nếu thiếu → executor phải start service trước theo hint.
5. **Embedder config phải hợp lệ** — provider khác rỗng + dim > 0; nếu không, baseline.py fail ngay sau login (W5 fix).

---

## Structured Issues (machine-readable)

```yaml
issues: []  # Round 2: zero issue. All 9 round-1 issues fixed.

verification_summary:
  round: 2
  blockers_round_1: 3
  blockers_remaining: 0
  warnings_round_1: 5
  warnings_remaining: 0
  info_round_1: 1
  info_remaining: 0
  fixes_verified:
    - id: B1
      status: fixed
      evidence: 01-CONTEXT.md:116,130-131 + 01-06-PLAN.md:577-591,645,713,965-969
    - id: B2
      status: fixed
      evidence: 01-CONTEXT.md:29 + 01-06-PLAN.md:535,540-541,557-558 + 01-05-PLAN.md:46,108-110
    - id: B3
      status: fixed
      evidence: 01-06-PLAN.md:135-224 (Task 0) + 301-358 (preflight_check) + 597 (goi truoc login)
    - id: W1
      status: fixed
      evidence: 01-01-PLAN.md:98 (pypdf>=5.0) + 172 (verify import) + 03-PLAN.md:317 (uses pypdf)
    - id: W2
      status: fixed
      evidence: 01-06-PLAN.md:937-962 (3-way logic) + 1019-1022 (verify automated bypass)
    - id: W3
      status: fixed
      evidence: 01-05-PLAN.md:146-153 (action) + 158-167 (verify automated, Python loop hop le)
    - id: W4
      status: fixed
      evidence: 01-04-PLAN.md:300-334 + 122-125 + 236-241 + 378
    - id: W5
      status: fixed
      evidence: 01-06-PLAN.md:471-477 + 19 + 602
    - id: I1
      status: fixed
      evidence: 01-02-PLAN.md:194-195 + 286-319 + 357 + 376

  regression_check:
    new_issues: 0
    waves_safe: true
    scope_within_budget: true
    requirement_coverage_full: true
    context_compliance: true
```

---

*Last updated: 2026-04-28 (gsd-plan-checker — round 2, verdict PASS)*
