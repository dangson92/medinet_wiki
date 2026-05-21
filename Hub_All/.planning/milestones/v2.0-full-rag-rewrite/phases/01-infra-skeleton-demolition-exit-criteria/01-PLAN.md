---
plan: 01
phase: 1
wave: 1
depends_on: []
files_modified:
  - Hub_All/api/pyproject.toml
  - Hub_All/api/uv.lock
  - Hub_All/api/Dockerfile
  - Hub_All/api/.dockerignore
  - Hub_All/api/.python-version
  - Hub_All/api/README.md
  - Hub_All/api/app/__init__.py
  - Hub_All/api/tests/__init__.py
  - Hub_All/.gitignore
autonomous: true
requirements: [CORE-01]
---

# Plan 01: Python skeleton `Hub_All/api/` (pyproject + uv + Dockerfile + lint/typecheck/test)

## Objective
Khởi tạo project Python `Hub_All/api/` với toolchain hoàn chỉnh (uv + ruff + mypy + pytest) và Docker image multi-stage non-root, pin chính xác các phiên bản theo `research/STACK.md` để Phase 2-7 build trên nền móng ổn định.

## Must-Haves
- File `Hub_All/api/pyproject.toml` tồn tại và lock đúng các phiên bản: `python>=3.11,<3.13`, `fastapi==0.136.1`, `cocoindex==1.0.3`, `pgvector==0.4.2`, `asyncpg==0.30.0`, `pyjwt[crypto]>=2.12,<3`, `pwdlib[argon2]==0.3.0`, `litellm>=1.82,<2`, `structlog>=25.0,<26`.
- Lệnh `uv run python -c "import cocoindex, fastapi, pgvector"` trong thư mục `Hub_All/api/` không phát sinh lỗi.
- File `Hub_All/api/Dockerfile` build được, image cuối chạy bằng user non-root `apiuser`.
- Cấu hình ruff + mypy + pytest đầy đủ trong `pyproject.toml`; `uv run ruff check .` và `uv run mypy app` PASS trên skeleton rỗng.
- `Hub_All/.gitignore` đã có entries cho `api/.venv/`, `api/keys/`, `file_store/`, `medinet_pgdata/`, `chroma_data/`.

## Tasks

<task id="01">
<action>
Tạo file `Hub_All/api/pyproject.toml` với nội dung paste-ready bên dưới (lấy từ `research/STACK.md` section "Installation"). PIN CHÍNH XÁC versions, không dùng `>=` cho các thư viện critical (`cocoindex`, `pgvector`, `asyncpg`, `pwdlib`, `python-docx`).

```toml
[project]
name = "medinet-wiki-api"
version = "0.1.0"
description = "Medinet Wiki M2 API — FastAPI + CocoIndex + pgvector"
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
    "gunicorn>=23,<24",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["app"]

[tool.ruff]
line-length = 100
target-version = "py312"
extend-exclude = ["migrations/versions"]

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "N", "C90", "W"]
ignore = ["E501"]

[tool.ruff.lint.per-file-ignores]
"tests/*" = ["N802", "N803"]

[tool.mypy]
python_version = "3.12"
strict = true
plugins = ["pydantic.mypy"]
ignore_missing_imports = true

[[tool.mypy.overrides]]
module = ["cocoindex.*", "litellm.*", "pgvector.*", "pwdlib.*"]
ignore_missing_imports = true

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
python_files = ["test_*.py"]
markers = [
    "critical: critical path test (auth, hub isolation, ingest, search, ask)",
    "integration: integration test requires Postgres + Redis testcontainers",
]
addopts = "-ra --strict-markers"
```
</action>
<read_first>
- Hub_All/.planning/research/STACK.md
- Hub_All/.planning/research/PITFALLS.md
</read_first>
<acceptance_criteria>
- File `Hub_All/api/pyproject.toml` tồn tại.
- `grep -c 'cocoindex==1.0.3' Hub_All/api/pyproject.toml` trả về `1`.
- `grep -c 'fastapi==0.136.1' Hub_All/api/pyproject.toml` trả về `1`.
- `grep -c 'pgvector==0.4.2' Hub_All/api/pyproject.toml` trả về `1`.
- `grep -c 'pwdlib\[argon2\]==0.3.0' Hub_All/api/pyproject.toml` trả về `1`.
- `grep -c 'asyncpg==0.30.0' Hub_All/api/pyproject.toml` trả về `1`.
- `grep -c 'pyjwt\[crypto\]' Hub_All/api/pyproject.toml` trả về `1`.
- `grep -c 'requires-python = ">=3.11,<3.13"' Hub_All/api/pyproject.toml` trả về `1`.
- `grep -c '\[tool.ruff\]' Hub_All/api/pyproject.toml` trả về `1`.
- `grep -c '\[tool.mypy\]' Hub_All/api/pyproject.toml` trả về `1`.
- `grep -c '\[tool.pytest.ini_options\]' Hub_All/api/pyproject.toml` trả về `1`.
</acceptance_criteria>
</task>

