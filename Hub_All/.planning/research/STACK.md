# Stack Research — M2 Full RAG Rewrite (Python FastAPI + CocoIndex + pgvector)

**Domain:** Brownfield rewrite — Vietnamese medical wiki RAG backend (replace Go + ChromaDB stack)
**Researched:** 2026-05-13
**Confidence:** HIGH (versions verified via PyPI / GitHub releases as of date)

> **Scope guardrail:** Stack list ONLY covers the NEW Python service. The existing Go backend (Gin/pgx/JWT/Argon2 — 16 internal packages), `docling-pipeline/`, ChromaDB, and eval scripts will be DELETED in M2 Phase 1-2. Frontend (React 19 + Vite 6 + TS 5.8 + Tailwind v4) is UNTOUCHED per Decision D6 — not re-listed here.

---

## TL;DR — One-Line Replacement Map

| Old (Go/M1) | New (Python/M2) | Why |
|---|---|---|
| Gin + pgx/v5 | **FastAPI 0.136 + asyncpg 0.30 (raw) + SQLAlchemy 2.0 async (only for Alembic models)** | Codebase đồng nhất Python với cocoindex |
| ChromaDB HTTP | **pgvector extension (Postgres 16) + `pgvector` 0.4.2** | Bớt service, dùng Postgres sẵn có (D3) |
| 9 chunker strategies + extractor + SwappableEmbedder | **cocoindex 1.0.3 (Rust core flow)** | Incremental diff content-hash built-in (giải backlog 999.1) — D2 |
| SwappableLLM (Gemini/OpenAI) | **LiteLLM 1.82** | Drop-in OpenAI-compatible — D5 |
| golang-jwt/jwt v5 RS256 | **PyJWT 2.x (KHÔNG dùng python-jose)** | python-jose barely maintained, có CVE history |
| alexedwards/argon2id | **pwdlib 0.3.0 (Argon2 backend)** ← KHÔNG dùng passlib | passlib deprecated, FastAPI official đã chuyển |
| go-redis/v9 | **redis-py 7.1.1 (async client built-in)** | Native asyncio support |
| golang-migrate raw SQL | **Alembic 1.18.4 (async template)** | Standard cho SQLAlchemy 2 |
| log/slog JSON | **structlog 25.x** | Fast, contextvar-aware, asyncio-safe |
| Go goroutine worker pool | **cocoindex built-in scheduler (Rust)** + FastAPI BackgroundTasks | Indexing concurrency do cocoindex sở hữu |
| Go `pdf`/`excelize` extractor | **pypdf 5.x (text-only PDF) + python-docx 1.2.0** | M2 không hỗ trợ scanned PDF (Docling đã gỡ — D4) |
| `go test` | **pytest + httpx (AsyncClient) + asgi-lifespan + pytest-asyncio** | Standard FastAPI test stack |

**Critical clarification:**
- CocoIndex needs Postgres for **its own state** (content-hash fingerprint, lineage tracking) — **CÙNG Postgres 16 instance** với app data, chỉ tách bằng `db_schema_name` setting → `cocoindex` schema riêng, app dùng schema `public`. KHÔNG cần Postgres riêng.
- pgvector **target** của cocoindex (vector store) cũng nằm trong cùng Postgres. Phải dùng image `pgvector/pgvector:pg17` (KHÔNG plain `postgres:17`) — plain image thiếu extension `vector`.

---

## Recommended Stack

### Core Technologies

