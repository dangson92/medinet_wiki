# MCP Service — Medinet Wiki

MCP Service là một **tiến trình độc lập** (standalone process) tách hẳn khỏi API Service. Nó expose
năng lực RAG read-only của Medinet Wiki qua giao thức **MCP (Model Context Protocol)** cho các AI
client bên ngoài (Claude Desktop, ChatGPT connectors, Cursor).

Phase 8.2 — **đảo decision D-04 của Phase 8.1**: thay vì MCP tool import và gọi trực tiếp service
layer in-process bên trong API Service, MCP Service giờ là process riêng và gọi API Service qua
**HTTP**.

## Kiến trúc

```
LLM Agent ─► MCP Service ─► API Service (HTTP)
```

- **LLM Agent** kết nối vào MCP Service qua transport MCP (Streamable HTTP).
- **MCP Service** không truy cập DB/Redis trực tiếp — mọi data đi qua API Service.
- **API Service** vẫn là bên duy nhất sở hữu DB, Redis, cocoindex, auth verification.

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
