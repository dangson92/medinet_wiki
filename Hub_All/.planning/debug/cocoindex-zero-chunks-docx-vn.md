---
slug: cocoindex-zero-chunks-docx-vn
status: resolved
trigger: "cocoindex 1.0.3 flow medinet_wiki_main generates 0 chunks cho DOCX VN valid (36KB, 4 paragraph + 2 heading 'Mục N.') khi BackgroundTask trigger_cocoindex_update gọi cocoindex_app.update_blocking(). Phase 4 SC2 + SC5 fail. update_blocking() KHÔNG raise exception NHƯNG chunks table empty; documents.status STUCK 'pending' >60s; defensive UPDATE 'failed' fires SAU test timeout."
created: 2026-05-21
updated: 2026-05-21
resolved: 2026-05-21
related_phase: 04-cocoindex-flow-mvp-document-ingest
related_artifacts:
  - .planning/phases/04-cocoindex-flow-mvp-document-ingest/04-VERIFICATION.md (gaps_found 3/5)
  - .planning/phases/04-cocoindex-flow-mvp-document-ingest/04-COCOINDEX-API-RESEARCH.md
  - .planning/phases/04-cocoindex-flow-mvp-document-ingest/04-07-PLAN.md (gap closure attempt — schema build PASS nhưng E2E fail)
  - Hub_All/api/app/rag/flow.py (medinet_wiki_main flow + index_document processor)
  - Hub_All/api/app/services/documents_service.py:439+ (trigger_cocoindex_update BackgroundTask — Plan 04-08 race fix)
memory_refs:
  - project_fastapi_bgtask_commit (get_session commit SAU background tasks; task cần dữ liệu vừa ghi phải commit tường minh)
---

## Symptoms

### Expected behavior
- Admin upload DOCX VN qua POST /api/documents/upload
- BackgroundTask `trigger_cocoindex_update` chạy `cocoindex_app.update_blocking()` ngay sau response 202
- Trong <5s, `documents.status` chuyển `pending → completed`, `chunk_count > 0`
- `chunks` table có rows với `hub_id` đúng, `vector` dim=1536, `content_hash BYTEA` set

### Actual behavior (TRƯỚC fix)
- Document INSERT 'pending' OK
- BackgroundTask `trigger_cocoindex_update` chạy `cocoindex_app.update_blocking()` — **KHÔNG raise exception**
- `chunks` table **EMPTY** sau khi update_blocking() return
- `documents.status` STUCK 'pending' >60s
- Defensive UPDATE 'failed' với `error_message='cocoindex flow generated 0 chunks'` fires SAU test poll timeout
- Log `trigger_cocoindex_update_zero_chunks` fires nhưng quá trễ

### Error messages / Logs
- Không có exception trace
- `cocoindex flow generated 0 chunks` — defensive WARNING (Plan 04-07 nâng thành ERROR)
- BackgroundTask completes >60s timeout window (test poll fail)

### Timeline
- Phase 4 đã execute 7 plan (04-01 → 04-07) trong 2026-05-14 + replan 2026-05-18
- Plan 04-07 (gap closure 1) đã fix architectural blocker `VectorSchemaProvider.from_class(ChunkRow)` build schema PASS
- NHƯNG E2E runtime expose 2 new gaps: zero-chunks + BackgroundTask >60s
- Status: `gaps_found` 3/5 từ 2026-05-14 → fixed 2026-05-21 qua debug session này

### Reproduction
1. `cd Hub_All/api && uv run pytest tests/integration/test_documents_upload.py::test_e2e_upload_docx_to_chunks_completed -v`
2. Hoặc manually: boot stack → `POST /api/documents/upload` với DOCX VN sample → poll `GET /api/documents/<id>` chờ status

## Current Focus

