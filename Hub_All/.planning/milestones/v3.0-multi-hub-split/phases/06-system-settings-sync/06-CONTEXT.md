---
phase: 6
phase_name: System Settings Sync
slug: system-settings-sync
milestone: v3.0
gathered: 2026-05-23
source: planner-seed-defaults (Auto Mode `--auto --chain`)
status: Ready for planning
---

# Phase 6: System Settings Sync — Context

**Gathered:** 2026-05-23
**Status:** Ready for planning
**Source:** Auto Mode `--auto --chain` — gray area GA-V3-B + 4 sub-decision chốt theo recommended seed defaults (REQUIREMENTS.md SETTINGS-01..04 đã lock pattern). KHÔNG mở `/gsd-discuss-phase 6` interactive.

> Nguồn quyết định: REQUIREMENTS.md (SETTINGS-01..04 spec chi tiết `rag_config` HTTP pull + cache Redis TTL 60s + pub/sub `settings:invalidate` + api_keys verify proxy + hub_registry read-only) + ROADMAP.md Phase 6 success criteria + carry-forward decisions từ Phase 3 (Settings.central_url + httpx async client + Settings.central_jwks_url pattern) + Phase 4 (asyncpg pool central_sync_pool + Prometheus metric per-hub) + M2 carry forward (`rag_config_service.py` AES-GCM at-rest, `api_key.py::require_api_key` dependency, `search_cache.py` Redis pub/sub pattern).

---

<domain>
## Phase Boundary

**WHAT phase 6 ships:**

1. **Hub con `rag_config` HTTP pull on-demand** — `GET https://central/api/rag-config` qua httpx async client (Phase 3 pattern carry forward). Cache local Redis TTL 60s key `settings:rag_config:{hub_name}`. Fail-loud nếu central down sau TTL expire (KHÔNG silent degrade → 503 envelope `SETTINGS_UNAVAILABLE`).

2. **Pub/sub invalidate cross-process** — Central `PUT /api/rag-config` (M2 carry forward) extend publish `settings:invalidate` channel với payload `{"config_key":"rag_config","hub":"<name>|*","timestamp":<unix>}`. Hub con subscriber `settings_subscriber` (asyncio task lifespan) lắng nghe → flush local Redis cache key tương ứng. E-V3-4 threshold: propagate < 30s (TTL 60s overlap đảm bảo nhanh hơn).

3. **API key verify proxy** — Hub con `X-API-Key:` header → gọi central `POST /api/api-keys/verify` (endpoint MỚI, Phase 6 ship ở central). Cache Redis TTL 60s key `apikey:verify:<sha256(key)>` (hash, KHÔNG plaintext). 401 nếu central reject. Central giữ nguyên AES-GCM at-rest từ M2 AUX-02 (KHÔNG đụng `api_key_service.verify_key` private logic).

4. **`hub_registry` read-only ở hub con** — Hub con load list hub_id + subpath + active từ central qua HTTP pull `GET https://central/api/hubs` (M2 endpoint hiện hữu, Plan 05-03 HUB-01) TTL 5 phút (rare-change) key `settings:hub_registry`. Hub con `POST/PUT/PATCH /api/hubs*` đã 404 do FACTOR-02 strip Phase 2 (hubs_router central-only). Read-only path: HubRegistryClient + lifespan startup fetch_initial fail-loud + background refresh task pattern song song JWKSCache Plan 03-02.

5. **Settings client module mới `api/app/settings_sync/`** — 4 file:
   - `keys.py` — Redis cache key constants + pub/sub channel name.
   - `client.py` — `RagConfigClient` + `HubRegistryClient` + `ApiKeyVerifyClient` (3 client class, share base httpx pattern).
   - `subscriber.py` — `settings_subscriber` asyncio task psubscribe `settings:invalidate`.
   - `__init__.py` — re-export public API.

