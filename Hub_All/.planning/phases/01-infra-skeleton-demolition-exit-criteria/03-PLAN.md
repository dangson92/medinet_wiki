---
plan: 03
phase: 1
wave: 2
depends_on: [01, 02]
files_modified:
  - Hub_All/api/app/__init__.py
  - Hub_All/api/app/main.py
  - Hub_All/api/app/config.py
  - Hub_All/api/app/pkg/__init__.py
  - Hub_All/api/app/pkg/response.py
  - Hub_All/api/tests/__init__.py
  - Hub_All/api/tests/conftest.py
  - Hub_All/api/tests/test_main.py
autonomous: true
requirements: [CORE-04]
---

<!--
Dependency rationale: Plan 03 chỉ cần Plan 01 (skeleton) để IMPORT được module,
nhưng Verification có bước `docker compose up -d` + `curl /healthz` đòi hỏi
Plan 02 (compose + .env.example) đã apply. Thêm `02` vào depends_on để wave
executor KHÔNG chạy verification trước khi 02 ready.
-->

# Plan 03: FastAPI app factory + lifespan + response envelope + healthcheck

## Objective
Dựng `api/app/main.py` với FastAPI app factory + `lifespan` async context manager (init/abort `cocoindex.FlowLiveUpdater` skeleton, init DB pool asyncpg, init Redis client), `pydantic-settings BaseSettings` ở `app/config.py`, envelope helper ở `app/pkg/response.py`, và 2 endpoint healthcheck `GET /healthz` + `GET /readyz` — đủ cho Plan 02 docker-compose `python-api` service lên healthy.

## Must-Haves
- `uv run python -c "from app.main import app; print(type(app).__name__)"` trong `Hub_All/api/` trả `FastAPI`.
- `curl http://localhost:8080/healthz` (sau `docker compose up`) trả HTTP 200 với body `{"success":true,"data":{"status":"ok"},"error":null,"meta":null}`.
- `curl http://localhost:8080/readyz` trả 200 khi DB pool + Redis + cocoindex updater đều ready; trả 503 khi 1 trong 3 chưa sẵn sàng.
- Pytest smoke `tests/test_main.py::test_healthz_returns_200` PASS.
- `app/config.py` đọc đủ env vars từ `.env.example` Plan 02 và validate type-safe.

## Tasks

<task id="01">
<action>
Tạo `Hub_All/api/app/config.py` với class `Settings(BaseSettings)` đọc từ env vars. Field bắt buộc khớp với `Hub_All/api/.env.example` Plan 02. Bake validation tối thiểu:
- `app_env: Literal["dev", "staging", "production"]`
- `database_url: str` (PostgresDsn cho `postgresql+asyncpg://`)
- `cocoindex_database_url: str` (DSN không async prefix)
- `redis_url: str`
- `app_namespace: str = "medinet_prod"` (cố định theo CONVENTIONS R5)
- `cocoindex_db_schema: str = "cocoindex"`
- `jwt_private_key_path: Path`, `jwt_public_key_path: Path`
- `jwt_access_token_ttl: int = 900`, `jwt_refresh_token_ttl: int = 604800`
- `file_store_dir: Path = Path("./file_store")`
- `rag_embedding_dim: int = 1536` (R1 pin)
- `log_level: str = "info"`, `log_format: str = "json"`
- `cors_allowed_origins: list[str]` (parse từ comma-separated string)

Singleton accessor `get_settings()` dùng `@lru_cache`. Nội dung paste-ready:

```python
"""Application settings — pydantic-settings BaseSettings.

Đọc env vars từ .env file (dev) hoặc OS env (prod). Type-safe, validate sớm.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Tổng hợp config runtime của Medinet Wiki API."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Runtime
    app_env: Literal["dev", "staging", "production"] = "dev"
    app_port: int = 8080
    log_level: str = "info"
    log_format: Literal["json", "console"] = "json"

    # Postgres
    database_url: str = Field(...)
    cocoindex_database_url: str = Field(...)

    # Redis
    redis_url: str = Field(...)

    # CocoIndex (R5 mitigation — cố định namespace)
    app_namespace: str = "medinet_prod"
    cocoindex_db_schema: str = "cocoindex"

    # JWT
    jwt_private_key_path: Path = Path("./keys/private.pem")
    jwt_public_key_path: Path = Path("./keys/public.pem")
    jwt_access_token_ttl: int = 900
    jwt_refresh_token_ttl: int = 604800

    # File storage
    file_store_dir: Path = Path("./file_store")

    # RAG (Phase 4-7 wiring — pin dim 1536 cho R1)
    rag_embedding_provider: str = "openai"
    rag_embedding_model: str = "text-embedding-3-small"
    rag_embedding_dim: int = 1536
    rag_llm_provider: str = "openai"
    rag_llm_model: str = "gpt-4o-mini"

    # External keys (Phase 7)
    openai_api_key: str = "sk-replace-me"
    gemini_api_key: str = "replace-me"

    # Settings encryption (Phase 5)
    aes_key: str = "replace-with-32-byte-base64-key"

    # CORS
    cors_allowed_origins: list[str] = Field(default_factory=list)

    @field_validator("cors_allowed_origins", mode="before")
    @classmethod
    def _parse_csv(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v


@lru_cache
def get_settings() -> Settings:
    """Singleton settings instance."""
    return Settings()  # type: ignore[call-arg]
```
</action>
<read_first>
- Hub_All/api/pyproject.toml
- Hub_All/api/.env.example
- Hub_All/.planning/research/STACK.md
- Hub_All/.planning/research/ARCHITECTURE.md
</read_first>
<acceptance_criteria>
- File `Hub_All/api/app/config.py` tồn tại.
- `grep -c 'class Settings(BaseSettings)' Hub_All/api/app/config.py` ≥ 1.
- `grep -c 'app_namespace: str = "medinet_prod"' Hub_All/api/app/config.py` ≥ 1.
- `grep -c 'cocoindex_db_schema: str = "cocoindex"' Hub_All/api/app/config.py` ≥ 1.
- `grep -c 'rag_embedding_dim: int = 1536' Hub_All/api/app/config.py` ≥ 1.
- `grep -c 'def get_settings' Hub_All/api/app/config.py` ≥ 1.
- `grep -c '@lru_cache' Hub_All/api/app/config.py` ≥ 1.
- `cd Hub_All/api && uv run python -c "from app.config import get_settings; s = get_settings(); print(s.app_namespace)"` chạy không exception khi có `.env` đủ vars (dev có thể skip — chỉ test khi `.env` sẵn).
</acceptance_criteria>
</task>

<task id="02">
<action>
Tạo `Hub_All/api/app/pkg/__init__.py` rỗng + `Hub_All/api/app/pkg/response.py` với envelope helpers. Mọi response của API tuân thủ shape `{"success": bool, "data": Any|None, "error": dict|None, "meta": dict|None}` để match contract Go cũ (D6 — frontend không sửa).

Nội dung paste-ready (`Hub_All/api/app/pkg/response.py`):

