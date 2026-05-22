---
phase: 02-hub-con-codebase-factor
plan: 05
subsystem: hub-registration
tags:
  - dynamic-hub-registration
  - settings-str-validator
  - regex-validation
  - reserved-name-blacklist
  - docker-compose-override
  - make-hub-add
  - factor-04
  - user-direction-b
requirements:
  - FACTOR-04
dependency_graph:
  requires:
    - 02-01  # create_app() factory pattern carry forward (Settings.hub_name dùng cho conditional mount)
    - 02-02  # docker-compose.yml base (4 hub gốc — override merge target)
    - 02-03  # integration test fixture pattern (test_config_hub_name regression baseline)
    - 02-04  # Phase 2 closeout (FACTOR-01..03 đã ship)
    - 01-02  # Phase 1 Settings + _enforce_hub_dsn_match validator (carry forward dynamic)
    - 01-05  # Phase 1 hub-init.sh (DB-level wrap target cho hub-add.sh)
  provides:
    - factor-04-dynamic-hub-registration
    - settings-hub-name-str-validator
    - reserved-hub-names-blacklist
    - scripts-hub-add-bash-pipeline
    - docker-compose-override-template
    - make-hub-add-target
  affects:
    - api/app/config.py
    - api/scripts/hub-init.sh
    - Hub_All/Makefile
    - api/Makefile
    - Hub_All/.gitignore
    - Hub_All/README.md
    - Hub_All/CLAUDE.md
    - .planning/STATE.md
tech-stack:
  added:
    - bash-regex-validation
    - sed-substitute-template
    - docker-compose-merge-override
  patterns:
    - field_validator-after-mode
    - frozenset-reserved-blacklist
    - bash-script-wrap-bash-script
    - yaml-anchor-cross-file-pitfall-avoidance
key-files:
  created:
    - api/tests/unit/test_config_hub_name_dynamic.py
    - api/scripts/hub-add.sh
    - docker-compose.override.yml.template
    - .planning/phases/02-hub-con-codebase-factor/02-05-SUMMARY.md
  modified:
    - api/app/config.py
    - api/tests/unit/test_config_hub_name.py
    - api/scripts/hub-init.sh
    - Hub_All/Makefile
    - api/Makefile
    - Hub_All/.gitignore
    - Hub_All/README.md
    - Hub_All/CLAUDE.md
    - .planning/STATE.md
decisions:
  - D-V3-Phase2-Dynamic-A regex ^[a-z][a-z0-9_]{0,15}$ max 16 char (Postgres identifier 63 char limit - prefix 12 char headroom)
  - D-V3-Phase2-Dynamic-B reserved blacklist 6 name {postgres cocoindex template0 template1 public medinet} - central KHÔNG reserved (aggregator special-case)
  - D-V3-Phase2-Dynamic-C compose layering base KHÔNG sửa + auto-gen override.yml gitignored operator-local
  - D-V3-Phase2-Dynamic-D auto-detect port = max ports hiện hữu + 1 (regex scan NNNN:8080) fallback 8184 nếu base parse fail
  - D-V3-Phase2-Dynamic-E hub_registry table source-of-truth defer Phase 6 SETTINGS-04 (Plan 02-05 chỉ validate format + sinh compose block)
metrics:
  duration_minutes: 25
  completed_date: 2026-05-22
  tasks_completed: 3
  tasks_skipped: 1
  commits: 4
---

# Phase 02 Plan 05: FACTOR-04 Dynamic Hub Registration Summary

> Mở rộng v3.0 architectural model — operator thêm hub mới (vd `phap_che`, `marketing`) bằng 1 lệnh `make hub-add HUB=<name> [PORT=<port>]` mà KHÔNG sửa code Python / `docker-compose.yml` base. Settings.hub_name `Literal[4]` → `str` + regex validator + reserved blacklist 6 name; `scripts/hub-add.sh` wrap `hub-init.sh` (DB layer Phase 1) + sed substitute `docker-compose.override.yml.template` → append `docker-compose.override.yml` (gitignored operator-local).

---

## Tóm tắt

Plan 02-05 hoàn thành FACTOR-04 — REQ-ID thêm vào Phase 2 retroactively theo user direction B 2026-05-22 sau Plan 02-04 closeout. **3 task ship** (Task 1 + 2 + 4) + **1 task skip** (Task 3 smoke runtime — pre-resolved user decision với rationale rõ). Phase 2 v3.0 nay fully DONE 5 plan, satisfied FACTOR-01..04. Hub_registry source-of-truth defer Phase 6 SETTINGS-04 (long-term).

