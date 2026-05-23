---
phase: 07
plan: 01
subsystem: migration
tags: [pg-dump, snapshot, bash-script, wave-1-blocking, migrate-01, foundation]
status: done
date_completed: 2026-05-23
duration_minutes: 3

requires:
  - Phase 1 TOPO-04 ship (per-hub Alembic 0001..0005 + medinet_hub_<name> schema ready)
  - Phase 2 FACTOR-04 ship (hub-add.sh validation chain regex + RESERVED blacklist T-5-05 mitigation pattern carry forward)
  - Phase 4 SYNC-01 ship (medinet_central.hubs row id UUID stable + HUB_*_ID env wire Plan 04-02)
  - D-V3-Phase7-A LOCKED 2026-05-23 (pg_dump --where option a REJECT cocoindex replay)

provides:
  - "Hub_All/scripts/migrate/01-snapshot-hubs.sh — pg_dump --data-only --no-owner --no-acl --column-inserts 5 table (chunks/documents/users/audit_logs/usage_events) --where hub_id filter 3 hub default (yte/duoc/hcns) HOẶC single hub arg + resolve hub_id UUID qua psql -tA + sanity check grep -c '^INSERT' + idempotent skip + exit codes 0/1/2/3/4 semantic"
  - "Hub_All/migrate-snapshots/.gitignore exclude *.sql + *.sql.gpg + *.dump (PII privacy enforce) + whitelist .gitignore + README.md tracked"
  - "Hub_All/migrate-snapshots/README.md document 30-day retention policy + find -mtime +30 -delete + cron 4AM + privacy/PII warning + recovery rollback procedure"
  - "Foundation BLOCKING cho Plan 07-02 (02-restore-hub.sh consume snapshot file) + Plan 07-03 (04-truncate-central.sh prerequisite) + Plan 07-04 (06-mcp-smoke runbook reference) + Plan 07-05 (05-smoke-e2e.sh post-migration verify)"

affects:
  - "Plan 07-02 02-restore-hub.sh consume output file pattern migrate-snapshots/migrate-<hub>-<YYYY-MM-DD>.sql"
  - "Plan 07-05 05-smoke-e2e.sh reference snapshot file path cho rollback scenario"
  - "Operator deploy team consume scripts/migrate/01-snapshot-hubs.sh + migrate-snapshots/README.md cho migration window blue/green per-hub"

tech-stack:
  added: []  # Bash-only — KHONG dep moi (pg_dump + psql + grep + wc + tr + find binary system)
  patterns:
    - "Bash strict mode (set -euo pipefail + IFS=\\$'\\n\\t') carry forward hub-init.sh + hub-add.sh"
    - "Hub name validation chain (regex ^[a-z][a-z0-9_]{0,15}$ + RESERVED blacklist 6 name + reject central) — T-5-05 mitigation pattern reuse"
    - "psql -tA -v ON_ERROR_STOP=1 resolve UUID per hub_name (analog hub-init.sh idempotent CREATE DATABASE check)"
    - "pg_dump --data-only --no-owner --no-acl --column-inserts --where filter row-level per hub_id (D-V3-Phase7-A LOCKED option a)"
    - "Sanity check post-dump grep -c '^INSERT' + warn neu 0 row (KHONG fail-loud — empty hub la legitimate edge case)"
    - "Idempotent skip neu output file da ton tai (operator phai delete explicit de re-snapshot)"
    - "Exit codes semantic 0/1/2/3/4 (success / summary fail / arg invalid / hub_id miss / pg_dump fail)"
    - ".gitignore PII exclude pattern (.sql / .sql.gpg / .dump) + whitelist README + .gitignore tracked"

key-files:
  created:
    - "Hub_All/scripts/migrate/01-snapshot-hubs.sh (194 LOC executable — pg_dump snapshot 3 hub default + validate_hub_name function + snapshot_one_hub function + sequential loop + summary)"
    - "Hub_All/migrate-snapshots/.gitignore (10 LOC — exclude *.sql/*.sql.gpg/*.dump + whitelist .gitignore/README.md)"
    - "Hub_All/migrate-snapshots/README.md (87 LOC — file naming convention + generate snapshot usage + 30-day retention + privacy/PII warn + recovery rollback procedure + reference cross-link)"
    - ".planning/phases/07-migration-smoke-e2e/07-01-SUMMARY.md (file này — closeout SUMMARY)"

  modified: []  # Plan 07-01 KHONG modify file hien huu — purely additive scaffold

