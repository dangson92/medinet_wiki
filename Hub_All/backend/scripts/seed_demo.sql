-- =============================================================================
-- MEDINET CENTRAL — Demo Seed Data
-- =============================================================================
-- Database : medinet_central (PostgreSQL)
-- Purpose  : Populate demo data matching frontend mockData.ts
-- Usage    : psql -U medinet_admin -d medinet_central -f seed_demo.sql
-- Idempotent: Yes — safe to re-run (uses ON CONFLICT / DELETE+re-insert)
-- =============================================================================

SET client_encoding = 'UTF8';

BEGIN;

-- ---------------------------------------------------------------------------
-- 0. Password hash constant (Argon2id for "Admin@123")
-- ---------------------------------------------------------------------------
DO $$ BEGIN
  RAISE NOTICE 'Starting seed_demo — inserting demo data...';
END $$;

-- ---------------------------------------------------------------------------
-- 1. HUBS (6 total — 3 existing, 3 new)
-- ---------------------------------------------------------------------------
INSERT INTO hubs (id, name, code, subdomain, description, chroma_collection, status, db_host, db_port, db_name, db_user, db_password_enc, created_at, updated_at)
VALUES
  -- Existing hubs (upsert to ensure consistency)
  (gen_random_uuid(), 'Tâm Đạo Y Quán', 'tamdao', 'tamdao.medinet.vn',
   'Hub y học cổ truyền Tâm Đạo Y Quán', 'col_tamdao', 'active',
   'localhost', 5432, 'medinet_tamdao', 'medinet_app', '', '2024-10-01'::timestamptz, NOW()),

  (gen_random_uuid(), 'Đỗ Minh Đường', 'dmd', 'dmd.medinet.vn',
   'Hub y học cổ truyền Đỗ Minh Đường', 'col_dmd', 'active',
   'localhost', 5432, 'medinet_dmd', 'medinet_app', '', '2024-11-15'::timestamptz, NOW()),

  (gen_random_uuid(), 'HCNS', 'hcns', 'hcns.medinet.vn',
   'Hub Hành chính Nhân sự', 'col_hcns', 'active',
   'localhost', 5432, 'medinet_hcns', 'medinet_app', '', '2024-12-20'::timestamptz, NOW()),

  -- New hubs
  (gen_random_uuid(), 'Test Hub', 'test', 'test.medinet.vn',
   'Hub dùng để test', 'col_test', 'inactive',
   'localhost', 5432, 'medinet_test', 'medinet_app', '', '2025-01-10'::timestamptz, NOW()),

  (gen_random_uuid(), 'Phòng khám Đa khoa Quốc tế', 'pkdkqt', 'pkdkqt.medinet.vn',
   'Phòng khám Đa khoa Quốc tế', 'col_pkdkqt', 'active',
   'localhost', 5432, 'medinet_pkdkqt', 'medinet_app', '', '2024-05-12'::timestamptz, NOW()),

  (gen_random_uuid(), 'Bệnh viện Y học Cổ truyền', 'bvyhct', 'bvyhct.medinet.vn',
   'Bệnh viện Y học Cổ truyền', 'col_bvyhct', 'active',
   'localhost', 5432, 'medinet_bvyhct', 'medinet_app', '', '2023-08-20'::timestamptz, NOW())

ON CONFLICT (code) DO UPDATE SET
  name          = EXCLUDED.name,
  subdomain     = EXCLUDED.subdomain,
  description   = EXCLUDED.description,
  status        = EXCLUDED.status,
  updated_at    = NOW();

-- ---------------------------------------------------------------------------
-- 2. USERS (35 demo users + admin@medinet.vn already exists)
-- ---------------------------------------------------------------------------
-- Common password hash for all demo users: "Admin@123"
-- $argon2id$v=19$m=65536,t=3,p=4$gpKFndFoG6bcXrx7R60sag$uhxmJMX03O6QlL0WZS+WdRhCOnGEoIpzUrL2vBzRN+c

