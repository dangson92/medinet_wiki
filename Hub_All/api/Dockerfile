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
