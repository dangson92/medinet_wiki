# VPS Deploy Guide — Medinet Wiki v3.0 Multi-Hub

> Hướng dẫn cài đặt **end-to-end trên VPS Linux từ đầu** cho stack Medinet Wiki v3.0 (multi-hub: central + 3 hub con yte/duoc/hcns + MCP + Caddy + frontend SPA). Tài liệu này khác [DEPLOY.md](DEPLOY.md) (M2 single-hub) — bao trùm DNS, firewall, OS setup, frontend build, multi-hub UUID resolve, Caddy auto-TLS.

**Milestone hiện tại:** v3.0 CLOSED 2026-05-23 · 38/38 plan · 30/30 REQ-ID · Stack Python ONLY (Go đã archive 2026-05-14).

---

## 1. Yêu cầu VPS

### 1.1 Phần cứng tối thiểu

| Resource | Dev/Staging | Production (4 hub) |
|----------|------------|---------------------|
| **vCPU** | 2 core | 4 core (cocoindex Rust + 4 FastAPI worker + Postgres) |
| **RAM** | 4 GB | **8 GB** (Postgres + Redis + 4 container Python + Caddy + MCP; thiếu RAM sẽ OOM khi embed batch lớn) |
| **Disk** | 20 GB SSD | **50 GB SSD** (`medinet_pgdata` ~10GB + `file_store` ~15GB + `.cocoindex/*` LMDB ~5GB + backup rotation 30 ngày ~15GB) |
| **Network** | 10 Mbps | 100 Mbps + IP public tĩnh |

### 1.2 Hệ điều hành khuyến nghị

- **Ubuntu 22.04 LTS** hoặc **Debian 12** (Docker official support tốt nhất).
- Kernel ≥ 5.10 (cgroups v2 cho Docker resource limit).
- Tránh CentOS 7 / RHEL 7 (EOL, Docker compose v2 không native).

### 1.3 Port phải mở ra Internet

| Port | Service | Bắt buộc | Ghi chú |
|------|---------|----------|---------|
| **22** | SSH | ✅ | Restrict IP allowlist trong UFW |
| **80** | Caddy HTTP | ✅ | ACME HTTP-01 challenge + redirect HTTPS |
| **443** | Caddy HTTPS | ✅ | Wiki + MCP service public traffic |
| 5432 | Postgres | ❌ | **CHỈ bind 127.0.0.1** — KHÔNG expose public |
| 6379 | Redis | ❌ | **CHỈ bind 127.0.0.1** — KHÔNG expose public |
| 8180-8183 | python-api-* | ❌ | Internal Docker network, KHÔNG expose |

### 1.4 Domain + DNS

- **1 record A bắt buộc** trỏ về IP VPS:
  - `wiki.medinet.vn` → IP VPS (frontend SPA + 4 hub API + MCP service qua Caddy)
- TTL khuyến nghị 300s (5 phút) để rollback DNS nhanh.
- **KHÔNG dùng wildcard** — Caddy ACME challenge HTTP-01 cần exact match.
- 2026-05-23: MCP service gộp về subpath `/mcp` cùng domain wiki (bỏ subdomain riêng `mcp.medinet.vn`).

### 1.5 Credentials cần chuẩn bị trước

- **OpenAI API key** tier paid (`sk-...`) — embedding + LLM answerer (~$0.20/eval run).
- **Gemini API key** — fallback hot-swap LiteLLM (D5).
- **SSH keypair** (Ed25519 khuyến nghị) để truy cập VPS — disable password login sau bước 2.

---

## 2. Chuẩn bị VPS

### 2.1 Hardening SSH cơ bản

```bash
# Đổi root pwd random + thêm user thường + sudo
adduser medinet
usermod -aG sudo medinet

# Copy SSH key tới user mới (chạy từ máy local)
ssh-copy-id medinet@<VPS_IP>

# Đăng nhập lại bằng medinet user
ssh medinet@<VPS_IP>

# Disable root SSH + password auth
sudo sed -i 's/^#*PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config
sudo sed -i 's/^#*PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
sudo systemctl restart sshd
```

### 2.2 Firewall UFW

