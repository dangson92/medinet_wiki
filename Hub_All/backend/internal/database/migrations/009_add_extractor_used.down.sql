-- 009_add_extractor_used.down.sql — đối xứng up.sql (CFG-06 M1 Phase 4).
DROP INDEX IF EXISTS idx_documents_extractor_used;
ALTER TABLE documents DROP COLUMN IF EXISTS extractor_used;
