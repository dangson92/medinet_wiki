# Research Summary — M2 Full RAG Rewrite

**Dự án:** Medinet Wiki (MEDWIKI) — Hub_All
**Milestone:** v2.0 — Full RAG Rewrite (CocoIndex + Python FastAPI + pgvector)
**Domain:** Brownfield rewrite · Vietnamese medical knowledge wiki · Multi-Hub (3 hubs: y tế / dược / HCNS) · RAG có citation
**Researched:** 2026-05-13
**Confidence tổng:** **MEDIUM-HIGH** (HIGH cho stack/pgvector/FastAPI/auth, MEDIUM cho cocoindex production patterns + Vietnamese chunk quality)
**Downstream consumer:** `gsd-roadmapper` (target **10 phases**, M2a + M2b split)

---

## Executive Summary

M2 là **pivot lần 2 trong 15 ngày** — gỡ toàn bộ Go backend + Docling sidecar + ChromaDB, viết lại bằng **Python 3.12 + FastAPI 0.136 + CocoIndex 1.0.3 + Postgres 16 với pgvector**. Stack đã verify HIGH-confidence trên PyPI/GitHub releases tính đến 2026-05-13. CocoIndex dùng **dạng library in-process** (init trong FastAPI `lifespan` + `FlowLiveUpdater`), KHÔNG dạng daemon riêng — phù hợp scale 100 docs/day và xóa nhu cầu xây worker pool tự custom (Rust scheduler của cocoindex thay thế). Trigger ingestion dùng **Postgres LISTEN/NOTIFY** trên bảng `documents` thay vì file-watcher (push-based, không race condition khi upload, mang theo metadata `hub_id`/`uploaded_by`). Search/Ask **bypass cocoindex hoàn toàn** — query pgvector trực tiếp bằng SQL (`<=>` cosine), giữ latency tối thiểu. LiteLLM 1.82 thay 4 file Go (`embedding/openai`, `embedding/gemini`, `llm/openai`, `llm/gemini`) bằng config-driven hot-swap.

**Khuyến nghị approach:** Lock-in **3 services Docker** (`pgvector/pgvector:pg16` + `redis:7-alpine` + `python-api`), **2 logical DB** trên cùng container Postgres (`medinet_central` cho app data, `medinet_cocoindex` cho cocoindex internal state — tách bằng database để alembic không clash với cocoindex auto-migration). Module layout `api/app/{auth,hubs,users,documents,audit,apikeys,rag,db,middleware,pkg}/` mirror layered pattern Go cũ nhưng group theo bounded context. Embedding dimension **PIN ở 1536** (OpenAI `text-embedding-3-large` với `dimensions=1536` param + Gemini `gemini-embedding-001` ở 1536 mode) để (a) né pgvector index limit 2000, (b) cho phép hot-swap OpenAI↔Gemini KHÔNG re-index. Quality gate **≥75% top-3 tuyệt đối** trên eval set mới (M1 abandoned → không có +15pp delta để so sánh).

**Risk chính & mitigation:** R3 — **Pivot fatigue → pivot 3** (CRITICAL): bake EXIT criteria vào PROJECT.md + chia M2 thành **M2a (Phase 1-4, value đứng độc lập) + M2b (Phase 5-10, RAG completion)**. R1 — pgvector index 2000-dim limit: dùng `dimensions=1536` OpenAI param từ Phase 1 (verify SQL trước khi viết flow). R2 — HNSW post-filter recall collapse khi filter `hub_id`: pin pgvector ≥0.8 + `SET hnsw.iterative_scan = relaxed_order`. R4 — scanned PDF tiếng Việt silent fail: return 415 explicit với enum `failed_unsupported`. Coverage test critical-path bắt buộc (auth + ingest + search + ask + hub isolation) ngay từ Phase 1 — không carry-over 0% coverage của M1.

---

## Key Findings

### Recommended Stack (chi tiết: `STACK.md`)

**Core (pinned versions, HIGH confidence):**

