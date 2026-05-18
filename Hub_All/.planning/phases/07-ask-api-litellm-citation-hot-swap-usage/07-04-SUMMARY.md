---
phase: 07-ask-api-litellm-citation-hot-swap-usage
plan: 04
subsystem: ask-api
tags: [ask, litellm, citation, hot-swap, usage, background-tasks, rate-limit]
dependency_graph:
  requires:
    - "07-01 — schemas/ask.py (AskRequest/Citation/AskResponse), services/ask_prompt.py (build_ask_messages/parse_citations)"
    - "07-02 — services/usage_service.py (log_usage_event — best-effort write path)"
    - "Phase 6 — services/search_service.py (SearchService.search/search_cross_hub)"
  provides:
    - "AskService.ask()/ask_cross_hub() — retrieve + LLM call + citation parse + usage record"
    - "POST /api/ask + /api/ask/cross-hub + alias /api/search/answer (rate-limit 100/min, usage logging)"
  affects:
    - "07-05 — integration test suite (ROADMAP SC1/SC5 verify dựa trên 3 endpoint này)"
tech_stack:
  added: []
  patterns:
    - "litellm.acompletion non-streaming — wrap lỗi provider thành AskError"
    - "hot-swap LLM provider — _resolve_llm_model() đọc get_settings() mỗi lần gọi"
    - "usage logging non-blocking — FastAPI BackgroundTasks.add_task(log_usage_event)"
    - "document_id augmentation — query chunks bù field search Phase 6 không trả"
key_files:
  created:
    - "api/app/services/ask_service.py"
    - "api/app/routers/ask.py"
  modified:
    - "api/app/routers/__init__.py"
    - "api/app/main.py"
decisions:
  - "D-07-04-A — đăng ký 3 path: /api/ask + /api/ask/cross-hub + alias /api/search/answer"
  - "D-07-04-C — AskService tự query chunks bù document_id (không sửa SearchService)"
  - "D-07-04-D — service trả UsageRecord, router schedule log_usage_event qua BackgroundTasks"
  - "D-07-04-F — AskError → 500 LLM_FAILED (resp không có helper bad_gateway)"
metrics:
  duration_minutes: 18
  completed_date: 2026-05-18
  tasks_completed: 2
  files_created: 2
  files_modified: 2
  commits: 2
---

# Phase 7 Plan 04: Ask API LiteLLM + Citation + Hot-Swap + Usage Summary

Wire toàn bộ Ask API — `AskService` retrieve qua `SearchService` Phase 6, dựng
prompt anti-injection 07-01, gọi `litellm.acompletion()` non-streaming, parse
citation `[N]`→`chunk_id`, trả `AskResponse`; router `POST /api/ask` +
`/api/ask/cross-hub` + alias `/api/search/answer`, rate-limit 100/min, ghi
`usage_events` qua FastAPI BackgroundTasks sau mỗi LLM call.

## Tổng quan

Plan 07-04 là plan "lắp ráp" Wave 2 — toàn bộ contract đã định nghĩa ở Wave 1
(07-01 schema + prompt + parser, 07-02 usage write path), plan này nối chúng
thành luồng hỏi-đáp hoàn chỉnh ASK-01/02/03/05 + AUX-03.

2 task atomic, mỗi task 1 commit:

| Task | Tên | Commit | File |
|------|-----|--------|------|
| 1 | `ask_service.py` — AskService + LLM call | `74bf598` | `api/app/services/ask_service.py` |
| 2 | `routers/ask.py` — 3 endpoint + rate-limit + usage BG task | `f998b62` | `api/app/routers/ask.py`, `routers/__init__.py`, `main.py` |

## BƯỚC 0 — Xác nhận LiteLLM version (P19 mid-phase drift guard)

Thực hiện TRƯỚC khi viết code Task 1:

- `pyproject.toml` đã pin `litellm>=1.82,<2` trong `[project.dependencies]` —
  KHÔNG cần pin lại.
- Version thực tế resolve: **LiteLLM 1.83.14** (`importlib.metadata.version('litellm')`).
- `litellm.acompletion` + `litellm.completion_cost` TỒN TẠI; chữ ký xác nhận
  khớp `<interfaces>` chính xác:
  - `acompletion(model: str, messages: List = [], ...)` → `ModelResponse` object
    (`.choices[0].message.content`, `.usage`).
  - `completion_cost(completion_response=None, ...)` → `float` USD.
