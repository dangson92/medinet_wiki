DROP TRIGGER IF EXISTS trg_users_updated_at ON users;
DROP TRIGGER IF EXISTS trg_hubs_updated_at ON hubs;
DROP FUNCTION IF EXISTS update_updated_at;

DROP TABLE IF EXISTS document_chunks;
DROP TABLE IF EXISTS documents;
DROP TABLE IF EXISTS revoked_tokens;
DROP TABLE IF EXISTS api_keys;
DROP TABLE IF EXISTS user_hub_roles;
DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS hubs;
