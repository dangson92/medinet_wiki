# Phase 5: Document version history - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in `05-CONTEXT.md` — this log preserves the alternatives considered.

**Date:** 2026-05-26
**Phase:** 05-document-version-history
**Mode:** `--auto` (Claude picks recommended defaults; no interactive questioning)
**Areas discussed:** GA-V3.1-D (snapshot file storage), GA-V3.1-E (chunks snapshot), GA-V3.1-F (RBAC viewer), GA-V3.1-G (retention enforcement), GA-V3.1-H (restore semantics) + 4 Claude codebase-audit decisions (plan count, migration name, audit action codes, reextract sync vs async)

**Tool fallback:** gsd-sdk v0.1.0 trong env KHÔNG có `query init.phase-op` mà workflow expect; chạy manual fallback mode (Write CONTEXT.md + DISCUSSION-LOG.md trực tiếp, commit qua Bash git).

---

## GA-V3.1-D — Snapshot file storage

| Option | Description | Selected |
|--------|-------------|----------|
| UUID mới mỗi version (copy binary) | Mỗi version = 1 file mới qua FileStore.save(); audit trail rõ NHƯNG disk explosion khi reupload nhiều lần cùng file | |
| **Dedupe qua content-hash + reference (Recommended)** | Compute SHA-256, check existing version cùng document_id có hash trùng → reference path cũ; chỉ save mới khi file khác. File cleanup tại retention prune nếu reference count = 0 | ✓ |
| Cross-document dedupe full | Dedupe across all documents qua reference_count schema | (defer v4.0) |

**Claude auto-mode choice:** Dedupe qua content-hash + reference (theo ROADMAP recommendation).
**Notes:** Phase 5 scope limit dedupe trong cùng document_id (giảm scope). Cross-document dedupe defer v4.0 (cần file_store schema migration thêm reference_count column). FE evidence (DocumentVersionHistory.tsx line 79 `a.download = v{N}_{name}`) cho thấy mỗi version cần file binary distinct (reference path cũ vẫn OK vì cùng content). LOCKED → D-V3.1-Phase5-A.

---

## GA-V3.1-E — Chunks snapshot per-version

| Option | Description | Selected |
|--------|-------------|----------|
| Snapshot full chunks per version | Tạo bảng `document_version_chunks` 1:N — mỗi version có chunks riêng (vector 1536-dim + content + metadata) | |
| **NO snapshot chunks, chỉ chunk_count metadata (Recommended)** | Bảng `document_versions` có cột `chunk_count INT` (snapshot count moment); GET /versions/{vid} trả `chunks: []` empty; restore = re-extract từ file binary qua cocoindex | ✓ |
| Hybrid (snapshot chunks last N versions only) | Snapshot chunks 2 versions gần nhất, drop chunks cũ | |

**Claude auto-mode choice:** NO snapshot chunks (theo ROADMAP recommendation).
**Notes:** Storage prohibitive — 100 documents × 5 versions × 50 chunks × 1536-dim vector ~150MB. Restore semantic đúng phải re-extract deterministic (extractor + chunker version pinned), KHÔNG restore stale chunks. FE typecheck happy với `chunks: []` empty array. LOCKED → D-V3.1-Phase5-B.

---

## GA-V3.1-F — RBAC viewer access

| Option | Description | Selected |
|--------|-------------|----------|
| **Viewer GET list + GET detail + GET file PASS, POST restore 403 (Recommended)** | Read-only consistency với existing document detail viewer permission; restore = mutate scope hub_admin+ only | ✓ |
| Only admin/hub_admin GET — viewer 403 | Stricter; viewer KHÔNG thấy version history (UX downgrade) | |
| Viewer GET list ONLY, GET file + detail 403 | Partial UX; phức tạp role matrix | |

**Claude auto-mode choice:** Viewer GET 3 endpoint PASS + POST restore 403 (theo ROADMAP recommendation).
**Notes:** Semantic carry forward existing M2 — viewer đã có quyền GET /api/documents/{id} + GET /api/documents/{id}/file. FE `canRestore?: boolean` prop tự handle UX layer cho viewer (button Khôi phục KHÔNG render). BE Layer 3 `assert_hub_admin_for` defense in depth. LOCKED → D-V3.1-Phase5-C.

---

## GA-V3.1-G — Retention "3 gốc + 2 gần nhất" enforcement point

| Option | Description | Selected |
|--------|-------------|----------|
| **BE write-time service-side cleanup (DEVIATION từ recommendation)** | Sau INSERT version mới (cùng transaction), DELETE middle versions qua CTE window function; BE invariant `COUNT(*) ≤ 5 per document_id` | ✓ |
| FE filter client-side (ROADMAP Recommended) | BE return full list chronological DESC; FE filter display "3 gốc + 2 gần nhất" | |
| BE read-time filter | BE store full, query response filter (KHÔNG cleanup) | |
| Configurable per-hub | system_settings extend retention policy | (defer v4.0) |

**Claude auto-mode choice:** BE write-time service-side cleanup (DEVIATION từ ROADMAP recommendation per FE codebase audit).
**Notes:** FE `DocumentVersionHistory.tsx` line 158 `versions.map(...)` KHÔNG có filter logic; line 146 hint "Lưu tối đa 5 phiên bản" + line 148 "Các phiên bản giữa được dọn tự động" — UX expectation explicit BE prune. Alternative "BE return all + FE filter" sẽ phá UX khi BE trả > 5 versions. Deviation justified. LOCKED → D-V3.1-Phase5-E.

---

## GA-V3.1-H — Restore semantics

