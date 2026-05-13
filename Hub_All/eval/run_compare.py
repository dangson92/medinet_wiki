"""run_compare.py — Plan 05-04 (EVAL-04) — Orchestrator + Quality Gate + EVAL.md generator.

Đây là **gate cuối cùng của milestone M1 — RAG Quality with Docling**.

Quy trình:
  1. Pre-condition: cả `baseline_native.json` + `baseline_docling.json` PHẢI tồn tại.
     Thiếu → fail loud + hint chạy `eval/run_docling.py` trước.
  2. Subprocess gọi `eval/run_extraction_compare.py` → sinh `eval/extraction_compare.json`
     (skip nếu `--skip-subprocess` hoặc file đã có và còn fresh).
  3. Subprocess gọi `eval/run_retrieval_eval.py` → sinh `eval/retrieval_eval.json`.
  4. Load 4 JSON: native snapshot + docling snapshot + 2 intermediate.
  5. Apply quality gate (CONTEXT 05 mục E):
        - PASS nếu delta_top3 ≥ +0.15 (≥ +15 điểm phần trăm)
        - PASS nếu docling_top3 ≥ 0.75 tuyệt đối
        - FAIL còn lại
  6. Sinh `eval/EVAL.md` với 7 section đúng template CONTEXT 05 mục F.
     EVAL.md SẼ ĐƯỢC SINH cả 2 case PASS/FAIL — chứa số liệu để debug.
  7. Exit code 0 nếu PASS, 1 nếu FAIL (CI-friendly).

Schema input (đọc từ disk):
  - eval/baseline_native.json (Phase 1, immutable, 75% top-3 baseline)
  - eval/baseline_docling.json (Plan 05-01 runtime artifact)
  - eval/extraction_compare.json (Plan 05-02 output)
  - eval/retrieval_eval.json (Plan 05-03 output)

Output:
  - eval/EVAL.md (Markdown, 7 section)
  - exit code 0 (PASS) | 1 (FAIL)

Usage:
    python eval/run_compare.py
    python eval/run_compare.py --skip-subprocess  # dùng intermediate JSON đã có
    python eval/run_compare.py \\
        --native-snapshot eval/baseline_native.json \\
        --docling-snapshot eval/baseline_docling.json \\
        --out eval/EVAL.md

Smoke test (giả lập docling = native):
    cp eval/baseline_native.json eval/baseline_docling.json
    python eval/run_compare.py --skip-subprocess
    # Expect: PASS (top-3 = 75% ≥ 75% tuyệt đối, dù delta = 0pp)

Quality gate (theo CONTEXT 05 mục E):
    delta = docling_top3 - native_top3
    if delta >= 0.15:    PASS — top-3 cải thiện ≥ +15pp
    elif d_top3 >= 0.75: PASS — top-3 đạt tuyệt đối ≥ 75% (dù delta nhỏ)
    else:                FAIL
"""
from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ─── Logging ─────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("run_compare")

# ─── Path defaults ───────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_NATIVE = REPO_ROOT / "eval" / "baseline_native.json"
DEFAULT_DOCLING = REPO_ROOT / "eval" / "baseline_docling.json"
DEFAULT_EXTRACTION_OUT = REPO_ROOT / "eval" / "extraction_compare.json"
DEFAULT_RETRIEVAL_OUT = REPO_ROOT / "eval" / "retrieval_eval.json"
DEFAULT_EVAL_MD = REPO_ROOT / "eval" / "EVAL.md"

# ─── Quality gate threshold (CONTEXT 05 mục E) ───────────────────────────────
GATE_DELTA_THRESHOLD = 0.15   # +15 điểm phần trăm
GATE_ABSOLUTE_THRESHOLD = 0.75  # 75% tuyệt đối

# ─── Tabulate optional (đồng bộ pattern Plan 05-02/03) ────────────────────────
try:
    from tabulate import tabulate as _tabulate_lib

    def render_markdown_table(rows: list[list[Any]], headers: list[str]) -> str:
        """Render bảng Markdown qua tabulate (tablefmt=github)."""
        return _tabulate_lib(rows, headers=headers, tablefmt="github")
