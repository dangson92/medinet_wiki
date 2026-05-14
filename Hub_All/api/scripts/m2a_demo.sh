#!/usr/bin/env bash
# Plan 04-06 REVISION 2 — M2a EXIT GATE auto-demo (subset của manual demo).
#
# Script này automate Bước 3-4-5 của docs/m2a-exit-gate-demo.md cho CI smoke test:
# - Login admin → upload DOCX VN runtime-generated → poll status (A4 BackgroundTask) → SELECT chunks.
# - Manual steps (docker compose up + scanned PDF) vẫn cần operator.
#
# REVISION 2 cập nhật:
# - KHÔNG còn target make cocoindex setup (Plan 04-03 REVISION 2 lifespan auto setup).
# - Poll loop wait 30s (A4 BackgroundTask trigger_cocoindex_update + cocoindex_app.update_blocking).
#
# Usage:
#   cd Hub_All/api && bash scripts/m2a_demo.sh
#
# Tiền điều kiện:
# - docker compose up postgres redis api (đã chạy).
# - make migrate-up (đã chạy — Plan 04-03 REVISION 2 lifespan auto setup cocoindex khi uvicorn start).
# - User admin@medinet.vn với hash R6 đã seed.
# - Hub slug 'hub_y_te' đã seed.
#
# Exit codes:
#   0 — PASS (chunks verified với dim=1536 + hub_id match + content_hash NOT NULL)
#   1 — FAIL (status không completed / chunks count = 0 / vector dim sai)

set -euo pipefail

API_URL="${API_URL:-http://localhost:8080}"
ADMIN_EMAIL="${ADMIN_EMAIL:-admin@medinet.vn}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-Admin@123}"
HUB_SLUG="${HUB_SLUG:-hub_y_te}"
PG_CONTAINER="${PG_CONTAINER:-medinet-postgres}"
PG_USER="${PG_USER:-medinet}"
PG_DB="${PG_DB:-medinet_central}"
POLL_TIMEOUT="${POLL_TIMEOUT:-30}"  # REVISION 2 — A4 BackgroundTask wait

log() { echo "[$(date +%H:%M:%S)] $*"; }
fail() { echo "FAIL: $*" >&2; exit 1; }

log "1) Health check (verify uvicorn lifespan đã setup cocoindex Plan 04-03 REVISION 2)..."
curl -fsS "$API_URL/healthz" >/dev/null || fail "Healthz fail at $API_URL"
READY=$(curl -fsS "$API_URL/readyz" || true)
if echo "$READY" | grep -q '"cocoindex":"ok"'; then
    log "cocoindex_ready_ok (lifespan setup OK)"
else
    log "cocoindex_not_ready: $READY (REVISION 2 — verify lifespan log có cocoindex_setup_ok)"
fi

