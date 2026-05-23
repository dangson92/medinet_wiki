---
phase: 07
plan: 02
subsystem: migration
tags: [psql-restore, blue-green, caddy-verify, bash-script, wave-2-blocking, migrate-02]
status: done
date_completed: 2026-05-23
duration_minutes: 4

requires:
  - Plan 07-01 ship (migrate-snapshots/ directory ready + 01-snapshot-hubs.sh có output pattern migrate-<hub>-<YYYY-MM-DD>.sql consume)
  - Phase 1 TOPO-04 ship (per-hub medinet_hub_<name> DB schema + Alembic 0001..0005 upgrade head)
  - Phase 4 SYNC-01 ship (per-hub sync_outbox schema Alembic 0005 — restored hub kế thừa)
  - Phase 5 PROXY-01 ship (Caddyfile dynamic regex `{re.hub_api.1}` + `reverse_proxy python-api-{re.hub_api.1}:8080` — verify-only mode rely trên dynamic capture)
  - D-V3-Phase7-B LOCKED 2026-05-23 (blue/green per-hub zero-downtime — KHÔNG full downtime weekend)
  - D-V3-Phase7-A LOCKED 2026-05-23 (pg_dump --where option a — snapshot input format match restore expectation)

provides:
  - "Hub_All/scripts/migrate/02-restore-hub.sh — psql -v ON_ERROR_STOP=1 -f restore snapshot vào medinet_hub_<HUB> 4-step pipeline (auto-detect latest snapshot + verify DB exist + current_database() match + psql -f restore + row count sanity check) + hub name validation chain T-5-05 + exit codes 0/2/3/4/5 semantic distinct + 7 psql command với ON_ERROR_STOP=1 fail-fast (T-07-02-03 mitigation)"
  - "Hub_All/scripts/migrate/03-switch-caddy.sh — VERIFY-ONLY mode (per CONTEXT.md correction Phase 5 dynamic regex đã ship) 3-step pipeline (docker compose ps verify container running + caddy validate Pitfall 7 mitigation + curl smoke warn-only) + --rollback flag stop hub container (Caddy fall-through file_server 404 T-07-02-04 accept) + hub name validation chain T-5-05 + exit codes 0/2/3/4 semantic distinct"
  - "Blue/green per-hub procedure step 3-5 implementable end-to-end: 01-snapshot-hubs.sh → 02-restore-hub.sh <HUB> → 03-switch-caddy.sh <HUB> → (Plan 07-05) 05-smoke-e2e.sh <HUB> chain với rollback path 03-switch-caddy.sh --rollback <HUB>"
  - "Foundation BLOCKING cho Plan 07-04 (06-mcp-smoke.md runbook reference restore procedure) + Plan 07-05 (05-smoke-e2e.sh post-restore smoke + rollback procedure documentation)"

affects:
  - "Plan 07-03 (04-truncate-central.sh) depend trên blue/green procedure complete — truncate central skeleton CHỈ sau 3 hub đã restore + smoke PASS qua 02-restore-hub.sh + 03-switch-caddy.sh + 05-smoke-e2e.sh"
  - "Plan 07-05 (05-smoke-e2e.sh) consume 03-switch-caddy.sh smoke endpoint pattern (curl -k https://${DOMAIN}/<HUB>/api/health) + rollback procedure reference"
  - "Operator deploy team consume 2 script này trong migration window: per-hub iterate yte/duoc/hcns với rollback fallback path"

tech-stack:
  added: []  # Bash-only — KHÔNG dep mới (psql + docker compose + curl + grep + ls + sort binary system)
  patterns:
    - "Bash strict mode (set -euo pipefail + IFS=\\$'\\n\\t') carry forward Plan 07-01 + hub-init.sh + hub-add.sh"
    - "Hub name validation chain (regex ^[a-z][a-z0-9_]{0,15}$ + RESERVED blacklist 6 name + reject central) — T-5-05 mitigation pattern reuse từ Plan 02-05 + 05-05 + 07-01"
    - "psql -v ON_ERROR_STOP=1 -tA pattern (7 lệnh trong 02-restore-hub.sh) — fail-fast trên bất kỳ error SQL"
    - "current_database() verify match TRƯỚC restore (T-07-02-03 mitigation — KHÔNG restore vào DB sai vd medinet_central)"
    - "Auto-detect latest snapshot qua ls -1 ... | sort -r | head -1 — operator KHÔNG cần specify file name explicit"
    - "VERIFY-ONLY pattern post Phase 5 dynamic regex — KHÔNG sed edit Caddyfile (shrink complexity ~50% so với sed approach)"
    - "docker compose ps --format json | grep '\"State\":\"running\"' pattern carry forward Plan 05-05 hub-add.sh Step 9"
    - "caddy validate PRE-reload (Pitfall 7 silent rollback mitigation) MANDATORY trong Caddy-touching scripts"
    - "curl -k -sf -o /dev/null --max-time 5 smoke warn-only pattern (KHÔNG fail-loud cho dev pre-up)"
    - "Rollback flag --rollback → docker compose stop + Caddy regex fall-through file_server 404 user-visible signal (T-07-02-04 accept)"
    - "Exit codes semantic 0/2/3/4/5 (success / arg invalid / resource miss / psql/caddy fail / row count mismatch) — parent script Plan 07-05 branch theo exit code"