except ImportError:  # pragma: no cover — fallback runtime
    logger.warning(
        "tabulate chưa cài (pip install tabulate). Fallback Markdown table thuần Python — render vẫn ok cho EVAL.md."
    )

    def render_markdown_table(rows: list[list[Any]], headers: list[str]) -> str:
        """Fallback Markdown table thuần Python — không cần tabulate."""
        head = "| " + " | ".join(str(h) for h in headers) + " |"
        sep = "| " + " | ".join("---" for _ in headers) + " |"
        body = "\n".join(
            "| " + " | ".join(str(c) if c is not None else "—" for c in row) + " |"
            for row in rows
        )
        return "\n".join([head, sep, body]) if rows else "\n".join([head, sep])


# ═══════════════════════════════════════════════════════════════════════════════
# 1. PRE-CONDITION
# ═══════════════════════════════════════════════════════════════════════════════

def precondition_check(native_path: Path, docling_path: Path) -> None:
    """Kiểm tra 2 snapshot tồn tại. Thiếu → fail loud."""
    missing: list[str] = []
    if not native_path.exists():
        missing.append(str(native_path))
    if not docling_path.exists():
        missing.append(str(docling_path))
    if missing:
        logger.error("[FATAL] Thiếu snapshot bắt buộc: %s", ", ".join(missing))
        logger.error("Hint: chạy `python eval/run_docling.py` trước để sinh baseline_docling.json")
        logger.error("Hoặc đảm bảo eval/baseline_native.json tồn tại (Phase 1 commit f37cd96)")
        sys.exit(1)


# ═══════════════════════════════════════════════════════════════════════════════
# 2. ORCHESTRATE SUBPROCESS
# ═══════════════════════════════════════════════════════════════════════════════

def run_subprocess(script_path: Path, label: str) -> None:
    """Chạy script Python subprocess + fail-loud nếu non-zero exit."""
    if not script_path.exists():
        logger.error("[FATAL] Script %s không tồn tại: %s", label, script_path)
        sys.exit(1)
    logger.info("Chạy subprocess %s: %s", label, script_path)
    result = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=str(REPO_ROOT),
        check=False,
    )
    if result.returncode != 0:
        logger.error("[FATAL] %s FAIL (exit %d)", label, result.returncode)
        sys.exit(1)
    logger.info("%s OK", label)


# ═══════════════════════════════════════════════════════════════════════════════
# 3. LOAD JSON
# ═══════════════════════════════════════════════════════════════════════════════

def load_json(path: Path, label: str) -> dict[str, Any]:
    """Load JSON file + fail-loud nếu thiếu hoặc parse error."""
    if not path.exists():
        logger.error("[FATAL] %s không tồn tại: %s", label, path)
        sys.exit(1)
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        logger.error("[FATAL] %s JSON parse error: %s", label, e)
        sys.exit(1)


# ═══════════════════════════════════════════════════════════════════════════════
# 4. QUALITY GATE LOGIC (CONTEXT 05 mục E)
# ═══════════════════════════════════════════════════════════════════════════════

