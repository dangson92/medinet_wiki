---
phase: 02-hub-con-codebase-factor
plan: 01
subsystem: app-factory
tags:
  - factory
  - router-conditional
  - hub-name
  - factor-01
  - factor-02
  - d-v3-phase2-a
  - d-v3-phase2-b
dependency_graph:
  requires:
    - "01-02-PLAN.md (Settings.hub_name + _enforce_hub_dsn_match validator)"
    - "01-04-PLAN.md (APP_NAMESPACE per-hub — universal lifespan giữ nguyên)"
  provides:
    - "create_app() factory với conditional router mount (FACTOR-01)"
    - "9 central-only router strip ở hub con (FACTOR-02)"
    - "Unit test fixture pattern monkeypatch.setenv + get_settings.cache_clear() boot 4 hub mode"
  affects:
    - "Plan 02-02 (docker-compose 4 service — tiêu thụ create_app() factory)"
    - "Plan 02-03 (integration test endpoint matrix — verify 404 envelope khi router strip)"
tech_stack:
  added: []
  patterns:
    - "Inline conditional router mount `if settings.hub_name == \"central\":`"
    - "Universal lifespan + middleware (D-V3-Phase2-G — KHÔNG đổi)"
    - "Logger info evidence cho FACTOR-02 strip (observability)"
key_files:
  created:
    - "api/tests/unit/test_main_factory.py (232 LOC, 9 test PASS)"
  modified:
    - "api/app/main.py (create_app() refactor mount block — 67 insertions, 59 deletions)"
decisions:
  - "D-V3-Phase2-A: no-arg create_app() factory — đọc settings.hub_name qua get_settings()"
  - "D-V3-Phase2-B: inline if conditional — KHÔNG feature flag config-driven"
  - "D-V3-Phase2-E: 404 shape khi router strip — KHÔNG 403 (router không exist)"
  - "D-V3-Phase2-G: lifespan universal — KHÔNG conditional skip step nào"
  - "WRN-02 honor: ask_router + search_router universal mount; cross-hub alias /api/ask/cross-hub + /api/search/answer defer strip Phase 4 SYNC-03"
metrics:
  duration_minutes: 12
  tasks_completed: 2
  files_modified: 2
  tests_added: 9
  tests_pass: 9
  completed_date: 2026-05-22
requirements:
  - FACTOR-01
  - FACTOR-02
---

# Phase 2 Plan 01: create_app() Factory + Conditional Router Mount Summary

**One-liner:** `create_app()` factory refactor mount 9 central-only router CHỈ khi `settings.hub_name == "central"` — 7 universal router (auth/documents/profile/search/ask/usage/ai_chat) giữ mount ở mọi process, đóng FACTOR-01 + FACTOR-02 ở unit-level với 9/9 test PASS.

---

## Mục tiêu

Refactor `api/app/main.py::create_app()` để mount router conditional theo `settings.hub_name` (Phase 1 Literal `central|yte|duoc|hcns`):

- **Tier 1 — Universal (7 router):** mount ở MỌI process (central + hub con) — `auth, documents, profile, search, ask, usage, ai_chat`. FACTOR-03 hub-scoped contract.
- **Tier 2 — Central-only (9 router):** mount CHỈ khi `hub_name == "central"` — `hubs, users, api_keys, audit_logs, rag_config, system_settings, sync, mcp_oauth, mcp_oauth_internal`. FACTOR-02 strip enforce.
- **Logger info evidence:** khi hub con boot → emit `central_only_routers_skipped: hub_name=<hub>` ở module-level (KHÔNG per-request — chỉ 1 lần boot).

Thêm unit test `tests/unit/test_main_factory.py` boot app ở 4 hub mode (central/yte/duoc/hcns) verify router list đúng expectation + log evidence + Phase 1 DSN validator regression check.

---

## Output

### Task 1 — Refactor `api/app/main.py` (commit `8d164ef`)

**Diff:** 67 insertions, 59 deletions (block mount router line 368-435 thay bằng 2 nhóm Tier 1 + Tier 2 conditional).

