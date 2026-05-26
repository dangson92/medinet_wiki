---
phase: 05-document-version-history
gathered: 2026-05-26
status: Ready for planning
source: ROADMAP §"Phase 5 — Document version history" 5 gray-area recommendation (GA-V3.1-D..H) + auto-mode codebase audit (frontend DocumentVersionHistory.tsx + DocumentVersionAPI 16-field interface + Phase 2 v3.1 assert_hub_admin_for + Phase 1 v3.1 Alembic 0006 introspect pattern + Phase 4 v3.0 outbox trigger pattern + FileStore local UUID + chunks.content_hash BYTEA evidence)
---

# Phase 5: Document version history (VER) — Context

**Trigger:** v3.1 milestone re-opened 2026-05-26 (sau v3.1 SHIPPED 2026-05-24) để pull v4.1 backlog "version history" về Phase 5. Lý do: frontend `DocumentVersionHistory.tsx` đã ship ở milestone trước (commit ~~old~~) — user mở tab "Lịch sử phiên bản" trong DocumentPreview gặp `404` console error 4 endpoint `/api/documents/{id}/versions*` vì backend chưa implement. Phase 5 = backend catch-up bắt buộc; KHÔNG đụng FE existing (R-V3-2 minimal scope carry forward — chỉ verify FE render OK sau BE ship).

**Auto-mode note:** `/gsd-discuss-phase 5 --auto` chạy 2026-05-26 trong `auto` mode (system reminder "Work without stopping" + project precedent Phase 1-4 v3.1 + Phase 4-7 v3.0). 5 gray area ROADMAP §"Discuss-phase gray areas" lock theo recommendation đã có. Codebase audit phát hiện 4 decision phụ (D-V3.1-Phase5-F/G/H/I — plan count + migration name + audit action code + retention enforcement point) lock thêm; 1 deviation tài liệu rõ (D-V3.1-Phase5-E retention enforce ở **BE write-time** thay vì "FE filter client-side" như ROADMAP GA-V3.1-G recommend — vì FE `DocumentVersionHistory.tsx` line 158 `versions.map(...)` KHÔNG có filter logic, hint "Lưu tối đa 5 phiên bản" line 146 là text-only, BE cleanup mới đúng UX expectation).

<domain>
## Phase Boundary

**Trong scope Phase 5 (VER):**

- **VER-01:** Schema migration `0007_document_versions.py` Alembic (introspect pattern carry forward Phase 1 v3.1 Plan 01-01 + Phase 4 v3.0 Plan 04-01) — tạo bảng `document_versions` 15 cột match FE `DocumentVersionAPI` interface (frontend/src/services/api.ts:599-615):
  - `id UUID PRIMARY KEY DEFAULT gen_random_uuid()`
  - `document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE`
  - `version_number INT NOT NULL` (monotonic increment per document_id)
  - `is_original BOOLEAN NOT NULL DEFAULT false` (v1 = is_original true; v2+ = false)
  - `name TEXT NOT NULL` (snapshot filename original từ upload)
  - `file_type TEXT NOT NULL` (mime type or extension)
  - `file_size BIGINT NOT NULL`
  - `file_path TEXT NOT NULL` (UUID-based path từ FileStore; reference, KHÔNG copy binary)
  - `file_hash TEXT` (SHA-256 hex 64-char optional — dedupe key D-V3.1-Phase5-A)
  - `extractor_used TEXT` (snapshot extractor name khi version tạo)
  - `chunk_count INT NOT NULL DEFAULT 0` (snapshot count, KHÔNG snapshot chunks themselves)
  - `change_type TEXT NOT NULL CHECK (change_type IN ('reupload','reextract','content_edit','restore'))`
  - `change_note TEXT` (optional human note)
  - `created_by UUID REFERENCES users(id) ON DELETE SET NULL`
  - `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`
  - `UNIQUE (document_id, version_number)` + index `ix_document_versions_document_id` cho list query.
  - downgrade() full implement — DROP TABLE document_versions (defensive: log COUNT(*) trước DROP).

- **VER-02:** Service layer `app/services/document_version_service.py` — snapshot insert API:
  - `async def snapshot(*, session, document, change_type, change_note=None, actor_user_id=None) -> DocumentVersion`
  - 4 trigger điểm gọi từ `documents_service.py` + router:
    - **reupload preview-confirm flow** (`POST /api/documents/{id}/file` hoặc reupload endpoint hiện tại — snapshot TRƯỚC khi overwrite `documents.file_path`).
    - **edit content** (nếu có endpoint metadata edit — snapshot TRƯỚC khi UPDATE `documents.name|metadata`).
    - **reextract trigger** (cocoindex re-index — snapshot TRƯỚC khi reset chunks).
    - **restore action** (POST /api/documents/{id}/versions/{vid}/restore — snapshot trạng thái hiện tại TRƯỚC khi rollback).
  - `version_number` derive qua `SELECT COALESCE(MAX(version_number), 0) + 1 FROM document_versions WHERE document_id = $1` (UNIQUE constraint backup).
  - `is_original = (version_number == 1)` derive.
  - `file_path` reference (D-V3.1-Phase5-A LOCKED dedupe-by-hash) — nếu `file_hash` đã tồn tại trong document_versions cùng document_id → reference path cũ; nếu file mới upload (reupload với file khác) → store mới qua FileStore.save() rồi reference UUID path mới.
  - **Retention cleanup tự động sau INSERT** (D-V3.1-Phase5-E LOCKED — server-side enforce):
    - Query `SELECT id FROM document_versions WHERE document_id = $1 ORDER BY version_number`
    - Keep set = `{v1, v2, v3}` (3 đầu) + 2 versions cuối (highest version_number).
    - DELETE rows ngoài keep set (cùng transaction INSERT) — version_number monotonic giữ nguyên (KHÔNG re-number).
    - File path cleanup: chỉ DELETE file vật lý qua FileStore.delete() nếu `file_path` KHÔNG còn version nào reference (SELECT COUNT(*) WHERE file_path = $1 → 0).
  - Audit emit (D-V3.1-Phase5-H LOCKED): `action='document.version.create'` payload nest `actor_role` + `actor_hub_id` + `document_id` + `version_number` + `change_type` qua `audit_service.build_audit_payload` (Plan 02-04 carry forward).

- **VER-03:** Router `app/routers/document_versions.py` 4 endpoint mount qua main.py:
  - `GET /api/documents/{document_id}/versions` → `{success: true, data: {versions: DocumentVersionAPI[]}, error: null, meta: null}` envelope shape M2 LOCKED; chronological DESC by `version_number`; KHÔNG paginate (≤ 5 rows sau retention).
  - `GET /api/documents/{document_id}/versions/{version_id}` → `{success: true, data: {version: DocumentVersionAPI, chunks: DocumentVersionChunkAPI[]}}`; **chunks = []** (D-V3.1-Phase5-B LOCKED — KHÔNG snapshot chunks, trả empty array để FE typecheck happy).
  - `GET /api/documents/{document_id}/versions/{version_id}/file` → `StreamingResponse` mime-type từ `version.file_type`; header `Content-Disposition: attachment; filename="v{N}_{name}"` (FE handle download line 79 `v{version_number}_{v.name}`).
  - `POST /api/documents/{document_id}/versions/{version_id}/restore` → snapshot hiện tại TRƯỚC (change_type='restore', append-only D-V3.1-Phase5-D) + UPDATE `documents.file_path|name|file_type|file_size` = giá trị từ version `{version_id}` + trigger re-extract (cocoindex re-index — chunks cập nhật từ file mới); return `{success: true, data: DocumentAPI}` (document refreshed).
  - Mount conditional theo `settings.hub_name` — universal mount (KHÔNG central-only) vì documents là per-hub data. Pattern carry forward Phase 2 v3.0 FACTOR-01 documents_router universal.

