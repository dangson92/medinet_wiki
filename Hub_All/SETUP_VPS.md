# Setup VPS Docker — Medinet Wiki v3.1 (Step by Step, ROOT user)

> Deploy nhanh lên VPS Linux (Ubuntu 22.04 / Debian 12) bằng Docker, **chạy trực tiếp bằng user `root`** (không tạo user thường). 2 hub thật: `dmd` (Đỗ Minh Đường) + `tdt` (Thuốc Dân Tộc).
>
> Yêu cầu VPS: **4 vCPU · 8 GB RAM · 50 GB SSD · IP public tĩnh**.
>
> Cần chuẩn bị trước: SSH access root, domain `wiki.medinet.work` đã trỏ A record về IP VPS, OpenAI API key.

---

## Step 1 — Firewall UFW

```bash
# Login VPS bằng root
apt update && apt install -y ufw

# Chỉ allow 22/80/443
ufw default deny incoming && ufw default allow outgoing
ufw allow 22/tcp && ufw allow 80/tcp && ufw allow 443/tcp
ufw --force enable
ufw status
```

---

## Step 2 — Cài Docker Engine + Compose v2

```bash
apt update
apt install -y ca-certificates curl gnupg lsb-release
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
  gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | \
  tee /etc/apt/sources.list.d/docker.list > /dev/null
apt update
apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

docker --version           # verify Docker Engine từ download.docker.com (v27+ hoặc mới hơn — Docker Inc đẩy major nhanh)
docker compose version     # verify plugin từ cùng repo chính thức (KHÔNG snap, KHÔNG universe)
```

---

## Step 3 — Cài tooling phụ

```bash
apt install -y git make jq openssl build-essential python3 python3-pip

# Postgres client 16 từ PGDG official repo (Ubuntu 22.04 default repo chỉ có
# client-14, KHÔNG tương thích pg16 server đầy đủ). Cần cho `make hub-init` +
# `make hub-add` ở Step 12-13 (script gọi `psql` native với env var, không qua
# `docker compose exec`).
apt install -y postgresql-common
/usr/share/postgresql-common/pgdg/apt.postgresql.org.sh -y
apt install -y postgresql-client-16
psql --version              # phải hiện 16.x

# uv — Astral Python package manager (Rust-based, dùng thay pip/poetry).
# Bắt buộc cho `make install` + `uv run alembic` ở Step 12 (hub-init step 4).
# Installer add ~/.local/bin vào PATH qua ~/.bashrc.
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc
uv --version                # phải hiện uv 0.x.x

# Node 20 LTS qua nvm (cài cho root)
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
source ~/.bashrc
nvm install 20 && nvm use 20
node --version              # v20.x
```

---

## Step 4 — Clone repo

```bash
mkdir -p /opt/medinet
cd /opt/medinet
git clone <REPO_URL> wiki
cd wiki/Hub_All
git checkout v3.1           # hoặc main
```

---

## Step 5 — Sinh 3 secret

```bash
# QUAN TRỌNG: PG_PWD BẮT BUỘC dùng hex (KHÔNG base64) — base64 có thể chứa
# `/` `+` `=` → 2 bug ở Step 12 hub-init:
#   1. URL parser hiểu `/` là path separator trong DSN
#   2. Python configparser (alembic.ini) hiểu `%` (sau khi URL-encode) là
#      interpolation prefix → ValueError "invalid interpolation syntax"
# Hex chỉ có a-f0-9 → an toàn tuyệt đối cho cả URL DSN lẫn configparser.
PG_PWD=$(openssl rand -hex 32)
SP_SECRET=$(openssl rand -hex 32)
AES=$(python3 -c "import os,base64; print(base64.urlsafe_b64encode(os.urandom(32)).decode())")

echo "POSTGRES_PASSWORD=${PG_PWD}"
echo "SETTINGS_PROXY_SECRET=${SP_SECRET}"
echo "AES_KEY=${AES}"
# COPY 3 dòng — dùng ở Step 6 + 7. Giữ shell session mở để biến vẫn còn.
```

