---
phase: 07-migration-smoke-e2e
reviewed: 2026-05-23T00:00:00Z
depth: standard
files_reviewed: 11
files_reviewed_list:
  - scripts/migrate/01-snapshot-hubs.sh
  - scripts/migrate/02-restore-hub.sh
  - scripts/migrate/03-switch-caddy.sh
  - scripts/migrate/04-truncate-central.sh
  - scripts/migrate/05-smoke-e2e.sh
  - scripts/migrate/06-mcp-smoke.md
  - scripts/migrate/fixtures/generate-sample.py
  - mcp_service/mcp_app/config.py
  - docker-compose.yml
  - migrate-snapshots/.gitignore
  - migrate-snapshots/README.md
findings:
  critical: 1
  warning: 6
  info: 5
  total: 12
status: issues_found
---

# Phase 7: Code Review Report

**Reviewed:** 2026-05-23
**Depth:** standard
**Files Reviewed:** 11
**Status:** issues_found

## Tóm tắt

Phase 7 v3.0 (final phase) ship 5 bash script DESTRUCTIVE + 1 runbook + 1 Python fixture generator + 1 MCP config re-point + 4 supporting file (docker-compose, .gitignore, README, REVIEW này). Đánh giá tổng thể:

**Điểm mạnh (positive findings — KHÔNG flagged):**

- D-V3-02 invariant CONFIRMED: `grep -n "DELETE FROM chunks" scripts/migrate/` returns 0 matches. `04-truncate-central.sh` chỉ DELETE 4 table (documents, users, audit_logs, usage_events) — chunks PRESERVED đúng theo D-V3-02 LOCKED.
- Dry-run default CONFIRMED: `04-truncate-central.sh` line 34 `MODE="--dry-run"` mặc định ON; operator phải pass `--apply` explicit + confirm prompt `'yes'` (line 73-85). `--yes` flag để skip prompt trong CI/automation.
- Audit non-repudiation CONFIRMED: line 178-193 INSERT audit_logs TRƯỚC DELETE trong cùng `BEGIN;...COMMIT;` transaction. Pre-DELETE row counts được capture vào `payload.row_count_*` của audit row đó (snapshot-in-jsonb pattern). Dry-run dùng `ROLLBACK` thay COMMIT — preserve atomicity contract.
- `audit_logs` self-preservation: line 207 `DELETE FROM audit_logs WHERE hub_id = '${HUB_ID}' AND action != 'migrate.truncate_hub'` — KHÔNG xoá row vừa INSERT (evidence chain preserved, T-07-03-03 mitigation).
- Hub name validation chain hoàn chỉnh: regex `^[a-z][a-z0-9_]{0,15}$` + RESERVED blacklist 6 names + explicit reject `central` được implement nhất quán 4 script (`01-snapshot-hubs.sh`, `02-restore-hub.sh`, `03-switch-caddy.sh`, `04-truncate-central.sh`).
- MCP signature carry forward: `mcp_service/mcp_app/server.py` `search_wiki(hub_id?)` + `ask_wiki(hub_id?)` UNCHANGED — chỉ `api_base_url` re-point central. Validator `_validate_base_url` enforce scheme http/https + host (SSRF mitigation T-08.2-01-T preserved).
- Secret hygiene PASS: KHÔNG hardcoded password/UUID trong script (env-driven). Default `medinet_dev_pwd` chỉ là dev fallback rõ ràng; production wire qua env `PGPASSWORD`/`POSTGRES_PASSWORD`. `migrate-snapshots/.gitignore` ignore `*.sql` (PII protection).
- Smoke envelope D6 parsing CORRECT: `assert_envelope_success()` line 80-95 parse `.success` + `.error.code` + `.error.message` đúng spec D6.

**Tồn tại:** 1 Critical (SQL injection vector dù mitigated bằng regex validation — vẫn nên fix theo defense-in-depth) + 6 Warning + 5 Info.

