# 02-CHECK — Plan-checker Phase 2 (Docling Service Python Sidecar) — ROUND 2

**Ngày check:** 2026-04-28
**Người check:** gsd-plan-checker (Opus 4.7 1M)
**Plans verified:** 8 (02-01 → 02-08)
**Loop iteration:** 2 / 3
**Goal verify:** Service Python FastAPI chạy ổn định trong Docker Compose, POST /v1/process trả chunks giàu metadata theo Docling, sẵn sàng Phase 3 wire.

---

## VERDICT: PASS — sẵn sàng `/gsd-execute-phase 2`

Tất cả 5 BLOCKER (B1-B5) + 4 WARNING (W3-W6) round 1 đã được fix đúng và đầy đủ trong plans revised. Coverage 14/14 REQ Phase 2 thực tế (sau khi REQUIREMENTS.md move EXTRACT-05 sang Phase 3). Plans đủ điều kiện execute.

---

## 1. Verification từng issue round 1

### BLOCKER

#### B1 — EXTRACT-05 orphan → FIXED

- **Action taken (planner + roadmapper):** REQUIREMENTS.md line 114 đã update — EXTRACT-05 move sang Phase 3 với note "moved 2026-04-28 — fallback policy thuộc WIRE Phase 3".
- **Verify trên plans:** `grep "EXTRACT-05" 02-*PLAN.md` chỉ trả về reference trong ghi chú revision (Plan 02-08 line 46, 422, 427) — KHÔNG còn xuất hiện trong frontmatter `requirements:` của bất kỳ plan nào (02-06 và 02-08 đã clean).
- **Status:** PASS

#### B2 — Docling tokenizer import path → FIXED

- **Plan 02-04:** chunker.py dùng `HybridChunker(tokenizer="cl100k_base", max_tokens=512, merge_peers=True)` — string overload đúng yêu cầu.
- **KHÔNG còn import OpenAITokenizer / BaseTokenizer manual.** Verify guard cuối Task 1 enforce.
- **Task 0 mới (verify-import fail-loud):** chạy pip install -e .[dev] + 2 lệnh python verify import + string overload accept. Nếu fail → STOP escalate.
- **Plan 02-01:** pyproject.toml pin `docling==2.91.0` exact (line 134), KHÔNG còn wildcard 2.91.* — verify guard regex chặn.
- **Status:** PASS

#### B3 — Table HTML + Figure caption test → FIXED

- **Plan 02-07** thêm file mới `tests/test_table_figure.py` với 2 test case:
  - `test_table_html_preserved` (line 466) — assert is_table=True + chuỗi `<table` + `<thead`/`<tbody` trong table_html.
  - `test_figure_caption_marker` (line 487) — regex pattern marker figure caption.
- **2 fixture mới:** `tests/fixtures/sample_with_table.pdf` + `sample_with_figure.pdf` (binary commit).
- **Script generate deterministic (đáp ứng I2):** `tests/fixtures/generate_fixtures.py` dùng reportlab + pillow sinh fixture, commit binary vào git → reproducibility tốt.
- **Marker @pytest.mark.slow** cho 2 test (cho phép skip ở fast loop, document trong README Plan 02-08).
- **Status:** PASS

#### B4 — Test 504 timeout → FIXED

- **Plan 02-07** thêm file mới `tests/test_limits.py` với `test_504_when_timeout` (line 530):
  - monkeypatch.setenv DOCLING_REQUEST_TIMEOUT_SEC=1 ép timeout 1s.
  - monkeypatch.setattr DoclingExtractor.extract bằng slow_extract với time.sleep(999) → trigger asyncio.timeout(1).
  - Assert response.status_code == 504 + body detail error là request_timeout + timeout_sec == 1.
- **Bonus:** kèm test_413_payload_too_large cho cùng SC5.
- **Status:** PASS

#### B5 — Lifespan readyz semantics → FIXED

- **Plan 02-06 main.py lifespan** phân biệt rõ 3 case:
  - **(a) ImportError docling** → set_models_ready(False) + log error docling_library_unavailable critical=True → /readyz 503 vĩnh viễn.
  - **(b) warm dummy fail (transient)** → set_models_ready(True) + log warning warm_dummy_failed_but_library_ok → /readyz 200 (request đầu chậm).
  - **(c) warm OK** → set_models_ready(True) + log info models_warmed state=ready → /readyz 200.
