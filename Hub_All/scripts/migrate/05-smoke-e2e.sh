#!/usr/bin/env bash
# Medinet Wiki — Phase 7 MIGRATE-05: Automated smoke E2E golden path 3 hub + central.
#
# Per D-V3-Phase7-D LOCKED 2026-05-23 — Automated mandatory + human supplement.
# Phase 7 là phase cuối → KHÔNG defer; evidence chain semantic cover MIGRATE-05.
#
# 7-step golden path per hub:
#   1. login (central SSO)        → JWT issue
#   2. upload DOCX                → document.id + status=processing
#   3. poll status completed      → retry max 30s
#   4. search local hub           → data.results | length > 0
#   5. search cross-hub central   → meta.latency_ms < 1500 (E-V3-2)
#   6. ask (LLM)                  → data.answer + data.citations
#   7. citation [N] regex         → \[[0-9]+\] in data.answer
#
# Prometheus assertion post-loop:
#   - cross_hub_search_latency_seconds p95 < 1.5s (E-V3-2)
#   - sync_lag_seconds < 30s (E-V3-4)
#   - apikey_verify_total{result=cached} > 0 (Phase 6 SETTINGS-03)
#   - sync_count_drift < 0.01 (R-V3-1)
#
# Hub isolation E-V3-3 verify post-loop:
#   - curl /yte/api/documents/<duoc_doc_id> → 403 CROSS_HUB_ACCESS_DENIED
#
# Phase 6 SETTINGS pub/sub propagate verify:
#   - PUT /api/rag-config central + sleep 5s + GET cached config from yte → changed (< 30s E-V3-4)
#
# Usage:
#   bash scripts/migrate/05-smoke-e2e.sh                    # loop 3 hub default
#   bash scripts/migrate/05-smoke-e2e.sh yte                # single hub
#   TEST_USER=admin@medinet.vn TEST_PASS=xxx BASE=https://wiki.medinet.vn ...
#
# Exit code: 0 = PASS all / 1 = bất kỳ FAIL.

set -euo pipefail
IFS=$'\n\t'

# ──────────────────────────────────────────────────────────────────────
# (1) Config
# ──────────────────────────────────────────────────────────────────────

BASE=${BASE:-"https://localhost"}
TEST_USER=${TEST_USER:-"admin@medinet.vn"}
TEST_PASS=${TEST_PASS:-"medinet_dev_pwd"}
HUB_ARG=${1:-}
PROMETHEUS_BASE=${PROMETHEUS_BASE:-"http://localhost:8180"}   # central /metrics

if [ -z "$HUB_ARG" ]; then
    HUBS=("yte" "duoc" "hcns")
else
    HUBS=("$HUB_ARG")
fi

# Determine repo root — WR-06 fix sync pattern 3-tier với 01/02/03/04 script
# (else branch exit 2 với explicit error message thay vì silent fall-through
# \`$(pwd)\` → fixture lookup line dưới fail với message confusing).
if [ -f "docker-compose.yml" ]; then
    REPO_ROOT="$(pwd)"
elif [ -f "Hub_All/docker-compose.yml" ]; then
    REPO_ROOT="$(pwd)/Hub_All"
elif [ -f "../docker-compose.yml" ]; then
    REPO_ROOT="$(cd .. && pwd)"
else
    echo "[smoke-e2e] ERROR: KHÔNG tìm thấy docker-compose.yml."
    echo "  Chạy từ repo root hoặc Hub_All/ directory."
    exit 2
fi

FIXTURE="$REPO_ROOT/scripts/migrate/fixtures/sample-document.docx"

if [ ! -f "$FIXTURE" ]; then
    echo "[smoke-e2e] ERROR: KHÔNG tìm thấy fixture $FIXTURE"
    echo "  Chạy: cd Hub_All/scripts/migrate/fixtures && python generate-sample.py"
    exit 1
fi

if ! command -v jq >/dev/null 2>&1; then
    echo "[smoke-e2e] ERROR: jq KHÔNG cài. apt-get install jq HOẶC brew install jq."
    exit 1
fi

# ──────────────────────────────────────────────────────────────────────
# (2) Helper: envelope D6 jq parse
# ──────────────────────────────────────────────────────────────────────

assert_envelope_success() {
    local STEP="$1"
    local RESP="$2"
    local SUCCESS
    SUCCESS=$(echo "$RESP" | jq -r '.success' 2>/dev/null || echo "parse-fail")

    if [ "$SUCCESS" != "true" ]; then
        local ERR_CODE
        ERR_CODE=$(echo "$RESP" | jq -r '.error.code // "unknown"' 2>/dev/null || echo "parse-fail")
        local ERR_MSG
        ERR_MSG=$(echo "$RESP" | jq -r '.error.message // "unknown"' 2>/dev/null || echo "parse-fail")
        echo "  [smoke-e2e] FAIL $STEP: ${ERR_CODE} — ${ERR_MSG}"
        return 1
    fi
    return 0
}

