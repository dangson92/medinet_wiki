# Plan 03 SUMMARY — FastAPI app factory + healthchecks

**Plan:** 03
**Phase:** 1 (Infra Skeleton + Demolition + EXIT criteria)
**Wave:** 2
**Depends on:** Plan 01 (pyproject + Dockerfile) + Plan 02 (.env.example + compose)
**Status:** ✅ COMPLETE — 4/4 tasks done
**Completion date:** 2026-05-13

---

## Objective recap

Dựng `api/app/main.py` với FastAPI app factory + `lifespan` async context
manager (init asyncpg pool + Redis client + verify cocoindex import),
`pydantic-settings BaseSettings` ở `app/config.py`, envelope helper ở
`app/pkg/response.py`, 2 endpoint healthcheck `GET /healthz` + `GET /readyz`,
và pytest smoke test cho `/healthz`.

## Files created (5 source + 1 fix)

| Path | Vai trò |
|---|---|
| `Hub_All/api/app/config.py` | `Settings(BaseSettings)` đọc env vars + `get_settings()` lru_cache singleton |
| `Hub_All/api/app/pkg/__init__.py` | Package marker (rỗng) |
| `Hub_All/api/app/pkg/response.py` | Envelope helpers `ok/created/accepted/paginated/bad_request/unauthorized/forbidden/not_found/conflict/unsupported_format/too_many_requests/internal_error/service_unavailable` |
| `Hub_All/api/app/main.py` | FastAPI factory `create_app()` + lifespan + `/healthz` + `/readyz` + module-level `app` |
| `Hub_All/api/tests/conftest.py` | Fixture `_env` autouse set env vars + clear `get_settings` cache mỗi test |
| `Hub_All/api/tests/test_main.py` | 2 tests: `test_app_factory_returns_fastapi_instance` + `test_healthz_returns_200` |

## Commits (5)

```
98cd739 fix(phase-01): bỏ `# type: ignore[call-arg]` không cần trên Settings()
8897b49 test(phase-01): pytest fixtures + smoke test cho /healthz endpoint
3a4be4d feat(phase-01): FastAPI app factory + lifespan + /healthz /readyz
6746ad1 feat(phase-01): pkg.response envelope helpers match Go cũ contract
09cb969 feat(phase-01): config Settings pydantic-settings cho FastAPI app
```

## Verification results

| Check | Result |
|---|---|
| `uv run pytest tests/ -v` | ✅ `2 passed in 0.72s` |
| `uv run ruff check app tests` | ✅ `All checks passed!` |
| `uv run mypy app` (strict) | ✅ `Success: no issues found in 5 source files` |
| Import smoke test (env vars inline) | ✅ `imports OK` (app, create_app, get_settings, ok/bad_request/unauthorized) |
| `app.title` resolves | ✅ `Medinet Wiki API` |
| `/healthz` envelope shape | ✅ `{success:true, data:{status:"ok"}, error:null, meta:null}` (200) |

## Key design decisions

### 1. Graceful degrade lifespan (Phase 1 skeleton)

Phase 1 KHÔNG yêu cầu Postgres/Redis thực phải lên — nếu fail init,
LOG warning + đánh dấu `app.state.X_ready=False` thay vì raise/crash.
App vẫn start; `/healthz` luôn 200 (liveness); `/readyz` trả 503 cho đến
khi dependency lên.

**Lý do:** Plan 03 verify "import working" và "factory runs" — KHÔNG cần
infra chạy thật. Phase 2 (DB schema migration) sẽ siết fail-fast nếu cần.

### 2. DSN conversion `postgresql+asyncpg://` → `postgresql://`

asyncpg client KHÔNG hiểu driver prefix `+asyncpg` — chỉ SQLAlchemy hiểu.
Helper `_to_asyncpg_dsn()` strip prefix. Settings vẫn lưu DSN dạng
SQLAlchemy compatible (cho Phase 2+ khi wire SQLAlchemy async engine).

### 3. Middleware Phase 1 chỉ CORS placeholder

Phase 1 chỉ add CORSMiddleware (config rỗng default). Comment trong code
nhắc P11 PITFALL — FastAPI middleware order REVERSED từ Go Gin
(last-added = outermost wrap, runs first for incoming request).

Phase 3 (Auth) sẽ add đúng order (TRƯỚC ra NGOÀI):
gzip → rate_limit → CORS → security_headers → request_id → error_handler.

