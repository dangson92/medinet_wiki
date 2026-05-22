---
phase: 03-auth-sso-hub-ids-jwt
reviewed: 2026-05-22T00:00:00Z
depth: standard
files_reviewed: 17
files_reviewed_list:
  - Hub_All/api/app/auth/jwks.py
  - Hub_All/api/app/auth/jwt.py
  - Hub_All/api/app/auth/_blacklist.py
  - Hub_All/api/app/auth/dependencies.py
  - Hub_All/api/app/auth/router.py
  - Hub_All/api/app/auth/service.py
  - Hub_All/api/app/auth/__init__.py
  - Hub_All/api/app/config.py
  - Hub_All/api/app/main.py
  - Hub_All/api/tests/unit/test_jwks_publish.py
  - Hub_All/api/tests/unit/test_jwks_cache.py
  - Hub_All/api/tests/unit/test_config_jwks.py
  - Hub_All/api/tests/unit/test_get_current_user_jwks_branch.py
  - Hub_All/api/tests/unit/test_jwt_iss_aud_hub_ids.py
  - Hub_All/api/tests/unit/test_redis_blacklist_key_schema.py
  - Hub_All/api/tests/unit/test_auth_router_hub_redirect.py
  - Hub_All/api/tests/integration/test_jwks_cache_lifecycle.py
  - Hub_All/api/tests/integration/test_sso_blacklist_cross_process.py
  - Hub_All/docker-compose.yml
  - Hub_All/docker-compose.override.yml.template
findings:
  critical: 0
  warning: 4
  info: 7
  total: 11
status: issues_found
---

# Phase 3: Code Review Report — Auth SSO + hub_ids trong JWT

**Reviewed:** 2026-05-22
**Depth:** standard
**Files Reviewed:** 17 source + 4 test/compose
**Status:** issues_found (0 Critical, 4 Warning, 7 Info)

## Tóm tắt

Phase 3 v3.0 Multi-Hub Split triển khai 5 plan SSO-01..04 với 8 quyết định LOCKED. Triển khai bám sát spec: JWKS endpoint RFC 7517 + JWKSCache in-process LRU + JWT `iss/aud/hub_ids` REQUIRED + Redis blacklist key `auth:blacklist:{jti}` + 307 redirect hub con → central. Test coverage tốt cho cả unit + integration (kid rotation lifecycle, stale 24h, cross-process blacklist, E4 reinforced Layer 3).

**Đánh giá tổng thể:** KHÔNG có vấn đề Critical security/data-loss. Phát hiện 4 Warning đáng chú ý:
1. `router.py::logout` re-verify JWT bằng `JWTManager.verify_token` (local PEM) thay vì JWKSCache khi chạy ở hub con — fragile (phụ thuộc shared volume `/keys`), trái với pattern `get_current_user` đã dùng JWKSCache cho hub con.
2. `get_current_user_for_hub_access` KHÔNG bypass admin role ở hub con — admin với `hub_ids=[]` (onboarding scenario allowed bởi `test_jwt_empty_hub_ids_allowed`) sẽ bị 403 ở mọi endpoint hub con, mâu thuẫn với docstring "admin role cross-hub theo thiết kế".
3. `_sso_redirect` build URL bằng string concat KHÔNG validate trailing slash — operator misconfig `CENTRAL_URL=http://central/` sẽ gây `//api/auth/login` 404.
4. JWKS endpoint `/.well-known/jwks.json` đọc PEM file mỗi request (KHÔNG cache trong memory) — DoS surface nhỏ (file system read per request) nhưng có thể bị flood.

7 Info chủ yếu là code quality (lazy import per-request, lock missing trên hot-path read, bare-except, missing test coverage).

## Warnings

### WR-01: Hub con `logout` re-verify JWT bằng local PEM thay vì JWKSCache

**File:** `Hub_All/api/app/auth/router.py:158`
**Issue:**
Endpoint `POST /api/auth/logout` đã có `user: User = Depends(get_current_user)` — dependency này verify JWT đúng cách (hub con dùng JWKSCache theo Plan 03-02). Sau đó router gọi thêm `jwt_mgr.verify_token(token, expected_type="access")` để lấy `jti + exp`. Method này dùng `self._public_pem` (local PEM bytes load ở `JWTManager.__init__`), KHÔNG đi qua JWKSCache.

