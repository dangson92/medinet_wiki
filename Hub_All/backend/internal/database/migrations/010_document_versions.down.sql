-- Rollback migration 010_document_versions.
DROP TRIGGER IF EXISTS trg_document_versions_prune ON document_versions;
DROP FUNCTION IF EXISTS prune_document_versions();
DROP TABLE IF EXISTS document_version_chunks;
DROP TABLE IF EXISTS document_versions;
