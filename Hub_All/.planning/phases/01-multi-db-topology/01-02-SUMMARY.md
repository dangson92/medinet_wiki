---
phase: 01-multi-db-topology
plan: 02
subsystem: multi-db-topology
tags:
  - settings
  - hub-isolation
  - asyncpg
  - pydantic-settings
  - topo-04
  - tdd
requirements:
  - TOPO-04
dependency_graph:
  requires:
    - "Plan 01-01 — Postgres 4 DB nghiep vu (medinet_central + medinet_hub_{yte,duoc,hcns}) san sang lam DSN target"
  provides:
    - "Settings.hub_name: Literal[4 gia tri] doc tu env HUB_NAME (default 'central')"
    - "Settings._enforce_hub_dsn_match validator fail-fast neu DATABASE_URL khong khop hub_name (E-V3-3)"
    - "resolve_database_url(base_dsn, hub_name) helper deterministic — central → medinet_hub_<name>"
    - "Test fixture central_sync_url pattern (rsplit/medinet_central) cho test integration tuong lai"
  affects:
    - "Plan 01-03 (per-hub Alembic env.py) — consume settings.database_url da validated qua -x hub=<name>"
    - "Plan 01-04 (cocoindex flow per-hub) — consume settings.hub_name de set APP_NAMESPACE + flow name"
    - "Plan 01-05 (hub-init.sh dynamic) — consume resolve_database_url helper de tao DSN per-hub on-the-fly"
    - "Phase 2 FACTOR — create_app() lifespan log 'starting hub=<name>' (T-01-02-05 accept)"
tech_stack:
  added: []
  patterns:
    - "pydantic v2 model_validator(mode='after') — fail-fast DSN suffix check sau khi tat ca field-level validator chay xong"
    - "Literal[4 gia tri] restrict input + default 'central' giu M2 backward-compat"
    - "DSN query string strip pattern (split('?', 1)[0]) — production DSN co ?sslmode=require"
    - "Test fixture central_sync_url swap (rsplit('/', 1)[0] + '/medinet_central') — preserve testcontainer cred + port"
key_files:
  created:
    - "Hub_All/api/tests/unit/test_config_hub_name.py — 11 test case TDD"
    - "Hub_All/.planning/phases/01-multi-db-topology/01-02-SUMMARY.md"
  modified:
    - "Hub_All/api/app/config.py — them hub_name field + model_validator + resolve_database_url helper"
    - "Hub_All/api/.env.example — them HUB_NAME placeholder + 4 hub DATABASE_URL pattern"
    - "Hub_All/api/app/db/session.py — verify-only (commit empty record gate)"
    - "Hub_All/api/tests/conftest.py — fix regression DATABASE_URL stub /test → /medinet_central"
    - "Hub_All/api/tests/integration/conftest.py — fix regression postgres_container CREATE DATABASE medinet_central + 3 fixture swap DSN"
decisions:
  - "Pydantic v2 model_validator(mode='after') thay vi field_validator vi can cross-field check (hub_name + database_url)"
  - "Strip query string truoc khi check DSN suffix — preserve compat voi DSN production co ?sslmode=require"
  - "Default hub_name='central' giu M2 backward-compat — KHONG bat operator bat buoc set HUB_NAME khi deploy don"
  - "Test refactor sang monkeypatch.setenv() pattern thay vi Settings(**kwargs) direct — pydantic-settings __init__ co special internal kwargs, mypy strict reject 64 error"
  - "Tao DB medinet_central trong postgres_container fixture (scope=module) thay vi rebuild image — cheap (1 lan per module), khong anh huong scope=function alembic_cfg performance"
  - "Skip REFACTOR commit cua TDD task — code GREEN da clean (validator + helper docstring day du, KHONG duplication, mypy + ruff clean)"
metrics:
  duration: ~30 min
  completed_date: "2026-05-21"
  tasks_completed: 3
  files_modified: 5
  files_created: 2
  commits: 5
---

# Phase 1 Plan 02: Settings.hub_name + DSN Validator + Per-hub Resolver Summary

