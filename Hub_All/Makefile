# Makefile root — Medinet Wiki (Hub_All) · M2 Full RAG Rewrite
#
# Sau khi xoá Hub_All/backend/ Go (TEARDOWN-01 pull-in 2026-05-14, sớm hơn
# Phase 8 theo quyết định user), Makefile này chỉ còn proxy sang `api/`.
# Recover Go code: `git checkout m1-go-archived -- Hub_All/backend/`.
#
# QUAN TRỌNG: Makefile yêu cầu TAB indent (KHÔNG dùng spaces).

.DEFAULT_GOAL := help

.PHONY: help up down logs api-dev api-test api-lint api-keys api-install \
        eval-install eval-seed eval-clean eval-smoke eval-all eval-report \
        eval-readme eval-restore hub-init hub-add

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
	@echo ""
	@echo "Phase 1 v3.0 Dynamic hub-init (TOPO-01 part 2):"
	@echo "  hub-init HUB=<name>     - them hub moi (CREATE DB + ext vector + HNSW verify + alembic upgrade head)"
	@echo ""
	@echo "Phase 2 v3.0 FACTOR-04 Dynamic hub registration (Plan 02-05):"
	@echo "  hub-add HUB=<name> [PORT=<port>] - them hub moi end-to-end (DB + ext vector + alembic + compose service block)"
	@echo ""
	@echo "Phase 9 Eval Framework (EVAL-02 + EVAL-04):"
	@echo "  eval-install            - cd eval && pip install -e '.[dev]'"
	@echo "  eval-seed               - psql -f eval/scripts/seed_hub.sql (idempotent)"
	@echo "  eval-clean              - python -m eval.scripts.cleanup (reset state)"
	@echo "  eval-smoke              - python -m eval.run_eval --mock-embed --skip-cleanup (< 60s)"
	@echo "  eval-all                - cleanup + run_eval real LLM (yeu cau OPENAI_API_KEY)"
	@echo "  eval-report             - python -m eval.report eval/results.json eval/EVAL.md"
	@echo "  eval-readme             - In quick start workflow snippet"
	@echo "  eval-restore            - git checkout 0af44f0 -- eval/dataset/ (restore M1)"

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

# ═══════════════════════════════════════════════════════════════════════════
# Phase 1 v3.0 — Dynamic hub initialization (TOPO-01 part 2)
# ═══════════════════════════════════════════════════════════════════════════
# Them hub moi ma KHONG can docker compose down. Usage:
#   make hub-init HUB=phap_che   # tao DB medinet_hub_phap_che + ext vector + alembic upgrade head
# Sau khi script DONE, can update app/config.py Literal hub_name de Settings accept hub moi.

hub-init:
	@if [ -z "$(HUB)" ]; then echo "Usage: make hub-init HUB=<name>"; exit 2; fi
	$(MAKE) -C api hub-init HUB=$(HUB)

# ═══════════════════════════════════════════════════════════════════════════
# Plan 02-05 FACTOR-04 — Dynamic hub registration end-to-end
# ═══════════════════════════════════════════════════════════════════════════
# Tien dieu kien giong hub-init: postgres dang chay + .env DATABASE_URL central.
# Khac biet: hub-add wrap quanh hub-init + auto-gen docker-compose.override.yml
# service block + volume declaration. Operator chay 1 lenh la tao xong hub moi.
#
# Usage:
#   make hub-add HUB=phap_che              # auto-detect port (8184 tro len)
#   make hub-add HUB=marketing PORT=8200   # explicit port
#
# Sau khi DONE:
#   docker compose up -d python-api-phap_che
#   curl http://localhost:<port>/api/health

hub-add:
	@if [ -z "$(HUB)" ]; then echo "Usage: make hub-add HUB=<name> [PORT=<port>]"; exit 2; fi
	$(MAKE) -C api hub-add HUB=$(HUB) PORT=$(PORT)

# ═══════════════════════════════════════════════════════════════════════════
# Phase 9 Eval Framework (EVAL-02 + EVAL-04)
# ═══════════════════════════════════════════════════════════════════════════
# Workflow chi tiet xem Hub_All/eval/README.md (Plan 09-04).
#
# Tien dieu kien gate verdict:
#   - Docker stack chay: make up (postgres + redis + python-api port 8180)
#   - eval_hub seed 1 lan: make eval-seed
#   - OPENAI_API_KEY thuc (real LLM gate ~$0.20/run): export OPENAI_API_KEY=sk-...
#
# Smoke regression KHONG can OPENAI_API_KEY (mock embedding).

eval-install:
	cd eval && pip install -e ".[dev]"

eval-seed:
	psql -h $${DB_HOST:-localhost} -U $${DB_USER:-medinet} -d $${DB_NAME:-medinet_central} \
		-f eval/scripts/seed_hub.sql

eval-clean:
	cd eval && python -m eval.scripts.cleanup

eval-smoke:
	cd eval && python -m eval.run_eval --mock-embed --skip-cleanup

eval-all:
	cd eval && python -m eval.scripts.cleanup
	cd eval && python -m eval.run_eval

eval-report:
	cd eval && python -m eval.report results.json EVAL.md

eval-readme:
	@echo "Eval README: Hub_All/eval/README.md"
	@echo ""
	@echo "Quick start:"
	@echo "  make eval-install   # cai deps Python eval"
	@echo "  make eval-seed      # seed eval_hub (1 lan duy nhat)"
	@echo "  make eval-smoke     # smoke regression < 60s (mock embedding)"
	@echo "  make eval-all       # full gate verdict (yeu cau OPENAI_API_KEY)"
	@echo ""
	@echo "Tien dieu kien gate:"
	@echo "  - Docker stack chay: make up"
	@echo "  - OPENAI_API_KEY thuc (~\$$0.20/run cho 10 file x 25 chunk x 1536 dim)"
	@echo "  - FAIL < 60% top-3 = trigger E5 STOP M2b (PROJECT.md EXIT)"

eval-restore:
	git checkout 0af44f0 -- eval/dataset/
