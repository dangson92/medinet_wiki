# CocoIndex 1.0.3 Actual API — Research cho Plan 04-03 Replan

**Date:** 2026-05-14
**Trigger:** Plan 04-01 executor phát hiện cocoindex 1.0.3 API divergence — `cocoindex.init()`, `cocoindex.setup_flow()`, `@cocoindex.flow_def`, `cocoindex.sources.Postgres`, `cocoindex.targets.Postgres`, `cocoindex.FlowLiveUpdater`, `cocoindex.VectorIndexDef`, `cocoindex.VectorSimilarityMetric` đều **KHÔNG TỒN TẠI** trong cocoindex 1.0.3 (release 2026-05-05). Plan 04-03 (PLAN.md) viết toàn bộ code dựa trên API cocoindex 0.x — phải replan trước khi execute để tránh Rule 1/Rule 4 escalation.

**Confidence:** HIGH (verified qua source code reading direct trong `.venv/Lib/site-packages/cocoindex/` + cross-check với GitHub README + `pyproject.toml` pin `cocoindex==1.0.3` exact).

**Sources verified:**
- `Hub_All/api/.venv/Lib/site-packages/cocoindex/__version__.py` → `__version__ = "1.0.3"` + `CORE_VERSION = "1.0.3"`.
- `Hub_All/api/.venv/Lib/site-packages/cocoindex/__init__.py` re-exports từ `_internal.api`.
- `Hub_All/api/.venv/Lib/site-packages/cocoindex/_internal/api.py` (export list `__all__` line 669-759).
- `Hub_All/api/.venv/Lib/site-packages/cocoindex/_internal/environment.py` (lifespan + start/stop + Settings).
- `Hub_All/api/.venv/Lib/site-packages/cocoindex/_internal/setting.py` (`COCOINDEX_DB` env var → LMDB path, KHÔNG `COCOINDEX_DATABASE_URL`).
- `Hub_All/api/.venv/Lib/site-packages/cocoindex/_internal/app.py` (App class + AppConfig + UpdateHandle + DropHandle).
- `Hub_All/api/.venv/Lib/site-packages/cocoindex/_internal/function.py` (`fn = _FunctionDecorator()` — `@coco.fn` decorator).
- `Hub_All/api/.venv/Lib/site-packages/cocoindex/connectors/postgres/_target.py` (`mount_table_target` + `TableTarget.declare_row` + `declare_vector_index` + `TableSchema.from_class`).
- `Hub_All/api/.venv/Lib/site-packages/cocoindex/connectors/postgres/_source.py` (`PgTableSource.fetch_rows()` — read API ONLY, **KHÔNG có LISTEN/NOTIFY notification support trong 1.0.3** — docstring line 3: "Change notifications will be added later").
- `Hub_All/api/.venv/Lib/site-packages/cocoindex/ops/litellm.py` (`LiteLLMEmbedder` — built-in helper).
- `Hub_All/api/.venv/Lib/site-packages/cocoindex/ops/text.py` (`RecursiveSplitter` + `SeparatorSplitter` built-in chunkers).
- `Hub_All/api/.venv/Lib/site-packages/cocoindex/resources/chunk.py` (`Chunk`, `TextPosition` dataclass).
- GitHub README example pattern (verified via WebFetch raw README.md).

---

## TL;DR Decision Matrix — Plan 04-03 PLAN.md vs cocoindex 1.0.3 thực tế

| Plan 04-03 assumption (WRONG — cocoindex 0.x API) | Cocoindex 1.0.3 actual (CORRECT) | Source verified |
|---|---|---|
| `cocoindex.init(database_url=...)` | **KHÔNG TỒN TẠI** — dùng `cocoindex.lifespan` decorator + `coco.start()` / `start_blocking()` | `_internal/environment.py:447-465` (lifespan), `_internal/api.py:603-625` (start/start_blocking) |
| `cocoindex.setup_flow(flow)` | **KHÔNG TỒN TẠI** — schema applied tự động khi `App.update_blocking()` / `App.update()` chạy | `_internal/app.py:299-366` (App.update + update_blocking) |
| `@cocoindex.flow_def(name=...)` | **KHÔNG TỒN TẠI** — dùng `coco.App(coco.AppConfig(name=...), main_fn)` pattern | `_internal/app.py:201-270` (App + AppConfig dataclass) |
| `def flow(flow_builder, data_scope)` | **KHÔNG TỒN TẠI** — main function là plain `async def main(*args)` decorated với `@coco.fn` (optional) | README example pattern |
| `flow_builder.add_source(...)` | **KHÔNG TỒN TẠI** — source là async iterator (e.g. `localfs.walk_dir().items()` hoặc `pg_source.fetch_rows()`) consumed bởi `coco.mount_each()` | `connectors/localfs/_source.py`, `connectors/postgres/_source.py:215-227` |
| `cocoindex.sources.Postgres(...)` + `PostgresNotification(channel=...)` + `ordinal_column=...` | **KHÔNG TỒN TẠI** — `cocoindex.connectors.postgres.PgTableSource(pool, table_name=...)` chỉ có `.fetch_rows()` ONE-SHOT đọc qua `SELECT *`. **LISTEN/NOTIFY notification chưa implement trong 1.0.3** (docstring `_source.py:3-5`: "Change notifications will be added later") | `connectors/postgres/_source.py:54-227` |
| `cocoindex.targets.Postgres(table_name=...)` | **KHÔNG TỒN TẠI** — dùng `cocoindex.connectors.postgres.mount_table_target(db: ContextKey[asyncpg.Pool], table_name=..., table_schema=TableSchema, pg_schema_name=...)` | `connectors/postgres/_target.py:1332-1364` |
| `cocoindex.VectorIndexDef(field_name="vector", metric=cocoindex.VectorSimilarityMetric.COSINE_SIM)` | **KHÔNG TỒN TẠI** — dùng `table.declare_vector_index(column="vector", metric="cosine", method="hnsw", m=..., ef_construction=...)` (kwargs literal `"cosine" / "l2" / "ip"`) | `connectors/postgres/_target.py:1194-1230` |
| `chunk.export("table_name", target=..., primary_key_fields=[...], vector_indexes=[...])` | **KHÔNG TỒN TẠI** — dùng `table.declare_row(**row_dict)` cho mỗi row (PK declared trong TableSchema, vector index declared TÁCH qua `declare_vector_index`) | `connectors/postgres/_target.py:1164-1175` |
| `@cocoindex.op.function()` | **KHÔNG TỒN TẠI** — dùng `@coco.fn` (sync/async polymorphic) HAY `@coco.fn.as_async` (force async, supports batching/runner) | `_internal/function.py:2015` (`fn = _FunctionDecorator()`) |
| `cocoindex.FlowLiveUpdater(flow_obj)` + `.start()` + `.abort()` | **KHÔNG TỒN TẠI** — dùng `app.update(live=True)` returns `UpdateHandle` (Awaitable + `.watch()` async iterator + `.result()`); shutdown qua `coco.stop()` | `_internal/app.py:299-333` (App.update returns UpdateHandle), `_internal/api.py:608-620` (stop/stop_blocking) |
| `COCOINDEX_DATABASE_URL=postgres://...` | **KHÔNG TỒN TẠI** trong cocoindex 1.0.3 — dùng `COCOINDEX_DB=/path/to/lmdb` (LMDB local filesystem cho cocoindex internal state) | `_internal/setting.py:12-21` (`get_default_db_path()` đọc `COCOINDEX_DB`) |
| `APP_NAMESPACE` env var (cocoindex.Settings) | **KHÔNG TỒN TẠI** — namespace = `AppConfig.name` field (mỗi `coco.App` có name riêng, registered trong `_default_env._info`) | `_internal/app.py:201-205` (AppConfig.name) + `_internal/environment.py:150-157` (register_app) |
| `COCOINDEX_DB_SCHEMA=cocoindex` | **KHÔNG TỒN TẠI** — cocoindex 1.0.3 lưu state trong LMDB (KHÔNG Postgres). Schema target Postgres cho user data dùng `pg_schema_name=...` kwarg trong `mount_table_target` | `connectors/postgres/_target.py:1332-1364` |
| Cocoindex auto-track `content_hash` cho dedup | **MỘT PHẦN ĐÚNG** — cocoindex 1.0.3 dùng `@coco.fn(memo=True)` + `FileLike.content_fingerprint()` cho file source. Cho Postgres source row, KHÔNG có auto content-hash; phải tự ship `content_hash` trong target row | `_internal/function.py:2015`, `resources/file.py:160-176` |

