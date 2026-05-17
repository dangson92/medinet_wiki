"""Hub isolation enforcement — HUB-02 (EXIT criteria E4, security-critical).

Defense in depth 3 lớp:
  (1) repository — `hub_filter_clause()` inject `WHERE hub_id IN (...)` vào mọi
      SELECT/UPDATE/DELETE để editor/viewer chỉ thấy row thuộc hub được assign.
  (2) service — `verify_hub_access()` gọi TRƯỚC mutation, so resource's hub_id
      THỰC TẾ (load từ DB row, KHÔNG từ payload) với user's hub assignments.
  (3) caller — khi reject (raise `HubIsolationError`), enqueue audit
      `security.hub_isolation_violation` cho forensic trail.

KHÔNG BAO GIỜ tin `hub_id` trong request payload. Editor của Hub A gửi
`{"hub_id": "hub_a"}` để mutate resource Hub B vẫn phải bị reject — hub_id
authorize luôn lấy từ JWT claims / `user_hubs` join table (verified source).

admin role bypass hub filter (quản trị cross-hub theo thiết kế — HUB-03 stats,
USER-01 CRUD). admin-only endpoint đã gate riêng qua `require_role("admin")`.
"""
from __future__ import annotations


class HubIsolationError(Exception):
    """Cross-hub access bị từ chối — caller map sang 403 + audit log.

    Lưu `resource_hub_id` để caller dùng cho audit payload
    (`security.hub_isolation_violation`).
    """

    def __init__(self, message: str, *, resource_hub_id: str | None = None) -> None:
        self.resource_hub_id = resource_hub_id
        super().__init__(message)


def hub_filter_clause(
    *,
    role: str,
    hub_ids: list[str],
    param_prefix: str = "uh",
) -> tuple[str, dict[str, str]]:
    """Sinh SQL fragment ràng buộc query theo hub user được assign (HUB-02).

    Trả `(clause, params)` để caller ghép vào WHERE + truyền bound param:
      - admin → `("", {})` — bypass, query KHÔNG thêm filter hub_id.
      - hub_ids rỗng (editor/viewer chưa assign hub) → `("hub_id IN (NULL)", {})`
        — clause luôn-false, user thấy 0 row (T-05-02-02 — KHÔNG leak mọi row).
      - editor/viewer có hub → `("hub_id IN (:uh0, :uh1, ...)", {...})`.

    `param_prefix` cho phép đổi tên param tránh đụng param khác trong query.
    """
    if role == "admin":
        return "", {}
    if not hub_ids:
        # Luôn-false clause — editor/viewer chưa assign hub KHÔNG thấy row nào.
        return "hub_id IN (NULL)", {}
    placeholders = ", ".join(f":{param_prefix}{i}" for i in range(len(hub_ids)))
    clause = f"hub_id IN ({placeholders})"
    params = {f"{param_prefix}{i}": h for i, h in enumerate(hub_ids)}
    return clause, params


def verify_hub_access(
    *,
    role: str,
    user_hub_ids: list[str],
    resource_hub_id: str,
) -> None:
    """Guard cross-hub mutation — raise `HubIsolationError` khi vi phạm (HUB-02).

    `resource_hub_id` PHẢI là hub_id THỰC TẾ của resource (load từ DB row),
    KHÔNG được lấy từ request payload (T-05-02-01).

    - admin → pass (return None) bất kể `resource_hub_id`.
    - editor/viewer → pass khi `resource_hub_id` ∈ `user_hub_ids`.
    - editor/viewer → raise `HubIsolationError` khi `resource_hub_id` ∉ assignment.
    """
    if role == "admin":
        return None
    if resource_hub_id not in user_hub_ids:
        raise HubIsolationError(
            f"Resource thuộc hub {resource_hub_id} ngoài quyền truy cập",
            resource_hub_id=resource_hub_id,
        )
    return None
