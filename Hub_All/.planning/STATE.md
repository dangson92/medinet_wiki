---
gsd_state_version: 1.0
milestone: v2.0
milestone_name: M2 — Full RAG Rewrite (CocoIndex + Python FastAPI + pgvector)
status: phase_in_progress
last_updated: "2026-05-14T03:32:00.000Z"
progress:
  total_phases: 10
  completed_phases: 2
  total_plans: 16
  completed_plans: 12
  percent: 30
current_phase:
  number: 3
  name: Auth Port + RBAC + Response Envelope
  plans_total: 5
  plans_complete: 1
  status: in_progress
next_phase:
  number: 4
  name: CocoIndex Flow MVP + Document Ingest
---

# State — MEDWIKI

**Mã dự án:** MEDWIKI
**Milestone:** v2.0 — Full RAG Rewrite (CocoIndex + Python FastAPI + pgvector)
**Ngày tạo state:** 2026-05-13 (pivot lần 2 — M1 Docling abandoned)
**Last updated:** 2026-05-13 (roadmap 10 phase tạo xong)

---

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-05-13) + `.planning/ROADMAP.md` (created 2026-05-13)

**Core value:** Ingestion tri thức của Medinet phải tái hiện trung thực cấu trúc tài liệu nguồn (heading, bảng, ảnh có chú thích, công thức, OCR tiếng Việt cho scanned PDF — defer trong M2 vì D4) — biến mọi tài liệu y tế / dược / HCNS thành chunk semantic giàu metadata, để top-3 retrieval đạt ≥ 75% trên eval set thật.

**Current focus:** M2 = Full RAG Rewrite. Pivot lần 2 ngày 2026-05-13 từ "RAG Quality with Docling" sang "Full RAG Rewrite (CocoIndex + Python FastAPI + pgvector)". M1 cũ abandoned (28 plans code complete nhưng chưa runtime verify) — phases archive vào `.planning/milestones/v1.0-docling-rag/`.

**Mode:** YOLO · **Granularity:** Large (10 phase — reconciled từ FEATURES 8 + ARCHITECTURE 12 trong SUMMARY.md) · **Phase numbering:** Reset về Phase 1 (`--reset-phase-numbers`)

**M2a/M2b split (R3 anti-pivot fatigue mitigation):**
- **M2a = Phase 1-4** (Infra + Schema + Auth + CocoIndex MVP) — Có thể ship standalone. Nếu user accept M2a → never pivot.
- **M2b = Phase 5-10** (CRUD + Search + Ask + Frontend smoke + Eval + Hardening) — Pivot M2b OK nếu cocoindex critical fail.
- 🚦 **M2a EXIT GATE** giữa Phase 4 và Phase 5 — demo upload DOCX → chunks pgvector → SELECT verify. User accept là điều kiện tiếp tục M2b.

---

## Current Position

| Field | Value |
|---|---|
| Milestone | v2.0 Full RAG Rewrite |
| Phase | **Phase 3 — Auth Port + RBAC + Response Envelope** (5 plans / 4 waves, **1/5 executed** — Plan 03-01 DONE) |
| Plan | 03-01 ✓ DONE (Wave 1: middleware infra + envelope UPPER_SNAKE_CASE + CORS P12 validator). 03-02 NEXT (Wave 1: JWT keypair); 03-03 Wave 2 (Argon2); 03-04 Wave 3 (auth router); 03-05 Wave 4 (RBAC + 5-AC integration test). |
| Status | Phase 3 in progress — Plan 03-01 thực thi xong 5/5 task, 9/9 pytest PASS, 11/11 acceptance check PASS. |
| Last activity | 2026-05-14 — `/gsd-execute-phase 3 plan 03-01`: 5 commits atomic (14e1e5f → 5a3c844). 2 deviation Rule 3: pydantic-settings NoDecode cho CSV env vars + bỏ LifespanManager test vì asyncpg blocking Windows. Forward links rõ cho 03-02/03/04/05 dùng resp helpers + RequestId middleware. |
| Total phases | 10 (M2a: 4 + M2b: 6) |
| Total requirements | 38 v1 REQ-ID · 5 satisfied (CORE-01..05) · 2 satisfied Phase 3 (AUTH-01, AUTH-04 partial — middleware+envelope) · 4 planned remaining (AUTH-02, AUTH-03, AUTH-05, AUTH-06) |
| Critical path | 1 ✓ → 2 ✓ → 4 → 6 → 7 → 9 → 10 |
| Auth branch | 3 (1/5 plans) → 5 → 8 |

**Progress bar:** `[███░░░░░░░] 30% (2/10 phase + 1/5 Phase 3 plans) · Phase 3 in progress: 1/5 plans done · Next: /gsd-execute-phase 3 plan 03-02 (JWT keypair)`

