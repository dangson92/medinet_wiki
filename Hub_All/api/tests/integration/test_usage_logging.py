"""Usage logging test suite — Plan 07-05 Task 4 (ASK-05 token usage).

Verify thật trên Postgres testcontainer + app boot:
- 10 ask call → 10 row usage_events (ROADMAP SC5) — verify DETERMINISTIC qua
  helper `_wait_usage_count` (D-07-05-B: poll có giới hạn ~2s, KHÔNG sleep cố
  định chống flaky BackgroundTask timing qua ASGITransport).
- usage_events PII-safe — schema chỉ token/model/id, KHÔNG cột nội dung query/answer.
- GET /api/usage list event + `?group_by=model` aggregate (SC5 URL literal).
- GET /api/usage/stats aggregate nhất quán.
- /api/usage admin-only (viewer → 403).

LLM call MOCK (`mock_llm` fixture — D-07-05-A): mock trả token cố định
(prompt=120, completion=40, total=160) → verify token ghi đúng.

DEF-05-01 — file này boot app qua `app_with_auth` → PHẢI chạy 1 FILE/LẦN pytest:

    uv run pytest tests/integration/test_usage_logging.py

KHÔNG gộp với test_ask_api.py / test_rag_config_hotswap.py trong cùng pytest
process (cocoindex `core.Environment` singleton — FAIL `environment already open`).

Reuse fixtures conftest: app_with_auth, auth_client, admin_user/admin_token,
viewer_token, mock_llm, _wait_usage_count, helpers seed.
"""
from __future__ import annotations

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


async def _seed_hub_chunks(*, user_id: str, code: str, n_chunks: int = 2) -> str:
    """Seed 1 hub + assign user + 1 document + N chunk → hub_id."""
    hub_id = await _insert_hub(name=f"Hub {code}", code=code, subdomain=code)
    await _assign_user_hub(user_id=user_id, hub_id=hub_id)
    doc_id = await _insert_document(hub_id=hub_id, filename=f"{code}.docx")
    for i in range(n_chunks):
        await _insert_chunk(
            document_id=doc_id,
            hub_id=hub_id,
            content=f"Nội dung đoạn {i}.",
            vector=_make_vec(0.1),
        )
    return hub_id


async def _ask_n_times(
    auth_client: Any, token: str, hub_id: str, n: int
) -> None:
    """Gọi POST /api/ask `n` lần — mỗi call assert 200."""
    headers = {"Authorization": f"Bearer {token}"}
    for i in range(n):
        r = await auth_client.post(
            "/api/ask",
            headers=headers,
            json={"query": f"Câu hỏi số {i}?", "hub_id": hub_id},
        )
        assert r.status_code == 200, r.text