key-files:
  created:
    - "Hub_All/scripts/migrate/02-restore-hub.sh (225 LOC executable — psql restore 4-step pipeline + 7 psql ON_ERROR_STOP=1 fail-fast + current_database() T-07-02-03 verify match + auto-detect latest snapshot + row count sanity check + hub validation chain)"
    - "Hub_All/scripts/migrate/03-switch-caddy.sh (132 LOC executable — VERIFY-ONLY 3-step pipeline + --rollback flag + docker compose ps verify container + caddy validate Pitfall 7 + curl smoke warn-only + hub validation chain)"
    - ".planning/phases/07-migration-smoke-e2e/07-02-SUMMARY.md (file này — closeout SUMMARY)"

  modified: []  # Plan 07-02 KHÔNG modify file hiện hữu — purely additive scaffold

decisions:
  - "Verify-only mode cho 03-switch-caddy.sh thay vì sed edit Caddyfile (per CONTEXT.md `<specifics>` correction 2026-05-23) — Phase 5 Caddyfile `{re.hub_api.1}` dynamic regex đã handle routing tự động dựa URL prefix, Phase 7 chỉ cần verify python-api-<HUB> container actually running + Caddy auto-route đúng. Shrink complexity ~50%, ít error-prone hơn sed approach."
  - "Pattern hub_name validation chain carry forward T-5-05 — Regex + RESERVED blacklist + reject central. Consistency với 9-step pipeline Phase 5 + Phase 2 FACTOR-04 + Plan 07-01. KHÔNG relax cho operator convenience (security mandate)."
  - "Auto-detect latest snapshot qua ls -1 ... | sort -r | head -1 thay vì arg file path explicit — Operator UX simpler (rerun với cùng arg sau debug). Snapshot naming convention `migrate-<hub>-<YYYY-MM-DD>.sql` (immutable timestamp T-07-01-04) đảm bảo sort -r reverse-chronological deterministic."
  - "current_database() verify match T-07-02-03 mitigation strong (KHÔNG warn-only) — Rationale: restore vào DB sai (vd medinet_central thay vì medinet_hub_yte) là data corruption silent disaster. Fail-fast exit 3 + operator review env wire trước retry."
  - "Row count sanity check tolerance — KHÔNG strict per-table (±5%) vì INSERT statements aggregate 5 table khó tách. Chỉ check TOTAL > 0 nếu EXPECTED_INSERTS > 0. Avoid false-positive cho hub empty legitimate."
  - "Per-hub Alembic head SHA verify WARN-only thay vì block — Rationale: schema mismatch sau 0001..0005 sẽ làm psql -f FAIL (CHECK constraint / FK violation) với ON_ERROR_STOP=1 catch immediate. Pre-check WARN giúp operator debug nhanh nhưng KHÔNG block restore."
  - "Rollback flag --rollback semantics: stop container thay vì revert Caddyfile — Phase 5 dynamic regex implies KHÔNG có Caddyfile state để revert; container down → Caddy regex fall-through file_server 404 user-visible signal. T-07-02-04 accept disposition (intentional behavior)."
  - "Exit codes 0/2/3/4/5 distinct semantic (02-restore-hub.sh) + 0/2/3/4 (03-switch-caddy.sh) — Parent script Plan 07-05 05-smoke-e2e.sh có thể branch theo exit code: 3 (snapshot miss / container down → operator gate) vs 4 (psql / caddy fail → ops escalate) vs 5 (row count → snapshot integrity issue)."