```bash
sudo apt update && sudo apt install -y ufw
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp comment 'SSH'
sudo ufw allow 80/tcp comment 'Caddy ACME HTTP-01'
sudo ufw allow 443/tcp comment 'Caddy HTTPS'
sudo ufw enable
sudo ufw status verbose
```

### 2.3 Cài Docker Engine + Compose v2

```bash
# Cài Docker official (Ubuntu 22.04)
sudo apt update
sudo apt install -y ca-certificates curl gnupg lsb-release
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
  sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Thêm user medinet vào group docker (KHÔNG cần sudo cho docker command)
sudo usermod -aG docker medinet
newgrp docker

# Verify
docker --version           # Docker version 24.0+
docker compose version     # Docker Compose version v2.x
```

### 2.4 Cài tooling phụ

```bash
sudo apt install -y \
  git \
  make \
  postgresql-client-16 \
  jq \
  openssl \
  python3 \
  python3-pip \
  build-essential \
  nodejs npm    # cho frontend build (Node 20+ khuyến nghị qua nvm)

# Node 20 LTS qua nvm (KHUYẾN NGHỊ — apt nodejs có thể cũ)
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
source ~/.bashrc
nvm install 20 && nvm use 20
node --version    # v20.x
```

---

## 3. Clone repo + chuẩn bị secret

### 3.1 Clone repo

```bash
cd /opt
sudo mkdir -p medinet && sudo chown medinet:medinet medinet
cd medinet
git clone <REPO_URL> wiki
cd wiki/Hub_All
```

### 3.2 Sinh `.env` root compose

File `.env` ở `Hub_All/.env` (KHÔNG commit) chứa biến cho docker-compose interpolation:

```bash
cat > .env <<'EOF'
# === Production env (Hub_All/.env — KHÔNG commit) ===
APP_ENV=production
LOG_LEVEL=info

# Postgres password — random 32+ char
POSTGRES_PASSWORD=<PASTE_KẾT_QUẢ_openssl_rand_base64_32>

# Phase 6 SETTINGS-03 — shared secret 32 char min cho internal endpoint
SETTINGS_PROXY_SECRET=<PASTE_KẾT_QUẢ_openssl_rand_hex_32>

# Caddy public domain — 2026-05-23: 1 domain duy nhất cho wiki + MCP
WIKI_PUBLIC_DOMAIN=wiki.medinet.vn
# MCP OAuth issuer — path suffix /mcp KHỚP MCP_PATH_PREFIX=mcp ở mcp_service/.env
MCP_OAUTH_ISSUER_URL=https://wiki.medinet.vn/mcp

# Allowlist 3 hub mặc định v3.0 — append thêm khi `make hub-add`
HUBS_ALLOWLIST=yte,duoc,hcns
HUBS_ALLOWLIST_REGEX=yte|duoc|hcns

# Hub UUID — RESOLVE Ở BƯỚC 5 sau khi seed central.hubs. Tạm để trống.
HUB_YTE_ID=
HUB_DUOC_ID=
HUB_HCNS_ID=

# Phase 4 SYNC-04 — central checksum scheduler. Resolve sau bước 5.
CHECKSUM_HUB_DSNS_JSON=
EOF

chmod 600 .env

# Sinh 2 secret cần thiết
echo "POSTGRES_PASSWORD=$(openssl rand -base64 32)"
echo "SETTINGS_PROXY_SECRET=$(openssl rand -hex 32)"
# Paste 2 dòng output vào .env ở trên
```

### 3.3 Sinh `api/.env` cho 4 container FastAPI

```bash
cp api/.env.example api/.env
chmod 600 api/.env
```

Sửa `api/.env` — điền tối thiểu:

```ini
# Production-critical secrets
POSTGRES_PASSWORD=<MATCH với .env root>
OPENAI_API_KEY=sk-<real-paid-key>
GEMINI_API_KEY=<real-key>
AES_KEY=<PASTE python -c "import os,base64; print(base64.urlsafe_b64encode(os.urandom(32)).decode())">
SETTINGS_PROXY_SECRET=<MATCH với .env root>

# CORS prod chỉ HTTPS thật — _no_lan_in_prod validator reject localhost
CORS_ALLOWED_ORIGINS=https://wiki.medinet.vn

APP_ENV=production
RAG_EMBEDDING_MODEL=text-embedding-3-large    # prod đổi từ small → large
```

