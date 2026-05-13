"""run_retrieval_eval.py — Plan 05-03 (EVAL-03)

So sánh retrieval quality giữa 2 mode (native vs docling) bằng cách load
2 snapshot có sẵn (`baseline_native.json` + `baseline_docling.json`) — KHÔNG
gọi lại `/api/search`. Compute top-1/3/5 hit rate + MRR cho mỗi mode, diff
per-query với 6 verdict (unchanged / FIXED / REGRESSED / IMPROVED / WORSE /
both_miss) và sinh `eval/retrieval_eval.json` cho Plan 05-04 orchestrator.

Schema đầu ra (xem `<interfaces>` của 05-03-PLAN.md):

    {
      "run_id": "...",
      "native_metrics": {"top_1": ..., "top_3": ..., "top_5": ..., "mrr": ...},
      "docling_metrics": {...},
      "delta": {"top_1": +X.XX, "top_3": ..., "top_5": ..., "mrr": ...},
      "per_query": [
        {"id": "q01", "expected": "...", "native_rank": 1,
         "docling_rank": 1, "verdict": "unchanged"},
        ...
      ],
      "summary": {
        "fixed_count": N, "regressed_count": N, "improved_count": N,
        "worse_count": N, "unchanged_count": N, "both_miss_count": N
      }
    }

Verdict logic (per task spec):
  - both_miss   : cả 2 native_rank, docling_rank == None
  - FIXED       : native_rank None  AND docling_rank ≤ 5
  - REGRESSED   : native_rank ≤ 5   AND docling_rank None
  - IMPROVED    : cả 2 hit, docling_rank tốt hơn ≥ 2 positions (rank thấp = tốt)
  - WORSE       : cả 2 hit, docling_rank tệ hơn ≥ 2 positions
  - unchanged   : cả 2 hit, |docling_rank - native_rank| ≤ 1

Exit code:
  0 — thành công (sinh file output)
  1 — pre-condition fail (thiếu snapshot, query set lệch, schema sai)
  2 — argparse usage error (argparse default)

Usage:
    python eval/run_retrieval_eval.py \
        --native-snapshot eval/baseline_native.json \
        --docling-snapshot eval/baseline_docling.json \
        --out eval/retrieval_eval.json

Smoke test (giả lập docling=native):
    python eval/run_retrieval_eval.py \
        --native-snapshot eval/baseline_native.json \
        --docling-snapshot eval/baseline_native.json \
        --out /tmp/retrieval_eval_smoke.json
    # Expect: tất cả per_query.verdict == "unchanged" hoặc "both_miss",
    # delta = 0 cho tất cả metric.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from tabulate import tabulate
except ImportError:  # tabulate là optional cho stdout pretty-print
    tabulate = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Hằng số
# ---------------------------------------------------------------------------

VERDICT_UNCHANGED = "unchanged"
VERDICT_FIXED = "FIXED"
VERDICT_REGRESSED = "REGRESSED"
VERDICT_IMPROVED = "IMPROVED"
VERDICT_WORSE = "WORSE"
VERDICT_BOTH_MISS = "both_miss"

ALL_VERDICTS = (
    VERDICT_UNCHANGED,
    VERDICT_FIXED,
    VERDICT_REGRESSED,
    VERDICT_IMPROVED,
    VERDICT_WORSE,
    VERDICT_BOTH_MISS,
)

RANK_DELTA_THRESHOLD = 2  # ≥ 2 positions để gọi IMPROVED / WORSE


# ---------------------------------------------------------------------------
# Helper IO
# ---------------------------------------------------------------------------


def load_snapshot(path: Path, label: str) -> dict[str, Any]:
    """Đọc snapshot JSON, fail loud nếu thiếu hoặc sai schema."""
    if not path.exists():
        msg = (
            f"[FATAL] Không tìm thấy snapshot {label}: {path}\n"
            f"        Hãy chạy `python eval/run_docling.py` trước để sinh "
            f"`eval/baseline_docling.json`, hoặc kiểm tra lại đường dẫn."
        )
        print(msg, file=sys.stderr)
        sys.exit(1)

    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[FATAL] Không đọc được snapshot {label} ({path}): {exc}",
              file=sys.stderr)
        sys.exit(1)

    if "retrieval" not in data or not isinstance(data["retrieval"], dict):
        print(f"[FATAL] Snapshot {label} thiếu block `retrieval`: {path}",
              file=sys.stderr)
        sys.exit(1)

    if "per_query" not in data["retrieval"]:
        print(f"[FATAL] Snapshot {label} thiếu `retrieval.per_query`: {path}",
              file=sys.stderr)
        sys.exit(1)

    return data


# ---------------------------------------------------------------------------
# Helper extract metrics + per-query
# ---------------------------------------------------------------------------


def extract_metrics(snapshot: dict[str, Any]) -> dict[str, float]:
    """Rút 4 metric aggregate từ block `retrieval` của snapshot."""
    retrieval = snapshot["retrieval"]
    return {
        "top_1": float(retrieval.get("top_1_hit_rate", 0.0) or 0.0),
        "top_3": float(retrieval.get("top_3_hit_rate", 0.0) or 0.0),
        "top_5": float(retrieval.get("top_5_hit_rate", 0.0) or 0.0),
        "mrr": float(retrieval.get("mrr", 0.0) or 0.0),
    }


def index_per_query(snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Trả dict {query_id: per_query_entry} để lookup nhanh khi diff."""
    indexed: dict[str, dict[str, Any]] = {}
    for entry in snapshot["retrieval"]["per_query"]:
        qid = entry.get("id")
        if not qid:
            continue
        indexed[qid] = entry
    return indexed


