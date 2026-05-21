"""Fixture Plan 10-03 critical-path acceptance test (HARD-03).

Bổ sung fixture cho ``test_critical_path_coverage.py`` mà KHÔNG override
``conftest.py`` Phase 4. Mục tiêu: 5 acceptance test crisp đáp ứng HARD-03
suite-level — KHÔNG duplicate test detail Phase 3-9 đã có.

Fixture chính:

- ``seeded_two_hubs_with_editor`` (function-scoped) — INSERT 2 hub (A + B) +
  assign editor user vào hub-A + INSERT 1 document vào mỗi hub → yield tuple
  ``(hub_a_id, hub_b_id, doc_a_id, doc_b_id)``. Dùng cho Test 2 (hub isolation
  E4 critical — editor Hub A KHÔNG DELETE được doc Hub B).
- ``mock_litellm_citation_response`` (function-scoped) — monkeypatch
  ``litellm.acompletion`` trả LiteLLM ``ModelResponse`` shape với content
  ``"Theo tài liệu, A là B [1]. Còn C [2]."``. Dùng cho Test 5 (citation
  parsing deterministic — KHÔNG cần OpenAI key thật).
- ``mock_cocoindex_app_noop`` (function-scoped) — gắn mock ``cocoindex_app``
  vào ``app.state.cocoindex_app`` để upload BackgroundTask
  ``trigger_cocoindex_update`` chạy sạch. Dùng cho Test 3 (VN filename
  roundtrip — focus UTF-8 preservation, KHÔNG focus chunking flow).

KHÔNG redeclare ``app_with_auth`` / ``admin_user`` / ``editor_user`` /
``viewer_user`` — Phase 3 conftest.py đã có.

Tham chiếu:

- Phase 5 ``test_hub_isolation.py`` pattern ``MockCocoindexApp``.
- Phase 7 ``mock_llm`` conftest fixture pattern ``litellm.acompletion`` monkey.
- Phase 8 ``test_vietnamese_filename.py`` pattern ``_MockCocoindexApp``.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
import pytest_asyncio

from tests.integration.conftest import (
    _assign_user_hub,
    _insert_document,
    _insert_hub,
)


class _MockCocoindexAppHardening:
    """Mock ``coco.App`` — ``update_blocking`` no-op cho test Phase 10.

    Test 3 (VN filename) focus filename UTF-8 roundtrip — KHÔNG cần cocoindex
    runtime tạo chunks thật. Test 2 (hub isolation DELETE) upload qua admin
    cũng dùng mock (chỉ cần document row tồn tại để DELETE).
    """

    def __init__(self) -> None:
        self.update_blocking_calls: int = 0

    def update_blocking(self) -> None:
        self.update_blocking_calls += 1


@pytest.fixture
def mock_cocoindex_app_noop(app_with_auth: Any) -> _MockCocoindexAppHardening:
    """Gắn mock cocoindex_app vào ``app.state.cocoindex_app`` (no-op flow).

    Dùng cho Test 2 / Test 3 / Test 4 / Test 5 — KHÔNG cần cocoindex runtime
    thật (test 5 acceptance là contract-level, KHÔNG ingest flow E2E).
    """
    mock = _MockCocoindexAppHardening()
    app_with_auth.state.cocoindex_app = mock
    return mock


@pytest_asyncio.fixture
async def seeded_two_hubs_with_editor(
    app_with_auth: Any,
    editor_user: dict[str, str],
    mock_cocoindex_app_noop: _MockCocoindexAppHardening,
) -> dict[str, str]:
    """Seed 2 hub (A+B) + assign editor vào hub-A + 1 document/hub.

    Trả dict ``{hub_a_id, hub_b_id, doc_a_id, doc_b_id, editor_id}`` — Test 2
    (hub isolation E4) dùng để verify editor Hub A DELETE doc Hub B → 403.

    ``mock_cocoindex_app_noop`` đảm bảo BackgroundTask trigger_cocoindex_update
    KHÔNG no-op fail khi router/service gọi update_blocking.
    """
    _ = (app_with_auth, mock_cocoindex_app_noop)

    hub_a = await _insert_hub(name="Hub A", code="hub-a", subdomain="hub-a")
    hub_b = await _insert_hub(name="Hub B", code="hub-b", subdomain="hub-b")
    await _assign_user_hub(user_id=editor_user["id"], hub_id=hub_a)

    doc_a = await _insert_document(hub_id=hub_a, filename="hub-a-doc.docx")
    doc_b = await _insert_document(hub_id=hub_b, filename="hub-b-doc.docx")

    return {
        "hub_a_id": hub_a,
        "hub_b_id": hub_b,
        "doc_a_id": doc_a,
        "doc_b_id": doc_b,
        "editor_id": editor_user["id"],
    }


@pytest.fixture
def mock_litellm_citation_response(
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, Any]:
    """Monkeypatch ``litellm.acompletion`` + ``litellm.completion_cost``.

    Trả ``ModelResponse`` shape ``SimpleNamespace`` cấp đủ:

    - ``resp.choices[0].message.content`` = ``"Theo tài liệu, A là B [1]. Còn C [2]."``
    - ``resp.usage.prompt_tokens`` / ``completion_tokens`` / ``total_tokens``

    ``AskService._call_llm`` đọc ``resp.choices[0].message.content``;
    ``AskService._extract_usage`` đọc ``resp.usage.*``. Mock cấu trúc khớp
    Phase 7 ``mock_llm`` conftest fixture (tái dùng pattern).

    Trả dict ``state`` để test customize:
    - ``state["answer"]`` — content LLM trả về (default citation 2 marker).
    - ``state["captured_messages"]`` — list message gửi cho LLM (verify
      anti-injection prompt được chèn).

    KHÔNG dùng OpenAI key thật — CI gate KHÔNG cần ``OPENAI_API_KEY``.
    """
    state: dict[str, Any] = {
        "answer": "Theo tài liệu, A là B [1]. Còn C [2].",
        "captured_messages": None,
        "captured_model": None,
    }

    async def _fake_acompletion(
        *, model: str, messages: list[dict[str, str]], **kw: Any
    ) -> Any:
        _ = kw
        state["captured_messages"] = messages
        state["captured_model"] = model
        msg = SimpleNamespace(content=state["answer"])
        choice = SimpleNamespace(message=msg)
        usage = SimpleNamespace(
            prompt_tokens=100,
            completion_tokens=20,
            total_tokens=120,
        )
        return SimpleNamespace(choices=[choice], usage=usage)

    def _fake_cost(*a: Any, **kw: Any) -> float:
        _ = (a, kw)
        return 0.0012

    monkeypatch.setattr("litellm.acompletion", _fake_acompletion)
    monkeypatch.setattr("litellm.completion_cost", _fake_cost)
    return state
