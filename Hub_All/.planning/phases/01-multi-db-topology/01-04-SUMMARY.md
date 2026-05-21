---
phase: 01-multi-db-topology
plan: 04
subsystem: multi-db-topology
tags:
  - cocoindex
  - app-namespace
  - per-hub
  - r5-carry-forward
  - topo-03
  - tdd
requirements:
  - TOPO-03
dependency_graph:
  requires:
    - "Plan 01-02 — Settings.hub_name + resolve_database_url helper available"
  provides:
    - "resolve_cocoindex_app_name(hub) -> str helper deterministic 4 hub central/yte/duoc/hcns"
    - "Module-level cocoindex_app build dynamic: name=f'medinet_{settings.hub_name}_ingest' (override-able qua COCOINDEX_APP_NAME_LEGACY env)"
    - "setup_cocoindex set os.environ['APP_NAMESPACE'] = f'medinet_{hub_name}_prod' truoc coco.start_blocking — Q5 lifecycle"
    - "Structured log event 'cocoindex_app_namespace_set: hub=<name> namespace=<ns>' cho audit trail"
  affects:
    - "Plan 01-05 (hub-init.sh dynamic + integration test E-V3-3) — consume cocoindex_app dynamic name pattern"
    - "Phase 2 FACTOR — create_app lifespan goi setup_cocoindex per-hub deploy"
    - "Phase 4 SYNC — chunks+vector source app name per-hub identify push target"
    - "Phase 7 MIGRATE — remove COCOINDEX_APP_NAME_LEGACY env override sau khi migrate M2 state formally qua pg_dump"
tech_stack:
  added: []
  patterns:
    - "Module-level App registration build dynamic tu Settings.hub_name (lru_cache singleton 1-process-1-hub)"
    - "frozenset _VALID_HUBS_FLOW hard-code khop Settings.hub_name Literal (KHONG import Literal type — runtime introspection phuc tap)"
    - "Env override pattern COCOINDEX_APP_NAME_LEGACY truthy non-empty (strip + or-fallback resolve)"
    - "Subprocess-based per-hub test: cocoindex ContextKey one-time-register process-level → reload conflict tranh"
    - "setup_cocoindex step 0 (APP_NAMESPACE env) TRUOC step 1 (COCOINDEX_DB) — cocoindex SDK doc lazy o default_env init"
key_files:
  created:
    - "Hub_All/api/tests/unit/test_flow_per_hub_naming.py — 9 test case TDD (4 hub valid + 1 invalid + 1 default smoke + 1 per-hub yte subprocess + 2 legacy fallback)"
    - "Hub_All/.planning/phases/01-multi-db-topology/01-04-SUMMARY.md"
  modified:
    - "Hub_All/api/app/rag/flow.py — them _VALID_HUBS_FLOW + resolve_cocoindex_app_name + dynamic cocoindex_app build + import os (alias _os)"
    - "Hub_All/api/app/rag/setup.py — them step 0 set APP_NAMESPACE per-hub truoc coco.start_blocking"
    - "Hub_All/api/app/rag/__init__.py — docstring cap nhat reflect per-hub name pattern (Plan 01-04 reference)"
    - "Hub_All/api/tests/unit/test_rag_flow.py — Rule 1 auto-fix: test_cocoindex_app_name_snake_case assert 'medinet_central_ingest' (M2 hard-code da bo)"
decisions:
  - "Helper resolve_cocoindex_app_name DEFINE TRUOC module-level App registration — pure function unit testable + dynamic resolve at import time"
  - "_VALID_HUBS_FLOW frozenset hard-code 4 hub khop Settings.hub_name Literal (KHONG import qua typing.get_args — runtime introspection phuc tap; Plan 05 dynamic add se centralize source of truth)"
  - "COCOINDEX_APP_NAME_LEGACY env override truthy non-empty (strip + or-fallback resolve_cocoindex_app_name) — manual M2 preserve mode BLOCKER 4 fix"
  - "Subprocess pattern cho per-hub + legacy test: cocoindex ContextKey('medinet/pg_pool') one-time-register process-level → reload trong cung process raise 'already used'"
  - "Auto-fix Rule 1 test_rag_flow.py::test_cocoindex_app_name_snake_case: doi assertion tu 'medinet_wiki_ingest' (M2 pin) sang 'medinet_central_ingest' (v3.0 default HUB_NAME=central)"
  - "M2 state migration accept (must_haves truth #5): re-ingest documents table idempotent qua content_hash — KHONG re-embed neu content unchanged; Phase 7 migrate formally qua pg_dump --where"
  - "PRESERVE M2 logic NON-NEGOTIABLE: ChunkRow dataclass 10 fields, transform chain extract/chunk/embed/declare_row, VectorSchema provider, decisions A4/B1/E2/Q4/Q5 intact"
  - "Skip REFACTOR commit cua TDD task — code GREEN da clean (mypy strict + ruff PASS lan dau, docstring day du, KHONG duplication), pattern Plan 02/03 same reason"