@pytest.mark.critical
@pytest.mark.integration
@pytest.mark.asyncio
async def test_ten_ask_calls_create_ten_usage_rows(
    auth_client: Any,
    admin_token: str,
    admin_user: dict[str, str],
    app_with_auth: Any,
    mock_llm: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ASK-05 / SC5 — 10 ask call → đúng 10 row usage_events (deterministic).

    Gọi POST /api/ask 10 lần. Dùng `_wait_usage_count(conn, 10)` (poll có giới
    hạn ~2s — D-07-05-B) chờ BackgroundTask ghi xong RỒI assert count == 10.
    Query 1 row verify cột NOT NULL + token từ mock (120/40/160).
    """
    _ = app_with_auth
    hub_id = await _seed_hub_chunks(user_id=admin_user["id"], code="hub-10")
    _patch_embed(monkeypatch, _make_vec(0.1))
    mock_llm["answer"] = "trả lời [1]"

    await _ask_n_times(auth_client, admin_token, hub_id, 10)

    pool = app_with_auth.state.db_pool
    assert pool is not None, "db_pool chưa sẵn sàng"
    async with pool.acquire() as conn:
        count = await _wait_usage_count(conn, 10)
        assert count == 10, f"SC5 VIOLATION — kỳ vọng 10 row, có {count}"
        row = await conn.fetchrow(
            "SELECT user_id, hub_id, model, prompt_tokens, completion_tokens, "
            "total_tokens, request_id FROM usage_events "
            "ORDER BY created_at DESC LIMIT 1"
        )
    assert row is not None
    assert row["user_id"] is not None, "user_id NULL"
    assert row["hub_id"] is not None, "hub_id NULL"
    assert row["model"], "model rỗng/NULL"
    assert row["request_id"] is not None, "request_id NULL"
    # Token từ mock make_fake_completion (prompt=120, completion=40, total=160).
    assert row["prompt_tokens"] == 120, row["prompt_tokens"]
    assert row["completion_tokens"] == 40, row["completion_tokens"]
    assert row["total_tokens"] == 160, row["total_tokens"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_usage_row_has_no_pii(
    auth_client: Any,
    admin_token: str,
    admin_user: dict[str, str],
    app_with_auth: Any,
    mock_llm: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ASK-05 T-07-05-02 — usage_events KHÔNG chứa PII (query/answer text).

    Sau 1 ask call, lấy danh sách cột thực tế của bảng `usage_events` từ
    `information_schema` → assert KHÔNG có cột text nội dung (query/answer/
    prompt_text/content). Schema PII-safe by design — chỉ token count + model + id.
    """
    _ = app_with_auth
    hub_id = await _seed_hub_chunks(user_id=admin_user["id"], code="hub-pii")
    _patch_embed(monkeypatch, _make_vec(0.1))
    mock_llm["answer"] = "trả lời [1]"

    await _ask_n_times(auth_client, admin_token, hub_id, 1)

    pool = app_with_auth.state.db_pool
    async with pool.acquire() as conn:
        await _wait_usage_count(conn, 1)
        col_rows = await conn.fetch(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'usage_events'"
        )
    columns = {str(r["column_name"]) for r in col_rows}
    expected = {
        "id", "user_id", "hub_id", "model", "prompt_tokens",
        "completion_tokens", "total_tokens", "cost_usd", "request_id",
        "created_at",
    }
    assert columns == expected, (
        f"usage_events có cột ngoài dự kiến (PII risk?): {columns - expected}"
    )
    pii_columns = {"query", "answer", "prompt_text", "content", "question"}
    assert not (columns & pii_columns), (
        f"PII VIOLATION — usage_events có cột nội dung: {columns & pii_columns}"
    )


@pytest.mark.critical
@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_usage_endpoint_returns_events(
    auth_client: Any,
    admin_token: str,
    admin_user: dict[str, str],
    app_with_auth: Any,
    mock_llm: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ASK-05 — sau 3 ask call, GET /api/usage trả list event ≥ 3 phần tử.

    Mỗi event có `model`, `total_tokens`, `provider`, `operation=="ask"`.
    """
    _ = app_with_auth
    hub_id = await _seed_hub_chunks(user_id=admin_user["id"], code="hub-ev")
    _patch_embed(monkeypatch, _make_vec(0.1))
    mock_llm["answer"] = "trả lời [1]"
    headers = {"Authorization": f"Bearer {admin_token}"}

    await _ask_n_times(auth_client, admin_token, hub_id, 3)
    pool = app_with_auth.state.db_pool
    async with pool.acquire() as conn:
        await _wait_usage_count(conn, 3)

    r = await auth_client.get("/api/usage", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["success"] is True, body
    events = body["data"]
    assert isinstance(events, list) and len(events) >= 3, body
    for ev in events:
        assert ev["model"], ev
        assert isinstance(ev["total_tokens"], int), ev
        assert ev["provider"], ev
        assert ev["operation"] == "ask", ev


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_usage_group_by_model(
    auth_client: Any,
    admin_token: str,
    admin_user: dict[str, str],
    app_with_auth: Any,
    mock_llm: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ASK-05 / SC5 — GET /api/usage?group_by=model trả aggregate (URL literal).

    Sau N ask call, GET `/api/usage?group_by=model` → envelope `data` có key
    `by_model` (list không rỗng) + `total_calls == N` (D-07-02-D — group_by
    delegate sang aggregate_usage).
    """
    _ = app_with_auth
    n = 4
    hub_id = await _seed_hub_chunks(user_id=admin_user["id"], code="hub-gb")
    _patch_embed(monkeypatch, _make_vec(0.1))
    mock_llm["answer"] = "trả lời [1]"
    headers = {"Authorization": f"Bearer {admin_token}"}

    await _ask_n_times(auth_client, admin_token, hub_id, n)
    pool = app_with_auth.state.db_pool
    async with pool.acquire() as conn:
        await _wait_usage_count(conn, n)

    r = await auth_client.get(
        "/api/usage?group_by=model", headers=headers
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert isinstance(data["by_model"], list) and data["by_model"], data
    assert data["total_calls"] == n, data


@pytest.mark.critical
@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_usage_stats_aggregate(
    auth_client: Any,
    admin_token: str,
    admin_user: dict[str, str],
    app_with_auth: Any,
    mock_llm: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ASK-05 — GET /api/usage/stats aggregate đúng sau N ask call.

    `data["total_calls"] == N`, `by_model` không rỗng, `total_tokens > 0`.
    `/stats` và `?group_by=model` cùng gọi `aggregate_usage` → nhất quán.
    """
    _ = app_with_auth
    n = 5
    hub_id = await _seed_hub_chunks(user_id=admin_user["id"], code="hub-st")
    _patch_embed(monkeypatch, _make_vec(0.1))
    mock_llm["answer"] = "trả lời [1]"
    headers = {"Authorization": f"Bearer {admin_token}"}

    await _ask_n_times(auth_client, admin_token, hub_id, n)
    pool = app_with_auth.state.db_pool
    async with pool.acquire() as conn:
        await _wait_usage_count(conn, n)

    r = await auth_client.get("/api/usage/stats", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["total_calls"] == n, data
    assert isinstance(data["by_model"], list) and data["by_model"], data
    assert data["total_tokens"] > 0, data
    # N call × 160 token/call (mock) → tổng token xác định.
    assert data["total_tokens"] == n * 160, data


@pytest.mark.integration
@pytest.mark.asyncio
async def test_usage_endpoint_admin_only(
    auth_client: Any,
    viewer_token: str,
    app_with_auth: Any,
) -> None:
    """ASK-05 T-07-02-02 — GET /api/usage admin-only: viewer → 403.

    Token usage là dữ liệu chi phí → chỉ admin xem (nhất quán audit-logs).
    """
    _ = app_with_auth
    r = await auth_client.get(
        "/api/usage",
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert r.status_code == 403, r.text
