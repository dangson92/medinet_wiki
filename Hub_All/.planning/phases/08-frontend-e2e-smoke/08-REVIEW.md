---
phase: 08-frontend-e2e-smoke
reviewed: 2026-05-18T00:00:00Z
depth: standard
files_reviewed: 13
files_reviewed_list:
  - api/.env.example
  - api/Makefile
  - api/app/config.py
  - api/app/main.py
  - api/app/routers/__init__.py
  - api/app/routers/ai_chat.py
  - api/scripts/smoke/__init__.py
  - api/scripts/smoke/boot_stack.sh
  - api/scripts/smoke/contract_diff.py
  - api/tests/integration/test_smoke_golden_path.py
  - api/tests/integration/test_vietnamese_filename.py
  - api/tests/unit/test_ai_chat.py
  - docker-compose.yml
findings:
  critical: 0
  warning: 3
  info: 5
  total: 8
status: issues_found
---

# Phase 8: Báo cáo Code Review

**Reviewed:** 2026-05-18T00:00:00Z
**Depth:** standard
**Files Reviewed:** 13
**Status:** issues_found

## Tổng kết

Review 13 file Phase 8 "Frontend E2E Smoke" — router proxy LLM mới `ai_chat.py`, script smoke (`boot_stack.sh`, `contract_diff.py`), test integration/unit, và hạ tầng (`docker-compose.yml`, `config.py`, `main.py`, `Makefile`, `.env.example`). Toàn bộ thay đổi nằm trong `api/` và hạ tầng — tuân thủ ràng buộc D6 (KHÔNG sửa frontend).

Đánh giá tổng thể: chất lượng tốt. `ai_chat.py` tách hàm lõi `run_ai_chat` để unit test sạch, containment lỗi LLM đúng (envelope `LLM_FAILED` generic, không leak trace), trích `choices[0].message.content` phòng thủ tốt. `contract_diff.py` thuần đọc file (không exec), `boot_stack.sh` có `set -euo pipefail` và verify đầy đủ. Không phát hiện lỗ hổng bảo mật Critical hay bug crash.

Các vấn đề ghi nhận: một số lệch giữa tài liệu/docstring và hành vi thực tế, một bug nhỏ trong logic Makefile target được tham chiếu, và vài điểm code quality. Không có vấn đề nào chặn ship Phase 8.

## Warnings

### WR-01: `boot_stack.sh` tham chiếu `make api-keys` không tồn tại

**File:** `api/scripts/smoke/boot_stack.sh:59`
**Issue:** Thông điệp cảnh báo khi thiếu keypair JWT hướng dẫn người dùng chạy `make api-keys`:
```
log "CẢNH BÁO: Chưa có keypair JWT tại api/keys/ — chạy 'make api-keys' trước nếu /readyz fail."
```
Nhưng `api/Makefile` KHÔNG có target `api-keys` — target sinh khoá thực tế tên là `keys` (dòng 16-17: `keys: bash scripts/generate_keys.sh`). Ngoài ra Makefile nằm trong `api/`, nên muốn chạy phải `cd api && make keys` chứ không phải `make api-keys` từ `Hub_All/`. Người vận hành làm theo hướng dẫn sẽ gặp lỗi `No rule to make target 'api-keys'` và bối rối khi `/readyz` fail vì thiếu khoá.
**Fix:** Sửa thông điệp cho khớp target thật và vị trí Makefile:
```bash
log "CẢNH BÁO: Chưa có keypair JWT tại api/keys/ — chạy 'cd api && make keys' trước nếu /readyz fail."
```

### WR-02: `_rate_limit_key` trả IP fallback khi gọi `litellm` thật vẫn tốn chi phí — nhưng test mode dùng key placeholder không đụng