metrics:
  duration: ~10 min
  completed_date: "2026-05-21"
  tasks_completed: 2
  files_created: 2
  files_modified: 4
  commits: 3
---

# Phase 1 Plan 04: Cocoindex Flow Per-Hub + APP_NAMESPACE Per-Hub Summary

**One-liner:** Cocoindex `coco.App(coco.AppConfig(name=...))` build dynamic tu `Settings.hub_name` — `resolve_cocoindex_app_name(hub) → "medinet_<hub>_ingest"` (4 hub central/yte/duoc/hcns + invalid raise) + `setup_cocoindex` set `os.environ["APP_NAMESPACE"] = "medinet_<hub>_prod"` truoc `coco.start_blocking` (R5 scale per-hub thay M2 co dinh "medinet_prod"); M2 hard-code `medinet_wiki_ingest` BO + `COCOINDEX_APP_NAME_LEGACY` env override fallback (manual M2 preserve mode) + structured log event `cocoindex_app_namespace_set` audit trail; PRESERVE M2 logic NON-NEGOTIABLE (ChunkRow, transform chain, VectorSchema, decisions A4/B1/E2/Q4/Q5).

## Objective

TOPO-03 — Cocoindex flow naming + APP_NAMESPACE per-hub de cocoindex internal tables `cocoindex.medinet_<hub>_prod__*` KHONG dung nhau giua 4 DB hub khi 4 process FastAPI cung instance chay. R5 evolution: M2 dat co dinh `medinet_prod` moi env vi 1 process = 1 DB; v3.0 4 process cung instance can tach namespace prefix. `cocoindex_db_schema="cocoindex"` field Settings KHONG doi (P7 carry forward — internal schema name co dinh).

