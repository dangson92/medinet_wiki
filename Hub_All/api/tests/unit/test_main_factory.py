"""Phase 2 FACTOR-01/02 — Unit test create_app() factory với 4 hub mode.

Verify conditional router mount đúng theo settings.hub_name:
- central: 7 universal + 9 central-only = 16 router (auth từ app.auth + 15 từ routers)
- yte/duoc/hcns: 7 universal CHỈ — 9 central-only strip (FACTOR-02)

Test KHÔNG cần Docker/testcontainers (unit-level — không hit lifespan
startup actually). FastAPI route registration ở module-import time qua
include_router → check app.routes list-as-is sau create_app() đủ.

Set COCOINDEX_SKIP_SETUP=1 để bypass cocoindex Environment singleton
(DEF-05-01 pattern M2 — Phase 4 test mode escape hatch).

Plan 02-01 Task 2.
"""
from __future__ import annotations

import logging
from collections.abc import Iterator

import pytest
from pydantic import ValidationError

# Path prefix expected mount cho từng hub mode (verify qua app.routes)
UNIVERSAL_PREFIXES = [
    "/api/auth",       # auth_router
    "/api/documents",  # documents_router
    "/api/profile",    # profile_router
    "/api/search",     # search_router
    "/api/ask",        # ask_router
    "/api/usage",      # usage_router
    "/api/ai/chat",    # ai_chat_router (note: prefix /api/ai/chat — không phải /api/ai)
]

CENTRAL_ONLY_PREFIXES = [
    "/api/rag-config",       # rag_config_router
    "/api/hubs",             # hubs_router
    "/api/users",            # users_router
    "/api/api-keys",         # api_keys_router
    "/api/audit-logs",       # audit_logs_router
    "/api/system-settings",  # system_settings_router
    "/api/sync",             # sync_router
    "/api/mcp",              # mcp_oauth_router (prefix /api/mcp/...)
    "/api/internal/mcp",     # mcp_oauth_internal_router
]


def _setup_env(monkeypatch: pytest.MonkeyPatch, hub_name: str) -> None:
    """Set env vars chuẩn cho create_app() boot theo hub mode.

    DSN suffix phải khớp hub_name (Settings._enforce_hub_dsn_match — Phase 1).
    """
    if hub_name == "central":
        db = "medinet_central"
    else:
        db = f"medinet_hub_{hub_name}"
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
    # Plan 03-02 Task 1 — validator hub con required CENTRAL_JWKS_URL.
    # Auto-set cho hub con để boot Settings PASS (regression update).
    # Plan 03-04 Task 1 — validator hub con required CENTRAL_URL. Cùng pattern.
    if hub_name != "central":
        monkeypatch.setenv(
            "CENTRAL_JWKS_URL",
            "http://python-api-central:8080/.well-known/jwks.json",
        )
        monkeypatch.setenv("CENTRAL_URL", "http://python-api-central:8080")
    # Force re-parse env mỗi test (lru_cache singleton)
    from app.config import get_settings

    get_settings.cache_clear()


def _route_paths(app: object) -> list[str]:
    """Trả danh sách path str từ app.routes (only có .path attr — Mount/Route)."""
    paths: list[str] = []
    for route in app.routes:  # type: ignore[attr-defined]
        path = getattr(route, "path", None)
        if isinstance(path, str):
            paths.append(path)
    return paths


def _has_prefix(paths: list[str], prefix: str) -> bool:
    """True nếu có ít nhất 1 path bắt đầu prefix."""
    return any(p.startswith(prefix) for p in paths)


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> Iterator[None]:
    from app.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_factory_central_mounts_all_routers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """HUB_NAME=central → mount cả 7 universal + 9 central-only."""
    _setup_env(monkeypatch, "central")
    from app.main import create_app

    app = create_app()
    paths = _route_paths(app)

    for prefix in UNIVERSAL_PREFIXES:
        assert _has_prefix(paths, prefix), (
            f"Universal router {prefix!r} PHẢI mount khi hub_name=central"
        )
    for prefix in CENTRAL_ONLY_PREFIXES:
        assert _has_prefix(paths, prefix), (
            f"Central-only router {prefix!r} PHẢI mount khi hub_name=central"
        )


