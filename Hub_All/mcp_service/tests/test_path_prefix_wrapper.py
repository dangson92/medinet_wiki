"""Test build_asgi_app cho path-prefix deploy (Phase 8.3 add-on).

Khi MCP_PATH_PREFIX non-empty (vd `mcp`), build_asgi_app trả Starlette
wrapper:
- 2 route metadata RFC 8414/9728 ở root với path suffix `/<prefix>`.
- Mount inner FastMCP app dưới `/<prefix>` (transport + OAuth + login).

Khi rỗng, build_asgi_app trả inner trực tiếp (subdomain/authority-root
deploy — behavior gốc Phase 8.3).

Test cover routing structure, KHÔNG cover end-to-end OAuth flow (đã có
test khác cho flow).
"""
from __future__ import annotations

import pytest
from starlette.routing import Mount, Route


@pytest.fixture(autouse=True)
def _reset_singletons():
    """Reset module-level singletons để mỗi test build app sạch."""
    from mcp_app import server

    server._api_client = None
    server._oauth_store = None
    server._oauth_provider = None
    yield
    server._api_client = None
    server._oauth_store = None
    server._oauth_provider = None


def test_path_prefix_empty_returns_inner_directly(monkeypatch) -> None:
    """`MCP_PATH_PREFIX=""` → trả inner Starlette app (subdomain deploy)."""
    monkeypatch.setenv("MCP_PATH_PREFIX", "")
    monkeypatch.setenv("MCP_OAUTH_ISSUER_URL", "http://localhost:8190")
    from mcp_app.config import get_settings

    get_settings.cache_clear()

    from mcp_app import server

    app = server.build_asgi_app()

    # Inner app có route `/mcp` (transport mặc định) + OAuth routes.
    paths = [getattr(r, "path", None) for r in app.routes]
    assert "/mcp" in paths
    # KHÔNG có metadata path-suffixed (subdomain mode).
    assert "/.well-known/oauth-authorization-server" in paths or any(
        "oauth-authorization-server" in str(p) for p in paths
    )


def test_path_prefix_wraps_with_mount_and_metadata_routes(monkeypatch) -> None:
    """`MCP_PATH_PREFIX=mcp` + issuer .../mcp → wrapper với 2 metadata route + Mount."""
    monkeypatch.setenv("MCP_PATH_PREFIX", "mcp")
    monkeypatch.setenv("MCP_OAUTH_ISSUER_URL", "https://wiki.example.com/mcp")
    from mcp_app.config import get_settings

    get_settings.cache_clear()

    from mcp_app import server

    app = server.build_asgi_app()

    # Wrapper là Starlette mới, có 3 route ở top level:
    # 1) /.well-known/oauth-authorization-server/mcp (AS metadata RFC 8414)
    # 2) /.well-known/oauth-protected-resource/mcp   (PR metadata RFC 9728)
    # 3) Mount("/mcp", inner)
    route_specs = []
    for r in app.routes:
        if isinstance(r, Mount):
            route_specs.append(("Mount", r.path))
        elif isinstance(r, Route):
            route_specs.append(("Route", r.path))

    assert ("Route", "/.well-known/oauth-authorization-server/mcp") in route_specs
    assert ("Route", "/.well-known/oauth-protected-resource/mcp") in route_specs
    assert ("Mount", "/mcp") in route_specs


def test_path_prefix_strips_slashes(monkeypatch) -> None:
    """`MCP_PATH_PREFIX=/mcp/` strip về `mcp` (idempotent)."""
    monkeypatch.setenv("MCP_PATH_PREFIX", "/mcp/")
    monkeypatch.setenv("MCP_OAUTH_ISSUER_URL", "https://wiki.example.com/mcp")
    from mcp_app.config import get_settings

    get_settings.cache_clear()

    from mcp_app import server

    app = server.build_asgi_app()

    mount_paths = [r.path for r in app.routes if isinstance(r, Mount)]
    assert "/mcp" in mount_paths
