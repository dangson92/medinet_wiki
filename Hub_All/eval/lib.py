"""Eval framework lib — APIClient + preflight + upload+poll (Phase 9 EVAL-02).

Pattern source: M1 baseline.py (commit 0af44f0:Hub_All/eval/baseline.py).
M2 adapt:
- D-02 POST /api/search body {query, hub_ids, top_k} (KHÔNG GET ?q=)
- D-10 result.title = filename (KHÔNG category)
- R4 415 tolerant cho scanned PDF (failed_unsupported KHÔNG raise)
- Phase 4 race fix tolerant: poll timeout ≥30s/file (Plan 04-08 retry 0.5/1.0/1.5s)
"""
from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

import httpx
import psycopg
from dotenv import load_dotenv

load_dotenv()


@dataclass(slots=True)
class EvalSettings:
    """Settings runtime của eval framework — đọc từ env (eval/.env)."""

    backend_url: str = field(
        default_factory=lambda: os.getenv("BACKEND_URL", "http://localhost:8180")
    )
    admin_email: str = field(
        default_factory=lambda: os.getenv("ADMIN_EMAIL", "admin@medinet.vn")
    )
    admin_password: str = field(
        default_factory=lambda: os.getenv("ADMIN_PASSWORD", "")
    )
    db_host: str = field(default_factory=lambda: os.getenv("DB_HOST", "localhost"))
    db_port: int = field(default_factory=lambda: int(os.getenv("DB_PORT", "5432")))
    db_name: str = field(
        default_factory=lambda: os.getenv("DB_NAME", "medinet_central")
    )
    db_user: str = field(default_factory=lambda: os.getenv("DB_USER", "medinet"))
    db_password: str = field(default_factory=lambda: os.getenv("DB_PASSWORD", ""))
    eval_hub_code: str = field(
        default_factory=lambda: os.getenv("EVAL_HUB_CODE", "eval")
    )
    upload_timeout_sec: int = field(
        default_factory=lambda: int(os.getenv("EVAL_UPLOAD_TIMEOUT_SEC", "60"))
    )
    poll_interval_sec: float = field(
        default_factory=lambda: float(os.getenv("EVAL_POLL_INTERVAL_SEC", "1.0"))
    )


def _dsn(s: EvalSettings) -> str:
    """Build Postgres DSN string từ EvalSettings."""
    return (
        f"host={s.db_host} port={s.db_port} dbname={s.db_name} "
        f"user={s.db_user} password={s.db_password}"
    )


