#!/usr/bin/env bash
# Medinet Wiki — Phase 7 MIGRATE-01: Snapshot data per hub_id từ medinet_central
# → migrate-snapshots/migrate-<hub>-<YYYY-MM-DD>.sql
#
# Per D-V3-Phase7-A LOCKED 2026-05-23 — pg_dump --where (option a, REJECT
# cocoindex replay): speed ~5-10 min/hub + vector preserve + schema match.
#
# Usage:
#   bash scripts/migrate/01-snapshot-hubs.sh                # loop 3 hub default
#   bash scripts/migrate/01-snapshot-hubs.sh yte            # single hub
#   HUB=duoc bash scripts/migrate/01-snapshot-hubs.sh
#
# Output: migrate-snapshots/migrate-<hub>-<date>.sql (gitignored — privacy PII).
# Retention: 30 days (xem migrate-snapshots/README.md cron command).
#
# Prereq:
#   - Postgres container running (docker compose up -d postgres)
#   - PGHOST/PGPORT/PGUSER/PGPASSWORD set HOẶC default medinet/medinet_dev_pwd
#   - medinet_central.hubs có row hub_name match arg + id UUID stable

set -euo pipefail
IFS=$'\n\t'

# ──────────────────────────────────────────────────────────────────────
# (1) Parse args
# ──────────────────────────────────────────────────────────────────────

HUB_ARG=${1:-${HUB:-}}

if [ -z "$HUB_ARG" ]; then
    HUBS_TO_SNAPSHOT=("yte" "duoc" "hcns")
    echo "[snapshot-hubs] Default loop 3 hub: ${HUBS_TO_SNAPSHOT[*]}"
else
    HUBS_TO_SNAPSHOT=("$HUB_ARG")
fi

validate_hub_name() {
    local HUB="$1"

    # Regex validate (sync hub-init.sh + hub-add.sh + Settings Plan 02-05 FACTOR-04)
    if ! [[ "$HUB" =~ ^[a-z][a-z0-9_]{0,15}$ ]]; then
        echo "[snapshot-hubs] ERROR: hub name '$HUB' invalid format."
        echo "  Pattern required: ^[a-z][a-z0-9_]{0,15}$"
        return 2
    fi

    # RESERVED blacklist (sync RESERVED_HUB_NAMES app/config.py)
    local RESERVED_NAMES=("postgres" "cocoindex" "template0" "template1" "public" "medinet")
    for reserved in "${RESERVED_NAMES[@]}"; do
        if [ "$HUB" = "$reserved" ]; then
            echo "[snapshot-hubs] ERROR: hub name '$HUB' reserved (Postgres system DB / role)."
            return 2
        fi
    done

    # Reject central (aggregator — KHÔNG snapshot central qua script này)
    if [ "$HUB" = "central" ]; then
        echo "[snapshot-hubs] ERROR: 'central' KHÔNG snapshot qua script này."
        echo "  Phase 7 chỉ snapshot 3 hub con; central truncate qua 04-truncate-central.sh."
        return 2
    fi

    return 0
}

# ──────────────────────────────────────────────────────────────────────
# (2) Postgres connection params (carry forward docker-compose.yml)
# ──────────────────────────────────────────────────────────────────────

PGHOST=${PGHOST:-localhost}
PGPORT=${PGPORT:-5432}
PGUSER_EFFECTIVE=${PGUSER:-medinet}
export PGPASSWORD=${PGPASSWORD:-${POSTGRES_PASSWORD:-medinet_dev_pwd}}

SOURCE_DB="medinet_central"

# ──────────────────────────────────────────────────────────────────────
# (3) Determine repo root + create output dir
# ──────────────────────────────────────────────────────────────────────

if [ -f "docker-compose.yml" ]; then
    REPO_ROOT="$(pwd)"
elif [ -f "Hub_All/docker-compose.yml" ]; then
    REPO_ROOT="$(pwd)/Hub_All"
elif [ -f "../docker-compose.yml" ]; then
    REPO_ROOT="$(cd .. && pwd)"
else
    echo "[snapshot-hubs] ERROR: KHÔNG tìm thấy docker-compose.yml."
    echo "  Chạy từ repo root hoặc Hub_All/ directory."
    exit 2
fi

OUT_DIR="$REPO_ROOT/migrate-snapshots"
mkdir -p "$OUT_DIR"

DATE_TAG=$(date +%Y-%m-%d)

# ──────────────────────────────────────────────────────────────────────
# (4) Snapshot one hub function
# ──────────────────────────────────────────────────────────────────────