log "2) Login admin..."
TOKEN=$(curl -fsS -X POST "$API_URL/api/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$ADMIN_EMAIL\",\"password\":\"$ADMIN_PASSWORD\"}" \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['data']['access_token'])")
[[ ${#TOKEN} -gt 100 ]] || fail "Token quá ngắn: ${#TOKEN} chars"
log "Token length: ${#TOKEN}"

log "3) Resolve hub_id từ slug=$HUB_SLUG..."
HUB_ID=$(docker exec "$PG_CONTAINER" psql -U "$PG_USER" -d "$PG_DB" -tA \
  -c "SELECT id FROM hubs WHERE slug='$HUB_SLUG' LIMIT 1")
[[ -n "$HUB_ID" ]] || fail "Hub slug=$HUB_SLUG không tồn tại"
log "HUB_ID=$HUB_ID"

log "4) Generate DOCX VN runtime..."
TMP_DOCX=$(mktemp --suffix=.docx)
python3 -c "
from docx import Document
doc = Document()
doc.add_paragraph('Mục 1. KHÁM TỔNG QUÁT')
doc.add_paragraph('Bệnh nhân được khám lâm sàng tỉ mỉ.')
doc.add_paragraph('Mục 2. XÉT NGHIỆM')
doc.add_paragraph('Làm xét nghiệm máu và siêu âm.')
doc.save('$TMP_DOCX')
print('Generated:', '$TMP_DOCX')
"

log "5) Upload DOCX (Plan 04-04 REVISION 2 router add A4 BackgroundTask)..."
UPLOAD=$(curl -fsS -X POST "$API_URL/api/documents/upload" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@$TMP_DOCX;filename=khám-bệnh.docx" \
  -F "hub_id=$HUB_ID")
DOC_ID=$(echo "$UPLOAD" | python3 -c "import json,sys; print(json.load(sys.stdin)['data']['document_id'])")
log "DOC_ID=$DOC_ID (status='pending' — A4 BackgroundTask đang chạy)"

log "6) Poll status đợi A4 BackgroundTask trigger_cocoindex_update + update_blocking + UPDATE status (timeout ${POLL_TIMEOUT}s)..."
STATUS="pending"
for i in $(seq 1 "$POLL_TIMEOUT"); do
  STATUS=$(curl -fsS "$API_URL/api/documents/$DOC_ID" \
    -H "Authorization: Bearer $TOKEN" \
    | python3 -c "import json,sys; print(json.load(sys.stdin)['data']['status'])")
  log "[$i] status=$STATUS"
  if [[ "$STATUS" == "completed" ]] || [[ "$STATUS" == "failed" ]] || [[ "$STATUS" == "failed_unsupported" ]]; then
    break
  fi
  sleep 1
done
[[ "$STATUS" == "completed" ]] || fail "Status không completed sau ${POLL_TIMEOUT}s: $STATUS (A4 BackgroundTask flakiness?)"

log "7) Verify chunks pgvector..."
CHUNK_COUNT=$(docker exec "$PG_CONTAINER" psql -U "$PG_USER" -d "$PG_DB" -tA \
  -c "SELECT COUNT(*) FROM chunks WHERE document_id='$DOC_ID'")
[[ "$CHUNK_COUNT" -gt 0 ]] || fail "chunks table empty"
log "chunks count=$CHUNK_COUNT"

# Verify dim = 1536 (R1 mitigation)
DIM=$(docker exec "$PG_CONTAINER" psql -U "$PG_USER" -d "$PG_DB" -tA \
  -c "SELECT vector_dims(vector) FROM chunks WHERE document_id='$DOC_ID' LIMIT 1")
[[ "$DIM" == "1536" ]] || fail "vector dim sai: $DIM (R1 yêu cầu 1536)"
log "vector dim=$DIM OK"

# Verify hub_id match (ChunkRow.hub_id wire từ doc_row REVISION 2)
HUB_MATCH=$(docker exec "$PG_CONTAINER" psql -U "$PG_USER" -d "$PG_DB" -tA \
  -c "SELECT COUNT(*) FROM chunks WHERE document_id='$DOC_ID' AND hub_id='$HUB_ID'")
[[ "$HUB_MATCH" == "$CHUNK_COUNT" ]] || fail "hub_id mismatch: $HUB_MATCH/$CHUNK_COUNT chunks match"
log "hub_id match=$HUB_MATCH/$CHUNK_COUNT OK"

# Verify content_hash NOT NULL (ChunkRow.content_hash sha256 wire REVISION 2)
HASH_NOT_NULL=$(docker exec "$PG_CONTAINER" psql -U "$PG_USER" -d "$PG_DB" -tA \
  -c "SELECT COUNT(*) FROM chunks WHERE document_id='$DOC_ID' AND content_hash IS NOT NULL")
[[ "$HASH_NOT_NULL" == "$CHUNK_COUNT" ]] || fail "content_hash NULL ở $((CHUNK_COUNT - HASH_NOT_NULL)) rows (D-1 violated)"
log "content_hash set=$HASH_NOT_NULL/$CHUNK_COUNT OK"

echo ""
echo "============================================"
echo "M2A_DEMO_PASS chunks=$CHUNK_COUNT dim=$DIM hub_id_match=$HUB_MATCH content_hash_set=$HASH_NOT_NULL"
echo "============================================"

rm -f "$TMP_DOCX"
exit 0
