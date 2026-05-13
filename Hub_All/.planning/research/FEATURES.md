# Feature Research — M2 Full RAG Rewrite (CocoIndex + FastAPI + pgvector)

**Domain:** Internal Vietnamese medical knowledge wiki — multi-Hub RAG (3 hubs: y tế / dược / HCNS), brownfield rewrite from Go+ChromaDB+Docling to Python+cocoindex+pgvector
**Researched:** 2026-05-13
**Confidence:** HIGH for cocoindex/LiteLLM/pgvector mechanics (Context7 + official docs verified), MEDIUM for operational patterns (cocoindex + FastAPI integration pattern is recent, few production references), LOW for "what users-of-Medinet expect" — bypassed because M2 is a port of an existing brownfield product, not a greenfield discovery

---

## Scope Note (read before everything else)

This milestone is a **stack rewrite**, not a feature discovery. The 13-page React frontend and the Go feature inventory in `PROJECT.md` already define what users expect:

- Auth (login/refresh/logout/me, RBAC admin/editor/viewer)
- Hub registry CRUD with `hub_id` isolation
- User management CRUD
- Document ingestion (upload → extract → chunk → embed → vector store) with async progress
- Search (single-hub + cross-hub, top-k, metadata filter)
- Ask (LLM answerer with `[src:<chunk_id>]` citations, cross-hub)
- Audit log + token usage tracking + API key management
- Provider hot-swap (embedding + LLM) at runtime via `PUT /api/rag-config`

This file does NOT re-validate those — they are PORTING REQUIREMENTS, listed under "Existing → ported" below. Instead, this file enumerates **what's NEW or what changes mechanically** because of D1 (Go→Python), D2 (cocoindex), D3 (pgvector), D5 (LiteLLM).

The question that drives this research: *"Given a fixed feature set that already exists in Go, which features become natural / cheap / hard / impossible in the new stack, and which behaviors change visibly to end users?"*

---

## Feature Landscape

### Table Stakes (must ship in M2 — RAG doesn't work without these)