**Pattern Tier 1 (universal — line ~388-406):**

```python
from app.auth import auth_router
from app.routers import (
    ai_chat_router, ask_router, documents_router,
    profile_router, search_router, usage_router,
)

app.include_router(auth_router)
app.include_router(documents_router)
app.include_router(profile_router)
app.include_router(search_router)
app.include_router(ask_router)
app.include_router(usage_router)
app.include_router(ai_chat_router)
```

**Pattern Tier 2 (central-only — line ~408-435):**

```python
if settings.hub_name == "central":
    from app.routers import (
        api_keys_router, audit_logs_router, hubs_router,
        mcp_oauth_internal_router, mcp_oauth_router,
        rag_config_router, sync_router, system_settings_router,
        users_router,
    )

    app.include_router(hubs_router)
    app.include_router(users_router)
    app.include_router(api_keys_router)
    app.include_router(audit_logs_router)
    app.include_router(rag_config_router)
    app.include_router(system_settings_router)
    app.include_router(sync_router)
    app.include_router(mcp_oauth_router)
    app.include_router(mcp_oauth_internal_router)
else:
    logger.info(
        "central_only_routers_skipped: hub_name=%s — 9 routers stripped "
        "(FACTOR-02 enforce)",
        settings.hub_name,
    )
```

**KHÔNG đổi:**
- Lifespan M2 (asyncpg pool + redis + cocoindex + jwt + watchdog + audit + search_cache_task) — universal cho mọi hub (D-V3-Phase2-G).
- Middleware order (CORS → SecurityHeaders → RequestId → Prometheus → ErrorHandler).
- HTTPException handler + HubIsolationError handler + healthz/readyz/metrics endpoint.
- Module-level `app = create_app()`.

**Smoke verify (acceptance criteria automated):**
- HUB_NAME=central → app.routes = 63 (mount cả `/api/rag-config`, `/api/hubs`, `/api/auth`, ...).
- HUB_NAME=yte → app.routes = 29 (strip 9 central-only; vẫn còn `/api/auth`, `/api/documents`, `/api/ai/chat`).
- Chênh 34 routes giữa central vs yte do mỗi router central-only có 2-7 endpoint.

### Task 2 — Unit test `tests/unit/test_main_factory.py` (commit `8f0caf8`)

**File mới — 232 LOC, 9 test PASS:**

| # | Test | Cover |
|---|------|-------|
| 1 | `test_factory_central_mounts_all_routers` | HUB_NAME=central → cả 7 universal + 9 central-only prefix có mặt trong app.routes |
| 2-4 | `test_factory_hub_strips_central_only[yte\|duoc\|hcns]` | Parametrize 3 hub — 9 central-only PHẢI strip, 7 universal PHẢI giữ |
| 5 | `test_factory_yte_strips_central_only` | Explicit yte (test name traceability) — `/api/rag-config` strip + `/api/auth` mount |
| 6 | `test_factory_duoc_strips_central_only` | Explicit duoc — `/api/hubs` strip |
| 7 | `test_factory_hcns_strips_central_only` | Explicit hcns — `/api/users` strip |
| 8 | `test_factory_yte_logs_central_only_skip` | caplog capture `logger.info('central_only_routers_skipped: hub_name=yte')` |
| 9 | `test_factory_hub_name_mismatch_dsn_raises` | Phase 1 `_enforce_hub_dsn_match` carry forward — HUB_NAME=yte + DSN `medinet_central` raise ValidationError |

**Fixture pattern (Phase 1 carry forward):**
```python
def _setup_env(monkeypatch, hub_name):
    db = "medinet_central" if hub_name == "central" else f"medinet_hub_{hub_name}"
    monkeypatch.setenv("HUB_NAME", hub_name)
    monkeypatch.setenv("DATABASE_URL", f"postgresql+asyncpg://u:p@localhost:5432/{db}")
    monkeypatch.setenv("COCOINDEX_DATABASE_URL", "postgresql://u:p@localhost:5432/medinet_cocoindex")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("COCOINDEX_SKIP_SETUP", "1")  # DEF-05-01 cocoindex Environment singleton bypass
    get_settings.cache_clear()
```

