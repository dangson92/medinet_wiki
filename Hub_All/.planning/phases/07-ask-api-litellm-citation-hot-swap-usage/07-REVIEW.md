---
phase: 07-ask-api-litellm-citation-hot-swap-usage
reviewed: 2026-05-18T00:00:00Z
depth: standard
files_reviewed: 11
files_reviewed_list:
  - Hub_All/api/app/main.py
  - Hub_All/api/app/routers/__init__.py
  - Hub_All/api/app/routers/ask.py
  - Hub_All/api/app/routers/usage.py
  - Hub_All/api/app/schemas/ask.py
  - Hub_All/api/app/schemas/rag_config.py
  - Hub_All/api/app/schemas/usage.py
  - Hub_All/api/app/services/ask_prompt.py
  - Hub_All/api/app/services/ask_service.py
  - Hub_All/api/app/services/rag_config_service.py
  - Hub_All/api/app/services/usage_service.py
findings:
  critical: 0
  warning: 5
  info: 6
  total: 11
status: issues_found
---

# Phase 7: Báo cáo Code Review

**Thời điểm review:** 2026-05-18
**Độ sâu:** standard (đọc đầy đủ từng file + kiểm tra chéo import/export với search_service, dependencies, response, embedder)
**Số file review:** 11 file nguồn (test file ngoài scope severity — chỉ tham chiếu)
**Trạng thái:** issues_found

## Tóm tắt

Phase 7 lắp ráp Ask API (LiteLLM non-streaming), citation parser `[N]`→`chunk_id`,
usage logging và rag-config hot-swap với dimension guard. Tổng thể chất lượng tốt:
SQL toàn bộ parametrized (không có injection trên write/read path usage), system
prompt anti-injection coi context/query là DỮ LIỆU, API key mã hoá AES-GCM at-rest,
key luôn masked khi đọc, error handler không leak stack trace, dimension guard R7
hoạt động đúng (REFUSE 400 khi cross-dim).

**Không phát hiện lỗi Critical.** Tuy nhiên có 5 Warning đáng xử lý trước khi ship,
đáng kể nhất là:

1. **Hub-scope widening trên `/api/ask`** — endpoint single-hub KHÔNG validate
   `hub_id`; khi thiếu, request âm thầm search TẤT CẢ hub mà user được assign thay
   vì lỗi 400 — vi phạm chủ đích "single-hub" và lệch với contract schema.
2. Cross-hub endpoint cũng không validate `hub_ids` → admin có thể vô tình fan-out
   toàn bộ hub.
3. Aggregate `request_count` cố định = 1 cho mỗi row làm sai số liệu khi 1 row đại
   diện nhiều call (hiện M2 1 row = 1 call nên đúng, nhưng giả định mong manh).

Các điểm còn lại là Warning nhỏ + Info về robustness và rõ ràng code.

## Cảnh báo (Warning)

### WR-01: `/api/ask` không validate `hub_id` — single-hub âm thầm thành multi-hub

**File:** `Hub_All/api/app/services/ask_service.py:170` · `Hub_All/api/app/routers/ask.py:124-141`
**Vấn đề:** Schema `AskRequest` (docstring `schemas/ask.py:24-26`) ghi rõ "Một trong
hai (`hub_id`/`hub_ids`) phải có ở router layer (validate ở Plan 07-04)". Nhưng cả
`ask_endpoint` lẫn `_run_ask` đều KHÔNG validate điều này. Trong `_retrieve` single-hub:

```python
hub_ids = [body.hub_id] if body.hub_id else None
```

khi `body.hub_id` None thì `hub_ids=None` được truyền xuống `SearchService.search()`.
`intersect_hubs(None, user_hub_ids, role)` với non-admin trả `base = set(user_hub_ids)`
→ search TẤT CẢ hub user được assign. Với admin → `is_admin_all=True` → search MỌI
hub active. Endpoint mang danh "single-hub ask" (ASK-01) nhưng thực thi cross-hub
âm thầm. Hậu quả: context trộn nhiều hub vào câu trả lời và citation, đi ngược chủ
đích hub isolation của `/api/ask` so với `/api/ask/cross-hub`.

**Sửa:** Validate ở router (hoặc đầu `_retrieve`) — single-hub bắt buộc có `hub_id`:

```python
# trong _run_ask, trước khi gọi service:
if not cross_hub and not body.hub_id:
    return resp.bad_request(
        message="Thiếu hub_id cho ask single-hub", code="INVALID_QUERY"
    )
```

### WR-02: `/api/ask/cross-hub` không validate `hub_ids` rỗng/None