**One-liner:** Settings extend voi field `hub_name: Literal["central","yte","duoc","hcns"]` doc tu env `HUB_NAME` (default "central") + `model_validator(mode="after")` E-V3-3 enforce DATABASE_URL suffix khop hub_name (fail-fast startup, KHONG defer runtime, KHONG fallback central) + helper `resolve_database_url(base_dsn, hub_name)` deterministic preserve query string; foundation cho Plan 03 Alembic per-hub + Plan 04 cocoindex flow per-hub + Plan 05 hub-init.sh dynamic.

## Objective

TOPO-04 — `Settings` layer foundation cho v3.0 Multi-Hub Split: 1 codebase deploy nhieu lan voi `HUB_NAME=<name>` env, moi process ket noi DUY NHAT 1 DB hub dung — KHONG fallback central, KHONG cross-hub access tu process layer. Mitigation T-01-02-01..03 (Spoofing/Info Disclosure/EoP) qua validator fail-fast; T-01-02-04 (Tampering helper) qua `ValueError` neu base_dsn sai.

## Tasks Completed

### Task 1 (TDD): Them Settings.hub_name + resolve_database_url + validator

**TDD gate sequence:**

| Gate | Commit | Description |
|------|--------|-------------|
| RED | `624bfb7` | `test(01-02): them failing test Settings.hub_name + resolve_database_url (TDD RED)` — 11 test case (8 core + 3 bonus) collection ImportError vi `resolve_database_url` chua ton tai |
| GREEN | `1051f67` | `feat(01-02): them Settings.hub_name + DSN validator + resolve_database_url (TDD GREEN)` — implement Settings.hub_name + model_validator + helper → 11/11 PASS |
| REFACTOR | SKIPPED | Code GREEN da clean (validator + helper docstring day du, mypy strict + ruff clean, KHONG duplication) — KHONG tao commit refactor empty |

**Files modified/created:**
- `Hub_All/api/app/config.py`:
  - Import `model_validator` tu pydantic.
  - Field `hub_name: Literal["central","yte","duoc","hcns"] = "central"` — chen sau `log_format` field.
  - Method `_enforce_hub_dsn_match` — `@model_validator(mode="after")` raise `ValueError` neu DSN suffix khong khop hub_name. Strip query string truoc khi check.
  - Module-level function `resolve_database_url(base_dsn, hub_name) -> str` — no-op khi hub_name='central'; swap segment medinet_central → medinet_hub_<name>; preserve query string; raise ValueError neu base_dsn khong ket thuc /medinet_central.
- `Hub_All/api/tests/unit/test_config_hub_name.py` (CREATED, 192 LOC):
  - 11 test case (8 core theo plan + 3 bonus coverage: query string, invalid base_dsn, query preserve resolve).
  - Pattern `monkeypatch.setenv()` + `Settings()` (KHONG direct kwargs — mypy strict reject pydantic-settings special internal kwargs).
  - Helper `_set_env()` deduplication setenv + cache_clear pattern.

### Task 2: Update .env.example voi HUB_NAME + 4 hub DATABASE_URL pattern

**Commit:** `19ede25` — `feat(01-02): them HUB_NAME + 4 hub DATABASE_URL pattern vao .env.example`

**File modified:**
- `Hub_All/api/.env.example`:
  - Them block "Hub identity (v3.0 Phase 1 TOPO-04)" o dau file (truoc Postgres block) — operator setup gap HUB_NAME truoc.
  - `HUB_NAME=central` default.
  - Comment liet ke 4 hub khop voi Settings.hub_name Literal restrict.
  - Update comment canh DATABASE_URL liet ke 4 pattern theo HUB_NAME — nhac operator E-V3-3 enforce.

**W10 fix (DRY):** Plan 02 KHONG hard-code secret pattern regex (`sk-...|AIza...|AKIA...`) — single source of truth la `.github/workflows/lint.yml` secret-detection job. Placeholder `medinet_dev_pwd` ro rang KHONG phai secret that.

### Task 3: Verify db/session.py thuan settings.database_url khong drift

**Commit:** `76538ce` — `docs(01-02): verify db/session.py thuan settings.database_url khong drift` (empty commit record gate, Plan 01-01 Task 2 da set tien le).

**File verified (KHONG sua):**
- `Hub_All/api/app/db/session.py`:
  - `init_engine(settings)` dung `settings.database_url` tu Settings (KHONG hardcode DSN).
  - Singleton pattern `_engine` global — OK voi 1 process = 1 hub deploy.
  - KHONG co branch `if settings.hub_name == ...` o session.py (validator o Settings da enforce).
  - KHONG co fallback `or settings.cocoindex_database_url`.