- `python>=3.11,<3.13` (khuyến nghị 3.12)
- `fastapi==0.136.1` + `uvicorn[standard]==0.46.0`
- `cocoindex==1.0.3` — RAG indexing dataflow (Rust core)
- `pgvector==0.4.2` (Python binding) + image `pgvector/pgvector:pg16` (ext ≥0.8)
- `asyncpg==0.30.0` + `sqlalchemy[asyncio]>=2.0.36` + `alembic==1.18.4`
- `litellm>=1.82` — drop-in OpenAI/Gemini hot-swap
- `pyjwt[crypto]>=2.12` — RS256
- `pwdlib[argon2]==0.3.0` + `argon2-cffi>=25.1.0` — Argon2id
- `redis>=7.1.1`
- `structlog>=25` — JSON logging contextvar-aware
- `pypdf>=5.0` + `python-docx==1.2.0` + `markdown-it-py>=3` + `chardet>=5`
- `pytest>=8` + `pytest-asyncio>=0.24` + `httpx>=0.27` + `asgi-lifespan>=2` + `testcontainers`
- Dev: `uv` + `ruff>=0.6` + `mypy>=1.11`

**REJECT (KHÔNG thêm vào pyproject.toml):**

| Reject | Use Instead | Reason |
|---|---|---|
| LangChain / LlamaIndex | CocoIndex + LiteLLM trực tiếp | Quá nhiều abstraction, lock-in |
| SQLModel | SQLAlchemy 2 typed + Pydantic v2 riêng | Abandoned giữa 2024 |
| python-jose | PyJWT | Barely maintained, CVE algorithm confusion |
| passlib | pwdlib | Deprecated (depends on Python `crypt` removed 3.13) |
| ChromaDB | pgvector | D3 |
| Docling | pypdf + python-docx | D4 |
| psycopg2 | asyncpg | Sync only, slow |
| `postgres:16-alpine` plain | `pgvector/pgvector:pg16` | Plain thiếu ext `vector` |

### Feature Categorization (chi tiết: `FEATURES.md`)

**16 Table Stakes (TS-1..TS-16) → 8 bucket cho roadmapper:**

| Bucket | Items | Tóm tắt |
|---|---|---|
| **CORE** | docker-compose 3 services, Alembic baseline, FastAPI skeleton, response envelope | Infra cross-cutting |
| **AUTH** | TS-4, TS-5 | JWT RS256 + Argon2 + login/refresh/me/logout + RBAC |
| **HUB** | TS-6 | Hub registry CRUD với `hub_id` isolation (drop `chroma_collection`) |
| **USER** | TS-7 | User CRUD + role assignment |
| **INGEST** | TS-1, TS-2, TS-3, TS-12 | CocoIndex flow (LISTEN/NOTIFY → extract → chunk → embed → pgvector) + job tracking + incremental diff |
| **SEARCH** | TS-8, TS-10 | Direct SQL `<=>` query + cross-hub `hub_id = ANY($1)` |
| **ASK** | TS-9, TS-11, TS-14 | LiteLLM acompletion + `[src:<chunk_id>]` + hot-swap + token usage |
| **EVAL** | (framework) | `queries.jsonl` + dataset VN medical + gate ≥75% top-3 |

**Phụ trợ:** TS-13 audit log, TS-15 API key mgmt, TS-16 frontend URL compat.

**6 Differentiators:** D-1 incremental re-index free (giải 999.1), D-2 stable chunk_id (citation không rot), D-3 lineage built-in, D-4 3-service compose, D-5 LiteLLM provider-agnostic, D-6 schema auto-evolution.

**Anti-features → Out-of-Scope:** OCR Vietnamese, hybrid BM25, streaming /ask, ChromaDB→pgvector migration, local embedding, comprehensive coverage, WebSocket job progress, GraphQL.

### Architectural Decisions (LOCK-IN — roadmapper KHÔNG re-debate)

1. **In-process CocoIndex (NOT daemon)** — Flow trong `api/app/rag/flow.py`, init+start `FlowLiveUpdater` trong FastAPI `lifespan`. Defer split container đến >1k docs/day (v4.0).
2. **Postgres LISTEN/NOTIFY trigger ingestion** — `cocoindex.sources.Postgres(notification=PostgresNotification(), ordinal_column="updated_at")`. Push-based.
3. **Search/Ask bypass cocoindex** — query path = embed query (LiteLLM) → raw SQL → assemble. Cocoindex chỉ indexing-time.
4. **2 logical DBs trên 1 container Postgres** — `medinet_central` (`public`) + `medinet_cocoindex` (cocoindex internal). NEVER share schema.