---

## Step 6 — Tạo `Hub_All/.env`

```bash
cat > .env <<EOF
APP_ENV=production
LOG_LEVEL=info

POSTGRES_PASSWORD=${PG_PWD}
SETTINGS_PROXY_SECRET=${SP_SECRET}

WIKI_PUBLIC_DOMAIN=wiki.medinet.work
MCP_OAUTH_ISSUER_URL=https://wiki.medinet.work/mcp

HUBS_ALLOWLIST=dmd,tdt
HUBS_ALLOWLIST_REGEX=dmd|tdt
HUB_DMD_ID=
HUB_TDT_ID=

# QUAN TRỌNG: BẮT BUỘC `{}` (empty JSON dict) — KHÔNG để rỗng. Settings validator
# `_enforce_checksum_hub_dsns_for_central` (config.py:520) chỉ accept None hoặc
# valid JSON dict. Empty string raise json.loads() → central crash lifespan boot.
# Step 14 sẽ overwrite với JSON dict thật sau khi resolve UUID 2 hub.
CHECKSUM_HUB_DSNS_JSON={}

# Dummy UUID cho 3 service ghost yte/duoc/hcns (pin trong docker-compose.yml
# base từ Phase 2 v3.0 với syntax fail-loud `${HUB_XXX_ID:?error}` — Plan 04-02
# SYNC-01). Compose parse TOÀN BỘ YAML khi `docker compose up -d postgres redis`,
# kể cả service không boot, nên thiếu 3 biến này → fail interpolation.
# 3 service ghost KHÔNG BAO GIỜ boot ở Step 15 (chỉ chạy python-api-dmd/tdt),
# nên UUID giả an toàn 100%.
HUB_YTE_ID=00000000-0000-0000-0000-000000000001
HUB_DUOC_ID=00000000-0000-0000-0000-000000000002
HUB_HCNS_ID=00000000-0000-0000-0000-000000000003

SETTINGS_CACHE_TTL_RAG_CONFIG=60
SETTINGS_CACHE_TTL_HUB_REGISTRY=300
SETTINGS_CACHE_TTL_APIKEY=60
SETTINGS_SUBSCRIBER_RECONNECT_SECONDS=5
  EOF

chmod 600 .env
```

---

## Step 7 — Tạo `api/.env`

> QUAN TRỌNG: `api/.env.example` có password `medinet_dev_pwd` HARDCODE INLINE
> trong `DATABASE_URL` + `COCOINDEX_DATABASE_URL`. Nếu chỉ `cp` + `nano` sửa
> biến `POSTGRES_PASSWORD=` riêng → 2 DSN inline VẪN GIỮ password cũ →
> alembic 401 ở Step 12. Heredoc dưới sinh đầy đủ trong 1 lần, password sync
> sẵn cả 3 nơi (POSTGRES_PASSWORD + 2 DSN inline). Hex password Step 5 KHÔNG
> cần URL-encode.