## Critical Issues

### CR-01: SQL injection vector qua heredoc string interpolation (DEPENDS ON regex validation)

**File:** `scripts/migrate/04-truncate-central.sh:183, 187-190, 197-201, 205-208, 212-216`
**File:** `scripts/migrate/01-snapshot-hubs.sh:118`
**File:** `scripts/migrate/02-restore-hub.sh:134, 146, 162`

**Issue:**
Toàn bộ 3 script dùng pattern `psql -c "SELECT ... WHERE hub_name='$HUB'"` HOẶC heredoc `WHERE hub_id = '${HUB_ID}'` để interpolate giá trị shell vào SQL string. Mặc dù `HUB` đã được validate bằng regex `^[a-z][a-z0-9_]{0,15}$` + RESERVED blacklist (mitigation hợp lệ cho hub name input), riêng `HUB_ID` UUID resolve được trust **toàn bộ** từ database query output mà KHÔNG re-validate trước khi interpolate vào SQL string thứ 2.

Cụ thể trong `04-truncate-central.sh`:
```bash
# line 143-146 — Resolve UUID từ DB (output coi như trusted)
HUB_ID=$(psql ... -c "SELECT id FROM hubs WHERE hub_name='$HUB' LIMIT 1" ...)

# line 173-219 — Interpolate vào heredoc SQL (KHÔNG re-validate UUID format)
psql ... <<-EOSQL
    INSERT INTO audit_logs ... VALUES (..., '${HUB_ID}', ...)
    DELETE FROM documents WHERE hub_id = '${HUB_ID}';
    ...
EOSQL
```

Threat model: nếu `medinet_central.hubs.id` cột bị corrupt (vd attacker có UPDATE quyền đã chèn UUID có chứa SQL meta-char) HOẶC psql output có warning prefix lẫn vào stdout (rare but possible — `-tA` flag mitigate), `${HUB_ID}` có thể chứa `'); DROP TABLE ...; --`.

Severity là **Critical** vì:
- Operator chạy script với role có DELETE permission rộng (PGUSER=medinet).
- Heredoc evaluate `${HUB_ID}` ở SHELL level TRƯỚC khi gửi tới psql — psql nhận raw SQL string đã được expand.
- 1 dòng SQL malicious sẽ COMMIT (hoặc ROLLBACK trong dry-run — dry-run KHÔNG bảo vệ vì attacker có thể inject `COMMIT;` overriding final ROLLBACK).

**Fix:**
Dùng psql parameter binding (`-v var=value` + `:'varname'` quoted reference) thay vì shell interpolation. Pattern này được psql sanitize tự động:

```bash
# Trong 04-truncate-central.sh truncate_one_hub:
psql -v ON_ERROR_STOP=1 \
    -h "$PGHOST" -p "$PGPORT" -U "$PGUSER_EFFECTIVE" \
    -d "$CENTRAL_DB" \
    -v hub_id_var="$HUB_ID" \
    -v hub_name_var="$HUB" \
    -v dry_run_var="$DRY_RUN_BOOL" \
    <<-EOSQL
    BEGIN;
    INSERT INTO audit_logs (user_id, action, target_type, target_id, payload)
    VALUES (
        NULL,
        'migrate.truncate_hub',
        'central_hub_rows',
        :'hub_id_var',
        jsonb_build_object(
            'hub_name', :'hub_name_var',
            'dry_run', :dry_run_var,
            ...
        )
    );
    DELETE FROM documents WHERE hub_id = :'hub_id_var';
    DELETE FROM users WHERE hub_id = :'hub_id_var';
    ...
EOSQL
```

Alternative (nếu muốn defense in depth nhanh): re-validate UUID format sau khi resolve TRƯỚC khi interpolate:

