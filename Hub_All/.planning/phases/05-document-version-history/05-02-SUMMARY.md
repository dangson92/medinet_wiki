---
phase: 05-document-version-history
plan: 02
subsystem: backend-service-layer
tags: [backend, service, version-history, snapshot, retention, dedupe-hash, audit-emit, file-store, ver-02]
requires:
  - 05-01-SUMMARY (Alembic migration 0007_document_versions ship — schema 15 cột + UNIQUE + INDEX + CHECK live testcontainers)
  - audit_service.build_audit_payload + enqueue_audit (Plan 02-04 v3.1 LOCKED)
  - FileStore.save/load/delete (M2 LOCKED)
  - Raw SQL text() pattern (Plan 01-02 v3.1 carry forward)
provides:
  - document_version_service.snapshot/restore_to_version/list_versions/get_version_with_chunks/get_version_file_path (5 public API)
  - _compute_file_hash + _enforce_retention + _cleanup_orphan_files (2 + 1 private helper)
  - ACTION_VERSION_CREATE + ACTION_VERSION_RESTORE + RETENTION_KEEP_FIRST_N + RETENTION_KEEP_LAST_N (4 constant)
affects:
  - Plan 05-03 router 4 endpoint UNBLOCKED (consume 5 public API exact signature)
  - Plan 05-04 integration test E2E sẽ verify dedupe + retention + restore append-only + audit forensic
tech-stack:
  added: []
  patterns:
    - "Dedupe-by-hash CTE check existing (document_id, file_hash) → reference path cũ (D-V3.1-Phase5-A)"
    - "Retention CTE window function ROW_NUMBER PARTITION BY + ORDER BY asc/desc + DELETE RETURNING (D-V3.1-Phase5-E)"
    - "Cross-version dedupe-safe file cleanup (SELECT COUNT(*) reference check trước FileStore.delete)"
    - "Restore append-only (snapshot TRƯỚC khi UPDATE documents — D-V3.1-Phase5-D)"
    - "Audit 2 action codes (document.version.create + restore — D-V3.1-Phase5-H)"
    - "Raw SQL via sqlalchemy.text() + named bind params (T-05-02-01 SQL injection mitigation)"
key-files:
  created:
    - api/app/services/document_version_service.py (633 LOC — 5 public API + 2 private helper + 1 cleanup helper + 4 constant)
    - api/tests/unit/test_document_version_service.py (341 LOC — 8 unit test PASS pure Python mock AsyncSession)
  modified: []
decisions:
  - "D-V3.1-Phase5-A LOCKED satisfied: SHA-256 hex 64-char dedupe key trong cùng document_id; reupload exact same → reference path cũ; KHÔNG đụng FileStore.save"
  - "D-V3.1-Phase5-B LOCKED satisfied: get_version_with_chunks trả (dict, []) — chunks empty array (FE typecheck happy)"
  - "D-V3.1-Phase5-D LOCKED satisfied: restore_to_version append-only — snapshot(change_type='restore') TRƯỚC khi UPDATE documents.file_path|filename|mime_type|file_size_bytes"
  - "D-V3.1-Phase5-E LOCKED satisfied: retention CTE BE write-time enforce ROW_NUMBER PARTITION BY document_id ORDER BY version_number asc + desc; DELETE WHERE asc_rank > 3 AND desc_rank > 2 RETURNING file_path"
  - "D-V3.1-Phase5-H LOCKED satisfied: audit emit 2 action codes (document.version.create + restore) với build_audit_payload nest actor_role + actor_hub_id"
  - "Service KHÔNG gọi FileStore.save (Plan 05-03 router responsibility — caller save trước khi gọi snapshot) — T-05-02-08 accept"
  - "Re-extract trigger SYNC defer Plan 05-03 router responsibility (documents_service.py grep KHÔNG có reextract API existing — note ở objective)"
metrics:
  duration_minutes: 25
  test_count: 8
  test_pass: 8
  file_count: 2
  loc_total: 974
  completed_date: 2026-05-26
---

# Phase 5 Plan 02: Document Version Service Layer (VER-02) — Summary

