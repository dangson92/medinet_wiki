---
phase: 04-cocoindex-flow-mvp-document-ingest
verified: 2026-05-14T17:30:00Z
status: gaps_found
score: 3/5 success criteria verified
must_haves_total: 5
must_haves_verified: 3
must_haves_failed: 2
re_verification:
  previous_status: null
  previous_score: null
  is_initial: true
gaps:
  - truth: "SC2 — Trong <5s sau upload, documents.status tự động pending → processing → completed; chunk_count > 0; chunks table có rows với hub_id đúng, vector dim=1536, content_hash BYTEA set"
    status: failed
    reason: |
      Cocoindex 1.0.3 flow KHÔNG thể ship rows vào pgvector vì kiến trúc dataclass
      ChunkRow.vector dùng Annotated[NDArray[np.float32], EMBEDDER] sai pattern —
      EMBEDDER là @coco.fn callable, KHÔNG phải VectorSpecProvider. Verified runtime:
      `await pg.TableSchema.from_class(ChunkRow, primary_key=['id'])` raise
      `ValueError: VectorSpecProvider is required for NumPy ndarray type`. Lifespan
      setup_cocoindex fail-soft → app.state.cocoindex_app = None. Kết quả:
      - Test E2E happy path (test_e2e_upload_docx_to_chunks_completed) SKIP với message
        "cocoindex_app KHÔNG setup được".
      - Trong production, BackgroundTask trigger_cocoindex_update sẽ skip với log
        "trigger_cocoindex_update_skip: cocoindex_app=None" → documents.status STUCK
        ở 'pending' forever; chunks table KHÔNG bao giờ có rows; chunk_count=0.
      Pipeline bị đứt ở mức ARCHITECTURAL — không phải bug nhỏ.
    artifacts:
      - path: Hub_All/api/app/rag/flow.py
        issue: |
          Line 132: `vector: Annotated[NDArray[np.float32], EMBEDDER]` — EMBEDDER
          (@coco.fn _embed_one) KHÔNG implement VectorSpecProvider protocol.
          Cocoindex 1.0.3 yêu cầu VectorSpecProvider implementation cho NDArray
          field annotation trong TableSchema.from_class.
      - path: Hub_All/api/tests/integration/test_ingest_e2e.py
        issue: |
          test_e2e_upload_docx_to_chunks_completed (line 178-228) + 
          test_e2e_content_hash_incremental_dedup (line 308-355) cả 2 SKIP với 
          message "cocoindex_app KHÔNG setup được" — verified pass theo testcontainer
          run, nhưng goal là PASS chứ không phải SKIP.
    missing:
      - "Sửa flow.py vector field annotation: dùng cocoindex.vector_spec.VectorSpec hoặc Annotated[Vector[Float32, Literal[1536]], cocoindex.VectorIndex(metric=...)] pattern thay Annotated[NDArray, EMBEDDER]."
      - "Tạo VectorSpecProvider class implement protocol cocoindex 1.0.3 yêu cầu cho NumPy ndarray, ép kiểu Postgres vector(1536) đúng."
      - "Re-run test_e2e_upload_docx_to_chunks_completed và test_e2e_content_hash_incremental_dedup với cocoindex_app real để PASS thay vì SKIP."
      - "Verify trong production env: docker compose up + uvicorn + curl POST /api/documents/upload → status pending → processing → completed (chunk_count > 0) trong <5s."
  - truth: "SC5 — Content-hash incremental: upload cùng file 2 lần → cocoindex memo via stable_chunk_id deterministic uuid5 → KHÔNG re-insert duplicate chunks"
    status: failed
    reason: |
      Cùng root-cause với SC2 — cocoindex flow không chạy được vì VectorSpecProvider
      issue. test_e2e_content_hash_incremental_dedup SKIP với cùng message
      "cocoindex_app KHÔNG setup được". Stable_chunk_id helper (uuid5) đã verify
      deterministic qua unit test (test_stable_chunk_id_deterministic PASS), NHƯNG
      end-to-end verification (cocoindex memo cache hit + KHÔNG re-insert) KHÔNG
      thể chạy vì flow architecturally broken ở schema build.
    artifacts:
      - path: Hub_All/api/app/rag/flow.py
        issue: "Cùng issue VectorSpecProvider — flow KHÔNG ship rows được."
      - path: Hub_All/api/tests/integration/test_ingest_e2e.py
        issue: "test_e2e_content_hash_incremental_dedup SKIP — KHÔNG verify được dedup behavior end-to-end."
    missing:
      - "Sau khi fix VectorSpecProvider, re-run test_e2e_content_hash_incremental_dedup để verify upload cùng content 2 lần → chunks count tuyến tính KHÔNG duplicate."
