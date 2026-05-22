---
phase: 05-reverse-proxy-frontend-subpath
plan: 05
subsystem: infra
tags: [scripts, hub-add, caddy-reload, factor-04-extend, proxy-01, v3.0, phase5, bash, sed-atomic]

# Dependency graph
requires:
  - phase: 02-hub-con-codebase-factor
    provides: "hub-add.sh 7-step pipeline (FACTOR-04 dynamic hub registration) + RESERVED_HUB_NAMES blacklist + regex validate `^[a-z][a-z0-9_]{0,15}$` (T-5-05 mitigation carry forward)"
  - phase: 05-reverse-proxy-frontend-subpath
    provides: "Plan 05-01 .env.example HUBS_ALLOWLIST + HUBS_ALLOWLIST_REGEX + WIKI_PUBLIC_DOMAIN + Caddyfile wiki block path_regexp matcher (step 8 consumes; step 9 reload target)"
provides:
  - "hub-add.sh 9-step pipeline (Plan 02-05 7-step + Phase 5 step 8 .env HUBS_ALLOWLIST atomic update + step 9 Caddy PRE-validate + reload + smoke)"
  - "Idempotent step 8 — sed-edit qua tmp file + mv, preserve other env vars, skip duplicate hub"
  - "Pitfall 7 mitigation — caddy validate TRƯỚC reload tránh silent rollback"
  - "Zero-downtime Caddy reload qua admin API (docker compose exec caddy caddy reload)"
  - "Post-reload smoke check curl -k https://${WIKI_PUBLIC_DOMAIN}/${HUB}/api/health (warn-only)"
  - "Dev pre-up tolerance — caddy container chưa running → skip reload với hint message"
affects: [phase-05-plan-06-closeout, phase-07-migrate-05-runtime-e2e]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Atomic sed-edit qua tmp file + mv (preserve other .env vars khi update 1 key)"
    - "sed delimiter `|` thay `/` để tránh collision với pipe trong REGEX value"
    - "Idempotent duplicate detect qua `[[ \",${LIST}, \" == *\",${ITEM}, \"* ]]` bash idiom"
    - "PRE-validate config TRƯỚC reload (Pitfall 7 — Caddy silent rollback mitigation)"
    - "Container state check qua `docker compose ps caddy --format json | grep running` (dev pre-up tolerance)"
    - "Smoke check warn-only (non-200 không abort — backend container có thể chưa up)"
    - "trap cleanup tmp file on EXIT (POSIX cleanup pattern)"

key-files:
  created: []
  modified:
    - "Hub_All/api/scripts/hub-add.sh (mở rộng 238 → 365 dòng, +137/-10)"

key-decisions:
  - "Insert step 8 + 9 TRƯỚC dòng `[hub-add] DONE` — đảm bảo DONE message in cuối cùng sau 9 step complete"
  - "sed delimiter `|` (KHÔNG `/`) để regex value `yte|duoc|hcns` không collide với delimiter — quan trọng khi update HUBS_ALLOWLIST_REGEX"
  - "Idempotent skip pattern `[[ \",${CURRENT_ALLOWLIST},\" == *\",${HUB},\"* ]]` — comma-padding tránh prefix match (vd `yte` match `yte_v2`)"
  - "Caddy validate PRE-reload (Pitfall 7) — caddy silent rollback nếu config invalid → operator KHÔNG biết failure"
  - "Dev pre-up tolerance — caddy container chưa running không abort, in hint message + continue (developer chưa start compose)"
  - "Smoke check curl warn-only — non-200/timeout không abort vì python-api-<hub> container có thể chưa up (separate concern từ Caddy registration)"
  - "T-5-05 carry forward strict — Step 1-3 Plan 02-05 (regex + RESERVED blacklist) KHÔNG relax; tất cả `${HUB}` interpolation step 8 + 9 đều quote"

patterns-established:
  - "9-step pipeline pattern — FACTOR-04 dynamic hub registration với reverse-proxy auto-reload integration"
  - "Atomic .env edit — tmp file + mv (KHÔNG sed -i in-place — race condition + atomicity concern cross-platform)"
  - "Zero-downtime reverse-proxy reload từ shell script — `docker compose exec` Caddy admin API thay vì restart container"

requirements-completed: [PROXY-01]

# Metrics
duration: ~12 min
completed: 2026-05-23
---

# Phase 5 Plan 05: hub-add.sh 9-step pipeline extension (PROXY-01 + FACTOR-04 carry forward) Summary

**hub-add.sh mở rộng từ 7-step → 9-step pipeline: step 8 idempotent atomic update .env HUBS_ALLOWLIST + HUBS_ALLOWLIST_REGEX qua tmp file + mv; step 9 Caddy PRE-validate (Pitfall 7 mitigation) + zero-downtime reload + smoke curl /<hub>/api/health với dev pre-up tolerance**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-05-23T18:15:00Z
- **Completed:** 2026-05-23T18:27:00Z
- **Tasks:** 2/2
- **Files modified:** 1 (`api/scripts/hub-add.sh` — +137 lines / -10 lines)