```bash
HUB_ID=$(psql ... -c "SELECT id FROM hubs WHERE hub_name='$HUB' LIMIT 1" ...)
# Defense in depth — UUID v4 format strict regex
if ! [[ "$HUB_ID" =~ ^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$ ]]; then
    echo "[truncate-central] ERROR: HUB_ID '$HUB_ID' không match UUID v4 format — abort."
    return 4
fi
```

Apply tương tự cho `01-snapshot-hubs.sh:118` (HUB_ID interpolate vào `pg_dump --where`) và `02-restore-hub.sh` (TARGET_DB + ALEMBIC_HEAD interpolate). Khuyến nghị Plan 07-03 follow-up commit fix toàn bộ 3 script bằng UUID regex validate + dần migrate sang `-v` binding.

## Warnings

### WR-01: Silent false-pass khi `LATENCY_MS` không phải integer

**File:** `scripts/migrate/05-smoke-e2e.sh:194-198`
**Issue:**
```bash
LATENCY_MS=$(echo "$CROSS_RESP" | jq -r '.meta.latency_ms // 9999')
if [ "$LATENCY_MS" -gt 1500 ] 2>/dev/null; then
    echo "  [smoke-e2e] FAIL cross-hub: latency ${LATENCY_MS}ms > 1500 (E-V3-2)"
    return 1
fi
```

Nếu `.meta.latency_ms` trả về string non-numeric (vd `"unknown"` hoặc float `123.45`), `[ -gt ]` raise error "integer expression expected", `2>/dev/null` nuốt error, `[` returns non-zero (false) → branch **skip FAIL check**. Step 5 PASS silent dù latency invalid.

**Fix:**
```bash
LATENCY_MS=$(echo "$CROSS_RESP" | jq -r '.meta.latency_ms // 9999')
# Strict integer validation
if ! [[ "$LATENCY_MS" =~ ^[0-9]+$ ]]; then
    echo "  [smoke-e2e] FAIL cross-hub: latency '$LATENCY_MS' không phải integer (envelope malformed)"
    return 1
fi
if [ "$LATENCY_MS" -gt 1500 ]; then
    echo "  [smoke-e2e] FAIL cross-hub: latency ${LATENCY_MS}ms > 1500 (E-V3-2)"
    return 1
fi
```

### WR-02: `pg_dump` mix stderr + stdout vào output file → sanity check sai

**File:** `scripts/migrate/01-snapshot-hubs.sh:138-154, 159`
**Issue:**
```bash
if ! pg_dump \
    -h "$PGHOST" ... \
    --where="hub_id = '$HUB_ID'" \
    "$SOURCE_DB" > "$OUT_FILE" 2>&1; then
    ...
fi
...
ROW_COUNT=$(grep -c '^INSERT' "$OUT_FILE" || echo "0")
```

`2>&1` redirect stderr vào `OUT_FILE` → file SQL bị nhiễm cảnh báo pg_dump (vd "WARNING: terminating connection...") lẫn vào giữa SQL → psql restore sẽ FAIL ON_ERROR_STOP=1 ở Plan 07-02. Đồng thời `grep -c '^INSERT'` có thể đếm sai nếu warning chứa "INSERT" text.

**Fix:**
```bash
# Tách stderr ra file riêng để debug, KHÔNG đẩy vào SQL output
local ERR_FILE="${OUT_FILE}.stderr"
if ! pg_dump \
    -h "$PGHOST" ... \
    --where="hub_id = '$HUB_ID'" \
    "$SOURCE_DB" > "$OUT_FILE" 2> "$ERR_FILE"; then
    echo "[snapshot-hubs] ERROR: pg_dump FAIL cho hub '$HUB'."
    echo "  stderr: $(cat "$ERR_FILE")"
    rm -f "$OUT_FILE" "$ERR_FILE"
    return 4
fi
# stderr empty trong happy path → rm; nếu non-empty → giữ để operator review
if [ ! -s "$ERR_FILE" ]; then
    rm -f "$ERR_FILE"
fi
```