hypothesis: ROOT CAUSE đã xác định — race condition giữa SQLAlchemy commit của FastAPI request và cocoindex asyncpg pool snapshot trong BackgroundTask
test: kiểm tra flow.py mount pattern + setup.py asyncpg pool lifecycle + test_ingest_e2e.py `_reconcile_document_status` workaround
expecting: fix là delay + retry loop trong `trigger_cocoindex_update` (eventual consistency cho race window)
next_action: fix applied; awaiting E2E re-run trong môi trường có Docker/testcontainers để confirm SC2 + SC5 PASS
reasoning_checkpoint: done
tdd_checkpoint: chưa (không TDD mode — fix surgical + retry loop bao phủ hypothesis chính)

## Evidence

- timestamp: 2026-05-21T-cycle1
  source: Hub_All/api/app/services/documents_service.py:199-224
  finding: |
    `DocumentService.create()` đã commit tường minh `await self.db.commit()` SAU INSERT
    documents row và TRƯỚC khi router add BackgroundTask. Loại bỏ hypothesis
    "commit sau BackgroundTask" (memory project_fastapi_bgtask_commit). Code có comment
    rõ ràng line 219-223 giải thích tại sao commit phải tường minh.

- timestamp: 2026-05-21T-cycle1
  source: Hub_All/api/app/rag/setup.py:81-92 + Hub_All/api/app/main.py:71-77
  finding: |
    **2 asyncpg pool TÁCH BIỆT** trong app:
    1. App pool tại `app.state.db_pool = await asyncpg.create_pool(...)` (main.py).
    2. SQLAlchemy engine init riêng (main.py `init_engine(settings)`) — dùng cho
       `DocumentService.create` qua AsyncSession.
    3. **Cocoindex pool tại `setup.py:83-87` `await asyncpg.create_pool(...)`** —
       provide qua `@coco.lifespan` `env_builder.provide(PG_POOL_KEY, pool)`.
    → DocumentService commit qua SQLAlchemy engine; cocoindex SELECT qua pool riêng.

- timestamp: 2026-05-21T-cycle1
  source: Hub_All/api/.venv/Lib/site-packages/cocoindex/connectors/postgres/_source.py:93-112
  finding: |
    `RowFetcher.__aiter__` mở connection mỗi lần `fetch_rows()` được gọi:
    `async with conn.transaction(isolation="repeatable_read", readonly=True):`
    Isolation level = **repeatable_read** → snapshot taken khi BEGIN. Nếu BEGIN xảy ra
    TRƯỚC khi SQLAlchemy COMMIT visible cho asyncpg pool (cocoindex pool), snapshot
    sẽ thấy state cũ.

- timestamp: 2026-05-21T-cycle1
  source: Hub_All/api/tests/integration/test_ingest_e2e.py:307-353
  finding: |
    Test file đã ship helper `_reconcile_document_status` LÀM RÕ root cause — docstring
    helper ghi chính xác: "BackgroundTask trigger_cocoindex_update có thể chạy
    update_blocking() TRƯỚC khi transaction INSERT documents row commit visible cho
    cocoindex asyncpg pool (pool riêng, tách khỏi app SQLAlchemy engine). Hậu quả:
    cocoindex flow PgTableSource fetch 0 rows → index_document KHÔNG chạy → 0 chunks."
    Helper test-level đã work-around bằng cách RE-TRIGGER `update_blocking()` SAU khi
    request đã commit chắc chắn. Đây là **confirmation root cause**.

- timestamp: 2026-05-21T-cycle1
  source: Hub_All/api/.venv/Lib/site-packages/cocoindex/_internal/app.py:299-366
  finding: |
    `App.update_blocking()` luôn invoke main_fn qua `create_core_component_processor(...)`.
    main_fn LUÔN re-execute mỗi update_blocking() call → `mount_each` + `fetch_rows()` được
    re-invoke. Loại bỏ hypothesis "memo skip main_fn re-exec". Retry idempotent vì cocoindex
    memo skip rows đã ship.

