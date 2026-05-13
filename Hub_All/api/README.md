# Medinet Wiki API (Python FastAPI + CocoIndex + pgvector)

Backend M2 thay thế Go monolith. Stack: FastAPI 0.136 + CocoIndex 1.0.3 +
pgvector. Chạy in-process, cocoindex `FlowLiveUpdater` start trong FastAPI
lifespan — không cần worker process riêng. Auth (JWT RS256 + Argon2), hub
registry, user management, audit log, search, answer đều handle tại đây.

Tham chiếu kiến trúc tổng thể: `../.planning/research/ARCHITECTURE.md` và
quyết định stack: `../.planning/research/STACK.md`.

## Yêu cầu môi trường

- Python 3.12 (file `.python-version` pin sẵn — uv tự nhận).
- uv ≥ 0.4.30 (cài qua `pip install uv` hoặc `winget install astral-sh.uv`).
- Docker Desktop (chạy Postgres + Redis).
- Postgres image bắt buộc `pgvector/pgvector:pg16` — plain `postgres:16` thiếu
  extension `vector` và sẽ FAIL khởi tạo cocoindex target.
- Redis 7+ (image `redis:7.4-alpine` trong docker-compose).

## Thiết lập dev

```bash
# Cài dependencies (gồm dev tools: ruff, mypy, pytest, pytest-asyncio...)
uv sync --extra dev

# Lint
uv run ruff check .

# Type check
uv run mypy app

# Test
uv run pytest
```

Chạy server local (sau khi Plan 03 wire `app.main:app`):

```bash
uv run uvicorn app.main:app --reload --port 8080
```

## Tham chiếu

- Stack pinned versions: `../.planning/research/STACK.md`
- Kiến trúc service + dataflow cocoindex: `../.planning/research/ARCHITECTURE.md`
- Pitfalls + prevention checklist: `../.planning/research/PITFALLS.md`
- Coding conventions Python (sẽ tạo ở Plan 06): `../.planning/CONVENTIONS.md`
- Roadmap 10 phase: `../.planning/ROADMAP.md`
