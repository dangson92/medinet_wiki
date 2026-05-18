"""Unit test ai_chat router — Plan 08-02 Task 2 (COMPAT-01, BLOCKER /api/ai/chat).

Pure-Python logic test — KHÔNG cần Postgres/Redis/FastAPI app. Phủ hàm lõi
`run_ai_chat` (gọi LLM proxy cho GeminiAssistant) qua `monkeypatch` mock
`litellm.acompletion`:

- messages rỗng → 400 envelope error.code = "INVALID_REQUEST".
- acompletion mock trả completion giả → 200 envelope data.response string.
- acompletion raise → 500 envelope error.code = "LLM_FAILED" (không leak stack).
- system_instruction prepend vào llm_messages role "system".

Threat coverage (xem `<threat_model>` Plan 08-02):
- T-08-02-04 — LLM lỗi → envelope LLM_FAILED message generic, không leak trace.
"""
from __future__ import annotations

import json
from typing import Any

import pytest

from app.routers.ai_chat import AiChatMessage, AiChatRequest, run_ai_chat


def _body(content: str) -> dict[str, Any]:
    """Parse JSONResponse body về dict."""
    return content  # placeholder — overridden bên dưới


def _decode(resp: Any) -> dict[str, Any]:
    """Trích envelope dict từ JSONResponse."""
    return json.loads(resp.body)


class _FakeMessage:
    def __init__(self, content: str | None) -> None:
        self.content = content


class _FakeChoice:
    def __init__(self, content: str | None) -> None:
        self.message = _FakeMessage(content)


class _FakeCompletion:
    """Mô phỏng litellm ModelResponse — đủ `.choices[0].message.content`."""

    def __init__(self, content: str | None) -> None:
        self.choices = [_FakeChoice(content)]


@pytest.mark.asyncio
async def test_empty_messages_returns_400() -> None:
    """messages rỗng → 400 envelope error.code INVALID_REQUEST."""
    body = AiChatRequest(messages=[])
    resp = await run_ai_chat(body)
    assert resp.status_code == 400
    env = _decode(resp)
    assert env["success"] is False
    assert env["error"]["code"] == "INVALID_REQUEST"


@pytest.mark.asyncio
@pytest.mark.critical
async def test_chat_success_returns_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """acompletion mock trả completion giả → 200 envelope data.response string."""

    async def _fake_acompletion(*, model: str, messages: list[Any]) -> Any:
        assert isinstance(model, str) and model
        return _FakeCompletion("Xin chào, tôi là trợ lý Medinet.")

    monkeypatch.setattr("app.routers.ai_chat.litellm.acompletion", _fake_acompletion)

    body = AiChatRequest(
        messages=[AiChatMessage(role="user", content="Chào bạn")],
        system_instruction="Bạn là trợ lý.",
    )
    resp = await run_ai_chat(body)
    assert resp.status_code == 200
    env = _decode(resp)
    assert env["success"] is True
    assert env["data"]["response"] == "Xin chào, tôi là trợ lý Medinet."


@pytest.mark.asyncio
async def test_llm_failure_returns_500_llm_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """acompletion raise → 500 envelope error.code LLM_FAILED, message generic."""

    async def _raise_acompletion(*, model: str, messages: list[Any]) -> Any:
        raise RuntimeError("provider key sai — chi tiet nhay cam KHONG duoc leak")

    monkeypatch.setattr(
        "app.routers.ai_chat.litellm.acompletion", _raise_acompletion
    )

    body = AiChatRequest(
        messages=[AiChatMessage(role="user", content="Câu hỏi")],
    )
    resp = await run_ai_chat(body)
    assert resp.status_code == 500
    env = _decode(resp)
    assert env["success"] is False
    assert env["error"]["code"] == "LLM_FAILED"
    # Không leak stack trace / chi tiết provider trong message.
    assert "key sai" not in env["error"]["message"]


@pytest.mark.asyncio
async def test_system_instruction_prepended(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """system_instruction → prepend message role 'system' đầu danh sách llm_messages."""
    captured: dict[str, Any] = {}

    async def _capture_acompletion(*, model: str, messages: list[Any]) -> Any:
        captured["messages"] = messages
        return _FakeCompletion("ok")

    monkeypatch.setattr(
        "app.routers.ai_chat.litellm.acompletion", _capture_acompletion
    )

    body = AiChatRequest(
        messages=[AiChatMessage(role="user", content="Hỏi")],
        system_instruction="Hướng dẫn hệ thống",
    )
    await run_ai_chat(body)
    msgs = captured["messages"]
    assert msgs[0] == {"role": "system", "content": "Hướng dẫn hệ thống"}
    assert msgs[1]["role"] == "user"
    assert msgs[1]["content"] == "Hỏi"


@pytest.mark.asyncio
async def test_model_role_normalized_to_assistant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """role 'model' (Gemini convention frontend) → chuẩn hoá 'assistant' cho LiteLLM."""
    captured: dict[str, Any] = {}

    async def _capture_acompletion(*, model: str, messages: list[Any]) -> Any:
        captured["messages"] = messages
        return _FakeCompletion("ok")

    monkeypatch.setattr(
        "app.routers.ai_chat.litellm.acompletion", _capture_acompletion
    )

    body = AiChatRequest(
        messages=[
            AiChatMessage(role="user", content="Câu 1"),
            AiChatMessage(role="model", content="Trả lời 1"),
            AiChatMessage(role="user", content="Câu 2"),
        ],
    )
    await run_ai_chat(body)
    roles = [m["role"] for m in captured["messages"]]
    assert roles == ["user", "assistant", "user"]
