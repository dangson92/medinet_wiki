"""Chạy ingestion với RAG_EXTRACTOR=docling runtime + sinh snapshot baseline_docling.json.

Phase 5 Plan 05-01 — input chính cho Plan 05-02..04 (extraction compare, retrieval eval,
orchestrator). Pattern song song với eval/baseline.py Phase 1 nhưng dùng eval/lib.py.

Pipeline:
  0. Pre-flight (lib.preflight) — backend Go, ChromaDB, hub seed.
  1. Login admin qua APIClient.
  2. Capture embedder config TRƯỚC khi switch mode.
  3. assert_embedder_match(current, baseline_native.json) — hard fail nếu lệch (gate fairness).
  4. Switch mode: PUT /api/rag-config {"extractor_mode": "docling"} (CFG-03).
  5. try:
       - upload_dataset 10 file (8 sources + 2 scanned), poll completion.
       - Verify Docling thực sự được dùng (count extractor_used == "docling").
       - evaluate_queries 12 query → top-1/3/5 + MRR.
     finally:
       - Restore /api/rag-config về extractor_mode=auto (đảm bảo dev mode không stuck).
  6. Snapshot eval/baseline_docling.json (schema identical baseline_native.json + extractor_used per-doc).

Chạy:
    python eval/run_docling.py [--top-k 5] [--upload-timeout 300] [--skip-cleanup]

Tiền điều kiện:
  - Backend Go đang chạy (RAG_EXTRACTOR cho phép switch — config hot-swap CFG-03).
  - Docling sidecar service đang chạy (Phase 2 — http://localhost:8081).
  - eval/baseline_native.json tồn tại (Phase 1 — embedder lock reference).
  - Hub `eval` đã seed.

Output: eval/baseline_docling.json (artifact runtime do user chạy).

LƯU Ý: Script này runtime defer cho user (cần Docling service real từ Phase 2-4).
Executor commit code + verify import, KHÔNG chạy thực tế ở Plan 05-01.
"""
from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
from pathlib import Path

