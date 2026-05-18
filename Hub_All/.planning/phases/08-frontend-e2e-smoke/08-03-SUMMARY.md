---
phase: 08-frontend-e2e-smoke
plan: 03
subsystem: api
tags: [compat, integration-test, golden-path, utf8, vietnamese, smoke, pytest]

# Dependency graph
requires:
  - phase: 08-frontend-e2e-smoke
    provides: 08-02 — router /api/ai/chat + port 8180 (api-side gap đã đóng)
  - phase: 07-ask-api
    provides: POST /api/ask + fixture mock_llm + pattern _patch_embed (test_ask_api.py)
  - phase: 06-search-api
    provides: POST /api/search/cross-hub + SearchService (embed_text query embedding)
  - phase: 05-hub-user-audit-apikey-settings
    provides: GET /api/audit-logs + audit_service (AUDIT_ACTIONS enum)
  - phase: 04-cocoindex-flow
    provides: POST /api/documents/upload + GET /api/documents/:id + FileStore UUID-rename
  - phase: 03-auth-rbac-envelope
    provides: POST /api/auth/login + fixture app_with_auth/admin_token + response envelope
provides:
  - "test_smoke_golden_path.py — golden path API SC2 verified tự động end-to-end (login→upload→search→ask→audit)"
  - "test_vietnamese_filename.py — VN filename UTF-8 SC4 verified + threat T-08-03-01 (no path traversal)"
  - "Input cho 08-04 manual checklist: golden path KHÔNG sinh audit entry (auth.login/document.upload không enqueue)"
affects: [08-04]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Golden path E2E gói thành 1 test function tuần tự (DEF-05-01 — tránh nhiều test cùng dùng app fixture trong cùng process)"
    - "Patch query embedding (search_service.embed_text) song song mock_llm — search/ask embed câu query qua embed_text, mock_llm chỉ patch litellm.acompletion"
    - "Verify path traversal qua file_path stem khớp UUID4 — chứng minh cơ chế FileStore UUID-rename đang bảo vệ"

key-files:
  created:
    - api/tests/integration/test_smoke_golden_path.py
    - api/tests/integration/test_vietnamese_filename.py
  modified: []

decisions:
  - "Helper test (seed hub, make_docx, patch embedding) giữ LOCAL trong từng file test — KHÔNG thêm vào conftest.py (plan dự kiến sửa conftest; thực tế fixture conftest hiện có đủ tái dùng, helper local theo precedent test_ask_api.py)"
  - "Audit assert linh hoạt theo plan Task 1 step 7 — code KHÔNG enqueue auth.login/document.upload dù có trong AUDIT_ACTIONS; test verify contract GET /api/audit-logs (200 + list) thay vì hardcode N entry"
  - "Golden path KHÔNG assert chunk_count>0 — không có cocoindex runtime trong test; status document có thể 'failed' (mock generate 0 chunk) — đó là phần manual UAT 08-04"

# Metrics
metrics:
  duration: ~25 phút
  completed: 2026-05-18
  tasks: 2
  files_created: 2
  files_modified: 0
  commits: 3
---

# Phase 8 Plan 03: Test Suite Golden Path + Vietnamese Filename Summary

Hai file test integration tự động chứng minh golden path API contract (ROADMAP
Phase 8 SC2) và Vietnamese filename UTF-8 (SC4) qua FastAPI in-process (httpx
ASGITransport) — LLM + query embedding mock; chạy per-file né DEF-05-01. Plan
08-04 (manual UAT) chỉ còn phần render UI 11 trang cần mắt người.

## Tasks hoàn thành

### Task 1 — Test suite golden path API end-to-end (`test_smoke_golden_path.py`)

1 test `test_golden_path_end_to_end` (`@pytest.mark.critical`) chạy tuần tự
toàn chuỗi golden path trong 1 test function (DEF-05-01):

1. Seed hub `hub_y_te` qua engine + gán admin vào hub (user_hubs).
2. Login admin → 200, `data.access_token` là chuỗi không rỗng.
3. Upload DOCX (tạo qua `python-docx` in-memory) vào hub → 202, lấy `data.id`,
   `data.name` khớp tên file.
4. GET `/api/documents/{id}` → 200, `name` khớp tên file, `status` thuộc vòng
   đời hợp lệ `{pending, processing, completed, failed}`.
5. POST `/api/search/cross-hub` `{query, hub_ids:[hub], top_k:10}` → 200, key
   `results` là list (rỗng — chunks table không có ingest thật).
6. POST `/api/ask` (mock_llm) → 200, `answer` là str, `citations` là list.
7. GET `/api/audit-logs` (admin) → 200, envelope `data` là list.

4 endpoint golden path đều được hit qua `httpx.AsyncClient` + `ASGITransport`.

### Task 2 — Test Vietnamese filename UTF-8 (`test_vietnamese_filename.py`)

1 test `test_vietnamese_filename_roundtrip` (`@pytest.mark.critical`):

- Upload file tên `"Khám bệnh đa khoa.docx"` (literal Unicode qua httpx
  multipart) → 202, `data.name` == chuỗi tiếng Việt nguyên vẹn (không mojibake).
- GET `/api/documents/{id}` → `data.name` vẫn == chuỗi tiếng Việt nguyên vẹn.
- Path traversal guard (threat T-08-03-01): `file_path` không chứa `..`, tên
  file đĩa KHÔNG dùng tên gốc, stem khớp pattern UUID4, nằm trong
  `file_store_dir`.

## Cơ chế bảo vệ path traversal (threat T-08-03-01 — mitigated)

