---
plan: 05
phase: 1
status: complete
completed_at: 2026-05-13
wave: 3
---

# Plan 05 — Tóm tắt: Demolition M1 + Rewrite Hub_All/CLAUDE.md

## Mục tiêu
Xoá toàn bộ source code M1 abandoned khỏi working tree (giữ qua git history) và rewrite `Hub_All/CLAUDE.md` phản ánh stack M2 mới. Hoàn tất chuyển project state từ M1 sang M2 chính thức ở Phase 1.

## Pre-flight verification

| Check | Kết quả |
|-------|---------|
| M1 archive `.planning/milestones/v1.0-docling-rag/` tồn tại | ✓ 6 items (5 phase M1 + 1 backlog 999.1) |
| Working tree clean trước demolition | ✓ |
| Branch `main` | ✓ |

## Đã xoá

| Path | Size | Files | Method | Commit |
|------|------|-------|--------|--------|
| `Hub_All/docling-pipeline/` | 3.8 MB | 32 tracked | `git rm -rf` | `6460858` |
| `Hub_All/eval/` | 8.9 MB | 32 tracked | `git rm -rf` | `b54a630` |
| `Hub_All/docker-compose.override.yml` | 12 dòng | 1 | `git rm` | `3fdc0dd` |
| `Hub_All/chroma_data/` | — | 0 | **no-op** (đã không tồn tại) | — |

**Tổng:** 64 file tracked đã xoá + 1 file config dev. Recover được qua git log nếu cần.

## Đã rewrite

| File | Size trước | Size sau | Commit |
|------|-----------|----------|--------|
| `Hub_All/CLAUDE.md` | ~7 KB (M1 RAG Quality with Docling) | ~10 KB (M2 Full RAG Rewrite, 10 phase) | `46f4447` |

**Thay đổi nội dung chính:**
- Section 1 (Tổng quan): components mới `api/` + `backend/` DEPRECATED + `frontend/` UNCHANGED. Gỡ `docling-pipeline/`, `eval/`, `chroma_data/`. Thêm block lịch sử pivot (2026-04-28 → 2026-05-13).
- Section 2 (Milestone): M2 = 10 phase, bảng phase đầy đủ M2a/M2b, M2a EXIT GATE giữa Phase 4-5, critical path 1→2→4→6→7→9→10, auth branch parallel 3→5→8.
- Section 3 (Constraint M2): stack pin, embedding dim 1536, cocoindex content-hash diff, APP_NAMESPACE `medinet_prod`, middleware order REVERSED, format whitelist DOCX/TXT/MD/PDF text-only, EXIT criteria E1-E5.
- Section 3 (Code conventions): Python ruff/mypy/pytest/uv, Go DEPRECATED, Frontend UNCHANGED.
- Section 3 (Testing): HARD-03 coverage ≥50% critical path Phase 10.
- Section 4 (Lệnh GSD) + Section 5 (Commit) giữ nguyên.

## Đã preserve

| Path | Lý do |
|------|-------|
| `Hub_All/backend/` | Go DEPRECATED — giữ runtime cho frontend smoke đến Phase 8 (TEARDOWN-01) |
| `Hub_All/frontend/` | React 19 — D6: KHÔNG sửa trong M2 |
| `Hub_All/api/` | Skeleton Python mới M2 (Plan 01-04 đã tạo) |
| `.planning/milestones/v1.0-docling-rag/` | Archive M1 đầy đủ (5 phase + backlog 999.1) |

## Verification kết quả

**Demolition success:**
- `test ! -d Hub_All/docling-pipeline` → exit 0 ✓
- `test ! -d Hub_All/eval` → exit 0 ✓
- `test ! -f Hub_All/docker-compose.override.yml` → exit 0 ✓
- `test ! -d Hub_All/chroma_data` → exit 0 ✓ (no-op pre-existing)

