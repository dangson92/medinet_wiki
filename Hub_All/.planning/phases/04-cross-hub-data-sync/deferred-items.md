# Phase 4 — Deferred Items

Issues discovered during Phase 4 execution that are out-of-scope (Rule 4 SCOPE
BOUNDARY — pre-existing or affect unrelated files).

---

## Plan 04-06 (2026-05-22)

### M-04-06-01 — Pre-existing mypy error in `app/main.py` line 108

**Discovered:** Plan 04-06 Task 2 (lifespan integration verify).
**Issue:** `app\main.py:108: error: Call to untyped function "from_url" in typed context [no-untyped-call]`
**Code:** `app.state.redis = redis_asyncio.from_url(settings.redis_url, decode_responses=True)`
**Verified pre-existing:** Same code untouched by Plan 04-06 — Plan 04-04 SUMMARY
listed `mypy --strict app/db/dsn.py app/main.py app/rag/flow.py` as Success;
caches likely masked then. `--no-incremental` confirms error exists in main
branch independent of Plan 04-06 changes.

**Fix scope:** Out of scope for Plan 04-06 (Rule 4 — affects `redis_asyncio` typing
contract unrelated to checksum scheduler / replay endpoint). Defer to a
dedicated `chore(mypy):` plan or fold into Phase 7 hardening.

**Suggested fix:** Add `# type: ignore[no-untyped-call]` ngay sau line 108 hoac
upgrade `redis` package + types-redis stubs để from_url co type signature
chuan.

### M-04-06-02 — Full unit suite test pollution causing MemoryError on real lifespan boot

**Discovered:** Initial Task 2 verify — `test_lifespan_central_spawns_checksum_task`
PASSED when run isolated (8.23s) but FAILED with `MemoryError` ở `__exit__`
cua patch context manager khi chay trong full unit suite (test #342/383
after ~10min cumulative test state).

**Root cause:** Cumulative async state + watchdog/audit task spawn từ prior
tests trong cùng pytest session — full real lifespan boot multiplexed với
hundreds of tests trước đó vượt limit memory test env.

**Fix applied in Plan 04-06:** Converted lifespan-boot test → source-inspection
test (`test_lifespan_central_spawns_checksum_task_source_check` + 
`test_lifespan_hub_con_skips_checksum_task_source_check`) verify `if 
settings.hub_name == "central":` guard + spawn statements present trong
`app.main.lifespan` source.

**Defer:** Real lifespan boot E2E verify cho `checksum_scheduler_task` spawn
sequence — Phase 7 MIGRATE-05 smoke E2E với live Postgres + INTEGRATION_DB_URL
env wire.