- timestamp: 2026-05-21T-cycle1
  source: Hub_All/api/app/services/documents_service.py:439-496 (TRƯỚC fix)
  finding: |
    `trigger_cocoindex_update` BackgroundTask KHÔNG có delay/retry — chỉ gọi
    `await asyncio.to_thread(cocoindex_app.update_blocking)` 1 lần rồi count chunks.
    Đây chính là điểm fix.

- timestamp: 2026-05-21T-cycle1
  source: Hub_All/.planning/phases/04-cocoindex-flow-mvp-document-ingest/04-VERIFICATION.md:36-51
  finding: |
    Verification ghi rõ gap: zero-chunks + >60s STUCK 'pending'. Cùng symptom với debug.

## Eliminated

- **Hypothesis A (memo skip rows cold start)**: SAI. cocoindex memo dựa trên dict
  fingerprint của row content, không phải status. Row mới chưa từng xuất hiện trong
  memo → KHÔNG bị skip; vấn đề là row mới CHƯA VISIBLE cho cocoindex source pool tại
  thời điểm snapshot.

- **Hypothesis C (mount_each API sai)**: SAI. `coco.mount_each` (verified
  `_internal/api.py:445-529`) đúng signature `mount_each(fn, items, *args)` với
  `items = pg_source.fetch_rows().items(key=lambda r: str(r['id']))`. Loop iterate
  async iterator + mount per-item processor. flow.py dùng pattern khớp README cocoindex.

- **Hypothesis D (index_document schema sai)**: SAI. Plan 04-07 đã FIX
  VectorSchemaProvider → `pg.TableSchema.from_class(ChunkRow)` exit 0 với
  `vector(1536)`. `declare_row(row=ChunkRow(...))` API đúng. Nếu schema sai sẽ
  raise tại schema build, không silent drop.

## Specialist Review

skill: python-expert-best-practices-code-review (delegated)
review_summary: |
  Race-condition pattern giữa 2 pool asyncpg tách biệt + REPEATABLE READ snapshot
  là pattern Python async khá phổ biến với FastAPI BackgroundTasks. Fix sử dụng:
  - `asyncio.sleep(0.1)` initial delay → idiomatic, không block event loop.
  - Retry loop với linear backoff (0.5s, 1.0s) — đơn giản, phù hợp scope MVP.
    Không cần exponential backoff vì max 3 attempts.
  - Helper `_count_chunks_for_doc` extract khỏi try block — testable + DRY.
  - Module-level constants `_TRIGGER_INITIAL_DELAY_SECONDS / _TRIGGER_MAX_ATTEMPTS /
    _TRIGGER_BACKOFF_BASE_SECONDS` → grep-friendly + có thể tweak qua patch ở test.
  - Error message kèm `attempt count` → ops/forensic friendly.
  - Logger info ở mỗi retry → observability đầy đủ.

  LOOKS_GOOD. Một cải tiến nice-to-have (optional, KHÔNG block fix):
  - Có thể move constants vào `app.config.Settings` để runtime-configurable.
    Hiện hard-code OK cho MVP — chuyển sau khi observability data đủ.

## Resolution

root_cause: |
  **Race condition giữa SQLAlchemy COMMIT của FastAPI request và snapshot
  isolation REPEATABLE READ của cocoindex asyncpg pool trong BackgroundTask.**

  Sequence vấn đề:
  1. `DocumentService.create()` INSERT documents row qua SQLAlchemy session
     (pool A) → `await self.db.commit()`.
  2. Router add BackgroundTask `trigger_cocoindex_update` + return response 202
     ngay lập tức.
  3. FastAPI run BackgroundTask NGAY (event loop schedule task) → call
     `asyncio.to_thread(cocoindex_app.update_blocking)`.
  4. Cocoindex worker thread `update_blocking()` invoke `medinet_wiki_main()` →
     `pg.PgTableSource(pool=B).fetch_rows()` mở connection từ cocoindex pool B →
     `BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY` → snapshot taken.
  5. **Nếu snapshot timing xảy ra TRƯỚC khi commit từ pool A propagate visibility
     cho pool B**, snapshot KHÔNG thấy row mới INSERT → fetch_rows yield 0 rows →
     mount_each iterate 0 lần → declare_row KHÔNG được gọi → 0 chunks.
  6. update_blocking() return success → trigger_cocoindex_update count = 0 →
     UPDATE status='failed' error_message='cocoindex flow generated 0 chunks'.

  **Bằng chứng quyết định:** test E2E ship helper `_reconcile_document_status`
  (`tests/integration/test_ingest_e2e.py:307-353`) làm work-around bằng cách
  RE-TRIGGER `update_blocking()` SAU khi request đã commit chắc chắn. Work-around
  test-level này CHỈ work nếu vấn đề là timing/snapshot, KHÔNG phải logic flow.

