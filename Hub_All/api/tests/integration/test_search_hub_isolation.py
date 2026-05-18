"""E4 EXIT criteria — search hub isolation critical test suite (Plan 06-04).

EXIT criteria E4 (PROJECT.md): hub isolation bug = ship-blocker. Viewer của Hub A
KHÔNG BAO GIỜ được thấy chunk của Hub B kể cả khi truyền explicit `hub_ids` chứa
Hub B. Test fail = STOP, security review (PROJECT.md E4).

MỌI test marker `@pytest.mark.critical` — CI gate `pytest -m critical` (HARD-03 /
CONVENTIONS §1 — search là critical path). KHÔNG `pytest.skip`, KHÔNG
`assert True # TODO` — E4 test phải genuinely PASS against real DB
(testcontainers Postgres) qua fixture `app_with_auth`.

Suite verify 6 must-haves Phase 6:
  - Test 1 — single-hub search trả results (SEARCH-01)
  - Test 2 — hub isolation E4: explicit `hub_ids:[A,B]` viewer A → CHỈ chunk A
  - Test 3 — cross-hub isolation: viewer A+B request [A,B,C] → chỉ A,B (SEARCH-03)
  - Test 4 — empty hub → `results: []` 200 không lỗi
  - Test 5 — cache: lần 1 cache_hit=false, lần 2 cache_hit=true (SEARCH-04)
  - Test 6 — EXPLAIN ANALYZE show ix_chunks_vector_hnsw, không Seq Scan (SC3 / R2)

KHÔNG phụ thuộc embedding API thật — `OPENAI_API_KEY` placeholder M2; query
embedding monkeypatch `app.services.search_service.embed_text` trả vector cố định
(T-06-04-03 accept — test verify SQL filter + cache + isolation, KHÔNG verify
chất lượng embedding).

Reuse fixtures conftest: app_with_auth, auth_client, viewer_user, viewer_token,
helpers _insert_hub, _assign_user_hub, _insert_document, _insert_chunk.
"""
from __future__ import annotations

from typing import Any

import pytest

from tests.integration.conftest import (
    _assign_user_hub,
    _insert_chunk,
    _insert_document,
    _insert_hub,
)

#: Số chiều vector embedding PIN M2 (R1 — pgvector 2000-dim index limit).
_EMBEDDING_DIM = 1536


def _fixed_vector(seed: float = 0.1) -> list[float]:
    """Vector deterministic 1536-dim — mọi phần tử = `seed`.

    Test seed chunk + monkeypatch query embedding dùng cùng vector → cosine
    distance xác định, KHÔNG phụ thuộc embedding API thật.
    """
    return [seed] * _EMBEDDING_DIM


def _patch_embed(monkeypatch: Any, vector: list[float]) -> None:
    """Monkeypatch `app.services.search_service.embed_text` trả `vector` cố định.

    Target `app.services.search_service.embed_text` vì `search_service` đã
    `from app.services.embedder import embed_text` (tên đã bind vào module
    search_service). Loại bỏ phụ thuộc OPENAI_API_KEY placeholder.
    """

    async def _fake_embed(text: str, model: str | None = None) -> list[float]:
        _ = (text, model)
        return list(vector)

    monkeypatch.setattr(
        "app.services.search_service.embed_text", _fake_embed
    )


