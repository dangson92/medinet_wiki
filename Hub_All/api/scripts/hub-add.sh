#!/usr/bin/env bash
# Medinet Wiki API — Dynamic hub registration (Plan 02-05 FACTOR-04 + Plan 05-05 PROXY-01 extend).
#
# 9-step pipeline (Phase 5 v3.0-05 PROXY-01 extend từ 7-step Plan 02-05):
#   1. Validate hub_name format regex (sync Settings Plan 02-05 + hub-init.sh)
#   2. Validate hub_name reserved blacklist (sync Settings RESERVED_HUB_NAMES)
#   3. Validate hub chua co trong docker-compose.yml base + override
#   4. Auto-detect port (8180 + N hien huu + 1) neu khong truyen explicit
#   5. Call hub-init.sh <HUB> -> CREATE DATABASE + ext + HNSW + alembic upgrade
#   6. Sed substitute docker-compose.override.yml.template -> append override
#   7. Docker compose config --quiet verify merge
#   8. (Phase 5 PROXY-01) Cap nhat .env HUBS_ALLOWLIST + HUBS_ALLOWLIST_REGEX
#      atomic qua tmp file + mv (preserve other env vars). Idempotent skip neu hub
#      da co trong allowlist.
#   9. (Phase 5 PROXY-01) Caddy validate config TRUOC reload (Pitfall 7 mitigation
#      avoid silent rollback) + zero-downtime `caddy reload` + smoke `curl
#      /<hub>/api/health`. Skip neu caddy container chua running (dev pre-up).
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
#   - (Optional Phase 5 step 9) caddy container running -> auto-reload sau register
#
# Validation chain (fail-fast cac error pre-DB-create):
#   - Regex format -> reject pre-CREATE DATABASE (orphan DB cleanup deu phai)
#   - Reserved blacklist -> reject pre-CREATE DATABASE
#   - Duplicate service detect -> reject pre-CREATE DATABASE
#
# T-5-05 mitigation (carry forward Plan 02-05 — Phase 5 KHONG relax):
#   - $HUB pass validate Step 1-2 (regex + RESERVED blacklist) truoc khi cham .env / caddy
#   - Tat ca $HUB interpolations TRONG step 8 + 9 deu quote "$HUB"
#   - sed expressions su dung delimiter "|" thay "/" de tranh collision voi pipe trong REGEX value

set -euo pipefail

# ──────────────────────────────────────────────────────────────────────────
# (1/9) Parse args
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
# (2/9) Validate hub_name regex format (sync Settings Plan 02-05)
# ──────────────────────────────────────────────────────────────────────────

if ! [[ "$HUB" =~ ^[a-z][a-z0-9_]{0,15}$ ]]; then
    echo "[hub-add] ERROR: hub name '$HUB' invalid format."
    echo "  Pattern required: ^[a-z][a-z0-9_]{0,15}$"
    echo "  Reject: uppercase / hyphen / starting-digit / starting-underscore / > 16 char."
    echo "  (sync Settings app/config.py FACTOR-04 Plan 02-05)"
    exit 2
fi

# ──────────────────────────────────────────────────────────────────────────
# (3/9) Validate hub_name reserved blacklist (sync RESERVED_HUB_NAMES)
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
# (4/9) Determine repo root + check docker-compose.yml exist
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
# (5/9) Detect duplicate service in base + override
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
# (6/9) Auto-detect port neu chua truyen (max port hien huu + 1)
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
# (7/9) Execute: hub-init.sh (DB) + sed template (compose) + register volume
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

# Generate service block (sed substitute placeholder)
# Bug fix 2026-05-23: thiếu {{HUB_UPPER}} substitution → docker compose config FAIL
# vì env HUB_ID parse `${HUB_{{HUB_UPPER}}_ID:?...}` literal placeholder. Compute
# HUB_UPPER qua `tr` (portable hơn bash ${HUB^^} cần bash 4+).
HUB_UPPER=$(echo "$HUB" | tr '[:lower:]' '[:upper:]')

# Bug fix 2026-05-25: khi hub thu 2+ duoc add, override.yml da co `volumes:` section
# o cuoi file → `sed >> override.yml` append service block VAO SAU `volumes:` →
# YAML parse service block thanh volume mapping → `volumes.python-api-X additional
# properties 'build', 'ports'... not allowed`. Fix: neu file da co `volumes:` section,
# INSERT service block TRUOC dong `^volumes:` qua awk split-and-rejoin (atomic tmp+mv).
SERVICE_BLOCK_TMP=$(mktemp)
trap 'rm -f "$SERVICE_BLOCK_TMP"' EXIT
sed "s/{{HUB_UPPER}}/$HUB_UPPER/g; s/{{HUB}}/$HUB/g; s/{{PORT}}/$PORT/g" "$TEMPLATE_PATH" > "$SERVICE_BLOCK_TMP"

