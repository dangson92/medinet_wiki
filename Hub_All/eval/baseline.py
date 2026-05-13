"""Đo baseline retrieval với extractor Go native — Phase 1 Eval Dataset & Baseline Native.

Pipeline orchestration script chính của Phase 1 (M1 RAG Quality with Docling).

Pipeline:
  0. Pre-flight: backend health + ChromaDB heartbeat + DB hub seed (REVISION 1 B3).
  1. Login admin -> access_token (handle 15-min TTL).
  2. Lấy embedder config: GET /api/rag-config + GET /api/rag-config/collections.
     Fail loud (SystemExit) nếu provider rỗng / dim=0 (REVISION 1 W5).
  3. Lấy eval_hub_id qua API list hub.
  4. Upload tất cả 10 file (8 sources + 2 scanned) -> poll status đến completed/error.
  5. Search 12 queries qua /api/search -> đo top-K hit rate + MRR.
     Match expected_doc_id (filename) với result.category lowercase (REVISION 1 B2).
  6. Ghi snapshot eval/baseline_native.json (REVISION 1 B1: KHÔNG có
     headings_recalled/missed — defer Phase 5 theo REQ EVAL-02).

Chạy:
    python eval/baseline.py [--top-k 5] [--upload-timeout 300] [--poll-interval 2]

Tiền điều kiện (Pre-flight tự verify, fail loud nếu thiếu):
  - Backend Go đang chạy ở BACKEND_URL.
  - ChromaDB đang chạy ở CHROMA_URL.
  - Hub `eval` đã seed (chạy `psql -f eval/scripts/seed_hub.sql` trước).
  - State sạch (chạy `python eval/scripts/cleanup.py` trước — khuyến nghị).

Output: `eval/baseline_native.json` (snapshot baseline cho M1 quality gate Phase 5).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import psycopg
from dotenv import load_dotenv

# ─── Logging setup (INFO mặc định, format khớp slog Go) ────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ─── Env load (eval/.env override eval/.env.example) ──────────────────────
REPO_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(REPO_ROOT / "eval" / ".env")

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8180")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@medinet.vn")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "Admin@123")
EVAL_HUB_CODE = os.getenv("EVAL_HUB_CODE", "eval")
CHROMA_URL = os.getenv("CHROMA_URL", "http://localhost:8000")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "medinet_central")
DB_USER = os.getenv("DB_USER", "medinet")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
UPLOAD_TIMEOUT_SEC = int(os.getenv("EVAL_UPLOAD_TIMEOUT_SEC", "300"))
POLL_INTERVAL_SEC = int(os.getenv("EVAL_POLL_INTERVAL_SEC", "2"))

SOURCES_DIR = REPO_ROOT / "eval" / "dataset" / "sources"
SCANNED_DIR = REPO_ROOT / "eval" / "dataset" / "scanned"
QUERIES_PATH = REPO_ROOT / "eval" / "dataset" / "queries.jsonl"
HEADINGS_PATH = REPO_ROOT / "eval" / "dataset" / "headings.json"
OUTPUT_PATH = REPO_ROOT / "eval" / "baseline_native.json"


# ─── Pre-flight (REVISION 1 B3) ───────────────────────────────────────────
async def preflight_check() -> None:
    """3 checks bắt buộc trước khi chạy baseline.

    1. Backend Go up: GET /api/health (fallback /api/rag-config nếu /health 404).
    2. ChromaDB up: GET /api/v2/heartbeat.
    3. Hub `eval` đã seed: SELECT id FROM hubs WHERE code='eval'.

    Fail loud -> SystemExit với hint cụ thể (lệnh khởi động + path seed file).
    """
    # Check 1: Backend Go health (fallback /api/rag-config public endpoint)
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            r = await client.get(f"{BACKEND_URL}/api/health")
            if r.status_code == 404:
                # Fallback: /api/rag-config (public endpoint, KHÔNG cần JWT)
                r = await client.get(f"{BACKEND_URL}/api/rag-config")
            if r.status_code != 200:
                raise SystemExit(
                    f"Pre-flight FAIL: Backend Go health check {BACKEND_URL} "
                    f"trả {r.status_code}. Khởi động backend trước:\n"
                    f"  cd backend && go run ./cmd/server"
                )
            logger.info("Pre-flight OK: Backend Go up @ %s", BACKEND_URL)
        except httpx.RequestError as e:
            raise SystemExit(
                f"Pre-flight FAIL: Không kết nối được backend ({BACKEND_URL}): {e}\n"
                f"Khởi động backend: cd backend && go run ./cmd/server"
            ) from e

        # Check 2: ChromaDB heartbeat (v2 API path chuẩn, public)
        try:
            r = await client.get(f"{CHROMA_URL}/api/v2/heartbeat")
            if r.status_code != 200:
                raise SystemExit(
                    f"Pre-flight FAIL: ChromaDB heartbeat {CHROMA_URL}/api/v2/heartbeat "
                    f"trả {r.status_code}. Khởi động: docker-compose up -d chroma"
                )
            logger.info("Pre-flight OK: ChromaDB up @ %s", CHROMA_URL)
        except httpx.RequestError as e:
            raise SystemExit(
                f"Pre-flight FAIL: Không kết nối được ChromaDB ({CHROMA_URL}): {e}\n"
                f"Khởi động: docker-compose up -d chroma"
            ) from e

    # Check 3: Hub eval đã seed (DB query qua psycopg, fail-fast 5s timeout)
    dsn = (
        f"host={DB_HOST} port={DB_PORT} dbname={DB_NAME} "
        f"user={DB_USER} password={DB_PASSWORD}"
    )
    try:
        with psycopg.connect(dsn, connect_timeout=5) as conn, conn.cursor() as cur:
            cur.execute("SELECT id FROM hubs WHERE code = %s", (EVAL_HUB_CODE,))
            row = cur.fetchone()
            if not row:
                raise SystemExit(
                    f"Pre-flight FAIL: Hub code='{EVAL_HUB_CODE}' chưa seed.\n"
                    f"Chạy seed trước:\n"
                    f"  psql -h {DB_HOST} -U {DB_USER} -d {DB_NAME} "
                    f"-f eval/scripts/seed_hub.sql"
                )
            logger.info("Pre-flight OK: hub '%s' đã seed (id=%s)", EVAL_HUB_CODE, row[0])
    except psycopg.OperationalError as e:
        raise SystemExit(
            f"Pre-flight FAIL: Không kết nối được Postgres "
            f"({DB_HOST}:{DB_PORT}/{DB_NAME}): {e}\n"
            f"Kiểm tra Postgres đang chạy + credential trong eval/.env."
        ) from e

    logger.info("Pre-flight: tất cả 3 check pass")


# ─── HTTP client với JWT auto-refresh (TTL 15 phút) ───────────────────────
class APIClient:
    """HTTP client gọi backend Go, auto-refresh JWT khi gặp 401.

    JWT access token TTL 15 phút (backend/.env.example:36 JWT_ACCESS_TOKEN_TTL=15m).
    Baseline upload 10 file có thể vượt 15 phút -> phải refresh khi 401.
    """

    def __init__(self, base_url: str, email: str, password: str) -> None:
        self.base_url = base_url
        self.email = email
        self.password = password
        self.access_token: str | None = None
        self.refresh_token: str | None = None
        # Timeout cao (120s) cho upload file lớn + embedding API chậm
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(120.0))

    async def aclose(self) -> None:
        await self._client.aclose()

    async def login(self) -> None:
        """Login admin, lưu access + refresh token."""
        r = await self._client.post(
            f"{self.base_url}/api/auth/login",
            json={"email": self.email, "password": self.password},
        )
        r.raise_for_status()
        data = r.json()["data"]
        self.access_token = data["access_token"]
        self.refresh_token = data["refresh_token"]
        logger.info("Login OK: %s (token TTL ~15m)", self.email)

    async def refresh(self) -> None:
        """Refresh access token. Nếu refresh fail -> re-login."""
        if not self.refresh_token:
            await self.login()
            return
        try:
            r = await self._client.post(
                f"{self.base_url}/api/auth/refresh",
                json={"refresh_token": self.refresh_token},
            )
            r.raise_for_status()
            data = r.json()["data"]
            self.access_token = data["access_token"]
            self.refresh_token = data["refresh_token"]
            logger.info("Refresh token OK")
        except httpx.HTTPStatusError:
            logger.warning("Refresh fail -> re-login")
            await self.login()

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.access_token}"} if self.access_token else {}

    async def _request_with_retry(
        self, method: str, url: str, **kw: Any
    ) -> httpx.Response:
        """Gửi request, nếu 401 -> refresh token rồi retry 1 lần."""
        kw.setdefault("headers", {}).update(self._headers())
        r = await self._client.request(method, url, **kw)
        if r.status_code == 401:
            await self.refresh()
            kw["headers"].update(self._headers())
            r = await self._client.request(method, url, **kw)
        return r

    async def get(self, path: str, **kw: Any) -> dict:
        r = await self._request_with_retry("GET", f"{self.base_url}{path}", **kw)
        r.raise_for_status()
        return r.json()

    async def post_json(self, path: str, body: dict) -> dict:
        r = await self._request_with_retry(
            "POST", f"{self.base_url}{path}", json=body
        )
        r.raise_for_status()
        return r.json()

    async def post_multipart(
        self, path: str, file_path: Path, fields: dict[str, str]
    ) -> dict:
        """Upload multipart: file=<binary> + extra fields (vd hub_id)."""
        with file_path.open("rb") as f:
            files = {
                "file": (file_path.name, f.read(), "application/octet-stream"),
            }
            r = await self._request_with_retry(
                "POST", f"{self.base_url}{path}", files=files, data=fields,
            )
        r.raise_for_status()
        return r.json()


# ─── Helpers ──────────────────────────────────────────────────────────────
async def get_eval_hub_id(api: APIClient) -> str:
    """Lấy hub_id của hub code='eval' qua API list hubs.

    Fallback: nếu API trả format khác (data trực tiếp là list, hoặc
    {data: {hubs: [...]}}), thử cả 2 layout.
    """
    resp = await api.get("/api/hubs")
    raw = resp.get("data", resp)
    hubs = raw.get("hubs", raw.get("items", [])) if isinstance(raw, dict) else raw

    for h in hubs:
        if h.get("code") == EVAL_HUB_CODE:
            return h["id"]
    raise SystemExit(
        f"Hub code='{EVAL_HUB_CODE}' chưa tồn tại qua API. Chạy seed_hub.sql trước:\n"
        f"  psql -f eval/scripts/seed_hub.sql"
    )


async def get_embedder_config(api: APIClient) -> dict:
    """Merge GET /api/rag-config (public) + /api/rag-config/collections (admin).

    REVISION 1 W5: Fail loud (SystemExit) nếu provider rỗng hoặc dim=0.
    Lý do: nếu config invalid -> baseline run vô nghĩa, không thể compare Phase 5.
    """
    rag = await api.get("/api/rag-config")
    if isinstance(rag, dict) and "data" in rag:
        rag = rag["data"]

    collections = await api.get("/api/rag-config/collections")
    if isinstance(collections, dict) and "data" in collections:
        collections = collections["data"]

    config = {
        "embedder_provider": rag.get("embedding_provider", ""),
        "embedder_model": rag.get("embedding_model", ""),
        "embedder_dim": collections.get("current_dimension", 0),
        "chunker": rag.get("chunker", "unknown"),
        "chunk_size": rag.get("chunk_size"),
        "chunk_overlap": rag.get("chunk_overlap"),
    }

    # W5: fail loud nếu provider rỗng / dim=0
    if not config.get("embedder_provider") or config.get("embedder_dim", 0) == 0:
        raise SystemExit(
            f"Embedding config invalid: provider={config.get('embedder_provider')!r}, "
            f"dim={config.get('embedder_dim')}.\n"
            f"Check backend /.env và GET {BACKEND_URL}/api/rag-config/collections — "
            f"collection medinet_eval phải đã được create với dim > 0.\n"
            f"Chạy: GET {BACKEND_URL}/api/rag-config để xem provider hiện tại."
        )
    return config


async def upload_and_wait(
    api: APIClient,
    file_path: Path,
    hub_id: str,
    timeout_sec: int,
    poll_sec: int,
) -> dict:
    """Upload 1 file, poll status đến completed|error|timeout.

    Trả dict chứa: id (doc_id), filename, status, progress, chunk_count, error_message.
    """
    logger.info("Upload %s (size %.1f KB)", file_path.name, file_path.stat().st_size / 1024)
    upload_resp = await api.post_multipart(
        "/api/documents/upload",
        file_path,
        {"hub_id": hub_id},
    )
    doc = upload_resp["data"]
    doc_id = doc["id"]
    logger.info("  -> doc_id=%s status=%s", doc_id, doc["status"])

    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        await asyncio.sleep(poll_sec)
        status_resp = await api.get(f"/api/documents/{doc_id}/status")
        s = status_resp["data"] if isinstance(status_resp, dict) and "data" in status_resp else status_resp
        st = s.get("status", "")
        progress = s.get("progress", 0)
        logger.info("  poll %s: %s %d%%", file_path.name, st, progress)
        if st in ("completed", "error"):
            return {"id": doc_id, "filename": file_path.name, **s}
    return {
        "id": doc_id,
        "filename": file_path.name,
        "status": "timeout",
        "progress": 0,
        "error_message": f"Poll timeout sau {timeout_sec}s",
    }


async def search_query(
    api: APIClient, query: str, hub_id: str, top_k: int
) -> list[dict]:
    """Gọi POST /api/search trả list results.

    Mỗi result có:
      - id: chunk_id (vector ID trong ChromaDB) — KHÔNG phải document_id.
      - category: document name (= filename gốc, từ searcher.go:131) — match field.
      - title, snippet, score, source.
    """
    resp = await api.post_json(
        "/api/search",
        {"query": query, "hub_ids": [hub_id], "top_k": top_k, "min_score": 0.0},
    )
    return resp["data"]["results"]


# ─── Metrics — REVISION 1 B2 (lowercase match) ────────────────────────────
def compute_retrieval_metrics(
    queries: list[dict], per_query_results: list[dict]
) -> dict:
    """Tính top-1/3/5 hit rate + Mean Reciprocal Rank.

    REVISION 1 B2: A hit = result.category (= document name = filename gốc, từ
    backend/internal/rag/searcher.go:131) lowercase compare với expected_doc_id
    lowercase. KHÔNG dùng result.id (= chunk_id, không phải document_id).

    Top-K hit rate: hit nếu BẤT KỲ result nào trong top-K có
    category == expected_doc_id (case-insensitive).

    MRR: trung bình của 1/rank (rank=1 cho hit đầu tiên trong top-K), 0 nếu miss.
    """
    n = len(queries)
    hits_at_1 = hits_at_3 = hits_at_5 = 0
    rr_sum = 0.0
    per_query: list[dict] = []

    for q, r in zip(queries, per_query_results, strict=True):
        expected_filename = q["expected_doc_id"].lower()
        results = r["results"]

        rank: int | None = None
        for idx, res in enumerate(results, 1):
            res_category = (res.get("category") or "").lower()
            if res_category == expected_filename:
                rank = idx
                break

        if rank == 1:
            hits_at_1 += 1
        if rank and rank <= 3:
            hits_at_3 += 1
        if rank and rank <= 5:
            hits_at_5 += 1
        if rank:
            rr_sum += 1.0 / rank

        per_query.append({
            "id": q["id"],
            "query": q["query"],
            "expected_doc_id": q["expected_doc_id"],
            "expected_section": q.get("expected_section", ""),
            "actual_top_5": [
                {
                    "chunk_id": res.get("id"),  # rename rõ: id từ API = chunk_id
                    "category": res.get("category"),  # filename gốc — match field
                    "title": res.get("title"),
                    "score": res.get("score"),
                }
                for res in results[:5]
            ],
            "rank": rank,
        })

    return {
        "top_1_hit_rate": hits_at_1 / n if n else 0.0,
        "top_3_hit_rate": hits_at_3 / n if n else 0.0,
        "top_5_hit_rate": hits_at_5 / n if n else 0.0,
        "mrr": rr_sum / n if n else 0.0,
        "per_query": per_query,
    }


# ─── Heading metrics — REVISION 1 B1: defer Phase 5 ───────────────────────
def annotate_heading_gold_count(
    docs: list[dict], headings_gold: dict[str, list[str]]
) -> list[dict]:
    """Chỉ ghi `headings_gold_count` per doc.

    REVISION 1 B1: KHÔNG ghi `headings_recalled` / `headings_missed` ở Phase 1
    — defer Phase 5 theo REQ EVAL-02. Phase 5 sẽ đọc lại headings.json + chunks
    metadata để compute recall thật.

    heading_recall measured in Phase 5 (REQ EVAL-02).
    """
    for d in docs:
        gold = headings_gold.get(d.get("filename", ""), [])
        d["headings_gold_count"] = len(gold)
    return docs


# ─── Main orchestration ───────────────────────────────────────────────────
async def run_baseline(args: argparse.Namespace) -> int:
    """Toàn bộ pipeline: pre-flight -> login -> upload -> search -> snapshot."""
    # REVISION 1 B3: pre-flight TRƯỚC khi tạo APIClient (giảm side-effect)
    await preflight_check()

    api = APIClient(BACKEND_URL, ADMIN_EMAIL, ADMIN_PASSWORD)
    try:
        await api.login()

        # W5: fail loud bên trong nếu config invalid
        embedder_cfg = await get_embedder_config(api)
        logger.info(
            "Embedder: %s/%s dim=%s",
            embedder_cfg["embedder_provider"],
            embedder_cfg["embedder_model"],
            embedder_cfg["embedder_dim"],
        )

        eval_hub_id = await get_eval_hub_id(api)
        logger.info("eval_hub_id=%s", eval_hub_id)

        # Build danh sách file: 8 sources + 2 scanned (sort theo tên cho deterministic)
        all_files = sorted(SOURCES_DIR.glob("*"))
        all_files += sorted(SCANNED_DIR.glob("*.pdf"))
        if len(all_files) != 10:
            logger.warning("Mong đợi 10 file, có %d", len(all_files))

        # Upload + poll sequential (tránh worker pool quá tải, default 3 worker)
        docs: list[dict] = []
        for fp in all_files:
            try:
                d = await upload_and_wait(
                    api, fp, eval_hub_id, args.upload_timeout, args.poll_interval
                )
            except httpx.HTTPStatusError as e:
                d = {
                    "filename": fp.name,
                    "status": "error",
                    "error_message": (
                        f"HTTP {e.response.status_code}: {e.response.text[:200]}"
                    ),
                }
            docs.append(d)

        # Load queries + headings vàng
        queries = [
            json.loads(line)
            for line in QUERIES_PATH.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        headings_gold = json.loads(HEADINGS_PATH.read_text(encoding="utf-8"))

        # Search 12 queries — match expected_doc_id LOWERCASE với
        # result.category LOWERCASE (REVISION 1 B2)
        per_q: list[dict] = []
        for q in queries:
            results = await search_query(api, q["query"], eval_hub_id, args.top_k)
            per_q.append({"results": results})

        retrieval = compute_retrieval_metrics(queries, per_q)
        docs = annotate_heading_gold_count(docs, headings_gold)

        # Snapshot output: KHÔNG có headings_recalled/headings_missed (B1 defer Phase 5)
        snapshot = {
            "run_id": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "extractor_mode": "native",
            **embedder_cfg,
            "eval_hub_id": eval_hub_id,
            "documents": docs,
            "retrieval": retrieval,
            "queries_count": len(queries),
            "files_count": len(all_files),
            "_note_heading_recall_deferred": (
                "heading_recall measured in Phase 5 per REQ EVAL-02"
            ),
        }

        OUTPUT_PATH.write_text(
            json.dumps(snapshot, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info(
            "Baseline DONE -> %s (top-1=%.3f top-3=%.3f top-5=%.3f mrr=%.3f)",
            OUTPUT_PATH,
            retrieval["top_1_hit_rate"],
            retrieval["top_3_hit_rate"],
            retrieval["top_5_hit_rate"],
            retrieval["mrr"],
        )

        # Phase 1 success criterion 4 — log explicit cho 2 scanned PDF
        scanned_failed = [
            d for d in docs
            if d.get("filename", "").endswith("_scanned.pdf")
            and d.get("status") == "error"
        ]
        if scanned_failed:
            logger.info(
                "Phase 1 SC4 met: %d scanned PDF có error log (gap cho Docling Phase 2)",
                len(scanned_failed),
            )
            # W2: assert error_message chứa "no text extracted"
            for sd in scanned_failed:
                err_text = (sd.get("error_message") or sd.get("error") or "").lower()
                if "no text extracted" in err_text:
                    logger.info(
                        "  W2 OK: %s error_message chứa 'no text extracted'",
                        sd["filename"],
                    )
                elif not err_text:
                    logger.warning(
                        "  W2 bypass: %s status=error nhưng API không trả "
                        "error_message (chỉ verify status=error)",
                        sd["filename"],
                    )
                else:
                    logger.warning(
                        "  W2 partial: %s error: %s",
                        sd["filename"],
                        err_text[:200],
                    )
        else:
            logger.warning(
                "Phase 1 SC4 NOT met: scanned PDF không fail như mong đợi — "
                "kiểm tra extractor backend pdf.go:52"
            )

        return 0
    finally:
        await api.aclose()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Baseline retrieval native (Phase 1 — M1 RAG Quality with Docling)"
    )
    parser.add_argument(
        "--top-k", type=int, default=5,
        help="Số kết quả lấy từ /api/search (default 5)",
    )
    parser.add_argument(
        "--upload-timeout", type=int, default=UPLOAD_TIMEOUT_SEC,
        help=f"Timeout poll status mỗi file (default {UPLOAD_TIMEOUT_SEC}s)",
    )
    parser.add_argument(
        "--poll-interval", type=int, default=POLL_INTERVAL_SEC,
        help=f"Khoảng poll status (default {POLL_INTERVAL_SEC}s)",
    )
    args = parser.parse_args()
    return asyncio.run(run_baseline(args))


if __name__ == "__main__":
    sys.exit(main())
