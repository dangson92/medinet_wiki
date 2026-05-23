#!/usr/bin/env bash
# Medinet Wiki — Phase 7 MIGRATE-02: Restore snapshot vào medinet_hub_<HUB> (blue/green per-hub)
# Per D-V3-Phase7-B LOCKED 2026-05-23 — Blue/green zero-downtime, KHÔNG full downtime.
#
# Usage:
#   bash scripts/migrate/02-restore-hub.sh yte
#   HUB=duoc bash scripts/migrate/02-restore-hub.sh
#
# Prereq:
#   - Plan 07-01 đã chạy: migrate-snapshots/migrate-<HUB>-<date>.sql exist
#   - hub-init.sh đã chạy: medinet_hub_<HUB> DB exist với schema + Alembic 0001..0005
#   - PGHOST/PGPORT/PGUSER/PGPASSWORD set HOẶC default
#
# Exit codes:
#   0 — restore success + row count sanity PASS
#   2 — arg invalid (hub_name regex / RESERVED / central reject / no docker-compose.yml)
#   3 — snapshot file miss / DB target không tồn tại / current_database mismatch
#   4 — psql -f restore FAIL
#   5 — row count sanity mismatch (expected > 0 nhưng total empty)
#
# T-07-02-01..05 STRIDE mitigation:
#   - T-07-02-01 Tampering hub_name: regex + RESERVED blacklist + reject central
#   - T-07-02-02 Path traversal snapshot: constrain ${REPO_ROOT}/migrate-snapshots/ + readable check
#   - T-07-02-03 Information Disclosure restore vào DB sai: SELECT current_database() verify match
#   - T-07-02-04 DoS rollback: rollback flag thuộc Plan 03-switch-caddy.sh (KHÔNG ở đây)
#   - T-07-02-05 Repudiation: snapshot file giữ lại debug + future Plan 07-03 audit_logs INSERT

set -euo pipefail
IFS=$'\n\t'

# ──────────────────────────────────────────────────────────────────────
# (1) Parse args + validate hub_name (T-07-02-01 mitigation)
# ──────────────────────────────────────────────────────────────────────

HUB=${1:-${HUB:-}}

if [ -z "$HUB" ]; then
    echo "[restore-hub] ERROR: thiếu hub name."
    echo "  Usage: bash scripts/migrate/02-restore-hub.sh <hub_name>"
    echo "         HUB=<name> bash scripts/migrate/02-restore-hub.sh"
    exit 2
fi

# Regex validate (T-5-05 carry forward Phase 5 hub-add.sh)
if ! [[ "$HUB" =~ ^[a-z][a-z0-9_]{0,15}$ ]]; then
    echo "[restore-hub] ERROR: hub name '$HUB' invalid format ^[a-z][a-z0-9_]{0,15}$"
    echo "  Reject: uppercase / hyphen / starting-digit / starting-underscore / > 16 char."
    exit 2
fi

# RESERVED blacklist (sync RESERVED_HUB_NAMES app/config.py)
RESERVED_NAMES=("postgres" "cocoindex" "template0" "template1" "public" "medinet")
for reserved in "${RESERVED_NAMES[@]}"; do
    if [ "$HUB" = "$reserved" ]; then
        echo "[restore-hub] ERROR: hub name '$HUB' reserved."
        echo "  6 reserved names: ${RESERVED_NAMES[*]}"
        exit 2
    fi
done

# Reject central (central restore qua procedure khác — KHÔNG dùng script này)
if [ "$HUB" = "central" ]; then
    echo "[restore-hub] ERROR: 'central' KHÔNG restore qua script này."
    echo "  Central là aggregator special — Phase 7 Plan 07-03 truncate skeleton thay."
    exit 2
fi

# ──────────────────────────────────────────────────────────────────────
# (2) Postgres connection params + repo root resolve
# ──────────────────────────────────────────────────────────────────────

PGHOST=${PGHOST:-localhost}
PGPORT=${PGPORT:-5432}
PGUSER_EFFECTIVE=${PGUSER:-medinet}
export PGPASSWORD=${PGPASSWORD:-${POSTGRES_PASSWORD:-medinet_dev_pwd}}

TARGET_DB="medinet_hub_$HUB"

# CR-01 defense-in-depth — Re-validate TARGET_DB format SAU khi compose TRƯỚC khi
# interpolate vào psql `-d` arg + heredoc `WHERE datname='$TARGET_DB'`. $HUB đã
# validate regex `^[a-z][a-z0-9_]{0,15}$` (line 45) — TARGET_DB phải match
# `^medinet_hub_[a-z][a-z0-9_]{0,15}$`. Reject bất kỳ char ngoài alnum/underscore.
if ! [[ "$TARGET_DB" =~ ^medinet_hub_[a-z][a-z0-9_]{0,15}$ ]]; then
    echo "[restore-hub] ERROR: TARGET_DB '$TARGET_DB' KHÔNG match format — abort (CR-01 defense-in-depth)."
    exit 2