if grep -q "^volumes:" "$OVERRIDE_PATH"; then
    # File da co volumes: section → INSERT service block TRUOC dong `^volumes:`
    OVERRIDE_TMP=$(mktemp)
    awk -v block_file="$SERVICE_BLOCK_TMP" '
        /^volumes:/ && !inserted {
            while ((getline line < block_file) > 0) print line
            close(block_file)
            inserted = 1
        }
        { print }
    ' "$OVERRIDE_PATH" > "$OVERRIDE_TMP" && mv "$OVERRIDE_TMP" "$OVERRIDE_PATH"

    # Append volume moi sau marker `^volumes:` (idempotent)
    sed -i.bak "/^volumes:/a\\
  medinet_cocoindex_$HUB:
" "$OVERRIDE_PATH" && rm -f "${OVERRIDE_PATH}.bak"
else
    # Chua co volumes: section → append service block + volumes: section vao cuoi
    cat "$SERVICE_BLOCK_TMP" >> "$OVERRIDE_PATH"
    cat >> "$OVERRIDE_PATH" <<EOF

volumes:
  medinet_cocoindex_$HUB:
EOF
fi
rm -f "$SERVICE_BLOCK_TMP"
trap - EXIT

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
# (8/9) Cap nhat .env HUBS_ALLOWLIST + HUBS_ALLOWLIST_REGEX (Phase 5 PROXY-01)
# ──────────────────────────────────────────────────────────────────────────
# Source: .planning/phases/05-reverse-proxy-frontend-subpath/05-RESEARCH.md
#         §"hub-add.sh extension Phase 5 (step 8 + 9)"
# Atomic edit qua tmp file + mv — preserve other env vars in .env.
# Idempotent: skip neu hub da co trong HUBS_ALLOWLIST (duplicate detect).
# Use sed delimiter "|" instead of "/" to avoid collision with REGEX pipe value.

ENV_FILE="$COMPOSE_ROOT/.env"

# Idempotent: tao .env tu .env.example neu chua co
if [ ! -f "$ENV_FILE" ]; then
    if [ -f "$COMPOSE_ROOT/.env.example" ]; then
        cp "$COMPOSE_ROOT/.env.example" "$ENV_FILE"
        echo "[hub-add] (8) Created .env tu .env.example"
    else
        # Minimum .env fallback — Phase 5 minimum keys (base 3 hub Phase 2)
        echo "HUBS_ALLOWLIST=yte,duoc,hcns" > "$ENV_FILE"
        echo "HUBS_ALLOWLIST_REGEX=yte|duoc|hcns" >> "$ENV_FILE"
        echo "[hub-add] (8) Created .env voi minimum HUBS_ALLOWLIST fallback"
    fi
fi

# Extract current allowlist (default empty neu missing key)
CURRENT_ALLOWLIST=$(grep -E "^HUBS_ALLOWLIST=" "$ENV_FILE" | head -1 | cut -d= -f2- || echo "")

# Check duplicate (hub da co trong allowlist — idempotent skip)
if [[ ",${CURRENT_ALLOWLIST}," == *",${HUB},"* ]]; then
    echo "[hub-add] (8) HUB '${HUB}' da co trong HUBS_ALLOWLIST — skip env update (idempotent)"
