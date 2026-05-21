---
plan: 05
phase: 1
wave: 3
depends_on: [03]
files_modified:
  - Hub_All/docling-pipeline
  - Hub_All/eval
  - Hub_All/chroma_data
  - Hub_All/CLAUDE.md
  - Hub_All/docker-compose.override.yml
autonomous: false
requirements: [CORE-03]
---

# Plan 05: Demolition M1 — xoá docling-pipeline, eval, chroma_data + cập nhật CLAUDE.md

## Objective
Xoá toàn bộ code M1 đã abandoned (`docling-pipeline/`, `eval/`, `chroma_data/`) khỏi working tree, giữ `backend/` Go đến Phase 8. Cập nhật `CLAUDE.md` Hub_All phản ánh stack M2 mới (Python FastAPI + CocoIndex + pgvector). Verify archive M1 ở `.planning/milestones/v1.0-docling-rag/` tồn tại TRƯỚC khi xoá (fail-fast nếu archive missing).

**Autonomous: false** — Plan này xoá file source, executor phải confirm với user trước khi commit.

## Must-Haves
- Archive M1 verified tồn tại tại `Hub_All/.planning/milestones/v1.0-docling-rag/` TRƯỚC khi xoá.
- `Hub_All/docling-pipeline/` không còn trong working tree.
- `Hub_All/eval/` không còn trong working tree.
- `Hub_All/chroma_data/` không còn trong working tree (nếu trước đó còn).
- `Hub_All/backend/` Go vẫn còn nguyên (giữ đến Phase 8).
- `Hub_All/CLAUDE.md` cập nhật section "1. Tổng quan dự án" và "2. Milestone hiện tại" phản ánh M2 stack Python.
- `Hub_All/docker-compose.override.yml` (nếu có) gỡ reference docling.

## Tasks

<task id="01">
<action>
VERIFY archive M1 tồn tại TRƯỚC khi xoá source. Đây là fail-fast guard — nếu archive không tồn tại, ABORT plan và yêu cầu user kiểm tra (vì xoá nguồn không backup = mất data).

Chạy lệnh check:
```bash
test -d Hub_All/.planning/milestones/v1.0-docling-rag || { echo "ABORT: archive M1 missing — KHÔNG xoá source" >&2; exit 1; }
ls Hub_All/.planning/milestones/v1.0-docling-rag/
```

Output phải show ít nhất 1 phase directory M1 (tham chiếu STATE.md: 5 phase M1 đã archive). Nếu archive trống → ABORT.

KHÔNG xoá file gì ở task này — chỉ verify.
</action>
<read_first>
- Hub_All/.planning/STATE.md
- Hub_All/.planning/MILESTONES.md
</read_first>
<acceptance_criteria>
- `test -d Hub_All/.planning/milestones/v1.0-docling-rag` exits 0.
- `ls Hub_All/.planning/milestones/v1.0-docling-rag/ | wc -l` ≥ 1 (có ít nhất 1 file/folder archive).
- Task này KHÔNG xoá file nào — chỉ verify.
</acceptance_criteria>
</task>

<task id="02">
<action>
Xoá `Hub_All/docling-pipeline/` toàn bộ qua `git rm -rf` (giữ history qua git, recoverable nếu cần). Lệnh:

```bash
git rm -rf Hub_All/docling-pipeline/
```

Nếu thư mục có untracked file → dùng `rm -rf Hub_All/docling-pipeline/` sau khi `git rm` xong.
</action>
<read_first>
- Hub_All/CLAUDE.md
- Hub_All/.planning/STATE.md
</read_first>
<acceptance_criteria>
- `test -d Hub_All/docling-pipeline` exits 1 (không tồn tại).
- `git ls-files Hub_All/docling-pipeline/ | wc -l` trả `0`.
- `git status Hub_All/docling-pipeline/ 2>&1` không show file untracked nào.
</acceptance_criteria>
</task>

<task id="03">
<action>
Xoá `Hub_All/eval/` toàn bộ qua `git rm -rf`. M2 Phase 9 sẽ dựng lại `eval/` từ đầu (port queries.jsonl + dataset từ M1 archive). Lệnh:

```bash
git rm -rf Hub_All/eval/
```