**Module layout chốt:**
```
Hub_All/api/
├── pyproject.toml + alembic.ini + Dockerfile
├── keys/                    # JWT PEM (gitignored)
├── app/
│   ├── main.py              # FastAPI factory + lifespan
│   ├── config.py            # pydantic-settings
│   ├── db/
│   ├── auth/                # router + service + jwt + argon2 + deps
│   ├── hubs/ users/ documents/ audit/ apikeys/ settings_store/
│   ├── rag/                 # flow.py (★) + search.py + ask.py + embeddings.py + llm.py
│   ├── middleware/
│   └── pkg/
├── migrations/              # Alembic async
└── tests/
```

**Process model M2:** uvicorn 1-2 workers (cocoindex MUST init exactly once).

### Critical Pitfalls — Watch Out For (top 5)

1. **R1 — pgvector index 2000-dim limit (HIGH):** `text-embedding-3-large` mặc định 3072 → HNSW FAIL → Seq Scan → p95 vỡ. **Mitigation:** `dimensions=1536` API param, verify Phase 1 bằng `CREATE INDEX` trước khi viết flow.

2. **R2 — HNSW post-filter recall collapse trên `hub_id` (HIGH):** pgvector không push down predicate → top-K bằng similarity TRƯỚC rồi filter SAU → hub khác leak hoặc results trống. **Mitigation:** pgvector ≥0.8 + `SET hnsw.iterative_scan = relaxed_order` + `SET hnsw.max_scan_tuples = 20000`. Measure recall WITH filter Phase 9 eval.

3. **R3 — Pivot fatigue → pivot 3 (CRITICAL):** M1 abandoned 2026-05-13, pivot 2 trong 15 ngày. **Mitigation:** EXIT criteria vào PROJECT.md (cocoindex critical bug no-fix 14 days; pgvector p95 >2000ms ở 50K chunks dù tune; Phase 1-3 vượt 21 ngày; hub isolation bug không fixable) + **split M2a (Phase 1-4) / M2b (Phase 5-10)** + weekly check-in day 7/14/21/28 + NO new tool adoption mid-flight.

4. **R4 — Scanned PDF tiếng Việt silent fail (HIGH):** D4 gỡ Docling → pypdf trên scanned PDF trả empty → `status='completed'` nhưng `chunk_count=0`. **Mitigation:** Explicit whitelist `{.docx, .txt, .md, .pdf}` + detect scanned PDF post-extract → enum `failed_unsupported` riêng (khác `failed`) + frontend message "chuyển sang DOCX" thay vì retry.

5. **CocoIndex naming + schema mix (HIGH debug waste):** Cocoindex lowercase mọi flow/target name + `APP_NAMESPACE` prefix → bảng "biến mất" pgAdmin. **Mitigation:** Tên flow snake_case (`name="medinet_wiki_ingest"`), `APP_NAMESPACE=medinet_prod` cố định trong `.env.example`, `db_schema_name="cocoindex"` tách `public`, alembic include_object filter ignore cocoindex tables, document tên thực tế trong CONVENTIONS.md.

**Risk → Phase mapping:** R1 → Phase 1+4, R2 → Phase 6+9, R3 → Phase 1 (PROJECT.md update), R4 → Phase 4+8. 16 pitfall còn lại (P5-P20) chi tiết trong `PITFALLS.md`.

---

## Roadmap Implications

### Phase Count Reconciliation: 8 vs 12 → **10 phases**, split M2a/M2b

FEATURES suggest 8, ARCHITECTURE suggest 12. Synthesize → **10**:
- Merge ARCHITECTURE Phase 0 (conventions + EXIT criteria) vào Phase 1
- Keep 4 core RAG phases (cocoindex flow, search, ask, eval)
- Merge audit/apikeys vào CRUD phase parallel
- Tear-down Go backend phase tách riêng (sau frontend smoke)
- Hardening = phase cuối

### Suggested 10 Phases (cho roadmapper)