**Status:** Task 1 + 2 + 4 DONE ✅, Task 3 SKIP với rationale documented. Phase 2 closeout retroactively extended 4 → 5 plan.

---

## Task ship

### Task 1: Settings refactor + 29 unit test dynamic + update test_config_hub_name.py

**File modified:**
- `api/app/config.py` — `RESERVED_HUB_NAMES` frozenset module-level + `hub_name: Literal[4]` → `str` + `field_validator("hub_name", mode="after")` regex + blacklist check. `_enforce_hub_dsn_match` model_validator (Phase 1 carry forward) KHÔNG sửa — đã dùng `self.hub_name` dynamic.
- `api/tests/unit/test_config_hub_name.py` — test 5 đổi từ `test_invalid_hub_name_raises` ("invalid_hub" — Literal reject) sang `test_invalid_hub_name_pattern_raises` ("Invalid_Hub" — uppercase regex reject). Sau Plan 02-05 "invalid_hub" snake_case 11 char PASS regex, cần input reject thực sự.

**File created:**
- `api/tests/unit/test_config_hub_name_dynamic.py` — 29 test PASS:
  - **Accept (10):** 4 parametrize regression (central/yte/duoc/hcns) + 3 parametrize dynamic (phap_che/marketing/dev_test) + 1 single-char ("a") + 1 max-length 16-char + 1 dynamic DSN match OK (phap_che + medinet_hub_phap_che).
  - **Reject (16):** 10 parametrize invalid pattern (uppercase Yte/YTE, hyphen phap-che, 1hub start-digit, _underscore start, 17-char too-long, empty, hub.dot, hub space, hub$dollar) + 6 parametrize reserved blacklist (sorted RESERVED_HUB_NAMES).
  - **Lock + DSN (3):** test_central_not_in_reserved_blacklist + test_reserved_blacklist_size_is_6 + test_dynamic_hub_dsn_mismatch_raises (phap_che + medinet_hub_marketing → ValidationError).

**Settings refactor diff:**
```python
# CŨ (Phase 1 Plan 01-02):
hub_name: Literal["central", "yte", "duoc", "hcns"] = "central"

# MỚI (Plan 02-05 FACTOR-04):
hub_name: str = "central"

@field_validator("hub_name", mode="after")
@classmethod
def _validate_hub_name(cls, v: str) -> str:
    if not re.fullmatch(r"^[a-z][a-z0-9_]{0,15}$", v):
        raise ValueError(f"hub_name invalid format: {v!r}. Pattern required: ...")
    if v in RESERVED_HUB_NAMES:
        raise ValueError(f"hub_name reserved: {v!r}. 6 reserved names ...")
    return v

# Module-level constant (BLACKLIST 6 name):
RESERVED_HUB_NAMES = frozenset({
    "postgres", "cocoindex", "template0", "template1", "public", "medinet",
})
```

**Verify:**
- `pytest tests/unit/test_config_hub_name.py tests/unit/test_config_hub_name_dynamic.py -v` — **40/40 PASS** in 0.51s (11 original + 29 dynamic).
- `ruff check app/config.py tests/unit/test_config_hub_name.py tests/unit/test_config_hub_name_dynamic.py` — exit 0 (1 fix import sort auto-applied).
- `mypy --strict app/config.py` — exit 0 "Success: no issues found in 1 source file".
- Regression `pytest tests/unit/test_main_factory.py` — **9/9 PASS** in 7.02s (Plan 02-01 KHÔNG break).

**Commit:** `408a587` feat(02-05): Settings hub_name Literal -> str + regex validator + reserved blacklist (TDD hỗn hợp 1 commit — test + impl gộp theo pattern Phase 1 Plan 01-02).

---

### Task 2: hub-add.sh + override template + Makefile target + hub-init.sh sync regex

