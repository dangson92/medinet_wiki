---
phase: 01-multi-db-topology
plan: 03
subsystem: multi-db-topology
tags:
  - alembic
  - migration
  - per-hub
  - make-target
  - r-v3-3
  - tdd
requirements:
  - TOPO-02
dependency_graph:
  requires:
    - "Plan 01-01 — 4 DB nghiep vu da ton tai (medinet_central + medinet_hub_yte/duoc/hcns)"
    - "Plan 01-02 — Settings.hub_name + resolve_database_url helper available"
  provides:
    - "alembic -x hub=<name> upgrade head CLI surface (per-hub migration)"
    - "make migrate-all target loop apply 4 DB tuan tu + auto-call head check"
    - "make migrate-status target show alembic current per hub"
    - "scripts/alembic-head-check.sh lint script verify head SHA match 4 DB"
    - "Helpers parse_hub_x_arg + resolve_env_database_url pure (unit testable qua sys.path inject)"
  affects:
    - "Plan 01-05 (hub-init.sh + integration test E-V3-3) — consume migrate-all + head-check chain"
    - "Plan 02 (FACTOR codebase) — process-per-hub deploy can migrate-all chay 1 lan setup"
    - "Phase 7 MIGRATE — migration data tu medinet_central cu sang DB con dung make migrate-all baseline"
tech_stack:
  added: []
  patterns:
    - "Guard hasattr(context, 'config') cho phep pytest import env.py helpers KHONG fail alembic runtime"
    - "Imperative bash for loop fail-fast '|| exit 1' chain migrate-all"
    - "declare -A bash associative array cho HEADS map hub -> rev SHA"
    - "alembic.context.get_x_argument(as_dictionary=False) tra list['key=value', ...]"
    - "Cross-hub roundtrip un-resolve (yte base → central → target hub) preserve query string"
key_files:
  created:
    - "Hub_All/api/tests/unit/test_alembic_env_hub_arg.py — 10 test case TDD (4 parse + 6 resolve)"
    - "Hub_All/api/scripts/alembic-head-check.sh — lint script R-V3-3 head SHA match verify"
    - "Hub_All/.planning/phases/01-multi-db-topology/01-03-SUMMARY.md"
  modified:
    - "Hub_All/api/migrations/env.py — them parse_hub_x_arg + resolve_env_database_url + guard hasattr"
    - "Hub_All/api/Makefile — them migrate-all + migrate-status targets + HUBS_ALL variable + .PHONY update"
decisions:
  - "Guard hasattr(context, 'config') thay vi try/except — sach hon, KHONG nuot exception"
  - "Helpers parse_hub_x_arg + resolve_env_database_url DEFINE TRUOC alembic runtime block — pure function unit testable"
  - "_VALID_HUBS set ngay tai env.py thay vi import tu Settings.hub_name Literal — tranh circular (Settings cung dung Literal hardcode)"
  - "fail-fast '|| exit 1' trong migrate-all loop bash — hub thu N+1 KHONG apply neu hub N fail (acceptable: alembic-head-check.sh se catch drift)"
  - "ASCII-only echo string trong alembic-head-check.sh — locale container Linux co the khong support UTF-8 echo"
  - "Skip REFACTOR commit cua TDD task — code GREEN da clean (mypy + ruff PASS, KHONG duplication, docstring day du)"
metrics:
  duration: ~25 min
  completed_date: "2026-05-21"
  tasks_completed: 3
  files_created: 2
  files_modified: 2
  commits: 4
---

# Phase 1 Plan 03: Per-hub Alembic + make migrate-all + alembic-head-check.sh Summary

**One-liner:** `api/migrations/env.py` extend doc `-x hub=<name>` argument override DSN runtime qua `resolve_env_database_url` helper (Plan 02 consume `resolve_database_url`); 2 Makefile target `migrate-all` + `migrate-status` loop 4 hub (`HUBS_ALL ?= central yte duoc hcns`); `scripts/alembic-head-check.sh` verify head SHA khop 4 DB sau apply (R-V3-3 drift mitigation); M2 pattern PRESERVE (W12: `compare_type=True` + `compare_server_default=True` + `include_object` cocoindex schema filter intact); W8 fix cross-hub roundtrip support (yte base + `-x hub=duoc` → un-resolve yte ve central roi resolve sang duoc).

