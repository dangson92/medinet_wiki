# Deferred Items — Phase 5

Mục out-of-scope phát hiện trong lúc execute Phase 5, KHÔNG fix tại plan hiện tại.

## DEF-05-01 — cocoindex Environment không re-open được trong cùng process (pre-existing Phase 4)

**TRẠNG THÁI: RESOLVED** (2026-05-17, commit `2796c13`) — fix-task test-infra Wave 3-4.

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

**Giải pháp (commit `2796c13`):** Escape-hatch env-flag (option ít xâm lấn nhất).
- `app/main.py` lifespan: khi env `COCOINDEX_SKIP_SETUP=1`, bỏ qua
  `setup_cocoindex()` hoàn toàn → singleton `core.Environment` không bao giờ
  được open trong test process. Production không set flag → fail-fast giữ nguyên.
- `tests/integration/conftest.py` fixture `app_with_auth`: set
  `COCOINDEX_SKIP_SETUP=1`. Test cần `cocoindex_app` (A4 BackgroundTask) cấp
  mock vào `app.state.cocoindex_app` sau lifespan (xem `mock_cocoindex_app`).
- Cùng commit sửa 2 lỗi cùng class "process-global state leak giữa test" lộ ra
  khi fixture dùng được nhiều test: (1) `audit_service._queue` asyncio.Queue
  module-global treo `queue.get()` trên event loop test sau — fixture gọi
  `reset_queue()`; (2) helper `_create_hub` thiếu cột NOT NULL migration 0003.

**Verify:** `pytest tests/integration/test_documents_list_delete.py` → 7 passed,
0 errors (trước đó 1 passed, 6 errors). Full check: `test_watchdog.py` +
`test_documents_list_delete.py` → 13 passed, 0 errors.

---

## DEF-05-02 — test_watchdog.py fixture chưa cập nhật cột `hubs.code` NOT NULL (pre-existing post-05-01)

**TRẠNG THÁI: RESOLVED** (2026-05-17, commit `a36fde9`) — fix-task test-infra Wave 3-4.

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

**Giải pháp (commit `a36fde9`):** Helper `_seed_hub_document` trong
`tests/unit/test_watchdog.py` cập nhật INSERT `hubs` truyền `code` + `subdomain`
(migration 0003 drop server_default 2 cột này → row mới phải set tường minh).
Dùng giá trị unique `hub-{hex}` cho `code` vì có constraint `uq_hubs_code`.
`hubs.status` NOT NULL giữ `server_default 'active'` nên không cần truyền.

**Verify:** `pytest tests/unit/test_watchdog.py` → 6 passed, 0 errors.

---

## DEF-05-03 — test_ingest_e2e::test_e2e_upload_docx_to_chunks_completed cần cocoindex thật

**TRẠNG THÁI: RESOLVED** (2026-05-18) — fix-task 3-test Phase 5.

**Phát hiện:** Plan 05-06 (chạy `pytest -m critical` per-file).

**Mô tả:** `test_e2e_upload_docx_to_chunks_completed` (Phase 4 Plan 04-06) assert
`app.state.cocoindex_app is not None` rồi chờ chunks tạo qua cocoindex flow thật.
Fixture `app_with_auth` (conftest) set `COCOINDEX_SKIP_SETUP=1` (DEF-05-01 fix) →
lifespan bỏ qua `setup_cocoindex()` → `app.state.cocoindex_app=None` → test fail
`AssertionError: Plan 04-07 architectural regression`.

**Bằng chứng:** `pytest -m critical tests/integration/test_ingest_e2e.py` →
1 passed, 1 failed. Lỗi: `assert None is not None`. `COCOINDEX_SKIP_SETUP` env
có TRƯỚC Plan 05-06 (đã trong conftest từ DEF-05-01 fix) — test này đã không
tương thích với shared fixture từ trước Plan 05-06.

**Tác động:** 1 critical test fail trong `pytest -m critical` (HARD-03 gate).
KHÔNG ảnh hưởng E4 hub-isolation hay wiring của Plan 05-06. Mâu thuẫn cấu trúc:
test E2E cocoindex thật vs shared fixture skip cocoindex (DEF-05-01).

