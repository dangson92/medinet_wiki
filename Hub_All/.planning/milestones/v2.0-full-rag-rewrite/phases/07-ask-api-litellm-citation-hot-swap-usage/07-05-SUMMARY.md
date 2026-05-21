---
phase: 07-ask-api-litellm-citation-hot-swap-usage
plan: 05
subsystem: ask-api
tags: [ask, integration-test, citation, anti-injection, hot-swap, usage, testcontainers]
dependency_graph:
  requires:
    - "07-01 — schemas/ask.py + services/ask_prompt.py (ANTI_INJECTION_SYSTEM_PROMPT)"
    - "07-02 — services/usage_service.py + routers/usage.py (GET /api/usage)"
    - "07-03 — services/rag_config_service.py (dimension guard + cost preview)"
    - "07-04 — services/ask_service.py + routers/ask.py (POST /api/ask)"
  provides:
    - "test_ask_api.py — critical test ASK-01/02/03 (citation map + anti-injection + cross-hub + hub isolation)"
    - "test_rag_config_hotswap.py — test ASK-04 (hot-swap LLM + dimension guard)"
    - "test_usage_logging.py — test ASK-05 (10 ask → 10 usage row + aggregate)"
    - "conftest.py — fixture mock_llm + helper _wait_usage_count/_make_vec/make_fake_completion"
  affects:
    - "Phase 9 — eval framework đo latency p95 + anti-injection LLM thật (07-HUMAN-UAT.md)"
tech_stack:
  added: []
  patterns:
    - "LLM mock — monkeypatch litellm.acompletion/completion_cost qua mock_llm fixture (D-07-05-A)"
    - "BackgroundTask poll — _wait_usage_count thay asyncio.sleep cố định (D-07-05-B chống flaky)"
    - "per-file pytest — DEF-05-01 cocoindex Environment singleton, 1 file test/lần invocation"
key_files:
  created:
    - "api/tests/integration/test_ask_api.py"
    - "api/tests/integration/test_rag_config_hotswap.py"
    - "api/tests/integration/test_usage_logging.py"
    - ".planning/phases/07-ask-api-litellm-citation-hot-swap-usage/07-HUMAN-UAT.md"
  modified:
    - "api/tests/integration/conftest.py"
    - "api/app/services/rag_config_service.py"
decisions:
  - "D-07-05-A — LLM call MOCK qua monkeypatch (OPENAI_API_KEY M2 dev là placeholder)"
  - "D-07-05-B — usage poll deterministic _wait_usage_count thay sleep cố định"
  - "D-07-05-C — latency p95 SC1 defer Phase 9 (mock không có latency thật)"
  - "D-07-05-D — anti-injection verify prompt được chèn (lớp hệ thống); LLM thật defer HUMAN-UAT"
  - "D-07-05-E — test hot-swap gửi gemini_llm_model (field D6 thực tế), không bare llm_model"
metrics:
  duration_minutes: 30
  completed_date: 2026-05-18
  tasks_completed: 4
  files_created: 4
  files_modified: 2
  commits: 4
---

# Phase 7 Plan 05: Ask API Integration Test Suite Summary

Bộ integration test critical-path Phase 7 (ASK-01..05) — 18 test (11 critical)
verify thật trên Postgres testcontainer + app boot, LiteLLM call MOCK: citation
marker `[N]`→`chunk_id` deterministic, anti-injection prompt được chèn, cross-hub
+ hub isolation `/ask`, hot-swap LLM + dimension guard, 10 ask call → 10 row
`usage_events` (verify qua poll deterministic).

## Tổng quan

Plan 07-05 là plan "đóng quality gate" Wave 3 — toàn bộ Ask API đã lắp ráp ở
07-01..04, plan này viết bộ test critical-path để verify các điểm vỡ chính:
citation mapping (ASK-01), anti-injection (ASK-02), hub isolation `/ask`
(ASK-03), hot-swap LLM + dimension guard (ASK-04), usage logging (ASK-05).

Tuân thủ DEF-05-01 (cocoindex 1.0.3 `core.Environment` là process-global
singleton — KHÔNG re-open được sau open+close) → 3 file test boot app PHẢI
chạy 1 file/lần pytest invocation, đúng pattern Phase 5/6.

