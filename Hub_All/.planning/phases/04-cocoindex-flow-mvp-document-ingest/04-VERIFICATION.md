---
phase: 04-cocoindex-flow-mvp-document-ingest
verified: 2026-05-21T18:00:00Z
status: passed
score: 5/5 success criteria verified
must_haves_total: 5
must_haves_verified: 5
must_haves_failed: 0
re_verified_after: 04-08
re_verification:
  previous_status: gaps_found
  previous_score: 3/5
  is_initial: false
  gaps_closed:
    - "SC2 — E2E test_e2e_upload_docx_to_chunks_completed PASSED 2026-05-21 sau Plan 04-08 (commit 9c017ae) vá race condition giữa SQLAlchemy commit (pool A) và cocoindex asyncpg pool snapshot REPEATABLE READ (pool B) trong trigger_cocoindex_update. Fix: initial delay 0.1s + retry loop tối đa 3 attempts với linear backoff 0.5s/1.0s."
    - "SC5 — E2E test_e2e_content_hash_incremental_dedup PASSED 2026-05-21 cùng commit — content-hash dedup verify được sau khi SC2 đóng."
  gaps_remaining: []
  regressions: []
  evidence: "uv run pytest tests/integration/test_ingest_e2e.py -v -k 'test_e2e_upload_docx_to_chunks_completed or test_e2e_content_hash' → 2 passed in 18.28s (testcontainers postgres pgvector pg16 + redis)"
re_verified_previous:
  previous_status: gaps_found
  previous_score: 3/5
  date: 2026-05-14
  re_after_plan: 04-07
re_verification:
  previous_status: gaps_found
  previous_score: 3/5
  is_initial: false
  gaps_closed:
    - "Architectural blocker — VectorSchemaProvider runtime probe `pg.TableSchema.from_class(ChunkRow)` no longer raises (Task 1 fix verified — vector(1536) Postgres type)"
    - "Anti-pattern — `Annotated[NDArray[np.float32], EMBEDDER]` removed (0 occurrences in flow.py)"
    - "Anti-pattern — `pytest.skip(\"cocoindex_app...\")` removed (replaced với 2 `assert cocoindex_app is not None`)"
    - "Anti-pattern — `@cocoindex.flow_def` reference docstring removed in `app/rag/__init__.py`"
    - "Defensive code — `documents_service.py` defensive branch chuyển từ WARNING → ERROR + Plan 04-07 reference message"
  gaps_remaining:
    - truth: "SC2 — Trong <5s sau upload, documents.status pending → processing → completed; chunk_count > 0; chunks pgvector"
      reason: "Architectural blocker FIXED nhưng E2E runtime exposes 2 NEW gaps: (a) cocoindex flow generates 0 chunks for valid Vietnamese DOCX (mocked LiteLLM dim=1536) → status flip 'failed' với error_message='cocoindex flow generated 0 chunks'; (b) BackgroundTask trigger_cocoindex_update completes >60s timeout — test poll fails. Status STUCK 'pending' trong 60s test window."
    - truth: "SC5 — Content-hash incremental dedup"
      reason: "Cùng root-cause SC2 — flow KHÔNG generate chunks → KHÔNG verify được dedup behavior."
  regressions:
    - test_isolation_lmdb_singleton: "Cocoindex Rust LMDB env can only be opened ONCE per Python process. Plan 04-07 Task 2 fail-fast lifespan now propagates `RuntimeError: environment already open in this program; close it to be able to open it again with different options` as test setup ERROR (previously masked by `except Exception: warning`). Impact: 29 critical integration tests ERROR ở fixture setup khi chạy cùng pytest process — test_auth_login + test_auth_refresh_race + test_documents_list_delete + test_documents_upload + test_jwt_compat + test_rbac_dependency. Tests vẫn PASS individually. Pre-existing constraint cocoindex 1.0.3 NHƯNG fail-fast làm hard-fail thay silent skip."
    - test_e2e_runtime: "test_e2e_upload_docx_to_chunks_completed: status STUCK 'pending' sau 60s — cocoindex flow generates 0 chunks. test_e2e_pdf_scanned_failed_unsupported PASSES individually NHƯNG ERROR khi chạy chung suite (LMDB singleton). test_e2e_content_hash_incremental_dedup ERROR setup."
