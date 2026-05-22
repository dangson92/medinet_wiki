---
phase: 2
phase_name: Hub-con Codebase Factor
slug: hub-con-codebase-factor
milestone: v3.0
gathered: 2026-05-22
source: planner-seed-defaults
status: Ready for planning
---

# Phase 2: Hub-con Codebase Factor — Context

**Gathered:** 2026-05-22
**Status:** Ready for planning
**Source:** Planner seed defaults (Auto Mode `--chain`) — 3 gray area chốt theo recommended option ở ROADMAP / REQUIREMENTS, KHÔNG mở `/gsd-discuss-phase 2` interactive.

> Nguồn quyết định: pattern Phase 1 (đã chốt seed default 3 gray area), khớp với pattern hiện hữu `api/app/main.py::create_app()` + `Settings.hub_name` Literal đã có sẵn từ Phase 1 TOPO-04, REQUIREMENTS FACTOR-01..03 đặc tả chi tiết.

---

<domain>
## Phase Boundary

**WHAT phase 2 ships:**

1. App factory `create_app()` đọc `settings.hub_name` (đã có từ Phase 1, Literal `central|yte|duoc|hcns`) — KHÔNG đổi signature (giữ no-arg, đọc env), nhưng RE-WIRE để conditional include/exclude routers + cocoindex flow name + APP_NAMESPACE dựa trên `hub_name`.
2. Strip 8 central-only router khi `hub_name != "central"` (rag_config / api_keys / hubs / users / audit_logs / system_settings / sync / mcp_oauth + mcp_oauth_internal — tổng 9 router; `/api/hubs` GET có thể giữ read-only ở hub con qua SETTINGS-04 nhưng defer Phase 6).
3. Hub con expose 10 endpoint hub-scoped (theo FACTOR-03 wildcard mapping bên dưới).
4. Docker compose mở rộng từ 3 service (postgres + redis + python-api) sang 1 postgres + 1 redis + 4 service FastAPI (`python-api-central` + `python-api-yte` + `python-api-duoc` + `python-api-hcns`) + giữ nguyên `mcp_service` + `caddy`. 4 service dedicated, KHÔNG dùng `deploy.replicas` (replicas KHÔNG cho phép env per-replica khác nhau).
5. Smoke test integration: `HUB_NAME=yte` deploy spawn process song song với central, mỗi process kết nối đúng DB (E-V3-3 đã enforce Phase 1 `_enforce_hub_dsn_match`), endpoint hub-scoped trả 200, endpoint central-only trả 404 ở hub con (KHÔNG 403 — endpoint không exist).

**WHAT phase 2 KHÔNG ship:**

- Caddy subpath routing `wiki.domain.com/<hub>/api/*` — defer Phase 5 PROXY-01.
- JWT SSO + JWKS endpoint — defer Phase 3 SSO-01..04. Phase 2 vẫn dùng JWT M2 hiện tại (per-process keypair). E4 isolation đã enforce ở Phase 1 (DB-level) — đủ tạm thời cho v3.0-a demo.
- Cross-hub data sync chunks+vector — defer Phase 4 SYNC-01..05.
- Frontend prefix detect / branding — defer Phase 5 PROXY-02/04.
- Settings sync HTTP pull + pub/sub invalidate — defer Phase 6 SETTINGS-01..04.

</domain>

<decisions>
## Implementation Decisions

### D-V3-Phase2-A · App Factory Pattern (GA-2-A LOCKED)

**Chốt:** 1 `create_app()` factory function (KHÔNG đổi signature từ M2) — DRY pattern.

**Lý do:**
- `Settings.hub_name` đã là singleton qua `lru_cache get_settings()` (Phase 1) — factory đọc settings không cần param.
- Hai file `main_central.py` + `main_hub.py` duplicate logic middleware + exception handler + lifespan (290+ LOC trùng).
- FastAPI canonical pattern: factory + lifespan. Test isolation: tạo nhiều app instance với env override (`monkeypatch.setenv("HUB_NAME", "yte")` → `create_app()`).
- M2 đã ship `create_app()` no-arg pattern — KHÔNG break uvicorn `app.main:app` entrypoint.

