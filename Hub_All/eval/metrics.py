"""Eval metrics — top-K hit rate + MRR + latency percentile (pure Python stdlib).

Phase 9 EVAL-02.
M2-specific match: result.title.lower() == expected_doc_id.lower() (D-10).
KHÔNG dùng category (Go cũ luôn None).

Stdlib only — `statistics.quantiles(n=100)` Python 3.8+ đủ cho 12 query
latency. KHÔNG dep numpy.
"""
from __future__ import annotations

import statistics
from typing import Any


def compute_retrieval_metrics(
    queries: list[dict],
    per_query_results: list[dict],
) -> dict:
    """Compute top-K hit rate + MRR.

    Args:
        queries: list[{id, query, expected_doc_id, expected_section, hub_id, notes}]
        per_query_results: list[{results: list[{title, score, ...}]}]
            (cùng độ dài, cùng thứ tự với queries).

    Returns:
        {top_1_hit_rate, top_3_hit_rate, top_5_hit_rate, mrr, per_query}
        per_query: list[{id, query, expected_doc_id, rank: int|None,
                         top_result_title, result_count}]
    """
    n = len(queries)
    if n == 0:
        return {
            "top_1_hit_rate": 0.0,
            "top_3_hit_rate": 0.0,
            "top_5_hit_rate": 0.0,
            "mrr": 0.0,
            "per_query": [],
        }
    if len(per_query_results) != n:
        raise ValueError(
            f"queries len ({n}) != per_query_results len "
            f"({len(per_query_results)})"
        )

    hits_at_1 = hits_at_3 = hits_at_5 = 0
    rr_sum = 0.0
    per_query: list[dict] = []

    for q, r in zip(queries, per_query_results, strict=True):
        expected = (q.get("expected_doc_id") or "").lower()
        results = r.get("results", []) or []
        rank: int | None = None
        for idx, res in enumerate(results, 1):
            # M2 D-10: title = filename (KHÔNG dùng category)
            title = (res.get("title") or "").lower()
            if title == expected:
                rank = idx
                break

        if rank == 1:
            hits_at_1 += 1
        if rank is not None and rank <= 3:
            hits_at_3 += 1
        if rank is not None and rank <= 5:
            hits_at_5 += 1
        if rank is not None:
            rr_sum += 1.0 / rank

        per_query.append(
            {
                "id": q.get("id"),
                "query": q.get("query"),
                "expected_doc_id": q.get("expected_doc_id"),
                "rank": rank,
                "top_result_title": (
                    results[0].get("title") if results else None
                ),
                "result_count": len(results),
            }
        )

    return {
        "top_1_hit_rate": hits_at_1 / n,
        "top_3_hit_rate": hits_at_3 / n,
        "top_5_hit_rate": hits_at_5 / n,
        "mrr": rr_sum / n,
        "per_query": per_query,
    }


def compute_latency_percentiles(latencies_ms: list[float]) -> dict[str, Any]:
    """Compute p50/p95/p99 latency từ list ms.

    Stdlib only (statistics.quantiles n=100). KHÔNG dep numpy.
    Edge case: empty list → zeros (NOT raise). 1 sample → all percentiles == sample.
    """
    if not latencies_ms:
        return {
            "count": 0,
            "mean_ms": 0.0,
            "p50_ms": 0.0,
            "p95_ms": 0.0,
            "p99_ms": 0.0,
        }

    sorted_lat = sorted(latencies_ms)
    n = len(sorted_lat)
    if n == 1:
        v = sorted_lat[0]
        return {
            "count": 1,
            "mean_ms": v,
            "p50_ms": v,
            "p95_ms": v,
            "p99_ms": v,
        }

    # statistics.quantiles(n=100) → 99 cutpoint chia thành 100 phần bằng nhau.
    # quantiles[i-1] = percentile i (i từ 1 đến 99).
    qs = statistics.quantiles(sorted_lat, n=100)
    return {
        "count": n,
        "mean_ms": statistics.fmean(sorted_lat),
        "p50_ms": qs[49],  # index 49 = percentile 50
        "p95_ms": qs[94],  # percentile 95
        "p99_ms": qs[98],  # percentile 99
    }
