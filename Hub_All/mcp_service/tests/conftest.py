"""Fixture chung cho test MCP Service — Phase 8.2 Plan 05 + Phase 8.3 Plan 01/03.

Cung cấp:
- `mock_ctx`     — factory tạo `ctx` MCP giả với (hoặc không có) header X-API-Key.
- `mock_ctx_oauth` — (Phase 8.3 Plan 03) factory tạo `ctx` MCP giả với header
  `Authorization: Bearer <token>` thay X-API-Key.
- `reset_api_client` — autouse, reset singleton `_api_client` của server trước/sau
  mỗi test để base_url không leak giữa các test.
- `api_base_url` — base URL dùng cho respx mock + override config qua env MCP_API_BASE_URL.
- `oauth_store`  — (Phase 8.3) OAuthStore tạm trên SQLite :memory:, schema sẵn sàng.
- `fake_pending_authorize` — (Phase 8.3) helper seed bản ghi oauth_pending cho Plan 02/03.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

# Base URL giả dùng xuyên suốt test tích hợp — respx route khớp theo URL này.
_API_BASE_URL = "http://testserver-api"


@pytest.fixture
def mock_ctx():
    """Factory tạo `ctx` MCP giả.

    Trả về hàm `_make(api_key=...)`:
    - `api_key` là chuỗi → `ctx.request_context.request.headers` là dict thật
      `{"x-api-key": api_key}` → `extract_api_key` đọc được key.
    - `api_key is None` → headers là dict rỗng `{}` → `extract_api_key` trả `None`
      → tool raise ToolError MCP_UNAUTHORIZED.

    Dùng dict thật (không MagicMock) cho `headers` để `.get("x-api-key")` trả
    đúng giá trị/None — MagicMock sẽ trả Mock object cho mọi `.get(...)`.
    """

    def _make(api_key: str | None = "test-key-123") -> MagicMock:
        ctx = MagicMock()
        headers: dict[str, str] = {"x-api-key": api_key} if api_key is not None else {}
        ctx.request_context.request.headers = headers
        return ctx

    return _make


@pytest.fixture
def mock_ctx_oauth():
    """Factory tạo `ctx` MCP giả mang header `Authorization: Bearer <token>`.

    Biến thể của `mock_ctx` cho client OAuth (Phase 8.3 Plan 03):
    - `token` là chuỗi → headers `{"authorization": "Bearer <token>"}` →
      `extract_oauth_token` đọc được token.
    - `token is None` → headers rỗng `{}` → cả X-API-Key lẫn OAuth đều thiếu.
    """

    def _make(token: str | None = "oauth-token-test") -> MagicMock:
        ctx = MagicMock()
        headers: dict[str, str] = (
            {"authorization": f"Bearer {token}"} if token is not None else {}
        )
        ctx.request_context.request.headers = headers
        return ctx

    return _make


@pytest.fixture(autouse=True)
def reset_api_client(monkeypatch: pytest.MonkeyPatch):
    """Reset singleton của server (ApiClient + OAuth store/provider) mỗi test.

    `mcp_app.server._api_client` / `_oauth_store` / `_oauth_provider` là singleton
    lazy-init. Nếu không reset, base_url / DB path của test trước leak sang test
    sau. Đặt `None` để `_get_*()` tạo instance mới từ config (đã bị override).

    Thêm: ép `MCP_PATH_PREFIX=""` mặc định mọi test — chống `.env` file ở
    project root (deploy env path-based) leak vào test, làm app wrap dưới
    Mount khiến route root như `/login` trả 404. Test nào cần path-prefix
    mode phải explicit `monkeypatch.setenv("MCP_PATH_PREFIX", "mcp")`.
    """
    import mcp_app.server as server
    from mcp_app.config import get_settings

    monkeypatch.setenv("MCP_PATH_PREFIX", "")
    # Đồng thời ép MCP_OAUTH_INTERNAL_TOKEN="" mặc định — chống `.env` deploy
    # (có shared secret) leak vào test khiến provider gọi API internal khi
    # complete_authorization → respx mock chưa setup endpoint → fail.
    # Test cần per-user bind explicit set env này + mock route.
    monkeypatch.setenv("MCP_OAUTH_INTERNAL_TOKEN", "")
    get_settings.cache_clear()
    server._api_client = None
    server._oauth_store = None
    server._oauth_provider = None
    yield
    server._api_client = None
    server._oauth_store = None
    server._oauth_provider = None


@pytest.fixture
def api_base_url(monkeypatch: pytest.MonkeyPatch) -> str:
    """Base URL API Service giả + override config để ApiClient dùng đúng URL.

    Set env `MCP_API_BASE_URL` và xoá cache `get_settings` (lru_cache) để
    `_get_client()` khởi tạo ApiClient với base_url khớp respx mock.
    """
    from mcp_app.config import get_settings

    monkeypatch.setenv("MCP_API_BASE_URL", _API_BASE_URL)
    get_settings.cache_clear()
    yield _API_BASE_URL
    get_settings.cache_clear()


@pytest.fixture
async def oauth_store():
    """OAuthStore tạm trên SQLite :memory: — schema khởi tạo sẵn.

    OAuthStore giữ một connection mở sau init_schema() → :memory: hoạt động
    (DB sống cùng connection). Đóng store ở teardown.
    """
    from mcp_app.oauth.store import OAuthStore

    store = OAuthStore(db_path=":memory:")
    await store.init_schema()
    yield store
    await store.aclose()


async def fake_pending_authorize(
    store,
    *,
    txn: str = "txn-test",
    client_id: str = "client-test",
    redirect_uri: str = "https://claude.ai/api/mcp/auth_callback",
    code_challenge: str = "challenge-test",
    code_challenge_method: str = "S256",
    csrf_token: str = "csrf-test-fixed",  # HIGH-09 — helper test default
    client_state: str | None = "client-state-test",
    scopes: list[str] | None = None,
    created_at: int | None = None,
) -> str:
    """Seed 1 bản ghi oauth_pending để test login callback nối lại flow.

    Trả về `txn` đã seed. csrf_token mặc định `"csrf-test-fixed"` — test mới
    HIGH-09 truyền tường minh giá trị khác để test verify mismatch.
    """
    import time

    await store.save_pending(
        txn=txn,
        client_id=client_id,
        redirect_uri=redirect_uri,
        code_challenge=code_challenge,
        code_challenge_method=code_challenge_method,
        csrf_token=csrf_token,
        client_state=client_state,
        scopes=scopes or ["wiki"],
        created_at=created_at if created_at is not None else int(time.time()),
    )
    return txn