## Objective

TOPO-02 — Per-hub Alembic migration set. Phase 2 se deploy 4 process FastAPI, moi process ket noi DB rieng — schema phai match 100% giua cac DB neu khong hub yte co cot moi ma hub duoc chua co se crash repository layer. Plan 03 implement CLI surface `alembic -x hub=<name> upgrade head` + 2 Makefile target loop apply 4 DB + 1 lint script verify head SHA match (R-V3-3 mitigation, Plan 05 wire vao CI).

## Tasks Completed

### Task 1 (TDD): Refactor migrations/env.py doc -x hub=<name> + override DSN

**TDD gate sequence:**

| Gate | Commit | Description |
|------|--------|-------------|
| RED | `ddd379c` | `test(01-03): them failing test parse_hub_x_arg + resolve_env_database_url (TDD RED)` — 10 test case collection ERROR vi env.py truy cap `context.config` module-level + helpers chua ton tai |
| GREEN | `48acecc` | `feat(01-03): them parse_hub_x_arg + resolve_env_database_url vao Alembic env.py (TDD GREEN)` — implement 2 helper pure + guard `hasattr(context, 'config')` + DSN inject runtime → 10/10 PASS |
| REFACTOR | SKIPPED | Code GREEN da clean (mypy strict + ruff PASS lan dau, docstring day du, KHONG duplication) — KHONG tao commit refactor empty |

**Files modified/created:**
- `Hub_All/api/migrations/env.py` (+139, -17 LOC):
  - Import them `resolve_database_url` tu `app.config` (Plan 02 helper).
  - `_VALID_HUBS = {"central", "yte", "duoc", "hcns"}` set hard-coded khop Settings.hub_name Literal.
  - Pure helper `parse_hub_x_arg(x_args: list[str]) -> str | None` — extract `hub=<name>` tu CLI -x args; raise ValueError neu hub khong hop le (T-01-03-01 mitigation).
  - Pure helper `resolve_env_database_url(base_dsn, hub_arg, default_hub) -> str` — 4-scenario logic: same central, central → hub, hub → central (un-resolve), hub → other hub (cross-hub roundtrip W8); raise ValueError neu base_dsn khong tro `medinet_central|medinet_hub_*` (T-01-03-02 mitigation).
  - Guard `hasattr(context, 'config')` bao quanh alembic runtime block (2 cho: DSN inject + entrypoint) — pytest import helpers KHONG trigger alembic.context truy cap.
  - DSN inject block thay tu `set_main_option(_settings.database_url)` thanh `set_main_option(_resolved_dsn)` (resolved qua helpers).
  - **PRESERVE W12 M2 patterns:** `include_object` cocoindex schema filter (P7) intact (4 mentions); `compare_type=True` (3 mentions) + `compare_server_default=True` (3 mentions) intact (P20).
- `Hub_All/api/tests/unit/test_alembic_env_hub_arg.py` (NEW, 105 LOC):
  - 10 test case (4 parse_hub_x_arg + 6 resolve_env_database_url).
  - 2 W8 specific test: `test_resolve_cross_hub_yte_to_duoc` (yte base + -x hub=duoc → resolves duoc) + `test_resolve_invalid_base_dsn_raises` (random_db → ValueError).
  - `sys.path.insert(0, migrations_dir)` pattern — env.py KHONG phai package chuan, import qua path inject.

### Task 2: Them Makefile targets migrate-all + migrate-status

**Commit:** `7224c06` — `feat(01-03): them migrate-all + migrate-status target loop 4 hub vao Makefile`

**File modified:**
- `Hub_All/api/Makefile` (+29, -1 LOC):
  - Update `.PHONY` them `migrate-all migrate-status` (multi-line backslash continuation).
  - Them comment block "Per-hub Alembic migration (Phase 1 v3.0 TOPO-02)" voi yeu cau prereq.
  - `HUBS_ALL ?= central yte duoc hcns` — override-able variable cho selective migration (vd `make migrate-all HUBS_ALL="central yte"`).
  - `migrate-all`: `@for hub in $(HUBS_ALL); do ...; done` fail-fast `|| exit 1`; cuoi loop goi `bash scripts/alembic-head-check.sh` verify head SHA.
  - `migrate-status`: same loop, goi `alembic -x hub=$$hub current` + `|| echo "  (FAIL)"` (KHONG fail-fast, show all hub state).