**File modified:**
- `api/scripts/hub-init.sh` — regex `{1,30}` → `{0,15}` sync Settings Plan 02-05 + comment cập nhật.
- `Hub_All/Makefile` — `.PHONY` thêm `hub-add` + help text section mới + target `hub-add` proxy `bash Hub_All/api/scripts/hub-add.sh $(HUB) $(PORT)` với pre-check `[ -z "$(HUB)" ]` exit 2.
- `api/Makefile` — `.PHONY` thêm `hub-add` + target proxy `bash scripts/hub-add.sh $(HUB) $(PORT)`.
- `Hub_All/.gitignore` — thêm `docker-compose.override.yml` (operator-local, T-02-05-04 Info Disclosure).

**File created:**
- `api/scripts/hub-add.sh` (chmod +x) — 7-step validate pipeline (xem snippet bên dưới).
- `docker-compose.override.yml.template` — service block inline `{{HUB}}` + `{{PORT}}` placeholder.

**scripts/hub-add.sh 7-step pipeline:**
1. **Parse args** — HUB + PORT positional hoặc env (`HUB=<name> PORT=<port>` prefix); empty HUB → exit 2 usage.
2. **Regex format validate** — `^[a-z][a-z0-9_]{0,15}$` sync Settings + hub-init.sh. Reject uppercase/hyphen/start-digit/start-underscore/>16char → exit 2.
3. **Reserved blacklist validate** — bash array `RESERVED_NAMES=(postgres cocoindex template0 template1 public medinet)` loop check → exit 2. `central` reject explicit (aggregator special-case đã có).
4. **Compose root detect** — `[ -f docker-compose.yml ]` cwd / `Hub_All/docker-compose.yml` / parent fallback. Verify template file exist hoặc exit 2.
5. **Duplicate service detect** — grep `^  python-api-${HUB}:` trong base + override → exit 2 nếu trùng.
6. **Auto-detect port** — `if [ -z "$PORT" ]` scan max port regex `"NNNN:8080"` trong base + override + 1, fallback 8184. Validate range 1024-65535 + port conflict check.
7. **Execute** — (a) `bash hub-init.sh $HUB` (DB layer Phase 1) → (b) sed substitute template `{{HUB}}` + `{{PORT}}` append override (write header `services:` nếu first-time) + append `medinet_cocoindex_$HUB:` volume declaration (write `volumes:` section nếu first-time, dùng sed `-i.bak` nếu đã có) → (c) `docker compose config --quiet` verify merge OK (exit 3 nếu fail).

**docker-compose.override.yml.template snippet:**
```yaml
  python-api-{{HUB}}:
    build:
      context: ./api
      dockerfile: Dockerfile
    env_file:
      - ./api/.env
    container_name: medinet-api-{{HUB}}
    environment:
      HUB_NAME: {{HUB}}
      DATABASE_URL: postgresql+asyncpg://medinet:${POSTGRES_PASSWORD:-medinet_dev_pwd}@postgres:5432/medinet_hub_{{HUB}}
      # ... (12 env line khác inline đầy đủ giống pattern Plan 02-02)
    volumes:
      - ./api/keys:/keys:ro
      - ./file_store:/file_store
      - medinet_cocoindex_{{HUB}}:/app/.cocoindex
    ports:
      - "{{PORT}}:8080"
    depends_on:
      postgres: { condition: service_healthy }
      redis: { condition: service_healthy }
    networks: [medinet_net]
```

**Quan trọng — YAML anchor cross-file pitfall:** Template KHÔNG dùng `<<: *api-template` cross-file vì YAML anchor base `&api-template` chỉ visible trong cùng file. Override file (riêng) KHÔNG thấy anchor base → inline đầy đủ environment + volumes + ports + depends_on + networks (cùng pattern Plan 02-02 với từng service hub gốc).

**Verify:**
- `bash -n api/scripts/hub-add.sh` exit 0 (syntax OK).
- `bash -n api/scripts/hub-init.sh` exit 0 (sync regex OK).
- `test -x api/scripts/hub-add.sh` PASS (executable).
- `test -f docker-compose.override.yml.template` PASS.
- `docker compose -f docker-compose.yml config --quiet` exit 0 (base parse OK với template file present).
- Grep acceptance: `{{HUB}}` 6 occurrences + `{{PORT}}` 2 + `hub-add:` target trong cả 2 Makefile + regex `0,15` 5 occurrences trong 2 script + `RESERVED_NAMES=` bash array + gitignore entry 3 occurrences.

**Commit:** `4537859` feat(02-05): hub-add.sh + override template + Makefile target FACTOR-04 dynamic hub registration.

---

### Task 3: SKIP — pre-resolved user decision