6. **Central extend `api/rag-config` PUT + `api/api-keys` verify endpoint:**
   - `PUT /api/rag-config` (M2 carry forward) thêm: sau commit DB → `redis.publish("settings:invalidate", json.dumps({"config_key":"rag_config","hub":"*","timestamp":...}))`. Best-effort fail-open (Redis down KHÔNG block PUT — TTL natural expire fallback).
   - `POST /api/api-keys/verify` MỚI ở central — body `{"api_key": "mdk_..."}` → trả `{valid: bool, principal: {id, permissions, allowed_hub_ids} | null}`. Admin-only? KHÔNG — endpoint này verify proxy cho hub con, dùng internal-only header `X-Internal-Auth: <shared_secret>` (env `SETTINGS_PROXY_SECRET`). Rate limit Redis token bucket 100 req/s per IP (defense-in-depth T-06-03-01).
   - `GET /api/hubs` (M2 hiện hữu) KHÔNG đổi — hub con dùng `X-Internal-Auth` header (settings_proxy_secret) HOẶC JWT admin token. Phase 6 chọn shared secret (đơn giản hơn provisioning JWT cho hub con internal call).

7. **Hub con `api/app/main.py::lifespan` thêm:**
   - `settings_sync_redis_pool` shared connection cho subscriber + cache.
   - `rag_config_client.fetch_initial()` blocking 5s (fail-loud boot pattern song song JWKSCache Phase 3 Plan 03-02).
   - `hub_registry_client.fetch_initial()` blocking 5s.
   - `settings_subscriber_task = asyncio.create_task(settings_subscriber_loop(...))` spawn.
   - Shutdown graceful: cancel subscriber_task + wait 10s + close redis pool.

8. **6 Prometheus metric mới (Phase 6 observability — pattern song song Phase 4):**
   - `settings_cache_hit_total{hub_name, key_type=rag_config|hub_registry|apikey}` counter.
   - `settings_cache_miss_total{hub_name, key_type}` counter.
   - `settings_pull_latency_seconds{hub_name, endpoint}` histogram (httpx central call).
   - `settings_invalidate_received_total{hub_name, key_type}` counter (pub/sub events).
   - `settings_stale_seconds{hub_name, key_type}` gauge (now - last_successful_pull).
   - `apikey_verify_total{hub_name, result=valid|invalid|cached}` counter.

**WHAT phase 6 KHÔNG ship:**

- `hub_registry` table thay thế `Settings.hub_name` env — defer v4.0 (Phase 6 chỉ pull endpoint hiện hữu, KHÔNG đụng schema).
- Push webhook thay HTTP pull — GA-V3-B đã reject (pull đơn giản hơn, latency acceptable < 30s qua pub/sub).
- Adaptive TTL — defer v4.0 (60s default đủ M2 settings change frequency).
- HA Redis cluster — defer v4.0 (R-V3-6 LOW, 1 Redis instance OK).
- MCP service settings sync — defer Phase 7 MIGRATE-04 (re-point central pattern).
- Frontend rewrite settings UI — D6 expired ở Phase 5; settings UI giữ nguyên central-only (M2 Settings.tsx + Documents ingest UI dùng `/api/rag-config` qua Caddy route central).

</domain>

<decisions>
## Implementation Decisions

### GA-V3-B · System Settings Sync Mechanism (LOCKED — recommended seed)

**D-V3-Phase6-A:** **HTTP pull on-demand + Redis pub/sub invalidate hybrid** — KHÔNG push webhook (REJECT), KHÔNG env var local (REJECT).

**Rationale:**
- HTTP pull đơn giản: hub con lifespan startup fetch_initial fail-loud + background asyncio task refresh trên cache miss/TTL expire. Pattern song song Phase 3 Plan 03-02 JWKSCache (đã proven).
- Pub/sub invalidate giải quyết "TTL window stale" — đổi config ở central → publish ngay → hub con flush cache trong < 1s thực tế (E-V3-4 < 30s threshold thừa margin).
- Push webhook REJECT: complexity hub con phải expose endpoint receive (security surface area + Caddy routing thêm rule); pub/sub Redis dùng infra hiện hữu.
- Env var local REJECT: đổi config phải redeploy hub con → không phù hợp ASK-04 hot-swap pattern M2 (rag_config update runtime).

**Reject alternatives:**
- Push webhook: thêm endpoint hub con + Caddy route + retry logic + idempotency key — over-engineer cho 3 setting category.
- Env var local: redeploy mọi đổi config → phá ASK-04 hot-swap M2.
- Postgres LISTEN/NOTIFY: cocoindex đã dùng (R5 conflict risk) + cross-instance pub/sub thực tế dùng Redis (Postgres LISTEN/NOTIFY single-instance only).

### D-V3-Phase6-B · Cache TTL Strategy (LOCKED — recommended seed)