**File:** `api/app/routers/ai_chat.py:16,137`
**Issue:** Docstring `ai_chat.py` (dòng 15-16) khẳng định `limiter.limit(SEARCH_LIMIT)` là "100/min/user" chống abuse đẩy chi phí LLM. Nhưng key rate-limit (`_rate_limit_key` trong `rate_limit.py:33-51`) chỉ trả `user:<sub>` khi decode JWT thành công; nếu `app.state.jwt_manager` là `None` (lifespan init JWT fail — `main.py:166` set `None` và chỉ log warning, KHÔNG crash) thì MỌI request rớt xuống `get_remote_address` fallback. Khi đó toàn bộ user sau cùng một NAT/proxy share một counter IP — vừa quá chặt (chặn nhầm user hợp lệ) vừa không phải "per-user" như docstring tuyên bố. Đồng thời `get_current_user` đã từ chối request không có JWT hợp lệ ở dòng 141, nên với endpoint này nhánh "chưa auth" của `_rate_limit_key` không bao giờ là request hợp lệ — fallback IP chỉ xảy ra đúng khi `jwt_manager is None`, tức một lỗi cấu hình. Đây là rủi ro vận hành cần ghi rõ, không phải bug code thuần tuý.
**Fix:** Không cần sửa code `ai_chat.py`. Đề xuất: (1) sửa docstring dòng 15-16 ghi rõ "per-user khi JWT manager sẵn sàng, fallback per-IP nếu JWT manager init fail"; (2) cân nhắc ở `readyz`/startup fail-fast khi `jwt_manager is None` thay vì log-soft, vì không có JWT manager thì cả auth lẫn rate-limit đều suy giảm — nhưng đây là quyết định Phase 3/skeleton design, ngoài scope Phase 8.

### WR-03: `run_ai_chat` không giới hạn kích thước/số lượng message gửi LLM

**File:** `api/app/routers/ai_chat.py:56-60,99-107`
**Issue:** `AiChatRequest.messages` là `list[AiChatMessage]` không giới hạn độ dài; `content` mỗi message là `str` không giới hạn ký tự; `system_instruction` cũng vậy. Client (hoặc attacker đã có JWT viewer) có thể gửi hàng nghìn message hoặc payload rất lớn — `run_ai_chat` forward thẳng toàn bộ vào `litellm.acompletion` (dòng 111-113). Hệ quả: chi phí token LLM tăng đột biến, hoặc provider trả lỗi context-length. Rate-limit 100/min chỉ giới hạn TẦN SUẤT, không giới hạn KÍCH THƯỚC mỗi request — một request đơn lẻ vẫn có thể rất đắt. Đây là khoảng trống của threat T-08-02-03 (abuse đẩy chi phí LLM).
**Fix:** Thêm ràng buộc Pydantic giới hạn input trước khi forward:
```python
class AiChatMessage(BaseModel):
    role: str
    content: str = Field(max_length=8000)

class AiChatRequest(BaseModel):
    messages: list[AiChatMessage] = Field(default_factory=list, max_length=50)
    system_instruction: str | None = Field(default=None, max_length=4000)
```
Pydantic raise 422 khi vượt — `http_exception_handler`/validation error envelope xử lý sạch. Nếu giá trị ngưỡng cần quyết định planner, ghi nhận vào input Plan 08-04 thay vì hardcode tuỳ tiện.

## Info

### IN-01: `api/scripts/smoke/__init__.py` rỗng nhưng `contract_diff.py` được chạy như package

**File:** `api/scripts/smoke/__init__.py:1`
**Issue:** File `__init__.py` rỗng (0 dòng nội dung). `contract_diff.py:9` ghi cách chạy `cd api && python -m scripts.smoke.contract_diff` — chế độ này cần `scripts/__init__.py` tồn tại nữa (không chỉ `scripts/smoke/__init__.py`). Nếu `api/scripts/__init__.py` chưa có thì lệnh `python -m scripts.smoke...` sẽ fail `No module named scripts`. Không nằm trong danh sách review nên chưa verify được — chỉ là điểm cần kiểm chứng.
**Fix:** Xác nhận `api/scripts/__init__.py` tồn tại; nếu không, lệnh `python -m` trong docstring nên đổi sang cách chạy trực tiếp `python api/scripts/smoke/contract_diff.py` (đã hoạt động nhờ `parents[3]` resolve path tuyệt đối).

