# Phase 6: Search API Single + Cross-Hub - Context

**Gathered:** 2026-05-18
**Status:** Ready for planning
**Source:** Inline discussion (thay cho /gsd-discuss-phase — user chọn "plan luôn không discuss"; quyết định chốt theo frontend contract D6)

<domain>
## Phase Boundary

Phase 6 giao **vector search API** trên pgvector: search trong 1 hoặc nhiều hub, cross-hub parallel aggregation, find-similar. Toàn bộ chạy trên FastAPI `api/`; query embedding qua LiteLLM (`embedder.embed_text`), SQL raw trên asyncpg pool — **bypass cocoindex hoàn toàn** (cocoindex chỉ lo INGEST/embed lúc index).

Requirements: SEARCH-01, SEARCH-02, SEARCH-03, SEARCH-04.

**NGOÀI scope Phase 6 (thuộc Phase 7 — Ask):**
- `POST /api/search/answer` (frontend `searchAnswer`) — RAG answer + citation, cần LLM. Endpoint này sẽ vẫn 404 sau Phase 6; fix ở Phase 7.

</domain>

<decisions>
## Implementation Decisions

### Contract source — frontend `api.ts` thắng ROADMAP/REQUIREMENTS (D6)
- **D-01 (HTTP method):** ROADMAP + REQUIREMENTS ghi `GET /api/search?q=...&hub_id=X` (query params). Frontend `api.ts` gọi **`POST /api/search`** với JSON body. → Dùng **POST + JSON body**. ROADMAP/REQUIREMENTS GET form bị superseded bởi frontend contract (D6 — frontend không sửa được). Cùng lý do: `POST /api/search/cross-hub`, `POST /api/search/similar`.
- **D-02 (field name):** Request body field tên `query` (KHÔNG `q`) — đúng `SearchRequestAPI` trong `api.ts`.

### Endpoint trong scope Phase 6 (3 endpoint)
- **D-03:** Build đúng 3 endpoint, shape khớp `api.ts` 1:1:
  - `POST /api/search` — body `SearchRequestAPI`, response `SearchResponseAPI`. (SEARCH-01, SEARCH-02)
  - `POST /api/search/cross-hub` — body `SearchRequestAPI`, response `SearchResponseAPI`. (SEARCH-03)
  - `POST /api/search/similar` — body `{content, hub_id?, threshold?}`, response `SimilarResponseAPI`.
- **D-04 (`/api/search/similar` không có REQ-ID):** `searchAnswer`/`findSimilar` không nằm trong SEARCH-01..04. `/api/search/similar` vẫn build trong Phase 6 vì frontend cần (D6) — coi như addition của Phase 6, KHÔNG cần REQ-ID mapping. `/api/search/answer` thì KHÔNG (chờ Phase 7).

### `/api/search` vs `/api/search/cross-hub` — phân biệt ngữ nghĩa
- **D-05 (`/api/search`):** Search trên **union** các `hub_ids` trong body bằng **1 câu SQL** (`WHERE hub_id = ANY($hubs)`), trả global top-`top_k` theo score. Nếu `hub_ids` rỗng/null → search toàn bộ hub user được assign. `total_hubs_searched` = số hub thực sự query.
- **D-06 (`/api/search/cross-hub`):** Query **song song mỗi hub** qua `asyncio.gather` (mỗi hub lấy `top_k` riêng), rồi **aggregate + re-rank** theo score → global top-`top_k`. Mỗi result kèm `hub_id` + `hub_name`. (Body vẫn `SearchRequestAPI`; `top_k` dùng làm top-k per-hub khi fan-out — REQUIREMENTS gọi `top_k_per_hub`, frontend chỉ gửi `top_k` nên dùng `top_k` cho cả hai.)

### Hub isolation — defense in depth (bắt buộc, EXIT-criteria-grade)
- **D-07:** `hub_ids` request PHẢI được giao (intersect) với hub user được assign (`user_hubs` join). Hub user không có quyền bị **loại ở service/repo layer** TRƯỚC khi vào SQL — KHÔNG để leak. Đây là defense in depth NGOÀI `WHERE hub_id = ANY(...)` SQL filter. Viewer Hub A request `hub_ids:[A,B,C]` mà chỉ assign A → chỉ search A. Pattern hub isolation: tái dùng cách Phase 5 (`app/repositories/hub_isolation.py`).