def evaluate_gate(native_top3: float, docling_top3: float) -> tuple[str, str]:
    """Apply quality gate logic theo CONTEXT 05 mục E.

    Trả về (verdict, reason):
      - "PASS" + reason nếu delta ≥ +15pp HOẶC docling_top3 ≥ 75% tuyệt đối
      - "FAIL" + reason nếu cả 2 không thoả

    Args:
        native_top3:  top-3 hit rate của baseline native (0..1)
        docling_top3: top-3 hit rate của Docling mode (0..1)

    Returns:
        (verdict, reason) — verdict ∈ {"PASS", "FAIL"}, reason là chuỗi tiếng Việt.
    """
    delta = docling_top3 - native_top3
    if delta >= GATE_DELTA_THRESHOLD:
        return (
            "PASS",
            f"top-3 cải thiện {delta * 100:+.1f}pp "
            f"({native_top3 * 100:.1f}% -> {docling_top3 * 100:.1f}%)",
        )
    if docling_top3 >= GATE_ABSOLUTE_THRESHOLD:
        return (
            "PASS",
            f"top-3 đạt {docling_top3 * 100:.1f}% (≥75% tuyệt đối, dù delta {delta * 100:+.1f}pp)",
        )
    return (
        "FAIL",
        f"top-3 chỉ {docling_top3 * 100:.1f}%, delta {delta * 100:+.1f}pp "
        f"— chưa đạt gate ≥+15pp HOẶC ≥75%",
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 5. EVAL.md GENERATOR (CONTEXT 05 mục F — 7 section)
# ═══════════════════════════════════════════════════════════════════════════════

def _fmt_pct(x: float | None) -> str:
    """Format hit rate dạng phần trăm (1 chữ số thập phân)."""
    if x is None:
        return "—"
    return f"{x * 100:.1f}%"


def _fmt_pp(x: float | None) -> str:
    """Format delta điểm phần trăm với dấu (vd '+12.5 pp')."""
    if x is None:
        return "—"
    return f"{x * 100:+.1f} pp"


def _fmt_mrr(x: float | None) -> str:
    """Format MRR (3 chữ số thập phân)."""
    if x is None:
        return "—"
    return f"{x:.3f}"


def _fmt_mrr_delta(x: float | None) -> str:
    """Format delta MRR (3 chữ số có dấu)."""
    if x is None:
        return "—"
    return f"{x:+.3f}"


def _parse_run_date(run_id: str | None) -> str:
    """Trích YYYY-MM-DD từ run_id ISO timestamp. Fallback chính chuỗi."""
    if not run_id:
        return "—"
    try:
        return run_id.split("T")[0]
    except Exception:
        return run_id


def _short_filename(filename: str, max_len: int = 38) -> str:
    """Cắt ngắn filename cho bảng Markdown đọc dễ."""
    if len(filename) <= max_len:
        return filename
    return filename[: max_len - 1] + "…"


# ─── Section 1: Setup ────────────────────────────────────────────────────────

def render_section_setup(
    native: dict[str, Any],
    docling: dict[str, Any],
    extraction: dict[str, Any],
) -> str:
    """Section 1: bullet list — dataset, queries, embedder, dates."""
    files_count = native.get("files_count", len(native.get("documents", [])))
    queries_count = native.get("queries_count", len(native.get("retrieval", {}).get("per_query", [])))
    provider = native.get("embedder_provider", "unknown")
    model = native.get("embedder_model", "unknown")
    dim = native.get("embedder_dim", "—")

    native_run = _parse_run_date(native.get("run_id"))
    docling_run = _parse_run_date(docling.get("run_id"))
    docs_compared = extraction.get("summary", {}).get("documents_count", "—")

    return "\n".join(
        [
            "## 1. Setup",
            "",
            f"- **Dataset:** {files_count} file (8 DMD docx + 1 PDF + 2 scanned PDF), so sánh {docs_compared} document.",
            f"- **Queries:** {queries_count} truy vấn vàng (`eval/dataset/queries.jsonl`).",
            f"- **Embedder:** `{provider}/{model}` {dim}d (locked — assert_embedder_match đảm bảo cùng model giữa 2 run).",
            f"- **Native run:** {native_run} (extractor_mode = `native`, snapshot `eval/baseline_native.json`).",
            f"- **Docling run:** {docling_run} (extractor_mode = `docling`, snapshot `eval/baseline_docling.json`).",
            f"- **Min score:** {native.get('min_score_used', 0.0)} (baseline Phase 1 đã fix từ 0.3 → 0.0).",
            "",
        ]
    )


# ─── Section 2: Retrieval Comparison ─────────────────────────────────────────

def render_section_retrieval(retrieval_eval: dict[str, Any]) -> str:
    """Section 2: bảng Markdown top-1/3/5 + MRR (native vs docling vs delta)."""
    n = retrieval_eval.get("native_metrics", {})
    d = retrieval_eval.get("docling_metrics", {})
    delta = retrieval_eval.get("delta", {})

    rows = [
        ["top-1", _fmt_pct(n.get("top_1")), _fmt_pct(d.get("top_1")), _fmt_pp(delta.get("top_1"))],
        ["top-3", _fmt_pct(n.get("top_3")), _fmt_pct(d.get("top_3")), _fmt_pp(delta.get("top_3"))],
        ["top-5", _fmt_pct(n.get("top_5")), _fmt_pct(d.get("top_5")), _fmt_pp(delta.get("top_5"))],
        ["MRR", _fmt_mrr(n.get("mrr")), _fmt_mrr(d.get("mrr")), _fmt_mrr_delta(delta.get("mrr"))],
    ]
    table = render_markdown_table(rows, headers=["Metric", "Native", "Docling", "Delta"])

    summary = retrieval_eval.get("summary", {})
    counts_line = (
        f"_Counts:_ FIXED={summary.get('fixed_count', 0)} · "
        f"REGRESSED={summary.get('regressed_count', 0)} · "
        f"IMPROVED={summary.get('improved_count', 0)} · "
        f"WORSE={summary.get('worse_count', 0)} · "
        f"unchanged={summary.get('unchanged_count', 0)} · "
        f"both_miss={summary.get('both_miss_count', 0)}"
    )

    return "\n".join(
        [
            "## 2. Retrieval Comparison",
            "",
            table,
            "",
            counts_line,
            "",
        ]
    )


# ─── Section 3: Per-Query Diff ───────────────────────────────────────────────

def render_section_per_query(retrieval_eval: dict[str, Any]) -> str:
    """Section 3: bảng 12 query với verdict."""
    per_query = retrieval_eval.get("per_query", [])
    rows = []
    for q in per_query:
        rows.append(
            [
                q.get("id", "—"),
                _short_filename(str(q.get("expected", "—"))),
                q.get("native_rank") if q.get("native_rank") is not None else "miss",
                q.get("docling_rank") if q.get("docling_rank") is not None else "miss",
                q.get("verdict", "—"),
            ]
        )
    table = render_markdown_table(
        rows, headers=["Q", "Expected", "Native rank", "Docling rank", "Verdict"]
    )
    return "\n".join(
        [
            "## 3. Per-Query Diff",
            "",
            table,
            "",
        ]
    )


# ─── Section 4: Per-Document Extraction Quality ──────────────────────────────

def render_section_per_document(extraction: dict[str, Any]) -> str:
    """Section 4: bảng từ extraction_compare.json — chunks + heading recall + tables."""
    docs = extraction.get("documents", [])
    rows = []
    for doc in docs:
        filename = doc.get("filename", "—")
        n = doc.get("native", {}) or {}
        d = doc.get("docling", {}) or {}

        n_chunks = n.get("chunks_count", "—")
        d_chunks = d.get("chunks_count", "—")

        n_recall = n.get("heading_recall")
        d_recall = d.get("heading_recall")
        recall_cell = f"{_fmt_pct(n_recall)} -> {_fmt_pct(d_recall)}"

        n_tables = n.get("tables_preserved", "—")
        d_tables = d.get("tables_preserved", "—")
        tables_total = n.get("tables_total", d.get("tables_total", "—"))
        tables_cell = f"{n_tables}/{tables_total} -> {d_tables}/{tables_total}"

        rows.append(
            [
                _short_filename(filename),
                n_chunks,
                d_chunks,
                recall_cell,
                tables_cell,
            ]
        )

    table = render_markdown_table(
        rows,
        headers=[
            "Doc",
            "Native chunks",
            "Docling chunks",
            "Heading recall (N→D)",
            "Table preservation (N→D)",
        ],
    )

    summary = extraction.get("summary", {})
    summary_line = (
        f"_Aggregate:_ heading recall {_fmt_pct(summary.get('avg_heading_recall_native'))} "
        f"-> {_fmt_pct(summary.get('avg_heading_recall_docling'))} · "
        f"table preservation {_fmt_pct(summary.get('table_preservation_native'))} "
        f"-> {_fmt_pct(summary.get('table_preservation_docling'))} "
        f"({summary.get('tables_preserved_native', 0)}/{summary.get('tables_total_gold', 0)} "
        f"-> {summary.get('tables_preserved_docling', 0)}/{summary.get('tables_total_gold', 0)})"
    )

    return "\n".join(
        [
            "## 4. Per-Document Extraction Quality",
            "",
            table,
            "",
            summary_line,
            "",
        ]
    )


# ─── Section 5: Smoke Verification ───────────────────────────────────────────

def render_section_smoke() -> str:
    """Section 5: placeholder cho `make eval-smoke` (Plan 05-05)."""
    return "\n".join(
        [
            "## 5. Smoke Verification",
            "",
            "- `make eval-smoke` last run: **deferred** — chờ user chạy (Plan 05-05 sẽ thêm Makefile target).",
            "- Mục đích: e2e test 1 file `DMD_T1-01_DinhVi_TrungTam_v1.docx` qua mode `docling` "
            "→ verify `extractor_used == 'docling'` + có ≥ 1 chunk `metadata.is_table = true`.",
            "",
        ]
    )


# ─── Section 6: Conclusion ───────────────────────────────────────────────────

def render_section_conclusion(verdict: str, reason: str, retrieval_eval: dict[str, Any]) -> str:
    """Section 6: text trình bày verdict + recommendation tiếng Việt."""
    summary = retrieval_eval.get("summary", {})
    fixed = summary.get("fixed_count", 0)
    regressed = summary.get("regressed_count", 0)
    improved = summary.get("improved_count", 0)
    worse = summary.get("worse_count", 0)

    if verdict == "PASS":
        body = [
            f"**Kết luận: PASS.** {reason}",
            "",
            f"Docling đã giúp FIXED **{fixed}** query (mà native miss) và IMPROVED **{improved}** query "
            f"(rank tốt hơn ≥ 2 vị trí). Đồng thời REGRESSED **{regressed}** + WORSE **{worse}** "
            "— theo dõi nhưng KHÔNG block milestone.",
            "",
            "**Khuyến nghị tiếp theo:**",
            "",
            "- Promote `RAG_EXTRACTOR=docling` (hoặc `auto` với circuit breaker) làm default production.",
            "- Theo dõi metric Docling (latency p95, fallback rate) qua dashboard để bắt regression sớm.",
            "- Giữ `eval/EVAL.md` này làm baseline cho M2/M3 — mọi thay đổi pipeline RAG về sau "
            "phải re-run `python eval/run_compare.py` và so sánh với số liệu này.",
        ]
    else:
        body = [
            f"**Kết luận: FAIL.** {reason}",
            "",
            f"Docling FIXED {fixed} query và IMPROVED {improved} query, nhưng REGRESSED {regressed} "
            f"+ WORSE {worse} làm cân bằng tổng thể chưa đạt gate.",
            "",
            "**Khuyến nghị (3 hướng đồng bộ CONTEXT 05 Rủi ro 4):**",
            "",
            "1. **Reranker** (defer M3 backlog 999.2): thêm cross-encoder rerank top-20 → top-5 "
            "có thể đẩy top-3 lên đáng kể mà không đổi pipeline embedding.",
            "2. **Hybrid retrieval**: kết hợp BM25 (sparse) + dense embedding để vá những query "
            "có keyword Việt đặc thù mà embedding miss.",
            "3. **Data improvement**: kiểm tra root cause — nhiều khi gap là do tài liệu nguồn thiếu "
            "thông tin (như trường hợp BS Lê Phương trong CONTEXT) chứ không phải bug RAG. "
            "Bổ sung dataset + query vàng cho domain Medinet thật.",
            "",
            "**KHÔNG** xem FAIL là milestone fail — Phase 5 còn cung cấp đủ telemetry để chọn 1 trong 3 hướng trên.",
        ]
    return "\n".join(["## 6. Conclusion", "", *body, ""])


# ─── Section 7: Defer for M2/M3 ──────────────────────────────────────────────

def render_section_defer(retrieval_eval: dict[str, Any]) -> str:
    """Section 7: liệt kê deferred ideas + query có verdict REGRESSED/both_miss."""
    per_query = retrieval_eval.get("per_query", [])
    flagged = [
        q for q in per_query if q.get("verdict") in ("REGRESSED", "both_miss")
    ]
    flagged_lines: list[str] = []
    for q in flagged:
        flagged_lines.append(
            f"  - `{q.get('id')}` ({q.get('verdict')}): expected `{q.get('expected')}` "
            f"— native_rank={q.get('native_rank') or 'miss'}, "
            f"docling_rank={q.get('docling_rank') or 'miss'}"
        )

    lines = [
        "## 7. Defer for M2/M3",
        "",
        "**Backlog idea (CONTEXT 05 Deferred Ideas):**",
        "",
        "- 999.13 — Auto eval CI (GitHub Actions chạy `python eval/run_compare.py` mỗi PR vào `pipeline.go`).",
        "- 999.14 — Visual dashboard eval (Streamlit / web UI để admin xem metrics history).",
        "- 999.15 — Larger eval dataset (100+ queries từ production logs khi có data thật).",
        "",
    ]
    if flagged:
        lines.extend(
            [
                f"**Query cần điều tra ({len(flagged)} flagged — verdict REGRESSED hoặc both_miss):**",
                "",
                *flagged_lines,
                "",
            ]
        )
    else:
        lines.extend(
            [
                "**Query cần điều tra:** không có (0 query REGRESSED hoặc both_miss).",
                "",
            ]
        )
    return "\n".join(lines)


# ─── Top-level EVAL.md builder ───────────────────────────────────────────────

def build_eval_md(
    native: dict[str, Any],
    docling: dict[str, Any],
    extraction: dict[str, Any],
    retrieval_eval: dict[str, Any],
    verdict: str,
    reason: str,
) -> str:
    """Sinh nội dung EVAL.md đầy đủ 7 section."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    header = "\n".join(
        [
            "# EVAL — M1 RAG Quality with Docling",
            "",
            f"**Ngày chạy:** {today}",
            f"**Verdict:** {verdict}",
            f"**Reason:** {reason}",
            "",
            "> Báo cáo định lượng so sánh `RAG_EXTRACTOR=native` vs `=docling` trên cùng dataset + queries vàng. "
            "Sinh tự động bởi `python eval/run_compare.py` (Plan 05-04, EVAL-04). "
            "EVAL.md vẫn được sinh dù FAIL — số liệu đầy đủ để debug.",
            "",
            "---",
            "",
        ]
    )

    sections = [
        render_section_setup(native, docling, extraction),
        render_section_retrieval(retrieval_eval),
        render_section_per_query(retrieval_eval),
        render_section_per_document(extraction),
        render_section_smoke(),
        render_section_conclusion(verdict, reason, retrieval_eval),
        render_section_defer(retrieval_eval),
    ]

    footer = "\n".join(
        [
            "---",
            "",
            f"_Generated by `eval/run_compare.py` at {datetime.now(timezone.utc).isoformat(timespec='seconds')} UTC._",
            "",
        ]
    )

    return header + "\n".join(sections) + "\n" + footer


# ═══════════════════════════════════════════════════════════════════════════════
# 6. CLI ENTRY
# ═══════════════════════════════════════════════════════════════════════════════

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Orchestrator + Quality Gate + EVAL.md generator (Plan 05-04, EVAL-04)"
    )
    p.add_argument(
        "--native-snapshot",
        type=Path,
        default=DEFAULT_NATIVE,
        help=f"Path tới baseline_native.json (default: {DEFAULT_NATIVE})",
    )
    p.add_argument(
        "--docling-snapshot",
        type=Path,
        default=DEFAULT_DOCLING,
        help=f"Path tới baseline_docling.json (default: {DEFAULT_DOCLING})",
    )
    p.add_argument(
        "--extraction-out",
        type=Path,
        default=DEFAULT_EXTRACTION_OUT,
        help=f"Path tới extraction_compare.json (default: {DEFAULT_EXTRACTION_OUT})",
    )
    p.add_argument(
        "--retrieval-out",
        type=Path,
        default=DEFAULT_RETRIEVAL_OUT,
        help=f"Path tới retrieval_eval.json (default: {DEFAULT_RETRIEVAL_OUT})",
    )
    p.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_EVAL_MD,
        help=f"Path xuất EVAL.md (default: {DEFAULT_EVAL_MD})",
    )
    p.add_argument(
        "--skip-subprocess",
        action="store_true",
        help="Skip chạy run_extraction_compare.py + run_retrieval_eval.py (dùng intermediate JSON đã có).",
    )
    p.add_argument(
        "--skip-extraction",
        action="store_true",
        help="Skip chạy run_extraction_compare.py (granular control).",
    )
    p.add_argument(
        "--skip-retrieval",
        action="store_true",
        help="Skip chạy run_retrieval_eval.py (granular control).",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()

    # Step 1: pre-condition
    logger.info("=" * 70)
    logger.info("Plan 05-04 — run_compare.py orchestrator + quality gate + EVAL.md")
    logger.info("=" * 70)
    precondition_check(args.native_snapshot, args.docling_snapshot)

    # Step 2: orchestrate subprocess
    extraction_script = REPO_ROOT / "eval" / "run_extraction_compare.py"
    retrieval_script = REPO_ROOT / "eval" / "run_retrieval_eval.py"

    skip_all = args.skip_subprocess
    if not skip_all and not args.skip_extraction:
        run_subprocess(extraction_script, "run_extraction_compare.py")
    else:
        logger.info("Skip subprocess run_extraction_compare.py (theo flag)")

    if not skip_all and not args.skip_retrieval:
        run_subprocess(retrieval_script, "run_retrieval_eval.py")
    else:
        logger.info("Skip subprocess run_retrieval_eval.py (theo flag)")

    # Step 3: load 4 JSON
    native = load_json(args.native_snapshot, "baseline_native.json")
    docling = load_json(args.docling_snapshot, "baseline_docling.json")
    extraction = load_json(args.extraction_out, "extraction_compare.json")
    retrieval_eval = load_json(args.retrieval_out, "retrieval_eval.json")

    # Step 4: apply quality gate
    native_top3 = native.get("retrieval", {}).get("top_3_hit_rate")
    docling_top3 = docling.get("retrieval", {}).get("top_3_hit_rate")
    if native_top3 is None or docling_top3 is None:
        logger.error(
            "[FATAL] Snapshot thiếu retrieval.top_3_hit_rate — native=%s docling=%s",
            native_top3,
            docling_top3,
        )
        sys.exit(1)

    verdict, reason = evaluate_gate(native_top3, docling_top3)
    logger.info("─" * 70)
    logger.info("QUALITY GATE: %s", verdict)
    logger.info("Reason: %s", reason)
    logger.info("  native_top3  = %.4f", native_top3)
    logger.info("  docling_top3 = %.4f", docling_top3)
    logger.info("  delta        = %+.4f (%+.1fpp)", docling_top3 - native_top3, (docling_top3 - native_top3) * 100)
    logger.info("─" * 70)

    # Step 5: sinh EVAL.md (cả PASS + FAIL đều ghi)
    md_content = build_eval_md(native, docling, extraction, retrieval_eval, verdict, reason)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(md_content, encoding="utf-8")
    logger.info("EVAL.md ghi: %s (%d ký tự)", args.out, len(md_content))

    # Step 6: exit code 0/1 theo gate
    exit_code = 0 if verdict == "PASS" else 1
    logger.info("Exit code: %d (%s)", exit_code, verdict)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
