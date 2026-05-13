"""Chạy lại CHỈ phần search 12 query (không upload lại) với min_score=0.05.

Mục đích: kiểm tra giả thuyết "min_score=0.3 default cắt 5/7 query empty".
Không tốn embedding cost cho doc upload (chỉ embed 12 query lần nữa qua /api/search).
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, UTC
from pathlib import Path

import httpx
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(REPO_ROOT / "eval" / ".env")

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8180")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@medinet.vn")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "Admin@123")
EVAL_HUB_CODE = os.getenv("EVAL_HUB_CODE", "eval")
MIN_SCORE = float(os.getenv("MIN_SCORE_OVERRIDE", "0.05"))


def login(client: httpx.Client) -> str:
    r = client.post(f"{BACKEND_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    r.raise_for_status()
    return r.json()["data"]["access_token"]


def get_hub_id(client: httpx.Client) -> str:
    r = client.get(f"{BACKEND_URL}/api/hubs")
    r.raise_for_status()
    for h in r.json()["data"]:
        if h.get("code") == EVAL_HUB_CODE:
            return h["id"]
    raise SystemExit(f"Eval hub '{EVAL_HUB_CODE}' không tồn tại")


def search_query(client: httpx.Client, query: str, hub_id: str, top_k: int = 5):
    body = {"query": query, "hub_ids": [hub_id], "top_k": top_k, "min_score": MIN_SCORE}
    r = client.post(f"{BACKEND_URL}/api/search", json=body)
    r.raise_for_status()
    return r.json()["data"]["results"]


def main() -> int:
    queries = [json.loads(line) for line in (REPO_ROOT / "eval/dataset/queries.jsonl").open(encoding="utf-8") if line.strip()]
    print(f"min_score override = {MIN_SCORE}")
    print(f"Queries: {len(queries)}")

    with httpx.Client(timeout=30) as client:
        token = login(client)
        client.headers["Authorization"] = f"Bearer {token}"
        hub_id = get_hub_id(client)
        print(f"hub_id={hub_id}")

        per_query = []
        for q in queries:
            results = search_query(client, q["query"], hub_id, top_k=5)
            top_5_files = [r.get("category", "") for r in results]
            expected = q["expected_doc_id"].lower()
            rank = None
            for idx, f in enumerate(top_5_files, 1):
                if f.lower() == expected:
                    rank = idx
                    break
            per_query.append({
                "id": q["id"],
                "expected_doc_id": q["expected_doc_id"],
                "actual_top_5": top_5_files,
                "rank": rank,
            })
            mark = f"OK rank={rank}" if rank else f"MISS top5={top_5_files[:3]}"
            print(f"  {q['id']}: {mark}")

    n = len(per_query)
    top1 = sum(1 for q in per_query if q["rank"] == 1) / n
    top3 = sum(1 for q in per_query if q["rank"] and q["rank"] <= 3) / n
    top5 = sum(1 for q in per_query if q["rank"] and q["rank"] <= 5) / n
    mrr = sum(1 / q["rank"] for q in per_query if q["rank"]) / n

    print(f"\ntop-1={top1:.3f}  top-3={top3:.3f}  top-5={top5:.3f}  mrr={mrr:.3f}")

    out = {
        "run_id": datetime.now(UTC).isoformat(),
        "extractor_mode": "native",
        "min_score_override": MIN_SCORE,
        "retrieval": {
            "top_1_hit_rate": top1,
            "top_3_hit_rate": top3,
            "top_5_hit_rate": top5,
            "mrr": mrr,
            "per_query": per_query,
        },
    }
    out_path = REPO_ROOT / "eval/baseline_native_minscore005.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSaved: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