- **VER-04:** RBAC hub-scope 3-layer (carry forward Phase 2 v3.1 + v3.0):
  - **Layer 1 (Plan 04-04 v3.0 carry forward):** `_enforce_hub_dsn_match` Settings validator boot-time — hub con DB isolation enforce.
  - **Layer 2 repository-level filter:** Mọi query trong document_version_service join documents → WHERE `documents.hub_id = settings.hub_id` (per-hub isolation). KHÔNG cross-hub query.
  - **Layer 3 dependency `assert_hub_admin_for(user, db, target_hub_id=document.hub_id)` Plan 02-01 carry forward:** 4 endpoint VER-03:
    - `GET /versions` + `GET /versions/{vid}` + `GET /versions/{vid}/file` — viewer + editor + hub_admin + super admin PASS (D-V3.1-Phase5-C LOCKED viewer read-only OK).
    - `POST /versions/{vid}/restore` — hub_admin trong hub đúng + super admin PASS; viewer + editor + cross-hub hub_admin → 403 `HUB_ADMIN_REQUIRED` envelope.
  - Audit emit cho `restore` action: `action='document.version.restore'` payload extend `actor_role + actor_hub_id + document_id + version_number + restored_to`.

- **VER-05:** Integration test pytest + testcontainers (pattern carry forward Plan 04-02 v3.1 `test_smoke_e2e_v3_1_rbac.py` + Plan 01-03 `test_migration_0006_idempotent.py`):
  - File mới `tests/integration/test_document_versions.py` (~350 LOC estimate).
  - 5 scenario (1 more than ROADMAP estimate 4 — bổ sung restore append-only verify):
    1. **Create version qua reupload** — upload doc → reupload với file khác → assert `document_versions` 2 row (v1 is_original=true + v2 change_type='reupload') + file_hash khác nhau.
    2. **List returns ordered DESC** — sau 3 mutation → GET /versions trả `[v3, v2, v1]` (DESC by version_number) + envelope M2 shape.
    3. **Restore tạo version mới change_type='restore'** — POST restore từ v1 → assert v4 INSERT với `change_type='restore'` + documents.file_path UPDATE = v1.file_path + chunks cập nhật từ file v1 (D-V3.1-Phase5-D append-only LOCKED).
    4. **Hub_admin scope enforce 403 cross-hub** — hub_admin dmd GET /versions của document thuộc hub tdt → 403 `HUB_ADMIN_REQUIRED` envelope (carry forward Plan 02-02 D-V3.1-Phase2-A LOCKED).
    5. **Audit forensic chain verified** — `SELECT payload->>'actor_role', payload->>'actor_hub_id', payload->>'document_id', payload->>'version_number' FROM audit_logs WHERE action LIKE 'document.version.%' ORDER BY created_at DESC` — assert metadata exact 4 scenario ops.
  - Reuse `seed_hubs_dmd_tdt` + `auth_client` + `_login_get_token` + `_wait_audit_row` từ conftest.py + `_seed_hub_admin_user` từ test_dep_hubs_scope.py.
  - Test fixture sample file: 2 DOCX nhỏ (~5KB mỗi cái — chỉ test path snapshot, KHÔNG cần cocoindex full extract; mock `coco_flow.run_for_document` qua monkeypatch nếu cần tránh OpenAI API call test infra).

**Ngoài scope (defer v4.0 backlog):**

- **Chunks per-version snapshot** (D-V3.1-Phase5-B LOCKED defer) — Frontend `DocumentVersionChunkAPI` interface (api.ts:633-640) đã có nhưng BE trả `chunks: []` empty. Snapshot chunks per-version cần dedupe strategy + storage explosion (mỗi version × N chunks × 1536-dim vector = nhiều GB). Defer v4.0 cùng dedup strategy thiết kế.
- **File binary content-hash dedupe** (D-V3.1-Phase5-A có touch nhưng full dedupe across documents defer) — Phase 5 dedupe chỉ trong cùng `document_id` (reupload exact same file → reference path cũ). Cross-document dedupe (2 user upload cùng 1 file → 1 binary) defer v4.0 — cần file_store schema migration thêm reference_count.
- **Version diff UI side-by-side compare** — Phase 5 chỉ list + download + restore; diff defer v4.0 frontend feature.
- **Cross-hub version restore** — vi phạm hub isolation (D-V3-01 LOCKED v3.0); 403 reject hard.
- **Retention policy configurable per-hub** — Phase 5 hardcode "3 gốc + 2 gần nhất" trong service code; per-hub override defer v4.0 system_settings extend.
- **Restore re-extract async via cocoindex queue** — Phase 5 simple sync re-extract (block restore endpoint < 5s đối với DOCX nhỏ); async queue defer v4.0.
- **DELETE /api/documents/{id}/versions/{vid}** — ROADMAP VER-03 mention `DELETE /versions/{id}` BUT FE `DocumentVersionHistory.tsx` KHÔNG có delete UI (chỉ list + download + restore). Defer v4.0 — Phase 5 ship 4 endpoint match FE consume (GET list + GET detail + GET file + POST restore).
- **HUMAN-UAT live runtime manual smoke** — automated semantic coverage 5 scenario đủ VER-05 scope; manual smoke defer ops handover (carry forward v3.0 + v3.1 closeout pattern).
- **OCR / scanned PDF version preservation** — Phase 5 KHÔNG đụng D4 LOCKED (carry forward M2 — OCR Vietnamese defer v4.0 + post-v3.1 quick feat 4→8 format extend chỉ áp dụng OCR ảnh, KHÔNG đụng version).

</domain>

<decisions>
## Implementation Decisions (LOCKED)

### D-V3.1-Phase5-A — Snapshot file storage = dedupe-by-hash trong cùng document_id (recommendation GA-V3.1-D LOCKED)

**Recommendation từ ROADMAP §"Discuss-phase gray areas" GA-V3.1-D:** Dedupe qua content-hash + reference (KHÔNG copy binary mỗi version).

**Lý do LOCKED:**
- Storage cost matter — disk explosion khi reupload nhiều lần cùng file (audit trail use case). Hash-based reference O(1) lookup `WHERE file_hash = $1 AND document_id = $2`.
- Reupload exact same file (no content change, only re-trigger workflow) → version_number tăng + change_type='reupload' + file_path reference đường dẫn cũ (KHÔNG ghi file mới qua FileStore.save).
- Reupload file khác (content change) → FileStore.save() tạo UUID path mới + file_hash mới.
- File cleanup tại retention prune: chỉ DELETE file vật lý nếu `file_path` KHÔNG còn version row nào reference (`SELECT COUNT(*) WHERE file_path = $1 → 0`). Pattern carry forward FileStore.delete() idempotent.
- Cross-document dedupe (2 documents khác nhau cùng hash) defer v4.0 — Phase 5 chỉ trong cùng document_id (giảm scope).

**Impact downstream:**
- Plan 05-01 schema: `file_hash TEXT` cột nullable (NULL = legacy data từ documents chưa migrate; new versions BẮT BUỘC compute hash).
- Plan 05-02 service: `_compute_file_hash(path: Path) -> str` helper SHA-256 hex (carry forward chunks.content_hash BYTEA pattern model layer M2 nhưng VER table dùng TEXT hex 64 char cho query-able).
- Plan 05-02 service: snapshot logic check existing hash trong cùng document_id TRƯỚC khi save file; reference path cũ nếu duplicate.
- Plan 05-02 retention cleanup: file delete chỉ khi reference count = 0.

