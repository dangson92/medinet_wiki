"""RAG config hot-swap test suite — Plan 07-05 Task 3 (ASK-04 + R7).

Verify thật trên Postgres testcontainer + app boot:
- Hot-swap LLM provider runtime (KHÔNG restart) → ask call kế dùng provider mới,
  `usage_events.model` phản ánh provider mới (ROADMAP SC3).
- Dimension guard: cross-dim embedding swap → 400 "dimension mismatch";
  within-dim swap → 200 có `cost_preview` + `warning` (R7).
- PUT /api/rag-config admin-only (viewer/editor → 403).

ÁNH XẠ FIELD (D-07-05-E / D-07-04-G): ROADMAP SC3 viết body literal key
`llm_model`, nhưng schema D6 FROZEN (`UpdateRagConfigRequest`) dùng field
`gemini_llm_model`. Test PHẢI gửi `gemini_llm_model` (field thực tế) —
`llm_model` chỉ là cách viết tắt trong ROADMAP, ánh xạ sang `gemini_llm_model`,
KHÔNG có code change.

NOTE — `/api/rag-config` trả RAW JSON (D6), KHÔNG envelope `{success,data,...}`.
Test đọc field trực tiếp: `body["error"]`, `body["cost_preview"]`,
`body["warning"]`, `body["active_llm_provider"]` — KHÔNG `body["data"]`.

DEF-05-01 — file này boot app qua `app_with_auth` → PHẢI chạy 1 FILE/LẦN pytest:

    uv run pytest tests/integration/test_rag_config_hotswap.py

KHÔNG gộp với test_ask_api.py / test_usage_logging.py trong cùng pytest process
(cocoindex `core.Environment` singleton — FAIL `environment already open`).

LLM call MOCK (`mock_llm` fixture — D-07-05-A): OPENAI_API_KEY M2 dev là
placeholder → mock kiểm soát answer + capture `captured_model` (verify model
LiteLLM nhận sau hot-swap).

Reuse fixtures conftest: app_with_auth, auth_client, admin_user/admin_token,
viewer_token/editor_token, mock_llm, _wait_usage_count, helpers seed.
"""
from __future__ import annotations

import re
from typing import Any

import pytest

from tests.integration.conftest import (
    _assign_user_hub,
    _insert_chunk,
    _insert_document,
    _insert_hub,
    _make_vec,
    _wait_usage_count,
)


def _patch_embed(monkeypatch: pytest.MonkeyPatch, vector: list[float]) -> None:
    """Monkeypatch query embedding `app.services.search_service.embed_text`."""

    async def _fake_embed(text: str, model: str | None = None) -> list[float]:
        _ = (text, model)
        return list(vector)

    monkeypatch.setattr(
        "app.services.search_service.embed_text", _fake_embed
    )


async def _seed_hub_chunk(*, user_id: str, code: str) -> str:
    """Seed 1 hub + assign user + 1 document + 1 chunk → hub_id."""
    hub_id = await _insert_hub(name=f"Hub {code}", code=code, subdomain=code)
    await _assign_user_hub(user_id=user_id, hub_id=hub_id)
    doc_id = await _insert_document(hub_id=hub_id, filename=f"{code}.docx")
    await _insert_chunk(
        document_id=doc_id,
        hub_id=hub_id,
        content="Nội dung tài liệu test hot-swap.",
        vector=_make_vec(0.1),
    )
    return hub_id