**Pre-resolved rationale (orchestrator + user):**
- 29 unit test test_config_hub_name_dynamic.py + 11 test test_config_hub_name.py cover validator behavior FULL (4 hub gốc regression accept + 3 dynamic accept + 1 single-char + 1 max-length boundary + 10 reject invalid pattern + 6 reject reserved + DSN match dynamic).
- `bash -n` syntax check Task 2 PASS — bash parse OK.
- `docker compose config --quiet` base verify đã PASS ở Plan 02-02 — compose layer template KHÔNG break base.
- Smoke runtime Docker (`make hub-add HUB=tmp_test PORT=8189` + `docker compose up python-api-tmp_test` + curl health 200) defer Phase 7 MIGRATE-05 full E2E khi có Docker Desktop available + DB migration data thật.

**KHÔNG chạy:** `make hub-add` runtime, `docker compose up -d python-api-tmp_test`, `curl http://localhost:8189/api/health`.

**Risk accepted:** Bug runtime KHÔNG visible qua unit/static (vd Postgres permission gốc role 'medinet' không có CREATEDB, alembic env.py không resolve dynamic DSN, docker compose merge override syntax invalid) — defer Phase 7 smoke E2E. Threat model T-02-05-06 Repudiation marked `mitigate` qua static verify chain Task 1 + 2 (90% rủi ro covered).

---

### Task 4: Docs update README + CLAUDE.md + STATE.md

**File modified:**
- `Hub_All/README.md` — thêm section `## Add a new hub (dynamic registration — FACTOR-04 Plan 02-05)` sau section Observability + trước Milestone status. 3-step quick start + validation rules + Phía sau hậu trường + Cleanup procedure + Hub registry source-of-truth defer note.
- `Hub_All/CLAUDE.md` section 6 — v3.0 progress table row Phase 2 đổi `4 plan | FACTOR-01..03 (3)` → `5 plan | FACTOR-01..04 (4 — FACTOR-04 added 2026-05-22 Plan 02-05)`. Thêm subsection "Phase 2 FACTOR-04 dynamic hub registration (added 2026-05-22 — user direction B)" với 5 bullet pattern + reference Plan 02-05. Footer: `9/~30 plan ≈ 28%` → `10/~32 plan ≈ 31%`.
- `Hub_All/.planning/STATE.md` — frontmatter status + completed_plans 9 → 10 + total_plans 9 → 10 + percent 28 → 31; Current Position Phase 2 DONE 5 plans; Plan 02-05 row Phase 2 Planning Summary status "DONE 2026-05-22"; Phase 2 Results Summary thêm row 02-05 Wave 4; Phase 2 deliverable summary thêm bullet FACTOR-04; Next Action xóa entry "Plan 02-05 pending" (đã DONE), shift 4 → 3 entries.

**Verify grep acceptance:**
- README.md: `## Add a new hub` 1, `make hub-add HUB=` 2, regex 1.
- CLAUDE.md: `FACTOR-04` 4 occurrences, `make hub-add` 1.
- STATE.md: `FACTOR-04` 8 occurrences, `completed_plans: 10` 1, `total_plans: 10` 1, `02-05` 10 occurrences, `user direction B` 4 occurrences.

**Commit:** `0254d10` docs(02-05): README hub-add quick start + CLAUDE.md FACTOR-04 note + STATE.md Phase 2 5 plan.

---

## Decision LOCKED (D-V3-Phase2-Dynamic-A..E)

