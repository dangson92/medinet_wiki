"""Cleanup state TRƯỚC mỗi eval run (Phase 9 EVAL-02 — idempotent reset).

Mixed strategy (RESEARCH Component Responsibilities):
1. API DELETE /api/documents/:id (cocoindex auto-tombstone chunks)
2. Postgres DELETE defensive (fallback nếu API stuck — TRUNCATE qua FK)
3. Redis DEL search:* + hub:*:invalidate + rate_limit:* cache (Phase 6 SEARCH-04)

Idempotent: chạy 2 lần với eval_hub trống KHÔNG raise.

CLI:
    python -m eval.scripts.cleanup [--skip-api] [--skip-postgres] [--skip-redis]

Trả exit 0 nếu xong (kể cả khi có WARN — chỉ HARD-FAIL khi không resolve được hub_id).
Trả exit 1 nếu eval_hub chưa seed (caller phải chạy ``psql -f seed_hub.sql`` trước).
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys

import httpx
import psycopg
import redis

# Module path: eval/scripts/cleanup.py → import eval.lib
from eval.lib import APIClient, EvalSettings, _dsn, get_eval_hub_id


async def _cleanup_via_api(settings: EvalSettings, hub_id: str) -> int:
    """List documents eval_hub → DELETE từng cái qua API. Trả count đã xoá.

    Cocoindex auto-tombstone chunks sau DELETE document (Phase 4 + Phase 5).
    Pagination per_page=100 (Phase 5 INGEST-08 cap).
    """
    deleted = 0
    async with APIClient(
        settings.backend_url, settings.admin_email, settings.admin_password
    ) as api:
        await api.login()
        page = 1
        while True:
            r = await api._request_with_retry(
                "GET",
                f"{settings.backend_url}/api/documents",
                params={"hub_id": hub_id, "page": page, "per_page": 100},
            )
            if r.status_code != 200:
                print(
                    f"  [API] WARN: list documents page {page} HTTP {r.status_code}",
                    file=sys.stderr,
                )
                break
            payload = r.json()
            data = payload.get("data", {})
            # Backend trả "items" hoặc "documents" tuỳ shape — accept cả 2.
            if isinstance(data, list):
                docs = data
            else:
                docs = data.get("items") or data.get("documents") or []
            if not docs:
                break
            for d in docs:
                doc_id = d.get("id")
                if not doc_id:
                    continue
                del_r = await api._request_with_retry(
                    "DELETE",
                    f"{settings.backend_url}/api/documents/{doc_id}",
                )
                if del_r.status_code in (200, 204):
                    deleted += 1
                else:
                    print(
                        f"  [API] WARN: DELETE {doc_id} HTTP {del_r.status_code}",
                        file=sys.stderr,
                    )
            # Pagination — meta có thể nằm ngoài data hoặc trong data
            meta = payload.get("meta") or (
                data.get("meta") if isinstance(data, dict) else {}
            ) or {}
            total_pages = meta.get("total_pages", 1)
            if page >= total_pages:
                break
            page += 1
    return deleted


def _cleanup_postgres_defensive(settings: EvalSettings, hub_id: str) -> int:
    """DELETE chunks + documents WHERE hub_id=eval_hub (defensive nếu API stuck).

    Cocoindex sẽ re-detect missing source vs target qua content-hash diff
    (LMDB fingerprint). Pattern này an toàn vì eval_hub isolation.
    """
    deleted = 0
    with psycopg.connect(_dsn(settings)) as conn, conn.cursor() as cur:
        cur.execute(
            "DELETE FROM chunks WHERE document_id IN "
            "(SELECT id FROM documents WHERE hub_id = %s)",
            (hub_id,),
        )
        deleted += cur.rowcount
        cur.execute("DELETE FROM documents WHERE hub_id = %s", (hub_id,))
        deleted += cur.rowcount
        conn.commit()
    return deleted


def _cleanup_redis_cache(_settings: EvalSettings) -> int:
    """DEL Redis cache key theo pattern Phase 6 SEARCH-04 + rate limit.

    Pattern:
    - ``search:*`` — search cache (Phase 6 SEARCH-04).
    - ``hub:*:invalidate`` — Pub/Sub invalidate marker.
    - ``rate_limit:*`` — defensive cho 429 không skew eval (Phase 5).
    """
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    r = redis.from_url(redis_url)
    deleted = 0
    for pattern in ("search:*", "hub:*:invalidate", "rate_limit:*"):
        keys = list(r.scan_iter(match=pattern, count=1000))
        if keys:
            r.delete(*keys)
            deleted += len(keys)
    return deleted


async def cleanup(
    skip_api: bool = False,
    skip_postgres: bool = False,
    skip_redis: bool = False,
) -> int:
    """Orchestrate 3 step cleanup. Trả exit code (0 OK, 1 hub chưa seed)."""
    settings = EvalSettings()

    try:
        hub_id = await get_eval_hub_id(settings)
    except SystemExit as e:
        print(f"FAIL: {e}", file=sys.stderr)
        return 1

    print(f"Cleanup eval_hub (id={hub_id})")

    if not skip_api:
        try:
            n = await _cleanup_via_api(settings, hub_id)
            print(
                f"  [API] DELETE {n} document(s) (cocoindex auto-tombstone chunks)"
            )
        except (httpx.RequestError, KeyError, ValueError) as e:
            print(
                f"  [API] WARN: {e} — fallback Postgres defensive",
                file=sys.stderr,
            )
    else:
        print("  [API] skipped")

    if not skip_postgres:
        try:
            n = _cleanup_postgres_defensive(settings, hub_id)
            print(
                f"  [Postgres] DELETE defensive {n} row(s) (chunks + documents)"
            )
        except psycopg.OperationalError as e:
            print(f"  [Postgres] WARN: {e}", file=sys.stderr)
    else:
        print("  [Postgres] skipped")

    if not skip_redis:
        try:
            n = _cleanup_redis_cache(settings)
            print(f"  [Redis] DEL {n} cache key(s)")
        except redis.RedisError as e:
            print(f"  [Redis] WARN: {e}", file=sys.stderr)
    else:
        print("  [Redis] skipped")

    print("Cleanup done.")
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI entry: ``python -m eval.scripts.cleanup [flags]``."""
    p = argparse.ArgumentParser(
        description="Cleanup eval_hub state idempotent (Phase 9 EVAL-02)",
    )
    p.add_argument(
        "--skip-api",
        action="store_true",
        help="Skip API DELETE /api/documents/:id step",
    )
    p.add_argument(
        "--skip-postgres",
        action="store_true",
        help="Skip Postgres DELETE defensive (TRUNCATE qua FK)",
    )
    p.add_argument(
        "--skip-redis",
        action="store_true",
        help="Skip Redis DEL search:* cache",
    )
    args = p.parse_args(argv)

    return asyncio.run(
        cleanup(
            skip_api=args.skip_api,
            skip_postgres=args.skip_postgres,
            skip_redis=args.skip_redis,
        )
    )


if __name__ == "__main__":
    sys.exit(main())