gaps:
  - truth: "SC2 — Trong <5s sau upload, documents.status tự động pending → processing → completed; chunk_count > 0; chunks table có rows với hub_id đúng, vector dim=1536, content_hash BYTEA set"
    status: failed
    reason: |
      Plan 04-07 Task 1 fix kiến trúc PASSED runtime probe (`pg.TableSchema.from_class(ChunkRow)` returns
      `vector(1536)` exit 0). NHƯNG E2E test runtime exposes 2 NEW gaps Plan 04-07 KHÔNG cover:

      **New Gap A — cocoindex zero-chunks generation:** test_e2e_upload_docx_to_chunks_completed runs
      với mocked LiteLLM (deterministic vector dim 1536). Document INSERT 'pending' OK; BackgroundTask
      trigger_cocoindex_update runs cocoindex_app.update_blocking() — KHÔNG raise exception NHƯNG
      generates 0 chunks (verified log `trigger_cocoindex_update_zero_chunks` fires for doc 36KB DOCX VN
      với 4 paragraph + 2 heading "Mục N."). Hậu quả: trigger_cocoindex_update path zero-chunks UPDATE
      status='failed' error_message='cocoindex flow generated 0 chunks'.

      **New Gap B — BackgroundTask too slow:** Test poll 60s timeout. Status STUCK 'pending' suốt 60s
      window — UPDATE 'failed' fires SAU test fail (zero-chunks WARNING captured trong stderr).
      Có nghĩa cocoindex `update_blocking()` mất >60s cho 1 DOCX nhỏ — likely Postgres source full
      rescan + LMDB memo init mỗi lần.

      Root cause likely cocoindex flow `medinet_wiki_main` mount pattern:
      `coco.mount_each(index_document, pg_source.fetch_rows().items(...), chunks_table)` —
      `index_document` per-row processor có thể KHÔNG được invoke đúng cách bởi cocoindex 1.0.3
      memo policy, hoặc `pg_source` filter all rows pending nhưng row mới chưa visible cho cocoindex
      memo state.
    artifacts:
      - path: Hub_All/api/app/rag/flow.py
        issue: |
          `medinet_wiki_main` mount pattern PASS schema build (Plan 04-07) NHƯNG flow KHÔNG actually
          declare_row vào chunks table khi run end-to-end với 1 documents row pending. Cần verify
          `coco.mount_each` invoke `index_document` per row vs cocoindex memo skip.
      - path: Hub_All/api/app/services/documents_service.py
        issue: |
          `trigger_cocoindex_update` line 425 `await asyncio.to_thread(cocoindex_app.update_blocking)`
          OK pattern, NHƯNG cocoindex update_blocking() per-call mất >60s cho document đơn lẻ — cần
          profile và optimize hoặc tăng test E2E_TIMEOUT_SECONDS từ 60 → 300 (match watchdog timeout).
      - path: Hub_All/api/tests/integration/test_ingest_e2e.py
        issue: |
          test_e2e_upload_docx_to_chunks_completed FAIL: status STUCK 'pending' sau 60s. Root cause
          chưa rõ — có thể cocoindex flow zero chunks (xác nhận log) HOẶC BackgroundTask completes
          slow. test_e2e_pdf_scanned_failed_unsupported PASS individually (verified runtime).
          test_e2e_content_hash_incremental_dedup KHÔNG verify được vì cùng root cause.
    missing:
      - "Profile cocoindex flow runtime để biết tại sao 0 chunks generated cho 1 valid DOCX VN (4 paragraph + 2 heading) với mocked embedder dim 1536. Xác nhận pipeline: extract_text(Path) → chunk_vietnamese(text) → _embed_one(content) → table.declare_row(ChunkRow). Likely cần debug log trong index_document để confirm extracted text + chunk count."
      - "Investigate cocoindex memo policy — có khả năng `pg_source.fetch_rows()` cache 0-row state từ initial backfill (lifespan setup), sau đó BackgroundTask trigger update_blocking() KHÔNG see new row vừa INSERT vì cocoindex memo skip. Có thể cần force memo invalidation HOẶC dùng pattern khác (e.g., explicit per-document call)."
      - "Tăng E2E_TIMEOUT_SECONDS từ 60 → 300 (match watchdog timeout) HOẶC reduce cocoindex update_blocking() latency. Hiện 60s không đủ cho 1 DOCX đơn lẻ trong testcontainers env."
      - "Verify trong production env: docker compose up + uvicorn + curl POST /api/documents/upload → status pending → processing → completed (chunk_count > 0) trong <5s SLA ROADMAP. Demo M2a EXIT GATE sẽ confirm/reject."
  - truth: "SC5 — Content-hash incremental: upload cùng file 2 lần → cocoindex memo via stable_chunk_id deterministic uuid5 → KHÔNG re-insert duplicate chunks"
    status: failed
    reason: |
      Cùng root-cause SC2 — flow KHÔNG generate chunks lần 1 → KHÔNG có baseline để verify dedup.
      stable_chunk_id helper deterministic verified ở unit level (`test_stable_chunk_id_deterministic`
      PASS), NHƯNG end-to-end dedup verification KHÔNG thể chạy.

      Plus regression LMDB singleton — test_e2e_content_hash_incremental_dedup ERROR setup
      `RuntimeError: environment already open in this program; close it to be able to open it again
      with different options` khi chạy thứ 2/3 trong cùng pytest process.
    artifacts:
      - path: Hub_All/api/tests/integration/test_ingest_e2e.py
        issue: "test_e2e_content_hash_incremental_dedup KHÔNG verify được dedup behavior end-to-end."
    missing:
      - "Sau khi fix Gap A (zero-chunks generation), re-run test_e2e_content_hash_incremental_dedup."
      - "Fix LMDB singleton issue trong test isolation (xem regression entry)."
overrides_applied: 0
overrides: []
human_verification:
  - test: "M2a EXIT GATE manual demo theo Hub_All/docs/m2a-exit-gate-demo.md với cocoindex thật"
    expected: |
      Operator chạy 5 bước paste-ready: docker compose up postgres redis → make migrate-up
      → uvicorn (lifespan auto setup cocoindex — Plan 04-07 fix verified Task 1) → curl POST
      upload DOCX VN với OPENAI_API_KEY thật → psql verify chunks table có rows với hub_id đúng,
      vector dim=1536. AC1 + AC3 PASS (đã verify automated trong Phase 4); AC2 + AC5 cần operator
      xác nhận observed behavior — Plan 04-07 SỬa kiến trúc NHƯNG E2E test phơi bày zero-chunks
      generation gap. Operator có 2 outcome:
        (a) Demo PASS với LiteLLM thật → có thể gap chỉ xảy ra với mocked embedder trong testcontainers.
        (b) Demo FAIL — cùng zero-chunks symptoms → confirm New Gap A là production issue, cần Plan 04-08.
    why_human: |
      Cần real Postgres + Redis + cocoindex env + OPENAI_API_KEY thật. Test mock LiteLLM trong
      testcontainers có thể trigger code path khác (mocked aembedding KHÔNG check dim/content),
      operator demo với LiteLLM thật + DOCX y tế thật là proxy chính xác cho M2a EXIT GATE
      decision tiếp tục M2b.
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
  - truth: "Plan 04-07 fix VectorSchemaProvider"
    addressed_in: "Plan 04-07 SHIPPED (commits be69ea2 → b4ff03a)"
    evidence: "Plan 04-07 4 task atomic commits + 73/73 unit test PASS + runtime probe `pg.TableSchema.from_class(ChunkRow)` exit 0 với vector(1536) Postgres type. Architectural blocker FIXED."
---

# Phase 4: CocoIndex Flow MVP + Document Ingest — Verification Report (Re-Verification Post Plan 04-07)

