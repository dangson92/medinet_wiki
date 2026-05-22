"""Phase 2 FACTOR-02/03 — Integration test endpoint matrix hub-scoped vs central-only.

Verify:
- FACTOR-02: 8 router central-only strip ở hub con (yte/duoc/hcns) → 404 envelope
  shape (D-V3-Phase2-E).
- FACTOR-03: 12 endpoint hub-scoped (D-V3-Phase2-D matrix) mount ở hub con —
  status_code != 404 (mount đúng; dependency có thể reject 401/422 OK).
- Central giữ NGUYÊN 20 endpoint (12 + 8) — M2 backward-compat.
- Phase 1 _enforce_hub_dsn_match regression: HUB_NAME=yte + DSN central → raise.

Test in-process qua TestClient(app) — KHÔNG cần docker/testcontainers (Plan 02-04
sẽ smoke compose-level).

COCOINDEX_SKIP_SETUP=1 trong hub_app_factory bypass cocoindex Environment singleton.
Lifespan asyncpg.create_pool fail-soft (Phase 1 skeleton — log warning, KHÔNG raise).

Plan 02-03 Task 2.

CLEANUP NOTE (WRN-03 fix): autouse `_phase2_clear_settings_cache_after` khai báo
TRONG FILE NÀY (không ở conftest.py) — chỉ áp dụng các test Phase 2 trong file.
Tránh affect Phase 1 hub_isolation + Phase 3 v2.0 auth_client fixture chain (autouse
ở conftest.py sẽ chạy cho mọi test integration → flaky risk).

BLK-01 fix: CENTRAL_ONLY_ENDPOINTS dùng `("GET", "/api/sync/stats")` — endpoint
thực tế của sync_router M2 compat stub (api/app/routers/sync.py line 39).
KHÔNG dùng endpoint `POST /api/sync` + segment "/run" legacy Go-era (chưa bao
giờ được port sang M2 — sẽ false-positive 404 ở central). Acceptance grep guard:
zero reference exact-string ở file này (regression guard cho BLK-01).
"""
from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

# Marker — HARD-03 CI gate critical path + integration suite.
pytestmark = [pytest.mark.critical, pytest.mark.integration]


# ─── Endpoint matrix D-V3-Phase2-D ─────────────────────────────────────────
# 12 endpoint hub-scoped tổng (Phase 2 FACTOR-03 baseline). Plan 03-04 SSO-02
# (D-V3-Phase3-G LOCKED 2026-05-22) split thành 2 group:
#   - 10 endpoint handle LOCAL ở hub con (status != 404, có thể 200/401/422).
#   - 2 endpoint SSO REDIRECT 307 (POST /api/auth/login + /api/auth/refresh).
# central giữ NGUYÊN 12 mount + handle local cho tất cả.
HUB_SCOPED_ENDPOINTS: list[tuple[str, str]] = [
    ("POST", "/api/auth/login"),
    ("POST", "/api/auth/refresh"),
    ("POST", "/api/auth/logout"),
    ("GET", "/api/auth/me"),
    ("GET", "/api/profile"),
    ("PATCH", "/api/profile"),
    ("POST", "/api/documents"),
    ("GET", "/api/documents"),
    ("DELETE", "/api/documents/00000000-0000-0000-0000-000000000000"),
    ("POST", "/api/search"),
    ("POST", "/api/ask"),
    ("GET", "/api/usage"),
]

# Phase 3 Plan 03-04 SSO-02 (D-V3-Phase3-G LOCKED) — Hub con auth login/refresh
# trả 307 Location: central thay vì handle local. Tách split assertion semantic.
HUB_SCOPED_SSO_REDIRECT_ENDPOINTS: list[tuple[str, str]] = [
    ("POST", "/api/auth/login"),    # → 307 Location: central
    ("POST", "/api/auth/refresh"),  # → 307 Location: central
]

# 10 endpoint còn lại — hub con handle LOCAL (Phase 2 FACTOR-03 carry forward
# semantic; Plan 03-04 KHÔNG đụng).
HUB_SCOPED_LOCAL_ENDPOINTS: list[tuple[str, str]] = [
    ep for ep in HUB_SCOPED_ENDPOINTS if ep not in HUB_SCOPED_SSO_REDIRECT_ENDPOINTS
]