- KHÔNG có drift — code extract apply theo `<interfaces>` nguyên xi.

## Chi tiết thực thi

### Task 1 — `ask_service.py` (commit `74bf598`)

`api/app/services/ask_service.py`:

- `AskError(Exception)` — LLM call fail / response shape sai (router map 502/500).
- `UsageRecord` dataclass — payload `log_usage_event` (user_id/hub_id/model/3×token/
  cost_usd/request_id); `request_id=None` ở service, router override.
- `AskOutcome` dataclass — `(response: AskResponse, usage: UsageRecord)`.
- `_AskChunk` dataclass — wrap search result + `document_id` cho `parse_citations`
  đọc (id/document_id/hub_id/title/hub_name/snippet/content/score).
- `_resolve_llm_model() -> tuple[str, str]` — đọc `get_settings()` MỖI lần gọi
  (hot-swap ASK-04); provider `gemini` + model chưa có `/` → prefix `gemini/`
  (cùng quy ước `embedder.py`).
- `_resolve_top_k()` — None → 6, clamp `[1,12]` (D-07-01-B).
- `AskService`:
  - `__init__(*, pool, redis=None)` — tạo `SearchService(pool=pool, redis=redis)`.
  - `_retrieve(*, body, user, cross_hub)` — gọi `search`/`search_cross_hub`,
    rỗng → `[]`; bù `document_id` qua `SELECT id, document_id FROM chunks
    WHERE id = ANY($1::uuid[])` (D-07-04-C), bọc `_AskChunk`.
  - `_call_llm(messages)` — `litellm.acompletion` non-streaming; mọi exception
    → `AskError` (D-07-04-F); content rỗng/None → `AskError`.
  - `_extract_usage()` — token từ `getattr(resp.usage, ...)` an toàn None;
    `completion_cost` bọc try/except → None nếu lỗi.
  - `ask(*, body, user)` — single-hub; `ask_cross_hub(*, body, user)` —
    cross-hub (`UsageRecord.hub_id=None`). Tách method riêng (không flag).
  - `query_time_ms` đo qua `time.perf_counter()` → ghi vào `AskResponse`
    (D-07-04-E — cấu trúc sẵn sàng đo p95 ở Phase 9).
  - Log `ask_completed`/`ask_cross_hub_completed` với model/chunk_count/
    citation_count/query_time_ms — KHÔNG log query/answer (PII).
- `__all__ = ["AskService", "AskError", "AskOutcome", "UsageRecord"]`.

Verify: import OK, `ruff check` + `mypy --strict` exit 0.

### Task 2 — `routers/ask.py` (commit `f998b62`)

`api/app/routers/ask.py`:

- `APIRouter(tags=["ask"])` KHÔNG prefix — path tuyệt đối từng endpoint (vì
  `/api/search/answer` khác nhánh `/api/ask`).
- `get_ask_service(request)` DI factory — pool + redis từ `app.state`; pool
  None → `RuntimeError`.
- `_run_ask(...)` helper dùng chung 3 endpoint — map `ValueError`→400
  `INVALID_QUERY`, `EmbedderError`→500 `EMBEDDING_FAILED`, `AskError`→500
  `LLM_FAILED`; thành công → `background_tasks.add_task(log_usage_event, pool,
  **usage)` (request_id từ `request.state.request_id`) → `resp.ok(...)`.
- 3 endpoint POST, mỗi endpoint `limiter.limit(SEARCH_LIMIT)` (100/min — AUX-03),
  `Depends(get_current_user_with_hubs)`, `request: Request` + `background_tasks`:
  `/api/ask` (cross_hub=False), `/api/search/answer` (cross_hub=False),
  `/api/ask/cross-hub` (cross_hub=True).
- `routers/__init__.py` — re-export `ask_router`; `main.py create_app()` —
  `app.include_router(ask_router)` cạnh `usage_router`.

Verify: `create_app()` mount đúng 3 path; `ruff check` + `mypy --strict` exit 0;
`@limiter.limit` đúng 3 decorator.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Tránh grep false-positive `@limiter.limit` trong docstring**
- **Found during:** Task 2 — acceptance criteria verify.
- **Issue:** Acceptance criterion `grep -c "@limiter.limit" app/routers/ask.py == 3`.
  Bản đầu module docstring nhắc literal `@limiter.limit` 2 lần (giải thích thứ tự
  decorator) → `grep -c` trả 5 dù số decorator THỰC TẾ là 3.