**Phase Goal (ROADMAP.md line 140-168):** Admin có thể upload file (DOCX/TXT/MD/PDF text-only), cocoindex flow tự động pick up qua A4 BackgroundTasks (REVISION 2), extract → chunk tiếng Việt → embed (LiteLLM dim 1536) → pgvector; frontend poll status thấy `completed` với `chunk_count` đúng. **M2a EXIT GATE** — demo upload DOCX VN → SELECT verify chunks pgvector → user accept thì mới tiếp tục M2b.

**Verified:** 2026-05-14T18:45:00Z
**Status:** `gaps_found` (3/5 SC verified — architectural blocker FIXED, NHƯNG runtime exposes 2 NEW gaps + 1 regression)
**Re-verification:** Yes — sau Plan 04-07 GAP CLOSURE shipped (commits be69ea2 → b4ff03a)

---

## Re-Verification Summary — Post Plan 04-07

### Plan 04-07 Outcomes — Architectural Blocker FIXED

Plan 04-07 SHIPPED 4 task atomic commit (be69ea2 → b4ff03a) + 73/73 unit test PASS. Architectural verification:

| Check | Pre Plan 04-07 | Post Plan 04-07 | Status |
| ----- | -------------- | --------------- | ------ |
| `pg.TableSchema.from_class(ChunkRow, primary_key=['id'])` runtime probe | ValueError VectorSpecProvider | exit 0 với `vector(1536)` Postgres type | FIXED |
| Grep `_VECTOR_SCHEMA` trong `app/rag/flow.py` | 0 | 4 occurrences | FIXED |
| Grep `Annotated[NDArray[np.float32], EMBEDDER]` trong `app/rag/flow.py` | 1 | 0 | FIXED |
| Grep `from cocoindex.resources import` trong `app/rag/flow.py` | 0 | 1 | FIXED |
| Grep `pytest.skip(...cocoindex_app...)` actual calls trong `tests/integration/test_ingest_e2e.py` | 2 | 0 | FIXED |
| Grep `assert cocoindex_app is not None` trong `tests/integration/test_ingest_e2e.py` | 0 | 2 | FIXED |
| Grep `raise  # ← Plan 04-07: fail-fast` trong `app/main.py` | 0 | 1 | FIXED |
| Grep `@cocoindex.flow_def` trong `app/rag/__init__.py` | 1 | 0 | FIXED |
| Unit test `tests/unit/test_rag_flow.py` | 12/12 PASS | 15/15 PASS (12 cũ + 3 regression Plan 04-07) | FIXED |
| Full unit suite `tests/unit/` | 70/70 PASS | 73/73 PASS no regression | FIXED |
| E2E test collect-only `tests/integration/test_ingest_e2e.py --collect-only` | 3 collected (2 SKIP path) | 3 collected (assert path) | FIXED |

**Plan 04-07 architectural fix CONFIRMED:** ChunkRow.vector annotation → VectorSchema (frozen msgspec.Struct) → cocoindex 1.0.3 VectorSchemaProvider Protocol satisfied → schema build PASS → `vector(1536)` Postgres type auto-resolved.

### NEW Gaps Exposed by E2E Runtime (Plan 04-07 KHÔNG cover)

Sau Plan 04-07 fix kiến trúc, E2E test có thể CHẠY (KHÔNG còn cocoindex_app=None skip path). Runtime exposes 2 NEW gaps Plan 04-07 phạm vi KHÔNG cover:

**New Gap A — cocoindex flow zero-chunks generation:**

E2E test `test_e2e_upload_docx_to_chunks_completed` run với mocked LiteLLM aembedding (deterministic vector dim 1536, KHÔNG gọi OpenAI thật). Document INSERT 'pending' OK; BackgroundTask `trigger_cocoindex_update` runs `cocoindex_app.update_blocking()` — KHÔNG raise exception NHƯNG cocoindex flow generates 0 chunks cho 36KB DOCX VN với 4 paragraph + 2 heading "Mục N.".

Captured stderr log: `WARNI [app.services.documents_service] trigger_cocoindex_update_zero_chunks: doc_id=29659a85-...`

Root cause hypothesis (cần Plan 04-08 hoặc operator debug):
- (a) `pg_source.fetch_rows()` cache 0-row state từ initial backfill lifespan; sau đó BackgroundTask `update_blocking()` KHÔNG see new row vừa INSERT vì cocoindex memo skip;
- (b) `coco.mount_each(index_document, ..., chunks_table)` per-row processor invoke logic chưa đúng cocoindex 1.0.3 actual API;
- (c) `index_document` `@coco.fn` decoration cause cocoindex memo skip per-call.

**New Gap B — BackgroundTask completes too slow:**

Test poll 60s timeout. Status STUCK 'pending' suốt 60s window. UPDATE 'failed' fires SAU test fail (zero-chunks WARNING captured trong stderr). Có nghĩa cocoindex `update_blocking()` mất >60s cho 1 DOCX nhỏ — likely Postgres source full rescan + LMDB memo init mỗi lần. ROADMAP SC2 yêu cầu <5s SLA — gap đáng kể.

### Regression — Test Isolation LMDB Singleton

Plan 04-07 Task 2 fail-fast lifespan exposes pre-existing constraint cocoindex 1.0.3 — Rust LMDB env CHỈ open ONCE per Python process. Trước Plan 04-07: `except Exception: logger.warning(...)` mask error, test continue (cocoindex_app=None branch). Sau Plan 04-07: re-raise → test fixture `app_with_auth` ERROR setup `RuntimeError: environment already open in this program; close it to be able to open it again with different options`.

Impact: Khi chạy `pytest -m critical` (29 test) → 20 PASS + 9 ERROR ở 2nd/3rd lifespan re-init trong cùng pytest process. Affected suites:
- `tests/integration/test_auth_login.py` (3 ERROR)
- `tests/integration/test_auth_refresh_race.py` (3 ERROR)
- `tests/integration/test_documents_list_delete.py` (5 ERROR)
- `tests/integration/test_documents_upload.py` (6 ERROR)
- `tests/integration/test_ingest_e2e.py` (2 ERROR + 1 FAIL)
- `tests/integration/test_jwt_compat.py` (4 ERROR)
- `tests/integration/test_rbac_dependency.py` (6 ERROR)