**Reject alternatives:**
- 2 file `main_central.py` + `main_hub.py`: duplicate 290+ LOC; mỗi sửa middleware/handler phải đồng bộ 2 nơi.
- `create_app(hub_name: str | None = None)` param explicit: thêm param nhưng `get_settings()` đã singleton, dùng param chỉ vì test → factory phức tạp hơn cần thiết. Test có thể `monkeypatch.setenv` rồi gọi `get_settings.cache_clear()`.

### D-V3-Phase2-B · Mount Router Conditional (GA-2-B LOCKED)

**Chốt:** Inline `if settings.hub_name == "central"` conditional trong `create_app()`, KHÔNG feature flag config-driven.

**Tách 2 nhóm router:**

```python
# Tier 1 — Universal (mount BOTH central + hub con, 7 router):
auth_router, documents_router, profile_router, search_router,
ask_router, usage_router, ai_chat_router

# Tier 2 — Central-only (mount CHỈ khi hub_name == "central", 8 router):
hubs_router, users_router, api_keys_router, audit_logs_router,
rag_config_router, system_settings_router, sync_router,
mcp_oauth_router, mcp_oauth_internal_router
```

**Pseudocode:**

```python
# Universal — mount ở mọi process
app.include_router(auth_router)
app.include_router(documents_router)
app.include_router(profile_router)
app.include_router(search_router)
app.include_router(ask_router)
app.include_router(usage_router)
app.include_router(ai_chat_router)

# Central-only — strip khi hub con
if settings.hub_name == "central":
    app.include_router(hubs_router)
    app.include_router(users_router)
    app.include_router(api_keys_router)
    app.include_router(audit_logs_router)
    app.include_router(rag_config_router)
    app.include_router(system_settings_router)
    app.include_router(sync_router)
    app.include_router(mcp_oauth_router)
    app.include_router(mcp_oauth_internal_router)
```

**Lý do:**
- Feature flag config-driven (`router_central_only=True/False`) thêm 1 layer indirection mà không có usage case (chỉ 2 hub class: central vs hub con).
- Inline conditional đọc tuyến tính, hiển nhiên cho reviewer; grep `if settings.hub_name == "central"` ra ngay.
- Test integration: `HUB_NAME=yte` boot app → `client.get("/api/rag-config")` → 404 (router không mount → FastAPI built-in 404 not envelope). Wrap với handler 404 → envelope `{success:false, data:null, error:{code:"NOT_FOUND",message:"..."}}` (đã có ở `ErrorHandlerMiddleware`).

**Reject alternatives:**
- Config-driven feature flag: over-engineer cho 2 class.
- Mount tất cả + 403 forbidden ở dependency: leak endpoint exist → FACTOR-02 yêu cầu 404 (endpoint không exist mới đúng "strip" semantic).

### D-V3-Phase2-C · Docker Compose Service Definition (GA-2-C LOCKED)

**Chốt:** 4 service dedicated FastAPI (`python-api-central` + `python-api-yte` + `python-api-duoc` + `python-api-hcns`) + YAML anchor `&api-template` dedupe shared config.

**Layout dự kiến:**