**File:** `Hub_All/api/app/routers/ask.py:164-181` · `Hub_All/api/app/services/ask_service.py:164-168`
**Vấn đề:** `ask_cross_hub` truyền thẳng `body.hub_ids` (có thể None hoặc `[]`) vào
`SearchRequest`. `intersect_hubs` với admin + `hub_ids` None → trả `[]` sentinel →
`search_cross_hub` query MỌI hub active. Với non-admin + None → trả toàn bộ hub user.
Caller không có cách phân biệt "cố ý cross toàn bộ" với "quên truyền hub_ids". Nên
yêu cầu `hub_ids` non-empty tường minh cho endpoint cross-hub để tránh fan-out ngoài
ý muốn (cũng là vấn đề chi phí LLM/vector).

**Sửa:** Thêm guard ở `_run_ask` nhánh `cross_hub`:

```python
if cross_hub and not body.hub_ids:
    return resp.bad_request(
        message="Thiếu hub_ids cho ask cross-hub", code="INVALID_QUERY"
    )
```

### WR-03: `request_count` hardcode = 1 trong `_row_to_event` — sai khi đổi mô hình row

**File:** `Hub_All/api/app/services/usage_service.py:173`
**Vấn đề:** `_row_to_event` đặt `request_count=1` cho mỗi row. Hiện M2 1 row =
1 LLM call nên giá trị đúng, nhưng `UsageEventResponse.request_count` về mặt ngữ
nghĩa là "số call" — nếu sau này endpoint list hỗ trợ group/rollup (frontend
`TokenUsageAPI` có field này hàm ý có thể >1) thì số liệu sai âm thầm. Đây là magic
number gắn giả định ngầm.

**Sửa:** Comment rõ giả định "1 row = 1 call ở M2" tại chỗ hardcode, hoặc derive
từ aggregate khi list ở chế độ group. Tối thiểu thêm chú thích để lần sau không
hiểu nhầm.

### WR-04: `_provider_of` mặc định "openai" cho mọi model không chứa "gemini"

**File:** `Hub_All/api/app/services/usage_service.py:38-40` · `:135-138` · `:220-221`
**Vấn đề:** `_provider_of` và các `CASE WHEN model ILIKE 'gemini%'` phân loại
provider chỉ bằng substring "gemini"; mọi thứ khác → "openai". Nếu admin hot-swap
sang model khác (vd Anthropic, hoặc model OpenAI-compatible khác) thì bị gán nhầm
"openai". Filter `provider=openai` map sang `model NOT ILIKE 'gemini%'` cũng kéo
theo các model không phải OpenAI. M2 chỉ openai/gemini nên chấp nhận được, nhưng
là phân loại sai tiềm ẩn khi mở rộng provider.

**Sửa:** Whitelist tường minh hoặc thêm prefix-based mapping; tối thiểu thêm nhánh
"unknown" thay vì gộp hết vào "openai". Comment đã ghi D-07-02-A nhưng nên nêu rõ
giới hạn này.

### WR-05: `query_usage` nhận `date_from`/`date_to` dạng string thô chưa validate

**File:** `Hub_All/api/app/services/usage_service.py:123-128` · `Hub_All/api/app/routers/usage.py:53-54`
**Vấn đề:** `date_from`/`date_to` đến từ query param string, đẩy thẳng làm tham số
`$N` cho so sánh `created_at >= $N`. Không có injection (parametrized), nhưng nếu
client gửi chuỗi không phải timestamp hợp lệ, asyncpg/Postgres raise lỗi cast và
request trả 500 thay vì 400 rõ ràng. Endpoint là admin-only nên rủi ro thấp, nhưng
trải nghiệm lỗi kém và không phân biệt được lỗi input với lỗi server.

**Sửa:** Validate/parse `date_from`/`date_to` thành `datetime`/`date` ở router
(Pydantic hoặc `datetime.fromisoformat`), trả 400 `INVALID_DATE` khi parse fail.

## Info

### IN-01: `_AskChunk.content` nhận từ `r.get("content")` — phụ thuộc dict, không phải object

**File:** `Hub_All/api/app/services/ask_service.py:176` · `:198`
**Vấn đề:** `_retrieve` ép kiểu `results: list[dict[str, Any]]` rồi truy cập `r["id"]`,
`r.get("content")`. `SearchService.search()` trả `SearchResponse.model_dump(mode="json")`
nên `results` đúng là list dict — hiện chạy đúng. Nhưng đây là coupling ngầm với
chi tiết `model_dump` của Phase 6; nếu search đổi sang trả object thì vỡ âm thầm.
Khuyến nghị thêm comment ràng buộc rõ giả định này (search luôn trả dict đã dump).