| # | Feature | Why Required | Complexity | Cocoindex/Pgvector Specifics |
|---|---------|--------------|------------|------------------------------|
| TS-1 | **Cocoindex flow definition** — single `@coco.fn` `app_main` chaining source (`localfs.walk_dir`) → file processor (`@coco.fn(memo=True)`) → chunk splitter (`RecursiveSplitter`) → per-chunk processor (`@coco.fn`) → `postgres.mount_table_target` with `declare_vector_index` | This IS the indexing pipeline. Without a flow, nothing reaches pgvector. | MEDIUM | Cocoindex is dataflow-as-code. The flow is committed Python — same code path is reused by query handlers via `@coco.transform_flow()` to guarantee index/query embedding consistency. |
| TS-2 | **pgvector schema with `hub_id` isolation** — single `chunks` table with `hub_id`, `document_id`, `chunk_id` (deterministic via `generate_id`), `text`, `embedding vector(N)`, `metadata jsonb`. HNSW index on `embedding` + B-tree index on `hub_id` | Multi-tenancy = core product feature. 3 hubs must not bleed into each other. | MEDIUM | See "Multi-tenancy decision" section below. Single table + `hub_id` filter + pgvector 0.8 `iterative_scan=relaxed` is the recommended pattern for ≤50 tenants. |
| TS-3 | **Incremental re-index on source content change** (replaces backlog 999.1) — when document text changes, only changed chunks re-embed; unchanged chunks keep their `chunk_id` AND skip the embedding API call | This is THE M2 differentiator from M1. Replaces the entire 999.1 backlog item with cocoindex-native behavior. Cost savings: ~80%+ embedding tokens on edits. | LOW (cocoindex does it) | `@coco.fn(memo=True)` + `generate_id(chunk.content)` deliver this for free. Memo cache keyed on `hash(input) + hash(function code)`. When `chunk.text` unchanged → `chunk_id` deterministic → embedding cached → pgvector row untouched. When content changes → only affected `chunk_id`s recomputed; cocoindex computes the diff against existing target rows by primary key. |
| TS-4 | **FastAPI auth: JWT RS256 + Argon2 + login/refresh/me/logout** — port from Go `pkg/jwt` + `pkg/hash/argon2`. Reuse existing keypair at `backend/keys/`. | Frontend hits `/api/auth/login` etc. URLs must be byte-identical. | LOW | `python-jose[cryptography]` for RS256, `passlib[argon2]` for password hash, `OAuth2PasswordBearer` + `Depends(get_current_user)` for the dependency chain. Standard FastAPI security pattern. |
| TS-5 | **RBAC middleware** — `Depends(require_role("admin"))`-style guards on hub CRUD, user mgmt, settings endpoints | Existing 3-role model (admin/editor/viewer) must survive port. | LOW | FastAPI dependency-injection pattern; can be done as `OAuth2PasswordBearer` + `SecurityScopes` or simpler `Depends(require_role)` factory returning a callable. |
| TS-6 | **Hub registry CRUD with `hub_id`** — port `hubs` table CRUD endpoints. Drop `chroma_collection` column (D3). | Existing schema/UI relies on it. | LOW | Plain SQL via asyncpg / SQLAlchemy 2.0 async. No cocoindex involvement (cocoindex doesn't own this table). |
| TS-7 | **User management CRUD** — port from Go. | Existing UI page `UserManagement.tsx` calls these endpoints. | LOW | Standard FastAPI CRUD. |
| TS-8 | **Vector search `/api/search`** — embed query through SAME transform_flow used at index time, then `SELECT ... ORDER BY embedding <=> $query_vec LIMIT k` with `WHERE hub_id = $1` (or `IN (...)` for cross-hub). Apply `min_score` post-filter. | Core retrieval. | MEDIUM | `@coco.transform_flow()` guarantees the embedder used at query is the same as at index. Must `SET hnsw.iterative_scan = relaxed_order` per-session or per-pool to avoid recall collapse when filtering by `hub_id`. |
| TS-9 | **LLM answerer `/api/ask` with `[src:<chunk_id>]` citation** — pass retrieved chunks to LLM via LiteLLM `completion()`, instruct model to inline `[src:<chunk_id>]` markers, parse markers post-generation, return both `answer` and `citations[]` to frontend. | Citation is the product. Without `[src:<chunk_id>]` the answer is uncited and `components/CitationText.tsx` won't render `[N]` superscripts. | MEDIUM | LiteLLM `completion(model="gemini/gemini-2.0-flash-lite" \| "openai/gpt-4o-mini", messages=[...])` is provider-agnostic. The `chunk_id` is the cocoindex-generated deterministic ID (TS-3) — stable across re-indexes for unchanged chunks. |
| TS-10 | **Cross-hub search** — `POST /api/search/cross-hub` with `hub_ids: [1, 2, 3]`. Single SQL query with `WHERE hub_id = ANY($1)`, aggregate, top-k overall. | Existing UI page `CrossHubSearch.tsx`. | LOW | One pgvector query with `ANY` array; cocoindex doesn't intermediate. Performance better than current Go (which did N collection queries to ChromaDB and merged in app code) — now it's a single index seek per pgvector partition. |
| TS-11 | **Embedding & LLM provider hot-swap via `PUT /api/rag-config`** | Existing Go feature; admin expectation. M2 cannot regress this. | MEDIUM-HIGH | **See "Hot-swap with cocoindex" section** — the implementation pattern differs significantly from Go. LiteLLM model selection is read from settings table at every `completion()` call → trivially hot-swappable. Embedding swap is harder because cocoindex's `Annotated[NDArray, EMBEDDER]` schema binds dimension at flow build time. Switching from 1536-dim to 3072-dim = schema change = full re-index. Switching WITHIN the same dimension (e.g., OpenAI 3-large 3072 ↔ Gemini gemini-embedding-001 3072) is possible without re-index by reading provider+key from the `EMBEDDER` ContextKey at each `_embedder.embed()` call. |
| TS-12 | **Async ingestion job tracking** — frontend polls `GET /api/documents/:id/status` for `pending → processing → completed/failed` | Existing UI page `DocumentIngestion.tsx` expects this contract. | MEDIUM | Cocoindex live mode (`app.update(live=True).watch()`) yields snapshots with stats, but does NOT expose per-document granularity by default. Bridge pattern: maintain a `documents.status` column updated by a wrapper `@coco.fn(memo=False)` that writes status before/after `process_file`, OR poll cocoindex's exposed metrics. **Recommend the wrapper pattern** — simpler, gives FastAPI direct DB-level read for polling endpoint. |
| TS-13 | **Audit log** — port existing `audit_logs` table + insert hooks on hub/user/document/settings mutations | Existing compliance requirement. | LOW | Plain asyncpg insert in service layer. Not cocoindex-related. |
| TS-14 | **Token usage logging** — port async batched `usage_events` insert from Go | Existing dashboard `TokenUsage.tsx`. | MEDIUM | LiteLLM exposes `response.usage` (prompt_tokens, completion_tokens, total_tokens) per call. Wrap LiteLLM calls in a helper that records to `usage_events` via FastAPI `BackgroundTasks` or an `asyncio.Queue`. The Go-style 16384-buffer + CopyFrom batcher is overkill for M2's load — replace with simple `BackgroundTasks` per call, defer the batcher to v4.0 hardening. |
| TS-15 | **API key management** — port existing CRUD | Existing feature. | LOW | Plain CRUD. |
| TS-16 | **Frontend URL compatibility** — every endpoint listed in `frontend/src/services/api.ts` must respond at same path with same envelope `{success, data, error, meta}` | D6: NO frontend changes in M2. | LOW (per-endpoint) but HIGH (total) | FastAPI response model wrapper + nginx routing or FastAPI app mount on port `:8180` (current Go port). Audit `api.ts` to enumerate every URL — non-trivial in headcount but mechanical. |

### Differentiators (M2 strengths vs M1 Go stack)

| # | Feature | Value Proposition | Complexity | Notes |
|---|---------|-------------------|------------|-------|
| D-1 | **Content-hash incremental re-index** (= TS-3, but as a differentiator) | M1's 999.1 backlog was estimated as a multi-day custom build on top of Go pipeline. In M2 it ships day-1 via `@coco.fn(memo=True)`. When user clicks "Sửa nội dung" → upload new version → only diff chunks re-embed. Cost: ~80% reduction in embedding API spend on document edits. UX: edit operations finish in seconds instead of minutes for long PDFs. | LOW (built-in) | Test plan must include "edit same doc twice, assert embedding API call count = chunks_changed not chunks_total". |
| D-2 | **Stable `chunk_id` for citations across re-index** | When document is edited, OLD citation links `[src:abc123]` referenced from saved answers / external sources REMAIN VALID if the cited chunk's text didn't change. This was BROKEN in M1 (every re-ingest = new UUIDs = stale citations). | LOW (built-in) | Driven by `await generate_id(chunk.text)` — deterministic hash of normalized content. Citations only break when the actual cited text changes, which is the desired semantic. |
| D-3 | **Built-in data lineage** | Cocoindex tracks `chunk → file → source` automatically. Future feature "show me which source doc produced this chunk" is free, including across nested transforms. | LOW | Surfaces in cocoindex CLI / dashboard. For M2, expose via debug endpoint only — not user-facing yet. |
| D-4 | **3-service Docker Compose** (down from 4: dropped ChromaDB) | One less service to operate; pgvector lives in the Postgres we already run. Reduces ops surface area. | LOW | `docker-compose.yml` = `postgres+pgvector` + `redis` + `python-api`. |
| D-5 | **Provider-agnostic LLM via LiteLLM** | Switching between Gemini / OpenAI / future Anthropic Claude / future local model is a 1-line config change (`model="anthropic/claude-..."`). M1 required writing a new Go provider client per vendor. | LOW (LiteLLM does it) | Confirmed for streaming `acompletion(..., stream=True)` over async generator. |
| D-6 | **Schema auto-evolution** | When the `DocEmbedding` dataclass gets a new field (e.g., `language`, `section_path`), cocoindex tries `ALTER TABLE` non-destructively before falling back to drop+recreate. M1 needed manual SQL migrations for every chunk metadata addition. | LOW (built-in) | Caveat: ANY change to embedding dimension = drop+recreate = full re-index (intentional, can't reuse 1536-dim cache for 3072-dim model). |

### Anti-Features (commonly tempting in this rewrite, but should NOT ship in M2)

| Anti-Feature | Why Tempting | Why Problematic in M2 | What to Do Instead |
|--------------|--------------|----------------------|---------------------|
| **OCR Vietnamese for scanned PDF via cocoindex custom function wrapping `pytesseract`** | M1 had it via Docling+Tesseract `vie+eng`. Users uploaded scanned protocols. Losing it feels like regression. | (a) D4 explicitly drops Docling. (b) Tesseract binary in Docker doubles image size; Tesseract Python is slow and inaccurate without Docling's pre-processing. (c) Quality gate ≥75% top-3 is achievable on text-only PDFs without OCR — opening the OCR rabbit hole risks missing the milestone. | M2 ships supporting **DOCX / TXT / MD / PDF text-only**. Scanned PDFs return explicit error `"file looks like scanned PDF — OCR not supported in M2, see v4.0 hardening"`. Documented as known risk in `PROJECT.md` Constraints. Forward-looking design: when revisited (v4.0+), wrap pytesseract in a `@coco.fn(memo=True)` custom function inserted BEFORE the chunker — fits cocoindex's dataflow naturally. |
| **Hybrid BM25 + vector retrieval** | Industry trend (RAG benchmark wins by hybrid). | Adds dependency (pg_trgm or Elasticsearch sidecar), requires reranker tuning, extends scope. Out of M2 scope per `PROJECT.md`. | Defer to v4.0 hardening. pgvector has `tsvector` support natively if hybrid revisited — no new service needed. |
| **Streaming LLM response with mid-stream citation injection** | Modern UX (ChatGPT-style word-by-word with hot citation popovers). | Citation markers `[src:<chunk_id>]` arrive in raw stream from LLM, but parsing them mid-stream while preserving SSE chunk boundaries is non-trivial (markers can span chunks). M1 was non-streaming and shipped fine. | M2 ships **non-streaming** `/api/ask` (matches M1 contract). Streaming `/api/ask/stream` SSE = future enhancement post-M2. When done: buffer until `[src:` is fully received before emitting chunk to client — see implementation pattern in Sources. |
| **Migrate ChromaDB data to pgvector** | "Don't lose user uploads" instinct. | M1 was never production-deployed (`MILESTONES.md` confirms no real users). Migration code = wasted effort. | Clean slate. Re-upload docs in M2. Document in release notes. |
| **Embedding model swap to local (sentence-transformers / BGE-M3)** | Cocoindex's flagship example uses sentence-transformers locally — feels native. Avoids OpenAI/Gemini API cost. | Adds 1-2 GB model download + GPU/CPU latency tuning. M2 scope is rewrite, not model exploration. Vietnamese-specific evaluation of BGE-M3 vs `gemini-embedding-001` is a separate experiment. | M2 keeps OpenAI/Gemini hot-swap as in Go (D5). Local-model experiment deferred — if pursued later, drop in `SentenceTransformerEmbedder` as the `EMBEDDER` ContextKey value (cocoindex pattern unchanged). |
| **General test coverage (>80% unit tests)** | Engineering hygiene urge. | Scope creep. M2 already has 8 REQ groups; comprehensive tests = separate milestone. | M2 tests critical paths only: auth login/refresh, ingest one doc end-to-end, search returns ≥1 result, ask returns citation. Defer full coverage to v4.0 hardening (per `PROJECT.md` Out of Scope). |
| **Real-time progress via WebSocket** | Modern UX. | Adds connection management, fallback handling, complicates auth (WebSocket + JWT). Current frontend polls `/api/documents/:id/status` and works. | Keep polling. The poll endpoint is TS-12. WebSocket = future v3.0 work when frontend rewrite happens anyway. |
| **GraphQL API** | Trendy. | Frontend already uses REST `services/api.ts` heavily. Switching = D6 violation (no frontend changes). | Stay REST. |

### Out of Scope (defer to v3.0 / v4.0 — already decided in PROJECT.md but echoed here for downstream `REQUIREMENTS.md`)

| Feature | Defer to | Reason |
|---------|----------|--------|
| Multi-subdomain SPA tear-down (Hub Tổng + 3 Hub SPAs) | v3.0 | Frontend untouched in M2 (D6). |
| MCP server for Claude/ChatGPT agent | v4.0 | Depends on stable RAG quality first. |
| Hybrid BM25 retrieval | v4.0 | M2 vector-only sufficient for ≥75% gate. |
| Version history & concurrent editing of wiki pages | v4.0+ | Phase 3 PRD. |
| Security hardening (`.gitignore` root, GCP key audit, AES_KEY rotation, XSS token storage → httpOnly cookie) | v4.0 | Explicit dedicated milestone. |
| OCR Vietnamese for scanned PDF | v4.0 (revisit) | See anti-feature row above. |
| Comprehensive test coverage | v4.0 | M2 critical path only. |
| Migration from ChromaDB to pgvector | Never | M1 not production, no data exists. |

---

## Multi-Tenancy Decision (pgvector schema for 3 hubs)

**Question:** Single table with `hub_id` column + filter on every query? Partitioned by `hub_id`? Schema-per-hub?

**Recommendation: Single table + `hub_id` column + composite index `(hub_id)` + HNSW on `embedding` + `SET hnsw.iterative_scan = relaxed_order`**

**Rationale (evidence-based):**

1. **Tenant count is small and bounded** (3 hubs, no plans for >50). Database-per-tenant or schema-per-tenant overhead (connection pools per schema, migration replay per schema) is wasted complexity at this scale.
2. **Tigerdata + Nile + PlanetScale guidance for shared-schema RAG:** "Shared-schema is the most common and recommended approach" for ≤100 tenants with ≤100K chunks each.
3. **HNSW + WHERE clause recall problem is SOLVED in pgvector 0.8.0** (released 2025) via iterative scans:
   - WITHOUT iterative scan: filter applied POST-index-scan, with `ef_search=40` and 33% selectivity (1 hub of 3) → ~13 results matched on average. Bad recall.
   - WITH `hnsw.iterative_scan = relaxed_order`: index keeps fetching until candidates satisfy the WHERE clause OR `max_scan_tuples` limit hit. ~9× faster query, ~100× more relevant results per AWS Aurora benchmarks.
4. **`hub_id` filter selectivity is high** (1/3 typically, 2/3 for cross-hub). Iterative scan handles this trivially.
5. **Partitioning by `hub_id` is an option** if growth >50K chunks/hub or if a hub develops drastically different query patterns. PRE-build per-partition HNSW indexes is cheap with declarative partitioning. **Defer until measured** — premature partitioning costs migration effort.

**Concrete schema sketch:**

```sql
CREATE TABLE chunks (
    chunk_id BIGINT PRIMARY KEY,        -- cocoindex generate_id(chunk.text)
    hub_id INT NOT NULL REFERENCES hubs(id),
    document_id BIGINT NOT NULL REFERENCES documents(id),
    chunk_index INT NOT NULL,
    text TEXT NOT NULL,
    embedding VECTOR(3072),              -- gemini-embedding-001 / text-embedding-3-large
    metadata JSONB,
    chunk_start INT,
    chunk_end INT,
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX chunks_hub_id_idx ON chunks (hub_id);
CREATE INDEX chunks_document_id_idx ON chunks (document_id);
CREATE INDEX chunks_embedding_hnsw ON chunks USING hnsw (embedding vector_cosine_ops) WITH (m=16, ef_construction=64);
-- Per-session: SET hnsw.iterative_scan = relaxed_order; SET hnsw.ef_search = 100;
```

**Confidence:** HIGH for the recommendation, HIGH for the iterative_scan necessity. The exact `m`/`ef_construction`/`ef_search` values are conservative defaults — tune during eval phase.

---

## Hot-Swap with Cocoindex (the tricky one)

**Question:** Current Go lets `PUT /api/rag-config` swap embedder provider+model at runtime without restart or re-index. Does cocoindex support this?

**Short answer:** Partially. The pattern differs from Go and has a hard constraint.

**The constraint:** Cocoindex flows are code-defined. The dataclass `DocEmbedding` carries `embedding: Annotated[NDArray, EMBEDDER]` which fixes the **dimension** at flow build time. Changing the embedder dimension = schema change = drop+recreate target table = full re-index.

**The implementable pattern:** Read provider+key+model from a mutable `ContextKey` or from the `settings` table at each `embed()` call. As long as dimension stays constant, the embedding API used per-call can vary.

```python
EMBEDDER_CONFIG = coco.ContextKey[dict]("embedder_config")  # provider, api_key, model

@coco.fn
async def embed_chunk(text: str) -> NDArray:
    cfg = coco.use_context(EMBEDDER_CONFIG)
    # litellm.aembedding handles provider routing
    resp = await litellm.aembedding(model=cfg["model"], input=[text], api_key=cfg["api_key"])
    return np.array(resp.data[0]["embedding"])
```

**What works without re-index (dimension preserved):**
- OpenAI `text-embedding-3-large` (3072) ↔ Gemini `gemini-embedding-001` (3072) — same dimension, hot-swappable
- OpenAI `text-embedding-3-small` (1536) ↔ Gemini legacy 768 — different dimensions, NOT hot-swappable to each other

**What requires re-index (dimension change):**
- 1536 → 3072 or vice versa → schema must drop+recreate. Cocoindex handles this automatically when flow is re-deployed with new annotation, but it triggers a `--full-reprocess`.

**M2 implementation recommendation:**
1. **At launch:** Pick one dimension (recommend 3072 = both OpenAI 3-large + Gemini 001) and pin it. Document this constraint.
2. **`PUT /api/rag-config`** writes provider/model/api_key to `settings` table, invalidates the `EMBEDDER_CONFIG` ContextKey value, future embeds (both ingest and query via `transform_flow`) use new provider.
3. **Cache invalidation gotcha:** Cocoindex memo cache is keyed on input + code hash. If you swap providers WITHOUT changing flow code, memo cache says "already embedded, skip" but the cached vector is from OLD provider. **Mitigation:** include provider+model in the `EMBEDDER_CONFIG` and reference it inside `embed_chunk` so the function input changes when provider changes → memo cache miss → re-embed. This effectively triggers a full re-embed on provider swap, which is correct behavior (mixing OpenAI and Gemini vectors in same index would destroy retrieval quality).
4. **UX:** Show admin a warning before swap — "This will re-embed all N chunks, est. cost $X.YZ, est. time M minutes" — same UX as M1's planned 999.1 behavior, but now actually correct.

**Confidence:** MEDIUM. The `ContextKey`-based pattern is documented in cocoindex docs (see `lifespan` example). The cache-invalidation-on-provider-swap detail is inferred from cocoindex's memo design rather than directly cited — flag this as a phase research item.

---

## CocoIndex Flow Versioning (when re-index IS necessary)

| Change Type | Re-index Required? | Mechanism |
|-------------|---------------------|-----------|
| Source document content changes (user edits) | Partial — only changed chunks | `@coco.fn(memo=True)` + `generate_id` |
| New document uploaded | Partial — only new chunks added | Same |
| Document deleted | Partial — affected rows removed via cocoindex's target diff | Same |
| Embedder MODEL changed within same dimension | Full re-embed (vectors invalid mixed) | Provider info as function input → memo cache miss |
| Embedder DIMENSION changed | Full re-embed + schema migration | Cocoindex `--full-reprocess` + `ALTER TABLE` or recreate |
| Chunk size / overlap changed | Full re-chunk + re-embed | Function code hash changes → memo invalidation |
| New chunk metadata field added (e.g., `language`) | Backfill only the new column | Cocoindex `ALTER TABLE` non-destructive evolution |
| Flow structure changes (new transform inserted) | Depends on cache key effect | Best to assume full re-process for safety |

**Operational implication:** Document this matrix in the admin UI / `Settings.tsx` so admins understand cost of changes. M2 should provide a `POST /api/admin/reindex?mode=full|incremental` button to force a full re-index (calls `app.update(force=True, full_reprocess=True)`).

---

## Feature Dependencies

```
TS-1 (cocoindex flow definition)
    └── TS-2 (pgvector schema) ── declared by flow's TableSchema
    └── TS-3 (incremental re-index) ── enabled by @coco.fn(memo=True) + generate_id
            └── D-1 (cost savings) ── observable consequence
            └── D-2 (stable chunk_id) ── observable consequence

TS-4 (auth JWT) ── FOUNDATION
    └── TS-5 (RBAC) ── depends on JWT claim with role
            └── TS-6 (hub CRUD admin-only)
            └── TS-7 (user CRUD admin-only)

TS-1 (flow) ── via @coco.transform_flow() ── TS-8 (search uses same embedder)
TS-8 (search) ── retrieves chunks ── TS-9 (ask passes chunks to LLM)
TS-9 (ask) ── needs ── TS-2 chunk_id is stable AND TS-3 (otherwise citations rot)

TS-11 (hot-swap) ── REQUIRES ── dimension pinned + ContextKey pattern + cache invalidation handling
TS-11 ── CONFLICTS with ── TS-3 if naive (caching old-provider vectors). Resolved by provider-aware function input.

TS-12 (ingest job tracking) ── wraps ── TS-1 flow execution

TS-14 (token usage) ── instruments ── TS-11 (LiteLLM calls) and TS-1 (embedding calls)

TS-16 (frontend URL compat) ── envelops ── ALL other TS endpoints
```

### Critical Dependencies for Roadmap Ordering

- **TS-1 + TS-2 must ship together** — flow declares schema, can't separate
- **TS-4 + TS-5 + TS-16 envelope wrapper** must precede all data endpoints (auth-gated)
- **TS-3 (incremental) is automatic** once TS-1 done correctly — no separate phase
- **TS-11 (hot-swap) should ship LATE** after TS-1/TS-8/TS-9 stable — it's the riskiest behavior and benefits from a stable baseline to compare against
- **TS-12 (job tracking)** can be done in parallel with TS-1 — they share the `documents` table

---

## MVP Definition

### Launch with M2 (defined as "what the frontend needs to not break")

Every endpoint currently called by `frontend/src/services/api.ts` must respond with the same envelope and same status codes. The frontend is UNTOUCHED per D6.

**Critical path for M2 GA:**

- [ ] TS-4 + TS-5 + TS-16 (auth + RBAC + URL compat) — frontend can log in
- [ ] TS-6 + TS-7 + TS-13 + TS-15 (hub/user/audit/apikey CRUD) — admin pages render
- [ ] TS-1 + TS-2 (cocoindex flow + pgvector schema) — backend can ingest
- [ ] TS-12 (job tracking) — DocumentIngestion page shows progress
- [ ] TS-8 + TS-10 (single + cross-hub search) — CrossHubSearch page works
- [ ] TS-9 (ask with citations) — answer endpoint returns `[src:N]` superscripts via `CitationText.tsx`
- [ ] TS-11 (provider hot-swap) — Settings page works without restart
- [ ] TS-14 (token usage) — TokenUsage dashboard renders
- [ ] **Quality gate:** ≥75% top-3 retrieval on eval dataset (10 Vietnamese medical docs)

### Defer to v4.0 hardening

- [ ] D-3 (lineage debug endpoint) — nice-to-have
- [ ] Streaming `/api/ask/stream` — UX improvement
- [ ] OCR Vietnamese — if user feedback shows regression on scanned PDFs
- [ ] BM25 hybrid — if quality gate fails purely on retrieval recall
- [ ] WebSocket job progress — if polling is too laggy in practice
- [ ] Multi-subdomain SPA (v3.0)
- [ ] MCP server (v4.0)

---

## Feature Prioritization Matrix

| # | Feature | User Value | Implementation Cost | Priority |
|---|---------|------------|---------------------|----------|
| TS-1 | Cocoindex flow definition | HIGH (enables everything) | MEDIUM | P1 |
| TS-2 | pgvector schema + hub_id | HIGH | MEDIUM | P1 |
| TS-3 | Incremental re-index | HIGH | LOW (built-in) | P1 |
| TS-4 | JWT auth | HIGH (gating) | LOW | P1 |
| TS-5 | RBAC | HIGH (security) | LOW | P1 |
| TS-6 | Hub CRUD | HIGH | LOW | P1 |
| TS-7 | User CRUD | HIGH | LOW | P1 |
| TS-8 | Vector search | HIGH | MEDIUM | P1 |
| TS-9 | LLM answerer + citation | HIGH | MEDIUM | P1 |
| TS-10 | Cross-hub search | MEDIUM | LOW | P1 |
| TS-11 | Provider hot-swap | MEDIUM (admin-only) | MEDIUM-HIGH | P1 (existing feature, can't regress) |
| TS-12 | Ingest job tracking | HIGH (UX) | MEDIUM | P1 |
| TS-13 | Audit log | MEDIUM | LOW | P1 |
| TS-14 | Token usage | MEDIUM | MEDIUM | P1 |
| TS-15 | API key mgmt | LOW (rarely used) | LOW | P2 (can ship in late M2 phase) |
| TS-16 | URL compat | HIGH (frontend won't load otherwise) | MEDIUM (audit-heavy) | P1 |
| D-1..D-6 | Differentiators | Observable consequences of P1 work | Already counted | P1 (free) |
| Streaming /ask | LOW (UX nicety) | MEDIUM | P3 |
| OCR Vietnamese | UNKNOWN | HIGH | P3 (revisit) |
| Hybrid BM25 | UNKNOWN | HIGH | P3 (revisit if eval fails) |

**Priority key:** P1 = M2 must-ship · P2 = M2 stretch · P3 = post-M2

---

## Vietnamese Medical Context — Specific Considerations

Although this is a stack rewrite not a content rewrite, several domain specifics influence implementation:

| Concern | M1 Solution (Docling) | M2 Stack Behavior | Risk |
|---------|------------------------|-------------------|------|
| Vietnamese heading detection (BS, BSCKII, TTUT prefixes) | Custom regex in Go chunker | Cocoindex's `RecursiveSplitter` with `language="markdown"` won't catch these. Need custom `@coco.fn` chunker OR pre-process with simple regex before splitter. | MEDIUM — schedule a phase to validate chunk boundaries on Vietnamese docs. |
| Tables in medical PDFs (dosage charts, vital signs) | Docling HTML table preservation | `pdfplumber` or `camelot-py` to extract tables, serialize to markdown table syntax, feed into `RecursiveSplitter` which respects markdown tables | HIGH — table-heavy docs are the biggest regression risk per `PROJECT.md` |
| Scanned PDF tiếng Việt | Docling+Tesseract `vie+eng` | NOT supported in M2 (D4). Return explicit error. | MEDIUM — documented in `PROJECT.md` Constraints already |
| LLM prompt language | Vietnamese system prompt | Same — LiteLLM is provider-agnostic; prompts stay Vietnamese | LOW |
| Embedding language coverage | OpenAI 3-large + Gemini 001 both multilingual | Same | LOW |
| Citation format `[src:<chunk_id>]` parsing | Go regex | Same regex in Python, stays compatible with `CitationText.tsx` | LOW |

---

## Sources

**Cocoindex (HIGH confidence — Context7 verified):**
- [CocoIndex on Context7](https://context7.com/cocoindex-io/cocoindex/llms.txt) — flow definition, `@coco.fn(memo=True)`, `generate_id`, pgvector target
- [CocoIndex incremental processing blog](https://cocoindex.io/blogs/incremental-processing/) — re-index triggers, source diff
- [CocoIndex core concepts](https://cocoindex.io/docs/programming_guide/core_concepts/) — flow lifecycle, schema evolution
- [CocoIndex CLI reference](https://cocoindex.io/docs/core/cli) — `update --live`, `--full-reprocess`, `--reset`
- [CocoIndex query support blog](https://cocoindex.io/blogs/query-support) — `@transform_flow()` for index/query consistency
- [CocoIndex Sentence Transformers ops](https://github.com/cocoindex-io/cocoindex/blob/main/docs/src/content/docs/ops/sentence_transformers.mdx) — complete pipeline example
- [CocoIndex skills SKILL.md](https://github.com/cocoindex-io/cocoindex/blob/main/skills/cocoindex/SKILL.md) — `generate_id` for deterministic chunk IDs
- [CocoIndex memoization keys](https://github.com/cocoindex-io/cocoindex/blob/main/docs/src/content/docs/advanced_topics/memoization_keys.mdx) — cache key mechanism
- [CocoIndex image_search FastAPI example](https://github.com/cocoindex-io/cocoindex/tree/main/examples/image_search) — `uvicorn api:app` integration pattern

**LiteLLM (HIGH confidence — Context7 verified):**
- [LiteLLM streaming docs](https://docs.litellm.ai/docs/completion/stream) — `acompletion(..., stream=True)` async generator
- [LiteLLM Context7](https://context7.com/berriai/litellm/llms.txt) — embedding + chat completion provider routing

**pgvector multi-tenancy (HIGH confidence — multiple authoritative sources):**
- [Tigerdata: Building Multi-Tenant RAG with PostgreSQL](https://www.tigerdata.com/blog/building-multi-tenant-rag-applications-with-postgresql-choosing-the-right-approach) — shared-schema vs partitioned vs schema-per-tenant guidance
- [Nile: Building Multi-Tenant RAG](https://www.thenile.dev/blog/multi-tenant-rag) — single-table + RLS pattern
- [pgvector 0.8.0 release](https://www.postgresql.org/about/news/pgvector-080-released-2952/) — iterative scan announcement
- [AWS Aurora pgvector 0.8.0 benchmarks](https://aws.amazon.com/blogs/database/supercharging-vector-search-performance-and-relevance-with-pgvector-0-8-0-on-amazon-aurora-postgresql/) — 9× faster, 100× more relevant with iterative scan
- [PlanetScale: Approaches to tenancy in Postgres](https://planetscale.com/blog/approaches-to-tenancy-in-postgres) — shared-schema is most common
- [Crunchy Data: HNSW Indexes with Postgres](https://www.crunchydata.com/blog/hnsw-indexes-with-postgres-and-pgvector) — HNSW + WHERE filter behavior

**FastAPI auth & streaming (MEDIUM confidence — common patterns):**
- [FastAPI OAuth2 + JWT tutorial](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/) — official `OAuth2PasswordBearer` + `Depends(get_current_user)` pattern
- [FastAPI SSE tutorial](https://fastapi.tiangolo.com/tutorial/server-sent-events/) — `StreamingResponse` with async generator
- [Logto: FastAPI RBAC with JWT](https://docs.logto.io/api-protection/python/fastapi) — RS256 via `PyJWKClient`, role validation in dependency

---

## Confidence Assessment

| Area | Confidence | Reason |
|------|-----------|--------|
| Cocoindex flow API & incremental processing | HIGH | Context7 + official docs + multiple working examples |
| Stable `chunk_id` via `generate_id` | HIGH | Explicitly documented as "same key always gets same ID" |
| pgvector multi-tenancy recommendation | HIGH | Multiple authoritative blogs converge on shared-schema for ≤100 tenants |
| pgvector 0.8 `iterative_scan` necessity | HIGH | AWS Aurora benchmarks + official release notes |
| LiteLLM streaming + provider routing | HIGH | Context7 + official docs verified |
| FastAPI JWT + RBAC patterns | HIGH | Official FastAPI tutorials |
| Cocoindex + FastAPI integration | MEDIUM | Example exists (`examples/image_search`) but production patterns under-documented; needs validation in M2 Phase 2 |
| Hot-swap embedder cache-invalidation behavior | MEDIUM | Inferred from cocoindex memo design — explicit doc reference not found; flag as phase research item |
| Vietnamese-specific tokenization quality with `RecursiveSplitter` | LOW | No cocoindex Vietnamese-specific docs found — must validate empirically against eval dataset |
| Table extraction from PDF without Docling | LOW | `pdfplumber`/`camelot` are options but quality on complex medical tables unknown — Phase ingest open question |

---

## Roadmap Implications for `REQUIREMENTS.md` Author

1. **Group P1 features into 6-8 phases** following the dependency chain:
   - Phase 1: Infra setup (docker-compose, postgres+pgvector, repo restructure, delete Go)
   - Phase 2: Auth + RBAC + URL envelope compat (TS-4, TS-5, TS-16 audit)
   - Phase 3: Hub/User/AuditLog/APIKey CRUD (TS-6, TS-7, TS-13, TS-15) — pure port, no cocoindex
   - Phase 4: CocoIndex flow + pgvector schema + ingest job tracking (TS-1, TS-2, TS-12)
   - Phase 5: Search + cross-hub (TS-8, TS-10) + `transform_flow` shared embedder
   - Phase 6: Ask + citation (TS-9) + LiteLLM integration + token usage (TS-14)
   - Phase 7: Provider hot-swap + cache invalidation (TS-11) — riskiest, ship after baseline
   - Phase 8: Eval framework + quality gate ≥75% top-3
2. **Flag for phase-specific deep research:**
   - Phase 4: Vietnamese chunk boundary validation (heading regex pre-processor) + PDF table extraction without Docling
   - Phase 7: Cache invalidation behavior on provider swap — confirm with cocoindex maintainer or empirical test
3. **Hard dependencies to highlight in `REQUIREMENTS.md`:**
   - "Search depends on flow's `transform_flow` decorator existing for the embedder"
   - "Citation correctness depends on `generate_id` deterministic chunk IDs (NOT `IdGenerator().next_id` which is per-call distinct)"
   - "Hot-swap depends on dimension being pinned; cross-dimension swap = full re-index (admin warning required)"
4. **Anti-features to explicitly mark as out-of-scope** in `REQUIREMENTS.md` to prevent scope drift:
   - OCR Vietnamese (D4 — Constraints)
   - Hybrid BM25 (deferred per PROJECT.md)
   - Streaming `/ask` (post-M2 enhancement)
   - Test coverage beyond critical path (v4.0)
   - ChromaDB→pgvector migration (no data exists)

---

*Feature research for: Medinet Wiki M2 Full RAG Rewrite (CocoIndex + Python FastAPI + pgvector)*
*Researched: 2026-05-13*
