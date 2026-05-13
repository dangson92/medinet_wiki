#!/usr/bin/env bash
# Smoke test Alembic config — Plan 03 verify env.py + alembic.ini hoạt động.
# Yêu cầu prereq: docker compose up -d postgres (Phase 1 Plan 02) + .env file đủ DSN.

set -euo pipefail

cd "$(dirname "$0")/.."

echo "[alembic-smoke] (1/3) Verify alembic CLI accessible..."
uv run alembic --help > /dev/null

echo "[alembic-smoke] (2/3) Verify env.py load (no migration apply)..."
uv run alembic current 2>&1 | tee /tmp/alembic_current.log

# Alembic current trên DB rỗng có thể trả về 1 trong các pattern:
# - "(empty)" — chưa có alembic_version table
# - "INFO  [alembic.runtime.migration] Context impl PostgresqlImpl." rồi blank
# Đều OK miễn KHÔNG exception traceback.
if grep -qE '(Traceback|Error|FATAL)' /tmp/alembic_current.log; then
    echo "FAIL: alembic current có exception/error."
    exit 1
fi

echo "[alembic-smoke] (3/3) Verify target_metadata pick up 10 tables..."
uv run python -c "
from app.db.base import Base
from app.models import *
tables = sorted(Base.metadata.tables.keys())
assert len(tables) == 10, f'Expected 10 tables, got {len(tables)}: {tables}'
print(f'OK — {len(tables)} tables registered: {tables}')
"

echo "[alembic-smoke] DONE — Alembic config sẵn sàng cho Plan 04 (sinh migration)."