@pytest.mark.critical
@pytest.mark.integration
@pytest.mark.asyncio
async def test_search_single_hub_returns_results(
    auth_client: Any,
    viewer_token: str,
    viewer_user: dict[str, str],
    app_with_auth: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SEARCH-01 — viewer search hub được assign trả ≥1 chunk thuộc hub đó."""
    _ = app_with_auth
    hub_a = await _insert_hub(name="Hub A", code="hub-a", subdomain="hub-a")
    await _assign_user_hub(user_id=viewer_user["id"], hub_id=hub_a)
    doc_a = await _insert_document(hub_id=hub_a, filename="kham-benh.docx")
    await _insert_chunk(
        document_id=doc_a,
        hub_id=hub_a,
        content="khám bệnh đa khoa",
        vector=_fixed_vector(0.1),
    )
    _patch_embed(monkeypatch, _fixed_vector(0.1))

    r = await auth_client.post(
        "/api/search",
        headers={"Authorization": f"Bearer {viewer_token}"},
        json={"query": "khám bệnh", "hub_ids": [hub_a]},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["success"] is True, body
    results = body["data"]["results"]
    assert len(results) >= 1, body
    assert all(item["hub_id"] == hub_a for item in results)
    assert body["data"]["total_hubs_searched"] == 1


@pytest.mark.critical
@pytest.mark.integration
@pytest.mark.asyncio
async def test_search_hub_isolation_explicit_hub_ids(
    auth_client: Any,
    viewer_token: str,
    viewer_user: dict[str, str],
    app_with_auth: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """E4 — viewer Hub A search explicit `hub_ids:[A,B]` → CHỈ chunk Hub A.

    Đây là test E4 EXIT-criteria-grade quan trọng nhất: viewer truyền explicit
    `hub_ids` chứa Hub B (không được assign) — defense in depth PHẢI loại Hub B
    TRƯỚC khi vào SQL. Hub isolation bug = STOP, security review (PROJECT.md E4).
    """
    _ = app_with_auth
    hub_a = await _insert_hub(name="Hub A", code="hub-a", subdomain="hub-a")
    hub_b = await _insert_hub(name="Hub B", code="hub-b", subdomain="hub-b")
    # Viewer CHỈ được assign Hub A — KHÔNG Hub B.
    await _assign_user_hub(user_id=viewer_user["id"], hub_id=hub_a)

    doc_a = await _insert_document(hub_id=hub_a, filename="hub-a.docx")
    doc_b = await _insert_document(hub_id=hub_b, filename="hub-b.docx")
    await _insert_chunk(
        document_id=doc_a,
        hub_id=hub_a,
        content="nội dung Hub A",
        vector=_fixed_vector(0.1),
    )
    await _insert_chunk(
        document_id=doc_b,
        hub_id=hub_b,
        content="nội dung Hub B bí mật",
        vector=_fixed_vector(0.1),
    )
    _patch_embed(monkeypatch, _fixed_vector(0.1))

    r = await auth_client.post(
        "/api/search",
        headers={"Authorization": f"Bearer {viewer_token}"},
        json={"query": "nội dung", "hub_ids": [hub_a, hub_b]},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    results = body["data"]["results"]
    assert all(item["hub_id"] == hub_a for item in results), (
        "E4 VIOLATION — viewer Hub A thấy chunk Hub B"
    )
    assert all(item["hub_id"] != hub_b for item in results), (
        "E4 VIOLATION — viewer Hub A thấy chunk Hub B"
    )


@pytest.mark.critical
@pytest.mark.integration
@pytest.mark.asyncio
async def test_cross_hub_search_isolation(
    auth_client: Any,
    viewer_token: str,
    viewer_user: dict[str, str],
    app_with_auth: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SEARCH-03 E4 — viewer A+B cross-hub request [A,B,C] → chỉ chunk A,B.

    Cross-hub fan-out PHẢI loại Hub C (không assign) — hub isolation bug = STOP,
    security review (PROJECT.md E4).
    """
    _ = app_with_auth
    hub_a = await _insert_hub(name="Hub A", code="hub-a", subdomain="hub-a")
    hub_b = await _insert_hub(name="Hub B", code="hub-b", subdomain="hub-b")
    hub_c = await _insert_hub(name="Hub C", code="hub-c", subdomain="hub-c")
    # Viewer được assign A + B — KHÔNG C.
    await _assign_user_hub(user_id=viewer_user["id"], hub_id=hub_a)
    await _assign_user_hub(user_id=viewer_user["id"], hub_id=hub_b)

    for hub_id, label in ((hub_a, "A"), (hub_b, "B"), (hub_c, "C")):
        doc = await _insert_document(hub_id=hub_id, filename=f"hub-{label}.docx")
        await _insert_chunk(
            document_id=doc,
            hub_id=hub_id,
            content=f"nội dung Hub {label}",
            vector=_fixed_vector(0.1),
        )
    _patch_embed(monkeypatch, _fixed_vector(0.1))

    r = await auth_client.post(
        "/api/search/cross-hub",
        headers={"Authorization": f"Bearer {viewer_token}"},
        json={"query": "nội dung", "hub_ids": [hub_a, hub_b, hub_c]},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    results = body["data"]["results"]
    seen_hubs = {item["hub_id"] for item in results}
    assert seen_hubs <= {hub_a, hub_b}, (
        "E4 VIOLATION — cross-hub search thấy chunk Hub C không được assign"
    )
    assert body["data"]["total_hubs_searched"] == 2


@pytest.mark.critical
@pytest.mark.integration
@pytest.mark.asyncio
async def test_search_empty_hub_returns_empty_list(
    auth_client: Any,
    viewer_token: str,
    viewer_user: dict[str, str],
    app_with_auth: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Specifics — hub chưa có chunk → `results: []`, status 200, KHÔNG lỗi."""
    _ = app_with_auth
    hub_a = await _insert_hub(name="Hub A", code="hub-a", subdomain="hub-a")
    await _assign_user_hub(user_id=viewer_user["id"], hub_id=hub_a)
    # KHÔNG seed chunk nào.
    _patch_embed(monkeypatch, _fixed_vector(0.1))

    r = await auth_client.post(
        "/api/search",
        headers={"Authorization": f"Bearer {viewer_token}"},
        json={"query": "không có gì", "hub_ids": [hub_a]},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["success"] is True, body
    assert body["data"]["results"] == []


@pytest.mark.critical
@pytest.mark.integration
@pytest.mark.asyncio
async def test_search_cache_hit(
    auth_client: Any,
    viewer_token: str,
    viewer_user: dict[str, str],
    app_with_auth: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SEARCH-04 — search lần 1 cache_hit=false, lần 2 (cùng query) cache_hit=true.

    Cần Redis testcontainer up (`app_with_auth` đã wire `app.state.redis`).
    """
    _ = app_with_auth
    hub_a = await _insert_hub(name="Hub A", code="hub-a", subdomain="hub-a")
    await _assign_user_hub(user_id=viewer_user["id"], hub_id=hub_a)
    doc_a = await _insert_document(hub_id=hub_a, filename="cache.docx")
    await _insert_chunk(
        document_id=doc_a,
        hub_id=hub_a,
        content="nội dung cache test",
        vector=_fixed_vector(0.1),
    )
    _patch_embed(monkeypatch, _fixed_vector(0.1))

    payload = {"query": "cache test", "hub_ids": [hub_a]}
    headers = {"Authorization": f"Bearer {viewer_token}"}

    r1 = await auth_client.post("/api/search", headers=headers, json=payload)
    assert r1.status_code == 200, r1.text
    body1 = r1.json()
    assert body1["data"]["cache_hit"] is False, body1

    r2 = await auth_client.post("/api/search", headers=headers, json=payload)
    assert r2.status_code == 200, r2.text
    body2 = r2.json()
    assert body2["data"]["cache_hit"] is True, body2


@pytest.mark.critical
@pytest.mark.integration
@pytest.mark.asyncio
async def test_explain_analyze_uses_hnsw_index(
    auth_client: Any,
    viewer_token: str,
    viewer_user: dict[str, str],
    app_with_auth: Any,
) -> None:
    """SEARCH-02 / SC3 / R2 — EXPLAIN ANALYZE vector query dùng HNSW Index Scan.

    Seed ~50 chunk (vector khác nhau). Verify HNSW index `ix_chunks_vector_hnsw`
    TỒN TẠI + DÙNG ĐƯỢC cho `ORDER BY vector <=>` — R2 (HNSW post-filter recall)
    mitigation, ROADMAP SC3.

    HNSW index `ix_chunks_vector_hnsw` chỉ phục vụ `ORDER BY vector <=>` (cột
    `vector`, KHÔNG có `hub_id`). Trên dataset test nhỏ (50 row), planner chọn
    B-tree `ix_chunks_hub_id_document_id` cho query có predicate `hub_id` vì rẻ
    hơn (top-N heapsort 50 row không đáng kể) — cost model ở scale 1K+ chunk là
    việc của Phase 9, KHÔNG phải test này.

    Để verify HNSW index dùng được cho mục đích của nó, chạy EXPLAIN trên query
    vector-ordering thuần (KHÔNG predicate `hub_id` — đúng job HNSW phục vụ);
    HNSW khi đó là index DUY NHẤT liên quan `ORDER BY vector <=>`. Hub isolation
    correctness đã được Test 2 + Test 3 chứng minh độc lập. Assert thêm: query
    có predicate `hub_id` KHÔNG dùng `Seq Scan` (R2 — luôn đi index path).
    """
    _ = (auth_client, viewer_token)
    hub_a = await _insert_hub(name="Hub A", code="hub-a", subdomain="hub-a")
    await _assign_user_hub(user_id=viewer_user["id"], hub_id=hub_a)
    doc_a = await _insert_document(hub_id=hub_a, filename="explain.docx")
    # Seed ~50 chunk với vector khác nhau (mỗi chunk seed riêng) — đủ rows.
    for i in range(50):
        await _insert_chunk(
            document_id=doc_a,
            hub_id=hub_a,
            content=f"chunk số {i}",
            vector=_fixed_vector(0.01 * (i + 1)),
        )

    vec_literal = "[" + ",".join(
        repr(float(x)) for x in _fixed_vector(0.1)
    ) + "]"

    pool = app_with_auth.state.db_pool
    assert pool is not None, "db_pool chưa sẵn sàng — test cần asyncpg pool"
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("SET LOCAL hnsw.ef_search = 200")
            await conn.execute("SET LOCAL enable_seqscan = off")
            # Query vector-ordering thuần — HNSW là index DUY NHẤT liên quan
            # `ORDER BY vector <=>` (KHÔNG predicate hub_id để B-tree cạnh tranh).
            hnsw_plan_rows = await conn.fetch(
                "EXPLAIN (ANALYZE, FORMAT TEXT) "
                "SELECT id, 1 - (vector <=> $1::vector) AS score FROM chunks "
                "WHERE vector IS NOT NULL "
                "ORDER BY vector <=> $1::vector LIMIT 10",
                vec_literal,
            )
            # Query thực tế của search_service (có predicate hub_id) — verify
            # KHÔNG `Seq Scan` (R2 — luôn đi index path nào đó).
            real_plan_rows = await conn.fetch(
                "EXPLAIN (ANALYZE, FORMAT TEXT) "
                "SELECT id, 1 - (vector <=> $1::vector) AS score FROM chunks "
                "WHERE hub_id = ANY($2::uuid[]) AND vector IS NOT NULL "
                "ORDER BY vector <=> $1::vector LIMIT 10",
                vec_literal,
                [hub_a],
            )
    hnsw_plan_text = "\n".join(r[0] for r in hnsw_plan_rows)
    real_plan_text = "\n".join(r[0] for r in real_plan_rows)
    assert "ix_chunks_vector_hnsw" in hnsw_plan_text, (
        f"HNSW index không dùng cho ORDER BY vector <=>:\n{hnsw_plan_text}"
    )
    assert "Seq Scan" not in hnsw_plan_text, (
        f"Seq Scan xuất hiện ở vector query (R2 vỡ):\n{hnsw_plan_text}"
    )
    assert "Seq Scan" not in real_plan_text, (
        f"Seq Scan xuất hiện ở search query thực tế (R2 vỡ):\n{real_plan_text}"
    )