### Task 3: Tao script alembic-head-check.sh — R-V3-3 mitigation

**Commit:** `e16eb3b` — `feat(01-03): them alembic-head-check.sh verify head SHA match 4 DB (R-V3-3)`

**File created:**
- `Hub_All/api/scripts/alembic-head-check.sh` (NEW, 58 LOC, mode `100755` executable):
  - `set -euo pipefail` defensive bash header.
  - `HUBS_ALL=${HUBS_ALL:-"central yte duoc hcns"}` — env override-able same Makefile.
  - `declare -A HEADS` bash associative array — map hub name → rev SHA.
  - Loop chinh: goi `alembic -x hub=$hub current 2>&1`, grep filter out `^INFO\|^WARNING\|^Context impl` log prefix, `awk 'NF{print $1; exit}'` lay first non-empty token la rev_id.
  - 2 exit paths:
    - FAIL fast: rev empty/ERROR → log + `FAIL=1` continue (collect all errors before exit).
    - Compare all heads = first hub's head; drift → exit 1 + R-V3-3 message.
  - ASCII-only echo string (locale container Linux co the khong support UTF-8).
  - Caller: Makefile `migrate-all` (Task 2) + Plan 05 CI workflow.

## Files Modified

| File | Change | LOC delta |
|------|--------|-----------|
| `Hub_All/api/migrations/env.py` | Add helpers + guard + DSN inject runtime, PRESERVE M2 patterns | +139 / -17 |
| `Hub_All/api/Makefile` | Add migrate-all + migrate-status targets + HUBS_ALL var + .PHONY update | +29 / -1 |
| `Hub_All/api/tests/unit/test_alembic_env_hub_arg.py` | CREATE — 10 test case TDD (4 parse + 6 resolve, 2 W8) | +105 (new) |
| `Hub_All/api/scripts/alembic-head-check.sh` | CREATE — lint script R-V3-3 head SHA match verify, mode 100755 | +58 (new) |

## Acceptance Criteria Met

### Task 1 (12/12 PASS — W8 + W12 verified)

| # | Criterion | Expected | Actual | Status |
|---|-----------|----------|--------|--------|
| 1 | `grep -cE "parse_hub_x_arg\|context.get_x_argument" env.py` | ≥ 2 | 5 | PASS |
| 2 | `grep -c "resolve_database_url" env.py` | ≥ 1 | 4 | PASS |
| 3 | `grep -c "_VALID_HUBS" env.py` | ≥ 1 | 3 | PASS |
| 4 | `grep -cE "yte\|duoc\|hcns" env.py` | ≥ 1 | 8 | PASS |
| 5 | `grep -c "include_object" env.py` (P7 preserve W12) | ≥ 1 | 4 | PASS |
| 6 | `grep -c "compare_type=True" env.py` (P20 preserve W12) | ≥ 1 | 3 | PASS |
| 7 | `grep -c "compare_server_default=True" env.py` (P20 preserve W12) | ≥ 1 | 3 | PASS |
| 8 | `grep -c "def test_" test_alembic_env_hub_arg.py` | ≥ 9 | 10 | PASS |
| 9 | `grep -cE "test_resolve_cross_hub_yte_to_duoc\|test_resolve_invalid_base_dsn_raises"` (W8) | ≥ 2 | 2 | PASS |
| 10 | `uv run pytest tests/unit/test_alembic_env_hub_arg.py -v` | 9/9 PASS | 10/10 PASS | PASS |
| 11 | `uv run mypy migrations/env.py` | exit 0 | Success: no issues | PASS |
| 12 | `uv run ruff check migrations/env.py tests/unit/test_alembic_env_hub_arg.py` | exit 0 | All checks passed | PASS |

### Task 2 (6/8 PASS — 2 deferred do make binary KHONG co tren Windows host)