### D-V3.1-Phase5-B — Chunks snapshot per-version = NO snapshot, trả `chunks: []` (recommendation GA-V3.1-E LOCKED)

**Recommendation từ ROADMAP §"Discuss-phase gray areas" GA-V3.1-E:** KHÔNG snapshot chunks (chỉ giữ `chunk_count` + change_type metadata); restore = re-index version file qua cocoindex.

**Lý do LOCKED:**
- Storage cost prohibitive — mỗi version × N chunks × (content TEXT + vector 1536-dim + content_hash) = MB+ per version. 100 documents × 5 versions × 50 chunks = 25K rows + 25K vector embed = ~150MB pgvector index.
- Snapshot semantics murky — chunks là derived data từ file binary qua extractor + chunker. Restore semantic đúng phải re-extract từ file binary (deterministic if extractor pinned), KHÔNG restore chunks frozen (stale extractor logic).
- FE `DocumentVersionChunkAPI` interface (api.ts:633-640) declared NHƯNG `GET /versions/{vid}` BE trả `chunks: []` empty array — FE typecheck happy + render chunks panel skip empty state (`v.chunk_count` displayed line 190 đã đủ UX info).
- Restore endpoint trigger re-extract qua existing `coco_flow.run_for_document(documents.id)` (cocoindex flow Phase 4 v2.0 ship M2) — chunks cập nhật từ file v1 binary deterministic.

**Impact downstream:**
- Plan 05-01 schema: KHÔNG có bảng `document_version_chunks` (defer v4.0).
- Plan 05-03 router GET /versions/{vid} response shape: `{version: <full obj>, chunks: []}` (FE typecheck).
- Plan 05-03 router POST /restore: gọi `coco_flow.run_for_document(doc_id)` qua existing M2 reextract trigger (Plan 05-02 reuse `documents_service.reextract_document` nếu có hoặc inline cocoindex call).
- Plan 05-05 test: assert `chunks` field trả `[]` empty (positive assertion — KHÔNG missing field).

### D-V3.1-Phase5-C — RBAC viewer = GET list + GET detail + GET file PASS, POST restore 403 (recommendation GA-V3.1-F LOCKED)

**Recommendation từ ROADMAP §"Discuss-phase gray areas" GA-V3.1-F:** Viewer GET list OK (read-only feature; same as document detail).

**Lý do LOCKED:**
- Semantic consistency với existing M2 — viewer đã có quyền GET /api/documents/{id} + GET /api/documents/{id}/file ở document detail; version history là view-only extension cùng nguyên tắc.
- 3 endpoint GET tránh hardcode role check — pattern qua `get_current_user_for_hub_access` (Layer 3 SSO-04 carry forward) check `document.hub_id ∈ user.hub_ids` JWT claim; KHÔNG cần phân biệt viewer/editor/hub_admin (Layer 3 đã enforce hub isolation).
- POST /restore endpoint gắn `assert_hub_admin_for(user, db, target_hub_id=document.hub_id)` qua hybrid pattern Plan 02-01 — viewer + cross-hub hub_admin reject 403 `HUB_ADMIN_REQUIRED`.
- FE `DocumentVersionHistory.tsx` line 19 prop `canRestore?: boolean` parent component truyền — viewer KHÔNG truyền canRestore=true → button Khôi phục KHÔNG render. BE Layer 3 defense-in-depth (FE UX + BE authoritative).

**Impact downstream:**
- Plan 05-03 router 3 GET endpoint: `Depends(get_current_user_for_hub_access)` (Phase 3 v3.0 SSO-04 carry forward) — hub isolation đủ; KHÔNG cần explicit role check.
- Plan 05-03 router POST /restore: `Depends(get_current_user)` + inline `await assert_hub_admin_for(user=user, db=db, target_hub_id=document.hub_id)` sau resolve document.
- Plan 05-04 RBAC test: 4 role × 4 endpoint matrix → 16 case ngắn (1 test với parametrize markers).

### D-V3.1-Phase5-D — Restore semantics = APPEND-ONLY (recommendation GA-V3.1-H LOCKED)

**Recommendation từ ROADMAP §"Discuss-phase gray areas" GA-V3.1-H:** Append-only (immutable history).

**Lý do LOCKED:**
- Audit trail requirement — version history là evidence chain cho compliance; immutable history KHÔNG cho phép xoá row (giống audit_logs pattern M2).
- Restore semantic clear — POST /restore từ v1 → snapshot hiện tại (v_max+1, change_type='restore') TRƯỚC khi rollback documents row; user thấy history `[v_max+1 restore, v_max, ..., v2, v1]` đầy đủ.
- Overwrite + delete newer pattern = data loss risk; nếu user lỡ tay restore wrong version → KHÔNG recovery.
- Storage cost bounded qua retention "3 gốc + 2 gần nhất" (D-V3.1-Phase5-E) — append-only KHÔNG nghĩa là unbounded growth.
- FE `DocumentVersionHistory.tsx` line 86-104 `handleRestore` confirm dialog "Phiên bản hiện tại sẽ được lưu lại trước khi ghi đè" — append-only match user expectation.

**Impact downstream:**
- Plan 05-02 service `snapshot(change_type='restore')` insert version mới TRƯỚC khi UPDATE documents (cùng transaction).
- Plan 05-03 router POST /restore implementation atomic: BEGIN → snapshot(restore) → UPDATE documents.file_path|name|file_type|file_size từ version target → coco_flow.run_for_document(doc_id) → audit_logs INSERT action='document.version.restore' → COMMIT.
- Plan 05-04 test scenario 3: assert sau restore từ v1, total versions = original + 1 + 1 (restore version_number = max+1, KHÔNG xoá v2/v3).

### D-V3.1-Phase5-E — Retention policy "3 gốc + 2 gần nhất" enforce ở **BE write-time service-side** (DEVIATION từ recommendation GA-V3.1-G; codebase audit override)

**Recommendation từ ROADMAP §"Discuss-phase gray areas" GA-V3.1-G:** FE filter client-side, BE trả full chronological DESC.

**DEVIATION lý do (auto-mode Claude codebase audit 2026-05-26):**
- FE `DocumentVersionHistory.tsx` line 158 `versions.map(...)` render TẤT CẢ versions BE trả về — KHÔNG có client-side filter logic. Nếu BE trả full (5+ versions sau nhiều mutation), FE render full → conflict với hint line 146 "Lưu tối đa 5 phiên bản".
- FE comment line 148 "Các phiên bản giữa được dọn tự động" = "Middle versions are auto-cleaned" — explicit báo user BE đã prune. UX expectation rõ ràng: BE prune.
- BE write-time cleanup (sau INSERT version mới, cùng transaction) là canonical implementation — đảm bảo invariant `COUNT(*) ≤ 5 per document_id` (v1, v2, v3 + 2 gần nhất). Idempotent retry-safe (re-run cleanup logic không gây side effect khác).
- Alternative "BE return all + FE filter" = FE complexity tăng (logic 3-most-recent identification + edge case khi < 5 versions). FE đơn giản hơn nếu BE prune.

**Implementation chi tiết:**
- Sau INSERT version mới trong `document_version_service.snapshot()`:
  ```python
  # Pseudo SQL trong cùng transaction
  WITH ranked AS (
      SELECT id, version_number,
             ROW_NUMBER() OVER (PARTITION BY document_id ORDER BY version_number) AS asc_rank,
             ROW_NUMBER() OVER (PARTITION BY document_id ORDER BY version_number DESC) AS desc_rank
      FROM document_versions
      WHERE document_id = $1
  )
  DELETE FROM document_versions
  WHERE id IN (
      SELECT id FROM ranked
      WHERE asc_rank > 3 AND desc_rank > 2  -- KHÔNG phải v1/v2/v3 (asc) VÀ KHÔNG phải 2 gần nhất (desc)
  )
  RETURNING file_path;
  ```
