#!/usr/bin/env bash
# Medinet Wiki — Plan 08-04 Task 1: Boot stack smoke script
#
# Tự động hoá phần boot KIỂM ĐƯỢC của Phase 8 Frontend E2E Smoke (SC1 + SC5):
#   1. docker compose up -d --build (3-service: postgres + redis + python-api).
#   2. Chờ 3 service healthy (poll tối đa 90s, in trạng thái mỗi 5s).
#   3. Verify HTTP /healthz + /readyz.
#   4. Apply alembic migration head trong container python-api.
#   5. Verify KHÔNG còn service Go (chỉ postgres + redis + python-api).
#   6. In hướng dẫn bước tiếp theo (chạy frontend dev server).
#
# Phần CHỈ con người verify được (render 11 trang React, citation [1] clickable)
# nằm ở checkpoint human-verify của Plan 08-04 — KHÔNG nằm trong script này.
#
# Script idempotent — chạy lại được nhiều lần.
#
# Usage:
#   bash api/scripts/smoke/boot_stack.sh   (chạy từ thư mục Hub_All/)
#
# Exit codes:
#   0 — PASS toàn bộ bước.
#   1 — FAIL bất kỳ bước nào (in thông điệp lỗi rõ ràng).

set -euo pipefail

# ─────────────────────────────────────────────────────────────────────────────
# Cấu hình + helper
# ─────────────────────────────────────────────────────────────────────────────

API_BASE="${API_BASE:-http://localhost:8180}"
HEALTH_TIMEOUT="${HEALTH_TIMEOUT:-90}"   # giây — tối đa chờ 3 service healthy
EXPECTED_SERVICES="postgres redis python-api"

log()  { echo "[$(date +%H:%M:%S)] $*"; }
fail() { echo "" >&2; echo "FAIL: $*" >&2; exit 1; }

# Xác định thư mục Hub_All/ (chứa docker-compose.yml). Script nằm tại
# api/scripts/smoke/boot_stack.sh → root là 3 cấp trên. KHÔNG dùng
# `git rev-parse --show-toplevel` vì git toplevel có thể là parent của Hub_All/.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

if [[ ! -f "${REPO_ROOT}/docker-compose.yml" ]]; then
  fail "Không tìm thấy docker-compose.yml tại ${REPO_ROOT} — chạy script từ Hub_All/."
fi
cd "${REPO_ROOT}"
log "Thư mục làm việc: ${REPO_ROOT}"

# ─────────────────────────────────────────────────────────────────────────────
# Bước 0: Kiểm tiền điều kiện
# ─────────────────────────────────────────────────────────────────────────────

command -v docker >/dev/null 2>&1 || fail "docker chưa cài đặt hoặc không có trong PATH."
docker compose version >/dev/null 2>&1 || fail "docker compose plugin không khả dụng."
command -v curl >/dev/null 2>&1 || fail "curl chưa cài đặt hoặc không có trong PATH."

# Cảnh báo nếu chưa có keypair JWT (api/ không boot được readyz nếu thiếu).
if [[ ! -f "${REPO_ROOT}/api/keys/private.pem" || ! -f "${REPO_ROOT}/api/keys/public.pem" ]]; then
  log "CẢNH BÁO: Chưa có keypair JWT tại api/keys/ — chạy 'make api-keys' trước nếu /readyz fail."
fi

# ─────────────────────────────────────────────────────────────────────────────
# Bước 1: docker compose up -d --build
# ─────────────────────────────────────────────────────────────────────────────

log "(1/6) docker compose up -d --build (postgres + redis + python-api)..."
docker compose up -d --build || fail "docker compose up thất bại — xem log phía trên."

# ─────────────────────────────────────────────────────────────────────────────
# Bước 2: Chờ 3 service healthy (poll tối đa HEALTH_TIMEOUT giây)
# ─────────────────────────────────────────────────────────────────────────────