---

## Performance Metrics

| Target | Source | Verified at |
|---|---|---|
| Search single-hub p95 <800ms | PRD v1.3 + PROJECT.md Constraints | Phase 6 (sanity) + Phase 9 (eval) |
| Search cross-hub p95 <1.5s | PRD v1.3 | Phase 6 + Phase 9 |
| CRUD endpoint p95 <300ms | PRD v1.3 | Phase 5 |
| Ingest 1 DOCX VN end-to-end <5s | Phase 4 MVP | Phase 4 |
| Quality gate top-3 retrieval ≥75% | EVAL-03 + Core Value | Phase 9 |
| Integration test coverage ≥50% critical path | HARD-03 | Phase 10 |
| HNSW recall WITH hub filter — measure ≥75% | R2 mitigation | Phase 9 |

---

## Accumulated Context

### Key decisions (lấy từ PROJECT.md)

- **D1: Toàn bộ backend Go → Python FastAPI** — codebase đồng nhất Python; tránh boundary Go↔Python phức tạp.
- **D2: CocoIndex v1.0.3+ làm indexing layer** — incremental diff content-hash + lineage built-in.
- **D3: Postgres pgvector** thay ChromaDB — bớt 1 service, dùng Postgres sẵn có.
- **D4: Gỡ Docling hoàn toàn** — ⚠️ risk regress scanned PDF tiếng Việt + bảng phức tạp; documented.
- **D5: LLM answerer giữ hot-swap OpenAI/Gemini** (port sang LiteLLM).
- **D6: Frontend KHÔNG sửa trong M2** — URL `/api/*` giữ nguyên.
- **D7: Abandon M1 hoàn toàn** — chưa runtime verify, chưa production.
- **D8: Eval framework làm lại từ đầu**.
- **D9: Phase numbering reset về 1**.

### Risk register (active)

| # | Risk | Severity | Phase address | Mitigation status |
|---|---|---|---|---|
| R1 | pgvector index 2000-dim limit | HIGH | Phase 1, 4 | OpenAI `dimensions=1536` API param; verify Phase 1 |
| R2 | HNSW post-filter recall collapse | HIGH | Phase 6, 9 | pgvector ≥0.8 + iterative_scan; measure WITH filter |
| R3 | Pivot fatigue → pivot 3 | CRITICAL | Phase 1 (bake) | M2a/M2b split + EXIT criteria E1-E5 + weekly check-in |
| R4 | Scanned PDF silent fail | HIGH | Phase 4, 8 | Whitelist format + enum `failed_unsupported` |
| R5 | CocoIndex naming + APP_NAMESPACE | MEDIUM | Phase 1, 4 | Snake_case + `medinet_prod` cố định + `db_schema_name="cocoindex"` |
| R6 | Argon2 hash cross-compat | MEDIUM | Phase 3 | Pin params Go-compat + integration test |
| R7 | Embedding swap = re-embed | MEDIUM | Phase 7 | Pin dim 1536 + cost preview UI + refuse cross-dim |

### EXIT Criteria (R3 mitigation, từ PROJECT.md)

| # | Trigger | Action |
|---|---|---|
| E1 | CocoIndex critical bug no-fix 14 ngày | STOP, `/gsd-discuss-milestone` |
| E2 | pgvector p95 >2000ms ở 50K chunks dù tune | STOP, discuss Qdrant |
| E3 | Phase 1-3 vượt 21 ngày calendar | STOP, scope review |
| E4 | Hub isolation bug không fixable trong 7 ngày | STOP, security review |
| E5 | Quality gate fail <60% top-3 dù iterate 3 vòng | Stop M2b, ship M2a standalone |

### Weekly check-in calendar (R3 mitigation)

- **Day 7:** Phase 1-2 done? Schema migration applied? Docker compose 3-service up?
- **Day 14:** Phase 3 PASS Argon2 cross-compat test? Phase 4 MVP ingest 1 file?
- **Day 21:** 🚦 **M2a EXIT GATE** — demo upload DOCX → chunks pgvector → user accept?
- **Day 28:** Phase 6-7 wire? Phase 8 frontend smoke pass?

### Todos cấp milestone

- [ ] (Phase 4 open question) Quyết định storage backend — local default, GDrive port optional confirm với user
- [ ] (Phase 3 open question) Verify JWT keypair format PKCS#1 vs PKCS#8 — convert nếu cần
- [ ] (Phase 4 open question) Quyết định PDF table extraction lib — pdfplumber vs camelot vs accept-loss (empirical test 3 VN medical PDF)
- [ ] (Phase 4 open question) Quyết định cocoindex augmenter — RTFM, default skip M2 nếu phức tạp
- [ ] (Phase 9 open question) Empirical confirm dim 1536 quality cho VN medical (gate ≥75%)

