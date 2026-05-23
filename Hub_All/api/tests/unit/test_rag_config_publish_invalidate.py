"""Phase 6 Plan 06-03 Wave 3 Task 2a — Unit test update_rag_config publish invalidate.

Per PLAN <behavior> 4 test:
1. PUT success + redis available → publish settings:invalidate JSON payload.
2. PUT success + redis=None → KHÔNG raise (best-effort fail-open).
3. PUT success + redis.publish raise ConnectionError → KHÔNG block 200 response.
4. PUT fail (service returns error str) → KHÔNG publish (early return 400).

Pattern: Mock RagConfigService + Request.app.state.redis (AsyncMock).

Decision traceability:
- D-V3-Phase6-C LOCKED — Channel "settings:invalidate" single channel.
- T-06-03-04 mitigation — try/except publish best-effort fail-open.
- T-06-03-06 — publish payload server-side JSON encode (KHÔNG user input).
"""
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.responses import JSONResponse

from app.routers.rag_config import update_rag_config


def _make_request(redis: object | None = None) -> MagicMock:
    """Tạo Request mock với app.state.redis."""
    request = MagicMock()
    request.app.state.redis = redis
    return request


def _make_user() -> SimpleNamespace:
    """Mock admin user."""
    return SimpleNamespace(id="user-admin-1", role="admin")


# --------------------------------------------------------------------------
# Test 1: PUT success + redis available → publish settings:invalidate
# --------------------------------------------------------------------------


async def test_publish_invalidate_on_success() -> None:
    """Test 1 — PUT success + redis mock → publish(channel, payload) called.

    Payload phải contain config_key=rag_config, hub=*, timestamp:int.
    """
    redis = MagicMock()
    redis.publish = AsyncMock(return_value=1)
    request = _make_request(redis=redis)
    user = _make_user()
    db = MagicMock()
    req = MagicMock()

    with patch("app.routers.rag_config.RagConfigService") as mock_service_cls:
        mock_service = MagicMock()
        mock_service.update_config = AsyncMock(
            return_value={"embedding_provider": "openai"}
        )
        mock_service_cls.return_value = mock_service

        result = await update_rag_config(
            request=request, req=req, user=user, db=db
        )

    # Result là dict (success), KHÔNG phải JSONResponse error
    assert result == {"embedding_provider": "openai"}

    # Publish called đúng channel + payload
    redis.publish.assert_awaited_once()
    call_args = redis.publish.call_args
    channel = call_args[0][0]
    payload_str = call_args[0][1]
    assert channel == "settings:invalidate"
    payload = json.loads(payload_str)
    assert payload["config_key"] == "rag_config"
    assert payload["hub"] == "*"
    assert isinstance(payload["timestamp"], int)


# --------------------------------------------------------------------------
# Test 2: PUT success + redis=None → KHÔNG raise (best-effort fail-open)
# --------------------------------------------------------------------------


async def test_redis_none_no_raise() -> None:
    """Test 2 — redis=None → publish skip + return dict 200 (fail-open)."""
    request = _make_request(redis=None)
    user = _make_user()
    db = MagicMock()
    req = MagicMock()

    with patch("app.routers.rag_config.RagConfigService") as mock_service_cls:
        mock_service = MagicMock()
        mock_service.update_config = AsyncMock(
            return_value={"embedding_provider": "openai"}
        )
        mock_service_cls.return_value = mock_service

        # KHÔNG raise — best-effort fail-open
        result = await update_rag_config(
            request=request, req=req, user=user, db=db
        )

    assert result == {"embedding_provider": "openai"}


# --------------------------------------------------------------------------
# Test 3: PUT success + redis.publish raise ConnectionError → 200 không block
# --------------------------------------------------------------------------


async def test_publish_failure_does_not_block_response() -> None:
    """Test 3 — redis.publish raise → log warning + return dict 200 (KHÔNG raise).

    Best-effort fail-open — admin PUT KHÔNG bị block bởi Redis down (T-06-03-04).
    """
    redis = MagicMock()
    redis.publish = AsyncMock(side_effect=ConnectionError("redis down"))
    request = _make_request(redis=redis)
    user = _make_user()
    db = MagicMock()
    req = MagicMock()

    with patch("app.routers.rag_config.RagConfigService") as mock_service_cls:
        mock_service = MagicMock()
        mock_service.update_config = AsyncMock(
            return_value={"embedding_provider": "openai"}
        )
        mock_service_cls.return_value = mock_service

        # KHÔNG raise — best-effort fail-open
        result = await update_rag_config(
            request=request, req=req, user=user, db=db
        )

    assert result == {"embedding_provider": "openai"}
    redis.publish.assert_awaited_once()  # publish attempted (raise được catch)


# --------------------------------------------------------------------------
# Test 4: PUT fail (service str error) → KHÔNG publish (early return 400)
# --------------------------------------------------------------------------


async def test_service_error_skips_publish() -> None:
    """Test 4 — service.update_config return error str → 400 JSONResponse +
    KHÔNG publish (early return trước publish block).
    """
    redis = MagicMock()
    redis.publish = AsyncMock(return_value=1)
    request = _make_request(redis=redis)
    user = _make_user()
    db = MagicMock()
    req = MagicMock()

    with patch("app.routers.rag_config.RagConfigService") as mock_service_cls:
        mock_service = MagicMock()
        mock_service.update_config = AsyncMock(
            return_value="invalid provider value"
        )
        mock_service_cls.return_value = mock_service

        result = await update_rag_config(
            request=request, req=req, user=user, db=db
        )

    assert isinstance(result, JSONResponse)
    assert result.status_code == 400
    # KHÔNG publish vì early return trước publish block
    redis.publish.assert_not_awaited()