- Sau DELETE, check file reference count cho mỗi `file_path` trả về:
  ```python
  for path in deleted_paths:
      remaining = await session.scalar(select(func.count()).where(DocumentVersion.file_path == path))
      if remaining == 0:
          file_store.delete(Path(path))  # FileStore.delete idempotent
  ```

**Impact downstream:**
- Plan 05-02 service `snapshot()` cuối transaction gọi `_enforce_retention(document_id)` helper.
- Plan 05-02 helper `_enforce_retention` raw SQL CTE query (KHÔNG SQLAlchemy ORM — complexity của window function + DELETE returning).
- Plan 05-03 router GET /versions trả TRỌN list (≤ 5 rows) KHÔNG paginate; FE render tất cả.
- Plan 05-04 test scenario phụ thuộc retention: tạo 6 versions → assert `COUNT(*) == 5` + version_number `[1, 2, 3, 5, 6]` (v4 prune).

### D-V3.1-Phase5-F — Plan count = 5 (Wave 1 schema + Wave 2 service + Wave 3 router + Wave 4 test + Wave 5 closeout)

**Rationale (Claude codebase audit 2026-05-26):**
- Phase 1 v3.1 (4 REQ) = 3 plan; Phase 2 v3.1 (5 REQ) = 5 plan; Phase 3 v3.1 (4 REQ) = 4 plan; Phase 4 v3.1 (2 REQ) = 3 plan. Phase 5 (5 REQ-ID — VER-01..05) → 5 plan đủ. Match ROADMAP estimate "4-5 plans".
- Wave 1 BLOCKING Plan 05-01: Schema migration 0007_document_versions Alembic (VER-01). Khoảng 200 LOC + introspect upgrade + downgrade + 5 unit/integration test idempotent.
- Wave 2 BLOCKING Plan 05-02: Service layer document_version_service.py (VER-02) + retention enforcement helper. Khoảng 350 LOC + 8 unit test snapshot semantics + retention cleanup.
- Wave 3 BLOCKING Plan 05-03: Router document_versions.py 4 endpoint + RBAC integration (VER-03 + VER-04). Khoảng 250 LOC + 8 unit test endpoint logic + 4 integration test smoke.
- Wave 4 BLOCKING Plan 05-04: Integration test test_document_versions.py 5 scenario E2E (VER-05) + audit forensic + RBAC hub-scope verify. Khoảng 350 LOC + reuse fixtures Plan 04-02 v3.1.
- Wave 5 BLOCKING Plan 05-05: Closeout 4 docs atomic + STATE.md update v3.1 re-opened completion. Nếu Phase 5 = phase cuối re-opened scope → git tag v3.1.1 annotate hoặc no tag (operator decide).

**Wave critical path:** 1 (1 plan BLOCKING) → 2 (1 plan BLOCKING) → 3 (1 plan BLOCKING) → 4 (1 plan BLOCKING) → 5 (1 plan BLOCKING) = 5 plan total. KHÔNG parallel-able — schema enable service; service enable router; router enable integration test; integration test enable closeout.

**Impact downstream:**
- Total 5 plan match ROADMAP "4-5 plans estimate".
- Plan 05-01: Alembic migration + integration test idempotent + downgrade safety.
- Plan 05-02: Service implementation + unit test semantics.
- Plan 05-03: Router 4 endpoint + RBAC dep integration.
- Plan 05-04: E2E 5 scenario test file mới.
- Plan 05-05: Docs + STATE.md (KHÔNG git tag v3.1.1 mặc định — operator decide).

### D-V3.1-Phase5-G — Migration revision name = `0007_document_versions`

**Rationale:**
- Sequence next sau `0006_role_hub_admin.py` (Phase 1 v3.1 LOCKED ship).
- Naming pattern carry forward 0005 + 0006 (snake_case feature description).
- `down_revision = "0006"` (string), `revision = "0007"`.

**Impact downstream:**
- Plan 05-01: File path `Hub_All/api/migrations/versions/0007_document_versions.py`.
- Plan 05-04: Test reset migration đến `0007` head (KHÔNG specify revision number cứng — `alembic upgrade head` mặc định).

### D-V3.1-Phase5-H — Audit action codes = `document.version.create` + `document.version.restore`

**Rationale:**
- 2 action emit theo trigger: `create` cho 3 trigger (reupload, reextract, content_edit) + `restore` riêng (POST /restore).
- Payload schema (carry forward Plan 02-04 `build_audit_payload` helper):
  ```python
  {
      "actor_role": "hub_admin",   # admin | hub_admin | editor | viewer
      "actor_hub_id": "<uuid>",    # NULL nếu super admin
      "document_id": "<uuid>",
      "version_number": 5,
      "change_type": "reupload",   # match document_versions.change_type
      "restored_to": "<version_id>",  # ONLY khi action='document.version.restore'
  }
  ```
- Forensic query example: `SELECT payload->>'document_id', payload->>'version_number', payload->>'restored_to' FROM audit_logs WHERE action='document.version.restore' ORDER BY created_at DESC LIMIT 10`.

**Impact downstream:**
- Plan 05-02 service emit `enqueue_audit(action='document.version.create', payload=build_audit_payload(...))` mỗi snapshot.
- Plan 05-03 router POST /restore emit thêm `action='document.version.restore'` (NGOÀI snapshot create của plan 05-02 — tổng 2 audit rows per restore).
- Plan 05-04 test scenario 5 forensic query assert 2 distinct actions + metadata exact.

### D-V3.1-Phase5-I — Reextract async vs sync trong POST /restore = SYNC (block endpoint, < 5s small DOCX) Phase 5 default

**Rationale:**
- Phase 5 small scope catch-up; cocoindex re-extract DOCX nhỏ (< 1MB) hoàn tất < 5s in-process — acceptable user wait time (loading state FE line 214 `<Loader2 animate-spin />`).
- Async queue defer v4.0 — cần infra Celery/RQ/Postgres LISTEN/NOTIFY job queue + status polling endpoint + FE polling logic. Out of scope Phase 5 catch-up.
- Edge case large file (> 10MB) — accept temporary block; document trong README operator + warn FE alert nếu file_size > threshold (defer v4.0).

**Impact downstream:**
- Plan 05-02 service `restore_to_version(document_id, version_id)` gọi `coco_flow.run_for_document(document_id)` sync (KHÔNG `asyncio.create_task` background).
- Plan 05-03 router POST /restore await full re-extract trước khi return — response trả document refreshed với new chunk_count.
- Plan 05-04 test scenario 3 mock cocoindex flow hoặc fixture small DOCX < 100KB để test < 1s.

### Claude's Discretion

