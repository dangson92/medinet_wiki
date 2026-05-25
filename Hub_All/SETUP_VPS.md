# Setup VPS Docker — Medinet Wiki v3.1 (Step by Step, ROOT user)

> Deploy nhanh lên VPS Linux (Ubuntu 22.04 / Debian 12) bằng Docker, **chạy trực tiếp bằng user `root`** (không tạo user thường). 2 hub thật: `dmd` (Đỗ Minh Đường) + `tdt` (Thuốc Dân Tộc).
>
> Yêu cầu VPS: **4 vCPU · 8 GB RAM · 50 GB SSD · IP public tĩnh**.
>
> Cần chuẩn bị trước: SSH access root, domain `wiki.medinet.vn` đã trỏ A record về IP VPS, OpenAI API key.

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

docker compose version     # verify v2.x
```

---

## Step 3 — Cài tooling phụ

```bash
apt install -y git make jq openssl postgresql-client-16 build-essential python3 python3-pip

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
PG_PWD=$(openssl rand -base64 32)
SP_SECRET=$(openssl rand -hex 32)
AES=$(python3 -c "import os,base64; print(base64.urlsafe_b64encode(os.urandom(32)).decode())")

echo "POSTGRES_PASSWORD=${PG_PWD}"
echo "SETTINGS_PROXY_SECRET=${SP_SECRET}"
echo "AES_KEY=${AES}"
# COPY 3 dòng — dùng ở Step 6 + 7
```

---

## Step 6 — Tạo `Hub_All/.env`

```bash
cat > .env <<EOF
APP_ENV=production
LOG_LEVEL=info

POSTGRES_PASSWORD=${PG_PWD}
SETTINGS_PROXY_SECRET=${SP_SECRET}

WIKI_PUBLIC_DOMAIN=wiki.medinet.vn
MCP_OAUTH_ISSUER_URL=https://wiki.medinet.vn/mcp

HUBS_ALLOWLIST=dmd,tdt
HUBS_ALLOWLIST_REGEX=dmd|tdt
HUB_DMD_ID=
HUB_TDT_ID=
CHECKSUM_HUB_DSNS_JSON=

SETTINGS_CACHE_TTL_RAG_CONFIG=60
SETTINGS_CACHE_TTL_HUB_REGISTRY=300
SETTINGS_CACHE_TTL_APIKEY=60
SETTINGS_SUBSCRIBER_RECONNECT_SECONDS=5
EOF

chmod 600 .env
```

---

## Step 7 — Tạo `api/.env`

```bash
cp api/.env.example api/.env
chmod 600 api/.env
nano api/.env       # sửa các giá trị dưới
```

Điền tối thiểu:

```ini
POSTGRES_PASSWORD=<PG_PWD ở Step 5>
OPENAI_API_KEY=sk-<paid-key>
GEMINI_API_KEY=<fallback-key>
AES_KEY=<AES ở Step 5>
SETTINGS_PROXY_SECRET=<SP_SECRET ở Step 5>
CORS_ALLOWED_ORIGINS=https://wiki.medinet.vn
APP_ENV=production
RAG_EMBEDDING_MODEL=text-embedding-3-large
```

---

## Step 8 — Sinh JWT keypair

```bash
make api-keys                          # tạo api/keys/{private,public}.pem chmod 600
ls -la api/keys/

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
MCP_OAUTH_ISSUER_URL=https://wiki.medinet.vn/mcp
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

## Step 11 — Boot Postgres + Redis

```bash
cd /opt/medinet/wiki/Hub_All
docker compose up -d postgres redis
sleep 5
docker compose ps       # cả 2 phải healthy

# Verify pgvector
docker compose exec postgres psql -U medinet -d medinet_central \
  -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

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
docker compose exec postgres psql -U medinet -d medinet_central <<'SQL'
INSERT INTO hubs (hub_name, display_name, description)
VALUES
  ('dmd', 'Đỗ Minh Đường', 'Hub tri thức Đỗ Minh Đường'),
  ('tdt', 'Thuốc Dân Tộc',  'Hub tri thức Thuốc Dân Tộc')
ON CONFLICT (hub_name) DO NOTHING;
SELECT id, hub_name FROM hubs;
SQL

# Resolve UUID vào .env
HUB_DMD_ID=$(docker compose exec -T postgres psql -U medinet -d medinet_central -tAc "SELECT id FROM hubs WHERE hub_name='dmd'")
HUB_TDT_ID=$(docker compose exec -T postgres psql -U medinet -d medinet_central -tAc "SELECT id FROM hubs WHERE hub_name='tdt'")
sed -i "s|^HUB_DMD_ID=.*|HUB_DMD_ID=${HUB_DMD_ID}|" .env
sed -i "s|^HUB_TDT_ID=.*|HUB_TDT_ID=${HUB_TDT_ID}|" .env

# Build CHECKSUM_HUB_DSNS_JSON cho central scheduler
PWD_ENC=$(grep '^POSTGRES_PASSWORD=' .env | cut -d= -f2-)
CHECKSUM_VALUE="{\"dmd\":\"postgresql://medinet:${PWD_ENC}@postgres:5432/medinet_hub_dmd\",\"tdt\":\"postgresql://medinet:${PWD_ENC}@postgres:5432/medinet_hub_tdt\"}"
sed -i "s|^CHECKSUM_HUB_DSNS_JSON=.*|CHECKSUM_HUB_DSNS_JSON='${CHECKSUM_VALUE}'|" .env

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
# Đợi dòng "certificate obtained successfully" cho wiki.medinet.vn (~30s)
# Ctrl+C khi thấy

# Verify HTTPS
curl -I https://wiki.medinet.vn/api/health        # 200 + strict-transport-security header
curl https://wiki.medinet.vn/dmd/api/health       # 200
curl https://wiki.medinet.vn/tdt/api/health       # 200
```

---

## Step 17 — Tạo super admin đầu tiên

```bash
docker compose exec python-api-central uv run python <<'PY'
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
        VALUES ('admin@medinet.vn', 'Super Admin', $1, 'admin', 'active')
        ON CONFLICT (email) DO NOTHING
    """, pwd_hash)
    await conn.close()
    print("Super admin: admin@medinet.vn / ChangeMe@123")

asyncio.run(main())
PY
```

Vào `https://wiki.medinet.vn/` → login `admin@medinet.vn` / `ChangeMe@123` → **đổi password ngay** (Settings → Profile).

---

## Step 18 — Smoke E2E

```bash
cd /opt/medinet/wiki/Hub_All
export WIKI_URL=https://wiki.medinet.vn
export ADMIN_EMAIL=admin@medinet.vn
export ADMIN_PASSWORD=<password vừa đổi ở Step 17>

bash scripts/migrate/05-smoke-e2e.sh
# Expected: PASS dmd + tdt + cross-hub p95 < 1.5s
```

---

## Done — Stack live tại `https://wiki.medinet.vn`

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
  -c "INSERT INTO hubs (hub_name, display_name) VALUES ('marketing', 'Hub Marketing');"
HUB_MARKETING_ID=$(docker compose exec -T postgres psql -U medinet -d medinet_central -tAc \
  "SELECT id FROM hubs WHERE hub_name='marketing'")
echo "HUB_MARKETING_ID=${HUB_MARKETING_ID}" >> .env

docker compose up -d python-api-marketing
docker compose exec caddy caddy reload --config /etc/caddy/Caddyfile
curl https://wiki.medinet.vn/marketing/api/health
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