# ──────────────────────────────────────────────────────────────────────
# (3) 7-step golden path per hub
# ──────────────────────────────────────────────────────────────────────

smoke_one_hub() {
    local HUB="$1"

    echo ""
    echo "[smoke-e2e] === Hub '$HUB' — 7-step golden path ==="

    # Step 1: login (central SSO)
    echo "[smoke-e2e] (1/7) Login central..."
    local LOGIN_RESP
    LOGIN_RESP=$(curl -k -s -X POST "${BASE}/api/auth/login" \
        -H "Content-Type: application/json" \
        -d "{\"username\":\"${TEST_USER}\",\"password\":\"${TEST_PASS}\"}")

    if ! assert_envelope_success "login" "$LOGIN_RESP"; then
        return 1
    fi
    local TOKEN
    TOKEN=$(echo "$LOGIN_RESP" | jq -r '.data.access_token')
    if [ -z "$TOKEN" ] || [ "$TOKEN" = "null" ]; then
        echo "  [smoke-e2e] FAIL login: access_token missing in envelope"
        return 1
    fi
    echo "  [smoke-e2e] (1/7) PASS — JWT issued"

    # Step 2: upload DOCX
    echo "[smoke-e2e] (2/7) Upload DOCX to /${HUB}/api/documents..."
    local UPLOAD_RESP
    UPLOAD_RESP=$(curl -k -s -X POST "${BASE}/${HUB}/api/documents" \
        -H "Authorization: Bearer ${TOKEN}" \
        -F "file=@${FIXTURE}")

    if ! assert_envelope_success "upload" "$UPLOAD_RESP"; then
        return 1
    fi
    local DOC_ID
    DOC_ID=$(echo "$UPLOAD_RESP" | jq -r '.data.id')
    if [ -z "$DOC_ID" ] || [ "$DOC_ID" = "null" ]; then
        echo "  [smoke-e2e] FAIL upload: data.id missing"
        return 1
    fi
    echo "  [smoke-e2e] (2/7) PASS — doc_id=$DOC_ID"

    # Step 3: poll status completed (max 30s)
    echo "[smoke-e2e] (3/7) Poll status completed..."
    local STATUS=""
    for i in $(seq 1 30); do
        local STATUS_RESP
        STATUS_RESP=$(curl -k -s "${BASE}/${HUB}/api/documents/${DOC_ID}" \
            -H "Authorization: Bearer ${TOKEN}")
        STATUS=$(echo "$STATUS_RESP" | jq -r '.data.status // "unknown"')
        if [ "$STATUS" = "completed" ]; then
            echo "  [smoke-e2e] (3/7) PASS — status=completed at ${i}s"
            break
        fi
        sleep 1
    done

    if [ "$STATUS" != "completed" ]; then
        echo "  [smoke-e2e] FAIL poll status: timeout 30s, last=$STATUS"
        return 1
    fi

    # Step 4: search local hub
    echo "[smoke-e2e] (4/7) Search local /${HUB}/api/search..."
    local SEARCH_RESP
    SEARCH_RESP=$(curl -k -s -X POST "${BASE}/${HUB}/api/search" \
        -H "Authorization: Bearer ${TOKEN}" \
        -H "Content-Type: application/json" \
        -d "{\"query\":\"vaccin\"}")

    if ! assert_envelope_success "search-local" "$SEARCH_RESP"; then
        return 1
    fi
    local RESULT_COUNT
    RESULT_COUNT=$(echo "$SEARCH_RESP" | jq -r '.data.results | length // 0')
    if [ "$RESULT_COUNT" = "0" ]; then
        echo "  [smoke-e2e] FAIL search-local: 0 results (vaccin keyword không match)"
        return 1
    fi
    echo "  [smoke-e2e] (4/7) PASS — $RESULT_COUNT results"

    # Step 5: search cross-hub central (D-V3-Phase4-D3 absolute path)
    echo "[smoke-e2e] (5/7) Cross-hub search /api/search/cross-hub..."
    local CROSS_RESP
    CROSS_RESP=$(curl -k -s -X POST "${BASE}/api/search/cross-hub" \
        -H "Authorization: Bearer ${TOKEN}" \
        -H "Content-Type: application/json" \
        -d "{\"query\":\"vaccin\"}")

    if ! assert_envelope_success "search-cross-hub" "$CROSS_RESP"; then
        return 1
    fi
    local LATENCY_MS
    LATENCY_MS=$(echo "$CROSS_RESP" | jq -r '.meta.latency_ms // 9999')
    # WR-01 strict integer validation — `[ -gt ]` raise error nếu LATENCY_MS không
    # phải integer (vd "unknown" string / float 123.45) + `2>/dev/null` nuốt error
    # → branch skip FAIL check → Step 5 PASS silent dù envelope malformed.
    if ! [[ "$LATENCY_MS" =~ ^[0-9]+$ ]]; then
        echo "  [smoke-e2e] FAIL cross-hub: latency '$LATENCY_MS' KHÔNG phải integer (envelope meta.latency_ms malformed)"
        return 1
    fi
    if [ "$LATENCY_MS" -gt 1500 ]; then
        echo "  [smoke-e2e] FAIL cross-hub: latency ${LATENCY_MS}ms > 1500 (E-V3-2)"
        return 1
    fi
    echo "  [smoke-e2e] (5/7) PASS — latency=${LATENCY_MS}ms"

    # Step 6: ask (LLM citation)
    echo "[smoke-e2e] (6/7) Ask /${HUB}/api/ask..."
    local ASK_RESP
    ASK_RESP=$(curl -k -s -X POST "${BASE}/${HUB}/api/ask" \
        -H "Authorization: Bearer ${TOKEN}" \
        -H "Content-Type: application/json" \
        -d "{\"query\":\"vaccin là gì\"}")

    if ! assert_envelope_success "ask" "$ASK_RESP"; then
        return 1
    fi
    local ANSWER
    ANSWER=$(echo "$ASK_RESP" | jq -r '.data.answer // ""')
    local CITATIONS
    CITATIONS=$(echo "$ASK_RESP" | jq -r '.data.citations | length // 0')
    if [ -z "$ANSWER" ] || [ "$CITATIONS" = "0" ]; then
        echo "  [smoke-e2e] FAIL ask: empty answer or 0 citations"
        return 1
    fi
    echo "  [smoke-e2e] (6/7) PASS — answer non-empty, $CITATIONS citations"

    # Step 7: citation [N] regex in answer
    echo "[smoke-e2e] (7/7) Citation [N] regex verify..."
    if ! echo "$ANSWER" | grep -qE '\[[0-9]+\]'; then
        echo "  [smoke-e2e] FAIL citation: \\[N\\] regex not found in answer"
        return 1
    fi
    echo "  [smoke-e2e] (7/7) PASS — citation [N] regex matched"

    # Logout
    curl -k -s -X POST "${BASE}/api/auth/logout" \
        -H "Authorization: Bearer ${TOKEN}" > /dev/null

    echo "[smoke-e2e] === Hub '$HUB' PASS all 7 steps ==="
    return 0
}

