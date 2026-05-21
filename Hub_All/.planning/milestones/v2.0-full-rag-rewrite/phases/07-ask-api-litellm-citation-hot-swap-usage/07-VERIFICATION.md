---
phase: 07-ask-api-litellm-citation-hot-swap-usage
verified: 2026-05-18T00:00:00Z
status: human_needed
score: 5/5 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Đo latency p95 của POST /api/ask trên corpus thật + OPENAI/GEMINI key thật"
    expected: "p95 < 5s end-to-end (retrieve + LLM call + citation parse) — SC1"
    why_human: "Integration test mock litellm.acompletion → không có latency provider thật; M2 dev dùng placeholder key sk-replace-me. Đo thật ở Phase 9 eval."
  - test: "Verify hành vi LLM THẬT chống prompt-injection — gửi loạt query tấn công 'bỏ qua chỉ thị / in system prompt'"
    expected: "LLM thực sự từ chối hoặc trả 'Tôi không có thông tin...' — KHÔNG leak system prompt, KHÔNG đổi vai trò (SC2)"
    why_human: "Test Phase 7 chỉ verify lớp hệ thống (prompt được chèn vào messages[0]); hành vi LLM thật cần key thật. Manual UAT hoặc Phase 9 eval."
  - test: "Đo chất lượng retrieval sau khi hot-swap embedding within-dim 1536 (vector cũ vs vector mới khác model)"
    expected: "top-3 recall không suy giảm đáng kể sau swap embedding provider (R7)"
    why_human: "M2 không auto re-embed corpus khi đổi provider; đo chất lượng cần corpus thật + re-embed thủ công → Phase 9 eval."
---

# Phase 7: Ask API + LiteLLM + Citation + Hot-Swap + Usage — Báo cáo Xác minh