```bash
cat > api/.env <<EOF
HUB_NAME=central

POSTGRES_PASSWORD=${PG_PWD}
DATABASE_URL=postgresql+asyncpg://medinet:${PG_PWD}@localhost:5432/medinet_central
COCOINDEX_DATABASE_URL=postgresql://medinet:${PG_PWD}@localhost:5432/medinet_cocoindex

REDIS_URL=redis://localhost:6379/0

APP_NAMESPACE=medinet_prod
COCOINDEX_DB_SCHEMA=cocoindex
COCOINDEX_DB=.cocoindex/state.lmdb
COCOINDEX_LMDB_PATH=.cocoindex

JWT_PRIVATE_KEY_PATH=./keys/private.pem
JWT_PUBLIC_KEY_PATH=./keys/public.pem
JWT_ACCESS_TOKEN_TTL=900
JWT_REFRESH_TOKEN_TTL=604800

FILE_STORE_DIR=./file_store

OPENAI_API_KEY=sk-CHANGE-ME-PASTE-PAID-KEY
GEMINI_API_KEY=CHANGE-ME-PASTE-FALLBACK-KEY
RAG_EMBEDDING_PROVIDER=openai
RAG_EMBEDDING_MODEL=text-embedding-3-large
RAG_EMBEDDING_DIM=1536
RAG_LLM_PROVIDER=openai
RAG_LLM_MODEL=gpt-4o-mini

AES_KEY=${AES}

CORS_ALLOWED_ORIGINS=https://wiki.medinet.work

APP_ENV=production
APP_PORT=8180
LOG_LEVEL=info
LOG_FORMAT=json

RATE_LIMIT_SEARCH_PER_MINUTE=100
RATE_LIMIT_UPLOAD_PER_MINUTE=30

WATCHDOG_TIMEOUT_SECONDS=300

SETTINGS_PROXY_SECRET=${SP_SECRET}
SETTINGS_CACHE_TTL_RAG_CONFIG=60
SETTINGS_CACHE_TTL_HUB_REGISTRY=300
SETTINGS_CACHE_TTL_APIKEY=60
SETTINGS_SUBSCRIBER_RECONNECT_SECONDS=5
EOF

chmod 600 api/.env

# Chỉ còn 2 giá trị BẮT BUỘC paste tay: OPENAI_API_KEY + GEMINI_API_KEY
nano api/.env       # tìm 2 dòng CHANGE-ME paste key thật

# Verify 3 password match (Hub_All/.env + api/.env POSTGRES_PASSWORD + 2 DSN)
grep -E '^(POSTGRES_PASSWORD|DATABASE_URL|COCOINDEX_DATABASE_URL)=' api/.env

# Verify 2 dòng PROD-CRITICAL (P12 mitigation Settings validator):
#   1. APP_ENV=production (Hub_All/.env compose override → container thấy production)
#   2. CORS_ALLOWED_ORIGINS=https://wiki.medinet.work (KHÔNG localhost — sẽ fail boot)
# Nếu lỡ `cp api/.env.example api/.env` thay vì dùng heredoc trên, 2 dòng này
# sẽ là localhost default + APP_ENV=dev → central lifespan crash ngay khi import
# middleware (config.py:318 `_no_lan_in_prod` reject localhost trong production).
grep -E '^(APP_ENV|CORS_ALLOWED_ORIGINS)=' api/.env
# Expected:
#   APP_ENV=production
#   CORS_ALLOWED_ORIGINS=https://wiki.medinet.work
```

---

## Step 8 — Sinh JWT keypair

```bash
cd api
make keys                              # target tên `keys` (KHÔNG `api-keys`) — sinh keys/{private,public}.pem
ls -la keys/                           # private.pem chmod 600 + public.pem chmod 644
cd ..

# QUAN TRỌNG: chown 1000:1000 — Dockerfile tạo apiuser uid=1000; file mount
# ro với owner root + chmod 600 → apiuser trong container DENIED đọc private key
# → lifespan log `jwt_manager_init_failed: Permission denied: '/keys/private.pem'`
# → /readyz trả jwt:not_ready. Sau chown, apiuser uid=1000 owner → đọc OK.
chown 1000:1000 api/keys/private.pem api/keys/public.pem
ls -la api/keys/                       # owner phải là 1000 (hoặc tên user host trùng uid)

# BACKUP api/keys/private.pem offline NGAY (mất file = invalidate toàn bộ refresh token)
scp api/keys/private.pem <user>@<local-machine>:~/backup/medinet-jwt-private.pem
```

---

## Step 9 — Tạo `mcp_service/.env`

```bash
cp mcp_service/.env.example mcp_service/.env
chmod 600 mcp_service/.env
nano mcp_service/.env
```

Điền:

```ini
MCP_API_BASE_URL=http://python-api-central:8080
MCP_OAUTH_ISSUER_URL=https://wiki.medinet.work/mcp
MCP_PATH_PREFIX=mcp
MCP_INTERNAL_TOKEN=<openssl rand -hex 32>
```

---

