"""Search cache — hub-tagged cache key scheme + Redis Pub/Sub invalidation (SEARCH-04 / D-12).

Vấn đề: cache key search (`search:<sha256>` / `search:cross:<sha256>` ở
`search_service.py`) băm query + hub_ids → KHÔNG chứa hub_id tường minh nên
không xoá cache "theo hub" được.

Giải pháp hub-tagged set: với MỖI cache key search, ngoài SET value còn thêm
key đó vào 1 Redis SET `search:hubtag:{hub_id}` cho mỗi hub trong query
(`tag_cache_key`). Khi 1 hub có document upload/delete → publish Pub/Sub channel
`hub:{hub_id}:invalidate`; subscriber (`search_cache_subscriber`) lắng nghe
pattern `hub:*:invalidate` → đọc SET `search:hubtag:{hub_id}` + `DEL` mọi member
+ `DEL` chính SET đó (`invalidate_hub`). Invalidate 1 hub CHỈ xoá cache key của
hub đó — KHÔNG đụng cache hub khác (T-06-03-02).

Mọi helper best-effort fail-open: Redis None / lỗi → log warning, KHÔNG raise
(precedent fail-open `documents_service.py` / `auth/dependencies.py`).

`decode_responses=True` (main.py step 2) → `message["channel"]` là `str`,
KHÔNG bytes — split trực tiếp OK.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)

#: Pattern channel subscriber psubscribe — mọi hub publish lên `hub:{id}:invalidate`.
INVALIDATE_CHANNEL_PATTERN = "hub:*:invalidate"
#: Prefix Redis SET gắn cache key theo hub.
HUBTAG_PREFIX = "search:hubtag:"
#: TTL SET hub-tag — tự hết hạn nếu subscriber miss event (phòng rò key).
HUBTAG_TTL = 600


def invalidate_channel(hub_id: str) -> str:
    """Tên channel Pub/Sub invalidate của 1 hub — `hub:{hub_id}:invalidate`."""
    return f"hub:{hub_id}:invalidate"


async def tag_cache_key(redis: Any, cache_key: str, hub_ids: list[str]) -> None:
    """Gắn 1 cache key search vào SET `search:hubtag:{hub_id}` cho mỗi hub.

    Gọi NGAY SAU khi search ghi cache. Best-effort fail-open — Redis None / lỗi
    → log warning, KHÔNG raise (cache là tối ưu hiệu năng, không phải hành vi
    đúng-sai của search).
    """
    if redis is None:
        return
    try:
        for hub_id in hub_ids:
            tag = f"{HUBTAG_PREFIX}{hub_id}"
            await redis.sadd(tag, cache_key)
            await redis.expire(tag, HUBTAG_TTL)
    except Exception as e:  # noqa: BLE001 — best-effort, KHÔNG raise
        logger.warning("search_cache_tag_failed: %s", e)


async def invalidate_hub(redis: Any, hub_id: str) -> int:
    """Xoá mọi cache key search gắn `hub_id` — đọc SET hub-tag + DEL member.

    Trả số cache key đã xoá. Best-effort fail-open — lỗi → log warning, trả 0.
    Invalidate hub X CHỈ DEL key của X — KHÔNG đụng cache hub khác (T-06-03-02).
    """
    if redis is None:
        return 0
    try:
        tag = f"{HUBTAG_PREFIX}{hub_id}"
        members = await redis.smembers(tag)
        deleted = 0
        if members:
            deleted = await redis.delete(*members)
        await redis.delete(tag)
        logger.info("search_cache_invalidated: hub=%s keys=%d", hub_id, deleted)
        return int(deleted)
    except Exception as e:  # noqa: BLE001
        logger.warning("search_cache_invalidate_failed: hub=%s err=%s", hub_id, e)
        return 0


async def publish_invalidate(redis: Any, hub_id: str) -> None:
    """Publish Pub/Sub channel `hub:{hub_id}:invalidate` — gọi sau document mutation.

    Best-effort fail-open — Redis None / down → log warning, KHÔNG raise
    (precedent fail-open: upload/delete vẫn thành công kể cả khi Redis chết —
    T-06-03-03).
    """
    if redis is None:
        return
    try:
        await redis.publish(invalidate_channel(hub_id), "1")
        logger.info("hub_invalidate_published: hub=%s", hub_id)
    except Exception as e:  # noqa: BLE001 — best-effort, KHÔNG raise
        logger.warning("hub_invalidate_publish_failed: hub=%s err=%s", hub_id, e)


async def search_cache_subscriber(redis: Any) -> None:
    """Subscriber loop — lắng nghe `hub:*:invalidate` → `invalidate_hub`.

    Chạy như asyncio background task trong lifespan (`main.py`). psubscribe
    pattern `hub:*:invalidate`; mỗi pmessage tách `hub_id` (phần giữa channel)
    + validate format TRƯỚC khi invalidate — channel rác bị bỏ qua (T-06-03-01).

    `CancelledError` → log + re-raise (graceful shutdown). Lỗi khác → log warning
    (KHÔNG crash lifespan — T-06-03-04). `finally` đóng pubsub.
    """
    if redis is None:
        logger.warning(
            "search_cache_subscriber: redis None — subscriber không khởi động"
        )
        return
    pubsub = redis.pubsub()
    try:
        await pubsub.psubscribe(INVALIDATE_CHANNEL_PATTERN)
        logger.info(
            "search_cache_subscriber_started: pattern=%s",
            INVALIDATE_CHANNEL_PATTERN,
        )
        async for message in pubsub.listen():
            if message is None or message.get("type") != "pmessage":
                continue
            channel = message.get("channel", "")
            # channel dạng "hub:{hub_id}:invalidate" — tách hub_id (phần giữa).
            # Validate format chặt: chỉ invalidate khi đúng schema (T-06-03-01).
            parts = channel.split(":")
            if len(parts) == 3 and parts[0] == "hub" and parts[2] == "invalidate":
                await invalidate_hub(redis, parts[1])
    except asyncio.CancelledError:
        logger.info("search_cache_subscriber_cancelled")
        raise
    except Exception as e:  # noqa: BLE001
        logger.warning("search_cache_subscriber_error: %s", e)
    finally:
        try:
            await pubsub.aclose()
        except Exception:  # noqa: BLE001
            pass
