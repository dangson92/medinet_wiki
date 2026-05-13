# Medinet Wiki API — dev tasks
.PHONY: install keys keys-verify lint test test-cov clean

UV ?= uv

install:
	$(UV) sync --extra dev

keys:
	bash scripts/generate_keys.sh

keys-verify:
	bash scripts/verify_keys.sh

lint:
	$(UV) run ruff check app tests
	$(UV) run mypy app

test:
	$(UV) run pytest -v

test-cov:
	$(UV) run pytest --cov=app --cov-report=term-missing

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache .venv