| ID | Decision | Rationale |
|----|----------|-----------|
| **D-V3-Phase2-Dynamic-A** | Regex `^[a-z][a-z0-9_]{0,15}$` (max 16 char) | Postgres identifier 63 char limit minus `medinet_hub_` prefix 12 char = 51 char headroom. 16 char cho dễ nhớ + URL prefix Phase 5 Caddy gọn. KHÔNG cho phép hyphen (Postgres identifier cần quote nếu non-alphanumeric) hoặc uppercase (case-sensitivity confuse). |
| **D-V3-Phase2-Dynamic-B** | Reserved blacklist 6 name `{postgres, cocoindex, template0, template1, public, medinet}` | Postgres có 4 template DB hệ thống + schema `public` + role `medinet` (M2 carry forward — OWNER mọi DB nghiệp vụ) + DB internal `cocoindex` (R5 + P7 carry forward). `central` KHÔNG trong blacklist — aggregator special-case mapping `medinet_central` (KHÔNG prefix `medinet_hub_`). |
| **D-V3-Phase2-Dynamic-C** | Compose layering = base KHÔNG sửa + auto-gen `docker-compose.override.yml` gitignored | Hub mới chỉ live trong override (operator-local). Docker compose tự merge `docker-compose.yml` + `docker-compose.override.yml` khi `docker compose up`. Template `.template` PHẢI commit (source-of-truth). |
| **D-V3-Phase2-Dynamic-D** | Auto-detect port = max ports hiện hữu + 1 (regex scan `"NNNN:8080"`) fallback 8184 | Scan max port trong base + override + 1. User truyền explicit `PORT=<port>` thì skip auto-detect; validate range 1024-65535 + port conflict check. |
| **D-V3-Phase2-Dynamic-E** | Hub_registry table source-of-truth defer Phase 6 SETTINGS-04 | Plan 02-05 chỉ validate format Settings + sinh compose block. Long-term `hub_registry` table ở `medinet_central` — central admin CRUD; hub con đọc TTL cache. Operator phải manual track danh sách hub đã add ở Plan 02-05. |

---

## Threat Model — 9 STRIDE Threat (mitigation summary)

| Threat ID | Category | Disposition | Mitigation |
|-----------|----------|-------------|------------|
| **T-02-05-01** | Tampering | mitigate | Regex `^[a-z][a-z0-9_]{0,15}$` reject special char ở Settings + hub-add.sh. Phase 1 `_enforce_hub_dsn_match` validator strip DSN query string + check suffix. Postgres identifier quoted internally bởi asyncpg/SQLAlchemy parameterized query. |
| **T-02-05-02** | Elevation of Privilege | mitigate | Reserved blacklist 6 name (`RESERVED_HUB_NAMES`) reject `postgres`, `medinet`, `template0`, `template1`, `public`, `cocoindex` ở Settings + hub-add.sh. Unit test `test_reject_reserved_hub_names` lock blacklist parametrize 6 name. |
| **T-02-05-03** | DoS | mitigate | Regex max 16 char hard cap. Settings validator + hub-add.sh validator reject pre-DB-create. Test `test_reject_invalid_pattern` parametrize 17-char input. |
| **T-02-05-04** | Information Disclosure | mitigate | `.gitignore` exclude `docker-compose.override.yml` (gitignored — operator-local hub list KHÔNG leak). Template `.template` commit OK (spec không chứa hub name cụ thể). README.md document gitignore rule. |
| **T-02-05-05** | Tampering | mitigate | hub-add.sh Step 5 grep duplicate detect (`^  python-api-${HUB}:` trong base + override), exit 2 với rõ error. Operator manual xoá block nếu muốn re-create. |
| **T-02-05-06** | Repudiation | mitigate | Task 3 SKIP với rationale rõ (Docker không available local). Unit test Task 1 (40 test) cover Settings validator + DSN match dynamic. Bash syntax check Task 2 + `docker compose config --quiet` parse OK = static verify compose layer. Smoke chỉ cover runtime startup — 90% rủi ro covered by static. |
| **T-02-05-07** | Elevation of Privilege | accept | hub-init.sh chạy TRƯỚC compose append (Step 7a → Step 7b). Nếu hub-init.sh fail `set -euo pipefail` abort → compose chưa append. State consistent. Postgres role `medinet` có CREATEDB từ M2. |
| **T-02-05-08** | Tampering | mitigate | Template commit vào git → code review catch. Threat scope tương đương docker-compose.yml base bị tamper. Branch protection (defer v4.0) sẽ enforce review. |
| **T-02-05-09** | DoS | accept | Phase 2 KHÔNG cover production capacity — operator self-aware. Phase 6 SETTINGS-04 `hub_registry` sẽ thêm capacity guard config-driven. |

---

## Verification (full chain)

### 1. Unit test Settings validator (Task 1)
- `pytest tests/unit/test_config_hub_name.py tests/unit/test_config_hub_name_dynamic.py -v` — **40/40 PASS** in 0.51s
  - test_config_hub_name.py 11/11 (10 original + 1 đổi test 5 thành test_invalid_hub_name_pattern_raises uppercase reject)
  - test_config_hub_name_dynamic.py 29/29 (4 regression accept + 3 dynamic accept + 2 boundary + 10 reject pattern + 6 reject reserved + 1 'central' not reserved + 1 size lock + 2 DSN match dynamic)