```python
"""Response envelope helpers — chuẩn hoá shape {success, data, error, meta} match Go cũ.

Mọi handler PHẢI return qua helper này (KHÔNG return Pydantic model raw).
"""
from __future__ import annotations

from typing import Any

from fastapi import status
from fastapi.responses import JSONResponse


def _envelope(
    *,
    success: bool,
    data: Any = None,
    error: dict[str, Any] | None = None,
    meta: dict[str, Any] | None = None,
    status_code: int,
) -> JSONResponse:
    body: dict[str, Any] = {
        "success": success,
        "data": data,
        "error": error,
        "meta": meta,
    }
    return JSONResponse(content=body, status_code=status_code)


def ok(data: Any = None, meta: dict[str, Any] | None = None) -> JSONResponse:
    return _envelope(success=True, data=data, meta=meta, status_code=status.HTTP_200_OK)


def created(data: Any = None, meta: dict[str, Any] | None = None) -> JSONResponse:
    return _envelope(success=True, data=data, meta=meta, status_code=status.HTTP_201_CREATED)


def accepted(data: Any = None, meta: dict[str, Any] | None = None) -> JSONResponse:
    return _envelope(success=True, data=data, meta=meta, status_code=status.HTTP_202_ACCEPTED)


def paginated(items: list[Any], page: int, per_page: int, total: int) -> JSONResponse:
    return _envelope(
        success=True,
        data=items,
        meta={"page": page, "per_page": per_page, "total": total},
        status_code=status.HTTP_200_OK,
    )


def _error(code: str, message: str, status_code: int, details: dict[str, Any] | None = None) -> JSONResponse:
    err: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        err["details"] = details
    return _envelope(success=False, error=err, status_code=status_code)


def bad_request(message: str, code: str = "bad_request", details: dict[str, Any] | None = None) -> JSONResponse:
    return _error(code, message, status.HTTP_400_BAD_REQUEST, details)


def unauthorized(message: str = "Yêu cầu đăng nhập", code: str = "unauthorized") -> JSONResponse:
    return _error(code, message, status.HTTP_401_UNAUTHORIZED)


def forbidden(message: str = "Không đủ quyền", code: str = "forbidden") -> JSONResponse:
    return _error(code, message, status.HTTP_403_FORBIDDEN)


def not_found(message: str = "Không tìm thấy", code: str = "not_found") -> JSONResponse:
    return _error(code, message, status.HTTP_404_NOT_FOUND)


def conflict(message: str, code: str = "conflict") -> JSONResponse:
    return _error(code, message, status.HTTP_409_CONFLICT)


def unsupported_format(message: str, code: str = "unsupported_format") -> JSONResponse:
    return _error(code, message, status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)


def too_many_requests(message: str = "Quá nhiều request", code: str = "rate_limited") -> JSONResponse:
    return _error(code, message, status.HTTP_429_TOO_MANY_REQUESTS)


def internal_error(message: str = "Lỗi máy chủ", code: str = "internal_error") -> JSONResponse:
    return _error(code, message, status.HTTP_500_INTERNAL_SERVER_ERROR)


def service_unavailable(message: str = "Dịch vụ chưa sẵn sàng", code: str = "service_unavailable") -> JSONResponse:
    return _error(code, message, status.HTTP_503_SERVICE_UNAVAILABLE)
```
</action>
<read_first>
- Hub_All/api/pyproject.toml
- Hub_All/.planning/research/ARCHITECTURE.md
- Hub_All/.planning/research/PITFALLS.md
</read_first>
<acceptance_criteria>
- File `Hub_All/api/app/pkg/__init__.py` tồn tại (có thể rỗng).
- File `Hub_All/api/app/pkg/response.py` tồn tại.
- `grep -c 'def ok' Hub_All/api/app/pkg/response.py` ≥ 1.
- `grep -c 'def created' Hub_All/api/app/pkg/response.py` ≥ 1.
- `grep -c 'def paginated' Hub_All/api/app/pkg/response.py` ≥ 1.
- `grep -c 'def bad_request' Hub_All/api/app/pkg/response.py` ≥ 1.
- `grep -c 'def unauthorized' Hub_All/api/app/pkg/response.py` ≥ 1.
- `grep -c 'def forbidden' Hub_All/api/app/pkg/response.py` ≥ 1.
- `grep -c 'def not_found' Hub_All/api/app/pkg/response.py` ≥ 1.
- `grep -c 'def too_many_requests' Hub_All/api/app/pkg/response.py` ≥ 1.
- `grep -c 'def internal_error' Hub_All/api/app/pkg/response.py` ≥ 1.
- `grep -c 'def service_unavailable' Hub_All/api/app/pkg/response.py` ≥ 1.
- `grep -c '"success": success' Hub_All/api/app/pkg/response.py` ≥ 1 (envelope shape).
- `grep -c 'unsupported_format' Hub_All/api/app/pkg/response.py` ≥ 1 (cho R4 Phase 4).
</acceptance_criteria>
</task>

<task id="03">
<action>
Tạo `Hub_All/api/app/main.py` — FastAPI app factory với `lifespan` async context manager. Lifespan PHẢI:
1. Init `asyncpg.create_pool(dsn=settings.database_url.replace("postgresql+asyncpg://", "postgresql://"), min_size=2, max_size=10)` → lưu vào `app.state.db_pool`.
2. Init `redis.asyncio.from_url(settings.redis_url, decode_responses=True)` → lưu vào `app.state.redis`. PING verify connection.
3. Init `cocoindex.FlowLiveUpdater` SKELETON (Phase 1 chưa có flow thực — chỉ test init/abort lifecycle bằng try/except, log warning nếu cocoindex chưa configured). Lưu vào `app.state.cocoindex_ready: bool` (True/False). Phase 4 sẽ thay bằng updater thực.
4. Yield → app run.
5. Shutdown: abort cocoindex updater (nếu started), close redis, close db_pool.

Healthcheck endpoint:
- `GET /healthz`: trả 200 luôn (liveness) — envelope `{success:true, data:{status:"ok"}}`.
- `GET /readyz`: kiểm tra `app.state.db_pool.acquire()` → SELECT 1, `app.state.redis.ping()`, `app.state.cocoindex_ready`. Nếu cả 3 OK → 200 với `data:{db:"ok", redis:"ok", cocoindex:"ok"}`. Nếu fail → 503 với envelope error detail.

Nội dung paste-ready:

```python
"""FastAPI app factory + lifespan — Medinet Wiki API M2.

Lifespan:
  - Init asyncpg pool (DATABASE_URL)
  - Init redis async client (REDIS_URL) + PING verify
  - Init cocoindex FlowLiveUpdater skeleton (Phase 4 sẽ wire flow thực)

Healthcheck:
  - GET /healthz — liveness (luôn 200 khi app run)
  - GET /readyz — readiness (200 khi cả 3 dependency ready, 503 ngược lại)
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

import asyncpg
import redis.asyncio as redis_asyncio
from fastapi import FastAPI

from app.config import get_settings
from app.pkg import response as resp

logger = logging.getLogger(__name__)


def _to_asyncpg_dsn(sqlalchemy_dsn: str) -> str:
    """SQLAlchemy DSN postgresql+asyncpg://... → asyncpg DSN postgresql://..."""
    return sqlalchemy_dsn.replace("postgresql+asyncpg://", "postgresql://", 1)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()

    # 1) asyncpg pool
    app.state.db_pool = await asyncpg.create_pool(
        dsn=_to_asyncpg_dsn(settings.database_url),
        min_size=2,
        max_size=10,
    )
    logger.info("db_pool_ready", extra={"min_size": 2, "max_size": 10})

    # 2) redis client
    app.state.redis = redis_asyncio.from_url(settings.redis_url, decode_responses=True)
    await app.state.redis.ping()
    logger.info("redis_ready")

    # 3) cocoindex FlowLiveUpdater skeleton (Phase 4 wire flow thực)
    app.state.cocoindex_ready = False
    try:
        import cocoindex  # noqa: F401 — verify import works

        # Phase 4 sẽ thay bằng cocoindex.init() + FlowLiveUpdater(flow_def).start()
        # Phase 1 chỉ verify package import được + đánh dấu ready.
        app.state.cocoindex_ready = True
        logger.info("cocoindex_skeleton_ready")
    except ImportError as e:
        logger.warning("cocoindex_import_failed", extra={"err": str(e)})

    try:
        yield
    finally:
        # Shutdown ngược thứ tự init
        if app.state.cocoindex_ready:
            # Phase 4: app.state.cocoindex_updater.abort()
            app.state.cocoindex_ready = False
        await app.state.redis.aclose()
        await app.state.db_pool.close()
        logger.info("lifespan_shutdown_complete")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Medinet Wiki API",
        version="0.1.0",
        lifespan=lifespan,
    )

    @app.get("/healthz")
    async def healthz() -> object:
        return resp.ok(data={"status": "ok"})

    @app.get("/readyz")
    async def readyz() -> object:
        checks: dict[str, str] = {}
        all_ok = True

        # DB check
        try:
            async with app.state.db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            checks["db"] = "ok"
        except Exception as e:  # noqa: BLE001
            checks["db"] = f"fail: {e}"
            all_ok = False

        # Redis check
        try:
            pong = await app.state.redis.ping()
            checks["redis"] = "ok" if pong else "fail"
            all_ok = all_ok and bool(pong)
        except Exception as e:  # noqa: BLE001
            checks["redis"] = f"fail: {e}"
            all_ok = False

        # CocoIndex check
        if getattr(app.state, "cocoindex_ready", False):
            checks["cocoindex"] = "ok"
        else:
            checks["cocoindex"] = "not_ready"
            all_ok = False

        if all_ok:
            return resp.ok(data=checks)
        return resp.service_unavailable(message=f"Dịch vụ chưa sẵn sàng: {checks}")

    return app


app = create_app()
```
</action>
<read_first>
- Hub_All/api/app/config.py
- Hub_All/api/app/pkg/response.py
- Hub_All/.planning/research/ARCHITECTURE.md
- Hub_All/.planning/research/PITFALLS.md
</read_first>
<acceptance_criteria>
- File `Hub_All/api/app/main.py` tồn tại.
- `grep -c 'def create_app' Hub_All/api/app/main.py` ≥ 1.
- `grep -c 'async def lifespan' Hub_All/api/app/main.py` ≥ 1.
- `grep -c '@asynccontextmanager' Hub_All/api/app/main.py` ≥ 1.
- `grep -c 'asyncpg.create_pool' Hub_All/api/app/main.py` ≥ 1.
- `grep -c 'redis_asyncio.from_url' Hub_All/api/app/main.py` ≥ 1.
- `grep -c 'import cocoindex' Hub_All/api/app/main.py` ≥ 1.
- `grep -c '/healthz' Hub_All/api/app/main.py` ≥ 1.
- `grep -c '/readyz' Hub_All/api/app/main.py` ≥ 1.
- `grep -c 'app = create_app()' Hub_All/api/app/main.py` ≥ 1.
- Set env vars inline vì Phase 1 chưa có file `.env` (defer Plan 02 hoặc copy thủ công):
  ```bash
  cd Hub_All/api && \
    DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/medinet_central \
    COCOINDEX_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/medinet_cocoindex \
    REDIS_URL=redis://localhost:6379/0 \
    uv run python -c "from app.main import app; print(app.title)"
  ```
  → trả `Medinet Wiki API` (không exception import / ValidationError).
