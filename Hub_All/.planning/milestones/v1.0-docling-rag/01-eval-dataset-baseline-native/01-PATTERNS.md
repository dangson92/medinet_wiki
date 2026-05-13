# Phase 1: Eval Dataset & Baseline Native — Pattern Map

**Mapped:** 2026-04-28
**Phase scope:** Tạo MỚI thư mục Python `eval/` ở root repo (không nằm trong `backend/`). Toàn bộ artifact mới là Python script + dataset + SQL seed; KHÔNG sửa code Go hiện hữu.
**Files mới phân tích:** 8 (1 SQL, 4 Python script, 1 pyproject, 1 baseline.py, 1 README/DATASET.md)
**Analogs Go tham khảo:** 7 file backend làm "contract reference" cho script Python gọi vào.

---

## File Classification

| File mới | Vai trò | Data Flow | Closest Analog | Match Quality |
|----------|---------|-----------|----------------|---------------|
| `eval/scripts/seed_hub.sql` | migration / seed SQL | CRUD (INSERT) | `backend/scripts/seed.sql:18-23` | exact (cùng pattern INSERT INTO hubs ... ON CONFLICT) |
| `eval/scripts/build_scanned.py` | utility (Python) | file-I/O batch transform | không có analog Python | no analog — dùng convention chuẩn (PEP 8 + ruff) |
| `eval/scripts/extract_headings.py` | utility (Python) | file-I/O transform | `backend/internal/rag/extractor/docx.go:46-95` (port logic) | role-match (khác ngôn ngữ, cùng thuật toán parse `pStyle` + `outlineLvl`) |
| `eval/scripts/cleanup.py` | utility (Python) | CRUD (DELETE) + HTTP | `backend/internal/service/document_service.go:367-401` (Delete flow) | role-match (Python gọi `psycopg`/`httpx` thay vì pgx + ChromaDB Go client) |
| `eval/baseline.py` | script chính (Python) | request-response + batch upload | `frontend/src/services/api.ts:23-49, 127-141` (HTTP client + multipart) | role-match (Python httpx thay vì fetch) |
| `eval/dataset/queries.jsonl` | data | static reference | không có | n/a — file dữ liệu |
| `eval/dataset/headings.json` | data | static reference | không có | n/a — file dữ liệu |
| `eval/pyproject.toml` | config | static | không có | no analog — dùng PEP 621 chuẩn |

---

## 1. API Endpoints script Python sẽ gọi

### `POST /api/documents/upload` (multipart, JWT bắt buộc, role admin)

**Handler:** `backend/internal/handler/document_handler.go:42-74`
**Service:** `backend/internal/service/document_service.go:74-181`
**Route đăng ký:** `backend/internal/router/router.go:474` — `docsAdmin.POST("/upload", docHandler.Upload)` (group đã apply `JWTAuth` + `RequireRole("admin")` ở dòng 463 + 472).

**Request multipart fields:**
- `file` (binary, required) — `backend/internal/handler/document_handler.go:55`
- `hub_id` (string UUID, required) — `backend/internal/handler/document_handler.go:49-53`

**Response (HTTP 202 Accepted):**
- Schema chuẩn `APIResponse` (`backend/internal/pkg/response/response.go:9-14`):
```json
{
  "success": true,
  "data": {
    "id": "<uuid>",
    "name": "<filename>",
    "file_type": "pdf|docx|...",
    "file_size": 12345,
    "hub_id": "<uuid>",
    "status": "pending",
    "progress": 0,
    "chunk_count": 0,
    "uploaded_by": "<uuid>",
    "uploaded_at": "2026-04-28T..."
  }
}
```
- Code Go ghi `response.Accepted(c, doc)` ở `document_handler.go:73`.
- File extension cho phép: `pdf, docx, txt, md, xlsx, pptx, jpg, png, csv, html` (`document_service.go:24-35`).
- Max file size mặc định 50MB (`document_service.go:57`, override qua env).

**Lưu ý quan trọng cho `baseline.py`:** Upload trả 202 ngay, **status = "pending"**. Phải poll `GET /api/documents/{id}/status` cho đến khi `status ∈ {completed, error}` (`document_handler.go:153-171`). Trả về JSON `{ "status": "...", "progress": 0..100 }`.

### `POST /api/search` (single-hub, JWT bắt buộc)

**Handler:** `backend/internal/handler/search_handler.go:44-76`
**Route:** `backend/internal/router/router.go:484` — không cần admin role.