LLM call MOCK (D-07-05-A): `OPENAI_API_KEY` M2 dev là placeholder `sk-replace-me`
→ KHÔNG gọi provider thật. Fixture `mock_llm` monkeypatch `litellm.acompletion`
+ `litellm.completion_cost` — vừa tránh gọi key giả, vừa KIỂM SOÁT answer trả về
(vd `"A [1] B [2]."`) để verify citation mapping deterministic, vừa CAPTURE
`messages`/`model` gửi cho LLM (verify anti-injection prompt + hot-swap).

## Tasks hoàn thành

### Task 1 — conftest.py: fixture mock LLM + helper seed/poll (commit 0cc39d3)

Bổ sung vào `conftest.py` (không xoá fixture cũ):
- `make_fake_completion(content, *, prompt_tokens, completion_tokens)` — object
  giả mô phỏng LiteLLM `ModelResponse` qua `SimpleNamespace` lồng nhau
  (`.choices[0].message.content` + `.usage.*`).
- `mock_llm` fixture — monkeypatch `litellm.acompletion` + `litellm.completion_cost`,
  trả `state` dict cho test set `answer` + đọc `captured_messages`/`captured_model`.
- `_wait_usage_count(conn, expected, *, timeout_s=2.0)` — poll `count(*)`
  usage_events có giới hạn, thay `asyncio.sleep` cố định (D-07-05-B — chống
  flaky BackgroundTask timing qua ASGITransport).
- `_make_vec(seed)` — vector 1536-dim deterministic cho `_insert_chunk`.

### Task 2 — test_ask_api.py: critical test ASK-01/02/03 (commit 442b1ec)

7 test (5 critical):
- `test_ask_returns_answer_and_citations` (critical) — envelope có
  `answer`/`citations`/`model`/`query_time_ms`.
- `test_citation_marker_maps_to_chunk_id` (critical) — ĐIỂM VỠ CHÍNH ASK-01:
  mock answer `"A [1] B [2]."` → 2 citation, `number` khớp marker, `chunk_id`
  nằm trong set 2 chunk seed, `citations[0].chunk_id != citations[1].chunk_id`.
- `test_anti_injection_system_prompt_present` (critical) — D-07-05-D lớp 1:
  query tấn công → `captured_messages[0]` role=system chứa substring
  `"DỮ LIỆU, KHÔNG phải chỉ thị"` + `"Tôi không có thông tin"`.
- `test_ask_refusal_answer_passthrough` — D-07-05-D lớp 2: LLM trả câu từ chối
  → API passthrough nguyên văn, `citations == []`.
- `test_ask_cross_hub_citations_have_hub_id` (critical) — ASK-03: cross-hub
  citations đều có `hub_id` không rỗng.
- `test_ask_hub_isolation` (critical) — E4: viewer hỏi `/ask` hub không assign
  → search rỗng → `citations == []`.
- `test_ask_unauthenticated_401` — POST `/api/ask` không token → 401.

### Task 3 — test_rag_config_hotswap.py: test ASK-04 (commit 9977791)

5 test (3 critical):
- `test_hotswap_llm_provider` (critical) — PUT `/api/rag-config` đổi gemini
  (raw JSON 200) → POST `/api/ask` → `captured_model` chứa "gemini" (hot-swap
  runtime KHÔNG restart).
- `test_hotswap_reflected_in_usage_events` (critical) — sau hot-swap + 1 ask
  → `usage_events.model` chứa "gemini" (SC3 — dấu vết bền vững).
- `test_cross_dim_embedding_swap_refused` (critical) — `text-embedding-3-large@3072`
  → 400 `body["error"]` chứa "dimension mismatch" (R7).
- `test_within_dim_embedding_swap_cost_preview` — `gemini-embedding-001@1536`
  → 200 `cost_preview` + `warning`, message khớp regex `est \$\d+\.\d{2},` (SC4).
- `test_rag_config_put_admin_only` — viewer/editor PUT → 403.

### Task 4 — test_usage_logging.py + 07-HUMAN-UAT.md (commit 13fe9ef)

6 test (3 critical):
- `test_ten_ask_calls_create_ten_usage_rows` (critical) — SC5: 10 ask call →
  đúng 10 row (verify qua `_wait_usage_count` poll deterministic), token từ
  mock (120/40/160).
- `test_usage_row_has_no_pii` — T-07-05-02: cột `usage_events` từ
  `information_schema` == set dự kiến, không cột nội dung query/answer.