- **Fix:** Đổi docstring dùng `limiter.limit` (không `@`) khi nhắc trong văn xuôi
  — decorator thực vẫn `@limiter.limit`. Sau sửa `grep -c` trả đúng 3.
- **Files modified:** `api/app/routers/ask.py` (chỉ docstring, KHÔNG đổi logic).
- **Commit:** `f998b62` (gộp trong commit Task 2 — sửa trước khi commit).
- **Note:** Cùng pattern deviation với 06-01 (docstring tránh false-positive grep).

Không có deviation Rule 1/2/4. Code plan paste-ready apply gần nguyên xi.

## Authentication Gates

Không có. `litellm.acompletion()` KHÔNG được gọi runtime trong plan này (không
chạy ask thật — OPENAI_API_KEY placeholder M2 dev). Verification chỉ static
(import + ruff + mypy + mount check). Ask call thật + ROADMAP SC1/SC5 verify
end-to-end thuộc Plan 07-05.

## Known Stubs

Không có stub. AskService + router wiring đầy đủ. Lưu ý:
- `cost_usd` có thể là `None` runtime khi `litellm.completion_cost` raise
  (provider không có bảng giá / key placeholder dev) — đây là behavior thiết kế
  (D-07-04-D), KHÔNG phải stub. `log_usage_event` đã xử lý `cost_usd=None`.
- `query_time_ms` đo thực qua `perf_counter` — đo p95 latency (SC1) defer Phase 9
  eval (D-07-04-E — không đo được lúc execute do key placeholder).

## TDD Gate Compliance

Plan 07-04 `type: execute` (KHÔNG `type: tdd`) — không yêu cầu RED/GREEN gate.
2 task đều `type="auto"` không `tdd="true"`. Integration test suite cho Ask API
(bao gồm critical test citation mapping + hub isolation) thuộc Plan 07-05.

## Threat Model Coverage

| Threat ID | Disposition | Trạng thái sau 07-04 |
|-----------|-------------|----------------------|
| T-07-04-01 | mitigate | `_retrieve` dùng `SearchService.search`/`search_cross_hub` — đã có `intersect_hubs` (lớp 1) + SQL `WHERE hub_id = ANY` (lớp 2); router dùng `get_current_user_with_hubs` (hub_ids từ DB). 07-05 verify. |
| T-07-04-02 | mitigate | `build_ask_messages` chèn `ANTI_INJECTION_SYSTEM_PROMPT` (07-01). 07-05 verify. |
| T-07-04-03 | mitigate | `limiter.limit(SEARCH_LIMIT)` 100/min trên cả 3 endpoint. |
| T-07-04-04 | mitigate | Router chỉ truyền token count + model + id vào `log_usage_event`; service log KHÔNG ghi query/answer (PII-safe). |
| T-07-04-05 | mitigate | `parse_citations` (07-01) map `[N]`→`chunks[N-1]` deterministic + clamp out-of-range. 07-05 critical test. |
| T-07-04-06 | mitigate | Router catch `AskError` → `resp.internal_error(code="LLM_FAILED")` message ngắn — KHÔNG leak stack trace. |

Không phát hiện threat surface mới ngoài `<threat_model>` — không có Threat Flags.

## Self-Check: PASSED

**File created:**
- FOUND: `api/app/services/ask_service.py`
- FOUND: `api/app/routers/ask.py`

**File modified:**
- FOUND: `api/app/routers/__init__.py` (ask_router export)
- FOUND: `api/app/main.py` (ask_router mount)

**Commit:**
- FOUND: `74bf598` — feat(07-04) AskService
- FOUND: `f998b62` — feat(07-04) router /api/ask

**Verification:**
- `ruff check` 4 file — exit 0
- `mypy --strict` 2 source — exit 0
- `create_app()` mount 3 path `/api/ask`, `/api/ask/cross-hub`, `/api/search/answer` — pass
- `@limiter.limit` đúng 3 decorator — pass
- `git diff --diff-filter=D HEAD~2 HEAD` — rỗng (không xoá file ngoài ý muốn)
