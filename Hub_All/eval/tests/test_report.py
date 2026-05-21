"""Unit test eval/report.py — gate verdict logic + Markdown integrity (Phase 9 EVAL-03).

Cover 3 verdict case core (PASS / FAIL borderline / FAIL trigger_e5) + boundary
exact (0.75 PASS, 0.60 không E5) + Markdown integrity (7 section header + MISS
marker + latency budget warning) + CLI ``main()`` write file + exit code đúng.

KHÔNG cần backend chạy — pure compute test (sample results dict tay).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from eval.report import gate_verdict, generate_eval_md, main

# ---------------------------------------------------------------------------
# gate_verdict — 3 case core + 3 boundary
# ---------------------------------------------------------------------------


@pytest.mark.critical
def test_gate_verdict_pass():
    """top_3 = 0.80 → PASS exit 0, không trigger_e5."""
    v = gate_verdict(0.80)
    assert v == {"verdict": "PASS", "exit_code": 0, "trigger_e5": False}


@pytest.mark.critical
def test_gate_verdict_fail_borderline():
    """top_3 = 0.70 (borderline 0.60-0.75) → FAIL exit 1, không trigger_e5."""
    v = gate_verdict(0.70)
    assert v == {"verdict": "FAIL", "exit_code": 1, "trigger_e5": False}


@pytest.mark.critical
def test_gate_verdict_fail_critical_triggers_e5():
    """top_3 = 0.50 (<0.60) → FAIL exit 1 + trigger_e5 True (PROJECT EXIT E5)."""
    v = gate_verdict(0.50)
    assert v == {"verdict": "FAIL", "exit_code": 1, "trigger_e5": True}


def test_gate_verdict_boundary_pass_exact_075():
    """top_3 = 0.75 exact → PASS (ranh giới INCLUSIVE)."""
    v = gate_verdict(0.75)
    assert v["verdict"] == "PASS"
    assert v["exit_code"] == 0
    assert v["trigger_e5"] is False


def test_gate_verdict_boundary_e5_exact_060():
    """top_3 = 0.60 exact → FAIL nhưng KHÔNG trigger_e5 (≥0.60 boundary)."""
    v = gate_verdict(0.60)
    assert v["verdict"] == "FAIL"
    assert v["exit_code"] == 1
    assert v["trigger_e5"] is False


def test_gate_verdict_just_below_060():
    """top_3 = 0.599 (just below 0.60) → trigger_e5 True."""
    v = gate_verdict(0.599)
    assert v["trigger_e5"] is True


# ---------------------------------------------------------------------------
# Helper sample results dict
# ---------------------------------------------------------------------------


def _sample_results(top_3: float = 0.80) -> dict:
    """Build sample results dict mock theo schema Plan 09-04 emit."""
    return {
        "run_metadata": {
            "timestamp": "2026-05-21T10:00:00Z",
            "backend_url": "http://localhost:8180",
            "embedding_model": "openai/text-embedding-3-large@1536",
            "llm_model": "openai/gpt-4o-mini",
            "eval_hub_id": "test-uuid",
            "dataset_size": 10,
            "query_count": 12,
            "mock_embed": False,
        },
        "upload_summary": {
            "completed": 8,
            "failed_unsupported": 2,
            "failed": 0,
            "timeout": 0,
            "documents": [],
        },
        "retrieval_metrics": {
            "top_1_hit_rate": 0.50,
            "top_3_hit_rate": top_3,
            "top_5_hit_rate": 0.92,
            "mrr": 0.65,
            "per_query": [
                {
                    "id": "q-01",
                    "query": "Test query VN",
                    "expected_doc_id": "doc-A.docx",
                    "rank": 1,
                    "top_result_title": "doc-A.docx",
                    "result_count": 10,
                },
                {
                    "id": "q-02",
                    "query": "Miss query",
                    "expected_doc_id": "doc-X.docx",
                    "rank": None,
                    "top_result_title": "doc-Y.docx",
                    "result_count": 5,
                },
            ],
        },
        "latency": {
            "count": 12,
            "mean_ms": 245.5,
            "p50_ms": 230.0,
            "p95_ms": 480.0,
            "p99_ms": 510.0,
        },
    }


# ---------------------------------------------------------------------------
# generate_eval_md — Markdown integrity
# ---------------------------------------------------------------------------


def test_generate_eval_md_pass_has_all_sections():
    """PASS case: Markdown chứa đủ 7 section header + KHÔNG E5 warning."""
    md = generate_eval_md(_sample_results(top_3=0.80))
    for h in [
        "## 1. Setup",
        "## 2. Metrics",
        "## 3. Per-Query Diff",
        "## 4. Latency",
        "## 5. Conclusion",
        "## 6. Recommendations",
        "## 7. Defer",
    ]:
        assert h in md, f"Section missing: {h}"
    assert "PASS" in md
    # KHÔNG có cảnh báo E5 ở PASS case
    assert "TRIGGER E5" not in md


def test_generate_eval_md_fail_e5_warning_appears():
    """FAIL critical <0.60: Markdown chứa TRIGGER E5 + STOP M2b + M2a standalone."""
    md = generate_eval_md(_sample_results(top_3=0.50))
    assert "TRIGGER E5" in md
    assert "STOP M2b" in md
    assert "M2a standalone" in md


def test_generate_eval_md_fail_borderline_iterate_advice():
    """FAIL borderline 0.60-0.75: KHÔNG E5 trigger + Recommendations có iterate advice."""
    md = generate_eval_md(_sample_results(top_3=0.65))
    # Tách section conclusion để xem nhánh E5 warning (đã chắc chắn KHÔNG xuất hiện
    # vì 0.65 >= 0.60).
    assert "TRIGGER E5" not in md
    # Recommendations có iterate advice
    assert "iterate" in md.lower()
    assert "Vòng 1" in md or "Vòng 2" in md or "Vòng 3" in md


def test_generate_eval_md_includes_per_query_miss_marker():
    """Per-Query Diff table chứa MISS marker khi rank=None."""
    md = generate_eval_md(_sample_results(top_3=0.80))
    assert "MISS" in md


def test_generate_eval_md_latency_budget_check_pass():
    """p95 < 800 → 'trong budget' marker."""
    md = generate_eval_md(_sample_results(top_3=0.80))
    assert "trong budget" in md


def test_generate_eval_md_latency_budget_check_fail():
    """p95 >= 800 → 'vượt budget' marker + ef_search tuning advice."""
    res = _sample_results(top_3=0.80)
    res["latency"]["p95_ms"] = 1500.0  # vượt budget 800ms
    md = generate_eval_md(res)
    assert "vượt budget" in md
    assert "ef_search" in md  # advice tune


def test_generate_eval_md_header_verdict_badge():
    """Header có badge PASS/FAIL + exit code."""
    md_pass = generate_eval_md(_sample_results(top_3=0.80))
    assert "✅ PASS" in md_pass
    assert "Exit code `0`" in md_pass

    md_fail = generate_eval_md(_sample_results(top_3=0.50))
    assert "❌ FAIL" in md_fail
    assert "Exit code `1`" in md_fail


# ---------------------------------------------------------------------------
# main CLI — write file + exit code
# ---------------------------------------------------------------------------


def test_main_writes_file_and_exits_zero_on_pass(tmp_path: Path):
    """main() với top_3=0.80 → ghi EVAL.md + return exit code 0."""
    results_path = tmp_path / "results.json"
    output_path = tmp_path / "EVAL.md"
    results_path.write_text(
        json.dumps(_sample_results(top_3=0.80)), encoding="utf-8"
    )

    exit_code = main([str(results_path), str(output_path)])

    assert exit_code == 0
    assert output_path.exists()
    md = output_path.read_text(encoding="utf-8")
    assert "PASS" in md
    assert "## 1. Setup" in md
    assert "## 7. Defer" in md


def test_main_exits_one_on_fail(tmp_path: Path):
    """main() với top_3=0.50 → ghi EVAL.md với TRIGGER E5 + return exit code 1."""
    results_path = tmp_path / "results.json"
    output_path = tmp_path / "EVAL.md"
    results_path.write_text(
        json.dumps(_sample_results(top_3=0.50)), encoding="utf-8"
    )

    exit_code = main([str(results_path), str(output_path)])

    assert exit_code == 1
    assert output_path.exists()
    md = output_path.read_text(encoding="utf-8")
    assert "FAIL" in md
    assert "TRIGGER E5" in md


def test_main_missing_results_returns_2(tmp_path: Path):
    """main() với results file không tồn tại → return exit code 2 (KHÔNG raise)."""
    missing = tmp_path / "nope.json"
    exit_code = main([str(missing), str(tmp_path / "out.md")])
    assert exit_code == 2


def test_main_creates_output_parent_dir(tmp_path: Path):
    """main() tự tạo thư mục parent của output_path nếu chưa tồn tại."""
    results_path = tmp_path / "results.json"
    # Output ở nested subdir chưa tồn tại
    output_path = tmp_path / "nested" / "subdir" / "EVAL.md"
    results_path.write_text(
        json.dumps(_sample_results(top_3=0.80)), encoding="utf-8"
    )

    exit_code = main([str(results_path), str(output_path)])
    assert exit_code == 0
    assert output_path.exists()