Trong docker-compose hiện tại, `./api/keys:/keys:ro` mount shared cho cả central + 3 hub con → local PEM giống central PEM → verify pass. Nhưng:
- Trái với pattern Plan 03-02 D-V3-Phase3-D "hub con verify qua JWKSCache".
- Nếu operator cấp keypair khác cho hub con (vd staging rotate sớm), logout sẽ FAIL 401 INVALID_TOKEN trong khi `get_current_user` đã pass.
- Hub con KHÔNG cần có private/public PEM local — nhưng `JWTManager.__init__` load PEM ở lifespan main.py:168 (`app.state.jwt_manager = JWTManager(settings)`) — boot fail nếu thiếu PEM.

**Fix:**
Phương án A (preferred — minimal change): Lấy `jti + exp` từ `request.state.jwt_claims` đã được `get_current_user` set sẵn (line 219 dependencies.py):
```python
@router.post("/logout")
async def logout(
    request: Request,
    body: LogoutRequest | None = None,
    user: User = Depends(get_current_user),
    service: AuthService = Depends(get_auth_service),
) -> JSONResponse:
    claims = getattr(request.state, "jwt_claims", None)
    if claims is None:
        return resp.unauthorized(
            message="Token state chưa init", code="AUTH_STATE_MISSING"
        )
    refresh_token = body.refresh_token if body else None
    try:
        await service.logout(
            access_jti=claims.jti,
            access_exp=claims.exp,
            refresh_token=refresh_token,
        )
    except AuthError as e:
        return _auth_error_to_response(e)
    return resp.ok(data={"message": "Đăng xuất thành công"})
```
Xoá luôn `jwt_mgr` dependency khỏi `logout` signature + xoá Bearer parsing (đã được `get_current_user` xử lý).

Phương án B (nếu muốn giữ verify lần 2 cho refresh_token body): branch theo `settings.hub_name` giống `get_current_user`.

---

### WR-02: `get_current_user_for_hub_access` KHÔNG bypass admin → admin bị block ở hub con

**File:** `Hub_All/api/app/auth/dependencies.py:381`
**Issue:**
Dependency check `if settings.hub_name not in claims.hub_ids: raise 403 CROSS_HUB_ACCESS_DENIED`. KHÔNG có nhánh `user.role == "admin"` bypass.

Mâu thuẫn 2 nguồn:
- `get_current_user_with_hubs` docstring (line 317): "admin role vẫn trả hub_ids thực tế nhưng `hub_filter_clause`/`verify_hub_access` sẽ bypass filter cho admin (quản trị cross-hub theo thiết kế)".
- `test_jwt_empty_hub_ids_allowed` (test_jwt_iss_aud_hub_ids.py:177): JWT của admin với `hub_ids=[]` được PASS verify — nghĩa là admin có thể có `hub_ids=[]`. Scenario: admin onboarding chưa assign hub.

Hậu quả: Admin với `hub_ids=[]` (hoặc admin assign chỉ `["central_admin"]`) khi gọi endpoint hub con bất kỳ (ví dụ `POST /api/documents` ở `python-api-yte`) → 403 CROSS_HUB_ACCESS_DENIED. Đây là regression so với design admin cross-hub.

**Fix:**
Thêm admin bypass tương tự central bypass:
```python
async def get_current_user_for_hub_access(
    request: Request,
    user: User = Depends(get_current_user),
) -> User:
    from app.config import get_settings

    settings = get_settings()
    if settings.hub_name == "central":
        return user  # cross-hub by design

    # Admin bypass — cross-hub admin theo thiết kế (USER-03 + HUB-02)
    if user.role == "admin":
        return user

    claims = getattr(request.state, "jwt_claims", None)
    # ... rest unchanged
```

Hoặc nếu thiết kế muốn admin BẮT BUỘC có hub trong claims (zero-trust), cập nhật docstring + thêm test verify admin với `hub_ids=[]` bị 403 ở hub con.

---

### WR-03: `_sso_redirect` build URL KHÔNG validate trailing slash → 404 silent

**File:** `Hub_All/api/app/auth/router.py:85`
**Issue:**
```python
return RedirectResponse(
    url=f"{settings.central_url}{target_path}",
    status_code=307,
    ...
)
```
String concat trực tiếp. Nếu operator set `CENTRAL_URL=http://python-api-central:8080/` (trailing slash — thói quen viết URL), thì target sẽ là `http://python-api-central:8080//api/auth/login` → central 404. Hub con redirect 307 thành công nhưng browser follow → 404 NOT_FOUND ở central → user thấy lỗi confusion "Đăng nhập fail" không rõ nguyên nhân.

