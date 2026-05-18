---
phase: 07-ask-api-litellm-citation-hot-swap-usage
plan: 01
subsystem: api
tags: [pydantic, prompt-engineering, citation, anti-injection, llm, ask]

# Dependency graph
requires:
  - phase: 06-search-api-single-cross-hub
    provides: SearchResultItem schema + SearchService (chunk shape tham chiếu cho parse_citations)
provides:
  - AskRequest / Citation / AskResponse — contract Pydantic v2 cho Ask API (ASK-01)
  - build_ask_messages() — prompt builder đánh số chunk [1]..[N]
  - ANTI_INJECTION_SYSTEM_PROMPT — system prompt chống prompt-injection (ASK-02)
  - parse_citations() — map marker [N] trong answer LLM về chunk_id
affects: [07-04 AskService, 07-05 ask integration test, 08 frontend smoke]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Tách prompt/parser (pure Python) khỏi I/O (LLM call) — cô lập phần dễ vỡ để unit test"
    - "Anti-injection system prompt: coi context+query là DỮ LIỆU, buộc trả lời từ context"

key-files:
  created:
    - api/app/schemas/ask.py
    - api/app/services/ask_prompt.py
    - api/tests/unit/test_ask_prompt.py
  modified: []

key-decisions:
  - "D-07-01-A — LLM sinh marker [N] (số); parser map [N]→chunk_id; Citation mang cả marker và chunk_id; rewrite [src:] để dành Plan 07-04"
  - "D-07-01-B — top_k default 6 clamp [1,12] — xử lý ở router 07-04, schema chỉ khai báo Optional"

patterns-established:
  - "TDD per-task: RED (test commit) → GREEN (impl commit) cho prompt+parser"
  - "parse_citations dùng getattr an toàn cho document_id — không sửa SearchResultItem"

requirements-completed: [ASK-01, ASK-02]

# Metrics
duration: 12min
completed: 2026-05-18
---

# Phase 7 Plan 01: Ask API Contract + Prompt + Citation Parser Summary

**Contract Pydantic v2 cho Ask API (AskRequest/Citation/AskResponse) + prompt builder đánh số chunk [1]..[N] với system prompt chống prompt-injection tiếng Việt + citation parser map marker [N] về chunk_id.**

## Performance

- **Duration:** 12 min
- **Started:** 2026-05-18T11:45:00Z
- **Completed:** 2026-05-18T11:57:28Z
- **Tasks:** 3
- **Files modified:** 3 (tất cả tạo mới)

## Accomplishments
- `schemas/ask.py` — 3 model Pydantic v2 (`AskRequest`, `Citation`, `AskResponse`) định nghĩa hợp đồng ASK-01; mọi field `Citation` đủ để Plan 07-04 map sang `CitationRefAPI` (D6).
- `services/ask_prompt.py` — `ANTI_INJECTION_SYSTEM_PROMPT` (5 quy tắc tiếng Việt, ASK-02) + `build_ask_messages()` đánh số chunk `[1]..[N]` + `parse_citations()` map marker `[N]` về `chunk_id`, clamp out-of-range, de-dup theo `number`.
- `tests/unit/test_ask_prompt.py` — 7 unit test pure-Python (1 `@pytest.mark.critical` cho citation mapping), KHÔNG cần Postgres/Redis/LLM.

## Task Commits

Each task was committed atomically (TDD: test → feat):

1. **Task 1: Schema ask.py — AskRequest / Citation / AskResponse** - `3da2c6a` (feat)
2. **Task 3: test_ask_prompt.py — RED gate prompt+parser** - `0584c68` (test)
3. **Task 2: ask_prompt.py — prompt builder + anti-injection + parser** - `bad7ad2` (feat, GREEN)

_Note: Task 1 schema không có failing-test commit riêng — verify qua import smoke + ruff/mypy theo acceptance criteria của plan (`query` là required field nên Pydantic tự enforce ValidationError). Task 2 và Task 3 ghép TDD: test commit (RED) trước implementation commit (GREEN)._

## Files Created/Modified
- `api/app/schemas/ask.py` — 3 model Pydantic v2 contract Ask API.
- `api/app/services/ask_prompt.py` — prompt builder + anti-injection prompt + citation parser.
- `api/tests/unit/test_ask_prompt.py` — 7 unit test (1 critical).

## Decisions Made
None - followed plan as specified. Hai quyết định planner D-07-01-A (marker `[N]`) và D-07-01-B (`top_k` clamp) đã được áp dụng đúng: schema khai báo `top_k` Optional (clamp để Plan 07-04 router), `Citation` mang cả `marker` và `chunk_id`.

## Deviations from Plan

None - plan executed exactly as written.

**Total deviations:** 0
**Impact on plan:** Toàn bộ code paste-ready từ plan apply nguyên xi. Verification suite (ruff + mypy --strict + pytest) pass sạch.

## Issues Encountered
None. RED phase confirm `ModuleNotFoundError` đúng kỳ vọng trước khi tạo `ask_prompt.py`; GREEN phase 7/7 test pass ngay lần đầu.

## TDD Gate Compliance
- RED gate: `0584c68` (`test(07-01)`) — test_ask_prompt.py commit trong trạng thái fail (`ModuleNotFoundError`).
- GREEN gate: `bad7ad2` (`feat(07-01)`) — ask_prompt.py implement → 7/7 test pass.
- REFACTOR: không cần — code đã sạch (ruff + mypy clean).

## User Setup Required
None - no external service configuration required. Plan thuần Python (không DB, không LLM call).

## Next Phase Readiness
- Contract Ask API sẵn sàng — Plan 07-04 (AskService + router) build trên `AskRequest`/`Citation`/`AskResponse` + gọi `build_ask_messages` / `parse_citations`.
- Carry-over cho Plan 07-04: (1) `top_k` clamp `[1,12]` default 6 thực thi ở router; (2) `parse_citations` cần object chunk có field `document_id` — Plan 07-04 cấp object đủ field, KHÔNG sửa `SearchResultItem`; (3) router rewrite marker `[N]` → `[src:<chunk_id>]` cho frontend (D-07-01-A).
- Anti-injection verify đầy đủ (T-07-01-01/02) để dành Plan 07-05 integration test.

## Self-Check: PASSED
- `api/app/schemas/ask.py` — FOUND
- `api/app/services/ask_prompt.py` — FOUND
- `api/tests/unit/test_ask_prompt.py` — FOUND
- Commit `3da2c6a` — FOUND
- Commit `0584c68` — FOUND
- Commit `bad7ad2` — FOUND

---
*Phase: 07-ask-api-litellm-citation-hot-swap-usage*
*Completed: 2026-05-18*