<task id="02">
<action>
Tạo file `Hub_All/api/.python-version` chứa duy nhất chuỗi `3.12` (không có newline cuối hoặc 1 newline duy nhất — `uv` accept cả 2). File này cho phép `uv` chọn đúng Python interpreter khi developer chạy lệnh trong `Hub_All/api/`.
</action>
<read_first>
- Hub_All/.planning/research/STACK.md
</read_first>
<acceptance_criteria>
- File `Hub_All/api/.python-version` tồn tại.
- Nội dung file là `3.12` (có thể kèm 1 newline cuối): `cat Hub_All/api/.python-version | tr -d '\n'` trả về chính xác `3.12`.
</acceptance_criteria>
</task>

<task id="03">
<action>
Tạo `Hub_All/api/app/__init__.py` rỗng (placeholder cho package) và `Hub_All/api/tests/__init__.py` rỗng. Đây là chỗ giữ chỗ cho Plan 03 (FastAPI app factory) — KHÔNG viết code FastAPI ở plan này, chỉ tạo package layout để `uv sync` không fail khi build wheel.

Đồng thời chạy lệnh `uv lock` trong `Hub_All/api/` để sinh file `Hub_All/api/uv.lock` (lock toàn bộ transitive deps).
</action>
<read_first>
- Hub_All/.planning/research/STACK.md
- Hub_All/.planning/research/ARCHITECTURE.md
</read_first>
<acceptance_criteria>
- File `Hub_All/api/app/__init__.py` tồn tại (có thể rỗng).
- File `Hub_All/api/tests/__init__.py` tồn tại (có thể rỗng).
- File `Hub_All/api/uv.lock` tồn tại.
- `grep -c '"cocoindex"' Hub_All/api/uv.lock` ≥ 1 (lock có entry cocoindex).
- `grep -c '"fastapi"' Hub_All/api/uv.lock` ≥ 1.
</acceptance_criteria>
</task>

<task id="04">
<action>
Tạo `Hub_All/api/Dockerfile` multi-stage với 2 stage:
- Stage 1 `builder`: base `python:3.12-slim-bookworm`, cài `uv` qua `pip install uv==0.4.30`, COPY `pyproject.toml` + `uv.lock`, chạy `uv sync --frozen --no-dev` để cài dependencies vào `/app/.venv`.
- Stage 2 `runtime`: base `python:3.12-slim-bookworm`, tạo user non-root `apiuser` UID 1000, COPY venv từ stage 1, COPY thư mục `app/`, EXPOSE 8080, CMD `["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]`.

Nội dung paste-ready:

```dockerfile
# syntax=docker/dockerfile:1.7

FROM python:3.12-slim-bookworm AS builder
ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
RUN pip install --no-cache-dir uv==0.4.30
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

FROM python:3.12-slim-bookworm AS runtime
ENV PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH=/app
RUN groupadd --system --gid 1000 apiuser \
 && useradd --system --uid 1000 --gid apiuser --create-home apiuser \
 && apt-get update \
 && apt-get install -y --no-install-recommends curl \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=builder --chown=apiuser:apiuser /app/.venv /app/.venv
COPY --chown=apiuser:apiuser app ./app
USER apiuser
EXPOSE 8080
HEALTHCHECK --interval=10s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -fsS http://localhost:8080/healthz || exit 1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

Đồng thời tạo `Hub_All/api/.dockerignore` để loại trừ `.venv`, `__pycache__`, `tests`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache`, `keys/`, `*.pem`, `.env`.
</action>
<read_first>
- Hub_All/api/pyproject.toml
- Hub_All/.planning/research/STACK.md
- Hub_All/.planning/research/ARCHITECTURE.md
</read_first>
<acceptance_criteria>
- File `Hub_All/api/Dockerfile` tồn tại.
- `grep -c 'FROM python:3.12-slim-bookworm AS builder' Hub_All/api/Dockerfile` trả về `1`.
- `grep -c 'FROM python:3.12-slim-bookworm AS runtime' Hub_All/api/Dockerfile` trả về `1`.
- `grep -c 'USER apiuser' Hub_All/api/Dockerfile` trả về `1`.
- `grep -c 'uv sync --frozen' Hub_All/api/Dockerfile` ≥ 1.
- `grep -c 'EXPOSE 8080' Hub_All/api/Dockerfile` trả về `1`.
- `grep -c 'HEALTHCHECK' Hub_All/api/Dockerfile` trả về `1`.
- File `Hub_All/api/.dockerignore` tồn tại và chứa các dòng: `.venv`, `__pycache__`, `keys/`, `.env`, `tests`.
</acceptance_criteria>
</task>