### WR-03: `ROW_COUNT=$(grep -c ... || echo "0")` luôn trả non-zero

**File:** `scripts/migrate/01-snapshot-hubs.sh:159`
**File:** `scripts/migrate/02-restore-hub.sh:117`
**Issue:**
```bash
ROW_COUNT=$(grep -c '^INSERT' "$OUT_FILE" || echo "0")
```

Trong bash `$(...)` subshell, exit code của lệnh con bị nuốt; `||` chỉ trigger khi grep exit non-zero (0 matches). Với `set -euo pipefail`, nếu grep miss thì subshell trả `0` đúng. NHƯNG: khi `OUT_FILE` không tồn tại, `grep -c` fail với stderr "No such file" → fallback `0` ẩn lỗi thật.

Đồng thời, nếu output file chứa multi-line warning từ pg_dump bắt đầu bằng "INSERT" (extremely rare), count sai. Pattern an toàn hơn: dùng `wc -l` sau khi đã grep ra file riêng, HOẶC kiểm tra file tồn tại trước.

**Fix:**
```bash
if [ ! -f "$OUT_FILE" ]; then
    echo "[snapshot-hubs] ERROR: $OUT_FILE missing post pg_dump — abort."
    return 4
fi
ROW_COUNT=$(grep -c '^INSERT INTO' "$OUT_FILE" 2>/dev/null || true)
ROW_COUNT=${ROW_COUNT:-0}
```

Hoặc anchor regex chặt hơn `^INSERT INTO ` (có space) để KHÔNG match string trong COMMENT/WARNING.

### WR-04: `read -r CONFIRM` không có timeout — block CI/automation

**File:** `scripts/migrate/04-truncate-central.sh:79-85`
**Issue:**
```bash
printf "[truncate-central] Type 'yes' để confirm: "
read -r CONFIRM
if [ "$CONFIRM" != "yes" ]; then
    echo "[truncate-central] ABORTED — confirm fail."
    exit 0
fi
```

Nếu chạy trong CI/cron không có stdin (vd `bash 04-truncate-central.sh --apply` qua systemd), `read` block forever cho đến khi process timeout. `--yes` flag mitigation đã có (line 73), nhưng UX dễ nhầm: operator quên `--yes` → script hang silent.

Hơn nữa exit code `0` khi `CONFIRM != "yes"` là sai — operator abort intentionally nhưng caller workflow KHÔNG biết phân biệt success vs cancelled (orchestrator sẽ tiếp tục).

**Fix:**
```bash
# Timeout 60s + distinct exit code cho cancel
if ! read -r -t 60 CONFIRM; then
    echo "[truncate-central] ABORTED — read timeout 60s (no stdin? use --yes flag for automation)."
    exit 2
fi
if [ "$CONFIRM" != "yes" ]; then
    echo "[truncate-central] ABORTED — user declined."
    exit 2  # distinct from success (0)
fi
```

### WR-05: `psql -f restore` output piped vào `tail -20` mask exit code

**File:** `scripts/migrate/02-restore-hub.sh:176-184`
**Issue:**
```bash
if ! psql -v ON_ERROR_STOP=1 \
    -h "$PGHOST" -p "$PGPORT" -U "$PGUSER_EFFECTIVE" \
    -d "$TARGET_DB" \
    -f "$SNAPSHOT_FILE" 2>&1 | tail -20; then
    echo "[restore-hub] ERROR: psql restore FAIL cho hub '$HUB'."
    ...
fi
```

`set -euo pipefail` ON nên `pipefail` THEORETICALLY return exit code của leftmost non-zero command in pipe. Tuy nhiên `if !` evaluate exit của ENTIRE pipeline; `tail -20` luôn return 0 (read stdin successful), nên với `pipefail` đúng là return psql exit. Nhưng pattern này fragile — nếu một ngày `set +o pipefail` slip in, exit code của psql bị mask.

