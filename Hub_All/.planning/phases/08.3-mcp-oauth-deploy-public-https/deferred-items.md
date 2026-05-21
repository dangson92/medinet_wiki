# Deferred items — Phase 08.3

## Plan 07 deferred (logged 2026-05-21)

### Pre-existing ruff errors trong `tests/test_path_prefix_wrapper.py` — out of scope Plan 07

`ruff check mcp_app/ tests/` báo 4 errors:
- E402 module-level import not at top of file (dòng 475, 477) — pattern test
  file đặt import inline trước test section.
- UP012 unnecessary UTF-8 `encoding` argument trong `.encode("utf-8")` (dòng
  558, 770).

Pre-existing từ trước Plan 07 (verify bằng `git log -- mcp_service/tests/
test_path_prefix_wrapper.py` — chạm cuối ở commit `282abaa` "fix(08.3):
_BasicAuthFormShim convert Authorization Basic → form body" — TRƯỚC Plan 07).
Plan 07 KHÔNG sửa file này (chỉ chạm provider.py / store.py / login.py /
server.py / conftest.py / test_oauth_login.py / test_oauth_store.py).

Theo SCOPE BOUNDARY rule (deviation_rules): "Pre-existing warnings... in
unrelated files are out of scope. Do NOT fix them."

**Đề xuất xử lý:** vá ở Plan 09 (test thêm) cùng với refactor test khác,
hoặc tạo `chore` commit riêng. KHÔNG block Plan 07 đóng.