Plan-phase agent quyết định:
- **Migration column order trong CREATE TABLE statement** — Alembic introspect-friendly đặt PK + FK columns đầu, metadata cuối.
- **Helper function placement** — `_compute_file_hash` ở `document_version_service.py` HOẶC `file_store.py` (depends reuse cross-service).
- **Audit payload helper** — reuse `build_audit_payload(actor_role, actor_hub_id, extra={...})` (Plan 02-04 LOCKED) HOẶC tạo wrapper `build_version_audit_payload` extend.
- **Test fixture sample DOCX** — tạo 2 file qua python-docx inline trong test setup HOẶC reuse `fixtures/sample-document.docx` từ Plan 07-05 v3.0 (depends path).
- **Cocoindex mock vs real** — Plan 05-04 test có thể mock `coco_flow.run_for_document` qua monkeypatch (avoid OpenAI API call test env) HOẶC use `COCOINDEX_SKIP_SETUP=1` escape hatch existing (carry forward Phase 4 v2.0).
- **Reextract endpoint discovery** — Plan 05-02 trigger reextract qua existing service function HOẶC inline cocoindex call (depends documents_service.py existing API).
- **Pytest marker phối hợp** — `@pytest.mark.critical @pytest.mark.integration` cả 2 (carry forward Plan 04-02 v3.1) HOẶC chỉ `@pytest.mark.integration` (depends pytest.ini config).
- **OpenAPI tag cho router** — `tags=["Documents"]` (cùng với documents_router) HOẶC `tags=["Document Versions"]` (depends OpenAPI grouping convention).
- **Closeout git tag** — Plan 05-05 KHÔNG tạo tag mới (v3.1 đã tag 2026-05-24) HOẶC tag v3.1.1 annotate "v3.1.1 Phase 5 Document version history" (depends operator preference; default KHÔNG tag mới để giữ semver clean).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### v3.1 Phase 5 prior artifacts (carry forward)

- `Hub_All/.planning/ROADMAP.md` §"Phase 5 — Document version history (VER)" — 5 success criteria + 5 gray areas GA-V3.1-D..H + Plans estimate (Plan 05-05 closeout update).
- `Hub_All/.planning/REQUIREMENTS.md` — bổ sung VER-01..05 (5 REQ-ID) chưa có trong file hiện tại (REQ-ID block dừng ở MIGRATE-02 v3.1 Phase 4). Plan 05-05 closeout APPEND section mới.
- `Hub_All/.planning/STATE.md` — v3.1 re-opened 2026-05-26 (`phase_5_status: PLANNED`, `next_action: /gsd-discuss-phase 5`). Plan 05-05 closeout update Phase 5 Results Summary.
- `Hub_All/CLAUDE.md` §6 — milestone close note v3.1 (line cuối). Plan 05-05 APPEND `### Phase 5 v3.1 Document version history pattern (VER-01..05 — 2026-05-26)` subsection.

### v3.1 Phase 1-4 prior artifacts (RBAC + migration pattern carry forward)

- `Hub_All/.planning/phases/01-rbac-schema-migration/01-01-PLAN.md` — Alembic migration introspect pattern (`sa.inspect()` 3 STEP upgrade + downgrade defensive). Plan 05-01 mirror pattern cho 0007 migration.
- `Hub_All/.planning/phases/01-rbac-schema-migration/01-03-PLAN.md` — Integration test idempotent pattern + SAFETY DSN injection fix I-01 + I-02 (Plan 05-01 chạy test idempotent cho 0007).
- `Hub_All/.planning/phases/02-backend-rbac-enforcement/02-01-PLAN.md` — `assert_hub_admin_for(user, db, target_hub_id)` validator + envelope `HUB_ADMIN_REQUIRED`. Plan 05-03 router POST /restore reuse.
- `Hub_All/.planning/phases/02-backend-rbac-enforcement/02-04-PLAN.md` — `build_audit_payload(actor_role, actor_hub_id, extra)` helper + B7 iter 1 future-proof guard. Plan 05-02 + 05-03 reuse cho audit emit.
- `Hub_All/.planning/phases/04-migration-smoke-e2e/04-02-PLAN.md` — `test_smoke_e2e_v3_1_rbac.py` 4 scenario pattern + `seed_hubs_dmd_tdt` fixture + `_assert_audit_actor_metadata` helper. Plan 05-04 mirror cho test_document_versions.py.
- `Hub_All/.planning/phases/04-migration-smoke-e2e/04-CONTEXT.md` — D-V3.1-Phase4-C testcontainers in-process pattern LOCKED. Plan 05-04 carry forward.

### v3.0 + M2 prior patterns (carry forward)

- `Hub_All/.planning/phases/04-cross-hub-data-sync/04-01-PLAN.md` v3.0 — Alembic 0005 introspect + trigger AFTER INSERT/DELETE pattern. Plan 05-01 reference cho 0007 introspect guard.
- `Hub_All/.planning/phases/03-auth-sso-hub-ids-jwt/03-03-PLAN.md` v3.0 — `get_current_user_for_hub_access` Layer 3 SSO-04 dependency. Plan 05-03 GET endpoint reuse cho hub isolation.

### Backend existing source-of-truth

- `Hub_All/api/migrations/versions/0006_role_hub_admin.py` — Plan 01-01 v3.1 ship (LOCKED, KHÔNG modify). Plan 05-01 sequence sau (`down_revision = "0006"`).
- `Hub_All/api/app/models/document.py` — Documents ORM model (Plan 05-01 ADD `DocumentVersion` model new — KHÔNG đụng Documents model existing).
- `Hub_All/api/app/services/file_store.py` — `FileStore.save() + load() + delete()` API. Plan 05-02 reuse — KHÔNG đụng FileStore service existing.
- `Hub_All/api/app/services/audit_service.py` — `build_audit_payload` helper + `enqueue_audit` API. Plan 05-02 + 05-03 reuse.
- `Hub_All/api/app/services/documents_service.py` — existing CRUD + reupload + reextract logic. Plan 05-02 service hook vào 3 trigger điểm.
- `Hub_All/api/app/routers/documents.py` — 6 endpoint hiện tại (POST upload, GET detail/status/file/list, DELETE). Plan 05-03 router MỚI mount riêng — KHÔNG sửa documents.py.
- `Hub_All/api/app/auth/dependencies.py` — `assert_hub_admin_for` + `get_current_user` + `get_current_user_for_hub_access`. Plan 05-03 4 endpoint reuse.
- `Hub_All/api/app/auth/role.py::get_effective_role` — Plan 01-02 v3.1 ship helper. Plan 05-03 indirect carry forward qua assert_hub_admin_for.
- `Hub_All/api/app/main.py::create_app` — Plan 05-03 ADD `app.include_router(document_versions_router, ...)` universal mount (KHÔNG central-only).
- `Hub_All/api/migrations/env.py:185-191` — runtime sqlalchemy.url OVERRIDE từ Settings (SAFETY-CRITICAL pattern Plan 01-03 carry forward).

### Frontend existing source-of-truth (R-V3-2 minimal scope — KHÔNG đụng FE)

- `Hub_All/frontend/src/components/DocumentVersionHistory.tsx` — Component đã ship (229 LOC). Phase 5 BE catch-up KHÔNG sửa FE.
- `Hub_All/frontend/src/services/api.ts:268-285` — 4 API call method (listDocumentVersions, getDocumentVersion, getDocumentVersionFileUrl, restoreDocumentVersion). Plan 05-03 router 4 endpoint match exact URL + envelope shape.
- `Hub_All/frontend/src/services/api.ts:599-615` — `DocumentVersionAPI` interface (15 field). Plan 05-01 schema match exact column shape (BE → FE response serialization).
- `Hub_All/frontend/src/services/api.ts:633-640` — `DocumentVersionChunkAPI` interface (6 field). Plan 05-03 GET /versions/{vid} trả `chunks: []` empty array để FE typecheck pass (D-V3.1-Phase5-B LOCKED).

### Test infrastructure existing (Phase 1-4 v3.1 + v3.0 carry forward)