**Request body** (`backend/internal/model/search.go:3-9`):
```json
{
  "query": "<câu hỏi tiếng Việt>",
  "hub_ids": ["<eval_hub_uuid>"],
  "top_k": 5,
  "min_score": 0.0
}
```
- Khi `hub_ids` có giá trị, handler dùng `hub_ids[0]` (`search_handler.go:59-61`).

**Response** (`backend/internal/model/search.go:33-38`):
```json
{
  "success": true,
  "data": {
    "results": [
      {"id": "...", "hub_id": "...", "title": "...", "snippet": "...", "score": 0.87, "raw_similarity": 0.83, "source": "..."}
    ],
    "total_hubs_searched": 1,
    "query_time_ms": 234,
    "cache_hit": false
  }
}
```

### `GET /api/rag-config` (JWT KHÔNG bắt buộc — public, chỉ mask key)

**Handler inline:** `backend/internal/router/router.go:77-104` — KHÔNG có middleware auth.

**Response:**
```json
{
  "chunker": "Semantic Chunker (AI-powered)",
  "chunk_size": 1000,
  "chunk_overlap": 200,
  "embedding_model": "text-embedding-3-small",
  "embedding_provider": "openai",
  "batch_size": 100,
  "gemini_key_mask": "AIza****abcd",
  "openai_key_mask": "sk-1****wxyz",
  "gemini_key_saved": true,
  "openai_key_saved": true,
  "llm_provider": "gemini",
  "gemini_llm_model": "gemini-2.0-flash-lite"
}
```

**Lưu ý:** `embedding_dim` KHÔNG có trong response trực tiếp. Để lấy dimension thật, phải gọi `GET /api/rag-config/collections` (`router.go:293-350`) — endpoint này TRẢ về `current_dimension` (`router.go:309-311`) **NHƯNG cần JWT + role admin** (`router.go:293`).

→ `baseline.py` phải dùng JWT admin để lấy dimension. Snapshot field `embedder_dim` có thể gán bằng `current_dimension` từ endpoint collections.

---

## 2. DB Schema liên quan

### Bảng `hubs` (`backend/internal/database/migrations/001_bootstrap.up.sql:7-23`)

```sql
CREATE TABLE IF NOT EXISTS hubs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(100) NOT NULL,
    code            VARCHAR(50) UNIQUE NOT NULL,
    subdomain       VARCHAR(100) UNIQUE NOT NULL,   -- ⚠ NOT NULL + UNIQUE
    description     TEXT,
    db_host, db_port, db_name, db_user, db_password_enc, ...,
    chroma_collection VARCHAR(100) NOT NULL,
    status          VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'inactive')),
    created_at, updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

**⚠ Constraint `subdomain UNIQUE NOT NULL`** — `seed_hub.sql` PHẢI cung cấp `subdomain` (vd `eval.medinet.vn`).
**⚠ Cột `is_active` KHÔNG tồn tại** — CONTEXT.md viết `is_active=false` là sai; thực tế là `status='inactive'`.

**Pattern seed hiện tại** (`backend/scripts/seed.sql:18-23`):
```sql
INSERT INTO hubs (name, code, subdomain, chroma_collection, description) VALUES
    ('Tâm Đạo Y Quán', 'tamdao', 'tamdao.medinet.vn', 'medinet_tamdao', 'Hub y học cổ truyền Tâm Đạo Y Quán'),
    ...