class APIClient:
    """httpx async client với JWT auto-refresh on 401.

    M2 endpoint adaptations:
    - POST /api/auth/login (Phase 3 — JWT RS256 TTL 15min)
    - POST /api/auth/refresh (Phase 3 — refresh rotation)
    - POST /api/documents/upload (Phase 4) — multipart
    - GET /api/documents/:id (Phase 4) — poll status
    - POST /api/search (Phase 6 D-02) — body {query, hub_ids, top_k}
    """

    def __init__(self, base_url: str, email: str, password: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.email = email
        self.password = password
        self.access_token: str | None = None
        self.refresh_token: str | None = None
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(120.0))

    async def __aenter__(self) -> APIClient:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self._client.aclose()

    async def aclose(self) -> None:
        """Đóng httpx client (nếu không dùng context manager)."""
        await self._client.aclose()

    async def login(self) -> None:
        """POST /api/auth/login → set access + refresh token."""
        r = await self._client.post(
            f"{self.base_url}/api/auth/login",
            json={"email": self.email, "password": self.password},
        )
        if r.status_code != 200:
            raise SystemExit(f"Login fail {r.status_code}: {r.text[:200]}")
        data = r.json()["data"]
        self.access_token = data["access_token"]
        self.refresh_token = data["refresh_token"]

    async def refresh(self) -> None:
        """POST /api/auth/refresh → rotate access + refresh.

        Refresh token expired → fallback re-login (admin credential có sẵn).
        """
        if not self.refresh_token:
            await self.login()
            return
        r = await self._client.post(
            f"{self.base_url}/api/auth/refresh",
            json={"refresh_token": self.refresh_token},
        )
        if r.status_code != 200:
            # Refresh token expired hoặc rotated → fallback re-login
            await self.login()
            return
        data = r.json()["data"]
        self.access_token = data["access_token"]
        self.refresh_token = data["refresh_token"]

    async def _request_with_retry(
        self, method: str, url: str, **kw: object
    ) -> httpx.Response:
        """Add Bearer header, gặp 401 → refresh → retry 1 lần."""
        headers = dict(kw.pop("headers", {}) or {})  # type: ignore[arg-type]
        headers["Authorization"] = f"Bearer {self.access_token}"
        r = await self._client.request(method, url, headers=headers, **kw)  # type: ignore[arg-type]
        if r.status_code == 401:
            await self.refresh()
            headers["Authorization"] = f"Bearer {self.access_token}"
            r = await self._client.request(method, url, headers=headers, **kw)  # type: ignore[arg-type]
        return r

    async def upload_document(
        self, file_path: Path, hub_id: str
    ) -> tuple[int, dict]:
        """POST /api/documents/upload (multipart).

        Trả (status_code, body_dict). Caller xử lý 202 (OK) vs 415
        (failed_unsupported R4 mitigation cho scanned PDF).
        """
        with file_path.open("rb") as f:
            files = {
                "file": (
                    file_path.name,
                    f.read(),
                    "application/octet-stream",
                )
            }
            r = await self._request_with_retry(
                "POST",
                f"{self.base_url}/api/documents/upload",
                files=files,
                data={"hub_id": hub_id},
            )
        try:
            body = r.json()
        except ValueError:
            body = {"raw": r.text}
        return r.status_code, body

    async def get_document(self, doc_id: str) -> dict:
        """GET /api/documents/:id — poll status."""
        r = await self._request_with_retry(
            "GET", f"{self.base_url}/api/documents/{doc_id}"
        )
        r.raise_for_status()
        return r.json()["data"]

    async def search(
        self, query: str, hub_id: str, top_k: int = 10
    ) -> tuple[list[dict], float]:
        """POST /api/search body {query, hub_ids, top_k} (D-02).

        Trả (results, latency_ms). KHÔNG dùng GET ?q= (Go cũ).
        result.title = filename (D-10) — caller dùng cho retrieval match.
        """
        t0 = time.perf_counter()
        r = await self._request_with_retry(
            "POST",
            f"{self.base_url}/api/search",
            json={"query": query, "hub_ids": [hub_id], "top_k": top_k},
        )
        t1 = time.perf_counter()
        r.raise_for_status()
        results = r.json()["data"]["results"]
        return results, (t1 - t0) * 1000.0


async def preflight_check(settings: EvalSettings) -> None:
    """Verify backend + Postgres + eval_hub seed — fail loud nếu thiếu.

    Raises SystemExit kèm hint khắc phục cụ thể:
    - /healthz ≠ 200 → hint docker compose up / make dev
    - /readyz ≠ 200 → hint check uvicorn logs cocoindex_init_failed_fail_fast
    - Postgres connect fail → hint check DB env
    - Hub code chưa seed → hint chạy psql -f seed_hub.sql
    """
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            r = await client.get(f"{settings.backend_url}/healthz")
            if r.status_code != 200:
                raise SystemExit(
                    f"Pre-flight FAIL: backend healthz {settings.backend_url} trả "
                    f"{r.status_code}.\n"
                    f"Khởi động: cd Hub_All && docker compose up -d "
                    f"hoặc (cd api && make dev)"
                )
            r = await client.get(f"{settings.backend_url}/readyz")
            if r.status_code != 200:
                raise SystemExit(
                    "Pre-flight FAIL: backend KHÔNG ready (cocoindex flow + DB pool).\n"
                    "Check uvicorn logs cho 'cocoindex_init_failed_fail_fast' ERROR."
                )
        except httpx.RequestError as e:
            raise SystemExit(
                f"Pre-flight FAIL: không kết nối backend {settings.backend_url}: {e}"
            ) from e

    try:
        with psycopg.connect(_dsn(settings), connect_timeout=5) as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM hubs WHERE code = %s", (settings.eval_hub_code,)
            )
            row = cur.fetchone()
            if not row:
                raise SystemExit(
                    f"Pre-flight FAIL: hub code='{settings.eval_hub_code}' chưa seed.\n"
                    f"Chạy: psql -h {settings.db_host} -U {settings.db_user} "
                    f"-d {settings.db_name} -f Hub_All/eval/scripts/seed_hub.sql"
                )
    except psycopg.OperationalError as e:
        raise SystemExit(
            f"Pre-flight FAIL: không kết nối Postgres "
            f"({settings.db_host}:{settings.db_port}/{settings.db_name}): {e}"
        ) from e