INSERT INTO users (id, email, name, phone, department, password_hash, avatar_url, status, failed_login_count, locked_until, created_at, updated_at)
VALUES
  (gen_random_uuid(), 'nva@medinet.vn',  'Nguyễn Văn A',   NULL, NULL, '$argon2id$v=19$m=65536,t=3,p=4$gpKFndFoG6bcXrx7R60sag$uhxmJMX03O6QlL0WZS+WdRhCOnGEoIpzUrL2vBzRN+c', NULL, 'active',   0, NULL, '2025-01-01'::timestamptz, NOW()),
  (gen_random_uuid(), 'ttb@medinet.vn',  'Trần Thị B',     NULL, NULL, '$argon2id$v=19$m=65536,t=3,p=4$gpKFndFoG6bcXrx7R60sag$uhxmJMX03O6QlL0WZS+WdRhCOnGEoIpzUrL2vBzRN+c', NULL, 'active',   0, NULL, '2025-02-15'::timestamptz, NOW()),
  (gen_random_uuid(), 'lmc@medinet.vn',  'Lê Minh C',      NULL, NULL, '$argon2id$v=19$m=65536,t=3,p=4$gpKFndFoG6bcXrx7R60sag$uhxmJMX03O6QlL0WZS+WdRhCOnGEoIpzUrL2vBzRN+c', NULL, 'disabled',  0, NULL, '2025-03-10'::timestamptz, NOW()),
  (gen_random_uuid(), 'pvd@medinet.vn',  'Phạm Văn D',     NULL, NULL, '$argon2id$v=19$m=65536,t=3,p=4$gpKFndFoG6bcXrx7R60sag$uhxmJMX03O6QlL0WZS+WdRhCOnGEoIpzUrL2vBzRN+c', NULL, 'active',   0, NULL, '2025-01-20'::timestamptz, NOW()),
  (gen_random_uuid(), 'hte@medinet.vn',  'Hoàng Thị E',    NULL, NULL, '$argon2id$v=19$m=65536,t=3,p=4$gpKFndFoG6bcXrx7R60sag$uhxmJMX03O6QlL0WZS+WdRhCOnGEoIpzUrL2vBzRN+c', NULL, 'active',   0, NULL, '2025-03-05'::timestamptz, NOW()),
  (gen_random_uuid(), 'vdf@medinet.vn',  'Vũ Đức F',       NULL, NULL, '$argon2id$v=19$m=65536,t=3,p=4$gpKFndFoG6bcXrx7R60sag$uhxmJMX03O6QlL0WZS+WdRhCOnGEoIpzUrL2vBzRN+c', NULL, 'active',   0, NULL, '2025-01-12'::timestamptz, NOW()),
  (gen_random_uuid(), 'dtg@medinet.vn',  'Đặng Thị G',     NULL, NULL, '$argon2id$v=19$m=65536,t=3,p=4$gpKFndFoG6bcXrx7R60sag$uhxmJMX03O6QlL0WZS+WdRhCOnGEoIpzUrL2vBzRN+c', NULL, 'active',   0, NULL, '2025-01-05'::timestamptz, NOW()),
  (gen_random_uuid(), 'bvh@medinet.vn',  'Bùi Văn H',      NULL, NULL, '$argon2id$v=19$m=65536,t=3,p=4$gpKFndFoG6bcXrx7R60sag$uhxmJMX03O6QlL0WZS+WdRhCOnGEoIpzUrL2vBzRN+c', NULL, 'active',   0, NULL, '2025-02-20'::timestamptz, NOW()),
  (gen_random_uuid(), 'nti@medinet.vn',  'Ngô Thị I',      NULL, NULL, '$argon2id$v=19$m=65536,t=3,p=4$gpKFndFoG6bcXrx7R60sag$uhxmJMX03O6QlL0WZS+WdRhCOnGEoIpzUrL2vBzRN+c', NULL, 'active',   0, NULL, '2025-03-01'::timestamptz, NOW()),
  (gen_random_uuid(), 'dvk@medinet.vn',  'Đỗ Văn K',       NULL, NULL, '$argon2id$v=19$m=65536,t=3,p=4$gpKFndFoG6bcXrx7R60sag$uhxmJMX03O6QlL0WZS+WdRhCOnGEoIpzUrL2vBzRN+c', NULL, 'disabled',  0, NULL, '2025-02-18'::timestamptz, NOW()),
  (gen_random_uuid(), 'ptl@medinet.vn',  'Phan Thị L',     NULL, NULL, '$argon2id$v=19$m=65536,t=3,p=4$gpKFndFoG6bcXrx7R60sag$uhxmJMX03O6QlL0WZS+WdRhCOnGEoIpzUrL2vBzRN+c', NULL, 'active',   0, NULL, '2025-01-22'::timestamptz, NOW()),
  (gen_random_uuid(), 'lvm@medinet.vn',  'Lý Văn M',       NULL, NULL, '$argon2id$v=19$m=65536,t=3,p=4$gpKFndFoG6bcXrx7R60sag$uhxmJMX03O6QlL0WZS+WdRhCOnGEoIpzUrL2vBzRN+c', NULL, 'active',   0, NULL, '2025-01-08'::timestamptz, NOW()),
  (gen_random_uuid(), 'htn@medinet.vn',  'Hồ Thị N',       NULL, NULL, '$argon2id$v=19$m=65536,t=3,p=4$gpKFndFoG6bcXrx7R60sag$uhxmJMX03O6QlL0WZS+WdRhCOnGEoIpzUrL2vBzRN+c', NULL, 'active',   0, NULL, '2025-02-14'::timestamptz, NOW()),
  (gen_random_uuid(), 'mvo@medinet.vn',  'Mai Văn O',       NULL, NULL, '$argon2id$v=19$m=65536,t=3,p=4$gpKFndFoG6bcXrx7R60sag$uhxmJMX03O6QlL0WZS+WdRhCOnGEoIpzUrL2vBzRN+c', NULL, 'active',   0, NULL, '2025-02-25'::timestamptz, NOW()),
  (gen_random_uuid(), 'ttp@medinet.vn',  'Tạ Thị P',       NULL, NULL, '$argon2id$v=19$m=65536,t=3,p=4$gpKFndFoG6bcXrx7R60sag$uhxmJMX03O6QlL0WZS+WdRhCOnGEoIpzUrL2vBzRN+c', NULL, 'active',   0, NULL, '2025-03-03'::timestamptz, NOW()),
  (gen_random_uuid(), 'dvq@medinet.vn',  'Dương Văn Q',    NULL, NULL, '$argon2id$v=19$m=65536,t=3,p=4$gpKFndFoG6bcXrx7R60sag$uhxmJMX03O6QlL0WZS+WdRhCOnGEoIpzUrL2vBzRN+c', NULL, 'active',   0, NULL, '2025-01-10'::timestamptz, NOW()),
  (gen_random_uuid(), 'ltr@medinet.vn',  'Lương Thị R',    NULL, NULL, '$argon2id$v=19$m=65536,t=3,p=4$gpKFndFoG6bcXrx7R60sag$uhxmJMX03O6QlL0WZS+WdRhCOnGEoIpzUrL2vBzRN+c', NULL, 'active',   0, NULL, '2025-01-28'::timestamptz, NOW()),
  (gen_random_uuid(), 'cvs@medinet.vn',  'Cao Văn S',      NULL, NULL, '$argon2id$v=19$m=65536,t=3,p=4$gpKFndFoG6bcXrx7R60sag$uhxmJMX03O6QlL0WZS+WdRhCOnGEoIpzUrL2vBzRN+c', NULL, 'active',   0, NULL, '2025-01-15'::timestamptz, NOW()),
  (gen_random_uuid(), 'ttt@medinet.vn',  'Triệu Thị T',   NULL, NULL, '$argon2id$v=19$m=65536,t=3,p=4$gpKFndFoG6bcXrx7R60sag$uhxmJMX03O6QlL0WZS+WdRhCOnGEoIpzUrL2vBzRN+c', NULL, 'disabled',  0, NULL, '2025-02-05'::timestamptz, NOW()),
  (gen_random_uuid(), 'kvu@medinet.vn',  'Kiều Văn U',     NULL, NULL, '$argon2id$v=19$m=65536,t=3,p=4$gpKFndFoG6bcXrx7R60sag$uhxmJMX03O6QlL0WZS+WdRhCOnGEoIpzUrL2vBzRN+c', NULL, 'active',   0, NULL, '2025-02-12'::timestamptz, NOW()),
  (gen_random_uuid(), 'ttv@medinet.vn',  'Tô Thị V',       NULL, NULL, '$argon2id$v=19$m=65536,t=3,p=4$gpKFndFoG6bcXrx7R60sag$uhxmJMX03O6QlL0WZS+WdRhCOnGEoIpzUrL2vBzRN+c', NULL, 'active',   0, NULL, '2025-02-20'::timestamptz, NOW()),
  (gen_random_uuid(), 'cvw@medinet.vn',  'Châu Văn W',     NULL, NULL, '$argon2id$v=19$m=65536,t=3,p=4$gpKFndFoG6bcXrx7R60sag$uhxmJMX03O6QlL0WZS+WdRhCOnGEoIpzUrL2vBzRN+c', NULL, 'active',   0, NULL, '2025-03-01'::timestamptz, NOW()),
  (gen_random_uuid(), 'ltx@medinet.vn',  'La Thị X',       NULL, NULL, '$argon2id$v=19$m=65536,t=3,p=4$gpKFndFoG6bcXrx7R60sag$uhxmJMX03O6QlL0WZS+WdRhCOnGEoIpzUrL2vBzRN+c', NULL, 'active',   0, NULL, '2025-01-08'::timestamptz, NOW()),
  (gen_random_uuid(), 'tvy@medinet.vn',  'Tăng Văn Y',     NULL, NULL, '$argon2id$v=19$m=65536,t=3,p=4$gpKFndFoG6bcXrx7R60sag$uhxmJMX03O6QlL0WZS+WdRhCOnGEoIpzUrL2vBzRN+c', NULL, 'active',   0, NULL, '2025-01-15'::timestamptz, NOW()),
  (gen_random_uuid(), 'qtz@medinet.vn',  'Quách Thị Z',    NULL, NULL, '$argon2id$v=19$m=65536,t=3,p=4$gpKFndFoG6bcXrx7R60sag$uhxmJMX03O6QlL0WZS+WdRhCOnGEoIpzUrL2vBzRN+c', NULL, 'active',   0, NULL, '2025-01-22'::timestamptz, NOW()),
  (gen_random_uuid(), 'tvaa@medinet.vn', 'Trịnh Văn AA',   NULL, NULL, '$argon2id$v=19$m=65536,t=3,p=4$gpKFndFoG6bcXrx7R60sag$uhxmJMX03O6QlL0WZS+WdRhCOnGEoIpzUrL2vBzRN+c', NULL, 'active',   0, NULL, '2025-02-01'::timestamptz, NOW()),
  (gen_random_uuid(), 'dtbb@medinet.vn', 'Đinh Thị BB',    NULL, NULL, '$argon2id$v=19$m=65536,t=3,p=4$gpKFndFoG6bcXrx7R60sag$uhxmJMX03O6QlL0WZS+WdRhCOnGEoIpzUrL2vBzRN+c', NULL, 'active',   0, NULL, '2025-02-10'::timestamptz, NOW()),
  (gen_random_uuid(), 'lvcc@medinet.vn', 'Lâm Văn CC',     NULL, NULL, '$argon2id$v=19$m=65536,t=3,p=4$gpKFndFoG6bcXrx7R60sag$uhxmJMX03O6QlL0WZS+WdRhCOnGEoIpzUrL2vBzRN+c', NULL, 'disabled',  0, NULL, '2025-02-18'::timestamptz, NOW()),
  (gen_random_uuid(), 'ttdd@medinet.vn', 'Thái Thị DD',    NULL, NULL, '$argon2id$v=19$m=65536,t=3,p=4$gpKFndFoG6bcXrx7R60sag$uhxmJMX03O6QlL0WZS+WdRhCOnGEoIpzUrL2vBzRN+c', NULL, 'active',   0, NULL, '2025-02-25'::timestamptz, NOW()),
  (gen_random_uuid(), 'mvee@medinet.vn', 'Mạc Văn EE',     NULL, NULL, '$argon2id$v=19$m=65536,t=3,p=4$gpKFndFoG6bcXrx7R60sag$uhxmJMX03O6QlL0WZS+WdRhCOnGEoIpzUrL2vBzRN+c', NULL, 'active',   0, NULL, '2025-03-05'::timestamptz, NOW()),
  (gen_random_uuid(), 'ttff@medinet.vn', 'Từ Thị FF',      NULL, NULL, '$argon2id$v=19$m=65536,t=3,p=4$gpKFndFoG6bcXrx7R60sag$uhxmJMX03O6QlL0WZS+WdRhCOnGEoIpzUrL2vBzRN+c', NULL, 'active',   0, NULL, '2025-03-10'::timestamptz, NOW()),
  (gen_random_uuid(), 'hvgg@medinet.vn', 'Hà Văn GG',      NULL, NULL, '$argon2id$v=19$m=65536,t=3,p=4$gpKFndFoG6bcXrx7R60sag$uhxmJMX03O6QlL0WZS+WdRhCOnGEoIpzUrL2vBzRN+c', NULL, 'active',   0, NULL, '2025-03-12'::timestamptz, NOW()),
  (gen_random_uuid(), 'sthh@medinet.vn', 'Sơn Thị HH',     NULL, NULL, '$argon2id$v=19$m=65536,t=3,p=4$gpKFndFoG6bcXrx7R60sag$uhxmJMX03O6QlL0WZS+WdRhCOnGEoIpzUrL2vBzRN+c', NULL, 'active',   0, NULL, '2025-03-15'::timestamptz, NOW()),
  (gen_random_uuid(), 'ovii@medinet.vn', 'Ông Văn II',     NULL, NULL, '$argon2id$v=19$m=65536,t=3,p=4$gpKFndFoG6bcXrx7R60sag$uhxmJMX03O6QlL0WZS+WdRhCOnGEoIpzUrL2vBzRN+c', NULL, 'active',   0, NULL, '2025-03-18'::timestamptz, NOW()),
  (gen_random_uuid(), 'atkk@medinet.vn', 'Âu Thị KK',      NULL, NULL, '$argon2id$v=19$m=65536,t=3,p=4$gpKFndFoG6bcXrx7R60sag$uhxmJMX03O6QlL0WZS+WdRhCOnGEoIpzUrL2vBzRN+c', NULL, 'active',   0, NULL, '2025-03-20'::timestamptz, NOW())

