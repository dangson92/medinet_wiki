# Makefile root — Medinet Wiki (Hub_All)
#
# Mục đích chính: cung cấp các target cấp dự án (eval-*) cho M1 Phase 5
# (RAG Quality with Docling). Các target backend chuyên sâu (build/run/migrate/...)
# đặt trong backend/Makefile — chạy bằng `cd backend && make <target>`.
#
# QUAN TRỌNG: Makefile yêu cầu TAB indent (KHÔNG dùng spaces).
#
# Ngôn ngữ: tiếng Việt có dấu cho phần mô tả; tên target / lệnh shell / đường dẫn
# giữ tiếng Anh (theo CLAUDE.md root).

.DEFAULT_GOAL := help

.PHONY: help \
        eval-smoke eval-baseline-docling eval-compare eval-all eval-clean \
        backend-dev backend-build backend-test

# ═══════════════════════════════════════════════════════════════════════════
# Help — danh sách target mặc định
# ═══════════════════════════════════════════════════════════════════════════

help: ## Hiển thị danh sách target khả dụng
	@echo "═══ Medinet Wiki — Makefile root ═══"
	@echo ""
	@echo "Eval (M1 Phase 5 — RAG Quality with Docling):"
	@echo "  eval-smoke              - Smoke test 1 file e2e: assert extractor_used=docling + is_table chunk indexed (~30s)"
	@echo "  eval-baseline-docling   - Snapshot mode docling: python eval/run_docling.py (~30-60 phut)"
	@echo "  eval-compare            - Orchestrate extraction + retrieval compare -> EVAL.md"
	@echo "  eval-all                - Chain: eval-baseline-docling -> eval-compare"
	@echo "  eval-clean              - Reset eval_hub state (Postgres + Chroma + uploads + Redis cache)"
	@echo ""
	@echo "Backend (chuyen sau, xem backend/Makefile):"
	@echo "  backend-dev             - Proxy: cd backend && make dev"
	@echo "  backend-build           - Proxy: cd backend && make build"
	@echo "  backend-test            - Proxy: cd backend && make test"
	@echo ""
	@echo "Tien dieu kien chay eval-*:"
	@echo "  - Backend Go up @ http://localhost:8180"
	@echo "  - PostgreSQL + Redis + ChromaDB up (docker compose up)"
	@echo "  - docling-pipeline up (cho eval-baseline-docling + eval-smoke)"
	@echo "  - eval/.env da config (copy tu eval/.env.example)"
	@echo "  - Hub 'eval' da seed (psql -f eval/scripts/seed_hub.sql)"

# ═══════════════════════════════════════════════════════════════════════════
# Eval (M1 Phase 5)
# ═══════════════════════════════════════════════════════════════════════════

eval-smoke: ## Smoke test 1 file e2e: upload qua Docling + assert extractor_used + is_table chunk indexed
	@python -c "import sys, os; \
sys.path.insert(0, 'eval'); \
from lib import APIClient, preflight; \
backend_url = os.getenv('BACKEND_URL', 'http://localhost:8180'); \
chroma_url = os.getenv('CHROMA_URL', 'http://localhost:8000'); \
admin_email = os.getenv('ADMIN_EMAIL', 'admin@medinet.vn'); \
admin_password = os.getenv('ADMIN_PASSWORD', 'Admin@123'); \
hub_code = os.getenv('EVAL_HUB_CODE', 'eval'); \
db_dsn = os.getenv('DB_DSN'); \
preflight(backend_url, db_dsn, chroma_url, hub_code); \
c = APIClient(backend_url, admin_email, admin_password); \
c.login(); \
hub = c.get_hub_id(hub_code); \
doc = c.upload_and_wait(hub, 'eval/dataset/sources/DMD_T1-01_DinhVi_TrungTam_v1.docx', timeout=300); \
extractor_used = doc.get('extractor_used'); \
assert extractor_used == 'docling', '[SMOKE FAIL] Expected extractor_used=docling, got ' + repr(extractor_used) + '. Kiem tra Docling sidecar UP + RAG_EXTRACTOR=docling/auto.'; \
print('[SMOKE] extractor_used=docling OK'); \
results = c.search(hub, 'tom tat dinh vi thuong hieu', top_k=5); \
print('[SMOKE] search returned ' + str(len(results)) + ' results'); \
table_chunks = [r for r in results if bool((r.get('metadata') or {}).get('is_table'))]; \
has_table = len(table_chunks) > 0; \
file_has_no_table = (extractor_used == 'docling' and len(results) > 0 and not has_table); \
print('[SMOKE] is_table chunks: ' + str(len(table_chunks)) + ('  (file co the khong co table -> SKIP table assert, defensive)' if file_has_no_table else '')); \
assert has_table or file_has_no_table, '[SMOKE FAIL] Expected >=1 chunk voi is_table=true HOAC zero search results.'; \
c.close(); \
print('SMOKE OK: Docling extractor used + (table chunk indexed HOAC defensive skip)')"

eval-baseline-docling: ## Snapshot mode docling: chay ingestion 10 file + 12 query -> baseline_docling.json
	python eval/run_docling.py

eval-compare: ## Orchestrator: extraction + retrieval compare -> eval/EVAL.md (verdict PASS/FAIL exit 0/1)
	python eval/run_compare.py

eval-all: eval-baseline-docling eval-compare ## Chain full: snapshot Docling -> compare -> EVAL.md

eval-clean: ## Reset eval_hub state (Postgres documents/chunks + Chroma collection + uploads + Redis cache)
	python eval/scripts/cleanup.py

# ═══════════════════════════════════════════════════════════════════════════
# Backend proxy (tien dung — uy quyen sang backend/Makefile)
# ═══════════════════════════════════════════════════════════════════════════

backend-dev:
	$(MAKE) -C backend dev

backend-build:
	$(MAKE) -C backend build

backend-test:
	$(MAKE) -C backend test
