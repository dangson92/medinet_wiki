"""Phase 3 SSO-02/03/04 — Integration test E4 reinforced cross-hub JWT
(Plan 03-03 Task 4).

Pragmatic scope (KHÔNG spawn 2 process subprocess thật):
- Stale JWT hub_ids=['duoc'] post tới endpoint hub_yte → 403 CROSS_HUB_ACCESS_DENIED
  (verify dependency get_current_user_for_hub_access wire vào test endpoint mock).
- Matching JWT hub_ids=['yte'] post tới hub_yte → KHÔNG 403 (accept path).
- Central bypass HUB_NAME check — JWT hub_ids=['yte'] post tới central → KHÔNG 403.

Full multi-process E2E `docker compose up python-api-central python-api-yte` +
curl matrix defer Plan 03-05 closeout smoke checkpoint.

Tracing: SSO-02 (Redis blacklist key cross-process) + SSO-03 (hub_ids claim) +
SSO-04 (E4 reinforced 3-layer enforce) + D-V3-Phase3-E + D-V3-Phase3-H.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import jwt as pyjwt
import pytest
from fastapi import APIRouter, Depends
from fastapi.testclient import TestClient


@pytest.fixture
def public_pem() -> bytes:
    p = Path("keys/public.pem")
    if not p.exists():
        pytest.skip("api/keys/public.pem missing — run 'make keys'")
    return p.read_bytes()


@pytest.fixture
def private_pem() -> bytes:
    p = Path("keys/private.pem")
    if not p.exists():
        pytest.skip("api/keys/private.pem missing — run 'make keys'")
    return p.read_bytes()


def _build_jwt(
    *,
    private_pem: bytes,
    public_pem: bytes,
    hub_ids: list[str],
    sub: str = "11111111-1111-1111-1111-111111111111",  # UUID format required
    email: str = "user@medinet.vn",
    role: str = "viewer",
) -> str:
    """Build JWT signed bằng central private key — match shape Plan 03-03.

    `sub` mặc định UUID hợp lệ để get_current_user đi tới step DB lookup
    (UUID(claims.sub) KHÔNG raise ValueError). User KHÔNG tồn tại DB → 401
    USER_DISABLED — acceptable cho test scope verify dependency chain.

    Note thứ tự dependency: get_current_user_for_hub_access depends
    get_current_user. FastAPI resolve theo thứ tự — nếu get_current_user
    raise (vd 401 USER_DISABLED do user không có DB), dep mới KHÔNG run.
    → test cần thứ tự: stale JWT hub_ids check ở Layer 3 dependency phải
    raise 403 TRƯỚC khi get_current_user chạy xong load user. Nhưng FastAPI
    Depends chain là LINEAR — get_current_user MUST complete trước. Test phải
    accept rằng nếu user không tồn tại DB → 401 trước E4 check chạy.

    Workaround Plan 03-03: hub yte stale JWT test cần inject user mock vào DB
    HOẶC override get_current_user dependency với mock trả user object trực tiếp.
    Plan 03-03 chọn approach #2 (override dep) — clean hơn, không cần DB.
    """
    from app.auth.jwks import _derive_kid
    from app.auth.jwt import JWT_ALGORITHM, JWT_AUDIENCE, JWT_ISSUER

    kid = _derive_kid(public_pem)
    now = datetime.now(tz=UTC)
    return pyjwt.encode(
        {
            "sub": sub,
            "email": email,
            "name": "Test User",
            "role": role,
            "hub_ids": hub_ids,
            "iss": JWT_ISSUER,
            "aud": [JWT_AUDIENCE],
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=15)).timestamp()),
            "jti": "jti_test_integration",
            "token_type": "access",
        },
        private_pem,
        algorithm=JWT_ALGORITHM,
        headers={"kid": kid},
    )


def _make_test_endpoint_app(app: Any, *, jwt_claims: Any) -> Any:
    """Mount test endpoint /api/test/hub-access lên app + override get_current_user.

    Pattern: override `get_current_user` qua `app.dependency_overrides` để trả
    MagicMock user (KHÔNG đi qua JWKS+DB+Redis chain). Cũng wire jwt_claims
    vào request.state qua middleware. MỤC ĐÍCH: cô lập test E4 dependency
    chain — chỉ verify Layer 3 hub_ids enforcement trong
    get_current_user_for_hub_access.

    Pattern này tương đương E2E test với mock layer — pragmatic cho integration
    scope Plan 03-03 (full multi-process docker compose smoke defer Plan 03-05).
    """
    from unittest.mock import MagicMock

    from app.auth.dependencies import (
        get_current_user,
        get_current_user_for_hub_access,
    )

    async def _mock_get_current_user() -> Any:
        # KHÔNG cần Request param ở đây — state.jwt_claims wire qua middleware.
        # Mock user.id phải là UUID hợp lệ cho str(uuid) trong endpoint response.
        user = MagicMock()
        user.id = "11111111-1111-1111-1111-111111111111"
        return user

    app.dependency_overrides[get_current_user] = _mock_get_current_user

    # Middleware wire jwt_claims vào request.state — pattern tương đương việc
    # get_current_user thật set state SAU verify pass.
    @app.middleware("http")  # type: ignore[untyped-decorator]
    async def _inject_jwt_claims(request: Any, call_next: Any) -> Any:
        request.state.jwt_claims = jwt_claims
        return await call_next(request)

    test_router = APIRouter()

    @test_router.get("/api/test/hub-access")
    async def _hub_access_check(
        user: Any = Depends(get_current_user_for_hub_access),  # noqa: B008
    ) -> dict[str, str]:
        return {"user_id": str(getattr(user, "id", "unknown"))}

    app.include_router(test_router)
    return app


@pytest.mark.critical
@pytest.mark.integration
def test_stale_jwt_cross_hub_returns_403_envelope(
    hub_app_factory: Any, private_pem: bytes, public_pem: bytes
) -> None:
    """SSO-04 E4 reinforced — stale JWT hub_ids=['duoc'] post tới hub yte → 403.

    Giả lập claims object với hub_ids=['duoc'] (stale cross-hub) inject vào
    request.state qua override get_current_user. Verify Layer 3 dependency
    get_current_user_for_hub_access raise 403 CROSS_HUB_ACCESS_DENIED envelope.

    Token JWT thật build kèm để test full HTTP request shape (Bearer header
    + auth flow surface). Token KHÔNG được verify vì override bypass — pattern
    pragmatic cô lập E4 logic khỏi JWKS/DB/Redis chain.
    """
    from unittest.mock import MagicMock

    stale_token = _build_jwt(
        private_pem=private_pem,
        public_pem=public_pem,
        hub_ids=["duoc"],
    )

    yte_app = hub_app_factory("yte")
    stale_claims = MagicMock()
    stale_claims.hub_ids = ["duoc"]  # NOT IN ["yte"] → 403
    _make_test_endpoint_app(yte_app, jwt_claims=stale_claims)

    with TestClient(yte_app) as client:
        resp = client.get(
            "/api/test/hub-access",
            headers={"Authorization": f"Bearer {stale_token}"},
        )
        assert resp.status_code == 403, (
            f"Stale JWT hub_ids=['duoc'] post tới hub yte → expect 403, "
            f"got {resp.status_code} body={resp.json()}"
        )
        body = resp.json()
        assert body["success"] is False
        assert body["error"]["code"] == "CROSS_HUB_ACCESS_DENIED"
        # Message phải reveal hub mismatch (helpful — KHÔNG leak data)
        assert "yte" in body["error"]["message"]


@pytest.mark.critical
@pytest.mark.integration
def test_matching_jwt_hub_accepts(
    hub_app_factory: Any, private_pem: bytes, public_pem: bytes
) -> None:
    """SSO-03 — JWT hub_ids chứa hub_name → dependency KHÔNG raise 403.

    Override get_current_user bypass JWKS+DB. Test endpoint reach 200 với
    mock user trả về (user.id UUID hợp lệ).
    """
    from unittest.mock import MagicMock

    valid_token = _build_jwt(
        private_pem=private_pem,
        public_pem=public_pem,
        hub_ids=["yte"],
    )

    yte_app = hub_app_factory("yte")
    valid_claims = MagicMock()
    valid_claims.hub_ids = ["yte"]  # IN ["yte"] → accept
    _make_test_endpoint_app(yte_app, jwt_claims=valid_claims)

    with TestClient(yte_app) as client:
        resp = client.get(
            "/api/test/hub-access",
            headers={"Authorization": f"Bearer {valid_token}"},
        )
        # Layer 3 dependency hub access check pass — KHÔNG 403.
        assert resp.status_code != 403, (
            f"Matching hub JWT KHÔNG được trả 403, "
            f"got {resp.status_code} body={resp.json()}"
        )
        # Override get_current_user bypass DB → endpoint return 200.
        assert resp.status_code == 200, (
            f"Expect 200 sau khi pass Layer 3 check, got {resp.status_code} "
            f"body={resp.json()}"
        )


@pytest.mark.critical
@pytest.mark.integration
def test_central_bypass_hub_access_check_integration(
    hub_app_factory: Any, private_pem: bytes, public_pem: bytes
) -> None:
    """SSO-04 — Central bypass HUB_NAME check (cross-hub by design).

    JWT hub_ids=['yte'] post tới central → dependency get_current_user_for_hub_access
    bypass check (central is cross-hub) → KHÔNG raise 403.
    """
    from unittest.mock import MagicMock

    token = _build_jwt(
        private_pem=private_pem,
        public_pem=public_pem,
        hub_ids=["yte"],  # only yte, but central bypass
        email="admin@medinet.vn",
        role="admin",
    )

    central_app = hub_app_factory("central")
    central_claims = MagicMock()
    central_claims.hub_ids = ["yte"]  # only yte but central bypass anyway
    _make_test_endpoint_app(central_app, jwt_claims=central_claims)

    with TestClient(central_app) as client:
        resp = client.get(
            "/api/test/hub-access",
            headers={"Authorization": f"Bearer {token}"},
        )
        # Central bypass — KHÔNG trả 403 CROSS_HUB_ACCESS_DENIED.
        assert resp.status_code != 403, (
            f"Central bypass HUB_NAME check failed, got 403 "
            f"body={resp.json()}"
        )
        assert resp.status_code == 200, (
            f"Expect 200 sau khi pass central bypass, got {resp.status_code} "
            f"body={resp.json()}"
        )