</acceptance_criteria>
</task>

<task id="04">
<action>
Tạo `Hub_All/api/tests/conftest.py` + `Hub_All/api/tests/test_main.py` với pytest fixture cơ bản và 1 smoke test cho `/healthz`. Smoke test KHÔNG cần Postgres/Redis thực — dùng `asgi-lifespan` + `httpx.AsyncClient` với `ASGITransport` và monkey-patch lifespan để skip DB init (hoặc test endpoint trực tiếp với app rỗng — đơn giản hơn).

Cho Plan 03 (Phase 1) chỉ cần test `/healthz` always-200, KHÔNG test `/readyz` (defer Phase 2 khi có DB testcontainer).

Nội dung `Hub_All/api/tests/conftest.py`:

```python
"""Pytest fixtures cho api/tests."""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set env vars tối thiểu cho Settings load được trong unit test."""
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
    monkeypatch.setenv("COCOINDEX_DATABASE_URL", "postgresql://test:test@localhost:5432/test_cocoindex")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("APP_ENV", "dev")
    # Reset settings cache để mỗi test fresh
    from app.config import get_settings

    get_settings.cache_clear()
```

Nội dung `Hub_All/api/tests/test_main.py`:

```python
"""Smoke test cho FastAPI app factory + /healthz."""
from __future__ import annotations

import pytest


def test_app_factory_returns_fastapi_instance() -> None:
    from fastapi import FastAPI

    from app.main import create_app

    app = create_app()
    assert isinstance(app, FastAPI)
    assert app.title == "Medinet Wiki API"


@pytest.mark.asyncio
async def test_healthz_returns_200() -> None:
    """GET /healthz luôn trả 200 với envelope {success:true, data:{status:'ok'}}."""
    from httpx import ASGITransport, AsyncClient

    from app.main import create_app

    app = create_app()
    # Skip lifespan (không cần DB/Redis cho healthz liveness check).
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/healthz")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"] == {"status": "ok"}
    assert body["error"] is None
```
</action>
<read_first>
- Hub_All/api/app/main.py
- Hub_All/api/app/config.py
- Hub_All/api/pyproject.toml
</read_first>
<acceptance_criteria>
- File `Hub_All/api/tests/conftest.py` tồn tại.
- File `Hub_All/api/tests/test_main.py` tồn tại.
- `grep -c 'def test_app_factory_returns_fastapi_instance' Hub_All/api/tests/test_main.py` ≥ 1.
- `grep -c 'async def test_healthz_returns_200' Hub_All/api/tests/test_main.py` ≥ 1.
- `grep -c '"success": True' Hub_All/api/tests/test_main.py | head -1` hoặc `grep -c 'body\["success"\] is True' Hub_All/api/tests/test_main.py` ≥ 1.
- `cd Hub_All/api && uv run pytest tests/test_main.py -v` exits 0 và output có `2 passed`.
</acceptance_criteria>
</task>

## Verification
- Set env vars inline vì Phase 1 chưa có file `.env` (defer Plan 02 hoặc copy thủ công):
  ```bash
  cd Hub_All/api && \
    DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/medinet_central \
    COCOINDEX_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/medinet_cocoindex \
    REDIS_URL=redis://localhost:6379/0 \
    uv run python -c "from app.main import app, create_app; from app.config import get_settings; from app.pkg.response import ok, bad_request, unauthorized; print('imports OK')"
  ```
  → exits 0 với output `imports OK`.
- `cd Hub_All/api && uv run pytest tests/test_main.py -v` exits 0 với `2 passed`.
- `cd Hub_All/api && uv run ruff check app tests` exits 0.
- `cd Hub_All/api && uv run mypy app` exits 0.
- Khi chạy `docker compose up -d` (sau Plan 02): `curl -s http://localhost:8080/healthz | jq -r '.success'` trả `true`.
- `curl -s http://localhost:8080/healthz | jq -r '.data.status'` trả `ok`.
