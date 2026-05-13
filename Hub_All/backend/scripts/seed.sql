-- ================================================================
-- Seed Data: Default admin + 3 hubs
-- Password: Admin@123 (Argon2id hash)
-- IMPORTANT: Change password on first login!
-- ================================================================

-- Default admin user
-- Password "Admin@123" hashed with Argon2id (memory=64MB, iterations=3, parallelism=4)
INSERT INTO users (email, name, password_hash, status)
VALUES (
    'admin@medinet.vn',
    'System Admin',
    '$argon2id$v=19$m=65536,t=3,p=4$gpKFndFoG6bcXrx7R60sag$uhxmJMX03O6QlL0WZS+WdRhCOnGEoIpzUrL2vBzRN+c',
    'active'
)
ON CONFLICT (email) DO NOTHING;

-- 3 Default hubs
INSERT INTO hubs (name, code, subdomain, chroma_collection, description) VALUES
    ('Tâm Đạo Y Quán', 'tamdao', 'tamdao.medinet.vn', 'medinet_tamdao', 'Hub y học cổ truyền Tâm Đạo Y Quán'),
    ('Đỗ Minh Đường', 'dmd', 'dmd.medinet.vn', 'medinet_dmd', 'Hub nhà thuốc Đỗ Minh Đường'),
    ('HCNS', 'hcns', 'hcns.medinet.vn', 'medinet_hcns', 'Hub Hành Chính Nhân Sự')
ON CONFLICT (code) DO NOTHING;

-- Assign admin to all hubs
INSERT INTO user_hub_roles (user_id, hub_id, role)
SELECT u.id, h.id, 'admin'
FROM users u, hubs h
WHERE u.email = 'admin@medinet.vn'
ON CONFLICT (user_id, hub_id) DO NOTHING;