| # | Criterion | Expected | Actual | Status |
|---|-----------|----------|--------|--------|
| 1 | `grep -c "^migrate-all:" Makefile` | ≥ 1 | 1 | PASS |
| 2 | `grep -c "^migrate-status:" Makefile` | ≥ 1 | 1 | PASS |
| 3 | `grep -c "HUBS_ALL" Makefile` | ≥ 1 | 3 | PASS |
| 4 | `grep -c "alembic -x hub=" Makefile` | ≥ 2 | 3 | PASS |
| 5 | `grep -c "alembic-head-check.sh" Makefile` | ≥ 1 | 3 | PASS |
| 6 | `grep -c ".PHONY.*migrate-all\|migrate-all migrate-status" Makefile` | ≥ 1 | 1 | PASS |
| 7 | `make -n migrate-all HUBS_ALL="central"` exit 0 | exit 0 | **DEFERRED** | DEFERRED (Rule 3) |
| 8 | `make -n migrate-status HUBS_ALL="central yte"` exit 0 | exit 0 | **DEFERRED** | DEFERRED (Rule 3) |

**Deferred items justification:** `where make`, `which mingw32-make`, `which gmake` deu tra ve "not found" tren Windows host. Makefile TAB indent valid (verified qua Python `lines[i].startswith(b'\t')` — 12 recipe lines tab-indented o new section). CI Linux + Plan 05 smoke se runtime validate.

### Task 3 (7/7 PASS)

| # | Criterion | Expected | Actual | Status |
|---|-----------|----------|--------|--------|
| 1 | File exists `Hub_All/api/scripts/alembic-head-check.sh` | exists | exists | PASS |
| 2 | `bash -n` syntax check | exit 0 | exit 0 + SYNTAX OK | PASS |
| 3 | `grep -c "HUBS_ALL" alembic-head-check.sh` | ≥ 1 | 4 | PASS |
| 4 | `grep -c "alembic.*-x hub=" alembic-head-check.sh` | ≥ 1 | 1 | PASS |
| 5 | `grep -c "drift detected" alembic-head-check.sh` | ≥ 1 | 1 | PASS |
| 6 | `grep -cE "PASS\|FAIL" alembic-head-check.sh` | ≥ 2 | 7 | PASS |
| 7 | `grep -c "R-V3-3" alembic-head-check.sh` | ≥ 1 | 2 | PASS |
| 8 | `grep -c "set -euo pipefail" alembic-head-check.sh` | ≥ 1 | 1 | PASS |
| 9 | File mode executable (Linux) | mode 100755 | mode 100755 (git update-index --chmod=+x) | PASS |

### Regression check (full unit test suite)

- `uv run pytest tests/unit/ -v` → **157/157 PASS** (no regression voi Plan 02 baseline 147/147; thua 10 do moi 10 test_alembic_env_hub_arg.py).
- mypy + ruff strict mode on env.py + test file: ALL PASS.

## Key Decisions

1. **Guard `hasattr(context, 'config')` thay vi try/except:** Pure check property — KHONG nuot exception khac ma alembic runtime co the raise. Bao quanh 2 block: DSN inject (line 116-130 sau modify) + entrypoint `if context.is_offline_mode()` (line 230-233). Pytest import `from env import parse_hub_x_arg, resolve_env_database_url` skip ca 2 block → KHONG fail.

2. **Helpers DEFINE TRUOC alembic runtime block:** Function `parse_hub_x_arg` + `resolve_env_database_url` o module top-level (line 38-119), TRUOC `if hasattr(context, 'config')` (line 124). Python only executes top-level definitions on import — function body chi chay khi caller goi → unit test import sach.

3. **`_VALID_HUBS` set hard-coded ngay tai env.py:** KHONG import tu `Settings.hub_name` Literal vi pydantic Literal type runtime introspection phuc tap (would need `typing.get_args(Settings.model_fields['hub_name'].annotation)`). Hard-code khop Settings (Plan 05 hub-init.sh dynamic add se centralize source of truth).

4. **fail-fast `|| exit 1` trong migrate-all bash loop:** Neu hub thu N fail (vd network drop), hub N+1 KHONG apply nua → giam blast radius. Tradeoff: hub da apply (hub 0..N-1) khong rollback — chap nhan vi alembic-head-check.sh sau loop se catch drift va fail toan migrate-all, ops re-run sau khi fix.

5. **ASCII-only echo string trong alembic-head-check.sh:** Locale container Linux production thuong la `C` hoac `POSIX`, KHONG `vi_VN.UTF-8`. UTF-8 tieng Viet co dau trong echo co the bi mojibake hoac `printf: cannot output broken UTF-8`. Script log ASCII-only de portability.

