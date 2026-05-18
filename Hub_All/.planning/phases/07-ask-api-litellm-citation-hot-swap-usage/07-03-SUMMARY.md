---
phase: 07-ask-api-litellm-citation-hot-swap-usage
plan: 03
subsystem: rag-config
tags: [rag-config, embedding, hot-swap, dimension-guard, cost-preview, ASK-04, R7]
requires:
  - "rag_config_service.update_config (commit 2d7a688 — endpoint build sớm)"
  - "schemas/rag_config.UpdateRagConfigRequest"
provides:
  - "dimension guard cross-dim swap → refuse 400"
  - "embedding cost preview WARNING within-dim swap"
  - "_embedding_dim_of helper (model name → dim)"
affects:
  - "routers/rag_config.py (KHÔNG sửa — đã map sẵn 2 nhánh str/dict)"
tech-stack:
  added: []
  patterns:
    - "model name hậu tố @<dim> → dimension (quy ước M2 D-07-03-A)"
    - "cost echo cho UI — format :.2f đảm bảo 2 chữ số thập phân"
key-files:
  created:
    - "api/tests/unit/test_rag_config_dim_guard.py"
  modified:
    - "api/app/services/rag_config_service.py"
    - "api/app/schemas/rag_config.py"
decisions:
  - "D-07-03-A — model name hậu tố @<dim> parse dimension; không hậu tố → 1536 pin"
  - "D-07-03-B — cost = n_chunks * 0.000013; minutes = ceil(n/450) min 1; message :.2f"
  - "D-07-03-C — within-dim swap KHÔNG tự re-embed, chỉ WARNING + cost preview"
  - "D-07-03-D — router contract D6 raw JSON giữ nguyên; KHÔNG đụng router"
metrics:
  duration: "~3 phút"
  completed: "2026-05-18"
  tasks: 3
  files: 3
---

# Phase 7 Plan 03: Ask API — RAG Config Dimension Guard + Cost Preview Summary

JWT-không liên quan — plan này hoàn thiện endpoint `/api/rag-config` (ASK-04 / R7):
thêm dimension guard chống cross-dim embedding swap (refuse 400) và cost preview
WARNING cho within-dim swap, vào service `rag_config_service.py` đã build sớm.

## Mục tiêu đạt được

HOÀN THIỆN (KHÔNG tạo lại) endpoint `/api/rag-config` để đáp ứng đầy đủ ASK-04 / R7:

- **LLM swap** — giữ nguyên (trivial config reload, không re-index).
- **Embedding swap WITHIN dim 1536** (OpenAI ↔ Gemini cùng dim) — cho phép NHƯNG
  trả `warning` + `cost_preview` ("re-embed N chunks, est $X.YZ, est T phút").
- **Embedding swap CROSS-dim** (1536 ↔ 3072) — TỪ CHỐI 400 "dimension mismatch —
  defer cross-dim swap v4.0".

## Công việc theo task

### Task 1 — `schemas/rag_config.py`: EmbeddingCostPreview (commit `789bc0d`)

Thêm model `EmbeddingCostPreview` (n_chunks / est_cost_usd / est_minutes / message)
mô tả shape cost preview. `UpdateRagConfigRequest` GIỮ NGUYÊN — request không đổi.
Service build nội dung rồi `.model_dump()` ghép vào response dict raw (contract D6).

### Task 2 — `rag_config_service.py`: dimension guard + cost preview (commit `2752d0b`)

- Hằng module-level: `PINNED_DIM = 1536`, `COST_PER_CHUNK_USD = 0.000013`,
  `CHUNKS_PER_MINUTE = 450`. Import `math`, `re`.
- Helper `_embedding_dim_of(model)` — regex `@(\d+)\s*$` parse hậu tố dim, fallback
  1536 (D-07-03-A).
- Method `_embedding_cost_preview()` — `count(*) FROM chunks` bọc try/except fallback
  n=0 (T-07-03-04), cost `round(n*rate,2)`, minutes `max(1, ceil(n/450))`, message
  format `:.2f` để cost LUÔN 2 chữ số.
- `update_config()` — chèn dimension guard NGAY SAU validate provider name: cross-dim
  → trả str (router map 400); within-dim embedding swap → tính `cost_preview`. Return
  dict thêm `warning` + `cost_preview` khi swap embedding.

