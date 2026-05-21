#!/usr/bin/env bash
# Medinet Wiki API — Dynamic hub initialization (Phase 1 v3.0 TOPO-01 part 2).
#
# Tao 1 hub moi khi cluster Postgres dang chay (khong can docker compose down):
#   1. CREATE DATABASE medinet_hub_<HUB> (idempotent)
#   2. CREATE EXTENSION vector
#   3. VERIFY HNSW vector(1536) build OK
#   4. uv run alembic -x hub=<HUB> upgrade head
#
# Usage:
#   bash api/scripts/hub-init.sh <hub_name>
#   HUB=<name> bash api/scripts/hub-init.sh
#
# Yeu cau prereq:
#   - Postgres container dang chay (Phase 1 Plan 01 init-db.sh da chay lan dau HOAC M2 cluster co san)
#   - PSQL co the connect superuser: PGHOST/PGPORT/PGUSER/PGPASSWORD env hoac .pgpass
#   - api/.env DATABASE_URL tro medinet_central (de alembic -x hub=<HUB> resolve)
#
# Validation regex: pattern hub_name = `^[a-z][a-z0-9_]{1,30}$`
# (lowercase a-z bat dau + a-z 0-9 underscore 1-30 char) - Postgres identifier safe.
#
# Note: KHONG validate hub_name in _VALID_HUBS hardcoded - script nay cho phep
# them hub MOI (vd "phap_che", "marketing"). Validation xay ra o Settings layer
# (Plan 02) - neu hub moi chua co trong Literal, Settings se raise ValueError
# o deploy time. De chuyen hub moi vao production, dev phai:
#   1. Chay script nay tao DB
#   2. Update Literal trong app/config.py + Plan 03 env.py + Plan 04 flow.py

set -euo pipefail

HUB=${1:-${HUB:-}}
if [ -z "$HUB" ]; then
    echo "[hub-init] ERROR: thieu hub name. Usage: bash hub-init.sh <hub_name>"
    exit 2
fi

# Sanitize: chi accept lowercase a-z 0-9 underscore (Postgres identifier safe)
# Regex pattern xuat hien literal trong validation block - Plan 05 Task 1 grep
# `grep -cF '^[a-z][a-z0-9_]' Hub_All/api/scripts/hub-init.sh` >= 1 cover.
if ! [[ "$HUB" =~ ^[a-z][a-z0-9_]{1,30}$ ]]; then
    echo "[hub-init] ERROR: hub name '$HUB' invalid. Pattern: ^[a-z][a-z0-9_]{1,30}$"
    exit 2
fi

DB_NAME="medinet_hub_$HUB"
PGUSER_EFFECTIVE=${PGUSER:-medinet}

echo "[hub-init] === Tao hub '$HUB' (DB '$DB_NAME') ==="

# (1/4) CREATE DATABASE idempotent
echo "[hub-init] (1/4) CREATE DATABASE $DB_NAME (idempotent)..."
exists=$(psql -tA -v ON_ERROR_STOP=1 -U "$PGUSER_EFFECTIVE" -d postgres \
    -c "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'")
if [ "$exists" != "1" ]; then
    psql -v ON_ERROR_STOP=1 -U "$PGUSER_EFFECTIVE" -d postgres \
        -c "CREATE DATABASE $DB_NAME OWNER $PGUSER_EFFECTIVE;"
else
    echo "[hub-init] (1/4) $DB_NAME da ton tai, skip."
fi

# (2/4) CREATE EXTENSION vector
echo "[hub-init] (2/4) CREATE EXTENSION IF NOT EXISTS vector tren $DB_NAME..."
psql -v ON_ERROR_STOP=1 -U "$PGUSER_EFFECTIVE" -d "$DB_NAME" \
    -c "CREATE EXTENSION IF NOT EXISTS vector;"

# (3/4) VERIFY HNSW vector(1536) build OK (R1)
echo "[hub-init] (3/4) VERIFY HNSW vector(1536) build OK..."
psql -v ON_ERROR_STOP=1 -U "$PGUSER_EFFECTIVE" -d "$DB_NAME" <<-EOSQL
    DROP TABLE IF EXISTS _hnsw_dim_check;
    CREATE TABLE _hnsw_dim_check (id serial primary key, v vector(1536));
    CREATE INDEX _hnsw_dim_check_idx ON _hnsw_dim_check USING hnsw (v vector_cosine_ops);
    DROP TABLE _hnsw_dim_check;
EOSQL

# (4/4) Apply Alembic migrations
echo "[hub-init] (4/4) Apply Alembic upgrade head tren $DB_NAME..."
# Caller phai set DATABASE_URL=...medinet_central trong api/.env de env.py base DSN OK.
# alembic -x hub=$HUB se resolve sang medinet_hub_$HUB (Plan 03).
(cd "$(dirname "$0")/.." && uv run alembic -x hub="$HUB" upgrade head)

echo "[hub-init] DONE - hub '$HUB' ready (DB $DB_NAME, alembic upgrade head applied)."