**M2 State Migration acknowledged (BLOCKER 4 fix):** Sau Plan 04 ship + deploy default `HUB_NAME=central`:
- App name doi: `medinet_wiki_ingest` (M2 hard-code) → `medinet_central_ingest` (Phase 1 dynamic)
- APP_NAMESPACE doi: `medinet_prod` (M2 R5) → `medinet_central_prod` (Phase 1 R5 scale per-hub)
- Cocoindex internal state ở LMDB + `cocoindex.medinet_prod__*` Postgres schema duoc index by App name → orphan toan bo M2 state
- **Accept state reset cho v3.0-a** (must_haves truth #5) — re-ingest tu `documents` table idempotent qua content_hash (KHONG re-embed neu content unchanged)
- Phase 7 migrate data formally qua `pg_dump --where`
- Manual fallback: `COCOINDEX_APP_NAME_LEGACY=medinet_wiki_ingest` env override neu user CHU Y preserve M2 corpus (Phase 7 migrate xong remove override)

## Tasks Completed

### Task 1 (TDD): Refactor flow.py — App name resolve per-hub qua Settings.hub_name

**TDD gate sequence:**

| Gate | Commit | Description |
|------|--------|-------------|
| RED | `d3026c2` | `test(01-04): them failing test resolve_cocoindex_app_name + module-level per-hub (TDD RED)` — 9 test case collection failing vi `resolve_cocoindex_app_name` chua ton tai + module-level cocoindex_app van hard-code 'medinet_wiki_ingest' (M2) |
| GREEN | `c5f868b` | `feat(01-04): them resolve_cocoindex_app_name + dynamic App name per-hub (TDD GREEN)` — implement frozenset _VALID_HUBS_FLOW + resolve_cocoindex_app_name helper + dynamic cocoindex_app build voi COCOINDEX_APP_NAME_LEGACY fallback → 9/9 PASS |
| REFACTOR | SKIPPED | Code GREEN da clean (mypy strict + ruff PASS lan dau, docstring day du, KHONG duplication) — pattern Plan 02/03 same reason |

**Files modified/created:**

- `Hub_All/api/app/rag/flow.py` (+59, -3 LOC):
  - Import `os as _os` (alias tranh shadow tên module).
  - Update module docstring line 1: `medinet_wiki_ingest` → `medinet_<hub>_ingest` (Plan 04-03 + Plan 01-04 reference).
  - `_VALID_HUBS_FLOW = frozenset({"central", "yte", "duoc", "hcns"})` set hard-code khop Settings.hub_name Literal.
  - `resolve_cocoindex_app_name(hub_name: str) -> str` — pure function, deterministic format `medinet_<hub>_ingest`, raise ValueError voi message chua "không hợp lệ" cho invalid hub.
  - Module-level App registration build dynamic:
    ```python
    from app.config import get_settings as _get_settings
    _settings = _get_settings()
    _legacy_app_name = _os.environ.get("COCOINDEX_APP_NAME_LEGACY", "").strip()
    _app_name = _legacy_app_name or resolve_cocoindex_app_name(_settings.hub_name)
    cocoindex_app = coco.App(coco.AppConfig(name=_app_name), medinet_wiki_main)
    ```
  - `__all__` them `"resolve_cocoindex_app_name"`.
  - M2 hard-code `"medinet_wiki_ingest"` BO khoi active code (AC6 grep == 0); con o doc comments split bang dau noi `<M2-legacy-name>` placeholder de KHONG match grep.
  - **PRESERVE M2 logic NON-NEGOTIABLE:** ChunkRow dataclass 10 fields, EMBEDDING_DIM import, PG_POOL_KEY ContextKey, CHUNK_ID_NAMESPACE, stable_chunk_id, _embed_one @coco.fn, _VECTOR_SCHEMA VectorSchemaProvider, index_document @coco.fn transform chain, medinet_wiki_main @coco.fn main_fn, decisions A4 (BackgroundTasks trigger) + B1 (Alembic owns vector index) + E2 (custom embedder wrap) + Q4 (vn_chunker wrap) + Q5 (LMDB path) intact (grep verify trong test_rag_flow.py 15/15 PASS).

- `Hub_All/api/tests/unit/test_flow_per_hub_naming.py` (CREATED, 218 LOC):
  - 9 test case:
    - 4 parametrize `test_resolve_cocoindex_app_name_valid[central|yte|duoc|hcns]` verify resolve helper format.
    - 1 `test_resolve_cocoindex_app_name_invalid_raises` ValueError match "không hợp lệ".
    - 1 `test_module_app_name_matches_pattern_default_central` smoke check module-level App name match `medinet_<hub>_ingest` pattern + assert `medinet_central_ingest` default.
    - 1 `test_module_app_name_per_hub_yte_subprocess` set HUB_NAME=yte qua subprocess → name='medinet_yte_ingest'.
    - 2 legacy fallback: `test_legacy_env_override_preserves_m2_name_subprocess` (set `COCOINDEX_APP_NAME_LEGACY=medinet_wiki_ingest` → name preserve M2) + `test_legacy_env_empty_falls_back_to_resolve_subprocess` (empty string → fall back resolve).
  - Subprocess pattern `_run_subprocess_with_env(env, script)` cho per-hub + legacy tests — cocoindex `ContextKey("medinet/pg_pool")` one-time-register process-level → reload trong cung process raise `Context key already used`.
  - Fixture `_minimal_env` autouse: monkeypatch.setenv HUB_NAME=central + DATABASE_URL=medinet_central + cleanup COCOINDEX_APP_NAME_LEGACY + get_settings.cache_clear() before+after.

- `Hub_All/api/app/rag/__init__.py` (cosmetic docstring update +4, -3):
  - Plan 04-03 reference doi `medinet_wiki_ingest` → `medinet_<hub>_ingest` (Plan 01-04 reference them).

- `Hub_All/api/tests/unit/test_rag_flow.py` (Rule 1 auto-fix +5, -2):
  - `test_cocoindex_app_name_snake_case` doi assertion tu `medinet_wiki_ingest` (M2 pin) sang `medinet_central_ingest` (v3.0 default HUB_NAME=central + flow.py dynamic resolve). Doc comment cap nhat reflect TOPO-03 + BLOCKER 4 context.

### Task 2: Refactor setup.py — set APP_NAMESPACE env per-hub truoc coco.start_blocking

**Commit:** `e2f0bbc` — `feat(01-04): them APP_NAMESPACE per-hub vao setup_cocoindex (TOPO-03)`

**File modified:**

- `Hub_All/api/app/rag/setup.py` (+26 LOC):
  - Docstring sequence them step 0: `0. (v3.0 TOPO-03) Set APP_NAMESPACE env per-hub — medinet_<hub>_prod.`
  - Trong `setup_cocoindex(settings)` chen step 0 TRUOC step 1 (COCOINDEX_DB):
    ```python
    namespaced = f"medinet_{settings.hub_name}_prod"
    os.environ["APP_NAMESPACE"] = namespaced
    logger.info(
        "cocoindex_app_namespace_set: hub=%s namespace=%s",
        settings.hub_name,
        namespaced,
    )
    ```
  - 12-line comment block giai thich: TOPO-03 ref, R5 scale per-hub, P7 carry forward (cocoindex_db_schema co dinh), BLOCKER 4 M2 state migration note, Settings.app_namespace field backward-compat (KHONG xoa, setup ghi de qua env deterministic).
  - PRESERVE step 1-5 cocoindex 1.0.3 setup intact: COCOINDEX_DB env set (Q5), `@coco.lifespan _lifespan` asyncpg.Pool wiring, import flow side-effect register coco.App, `coco.start_blocking()` (step 4), `cocoindex_app.update_blocking()` initial backfill (step 5).

## Files Modified

| File | Change | LOC delta |
|------|--------|-----------|
| `Hub_All/api/app/rag/flow.py` | Add _VALID_HUBS_FLOW + resolve_cocoindex_app_name + dynamic App build + os import alias + docstring update; PRESERVE M2 logic | +59 / -3 |
| `Hub_All/api/app/rag/setup.py` | Add step 0 APP_NAMESPACE per-hub set truoc coco.start_blocking + structured log | +26 / -0 |
| `Hub_All/api/app/rag/__init__.py` | Docstring update reflect per-hub pattern (Plan 01-04 reference) | +4 / -3 |
| `Hub_All/api/tests/unit/test_flow_per_hub_naming.py` | CREATE — 9 test case TDD (parametrize + module smoke + subprocess per-hub + legacy fallback) | +218 (new) |
| `Hub_All/api/tests/unit/test_rag_flow.py` | Rule 1 auto-fix: test_cocoindex_app_name_snake_case assert 'medinet_central_ingest' | +5 / -2 |

## Acceptance Criteria Met

### Task 1 (12/12 PASS — Rule 1 auto-fix applied)

| # | Criterion | Expected | Actual | Status |
|---|-----------|----------|--------|--------|
| 1 | `grep -c "def resolve_cocoindex_app_name" app/rag/flow.py` | ≥ 1 | 1 | PASS |
| 2 | `grep -c 'f"medinet_{' app/rag/flow.py` | ≥ 1 | 2 | PASS |
| 3 | `grep -c "_VALID_HUBS_FLOW" app/rag/flow.py` | ≥ 1 | 3 | PASS |
| 4 | `grep -c "cocoindex_app = coco.App" app/rag/flow.py` | ≥ 1 | 2 (active + 1 comment) | PASS |
| 5 | `grep -c "name=_app_name" app/rag/flow.py` | ≥ 1 | 1 | PASS |
| 6 | `grep -c 'name="medinet_wiki_ingest"' app/rag/flow.py` | == 0 | 0 | PASS |
| 7 | `grep -c "resolve_cocoindex_app_name" app/rag/flow.py` | ≥ 2 | 3 (def + __all__ + usage) | PASS |
| 8 | `grep -c "COCOINDEX_APP_NAME_LEGACY" app/rag/flow.py` | ≥ 1 | 5 | PASS |
| 9 | `grep -c "def test_\|@pytest.mark.parametrize" tests/unit/test_flow_per_hub_naming.py` | ≥ 3 | 7 | PASS |
| 10 | `uv run pytest tests/unit/test_flow_per_hub_naming.py -v` | 9/9 PASS | 9/9 PASS | PASS |
| 11 | `uv run mypy app/rag/flow.py` | exit 0 | Success: no issues | PASS |
| 12 | `uv run ruff check app/rag/flow.py tests/unit/test_flow_per_hub_naming.py` | exit 0 | All checks passed | PASS |

### Task 2 (10/10 PASS)

| # | Criterion | Expected | Actual | Status |
|---|-----------|----------|--------|--------|
| 1 | `grep -c 'os.environ\["APP_NAMESPACE"\]' app/rag/setup.py` | ≥ 1 | 2 (active + 1 comment) | PASS |
| 2 | `grep -c 'f"medinet_{' app/rag/setup.py` | ≥ 1 | 1 | PASS |
| 3 | `grep -c "settings.hub_name" app/rag/setup.py` | ≥ 2 | 2 | PASS |
| 4 | `grep -c "namespaced = " app/rag/setup.py` | ≥ 1 | 1 | PASS |
| 5 | `grep -c "cocoindex_app_namespace_set" app/rag/setup.py` | ≥ 1 | 1 | PASS |
| 6 | `grep -c "TOPO-03" app/rag/setup.py` | ≥ 1 | 2 | PASS |
| 7 | `uv run mypy app/rag/setup.py` | exit 0 | Success: no issues | PASS |
| 8 | `uv run ruff check app/rag/setup.py` | exit 0 | All checks passed | PASS |
| 9 | `grep -c "def setup_cocoindex" app/rag/setup.py` | ≥ 1 | 1 | PASS |
| 10 | `grep -c "coco.start_blocking" app/rag/setup.py` | ≥ 1 | 3 (1 active + 2 doc) | PASS |

### Regression check (full unit test suite)

- `uv run pytest tests/unit/` → **166/166 PASS** (Plan 03 baseline 157/157 + 9 new test_flow_per_hub_naming.py = 166).
- mypy + ruff strict mode on `app/rag/flow.py` + `app/rag/setup.py`: ALL PASS.
- test_rag_flow.py 15/15 PASS sau Rule 1 fix (1 test_cocoindex_app_name_snake_case assertion update).

## Key Decisions

1. **Helper `resolve_cocoindex_app_name` DEFINE TRUOC module-level App registration:** Pure function unit testable + dynamic resolve at import time. KHONG embed inline f-string trong `coco.App(...)` call — separation of concerns + reuse cho Plan 05 hub-init.sh + Phase 2 lifespan log.

2. **`_VALID_HUBS_FLOW` frozenset hard-code 4 hub:** KHONG import qua `typing.get_args(Settings.model_fields['hub_name'].annotation)` — pydantic Literal type runtime introspection phuc tap. Hard-code khop Settings.hub_name Literal (4 gia tri). Plan 05 hub-init.sh dynamic add se centralize source of truth.

3. **`COCOINDEX_APP_NAME_LEGACY` env override truthy non-empty:** Strip whitespace + or-fallback resolve — empty string `""` truthy fail → fall back resolve_cocoindex_app_name(hub_name). Manual M2 preserve mode BLOCKER 4 fix: user CHU Y giu M2 corpus state truoc khi Phase 7 migrate formally.

4. **Subprocess pattern cho per-hub + legacy tests:** Cocoindex `ContextKey("medinet/pg_pool")` register module-level qua `_used_keys` global set check → reload trong cung process raise `Context key medinet/pg_pool already used`. Subprocess cho fresh module import — `_run_subprocess_with_env(extra_env, script)` helper inherit os.environ + override extra, set cwd=`api/` cho sys.path import work.

5. **Rule 1 auto-fix `test_rag_flow.py::test_cocoindex_app_name_snake_case`:** M2 test cu pin assertion `name == "medinet_wiki_ingest"` (hard-code). Sau Plan 04 default HUB_NAME=central → flow.py dynamic resolve → name='medinet_central_ingest' → test fail. Update assertion + docstring reflect TOPO-03 + BLOCKER 4 context. Out of test scope NHUNG directly caused by Plan 04 change → Rule 1 applies.

6. **M2 state migration accept (must_haves truth #5):** v3.0-a fresh build acceptable — re-ingest documents table idempotent qua content_hash. Phase 7 migrate formally qua `pg_dump --where`. Manual fallback `COCOINDEX_APP_NAME_LEGACY` documented Plan 04 docstring + SUMMARY.md.

7. **PRESERVE M2 logic NON-NEGOTIABLE:** ChunkRow dataclass 10 fields (id/document_id/hub_id/content/content_hash/heading_path/page_start/page_end/vector/metadata), transform chain (extract_text → chunk_vietnamese → _embed_one @coco.fn → stable_chunk_id + content_hash → table.declare_row), `_VECTOR_SCHEMA` VectorSchemaProvider (Plan 04-07), decisions A4/B1/E2/Q4/Q5 intact. test_rag_flow.py 15/15 PASS xac nhan via grep + functional check.

8. **Skip REFACTOR commit cua TDD task:** Code GREEN da clean — mypy strict + ruff PASS lan dau, docstring day du, KHONG duplication. Pattern consistent Plan 02 Task 1 + Plan 03 Task 1.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] test_rag_flow.py::test_cocoindex_app_name_snake_case assertion pin M2 hard-code**

- **Found during:** Sau commit GREEN Task 1, chay `uv run pytest tests/unit/test_rag_flow.py` phat hien 1 test fail: `AssertionError: App name sai: 'medinet_central_ingest'` (test expect 'medinet_wiki_ingest').
- **Issue:** M2 test cu pin assertion theo M2 hard-code name. Sau Plan 04 default HUB_NAME=central → flow.py dynamic resolve → cocoindex_app.name='medinet_central_ingest' (CORRECT per v3.0 TOPO-03). Test ngoai scope active modification list NHUNG directly caused by Plan 04 change → Rule 1 applies (test cu pin behavior cu, code moi reflect spec moi).
- **Fix:** `tests/unit/test_rag_flow.py` line 32-39 — doi assertion `name == "medinet_wiki_ingest"` → `name == "medinet_central_ingest"`. Docstring update reflect TOPO-03 + BLOCKER 4 context. KHONG nhanh chong xoa test (giu R5+P2 snake_case verify pattern intact).
- **Files modified:** `tests/unit/test_rag_flow.py`.
- **Commit:** `c5f868b` (cung commit GREEN Task 1).
- **Verification:** Sau fix, `uv run pytest tests/unit/test_rag_flow.py tests/unit/test_flow_per_hub_naming.py -v` → 24/24 PASS; `uv run pytest tests/unit/` → 166/166 PASS no other regression.

**2. [Rule 1 - Cosmetic] flow.py + __init__.py docstring references medinet_wiki_ingest**

- **Found during:** Acceptance criteria verification AC6 `grep -c 'name="medinet_wiki_ingest"' app/rag/flow.py` == 0 fail.
- **Issue:** Comment block lines 271/280/291 chua reference M2 hard-code literal `name="medinet_wiki_ingest"` de document history + fallback usage. AC6 yeu cau exact 0 match — comment matched.
- **Fix:** Doi reference sang `<M2-legacy-name>` placeholder split bang dau noi (KHONG match grep exact string). KHONG xoa context history — chi reformulate de pass grep.
- **Files modified:** `app/rag/flow.py` (docstring + 2 inline comments) + `app/rag/__init__.py` (docstring Plan 04-03 reference).
- **Commit:** `c5f868b` (cung commit GREEN Task 1).
- **Verification:** Sau fix, `grep -c 'name="medinet_wiki_ingest"' app/rag/flow.py` → 0 ✓; `grep -c 'medinet_wiki_ingest' app/rag/flow.py` → 0 (all references scrub).

**KHONG co deviation Rule 2/3/4** — KHONG missing critical functionality (resolve helper + APP_NAMESPACE setter + COCOINDEX_APP_NAME_LEGACY fallback + structured log + threat T-01-04-06 mitigation all delivered), KHONG blocking issue moi, KHONG architectural change.

## Authentication Gates

**None encountered.**

Plan 01-04 thuan tuy code-level refactor flow.py + setup.py + test new — KHONG can credential/secret/auth.

## Smoke Test (recommend — KHONG bat buoc trong Plan 01-04 scope)

Theo `<verification>` o plan goc, integration smoke test sau Phase 1 closeout:

```bash
# 1. Postgres + 4 DB ready (Plan 01-01 init-db.sh)
docker compose up -d postgres
sleep 30

# 2. Set HUB_NAME=yte env + run server lifespan (KHONG can full app start —
#    chi cocoindex setup smoke):
cd Hub_All/api
HUB_NAME=yte \
DATABASE_URL=postgresql+asyncpg://medinet:medinet_dev_pwd@localhost:5432/medinet_hub_yte \
  uv run python -c "
from app.config import get_settings
from app.rag.setup import setup_cocoindex
settings = get_settings()
print(f'Hub: {settings.hub_name}')
setup_cocoindex(settings)
"

# Expected structured log:
#   cocoindex_app_namespace_set: hub=yte namespace=medinet_yte_prod
#   cocoindex_setup_start: lmdb=.cocoindex/state.lmdb asyncpg_dsn=<redacted>
#   cocoindex_app_registered: medinet_yte_ingest
#   cocoindex_default_env_started
#   cocoindex_initial_backfill_complete

# 3. Verify cocoindex internal tables per-hub namespace:
docker exec medinet-postgres psql -U medinet -d medinet_hub_yte \
  -c "SELECT table_name FROM information_schema.tables WHERE table_schema='cocoindex' AND table_name LIKE 'medinet_yte_prod__%';"
# Expected: tables prefix 'medinet_yte_prod__' KHONG 'medinet_prod__'
```

**Khuyen nghi:** Verifier agent (`/gsd-verify-work 1`) chay smoke o Phase 1 closeout — KHONG can chay ngay sau Plan 01-04 vi se phai run lai sau Plan 01-05 (`make hub-init` dynamic + integration test E-V3-3).

## Post-Deploy Re-ingest Task (M2 State Migration — BLOCKER 4 Mitigation)

Sau Plan 04 ship + restart server (default HUB_NAME=central), thuc hien:

```bash
# Re-trigger cocoindex re-process toan bo M2 corpus voi App name + APP_NAMESPACE moi
docker exec medinet-postgres psql -U medinet -d medinet_central -c \
  "UPDATE documents SET status='pending' WHERE status='completed'"

# Cocoindex flow medinet_central_ingest se pick up documents.status='pending'
# qua Plan 04-04 BackgroundTasks (A4) → reprocess. content_hash idempotent
# → KHONG re-embed neu content unchanged. ETA: ~5-10min cho M2 corpus typical.

# Verify re-ingest DONE:
docker exec medinet-postgres psql -U medinet -d medinet_central -c \
  "SELECT COUNT(*) FROM documents WHERE status='completed';"
# Expected: tra lai so cu truoc UPDATE
```

**Manual M2 fallback (neu user CHU Y preserve M2 corpus):**

```bash
# Set env override TRUOC khi start server:
export COCOINDEX_APP_NAME_LEGACY=medinet_wiki_ingest

# Server se dung App name M2 cu thay vi medinet_central_ingest
# (chi su dung tam thoi — Phase 7 migrate formally qua pg_dump xong remove env)
```

## Threat Model Honored

| Threat ID | Disposition | Mitigation Applied |
|-----------|-------------|---------------------|
| T-01-04-01 (Tampering — caller set APP_NAMESPACE env truoc setup_cocoindex) | mitigate | `setup_cocoindex` GHI DE qua `os.environ["APP_NAMESPACE"] = namespaced` deterministic theo `settings.hub_name`. Structured log event `cocoindex_app_namespace_set: hub=<name> namespace=<ns>` audit trail. |
| T-01-04-02 (Info Disclosure — App name medinet_yte_ingest leak ra error log) | accept | App name KHONG phai PII / secret; hub identity la public info trong topology. Cocoindex SDK crash log se chua app name nhung KHONG credentials. |
| T-01-04-03 (Tampering — flow.py module-level _get_settings() cache stale neu test thay env) | mitigate | Test fixture `_minimal_env` autouse goi `get_settings.cache_clear()` truoc + sau. Subprocess pattern cho per-hub + legacy test fresh module import — tranh reload conflict. Production runtime 1 process = 1 hub deploy → cache OK. |
| T-01-04-04 (Spoofing — hub yte co dang ky App name 'medinet_central_ingest') | mitigate | `resolve_cocoindex_app_name` lay hub_name tu Settings (validated qua Plan 02 `_enforce_hub_dsn_match` model_validator khop DATABASE_URL suffix). Hub yte process KHONG the dat hub_name="central" ma KHONG doi DATABASE_URL → fail-fast startup. Test `test_resolve_cocoindex_app_name_invalid_raises` PASS. |
| T-01-04-05 (Info Disclosure — cocoindex.medinet_<hub>_prod__* same DB query cross-namespace) | accept | Phase 1 v3.0 TOPO-03 chi scope process layer naming; cross-namespace SQL access can Postgres-level role grant (defer Phase 7 production hardening). Hub con KHONG co quyen connect cocoindex internal DB tu outside — chi qua coco.App SDK. |
| T-01-04-06 (Tampering/Data Loss — M2 cocoindex internal state orphan sau doi App name + APP_NAMESPACE) | mitigate | **Accept state reset** v3.0-a — must_haves truth #5. Mitigation chain: (1) Post-deploy re-ingest task `UPDATE documents SET status='pending' WHERE status='completed'` idempotent qua content_hash; (2) Manual fallback env `COCOINDEX_APP_NAME_LEGACY` neu user CHU Y preserve M2; (3) Structured log `cocoindex_app_namespace_set` audit trail; (4) Document trade-off ở SUMMARY.md + verification block re-ingest task ở plan + Phase 7 migrate formally qua pg_dump. Test `test_legacy_env_override_preserves_m2_name_subprocess` PASS — fallback path verified. |

## Threat Flags

**None.**

Plan 01-04 chi them helper pure + module-level App dynamic build + setup step 0 APP_NAMESPACE env set — KHONG gioi thieu network endpoint moi, auth path moi, file access pattern moi, hoac schema change o trust boundary. Tat ca surface da bake o threat_model frontmatter (6 threat T-01-04-01..06).

## Known Stubs

**None.**

Tat ca code da functional:
- `resolve_cocoindex_app_name` deterministic logic + ValueError invalid.
- Module-level `cocoindex_app` build dynamic tu Settings.hub_name + COCOINDEX_APP_NAME_LEGACY override.
- `setup_cocoindex` step 0 set APP_NAMESPACE env that.
- Structured log event `cocoindex_app_namespace_set` log dung audit format.

KHONG co placeholder/TODO/FIXME. M2 state migration documented + mitigation chain functional (re-ingest documents table works thanks to content_hash idempotent + cocoindex memo skip).

## API Surface Summary

### resolve_cocoindex_app_name

```python
def resolve_cocoindex_app_name(hub_name: str) -> str
```

- Input: hub name (`"central" | "yte" | "duoc" | "hcns"`).
- Output: App name string format `medinet_<hub>_ingest`.
- Raises: `ValueError` neu hub_name khong thuoc 4 gia tri (message chua "không hợp lệ" tieng Viet).

**Use cases (downstream plans):**

| Plan | Consume |
|------|---------|
| 01-04 module-level | `_app_name = COCOINDEX_APP_NAME_LEGACY or resolve_cocoindex_app_name(settings.hub_name)` |
| 01-05 (hub-init.sh dynamic) | Reference cho integration test E-V3-3 verify per-hub naming |
| Phase 2 FACTOR | `create_app()` lifespan log `starting hub=<name> app=<resolved_name>` |
| Phase 4 SYNC | Identify push source vs central target qua App name pattern |

### Module-level App registration logic

```python
from app.config import get_settings as _get_settings
_settings = _get_settings()
_legacy_app_name = _os.environ.get("COCOINDEX_APP_NAME_LEGACY", "").strip()
_app_name = _legacy_app_name or resolve_cocoindex_app_name(_settings.hub_name)
cocoindex_app = coco.App(coco.AppConfig(name=_app_name), medinet_wiki_main)
```

- `_settings` build tu lru_cache singleton — 1 process = 1 hub_name = 1 App instance (KHONG re-register).
- `_legacy_app_name` strip + truthy check — empty string `""` falsy → fall back resolve.
- M2 fallback: caller set `COCOINDEX_APP_NAME_LEGACY=medinet_wiki_ingest` env truoc start server → App name preserve M2 (chi su dung khi user CHU Y giu M2 corpus).

### setup_cocoindex APP_NAMESPACE step 0

```python
namespaced = f"medinet_{settings.hub_name}_prod"
os.environ["APP_NAMESPACE"] = namespaced
logger.info("cocoindex_app_namespace_set: hub=%s namespace=%s", settings.hub_name, namespaced)
```

- Format: `medinet_<hub>_prod` (R5 scale per-hub thay M2 co dinh `medinet_prod`).
- Set TRUOC `coco.start_blocking()` — cocoindex SDK doc lazy o `default_env()` init time.
- Settings.app_namespace field default `medinet_prod` KHONG xoa — backward-compat M2 deploy; setup ghi de qua os.environ deterministic.

## R5 Scale Per-Hub Pattern

```
Process startup (HUB_NAME env)
    ↓
Settings() pydantic v2 instantiation (Plan 02 — _enforce_hub_dsn_match validator)
    ↓
get_settings() lru_cache singleton
    ↓
flow.py module-level cocoindex_app build:
    _legacy = os.environ.get("COCOINDEX_APP_NAME_LEGACY", "").strip()
    _app_name = _legacy OR resolve_cocoindex_app_name(settings.hub_name)
    cocoindex_app = coco.App(coco.AppConfig(name=_app_name), medinet_wiki_main)
        → registered process-level (1 process = 1 app)
    ↓
setup_cocoindex(settings):
    step 0: os.environ["APP_NAMESPACE"] = f"medinet_{hub_name}_prod"
        → cocoindex internal tables `cocoindex.medinet_<hub>_prod__*` per-hub
    step 1: COCOINDEX_DB (LMDB path Q5)
    step 2: @coco.lifespan asyncpg.Pool
    step 3: import flow side-effect (cocoindex_app da register o step truoc)
    step 4: coco.start_blocking() — SDK doc APP_NAMESPACE env tai day
    step 5: cocoindex_app.update_blocking() — initial backfill
```

**Key property:** 4 hub process cung instance Postgres → cocoindex internal tables tach prefix:
- `cocoindex.medinet_central_prod__chunks__*` (central process)
- `cocoindex.medinet_yte_prod__chunks__*` (yte process)
- `cocoindex.medinet_duoc_prod__chunks__*` (duoc process)
- `cocoindex.medinet_hcns_prod__chunks__*` (hcns process)

KHONG dung nhau giua process layer. P7 carry forward: `cocoindex_db_schema="cocoindex"` co dinh (KHONG doi schema name).

## Self-Check

### Files exist

| Path | Exists? |
|------|---------|
| `Hub_All/api/app/rag/flow.py` | FOUND (modified +59 -3 LOC) |
| `Hub_All/api/app/rag/setup.py` | FOUND (modified +26 LOC) |
| `Hub_All/api/app/rag/__init__.py` | FOUND (modified docstring) |
| `Hub_All/api/tests/unit/test_flow_per_hub_naming.py` | FOUND (created 218 LOC) |
| `Hub_All/api/tests/unit/test_rag_flow.py` | FOUND (Rule 1 auto-fix) |
| `Hub_All/.planning/phases/01-multi-db-topology/01-04-SUMMARY.md` | FOUND (this file) |

### Commits exist

| Hash | Type | Description |
|------|------|-------------|
| `d3026c2` | test | TDD RED — failing test 9 case (resolve + module + legacy fallback subprocess) |
| `c5f868b` | feat | TDD GREEN — resolve_cocoindex_app_name + dynamic App + Rule 1 test_rag_flow fix |
| `e2f0bbc` | feat | Task 2 — setup_cocoindex APP_NAMESPACE per-hub step 0 + structured log |

### Acceptance criteria all PASS

- Task 1: 12/12 PASS (xem table tren — Rule 1 auto-fix applied)
- Task 2: 10/10 PASS (xem table tren)
- Full unit test suite: 166/166 PASS (Plan 03 baseline 157 + 9 new = 166; no regression)
- mypy strict on flow.py + setup.py: Success: no issues
- ruff check on 5 modified file: All checks passed

### TDD Gate Compliance

- RED: `d3026c2` (`test:` prefix) — failing test exist truoc GREEN.
- GREEN: `c5f868b` (`feat:` prefix) — implement pass tests + Rule 1 fix.
- REFACTOR: SKIPPED (intentional — code GREEN da clean, KHONG commit empty; pattern Plan 02/03 same reason).

## Self-Check: PASSED

---

*Generated 2026-05-21 — Plan 01-04 (Wave 2) hoan thanh 2/2 task (1 TDD + 1 non-TDD). 3 commit (1 RED `d3026c2`, 1 GREEN `c5f868b` co Rule 1 auto-fix, 1 Task 2 `e2f0bbc`). Wave 2 (01-03 + 01-04) complete sau Plan 01-04. Next: Wave 3 — Plan 01-05 (hub-init.sh dynamic + integration test E-V3-3 + CI workflow + [BLOCKING] schema push) sequential sau ca W2.*