**Chốt:**
- `rag_config`: TTL **60s** (default — E-V3-4 propagate < 30s; pub/sub overlap natural).
- `hub_registry`: TTL **300s (5 phút)** (rare-change — operator add hub qua `make hub-add` không thường xuyên).
- `apikey:verify`: TTL **60s** (M2 baseline + AUX-02 hot revoke acceptable window).

**Rationale:**
- 60s rag_config: TTL ngắn = stale window ngắn; pub/sub invalidate là PRIMARY mechanism, TTL là FALLBACK (Redis down recovery).
- 300s hub_registry: hub_registry đổi rare → TTL dài giảm load central. Pub/sub vẫn invalidate ngay khi `make hub-add` → publish `settings:invalidate` `config_key="hub_registry"`.
- 60s apikey: AUX-02 revoke API key → 60s tolerable; admin revoke + flush qua manual `POST /api/api-keys/{id}/revoke` → publish `settings:invalidate` `config_key="apikey"` flush cache 1 hub hoặc all.

**Reject:**
- Adaptive TTL: over-engineer cho 3 category; defer v4.0.
- 5min default cho mọi key: hub_registry OK nhưng rag_config + apikey window quá dài cho M2 hot-swap UX.

### D-V3-Phase6-C · Pub/Sub Channel Schema (LOCKED — recommended seed)

**Chốt:**
- **1 channel `settings:invalidate`** cho cả 3 category (KHÔNG split `settings:rag_config:invalidate` + `settings:hub_registry:invalidate` + `settings:apikey:invalidate`).
- Payload JSON `{"config_key": "rag_config|hub_registry|apikey", "hub": "yte|*", "key_id"?: "<uuid>", "timestamp": <unix>}`.
  - `config_key`: required, 1 trong 3 enum value.
  - `hub`: required, hub name cụ thể HOẶC `"*"` (broadcast all hub con).
  - `key_id`: optional, cho apikey invalidate granular (1 specific key revoke); rag_config + hub_registry KHÔNG dùng.
  - `timestamp`: unix epoch seconds, debug + ordering.
- Subscriber pattern: `redis.pubsub().psubscribe("settings:invalidate")` (KHÔNG psubscribe pattern — 1 channel cụ thể).

**Rationale:**
- 1 channel đơn giản subscribe + payload filter logic ở subscriber. 3 channel = 3 subscribe call + dedup logic phức tạp.
- `config_key` enum 3 value: extensibility tốt (Phase 7 thêm "mcp_token" OK), KHÔNG free-form (T-06-03-03 injection mitigation — validator enum).
- `hub="*"` broadcast: rag_config + hub_registry là global config, đổi 1 lần → mọi hub flush. apikey thường specific hub (1 hub assign key), nhưng dùng `"*"` mặc định OK (flush hub không có key = no-op).

**Reject:**
- 3 channel split: complexity subscribe + chia codepath subscriber.
- Pattern subscribe `settings:*`: matching overhead Redis + collision với future channel namespace.

### D-V3-Phase6-D · API Key Verify Proxy Authentication (LOCKED — recommended seed)

**Chốt:** **Shared secret header `X-Internal-Auth: <SETTINGS_PROXY_SECRET>`** cho 2 endpoint internal-only ở central:
- `POST /api/api-keys/verify` (hub con call).
- (Tương lai) `POST /api/rag-config/internal-flush` (defer — KHÔNG ship Phase 6).

**Implementation:**
- Settings field MỚI `settings_proxy_secret: str` (env `SETTINGS_PROXY_SECRET`, validator min length 32 char, required cho cả central + hub con).
- Central dependency MỚI `require_internal_auth` ở `api/app/auth/dependencies.py`: header check `X-Internal-Auth == settings.settings_proxy_secret` (constant-time compare hmac.compare_digest) → 401 `INTERNAL_AUTH_FAIL` envelope nếu mismatch.
- Endpoint `POST /api/api-keys/verify` ở central mount conditional `if settings.hub_name == "central"` (FACTOR-02 + Phase 2 pattern).
- Rate limit Redis token bucket 100 req/s per IP qua middleware (defense-in-depth — secret leak protect).

