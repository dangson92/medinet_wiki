# Medinet Wiki API — dev tasks
.PHONY: install keys keys-verify keys-verify-jwt lint test test-cov clean migrate-up migrate-down migrate-check migrate-history cocoindex-setup

UV ?= uv

install:
	$(UV) sync --extra dev

keys:
	bash scripts/generate_keys.sh

keys-verify:
	bash scripts/verify_keys.sh

keys-verify-jwt:
	bash scripts/verify_jwt_format.sh

lint:
	$(UV) run ruff check app tests
	$(UV) run mypy app

test:
	$(UV) run pytest -v

test-cov:
	$(UV) run pytest --cov=app --cov-report=term-missing

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache .venv

# === Alembic migration targets (Phase 2 Plan 05) ===
# Tien dieu kien: docker compose up -d postgres (Phase 1 Plan 02) + .env file day DSN.

migrate-up:
	uv run alembic upgrade head

migrate-down:
	uv run alembic downgrade base

migrate-check:
	uv run alembic check

migrate-history:
	uv run alembic history --verbose

# === Cocoindex setup (Phase 4 Plan 04-01) ===
# Chạy MỘT LẦN sau `make migrate-up`. Idempotent — chạy lại OK sau Plan 04-02 (flow.py).
# Tạo internal state tables trong schema `cocoindex` (P7 mitigation).

cocoindex-setup:
	$(UV) run python scripts/cocoindex_setup.py