# 9 endpoint central-only — STRIP ở hub con (FACTOR-02 + FACTOR-02 extend)
# NOTE BLK-01 fix: sync_router thực tế (api/app/routers/sync.py M2 compat stub)
# chỉ có /stats, /batches, /batches/{id}, approve, reject (KHÔNG có /run legacy).
# Plan 02-03 dùng GET /api/sync/stats làm proxy verify FACTOR-02 strip semantic.
#
# Phase 4 Plan 04-05 (SYNC-03 / D-V3-Phase4-D3) — FACTOR-02 extend: thêm
# POST /api/search/cross-hub vào CENTRAL_ONLY list. Tach khoi universal
# `search_router` (van mount moi process cho /api/search + /api/search/similar).
# Hub con KHONG own cross-hub aggregated data (medinet_central.chunks
# denormalized read replica per D-V3-02) → strip endpoint la correct semantic.
# Hub con request → 404 NOT_FOUND envelope D6.
CENTRAL_ONLY_ENDPOINTS: list[tuple[str, str]] = [
    ("GET", "/api/rag-config"),
    ("GET", "/api/api-keys"),
    ("GET", "/api/hubs"),
    ("GET", "/api/users"),
    ("GET", "/api/audit-logs"),
    ("GET", "/api/system-settings"),
    ("GET", "/api/sync/stats"),
    ("GET", "/api/mcp/my-oauth-client"),
    # Phase 4 Plan 04-05 SYNC-03 — Cross-hub aggregated search central-only:
    ("POST", "/api/search/cross-hub"),
]


@pytest.fixture(autouse=True)
def _phase2_clear_settings_cache_after() -> Iterator[None]:
    """Cleanup lru_cache Settings sau MỖI test Phase 2 — CỤC BỘ trong file này.

    WRN-03 fix: KHÔNG khai báo ở conftest.py để tránh autouse chạy cho mọi test
    integration (Phase 1 hub_isolation + Phase 3 v2.0 auth_client chain) →
    có thể clear cache giữa assert → flaky.

    autouse=True ở module-level chỉ áp dụng test trong file này.
    """
    from app.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _dispatch(client: TestClient, method: str, path: str) -> Any:
    """Gọi TestClient với method động, body rỗng (không validate body — chỉ mount check)."""
    method_lower = method.lower()
    if method_lower == "get":
        return client.get(path)
    if method_lower == "post":
        return client.post(path, json={})
    if method_lower == "patch":
        return client.patch(path, json={})
    if method_lower == "delete":
        return client.delete(path)
    if method_lower == "put":
        return client.put(path, json={})
    raise ValueError(f"Method không support: {method}")


def _is_envelope_404(response: Any) -> bool:
    """True nếu response là 404 envelope shape D-V3-Phase2-E.

    Envelope shape: {success:false, data:null, error:{code, message}, meta:null}
    Tolerance: error.code value linh hoạt (NOT_FOUND / ERROR / HTTP_404 / ...) —
    chỉ verify shape đầy đủ + presence "code" + "message" trong error dict.
    """
    if response.status_code != 404:
        return False
    try:
        body = response.json()
    except ValueError:
        return False
    if body.get("success") is not False:
        return False
    if body.get("data") is not None:
        return False
    error = body.get("error")
    if not isinstance(error, dict):
        return False
    if "code" not in error:
        return False
    if "message" not in error:
        return False
    return True


def test_central_mounts_all_endpoints(hub_app_factory: Any) -> None:
    """Central giữ NGUYÊN 20 endpoint (12 hub-scoped + 8 central-only)."""
    app = hub_app_factory("central")
    with TestClient(app) as client:
        for method, path in HUB_SCOPED_ENDPOINTS + CENTRAL_ONLY_ENDPOINTS:
            resp = _dispatch(client, method, path)
            assert resp.status_code != 404, (
                f"Central PHẢI mount {method} {path} — status: {resp.status_code} "
                f"body: {resp.text[:200]}"
            )


@pytest.mark.parametrize("hub_name", ["yte", "duoc", "hcns"])
def test_hub_strips_central_only(hub_app_factory: Any, hub_name: str) -> None:
    """Hub con (yte/duoc/hcns) STRIP 8 endpoint central-only → 404 envelope (FACTOR-02)."""
    app = hub_app_factory(hub_name)
    with TestClient(app) as client:
        for method, path in CENTRAL_ONLY_ENDPOINTS:
            resp = _dispatch(client, method, path)
            assert resp.status_code == 404, (
                f"Hub {hub_name} PHẢI strip {method} {path} (404) — actual: "
                f"{resp.status_code} body: {resp.text[:200]}"
            )
            assert _is_envelope_404(resp), (
                f"Hub {hub_name} {method} {path} 404 PHẢI envelope shape "
                f"{{success:false, data:null, error:{{code,message}}, meta:null}} — "
                f"actual body: {resp.text[:300]}"
            )


