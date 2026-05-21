"""Unit test eval/metrics.py — pure compute, không cần backend (Phase 9 EVAL-02)."""
from __future__ import annotations

import pytest

from eval.metrics import compute_latency_percentiles, compute_retrieval_metrics


@pytest.mark.critical
def test_top_1_hit_perfect():
    queries = [{"id": "q1", "query": "x", "expected_doc_id": "doc-A.docx"}]
    results = [{"results": [{"title": "doc-A.docx", "score": 0.9}]}]
    m = compute_retrieval_metrics(queries, results)
    assert m["top_1_hit_rate"] == 1.0
    assert m["top_3_hit_rate"] == 1.0
    assert m["top_5_hit_rate"] == 1.0
    assert m["mrr"] == 1.0
    assert m["per_query"][0]["rank"] == 1


@pytest.mark.critical
def test_top_3_hit_rank_2():
    queries = [{"id": "q1", "query": "x", "expected_doc_id": "doc-A.docx"}]
    results = [
        {
            "results": [
                {"title": "doc-B.docx", "score": 0.95},
                {"title": "doc-A.docx", "score": 0.80},
                {"title": "doc-C.docx", "score": 0.70},
            ]
        }
    ]
    m = compute_retrieval_metrics(queries, results)
    assert m["top_1_hit_rate"] == 0.0
    assert m["top_3_hit_rate"] == 1.0
    assert m["top_5_hit_rate"] == 1.0
    assert m["mrr"] == 0.5
    assert m["per_query"][0]["rank"] == 2


@pytest.mark.critical
def test_no_match():
    queries = [{"id": "q1", "query": "x", "expected_doc_id": "doc-A.docx"}]
    results = [{"results": [{"title": "other.docx"}, {"title": "another.docx"}]}]
    m = compute_retrieval_metrics(queries, results)
    assert m["top_1_hit_rate"] == 0.0
    assert m["top_3_hit_rate"] == 0.0
    assert m["mrr"] == 0.0
    assert m["per_query"][0]["rank"] is None


def test_three_query_mix():
    queries = [
        {"id": "q1", "query": "x", "expected_doc_id": "A.docx"},
        {"id": "q2", "query": "y", "expected_doc_id": "B.docx"},
        {"id": "q3", "query": "z", "expected_doc_id": "C.docx"},
    ]
    results = [
        {"results": [{"title": "A.docx"}]},                          # rank 1
        {"results": [{"title": "X.docx"}, {"title": "B.docx"}]},     # rank 2
        {"results": [{"title": "X.docx"}, {"title": "Y.docx"}]},     # miss
    ]
    m = compute_retrieval_metrics(queries, results)
    assert m["top_1_hit_rate"] == pytest.approx(1 / 3)
    assert m["top_3_hit_rate"] == pytest.approx(2 / 3)
    assert m["top_5_hit_rate"] == pytest.approx(2 / 3)
    assert m["mrr"] == pytest.approx((1 + 0.5 + 0) / 3)


def test_case_insensitive_match():
    queries = [{"id": "q1", "query": "x", "expected_doc_id": "DMD_T1-01.docx"}]
    results = [{"results": [{"title": "dmd_t1-01.DOCX"}]}]
    m = compute_retrieval_metrics(queries, results)
    assert m["top_1_hit_rate"] == 1.0  # case-insensitive


@pytest.mark.critical
def test_latency_percentiles_12_samples():
    lat = [100.0, 110.0, 120.0, 130.0, 140.0, 150.0, 160.0, 170.0,
           180.0, 190.0, 200.0, 210.0]
    p = compute_latency_percentiles(lat)
    assert p["count"] == 12
    assert p["mean_ms"] == pytest.approx(155.0)
    # p50 = median = 155 (statistics.quantiles n=100 với 12 sample method
    # exclusive default)
    assert p["p50_ms"] == pytest.approx(155.0)
    # p95/p99 extrapolate linear (exclusive method, n<100) — có thể vượt max
    # sample vì cutpoint position > n. Đây là behavior chuẩn stdlib —
    # eval thật chạy 12 query 1 lần đủ smoke; production scale 100+ query
    # sẽ không extrapolate vì position ≤ n.
    assert p["p95_ms"] >= 200.0  # p95 phải > 200 (sample lớn nhất là 210)
    assert p["p99_ms"] >= p["p95_ms"]  # p99 ≥ p95 (monotone)
    assert p["p99_ms"] < 250.0  # extrapolate không quá xa (sanity)


def test_latency_empty():
    p = compute_latency_percentiles([])
    assert p == {
        "count": 0,
        "mean_ms": 0.0,
        "p50_ms": 0.0,
        "p95_ms": 0.0,
        "p99_ms": 0.0,
    }


def test_latency_single_sample():
    p = compute_latency_percentiles([100.0])
    assert p["count"] == 1
    assert p["p50_ms"] == 100.0
    assert p["p99_ms"] == 100.0


def test_empty_queries():
    m = compute_retrieval_metrics([], [])
    assert m["top_1_hit_rate"] == 0.0
    assert m["per_query"] == []


def test_mismatch_length_raises():
    with pytest.raises(ValueError):
        compute_retrieval_metrics([{"id": "q1"}], [])
