"""EVAL-02 — So sánh chất lượng extraction per-document giữa native vs docling.

Plan: .planning/phases/05-eval-compare-quality-gate/05-02-PLAN.md (Wave 2).

Mục tiêu:
  - Load 2 snapshot (`eval/baseline_native.json` + `eval/baseline_docling.json`).
  - Per-document compare 4 metric:
      * chunks_count
      * avg_chunk_tokens
      * heading_recall — match heading vàng (`eval/dataset/headings.json`) trong
        chunk content (substring case-insensitive + accent-stripped — W2 fix
        cho tiếng Việt có dấu).
      * tables_preserved — đếm chunks có metadata.is_table = true (Phase 4 CFG-06).
  - Sinh `eval/extraction_compare.json` cho Plan 05-04 orchestrator consume.
  - Print summary table ra stdout (tabulate).

Heading recall query DB direct (psycopg) để tránh expose endpoint internal —
auto-mode log Phase 5 CONTEXT mục "Heading recall query: DB direct".

Usage:
    python eval/run_extraction_compare.py
    python eval/run_extraction_compare.py \\
        --native-snapshot eval/baseline_native.json \\
        --docling-snapshot eval/baseline_docling.json \\
        --out eval/extraction_compare.json

Pre-condition: cần `baseline_docling.json` (Plan 05-01 output) + Postgres
running với data đã ingest cả 2 mode. Nếu thiếu docling snapshot →
SystemExit(2) với message hướng dẫn chạy `python eval/run_docling.py` trước.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import unicodedata
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psycopg
from dotenv import load_dotenv

# ─── Logging setup (đồng bộ lib.py / baseline.py) ───────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ─── Env load ─────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(REPO_ROOT / "eval" / ".env")

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "medinet_central")
DB_USER = os.getenv("DB_USER", "medinet")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

DEFAULT_NATIVE = REPO_ROOT / "eval" / "baseline_native.json"
DEFAULT_DOCLING = REPO_ROOT / "eval" / "baseline_docling.json"
DEFAULT_HEADINGS = REPO_ROOT / "eval" / "dataset" / "headings.json"
DEFAULT_OUT = REPO_ROOT / "eval" / "extraction_compare.json"


# ═══════════════════════════════════════════════════════════════════════════
# Hardcoded mapping số bảng vàng per-file (Phase 1 đã label trong dataset).
# Plan task spec line 122: "Hardcode mapping ngắn ở đầu script". Fallback
# tables_total = 0 nếu file không có trong mapping (script vẫn chạy không crash).
# ═══════════════════════════════════════════════════════════════════════════

TABLES_TOTAL_GOLD: dict[str, int] = {
    "DMD_T1-01_DinhVi_TrungTam_v1.docx": 4,
    "DMD_T1-01_scanned.pdf": 4,
    "DMD_T1-02_TuDien_ThuongHieu_v1.docx": 0,
    "DMD_T1-03_Script_Library_v1.docx": 0,
    "DMD_T1-04_FAQ_ThuongHieu_v1.docx": 1,
    "DMD_T1-04_scanned.pdf": 1,
    "DMD_T3-02_PhanCong_NhanVat_v1.docx": 1,  # ma trận 4×7
    "DMD_T5-01_ContentStrategy_12TuyenND_v1.docx": 0,
    "DMD_T5-02_Playbook_KenhTruyen_v1.docx": 0,
    "tri_thuc_chinh_tri.pdf": 0,
}


# ═══════════════════════════════════════════════════════════════════════════
# Helper functions
# ═══════════════════════════════════════════════════════════════════════════


def strip_accent(s: str) -> str:
    """Lột dấu tiếng Việt + lowercase + collapse whitespace.

    W2 fix: heading vàng tiếng Việt có dấu, chunk content có thể normalize khác
    (vd Docling output normalized form khác python-docx). Ta strip accent +
    lowercase trước khi substring match → robust hơn.

    Ví dụ: "PHẦN 01 | CÂU TUYÊN BỐ" → "phan 01 | cau tuyen bo".
    """
    if not s:
        return ""
    # NFKD decompose: "ầ" → "a" + combining grave/circumflex
    nfkd = unicodedata.normalize("NFKD", s)
    # Drop combining marks (category Mn) + lowercase
    stripped = "".join(c for c in nfkd if not unicodedata.combining(c))
    # Collapse whitespace
    return " ".join(stripped.lower().split())


def count_heading_recall(chunks: list[dict[str, Any]], gold_headings: list[str]) -> tuple[int, int, float]:
    """Tính heading recall.

    Cho mỗi gold heading, search trong list chunks: nếu có chunk nào chứa
    heading đó (substring, accent-stripped, case-insensitive) → match.

    Returns (matched_count, total_count, recall).
    Recall = matched / total. Nếu total = 0 → recall = 0.0 (không có heading
    vàng để compute).
    """
    total = len(gold_headings)
    if total == 0:
        return 0, 0, 0.0

    # Pre-normalize chunk contents 1 lần (avoid O(N×M) accent strip).
    normalized_chunks = [strip_accent(c.get("content", "")) for c in chunks]

    matched = 0
    for heading in gold_headings:
        h_norm = strip_accent(heading)
        if not h_norm:
            continue
        if any(h_norm in chunk_norm for chunk_norm in normalized_chunks):
            matched += 1

    recall = matched / total if total > 0 else 0.0
    return matched, total, recall


def count_tables(chunks: list[dict[str, Any]]) -> int:
    """Đếm chunks có metadata.is_table = true.

    metadata trong document_chunks là JSONB → psycopg tự decode thành dict.
    is_table có thể là bool true hoặc string "true" (depending on extractor
    output). Accept cả 2.
    """
    count = 0
    for chunk in chunks:
        metadata = chunk.get("metadata") or {}
        if not isinstance(metadata, dict):
            # Defensive: nếu metadata là string JSON chưa decode
            try:
                metadata = json.loads(metadata) if isinstance(metadata, str) else {}
            except (json.JSONDecodeError, TypeError):
                metadata = {}
        is_table = metadata.get("is_table")
        if is_table is True or (isinstance(is_table, str) and is_table.lower() == "true"):
            count += 1
    return count


def query_chunks_for_doc(conn: psycopg.Connection, doc_id: str) -> list[dict[str, Any]]:
    """Query content + metadata cho mọi chunk của 1 document.

    Returns list of {"content": str, "metadata": dict}. Empty list nếu
    document không có chunks (vd ingestion fail / status=error).
    """
    if not doc_id:
        return []
    with conn.cursor() as cur:
        cur.execute(
            "SELECT content, metadata FROM document_chunks WHERE document_id = %s",
            (doc_id,),
        )
        rows = cur.fetchall()
    return [{"content": row[0] or "", "metadata": row[1] or {}} for row in rows]


# ═══════════════════════════════════════════════════════════════════════════
# Snapshot loading + pre-condition
# ═══════════════════════════════════════════════════════════════════════════


def load_snapshot(path: Path, label: str) -> dict[str, Any]:
    """Load JSON snapshot. SystemExit(2) nếu thiếu / lỗi parse."""
    if not path.exists():
        if label == "docling":
            raise SystemExit(
                f"Pre-condition FAIL: thiếu snapshot {path}.\n"
                f"Run `python eval/run_docling.py` first."
            )
        raise SystemExit(
            f"Pre-condition FAIL: thiếu snapshot {path} ({label}).\n"
            f"Phase 1 baseline phải tồn tại — kiểm tra commit history (eval/baseline_native.json)."
        )
    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise SystemExit(f"Pre-condition FAIL: snapshot {path} parse JSON lỗi: {e}") from e
    logger.info("Loaded snapshot %s: %d documents (mode=%s)",
                label, len(data.get("documents", [])), data.get("extractor_mode", "?"))
    return data


def load_headings(path: Path) -> dict[str, list[str]]:
    """Load gold headings từ Phase 1 EVAL-01."""
    if not path.exists():
        raise SystemExit(f"Pre-condition FAIL: thiếu {path} (Phase 1 EVAL-01 artifact).")
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def build_dsn() -> str:
    """Build psycopg DSN từ env."""
    return (
        f"host={DB_HOST} port={DB_PORT} dbname={DB_NAME} "
        f"user={DB_USER} password={DB_PASSWORD}"
    )


# ═══════════════════════════════════════════════════════════════════════════
# Main compare logic
# ═══════════════════════════════════════════════════════════════════════════


def compare_one_document(
    conn: psycopg.Connection,
    filename: str,
    native_doc: dict[str, Any] | None,
    docling_doc: dict[str, Any] | None,
    gold_headings: list[str],
) -> dict[str, Any]:
    """So sánh 1 document giữa 2 mode. Returns dict theo schema interfaces."""
    tables_total = TABLES_TOTAL_GOLD.get(filename, 0)

    def metrics_for(doc: dict[str, Any] | None, label: str) -> dict[str, Any]:
        if doc is None:
            logger.warning("  [%s] document missing trong snapshot — fill zeros", label)
            return {
                "chunks_count": 0,
                "avg_chunk_tokens": 0.0,
                "heading_recall": 0.0,
                "headings_matched": 0,
                "headings_total": len(gold_headings),
                "tables_preserved": 0,
                "tables_total": tables_total,
            }
        doc_id = doc.get("id") or doc.get("doc_id") or ""
        chunks = query_chunks_for_doc(conn, doc_id)
        matched, total, recall = count_heading_recall(chunks, gold_headings)
        tables_preserved = count_tables(chunks)
        logger.info(
            "  [%s] doc_id=%s db_chunks=%d heading_recall=%.3f (%d/%d) tables=%d/%d",
            label, doc_id[:8], len(chunks), recall, matched, total, tables_preserved, tables_total,
        )
        return {
            "chunks_count": int(doc.get("chunks_count", 0) or 0),
            "avg_chunk_tokens": float(doc.get("avg_chunk_tokens", 0.0) or 0.0),
            "heading_recall": round(recall, 4),
            "headings_matched": matched,
            "headings_total": total,
            "tables_preserved": tables_preserved,
            "tables_total": tables_total,
        }

    native_m = metrics_for(native_doc, "native")
    docling_m = metrics_for(docling_doc, "docling")

    delta = {
        "chunks_count": docling_m["chunks_count"] - native_m["chunks_count"],
        "avg_chunk_tokens": round(docling_m["avg_chunk_tokens"] - native_m["avg_chunk_tokens"], 2),
        "heading_recall_pp": round((docling_m["heading_recall"] - native_m["heading_recall"]) * 100, 2),
        "tables_preserved": docling_m["tables_preserved"] - native_m["tables_preserved"],
    }

    return {
        "filename": filename,
        "native": native_m,
        "docling": docling_m,
        "delta": delta,
    }


def index_by_filename(snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Index documents trong snapshot theo filename để lookup nhanh."""
    out: dict[str, dict[str, Any]] = {}
    for doc in snapshot.get("documents", []):
        fname = doc.get("filename")
        if fname:
            out[fname] = doc
    return out


