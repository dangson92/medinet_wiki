# Milestones — MEDWIKI

Lịch sử các milestone đã chạy / abandon của dự án Medinet Wiki (Hub_All).

---

## v1.0 — RAG Quality with Docling — ❌ ABANDONED 2026-05-13

**Trạng thái khi abandon:** Code complete 100% (28 plans / 5 phase / 34 REQ), CHƯA runtime verify (chưa chạy `make eval-all`).

**Goal cũ:** Nâng chất lượng ingestion RAG bằng Docling (extract + chunk) trong service Python sidecar, gate top-3 retrieval ≥ 75% hoặc +15pp.

**Phases archive:** `.planning/milestones/v1.0-docling-rag/` chứa 5 phase + 1 backlog 999.1:

| # | Phase | Status | Commit cuối |
|---|---|---|---|
| 1 | Eval Dataset & Baseline Native | ✅ Completed | `f37cd96` |
| 2 | Docling Service (Python Sidecar) | 🟡 PARTIAL (8/8 plans code, smoke runtime defer) | — |
| 3 | Go Adapter & Pipeline Wiring | ✅ Completed (5/5 plans, 8/8 REQ) | `c7aa5b3` |
| 4 | Config Hot-Swap & Circuit Breaker | ✅ Completed (5/5 plans, 7/7 REQ) | `b52ec08` |
| 5 | Eval Compare & Quality Gate | ✅ Completed (5/5 plans, 4/4 REQ) | `3f54aee` |
| 999.1 | Incremental chunk re-embed (backlog) | Absorbed into M2 (cocoindex core value) | — |

**Lý do abandon (2026-05-13):**
- User quyết định pivot toàn bộ RAG sang **cocoindex** ([github.com/cocoindex-io/cocoindex](https://github.com/cocoindex-io/cocoindex)) v1.0.3+ thay vì Docling+Go tự build.
- Đi kèm rewrite backend Go → Python FastAPI (mục tiêu codebase đồng nhất).
- Migrate vector store ChromaDB → Postgres pgvector (bớt service, dùng Postgres sẵn có).
- M1 chưa chạy production (chỉ commit code, chưa user upload thật), không cần data migration.

**Code sẽ bị xóa trong M2 Phase 1:**
- `Hub_All/docling-pipeline/` (Python sidecar Docling)
- `Hub_All/eval/` (eval scripts cũ)
- `Hub_All/backend/internal/rag/`
- `Hub_All/backend/internal/embedding/`
- `Hub_All/backend/internal/llm/`
- `Hub_All/backend/internal/vectorstore/`
- `Hub_All/backend/internal/worker/`
- `Hub_All/backend/internal/storage/`
- Toàn bộ backend Go sau khi đã port logic sang FastAPI (M2 Phase cuối)

**Giá trị giữ lại từ M1:**
- Decision log + research Docling vs alternatives (lưu trong git history)
- Schema documents/hubs/users/audit_logs Postgres (giữ + migrate)
- Frontend React 19 (KHÔNG đổi)
- Knowledge: yêu cầu OCR tiếng Việt + table preservation cho scanned PDF y tế (sẽ ghi vào REQUIREMENTS M2 dưới dạng risk + open question)

**Pivot lần thứ 2:** Trước đó M1 đã pivot một lần từ "Multi-subdomain SPA" sang "RAG Quality with Docling" (2026-04-28). Lần này (2026-05-13) là pivot thứ 2 trong vòng 15 ngày — cần lưu ý về tốc độ thay đổi định hướng và rủi ro thrash.

---

## v2.0 — Full RAG Rewrite (CocoIndex + Python FastAPI + pgvector) — 🟡 IN PROGRESS

Khởi tạo: 2026-05-13. Chi tiết: `.planning/PROJECT.md` + `.planning/ROADMAP.md`.

**Goal:** Xóa toàn bộ stack RAG + backend Go hiện hữu, viết lại bằng **Python FastAPI + cocoindex v1.0.3+ + pgvector**. CocoIndex sở hữu indexing dataflow; FastAPI handle auth/hub/user/search/answer.

---

## Milestones tương lai (sau v2.0)

### v3.0 — Multi-subdomain SPA (defer từ trước — PRD v1.3)

Tách frontend thành 4 SPA (Hub Tổng + 3 Hub Dự Án). JWT mang `hub_id` từ subdomain context. Nginx routing wildcard. Defer lần 2: trước M1, và một lần nữa qua M2 hiện tại — sẽ chạy sau khi v2.0 done.

### v4.0 — MCP Server + Production Hardening

MCP Server expose RAG/Wiki cho Claude/ChatGPT agent. Đi kèm hardening: test coverage, `.gitignore` root, GCP key audit, AES_KEY rotation, XSS token storage migration.

---

*Last updated: 2026-05-13 (M1 abandoned, M2 khởi tạo)*