- `Hub_All/api/tests/integration/conftest.py` — `postgres_container` + `redis_container` + `alembic_cfg` + `app_with_auth` + `seed_hubs_dmd_tdt` (Plan 04-02 v3.1 ship). Plan 05-04 reuse.
- `Hub_All/api/tests/integration/test_smoke_e2e_v3_1_rbac.py` — Plan 04-02 v3.1 ship 4 scenario E2E (~430 LOC). Plan 05-04 mirror pattern cho 5 scenario document_versions.
- `Hub_All/api/tests/integration/test_dep_hubs_scope.py` — Plan 02-02 v3.1 ship — helper `_seed_hub_admin_user` line 37-76 reuse Plan 05-04.
- `Hub_All/api/tests/integration/test_audit_actor_metadata.py` — Plan 02-04 v3.1 ship — forensic query pattern `payload->>'actor_role'` reuse Plan 05-04 scenario 5.
- `Hub_All/api/tests/conftest.py:778-806` — `_wait_audit_row` poll helper (BackgroundTask audit emit timing). Plan 05-04 reuse.
- `Hub_All/api/Makefile` — `test-integration` + `test-migration` target (Plan 04-01 v3.1 ship). Plan 05-04 chạy bắt buộc qua existing target.

### Memory references (user-level cross-session)

- `memory/project_rbac_hub_admin_gap.md` — Role per-hub LOCKED M2 invariant (admin = GLOBAL super-admin). Plan 05-03 RBAC layer enforce.
- `memory/project_real_hubs_deployment.md` — 2 hub thật DB (dmd + tdt). Plan 05-04 test seed scope.
- `memory/project_fastapi_bgtask_commit.md` — BackgroundTask audit emit commit SAU task; helper `_wait_audit_row` poll pattern. Plan 05-04 scenario 5 carry forward.
- `memory/project_asyncpg_timestamptz_param.md` — Raw SQL filter ngày phải dùng `$N::text::timestamptz`. Plan 05-04 nếu có query filter created_at (KHÔNG cần cho Phase 5 — list KHÔNG paginate by date).
- `memory/project_v3_milestone_started.md` — v3.x naming convention reference.
- `memory/feedback_surface_error_message.md` — UI failure phải render `documents.error_message` thay vì "Không rõ nguyên nhân". KHÔNG áp dụng Phase 5 (BE scope) NHƯNG ghi nhận pattern khi router error envelope generate.
- `memory/project_jsonb_boolean_str_bug.md` — system_settings_service _parse_jsonb over-parse JSONB string "true" → bool True. KHÔNG áp dụng Phase 5 (document_versions KHÔNG dùng JSONB column).
- `memory/project_file_format_extended.md` — ALLOWED_EXTENSIONS 8 format post-v3.1. Phase 5 version history áp dụng cho ALL 8 format (KHÔNG limit text-only).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets (Phase 1-4 v3.1 + v3.0 + M2 carry forward)

- **`api/app/services/file_store.py::FileStore`** — `save(content, original_filename) -> Path` + `load(path) -> bytes` + `delete(path) -> bool`. Plan 05-02 reuse cho file binary store khi reupload với file khác hash.
- **`api/app/services/audit_service.py::build_audit_payload + enqueue_audit`** — Plan 02-04 v3.1 ship. Plan 05-02 + 05-03 reuse cho 2 action `document.version.{create,restore}`.
- **`api/app/auth/dependencies.py::assert_hub_admin_for`** — Plan 02-01 v3.1 ship. Plan 05-03 POST /restore endpoint inline check sau resolve document.hub_id.
- **`api/app/auth/dependencies.py::get_current_user_for_hub_access`** — Plan 03-03 v3.0 ship Layer 3 SSO-04. Plan 05-03 3 GET endpoint hub isolation đủ.
- **`api/app/services/documents_service.py`** — existing CRUD + reupload + reextract trigger points. Plan 05-02 hook vào 4 mutation điểm (reupload + content_edit + reextract + restore).
- **`api/app/models/chunk.py:54` `content_hash: Mapped[bytes]`** — M2 chunks model pattern (BYTEA at-rest). Plan 05-01 dùng TEXT hex 64-char cho file_hash (query-able qua `WHERE file_hash = $1` simple equality — KHÔNG cần `encode(content_hash, 'hex')`).
- **`api/migrations/versions/0006_role_hub_admin.py`** — Plan 01-01 v3.1 ship introspect pattern. Plan 05-01 mirror 3-STEP upgrade + defensive downgrade.
- **`api/tests/integration/conftest.py::app_with_auth + seed_hubs_dmd_tdt + auth_client + _login_get_token + GO_SEED_HASH + admin_user|admin_token|viewer_user|viewer_token`** — Plan 05-04 reuse hoàn toàn.

### Established Patterns

- **Alembic migration introspect** (`sa.inspect(conn).get_columns / get_check_constraints`) — Plan 01-01 v3.1 + Plan 04-01 v3.0 pattern. Plan 05-01 STEP 1: check `document_versions` table KHÔNG tồn tại (skip CREATE TABLE nếu re-run) + STEP 2: check `documents` table tồn tại (precondition FK).
- **Service layer snapshot atomic transaction** — Pattern carry forward `documents_service` reupload/reextract. Plan 05-02 `snapshot()` + retention cleanup cùng transaction `session.flush()` TRƯỚC commit.
- **Audit emit BackgroundTask fire-and-forget + `_wait_audit_row` poll** — Pattern Plan 02-04 v3.1. Plan 05-04 scenario 5 reuse.
- **RBAC 3-layer (DSN + repository + dependency)** — Pattern carry forward Phase 3 v3.0 SSO-04. Plan 05-03 router enforce Layer 3.
- **Universal router mount (KHÔNG central-only)** — Plan 05-03 mount qua `main.py::create_app` UNIVERSAL (giống documents_router) — documents là per-hub data, KHÔNG central-only.
- **Hub isolation defense in depth** — FE prop `canRestore` (UX layer) + BE Layer 3 `assert_hub_admin_for` (authoritative). Plan 05-03 KHÔNG trust FE.
- **Append-only history** — Pattern carry forward audit_logs M2. Plan 05-02 + 05-03 KHÔNG cho DELETE version row qua endpoint user-facing (chỉ retention cleanup service-side internal).
- **Test seed via auth_client + _login_get_token** — Pattern Plan 04-02 v3.1. Plan 05-04 reuse.
- **Closeout 4 docs atomic** — Pattern Plan 02-05 + 03-04 + 04-03 v3.1. Plan 05-05 mirror (STATE.md + REQUIREMENTS.md + ROADMAP.md + CLAUDE.md).
- **CLAUDE.md §6 subsection APPEND** — Pattern carry forward Phase 1..4 v3.1. Plan 05-05 APPEND `### Phase 5 v3.1 Document version history pattern (VER-01..05 — 2026-05-26)` + bump trailing `*Cập nhật:` line.

### Integration Points

- **`api/app/services/documents_service.py` reupload + reextract trigger** — Plan 05-02 ADD `await document_version_service.snapshot(session, document, change_type='reupload', actor_user_id=user.id)` TRƯỚC khi `document.file_path = new_path`. Pattern carry forward FastAPI BackgroundTask commit ordering (memory `project_fastapi_bgtask_commit`).
- **`api/app/main.py::create_app` router include** — Plan 05-03 ADD `app.include_router(document_versions_router)` SAU `documents_router` block (universal mount).
- **`Hub_All/api/migrations/versions/0007_document_versions.py` → conftest `alembic_cfg` fixture** — Plan 05-01 + 05-04 `alembic upgrade head` apply 0007 schema.
- **`api/app/routers/document_versions.py` → frontend `api.listDocumentVersions(id)`** — Plan 05-03 endpoint URL exact match `GET /api/documents/{document_id}/versions` + envelope M2 `{success, data: {versions: [...]}, error, meta}`.
- **`api/app/services/document_version_service.py::snapshot` → `audit_service.enqueue_audit` + `build_audit_payload`** — Plan 05-02 emit `action='document.version.create'` payload nest actor_role + actor_hub_id + document_id + version_number + change_type.

