"""Usage schemas — Pydantic v2 contract Plan 07-02 (ASK-05 token usage).

D6 contract: shape khớp `frontend/src/services/api.ts` (`TokenUsageAPI`,
`TokenUsageGroupAPI`, `TokenUsageDailyPointAPI`, `TokenUsageStatsAPI`,
`TokenUsageRealtimePoint`, `TokenUsageRealtimeAPI`) 1:1 — đổi tên field sẽ break
frontend (KHÔNG sửa React M2).

Lưu ý chốt (D-07-02-A): bảng `usage_events` chỉ có cột token-count + model + id;
KHÔNG có `provider`/`operation`/`latency_ms`/`status`. Các field thiếu được
derive/hằng ở `usage_service.py`:
- `provider` derive từ `model` ("gemini" nếu model chứa "gemini", ngược lại
  "openai").
- `operation` hằng "ask"; `source_module` hằng "ask".
- `latency_ms` hằng 0; `status` hằng "success"; `error_message` luôn None.
- `output_tokens` map từ cột `completion_tokens`.
"""
from __future__ import annotations

from pydantic import BaseModel


class UsageEventResponse(BaseModel):
    """1 dòng usage event — = `TokenUsageAPI` (api.ts:638).

    `provider`/`operation`/`source_module`/`latency_ms`/`status` derive hoặc
    hằng (D-07-02-A) — bảng `usage_events` không có cột tương ứng.
    """

    id: str
    timestamp: str
    provider: str
    model: str
    operation: str
    source_module: str | None = None
    user_id: str | None = None
    user_name: str | None = None
    hub_id: str | None = None
    request_count: int
    prompt_tokens: int
    output_tokens: int
    total_tokens: int
    latency_ms: int
    status: str
    error_message: str | None = None


class UsageGroup(BaseModel):
    """1 nhóm aggregate — = `TokenUsageGroupAPI` (api.ts:657)."""

    key: str
    calls: int
    total_tokens: int


class UsageDailyPoint(BaseModel):
    """1 điểm aggregate theo ngày — = `TokenUsageDailyPointAPI` (api.ts:663)."""

    date: str
    calls: int
    total_tokens: int


class UsageStats(BaseModel):
    """Thống kê aggregate — = `TokenUsageStatsAPI` (api.ts:669).

    `error_calls`/`avg_latency_ms` hằng 0 ở M2 (D-07-02-A — không có cột
    latency/status trong `usage_events`).
    """

    total_calls: int
    total_tokens: int
    total_prompt_tokens: int
    total_output_tokens: int
    error_calls: int
    avg_latency_ms: float
    by_provider: list[UsageGroup]
    by_model: list[UsageGroup]
    by_operation: list[UsageGroup]
    daily: list[UsageDailyPoint]


class UsageRealtimePoint(BaseModel):
    """1 điểm realtime (group theo phút) — = `TokenUsageRealtimePoint` (api.ts:682)."""

    minute: str
    calls: int
    total_tokens: int
    prompt_tokens: int
    output_tokens: int
    avg_latency_ms: float
    errors: int
    by_provider: dict[str, int]
    by_operation: dict[str, int]


class UsageRealtime(BaseModel):
    """Realtime window 60 phút — = `TokenUsageRealtimeAPI` (api.ts:694).

    D-07-02-C: M2 best-effort từ cùng bảng `usage_events`
    (`WHERE created_at > NOW() - INTERVAL '60 minutes'`) — KHÔNG stream.
    """

    window_minutes: int
    points: list[UsageRealtimePoint]
    totals: UsageRealtimePoint