### Task 3 — `test_rag_config_dim_guard.py` (commit `29a11db`)

6 unit test pure-Python (KHÔNG cần DB), 1 `@pytest.mark.critical`:
- `test_dim_of_default_no_suffix` / `test_dim_of_within_suffix` /
  `test_dim_of_cross_dim_suffix` (critical) — phủ `_embedding_dim_of`.
- `test_cost_formula` — verify công thức cost preview.
- `test_cross_dim_refuse_message_shape` — logic so sánh dim cross-dim → True.
- `test_cost_message_two_decimal_places` — n=7692 cho cost == 0.10 (trailing-zero
  case); message khớp regex `est \$\d+\.\d{2},` chứng minh `:.2f` (ROADMAP SC4).

## TDD Gate Compliance

Task 3 có `tdd="true"`. Hàm under test (`_embedding_dim_of` + hằng cost) là pure
logic đã implement ở Task 2 — không có vòng RED/GREEN riêng cho code vì test chỉ
verify thuần tính toán. Test file commit prefix `test(...)` sau khi implementation
đã tồn tại; tất cả 6 test PASS ngay từ lần chạy đầu (không có giai đoạn fail giả).
Đây là unit test verify-logic, không phải feature TDD cycle — phù hợp bản chất task.

## Deviations from Plan

None — plan executed exactly as written. 0 auto-fix. Code plan paste-ready apply
nguyên xi (chỉ thêm `import pytest` cho marker `@critical` như plan đã chỉ định).

## Threat Model Coverage

| Threat ID | Disposition | Trạng thái |
|-----------|-------------|------------|
| T-07-03-01 (Tampering — cross-dim vector mismatch) | mitigate | ✅ `update_config` refuse 400, KHÔNG persist config cross-dim |
| T-07-03-02 (Info Disclosure — leak API key) | accept→mitigate | ✅ `update_config` chỉ trả active_embedding/llm/warning/cost_preview — KHÔNG key |
| T-07-03-03 (EoP — non-admin gọi PUT) | mitigate | ✅ Router auth `require_role("admin")` giữ nguyên — plan không đụng router |
| T-07-03-04 (DoS — count(*) chậm) | accept | ✅ `_embedding_cost_preview` bọc try/except fallback n=0 |

## Verification

- `ruff check` service + schema + test → exit 0.
- `mypy --strict` service + schema → exit 0 (2 source clean).
- `pytest tests/unit/test_rag_config_dim_guard.py` → 6 passed.
- `pytest -m critical` → 1 passed, 5 deselected.
- `git diff --stat HEAD~3 HEAD` → CHỈ 3 file (service + schema + test) — router
  `rag_config.py` KHÔNG bị đụng (contract D6 raw JSON giữ nguyên).
- `git diff --diff-filter=D HEAD~3 HEAD` → rỗng (không xoá file ngoài ý muốn).
- AC grep — "dimension mismatch — defer cross-dim swap v4.0" match (chuỗi chính xác
  ROADMAP SC4); `_embedding_dim_of` + `_embedding_cost_preview` match; `:.2f}` match.

## Known Stubs

None — toàn bộ logic được wire đầy đủ. `_embedding_cost_preview` query `count(*)`
thật từ bảng `chunks`; nếu corpus rỗng (M2 chưa có chunk thật) thì n=0 — đây là
hành vi đúng, không phải stub.

## Forward Links

- **Plan 07-05** — integration test `_embedding_cost_preview` full (cần DB + chunks
  thật) + test `update_config` end-to-end cross-dim 400 / within-dim 200 + warning.
- ROADMAP SC4 verbatim "$X.YZ" được đảm bảo bởi format `:.2f` — verify cuối ở 07-05.

## Self-Check: PASSED

- `api/app/schemas/rag_config.py` — FOUND (class EmbeddingCostPreview).
- `api/app/services/rag_config_service.py` — FOUND (_embedding_dim_of + guard).
- `api/tests/unit/test_rag_config_dim_guard.py` — FOUND.
- Commit `789bc0d` — FOUND.
- Commit `2752d0b` — FOUND.
- Commit `29a11db` — FOUND.
