# syntax=docker/dockerfile:1.7
# Dockerfile MCP Service — Phase 8.3.
# Multi-stage uv (mẫu theo api/Dockerfile). KHÁC api: không DB chung nên KHÔNG
# alembic/migrations; CMD dùng FACTORY build_asgi_app nên cần cờ --factory.

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
RUN groupadd --system --gid 1000 mcpuser \
 && useradd --system --uid 1000 --gid mcpuser --create-home mcpuser \
 && apt-get update \
 && apt-get install -y --no-install-recommends curl \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=builder --chown=mcpuser:mcpuser /app/.venv /app/.venv
COPY --chown=mcpuser:mcpuser mcp_app ./mcp_app
# Thư mục SQLite OAuth state — tạo + chown TRƯỚC khi hạ quyền (mcpuser không tạo
# được thư mục con dưới /app do root sở hữu). Mount named volume tại đây ở compose.
RUN mkdir -p /app/.oauth && chown mcpuser:mcpuser /app/.oauth
USER mcpuser
EXPOSE 8190
# HEALTHCHECK probe route /.well-known/oauth-authorization-server — route TẤT ĐỊNH:
# Settings có default issuer (Plan 01) nên Settings() không raise khi thiếu env;
# SDK mcp mount well-known route ngay khi auth_server_provider non-None → trả 200
# từ lúc app start, kể cả trước khi operator set domain thật.
# start-period=20s cho app + lifespan init_schema() (Plan 02) kịp khởi động.
HEALTHCHECK --interval=10s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:8190/.well-known/oauth-authorization-server || exit 1
# build_asgi_app là FACTORY (FastMCP mới mỗi lần gọi — Plan 02) → BẮT BUỘC cờ --factory.
CMD ["uvicorn", "mcp_app.server:build_asgi_app", "--factory", "--host", "0.0.0.0", "--port", "8190"]