| # | Phase | Depends on | Parallel-able with | Research flag |
|---|---|---|---|---|
| 1 | **Infra Skeleton + Demolition + EXIT Criteria** | — | (sequential, blocking) | LOW |
| 2 | **Database Schema + Alembic Baseline** | 1 | (sequential) | LOW |
| 3 | **Auth Port + RBAC + Response Envelope** | 2 | Phase 4 | **MEDIUM** (Argon2 cross-compat empirical) |
| 4 | **CocoIndex Flow MVP + Document Ingest** ★ | 2 | Phase 3 | **HIGH** (augmenter, PDF table, VN chunking) |
| — | **🚦 M2a EXIT GATE** — demo upload→chunks→SELECT verify. Reject → STOP, không pivot 3 | After 4 | — | — |
| 5 | **Hub + User + Audit + APIKey CRUD** | 3 | Phase 6 | LOW |
| 6 | **Search API (Single + Cross-Hub)** | 4 | Phase 5 | LOW |
| 7 | **Ask API + LiteLLM + Citation + Hot-Swap** | 6 | — | **MEDIUM** (memo cache invalidation) |
| 8 | **Frontend E2E Smoke + Tear-down Old Go Backend** | 3-7 | — | LOW |
| 9 | **Eval Framework + Quality Gate ≥75% top-3** | 7 | Phase 10 | **MEDIUM** (dim 1536 vs 3072 VN quality) |
| 10 | **Hardening + Observability** | (parallel internally) | Phase 9 | LOW |

**Critical path:** 1 → 2 → 4 → 6 → 7 → 9 → 10. Auth branch (3 → 5 → 8) parallel.

### Open Questions (carry-forward sang REQUIREMENTS.md)

1. **Storage backend** — local default (M2), GDrive port optional → confirm trước Phase 4
2. **JWT keypair format** — PKCS#1 (Go default) vs PKCS#8 — verify `openssl rsa -in private.pem -text -noout` Phase 3, convert nếu cần
3. **Argon2 hash cross-compat Go↔Python** — Phase 3 mandatory test với Go params `m=65536, t=1, p=2, saltLen=16, keyLen=32`
4. **Cocoindex augmenter equivalent** — Go có Q&A pair gen. Default skip M2, defer v4.0 (giảm scope) trừ khi RTFM Phase 4 chứng minh dễ thêm
5. **PDF table extraction lib** — pdfplumber vs camelot vs accept loss. Test 3 samples Phase 4, ship M2 với accept-loss warning UI nếu cả 2 fail
6. **Embedding dim 1536 vs 3072 quality** — Phase 9 empirical (gate ≥75% confirm choice)
7. **Postgres pg16 vs pg17** — Giữ pg16 M2, upgrade pg17 hardening v4.0

### Quality Gate Configuration

- **Model:** `text-embedding-3-large @ dimensions=1536` + cocoindex `RecursiveSplitter` VN regex + `gpt-4o-mini` answerer
- **Threshold:** ≥75% top-3 retrieval WITH `hub_id` filter (KHÔNG có +15pp delta vì M1 abandoned)
- **Dataset:** 10 file VN medical + 12 queries (port semantically từ M1 archive `eval/`)
- **Metrics:** top-1/3/5 recall, MRR, latency p50/p95/p99
- **Pass action:** declare M2 complete
- **Fail action:** iterate chunker/prompt **trong Phase 9**, KHÔNG pivot

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack (versions, library choice) | **HIGH** | Verified PyPI/GitHub 2026-05-13 |
| Features (table stakes scope) | **HIGH** | Port từ existing Go inventory |
| Features (cocoindex+FastAPI patterns) | **MEDIUM** | Official examples confirm, production refs ít |
| Architecture (in-process + LISTEN/NOTIFY + bypass query) | **HIGH** | Official examples confirm |
| Architecture (migration ordering, parallelization) | **MEDIUM** | Project-specific judgment |
| Pitfalls (pgvector + auth + alembic) | **HIGH** | Battle-tested community knowledge |
| Pitfalls (cocoindex specifics) | **MEDIUM** | Small community, memo cache cần empirical |
| Vietnamese-specific quality | **LOW** | No cocoindex VN-specific docs; empirical Phase 4+9 |

**Overall: MEDIUM-HIGH** — đủ để start roadmap với 10 phases.

### Gaps to Address

