# Conventions — Medinet Wiki M2 (Python FastAPI + CocoIndex + pgvector)

**Stack:** Python 3.12 · FastAPI 0.136 · CocoIndex 1.0.3 · pgvector pg16 · asyncpg · Alembic · LiteLLM · PyJWT · pwdlib · structlog
**Áp dụng:** Toàn bộ code mới trong `Hub_All/api/` từ M2 Phase 1 trở đi. Code Go `Hub_All/backend/` (legacy, giữ đến Phase 8) tuân thủ convention cũ ở `.planning/codebase/CONVENTIONS.md`.
**Mục đích:** Source of truth cho test strategy, naming, namespace, middleware, logging. Phase 2-10 ship feature PHẢI tuân thủ.

---

## 1. Test Strategy

### Rule

M2 áp dụng **critical-path mandatory testing** — không phải comprehensive coverage. PR ship feature thuộc critical path PHẢI kèm test; coverage tổng thể target ≥ 50%, comprehensive >80% defer v4.0 (xem `REQUIREMENTS.md` Out of Scope).

**Critical path bắt buộc test** (mỗi mục có ít nhất 1 integration test):

| Module | Test bắt buộc |
|---|---|
| Auth (Phase 3) | Login happy + invalid password + locked account + refresh + JWT verify với Go-generated token |
| RBAC | Viewer/Editor KHÔNG thể mutate endpoint admin-only → 403 |
| Hub isolation | Editor Hub A KHÔNG thể PATCH/DELETE doc Hub B kể cả khi explicit `hub_id` trong payload → 403 |
| Ingest (Phase 4) | Upload DOCX → assert chunks tồn tại với `hub_id` đúng + scanned PDF → 415 `failed_unsupported` |
| Search (Phase 6) | Cross-hub search chỉ trả chunks thuộc hub user có access (defense in depth ngoài SQL filter) |
| Ask (Phase 7) | LLM mock return citation `[N]` map đúng `chunks[N-1].chunk_id` |

### Tooling

- **Framework:** `pytest>=8` + `pytest-asyncio>=0.24`
- **HTTP client:** `httpx.AsyncClient` + `ASGITransport` (in-process, không cần boot server)
- **Lifespan trong test:** `asgi-lifespan>=2` (cho test có DB pool init)
- **Real Postgres/Redis:** `testcontainers-python` (Phase 10) — image `pgvector/pgvector:pg16` (KHÔNG mock asyncpg)
- **Marker:** `@pytest.mark.critical` cho critical path → CI gate: `pytest -m critical` PHẢI pass

### DO

```python
# tests/integration/test_hub_isolation.py
@pytest.mark.critical
@pytest.mark.asyncio
async def test_editor_hub_a_cannot_patch_doc_hub_b(client, editor_hub_a_token, doc_hub_b):
    resp = await client.patch(
        f"/api/documents/{doc_hub_b.id}",
        headers={"Authorization": f"Bearer {editor_hub_a_token}"},
        json={"filename": "hacked.docx", "hub_id": "hub_a"},  # explicit override
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "forbidden"
```

### DON'T

```python
# ❌ Skip integration test "vì giống endpoint khác"
def test_hub_a_isolation():
    assert True  # TODO Phase 10
```

### Reference

- Pitfall P9 — 0% test coverage carry-over (HIGH severity)
- `Hub_All/.planning/research/PITFALLS.md#pitfall-9`
- HARD-03 (Phase 10) — integration test ≥50% critical path + CI gate

---

## 2. Naming Conventions (Python + CocoIndex)

### Rule

| Element | Convention | Ví dụ |
|---|---|---|
| Python package/module | `snake_case` | `app.rag.flow`, `app.auth.service` |
| Python class | `PascalCase` | `class DocumentService`, `class HubRepo` |
| Python function/variable | `snake_case` | `def embed_text()`, `chunk_size = 512` |
| Constant module-level | `UPPER_SNAKE_CASE` | `MAX_CHUNK_TOKENS = 8000` |
| File path | `snake_case.py` | `api/app/rag/embeddings.py` |
| Pytest test function | `test_<snake_case>` | `test_login_happy_path` |
| CocoIndex flow name | `snake_case` BẮT BUỘC | `name="medinet_wiki_ingest"` |
| CocoIndex target table | `snake_case` BẮT BUỘC | `table_name="chunks"` |
| Postgres table | `snake_case` | `users`, `hubs`, `documents`, `chunks`, `audit_logs` |
| Postgres column | `snake_case` | `created_at`, `hub_id`, `content_hash` |
| REQ-ID (giữ nguyên Go style) | `UPPER-NN` | `CORE-01`, `INGEST-03`, `HARD-04` |

### CocoIndex naming chi tiết