ON CONFLICT (code) DO NOTHING;
```

**`seed_hub.sql` đề xuất** (sửa lại CONTEXT):
```sql
INSERT INTO hubs (name, code, subdomain, chroma_collection, description, status)
VALUES (
  'Eval Sandbox (M1 RAG Quality)',
  'eval',
  'eval.medinet.vn',
  'medinet_eval',
  'Sandbox cho eval dataset M1',
  'active'
)
ON CONFLICT (code) DO NOTHING;
```

### Bảng `documents` (`001_bootstrap.up.sql:88-104`)

- FK: `hub_id REFERENCES hubs(id)` (NOT NULL).
- `file_type` CHECK constraint giới hạn: `pdf, docx, txt, md, xlsx, pptx, jpg, png, csv, html`.
- `status` CHECK: `pending, processing, completed, error`.

### Bảng `document_chunks` (`001_bootstrap.up.sql:110-120`)

- FK: `document_id REFERENCES documents(id) ON DELETE CASCADE` → cleanup chỉ cần xóa `documents`, chunks tự cascade.
- Cột `chroma_id VARCHAR(100)` — link sang ChromaDB vector ID.
- Cột `metadata JSONB DEFAULT '{}'`.

### Bảng `audit_logs` (`backend/internal/database/migrations/004_audit.up.sql:6-22`)

- PARTITIONED BY RANGE (timestamp) — partition theo tháng (`audit_logs_2026_04`, `_05`, ...).
- Cleanup audit log của eval run: dùng `DELETE FROM audit_logs WHERE hub_id = <eval_hub_id>` (Postgres tự apply trên partitions).

### `cleanup.py` flow đề xuất (cascade đúng)

```python
# 1. Lấy eval_hub_id từ code='eval'
# 2. DELETE FROM documents WHERE hub_id = <eval_hub_id>;  -- cascade xóa document_chunks
# 3. ChromaDB: DELETE /api/v2/.../collections/medinet_eval (xem mục 3)
# 4. Redis FLUSHDB? KHÔNG — chỉ xóa key prefix `rag:cache:*` (xem cache.go nếu cần)
# 5. Audit logs: DELETE FROM audit_logs WHERE hub_id = <eval_hub_id>; -- optional, giữ để debug
```

---

## 3. ChromaDB client — Create / Delete Collection

**File:** `backend/internal/vectorstore/chromadb.go`

**Base URL pattern (v2 API):** `backend/internal/vectorstore/chromadb.go:15`
```go
const v2Base = "/api/v2/tenants/default_tenant/databases/default_database"
```

**Create collection** (`chromadb.go:72-88`):
```go
body := map[string]interface{}{
    "name": name,
    "metadata": map[string]interface{}{"hnsw:space": "cosine"},
    "get_or_create": true,
}
// POST /api/v2/tenants/default_tenant/databases/default_database/collections
```

**Delete collection** (`chromadb.go:90-93`):
```go
// DELETE /api/v2/tenants/default_tenant/databases/default_database/collections/<name>
```

**Auth header:** `Authorization: Bearer <CHROMA_TOKEN>` (chỉ set khi token != ""), `Content-Type: application/json` (`chromadb.go:54-57`).

**Auto-recreate sau delete:** Backend tự gọi `CreateCollection` lúc khởi động cho mọi hub `active` (`backend/cmd/server/main.go:211-225`):
```go
for _, h := range allHubs {
    if h.Status != "active" { continue }
    col := h.ChromaCollection
    if col == "" { col = "medinet_" + h.Code }
    chromaDB.CreateCollection(context.Background(), col)
}
```

→ `cleanup.py` sau khi DELETE collection chỉ cần restart backend HOẶC gọi 1 lần upload (collection auto-create vì backend chỉ ensure lúc startup) → **đề xuất: cleanup.py tự gọi `POST /collections` để re-create ngay sau DELETE** thay vì phụ thuộc backend restart.

**Pattern Python (httpx) tương đương:**
```python
import httpx

CHROMA_URL = os.getenv("CHROMA_URL", "http://localhost:8000")
CHROMA_TOKEN = os.getenv("CHROMA_TOKEN", "")
V2_BASE = "/api/v2/tenants/default_tenant/databases/default_database"

headers = {"Content-Type": "application/json"}
if CHROMA_TOKEN:
    headers["Authorization"] = f"Bearer {CHROMA_TOKEN}"

async with httpx.AsyncClient(timeout=30) as client:
    # Delete
    await client.delete(f"{CHROMA_URL}{V2_BASE}/collections/medinet_eval", headers=headers)
    # Re-create
    await client.post(
        f"{CHROMA_URL}{V2_BASE}/collections",
        json={"name": "medinet_eval", "metadata": {"hnsw:space": "cosine"}, "get_or_create": True},
        headers=headers,
    )
