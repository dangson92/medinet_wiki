"""Conftest cho unit tests — re-export integration fixtures.

Plan 04-05 task 04 test_watchdog.py technically là integration (cần Postgres
testcontainer) nhưng đặt unit/ vì test query logic isolated KHÔNG cần FastAPI
app/lifespan/auth router.

pytest fixtures KHÔNG inherit qua sibling directories — `tests/integration/conftest.py`
fixtures (`postgres_container`, `alembic_cfg`) chỉ visible cho file trong
`tests/integration/`. Re-import vào `tests/unit/conftest.py` để test_watchdog.py
xài được.

KHÔNG đụng `tests/conftest.py` autouse `_env` (Phase 1) — fixture `_env` set
DATABASE_URL placeholder trước, nhưng `alembic_cfg` (function-scope) sẽ
override env vars thật từ postgres_container TRƯỚC khi test code chạy.
"""
from __future__ import annotations

# Re-export integration fixtures (postgres_container, alembic_cfg, redis_container, ...).
# pytest tự discover fixture qua module-level reference.
from tests.integration.conftest import (  # noqa: F401
    alembic_cfg,
    postgres_container,
    redis_container,
)