**Đề xuất:** Phase 10 hardening — hoặc (a) cấp fixture riêng `app_with_cocoindex`
chạy module-scope đơn lẻ cho test_ingest_e2e, hoặc (b) đánh dấu test này chạy
tách process (pytest-forked) khỏi suite chung, hoặc (c) di chuyển ra eval suite
Phase 9. Là quyết định cấu trúc test-infra — KHÔNG fix tại Plan 05-06 (Rule 4).

**KHÔNG fix tại Plan 05-06** — ngoài scope (file test Phase 4, pre-existing
incompatibility với DEF-05-01 fixture; fix cần thay đổi kiến trúc test-infra).

**Giải pháp (2026-05-18):** Option (a) — fixture riêng cho `test_ingest_e2e.py`.
- `tests/integration/test_ingest_e2e.py` thêm fixture session-scope `_cocoindex_env`
  chạy `setup_cocoindex()` ĐÚNG 1 LẦN cho cả test session + `stop_cocoindex()` 1 lần
  ở finalizer (tôn trọng constraint DEF-05-01 — `core.Environment` singleton mở 1 lần).
- File này override (shadow) fixture `app_with_auth` của conftest: GIỮ
  `COCOINDEX_SKIP_SETUP=1` (lifespan KHÔNG start/stop cocoindex per-test), gắn real
  `cocoindex_app` session-scoped vào `app.state` SAU lifespan startup, và CLEAR
  `app.state.cocoindex_app=None` TRƯỚC lifespan shutdown — nếu không, main.py shutdown
  gọi `stop_cocoindex()` đóng Environment → test thứ 2 FAIL `pool is closed`.
- Phát hiện thêm khi fix: cocoindex zero-chunks ("New Gap A" — 04-VERIFICATION.md)
  KHÔNG phải lỗi flow mà là **A4 BackgroundTask race**: `trigger_cocoindex_update`
  chạy `update_blocking()` TRƯỚC khi transaction INSERT `documents` row commit visible
  cho cocoindex asyncpg pool → flow fetch 0 rows → 0 chunks. Bằng chứng: re-trigger
  `update_blocking()` SAU khi row đã commit → flow tạo chunks bình thường (2 chunks).
  E2E test thêm helper `_reconcile_document_status` re-trigger update_blocking +
  reconcile `documents.status` sau upload (row chắc chắn đã commit).

**Verify:** `pytest tests/integration/test_ingest_e2e.py` → 3 passed, 0 errors.
`pytest -m critical` → 57 passed, 0 failed (trước fix-task: 3 failed, 54 passed).

---

## DEF-05-04 — alembic drift: model `Hub` thiếu UniqueConstraint `uq_hubs_code`

**TRẠNG THÁI: RESOLVED** (2026-05-18) — fix-task 3-test Phase 5.

**Phát hiện:** fix-task (chạy `pytest -m critical`).

**Mô tả:** Migration 0003 (Plan 05-01) `op.create_unique_constraint("uq_hubs_code",
"hubs", ["code"])` tạo unique constraint trên `hubs.code`, NHƯNG model SQLAlchemy
`Hub` (`app/models/hub.py`) khai báo `code` không có `unique=True` / không có
`UniqueConstraint` trong `__table_args__`. `alembic check` sau `upgrade head` phát
hiện drift: `remove_constraint UniqueConstraint(code, table=hubs)` — autogenerate
muốn xoá constraint có trong DB nhưng không có trong model.

**Bằng chứng:** `test_alembic_check_no_drift_after_upgrade` +
`test_phase4_migration_no_drift` FAIL với
`AutogenerateDiffsDetected: [('remove_constraint', UniqueConstraint(Column('code'...`.

**Tác động:** 2 critical migration-drift test fail. Pre-existing từ Plan 05-01
(migration 0003 + model `Hub` không nhất quán) — model thiếu khai báo constraint.

**Giải pháp (2026-05-18):** `app/models/hub.py` thêm `UniqueConstraint("code",
name="uq_hubs_code")` vào `Hub.__table_args__` (khớp tên constraint migration 0003
tạo). Chỉ sửa model — migration 0003 giữ nguyên (intent `code` unique đúng theo W1).

**Verify:** `test_alembic_check_no_drift_after_upgrade` +
`test_phase4_migration_no_drift` → 2 passed.