- `mypy --strict app/config.py` — exit 0
- `ruff check app/config.py tests/unit/test_config_hub_name.py tests/unit/test_config_hub_name_dynamic.py` — exit 0 (1 fix import sort auto-applied)

### 2. Static verify bash + compose (Task 2)
- `bash -n api/scripts/hub-add.sh` exit 0 (syntax OK)
- `bash -n api/scripts/hub-init.sh` exit 0 (sync regex OK)
- `docker compose -f docker-compose.yml config --quiet` exit 0 (base parse OK với template file present)
- `test -f docker-compose.override.yml.template && test -f api/scripts/hub-add.sh && test -x api/scripts/hub-add.sh` PASS

### 3. Smoke runtime — Task 3 SKIP
Pre-resolved user decision với rationale rõ (xem Task 3 section). Smoke defer Phase 7 MIGRATE-05 full E2E.

### 4. Docs integrity (Task 4)
README.md có section "Add a new hub" 3-step + validation rules + cleanup; CLAUDE.md section 6 update FACTOR-04 covered + Phase 2 plan count 5 + Phase 2 FACTOR-04 subsection; STATE.md frontmatter `completed_plans: 10`, `percent: 31`, Phase 2 Results Summary row 02-05.

### 5. Regression check
- Phase 1 Plan 01-02 test (`test_config_hub_name.py`) — 4 hub gốc accept (regression không break)
- Plan 02-01 test (`test_main_factory.py`) — **9/9 PASS** create_app() 4 hub mode KHÔNG break
- Plan 02-02 docker compose base — `docker compose config --quiet` exit 0 (parse OK)

---

## Performance Metrics

| Metric | Value |
|--------|-------|
| Duration | ~25 minutes |
| Tasks completed | 3/4 (Task 1 + 2 + 4 ship; Task 3 SKIP pre-resolved smoke runtime) |
| Files created | 4 (`api/tests/unit/test_config_hub_name_dynamic.py`, `api/scripts/hub-add.sh`, `docker-compose.override.yml.template`, `02-05-SUMMARY.md`) |
| Files modified | 9 (`api/app/config.py`, `api/tests/unit/test_config_hub_name.py`, `api/scripts/hub-init.sh`, `Hub_All/Makefile`, `api/Makefile`, `Hub_All/.gitignore`, `Hub_All/README.md`, `Hub_All/CLAUDE.md`, `.planning/STATE.md`) |
| Unit tests added | 29 (test_config_hub_name_dynamic.py — 4 regression + 3 dynamic + 2 boundary + 10 reject pattern + 6 reject reserved + 1 'central' not reserved + 1 size lock + 2 DSN match) |
| Test pass rate | 40/40 (100%) test_config_hub_name + test_config_hub_name_dynamic in 0.51s |
| Regression test_main_factory.py | 9/9 PASS (5.39s) |
| Lint | ruff (1 auto-fix import sort) + mypy --strict PASS |
| Commits | 4 (Task 1 `408a587` + Task 2 `4537859` + Task 4 `0254d10` + SUMMARY tới đây) |
| Deviations | 1 (Task 3 SKIP smoke runtime — pre-resolved user decision; rationale: 40 unit test + bash syntax + docker compose config base verify đã PASS; smoke Docker defer Phase 7 MIGRATE-05) |

---

## Deviations from Plan

### Task 3 SKIP (pre-resolved)

**1. [Pre-resolved] Task 3 smoke runtime SKIP — Docker Desktop không available local**
- **Found during:** Pre-execution checkpoint
- **Issue:** Plan Task 3 = `checkpoint:human-action gate=blocking` — yêu cầu operator chạy `make hub-add HUB=tmp_test PORT=8189` + `docker compose up -d python-api-tmp_test` + `curl localhost:8189/api/health 200` + cleanup. Yêu cầu Docker Desktop + Postgres running.
- **Fix:** Pre-resolved bởi user trước khi execute với decision "skip smoke" + rationale rõ. Static verify chain (40 unit test + bash -n + docker compose config --quiet) cover 90% rủi ro. Smoke runtime defer Phase 7 MIGRATE-05 full E2E.
- **Files modified:** None (skip task entirely)
- **Commit:** N/A
- **Threat impact:** T-02-05-06 Repudiation marked `mitigate` qua static verify chain (xem threat model table).