| Option | Description | Selected |
|--------|-------------|----------|
| **Append-only history (Recommended)** | Restore tạo version mới (change_type='restore', version_number = max+1) TRƯỚC khi UPDATE document; existing versions preserved | ✓ |
| Overwrite + delete newer | Restore xoá v_max+1..N existing và rollback documents | |
| In-place rollback (KHÔNG version mới) | UPDATE documents row, KHÔNG snapshot trạng thái hiện tại | |

**Claude auto-mode choice:** Append-only history (theo ROADMAP recommendation).
**Notes:** Audit trail requirement — immutable history pattern carry forward audit_logs M2. FE confirm dialog (line 87) explicit báo user "Phiên bản hiện tại sẽ được lưu lại trước khi ghi đè" — match user expectation. Data loss protection. Bounded growth qua retention D-V3.1-Phase5-E. LOCKED → D-V3.1-Phase5-D.

---

## D-V3.1-Phase5-F — Plan count

| Option | Description | Selected |
|--------|-------------|----------|
| 3 plan (schema + impl + closeout) | Compact — gom service + router cùng 1 plan | |
| 4 plan (schema + service + router-test + closeout) | Match Phase 3 v3.1 model | |
| **5 plan (schema + service + router + test + closeout) — Recommended** | Match ROADMAP estimate "4-5 plans"; clean wave separation; mirror Phase 2 v3.1 (5 plan) | ✓ |
| 6 plan (schema + service + router + test + RBAC dedicated + closeout) | Separate RBAC dedicated wave | |

**Claude auto-mode choice:** 5 plan (recommended based on codebase pattern audit Phase 1-4 v3.1).
**Notes:** Wave critical path 1→2→3→4→5 BLOCKING (KHÔNG parallel-able). LOCKED → D-V3.1-Phase5-F.

---

## D-V3.1-Phase5-G — Migration revision name

| Option | Description | Selected |
|--------|-------------|----------|
| **`0007_document_versions` (Recommended)** | Sequence next sau 0006; snake_case feature description | ✓ |
| `0007_phase5_v31_versions` | Phase + milestone explicit trong tên (verbose) | |

**Claude auto-mode choice:** `0007_document_versions` (carry forward 0005 + 0006 naming convention).
**Notes:** LOCKED → D-V3.1-Phase5-G.

---

## D-V3.1-Phase5-H — Audit action codes

| Option | Description | Selected |
|--------|-------------|----------|
| **`document.version.create` + `document.version.restore` (Recommended)** | 2 distinct action code; 3 trigger (reupload, reextract, content_edit) emit `create`; POST /restore emit `restore` | ✓ |
| 4 action distinct (1 per change_type) | `document.version.reupload` + `document.version.reextract` + `document.version.content_edit` + `document.version.restore` — granular | |
| 1 generic action | `document.version` + payload `event` field — under-detailed | |

**Claude auto-mode choice:** 2 distinct actions (carry forward Plan 02-04 audit_action naming convention).
**Notes:** change_type metadata trong payload đã capture granularity; KHÔNG cần 4 distinct actions. LOCKED → D-V3.1-Phase5-H.

---

## D-V3.1-Phase5-I — Reextract sync vs async trong POST /restore

| Option | Description | Selected |
|--------|-------------|----------|
| **Sync block endpoint < 5s small file (Recommended)** | Simple; cocoindex re-extract DOCX < 1MB hoàn tất < 5s; FE loading state visible | ✓ |
| Async via background task | Spawn `asyncio.create_task(coco_flow.run_for_document(doc_id))`; FE polling /status | |
| Queue-based (Celery/RQ) | Production-grade async; complex infra | (defer v4.0) |

**Claude auto-mode choice:** Sync block (Phase 5 small scope; async queue defer v4.0).
**Notes:** Large file (> 10MB) warn UI defer v4.0; acceptable temporary block for catch-up scope. LOCKED → D-V3.1-Phase5-I.

---

## Claude's Discretion

Areas where plan-phase agent quyết định tại implementation time:
- Migration column order in CREATE TABLE statement
- Helper function placement (`_compute_file_hash` ở service vs file_store)
- Audit payload helper wrapper vs direct `build_audit_payload`
- Test fixture sample DOCX (inline python-docx generation vs reuse `fixtures/sample-document.docx`)
- Cocoindex mock vs real (monkeypatch hay `COCOINDEX_SKIP_SETUP=1` env)
- Reextract endpoint discovery (existing service function vs inline call)
- Pytest markers combination (`@pytest.mark.critical @pytest.mark.integration` cả 2 hay chỉ integration)
- OpenAPI tag (`Documents` cùng router vs `Document Versions` mới)
- Closeout git tag (KHÔNG tag mới mặc định vs `v3.1.1` annotate optional)

---

## Deferred Ideas

Captured during Phase 5 discussion, parked for future phases/milestones:
- Chunks per-version full snapshot (defer v4.0 cùng dedup strategy)
- Cross-document file binary dedupe via reference_count (defer v4.0)
- Version diff UI side-by-side compare (defer v4.0 FE feature)
- DELETE /api/documents/{id}/versions/{vid} endpoint (defer v4.0 — FE chưa có delete UI)
- Retention policy configurable per-hub via system_settings (defer v4.0)
- Restore re-extract async via cocoindex queue Celery/RQ (defer v4.0)
- Cross-hub version restore (NEVER — vi phạm hub isolation D-V3-01 LOCKED)
- HUMAN-UAT live runtime manual smoke (defer ops handover)
- OCR / scanned PDF version preservation (defer v4.0 — D4 LOCKED carry forward M2)
- v3.1.1 git tag annotated (defer operator decide)

---

*Generated 2026-05-26 by /gsd-discuss-phase 5 --auto (manual fallback mode due to gsd-sdk v0.1.0 lacking `query` subcommand)*