# ---------------------------------------------------------------------------
# Verdict logic
# ---------------------------------------------------------------------------


def _normalize_rank(raw: Any) -> int | None:
    """Chuẩn hoá rank: chấp nhận int hợp lệ (1..) hoặc None."""
    if raw is None:
        return None
    try:
        val = int(raw)
    except (TypeError, ValueError):
        return None
    if val <= 0:
        return None
    return val


def classify_verdict(native_rank: int | None,
                     docling_rank: int | None) -> str:
    """Phân loại 1 query thành 1 trong 6 verdict.

    Quy ước: rank thấp hơn = tốt hơn. None = miss.
    """
    if native_rank is None and docling_rank is None:
        return VERDICT_BOTH_MISS

    if native_rank is None and docling_rank is not None:
        return VERDICT_FIXED

    if native_rank is not None and docling_rank is None:
        return VERDICT_REGRESSED

    # Cả 2 hit — so sánh delta rank
    assert native_rank is not None and docling_rank is not None
    diff = docling_rank - native_rank  # >0 = docling tệ hơn, <0 = tốt hơn
    if diff <= -RANK_DELTA_THRESHOLD:
        return VERDICT_IMPROVED
    if diff >= RANK_DELTA_THRESHOLD:
        return VERDICT_WORSE
    return VERDICT_UNCHANGED


def build_per_query_diff(native_idx: dict[str, dict[str, Any]],
                         docling_idx: dict[str, dict[str, Any]]
                         ) -> list[dict[str, Any]]:
    """Sinh list per_query đầy đủ với verdict, theo thứ tự query_id sort tự nhiên."""
    all_qids = sorted(set(native_idx.keys()) | set(docling_idx.keys()))
    out: list[dict[str, Any]] = []
    for qid in all_qids:
        native_entry = native_idx.get(qid, {})
        docling_entry = docling_idx.get(qid, {})

        native_rank = _normalize_rank(native_entry.get("rank"))
        docling_rank = _normalize_rank(docling_entry.get("rank"))

        # expected_doc_id ưu tiên lấy từ docling (mới hơn) rồi fallback native
        expected = (
            docling_entry.get("expected_doc_id")
            or native_entry.get("expected_doc_id")
            or ""
        )

        verdict = classify_verdict(native_rank, docling_rank)
        out.append({
            "id": qid,
            "expected": expected,
            "native_rank": native_rank,
            "docling_rank": docling_rank,
            "verdict": verdict,
        })
    return out