**Rationale:**
- JWT internal-only quá phức tạp: phải provision service token cho hub con + rotate.
- Shared secret đủ cho internal network call (docker-compose private network) + audit qua audit_logs M2.
- Constant-time compare hmac.compare_digest tránh timing attack.
- T-06-04-01 STRIDE Tampering — header spoofing chỉ work nếu attacker biết secret; 32-char random hex/base64 = 128-bit entropy đủ.

**Reject:**
- JWT internal-only: complexity + rotation burden — over-engineer Phase 6 scope.
- mTLS: docker-compose dev mode khó setup cert; defer v4.0 production hardening.
- IP allowlist: docker-compose service network IP volatile; không robust với FACTOR-04 dynamic hub add.

### Claude's Discretion

- httpx async client: dùng `httpx.AsyncClient` singleton qua `lru_cache` (pattern Phase 3 JWKSCache + Phase 4 central_sync_pool).
- httpx timeout: `httpx.Timeout(connect=2s, read=5s)` cho fetch_initial blocking; refresh task timeout `connect=5s, read=10s` (relax cho background).
- Subscriber failure handling: pub/sub disconnect → log warning + retry connect mỗi 5s (KHÔNG fail-loud — TTL natural fallback). Pattern song song `documents_service.py` publish_invalidate fail-open.
- Cache write strategy: write-through (set cache sau khi fetch OK) + no negative cache (fetch fail → KHÔNG cache 401/500).
- Settings env wiring docker-compose: `SETTINGS_PROXY_SECRET` shared 4 service (central + 3 hub con) + override.yml.template FACTOR-04 placeholder.
- Error envelope shape khi fail-loud (TTL expire + central down): 503 `{success:false, error:{code:"SETTINGS_UNAVAILABLE", message:"..."}}` qua M2 ErrorHandlerMiddleware wrap.

### Folded Todos

No pending todos matched Phase 6 scope (review backlog 999.x parking lot returned empty).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project Spec
- `Hub_All/.planning/PROJECT.md` — Project vision + v3.0 milestone scope + R-V3-6 (settings sync race) LOW severity.
- `Hub_All/.planning/REQUIREMENTS.md` § "SETTINGS — System Settings Sync (4 REQ — GA-V3-B chốt ở `/gsd-discuss-phase 6`)" — SETTINGS-01..04 spec chi tiết HTTP pull + pub/sub invalidate + api_keys proxy + hub_registry read-only.
- `Hub_All/.planning/ROADMAP.md` § "Phase 6 — System Settings Sync (GA-V3-B)" — Phase 6 goal + 4 success criteria + 3 gray area description.
- `Hub_All/.planning/STATE.md` — Current state (Phase 1+2+3+4+5 DONE — 28/~32 plans complete).
- `Hub_All/CLAUDE.md` § 6 v3.0 progress + Phase 3 SSO pattern + Phase 4 Cross-hub Data Sync pattern + Phase 5 Reverse Proxy pattern.

### Prior Phase Context
- `Hub_All/.planning/phases/02-hub-con-codebase-factor/02-CONTEXT.md` — D-V3-Phase2-A..E (create_app factory + central-only mount + 12 hub-scoped endpoint matrix).
- `Hub_All/.planning/phases/02-hub-con-codebase-factor/02-05-PLAN.md` — FACTOR-04 dynamic hub registration (Phase 6 settings_proxy_secret env wire override.yml.template).
- `Hub_All/.planning/phases/03-auth-sso-hub-ids-jwt/03-CONTEXT.md` — D-V3-Phase3-A..H (JWKS endpoint + cache + Settings.central_url + httpx pattern).
- `Hub_All/.planning/phases/03-auth-sso-hub-ids-jwt/03-02-PLAN.md` — `JWKSCache` lifespan blocking fetch + background refresh task + `JWKS_SKIP_FETCH=1` escape hatch (Phase 6 reuse pattern cho RagConfigClient + HubRegistryClient).
- `Hub_All/.planning/phases/04-cross-hub-data-sync/04-CONTEXT.md` — D-V3-Phase4-A..D (outbox + worker + 6 Prometheus metric + asyncpg pool + Settings 7 field).
- `Hub_All/.planning/phases/04-cross-hub-data-sync/04-03-PLAN.md` — `api/app/sync/` module 4 file pattern (Phase 6 reuse cho `api/app/settings_sync/` module).
- `Hub_All/.planning/phases/04-cross-hub-data-sync/04-04-PLAN.md` — Lifespan integration central_sync_pool + asyncio task spawn + shutdown graceful (Phase 6 reuse cho subscriber_task).
- `Hub_All/.planning/phases/05-reverse-proxy-frontend-subpath/05-CONTEXT.md` — D-V3-Phase5-A..D (Caddy subpath routing — Phase 6 hub con HTTP call central qua `http://python-api-central:8080` internal network, KHÔNG qua Caddy).