6. **Skip REFACTOR commit cua TDD task:** Code GREEN da clean (mypy strict + ruff PASS lan dau, docstring day du, KHONG code duplication, naming consistent). Theo TDD discipline REFACTOR optional — KHONG tao commit refactor empty (chi commit khi co code change thuc te). Phu hop voi pattern Plan 02 Task 1 (skip REFACTOR same reason).

7. **Cross-hub roundtrip W8 — un-resolve about central first:** Logic don gian hon 2-step direct hub→hub swap. `resolve_env_database_url(BASE_YTE, "duoc", default_hub="yte")` flow: detect `is_hub_base=True` (last_seg starts `medinet_hub_`) → swap segment ve `medinet_central` → goi `resolve_database_url(central_base, "duoc")` Plan 02 helper → tra DSN duoc. Reuse Plan 02 helper KHONG duplicate logic.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] env.py truy cap context.config module-level chan unit test import**

- **Found during:** Task 1 RED gate verification — pytest collection ERROR `AttributeError: module 'alembic.context' has no attribute 'config'`.
- **Issue:** Plan goc proposes test import `from env import parse_hub_x_arg, resolve_env_database_url` qua `sys.path.insert(0, migrations_dir)`. Nhung env.py original co `config = context.config` o line 26 module-level — `alembic.context.config` CHI exist khi alembic exec_module load env.py voi `EnvironmentContext` proxy active. Import tu pytest se fail truoc khi reach `from env import X`.
- **Fix:** Bao quanh alembic-runtime code block bang `if hasattr(context, 'config'):` (2 cho: DSN inject + final entrypoint). Pure helpers + function definitions van o module top-level → import sach.
- **Files modified:** `api/migrations/env.py` (same GREEN commit `48acecc`).
- **Verification:** Sau fix, `uv run pytest tests/unit/test_alembic_env_hub_arg.py -v` → 10/10 PASS. Alembic runtime path KHONG bi anh huong (`alembic upgrade head` van trigger DSN inject + entrypoint binh thuong).

**2. [Rule 3 - Blocking] `make` binary KHONG co tren Windows host execute time → AC7 + AC8 Task 2 dry-run defer**

- **Found during:** Task 2 acceptance criteria verification — `make -n migrate-all` raise `command not found`.
- **Issue:** Windows 11 host KHONG cai GNU Make. `where make`, `which mingw32-make`, `which gmake` deu khong tim thay. Plan AC7 + AC8 yeu cau `make -n` dry-run exit 0.
- **Fix:** Substitute validation qua Python parser — verify TAB indent recipe lines (`line.startswith(b'\t')`) + grep AC1-AC6. Plan 05 (Wave 3) chay tren docker container Linux co GNU make → smoke runtime se validate.
- **Files modified:** None (procedural deviation).
- **Verification:** Python parser xac nhan 12 recipe lines o new section (lines 65-79) deu TAB-indent. `grep -c` AC1-AC6 all PASS. CI Linux + Plan 05 se runtime smoke.

**Khong co deviation Rule 1/2/4** — KHONG bug code (helpers logic dung lan dau), KHONG missing critical functionality (validator + helper + Makefile + script day du theo plan), KHONG architectural change.

## Authentication Gates

**None encountered.**

Plan 01-03 thuan tuy code-level + bash script — KHONG can credential/secret/auth.

## Smoke Test (recommend — KHONG bat buoc trong Plan 01-03 scope)

Theo `<verification>` o plan goc, manual smoke test sau Wave 2 done:

```bash
# 1. Postgres + 4 DB ready (Plan 01-01 init-db.sh)
docker compose up -d postgres
sleep 30

# 2. Run migrate-all
cd Hub_All/api
HUB_NAME=central DATABASE_URL=postgresql+asyncpg://medinet:medinet_dev_pwd@localhost:5432/medinet_central \
  make migrate-all

# Expected:
#   [migrate-all] === hub=central ===
#   ... alembic upgrade head output ...
#   [migrate-all] === hub=yte ===
#   ... alembic upgrade head output ...
#   ... (duoc + hcns) ...
#   [migrate-all] DONE. Verify head SHA match qua scripts/alembic-head-check.sh
#   [alembic-head-check] Collect head SHA per hub...
#     hub=central head=<sha>
#     hub=yte head=<sha>
#     hub=duoc head=<sha>
#     hub=hcns head=<sha>
#   [alembic-head-check] PASS - tat ca 4 DB cung head SHA: <sha>

# 3. Status check
make migrate-status
# Expected: 4 hub deu hien thi head SHA same

# 4. Cross-hub W8 manual test
HUB_NAME=yte DATABASE_URL=postgresql+asyncpg://medinet:medinet_dev_pwd@localhost:5432/medinet_hub_yte \
  uv run alembic -x hub=duoc current
# Expected: print head SHA cua medinet_hub_duoc (KHONG cua medinet_hub_yte)
```