**Bottom line:** **Plan 04-03 viết theo cocoindex 0.x API hoàn toàn không chạy được trên cocoindex 1.0.3.** Toàn bộ flow.py phải re-architect — không phải fix nhỏ. KHÔNG có LISTEN/NOTIFY trong 1.0.3 → architectural decision cần thiết (xem Section 9 + Open Questions).

---

## Section 1: Flow definition syntax

### 1.1 Cocoindex 1.0.3 KHÔNG có "flow" abstraction — chỉ có `App + main function`

Cocoindex 1.0 đã refactor hoàn toàn từ "flow DSL" (`flow_builder + data_scope + transform chain`) sang **"function-based App"** model:

```python
import cocoindex as coco

@coco.fn
async def main(src_path: str) -> None:
    """Main function — đây là 'flow' trong 1.0.3 mental model."""
    # ... mount targets, mount each source row, declare rows
    pass

# App = container ràng buộc 1 main_fn + name + environment
app = coco.App(coco.AppConfig(name="medinet_wiki_ingest"), main, src_path="./docs")

# Run once (sync)
app.update_blocking()  # one-shot incremental update + apply schema
# Or async equivalent:
# handle = app.update(); await handle.result()
```

**Verified pattern (README):**

```python
import cocoindex as coco
from cocoindex.connectors import localfs, postgres
from cocoindex.ops.text import RecursiveSplitter

@coco.fn(memo=True)
async def index_file(file, table):
    for chunk in RecursiveSplitter().split(await file.read_text()):
        table.declare_row(text=chunk.text, embedding=embed(chunk.text))

@coco.fn
async def main(src):
    table = await postgres.mount_table_target(PG, table_name="docs")
    table.declare_vector_index(column="embedding")
    await coco.mount_each(index_file, localfs.walk_dir(src).items(), table)

coco.App(coco.AppConfig(name="docs"), main, src="./docs").update_blocking()
```

### 1.2 No `flow_builder`, no `data_scope`

`flow_builder.add_source(...)` + `data_scope["documents"] = ...` + `with data_scope["documents"].row() as doc:` patterns **đều không tồn tại**. Thay thế:

| Cocoindex 0.x DSL | Cocoindex 1.0.3 thay thế |
|---|---|
| `flow_builder.add_source(Postgres(...))` | Async iterator: `pg_source.fetch_rows().items(key=lambda r: r["id"])` |
| `data_scope["docs"] = source` | KHÔNG cần — pass trực tiếp vào `coco.mount_each(fn, items, ...)` |
| `with data_scope["docs"].row() as doc:` | `coco.mount_each(per_row_fn, items, target)` — `per_row_fn(row, target)` được gọi cho mỗi item |
| `doc["x"].transform(my_op)` | Plain Python: gọi function trực tiếp `result = await my_op(doc.x)` (cocoindex tự memoize qua `@coco.fn`) |
| `with doc["chunks"].row() as chunk: ...` | Plain Python loop: `for chunk in chunks: table.declare_row(...)` |
| `chunk.export("chunks", target, ...)` | `table.declare_row(**row_dict)` (table mounted ngoài, PK trong TableSchema) |

### 1.3 Decorator signatures (paste-ready)

```python
# Sync function — auto-wrapped (no batching/runner)
@coco.fn
def my_sync_fn(text: str) -> bytes:
    return hashlib.sha256(text.encode()).digest()

# Async function — auto-wrapped
@coco.fn
async def my_async_fn(text: str) -> str:
    return text.upper()

# With memoization (skip re-execute if input unchanged + code hash unchanged)
@coco.fn(memo=True, version=1, logic_tracking="self")
async def expensive_op(content: str) -> bytes:
    return await call_external_api(content)

# Force async + enable batching (for embedder pattern)
@coco.fn.as_async(batching=True, max_batch_size=64)
async def embed_batch(texts: list[str]) -> list[NDArray[np.float32]]:
    return await litellm.aembedding(model="text-embedding-3-small", input=texts)
```

**Source verified:** `_internal/function.py:1768-2012` (`_FunctionDecorator` class với overloads + `fn = _FunctionDecorator()` line 2015).

---

## Section 2: Transform chain

### 2.1 No "transform chain" DSL — pure Python composition

Cocoindex 1.0.3 KHÔNG có concept "transform chain" như 0.x. Logic transform = Python composition trong main function (hoặc nested `@coco.fn` calls):

```python
@coco.fn
async def per_document(doc, table):
    """Process 1 document row from Postgres source."""
    # Step 1: extract
    extracted = await extract_text_op(doc["file_path"])  # call @coco.fn function
    if extracted.is_scanned:
        return  # router đã early-detect; defensive check
    # Step 2: chunk
    chunks = chunk_vietnamese_op(extracted.text)
    # Step 3: per-chunk: hash + embed + declare row
    for chunk_payload in chunks:
        embedding = await embedder.embed(chunk_payload.content)
        table.declare_row(
            id=uuid.uuid5(uuid.NAMESPACE_OID, f"{doc['id']}:{chunk_payload.idx}"),
            document_id=doc["id"],
            hub_id=doc["hub_id"],
            content=chunk_payload.content,
            content_hash=hashlib.sha256(chunk_payload.content.encode()).digest(),
            heading_path=chunk_payload.heading_path,
            page_start=chunk_payload.page_start,
            page_end=chunk_payload.page_end,
            metadata={"heading_path": chunk_payload.heading_path, "page_start": chunk_payload.page_start, "page_end": chunk_payload.page_end},
            vector=embedding,
        )
```

### 2.2 Return type requirement

**Op functions ĐƯỢC return bất kỳ Python type** — cocoindex 1.0.3 dùng plain Python composition, KHÔNG yêu cầu typed dataclass. NHƯNG:

- Nếu dùng `@coco.fn(memo=True)` — return type cần serializable qua `cocoindex._internal.serde` (msgspec). Dataclass / NamedTuple / Pydantic / primitives đều OK; `dict[str, Any]` cũng OK.
- Nếu pass row vào `table.declare_row(**row_dict)` — schema check chạy theo `TableSchema` (xem Section 3).
- Nếu dùng `mount_table_target` với `TableSchema.from_class(MyDataclass, primary_key=["id"])` — row PHẢI là instance của `MyDataclass` HAY `dict[str, Any]` matching field names.

**Source verified:** `connectors/postgres/_target.py:1164-1192` (`declare_row` accept dict OR object via `_row_to_dict`).

### 2.3 Custom op decorator: `@coco.fn` (NOT `@cocoindex.op.function()`)