### M2 v2.0 Carry Forward (Settings + API key baseline)
- `Hub_All/api/app/services/rag_config_service.py` — M2 rag_config CRUD + AES-GCM at-rest + hot-swap runtime. Phase 6 central PUT extend publish pub/sub.
- `Hub_All/api/app/routers/rag_config.py` — M2 rag_config router (GET/PUT/test/collections). Phase 6 hub con KHÔNG mount (FACTOR-02 strip Phase 2).
- `Hub_All/api/app/services/api_key_service.py` — M2 `ApiKeyService.verify_key` (verify plaintext qua AES-GCM decrypt + key_prefix match). Phase 6 central `POST /api/api-keys/verify` proxy wrap method này.
- `Hub_All/api/app/routers/api_keys.py` — M2 api_keys router (CRUD admin-only). Phase 6 thêm POST /verify internal-only.
- `Hub_All/api/app/auth/api_key.py` — M2 `require_api_key` dependency (X-API-Key header verify qua ApiKeyService.verify_key local). Phase 6 hub con REFACTOR: thay local verify bằng ApiKeyVerifyClient HTTP call central + cache Redis TTL 60s.
- `Hub_All/api/app/routers/hubs.py` — M2 hubs_router CRUD (HUB-01). Phase 6 hub con KHÔNG mount (FACTOR-02 strip Phase 2); hub con dùng `GET /api/hubs` HTTP pull central.
- `Hub_All/api/app/services/search_cache.py` — M2 Redis pub/sub pattern `psubscribe("hub:*:invalidate")` (SEARCH-04). Phase 6 reuse pattern cho `psubscribe("settings:invalidate")` — subscriber loop + best-effort fail-open.
- `Hub_All/api/app/config.py` — M2 + Phase 1..5 Settings fields (hub_name, hub_id, central_url, central_jwks_url, central_sync_dsn, sync_*). Phase 6 thêm 5 field: `settings_proxy_secret`, `settings_cache_ttl_rag_config=60`, `settings_cache_ttl_hub_registry=300`, `settings_cache_ttl_apikey=60`, `settings_subscriber_reconnect_seconds=5`.

### Existing Redis Pub/Sub Pattern
- `Hub_All/api/app/services/documents_service.py:139-140` — `publish_invalidate` best-effort fail-open pattern carry forward.
- `Hub_All/api/app/services/search_cache.py:25-80` — `INVALIDATE_CHANNEL_PATTERN = "hub:*:invalidate"` + `tag_cache_key` + `invalidate_hub` + subscriber loop pattern.
- `Hub_All/api/app/main.py:108` — `redis.asyncio.from_url(REDIS_URL)` lifespan init + PING verify connection.

### v3.0 Seed
- `Hub_All/.planning/seeds/v3.0-multi-hub-split.md` — GA-V3-B (System settings sync gray area) + R-V3-6 (settings sync race LOW severity).

### External Reference
- Redis Pub/Sub docs — `PSUBSCRIBE` pattern matching, message delivery best-effort (KHÔNG durable — TTL fallback bắt buộc).
- HTTPX async client — `httpx.AsyncClient` connection pool + Timeout config.
- hmac.compare_digest — constant-time string compare cho shared secret.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets (M2 v2.0 + Phase 1..5 ship — Phase 6 carry forward)

