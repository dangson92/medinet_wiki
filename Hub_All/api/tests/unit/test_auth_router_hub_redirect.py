"""Phase 3 SSO-02 — Unit test auth router 307 redirect (Plan 03-04 Task 2).

Verify:
- Hub con POST /api/auth/login → 307 Location: {central_url}/api/auth/login
- Hub con POST /api/auth/refresh → 307 Location: {central_url}/api/auth/refresh
- Hub con POST /api/auth/logout → handle local (KHÔNG 307; 401 vì thiếu Bearer)
- Hub con GET /api/auth/me → handle local (KHÔNG 307; 401 vì thiếu Bearer)
- Central POST /api/auth/login → handle local (KHÔNG 307)

Decision traceability:
- D-V3-Phase3-G LOCKED — Hub con login/refresh 307 Location: central
- D-V3-Phase3-C LOCKED — Hub con KHÔNG sinh refresh (100% refresh ở central)
- D-V3-Phase3-F LOCKED — Frontend redirect form wire defer Phase 5 PROXY-02

Pattern: TestClient(app, follow_redirects=False) — KHÔNG follow tự động (default
TestClient follow → mất 307 status code).
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def _setup_env(monkeypatch: pytest.MonkeyPatch, hub_name: str) -> None:
    """Boot env cho create_app() — pattern Plan 03-02 _setup_env.

    Hub con cần CENTRAL_JWKS_URL + CENTRAL_URL (Plan 03-02/04 validator). Đồng
    thời JWKS_SKIP_FETCH=1 bypass blocking fetch_initial (test KHÔNG verify JWT
    path qua JWKSCache thực — fake URL fetch sẽ fail ConnectError).
    """
    db = "medinet_central" if hub_name == "central" else f"medinet_hub_{hub_name}"
    monkeypatch.setenv("HUB_NAME", hub_name)
    monkeypatch.setenv(
        "DATABASE_URL", f"postgresql+asyncpg://u:p@localhost:5432/{db}"
    )
    monkeypatch.setenv(
        "COCOINDEX_DATABASE_URL",
        "postgresql://u:p@localhost:5432/medinet_cocoindex",
    )
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("COCOINDEX_SKIP_SETUP", "1")
    monkeypatch.setenv("APP_ENV", "dev")
    if hub_name != "central":
        monkeypatch.setenv(
            "CENTRAL_JWKS_URL",
            "http://python-api-central:8080/.well-known/jwks.json",
        )
        monkeypatch.setenv("CENTRAL_URL", "http://python-api-central:8080")
        monkeypatch.setenv("JWKS_SKIP_FETCH", "1")
    from app.config import get_settings

    get_settings.cache_clear()

    # DEF-05-01 carry forward — reset module-global state TRƯỚC khi boot app
    # mới (cùng pattern hub_app_factory integration fixture).
    from app.services.audit_service import reset_queue

    reset_queue()
    from app.db import session as _db_session

    _db_session._engine = None
    _db_session._session_factory = None


@pytest.mark.parametrize("hub_name", ["yte", "duoc", "hcns"])
def test_hub_con_login_returns_307_redirect_to_central(
    monkeypatch: pytest.MonkeyPatch, hub_name: str
) -> None:
    """Hub con POST /api/auth/login → 307 Location: central (D-V3-Phase3-G)."""
    _setup_env(monkeypatch, hub_name)
    from app.main import create_app

    app = create_app()
    with TestClient(app, follow_redirects=False) as client:
        resp = client.post(
            "/api/auth/login",
            json={"email": "u@m.vn", "password": "secret"},
        )
        assert resp.status_code == 307, (
            f"Hub {hub_name} login phải trả 307, got {resp.status_code} "
            f"body: {resp.text[:200]}"
        )
        assert resp.headers["location"] == (
            "http://python-api-central:8080/api/auth/login"
        )
        # SSO redirect reason header (debug + observability)
        assert resp.headers.get("x-sso-redirect-reason") == "hub_con_no_local_login"
        assert resp.headers.get("x-sso-original-hub") == hub_name


@pytest.mark.parametrize("hub_name", ["yte", "duoc", "hcns"])
def test_hub_con_refresh_returns_307_redirect_to_central(
    monkeypatch: pytest.MonkeyPatch, hub_name: str
) -> None:
    """Hub con POST /api/auth/refresh → 307 Location: central (D-V3-Phase3-C/G)."""
    _setup_env(monkeypatch, hub_name)
    from app.main import create_app

    app = create_app()
    with TestClient(app, follow_redirects=False) as client:
        resp = client.post(
            "/api/auth/refresh",
            json={"refresh_token": "dummy.refresh.token"},
        )
        assert resp.status_code == 307, (
            f"Hub {hub_name} refresh phải trả 307, got {resp.status_code} "
            f"body: {resp.text[:200]}"
        )
        assert resp.headers["location"] == (
            "http://python-api-central:8080/api/auth/refresh"
        )
        assert resp.headers.get("x-sso-redirect-reason") == "hub_con_no_local_refresh"
        assert resp.headers.get("x-sso-original-hub") == hub_name


def test_hub_con_logout_handles_local_not_redirected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Hub con POST /api/auth/logout → handle local (KHÔNG 307).

    KHÔNG Authorization header → 401 MISSING_AUTHORIZATION / INVALID_AUTHORIZATION_FORMAT
    (KHÔNG 307 — verify local path qua JWKSCache Plan 03-02 + Redis blacklist
    chung Plan 03-03).
    """
    _setup_env(monkeypatch, "yte")
    from app.main import create_app

    app = create_app()
    with TestClient(app, follow_redirects=False) as client:
        resp = client.post("/api/auth/logout", json={})
        # Logout require Bearer → 401 (KHÔNG 307 — verify local path).
        assert resp.status_code != 307, (
            f"Hub yte logout KHÔNG được redirect (D-V3-Phase3-G clarify), "
            f"got {resp.status_code}"
        )
        assert resp.status_code == 401
        body = resp.json()
        # Logout dependency `get_current_user` chain reject với code
        # MISSING_AUTHORIZATION (chưa Bearer) hoặc INVALID_AUTHORIZATION_FORMAT.
        assert body["error"]["code"] in (
            "MISSING_AUTHORIZATION",
            "INVALID_AUTHORIZATION_FORMAT",
            "INVALID_TOKEN",
            "UNAUTHORIZED",
        ), f"Unexpected error code: {body['error']['code']}"