| Technology | Version (pinned) | Purpose | Why Recommended |
|---|---|---|---|
| **Python** | `>=3.11,<3.13` | Runtime | cocoindex yêu cầu 3.11+; tránh 3.13 cho đến khi mọi dep ổn định (argon2-cffi đã sẵn sàng nhưng nhiều dep khác chưa) |
| **FastAPI** | `0.136.1` | HTTP framework | Latest stable (released 2026-04-23). Pydantic v2 only từ v0.119+. Native async, OpenAPI auto, dependency injection match Go middleware pattern |
| **Pydantic** | `>=2.7.0,<3` | Validation + settings | FastAPI yêu cầu; Rust core 5-50x nhanh hơn v1. Dùng `pydantic-settings>=2` cho config |
| **Uvicorn** | `0.46.0` | ASGI server | Latest (2026-04-23). Dùng `uvicorn[standard]` để có `uvloop`+`httptools` |
| **Gunicorn** | `>=23.0` (Linux only) | Process manager (prod) | Spawn N uvicorn workers (`-k uvicorn.workers.UvicornWorker`). Windows dev dùng uvicorn trực tiếp |
| **CocoIndex** | `1.0.3` | RAG indexing dataflow (extract → chunk → embed → upsert) | v1.0.3 released 2026-05-05 — production-stable (Rust core). v1.0.0 stable cutover 2026-04-22. Owns incremental diff (content-hash + lineage) — giải backlog 999.1 free. KHÔNG dùng LangChain/LlamaIndex (xem "What NOT to Use") |
| **pgvector** (Python lib) | `0.4.2` | Vector type binding cho SQLAlchemy/asyncpg | Official Python binding; supports asyncpg + SQLAlchemy 2 async |
| **pgvector** (PG ext) | `>=0.7.0` (server-side) | Postgres vector extension | Cocoindex flagship target. Image: `pgvector/pgvector:pg17` |
| **asyncpg** | `0.30.x` | Raw async Postgres driver | 15k QPS — fastest async PG driver. Dùng cho cocoindex flow + read-heavy endpoints |
| **SQLAlchemy** | `2.0.x` (async) | ORM (chỉ cho Alembic model declaration + complex queries) | Cần cho Alembic auto-generate migrations. Async engine dùng asyncpg under the hood |
| **Alembic** | `1.18.4` | Schema migrations | Latest (2026-02-10). Hỗ trợ async template native — thay thế Go raw SQL trong `scripts/migrations/` |
| **LiteLLM** | `1.82.x` | LLM + embedding hot-swap (OpenAI ↔ Gemini) | Single API for 100+ providers. `litellm.acompletion()` + `litellm.aembedding()` async-first. Match Go SwappableLLM/SwappableEmbedder semantics |
| **PyJWT** | `2.12.x` | JWT RS256 sign/verify | **KHÔNG python-jose** (xem "What NOT to Use"). PyJWT actively maintained, drop-in replacement, support RS256/RS384/RS512 + algorithm pinning |
| **pwdlib** | `0.3.0` | Argon2 password hashing | **KHÔNG passlib** (deprecated, Python 3.13 `crypt` removal). pwdlib là khuyến nghị chính thức của FastAPI tutorial (PR #13917) và fastapi-users v13+ |
| **argon2-cffi** | `25.1.0` | Argon2 backend (pwdlib dep) | Auto-installed bởi `pwdlib[argon2]`. Liệt kê tường minh để pin version |
| **redis-py** | `7.1.1` | Redis async client | Released 2026-02-09. Async client built-in (`redis.asyncio`). Hot-swap config cache + rate limit |
| **structlog** | `25.x` | JSON structured logging | Fastest Python logger. contextvars-based — đúng cho asyncio. Match Go log/slog JSON format cho ops tooling tiếp tục dùng được |

### Document Parsers (Replace Docling / Go extractors)

| Library | Version | Purpose | Constraint |
|---|---|---|---|
| **pypdf** | `5.x` | PDF text extraction (text-only PDF) | KHÔNG OCR. Scanned PDF tiếng Việt → trả lỗi tường minh (per D4 + Constraint trong PROJECT.md) |
| **python-docx** | `1.2.0` | DOCX text + table | Standard, maintained. Đủ cho M2 (text + simple tables) |
| **markdown-it-py** | `>=3` | MD → AST cho cocoindex chunker | Cocoindex examples dùng. Native MD chunker preserves headings |
| **chardet** | `>=5` | Encoding detect cho TXT tiếng Việt | UTF-8 BOM / Windows-1258 fallback |

**OUT of scope for M2 parsers (revisit hardening milestone v4):**
- pdfplumber (table-heavy PDFs) — defer
- unstructured / Docling — gỡ hoàn toàn (D4)
- Tesseract OCR (`vie+eng`) — defer, M2 reject scanned PDF tường minh

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---|---|---|---|
| **httpx** | `>=0.27` | Async HTTP client | LiteLLM dùng nội bộ + test client (`AsyncClient` + `ASGITransport`) |
| **pytest** | `>=8` | Test framework | Standard |
| **pytest-asyncio** | `>=0.24` | Async test fixtures | `@pytest.mark.asyncio` cho async tests |
| **asgi-lifespan** | `>=2` | Test lifespan events | Cần thiết khi test cocoindex init / DB pool init trong startup |
| **anyio** | `>=4` | Async backend abstraction | FastAPI/httpx dep — pin để không bị break |
| **python-multipart** | `>=0.0.12` | File upload (FastAPI form-data) | Cần cho `/api/documents/upload` |
| **pydantic-settings** | `>=2.6` | `.env` + 12-factor config | Thay thế Go `os.Getenv` pattern, type-safe |
| **python-dotenv** | `>=1.0` | Load `.env` (dev) | Pydantic-settings dùng. Prod đọc từ env vars |
| **tenacity** | `>=9` | Retry decorator cho LiteLLM calls | Match Go circuit-breaker pattern (M1 Phase 4 logic) |
| **typer** | `>=0.12` | CLI cho admin scripts (hash password, gen keys, run eval) | Thay thế `backend/cmd/hashpw`, `backend/scripts/generate_keys.sh` |

### Development Tools

| Tool | Purpose | Notes |
|---|---|---|
| **uv** | Package manager + venv | Astral's Rust-based pip replacement. 10-100x faster than pip. `uv pip install`, `uv sync`. Recommended 2026 |
| **ruff** | Linter + formatter | Replaces black + isort + flake8. Pin `>=0.6`. Config trong `pyproject.toml` |
| **mypy** | Static type check | `--strict` cho `app/` core code |
| **pre-commit** | Git hook runner | ruff + mypy + secret scan |
| **docker compose** | Local stack (postgres + redis + api) | 3 services thay vì 4 (drop chromadb) |

---

## Installation

**`pyproject.toml` (target — paste-ready):**

```toml
[project]
name = "medinet-wiki-api"
version = "0.1.0"
requires-python = ">=3.11,<3.13"
dependencies = [
    # Web framework
    "fastapi==0.136.1",
    "uvicorn[standard]==0.46.0",
    "pydantic>=2.7.0,<3",
    "pydantic-settings>=2.6,<3",
    "python-multipart>=0.0.12",

    # RAG core
    "cocoindex==1.0.3",
    "litellm>=1.82,<2",
    "pgvector==0.4.2",

    # Database
    "asyncpg==0.30.0",
    "sqlalchemy[asyncio]>=2.0.36,<2.1",
    "alembic==1.18.4",
    "redis>=7.1.1,<8",

    # Auth
    "pyjwt[crypto]>=2.12,<3",
    "pwdlib[argon2]==0.3.0",
    "argon2-cffi>=25.1.0",

    # Document parsing (no OCR — D4)
    "pypdf>=5.0,<6",
    "python-docx==1.2.0",
    "markdown-it-py>=3,<4",
    "chardet>=5,<6",

    # Observability + util
    "structlog>=25.0,<26",
    "tenacity>=9,<10",
    "typer>=0.12,<1",
    "httpx>=0.27,<1",
]

[project.optional-dependencies]
dev = [
    "pytest>=8,<9",
    "pytest-asyncio>=0.24,<1",
    "pytest-cov>=5,<6",
    "asgi-lifespan>=2,<3",
    "anyio>=4,<5",
    "ruff>=0.6,<1",
    "mypy>=1.11,<2",
    "pre-commit>=3,<4",
]
prod = [
    "gunicorn>=23,<24",  # Linux production only
]
```

**Install:**

```bash
# Use uv (recommended, fast)
uv sync --extra dev

# OR pip
pip install -e ".[dev]"

# Production image
pip install -e ".[prod]"
```

---

## CocoIndex Integration Detail (Critical)

CocoIndex requires Postgres for **3 distinct purposes** — all CAN share the same Postgres 16 instance via schemas:

| Purpose | Postgres Component | Setting |
|---|---|---|
| **App business data** (users, hubs, documents, audit_logs) | Schema `public` | Owned by Alembic migrations |
| **CocoIndex internal state** (fingerprint, lineage, flow tracking) | Schema `cocoindex` (configurable via `db_schema_name`) | `cocoindex.Settings(database=ConnectionSpec(url=..., db_schema_name="cocoindex"))` |
| **pgvector target** (chunks + embeddings) | Schema `rag` (recommended) hoặc `public.chunks` | Cocoindex `PostgresTarget(schema="rag", table_name="chunks")` |

**Why 3 schemas (not 3 databases):**
- 1 Postgres container = 1 backup, 1 monitoring target, 1 connection pool (Constraint: bớt service per D3).
- Schema isolation đủ về logic. cocoindex CRUD trên schema riêng không đụng vào table app.
- Alembic chỉ quản lý schema `public` + `rag` (DDL cho table `chunks` cocoindex dùng). Schema `cocoindex` để **cocoindex auto-create** — KHÔNG để Alembic touch (cocoindex tự upgrade qua release).

**Required Postgres image:** `pgvector/pgvector:pg17` (alpine variant nếu cần size nhỏ). Plain `postgres:17` SẼ FAIL với `extension "vector" is not available`.

**docker-compose.yml shape (3 services):**

```yaml
services:
  postgres:
    image: pgvector/pgvector:pg17
    environment:
      POSTGRES_USER: medwiki
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_DB: medwiki
    volumes: ["pgdata:/var/lib/postgresql/data"]
    ports: ["5432:5432"]

  redis:
    image: redis:7.4-alpine
    ports: ["6379:6379"]

  api:
    build: .
    depends_on: [postgres, redis]
    environment:
      DATABASE_URL: postgresql+asyncpg://medwiki:${DB_PASSWORD}@postgres:5432/medwiki
      COCOINDEX_DATABASE_URL: postgres://medwiki:${DB_PASSWORD}@postgres:5432/medwiki
      REDIS_URL: redis://redis:6379/0
    ports: ["8080:8080"]
```

Note: `DATABASE_URL` dùng `postgresql+asyncpg://` (SQLAlchemy/Alembic format). `COCOINDEX_DATABASE_URL` dùng `postgres://` (cocoindex internal format) — same DB, khác URL scheme prefix.

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|---|---|---|
| **PyJWT** | python-jose | **NEVER** (xem "What NOT to Use") |
| **pwdlib** | passlib | NEVER for new code (deprecated); chỉ giữ nếu legacy hash format khác Argon2 cần verify |
| **pwdlib** | argon2-cffi trực tiếp | Khi muốn full control hash format (nâng cao). pwdlib đã wrap argon2-cffi với defaults secure. |
| **asyncpg (raw) + SQLAlchemy 2 (Alembic only)** | Pure asyncpg (no ORM) | Khi không cần migrations (M2 cần) |
| **asyncpg + SQLAlchemy** | psycopg3 async | Khi cần Postgres-native LISTEN/NOTIFY (M2 không cần — Redis pub/sub đủ) |
| **asyncpg + SQLAlchemy** | SQLModel | SQLModel = SQLAlchemy + Pydantic merged, nhưng ABANDONED development pace; SQLAlchemy 2 đã có typed mapped_column tốt hơn. |
| **CocoIndex** | LangChain / LlamaIndex | **NEVER cho M2** — D2 đã chọn cocoindex. LangChain quá nhiều abstraction, lock-in nặng. LlamaIndex cũng tương tự + tài liệu loãng. |
| **CocoIndex** | Tự build pipeline (như Go cũ) | NEVER — đó là lý do pivot M2 |
| **pypdf** | pdfplumber | Khi cần extract tables phức tạp (defer v4) |
| **pypdf** | PyMuPDF (fitz) | Khi cần OCR-free maximum extraction quality. Trade-off: AGPL license — Medinet nội bộ OK nhưng cẩn trọng nếu sau này commercialize |
| **pypdf** | unstructured | Khi muốn 1 lib cho all formats. Slow (1.29s vs 0.024s pypdf), nặng dep, không cần thiết cho M2 |
| **LiteLLM** | OpenAI SDK + Google genai SDK riêng | Khi chỉ dùng 1 provider. M2 cần hot-swap → LiteLLM win |
| **LiteLLM** | LangChain LLM wrappers | Lock-in LangChain — không muốn |
| **structlog** | loguru | Loguru dễ dùng hơn nhưng không structured-first; harder cho log aggregator (Loki, Datadog) parse |
| **uvicorn** | Hypercorn | HTTP/2 support, nhưng Hypercorn chậm hơn ~2x. M2 không cần HTTP/2 (nginx terminate) |
| **uv** | poetry / pdm / pip-tools | uv là consensus 2026 — fastest, Rust-based, drop-in pip API. Poetry vẫn fine nhưng chậm hơn ×10 |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|---|---|---|
| **python-jose** | "Barely maintained, less secure than PyJWT" — community consensus 2026. Có history CVE algorithm confusion. | **PyJWT 2.12+** with `algorithms=["RS256"]` explicit (never accept `none`) |
| **passlib** | Last release 2020, không maintain. Phụ thuộc `crypt` module bị removal trong Python 3.13. FastAPI official tutorial đã chuyển sang pwdlib (PR #13917) | **pwdlib 0.3 + Argon2** |
| **bcrypt** (vs Argon2) | Argon2id win OWASP 2024+ recommendation. Backward-compat với keypair hiện có của Go (alexedwards/argon2id) → chọn Argon2 |
| **LangChain** | Quá nhiều abstraction layers, breaking changes liên tục (0.1 → 0.2 → 0.3 → langchain-core split). Cocoindex IS the framework. | **Direct LiteLLM + cocoindex** |
| **LlamaIndex** | Same lý do as LangChain + index abstraction xung đột với cocoindex flow model | **Cocoindex** |
| **ChromaDB Python client** | Đã quyết định gỡ ChromaDB (D3). Có `pgvector` rồi. | **pgvector + asyncpg** |
| **Docling Python** | Đã gỡ hoàn toàn per D4. Binary 2GB + Tesseract dep nặng. | **pypdf + python-docx (text-only)** — chấp nhận regress scanned PDF |
| **psycopg2** | Sync only, slow, legacy. | **asyncpg** (or psycopg3 nếu cần native PG features) |
| **Flask / Starlette raw** | Flask sync-first → FastAPI async win. Starlette là FastAPI's base — dùng FastAPI luôn cho OpenAPI + DI. | **FastAPI** |
| **django** | Quá nặng, ORM sync-first, migration system clash với Alembic. M2 không cần admin/auth của Django. | **FastAPI + Alembic** |
| **plain `postgres:17` image** | Thiếu extension `vector` — cocoindex sẽ FAIL khởi tạo target | **`pgvector/pgvector:pg17`** |
| **SQLModel** | Development pace abandoned từ giữa 2024. SQLAlchemy 2 typed API đã đủ. | **SQLAlchemy 2 + Pydantic v2** riêng biệt |
| **logging stdlib** trực tiếp | Không structured-first, asyncio context propagation kém | **structlog** |

---

## Stack Patterns by Variant

### If running on Windows dev machine (current user setup):
- **Skip Gunicorn** — Gunicorn không support Windows. Dev: `uvicorn app.main:app --reload --port 8080`
- Postgres: Docker Desktop với image `pgvector/pgvector:pg17` (KHÔNG cài Postgres native — extension management phức tạp)
- Redis: Memurai (Windows-native) HOẶC Docker Desktop `redis:7.4-alpine` (consistent với prod)
- Python venv: `uv venv` rồi `uv pip install -e ".[dev]"`

### If deploying to Linux production:
- Gunicorn + Uvicorn worker: `gunicorn -k uvicorn.workers.UvicornWorker -w 4 app.main:app --bind 0.0.0.0:8080`
- Worker count: `(2 * CPU_cores) + 1` baseline, tune theo I/O pattern
- Reverse proxy: nginx (giữ pattern hiện tại của Go backend cho frontend `/api/*` routing)

### If cocoindex flow gets slow on large docs:
- Cocoindex có **Rust core scheduler** — KHÔNG tự build worker pool (D2 nhấn mạnh điều này)
- Adjust `cocoindex.Settings(global_execution_options=...)` parallelism instead
- pgvector index: `CREATE INDEX ... USING hnsw (embedding vector_cosine_ops)` sau ingest, không trước

### If embedding cost balloons:
- LiteLLM has built-in caching layer (Redis backend) — bật khi cần
- Cocoindex incremental diff (content-hash) đã giảm 90% re-embed call — đó là D2 raison d'être

---

## Version Compatibility Matrix

| Package | Compatible With | Notes |
|---|---|---|
| `fastapi==0.136.1` | `pydantic>=2.7,<3`, `starlette>=0.40,<1`, `python>=3.9` | Pin Pydantic v2 — v0.119+ dropped v1 |
| `cocoindex==1.0.3` | `python>=3.11`, `pydantic>=2` | Rust core ships in wheel — KHÔNG cần Rust toolchain cài máy. Linux/macOS/Windows x64 wheels có sẵn |
| `sqlalchemy>=2.0.36` | `asyncpg>=0.28`, `alembic>=1.13` | SQLAlchemy 2.0 typed mapped_column, KHÔNG dùng 1.4 legacy |
| `alembic==1.18.4` | `sqlalchemy>=2.0`, `python>=3.9` | Use `async` template trong `alembic init -t async migrations/` |
| `pgvector==0.4.2` (Python) | pgvector PG ext `>=0.5`, `sqlalchemy>=1.4` OR `asyncpg>=0.27` | Cocoindex flow tự dùng asyncpg internally — không xung đột |
| `pgvector` (PG ext) | Postgres 13-17. Image `pgvector/pgvector:pg17` ext version 0.8.0 | M2 chốt Postgres 16 → image `pgvector/pgvector:pg16` HOẶC upgrade lên pg17 |
| `pyjwt[crypto]>=2.12` | `cryptography>=42` | `[crypto]` extra cài cryptography cho RS256 |
| `pwdlib[argon2]==0.3.0` | `argon2-cffi>=23` | Bcrypt fallback cũng có nếu legacy hash xuất hiện |
| `litellm>=1.82` | `openai>=1.40`, `httpx>=0.27`, `pydantic>=2` | LiteLLM tự pin OpenAI + Google SDK — KHÔNG cài riêng |
| `redis==7.1.1` | `python>=3.10` | Async client là `redis.asyncio.Redis` — KHÔNG cài `aioredis` riêng (deprecated, merged) |
| `structlog>=25` | `python>=3.9` | contextvars-based — works với asyncio out of box |

**Known gotchas:**
- Nếu Python 3.13: `pwdlib` OK, `pypdf` OK, nhưng `cocoindex==1.0.3` wheel có thể chưa có (check PyPI). **Khuyến nghị M2: Python 3.12** — sweet spot.
- LiteLLM cài kéo theo `openai` + `google-generativeai`. Đừng pin chúng riêng — để LiteLLM quản.
- Alembic async template DDL ops vẫn chạy sync trong sync context. KHÔNG gọi async function trong migration body trừ khi dùng `op.run_async()` mới (Alembic 1.18+).
- pgvector index HNSW: build CHẬM trên dataset lớn. Strategy: bulk insert chunks → build index sau (`CREATE INDEX CONCURRENTLY`).

---

## What's NEW vs M1 (cho author REQUIREMENTS dễ map)

**Đã có trong M1 (sẽ port logic, không re-research):**
- JWT RS256 keypair `backend/keys/private.pem|public.pem` — reuse, chỉ đổi library Go→PyJWT
- Postgres schema `users / hubs / documents / audit_logs` — keep, Alembic baseline migration sẽ snapshot từ schema hiện tại
- Frontend `/api/*` contract — keep URL identical (D6)
- Eval queries.jsonl + 10 file dataset y tế (giữ semantic, port runner Go→pytest per D8)

**Hoàn toàn mới (chưa có equivalent):**
- Cocoindex flow declaration (Python decorators `@cocoindex.flow_def`)
- LiteLLM provider switching (thay SwappableEmbedder/SwappableLLM)
- pgvector schema `chunks` table với HNSW index
- pwdlib hash format (Argon2id) — verify cross-compat với hash hiện có trong DB `users.password_hash` (Go alexedwards/argon2id cùng format Argon2id `$argon2id$v=19$...` → pwdlib verify được)
- structlog JSON output (cố gắng match field names: `time`, `level`, `msg`, `request_id`, `hub_id` → đồng nhất với Go log/slog output cũ để ops dashboards reuse)

**Bị gỡ hoàn toàn:**
- 9 chunker strategies Go (cocoindex chunker thay thế)
- Augmenter Q&A generation (cocoindex transform function hoặc skip — TBD trong REQUIREMENTS)
- ChromaDB client + persistent volume `chroma_data/`
- Storage layer GDrive (`google.golang.org/api/drive/v3`) — defer hoặc port riêng nếu user cần (TBD)
- Docling sidecar + Tesseract `vie+eng` binary

---

## Open Questions (Flag cho REQUIREMENTS author + Roadmapper)

1. **Storage backend cho file uploads** — Go có local + GDrive. M2 default `local` (mount volume Docker). GDrive port là optional task — confirm với user.
2. **GitOps eval framework** — pytest-based mới (D8). queries.jsonl format port nguyên hay refactor?
3. **JWT keypair reuse** — `backend/keys/` cũ là PKCS#1 (Go default). PyJWT cần PKCS#8 hoặc PKCS#1 đều OK với `cryptography` lib. CONFIRM keypair load đúng.
4. **Argon2 hash cross-compat** — verify pwdlib có thể verify hash do Go `alexedwards/argon2id` tạo (cùng `$argon2id$` prefix nhưng params có thể khác). Test sớm Phase 2.
5. **Cocoindex augmenter equivalent** — Go có augmenter sinh Q&A pair từ chunk. Cocoindex có transform function tương đương? Hoặc skip augmenter trong M2 (chấp nhận quality regress) → flag risk.
6. **Postgres 16 → 17 upgrade** — pgvector image official ưu tiên pg17. M2 nên migrate luôn lên 17 hay giữ 16 (giảm risk)? Khuyến nghị: giữ 16 (`pgvector/pgvector:pg16`), upgrade ở hardening v4.

---

## Sources

**HIGH confidence (PyPI / official docs / GitHub releases):**
- [cocoindex on GitHub Releases](https://github.com/cocoindex-io/cocoindex/releases) — v1.0.0 (2026-04-22), v1.0.3 (2026-05-05) confirmed
- [cocoindex on PyPI](https://pypi.org/project/cocoindex/) — installation, Python 3.11 requirement
- [cocoindex docs — Docker + pgvector setup](https://cocoindex.io/docs/tutorials/docker_pgvector_setup) — `pgvector/pgvector:pg17` image requirement
- [cocoindex docs — Postgres target](https://cocoindex.io/docs/targets/postgres) — schema parameter, vector type mapping
- [cocoindex docs — Settings](https://cocoindex.io/docs/core/settings) — `db_schema_name` for shared Postgres
- [FastAPI Release Notes](https://fastapi.tiangolo.com/release-notes/) — v0.136.1 (2026-04-23), Pydantic v2 only from v0.119
- [Uvicorn Release Notes](https://uvicorn.dev/release-notes/) — v0.46.0 (2026-04-23)
- [Alembic Changelog](https://alembic.sqlalchemy.org/en/latest/changelog.html) — v1.18.4 (2026-02-10), async template, run_async()
- [redis-py releases](https://github.com/redis/redis-py/releases) — v7.1.1 (2026-02-09), Python 3.10+
- [pgvector-python on GitHub](https://github.com/pgvector/pgvector-python) — v0.4.2, asyncpg + SQLAlchemy support
- [PyJWT on PyPI](https://pypi.org/project/PyJWT/) — v2.12.x, March 2026 release
- [pwdlib on PyPI](https://pypi.org/project/pwdlib/) — v0.3.0 (October 2025)
- [LiteLLM releases](https://github.com/BerriAI/litellm/releases) — v1.82+ active maintenance
- [python-docx on PyPI](https://pypi.org/project/python-docx/) — v1.2.0
- [argon2-cffi on PyPI](https://pypi.org/project/argon2-cffi/) — v25.1.0, Python 3.13/3.14 support

**MEDIUM confidence (community blogs + cross-verified):**
- [FastAPI PR #13917 — pwdlib migration](https://github.com/fastapi/fastapi/pull/13917) — official FastAPI tutorial migration to pwdlib
- [fastapi-users v13 release](https://github.com/fastapi-users/fastapi-users/discussions/1372) — pwdlib + Argon2 default
- [asyncpg vs psycopg3 vs SQLAlchemy 2026 benchmarks](https://leapcell.io/blog/building-high-performance-async-apis-with-fastapi-sqlalchemy-2-0-and-asyncpg) — 15k QPS asyncpg
- [PyJWT vs python-jose recommendation 2026](https://snyk.io/advisor/python/pyjwt) — Snyk maintenance scoring
- [PDF extractor comparison 2026](https://onlyoneaman.medium.com/i-tested-7-python-pdf-extractors-so-you-dont-have-to-2025-edition-c88013922257) — pypdf 0.024s vs unstructured 1.29s
- [Choosing Python Logging Library 2026 — Dash0](https://www.dash0.com/guides/python-logging-libraries) — structlog production recommendation

**LOW confidence (single source, flag for validation in Phase 1):**
- Exact wheel availability for `cocoindex==1.0.3` on Windows x64 — need to verify by `pip install` smoke test
- `pwdlib` verifying hash from Go `alexedwards/argon2id` — need integration test Phase 2 (Auth port)
- Cocoindex augmenter / transform function feature parity with Go augmenter — need RTFM Phase 5 (Ingest)

---

*Stack research for: M2 Full RAG Rewrite (Medinet Wiki Hub_All)*
*Researched: 2026-05-13*
*Confidence: HIGH on versions, MEDIUM on cross-compat assumptions, LOW on cocoindex feature parity for augmenter*