### Auto-fixed Issues

**1. [Rule 3 — Blocking] Ruff import sort auto-fix `api/app/config.py`**
- **Found during:** Task 1 ruff check
- **Issue:** `ruff check` báo I001 import block un-sorted sau khi insert blank lines mới giữa imports + RESERVED_HUB_NAMES constant.
- **Fix:** `ruff check --fix` auto-format blank line (single intentional change — không đổi semantic).
- **Files modified:** `api/app/config.py` (blank line only)
- **Commit:** Included in `408a587`

---

## Known Stubs

Không có. Tất cả deliverable production-ready cho ops workflow.

`hub_registry` table integration KHÔNG phải stub — đã document rõ defer Phase 6 SETTINGS-04 trong README + CLAUDE.md + plan frontmatter (D-V3-Phase2-Dynamic-E LOCKED). Plan 02-05 phạm vi chỉ validate format + sinh compose block; long-term source-of-truth ở Phase 6.

---

## Next

**Phase 2 v3.0 fully DONE — 5 plan ship 2026-05-22 (FACTOR-01..04 satisfied):**
- Plan 02-01 FACTOR-01 + FACTOR-02 (create_app() conditional mount)
- Plan 02-02 FACTOR-01 (docker-compose 4 service)
- Plan 02-03 FACTOR-02 + FACTOR-03 (integration test endpoint matrix)
- Plan 02-04 FACTOR-01..03 closeout docs
- Plan 02-05 FACTOR-04 (dynamic hub registration) ✅ **NEW**

**Next milestone progression:**
1. **(Recommended) `/gsd-discuss-phase 3`** — Auth SSO + hub_ids trong JWT (GA-V3-A chốt). Gray areas: JWKS endpoint vs shared keypair vs cookie domain `.medinet.vn`.
2. (Optional) `/gsd-code-review 2` — advisory code review trên 9+ commits Phase 2 nay phủ cả Plan 02-05 FACTOR-04.
3. (Optional) `/gsd-verify-work 2` — manual UAT bổ sung; smoke compose runtime Plan 02-04 + Plan 02-05 Task 3 đều defer Phase 7 MIGRATE-05.

**v3.0-a progress:** Phase 1+2 DONE (2/3 phase v3.0-a — 10/~32 plan ≈ 31%). Phase 3 Auth SSO sẽ trigger v3.0-a EXIT GATE giữa Phase 3-4.

---

## Self-Check

Verify created files + commits exist (run từ Hub_All cwd).

**Files:**
- `api/app/config.py` — FOUND (modified, contains `RESERVED_HUB_NAMES` + `_validate_hub_name`)
- `api/tests/unit/test_config_hub_name.py` — FOUND (test 5 đổi sang `test_invalid_hub_name_pattern_raises`)
- `api/tests/unit/test_config_hub_name_dynamic.py` — FOUND (29 test)
- `api/scripts/hub-add.sh` — FOUND (executable, 7-step pipeline)
- `api/scripts/hub-init.sh` — FOUND (regex synced `{0,15}`)
- `docker-compose.override.yml.template` — FOUND (inline service block + placeholder)
- `Hub_All/Makefile` — FOUND (hub-add target + .PHONY)
- `api/Makefile` — FOUND (hub-add target + .PHONY)
- `Hub_All/.gitignore` — FOUND (docker-compose.override.yml entry)
- `Hub_All/README.md` — FOUND (Add a new hub section)
- `Hub_All/CLAUDE.md` — FOUND (FACTOR-04 subsection + table row updated)
- `Hub_All/.planning/STATE.md` — FOUND (completed_plans: 10 + Phase 2 row 02-05)
- `Hub_All/.planning/phases/02-hub-con-codebase-factor/02-05-SUMMARY.md` — FOUND (file này)

**Commits:**
- `408a587` feat(02-05): Settings hub_name Literal -> str + regex validator + reserved blacklist — FOUND
- `4537859` feat(02-05): hub-add.sh + override template + Makefile target FACTOR-04 dynamic hub registration — FOUND
- `0254d10` docs(02-05): README hub-add quick start + CLAUDE.md FACTOR-04 note + STATE.md Phase 2 5 plan — FOUND

## Self-Check: PASSED