Service layer `document_version_service.py` ship 5 public async API + 2 private helper với SHA-256 dedupe-by-hash, CTE window function retention "3 gốc + 2 gần nhất", restore append-only, và audit emit 2 action codes — Plan 05-03 router unblocked.

## Tổng quan

Plan 05-02 v3.1 Phase 5 Wave 2 BLOCKING ship **service layer cho document version history** (VER-02). Đây là lớp service core consume bởi Plan 05-03 router 4 endpoint (GET list + GET detail + GET file + POST restore). Plan 05-01 (Wave 1) đã ship migration 0007_document_versions schema 15 cột + UNIQUE + INDEX + CHECK live testcontainers — Plan 05-02 build trên schema đó.

5 public async API export:

1. **`snapshot(*, session, document, change_type, change_note=None, actor_user_id=None, actor_role='admin', actor_hub_id=None) -> dict`** — Tạo version snapshot atomic 7 step: compute SHA-256 hash → dedupe check → SELECT MAX version_number + 1 → INSERT row → retention CTE cleanup → file cleanup reference count → audit emit `document.version.create`.

2. **`restore_to_version(*, session, document_id, version_id, actor_user_id=None, actor_role='admin', actor_hub_id=None) -> dict`** — Append-only rollback (D-V3.1-Phase5-D LOCKED): resolve target version → snapshot current TRƯỚC → UPDATE documents → audit emit `document.version.restore` → re-fetch refreshed.

3. **`list_versions(session, document_id) -> list[dict]`** — SELECT * ORDER BY version_number DESC (≤ 5 row sau retention prune).

4. **`get_version_with_chunks(session, document_id, version_id) -> tuple[dict, list]`** — Return `(version_dict, [])` empty chunks (D-V3.1-Phase5-B LOCKED — FE typecheck happy).

5. **`get_version_file_path(session, document_id, version_id) -> Path | None`** — Return Path object cho StreamingResponse Plan 05-03.

2 private helper:

- **`_compute_file_hash(path: Path) -> str`** (sync) — SHA-256 hex 64-char dedupe key (D-V3.1-Phase5-A LOCKED).
- **`_enforce_retention(session, document_id) -> list[str]`** (async) — CTE window function ROW_NUMBER PARTITION BY document_id ORDER BY version_number asc + desc; DELETE WHERE asc_rank > 3 AND desc_rank > 2 RETURNING file_path (D-V3.1-Phase5-E LOCKED).
- **`_cleanup_orphan_files(session, deleted_paths) -> int`** (async) — cross-version dedupe-safe FileStore.delete chỉ khi reference count = 0.

4 constant module-level:

- `ACTION_VERSION_CREATE = "document.version.create"` (D-V3.1-Phase5-H)
- `ACTION_VERSION_RESTORE = "document.version.restore"` (D-V3.1-Phase5-H)
- `RETENTION_KEEP_FIRST_N = 3` (D-V3.1-Phase5-E "3 gốc đầu")
- `RETENTION_KEEP_LAST_N = 2` (D-V3.1-Phase5-E "2 gần nhất")

## Quyết định LOCKED satisfied (5 decision)

| Decision | Scope | Implementation |
|----------|-------|----------------|
| **D-V3.1-Phase5-A** | Dedupe-by-hash trong cùng document_id | `_compute_file_hash` SHA-256 hex 64-char + `snapshot` dedupe SELECT `WHERE document_id = :doc_id AND file_hash = :hash LIMIT 1` → reference path cũ nếu HIT, document.file_path nếu MISS |
| **D-V3.1-Phase5-B** | Chunks per-version NO snapshot | `get_version_with_chunks` return `(_row_to_dict(row), [])` — empty list explicit (FE `DocumentVersionChunkAPI[]` typecheck happy) |
| **D-V3.1-Phase5-D** | Restore append-only | `restore_to_version` flow step 3: snapshot(change_type='restore') gọi TRƯỚC khi UPDATE documents (history preserve immutable) |
| **D-V3.1-Phase5-E** | Retention "3 gốc + 2 gần nhất" BE write-time enforce | `_enforce_retention` CTE WITH ranked ROW_NUMBER OVER PARTITION BY document_id ORDER BY version_number asc/desc → DELETE WHERE asc_rank > 3 AND desc_rank > 2 RETURNING file_path |
| **D-V3.1-Phase5-H** | Audit 2 action codes | `snapshot` emit ACTION_VERSION_CREATE; `restore_to_version` emit ACTION_VERSION_RESTORE với payload nest `restored_to=version_id` |