```python
import cocoindex as coco
import hashlib

@coco.fn
def hash_op(content: str) -> bytes:
    """SHA-256 hash → bytes (cho content_hash BYTEA column)."""
    return hashlib.sha256(content.encode("utf-8")).digest()

@coco.fn
async def extract_text_op(file_path: str) -> "ExtractResult":
    """Wrap services Plan 04-02 file_extract.extract_text()."""
    text, is_scanned, meta = extract_text(Path(file_path))
    return ExtractResult(text=text, is_scanned=is_scanned, pages=int(meta.get("pages", 1)), format=str(meta.get("format", "unknown")))
```

**Verified:** `_internal/function.py:2015` `fn = _FunctionDecorator()`. Re-exported as `cocoindex.fn` (line 682 trong `_internal/api.py:__all__`).

---

## Section 3: Target export

### 3.1 `mount_table_target` API (paste-ready signature)

```python
from cocoindex.connectors.postgres import (
    mount_table_target,
    TableSchema,
    declare_table_target,
    table_target,
)
import asyncpg
import cocoindex as coco

# 1) Define a ContextKey để inject asyncpg.Pool vào target (provided ở lifespan)
PG_POOL_KEY = coco.ContextKey[asyncpg.Pool]("medinet/pg_pool")

# 2) Build TableSchema từ dataclass
@dataclass
class ChunkRow:
    id: uuid.UUID
    document_id: uuid.UUID
    hub_id: uuid.UUID
    content: str
    content_hash: bytes
    heading_path: str | None
    page_start: int | None
    page_end: int | None
    vector: Annotated[np.ndarray, embedder]  # VectorSchemaProvider — auto-resolves dim
    metadata: dict[str, Any]

# 3) Mount inside main fn
table_schema = await TableSchema.from_class(ChunkRow, primary_key=["id"])
table = await mount_table_target(
    PG_POOL_KEY,
    table_name="chunks",
    table_schema=table_schema,
    pg_schema_name="public",  # OR omitted → defaults to public
    managed_by=coco.connectorkits.target.ManagedBy.USER,  # USER = table đã tồn tại (Alembic 0001 tạo); SYSTEM = cocoindex tự CREATE TABLE
)
```

**Source verified:**
- `connectors/postgres/_target.py:1332-1364` — `async def mount_table_target(db, table_name, table_schema, *, pg_schema_name=None, managed_by=...)`.
- `connectors/postgres/_target.py:290-317` — `TableSchema.from_class(record_type, primary_key, *, column_overrides=None)`.

### 3.2 Vector index declaration — `declare_vector_index` (NOT `VectorIndexDef`)

```python
# Verified signature: connectors/postgres/_target.py:1194-1230
table.declare_vector_index(
    name=None,                # default = column name
    column="vector",          # column to index — KEYWORD `column=` NOT `field_name=`
    metric="cosine",          # Literal["cosine", "l2", "ip"]  — STRING NOT enum
    method="hnsw",            # Literal["ivfflat", "hnsw"] — defaults "ivfflat"
    m=16,                     # hnsw only
    ef_construction=64,       # hnsw only
    # lists=100,              # ivfflat only — omit cho hnsw
)
```

**CRITICAL:** Index tên thực tế = `{table_name}__vector__{name}` = `chunks__vector__vector` (default name = column name).

**⚠️ Conflict với Migration 0001:** Migration 0001 đã tạo `ix_chunks_vector_hnsw` (manual SQL — `CREATE INDEX ix_chunks_vector_hnsw ON chunks USING hnsw (vector vector_cosine_ops)`). Nếu cocoindex `declare_vector_index(column="vector")` chạy với `managed_by=USER`, cocoindex **vẫn drop+recreate index** với tên `chunks__vector__vector` (xem `_VectorIndexHandler._apply_actions` line 422-456). → Sẽ có 2 indexes trên cùng column (duplicate). **Mitigation:** xem Section 9 — KHÔNG gọi `declare_vector_index` (Alembic đã handle), HOẶC drop manual index ở Migration 0003.

### 3.3 Target Postgres class location

| Plan 04-03 path | Cocoindex 1.0.3 actual path | Notes |
|---|---|---|
| `cocoindex.targets.Postgres` | `cocoindex.connectors.postgres.mount_table_target` | function, NOT class |
| `cocoindex.targets.Postgres(table_name="chunks")` | `mount_table_target(PG_POOL_KEY, table_name="chunks", table_schema=...)` | requires asyncpg.Pool ContextKey + TableSchema |

---

## Section 4: Setup / Update / Live mode

### 4.1 `cocoindex.init()` — DOES NOT EXIST

Replacement: `coco.start()` (async) hoặc `coco.start_blocking()` (sync). Cả 2 chỉ "start the default environment" — KHÔNG nhận arguments. Configuration đến qua **`@coco.lifespan` decorator** trên 1 generator function.

```python
import cocoindex as coco
import asyncpg
from contextlib import asynccontextmanager

PG_POOL_KEY = coco.ContextKey[asyncpg.Pool]("medinet/pg_pool")

@coco.lifespan  # ← decorator register lifespan với cocoindex default env
async def cocoindex_lifespan(env_builder: coco.EnvironmentBuilder):
    """Cocoindex env startup/teardown.

    Provided values qua `env_builder.provide_async_with(KEY, async_cm)` available
    cho mọi mounted target/source qua `coco.use_context(KEY)` hoặc ContextKey injection.
    """
    pool = await asyncpg.create_pool(dsn=settings.database_url, min_size=2, max_size=10)
    env_builder.provide(PG_POOL_KEY, pool)
    try:
        yield
    finally:
        await pool.close()
```

**Verified:**
- `_internal/environment.py:447-465` (`lifespan` decorator).
- `_internal/environment.py:118-121` (`LifespanFn = Callable[[EnvironmentBuilder], Iterator[None] | AsyncIterator[None]]`).
- `_internal/environment.py:330-337` (`LazyEnvironment.lifespan(fn)` — register).

### 4.2 `cocoindex.setup_flow(flow)` — DOES NOT EXIST

Replacement: schema apply tự động khi `App.update_blocking()` / `App.update()` chạy. Không có "setup phase" tách biệt — cocoindex 1.0.3 dùng **state diff reconciliation**:

```python
app = coco.App(coco.AppConfig(name="medinet_wiki_ingest"), main, src=...)

# Sync: apply schema + run main fn one-shot
result = app.update_blocking(report_to_stdout=False, full_reprocess=False, live=False)

# Async: returns UpdateHandle
handle = app.update(full_reprocess=False, live=False)
result = await handle.result()  # OR: await handle  (UpdateHandle is Awaitable)
```

**Verified:**
- `_internal/app.py:299-333` (`App.update`).
- `_internal/app.py:335-366` (`App.update_blocking`).

### 4.3 `start()` / `start_blocking()` / `mount` / `lifespan` summary

| API | Type | Use case |
|---|---|---|
| `coco.start()` | async | Start default env (enter lifespan if registered) — usually called implicit khi `app.update()` chạy |
| `coco.start_blocking()` | sync | Sync version |
| `coco.stop()` / `coco.stop_blocking()` | async/sync | Tear down env (exit lifespan) |
| `coco.runtime()` | dual context manager | `with coco.runtime(): ...` (sync) hoặc `async with coco.runtime(): ...` (async) — lifecycle helper |
| `@coco.lifespan` | decorator | Register lifespan function on default env (only 1 — second call warns + replaces) |
| `coco.mount(fn, *args)` | async | Mount 1 background processing unit, returns `ComponentMountHandle` (await `.ready()` to wait) |
| `coco.mount_each(fn, items, ...)` | async | Mount 1 unit per item (parallel) |
| `coco.mount_target(target_state)` | async | Mount a target (e.g. table_target) — sugar over `use_mount` |
| `coco.use_mount(fn, ...)` | async | Mount + return result of fn |

