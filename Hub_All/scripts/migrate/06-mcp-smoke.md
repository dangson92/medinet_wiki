# MCP Smoke Runbook (Phase 7 v3.0 MIGRATE-04)

**Created:** 2026-05-23 (Phase 7 Plan 07-04)
**Decision:** D-V3-Phase7-C LOCKED — MCP re-point central aggregate (KHÔNG fan-out N hub).
**Carry forward:** Phase 8.3 v2.0 OAuth flow UNCHANGED + 135/135 mcp_service/tests/ regression baseline.

Manual checklist 5-step verify MCP service hoạt động sau Phase 7 re-point `api_base_url = http://python-api-central:8080`. Operator chạy sau khi `docker compose up -d mcp_service`.

## Pre-deploy verify (mandatory)

Trước khi smoke, verify regression baseline:

```bash
cd Hub_All/mcp_service
uv run pytest -q
# Expected: 135 passed (Phase 8.3 v2.0 baseline)
# Thực tế hiện tại: 143 passed (8 test thêm từ Plan 10-04 CORS split policy)
# Nếu FAIL → block deploy, fix trước.
```

Verify container running:

```bash
cd Hub_All
docker compose ps mcp_service
# Expected: State=running

docker compose logs --tail=50 mcp_service
# Expected: KHÔNG có boot error; thấy "Application startup complete"
```

Verify env wire central re-point:

```bash
docker compose exec mcp_service env | grep MCP_API_BASE_URL
# Expected: MCP_API_BASE_URL=http://python-api-central:8080
```

## Smoke checklist 5-step

### Step 1 — Connect Claude Inspector via OAuth

