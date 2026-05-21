"""EVAL.md generator + quality gate verdict (Phase 9 EVAL-03).

7 section: Setup · Metrics · Per-Query Diff · Latency · Conclusion · Recommendations · Defer.
Gate: top_3 ≥ 0.75 absolute → PASS exit 0; < 0.75 → FAIL exit 1.
Trigger E5 STOP M2b nếu < 0.60 (per ROADMAP + PROJECT.md EXIT criteria).

Module export:
- ``gate_verdict(top_3)`` — quy đổi top-3 hit rate thành verdict + exit code.
- ``generate_eval_md(results)`` — sinh Markdown 7 section đầy đủ.
- ``main(argv)`` — CLI entry point, đọc results.json + ghi EVAL.md + trả exit code.

Run trực tiếp:
    python -m eval.report                       # default eval/results.json → eval/EVAL.md
    python -m eval.report path/results.json     # output mặc định eval/EVAL.md
    python -m eval.report results.json EVAL.md  # tuỳ chỉnh cả 2 path

Phụ thuộc:
- ``tabulate>=0.9`` (PEP 621 dep eval/pyproject.toml) — render Markdown table github format.
- Không depend ``eval/lib.py`` → có thể chạy parallel với Plan 09-02.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from tabulate import tabulate

# Threshold pin từ ROADMAP Phase 9 SC + PROJECT.md EXIT criteria E5.
GATE_THRESHOLD_PASS = 0.75
GATE_THRESHOLD_E5_STOP = 0.60


def gate_verdict(top_3: float) -> dict[str, Any]:
    """Quy đổi top-3 hit rate thành verdict + exit code.

    Quy tắc (ROADMAP Phase 9 SC + PROJECT EXIT criteria E5):

    - ``top_3 >= 0.75`` → PASS exit 0, không trigger_e5.
    - ``0.60 <= top_3 < 0.75`` → FAIL exit 1 (iterate chunker/prompt 3 vòng), không trigger_e5.
    - ``top_3 < 0.60`` → FAIL exit 1 + trigger_e5 (STOP M2b, ship M2a standalone).

    Returns:
        Dict ``{verdict: 'PASS'|'FAIL', exit_code: 0|1, trigger_e5: bool}``.
    """
    if top_3 >= GATE_THRESHOLD_PASS:
        return {"verdict": "PASS", "exit_code": 0, "trigger_e5": False}
    if top_3 < GATE_THRESHOLD_E5_STOP:
        return {"verdict": "FAIL", "exit_code": 1, "trigger_e5": True}
    return {"verdict": "FAIL", "exit_code": 1, "trigger_e5": False}


def _truncate(s: str, n: int = 50) -> str:
    """Cắt chuỗi cho gọn trong Markdown table — append ellipsis nếu vượt ``n`` ký tự."""
    if not s:
        return ""
    return s if len(s) <= n else s[: n - 1] + "…"


def _section_setup(results: dict[str, Any]) -> str:
    """Section 1 — Setup: timestamp, backend, model, dataset size, mock flag."""
    m = results.get("run_metadata", {})
    mock_flag = m.get("mock_embed")
    mock_label = (
        "YES (smoke regression — KHÔNG gate verdict)"
        if mock_flag
        else "NO (real LLM gate)"
    )
    rows = [
        ["Timestamp", m.get("timestamp", "?")],
        ["Backend URL", m.get("backend_url", "?")],
        ["Embedding model", m.get("embedding_model", "?")],
        ["LLM model", m.get("llm_model", "?")],
        ["Eval hub ID", m.get("eval_hub_id", "?")],
        ["Dataset size", m.get("dataset_size", "?")],
        ["Query count", m.get("query_count", "?")],
        ["Mock embed", mock_label],
    ]
    body = tabulate(rows, headers=["Key", "Value"], tablefmt="github")
    return f"## 1. Setup\n\n{body}\n"


def _section_metrics(results: dict[str, Any]) -> str:
    """Section 2 — Metrics: top-1/3/5 hit rate + MRR + upload summary."""
    r = results.get("retrieval_metrics", {})
    u = results.get("upload_summary", {})
    rows = [
        [
            "Top-1 hit rate",
            f"{r.get('top_1_hit_rate', 0):.3f}",
            f"{r.get('top_1_hit_rate', 0) * 100:.1f}%",
        ],
        [
            "Top-3 hit rate (GATE)",
            f"{r.get('top_3_hit_rate', 0):.3f}",
            f"{r.get('top_3_hit_rate', 0) * 100:.1f}%",
        ],
        [
            "Top-5 hit rate",
            f"{r.get('top_5_hit_rate', 0):.3f}",
            f"{r.get('top_5_hit_rate', 0) * 100:.1f}%",
        ],
        ["MRR (Mean Reciprocal Rank)", f"{r.get('mrr', 0):.3f}", "—"],
    ]
    body = tabulate(rows, headers=["Metric", "Score", "Percent"], tablefmt="github")
    upload = (
        f"\n**Upload summary:** {u.get('completed', 0)} completed · "
        f"{u.get('failed_unsupported', 0)} failed_unsupported (R4 scanned PDF) · "
        f"{u.get('failed', 0)} failed · {u.get('timeout', 0)} timeout\n"
    )
    return f"## 2. Metrics\n\n{body}\n{upload}"


def _section_per_query(results: dict[str, Any]) -> str:
    """Section 3 — Per-Query Diff: bảng debug 12 query (id/query/expected/rank/top result)."""
    pq = results.get("retrieval_metrics", {}).get("per_query", [])
    rows = []
    for q in pq:
        rank = q.get("rank")
        rank_display = str(rank) if rank is not None else "MISS"
        rows.append(
            [
                q.get("id", "?"),
                _truncate(q.get("query", ""), 50),
                _truncate(q.get("expected_doc_id", ""), 40),
                rank_display,
                _truncate(q.get("top_result_title", "") or "—", 40),
                q.get("result_count", 0),
            ]
        )
    body = tabulate(
        rows,
        headers=["ID", "Query", "Expected", "Rank", "Top result", "#Results"],
        tablefmt="github",
    )
    return f"## 3. Per-Query Diff\n\n{body}\n"


def _section_latency(results: dict[str, Any]) -> str:
    """Section 4 — Latency: p50/p95/p99 + so target 800ms single hub."""
    lat = results.get("latency", {})
    rows = [
        ["Count", lat.get("count", 0)],
        ["Mean (ms)", f"{lat.get('mean_ms', 0):.1f}"],
        ["p50 (ms)", f"{lat.get('p50_ms', 0):.1f}"],
        ["p95 (ms)", f"{lat.get('p95_ms', 0):.1f} (target <800ms single hub)"],
        ["p99 (ms)", f"{lat.get('p99_ms', 0):.1f}"],
    ]
    body = tabulate(rows, headers=["Metric", "Value"], tablefmt="github")
    p95 = lat.get("p95_ms", 0)
    budget = "✓ trong budget" if p95 < 800 else "✗ vượt budget 800ms"
    return (
        f"## 4. Latency (search endpoint)\n\n"
        f"{body}\n\n"
        f"**p95 vs target 800ms:** {budget}\n"
    )


def _section_conclusion(results: dict[str, Any], verdict_info: dict[str, Any]) -> str:
    """Section 5 — Conclusion: badge PASS/FAIL + rationale + exit code + E5 warning."""
    r = results.get("retrieval_metrics", {})
    top_3 = r.get("top_3_hit_rate", 0)
    verdict = verdict_info["verdict"]
    badge = "✅ **PASS**" if verdict == "PASS" else "❌ **FAIL**"
    rationale = (
        f"top-3 hit rate = `{top_3:.3f}` ({top_3 * 100:.1f}%) "
        f"{'≥' if verdict == 'PASS' else '<'} threshold `0.75` (75%)."
    )
    e5_warn = ""
    if verdict_info.get("trigger_e5"):
        e5_warn = (
            "\n\n> 🚨 **TRIGGER E5 — STOP M2b.** top-3 < 0.60 dù chạy gate.\n"
            "> Action: Ship M2a standalone (Phase 1-4 + EXIT GATE đã PASS 2026-05-21). "
            "Discuss reranker / hybrid BM25 cho v3.0 với user (PROJECT.md EXIT criteria E5)."
        )
    exit_code = verdict_info["exit_code"]
    return (
        f"## 5. Conclusion\n\n"
        f"{badge}\n\n{rationale}\n\n"
        f"**Exit code:** `{exit_code}` (CI-friendly: 0 PASS, 1 FAIL)."
        f"{e5_warn}\n"
    )


def _section_recommendations(
    verdict_info: dict[str, Any],
    results: dict[str, Any],
) -> str:
    """Section 6 — Recommendations: conditional theo verdict (PASS / FAIL borderline / FAIL E5)."""
    verdict = verdict_info["verdict"]
    trigger_e5 = verdict_info.get("trigger_e5", False)
    lines: list[str] = ["## 6. Recommendations\n"]

    if verdict == "PASS":
        lines.append(
            "- ✅ Ship M2 — gate ≥ 75% top-3 đạt. Tiếp Phase 10 hardening.\n"
            "- Log iterate VN medical quality cải tiến cho v4.0:\n"
            "  - Hybrid BM25 + dense vector (RAG-V4-01 defer).\n"
            "  - Reranker Cohere rerank-3 / local cross-encoder (RAG-V4-02 defer).\n"
            "  - Eval dataset mở rộng (100+ query) khi có prod data thật (post-M2 deploy).\n"
            "- Document `EVAL.md` này như baseline; mỗi lần đổi chunker/prompt re-run "
            "`make eval-all`.\n"
        )
    elif trigger_e5:
        lines.append(
            "- 🚨 **TRIGGER E5 STOP M2b** (PROJECT.md EXIT criteria).\n"
            "- Stop M2b, ship M2a (Phase 1-4) standalone — đã PASS EXIT GATE 2026-05-21.\n"
            "- Discuss với user:\n"
            "  - Hybrid BM25 + dense (recall boost cho VN medical jargon).\n"
            "  - Reranker layer (Cohere rerank-3) — tăng precision sau retrieval.\n"
            "  - Embedding dim 3072 (text-embedding-3-large full) — cross-dim defer v4.0 "
            "NHƯNG có thể bump lên v3.0 nếu gate < 60%.\n"
            "  - Chunker strategy mới: semantic chunking + sentence-window retrieval.\n"
        )
    else:
        # FAIL borderline 0.60-0.75
        lines.append(
            "- ⚠️ FAIL borderline (60-75% top-3) — iterate trước khi trigger E5.\n"
            "- Iterate chunker boundary VN (3 vòng max — PROJECT.md):\n"
            "  - Vòng 1: tune `RecursiveSplitter` regex VN heading (Mục/Chương boundary).\n"
            "  - Vòng 2: prompt expansion (query rewrite cho VN medical jargon).\n"
            "  - Vòng 3: tăng `top_k_search=15` (post-filter sau retrieval).\n"
            "- Mỗi vòng `make eval-all` + ghi `EVAL-${date}.md` (gitignored).\n"
            "- Vòng 3 vẫn fail → trigger E5.\n"
        )

    # Latency advice — bổ sung nếu p95 vượt budget.
    p95 = results.get("latency", {}).get("p95_ms", 0)
    if p95 >= 800:
        lines.append(
            f"- ⚠️ Latency p95 = `{p95:.1f}ms` vượt budget 800ms single hub.\n"
            "  - Re-tune `SET hnsw.ef_search` xuống 100-150 (đánh đổi recall vs latency).\n"
            "  - Tăng connection pool size (asyncpg `min_size=10, max_size=20`).\n"
        )

    # MISS query analysis — đếm query MISS để review thủ công.
    miss = [
        q
        for q in results.get("retrieval_metrics", {}).get("per_query", [])
        if q.get("rank") is None
    ]
    if miss:
        lines.append(
            f"- {len(miss)} query MISS — review thủ công `Per-Query Diff` section 3 "
            "để hiểu loại miss:\n"
            "  - Heading nhiễu (chunker boundary sai).\n"
            "  - VN medical jargon (synonym expansion cần thiết).\n"
            "  - File scanned PDF (R4 expected `failed_unsupported`, KHÔNG count vào "
            "miss thật).\n"
        )

    return "\n".join(lines)


def _section_defer() -> str:
    """Section 7 — Defer: liệt kê các metric / capability OUT OF SCOPE Phase 9."""
    return (
        "## 7. Defer (Out of Scope Phase 9)\n\n"
        "- **Answer quality (BLEU/ROUGE)** → defer v4.0.\n"
        "- **LLM-as-judge auto-grading** → defer v4.0 (12 query có expected_doc_id đủ "
        "ground truth).\n"
        "- **Statistical significance test** → defer v4.0 (12 query quá ít cho t-test).\n"
        "- **A/B multi embedding model (BGE-M3, sentence-transformers)** → defer v4.1.\n"
        "- **Visual dashboard Streamlit** → defer v4.0.\n"
        "- **Auto regression CI (GitHub Actions)** → defer Phase 10 HARD-03.\n"
        "- **Heading recall metric** → defer v4.1 (cocoindex chunker khác Go regex, "
        "không ground truth).\n"
        "- **Larger eval dataset 100+ queries** → defer khi có prod data thật "
        "post-M2 deploy.\n"
        "- **Cross-hub search eval** → defer v4.0 (REQUIREMENTS chỉ single-hub "
        "`/api/search`).\n"
        "- **Eval `/api/ask` end-to-end + citation correctness** → defer v4.0 "
        "(anti-injection LLM thật, response parse `[N]`).\n"
    )


def generate_eval_md(results: dict[str, Any]) -> str:
    """Sinh Markdown 7 section từ ``results`` dict.

    Idempotent — không side effect (không ghi file, không gọi network).
    Đầu vào là dict đọc từ ``eval/results.json`` (schema run_metadata +
    upload_summary + retrieval_metrics + latency).

    Returns:
        Chuỗi Markdown UTF-8 đầy đủ 7 section + header verdict.
    """
    top_3 = results.get("retrieval_metrics", {}).get("top_3_hit_rate", 0)
    verdict_info = gate_verdict(top_3)

    badge_short = "✅ PASS" if verdict_info["verdict"] == "PASS" else "❌ FAIL"
    header = (
        "# Eval Report — Phase 9 Quality Gate ≥75% top-3\n\n"
        f"> **Verdict:** {badge_short} · "
        f"top-3 hit rate `{top_3:.3f}` ({top_3 * 100:.1f}%) · "
        f"Exit code `{verdict_info['exit_code']}`\n\n"
        "---\n\n"
    )

    sections = [
        _section_setup(results),
        _section_metrics(results),
        _section_per_query(results),
        _section_latency(results),
        _section_conclusion(results, verdict_info),
        _section_recommendations(verdict_info, results),
        _section_defer(),
    ]

    return header + "\n---\n\n".join(sections) + "\n"


def main(argv: list[str] | None = None) -> int:
    """CLI entry: ``python -m eval.report [results.json [EVAL.md]]``.

    Default paths: ``eval/results.json`` → ``eval/EVAL.md``.

    Args:
        argv: optional list of CLI args (mặc định lấy từ ``sys.argv[1:]``).

    Returns:
        Exit code:
        - ``0`` nếu top-3 ≥ 0.75 (PASS).
        - ``1`` nếu top-3 < 0.75 (FAIL — có thể trigger_e5 nếu < 0.60).
        - ``2`` nếu file results không tồn tại.
    """
    args = argv if argv is not None else sys.argv[1:]
    results_path = Path(args[0]) if len(args) >= 1 else Path("eval/results.json")
    output_path = Path(args[1]) if len(args) >= 2 else Path("eval/EVAL.md")

    if not results_path.exists():
        print(
            f"ERROR: results file không tồn tại: {results_path}",
            file=sys.stderr,
        )
        return 2

    results: dict[str, Any] = json.loads(results_path.read_text(encoding="utf-8"))
    md = generate_eval_md(results)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(md, encoding="utf-8")

    top_3 = results.get("retrieval_metrics", {}).get("top_3_hit_rate", 0)
    v = gate_verdict(top_3)
    extra = (
        "\n🚨 TRIGGER E5 STOP M2b — discuss với user."
        if v.get("trigger_e5")
        else ""
    )
    print(
        f"Eval report written: {output_path}\n"
        f"Verdict: {v['verdict']} (top-3 = {top_3:.3f}, threshold 0.75)\n"
        f"Exit code: {v['exit_code']}"
        f"{extra}"
    )
    return v["exit_code"]


if __name__ == "__main__":
    sys.exit(main())