<task id="05">
<action>
Cập nhật `Hub_All/.gitignore` (nếu chưa tồn tại thì tạo mới ở `Hub_All/.gitignore` cấp Hub_All). Thêm các entries sau (nếu đã có thì skip dòng đó, không trùng lặp):

```
# Python venv & cache (M2 stack)
api/.venv/
api/__pycache__/
api/**/__pycache__/
api/.pytest_cache/
api/.mypy_cache/
api/.ruff_cache/
api/*.egg-info/

# Secrets (M2)
api/keys/
api/keys/*.pem
api/.env

# File store (local uploads)
file_store/

# Postgres data volume
medinet_pgdata/

# Legacy M1 data (deleted Plan 05 nhưng giữ ignore phòng tái sinh)
chroma_data/
```

Lưu ý: `backend/keys/` đã có ignore từ M1 — giữ nguyên, KHÔNG xóa entry đó (backend/ còn đến Phase 8).
</action>
<read_first>
- Hub_All/.gitignore
- Hub_All/CLAUDE.md
</read_first>
<acceptance_criteria>
- File `Hub_All/.gitignore` tồn tại.
- `grep -c '^api/.venv/' Hub_All/.gitignore` ≥ 1.
- `grep -c '^api/keys/' Hub_All/.gitignore` ≥ 1.
- `grep -c '^file_store/' Hub_All/.gitignore` ≥ 1.
- `grep -c '^medinet_pgdata/' Hub_All/.gitignore` ≥ 1.
- `grep -c '^chroma_data/' Hub_All/.gitignore` ≥ 1.
- `grep -c '^api/.env' Hub_All/.gitignore` ≥ 1.
</acceptance_criteria>
</task>

<task id="06">
<action>
Tạo `Hub_All/api/README.md` với 4 section ngắn (~30-40 dòng):

1. `# Medinet Wiki API (Python FastAPI + CocoIndex + pgvector)` — 1 đoạn giới thiệu (Vietnamese có dấu): "Backend M2 thay thế Go monolith. Stack: FastAPI 0.136 + CocoIndex 1.0.3 + pgvector. Chạy in-process, cocoindex `FlowLiveUpdater` start trong FastAPI lifespan."
2. `## Yêu cầu môi trường` — bullet: Python 3.12, uv ≥ 0.4.30, Docker Desktop, Postgres image `pgvector/pgvector:pg16`.
3. `## Thiết lập dev` — fenced code block với 4 lệnh: `uv sync --extra dev`, `uv run ruff check .`, `uv run mypy app`, `uv run pytest`.
4. `## Tham chiếu` — bullet trỏ về `../.planning/research/STACK.md`, `../.planning/research/ARCHITECTURE.md`, `../.planning/CONVENTIONS.md` (file sẽ tạo ở Plan 06).
</action>
<read_first>
- Hub_All/api/pyproject.toml
- Hub_All/.planning/research/STACK.md
</read_first>
<acceptance_criteria>
- File `Hub_All/api/README.md` tồn tại.
- `grep -c '# Medinet Wiki API' Hub_All/api/README.md` ≥ 1.
- `grep -c 'uv sync --extra dev' Hub_All/api/README.md` ≥ 1.
- `grep -c 'uv run ruff check' Hub_All/api/README.md` ≥ 1.
- `grep -c 'uv run mypy' Hub_All/api/README.md` ≥ 1.
- `grep -c 'uv run pytest' Hub_All/api/README.md` ≥ 1.
- `grep -c 'pgvector/pgvector:pg16' Hub_All/api/README.md` ≥ 1.
</acceptance_criteria>
</task>

## Verification
- `cd Hub_All/api && uv sync --extra dev` exits 0.
- `cd Hub_All/api && uv run python -c "import cocoindex, fastapi, pgvector, asyncpg, pwdlib, litellm, structlog"` exits 0.
- `cd Hub_All/api && uv run ruff check .` exits 0 (skeleton rỗng = no findings).
- `cd Hub_All/api && uv run mypy app` exits 0 (skeleton rỗng).
- `docker build -t medinet-api:plan01 Hub_All/api/` exits 0 và image cuối có user `apiuser`: `docker run --rm medinet-api:plan01 whoami` trả `apiuser`.
- `git check-ignore Hub_All/api/.venv/` exits 0 (ignored).
- `git check-ignore Hub_All/api/keys/private.pem` exits 0 (ignored).