@pytest.mark.parametrize("hub_name", ["yte", "duoc", "hcns"])
def test_hub_mounts_hub_scoped(hub_app_factory: Any, hub_name: str) -> None:
    """Hub con (yte/duoc/hcns) MOUNT 12 endpoint hub-scoped — 10 LOCAL + 2 SSO REDIRECT.

    Phase 2 Plan 02-03 ship 12 endpoint không 404. Plan 03-04 SSO-02
    (D-V3-Phase3-G) refine assertion:
    - 10 endpoint LOCAL handle: assert != 404 (200/401/422/etc.) — semantic cũ.
    - 2 endpoint SSO REDIRECT (login + refresh): assert == 307 Location: central
      (Plan 03-04 Task 2 ship router refactor).

    TestClient `follow_redirects=False` critical — default follow tự động sẽ
    mất 307 status code, mất Location header (KHÔNG verify được redirect).
    """
    app = hub_app_factory(hub_name)
    with TestClient(app, follow_redirects=False) as client:
        # Group 1 — 10 endpoint local handle (Phase 2 FACTOR-03 carry forward)
        for method, path in HUB_SCOPED_LOCAL_ENDPOINTS:
            resp = _dispatch(client, method, path)
            assert resp.status_code != 404, (
                f"Hub {hub_name} PHẢI mount {method} {path} (FACTOR-03 LOCAL) — "
                f"actual: {resp.status_code} body: {resp.text[:200]}"
            )

        # Group 2 — 2 endpoint SSO REDIRECT (Plan 03-04 SSO-02 D-V3-Phase3-G)
        # IMPORTANT: gửi body Pydantic-valid cho login/refresh — KHÔNG `json={}`
        # vì Pydantic validation reject 422 TRƯỚC khi handler chạy → KHÔNG có
        # branch redirect 307. Plan 03-04 router branch hub con check ở
        # handler-level (sau body parse) nên test phải gửi body hợp lệ.
        sso_valid_bodies = {
            "/api/auth/login": {"email": "u@m.vn", "password": "secret"},
            "/api/auth/refresh": {"refresh_token": "dummy.refresh.token"},
        }
        for method, path in HUB_SCOPED_SSO_REDIRECT_ENDPOINTS:
            body = sso_valid_bodies.get(path, {})
            resp = client.post(path, json=body) if method == "POST" else _dispatch(
                client, method, path
            )
            assert resp.status_code == 307, (
                f"Hub {hub_name} {method} {path} — Plan 03-04 SSO-02 phải 307 "
                f"redirect tới central, got {resp.status_code} body: {resp.text[:200]}"
            )
            location = resp.headers.get("location", "")
            assert location, (
                f"Hub {hub_name} {method} {path} 307 PHẢI có Location header — "
                f"headers: {dict(resp.headers)}"
            )
            # Verify Location trỏ central (CENTRAL_URL set qua hub_app_factory
            # fixture conftest.py). Endpoint path match login hoặc refresh.
            assert "/api/auth/login" in location or "/api/auth/refresh" in location, (
                f"Hub {hub_name} {method} {path} 307 Location KHÔNG trỏ central "
                f"auth endpoint: {location!r}"
            )
            assert "python-api-central" in location, (
                f"Hub {hub_name} {method} {path} 307 Location KHÔNG trỏ central "
                f"service: {location!r}"
            )


def test_404_envelope_shape_hub_strip(hub_app_factory: Any) -> None:
    """Hub yte + GET /api/rag-config → envelope shape verify chi tiết (D-V3-Phase2-E)."""
    app = hub_app_factory("yte")
    with TestClient(app) as client:
        resp = client.get("/api/rag-config")
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}"
        body = resp.json()
        assert body["success"] is False
        assert body["data"] is None
        assert isinstance(body["error"], dict)
        assert "code" in body["error"]
        assert "message" in body["error"]
        # meta key OPTIONAL — ErrorHandlerMiddleware M2 set None hoặc absent
        # tuỳ implementation. KHÔNG hard-assert.


