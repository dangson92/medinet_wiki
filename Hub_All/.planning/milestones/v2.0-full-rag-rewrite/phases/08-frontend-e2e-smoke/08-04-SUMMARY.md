---
phase: 08-frontend-e2e-smoke
plan: 04
subsystem: api
tags: [compat, smoke, boot-stack, docker-compose, uat, checkpoint, human-verify]

# Dependency graph
requires:
  - phase: 08-frontend-e2e-smoke
    provides: 08-01 — 08-CONTRACT-DIFF.md (54 endpoint phân loại, SC3 đối chiếu tĩnh)
  - phase: 08-frontend-e2e-smoke
    provides: 08-02 — router /api/ai/chat + port 8180 + CORS dev (gap api-side đã đóng)
  - phase: 08-frontend-e2e-smoke
    provides: 08-03 — test_smoke_golden_path.py + test_vietnamese_filename.py (SC2 API + SC4 verified tự động)
provides:
  - "api/scripts/smoke/boot_stack.sh — script boot docker compose 3-service + healthcheck verify tự động"
  - "08-SMOKE-CHECKLIST.md — checklist 4 section A/B/C/D cho người verify UAT thủ công"
  - "08-HUMAN-UAT.md — biên bản UAT Phase 8, verdict PARTIAL (SC1/SC2/SC5 pending chờ human verify)"
affects: [09-eval-framework]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Boot stack tự động hoá phần kiểm được (docker compose up + poll healthy + curl /healthz + assert no Go service); checkpoint human-verify cho phần render UI"
    - "UAT template chuẩn dự án (frontmatter status:partial + Current Test / Tests / Summary / Gaps) — mục cần mắt người để result:[pending] khi checkpoint auto-approve"

key-files:
  created:
    - .planning/phases/08-frontend-e2e-smoke/08-HUMAN-UAT.md
  modified: []

decisions:
  - "Checkpoint human-verify bị AUTO-APPROVE cơ học trong chế độ --auto (auto_advance:true) — KHÔNG có người thật boot stack hay click 11 trang React; 08-SMOKE-CHECKLIST.md CHƯA điền"
  - "08-HUMAN-UAT.md sinh từ cấu trúc checklist + 5 SC Phase 8 — KHÔNG fabricate PASS; SC1/SC2/SC5 (cần mắt người) để result:[pending], chỉ SC3 (08-01 đối chiếu tĩnh) + SC4 (08-03 test) đánh passed vì có artifact thật"
  - "Verdict UAT = PARTIAL; COMPAT-01 = PARTIAL — chờ /gsd-verify-work 8 verify thật mới đóng Phase 8"

# Metrics
metrics:
  duration: ~15 phút
  completed: 2026-05-18
  tasks: 2
  files_created: 1
  files_modified: 0
  commits: 2
---

# Phase 8 Plan 04: Boot Stack + Checkpoint Human-Verify + UAT Summary

Plan tạo công cụ smoke E2E frontend cuối Phase 8: script boot stack tự động hoá
phần kiểm được + checklist 4 section + biên bản UAT. **Checkpoint `human-verify`
bị auto-approve cơ học trong chế độ `--auto` — KHÔNG có người thật verify.** Biên
bản `08-HUMAN-UAT.md` sinh đúng thực trạng: SC1/SC2/SC5 để `pending`, verdict
PARTIAL. Phase 8 chỉ đóng được sau `/gsd-verify-work 8`.

## Tasks hoàn thành

### Task 1 — Script boot_stack.sh + checklist 11 trang (commit `422243a`, agent trước)

Đã hoàn thành bởi agent execution trước checkpoint:

- `api/scripts/smoke/boot_stack.sh` — script bash `set -euo pipefail`, idempotent:
  `docker compose up -d --build` → poll 3 service `healthy` (90s, in mỗi 5s) →
  `curl /healthz` + `/readyz` → `alembic upgrade head` → assert
  `docker compose config --services` chỉ 3 service không Go → exit 0/1 rõ ràng.
- `08-SMOKE-CHECKLIST.md` — 4 section: A (boot stack A1–A4), B (11 trang B1–B11 +
  2 dòng EXCLUDED E1/E2 SyncQueue/SyncReview), C (golden path browser C1–C5 với
  citation `[1]` clickable), D (tiêu chí PASS tổng D1–D4).

### Checkpoint human-verify — AUTO-APPROVED (không phải human verify thật)

Checkpoint `type="checkpoint:human-verify"` của plan đã bị orchestrator
**auto-approve** trong chế độ `--auto` (`auto_advance: true`) để giữ chuỗi tự động
chạy tiếp. `{user_response} = "approved"` là tín hiệu cơ học — **KHÔNG có người
thật nào boot stack, render 11 trang React, hay click citation `[1]`.** File
`08-SMOKE-CHECKLIST.md` CHƯA được con người điền.

### Task 2 — Tổng hợp 08-HUMAN-UAT.md (commit `76afc02`)

Vì checklist CHƯA điền, `08-HUMAN-UAT.md` được sinh từ **cấu trúc**
`08-SMOKE-CHECKLIST.md` + 5 Success Criteria ROADMAP Phase 8, dùng UAT template
chuẩn dự án (mẫu `07-HUMAN-UAT.md`):