**`FlowLiveUpdater` — DOES NOT EXIST.** Live mode = `app.update(live=True)` returns `UpdateHandle`; live components continue processing after initial ready. Stop = drop reference to `UpdateHandle` + call `coco.stop()` (or just exit lifespan).

### 4.4 FastAPI lifespan integration (paste-ready)

```python
# api/app/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
import asyncio
import asyncpg
import cocoindex as coco

from app.config import get_settings
from app.rag.flow import medinet_wiki_app, PG_POOL_KEY  # see Section 9

@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()

    # 1) Register cocoindex lifespan (provides asyncpg.Pool to flow target)
    @coco.lifespan
    async def _coco_lifespan(env_builder: coco.EnvironmentBuilder):
        pool = await asyncpg.create_pool(dsn=settings.cocoindex_database_url)
        env_builder.provide(PG_POOL_KEY, pool)
        try:
            yield
        finally:
            await pool.close()

    # 2) Start cocoindex env + run initial backfill (sync API in thread executor)
    await asyncio.to_thread(coco.start_blocking)

    # 3) Run app.update_blocking once (apply schema + initial backfill).
    #    For live mode (incremental periodic re-poll), set live=True.
    update_handle = medinet_wiki_app.update(live=True)
    app.state.cocoindex_update_handle = update_handle

    yield

    # 4) Shutdown: stop cocoindex (cancels pending update, exits lifespan, closes pool)
    await coco.stop()
    app.state.cocoindex_update_handle = None
```

**⚠️ CRITICAL caveat:** Cocoindex 1.0.3 KHÔNG có "live LISTEN/NOTIFY" cho Postgres source. `live=True` mode chỉ áp dụng cho `LiveComponent` classes (e.g. `LiveMapFeed` cho file watching qua `localfs.walk_dir(live=True)`). Postgres source là one-shot `SELECT *` qua `fetch_rows()`. → Để re-process khi router INSERT row mới, phải re-run `app.update()` periodically (cron) HOẶC dùng `localfs.walk_dir(live=True)` cho file-based source thay vì Postgres LISTEN/NOTIFY. **Đây là architectural blocker — xem Section 9.**

---

## Section 5: Database backend — CRITICAL re-architecture

### 5.1 Cocoindex 1.0.3 backend = LMDB (NOT Postgres for internal state)

Cocoindex 0.x dùng Postgres cho internal state (lineage, fingerprint, memo cache) — schema `cocoindex.medinet_prod__*`. Cocoindex 1.0.3 đã chuyển sang **LMDB local filesystem**:

```python
# _internal/setting.py:12-21
def get_default_db_path() -> pathlib.Path | None:
    """Get the default database path from the COCOINDEX_DB environment variable."""
    db_path = os.getenv("COCOINDEX_DB")
    return pathlib.Path(db_path) if db_path else None

@dataclass
class Settings:
    db_path: os.PathLike[str] | None = None  # LMDB path
    global_execution_options: GlobalExecutionOptions | None = None
    lmdb_max_dbs: int = 1024
    lmdb_map_size: int = 0x1_0000_0000  # 4 GiB default

# _internal/environment.py:222 (Environment __init__)
if not settings.db_path:
    raise ValueError("Settings.db_path must be provided")
```

### 5.2 Env var name: `COCOINDEX_DB` (LMDB filesystem path)

| Cocoindex 1.0.3 env var | Type | Purpose | Required |
|---|---|---|---|
| `COCOINDEX_DB` | filesystem path | LMDB directory cho cocoindex internal state (memo cache, fingerprint, lineage) | YES |
| `COCOINDEX_LMDB_MAX_DBS` | int | LMDB max databases (default 1024) | NO |
| `COCOINDEX_LMDB_MAP_SIZE` | int | LMDB map size bytes (default 4 GiB) | NO |
| `COCOINDEX_SOURCE_MAX_INFLIGHT_ROWS` | int | Source concurrency limit (default 1024) | NO |
| `COCOINDEX_SOURCE_MAX_INFLIGHT_BYTES` | int | Source concurrency limit (bytes) | NO |
| `COCOINDEX_MAX_INFLIGHT_COMPONENTS` | int | Max concurrent component instances (default 1024) | NO |
| `COCOINDEX_SERVER_ADDRESS` | "host:port" | CocoInsight UI server (default 127.0.0.1:49344) | NO (only if `cocoindex server` CLI used) |
| `COCOINDEX_SERVER_CORS_ORIGINS` | comma-separated | CocoInsight CORS | NO |
| `COCOINDEX_DATABASE_URL` | — | **DOES NOT EXIST in 1.0.3** | N/A |
| `APP_NAMESPACE` | — | **DOES NOT EXIST in 1.0.3** | N/A |
| `COCOINDEX_DB_SCHEMA` | — | **DOES NOT EXIST in 1.0.3** (target Postgres schema = `pg_schema_name=` kwarg trong `mount_table_target`) | N/A |

### 5.3 Postgres target sync from LMDB

Cocoindex 1.0.3 architecture:
- **Internal state (memo cache, fingerprint, target tracking records)**: LMDB tại `COCOINDEX_DB` path.
- **Target Postgres (chunks table)**: Standalone Postgres connection via asyncpg.Pool injected qua `ContextKey` lifespan.
- **Write flow**: `table.declare_row(...)` → cocoindex Rust core diffs against LMDB tracking record → emit upsert/delete batch → asyncpg.Pool execute (in `_RowHandler._apply_actions`).

**KEY INSIGHT:** Cocoindex 1.0.3 KHÔNG cần dedicated Postgres schema cho cocoindex state nữa. Schema isolation `cocoindex` (P7 mitigation) **không còn cần thiết** — LMDB đã isolate. Alembic `include_object` filter cocoindex schema vẫn OK (defensive — schema rỗng) nhưng KHÔNG còn purpose.

### 5.4 Setup command — there is NO "setup" step

Cocoindex 1.0.3 KHÔNG có `cocoindex setup` CLI command. Setup phase merged vào `App.update()` — first call tự apply schema diff. CLI commands chỉ có:
- `cocoindex ls [APP_TARGET | --db PATH]` — list apps
- `cocoindex show APP_TARGET [--tree]` — show stable paths
- `cocoindex update APP_TARGET [--full-reprocess] [--live] [-L]` — run update
- `cocoindex drop APP_TARGET [-f]` — drop app state + revert targets
- `cocoindex server APP_TARGET` — start CocoInsight UI

**Source verified:** `cli.py:519-808` (cli commands `ls`, `show`, `update`, `drop`, `server`).

→ Plan 04-01 `make cocoindex-setup` script bây giờ chỉ cần:
1. Set `COCOINDEX_DB` env var (LMDB path).
2. Import `app.rag.flow` (tạo `coco.App` instance + register lifespan).
3. Gọi `coco.start_blocking()` HOẶC `app.update_blocking()` (sau implies trước).

→ Plan 04-01 setup.py hiện tại (gọi `cocoindex.start_blocking()` trống) chỉ verify env init OK; KHÔNG apply chunks table schema vì chưa có `coco.App` registered. **OK cho Plan 04-01 graceful no-op pattern**, nhưng Plan 04-02 phải tạo `coco.App` instance để `update_blocking()` mới apply schema.