Sau khi xoá, nếu có untracked file → `rm -rf Hub_All/eval/`.
</action>
<read_first>
- Hub_All/.planning/STATE.md
- Hub_All/.planning/ROADMAP.md
</read_first>
<acceptance_criteria>
- `test -d Hub_All/eval` exits 1 (không tồn tại).
- `git ls-files Hub_All/eval/ | wc -l` trả `0`.
</acceptance_criteria>
</task>

<task id="04">
<action>
Xoá `Hub_All/chroma_data/` nếu còn (đa số trường hợp đã được gitignore từ M1 nhưng có thể còn untracked persistent data). Lệnh:

```bash
rm -rf Hub_All/chroma_data/ 2>/dev/null || true
```

Nếu thư mục có tracked file (git ls-files chỉ ra) → `git rm -rf Hub_All/chroma_data/` trước. Không có file = no-op.
</action>
<read_first>
- Hub_All/.gitignore
</read_first>
<acceptance_criteria>
- `test -d Hub_All/chroma_data` exits 1 HOẶC `ls Hub_All/chroma_data 2>/dev/null | wc -l` trả `0`.
- `git ls-files Hub_All/chroma_data/ 2>/dev/null | wc -l` trả `0`.
</acceptance_criteria>
</task>

<task id="05">
<action>
VERIFY `Hub_All/backend/` Go vẫn còn nguyên — KHÔNG được xoá trong Phase 1 (giữ đến Phase 8 TEARDOWN-01). Chạy:

```bash
test -d Hub_All/backend || { echo "LỖI: backend/ Go đã bị xoá nhầm — Phase 1 không được xoá backend, chỉ Phase 8 mới xoá." >&2; exit 1; }
[ "$(git ls-files Hub_All/backend/ | wc -l)" -gt 0 ] || { echo "LỖI: backend/ không có file tracked" >&2; exit 2; }
```

Task này CHỈ verify, KHÔNG sửa gì.
</action>
<read_first>
- Hub_All/.planning/ROADMAP.md
- Hub_All/.planning/STATE.md
</read_first>
<acceptance_criteria>
- `test -d Hub_All/backend` exits 0 (backend/ tồn tại).
- `git ls-files Hub_All/backend/ | wc -l` > 0 (có tracked files).
- Task này KHÔNG xoá hoặc sửa file backend/.
</acceptance_criteria>
</task>

<task id="06">
<action>
Cập nhật `Hub_All/CLAUDE.md` — REWRITE toàn bộ section "1. Tổng quan dự án" và "2. Milestone hiện tại" + "3. Quy tắc làm việc" để phản ánh stack M2 mới. Giữ section "4. Lệnh GSD nhanh" và "5. Cấu trúc commit" (đã đúng generic, không cần đổi).

PATTERN: 
- Section 1: list components mới (`api/` Python, `backend/` Go giữ đến Phase 8, `frontend/` không đổi, `.planning/` GSD), gỡ `docling-pipeline/`, `eval/`, `chroma_data/`.
- Section 2: M2 v2.0 — Full RAG Rewrite, 10 phase (M2a 4 + M2b 6), M2a EXIT GATE giữa Phase 4 và 5. Bảng phase reference ROADMAP.md.
- Section 3.constraint: thay constraint M1 bằng constraint M2 — stack pin (cocoindex 1.0.3, fastapi 0.136.1, pgvector pg16, dim 1536 R1), CORE-05 reference CONVENTIONS.md (sẽ tạo ở Plan 06), middleware order REVERSED (P11), APP_NAMESPACE cố định "medinet_prod" (R5).
- Section 3.code conventions: cập nhật cho Python — ruff + mypy + pytest + uv. Gỡ Go reference (giữ note "Go backend còn đến Phase 8, đọc backend/keys/, backend/scripts/ làm tham chiếu để port").

Nội dung paste-ready cho file `Hub_All/CLAUDE.md` (toàn bộ — REWRITE):