fi

# Repo root resolve (3-tier fallback — sync hub-add.sh)
if [ -f "docker-compose.yml" ]; then
    REPO_ROOT="$(pwd)"
elif [ -f "Hub_All/docker-compose.yml" ]; then
    REPO_ROOT="$(pwd)/Hub_All"
elif [ -f "../docker-compose.yml" ]; then
    REPO_ROOT="$(cd .. && pwd)"
else
    echo "[restore-hub] ERROR: KHÔNG tìm thấy docker-compose.yml."
    echo "  Chạy từ repo root hoặc Hub_All/ directory."
    exit 2
fi

SNAPSHOT_DIR="$REPO_ROOT/migrate-snapshots"

# ──────────────────────────────────────────────────────────────────────
# (3/4) Auto-detect latest snapshot file (T-07-02-02 path constrain)
# ──────────────────────────────────────────────────────────────────────

echo "[restore-hub] === Restore hub '$HUB' → DB '$TARGET_DB' ==="
echo "[restore-hub] (1/4) Auto-detect latest snapshot trong $SNAPSHOT_DIR..."

SNAPSHOT_FILE=$(ls -1 "$SNAPSHOT_DIR"/migrate-"$HUB"-*.sql 2>/dev/null | sort -r | head -1 || echo "")

if [ -z "$SNAPSHOT_FILE" ] || [ ! -f "$SNAPSHOT_FILE" ]; then
    echo "[restore-hub] ERROR: KHÔNG tìm thấy snapshot file migrate-${HUB}-*.sql trong $SNAPSHOT_DIR."
    echo "  Chạy: bash scripts/migrate/01-snapshot-hubs.sh $HUB"
    exit 3
fi

if [ ! -r "$SNAPSHOT_FILE" ]; then
    echo "[restore-hub] ERROR: snapshot file '$SNAPSHOT_FILE' KHÔNG readable (T-07-02-02)."
    exit 3
fi

echo "[restore-hub] (1/4) Latest snapshot: $SNAPSHOT_FILE"

# Count expected INSERT row trong snapshot
# WR-03 fix — fail-loud nếu SNAPSHOT_FILE miss (đã check line 103-107). Anchor
# regex chặt hơn `^INSERT INTO ` (có space) để KHÔNG match warning text. `|| true`
# thay `|| echo "0"` để KHÔNG nhầm warning thành 0-row (giữ var unset → fallback).
EXPECTED_INSERTS=$(grep -c '^INSERT INTO ' "$SNAPSHOT_FILE" 2>/dev/null || true)
EXPECTED_INSERTS=${EXPECTED_INSERTS:-0}
echo "[restore-hub] (1/4) Expected INSERT rows: $EXPECTED_INSERTS"

if [ "$EXPECTED_INSERTS" = "0" ]; then
    echo "[restore-hub] WARN: snapshot có 0 INSERT — hub có thể empty hoặc snapshot corrupt."
    echo "  Proceed restore (0-row OK nếu hub mới chưa có data ingest)."
fi

# ──────────────────────────────────────────────────────────────────────
# (2/4) Verify target DB exist + current_database() match (T-07-02-03)
# ──────────────────────────────────────────────────────────────────────

echo "[restore-hub] (2/4) Verify target DB '$TARGET_DB' exist..."

DB_EXISTS=$(psql -v ON_ERROR_STOP=1 -tA \
    -h "$PGHOST" -p "$PGPORT" -U "$PGUSER_EFFECTIVE" \
    -d postgres \
    -c "SELECT 1 FROM pg_database WHERE datname='$TARGET_DB'" 2>/dev/null || echo "")

if [ "$DB_EXISTS" != "1" ]; then
    echo "[restore-hub] ERROR: DB '$TARGET_DB' KHÔNG tồn tại."
    echo "  Chạy: bash api/scripts/hub-init.sh $HUB"
    exit 3
fi

# T-07-02-03 mitigation: verify current_database() match TRƯỚC restore
# Fail-fast nếu DSN trỏ medinet_central thay vì medinet_hub_<HUB>
CURRENT_DB=$(psql -v ON_ERROR_STOP=1 -tA \
    -h "$PGHOST" -p "$PGPORT" -U "$PGUSER_EFFECTIVE" \
    -d "$TARGET_DB" \
    -c "SELECT current_database()" 2>/dev/null || echo "")

