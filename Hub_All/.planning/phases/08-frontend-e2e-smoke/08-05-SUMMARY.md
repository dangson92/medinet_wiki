---
phase: 08-frontend-e2e-smoke
plan: 05
subsystem: infra
tags: [docker, cocoindex, lmdb, alembic, docker-compose, pydantic-settings]

# Dependency graph
requires:
  - phase: 04-cocoindex-flow-mvp-document-ingest
    provides: cocoindex_lmdb_path setting + setup_cocoindex() COCOINDEX_DB env wiring
provides:
  - cocoindex LMDB path tương đối an toàn (.cocoindex/state.lmdb) — không tiền tố Hub_All/
  - Dockerfile tạo+chown /app/.cocoindex cho apiuser trước khi hạ quyền
  - docker-compose ép COCOINDEX_DB tuyệt đối + named volume medinet_cocoindex_state
  - alembic.ini + migrations/ có trong Docker image — alembic upgrade head chạy được trong container
affects: [09-eval, 10-hardening]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Default config an toàn (đường dẫn tương đối) + env override tuyệt đối cho container"
    - "environment: thắng env_file: trong docker-compose để override theo môi trường"

key-files:
  created: []
  modified:
    - api/app/config.py
    - api/app/rag/setup.py
    - api/.env.example
    - api/.env
    - api/Dockerfile
    - docker-compose.yml

key-decisions:
  - "Default cocoindex_lmdb_path tương đối .cocoindex/state.lmdb — KHÔNG dùng tuyệt đối /app/... (sẽ hỏng chạy native trên Windows); container ép tuyệt đối qua env"
  - "setup.py GÁN trực tiếp os.environ[COCOINDEX_DB] thay setdefault — Settings là single source of truth, .env không bypass"
  - "Gộp fix alembic image vào plan 08-05 (user decision) — cùng file Dockerfile, cùng chặn checkpoint boot_stack.sh"
  - "Xóa 3 documents + 65 chunks rác (file_path Windows tuyệt đối) — data dev cũ, không thuộc scope code 08-05"

patterns-established:
  - "Pattern: config default an toàn 2 môi trường + env override — chạy native lẫn container không sửa code"

requirements-completed: [COMPAT-01]

# Metrics
duration: 25min
completed: 2026-05-19
---

# Phase 8 / Plan 05: Đóng gap SC5 cocoindex LMDB Permission denied

**Container python-api boot healthy không còn RuntimeError Permission denied — bỏ tiền tố Hub_All/ khỏi cocoindex LMDB path, chown /app/.cocoindex trong Dockerfile, ép COCOINDEX_DB tuyệt đối + named volume qua docker-compose; gộp thêm fix COPY alembic.ini/migrations/ vào image.**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-05-19T08:43:36+07:00
- **Completed:** 2026-05-19T08:49:39+07:00
- **Tasks:** 4 (3 auto + 1 bổ sung) + 1 human checkpoint
- **Files modified:** 6

## Accomplishments
- Gap blocker **SC5** đóng: `python-api` container boot thành công, KHÔNG còn `RuntimeError: Permission denied (os error 13)` khi cocoindex `Environment.__init__` mở LMDB.
- `docker compose up` lên healthy 3-service (`postgres` + `redis` + `python-api`); `GET /healthz` → `{"success":true,"data":{"status":"ok"}}`, `/readyz` → `cocoindex":"ok"`.
- cocoindex LMDB state persist qua `docker compose restart` (named volume `medinet_cocoindex_state`).
- Phát hiện + đóng luôn gap thứ 2 lộ ra sau khi SC5 fix: `alembic upgrade head` trong container fail vì image thiếu `alembic.ini` + `migrations/` → đã COPY vào image (verify `alembic current` = `0003 (head)`).

## Task Commits

1. **Task 1: Sửa cocoindex LMDB path (config.py + setup.py + .env + .env.example)** — `c00bd8d` (fix)
2. **Task 2: Dockerfile mkdir+chown /app/.cocoindex trước USER apiuser** — `55342a6` (fix)
3. **Task 3: docker-compose env override COCOINDEX_DB + named volume** — `23182eb` (fix)
4. **Task 3b (bổ sung): COPY alembic.ini + migrations/ vào Docker image** — `61731dd` (fix)

## Files Created/Modified
- `api/app/config.py` — default `cocoindex_lmdb_path` = `.cocoindex/state.lmdb` (bỏ tiền tố `Hub_All/`)
- `api/app/rag/setup.py` — GÁN trực tiếp `os.environ["COCOINDEX_DB"]` thay `setdefault`
- `api/.env` + `api/.env.example` — `COCOINDEX_DB=.cocoindex/state.lmdb`
- `api/Dockerfile` — `RUN mkdir -p /app/.cocoindex && chown apiuser:apiuser` trước `USER apiuser`; COPY `alembic.ini` + `migrations/`
- `docker-compose.yml` — env `COCOINDEX_DB`/`COCOINDEX_LMDB_PATH` = `/app/.cocoindex/state.lmdb` + named volume `medinet_cocoindex_state`

