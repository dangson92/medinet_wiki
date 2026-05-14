"""Unit test require_role guard — Plan 03-05 (AUTH-04).

Pure Python test, KHÔNG cần Postgres/Redis. Verify:
- Gate ValueError khi gọi `require_role()` không argument (an toàn — tránh
  khai báo route mở cho mọi role).
- Return callable cho 1 role hoặc multi-role.
"""
from __future__ import annotations

import pytest

from app.auth import require_role


def test_require_role_raises_value_error_on_empty_roles() -> None:
    """Empty *roles → ValueError với message Vietnamese."""
    with pytest.raises(ValueError, match="ít nhất 1 role"):
        require_role()


def test_require_role_returns_callable_with_single_role() -> None:
    """require_role('admin') → return Callable không raise."""
    dep = require_role("admin")
    assert callable(dep)


def test_require_role_returns_callable_with_multiple_roles() -> None:
    """require_role('admin', 'editor') → return Callable cho multi-role."""
    dep = require_role("admin", "editor")
    assert callable(dep)


def test_require_role_returns_callable_with_three_roles() -> None:
    """require_role('admin', 'editor', 'viewer') → 3 role allowed."""
    dep = require_role("admin", "editor", "viewer")
    assert callable(dep)


def test_require_role_different_calls_return_different_callables() -> None:
    """Mỗi call tạo Callable instance riêng — KHÔNG share closure state."""
    dep_admin = require_role("admin")
    dep_editor = require_role("editor")
    assert dep_admin is not dep_editor
