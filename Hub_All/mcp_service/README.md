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

---

## Phase 8.3 — OAuth 2.0 + Deploy public HTTPS

Phase 8.3 thêm lớp **OAuth 2.0** cho MCP Service và đưa service ra **public qua
HTTPS**, để Claude web "Add custom connector" kết nối được — dialog connector chỉ
chấp nhận URL public HTTPS + OAuth 2.0, KHÔNG gửi được header `X-API-Key`.

### Kiến trúc đích

```
Claude web  ──(OAuth 2.0)──►  MCP Service (public HTTPS)  ──(JWT RS256 nội bộ)──►  API Service
```

MCP Service nay đóng cả vai **Authorization Server** (phát token, metadata
discovery, Dynamic Client Registration) lẫn **Resource Server** (verify token mỗi
tool call). Khi user OAuth login thành công, MCP Service login vào API Service như
chính user đó → nhận JWT RS256 → bind vào token OAuth → mỗi tool call forward JWT
xuống API Service. Hub isolation + RBAC enforce API-side theo từng user.

### Hai cách xác thực (song song)

| Cách | Dùng cho | Header |
|------|----------|--------|
| OAuth 2.0 | Claude web "Add custom connector" | `Authorization: Bearer <oauth_token>` |
| X-API-Key | Claude Code / Claude Desktop (client local) | `X-API-Key: <key>` |

Cả hai dùng được đồng thời — client local hiện có từ Phase 8.2 KHÔNG vỡ.

### Cách chạy có OAuth

```bash
# Toàn stack (khuyến nghị — kèm API Service + Caddy reverse proxy):
cd Hub_All
docker compose up -d

# HOẶC chạy native (chỉ MCP Service — build_asgi_app là FACTORY → cần --factory):
cd Hub_All/mcp_service
uv run uvicorn mcp_app.server:build_asgi_app --factory --host 0.0.0.0 --port 8190
```

### Biến môi trường OAuth mới

| Biến | Mặc định | Mô tả |
|------|----------|-------|
| `MCP_OAUTH_ISSUER_URL` | `http://localhost:8190` | URL public HTTPS để Claude web kết nối connector. **Prod PHẢI là `https://` domain thật** (Pitfall 6 — issuer localhost làm hỏng discovery + redirect). |
| `MCP_OAUTH_STATE_DB_PATH` | `.oauth/state.db` | File SQLite lưu OAuth state (clients/codes/tokens/pending). Docker override `/app/.oauth/state.db` trên named volume. |
| `MCP_OAUTH_ACCESS_TOKEN_TTL` | `3600` | Lifetime OAuth access token (giây). |
| `MCP_OAUTH_REFRESH_TOKEN_TTL` | `2592000` | Lifetime OAuth refresh token (giây — 30 ngày). |

### Reverse proxy + deploy public HTTPS

Mặc định dùng **Caddy** auto-TLS (Let's Encrypt) — service `caddy` trong
`docker-compose.yml`, cấu hình `Hub_All/Caddyfile`. Caddy tự xin + gia hạn cert,
cần port 80 + 443 mở ra Internet. Domain truyền qua biến `WIKI_PUBLIC_DOMAIN`.

> 2026-05-23: MCP service gộp về `wiki.medinet.vn/mcp` (path-prefix mode qua
> `MCP_PATH_PREFIX=mcp`). Bỏ subdomain riêng `mcp.medinet.vn` — Caddy serve
> `/mcp/*` + `/.well-known/oauth-*` cùng domain với wiki. Xem
> `.planning/quick/2026-05-23-mcp-subdomain-consolidate/PLAN.md`.

**Fallback Cloudflare Tunnel** — nếu không mở được port 80/443: thay service
`caddy` bằng `cloudflared` (tunnel zero-port, tự cấp HTTPS). Đổi reverse proxy chỉ
cần đổi `MCP_OAUTH_ISSUER_URL` + service compose — **KHÔNG sửa code `mcp_app`**.

> Quy trình kết nối thật từ Claude web (UAT thủ công SC4): xem
> `.planning/phases/08.3-mcp-oauth-deploy-public-https/08.3-HUMAN-UAT.md`.