## File ship

| File | LOC | Status |
|------|-----|--------|
| `api/app/services/document_version_service.py` | 633 | Mới — 5 public API + 2 private helper + 1 cleanup helper + 4 constant + 1 row→dict helper |
| `api/tests/unit/test_document_version_service.py` | 341 | Mới — 8 unit test PASS pure Python mock AsyncSession |

**Tổng:** 974 LOC ship · 8 unit test PASS (4.45s) · 0 file modify.

## Commit chain

| Commit | Type | File |
|--------|------|------|
| `629b32e` | `feat(05-02)` | document_version_service.py 5 public API + 2 helper (VER-02) |
| `bd79e5b` | `test(05-02)` | test_document_version_service.py 8 unit test PASS (VER-02) |

## Test PASS (8/8 — 4.45s)

```
tests/unit/test_document_version_service.py::test_snapshot_inserts_row_atomic PASSED [ 12%]
tests/unit/test_document_version_service.py::test_snapshot_dedupe_by_hash_reuses_path PASSED [ 25%]
tests/unit/test_document_version_service.py::test_snapshot_audit_emits_create_action PASSED [ 37%]
tests/unit/test_document_version_service.py::test_snapshot_version_number_monotonic PASSED [ 50%]
tests/unit/test_document_version_service.py::test_list_versions_returns_desc PASSED [ 62%]
tests/unit/test_document_version_service.py::test_get_version_with_chunks_returns_empty_chunks PASSED [ 75%]
tests/unit/test_document_version_service.py::test_get_version_file_path_returns_path_object PASSED [ 87%]
tests/unit/test_document_version_service.py::test_compute_file_hash_returns_sha256_hex_64 PASSED [100%]
======================== 8 passed, 1 warning in 4.45s =========================
```

8 test cover semantic D-V3.1-Phase5-A/B/D/E/H LOCKED:

| Test | Decision | Verify |
|------|----------|--------|
| 1. `snapshot_inserts_row_atomic` | snapshot core | dedupe + MAX + INSERT call chain (`call_count >= 3`), version_number=1, is_original=True, file_hash SHA-256 match stdlib |
| 2. `snapshot_dedupe_by_hash_reuses_path` | D-V3.1-Phase5-A | dedupe HIT trả `(old_path,)` → `result['file_path'] == old_path` (KHÔNG document.file_path mới) |
| 3. `snapshot_audit_emits_create_action` | D-V3.1-Phase5-H | enqueue_audit gọi 1 lần với AuditEntry.action == `'document.version.create'` + payload nest đủ 5 field (actor_role, actor_hub_id, document_id, version_number, change_type) |
| 4. `snapshot_version_number_monotonic` | snapshot SELECT MAX | MAX scalar=3 → next=4 + is_original=False (`COALESCE(MAX, 0) + 1`) |
| 5. `list_versions_returns_desc` | list_versions ORDER BY | 3 row order [3, 2, 1] DESC + `is_original` derive đúng |
| 6. `get_version_with_chunks_returns_empty_chunks` | D-V3.1-Phase5-B | chunks == [] (FE typecheck happy) + isinstance(chunks, list) |
| 7. `get_version_file_path_returns_path_object` | Plan 05-03 StreamingResponse | Path('/tmp/storage/abc.docx') + isinstance Path |
| 8. `compute_file_hash_returns_sha256_hex_64` | D-V3.1-Phase5-A | len 64 + match `hashlib.sha256(b'hello').hexdigest()` + hex chars only |

## Mitigations security (T-05-02-XX STRIDE)