patterns-established:
  - "Plan 07-02 pair pattern — Restore + Switch-Caddy hai script luôn invoke cùng nhau cho blue/green per-hub procedure. Operator workflow: 02-restore-hub.sh <HUB> → 03-switch-caddy.sh <HUB> → 05-smoke-e2e.sh <HUB>. Rollback: 03-switch-caddy.sh <HUB> --rollback (1-flag rollback đủ — KHÔNG cần revert restore vì DB hub con isolated)."
  - "VERIFY-ONLY mode post Phase 5 dynamic regex pattern — Future migration milestone (v4.0 sub-hub split per project_v3_multi_hub_split.md seed memory) reuse pattern này nếu Caddy regex tiếp tục dynamic capture. KHÔNG sed edit Caddyfile cho hub-scoped routing."
  - "current_database() verify match T-07-02-03 — Pattern reusable cho future DB-touching script trong v4.0+ (vd sub-hub split restore vào medinet_sub_hub_<X> phải verify current_database() match đúng)."

threat_coverage:
  - "T-07-02-01 Tampering hub_name arg (mitigate): Regex ^[a-z][a-z0-9_]{0,15}$ + RESERVED blacklist 6 name + reject 'central' explicit TRƯỚC pass vào psql -c / docker compose / curl URL build (T-5-05 carry forward — KHÔNG inject shell via hub_name)"
  - "T-07-02-02 Tampering snapshot .sql file path traversal (mitigate): Path constrain ${REPO_ROOT}/migrate-snapshots/migrate-<hub>-*.sql qua REPO_ROOT 3-tier fallback + ls -1 glob limit + [ -r FILE ] readable check TRƯỚC psql -f"
  - "T-07-02-03 Information Disclosure restore vào DB sai (mitigate STRONG): psql -tA -c \"SELECT current_database()\" verify match medinet_hub_<HUB> TRƯỚC psql -f restore; fail-fast exit 3 nếu mismatch (vd DSN sai trỏ medinet_central). KHÔNG cho phép data corruption silent."
  - "T-07-02-04 DoS rollback stop container (accept): Rollback intentional behavior — operator explicit `--rollback` flag; Caddy regex fall-through file_server → SPA 404 user-visible là signal đúng cho switch revert. Acceptable risk first migration."
  - "T-07-02-05 Repudiation restore KHÔNG có audit trail (accept): Phase 7 Plan 07-03 sẽ INSERT audit_logs cho truncate central skeleton; restore là forward-only load operation — acceptable risk first migration v3.0. Snapshot file naming `migrate-<hub>-<YYYY-MM-DD>.sql` immutable timestamp đủ Repudiation evidence chain."

requirements-completed: [MIGRATE-02]

metrics:
  duration_minutes: 4
  tasks_completed: 2  # Task 1 restore script + Task 2 switch-caddy verify-only script
  files_created: 3  # 02-restore-hub.sh + 03-switch-caddy.sh + SUMMARY.md
  files_modified: 0  # KHÔNG modify file hiện hữu
  tests_added: 0  # Bash-only — bash -n syntax + 21 grep acceptance (10 Task 1 + 11 Task 2) — KHÔNG unit/integration test runtime

date_completed: 2026-05-23
---

# Phase 7 Plan 07-02: Restore Snapshot + Switch Caddy Verify-Only Summary

**Hai bash script `02-restore-hub.sh` (psql restore 4-step) + `03-switch-caddy.sh` (VERIFY-ONLY 3-step) implement blue/green per-hub procedure step 3-5 (D-V3-Phase7-B LOCKED). Foundation BLOCKING cho Plan 07-04 + 07-05.**

## Performance

- **Duration:** 4 phút (~4 phút thực tế)
- **Started:** 2026-05-23T05:25:23Z
- **Completed:** 2026-05-23T05:29:22Z
- **Tasks:** 2/2 (Task 1 restore script + Task 2 switch-caddy verify-only)
- **Files created:** 3 (02-restore-hub.sh 225 LOC + 03-switch-caddy.sh 132 LOC + SUMMARY.md)
- **Files modified:** 0

## Accomplishments

