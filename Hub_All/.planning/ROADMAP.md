# Roadmap — Medinet Wiki (MEDWIKI)

**Project:** Medinet Wiki (Hub_All) · **Tracking:** ROADMAP (current) + MILESTONES.md (history) + `.planning/milestones/v*/` (archives)
**Last updated:** 2026-05-23 (post `/gsd-complete-milestone v3.0`)

---

## Milestones

- ❌ **v1.0 RAG Quality with Docling** — Abandoned 2026-05-13 (xem [`milestones/v1.0-docling-rag/`](milestones/v1.0-docling-rag/))
- ✅ **v2.0 Full RAG Rewrite** — Shipped 2026-05-21, 13 phases / ~75 plans / 38 REQ-ID (archive: [`milestones/v2.0-full-rag-rewrite/`](milestones/v2.0-full-rag-rewrite/))
- ✅ **v3.0 Multi-Hub Split** — Shipped 2026-05-23, 7 phases / 38 plans / 30 REQ-ID (archive: [`milestones/v3.0-multi-hub-split/`](milestones/v3.0-multi-hub-split/))
- 📋 **v3.1 RBAC hub_admin** — Next (gap thiết kế role-per-hub user yêu cầu 2026-05-23 — xem `project_rbac_hub_admin_gap` memory)
- 📋 **v4.0 Production Hardening + Advanced RAG** — Backlog (OCR Vietnamese, cross-dim embedding swap, streaming `/api/ask`, coverage >80%, ...)
- 📋 **v4.1 Advanced Retrieval** — Backlog (Hybrid BM25 + reranker, local embedding SEED-001, version history)

---

## Phases

<details>
<summary>✅ <strong>v3.0 Multi-Hub Split (Phases 1-7)</strong> — SHIPPED 2026-05-23 · 38/38 plans · 30/30 REQ-ID</summary>

- [x] Phase 1: Multi-DB Topology + Per-hub Alembic (5/5 plans) — 2026-05-21 · TOPO-01..04
- [x] Phase 2: Hub-con Codebase Factor (5/5 plans) — 2026-05-22 · FACTOR-01..04
- [x] Phase 3: Auth SSO + hub_ids trong JWT (5/5 plans) — 2026-05-22 · SSO-01..04
- 🚦 v3.0-a EXIT GATE — triggered 2026-05-22, user accept tiếp tục v3.0-b
- [x] Phase 4: Cross-hub Data Sync (7/7 plans) — 2026-05-22 · SYNC-01..05
- [x] Phase 5: Reverse Proxy + Frontend Subpath (6/6 plans) — 2026-05-23 · PROXY-01..04
- [x] Phase 6: System Settings Sync (5/5 plans) — 2026-05-23 · SETTINGS-01..04
- [x] Phase 7: Migration + Smoke E2E (5/5 plans) — 2026-05-23 · MIGRATE-01..05

Full details: [`milestones/v3.0-multi-hub-split/ROADMAP.md`](milestones/v3.0-multi-hub-split/ROADMAP.md) · [`REQUIREMENTS.md`](milestones/v3.0-multi-hub-split/REQUIREMENTS.md)

</details>

<details>
<summary>✅ <strong>v2.0 Full RAG Rewrite (Phases 1-10 + 8.1/8.2/8.3)</strong> — SHIPPED 2026-05-21 · 38/38 REQ-ID · 13/13 phases</summary>

Full details: [`milestones/v2.0-full-rag-rewrite/ROADMAP.md`](milestones/v2.0-full-rag-rewrite/ROADMAP.md) · [`phases/`](milestones/v2.0-full-rag-rewrite/phases/)

</details>

### 📋 v3.1 RBAC hub_admin (Next)

Gap thiết kế role-per-hub được defer v4.0 đã trở thành block user yêu cầu fix proper 2026-05-23. Phase đề xuất:

- [ ] Phase 1: DB migration `role_enum` thêm `hub_admin` + UserHub.role per-hub column (carry forward M2 schema)
- [ ] Phase 2: Backend `require_role()` + `require_hub_admin_for(hub_id)` dependency + filter `GET /api/hubs` cho hub_admin
- [ ] Phase 3: Frontend UserManagement form tách "Admin toàn hệ thống" vs "Quản lý hub này" + hub switcher hide central nếu non-super-admin
- [ ] Phase 4: Migration script seed existing admins giữ super-admin role + audit

Trigger: `/gsd-new-milestone v3.1` (sau khi user confirm scope đầy đủ).

---

## Progress

| Milestone | Phases | Plans Complete | REQ-ID | Status | Completed |
| --- | --- | --- | --- | --- | --- |
| v1.0 RAG Quality with Docling | 5 | 28/28 | 34/34 | ❌ Abandoned | 2026-05-13 |
| v2.0 Full RAG Rewrite | 13 | ~75/75 | 38/38 | ✅ Shipped | 2026-05-21 |
| **v3.0 Multi-Hub Split** | 7 | 38/38 | 30/30 | ✅ Shipped | 2026-05-23 |
| v3.1 RBAC hub_admin | ~4 | — | — | 📋 Next | — |
| v4.0 Production Hardening | — | — | — | 📋 Backlog | — |
| v4.1 Advanced Retrieval | — | — | — | 📋 Backlog | — |

---

## Backlog (project-level parking lot)

Tham chiếu `.planning/BACKLOG.md` cho 999.x items. Highlights cho v3.1 / v4.0 / v4.1:

- **RBAC hub_admin role per-hub** → v3.1 (user request 2026-05-23 — xem `project_rbac_hub_admin_gap` memory)
- 999.1 (M1) Incremental chunk re-embed → ✅ Absorbed v2.0 cocoindex core value
- Local embedding model (sentence-transformers, BGE-M3) → SEED-001 dormant v4.1
- OCR Vietnamese + table preservation revisit → v4.0
- Streaming `/api/ask` SSE → v4.0
- Hybrid retrieval BM25 + reranker → v4.1
- Comprehensive coverage >80% → v4.0
- Branch protection rule GitHub repo enforce 2 workflow → v4.0
- Visual regression smoke 4 hub × 11 trang (defer ops handover post-v3.0) → v3.1 or v4.0

---

## Deferred Items (carry forward từ v3.0 close)

- **podman-init-admin-issue** (debug, deferred) — WSL provider hang Windows env-specific, không block production
- **Phase 06 HUMAN-UAT partial** — visual smoke runtime defer ops handover
- **Phase 06 VERIFICATION human_needed** — defer ops handover
- **SEED-001 local embedding model** (dormant) — v4.1

---

*Last updated: 2026-05-23 sau `/gsd-complete-milestone v3.0` — archive milestone .planning/milestones/v3.0-multi-hub-split/. Next: `/gsd-new-milestone v3.1` cho RBAC hub_admin.*