### IN-02: `contract_diff.py` không xử lý `FileNotFoundError` khi thiếu `api.ts` hoặc router

**File:** `api/scripts/smoke/contract_diff.py:162,186`
**Issue:** `extract_frontend_endpoints` gọi `api_ts.read_text(...)` và `_extract_routes_from_file` gọi `path.read_text(...)` không bọc try/except. Nếu `frontend/src/services/api.ts` bị di chuyển/xoá, hoặc một file trong `ROUTER_FILES` bị đổi tên, script crash với `FileNotFoundError` traceback thô thay vì thông điệp rõ ràng. Với một script smoke/CI dùng exit code để phân loại, traceback thô khó chẩn đoán hơn một message có ngữ cảnh.
**Fix:** Thêm guard rõ ràng, ví dụ trong `main()`:
```python
for f in [API_TS, AUTH_ROUTER, *(ROUTERS_DIR / n for n in ROUTER_FILES)]:
    if not f.exists():
        print(f"LOI: khong tim thay file can doi chieu: {f}", file=sys.stderr)
        return 1
```

### IN-03: `_normalize_role` chỉ map `model` — role lạ vẫn forward nguyên trạng

**File:** `api/app/routers/ai_chat.py:69-76`
**Issue:** `_normalize_role` chỉ chuyển `model` → `assistant`; mọi role khác giữ nguyên. Nếu frontend (hoặc client tuỳ ý) gửi `role` ngoài tập `{user, assistant, system, model}` — ví dụ `role: "tool"` hay chuỗi rỗng — giá trị đó forward thẳng vào `litellm.acompletion` và provider có thể reject với lỗi khó hiểu, hoặc tệ hơn là diễn giải sai. Đây không phải bug bảo mật (LLM proxy, không ảnh hưởng RAG), chỉ là độ bền input.
**Fix:** Whitelist role hợp lệ, mặc định về `user` cho giá trị lạ:
```python
def _normalize_role(role: str) -> str:
    if role == "model":
        return "assistant"
    return role if role in {"user", "assistant", "system"} else "user"
```

### IN-04: `.env.example` còn comment defer Phase 7 cho LLM providers — đã lỗi thời ở Phase 8

**File:** `api/.env.example:35`
**Issue:** Dòng 35 ghi `# === LLM providers (defer Phase 7 wiring, đặt placeholder trước) ===`. Tới Phase 8, LLM đã được wire (Phase 7 ASK-01..05 hoàn tất theo ROADMAP, và `ai_chat.py` Phase 8 dùng `litellm.acompletion` trực tiếp). Comment "defer Phase 7" nay gây hiểu nhầm rằng LLM chưa wire. Chỉ là vệ sinh tài liệu, không ảnh hưởng runtime.
**Fix:** Cập nhật comment: `# === LLM providers (wired Phase 7 ASK + Phase 8 /api/ai/chat — điền key thật vào .env) ===`.

### IN-05: Lặp lại `_MockCocoindexApp` + `_make_docx_bytes` giữa hai file test integration

**File:** `api/tests/integration/test_smoke_golden_path.py:60-88`, `api/tests/integration/test_vietnamese_filename.py:44-61`
**Issue:** Class `_MockCocoindexApp` và hàm `_make_docx_bytes()` được định nghĩa gần như giống hệt trong cả hai file test. Code trùng lặp làm tăng chi phí bảo trì — sửa hành vi mock (vd thêm method `add_source`) phải sửa hai chỗ, dễ lệch. Vì hai file CỐ TÌNH chạy riêng process (DEF-05-01 — cocoindex Environment singleton), việc đặt chung trong `conftest.py` vẫn an toàn (conftest chỉ là helper, không boot app).
**Fix:** Chuyển `_MockCocoindexApp` và `_make_docx_bytes()` vào `tests/integration/conftest.py` (hoặc một module helper dùng chung) và import vào cả hai file test. Lưu ý giữ nguyên cô lập process — chỉ refactor helper, không gộp test function.

---

_Reviewed: 2026-05-18T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