- **Script `scripts/migrate/02-restore-hub.sh` (225 LOC)** — Bash strict mode + hub name validation chain (regex `^[a-z][a-z0-9_]{0,15}$` + RESERVED blacklist 6 name + reject central) + 4-step pipeline (auto-detect latest snapshot qua `ls -1 ... | sort -r | head -1` + verify target DB exist `pg_database` + current_database() match TRƯỚC restore (T-07-02-03 mitigation) + alembic_version warn-only + psql -v ON_ERROR_STOP=1 -f restore + post-restore SELECT COUNT chunks/documents/users sanity check) + exit codes 0/2/3/4/5 semantic distinct.
- **Script `scripts/migrate/03-switch-caddy.sh` (132 LOC)** — VERIFY-ONLY mode (per CONTEXT.md `<specifics>` correction 2026-05-23 — Caddyfile `{re.hub_api.1}` dynamic regex Phase 5 PROXY-01 đã handle routing) + 3-step pipeline (docker compose ps verify `python-api-<HUB>` running + caddy validate Pitfall 7 mitigation + curl smoke `https://${WIKI_PUBLIC_DOMAIN}/<HUB>/api/health` warn-only) + `--rollback` flag → `docker compose stop python-api-<HUB>` (Caddy regex fall-through file_server 404 T-07-02-04 accept) + hub name validation chain T-5-05 + exit codes 0/2/3/4 semantic distinct.
- **Blue/green per-hub procedure step 3-5 implementable end-to-end** — Operator workflow: `01-snapshot-hubs.sh` (Plan 07-01) → `02-restore-hub.sh <HUB>` → `03-switch-caddy.sh <HUB>` → `05-smoke-e2e.sh <HUB>` (Plan 07-05). Rollback path: `03-switch-caddy.sh <HUB> --rollback` (1-flag, 30-day snapshot retention enable rollback restore từ snapshot cũ nếu cần).
- **Foundation BLOCKING resolved** cho Plan 07-03 (04-truncate-central.sh chỉ truncate central skeleton SAU 3 hub PASS smoke qua script này) + Plan 07-04 (06-mcp-smoke.md runbook reference rollback procedure) + Plan 07-05 (05-smoke-e2e.sh consume smoke endpoint pattern + rollback documentation).

## Task Commits

Each task was committed atomically:

1. **Task 1: Tạo scripts/migrate/02-restore-hub.sh psql restore snapshot blue/green** — `81256fc` (feat)
2. **Task 2: Tạo scripts/migrate/03-switch-caddy.sh VERIFY-ONLY (Caddyfile KHÔNG sed edit)** — `f1556cc` (feat)

**Plan metadata commit (SUMMARY.md + STATE.md + ROADMAP.md + REQUIREMENTS.md):** TBD (final docs commit)

## Files Created

- `Hub_All/scripts/migrate/02-restore-hub.sh` — psql restore snapshot blue/green (225 LOC bash, executable, syntax PASS `bash -n` exit 0)
- `Hub_All/scripts/migrate/03-switch-caddy.sh` — Caddy verify-only post Phase 5 dynamic regex (132 LOC bash, executable, syntax PASS `bash -n` exit 0)
- `.planning/phases/07-migration-smoke-e2e/07-02-SUMMARY.md` — File này (closeout SUMMARY)

## Decisions Made