ON CONFLICT (email) DO UPDATE SET
  name         = EXCLUDED.name,
  password_hash = EXCLUDED.password_hash,
  status       = EXCLUDED.status,
  updated_at   = NOW();

-- ---------------------------------------------------------------------------
-- 3. USER-HUB ROLES
-- ---------------------------------------------------------------------------
-- Clear existing demo roles (but keep admin@medinet.vn roles intact)
DELETE FROM user_hub_roles
WHERE user_id IN (
  SELECT id FROM users WHERE email != 'admin@medinet.vn'
);

-- FE role mapping: 'admin' -> 'admin', 'viewer' -> 'viewer'
-- Hub mapping: '1' -> tamdao, '2' -> dmd, '3' -> hcns

INSERT INTO user_hub_roles (user_id, hub_id, role) VALUES
  -- u1: nva@medinet.vn, admin, hub tamdao
  ((SELECT id FROM users WHERE email = 'nva@medinet.vn'),  (SELECT id FROM hubs WHERE code = 'tamdao'), 'admin'),
  -- u2: ttb@medinet.vn, viewer, hub tamdao
  ((SELECT id FROM users WHERE email = 'ttb@medinet.vn'),  (SELECT id FROM hubs WHERE code = 'tamdao'), 'viewer'),
  -- u3: lmc@medinet.vn, viewer, hub tamdao
  ((SELECT id FROM users WHERE email = 'lmc@medinet.vn'),  (SELECT id FROM hubs WHERE code = 'tamdao'), 'viewer'),
  -- u4: pvd@medinet.vn, admin, hub dmd
  ((SELECT id FROM users WHERE email = 'pvd@medinet.vn'),  (SELECT id FROM hubs WHERE code = 'dmd'),    'admin'),
  -- u5: hte@medinet.vn, viewer, hub hcns
  ((SELECT id FROM users WHERE email = 'hte@medinet.vn'),  (SELECT id FROM hubs WHERE code = 'hcns'),   'viewer'),
  -- u6: vdf@medinet.vn, viewer, hub tamdao
  ((SELECT id FROM users WHERE email = 'vdf@medinet.vn'),  (SELECT id FROM hubs WHERE code = 'tamdao'), 'viewer'),
  -- u7: dtg@medinet.vn, admin, hub tamdao
  ((SELECT id FROM users WHERE email = 'dtg@medinet.vn'),  (SELECT id FROM hubs WHERE code = 'tamdao'), 'admin'),
  -- u8: bvh@medinet.vn, viewer, hub tamdao
  ((SELECT id FROM users WHERE email = 'bvh@medinet.vn'),  (SELECT id FROM hubs WHERE code = 'tamdao'), 'viewer'),
  -- u9: nti@medinet.vn, viewer, hub tamdao
  ((SELECT id FROM users WHERE email = 'nti@medinet.vn'),  (SELECT id FROM hubs WHERE code = 'tamdao'), 'viewer'),
  -- u10: dvk@medinet.vn, viewer, hub tamdao
  ((SELECT id FROM users WHERE email = 'dvk@medinet.vn'),  (SELECT id FROM hubs WHERE code = 'tamdao'), 'viewer'),
  -- u11: ptl@medinet.vn, viewer, hub tamdao
  ((SELECT id FROM users WHERE email = 'ptl@medinet.vn'),  (SELECT id FROM hubs WHERE code = 'tamdao'), 'viewer'),
  -- u12: lvm@medinet.vn, admin, hub tamdao
  ((SELECT id FROM users WHERE email = 'lvm@medinet.vn'),  (SELECT id FROM hubs WHERE code = 'tamdao'), 'admin'),
  -- u13: htn@medinet.vn, viewer, hub tamdao
  ((SELECT id FROM users WHERE email = 'htn@medinet.vn'),  (SELECT id FROM hubs WHERE code = 'tamdao'), 'viewer'),
  -- u14: mvo@medinet.vn, viewer, hub tamdao
  ((SELECT id FROM users WHERE email = 'mvo@medinet.vn'),  (SELECT id FROM hubs WHERE code = 'tamdao'), 'viewer'),
  -- u15: ttp@medinet.vn, viewer, hub tamdao
  ((SELECT id FROM users WHERE email = 'ttp@medinet.vn'),  (SELECT id FROM hubs WHERE code = 'tamdao'), 'viewer'),
  -- u16: dvq@medinet.vn, viewer, hub dmd
  ((SELECT id FROM users WHERE email = 'dvq@medinet.vn'),  (SELECT id FROM hubs WHERE code = 'dmd'),    'viewer'),
  -- u17: ltr@medinet.vn, viewer, hub dmd
  ((SELECT id FROM users WHERE email = 'ltr@medinet.vn'),  (SELECT id FROM hubs WHERE code = 'dmd'),    'viewer'),
  -- u18: cvs@medinet.vn, admin, hub dmd
  ((SELECT id FROM users WHERE email = 'cvs@medinet.vn'),  (SELECT id FROM hubs WHERE code = 'dmd'),    'admin'),
  -- u19: ttt@medinet.vn, viewer, hub dmd
  ((SELECT id FROM users WHERE email = 'ttt@medinet.vn'),  (SELECT id FROM hubs WHERE code = 'dmd'),    'viewer'),
  -- u20: kvu@medinet.vn, viewer, hub dmd
  ((SELECT id FROM users WHERE email = 'kvu@medinet.vn'),  (SELECT id FROM hubs WHERE code = 'dmd'),    'viewer'),
  -- u21: ttv@medinet.vn, viewer, hub dmd
  ((SELECT id FROM users WHERE email = 'ttv@medinet.vn'),  (SELECT id FROM hubs WHERE code = 'dmd'),    'viewer'),
  -- u22: cvw@medinet.vn, viewer, hub dmd
  ((SELECT id FROM users WHERE email = 'cvw@medinet.vn'),  (SELECT id FROM hubs WHERE code = 'dmd'),    'viewer'),
  -- u23: ltx@medinet.vn, viewer, hub hcns
  ((SELECT id FROM users WHERE email = 'ltx@medinet.vn'),  (SELECT id FROM hubs WHERE code = 'hcns'),   'viewer'),
  -- u24: tvy@medinet.vn, admin, hub hcns
  ((SELECT id FROM users WHERE email = 'tvy@medinet.vn'),  (SELECT id FROM hubs WHERE code = 'hcns'),   'admin'),
  -- u25: qtz@medinet.vn, viewer, hub hcns
  ((SELECT id FROM users WHERE email = 'qtz@medinet.vn'),  (SELECT id FROM hubs WHERE code = 'hcns'),   'viewer'),
  -- u26: tvaa@medinet.vn, viewer, hub hcns
  ((SELECT id FROM users WHERE email = 'tvaa@medinet.vn'), (SELECT id FROM hubs WHERE code = 'hcns'),   'viewer'),
  -- u27: dtbb@medinet.vn, viewer, hub hcns
  ((SELECT id FROM users WHERE email = 'dtbb@medinet.vn'), (SELECT id FROM hubs WHERE code = 'hcns'),   'viewer'),
  -- u28: lvcc@medinet.vn, viewer, hub hcns
  ((SELECT id FROM users WHERE email = 'lvcc@medinet.vn'), (SELECT id FROM hubs WHERE code = 'hcns'),   'viewer'),
  -- u29: ttdd@medinet.vn, viewer, hub hcns
  ((SELECT id FROM users WHERE email = 'ttdd@medinet.vn'), (SELECT id FROM hubs WHERE code = 'hcns'),   'viewer'),
  -- u30: mvee@medinet.vn, viewer, hub hcns
  ((SELECT id FROM users WHERE email = 'mvee@medinet.vn'), (SELECT id FROM hubs WHERE code = 'hcns'),   'viewer'),
  -- u31: ttff@medinet.vn, viewer, hub hcns
  ((SELECT id FROM users WHERE email = 'ttff@medinet.vn'), (SELECT id FROM hubs WHERE code = 'hcns'),   'viewer'),
  -- u32: hvgg@medinet.vn, admin, hub hcns
  ((SELECT id FROM users WHERE email = 'hvgg@medinet.vn'), (SELECT id FROM hubs WHERE code = 'hcns'),   'admin'),
  -- u33: sthh@medinet.vn, viewer, hub tamdao
  ((SELECT id FROM users WHERE email = 'sthh@medinet.vn'), (SELECT id FROM hubs WHERE code = 'tamdao'), 'viewer'),
  -- u34: ovii@medinet.vn, viewer, hub tamdao
  ((SELECT id FROM users WHERE email = 'ovii@medinet.vn'), (SELECT id FROM hubs WHERE code = 'tamdao'), 'viewer'),
  -- u35: atkk@medinet.vn, viewer, hub dmd
  ((SELECT id FROM users WHERE email = 'atkk@medinet.vn'), (SELECT id FROM hubs WHERE code = 'dmd'),    'viewer')

