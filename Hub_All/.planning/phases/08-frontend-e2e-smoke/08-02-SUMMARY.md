---
phase: 08-frontend-e2e-smoke
plan: 02
subsystem: api
tags: [compat, fastapi, llm, litellm, cors, docker-compose, port-mapping, react]

# Dependency graph
requires:
  - phase: 08-frontend-e2e-smoke
    provides: 08-CONTRACT-DIFF.md — danh sách gap api-side (1 BLOCKER /api/ai/chat + 2 FIX-API)
  - phase: 07-ask-api
    provides: ask_service._resolve_llm_model() + pattern router ask.py (limiter, envelope)
  - phase: 03-auth-rbac-envelope
    provides: get_current_user dependency + response envelope {success, data, error, meta}
  - phase: 05-hub-user-audit-apikey-settings
    provides: middleware SEARCH_LIMIT + limiter (slowapi)
provides:
  - "Port host 8180 → container 8080 ở docker-compose + Makefile dev + config default — frontend api.ts reach backend không sửa frontend (D6)"
  - "Router POST /api/ai/chat — proxy LLM cho GeminiAssistant (BLOCKER 08-CONTRACT-DIFF đóng)"
  - "CORS dev origin localhost:5173 (Vite 6) — validator _no_lan_in_prod giữ nguyên"
affects: [08-03, 08-04]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Router proxy LLM tối giản tách hàm lõi run_ai_chat khỏi endpoint FastAPI để unit test thuần Python mock litellm.acompletion"
    - "Chuẩn hoá role model→assistant — bắc cầu quy ước Gemini frontend ↔ chuẩn OpenAI LiteLLM"
    - "Port mapping host≠container ở compose — giữ Dockerfile/uvicorn nội bộ 8080, chỉ map ở compose layer"

key-files:
  created:
    - api/app/routers/ai_chat.py
    - api/tests/unit/test_ai_chat.py
  modified:
    - docker-compose.yml
    - api/Makefile
    - api/.env.example
    - api/app/config.py
    - api/app/routers/__init__.py
    - api/app/main.py

decisions:
  - "Makefile chưa có target `dev` → THÊM mới target `dev` chạy uvicorn local native --port 8180 (plan dự kiến sửa target có sẵn; thực tế phải tạo)"
  - "Resolve LLM model: import _resolve_llm_model() từ ask_service (hàm `_`-prefix private nhưng import được) — KHÔNG copy logic, hot-swap ASK-04 hiệu lực ngay"
  - "Chuẩn hoá role `model`→`assistant`: GeminiAssistant gửi role `model` (quy ước Gemini); LiteLLM/OpenAI dùng `assistant` — map để tránh provider reject"
  - "Lỗi LLM map qua resp.internal_error(code=LLM_FAILED) — nhất quán với ask.py D-07-04-F (response.py không có helper bad_gateway)"

metrics:
  duration: ~4 phút
  completed: 2026-05-18
  tasks: 2
  files-created: 2
  files-modified: 6
---

# Phase 8 Plan 02: Đóng gap api-side Frontend ↔ FastAPI Summary

Đóng 1 BLOCKER (`POST /api/ai/chat` cho GeminiAssistant) + port mapping 8180 cho frontend `api.ts` — fix hoàn toàn phía `api/` + hạ tầng, KHÔNG đụng `frontend/` (D6).

## Kết quả

Plan 08-02 (Wave 2) đóng các gap api-side mà Plan 08-01 phát hiện trong `08-CONTRACT-DIFF.md`:

- **BLOCKER `/api/ai/chat`** — GeminiAssistant trên golden path Dashboard trước đây gọi endpoint không tồn tại (404). Nay có router proxy LLM tối giản trả envelope `{success, data: {response}, error, meta}` đúng contract frontend kỳ vọng.
- **Port 8180** — frontend `api.ts` hardcode `http://<hostname>:8180` (Hyper-V excluded range 8038-8137 trên Windows). Backend nay được map ở 8180 qua docker-compose + Makefile `dev` + config default — frontend reach backend mà không sửa file nào trong `frontend/`.
- **CORS dev origin** — `localhost:5173` (Vite 6 dev server) đã có sẵn trong `.env.example`; validator `_no_lan_in_prod` giữ nguyên (production vẫn reject localhost/LAN — P12).

Bao phủ ROADMAP Phase 8 SC1 (boot stack đúng port) + SC5 (docker compose 3-service healthy, không service Go).

## Tasks hoàn thành

| Task | Tên | Loại | Commit | Files |
| ---- | --- | ---- | ------ | ----- |
| 1 | Map port host 8180 + CORS dev origin | auto | `af70241` | docker-compose.yml, api/Makefile, api/.env.example, api/app/config.py |
| 2 (RED) | Unit test thất bại cho /api/ai/chat | tdd | `3434bac` | api/tests/unit/test_ai_chat.py |
| 2 (GREEN) | Router POST /api/ai/chat proxy LLM | tdd | `a203092` | api/app/routers/ai_chat.py, api/app/routers/__init__.py, api/app/main.py, api/tests/unit/test_ai_chat.py |

## Chi tiết kỹ thuật

### Task 1 — Port mapping 8180