Docker-compose hiện tại đặt `CENTRAL_URL: http://python-api-central:8080` (KHÔNG trailing) → OK. Nhưng template `docker-compose.override.yml.template` cũng KHÔNG trailing slash → fragile khi operator thêm hub mới qua `make hub-add` mà sao chép URL từ nơi khác.

**Fix:**
Option A — strip trailing slash trong validator Settings:
```python
@field_validator("central_url", mode="after")
@classmethod
def _strip_trailing_slash(cls, v: str | None) -> str | None:
    if v is not None:
        return v.rstrip("/")
    return v
```

Option B — strip trong `_sso_redirect`:
```python
base = settings.central_url.rstrip("/")
return RedirectResponse(url=f"{base}{target_path}", ...)
```

Option A preferred — fail-fast ở Settings init thay vì runtime, đồng thời cover cho future `central_url` consumers (Phase 5 PROXY-02 frontend).

---

### WR-04: JWKS endpoint đọc PEM file mỗi request → DoS surface

**File:** `Hub_All/api/app/main.py:519-535`
**Issue:**
```python
@app.get("/.well-known/jwks.json", ...)
async def jwks_endpoint() -> StarletteJSONResponse:
    try:
        jwks = publish_jwks(settings.jwt_public_key_path)
    ...
```
`publish_jwks()` gọi `pem_path.read_bytes()` + `serialization.load_pem_public_key()` + `_int_to_base64url()` MỖI request. Endpoint là public (KHÔNG auth). Attacker có thể flood `/.well-known/jwks.json` → file system read I/O contention + CPU parsing.

Mitigation hiện có: `Cache-Control: public, max-age=3600` chỉ áp dụng client-side (browser/reverse-proxy cache) — attacker bypass bằng cách KHÔNG gửi `If-None-Match`/cache header → server vẫn parse mỗi request.

Threat severity: thấp (PEM file nhỏ, parse RSA 4096-bit ~ms, no DB hit), nhưng dễ fix.

**Fix:**
Cache JWK Set trong memory ở app.state lúc lifespan startup (central path), serve cached value. Rotation strategy: cache invalidate khi PEM mtime đổi (hoặc require restart — matching `make keys` workflow hiện tại).
```python
# Trong lifespan central path:
if settings.hub_name == "central":
    try:
        app.state.jwks_cached = publish_jwks(settings.jwt_public_key_path)
        logger.info("jwks_cached_ready")
    except (OSError, ValueError) as e:
        app.state.jwks_cached = None
        logger.error("jwks_cache_init_failed: %s", e)

# Trong endpoint:
@app.get("/.well-known/jwks.json", ...)
async def jwks_endpoint() -> StarletteJSONResponse:
    jwks = getattr(app.state, "jwks_cached", None)
    if jwks is None:
        # Fallback re-read (also handles failed initial load case)
        try:
            jwks = publish_jwks(settings.jwt_public_key_path)
            app.state.jwks_cached = jwks
        except (OSError, ValueError) as e:
            return StarletteJSONResponse(status_code=503, content={...})
    return StarletteJSONResponse(content=jwks, headers={"Cache-Control": "public, max-age=3600"})
```

Alternative đơn giản: dùng `@functools.lru_cache(maxsize=1)` cho `publish_jwks` — nhưng key sẽ là `Path` immutable, KHÔNG invalidate khi `make keys` rotate. Approach trên cho phép manual reset qua restart central (đúng workflow LOCKED).

## Info

### IN-01: `get_current_user` lazy import per-request

**File:** `Hub_All/api/app/auth/dependencies.py:123, 138-144`
**Issue:**
Trong hot path `get_current_user`, có 4 lazy import nằm trong function body: `from app.config import get_settings`, `import jwt as pyjwt`, `from app.auth.jwks import (...)`. Python cache module sau lần đầu nên overhead nhỏ, nhưng attribute lookup vẫn add ~µs mỗi request + làm code khó scan.

**Fix:** Move imports lên module-level top-of-file. Không có circular import risk vì `app.auth.jwks` KHÔNG import `app.auth.dependencies`.

