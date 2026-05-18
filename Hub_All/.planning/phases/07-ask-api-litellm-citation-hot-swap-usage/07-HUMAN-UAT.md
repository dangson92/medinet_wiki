---
status: partial
phase: 07-ask-api-litellm-citation-hot-swap-usage
source: [07-05-PLAN.md, 07-05-SUMMARY.md]
started: 2026-05-18T00:00:00Z
updated: 2026-05-18T00:00:00Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. Latency p95 /api/ask < 5s (SC1)
expected: Trên corpus thật + `OPENAI_API_KEY`/`GEMINI_API_KEY` thật, `POST /api/ask` (single hub) đo p95 < 5s end-to-end (retrieve + LLM call + citation parse). Integration test Phase 7 mock LLM (`litellm.acompletion`) → KHÔNG có latency provider thật, chỉ verify field `query_time_ms` TỒN TẠI trong `AskResponse` (cấu trúc sẵn sàng đo). Cần đo thật khi Phase 9 dựng eval set + cấu hình key thật.
result: [pending]

### 2. Anti-injection hành vi LLM THẬT (SC2)
expected: Test Phase 7 (`test_anti_injection_system_prompt_present`) chỉ verify lớp HỆ THỐNG — `ANTI_INJECTION_SYSTEM_PROMPT` được chèn vào `messages[0]` gửi cho LLM bất kể query. Verify hành vi LLM THẬT (LLM thực sự từ chối query tấn công "bỏ qua chỉ thị / in system prompt", KHÔNG leak prompt, KHÔNG đổi vai trò) cần `OPENAI_API_KEY`/`GEMINI_API_KEY` thật — gửi loạt query injection thật, kiểm tra answer không leak. Manual UAT hoặc đưa vào Phase 9 eval (giống cách Phase 6 defer recall).
result: [pending]

### 3. Hot-swap embedding within-dim — chất lượng re-embed thực tế (R7)
expected: Test Phase 7 (`test_within_dim_embedding_swap_cost_preview`) verify swap within-dim 1536 trả 200 + cost preview + warning. M2 KHÔNG auto re-embed corpus khi đổi provider (R7 — chỉ document upload mới dùng provider mới). Đo chất lượng retrieval SAU khi swap embedding provider (vector cũ vs vector mới cùng dim nhưng khác model) cần corpus thật + re-embed thủ công → defer Phase 9 eval đo top-3 recall trước/sau swap.
result: [pending]

## Summary

total: 3
passed: 0
issues: 0
pending: 3
skipped: 0
blocked: 0

## Gaps

- Latency p95, hành vi LLM thật, chất lượng embedding sau swap đều cần dữ liệu thật + API key thật (M2 dev dùng placeholder `sk-replace-me`). 3 mục này gom vào Phase 9 (Eval Framework + Quality Gate) — Phase 9 dựng `queries.jsonl` + 10 file VN medical + cấu hình key thật để đo end-to-end.
