"""API key schemas — Pydantic v2 (Plan 05-05, AUX-02).

Contract endpoint lấy từ `frontend/src/services/api.ts` (D-07 — frontend thắng
REQUIREMENTS.md khi mâu thuẫn verb/path/field).

`APIKeyAPI` (api.ts ~595): id, name, key_prefix, permissions[], allowed_hub_ids?,
allowed_rag_configs?, rate_limit, expires_at?, status, requests_today, requests_7d,
bandwidth_used, last_used_at?, created_by, created_at.

LƯU Ý — field không có cột DB (M2 chưa track usage; defer v4.0):
- `requests_today` / `requests_7d` / `bandwidth_used` → trả 0 hằng số.
- `allowed_rag_configs` → trả [] hằng số.
- `status` derive từ `is_active` (TRUE → "active", FALSE → "revoked").

Plaintext key CHỈ trả 1 lần lúc POST create (`ApiKeyWithPlaintext.plain_key`);
GET/list KHÔNG bao giờ trả plaintext (T-05-05-01).
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

# Derive từ api_keys.is_active — TRUE → "active", FALSE → "revoked".
ApiKeyStatus = Literal["active", "revoked"]


class CreateApiKeyRequest(BaseModel):
    """POST /api/api-keys body — admin tạo API key mới (api.ts:314)."""

    name: str = Field(min_length=1, max_length=200)
    permissions: list[str] = Field(default_factory=list)
    allowed_hub_ids: list[str] | None = None
    rate_limit: int = Field(default=100, ge=1, le=10000)


class UpdateApiKeyRequest(BaseModel):
    """PUT /api/api-keys/:id body — admin cập nhật metadata (api.ts:318)."""

    name: str | None = Field(default=None, max_length=200)
    permissions: list[str] | None = None
    allowed_hub_ids: list[str] | None = None
    rate_limit: int | None = Field(default=None, ge=1, le=10000)


class ApiKeyResponse(BaseModel):
    """GET /api/api-keys(:id) response data — APIKeyAPI contract frontend.

    KHÔNG có `plain_key` — GET/list không bao giờ trả plaintext (T-05-05-01).
    """

    id: str  # UUID string
    name: str
    key_prefix: str
    permissions: list[str]
    allowed_hub_ids: list[str] | None
    allowed_rag_configs: list[str] = Field(default_factory=list)
    rate_limit: int
    expires_at: datetime | None
    status: ApiKeyStatus
    requests_today: int = 0
    requests_7d: int = 0
    bandwidth_used: int = 0
    last_used_at: datetime | None
    created_by: str | None
    created_at: datetime


class ApiKeyWithPlaintext(ApiKeyResponse):
    """POST /api/api-keys response data — APIKeyWithPlaintextAPI.

    `plain_key` plaintext key CHỈ trả 1 lần duy nhất lúc create — sau đó không
    khôi phục được (key_hash lưu AES-GCM, GET chỉ trả key_prefix).
    """

    plain_key: str


class VerifyApiKeyRequest(BaseModel):
    """POST /api/api-keys/verify body — Phase 6 Plan 06-03 (D-V3-Phase6-D).

    Internal proxy endpoint dùng cho hub con call central verify X-API-Key
    qua ApiKeyVerifyClient (Plan 06-02). Body chứa plaintext api_key — bảo
    vệ qua header X-Internal-Auth shared secret + intra-network medinet_net
    Docker isolation (T-06-03-03 accepted defer v4.0 mTLS).
    """

    api_key: str = Field(..., min_length=1, max_length=256)