---

### IN-02: `JWKSCache.get_public_key` và `is_stale` đọc state KHÔNG lock

**File:** `Hub_All/api/app/auth/jwks.py:300-324`
**Issue:**
`is_stale()` đọc `self._last_refresh_ts` và `get_public_key()` đọc `self._keys_by_kid` KHÔNG acquire `self._lock`. `_fetch_and_cache` ghi cả 2 dưới lock. Python GIL làm assignment `self._keys_by_kid = new_keys` atomic (reader chỉ thấy ref cũ HOẶC ref mới — KHÔNG partial dict), và `time.time()` float assignment cũng atomic — nên hiện tại không gây bug. Nhưng:
- Code style: pattern "lock write but unlocked read" dễ misleading future maintainer.
- Nếu sau này thêm field cần invariant (vd `_last_refresh_ts` cùng `_keys_by_kid` phải reflect cùng 1 fetch), unlocked read sẽ break invariant.

**Fix:** Document rõ ràng trong docstring `JWKSCache` rằng read path intentionally lock-free + lý do (GIL + atomic reference swap pattern). Hoặc dùng `asyncio.Lock` cho cả read path nếu muốn invariant tightness — nhưng tăng latency.

---

### IN-03: `router.py::logout` bare `except Exception` swallow

**File:** `Hub_All/api/app/auth/router.py:159`
**Issue:**
```python
try:
    claims = jwt_mgr.verify_token(token, expected_type="access")
except Exception:  # noqa: BLE001
    return resp.unauthorized(...)
```
Swallow mọi exception (bao gồm `KeyError`/`AttributeError` từ bug code) → trả 401 INVALID_TOKEN gây misleading debug. Nên catch cụ thể `JWTError`.

**Fix:**
```python
from app.auth.jwt import JWTError
...
try:
    claims = jwt_mgr.verify_token(token, expected_type="access")
except JWTError:
    return resp.unauthorized(message="Token không hợp lệ", code="INVALID_TOKEN")
```
(Nếu fix WR-01 thì block try/except này biến mất hoàn toàn.)

---

### IN-04: `_refresh_loop` exception handler có thể spin tight nếu `asyncio.sleep` fail

**File:** `Hub_All/api/app/auth/jwks.py:343-351`
**Issue:**
```python
while True:
    try:
        await asyncio.sleep(self._refresh_interval)
        await self.refresh()
    except asyncio.CancelledError:
        ...
    except Exception as e:
        logger.error("jwks_refresh_loop_unexpected: %s", e)
```
Trong trường hợp cực hiếm `asyncio.sleep` raise lỗi (event loop bị shutdown bất thường), loop sẽ log error rồi `continue` ngay → spin tight log spam. `refresh()` đã wrap try/except internal → exception ra đến đây chỉ từ `sleep` hoặc programming error.

**Fix:** Thêm fallback sleep trong except branch để tránh tight loop:
```python
except Exception as e:
    logger.error("jwks_refresh_loop_unexpected: %s", e)
    # Sleep ngắn để tránh tight loop nếu sleep() chính fail
    try:
        await asyncio.sleep(min(60, self._refresh_interval))
    except asyncio.CancelledError:
        raise
```

---

### IN-05: `JWKSCache` first refresh delayed `refresh_interval` (1h default) sau boot

**File:** `Hub_All/api/app/auth/jwks.py:336-346`
**Issue:**
Pattern `while True: await asyncio.sleep(refresh_interval); await self.refresh()` — sau `fetch_initial()` boot, refresh tiếp theo phải đợi 1h. Nếu central rotate keypair ngay sau khi hub con boot xong, hub con miss key mới tới 1h (acceptable per D-V3-Phase3-D, nhưng có thể UX nicer nếu first refresh ở `refresh_interval/2`).

**Fix:** Cosmetic, không bắt buộc. Nếu muốn refresh phân bố đều giữa N hub con (tránh thundering-herd central JWKS endpoint), thêm jitter:
```python
import random
await asyncio.sleep(self._refresh_interval + random.uniform(0, 60))
```

---

### IN-06: Thiếu test coverage cho `_enforce_central_url_for_hub` validator strip vs preserve

