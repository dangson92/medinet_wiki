# Medinet Wiki API — dev tasks
.PHONY: install dev keys keys-verify keys-verify-jwt lint test test-cov test-integration test-migration clean \
        migrate-up migrate-down migrate-check migrate-history cocoindex-setup \
        migrate-all migrate-status hub-init hub-add

UV ?= uv

install:
	$(UV) sync --extra dev

# Chạy API local native (không Docker — xem MEMORY "Chạy backend local nhanh":
# Postgres/Redis trong Docker, uvicorn native). Port 8180 để khớp frontend
# `api.ts` hardcode (Hyper-V excluded range 8038-8137). Postgres + Redis phải
# up trước (`docker compose up -d postgres redis`).
dev:
	$(UV) run uvicorn app.main:app --reload --host 0.0.0.0 --port 8180

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

# === Integration test (Phase 4 v3.1 MIGRATE-01 + MIGRATE-02) ===
# Requires Docker Desktop running (testcontainers pgvector/pgvector:pg16 + redis).
# Auto-spin Postgres + Redis containers — KHÔNG cần TEST_DATABASE_URL env set
# nếu test dùng postgres_container fixture (recommended). Fallback TEST_DATABASE_URL
# nếu chạy ad-hoc test_migration_0006_idempotent.py (Plan 01-03 pattern).

test-integration:
	$(UV) run pytest tests/integration -v -m integration --tb=short

test-migration:
	$(UV) run pytest tests/integration/test_migration_0006_idempotent.py tests/integration/test_migration_upgrade_downgrade.py -v --tb=short

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

# === Per-hub Alembic migration (Phase 1 v3.0 TOPO-02) ===
# Yeu cau prereq: docker compose up -d postgres (Phase 1 Plan 01 — 4 DB da tao)
# + .env DATABASE_URL tro medinet_central + HUB_NAME=central.
# Tu loop 4 hub: central + yte + duoc + hcns.
# Moi hub apply tuan tu qua `alembic -x hub=<name> upgrade head`.
# Sau loop goi scripts/alembic-head-check.sh verify head SHA match 4 DB
# (R-V3-3 drift mitigation).

HUBS_ALL ?= central yte duoc hcns

migrate-all:
	@echo "[migrate-all] Apply Alembic upgrade head tuan tu 4 DB..."
	@for hub in $(HUBS_ALL); do \
		echo "[migrate-all] === hub=$$hub ==="; \
		$(UV) run alembic -x hub=$$hub upgrade head || exit 1; \
	done
	@echo "[migrate-all] DONE. Verify head SHA match qua scripts/alembic-head-check.sh"
	@bash scripts/alembic-head-check.sh

migrate-status:
	@echo "[migrate-status] Show alembic current per hub..."
	@for hub in $(HUBS_ALL); do \
		echo "[migrate-status] --- hub=$$hub ---"; \
		$(UV) run alembic -x hub=$$hub current || echo "  (FAIL)"; \
	done

# === Dynamic hub init (Phase 1 v3.0 Plan 01-05 TOPO-01 part 2) ===
# Tien dieu kien: docker compose up -d postgres (Phase 1 Plan 01 — central + cocoindex DB da ton tai)
# + .env DATABASE_URL tro medinet_central + HUB_NAME=central (de alembic env.py
# base DSN resolve ok).
# Goi: make hub-init HUB=<name>
# Vd: make hub-init HUB=phap_che
# Script chay scripts/hub-init.sh - CREATE DB + ext + HNSW verify + alembic upgrade head.

hub-init:
	@if [ -z "$(HUB)" ]; then echo "Usage: make hub-init HUB=<name>"; exit 2; fi
	@bash scripts/hub-init.sh $(HUB)

# === Dynamic hub registration end-to-end (Plan 02-05 v3.0 FACTOR-04) ===
# Wrap quanh hub-init + auto-gen docker-compose.override.yml service block.
# Goi: make hub-add HUB=<name> [PORT=<port>]
# Sau khi DONE: docker compose up -d python-api-<name>

hub-add:
	@if [ -z "$(HUB)" ]; then echo "Usage: make hub-add HUB=<name> [PORT=<port>]"; exit 2; fi
	@bash scripts/hub-add.sh $(HUB) $(PORT)

# === Cocoindex setup (Phase 4 Plan 04-01) ===
# Chạy MỘT LẦN sau `make migrate-up`. Idempotent — chạy lại OK sau Plan 04-02 (flow.py).
# Tạo internal state tables trong schema `cocoindex` (P7 mitigation).

cocoindex-setup:
	$(UV) run python scripts/cocoindex_setup.py
