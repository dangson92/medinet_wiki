"""Đối chiếu contract giữa React frontend và FastAPI ``api/`` mới.

Mục đích (Phase 8 — Frontend E2E Smoke, COMPAT-01): trước khi smoke runtime,
lập bản đồ mọi endpoint mà ``frontend/src/services/api.ts`` gọi, so với router
FastAPI thực tế trong ``api/app/routers/`` + ``api/app/auth/router.py``, rồi
phân loại từng gap thành MATCH / BLOCKER / EXCLUDED / FIX-API / UNCLASSIFIED.

Chạy:
    cd api && python -m scripts.smoke.contract_diff
hoặc:
    python api/scripts/smoke/contract_diff.py   (từ Hub_All/)

Exit code: 0 nếu không có endpoint UNCLASSIFIED, 1 nếu có (để CI phát hiện
endpoint frontend mới chưa được planner phân loại).

Script thuần đọc file (regex tĩnh) — không import app, không thực thi mã từ
api.ts hay router. Chỉ dùng stdlib ``re``, ``pathlib``, ``sys``.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Gốc repo Hub_All: scripts/smoke/contract_diff.py -> smoke -> scripts -> api -> Hub_All
REPO_ROOT = Path(__file__).resolve().parents[3]
API_TS = REPO_ROOT / "frontend" / "src" / "services" / "api.ts"
ROUTERS_DIR = REPO_ROOT / "api" / "app" / "routers"
AUTH_ROUTER = REPO_ROOT / "api" / "app" / "auth" / "router.py"
REPORT_PATH = (
    REPO_ROOT
    / ".planning"
    / "phases"
    / "08-frontend-e2e-smoke"
    / "08-CONTRACT-DIFF.md"
)

# 10 file router trong api/app/routers/ (api_keys, audit_logs, ask, documents,
# hubs, profile, rag_config, search, usage, users) + auth/router.py.
ROUTER_FILES = [
    "api_keys.py",
    "audit_logs.py",
    "ask.py",
    "documents.py",
    "hubs.py",
    "profile.py",
    "rag_config.py",
    "search.py",
    "usage.py",
    "users.py",
]

# Regex trích lời gọi this.request<...>('METHOD', <path>).
# <path> có 2 dạng: chuỗi đơn 'literal' (kết thúc ở dấu '), hoặc template
# `...${qs ? '?' + qs : ''}` (kết thúc ở backtick — bên trong CÓ THỂ chứa dấu '
# nên không thể dùng class [^`'] chung). Hai nhánh xử lý riêng:
_REQUEST_RE = re.compile(
    r"""this\.request<[^>]*>\(\s*'(\w+)',\s*"""
    r"""(?:`([^`]+)`|'([^']+)')""",
    re.VERBOSE,
)
# Regex trích fetch trực tiếp: fetch(`${this.baseURL}/api/...`, { method: 'METHOD' })
_FETCH_RE = re.compile(
    r"""fetch\(\s*`\$\{this\.baseURL\}([^`]+)`\s*,\s*\{\s*method:\s*'(\w+)'""",
    re.VERBOSE,
)
# Regex trích getDocumentFileUrl / getDocumentVersionFileUrl: return `${baseURL}/api/...`
_URL_BUILDER_RE = re.compile(
    r"""return\s+`\$\{this\.baseURL\}([^`]+)`""",
    re.VERBOSE,
)

# Trích prefix + route FastAPI
_PREFIX_RE = re.compile(r"""APIRouter\([^)]*prefix=['"]([^'"]+)['"]""", re.DOTALL)
_ROUTE_RE = re.compile(
    r"""@router\.(get|post|put|delete|patch)\(\s*['"]([^'"]*)['"]""",
)

# Bảng phân loại CỨNG — quyết định planner (08-01-PLAN.md). Executor KHÔNG tự
# suy diễn. Mỗi entry: (matcher_kind, key) -> (status, reason).
#   exact     : path template trùng tuyệt đối
#   prefix    : path bắt đầu bằng key
#   substring : key là chuỗi con của path
_CLASSIFICATION: list[tuple[str, str, str, str]] = [
    (
        "exact",
        "/api/ai/chat",
        "BLOCKER",
        "GeminiAssistant trên golden path Dashboard — FastAPI chưa có endpoint",
    ),
    (
        "prefix",
        "/api/sync/",
        "EXCLUDED",
        "sync queue loai khoi M2 — Phase 5 CONTEXT D-01",
    ),
    (
        "substring",
        "/versions",
        "EXCLUDED",
        "version history defer v4.1 — RAG-V4-03",
    ),
    (
        "substring",
        "/reupload",
        "EXCLUDED",
        "version history defer v4.1 — RAG-V4-03",
    ),
    (
        "substring",
        "/content",
        "EXCLUDED",
        "version history defer v4.1 — RAG-V4-03",
    ),
    (
        "exact",
        "/api/hubs/{id}/test-connection",
        "EXCLUDED",
        "D-06 PROJECT.md — KHONG test-connection",
    ),
    (
        "exact",
        "/api/documents/compose",
        "FIX-API",
        "compose mode DocumentIngestion — can stub api-side",
    ),
    (
        "exact",
        "/api/documents/{id}/file",
        "FIX-API",
        "tai file goc — can stub api-side",
    ),
]


def _normalize_path(path: str) -> str:
    """Chuẩn hoá path template: bỏ ``${...}`` interpolation TRƯỚC (vì nội dung
    interpolation — ví dụ ``${qs ? '?' + qs : ''}`` — có thể chứa ``?`` gây cắt
    nhầm query string), rồi bỏ query string, rồi gộp mọi path param về ``{id}``.

    Path param frontend (``${id}`` ``${docId}``...) và FastAPI (``{document_id}``
    ``{hub_id}``...) đều quy về ``{id}`` để hai bên so khớp được."""
    # Bước 1: bỏ interpolation query-string ``${qs ? '?' + qs : ''}`` — nội dung
    # chứa dấu '?' nên phải xoá HẲN (thay rỗng) trước, tránh cắt nhầm path.
    path = re.sub(r"\$\{[^}]*\?[^}]*\}", "", path)
    # Bước 2: interpolation còn lại là path param (${id} ${docId} ${versionId})
    # -> quy về {id}.
    path = re.sub(r"\$\{[^}]*\}", "{id}", path)
    # Bước 3: bỏ query string literal nếu còn.
    path = path.split("?", 1)[0]
    # Bước 4: path param FastAPI {document_id}/{hub_id}/{user_id}... -> {id}.
    path = re.sub(r"\{[^}]+\}", "{id}", path)
    return path.rstrip("/") or "/"


def extract_frontend_endpoints(api_ts: Path) -> list[tuple[str, str]]:
    """Trích mọi endpoint frontend gọi từ ``api.ts``.

    Trả về list các tuple ``(METHOD, path_template)`` đã sort + dedupe.
    """
    text = api_ts.read_text(encoding="utf-8")
    found: set[tuple[str, str]] = set()

    # _REQUEST_RE có 3 group: method, path-backtick, path-quote. Đúng 1 trong 2
    # group path khớp mỗi lần — lấy group nào khác rỗng.
    for method, path_backtick, path_quote in _REQUEST_RE.findall(text):
        raw_path = path_backtick or path_quote
        found.add((method.upper(), _normalize_path(raw_path)))

    for raw_path, method in _FETCH_RE.findall(text):
        found.add((method.upper(), _normalize_path(raw_path)))

    # getDocumentFileUrl / getDocumentVersionFileUrl: dùng làm <a href> / <img src>
    # — request GET ngầm khi browser tải. Coi như GET.
    for raw_path in _URL_BUILDER_RE.findall(text):
        if raw_path.startswith("/api/"):
            found.add(("GET", _normalize_path(raw_path)))

    return sorted(found)


def _extract_routes_from_file(path: Path) -> list[tuple[str, str]]:
    """Trích route từ một file router: ghép ``prefix`` với path decorator."""
    text = path.read_text(encoding="utf-8")
    prefix_match = _PREFIX_RE.search(text)
    prefix = prefix_match.group(1) if prefix_match else ""
    routes: list[tuple[str, str]] = []
    for method, route_path in _ROUTE_RE.findall(text):
        full = prefix + route_path
        routes.append((method.upper(), _normalize_path(full)))
    return routes


def extract_fastapi_endpoints() -> list[tuple[str, str]]:
    """Trích mọi endpoint FastAPI từ 10 router + auth/router.py.

    Trả về list các tuple ``(METHOD, path)`` đã sort + dedupe.
    """
    found: set[tuple[str, str]] = set()
    for name in ROUTER_FILES:
        found.update(_extract_routes_from_file(ROUTERS_DIR / name))
    found.update(_extract_routes_from_file(AUTH_ROUTER))
    return sorted(found)


def classify_gap(path: str) -> tuple[str, str]:
    """Phân loại một endpoint frontend KHÔNG khớp FastAPI.

    Trả về ``(status, reason)``. Mặc định ``UNCLASSIFIED`` nếu không match
    bảng phân loại cứng — đây là tín hiệu có endpoint mới cần planner xử lý.
    """
    for kind, key, status, reason in _CLASSIFICATION:
        if kind == "exact" and path == key:
            return status, reason
        if kind == "prefix" and path.startswith(key):
            return status, reason
        if kind == "substring" and key in path:
            return status, reason
    return "UNCLASSIFIED", "endpoint frontend moi — chua co nhan phan loai"


def build_diff() -> list[tuple[str, str, str, str]]:
    """So frontend vs FastAPI, trả bảng ``(METHOD, PATH, STATUS, REASON)``."""
    frontend = extract_frontend_endpoints(API_TS)
    fastapi = set(extract_fastapi_endpoints())

    rows: list[tuple[str, str, str, str]] = []
    for method, path in frontend:
        if (method, path) in fastapi:
            rows.append((method, path, "MATCH", "khop router FastAPI"))
        else:
            status, reason = classify_gap(path)
            rows.append((method, path, status, reason))
    return rows


def _render_table(rows: list[tuple[str, str, str, str]]) -> str:
    """Render bảng Markdown 4 cột."""
    lines = [
        "| METHOD | PATH | STATUS | REASON |",
        "|--------|------|--------|--------|",
    ]
    for method, path, status, reason in rows:
        lines.append(f"| {method} | `{path}` | {status} | {reason} |")
    return "\n".join(lines)


def _render_report(rows: list[tuple[str, str, str, str]]) -> str:
    """Render báo cáo Markdown đầy đủ cho 08-CONTRACT-DIFF.md."""
    counts: dict[str, int] = {}
    for _, _, status, _ in rows:
        counts[status] = counts.get(status, 0) + 1

    summary = " · ".join(
        f"{status}={counts.get(status, 0)}"
        for status in ("MATCH", "BLOCKER", "EXCLUDED", "FIX-API", "UNCLASSIFIED")
    )

    return "\n".join(
        [
            "# 08-CONTRACT-DIFF — Bản đồ contract Frontend ↔ FastAPI",
            "",
            "> Sinh tự động bởi `api/scripts/smoke/contract_diff.py` (Plan 08-01).",
            "> Phase 8 verify-only — đối chiếu tĩnh, KHÔNG sửa frontend (D6).",
            "",
            "## Tổng kết phân loại",
            "",
            f"**{summary}**",
            "",
            "- **MATCH** — endpoint frontend gọi, FastAPI có sẵn → smoke pass kỳ vọng.",
            "- **BLOCKER** — gap thật trên golden path → phải fix `api/` (Plan 08-02).",
            "- **EXCLUDED** — feature out-of-scope M2 → lỗi hợp lệ, KHÔNG fix.",
            "- **FIX-API** — gap cần stub api-side → input Plan 08-02.",
            "- **UNCLASSIFIED** — endpoint mới chưa phân loại → planner phải xử lý.",
            "",
            "## Bảng đối chiếu endpoint",
            "",
            _render_table(rows),
            "",
        ]
    )


def main() -> int:
    """Điểm vào: build diff, in stdout, ghi báo cáo Markdown, trả exit code."""
    # Console Windows mặc định cp1252 — ép UTF-8 để in được tiếng Việt có dấu.
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8")

    rows = build_diff()

    # In bảng phẳng ra stdout
    print(_render_table(rows))

    unclassified = [r for r in rows if r[2] == "UNCLASSIFIED"]
    if unclassified:
        print(
            f"\nCANH BAO: {len(unclassified)} endpoint UNCLASSIFIED — "
            "bo sung nhan vao _CLASSIFICATION:",
            file=sys.stderr,
        )
        for method, path, _, _ in unclassified:
            print(f"  - {method} {path}", file=sys.stderr)

    # Ghi báo cáo Markdown
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(_render_report(rows), encoding="utf-8")
    print(f"\nDa ghi bao cao: {REPORT_PATH}", file=sys.stderr)

    return 1 if unclassified else 0


if __name__ == "__main__":
    sys.exit(main())