def compute_summary(per_doc: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate summary từ per-document results."""
    if not per_doc:
        return {
            "avg_heading_recall_native": 0.0,
            "avg_heading_recall_docling": 0.0,
            "table_preservation_native": 0.0,
            "table_preservation_docling": 0.0,
            "documents_count": 0,
        }

    n_recall = sum(d["native"]["heading_recall"] for d in per_doc) / len(per_doc)
    d_recall = sum(d["docling"]["heading_recall"] for d in per_doc) / len(per_doc)

    n_preserved = sum(d["native"]["tables_preserved"] for d in per_doc)
    d_preserved = sum(d["docling"]["tables_preserved"] for d in per_doc)
    total_tables_gold = sum(d["native"]["tables_total"] for d in per_doc)

    n_table_rate = n_preserved / total_tables_gold if total_tables_gold > 0 else 0.0
    d_table_rate = d_preserved / total_tables_gold if total_tables_gold > 0 else 0.0

    return {
        "avg_heading_recall_native": round(n_recall, 4),
        "avg_heading_recall_docling": round(d_recall, 4),
        "table_preservation_native": round(n_table_rate, 4),
        "table_preservation_docling": round(d_table_rate, 4),
        "tables_total_gold": total_tables_gold,
        "tables_preserved_native": n_preserved,
        "tables_preserved_docling": d_preserved,
        "documents_count": len(per_doc),
    }


def print_summary_table(per_doc: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    """Print Markdown-style summary table ra stdout."""
    try:
        from tabulate import tabulate
    except ImportError:
        logger.warning("tabulate chưa cài — skip pretty print. `pip install tabulate>=0.9`.")
        return

    rows = []
    for d in per_doc:
        rows.append([
            d["filename"][:42],
            d["native"]["chunks_count"],
            d["docling"]["chunks_count"],
            f"{d['native']['heading_recall']:.2f}",
            f"{d['docling']['heading_recall']:.2f}",
            f"{d['delta']['heading_recall_pp']:+.1f}pp",
            f"{d['native']['tables_preserved']}/{d['native']['tables_total']}",
            f"{d['docling']['tables_preserved']}/{d['docling']['tables_total']}",
        ])
    headers = ["Filename", "N chunks", "D chunks", "N recall", "D recall", "Δ recall", "N tables", "D tables"]
    print("\n" + tabulate(rows, headers=headers, tablefmt="github"))

    print("\nAggregate:")
    print(f"  avg_heading_recall: native={summary['avg_heading_recall_native']:.3f} → docling={summary['avg_heading_recall_docling']:.3f}")
    print(f"  table_preservation: native={summary['table_preservation_native']:.3f} → docling={summary['table_preservation_docling']:.3f}")
    print(f"  tables (preserved/gold): native={summary['tables_preserved_native']}/{summary['tables_total_gold']}, docling={summary['tables_preserved_docling']}/{summary['tables_total_gold']}")


# ═══════════════════════════════════════════════════════════════════════════
# Entrypoint
# ═══════════════════════════════════════════════════════════════════════════


def main() -> int:
    parser = argparse.ArgumentParser(
        description="EVAL-02 — So sánh extraction quality per-document (native vs docling).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--native-snapshot", type=Path, default=DEFAULT_NATIVE,
                        help="Path tới baseline_native.json (Phase 1, immutable).")
    parser.add_argument("--docling-snapshot", type=Path, default=DEFAULT_DOCLING,
                        help="Path tới baseline_docling.json (Plan 05-01 output).")
    parser.add_argument("--headings", type=Path, default=DEFAULT_HEADINGS,
                        help="Path tới headings.json gold (Phase 1 EVAL-01).")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT,
                        help="Output JSON intermediate (cho Plan 05-04 orchestrator).")
    parser.add_argument("--db-dsn", default=None,
                        help="Postgres DSN (override env DB_*). Format: 'host=... dbname=... user=... password=...'")
    args = parser.parse_args()

    # ─── Pre-condition ────────────────────────────────────────────────────
    native = load_snapshot(args.native_snapshot, "native")
    docling = load_snapshot(args.docling_snapshot, "docling")
    headings_map = load_headings(args.headings)
    logger.info("Loaded gold headings cho %d files", len(headings_map))

    # ─── Index docs theo filename ───────────────────────────────────────
    native_by_name = index_by_filename(native)
    docling_by_name = index_by_filename(docling)

    # Union filenames (theo native order — stable cho diff git)
    filenames: list[str] = list(native_by_name.keys())
    for fname in docling_by_name:
        if fname not in filenames:
            filenames.append(fname)

    # ─── Postgres connect ─────────────────────────────────────────────────
    dsn = args.db_dsn or build_dsn()
    logger.info("Connecting Postgres dbname=%s host=%s …", DB_NAME, DB_HOST)
    try:
        conn = psycopg.connect(dsn, connect_timeout=10)
    except psycopg.Error as e:
        raise SystemExit(
            f"Pre-condition FAIL: Postgres connect lỗi: {e}\n"
            f"Kiểm tra DB_HOST/DB_PORT/DB_NAME/DB_USER/DB_PASSWORD env hoặc --db-dsn."
        ) from e

    # ─── Per-document compare ─────────────────────────────────────────────
    per_doc: list[dict[str, Any]] = []
    try:
        for filename in filenames:
            logger.info("Comparing %s …", filename)
            gold = headings_map.get(filename, [])
            if not gold:
                logger.warning("  Không có gold headings cho %s — heading_recall = 0", filename)
            row = compare_one_document(
                conn=conn,
                filename=filename,
                native_doc=native_by_name.get(filename),
                docling_doc=docling_by_name.get(filename),
                gold_headings=gold,
            )
            per_doc.append(row)
    finally:
        conn.close()

    # ─── Summary aggregate ────────────────────────────────────────────────
    summary = compute_summary(per_doc)

    out_payload = {
        "run_id": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "native_snapshot": str(args.native_snapshot.relative_to(REPO_ROOT)) if args.native_snapshot.is_absolute() else str(args.native_snapshot),
        "docling_snapshot": str(args.docling_snapshot.relative_to(REPO_ROOT)) if args.docling_snapshot.is_absolute() else str(args.docling_snapshot),
        "documents": per_doc,
        "summary": summary,
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as f:
        json.dump(out_payload, f, ensure_ascii=False, indent=2)
    logger.info("Wrote %s (%d documents, summary %d aggregate keys)",
                args.out, len(per_doc), len(summary))

    # ─── Pretty print ─────────────────────────────────────────────────────
    print_summary_table(per_doc, summary)

    return 0


if __name__ == "__main__":
    sys.exit(main())
