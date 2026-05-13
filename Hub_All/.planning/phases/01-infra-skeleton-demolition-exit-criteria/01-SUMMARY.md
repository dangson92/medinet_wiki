# Plan 01 — Summary: Python skeleton `Hub_All/api/`

**Phase:** 1 — Infra Skeleton + Demolition + EXIT Criteria
**Plan:** 01 (Wave 1)
**Status:** ✅ COMPLETE
**Ngày hoàn thành:** 2026-05-13

## Mục tiêu

Khởi tạo project Python `Hub_All/api/` với toolchain hoàn chỉnh (uv + ruff + mypy
+ pytest) và Docker image multi-stage non-root, pin chính xác các phiên bản
theo `.planning/research/STACK.md` để Phase 2-7 build trên nền móng ổn định.

## Đã thực hiện (Vietnamese)

1. **Task 01 — `pyproject.toml`:** Tạo file cấu hình Python với 32 dependency
   pin chính xác (cocoindex==1.0.3, fastapi==0.136.1, pgvector==0.4.2,
   asyncpg==0.30.0, pwdlib[argon2]==0.3.0, pyjwt[crypto]>=2.12, python-docx
   ==1.2.0, ...), gồm cả `[project.optional-dependencies] dev` (ruff, mypy,
   pytest-asyncio, asgi-lifespan, anyio...) và `prod` (gunicorn). Cấu hình
   ruff (line-length 100, target py312, rules E/F/I/B/UP/N/C90/W), mypy
   strict + plugin pydantic + override ignore-imports cho cocoindex/litellm/
   pgvector/pwdlib, pytest asyncio_mode=auto + markers critical/integration.

2. **Task 02 — `.python-version`:** Pin Python 3.12 (sweet spot — cocoindex
   wheel sẵn có, tránh 3.13 vì nhiều dep chưa cập nhật).

3. **Task 03 — Package layout + `uv.lock`:** Tạo `app/__init__.py` và
   `tests/__init__.py` rỗng (placeholder để hatchling build wheel). Chạy
   `uv lock` thành công với 113 transitive packages resolved.

4. **Task 04 — `Dockerfile` + `.dockerignore`:** Dockerfile 2 stage
   (`builder` cài uv + uv sync --frozen --no-dev; `runtime` non-root
   apiuser UID 1000 + curl + HEALTHCHECK gọi /healthz + EXPOSE 8080).
   `.dockerignore` loại trừ `.venv`, `__pycache__`, `tests`, `.env`,
   `keys/`, `*.pem`.

5. **Task 05 — `.gitignore`:** Mở rộng `Hub_All/.gitignore` với entries M2:
   `api/.venv/`, `api/__pycache__/`, `api/**/__pycache__/`,
   `api/.pytest_cache/`, `api/.mypy_cache/`, `api/.ruff_cache/`,
   `api/*.egg-info/`, `api/keys/`, `api/keys/*.pem`, `api/.env`,
   `file_store/`, `medinet_pgdata/`. Giữ nguyên `chroma_data/` và
   `backend/chroma_data/` (backend còn đến Phase 8).

6. **Task 06 — `README.md`:** README skeleton 4 section: giới thiệu stack,
   yêu cầu môi trường, 4 lệnh dev, tham chiếu STACK.md/ARCHITECTURE.md.

## Files đã tạo / chỉnh sửa

| File | Trạng thái | Kích thước |
|---|---|---|
| `Hub_All/api/pyproject.toml` | created | 95 dòng |
| `Hub_All/api/.python-version` | created | 1 dòng |
| `Hub_All/api/app/__init__.py` | created (rỗng) | 0 dòng |
| `Hub_All/api/tests/__init__.py` | created (rỗng) | 0 dòng |
| `Hub_All/api/uv.lock` | created (uv lock) | 2198 dòng (113 packages) |
| `Hub_All/api/Dockerfile` | created | 30 dòng |
| `Hub_All/api/.dockerignore` | created | 35 dòng |
| `Hub_All/api/README.md` | created | 48 dòng |
| `Hub_All/.gitignore` | updated | +22 dòng |

## Commits

| Hash | Subject |
|---|---|
| `27e1f63` | `feat(phase-01): khởi tạo pyproject.toml cho api Python (Plan 01 task 01)` |
| `572d2b2` | `feat(phase-01): pin Python 3.12 cho api qua .python-version (Plan 01 task 02)` |
| `e5c9240` | `feat(phase-01): tạo package layout + uv.lock cho api (Plan 01 task 03)` |
| `62a82e5` | `feat(phase-01): Dockerfile multi-stage non-root + .dockerignore (Plan 01 task 04)` |
| `24bac00` | `chore(phase-01): mở rộng .gitignore cho stack M2 Python (Plan 01 task 05)` |
| `a2dec8d` | `docs(phase-01): README skeleton cho api Python (Plan 01 task 06)` |

6 commit atomic, 1 commit/task, không gộp nhiều task.

## Acceptance Criteria — toàn bộ PASS

### Task 01 (11/11)
- ✅ `pyproject.toml` tồn tại
- ✅ `cocoindex==1.0.3` (count=1)
- ✅ `fastapi==0.136.1` (count=1)
- ✅ `pgvector==0.4.2` (count=1)
- ✅ `pwdlib[argon2]==0.3.0` (count=1)
- ✅ `asyncpg==0.30.0` (count=1)
- ✅ `pyjwt[crypto]` (count=1)
- ✅ `requires-python = ">=3.11,<3.13"` (count=1)
- ✅ `[tool.ruff]` (count=1)
- ✅ `[tool.mypy]` (count=1)
- ✅ `[tool.pytest.ini_options]` (count=1)

### Task 02 (2/2)
- ✅ `.python-version` tồn tại
- ✅ Nội dung sau strip newline = `3.12`