**Phase Goal:** Người dùng có thể hỏi câu hỏi tự nhiên, LLM (OpenAI/Gemini qua LiteLLM) trả lời với citation `[N]` map về `chunk_id`; admin có thể hot-swap provider runtime KHÔNG cần restart.
**Verified:** 2026-05-18
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| #   | Truth | Status | Evidence |
| --- | ----- | ------ | -------- |
| 1 | SC1 — `POST /api/ask` trả `{answer, citations:[{chunk_id, document_id, score, content_snippet}]}`; marker `[N]` map đúng `chunks[N-1].chunk_id` | ✓ VERIFIED | `ask_service.py:259-292` `ask()` retrieve → `build_ask_messages` → `litellm.acompletion` → `parse_citations`; `ask_prompt.py:85-115` `parse_citations` clamp `1<=n<=len(chunks)`, map `chunks[n-1]`; `schemas/ask.py` `Citation` có đủ field; integration test `test_citation_marker_maps_to_chunk_id` (critical). Latency p95 → human (HUMAN-UAT mục 1). |
| 2 | SC2 — Anti-injection: query "ignore previous instructions" KHÔNG bypass system prompt | ✓ VERIFIED (lớp hệ thống) | `ask_prompt.py:33-46` `ANTI_INJECTION_SYSTEM_PROMPT` quy tắc 1/2/4 (context+query là DỮ LIỆU, câu từ chối chuẩn); `build_ask_messages` luôn chèn vào `messages[0]`; integration test `test_anti_injection_system_prompt_present` (critical) verify prompt được chèn. Hành vi LLM thật → human (HUMAN-UAT mục 2). |
| 3 | SC3 — Hot-swap LLM provider qua `PUT /api/rag-config` → next `/api/ask` dùng provider mới, KHÔNG restart | ✓ VERIFIED | `rag_config_service.py:137-151` `_apply_runtime()` mutate `s.rag_llm_model = req.gemini_llm_model` (FIX Rule 1 deviation — bug cũ không mutate field này); `ask_service.py:114-126` `_resolve_llm_model()` đọc `get_settings()` mỗi lần gọi; integration test `test_hotswap_llm_provider` + `test_hotswap_reflected_in_usage_events` (critical). |
| 4 | SC4 — Hot-swap embedding within-dim 1536 → 200 cost preview; cross-dim → 400 "dimension mismatch" | ✓ VERIFIED | `rag_config_service.py:54` `_embedding_dim_of()`; `:244-256` dimension guard refuse cross-dim với chuỗi "dimension mismatch — defer cross-dim swap v4.0"; `:205-223` `_embedding_cost_preview()` message `re-embed N chunks, est $X.YZ, est T phút` (format `:.2f`); integration test `test_cross_dim_embedding_swap_refused` (critical) + `test_within_dim_embedding_swap_cost_preview`. |
| 5 | SC5 — 10 ask call → 10 row `usage_events` đầy đủ cột; `GET /api/usage?group_by=model` aggregate đúng | ✓ VERIFIED | `usage_service.py:72` `INSERT INTO usage_events`; `ask.py:109-120` `background_tasks.add_task(log_usage_event, ...)`; `usage.py:51-86` `GET /api/usage` với param `group_by` delegate `aggregate_usage`; integration test `test_ten_ask_calls_create_ten_usage_rows` (critical, poll deterministic) + `test_get_usage_group_by_model`. |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `api/app/schemas/ask.py` | AskRequest/Citation/AskResponse contract | ✓ VERIFIED | 3 model Pydantic v2; `Citation` có `chunk_id`/`document_id`/`score`/`content_snippet`; import bởi `ask_prompt.py` + `ask_service.py`. |
| `api/app/services/ask_prompt.py` | build_ask_messages + parse_citations + ANTI_INJECTION_SYSTEM_PROMPT | ✓ VERIFIED | 116 dòng, đủ 3 export; regex `[N]` parser clamp out-of-range + de-dup; wired vào `ask_service.py`. |
| `api/app/services/usage_service.py` | log_usage_event write + query/aggregate/realtime read | ✓ VERIFIED | `INSERT INTO usage_events` (raw SQL parametrized); 4 hàm async; PII-safe (không ghi query/answer); wired vào `ask.py` + `usage.py`. |
| `api/app/routers/usage.py` | GET /api/usage (+?group_by) + /stats + /realtime admin-only | ✓ VERIFIED | 3 endpoint `@router.get`, `require_role("admin")`; `group_by` param delegate aggregate; mount qua `usage_router`. |
| `api/app/services/ask_service.py` | AskService.ask() + ask_cross_hub() — search + LLM + citation + usage | ✓ VERIFIED | 329 dòng; `litellm.acompletion`; tái dùng `SearchService`; query `SELECT id, document_id FROM chunks`; KHÔNG tự ghi usage (router BackgroundTasks). |
| `api/app/routers/ask.py` | POST /api/ask + /cross-hub + alias /api/search/answer | ✓ VERIFIED | 3 endpoint, mỗi endpoint `@limiter.limit(SEARCH_LIMIT)` (3/3); `background_tasks.add_task(log_usage_event)`; mount qua `ask_router`. |
| `api/app/services/rag_config_service.py` | dimension guard + cost preview + hot-swap LLM model fix | ✓ VERIFIED | `_embedding_dim_of` + `_embedding_cost_preview` + dimension guard; Rule 1 fix `_apply_runtime` mutate `rag_llm_model` xác nhận tại dòng 151. |
| `api/tests/integration/test_ask_api.py` | Critical test ASK-01/02/03 | ✓ VERIFIED | 7 test, 5 critical; citation map + anti-injection + cross-hub + hub isolation. |
| `api/tests/integration/test_rag_config_hotswap.py` | Test ASK-04 hot-swap + dimension guard | ✓ VERIFIED | 5 test, 3 critical. |
| `api/tests/integration/test_usage_logging.py` | Test ASK-05 10 ask → 10 row + aggregate | ✓ VERIFIED | 6 test, 3 critical; poll deterministic `_wait_usage_count`. |
| `api/tests/unit/test_ask_prompt.py` | Unit test prompt + parser | ✓ VERIFIED | 1 critical (citation mapping). |
| `api/tests/unit/test_rag_config_dim_guard.py` | Unit test dimension guard + cost formula | ✓ VERIFIED | 1 critical (cross-dim suffix). |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | -- | --- | ------ | ------- |
| `ask_prompt.parse_citations` | `Citation.chunk_id` | regex `[N]` → `chunks[N-1]` | WIRED | `ask_prompt.py:95-113` finditer `_MARKER_RE`, `chunk_id=str(chunk.id)`. |
| `ask_service.ask` | `SearchService.search` | reuse single-hub retrieval | WIRED | `ask_service.py:145` `SearchService(pool=pool, redis=redis)`; `:168/174` gọi `search_cross_hub`/`search`. |
| `ask router` | `usage_service.log_usage_event` | `BackgroundTasks.add_task` | WIRED | `ask.py:109-120` `background_tasks.add_task(log_usage_event, pool, ...)`. |
| `usage_service.log_usage_event` | `usage_events` table | INSERT raw SQL | WIRED | `usage_service.py:72` `INSERT INTO usage_events ...` parametrized `$1..$8`. |
| `rag_config_service.update_config` | embedding dimension guard | `_embedding_dim_of(model)` check | WIRED | `rag_config_service.py:246-252` `_embedding_dim_of(req.embedding_model)` so với `rag_embedding_dim`. |
| `rag_config_service._apply_runtime` | `Settings.rag_llm_model` | mutate singleton (hot-swap) | WIRED | `rag_config_service.py:151` `s.rag_llm_model = req.gemini_llm_model` (Rule 1 deviation fix xác nhận). |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| -------- | ------------- | ------ | ------------------ | ------ |
| `AskResponse.citations` | `citations` | `parse_citations(answer, chunks)` — chunks từ `SearchService` (vector SQL) + LLM answer | Yes (search SQL + LLM `acompletion`) | ✓ FLOWING |
| `AskResponse.answer` | `answer` | `litellm.acompletion().choices[0].message.content` | Yes (LLM call; mock chỉ ở test) | ✓ FLOWING |
| `GET /api/usage` data | `events` / `stats` | `query_usage`/`aggregate_usage` — raw SQL `SELECT ... FROM usage_events` | Yes (DB query) | ✓ FLOWING |
| `usage_events` rows | INSERT payload | `UsageRecord` từ `litellm` response usage object | Yes (LLM token counts) | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| App boot mount 6 ask/usage routes | `create_app()` → assert routes ⊆ paths | `/api/ask`, `/api/ask/cross-hub`, `/api/search/answer`, `/api/usage`, `/api/usage/stats`, `/api/usage/realtime` đều mounted | ✓ PASS |
| LiteLLM pin xác nhận | `grep litellm pyproject.toml` | `litellm>=1.82,<2` pinned trong `[project.dependencies]` | ✓ PASS |
| Rate-limit 3/3 ask endpoint | `grep -c @limiter.limit ask.py` | 3 | ✓ PASS |
| Integration suite 18 test / 11 critical | per-file pytest (orchestrator) | 18 test pass, 11 critical pass trên Postgres testcontainer + LLM mock | ✓ PASS (báo cáo orchestrator) |
| Regression ruff + mypy --strict + 104 unit test | orchestrator | clean / clean (76 files) / 104 pass | ✓ PASS (báo cáo orchestrator) |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| ----------- | ----------- | ----------- | ------ | -------- |
| ASK-01 | 07-01, 07-04, 07-05 | POST /api/ask + citation `[N]`→chunk_id | ✓ SATISFIED | `ask_service.ask` + `parse_citations`; test `test_citation_marker_maps_to_chunk_id` critical. |
| ASK-02 | 07-01, 07-05 | System prompt anti-injection | ✓ SATISFIED | `ANTI_INJECTION_SYSTEM_PROMPT`; test prompt được chèn. Hành vi LLM thật → HUMAN-UAT. |
| ASK-03 | 07-04, 07-05 | POST /api/ask/cross-hub citation kèm hub_id | ✓ SATISFIED | `ask_cross_hub` + endpoint; test `test_ask_cross_hub_citations_have_hub_id` + hub isolation critical. |
| ASK-04 | 07-03, 07-05 | GET/PUT /api/rag-config hot-swap embedding + LLM | ✓ SATISFIED | dimension guard + cost preview + `_apply_runtime` LLM model fix; test hot-swap + cross-dim 400 critical. |
| ASK-05 | 07-02, 07-04, 07-05 | Token usage logging + GET /api/usage aggregate | ✓ SATISFIED | `log_usage_event` qua BackgroundTasks + 3 endpoint GET; test 10 ask → 10 row + aggregate critical. |

