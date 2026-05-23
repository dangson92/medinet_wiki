"""Phase 6 Plan 06-02 Wave 2 Task 2 — Unit test subscriber.py + InvalidateMessage.

Per PLAN <behavior> 8 test (3 Pydantic schema + 5 subscriber loop behavior):

Pydantic InvalidateMessage:
- model_validate happy 3 config_key + accept optional key_id.
- ValidationError reject invalid config_key (Literal enum) — T-06-02-03 Tampering.
- model_validate accept key_id None default.

Subscriber loop:
- Receive rag_config hub="*" → redis.delete called + emit invalidate counter.
- Receive rag_config hub mismatch ("duoc" ở hub "yte") → KHÔNG delete (skip).
- Receive hub_registry → redis.delete("settings:hub_registry") singleton.
- Receive invalid JSON → log warning skip + KHÔNG delete.
- CancelledError → loop re-raise (graceful shutdown).

Pattern carry forward:
- search_cache.py subscriber loop pattern (M2 SEARCH-04).
- test_jwks_cache.py asyncio.CancelledError pattern.

Decision traceability:
- D-V3-Phase6-C — 1 channel "settings:invalidate" + Pydantic Literal enum payload.
- T-06-02-03 — Tampering mitigation Pydantic validate.
- T-06-02-05 — DoS subscriber crash KHÔNG block lifespan (best-effort fail-open).
"""
from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

# ────────────────────────────────────────────────────────────────────
# Pydantic InvalidateMessage (3 test)
# ────────────────────────────────────────────────────────────────────


def test_invalidate_message_accepts_rag_config_broadcast() -> None:
    """InvalidateMessage model_validate({"config_key":"rag_config","hub":"*",...}) OK."""
    from app.settings_sync.subscriber import InvalidateMessage

    msg = InvalidateMessage.model_validate(
        {"config_key": "rag_config", "hub": "*", "timestamp": 1234}
    )
    assert msg.config_key == "rag_config"
    assert msg.hub == "*"
    assert msg.timestamp == 1234
    assert msg.key_id is None  # optional default


def test_invalidate_message_rejects_invalid_config_key() -> None:
    """InvalidateMessage Literal enum reject KHÔNG trong 3 value valid.

    T-06-02-03 Tampering mitigation — attacker compromise Redis publish
    KHÔNG inject arbitrary config_key string vào subscriber branch logic.
    """
    from app.settings_sync.subscriber import InvalidateMessage

    with pytest.raises(ValidationError):
        InvalidateMessage.model_validate(
            {"config_key": "INVALID_TYPE", "hub": "*", "timestamp": 1234}
        )


def test_invalidate_message_accepts_apikey_with_key_id() -> None:
    """apikey config_key + optional key_id (granular revoke)."""
    from app.settings_sync.subscriber import InvalidateMessage

    msg = InvalidateMessage.model_validate(
        {
            "config_key": "apikey",
            "hub": "yte",
            "key_id": "uuid-1234",
            "timestamp": 5678,
        }
    )
    assert msg.config_key == "apikey"
    assert msg.hub == "yte"
    assert msg.key_id == "uuid-1234"


# ────────────────────────────────────────────────────────────────────
# Subscriber loop helpers
# ────────────────────────────────────────────────────────────────────


def _make_message(payload: dict[str, Any] | str) -> dict[str, Any]:
    """Build Redis pubsub message envelope shape {type, channel, data}.

    `decode_responses=True` (main.py M2 setup) → channel str, data str.
    Subscriber loop logic handle both str + bytes (defensive).
    """
    data = payload if isinstance(payload, str) else json.dumps(payload)
    return {
        "type": "message",
        "channel": "settings:invalidate",
        "data": data,
    }


def _make_pubsub_mock(
    messages: list[dict[str, Any]],
) -> MagicMock:
    """Mock Redis pubsub object — .subscribe() async + .listen() async iterator.

    Yields each message in turn → iterator ends → subscriber outer except generic
    catches StopAsyncIteration / drain → reconnect sleep. Caller dùng wait_for
    timeout để exit graceful (tránh CancelledError pytest-asyncio conflict).
    """
    pubsub = MagicMock()
    pubsub.subscribe = AsyncMock(return_value=None)
    pubsub.aclose = AsyncMock(return_value=None)

    async def _listen() -> AsyncIterator[dict[str, Any]]:
        for item in messages:
            yield item

    pubsub.listen = _listen
    return pubsub


def _make_redis_with_pubsub(
    pubsub_mock: MagicMock,
    scan_return: tuple[int, list[bytes]] | None = None,
) -> MagicMock:
    """Mock Redis with pubsub() method + delete + scan async methods."""
    redis = MagicMock()
    redis.pubsub = MagicMock(return_value=pubsub_mock)
    redis.delete = AsyncMock(return_value=1)
    if scan_return is not None:
        redis.scan = AsyncMock(return_value=scan_return)
    else:
        # Default scan: empty result (cursor 0, no keys)
        redis.scan = AsyncMock(return_value=(0, []))
    return redis


# ────────────────────────────────────────────────────────────────────
# Subscriber loop (5 test)
# ────────────────────────────────────────────────────────────────────


async def _run_loop_until_stop(
    redis: Any, hub_name: str, *, timeout: float = 2.0
) -> None:
    """Chạy subscriber_loop với asyncio.wait_for timeout — tránh test hang."""
    from app.settings_sync.subscriber import settings_subscriber_loop

    try:
        await asyncio.wait_for(
            settings_subscriber_loop(
                redis, hub_name=hub_name, reconnect_seconds=10
            ),
            timeout=timeout,
        )
    except TimeoutError:
        # Subscriber stuck in reconnect sleep (after exception drained iterator)
        # — expected exit path để assert sau khi message đã consume.
        pass