---

## Section 6: Memo / content-hash

### 6.1 Cocoindex 1.0.3 KHÔNG auto-track `content_hash` cho Postgres source row

Cocoindex 1.0.3 memo system dựa vào **`@coco.fn(memo=True)`** + **input/output fingerprinting**. Cho:
- **File source** (`localfs.walk_dir`): `FileLike.content_fingerprint()` = `fingerprint_bytes(file_content)` (sha256-equivalent). Auto-cache. (Source: `resources/file.py:160-176`.)
- **Postgres source** (`PgTableSource.fetch_rows()`): mỗi row là `dict[str, Any]` — fingerprinted by `_canonicalize` của entire dict. KHÔNG auto-track riêng `content_hash` column. → Phải tự ship `content_hash` trong row dict cho target.

### 6.2 Manual content_hash op (paste-ready)

```python
import hashlib
import cocoindex as coco

@coco.fn
def hash_content(content: str) -> bytes:
    """SHA-256 hash → BYTEA cho chunks.content_hash NOT NULL column."""
    return hashlib.sha256(content.encode("utf-8")).digest()
```

Dùng trong main fn:

```python
content_hash = hash_content(chunk.text)  # plain Python call (sync)
table.declare_row(
    id=...,
    document_id=...,
    hub_id=...,
    content=chunk.text,
    content_hash=content_hash,
    ...
)
```

### 6.3 Schema migration 0001 đã có `content_hash BYTEA` — ✓ verified

`Hub_All/api/migrations/versions/0001_initial_schema.py:315`:
```python
sa.Column("content_hash", sa.LargeBinary(), nullable=False),
```

→ Schema 0001 sẵn sàng. Plan 04-02/04-03 chỉ cần wire `content_hash=hash_content(content)` trong `declare_row` call.

---

## Section 7: Stable chunk_id (D-1/D-2 citation preservation)

### 7.1 Cocoindex 1.0.3 KHÔNG auto-generate chunk_id từ `(document_id, chunk_index)`

`mount_table_target` không tạo PK column — PK do **`TableSchema.primary_key=["id"]`** declare. PK value PHẢI được caller cung cấp trong `declare_row(id=..., ...)` call.

→ Để stable chunk_id qua re-index (citation preservation), **caller phải tự generate deterministic UUID5** từ `(document_id, chunk_index)`:

```python
import uuid

CHUNK_NAMESPACE = uuid.UUID("00000000-0000-0000-0000-000000000001")  # constant per app

def stable_chunk_id(document_id: uuid.UUID, chunk_index: int) -> uuid.UUID:
    """Deterministic chunk_id — same (doc_id, idx) always → same UUID. D-1/D-2 citation stable."""
    return uuid.uuid5(CHUNK_NAMESPACE, f"{document_id}:{chunk_index}")
```

### 7.2 Migration 0001 conflict — `id` có server-side default `gen_random_uuid()`

`migrations/versions/0001_initial_schema.py:307-311`:
```python
sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False,
    server_default=sa.text("gen_random_uuid()"))
```

Cocoindex `mount_table_target` với `managed_by=USER` (table đã tồn tại) sẽ INSERT `id` với value provided trong `declare_row(id=...)` → server-side default chỉ áp dụng nếu KHÔNG provide. → Stable UUID5 từ caller WILL override server-side default. ✓ OK.

**HOWEVER:** `TableSchema.from_class(ChunkRow, primary_key=["id"])` requires field `id` trong dataclass declared. → Phải khai `id: uuid.UUID` trong ChunkRow + tự generate UUID5 trước khi `declare_row`. Cocoindex sẽ TYPE-MAP `uuid.UUID → uuid` Postgres type (verified `connectors/postgres/_target.py:167` `uuid.UUID: _TypeMapping("uuid")`).

---

## Section 8: APP_NAMESPACE & db_schema

### 8.1 No `APP_NAMESPACE` env var, no `cocoindex.init(app_namespace=...)`

Cocoindex 1.0.3 namespace = **`AppConfig.name`** field. Mỗi `coco.App(coco.AppConfig(name="medinet_wiki_ingest"), main, ...)` registered trong default env's `_app_registry` qua name. Same name twice = `ValueError` (line 154 `_internal/environment.py`). → CONVENTIONS.md M2 PIN `APP_NAMESPACE = "medinet_prod"` ánh xạ thành `AppConfig.name = "medinet_prod"` (HOẶC giữ tên flow `"medinet_wiki_ingest"` — chọn 1).

### 8.2 No `COCOINDEX_DB_SCHEMA` env var

Schema target = `pg_schema_name=` kwarg trong `mount_table_target`. Multiple targets có thể dùng schema khác nhau:

```python
chunks_table = await mount_table_target(PG_POOL_KEY, table_name="chunks", table_schema=cs, pg_schema_name="public")
debug_table = await mount_table_target(PG_POOL_KEY, table_name="cocoindex_debug", table_schema=ds, pg_schema_name="cocoindex")
```

→ CONVENTIONS.md M2 chỉ định `pg_schema_name="public"` cho chunks (Alembic-managed, USER-managed in cocoindex). KHÔNG còn cần schema `cocoindex` (LMDB đã isolate state — xem Section 5.3).

### 8.3 Memo tables location

Trong cocoindex 1.0.3, memo cache nằm **trong LMDB tại `COCOINDEX_DB` path** — KHÔNG có "memo tables" trong Postgres. → Plan 04-01 truth #4 ("schema cocoindex có ít nhất 1 bảng prefix medinet_prod__") **KHÔNG còn áp dụng** cho cocoindex 1.0.3.

---

## Section 9: Plan 04-03 replan blueprint

### 9.1 Architectural decisions cần thiết TRƯỚC khi Plan 04-03 replan

**Decision A: Source pattern** — cocoindex 1.0.3 KHÔNG có Postgres LISTEN/NOTIFY. Lựa chọn:

| Option | Description | Trade-off |
|---|---|---|
| **A1: Periodic poll Postgres** | Cron hoặc `asyncio.create_task` chạy `app.update()` mỗi N giây | Latency N giây; tốn CPU; SIMPLE — verify dùng được `pg_source.fetch_rows()` |
| **A2: Switch to file-based source `localfs.walk_dir(live=True)`** | Router upload → save file vào `RAG_UPLOAD_DIR` → cocoindex `localfs` tự pick up qua `LiveMapFeed` (file watcher) | Bỏ Postgres source; documents table chỉ làm metadata catalog; complex stable-id mapping |
| **A3: Custom LiveComponent subclass** | Implement `LiveComponent` wrapping psycopg LISTEN/NOTIFY trên `documents_notify` channel; emit `LiveMapFeed[doc_id, doc_row]` | Phức tạp; cần dùng `LiveMapSubscriber`; defer post-MVP |
| **A4: Sync API call trong router** | Router upload → INSERT `documents` row → call `medinet_wiki_app.update_blocking()` synchronous trong endpoint hoặc `BackgroundTasks` | KHÔNG cần live mode; immediate processing; KHÔNG support multi-worker (mỗi worker chạy update song song = race condition) |

**Recommend:** **A1 (periodic poll, 5-10 sec interval)** cho M2a MVP — simple, works với Postgres source as-is, KHÔNG re-architect document storage. Defer A3 (Custom LiveComponent) cho hardening Phase 10.

**Decision B: Vector index ownership** — cocoindex `declare_vector_index` vs Alembic Migration 0001 `ix_chunks_vector_hnsw`. Lựa chọn:

| Option | Description |
|---|---|
| **B1: Cocoindex skip declare_vector_index, Alembic owns index** | Migration 0001 `ix_chunks_vector_hnsw` giữ. KHÔNG gọi `table.declare_vector_index(...)`. ANN search vẫn work. |
| **B2: Migration 0003 drop `ix_chunks_vector_hnsw`, cocoindex owns index `chunks__vector__vector`** | Cocoindex tự tạo + maintain. Index naming khớp cocoindex convention. |

**Recommend:** **B1** — Alembic owns DDL (P7-style isolation). Cocoindex KHÔNG cần manage vector index khi user đã setup.

**Decision C: Table managed_by** — `SYSTEM` (cocoindex CREATE TABLE) vs `USER` (Alembic CREATE TABLE, cocoindex chỉ INSERT/UPSERT/DELETE rows).

**Recommend:** **`USER`** — Alembic Migration 0001 đã tạo bảng `chunks` (10 columns đầy đủ). Cocoindex chỉ cần INSERT/UPSERT rows, KHÔNG touch DDL.

```python
from cocoindex.connectorkits import target as ck_target

table = await mount_table_target(
    PG_POOL_KEY,
    table_name="chunks",
    table_schema=table_schema,
    pg_schema_name="public",
    managed_by=ck_target.ManagedBy.USER,  # Alembic owns DDL
)
```

### 9.2 Plan 04-03 replan task breakdown (revised)

**Task 01 (NEW):** `Hub_All/api/app/rag/flow.py` — define `medinet_wiki_app` `coco.App`:

```python
"""CocoIndex 1.0.3 flow medinet_wiki_ingest — Plan 04-03 (INGEST-01..03).

Architecture (cocoindex 1.0.3 actual API):
- Source: Postgres `documents` table read qua PgTableSource.fetch_rows() — one-shot
  per app.update() call. LISTEN/NOTIFY chưa support trong 1.0.3.
- Trigger: periodic poll (Plan 04-04 router lifespan task) gọi app.update() mỗi 10s,
  OR asyncio.create_task spawn từ lifespan (Decision A1).
- Transform chain: pure Python composition trong main fn — extract → chunk → hash + embed.
- Target: chunks table USER-managed (Alembic owns DDL); cocoindex declare_row() upsert.
- Vector index: Alembic ix_chunks_vector_hnsw owns (Decision B1) — KHÔNG declare_vector_index.
"""
from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any

import asyncpg
import cocoindex as coco
from cocoindex.connectors import postgres as pg
from cocoindex.connectorkits import target as ck_target
from cocoindex.ops.litellm import LiteLLMEmbedder
import numpy as np
from numpy.typing import NDArray

from app.config import get_settings
from app.services.file_extract import extract_text
from app.services.vn_chunker import chunk_vietnamese

# === ContextKey cho asyncpg.Pool injection ===
PG_POOL_KEY = coco.ContextKey[asyncpg.Pool]("medinet/pg_pool")

# === Stable chunk_id (D-1/D-2 citation preservation) ===
CHUNK_ID_NAMESPACE = uuid.UUID("8f1a3c6e-0000-4000-a000-medinet0000")  # constant

def stable_chunk_id(document_id: uuid.UUID, chunk_index: int) -> uuid.UUID:
    """Deterministic chunk_id từ (doc_id, idx) — same input always → same UUID."""
    return uuid.uuid5(CHUNK_ID_NAMESPACE, f"{document_id}:{chunk_index}")

# === LiteLLM embedder — built-in cocoindex helper (replaces Plan 04-02 embedder.py) ===
settings = get_settings()
EMBEDDER = LiteLLMEmbedder(
    model=settings.embedding_model,  # e.g. "text-embedding-3-small"
    api_key=settings.openai_api_key,
    dimensions=1536,  # R1 mitigation pgvector 2000-dim
)

# === ChunkRow dataclass for TableSchema.from_class ===

@dataclass
class ChunkRow:
    """Row schema cho chunks table — match Migration 0001 columns.

    Cocoindex 1.0.3 type mapping (verified _target.py:139-180):
        uuid.UUID → "uuid"
        str → "text"
        bytes → "bytea"
        int → "bigint" (use Annotated[int, PgType("integer")] cho int4)
        np.ndarray → "vector(N)" via VectorSchemaProvider EMBEDDER
        dict → "jsonb"
    """
    id: uuid.UUID
    document_id: uuid.UUID
    hub_id: uuid.UUID
    content: str
    content_hash: bytes
    heading_path: str | None
    page_start: Annotated[int, pg.PgType("integer")] | None
    page_end: Annotated[int, pg.PgType("integer")] | None
    vector: Annotated[NDArray[np.float32], EMBEDDER]  # auto-resolves dim 1536 cho pgvector
    metadata: dict[str, Any]
    # `created_at`: server-side DEFAULT NOW() — KHÔNG declare ở dataclass


# === Per-document processor ===

@coco.fn
async def index_document(doc_row: dict[str, Any], table: pg.TableTarget[ChunkRow]) -> None:
    """Process 1 document row → declare N chunk rows.

    Args:
        doc_row: dict từ documents table (PgTableSource fetch_rows yields dict[str, Any]).
        table: TableTarget chunks bound qua mount_table_target trong main_fn.
    """
    doc_id = uuid.UUID(str(doc_row["id"]))
    hub_id = uuid.UUID(str(doc_row["hub_id"]))
    file_path_str = doc_row["file_path"]

    # 1) Extract text + scanned-detect
    text, is_scanned, meta = extract_text(Path(file_path_str))
    if is_scanned:
        # R4 mitigation defensive — router Plan 04-04 đã early-detect; flow skip silently
        return

    # 2) Chunk VN
    chunks = chunk_vietnamese(text)

    # 3) Per chunk: hash + embed + declare_row
    for idx, chunk_draft in enumerate(chunks):
        embedding = await EMBEDDER.embed(chunk_draft.content)
        row = ChunkRow(
            id=stable_chunk_id(doc_id, idx),
            document_id=doc_id,
            hub_id=hub_id,
            content=chunk_draft.content,
            content_hash=hashlib.sha256(chunk_draft.content.encode("utf-8")).digest(),
            heading_path=chunk_draft.heading_path,
            page_start=chunk_draft.page_start,
            page_end=chunk_draft.page_end,
            vector=embedding,
            metadata={
                "heading_path": chunk_draft.heading_path,
                "page_start": chunk_draft.page_start,
                "page_end": chunk_draft.page_end,
            },
        )
        table.declare_row(row=row)


# === Main fn: orchestrate source + target + per-row processing ===

@coco.fn
async def medinet_wiki_main() -> None:
    """Cocoindex App main fn — INGEST-01..03.

    Pull document rows from Postgres → process each (extract/chunk/embed) →
    upsert chunks. Re-run via app.update() for incremental processing.
    """
    pool = coco.use_context(PG_POOL_KEY)

    # 1) Mount target chunks table (USER-managed — Alembic owns DDL)
    chunks_schema = await pg.TableSchema.from_class(ChunkRow, primary_key=["id"])
    table = await pg.mount_table_target(
        PG_POOL_KEY,
        table_name="chunks",
        table_schema=chunks_schema,
        pg_schema_name="public",
        managed_by=ck_target.ManagedBy.USER,
    )
    # Decision B1: Alembic ix_chunks_vector_hnsw owns vector index — KHÔNG declare.
    # (Nếu chuyển B2: table.declare_vector_index(column="vector", metric="cosine", method="hnsw"))

    # 2) Mount source: Postgres documents table read
    pg_source = pg.PgTableSource(
        pool,
        table_name="documents",
        columns=["id", "hub_id", "file_path", "status"],
    )

    # 3) Mount per-document processor — parallel across documents
    await coco.mount_each(
        index_document,
        pg_source.fetch_rows().items(key=lambda r: str(r["id"])),
        table,
    )


# === App instance — registered on import ===

medinet_wiki_app = coco.App(
    coco.AppConfig(name="medinet_wiki_ingest"),
    medinet_wiki_main,
)


__all__ = [
    "ChunkRow",
    "PG_POOL_KEY",
    "medinet_wiki_app",
    "medinet_wiki_main",
    "stable_chunk_id",
]
```