```

---

## 4. Pipeline ingestion async — cleanup script cần xóa gì

**File:** `backend/internal/worker/manager.go`

**Worker pool flow** (`worker/manager.go:101-183`):
1. `processJob` cập nhật `documents.status = 'processing'` (`manager.go:111`).
2. Gọi `pipeline.ProcessWithChunks(...)` (`manager.go:134-142`).
3. Insert chunks vào DB qua `docRepo.BatchInsertChunks` (`manager.go:168`).
4. Cập nhật `documents.status = 'completed'` + `chunk_count` (`manager.go:177`).
5. Khi lỗi: `documents.status = 'error' + error_message` (`manager.go:146-148`).

**Worker pool size:** mặc định 3 worker, channel buffer = `workers * 10` = 30 jobs (`manager.go:38, 41`).

**Hệ quả cho `cleanup.py`:**
- KHÔNG cần xóa file local trên disk — `document_service.go:399-401` xóa `dirPath = filepath.Dir(doc.FilePath)` qua `os.RemoveAll` khi DELETE document. **Nhưng baseline.py dùng cleanup.py xóa qua DB direct → file local sẽ bị bỏ lại**. Đề xuất: cleanup.py thêm bước `shutil.rmtree(uploads_dir / 'eval')` để dọn `backend/uploads/eval/<doc_uuid>/`.
- KHÔNG cần đợi worker drain — DELETE FROM documents khi worker đang process sẽ gây race; **đề xuất:** chạy cleanup KHI backend dừng (hoặc đảm bảo không có job pending). Tốt nhất là cleanup.py kiểm tra `SELECT COUNT(*) FROM documents WHERE hub_id=<eval> AND status IN ('pending','processing')` = 0 trước khi xóa.

**Upload service flow** (`backend/internal/service/document_service.go:74-181`):
- Lưu file local: `backend/uploads/<hub_code>/<doc_uuid>/<filename>` (`document_service.go:119-126`).
- Lưu doc record với `status='pending'` (`document_service.go:141-153`).
- Enqueue job tới worker pool (`document_service.go:166-177`).

→ `baseline.py` upload sequential từng file (10 file), poll status mỗi 2s, timeout 5 phút/file. Resume bằng cách check trước: `GET /api/documents?hub_id=<eval>&file_type=...` rồi skip nếu đã `completed`.

---

## 5. Cấu hình env liên quan

**File:** `backend/.env.example`

| Env | Default | Mục đích cho Phase 1 |
|-----|---------|-----------------------|
| `APP_PORT` | `8180` (`backend/.env.example:3`) | URL gọi API: `http://localhost:8180/api/...` |
| `DB_HOST/PORT/NAME/USER/PASSWORD` | `localhost:5432/medinet_central` (`backend/.env.example:8-15`) | `seed_hub.sql` + `cleanup.py` connect Postgres |
| `REDIS_URL` | `redis://localhost:6379/0` (`backend/.env.example:21`) | `cleanup.py` flush key cache `rag:*` (nếu enable cache cleanup) |
| `CHROMA_URL` | `http://localhost:8000` (`backend/.env.example:28`) | `cleanup.py` gọi DELETE/POST collection |
| `CHROMA_TOKEN` | rỗng (`backend/.env.example:29`) | dev mode không cần token |

**Embedding env** (KHÔNG có trong `.env.example` — config qua DB settings):
- `RAG_EMBEDDING_PROVIDER`, `RAG_EMBEDDING_MODEL`, `RAG_CHUNK_SIZE`, `RAG_CHUNK_OVERLAP`, `RAG_BATCH_SIZE` được lưu ở bảng `settings` qua `settingsRepo.Get/Set` (`backend/cmd/server/main.go:138-158`).
- `OPENAI_API_KEY`, `GEMINI_API_KEY` cũng đọc từ DB settings (mã hóa AES — `main.go:128-136`).

**Hệ quả cho `baseline.py`:** Đọc `.env` để lấy `APP_PORT`, `DB_*`, `CHROMA_URL`. Provider/model embedding lấy qua `GET /api/rag-config` runtime — **KHÔNG đọc từ env**.

**`eval/.env.example` đề xuất** (cho script Python, separate từ backend):
```bash
BACKEND_URL=http://localhost:8180
ADMIN_EMAIL=admin@medinet.vn
ADMIN_PASSWORD=Admin@123
DB_HOST=localhost
DB_PORT=5432
DB_NAME=medinet_central
DB_USER=medinet
DB_PASSWORD=change_me_in_production
CHROMA_URL=http://localhost:8000
CHROMA_TOKEN=
EVAL_HUB_CODE=eval
EVAL_COLLECTION=medinet_eval
```

---

## 6. Code style Python — không có analog trong repo

**Không có file Python nào trong repo hiện tại** (xác nhận qua `Glob('**/*.py')` = empty). Đây là Python codebase **đầu tiên** — phải tự đặt convention.