**Preservation success:**
- `test -d Hub_All/backend` → exit 0 ✓
- `test -d Hub_All/frontend` → exit 0 ✓
- `test -d Hub_All/api` → exit 0 ✓

**CLAUDE.md M2 transition (per Plan 05 task 06 acceptance):**

| Check | Yêu cầu | Kết quả |
|-------|---------|---------|
| `grep -c 'M2 — v2.0 Full RAG Rewrite'` | ≥1 | 1 ✓ |
| `grep -c 'cocoindex==1.0.3'` | ≥1 | 1 ✓ |
| `grep -c 'pgvector/pgvector:pg16'` | ≥1 | 1 ✓ |
| `grep -c 'APP_NAMESPACE'` | ≥1 | 1 ✓ |
| `grep -c 'medinet_prod'` | ≥1 | 1 ✓ |
| `grep -c 'M2a EXIT GATE'` | ≥1 | 3 ✓ |
| `grep -c 'EXIT criteria E1-E5'` | ≥1 | 1 ✓ |
| `grep -c 'Phase 8'` | ≥1 | 3 ✓ |
| `grep -c 'docling-pipeline'` | =0 | 0 ✓ |
| `grep -c 'chroma_data'` | =0 | 0 ✓ |

**.gitignore sanity (Plan 01 still intact):**
- `api/.venv` ✓ · `api/keys` ✓ · `file_store` ✓ · `medinet_pgdata` ✓

**Git history clean:** working tree empty sau 4 commits Plan 05.

## Commits Plan 05

1. `6460858` — chore(phase-01): xoá Hub_All/docling-pipeline/ — M1 archived
2. `b54a630` — chore(phase-01): xoá Hub_All/eval/ — M1 eval framework abandoned (D8)
3. `3fdc0dd` — chore(phase-01): xoá docker-compose.override.yml — ref docling-pipeline đã chết
4. `46f4447` — docs(phase-01): rewrite Hub_All/CLAUDE.md sang M2 Full RAG Rewrite
5. (Commit này) — docs(phase-01): tóm tắt Plan 05

## Deviations

- **chroma_data/ no-op:** Thư mục đã không tồn tại trước khi Plan 05 chạy (gitignored từ M1, dev local chưa lần nào tạo). Skip silently theo execution rule. KHÔNG cần commit cho task này. Đã document trong bảng "Đã xoá".

- **Historical reference cho từ khoá "docling" trong CLAUDE.md:** Plan acceptance yêu cầu `grep -c 'docling-pipeline' Hub_All/CLAUDE.md` = 0 (KHÔNG còn ref path). Block lịch sử pivot vẫn nhắc "Docling" (M1 RAG Quality with Docling) làm context, KHÔNG còn nhắc path `docling-pipeline/` cụ thể. Pass acceptance.

## State sau Plan 05

- Phase 1 progress: 5/6 plans complete (Wave 1+2+3 done, Wave 4 còn Plan 06 CONVENTIONS.md).
- Project state đã chuyển hoàn toàn từ M1 sang M2 trên working tree.
- M1 source recoverable qua git: `git show 6460858^:Hub_All/docling-pipeline/...` hoặc archive `.planning/milestones/v1.0-docling-rag/`.
- Phase 8 (TEARDOWN-01) sẽ xoá `Hub_All/backend/` Go sau khi frontend smoke pass.

## Self-Check

- ✓ Tất cả must-have Plan 05 hoàn tất.
- ✓ Tất cả acceptance criteria task 02-07 PASS.
- ✓ Tất cả verification step trong section "Verification" của 05-PLAN.md PASS.
- ✓ Commit atomic (5 commits, mỗi task riêng + summary cuối).
- ✓ Commit message tiếng Việt có dấu + prefix English chuẩn + Co-Authored-By.
- ✓ KHÔNG touch `.planning/STATE.md`, `.planning/ROADMAP.md`, `backend/`, `frontend/`.
- ✓ Working tree clean.

**Kết luận:** PLAN 05 COMPLETE.
