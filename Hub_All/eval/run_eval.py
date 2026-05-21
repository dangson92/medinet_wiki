"""Eval orchestrator end-to-end (Phase 9 EVAL-02).

Workflow 8 bước:
  1. _check_llm_credentials (mock OR real LLM gate)
  2. preflight_check (healthz + readyz + Postgres + eval_hub seed)
  3. get_eval_hub_id (resolve UUID từ code='eval')
  4. Cleanup state (--skip-cleanup để bỏ qua)
  5. Login admin + upload 10 file (8 sources + 2 scanned PDF R4)
  6. Settle 2s cho cocoindex flush LMDB fingerprint
  7. Run 12 query qua POST /api/search top_k
  8. Compute metrics + write results.json + EVAL.md + exit verdict

CLI:
  python -m eval.run_eval                  # default: real LLM (yêu cầu OPENAI_API_KEY)
  python -m eval.run_eval --mock-embed     # smoke regression mode (KHÔNG gate verdict)
  python -m eval.run_eval --skip-cleanup   # skip cleanup step (vừa cleanup xong)
  python -m eval.run_eval --top-k 15       # tăng top_k (Vòng 3 iterate borderline)

Env switch (RESEARCH Open Q5):
  EVAL_MOCK_EMBED=1     → mock embedding (CI smoke; KHÔNG dùng cho gate verdict)
  EVAL_USE_REAL_LLM=1   → real OpenAI/Gemini call (Wave 4 gate verdict)
"""
from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

import httpx

from eval.lib import (
    APIClient,
    EvalSettings,
    get_eval_hub_id,
    preflight_check,
    upload_and_wait,
)
from eval.metrics import compute_latency_percentiles, compute_retrieval_metrics
from eval.report import gate_verdict, generate_eval_md

EVAL_ROOT = Path(__file__).resolve().parent
DATASET_SOURCES = EVAL_ROOT / "dataset" / "sources"
DATASET_SCANNED = EVAL_ROOT / "dataset" / "scanned"
QUERIES_PATH = EVAL_ROOT / "queries.jsonl"


def _load_queries() -> list[dict]:
    """Đọc queries.jsonl trả list 12 query (1 dòng / query, JSON ensure_ascii=False)."""
    if not QUERIES_PATH.exists():
        raise SystemExit(f"queries.jsonl không tồn tại: {QUERIES_PATH}")
    out: list[dict] = []
    for line in QUERIES_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        out.append(json.loads(line))
    if not out:
        raise SystemExit(f"queries.jsonl rỗng: {QUERIES_PATH}")
    return out


def _collect_dataset_files() -> list[Path]:
    """8 sources DOCX/PDF + 2 scanned PDF = 10 file.

    Raises SystemExit nếu dataset trống — hint restore từ git M1 archive
    commit 0af44f0 (Plan 09-01 đã làm trước đó).
    """
    files: list[Path] = []
    if DATASET_SOURCES.exists():
        files.extend(sorted(p for p in DATASET_SOURCES.iterdir() if p.is_file()))
    if DATASET_SCANNED.exists():
        files.extend(sorted(p for p in DATASET_SCANNED.iterdir() if p.is_file()))
    if not files:
        raise SystemExit(
            f"Dataset trống ({EVAL_ROOT}/dataset). Restore từ git M1: "
            f"git checkout 0af44f0 -- Hub_All/eval/dataset/"
        )
    return files


def _check_llm_credentials(mock_embed: bool) -> None:
    """Validate điều kiện LLM call trước khi chạy gate.

    - mock_embed=True → print WARNING + tiếp tục (KHÔNG gate verdict thật).
    - mock_embed=False + thiếu OPENAI_API_KEY → SystemExit kèm hint set env.
    """
    if mock_embed:
        print(
            "[WARN] MOCK EMBED mode — KHÔNG measure gate verdict thật. "
            "Chỉ smoke regression.",
            file=sys.stderr,
        )
        return
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        raise SystemExit(
            "OPENAI_API_KEY chưa set — gate verdict YÊU CẦU real LLM call.\n"
            "Set: export OPENAI_API_KEY=sk-... (PowerShell: $env:OPENAI_API_KEY='sk-...')\n"
            "HOẶC chạy smoke mock: python -m eval.run_eval --mock-embed\n"
            "Tiền điều kiện: tài khoản OpenAI tier paid (RESEARCH Open Q2)."
        )


