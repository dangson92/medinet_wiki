#!/usr/bin/env bash
# Medinet Wiki — Phase 7 MIGRATE-03: Truncate central skeleton rows per hub_id.
#
# Per D-V3-02 LOCKED — medinet_central.chunks KHÔNG truncate (vẫn nhận sync
# 1-way từ hub con cho cross-hub search per SYNC-01..03 Phase 4 Plan 04-01..05).
# Chỉ DELETE 4 table: documents, users, audit_logs, usage_events.
#
# SAFETY: --dry-run mặc định ON. Operator PHẢI pass --apply explicit để thực thi DELETE.
#
# Usage:
#   bash scripts/migrate/04-truncate-central.sh                       # dry-run loop 3 hub
#   bash scripts/migrate/04-truncate-central.sh --dry-run             # explicit dry-run 3 hub
#   bash scripts/migrate/04-truncate-central.sh yte --dry-run         # dry-run single hub
#   bash scripts/migrate/04-truncate-central.sh --apply               # DELETE 3 hub (confirm prompt)
#   bash scripts/migrate/04-truncate-central.sh yte --apply --yes     # DELETE single hub no prompt
#
# Audit trail: INSERT audit_logs action='migrate.truncate_hub' TRƯỚC DELETE atomic transaction.
# Pattern carry forward Phase 4 sync.py W8 fix (T-04-06-03 reinforced) — non-repudiation.
#
# Exit codes:
#   0  — success (toàn bộ hub PASS)
#   1  — partial fail (≥ 1 hub fail, summary reflect FAIL_COUNT)
#   2  — arg invalid (unknown flag, hub name format)
#   3  — hub_id resolve miss (hub_name không có trong medinet_central.hubs)
#   4  — psql transaction fail (DB connect, SQL error)

set -euo pipefail
IFS=$'\n\t'

# ──────────────────────────────────────────────────────────────────────
# (1) Parse args + determine mode
# ──────────────────────────────────────────────────────────────────────

MODE="--dry-run"   # SAFETY default ON — D-V3-Phase7 LOCKED
AUTO_YES="false"
HUB_ARG=""

for arg in "$@"; do
    case "$arg" in
        --dry-run)
            MODE="--dry-run"
            ;;
        --apply)
            MODE="--apply"
            ;;
        --yes)
            AUTO_YES="true"
            ;;
        --help|-h)
            grep '^#' "$0" | head -25
            exit 0
            ;;
        *)
            if [ -z "$HUB_ARG" ]; then
                HUB_ARG="$arg"
            else
                echo "[truncate-central] ERROR: unknown arg '$arg'"
                exit 2
            fi
            ;;
    esac
done

if [ -z "$HUB_ARG" ]; then
    HUBS_TO_TRUNCATE=("yte" "duoc" "hcns")
    echo "[truncate-central] Default loop 3 hub: ${HUBS_TO_TRUNCATE[*]}"
else
    HUBS_TO_TRUNCATE=("$HUB_ARG")
fi

echo "[truncate-central] === MODE: $MODE ==="

if [ "$MODE" = "--apply" ] && [ "$AUTO_YES" != "true" ]; then
    echo ""
    echo "[truncate-central] WARNING: --apply mode sẽ DELETE rows từ medinet_central."
    echo "[truncate-central] Hubs: ${HUBS_TO_TRUNCATE[*]}"
    echo "[truncate-central] D-V3-02 LOCKED — chunks KHÔNG truncate, chỉ documents/users/audit_logs/usage_events."
    echo ""
    printf "[truncate-central] Type 'yes' để confirm: "
    read -r CONFIRM
    if [ "$CONFIRM" != "yes" ]; then
        echo "[truncate-central] ABORTED — confirm fail."
        exit 0
    fi
fi

# ──────────────────────────────────────────────────────────────────────
# (2) Validate hub_name + Postgres params (T-5-05 mitigation carry forward)
# ──────────────────────────────────────────────────────────────────────

validate_hub_name() {
    local HUB="$1"
    if ! [[ "$HUB" =~ ^[a-z][a-z0-9_]{0,15}$ ]]; then
        echo "[truncate-central] ERROR: hub name '$HUB' invalid format (regex ^[a-z][a-z0-9_]{0,15}\$)."
        return 2
    fi
    local RESERVED_NAMES=("postgres" "cocoindex" "template0" "template1" "public" "medinet")
    for reserved in "${RESERVED_NAMES[@]}"; do
        if [ "$HUB" = "$reserved" ]; then
            echo "[truncate-central] ERROR: hub name '$HUB' reserved."
            return 2
        fi
    done
    if [ "$HUB" = "central" ]; then
        echo "[truncate-central] ERROR: 'central' KHÔNG truncate qua script này (D-V3-Phase7-A guard)."
        return 2
    fi
    return 0
}

