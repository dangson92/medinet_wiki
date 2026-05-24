"""Unit test build_audit_payload — Phase 2 Plan 02-04 DEP-05 D-V3.1-Phase2-C LOCKED.

Pure Python test — KHÔNG cần Postgres/Redis. Verify shape dict output cho 4 case.
"""
from __future__ import annotations

from app.services.audit_service import build_audit_payload


def test_super_admin_nests_actor_role_admin_and_null_hub() -> None:
    """Case 1: super admin → actor_role='admin' + actor_hub_id=None + extra merged."""
    result = build_audit_payload(
        actor_role="admin",
        actor_hub_id=None,
        extra={"email": "x@y.com", "role": "viewer"},
    )
    assert result["actor_role"] == "admin"
    assert result["actor_hub_id"] is None
    assert result["email"] == "x@y.com"
    assert result["role"] == "viewer"
    assert len(result) == 4


def test_hub_admin_nests_actor_role_hub_admin_and_hub_id() -> None:
    """Case 2: hub_admin → actor_role='hub_admin' + actor_hub_id=<uuid> + extra."""
    hub_id = "dmd-uuid-12345"
    result = build_audit_payload(
        actor_role="hub_admin",
        actor_hub_id=hub_id,
        extra={"code": "dmd", "name": "Đỗ Minh Đường"},
    )
    assert result["actor_role"] == "hub_admin"
    assert result["actor_hub_id"] == hub_id
    assert result["code"] == "dmd"
    assert result["name"] == "Đỗ Minh Đường"


def test_extra_none_returns_only_actor_keys() -> None:
    """Case 3: extra=None → dict CHỈ 2 key actor (KHÔNG merge thêm)."""
    result = build_audit_payload(
        actor_role="admin", actor_hub_id=None, extra=None
    )
    assert set(result.keys()) == {"actor_role", "actor_hub_id"}
    assert result["actor_role"] == "admin"
    assert result["actor_hub_id"] is None


def test_extra_can_override_actor_keys_document_behavior() -> None:
    """Case 4 defensive: extra có actor_role/actor_hub_id sẽ OVERRIDE base.

    Document behavior — caller responsibility KHÔNG pass extra với actor keys.
    Helper KHÔNG enforce hard guard (PEP 20 simple > complex; caller bug guard
    qua code review thay vì runtime check).
    """
    result = build_audit_payload(
        actor_role="admin",
        actor_hub_id=None,
        extra={"actor_role": "override_value"},
    )
    assert result["actor_role"] == "override_value", (
        "Document behavior: extra override base (caller bug responsibility)."
    )