def summarize_verdicts(per_query: list[dict[str, Any]]) -> dict[str, int]:
    """Đếm số query mỗi verdict."""
    counts = {v: 0 for v in ALL_VERDICTS}
    for entry in per_query:
        verdict = entry.get("verdict")
        if verdict in counts:
            counts[verdict] += 1
    # Đặt tên key theo schema task: fixed_count, regressed_count, ...
    return {
        "fixed_count": counts[VERDICT_FIXED],
        "regressed_count": counts[VERDICT_REGRESSED],
        "improved_count": counts[VERDICT_IMPROVED],
        "worse_count": counts[VERDICT_WORSE],
        "unchanged_count": counts[VERDICT_UNCHANGED],
        "both_miss_count": counts[VERDICT_BOTH_MISS],
    }


# ---------------------------------------------------------------------------
# Validate query set khớp giữa 2 snapshot (T-05-07 mitigation)
# ---------------------------------------------------------------------------


def assert_query_sets_match(native_idx: dict[str, dict[str, Any]],
                            docling_idx: dict[str, dict[str, Any]]) -> None:
    """Hard-fail nếu 2 snapshot không cùng query_id set (mitigate T-05-07).

    Cho phép case docling snapshot trống/skip (vd Plan 05-01 chưa chạy thật)
    NHƯNG nếu cả 2 đều có per_query thì set phải khớp tuyệt đối.
    """
    native_set = set(native_idx.keys())
    docling_set = set(docling_idx.keys())

    if not native_set:
        print("[FATAL] Snapshot native không có per_query nào.", file=sys.stderr)
        sys.exit(1)
    if not docling_set:
        print("[FATAL] Snapshot docling không có per_query nào — chưa chạy "
              "`python eval/run_docling.py`?", file=sys.stderr)
        sys.exit(1)

    if native_set != docling_set:
        only_native = sorted(native_set - docling_set)
        only_docling = sorted(docling_set - native_set)
        print(
            "[FATAL] Query set 2 snapshot lệch nhau (T-05-07 violation).\n"
            f"        Chỉ có ở native : {only_native}\n"
            f"        Chỉ có ở docling: {only_docling}\n"
            "        2 snapshot PHẢI chạy cùng `eval/dataset/queries.jsonl`.",
            file=sys.stderr,
        )
        sys.exit(1)


# ---------------------------------------------------------------------------
# Pretty-print stdout
# ---------------------------------------------------------------------------


def _fmt_rank(rank: int | None) -> str:
    return "-" if rank is None else str(rank)


def _fmt_pct(value: float) -> str:
    return f"{value * 100:5.1f}%"


def _fmt_delta_pct(delta: float) -> str:
    sign = "+" if delta >= 0 else ""
    return f"{sign}{delta * 100:5.1f}pp"


def _fmt_delta_mrr(delta: float) -> str:
    sign = "+" if delta >= 0 else ""
    return f"{sign}{delta:.3f}"