decisions:
  - "Pattern hub_name validate carry forward T-5-05 mitigation hub-add.sh — regex + RESERVED blacklist + reject central — duy trì consistency với 9-step pipeline Phase 5 + Phase 2 FACTOR-04. Function-scope local var trong validate_hub_name() de reuse cho future migrate scripts (02-restore-hub.sh + 04-truncate-central.sh) thay vi top-level guard."
  - "Sanity check grep -c '^INSERT' WARN neu 0 row (KHONG fail-loud) — Rationale: hub empty la legitimate case (mới register chưa có data ingest), operator manual review FILE_SIZE + ROW_COUNT log + decide. Fail-loud sẽ false-positive block migration cho operator clean hub."
  - "Idempotent skip qua [-f \"$OUT_FILE\"] check — Rationale: 3 hub loop có thể fail mid-run; resume KHONG phai re-snapshot 2 hub đã done (mỗi snapshot 5-10 min). Operator explicit delete file de re-snapshot (avoid accidental overwrite production backup)."
  - "Exit codes 0/1/2/3/4 semantic distinct (KHONG dùng exit 1 chung) — Rationale: parent script (02-restore-hub.sh hoặc Plan 07-05 05-smoke-e2e.sh) có thể branch theo exit code distinguishing 'hub_id miss' vs 'pg_dump fail' vs 'arg invalid' để retry/skip/abort differently."
  - "MERGE Task 1+2 acceptance criteria 18/18 PASS grep — KHONG sửa LOC count target (PLAN spec min_lines: 120; thực ship 194 LOC). LOC growth do verbose Vietnamese comment + 5-section structure organize."

patterns-established:
  - "scripts/migrate/ module structure — Phase 7 NEW directory cho 5 bash script (01-snapshot + 02-restore + 03-switch-caddy + 04-truncate + 05-smoke-e2e). Tách rời scripts/ vs api/scripts/ — operator-facing migration vs developer per-hub init."
  - "migrate-snapshots/ output directory — .gitignore + README.md committed; *.sql/*.sql.gpg/*.dump excluded operator-local-only 30-day retention. Pattern reusable cho future migration milestone (v4.0+)."
  - "pg_dump --where filter per-hub_id — D-V3-Phase7-A LOCKED option a baseline cho future schema split migration (v4.0 sub-hub split per project_v3_multi_hub_split.md seed memory 2026-05-21)."
  - "Snapshot file naming convention migrate-<hub>-<YYYY-MM-DD>.sql — Date tag enable find -mtime +30 -delete automation; immutable timestamp T-07-01-04 Repudiation mitigation."

threat_coverage:
  - "T-07-01-01 Tampering hub_name arg (mitigate): Regex ^[a-z][a-z0-9_]{0,15}$ + RESERVED blacklist 6 name + reject 'central' explicit TRƯỚC pass vào psql -c / pg_dump (T-5-05 carry forward — KHONG inject shell via hub_name)"
  - "T-07-01-02 Information Disclosure migrate-snapshots/*.sql (mitigate): .gitignore *.sql + *.sql.gpg + *.dump + README explicit warn 'KHÔNG commit production data' + operator local-only 30-day retention + chmod 600 hint nếu multi-user host"
  - "T-07-01-03 DoS pg_dump on medinet_central (accept): Operator runs off-peak; --where filter giảm row scope ~5-10 min/hub acceptable. Sequential 3 hub avoid concurrent pg_dump memory pressure."
  - "T-07-01-04 Repudiation snapshot file naming (mitigate): Filename pattern migrate-<hub>-<YYYY-MM-DD>.sql immutable timestamp + pg_dump header tự ghi version + DB + extraction timestamp khi restore."

requirements-completed: [MIGRATE-01]

metrics:
  duration_minutes: 3
  tasks_completed: 2  # Task 1 snapshot script + Task 2 .gitignore + README
  files_created: 4  # 01-snapshot-hubs.sh + .gitignore + README.md + SUMMARY.md
  files_modified: 0  # KHONG modify file hien huu
  tests_added: 0  # Bash-only — bash -n syntax + 18 grep acceptance (KHONG unit/integration test runtime)

# Tags duplicate (sync)
date_completed: 2026-05-23
---

# Phase 7 Plan 07-01: Snapshot pg_dump per hub_id Summary

**Bash script `01-snapshot-hubs.sh` pg_dump --data-only --where hub_id 5 table (chunks/documents/users/audit_logs/usage_events) cho 3 hub default → `migrate-snapshots/migrate-<hub>-<YYYY-MM-DD>.sql` + .gitignore PII exclude + README.md 30-day retention policy. Foundation BLOCKING cho 4 plan Phase 7 sau.**

## Performance

- **Duration:** 3 phút (~3 phút thực tế)
- **Started:** 2026-05-23T05:17:39Z
- **Completed:** 2026-05-23T05:20:00Z
- **Tasks:** 2/2 (Task 1 snapshot script + Task 2 .gitignore + README)
- **Files created:** 4 (01-snapshot-hubs.sh + .gitignore + README.md + SUMMARY.md)
- **Files modified:** 0