### Blockers

- Không có blocker khởi đầu. Codebase Go hiện hữu chạy được — Phase 1 (skeleton FastAPI + tear-down) chạy được ngay sau khi user approve roadmap.

### Notes

- **M2 = pivot lần 2 trong 15 ngày.** Tốc độ thay đổi định hướng đáng lưu ý — sau M2 cần ổn định ít nhất 4-8 tuần trước pivot tiếp. EXIT criteria E1-E5 bake để chống pivot lần 3.
- **Backlog 999.1 (incremental chunk re-embed)** được hợp nhất vào M2 vì đây chính là core value của cocoindex (content-hash diff). KHÔNG còn là backlog riêng.
- **Frontend KHÔNG đổi** — toàn bộ trang quản trị React 19 hiện hữu tương thích qua URL `/api/*` (nginx hoặc FastAPI mount port :8080).
- **Phases M1 archive:** `.planning/milestones/v1.0-docling-rag/` chứa 5 phase + 1 backlog 999.1 (git mv, history giữ nguyên).
- **Code Go sẽ bị xóa trong Phase 8** sau khi frontend smoke pass + git tag `m1-go-archived` backup.
- **OCR Vietnamese gỡ trong M2** — nếu user feedback regress, revisit ở milestone v4.0 (đưa Docling/Tesseract trở lại như extract function trong cocoindex flow).
- **Research flags theo phase:** Phase 3 MEDIUM (Argon2 cross-compat), Phase 4 HIGH (augmenter + PDF table + VN chunking), Phase 7 MEDIUM (memo cache invalidation), Phase 9 MEDIUM (dim quality empirical).

---

## Session Continuity

**Last session (2026-05-14 — Plan 03-01 execute):** `/gsd-execute-phase 3 plan 03-01` → executor agent thực thi 5 task atomic:
- Task 01 (`14e1e5f`): tạo 4 middleware file (`__init__.py`, `request_id.py`, `security_headers.py`, `error_handler.py`) — BaseHTTPMiddleware pattern, HTTPException pass-through để Plan 03-05 exception_handler render envelope.
- Task 02 (`464902b`): sửa `pkg/response.py` — 9 error code lowercase → UPPER_SNAKE_CASE (D6 Go-compat) + thêm `validation_error(422)` helper.
- Task 03 (`fb5c9e8`): config.py thêm `_no_lan_in_prod` validator (P12 mitigation, mode='after') + Rule 3 fix `Annotated[list[str], NoDecode]` vì pydantic-settings v2 auto-JSON-decode complex types break CSV env var.
- Task 04 (`3bbca23`): main.py wire 3 middleware theo P11 reversed (CORS → SecurityHeaders → RequestId → ErrorHandler outermost).
- Task 05 (`5a3c844`): tests/test_middleware.py — 9 unit test cover 5 behavior (request_id sinh/echo, security headers, error envelope, HTTPException pass-through, CORS prod reject + dev allow). Rule 3 fix bỏ LifespanManager vì asyncpg blocking Windows >5s khi không có Postgres.
- Verification suite 11/11 PASS: pytest 9/9 + ruff 7/7 + mypy 7/7 + middleware factory wired 4/4.
- SUMMARY.md `.planning/phases/03-auth-port-rbac-response-envelope/03-01-SUMMARY.md` tạo với 5 commit hash + 2 deviation log + threat model tracking + forward links cho 03-02/03/04/05.

**Next action:** Chạy `/gsd-execute-phase 3 plan 03-02` để tiếp tục Wave 1 (JWT keypair format detection + PyJWT RS256 wrapper — JWTManager + JWTClaims + TokenPair). Plan 03-02 có thể parallel với Plan 03-01 đã xong, nhưng đợt này executor chạy tuần tự. Sau 03-02 → Wave 2 (03-03 Argon2 cross-compat — cần Docker testcontainers Postgres).

**Files cần đọc khi resume:**

- `.planning/PROJECT.md` (core value + 9 key decisions D1-D9 + risk register R1-R7 + EXIT criteria E1-E5)
- `.planning/ROADMAP.md` (10 phase + success criteria + critical path)
- `.planning/REQUIREMENTS.md` (38 REQ-ID + Traceability section)
- `.planning/research/SUMMARY.md` (research synthesis)
- `.planning/research/{STACK,FEATURES,ARCHITECTURE,PITFALLS}.md` (chi tiết khi cần)
- `.planning/MILESTONES.md` (v1.0 abandoned context)

---

*Last updated: 2026-05-13 (Phase 2 planned — 5 plan ready to execute, đang chờ `/gsd-execute-phase 2`)*