## Files Modified

| File | Change | LOC delta |
|------|--------|-----------|
| `Hub_All/api/app/config.py` | Add hub_name field + model_validator + resolve_database_url helper | +88 / -1 |
| `Hub_All/api/.env.example` | Add HUB_NAME block + DATABASE_URL pattern comment | +15 / -0 |
| `Hub_All/api/tests/unit/test_config_hub_name.py` | CREATE — 11 test case TDD | +192 (new) |
| `Hub_All/api/tests/conftest.py` | Fix regression _env fixture DSN stub | +8 / -1 |
| `Hub_All/api/tests/integration/conftest.py` | Fix regression postgres_container + 3 fixture DSN swap | +60 / -10 |
| `Hub_All/api/app/db/session.py` | Verify-only (KHONG sua) | 0 / 0 |

## Acceptance Criteria Met

### Task 1 (9/9 PASS)

| # | Criterion | Expected | Actual | Status |
|---|-----------|----------|--------|--------|
| 1 | `grep -c "hub_name: Literal" app/config.py` | ≥ 1 | 1 | PASS |
| 2 | `grep -c "model_validator" app/config.py` | ≥ 1 | 2 (import + decorator) | PASS |
| 3 | `grep -c "def resolve_database_url" app/config.py` | ≥ 1 | 1 | PASS |
| 4 | `grep -c "DSN mismatch hub_name" app/config.py` | ≥ 1 | 1 | PASS |
| 5 | `grep -c "medinet_hub_" app/config.py` | ≥ 1 | 7 | PASS |
| 6 | `grep -c "def test_" test_config_hub_name.py` | ≥ 8 | 11 | PASS |
| 7 | `uv run pytest tests/unit/test_config_hub_name.py -v` | 8/8 PASS | 11/11 PASS | PASS |
| 8 | `uv run mypy app/config.py` | exit 0 | Success: no issues | PASS |
| 9 | `uv run ruff check app/config.py tests/unit/test_config_hub_name.py` | exit 0 | All checks passed | PASS |

### Task 2 (4/4 PASS — W10 fix applied)

| # | Criterion | Expected | Actual | Status |
|---|-----------|----------|--------|--------|
| 1 | `grep -c "^HUB_NAME=" .env.example` | ≥ 1 | 1 | PASS |
| 2 | `grep -cE "medinet_hub_yte|medinet_hub_duoc|medinet_hub_hcns" .env.example` | ≥ 1 | 6 | PASS |
| 3 | `grep -c "^DATABASE_URL=" .env.example` | ≥ 1 | 1 (giu existing) | PASS |
| 4 | `grep -c "medinet_dev_pwd" .env.example` | ≥ 1 | 3 | PASS |

**W10 delegate:** secret detection KHONG hard-code regex — single source of truth `.github/workflows/lint.yml` CI gate.

### Task 3 (6/6 PASS)

| # | Criterion | Expected | Actual | Status |
|---|-----------|----------|--------|--------|
| 1 | `grep -c "settings.database_url" app/db/session.py` | ≥ 1 | 1 | PASS |
| 2 | `grep -c "create_async_engine" app/db/session.py` | ≥ 1 | 2 | PASS |
| 3 | `grep -c "if.*hub_name" app/db/session.py` | == 0 | 0 | PASS |
| 4 | `grep -c "or settings.cocoindex" app/db/session.py` | == 0 | 0 | PASS |
| 5 | `uv run mypy app/db/session.py` | exit 0 | Success: no issues | PASS |
| 6 | `uv run ruff check app/db/session.py` | exit 0 | All checks passed | PASS |

### Integration smoke (recommend — KHONG bat buoc trong plan scope)

```bash
HUB_NAME=yte DATABASE_URL=postgresql+asyncpg://u:p@h:5432/medinet_central \
  uv run python -c "from app.config import Settings; Settings()"
# Output: ValidationError "DSN mismatch hub_name: HUB_NAME='yte' yeu cau
# database 'medinet_hub_yte' nhung DATABASE_URL tro 'medinet_central'.
# E-V3-3 enforce — KHONG fallback central."
```

**Verified manual run:** PASS — exception raise dung message, fail-fast TRUOC ket noi DB.