### Constraint (R-V3.1-1/-2 v3.1 carry forward + Phase 5 new constraints)

- **R-V3.1-2 frontend role bypass mitigation Phase 5:**
  - BE Layer 3 `assert_hub_admin_for` authoritative — KHÔNG dựa FE `canRestore` prop. Plan 05-03 POST /restore enforce.
  - Test Plan 05-04 scenario 4 hub_admin dmd → document tdt → 403 verify defense in depth.
- **Phase 5 new: Storage explosion mitigation D-V3.1-Phase5-A + D-V3.1-Phase5-E chain:**
  - Dedupe-by-hash trong cùng document_id (reupload exact same file → reference path cũ).
  - Retention "3 gốc + 2 gần nhất" cap COUNT(*) ≤ 5 per document.
  - File cleanup tại retention prune (reference count = 0 → physical delete).
  - Worst case 1 document × 5 versions × 5MB DOCX = 25MB; 1000 documents = 25GB (acceptable VPS).
- **Phase 5 new: Cocoindex re-extract sync block D-V3.1-Phase5-I:**
  - Mitigation: ALLOWED_EXTENSIONS 8 format text extract < 5s small file; large file (> 10MB) warn UI defer v4.0 async queue.
- **Phase 5 new: FE contract LOCKED — KHÔNG đụng frontend (R-V3-2 minimal scope):**
  - Plan 05-01 schema 15 field exact match `DocumentVersionAPI` interface (api.ts:599-615).
  - Plan 05-03 4 endpoint URL + response envelope exact match api.ts:268-285.
  - 1 test giả hành ship Plan 05-04 verify FE typecheck `chunks: []` empty array.

</code_context>

<specifics>
## Specific Ideas

### Plan 05-01 — Alembic 0007 migration `document_versions` table

```python
"""0007 — document_versions table for Phase 5 v3.1 (VER-01).

Carry forward Plan 01-01 v3.1 introspect pattern + Plan 04-01 v3.0 introspect.
- STEP 1: check document_versions table KHÔNG tồn tại (idempotent re-run).
- STEP 2: check documents table tồn tại (precondition FK target).
- CREATE TABLE document_versions (15 cột match DocumentVersionAPI).
- UNIQUE (document_id, version_number) + index ix_document_versions_document_id.
- downgrade: DROP TABLE document_versions (log COUNT(*) trước drop).
"""
revision = "0007"
down_revision = "0006"

def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    # STEP 1: idempotent check
    if "document_versions" in inspector.get_table_names():
        print("[migration 0007] document_versions already exists — skip CREATE")
        return

    # STEP 2: precondition
    if "documents" not in inspector.get_table_names():
        raise RuntimeError("Migration 0007 requires documents table — run upgrade head sequential")

    # STEP 3: CREATE TABLE
    op.create_table(
        "document_versions",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("document_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("is_original", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("file_type", sa.Text(), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("file_hash", sa.Text(), nullable=True),  # SHA-256 hex 64-char optional
        sa.Column("extractor_used", sa.Text(), nullable=True),
        sa.Column("chunk_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("change_type", sa.Text(), nullable=False),
        sa.Column("change_note", sa.Text(), nullable=True),
        sa.Column("created_by", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.dialects.postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("document_id", "version_number", name="uq_document_versions_doc_ver"),
        sa.CheckConstraint("change_type IN ('reupload','reextract','content_edit','restore')", name="ck_document_versions_change_type"),
    )
    op.create_index("ix_document_versions_document_id", "document_versions", ["document_id"])

def downgrade() -> None:
    conn = op.get_bind()
    count_result = conn.execute(sa.text("SELECT COUNT(*) FROM document_versions")).scalar()
    print(f"[migration 0007 downgrade] dropping document_versions table with {count_result} existing rows")
    op.drop_index("ix_document_versions_document_id", table_name="document_versions")
    op.drop_table("document_versions")
```

### Plan 05-02 — Service `document_version_service.py` core API

```python
"""document_version_service.py — VER-02 service layer.

API:
- snapshot(*, session, document, change_type, change_note=None, actor_user_id=None) -> DocumentVersion
- restore_to_version(*, session, document_id, version_id, actor_user_id) -> Document
- list_versions(session, document_id) -> list[DocumentVersion]
- get_version_with_chunks(session, document_id, version_id) -> tuple[DocumentVersion, list]  # chunks=[]
- get_version_file_path(session, document_id, version_id) -> Path

Helper:
- _compute_file_hash(path: Path) -> str  # SHA-256 hex 64-char
- _enforce_retention(session, document_id) -> list[Path]  # deleted file paths
"""
import hashlib
from pathlib import Path

async def snapshot(*, session, document, change_type, change_note=None, actor_user_id=None) -> DocumentVersion:
    """Tạo version snapshot cho document.

    1. Compute file_hash từ current document.file_path (SHA-256).
    2. Check existing version có cùng (document_id, file_hash) → reference path cũ; otherwise reference new path.
    3. version_number = MAX(version_number) + 1.
    4. is_original = (version_number == 1).
    5. INSERT row + audit emit 'document.version.create'.
    6. _enforce_retention → DELETE middle versions + cleanup file path nếu zero reference.
    """
    # ... implementation chi tiết Plan 05-02

async def restore_to_version(*, session, document_id, version_id, actor_user_id) -> Document:
    """Rollback document về trạng thái version target (append-only D-V3.1-Phase5-D LOCKED).

    1. Resolve target version từ document_versions.
    2. snapshot(change_type='restore', change_note=f"Restore to v{N}") — cùng transaction TRƯỚC khi UPDATE.
    3. UPDATE documents.file_path|name|file_type|file_size = giá trị từ target version.
    4. Trigger coco_flow.run_for_document(document_id) sync — chunks cập nhật từ file v_target.
    5. Audit emit 'document.version.restore' payload nest restored_to=version_id.
    6. Return document refreshed.
    """
    # ... implementation chi tiết Plan 05-02

def _enforce_retention(session, document_id) -> list[Path]:
    """Retention cleanup '3 gốc + 2 gần nhất' (D-V3.1-Phase5-E LOCKED BE write-time).

    SQL CTE:
    WITH ranked AS (
        SELECT id, version_number, file_path,
               ROW_NUMBER() OVER (PARTITION BY document_id ORDER BY version_number) AS asc_rank,
               ROW_NUMBER() OVER (PARTITION BY document_id ORDER BY version_number DESC) AS desc_rank
        FROM document_versions
        WHERE document_id = :doc_id
    )
    DELETE FROM document_versions
    WHERE id IN (SELECT id FROM ranked WHERE asc_rank > 3 AND desc_rank > 2)
    RETURNING file_path;
    """
    # ... return list of file_path strings deleted
```

### Plan 05-03 — Router `document_versions.py` 4 endpoint