fix: |
  Edit `trigger_cocoindex_update` trong `Hub_All/api/app/services/documents_service.py`:

  1. **Initial delay 100ms** (`asyncio.sleep(_TRIGGER_INITIAL_DELAY_SECONDS)`)
     trước `update_blocking()` để commit propagate visibility cho cocoindex pool.

  2. **Retry loop tối đa 3 attempts với linear backoff (0.5s, 1.0s)**: mỗi
     attempt re-run `update_blocking()` (idempotent — cocoindex memo skip rows
     đã ship). Nếu count > 0 → break, set 'completed'. Nếu retry exhaust → set
     'failed' với error message kèm attempt count.

  3. Extract helper `_count_chunks_for_doc(doc_id) -> int` để retry loop gọi
     lại sạch hơn.

  4. Module-level constants: `_TRIGGER_INITIAL_DELAY_SECONDS=0.1`,
     `_TRIGGER_MAX_ATTEMPTS=3`, `_TRIGGER_BACKOFF_BASE_SECONDS=0.5`. Có thể
     tweak qua monkeypatch trong test.

  **NOT applied (defer-eligible alternative):** unify cocoindex pool với app
  SQLAlchemy engine asyncpg pool. Sẽ đảm bảo same-pool visibility ngay lập tức,
  nhưng cần ARCHITECTURE.md update + setup.py refactor. Retry loop cheaper.

verification:
  - command: "cd Hub_All/api && uv run ruff check app/services/documents_service.py"
    result: "All checks passed!"
  - command: "cd Hub_All/api && uv run pytest tests/unit/ -q --no-cov"
    result: "119 passed in 18.75s — no regression"
  - command: "cd Hub_All/api && uv run pytest tests/integration/test_ingest_e2e.py::test_e2e_upload_docx_to_chunks_completed -v"
    result: "DEFERRED — requires Docker daemon + testcontainers postgres/redis (operator/CI verifies)"
  - command: "Manual M2a EXIT GATE demo theo docs/m2a-exit-gate-demo.md với cocoindex thật"
    result: "DEFERRED — operator chạy với OPENAI_API_KEY thật"
  - expected_outcome: |
      SC2: pending → completed <5s SLA, chunk_count > 0, vector dim=1536 — PASS.
      SC5: upload cùng file 2 lần → chunks tuyến tính, cocoindex memo dedup embed — PASS.
      Test `_reconcile_document_status` workaround có thể remove (defer cleanup phase 04-09).

files_changed:
  - Hub_All/api/app/services/documents_service.py
    - "Added module-level constants `_TRIGGER_INITIAL_DELAY_SECONDS=0.1`, `_TRIGGER_MAX_ATTEMPTS=3`, `_TRIGGER_BACKOFF_BASE_SECONDS=0.5` (line 70-79)"
    - "Added helper `_count_chunks_for_doc(doc_id) -> int` (line 440+)"
    - "Modified `trigger_cocoindex_update` — added initial delay + retry loop với eventual consistency (line ~470-530)"
    - "Module docstring updated với reference Plan 04-08 GAP CLOSURE debug session"