- **Frontmatter** `status: partial` + source + timestamps.
- **Tests (5 mục = 5 SC):**
  - SC1 (11 trang React render) → `result: [pending]` — cần mắt người.
  - SC2 (golden path browser + citation `[1]` clickable) → `result: [pending]` —
    phần API đã verify tự động ở 08-03; phần browser cần mắt người.
  - SC3 (contract/replay test) → `result: passed` — đã verify ở 08-01 qua đối
    chiếu tĩnh 3 lớp, artifact `08-CONTRACT-DIFF.md`.
  - SC4 (VN filename UTF-8) → `result: passed` — đã verify ở 08-03,
    `test_vietnamese_filename.py` critical PASS (commit `74a7e3c`).
  - SC5 (docker compose 3-service healthy không Go) → `result: [pending]` —
    cần người chạy `boot_stack.sh` thật trên máy có Docker.
- **Summary:** total 5 / passed 2 / pending 3.
- **Gaps:** SC1/SC2/SC5 chưa human verify; chưa phát hiện gap kỹ thuật mới ngoài
  nhóm EXCLUDED đã biết.
- **COMPAT-01:** PARTIAL — lớp tĩnh/tự động ĐẠT, lớp browser chưa xác nhận.
- **Verdict:** PARTIAL — Phase 8 chưa đủ điều kiện đóng; bước tiếp theo
  `/gsd-verify-work 8`.

Biên bản ghi rõ một dòng note ở đầu file: các mục `pending` chờ người dùng chạy
`/gsd-verify-work 8` để verify thật.

## Deviations from Plan

### Điều chỉnh do checkpoint auto-approve (không phải bug — quy trình)

**1. [Continuation - Quy trình] KHÔNG fabricate kết quả PASS cho SC1/SC2/SC5**
- **Bối cảnh:** Plan Task 2 `<action>` giả định đọc `08-SMOKE-CHECKLIST.md` "đã
  điền" bởi người verify để tổng hợp PASS/FAIL từng trang. Thực tế checkpoint
  `human-verify` bị auto-approve cơ học (`--auto`) — checklist CHƯA điền, không
  có dữ liệu verify thật.
- **Điều chỉnh:** Sinh `08-HUMAN-UAT.md` từ **cấu trúc** checklist + 5 SC, đánh
  dấu mọi mục cần mắt người (SC1 render 11 trang, SC2 browser golden path +
  citation clickable, SC5 docker compose healthy) là `result: [pending]` — KHÔNG
  ghi `passed`. Chỉ SC3 + SC4 đánh `passed` vì có artifact verify thật (08-01
  đối chiếu tĩnh, 08-03 test critical PASS).
- **Lý do:** Auto-approve giữ chuỗi `--auto` chạy không tương đương human
  verification. Ghi PASS giả sẽ làm sai lệch trạng thái Phase 8 và COMPAT-01.
- **Files:** `08-HUMAN-UAT.md`.
- **Commit:** `76afc02`.

## Input cho bước tiếp theo

- **`/gsd-verify-work 8` BẮT BUỘC trước khi đóng Phase 8.** Người dùng làm theo
  `08-SMOKE-CHECKLIST.md`: chạy `boot_stack.sh`, `npm run dev`, login admin,
  render 11 trang, chạy golden path browser, điền PASS/FAIL — rồi cập nhật
  `result:` của Test 1/2/3 trong `08-HUMAN-UAT.md`.
- Nếu SC1/SC2/SC5 đều PASS → verdict UAT chuyển PASS, COMPAT-01 ĐẠT, Phase 8 đóng,
  tiếp Phase 9 (Eval Framework).
- Nếu có trang FAIL ngoài nhóm EXCLUDED (version history v4.1, sync queue M2,
  test-connection D-06) → ghi gap, input cho `/gsd-plan-phase 8 --gaps`.
- **Lưu ý audit (từ 08-03):** golden path login + upload qua UI KHÔNG sinh audit
  entry `auth.login`/`document.upload` — để Section C5 thấy audit log có dữ liệu,
  làm thêm thao tác `hub.create`/`user.create`/`document.delete`.

## Known Stubs

Không có. `08-HUMAN-UAT.md` là biên bản deliverable hoàn chỉnh — các mục
`result: [pending]` KHÔNG phải stub mà là trạng thái UAT đúng thực tế (chờ human
verify), được ghi rõ trong note đầu file + Summary + Verdict.

## Verification

- `bash -n api/scripts/smoke/boot_stack.sh` — syntax OK (Task 1, verified commit `422243a`).
- `test -f 08-SMOKE-CHECKLIST.md && grep -q "SyncQueue"` — OK (Task 1).
- `test -f 08-HUMAN-UAT.md && grep -qE "SC1|SC5|COMPAT-01"` — OK (Task 2).
- `08-HUMAN-UAT.md` có 4 nội dung yêu cầu: bảng 5 SC (Tests), 11 trang (mô tả
  trong Test 2 + EXCLUDED), Gap, COMPAT-01 + verdict cuối.
- D6 tuân thủ tuyệt đối: `git status` chỉ 1 file mới `08-HUMAN-UAT.md` trong
  `.planning/` — KHÔNG file nào trong `frontend/` bị sửa; không deletion.

## Self-Check: PASSED

- FOUND: .planning/phases/08-frontend-e2e-smoke/08-HUMAN-UAT.md
- FOUND: .planning/phases/08-frontend-e2e-smoke/08-SMOKE-CHECKLIST.md (Task 1)
- FOUND: api/scripts/smoke/boot_stack.sh (Task 1)
- FOUND commit: 422243a (Task 1 — script boot stack + checklist)
- FOUND commit: 76afc02 (Task 2 — biên bản UAT 08-HUMAN-UAT.md)
