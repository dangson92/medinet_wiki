# Deferred Items — Phase 5

Mục out-of-scope phát hiện trong lúc execute Phase 5, KHÔNG fix tại plan hiện tại.

## DEF-05-01 — cocoindex Environment không re-open được trong cùng process (pre-existing Phase 4)

**Phát hiện:** Plan 05-01 Task 4 (test_audit_logger.py).

**Mô tả:** Fixture `app_with_auth` (tests/integration/conftest.py) chạy full
FastAPI lifespan gồm `setup_cocoindex()`. Cocoindex 1.0.3 `core.Environment`
là process-global singleton — KHÔNG re-open được sau khi đã open + close. Mọi
test file dùng `app_with_auth` cho >1 test sẽ FAIL từ test thứ 2 với
`RuntimeError: environment already open in this program`.

**Bằng chứng:** `uv run pytest tests/integration/test_documents_list_delete.py`
→ 1 passed, 6 errors (tất cả error đều `environment already open`). Đây là
file Phase 4, KHÔNG do Plan 05-01 gây ra.

**Tác động:** Test integration dùng `app_with_auth` nhiều test cùng module
không chạy được. Plan 05-01 Task 4 né bằng fixture `audit_db` tự cấp (chỉ init
DB engine, không boot cocoindex). Wave 3-4 Phase 5 (hub/user/apikey CRUD test)
sẽ cần giải pháp chung — ví dụ: fixture cocoindex mock, hoặc tách
`setup_cocoindex` khỏi lifespan trong test mode, hoặc module-scope app fixture.

**Đề xuất:** Plan 05-06 (wiring + integration test) hoặc Phase 10 hardening
xử lý — thêm fixture `app_no_cocoindex` hoặc mock `setup_cocoindex` ở conftest.

**KHÔNG fix tại Plan 05-01** — ngoài scope (pre-existing, không do task này tạo).