log "(2/6) Chờ 3 service healthy (tối đa ${HEALTH_TIMEOUT}s)..."
elapsed=0
while true; do
  all_healthy=true
  status_line=""
  for svc in ${EXPECTED_SERVICES}; do
    cid="$(docker compose ps -q "${svc}" 2>/dev/null || true)"
    if [[ -z "${cid}" ]]; then
      svc_state="missing"
      all_healthy=false
    else
      # Container có healthcheck → đọc .State.Health.Status; nếu không có thì .State.Status.
      svc_state="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "${cid}" 2>/dev/null || echo "unknown")"
      if [[ "${svc_state}" != "healthy" ]]; then
        all_healthy=false
      fi
    fi
    status_line+="${svc}=${svc_state} "
  done

  if [[ "${all_healthy}" == "true" ]]; then
    log "  → 3 service healthy: ${status_line}"
    break
  fi

  if (( elapsed >= HEALTH_TIMEOUT )); then
    log "  → Trạng thái cuối: ${status_line}"
    docker compose ps || true
    fail "3 service KHÔNG healthy sau ${HEALTH_TIMEOUT}s — kiểm 'docker compose logs'."
  fi

  log "  ... ${status_line}(đã chờ ${elapsed}s)"
  sleep 5
  elapsed=$(( elapsed + 5 ))
done

# ─────────────────────────────────────────────────────────────────────────────
# Bước 3: Verify HTTP /healthz + /readyz
# ─────────────────────────────────────────────────────────────────────────────

log "(3/6) Verify HTTP healthcheck tại ${API_BASE}..."

healthz_body="$(curl -fsS "${API_BASE}/healthz" 2>/dev/null || true)"
if [[ -z "${healthz_body}" ]]; then
  fail "GET ${API_BASE}/healthz không phản hồi — python-api chưa expose port 8180?"
fi
if [[ "${healthz_body}" != *'"status"'* || "${healthz_body}" != *'"ok"'* ]]; then
  fail "GET /healthz body không chứa status/ok: ${healthz_body}"
fi
log "  → /healthz OK: ${healthz_body}"

readyz_body="$(curl -fsS "${API_BASE}/readyz" 2>/dev/null || true)"
if [[ -z "${readyz_body}" ]]; then
  fail "GET ${API_BASE}/readyz không phản hồi hoặc trả lỗi — DB pool / JWT chưa sẵn sàng?"
fi
log "  → /readyz OK: ${readyz_body}"

# ─────────────────────────────────────────────────────────────────────────────
# Bước 4: Apply alembic migration head
# ─────────────────────────────────────────────────────────────────────────────

log "(4/6) Apply alembic migration (alembic upgrade head) trong container python-api..."
if docker compose exec -T python-api alembic upgrade head; then
  log "  → alembic upgrade head OK."
else
  fail "alembic upgrade head thất bại — kiểm DSN / migration trong container."
fi

# ─────────────────────────────────────────────────────────────────────────────
# Bước 5: Verify KHÔNG còn service Go
# ─────────────────────────────────────────────────────────────────────────────

log "(5/6) Verify compose chỉ có 3-service, không reference Go..."
services_actual="$(docker compose config --services | sort | tr '\n' ' ' | sed 's/ $//')"
services_expected="$(echo "${EXPECTED_SERVICES}" | tr ' ' '\n' | sort | tr '\n' ' ' | sed 's/ $//')"

if [[ "${services_actual}" != "${services_expected}" ]]; then
  fail "Danh sách service không khớp. Mong đợi [${services_expected}], thực tế [${services_actual}]."
fi

# Bắt mọi service có tên chứa 'go' hoặc 'backend' (Go backend đã teardown 2026-05-14).
for svc in ${services_actual}; do
  if [[ "${svc}" == *go* || "${svc}" == *backend* ]]; then
    fail "Phát hiện service nghi Go: '${svc}' — Go backend phải đã teardown (TEARDOWN-01)."
  fi
done
log "  → compose 3-service [${services_actual}] — KHÔNG có service Go."

# ─────────────────────────────────────────────────────────────────────────────
# Bước 6: Hướng dẫn bước tiếp theo
# ─────────────────────────────────────────────────────────────────────────────

log "(6/6) Boot stack PASS."
echo ""
echo "═══════════════════════════════════════════════════════════════════════"
echo " Backend sẵn sàng tại ${API_BASE}"
echo " Tiếp theo: cd frontend && npm install && npm run dev"
echo " Rồi mở http://localhost:5173 và làm theo 08-SMOKE-CHECKLIST.md"
echo "═══════════════════════════════════════════════════════════════════════"
exit 0
