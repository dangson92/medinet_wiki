"""Unit test hub isolation helper — Plan 05-02 Task 1 (HUB-02, EXIT criteria E4).

Pure-Python logic test — KHÔNG cần Postgres/Redis. Phủ `hub_filter_clause`
(WHERE-clause builder) + `verify_hub_access` (cross-hub guard).

Threat coverage:
- T-05-02-01 — editor truyền payload hub_id giả → verify_hub_access reject.
- T-05-02-02 — hub_ids rỗng → clause luôn-false (KHÔNG leak mọi row).
- T-05-02-03 — admin bypass hub filter (theo thiết kế cross-hub).
"""
from __future__ import annotations

import pytest

from app.repositories.hub_isolation import (
    HubIsolationError,
    hub_filter_clause,
    verify_hub_access,
)


class TestHubFilterClause:
    """hub_filter_clause — sinh SQL fragment WHERE hub_id IN (...)."""

    def test_admin_bypass_returns_empty_clause(self) -> None:
        """admin → ('', {}) — admin quản trị cross-hub, query KHÔNG thêm WHERE."""
        clause, params = hub_filter_clause(role="admin", hub_ids=["a", "b"])
        assert clause == ""
        assert params == {}

    def test_admin_bypass_even_with_empty_hub_ids(self) -> None:
        """admin với hub_ids rỗng vẫn bypass — admin không cần assignment."""
        assert hub_filter_clause(role="admin", hub_ids=[]) == ("", {})

    def test_editor_with_hubs_builds_in_clause(self) -> None:
        """editor có hub → 'hub_id IN (:uh0, :uh1)' + params map."""
        clause, params = hub_filter_clause(role="editor", hub_ids=["a", "b"])
        assert clause == "hub_id IN (:uh0, :uh1)"
        assert params == {"uh0": "a", "uh1": "b"}

    def test_editor_single_hub(self) -> None:
        """editor 1 hub → 1 placeholder."""
        clause, params = hub_filter_clause(role="editor", hub_ids=["x"])
        assert clause == "hub_id IN (:uh0)"
        assert params == {"uh0": "x"}

    def test_empty_hub_ids_returns_always_false_clause(self) -> None:
        """T-05-02-02 — editor chưa assign hub → 'hub_id IN (NULL)' (0 row)."""
        clause, params = hub_filter_clause(role="editor", hub_ids=[])
        assert "NULL" in clause
        assert params == {}

    def test_viewer_empty_hub_ids_also_false(self) -> None:
        """viewer chưa assign hub cũng phải thấy 0 row (KHÔNG leak)."""
        clause, _ = hub_filter_clause(role="viewer", hub_ids=[])
        assert "NULL" in clause

    def test_custom_param_prefix(self) -> None:
        """param_prefix tùy biến để tránh đụng tên param khác trong query."""
        clause, params = hub_filter_clause(
            role="editor", hub_ids=["a"], param_prefix="hubp"
        )
        assert clause == "hub_id IN (:hubp0)"
        assert params == {"hubp0": "a"}


class TestVerifyHubAccess:
    """verify_hub_access — raise HubIsolationError khi cross-hub."""

    def test_admin_passes_any_hub(self) -> None:
        """admin bypass — pass kể cả hub không trong assignment."""
        assert (
            verify_hub_access(
                role="admin", user_hub_ids=[], resource_hub_id="z"
            )
            is None
        )

    def test_editor_access_own_hub_passes(self) -> None:
        """editor truy cập hub thuộc assignment → pass."""
        assert (
            verify_hub_access(
                role="editor", user_hub_ids=["a", "b"], resource_hub_id="a"
            )
            is None
        )

    def test_editor_cross_hub_raises(self) -> None:
        """T-05-02-01 — editor hub A truy cập resource hub B → raise."""
        with pytest.raises(HubIsolationError) as exc_info:
            verify_hub_access(
                role="editor", user_hub_ids=["a"], resource_hub_id="b"
            )
        assert exc_info.value.resource_hub_id == "b"

    def test_viewer_cross_hub_raises(self) -> None:
        """viewer cũng bị enforce isolation y hệt editor."""
        with pytest.raises(HubIsolationError):
            verify_hub_access(
                role="viewer", user_hub_ids=["a"], resource_hub_id="b"
            )

    def test_editor_no_hub_raises(self) -> None:
        """editor chưa assign hub → bất kỳ resource đều reject."""
        with pytest.raises(HubIsolationError):
            verify_hub_access(
                role="editor", user_hub_ids=[], resource_hub_id="a"
            )

    def test_hub_isolation_error_carries_resource_hub_id(self) -> None:
        """HubIsolationError lưu resource_hub_id cho audit payload."""
        err = HubIsolationError("test", resource_hub_id="hub-x")
        assert err.resource_hub_id == "hub-x"
        assert "test" in str(err)

    def test_hub_isolation_error_default_resource_hub_id_none(self) -> None:
        """resource_hub_id optional — default None."""
        err = HubIsolationError("no id")
        assert err.resource_hub_id is None
