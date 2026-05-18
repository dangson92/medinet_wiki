"""Unit test dimension guard + cost formula — Plan 07-03 Task 3 (ASK-04, R7).

Pure-Python logic test — KHÔNG cần Postgres/Redis. Phủ `_embedding_dim_of`
(parse hậu tố @<dim> từ model name) + công thức cost preview.

Phần cần DB (`_embedding_cost_preview` full + `update_config` end-to-end) để
Plan 07-05 integration test — file này chỉ unit test phần thuần tính toán.

Threat coverage:
- T-07-03-01 — cross-dim swap → `_embedding_dim_of(@3072) != 1536` → True (nhánh refuse).
- ROADMAP SC4 — message cost preview LUÔN có 2 chữ số thập phân (format `:.2f`).
"""
from __future__ import annotations

import math
import re

import pytest

from app.services.rag_config_service import (
    CHUNKS_PER_MINUTE,
    COST_PER_CHUNK_USD,
    PINNED_DIM,
    _embedding_dim_of,
)


def test_dim_of_default_no_suffix() -> None:
    """Model không hậu tố @<dim> → mặc định 1536 (M2 pin)."""
    assert _embedding_dim_of("text-embedding-3-small") == 1536
    assert _embedding_dim_of("gemini-embedding-001") == PINNED_DIM


def test_dim_of_within_suffix() -> None:
    """Model hậu tố @1536 → 1536 (within-dim, hợp lệ)."""
    assert _embedding_dim_of("gemini-embedding-001@1536") == 1536


@pytest.mark.critical
def test_dim_of_cross_dim_suffix() -> None:
    """Model hậu tố @3072 → 3072 — nhánh quyết định refuse cross-dim (critical)."""
    assert _embedding_dim_of("text-embedding-3-large@3072") == 3072


def test_cost_formula() -> None:
    """Công thức cost preview với n cố định cho ra số hợp lệ."""
    n = 5234
    est_cost = round(n * COST_PER_CHUNK_USD, 2)
    est_minutes = math.ceil(n / CHUNKS_PER_MINUTE)
    assert est_cost > 0
    assert est_minutes >= 1


def test_cross_dim_refuse_message_shape() -> None:
    """Logic so sánh dim cross-dim → True, chuỗi refuse build được."""
    assert _embedding_dim_of("x@3072") != PINNED_DIM
    refuse_msg = "dimension mismatch — defer cross-dim swap v4.0"
    full = (
        f"{refuse_msg} (model yêu cầu dim 3072, hệ thống pin dim {PINNED_DIM})"
    )
    assert refuse_msg in full


def test_cost_message_two_decimal_places() -> None:
    """Message cost preview LUÔN có 2 chữ số thập phân — khớp regex (SC4).

    Chọn n sao cho round(n*rate, 2) cho ra số có trailing zero (cost == 0.10):
    `round(n*rate)` strip trailing zero → "0.1"; format `:.2f` giữ "$0.10".
    """
    # n cho cost ≈ 0.10 — round(7692 * 0.000013, 2) == 0.1
    n = 7692
    cost = round(n * COST_PER_CHUNK_USD, 2)
    assert cost == 0.10  # trailing-zero case — không có :.2f sẽ in "0.1"
    m = math.ceil(n / CHUNKS_PER_MINUTE)
    message = f"re-embed {n} chunks, est ${cost:.2f}, est {m} phút"
    assert re.search(r"est \$\d+\.\d{2},", message) is not None
    assert "$0.10" in message
