"""Fixture eval pipeline smoke regression (Phase 9 EVAL-04 / Plan 09-05).

Bổ sung fixture cho `test_eval_pipeline.py` mà KHÔNG override conftest.py
Phase 4. Mục tiêu pytest smoke regression (CI gate) — chứng minh eval pipeline
KHÔNG vỡ khi merge PR mới, KHÔNG measure gate verdict ≥75% top-3 (đó là track
`make eval-all` Wave 4 với OpenAI key thật).

Fixture chính:
- ``mock_litellm_embed`` (function-scoped) — monkeypatch ``litellm.aembedding``
  trả 1536-dim deterministic vector từ SHA-256 input. Vector KHÔNG có semantic
  (chỉ tránh randomness pure để test reproducible) → CHỈ dùng cho smoke, KHÔNG
  cho verdict.
- ``eval_hub_seeded`` (function-scoped) — INSERT 1 hub ``code='eval-smoke'``
  vào ``hubs`` qua SQLAlchemy async engine, yield ``hub_id`` UUID string, cleanup
  FK cascade sau test (chunks → documents → hub).
- ``eval_admin_login`` (function-scoped) — alias ``admin_token`` cho symmetry
  với eval/lib APIClient.

KHÔNG redeclare ``app_with_auth`` / ``admin_user`` — Phase 4 conftest.py đã có.

Tham chiếu:
- Phase 4 ``test_ingest_e2e.py`` pattern ``_cocoindex_env`` + override ``app_with_auth``.
- ``app.rag.embedder`` wrap ``litellm.aembedding`` (Plan 04-02).
- Search response shape D-10: ``result.title = filename``.
"""
from __future__ import annotations

import hashlib
import uuid
from collections.abc import AsyncIterator
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import text


def _deterministic_embedding(input_text: str, dim: int = 1536) -> list[float]:
    """Sinh vector deterministic từ SHA-256 hash của input.

    KHÔNG dùng cho gate verdict — vector hash-based không có semantic ý nghĩa.
    Chỉ dùng cho smoke regression: cùng input → cùng vector → test reproducible
    (tránh flaky CI khi random seed thay đổi).

    Implementation:
    - Lặp ``sha256(input + counter)`` để pool đủ ``dim*4`` byte.
    - Mỗi 4 byte → 1 unsigned int32 → normalize về ``[-1, 1]``.
    """
    h = hashlib.sha256(input_text.encode("utf-8")).digest()
    out: list[float] = []
    pool = bytearray()
    counter = 0
    while len(out) < dim:
        pool.extend(hashlib.sha256(h + counter.to_bytes(4, "big")).digest())
        counter += 1
        while len(pool) >= 4 and len(out) < dim:
            chunk = bytes(pool[:4])
            pool = pool[4:]
            val = int.from_bytes(chunk, "big", signed=False)
            # Normalize về [-1, 1]
            out.append((val / (2**32 - 1)) * 2 - 1)
    return out[:dim]