> **Quan trọng:** `HUB_NAME` / `DATABASE_URL` / `HUB_ID` / `CENTRAL_*` ở `api/.env` BỊ OVERRIDE bởi docker-compose `environment:` block per service. Phần `.env` chỉ dùng cho biến share (OpenAI key, AES_KEY, embedding config).

### 3.4 Sinh JWT keypair RS256

```bash
make api-keys
# Tạo Hub_All/api/keys/{private.pem, public.pem} chmod 600
ls -la api/keys/
```

> **Backup `api/keys/private.pem` offline ngay** — mất file = invalidate toàn bộ refresh token, force re-login toàn bộ user.

### 3.5 Sinh `mcp_service/.env`

```bash
cp mcp_service/.env.example mcp_service/.env
chmod 600 mcp_service/.env
```

Sửa `mcp_service/.env`:

```ini
MCP_API_BASE_URL=http://python-api-central:8080
MCP_OAUTH_ISSUER_URL=https://wiki.medinet.vn/mcp   # PHẢI HTTPS prod (P-MCP-6) — path /mcp khớp MCP_PATH_PREFIX
MCP_PATH_PREFIX=mcp                                # 2026-05-23 path-prefix mode (consolidate subdomain)
MCP_INTERNAL_TOKEN=<PASTE openssl rand -hex 32>
```

---

## 4. Build frontend SPA

Caddy file_server serve static từ `Hub_All/frontend/dist/`. Build 1 lần trên VPS (hoặc CI):

```bash
cd /opt/medinet/wiki/Hub_All/frontend
npm install
npm run build
ls dist/    # index.html + assets/

cd ..
```

> **1 build dùng chung 4 hub** (Phase 5 PROXY-02 — Vite `base='/'` + `BrowserRouter basename` runtime detect prefix). KHÔNG cần build matrix per-hub.

---

## 5. Boot stack bước-một (Postgres + Redis trước, resolve UUID, rồi 4 API)

Multi-hub có **dependency vòng**: hub con cần `HUB_ID` UUID khớp `medinet_central.hubs.id` → phải boot central trước, seed hub, lấy UUID, rồi mới boot hub con.

### 5.1 Boot infra layer (postgres + redis)

```bash
cd /opt/medinet/wiki/Hub_All
docker compose up -d postgres redis

# Wait healthy
docker compose ps
# postgres status = healthy
# redis status = healthy

# Verify pgvector extension installed
docker compose exec postgres psql -U medinet -d medinet_central \
  -c "CREATE EXTENSION IF NOT EXISTS vector; SELECT extname, extversion FROM pg_extension;"
```

### 5.2 Tạo DB cho 3 hub con (Phase 1 hub-init)

```bash
# hub-init: CREATE DB medinet_hub_<name> + ext vector + HNSW verify + alembic upgrade head
make hub-init HUB=yte
make hub-init HUB=duoc
make hub-init HUB=hcns

# Verify 5 DB exist
docker compose exec postgres psql -U medinet -l
# medinet_central, medinet_cocoindex, medinet_hub_yte, medinet_hub_duoc, medinet_hub_hcns
```

### 5.3 Boot central trước (cần để seed hubs table)

```bash
docker compose up -d python-api-central
sleep 10
docker compose logs python-api-central | tail -50

# Smoke
curl http://127.0.0.1:8180/healthz
curl http://127.0.0.1:8180/readyz
```

### 5.4 Seed `central.hubs` table + resolve UUID