# Đảm bảo lib.py import được khi chạy `python eval/run_docling.py` từ root repo
sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import (  # noqa: E402
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    BACKEND_URL,
    EVAL_HUB_CODE,
    REPO_ROOT,
    APIClient,
    assert_embedder_match,
    evaluate_queries,
    get_embedder_config,
    make_snapshot,
    preflight,
    upload_dataset,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

OUTPUT_PATH = REPO_ROOT / "eval" / "baseline_docling.json"
BASELINE_NATIVE_PATH = REPO_ROOT / "eval" / "baseline_native.json"
DATASET_DIR = REPO_ROOT / "eval" / "dataset"
QUERIES_PATH = DATASET_DIR / "queries.jsonl"
CLEANUP_SCRIPT = REPO_ROOT / "eval" / "scripts" / "cleanup.py"


def run_cleanup() -> None:
    """Chạy eval/scripts/cleanup.py reset state eval_hub trước khi switch mode.

    Theo CONTEXT mục D Rủi ro 2: cleanup eval_hub trước khi switch + chờ all
    workers idle để tránh race condition khi switch mode runtime.
    """
    if not CLEANUP_SCRIPT.exists():
        logger.warning(
            "Cleanup script không tồn tại tại %s — bỏ qua (state có thể chưa sạch)",
            CLEANUP_SCRIPT,
        )
        return

    logger.info("Cleanup eval_hub state qua %s", CLEANUP_SCRIPT)
    result = subprocess.run(
        [sys.executable, str(CLEANUP_SCRIPT)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise SystemExit(
            f"Cleanup FAIL (exit {result.returncode}):\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )
    logger.info("Cleanup OK")


def run_docling(args: argparse.Namespace) -> int:
    """Pipeline chính: pre-flight → switch mode docling → upload → eval → restore auto."""

    # Step 0: Pre-flight
    preflight(BACKEND_URL, None, None, EVAL_HUB_CODE)  # type: ignore[arg-type]
    # Note: preflight signature dùng default chroma_url + db_dsn từ env

    # Step 1: Login
    client = APIClient(BACKEND_URL, ADMIN_EMAIL, ADMIN_PASSWORD)
    try:
        client.login()

        # Step 2: Capture embedder config TRƯỚC khi switch mode (gate fairness)
        embedder = get_embedder_config(client)
        logger.info(
            "Embedder current: %s/%s dim=%s",
            embedder["embedder_provider"],
            embedder["embedder_model"],
            embedder["embedder_dim"],
        )

        # Step 3: Embedder lock verify — hard fail nếu lệch baseline_native.json
        assert_embedder_match(embedder, str(BASELINE_NATIVE_PATH))

        # Step 4: Cleanup state (optional skip qua --skip-cleanup)
        if not args.skip_cleanup:
            run_cleanup()
        else:
            logger.info("Skip cleanup (--skip-cleanup)")

        # Step 5: Capture original mode để restore
        current_cfg = client.get_rag_config()
        original_mode = current_cfg.get("extractor_mode", "auto")
        logger.info("Original extractor_mode = %s (sẽ restore cuối run)", original_mode)

        # Step 6: Switch mode docling — log loud
        logger.info("=" * 70)
        logger.info("SWITCH extractor_mode → docling (CFG-03 hot-swap)")
        logger.info("=" * 70)
        client.put_rag_config({"extractor_mode": "docling"})

        # Step 7: try/finally restore mode auto — đảm bảo dev mode không stuck
        snapshot: dict | None = None
        try:
            hub_id = client.get_hub_id(EVAL_HUB_CODE)
            logger.info("eval_hub_id = %s", hub_id)

            # Upload dataset (10 file, timeout cao 300s vì Docling chậm)
            docs = upload_dataset(
                client,
                hub_id,
                str(DATASET_DIR),
                timeout=args.upload_timeout,
            )

            # Verify Docling thực sự được dùng (CONTEXT mục D step 3)
            docling_used = sum(1 for d in docs if d.extractor_used == "docling")
            native_used = sum(1 for d in docs if d.extractor_used == "native")
            unknown = sum(1 for d in docs if not d.extractor_used)
            logger.info(
                "extractor_used distribution: docling=%d native=%d unknown=%d (total=%d)",
                docling_used,
                native_used,
                unknown,
                len(docs),
            )
            if docling_used == 0:
                logger.warning(
                    "CẢNH BÁO: KHÔNG có document nào dùng docling — "
                    "circuit breaker có thể đã fallback hết về native. "
                    "Kiểm tra Docling sidecar @ http://localhost:8081 + log backend."
                )

            # Run 12 query
            metrics = evaluate_queries(
                client,
                hub_id,
                str(QUERIES_PATH),
                top_k=args.top_k,
            )

            # Build snapshot identical schema baseline_native.json
            snapshot = make_snapshot(
                extractor_mode="docling",
                embedder=embedder,
                eval_hub_id=hub_id,
                docs=docs,
                metrics=metrics,
                queries_count=len(metrics.per_query),
                extra={
                    "min_score_used": 0.0,
                    "_note_phase": "Phase 5 Plan 05-01 — Docling mode run",
                    "extractor_used_summary": {
                        "docling": docling_used,
                        "native": native_used,
                        "unknown": unknown,
                    },
                },
            )

            OUTPUT_PATH.write_text(
                json.dumps(snapshot, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            logger.info(
                "Snapshot DONE → %s (top-1=%.3f top-3=%.3f top-5=%.3f mrr=%.3f)",
                OUTPUT_PATH,
                metrics.top_1_hit_rate,
                metrics.top_3_hit_rate,
                metrics.top_5_hit_rate,
                metrics.mrr,
            )
        finally:
            # Step 8: Restore mode auto (CONTEXT mục D "Restore mode sau run")
            try:
                client.put_rag_config({"extractor_mode": "auto"})
                logger.info("Restored extractor_mode=auto (dev mode an toàn)")
            except Exception as e:
                logger.error(
                    "RESTORE FAIL: extractor_mode có thể vẫn ở 'docling' — "
                    "manual restore qua: PUT %s/api/rag-config {\"extractor_mode\":\"auto\"}\n"
                    "Lỗi: %s",
                    BACKEND_URL,
                    e,
                )

        return 0 if snapshot else 1
    finally:
        client.close()


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Chạy ingestion mode docling + snapshot baseline_docling.json "
            "(Phase 5 Plan 05-01)"
        )
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Số kết quả lấy từ /api/search (default 5)",
    )
    parser.add_argument(
        "--upload-timeout",
        type=int,
        default=300,
        help="Timeout poll status mỗi file (default 300s — Docling chậm hơn baseline)",
    )
    parser.add_argument(
        "--skip-cleanup",
        action="store_true",
        help="Bỏ qua cleanup eval_hub state (mặc định chạy cleanup.py)",
    )
    args = parser.parse_args()
    return run_docling(args)


if __name__ == "__main__":
    sys.exit(main())