snapshot_one_hub() {
    local HUB="$1"

    echo ""
    echo "[snapshot-hubs] === Snapshot hub '$HUB' (date=$DATE_TAG) ==="

    if ! validate_hub_name "$HUB"; then
        return 2
    fi

    # Resolve hub_id UUID
    echo "[snapshot-hubs] (1/3) Resolve hub_id UUID từ $SOURCE_DB.hubs..."
    local HUB_ID
    HUB_ID=$(psql -tA -v ON_ERROR_STOP=1 \
        -h "$PGHOST" -p "$PGPORT" -U "$PGUSER_EFFECTIVE" \
        -d "$SOURCE_DB" \
        -c "SELECT id FROM hubs WHERE hub_name='$HUB' LIMIT 1" 2>/dev/null || echo "")

    if [ -z "$HUB_ID" ]; then
        echo "[snapshot-hubs] ERROR: KHÔNG tìm thấy hub_id cho hub_name='$HUB' trong $SOURCE_DB.hubs."
        echo "  Kiểm tra: psql -d $SOURCE_DB -c \"SELECT id, hub_name FROM hubs;\""
        return 3
    fi

    # CR-01 defense-in-depth — Re-validate UUID v4 format SAU khi resolve TRƯỚC khi
    # interpolate vào pg_dump --where SQL. Nếu central.hubs.id bị corrupt hoặc psql
    # output có warning prefix lẫn vào stdout, regex sẽ reject thay vì cho phép SQL
    # injection qua '$HUB_ID' shell-expand vào --where filter.
    if ! [[ "$HUB_ID" =~ ^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$ ]]; then
        echo "[snapshot-hubs] ERROR: HUB_ID '$HUB_ID' KHÔNG match UUID v4 format — abort (CR-01 defense-in-depth)."
        return 3
    fi

    echo "[snapshot-hubs] (1/3) hub_id='$HUB_ID'"

    local OUT_FILE="$OUT_DIR/migrate-${HUB}-${DATE_TAG}.sql"

    # Idempotent skip
    if [ -f "$OUT_FILE" ]; then
        echo "[snapshot-hubs] (2/3) $OUT_FILE đã tồn tại — skip (xóa explicit để re-snapshot)."
        return 0
    fi

    # pg_dump (D-V3-Phase7-A LOCKED)
    # WR-02 fix — tách stderr ra file riêng để debug, KHÔNG mix vào SQL output.
    # `2>&1` cũ làm warning pg_dump (vd "WARNING: terminating connection...") lẫn
    # vào giữa SQL → psql restore Plan 07-02 FAIL ON_ERROR_STOP=1 + grep INSERT
    # count sai (false-positive nếu warning text chứa "INSERT").
    echo "[snapshot-hubs] (2/3) pg_dump --data-only --where=\"hub_id='$HUB_ID'\" 5 table..."
    local ERR_FILE="${OUT_FILE}.stderr"
    if ! pg_dump \
        -h "$PGHOST" -p "$PGPORT" -U "$PGUSER_EFFECTIVE" \
        --data-only \
        --no-owner \
        --no-acl \
        --column-inserts \
        --table=chunks \
        --table=documents \
        --table=users \
        --table=audit_logs \
        --table=usage_events \
        --where="hub_id = '$HUB_ID'" \
        "$SOURCE_DB" > "$OUT_FILE" 2> "$ERR_FILE"; then
        echo "[snapshot-hubs] ERROR: pg_dump FAIL cho hub '$HUB'."
        if [ -s "$ERR_FILE" ]; then
            echo "  stderr:"
            sed 's/^/    /' "$ERR_FILE"
        fi
        rm -f "$OUT_FILE" "$ERR_FILE"
        return 4
    fi
    # Happy path — empty stderr → rm; non-empty (warning) → giữ debug operator review
    if [ ! -s "$ERR_FILE" ]; then
        rm -f "$ERR_FILE"
    else
        echo "[snapshot-hubs] WARN: pg_dump stderr non-empty — giữ debug $ERR_FILE"
    fi

    # Sanity check
    echo "[snapshot-hubs] (3/3) Sanity check row count..."
    local ROW_COUNT
    ROW_COUNT=$(grep -c '^INSERT' "$OUT_FILE" || echo "0")
    local FILE_SIZE
    FILE_SIZE=$(wc -c < "$OUT_FILE" | tr -d ' ')

    if [ "$ROW_COUNT" = "0" ]; then
        echo "[snapshot-hubs] WARN: hub '$HUB' có 0 INSERT row — hub có thể empty hoặc hub_id resolve sai."
        echo "         File giữ lại debug: $OUT_FILE (size $FILE_SIZE bytes)"
    else
        echo "[snapshot-hubs] (3/3) PASS — $ROW_COUNT INSERT statements, file size $FILE_SIZE bytes."
    fi

    echo "[snapshot-hubs] DONE hub '$HUB' → $OUT_FILE"
    return 0
}

# ──────────────────────────────────────────────────────────────────────
# (5) Execute sequential (v3.0 first migration ưu tiên debug)
# ──────────────────────────────────────────────────────────────────────

FAIL_COUNT=0
for HUB in "${HUBS_TO_SNAPSHOT[@]}"; do
    if ! snapshot_one_hub "$HUB"; then
        FAIL_COUNT=$((FAIL_COUNT + 1))
    fi
done

echo ""
echo "[snapshot-hubs] === Summary ==="
echo "[snapshot-hubs] Total: ${#HUBS_TO_SNAPSHOT[@]} hub. Failed: $FAIL_COUNT."

if [ "$FAIL_COUNT" -gt 0 ]; then
    exit 1
fi

echo "[snapshot-hubs] Next: bash scripts/migrate/02-restore-hub.sh <hub>"
exit 0