@pytest.mark.critical
@pytest.mark.integration
@pytest.mark.asyncio
async def test_hotswap_llm_provider(
    auth_client: Any,
    admin_token: str,
    admin_user: dict[str, str],
    app_with_auth: Any,
    mock_llm: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ASK-04 — hot-swap LLM provider runtime → ask call kế dùng provider mới.

    Admin PUT /api/rag-config đổi sang gemini (raw JSON 200). Sau đó POST
    /api/ask → `mock_llm["captured_model"]` chứa "gemini" → hot-swap có hiệu
    lực NGAY câu hỏi kế, KHÔNG cần restart process.
    """
    _ = app_with_auth
    headers = {"Authorization": f"Bearer {admin_token}"}

    r_cfg = await auth_client.put(
        "/api/rag-config",
        headers=headers,
        json={
            "llm_provider": "gemini",
            "gemini_llm_model": "gemini-2.0-flash-lite",
        },
    )
    assert r_cfg.status_code == 200, r_cfg.text
    cfg_body = r_cfg.json()
    # Raw JSON (D6) — KHÔNG envelope. Có `active_llm_provider` HOẶC `message`.
    assert "active_llm_provider" in cfg_body or "message" in cfg_body, cfg_body
    assert cfg_body.get("active_llm_provider") == "gemini", cfg_body

    hub_id = await _seed_hub_chunk(user_id=admin_user["id"], code="hub-hs")
    _patch_embed(monkeypatch, _make_vec(0.1))
    mock_llm["answer"] = "Trả lời sau hot-swap [1]."

    r_ask = await auth_client.post(
        "/api/ask",
        headers=headers,
        json={"query": "Câu hỏi sau swap?", "hub_id": hub_id},
    )
    assert r_ask.status_code == 200, r_ask.text
    captured_model = mock_llm["captured_model"]
    assert captured_model is not None, "mock LLM không nhận model"
    assert "gemini" in captured_model.lower(), (
        f"hot-swap LLM provider KHÔNG phản ánh ở model gửi LLM: {captured_model}"
    )


@pytest.mark.critical
@pytest.mark.integration
@pytest.mark.asyncio
async def test_hotswap_reflected_in_usage_events(
    auth_client: Any,
    admin_token: str,
    admin_user: dict[str, str],
    app_with_auth: Any,
    mock_llm: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ASK-04 / SC3 — sau hot-swap gemini + 1 ask call, usage_events.model chứa gemini.

    Verify hot-swap qua dấu vết bền vững (`usage_events.model`), KHÔNG chỉ ở
    biến runtime. Dùng `_wait_usage_count` chờ BackgroundTask ghi xong
    deterministic trước khi query.
    """
    _ = app_with_auth
    headers = {"Authorization": f"Bearer {admin_token}"}

    r_cfg = await auth_client.put(
        "/api/rag-config",
        headers=headers,
        json={
            "llm_provider": "gemini",
            "gemini_llm_model": "gemini-2.0-flash-lite",
        },
    )
    assert r_cfg.status_code == 200, r_cfg.text

    hub_id = await _seed_hub_chunk(user_id=admin_user["id"], code="hub-us")
    _patch_embed(monkeypatch, _make_vec(0.1))
    mock_llm["answer"] = "Trả lời [1]."

    r_ask = await auth_client.post(
        "/api/ask",
        headers=headers,
        json={"query": "Câu hỏi?", "hub_id": hub_id},
    )
    assert r_ask.status_code == 200, r_ask.text

    pool = app_with_auth.state.db_pool
    assert pool is not None, "db_pool chưa sẵn sàng"
    async with pool.acquire() as conn:
        await _wait_usage_count(conn, 1)
        model = await conn.fetchval(
            "SELECT model FROM usage_events ORDER BY created_at DESC LIMIT 1"
        )
    assert model is not None, "usage_events không có row sau ask call"
    assert "gemini" in str(model).lower(), (
        f"SC3 VIOLATION — usage_events.model không phản ánh hot-swap: {model}"
    )


@pytest.mark.critical
@pytest.mark.integration
@pytest.mark.asyncio
async def test_cross_dim_embedding_swap_refused(
    auth_client: Any,
    admin_token: str,
    app_with_auth: Any,
) -> None:
    """ASK-04 / R7 — cross-dim embedding swap → 400 "dimension mismatch".

    Model `text-embedding-3-large@3072` yêu cầu dim 3072 ≠ pin 1536 → service
    REFUSE 400 (defer cross-dim swap v4.0). Raw JSON: `body["error"]` chứa
    substring "dimension mismatch".
    """
    _ = app_with_auth
    r = await auth_client.put(
        "/api/rag-config",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "embedding_provider": "openai",
            "embedding_model": "text-embedding-3-large@3072",
        },
    )
    assert r.status_code == 400, r.text
    body = r.json()
    assert "error" in body, body
    assert "dimension mismatch" in body["error"], body["error"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_within_dim_embedding_swap_cost_preview(
    auth_client: Any,
    admin_token: str,
    admin_user: dict[str, str],
    app_with_auth: Any,
) -> None:
    """ASK-04 / R7 / SC4 — within-dim embedding swap → 200 cost preview + warning.

    Seed vài chunk trước (để `count(*) > 0`). Swap sang `gemini-embedding-001@1536`
    (dim 1536 = pin) → 200 raw JSON: `cost_preview.message` chứa "re-embed" +
    "phút", khớp regex `est \\$\\d+\\.\\d{2},` (cost LUÔN 2 chữ số — SC4 verbatim);
    `body` có key `warning`.
    """
    _ = app_with_auth
    hub_id = await _insert_hub(name="Hub Cost", code="hub-cost", subdomain="hub-cost")
    doc_id = await _insert_document(hub_id=hub_id, filename="cost.docx")
    for i in range(3):
        await _insert_chunk(
            document_id=doc_id,
            hub_id=hub_id,
            content=f"chunk {i}",
            vector=_make_vec(0.1),
        )
    _ = admin_user

    r = await auth_client.put(
        "/api/rag-config",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "embedding_provider": "gemini",
            "embedding_model": "gemini-embedding-001@1536",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "cost_preview" in body, body
    assert "warning" in body, body
    message = body["cost_preview"]["message"]
    assert "re-embed" in message, message
    assert "phút" in message, message
    assert re.search(r"est \$\d+\.\d{2},", message), (
        f"SC4 — cost preview message thiếu cost 2 chữ số: {message}"
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_rag_config_put_admin_only(
    auth_client: Any,
    viewer_token: str,
    editor_token: str,
    app_with_auth: Any,
) -> None:
    """ASK-04 — PUT /api/rag-config admin-only: viewer + editor → 403.

    rag-config đổi provider/key = thao tác chi phí + bảo mật → chỉ admin.
    """
    _ = app_with_auth
    for label, token in (("viewer", viewer_token), ("editor", editor_token)):
        r = await auth_client.put(
            "/api/rag-config",
            headers={"Authorization": f"Bearer {token}"},
            json={"llm_provider": "gemini"},
        )
        assert r.status_code == 403, f"{label}: {r.text}"