- `Hub_All/api/app/services/rag_config_service.py` — `RagConfigService.get_config()` + `update_config()` + `load_persisted_into_runtime()`. Phase 6 central `update_config()` thêm publish pub/sub sau commit.
- `Hub_All/api/app/services/api_key_service.py` — `ApiKeyService.verify_key()` private logic (decrypt + match). Phase 6 central wrap qua `POST /api/api-keys/verify` endpoint mới.
- `Hub_All/api/app/services/hub_service.py` — `HubService.list()` (HUB-01 list hubs). Phase 6 hub con `HubRegistryClient.fetch_all()` HTTP pull endpoint hiện hữu, KHÔNG đụng service logic.
- `Hub_All/api/app/auth/api_key.py::require_api_key` — Phase 6 REFACTOR: detect `settings.hub_name != "central"` → dùng `ApiKeyVerifyClient.verify(x_api_key)` thay vì `ApiKeyService(db).verify_key()`.
- `Hub_All/api/app/services/search_cache.py` — pub/sub subscriber loop pattern. Phase 6 mới `api/app/settings_sync/subscriber.py` reuse pattern.
- `Hub_All/api/app/main.py::lifespan` — Phase 3+4 đã có pattern `if settings.hub_name != "central":` block + asyncio task spawn + shutdown graceful. Phase 6 extend thêm 1 block cho settings_sync.
- `Hub_All/api/app/observability/metrics.py` — Prometheus collector module-level. Phase 6 thêm 6 metric mới (pattern Phase 4 `sync_*` metric).

### Established Patterns

- **Lifespan startup fail-loud pattern (Phase 3 Plan 03-02):** `await rag_config_client.fetch_initial(timeout=5s)` → exception → process exit code 1. Background refresh task fail-quiet log warning. Phase 6 reuse cho cả 2 client (rag_config + hub_registry).
- **In-process cache + TTL pattern (Phase 3 JWKSCache):** asyncio task chạy mỗi N giây fetch refresh, KHÔNG exception trên fail. Phase 6 RagConfigClient + HubRegistryClient adopt + thêm Redis cache layer (vì cross-process — multiple hub con worker process share cache).
- **Redis pub/sub subscriber pattern (search_cache.py):** `redis.pubsub().psubscribe()` + async iterator + best-effort fail-open + log warning. Phase 6 `settings_subscriber_loop` adopt + reconnect logic 5s retry.
- **httpx async client singleton (Phase 3 JWKS fetch):** `httpx.AsyncClient(timeout=...)` reuse cho 3 client (rag_config + hub_registry + apikey_verify) qua shared base class HOẶC module-level singleton.
- **Best-effort fail-open Redis publish (documents_service.py + search_cache.py):** try/except + log warning + return None — KHÔNG raise nếu Redis down. Phase 6 central `update_config()` adopt cho publish_invalidate.
- **Prometheus collector module-level (Phase 4 metrics.py):** `Counter/Histogram/Gauge` ở module-level + label `hub_name`. Phase 6 add 6 collector mới `settings_*` + `apikey_verify_total`.

### Integration Points

- **`api/app/main.py::create_app()::lifespan`** — Phase 6 thêm block `if settings.hub_name != "central":`:
  1. Init `settings_sync_redis_pool` (share `app.state.redis` từ M2 baseline OK).
  2. `await rag_config_client.fetch_initial()` blocking 5s.
  3. `await hub_registry_client.fetch_initial()` blocking 5s.
  4. Spawn `settings_subscriber_task = asyncio.create_task(settings_subscriber_loop(app))`.
  5. Shutdown: cancel task + wait 10s + log graceful.
- **`api/app/auth/api_key.py::require_api_key`** — Phase 6 REFACTOR: branch verify path:
  ```python
  if settings.hub_name == "central":
      principal = await ApiKeyService(db=db).verify_key(x_api_key)  # M2 local
  else:
      principal = await api_key_verify_client.verify(x_api_key)  # Phase 6 proxy
  ```
- **`api/app/routers/rag_config.py::update_rag_config`** — Phase 6 extend central: sau `service.update_config()` thành công → `await app.state.redis.publish("settings:invalidate", json.dumps({"config_key":"rag_config","hub":"*","timestamp":int(time.time())}))` best-effort.
- **`api/app/routers/api_keys.py`** — Phase 6 thêm endpoint MỚI `POST /api/api-keys/verify` ở central conditional mount (FACTOR-02). Dependency `require_internal_auth`.
- **`api/app/routers/__init__.py`** — Phase 6 KHÔNG đụng (api_keys_router central-only đã đúng).
- **`api/app/main.py::create_app()`** — Phase 6 KHÔNG add router mới (api_keys POST /verify mount qua hiện hữu `api_keys_router`).
- **`docker-compose.yml`** — Phase 6 thêm env `SETTINGS_PROXY_SECRET=${SETTINGS_PROXY_SECRET:?error}` cho cả 4 service (central + 3 hub con) — fail-loud nếu thiếu (T-06-04-01 mitigation). `.env.example` document gen lệnh `openssl rand -hex 32`.
- **`docker-compose.override.yml.template`** — Phase 6 thêm `SETTINGS_PROXY_SECRET` env placeholder cho hub con dynamic FACTOR-04.
- **`api/app/config.py::Settings`** — Phase 6 thêm 5 field + 1 validator (`settings_proxy_secret` min 32 char).

