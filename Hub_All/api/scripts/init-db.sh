#!/usr/bin/env bash
# Medinet Wiki - Postgres init script (Phase 1 v3.0)
# Tao 4 DB nghiep vu (medinet_central + medinet_hub_yte + medinet_hub_duoc + medinet_hub_hcns)
# + 1 DB cocoindex internal (medinet_cocoindex) tren cung 1 Postgres instance.
# Moi DB nghiep vu: CREATE EXTENSION vector + VERIFY HNSW 1536-dim build OK (R1 carry forward).
# Chay 1 lan khi Postgres cluster khoi tao lan dau (mount /docker-entrypoint-initdb.d/00-init.sh).
# Idempotent: re-run khong loi (SELECT pg_database WHERE datname + IF NOT EXISTS).

set -euo pipefail

# GA-Phase1-A LOCKED: imperative bash loop hardcode 3 hub yte/duoc/hcns.
# KHONG declarative — them hub moi o Plan 04 qua `make hub-init HUB=<name>` (khong sua file nay).
# Loop bien se expand ra 3 DB literal:
#   - medinet_hub_yte
#   - medinet_hub_duoc
#   - medinet_hub_hcns
HUBS=("yte" "duoc" "hcns")

# Buoc (1/4): tao 3 DB hub con medinet_hub_<hub>.
# Postgres KHONG ho tro `CREATE DATABASE IF NOT EXISTS` — dung SELECT pg_database guard.
for hub in "${HUBS[@]}"; do
    db_name="medinet_hub_${hub}"
    echo "[init-db] (1/4) Tao database ${db_name}..."
    exists=$(psql -tA -v ON_ERROR_STOP=1 --username "${POSTGRES_USER}" --dbname "postgres" \
        -c "SELECT 1 FROM pg_database WHERE datname='${db_name}'")
    if [ "$exists" != "1" ]; then
        psql -v ON_ERROR_STOP=1 --username "${POSTGRES_USER}" --dbname "postgres" \
            -c "CREATE DATABASE ${db_name} OWNER ${POSTGRES_USER};"
    else
        echo "[init-db] (1/4) ${db_name} da ton tai, skip."
    fi
done

# Buoc (2/4): tao medinet_cocoindex (M2 carry forward) — R5/P7 cocoindex schema co dinh trong DB nay.
echo "[init-db] (2/4) Tao database medinet_cocoindex..."
exists=$(psql -tA -v ON_ERROR_STOP=1 --username "${POSTGRES_USER}" --dbname "postgres" \
    -c "SELECT 1 FROM pg_database WHERE datname='medinet_cocoindex'")
if [ "$exists" != "1" ]; then
    psql -v ON_ERROR_STOP=1 --username "${POSTGRES_USER}" --dbname "postgres" \
        -c "CREATE DATABASE medinet_cocoindex OWNER ${POSTGRES_USER};"
else
    echo "[init-db] (2/4) medinet_cocoindex da ton tai, skip."
fi

# Buoc (3/4): enable extension vector tren 5 DB (central + 3 hub con + cocoindex).
ALL_DBS=("medinet_central" "medinet_cocoindex")
for hub in "${HUBS[@]}"; do ALL_DBS+=("medinet_hub_${hub}"); done
for db in "${ALL_DBS[@]}"; do
    echo "[init-db] (3/4) Enable extension vector tren ${db}..."
    psql -v ON_ERROR_STOP=1 --username "${POSTGRES_USER}" --dbname "${db}" <<-EOSQL
        CREATE EXTENSION IF NOT EXISTS vector;
EOSQL
done

# Buoc (4/4): VERIFY HNSW 1536-dim build OK tren 4 DB nghiep vu (KHONG verify cocoindex internal).
VERIFY_DBS=("medinet_central")
for hub in "${HUBS[@]}"; do VERIFY_DBS+=("medinet_hub_${hub}"); done
for db in "${VERIFY_DBS[@]}"; do
    echo "[init-db] (4/4) VERIFY HNSW vector(1536) build OK tren ${db}..."
    psql -v ON_ERROR_STOP=1 --username "${POSTGRES_USER}" --dbname "${db}" <<-EOSQL
        DROP TABLE IF EXISTS _hnsw_dim_check;
        CREATE TABLE _hnsw_dim_check (id serial primary key, v vector(1536));
        CREATE INDEX _hnsw_dim_check_idx ON _hnsw_dim_check USING hnsw (v vector_cosine_ops);
        DROP TABLE _hnsw_dim_check;
EOSQL
done

echo "[init-db] DONE — 4 nghiep vu DB + cocoindex created, vector ext enabled, HNSW 1536-dim verified."