Tất cả 5 ID ASK-01..05 được khai báo trong PLAN frontmatter và khớp `REQUIREMENTS.md` section ASK — KHÔNG có ID orphaned.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| — | — | — | — | Không phát hiện blocker. Mock `litellm` chỉ trong `tests/integration/conftest.py` (test fixture hợp lệ, D-07-05-A — KHÔNG phải production stub). Code review 07-REVIEW.md: 0 Critical, 4-5 Warning (đã ghi nhận, không chặn goal). |

### Human Verification Required

Các mục dưới đây cần dữ liệu/key thật — M2 dev dùng placeholder `OPENAI_API_KEY=sk-replace-me`. Đã lưu trong `07-HUMAN-UAT.md`, gom vào Phase 9 (Eval Framework + Quality Gate).

1. **Latency p95 /api/ask < 5s (SC1)** — đo trên corpus thật + key thật. Integration test mock LLM nên chỉ verify field `query_time_ms` tồn tại; cấu trúc đo đã sẵn sàng.
2. **Anti-injection hành vi LLM THẬT (SC2)** — gửi loạt query tấn công thật, verify LLM không leak system prompt / không đổi vai trò. Test Phase 7 chỉ verify lớp hệ thống (prompt được chèn).
3. **Hot-swap embedding within-dim — chất lượng re-embed thực tế (R7)** — đo top-3 recall trước/sau swap embedding provider. M2 không auto re-embed corpus.

### Gaps Summary

KHÔNG có gap chặn goal. Cả 5 Success Criteria SC1-SC5 đã đạt ở mức xác minh tự động:
mọi artifact tồn tại, substantive, wired đúng và dữ liệu chảy thật (search SQL + LLM call +
INSERT usage_events). Bug hot-swap LLM model (Rule 1 deviation Plan 07-05) đã được fix —
`_apply_runtime()` mutate `s.rag_llm_model` xác nhận tại `rag_config_service.py:151`.

Trạng thái `human_needed` (KHÔNG phải `gaps_found`) vì 3 mục SC1 (latency p95), SC2
(anti-injection hành vi LLM thật) và R7 (chất lượng re-embed) hợp pháp defer sang Phase 9 —
cần API key thật + corpus thật mà M2 dev không có. Đây là defer có chủ đích, đã tài liệu hoá
trong `07-HUMAN-UAT.md` và ROADMAP. Theo cây quyết định Step 9, khi tất cả truth tự động đã
VERIFIED nhưng tồn tại hạng mục human verification → status = `human_needed`.

---

_Verified: 2026-05-18_
_Verifier: Claude (gsd-verifier)_