ON CONFLICT (user_id, hub_id) DO UPDATE SET
  role = EXCLUDED.role;

-- ---------------------------------------------------------------------------
-- 4. API KEYS (15 keys — delete existing demo keys, then re-insert)
-- ---------------------------------------------------------------------------
-- Delete existing demo API keys (identified by name pattern)
DELETE FROM api_keys WHERE name IN (
  'Claude Desktop — Team AI',
  'ChatGPT Plugin',
  'Test Key cũ',
  'Gemini Agent — Tâm Đạo',
  'Mobile App — iOS',
  'Mobile App — Android',
  'Webhook — Slack Bot',
  'Data Pipeline — ETL',
  'Perplexity Integration',
  'Copilot Extension',
  'Dev Key — Staging',
  'Old Migration Key',
  'Backup Service',
  'Analytics Dashboard',
  'Temp Key — Demo'
);

-- Helper: deterministic fake SHA-256 hashes for key_hash
-- key_prefix follows pattern "mk_xxxx" (first 7 chars shown)

INSERT INTO api_keys (
  id, name, key_hash, key_prefix, permissions, allowed_hub_ids,
  allowed_rag_configs, rate_limit, expires_at, status,
  requests_today, requests_7d, bandwidth_used, last_used_at,
  created_by, created_at
) VALUES
  -- k1: Claude Desktop — Team AI (all hubs, active)
  (gen_random_uuid(),
   'Claude Desktop — Team AI',
   'a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2',
   'mk_clau',
   ARRAY['Read','Write'],
   (SELECT ARRAY_AGG(id) FROM hubs),
   ARRAY['Default (Gemini 2.0)', 'High Precision (Text-004)'],
   100, NULL, 'active',
   156, 1247, 13005037,  -- 12.4 MB
   NOW() - INTERVAL '5 minutes',
   (SELECT id FROM users WHERE email = 'admin@medinet.vn'),
   '2025-01-01'::timestamptz),

  -- k2: ChatGPT Plugin (tamdao, dmd)
  (gen_random_uuid(),
   'ChatGPT Plugin',
   'b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3',
   'mk_chat',
   ARRAY['Read'],
   ARRAY[(SELECT id FROM hubs WHERE code = 'tamdao'), (SELECT id FROM hubs WHERE code = 'dmd')],
   ARRAY['Default (Gemini 2.0)'],
   50, NULL, 'active',
   12, 89, 1258291,  -- 1.2 MB
   NOW() - INTERVAL '2 days',
   (SELECT id FROM users WHERE email = 'admin@medinet.vn'),
   '2025-02-15'::timestamptz),

  -- k3: Test Key cũ (hcns, revoked)
  (gen_random_uuid(),
   'Test Key cũ',
   'c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4',
   'mk_test',
   ARRAY['Read'],
   ARRAY[(SELECT id FROM hubs WHERE code = 'hcns')],
   ARRAY[]::TEXT[],
   10, NULL, 'revoked',
   0, 0, 0,
   NOW() - INTERVAL '30 days',
   (SELECT id FROM users WHERE email = 'admin@medinet.vn'),
   '2025-03-10'::timestamptz),

  -- k4: Gemini Agent — Tâm Đạo (tamdao)
  (gen_random_uuid(),
   'Gemini Agent — Tâm Đạo',
   'd4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5',
   'mk_gemi',
   ARRAY['Read','Write'],
   ARRAY[(SELECT id FROM hubs WHERE code = 'tamdao')],
   ARRAY['Default (Gemini 2.0)'],
   200, NULL, 'active',
   312, 2340, 29465754,  -- 28.1 MB
   NOW() - INTERVAL '10 minutes',
   (SELECT id FROM users WHERE email = 'admin@medinet.vn'),
   '2025-01-05'::timestamptz),

  -- k5: Mobile App — iOS (all hubs)
  (gen_random_uuid(),
   'Mobile App — iOS',
   'e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6',
   'mk_ios_',
   ARRAY['Read'],
   (SELECT ARRAY_AGG(id) FROM hubs),
   ARRAY['Fast Retrieval (ChromaDB)'],
   100, NULL, 'active',
   78, 567, 5872026,  -- 5.6 MB
   NOW() - INTERVAL '1 hour',
   (SELECT id FROM users WHERE email = 'admin@medinet.vn'),
   '2025-01-20'::timestamptz),

  -- k6: Mobile App — Android (all hubs)
  (gen_random_uuid(),
   'Mobile App — Android',
   'f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1',
   'mk_andr',
   ARRAY['Read'],
   (SELECT ARRAY_AGG(id) FROM hubs),
   ARRAY['Fast Retrieval (ChromaDB)'],
   100, NULL, 'active',
   65, 432, 4509716,  -- 4.3 MB
   NOW() - INTERVAL '30 minutes',
   (SELECT id FROM users WHERE email = 'admin@medinet.vn'),
   '2025-01-20'::timestamptz),

  -- k7: Webhook — Slack Bot (hcns)
  (gen_random_uuid(),
   'Webhook — Slack Bot',
   'a7b8c9d0e1f2a7b8c9d0e1f2a7b8c9d0e1f2a7b8c9d0e1f2a7b8c9d0e1f2a7b8',
   'mk_slac',
   ARRAY['Read'],
   ARRAY[(SELECT id FROM hubs WHERE code = 'hcns')],
   ARRAY['Default (Gemini 2.0)'],
   30, NULL, 'active',
   23, 156, 911360,  -- 890 KB
   NOW() - INTERVAL '3 hours',
   (SELECT id FROM users WHERE email = 'admin@medinet.vn'),
   '2025-02-01'::timestamptz),

  -- k8: Data Pipeline — ETL (all hubs)
  (gen_random_uuid(),
   'Data Pipeline — ETL',
   'b8c9d0e1f2a7b8c9d0e1f2a7b8c9d0e1f2a7b8c9d0e1f2a7b8c9d0e1f2a7b8c9',
   'mk_etl_',
   ARRAY['Read','Write'],
   (SELECT ARRAY_AGG(id) FROM hubs),
   ARRAY['High Precision (Text-004)'],
   500, NULL, 'active',
   0, 890, 47395430,  -- 45.2 MB
   NOW() - INTERVAL '6 hours',
   (SELECT id FROM users WHERE email = 'admin@medinet.vn'),
   '2025-02-10'::timestamptz),

  -- k9: Perplexity Integration (tamdao, dmd)
  (gen_random_uuid(),
   'Perplexity Integration',
   'c9d0e1f2a7b8c9d0e1f2a7b8c9d0e1f2a7b8c9d0e1f2a7b8c9d0e1f2a7b8c9d0',
   'mk_perp',
   ARRAY['Read'],
   ARRAY[(SELECT id FROM hubs WHERE code = 'tamdao'), (SELECT id FROM hubs WHERE code = 'dmd')],
   ARRAY['Default (Gemini 2.0)'],
   50, NULL, 'active',
   0, 234, 2202009,  -- 2.1 MB
   NOW() - INTERVAL '1 day',
   (SELECT id FROM users WHERE email = 'admin@medinet.vn'),
   '2025-02-15'::timestamptz),

  -- k10: Copilot Extension (hcns)
  (gen_random_uuid(),
   'Copilot Extension',
   'd0e1f2a7b8c9d0e1f2a7b8c9d0e1f2a7b8c9d0e1f2a7b8c9d0e1f2a7b8c9d0e1',
   'mk_copi',
   ARRAY['Read','Write'],
   ARRAY[(SELECT id FROM hubs WHERE code = 'hcns')],
   ARRAY['Default (Gemini 2.0)', 'High Precision (Text-004)'],
   100, NULL, 'active',
   45, 345, 3565158,  -- 3.4 MB
   NOW() - INTERVAL '4 hours',
   (SELECT id FROM users WHERE email = 'admin@medinet.vn'),
   '2025-02-20'::timestamptz),

  -- k11: Dev Key — Staging (all hubs)
  (gen_random_uuid(),
   'Dev Key — Staging',
   'e1f2a7b8c9d0e1f2a7b8c9d0e1f2a7b8c9d0e1f2a7b8c9d0e1f2a7b8c9d0e1f2',
   'mk_dev_',
   ARRAY['Read','Write'],
   (SELECT ARRAY_AGG(id) FROM hubs),
   ARRAY['Default (Gemini 2.0)', 'Fast Retrieval (ChromaDB)'],
   20, NULL, 'active',
   0, 45, 327680,  -- 320 KB
   NOW() - INTERVAL '2 days',
   (SELECT id FROM users WHERE email = 'admin@medinet.vn'),
   '2025-02-25'::timestamptz),

  -- k12: Old Migration Key (dmd, revoked)
  (gen_random_uuid(),
   'Old Migration Key',
   'f2a7b8c9d0e1f2a7b8c9d0e1f2a7b8c9d0e1f2a7b8c9d0e1f2a7b8c9d0e1f2a7',
   'mk_migr',
   ARRAY['Read'],
   ARRAY[(SELECT id FROM hubs WHERE code = 'dmd')],
   ARRAY[]::TEXT[],
   10, NULL, 'revoked',
   0, 0, 0,
   NOW() - INTERVAL '60 days',
   (SELECT id FROM users WHERE email = 'admin@medinet.vn'),
   '2024-12-01'::timestamptz),

  -- k13: Backup Service (all hubs)
  (gen_random_uuid(),
   'Backup Service',
   'a3b4c5d6e7f8a3b4c5d6e7f8a3b4c5d6e7f8a3b4c5d6e7f8a3b4c5d6e7f8a3b4',
   'mk_back',
   ARRAY['Read'],
   (SELECT ARRAY_AGG(id) FROM hubs),
   ARRAY['High Precision (Text-004)'],
   50, NULL, 'active',
   24, 168, 71092633,  -- 67.8 MB
   NOW() - INTERVAL '12 hours',
   (SELECT id FROM users WHERE email = 'admin@medinet.vn'),
   '2025-03-01'::timestamptz),

  -- k14: Analytics Dashboard (all hubs)
  (gen_random_uuid(),
   'Analytics Dashboard',
   'b4c5d6e7f8a3b4c5d6e7f8a3b4c5d6e7f8a3b4c5d6e7f8a3b4c5d6e7f8a3b4c5',
   'mk_anal',
   ARRAY['Read'],
   (SELECT ARRAY_AGG(id) FROM hubs),
   ARRAY['Fast Retrieval (ChromaDB)'],
   200, NULL, 'active',
   189, 1120, 9332736,  -- 8.9 MB
   NOW() - INTERVAL '2 hours',
   (SELECT id FROM users WHERE email = 'admin@medinet.vn'),
   '2025-03-05'::timestamptz),

  -- k15: Temp Key — Demo (tamdao, revoked)
  (gen_random_uuid(),
   'Temp Key — Demo',
   'c5d6e7f8a3b4c5d6e7f8a3b4c5d6e7f8a3b4c5d6e7f8a3b4c5d6e7f8a3b4c5d6',
   'mk_demo',
   ARRAY['Read'],
   ARRAY[(SELECT id FROM hubs WHERE code = 'tamdao')],
   ARRAY[]::TEXT[],
   10, NULL, 'revoked',
   0, 12, 57344,  -- 56 KB
   NOW() - INTERVAL '5 days',
   (SELECT id FROM users WHERE email = 'admin@medinet.vn'),
   '2025-03-08'::timestamptz);