```yaml
x-api-template: &api-template
  build:
    context: ./api
    dockerfile: Dockerfile
  env_file:
    - ./api/.env
  environment:
    REDIS_URL: redis://redis:6379/0
    APP_NAMESPACE: medinet_prod
    COCOINDEX_DB_SCHEMA: cocoindex
    JWT_PRIVATE_KEY_PATH: /keys/private.pem
    JWT_PUBLIC_KEY_PATH: /keys/public.pem
    FILE_STORE_DIR: /file_store
    APP_ENV: ${APP_ENV:-dev}
    LOG_LEVEL: ${LOG_LEVEL:-info}
    COCOINDEX_DB: /app/.cocoindex/state.lmdb
    COCOINDEX_LMDB_PATH: /app/.cocoindex/state.lmdb
  volumes:
    - ./api/keys:/keys:ro
    - ./file_store:/file_store
  depends_on:
    postgres:
      condition: service_healthy
    redis:
      condition: service_healthy
  networks: [medinet_net]

services:
  python-api-central:
    <<: *api-template
    container_name: medinet-api-central
    environment:
      HUB_NAME: central
      DATABASE_URL: postgresql+asyncpg://medinet:${POSTGRES_PASSWORD:-medinet_dev_pwd}@postgres:5432/medinet_central
      COCOINDEX_DATABASE_URL: postgresql://medinet:${POSTGRES_PASSWORD:-medinet_dev_pwd}@postgres:5432/medinet_cocoindex
    volumes:
      - medinet_cocoindex_central:/app/.cocoindex
    ports:
      - "8180:8080"

  python-api-yte:
    <<: *api-template
    container_name: medinet-api-yte
    environment:
      HUB_NAME: yte
      DATABASE_URL: postgresql+asyncpg://medinet:${POSTGRES_PASSWORD:-medinet_dev_pwd}@postgres:5432/medinet_hub_yte
      COCOINDEX_DATABASE_URL: postgresql://medinet:${POSTGRES_PASSWORD:-medinet_dev_pwd}@postgres:5432/medinet_cocoindex
    volumes:
      - medinet_cocoindex_yte:/app/.cocoindex
    ports:
      - "8181:8080"

  python-api-duoc:
    <<: *api-template
    container_name: medinet-api-duoc
    environment:
      HUB_NAME: duoc
      DATABASE_URL: postgresql+asyncpg://medinet:${POSTGRES_PASSWORD:-medinet_dev_pwd}@postgres:5432/medinet_hub_duoc
      COCOINDEX_DATABASE_URL: postgresql://medinet:${POSTGRES_PASSWORD:-medinet_dev_pwd}@postgres:5432/medinet_cocoindex
    volumes:
      - medinet_cocoindex_duoc:/app/.cocoindex
    ports:
      - "8182:8080"

  python-api-hcns:
    <<: *api-template
    container_name: medinet-api-hcns
    environment:
      HUB_NAME: hcns
      DATABASE_URL: postgresql+asyncpg://medinet:${POSTGRES_PASSWORD:-medinet_dev_pwd}@postgres:5432/medinet_hub_hcns
      COCOINDEX_DATABASE_URL: postgresql://medinet:${POSTGRES_PASSWORD:-medinet_dev_pwd}@postgres:5432/medinet_cocoindex
    volumes:
      - medinet_cocoindex_hcns:/app/.cocoindex
    ports:
      - "8183:8080"
```

**Port mapping:** central 8180 (giữ M2 backward-compat — frontend hardcode), yte 8181, duoc 8182, hcns 8183. Phase 5 Caddy sẽ strip prefix `/<hub>` + route subpath qua port internal — port host chỉ dùng cho direct dev/test trước khi Caddy lên.

**Cocoindex LMDB volume per-hub:** Mỗi process cocoindex 1.0.3 environment singleton — KHÔNG share state across HUB_NAME. Mỗi service mount volume riêng (`medinet_cocoindex_yte`, ...).

**MCP service KHÔNG mount per-hub:** mcp_service giữ nguyên (gọi central qua HTTP). Phase 7 MIGRATE-04 sẽ re-point central URL chính xác.

**Lý do reject `deploy.replicas` + env override:**
- `deploy.replicas: 4` chỉ duplicate cùng env → tất cả replica có `HUB_NAME=central` (hoặc bất cứ giá trị nào set).
- Docker compose KHÔNG support `replicas` với env per-replica khác nhau (chỉ swarm mode + service template phức tạp).
- 4 service dedicated dễ debug log (`docker logs medinet-api-yte`), restart độc lập, mount volume cocoindex per-hub rạch ròi.

