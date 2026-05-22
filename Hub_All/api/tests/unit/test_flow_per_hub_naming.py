"""Unit test cocoindex flow per-hub App naming — Plan 01-04 TOPO-03.

Verify dynamic App name resolve per `Settings.hub_name`:
    central → medinet_central_ingest
    yte     → medinet_yte_ingest
    duoc    → medinet_duoc_ingest
    hcns    → medinet_hcns_ingest

KHÔNG cần Postgres runtime — chỉ verify resolve helper + module-level App name pattern.

M2 fallback `COCOINDEX_APP_NAME_LEGACY` env override — test riêng cho manual M2
preserve mode (Phase 7 migrate xong remove override).

Lưu ý: cocoindex `ContextKey` register module-level một-lần-trong-process
(`raise ValueError("Context key ... already used")` nếu reload). Các test thay
đổi `HUB_NAME` hoặc `COCOINDEX_APP_NAME_LEGACY` qua subprocess `python -c "..."`
để có module-level fresh import — tránh reload conflict.

Threat coverage:
- T-01-04-01 mitigate (validator + override pattern documented).
- T-01-04-03 mitigate (test fixture `_minimal_env` + `get_settings.cache_clear()`).
- T-01-04-04 mitigate (resolve_cocoindex_app_name validate hub_name input).
- T-01-04-06 mitigate (legacy env override path verified qua subprocess).
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _minimal_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set env vars tối thiểu cho `Settings` load + reset get_settings cache.

    KHÔNG set COCOINDEX_APP_NAME_LEGACY ở default — test legacy override sẽ
    setenv tường minh qua subprocess.
    """
    monkeypatch.setenv("HUB_NAME", "central")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+asyncpg://u:p@localhost:5432/medinet_central",
    )
    monkeypatch.setenv(
        "COCOINDEX_DATABASE_URL",
        "postgresql://u:p@localhost:5432/medinet_cocoindex",
    )
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.delenv("COCOINDEX_APP_NAME_LEGACY", raising=False)

    from app.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _run_subprocess_with_env(extra_env: dict[str, str], script: str) -> str:
    """Run `python -c "<script>"` subprocess kế thừa env hiện tại + override extra.

    Trả về stdout strip. Subprocess cho phép fresh module import — cocoindex
    ContextKey register lại trong process con mà không clash module-level
    process cha.

    Set cwd = `api/` để import app.* work (sys.path).
    """
    env = os.environ.copy()
    env.update(extra_env)
    api_dir = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [sys.executable, "-c", script],
        env=env,
        cwd=str(api_dir),
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(
            f"Subprocess failed (exit={result.returncode}):\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
    return result.stdout.strip()


# ===== Resolve helper deterministic tests (4 hub valid + 1 invalid) =====


@pytest.mark.parametrize(
    "hub,expected",
    [
        ("central", "medinet_central_ingest"),
        ("yte", "medinet_yte_ingest"),
        ("duoc", "medinet_duoc_ingest"),
        ("hcns", "medinet_hcns_ingest"),
    ],
)
def test_resolve_cocoindex_app_name_valid(hub: str, expected: str) -> None:
    """resolve_cocoindex_app_name deterministic cho 4 hub hợp lệ."""
    from app.rag.flow import resolve_cocoindex_app_name

    assert resolve_cocoindex_app_name(hub) == expected


def test_resolve_cocoindex_app_name_invalid_raises() -> None:
    """resolve_cocoindex_app_name raise ValueError voi hub khong hop le."""
    from app.rag.flow import resolve_cocoindex_app_name

    with pytest.raises(ValueError, match="không hợp lệ"):
        resolve_cocoindex_app_name("invalid")


# ===== Module-level App instance smoke check =====


def test_module_app_name_matches_pattern_default_central() -> None:
    """Smoke: module-level cocoindex_app.name match `medinet_<hub>_ingest`.

    Fixture set HUB_NAME=central (default M2 backward-compat) →
    name='medinet_central_ingest'. Import module-level (KHÔNG reload — cocoindex
    ContextKey one-time-register process-level).
    """
    from app.rag.flow import cocoindex_app

    name = getattr(cocoindex_app, "name", None) or getattr(
        cocoindex_app, "_name", ""
    )
    assert name.startswith("medinet_") and name.endswith("_ingest"), (
        f"App name {name!r} không match pattern medinet_<hub>_ingest"
    )
    # Default hub_name='central' → expect medinet_central_ingest
    assert name == "medinet_central_ingest", (
        f"Default HUB_NAME=central kỳ vọng 'medinet_central_ingest', got {name!r}"
    )


# ===== Subprocess-based tests for per-hub + legacy override =====


def test_module_app_name_per_hub_yte_subprocess() -> None:
    """Set HUB_NAME=yte qua subprocess → cocoindex_app.name = 'medinet_yte_ingest'.

    Subprocess cần thiết vì cocoindex ContextKey one-time-register process-level —
    reload trong cùng process raise `Context key ... already used`.
    """
    script = (
        "from app.rag.flow import cocoindex_app; "
        "n = getattr(cocoindex_app, 'name', None) or getattr(cocoindex_app, '_name', ''); "
        "print(n)"
    )
    name = _run_subprocess_with_env(
        {
            "HUB_NAME": "yte",
            "DATABASE_URL": "postgresql+asyncpg://u:p@localhost:5432/medinet_hub_yte",
            "COCOINDEX_DATABASE_URL": "postgresql://u:p@localhost:5432/medinet_cocoindex",
            "REDIS_URL": "redis://localhost:6379/0",
            # Plan 03-02 Task 1 — validator hub con required CENTRAL_JWKS_URL.
            "CENTRAL_JWKS_URL": "http://python-api-central:8080/.well-known/jwks.json",
            # Plan 03-04 Task 1 — validator hub con required CENTRAL_URL.
            "CENTRAL_URL": "http://python-api-central:8080",
            # Plan 04-02 Task 1 — validator hub con required HUB_ID + CENTRAL_SYNC_DSN.
            "HUB_ID": "12345678-1234-1234-1234-123456789012",
            "CENTRAL_SYNC_DSN": "postgresql+asyncpg://sync_user:pwd@postgres:5432/medinet_central",
        },
        script,
    )
    assert name == "medinet_yte_ingest", (
        f"HUB_NAME=yte kỳ vọng 'medinet_yte_ingest', got {name!r}"
    )


def test_legacy_env_override_preserves_m2_name_subprocess() -> None:
    """COCOINDEX_APP_NAME_LEGACY env set → app name = legacy (override hub resolve).

    Manual fallback: user CHỦ Ý preserve M2 corpus cocoindex state (App name
    `medinet_wiki_ingest` được index by name). Phase 7 migrate xong remove env.
    """
    script = (
        "from app.rag.flow import cocoindex_app; "
        "n = getattr(cocoindex_app, 'name', None) or getattr(cocoindex_app, '_name', ''); "
        "print(n)"
    )
    name = _run_subprocess_with_env(
        {
            "HUB_NAME": "central",
            "DATABASE_URL": "postgresql+asyncpg://u:p@localhost:5432/medinet_central",
            "COCOINDEX_DATABASE_URL": "postgresql://u:p@localhost:5432/medinet_cocoindex",
            "REDIS_URL": "redis://localhost:6379/0",
            "COCOINDEX_APP_NAME_LEGACY": "medinet_wiki_ingest",
        },
        script,
    )
    assert name == "medinet_wiki_ingest", (
        f"COCOINDEX_APP_NAME_LEGACY override kỳ vọng 'medinet_wiki_ingest', got {name!r}"
    )


def test_legacy_env_empty_falls_back_to_resolve_subprocess() -> None:
    """COCOINDEX_APP_NAME_LEGACY="" (empty) → fall back resolve_cocoindex_app_name.

    Empty string truthy check fail → KHÔNG override, dùng dynamic resolve theo
    HUB_NAME (central default → medinet_central_ingest).
    """
    script = (
        "from app.rag.flow import cocoindex_app; "
        "n = getattr(cocoindex_app, 'name', None) or getattr(cocoindex_app, '_name', ''); "
        "print(n)"
    )
    name = _run_subprocess_with_env(
        {
            "HUB_NAME": "central",
            "DATABASE_URL": "postgresql+asyncpg://u:p@localhost:5432/medinet_central",
            "COCOINDEX_DATABASE_URL": "postgresql://u:p@localhost:5432/medinet_cocoindex",
            "REDIS_URL": "redis://localhost:6379/0",
            "COCOINDEX_APP_NAME_LEGACY": "",
        },
        script,
    )
    assert name == "medinet_central_ingest", (
        f"Empty legacy env phải fall back resolve, got {name!r}"
    )