- **Verify-only mode cho `03-switch-caddy.sh`** (per CONTEXT.md `<specifics>` correction 2026-05-23) — Phase 5 Caddyfile `{re.hub_api.1}` dynamic regex đã handle routing tự động dựa URL prefix; Phase 7 chỉ cần verify `python-api-<HUB>` container actually running + Caddy auto-route đúng. Shrink complexity ~50%, ít error-prone hơn sed approach.
- **Pattern hub_name validation chain carry forward T-5-05** — Regex `^[a-z][a-z0-9_]{0,15}$` + RESERVED blacklist 6 name + reject `central` explicit. Consistency với 9-step pipeline Phase 5 + Phase 2 FACTOR-04 + Plan 07-01.
- **Auto-detect latest snapshot qua `ls -1 ... | sort -r | head -1`** — Operator UX simpler (rerun với cùng arg sau debug); snapshot naming convention `migrate-<hub>-<YYYY-MM-DD>.sql` (immutable timestamp T-07-01-04) đảm bảo sort -r reverse-chronological deterministic.
- **`current_database()` verify match T-07-02-03 strong (KHÔNG warn-only)** — Restore vào DB sai (vd `medinet_central` thay vì `medinet_hub_yte`) là data corruption silent disaster. Fail-fast exit 3 + operator review env wire trước retry.
- **Row count sanity check tolerance KHÔNG strict per-table** — INSERT statements aggregate 5 table khó tách per-table tolerance ±5%. Chỉ check TOTAL > 0 nếu EXPECTED_INSERTS > 0. Avoid false-positive cho hub empty legitimate case.
- **Per-hub Alembic head SHA verify WARN-only thay vì block** — Schema mismatch sau 0001..0005 sẽ làm `psql -f` FAIL với ON_ERROR_STOP=1 catch immediate; pre-check WARN giúp operator debug nhanh nhưng KHÔNG block restore.
- **Rollback flag `--rollback` semantics: stop container thay vì revert Caddyfile** — Phase 5 dynamic regex implies KHÔNG có Caddyfile state để revert; container down → Caddy regex fall-through file_server 404 user-visible signal. T-07-02-04 accept disposition.
- **Exit codes semantic distinct** (02-restore-hub.sh: 0/2/3/4/5; 03-switch-caddy.sh: 0/2/3/4) — Parent script Plan 07-05 05-smoke-e2e.sh có thể branch theo exit code distinguishing: snapshot miss / container down / psql fail / caddy fail / row count mismatch.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] psql command flag order fix để match acceptance criteria grep pattern**
- **Found during:** Task 1 verification — initial grep acceptance check returned `psql -v ON_ERROR_STOP=1` count: 1 (expected ≥4).
- **Issue:** 5 lệnh psql trong script viết `psql -tA -v ON_ERROR_STOP=1` (theo Phase 1 hub-init.sh pattern), nhưng acceptance criteria grep strict `psql -v ON_ERROR_STOP=1` chỉ match flag order `-v` ngay sau `psql`.
- **Fix:** Đổi 5 lệnh psql từ `psql -tA -v ON_ERROR_STOP=1` thành `psql -v ON_ERROR_STOP=1 -tA`. Functional equivalent (flag order trong psql KHÔNG matter — cùng kết quả -t tuples-only + -A unaligned). Match acceptance criteria pattern.
- **Files modified:** `Hub_All/scripts/migrate/02-restore-hub.sh` (5 vị trí — DB_EXISTS / CURRENT_DB / ALEMBIC_HEAD / ACTUAL_CHUNKS / ACTUAL_DOCS / ACTUAL_USERS)
- **Commit:** Included trong Task 1 commit `81256fc` (single atomic — fix trước khi initial commit)

**Total deviations:** 1 (Rule 1 inline fix — KHÔNG block plan execution, acceptance criteria 10/10 + 11/11 PASS post-fix)
**Impact on plan:** None — clean execution per planner spec sau Rule 1 inline fix.

## Issues Encountered

- **Git CRLF warning** trên both commit — `warning: in the working copy ..., LF will be replaced by CRLF the next time Git touches it`. Bash script file ship với LF (Unix-correct) — Git auto-convert CRLF khi checkout Windows. KHÔNG block, expected Windows behavior (carry forward Plan 07-01).
- **Acceptance criteria grep pattern flag order** — Task 1 initial implementation theo Phase 1 hub-init.sh convention `psql -tA -v ON_ERROR_STOP=1` nhưng acceptance criteria pattern strict `psql -v ON_ERROR_STOP=1`. Fix qua Rule 1 inline reorder flag — functional equivalent. (Note: future scripts nên match acceptance pattern từ đầu nếu writer agent biết spec).

## SCOPE LIMIT executor honored

Per objective `<scope_limit>` Executor tạo scripts, KHÔNG chạy migration thật:

- ✅ `bash -n Hub_All/scripts/migrate/02-restore-hub.sh` exit 0 (syntax check mandatory)
- ✅ `bash -n Hub_All/scripts/migrate/03-switch-caddy.sh` exit 0 (syntax check mandatory)
- ✅ KHÔNG actually run `psql` against real `medinet_hub_<HUB>` DB
- ✅ KHÔNG actually run `docker compose` against live infra
- ✅ KHÔNG actually invoke `caddy validate` / `caddy reload` against running Caddy
- ✅ KHÔNG actually `curl` against `${WIKI_PUBLIC_DOMAIN}`
- ✅ Verify scripts via syntax + 21 grep acceptance criteria PASS (10 Task 1 + 11 Task 2) — KHÔNG runtime execution
- ✅ 03-switch-caddy.sh VERIFY-ONLY semantics confirmed: 0 actual sed command lines + 0 mv Caddyfile command (sed/Caddyfile mentions chỉ trong comment giải thích)

**Runtime execution defer Phase 7 Plan 07-05 MIGRATE-05** (full E2E 3 hub × 7-step golden path + central + JWT SSO live + cross-hub search live + per-hub branding visual diff).

## Next Plan Readiness