### D-V3-Phase2-D · 10 Endpoint Hub-Scoped Whitelist (FACTOR-03)

**Chốt:** Theo REQUIREMENTS.md FACTOR-03 wildcard mapping — mỗi router universal expose endpoint cụ thể sau đây ở hub con:

| # | Method | Path | Router | Note |
|---|--------|------|--------|------|
| 1 | POST | `/api/auth/login` | auth | SSO Phase 3 sẽ redirect central; Phase 2 vẫn login local |
| 2 | POST | `/api/auth/refresh` | auth | Phase 3 sẽ chuyển central-only; Phase 2 local |
| 3 | POST | `/api/auth/logout` | auth | Local revoke (Redis blacklist Phase 3 chung sau) |
| 4 | GET | `/api/auth/me` | auth | Current user |
| 5 | GET | `/api/profile` | profile | User profile |
| 6 | PATCH | `/api/profile` | profile | Update profile |
| 7 | POST | `/api/documents` | documents | Upload local hub |
| 8 | GET | `/api/documents` | documents | List local hub |
| 9 | DELETE | `/api/documents/{id}` | documents | Delete local hub (HubIsolationError enforce) |
| 10 | POST | `/api/search` | search | Local hub search (KHÔNG cross-hub) |
| 11 | POST | `/api/ask` | ask | Local hub Q&A |
| 12 | GET | `/api/usage` | usage | Own token usage |

> REQUIREMENTS.md FACTOR-03 mô tả là "10 endpoint hub-scoped" với wildcard `POST/GET /api/auth/*` + `GET/PATCH /api/profile` + `POST/GET/DELETE /api/documents/*` + 3 endpoint single — đếm collective. Implementation thực tế là 12 endpoint cụ thể (4 auth + 2 profile + 3 documents + search + ask + usage). Smoke test cover hết 12.

**KHÔNG expose ở hub con (Phase 2 strip):**
- `POST /api/search/cross-hub` — cross-hub search là central-only (Phase 4 SYNC-03). Hub con search local only.
- `POST /api/search/answer` (alias ask) — cross-hub flavor → strip.
- `/api/ai/chat` — proxy LLM cho frontend GeminiAssistant; mount ở central; defer Phase 5 quyết per-hub có cần không.

### D-V3-Phase2-E · 404 Shape Khi Strip Router

**Chốt:** Khi hub con nhận request central-only endpoint → FastAPI built-in 404 → wrap qua `ErrorHandlerMiddleware` đã có để render envelope `{success:false, data:null, error:{code:"NOT_FOUND", message:"..."}, meta:null}`.

**Verify:** ErrorHandlerMiddleware đã catch 404 ở M2 (test envelope shape `tests/integration/test_envelope.py`). Phase 2 KHÔNG cần thêm exception handler mới — chỉ đảm bảo 404 (router không mount) NGUYÊN dạng envelope.

**KHÔNG dùng 403 Forbidden:** 403 leak endpoint exists. 404 implies "endpoint không exist" — FACTOR-02 yêu cầu strip semantic chính xác.

### D-V3-Phase2-F · APP_NAMESPACE + Cocoindex Flow Name Per-Hub

**Chốt:** Cocoindex 1.0.3 Environment đã được Phase 1 Plan 01-04 wire `medinet_<hub>_ingest` + `APP_NAMESPACE=medinet_<hub>_prod` (TOPO-03 DONE). Phase 2 verify integration: `HUB_NAME=yte` boot → cocoindex log `Flow medinet_yte_ingest registered` + APP_NAMESPACE `medinet_yte_prod`.

Phase 2 KHÔNG đổi `app/rag/setup.py` — chỉ smoke verify boot mỗi hub PASS.

### D-V3-Phase2-G · Lifespan Universal — KHÔNG Conditional

**Chốt:** Giữ nguyên lifespan M2 — tất cả step (asyncpg pool, redis, rag_config load, cocoindex setup, JWT manager, watchdog, audit, search cache subscriber) chạy ở MỌI process bất kể `hub_name`.