async def get_eval_hub_id(settings: EvalSettings) -> str:
    """SELECT id FROM hubs WHERE code=eval_hub_code → return UUID str.

    Raises SystemExit nếu hub chưa seed (preflight đã catch nhưng caller
    có thể skip preflight cho test).
    """
    with psycopg.connect(_dsn(settings)) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM hubs WHERE code = %s", (settings.eval_hub_code,)
        )
        row = cur.fetchone()
        if not row:
            raise SystemExit(
                f"eval_hub code='{settings.eval_hub_code}' không tồn tại"
            )
        return str(row[0])


async def upload_and_wait(
    api: APIClient,
    file_path: Path,
    hub_id: str,
    timeout_sec: int = 60,
    poll_sec: float = 1.0,
) -> dict:
    """Upload file + poll status cho đến terminal state hoặc timeout.

    R4 mitigation: scanned PDF 415 KHÔNG raise — trả status='failed_unsupported'.
    Phase 4 race fix tolerant: poll timeout default 60s/file (worst-case
    Plan 04-08 trigger_cocoindex_update retry 0.1 + 0.5 + 1.0 + 1.5 = ~3.6s
    overhead trên top extract/chunk/embed thật sự).

    Returns dict:
      {id, filename, status: pending|processing|completed|failed|
                              failed_unsupported|timeout,
       chunk_count, error_message?}
    """
    status_code, body = await api.upload_document(file_path, hub_id)

    # R4 mitigation — scanned PDF expected 415
    if status_code == 415:
        err = body.get("error", {}) or {}
        return {
            "filename": file_path.name,
            "status": "failed_unsupported",
            "error_message": err.get("message", "unsupported format"),
            "id": None,
            "chunk_count": 0,
        }
    if status_code not in (200, 201, 202):
        return {
            "filename": file_path.name,
            "status": "failed",
            "error_message": f"Upload HTTP {status_code}: {body}",
            "id": None,
            "chunk_count": 0,
        }

    doc = body.get("data", {})
    doc_id = doc.get("id")
    if not doc_id:
        return {
            "filename": file_path.name,
            "status": "failed",
            "error_message": f"Upload OK nhưng thiếu document id: {body}",
            "id": None,
            "chunk_count": 0,
        }
    last_status = doc.get("status", "pending")

    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        await asyncio.sleep(poll_sec)
        try:
            s = await api.get_document(doc_id)
        except httpx.HTTPStatusError as e:
            return {
                "id": doc_id,
                "filename": file_path.name,
                "status": "failed",
                "error_message": f"Poll HTTP error: {e}",
                "chunk_count": 0,
            }
        last_status = s.get("status", "unknown")
        if last_status in ("completed", "failed", "failed_unsupported"):
            return {
                "id": doc_id,
                "filename": file_path.name,
                "status": last_status,
                "chunk_count": s.get("chunk_count", 0),
                "error_message": s.get("error_message"),
            }
    return {
        "id": doc_id,
        "filename": file_path.name,
        "status": "timeout",
        "error_message": (
            f"Poll timeout {timeout_sec}s — last status: {last_status}"
        ),
        "chunk_count": 0,
    }