**Fix:** Capture stderr riêng để debug + KHÔNG dùng pipe trong `if !`:
```bash
local RESTORE_LOG="$REPO_ROOT/migrate-snapshots/.restore-${HUB}-$(date +%Y%m%d-%H%M%S).log"
if ! psql -v ON_ERROR_STOP=1 \
    -h "$PGHOST" -p "$PGPORT" -U "$PGUSER_EFFECTIVE" \
    -d "$TARGET_DB" \
    -f "$SNAPSHOT_FILE" > "$RESTORE_LOG" 2>&1; then
    echo "[restore-hub] ERROR: psql restore FAIL cho hub '$HUB'."
    echo "  Last 20 lines log:"
    tail -20 "$RESTORE_LOG"
    echo "  Full log: $RESTORE_LOG"
    exit 4
fi
```

### WR-06: REPO_ROOT detect fallback `(pwd)` trong `05-smoke-e2e.sh` mask config error

**File:** `scripts/migrate/05-smoke-e2e.sh:55-61`
**Issue:**
```bash
if [ -f "docker-compose.yml" ]; then
    REPO_ROOT="$(pwd)"
elif [ -f "Hub_All/docker-compose.yml" ]; then
    REPO_ROOT="$(pwd)/Hub_All"
else
    REPO_ROOT="$(pwd)"
fi
```

Cả 4 script khác (`01..04`) dùng 3-tier fallback ĐỒNG NHẤT + exit 2 nếu KHÔNG tìm thấy `docker-compose.yml`. Riêng `05-smoke-e2e.sh` else branch silent fall-through `REPO_ROOT=$(pwd)` → fixture lookup line 63 `FIXTURE="$REPO_ROOT/scripts/migrate/fixtures/sample-document.docx"` sẽ FAIL với message confusing thay vì rõ "wrong directory".

**Fix:** Sync pattern với 4 script kia:
```bash
if [ -f "docker-compose.yml" ]; then
    REPO_ROOT="$(pwd)"
elif [ -f "Hub_All/docker-compose.yml" ]; then
    REPO_ROOT="$(pwd)/Hub_All"
elif [ -f "../docker-compose.yml" ]; then
    REPO_ROOT="$(cd .. && pwd)"
else
    echo "[smoke-e2e] ERROR: KHÔNG tìm thấy docker-compose.yml."
    echo "  Chạy từ repo root hoặc Hub_All/ directory."
    exit 2
fi
```

## Info

### IN-01: `validate_hub_name` chỉ trong `01-snapshot-hubs.sh` + `04-truncate-central.sh` — `02`/`03` inline duplicate

**File:** `scripts/migrate/02-restore-hub.sh:45-66`
**File:** `scripts/migrate/03-switch-caddy.sh:41-60`
**Issue:** `01` và `04` đã refactor validation thành function `validate_hub_name()`; `02` và `03` duplicate logic inline. Risk: tương lai update regex (vd extend max length 16 → 32 char per future REQ) sẽ phải sửa 4 chỗ, dễ miss.

**Fix:** Tạo `scripts/migrate/lib/validate-hub.sh` shared, source vào 4 script. Defer follow-up commit nếu time tight (Phase 7 final phase — chấp nhận duplicate cho v3.0 closeout).

### IN-02: `central` reject logic duplicate 4 lần

**File:** `scripts/migrate/01-snapshot-hubs.sh:57-61`
**File:** `scripts/migrate/02-restore-hub.sh:62-66`
**File:** `scripts/migrate/03-switch-caddy.sh:56-60`
**File:** `scripts/migrate/04-truncate-central.sh:104-107`
**Issue:** Cùng pattern, error message khác nhau (đôi chỗ refer Plan 07-02 / 07-03 / 07-04 mismatched). Recommend consolidate vào shared lib (IN-01 fix song song).

**Fix:** Cùng IN-01.

