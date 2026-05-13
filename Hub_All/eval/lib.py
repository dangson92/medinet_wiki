"""Shared module dùng chung cho mọi script Phase 5 — extract pattern reuse từ baseline.py.

Module library (KHÔNG có `if __name__ == "__main__"`). Cung cấp:

  - APIClient: HTTP client gọi backend Go có auto-refresh JWT (TTL 15 phút).
  - DocResult / QueryResult / RetrievalMetrics: dataclass thống nhất output.
  - preflight(): 3 check bắt buộc (backend Go, ChromaDB, hub seed).
  - get_embedder_config(): merge GET /api/rag-config + /api/rag-config/collections.
  - assert_embedder_match(): hard fail nếu provider/model/dim lệch so với baseline_native.json.
  - upload_dataset(): upload toàn bộ 10 file eval/dataset/ + poll status.
  - evaluate_queries(): chạy 12 query, tính top-1/3/5 hit rate + MRR.

Phase 5 plan kế tiếp (05-02..05) import module này — KHÔNG sửa baseline.py (immutable).

Tham chiếu interface chốt: .planning/phases/05-eval-compare-quality-gate/05-01-PLAN.md.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import psycopg
from dotenv import load_dotenv

# ─── Logging setup (đồng bộ baseline.py) ───────────────────────────────────
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


# ═══════════════════════════════════════════════════════════════════════════
# Dataclass — output schema thống nhất Phase 5
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class DocResult:
    """Kết quả ingestion 1 file qua API.

    extractor_used: đọc từ documents.extractor_used (CFG-06, Phase 4 plan-05).
    "" nếu document fail trước khi ghi (vd timeout poll status).
    """

    doc_id: str
    filename: str
    status: str  # "completed" | "error" | "timeout"
    chunks_count: int
    avg_chunk_tokens: float
    extractor_used: str  # "docling" | "native" | ""
    error: str | None = None


@dataclass
class QueryResult:
    """Kết quả 1 query trên /api/search.

    top_rank: rank đầu tiên (1-indexed) match expected_doc_id, None nếu miss.
    actual_top_5: list filename top-5 raw để debug.
    """

    query_id: str
    query: str
    expected_doc_id: str
    top_rank: int | None
    actual_top_5: list[str] = field(default_factory=list)


@dataclass
class RetrievalMetrics:
    """Tổng kết metric retrieval qua N query."""

    top_1_hit_rate: float
    top_3_hit_rate: float
    top_5_hit_rate: float
    mrr: float
    per_query: list[QueryResult] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════════════════
# Pre-flight (REVISION 1 B3 từ baseline.py — 3 check fail loud)
# ═══════════════════════════════════════════════════════════════════════════


def preflight(
    backend_url: str = BACKEND_URL,
    db_dsn: str | None = None,
    chroma_url: str = CHROMA_URL,
    hub_code: str = EVAL_HUB_CODE,
) -> None:
    """3 check bắt buộc trước khi chạy bất kỳ script eval nào.

    1. Backend Go up: GET /api/health (fallback /api/rag-config nếu /health 404).
    2. ChromaDB up: GET /api/v2/heartbeat.
    3. Hub `eval` đã seed: SELECT id FROM hubs WHERE code='eval'.

    Fail loud → SystemExit với hint cụ thể.

    Wrapper sync — gọi async preflight bên trong asyncio.run.
    """
    asyncio.run(_preflight_async(backend_url, db_dsn, chroma_url, hub_code))


async def _preflight_async(
    backend_url: str,
    db_dsn: str | None,
    chroma_url: str,
    hub_code: str,
) -> None:
    """Async impl của preflight — dùng httpx.AsyncClient."""
    async with httpx.AsyncClient(timeout=10) as client:
        # Check 1: Backend Go health
        try:
            r = await client.get(f"{backend_url}/api/health")
            if r.status_code == 404:
                r = await client.get(f"{backend_url}/api/rag-config")
            if r.status_code != 200:
                raise SystemExit(
                    f"Pre-flight FAIL: Backend Go health check {backend_url} "
                    f"trả {r.status_code}. Khởi động backend trước:\n"
                    f"  cd backend && go run ./cmd/server"
                )
            logger.info("Pre-flight OK: Backend Go up @ %s", backend_url)
        except httpx.RequestError as e:
            raise SystemExit(
                f"Pre-flight FAIL: Không kết nối được backend ({backend_url}): {e}\n"
                f"Khởi động backend: cd backend && go run ./cmd/server"
            ) from e

        # Check 2: ChromaDB heartbeat
        try:
            r = await client.get(f"{chroma_url}/api/v2/heartbeat")
            if r.status_code != 200:
                raise SystemExit(
                    f"Pre-flight FAIL: ChromaDB heartbeat {chroma_url}/api/v2/heartbeat "
                    f"trả {r.status_code}. Khởi động: docker-compose up -d chroma"
                )
            logger.info("Pre-flight OK: ChromaDB up @ %s", chroma_url)
        except httpx.RequestError as e:
            raise SystemExit(
                f"Pre-flight FAIL: Không kết nối được ChromaDB ({chroma_url}): {e}\n"
                f"Khởi động: docker-compose up -d chroma"
            ) from e

    # Check 3: Hub seed
    dsn = db_dsn or (
        f"host={DB_HOST} port={DB_PORT} dbname={DB_NAME} "
        f"user={DB_USER} password={DB_PASSWORD}"
    )
    try:
        with psycopg.connect(dsn, connect_timeout=5) as conn, conn.cursor() as cur:
            cur.execute("SELECT id FROM hubs WHERE code = %s", (hub_code,))
            row = cur.fetchone()
            if not row:
                raise SystemExit(
                    f"Pre-flight FAIL: Hub code='{hub_code}' chưa seed.\n"
                    f"Chạy seed trước:\n"
                    f"  psql -h {DB_HOST} -U {DB_USER} -d {DB_NAME} "
                    f"-f eval/scripts/seed_hub.sql"
                )
            logger.info("Pre-flight OK: hub '%s' đã seed (id=%s)", hub_code, row[0])
    except psycopg.OperationalError as e:
        raise SystemExit(
            f"Pre-flight FAIL: Không kết nối được Postgres "
            f"({DB_HOST}:{DB_PORT}/{DB_NAME}): {e}\n"
            f"Kiểm tra Postgres đang chạy + credential trong eval/.env."
        ) from e

    logger.info("Pre-flight: tất cả 3 check pass")


# ═══════════════════════════════════════════════════════════════════════════
# APIClient — sync wrapper quanh async httpx (đơn giản hoá cho script eval)
# ═══════════════════════════════════════════════════════════════════════════


class APIClient:
    """HTTP client gọi backend Go, auto-refresh JWT khi gặp 401.

    Toàn bộ method là sync (asyncio.run nội bộ) — script eval Phase 5 chạy
    sequential, không cần concurrency. Giảm complexity so với baseline.py async.

    JWT access token TTL 15 phút (backend/.env JWT_ACCESS_TOKEN_TTL=15m).
    """

    def __init__(self, base_url: str, email: str, password: str) -> None:
        self.base_url = base_url
        self.email = email
        self.password = password
        self.access_token: str | None = None
        self.refresh_token: str | None = None
        # Timeout cao 300s cho upload file lớn + Docling extract chậm
        self._client = httpx.Client(timeout=httpx.Timeout(300.0))

    def close(self) -> None:
        self._client.close()

    # ─── Auth ──────────────────────────────────────────────────────────────

    def login(self) -> None:
        """Login admin, lưu access + refresh token."""
        r = self._client.post(
            f"{self.base_url}/api/auth/login",
            json={"email": self.email, "password": self.password},
        )
        r.raise_for_status()
        data = r.json()["data"]
        self.access_token = data["access_token"]
        self.refresh_token = data["refresh_token"]
        logger.info("Login OK: %s (token TTL ~15m)", self.email)

    def refresh_if_expired(self) -> None:
        """Refresh access token. Nếu refresh fail → re-login."""
        if not self.refresh_token:
            self.login()
            return
        try:
            r = self._client.post(
                f"{self.base_url}/api/auth/refresh",
                json={"refresh_token": self.refresh_token},
            )
            r.raise_for_status()
            data = r.json()["data"]
            self.access_token = data["access_token"]
            self.refresh_token = data["refresh_token"]
            logger.info("Refresh token OK")
        except httpx.HTTPStatusError:
            logger.warning("Refresh fail → re-login")
            self.login()

    def _headers(self) -> dict[str, str]:
        return (
            {"Authorization": f"Bearer {self.access_token}"} if self.access_token else {}
        )

    def _request_with_retry(
        self, method: str, url: str, **kw: Any
    ) -> httpx.Response:
        """Gửi request, nếu 401 → refresh token rồi retry 1 lần."""
        kw.setdefault("headers", {}).update(self._headers())
        r = self._client.request(method, url, **kw)
        if r.status_code == 401:
            self.refresh_if_expired()
            kw["headers"].update(self._headers())
            r = self._client.request(method, url, **kw)
        return r

    # ─── Generic helpers ───────────────────────────────────────────────────

    def _get(self, path: str, **kw: Any) -> dict:
        r = self._request_with_retry("GET", f"{self.base_url}{path}", **kw)
        r.raise_for_status()
        return r.json()

    def _post_json(self, path: str, body: dict) -> dict:
        r = self._request_with_retry(
            "POST", f"{self.base_url}{path}", json=body
        )
        r.raise_for_status()
        return r.json()

    def _put_json(self, path: str, body: dict) -> dict:
        r = self._request_with_retry(
            "PUT", f"{self.base_url}{path}", json=body
        )
        r.raise_for_status()
        return r.json()

    def _post_multipart(
        self, path: str, file_path: Path, fields: dict[str, str]
    ) -> dict:
        with file_path.open("rb") as f:
            files = {
                "file": (file_path.name, f.read(), "application/octet-stream"),
            }
            r = self._request_with_retry(
                "POST", f"{self.base_url}{path}", files=files, data=fields,
            )
        r.raise_for_status()
        return r.json()

    # ─── Domain methods ────────────────────────────────────────────────────

    def get_hub_id(self, code: str) -> str:
        """Lấy hub_id qua API list hubs. Fallback nhiều layout response."""
        resp = self._get("/api/hubs")
        raw = resp.get("data", resp)
        hubs = raw.get("hubs", raw.get("items", [])) if isinstance(raw, dict) else raw
        for h in hubs:
            if h.get("code") == code:
                return h["id"]
        raise SystemExit(
            f"Hub code='{code}' chưa tồn tại qua API. Chạy seed trước:\n"
            f"  psql -f eval/scripts/seed_hub.sql"
        )

    def upload_and_wait(
        self,
        hub_id: str,
        file_path: str,
        timeout: int = 300,
        poll_interval: int = 2,
    ) -> dict:
        """Upload 1 file, poll /api/documents/{id}/status đến completed|error.

        Trả dict đầy đủ document object từ GET /api/documents/{id}, bao gồm:
          - id, filename, status, progress
          - chunks_count, avg_chunk_tokens (nếu có)
          - extractor_used (CFG-06, Phase 4 plan-05)
          - error_message (nếu error)
        """
        fp = Path(file_path)
        logger.info(
            "Upload %s (size %.1f KB)",
            fp.name,
            fp.stat().st_size / 1024,
        )
        upload_resp = self._post_multipart(
            "/api/documents/upload",
            fp,
            {"hub_id": hub_id},
        )
        doc = upload_resp["data"]
        doc_id = doc["id"]
        logger.info("  → doc_id=%s status=%s", doc_id, doc["status"])

        deadline = time.time() + timeout
        last_status: dict[str, Any] = {}
        while time.time() < deadline:
            time.sleep(poll_interval)
            status_resp = self._get(f"/api/documents/{doc_id}/status")
            s = (
                status_resp["data"]
                if isinstance(status_resp, dict) and "data" in status_resp
                else status_resp
            )
            last_status = s
            st = s.get("status", "")
            progress = s.get("progress", 0)
            logger.info("  poll %s: %s %d%%", fp.name, st, progress)
            if st in ("completed", "error"):
                # Lấy thêm document detail để có extractor_used + chunks_count
                detail_resp = self._get(f"/api/documents/{doc_id}")
                detail = (
                    detail_resp["data"]
                    if isinstance(detail_resp, dict) and "data" in detail_resp
                    else detail_resp
                )
                return {"id": doc_id, "filename": fp.name, **s, **detail}
        return {
            "id": doc_id,
            "filename": fp.name,
            "status": "timeout",
            "progress": 0,
            "error_message": f"Poll timeout sau {timeout}s",
            **last_status,
        }

    def search(
        self,
        hub_id: str,
        query: str,
        top_k: int = 5,
        min_score: float = 0.0,
    ) -> list[dict]:
        """Gọi POST /api/search trả list results (mỗi item có category=filename gốc)."""
        resp = self._post_json(
            "/api/search",
            {
                "query": query,
                "hub_ids": [hub_id],
                "top_k": top_k,
                "min_score": min_score,
            },
        )
        return resp["data"]["results"]

    def get_rag_config(self) -> dict:
        """GET /api/rag-config — public endpoint, KHÔNG cần admin token."""
        resp = self._get("/api/rag-config")
        return resp["data"] if isinstance(resp, dict) and "data" in resp else resp

    def get_rag_collections(self) -> dict:
        """GET /api/rag-config/collections — admin endpoint."""
        resp = self._get("/api/rag-config/collections")
        return resp["data"] if isinstance(resp, dict) and "data" in resp else resp

    def put_rag_config(self, payload: dict) -> dict:
        """PUT /api/rag-config — admin token bắt buộc.

        Phổ biến: {"extractor_mode": "docling" | "native" | "auto"} (CFG-03).
        """
        resp = self._put_json("/api/rag-config", payload)
        logger.info("PUT /api/rag-config %s → OK", payload)
        return resp

    def update_rag_config(self, payload: dict) -> dict:
        """Alias của put_rag_config (đồng bộ tên với task description Plan 05-01)."""
        return self.put_rag_config(payload)

    def reindex(self, doc_id: str, extractor: str) -> dict:
        """POST /api/documents/{id}/reindex?extractor=... (CFG-07, Phase 4 plan-05).

        extractor ∈ {"docling", "native", "auto"}.
        Trả response 202 (admin).
        """
        url = f"/api/documents/{doc_id}/reindex?extractor={extractor}"
        r = self._request_with_retry("POST", f"{self.base_url}{url}")
        r.raise_for_status()
        logger.info("Reindex doc=%s extractor=%s → 202", doc_id, extractor)
        return r.json()


# ═══════════════════════════════════════════════════════════════════════════
# Helpers — embedder config + lock verify
# ═══════════════════════════════════════════════════════════════════════════


def get_embedder_config(client: APIClient) -> dict:
    """Merge GET /api/rag-config + /api/rag-config/collections → {provider, model, dim, ...}.

    Fail loud (SystemExit) nếu provider rỗng / dim=0 (REVISION 1 W5 từ baseline.py).
    """
    rag = client.get_rag_config()
    collections = client.get_rag_collections()

    config = {
        "embedder_provider": rag.get("embedding_provider", ""),
        "embedder_model": rag.get("embedding_model", ""),
        "embedder_dim": collections.get("current_dimension", 0),
        "chunker": rag.get("chunker", "unknown"),
        "chunk_size": rag.get("chunk_size"),
        "chunk_overlap": rag.get("chunk_overlap"),
    }

    if not config.get("embedder_provider") or config.get("embedder_dim", 0) == 0:
        raise SystemExit(
            f"Embedding config invalid: provider={config.get('embedder_provider')!r}, "
            f"dim={config.get('embedder_dim')}.\n"
            f"Check backend /.env và GET /api/rag-config/collections — "
            f"collection medinet_eval phải đã được create với dim > 0."
        )
    return config


def assert_embedder_match(current: dict, baseline_native_path: str) -> None:
    """Hard fail nếu provider/model/dim hiện tại lệch so với baseline_native.json.

    Lý do: gate fairness tuyệt đối — Docling vs Native phải compare trên CÙNG
    embedding để delta retrieval phản ánh đúng chất lượng extraction.

    Raises SystemExit(2) nếu lệch.
    """
    baseline_path = Path(baseline_native_path)
    if not baseline_path.is_absolute():
        baseline_path = REPO_ROOT / baseline_native_path
    if not baseline_path.exists():
        raise SystemExit(
            f"EMBEDDER LOCK FAIL: baseline_native.json không tồn tại tại {baseline_path}.\n"
            f"Chạy Phase 1 baseline trước: python eval/baseline.py"
        )

    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))

    mismatches: list[str] = []
    for field_name in ("embedder_provider", "embedder_model", "embedder_dim"):
        cur_val = current.get(field_name)
        base_val = baseline.get(field_name)
        if cur_val != base_val:
            mismatches.append(
                f"  {field_name}: current={cur_val!r} ≠ baseline={base_val!r}"
            )

    if mismatches:
        raise SystemExit(
            "EMBEDDER LOCK FAIL: cấu hình embedding hiện tại lệch so với "
            f"baseline_native.json — gate fairness Phase 5 không thể tiếp tục.\n"
            + "\n".join(mismatches)
            + f"\nKhôi phục backend/.env về cấu hình baseline rồi chạy lại."
        )

    logger.info(
        "Embedder lock OK: %s/%s dim=%s khớp baseline_native.json",
        current.get("embedder_provider"),
        current.get("embedder_model"),
        current.get("embedder_dim"),
    )


# ═══════════════════════════════════════════════════════════════════════════
# Dataset upload + retrieval evaluation
# ═══════════════════════════════════════════════════════════════════════════


def upload_dataset(
    client: APIClient,
    hub_id: str,
    dataset_dir: str,
    timeout: int = 300,
) -> list[DocResult]:
    """Glob dataset_dir/sources/*.{docx,pdf} + dataset_dir/scanned/*.pdf, upload tuần tự.

    Trả list[DocResult]. extractor_used đọc từ documents.extractor_used (CFG-06).
    """
    base = Path(dataset_dir)
    if not base.is_absolute():
        base = REPO_ROOT / dataset_dir

    sources_dir = base / "sources"
    scanned_dir = base / "scanned"

    all_files: list[Path] = []
    if sources_dir.exists():
        all_files.extend(sorted(sources_dir.glob("*")))
    if scanned_dir.exists():
        all_files.extend(sorted(scanned_dir.glob("*.pdf")))

    if not all_files:
        raise SystemExit(
            f"upload_dataset: không tìm thấy file nào trong {sources_dir} hoặc {scanned_dir}"
        )

    logger.info(
        "Upload dataset: %d file (sources=%d, scanned=%d)",
        len(all_files),
        len(list(sources_dir.glob("*"))) if sources_dir.exists() else 0,
        len(list(scanned_dir.glob("*.pdf"))) if scanned_dir.exists() else 0,
    )

    results: list[DocResult] = []
    for idx, fp in enumerate(all_files, 1):
        logger.info("[%d/%d] Processing %s", idx, len(all_files), fp.name)
        try:
            doc = client.upload_and_wait(hub_id, str(fp), timeout=timeout)
            results.append(
                DocResult(
                    doc_id=doc.get("id", ""),
                    filename=fp.name,
                    status=doc.get("status", "unknown"),
                    chunks_count=int(doc.get("chunks_count", 0) or 0),
                    avg_chunk_tokens=float(doc.get("avg_chunk_tokens", 0) or 0),
                    extractor_used=doc.get("extractor_used") or "",
                    error=doc.get("error_message"),
                )
            )
        except httpx.HTTPStatusError as e:
            results.append(
                DocResult(
                    doc_id="",
                    filename=fp.name,
                    status="error",
                    chunks_count=0,
                    avg_chunk_tokens=0.0,
                    extractor_used="",
                    error=f"HTTP {e.response.status_code}: {e.response.text[:200]}",
                )
            )
    return results


def evaluate_queries(
    client: APIClient,
    hub_id: str,
    queries_path: str,
    top_k: int = 5,
) -> RetrievalMetrics:
    """Load queries.jsonl, chạy mỗi query qua /api/search, tính top-1/3/5 + MRR.

    Match logic: result.category (= filename gốc, từ searcher.go:131) lowercase
    so với expected_doc_id lowercase (REVISION 1 B2 từ baseline.py).
    """
    qp = Path(queries_path)
    if not qp.is_absolute():
        qp = REPO_ROOT / queries_path

    queries = [
        json.loads(line)
        for line in qp.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    n = len(queries)
    if n == 0:
        raise SystemExit(f"evaluate_queries: queries file rỗng → {qp}")

    hits_at_1 = hits_at_3 = hits_at_5 = 0
    rr_sum = 0.0
    per_query: list[QueryResult] = []

    for q in queries:
        results = client.search(hub_id, q["query"], top_k=top_k, min_score=0.0)
        expected = q["expected_doc_id"].lower()

        rank: int | None = None
        for idx, res in enumerate(results, 1):
            res_category = (res.get("category") or "").lower()
            if res_category == expected:
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

        per_query.append(
            QueryResult(
                query_id=q["id"],
                query=q["query"],
                expected_doc_id=q["expected_doc_id"],
                top_rank=rank,
                actual_top_5=[
                    res.get("category", "") for res in results[:5]
                ],
            )
        )

    return RetrievalMetrics(
        top_1_hit_rate=hits_at_1 / n,
        top_3_hit_rate=hits_at_3 / n,
        top_5_hit_rate=hits_at_5 / n,
        mrr=rr_sum / n,
        per_query=per_query,
    )


# ═══════════════════════════════════════════════════════════════════════════
# Snapshot helper
# ═══════════════════════════════════════════════════════════════════════════


def make_snapshot(
    extractor_mode: str,
    embedder: dict,
    eval_hub_id: str,
    docs: list[DocResult],
    metrics: RetrievalMetrics,
    queries_count: int,
    extra: dict | None = None,
) -> dict:
    """Build snapshot dict identical schema với baseline_native.json.

    Thêm field extractor_used per-document (Phase 5 mới so với Phase 1).
    """
    snapshot = {
        "run_id": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "extractor_mode": extractor_mode,
        **embedder,
        "eval_hub_id": eval_hub_id,
        "documents": [
            {
                "id": d.doc_id,
                "filename": d.filename,
                "status": d.status,
                "chunks_count": d.chunks_count,
                "avg_chunk_tokens": d.avg_chunk_tokens,
                "extractor_used": d.extractor_used,
                "error_message": d.error,
            }
            for d in docs
        ],
        "retrieval": {
            "top_1_hit_rate": metrics.top_1_hit_rate,
            "top_3_hit_rate": metrics.top_3_hit_rate,
            "top_5_hit_rate": metrics.top_5_hit_rate,
            "mrr": metrics.mrr,
            "per_query": [
                {
                    "id": q.query_id,
                    "query": q.query,
                    "expected_doc_id": q.expected_doc_id,
                    "actual_top_5": q.actual_top_5,
                    "rank": q.top_rank,
                }
                for q in metrics.per_query
            ],
        },
        "queries_count": queries_count,
        "files_count": len(docs),
    }
    if extra:
        snapshot.update(extra)
    return snapshot