## Accomplishments

- **Script `scripts/migrate/01-snapshot-hubs.sh` (194 LOC)** — Bash strict mode + validate_hub_name function (regex + RESERVED blacklist + reject central) + snapshot_one_hub function (resolve hub_id UUID qua psql -tA + pg_dump --data-only --where 5 table + sanity check grep -c '^INSERT' + idempotent skip) + sequential 3 hub loop + summary exit code reflect overall.
- **`migrate-snapshots/.gitignore` (10 LOC)** — Exclude `*.sql` + `*.sql.gpg` + `*.dump` (PII privacy enforce) + whitelist `.gitignore` + `README.md` tracked (T-07-01-02 Information Disclosure mitigation).
- **`migrate-snapshots/README.md` (87 LOC)** — Document file naming convention `migrate-<hub>-<YYYY-MM-DD>.sql` (T-07-01-04 Repudiation immutable timestamp) + generate snapshot usage (loop / single hub) + 30-day retention policy (manual `find -mtime +30 -delete` + cron 4AM example) + privacy/PII warning (users/audit_logs/usage_events/documents) + recovery rollback procedure (DROP + hub-init + psql -f restore + re-smoke).
- **Foundation BLOCKING** cho Plan 07-02 (`02-restore-hub.sh` consume snapshot file pattern) + Plan 07-03 (`04-truncate-central.sh` prerequisite chỉ truncate sau 3 hub PASS smoke) + Plan 07-05 (`05-smoke-e2e.sh` post-migration verify reference snapshot cho rollback scenario).

## Task Commits

Each task was committed atomically:

1. **Task 1: Tạo scripts/migrate/01-snapshot-hubs.sh** — `e057e5f` (feat)
2. **Task 2: Tạo migrate-snapshots/.gitignore + README.md** — `786586d` (docs)

**Plan metadata commit (SUMMARY.md + STATE.md + ROADMAP.md + REQUIREMENTS.md):** TBD (final docs commit)

## Files Created

- `Hub_All/scripts/migrate/01-snapshot-hubs.sh` — pg_dump snapshot 3 hub_id từ medinet_central (194 LOC bash, executable, syntax PASS `bash -n` exit 0)
- `Hub_All/migrate-snapshots/.gitignore` — Exclude .sql snapshot khỏi git (privacy PII enforce)
- `Hub_All/migrate-snapshots/README.md` — 30-day retention policy + recovery rollback procedure
- `.planning/phases/07-migration-smoke-e2e/07-01-SUMMARY.md` — File này (closeout SUMMARY)

## Decisions Made

- **Pattern hub_name validate carry forward T-5-05** — Regex `^[a-z][a-z0-9_]{0,15}$` + RESERVED blacklist 6 name (`postgres`/`cocoindex`/`template0`/`template1`/`public`/`medinet`) + reject `central` explicit. Function-scope `validate_hub_name()` reusable cho future migrate scripts.
- **Sanity check WARN neu 0 row** (KHONG fail-loud) — Empty hub là legitimate case (mới register chưa có data ingest), avoid false-positive block migration cho operator clean hub.
- **Idempotent skip neu output file da ton tai** — 3 hub loop có thể fail mid-run; resume KHONG phai re-snapshot 2 hub đã done (mỗi snapshot 5-10 min thực tế).
- **Exit codes semantic distinct 0/1/2/3/4** — Parent script (02-restore-hub.sh, 05-smoke-e2e.sh) branch theo exit code distinguishing arg invalid vs hub_id miss vs pg_dump fail.

## Deviations from Plan

**None — plan executed exactly as written.**

- Task 1 action block COPY VERBATIM 194 LOC bash script (PLAN spec writer agent: COPY VERBATIM directive honored).
- Task 2 action block COPY VERBATIM .gitignore + README.md (PLAN spec writer agent: COPY VERBATIM directive honored).
- Acceptance criteria 18/18 grep PASS (9 Task 1 + 9 Task 2).
- Bash syntax `bash -n Hub_All/scripts/migrate/01-snapshot-hubs.sh` exit 0.

**Total deviations:** 0
**Impact on plan:** None — clean execution per planner spec.

## Issues Encountered