## Key Decisions

1. **pydantic v2 `model_validator(mode='after')` thay vi `field_validator`:** Validator can cross-field check (hub_name + database_url) → `field_validator` chi access 1 field tai 1 thoi diem. `model_validator(mode='after')` chay sau khi tat ca field-level validator xong → access `self.hub_name` + `self.database_url` an toan.

2. **Strip query string truoc check DSN suffix:** Production DSN thuong co `?sslmode=require` hoac tham so connection pool. Logic `self.database_url.split("?", 1)[0].rstrip("/")` cho phep DSN co query van validate dung. Bonus test `test_dsn_with_query_string_validates` cover.

3. **Default `hub_name="central"` giu M2 backward-compat:** Operator dang deploy M2 don le (1 instance Postgres + 1 DB medinet_central) KHONG can set env HUB_NAME → default central → DSN suffix khop medinet_central → validator pass. Khi deploy multi-hub se phai set HUB_NAME=<name> + DATABASE_URL=<dsn> tuong ung.

4. **Test refactor sang `monkeypatch.setenv()` pattern:** pydantic-settings `__init__` co special internal kwargs (`_case_sensitive`, `_env_file`, `_secrets_dir`, ...) → kwargs user trung ten field bi mypy reject voi 64 error type union. Refactor sang env-based pattern consistent voi conftest.py va cac test khac trong `api/tests/`.

5. **Tao DB `medinet_central` trong `postgres_container` fixture:** Testcontainer auto-create DB ten `test` (POSTGRES_DB default). Tao them DB `medinet_central` + enable ext `vector + pgcrypto` ngay sau khi container start → cheap (1 lan per module scope), KHONG anh huong scope=function `alembic_cfg` performance. Test fixture co the doi DSN sang `/medinet_central` qua `sync_url.rsplit("/", 1)[0] + "/medinet_central"` ma KHONG rebuild image.

6. **Skip REFACTOR commit cua TDD task:** Code GREEN da clean — validator + helper docstring day du, mypy strict + ruff clean tu lan dau, KHONG duplication. Theo TDD discipline, REFACTOR phase optional — KHONG tao commit empty record gate (chi commit khi co code change thuc te). Khac voi Task 3 verify-only (record gate atomic per-task la bat buoc theo executor protocol).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed test fixture regression do validator moi**

- **Found during:** Sau khi commit GREEN Task 1, chay `uv run pytest tests/unit/` phat hien 7 test FAIL (1 test_lifespan_calls_configure_structlog_idempotent + 6 test_watchdog tests).
- **Issue:** Validator `_enforce_hub_dsn_match` yeu cau `DATABASE_URL` ket thuc `/medinet_central` (HUB_NAME=central default). `tests/conftest.py` autouse `_env` fixture set stub `DATABASE_URL=postgresql+asyncpg://test:test@localhost:5432/test` → DB name `test` → validator raise `ValidationError` → test import `app.main` hoac instantiate Settings deu fail.
- **Fix:** 
  - `tests/conftest.py` — doi stub DSN tu `/test` sang `/medinet_central` (vo hai vi test cu khong dung Postgres that).
  - `tests/integration/conftest.py` — `postgres_container` fixture them buoc CREATE DATABASE `medinet_central` + enable ext; 3 fixture (`alembic_cfg`, `auth_env`, `app_with_auth`) swap DSN tu container default (`/test`) sang `/medinet_central` qua `sync_url.rsplit("/", 1)[0] + "/medinet_central"`.
- **Files modified:** `tests/conftest.py`, `tests/integration/conftest.py`.
- **Commit:** `db4dd3d` — `refactor(01-02): cap nhat test fixtures cho Settings validator + mypy strict`.
- **Verification:** Sau fix `uv run pytest tests/unit/` → 147/147 PASS.

**2. [Rule 1 - Bug] Refactor test_config_hub_name.py tu kwargs sang env pattern**

