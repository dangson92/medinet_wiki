"""Phase 6 settings_sync — pub/sub subscriber loop (D-V3-Phase6-C LOCKED).

Lắng nghe channel `settings:invalidate` (1 channel duy nhất — KHÔNG split 3 channel).
Pydantic `InvalidateMessage` validate payload trước khi flush cache.

3 config_key flush branch (D-V3-Phase6-C LOCKED):
- rag_config: hub="*" broadcast HOẶC hub==settings.hub_name match
  → `redis.delete(f"settings:rag_config:{hub_name}")`.
- hub_registry: any hub → `redis.delete("settings:hub_registry")` singleton.
- apikey: key_id set HOẶC null → SCAN + DEL all `apikey:verify:*` (full flush
  vì subscriber không có plaintext key để compute hash; 60s TTL natural burn
  acceptable per CONTEXT Claude's Discretion).

Reconnect logic (T-06-02-05 DoS mitigation):
- ConnectionError / generic Exception → log warning + asyncio.sleep(reconnect_seconds)
  + retry (KHÔNG fail-loud — TTL natural fallback nếu Redis down kéo dài).
- CancelledError → re-raise (graceful shutdown lifespan).

Pattern carry forward:
- `api/app/services/search_cache.py::search_cache_subscriber` (M2 SEARCH-04
  subscribe + listen + finally aclose).
- `api/app/auth/jwks.py::JWKSCache._refresh_loop` (defensive try/except global).

Threat model:
- T-06-02-03 Tampering: Pydantic Literal enum reject invalid config_key
  (T-06-03-03 carry forward search_cache schema validation pattern).
- T-06-02-05 DoS: subscriber crash KHÔNG block lifespan (best-effort fail-open).
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError

from app.settings_sync.keys import (
    APIKEY_VERIFY_KEY_PREFIX,
    HUB_REGISTRY_KEY,
    RAG_CONFIG_KEY_PREFIX,
    SETTINGS_INVALIDATE_CHANNEL,
)
from app.settings_sync.metrics import SETTINGS_INVALIDATE_RECEIVED_TOTAL

logger = logging.getLogger(__name__)


class InvalidateMessage(BaseModel):
    """Phase 6 SETTINGS-02 (D-V3-Phase6-C) — pub/sub payload schema.

    Fields:
    - config_key: Literal enum 3 value (rag_config | hub_registry | apikey).
      T-06-02-03 Tampering mitigation — attacker compromise Redis publish
      KHÔNG inject arbitrary code path branch.
    - hub: required str max_length=32, hub name cụ thể HOẶC "*" broadcast.
    - key_id: optional str — apikey granular revoke (rag_config + hub_registry
      KHÔNG dùng).
    - timestamp: unix epoch seconds — debug + future ordering replay.
    """

    config_key: Literal["rag_config", "hub_registry", "apikey"]
    hub: str = Field(..., min_length=1, max_length=32)
    key_id: str | None = None
    timestamp: int


async def _flush_apikey_full_scan(redis: Any) -> None:
    """SCAN + DEL all `apikey:verify:*` keys (full flush pattern).

    Subscriber KHÔNG có plaintext key để compute hash → flush all (60s TTL
    natural burn acceptable per CONTEXT Claude's Discretion).
    """
    cursor: int = 0
    while True:
        cursor, keys = await redis.scan(
            cursor=cursor,
            match=f"{APIKEY_VERIFY_KEY_PREFIX}*",
            count=100,
        )
        if keys:
            await redis.delete(*keys)
        if cursor == 0:
            break


async def _handle_invalidate(
    redis: Any, hub_name: str, msg: InvalidateMessage
) -> None:
    """Phân nhánh 3 config_key flush cache key đúng (D-V3-Phase6-C LOCKED)."""
    if msg.config_key == "rag_config":
        # rag_config: hub="*" broadcast HOẶC hub specific match
        if msg.hub != "*" and msg.hub != hub_name:
            return  # mismatch skip
        await redis.delete(f"{RAG_CONFIG_KEY_PREFIX}{hub_name}")
        logger.info(
            "settings_invalidate_rag_config: hub=%s flushed",
            hub_name,
        )
    elif msg.config_key == "hub_registry":
        await redis.delete(HUB_REGISTRY_KEY)
        logger.info("settings_invalidate_hub_registry: flushed singleton")
    elif msg.config_key == "apikey":
        await _flush_apikey_full_scan(redis)
        logger.info(
            "settings_invalidate_apikey: full flush all (key_id=%s)",
            msg.key_id,
        )
    SETTINGS_INVALIDATE_RECEIVED_TOTAL.labels(
        hub_name=hub_name, key_type=msg.config_key
    ).inc()


async def _process_message(redis: Any, hub_name: str, message: Any) -> None:
    """Parse + validate + dispatch 1 pubsub message — defensive try/except inside."""
    if message is None or message.get("type") != "message":
        return
    raw = message.get("data")
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    try:
        payload = json.loads(raw)
        msg = InvalidateMessage.model_validate(payload)
    except (json.JSONDecodeError, ValidationError) as e:
        logger.warning(
            "settings_subscriber_invalid_payload: err=%s raw=%r",
            e,
            raw,
        )
        return
    try:
        await _handle_invalidate(redis, hub_name, msg)
    except Exception as e:  # noqa: BLE001 — defensive handle error
        logger.warning(
            "settings_subscriber_handle_error: msg=%s err=%s",
            msg,
            e,
        )


async def _subscribe_and_listen(redis: Any, hub_name: str) -> None:
    """1 inner iteration — subscribe channel + listen messages + dispatch."""
    pubsub = None
    try:
        pubsub = redis.pubsub()
        await pubsub.subscribe(SETTINGS_INVALIDATE_CHANNEL)
        logger.info(
            "settings_subscriber_started: channel=%s hub=%s",
            SETTINGS_INVALIDATE_CHANNEL,
            hub_name,
        )
        async for message in pubsub.listen():
            await _process_message(redis, hub_name, message)
    finally:
        if pubsub is not None:
            try:
                await pubsub.aclose()
            except Exception:  # noqa: BLE001
                pass


async def settings_subscriber_loop(
    redis: Any,
    *,
    hub_name: str,
    reconnect_seconds: int = 5,
) -> None:
    """Settings invalidate subscriber loop — outer while True wrap reconnect.

    Mỗi inner iteration: subscribe channel + listen messages + dispatch.
    ConnectionError / generic Exception → log warning + asyncio.sleep + retry
    (best-effort fail-open T-06-02-05). CancelledError → re-raise graceful.

    Args:
        redis: Redis async client (None → log warning + return early).
        hub_name: Subscriber hub identity (filter rag_config branch).
        reconnect_seconds: Sleep duration giữa reconnect attempts.

    Raises:
        asyncio.CancelledError: Graceful shutdown từ lifespan stop signal.
    """
    if redis is None:
        logger.warning(
            "settings_subscriber: redis None — subscriber không khởi động"
        )
        return

    while True:
        try:
            await _subscribe_and_listen(redis, hub_name)
        except asyncio.CancelledError:
            logger.info("settings_subscriber_cancelled: hub=%s", hub_name)
            raise
        except Exception as e:  # noqa: BLE001 — best-effort fail-open reconnect
            logger.warning(
                "settings_subscriber_error_reconnect: hub=%s err=%s sleep=%ds",
                hub_name,
                e,
                reconnect_seconds,
            )
        # Reconnect delay (only reached on non-cancel exception path or natural
        # listen iterator drain — Redis pubsub thực tế listen() block vĩnh viễn).
        await asyncio.sleep(reconnect_seconds)


__all__ = [
    "InvalidateMessage",
    "settings_subscriber_loop",
]