## Accomplishments

- **Step 8 (PROXY-01):** Idempotent atomic update `.env` cập nhật `HUBS_ALLOWLIST` (comma-separated) + `HUBS_ALLOWLIST_REGEX` (pipe-separated, auto-derive qua `tr ',' '|'`). Atomic qua `mktemp` → `sed` → `mv` (preserve other env vars). Duplicate detect skip nếu hub đã có trong allowlist. Fallback tạo `.env` từ `.env.example` nếu missing.
- **Step 9 (PROXY-01):** PRE-validate `docker compose exec caddy caddy validate --config /etc/caddy/Caddyfile` (Pitfall 7 mitigation tránh Caddy silent rollback nếu config invalid) → zero-downtime `caddy reload` qua admin API → sleep 1s settle → smoke `curl -k https://${WIKI_PUBLIC_DOMAIN:-localhost}/${HUB}/api/health` (warn-only). Dev pre-up tolerance: caddy container chưa running → skip reload với hint message.
- **T-5-05 carry forward strict guard:** Plan 02-05 Step 1-3 (regex `^[a-z][a-z0-9_]{0,15}$` + RESERVED_HUB_NAMES blacklist 6 name + duplicate detect) KHÔNG relax. Tất cả `${HUB}` interpolation trong step 8 + 9 đều quote.
- **Header docstring update:** "7-step pipeline" → "9-step pipeline (Phase 5 v3.0-05 PROXY-01 extend)"; step counter 1/7..7/7 → 1/9..7/9 cho consistency; thêm "T-5-05 mitigation" section ghi rõ carry forward Plan 02-05.

## Task Commits

Each task was committed atomically:

1. **Task 1: Append step 8 + step 9 vào hub-add.sh** — `6b282b8` (feat)
2. **Task 2: Dry-run + structural verify** — KHÔNG commit (read-only structural verify, không có file changes)

**Plan metadata:** (will be appended below — feat closeout commit + SUMMARY.md + STATE.md)

_Note: Task 2 là pure verification step (bash -n + grep structural check) — không có file modification nên không tạo commit riêng. Acceptance criteria PASS chứng cứ documented trong SUMMARY này._

## Files Created/Modified

- `Hub_All/api/scripts/hub-add.sh` — Mở rộng 9-step pipeline (Plan 02-05 7-step Phase 5 + step 8 .env atomic update + step 9 Caddy validate + reload + smoke); +137 lines / -10 lines; 238 → 365 dòng.

## Decisions Made

| Decision | Rationale |
|----------|-----------|
| Insert step 8 + 9 TRƯỚC dòng `DONE` | DONE message phải in cuối cùng sau 9 step complete để operator biết toàn bộ pipeline thành công. |
| sed delimiter `\|` thay `/` | REGEX value `yte\|duoc\|hcns` chứa pipe sẽ collide với delimiter `/` nếu sed pattern dùng `s/.../.../`. Dùng `s\|...\|...\|` an toàn. |
| Idempotent comma-padding match | Pattern `[[ ",${LIST}," == *",${ITEM},"* ]]` tránh prefix match (vd `yte` match `yte_v2`). Comma cả 2 đầu = exact boundary. |
| PRE-validate trước reload | Pitfall 7 — Caddy silent rollback old config nếu new invalid; operator KHÔNG biết failure. PRE-validate fail-fast với rollback instruction. |
| Dev pre-up tolerance | Developer có thể `make hub-add` TRƯỚC `docker compose up` — script KHÔNG abort, in hint message + continue (caddy reload sẽ apply tự nhiên khi compose up đọc .env mới). |
| Smoke check warn-only | python-api-<hub> container có thể chưa up khi register hub mới (separate concern từ Caddy registration). Non-200/timeout = WARN + hint, KHÔNG fail step 9. |
| T-5-05 NO relax | Plan 02-05 Step 1-3 (regex + RESERVED blacklist) là single source-of-truth security boundary. Phase 5 KHÔNG bypass / re-validate / soften — `$HUB` đã pass validate khi tới step 8. |

## Deviations from Plan

None — plan executed exactly as written.

Plan 05-05 spec rất chi tiết (RESEARCH.md đã có verbatim bash snippet ~85 dòng cho step 8 + 9). Implementation match 100% snippet — không cần auto-fix Rule 1/2/3.

## Acceptance Criteria PASS Table

### Task 1 acceptance (13/13 PASS)