-- ---------------------------------------------------------------------------
-- 5. DOCUMENTS (32 documents from mockData — delete+re-insert)
-- ---------------------------------------------------------------------------
-- Remove existing demo document_chunks first (FK dependency)
DELETE FROM document_chunks WHERE document_id IN (
  SELECT id FROM documents WHERE uploaded_by = (SELECT id FROM users WHERE email = 'admin@medinet.vn')
);

-- Remove existing demo documents
DELETE FROM documents WHERE uploaded_by = (SELECT id FROM users WHERE email = 'admin@medinet.vn');

-- Insert all documents from mockData
-- File size conversions: MB * 1048576, KB * 1024

INSERT INTO documents (
  id, name, file_type, file_size, file_path, hub_id, status, progress,
  error_message, chunk_count, uploaded_by, uploaded_at, processed_at
) VALUES
  -- doc-1: Quy-trinh-kham-benh-2024.pdf, 2.4 MB, tamdao, completed
  (gen_random_uuid(),
   'Quy-trinh-kham-benh-2024.pdf', 'pdf', 2516582,
   'uploads/tamdao/' || gen_random_uuid() || '/Quy-trinh-kham-benh-2024.pdf',
   (SELECT id FROM hubs WHERE code = 'tamdao'), 'completed', 100,
   NULL, 15,
   (SELECT id FROM users WHERE email = 'admin@medinet.vn'),
   '2024-03-20T10:00:00Z'::timestamptz, '2024-03-20T10:05:00Z'::timestamptz),

  -- doc-2: Huong-dan-su-dung-thuoc.docx, 1.1 MB, dmd, processing
  (gen_random_uuid(),
   'Huong-dan-su-dung-thuoc.docx', 'docx', 1153434,
   'uploads/dmd/' || gen_random_uuid() || '/Huong-dan-su-dung-thuoc.docx',
   (SELECT id FROM hubs WHERE code = 'dmd'), 'processing', 45,
   NULL, 0,
   (SELECT id FROM users WHERE email = 'admin@medinet.vn'),
   '2024-03-21T14:30:00Z'::timestamptz, NULL),

  -- doc-3: Chinh-sach-bao-mat.txt, 15 KB, tamdao, pending
  (gen_random_uuid(),
   'Chinh-sach-bao-mat.txt', 'txt', 15360,
   'uploads/tamdao/' || gen_random_uuid() || '/Chinh-sach-bao-mat.txt',
   (SELECT id FROM hubs WHERE code = 'tamdao'), 'pending', 0,
   NULL, 0,
   (SELECT id FROM users WHERE email = 'admin@medinet.vn'),
   '2024-03-21T16:00:00Z'::timestamptz, NULL),

  -- doc-4: Bao-cao-tai-chinh-Q1-2024.xlsx, 4.5 MB, hcns, completed
  (gen_random_uuid(),
   'Bao-cao-tai-chinh-Q1-2024.xlsx', 'xlsx', 4718592,
   'uploads/hcns/' || gen_random_uuid() || '/Bao-cao-tai-chinh-Q1-2024.xlsx',
   (SELECT id FROM hubs WHERE code = 'hcns'), 'completed', 100,
   NULL, 28,
   (SELECT id FROM users WHERE email = 'admin@medinet.vn'),
   '2024-03-22T09:00:00Z'::timestamptz, '2024-03-22T09:08:00Z'::timestamptz),

  -- doc-5: Danh-muc-thuoc-thiet-yeu.pdf, 3.2 MB, tamdao, completed
  (gen_random_uuid(),
   'Danh-muc-thuoc-thiet-yeu.pdf', 'pdf', 3355443,
   'uploads/tamdao/' || gen_random_uuid() || '/Danh-muc-thuoc-thiet-yeu.pdf',
   (SELECT id FROM hubs WHERE code = 'tamdao'), 'completed', 100,
   NULL, 22,
   (SELECT id FROM users WHERE email = 'admin@medinet.vn'),
   '2024-03-22T11:30:00Z'::timestamptz, '2024-03-22T11:38:00Z'::timestamptz),

  -- doc-6: Quy-dinh-ve-an-toan-lao-dong.docx, 850 KB, hcns, completed
  (gen_random_uuid(),
   'Quy-dinh-ve-an-toan-lao-dong.docx', 'docx', 870400,
   'uploads/hcns/' || gen_random_uuid() || '/Quy-dinh-ve-an-toan-lao-dong.docx',
   (SELECT id FROM hubs WHERE code = 'hcns'), 'completed', 100,
   NULL, 8,
   (SELECT id FROM users WHERE email = 'admin@medinet.vn'),
   '2024-03-23T08:15:00Z'::timestamptz, '2024-03-23T08:20:00Z'::timestamptz),

  -- doc-7: Ke-hoach-marketing-2024.pptx, 12.4 MB, dmd, processing
  (gen_random_uuid(),
   'Ke-hoach-marketing-2024.pptx', 'pptx', 13002342,
   'uploads/dmd/' || gen_random_uuid() || '/Ke-hoach-marketing-2024.pptx',
   (SELECT id FROM hubs WHERE code = 'dmd'), 'processing', 70,
   NULL, 0,
   (SELECT id FROM users WHERE email = 'admin@medinet.vn'),
   '2024-03-23T15:45:00Z'::timestamptz, NULL),

  -- doc-8: Bien-ban-hop-giao-ban-tuan-12.txt, 12 KB, tamdao, completed
  (gen_random_uuid(),
   'Bien-ban-hop-giao-ban-tuan-12.txt', 'txt', 12288,
   'uploads/tamdao/' || gen_random_uuid() || '/Bien-ban-hop-giao-ban-tuan-12.txt',
   (SELECT id FROM hubs WHERE code = 'tamdao'), 'completed', 100,
   NULL, 3,
   (SELECT id FROM users WHERE email = 'admin@medinet.vn'),
   '2024-03-24T10:30:00Z'::timestamptz, '2024-03-24T10:32:00Z'::timestamptz),

  -- doc-9: Huong-dan-so-cuu-co-ban.pdf, 5.6 MB, tamdao, completed
  (gen_random_uuid(),
   'Huong-dan-so-cuu-co-ban.pdf', 'pdf', 5872026,
   'uploads/tamdao/' || gen_random_uuid() || '/Huong-dan-so-cuu-co-ban.pdf',
   (SELECT id FROM hubs WHERE code = 'tamdao'), 'completed', 100,
   NULL, 35,
   (SELECT id FROM users WHERE email = 'admin@medinet.vn'),
   '2024-03-24T14:00:00Z'::timestamptz, '2024-03-24T14:10:00Z'::timestamptz),

  -- doc-10: Quy-trinh-tiep-nhan-benh-nhan.docx, 1.2 MB, dmd, completed
  (gen_random_uuid(),
   'Quy-trinh-tiep-nhan-benh-nhan.docx', 'docx', 1258291,
   'uploads/dmd/' || gen_random_uuid() || '/Quy-trinh-tiep-nhan-benh-nhan.docx',
   (SELECT id FROM hubs WHERE code = 'dmd'), 'completed', 100,
   NULL, 10,
   (SELECT id FROM users WHERE email = 'admin@medinet.vn'),
   '2024-03-25T09:30:00Z'::timestamptz, '2024-03-25T09:35:00Z'::timestamptz),

  -- doc-11: Bao-cao-nghien-cuu-thi-truong.pdf, 8.4 MB, dmd, completed
  (gen_random_uuid(),
   'Bao-cao-nghien-cuu-thi-truong.pdf', 'pdf', 8808038,
   'uploads/dmd/' || gen_random_uuid() || '/Bao-cao-nghien-cuu-thi-truong.pdf',
   (SELECT id FROM hubs WHERE code = 'dmd'), 'completed', 100,
   NULL, 52,
   (SELECT id FROM users WHERE email = 'admin@medinet.vn'),
   '2024-03-25T16:20:00Z'::timestamptz, '2024-03-25T16:35:00Z'::timestamptz),

  -- doc-12: Noi-quy-phong-kham.txt, 8 KB, tamdao, completed
  (gen_random_uuid(),
   'Noi-quy-phong-kham.txt', 'txt', 8192,
   'uploads/tamdao/' || gen_random_uuid() || '/Noi-quy-phong-kham.txt',
   (SELECT id FROM hubs WHERE code = 'tamdao'), 'completed', 100,
   NULL, 2,
   (SELECT id FROM users WHERE email = 'admin@medinet.vn'),
   '2024-03-26T08:00:00Z'::timestamptz, '2024-03-26T08:01:00Z'::timestamptz),

  -- doc-13: Danh-sach-doi-tac-cung-ung.xlsx, 1.5 MB, hcns, completed
  (gen_random_uuid(),
   'Danh-sach-doi-tac-cung-ung.xlsx', 'xlsx', 1572864,
   'uploads/hcns/' || gen_random_uuid() || '/Danh-sach-doi-tac-cung-ung.xlsx',
   (SELECT id FROM hubs WHERE code = 'hcns'), 'completed', 100,
   NULL, 12,
   (SELECT id FROM users WHERE email = 'admin@medinet.vn'),
   '2024-03-26T11:00:00Z'::timestamptz, '2024-03-26T11:05:00Z'::timestamptz),

  -- doc-14: Huong-dan-ve-sinh-khu-trung.pdf, 2.8 MB, tamdao, completed
  (gen_random_uuid(),
   'Huong-dan-ve-sinh-khu-trung.pdf', 'pdf', 2936013,
   'uploads/tamdao/' || gen_random_uuid() || '/Huong-dan-ve-sinh-khu-trung.pdf',
   (SELECT id FROM hubs WHERE code = 'tamdao'), 'completed', 100,
   NULL, 18,
   (SELECT id FROM users WHERE email = 'admin@medinet.vn'),
   '2024-03-27T13:45:00Z'::timestamptz, '2024-03-27T13:52:00Z'::timestamptz),

  -- doc-15: Quy-dinh-ve-quan-ly-ho-so-benh-an.docx, 1.8 MB, dmd, completed
  (gen_random_uuid(),
   'Quy-dinh-ve-quan-ly-ho-so-benh-an.docx', 'docx', 1887437,
   'uploads/dmd/' || gen_random_uuid() || '/Quy-dinh-ve-quan-ly-ho-so-benh-an.docx',
   (SELECT id FROM hubs WHERE code = 'dmd'), 'completed', 100,
   NULL, 14,
   (SELECT id FROM users WHERE email = 'admin@medinet.vn'),
   '2024-03-27T15:30:00Z'::timestamptz, '2024-03-27T15:38:00Z'::timestamptz),

  -- doc-16: Bao-cao-chat-luong-dich-vu-thang-3.pdf, 4.2 MB, tamdao, completed
  (gen_random_uuid(),
   'Bao-cao-chat-luong-dich-vu-thang-3.pdf', 'pdf', 4404019,
   'uploads/tamdao/' || gen_random_uuid() || '/Bao-cao-chat-luong-dich-vu-thang-3.pdf',
   (SELECT id FROM hubs WHERE code = 'tamdao'), 'completed', 100,
   NULL, 26,
   (SELECT id FROM users WHERE email = 'admin@medinet.vn'),
   '2024-03-28T10:15:00Z'::timestamptz, '2024-03-28T10:25:00Z'::timestamptz),

  -- doc-17: Ke-hoach-dao-tao-nhan-vien-Q2.docx, 1.1 MB, hcns, completed
  (gen_random_uuid(),
   'Ke-hoach-dao-tao-nhan-vien-Q2.docx', 'docx', 1153434,
   'uploads/hcns/' || gen_random_uuid() || '/Ke-hoach-dao-tao-nhan-vien-Q2.docx',
   (SELECT id FROM hubs WHERE code = 'hcns'), 'completed', 100,
   NULL, 9,
   (SELECT id FROM users WHERE email = 'admin@medinet.vn'),
   '2024-03-28T14:30:00Z'::timestamptz, '2024-03-28T14:36:00Z'::timestamptz),

  -- doc-18: Quy-trinh-xu-ly-rac-thai-y-te.pdf, 3.5 MB, tamdao, completed
  (gen_random_uuid(),
   'Quy-trinh-xu-ly-rac-thai-y-te.pdf', 'pdf', 3670016,
   'uploads/tamdao/' || gen_random_uuid() || '/Quy-trinh-xu-ly-rac-thai-y-te.pdf',
   (SELECT id FROM hubs WHERE code = 'tamdao'), 'completed', 100,
   NULL, 20,
   (SELECT id FROM users WHERE email = 'admin@medinet.vn'),
   '2024-03-29T09:00:00Z'::timestamptz, '2024-03-29T09:08:00Z'::timestamptz),

  -- doc-19: Danh-muc-trang-thiet-bi-y-te.xlsx, 5.8 MB, tamdao, completed
  (gen_random_uuid(),
   'Danh-muc-trang-thiet-bi-y-te.xlsx', 'xlsx', 6081740,
   'uploads/tamdao/' || gen_random_uuid() || '/Danh-muc-trang-thiet-bi-y-te.xlsx',
   (SELECT id FROM hubs WHERE code = 'tamdao'), 'completed', 100,
   NULL, 38,
   (SELECT id FROM users WHERE email = 'admin@medinet.vn'),
   '2024-03-29T11:45:00Z'::timestamptz, '2024-03-29T11:55:00Z'::timestamptz),

  -- doc-20: Huong-dan-su-dung-phan-mem-quan-ly.pdf, 10.2 MB, hcns, completed
  (gen_random_uuid(),
   'Huong-dan-su-dung-phan-mem-quan-ly.pdf', 'pdf', 10695475,
   'uploads/hcns/' || gen_random_uuid() || '/Huong-dan-su-dung-phan-mem-quan-ly.pdf',
   (SELECT id FROM hubs WHERE code = 'hcns'), 'completed', 100,
   NULL, 65,
   (SELECT id FROM users WHERE email = 'admin@medinet.vn'),
   '2024-03-30T15:00:00Z'::timestamptz, '2024-03-30T15:15:00Z'::timestamptz),

  -- doc-21: Quy-dinh-ve-trang-phuc-nhan-vien.docx, 750 KB, tamdao, completed
  (gen_random_uuid(),
   'Quy-dinh-ve-trang-phuc-nhan-vien.docx', 'docx', 768000,
   'uploads/tamdao/' || gen_random_uuid() || '/Quy-dinh-ve-trang-phuc-nhan-vien.docx',
   (SELECT id FROM hubs WHERE code = 'tamdao'), 'completed', 100,
   NULL, 6,
   (SELECT id FROM users WHERE email = 'admin@medinet.vn'),
   '2024-03-30T16:30:00Z'::timestamptz, '2024-03-30T16:33:00Z'::timestamptz),

  -- doc-22: Bao-cao-ket-qua-kham-suc-khoe-doan.pdf, 15.4 MB, dmd, completed
  (gen_random_uuid(),
   'Bao-cao-ket-qua-kham-suc-khoe-doan.pdf', 'pdf', 16147865,
   'uploads/dmd/' || gen_random_uuid() || '/Bao-cao-ket-qua-kham-suc-khoe-doan.pdf',
   (SELECT id FROM hubs WHERE code = 'dmd'), 'completed', 100,
   NULL, 96,
   (SELECT id FROM users WHERE email = 'admin@medinet.vn'),
   '2024-03-31T10:00:00Z'::timestamptz, '2024-03-31T10:20:00Z'::timestamptz),

  -- doc-23: Ke-hoach-to-chuc-su-kien-1-5.pptx, 8.6 MB, hcns, completed
  (gen_random_uuid(),
   'Ke-hoach-to-chuc-su-kien-1-5.pptx', 'pptx', 9017753,
   'uploads/hcns/' || gen_random_uuid() || '/Ke-hoach-to-chuc-su-kien-1-5.pptx',
   (SELECT id FROM hubs WHERE code = 'hcns'), 'completed', 100,
   NULL, 54,
   (SELECT id FROM users WHERE email = 'admin@medinet.vn'),
   '2024-03-31T14:00:00Z'::timestamptz, '2024-03-31T14:12:00Z'::timestamptz),

  -- doc-24: Quy-trinh-bao-tri-may-moc.docx, 1.4 MB, tamdao, completed
  (gen_random_uuid(),
   'Quy-trinh-bao-tri-may-moc.docx', 'docx', 1468006,
   'uploads/tamdao/' || gen_random_uuid() || '/Quy-trinh-bao-tri-may-moc.docx',
   (SELECT id FROM hubs WHERE code = 'tamdao'), 'completed', 100,
   NULL, 11,
   (SELECT id FROM users WHERE email = 'admin@medinet.vn'),
   '2024-04-01T08:30:00Z'::timestamptz, '2024-04-01T08:36:00Z'::timestamptz),

  -- doc-25: Danh-sach-nhan-vien-xuat-sac-thang-3.xlsx, 45 KB, tamdao, completed
  (gen_random_uuid(),
   'Danh-sach-nhan-vien-xuat-sac-thang-3.xlsx', 'xlsx', 46080,
   'uploads/tamdao/' || gen_random_uuid() || '/Danh-sach-nhan-vien-xuat-sac-thang-3.xlsx',
   (SELECT id FROM hubs WHERE code = 'tamdao'), 'completed', 100,
   NULL, 1,
   (SELECT id FROM users WHERE email = 'admin@medinet.vn'),
   '2024-04-01T11:00:00Z'::timestamptz, '2024-04-01T11:01:00Z'::timestamptz),

  -- doc-26: Huong-dan-phong-chay-chua-chay.pdf, 4.8 MB, tamdao, completed
  (gen_random_uuid(),
   'Huong-dan-phong-chay-chua-chay.pdf', 'pdf', 5033165,
   'uploads/tamdao/' || gen_random_uuid() || '/Huong-dan-phong-chay-chua-chay.pdf',
   (SELECT id FROM hubs WHERE code = 'tamdao'), 'completed', 100,
   NULL, 30,
   (SELECT id FROM users WHERE email = 'admin@medinet.vn'),
   '2024-04-02T09:45:00Z'::timestamptz, '2024-04-02T09:55:00Z'::timestamptz),

  -- doc-27: Quy-dinh-ve-nghi-phep-va-le-tet.docx, 1.2 MB, hcns, completed
  (gen_random_uuid(),
   'Quy-dinh-ve-nghi-phep-va-le-tet.docx', 'docx', 1258291,
   'uploads/hcns/' || gen_random_uuid() || '/Quy-dinh-ve-nghi-phep-va-le-tet.docx',
   (SELECT id FROM hubs WHERE code = 'hcns'), 'completed', 100,
   NULL, 10,
   (SELECT id FROM users WHERE email = 'admin@medinet.vn'),
   '2024-04-02T14:15:00Z'::timestamptz, '2024-04-02T14:22:00Z'::timestamptz),

  -- doc-28: Bao-cao-su-dung-vat-tu-tieu-hao.pdf, 2.5 MB, tamdao, completed
  (gen_random_uuid(),
   'Bao-cao-su-dung-vat-tu-tieu-hao.pdf', 'pdf', 2621440,
   'uploads/tamdao/' || gen_random_uuid() || '/Bao-cao-su-dung-vat-tu-tieu-hao.pdf',
   (SELECT id FROM hubs WHERE code = 'tamdao'), 'completed', 100,
   NULL, 16,
   (SELECT id FROM users WHERE email = 'admin@medinet.vn'),
   '2024-04-03T10:30:00Z'::timestamptz, '2024-04-03T10:38:00Z'::timestamptz),

  -- doc-29: Ke-hoach-phat-trien-dich-vu-moi.docx, 2.1 MB, dmd, completed
  (gen_random_uuid(),
   'Ke-hoach-phat-trien-dich-vu-moi.docx', 'docx', 2202009,
   'uploads/dmd/' || gen_random_uuid() || '/Ke-hoach-phat-trien-dich-vu-moi.docx',
   (SELECT id FROM hubs WHERE code = 'dmd'), 'completed', 100,
   NULL, 13,
   (SELECT id FROM users WHERE email = 'admin@medinet.vn'),
   '2024-04-03T15:45:00Z'::timestamptz, '2024-04-03T15:52:00Z'::timestamptz),

  -- doc-30: Bien-ban-kiem-ke-tai-san-cuoi-nam.xlsx, 3.4 MB, tamdao, completed
  (gen_random_uuid(),
   'Bien-ban-kiem-ke-tai-san-cuoi-nam.xlsx', 'xlsx', 3565158,
   'uploads/tamdao/' || gen_random_uuid() || '/Bien-ban-kiem-ke-tai-san-cuoi-nam.xlsx',
   (SELECT id FROM hubs WHERE code = 'tamdao'), 'completed', 100,
   NULL, 22,
   (SELECT id FROM users WHERE email = 'admin@medinet.vn'),
   '2024-04-04T09:00:00Z'::timestamptz, '2024-04-04T09:10:00Z'::timestamptz),

  -- doc-31: Huong-dan-cham-soc-benh-nhan-sau-mo.pdf, 6.2 MB, tamdao, completed
  (gen_random_uuid(),
   'Huong-dan-cham-soc-benh-nhan-sau-mo.pdf', 'pdf', 6501171,
   'uploads/tamdao/' || gen_random_uuid() || '/Huong-dan-cham-soc-benh-nhan-sau-mo.pdf',
   (SELECT id FROM hubs WHERE code = 'tamdao'), 'completed', 100,
   NULL, 40,
   (SELECT id FROM users WHERE email = 'admin@medinet.vn'),
   '2024-04-04T13:30:00Z'::timestamptz, '2024-04-04T13:42:00Z'::timestamptz),

  -- doc-32: Quy-trinh-tiep-nhan-khieu-nai.docx, 1.1 MB, dmd, completed
  (gen_random_uuid(),
   'Quy-trinh-tiep-nhan-khieu-nai.docx', 'docx', 1153434,
   'uploads/dmd/' || gen_random_uuid() || '/Quy-trinh-tiep-nhan-khieu-nai.docx',
   (SELECT id FROM hubs WHERE code = 'dmd'), 'completed', 100,
   NULL, 8,
   (SELECT id FROM users WHERE email = 'admin@medinet.vn'),
   '2024-04-05T10:45:00Z'::timestamptz, '2024-04-05T10:50:00Z'::timestamptz);

-- ---------------------------------------------------------------------------
-- 6. Summary
-- ---------------------------------------------------------------------------
DO $$
DECLARE
  hub_count    INT;
  user_count   INT;
  role_count   INT;
  key_count    INT;
  doc_count    INT;
BEGIN
  SELECT COUNT(*) INTO hub_count  FROM hubs;
  SELECT COUNT(*) INTO user_count FROM users;
  SELECT COUNT(*) INTO role_count FROM user_hub_roles;
  SELECT COUNT(*) INTO key_count  FROM api_keys;
  SELECT COUNT(*) INTO doc_count  FROM documents;

  RAISE NOTICE '==========================================';
  RAISE NOTICE 'Seed complete!';
  RAISE NOTICE '  Hubs:           %', hub_count;
  RAISE NOTICE '  Users:          %', user_count;
  RAISE NOTICE '  User-Hub Roles: %', role_count;
  RAISE NOTICE '  API Keys:       %', key_count;
  RAISE NOTICE '  Documents:      %', doc_count;
  RAISE NOTICE '==========================================';
END $$;

COMMIT;