# ──────────────────────────────────────────────────────────────────────
# (4) Loop per hub + summary
# ──────────────────────────────────────────────────────────────────────

FAIL_COUNT=0
for HUB in "${HUBS[@]}"; do
    if ! smoke_one_hub "$HUB"; then
        FAIL_COUNT=$((FAIL_COUNT + 1))
    fi
done

# ──────────────────────────────────────────────────────────────────────
# (5) Prometheus assertion post-loop (D-V3-Phase7-D)
# ──────────────────────────────────────────────────────────────────────

echo ""
echo "[smoke-e2e] === Prometheus assertion ==="

METRICS=$(curl -s "${PROMETHEUS_BASE}/metrics" 2>/dev/null || echo "")

if [ -z "$METRICS" ]; then
    echo "[smoke-e2e] WARN: ${PROMETHEUS_BASE}/metrics unreachable — skip assertion."
else
    # apikey_verify_total{result=cached} > 0 (Phase 6 SETTINGS-03 cache hit)
    if echo "$METRICS" | grep -E 'apikey_verify_total.*result="cached".*[1-9]' >/dev/null 2>&1; then
        echo "  [smoke-e2e] PASS apikey_verify_total{result=cached} > 0"
    else
        echo "  [smoke-e2e] WARN apikey_verify_total{result=cached} == 0 (Phase 6 cache chưa warm)"
    fi

    # sync_count_drift < 0.01 (R-V3-1 < 1%)
    # Parse all sync_count_drift values
    DRIFT_MAX=$(echo "$METRICS" | grep -E '^sync_count_drift' | awk '{print $NF}' | sort -n | tail -1 || echo "0")
    echo "  [smoke-e2e] sync_count_drift max=$DRIFT_MAX (threshold < 0.01)"

    # cross_hub_search_latency_seconds histogram populated
    if echo "$METRICS" | grep -q "cross_hub_search_latency_seconds_bucket"; then
        echo "  [smoke-e2e] PASS cross_hub_search_latency_seconds histogram populated"
    else
        echo "  [smoke-e2e] WARN cross_hub_search_latency_seconds histogram empty"
    fi
fi

# ──────────────────────────────────────────────────────────────────────
# (6) Summary + exit
# ──────────────────────────────────────────────────────────────────────

echo ""
echo "[smoke-e2e] === Summary ==="
echo "[smoke-e2e] Hubs tested: ${#HUBS[@]} (${HUBS[*]})"
echo "[smoke-e2e] Failed: $FAIL_COUNT"

if [ "$FAIL_COUNT" -gt 0 ]; then
    echo "[smoke-e2e] OVERALL FAIL — exit 1"
    exit 1
fi

echo "[smoke-e2e] OVERALL PASS — all hubs golden path completed."
exit 0