```bash
# Insert 3 row hub vào medinet_central.hubs (nếu chưa có)
docker compose exec postgres psql -U medinet -d medinet_central <<'SQL'
INSERT INTO hubs (hub_name, display_name, description)
VALUES
  ('yte',  'Hub Y tế',  'Hub tri thức Y tế'),
  ('duoc', 'Hub Dược',  'Hub tri thức Dược'),
  ('hcns', 'Hub HCNS',  'Hub Hành chính Nhân sự')
ON CONFLICT (hub_name) DO NOTHING;

SELECT id, hub_name FROM hubs ORDER BY hub_name;
SQL

# Resolve UUID vào .env
HUB_YTE_ID=$(docker compose exec -T postgres psql -U medinet -d medinet_central -tAc "SELECT id FROM hubs WHERE hub_name='yte'")
HUB_DUOC_ID=$(docker compose exec -T postgres psql -U medinet -d medinet_central -tAc "SELECT id FROM hubs WHERE hub_name='duoc'")
HUB_HCNS_ID=$(docker compose exec -T postgres psql -U medinet -d medinet_central -tAc "SELECT id FROM hubs WHERE hub_name='hcns'")

# Patch .env (idempotent — replace dòng có sẵn)
sed -i "s|^HUB_YTE_ID=.*|HUB_YTE_ID=${HUB_YTE_ID}|" .env
sed -i "s|^HUB_DUOC_ID=.*|HUB_DUOC_ID=${HUB_DUOC_ID}|" .env
sed -i "s|^HUB_HCNS_ID=.*|HUB_HCNS_ID=${HUB_HCNS_ID}|" .env

# Build CHECKSUM_HUB_DSNS_JSON cho central (Phase 4 SYNC-04)
PWD_ENC=$(grep '^POSTGRES_PASSWORD=' .env | cut -d= -f2-)
cat <<EOF | tr -d '\n' > /tmp/checksum.json
{"yte":"postgresql://medinet:${PWD_ENC}@postgres:5432/medinet_hub_yte","duoc":"postgresql://medinet:${PWD_ENC}@postgres:5432/medinet_hub_duoc","hcns":"postgresql://medinet:${PWD_ENC}@postgres:5432/medinet_hub_hcns"}
EOF
CHECKSUM_VALUE=$(cat /tmp/checksum.json)
sed -i "s|^CHECKSUM_HUB_DSNS_JSON=.*|CHECKSUM_HUB_DSNS_JSON='${CHECKSUM_VALUE}'|" .env
rm /tmp/checksum.json

grep -E '^(HUB_.*_ID|CHECKSUM_HUB_DSNS_JSON)=' .env
```

### 5.5 Restart central + boot 3 hub con + MCP + Caddy

```bash
# Restart central để pickup CHECKSUM_HUB_DSNS_JSON mới
docker compose up -d --force-recreate python-api-central

# Boot 3 hub con (cần HUB_*_ID đã resolve ở 5.4)
docker compose up -d python-api-yte python-api-duoc python-api-hcns

# Boot MCP + Caddy
docker compose up -d mcp_service caddy

# Verify tất cả service healthy
docker compose ps
```

### 5.6 Smoke 4 hub local

```bash
# 4 healthz qua port host (bypass Caddy)
curl http://127.0.0.1:8180/healthz   # central
curl http://127.0.0.1:8181/healthz   # yte
curl http://127.0.0.1:8182/healthz   # duoc
curl http://127.0.0.1:8183/healthz   # hcns

# Smoke qua Caddy (yêu cầu DNS đã trỏ về VPS — xem bước 6)
curl -k https://wiki.medinet.vn/api/health        # central
curl -k https://wiki.medinet.vn/yte/api/health    # yte qua subpath
```

---

## 6. DNS + Caddy auto-TLS

### 6.1 Trỏ DNS

Ở provider DNS (Cloudflare/DNSPod/Mắt Bão...):

```
A   wiki.medinet.vn   →  <VPS_IP>   TTL 300
```

> 2026-05-23: chỉ cần 1 record — MCP service serve qua subpath `/mcp` cùng domain wiki (bỏ `mcp.medinet.vn`).

Verify từ VPS:

```bash
dig +short wiki.medinet.vn   # phải trả đúng VPS_IP
```

### 6.2 Caddy auto-xin cert Let's Encrypt

Caddy đã được boot ở bước 5.5. Lần đầu start sẽ auto challenge ACME HTTP-01 qua port 80:

```bash
docker compose logs -f caddy
# Tìm dòng "certificate obtained successfully" cho wiki.medinet.vn

# Test HTTPS
curl https://wiki.medinet.vn/api/health         # 200 envelope D6 central API
curl https://wiki.medinet.vn/.well-known/oauth-authorization-server/mcp   # MCP OAuth metadata (path-prefix mode)
curl https://wiki.medinet.vn/mcp                                          # MCP Streamable HTTP root
```

