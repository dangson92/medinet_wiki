---
phase: 3
phase_name: Auth SSO + hub_ids trong JWT
slug: auth-sso-hub-ids-jwt
milestone: v3.0
gathered: 2026-05-22
source: planner-seed-defaults (Auto Mode `--auto --chain`)
status: Ready for planning
---

# Phase 3: Auth SSO + hub_ids trong JWT — Context

**Gathered:** 2026-05-22
**Status:** Ready for planning
**Source:** Auto Mode `--auto --chain` — gray area GA-V3-A + 6 sub-decision chốt theo recommended seed defaults (REQUIREMENTS.md SSO-01..04 đã lock pattern). KHÔNG mở `/gsd-discuss-phase 3` interactive.

> Nguồn quyết định: REQUIREMENTS.md (SSO-01..04 spec chi tiết JWKS endpoint + Redis blacklist chung + hub_ids claim + E4 reinforced) + ROADMAP.md Phase 3 success criteria + carry-forward decisions từ M2 v2.0 (RS256 keypair PKCS#8 + pwdlib Argon2 + PyJWT + redis-py) + Phase 1 `_enforce_hub_dsn_match` + Phase 2 `create_app()` conditional mount.

---

<domain>
## Phase Boundary

**WHAT phase 3 ships:**

1. **Central expose `GET /.well-known/jwks.json`** — public key RS256 (PKCS#8) qua endpoint chuẩn RFC 7517 JWK Set. Endpoint public (KHÔNG auth) — Caddy/Nginx có thể cache CDN-level.
2. **Hub con cache JWKS local TTL 1h** — startup load 1 lần (fail-loud nếu central down KHI boot), refresh background mỗi 1h (R-V3-5 HA mitigation). KHÔNG fallback static keypair embedded — boot phải có central reachable.
3. **Redis blacklist `auth:blacklist:<jti>` chung** cross-process — central + hub con cùng kết nối 1 Redis instance (M2 baseline). Logout central → revoke JWT → hub con reject trong < 1s (TTL key = JWT exp; KHÔNG cần pub/sub).
4. **JWT claim `hub_ids: list[str]`** reflect user's hub assignments — issued bởi central ở login + refresh. Central + hub con verify access dùng claim này (intersection logic ở central cross-hub search, equality check ở hub con local).
5. **Hub con KHÔNG sinh refresh token** — login + refresh chỉ ở central qua `POST https://central/api/auth/login` + `POST https://central/api/auth/refresh`. Hub con CHỈ verify access token + reject expired.
6. **E4 reinforced** — hub con CHỈ truy cập data hub khớp `HUB_NAME` (Phase 1 `_enforce_hub_dsn_match` DSN + repository layer `WHERE hub_id = settings.hub_name`). Stale JWT chứa `hub_ids=["duoc"]` post tới `medinet_hub_yte` API → 403 (KHÔNG 404 hay data leak).

**WHAT phase 3 KHÔNG ship:**

- Caddy subpath routing `wiki.domain.com/<hub>/api/*` — defer Phase 5 PROXY-01.
- Per-hub login branding (logo/title/theme) — defer Phase 5 PROXY-04.
- Cross-hub data sync chunks+vector — defer Phase 4 SYNC-01..05.
- Frontend rewrite — D6 expire ở Phase 5 PROXY-02 (D-V3-06 LOCKED).
- DCR (Dynamic Client Registration) cho hub con — KHÔNG cần vì hub con KHÔNG là OAuth client; chỉ verify JWT do central issue (RS256 public key).
- Token rotation strategy (sliding refresh window) — re-use M2 v2.0 baseline (refresh token replace cũ ở central).

</domain>

<decisions>
## Implementation Decisions

### GA-V3-A · Auth SSO Design (LOCKED — recommended seed)

**D-V3-Phase3-A:** **JWKS endpoint** từ central serving public key RS256.

**Rationale:**
- HA dễ hơn shared keypair file mount (R-V3-5 mitigation): central rotation → hub con tự detect ở next TTL refresh, KHÔNG cần redeploy hub con.
- Standard pattern RFC 7517 — PyJWT + python-jose support natively.
- Tránh trust-on-deploy của shared keypair file mount (mỗi hub deploy phải copy keypair file → tăng surface area secret leak).
- Cookie domain `.medinet.vn` REJECT — phá subpath model Phase 5 (`wiki.medinet.vn/yte/api/*` cookie scope conflict), thiếu visibility cross-hub revoke.

**Reject alternatives:**
- Shared keypair file mount: simple boot nhưng rotation phức tạp (re-deploy mọi hub con + central cùng lúc).
- Cookie domain `.medinet.vn`: subpath model conflict + CSRF surface area lớn + KHÔNG quản lý revoke cross-hub.

### D-V3-Phase3-B · JWKS Cache Fallback (LOCKED — recommended seed)

**Chốt:** **Fail-loud nếu central down khi boot hub con** + **fail-quiet với cached value khi background refresh fail trong TTL window**.

**Implementation:**
- Boot hub con: `httpx.get(f"{settings.jwks_url}", timeout=5s)` blocking lifespan startup → exception → process exit code 1 (KHÔNG start uvicorn). docker-compose `depends_on: python-api-central: condition: service_started` (KHÔNG `service_healthy` để tránh circular wait nếu central cần hub con).
- Background refresh: asyncio task chạy mỗi 1h, fetch JWKS mới, KHÔNG exception trên fail (log warning + giữ cached value). Nếu cached value expire (> 24h KHÔNG refresh thành công) → log critical + return 503 cho mọi request verify JWT (fail-loud delayed).
- Persistence: KHÔNG cache disk (LMDB/file) — hub con luôn fetch fresh JWKS ở boot. Restart hub con = re-fetch.

**Rationale:**
- Boot fail-loud catch lỗi network/config sớm (operator deploy thấy ngay).
- Runtime fail-quiet tránh outage chain (central JWKS endpoint blip 5 phút KHÔNG nên kill hub con request).
- 24h hard limit prevent stale key dùng vĩnh viễn nếu rotation diễn ra mà hub con KHÔNG biết.

**Reject:**
- Static keypair embedded fallback: trade-off security (key leak qua filesystem) cho availability — R-V3-5 acceptable ở v3.0-a vì central + hub con đều same instance Postgres cluster.

### D-V3-Phase3-C · Refresh Token Rotation Contract (LOCKED — re-confirm SSO-02)

**Chốt:** **Central handle 100% refresh token logic** (issue + rotate + blacklist). Hub con CHỈ verify access token, KHÔNG sinh refresh.

**Implementation:**
- `POST https://central/api/auth/login` → response `{access_token, refresh_token}` (RS256 JWT cho access; refresh là opaque token UUID lưu Postgres `refresh_tokens` table M2 carry forward).
- `POST https://central/api/auth/refresh` → verify refresh_token DB + revoke cũ + issue new pair.
- `POST https://central/api/auth/logout` → blacklist current access JWT jti vào Redis (TTL = JWT exp - now) + revoke refresh_token DB.
- Hub con `/api/auth/*` router → STRIP (Phase 2 FACTOR-02 đã loại auth_router khỏi central-only? NO — auth_router universal mount). Phase 3 sẽ refactor: hub con `/api/auth/login` + `/api/auth/refresh` trả 405 hoặc 307 redirect tới central. `/api/auth/me` + `/api/auth/logout` vẫn handle local (me = verify JWT + return user; logout = blacklist Redis chung).

**Rationale:**
- 1 source-of-truth cho session lifecycle — KHÔNG race condition cross-hub refresh.
- DB `refresh_tokens` table M2 đã có (Phase 8 v2.0 ship) — re-use, KHÔNG cần migration.
- Frontend login form (Phase 5 PROXY-02 rewrite) sẽ POST trực tiếp central endpoint — bypass hub con cho auth flow.

### D-V3-Phase3-D · JWKS Cache Storage (LOCKED — recommended seed)

**Chốt:** **In-process LRU cache** (`functools.lru_cache(maxsize=2)` keyed on `kid`) + asyncio refresh task. KHÔNG Redis cache cho JWKS.

**Rationale:**
- JWKS payload nhỏ (< 2KB cho 1 RS256 key) — Redis overhead không đáng.
- In-process cache zero latency mọi JWT verify (Redis network call thêm 0.5-1ms × hot path verify).
- Cross-hub consistency KHÔNG cần (mỗi hub con cache độc lập, refresh đồng bộ qua TTL 1h).
- Restart hub con = re-fetch JWKS (boot dependency D-V3-Phase3-B).

**Reject:**
- Redis cache JWKS: thêm network hop, complexity không cần thiết cho payload nhỏ + cross-hub không share state.

### D-V3-Phase3-E · JWT Issuer + Audience Claims (LOCKED — recommended seed)

**Chốt:**
- `iss: "https://central/"` cố định (KHÔNG đổi per-hub).
- `aud: ["medinet-wiki"]` đơn giản (KHÔNG split per-hub `medinet-wiki-yte` etc.).
- Hub con verify `iss` strict (mismatch → 401) + `aud` contains check.
- `hub_ids` claim REQUIRED (missing → 401 — backward incompat M2 v2.0 JWT cần re-login sau Phase 3 deploy).

**Rationale:**
- iss central cố định: SSO model 1 issuer, N audience.
- aud không split: hub con verify `HUB_NAME in current_user.hub_ids` cho local access check (đã đủ E4); aud chỉ phân biệt medinet-wiki với services khác (MCP) — defer Phase 7 MIGRATE-04.
- `hub_ids` REQUIRED: post-Phase 3 deploy, JWT cũ M2 KHÔNG chứa claim → reject → user re-login. Acceptable downtime (15-30s) — communicate operator advance.

### D-V3-Phase3-F · Login Redirect Flow (LOCKED — recommended seed)

**Chốt:** **Hub con login page redirect form action sang central** — KHÔNG cross-origin POST từ hub con.

**Implementation:**
- Frontend hub con (Phase 5 PROXY-02 sau D6 expire): `<form action="https://central/api/auth/login" method="POST">` — browser navigate sang central, central handle login + redirect back `https://wiki.medinet.vn/<hub>/?token=<access_jwt>` (URL fragment access token + DB refresh_token via cookie domain `.medinet.vn` — chỉ refresh_token cookie cross-domain, access JWT qua URL fragment 1 lần).
- Sau redirect, frontend hub con extract access JWT từ URL fragment → localStorage; refresh token implicit qua cookie `.medinet.vn`.
- KHÔNG cross-origin POST từ hub con → central (CORS complexity + preflight overhead).

**Rationale:**
- Standard SSO redirect pattern (SAML/OAuth2 implicit-like flow simplified).
- Tránh CORS preflight + credentials issue.
- D-V3-06 D6 expire ở Phase 5 → frontend rewrite mới + redirect flow đồng thời.

**Note:** Phase 3 KHÔNG ship frontend redirect logic (D6 chưa expire). Phase 3 chỉ ship BACKEND: JWKS endpoint + Redis blacklist + JWT claim `hub_ids` + E4 reinforced. Frontend Phase 5 sẽ wire redirect form.

### D-V3-Phase3-G · Phase 2 Auth Router Refactor (NEW DECISION — Phase 3 scope expansion)

**Chốt:** **Hub con `/api/auth/login` + `/api/auth/refresh` trả 405 hoặc 307 Location: central** — Phase 3 refactor `create_app()` từ Phase 2 Plan 02-01.

**Implementation:**
- `auth_router.post("/login")` ở hub con: detect `settings.hub_name != "central"` → return 307 Location: `{settings.central_url}/api/auth/login` (browser auto-follow).
- `auth_router.post("/refresh")` ở hub con: tương tự → 307.
- `auth_router.get("/me")` + `auth_router.post("/logout")` ở hub con: handle local (verify JWT + Redis blacklist).
- Phase 2 endpoint matrix (FACTOR-03 — 12 specific endpoints) cần update: hub con auth count giảm từ 4 → 2 (me + logout). 2 endpoint chuyển sang redirect ≠ strip (vẫn mount route nhưng response 307).
- Update REQUIREMENTS.md FACTOR-03 note: "hub con auth = 2 specific (me + logout) + 2 redirect (login + refresh → central)".

**Rationale:**
- Phase 2 mount universal auth_router KHÔNG cover SSO contract đầy đủ → Phase 3 phải refactor.
- 307 redirect tốt hơn 405 vì browser auto-follow + tránh form re-render fail.

**Risk:** Phase 2 integration test (`test_factor_hub_scoped.py::test_hub_mounts_hub_scoped[POST /api/auth/login]`) hiện assert KHÔNG-404 (200/401/422 OK). Sau Phase 3 sẽ assert 307. Plan Phase 3 phải update test.

### D-V3-Phase3-H · Redis Blacklist Key Schema + TTL (LOCKED — recommended seed)

**Chốt:**
- Key: `auth:blacklist:{jti}` (jti là UUID4 trong JWT claim).
- Value: `"1"` (marker only — không lưu metadata).
- TTL: `JWT.exp - now()` (auto-expire khi token expired anyway → cleanup miễn phí).
- Lookup: hub con verify JWT → `redis.exists(f"auth:blacklist:{jti}")` → 401 nếu exists.
- Redis instance: M2 baseline `REDIS_URL` chung (KHÔNG split per-hub Redis DB — keep db=0 — share cross-process).

**Rationale:**
- TTL = exp → KHÔNG cần background cleanup cron.
- Marker value đủ — metadata audit qua `audit_logs` table M2 carry forward.
- 1 Redis instance đủ cho v3.0-a (HA Redis defer v4.0 — R-V3-6 LOW severity).

### Claude's Discretion

- JWT signing algorithm pin: RS256 (M2 baseline carry forward — KHÔNG bàn).
- JWT exp duration: 15 phút access + 7 ngày refresh (M2 carry forward).
- JWKS endpoint cache header: `Cache-Control: public, max-age=3600` (1h matches hub con TTL).
- Python library: PyJWT (M2 đã có) + jwcrypto cho JWK export (chuẩn RFC 7517 PKCS#8 → JWK format).
- httpx async client cho JWKS fetch (M2 đã có dep).
- Error envelope shape khi JWT verify fail: 401 `{success:false, error:{code:"AUTH_INVALID_TOKEN", message:"..."}}` M2 ErrorHandlerMiddleware wrap (Phase 2 D-V3-Phase2-E carry forward).

### Folded Todos

No pending todos matched Phase 3 scope (cross_reference_todos step returned empty).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project Spec
- `Hub_All/.planning/PROJECT.md` — Project vision + v3.0 milestone scope + R-V3-5 (JWKS HA risk) + carry-forward decisions.
- `Hub_All/.planning/REQUIREMENTS.md` § "SSO — Auth SSO + hub_ids trong JWT (4 REQ — GA-V3-A chốt ở `/gsd-discuss-phase 3`)" — Lines 45-50, SSO-01..04 spec chi tiết JWKS endpoint + Redis blacklist + hub_ids claim + E4 reinforced.
- `Hub_All/.planning/ROADMAP.md` § "Phase 3 — Auth SSO + hub_ids trong JWT (GA-V3-A)" — Lines 113-130, Phase 3 goal + 4 success criteria + 3 gray area description.
- `Hub_All/.planning/STATE.md` — Current state (Phase 1+2 DONE 2026-05-22, 10/~30 plans complete).

### Prior Phase Context
- `Hub_All/.planning/phases/01-multi-db-topology/01-CONTEXT.md` — D-V3-Phase1 decisions (Settings.hub_name, DSN validator, per-hub Alembic).
- `Hub_All/.planning/phases/01-multi-db-topology/01-02-PLAN.md` — `_enforce_hub_dsn_match` validator pattern (Phase 3 verify hub con bind đúng DB).
- `Hub_All/.planning/phases/02-hub-con-codebase-factor/02-CONTEXT.md` — D-V3-Phase2-A..E decisions + endpoint matrix 12 hub-scoped.
- `Hub_All/.planning/phases/02-hub-con-codebase-factor/02-01-PLAN.md` — `create_app()` conditional mount pattern (Phase 3 refactor auth_router redirect logic).
- `Hub_All/.planning/phases/02-hub-con-codebase-factor/02-04-SUMMARY.md` — Phase 2 closeout + Phase 2 pattern docs.
- `Hub_All/.planning/phases/02-hub-con-codebase-factor/02-05-SUMMARY.md` — FACTOR-04 dynamic hub registration (Phase 3 verify Settings.hub_name dynamic không break SSO).
- `Hub_All/.planning/phases/02-hub-con-codebase-factor/02-VERIFICATION.md` — Phase 2 4/4 SC PASS evidence.

### M2 v2.0 Carry Forward (Auth baseline)
- `Hub_All/api/app/auth/` — M2 v2.0 auth module (JWT RS256, Argon2 pwdlib, refresh_tokens table). Phase 3 extend, KHÔNG rewrite.
- `Hub_All/api/app/auth/router.py` — auth_router 4 endpoint (login/refresh/logout/me) — Phase 3 refactor cho hub con redirect.
- `Hub_All/api/alembic/versions/` — `refresh_tokens` table migration (M2 ship) — Phase 3 KHÔNG migration mới.
- `Hub_All/api/app/auth/jwt.py` — JWT encode/decode helpers (PyJWT) — Phase 3 thêm JWKS publish + cache logic.

### v3.0 Seed
- `Hub_All/.planning/seeds/v3.0-multi-hub-split.md` — Lines 59 + 91 — JWT shared vs JWKS gray area + Phase 3 description.

### External Spec (RFC reference)
- RFC 7517 JWK Set — JWKS endpoint format `{"keys": [{"kty":"RSA", "kid":"...", "use":"sig", "n":"...", "e":"AQAB"}]}`.
- RFC 7519 JWT — `iss`, `aud`, `exp`, `jti` claim semantic.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets (M2 v2.0 ship — Phase 3 carry forward)

- `Hub_All/api/app/auth/router.py` — 4 endpoint (login/refresh/logout/me). Phase 3 refactor hub con behavior cho login + refresh (307 redirect tới central).
- `Hub_All/api/app/auth/jwt.py` — JWT encode/decode helpers PyJWT RS256. Phase 3 thêm `publish_jwks()` function + `JWKSCache` class.
- `Hub_All/api/app/auth/service.py` — `AuthService` (login/refresh/logout/blacklist). Phase 3 thêm `hub_ids` claim build từ user.hub_ids relationship.
- `Hub_All/api/app/auth/dependencies.py` — `get_current_user` dependency verify JWT. Phase 3 update: nếu hub con, verify qua JWKS cache + check `HUB_NAME in current_user.hub_ids`.
- `Hub_All/api/keys/` — RS256 private.pem + public.pem PKCS#8 (M2 generate qua `make keys`). Phase 3 dùng public.pem để publish JWKS endpoint ở central.
- `Hub_All/api/alembic/versions/<...>_refresh_tokens.py` — `refresh_tokens` table (id, user_id, token_hash, expires_at, revoked_at). M2 carry forward.

### Established Patterns

- **JWT verify pattern (M2):** Dependency `Depends(get_current_user)` → decode JWT → check Redis blacklist → load user from DB → return `User` model. Phase 3 refactor: hub con dùng JWKS cache instead of local public.pem read.
- **Redis client pattern:** `redis.asyncio.Redis.from_url(settings.redis_url)` singleton qua `lru_cache` (M2). Phase 3 reuse — KHÔNG split per-hub Redis DB.
- **Error envelope wrap (Phase 2 D-V3-Phase2-E):** `M2 ErrorHandlerMiddleware` + Starlette HTTPException handler (Phase 2 Plan 02-03 Rule 2). 401/403 từ Phase 3 đi qua wrap → consistent envelope.
- **lifespan startup pattern (FastAPI):** `@asynccontextmanager async def lifespan(app):` block dùng cho JWKS cache fetch initial.

### Integration Points

- **`api/app/main.py::create_app()`** — Phase 3 thêm `if settings.hub_name != "central":` block trong lifespan startup → `await jwks_cache.fetch_initial(settings.central_jwks_url)`.
- **`api/app/auth/router.py`** — Phase 3 thêm conditional return 307 redirect cho login/refresh ở hub con.
- **`api/app/auth/dependencies.py::get_current_user`** — Phase 3 refactor: branch verify path (central dùng local private.pem; hub con dùng JWKS cache).
- **`docker-compose.yml`** — Phase 3 thêm env `CENTRAL_URL=http://python-api-central:8080` + `CENTRAL_JWKS_URL=http://python-api-central:8080/.well-known/jwks.json` cho 3 hub con service block. KHÔNG sửa central block.
- **`api/app/config.py::Settings`** — Phase 3 thêm field `central_url: str | None = None` (required cho hub con qua field_validator) + `central_jwks_url: str | None = None` (compute từ central_url default).

### Creative Options Enabled

- JWKS cache reuse cho per-hub frontend (Phase 5 PROXY-02) verify JWT client-side (dùng jose.js fetch JWKS từ central qua CORS).
- Audit trail hub_ids claim — log mỗi cross-hub access denied → Prometheus metric `auth_cross_hub_denied_total` (HARD-02 carry forward).

</code_context>

<specifics>
## Specific Ideas

- **JWKS endpoint test pattern:** Integration test rotate central keypair → verify hub con detect mới trong TTL window. Pattern: spawn 2 process (central + yte) via TestClient + ASGI lifespan, fetch JWKS từ hub con cache → verify == central public key → swap central keypair → wait TTL (mock asyncio.sleep với freezegun) → fetch lại → verify mới.
- **stale JWT test pattern (E4 reinforced):** Build stale JWT với `hub_ids=["duoc"]` + valid signature → POST tới `medinet_hub_yte` `/api/documents` → assert 403 (KHÔNG 404 — endpoint exist nhưng access denied; KHÔNG 500 — verify path complete). Reference pattern: Phase 2 Plan 02-03 `test_factor_hub_scoped.py` (sửa fixture parametrize hub_name).
- **Backward incompat warning operator:** Phase 3 deploy → JWT M2 cũ KHÔNG có `hub_ids` claim → reject. Operator phải communicate downtime 15-30s (broadcast Slack + login screen banner "session expired, please re-login"). README.md Phase 3 ship phải có note.

</specifics>

<deferred>
## Deferred Ideas

### Defer Phase 5 PROXY-02 (frontend rewrite)
- Login form redirect implementation (`<form action="https://central/api/auth/login">`) — Phase 3 chỉ ship backend, frontend wire ở Phase 5 sau D-V3-06 D6 expire.
- Per-hub branding component (logo/title/theme) — defer Phase 5 PROXY-04.

### Defer Phase 6 SETTINGS-04 (hub registry table)
- `hub_registry` table thay thế `Settings.hub_name` env-only — Phase 3 vẫn dùng Settings.hub_name (Phase 2 FACTOR-04 carry forward).

### Defer Phase 7 MIGRATE-04 (MCP service re-point)
- MCP service JWT verify dùng JWKS cache (cùng pattern hub con) — defer Phase 7.
- JWT audience split `medinet-wiki-mcp` vs `medinet-wiki-api` — defer Phase 7.

### Defer v4.0 (Production Hardening)
- HA Redis cluster (R-V3-6 LOW) — single Redis đủ cho v3.0-a/b.
- JWT rotation strategy (sliding refresh window) — re-use M2 baseline.
- JWKS endpoint rate limit (R-V3-5 surface area) — Caddy WAF rule defer Phase 5.
- Branch protection rule GitHub repo enforce auth review trước merge — defer v4.0.

### Reviewed Todos (not folded)
No pending todos reviewed in cross_reference_todos.

</deferred>

---

*Phase: 03-auth-sso-hub-ids-jwt*
*Context gathered: 2026-05-22 via `--auto --chain` mode (planner seed defaults)*
*Auto-chain active → next: `/gsd-plan-phase 3 --auto`*