**File:** `Hub_All/api/tests/unit/test_config_jwks.py:136-156`
**Issue:**
Test verify hub con KHÔNG có CENTRAL_URL → raise. Nhưng KHÔNG test:
- Trailing slash handling (WR-03): `CENTRAL_URL=http://central/` → validator hiện tại accept → silent bug ở `_sso_redirect`.
- Malformed URL: `CENTRAL_URL=not-a-url` → validator hiện tại accept → 307 redirect với location không valid.

**Fix:** Sau khi fix WR-03 (validator strip slash), thêm test cases:
```python
def test_central_url_strips_trailing_slash(monkeypatch):
    _common_env(monkeypatch, "yte")
    monkeypatch.setenv("CENTRAL_JWKS_URL", "http://c:8080/.well-known/jwks.json")
    monkeypatch.setenv("CENTRAL_URL", "http://python-api-central:8080/")  # trailing
    get_settings.cache_clear()
    s = Settings()
    assert s.central_url == "http://python-api-central:8080"  # stripped
```

---

### IN-07: `__init__.py` docstring outdated — đề cập "Plan 03-02" cho password module

**File:** `Hub_All/api/app/auth/__init__.py:18-21`
**Issue:**
```python
"""
Plan 03-02 ships JWT layer. Plan 03-03 extends với Argon2 password hasher.
Plan 03-04 thêm AuthService + dependencies + router (4 endpoint
login/refresh/logout/me).
"""
```
Plan numbering này thuộc M2 (Phase 3 cũ). v3.0 Phase 3 plan numbering hoàn toàn khác (03-01 JWKS publish, 03-02 JWKS cache, 03-03 hub_ids+blacklist, 03-04 SSO redirect, 03-05 closeout). Docstring có thể gây nhầm lẫn cho operator/maintainer mới.

**Fix:** Cập nhật docstring phản ánh v3.0 Phase 3 plan map, hoặc bỏ Plan numbering cụ thể, chỉ giữ public API description.

---

## Phụ lục: Checklist các điểm KHÔNG phát hiện vấn đề

Các threat model focus được verify pass:
- **JWT alg confusion (T-03-jwt-alg-confusion):** `JWT_ALGORITHMS_ALLOWED = ["RS256"]` cứng ở cả `verify_token` + `verify_token_with_key`. KHÔNG có path nào cho phép mở rộng.
- **JWKS cache poisoning:** Hub con verify JWT bằng public key reconstruct từ JWK Set fetched qua HTTPS (production) / intra-network HTTP (compose). Kid bị attacker forge → `JWKSKidNotFoundError` 401, KHÔNG silent accept.
- **Hub_ids forge via aud confused-deputy:** `aud` REQUIRED + `hub_ids` REQUIRED + Layer 3 enforcement (`get_current_user_for_hub_access`) check `settings.hub_name in claims.hub_ids`. Stale JWT cross-hub → 403 envelope rõ ràng.
- **Redis blacklist key collision (T-D-V3-Phase3-H):** Key schema `auth:blacklist:{jti}` namespace tránh collision. jti UUID4 (122 bit entropy) → collision không khả thi.
- **TTL=0 edge case logout:** `max(1, exp - now)` guard ở `service.py:251` — token đã expired vẫn blacklist với TTL=1s (tránh `SET ex=0` redis behavior undefined).
- **307 redirect with body preserve:** `RedirectResponse(status_code=307)` đúng RFC 7231 method-preserving. Test `test_hub_con_login_returns_307_redirect_to_central` verify status code + Location header + X-SSO debug headers.
- **Boot fail-loud (D-V3-Phase3-B):** `JWKSCache.fetch_initial` re-raise exception → `main.py:217-224` re-raise → uvicorn exit 1.
- **24h hard limit (R-V3-5):** `JWKSCache.is_stale()` + `get_public_key` raise `JWKSStaleError` → dependency render 503 JWKS_STALE envelope.
- **Cross-process Redis blacklist:** Helper `make_blacklist_key` ở `_blacklist.py` shared module → central + hub con cùng dùng → key consistency guaranteed.
- **E4 reinforced 3-layer:** Layer 1 (Settings `_enforce_hub_dsn_match` Phase 1) + Layer 2 (repo `WHERE hub_id = settings.hub_name` M2 carry forward) + Layer 3 (Phase 3 mới `get_current_user_for_hub_access`) verify đầy đủ trong code path.

---

_Reviewed: 2026-05-22_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
