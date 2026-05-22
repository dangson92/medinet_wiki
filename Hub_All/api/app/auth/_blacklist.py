"""Phase 3 Plan 03-03 (D-V3-Phase3-H) — Redis blacklist key schema.

Mini-module chứa constant + helper để tránh circular import giữa
`service.py` + `dependencies.py` (cả 2 cần access prefix).

D-V3-Phase3-H spec (CONTEXT.md):
- Key: `auth:blacklist:{jti}` (namespace clarity, tránh collision cross-feature)
- Value: `"1"` (marker only — metadata audit qua audit_logs M2 carry forward)
- TTL: `JWT.exp - now()` (auto-expire, KHÔNG cần cron cleanup)
- Lookup: `redis.exists(f"auth:blacklist:{jti}")` → 401 TOKEN_REVOKED
- Redis instance: M2 baseline `REDIS_URL` chung (cross-process central + hub con)

Tracing: SSO-02 (Redis blacklist key schema) + D-V3-Phase3-H.

M2 backward incompat: key cũ `blacklist:{jti}` sau Plan 03-03 deploy KHÔNG
được check nữa (chuyển sang `auth:blacklist:{jti}`). Operator có thể flush
prefix cũ trong Redis post-deploy nếu muốn dọn dẹp (KHÔNG bắt buộc — key cũ
sẽ tự expire theo TTL ≤ 7d refresh token).
"""
from __future__ import annotations

# Phase 3 Plan 03-03 (D-V3-Phase3-H SSO-02) — Redis blacklist key prefix.
# Đổi từ M2 `blacklist:` → `auth:blacklist:` để namespace clarity (tránh
# collision với future blacklist feature, vd `apikey:blacklist:`, `mcp:blacklist:`).
REDIS_BLACKLIST_PREFIX = "auth:blacklist:"


def make_blacklist_key(jti: str) -> str:
    """Build Redis key `auth:blacklist:{jti}` — D-V3-Phase3-H.

    Args:
        jti: JWT ID (UUID4 string) — JWT.claims.jti.

    Returns:
        Redis key string `auth:blacklist:{jti}` để dùng cho
        `redis.set(key, "1", ex=ttl)` (logout) hoặc `redis.exists(key)`
        (verify get_current_user).
    """
    return f"{REDIS_BLACKLIST_PREFIX}{jti}"
