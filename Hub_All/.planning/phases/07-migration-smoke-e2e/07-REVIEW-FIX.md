---
phase: 07-migration-smoke-e2e
fixed_at: 2026-05-23T00:00:00Z
review_path: Hub_All/.planning/phases/07-migration-smoke-e2e/07-REVIEW.md
iteration: 1
findings_in_scope: 7
fixed: 7
skipped: 0
status: all_fixed
---

# Phase 7: Code Review Fix Report

**Fixed at:** 2026-05-23
**Source review:** `Hub_All/.planning/phases/07-migration-smoke-e2e/07-REVIEW.md`
**Iteration:** 1

**Summary:**

- Findings in scope: 7 (1 Critical CR-01 + 6 Warning WR-01..06)
- Fixed: 7
- Skipped: 0
- 5 Info findings (IN-01..05) **out-of-scope** theo `fix_scope=critical_warning` — KHÔNG xử lý đợt này.

## Fixed Issues

### CR-01: SQL injection vector qua heredoc string interpolation (DEPENDS ON regex validation)

**Files modified:** `Hub_All/scripts/migrate/01-snapshot-hubs.sh`, `Hub_All/scripts/migrate/02-restore-hub.sh`, `Hub_All/scripts/migrate/04-truncate-central.sh`
**Commit:** `6374741`
**Applied fix:** Defense-in-depth approach (alternative trong REVIEW Fix section) — re-validate UUID v4 format strict regex `^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$` SAU khi resolve HUB_ID từ `medinet_central.hubs` TRƯỚC khi interpolate vào pg_dump `--where` (01) / psql `-d` arg + heredoc `WHERE datname` (02 — validate composed TARGET_DB format `^medinet_hub_[a-z][a-z0-9_]{0,15}$`) / psql heredoc DELETE+INSERT 4 table (04). Nếu DB row corrupt hoặc psql output có warning prefix lẫn vào stdout, regex reject + return error code 3 thay vì cho phép SQL injection qua `'${HUB_ID}'` shell-expand. Chọn defense-in-depth thay vì `psql -v var=val` + `:'varname'` binding để giữ scope nhỏ (single-line check per script) + giữ pattern heredoc đang dùng — migrate sang `-v` binding có thể là follow-up commit. D-V3-02 chunks PRESERVED + dry-run default ON + envelope D6 jq parse + bash `set -euo pipefail` UNCHANGED.

**Note (logic verification):** Fix là defense-in-depth check format only — KHÔNG đổi semantic SQL hay logic flow. Tier 1 + Tier 2 bash syntax check PASS đủ. KHÔNG cần human re-verify logic.

### WR-01: Silent false-pass khi `LATENCY_MS` không phải integer

**Files modified:** `Hub_All/scripts/migrate/05-smoke-e2e.sh`
**Commit:** `d7a24a5`
**Applied fix:** Áp dụng exact fix theo REVIEW — thêm regex pre-check `^[0-9]+$` TRƯỚC `[ -gt ]` compare. Reject non-integer với explicit FAIL message "envelope meta.latency_ms malformed". Loại bỏ `2>/dev/null` masking trên `[ -gt ]`. Strict integer enforcement.

### WR-02: `pg_dump` mix stderr + stdout vào output file → sanity check sai

**Files modified:** `Hub_All/scripts/migrate/01-snapshot-hubs.sh`
**Commit:** `6f1b6a8`
**Applied fix:** Áp dụng exact fix theo REVIEW — đổi `> OUT_FILE 2>&1` thành `> OUT_FILE 2> ERR_FILE` tách stderr ra file riêng `${OUT_FILE}.stderr`. Happy path empty stderr → rm; non-empty (warning) → giữ debug + WARN log. FAIL path → print stderr indent 4 space + cleanup both file + return 4. Đảm bảo psql restore Plan 07-02 KHÔNG bị nhiễm warning text + grep INSERT count chuẩn.

### WR-03: `ROW_COUNT=$(grep -c ... || echo "0")` luôn trả non-zero

**Files modified:** `Hub_All/scripts/migrate/01-snapshot-hubs.sh`, `Hub_All/scripts/migrate/02-restore-hub.sh`
**Commit:** `e4cdbbc`
**Applied fix:** Áp dụng exact fix theo REVIEW cho cả 2 file.
- `01-snapshot-hubs.sh:159` — thêm explicit `[ ! -f "$OUT_FILE" ]` check post pg_dump (return 4 fail-loud nếu missing); anchor regex `^INSERT INTO ` (có space, chặt hơn); `|| true` thay `|| echo "0"` + `${ROW_COUNT:-0}` fallback.
- `02-restore-hub.sh:117` — anchor regex `^INSERT INTO ` + `|| true` + `${EXPECTED_INSERTS:-0}` fallback. SNAPSHOT_FILE đã check exist line 103-107 nên không thêm file-exist guard duplicate.

### WR-04: `read -r CONFIRM` không có timeout — block CI/automation

