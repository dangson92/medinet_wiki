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

---

## DEF-05-02 — test_watchdog.py fixture chưa cập nhật cột `hubs.code` NOT NULL (pre-existing post-05-01)

**Phát hiện:** Plan 05-02 (regression check `uv run pytest tests/unit`).

**Mô tả:** 5 test trong `tests/unit/test_watchdog.py` FAIL với
`asyncpg.exceptions.NotNullViolationError: null value in column "code" of
relation "hubs"`. Migration 0003 (Plan 05-01 Task 1) thêm cột `hubs.code`
NOT NULL nhưng helper insert hub trong `test_watchdog.py` (Phase 4) chưa
truyền `code` → vi phạm NOT NULL constraint.

**Bằng chứng:** `uv run pytest tests/unit/test_watchdog.py::test_watchdog_skips_pending`
→ NotNullViolationError trên `hubs.code`. Plan 05-02 KHÔNG touch bảng `hubs`,
watchdog, hay file test này.

**Tác động:** 5 watchdog unit test fail. KHÔNG ảnh hưởng hub isolation /
rate-limit của Plan 05-02. Pre-existing — do migration 0003 (05-01), KHÔNG do
Plan 05-02 gây ra; chỉ lộ ra khi 05-02 chạy full unit suite làm regression check.

**Đề xuất:** Plan cập nhật helper insert hub trong `test_watchdog.py` truyền
`code` (+ `subdomain`/`status` nếu cần). Wave 3 (05-03 Hub CRUD) hoặc Phase 10
hardening xử lý — cùng lúc rà các test fixture insert `hubs` khác.

**KHÔNG fix tại Plan 05-02** — ngoài scope (file test Phase 4, pre-existing do 05-01).