Browser tới Inspector URL (https://inspector.modelcontextprotocol.io HOẶC `http://localhost:6274` dev):

1. Inspector "Add Server" → MCP URL: `https://wiki.medinet.vn/mcp/` (prod) HOẶC `http://localhost:8190/` (dev native).
2. Click "Authorize" → Inspector redirect tới `wiki.medinet.vn/mcp/auth/v2/authorize` (OAuth flow Phase 8.3).
3. Verify discovery metadata response 200:
   ```bash
   curl -k https://wiki.medinet.vn/.well-known/oauth-authorization-server | jq '.'
   # Expected: {issuer, authorization_endpoint, token_endpoint, registration_endpoint, ...}
   ```
4. Complete OAuth dance: enter test credentials (admin@medinet.vn / dev password) → consent screen → redirect Inspector với code → token exchange.
5. Inspector connection state: **Connected** (green indicator).

**FAIL signal:** Discovery 404 / token exchange 401 / CORS preflight reject → check Caddy reverse proxy `/.well-known/*` + `/mcp/*` route (Phase 5 PROXY-01 carry forward).

### Step 2 — Call `search_wiki(query="vaccin", hub_id="yte")` single-hub

Inspector tools tab → invoke `search_wiki`:

```json
{
  "query": "vaccin",
  "hub_id": "yte"
}
```

Expected response envelope D6:
```json
{
  "success": true,
  "data": {
    "results": [
      {
        "chunk_id": "...",
        "content": "Vaccin (vaccine) là chế phẩm sinh học...",
        "score": 0.85,
        "hub_id": "yte",
        "document_id": "..."
      }
    ]
  },
  "error": null,
  "meta": {"hub_id": "yte"}
}
```

**Verify:** Tất cả chunks chứa `hub_id="yte"` only (KHÔNG cross-hub leak).

**FAIL signal:** 403 CROSS_HUB_ACCESS_DENIED → JWT user thiếu `hub_ids=["yte"]` claim (Phase 3 Plan 03-03 hub_ids REQUIRED). 500 → central upstream down hoặc DB connection fail.

### Step 3 — Call `ask_wiki(query="dược ngoại")` cross-hub no hub_id

Inspector tools tab → invoke `ask_wiki`:

```json
{
  "query": "dược ngoại"
}
```

Expected response:
```json
{
  "success": true,
  "data": {
    "answer": "Theo tài liệu [1], dược ngoại là... [2] đề cập...",
    "citations": [
      {"id": 1, "chunk_id": "...", "hub_id": "duoc", "content": "...", "document_id": "..."},
      {"id": 2, "chunk_id": "...", "hub_id": "yte", "content": "..."}
    ]
  }
}
```

**Verify:**
- Cross-hub aggregation: citations từ MULTIPLE hub_id (intersection user.hub_ids ∩ all hubs = central aggregate Phase 4 Plan 04-05).
- Citation `[N]` xuất hiện trong `data.answer` text (M2 LLM citation Phase 7 v2.0 carry forward).
- Latency p95 < 1.5s (E-V3-2 — đo qua Inspector network tab).

**FAIL signal:** citations chỉ 1 hub → cross-hub search aggregate fail (Phase 4 Plan 04-05 D-V3-Phase4-D1 broke). Empty answer → LLM provider down hoặc rag_config sai (Phase 6 SETTINGS-01 cache stale).

### Step 4 — Verify citation `[N]` resolve

Click `[1]` link trong Inspector response → expect popup hoặc detail view document:

1. Document title displayed.
2. Document hub_id match citation `hub_id` field.
3. Chunk content highlight trong document body (carry forward M2 Phase 7 v2.0).

**Verify:** `GET /api/documents/<id>` envelope D6 success + data.id match citation chunk_id parent document.

**FAIL signal:** 404 document → chunk_id orphan (sync drift R-V3-1 — chạy `POST /api/sync/replay` Phase 4 Plan 04-06 recover). 403 → hub access enforce (Phase 3 SSO-04 E4 3-layer).

### Step 5 — Verify Prometheus metrics post-smoke

```bash
curl http://localhost:8180/metrics | grep -E "apikey_verify_total|cross_hub_search_latency"
# Expected:
#   apikey_verify_total{hub_name="central",result="cached"} > 0  (Phase 6 SETTINGS-03 cache hit)
#   cross_hub_search_latency_seconds histogram populated (Phase 4 Plan 04-05)

curl http://localhost:8180/metrics | grep -E "sync_lag_seconds|sync_count_drift"
# Expected:
#   sync_lag_seconds{hub_name=...} < 30 (E-V3-4)
#   sync_count_drift{hub_name=...} < 0.01 (< 1% drift, R-V3-1)
```

**FAIL signal:** sync_lag > 30s → hub con worker stale (Phase 4 Plan 04-04 lifespan). count_drift > 1% → checksum scheduler alert (Phase 4 Plan 04-06).

## Rollback procedure

Nếu Step 1-5 FAIL critical (vd: OAuth flow break / fan-out N hub instead aggregate):

```bash
# 1. Stop mcp_service
docker compose stop mcp_service

# 2. Revert config.py + docker-compose.yml comment changes
git revert <commit-sha-phase7-mcp-repoint>

# 3. Re-build + restart
docker compose up -d --build mcp_service

# 4. Re-run regression
cd mcp_service && uv run pytest -q
# Expected: 135 passed (143 thực tế post-Phase 10-04)

# 5. Manual verify Inspector connect lại
```

M2 monolith `http://localhost:8180` legacy default reachable (port 8180 = python-api-central host map, container alias `python-api-central:8080`).

## Reference

- `Hub_All/mcp_service/mcp_app/config.py` — Settings.api_base_url default re-point central.
- `Hub_All/docker-compose.yml` lines 264-271 — env wire MCP_API_BASE_URL.
- `.planning/phases/07-migration-smoke-e2e/07-CONTEXT.md` §decisions D-V3-Phase7-C LOCKED.
- `.planning/phases/07-migration-smoke-e2e/07-04-PLAN.md` — Plan này.
- Phase 8.3 v2.0 archive (`.planning/milestones/v2.0-archive/`) — OAuth 9-plan ship carry forward UNCHANGED.
- Phase 4 Plan 04-05 — Cross-hub search 1 SQL aggregated D-V3-Phase4-D1 LOCKED.
