#!/usr/bin/env bash
# Medinet Wiki — Rebuild all (FE + BE) sau khi sửa code.
#
# Mặc định: rebuild cả Frontend (Vite build → dist/ Caddy auto-serve qua volume
# read-only mount) + Backend (docker compose build + recreate các API container
# đang active: central + dmd + mcp_service).
#
# Active hub deployment hiện tại (2026-05-25): python-api-central + python-api-dmd
# (override.yml) + mcp_service. yte/duoc/hcns là ghost — KHÔNG build/recreate vì
# không có DB row hub.id khớp (xem memory project_real_hubs_deployment).
#
# Usage (chạy từ Hub_All/ root):
#   bash scripts/rebuild-all.sh                 # rebuild FE + BE + recreate
#   bash scripts/rebuild-all.sh --fe-only       # chỉ build FE (Caddy reload nếu hot)
#   bash scripts/rebuild-all.sh --be-only       # chỉ rebuild BE (skip Vite)
#   bash scripts/rebuild-all.sh --no-cache      # docker build --no-cache (slow nhưng clean)
#   bash scripts/rebuild-all.sh --logs          # tail logs sau khi recreate xong
#   bash scripts/rebuild-all.sh --fe-only --logs
#
# Exit code: 0 success / 1 fail tại bước nào đó (script set -euo pipefail).

set -euo pipefail

# ── Color helpers ────────────────────────────────────────────────────────────
if [ -t 1 ]; then
  RED=$'\033[0;31m'; GREEN=$'\033[0;32m'; YELLOW=$'\033[1;33m'
  BLUE=$'\033[0;34m'; BOLD=$'\033[1m'; NC=$'\033[0m'
else
  RED=""; GREEN=""; YELLOW=""; BLUE=""; BOLD=""; NC=""
fi

log()  { printf "%s[rebuild]%s %s\n" "$BLUE" "$NC" "$*"; }
ok()   { printf "%s[rebuild]%s %s\n" "$GREEN" "$NC" "$*"; }
warn() { printf "%s[rebuild]%s %s\n" "$YELLOW" "$NC" "$*"; }
err()  { printf "%s[rebuild]%s %s\n" "$RED" "$NC" "$*" >&2; }

# ── Parse flags ──────────────────────────────────────────────────────────────
FE_ONLY=0
BE_ONLY=0
NO_CACHE=0
TAIL_LOGS=0

for arg in "$@"; do
  case "$arg" in
    --fe-only)   FE_ONLY=1 ;;
    --be-only)   BE_ONLY=1 ;;
    --no-cache)  NO_CACHE=1 ;;
    --logs)      TAIL_LOGS=1 ;;
    -h|--help)
      grep -E '^# ' "$0" | sed 's/^# //'
      exit 0
      ;;
    *)
      err "Unknown flag: $arg (xem --help)"
      exit 2
      ;;
  esac
done

if [ "$FE_ONLY" = "1" ] && [ "$BE_ONLY" = "1" ]; then
  err "--fe-only và --be-only không dùng cùng lúc"
  exit 2
fi

# ── Locate Hub_All root ──────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HUB_ALL_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$HUB_ALL_ROOT"
log "Working dir: $HUB_ALL_ROOT"

# ── Pre-flight ───────────────────────────────────────────────────────────────
if ! command -v docker >/dev/null 2>&1; then
  err "docker chưa cài/PATH"
  exit 1
fi
if ! docker compose version >/dev/null 2>&1; then
  err "docker compose plugin chưa cài"
  exit 1
fi

START_TS=$(date +%s)

# ── 1) Frontend build ────────────────────────────────────────────────────────
if [ "$BE_ONLY" = "0" ]; then
  log "${BOLD}[1/3] Frontend build (Vite)${NC}"
  pushd frontend >/dev/null

  if [ ! -d node_modules ]; then
    warn "node_modules chưa có → chạy npm ci"
    npm ci
  fi

  log "Vite build → frontend/dist/"
  npm run build
  popd >/dev/null
  ok "Frontend build xong → Caddy serve qua volume mount ./frontend/dist:/srv/wiki/dist:ro (no restart cần)"
else
  warn "Skip frontend (--be-only)"
fi

# ── 2) Backend image rebuild ─────────────────────────────────────────────────
# Active services (hiện tại 2026-05-25): central + dmd + mcp_service.
# Nếu sau này thêm hub qua `make hub-add HUB=<name>` → operator UPDATE
# array dưới đây HOẶC chạy thủ công `docker compose build python-api-<hub>`.
API_SERVICES=(python-api-central python-api-dmd)
ALL_SERVICES=("${API_SERVICES[@]}" mcp_service)

if [ "$FE_ONLY" = "0" ]; then
  log "${BOLD}[2/3] Backend rebuild${NC} (services: ${ALL_SERVICES[*]})"

  BUILD_ARGS=()
  [ "$NO_CACHE" = "1" ] && BUILD_ARGS+=(--no-cache)

  docker compose build "${BUILD_ARGS[@]}" "${ALL_SERVICES[@]}"
  ok "Backend image rebuild xong"

  # ── 3) Recreate containers ─────────────────────────────────────────────────
  log "${BOLD}[3/3] Recreate containers${NC} (--force-recreate, infra services KHÔNG đụng)"
  # Không đụng postgres + redis + caddy (infra) — tránh interrupt DB/cache.
  docker compose up -d --force-recreate --no-deps "${ALL_SERVICES[@]}"
  ok "Containers recreated"

  # ── Health check ────────────────────────────────────────────────────────────
  log "Chờ 5s rồi check health..."
  sleep 5
  for svc in "${API_SERVICES[@]}"; do
    cname="medinet-api-${svc#python-api-}"
    state=$(docker inspect -f '{{.State.Status}}' "$cname" 2>/dev/null || echo "missing")
    if [ "$state" = "running" ]; then
      ok "$cname: running"
    else
      err "$cname: $state — kiểm tra: docker logs $cname --tail 50"
    fi
  done
else
  warn "Skip backend (--fe-only)"
fi

# ── Summary ──────────────────────────────────────────────────────────────────
END_TS=$(date +%s)
ELAPSED=$((END_TS - START_TS))
ok "${BOLD}DONE${NC} trong ${ELAPSED}s"

if [ "$BE_ONLY" = "0" ]; then
  log "Frontend đã ở frontend/dist/ → mở https://${WIKI_PUBLIC_DOMAIN:-localhost}/ verify"
fi
if [ "$FE_ONLY" = "0" ]; then
  log "Backend smoke: curl -sk https://${WIKI_PUBLIC_DOMAIN:-localhost}/api/health | jq"
  log "              curl -sk https://${WIKI_PUBLIC_DOMAIN:-localhost}/dmd/api/health | jq"
fi

# ── Optional tail logs ───────────────────────────────────────────────────────
if [ "$TAIL_LOGS" = "1" ] && [ "$FE_ONLY" = "0" ]; then
  log "Tail logs (Ctrl+C để thoát)..."
  docker compose logs -f --tail=20 "${ALL_SERVICES[@]}"
fi