async def test_subscriber_rag_config_broadcast_deletes_per_hub_key() -> None:
    """rag_config hub="*" broadcast → delete settings:rag_config:<hub_name>."""
    payload = {"config_key": "rag_config", "hub": "*", "timestamp": 1000}
    # Yield 1 message → iterator end → subscriber generic except catches
    # StopAsyncIteration / drain → reconnect sleep → wait_for timeout exit.
    pubsub = _make_pubsub_mock([_make_message(payload)])
    redis = _make_redis_with_pubsub(pubsub)

    await _run_loop_until_stop(redis, hub_name="yte")

    redis.delete.assert_any_call("settings:rag_config:yte")


async def test_subscriber_rag_config_hub_mismatch_skips_delete() -> None:
    """rag_config hub="duoc" ở subscriber hub_name="yte" → KHÔNG delete (skip)."""
    payload = {"config_key": "rag_config", "hub": "duoc", "timestamp": 1000}
    pubsub = _make_pubsub_mock([_make_message(payload)])
    redis = _make_redis_with_pubsub(pubsub)

    await _run_loop_until_stop(redis, hub_name="yte")

    # delete KHÔNG được gọi vì hub mismatch
    redis.delete.assert_not_called()


async def test_subscriber_hub_registry_deletes_singleton_key() -> None:
    """hub_registry → delete settings:hub_registry (singleton, any hub)."""
    payload = {"config_key": "hub_registry", "hub": "*", "timestamp": 1000}
    pubsub = _make_pubsub_mock([_make_message(payload)])
    redis = _make_redis_with_pubsub(pubsub)

    await _run_loop_until_stop(redis, hub_name="yte")

    redis.delete.assert_any_call("settings:hub_registry")


async def test_subscriber_invalid_json_logs_warning_and_continues() -> None:
    """Invalid JSON payload → log warning skip + KHÔNG redis.delete + KHÔNG crash."""
    pubsub = _make_pubsub_mock(
        [
            {"type": "message", "channel": "settings:invalidate", "data": "not-json{"},
        ]
    )
    redis = _make_redis_with_pubsub(pubsub)

    await _run_loop_until_stop(redis, hub_name="yte")

    redis.delete.assert_not_called()  # invalid → skip


async def test_subscriber_cancelled_error_reraises_graceful() -> None:
    """asyncio.CancelledError trong listen → loop re-raise (graceful shutdown).

    Test manually drive subscriber qua asyncio.create_task + task.cancel() — đây
    là cách production thực sự cancel subscriber (lifespan task.cancel()).
    """
    from app.settings_sync.subscriber import settings_subscriber_loop

    # Pubsub blocks forever on listen() — task.cancel() trigger CancelledError
    # truyền vào async for loop.
    pubsub = MagicMock()
    pubsub.subscribe = AsyncMock(return_value=None)
    pubsub.aclose = AsyncMock(return_value=None)

    async def _listen_forever() -> AsyncIterator[dict[str, Any]]:
        await asyncio.sleep(60)  # block — task.cancel() trigger CancelledError
        yield {}  # unreachable

    pubsub.listen = _listen_forever
    redis = MagicMock()
    redis.pubsub = MagicMock(return_value=pubsub)
    redis.delete = AsyncMock(return_value=1)
    redis.scan = AsyncMock(return_value=(0, []))

    task = asyncio.create_task(
        settings_subscriber_loop(redis, hub_name="yte", reconnect_seconds=1)
    )
    # Cho task start subscribe + enter listen sleep
    await asyncio.sleep(0.1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    # pubsub.aclose() vẫn được gọi
    pubsub.aclose.assert_called()


# ────────────────────────────────────────────────────────────────────
# Extra (3 test) — apikey full flush + invalid validation + redis None guard
# ────────────────────────────────────────────────────────────────────


async def test_subscriber_apikey_null_key_id_scans_and_flushes() -> None:
    """apikey null key_id → SCAN + DEL all apikey:verify:* keys."""
    payload = {"config_key": "apikey", "hub": "*", "timestamp": 1000}
    pubsub = _make_pubsub_mock([_make_message(payload)])
    # Mock scan trả về 2 keys ở first iteration, cursor 0 (done)
    scan_keys = [b"apikey:verify:hash1", b"apikey:verify:hash2"]
    redis = _make_redis_with_pubsub(pubsub, scan_return=(0, scan_keys))

    await _run_loop_until_stop(redis, hub_name="yte")

    redis.scan.assert_called()
    redis.delete.assert_called_with(*scan_keys)


async def test_subscriber_invalid_payload_schema_skips() -> None:
    """Pydantic ValidationError (config_key INVALID enum) → log warning skip."""
    pubsub = _make_pubsub_mock(
        [_make_message({"config_key": "INVALID", "hub": "yte", "timestamp": 1})]
    )
    redis = _make_redis_with_pubsub(pubsub)

    await _run_loop_until_stop(redis, hub_name="yte")

    redis.delete.assert_not_called()


async def test_subscriber_redis_none_returns_early() -> None:
    """redis=None → subscriber log warning + return KHÔNG block lifespan."""
    from app.settings_sync.subscriber import settings_subscriber_loop

    # Should return immediately without raising
    await settings_subscriber_loop(
        None, hub_name="yte", reconnect_seconds=1
    )