**Task 02 (REVISED):** `Hub_All/api/app/rag/setup.py` — refactor cho 1.0.3 API:

```python
"""Cocoindex 1.0.3 setup helper — Plan 04-01 + 04-03.

Replace cocoindex.init() + setup_flow() (cocoindex 0.x) với:
- @coco.lifespan decorator register asyncpg.Pool injection
- coco.start_blocking() / app.update_blocking() cho one-shot setup
- coco.stop_blocking() cho clean teardown
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

import asyncpg
import cocoindex as coco

from app.config import Settings

logger = logging.getLogger(__name__)


def setup_cocoindex(settings: Settings) -> None:
    """Init cocoindex 1.0.3 default env + apply chunks schema.

    Sequence:
        1. Set COCOINDEX_DB env var (LMDB filesystem path).
        2. Register lifespan provides asyncpg.Pool to PG_POOL_KEY.
        3. Import app.rag.flow → side-effect tạo coco.App instance.
        4. coco.start_blocking() — enter lifespan + start default env.
        5. medinet_wiki_app.update_blocking() — apply chunks schema + initial backfill.

    Idempotent: chạy nhiều lần OK. App.update_blocking() là delta-only.
    """
    # 1) Set COCOINDEX_DB (LMDB path)
    os.environ.setdefault("COCOINDEX_DB", settings.cocoindex_lmdb_path)

    # 2) Register lifespan
    from app.rag.flow import PG_POOL_KEY  # type: ignore[attr-defined]

    @coco.lifespan
    async def _lifespan(env_builder: coco.EnvironmentBuilder):
        pool = await asyncpg.create_pool(
            dsn=settings.database_url,
            min_size=2,
            max_size=10,
        )
        env_builder.provide(PG_POOL_KEY, pool)
        try:
            yield
        finally:
            await pool.close()

    logger.info("cocoindex_setup_start: lmdb=%s", settings.cocoindex_lmdb_path)

    # 3) Import flow → register coco.App
    from app.rag.flow import medinet_wiki_app  # type: ignore[attr-defined]
    logger.info("cocoindex_app_registered: %s", medinet_wiki_app._name)

    # 4) Start env + apply schema
    coco.start_blocking()
    logger.info("cocoindex_default_env_started")

    # 5) One-shot update — apply chunks schema diff + initial backfill
    medinet_wiki_app.update_blocking(report_to_stdout=False)
    logger.info("cocoindex_initial_backfill_complete")


def stop_cocoindex() -> None:
    """Clean shutdown cocoindex (call ở lifespan finally)."""
    try:
        coco.stop_blocking()
        logger.info("cocoindex_default_env_stopped")
    except Exception as e:  # noqa: BLE001
        logger.warning("cocoindex_stop_failed: %s", e)
```

**Task 03 (REVISED):** `Hub_All/api/app/main.py` lifespan integration:

```python
# In api/app/main.py lifespan:

import asyncio
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()

    # ... existing JWT/Redis/DB pool init ...

    # Cocoindex 1.0.3 setup (Plan 04-03)
    try:
        from app.rag.setup import setup_cocoindex
        await asyncio.to_thread(setup_cocoindex, settings)
        app.state.cocoindex_ready = True
        logger.info("cocoindex_setup_ok")
    except Exception as e:  # noqa: BLE001
        logger.warning("cocoindex_setup_failed: %s", e)
        app.state.cocoindex_ready = False

    # Optional: spawn periodic re-poll task (Decision A1)
    # KHÔNG dùng cho M2a Phase 4 — defer Plan 04-05 watchdog hoặc Plan 04-04 router on-demand trigger.

    yield

    # Shutdown
    if app.state.cocoindex_ready:
        try:
            from app.rag.setup import stop_cocoindex
            await asyncio.to_thread(stop_cocoindex)
        except Exception as e:  # noqa: BLE001
            logger.warning("cocoindex_stop_failed: %s", e)
```

**Task 04 (REVISED):** Unit test file — assert `coco.App` registered + ChunkRow dataclass valid + main fn callable + stable_chunk_id deterministic. KHÔNG assert source `Postgres LISTEN/NOTIFY` (không tồn tại); KHÔNG assert `field_name="vector"` (không có VectorIndexDef).

### 9.3 Acceptance criteria revised

```python
# OLD (cocoindex 0.x assumption — REMOVE):
# - grep '@cocoindex.flow_def' ≥ 1
# - grep 'cocoindex.sources.Postgres' ≥ 1
# - grep 'PostgresNotification' ≥ 1
# - grep 'documents_notify' ≥ 1
# - grep 'cocoindex.targets.Postgres' ≥ 1
# - grep 'VectorSimilarityMetric.COSINE_SIM' ≥ 1
# - grep 'field_name="vector"' ≥ 1
# - grep 'cocoindex.FlowLiveUpdater' ≥ 1

# NEW (cocoindex 1.0.3 actual — USE):
# - grep 'import cocoindex as coco' ≥ 1
# - grep 'coco.App(coco.AppConfig(name="medinet_wiki_ingest")' ≥ 1
# - grep '@coco.fn' ≥ 2
# - grep 'mount_table_target' ≥ 1
# - grep 'TableSchema.from_class' ≥ 1
# - grep 'PgTableSource' ≥ 1
# - grep 'mount_each' ≥ 1
# - grep 'declare_row' ≥ 1
# - grep 'ManagedBy.USER' ≥ 1
# - grep 'PG_POOL_KEY' ≥ 1
# - grep 'stable_chunk_id' ≥ 1
# - grep '@coco.lifespan' ≥ 1
# - grep 'coco.start_blocking\|coco.stop_blocking' ≥ 1
```

---

## Open questions for human verification

### Q1: LISTEN/NOTIFY trigger pattern (BLOCKING for M2a Phase 4-5 EXIT GATE demo)

Cocoindex 1.0.3 KHÔNG support Postgres LISTEN/NOTIFY natively cho source (`_source.py:3-5` docstring confirms "Change notifications will be added later"). Decision A blocker:

- **A1 — Periodic poll cron (RECOMMEND)**: lifespan spawn `asyncio.create_task(periodic_update())` chạy `medinet_wiki_app.update()` mỗi 10s. Pros: simple, works as-is. Cons: 10s latency.
- **A2 — File-based source via localfs**: bỏ Postgres source, dùng `localfs.walk_dir(RAG_UPLOAD_DIR, live=True)`. Documents table chỉ làm metadata catalog. Pros: native live mode. Cons: re-architect storage.
- **A3 — Custom LiveComponent**: implement `LiveMapSubscriber` wrapping psycopg LISTEN. Pros: closest to original design. Cons: ~100 LOC custom code, risk.
- **A4 — Router synchronous trigger**: router upload → INSERT row → call `medinet_wiki_app.update_blocking()` trong BackgroundTasks. Pros: zero polling. Cons: KHÔNG multi-worker safe.

