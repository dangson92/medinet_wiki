-- Phase 9 EVAL-01: Seed hub eval idempotent.
-- Chạy: psql -h $DB_HOST -U $DB_USER -d $DB_NAME -f Hub_All/eval/scripts/seed_hub.sql
--
-- Hub eval isolation: tách hẳn hub dev/prod (RESEARCH Open Q3 — D-09-01).
-- Subdomain "eval.medinet.vn" KHÔNG cần DNS thật (eval framework gọi qua BACKEND_URL trực tiếp).

INSERT INTO hubs (id, code, name, subdomain, is_active, created_at)
VALUES (
    gen_random_uuid(),
    'eval',
    'Eval Hub (Phase 9 quality gate)',
    'eval.medinet.vn',
    TRUE,
    NOW()
)
ON CONFLICT (code) DO NOTHING;

-- Verify
SELECT id, code, subdomain, is_active FROM hubs WHERE code = 'eval';