**Files modified:** `Hub_All/scripts/migrate/04-truncate-central.sh`
**Commit:** `561451b`
**Applied fix:** Áp dụng exact fix theo REVIEW — `read -r -t 60 CONFIRM` timeout 60s. Cancel/timeout → `exit 2` distinct từ success 0. Explicit hint "--yes flag for automation" trong error message. `--yes` flag (line 73) UNCHANGED. Operator workflow phân biệt được user-declined (exit 2) vs success (exit 0) vs psql fail (exit 4) vs hub_id resolve miss (exit 3).

### WR-05: `psql -f restore` output piped vào `tail -20` mask exit code

**Files modified:** `Hub_All/scripts/migrate/02-restore-hub.sh`
**Commit:** `6638eab`
**Applied fix:** Áp dụng exact fix theo REVIEW — capture full psql output ra log file `${REPO_ROOT}/migrate-snapshots/.restore-${HUB}-$(date +%Y%m%d-%H%M%S).log` (timestamp prevent collision). Bỏ pipe trong `if !` — exit code psql clean KHÔNG depend on `pipefail`. FAIL branch: print last 20 lines (sed indent 4 space) + full log path + snapshot debug path. Success branch: log path printed cho operator audit.

### WR-06: REPO_ROOT detect fallback `(pwd)` trong `05-smoke-e2e.sh` mask config error

**Files modified:** `Hub_All/scripts/migrate/05-smoke-e2e.sh`
**Commit:** `09daf06`
**Applied fix:** Áp dụng exact fix theo REVIEW — extend pattern 3-tier với fallback `../docker-compose.yml` (đồng nhất với `01-snapshot-hubs.sh` / `02-restore-hub.sh` / `04-truncate-central.sh`). Else branch exit 2 với explicit error message "KHÔNG tìm thấy docker-compose.yml" + hint "Chạy từ repo root hoặc Hub_All/ directory" thay vì silent `REPO_ROOT=$(pwd)` fall-through gây confusing fixture lookup FAIL message.

## Out-of-scope (Info — skipped by fix_scope=critical_warning)

5 Info finding sau KHÔNG được fix đợt này (orchestrator scope `critical_warning` only):

- **IN-01** `validate_hub_name` duplicate inline `02-restore-hub.sh` + `03-switch-caddy.sh` (refactor sang `scripts/migrate/lib/validate-hub.sh` shared) — defer Phase 7 follow-up hoặc v3.1.
- **IN-02** `central` reject logic duplicate 4 lần — defer cùng IN-01.
- **IN-03** `06-mcp-smoke.md` reference path `localhost:8190` (mcp_service KHÔNG map port host) + `localhost:8180/metrics` (python-api-central, không phải mcp_service) cần clarify — defer doc-only update.
- **IN-04** `01-snapshot-hubs.sh:137` comment "5 table" misleading vs `04-truncate-central.sh` chỉ DELETE 4 table — defer comment cosmetic.
- **IN-05** `migrate-snapshots/README.md:69` recovery procedure dùng `psql -f` raw thay vì `02-restore-hub.sh` (bypass current_database verify + row count sanity + alembic verify) — defer doc-only update.

Khuyến nghị orchestrator schedule second-pass `fix_scope=all` nếu Info findings cần đóng trước v3.0 milestone archive — đặc biệt IN-05 (operator runbook safety) ưu tiên hơn IN-01..04 (DRY refactor + comment + doc clarify).

## Verification summary

- 3-tier verification ALL PASS per fix:
  - Tier 1: Re-read modified file section — fix text confirmed, surrounding code intact (KHÔNG corruption).
  - Tier 2: `bash -n <file>` syntax check PASS cho 4 file shell mỗi lần edit.
  - Tier 3: KHÔNG cần fallback (Tier 2 PASS đủ).
- Bash strict mode `set -euo pipefail` UNCHANGED toàn bộ 4 file.
- D-V3-02 invariant (chunks PRESERVED) UNCHANGED — `04-truncate-central.sh` heredoc DELETE 4 table (documents/users/audit_logs/usage_events) preserve `chunks` skip.
- Dry-run default ON UNCHANGED — `04-truncate-central.sh:34` `MODE="--dry-run"`.
- Hub validation chain (regex + RESERVED + reject central) UNCHANGED 4 script.
- Envelope D6 jq parse pattern UNCHANGED `05-smoke-e2e.sh::assert_envelope_success`.

## Commits (7 atomic)

| # | Finding | Commit | Files |
|---|---------|--------|-------|
| 1 | CR-01 | `6374741` | `01-snapshot-hubs.sh` + `02-restore-hub.sh` + `04-truncate-central.sh` |
| 2 | WR-01 | `d7a24a5` | `05-smoke-e2e.sh` |
| 3 | WR-02 | `6f1b6a8` | `01-snapshot-hubs.sh` |
| 4 | WR-03 | `e4cdbbc` | `01-snapshot-hubs.sh` + `02-restore-hub.sh` |
| 5 | WR-04 | `561451b` | `04-truncate-central.sh` |
| 6 | WR-05 | `6638eab` | `02-restore-hub.sh` |
| 7 | WR-06 | `09daf06` | `05-smoke-e2e.sh` |

---

_Fixed: 2026-05-23_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
