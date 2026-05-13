-- =============================================================================
-- eval/scripts/seed_hub.sql
-- Seed hub `eval` cho dataset M1 RAG Quality (Phase 1).
-- =============================================================================
-- Mục đích:
--   Tạo sandbox hub `eval` riêng biệt để chạy baseline retrieval với extractor
--   Go native (Phase 1) và sau này so sánh với Docling (Phase 5). Sandbox tuyệt
--   đối — tách hoàn toàn khỏi data hub dev/prod (`tamdao`, `dmd`, `hcns`).
--
-- Cách chạy:
--   psql -h localhost -U medinet -d medinet_central -f eval/scripts/seed_hub.sql
--
-- Idempotent:
--   ON CONFLICT (code) DO NOTHING — chạy lại nhiều lần an toàn, không tạo
--   duplicate hub. Lệnh SELECT cuối cùng dùng để verify hub đã tồn tại.
--
-- Schema reference:
--   backend/internal/database/migrations/001_bootstrap.up.sql:7-23
--   - `subdomain` UNIQUE NOT NULL → bắt buộc cung cấp.
--   - `chroma_collection` NOT NULL → đặt cố định 'medinet_eval'.
--   - Cột `status` (KHÔNG phải `is_active`) — CHECK ('active','inactive').
--   - `id` để Postgres tự sinh qua `gen_random_uuid()` (KHÔNG hard-code).
-- =============================================================================

INSERT INTO hubs (name, code, subdomain, chroma_collection, description, status)
VALUES (
    'Eval Sandbox (M1 RAG Quality)',
    'eval',
    'eval.medinet.vn',
    'medinet_eval',
    'Sandbox cho eval dataset M1 — đo baseline retrieval với extractor Go native',
    'active'
)
ON CONFLICT (code) DO NOTHING;

-- Verify: in ra hub eval vừa tạo (hoặc đã tồn tại từ lần chạy trước).
SELECT id, code, name, subdomain, chroma_collection, status, created_at
FROM hubs
WHERE code = 'eval';