> **Nếu cert FAIL:** kiểm tra (1) port 80 mở ra Internet (UFW), (2) DNS đã propagate đúng IP, (3) Caddy log không bị rate-limit Let's Encrypt (5 cert/tuần/domain).

---

## 7. Smoke E2E v3.0 (Plan 07-05)

```bash
cd /opt/medinet/wiki/Hub_All

# Set env cho smoke script (tùy chỉnh theo deploy)
export WIKI_URL=https://wiki.medinet.vn
export ADMIN_EMAIL=admin@medinet.vn
export ADMIN_PASSWORD=<initial-admin-pwd>

# Chạy automated smoke 3 hub × 7-step golden path
bash scripts/migrate/05-smoke-e2e.sh

# Output expected:
# [PASS] yte:  login + upload + poll + search + cross-hub + ask + citation
# [PASS] duoc: ...
# [PASS] hcns: ...
# Prometheus assertion: cross_hub_search_latency p95 < 1.5s ✓
```

> Smoke script này là **acceptance bắt buộc** Phase 7 MIGRATE-05. Nếu FAIL → kiểm tra log container, verify HUB_*_ID khớp, verify JWT keypair load đúng, verify OpenAI API key có dư quota.

---

## 8. Backup tự động (HARD-04 daily cron)

### 8.1 Script backup

```bash
sudo mkdir -p /var/backups/medinet
sudo chown medinet:medinet /var/backups/medinet

cat > /opt/medinet/wiki/Hub_All/scripts/backup-daily.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

BACKUP_DIR=/var/backups/medinet
DATE=$(date +%F)
ROOT=/opt/medinet/wiki/Hub_All
cd "$ROOT"

# 1. Postgres — TẤT CẢ DB (central + 3 hub con + cocoindex)
for DB in medinet_central medinet_cocoindex medinet_hub_yte medinet_hub_duoc medinet_hub_hcns; do
  docker compose exec -T postgres pg_dump -U medinet "$DB" \
    | gzip > "$BACKUP_DIR/${DB}_${DATE}.sql.gz"
done

# 2. file_store (raw upload)
tar czf "$BACKUP_DIR/file_store_${DATE}.tar.gz" -C "$ROOT" file_store/

# 3. CocoIndex LMDB fingerprint (4 volume)
for HUB in central yte duoc hcns; do
  docker run --rm -v medinet-wiki_medinet_cocoindex_${HUB}:/data:ro \
    -v "$BACKUP_DIR:/backup" alpine \
    tar czf "/backup/cocoindex_${HUB}_${DATE}.tar.gz" -C /data .
done

# 4. OAuth state SQLite (MCP Phase 8.3)
docker run --rm -v medinet-wiki_medinet_mcp_oauth_state:/data:ro \
  -v "$BACKUP_DIR:/backup" alpine \
  tar czf "/backup/mcp_oauth_state_${DATE}.tar.gz" -C /data .

# 5. JWT keypair + .env (offline-only, sensitive)
tar czf "$BACKUP_DIR/secrets_${DATE}.tar.gz" \
  api/keys/ .env api/.env mcp_service/.env

# 6. Rotation 30 ngày
find "$BACKUP_DIR" -name "*.gz" -mtime +30 -delete

echo "[$(date -Iseconds)] Backup done → $BACKUP_DIR"
EOF

chmod +x /opt/medinet/wiki/Hub_All/scripts/backup-daily.sh
```

### 8.2 Cron daily 02:00

```bash
crontab -e
# Append dòng:
0 2 * * * /opt/medinet/wiki/Hub_All/scripts/backup-daily.sh >> /var/log/medinet-backup.log 2>&1
```

### 8.3 Off-site backup (KHUYẾN NGHỊ)

Sync `/var/backups/medinet/` lên S3 / Backblaze B2 / rsync.net hàng tuần — KHÔNG lưu chỉ trên VPS (mất disk = mất hết).

```bash
# Ví dụ rclone tới Backblaze B2
rclone sync /var/backups/medinet b2:medinet-backup/wiki/ --transfers 4
```

---

## 9. Vận hành thường ngày