def test_hub_con_me_handles_local_not_redirected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Hub con GET /api/auth/me → handle local (KHÔNG 307).

    KHÔNG Bearer → 401 (verify local — JWKSCache Plan 03-02 path).
    """
    _setup_env(monkeypatch, "yte")
    from app.main import create_app

    app = create_app()
    with TestClient(app, follow_redirects=False) as client:
        resp = client.get("/api/auth/me")
        assert resp.status_code != 307, (
            f"Hub yte me KHÔNG được redirect, got {resp.status_code}"
        )
        assert resp.status_code == 401
        body = resp.json()
        assert body["error"]["code"] in (
            "MISSING_AUTHORIZATION",
            "INVALID_AUTHORIZATION_FORMAT",
            "INVALID_TOKEN",
            "UNAUTHORIZED",
        )


def test_central_login_still_works_locally(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Central POST /api/auth/login → KHÔNG 307 (handle local M2 path)."""
    _setup_env(monkeypatch, "central")
    from app.main import create_app

    app = create_app()
    with TestClient(app, follow_redirects=False) as client:
        resp = client.post(
            "/api/auth/login",
            json={"email": "u@m.vn", "password": "wrong"},
        )
        # Central handle local → 401 INVALID_CREDENTIALS (KHÔNG có user thật).
        # Acceptable: 401 (user không có) / 422 (validation) / 500 (DB không có)
        # / 503 (lifespan startup chưa wire DB). KHÔNG 307.
        assert resp.status_code != 307, (
            f"Central login KHÔNG được redirect (handle local), "
            f"got {resp.status_code}"
        )
        assert resp.status_code in (401, 422, 500, 503), (
            f"Central login unexpected status: {resp.status_code} body: {resp.text[:200]}"
        )


def test_central_refresh_still_works_locally(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Central POST /api/auth/refresh → KHÔNG 307 (handle local M2 path)."""
    _setup_env(monkeypatch, "central")
    from app.main import create_app

    app = create_app()
    with TestClient(app, follow_redirects=False) as client:
        resp = client.post(
            "/api/auth/refresh",
            json={"refresh_token": "dummy.fake.token"},
        )
        assert resp.status_code != 307, (
            f"Central refresh KHÔNG được redirect, got {resp.status_code}"
        )
        assert resp.status_code in (401, 422, 500, 503)