def print_stdout_report(native_metrics: dict[str, float],
                        docling_metrics: dict[str, float],
                        delta: dict[str, float],
                        per_query: list[dict[str, Any]],
                        summary: dict[str, int]) -> None:
    """In bảng metric tổng + per-query + verdict counts ra stdout."""
    print()
    print("=" * 78)
    print(" RETRIEVAL EVAL — Native vs Docling")
    print("=" * 78)

    # Bảng metrics tổng
    metric_rows = [
        ["top-1", _fmt_pct(native_metrics["top_1"]),
         _fmt_pct(docling_metrics["top_1"]), _fmt_delta_pct(delta["top_1"])],
        ["top-3", _fmt_pct(native_metrics["top_3"]),
         _fmt_pct(docling_metrics["top_3"]), _fmt_delta_pct(delta["top_3"])],
        ["top-5", _fmt_pct(native_metrics["top_5"]),
         _fmt_pct(docling_metrics["top_5"]), _fmt_delta_pct(delta["top_5"])],
        ["MRR",   f"{native_metrics['mrr']:.3f}",
         f"{docling_metrics['mrr']:.3f}", _fmt_delta_mrr(delta["mrr"])],
    ]
    headers = ["Metric", "Native", "Docling", "Delta"]
    if tabulate is not None:
        print()
        print(tabulate(metric_rows, headers=headers, tablefmt="github"))
    else:
        print()
        print(" | ".join(headers))
        for row in metric_rows:
            print(" | ".join(row))

    # Bảng per-query
    pq_rows = [[
        e["id"],
        (e["expected"] or "")[:42],
        _fmt_rank(e["native_rank"]),
        _fmt_rank(e["docling_rank"]),
        e["verdict"],
    ] for e in per_query]
    pq_headers = ["Query", "Expected", "Native rank", "Docling rank", "Verdict"]
    print()
    if tabulate is not None:
        print(tabulate(pq_rows, headers=pq_headers, tablefmt="github"))
    else:
        print(" | ".join(pq_headers))
        for row in pq_rows:
            print(" | ".join(str(c) for c in row))

    # Verdict summary
    print()
    print("Verdict counts:")
    print(f"  unchanged  : {summary['unchanged_count']}")
    print(f"  FIXED      : {summary['fixed_count']}")
    print(f"  REGRESSED  : {summary['regressed_count']}")
    print(f"  IMPROVED   : {summary['improved_count']}")
    print(f"  WORSE      : {summary['worse_count']}")
    print(f"  both_miss  : {summary['both_miss_count']}")
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "So sánh retrieval quality giữa 2 mode native vs docling từ "
            "snapshot có sẵn — sinh eval/retrieval_eval.json cho Plan 05-04."
        ),
    )
    parser.add_argument(
        "--native-snapshot",
        type=Path,
        default=Path("eval/baseline_native.json"),
        help="Đường dẫn snapshot native (mặc định eval/baseline_native.json)",
    )
    parser.add_argument(
        "--docling-snapshot",
        type=Path,
        default=Path("eval/baseline_docling.json"),
        help="Đường dẫn snapshot docling (mặc định eval/baseline_docling.json)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("eval/retrieval_eval.json"),
        help="File JSON intermediate output (mặc định eval/retrieval_eval.json)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    print(f"[run_retrieval_eval] Native snapshot : {args.native_snapshot}")
    print(f"[run_retrieval_eval] Docling snapshot: {args.docling_snapshot}")
    print(f"[run_retrieval_eval] Output          : {args.out}")

    native_snap = load_snapshot(args.native_snapshot, "native")
    docling_snap = load_snapshot(args.docling_snapshot, "docling")

    native_metrics = extract_metrics(native_snap)
    docling_metrics = extract_metrics(docling_snap)
    delta = {
        "top_1": docling_metrics["top_1"] - native_metrics["top_1"],
        "top_3": docling_metrics["top_3"] - native_metrics["top_3"],
        "top_5": docling_metrics["top_5"] - native_metrics["top_5"],
        "mrr":   docling_metrics["mrr"] - native_metrics["mrr"],
    }

    native_idx = index_per_query(native_snap)
    docling_idx = index_per_query(docling_snap)
    assert_query_sets_match(native_idx, docling_idx)

    per_query = build_per_query_diff(native_idx, docling_idx)
    summary = summarize_verdicts(per_query)

    run_id = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    output = {
        "run_id": run_id,
        "native_snapshot": str(args.native_snapshot),
        "docling_snapshot": str(args.docling_snapshot),
        "native_run_id": native_snap.get("run_id"),
        "docling_run_id": docling_snap.get("run_id"),
        "queries_count": len(per_query),
        "native_metrics": native_metrics,
        "docling_metrics": docling_metrics,
        "delta": delta,
        "per_query": per_query,
        "summary": summary,
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"[run_retrieval_eval] OK -> wrote {args.out}")

    print_stdout_report(native_metrics, docling_metrics, delta,
                        per_query, summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
