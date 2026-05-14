# Makefile root — Medinet Wiki (Hub_All) · M2 Full RAG Rewrite
#
# Sau khi xoá Hub_All/backend/ Go (TEARDOWN-01 pull-in 2026-05-14, sớm hơn
# Phase 8 theo quyết định user), Makefile này chỉ còn proxy sang `api/`.
# Recover Go code: `git checkout m1-go-archived -- Hub_All/backend/`.
#
# QUAN TRỌNG: Makefile yêu cầu TAB indent (KHÔNG dùng spaces).

.DEFAULT_GOAL := help

.PHONY: help up down logs api-dev api-test api-lint api-keys api-install

# ═══════════════════════════════════════════════════════════════════════════
# Help
# ═══════════════════════════════════════════════════════════════════════════

help: ## Hiển thị danh sách target khả dụng
	@echo "═══ Medinet Wiki — Makefile root (M2) ═══"
	@echo ""
	@echo "Docker compose (3-service: postgres + redis + python-api):"
	@echo "  up                      - docker compose up -d (postgres + redis + python-api)"
	@echo "  down                    - docker compose down"
	@echo "  logs                    - docker compose logs -f python-api"
	@echo ""
	@echo "Python api/ (proxy sang api/Makefile):"
	@echo "  api-install             - cd api && make install (uv sync)"
	@echo "  api-keys                - cd api && make keys (sinh RSA keypair JWT)"
	@echo "  api-dev                 - cd api && make dev (uvicorn reload :8080)"
	@echo "  api-test                - cd api && make test (pytest + testcontainers)"
	@echo "  api-lint                - cd api && make lint (ruff + mypy strict)"

# ═══════════════════════════════════════════════════════════════════════════
# Docker compose
# ═══════════════════════════════════════════════════════════════════════════

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f python-api

# ═══════════════════════════════════════════════════════════════════════════
# Python api/ proxy
# ═══════════════════════════════════════════════════════════════════════════

api-install:
	$(MAKE) -C api install

api-keys:
	$(MAKE) -C api keys

api-dev:
	$(MAKE) -C api dev

api-test:
	$(MAKE) -C api test

api-lint:
	$(MAKE) -C api lint
