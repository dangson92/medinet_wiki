#!/usr/bin/env bash
# Medinet Wiki — Postgres init script
# Tạo 2 logical DB + CREATE EXTENSION vector + VERIFY HNSW 1536-dim build OK (R1 mitigation).
# Chạy 1 lần khi Postgres cluster khởi tạo lần đầu (mount /docker-entrypoint-initdb.d/00-init.sh).

set -euo pipefail

echo "[init-db] (1/4) Tạo database medinet_cocoindex..."
psql -v ON_ERROR_STOP=1 --username "${POSTGRES_USER}" --dbname "postgres" <<-EOSQL
    CREATE DATABASE medinet_cocoindex OWNER ${POSTGRES_USER};
EOSQL

echo "[init-db] (2/4) Enable extension vector trên medinet_central..."
psql -v ON_ERROR_STOP=1 --username "${POSTGRES_USER}" --dbname "medinet_central" <<-EOSQL
    CREATE EXTENSION IF NOT EXISTS vector;
EOSQL

echo "[init-db] (3/4) Enable extension vector trên medinet_cocoindex..."
psql -v ON_ERROR_STOP=1 --username "${POSTGRES_USER}" --dbname "medinet_cocoindex" <<-EOSQL
    CREATE EXTENSION IF NOT EXISTS vector;
EOSQL

echo "[init-db] (4/4) VERIFY HNSW 1536-dim index build OK (R1 mitigation)..."
psql -v ON_ERROR_STOP=1 --username "${POSTGRES_USER}" --dbname "medinet_central" <<-EOSQL
    CREATE TABLE _hnsw_dim_check (id serial primary key, v vector(1536));
    CREATE INDEX _hnsw_dim_check_idx ON _hnsw_dim_check USING hnsw (v vector_cosine_ops);
    DROP TABLE _hnsw_dim_check;
EOSQL

echo "[init-db] DONE — 2 DB created, vector ext enabled, HNSW 1536-dim verified."