### 9.1 Theo dõi log

```bash
cd /opt/medinet/wiki/Hub_All

# Live tail 1 service
docker compose logs -f python-api-central
docker compose logs -f caddy
docker compose logs -f mcp_service

# Tất cả service
docker compose logs -f --tail 100
```

### 9.2 Restart / Update code

```bash
# Pull code mới
cd /opt/medinet/wiki && git pull
cd Hub_All

# Rebuild + restart chỉ container Python
docker compose build python-api-central python-api-yte python-api-duoc python-api-hcns
docker compose up -d --force-recreate python-api-central python-api-yte python-api-duoc python-api-hcns

# Rebuild frontend nếu có code FE
cd frontend && npm install && npm run build && cd ..

# Caddy reload zero-downtime nếu sửa Caddyfile
docker compose exec caddy caddy reload --config /etc/caddy/Caddyfile
```

### 9.3 Alembic migration mới

```bash
# Migration central
docker compose exec python-api-central alembic upgrade head

# Migration mỗi hub con
for HUB in yte duoc hcns; do
  docker compose exec python-api-${HUB} alembic upgrade head
done
```

### 9.4 Thêm hub mới (FACTOR-04)

```bash
cd /opt/medinet/wiki/Hub_All

# 1. hub-add tự động: hub-init DB + sed compose override + Caddy regex
make hub-add HUB=marketing

# 2. Seed row vào central.hubs + resolve UUID + patch .env
docker compose exec postgres psql -U medinet -d medinet_central \
  -c "INSERT INTO hubs (hub_name, display_name) VALUES ('marketing', 'Hub Marketing');"
HUB_MARKETING_ID=$(docker compose exec -T postgres psql -U medinet -d medinet_central -tAc \
  "SELECT id FROM hubs WHERE hub_name='marketing'")
echo "HUB_MARKETING_ID=${HUB_MARKETING_ID}" >> .env

# 3. Boot hub mới + reload Caddy
docker compose up -d python-api-marketing
docker compose exec caddy caddy reload --config /etc/caddy/Caddyfile

# 4. Verify
curl https://wiki.medinet.vn/marketing/api/health
```

### 9.5 Restore từ backup (disaster recovery)

```bash
RESTORE_DATE=2026-05-20

cd /opt/medinet/wiki/Hub_All
docker compose down

# Restore Postgres
for DB in medinet_central medinet_cocoindex medinet_hub_yte medinet_hub_duoc medinet_hub_hcns; do
  docker compose up -d postgres
  sleep 5
  docker compose exec -T postgres psql -U medinet -c "DROP DATABASE IF EXISTS ${DB}; CREATE DATABASE ${DB};"
  gunzip -c /var/backups/medinet/${DB}_${RESTORE_DATE}.sql.gz \
    | docker compose exec -T postgres psql -U medinet -d ${DB}
done

# Restore file_store
tar xzf /var/backups/medinet/file_store_${RESTORE_DATE}.tar.gz -C ./

# Restore secrets
tar xzf /var/backups/medinet/secrets_${RESTORE_DATE}.tar.gz

# Boot lại stack
docker compose up -d
bash scripts/migrate/05-smoke-e2e.sh
```

---

## 10. Security checklist production

| # | Item | Cách verify |
|---|------|-------------|
| 1 | UFW chỉ allow 22/80/443 | `sudo ufw status verbose` |
| 2 | SSH password auth disabled | `grep PasswordAuthentication /etc/ssh/sshd_config` |
| 3 | Root SSH disabled | `grep PermitRootLogin /etc/ssh/sshd_config` |
| 4 | Postgres KHÔNG expose public | `ss -tlnp | grep 5432` (chỉ 127.0.0.1 hoặc docker bridge) |
| 5 | Redis KHÔNG expose public | `ss -tlnp | grep 6379` |
| 6 | `.env` + `api/.env` chmod 600 | `ls -la .env api/.env` |
| 7 | `api/keys/private.pem` chmod 600 + backup offline | `ls -la api/keys/` |
| 8 | `POSTGRES_PASSWORD` ≥ 32 char random | `openssl rand -base64 32` |
| 9 | `SETTINGS_PROXY_SECRET` ≥ 32 char hex | `openssl rand -hex 32` |
| 10 | `AES_KEY` 32-byte base64 backup offline | python urandom 32 |
| 11 | `CORS_ALLOWED_ORIGINS` prod chỉ HTTPS thật | `grep CORS api/.env` (KHÔNG có localhost) |
| 12 | Caddy TLS cert valid Let's Encrypt | `curl -I https://wiki.medinet.vn` (header `strict-transport-security`) |
| 13 | MCP issuer HTTPS thật (path-prefix) | `echo $MCP_OAUTH_ISSUER_URL` (`https://wiki.medinet.vn/mcp`) |
| 14 | Backup cron chạy daily 02:00 | `tail /var/log/medinet-backup.log` |
| 15 | Off-site backup sync weekly | rclone sync log |
| 16 | Smoke 05-smoke-e2e.sh PASS | sau mỗi deploy code |