- **api/health.py:** _models_ready bool = False mặc định, comment ghi rõ B5 semantics. /readyz trả 503 reason=docling_library_unavailable khi _models_ready=False.
- **Bảng tóm tắt 3 case** ghi explicit cuối Plan 02-06 action.
- **Verify guard:** kiểm pattern ImportError + set_models_ready(False) + set_models_ready(True) đều có trong main.py.
- **Status:** PASS


### WARNING

#### W3 — Wave 2 deps `core/__init__.py` → FIXED

- **Plan 02-01 must_haves.truths line 29:** explicit ghi gate W3 — core/__init__.py + api/__init__.py + observability/__init__.py PHẢI tồn tại sau Plan 01 trước khi Wave 2 spawn.
- **Plan 02-01 artifacts:** 3 entry __init__.py rõ ràng với note "Package marker rỗng — gate cho Wave 2".
- **Plan 02-01 Task 2 action line 235:** ghi rõ W3 — Wave 2 dependency gate + lý do tránh ImportError khi Wave 2 plan chạy song song.
- **Status:** PASS

#### W4 — request_id propagation test → FIXED

- **Plan 02-07 file mới `tests/test_logging.py`** với `test_request_id_propagated_to_log` (line 577):
  - Generate rid = f"test-w4-{uuid.uuid4()}".
  - POST /v1/process với header X-Request-Id: rid.
  - capsys.readouterr() capture stdout structlog JSON.
  - Assert rid in captured.out.
- **Conftest:** os.environ.setdefault DOCLING_LOG_FORMAT=json đảm bảo structlog output JSON cho test này.
- **Status:** PASS

#### W5 — ImageFormatOption → FIXED

- **Plan 02-03 action line 142-145:** import ImageFormatOption từ docling.document_converter.
- **Line 201-207:** format_options khai báo CẢ PdfFormatOption (cho PDF) lẫn ImageFormatOption(pipeline_options=pipe_opts) (cho IMAGE).
- **Note fallback (line 197-200, 278):** nếu ImageFormatOption(pipeline_options=...) raise validation error runtime → bỏ entry IMAGE, KHÔNG dùng PdfFormatOption cho IMAGE.
- **Verify guard:** kiểm pattern ImageFormatOption enforce.
- **Status:** PASS

#### W6 — Smoke PDF reference → FIXED

- **Plan 02-08 must_haves.truths line 27-29:** explicit reference 2 file:
  - eval/dataset/sources/tri_thuc_chinh_tri.pdf
  - eval/dataset/scanned/DMD_T1-01_scanned.pdf (commit 045d29b)
- **Plan 02-08 README content (Smoke section line 167-174):** block W6 callout ghi rõ ls -la 2 file trước smoke + fallback "ls eval/dataset/sources/*.pdf | head -1" nếu thiếu.
- **Plan 02-08 Task 2 checkpoint (Option A line 336-341):** lệnh ls -la 2 file dataset trước khi build.
- **Verify guard:** README phải chứa tri_thuc_chinh_tri.pdf + DMD_T1-01_scanned.pdf.
- **Status:** PASS

---

## 2. Coverage Matrix updated (REQ x Plan)

Sau update REQUIREMENTS.md (EXTRACT-05 → Phase 3), Phase 2 cần cover **14 REQ-IDs**:

| REQ-ID | Plans claim trong frontmatter | Status |
|--------|--------------------------------|--------|
| DSVC-01 | 02-06, 02-07, 02-08 | OK |
| DSVC-02 | 02-05, 02-07, 02-08 | OK |
| DSVC-03 | 02-03, 02-08 | OK |
| DSVC-04 | 02-06, 02-07, 02-08 | OK |
| DSVC-05 | 02-01, 02-02, 02-08 | OK |
| DSVC-06 | 02-01, 02-06, 02-07, 02-08 | OK |
| EXTRACT-01 | 02-03, 02-07 | OK |
| EXTRACT-02 | 02-03, 02-07, 02-08 | OK |
| EXTRACT-03 | 02-05, 02-07, 02-08 | OK |
| EXTRACT-04 | 02-05, 02-07, 02-08 | OK |
| CHUNK-01 | 02-04 | OK |
| CHUNK-02 | 02-04 | OK |
| CHUNK-03 | 02-05, 02-06 | OK |
| CHUNK-04 | 02-04 | OK |

**Coverage:** 14/14 REQ Phase 2 thực tế (sau move EXTRACT-05). EVAL-01 đã ở Phase 1, CHUNK-05 ở Phase 3.


---

## 3. SC x Plan (Success Criteria coverage)