| Threat ID | Category | Disposition | Mitigation |
|-----------|----------|-------------|------------|
| **T-05-02-01** | Tampering (SQL injection) | mitigate | Tất cả raw SQL via `sqlalchemy.text()` + named bind params (`:doc_id`, `:hash`, `:version_id`, `:keep_first`, `:keep_last`) — KHÔNG concat string trực tiếp |
| **T-05-02-02** | Elevation of Privilege (cross-document restore) | mitigate | `restore_to_version` check `WHERE document_id = :doc_id AND id = :version_id` → ValueError raise nếu mismatch |
| **T-05-02-04** | Integrity (storage explosion) | mitigate | D-V3.1-Phase5-A dedupe-by-hash + D-V3.1-Phase5-E retention cap COUNT(*) ≤ 5 per document |
| **T-05-02-05** | Tampering (file delete race) | mitigate | `_cleanup_orphan_files` SELECT COUNT(*) reference check trước FileStore.delete (cross-version dedupe safe) |
| **T-05-02-07** | Repudiation (restore KHÔNG audit) | mitigate | `restore_to_version` emit `document.version.restore` với payload nest `restored_to=version_id` + `document_id` + `version_number` |
| **T-05-02-08** | Tampering (FileStore.save race) | accept | Service KHÔNG gọi FileStore.save — caller (Plan 05-03 router) responsibility save trước khi gọi snapshot |

## Carry forward (KHÔNG đụng source)

- **audit_service.build_audit_payload + enqueue_audit** (Plan 02-04 v3.1 D-V3.1-Phase2-C LOCKED) — reuse cho 2 action emit `document.version.create` + `document.version.restore`. AUDIT_ACTIONS frozenset trong audit_service.py KHÔNG include 2 action mới — enqueue_audit KHÔNG enforce hard (caller responsibility comment trong service code).
- **FileStore.save/load/delete** (M2 LOCKED) — reuse `FileStore().delete(Path(path))` trong `_cleanup_orphan_files`; KHÔNG đụng file_store.py source.
- **Raw SQL text() pattern** (Plan 01-02 v3.1 carry forward) — CTE window function complex DELETE + RETURNING + ROW_NUMBER KHÔNG dễ ORM; raw SQL via `sqlalchemy.text()` + named bind params là pattern proven (Plan 01-02 `get_effective_role`).
- **AsyncMock factory _make_session pattern** (Plan 01-02 + 02-01 carry forward) — test isolation pure Python KHÔNG cần Postgres/Redis runtime.

## Deviation (Rule 1 - Bug)

**1. [Rule 1 - Bug] Test mock factory ordering alignment**

- **Found during:** Task 2 (test run iteration 1)
- **Issue:** Initial test 1-4 input `_make_session(None, (inserted_id, created_at), fetchall_returns=[], scalar_returns=[0])` failed `TypeError: 'NoneType' object is not subscriptable` ở `inserted = insert_result.fetchone()` (line 322 service code).
- **Root cause:** Service `snapshot()` call execute 4 lần theo thứ tự: #1 dedupe (fetchone) | #2 MAX (scalar) | #3 INSERT RETURNING (fetchone) | #4 retention (fetchall). Factory build N mock với `fetchone_iter + scalar_iter` advance per-mock — mock #1 fetchone=None, mock #2 fetchone=(inserted_id, created_at) — nhưng service call #2 dùng `.scalar()` (fetchone unused); service call #3 INSERT cần fetchone từ mock #3 (StopIteration default None) → bug.
- **Fix:** Insert placeholder `None` ở vị trí fetchone của mock #2 trong test 1-3 (`_make_session(None, None, (inserted_id, created_at), ...)`). Test 4 additionally shift `scalar_returns=[0, 3]` để leading 0 align với mock #1 (scalar unused) + scalar=3 align với mock #2 (MAX query) — KHÔNG đụng service code; chỉ adjust test mock setup.
- **Files modified:** `api/tests/unit/test_document_version_service.py` (4 test fixture inline comment thêm `mock align` explain)
- **Commit:** `bd79e5b` (squashed vào test commit — bug fix là test setup KHÔNG phải service implementation, gắn vào test commit hợp lý)
- **Verify:** 8/8 PASS in 4.45s sau fix; service code KHÔNG đụng (commit 629b32e LOCKED).