CocoIndex **lowercase TẤT CẢ** flow name và target name khi tạo bảng Postgres. Nếu flow name `TextEmbedding` → bảng `textembedding`. Đặt snake_case từ đầu để bảng thực tế DỄ TRA trong pgAdmin.

Bảng thực tế CocoIndex tạo tuân theo format: `<APP_NAMESPACE>__<flow_name>__<target_name>`.

Với M2: `APP_NAMESPACE=medinet_prod` (xem section 3), flow `medinet_wiki_ingest`, target `chunks` → bảng thực tế: `medinet_prod__medinet_wiki_ingest__chunks` trong schema `cocoindex`.

### DO

```python
# api/app/rag/flow.py
@cocoindex.flow_def(name="medinet_wiki_ingest")  # snake_case
def medinet_wiki_ingest_flow(flow_builder, data_scope):
    ...
    chunk.export(
        "chunks",  # target table snake_case
        cocoindex.targets.Postgres(table_name="chunks"),
        ...
    )
```

### DON'T

```python
# ❌ PascalCase / camelCase → cocoindex sẽ lowercase, bảng "biến mất" so với expectation
@cocoindex.flow_def(name="MedinetWikiIngest")  # tạo bảng medinetwikiingest — KHÔNG match snake_case khác
def flow(...):
    chunk.export("DocChunks", ...)  # → bảng docchunks, dev tìm "DocChunks" trong psql fail
```

### Vector index ops