### IN-03: `06-mcp-smoke.md` reference path 8190 dev native vs container

**File:** `scripts/migrate/06-mcp-smoke.md:45, 138, 143`
**Issue:**
- Line 45: `http://localhost:8190/` dev native — nhưng `docker-compose.yml:252-280` mcp_service KHÔNG map port host (`ports:` không khai báo). Operator chạy `docker compose up mcp_service` rồi browse `localhost:8190` sẽ FAIL.
- Line 138/143: `curl http://localhost:8180/metrics` — port 8180 là **python-api-central** host map (`docker-compose.yml:118`), KHÔNG phải mcp_service. Đoạn này nên clarify rằng metrics endpoint là của API service, KHÔNG phải MCP.

**Fix:** Sửa runbook:
```markdown
1. Inspector "Add Server" → MCP URL: `https://wiki.medinet.vn/mcp/` (prod via Caddy reverse proxy) HOẶC dev: chạy mcp_service native `uv run python -m mcp_app` ngoài Docker, sau đó `http://localhost:8190/` (Docker mcp_service KHÔNG map port host — chỉ access qua Caddy intra-network).
...
curl http://localhost:8180/metrics  # NOTE: 8180 = python-api-central host map, KHÔNG phải mcp_service
```

### IN-04: `01-snapshot-hubs.sh` line 137 misleading comment "5 table"

**File:** `scripts/migrate/01-snapshot-hubs.sh:137`
**Issue:**
```bash
echo "[snapshot-hubs] (2/3) pg_dump --data-only --where=\"hub_id='$HUB_ID'\" 5 table..."
```

Comment nói "5 table" — match với `--table=chunks/documents/users/audit_logs/usage_events` line 144-148 (đúng 5 table). Nhưng `04-truncate-central.sh` chỉ DELETE 4 table (chunks PRESERVED). Vô tình tạo confusion: tại sao snapshot 5 table nhưng truncate 4? Là **đúng** semantic (chunks vẫn cần snapshot để hub con DB có data, central preserve chunks cho cross-hub sync), nhưng nên comment rõ ràng hơn để future operator KHÔNG bị nhầm là bug.

**Fix:**
```bash
echo "[snapshot-hubs] (2/3) pg_dump --data-only --where=\"hub_id='$HUB_ID'\" 5 table..."
echo "                       (chunks INCLUDED — restore vào medinet_hub_<HUB>; central chunks preserved D-V3-02)"
```

### IN-05: `migrate-snapshots/README.md` recovery procedure refer wrong DB

**File:** `migrate-snapshots/README.md:69`
**Issue:**
```bash
psql -U medinet -d postgres -c "DROP DATABASE medinet_hub_yte;"
bash api/scripts/hub-init.sh yte
psql -U medinet -d medinet_hub_yte -f migrate-snapshots/migrate-yte-<date>.sql
```

Step 3 dùng `psql -f` trực tiếp thay vì `bash scripts/migrate/02-restore-hub.sh yte`. Nếu operator follow runbook này thay vì `02-restore-hub.sh`, sẽ bypass:
- `current_database()` verify (T-07-02-03 mitigation)
- Row count sanity check
- Alembic head verify

**Fix:**
```bash
# 1. Switch Caddy upstream về central (Plan 07-02 03-switch-caddy.sh --rollback)
bash scripts/migrate/03-switch-caddy.sh yte --rollback

# 2. Drop hub con DB + re-create từ snapshot
psql -U medinet -d postgres -c "DROP DATABASE medinet_hub_yte;"
bash api/scripts/hub-init.sh yte  # CREATE DB + alembic upgrade head

# 3. Restore qua script (KHÔNG dùng raw psql — bypass safety check)
bash scripts/migrate/02-restore-hub.sh yte

# 4. Re-run smoke
bash scripts/migrate/05-smoke-e2e.sh yte
```

---

_Reviewed: 2026-05-23_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