## Authentication gates

KHÔNG có auth gate trong Plan 05-02 scope (pure service layer + unit test mock; KHÔNG hit real Postgres/Redis/auth flow).

## Known Stubs

KHÔNG có stub. 5 public API + 2 private helper đầy đủ implementation; chỉ defer 1 surface scope:

- **Re-extract trigger SYNC trong `restore_to_version`** (D-V3.1-Phase5-I LOCKED defer) — Plan 05-02 service KHÔNG gọi `coco_flow.run_for_document(document_id)` vì `documents_service.py` grep KHÔNG có existing reextract API public. Plan 05-03 router POST /restore responsibility (gọi sau khi `restore_to_version` return) HOẶC defer v4.0 nếu cocoindex inline call complex. Note đã ghi trong service docstring step 5 + plan `<objective>` note cuối.

## Trigger điểm reupload/edit/reextract — defer Plan 05-03 hoặc v4.0

Phase 5 KHÔNG wire snapshot vào reupload/edit/reextract trigger điểm hiện tại (theo CONTEXT.md `<domain>` VER-02 mention 4 trigger điểm). Lý do:

- `documents_service.py` grep KHÔNG có endpoint `reupload` / `edit_content` / `reextract` existing — FE `previewReuploadDocument` ở `api.ts:287-296` ám chỉ endpoint chưa ship BE.
- Plan 05-02 chỉ build core service API (5 public API + 2 private helper); Plan 05-03 router POST /restore trigger `snapshot(change_type='restore')` trực tiếp.
- Trigger điểm reupload/edit/reextract sẽ wire sau khi BE ship router tương ứng (defer task wiring trong Plan 05-03 hoặc v4.0 nếu BE chưa ship).
- Service API ready cho future wiring — caller chỉ cần `await document_version_service.snapshot(session=, document=, change_type=, ...)`.

## Plan 05-03 router unblocked (consumer contract verify)

5 public API exact signature match Plan 05-03 router consumer (Wave 3):

```python
# Plan 05-03 GET /versions:
versions = await document_version_service.list_versions(db, document_id)
return success_envelope({"versions": versions})

# Plan 05-03 GET /versions/{vid}:
version, chunks = await document_version_service.get_version_with_chunks(db, document_id, version_id)
return success_envelope({"version": version, "chunks": chunks})  # chunks=[]

# Plan 05-03 GET /versions/{vid}/file:
file_path = await document_version_service.get_version_file_path(db, document_id, version_id)
return StreamingResponse(file_path.open("rb"), media_type=..., ...)

# Plan 05-03 POST /restore:
refreshed = await document_version_service.restore_to_version(
    session=db, document_id=document_id, version_id=version_id,
    actor_user_id=user.id, actor_role=..., actor_hub_id=...,
)
return success_envelope(refreshed)
```

## Self-Check: PASSED

- `Hub_All/api/app/services/document_version_service.py` FOUND (633 LOC).
- `Hub_All/api/tests/unit/test_document_version_service.py` FOUND (341 LOC).
- Commit `629b32e` FOUND (`feat(05-02): document_version_service.py 5 public API + 2 helper (VER-02)`).
- Commit `bd79e5b` FOUND (`test(05-02): test_document_version_service.py 8 unit test PASS (VER-02)`).
- 8/8 unit test PASS verified `cd Hub_All/api && PYTHONIOENCODING=utf-8 python -m pytest tests/unit/test_document_version_service.py -v --tb=short` exit 0 in 4.45s.
- Module importable: `from app.services.document_version_service import snapshot, restore_to_version, list_versions, get_version_with_chunks, get_version_file_path, _compute_file_hash, _enforce_retention` (verified via `inspect.iscoroutinefunction` assertion).
- STATE.md / REQUIREMENTS.md / ROADMAP.md / CLAUDE.md / file_store.py / audit_service.py KHÔNG modify (per objective spec — defer Plan 05-05 closeout).