- **Windows Bash dirent + Vietnamese path** — `c:\Users\dangs\OneDrive\Máy tính\Code\medinet_wiki` chứa Vietnamese diacritic `Máy`. Initial `ls "...\Hub_All"` PowerShell syntax fail (`$null` ambiguous redirect) → switched to bash POSIX path `c:/Users/dangs/OneDrive/Máy tính/Code/medinet_wiki/Hub_All` + `2>/dev/null || echo "NOT EXISTS"` pattern. Workaround applied successfully, KHONG block plan execution.
- **Git CRLF warning** trên both commit — `warning: in the working copy ..., LF will be replaced by CRLF the next time Git touches it`. Bash script file ship với LF (Unix-correct) — Git auto-convert CRLF khi checkout Windows. KHONG block, expected Windows behavior.

## SCOPE LIMIT executor honored

Per objective `<scope_limit>` Executor tạo scripts, KHONG chạy migration thật:

- ✅ `bash -n Hub_All/scripts/migrate/01-snapshot-hubs.sh` exit 0 (syntax check mandatory)
- ✅ KHONG actually run `pg_dump` against real `medinet_central` DB
- ✅ KHONG actually create snapshot .sql files in `migrate-snapshots/`
- ✅ Verify scripts via syntax + 18 grep acceptance criteria PASS (KHONG runtime execution)

**Runtime execution defer Phase 7 Plan 07-05 MIGRATE-05** (full E2E 3 hub + central + golden path + JWT SSO + cross-hub search live + per-hub branding visual diff).

## Next Plan Readiness

- **Plan 07-02 READY** — `02-restore-hub.sh` consume snapshot file pattern `migrate-snapshots/migrate-<hub>-<YYYY-MM-DD>.sql` (Task 1 output). Foundation BLOCKING resolved.
- **Plan 07-03 READY** — `04-truncate-central.sh` prerequisite (chỉ truncate sau 3 hub PASS smoke; snapshot backup retention 30-day enable rollback).
- **Plan 07-04 READY** — `06-mcp-smoke.md` runbook reference snapshot procedure cho rollback scenario.
- **Plan 07-05 READY** — `05-smoke-e2e.sh` post-migration verify reference snapshot file cho recovery rollback procedure documented `migrate-snapshots/README.md`.

**No blockers.** Wave 1 BLOCKING phase complete; 4 plan sau (Plan 07-02..07-05) có thể proceed.

## Acceptance Criteria Verification

**Task 1 (9 grep checks PASS):**

| # | Check | Result |
|---|-------|--------|
| 1 | `bash -n` exit 0 | PASS |
| 2 | `set -euo pipefail` count ≥ 1 | 1 ✅ |
| 3 | `pg_dump --data-only` count ≥ 1 | 1 ✅ |
| 4 | Regex pattern `^[a-z][a-z0-9_]` count ≥ 1 | 2 ✅ |
| 5 | `RESERVED_NAMES` count ≥ 1 | 2 ✅ |
| 6 | `migrate-snapshots/migrate-` count ≥ 1 | 2 ✅ |
| 7 | `SELECT id FROM hubs` count ≥ 1 | 1 ✅ |
| 8 | `"central"` count ≥ 1 (reject explicit) | 1 ✅ |
| 9 | `snapshot_one_hub` count ≥ 2 (def + call) | 2 ✅ |

**Task 2 (9 checks PASS):**

| # | Check | Result |
|---|-------|--------|
| 1 | `.gitignore` exists | PASS |
| 2 | `README.md` exists | PASS |
| 3 | `*.sql` in .gitignore count ≥ 1 | 2 ✅ |
| 4 | `!.gitignore` whitelist count ≥ 1 | 1 ✅ |
| 5 | `!README.md` whitelist count ≥ 1 | 1 ✅ |
| 6 | `find migrate-snapshots/` in README count ≥ 1 | 2 ✅ |
| 7 | "30 ngày" / "30 days" count ≥ 1 | 5 ✅ |
| 8 | "privacy" / "PII" count ≥ 1 | 2 ✅ |
| 9 | `migrate-yte-2026-05-23.sql` count ≥ 1 | 1 ✅ |

## Self-Check: PASSED

**Files exist:**
- ✅ `Hub_All/scripts/migrate/01-snapshot-hubs.sh` (FOUND, 194 LOC, executable)
- ✅ `Hub_All/migrate-snapshots/.gitignore` (FOUND, 10 LOC)
- ✅ `Hub_All/migrate-snapshots/README.md` (FOUND, 87 LOC)
- ✅ `.planning/phases/07-migration-smoke-e2e/07-01-SUMMARY.md` (FOUND, file này)

**Commits exist:**
- ✅ `e057e5f` (feat Task 1 snapshot script)
- ✅ `786586d` (docs Task 2 .gitignore + README)

---

*Phase: 07-migration-smoke-e2e*
*Plan: 01 — Snapshot pg_dump per hub_id (Wave 1 BLOCKING)*
*Completed: 2026-05-23*
*Foundation BLOCKING resolved cho Plan 07-02..07-05.*