| # | Criteria | Method | Result |
|---|----------|--------|--------|
| 1 | `bash -n` syntax check | `bash -n api/scripts/hub-add.sh` | PASS exit 0 |
| 2 | Step 8 header present | `grep -q "(8/9) Cap nhat .env HUBS_ALLOWLIST"` | PASS |
| 3 | Step 9 header present | `grep -q "(9/9) Caddy validate + reload"` | PASS |
| 4 | HUBS_ALLOWLIST_REGEX touched | `grep -q "HUBS_ALLOWLIST_REGEX"` | PASS |
| 5 | Caddy PRE-validate present | `grep -q "caddy validate --config /etc/caddy/Caddyfile"` | PASS |
| 6 | Caddy reload present | `grep -q "caddy reload --config /etc/caddy/Caddyfile"` | PASS |
| 7 | Curl smoke check | `grep -q "curl.*api/health"` | PASS |
| 8 | WIKI_PUBLIC_DOMAIN consume | `grep -q "WIKI_PUBLIC_DOMAIN"` | PASS |
| 9 | HUBS_ALLOWLIST → REGEX derive | `grep -q "tr ',' '\|'"` | PASS |
| 10 | trap cleanup on EXIT | `grep -q "trap.*rm -f"` | PASS |
| 11 | Regex carry forward Plan 02-05 | `grep -q '\[a-z\]\[a-z0-9_\]{0,15}'` | PASS |
| 12 | RESERVED blacklist carry forward | `grep -q "RESERVED_NAMES\|postgres"` | PASS |
| 13 | DONE message preserved cuối file | `tail -20 ... \| grep -q "DONE"` | PASS |

Bonus: `set -euo pipefail` preserved → PASS.

### Task 2 acceptance (5/5 PASS)

| # | Criteria | Method | Result |
|---|----------|--------|--------|
| 1 | bash syntax valid | `bash -n api/scripts/hub-add.sh` | PASS exit 0 |
| 2 | Step ordering 1→9 | `grep -nE "^# \([0-9]+/9\)"` returns 9 headers in order | PASS (1/9 → 9/9 all present) |
| 3 | Idempotent duplicate handling | sed range 229,290 contains "idempotent" or "skip env update" or "da co" | PASS |
| 4 | PRE-validate before reload semantic | `validate` at line 295 < `reload` at line 316 | PASS |
| 5 | Atomic .env edit pattern | `grep -qE "mktemp\|TMP_ENV"` | PASS |

## Issues Encountered

None — task chạy clean.

Lưu ý nhỏ: acceptance criteria gốc dùng `grep -B 2` cho PRE-validate check, nhưng do gap thực tế giữa `caddy validate` (line 295) và `caddy reload` (line 316) là 21 dòng (echo log + error rollback instructions giữa), nên dùng `grep -B 25` mới match. Đây là grep context window quirk — KHÔNG phải bug code. Semantic ordering (validate BEFORE reload) đã verify trực tiếp bằng line number comparison.

## Carry-Forward Notes

- **T-5-05 strict guard Plan 02-05 KHÔNG relax:** Phase 5 step 8 + 9 không bypass / re-validate / soften regex `^[a-z][a-z0-9_]{0,15}$` + RESERVED_HUB_NAMES blacklist. `$HUB` đã pass validate khi tới step 8 — tất cả interpolation quote `"${HUB}"`.
- **Live dry-run defer Phase 7 MIGRATE-05** per v3.0-b precedent (Plan 02-05 + 03-05 + 04-07 đều skip live smoke). Plan 05-05 chỉ verify script SYNTAX + STRUCTURE; live test runtime (actual `make hub-add HUB=phap_che` + Caddy reload + curl smoke với 3 hub) defer Phase 7 MIGRATE-05.
- **Settings hub_registry persistence defer Phase 6 SETTINGS-04:** Long-term hub allowlist sẽ ship `hub_registry` table ở `medinet_central` (central admin CRUD; hub con đọc TTL cache). Plan 05-05 hiện tại update `.env` HUBS_ALLOWLIST as source-of-truth — Phase 6 sẽ sync.
- **R-V3-2 mitigation:** Smoke regression frontend 11 trang defer Plan 05-06 closeout `checkpoint:human-action` (D-V3-Phase5-D4 manual checklist).

## Next Phase Readiness

Plan 05-05 ship Wave 4 — hub-add.sh 9-step pipeline ready. Operator chạy `make hub-add HUB=phap_che` sẽ tự register full chain:

1. DB layer (hub-init.sh)
2. docker-compose.override.yml append python-api-phap_che service block
3. .env HUBS_ALLOWLIST=yte,duoc,hcns,phap_che + HUBS_ALLOWLIST_REGEX=yte|duoc|hcns|phap_che
4. Caddy validate + reload zero-downtime
5. Smoke curl /phap_che/api/health (warn-only nếu backend chưa up)

**Next:** Plan 05-06 (closeout Wave 5) — depend cumulative Plan 05-01..05; cập nhật docs (CLAUDE.md + STATE.md + REQUIREMENTS.md + README.md) + smoke checkpoint manual checklist D-V3-Phase5-D4 (4 URL × 4 hub + 11 trang COMPAT-01 regression). PROXY-01..04 mark `[x]` complete + ROADMAP Phase 5 DONE.

## Self-Check

Verified:

- File `Hub_All/api/scripts/hub-add.sh` FOUND (365 dòng — pre-edit 238 dòng + 137 dòng step 8 + 9).
- Commit `6b282b8` FOUND in `git log --oneline -5`.

---
*Phase: 05-reverse-proxy-frontend-subpath*
*Completed: 2026-05-23*