**Lý do:**
- Hub con vẫn cần: db pool (local DB), redis (blacklist Phase 3 + search cache), cocoindex (ingest local), jwt (verify JWKS Phase 3, Phase 2 vẫn dùng key local), watchdog (process local document stuck).
- KHÔNG bỏ rag_config load ở hub con — Phase 2 vẫn load từ DB hub con local (chưa pull từ central — defer SETTINGS-01 Phase 6). Tạm dùng cùng `rag_config` row được seed identical ở mọi DB hub con qua Alembic data migration (đã có Phase 1).

**Edge case lifespan có thể skip ở hub con (defer):**
- `mcp_oauth_internal_router` có background task — đã mount ở central-only. KHÔNG ảnh hưởng lifespan.
- `search_cache_task` (Phase 6 D-12 subscriber Redis Pub/Sub `hub:*:invalidate`) — hub con vẫn subscribe nhưng channel theo `hub_name` của mình. Defer tinh chỉnh Phase 6.

### D-V3-Phase2-H · Test Integration — 4 Service Compose Boot

**Chốt:** Add integration test `tests/integration/test_factor_hub_scoped.py` với scenario:

1. **boot 4 process song song** qua docker compose `up python-api-central python-api-yte` (2 process là đủ smoke — duoc/hcns analog).
2. **central:** `GET http://localhost:8180/api/rag-config` → 200 envelope.
3. **hub yte:** `GET http://localhost:8181/api/rag-config` → 404 envelope (router strip).
4. **hub yte:** `GET http://localhost:8181/api/health` → 200 (universal).
5. **hub yte:** `GET http://localhost:8181/api/auth/me` (no token) → 401 envelope (router mount, dependency reject).
6. **hub yte:** `POST http://localhost:8181/api/documents` (upload local DOCX) → 200 / 202 (router mount, FACTOR-03 enforce).
7. **hub yte:** `GET http://localhost:8181/healthz` → 200 (liveness universal).

**Markers:** `@pytest.mark.integration` + `@pytest.mark.docker_compose` (skip ở CI non-docker).

### D-V3-Phase2-I · CLAUDE.md Section 2 Update

**Chốt:** Phase 2 PLAN cuối wave update `Hub_All/CLAUDE.md` section 2 (Milestone hiện tại) ghi nhận Phase 2 DONE — pattern Phase 1 đã làm. CLAUDE.md là project context Claude đọc ở session sau, phải reflect v3.0 progress kịp thời.

### Claude's Discretion

Phần dưới KHÔNG specify trong ROADMAP/REQUIREMENTS, planner toàn quyền chốt:

- **Số plan break-down:** ~3-4 plan cho phase 2 (4 plan đề xuất bên dưới); planner có thể merge/split nếu lý do rõ.
- **Wave parallelization:** Plan 02-01 (factory refactor) BLOCKING — Plan 02-02 (router strip) + Plan 02-03 (docker compose) có thể parallel (file disjoint). Plan 02-04 (integration test + CLAUDE.md) Wave 3.
- **Test fixture refactor:** Nếu pytest fixture `app_with_auth` cần `HUB_NAME` param, planner thêm fixture `app_with_hub` parameterized.
- **OpenAPI/docs:** `/docs` Swagger ở hub con sẽ tự động ẩn central-only router. KHÔNG cần custom config.
- **Health/readiness:** giữ logic `/healthz` + `/readyz` M2; hub con `/readyz` vẫn cần cocoindex_ready=True.
- **mcp_service docker-compose:** KHÔNG đổi gì Phase 2 — phụ thuộc central qua `MCP_API_BASE_URL: http://python-api-central:8080` (rename từ `python-api` cũ → planner update line).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents (planner, executor) MUST read trước khi plan/execute.**