### Creative Options Enabled

- Phase 7 MIGRATE-04 MCP service settings sync — re-point central + reuse RagConfigClient pattern (Phase 6 ship pattern proven).
- v4.0 hub_registry table thay env — đổi `HubRegistryClient` data source từ `GET /api/hubs` sang DB table read; client interface giữ nguyên (decoupling tốt).
- v4.0 settings audit log — `audit_logs` table M2 carry forward, log mỗi pub/sub event + cache flush.

</code_context>

<specifics>
## Specific Ideas

- **Pub/sub payload validation pattern:** `settings_subscriber_loop` receive message → `json.loads()` → Pydantic `InvalidateMessage(BaseModel)` schema validate (`config_key: Literal["rag_config","hub_registry","apikey"]`, `hub: str`, `timestamp: int`). Invalid → log warning skip (KHÔNG crash subscriber). Pattern T-06-03-03 STRIDE Tampering mitigation.

- **Cache key consistency hash (apikey):** Hub con receive `X-API-Key: mdk_abc...` → compute `sha256(key)[:16]` → cache key `apikey:verify:{hash_prefix}`. KHÔNG plaintext key trong Redis key/value. T-06-04-02 Information Disclosure mitigation.

- **Fail-loud timing test pattern:** Integration test rotate central rag_config + simulate Redis down → assert hub con dùng cached value cho tới TTL expire (60s) → assert 503 SETTINGS_UNAVAILABLE sau TTL. Mock asyncio sleep với freezegun.

- **Pub/sub propagate test pattern:** Spawn 2 process (central + yte) via TestClient + ASGI lifespan + share Redis → POST `/api/rag-config` ở central → assert hub con cache flush trong < 1s thực tế (subscribe message receive). Reference pattern: M2 search_cache_subscriber test (đã có ở M2 test suite).

- **Backward incompat warning operator:** Phase 6 deploy → hub con M2 (chưa có settings_sync module) phải re-deploy mới load. Operator phải set `SETTINGS_PROXY_SECRET` env trước deploy → docker-compose down + up cả 4 service. Cache miss đầu tiên = HTTP call central blocking (acceptable boot delay 100-300ms). README.md Phase 6 deploy 5 step + rollback procedure.

- **Smoke test runtime defer pattern:** Pattern Plan 03-05 + 04-07 + 05-06 carry forward — closeout plan auto-fallback `skip smoke` per v3.0-b precedent (--auto chain mode active). Full E2E defer Phase 7 MIGRATE-05.

</specifics>

<deferred>
## Deferred Ideas

### Defer Phase 7 MIGRATE-04
- MCP service settings sync — re-point central + reuse RagConfigClient pattern.
- MCP token verify proxy (nếu cần) — pattern song song apikey_verify.

### Defer v4.0 (Production Hardening)
- `hub_registry` table thay env `Settings.hub_name` — Phase 6 vẫn dùng env-based; long-term central DB-driven.
- Adaptive TTL — dựa trên change frequency analytics.
- HA Redis cluster (R-V3-6 LOW) — single Redis đủ cho v3.0-a/b.
- Settings audit log granular — log mỗi pub/sub event + cache flush.
- mTLS thay shared secret cho internal proxy auth.
- IP allowlist defense-in-depth.

### Deferred Cross-cutting
- Cache warm-up cron — pre-fetch trước TTL expire để tránh user-facing latency. Phase 6 dùng on-demand fetch (acceptable cold start).
- Settings versioning + rollback API — central admin UI revert config.

### Reviewed Todos (not folded)
No pending todos reviewed in cross_reference_todos.

</deferred>

---

*Phase: 06-system-settings-sync*
*Context gathered: 2026-05-23 via `--auto --chain` mode (planner seed defaults)*
*Auto-chain active → next: `/gsd-plan-phase 6 --auto`*
