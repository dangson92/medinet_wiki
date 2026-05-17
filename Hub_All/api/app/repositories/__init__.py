"""Repository layer — data-access helper mỏng tách khỏi service.

Phase 4 dùng pattern service-chứa-SQL. Phase 5 introduce module này CHỈ cho
HUB-02 hub-isolation query builder (`hub_isolation`) — chỗ duy nhất cần
repository riêng để test cô lập logic enforcement (EXIT criteria E4).
"""
from __future__ import annotations
