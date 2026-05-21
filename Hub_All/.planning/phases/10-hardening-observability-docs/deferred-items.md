# Deferred Items — Phase 10

Items discovered during Phase 10 execution that are out of scope for the
current plan but should be tracked for future resolution.

## DEF-10-01-A: `tests/integration/test_eval_pipeline.py` collect error — missing `psycopg`

**Discovered:** 2026-05-21 trong Plan 10-01 Task 2 regression check.

**Symptom:**
```
ImportError while importing test module 'tests/integration/test_eval_pipeline.py'.
File "...api/.venv/Lib/site-packages/...":
File "...eval/lib.py":19: in <module>
    import psycopg
E   ModuleNotFoundError: No module named 'psycopg'
```

**Root cause:** `tests/integration/test_eval_pipeline.py` (Plan 09-05) inject
`sys.path` để import `eval.lib`. `eval/lib.py` import `psycopg` (Plan 09-02) —
nhưng `psycopg` chỉ install trong `eval/.venv` (eval project độc lập với
`api/.venv`). Khi `api/.venv` collect test → ImportError.

**Pre-existing — KHÔNG do Plan 10-01.** Verify: `git log --oneline --
tests/integration/test_eval_pipeline.py` → file thêm bởi Plan 09-05 (`717b53b`).

**Workaround dùng tạm:** `pytest --ignore=tests/integration/test_eval_pipeline.py`.

**Resolution options:**
1. Thêm `psycopg[binary]>=3,<4` vào `api/pyproject.toml` `[project.optional-dependencies].dev`
   — đơn giản nhất, install thêm 1 dep vào api/.venv.
2. Tách `test_eval_pipeline.py` ra ngoài `tests/` thường — chỉ chạy qua
   `make eval-smoke` thay vì `pytest -m critical`.
3. Lazy import `psycopg` trong `eval/lib.py` (chỉ khi gọi function nào dùng nó).

**Phase target:** Plan 10-03 (HARD-03 — integration test suite ≥50% coverage) —
sẽ phải fix vì Plan 10-03 chạy pytest -m critical đủ collection để đo coverage.

## DEF-10-01-B: Các service module khác trong `api/app/services/` vẫn dùng `logging.getLogger`

**Discovered:** 2026-05-21 trong Plan 10-01 Task 2 refactor `documents_service.trigger_cocoindex_update`.

**Scope HARD-01 Plan 10-01:** CHỈ propagate request_id xuống cocoindex flow
(`trigger_cocoindex_update` — function chạy trong FastAPI BackgroundTask cần
ContextVar carry sang). Các function khác trong `documents_service.py` (service
method synchronous gọi từ router scope) + các module `app/services/*.py` khác
vẫn dùng `logger = logging.getLogger(__name__)` — log entry KHÔNG có request_id
field qua structlog ContextVar processor.

**Tác động:** Log entry từ service method (vd `document_delete`, `audit_flush`)
ra stdout dạng stdlib logging format (KHÔNG JSON, KHÔNG request_id). Vẫn được
Docker capture nhưng ops dashboard Loki/Datadog parse được sẽ thiếu correlation.

**Resolution:** Migrate dần các module service sang `structlog.get_logger`
trong v4.0 (defer trong M2 — comprehensive coverage out of scope theo PROJECT).
Phase 10 chỉ cần verify cocoindex BackgroundTask carry request_id (đã DONE).

**Workaround dùng tạm:** structlog ProcessorAdapter wrap stdlib logger nếu cần
migrate full (out of scope Plan 10-01).

## DEF-10-04-A: Pre-existing mypy --strict errors trong `mcp_service/mcp_app/server.py`

**Discovered:** 2026-05-21 trong Plan 10-04 Task 1 verify mypy.