**Đề xuất convention chuẩn (tham khảo Python community + ROADMAP nói Phase 2 sẽ thêm `docling-pipeline/` Python sidecar — cần convention nhất quán giữa hai thư mục):**

| Aspect | Convention | Lý do |
|--------|-----------|-------|
| Python version | `>= 3.11` | ROADMAP Phase 2 yêu cầu 3.11+ cho Docling |
| Formatter | `ruff format` (replace black) | All-in-one nhanh hơn black + isort |
| Linter | `ruff check` với rule set: `E, W, F, I, N, UP, B, SIM, RUF` | Cover style + bugbear + simplification |
| Type checker | `mypy --strict` (optional Phase 1, mandatory Phase 2) | |
| File naming | snake_case: `build_scanned.py`, `extract_headings.py` | PEP 8 |
| Function/var | snake_case: `upload_document`, `eval_hub_id` | PEP 8 |
| Class | PascalCase: `BaselineRunner`, `EvalConfig` | PEP 8 |
| Constant | UPPER_SNAKE_CASE: `BACKEND_URL`, `CHROMA_V2_BASE` | PEP 8 |
| Imports order | stdlib → third-party → local (cách nhau dòng trống), `ruff` tự sort | giống quy ước Go ở `CONVENTIONS.md` mục Backend |
| Docstring | Google style cho function ≥ 5 dòng | Đọc dễ + sphinx-friendly |
| Comment | **Tiếng Việt** cho business logic, English cho technical detail (theo `CLAUDE.md` global rule) | |
| Logging | `logging.getLogger(__name__)` + structured (extra dict), level INFO mặc định | Tương đương `slog` Go |
| Error handling | `try/except` cụ thể class, KHÔNG bắt `Exception` trần | giống Go pattern wrap error |
| HTTP client | `httpx` (async-ready), KHÔNG dùng `requests` | Tương lai dễ migrate sang async |
| DB driver | `psycopg[binary] >= 3.1` (psycopg3, không psycopg2) | Modern, thread-safe, async support |
| Test | `pytest` + `pytest-asyncio` | Default Python eco-system |

**`pyproject.toml` skeleton:**
```toml
[project]
name = "medinet-eval"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "httpx>=0.27",
    "psycopg[binary]>=3.1",
    "python-docx>=1.1",
    "pdf2image>=1.17",
    "img2pdf>=0.5",
    "Pillow>=10.0",
    "python-dotenv>=1.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "pytest-asyncio>=0.23", "ruff>=0.5", "mypy>=1.10"]

[tool.ruff]
line-length = 100
target-version = "py311"
[tool.ruff.lint]
select = ["E", "W", "F", "I", "N", "UP", "B", "SIM", "RUF"]
```

---

## 7. Heading detection trong DOCX — port logic Go sang Python

**Source pattern Go:** `backend/internal/rag/extractor/docx.go:46-95`

**Thuật toán hiện tại** (Go):
1. Mở DOCX như zip → đọc `word/styles.xml`.
2. Parse XML element `<w:style w:styleId="...">`, lưu `currentStyleID` (`docx.go:67-74`).
3. Trong style đó, tìm `<w:outlineLvl w:val="N"/>` → `headingLevel = N + 1` (0-based → 1-based) (`docx.go:75-83`).
4. **Fallback hard-coded:** map style ID `"Heading1".."Heading6"` → level 1..6 nếu chưa có outlineLvl (`docx.go:88-93`).
5. Trong `parseDocxStructured` (`docx.go:97-265`): với mỗi paragraph, đọc `<w:pStyle w:val="...">` (`docx.go:195-200`), lookup style → nếu `headingLevel > 0 && <= 6`, output Markdown heading `## Title` (`docx.go:124-129`).

**Port sang Python với `python-docx`:**

`python-docx` không expose `outlineLvl` trực tiếp qua API cao cấp — phải đọc raw XML. Pattern đề xuất:

```python
# eval/scripts/extract_headings.py
"""Port logic từ backend/internal/rag/extractor/docx.go:46-95.

Đọc DOCX styles, map styleId → heading level qua outlineLvl + fallback Heading1..6.
Sau đó duyệt body paragraphs, lookup pStyle để build heading path tree.
"""
from __future__ import annotations

import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

NS_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def parse_docx_styles(docx_path: Path) -> dict[str, int]:
    """Trả về map {styleId: headingLevel}. headingLevel=0 nghĩa không phải heading."""
    styles: dict[str, int] = {}
    with zipfile.ZipFile(docx_path) as z:
        with z.open("word/styles.xml") as f:
            tree = ET.parse(f)
        for style_el in tree.findall(f"{NS_W}style"):
            style_id = style_el.get(f"{NS_W}styleId")
            if not style_id:
                continue
            outline = style_el.find(f".//{NS_W}outlineLvl")
            if outline is not None:
                val = outline.get(f"{NS_W}val")
                if val is not None and val.isdigit():
                    # Go code: headingLevel = N + 1 (0-based → 1-based)
                    styles[style_id] = int(val) + 1
    # Fallback hard-coded (giống docx.go:88-93)
    for i in range(1, 7):
        styles.setdefault(f"Heading{i}", i)
    return styles


def extract_heading_paths(docx_path: Path) -> list[str]:
    """Duyệt body paragraphs, build heading path từ root.

    Ví dụ output: ["Định vị thương hiệu", "Định vị thương hiệu > Thông điệp cốt lõi"].
    Path nối bằng " > " để khớp schema queries.jsonl (CONTEXT mục A).
    """
    styles = parse_docx_styles(docx_path)
    paths: list[str] = []
    stack: list[str] = []  # stack[i] = title của heading level i+1

    with zipfile.ZipFile(docx_path) as z:
        with z.open("word/document.xml") as f:
            tree = ET.parse(f)

    body = tree.getroot().find(f"{NS_W}body")
    if body is None:
        return paths

    for p in body.findall(f"{NS_W}p"):
        p_style = p.find(f".//{NS_W}pStyle")
        if p_style is None:
            continue
        style_id = p_style.get(f"{NS_W}val")
        level = styles.get(style_id, 0) if style_id else 0
        if level <= 0 or level > 6:
            continue
        # Lấy text của paragraph
        text_runs = [t.text or "" for t in p.findall(f".//{NS_W}t")]
        title = "".join(text_runs).strip()
        if not title:
            continue
        # Cập nhật stack tại level (truncate stack về đúng độ sâu)
        del stack[level - 1 :]
        stack.append(title)
        paths.append(" > ".join(stack))
    return paths
```

**Validation tương đương:** dùng cùng input DOCX, gọi extractor Go (qua CLI `backend/cmd/testpdf` hoặc upload thật) → so sánh số heading + thứ tự với output `extract_headings.py`. Nếu khác, kiểm tra style XML namespace (`xmlns:w`).

---

## 8. Authentication — JWT login

**Endpoint login:** `POST /api/auth/login` (public, có rate limit `LoginRateLimit`)
**Handler:** `backend/internal/handler/auth_handler.go:22-37`
**Route:** `backend/internal/router/router.go:431` — `auth.POST("/login", middleware.LoginRateLimit(rdb), authHandler.Login)`

**Request body** (`backend/internal/model/user.go:35-39`):
```json
{
  "email": "admin@medinet.vn",
  "password": "Admin@123",
  "hub_id": ""
}
```
- `hub_id` optional (cho phép login global, không bind vào hub cụ thể).

**Response** (`backend/internal/model/user.go:41-46`):
```json
{
  "success": true,
  "data": {
    "access_token": "eyJhbGciOiJSUzI1NiIs...",
    "refresh_token": "eyJhbGciOiJSUzI1NiIs...",
    "expires_at": 1714329600,
    "user": { "user": {...}, "roles": [...] }
  }
}
```

**Default admin credential:**
- Email: `admin@medinet.vn` (`backend/scripts/seed.sql:11`)
- Password: `Admin@123` (`backend/scripts/seed.sql:8` — comment xác nhận)
- Hash đã lưu sẵn: `$argon2id$v=19$m=65536,t=3,p=4$...` (seed.sql:13)

**Header gọi protected endpoint:** `Authorization: Bearer <access_token>`

**TTL access token:** 15 phút (`backend/.env.example:36` `JWT_ACCESS_TOKEN_TTL=15m`).
**TTL refresh:** 168 giờ = 7 ngày (`.env.example:37`).

**API key alternative:** Có endpoint `/api/api-keys` (`router.go:542-550`) cho admin tạo API key, nhưng:
- API key chỉ áp dụng cho subset endpoint cụ thể (chưa rõ middleware `JWTAuth` có chấp nhận API key không).
- **Đề xuất cho Phase 1:** dùng JWT login admin đơn giản hơn, không cần API key. Eval chỉ chạy local.