### IN-02: `build_ask_messages` nhúng nguyên `title` chunk vào context không giới hạn độ dài

**File:** `Hub_All/api/app/services/ask_prompt.py:64-66`
**Vấn đề:** Mỗi dòng context dùng `body` = `chunk.content` đầy đủ (không phải
snippet đã cắt 300 ký tự). Với top_k=12 chunk nội dung dài, prompt có thể rất lớn
→ tăng prompt_tokens/chi phí và có nguy cơ chạm context window model. Không phải
lỗi đúng/sai nhưng là rủi ro chi phí (threat surface "LLM cost/DoS" của phase).
Cân nhắc cắt mỗi chunk theo trần ký tự khi dựng context.

### IN-03: `parse_citations` không xử lý marker dạng `[1, 2]` hoặc `[1][2]` gộp

**File:** `Hub_All/api/app/services/ask_prompt.py:49` · `:95`
**Vấn đề:** Regex `\[(\d+)\]` chỉ bắt 1 số nguyên mỗi cặp ngoặc. Nếu LLM sinh
`[1, 2]` hoặc `[1-3]` (dù system prompt yêu cầu `[N]`) thì marker bị bỏ hoàn toàn,
mất citation. Không phải bug — đúng theo D-07-01-A — nhưng nên ghi chú giới hạn
hoặc xử lý mềm dẻo hơn vì output LLM không đảm bảo tuyệt đối.

### IN-04: `cost_usd` ép `Decimal(str(float))` — rủi ro tràn `Numeric(10,6)`

**File:** `Hub_All/api/app/services/usage_service.py:68`
**Vấn đề:** `litellm.completion_cost` trả float USD; ép `Decimal(str(...))` để khớp
cột `Numeric(10,6)`. Nếu cost > 9999.999999 (khó xảy ra cho 1 call) hoặc float có
nhiều hơn 6 chữ số thập phân, Postgres có thể raise/round. `log_usage_event` đã bọc
try/except best-effort nên không sập request, nhưng row usage sẽ mất âm thầm. Cân
nhắc `quantize` Decimal về 6 chữ số trước khi insert.

### IN-05: `_run_ask` đọc `request.app.state.db_pool` lần hai không guard None

**File:** `Hub_All/api/app/routers/ask.py:108`
**Vấn đề:** `get_ask_service` đã guard `pool is None` → `RuntimeError`. Trong
`_run_ask`, dòng `pool = request.app.state.db_pool` truy cập trực tiếp không
`getattr` default. Vì DI factory chạy trước nên pool chắc chắn tồn tại — không phải
bug. Nhưng nên tái dùng `service.pool` thay vì truy cập lại `app.state` cho nhất
quán và tránh phụ thuộc thứ tự dependency.

### IN-06: `usage` mutate `usage.request_id` in-place trên dataclass dùng chung

**File:** `Hub_All/api/app/routers/ask.py:107`
**Vấn đề:** Router gán `usage.request_id = ...` mutate `UsageRecord` trả từ service.
Mỗi request tạo `UsageRecord` mới nên an toàn, nhưng pattern mutate cross-layer
(service tạo với `request_id=None`, router điền sau) làm dòng dữ liệu khó theo dõi.
Cân nhắc truyền `request_id` vào lúc dựng record hoặc tạo bản copy. Thuần style,
không ảnh hưởng chạy.

---

## Ghi nhận tích cực (không phải finding)

- SQL write/read path `usage_service.py` toàn bộ parametrized `$N` + WHERE-builder
  động chỉ append placeholder — không có SQL injection (T-07-02-03 đạt).
- `ANTI_INJECTION_SYSTEM_PROMPT` quy tắc 4 coi context+query là DỮ LIỆU, cấm tiết
  lộ system prompt — đúng mitigation T-07-01-01/02/03.
- `parse_citations` clamp `1 <= n <= len(chunks)` + de-dup — không tạo citation rác
  (T-07-01-04 đạt).
- API key mã hoá AES-GCM at-rest, `mask_key` luôn che, `get_config` không trả
  plaintext — không leak key.
- Dimension guard R7 (`rag_config_service.py:245-253`) REFUSE 400 đúng khi cross-dim.
- `AskError` map message ngắn gọn, không leak stack trace (T-07-04-06 đạt).
- `usage_events` schema không có cột `query`/`answer` → PII-safe by schema (T-07-02-PII).
- `log_usage_event` best-effort try/except — background task lỗi không sập request.
- Usage endpoint admin-only qua `require_role("admin")` — đúng T-07-02-02.

---

_Reviewed: 2026-05-18_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