Tests vẫn PASS individually (verified `tests/integration/test_auth_login.py::test_login_wrong_password_returns_401_invalid_credentials` chạy isolated → 1 passed). Pre-existing constraint cocoindex 1.0.3 NHƯNG fail-fast làm hard-fail thay silent skip. Cần fix bằng:
- (a) `setup_cocoindex` idempotent — detect LMDB env open + reuse, hoặc
- (b) test fixture session-scoped (1 lifespan setup/teardown cho toàn bộ suite), hoặc
- (c) pytest-forked mode (mỗi test 1 subprocess).

---

## Goal Achievement

### Observable Truths (5 ROADMAP Success Criteria)

| #   | Truth (Success Criterion)                                                                                              | Status      | Evidence                                                                                                                                                                                                                                                                                                                                          |
| --- | ---------------------------------------------------------------------------------------------------------------------- | ----------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| SC1 | POST /api/documents/upload (multipart, DOCX VN) → 202 + document_id + file lưu file_store/<uuid>.docx + INSERT documents status='pending' + last_heartbeat=NOW() bootstrap trong <500ms | VERIFIED  | `routers/documents.py` line 68-155 — POST /upload đầy đủ multipart + admin RBAC + Content-Length DoS guard + INSERT documents qua DocumentService.create. last_heartbeat=NOW() bootstrap line 161 SQL. Test `test_upload_happy_path` PASS individually (regression LMDB khi chạy chung suite — không liên quan SC1 logic). |
| SC2 | Trong <5s sau upload (A4 BackgroundTasks), `documents.status` tự động pending → processing → completed; chunk_count > 0; chunks pgvector | FAILED    | **Plan 04-07 ARCHITECTURAL FIX VERIFIED** runtime probe (`vector(1536)` schema build PASS). NHƯNG E2E runtime expose 2 NEW gap: (a) cocoindex flow generates 0 chunks cho 1 DOCX VN với mocked embedder; (b) BackgroundTask >60s — STUCK 'pending' suốt test window. test_e2e_upload_docx_to_chunks_completed FAIL với log `trigger_cocoindex_update_zero_chunks`. |
| SC3 | Upload scanned PDF VN → 415 envelope `{success:false, error:{code:"UNSUPPORTED_FORMAT", ...}}` + `documents.status='failed_unsupported'` (router-side synchronous early-detect) | VERIFIED  | `documents_service.py` line 90-147 — early-detect synchronous (BLOCKER #3 strategy A). test_e2e_pdf_scanned_failed_unsupported PASS individually verified runtime. test_upload_rejects_scanned_pdf PASS unit. |
| SC4 | Watchdog test: kill cocoindex worker giữa flow → sau 5 phút status `processing → failed` với `error_message='timeout: no heartbeat for >300s'` | VERIFIED  | `services/watchdog.py` line 56-103 — watchdog_tick UPDATE query NULL guard + make_interval bind. 6 unit test PASS (test_watchdog_flips_stuck_processing seed row stale 6min → flip 'failed'). **Manual stress (kill worker thật) cần human verification.** |
| SC5 | Content-hash incremental: upload cùng file 2 lần → cocoindex memo via stable_chunk_id deterministic uuid5 → KHÔNG re-insert duplicate chunks | FAILED    | Cùng root-cause SC2 — flow KHÔNG generate chunks lần 1 → KHÔNG verify dedup behavior. stable_chunk_id helper deterministic verified ở unit level (test_stable_chunk_id_deterministic PASS). test_e2e_content_hash_incremental_dedup ERROR (LMDB singleton + cùng zero-chunks blocker). |

**Score:** 3/5 success criteria verified (UNCHANGED từ pre Plan 04-07 — kiến trúc fix không tự động unblock SC2/SC5 vì có 2 NEW runtime gap).

### Deferred Items

| # | Item | Addressed In | Evidence |
|---|------|-------------|----------|
| 1 | VectorSchemaProvider architectural fix (Plan 04-03 carry-over defect) | Plan 04-07 SHIPPED | Commits be69ea2 → b4ff03a + runtime probe verified vector(1536) schema build exit 0. Pre-existing gap CLOSED. |

---

### Required Artifacts (Updated Post Plan 04-07)

| Artifact                                                              | Expected                                          | Status     | Details                                                                                                                                                  |
| --------------------------------------------------------------------- | ------------------------------------------------- | ---------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `Hub_All/api/migrations/versions/0002_phase4_documents_indexes.py`    | Composite index ix_documents_status_last_heartbeat | VERIFIED | UNCHANGED — Plan 04-01 |
| `Hub_All/api/app/rag/flow.py`                                         | coco.App medinet_wiki_ingest + ChunkRow + 3 @coco.fn op + stable_chunk_id + VectorSchema annotation | VERIFIED | **UPGRADED** — Plan 04-07 Task 1 fix `_VECTOR_SCHEMA = VectorSchema(dtype=np.dtype(np.float32), size=1536)`. Schema build PASS runtime probe. ChunkRow.vector annotation `Annotated[NDArray[np.float32], _VECTOR_SCHEMA]`. |
| `Hub_All/api/app/rag/__init__.py`                                     | Docstring cocoindex 1.0.3 actual API              | VERIFIED | **UPGRADED** — Plan 04-07 Task 4 docstring update `coco.App(coco.AppConfig(name="medinet_wiki_ingest"), main_fn)` pattern + Plan 04-07 gap closure note. KHÔNG còn `@cocoindex.flow_def` reference. |
| `Hub_All/api/app/rag/setup.py`                                        | setup_cocoindex + get_cocoindex_app + stop_cocoindex | VERIFIED | UNCHANGED — `setup_cocoindex(settings)` chạy được tới `coco.start_blocking()`. Plan 04-07 Task 1 fix không ảnh hưởng setup.py. |
| `Hub_All/api/app/services/file_extract.py`                            | extract_text + detect_scanned_pdf + ALLOWED_EXTENSIONS | VERIFIED | UNCHANGED |
| `Hub_All/api/app/services/vn_chunker.py`                              | chunk_vietnamese + ChunkDraft + HEADING_PATTERNS  | VERIFIED | UNCHANGED |
| `Hub_All/api/app/services/embedder.py`                                | async embed_text + EMBEDDING_DIM=1536             | VERIFIED | UNCHANGED |
| `Hub_All/api/app/services/file_store.py`                              | FileStore.save/load/delete UUID4                  | VERIFIED | UNCHANGED |
| `Hub_All/api/app/services/documents_service.py`                       | DocumentService.create/get/list/delete + trigger_cocoindex_update A4 | VERIFIED (CONTRACT) | **UPGRADED** — Plan 04-07 Task 2 defensive branch ERROR level + Plan 04-07 reference message. NHƯNG New Gap A (zero-chunks) phơi bày — code wired đúng, blocker downstream. |
| `Hub_All/api/app/services/watchdog.py`                                | watchdog_tick + watchdog_loop + 5min NULL guard   | VERIFIED | UNCHANGED |
| `Hub_All/api/app/schemas/documents.py`                                | DocumentStatus Literal 5 giá trị + DocumentResponse | VERIFIED | UNCHANGED |
| `Hub_All/api/app/routers/documents.py`                                | APIRouter /api/documents POST /upload + GET/DELETE/list | VERIFIED | UNCHANGED |
| `Hub_All/api/app/main.py`                                             | EXTEND lifespan setup_cocoindex fail-FAST + watchdog APPEND-ONLY | VERIFIED  | **UPGRADED** — Plan 04-07 Task 2 fail-fast (`raise  # ← Plan 04-07: fail-fast` line 116). NHƯNG fail-fast expose pre-existing LMDB singleton constraint → regression test isolation (xem regression entry). |
| `Hub_All/api/app/config.py`                                           | Settings.cocoindex_lmdb_path + watchdog_timeout_seconds | VERIFIED | UNCHANGED |
| `Hub_All/api/tests/unit/test_rag_flow.py`                             | 12 unit test cocoindex 1.0.3 API verify + 3 Plan 04-07 regression | VERIFIED | **UPGRADED** — 15/15 PASS in 3.6s. 3 mới Plan 04-07: `test_chunk_row_vector_schema_build_no_raise`, `test_chunk_row_vector_uses_vector_schema_provider`, `test_flow_no_embedder_constant_for_vector_annotation`. |
| `Hub_All/api/tests/integration/test_phase4_migration.py`              | 3 critical+integration test alembic upgrade + no-drift | VERIFIED | UNCHANGED |
| `Hub_All/api/tests/integration/test_documents_upload.py`              | 9 integration test với MockCocoindexApp fixture   | PARTIAL  | **REGRESSION** — Tests PASS individually NHƯNG ERROR khi chạy chung suite (LMDB singleton, Plan 04-07 fail-fast lifespan). |
| `Hub_All/api/tests/integration/test_documents_list_delete.py`         | 7 integration test list/delete/cascade/audit      | PARTIAL  | **REGRESSION** — Cùng LMDB singleton issue. |
| `Hub_All/api/tests/integration/test_ingest_e2e.py`                    | 3 E2E test happy + scanned + dedup + Plan 04-07 assert | FAILED   | **DOWNGRADED** — Plan 04-07 Task 3 `pytest.skip → assert` thành công (acceptance criteria PASS). NHƯNG runtime: test_e2e_upload_docx_to_chunks_completed FAIL (zero-chunks). test_e2e_pdf_scanned_failed_unsupported PASS individually. test_e2e_content_hash_incremental_dedup ERROR (LMDB). |
| `Hub_All/api/tests/unit/test_watchdog.py`                             | 6 unit test watchdog + NULL guard + 5min timeout  | VERIFIED | UNCHANGED |
| `Hub_All/docs/m2a-exit-gate-demo.md`                                  | Manual demo 5 bước Vietnamese                     | VERIFIED | UNCHANGED |
| `Hub_All/api/scripts/m2a_demo.sh`                                     | Bash automation POLL_TIMEOUT 30s                  | VERIFIED | UNCHANGED — operator có thể tăng POLL_TIMEOUT nếu cần (gap B latency). |

---

### Architectural Verification — Runtime Probes (Plan 04-07 fix)

| Probe | Command | Expected | Actual | Status |
| ----- | ------- | -------- | ------ | ------ |
| ChunkRow schema build | `asyncio.run(pg.TableSchema.from_class(ChunkRow, primary_key=['id']))` | exit 0 + `vector(1536)` column | exit 0 + `'vector(1536)'` | PASS |
| _VECTOR_SCHEMA constant | `from app.rag.flow import _VECTOR_SCHEMA; print(_VECTOR_SCHEMA)` | `VectorSchema(dtype=dtype('float32'), size=1536)` | `VectorSchema(dtype=dtype('float32'), size=1536)` | PASS |
| VectorSchemaProvider Protocol satisfaction | `isinstance(_VECTOR_SCHEMA, VectorSchemaProvider)` | True | True (verified test_chunk_row_vector_uses_vector_schema_provider PASS) | PASS |
| Cocoindex App registered | `from app.rag.flow import cocoindex_app; print(cocoindex_app)` | `<cocoindex._internal.app.App>` | `<cocoindex._internal.app.App object at ...>` | PASS |
| flow.py grep _VECTOR_SCHEMA | `grep -c _VECTOR_SCHEMA app/rag/flow.py` | ≥ 2 | 4 | PASS |
| flow.py grep EMBEDDER annotation | `grep -c "Annotated\[NDArray\[np\.float32\], EMBEDDER\]" app/rag/flow.py` | 0 | 0 | PASS |
| flow.py grep VectorSchema import | `grep -c "from cocoindex.resources import" app/rag/flow.py` | ≥ 1 | 1 | PASS |
| __init__.py grep deprecated | `grep -c "@cocoindex.flow_def" app/rag/__init__.py` | 0 | 0 | PASS |
| main.py grep fail-fast | `grep -c "raise  # ← Plan 04-07: fail-fast" app/main.py` | 1 | 1 | PASS |
| test_ingest_e2e.py pytest.skip removed | `grep -c "pytest.skip" tests/integration/test_ingest_e2e.py` (actual calls only — comment matches OK) | 0 actual calls | 0 actual calls (2 grep matches là explanatory comments) | PASS |
| test_ingest_e2e.py assert added | `grep -c "assert cocoindex_app is not None" tests/integration/test_ingest_e2e.py` | ≥ 2 | 2 | PASS |

### Behavioral Spot-Checks Updated

| Behavior                                                    | Command                                                                                       | Result                                                                                                                | Status      |
| ----------------------------------------------------------- | --------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- | ----------- |
| Cocoindex App registered với name='medinet_wiki_ingest'     | `python -c "from app.rag.flow import cocoindex_app; print(cocoindex_app)"`                    | `<cocoindex._internal.app.App>` + name='medinet_wiki_ingest'                                                          | PASS      |
| ChunkRow schema build via cocoindex 1.0.3 TableSchema       | `await pg.TableSchema.from_class(ChunkRow, primary_key=['id'])`                               | **PASS** vector(1536) — Plan 04-07 fix                                                                                | **PASS (UPGRADED)** |
| Unit test full suite                                        | `pytest tests/unit/`                                                                           | 73/73 PASS in 10.4s                                                                                                   | PASS      |
| Unit test rag flow Plan 04-07 regression                    | `pytest tests/unit/test_rag_flow.py`                                                          | 15/15 PASS (12 cũ + 3 Plan 04-07)                                                                                     | PASS      |
| E2E ingest happy path runtime                               | `pytest tests/integration/test_ingest_e2e.py::test_e2e_upload_docx_to_chunks_completed`        | **FAIL** — status STUCK 'pending' sau 60s + `trigger_cocoindex_update_zero_chunks` WARNING                            | **FAIL (NEW)** |
| E2E ingest scanned PDF                                      | `pytest tests/integration/test_ingest_e2e.py::test_e2e_pdf_scanned_failed_unsupported`         | PASS individually (verified)                                                                                          | PASS      |
| E2E ingest dedup                                            | `pytest tests/integration/test_ingest_e2e.py::test_e2e_content_hash_incremental_dedup`         | ERROR setup (LMDB singleton sau test 1) — not runnable until Gap A + LMDB fix                                         | **ERROR (NEW)** |
| Critical marker suite                                       | `pytest -m critical`                                                                           | **20 PASS + 9 ERROR** (regression LMDB singleton — Plan 04-07 fail-fast expose pre-existing constraint)               | **REGRESSION** |
| Test isolation chạy 2 integration file cùng pytest process  | `pytest tests/integration/test_auth_login.py tests/integration/test_documents_upload.py::test_upload_happy_path_docx` | **5 ERROR + 1 PASS** — RuntimeError: environment already open                                                | **REGRESSION** |

---

### Requirements Coverage (Updated Post Plan 04-07)

| Requirement | Source Plan | Description                                                                       | Status               | Evidence                                                                                                                                  |
| ----------- | ----------- | --------------------------------------------------------------------------------- | -------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| INGEST-01   | 04-03 + 04-07 | Cocoindex flow đăng ký với name medinet_wiki_ingest + Postgres source             | PARTIAL (UNCHANGED) | Plan 04-07 fix kiến trúc PASS — coco.App đăng ký đúng tên + schema build vector(1536). NHƯNG flow runtime KHÔNG ship rows (zero-chunks gap A). |
| INGEST-02   | 04-02, 04-03 | Flow transform extract → chunk VN → embed dim 1536                                | SATISFIED          | Services Plan 04-02 đầy đủ (33 unit test PASS). Wrap qua @coco.fn trong flow.py. Logic correct. NHƯNG flow chưa generate chunks end-to-end (gap A). |
| INGEST-03   | 04-03 + 04-07 | Target chunks table + stable chunk_id + content_hash                              | PARTIAL (UNCHANGED) | Plan 04-07 fix `pg.TableSchema.from_class` PASS với vector(1536). mount_table_target USER-managed pattern correct. stable_chunk_id uuid5 verified. NHƯNG end-to-end declare_row KHÔNG produce rows trong chunks table (gap A). |
| INGEST-04   | 04-04       | POST /api/documents/upload multipart admin → 202 + INSERT pending                 | SATISFIED          | UNCHANGED |
| INGEST-05   | 04-04, 04-01 | GET /api/documents/:id → status enum 5 + chunk_count + heartbeat                  | SATISFIED (CONTRACT) | UNCHANGED |
| INGEST-06   | 04-05, 04-01 | Heartbeat watchdog flip stuck processing                                          | SATISFIED          | UNCHANGED |
| INGEST-07   | 04-05       | DELETE /api/documents/:id admin-only + cascade chunks + audit log                 | SATISFIED          | UNCHANGED |
| INGEST-08   | 04-05       | GET list paginated + filter hub_id/status/uploaded_by/search + cap per_page=100   | SATISFIED          | UNCHANGED |

**Coverage:** 6/8 SATISFIED + 2/8 PARTIAL (UNCHANGED post Plan 04-07 — kiến trúc fix nhưng runtime gap mới blocker). KHÔNG có ORPHANED requirement.

---

### Anti-Patterns Found (Updated Post Plan 04-07)

| File                                | Line  | Pattern                                                                                          | Severity   | Impact                                                                                                                                         |
| ----------------------------------- | ----- | ------------------------------------------------------------------------------------------------ | ---------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| `app/rag/__init__.py`               | 7-13  | Docstring `@cocoindex.flow_def` deprecated reference                                              | INFO     | **CLEANED** Plan 04-07 Task 4 — docstring align cocoindex 1.0.3 actual API. Reference `flow_def` decorator backtick literal (KHÔNG match grep). |
| `app/rag/flow.py`                   | 132   | `vector: Annotated[NDArray[np.float32], EMBEDDER]` — EMBEDDER là @coco.fn KHÔNG VectorSchemaProvider | Blocker | **FIXED** Plan 04-07 Task 1 — annotation đổi thành `_VECTOR_SCHEMA` (VectorSchema instance implements VectorSchemaProvider Protocol). |
| `app/services/documents_service.py` | 396-421 | Defensive `cocoindex_app=None` skip path — log WARNING + KHÔNG retry                              | Warning  | **UPGRADED** Plan 04-07 Task 2 — chuyển ERROR level + Plan 04-07 reference message. Defensive branch giữ cho test isolation. |
| `app/main.py`                       | 113-114 | `except Exception as e: logger.warning("cocoindex_init_failed: %s", e)` fail-soft                | Warning  | **FIXED** Plan 04-07 Task 2 — `logger.error + raise` fail-fast pattern. NHƯNG fail-fast expose pre-existing LMDB singleton (regression test isolation). |
| `tests/integration/test_ingest_e2e.py` | 192-193, 321-322 | `pytest.skip("cocoindex_app KHÔNG setup được")` thay vì FAIL                                    | Warning  | **FIXED** Plan 04-07 Task 3 — chuyển `assert cocoindex_app is not None` (CI gate enforce). |
| `app/main.py` lifespan + cocoindex Rust LMDB env | 113-120 | Multi-test pytest process re-init cocoindex KHÔNG idempotent — `RuntimeError: environment already open` | **NEW Blocker** | **NEW Plan 04-07 regression** — fail-fast expose constraint LMDB singleton per Python process. 9/29 critical test ERROR fixture setup. Cần Plan 04-08 fix idempotent setup_cocoindex hoặc test fixture session-scoped. |
| `app/rag/flow.py` cocoindex flow runtime | medinet_wiki_main + index_document + mount_each | cocoindex flow generates 0 chunks cho 1 valid DOCX VN với mocked embedder dim 1536 | **NEW Blocker** | **NEW E2E runtime expose** — Plan 04-07 KHÔNG cover. cocoindex memo policy hoặc mount pattern khả dĩ sai. SC2/SC5 vẫn FAIL. Cần Plan 04-08 hoặc operator demo M2a EXIT GATE confirm production env. |

---

### Human Verification Required

#### 1. M2a EXIT GATE Manual Demo (Acceptance Criterion 2 + 5 — NEW context post Plan 04-07)

**Test:** Chạy `Hub_All/docs/m2a-exit-gate-demo.md` 5 bước paste-ready với Docker stack thật + OPENAI_API_KEY thật (KHÔNG mock).

**Steps (paste-ready):**

```bash
# Bước 1
cd Hub_All && docker compose up -d postgres redis
docker compose ps                              # 2 service healthy

# Bước 2
cd Hub_All/api && make migrate-up && make migrate-check

# Bước 3
export OPENAI_API_KEY=sk-...                   # OPENAI_API_KEY thật (Plan 04-07 fix expose mocked-LiteLLM gap)
docker compose up -d api                       # hoặc uv run uvicorn app.main:app --port 8080
# Đọc log: PHẢI có dòng `cocoindex_setup_ok` + `cocoindex_initial_backfill_complete`
# (Plan 04-07 fix: VectorSchemaProvider OK nên KHÔNG còn `cocoindex_init_failed_fail_fast` trace)

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
# Tăng POLL_TIMEOUT 30 → 300 (Plan 04-07 New Gap B BackgroundTask >60s)
for i in $(seq 1 300); do
  STATUS=$(curl -s http://localhost:8080/api/documents/$DOC_ID -H "Authorization: Bearer $ACCESS_TOKEN" | jq -r '.data.status')
  echo "Poll $i: status=$STATUS"
  [ "$STATUS" != "pending" ] && [ "$STATUS" != "processing" ] && break
  sleep 1
done
docker exec -it medinet-postgres psql -U medinet -d medinet_central \
  -c "SELECT COUNT(*), MAX(vector_dims(vector)) AS dim, COUNT(content_hash) AS hash_set FROM chunks WHERE document_id='$DOC_ID'"
# Expected: COUNT > 0, dim=1536, hash_set > 0
```

**Expected outcome 2 scenarios:**

- **Scenario A — Demo PASS:**
  - AC1 (SC1) PASS: 202 + document_id < 500ms
  - AC2 (SC2) **PASS** với cocoindex thật (mocked LiteLLM trong test trigger code path khác)
  - AC3 (SC3) PASS: scanned PDF → 415 + failed_unsupported
  - AC4 (SC4) requires manual stress (kill worker + đợi 5 phút)
  - AC5 (SC5) **PASS** memo dedup hoạt động với cocoindex thật
  - **Verdict:** Phase 4 COMPLETE → user accept M2a EXIT GATE → tiếp tục M2b (Phase 5+)

- **Scenario B — Demo FAIL cùng zero-chunks symptom:**
  - AC1 + AC3 PASS (router-side logic OK)
  - AC2 **FAIL** — status STUCK 'pending' hoặc 'failed' với error_message='cocoindex flow generated 0 chunks'
  - AC5 cùng root-cause AC2 fail
  - **Verdict:** New Gap A là production issue → cần Plan 04-08 GAP CLOSURE 2: investigate cocoindex `coco.mount_each` per-row processor invocation + memo policy. M2a EXIT GATE BLOCKED đến khi resolved.

**Why human:** Cần real Postgres + Redis + cocoindex env + OPENAI_API_KEY thật. Test mock LiteLLM trong testcontainers có thể trigger code path khác (mocked aembedding KHÔNG check dim/content), operator demo với cocoindex thật + DOCX y tế thật là proxy chính xác cho M2a EXIT GATE decision tiếp tục M2b.

#### 2. Watchdog Stress Test (SC4 — UNCHANGED)

**Test:** Manual stress test watchdog 5 phút timeout với cocoindex worker thật.

**Steps:**
1. Upload 1 DOCX VN (giả định Scenario A demo PASS).
2. Đợi status='processing'.
3. Kill toàn bộ uvicorn process khi đang trong middle of update_blocking.
4. Restart uvicorn (lifespan re-init Plan 04-07 fail-fast → uvicorn crash nếu LMDB env chưa close → cần restart Docker postgres để reset LMDB env? — operator verify).
5. Đợi 5 phút (Settings.watchdog_timeout_seconds=300).
6. SELECT documents WHERE id=:id → status='failed', error_message LIKE '%timeout%no heartbeat%'.

**Expected:** Watchdog flip processing → failed sau timeout.

**Why human:** Test logic đã verify ở DB level (test_watchdog_flips_stuck_processing PASS), NHƯNG behavior real-world requires cocoindex worker process control mà KHÔNG thể automate trong testcontainers env.

---

### Gaps Summary (Updated Post Plan 04-07)

**Phase 4 status: GAPS_FOUND (UNCHANGED — score 3/5 SC).**

**Plan 04-07 successfully closed:**
1. **Architectural blocker VectorSchemaProvider FIXED** — `pg.TableSchema.from_class(ChunkRow)` exit 0 với `vector(1536)` Postgres type. 73/73 unit test PASS + 15/15 test_rag_flow.py PASS với 3 regression test mới.
2. **Anti-pattern cleanup** — fail-soft → fail-fast lifespan, pytest.skip → assert (CI gate), docstring align cocoindex 1.0.3.
3. **Documentation alignment** — `app/rag/__init__.py` docstring update.

**NEW gaps Plan 04-07 KHÔNG cover (E2E runtime expose):**

1. **New Gap A — cocoindex flow zero-chunks generation:**
   - **Symptom:** test_e2e_upload_docx_to_chunks_completed FAIL — status STUCK 'pending' sau 60s. Captured stderr `trigger_cocoindex_update_zero_chunks: doc_id=...`.
   - **Hypothesis:** cocoindex memo policy / mount_each per-row invocation / @coco.fn decoration trigger memo skip cho new row vừa INSERT.
   - **Impact:** SC2 + SC5 vẫn FAIL post Plan 04-07.

2. **New Gap B — BackgroundTask completes too slow (>60s vs 5s SLA):**
   - **Symptom:** ROADMAP SC2 yêu cầu <5s pending → completed. test E2E timeout 60s vẫn không đủ.
   - **Hypothesis:** cocoindex `update_blocking()` mỗi call full Postgres source rescan + LMDB memo init.
   - **Impact:** SLA violation trong production.

3. **NEW Regression — Test isolation LMDB singleton:**
   - **Symptom:** Plan 04-07 fail-fast lifespan expose pre-existing constraint cocoindex 1.0.3 — Rust LMDB env CHỈ open ONCE per Python process. 9/29 critical test ERROR ở fixture setup.
   - **Affected:** test_auth_login + test_auth_refresh_race + test_documents_list_delete + test_documents_upload + test_jwt_compat + test_rbac_dependency + test_ingest_e2e (test 2-3).
   - **Tests vẫn PASS individually** — chỉ fail khi chạy cùng pytest process.
   - **Impact:** CI bị break full integration suite — phải chạy mỗi test 1 subprocess (`pytest-forked`) hoặc fixture session-scoped.

**Phase 4 đạt 6/8 INGEST end-to-end (UNCHANGED) + 3/5 ROADMAP SC verified (UNCHANGED).** Plan 04-07 fix kiến trúc thành công NHƯNG KHÔNG đủ unblock SC2/SC5 vì 2 NEW runtime gap.

### Recommended Next Steps

**Verifier verdict: gaps_found.** Plan 04-07 PARTIALLY successful — kiến trúc FIXED nhưng runtime expose NEW gaps.

**Recommended sequence:**

1. **PRIORITY 1 — Run M2a EXIT GATE manual demo trước Plan 04-08** (Hub_All/docs/m2a-exit-gate-demo.md với cocoindex + LiteLLM thật):
   - **Nếu demo PASS** (Scenario A) → New Gap A là test mock issue (mocked LiteLLM trigger different code path) → upgrade test_ingest_e2e.py mock pattern HOẶC accept demo PASS = Phase 4 COMPLETE → user accept M2a EXIT GATE.
   - **Nếu demo FAIL** (Scenario B) → New Gap A là production blocker → cần **Plan 04-08 GAP CLOSURE 2: cocoindex flow zero-chunks investigation**.

2. **PRIORITY 2 — Plan 04-08 (BLOCKING nếu demo FAIL)** — Investigate cocoindex flow runtime:
   - Profile `medinet_wiki_main` + `index_document` invocation trace (debug log per cocoindex memo decision).
   - Verify `pg_source.fetch_rows()` actually fetch new rows (not memo-skipped).
   - Verify `coco.mount_each` per-row processor invocation pattern correct cho cocoindex 1.0.3.
   - Reduce update_blocking() latency hoặc tăng E2E_TIMEOUT_SECONDS từ 60 → 300.

3. **PRIORITY 3 — Plan 04-09 (NICE-TO-HAVE)** — Fix LMDB singleton test isolation:
   - Option (a): `setup_cocoindex` idempotent — detect LMDB env open + reuse.
   - Option (b): test fixture session-scoped (1 lifespan setup/teardown cho toàn bộ suite).
   - Option (c): pytest-forked mode (mỗi test 1 subprocess) — slow nhưng simple.
   - Decision: prefer (a) — production-grade idempotent setup; (b)+(c) là test-only workaround.

4. **M2a EXIT GATE gating decision:**
   - **Phase 5+ có thể kick-off PARALLEL** với Plan 04-08 vì auth branch (Phase 5 HUB/USER CRUD) KHÔNG depend on cocoindex chunks data.
   - **Phase 6 (Search) BLOCKED** vì cần chunks pgvector data từ ingest pipeline. Recommend BLOCK Phase 6+ đến khi New Gap A resolved (qua demo PASS hoặc Plan 04-08).
   - **PROJECT.md R3 mitigation:** "Reject demo → STOP M2b, KHÔNG pivot lần 3". Demo Scenario B → KHÔNG pivot, chỉ Plan 04-08 fix forward.

---

_Re-verified: 2026-05-14T18:45:00Z (sau Plan 04-07 GAP CLOSURE shipped)_
_Verifier: Claude (gsd-verifier)_
_Previous verification: 2026-05-14T17:30:00Z (commit 8cac399, status gaps_found, score 3/5)_