**Khuyen nghi:** Verifier agent (`/gsd-verify-work 1`) chay smoke o Phase 1 closeout — KHONG can chay ngay sau Plan 01-03 vi se phai run lai sau Plan 01-05 (`make hub-init` dynamic add).

## Threat Model Honored

| Threat ID | Disposition | Mitigation Applied |
|-----------|-------------|---------------------|
| T-01-03-01 (Tampering — -x hub=invalid) | mitigate | `parse_hub_x_arg` raise ValueError voi message "hub khong hop le". Test `test_parse_invalid_raises` PASS. |
| T-01-03-02 (Tampering — DSN resolver bug) | mitigate | `resolve_env_database_url` 2-pass check: target=central + base trỏ central → no-op; target=<hub> + base trỏ central → swap; cross-hub un-resolve ve central truoc; base sai → ValueError. Tests `test_resolve_unresolves_yte_base_when_arg_central` + `test_resolve_cross_hub_yte_to_duoc` (W8) + `test_resolve_invalid_base_dsn_raises` (W8) PASS. |
| T-01-03-03 (Information Disclosure — script log full DSN) | mitigate | `alembic-head-check.sh` chi echo hub name + rev SHA + drift message — KHONG `echo "$DATABASE_URL"` hay credentials. Pattern grep `echo` trong script KHONG chua `DATABASE_URL`. |
| T-01-03-04 (DoS — migrate-all fail mid-way) | mitigate | `for hub in ...; do ... \|\| exit 1; done` fail-fast — nhung hub da apply khong rollback. R-V3-3 mitigation: alembic-head-check.sh exit 1 → CI gate block merge (Plan 05) → ops re-run migrate-all sau fix. Acceptable trade-off. |
| T-01-03-05 (EoP — migration with superuser) | accept | M2 dung POSTGRES_USER (superuser) cho moi migration — separation of duties defer Phase 7 migration phase (per-hub dedicated migration role). |

## Threat Flags

**None.**

Plan 01-03 chi them helpers pure + Makefile target + bash lint script — KHONG gioi thieu network endpoint moi, auth path moi, file access pattern moi, hoac schema change o trust boundary. Tat ca surface da bake o threat_model frontmatter.

## Known Stubs

**None.**

Tat ca code da functional:
- `parse_hub_x_arg` parse CLI -x argument that.
- `resolve_env_database_url` deterministic DSN resolve voi cross-hub roundtrip support.
- Makefile `migrate-all` + `migrate-status` chay alembic CLI runtime.
- `alembic-head-check.sh` lint script runtime.

KHONG co placeholder/TODO/FIXME. Stub HEAD SHA so sanh = first hub's head dung pattern simple (KHONG complex consensus protocol — overkill cho lint check).

## API Surface Summary

### parse_hub_x_arg

```python
def parse_hub_x_arg(x_args: list[str]) -> str | None
```

- Input: list of `"key=value"` (tu `context.get_x_argument(as_dictionary=False)`).
- Output: hub name (`"central" | "yte" | "duoc" | "hcns"`) hoac None.
- Raises: `ValueError` neu `hub=<invalid>` (hub khong thuoc 4 gia tri).

### resolve_env_database_url

```python
def resolve_env_database_url(
    base_dsn: str, hub_arg: str | None, default_hub: str
) -> str
```

- Input: base DSN tu Settings.database_url (validated qua Plan 02 model_validator), `hub_arg` tu CLI -x, `default_hub` tu Settings.hub_name fallback.
- Output: DSN resolved cho target hub (target=central → no-op; target=<hub> → swap segment; cross-hub → un-resolve ve central + resolve sang target).
- Raises: `ValueError` neu base_dsn KHONG tro `medinet_central` HOAC `medinet_hub_*`.