async def run_eval(
    mock_embed: bool = False,
    skip_cleanup: bool = False,
    top_k: int = 10,
    output_path: Path | None = None,
    eval_md_path: Path | None = None,
) -> int:
    """Orchestrate full pipeline. Trả exit code (0 PASS, 1 FAIL).

    8 step pipeline (xem module docstring).
    """
    if output_path is None:
        output_path = EVAL_ROOT / "results.json"
    if eval_md_path is None:
        eval_md_path = EVAL_ROOT / "EVAL.md"

    settings = EvalSettings()
    _check_llm_credentials(mock_embed)

    print(f"[1/8] Preflight check (backend={settings.backend_url})...")
    await preflight_check(settings)

    print("[2/8] Resolve eval_hub_id...")
    hub_id = await get_eval_hub_id(settings)
    print(f"      eval_hub_id = {hub_id}")

    if not skip_cleanup:
        print("[3/8] Cleanup state (API DELETE + Postgres + Redis)...")
        # Late import để tránh cycle nếu cleanup.py import run_eval sau này.
        from eval.scripts.cleanup import cleanup as _cleanup

        rc = await _cleanup()
        if rc != 0:
            print(
                "  WARN: cleanup non-zero — continue anyway",
                file=sys.stderr,
            )
    else:
        print("[3/8] Cleanup SKIPPED (--skip-cleanup).")

    dataset_files = _collect_dataset_files()
    print(f"[4/8] Login admin + upload {len(dataset_files)} file...")

    upload_results: list[dict] = []
    per_query_results: list[dict] = []
    latencies: list[float] = []
    queries = _load_queries()

    async with APIClient(
        settings.backend_url, settings.admin_email, settings.admin_password
    ) as api:
        await api.login()

        for fp in dataset_files:
            print(f"      upload: {fp.name}")
            res = await upload_and_wait(
                api,
                fp,
                hub_id,
                timeout_sec=settings.upload_timeout_sec,
                poll_sec=settings.poll_interval_sec,
            )
            upload_results.append(res)
            print(
                f"        -> status={res['status']} "
                f"chunks={res.get('chunk_count', 0)}"
            )

        # Settle cocoindex flush LMDB fingerprint (Phase 4 race tolerant).
        print("[5/8] Settle 2s cho cocoindex flush LMDB...")
        await asyncio.sleep(2.0)

        # Run queries
        print(
            f"[6/8] Run {len(queries)} query qua POST /api/search top_k={top_k}..."
        )
        for q in queries:
            try:
                results, lat_ms = await api.search(q["query"], hub_id, top_k=top_k)
            except (httpx.HTTPError, OSError, ValueError, KeyError, RuntimeError) as e:
                print(
                    f"  q={q.get('id')} search FAIL: {e}",
                    file=sys.stderr,
                )
                results, lat_ms = [], 0.0
            per_query_results.append({"results": results})
            latencies.append(lat_ms)

    print("[7/8] Compute metrics (retrieval + latency)...")
    retrieval_metrics = compute_retrieval_metrics(queries, per_query_results)
    latency_stats = compute_latency_percentiles(latencies)

    upload_summary = {
        "completed": sum(
            1 for u in upload_results if u["status"] == "completed"
        ),
        "failed_unsupported": sum(
            1 for u in upload_results if u["status"] == "failed_unsupported"
        ),
        "failed": sum(1 for u in upload_results if u["status"] == "failed"),
        "timeout": sum(1 for u in upload_results if u["status"] == "timeout"),
        "documents": upload_results,
    }

    results = {
        "run_metadata": {
            "timestamp": datetime.now(UTC).isoformat(timespec="seconds"),
            "backend_url": settings.backend_url,
            "embedding_model": os.getenv(
                "EVAL_EMBEDDING_MODEL", "openai/text-embedding-3-large@1536"
            ),
            "llm_model": os.getenv("EVAL_LLM_MODEL", "openai/gpt-4o-mini"),
            "eval_hub_id": hub_id,
            "dataset_size": len(dataset_files),
            "query_count": len(queries),
            "mock_embed": mock_embed,
        },
        "upload_summary": upload_summary,
        "retrieval_metrics": retrieval_metrics,
        "latency": latency_stats,
    }

    print("[8/8] Write results.json + EVAL.md...")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(results, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    md = generate_eval_md(results)
    eval_md_path.parent.mkdir(parents=True, exist_ok=True)
    eval_md_path.write_text(md, encoding="utf-8")

    top_3 = retrieval_metrics["top_3_hit_rate"]
    v = gate_verdict(top_3)
    badge = "PASS" if v["verdict"] == "PASS" else "FAIL"
    print(
        "\n" + "=" * 60 + "\n"
        f"{badge}  top-3 hit rate = {top_3:.3f} ({top_3 * 100:.1f}%)\n"
        f"Exit code: {v['exit_code']}\n"
        f"Report: {eval_md_path}\n"
        f"Raw: {output_path}\n"
        + "=" * 60
    )
    if v.get("trigger_e5"):
        print(
            "TRIGGER E5 — STOP M2b. Discuss với user (PROJECT.md EXIT criteria).",
            file=sys.stderr,
        )
    if mock_embed:
        print(
            "[INFO] Mock-embed mode — verdict KHÔNG đại diện chất lượng thật. "
            "Re-run với real LLM cho gate.",
            file=sys.stderr,
        )

    return v["exit_code"]


def main(argv: list[str] | None = None) -> int:
    """CLI entry: ``python -m eval.run_eval [flags]``."""
    p = argparse.ArgumentParser(
        description="Eval orchestrator end-to-end (Phase 9 EVAL-02)",
    )
    p.add_argument(
        "--mock-embed",
        action="store_true",
        help=(
            "Mock embedding (smoke regression — KHÔNG gate verdict). "
            "Đồng bộ env EVAL_MOCK_EMBED=1."
        ),
    )
    p.add_argument(
        "--skip-cleanup",
        action="store_true",
        help="Skip cleanup step (dùng khi vừa cleanup xong tay)",
    )
    p.add_argument(
        "--top-k",
        type=int,
        default=10,
        help="top_k cho POST /api/search (default 10; Vòng 3 iterate tăng 15)",
    )
    p.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output results.json path (default eval/results.json)",
    )
    p.add_argument(
        "--eval-md",
        type=Path,
        default=None,
        help="Output EVAL.md path (default eval/EVAL.md)",
    )
    args = p.parse_args(argv)

    # Env consistency — flag CLI hoặc env đều bật mock.
    mock = args.mock_embed or os.getenv("EVAL_MOCK_EMBED", "").lower() in (
        "1",
        "true",
        "yes",
    )

    # SystemExit từ preflight / login / dataset → propagate exit code.
    try:
        return asyncio.run(
            run_eval(
                mock_embed=mock,
                skip_cleanup=args.skip_cleanup,
                top_k=args.top_k,
                output_path=args.output,
                eval_md_path=args.eval_md,
            )
        )
    except SystemExit as e:
        # SystemExit code int hoặc str — propagate code (1 nếu non-int).
        code = e.code
        if isinstance(code, int):
            return code
        if code is None:
            return 0
        print(str(code), file=sys.stderr)
        return 1


if __name__ == "__main__":
    # contextlib.suppress KeyboardInterrupt cho dev thoát Ctrl-C êm.
    with contextlib.suppress(KeyboardInterrupt):
        sys.exit(main())
