#!/usr/bin/env bash
# Medinet Wiki API - Alembic head SHA match check (Phase 1 v3.0 TOPO-02).
#
# R-V3-3 mitigation (PROJECT.md): Per-hub Alembic drift = MEDIUM risk.
# Moi DB hub co alembic_version table rieng - phai khop head revision sau
# make migrate-all. Script nay lint check + exit 1 neu drift.
#
# Caller chinh:
#   - api/Makefile target 'migrate-all' (sau loop upgrade head)
#   - .github/workflows/test.yml step CI (Plan 05 Task 3)
#
# Yeu cau prereq:
#   - 4 DB ton tai (Plan 01-01 init-db.sh)
#   - DATABASE_URL=...medinet_central + HUB_NAME=central trong .env (base DSN)
#   - uv installed + alembic configured

set -euo pipefail

HUBS_ALL=${HUBS_ALL:-"central yte duoc hcns"}
UV=${UV:-uv}

echo "[alembic-head-check] Collect head SHA per hub..."

declare -A HEADS
FAIL=0

for hub in $HUBS_ALL; do
    # 'alembic current' output: '<rev_id> (head)\n' hoac rong neu chua apply migration.
    # Extract first non-empty line khong match log prefix INFO/WARNING/Context.
    raw=$($UV run alembic -x hub="$hub" current 2>&1 || echo "ERROR")
    rev=$(echo "$raw" | grep -v '^INFO\|^WARNING\|^Context impl' | awk 'NF{print $1; exit}')
    if [ -z "$rev" ] || [ "$rev" = "ERROR" ]; then
        echo "[alembic-head-check] FAIL: hub=$hub khong lay duoc current head (raw: $raw)"
        FAIL=1
        continue
    fi
    HEADS[$hub]=$rev
    echo "[alembic-head-check]   hub=$hub head=$rev"
done

if [ $FAIL -eq 1 ]; then
    echo "[alembic-head-check] FAIL - khong lay duoc head cho it nhat 1 hub."
    exit 1
fi

# Compare all heads = first hub's head.
FIRST_HUB=$(echo "$HUBS_ALL" | awk '{print $1}')
FIRST_HEAD=${HEADS[$FIRST_HUB]}
for hub in $HUBS_ALL; do
    if [ "${HEADS[$hub]}" != "$FIRST_HEAD" ]; then
        echo "[alembic-head-check] FAIL - drift detected: hub=$hub head=${HEADS[$hub]} != $FIRST_HUB head=$FIRST_HEAD"
        echo "[alembic-head-check] R-V3-3 mitigation triggered. Run 'make migrate-all' de re-apply."
        exit 1
    fi
done

echo "[alembic-head-check] PASS - tat ca 4 DB cung head SHA: $FIRST_HEAD"
exit 0