## Decisions Made
- Default `cocoindex_lmdb_path` tương đối, KHÔNG tuyệt đối — an toàn cả chạy native (uvicorn cwd `Hub_All/api/`) lẫn container (ép tuyệt đối qua env).
- `setup.py` GÁN trực tiếp `os.environ["COCOINDEX_DB"]` để `Settings.cocoindex_lmdb_path` là single source of truth.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Bổ sung COPY alembic.ini + migrations/ vào Docker image**
- **Found during:** Task 4 (human checkpoint — `boot_stack.sh` bước 4/6)
- **Issue:** Sau khi gap SC5 đóng, `boot_stack.sh` chạy tiếp tới bước `alembic upgrade head` trong container và fail `No 'script_location' key found` — image runtime stage chỉ `COPY app ./app`, thiếu `alembic.ini` và `migrations/`. Lỗi này trước đây bị che vì container crash startup nên script không chạy tới bước 4.
- **Fix:** Thêm `COPY --chown=apiuser:apiuser alembic.ini ./alembic.ini` và `COPY --chown=apiuser:apiuser migrations ./migrations` vào runtime stage Dockerfile.
- **Files modified:** `api/Dockerfile`
- **Verification:** Rebuild image → `docker compose exec python-api alembic upgrade head` exit 0; `alembic current` = `0003 (head)`.
- **Committed in:** `61731dd`
- **Decision authority:** User xác nhận gộp fix vào plan 08-05 (cùng file Dockerfile đã trong `files_modified`, cùng chặn checkpoint).

---

**Total deviations:** 1 auto-fixed (1 blocking, có user approval)
**Impact on plan:** Fix cần thiết để checkpoint Task 4 (`boot_stack.sh` PASS) hoàn tất. Cùng subsystem (Docker image hạ tầng), không scope creep sang frontend/code nghiệp vụ.

## Issues Encountered
- **cocoindex backfill `component build failed` × 3 (non-fatal):** Sau khi SC5 fix, log container có 3 ERROR `FileNotFoundError` — DB Postgres có 3 dòng `documents` cũ với `file_path` là đường dẫn tuyệt đối Windows (`C:\Users\...\file_store\*.docx`), không resolve được trong container Linux. KHÔNG fatal (`Application startup complete`, container healthy). Đây là data dev cũ, không phải bug code của 08-05 và không thuộc scope plan.
  - **Xử lý:** User quyết định dọn data dev — `DELETE FROM chunks` (65 dòng) + `DELETE FROM documents` (3 dòng); restart `python-api` → backfill sạch, không còn ERROR.
  - **Follow-up khuyến nghị:** `documents.file_path` nên lưu đường dẫn TƯƠNG ĐỐI theo `FILE_STORE_DIR` để portable giữa host/container — thuộc Phase 4/5, không xử lý ở đây.

## User Setup Required
None — không cần cấu hình dịch vụ ngoài.

## Verification (Task 4 — human checkpoint, đã approved)
- `bash api/scripts/smoke/boot_stack.sh` → `(6/6) Boot stack PASS` (user xác nhận "approved").
- `docker compose ps` → 3 service `healthy`.
- `curl http://localhost:8180/healthz` → `{"success":true,"data":{"status":"ok"}}`.
- `docker compose logs python-api` → KHÔNG còn `RuntimeError`/`Permission denied`/`Application startup failed`.
- `docker compose restart python-api` → healthy lại, `/healthz` vẫn OK (persist named volume).

> Lưu ý nhỏ: verify tự động Task 1 trong plan so chuỗi `str(cocoindex_lmdb_path)=='.cocoindex/state.lmdb'`; trên Windows `str(Path)` dùng `\` nên so chuỗi lệch — đã verify platform-agnostic bằng `Path('.cocoindex/state.lmdb')` (khớp); trong container Linux value là `.cocoindex/state.lmdb`.

## Next Phase Readiness
- Gap SC5 đóng → SC1 + SC2-browser của Phase 8 mở khoá để con người UAT theo `08-SMOKE-CHECKLIST.md`.
- Stack pin nguyên — 0 version thư viện bị bump; 0 file `frontend/` thay đổi (D6).
- Phase 9 (Eval Framework) không phụ thuộc plan này; sẵn sàng tiếp tục.

---
*Phase: 08-frontend-e2e-smoke*
*Completed: 2026-05-19*