**Symptom (6 errors):**
```
mcp_app\server.py:389: error: Unused "type: ignore" comment  [unused-ignore]
mcp_app\server.py:390: error: Missing type arguments for generic type "Context"  [type-arg]
mcp_app\server.py:441: error: Unused "type: ignore" comment  [unused-ignore]
mcp_app\server.py:442: error: Missing type arguments for generic type "Context"  [type-arg]
mcp_app\server.py:1249: error: Missing type arguments for generic type "dict"  [type-arg]
mcp_app\server.py:1260: error: Returning Any from function declared to return "dict[Any, Any]"  [no-any-return]
```

**Pre-existing — KHÔNG do Plan 10-04.** Verify: `git stash` rồi chạy
`uv run mypy --strict mcp_app/server.py` → 6 errors như trên (toàn pre-existing,
liên quan tới tool decorator `# type: ignore[type-arg]` cho `Context` generic
+ _BasicAuthFormShim `_receive` return type Phase 8.3).

**Plan 10-04 KHÔNG thêm mypy error mới** — đã fix error duy nhất do middleware
mới gây ra (dict missing type args ở `_wrapped_send`).

**Resolution:** Migrate dần khi MCP SDK upstream expose proper `Context[T]`
generic. Defer v4.0 — out of scope Plan 10-04 (CORS policy split focus).

## DEF-10-04-B: Pre-existing ruff E402 + UP012 trong `tests/test_path_prefix_wrapper.py`

**Discovered:** 2026-05-21 trong Plan 10-04 regression sweep.

**Source:** Plan 08.3-07 SUMMARY note (deferred-items.md sau commit `a5f3364`).

**Status:** Plan 10-04 KHÔNG đụng file `tests/test_path_prefix_wrapper.py` (CORS
tests cũ vẫn assert metadata `ACAO=*` đúng behavior sau Plan 10-04). KHÔNG cần
patch test cũ — middleware mới giữ metadata wildcard nguyên vẹn.

**Resolution:** Defer chore commit riêng — out of scope Plan 10-04.

## DEF-10-02-A: 4 pre-existing integration test failures (Phase 8.3 migration 0004)

**Discovered:** 2026-05-21 trong Plan 10-02 Task 2 regression check (`pytest -m critical`).

**Symptom:** 4 test fail trong critical suite (85 PASS / 4 FAIL / 173 deselected):
1. `tests/integration/test_alembic_ignores_cocoindex_schema.py::test_alembic_check_no_drift_after_upgrade`
   — alembic phát hiện removed index `ix_mcp_oauth_clients_client_id` (migration
   0004 add Phase 8.3 nhưng autogen check không khớp).
2. `tests/integration/test_auth_refresh_race.py::test_refresh_happy_returns_new_pair`
   — `KeyError: 'email'` (response shape `/api/auth/refresh` không có `user` object
   nested — contract thay đổi sau commit `41b8d5c`).
3. `tests/integration/test_migration_upgrade_downgrade.py::test_upgrade_creates_10_tables`
   — sau migration 0004 (mcp_oauth_clients) số bảng = 11, test assert == 10.
4. `tests/integration/test_phase4_migration.py::test_phase4_migration_no_drift`
   — cùng nguyên nhân drift Phase 8.3.

**Pre-existing — KHÔNG do Plan 10-02.** Verify:
- 11/11 test mới của Plan 10-02 (6 unit `test_metrics.py` + 5 integration
  `test_metrics_endpoint.py`) PASS.
- 4 test fail trên đều reference schema/migration/auth contract — KHÔNG động
  observability/metrics module mới.
- 4 file pre-date Plan 10-02 (git log `92d966d` Phase 8.3 commit thêm migration 0004).

**Phase target:** Plan 10-03 (HARD-03 — integration test coverage ≥50%) — sẽ
phải fix để integration suite chạy clean cho coverage measure.

**Workaround dùng tạm:** `pytest -m critical --ignore=...4-file-trên` để verify
KHÔNG có regression mới do Plan 10-02.