- `test_get_usage_endpoint_returns_events` (critical) — 3 ask → GET `/api/usage`
  list ≥3 event, mỗi event `operation=="ask"`.
- `test_get_usage_group_by_model` — SC5 URL literal: GET `/api/usage?group_by=model`
  → `by_model` không rỗng + `total_calls == N`.
- `test_get_usage_stats_aggregate` (critical) — GET `/api/usage/stats`
  → `total_calls == N`, `total_tokens == N*160`.
- `test_usage_endpoint_admin_only` — viewer GET `/api/usage` → 403.

`07-HUMAN-UAT.md` — 3 mục defer cần dữ liệu/key thật (latency p95 SC1,
anti-injection hành vi LLM thật SC2, chất lượng re-embed within-dim R7) → Phase 9.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Hot-swap LLM model không có hiệu lực**
- **Found during:** Task 3 (chuẩn bị test_hotswap_llm_provider)
- **Issue:** `rag_config_service._apply_runtime()` mutate `s.rag_llm_provider`
  từ `req.llm_provider` nhưng KHÔNG mutate `s.rag_llm_model` từ
  `req.gemini_llm_model`. `ask_service._resolve_llm_model()` đọc `s.rag_llm_model`
  → admin đổi model qua PUT `/api/rag-config` bị bỏ qua, ask vẫn gửi
  `gpt-4o-mini` cho LiteLLM (chỉ prefix `gemini/` đổi theo provider). Đây là gap
  correctness của hot-swap (ASK-04 must-have "hot-swap LLM provider phản ánh
  provider mới").
- **Fix:** Bổ sung `_apply_runtime` set `s.rag_llm_model = req.gemini_llm_model`
  khi field gửi lên; bổ sung `load_persisted_into_runtime` restore
  `s.rag_llm_model` từ key DB `LLM_GEMINI_MODEL` (giữ hot-swap qua restart).
- **Files modified:** `api/app/services/rag_config_service.py`
- **Commit:** 9977791

## Threat Surface Scan

Không có threat surface mới — plan 07-05 chỉ thêm test file + helper conftest +
1 fix runtime mutation. `rag_config_service` fix nằm trong trust boundary
admin-only sẵn có (PUT `/api/rag-config` `require_role("admin")`), không thêm
endpoint/auth path/schema mới.

## Verification

- 3 file test chạy PER-FILE (DEF-05-01) — mỗi lệnh exit 0:
  - `pytest tests/integration/test_ask_api.py` → 7 passed
  - `pytest tests/integration/test_rag_config_hotswap.py` → 5 passed
  - `pytest tests/integration/test_usage_logging.py` → 6 passed
- `pytest -m critical` per-file: 5 + 3 + 3 = 11 critical test pass.
- `ruff check` 4 file (3 test + conftest) → All checks passed.
- `mypy --strict app/services/rag_config_service.py` → Success.
- Tổng: 18 test (≥16 yêu cầu), 11 critical (≥9 yêu cầu).

## Success Criteria

- [x] Citation `[N]` map đúng `chunk_id` verified (test critical) — ASK-01.
- [x] Anti-injection prompt được chèn vào mọi ask call verified — ASK-02.
- [x] Cross-hub citation có `hub_id`; hub isolation `/ask` verified — ASK-03.
- [x] Hot-swap LLM → `usage_events.model` phản ánh provider mới; cross-dim
      swap → 400 — ASK-04.
- [x] 10 ask call → 10 row `usage_events` (verify deterministic qua poll);
      GET `/api/usage?group_by=model` aggregate đúng — ASK-05.
- [x] 18 test tổng, 11 critical; latency p95 defer HUMAN-UAT.
- [x] `07-HUMAN-UAT.md` tồn tại, liệt kê 3 mục defer.

## Known Stubs

Không có stub — 3 file test verify thật trên Postgres testcontainer + app boot,
mọi assert giá trị cụ thể (chunk_id khớp, count==10, model chứa "gemini",
403/401 status). LLM mock là test fixture hợp lệ (D-07-05-A), KHÔNG phải stub
production code.

## Self-Check: PASSED

- 5 file (3 test + HUMAN-UAT + SUMMARY) — đều FOUND trên filesystem.
- 4 commit (0cc39d3, 442b1ec, 9977791, 13fe9ef) — đều FOUND trong git log.