PGHOST=${PGHOST:-localhost}
PGPORT=${PGPORT:-5432}
PGUSER_EFFECTIVE=${PGUSER:-medinet}
export PGPASSWORD=${PGPASSWORD:-${POSTGRES_PASSWORD:-medinet_dev_pwd}}

CENTRAL_DB="medinet_central"

# ──────────────────────────────────────────────────────────────────────
# (3) Truncate one hub function — atomic transaction
# ──────────────────────────────────────────────────────────────────────
# SQL atomic transaction pattern:
#   BEGIN;
#   INSERT audit_logs (audit row TRUOC DELETE — Phase 4 sync.py:240-258 W8 pattern)
#   SELECT COUNT pre-delete (log)
#   DELETE 4 table WHERE hub_id = '<uuid>'
#   (KHONG xoá chunks table — D-V3-02 LOCKED preserve cross-hub aggregate)
#   SELECT COUNT post-delete (verify = 0)
#   COMMIT (or ROLLBACK in dry-run)

truncate_one_hub() {
    local HUB="$1"
    local MODE="$2"

    echo ""
    echo "[truncate-central] === Hub '$HUB' (mode=$MODE) ==="

    if ! validate_hub_name "$HUB"; then
        return 2
    fi

    # Resolve hub_id UUID từ medinet_central.hubs (T-07-03-01 guard — reject before psql DELETE)
    local HUB_ID
    HUB_ID=$(psql -v ON_ERROR_STOP=1 -tA \
        -h "$PGHOST" -p "$PGPORT" -U "$PGUSER_EFFECTIVE" \
        -d "$CENTRAL_DB" \
        -c "SELECT id FROM hubs WHERE hub_name='$HUB' LIMIT 1" 2>/dev/null || echo "")

    if [ -z "$HUB_ID" ]; then
        echo "[truncate-central] ERROR: hub_id resolve fail cho hub_name='$HUB' (KHÔNG có trong medinet_central.hubs)."
        return 3
    fi

    echo "[truncate-central] hub_id='$HUB_ID'"

    # Determine COMMIT or ROLLBACK based on MODE
    local FINAL_OP="COMMIT"
    local DRY_RUN_BOOL="false"
    local LOG_PREFIX=""
    if [ "$MODE" = "--dry-run" ]; then
        FINAL_OP="ROLLBACK"
        DRY_RUN_BOOL="true"
        LOG_PREFIX="[DRY-RUN] "
    fi

    # Execute atomic transaction (psql heredoc)
    # KHONG xoá chunks table — D-V3-02 LOCKED (chunks vẫn nhận sync 1-way từ hub con
    # cho cross-hub search SYNC-01..03 Phase 4 — explicit preserve invariant).
    # audit_logs DELETE filter NOT IN action vừa INSERT để tránh xóa chính row vừa tạo
    # (Repudiation evidence chain preserved — T-07-03-03 mitigation).
    set +e
    psql -v ON_ERROR_STOP=1 \
        -h "$PGHOST" -p "$PGPORT" -U "$PGUSER_EFFECTIVE" \
        -d "$CENTRAL_DB" <<-EOSQL
    BEGIN;

    -- (1) INSERT audit_logs TRƯỚC DELETE (Phase 4 sync.py:240-258 W8 carry forward)
    --     T-07-03-03 Repudiation mitigation — non-repudiation evidence chain.
    INSERT INTO audit_logs (user_id, action, target_type, target_id, payload)
    VALUES (
        NULL,
        'migrate.truncate_hub',
        'central_hub_rows',
        '${HUB_ID}',
        jsonb_build_object(
            'hub_name', '${HUB}',
            'dry_run', ${DRY_RUN_BOOL},
            'row_count_documents', (SELECT COUNT(*) FROM documents WHERE hub_id = '${HUB_ID}'),
            'row_count_users', (SELECT COUNT(*) FROM users WHERE hub_id = '${HUB_ID}'),
            'row_count_audit_logs', (SELECT COUNT(*) FROM audit_logs WHERE hub_id = '${HUB_ID}' AND action != 'migrate.truncate_hub'),
            'row_count_usage_events', (SELECT COUNT(*) FROM usage_events WHERE hub_id = '${HUB_ID}'),
            'timestamp', now()::text
        )
    );

    -- (2) Log pre-DELETE counts (5 table — chunks PRESERVED D-V3-02 LOCKED)
    \echo '${LOG_PREFIX}Pre-DELETE row counts:'
    SELECT 'documents' AS tbl, COUNT(*) AS rows FROM documents WHERE hub_id = '${HUB_ID}'
    UNION ALL SELECT 'users', COUNT(*) FROM users WHERE hub_id = '${HUB_ID}'
    UNION ALL SELECT 'audit_logs (non-migrate)', COUNT(*) FROM audit_logs WHERE hub_id = '${HUB_ID}' AND action != 'migrate.truncate_hub'
    UNION ALL SELECT 'usage_events', COUNT(*) FROM usage_events WHERE hub_id = '${HUB_ID}'
    UNION ALL SELECT 'chunks (PRESERVED D-V3-02)', COUNT(*) FROM chunks WHERE hub_id = '${HUB_ID}';

    -- (3) DELETE 4 table — KHÔNG xoá chunks table (D-V3-02 LOCKED)
    --     chunks vẫn nhận sync 1-way từ hub con cho cross-hub aggregate.
    DELETE FROM documents WHERE hub_id = '${HUB_ID}';
    DELETE FROM users WHERE hub_id = '${HUB_ID}';
    DELETE FROM audit_logs WHERE hub_id = '${HUB_ID}' AND action != 'migrate.truncate_hub';
    DELETE FROM usage_events WHERE hub_id = '${HUB_ID}';

    -- (4) Log post-DELETE counts (expect 4 table = 0; chunks PRESERVED D-V3-02 KHÔNG đổi)
    \echo '${LOG_PREFIX}Post-DELETE row counts:'
    SELECT 'documents' AS tbl, COUNT(*) AS rows FROM documents WHERE hub_id = '${HUB_ID}'
    UNION ALL SELECT 'users', COUNT(*) FROM users WHERE hub_id = '${HUB_ID}'
    UNION ALL SELECT 'audit_logs (non-migrate)', COUNT(*) FROM audit_logs WHERE hub_id = '${HUB_ID}' AND action != 'migrate.truncate_hub'
    UNION ALL SELECT 'usage_events', COUNT(*) FROM usage_events WHERE hub_id = '${HUB_ID}'
    UNION ALL SELECT 'chunks (PRESERVED D-V3-02)', COUNT(*) FROM chunks WHERE hub_id = '${HUB_ID}';

    ${FINAL_OP};
EOSQL
    local PSQL_EXIT=$?
    set -e

    if [ "$PSQL_EXIT" -ne 0 ]; then
        echo "[truncate-central] ERROR: psql FAIL cho hub '$HUB' (exit $PSQL_EXIT)."
        return 4
    fi

    echo "[truncate-central] ${LOG_PREFIX}Hub '$HUB' transaction $FINAL_OP."

    if [ "$MODE" = "--dry-run" ]; then
        echo "[truncate-central] [DRY-RUN] No actual DELETE — re-run với --apply để thực thi."
    fi

    return 0
}

