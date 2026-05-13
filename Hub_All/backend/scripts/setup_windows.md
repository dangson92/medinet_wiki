# Huong dan cai dat Medinet Wiki Backend tren Windows

## 1. Cai dat Go 1.22+

1. Tai tu: https://go.dev/dl/
2. Chon file `go1.22.x.windows-amd64.msi`
3. Cai dat, restart terminal
4. Kiem tra: `go version`

## 2. Cai dat PostgreSQL 16

1. Tai tu: https://www.postgresql.org/download/windows/
2. Chon **PostgreSQL 16** installer tu EDB
3. Cai dat voi cac thong so mac dinh:
   - Port: `5432`
   - Superuser password: ghi nho de dung cho buoc tiep
4. Sau khi cai xong, mo **pgAdmin** hoac dung `psql`:

```bash
# Mo Command Prompt hoac Git Bash
psql -U postgres

# Tao user
CREATE USER medinet WITH PASSWORD 'mat_khau_cua_ban';

# Tao database
CREATE DATABASE medinet_central OWNER medinet;

# Cap quyen
GRANT ALL PRIVILEGES ON DATABASE medinet_central TO medinet;

# Thoat
\q
```

Hoac chay: `make db-create` (can sua password trong Makefile truoc)

## 3. Cai dat Redis

### Cach 1: Memurai (Khuyen dung — Redis-compatible cho Windows)

1. Tai tu: https://www.memurai.com/get-memurai
2. Cai dat, service tu dong chay tren port `6379`
3. Kiem tra: `memurai-cli ping` → `PONG`

### Cach 2: Redis qua WSL2

```bash
# Trong WSL2 terminal
sudo apt update
sudo apt install redis-server
sudo service redis-server start
redis-cli ping  # PONG
```

## 4. Cai dat ChromaDB

Can Python 3.8+ da cai san.

```bash
pip install chromadb

# Chay ChromaDB server
chroma run --host localhost --port 8000
```

Kiem tra: truy cap http://localhost:8000/api/v1/heartbeat

**Luu y:** De ChromaDB chay ngam, mo mot terminal rieng hoac dung `start /B chroma run --host localhost --port 8000`

## 5. Cai dat OpenSSL (de tao JWT keys)

- Neu da cai Git for Windows: OpenSSL da co san trong Git Bash
- Neu chua: tai tu https://slproweb.com/products/Win32OpenSSL.html

## 6. Setup project

```bash
# Clone va vao thu muc backend
cd backend

# Cai Go dependencies
go mod tidy

# Tao JWT keypair (chay trong Git Bash)
bash scripts/generate_keys.sh

# Copy va chinh sua env
cp .env.example .env
# Sua .env: dien DB_PASSWORD, REDIS_PASSWORD, AES_KEY...

# Kiem tra services
make setup-check

# Chay server
make dev
```

## 7. Seed du lieu

```bash
# Dam bao PostgreSQL dang chay va database da tao
make seed
```

## 8. Kiem tra

```bash
# Health check
curl http://localhost:8080/health

# Login (sau khi seed)
curl -X POST http://localhost:8080/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@medinet.vn","password":"Admin@123"}'
```

## Ports su dung

| Service    | Port | Ghi chu                |
|------------|------|------------------------|
| Go API     | 8080 | Backend server         |
| PostgreSQL | 5432 | Database               |
| Redis      | 6379 | Cache / Queue          |
| ChromaDB   | 8000 | Vector database        |