**autouse fixture `_clear_settings_cache`:** clear `lru_cache` trước + sau mỗi test → state KHÔNG leak giữa test.

---

## Verification

| Check | Status |
|---|---|
| `cd Hub_All/api && uv run ruff check app/main.py tests/unit/test_main_factory.py` | PASS (0 issues) |
| `cd Hub_All/api && uv run mypy app/main.py tests/unit/test_main_factory.py` | PASS (0 errors) |
| `cd Hub_All/api && uv run pytest tests/unit/test_main_factory.py -v` | **9/9 PASS** (5.39s) |
| Phase 1 regression: `pytest tests/unit/test_config_hub_name.py tests/unit/test_alembic_env_hub_arg.py tests/unit/test_flow_per_hub_naming.py -v` | **30/30 PASS** (17.61s) — KHÔNG break |
| Acceptance grep: `if settings.hub_name == "central":` count | 1 ✓ |
| Acceptance grep: `central_only_routers_skipped` count | 1 (main.py) + 3 (test) ✓ |
| Acceptance grep: `FACTOR-01\|FACTOR-02` count main.py | 4 ✓ (≥ 2) |
| Acceptance grep: `D-V3-Phase2-A\|D-V3-Phase2-B` count main.py | 2 ✓ |
| Acceptance grep: `Tier 1 — Universal\|Tier 2 — Central-only` count main.py | 2 ✓ |
| Smoke: HUB_NAME=central create_app() → `/api/rag-config` mount | OK 63 routes |
| Smoke: HUB_NAME=yte create_app() → `/api/rag-config` strip, `/api/auth` mount | OK 29 routes |

---

## Decisions Made

1. **D-V3-Phase2-A consumed:** `create_app()` giữ signature no-arg M2. Đọc `settings.hub_name` qua `get_settings()` singleton (Phase 1 lru_cache). Test override qua `monkeypatch.setenv` + `get_settings.cache_clear()`.

2. **D-V3-Phase2-B consumed:** Inline `if settings.hub_name == "central":` block trong `create_app()` — KHÔNG dùng feature flag config-driven (`settings.router_central_only`). Code đọc tuyến tính, grep ra ngay.

3. **D-V3-Phase2-E consumed:** Router không mount → FastAPI built-in 404 → `ErrorHandlerMiddleware` M2 wrap envelope `{success:false, data:null, error:{code:"NOT_FOUND", message}, meta:null}`. KHÔNG dùng 403 (leak endpoint existence).

4. **D-V3-Phase2-G consumed:** Lifespan KHÔNG đổi — universal cho mọi hub. Hub con vẫn cần asyncpg pool + redis + cocoindex local + jwt + watchdog + audit + search_cache_task.

5. **WRN-02 honored:** `ask_router` + `search_router` thuộc nhóm universal Plan 02-01 — cross-hub alias `/api/ask/cross-hub` + `/api/search/answer` hiện EXPOSE ở hub con runtime. Phase 4 SYNC-03 sẽ tách `ask_local_router` (universal) khỏi `ask_cross_hub_router` (central-only). DB-level isolation E-V3-3 Phase 1 enforce KHÔNG có lỗ hổng leak data.

6. **Logger info emit 1 lần boot, KHÔNG per-request:** mitigate T-02-01-05 DoS (log spam). Verify qua `grep -c central_only_routers_skipped api/app/main.py` = 1.

---

## Deviations from Plan

**None — plan executed exactly as written.**

Cả 2 task hoàn thành theo `<action>` block của plan, không Rule 1/2/3 deviation. Lint + type-check + pytest đều PASS lần đầu.

Lỗi nhỏ duy nhất gặp khi viết test: mypy --strict báo `Generator` return type cho fixture yield → fix thêm `from collections.abc import Iterator` + annotation `Iterator[None]`. Đây là fix lint-level KHÔNG phải deviation behavior.

---

## Authentication Gates

**None.** Test unit-level KHÔNG cần Postgres/Redis thật — chỉ check `app.routes` list-as-is sau `create_app()`. KHÔNG có auth gate.