else
    # Append hub vao allowlist
    NEW_ALLOWLIST="${CURRENT_ALLOWLIST:+${CURRENT_ALLOWLIST},}${HUB}"
    NEW_REGEX=$(echo "${NEW_ALLOWLIST}" | tr ',' '|')

    # Atomic edit qua tmp file + mv (preserve other env vars in .env)
    TMP_ENV=$(mktemp)
    trap 'rm -f "$TMP_ENV"' EXIT

    # Update HUBS_ALLOWLIST (sed delimiter "|" tranh collision voi regex pipe)
    if grep -qE "^HUBS_ALLOWLIST=" "$ENV_FILE"; then
        sed "s|^HUBS_ALLOWLIST=.*|HUBS_ALLOWLIST=${NEW_ALLOWLIST}|" "$ENV_FILE" > "$TMP_ENV"
    else
        cp "$ENV_FILE" "$TMP_ENV"
        echo "HUBS_ALLOWLIST=${NEW_ALLOWLIST}" >> "$TMP_ENV"
    fi

    # Update HUBS_ALLOWLIST_REGEX (in tmp file, not original — atomic single mv cuoi)
    if grep -qE "^HUBS_ALLOWLIST_REGEX=" "$TMP_ENV"; then
        TMP_ENV2=$(mktemp)
        sed "s|^HUBS_ALLOWLIST_REGEX=.*|HUBS_ALLOWLIST_REGEX=${NEW_REGEX}|" "$TMP_ENV" > "$TMP_ENV2"
        mv "$TMP_ENV2" "$TMP_ENV"
    else
        echo "HUBS_ALLOWLIST_REGEX=${NEW_REGEX}" >> "$TMP_ENV"
    fi

    mv "$TMP_ENV" "$ENV_FILE"
    trap - EXIT
    echo "[hub-add] (8) Updated .env HUBS_ALLOWLIST=${NEW_ALLOWLIST}"
    echo "[hub-add] (8) Updated .env HUBS_ALLOWLIST_REGEX=${NEW_REGEX}"
fi

# ──────────────────────────────────────────────────────────────────────────
# (9/9) Caddy validate + reload zero-downtime + smoke (Phase 5 PROXY-01)
# ──────────────────────────────────────────────────────────────────────────
# Pitfall 7 mitigation (Caddy reload silent rollback):
#   Caddy silent rollback old config neu new config invalid — operator KHONG biet failure.
#   PRE-validate `caddy validate --config` TRUOC reload → fail-fast voi explicit
#   error message + rollback instruction.
# T-5-16: dev WIKI_PUBLIC_DOMAIN=localhost dung self-signed cert; `-k` flag chap nhan.
# Prod ACME Let's Encrypt valid cert KHONG can `-k`.

# Check neu caddy container dang chay (dev pre-up — operator chua start compose)
if docker compose ps caddy --format json 2>/dev/null | grep -q '"State":"running"'; then
    echo "[hub-add] (9) Validate Caddy config TRUOC reload..."

    # PRE-validate — fail-fast neu config invalid (avoid silent rollback Pitfall 7)
    if ! docker compose exec -T caddy caddy validate --config /etc/caddy/Caddyfile 2>&1; then
        echo "[hub-add] ERROR: Caddy config validate FAIL — rollback .env edit can thiet."
        echo "  Manual rollback:"
        echo "    sed -i 's|^HUBS_ALLOWLIST=.*|HUBS_ALLOWLIST=${CURRENT_ALLOWLIST}|' $ENV_FILE"
        echo "    sed -i 's|^HUBS_ALLOWLIST_REGEX=.*|HUBS_ALLOWLIST_REGEX=$(echo "${CURRENT_ALLOWLIST}" | tr ',' '|')|' $ENV_FILE"
        exit 4
    fi

    echo "[hub-add] (9) Validate PASS — reloading Caddy (zero-downtime via admin API)..."

    # Atomic reload qua Caddy admin API (zero-downtime — KHONG restart container)
    if ! docker compose exec -T caddy caddy reload --config /etc/caddy/Caddyfile 2>&1; then
        echo "[hub-add] ERROR: Caddy reload FAIL"
        exit 4
    fi

    # Smoke checkpoint: verify hub moi route work post-reload
    sleep 1  # cho Caddy settle

    if command -v curl >/dev/null 2>&1; then
        DOMAIN="${WIKI_PUBLIC_DOMAIN:-localhost}"
        SMOKE_URL="https://${DOMAIN}/${HUB}/api/health"
        echo "[hub-add] (9) Smoke check: curl -k ${SMOKE_URL}"
        if curl -k -sf -o /dev/null --max-time 5 "${SMOKE_URL}" 2>/dev/null; then
            echo "[hub-add] (9) Smoke PASS — hub '${HUB}' route work qua Caddy"
        else
            echo "[hub-add] WARN: Smoke check returned non-200 hoac timeout."
            echo "         Backend container python-api-${HUB} co the chua up."
            echo "         Run: docker compose up -d python-api-${HUB} && curl -k ${SMOKE_URL}"
        fi
    else
        echo "[hub-add] (9) Skip smoke check (curl khong co)"
    fi
else
    echo "[hub-add] (9) Caddy container chua running — skip reload (se apply khi 'docker compose up')"
    echo "         Sau khi up: docker compose exec caddy caddy reload --config /etc/caddy/Caddyfile"
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