def test_404_envelope_unknown_route_central(hub_app_factory: Any) -> None:
    """Central + path không tồn tại → 404 envelope (verify ErrorHandlerMiddleware wrap mọi 404)."""
    app = hub_app_factory("central")
    with TestClient(app) as client:
        resp = client.get("/api/this-endpoint-does-not-exist")
        assert resp.status_code == 404
        assert _is_envelope_404(resp), (
            f"Central 404 unknown route PHẢI envelope shape — body: {resp.text[:300]}"
        )


# ─── Phase 4 Plan 04-05 (SYNC-03 / D-V3-Phase4-D3) dedicated tests ────────
# Cross-hub aggregated search central-only mount. Hub con strip → 404 envelope
# (FACTOR-02 extend). Public API SearchService.search_cross_hub signature
# KHONG doi — backward compat M2 contract.


@pytest.mark.parametrize("hub_name", ["yte", "duoc", "hcns"])
def test_hub_con_strips_search_cross_hub(
    hub_app_factory: Any, hub_name: str
) -> None:
    """Plan 04-05 SYNC-03 / D-V3-Phase4-D3 — Hub con strip /api/search/cross-hub.

    Hub con (yte/duoc/hcns) KHONG mount cross_hub_router → request → 404
    NOT_FOUND envelope D6 qua Starlette HTTPException handler (Plan 02-03
    carry forward). KHONG dung 403 (leak endpoint existence — FACTOR-02 lock).
    """
    app = hub_app_factory(hub_name)
    with TestClient(app) as client:
        resp = client.post(
            "/api/search/cross-hub",
            json={"query": "test", "top_k": 5},
        )
        assert resp.status_code == 404, (
            f"Hub {hub_name} PHAI strip POST /api/search/cross-hub → 404 "
            f"(FACTOR-02 extend), actual: {resp.status_code} body: {resp.text[:200]}"
        )
        assert _is_envelope_404(resp), (
            f"Hub {hub_name} POST /api/search/cross-hub 404 PHAI envelope shape "
            f"{{success:false, data:null, error:{{code,message}}, meta:null}} — "
            f"actual body: {resp.text[:300]}"
        )


def test_central_mounts_search_cross_hub(hub_app_factory: Any) -> None:
    """Plan 04-05 SYNC-03 — Central giu mount /api/search/cross-hub.

    Central process include search_cross_hub_router (main.py block central-only).
    Endpoint ton tai → response != 404 (200/401/422 acceptable theo auth +
    body validation; KHONG 404 endpoint missing).
    """
    app = hub_app_factory("central")
    with TestClient(app) as client:
        resp = client.post(
            "/api/search/cross-hub",
            json={"query": "test", "top_k": 5},
        )
        assert resp.status_code != 404, (
            f"Central PHAI mount POST /api/search/cross-hub (SYNC-03 D-V3-Phase4-D3), "
            f"actual: {resp.status_code} body: {resp.text[:200]}"
        )


def test_hub_con_mounts_search_local(hub_app_factory: Any) -> None:
    """Plan 04-05 — Hub con van mount POST /api/search (universal router).

    Universal `search_router` mount moi process. Hub con dung local DB
    `medinet_hub_yte` cho local single-hub search (E-V3-3 isolation).
    """
    app = hub_app_factory("yte")
    with TestClient(app) as client:
        resp = client.post(
            "/api/search",
            json={"query": "test", "top_k": 5},
        )
        assert resp.status_code != 404, (
            f"Hub yte PHAI mount POST /api/search (universal — local single-hub), "
            f"actual: {resp.status_code} body: {resp.text[:200]}"
        )


def test_hub_yte_dsn_mismatch_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """HUB_NAME=yte + DSN trỏ /medinet_central → Settings raise ValidationError.

    Phase 1 _enforce_hub_dsn_match validator carry forward — Plan 02-03 verify
    KHÔNG regress (E-V3-3 enforce).
    """
    monkeypatch.setenv("HUB_NAME", "yte")
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql+asyncpg://u:p@localhost:5432/medinet_central"
    )
    monkeypatch.setenv(
        "COCOINDEX_DATABASE_URL",
        "postgresql://u:p@localhost:5432/medinet_cocoindex",
    )
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("COCOINDEX_SKIP_SETUP", "1")
    monkeypatch.setenv("APP_ENV", "dev")

    from app.config import Settings, get_settings

    get_settings.cache_clear()

    with pytest.raises(ValidationError, match="DSN mismatch hub_name"):
        Settings()
