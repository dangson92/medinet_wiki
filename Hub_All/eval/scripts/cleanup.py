"""Reset eval state trước mỗi baseline run (Phase 1 / M1 RAG Quality).

Chạy:
    python eval/scripts/cleanup.py [--keep-uploads] [--keep-audit]
    python -m eval.scripts.cleanup [--keep-uploads] [--keep-audit]

5 bước thực thi:
    1. Lấy `eval_hub_id` từ row `code='eval'` (fail loud nếu chưa seed).
    2. Kiểm tra không có document `pending`/`processing` (race với worker pool Go).
    3. DELETE FROM documents WHERE hub_id=<eval_id> → cascade xóa document_chunks.
    4. DELETE ChromaDB collection `medinet_eval` qua v2 API:
       - GET /collections để lookup UUID của collection theo `name`.
       - DELETE /collections/<uuid> nếu tồn tại.
       - POST /collections với `get_or_create=true` để re-create ngay (không cần restart backend Go).
    5. shutil.rmtree backend/uploads/eval/ — guard 3 lớp chống xóa nhầm
       (skip nếu --keep-uploads).
    6. (Optional) DELETE FROM audit_logs WHERE hub_id=<eval_id> (skip nếu --keep-audit).

Exit codes:
    0  — thành công.
    2  — hub `eval` chưa seed (chạy seed_hub.sql trước).
    3  — còn document đang pending/processing (chờ worker drain).
    4  — lỗi network ChromaDB DELETE.
    5  — lỗi ChromaDB CREATE collection.
    99 — guard rmtree fail (EVAL_HUB_CODE rỗng/dangerous, target không phải subdir, hoặc path không chứa "eval").

Output cuối cùng (JSON 1 dòng) phục vụ CI parse:
    {"deleted_documents": N, "deleted_chunks": null, "chroma_dropped": bool, "uploads_cleaned": bool}
"""
from __future__ import annotations

import argparse
import contextlib
import json
import logging
import os
import shutil
import sys
from pathlib import Path

import httpx
import psycopg
from dotenv import load_dotenv

# Ép UTF-8 cho stdout/stderr — Windows console mặc định cp1252 không in được
# tiếng Việt có dấu (argparse --help / docstring sẽ raise UnicodeEncodeError).
for _stream in (sys.stdout, sys.stderr):
    _reconfigure = getattr(_stream, "reconfigure", None)
    if _reconfigure is not None:
        # stream không hỗ trợ reconfigure (vd đã đóng, không phải TextIO) → bỏ qua
        with contextlib.suppress(OSError, ValueError):
            _reconfigure(encoding="utf-8")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# Repo root = thư mục chứa folder `eval/` (parent cách 2 cấp từ scripts/cleanup.py)
REPO_ROOT = Path(__file__).resolve().parents[2]

# Ưu tiên load eval/.env, fallback backend/.env (theo prompt task)
load_dotenv(REPO_ROOT / "eval" / ".env")
load_dotenv(REPO_ROOT / "backend" / ".env", override=False)

# Config từ env (default khớp backend/.env.example)
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "medinet_central")
DB_USER = os.getenv("DB_USER", "medinet")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
CHROMA_URL = os.getenv("CHROMA_URL", "http://localhost:8000").rstrip("/")
CHROMA_TOKEN = os.getenv("CHROMA_TOKEN", "")
EVAL_HUB_CODE = os.getenv("EVAL_HUB_CODE", "eval")
EVAL_COLLECTION = os.getenv("EVAL_COLLECTION", "medinet_eval")

# ChromaDB v2 base — khớp `backend/internal/vectorstore/chromadb.go:15`
V2_BASE = "/api/v2/tenants/default_tenant/databases/default_database"

# Guard 3 lớp chống xóa nhầm thư mục (REVISION 1 — issue I1):
# Tập giá trị "dangerous" cho EVAL_HUB_CODE — nếu env value rơi vào đây thì
# `backend/uploads/<value>` có thể trỏ về thư mục root hoặc parent.
DANGEROUS_HUB_CODES = {"", ".", "/", "*", "..", "~"}


def chroma_headers() -> dict[str, str]:
    """Build header gọi ChromaDB v2 API. Chỉ set Authorization khi có token."""
    headers = {"Content-Type": "application/json"}
    if CHROMA_TOKEN:
        headers["Authorization"] = f"Bearer {CHROMA_TOKEN}"
    return headers