### HNSW tuning (SEARCH-02 — R2 mitigation)
- **D-08:** Mỗi search query set session config trên connection trước khi chạy vector SQL:
  - `SET LOCAL hnsw.ef_search = 200`
  - `SET hnsw.iterative_scan = relaxed_order`
  - `SET hnsw.max_scan_tuples = 20000`
  `SET LOCAL` cần chạy trong transaction; `SET` (không LOCAL) ở connection-level. Planner xác định cách áp đúng với asyncpg pool (acquire connection → set → query → release). p95 target <800ms single-hub, <1.5s cross-hub.

### Vector SQL — raw, bypass cocoindex
- **D-09:** Query embed qua `app/services/embedder.py::embed_text()` — CÙNG provider/model/dimension (1536) như lúc index. SQL raw:
  ```sql
  SELECT c.id, c.document_id, c.hub_id, c.content, c.heading_path, c.metadata,
         1 - (c.vector <=> $1) AS score
  FROM chunks c
  WHERE c.hub_id = ANY($2) AND c.vector IS NOT NULL
  ORDER BY c.vector <=> $1
  LIMIT $3
  ```
  Vector param truyền dạng pgvector literal (`'[...]'`) hoặc qua pgvector asyncpg codec — planner chọn cách khớp codebase hiện tại.
- **D-10 (joins cho `SearchResultAPI`):** `chunks` KHÔNG có title/hub_name/category/tags. JOIN `documents` (lấy `filename`→`title`, `updated_at`) + `hubs` (lấy `name`→`hub_name`). `category`/`tags` schema M2 chưa có → trả `null`/`[]`. `source` = hằng `"document"`. `snippet` = `content` truncate (~300 ký tự, cắt theo word boundary). `content` field optional — trả full content. `raw_similarity` = cùng giá trị cosine `1-(vector<=>q)`; `score` = raw (M2 chưa rerank model — `score == raw_similarity`).

### Redis cache (SEARCH-04)
- **D-11:** Cache search results. Key `search:{sha256(query + sorted(hub_ids) + top_k + min_score)}`, TTL **300s**. `cache_hit` field trong response phản ánh đúng. Cache cho `/api/search` + `/api/search/cross-hub` (KHÔNG cache `/api/search/similar`).
- **D-12 (invalidation):** Khi document **upload/edit/delete** trong hub → publish Redis Pub/Sub channel `hub:{hub_id}:invalidate`. Subscriber xoá cache key liên quan hub đó. Cần wire publish vào `app/services/documents_service.py` (upload/reupload/content-edit/delete paths). Cách xoá theca key của 1 hub: planner chọn (vd cache key kèm hub-tag set, hoặc namespaced key `search:{hub_id}:...`). Đơn giản-hoá M2 OK miễn upload mới → search lần sau không trả stale.

### Rate limit (AUX-03 — decoration defer từ Phase 5)
- **D-13:** Decorate search endpoints `@limiter.limit("100/minute")` (slowapi `limiter` đã wire ở `app/main.py` Phase 5). 100 req/min/user trên search.

### Filters
- **D-14:** `SearchRequestAPI.filters` (`categories`/`tags`/`date_from`/`date_to`) + `min_score`: `min_score` áp được ngay (filter `score >= min_score`). `categories`/`tags`/`date_*` — schema M2 chưa có nguồn data category/tags trên documents → **accept-but-noop** cho M2 (parse, không lỗi nếu gửi, nhưng không filter). Ghi nhận deferred. `date_from`/`date_to` nếu áp được lên `documents.updated_at` thì áp; nếu không, noop.

### Claude's Discretion (planner quyết)
- Layout module: `app/routers/search.py` + `app/services/search_service.py` + `app/schemas/search.py` + (tùy) `app/repositories/search_repo.py` — theo layered pattern CONVENTIONS.md.
- Cách truyền vector param cho asyncpg (pgvector codec vs literal string).
- Cách tổ chức cache key + invalidation (hub-tagged set vs namespaced key).
- Có cần Alembic migration không — **dự kiến KHÔNG** (chunks + HNSW index `chunks_vector_hnsw` đã có từ Migration 0001). Nếu planner phát hiện thiếu index thì mới thêm.
- Subscriber Pub/Sub chạy ở đâu (asyncio task trong lifespan vs lazy).