> **Vector index ops:** Mọi HNSW index trên column `vector` PHẢI dùng `vector_cosine_ops` (cosine similarity). KHÔNG đổi sang `vector_l2_ops` sau khi data đã embed — re-index toàn bộ corpus (xem Pitfalls#P17).

### Reference

- Pitfall P2 (HIGH) — CocoIndex flow naming + namespace gây bảng "biến mất"
- Pitfall P17 (MEDIUM) — Cosine vs L2 metric mismatch sau khi embed
- Pitfall P19 (LOW) — `cocoindex.main_fn()` deprecated v0.3.36+ → dùng `@cocoindex.flow_def` pattern + pin `cocoindex==1.0.3` exact
- `Hub_All/.planning/research/PITFALLS.md#pitfall-2`

---

## 3. APP_NAMESPACE Policy

### Rule

**`APP_NAMESPACE=medinet_prod` cố định cho MỌI môi trường (dev/staging/production).** KHÔNG đổi namespace giữa env — nếu đổi, CocoIndex sẽ tạo bảng prefix khác → re-index toàn bộ + state cũ orphan.

**Env separation đạt được qua 3 lớp độc lập (không phải qua namespace):**
1. **Database logical:** `medinet_central` (app data) vs `medinet_cocoindex` (cocoindex state) — 2 DB tách bạch trên cùng 1 Postgres instance.
2. **Schema:** App data ở `public`, CocoIndex state ở `cocoindex` (qua `COCOINDEX_DB_SCHEMA=cocoindex` — P7 mitigation).
3. **Container instance:** dev local, staging remote, prod remote — 3 Postgres khác nhau hoàn toàn.

### Bảng thực tế CocoIndex tạo

Với M2 config:
- `APP_NAMESPACE=medinet_prod`
- Flow `name="medinet_wiki_ingest"`
- Target `table_name="chunks"`

→ Bảng thực tế trong Postgres: **`cocoindex.medinet_prod__medinet_wiki_ingest__chunks`** (schema `cocoindex`, double-underscore separator).

State table của CocoIndex (lineage, fingerprint): trong cùng schema `cocoindex`, tên prefix `__cocoindex_*` hoặc tương tự.

### DO

```bash
# Hub_All/api/.env (mọi env)
APP_NAMESPACE=medinet_prod
COCOINDEX_DB_SCHEMA=cocoindex
DATABASE_URL=postgresql+asyncpg://...medinet_central
COCOINDEX_DATABASE_URL=postgresql://...medinet_cocoindex
```

```sql
-- pgAdmin / psql tra bảng thực tế:
\dt cocoindex.medinet_prod__*
-- → liệt kê tất cả bảng CocoIndex của project
```

### DON'T

```bash
# ❌ Đổi namespace giữa env → bảng khác nhau, re-index toàn bộ khi deploy
# dev: APP_NAMESPACE=medinet_dev
# prod: APP_NAMESPACE=medinet_prod
# → 2 set bảng riêng, không share state, lãng phí re-index
```

```bash
# ❌ Đổi APP_NAMESPACE đột ngột giữa Phase 4 và Phase 9
# → CocoIndex flow tạo bảng mới ở namespace mới, bảng cũ orphan, eval Phase 9 query bảng mới = 0 rows
```

### Reference

- Pitfall P2 (HIGH) — Naming + namespace
- Pitfall P7 (MEDIUM) — Schema isolation cocoindex vs app
- R5 risk register — CocoIndex naming + APP_NAMESPACE
- `Hub_All/.planning/research/PITFALLS.md#pitfall-2` và `#pitfall-7`

---

## 4. FastAPI Middleware Order (REVERSED từ Go Gin)

### Rule

**FastAPI middleware execute theo "onion model": middleware ADD CUỐI thực thi ĐẦU TIÊN cho incoming request.**

Order add trong `create_app()` (từ trong ra ngoài):

| Thứ tự add | Middleware | Vị trí onion |
|---|---|---|
| 1. add FIRST | RateLimit | trong cùng |
| 2. add thứ 2 | CORS | |
| 3. add thứ 3 | SecurityHeaders | |
| 4. add LAST | Recovery / error_handler | ngoài cùng → wraps tất cả |

**Outermost (FastAPI) = error_handler / RecoveryMiddleware** — phải catch mọi exception kể cả từ CORS/security middleware bên trong.

### DO

```python
# api/app/main.py — order đúng (CHÚ Ý: REVERSED từ Go Gin)
# NOTE: FastAPI executes last-added FIRST. Order ngược với Go Gin.
app.add_middleware(RateLimitMiddleware)         # 1st add → INNERMOST (sees request sau cùng)
app.add_middleware(CORSMiddleware, ...)         # 2nd add
app.add_middleware(SecurityHeadersMiddleware)   # 3rd add
app.add_middleware(RequestIdMiddleware)         # 4th add — gắn X-Request-Id sớm cho log
app.add_middleware(ErrorHandlerMiddleware)      # LAST add → OUTERMOST (catch all)
```

### DON'T

```python
# ❌ Port thẳng order từ Go → ErrorHandler trở thành innermost
# → exception từ CORS middleware không được catch → 500 raw stack trace leak ra client
app.add_middleware(ErrorHandlerMiddleware)      # 1st = INNERMOST — SAI
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(CORSMiddleware, ...)
app.add_middleware(RateLimitMiddleware)         # LAST = OUTERMOST — KHÔNG đúng
```

### CORS production check (P12 mitigation)

```python
# api/app/config.py
from pydantic import field_validator

class Settings(BaseSettings):
    cors_allowed_origins: list[str]
    app_env: Literal["dev", "staging", "production"]

    @field_validator("cors_allowed_origins")
    @classmethod
    def _no_lan_in_prod(cls, v, info):
        if info.data.get("app_env") != "production":
            return v
        forbidden_patterns = [r"localhost", r"127\.0\.0\.1", r"192\.168\.", r"10\.", r"172\.(1[6-9]|2[0-9]|3[01])\."]
        for origin in v:
            for pattern in forbidden_patterns:
                if re.search(pattern, origin):
                    raise ValueError(f"Production cannot have CORS origin: {origin}")
        return v
```

### Reference

- Pitfall P11 (MEDIUM) — Middleware order REVERSED
- Pitfall P12 (MEDIUM) — CORS production origin leak
- `Hub_All/.planning/research/PITFALLS.md#pitfall-11` và `#pitfall-12`

---

## 5. Logging Fields

### Rule

**Output:** structlog JSON với fields MATCH Go `log/slog` semantic để ops tooling (Loki/Datadog) tiếp tục dùng dashboard cũ.

**Required fields mỗi request log entry:**

| Field | Type | Source | Note |
|---|---|---|---|
| `level` | string | structlog | `debug`, `info`, `warning`, `error`, `critical` |
| `msg` | string | structlog | Verb + object: `request_completed`, `db_query_slow` |
| `ts` | ISO-8601 string | structlog | `2026-05-13T14:30:45.123Z` UTC |
| `request_id` | UUID4 | X-Request-Id middleware | Sinh nếu client KHÔNG gửi |
| `user_id` | UUID hoặc null | JWT claim | null cho unauthenticated endpoint |
| `hub_id` | UUID hoặc null | request scope | null cho cross-hub hoặc admin endpoint |
| `latency_ms` | int | middleware timing | Chỉ ở log "request_completed" |
| `path` | string | request.url.path | `/api/documents/upload` |
| `method` | string | request.method | `POST`, `GET` |
| `status` | int | response.status_code | `200`, `403`, `500` |

### X-Request-Id middleware

```python
# api/app/middleware/request_id.py
import uuid
from starlette.middleware.base import BaseHTTPMiddleware

class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        rid = request.headers.get("X-Request-Id") or str(uuid.uuid4())
        request.state.request_id = rid
        # Propagate xuống cocoindex flow logs qua contextvar (Phase 4)
        response = await call_next(request)
        response.headers["X-Request-Id"] = rid
        return response
```

### DO

```python
# api/app/auth/service.py
import structlog
log = structlog.get_logger(__name__)

async def login(email: str, password: str, request_id: str) -> dict:
    log.info(
        "auth_login_attempt",
        request_id=request_id,
        email_hash=hashlib.sha256(email.encode()).hexdigest()[:8],  # PII-safe
    )
    user = await repo.find_by_email(email)
    if not user:
        log.warning("auth_login_failed", request_id=request_id, reason="user_not_found")
        raise UnauthorizedError()
    ...
```

### DON'T

```python
# ❌ Logging f-string không structured → ops tool KHÔNG parse được field
import logging
logging.info(f"User {email} logged in at {datetime.now()}")  # KHÔNG có request_id, KHÔNG JSON

# ❌ Log PII raw (email, password, full token)
log.info("login", email=email, password=password)  # password leak!
```

### Reference

- HARD-01 (Phase 10) — structlog JSON output + X-Request-Id middleware
- Match Go `log/slog` JSON output cho ops dashboard reuse
- `Hub_All/.planning/research/STACK.md` — structlog 25.x recommendation

### Plan 10-01 status

HARD-01 đã ship Phase 10 Plan 10-01 (2026-05-21):

- `app/logging_config.py` — `configure_structlog()` factory idempotent + 3 ContextVar (`request_id_var`, `user_id_var`, `hub_id_var` default None tường minh — Loki/Datadog query `IS NULL` consistent)
- `app/middleware/request_id.py` — set ContextVar trong `dispatch()` + đo `latency_ms` qua `time.perf_counter()` + emit log `request_completed` với 10 field schema
- Wire vào `app/main.py` lifespan step 0 (gọi `configure_structlog()` TRƯỚC db_pool/redis/cocoindex init) + cocoindex BackgroundTask log qua `app/services/documents_service.py:_struct_logger` (ContextVar propagation qua `asyncio.create_task` copy_context)
- Processor chain: `merge_contextvars` + `_add_contextvars` custom + `add_log_level` + `TimeStamper(iso, utc, key=ts)` + `EventRenamer("msg")` rename `event`→`msg` match Go log/slog + `JSONRenderer`
- 11 unit/integration test PASS (8 trong `test_logging_config.py` + 3 trong `test_request_id_middleware.py`)

Mọi log mới TRONG `app/` PHẢI dùng `structlog.get_logger(__name__)` thay vì
`logging.getLogger(__name__)` — JSON output + ContextVar tự inject `request_id`.
Migrate service module cũ sang structlog defer v4.0 (DEF-10-01-B — out of scope HARD-01).

---

## Reference Documents

- `.planning/PROJECT.md` — 9 key decisions D1-D9, risk register R1-R7, EXIT criteria E1-E5
- `.planning/REQUIREMENTS.md` — 38 REQ-ID M2, Traceability section
- `.planning/ROADMAP.md` — 10 phase + critical path + parallel opportunities
- `.planning/research/STACK.md` — pinned versions + alternatives + what NOT to use
- `.planning/research/ARCHITECTURE.md` — in-process cocoindex, LISTEN/NOTIFY pattern, module layout
- `.planning/research/PITFALLS.md` — 20 pitfalls với prevention + phase mapping
- `.planning/research/FEATURES.md` — feature reconciliation từ M1 → M2
- `.planning/codebase/*.md` — ⚠️ STALE snapshot codebase Go cũ (Go đã xóa 2026-05-14). Chỉ là tư liệu lịch sử — KHÔNG dùng làm reference cho Phase 5/6/7. Contract reference dùng `frontend/src/services/api.ts` + git tag `m1-go-archived`.

### EXIT Criteria reference (R3 mitigation, KHÔNG bake lại — link đến PROJECT.md)

Khi gặp blocker, đối chiếu với EXIT criteria E1-E5 trong `.planning/PROJECT.md`:

| # | Trigger | Action |
|---|---|---|
| E1 | CocoIndex critical bug no-fix 14 ngày | STOP, `/gsd-discuss-milestone` |
| E2 | pgvector p95 >2000ms ở 50K chunks dù tune | STOP, discuss Qdrant |
| E3 | Phase 1-3 vượt 21 ngày calendar | STOP, scope review |
| E4 | Hub isolation bug không fixable trong 7 ngày | STOP, security review |
| E5 | Quality gate fail <60% top-3 dù iterate 3 vòng | Stop M2b, ship M2a standalone |

**M2a EXIT GATE** giữa Phase 4 và Phase 5 — demo upload DOCX → chunks pgvector → user accept? Reject = STOP, KHÔNG pivot 3 (trừ khi E1-E5 trigger).

---

*Conventions created: 2026-05-13 (Phase 1 — CORE-05). Áp dụng từ Phase 2 trở đi.*