```python
"""document_versions.py — VER-03 router 4 endpoint."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/api/documents", tags=["Document Versions"])

@router.get("/{document_id}/versions", response_model=None)
async def list_document_versions(
    document_id: UUID,
    user: User = Depends(get_current_user_for_hub_access),  # Layer 3 SSO-04
    db: AsyncSession = Depends(get_session),
):
    """GET versions list — viewer + editor + hub_admin + super admin PASS.

    Hub isolation enforce qua Layer 3 (document.hub_id ∈ user.hub_ids).
    Returns envelope: {success: true, data: {versions: [...]}, error: null, meta: null}
    """
    document = await documents_service.get_document_or_404(db, document_id)
    # Hub isolation Layer 3 already enforced via Depends; no explicit check needed
    versions = await document_version_service.list_versions(db, document_id)
    return success_envelope({"versions": [v.to_api_dict() for v in versions]})

@router.get("/{document_id}/versions/{version_id}", response_model=None)
async def get_document_version_detail(...):
    """GET version detail — chunks: [] empty (D-V3.1-Phase5-B LOCKED)."""
    # ... return {"version": {...}, "chunks": []}

@router.get("/{document_id}/versions/{version_id}/file", response_model=None)
async def download_document_version_file(...):
    """GET file binary — StreamingResponse với Content-Disposition attachment."""
    # ...

@router.post("/{document_id}/versions/{version_id}/restore", response_model=None)
async def restore_document_to_version(
    document_id: UUID,
    version_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
    background_tasks: BackgroundTasks = None,
):
    """POST restore — hub_admin + super admin PASS; viewer + cross-hub → 403."""
    document = await documents_service.get_document_or_404(db, document_id)
    await assert_hub_admin_for(user=user, db=db, target_hub_id=document.hub_id)
    refreshed = await document_version_service.restore_to_version(
        session=db, document_id=document_id, version_id=version_id, actor_user_id=user.id,
    )
    return success_envelope(refreshed.to_api_dict())
```

### Plan 05-04 — Test fixture sample DOCX seed (Plan 05-04)

```python
# tests/integration/test_document_versions.py
import pytest
from pathlib import Path
from docx import Document  # python-docx (already in pyproject.toml — M2 extractor dep)

@pytest.fixture
async def sample_docs():
    """Tạo 2 DOCX nhỏ (~5KB) inline qua python-docx — KHÔNG cần fixture file disk."""
    doc1 = Document()
    doc1.add_paragraph("Sample document v1 — vaccin covid 2026")
    doc2 = Document()
    doc2.add_paragraph("Sample document v2 — vaccin covid updated 2026-05")

    path1 = Path(tempfile.mkdtemp()) / "sample-v1.docx"
    path2 = Path(tempfile.mkdtemp()) / "sample-v2.docx"
    doc1.save(path1)
    doc2.save(path2)
    return [path1, path2]

@pytest.mark.critical
@pytest.mark.integration
async def test_create_version_via_reupload(auth_client, admin_token, sample_docs, postgres_container, ...):
    """Scenario 1: upload + reupload → 2 version rows."""
    # POST /api/documents/upload với sample_docs[0]
    # POST /api/documents/{id}/file (reupload) với sample_docs[1]
    # GET /api/documents/{id}/versions → assert len = 2 + v1.is_original=True + v2.change_type='reupload'

@pytest.mark.critical
@pytest.mark.integration
async def test_list_returns_ordered_desc(auth_client, admin_token, sample_docs, ...):
    """Scenario 2: 3 mutations → DESC order."""

@pytest.mark.critical
@pytest.mark.integration
async def test_restore_creates_new_version_append_only(auth_client, admin_token, sample_docs, ...):
    """Scenario 3: restore v1 → v_max+1 with change_type='restore', existing rows preserved."""

@pytest.mark.critical
@pytest.mark.integration
async def test_hub_admin_cross_hub_versions_403(auth_client, seed_hubs_dmd_tdt, ...):
    """Scenario 4: hub_admin dmd → document tdt → 403 HUB_ADMIN_REQUIRED."""

@pytest.mark.critical
@pytest.mark.integration
async def test_audit_forensic_chain(auth_client, admin_token, sample_docs, postgres_container, ...):
    """Scenario 5: query audit_logs.payload->>'actor_role' + 'document_id' + 'version_number' exact."""
```

### Plan 05-05 — Closeout 4 docs

1. **STATE.md frontmatter** — `phase_5_status: DONE` + `phase_5_done_date: 2026-05-XX` + `progress.completed_phases: 5` + `progress.completed_plans: 20` + `next_action: /gsd-complete-milestone v3.1 hoặc /gsd-new-milestone v4.0` + body Phase 5 Results Summary section.
2. **REQUIREMENTS.md** — APPEND mới section VER-01..05 với 5 dòng `- [x] **VER-XX** ... (DONE 2026-05-XX — Plan 05-XX)`. Total v1 Requirements grow 15 → 20 REQ-ID v3.1.
3. **ROADMAP.md** — Phase 5 row DONE + Plans checklist 5 plan mark `[x]` + milestone progress table v3.1 4 phase → 5 phase / 15 plan → 20 plan / 15 REQ → 20 REQ.
4. **CLAUDE.md §6** — APPEND subsection `### Phase 5 v3.1 Document version history pattern (VER-01..05 — 2026-05-26)` + bump trailing `*Cập nhật:` line reflect Phase 5 done.
5. **Git tag** — KHÔNG tạo tag mới (v3.1 đã tag 2026-05-24 carry forward, semver clean). Optional: `git tag -a v3.1.1 -m "v3.1.1 Phase 5 Document version history"` (operator decide — defer Claude's discretion).

</specifics>

<deferred>
## Deferred Ideas

- **Chunks per-version snapshot** — D-V3.1-Phase5-B LOCKED defer v4.0 cùng dedup strategy.
- **File binary content-hash dedupe cross-document** — Phase 5 chỉ trong cùng document_id; cross-document dedupe defer v4.0 cần file_store schema migration thêm reference_count.
- **Version diff UI side-by-side** — defer v4.0 frontend feature.
- **DELETE /api/documents/{id}/versions/{vid} endpoint** — ROADMAP VER-03 mention NHƯNG FE KHÔNG có delete UI; defer v4.0.
- **Retention policy configurable per-hub** — hardcode "3 gốc + 2 gần nhất" Phase 5; per-hub override defer v4.0 qua system_settings extend.
- **Restore re-extract async via cocoindex queue** — Phase 5 sync block endpoint < 5s small file; async defer v4.0 với Celery/RQ/Postgres LISTEN/NOTIFY.
- **Cross-hub version restore** — vi phạm D-V3-01 hub isolation; 403 reject hard.
- **HUMAN-UAT live runtime manual smoke** — automated 5 scenario đủ VER-05; manual defer ops handover (carry forward v3.0 + v3.1 closeout pattern).
- **OCR / scanned PDF version preservation** — D4 LOCKED carry forward M2; OCR Vietnamese defer v4.0.
- **Reviewed Todos (not folded)** — KHÔNG có pending todo cross-reference cho Phase 5 (gsd-sdk todo command KHÔNG available trong env hiện tại — SDK v0.1.0 mismatch với workflow expect).
- **v3.1.1 git tag annotated** — Plan 05-05 default KHÔNG tag mới (semver clean); operator quyết định qua `git tag -a v3.1.1` manual nếu cần.

</deferred>

---

*Phase: 05-document-version-history*
*Context gathered: 2026-05-26 via /gsd-discuss-phase 5 --auto (5 gray area ROADMAP GA-V3.1-D..H — 4 LOCKED theo recommendation + 1 deviation D-V3.1-Phase5-E retention enforce BE write-time per FE codebase audit override; 4 decision phụ D-V3.1-Phase5-F plan count + G migration name + H audit action + I reextract sync LOCKED)*
*Tool fallback note: gsd-sdk v0.1.0 trong env KHÔNG có `query` subcommand mà workflow expect (init.phase-op, commit, etc.); workflow chạy fallback manual mode — phase dir + CONTEXT.md + DISCUSSION-LOG.md write trực tiếp qua Write tool, commit qua Bash git commit. Plan-phase phải biết để cũng fallback manual.*