`FileStore.save()` (`api/app/services/file_store.py`) sinh tên file trên đĩa =
`<uuid4>.<ext>` — chỉ lấy extension từ filename gốc, KHÔNG dùng basename gốc.
Vì vậy tên file tiếng Việt (hoặc chứa `../`) KHÔNG bao giờ vào path đĩa. Cơ chế
bảo vệ là **UUID rename** (KHÔNG sanitize). Test xác nhận chủ động: `file_path`
stem là UUID4 hợp lệ, không `..`, nằm trong `file_store_dir`. Threat
T-08-03-01-01 đóng — KHÔNG phát hiện traversal, KHÔNG BLOCKER.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Patch query embedding cho cross-hub search + ask**
- **Found during:** Task 1, bước 5 (cross-hub search).
- **Issue:** Plan `<interfaces>` chỉ nêu LLM call mock qua `mock_llm`. Nhưng
  `/api/search/cross-hub` (và `/api/ask`) gọi `embed_text` để embed câu query —
  bước này KHÔNG nằm trong `mock_llm` (`mock_llm` chỉ patch
  `litellm.acompletion`). Với `OPENAI_API_KEY` placeholder M2 (`sk-replace-me`),
  `embed_text` thật → 401 → search trả 500 `EMBEDDING_FAILED`. Test FAIL ở bước 5.
- **Fix:** Thêm helper `_patch_query_embedding` monkeypatch
  `app.services.search_service.embed_text` trả vector 1536-dim deterministic —
  cùng pattern `_patch_embed` của `test_ask_api.py` (Phase 7). Golden path verify
  flow + SHAPE response, KHÔNG verify chất lượng embedding.
- **Files modified:** `api/tests/integration/test_smoke_golden_path.py`.
- **Commit:** `467e3f5`.

**2. [Rule 1 - Bug assumption] Audit log: golden path KHÔNG sinh audit entry**
- **Found during:** Task 1, bước 7 (audit log).
- **Issue:** Plan `<behavior>` giả định `GET /api/audit-logs` chứa ít nhất entry
  `auth.login` ("login vừa thực hiện đã enqueue audit"). Verify code thực tế:
  `AUDIT_ACTIONS` (audit_service.py) khai báo `auth.login` + `document.upload`
  trong enum NHƯNG **KHÔNG có code nào enqueue 2 action này** —
  `app/auth/service.py` chỉ structured-log `auth_login_success`, upload router
  KHÔNG gọi `enqueue_audit`. Action THỰC SỰ enqueue:
  `hub.create`/`hub.update`/`user.create`/`security.hub_isolation_violation`
  (qua `enqueue_audit`) + `document_delete` (synchronous INSERT, action string
  có gạch dưới). → Golden path login→upload→search→ask sinh **0 audit entry**.
- **Fix:** Plan Task 1 step 7 đã lường trước ("KHÔNG hardcode '4 entry' — assert
  linh hoạt... nếu không assert ≥1 và ghi chú trong SUMMARY action nào không
  được log"). Theo đúng fallback đó: test verify endpoint `GET /api/audit-logs`
  đúng contract (200 + envelope `data` là list, admin đọc được) — phần kiểm
  được bằng máy. "Audit thấy N entry sau golden path" chuyển sang 08-04 manual
  UAT.
- **Files modified:** `api/tests/integration/test_smoke_golden_path.py`.
- **Commit:** `467e3f5`.

### Lệch nhỏ so với plan (không cần fix)

- Plan `files_modified` liệt kê `api/tests/integration/conftest.py`. Thực tế
  KHÔNG sửa conftest — fixture hiện có (`app_with_auth`, `admin_token`,
  `mock_llm`, `admin_user`) đủ tái dùng nguyên trạng; helper riêng (seed hub,
  make_docx, patch embedding) giữ LOCAL trong từng file test theo precedent
  `test_ask_api.py`. Ít thay đổi hơn plan — chấp nhận.

## Input cho Plan 08-04 (manual UAT checklist)

- **Audit log behavior:** Golden path qua UI (login → upload → search → ask)
  KHÔNG sinh audit entry — `GET /api/audit-logs` sẽ trống nếu chưa có thao tác
  `hub.create`/`user.create`/`hub.update`/document delete. Manual UAT muốn thấy
  audit entry cần thực hiện 1 trong các thao tác đó. Cân nhắc: nếu requirement
  thật sự cần audit `auth.login`/`document.upload`, đây là gap code cần báo
  (defer — ngoài scope plan test này).
- **chunk_count:** Test integration không có cocoindex runtime → document sau
  upload có thể `status='failed'` (mock generate 0 chunk). Manual UAT 08-04 với
  cocoindex thật mới verify được `status='completed'` + `chunk_count>0`.

## Known Stubs

Không có. Hai file test là deliverable hoàn chỉnh, không chứa stub/placeholder.

## Verification

- `pytest tests/integration/test_smoke_golden_path.py` — 1 passed (per-file).
- `pytest tests/integration/test_vietnamese_filename.py` — 1 passed (per-file).
- `pytest -m critical` từng file — 2 test critical PASS.
- `ruff check` clean trên cả 2 file test.
- D6 tuân thủ: KHÔNG file nào trong `frontend/` bị sửa; chỉ thêm 2 file test
  trong `api/tests/integration/`.

## Self-Check: PASSED

- FOUND: api/tests/integration/test_smoke_golden_path.py
- FOUND: api/tests/integration/test_vietnamese_filename.py
- FOUND commit: 467e3f5 (test 08-03 golden path)
- FOUND commit: 74a7e3c (test 08-03 VN filename)
