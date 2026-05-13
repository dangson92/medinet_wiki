# Architecture Research — M2 Full RAG Rewrite

**Domain:** Multi-tenant internal wiki + RAG (FastAPI + cocoindex + pgvector, brownfield rewrite replacing Go monolith)
**Researched:** 2026-05-13
**Confidence:** HIGH for cocoindex/FastAPI integration pattern (official example exists), MEDIUM for migration ordering (project-specific judgment), HIGH for module layout (mirrors current Go layered pattern + Python conventions).
**Downstream consumer:** Roadmapper agent — output drives 10-15 phase ordering.

---

## TL;DR — Concrete Architecture Proposal (1 page)

| Decision | Recommendation | Rationale |
|---|---|---|
| **Process model** | Single FastAPI process running cocoindex `FlowLiveUpdater` in `lifespan` (in-process, background threads managed by cocoindex Rust core). NO separate worker container in M2. | Official `examples/fastapi_server_docker` + `examples/image_search` confirm this pattern. 100 docs/day load is trivially handled by cocoindex's Rust scheduler. Adding a separate worker process now = premature complexity. Defer to v4.0 hardening if scale demands. |
| **CocoIndex pattern** | **Library, in-process.** Flow defined in `api/app/rag/flow.py`, started in FastAPI lifespan. Source = **Postgres `documents` table with `LISTEN/NOTIFY`** (not LocalFile watcher). | Native push-based trigger when FastAPI inserts a row → cocoindex picks up immediately. Beats LocalFile polling and avoids a separate queue abstraction. Confirmed by `cocoindex.sources.Postgres(... notification=PostgresNotification())`. |
| **Ingestion flow** | `POST /api/documents/upload` → save file to file_store (local disk, `RAG_UPLOAD_DIR=./uploads/`) → `INSERT INTO documents (..., status='pending')` → Postgres LISTEN/NOTIFY wakes cocoindex flow → flow reads file_path, extracts, chunks, embeds (LiteLLM), writes to `chunks` table with `vector` column → cocoindex updates `documents.indexed_at`. Frontend polls `GET /api/documents/:id/status`. | Decouples API from indexing. Cocoindex owns incremental diff (content-hash). FastAPI never blocks on extract/embed. |
| **Search/Ask flow** | FastAPI handler queries `chunks` table directly via SQL — `SELECT ... ORDER BY embedding <=> $1 LIMIT k WHERE hub_id = $2`. **Cocoindex is NOT in the query path.** `/api/ask` = search + LiteLLM streaming (SSE) + citation injection. | Cocoindex is indexing-only (per official guidance in image_search example). Search latency = pgvector ANN only. Hot-swap of embedding/LLM happens at query embed time via LiteLLM config reload. |
| **Module layout** | `Hub_All/api/app/{auth,hubs,users,documents,audit,rag}/` — one folder per domain mirroring current Go pattern. `rag/` contains `flow.py` (cocoindex), `search.py`, `ask.py`, `embeddings.py` (LiteLLM wrapper). | Familiar to anyone reading current Go code; clear boundaries; pytest can mirror this layout. |
| **Config** | `pydantic-settings` `BaseSettings` reading from `.env`. Same env vars carry over (`DATABASE_URL`, `REDIS_URL`, `JWT_PRIVATE_KEY_PATH`...). NEW: `COCOINDEX_DATABASE_URL` for cocoindex internal state (separate DB on same Postgres instance). | Cocoindex requires `COCOINDEX_DATABASE_URL` (confirmed in docs). Use separate logical DB `cocoindex_state` on same Postgres 16+pgvector container to avoid coupling our schema with cocoindex's internal lineage tables. |
| **Migration order** | 1) Skeleton + tear-down old Python sidecar/eval/chroma_data. 2) Compose rewrite (postgres+pgvector + redis + python-api). 3) Auth port. 4) Hub + user + audit port (parallel-able with 5). 5) Cocoindex flow MVP (DOCX/TXT/MD/PDF text). 6) Search endpoint. 7) Ask endpoint + LiteLLM hot-swap. 8) Frontend smoke test (URL compat). 9) Eval framework + gate ≥75%. 10) Tear-down old Go backend. 11-12) Hardening (logs, metrics, integration tests). | See §"Migration Path" for parallelization opportunities. **Phase 4 (cocoindex flow) can run in parallel with Phase 3 (auth) once Phase 2 compose is up** — 2 devs can split. |
| **Docker compose** | 3 services: `postgres-pgvector` (pgvector/pgvector:pg16 image), `redis`, `python-api`. NO separate cocoindex container in M2. Drop `chromadb` + `docling-pipeline`. | 1 fewer service vs M1. Cocoindex runs inside `python-api`. |
| **Tests** | `api/tests/` separate top-level dir mirroring `api/app/` structure. pytest convention. | Python idiom (vs Go's co-located `_test.go`). |
| **JWT keys** | Move to `api/keys/` (was `backend/keys/`). Same PEM files, same RS256 algorithm. | Locality with new code; update `.env` path. |

---

## Standard Architecture

### System Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                      Frontend (UNCHANGED in M2)                       │
│         React 19 SPA · localhost:5173 · GET/POST /api/*               │
└──────────────────────────────┬───────────────────────────────────────┘
                               │  HTTP (port 8080)
                               ▼
┌──────────────────────────────────────────────────────────────────────┐
│                  FastAPI Process (uvicorn workers)                    │
│                                                                       │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │              HTTP / Middleware Layer (FastAPI)                │    │
│  │  CORS · GZip · JWT auth dep · RBAC dep · rate-limit (slowapi) │    │
│  └──────────┬───────────────────────────────────────────────────┘    │
│             │                                                          │
│  ┌──────────▼───────────────────────────────────────────────────┐    │
│  │                    Route Handlers (APIRouter)                 │    │
│  │   auth · hubs · users · documents · search · ask · audit ·   │    │
│  │                    apikeys · settings                          │    │
│  └──────────┬───────────────────────────────────────────────────┘    │
│             │                                                          │
│  ┌──────────▼───────────────────────────────────────────────────┐    │
│  │                  Service Layer (business logic)               │    │
│  │   AuthService · HubService · DocumentService · SearchService  │    │
│  │                  AskService · AuditService                    │    │
│  └──────────┬───────────────────────────────────────────────────┘    │
│             │                                                          │
│  ┌──────────▼───────────────────────────────────────────────────┐    │
│  │       Repository Layer (asyncpg via SQLAlchemy 2.x async)     │    │
│  └──────────┬───────────────────────────────────────────────────┘    │
│             │                                                          │
│  ┌──────────▼───────────────────────────────────────────────────┐    │
│  │         ╔══════════ Cocoindex Library (in-process) ══════╗    │    │
│  │         ║  FlowLiveUpdater (started in lifespan)         ║    │    │
│  │         ║  ┌──────────────────────────────────────────┐  ║    │    │
│  │         ║  │ Source: Postgres documents (LISTEN/      │  ║    │    │
│  │         ║  │         NOTIFY on INSERT/UPDATE)         │  ║    │    │
│  │         ║  │ Transform: extract → chunk → embed       │  ║    │    │
│  │         ║  │ Target: pgvector chunks table            │  ║    │    │
│  │         ║  └──────────────────────────────────────────┘  ║    │    │
│  │         ║  Internal state: COCOINDEX_DATABASE_URL        ║    │    │
│  │         ╚════════════════════════════════════════════════╝    │    │
│  └───────────────────────────────────────────────────────────────┘    │
└───────┬─────────────────────┬───────────────────┬────────────────────┘
        │                     │                   │
        ▼                     ▼                   ▼
┌───────────────┐    ┌────────────────┐    ┌──────────────────────────┐
│   Redis 7     │    │ Postgres 16    │    │ External: OpenAI/Gemini  │
│ rate-limit ·  │    │ + pgvector     │    │   via LiteLLM (HTTPS)    │
│ JWT blacklist │    │                │    │                          │
│ · search cache│    │ DB 1: medinet  │    └──────────────────────────┘
│ · usage rt    │    │   (app schema) │
└───────────────┘    │ DB 2: cocoindex│    ┌──────────────────────────┐
                     │   (state/LMDB) │    │ File Store               │
                     │                │    │ ./uploads/ (host vol)    │
                     │ Tables:        │    │ optional: GCS at v4.0    │
                     │ - users        │    └──────────────────────────┘
                     │ - hubs         │
                     │ - documents    │
                     │ - chunks       │
                     │   (vector col) │
                     │ - audit_logs   │
                     │ - api_keys     │
                     │ - usage_events │
                     └────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation | New / Modified / Deleted vs M1 |
|-----------|----------------|------------------------|--------------------------------|
| **FastAPI app** | HTTP gateway, dependency injection, route registration | `api/app/main.py` (`create_app()` factory) | NEW (replaces Gin) |
| **Middleware** | CORS, GZip, JWT verify, RBAC, rate-limit | `starlette.middleware.*` + `slowapi` + custom `Depends()` | NEW (replaces `internal/middleware/`) |
| **Auth domain** | Login, refresh, logout, /me, password hashing (Argon2), JWT issuance (RS256) | `python-jose[cryptography]` + `passlib[argon2]` | NEW (replaces Go `auth_service.go` + `pkg/jwt`) |
| **Hub registry** | CRUD hubs, isolation key for all queries | SQLAlchemy 2.x async ORM | NEW (replaces Go `hub_service.go`) |
| **User mgmt** | CRUD users, role assignment, profile | SQLAlchemy 2.x async ORM | NEW |
| **Document service** | Upload, status query, list — also INSERTs into `documents` to trigger cocoindex | SQLAlchemy + file_store interface | NEW (slim — no extract logic; cocoindex owns it) |
| **Cocoindex flow** | Extract → chunk → embed → upsert chunks | `cocoindex` library, defined in `api/app/rag/flow.py` | NEW (replaces ENTIRE `internal/rag/pipeline.go` + 9 chunkers + extractors + worker pool) |
| **Search service** | Embed query (LiteLLM) → SQL `<=>` query on `chunks` → assemble response | `asyncpg` raw SQL or SQLAlchemy `func.l2_distance` | NEW (replaces Go `rag/searcher.go`) |
| **Ask service** | Search + LLM call (LiteLLM streaming) + citation injection | LiteLLM `acompletion(stream=True)` + SSE response | NEW (replaces Go `rag/answerer.go`) |
| **Embeddings wrapper** | Hot-swap OpenAI/Gemini via LiteLLM config reload | LiteLLM `embedding()` with model alias | NEW (replaces `internal/embedding/swappable.go`) |
| **Audit log** | Async append-only event log | SQLAlchemy + asyncio background task | NEW (replaces `internal/service/audit_service.go`) |
| **File store** | Save uploaded files | Local FS adapter; GCS adapter deferred | MODIFIED — drop gdrive Go SDK, add `google-cloud-storage` Python later |
| **Migrations** | Schema management | Alembic | NEW (replaces `golang-migrate`); migration files **NEW** (not ported from Go SQL — schema is being redesigned to add `vector` column + drop chroma-only cols) |
| **ChromaDB client** | — | — | **DELETED** (whole `internal/vectorstore/`) |
| **Worker pool** | — | — | **DELETED** (cocoindex's Rust scheduler replaces `internal/worker/`) |
| **Docling sidecar** | — | — | **DELETED** (whole `docling-pipeline/` dir; D4) |

---

## Recommended Project Structure

```
Hub_All/
├── api/                                # NEW — Python project root
│   ├── pyproject.toml                  # Poetry or uv project def
│   ├── alembic.ini                     # Alembic config
│   ├── .env / .env.example             # All env vars (DATABASE_URL, COCOINDEX_DATABASE_URL, ...)
│   ├── Dockerfile                      # python:3.11-slim base
│   ├── keys/                           # JWT RSA PEMs (gitignored) — moved from backend/keys/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                     # FastAPI app factory + lifespan (cocoindex init/start)
│   │   ├── config.py                   # pydantic-settings BaseSettings
│   │   ├── db/
│   │   │   ├── __init__.py
│   │   │   ├── session.py              # async engine + AsyncSession factory
│   │   │   ├── base.py                 # SQLAlchemy declarative base
│   │   │   └── models.py               # ORM: User, Hub, Document, Chunk, AuditLog, APIKey
│   │   ├── auth/
│   │   │   ├── router.py               # /api/auth/login, /refresh, /me, /logout
│   │   │   ├── service.py              # business logic
│   │   │   ├── deps.py                 # get_current_user, require_role
│   │   │   ├── jwt.py                  # RS256 sign/verify wrapper
│   │   │   └── argon2.py               # password hash helpers
│   │   ├── hubs/
│   │   │   ├── router.py               # /api/hubs CRUD
│   │   │   ├── service.py
│   │   │   ├── repo.py
│   │   │   └── schemas.py              # Pydantic DTOs
│   │   ├── users/
│   │   │   ├── router.py
│   │   │   ├── service.py
│   │   │   ├── repo.py
│   │   │   └── schemas.py
│   │   ├── documents/
│   │   │   ├── router.py               # /api/documents/upload, /:id/status
│   │   │   ├── service.py              # save file → INSERT documents (triggers cocoindex)
│   │   │   ├── repo.py
│   │   │   ├── storage.py              # file_store interface + local impl
│   │   │   └── schemas.py
│   │   ├── audit/
│   │   │   ├── router.py
│   │   │   ├── service.py              # async background-task logger
│   │   │   └── repo.py
│   │   ├── apikeys/
│   │   │   ├── router.py
│   │   │   ├── service.py
│   │   │   └── repo.py
│   │   ├── rag/
│   │   │   ├── __init__.py
│   │   │   ├── flow.py                 # ★ cocoindex flow definition (the ENTIRE indexing pipeline)
│   │   │   ├── search.py               # vector ANN query → top-k chunks
│   │   │   ├── ask.py                  # search + LLM stream + citation
│   │   │   ├── embeddings.py           # LiteLLM embedding hot-swap wrapper
│   │   │   ├── llm.py                  # LiteLLM completion hot-swap wrapper
│   │   │   ├── router.py               # /api/search, /api/ask, /api/rag-config
│   │   │   └── schemas.py
│   │   ├── settings_store/             # for runtime settings (provider keys etc.) — replaces internal/service/settings
│   │   │   ├── service.py              # AES-GCM encrypt secrets, persist to settings table
│   │   │   └── repo.py
│   │   ├── middleware/
│   │   │   ├── rate_limit.py           # slowapi or custom Redis bucket
│   │   │   ├── security_headers.py
│   │   │   └── error_handler.py        # exception_handler → {success:false, error:{...}}
│   │   └── pkg/
│   │       ├── response.py             # envelope helper {success, data, error, meta}
│   │       ├── crypto.py               # AES-GCM (mirrors pkg/crypto/aes.go)
│   │       └── validator.py
│   ├── migrations/                     # Alembic
│   │   ├── env.py
│   │   ├── script.py.mako
│   │   └── versions/
│   │       ├── 001_init_pgvector.py    # CREATE EXTENSION vector; users, hubs, tokens
│   │       ├── 002_wiki.py             # documents, chunks (with vector col)
│   │       ├── 003_audit.py
│   │       ├── 004_api_keys.py
│   │       ├── 005_settings.py
│   │       └── 006_usage.py
│   └── tests/
│       ├── conftest.py                 # pytest fixtures (db, client, jwt)
│       ├── unit/
│       │   ├── auth/test_jwt.py
│       │   ├── auth/test_argon2.py
│       │   └── rag/test_search.py
│       └── integration/
│           ├── test_auth_flow.py
│           ├── test_document_upload_to_search.py    # end-to-end with cocoindex
│           └── test_hub_isolation.py
│
├── frontend/                           # UNCHANGED
│
├── docker-compose.yml                  # MODIFIED — 3 services (was 4)
├── eval/                               # NEW (M1 deleted, written from scratch)
│   ├── queries.jsonl                   # ported semantically from M1
│   ├── dataset/                        # 10 Vietnamese medical files
│   ├── run_eval.py                     # pytest-based
│   └── metrics.py                      # top-K recall, MRR, latency
│
├── backend/                            # DELETED at Phase 10 — kept until then for reference port
├── docling-pipeline/                   # DELETED at Phase 1
├── chroma_data/                        # DELETED at Phase 1
└── .planning/                          # GSD planning (unchanged)
```

### Structure Rationale

- **`api/` as top-level Python project:** mirrors current `backend/` Go project; keeps Python tooling (`pyproject.toml`, `pytest.ini`, `alembic.ini`) co-located; gives clean Docker build context.
- **Domain folders under `app/` (auth, hubs, users, documents, rag, audit):** mirrors current Go layered pattern (`handler_*` + `service_*` + `repo_*`) but groups by aggregate not by layer — improves cohesion and matches FastAPI community convention (see `tiangolo/full-stack-fastapi-template`). One folder = one bounded context.
- **`rag/` as a domain like any other (not a special package):** prevents the M1 mistake of treating RAG as separate "engine" code. RAG endpoints are just routes; cocoindex flow is just `flow.py` inside.
- **`db/models.py` single file for all SQLAlchemy ORM models:** Alembic autogenerate needs one MetaData; co-locating models simplifies migration. Each domain folder imports from `db.models` — no duplicate model files.
- **`migrations/` as sibling of `app/`:** Alembic convention; keeps SQL versioning separate from runtime code.
- **`tests/` mirrors `app/`:** standard pytest layout; can run `pytest tests/unit/auth/` to scope.
- **`keys/` next to `app/`:** JWT private keys + same ACL as code repo; `.gitignore` enforced.
- **`eval/` as Hub_All sibling, not under `api/`:** evaluation is a separate concern; can be run from CI without booting the full API.

---

## Architectural Patterns

### Pattern 1: Cocoindex as In-Process Library (NOT Daemon)

**What:** Define cocoindex flow in `api/app/rag/flow.py`, initialize and start `FlowLiveUpdater` in FastAPI `lifespan`. Cocoindex runs background threads inside the FastAPI process via its Rust core.

**When to use:** Web API that owns its own ingestion. Workload < tens of thousands of docs/day. Want single deployable unit.

**Trade-offs:**
- (+) Single process → simpler deploy, no IPC, no Redis queue layer
- (+) Cocoindex's Rust scheduler is already async-safe and respects concurrency limits (`GlobalExecutionOptions`)
- (+) FastAPI lifespan ensures clean startup/shutdown ordering
- (−) Heavy ingestion CPU/RAM impacts API response latency on same machine
- (−) Cannot scale ingestion independently of API (mitigated by uvicorn workers > 1, but cocoindex must be initialized exactly once — see Pitfalls)

**Example (canonical pattern from `cocoindex/examples/fastapi_server_docker` and `image_search`):**
```python
# api/app/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
import cocoindex
from app.rag.flow import medinet_ingest_flow

@asynccontextmanager
async def lifespan(app: FastAPI):
    cocoindex.init()                              # reads COCOINDEX_DATABASE_URL
    app.state.updater = cocoindex.FlowLiveUpdater(medinet_ingest_flow)
    app.state.updater.start()
    yield
    app.state.updater.abort()                     # graceful stop

app = FastAPI(lifespan=lifespan)
```

### Pattern 2: Postgres LISTEN/NOTIFY as Ingestion Trigger (NOT File Watcher)

**What:** Use `cocoindex.sources.Postgres(table_name="documents", notification=PostgresNotification())` as the flow's source. Cocoindex receives a NOTIFY when FastAPI INSERTs a row → processes that row immediately.

**When to use:** API-driven uploads where the file is saved AND a metadata row is inserted in the same transaction.

**Trade-offs:**
- (+) Push-based — no polling, no LocalFile watcher race conditions
- (+) FastAPI controls when ingestion happens (write the row when ready)
- (+) Natural place to put `hub_id`, `uploaded_by`, `mime_type`, `file_path` — cocoindex flow reads these for routing/metadata
- (−) Requires a `documents` table schema that's the contract between FastAPI and cocoindex
- (−) Need `ordinal_column` (e.g. `updated_at`) for cocoindex to detect reprocessable changes for incremental diff

**Example:**
```python
# api/app/rag/flow.py
import cocoindex
from cocoindex.sources import Postgres, PostgresNotification
from app.rag.embeddings import embed_text          # LiteLLM wrapper

@cocoindex.flow_def(name="medinet_ingest")
def medinet_ingest_flow(flow_builder, data_scope):
    data_scope["documents"] = flow_builder.add_source(
        Postgres(
            table_name="documents",
            ordinal_column="updated_at",
            notification=PostgresNotification(),
            # database= cocoindex.add_transient_auth_entry(...) for app's DATABASE_URL
        ),
    )
    with data_scope["documents"].row() as doc:
        doc["text"] = doc["file_path"].transform(extract_text)   # custom fn
        with doc["text"].chunk(chunk_size=512, overlap=64) as chunk:
            chunk["embedding"] = chunk["content"].transform(embed_text)
            chunk.export(
                "chunks",
                cocoindex.targets.Postgres(table_name="chunks"),
                primary_key_fields=["doc_id", "chunk_idx"],
                vector_indexes=[cocoindex.VectorIndexDef("embedding", cocoindex.VectorSimilarityMetric.COSINE_SIM)],
            )
```

### Pattern 3: Search/Ask Bypass Cocoindex — Direct pgvector SQL

**What:** Query endpoints do not call cocoindex. They embed the query string (LiteLLM) and run `SELECT ... ORDER BY embedding <=> $1` against the `chunks` table that cocoindex populated.

**When to use:** Always, for read paths. This is the official pattern from `examples/image_search` (search endpoint queries Qdrant directly, not cocoindex).

**Trade-offs:**
- (+) Search latency = pgvector ANN only (cocoindex adds zero overhead)
- (+) Decouples query schema from indexing logic — admin can adjust ANN params (`hnsw.ef_search`) without touching flow
- (+) Hot-swap embedding provider only affects query embedding (and next reindex)
- (−) Hot-swap changes the embedding model dimension → existing chunks become incompatible. Mitigation: bind embedding model version per hub; full reindex required on swap (cocoindex's content-hash diff handles this automatically — flag chunks as stale).

**Example:**
```python
# api/app/rag/search.py
async def search(db: AsyncSession, q: str, hub_id: str, k: int = 10):
    qvec = await embed_text(q)                    # LiteLLM
    rows = await db.execute(text("""
        SELECT chunk_id, content, doc_id, 1 - (embedding <=> :qv) AS score
        FROM chunks
        WHERE hub_id = :hub
        ORDER BY embedding <=> :qv
        LIMIT :k
    """), {"qv": qvec, "hub": hub_id, "k": k})
    return rows.all()
```

### Pattern 4: LiteLLM as Provider Abstraction (Replaces Swappable Wrappers)

**What:** Use `litellm.acompletion()` and `litellm.aembedding()` with model aliases. Settings table stores `LLM_PROVIDER`, `LLM_MODEL`, `EMBEDDING_PROVIDER`, `EMBEDDING_MODEL`. `/api/rag-config` PUT updates settings + signals a reload (in-memory config refresh — no process restart).

**When to use:** Whenever you need OpenAI ↔ Gemini hot-swap.

**Trade-offs:**
- (+) ~20 LOC replaces Go `swappable.go` + `openai.go` + `gemini.go` × 2 (embedding + LLM)
- (+) Built-in retry, rate-limit, fallback, cost tracking
- (+) Adding new provider (Anthropic, Cohere, local Ollama) = config-only
- (−) Adds a heavy dependency (~50 MB); pin version to avoid breakage
- (−) Streaming behavior differs slightly per provider — wrap in normalizer

### Pattern 5: Async Background Tasks for Audit/Usage Logging

**What:** Use FastAPI `BackgroundTasks` + `asyncio.Queue` for non-blocking audit log writes. Batched `INSERT ... VALUES (...)` flush every 2s or 128 entries.

**When to use:** Replaces Go's `UsageLogger` CopyFrom batcher. Audit, usage events.

**Trade-offs:**
- (+) Single process — no need for Redis Pub/Sub between API and worker
- (−) On process crash, in-memory buffer is lost (acceptable for audit; for billing use durable queue)
- For M2: in-memory is fine (defer durable queue to hardening v4.0)

---

## Data Flow

### Flow 1 — Document Ingestion (Frontend → pgvector)

```
[Admin uploads file in DocumentIngestion.tsx]
        │
        ▼  POST /api/documents/upload (multipart, JWT)
[FastAPI: documents/router.py]
        │
        ▼  DocumentService.create()
[1] Save file to RAG_UPLOAD_DIR/<uuid>.<ext>  (storage.save)
[2] INSERT INTO documents (id, hub_id, file_path, mime, status='pending', updated_at=now())
        │
        │  ── Postgres NOTIFY fires ──
        ▼
[Cocoindex FlowLiveUpdater (in-process)]
        │
        ▼  flow.medinet_ingest_flow
[Stage 1] Extract text by mime → str
[Stage 2] Chunk (cocoindex SplitRecursively or custom) → List[chunk]
[Stage 3] Embed each chunk via LiteLLM (OpenAI/Gemini)
[Stage 4] UPSERT INTO chunks (chunk_id, doc_id, hub_id, content, embedding, ...)
[Stage 5] UPDATE documents SET status='completed', indexed_at=now() WHERE id=...
        │
        ▼
[Frontend polls GET /api/documents/:id/status]
[FastAPI returns {status:'completed', chunk_count:N}]
```

**Key integration points:**
- File path passed via DB row (not via memory or queue) — cocoindex flow reads `documents.file_path` and opens the file from the shared volume.
- Cocoindex content-hash incremental diff: re-uploading the same file → no re-embed (closes backlog 999.1 natively).
- Editing a document (PATCH `/api/documents/:id` setting new `content_hash`) → cocoindex re-processes only that row.

### Flow 2 — Search (Frontend → top-K chunks)

```
[User types query in CrossHubSearch.tsx]
        │
        ▼  GET /api/search?q=...&hub_id=X&k=10  (JWT)
[FastAPI: rag/router.py → search.py]
        │
        ▼  SearchService.search()
[1] Check Redis cache (key = sha256(q|hub|k|provider|model))
[2] Cache miss → LiteLLM embed(q) → vector
[3] SQL: SELECT ... FROM chunks WHERE hub_id=... ORDER BY embedding <=> $1 LIMIT k
[4] Filter min_score (>0.3 default)
[5] Cache result in Redis (TTL 5min)
        │
        ▼
[Response: List[{chunk_id, content, doc_id, score}] in {success, data} envelope]
```

### Flow 3 — Ask (Frontend → LLM answer with citations, streaming)

```
[User clicks "Ask" in CrossHubSearch.tsx]
        │
        ▼  POST /api/ask {q, hub_ids[], stream:true}
[FastAPI: rag/router.py → ask.py]
        │
        ▼  AskService.ask()
[1] SearchService.search() → top-k chunks
[2] Build prompt:
       "Context:\n[src:abc] chunk content...\n[src:def] ...\nQuestion: ...\nAnswer with [src:id] citations."
[3] LiteLLM acompletion(stream=True)
        │
        ▼  SSE response (Server-Sent Events via StreamingResponse)
[Frontend reads SSE, appends text, parses [src:X] → CitationText.tsx renders [N] popover]
[On stream end: send final {citations: [{number:1, chunk_id:abc, snippet:...}, ...]}]
```

### Flow 4 — Hot-Swap Provider

```
[Admin in Settings.tsx changes embedding model]
        │
        ▼  PUT /api/rag-config {provider, key, model}
[FastAPI: rag/router.py PUT handler]
        │
        ▼
[1] settings_store.set(key, value, secret=True for API key) — AES-GCM encrypt
[2] In-memory config singleton refresh
[3] LiteLLM model alias re-register
[4] Audit log entry
        │
        ▼  202 Accepted
[Next /api/search call uses new provider — no restart]
```

**WARNING:** Changing embedding model dimension → existing chunks have wrong dim. Two options:
- (a) Trigger full reindex by `UPDATE documents SET updated_at = now()` for all rows in hub (cocoindex picks up).
- (b) Refuse swap if dimension mismatch and warn admin.

Recommend (b) for M2 with explicit "reindex hub" admin action.

### State Management

- **Backend stateless HTTP.** State in Postgres (durable) + Redis (cache/realtime) + file_store (binary).
- **Cocoindex internal state in COCOINDEX_DATABASE_URL Postgres DB** — lineage, content-hash, last-processed offsets. NOT in app's main DB to keep schemas clean.
- **Settings cached in process memory after first read** — invalidated by `PUT /api/rag-config`.

---

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| **0-100 users, 100 docs/day (M2 target)** | Single FastAPI process, 2 uvicorn workers, cocoindex in-process, 1 Postgres, 1 Redis. Total 3 containers. |
| **100-1k users, 1k docs/day** | Bump uvicorn workers to 4-8. Cocoindex must be initialized in exactly one worker (use `--preload` carefully — see Pitfalls). pgvector HNSW index tuning (`ef_construction=128`, `m=16`). Postgres pool size to 25. |
| **1k+ users or 10k docs/day** | Split cocoindex into a separate container (`cocoindex-worker`) using `cocoindex update -L` CLI. FastAPI containers scale horizontally (no cocoindex). Cocoindex worker is singleton with HA via Postgres advisory lock. Redis for query cache. Consider read replica for pgvector. |
| **>10k docs/day** | Sharded pgvector by `hub_id`; or migrate to Qdrant cluster. Cocoindex worker pool of N (each scoped to a hub subset by source filter). |

### Scaling Priorities

1. **First bottleneck (M2 traffic profile):** Embedding API latency (~200-500ms per call from OpenAI/Gemini). Mitigation: cocoindex batches embeddings automatically; tune `batch_size` setting.
2. **Second bottleneck:** pgvector ANN scan for cross-hub search. Mitigation: HNSW index per `hub_id` filter (`CREATE INDEX ... USING hnsw (embedding vector_cosine_ops)` + `WHERE hub_id = ?`); enable `hnsw.iterative_scan` if pg17.
3. **Third (only at scale):** FastAPI single-process CPU during ingestion bursts. Mitigation: split cocoindex out then.

---

## Anti-Patterns

### Anti-Pattern 1: Running Cocoindex in Multiple Uvicorn Workers

**What people do:** `uvicorn app.main:app --workers 4` with cocoindex initialized in each worker.
**Why it's wrong:** Cocoindex's `FlowLiveUpdater` will start 4 times, each processing the same Postgres NOTIFY events → duplicate work and possible deadlock.
**Do this instead:** Either (a) run uvicorn with 1 worker + asyncio concurrency (sufficient for M2), or (b) gate cocoindex init behind worker ID (`if os.getenv("WORKER_ID") == "0"`), or (c) move cocoindex to a separate container (defer to scale phase).

### Anti-Pattern 2: Calling Cocoindex from Query Path

**What people do:** Search handler invokes cocoindex API to "retrieve."
**Why it's wrong:** Cocoindex is an indexing framework, not a query engine. Adds latency, complexity, and couples query schema to flow definition.
**Do this instead:** Query pgvector directly with SQL. Cocoindex only populates `chunks`; queries are independent.

### Anti-Pattern 3: Using LocalFile Source for User Uploads

**What people do:** Drop uploaded files into a watched folder and let cocoindex's LocalFile source discover them.
**Why it's wrong:** Race condition (file partially written), no way to attach metadata (hub_id, uploader), polling overhead.
**Do this instead:** Use Postgres source with LISTEN/NOTIFY. File path is a column; metadata is in the row; trigger is push-based.

### Anti-Pattern 4: Mixing Cocoindex State with App Schema

**What people do:** Put `COCOINDEX_DATABASE_URL` pointing to the same DB as app data.
**Why it's wrong:** Cocoindex creates its own tracking tables (`__cocoindex_lineage`, `__cocoindex_state`); these pollute app schema; Alembic migrations may conflict; rollback risk.
**Do this instead:** Same Postgres instance, separate logical DB (e.g. `medinet_central` for app, `medinet_cocoindex` for cocoindex state). Use a single `pgvector/pgvector:pg16` container with two DBs created at init.

### Anti-Pattern 5: Putting Heavy Extract in Async Endpoint

**What people do:** `POST /api/documents/upload` extracts text synchronously before returning 200.
**Why it's wrong:** Request can take 30+ seconds; user sees timeout; doesn't scale.
**Do this instead:** Save file + INSERT row + return 202 immediately. Cocoindex picks up via NOTIFY. Frontend polls status (existing pattern).

### Anti-Pattern 6: Storing JWT Keys in App/

**What people do:** `api/app/keys/private.pem` and import directly.
**Why it's wrong:** Keys ship in Docker image if not careful; gitignore must be precise.
**Do this instead:** `api/keys/` outside `app/` (mounted as Docker volume in prod). `.dockerignore` excludes `keys/`.

---

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| **OpenAI / Gemini** | LiteLLM (`litellm.acompletion`, `litellm.aembedding`). API keys from `settings` table (AES-encrypted). | Replaces 4 Go files (`embedding/openai.go`, `embedding/gemini.go`, `llm/openai.go`, `llm/gemini.go`). LiteLLM handles retries + 429 backoff natively. |
| **Postgres + pgvector** | Two roles: (1) app data via SQLAlchemy async; (2) cocoindex state via cocoindex's own connector. Both point to same container, different DBs. | Image: `pgvector/pgvector:pg16` (replaces `postgres:16-alpine`). Init script creates 2 DBs + `CREATE EXTENSION vector` in `medinet_central`. |
| **Redis 7** | Same use cases as M1: rate-limit, JWT blacklist, search cache, usage realtime. | Library: `redis-py` async (`redis.asyncio`). Server can run without Redis (graceful degrade) — same as M1. |
| **File storage (local)** | Mount host volume into container at `/uploads`. Path stored in `documents.file_path`. | `pathlib.Path` ops; no async file I/O needed at this scale. |
| **File storage (GCS, deferred)** | `google-cloud-storage` Python SDK; same `FileStore` interface. | Out of M2 scope per Constraints. |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| **FastAPI handler ↔ Service** | Function call within process | Standard async function injection via `Depends()` |
| **Service ↔ Repository** | SQLAlchemy `AsyncSession` injection | Repo returns ORM model or Pydantic DTO |
| **FastAPI ↔ Cocoindex** | **Postgres `documents` table (LISTEN/NOTIFY)** — NOT direct function calls | This is the critical decoupling: FastAPI never calls cocoindex code; cocoindex picks up DB changes |
| **Cocoindex ↔ pgvector** | cocoindex `targets.Postgres` writes `chunks` | Cocoindex owns this schema (`chunk_id`, `embedding`, etc.); app reads via SQL |
| **Search ↔ pgvector** | Raw SQL via SQLAlchemy `text()` | Bypasses cocoindex entirely; query path is independent |
| **Audit ↔ Postgres** | Async background task → batched INSERT | Mirrors current Go UsageLogger; in-memory buffer (acceptable for M2) |
| **Frontend ↔ FastAPI** | HTTPS, `/api/*` paths preserved exactly | Nginx or FastAPI mounting at port 8080. Frontend zero changes (D6). |

---

## Migration Path (Concrete Phase Order for Roadmapper)

**Goal:** 10-15 phases. Below are 12 with explicit dependencies + parallelization opportunities.

### Phase 1 — Skeleton + Demolition (sequential, blocking)
- **New:** `api/` directory with empty `app/main.py`, `pyproject.toml`, `Dockerfile`, `alembic.ini`. Health endpoint `GET /api/health` returning `{"status":"ok"}`.
- **Modified:** `docker-compose.yml` — replace `chromadb` + `docling-pipeline` services with `pgvector/pgvector:pg16` (replacing `postgres:16-alpine`) and `python-api` (new). Keep `redis` as-is.
- **Deleted:** `chroma_data/`, `docling-pipeline/`, `backend/chroma_data/`, `backend/uploads/` references in compose.
- **Frontend impact:** None yet (old Go backend still running in parallel during transition).
- **Exit criteria:** `docker compose up` shows postgres+pgvector + redis healthy; `curl /api/health` returns 200.

### Phase 2 — Database Schema + Migrations (sequential, blocks 3-7)
- **New:** Alembic init; migrations `001_init` (users, hubs, refresh_tokens, api_keys, settings) and `002_wiki` (documents, chunks with `vector(1536)` column + HNSW index) and `003_audit` (audit_logs, usage_events).
- **Schema decisions:**
  - `chunks.embedding vector(N)` where N = configured embedding dim (default 1536 for `text-embedding-3-small`).
  - `chunks.hub_id`, `chunks.doc_id`, `chunks.chunk_idx`, `chunks.content TEXT`, `chunks.metadata JSONB`.
  - HNSW index: `CREATE INDEX chunks_emb_hub ON chunks USING hnsw (embedding vector_cosine_ops) WHERE hub_id IS NOT NULL`.
  - Drop M1 chroma-only columns from `documents` (`chroma_collection`, `extractor_used`).
- **Frontend impact:** None.

### Phase 3 — Auth Port (parallel-able with Phase 4 after Phase 2 done)
- **New:** `app/auth/` with `router.py`, `service.py`, `jwt.py`, `argon2.py`, `deps.py`. Endpoints: `POST /api/auth/login`, `/refresh`, `/logout`, `GET /api/auth/me`.
- **Reuse:** `backend/keys/private.pem` + `public.pem` → moved to `api/keys/`. Same RS256 algorithm → existing tokens still verify (constraint).
- **Critical:** Port Argon2 params exactly (memory, iterations, parallelism) from `pkg/hash/argon2.go` so existing user passwords still verify.
- **Frontend impact:** First URL compatibility test. `frontend/src/services/api.ts` already points to `:8080` — if FastAPI binds 8080 and old Go is moved to another port, frontend works against new auth.
- **Tests:** unit (jwt sign/verify, argon2 verify with M1 hash), integration (login → refresh → me → logout).

### Phase 4 — Cocoindex Flow MVP (parallel-able with Phase 3 after Phase 2 done)
- **New:** `app/rag/flow.py` with `medinet_ingest_flow` using `Postgres` source (LISTEN/NOTIFY) → extract (DOCX via python-docx, PDF via pypdf text-only, TXT/MD passthrough) → `SplitRecursively` chunk → LiteLLM embed (Gemini default) → `targets.Postgres(chunks)`.
- **New:** `app/rag/embeddings.py` (LiteLLM wrapper).
- **New:** Cocoindex initialization in `app/main.py` lifespan. `COCOINDEX_DATABASE_URL` env added.
- **Modified:** `docker-compose.yml` — add init script to create second DB `medinet_cocoindex` on same Postgres.
- **Frontend impact:** None (no upload endpoint yet).
- **Note for roadmapper:** This phase is independent of auth; a second dev can take this in parallel.
- **Exit criteria:** Manual `INSERT INTO documents (...)` triggers cocoindex flow; `chunks` table populated; verify with `SELECT COUNT(*) FROM chunks`.

### Phase 5 — Hub + User + Document CRUD (depends on Phase 3 auth)
- **New:** `app/hubs/`, `app/users/`, `app/documents/` — routers + services + repos.
- **Endpoints:** `/api/hubs` (CRUD admin), `/api/users` (CRUD admin), `/api/documents/upload`, `/api/documents/:id/status`, `/api/documents/:id` (GET/DELETE), `/api/documents?hub_id=...`.
- **Document upload service:** save file → INSERT row → cocoindex picks up via NOTIFY (from Phase 4). Returns 202 with `document_id`.
- **Frontend impact:** Hub registry, user management, document ingestion pages should function end-to-end against new backend.
- **Tests:** integration test "upload doc → poll status → expect chunks count > 0" (validates Phase 4 + Phase 5 together).

### Phase 6 — Search Endpoint (depends on Phase 4)
- **New:** `app/rag/search.py`, `app/rag/router.py` with `GET /api/search`, `POST /api/search/cross-hub`.
- **Logic:** embed query → pgvector ANN with `hub_id` filter (or IN-list for cross-hub) → Redis cache.
- **Frontend impact:** CrossHubSearch.tsx works.

### Phase 7 — Ask Endpoint + LiteLLM Streaming (depends on Phase 6)
- **New:** `app/rag/ask.py` with `POST /api/ask`. LiteLLM `acompletion(stream=True)` → SSE via FastAPI `StreamingResponse`.
- **Citation injection:** prompt includes `[src:<chunk_id>]` markers; post-process to build citations array sent at stream end.
- **New:** `PUT /api/rag-config` for hot-swap (provider + key + model + chunk params).
- **Frontend impact:** Settings page works for hot-swap; CitationText.tsx renders properly.

### Phase 8 — Audit + API Keys + Misc (parallel-able with Phase 7)
- **New:** `app/audit/`, `app/apikeys/`, `app/settings_store/`.
- **Endpoints:** `/api/audit-logs`, `/api/api-keys`, `/api/system-settings`.
- **Audit logger:** in-memory queue + asyncio batch flush every 2s.
- **Frontend impact:** AuditLog.tsx, APIKeyManagement.tsx, Settings.tsx work.

### Phase 9 — Frontend End-to-End Smoke Test (depends on 3-8)
- **No new code in `api/` — verification only.**
- **Activities:** Boot full new stack; run every frontend page; verify all `/api/*` calls succeed with same envelope `{success, data, error, meta}` as Go backend.
- **Modified (if needed):** Backwards-compat shims for any URL/payload drift discovered.
- **Frontend impact:** Confirm D6 constraint met (zero frontend changes).

### Phase 10 — Eval Framework + Quality Gate (depends on Phase 7)
- **New:** `eval/queries.jsonl` (port semantically from M1), `eval/dataset/` (10 Vietnamese medical files), `eval/run_eval.py` (pytest), `eval/metrics.py`.
- **Gate:** ≥75% top-3 retrieval recall. **Roadmap-critical:** if gate fails, iterate chunker/embed params in this phase before tear-down.

### Phase 11 — Tear-Down Old Go Backend (depends on 9 + 10 PASS)
- **Deleted:** `backend/` directory entirely. `backend/keys/` already moved to `api/keys/` in Phase 3.
- **Deleted:** old `docker-compose` references to backend.
- **Modified:** root `.gitignore`, `Makefile` (if any) → all point to `api/`.
- **Frontend impact:** None (frontend has been on new backend since Phase 9).

### Phase 12 — Hardening (parallel-able internally)
- Structured logging (JSON), Prometheus metrics endpoint, error tracking placeholder, OpenAPI tags polished, integration test suite filled out, Docker image size optimization.

### Parallelization Map (for roadmapper)

```
Phase 1 (skeleton) ─┐
                    ├─→ Phase 2 (schema) ─┬─→ Phase 3 (auth) ─┐
                                          │                   ├─→ Phase 5 (hub/user/doc) ─┐
                                          └─→ Phase 4 (cocoindex flow) ─┐                 │
                                                                        ├─→ Phase 6 (search) ─→ Phase 7 (ask)
                                                                                            │
                                                                        Phase 8 (audit) ────┤
                                                                                            │
                                                                        Phase 9 (FE smoke) ─┤
                                                                        Phase 10 (eval) ────┤
                                                                                            ▼
                                                                                  Phase 11 (tear-down)
                                                                                            │
                                                                                            ▼
                                                                                  Phase 12 (hardening)
```

**Parallel opportunities (2-dev allocation):**
- Dev A: 3 (auth) → 5 (CRUD) → 8 (audit) → 9 (FE smoke)
- Dev B: 4 (cocoindex) → 6 (search) → 7 (ask) → 10 (eval)
- Phases 1, 2, 11, 12 = sequential checkpoints.

---

## Docker Compose Proposal (Phase 1 deliverable)

```yaml
services:
  postgres:
    image: pgvector/pgvector:pg16                   # CHANGED from postgres:16-alpine
    container_name: medinet-postgres
    environment:
      POSTGRES_DB: medinet_central
      POSTGRES_USER: medinet
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - ./postgres_data:/var/lib/postgresql/data
      - ./scripts/init_dbs.sql:/docker-entrypoint-initdb.d/init.sql:ro   # NEW: create medinet_cocoindex DB + CREATE EXTENSION vector
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U medinet -d medinet_central"]
      interval: 10s

  redis:
    image: redis:7-alpine                            # UNCHANGED
    # ... same as M1 ...

  api:                                               # NEW (replaces chromadb + docling-pipeline)
    build:
      context: ./api
      dockerfile: Dockerfile
    container_name: medinet-api
    environment:
      DATABASE_URL: postgresql+asyncpg://medinet:${POSTGRES_PASSWORD}@postgres:5432/medinet_central
      COCOINDEX_DATABASE_URL: postgresql://medinet:${POSTGRES_PASSWORD}@postgres:5432/medinet_cocoindex
      REDIS_URL: redis://redis:6379/0
      JWT_PRIVATE_KEY_PATH: /keys/private.pem
      JWT_PUBLIC_KEY_PATH: /keys/public.pem
      OPENAI_API_KEY: ${OPENAI_API_KEY}
      GEMINI_API_KEY: ${GEMINI_API_KEY}
      RAG_UPLOAD_DIR: /uploads
    volumes:
      - ./api/keys:/keys:ro
      - ./uploads:/uploads
    ports:
      - "8080:8080"
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy

networks:
  medinet-net:
    driver: bridge
```

**Net change:** 4 services → 3 services. Cocoindex runs inside `api`. No separate worker (M2 scale doesn't justify it; revisit at v4.0 hardening).

---

## Configuration (Phase 1 Env Var Map)

| Old (Go) | New (Python) | Notes |
|---|---|---|
| `DB_HOST` + `DB_PORT` + `DB_NAME` + `DB_USER` + `DB_PASSWORD` | `DATABASE_URL` (single DSN) | SQLAlchemy / asyncpg convention; build via pydantic-settings if separate vars preferred |
| `CHROMA_URL`, `CHROMA_TOKEN` | — (deleted) | |
| — | `COCOINDEX_DATABASE_URL` | NEW — required by cocoindex |
| `REDIS_URL` | `REDIS_URL` | Same |
| `JWT_PRIVATE_KEY_PATH`, `JWT_PUBLIC_KEY_PATH` | Same (path updated to `/keys/...` inside container) | |
| `JWT_ACCESS_TOKEN_TTL`, `JWT_REFRESH_TOKEN_TTL` | Same | |
| `AES_KEY` | Same | For settings encryption |
| `OPENAI_API_KEY`, `GEMINI_API_KEY` | Same (also stored in DB `settings` for runtime override) | |
| `RAG_EMBEDDING_PROVIDER`, `RAG_CHUNK_SIZE`, `RAG_WORKER_COUNT` | Same names; `RAG_WORKER_COUNT` ignored (cocoindex manages) | |
| `RAG_UPLOAD_DIR` | Same | |
| `STORAGE_PROVIDER`, `GDRIVE_*` | Deleted in M2 (local only); add back at v4.0 with `google-cloud-storage` | |
| `APP_ENV`, `APP_PORT` | `APP_ENV`, `APP_PORT` (default 8080) | |
| `CORS_ALLOWED_ORIGINS` | Same | |
| `LOG_LEVEL`, `LOG_FORMAT` | Same (`structlog` JSON) | |

---

## Sources

- [CocoIndex — FastAPI integration example (image_search)](https://cocoindex.io/examples/image_search) — HIGH confidence, official example
- [CocoIndex GitHub — fastapi_server_docker example](https://github.com/cocoindex-io/cocoindex/tree/main/examples/fastapi_server_docker) — HIGH confidence, canonical reference
- [CocoIndex Flow Methods Documentation](https://cocoindex.io/docs/core/flow_methods) — HIGH confidence (FlowLiveUpdater API)
- [CocoIndex Postgres Source with LISTEN/NOTIFY](https://cocoindex.io/docs-v0/examples/postgres_source/) — HIGH confidence, push trigger pattern
- [CocoIndex Settings (COCOINDEX_DATABASE_URL)](https://cocoindex.io/docs/core/settings) — HIGH confidence
- [CocoIndex Custom Sources](https://cocoindex.io/docs-v0/examples/custom_source_hackernews/) — fallback if Postgres source insufficient
- [CocoIndex Docker + pgvector tutorial](https://cocoindex.io/docs/tutorials/docker_pgvector_setup) — HIGH confidence, compose pattern
- [CocoIndex Daemon Architecture (cocoindex-code)](https://cocoindex.io/blogs/building-an-invisible-daemon/) — context for when daemon split helps (NOT for our scale)
- [CocoIndex Concurrency Control](https://cocoindex.io/blogs/flow-control) — sizing for ingestion bursts
- [FastAPI Lifespan Events](https://fastapi.tiangolo.com/advanced/events/) — HIGH confidence, integration pattern
- [LiteLLM Documentation](https://docs.litellm.ai/) — HIGH confidence for provider hot-swap
- Internal: `Hub_All/.planning/PROJECT.md` (M2 goals, decisions D1-D9)
- Internal: `Hub_All/.planning/codebase/ARCHITECTURE.md` (existing Go layered pattern, to replace)
- Internal: `Hub_All/.planning/codebase/STRUCTURE.md` (folder conventions, to mirror)
- Internal: `Hub_All/.planning/codebase/INTEGRATIONS.md` (env vars, external services to port)
- Internal: `Hub_All/docker-compose.yml` (M1 compose, to replace)
- Internal: `Hub_All/backend/cmd/server/main.go` (Go wiring pattern, to port)

---

*Architecture research for: M2 Full RAG Rewrite (Python FastAPI + cocoindex + pgvector)*
*Researched: 2026-05-13*
