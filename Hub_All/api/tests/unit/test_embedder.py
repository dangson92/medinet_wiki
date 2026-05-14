"""Unit test embedder — Plan 04-02 Task 03 (INGEST-02 prerequisite).

Mock litellm.aembedding để KHÔNG gọi external API trong unit test (CI không
cần OpenAI/Gemini API key). Test 5 case theo plan behavior matrix:
- Mock dim=1536 → embed_text return list[float] đúng dim.
- Empty text → ValueError.
- LiteLLM raise → EmbedderError wrap.
- Mock dim sai → EmbedderError ("dim sai").
- Hot-swap model qua arg.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.services.embedder import EMBEDDING_DIM, EmbedderError, embed_text


@pytest.mark.asyncio
async def test_embed_text_dim_1536() -> None:
    """Mock litellm trả vector dim 1536 → embed_text return list[float] đúng dim."""
    fake_response = SimpleNamespace(
        data=[{"embedding": [0.1] * EMBEDDING_DIM, "index": 0}]
    )
    with patch(
        "app.services.embedder.litellm.aembedding",
        new=AsyncMock(return_value=fake_response),
    ):
        vec = await embed_text("xin chào")
    assert len(vec) == EMBEDDING_DIM
    assert all(isinstance(x, float) for x in vec)


@pytest.mark.asyncio
async def test_embed_text_empty_raises() -> None:
    """Empty / whitespace text → ValueError (KHÔNG gọi API)."""
    with pytest.raises(ValueError, match="rỗng"):
        await embed_text("")
    with pytest.raises(ValueError, match="rỗng"):
        await embed_text("   ")


@pytest.mark.asyncio
async def test_embed_text_litellm_error_wrapped() -> None:
    """LiteLLM raise (rate limit, network) → EmbedderError wrap."""
    with patch(
        "app.services.embedder.litellm.aembedding",
        new=AsyncMock(side_effect=RuntimeError("rate limit hit")),
    ):
        with pytest.raises(EmbedderError, match="LiteLLM"):
            await embed_text("text")


@pytest.mark.asyncio
async def test_embed_text_wrong_dim_raises() -> None:
    """LiteLLM trả vector dim sai → EmbedderError ('dim sai')."""
    fake_response = SimpleNamespace(
        data=[{"embedding": [0.1] * 512, "index": 0}]  # SAI dim — phải 1536
    )
    with patch(
        "app.services.embedder.litellm.aembedding",
        new=AsyncMock(return_value=fake_response),
    ):
        with pytest.raises(EmbedderError, match="dim sai"):
            await embed_text("text")


@pytest.mark.asyncio
async def test_embed_text_hot_swap_model() -> None:
    """Override model qua arg → litellm.aembedding nhận model arg đó."""
    fake_response = SimpleNamespace(
        data=[{"embedding": [0.2] * EMBEDDING_DIM, "index": 0}]
    )
    mock = AsyncMock(return_value=fake_response)
    with patch("app.services.embedder.litellm.aembedding", new=mock):
        await embed_text("hello", model="gemini/embedding-001")
    # Verify litellm nhận đúng model arg.
    mock.assert_called_once()
    _, kwargs = mock.call_args
    assert kwargs["model"] == "gemini/embedding-001"
    assert kwargs["dimensions"] == EMBEDDING_DIM


@pytest.mark.asyncio
async def test_embed_text_response_missing_data() -> None:
    """LiteLLM return response không có data → EmbedderError."""
    fake_response = SimpleNamespace(data=None)
    with patch(
        "app.services.embedder.litellm.aembedding",
        new=AsyncMock(return_value=fake_response),
    ):
        with pytest.raises(EmbedderError, match="thiếu data"):
            await embed_text("text")


def test_embedding_dim_pinned_1536() -> None:
    """Constant pin 1536 cho R1 mitigation pgvector HNSW index 2000-dim limit."""
    assert EMBEDDING_DIM == 1536