**Pattern Python cho `baseline.py`:**

```python
# Login một lần đầu, refresh khi cần (token hết hạn 15m, baseline upload 10 file có thể dài hơn)
import httpx
import os

class APIClient:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self._access_token: str | None = None
        self._refresh_token: str | None = None
        self._client = httpx.AsyncClient(timeout=120)

    async def login(self, email: str, password: str) -> None:
        r = await self._client.post(
            f"{self.base_url}/api/auth/login",
            json={"email": email, "password": password},
        )
        r.raise_for_status()
        data = r.json()["data"]
        self._access_token = data["access_token"]
        self._refresh_token = data["refresh_token"]

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._access_token}"} if self._access_token else {}

    async def upload_document(self, file_path: Path, hub_id: str) -> dict:
        with file_path.open("rb") as f:
            files = {"file": (file_path.name, f, "application/octet-stream")}
            data = {"hub_id": hub_id}
            r = await self._client.post(
                f"{self.base_url}/api/documents/upload",
                files=files, data=data, headers=self._headers(),
            )
        r.raise_for_status()
        return r.json()["data"]
```

---

## Shared Patterns

### Response shape chuẩn (mọi endpoint Go)

**Source:** `backend/internal/pkg/response/response.go:9-26`

Mọi response thành công có shape:
```json
{ "success": true, "data": <T>, "meta": <pagination_optional> }
```

Mọi response lỗi:
```json
{ "success": false, "error": { "code": "BAD_REQUEST|UNAUTHORIZED|...", "message": "..." } }
```

→ Mọi Python script gọi API phải đọc `response["data"]` thay vì root JSON. Code lỗi viết HOA gạch dưới.

### Cấu trúc collection name mặc định

**Source:** `backend/cmd/server/main.go:218` và `backend/internal/router/router.go:330`
```go
col := h.ChromaCollection
if col == "" { col = "medinet_" + h.Code }
```

→ `eval` hub với `chroma_collection='medinet_eval'` đã được set explicit trong `seed_hub.sql` → không phụ thuộc default behavior.

### File path local upload

**Source:** `backend/internal/service/document_service.go:119-126`
```go
localDir := filepath.Join(s.uploadDir, hub.Code, docID.String())
localPath := filepath.Join(localDir, filepath.Base(header.Filename))
```

→ Eval document file local nằm tại `backend/uploads/eval/<doc_uuid>/<filename>`. Cleanup script cần `shutil.rmtree(backend/uploads/eval)` để dọn sạch.

---

## No Analog Found

| File | Lý do |
|------|-------|
| `eval/scripts/build_scanned.py` | Repo chưa có script Python nào — convention chuẩn PEP 8 + ruff (mục 6 ở trên) |
| `eval/baseline.py` | Repo chưa có script orchestration Python — port logic từ `frontend/src/services/api.ts:23-49, 127-141` (HTTP client + multipart upload pattern) |
| `eval/dataset/queries.jsonl` | File data, không có analog code |
| `eval/dataset/headings.json` | File data, không có analog code |
| `eval/pyproject.toml` | Repo chưa có Python build config — dùng PEP 621 chuẩn |

---

## Metadata

**Analog search scope:**
- `backend/internal/handler/` (3 file đọc đầy đủ)
- `backend/internal/service/document_service.go` (đọc đầy đủ 405 dòng)
- `backend/internal/worker/manager.go` (đọc đầy đủ)
- `backend/internal/vectorstore/chromadb.go` (đọc đầy đủ)
- `backend/internal/rag/extractor/docx.go` (đọc đầy đủ — focus 46-95)
- `backend/internal/rag/extractor/pdf.go` (đọc đầy đủ — focus dòng 52 cho error `no text extracted`)
- `backend/internal/router/router.go` (đọc đầy đủ 602 dòng)
- `backend/internal/database/migrations/001_bootstrap.up.sql` + `002_wiki.up.sql` + `004_audit.up.sql`
- `backend/scripts/seed.sql` + `seed_demo.sql` (head 120 dòng)
- `backend/internal/pkg/response/response.go`
- `backend/internal/model/user.go` + `search.go`
- `backend/.env.example`
- `frontend/src/services/api.ts:1-200`
- `backend/cmd/server/main.go` (đọc đầy đủ 444 dòng)

**Files Python scanned:** 0 (repo không có Python).

**Pattern extraction date:** 2026-04-28
