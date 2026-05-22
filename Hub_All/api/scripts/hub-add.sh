#!/usr/bin/env bash
# Medinet Wiki API — Dynamic hub registration (Plan 02-05 FACTOR-04).
#
# Tao 1 hub moi end-to-end (DB + compose service) bang 1 lenh:
#   1. Validate hub_name format regex (sync Settings Plan 02-05 + hub-init.sh)
#   2. Validate hub_name reserved blacklist (sync Settings RESERVED_HUB_NAMES)
#   3. Validate hub chua co trong docker-compose.yml base + override
#   4. Auto-detect port (8180 + N hien huu + 1) neu khong truyen explicit
#   5. Call hub-init.sh <HUB> -> CREATE DATABASE + ext + HNSW + alembic upgrade
#   6. Sed substitute docker-compose.override.yml.template -> append override
#   7. In huong dan next step (docker compose up -d python-api-<HUB>)
#
# Usage:
#   bash api/scripts/hub-add.sh <hub_name> [<port>]
#   HUB=<name> [PORT=<port>] bash api/scripts/hub-add.sh
#
# Vd:
#   bash api/scripts/hub-add.sh phap_che           # auto-detect port
#   bash api/scripts/hub-add.sh phap_che 8189     # explicit port
#
# Yeu cau prereq:
#   - Postgres container dang chay (docker compose up -d postgres)
#   - api/.env DATABASE_URL tro medinet_central
#   - Working directory = repo root (chua docker-compose.yml) hoac Hub_All/
#
# Validation chain (fail-fast cac error pre-DB-create):
#   - Regex format -> reject pre-CREATE DATABASE (orphan DB cleanup deu phai)
#   - Reserved blacklist -> reject pre-CREATE DATABASE
#   - Duplicate service detect -> reject pre-CREATE DATABASE

set -euo pipefail

# ──────────────────────────────────────────────────────────────────────────
# (1/7) Parse args
# ──────────────────────────────────────────────────────────────────────────

HUB=${1:-${HUB:-}}
PORT=${2:-${PORT:-}}

if [ -z "$HUB" ]; then
    echo "[hub-add] ERROR: thieu hub name."
    echo "Usage: bash api/scripts/hub-add.sh <hub_name> [<port>]"
    echo "       HUB=<name> [PORT=<port>] bash api/scripts/hub-add.sh"
    exit 2
fi

# ──────────────────────────────────────────────────────────────────────────
# (2/7) Validate hub_name regex format (sync Settings Plan 02-05)
# ──────────────────────────────────────────────────────────────────────────

if ! [[ "$HUB" =~ ^[a-z][a-z0-9_]{0,15}$ ]]; then
    echo "[hub-add] ERROR: hub name '$HUB' invalid format."
    echo "  Pattern required: ^[a-z][a-z0-9_]{0,15}$"
    echo "  Reject: uppercase / hyphen / starting-digit / starting-underscore / > 16 char."
    echo "  (sync Settings app/config.py FACTOR-04 Plan 02-05)"
    exit 2
fi

# ──────────────────────────────────────────────────────────────────────────
# (3/7) Validate hub_name reserved blacklist (sync RESERVED_HUB_NAMES)
# ──────────────────────────────────────────────────────────────────────────

RESERVED_NAMES=("postgres" "cocoindex" "template0" "template1" "public" "medinet")
for reserved in "${RESERVED_NAMES[@]}"; do
    if [ "$HUB" = "$reserved" ]; then
        echo "[hub-add] ERROR: hub name '$HUB' reserved."
        echo "  6 reserved names: ${RESERVED_NAMES[*]}"
        echo "  (Postgres system DB / role medinet collision)"
        exit 2
    fi
done

# 'central' KHONG reserved (aggregator special) nhung tao hub_central qua hub-add
# se gay confusion - reject explicit.
if [ "$HUB" = "central" ]; then
    echo "[hub-add] ERROR: 'central' la aggregator special-case, da co san."
    echo "  Hub moi phai khac 'central'."
    exit 2
fi

# ──────────────────────────────────────────────────────────────────────────
# (4/7) Determine repo root + check docker-compose.yml exist
# ──────────────────────────────────────────────────────────────────────────

# Find compose root: uu tien cwd neu co docker-compose.yml, fallback Hub_All/
if [ -f "docker-compose.yml" ]; then
    COMPOSE_ROOT="$(pwd)"
elif [ -f "Hub_All/docker-compose.yml" ]; then
    COMPOSE_ROOT="$(pwd)/Hub_All"
elif [ -f "../docker-compose.yml" ]; then
    COMPOSE_ROOT="$(cd .. && pwd)"
else
    echo "[hub-add] ERROR: KHONG tim thay docker-compose.yml."
    echo "  Chay tu repo root hoac Hub_All/ directory."
    exit 2
fi

TEMPLATE_PATH="$COMPOSE_ROOT/docker-compose.override.yml.template"
OVERRIDE_PATH="$COMPOSE_ROOT/docker-compose.override.yml"
BASE_PATH="$COMPOSE_ROOT/docker-compose.yml"

if [ ! -f "$TEMPLATE_PATH" ]; then
    echo "[hub-add] ERROR: KHONG tim thay $TEMPLATE_PATH"
    echo "  Plan 02-05 phai ship docker-compose.override.yml.template cung commit."
    exit 2
fi

# ──────────────────────────────────────────────────────────────────────────
# (5/7) Detect duplicate service in base + override
# ──────────────────────────────────────────────────────────────────────────

if grep -q "^  python-api-${HUB}:" "$BASE_PATH"; then
    echo "[hub-add] ERROR: service python-api-${HUB} da ton tai trong docker-compose.yml base."
    echo "  Hub goc Phase 2: central, yte, duoc, hcns. Hub trung KHONG cho phep."
    exit 2