# ──────────────────────────────────────────────────────────────────────
# (4) Execute per hub sequential (per-hub error isolation)
# ──────────────────────────────────────────────────────────────────────

FAIL_COUNT=0
for HUB in "${HUBS_TO_TRUNCATE[@]}"; do
    set +e
    truncate_one_hub "$HUB" "$MODE"
    HUB_EXIT=$?
    set -e
    if [ "$HUB_EXIT" -ne 0 ]; then
        FAIL_COUNT=$((FAIL_COUNT + 1))
        echo "[truncate-central] WARN: hub '$HUB' failed (exit $HUB_EXIT) — continue next hub (per-hub error isolation)."
    fi
done

echo ""
echo "[truncate-central] === Summary ==="
echo "[truncate-central] Mode: $MODE | Hubs: ${#HUBS_TO_TRUNCATE[@]} | Failed: $FAIL_COUNT"

if [ "$FAIL_COUNT" -gt 0 ]; then
    exit 1
fi

if [ "$MODE" = "--dry-run" ]; then
    echo "[truncate-central] DRY-RUN OK. Re-run với --apply để thực thi DELETE."
else
    echo "[truncate-central] DONE — central skeleton truncated cho ${HUBS_TO_TRUNCATE[*]}."
    echo "[truncate-central] Verify chunks PRESERVED (D-V3-02 LOCKED):"
    echo "[truncate-central]   psql -d medinet_central -c 'SELECT hub_id, COUNT(*) FROM chunks GROUP BY hub_id'"
fi

exit 0