---

## Notable Implementation Details

### Cocoindex test mode escape (DEF-05-01)

`COCOINDEX_SKIP_SETUP=1` env var bypass `setup_cocoindex()` trong lifespan. Cocoindex 1.0.3 `core.Environment` là process-global singleton — KHÔNG re-open được sau khi đã open + close. Unit test boot `create_app()` 9 lần (1 central + 3 parametrize + 3 explicit + 1 log + 1 mismatch) sẽ FAIL từ lần thứ 2 nếu KHÔNG skip cocoindex. Production KHÔNG bao giờ set flag này.

### Route count chênh giữa central vs hub con

- Central: 63 routes (7 universal × N endpoint + 9 central-only × M endpoint + healthz/readyz/metrics + middleware route).
- Hub con: 29 routes (chỉ 7 universal + healthz/readyz/metrics).
- Chênh 34 routes do 9 central-only router mỗi router có 2-7 endpoint (vd `/api/rag-config` GET+PUT, `/api/users` GET+POST+PATCH+DELETE, `/api/hubs` GET+POST+PUT+DELETE, ...).

### Phase 1 DSN validator carry forward

Plan 02-01 KHÔNG sửa `Settings._enforce_hub_dsn_match` (Phase 1 TOPO-04 Plan 01-02). Test 9 (`test_factory_hub_name_mismatch_dsn_raises`) verify HUB_NAME=yte + DATABASE_URL trỏ `medinet_central` vẫn raise `ValidationError("DSN mismatch hub_name")`. E-V3-3 enforce KHÔNG regress.

---

## Next Steps

**Plan 02-01 BLOCKING dependency cho Wave 2:**

- **Plan 02-02 (Wave 2 parallel):** Docker compose 4 service `&api-template` anchor + cocoindex LMDB volume per-hub + port mapping 8180-8183 + `mcp_service.MCP_API_BASE_URL` re-point `python-api-central`. Consume `create_app()` factory mount conditional đã ship.

- **Plan 02-03 (Wave 2 parallel):** Integration test `tests/integration/test_factor_hub_scoped.py` — endpoint matrix 12 hub-scoped + 8 central-only + envelope shape 404 verify khi router strip. Consume FACTOR-02 strip behavior verify ở Plan 02-01 unit-level.

- **Plan 02-04 (Wave 3 closeout):** CLAUDE.md section 2 update Phase 2 DONE + STATE.md move + REQUIREMENTS.md mark FACTOR-01/02/03 ✓ + smoke compose checkpoint:human-action.

**FACTOR-03 (hub-scoped 10 endpoint) coverage:** Plan 02-01 mount 7 universal router → bao gồm cả 12 endpoint cụ thể trong FACTOR-03 list (4 auth + 2 profile + 3 documents + 1 search + 1 ask + 1 usage). Verify endpoint trả 200/auth-reject (KHÔNG 404) defer Plan 02-03 integration.

---

## Self-Check: PASSED

**Files verified exist:**
- `Hub_All/api/app/main.py` — FOUND (modified, 67 insertions, 59 deletions)
- `Hub_All/api/tests/unit/test_main_factory.py` — FOUND (created, 232 LOC)

**Commits verified exist:**
- `8d164ef` — `feat(02-01): conditional router mount theo settings.hub_name` — FOUND
- `8f0caf8` — `test(02-01): unit test create_app() factory 4 hub mode` — FOUND

**Test results verified:**
- `tests/unit/test_main_factory.py` — 9/9 PASS (5.39s)
- Phase 1 regression (`test_config_hub_name.py` + `test_alembic_env_hub_arg.py` + `test_flow_per_hub_naming.py`) — 30/30 PASS (17.61s)

**Acceptance criteria verified:** Tất cả grep + smoke check trong `<acceptance_criteria>` block của Task 1 + Task 2 PASS.

---

*Plan 02-01 completed 2026-05-22. Wave 1 BLOCKING ✅ — Plan 02-02 + 02-03 sẵn sàng execute Wave 2.*