## Step 10 — Build frontend SPA

```bash
cd /opt/medinet/wiki/Hub_All/frontend
npm install
npm run build
ls dist/                # phải thấy index.html + assets/
cd ..
```

---

## Step 11 — Boot Postgres + Redis + chuẩn bị tooling psql/alembic

### 11.1 — Boot 2 service infra

```bash
cd /opt/medinet/wiki/Hub_All
docker compose up -d postgres redis
sleep 5
docker compose ps       # cả 2 phải healthy

# Verify pgvector
docker compose exec postgres psql -U medinet -d medinet_central \
  -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

### 11.2 — Cài Python deps vào `.venv` (cho alembic + asyncpg + sqlalchemy)

`make hub-init` ở Step 12 gọi `uv run alembic upgrade head` — cần `.venv` có sẵn deps. Lần đầu mất ~2-3 phút (uv tự download Python 3.12 nếu chưa có).

```bash
cd /opt/medinet/wiki/Hub_All/api
make install                 # = uv sync --extra dev
uv run alembic --version     # verify alembic chạy được
cd ..
```

### 11.3 — Migrate `medinet_central` (BẮT BUỘC trước Step 14)

> Step 12 `make hub-init` chỉ migrate per-hub DB (`medinet_hub_dmd` + `medinet_hub_tdt`), KHÔNG đụng `medinet_central`. Nếu skip step này, central lifespan boot sẽ fail ở `cocoindex.update_blocking()` với `UndefinedTableError: relation "documents" does not exist` → exit. Memory `project_alembic_upgrade_windows` carry forward — prefix `PYTHONIOENCODING=utf-8` để fix migration 0006 `print()` chữ Việt cp1252 fail.

```bash
cd /opt/medinet/wiki/Hub_All/api
PYTHONIOENCODING=utf-8 uv run alembic upgrade head    # DSN default từ api/.env DATABASE_URL → medinet_central
cd ..

# Verify 12 bảng tồn tại (includes documents — cocoindex SELECT target)
docker compose exec postgres psql -U medinet -d medinet_central -c "\dt"
# PHẢI thấy: users, hubs, documents, chunks, audit_logs, usage_events,
#            refresh_tokens, api_keys, user_hubs, mcp_oauth_clients,
#            settings, alembic_version
```

### 11.4 — Export 4 env var cho psql native (Step 12 + 14)

`hub-init.sh` + Step 14 dùng `psql` native (KHÔNG qua `docker compose exec`). Cần 4 env var connect tới postgres container.

```bash
export PGHOST=localhost
export PGPORT=5432
export PGUSER=medinet
export PGPASSWORD=$(grep '^POSTGRES_PASSWORD=' .env | cut -d= -f2-)

# Verify connect OK
psql -d medinet_central -c "SELECT current_database();"
```

> Lưu ý: 4 env var này chỉ tồn tại trong shell session hiện tại. Nếu logout/reopen SSH, phải export lại trước khi chạy `make hub-init` hoặc Step 14.

---

## Step 12 — Tạo DB cho 2 hub

```bash
make hub-init HUB=dmd
make hub-init HUB=tdt

docker compose exec postgres psql -U medinet -l
# Phải thấy: medinet_central, medinet_cocoindex, medinet_hub_dmd, medinet_hub_tdt
```

---

## Step 13 — Sinh `docker-compose.override.yml` cho 2 hub thật

```bash
make hub-add HUB=dmd PORT=8181
make hub-add HUB=tdt PORT=8182

docker compose config --quiet           # phải PASS (không error YAML)
```

> Base `docker-compose.yml` vẫn pin 3 service ghost `yte/duoc/hcns` — KHÔNG boot chúng ở Step 15 (chỉ chọn lọc service `python-api-dmd` + `python-api-tdt`).

---

## Step 14 — Boot central + seed 2 hub row → resolve UUID

```bash
# Boot central trước
docker compose up -d python-api-central
sleep 10
curl http://127.0.0.1:8180/healthz       # PASS