### Project source-of-truth
- `Hub_All/CLAUDE.md` — Project instructions, M2 stack (FastAPI / cocoindex / pgvector), v3.0 milestone overview, conventions, section 3 (Quy tắc làm việc) GSD workflow + ngôn ngữ Tiếng Việt.
- `Hub_All/.planning/ROADMAP.md` — Phase 2 row + gray area description + success criteria.
- `Hub_All/.planning/REQUIREMENTS.md` — FACTOR-01..03 chi tiết + Out of Scope + Traceability.
- `Hub_All/.planning/STATE.md` — Phase 1 results summary, Phase 2 next action.
- `Hub_All/.planning/CONVENTIONS.md` — Python coding standards, ruff/mypy/pytest layout, layered architecture (router → service → repository).

### v3.0 architectural decisions (LOCKED)
- `Hub_All/.planning/seeds/v3.0-multi-hub-split.md` — 4 LOCKED decision D-V3-01/02/03/04 (DB topology, dataflow, scoping, M2 closeout prerequisite).

### Existing Phase 1 outputs (Phase 2 build trên top)
- `Hub_All/.planning/phases/01-multi-db-topology/01-01-PLAN.md` — Postgres init-db.sh 4 DB.
- `Hub_All/.planning/phases/01-multi-db-topology/01-02-PLAN.md` — Settings.hub_name + DSN validator + resolve_database_url (**input chính cho Phase 2**).
- `Hub_All/.planning/phases/01-multi-db-topology/01-04-PLAN.md` — Cocoindex APP_NAMESPACE + flow name per-hub.
- `Hub_All/.planning/phases/01-multi-db-topology/01-05-PLAN.md` — hub-init.sh + integration test E-V3-3.
- `Hub_All/.planning/phases/01-multi-db-topology/01-VERIFICATION.md` — 4 SC PASS evidence.

### Code analog (Phase 2 sửa / extend)
- `Hub_All/api/app/main.py` — `create_app()` factory M2, mount tất cả router unconditional (line ~325-460). **Phase 2 sửa ở đây** — wrap central-only block với `if settings.hub_name == "central"`.
- `Hub_All/api/app/config.py` — `Settings.hub_name` Literal đã có (Phase 1). `_enforce_hub_dsn_match` đã enforce HUB_NAME ↔ DSN. **Phase 2 KHÔNG sửa** — chỉ consume.
- `Hub_All/api/app/routers/__init__.py` — Re-export router. Phase 2 KHÔNG đổi exports, chỉ đổi import order trong `main.py` để central-only mount conditionally.
- `Hub_All/api/app/middleware/error_handler.py` — Envelope renderer cho HTTPException + 404. **Phase 2 verify** 404 router-not-mount cũng được wrap.
- `Hub_All/docker-compose.yml` — M2 service `python-api`. **Phase 2 thay** bằng 4 service template `&api-template`.

### Carry forward (M2 / Phase 1)
- `Hub_All/api/scripts/init-db.sh` — 4 DB init (Phase 1) — KHÔNG đổi Phase 2.
- `Hub_All/api/scripts/hub-init.sh` — Dynamic add hub (Phase 1 Plan 01-05) — Phase 2 KHÔNG sửa.
- `Hub_All/api/app/db/session.py` — `init_engine`, `get_engine(hub_name)`, `resolve_database_url` (Phase 1) — Phase 2 consume.

### v2.0 archive (đề phòng cần check shape Go cũ)
- `Hub_All/.planning/milestones/v2.0-full-rag-rewrite/REQUIREMENTS.md` — 38 REQ-ID v2.0 đầy đủ (COMPAT-01 envelope shape).

</canonical_refs>

<specifics>
## Specific Ideas / Concrete Patterns

### Pattern: Conditional router mount block

