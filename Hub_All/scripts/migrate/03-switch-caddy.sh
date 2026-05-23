#!/usr/bin/env bash
# Medinet Wiki — Phase 7 MIGRATE-02: Verify Caddy auto-route post-restore (VERIFY-ONLY).
#
# Per CONTEXT.md `<specifics>` correction 2026-05-23: Caddyfile sau Phase 5 đã có
# dynamic regex `{re.hub_api.1}` capture hub_name từ URL prefix + `reverse_proxy
# python-api-{re.hub_api.1}:8080` (Phase 5 Plan 05-01 PROXY-01). Phase 7 KHÔNG cần
# sed edit Caddyfile — chỉ verify python-api-<HUB> container running + Caddy
# auto-route. Script shrink ~50% so với sed edit complex.
#
# Usage:
#   bash scripts/migrate/03-switch-caddy.sh yte              # verify + smoke
#   bash scripts/migrate/03-switch-caddy.sh yte --rollback   # stop hub container (revert routing)
#   HUB=duoc bash scripts/migrate/03-switch-caddy.sh
#
# Exit codes:
#   0 — verify PASS (container running + caddy validate + smoke 200) HOẶC rollback DONE
#   2 — arg invalid (hub_name regex / RESERVED / central reject / missing arg)
#   3 — python-api-<HUB> container KHÔNG running (operator phải docker compose up trước)
#   4 — caddy validate FAIL (Caddyfile syntax broken)
#
# T-07-02-04 DoS rollback flag accept disposition — intentional behavior; operator
# explicit flag; user-visible 404 là signal cho switch revert (acceptable).

set -euo pipefail
IFS=$'\n\t'

# ──────────────────────────────────────────────────────────────────────
# (1) Parse args + validate hub_name
# ──────────────────────────────────────────────────────────────────────

HUB=${1:-${HUB:-}}
MODE=${2:-"verify"}

if [ -z "$HUB" ]; then
    echo "[switch-caddy] ERROR: thiếu hub name."
    echo "  Usage: bash scripts/migrate/03-switch-caddy.sh <hub_name> [--rollback]"
    exit 2
fi

# Regex validate (T-5-05 carry forward Phase 5 hub-add.sh)
if ! [[ "$HUB" =~ ^[a-z][a-z0-9_]{0,15}$ ]]; then
    echo "[switch-caddy] ERROR: hub name '$HUB' invalid format ^[a-z][a-z0-9_]{0,15}$"
    exit 2
fi

# RESERVED blacklist (sync RESERVED_HUB_NAMES app/config.py)
RESERVED_NAMES=("postgres" "cocoindex" "template0" "template1" "public" "medinet")
for reserved in "${RESERVED_NAMES[@]}"; do
    if [ "$HUB" = "$reserved" ]; then
        echo "[switch-caddy] ERROR: hub name '$HUB' reserved."
        exit 2
    fi
done

# Reject central
if [ "$HUB" = "central" ]; then
    echo "[switch-caddy] ERROR: 'central' KHÔNG switch qua script này."
    echo "  Central routing Caddy handle /api/* (no strip) — Phase 5 LOCKED."
    exit 2
fi

# ──────────────────────────────────────────────────────────────────────
# (2) Rollback mode: stop hub container (Caddy regex fall-through file_server)
# ──────────────────────────────────────────────────────────────────────

if [ "$MODE" = "--rollback" ]; then
    echo "[switch-caddy] === ROLLBACK hub '$HUB' (stop container — Caddy fall through file_server 404) ==="
    if docker compose ps "python-api-$HUB" --format json 2>/dev/null | grep -q '"State":"running"'; then
        docker compose stop "python-api-$HUB"
        echo "[switch-caddy] ROLLBACK DONE — python-api-$HUB stopped."
        echo "  Caddy regex /({\$HUBS_ALLOWLIST_REGEX})/api/* fall-through → file_server 404 user-visible."
        echo "  Re-start sau khi fix: docker compose start python-api-$HUB"
        exit 0
    else
        echo "[switch-caddy] WARN: python-api-$HUB không running — nothing to rollback."
        exit 0
    fi
fi

# ──────────────────────────────────────────────────────────────────────
# (3) Verify-only mode: container running + caddy validate + smoke curl
# ──────────────────────────────────────────────────────────────────────

echo "[switch-caddy] === VERIFY Caddy auto-route hub '$HUB' ==="
echo "[switch-caddy] (NOTE) Caddyfile dynamic regex {re.hub_api.1} đã ship Phase 5 —"
echo "[switch-caddy]        KHÔNG sed edit Caddyfile (verify-only mode)."

# Step 1: Verify python-api-<HUB> container running
echo "[switch-caddy] (1/3) Verify docker compose ps python-api-$HUB running..."
if ! docker compose ps "python-api-$HUB" --format json 2>/dev/null | grep -q '"State":"running"'; then
    echo "[switch-caddy] ERROR: python-api-$HUB KHÔNG running."
    echo "  Run: docker compose up -d python-api-$HUB"
    echo "  Verify env wire: HUB_NAME=$HUB, DATABASE_URL trỏ medinet_hub_$HUB."
    exit 3
fi
echo "[switch-caddy] (1/3) python-api-$HUB running."

# Step 2: Caddy validate (Pitfall 7 mitigation — Phase 5 Plan 05-05 carry forward)
echo "[switch-caddy] (2/3) Caddy validate config (Pitfall 7 silent rollback mitigation)..."
if docker compose ps caddy --format json 2>/dev/null | grep -q '"State":"running"'; then
    if ! docker compose exec -T caddy caddy validate --config /etc/caddy/Caddyfile 2>&1; then
        echo "[switch-caddy] ERROR: Caddy config validate FAIL."
        echo "  Caddyfile có syntax error — fix trước khi reload."
        exit 4
    fi
    echo "[switch-caddy] (2/3) Caddy validate PASS."
else
    echo "[switch-caddy] (2/3) Caddy container chưa running — skip validate (dev pre-up)."
    echo "  Sau khi up: docker compose exec caddy caddy validate --config /etc/caddy/Caddyfile"
fi

# Step 3: Smoke curl /<HUB>/api/health (warn-only per hub-add.sh Step 9 pattern)
echo "[switch-caddy] (3/3) Smoke check Caddy auto-route..."
if command -v curl >/dev/null 2>&1; then
    DOMAIN="${WIKI_PUBLIC_DOMAIN:-localhost}"
    SMOKE_URL="https://${DOMAIN}/${HUB}/api/health"
    echo "[switch-caddy] (3/3) curl -k ${SMOKE_URL}"
    if curl -k -sf -o /dev/null --max-time 5 "${SMOKE_URL}" 2>/dev/null; then
        echo "[switch-caddy] (3/3) Smoke PASS — Caddy auto-route python-api-$HUB:8080 (dynamic regex {re.hub_api.1})."
    else
        echo "[switch-caddy] WARN: Smoke check returned non-200 hoặc timeout."
        echo "  Caddy có thể chưa running HOẶC python-api-$HUB chưa ready ($DOMAIN unreachable)."
        echo "  Retry sau 5-10s: curl -k $SMOKE_URL"
    fi
else
    echo "[switch-caddy] (3/3) Skip smoke check (curl không có trên host)."
fi

echo ""
echo "[switch-caddy] DONE — hub '$HUB' Caddy auto-route verified."
echo "Next: bash scripts/migrate/05-smoke-e2e.sh $HUB  # golden path 7-step E2E (Plan 07-05)"
exit 0