→ **Cần user accept Decision A trước Plan 04-03 replan.** Recommend A1 cho M2a; A4 cho dev/test.

### Q2: Vector index ownership (vital for Migration 0003 decision)

Cocoindex `declare_vector_index(column="vector")` sẽ tạo `chunks__vector__vector` index. Migration 0001 đã có `ix_chunks_vector_hnsw`. Decision B:

- **B1 — Alembic owns (RECOMMEND)**: Plan 04-03 KHÔNG gọi `declare_vector_index`. ix_chunks_vector_hnsw giữ. Cocoindex chỉ INSERT rows.
- **B2 — Cocoindex owns**: Migration 0003 drop `ix_chunks_vector_hnsw`. Plan 04-03 gọi `declare_vector_index(column="vector", metric="cosine", method="hnsw", m=16, ef_construction=64)`.

→ Recommend B1. Confirm với user.

### Q3: Embedder source — built-in `LiteLLMEmbedder` vs custom Plan 04-02 `embedder.py`?

Cocoindex 1.0.3 ship `cocoindex.ops.litellm.LiteLLMEmbedder` với:
- Built-in `@coco.fn.as_async(batching=True, max_batch_size=64)` cho `_embed`
- Built-in `@coco.fn(memo=True, version=1)` cho `embed`
- Built-in `VectorSchemaProvider` (auto-resolve dim cho pgvector column type)

Plan 04-02 (PLAN.md) định nghĩa custom `app.services.embedder.embed_text(text) -> list[float]`. Lựa chọn:

- **E1 — Use built-in `LiteLLMEmbedder`**: drop Plan 04-02 embedder.py. Pros: less code, auto-batch, auto-VectorSchema. Cons: lock-in cocoindex API; harder to test ngoài cocoindex context.
- **E2 — Keep custom embedder**: Plan 04-02 embedder.py wrap qua `@coco.fn(memo=True)`. Pros: testable standalone; flexible cho /api/search query embedding. Cons: re-implement batching.

→ Recommend **E2** (custom Plan 04-02 embedder + wrap `@coco.fn` ở Plan 04-03 flow.py). Reason: search/ask endpoints (Phase 6/7) cũng cần embed, KHÔNG nên phụ thuộc cocoindex context. Confirm với user.

### Q4: Chunker — built-in `RecursiveSplitter` vs Plan 04-02 `vn_chunker.py`?

Cocoindex `cocoindex.ops.text.RecursiveSplitter` là Rust-based syntax-aware splitter. KHÔNG có VN-specific config. Plan 04-02 define `vn_chunker.chunk_vietnamese(text)` — VN-specific (heading detection, paragraph rules).

→ Recommend **keep custom `vn_chunker`** — RecursiveSplitter generic không match VN medical wiki structure. Wrap qua `@coco.fn` trong Plan 04-03.

### Q5: `cocoindex_lmdb_path` setting field

Plan 04-01 setup.py dùng `os.environ.setdefault("COCOINDEX_DATABASE_URL", settings.cocoindex_database_url)`. Plan 04-03 cần thay bằng `os.environ.setdefault("COCOINDEX_DB", settings.cocoindex_lmdb_path)`. → Phase 1 `.env.example` + `app.config.Settings` cần thêm field `cocoindex_lmdb_path` (default `./cocoindex_lmdb`). Defer task hoặc include trong Plan 04-03 Task 02.

### Q6: Is `PgTableSource.fetch_rows()` re-callable?

Cocoindex 1.0.3 source code (`_source.py:215-227`) — `fetch_rows()` returns new `RowFetcher` mỗi call. Mỗi call mở connection acquire → `SELECT *` → repeatable_read read-only transaction → cursor stream rows. `mount_each` consume async iterator. → Verified `app.update()` re-call sẽ re-fetch rows.

**Pitfall:** Mỗi `app.update()` lần re-fetch ALL documents rows (full SELECT *). Cocoindex memo (qua `@coco.fn(memo=True)` trên `index_document`) skip re-process unchanged. NHƯNG SELECT * vẫn N rows — với 10k documents sẽ chậm. → Mitigate sau bằng `WHERE updated_at > last_run_ts` filter (cần custom subclass HOẶC cocoindex 1.1+ feature). M2a 100 docs OK.

---

## Confidence assessment

| Section | Level | Reason |
|---|---|---|
| Section 1 (Flow def) | HIGH | Verified via direct source read + GitHub README example pattern matched |
| Section 2 (Transform chain) | HIGH | `@coco.fn` decorator + `_FunctionDecorator` class verified line-for-line |
| Section 3 (Target export) | HIGH | `mount_table_target` + `TableSchema.from_class` + `declare_vector_index` signatures verified |
| Section 4 (Setup/Update/Live) | HIGH | `lifespan`, `start`, `start_blocking`, `App.update`, `update_blocking` all verified; `FlowLiveUpdater` confirmed missing via `dir(cocoindex)` |
| Section 5 (DB backend) | HIGH | `Settings.db_path`, `get_default_db_path` qua `COCOINDEX_DB` env var verified |
| Section 6 (Memo/content-hash) | MEDIUM | Generic memo verified; Postgres source row content_hash absence inferred from no auto-fingerprint code in `_source.py` |
| Section 7 (Stable chunk_id) | HIGH | UUID5 pattern standard Python; Migration 0001 schema verified |
| Section 8 (Namespace/schema) | HIGH | `AppConfig.name` + `pg_schema_name` kwarg verified; LMDB-based memo verified |
| Section 9 (Replan blueprint) | MEDIUM | Code paste-ready compiled but UNTESTED runtime — Decision A blocker for full verification |

**Overall:** HIGH confidence on API surface; MEDIUM on architectural decisions Q1-Q5 (need user input).

---

## Plan 04-03 PLAN.md status

**RECOMMENDATION:** `gsd-discuss-phase 4` re-open trước khi `gsd-plan-phase 4` re-execute. Decision A (LISTEN/NOTIFY replacement) + Decision B (vector index ownership) + Decision E (embedder built-in vs custom) là **architectural choices KHÔNG thuộc về planner discretion** — phải user accept trước.

Sau khi 5 decisions confirmed, re-run `gsd-plan-phase 4` với:
- Phase 4 ARCHITECTURE.md updated (replace Pattern 1+2 với cocoindex 1.0.3 App+lifespan+mount pattern)
- Phase 4 STACK.md updated (cocoindex 1.0.3 LMDB-based, KHÔNG schema isolation)
- Plan 04-02 embedder.py: confirm wrap pattern qua `@coco.fn` (Q3 E2)
- Plan 04-03 flow.py: rewrite full theo blueprint Section 9.2 (Task 01-04)
- Plan 04-04 router: verify on-demand `app.update()` trigger pattern (Q1 A4 fallback) hoặc background poll integration (Q1 A1)
- Plan 04-05 watchdog: revise — heartbeat update phải thuộc per-row processor (`@coco.fn` body), KHÔNG thuộc cocoindex layer

---

## RESEARCH COMPLETE

Sources:
- [cocoindex on PyPI](https://pypi.org/project/cocoindex/) — v1.0.3 verified
- [cocoindex GitHub README](https://github.com/cocoindex-io/cocoindex) — App + lifespan + mount pattern reference
- [CocoIndex Postgres docs](https://cocoindex.io/docs/targets/postgres) — target API (404 for newer paths but confirms v1.0+ structure)
- Direct source code read at `Hub_All/api/.venv/Lib/site-packages/cocoindex/` (cocoindex 1.0.3 wheel installed)
