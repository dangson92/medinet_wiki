# MCP Service — Medinet Wiki

MCP Service là một **tiến trình độc lập** (standalone process) tách hẳn khỏi API Service. Nó expose
năng lực RAG read-only của Medinet Wiki qua giao thức **MCP (Model Context Protocol)** cho các AI
client bên ngoài (Claude Desktop, ChatGPT connectors, Cursor).

Phase 8.2 — **đảo decision D-04 của Phase 8.1**: thay vì MCP tool import và gọi trực tiếp service
layer in-process bên trong API Service, MCP Service giờ là process riêng và gọi API Service qua
**HTTP**.

## Kiến trúc sau Phase 8.2

```
Frontend  ─────────────────────────────►  API Service  ─►  DB / Redis / cocoindex
                                             ▲
LLM Agent  ─►  MCP Service  ──(HTTP)─────────┘
```

- **Frontend** gọi thẳng API Service như cũ — không liên quan MCP Service.
- **LLM Agent** kết nối MCP Service qua transport MCP (Streamable HTTP).
- **MCP Service** là process độc lập, KHÔNG truy cập DB/Redis — mọi data đi qua
  API Service bằng HTTP (kèm header `X-API-Key`).
- **API Service** là bên duy nhất sở hữu DB, Redis, cocoindex, auth verification.

Phase 8.2 **đảo decision D-04 của Phase 8.1**: Phase 8.1 mount MCP server in-process
trong API Service và tool import trực tiếp service layer. Phase 8.2 tách MCP ra
process riêng, tool gọi API Service qua HTTP — API Service không còn biết gì về MCP.

MCP Service **KHÔNG cần truy cập DB/Redis**. Nó chỉ là một lớp adapter mỏng: nhận lời gọi tool MCP,
forward sang API Service qua HTTP (kèm header `X-API-Key`), rồi trả kết quả về cho LLM Agent.

## Phụ thuộc

Package này độc lập hoàn toàn với `api/`. Dependency tối thiểu:

- `mcp` — MCP Python SDK (cùng pin `>=1.27.0,<1.28` với API Service).
- `httpx` — HTTP client gọi API Service.
- `pydantic` + `pydantic-settings` — schema và cấu hình.

**KHÔNG** có `fastapi`, `cocoindex`, `asyncpg`, `sqlalchemy` hay bất kỳ dependency nào của API Service.

## Chạy

```bash
cd Hub_All/mcp_service
uv run python -m mcp_app.server
# hoặc
python -m mcp_app.server
```

Port mặc định: **8190**.

## Biến môi trường

| Biến | Mặc định | Mô tả |
|------|----------|-------|
| `MCP_API_BASE_URL` | `http://localhost:8180` | Base URL của API Service (KHÔNG kèm `/api`). Chỉ chấp nhận scheme `http`/`https`. |
| `MCP_SERVICE_HOST` | `0.0.0.0` | Host MCP Service lắng nghe. |
| `MCP_SERVICE_PORT` | `8190` | Port MCP Service lắng nghe. |
| `MCP_HTTP_TIMEOUT` | `30` | Timeout (giây) cho mỗi request HTTP tới API Service. |

Xem `.env.example` để biết mẫu cấu hình.

## Chạy test

```bash
cd Hub_All/mcp_service
python -m pytest tests/ -q
# hoặc
uv run python -m pytest tests/ -q
```

Toàn bộ test dùng [`respx`](https://lundberg.github.io/respx/) mock các endpoint
của API Service ở tầng HTTP transport — **KHÔNG cần API Service thật chạy, KHÔNG
cần Postgres/Redis**. Bộ test gồm:

- `test_config.py` — validate Settings + base URL scheme.
- `test_api_client.py` — `ApiClient` unwrap envelope + map exception (respx).
- `test_auth.py` — trích `X-API-Key` từ header MCP.
- `test_server.py` — 3 tool, mock ở tầng `ApiClient`.
- `test_integration_tools.py` — 3 tool end-to-end qua boundary HTTP (respx mock
  API Service): verify request shape, envelope unwrap, map `ToolError`
  (`MCP_UNAUTHORIZED` / `HUB_ACCESS_DENIED`).

Lint: `python -m ruff check mcp_app/ tests/`.

## UAT thủ công — SC4 usage_events

SC4 yêu cầu: sau mỗi `ask_wiki` thành công, bảng `usage_events` của API Service có
thêm một row (do endpoint `/api/ask` ghi qua `BackgroundTasks`).

**SC4 KHÔNG verify được trong test tự động** — test `mcp_service/` dùng `respx`
mock HTTP nên không có Postgres trong vòng test. SC4 được phủ ở 2 tầng:

1. **API-side unit test** — Phase 8.2 Plan 02 Task 3 đã verify
   `background_tasks.add_task(log_usage_event, ...)` ĐƯỢC gọi khi `/api/ask` chạy
   qua đường `X-API-Key` (logic ghi usage không phụ thuộc kiểu auth).
2. **UAT thủ công** — verify row DB thật:

   1. Chạy API Service + MCP Service thật, Postgres sẵn sàng.
   2. `SELECT count(*) FROM usage_events;` — ghi lại số **trước**.
   3. Gọi `ask_wiki` qua một MCP client với header `X-API-Key` hợp lệ → nhận
      câu trả lời thành công.
   4. Đợi vài giây (`BackgroundTasks` chạy sau khi response trả về), chạy lại
      `SELECT count(*) FROM usage_events;` → số phải **tăng đúng 1**.