</decisions>

<specifics>
## Specific Ideas

- **Hub isolation là điều kiện ship** — integration test bắt buộc: viewer Hub A KHÔNG bao giờ thấy chunk Hub B kể cả khi truyền explicit `hub_ids` chứa hub B.
- Response envelope `{success, data, error, meta}` shape-identical mọi endpoint (kể cả 401/403/422/429). Search trả data = `SearchResponseAPI`.
- `EXPLAIN ANALYZE` cho vector query phải show `Index Scan using ix_chunks_vector_hnsw` KHÔNG `Seq Scan` trên dataset 1K+ chunks (Success Criteria #3) — đưa vào verification.
- p95 latency: <800ms single-hub, <1.5s cross-hub (Success Criteria #1,#2). Sanity check ở Phase 6; tune `ef_search`/`iterative_scan` nếu vỡ.
- Auth: JWT bắt buộc, role viewer trở lên. Lấy `get_current_user` dependency Phase 3.
- Empty result hợp lệ: hub chưa có chunk → trả `results: []`, KHÔNG lỗi.

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope
- `.planning/ROADMAP.md` §"Phase 6: Search API Single + Cross-Hub" — goal + 5 success criteria + risks (R2/E2)
- `.planning/REQUIREMENTS.md` §"SEARCH" — SEARCH-01..04 chi tiết

### Contract reference (D6 — SOURCE OF TRUTH cho endpoint shape)
- `Hub_All/frontend/src/services/api.ts` — `search()`, `crossHubSearch()`, `findSimilar()` + types `SearchRequestAPI`, `SearchResultAPI`, `SearchResponseAPI`, `SimilarResponseAPI`. Khi mâu thuẫn ROADMAP/REQUIREMENTS → file này thắng (D-01).

### Codebase — reuse
- `Hub_All/api/app/services/embedder.py` — `embed_text()` query embedding (dim 1536 PIN)
- `Hub_All/api/app/rag/flow.py` — `ChunkRow` schema, cách chunks được index (tham khảo column thực)
- `Hub_All/api/migrations/versions/0001_initial_schema.py` §chunks §documents §hubs — column thật: `chunks(id, document_id, hub_id, content, content_hash, heading_path, page_start, page_end, vector, metadata, created_at)`, `documents(id, hub_id, uploaded_by, filename, file_path, mime_type, file_size_bytes, status, ..., updated_at)`, `hubs(id, slug, name, description, ..., code, subdomain, status, updated_at)`. HNSW index `ix_chunks_vector_hnsw` (vector_cosine_ops).
- `Hub_All/api/app/repositories/hub_isolation.py` + Phase 5 hub isolation pattern (`HubisolationError` → 403 handler đã có ở `main.py`)
- `Hub_All/api/app/services/documents_service.py` — wire Pub/Sub invalidate publish vào upload/reupload/edit/delete
- `Hub_All/api/app/routers/__init__.py` + `app/main.py::create_app()` — cách mount router
- `Hub_All/api/app/middleware/rate_limit.py` — `limiter` slowapi instance
- `Hub_All/api/app/auth/dependencies.py` — `get_current_user`, role dependency
- `.planning/CONVENTIONS.md` — layered architecture router→service→repository

### Established Patterns
- Layered: router → service → repository → raw SQL / model
- Test: pytest + httpx AsyncClient + testcontainers Postgres + Redis; marker `@pytest.mark.critical` cho hub isolation
- Envelope handler + HubIsolationError handler đã có sẵn ở `app/main.py`

</canonical_refs>

<deferred>
## Deferred Ideas

- `POST /api/search/answer` (RAG answer + citation) — Phase 7 (ASK-01..03)
- `filters.categories` / `filters.tags` / rerank model — schema M2 chưa có nguồn data; accept-but-noop, revisit khi có category/tag trên documents
- Recall eval ≥75% — Phase 9 (eval gate); Phase 6 chỉ sanity check thủ công 50 query VN

</deferred>

---

*Phase: 06-search-api-single-cross-hub*
*Context gathered: 2026-05-18 (inline discussion — quyết định chốt theo frontend contract D6)*