```python
# api/app/main.py — bên trong create_app() (sau settings = get_settings())

# ----- Universal routers (mount ở mọi process: central + hub con) -----
app.include_router(auth_router)
app.include_router(documents_router)
app.include_router(profile_router)
app.include_router(search_router)  # local search; cross-hub branch ở Phase 4
app.include_router(ask_router)
app.include_router(usage_router)
app.include_router(ai_chat_router)

# ----- Central-only routers (strip ở hub con — FACTOR-02) -----
if settings.hub_name == "central":
    app.include_router(hubs_router)
    app.include_router(users_router)
    app.include_router(api_keys_router)
    app.include_router(audit_logs_router)
    app.include_router(rag_config_router)
    app.include_router(system_settings_router)
    app.include_router(sync_router)
    app.include_router(mcp_oauth_router)
    app.include_router(mcp_oauth_internal_router)
else:
    logger.info(
        "central_only_routers_skipped: hub_name=%s — 9 routers stripped "
        "(FACTOR-02 enforce)", settings.hub_name
    )
```

### Pattern: Pytest fixture for hub-mode app

```python
# tests/integration/conftest.py — thêm fixture parameterized hub_name

@pytest.fixture
def hub_app(monkeypatch, hub_name: str) -> FastAPI:
    """Boot app với HUB_NAME override + DSN per-hub.

    Test phải set:
    - HUB_NAME = "yte" | "duoc" | "hcns" | "central"
    - DATABASE_URL matching (testcontainers DSN per-hub)
    """
    monkeypatch.setenv("HUB_NAME", hub_name)
    # DATABASE_URL set ở caller (testcontainers fixture)
    get_settings.cache_clear()  # Force re-parse env
    from app.main import create_app
    return create_app()
```

### Pattern: Docker compose YAML anchor

Anchor `&api-template` ở top-level `x-api-template:` key. Service body dùng `<<: *api-template` để inherit, sau đó override `environment.HUB_NAME` + `DATABASE_URL` + `ports` + `container_name` + `volumes.cocoindex`.

### Pattern: Smoke test endpoint matrix

```python
# tests/integration/test_factor_hub_scoped.py — pseudocode

CENTRAL_ONLY = [
    "/api/rag-config", "/api/api-keys", "/api/hubs", "/api/users",
    "/api/audit-logs", "/api/system-settings", "/api/sync",
    "/api/mcp/my-oauth-client",
]
HUB_SCOPED = [
    "/api/auth/login", "/api/auth/refresh", "/api/auth/logout", "/api/auth/me",
    "/api/profile", "/api/documents",
    "/api/search", "/api/ask", "/api/usage",
]

@pytest.mark.parametrize("hub_name", ["yte", "duoc", "hcns"])
def test_hub_strips_central_routers(hub_name, hub_app_factory):
    app = hub_app_factory(hub_name)
    with TestClient(app) as client:
        for path in CENTRAL_ONLY:
            resp = client.get(path)
            assert resp.status_code == 404
            body = resp.json()
            assert body["success"] is False
            assert body["error"]["code"] in ("NOT_FOUND", "ERROR")
        for path in HUB_SCOPED:
            resp = client.get(path)
            # Không assert 200 (depends method); chỉ verify KHÔNG 404
            assert resp.status_code != 404
```

</specifics>

<deferred>
## Deferred Ideas

- **Dynamic hub list (không Literal):** Hiện `Settings.hub_name: Literal["central","yte","duoc","hcns"]`. Add hub mới phải sửa code. Defer Phase 7 MIGRATE hoặc v3.0-b: chuyển sang `str` + validate qua `hub_registry` table (SETTINGS-04 Phase 6).
- **Per-hub branding ở backend:** Logo URL, tiêu đề VN khác nhau ở config — defer Phase 5 PROXY-04 (frontend rewrite).
- **JWKS endpoint + cross-process JWT:** Phase 3 SSO-01..04.
- **Cross-hub search aggregation:** Phase 4 SYNC-03.
- **Caddy subpath routing:** Phase 5 PROXY-01.
- **Settings HTTP pull + pub/sub:** Phase 6 SETTINGS-01..04.
- **MCP fan-out per-hub:** KHÔNG fan-out (LOCKED D-V3-02). MCP gọi central aggregate. Phase 7 MIGRATE-04 re-confirm.
- **Hub con `/api/usage` show admin-level central usage:** Hiện hub con chỉ show own usage. Admin cross-hub usage report → defer Phase 4+ central-only endpoint.