overrides_applied: 0
human_verification:
  - test: "M2a EXIT GATE manual demo theo Hub_All/docs/m2a-exit-gate-demo.md"
    expected: |
      Operator chạy 5 bước paste-ready: docker compose up postgres redis → make migrate-up
      → uvicorn (lifespan auto setup cocoindex) → curl POST upload DOCX VN → psql verify
      chunks table có rows với hub_id đúng, vector dim=1536. AC1 + AC3 (HTTP 415 scanned PDF)
      có thể PASS vì router-level check; AC2 + AC5 sẽ fail nếu cocoindex_app=None do
      VectorSpecProvider bug — operator phải xác nhận observed behavior để gate decision.
    why_human: |
      Cần real Postgres + Redis + cocoindex env (Docker không lên trong verifier session).
      Manual demo là M2a EXIT GATE proxy — gating decision tiếp tục M2b. Plan 04-06 đã
      ship checkpoint:human-verify protocol auto-approved qua orchestrator --auto, nhưng
      acceptance criteria human-verify chỉ valid khi cocoindex_app real chạy được.
  - test: "Watchdog stress test (SC4) — kill cocoindex worker + đợi 5 phút"
    expected: |
      Manual stress: gửi 1 upload DOCX → đợi status='processing' → kill cocoindex worker
      thread (hoặc kill toàn bộ uvicorn process khi đang trong middle of update_blocking)
      → restart uvicorn → đợi 5 phút (Settings.watchdog_timeout_seconds=300) → SELECT
      documents WHERE id=:id → status='failed', error_message LIKE '%timeout%no heartbeat%'.
    why_human: |
      Test đã verify watchdog logic ở DB level (test_watchdog_flips_stuck_processing PASS,
      seed row stale 6min → flip 'failed'), NHƯNG behavior real-world requires cocoindex
      worker process control mà KHÔNG thể automate trong testcontainers env.
deferred:
  - truth: "Plan 04-07 fix VectorSpecProvider"
    addressed_in: "Plan 04-07 (chưa tồn tại) hoặc Phase 10 hardening"
    evidence: "Plan 04-06 SUMMARY documented: 'NOT a Plan 04-06 task scope: Đây là Plan 04-03 implementation defect... Defer: Plan 04-07 hoặc Phase 10 hardening' + 'Rule 4 architectural — KHÔNG fix trong Plan 04-06 scope'"
---

# Phase 4: CocoIndex Flow MVP + Document Ingest — Verification Report

**Phase Goal (ROADMAP.md line 140-168):** Admin có thể upload file (DOCX/TXT/MD/PDF text-only), cocoindex flow tự động pick up qua A4 BackgroundTasks (REVISION 2 — KHÔNG còn LISTEN/NOTIFY vì cocoindex 1.0.3 không hỗ trợ), extract → chunk tiếng Việt → embed (LiteLLM dim 1536) → pgvector; frontend poll status thấy `completed` với `chunk_count` đúng. **M2a EXIT GATE** — demo upload DOCX VN → SELECT verify chunks pgvector → user accept thì mới tiếp tục M2b.

**Verified:** 2026-05-14T17:30:00Z
**Status:** `gaps_found` (3/5 SC verified, 2 critical SC blocked bởi VectorSpecProvider architectural defect)
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths (5 ROADMAP Success Criteria)