- **Plan 07-03 READY** — `04-truncate-central.sh` chỉ truncate central skeleton SAU 3 hub PASS smoke qua 02-restore-hub.sh + 03-switch-caddy.sh + 05-smoke-e2e.sh chain. Foundation pair này đủ blue/green procedure step 3-5.
- **Plan 07-04 READY** — `06-mcp-smoke.md` runbook reference rollback procedure (`03-switch-caddy.sh <HUB> --rollback` + snapshot 30-day retention restore).
- **Plan 07-05 READY** — `05-smoke-e2e.sh` consume smoke endpoint pattern `https://${WIKI_PUBLIC_DOMAIN}/<HUB>/api/health` từ 03-switch-caddy.sh + rollback procedure documentation trong README.md NEW section "Migration + Smoke E2E Runbook (Phase 7 v3.0)".

**No blockers.** Wave 2 BLOCKING phase complete; 3 plan sau (Plan 07-03..07-05) có thể proceed sequential.

## Acceptance Criteria Verification

**Task 1 — `02-restore-hub.sh` (10 grep checks PASS):**

| # | Check | Expected | Result |
|---|-------|----------|--------|
| 1 | `bash -n` exit 0 | PASS | ✅ PASS |
| 2 | `set -euo pipefail` count | ≥ 1 | 1 ✅ |
| 3 | `psql -v ON_ERROR_STOP=1` count | ≥ 4 | 7 ✅ |
| 4 | `medinet_hub_` count | ≥ 2 | 4 ✅ |
| 5 | `current_database()` count | ≥ 1 | 5 ✅ |
| 6 | `SELECT COUNT(*) FROM chunks` count | ≥ 1 | 1 ✅ |
| 7 | `RESERVED_NAMES` count | ≥ 1 | 3 ✅ |
| 8 | `migrate-snapshots` count | ≥ 1 | 3 ✅ |
| 9 | `ON_ERROR_STOP=1` count | ≥ 4 | 9 ✅ |
| 10 | Line 1 = `#!/usr/bin/env bash` | exact | ✅ PASS |

**Task 2 — `03-switch-caddy.sh` (11 checks PASS):**

| # | Check | Expected | Result |
|---|-------|----------|--------|
| 1 | `bash -n` exit 0 | PASS | ✅ PASS |
| 2 | `set -euo pipefail` count | ≥ 1 | 1 ✅ |
| 3 | `caddy validate` count | ≥ 1 | 5 ✅ |
| 4 | `docker compose ps python-api-` count | ≥ 1 | 1 ✅ |
| 5 | `"State":"running"` count | ≥ 2 | 3 ✅ |
| 6 | `WIKI_PUBLIC_DOMAIN` count | ≥ 1 | 1 ✅ |
| 7 | `curl -k` count | ≥ 1 | 3 ✅ |
| 8 | `--rollback` count | ≥ 2 | 3 ✅ |
| 9 | `docker compose stop` count | ≥ 1 | 1 ✅ |
| 10 | VERIFY-ONLY (no actual sed exec) | 0 sed command lines | ✅ PASS (sed mentions chỉ comment) |
| 11 | Line 1 = `#!/usr/bin/env bash` | exact | ✅ PASS |

**Min lines target:**

| File | Expected min_lines | Actual LOC | Result |
|------|-------------------|------------|--------|
| `02-restore-hub.sh` | 130 | 225 | ✅ +73% headroom |
| `03-switch-caddy.sh` | 80 | 132 | ✅ +65% headroom |

## Self-Check: PASSED

**Files exist:**
- ✅ `Hub_All/scripts/migrate/02-restore-hub.sh` (FOUND, 225 LOC, executable)
- ✅ `Hub_All/scripts/migrate/03-switch-caddy.sh` (FOUND, 132 LOC, executable)
- ✅ `.planning/phases/07-migration-smoke-e2e/07-02-SUMMARY.md` (FOUND, file này)

**Commits exist:**
- ✅ `81256fc` (feat Task 1 — 02-restore-hub.sh psql restore snapshot blue/green)
- ✅ `f1556cc` (feat Task 2 — 03-switch-caddy.sh verify-only post Phase 5 dynamic regex)

---

*Phase: 07-migration-smoke-e2e*
*Plan: 02 — Restore Snapshot + Switch Caddy Verify-Only (Wave 2 BLOCKING)*
*Completed: 2026-05-23*
*Foundation BLOCKING resolved cho Plan 07-03..07-05.*