```markdown
# CLAUDE.md — Medinet Wiki (Hub_All)

> Hướng dẫn cho Claude làm việc trong repository này. Toàn bộ giao tiếp BẰNG TIẾNG VIỆT có dấu (xem `~/.claude/CLAUDE.md`). Tên kỹ thuật, REQ-ID, lệnh shell, đường dẫn file giữ nguyên tiếng Anh.

---

## 1. Tổng quan dự án

**Medinet Wiki** là hệ thống quản lý tri thức nội bộ đa-Hub cho Medinet — wiki + RAG + MCP. Codebase này (`Hub_All/`) chứa:

- `api/` — **Python 3.12 · FastAPI 0.136 · CocoIndex 1.0.3 · pgvector (pg16) · asyncpg · SQLAlchemy 2.0 async · Alembic · Redis 7 · LiteLLM · PyJWT RS256 · pwdlib Argon2.** Stack mới M2 (in-process cocoindex, LISTEN/NOTIFY trigger).
- `backend/` — Go 1.25 · Gin · pgx/v5. **Giữ đến Phase 8** (smoke test frontend xong → xoá ở TEARDOWN-01).
- `frontend/` — React 19 · Vite 6 · TypeScript 5.8 · Tailwind v4. **KHÔNG sửa trong M2** (D6 — URL `/api/*` giữ nguyên).
- `documents/` — PRD v1.3, RAG Pipeline v3, BACKEND_DEVELOPMENT_PLAN, các prompt design.
- `.planning/` — GSD planning docs (PROJECT, REQUIREMENTS, ROADMAP, STATE, research, codebase map).

**Core value (M2):** Ingestion tri thức Medinet phải tái hiện trung thực cấu trúc tài liệu nguồn (heading, bảng, ảnh có chú thích, công thức — OCR tiếng Việt defer v4.0 vì D4) — biến mọi tài liệu y tế / dược / HCNS thành chunk semantic giàu metadata, để top-3 retrieval đạt ≥ 75% trên eval set thật.

## 2. Milestone hiện tại

**M2 — v2.0 Full RAG Rewrite (CocoIndex + Python FastAPI + pgvector)** · Granularity: large · Mode: YOLO · 10 phase · 38 REQ.

> Pivot 2026-05-13: M1 cũ (Docling RAG Quality) abandoned (28 plans code complete chưa runtime verify). Phases M1 archive: `.planning/milestones/v1.0-docling-rag/`. M2 = bộ REQ-ID hoàn toàn mới.

**M2a/M2b split (R3 anti-pivot fatigue):**
- **M2a (Phase 1-4):** Infra + Schema + Auth + CocoIndex MVP. Có thể ship standalone. M2a EXIT GATE giữa Phase 4 và 5.
- **M2b (Phase 5-10):** CRUD + Search + Ask + Frontend smoke + Eval + Hardening.

| # | Phase | Trọng tâm |
|---|-------|----------|
| 1 | Infra Skeleton + Demolition + EXIT Criteria | `api/` skeleton + Docker Compose 3-service + xoá M1 + CONVENTIONS.md |
| 2 | Database Schema + Alembic Baseline | Alembic migration users/hubs/documents/chunks/audit_logs/usage_events/refresh_tokens/api_keys |
| 3 | Auth Port + RBAC + Response Envelope | JWT RS256 + Argon2 cross-compat + RBAC |
| 4 | CocoIndex Flow MVP + Document Ingest | flow LISTEN/NOTIFY + extract/chunk/embed/pgvector |
| 5 | Hub + User + Audit + APIKey + Settings CRUD | port CRUD endpoint Go → Python |
| 6 | Search API Single + Cross-Hub | vector search direct pgvector + iterative_scan + Redis cache |
| 7 | Ask API + LiteLLM + Citation + Hot-Swap + Usage | LLM answerer + citation `[N]` + provider hot-swap |
| 8 | Frontend E2E Smoke + Tear-down Go Backend | React 19 smoke + xoá `backend/` Go |
| 9 | Eval Framework + Quality Gate ≥75% top-3 | pytest-based eval + 10 file VN medical |
| 10 | Hardening + Observability + Docs | structlog JSON + Prometheus + integration test ≥50% |

Critical path: 1 → 2 → 4 → 6 → 7 → 9 → 10. Auth branch parallel: 3 → 5 → 8.

## 3. Quy tắc làm việc

### Ngôn ngữ
- Tất cả tài liệu sinh ra (PLAN.md, REVIEW.md, SPEC.md, commit message phần mô tả, PR body) viết tiếng Việt có dấu.
- KHÔNG xen đoạn tiếng Anh dài. Chỉ giữ tiếng Anh cho: tên hàm/biến, lệnh code, REQ-ID, tên thư viện, đường dẫn file, prefix commit (`feat:` `fix:` `chore:` `docs:` `test:`).

### GSD workflow
- Mỗi phase: `/gsd-discuss-phase N` → `/gsd-plan-phase N` → `/gsd-execute-phase N`. Mode YOLO → có thể chạy `/gsd-autonomous` để chuỗi tự động.
- Các tài liệu nguồn sự thật: `.planning/PROJECT.md`, `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md`, `.planning/STATE.md`, `.planning/CONVENTIONS.md` (mới M2).
- Không sửa REQ-ID đã commit; thay đổi requirement phải qua `/gsd-discuss-phase` hoặc commit có lý do rõ trong message.

### Constraint M2 (Full RAG Rewrite)
- **Stack pin:** `python>=3.11,<3.13` (khuyến nghị 3.12), `fastapi==0.136.1`, `cocoindex==1.0.3`, `pgvector==0.4.2`, `asyncpg==0.30.0`. KHÔNG bump version giữa phase (chống pitfall P19).
- **Postgres image:** `pgvector/pgvector:pg16` (KHÔNG `postgres:16-alpine` — sẽ FAIL `CREATE EXTENSION vector`).
- **Embedding dim:** PIN 1536 cho cả OpenAI + Gemini (R1 mitigation pgvector 2000-dim index limit). Cross-dim swap REFUSE 400.
- **APP_NAMESPACE:** Cố định `medinet_prod` mọi env (R5 mitigation). Env separation qua database (`medinet_central` vs `medinet_cocoindex`) + container instance khác.
- **CocoIndex db_schema:** `cocoindex` (separate khỏi `public` — P7 mitigation).
- **Middleware order:** FastAPI REVERSED từ Go Gin (P11). Recovery/error_handler add CUỐI (outermost).
- **Test critical-path mandatory:** auth + hub isolation + ingest + search + ask. Coverage target 50%+. Reference `.planning/CONVENTIONS.md`.
- **Frontend D6:** KHÔNG sửa React 19. URL `/api/*` + response envelope `{success, data, error, meta}` shape-identical với Go cũ.
- **EXIT criteria E1-E5:** Bake trong `.planning/PROJECT.md`. M2a EXIT GATE giữa Phase 4-5: demo upload DOCX → chunks pgvector → user accept? Reject → STOP, không pivot 3.

### Code conventions (chi tiết: `.planning/CONVENTIONS.md`)
- **Python `api/`:** layered (router/service/repo). Format/lint: `ruff` (replaces black+isort+flake8). Type-check: `mypy --strict`. Test: `pytest + httpx AsyncClient + asgi-lifespan + testcontainers`. Manager: `uv` (Astral, Rust-based). Lệnh: `make install`, `make keys`, `make lint`, `make test`.
- **Go `backend/` (legacy, giữ đến Phase 8):** ĐỌC làm tham chiếu khi port (Argon2 params, JWT keypair format, response envelope shape, audit log fields). KHÔNG sửa code Go trong M2.
- **Frontend React (UNCHANGED M2):** Context API, API client `frontend/src/services/api.ts`. `npm run dev/build/lint`.

### Testing
- M2 critical path mandatory: pytest + testcontainers Postgres + Redis (Phase 10). Coverage 50%+ trên auth/ingest/search/ask/hub isolation. Comprehensive coverage >80% defer v4.0.

### Concerns đáng nhớ (chi tiết: `.planning/codebase/CONCERNS.md` + research/PITFALLS.md)
- **P1 (pgvector dim 2000):** dùng OpenAI `dimensions=1536` API param + verify HNSW build (Phase 1 init-db.sh).
- **P4 (HNSW post-filter recall):** pgvector ≥ 0.8 + `iterative_scan=relaxed_order` + `ef_search=200` (Phase 6).
- **P5 (Scanned PDF silent fail):** whitelist `{.docx, .txt, .md, .pdf}` + detect scanned → `failed_unsupported` (Phase 4).
- **P6 (Argon2 cross-compat):** pin pwdlib params `m=65536, t=1, p=2, saltLen=16, keyLen=32` match Go alexedwards (Phase 3).
- **P8 (Stuck processing):** heartbeat column + watchdog cron (Phase 4).
- **P9 (0% test coverage carry):** mandatory test critical path mỗi phase ship.

## 4. Lệnh GSD nhanh

| Lệnh | Khi dùng |
|------|---------|
| `/gsd-progress` | Xem trạng thái milestone hiện tại |
| `/gsd-plan-phase N` | Lập plan chi tiết cho phase N |
| `/gsd-execute-phase N` | Thực thi plan đã được duyệt |
| `/gsd-verify-work N` | UAT phase N |
| `/gsd-next` | Tự động đi tiếp bước hợp lý kế tiếp |
| `/gsd-debug` | Khi gặp bug khó |
| `/gsd-help` | Bảng đầy đủ |

## 5. Cấu trúc commit

- Phần prefix tiếng Anh chuẩn: `feat:`, `fix:`, `chore:`, `docs:`, `test:`, `refactor:`.
- Phần mô tả tiếng Việt có dấu, ngắn gọn, nói "tại sao" trước "làm gì".
- Mỗi plan trong phase commit atomic — không gộp nhiều plan vào một commit.

---

*Cập nhật: 2026-05-13 (pivot M2 — Full RAG Rewrite, Phase 1 đang execute).*
```
</action>
<read_first>
- Hub_All/CLAUDE.md
- Hub_All/.planning/PROJECT.md
- Hub_All/.planning/ROADMAP.md
- Hub_All/.planning/REQUIREMENTS.md
</read_first>
<acceptance_criteria>
- `grep -c 'M2 — v2.0 Full RAG Rewrite' Hub_All/CLAUDE.md` ≥ 1.
- `grep -c 'cocoindex==1.0.3' Hub_All/CLAUDE.md` ≥ 1.
- `grep -c 'pgvector/pgvector:pg16' Hub_All/CLAUDE.md` ≥ 1.
- `grep -c 'APP_NAMESPACE' Hub_All/CLAUDE.md` ≥ 1.
- `grep -c 'medinet_prod' Hub_All/CLAUDE.md` ≥ 1.
- `grep -c 'M2a EXIT GATE' Hub_All/CLAUDE.md` ≥ 1.
- `grep -c 'docling-pipeline' Hub_All/CLAUDE.md` trả về `0` (KHÔNG còn reference docling).
- `grep -c '`backend/`' Hub_All/CLAUDE.md` ≥ 1 (vẫn note backend/ giữ đến Phase 8).
- `grep -c '`api/`' Hub_All/CLAUDE.md` ≥ 1 (stack mới Python).
- `grep -c 'EXIT criteria E1-E5' Hub_All/CLAUDE.md` ≥ 1.
- `grep -c 'Phase 8' Hub_All/CLAUDE.md` ≥ 1 (tear-down Go).
</acceptance_criteria>
</task>

<task id="07">
<action>
Kiểm tra `Hub_All/docker-compose.override.yml` (nếu tồn tại từ M1) — gỡ mọi reference đến `docling-pipeline` hoặc `chromadb`. Nếu file chỉ chứa reference M1 → xoá toàn bộ file (Plan 02 đã có `docker-compose.yml` đủ cho M2).

Trình tự:
1. `cat Hub_All/docker-compose.override.yml 2>/dev/null` — xem nội dung.
2. Nếu file có service `docling-pipeline` hoặc `chromadb` mà KHÔNG có service khác cần giữ → `git rm Hub_All/docker-compose.override.yml`.
3. Nếu file có override hợp lệ cho M2 → giữ lại, chỉ xoá block docling/chroma.

Trường hợp file không tồn tại → skip (no-op).
</action>
<read_first>
- Hub_All/docker-compose.override.yml
- Hub_All/docker-compose.yml
</read_first>
<acceptance_criteria>
- Hoặc `test ! -f Hub_All/docker-compose.override.yml` (file đã bị xoá), HOẶC `grep -c 'docling' Hub_All/docker-compose.override.yml` trả `0` VÀ `grep -c 'chromadb' Hub_All/docker-compose.override.yml` trả `0`.
- `docker compose -f Hub_All/docker-compose.yml config` exits 0 (vẫn valid sau khi điều chỉnh override).
</acceptance_criteria>
</task>

## Verification
- `test -d Hub_All/docling-pipeline` exits 1.
- `test -d Hub_All/eval` exits 1.
- `test -d Hub_All/chroma_data` exits 1 hoặc thư mục rỗng.
- `test -d Hub_All/backend` exits 0 (Go backend còn nguyên).
- `git ls-files Hub_All/backend/ | wc -l` > 0.
- `git status --short Hub_All/docling-pipeline/ Hub_All/eval/ 2>&1 | wc -l` = 0 (working tree clean cho các path đã xoá).
- `grep -c 'M2 — v2.0' Hub_All/CLAUDE.md` ≥ 1.
- `grep -c 'docling' Hub_All/CLAUDE.md` trả `0` (không còn reference M1 stack).
- `docker compose -f Hub_All/docker-compose.yml config` exits 0.
