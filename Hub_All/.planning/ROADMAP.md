# Roadmap — Medinet Wiki (MEDWIKI)

**Project:** Medinet Wiki (Hub_All) · **Tracking:** ROADMAP (current) + MILESTONES.md (history) + `.planning/milestones/v*/` (archives)
**Last updated:** 2026-05-21 (`/gsd-complete-milestone v2.0`)

---

## Milestones

- ❌ **v1.0 RAG Quality with Docling** — Abandoned 2026-05-13 (xem `.planning/milestones/v1.0-docling-rag/`)
- ✅ **v2.0 Full RAG Rewrite (CocoIndex + Python FastAPI + pgvector)** — Shipped 2026-05-21, 13 phases / ~75 plans / 38 REQ-ID done. Archive: [`milestones/v2.0-full-rag-rewrite/ROADMAP.md`](milestones/v2.0-full-rag-rewrite/ROADMAP.md) · [`REQUIREMENTS.md`](milestones/v2.0-full-rag-rewrite/REQUIREMENTS.md)
- 📋 **v3.0 Multi-Hub Split** — Seeded (LOCKED 4 D-V3, 4 GA-V3 open). Trigger: `/gsd-new-milestone v3.0` sau khi user verify v2.0 closeout. Seed: `.planning/seeds/v3.0-multi-hub-split.md`
- 📋 **v4.0 Production Hardening + Advanced RAG** — Backlog (OCR Vietnamese, cross-dim embedding swap, streaming `/api/ask`, comprehensive coverage >80%, ...)

---

## Phases

<details>
<summary>✅ <strong>v2.0 Full RAG Rewrite (Phases 1-10 + 8.1/8.2/8.3)</strong> — SHIPPED 2026-05-21 · 38/38 REQ-ID · 13/13 phases</summary>

- [x] Phase 1: Infra Skeleton + Demolition + EXIT Criteria (6/6 plans) — 2026-05-13
- [x] Phase 2: Database Schema + Alembic Baseline (5/5 plans) — 2026-05-13
- [x] Phase 3: Auth Port + RBAC + Response Envelope (5/5 plans) — 2026-05-14
- [x] Phase 4: CocoIndex Flow MVP + Document Ingest (8/8 plans) — 2026-05-21 · 🚦 M2a EXIT GATE PASSED
- [x] Phase 5: Hub + User + Audit + APIKey + Settings CRUD (6/6 plans) — 2026-05-17
- [x] Phase 6: Search API Single + Cross-Hub (4/4 plans) — 2026-05-18
- [x] Phase 7: Ask API + LiteLLM + Citation + Hot-Swap + Usage (5/5 plans) — 2026-05-18
- [x] Phase 8: Frontend E2E Smoke (TEARDOWN-01 done 2026-05-14) (5/5 plans) — 2026-05-19
- [x] Phase 8.1: MCP Server — Expose Wiki Tools (3/3 plans) — 2026-05-19
- [x] Phase 8.2: MCP Service — Tách Process Độc Lập (5/5 plans) — 2026-05-19
- [x] Phase 8.3: MCP OAuth 2.0 + Deploy Public HTTPS (9/9 plans) — 2026-05-21
- [x] Phase 9: Eval Framework + Quality Gate ≥75% top-3 (5/5 plans) — 2026-05-21
- [x] Phase 10: Hardening + Observability + Docs (6/6 plans) — 2026-05-21

Full details: [`milestones/v2.0-full-rag-rewrite/ROADMAP.md`](milestones/v2.0-full-rag-rewrite/ROADMAP.md)

</details>

### 📋 v3.0 Multi-Hub Split — SEEDED (chờ trigger)

Multi-tenancy PHYSICAL: tách hub con thành process + Postgres database riêng (cùng instance), hub tổng aggregator nhận chunks/vector từ hub con (sync 1 chiều). URL subpath `wiki.domain.com/<ten_hub>`. Auth SSO + reverse-proxy frontend prefix detect + migration data từ `medinet_central` cũ.

**LOCKED decisions (2026-05-21):**
- D-V3-01: Postgres database riêng cùng instance (1 instance, N database)
- D-V3-02: Dataflow hub con → tổng = chunks + vector denormalized (sync 1 chiều)
- D-V3-03: Milestone-level scoping (KHÔNG nhét vào M2)
- D-V3-04: M2 closeout precondition (HUMAN UAT Phase 9 gate verdict + retrospective)

**Open questions (chốt ở `/gsd-discuss-milestone v3.0`):**
- GA-V3-A: Auth SSO design (JWT shared / OIDC / cookie domain)
- GA-V3-B: System settings sync (rag-config global vs per-hub)
- GA-V3-C: Reverse proxy frontend prefix detect
- GA-V3-D: Migration data từ `medinet_central` cũ

Seed: `.planning/seeds/v3.0-multi-hub-split.md` (7 phase ~35 plan + 4 R-V3 + 4 E-V3)

---

## Progress

| Milestone | Phases | Plans Complete | Status | Completed |
| --- | --- | --- | --- | --- |
| v1.0 RAG Quality with Docling | 5 | 28/28 | ❌ Abandoned | 2026-05-13 |
| v2.0 Full RAG Rewrite | 13 | ~75/75 | ✅ Shipped (38/38 REQ-ID) | 2026-05-21 |
| v3.0 Multi-Hub Split | — | — | 📋 Seeded | — |

---

## Backlog (project-level parking lot)

Tham chiếu `.planning/BACKLOG.md` cho 999.x items. Một số highlights chuyển vào v3.0/v4.0:

- 999.1 (M1) Incremental chunk re-embed → ✅ Absorbed M2 cocoindex core value (Phase 4)
- Local embedding model (sentence-transformers, BGE-M3) → SEED-001 v4.1
- v3.0 Multi-Hub Split → seed v3.0
- OCR Vietnamese + table preservation revisit → v4.0
- Streaming `/api/ask` SSE → v4.0
- Hybrid retrieval BM25 + reranker → v4.1
- Comprehensive coverage >80% → v4.0
- Branch protection GitHub repo → v4.0

---

*Roadmap collapsed: 2026-05-21 (`/gsd-complete-milestone v2.0`)*
*v1.0 archive: `.planning/milestones/v1.0-docling-rag/` · v2.0 archive: `.planning/milestones/v2.0-full-rag-rewrite/`*