fi

if [ -f "$OVERRIDE_PATH" ] && grep -q "^  python-api-${HUB}:" "$OVERRIDE_PATH"; then
    echo "[hub-add] ERROR: service python-api-${HUB} da ton tai trong $OVERRIDE_PATH."
    echo "  Hub da add truoc - xoa thu cong neu muon re-create."
    exit 2
fi

# ──────────────────────────────────────────────────────────────────────────
# (6/7) Auto-detect port neu chua truyen (max port hien huu + 1)
# ──────────────────────────────────────────────────────────────────────────

if [ -z "$PORT" ]; then
    # Scan max port "NNNN:8080" trong base + override
    MAX_PORT=0
    while IFS= read -r line; do
        if [[ "$line" =~ \"([0-9]{4,5}):8080\" ]]; then
            port="${BASH_REMATCH[1]}"
            if [ "$port" -gt "$MAX_PORT" ]; then
                MAX_PORT=$port
            fi
        fi
    done < <(cat "$BASE_PATH" "$OVERRIDE_PATH" 2>/dev/null || true)

    if [ "$MAX_PORT" -eq 0 ]; then
        PORT=8184  # fallback neu base parse fail
    else
        PORT=$((MAX_PORT + 1))
    fi
    echo "[hub-add] Auto-detect port: $PORT (max hien huu = $MAX_PORT)"
fi

# Validate port range 1024-65535 (privileged port reject)
if ! [[ "$PORT" =~ ^[0-9]+$ ]] || [ "$PORT" -lt 1024 ] || [ "$PORT" -gt 65535 ]; then
    echo "[hub-add] ERROR: port '$PORT' invalid. Range 1024-65535."
    exit 2
fi

# Detect port conflict trong base + override
if grep -qE "\"${PORT}:8080\"" "$BASE_PATH" 2>/dev/null; then
    echo "[hub-add] ERROR: port $PORT da xai trong docker-compose.yml base."
    exit 2
fi
if [ -f "$OVERRIDE_PATH" ] && grep -qE "\"${PORT}:8080\"" "$OVERRIDE_PATH"; then
    echo "[hub-add] ERROR: port $PORT da xai trong $OVERRIDE_PATH."
    exit 2
fi

# ──────────────────────────────────────────────────────────────────────────
# (7/7) Execute: hub-init.sh (DB) + sed template (compose) + register volume
# ──────────────────────────────────────────────────────────────────────────

echo "[hub-add] === Tao hub moi '$HUB' (port=$PORT, DB=medinet_hub_$HUB) ==="

# Step 7a: Call hub-init.sh (DB-level Phase 1)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "[hub-add] (a) Goi $SCRIPT_DIR/hub-init.sh $HUB ..."
bash "$SCRIPT_DIR/hub-init.sh" "$HUB"

# Step 7b: Sed substitute template -> append override
echo "[hub-add] (b) Generate service block tu template..."
if [ ! -f "$OVERRIDE_PATH" ]; then
    # First-time: write header
    cat > "$OVERRIDE_PATH" <<EOF
# Plan 02-05 FACTOR-04 — Dynamic hub registration override (auto-generated).
# Generate by: scripts/hub-add.sh
# Edit thu cong KHONG khuyen nghi - re-run hub-add.sh se append/conflict.
# .gitignored - hub moi la operator-local, KHONG commit.

services:
EOF
fi

# Append service block (sed substitute placeholder)
sed "s/{{HUB}}/$HUB/g; s/{{PORT}}/$PORT/g" "$TEMPLATE_PATH" >> "$OVERRIDE_PATH"

# Append volume declaration (cocoindex LMDB per-hub) neu chua co volumes: section
if ! grep -q "^volumes:" "$OVERRIDE_PATH"; then
    cat >> "$OVERRIDE_PATH" <<EOF

volumes:
  medinet_cocoindex_$HUB:
EOF
else
    # Volumes section da co — append volume moi sau marker
    sed -i.bak "/^volumes:/a\\
  medinet_cocoindex_$HUB:
" "$OVERRIDE_PATH" && rm -f "${OVERRIDE_PATH}.bak"
fi

# Step 7c: Verify docker compose config merge OK
echo "[hub-add] (c) Verify docker compose config merge OK..."
cd "$COMPOSE_ROOT"
if ! docker compose config --quiet 2>&1; then
    echo "[hub-add] ERROR: docker compose config merge FAIL sau append."
    echo "  Override file: $OVERRIDE_PATH"
    echo "  Xoa thu cong block python-api-$HUB neu can rollback."
    exit 3
fi

# ──────────────────────────────────────────────────────────────────────────
# DONE
# ──────────────────────────────────────────────────────────────────────────

echo "[hub-add] DONE — hub '$HUB' ready."
echo ""
echo "Next steps:"
echo "  1. Build + up service:"
echo "     docker compose up -d python-api-$HUB"
echo ""
echo "  2. Verify health:"
echo "     curl http://localhost:$PORT/api/health"
echo "     Expected: 200 {\"success\":true,\"data\":{\"status\":\"ok\"},...}"
echo ""
echo "  3. Logs:"
echo "     docker compose logs -f python-api-$HUB"
echo ""
echo "  4. Frontend route (Phase 5 Caddy chua ship):"
echo "     Direct: http://localhost:$PORT/api/..."
echo "     Caddy subpath (Phase 5): http://wiki.domain.com/$HUB/api/..."
echo ""
echo "Override file: $OVERRIDE_PATH"
echo "Hub_registry persistence: defer Phase 6 SETTINGS-04 hub_registry table."