# Seed 2 hub row vào medinet_central.hubs
# Flag -T BẮT BUỘC khi dùng heredoc (stdin không phải TTY → docker compose mặc định
# allocate TTY sẽ reject: "cannot attach stdin to a TTY-enabled container")
docker compose exec -T postgres psql -U medinet -d medinet_central <<'SQL'
INSERT INTO hubs (slug, code, name, subdomain, description, status)
VALUES
  ('dmd', 'dmd', 'Đỗ Minh Đường', 'dmd', 'Hub tri thức Đỗ Minh Đường', 'active'),
  ('tdt', 'tdt', 'Thuốc Dân Tộc',  'tdt', 'Hub tri thức Thuốc Dân Tộc', 'active')
ON CONFLICT (slug) DO NOTHING;
SELECT id, slug, code, name FROM hubs;
SQL
# Schema thực tế (Phase 5 v2.0 reconcile): 4 NOT NULL fields = slug + code +
# name + subdomain (KHÔNG có hub_name/display_name). slug = code.lower()
# (mirror Phase 2 legacy NOT NULL UNIQUE). HubService.create dùng cùng pattern.

# Resolve UUID vào .env (column đúng = slug)
HUB_DMD_ID=$(docker compose exec -T postgres psql -U medinet -d medinet_central -tAc "SELECT id FROM hubs WHERE slug='dmd'")
HUB_TDT_ID=$(docker compose exec -T postgres psql -U medinet -d medinet_central -tAc "SELECT id FROM hubs WHERE slug='tdt'")
sed -i "s|^HUB_DMD_ID=.*|HUB_DMD_ID=${HUB_DMD_ID}|" .env
sed -i "s|^HUB_TDT_ID=.*|HUB_TDT_ID=${HUB_TDT_ID}|" .env

# Build CHECKSUM_HUB_DSNS_JSON cho central scheduler
# QUAN TRỌNG: sed value KHÔNG bao single quote — docker-compose `.env` parser
# KHÔNG strip quote → nếu wrap `'{"dmd":...}'`, container nhận literal có quote
# → json.loads() fail → validator raise → central crash. JSON raw đi thẳng OK.
PWD_ENC=$(grep '^POSTGRES_PASSWORD=' .env | cut -d= -f2-)
CHECKSUM_VALUE="{\"dmd\":\"postgresql://medinet:${PWD_ENC}@postgres:5432/medinet_hub_dmd\",\"tdt\":\"postgresql://medinet:${PWD_ENC}@postgres:5432/medinet_hub_tdt\"}"
sed -i "s|^CHECKSUM_HUB_DSNS_JSON=.*|CHECKSUM_HUB_DSNS_JSON=${CHECKSUM_VALUE}|" .env
#                                                          ^^^^^^^^^^^^^^^^^^ KHÔNG ' wrap

grep -E '^(HUB_.*_ID|CHECKSUM_HUB_DSNS_JSON)=' .env
```

---

## Step 15 — Boot 2 hub con + MCP + Caddy

```bash
# Restart central pickup CHECKSUM_HUB_DSNS_JSON
docker compose up -d --force-recreate python-api-central

# Boot 2 hub thật
docker compose up -d python-api-dmd python-api-tdt

# Boot MCP + Caddy
docker compose up -d mcp_service caddy

docker compose ps       # tất cả service healthy
```

---

## Step 16 — Verify Caddy auto-TLS Let's Encrypt

```bash
docker compose logs -f caddy
# Đợi dòng "certificate obtained successfully" cho wiki.medinet.work (~30s)
# Ctrl+C khi thấy

# Verify HTTPS
curl -I https://wiki.medinet.work/api/health        # 200 + strict-transport-security header
curl https://wiki.medinet.work/dmd/api/health       # 200
curl https://wiki.medinet.work/tdt/api/health       # 200
```

---

## Step 17 — Tạo super admin đầu tiên

```bash
# Flag -T BẮT BUỘC khi dùng heredoc (stdin không phải TTY)
docker compose exec -T python-api-central uv run python <<'PY'
import asyncio, asyncpg, os
from passlib.hash import argon2