@pytest.mark.parametrize("hub_name", ["yte", "duoc", "hcns"])
def test_factory_hub_strips_central_only(
    monkeypatch: pytest.MonkeyPatch, hub_name: str
) -> None:
    """HUB_NAME=yte|duoc|hcns → strip 9 central-only, giữ 7 universal."""
    _setup_env(monkeypatch, hub_name)
    from app.main import create_app

    app = create_app()
    paths = _route_paths(app)

    # 7 universal PHẢI có
    for prefix in UNIVERSAL_PREFIXES:
        assert _has_prefix(paths, prefix), (
            f"Universal router {prefix!r} PHẢI mount khi hub_name={hub_name}"
        )

    # 9 central-only PHẢI KHÔNG có
    for prefix in CENTRAL_ONLY_PREFIXES:
        assert not _has_prefix(paths, prefix), (
            f"Central-only router {prefix!r} PHẢI strip khi hub_name={hub_name} "
            f"— FACTOR-02 enforce"
        )


def test_factory_yte_strips_central_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Explicit yte test — alias cho parametrize trên (test name traceability)."""
    _setup_env(monkeypatch, "yte")
    from app.main import create_app

    app = create_app()
    paths = _route_paths(app)
    assert not _has_prefix(paths, "/api/rag-config"), (
        "/api/rag-config PHẢI strip ở hub yte — FACTOR-02"
    )
    assert _has_prefix(paths, "/api/auth"), (
        "/api/auth PHẢI mount ở hub yte — FACTOR-03"
    )


def test_factory_duoc_strips_central_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Explicit duoc test."""
    _setup_env(monkeypatch, "duoc")
    from app.main import create_app

    app = create_app()
    paths = _route_paths(app)
    assert not _has_prefix(paths, "/api/hubs"), (
        "/api/hubs PHẢI strip ở hub duoc — FACTOR-02"
    )


def test_factory_hcns_strips_central_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Explicit hcns test."""
    _setup_env(monkeypatch, "hcns")
    from app.main import create_app

    app = create_app()
    paths = _route_paths(app)
    assert not _has_prefix(paths, "/api/users"), (
        "/api/users PHẢI strip ở hub hcns — FACTOR-02"
    )


def test_factory_yte_logs_central_only_skip(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """HUB_NAME=yte → logger.info emit central_only_routers_skipped với hub_name=yte."""
    _setup_env(monkeypatch, "yte")
    with caplog.at_level(logging.INFO, logger="app.main"):
        from app.main import create_app

        create_app()

    matches = [
        rec.getMessage()
        for rec in caplog.records
        if "central_only_routers_skipped" in rec.getMessage()
    ]
    assert matches, "Phải log central_only_routers_skipped khi hub_name=yte"
    assert any("hub_name=yte" in m for m in matches), (
        f"Log phải chứa 'hub_name=yte', got: {matches!r}"
    )


def test_factory_hub_name_mismatch_dsn_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """HUB_NAME=yte + DSN trỏ medinet_central → Settings raise ValidationError.

    Phase 1 _enforce_hub_dsn_match validator carry forward — Plan 02-01 KHÔNG regress.
    """
    monkeypatch.setenv("HUB_NAME", "yte")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+asyncpg://u:p@localhost:5432/medinet_central",
    )
    monkeypatch.setenv(
        "COCOINDEX_DATABASE_URL",
        "postgresql://u:p@localhost:5432/medinet_cocoindex",
    )
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("COCOINDEX_SKIP_SETUP", "1")

    from app.config import Settings, get_settings

    get_settings.cache_clear()

    with pytest.raises(ValidationError, match="DSN mismatch hub_name"):
        Settings()