| Gap | Phase to Validate | Mitigation Plan |
|---|---|---|
| Cocoindex augmenter parity | Phase 4 RTFM | Default skip M2, defer v4.0 |
| Argon2 cross-compat | Phase 3 integration test | Pin pwdlib params Go-compat; fail-fast mismatch |
| PDF table extraction VN | Phase 4 sample 3 docs | Ship M2 với accept-loss warning UI |
| Embedding dim 1536 quality | Phase 9 eval gate | Iterate prompt/chunker nếu <75% |
| Cocoindex wheel Windows | Phase 1 smoke `pip install` | WSL2 hoặc Docker dev container nếu fail |
| Vietnamese chunk boundary | Phase 4 + 9 sample 10 chunks | Custom regex + iterate if eval fails |

---

## Sources

### Primary (HIGH confidence — Context7 + PyPI + official docs verified 2026-05-13)

**Cocoindex:**
- [cocoindex releases](https://github.com/cocoindex-io/cocoindex/releases) — v1.0.3 (2026-05-05)
- [Settings docs](https://cocoindex.io/docs/core/settings) — db_schema_name, app_namespace
- [Flow definition](https://cocoindex.io/docs/core/flow_def)
- [Docker + pgvector tutorial](https://cocoindex.io/docs/tutorials/docker_pgvector_setup)
- [Postgres source LISTEN/NOTIFY](https://cocoindex.io/docs-v0/examples/postgres_source/)
- [fastapi_server_docker example](https://github.com/cocoindex-io/cocoindex/tree/main/examples/fastapi_server_docker)
- [image_search example](https://cocoindex.io/examples/image_search)

**FastAPI ecosystem:**
- [Release notes](https://fastapi.tiangolo.com/release-notes/) — v0.136.1
- [Lifespan events](https://fastapi.tiangolo.com/advanced/events/)
- [OAuth2 JWT tutorial](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/)
- [pwdlib migration PR #13917](https://github.com/fastapi/fastapi/pull/13917)
- [Alembic 1.18.4 changelog](https://alembic.sqlalchemy.org/en/latest/changelog.html)

**pgvector:**
- [0.8.0 release](https://www.postgresql.org/about/news/pgvector-080-released-2952/)
- [AWS Aurora benchmarks](https://aws.amazon.com/blogs/database/supercharging-vector-search-performance-and-relevance-with-pgvector-0-8-0-on-amazon-aurora-postgresql/)
- [Issue #461 dim limit](https://github.com/pgvector/pgvector/issues/461)
- [Issue #259 HNSW filter](https://github.com/pgvector/pgvector/issues/259)

**Auth + crypto:**
- [PyJWT](https://pypi.org/project/PyJWT/) v2.12+
- [pwdlib](https://pypi.org/project/pwdlib/) v0.3.0
- [alexedwards/argon2id Go](https://github.com/alexedwards/argon2id)

**LiteLLM:** [docs](https://docs.litellm.ai/)

**Multi-tenancy pgvector:**
- [Tigerdata multi-tenant RAG](https://www.tigerdata.com/blog/building-multi-tenant-rag-applications-with-postgresql-choosing-the-right-approach)
- [Nile multi-tenant RAG](https://www.thenile.dev/blog/multi-tenant-rag)

### Secondary (MEDIUM confidence)

- [Gin vs FastAPI middleware](https://leapcell.io/blog/unraveling-middleware-execution-in-gin-and-fastapi)
- [testcontainers + asyncpg](https://lealre.github.io/fastapi-testcontainer-asyncpg/)
- [FastAPI + SQLA 2 + asyncpg benchmarks](https://leapcell.io/blog/building-high-performance-async-apis-with-fastapi-sqlalchemy-2-0-and-asyncpg)
- [PDF extractor benchmark 2026](https://onlyoneaman.medium.com/i-tested-7-python-pdf-extractors-so-you-dont-have-to-2025-edition-c88013922257)
- [text-embedding-3-large dimensions](https://community.openai.com/t/text-embedding-3-large-at-256-or-3072-dimensions/966400)

### Project-internal references

- `.planning/PROJECT.md` — M2 goals, D1-D9
- `.planning/MILESTONES.md` — M1 abandoned
- `.planning/research/{STACK,FEATURES,ARCHITECTURE,PITFALLS}.md` — chi tiết đầy đủ

---

*Synthesized 2026-05-13 từ 4 parallel research agents (STACK / FEATURES / ARCHITECTURE / PITFALLS).*