def get_eval_hub_id(conn: psycopg.Connection) -> str:
    """Trả về UUID của hub `eval`. Fail loud (exit 2) nếu chưa seed."""
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM hubs WHERE code = %s", (EVAL_HUB_CODE,))
        row = cur.fetchone()
        if not row:
            logger.error(
                "Hub code='%s' chưa tồn tại. Chạy seed trước:\n"
                "  psql -h %s -U %s -d %s -f eval/scripts/seed_hub.sql",
                EVAL_HUB_CODE,
                DB_HOST,
                DB_USER,
                DB_NAME,
            )
            sys.exit(2)
        return str(row[0])


def assert_no_active_jobs(conn: psycopg.Connection, hub_id: str) -> None:
    """Race-safety: không xóa khi worker còn process job pending/processing."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM documents "
            "WHERE hub_id = %s AND status IN ('pending','processing')",
            (hub_id,),
        )
        row = cur.fetchone()
        count = int(row[0]) if row else 0
        if count > 0:
            logger.error(
                "Có %d document đang pending/processing — chờ worker drain xong rồi chạy lại.",
                count,
            )
            sys.exit(3)


def cleanup_documents(conn: psycopg.Connection, hub_id: str) -> int:
    """DELETE documents — cascade xóa document_chunks qua FK ON DELETE CASCADE."""
    with conn.cursor() as cur:
        cur.execute("DELETE FROM documents WHERE hub_id = %s", (hub_id,))
        deleted = cur.rowcount
        conn.commit()
        logger.info("Đã xóa %d documents (chunks tự cascade qua FK)", deleted)
        return deleted


def cleanup_audit_logs(conn: psycopg.Connection, hub_id: str) -> int:
    """DELETE audit_logs — partition theo timestamp tự apply trên all partitions.

    Bảng `audit_logs` có thể KHÔNG tồn tại trong môi trường eval mới (migration
    004_audit chưa chạy). Bắt lỗi UndefinedTable và bỏ qua cho idempotent.
    """
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM audit_logs WHERE hub_id = %s", (hub_id,))
            deleted = cur.rowcount
            conn.commit()
            logger.info("Đã xóa %d audit_logs", deleted)
            return deleted
    except psycopg.errors.UndefinedTable:
        conn.rollback()
        logger.info("Bảng audit_logs chưa tồn tại — skip cleanup audit.")
        return 0
    except psycopg.errors.UndefinedColumn:
        conn.rollback()
        logger.info("Bảng audit_logs không có cột hub_id — skip cleanup audit.")
        return 0


def lookup_chroma_collection_id(client: httpx.Client) -> str | None:
    """GET /collections, scan list để tìm collection theo `name = EVAL_COLLECTION`.

    ChromaDB v2 API delete bằng UUID, không phải bằng name → phải lookup trước.
    Trả về `None` nếu collection không tồn tại (không phải lỗi).
    """
    list_url = f"{CHROMA_URL}{V2_BASE}/collections"
    try:
        r = client.get(list_url)
    except httpx.RequestError as e:
        logger.error("ChromaDB GET /collections lỗi network: %s", e)
        sys.exit(4)
    if r.status_code == 404:
        logger.warning("ChromaDB GET /collections → 404 (server chưa init tenant?)")
        return None
    if r.status_code != 200:
        logger.error("ChromaDB GET /collections → %d %s", r.status_code, r.text[:200])
        sys.exit(4)
    try:
        items = r.json()
    except ValueError:
        logger.error("ChromaDB GET /collections trả body không phải JSON")
        sys.exit(4)
    if not isinstance(items, list):
        logger.warning("ChromaDB GET /collections trả non-list: %s", type(items).__name__)
        return None
    for item in items:
        if isinstance(item, dict) and item.get("name") == EVAL_COLLECTION:
            cid = item.get("id")
            if cid:
                return str(cid)
    return None


def cleanup_chroma_collection() -> bool:
    """DELETE collection `medinet_eval` qua ChromaDB v2 API (lookup UUID trước).

    Sau DELETE, gọi POST get_or_create=true để re-create ngay — backend Go chỉ
    tự CreateCollection lúc khởi động, runtime cleanup cần tự re-create để
    upload tiếp theo không 404.

    Return: True nếu đã DELETE (collection trước đó tồn tại), False nếu collection
    chưa có (nothing to drop).
    """
    headers = chroma_headers()
    dropped = False
    with httpx.Client(timeout=30, headers=headers) as client:
        # Bước 1: lookup UUID collection theo name
        cid = lookup_chroma_collection_id(client)

        # Bước 2: DELETE bằng UUID (nếu tồn tại)
        if cid:
            del_url = f"{CHROMA_URL}{V2_BASE}/collections/{cid}"
            try:
                r = client.delete(del_url)
            except httpx.RequestError as e:
                logger.error("ChromaDB DELETE %s lỗi network: %s", cid, e)
                sys.exit(4)
            if r.status_code in (200, 204, 404):
                logger.info(
                    "ChromaDB DELETE collection %s (id=%s) → %d",
                    EVAL_COLLECTION,
                    cid,
                    r.status_code,
                )
                dropped = True
            else:
                logger.error(
                    "ChromaDB DELETE %s thất bại: %d %s",
                    cid,
                    r.status_code,
                    r.text[:200],
                )
                sys.exit(4)
        else:
            logger.info(
                "ChromaDB collection %s chưa tồn tại — skip DELETE",
                EVAL_COLLECTION,
            )

        # Bước 3: re-create ngay qua POST get_or_create
        create_url = f"{CHROMA_URL}{V2_BASE}/collections"
        body = {
            "name": EVAL_COLLECTION,
            "metadata": {"hnsw:space": "cosine"},
            "get_or_create": True,
        }
        try:
            r = client.post(create_url, json=body)
        except httpx.RequestError as e:
            logger.error("ChromaDB POST /collections lỗi network: %s", e)
            sys.exit(5)
        if r.status_code not in (200, 201):
            logger.error(
                "ChromaDB CREATE %s thất bại: %d %s",
                EVAL_COLLECTION,
                r.status_code,
                r.text[:200],
            )
            sys.exit(5)
        logger.info("ChromaDB CREATE collection %s → %d", EVAL_COLLECTION, r.status_code)
    return dropped


def cleanup_uploads_dir() -> bool:
    """Xóa `backend/uploads/<EVAL_HUB_CODE>/` (file local).

    REVISION 1 (I1): Guard 3 lớp chống xóa nhầm:
        Layer 1: EVAL_HUB_CODE không được rỗng / "." / "/" / "*" / ".." / "~".
        Layer 2: target tồn tại + là directory thật (không phải symlink/file).
        Layer 3: path string phải chứa "eval" — sanity check cuối.

    Return: True nếu đã rmtree, False nếu thư mục không tồn tại (skip).
    Fail loud (exit 99) nếu bất kỳ guard nào fail.
    """
    # Layer 1: env value sanity
    if not EVAL_HUB_CODE or EVAL_HUB_CODE in DANGEROUS_HUB_CODES:
        logger.error(
            "Refusing rmtree: EVAL_HUB_CODE='%s' rỗng/dangerous "
            "— KHÔNG xóa thư mục root backend/uploads/.",
            EVAL_HUB_CODE,
        )
        sys.exit(99)

    uploads_root = REPO_ROOT / "backend" / "uploads"
    target = uploads_root / EVAL_HUB_CODE

    # Layer 2: target tồn tại + là dir thật
    if not target.exists():
        logger.info("Thư mục %s không tồn tại — skip rmtree", target)
        return False
    if not target.is_dir():
        logger.error("Refusing rmtree: %s không phải là directory", target)
        sys.exit(99)

    # Layer 3: sanity — path string phải chứa "eval"
    if "eval" not in str(target).lower():
        logger.error("Refusing rmtree: path %s không chứa 'eval' — sanity fail", target)
        sys.exit(99)

    shutil.rmtree(target)
    logger.info("Đã xóa thư mục %s", target)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Reset eval state trước baseline run.",
    )
    parser.add_argument(
        "--keep-uploads",
        action="store_true",
        help="Giữ file local backend/uploads/eval/",
    )
    parser.add_argument(
        "--keep-audit",
        action="store_true",
        help="Giữ rows trong audit_logs",
    )
    args = parser.parse_args()

    dsn = (
        f"host={DB_HOST} port={DB_PORT} dbname={DB_NAME} "
        f"user={DB_USER} password={DB_PASSWORD}"
    )

    deleted_documents = 0
    with psycopg.connect(dsn) as conn:
        hub_id = get_eval_hub_id(conn)
        logger.info("Eval hub_id = %s", hub_id)
        assert_no_active_jobs(conn, hub_id)
        deleted_documents = cleanup_documents(conn, hub_id)
        if not args.keep_audit:
            cleanup_audit_logs(conn, hub_id)

    chroma_dropped = cleanup_chroma_collection()
    uploads_cleaned = False
    if not args.keep_uploads:
        uploads_cleaned = cleanup_uploads_dir()

    logger.info("Cleanup hoàn tất.")

    # Output structured 1 dòng JSON (cho CI/baseline.py parse).
    summary = {
        "deleted_documents": deleted_documents,
        "deleted_chunks": None,  # cascade qua FK — không count được trực tiếp
        "chroma_dropped": chroma_dropped,
        "uploads_cleaned": uploads_cleaned,
    }
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