@pytest.fixture
def mock_litellm_embed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Monkeypatch ``litellm.aembedding`` trả deterministic 1536-dim vector.

    Side effect: pipeline KHÔNG gọi OpenAI API thật → CI không cần ``OPENAI_API_KEY``,
    test chạy < 60s.

    Response shape khớp OpenAI Embedding API (LiteLLM proxy chuẩn):

    .. code-block:: python

        {
          "data": [{"embedding": [float]*1536, "index": 0, "object": "embedding"}, ...],
          "model": "text-embedding-3-large",
          "object": "list",
          "usage": {"prompt_tokens": N, "total_tokens": N}
        }

    Khớp với Phase 4 ``mock_litellm_embedding`` fixture nhưng dùng deterministic
    seed thay vì ``random.Random(42)`` → reproducible giữa CI run (tránh
    incidental ordering flakiness).
    """

    async def _mock_aembedding(
        model: str = "",
        input: Any = "",  # noqa: A002 — match LiteLLM kwarg name
        **kwargs: Any,
    ) -> Any:
        # LiteLLM accept input là str hoặc list[str]
        if isinstance(input, str):
            inputs = [input]
        elif isinstance(input, list):
            inputs = [str(x) for x in input]
        else:
            inputs = [str(input)]

        dim = int(kwargs.get("dimensions", 1536))
        data = [
            {
                "embedding": _deterministic_embedding(s, dim),
                "index": i,
                "object": "embedding",
            }
            for i, s in enumerate(inputs)
        ]
        # Token count xấp xỉ (LiteLLM heuristic 1 token ≈ 4 char)
        total_tokens = sum(max(1, len(s) // 4) for s in inputs)
        return {
            "data": data,
            "model": model or "text-embedding-3-large",
            "object": "list",
            "usage": {
                "prompt_tokens": total_tokens,
                "total_tokens": total_tokens,
            },
        }

    # Patch cả module-level ``litellm.aembedding`` để cocoindex flow + embedder
    # đều intercept (Phase 4 ``test_ingest_e2e`` cùng pattern).
    monkeypatch.setattr("litellm.aembedding", _mock_aembedding)


@pytest_asyncio.fixture
async def eval_hub_seeded(app_with_auth: Any) -> AsyncIterator[str]:
    """INSERT hub ``code='eval-smoke'`` qua SQLAlchemy async engine → yield hub_id UUID.

    Tái dùng ``app_with_auth`` (đã apply migration head + TRUNCATE per-test) —
    KHÔNG mở connection psycopg riêng (tránh bypass test isolation).

    Cleanup tự FK cascade khi ``app_with_auth`` TRUNCATE ở test sau, nhưng
    fixture cũng DELETE explicit cho idempotency trong cùng module test.
    """
    _ = app_with_auth  # trigger lifespan + migration
    from app.db.session import get_engine

    engine = get_engine()
    hub_id = str(uuid.uuid4())
    code = "eval-smoke"
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO hubs "
                "(id, slug, code, subdomain, name, description, status, "
                "is_active, created_at, updated_at) "
                "VALUES (:id, :slug, :code, :subdomain, :name, NULL, 'active', "
                "TRUE, NOW(), NOW()) "
                "ON CONFLICT (code) DO UPDATE SET is_active = TRUE"
            ),
            {
                "id": hub_id,
                "slug": code,
                "code": code,
                "subdomain": "eval-smoke.medinet.vn",
                "name": "Eval Smoke Hub",
            },
        )
        # Re-fetch trong case ON CONFLICT (hub đã tồn tại từ test trước)
        result = await conn.execute(
            text("SELECT id FROM hubs WHERE code = :code"), {"code": code}
        )
        actual_id = str(result.scalar_one())

    yield actual_id

    # Cleanup explicit — DELETE chunks → documents → hub (FK order).
    # TRUNCATE CASCADE ở app_with_auth (test sau) cũng dọn, nhưng cùng module
    # test cần idempotent re-seed.
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "DELETE FROM chunks WHERE document_id IN "
                    "(SELECT id FROM documents WHERE hub_id = :hid)"
                ),
                {"hid": actual_id},
            )
            await conn.execute(
                text("DELETE FROM documents WHERE hub_id = :hid"),
                {"hid": actual_id},
            )
            await conn.execute(
                text("DELETE FROM hubs WHERE id = :hid"),
                {"hid": actual_id},
            )
    except Exception:  # noqa: BLE001 — best-effort cleanup, fixture đang teardown
        # Cleanup best-effort: nếu engine đã dispose (lifespan shutdown) thì
        # TRUNCATE CASCADE ở test sau sẽ dọn → không raise giữa teardown.
        pass


@pytest.fixture
def eval_admin_login(admin_token: str) -> str:
    """Alias ``admin_token`` cho symmetry với ``eval/lib.APIClient`` naming.

    APIClient eval pattern login → access_token; conftest Phase 3 ``admin_token``
    đã trả access_token đó. Fixture này chỉ rename giúp test_eval_pipeline.py
    đọc rõ ý đồ (smoke pipeline gọi "admin login" giống eval CLI runtime).
    """
    return admin_token