| #   | Truth (Success Criterion)                                                                                              | Status      | Evidence                                                                                                                                                                                                                                                                                                                                          |
| --- | ---------------------------------------------------------------------------------------------------------------------- | ----------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| SC1 | POST /api/documents/upload (multipart, DOCX VN) → 202 + document_id + file lưu file_store/<uuid>.docx + INSERT documents status='pending' + last_heartbeat=NOW() bootstrap trong <500ms | ✓ VERIFIED  | `routers/documents.py` line 68-155 — POST /upload đầy đủ multipart + admin RBAC + Content-Length DoS guard + INSERT documents qua DocumentService.create (line 148-211 service). last_heartbeat=NOW() bootstrap line 161 SQL. Test `test_upload_happy_path` + `test_upload_creates_document_with_pending_status` (test_documents_upload.py) PASS in 20s. |
| SC2 | Trong <5s sau upload (A4 BackgroundTasks), `documents.status` tự động pending → processing → completed; chunk_count > 0; chunks table có rows với hub_id đúng, vector dim=1536, content_hash BYTEA set | ✗ FAILED    | **VectorSpecProvider blocker** — Probe runtime: `await pg.TableSchema.from_class(ChunkRow, primary_key=['id'])` raise `ValueError: VectorSpecProvider is required for NumPy ndarray type`. Lifespan setup_cocoindex fail-soft → `app.state.cocoindex_app=None` → BackgroundTask `trigger_cocoindex_update` skip → status STUCK 'pending' forever. test_e2e_upload_docx_to_chunks_completed SKIP. Pipeline architecturally broken ở schema build step. |
| SC3 | Upload scanned PDF VN → 415 envelope `{success:false, error:{code:"UNSUPPORTED_FORMAT", ...}}` + `documents.status='failed_unsupported'` (router-side synchronous early-detect) | ✓ VERIFIED  | `documents_service.py` line 90-147 — early-detect synchronous (BLOCKER #3 strategy A): nếu ext='.pdf' → `detect_scanned_pdf(saved_path)` sync → True → INSERT failed_unsupported + raise UnsupportedFormatError → router 415. test_e2e_pdf_scanned_failed_unsupported PASS in 10s (test_ingest_e2e.py). test_upload_rejects_scanned_pdf PASS (test_documents_upload.py). |
| SC4 | Watchdog test: kill cocoindex worker giữa flow → sau 5 phút (REVISION 2) status `processing → failed` với `error_message='timeout: no heartbeat for >300s'` | ✓ VERIFIED  | `services/watchdog.py` line 56-103 — watchdog_tick UPDATE query `WHERE status='processing' AND last_heartbeat IS NOT NULL AND last_heartbeat < NOW() - make_interval(secs => :timeout_secs)` (timeout=300 default). Settings.watchdog_timeout_seconds=300 verified. test_watchdog_flips_stuck_processing PASS (seed row stale 6min → flip 'failed'). test_watchdog_respects_5min_timeout PASS (boundary 3min KHÔNG flip + 6min flip). test_watchdog_skips_null_heartbeat_processing PASS (WARNING #7). Tất cả PASS in 9s. **Manual stress (kill worker thật) cần human verification.** |
| SC5 | Content-hash incremental: upload cùng file 2 lần → cocoindex memo via stable_chunk_id deterministic uuid5 → KHÔNG re-insert duplicate chunks | ✗ FAILED    | Cùng root-cause SC2 — cocoindex flow KHÔNG chạy được. stable_chunk_id helper deterministic verified ở unit level (test_stable_chunk_id_deterministic PASS — uuid5 same input → same UUID). NHƯNG end-to-end dedup behavior KHÔNG verify được vì test_e2e_content_hash_incremental_dedup SKIP do cocoindex_app=None. |

**Score:** 3/5 success criteria verified.

### Deferred Items

| # | Item | Addressed In | Evidence |
|---|------|-------------|----------|
| 1 | Fix `app/rag/flow.py` ChunkRow.vector annotation thành VectorSpecProvider pattern (cocoindex 1.0.3 actual API) | Plan 04-07 (chưa tồn tại) hoặc Phase 10 hardening | Plan 04-06 SUMMARY: "NOT a Plan 04-06 task scope: Đây là Plan 04-03 implementation defect... Defer: Plan 04-07 hoặc Phase 10 hardening". Rule 4 architectural escalation. |

**Lưu ý:** Item này về implementation defect Plan 04-03 — KHÔNG nằm trong scope Phase 4 nguyên gốc, nhưng cũng KHÔNG được explicit defer trong ROADMAP/Phase 5+. Đây là escalation gate gap thực sự — verifier giữ là **gap thật** (không phải deferred), vì SC2/SC5 ROADMAP là điều kiện M2a EXIT GATE.

---

### Required Artifacts

| Artifact                                                              | Expected                                          | Status     | Details                                                                                                                                                  |
| --------------------------------------------------------------------- | ------------------------------------------------- | ---------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `Hub_All/api/migrations/versions/0002_phase4_documents_indexes.py`    | Composite index ix_documents_status_last_heartbeat | ✓ VERIFIED | Tồn tại 1358 bytes. revision='0002', down_revision='0001'. test_phase4_migration_upgrade PASS — ORM mirror đã sửa drift (Plan 04-01 deviation 4). |
| `Hub_All/api/app/rag/flow.py`                                         | coco.App medinet_wiki_ingest + ChunkRow + 3 @coco.fn op + stable_chunk_id | ⚠️ STUB    | Tồn tại 10757 bytes. coco.App registered with name='medinet_wiki_ingest' (verified test_cocoindex_app_name_snake_case PASS). NHƯNG ChunkRow.vector annotation Annotated[NDArray[np.float32], EMBEDDER] FAIL ở runtime (VectorSpecProvider required). Code có nhưng KHÔNG functional. |
| `Hub_All/api/app/rag/setup.py`                                        | setup_cocoindex + get_cocoindex_app + stop_cocoindex | ✓ VERIFIED | Tồn tại 5313 bytes. setup_cocoindex chạy được tới `coco.start_blocking()` (verified probe). Nhưng `update_blocking()` fail vì pool key + schema build fail. |
| `Hub_All/api/app/services/file_extract.py`                            | extract_text + detect_scanned_pdf + ALLOWED_EXTENSIONS | ✓ VERIFIED | Tồn tại 7167 bytes. 10 unit test PASS (test_file_extract.py). detect_scanned_pdf public sync API (BLOCKER #3 prerequisite). |
| `Hub_All/api/app/services/vn_chunker.py`                              | chunk_vietnamese + ChunkDraft + HEADING_PATTERNS  | ✓ VERIFIED | Tồn tại 8350 bytes. 10 unit test PASS. _VN_CAPS regex cover full VN diacritics. |
| `Hub_All/api/app/services/embedder.py`                                | async embed_text + EMBEDDING_DIM=1536             | ✓ VERIFIED | Tồn tại 3597 bytes. 7 unit test PASS (mock litellm.aembedding dim=1536). |
| `Hub_All/api/app/services/file_store.py`                              | FileStore.save/load/delete UUID4                  | ✓ VERIFIED | Tồn tại 2375 bytes. 6 unit test PASS. UTF-8 VN filename + ext lowercase preserved. |
| `Hub_All/api/app/services/documents_service.py`                       | DocumentService.create/get/list/delete + trigger_cocoindex_update A4 | ✓ VERIFIED | Tồn tại 19523 bytes. trigger_cocoindex_update line 369-485 đầy đủ A4 (await asyncio.to_thread + count chunks + UPDATE status). last_heartbeat=NOW() bootstrap. NHƯNG defensive cocoindex_app=None case sẽ kích hoạt vì SC2 blocker. |
| `Hub_All/api/app/services/watchdog.py`                                | watchdog_tick + watchdog_loop + 5min NULL guard   | ✓ VERIFIED | Tồn tại 5345 bytes. NOT NULL guard line 89, make_interval bind param line 90. 6 unit test PASS. |
| `Hub_All/api/app/schemas/documents.py`                                | DocumentStatus Literal 5 giá trị + DocumentResponse + DocumentUploadResponse | ✓ VERIFIED | Tồn tại 1796 bytes. Status enum match Migration 0001 CHECK constraint. chunk_count field present. |
| `Hub_All/api/app/routers/documents.py`                                | APIRouter /api/documents POST /upload + GET /:id + DELETE /:id + GET list | ✓ VERIFIED | Tồn tại 10906 bytes. 4 endpoint mounted. background_tasks.add_task(trigger_cocoindex_update, ...) line 148 (A4 wire). require_role('admin') trên POST/DELETE. |
| `Hub_All/api/app/main.py`                                             | EXTEND lifespan setup_cocoindex + watchdog APPEND-ONLY | ✓ VERIFIED | setup_cocoindex qua asyncio.to_thread line 108. app.state.cocoindex_app=None default + try/except fail-soft (line 102-114). watchdog_task line 170. Cancel order watchdog → sqlalchemy → jwt → cocoindex (line 181-208). |
| `Hub_All/api/app/config.py`                                           | Settings.cocoindex_lmdb_path + watchdog_timeout_seconds | ✓ VERIFIED | get_settings().watchdog_timeout_seconds=300 verified runtime. cocoindex_lmdb_path field present. |
| `Hub_All/api/tests/unit/test_rag_flow.py`                             | 12 unit test cocoindex 1.0.3 API verify           | ✓ VERIFIED | 12/12 PASS in 8s. test_flow_no_deprecated_cocoindex_0x_api PASS (KHÔNG @flow_def, KHÔNG sources.Postgres). |
| `Hub_All/api/tests/integration/test_phase4_migration.py`              | 3 critical+integration test alembic upgrade + no-drift | ✓ VERIFIED | 3 test PASS — composite index `ix_documents_status_last_heartbeat` tồn tại + alembic check no-drift. |
| `Hub_All/api/tests/integration/test_documents_upload.py`              | 9 integration test với MockCocoindexApp fixture   | ✓ VERIFIED | 9/9 PASS — happy DOCX + 415 .exe + 415 scanned + 403 viewer + 401 missing auth + 400 invalid hub_id + 400 empty file + GET 404 + GET sau upload. |
| `Hub_All/api/tests/integration/test_documents_list_delete.py`         | 7 integration test list/delete/cascade/audit      | ✓ VERIFIED | 7/7 PASS — list empty + cap per_page=100 + filter hub_id + filter search + DELETE cascade + viewer 403 + DELETE 404. |
| `Hub_All/api/tests/integration/test_ingest_e2e.py`                    | 3 E2E test happy + scanned + dedup                | ⚠️ PARTIAL  | 1/3 PASS (test_e2e_pdf_scanned_failed_unsupported) + 2/3 SKIP (test_e2e_upload_docx_to_chunks_completed + test_e2e_content_hash_incremental_dedup) — VectorSpecProvider blocker. |
| `Hub_All/api/tests/unit/test_watchdog.py`                             | 6 unit test watchdog + NULL guard + 5min timeout  | ✓ VERIFIED | 6/6 PASS in 9s. test_watchdog_respects_5min_timeout (REVISION 2 NEW) verify boundary 3min vs 6min. |
| `Hub_All/docs/m2a-exit-gate-demo.md`                                  | Manual demo 5 bước Vietnamese                     | ✓ VERIFIED | Tồn tại 12346 bytes. 5 H2 sections: Tiền điều kiện + Bước 1-5 + Quyết định gate + Reference. AC1-5 mapping đầy đủ. |
| `Hub_All/api/scripts/m2a_demo.sh`                                     | Bash automation POLL_TIMEOUT 30s                  | ✓ VERIFIED | Tồn tại 5769 bytes, executable. 7 step automation + python3 inline JSON parser portable + M2A_DEMO_PASS marker. |

---

### Key Link Verification (Wiring)

| From                                            | To                                                  | Via                                                                                          | Status     | Details                                                                                                                                          |
| ----------------------------------------------- | --------------------------------------------------- | -------------------------------------------------------------------------------------------- | ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| `routers/documents.py` POST /upload             | `services/documents_service.py` DocumentService.create | `service.create(hub_id, uploaded_by, file_content, original_filename)`                       | ✓ WIRED    | Line 138-145 router. service.create raise UnsupportedFormatError → router catch (line 134-145) → 415 envelope.                                  |
| `routers/documents.py` POST /upload (sau OK)    | `services/documents_service.py` trigger_cocoindex_update via FastAPI BackgroundTasks | `background_tasks.add_task(trigger_cocoindex_update, request.app.state.cocoindex_app, doc_id)` | ✓ WIRED    | Line 148-152 router. KHÔNG còn pg_notify (A4). Plan 04-04 verified.                                                                              |
| `documents_service.py::create` (.pdf path)      | `file_extract.py::detect_scanned_pdf` (Plan 04-02 PUBLIC sync) | `is_scanned = detect_scanned_pdf(saved_path)` synchronous trước INSERT                       | ✓ WIRED    | Line 100-103. Defensive try/except cho pypdf parse fail. is_scanned=True → INSERT failed_unsupported + raise. BLOCKER #3 strategy A.            |
| `documents_service.py::trigger_cocoindex_update` | `cocoindex_app.update_blocking()` qua asyncio.to_thread | `await asyncio.to_thread(cocoindex_app.update_blocking)` (line 421) → SELECT COUNT chunks → UPDATE status | ⚠️ HOLLOW  | Code wired đúng pattern, NHƯNG cocoindex_app=None trong production (VectorSpecProvider) → defensive log "trigger_cocoindex_update_skip: cocoindex_app=None" line 397-399. KHÔNG ship chunks → status stuck pending.    |
| `main.py::lifespan`                             | `app/rag/setup.py::setup_cocoindex` (Plan 04-03)    | `await asyncio.to_thread(setup_cocoindex, settings)` → `app.state.cocoindex_app = get_cocoindex_app()` | ⚠️ PARTIAL | Code wired đúng (line 102-114), NHƯNG setup_cocoindex throw exception ở `update_blocking()` (VectorSpecProvider) → fail-soft → app.state.cocoindex_app=None.  |
| `main.py::lifespan`                             | `app/services/watchdog.py::watchdog_loop`           | `app.state.watchdog_task = asyncio.create_task(watchdog_loop())` APPEND-ONLY sau cocoindex setup | ✓ WIRED    | Line 170. Cancel TRƯỚC dispose_engine ở shutdown line 181-189.                                                                                  |
| `app/rag/flow.py`                               | `app/services/file_extract.py::extract_text`        | wrap qua flow logic (KHÔNG @coco.fn — direct call)                                           | ✓ WIRED    | Line 65 import + line 162 call. Plan 04-02 service expose extract_text(Path) → tuple[str, bool, dict].                                          |
| `app/rag/flow.py`                               | `app/services/vn_chunker.py::chunk_vietnamese`      | direct call trong index_document                                                             | ✓ WIRED    | Line 66 import + line 168 call.                                                                                                                  |
| `app/rag/flow.py`                               | `app/services/embedder.py::embed_text` (alias `aembedding_one`) | `aembedding_one = embed_text` alias + `_embed_one` @coco.fn wrap                            | ✓ WIRED    | Line 64 import as alias. _embed_one line 89-97 wraps. Plan 04-03 deviation Rule 1 documented.                                                    |
| `app/rag/flow.py::medinet_wiki_main`            | chunks table mount_table_target USER-managed (B1)   | `await pg.mount_table_target(PG_POOL_KEY, table_name='chunks', table_schema=ChunkRow_schema, managed_by=ManagedBy.USER)` | ✗ NOT_WIRED | Line 213-219 code present. NHƯNG `pg.TableSchema.from_class(ChunkRow)` line 212 FAIL với ValueError VectorSpecProvider — KHÔNG bao giờ reach mount_table_target ở runtime. |

---

### Data-Flow Trace (Level 4)

| Artifact                                       | Data Variable          | Source                                       | Produces Real Data | Status            |
| ---------------------------------------------- | ---------------------- | -------------------------------------------- | ------------------ | ----------------- |
| `routers/documents.py` POST /upload response   | `result.document_id`   | `service.create()` returns DocumentUploadResponse | ✓ Yes              | ✓ FLOWING         |
| `routers/documents.py` GET /:id response       | `doc.chunk_count`      | `SELECT chunk_count FROM documents WHERE id=:id` (line 215 service.get) | ⚠️ STATIC always 0 | ⚠️ HOLLOW         |
| `documents` table `status` column              | `'pending'` initial    | service.create INSERT line 158-162           | ✓ Yes              | ✓ FLOWING         |
| `documents` table `status` transition          | `'completed'`/`'failed'` | trigger_cocoindex_update UPDATE (line 438-477) | ✗ DISCONNECTED     | ✗ DISCONNECTED — cocoindex_app=None → defensive skip → status STUCK 'pending' (verified probe). |
| `chunks` table rows                            | N/A (data goal)        | cocoindex flow `table.declare_row(ChunkRow)` (flow.py line 192) | ✗ DISCONNECTED     | ✗ DISCONNECTED — flow KHÔNG ship rows vì VectorSpecProvider schema build fail. |

**Summary:** Upload path ships document row ('pending') correctly. Status transition + chunks generation BROKEN ở data-flow level. UI sẽ thấy status='pending' forever, chunk_count=0 forever.

---

### Behavioral Spot-Checks

| Behavior                                                    | Command                                                                                       | Result                                                                                                                | Status      |
| ----------------------------------------------------------- | --------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- | ----------- |
| Cocoindex App registered với name='medinet_wiki_ingest'     | `python -c "from app.rag.flow import cocoindex_app; print(cocoindex_app)"`                    | `<cocoindex._internal.app.App object>` + name='medinet_wiki_ingest'                                                   | ✓ PASS      |
| Settings.watchdog_timeout_seconds default 300               | `python -c "from app.config import get_settings; print(get_settings().watchdog_timeout_seconds)"` | `300` (REVISION 2 default 5 phút)                                                                                     | ✓ PASS      |
| Stable chunk_id deterministic (uuid5)                       | `test_stable_chunk_id_deterministic` (test_rag_flow.py)                                       | PASS — same (doc_id, chunk_index) → same UUID                                                                         | ✓ PASS      |
| ChunkRow schema build via cocoindex 1.0.3 TableSchema       | `await pg.TableSchema.from_class(ChunkRow, primary_key=['id'])`                               | `ValueError: VectorSpecProvider is required for NumPy ndarray type`                                                   | ✗ FAIL      |
| Cocoindex env start (start_blocking)                        | `coco.start_blocking()` after `flow.cocoindex_app` import                                     | OK exit 0                                                                                                             | ✓ PASS      |
| Cocoindex update_blocking() per-document                    | `flow.cocoindex_app.update_blocking()` (no DB)                                                 | `KeyError: 'medinet/pg_pool'` — context key not bound (lifespan fail thì pool không có)                              | ✗ FAIL      |
| Watchdog tick logic flips stale processing                  | test_watchdog_flips_stuck_processing (seed row stale 6min)                                    | PASS — flip 'failed' + error_message LIKE '%timeout%no heartbeat%'                                                    | ✓ PASS      |
| Watchdog NULL guard skip                                    | test_watchdog_skips_null_heartbeat_processing                                                 | PASS — last_heartbeat=NULL → KHÔNG flip                                                                               | ✓ PASS      |
| Forbidden cocoindex 0.x API mentions in source              | `grep -rn "cocoindex.sources.Postgres\|@cocoindex.flow_def\|FlowLiveUpdater\|VectorIndexDef\|cocoindex.init(\|cocoindex.setup_flow"` `app/` | 1 hit only — `app/rag/__init__.py` docstring stale comment "Plan 04-02 thêm flow.py — @cocoindex.flow_def medinet_wiki_ingest". KHÔNG functional impact (chỉ docstring), nhưng nên cleanup. | ⚠️ INFO     |

---

### Requirements Coverage

| Requirement | Source Plan | Description                                                                       | Status               | Evidence                                                                                                                                  |
| ----------- | ----------- | --------------------------------------------------------------------------------- | -------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| INGEST-01   | 04-03       | Cocoindex flow đăng ký với name medinet_wiki_ingest + Postgres source             | ⚠️ PARTIAL           | coco.App registered đúng tên. NHƯNG flow KHÔNG run được vì VectorSpecProvider schema build fail. Code có, behavior broken.                |
| INGEST-02   | 04-02, 04-03 | Flow transform extract → chunk VN → embed dim 1536                                | ✓ SATISFIED          | Services Plan 04-02 đầy đủ (33 unit test PASS). Wrap qua @coco.fn trong flow.py. Logic correct. NHƯNG flow chưa run được end-to-end.    |
| INGEST-03   | 04-03       | Target chunks table + stable chunk_id + content_hash                              | ⚠️ PARTIAL           | ChunkRow dataclass match Migration 0001 schema. mount_table_target USER-managed pattern correct. stable_chunk_id uuid5 verified. NHƯNG declare_row KHÔNG bao giờ chạy vì schema build fail. |
| INGEST-04   | 04-04       | POST /api/documents/upload multipart admin → 202 + INSERT pending                 | ✓ SATISFIED          | 9 integration test test_documents_upload.py PASS. Router + service + FileStore + Content-Length DoS guard + RBAC.                       |
| INGEST-05   | 04-04, 04-01 | GET /api/documents/:id → status enum 5 + chunk_count + heartbeat                  | ✓ SATISFIED (CONTRACT) | Endpoint + DocumentResponse schema 5 status enum verified. NHƯNG chunk_count luôn = 0 trong production vì cocoindex flow KHÔNG ship chunks. |
| INGEST-06   | 04-05, 04-01 | Heartbeat watchdog flip stuck processing                                          | ✓ SATISFIED          | watchdog_tick query + 5min timeout + NULL guard + Migration 0002 composite index. 6 unit test PASS.                                       |
| INGEST-07   | 04-05       | DELETE /api/documents/:id admin-only + cascade chunks + audit log                 | ✓ SATISFIED          | service.delete + INSERT audit_logs + FK CASCADE Phase 2 + best-effort unlink. 3 integration test PASS.                                    |
| INGEST-08   | 04-05       | GET list paginated + filter hub_id/status/uploaded_by/search + cap per_page=100   | ✓ SATISFIED          | service.list + router cap min(per_page, 100). 4 integration test PASS (cap + filter hub_id + search + empty).                            |

**Coverage:** 6/8 SATISFIED + 2/8 PARTIAL (cùng root cause VectorSpecProvider). KHÔNG có ORPHANED requirement.

---

### Anti-Patterns Found

| File                                | Line  | Pattern                                                                                          | Severity   | Impact                                                                                                                                         |
| ----------------------------------- | ----- | ------------------------------------------------------------------------------------------------ | ---------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| `app/rag/__init__.py`               | 7     | Docstring stale: "Plan 04-02 thêm flow.py — @cocoindex.flow_def medinet_wiki_ingest"             | ℹ️ Info     | Documentation drift — refer @cocoindex.flow_def (deprecated 0.x API). KHÔNG functional impact (docstring), nên cleanup.                       |
| `app/rag/flow.py`                   | 132   | `vector: Annotated[NDArray[np.float32], EMBEDDER]` — EMBEDDER là @coco.fn KHÔNG VectorSpecProvider | 🛑 Blocker | Cocoindex 1.0.3 schema build fail runtime → toàn bộ ingest pipeline broken (SC2 + SC5 fail).                                                  |
| `app/services/documents_service.py` | 397-399 | Defensive `cocoindex_app=None` skip path — log warning + KHÔNG retry                              | ⚠️ Warning  | Khi cocoindex_app=None (verified runtime), trigger_cocoindex_update silent skip → status STUCK pending. Defensive đúng nhưng masking root issue. |
| `app/main.py`                       | 113-114 | `except Exception as e: logger.warning("cocoindex_init_failed: %s", e)` fail-soft                | ⚠️ Warning  | Phase 1 fail-soft pattern đúng — KHÔNG crash uvicorn nếu cocoindex fail. Nhưng masking architectural blocker (VectorSpecProvider).            |
| `tests/integration/test_ingest_e2e.py` | 192-193, 321-322 | `pytest.skip("cocoindex_app KHÔNG setup được")` thay vì FAIL                                    | ⚠️ Warning  | Skip thay fail = ẩn architectural issue trong CI. SC2 + SC5 KHÔNG được verified end-to-end. Cần convert skip → fail sau khi fix VectorSpec.   |

---

### Human Verification Required

#### 1. M2a EXIT GATE Manual Demo (Acceptance Criterion 1-5)

**Test:** Chạy `Hub_All/docs/m2a-exit-gate-demo.md` 5 bước paste-ready trên dev machine với Docker stack thật.

**Steps (paste-ready):**

```bash
# Bước 1
cd Hub_All && docker compose up -d postgres redis
docker compose ps                              # 2 service healthy

# Bước 2
cd Hub_All/api && make migrate-up && make migrate-check

# Bước 3
docker compose up -d api                       # hoặc uv run uvicorn app.main:app --port 8080
# Đọc log: PHẢI có dòng `cocoindex_setup_ok` + `cocoindex_initial_backfill_complete`
# NẾU log có `cocoindex_init_failed: VectorSpecProvider is required for NumPy ndarray type`
# → SC2 + SC5 sẽ FAIL trong demo (root cause confirmed verifier session).

# Seed admin user (xem Bước 3 trong demo md)

# Bước 4 — Upload DOCX VN
ACCESS_TOKEN=$(curl -s -X POST http://localhost:8080/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@medinet.vn","password":"Admin@123"}' | jq -r '.data.access_token')
DOC_ID=$(curl -s -X POST http://localhost:8080/api/documents/upload \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -F "file=@khám-bệnh-mẫu.docx" \
  -F "hub_id=$HUB_ID" | jq -r '.data.document_id')

# Bước 5 — Poll status + verify chunks
for i in $(seq 1 30); do
  STATUS=$(curl -s http://localhost:8080/api/documents/$DOC_ID -H "Authorization: Bearer $ACCESS_TOKEN" | jq -r '.data.status')
  echo "Poll $i: status=$STATUS"
  [ "$STATUS" != "pending" ] && break
  sleep 1
done
docker exec -it medinet-postgres psql -U medinet -d medinet_central \
  -c "SELECT COUNT(*), MAX(vector_dims(vector)) AS dim, COUNT(content_hash) AS hash_set FROM chunks WHERE document_id='$DOC_ID'"
# Expected: COUNT > 0, dim=1536, hash_set > 0
```

**Expected outcome:**

- AC1 (SC1) PASS: 202 + document_id < 500ms ✓
- AC2 (SC2) **EXPECTED FAIL** trong env hiện tại: status STUCK pending vì cocoindex_app=None (VectorSpecProvider blocker confirmed runtime)
- AC3 (SC3) PASS: scanned PDF → 415 + failed_unsupported ✓
- AC4 (SC4) requires manual stress (kill worker + đợi 5 phút)
- AC5 (SC5) **EXPECTED FAIL** cùng root cause AC2

**Why human:** Cần real Postgres + Redis + cocoindex env (Docker không lên trong verifier session). Manual demo là M2a EXIT GATE proxy — gating decision tiếp tục M2b.

#### 2. Watchdog Stress Test (SC4)

**Test:** Manual stress test watchdog 5 phút timeout với cocoindex worker thật.

**Steps:**
1. Upload 1 DOCX VN (giả định đã fix VectorSpecProvider — nếu chưa fix thì test này KHÔNG meaningful).
2. Đợi status='processing'.
3. Kill toàn bộ uvicorn process khi đang trong middle of update_blocking.
4. Restart uvicorn (lifespan re-init nhưng KHÔNG re-trigger cocoindex cho doc_id cũ).
5. Đợi 5 phút (Settings.watchdog_timeout_seconds=300).
6. SELECT documents WHERE id=:id → status='failed', error_message LIKE '%timeout%no heartbeat%'.

**Expected:** Watchdog flip processing → failed sau timeout.

**Why human:** Test logic đã verify ở DB level (test_watchdog_flips_stuck_processing PASS), NHƯNG behavior real-world requires cocoindex worker process control mà KHÔNG thể automate trong testcontainers env.

---

### Gaps Summary

**Phase 4 status: GAPS_FOUND.**

1. **VectorSpecProvider architectural defect (Plan 04-03 carry-over)** — Chặn 2/5 ROADMAP success criteria (SC2 + SC5):
   - **Root cause:** `app/rag/flow.py` line 132 `vector: Annotated[NDArray[np.float32], EMBEDDER]` — EMBEDDER là @coco.fn callable KHÔNG implement VectorSpecProvider protocol mà cocoindex 1.0.3 yêu cầu cho NumPy ndarray field annotation.
   - **Verified runtime:** `await pg.TableSchema.from_class(ChunkRow, primary_key=['id'])` raise `ValueError: VectorSpecProvider is required for NumPy ndarray type`.
   - **Impact downstream:** Lifespan setup_cocoindex fail → `app.state.cocoindex_app=None` → BackgroundTask trigger_cocoindex_update silent skip → documents.status STUCK 'pending' forever → chunks table KHÔNG bao giờ có rows.
   - **Test impact:** test_e2e_upload_docx_to_chunks_completed + test_e2e_content_hash_incremental_dedup SKIP (KHÔNG verify được goal).

2. **M2a EXIT GATE goal "demo upload DOCX VN → SELECT verify chunks pgvector" KHÔNG verifiable end-to-end** — Plan 04-06 đã ship checkpoint:human-verify auto-approved qua orchestrator --auto, nhưng acceptance criteria human-verify chỉ valid khi cocoindex_app real chạy được. Manual demo sẽ confirm AC2 + AC5 fail.

3. **Plan 04-06 SUMMARY claim "Đây là Plan 04-03 implementation defect... Defer: Plan 04-07 hoặc Phase 10 hardening"** — Verifier đồng ý đây là defect Plan 04-03, NHƯNG **KHÔNG đồng ý** đây nên defer hoàn toàn vì:
   - SC2 + SC5 là điều kiện ROADMAP M2a EXIT GATE (gating decision tiếp tục M2b).
   - PROJECT.md R3 mitigation: "Reject demo → STOP M2b, KHÔNG pivot lần 3".
   - ROADMAP.md line 158: "🚦 **M2a EXIT GATE** giữa Phase 4 và 5 — demo upload DOCX VN → SELECT verify chunks pgvector → user accept thì mới tiếp tục M2b."
   - Phase 5 chưa có plan/scope cover VectorSpecProvider fix.

**Phase 4 đạt 6/8 INGEST requirements end-to-end + 3/5 ROADMAP SC verified** — đủ shippable cho watchdog/router/scanned-PDF pipeline (SC1, SC3, SC4), NHƯNG cocoindex chunk generation (SC2, SC5 — core ingest goal) FAIL kiến trúc.

### Recommended Next Steps

**Verifier verdict: gaps_found.**

1. **Tạo Plan 04-07 (BLOCKING — trước Phase 5+)** sửa VectorSpecProvider:
   - Reference cocoindex 1.0.3 actual API: `cocoindex.vector_spec.VectorSpec` hoặc `cocoindex.Vector[Float32, Literal[1536]]` annotation pattern thay `Annotated[NDArray, callable]`.
   - Re-run test_e2e_upload_docx_to_chunks_completed + test_e2e_content_hash_incremental_dedup PASS thay SKIP.
   - Manual demo M2a EXIT GATE pass AC2 + AC5 với cocoindex thật.
   - Convert pytest.skip → assert trong E2E test (CI gate enforce).

2. **Cleanup `app/rag/__init__.py` line 7 docstring** — xóa mention `@cocoindex.flow_def` (deprecated 0.x).

3. **M2a EXIT GATE gating decision** — Phase 5+ có thể kick-off PARALLEL với Plan 04-07 vì auth branch (Phase 5 HUB/USER CRUD) KHÔNG depend on cocoindex, NHƯNG Phase 6 (Search) blocked vì cần chunks pgvector data từ ingest pipeline. Recommend BLOCK Phase 6+ cho đến khi VectorSpecProvider fix.

---

_Verified: 2026-05-14T17:30:00Z_
_Verifier: Claude (gsd-verifier)_