---

## 11. Troubleshooting

### 11.1 Container boot fail-loud

| Lỗi | Nguyên nhân | Fix |
|-----|-------------|-----|
| `SETTINGS_PROXY_SECRET env var phai set min 32 char` | `.env` chưa có hoặc < 32 char | `openssl rand -hex 32` → paste vào `.env` |
| `HUB_YTE_ID env var phai set khop central.hubs.id UUID` | Chưa resolve UUID bước 5.4 | Chạy lại bước 5.4 |
| `JWKS_UNAVAILABLE 503` ở hub con | central chưa boot xong / `api/keys/public.pem` missing | Boot central trước, verify `make api-keys` đã chạy |
| `Settings._enforce_hub_dsn_match` FAIL | `HUB_NAME` không khớp DB suffix trong DSN | Verify docker-compose `environment:` đúng |
| pgvector `CREATE EXTENSION vector` FAIL | Dùng nhầm `postgres:16-alpine` thay vì `pgvector/pgvector:pg16` | `docker compose down -v && docker compose up -d postgres` (sẽ mất data — chỉ làm khi fresh deploy) |

### 11.2 Caddy ACME cert fail

```bash
# Check log
docker compose logs caddy | grep -i "error\|challenge"

# Lý do phổ biến:
# 1. Port 80 chưa mở: sudo ufw status
# 2. DNS chưa propagate: dig +short wiki.medinet.vn
# 3. Rate-limit Let's Encrypt: chờ 1h hoặc dùng staging endpoint
# 4. Cloudflare proxy enabled (orange cloud): tắt proxy → DNS-only (gray cloud)
```

### 11.3 Smoke E2E FAIL

```bash
# Verbose debug
bash -x scripts/migrate/05-smoke-e2e.sh 2>&1 | tee /tmp/smoke.log

# Check Prometheus metric
curl https://wiki.medinet.vn/api/metrics | grep -E "cross_hub_search|sync_lag"

# Check sync outbox pending
docker compose exec postgres psql -U medinet -d medinet_hub_yte \
  -c "SELECT status, COUNT(*) FROM sync_outbox GROUP BY status;"
```

### 11.4 Out-of-memory (OOM)

VPS 4GB có thể OOM khi embed batch DOCX lớn:

```bash
# Monitor RAM
free -h
docker stats --no-stream

# Fix: thêm swap 4GB
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

# Long-term: upgrade VPS lên 8GB
```

---

## 12. Reference

- [DEPLOY.md](DEPLOY.md) — Generic stack deploy guide M2 (single-hub).
- [CLAUDE.md](CLAUDE.md) — Tổng quan v3.0 architecture + 7 phase pattern.
- `scripts/migrate/` — 5 bash script Phase 7 MIGRATE-01..05.
- `api/scripts/hub-init.sh` + `api/scripts/hub-add.sh` — Dynamic hub registration FACTOR-04.
- `.planning/phases/0{1..7}-*/` — Implementation chi tiết 7 phase v3.0.

---

*VPS Deploy guide v3.0 — cập nhật 2026-05-23 (Phase 7 closeout). Bao trùm OS hardening, DNS, Caddy auto-TLS, multi-hub UUID resolve, frontend SPA build, backup automation, security checklist 16 item, troubleshooting 4 nhóm lỗi phổ biến.*