if [ "$CURRENT_DB" != "$TARGET_DB" ]; then
    echo "[restore-hub] ERROR: current_database() returns '$CURRENT_DB' KHÔNG khớp '$TARGET_DB'."
    echo "  T-07-02-03 mitigation — KHÔNG restore vào DB sai (vd medinet_central)."
    exit 3
fi

echo "[restore-hub] (2/4) DB '$TARGET_DB' ready (current_database verified)."

# Optional: per-hub Alembic head SHA verify (warn-only — KHÔNG block restore)
# Carry forward Phase 1 alembic-head-check pattern. Schema mismatch warn → operator review.
ALEMBIC_HEAD=$(psql -v ON_ERROR_STOP=1 -tA \
    -h "$PGHOST" -p "$PGPORT" -U "$PGUSER_EFFECTIVE" \
    -d "$TARGET_DB" \
    -c "SELECT version_num FROM alembic_version LIMIT 1" 2>/dev/null || echo "")

if [ -n "$ALEMBIC_HEAD" ]; then
    echo "[restore-hub] (2/4) Alembic head trên $TARGET_DB: $ALEMBIC_HEAD (per-hub 0001..0005 expected)"
else
    echo "[restore-hub] WARN: alembic_version table empty/miss — schema có thể chưa upgrade."
fi

# ──────────────────────────────────────────────────────────────────────
# (3/4) psql -f restore với ON_ERROR_STOP=1
# ──────────────────────────────────────────────────────────────────────

echo "[restore-hub] (3/4) psql -f restore $(basename "$SNAPSHOT_FILE") → $TARGET_DB..."

if ! psql -v ON_ERROR_STOP=1 \
    -h "$PGHOST" -p "$PGPORT" -U "$PGUSER_EFFECTIVE" \
    -d "$TARGET_DB" \
    -f "$SNAPSHOT_FILE" 2>&1 | tail -20; then
    echo "[restore-hub] ERROR: psql restore FAIL cho hub '$HUB'."
    echo "  Snapshot file giữ lại debug: $SNAPSHOT_FILE"
    echo "  Retry sau khi fix schema mismatch: bash $0 $HUB"
    exit 4
fi

# ──────────────────────────────────────────────────────────────────────
# (4/4) Post-restore row count sanity check
# ──────────────────────────────────────────────────────────────────────

echo "[restore-hub] (4/4) Post-restore row count sanity check..."

ACTUAL_CHUNKS=$(psql -v ON_ERROR_STOP=1 -tA \
    -h "$PGHOST" -p "$PGPORT" -U "$PGUSER_EFFECTIVE" \
    -d "$TARGET_DB" \
    -c "SELECT COUNT(*) FROM chunks" 2>/dev/null || echo "0")

ACTUAL_DOCS=$(psql -v ON_ERROR_STOP=1 -tA \
    -h "$PGHOST" -p "$PGPORT" -U "$PGUSER_EFFECTIVE" \
    -d "$TARGET_DB" \
    -c "SELECT COUNT(*) FROM documents" 2>/dev/null || echo "0")

ACTUAL_USERS=$(psql -v ON_ERROR_STOP=1 -tA \
    -h "$PGHOST" -p "$PGPORT" -U "$PGUSER_EFFECTIVE" \
    -d "$TARGET_DB" \
    -c "SELECT COUNT(*) FROM users" 2>/dev/null || echo "0")

echo "[restore-hub] (4/4) Row counts post-restore:"
echo "  chunks=$ACTUAL_CHUNKS, documents=$ACTUAL_DOCS, users=$ACTUAL_USERS"
echo "  expected INSERT statements in snapshot: $EXPECTED_INSERTS"

# Tolerance check — INSERT statements include all 5 tables, KHÔNG chính xác per-table
# Chỉ verify total > 0 nếu expected > 0 (avoid false-positive cho empty hub)
TOTAL_ROWS=$((ACTUAL_CHUNKS + ACTUAL_DOCS + ACTUAL_USERS))
if [ "$EXPECTED_INSERTS" -gt "0" ] && [ "$TOTAL_ROWS" = "0" ]; then
    echo "[restore-hub] ERROR: Expected $EXPECTED_INSERTS INSERT nhưng DB hoàn toàn empty."
    echo "  Có thể psql -f restore silent FAIL (ON_ERROR_STOP=1 đáng lẽ catch — debug snapshot SQL)."
    exit 5
fi

echo ""
echo "[restore-hub] DONE — hub '$HUB' restored từ $(basename "$SNAPSHOT_FILE")."
echo "Next steps:"
echo "  bash scripts/migrate/03-switch-caddy.sh $HUB   # verify Caddy auto-route"
echo "  bash scripts/migrate/05-smoke-e2e.sh $HUB      # golden path 7-step E2E (Plan 07-05)"
exit 0