async def main():
    pwd_hash = argon2.using(
        rounds=1, memory_cost=65536, parallelism=2,
        salt_size=16, digest_size=32
    ).hash("ChangeMe@123")
    dsn = os.environ["DATABASE_URL"].replace("+asyncpg", "")
    conn = await asyncpg.connect(dsn)
    await conn.execute("""
        INSERT INTO users (email, full_name, password_hash, role, status)
        VALUES ('admin@medinetgroup.vn', 'Super Admin', $1, 'admin', 'active')
        ON CONFLICT (email) DO NOTHING
    """, pwd_hash)
    await conn.close()
    print("Super admin: admin@medinetgroup.vn / ChangeMe@123")

asyncio.run(main())
PY
```

Vào `https://wiki.medinet.work/` → login `admin@medinetgroup.vn` / `ChangeMe@123` → **đổi password ngay** (Settings → Profile).

---

## Step 18 — Smoke E2E

```bash
cd /opt/medinet/wiki/Hub_All
export WIKI_URL=https://wiki.medinet.work
export ADMIN_EMAIL=admin@medinetgroup.vn
export ADMIN_PASSWORD=<password vừa đổi ở Step 17>

bash scripts/migrate/05-smoke-e2e.sh
# Expected: PASS dmd + tdt + cross-hub p95 < 1.5s
```

---

## Done — Stack live tại `https://wiki.medinet.work`

### Update code thường ngày

```bash
cd /opt/medinet/wiki && git pull && cd Hub_All
docker compose build python-api-central python-api-dmd python-api-tdt
docker compose up -d --force-recreate python-api-central python-api-dmd python-api-tdt

# Frontend nếu có FE change
cd frontend && npm install && npm run build && cd ..
docker compose exec caddy caddy reload --config /etc/caddy/Caddyfile
```

### Thêm hub mới

```bash
make hub-add HUB=marketing
docker compose exec postgres psql -U medinet -d medinet_central \
  -c "INSERT INTO hubs (slug, code, name, subdomain, status) VALUES ('marketing', 'marketing', 'Hub Marketing', 'marketing', 'active');"
HUB_MARKETING_ID=$(docker compose exec -T postgres psql -U medinet -d medinet_central -tAc \
  "SELECT id FROM hubs WHERE slug='marketing'")
echo "HUB_MARKETING_ID=${HUB_MARKETING_ID}" >> .env

docker compose up -d python-api-marketing
docker compose exec caddy caddy reload --config /etc/caddy/Caddyfile
curl https://wiki.medinet.work/marketing/api/health
```

### Backup daily Postgres

```bash
# Cron daily 2AM dump central + 2 hub DB
cat > /etc/cron.daily/medinet-backup <<'CRON'
#!/bin/bash
BACKUP_DIR=/opt/medinet/backup
mkdir -p $BACKUP_DIR
DATE=$(date +%Y-%m-%d)
cd /opt/medinet/wiki/Hub_All
for DB in medinet_central medinet_hub_dmd medinet_hub_tdt; do
  docker compose exec -T postgres pg_dump -U medinet -F c $DB \
    > $BACKUP_DIR/$DB-$DATE.dump
done
# Rotate giữ 30 ngày
find $BACKUP_DIR -name '*.dump' -mtime +30 -delete
CRON
chmod +x /etc/cron.daily/medinet-backup
```

---

*Quick setup cho v3.1 SHIPPED 2026-05-24. Chạy bằng user root VPS.*
*Cập nhật 2026-05-25 (fix 5 gap deploy thật trên VPS): CHECKSUM_HUB_DSNS_JSON bootstrap `{}` (Step 6) + verify CORS_ALLOWED_ORIGINS prod (Step 7) + Makefile target `keys` + chown 1000:1000 JWT keys (Step 8) + migrate medinet_central trước Step 14 (Step 11.3 mới) + sed bỏ single quote wrap CHECKSUM JSON (Step 14).*