- **docker-compose.yml** — `python-api` ports `8080:8080` → `8180:8080`. Container nội bộ + `Dockerfile` (`EXPOSE 8080`, `uvicorn --port 8080`) GIỮ NGUYÊN — chỉ map ở compose layer. `docker compose config` parse OK: 3 service (postgres, redis, python-api), không service Go.
- **api/Makefile** — thêm target `dev` (chạy `uv run uvicorn app.main:app --reload --port 8180` native, không Docker — theo MEMORY "Chạy backend local nhanh"). Xem Deviation #1.
- **api/.env.example** — `APP_PORT` 8080 → 8180 + comment giải thích. `CORS_ALLOWED_ORIGINS` đã có `http://localhost:5173,http://localhost:3000` — bổ sung comment Vite 6.
- **api/app/config.py** — `app_port` default 8080 → 8180. Validator `_no_lan_in_prod` KHÔNG đụng.

### Task 2 — Router POST /api/ai/chat

- **api/app/routers/ai_chat.py** — `APIRouter(tags=["ai"])` không prefix, path tuyệt đối `/api/ai/chat`. 1 endpoint:
  - JWT bắt buộc qua `Depends(get_current_user)` → 401 nếu thiếu/sai token (T-08-02-02).
  - `@limiter.limit(SEARCH_LIMIT)` (100/min/user) chống abuse đẩy chi phí LLM (T-08-02-03).
  - Schema inline Pydantic v2: `AiChatMessage`, `AiChatRequest`, `AiChatResponse`.
  - Hàm lõi `run_ai_chat(body)` tách khỏi endpoint FastAPI → unit test thuần Python mock `litellm.acompletion` không cần ASGI app/DB.
  - Resolve model qua `_resolve_llm_model()` import từ `ask_service` (hot-swap ASK-04 — đọc `get_settings()` mỗi lần gọi).
  - Chuẩn hoá role `model` → `assistant` (GeminiAssistant gửi `model` theo quy ước Gemini; LiteLLM dùng `assistant`).
  - Lỗi provider → `resp.internal_error(code="LLM_FAILED")`, message generic, log KHÔNG chứa nội dung message người dùng (T-08-02-04 PII-safe).
- **Wire** — `routers/__init__.py` re-export `ai_chat_router`; `main.py` `include_router(ai_chat_router)` sau `ask_router`.
- **Test** — `tests/unit/test_ai_chat.py`, 5 unit test pure-Python (1 `@pytest.mark.critical`): messages rỗng → 400 INVALID_REQUEST; acompletion mock → 200 `{response}`; acompletion raise → 500 LLM_FAILED không leak; system_instruction prepend role `system`; role `model` → `assistant`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Makefile chưa có target `dev`**
- **Found during:** Task 1
- **Issue:** Plan dự kiến sửa cờ port trong target `dev` có sẵn của `api/Makefile`. Thực tế Makefile KHÔNG có target `dev` nào — chỉ có `install`, `keys`, `lint`, `test`, `migrate-*`, `cocoindex-setup`.
- **Fix:** Thêm mới target `dev` chạy `uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8180` (theo MEMORY "Chạy backend local nhanh" — uvicorn native, Postgres/Redis trong Docker). Cập nhật `.PHONY`.
- **Files modified:** api/Makefile
- **Commit:** `af70241`

Plan đã lường trước tình huống này ("Nếu target `dev`..."), nên đây là điều chỉnh trong scope chứ không phải gap thật.

## Verification

- ✅ `grep 8180:8080 docker-compose.yml` khớp 1 dòng (service python-api)
- ✅ `grep APP_PORT=8180 api/.env.example` khớp; `grep 5173` khớp (CORS dev origin)
- ✅ `grep "app_port: int = 8180" api/app/config.py` khớp
- ✅ `api/Dockerfile` KHÔNG đổi (`git diff` rỗng)
- ✅ `docker compose config` parse OK — 3 service, không service Go
- ✅ `create_app()` route list chứa `/api/ai/chat` (in `mounted OK`)
- ✅ `ai_chat_router` xuất hiện trong `main.py` + `routers/__init__.py`
- ✅ `pytest tests/unit/test_ai_chat.py` — 5 passed (1 `@pytest.mark.critical`)
- ✅ `ruff check` exit 0 trên file mới + file sửa
- ✅ `mypy --strict api/app/routers/ai_chat.py` — Success, no issues
- ✅ `git diff --name-only` KHÔNG chứa path `frontend/` — D6 tuân thủ tuyệt đối
- ✅ KHÔNG có file deletion nào trong 3 commit của plan

## TDD Gate Compliance

- RED gate: `3434bac` — `test(08-02)` commit, test FAIL (`ModuleNotFoundError: app.routers.ai_chat`).
- GREEN gate: `a203092` — `feat(08-02)` commit, 5 test PASS.
- REFACTOR: không cần — code đã sạch ngay GREEN (chỉ gỡ 1 hàm helper chết `_body` trong test trước khi commit GREEN).

## Known Stubs

Không có stub. Router `/api/ai/chat` gọi LiteLLM thật (live khi có API key hợp lệ trong `.env`). Unit test mock `litellm.acompletion` là test-double hợp lệ, không phải stub production.

## Self-Check: PASSED

- FOUND: api/app/routers/ai_chat.py
- FOUND: api/tests/unit/test_ai_chat.py
- FOUND: commit af70241 (fix port mapping)
- FOUND: commit 3434bac (test RED)
- FOUND: commit a203092 (feat GREEN)