- **Found during:** Chay `uv run mypy tests/unit/test_config_hub_name.py` lan dau.
- **Issue:** Pattern `Settings(**VALID_BASE)` direct kwargs raise 64 mypy error vi pydantic-settings `__init__` co special internal kwargs (`_case_sensitive`, `_env_file`, `_secrets_dir`, ...) — mypy KHONG reconcile duoc voi user kwargs trung ten field.
- **Fix:** Refactor 11 test tu `Settings(hub_name="yte", database_url="...", **VALID_BASE)` sang `monkeypatch.setenv("HUB_NAME", "yte") + monkeypatch.setenv("DATABASE_URL", "...") + get_settings.cache_clear() + Settings()`. Tao helper `_set_env()` deduplicate boilerplate.
- **Files modified:** `tests/unit/test_config_hub_name.py` (cung commit `db4dd3d` voi deviation #1).
- **Verification:** Sau refactor `uv run mypy tests/unit/test_config_hub_name.py` → Success: no issues; `uv run pytest` → 11/11 PASS giu nguyen.

**Khong co deviation Rule 2/3/4** — KHONG missing critical functionality (validator + helper + .env.example da day du), KHONG blocking issue moi, KHONG architectural change.

## Authentication Gates

**None encountered.**

Plan 01-02 thuan tuy code-level Settings extend + test fixture fix — KHONG can credential/secret/auth.

## Threat Model Honored

| Threat ID | Disposition | Mitigation Applied |
|-----------|-------------|---------------------|
| T-01-02-01 (Spoofing — HUB_NAME=yte + DSN central) | mitigate | `_enforce_hub_dsn_match` raise ValidationError. Test `test_yte_mismatch_central_raises` PASS. |
| T-01-02-02 (Info Disclosure — cross-hub DSN typo) | mitigate | Validator check DSN suffix khop `medinet_hub_<hub_name>`. Test `test_duoc_mismatch_yte_dsn_raises` PASS. |
| T-01-02-03 (EoP — hub con co y trо central) | mitigate | DB-level isolation Plan 01-01 (DB rieng); validator enforce DSN match — neu attacker doi DATABASE_URL → ops audit. Production grant defer Phase 7. |
| T-01-02-04 (Tampering — resolve_database_url base_dsn sai) | mitigate | Helper raise `ValueError` neu `base_dsn` khong ket thuc `/medinet_central`. Test `test_resolve_database_url_invalid_base_raises` PASS. |
| T-01-02-05 (Repudiation — KHONG log hub_name startup) | accept | Log hub_name o Phase 2 FACTOR-01 create_app lifespan ("starting hub=<name>") — ngoai scope Plan 01-02. |

## Threat Flags

**None.**

Plan 01-02 chi them Settings field + validator + helper module-level + cap nhat test fixture — KHONG gioi thieu network endpoint moi, auth path moi, file access pattern moi, hoac schema change o trust boundary. Tat ca surface da bake o threat_model frontmatter.

## Known Stubs

**None.**

Tat ca code da functional:
- `Settings.hub_name` field doc env that.
- `_enforce_hub_dsn_match` validator raise validation error that.
- `resolve_database_url` helper deterministic, no placeholder.
- `.env.example` co HUB_NAME placeholder ro rang (operator dien gia tri thuc te khi deploy).

## API Surface Summary

### Settings.hub_name

```python
hub_name: Literal["central", "yte", "duoc", "hcns"] = "central"
```

- Doc tu env `HUB_NAME`.
- 4 gia tri Literal restrict — hub moi phai update Literal o Plan 05 (KHONG dynamic).
- Default "central" giu M2 backward-compat.

### Settings._enforce_hub_dsn_match

```python
@model_validator(mode="after")
def _enforce_hub_dsn_match(self) -> Settings:
    """E-V3-3 enforce — DSN suffix khop hub_name. Fail-fast startup."""
```

- Strip query string truoc check (`?sslmode=...` OK).
- Expected: `central → /medinet_central`, `<hub> → /medinet_hub_<hub>`.
- Error message: `f"DSN mismatch hub_name: HUB_NAME={...} yeu cau database {...} nhung DATABASE_URL tro {...}. E-V3-3 enforce — KHONG fallback central."`

### resolve_database_url

```python
def resolve_database_url(base_dsn: str, hub_name: str) -> str:
```

- `hub_name == "central"` → no-op (tra `base_dsn` nguyen).
- `hub_name != "central"` → swap segment `medinet_central` → `medinet_hub_<hub_name>`.
- Preserve query string (`?sslmode=require` giu nguyen).
- Raise `ValueError` neu `base_dsn` khong ket thuc `/medinet_central`.

**Use cases (downstream plans):**

| Plan | Consume |
|------|---------|
| 01-03 (Alembic per-hub) | `alembic -x hub=<name>` doc settings → resolve DSN per-hub tu central base |
| 01-04 (cocoindex flow per-hub) | `setup_cocoindex(settings)` doc `settings.hub_name` → flow name `medinet_<hub>_ingest` |
| 01-05 (hub-init.sh dynamic) | `make hub-init HUB=<name>` script call `resolve_database_url` Python helper tu shell |

## E-V3-3 Fail-Fast Pattern

```
Process startup (HUB_NAME env)
    ↓
Settings() pydantic v2 instantiation
    ↓
field_validator (cors_allowed_origins _parse_csv mode=before)
    ↓
field_validator (cors_allowed_origins _no_lan_in_prod mode=after)
    ↓
**model_validator(mode='after') _enforce_hub_dsn_match** ← E-V3-3 gate
    ├─ DSN match → return self → get_settings() cached
    └─ DSN mismatch → raise ValueError → process exit (KHONG accept request)
```

**Key property:** Validator chay TRUOC bat ky request handler nao. Process KHONG accept HTTP request neu config sai → KHONG co "silent run sai data" window.

## W10 Fix Applied (DRY)

Acceptance criteria Plan 02 KHONG hard-code secret pattern regex (`sk-...|AIza...|AKIA...`). Single source of truth = `.github/workflows/lint.yml` secret-detection job. Local Plan 02 verify chi:
- `^HUB_NAME=` ton tai (operator-facing setup)
- `medinet_hub_yte|duoc|hcns` mention (operator biet 4 hub khac DSN)
- `^DATABASE_URL=` giu existing
- `medinet_dev_pwd` placeholder ro rang (NOT real secret pattern)

CI lint workflow tu verify secret detection khi PR merge — KHONG duplicate pattern source of truth.

## Self-Check

### Files exist

| Path | Exists? |
|------|---------|
| `Hub_All/api/app/config.py` | FOUND (modified) |
| `Hub_All/api/.env.example` | FOUND (modified) |
| `Hub_All/api/app/db/session.py` | FOUND (verified, KHONG sua) |
| `Hub_All/api/tests/unit/test_config_hub_name.py` | FOUND (created) |
| `Hub_All/api/tests/conftest.py` | FOUND (modified Rule 1 fix) |
| `Hub_All/api/tests/integration/conftest.py` | FOUND (modified Rule 1 fix) |
| `Hub_All/.planning/phases/01-multi-db-topology/01-02-SUMMARY.md` | FOUND (this file) |

### Commits exist

| Hash | Type | Description |
|------|------|-------------|
| `624bfb7` | test | TDD RED — failing test 11 case |
| `1051f67` | feat | TDD GREEN — Settings.hub_name + validator + helper |
| `19ede25` | feat | Task 2 — .env.example HUB_NAME + 4 hub pattern |
| `76538ce` | docs | Task 3 — verify db/session.py (empty record gate) |
| `db4dd3d` | refactor | Deviation Rule 1 — fix test fixture regression + mypy strict |

### Acceptance criteria all PASS

- Task 1: 9/9 PASS (xem table tren)
- Task 2: 4/4 PASS (W10 fix applied)
- Task 3: 6/6 PASS
- Integration smoke: VERIFIED PASS (manual run)
- Full unit test suite: 147/147 PASS (no regression)
- mypy strict on 5 modified file: Success: no issues
- ruff check on 5 modified file: All checks passed

### TDD Gate Compliance

- RED: `624bfb7` (`test:` prefix) — failing test exist truoc GREEN.
- GREEN: `1051f67` (`feat:` prefix) — implement pass tests.
- REFACTOR: SKIPPED (intentional — code GREEN da clean, KHONG commit empty).

## Self-Check: PASSED

---

*Generated 2026-05-21 — Plan 01-02 (Wave 1) hoan thanh 3/3 task (1 TDD). 5 commit (1 RED, 1 GREEN, 2 task commit, 1 deviation fix). Next: Wave 2 — Plan 01-03 (per-hub Alembic env.py -x hub) + Plan 01-04 (cocoindex flow per-hub) parallel. Wave 1 cua Phase 1 complete sau Plan 01-02 (01-01 da xong commits e398a83/55856b9/8e06803).*