| SC | Mô tả | Plan deliver | Status round 2 |
|----|-------|--------------|----------------|
| SC1 | healthz/readyz container healthy | 02-06 (lifespan B5) + 02-07 (test_health) + 02-08 (smoke) | PASS (B5 fixed) |
| SC2 | /v1/process schema DSVC-02 | 02-05 + 02-06 + 02-07 (assert 10 field) + 02-08 (smoke tri_thuc_chinh_tri.pdf) | PASS |
| SC3 | Scanned PDF VN OCR | 02-03 (Tesseract vie+eng) + 02-07 (test_ocr expect VN tokens) + 02-08 (smoke DMD_T1-01_scanned.pdf) | PASS |
| SC4 | Table HTML + figure caption | 02-05 (logic) + 02-07 (test_table_figure B3) + 02-08 (smoke) | PASS (B3 fixed) |
| SC5 | 413 + 504 + request_id in log | 02-06 (handler) + 02-07 (test_limits B4 + test_logging W4) + 02-08 (smoke 413) | PASS (B4 + W4 fixed) |

---

## 4. Trả lời 9 gate-prompts (round 2)

| # | Câu hỏi | Verdict round 1 | Verdict round 2 |
|---|---------|----------------|----------------|
| 1 | Mỗi SC có >= 1 plan task? | PARTIAL | YES (B3+B4 đã add test cho SC4+SC5) |
| 2 | Tất cả REQ Phase 2 cover? | NO (B1) | YES (14/14 sau move EXTRACT-05) |
| 3 | Wave 2 parallel an toàn? | YES | YES (W3 gate explicit) |
| 4 | Plan 02-08 fallback Docker fail? | YES | YES (Option B defer giữ nguyên) |
| 5 | Docling API signatures sai? | POTENTIAL | MITIGATED (B2 string overload + Task 0 verify-import fail-loud + W5 ImageFormatOption) |
| 6 | Tokenizer cl100k_base + per-request override? | PARTIAL | PASS (string overload, _validate_tokenizer_name fail-loud cho name unknown) |
| 7 | Lifespan warm models async đúng? | NO (B5) | YES (3 case explicit) |
| 8 | structlog JSON + request_id propagate? | YES (arch) / NO (test) | YES + test (W4 capsys) |
| 9 | Giả định môi trường (Docker/OS)? | PARTIAL | PARTIAL (giữ — README Plan 02-08 đã add Windows note PowerShell cho dd) |

---

## 5. Issues còn lại (info-level, không blocker)

### I1 — Image final ~2.5GB
CONTEXT đã chấp nhận. Defer M3 nếu cần optimize.

### I4 — ROADMAP.md chưa đồng bộ với REQUIREMENTS.md (mới phát hiện round 2)
- ROADMAP.md line 62 vẫn liệt kê EXTRACT-05 trong Requirements Phase 2.
- REQUIREMENTS.md line 114 đã move sang Phase 3.
- **Impact:** Cosmetic — REQUIREMENTS.md là source of truth, plans đã đồng bộ với REQUIREMENTS.md.
- **Suggest:** Roadmapper update ROADMAP.md line 62 để loại EXTRACT-05 và line 90 (Phase 3 Requirements) thêm EXTRACT-05. KHÔNG block execute Phase 2.

### I5 — Test phụ thuộc Tesseract vie+eng cài sẵn (mới phát hiện round 2)
- test_ocr.py + smoke SC3 yêu cầu Tesseract vie language pack.
- README Plan 02-08 có hướng dẫn cài (line 110-115) nhưng nếu CI environment chưa có → test sẽ fail.
- **Mitigation đã có:** Marker @pytest.mark.slow cho phép skip ở fast loop. Smoke trong Docker container đã apt-get install tesseract-ocr-vie (Plan 02-01 Dockerfile line 100).
- **Status:** Acceptable — local dev cần cài, CI/Docker đã cover.

---

## 6. Recommendation

**PASS Round 2 — Plans sẵn sàng `/gsd-execute-phase 2`.**

Tất cả 5 BLOCKER (B1-B5) clear. 4 WARNING (W3-W6) clear. 2 info issue mới phát hiện (I4, I5) không block execute.

**Next action cho orchestrator:**
1. Spawn `/gsd-execute-phase 2` — bắt đầu Wave 1 (Plan 02-01 skeleton).
2. (Optional) Roadmapper đồng bộ ROADMAP.md với REQUIREMENTS.md để loại bỏ I4 cosmetic mismatch — KHÔNG block.

**Loop status:** 2 / 3 — KHÔNG cần round 3.

---

*File này là output của Revision Gate (gates.md) round 2. Plans pass — không escalate user.*