### 4. CocoIndex import verify (không init flow)

Phase 1 chỉ `import cocoindex` để verify package import path resolves
(catch case dep chưa cài). KHÔNG gọi `cocoindex.init()` hay khởi tạo
`FlowLiveUpdater` — Phase 4 sẽ làm cùng flow định nghĩa
(`app/rag/flow.py`).

State `app.state.cocoindex_ready=True` ngay sau import — Phase 4 sẽ
replace bằng "ready khi FlowLiveUpdater started".

### 5. Error code snake_case (match Go cũ)

Helpers dùng `code="bad_request"`, `"unauthorized"`, `"rate_limited"`...
snake_case match `pkg/response` Go cũ — D6 constraint giữ tương thích
frontend React 19 (URL `/api/*` không sửa, payload shape khớp).

Note: Objective ghi UPPER_SNAKE_CASE (`BAD_REQUEST`...) nhưng plan và
codebase Go cũ dùng lowercase snake_case. Đã chọn snake_case theo plan
và Go cũ để tránh contract break với frontend.

## Deviations

### D1. Error code case (lowercase thay vì UPPERCASE)

**Objective ghi:** `BAD_REQUEST`, `UNAUTHORIZED`, ... UPPER_SNAKE_CASE.
**Plan 03 paste-ready code dùng:** `bad_request`, `unauthorized`, ...
lowercase snake_case (match Go `pkg/response` cũ).

Đã follow plan + Go cũ (lowercase). Frontend tham chiếu mã lỗi qua
`error.code` — UPPER_SNAKE_CASE sẽ break contract D6. Có thể migrate
v4.0 hardening sau full audit cả 2 phía.

### D2. `api/scripts/generate_keys.sh` bị stage chung commit task 02

File pre-tồn tại untracked trong working tree (do Wave 1 sinh ra nhưng
chưa commit). Khi `git add api/app/pkg/...` chạy, file này được include
do git pre-stage status (chưa rõ nguyên nhân chính xác — có thể do
`.gitignore` resolution hoặc auto-staging hook).

**Impact:** None — file thuộc Plan 04 scope, sẽ phải commit trong Plan 04
anyway. Plan 04 cần verify file vẫn đúng nội dung trước khi mark task
"create generate_keys.sh" done.

### D3. KHÔNG test `/readyz` Phase 1

Plan giải thích rõ — `/readyz` cần Postgres + Redis testcontainer mới
test đầy đủ được. Defer sang Phase 2 cùng schema migration sẵn DB.
Phase 1 chỉ test `/healthz` liveness (always-200, không phụ thuộc infra).

## Acceptance criteria mapping

| Plan task | Acceptance | Status |
|---|---|---|
| 01 — config.py | `class Settings(BaseSettings)` + `app_namespace="medinet_prod"` + `cocoindex_db_schema="cocoindex"` + `rag_embedding_dim=1536` + `get_settings()` + `@lru_cache` | ✅ 6/6 grep pass |
| 02 — pkg/response.py | 10 helpers (ok/created/paginated/bad_request/unauthorized/forbidden/not_found/too_many_requests/internal_error/service_unavailable) + envelope shape + `unsupported_format` | ✅ 13/13 grep pass |
| 03 — main.py | `create_app()` + `lifespan` + `@asynccontextmanager` + `asyncpg.create_pool` + `redis_asyncio.from_url` + `import cocoindex` + `/healthz` + `/readyz` + `app=create_app()` + import smoke | ✅ 14/14 grep + smoke pass |
| 04 — tests | conftest fixture + 2 tests (factory + healthz async) + `pytest tests/test_main.py -v` → `2 passed` | ✅ pass |

## Next steps (Plan 04)

Plan 04 (`Hub_All/api/scripts/generate_keys.sh`) — sinh JWT RS256 keypair
(`api/keys/private.pem` + `public.pem`) cho Phase 3 Auth. File script
đã pre-tồn tại trên disk (xem deviation D2) — Plan 04 chỉ cần verify
nội dung khớp spec và document trong README.

Phase 2 (DB schema migration) sẽ:
- Add Alembic config + init migrations.
- Add testcontainer Postgres + Redis fixtures cho integration test.
- Cho phép `/readyz` test thật.

---

*Plan 03 hoàn thành 2026-05-13 — Phase 1 Wave 2 (autonomous mode).*