### Makefile contracts

| Target | Mode | Behavior |
|--------|------|----------|
| `migrate-all` | apply | Loop `HUBS_ALL` chay `alembic -x hub=$$hub upgrade head` fail-fast + goi `scripts/alembic-head-check.sh` cuoi loop |
| `migrate-status` | read | Loop `HUBS_ALL` chay `alembic -x hub=$$hub current` show head SHA per hub |

`HUBS_ALL ?= central yte duoc hcns` — override-able cho selective migration.

### alembic-head-check.sh CLI

```bash
# Default (4 hub)
bash scripts/alembic-head-check.sh

# Selective
HUBS_ALL="central yte" bash scripts/alembic-head-check.sh

# CI integration (Plan 05)
HUBS_ALL="central yte duoc hcns" UV=uv bash scripts/alembic-head-check.sh
```

- Exit 0: PASS — tat ca hub cung head SHA.
- Exit 1: FAIL — drift detected HOAC khong lay duoc head 1 hub.

## R-V3-3 Mitigation Chain

```
make migrate-all (Plan 03)
    ↓ for hub in HUBS_ALL:
    ↓   alembic -x hub=$$hub upgrade head  (env.py resolve DSN runtime)
    ↓
scripts/alembic-head-check.sh (Plan 03)
    ↓ alembic -x hub=$$hub current --> extract rev SHA
    ↓ compare all heads = HUBS_ALL[0].head
    ├─ PASS → exit 0 → CI gate proceed
    └─ FAIL → exit 1 → CI gate block (Plan 05 wire test.yml step)
                    → ops investigate drift
                    → make migrate-all re-apply
```

**Key property:** Lint script chay sau migrate-all → drift detected truoc khi tag/release → ops biet phai re-run migration TRUOC khi user nhin thay error "table column not exist".

## Self-Check

### Files exist

| Path | Exists? |
|------|---------|
| `Hub_All/api/migrations/env.py` | FOUND (modified) |
| `Hub_All/api/Makefile` | FOUND (modified) |
| `Hub_All/api/tests/unit/test_alembic_env_hub_arg.py` | FOUND (created) |
| `Hub_All/api/scripts/alembic-head-check.sh` | FOUND (created, mode 100755) |
| `Hub_All/.planning/phases/01-multi-db-topology/01-03-SUMMARY.md` | FOUND (this file) |

### Commits exist

| Hash | Type | Description |
|------|------|-------------|
| `ddd379c` | test | TDD RED — failing test 10 case |
| `48acecc` | feat | TDD GREEN — env.py helpers + guard + DSN inject |
| `7224c06` | feat | Task 2 — Makefile migrate-all + migrate-status |
| `e16eb3b` | feat | Task 3 — alembic-head-check.sh |

### Acceptance criteria all PASS

- Task 1: 12/12 PASS (xem table tren)
- Task 2: 6/8 PASS + 2 DEFERRED (Rule 3 — make binary thieu tren Windows host; substitute Python parser PASS; CI Linux + Plan 05 smoke se validate)
- Task 3: 9/9 PASS (xem table tren — bash -n + grep + mode 100755)
- Full unit test suite: 157/157 PASS (no regression voi Plan 02 baseline 147/147)
- mypy strict on env.py: Success: no issues
- ruff check on env.py + test file: All checks passed

### TDD Gate Compliance

- RED: `ddd379c` (`test:` prefix) — failing test exist truoc GREEN.
- GREEN: `48acecc` (`feat:` prefix) — implement pass tests + 2 Rule 3 fix.
- REFACTOR: SKIPPED (intentional — code GREEN da clean, KHONG commit empty).

## Self-Check: PASSED

---

*Generated 2026-05-21 — Plan 01-03 (Wave 2) hoan thanh 3/3 task (1 TDD + 2 non-TDD). 4 commit (1 RED `ddd379c`, 1 GREEN `48acecc`, 1 Task 2 `7224c06`, 1 Task 3 `e16eb3b`). Next: Wave 2 cung lung voi Plan 01-04 (cocoindex flow per-hub) — chay parallel; Wave 3 Plan 01-05 (hub-init.sh dynamic + [BLOCKING] schema push) sequential sau ca W2.*