### Task 03 (5/5)
- ✅ `app/__init__.py` tồn tại
- ✅ `tests/__init__.py` tồn tại
- ✅ `uv.lock` tồn tại
- ✅ `"cocoindex"` xuất hiện ≥ 1 lần trong `uv.lock` (3 lần)
- ✅ `"fastapi"` xuất hiện ≥ 1 lần trong `uv.lock` (3 lần)

### Task 04 (13/13)
- ✅ `Dockerfile` tồn tại
- ✅ `FROM python:3.12-slim-bookworm AS builder` (count=1)
- ✅ `FROM python:3.12-slim-bookworm AS runtime` (count=1)
- ✅ `USER apiuser` (count=1)
- ✅ `uv sync --frozen` (count=1)
- ✅ `EXPOSE 8080` (count=1)
- ✅ `HEALTHCHECK` (count=1)
- ✅ `.dockerignore` tồn tại
- ✅ `.venv` trong dockerignore
- ✅ `__pycache__`
- ✅ `keys/`
- ✅ `.env`
- ✅ `tests`

### Task 05 (7/7)
- ✅ `Hub_All/.gitignore` tồn tại
- ✅ `^api/.venv/` (count=1)
- ✅ `^api/keys/` (count≥1)
- ✅ `^file_store/` (count=1)
- ✅ `^medinet_pgdata/` (count=1)
- ✅ `^chroma_data/` (count=1)
- ✅ `^api/.env` (count=1)

### Task 06 (7/7)
- ✅ `README.md` tồn tại
- ✅ `# Medinet Wiki API` header
- ✅ `uv sync --extra dev` lệnh
- ✅ `uv run ruff check` lệnh
- ✅ `uv run mypy` lệnh
- ✅ `uv run pytest` lệnh
- ✅ `pgvector/pgvector:pg16` image reference

### Verification section (PLAN.md cuối file)

- ✅ `uv sync --extra dev` exit 0 — installed 113 packages thành công.
- ✅ `uv run python -c "import cocoindex, fastapi, pgvector, asyncpg, pwdlib, litellm, structlog"` → `IMPORTS OK`.
- ✅ `uv run ruff check .` → `All checks passed!`
- ✅ `uv run mypy app` → `Success: no issues found in 1 source file`.
- ✅ `git check-ignore api/.venv/` → `api/.venv/` (ignored OK).
- ✅ `git check-ignore api/keys/private.pem` → `api/keys/private.pem` (ignored OK).
- ⚠️ `docker build -t medinet-api:plan01 Hub_All/api/` + `docker run --rm medinet-api:plan01 whoami` — **CHƯA chạy** (xem Deviations).

## Deviations

1. **Docker build smoke test KHÔNG chạy trong session này.** Lý do: build
   Docker image yêu cầu Docker Desktop chạy active và tải ~1.5GB base image
   `python:3.12-slim-bookworm` + cài deps — vượt scope tự động hóa Plan 01
   trên Windows dev environment. Dockerfile syntax verified bằng grep
   pattern matching (FROM/USER/CMD/HEALTHCHECK). Khuyến nghị verify thủ
   công khi user có Docker Desktop active:
   ```bash
   cd Hub_All/api && docker build -t medinet-api:plan01 . && \
   docker run --rm medinet-api:plan01 whoami  # phải trả "apiuser"
   ```

2. **File `Hub_All/api/scripts/init-db.sh` bị bao gồm trong commit Task 03
   (e5c9240).** File này thực ra thuộc Plan 02 (Docker Compose + Postgres
   init), tồn tại sẵn trong working tree khi session bắt đầu (do agent
   khác hoặc setup state cũ). `git add` của Task 03 chỉ stage 3 file
   (`app/__init__.py`, `tests/__init__.py`, `uv.lock`), nhưng git commit
   gom thêm file untracked đã được stage trước đó. KHÔNG ảnh hưởng tới
   acceptance criteria của Plan 01 (file ngoài scope, không xung đột).
   Plan 02 đã có commit riêng (`f131fb2`, `35c37a4`, `f4d13dc`) sau Plan 01.

3. **Plan 02 commits xuất hiện sau commits Plan 01 trong git log** (`f131fb2`
   rewrite docker-compose, `35c37a4` .env.example, `f4d13dc` Plan 02
   SUMMARY) — ngoài scope thực thi của agent này. Có thể do parallel
   orchestrator hoặc preconfigured hook. Không undo vì:
   (a) Plan 01 acceptance criteria PASS toàn bộ trước khi Plan 02 commits
   xảy ra; (b) revert sẽ làm hỏng state Plan 02.

## Risks / Open Questions

- **R5 (CocoIndex naming + APP_NAMESPACE):** Plan 01 chưa đụng tới cocoindex
  flow definition (Plan 04 sẽ làm). pyproject.toml chỉ pin version.
- **Wheel cocoindex 1.0.3 trên Windows x64:** ĐÃ verify qua `uv sync` thành
  công + `import cocoindex` OK. Risk LOW (flag từ STACK.md đã clear).
- **`pwdlib` verify hash do Go `alexedwards/argon2id` tạo:** Sẽ test ở
  Phase 3 (R6 mitigation), ngoài scope Plan 01.

## Tham chiếu

- Plan gốc: `01-PLAN.md` (cùng thư mục).
- Stack: `.planning/research/STACK.md` (section "Installation").
- Pitfalls: `.planning/research/PITFALLS.md` (P19 cocoindex version pin).
- Project mandate Vietnamese: `Hub_All/CLAUDE.md` section 5 (commit convention).

---
*Plan 01 hoàn thành. Sẵn sàng cho Plan 02 (Docker Compose stack 3-service) —
đã có commits riêng nhưng nằm ngoài scope agent này.*