</deferred>

<planning_hints>
## Planning Hints (cho gsd-planner)

### Đề xuất plan break-down (~4 plan)

| Plan | Wave | Trọng tâm | Files | REQ |
|------|------|-----------|-------|-----|
| 02-01 | 1 | Refactor `create_app()` — wrap central-only routers với `if settings.hub_name == "central"` + logger info strip + unit test boot 4 hub mode | `api/app/main.py`, `tests/unit/test_main_factory.py` (new) | FACTOR-01, FACTOR-02 |
| 02-02 | 2 | Docker compose 4 service `&api-template` anchor + cocoindex LMDB volume per-hub + port mapping 8180-8183 + `mcp_service.MCP_API_BASE_URL` re-point | `docker-compose.yml`, `Hub_All/README.md` section deploy update | FACTOR-01 |
| 02-03 | 2 | Integration test `test_factor_hub_scoped.py` — endpoint matrix 12 hub-scoped + 8 central-only + envelope shape verify; pytest fixture `hub_app_factory` parameterized HUB_NAME + DATABASE_URL | `tests/integration/test_factor_hub_scoped.py` (new), `tests/integration/conftest.py` | FACTOR-02, FACTOR-03 |
| 02-04 | 3 | CLAUDE.md section 2 update Phase 2 DONE; `.planning/STATE.md` move Phase 2 → DONE; verify 4 service compose smoke local (curl matrix) | `Hub_All/CLAUDE.md`, `.planning/STATE.md` | — (closeout) |

**Critical path:** 02-01 (BLOCKING — refactor factory) → 02-02 + 02-03 parallel Wave 2 → 02-04 Wave 3.

**Wave 1 (1 plan, blocking):** 02-01
**Wave 2 (2 plan, parallel — file disjoint):** 02-02, 02-03
**Wave 3 (1 plan, closeout):** 02-04

### Each plan MUST include:

- `<read_first>` — `api/app/main.py` + `api/app/config.py` (singleton `Settings.hub_name` từ Phase 1) + `docker-compose.yml` cho 02-02, plus relevant test files.
- `<acceptance_criteria>` — grep-verifiable, command-verifiable. Ví dụ:
  - `api/app/main.py contains 'if settings.hub_name == "central":'`
  - `docker compose config | grep -c '^  python-api-' = 4`
  - `pytest tests/integration/test_factor_hub_scoped.py -v` exits 0
  - `HUB_NAME=yte uvicorn app.main:app --port 8181 &` then `curl localhost:8181/api/rag-config` returns 404 with envelope shape.
- `<must_haves>` for goal-backward verification:
  - 4 service compose up song song KHÔNG conflict.
  - Central giữ nguyên 100% endpoint M2.
  - Hub con expose 12 endpoint (FACTOR-03 list), strip 8 central-only.
  - 404 ở hub con dùng envelope shape `{success:false, data:null, error:{code, message}, meta:null}`.
  - E-V3-3 DB isolation KHÔNG regress (Phase 1 enforce vẫn PASS).
- Threat model: scope hẹp Phase 2 — chủ yếu T-02-01 (information disclosure): central-only endpoint leak ở hub con. Mitigation đã chốt qua 404 KHÔNG mount router. Đầy đủ threat model trong PLAN.md `<threat_model>` block (ASVS L1 enforced).

</planning_hints>

---

*Phase: 02-hub-con-codebase-factor*
*Context gathered: 2026-05-22 via planner seed defaults (Auto Mode `--chain`)*
*Source decisions: 3 GA (App factory / Router conditional / Docker compose 4-service) + 6 D-V3-Phase2 chốt LOCKED + 1 endpoint matrix LOCKED.*
