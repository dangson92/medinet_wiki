"""Unit test schemas/usage.py — Plan 07-02 Task 1 (ASK-05 contract layer).

Test pure-Python (KHÔNG cần Postgres) — xác nhận shape Pydantic v2 khớp contract
D6 `frontend/src/services/api.ts` (`TokenUsageAPI`, `TokenUsageStatsAPI`,
`TokenUsageRealtimeAPI`).
"""
from __future__ import annotations

from app.schemas.usage import (
    UsageEventResponse,
    UsageRealtime,
    UsageRealtimePoint,
    UsageStats,
)


def test_usage_event_response_valid() -> None:
    """UsageEventResponse với đủ field bắt buộc hợp lệ — khớp TokenUsageAPI."""
    event = UsageEventResponse(
        id="abc-123",
        timestamp="2026-05-18T12:00:00+00:00",
        provider="openai",
        model="gpt-4o-mini",
        operation="ask",
        request_count=1,
        prompt_tokens=10,
        output_tokens=5,
        total_tokens=15,
        latency_ms=0,
        status="success",
    )
    assert event.provider == "openai"
    assert event.operation == "ask"
    assert event.total_tokens == 15
    # Optional field default None.
    assert event.source_module is None
    assert event.user_name is None
    assert event.error_message is None


def test_usage_stats_empty_groups_valid() -> None:
    """UsageStats với list group rỗng hợp lệ — khớp TokenUsageStatsAPI."""
    stats = UsageStats(
        total_calls=0,
        total_tokens=0,
        total_prompt_tokens=0,
        total_output_tokens=0,
        error_calls=0,
        avg_latency_ms=0.0,
        by_provider=[],
        by_model=[],
        by_operation=[],
        daily=[],
    )
    assert stats.total_calls == 0
    assert stats.by_provider == []
    assert stats.daily == []


def test_usage_realtime_valid() -> None:
    """UsageRealtime + UsageRealtimePoint hợp lệ — khớp TokenUsageRealtimeAPI."""
    totals = UsageRealtimePoint(
        minute="2026-05-18 12:00",
        calls=3,
        total_tokens=30,
        prompt_tokens=20,
        output_tokens=10,
        avg_latency_ms=0.0,
        errors=0,
        by_provider={"openai": 3},
        by_operation={"ask": 3},
    )
    rt = UsageRealtime(window_minutes=60, points=[totals], totals=totals)
    assert rt.window_minutes == 60
    assert len(rt.points) == 1
    assert rt.totals.calls == 3
