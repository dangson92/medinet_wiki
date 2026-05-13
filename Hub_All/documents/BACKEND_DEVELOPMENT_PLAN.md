# MEDINET WIKI — BACKEND DEVELOPMENT PLAN

**Version:** 1.1
**Date:** 2026-04-07 (updated)
**Architecture:** Vector-First — RAG Pipeline & Semantic Search as Core Priority
**Tech Stack:** Go 1.22+ · PostgreSQL 16 · ChromaDB · Redis 7 · JWT RS256

---

## Mục lục

- [1. Tổng Quan Kiến Trúc](#1-tổng-quan-kiến-trúc)
- [2. Tech Stack Chi Tiết](#2-tech-stack-chi-tiết)
- [3. Project Structure](#3-project-structure)
- [4. Infrastructure (Docker Compose)](#4-infrastructure-docker-compose)
- [5. PHASE 1 — Minimal Foundation](#5-phase-1--minimal-foundation)
- [6. PHASE 2 — RAG Pipeline & Vector Hóa Dữ Liệu](#6-phase-2--rag-pipeline--vector-hóa-dữ-liệu)
- [7. PHASE 3 — Semantic Search & Cross-Hub Search](#7-phase-3--semantic-search--cross-hub-search)
- [8. PHASE 4 — Wiki Pages & Sync Workflow](#8-phase-4--wiki-pages--sync-workflow)
- [9. PHASE 5 — User Management, Audit & API Keys](#9-phase-5--user-management-audit--api-keys)
- [10. PHASE 6 — MCP Server & Production Hardening](#10-phase-6--mcp-server--production-hardening)
- [11. Tổng Kết & Roadmap](#11-tổng-kết--roadmap)
- [12. Phụ Lục — Bảo Mật & Hiệu Năng](#12-phụ-lục--bảo-mật--hiệu-năng)

---

## 1. Tổng Quan Kiến Trúc

### 1.1 Triết Lý Thiết Kế

```
Kế hoạch truyền thống:  Auth → Hub → User → Sync → Wiki → RAG → MCP
                                                              ▲ RAG ở cuối

Kế hoạch Vector-First:  Foundation tối thiểu → RAG Pipeline → Search → phần còn lại
                                                 ▲ RAG ngay sau nền tảng
```

**Lý do ưu tiên Vector/RAG:**

- Giá trị cốt lõi của Medinet Wiki là semantic search — giảm >= 40% thời gian tìm kiếm (PRD 1.2)
- Validate sớm chất lượng embedding tiếng Việt (đặc biệt tài liệu y khoa)
- Phát hiện sớm bottleneck hiệu năng (chunking, embedding latency, ChromaDB query speed)
- Demo giá trị AI cho stakeholder ngay từ đầu
- Các module khác (Sync, MCP, Wiki) đều consume RAG — xây trước thì integrate sau nhanh hơn

### 1.2 Thuật Ngữ FE ↔ BE

| Frontend (UI tiếng Việt) | Backend (API / DB) | Ghi chú |
|---|---|---|
| Danh sách tri thức | `GET /api/documents` | FE dùng "tri thức" thay "tài liệu" |
| Hàng đợi Sync | `GET /api/sync/batches` | Hiển thị file type badges + dung lượng |
| Nạp tri thức mới | `POST /api/documents/upload` | **Ẩn ở Hub Tổng** (IS_HUB_TONG flag) |
| Dark mode toggle | Client-side localStorage | Key: `medinet-theme`, detect OS preference |

### 1.3 Kiến Trúc Hệ Thống

```
                     ┌──────────────────────────────────────┐
                     │          Nginx (*.medinet.vn)         │
                     │    SSL Wildcard + Subdomain Routing   │
                     └──────────────┬───────────────────────┘
                                    │
               ┌────────────────────┼────────────────────┐
               ▼                    ▼                    ▼
      wiki.medinet.vn      tamdao.medinet.vn      dmd.medinet.vn
      (Hub Tổng SPA)       (Hub Tâm Đạo SPA)     (Hub DMD SPA)
               │                    │                    │
               └────────────────────┼────────────────────┘
                                    ▼
                     ┌───────────────────────┐
                     │   Hub Tổng Go API     │
                     │     (port 8080)       │
                     │  ┌─────────────────┐  │
                     │  │ Middleware Chain │  │
                     │  │ CORS → Rate     │  │
                     │  │ → JWT → RBAC    │  │
                     │  ├─────────────────┤  │
                     │  │ Handler Layer   │  │
                     │  ├─────────────────┤  │
                     │  │ Service Layer   │  │
                     │  ├─────────────────┤  │
                     │  │ Repository Layer│  │
                     │  └──┬───┬───┬──┬──┘  │
                     └─────┼───┼───┼──┼─────┘
                           │   │   │  │
              ┌────────────┘   │   │  └────────────┐
              ▼                ▼   ▼               ▼
     ┌──────────────┐ ┌────────┐ ┌────────┐ ┌──────────────┐
     │ Central DB   │ │Hub DBs │ │ Redis  │ │   ChromaDB   │
     │ (PostgreSQL) │ │(per-Hub│ │ Cache  │ │ (per-Hub     │
     │ users, hubs, │ │ pages, │ │ Queue  │ │  collection) │
     │ audit, sync, │ │ cats,  │ │ Session│ │              │
     │ documents,   │ │versions│ │        │ │              │
     │ api_keys     │ │)       │ │        │ │              │
     └──────────────┘ └────────┘ └────────┘ └──────────────┘
```

### 1.4 Dependency Graph Giữa Các Phase

```
  Phase 1: Minimal Foundation ───┐
  (Config, DB, Auth cơ bản)      │
                                 ▼
  Phase 2: RAG Pipeline ─────────┼──► Phase 3: Search & Query ──┐
  (Ingestion, Embed, ChromaDB)   │    (Single + Cross-hub)      │
                                 │                               │
                                 ├──► Phase 4: Wiki + Sync       │
                                 │    (Pages CRUD, Versions)     │
                                 │                               │
                                 ├──► Phase 5: Quản trị          │
                                 │    (Users, Audit, API Keys)   │
                                 │                               │
                                 └──► Phase 6: MCP + Production ◄┘
                                      (AI Agent, Ops, Docker)
```

### 1.5 Luồng Request Theo Subdomain

```
wiki.medinet.vn    → Nginx → Hub Tổng React SPA → Hub Tổng Go API
                     Admin dashboard, cross-hub search, user management, MCP config

tamdao.medinet.vn  → Nginx → Hub Tâm Đạo React SPA → Hub Tổng Go API (JWT hub_id=tamdao)
                     Login riêng, chỉ thấy nội dung Tâm Đạo

dmd.medinet.vn     → Nginx → Hub DMD React SPA → Hub Tổng Go API (JWT hub_id=dmd)
                     Login riêng, chỉ thấy nội dung Đỗ Minh Đường

hcns.medinet.vn    → Nginx → Hub HCNS React SPA → Hub Tổng Go API (JWT hub_id=hcns)
                     Login riêng, chỉ thấy nội dung HCNS

AI Agent / MCP     → wiki.medinet.vn/mcp → Hub Tổng Go API (API key auth)
                     Không qua user session, dùng API key riêng
```

---

## 2. Tech Stack Chi Tiết

| Layer | Technology | Lý Do Chọn |
|-------|-----------|-------------|
| **Language** | Go 1.22+ | Performance cao, goroutine cho fan-out search, stateless dễ scale |
| **API Framework** | Gin hoặc Chi | Lightweight, high-performance, middleware chain rõ ràng |
| **Central DB** | PostgreSQL 16 | ACID, full-text search (GIN), JSONB, table partitioning |
| **Hub DB** | PostgreSQL 16 (per-Hub) | Data isolation hoàn toàn giữa các Hub |
| **Vector DB** | ChromaDB 0.5+ | Simple, Python/Go client, per-collection isolation |
| **Cache / Queue** | Redis 7 | Session store, search cache, job queue, rate limiting |
| **Auth** | JWT RS256 | Asymmetric key per Hub, stateless verification |
| **Password** | Argon2id | Chống GPU attack, memory-hard |
| **ORM / Query** | sqlc | Type-safe generated Go code từ SQL |
| **Migration** | golang-migrate | Version-controlled DB schema |
| **Embedding** | OpenAI text-embedding-3-small (default) | 1536 dims, multilingual tốt, giá rẻ |
| **File Extract** | pdftotext, excelize, unioffice, goquery, encoding/csv | PDF, XLSX, DOCX, HTML, CSV extraction; JPG/PNG via OCR (tesseract) |
| **Container** | Docker + Docker Compose | Dev environment nhất quán |
| **Monitoring** | Prometheus + Grafana (Phase 6) | Metrics, alerting |
| **Logging** | slog (Go stdlib) | Structured JSON logs |

---

## 3. Project Structure

```
backend/
├── cmd/
│   └── server/
│       └── main.go                     # Entry point — init config, DB, router, start server
│
├── internal/
│   ├── config/
│   │   └── config.go                   # Load env/yaml, validate, expose Config struct
│   │
│   ├── database/
│   │   ├── postgres.go                 # Central DB connection pool
│   │   ├── hubpool.go                  # Dynamic per-Hub DB pool manager
│   │   └── migrations/
│   │       ├── 001_bootstrap.up.sql    # Phase 1: hubs, users, user_hub_roles, api_keys
│   │       ├── 001_bootstrap.down.sql
│   │       ├── 002_documents.up.sql    # Phase 2: documents, document_chunks
│   │       ├── 002_documents.down.sql
│   │       ├── 003_sync.up.sql         # Phase 4: sync_batches, sync_pages
│   │       ├── 003_sync.down.sql
│   │       ├── 004_audit.up.sql        # Phase 5: audit_logs (partitioned)
│   │       ├── 004_audit.down.sql
│   │       ├── 005_settings.up.sql     # Phase 6: settings
│   │       └── 005_settings.down.sql
│   │
│   ├── middleware/
│   │   ├── auth.go                     # JWT verification + hub context extraction
│   │   ├── apikey.go                   # API key auth for MCP/external access
│   │   ├── cors.go                     # CORS whitelist *.medinet.vn
│   │   ├── ratelimit.go               # Token bucket rate limiting (Redis)
│   │   ├── audit.go                    # Auto audit logging middleware
│   │   └── recovery.go                # Panic recovery + structured error logging
│   │
│   ├── model/
│   │   ├── hub.go                      # Hub struct
│   │   ├── user.go                     # User, UserHubRole structs
│   │   ├── document.go                 # Document, DocumentChunk structs
│   │   ├── page.go                     # Page, PageVersion structs
│   │   ├── sync.go                     # SyncBatch, SyncPage structs
│   │   ├── audit.go                    # AuditLogEntry struct
│   │   ├── apikey.go                   # APIKey struct
│   │   └── search.go                  # SearchRequest, SearchResult structs
│   │
│   ├── repository/
│   │   ├── hub_repo.go                 # Hub CRUD queries
│   │   ├── user_repo.go                # User CRUD queries
│   │   ├── document_repo.go            # Document + chunk queries
│   │   ├── page_repo.go                # Page + version queries (per-Hub DB)
│   │   ├── sync_repo.go                # Sync batch + page queries
│   │   ├── audit_repo.go               # Audit log queries
│   │   ├── apikey_repo.go              # API key queries
│   │   └── settings_repo.go            # Settings queries
│   │
│   ├── service/
│   │   ├── auth_service.go             # Login, logout, token refresh
│   │   ├── hub_service.go              # Hub management logic
│   │   ├── user_service.go             # User management + invitation
│   │   ├── document_service.go         # Document upload + management
│   │   ├── page_service.go             # Wiki page CRUD + version
│   │   ├── sync_service.go             # Sync workflow logic
│   │   ├── audit_service.go            # Audit query + CSV export
│   │   ├── apikey_service.go           # API key lifecycle
│   │   ├── profile_service.go          # Profile + password change
│   │   └── settings_service.go         # System settings
│   │
│   ├── handler/
│   │   ├── auth_handler.go             # POST /api/auth/*
│   │   ├── hub_handler.go              # /api/hubs/*
│   │   ├── user_handler.go             # /api/users/*
│   │   ├── document_handler.go         # /api/documents/*
│   │   ├── page_handler.go             # /api/pages/*
│   │   ├── search_handler.go           # /api/search/*
│   │   ├── sync_handler.go             # /api/sync/*
│   │   ├── audit_handler.go            # /api/audit-logs/*
│   │   ├── apikey_handler.go           # /api/api-keys/*
│   │   ├── profile_handler.go          # /api/profile/*
│   │   ├── settings_handler.go         # /api/settings/*
│   │   └── mcp_handler.go             # /mcp/tools/*
│   │
│   ├── router/
│   │   └── router.go                   # Route registration + middleware binding
│   │
│   ├── vectorstore/
│   │   ├── store.go                    # VectorStore interface
│   │   ├── chromadb.go                 # ChromaDB implementation
│   │   └── mock.go                     # Mock implementation for testing
│   │
│   ├── embedding/
│   │   ├── provider.go                 # EmbeddingProvider interface
│   │   ├── openai.go                   # OpenAI text-embedding-3-small/large
│   │   ├── gemini.go                   # Google text-embedding-004
│   │   └── batch.go                    # Batch embedding processor
│   │
│   ├── rag/
│   │   ├── pipeline.go                 # Pipeline orchestrator (Extract → Chunk → Embed → Store)
│   │   ├── extractor/
│   │   │   ├── extractor.go            # Extractor interface
│   │   │   ├── pdf.go                  # PDF extraction (pdftotext/Tika)
│   │   │   ├── docx.go                # DOCX extraction (unioffice)
│   │   │   ├── xlsx.go                # XLSX extraction (excelize)
│   │   │   ├── pptx.go               # PPTX extraction
│   │   │   └── text.go                # TXT/MD passthrough
│   │   ├── chunker/
│   │   │   ├── chunker.go             # Chunker interface
│   │   │   ├── recursive.go           # Recursive text splitter
│   │   │   └── semantic.go            # Heading-aware semantic chunker
│   │   ├── searcher.go                 # Search engine (single + cross-hub)
│   │   ├── scorer.go                   # ALG-001 scoring algorithm
│   │   └── cache.go                    # Redis search cache layer
│   │
│   ├── worker/
│   │   ├── manager.go                  # Worker pool manager
│   │   ├── embed_worker.go             # Document embedding worker
│   │   ├── reembed_worker.go           # Auto re-embed on page change
│   │   ├── email_worker.go             # Email sending worker
│   │   └── audit_worker.go             # Async audit log writer
│   │
│   └── pkg/
│       ├── jwt/
│       │   └── jwt.go                  # Sign/Verify JWT with RS256
│       ├── hash/
│       │   └── argon2.go               # Argon2id password hashing
│       ├── crypto/
│       │   └── aes.go                  # AES-256-GCM for DB credential encryption
│       ├── validator/
│       │   └── validator.go            # Input validation helpers
│       └── response/
│           └── response.go             # Standardized JSON response format
│
├── scripts/
│   ├── seed.sql                        # Seed data: default admin + 3 hubs
│   └── generate_keys.sh                # Generate RS256 keypair per hub
│
├── docker-compose.yml
├── Dockerfile
├── Makefile
├── go.mod
├── go.sum
├── .env.example
└── README.md
```

---

## 4. Infrastructure (Docker Compose)

```yaml
# docker-compose.yml

version: "3.9"

services:
  # ─────────────── PostgreSQL ───────────────
  postgres:
    image: postgres:16-alpine
    container_name: medinet_postgres
    restart: unless-stopped
    environment:
      POSTGRES_DB: medinet_central
      POSTGRES_USER: medinet
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - pgdata:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U medinet"]
      interval: 10s
      timeout: 5s
      retries: 5

  # ─────────────── Redis ───────────────
  redis:
    image: redis:7-alpine
    container_name: medinet_redis
    restart: unless-stopped
    command: >
      redis-server
      --requirepass ${REDIS_PASSWORD}
      --maxmemory 256mb
      --maxmemory-policy allkeys-lru
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "-a", "${REDIS_PASSWORD}", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  # ─────────────── ChromaDB ───────────────
  chromadb:
    image: chromadb/chroma:0.5.23
    container_name: medinet_chromadb
    restart: unless-stopped
    environment:
      ANONYMIZED_TELEMETRY: "false"
      CHROMA_SERVER_AUTH_CREDENTIALS: ${CHROMA_TOKEN}
      CHROMA_SERVER_AUTH_PROVIDER: chromadb.auth.token_authn.TokenAuthenticationServerProvider
    volumes:
      - chromadata:/chroma/chroma
    ports:
      - "8000:8000"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/v1/heartbeat"]
      interval: 10s
      timeout: 5s
      retries: 5

  # ─────────────── Go API (dev) ───────────────
  api:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: medinet_api
    restart: unless-stopped
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
      chromadb:
        condition: service_healthy
    environment:
      - APP_ENV=development
      - DB_HOST=postgres
      - DB_PORT=5432
      - DB_NAME=medinet_central
      - DB_USER=medinet
      - DB_PASSWORD=${DB_PASSWORD}
      - REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379/0
      - CHROMA_URL=http://chromadb:8000
      - CHROMA_TOKEN=${CHROMA_TOKEN}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - JWT_PRIVATE_KEY_PATH=/app/keys/private.pem
      - JWT_PUBLIC_KEY_PATH=/app/keys/public.pem
    volumes:
      - ./backend:/app
      - ./keys:/app/keys:ro
      - uploads:/app/uploads
    ports:
      - "8080:8080"

volumes:
  pgdata:
  chromadata:
  uploads:
```

---

## 5. PHASE 1 — Minimal Foundation

### 5.1 Mục Tiêu

Go server chạy được, kết nối PostgreSQL + Redis + ChromaDB, auth đủ dùng để bảo vệ API.
Không làm thừa — **chỉ đủ để Phase 2 (RAG Pipeline) hoạt động**.

### 5.2 Database Schema

```sql
-- ================================================================
-- Migration: 001_bootstrap.up.sql
-- CENTRAL DB — Chỉ những bảng mà RAG Pipeline cần
-- ================================================================

-- ─────────────── Hubs ───────────────
-- RAG cần biết hub nào tồn tại để map ChromaDB collection
CREATE TABLE hubs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(100) NOT NULL,
    code            VARCHAR(50) UNIQUE NOT NULL,
    subdomain       VARCHAR(100) UNIQUE NOT NULL,
    description     TEXT,
    db_host         VARCHAR(255),
    db_port         INT DEFAULT 5432,
    db_name         VARCHAR(100),
    db_user         VARCHAR(100),
    db_password_enc TEXT,                          -- AES-256-GCM encrypted
    chroma_collection VARCHAR(100) NOT NULL,
    status          VARCHAR(20) DEFAULT 'active'
                    CHECK (status IN ('active', 'inactive')),
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────── Users ───────────────
-- Minimal cho auth
CREATE TABLE users (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email              VARCHAR(255) UNIQUE NOT NULL,
    name               VARCHAR(100) NOT NULL,
    phone              VARCHAR(20),
    department         VARCHAR(100),
    password_hash      TEXT NOT NULL,               -- Argon2id
    avatar_url         VARCHAR(500),
    status             VARCHAR(20) DEFAULT 'active'
                       CHECK (status IN ('active', 'disabled')),
    failed_login_count INT DEFAULT 0,
    locked_until       TIMESTAMPTZ,
    created_at         TIMESTAMPTZ DEFAULT NOW(),
    updated_at         TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────── User-Hub Role Mapping (RBAC per Hub) ───────────────
CREATE TABLE user_hub_roles (
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    hub_id  UUID REFERENCES hubs(id) ON DELETE CASCADE,
    role    VARCHAR(30) NOT NULL
            CHECK (role IN ('admin_hub_tong', 'admin_hub_du_an', 'viewer')),
    PRIMARY KEY (user_id, hub_id)
);

-- ─────────────── API Keys ───────────────
-- Cho phép RAG search không cần user session (MCP, external)
CREATE TABLE api_keys (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(100) NOT NULL,
    key_hash        TEXT NOT NULL,                  -- SHA-256 (không lưu plaintext)
    key_prefix      VARCHAR(12) NOT NULL,           -- "mk_xxxx..." for display
    permissions     TEXT[] NOT NULL DEFAULT '{read}',
    allowed_hub_ids UUID[],
    allowed_rag_configs TEXT[],
    rate_limit      INT DEFAULT 60,                 -- requests per minute
    expires_at      TIMESTAMPTZ,
    status          VARCHAR(20) DEFAULT 'active'
                    CHECK (status IN ('active', 'revoked')),
    requests_today  INT DEFAULT 0,
    requests_7d     INT DEFAULT 0,
    bandwidth_used  BIGINT DEFAULT 0,
    last_used_at    TIMESTAMPTZ,
    created_by      UUID REFERENCES users(id),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────── Revoked Tokens (JWT blacklist for logout) ───────────────
CREATE TABLE revoked_tokens (
    jti        UUID PRIMARY KEY,
    user_id    UUID REFERENCES users(id),
    revoked_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX idx_revoked_tokens_expires ON revoked_tokens(expires_at);

-- ─────────────── Documents ───────────────
-- Metadata tài liệu upload cho RAG pipeline
-- LƯU Ý: Ở giao diện Hub Tổng, module này hiển thị là "Danh sách tri thức"
-- Hub Tổng chỉ nhận và duyệt tri thức từ Hub con qua Sync Workflow,
-- KHÔNG có chức năng nạp tri thức mới (ẩn ở FE bằng flag IS_HUB_TONG).
-- Chỉ Hub Dự Án mới có quyền upload/compose/import tài liệu.
CREATE TABLE documents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(500) NOT NULL,
    file_type       VARCHAR(10) NOT NULL
                    CHECK (file_type IN ('pdf','docx','txt','md','xlsx','pptx','jpg','png','csv','html')),
    file_size       BIGINT,
    file_path       VARCHAR(1000),
    hub_id          UUID REFERENCES hubs(id) NOT NULL,
    status          VARCHAR(20) DEFAULT 'pending'
                    CHECK (status IN ('pending','processing','completed','error')),
    progress        INT DEFAULT 0 CHECK (progress >= 0 AND progress <= 100),
    error_message   TEXT,
    chunk_count     INT DEFAULT 0,
    uploaded_by     UUID REFERENCES users(id),
    uploaded_at     TIMESTAMPTZ DEFAULT NOW(),
    processed_at    TIMESTAMPTZ
);

CREATE INDEX idx_documents_hub ON documents(hub_id);
CREATE INDEX idx_documents_status ON documents(status);

-- ─────────────── Document Chunks ───────────────
-- Tracking từng chunk đã embed vào ChromaDB
CREATE TABLE document_chunks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id     UUID REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index     INT NOT NULL,
    content         TEXT NOT NULL,
    token_count     INT,
    chroma_id       VARCHAR(100),                   -- ChromaDB document ID
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(document_id, chunk_index)
);

CREATE INDEX idx_chunks_document ON document_chunks(document_id);
CREATE INDEX idx_chunks_chroma ON document_chunks(chroma_id);
```

**Seed Data:**

```sql
-- scripts/seed.sql

-- Default admin (password: sẽ thay đổi lần đầu đăng nhập)
INSERT INTO users (email, name, password_hash) VALUES
    ('admin@medinet.vn', 'System Admin', '$argon2id$...');

-- 3 Hubs mặc định
INSERT INTO hubs (name, code, subdomain, chroma_collection) VALUES
    ('Tâm Đạo Y Quán', 'tamdao', 'tamdao.medinet.vn', 'medinet_tamdao'),
    ('Đỗ Minh Đường', 'dmd', 'dmd.medinet.vn', 'medinet_dmd'),
    ('HCNS', 'hcns', 'hcns.medinet.vn', 'medinet_hcns');

-- Admin role assignment
INSERT INTO user_hub_roles (user_id, hub_id, role)
SELECT u.id, h.id, 'admin_hub_tong'
FROM users u, hubs h
WHERE u.email = 'admin@medinet.vn';
```

### 5.3 Auth API

| Endpoint | Method | Mô Tả | Auth |
|----------|--------|--------|------|
| `/api/auth/login` | POST | Email + password -> JWT access + refresh token | Public |
| `/api/auth/logout` | POST | Blacklist token (thêm jti vào revoked_tokens) | JWT |
| `/api/auth/refresh` | POST | Refresh token -> new access token | Refresh token |
| `/api/auth/me` | GET | Current user info + roles | JWT |

**JWT Payload Structure:**

```json
{
  "sub": "user-uuid",
  "email": "admin@medinet.vn",
  "name": "System Admin",
  "hub_id": "hub-uuid",
  "role": "admin_hub_tong",
  "subdomain": "wiki.medinet.vn",
  "iat": 1712505600,
  "exp": 1712506500,
  "jti": "unique-token-uuid"
}
```

**Token Lifetime:**

| Token Type | Lifetime |
|-----------|----------|
| Access Token | 15 phút |
| Refresh Token | 7 ngày |

**Middleware Chain:**

```
Request → CORS → Recovery → RateLimit → JWT Verify → Hub Context → RBAC → Handler
```

### 5.4 Hub Registry API (Read-heavy)

| Endpoint | Method | Mô Tả | Auth |
|----------|--------|--------|------|
| `/api/hubs` | GET | List all hubs (dùng cho dropdown frontend) | JWT |
| `/api/hubs/:id` | GET | Hub detail | JWT |
| `/api/hubs` | POST | Create hub + init ChromaDB collection | admin_hub_tong |
| `/api/hubs/:id` | PUT | Update hub config | admin_hub_tong |
| `/api/hubs/:id/status` | PATCH | Enable/Disable hub | admin_hub_tong |
| `/api/hubs/:id/test-connection` | POST | Test DB connection (timeout 5s) | admin_hub_tong |

### 5.5 Bảo Mật Phase 1

| Aspect | Implementation | Chi Tiết |
|--------|---------------|----------|
| Password hashing | Argon2id | memory=64MB, iterations=3, parallelism=4 |
| JWT signing | RS256 (asymmetric) | Mỗi Hub có keypair riêng, private key chỉ ở server |
| Login brute-force | Rate limit + account lock | 5 failed attempts -> lock 15 phút (theo URD UC-01) |
| CORS | Strict whitelist | Chỉ cho phép `*.medinet.vn` origins |
| SQL injection | Parameterized queries | sqlc generates type-safe code |
| Input validation | Struct tags + validator | Validate tất cả input trước khi xử lý |
| DB credentials | AES-256-GCM | Hub DB password encrypted at rest |
| Secrets management | Environment variables | Không hardcode, `.env` file cho dev |

### 5.6 Deliverables Phase 1

- [x] Go project initialized với Gin framework
- [x] Cài trực tiếp trên Windows (PostgreSQL + ChromaDB pip + Redis optional)
- [x] Database migrations chạy tự động khi server start (embedded SQL, golang-migrate)
- [x] Seed data: admin user + 3 hubs + 36 demo users + 32 documents + 15 API keys
- [x] Login/Logout/Refresh/Me API hoạt động (Argon2id + RS256 JWT)
- [x] JWT middleware verify token + RequireRole("admin")
- [x] Hub registry CRUD API (list, get, create, update, status, test-connection)
- [x] Health check endpoint: `GET /health`
- [x] Structured logging (slog JSON)
- [x] Makefile + start.ps1 (auto-load .env, kill old port, start ChromaDB)
- [x] Redis optional — server chạy bình thường khi không có Redis
- [x] FE kết nối: Login, Layout (user info), Dashboard (hubs), HubRegistry (CRUD)

> **Ghi chú:** Đã đổi role system từ `admin_hub_tong/admin_hub_du_an/viewer` → đơn giản `admin/viewer`

---

## 6. PHASE 2 — RAG Pipeline & Vector Hóa Dữ Liệu

### 6.1 Mục Tiêu

Xây toàn bộ pipeline: **Upload → Extract → Chunk → Embed → Store vào ChromaDB**.
Đây là trọng tâm cốt lõi — module có giá trị nhất của hệ thống.

### 6.2 Pipeline Architecture

```
┌────────────────────────────────────────────────────────────────────┐
│                       RAG INGESTION PIPELINE                        │
│                                                                      │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐     │
│  │ EXTRACT  │───►│ CHUNK    │───►│ EMBED    │───►│ STORE    │     │
│  │          │    │          │    │          │    │          │     │
│  │ PDF→Text │    │ 512 tok  │    │ Batch    │    │ ChromaDB │     │
│  │ DOCX→Txt │    │ 50 over  │    │ 100/call │    │ + PgSQL  │     │
│  │ XLSX→Txt │    │ Heading  │    │ Retry 3x │    │ Metadata │     │
│  │ PPTX→Txt │    │ aware    │    │ Backoff  │    │          │     │
│  │ TXT/MD   │    │          │    │          │    │          │     │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘     │
│   progress:        progress:       progress:       progress:        │
│     0-10%           10-40%          40-80%          80-100%         │
│                                                                      │
│  Status updates: Redis PubSub → API polling → Frontend               │
└────────────────────────────────────────────────────────────────────┘
```

### 6.3 Embedding Provider Abstraction

```go
// internal/embedding/provider.go

type EmbeddingProvider interface {
    // Embed converts text strings into vector embeddings
    Embed(ctx context.Context, texts []string) ([][]float32, error)
    
    // ModelName returns the model identifier
    ModelName() string
    
    // Dimension returns the embedding vector dimension
    Dimension() int
}
```

**Supported Providers:**

| Provider | Model | Dimension | Tiếng Việt | Cost | Phase |
|----------|-------|-----------|------------|------|-------|
| OpenAI | `text-embedding-3-small` | 1536 | Tốt | $0.02/1M tokens | **Phase 2 default** |
| OpenAI | `text-embedding-3-large` | 3072 | Rất tốt | $0.13/1M tokens | Production option |
| Google | `text-embedding-004` | 768 | Tốt | Free tier generous | Alternative |
| Self-host | `Qwen3-Embedding` | 1024 | Rất tốt (y khoa VN) | Infrastructure cost | Phase 6 evaluate |

**Cấu hình (Settings frontend tab "Cấu hình RAG"):**

| Setting | Key | Default | Mô Tả |
|---------|-----|---------|--------|
| Embedding Model | `rag.embedding_model` | `text-embedding-3-small` | Model dùng để vector hóa |
| Chunk Size | `rag.chunk_size` | `512` | Số tokens mỗi chunk |
| Chunk Overlap | `rag.chunk_overlap` | `50` | Overlap giữa các chunk |
| Batch Size | `rag.batch_size` | `100` | Số chunks mỗi lần gọi API |
| Min Similarity | `rag.min_similarity` | `0.3` | Ngưỡng similarity tối thiểu |

### 6.4 ChromaDB Client Abstraction

```go
// internal/vectorstore/store.go

type VectorStore interface {
    // Collection management
    CreateCollection(ctx context.Context, name string) error
    DeleteCollection(ctx context.Context, name string) error
    ListCollections(ctx context.Context) ([]string, error)
    
    // Document operations — batch upsert/delete
    Upsert(ctx context.Context, collection string, docs []VectorDocument) error
    Delete(ctx context.Context, collection string, filter map[string]any) error
    
    // Query — vector similarity search
    Query(ctx context.Context, collection string, queryVec []float32, opts QueryOpts) ([]VectorSearchResult, error)
    
    // Count vectors in collection
    Count(ctx context.Context, collection string) (int, error)
}

type VectorDocument struct {
    ID        string              // Format: "{docID}_{chunkIndex}"
    Content   string              // Chunk text content
    Embedding []float32           // Vector embedding
    Metadata  map[string]any      // document_id, document_name, hub_id, chunk_index, category, tags
}

type QueryOpts struct {
    TopK     int                  // Number of results to return
    MinScore float64              // Minimum cosine similarity threshold
    Filter   map[string]any       // Metadata filter (category, tags, date range)
}

type VectorSearchResult struct {
    ID       string
    Content  string
    Score    float64              // Cosine similarity (0-1)
    Metadata map[string]any
}
```

**ChromaDB Collection Naming Convention:**

```
Hub "Tâm Đạo"     → collection: "medinet_tamdao"
Hub "Đỗ Minh"     → collection: "medinet_dmd"
Hub "HCNS"        → collection: "medinet_hcns"
Hub Tổng (synced) → collection: "medinet_central"
```

Mỗi Hub = 1 ChromaDB collection riêng → data isolation + query performance (không cần filter hub_id trong vector search).

### 6.5 Extract Stage — Trích Xuất Nội Dung

```go
// internal/rag/extractor/extractor.go

type Extractor interface {
    Extract(ctx context.Context, filePath string) (string, error)
    SupportedType() string
}
```

| File Type | Library / Tool | Ghi Chú |
|-----------|---------------|---------|
| PDF | `pdftotext` (poppler-utils) | Nhanh, CLI tool. Fallback: Apache Tika cho PDF phức tạp |
| DOCX | `unidoc/unioffice` | Pure Go, không cần external dependency |
| XLSX | `excelize` | Parse từng sheet → concatenate text |
| PPTX | Go XML parser | Extract text từ slides |
| TXT | `os.ReadFile` | Direct read, UTF-8 |
| MD | `os.ReadFile` | Direct read, giữ nguyên markdown structure |

**Xử lý đặc biệt cho tài liệu y khoa:**

- PDF bài thuốc thường có bảng (thành phần, liều lượng) → extract bảng thành markdown table
- DOCX phác đồ điều trị có nested list → preserve hierarchy
- XLSX danh mục thuốc → mỗi row thành 1 text block với column headers

### 6.6 Chunk Stage — Chia Nhỏ Văn Bản

```go
// internal/rag/chunker/chunker.go

type Chunker interface {
    Chunk(text string, opts ChunkOpts) []Chunk
}

type ChunkOpts struct {
    MaxTokens  int    // default 512
    Overlap    int    // default 50
}

type Chunk struct {
    Index      int
    Content    string
    TokenCount int
    StartChar  int    // Character offset trong original text
    EndChar    int
}
```

**Chiến lược Chunking (Recursive Text Splitter):**

```
Ưu tiên 1: Split by heading (## / ###) — giữ nguyên section logic
    ↓ nếu chunk vẫn > MaxTokens
Ưu tiên 2: Split by paragraph (\n\n) — giữ nguyên ý nghĩa
    ↓ nếu chunk vẫn > MaxTokens
Ưu tiên 3: Split by sentence (. ! ?) — cắt theo câu
    ↓ nếu chunk vẫn > MaxTokens
Ưu tiên 4: Split by token (hard cut) — last resort, thêm overlap
```

**Overlap 50 tokens giữa các chunk liền kề → đảm bảo tên thuốc/bài thuốc không bị cắt giữa chừng:**

```
Ví dụ bài thuốc "Bình Vị Tán":

┌────────────────────────────────────────────────────────────┐
│ Chunk 0: "## Bình Vị Tán                                   │
│ Thành phần: Thương truật 12g, Hậu phác 10g, Trần bì 8g,  │
│ Cam thảo 4g, Sinh khương 3 lát, Đại táo 3 quả.           │
│                                                            │
│ Công dụng: Kiện tỳ táo thấp, hành khí..."                 │
├───────────── overlap 50 tokens ────────────────────────────┤
│ Chunk 1: "...hành khí hòa vị.                              │
│ Chủ trị: Tỳ vị thấp trệ, bụng trướng đầy,               │
│ ăn không tiêu, nôn mửa, tiêu chảy..."                     │
└────────────────────────────────────────────────────────────┘
```

### 6.7 Embed Stage — Vector Hóa

```go
// internal/rag/pipeline.go — Embed stage

func (p *Pipeline) embedChunks(ctx context.Context, docID string, chunks []Chunk) error {
    totalBatches := (len(chunks) + p.batchSize - 1) / p.batchSize
    
    for batchIdx := 0; batchIdx < totalBatches; batchIdx++ {
        start := batchIdx * p.batchSize
        end := min(start+p.batchSize, len(chunks))
        batch := chunks[start:end]
        
        // Extract text content from chunks
        texts := make([]string, len(batch))
        for i, c := range batch {
            texts[i] = c.Content
        }
        
        // Call embedding API with retry (exponential backoff)
        var vectors [][]float32
        err := retryWithBackoff(ctx, 3, time.Second, func() error {
            var embedErr error
            vectors, embedErr = p.embedder.Embed(ctx, texts)
            return embedErr
        })
        if err != nil {
            return fmt.Errorf("embedding batch %d failed: %w", batchIdx, err)
        }
        
        // Build VectorDocuments
        docs := make([]VectorDocument, len(batch))
        for i, chunk := range batch {
            docs[i] = VectorDocument{
                ID:        fmt.Sprintf("%s_%d", docID, chunk.Index),
                Content:   chunk.Content,
                Embedding: vectors[i],
                Metadata: map[string]any{
                    "document_id":   docID,
                    "document_name": p.currentDocName,
                    "hub_id":        p.currentHubID,
                    "chunk_index":   chunk.Index,
                    "token_count":   chunk.TokenCount,
                },
            }
        }
        
        // Upsert to ChromaDB
        if err := p.store.Upsert(ctx, p.currentCollection, docs); err != nil {
            return fmt.Errorf("store batch %d failed: %w", batchIdx, err)
        }
        
        // Save chunks to PostgreSQL
        if err := p.chunkRepo.BatchInsert(ctx, docID, batch, docs); err != nil {
            return fmt.Errorf("save chunks batch %d failed: %w", batchIdx, err)
        }
        
        // Update progress: 40% (chunk done) + 40% * (batch progress)
        progress := 40 + (40 * (batchIdx + 1) / totalBatches)
        p.updateProgress(ctx, docID, "embed", progress)
    }
    
    return nil
}
```

### 6.8 Document Upload API

| Endpoint | Method | Mô Tả | Auth |
|----------|--------|--------|------|
| `/api/documents/upload` | POST | Multipart upload → queue processing | JWT (admin) |
| `/api/documents` | GET | List documents (filter: hub, status, type) | JWT |
| `/api/documents/:id` | GET | Document detail + chunks preview | JWT |
| `/api/documents/:id/status` | GET | Processing progress (polling) | JWT |
| `/api/documents/:id` | DELETE | Delete doc + remove vectors from ChromaDB | JWT (admin) |
| `/api/documents/compose` | POST | Direct text input → queue processing | JWT (admin) |
| `/api/documents/url` | POST | URL extraction → queue processing | JWT (admin) |

**Upload Flow:**

```
Client                        API Server                     Redis Queue          Worker
──────                        ──────────                     ───────────          ──────
  │ POST /api/documents/upload    │                              │                   │
  │ (multipart/form-data)         │                              │                   │
  │──────────────────────────────►│                              │                   │
  │                               │ 1. Validate file             │                   │
  │                               │    (type, size, MIME)        │                   │
  │                               │ 2. Save to disk              │                   │
  │                               │    uploads/{hub}/{docId}/    │                   │
  │                               │ 3. Insert document record    │                   │
  │                               │    (status='pending')        │                   │
  │                               │ 4. Enqueue job ─────────────►│                   │
  │                               │                              │                   │
  │◄──────────────────────────────│                              │                   │
  │ 202 Accepted                  │                              │                   │
  │ { id, status: "pending" }     │                              │                   │
  │                               │                              │ 5. Dequeue ──────►│
  │                               │                              │                   │
  │                               │                              │    Extract (0-10%)│
  │                               │                              │    Chunk (10-40%) │
  │                               │                              │    Embed (40-80%) │
  │                               │                              │    Store (80-100%)│
  │                               │                              │                   │
  │ GET /api/documents/:id/status │                              │    Update progress│
  │──────────────────────────────►│◄─────────────────────────────│────────────────── │
  │◄──────────────────────────────│                              │                   │
  │ { progress: 65, stage: "embed" }                             │                   │
  │                               │                              │    status →       │
  │                               │                              │    "completed"    │
```

### 6.9 Worker Pool Architecture

```go
// internal/worker/manager.go

type WorkerManager struct {
    embedWorkers   int           // default 3 concurrent workers
    reembedWorkers int           // default 1 worker
    redis          *redis.Client
    pipeline       *rag.Pipeline
}

// Redis Queue Keys:
// "rag:embed"     — document embedding jobs (Phase 2)
// "rag:reembed"   — page re-embed jobs (Phase 4 hook)
// "email:send"    — email sending jobs (Phase 5)
// "audit:write"   — async audit log writing (Phase 5)
```

**Job Payload (Redis):**

```json
{
  "job_id": "uuid",
  "document_id": "uuid",
  "hub_id": "uuid",
  "hub_code": "tamdao",
  "file_path": "uploads/tamdao/doc-uuid/original.pdf",
  "file_type": "pdf",
  "collection": "medinet_tamdao",
  "retry_count": 0,
  "max_retries": 3,
  "created_at": "2026-04-07T10:00:00Z"
}
```

### 6.10 Auto Re-embed Worker (RG-08 từ PRD)

Xây sẵn worker ở Phase 2, hook vào wiki CRUD ở Phase 4:

```
Wiki page created/updated/deleted
         │
         ▼
  Redis Queue: "rag:reembed"
  {
    "action": "upsert" | "delete",
    "hub_id": "uuid",
    "hub_code": "tamdao",
    "page_id": "uuid",
    "title": "Phác đồ trị đau dạ dày",
    "content": "## Phác đồ...",
    "category": "Điều trị",
    "tags": ["Dạ dày", "Đông y"]
  }
         │
         ▼
  Worker: Chunk content → Embed → Upsert to ChromaDB
  (replace old vectors where metadata.page_id == page_id)
```

### 6.11 Hiệu Năng & Resilience

| Concern | Solution |
|---------|----------|
| Upload blocking API | Async: API trả `202 Accepted`, worker xử lý background |
| Embedding API chậm | Batch 100 chunks/call → giảm roundtrip 100x |
| Embedding API fail | Retry 3x, exponential backoff (1s → 2s → 4s) |
| Large file (>50MB) | Reject. Max file size configurable, default 50MB |
| Worker crash | Redis queue + job acknowledgment → auto-retry unacked jobs |
| Concurrent uploads | Worker pool 3 goroutines (configurable `RAG_WORKER_COUNT`) |
| Duplicate upload | SHA-256 file content hash → skip nếu đã tồn tại |
| Progress tracking | Redis key `rag:progress:{docId}` → polling endpoint |
| Memory usage | Stream extract — không load toàn bộ file vào RAM |
| ChromaDB down | Worker retry with backoff, document status → "error" |

### 6.12 Bảo Mật Phase 2

| Concern | Solution |
|---------|----------|
| File upload attack | Validate MIME magic bytes (không tin file extension) |
| Path traversal | UUID-based storage path: `uploads/{hub_code}/{doc_uuid}/` |
| File size limit | Max 50MB per file, configurable |
| File type whitelist | Chỉ cho phép: pdf, docx, txt, md, xlsx, pptx |
| Content injection | Sanitize extracted text trước khi embed |
| Storage isolation | Mỗi Hub có thư mục riêng |
| API key exposure | Embedding API key chỉ trong env, không log |

### 6.13 Deliverables Phase 2

- [x] Embedding provider: OpenAI implementation (text-embedding-3-small/large)
- [x] Embedding provider: Gemini implementation (text-embedding-004)
- [x] ChromaDB client wrapper (v2 API: `/api/v2/tenants/default_tenant/databases/...`)
- [x] Extractor: PDF, DOCX, XLSX, PPTX, TXT, MD, CSV, HTML (8 types)
- [x] Recursive text chunker (heading → paragraph → sentence → hard cut, overlap 50)
- [x] Batch embedding processor (configurable batch size, retry 3x exponential backoff)
- [x] Pipeline orchestrator (Extract → Chunk → Embed → Store, progress callback)
- [x] Worker pool manager (channel-based in-memory queue, 3 concurrent goroutines)
- [x] Document upload API (multipart, validate type/size, save to `uploads/{hub}/{uuid}/`)
- [x] Document compose API (text → .md → enqueue)
- [x] Document list/detail/delete API (pagination, filter by hub/status/type)
- [x] Progress tracking endpoint (polling `GET /api/documents/:id/status`)
- [x] Auto re-embed worker (ready, hooked in Phase 4)
- [ ] Integration test: upload PDF → verify vectors in ChromaDB (cần OpenAI key thật)
- [x] FE kết nối: DocumentIngestion (upload, compose, list, delete, status polling)

> **Ghi chú:** ChromaDB 1.5.6 dùng v2 API (không còn v1). File type lưu không có dấu chấm ("pdf" không phải ".pdf").

---

## 7. PHASE 3 — Semantic Search & Cross-Hub Search

### 7.1 Mục Tiêu

Search hoạt động end-to-end: single hub + cross-hub + hybrid scoring + caching.
Frontend `CrossHubSearch.tsx` kết nối được API thực.

### 7.2 Search API

| Endpoint | Method | Mô Tả | Auth |
|----------|--------|--------|------|
| `/api/search` | POST | Search within single hub (JWT's hub context) | JWT |
| `/api/search/cross-hub` | POST | Fan-out search across all active hubs | admin_hub_tong |
| `/api/search/similar` | POST | Find similar pages (duplicate detection for Sync) | JWT (admin) |

### 7.3 Request / Response Schema

**Search Request:**

```json
{
  "query": "Phác đồ trị đau dạ dày",
  "hub_ids": [],
  "top_k": 10,
  "min_score": 0.3,
  "filters": {
    "categories": ["Điều trị"],
    "tags": ["Đông y"],
    "date_from": "2025-01-01",
    "date_to": "2026-04-07"
  }
}
```

- `hub_ids`: empty = search all active hubs (cross-hub), hoặc chỉ định hub cụ thể
- `top_k`: max 50, default 10
- `min_score`: cosine similarity threshold, default 0.3

**Search Response:**

```json
{
  "results": [
    {
      "id": "doc_uuid_3",
      "hub_id": "hub-uuid",
      "hub_name": "Tâm Đạo Y Quán",
      "title": "Phác đồ trị đau dạ dày",
      "snippet": "Sử dụng bài thuốc Bình Vị Tán kết hợp châm cứu các huyệt Trung Quản, Túc Tam Lý...",
      "category": "Điều trị",
      "tags": ["Dạ dày", "Đông y"],
      "score": 0.87,
      "raw_similarity": 0.92,
      "updated_at": "2026-04-05T10:30:00Z",
      "source": "document"
    }
  ],
  "total_hubs_searched": 3,
  "query_time_ms": 156,
  "cache_hit": false
}
```

### 7.4 Single-Hub Search Flow

```
Query "Phác đồ trị đau dạ dày"
        │
        ▼
┌───────────────────┐
│ 1. Check Cache    │ ── hit ──► Return cached results
│    (Redis 5min)   │
└───────┬───────────┘
        │ miss
        ▼
┌───────────────────┐
│ 2. Embed Query    │ ← Check embedding cache (Redis 1h) first
│    text → vector  │   Reuse if same query was embedded before
└───────┬───────────┘
        │ query_vector [1536]
        ▼
┌───────────────────┐     ┌───────────────────┐
│ 3a. Vector Search │     │ 3b. Keyword Search│
│   (ChromaDB)      │     │   (PostgreSQL FTS)│
│                   │     │                   │
│   collection:     │     │   to_tsvector()   │
│   medinet_tamdao  │     │   GIN index       │
│   top_k: 20       │     │   top_k: 20       │
└───────┬───────────┘     └───────┬───────────┘
        │ vector_results          │ keyword_results
        └──────────┬──────────────┘
                   ▼
        ┌──────────────────┐
        │ 4. Hybrid Merge  │
        │    Deduplicate   │
        │    + Re-ranking  │
        │    (ALG-001)     │
        └────────┬─────────┘
                 ▼
        ┌──────────────────┐
        │ 5. Return Top K  │
        │    + Cache result │
        └──────────────────┘
```

### 7.5 Cross-Hub Search (Fan-out Pattern)

```go
// Pseudocode — Cross-Hub Search

func CrossHubSearch(ctx, request):
    // 1. Embed query ONCE (reuse across all hubs)
    queryVec = embedder.Embed(request.Query)
    
    // 2. Get target hubs
    hubs = getActiveHubs(request.HubIDs)  // all active if empty
    
    // 3. Fan-out: query all hubs concurrently with timeout
    ctx = withTimeout(ctx, 5 * Second)
    
    channel = make(chan hubResult, len(hubs))
    
    for each hub in hubs:
        go func(hub):
            results = vectorStore.Query(hub.Collection, queryVec, topK=10)
            channel <- {hub, results, error}
    
    // 4. Collect results (respect timeout)
    allResults = []
    hubsSearched = 0
    
    for i = 0; i < len(hubs); i++:
        select:
            case hr = <-channel:
                if hr.error == nil:
                    hubsSearched++
                    allResults.append(enrichWithHubInfo(hr.results, hr.hub))
                // Hub timeout/error → skip, log warning
            case <-ctx.Done():
                break  // global 5s timeout hit
    
    // 5. Global re-rank + return top results
    scored = applyALG001Scoring(allResults)
    sort(scored, by: score DESC)
    return scored[:request.TopK]
```

**Key Design Decisions:**

- Query embedding chỉ gọi **1 lần** dù search N hubs → tiết kiệm API cost
- Mỗi Hub query trong goroutine riêng → parallel execution
- 5s global timeout → hub chậm/chết không block toàn bộ search
- Hub lỗi → skip silently, log warning, frontend hiện badge "Hub X unavailable"
- Final re-rank gộp kết quả từ tất cả Hub → consistent scoring

### 7.6 Scoring Algorithm — ALG-001

Theo PRD Section 3.3:

```
FinalScore = CosineSimilarity × 0.60
           + Popularity       × 0.20
           + Recency          × 0.20
           + VerifiedBonus    (+ 0.05 nếu is_verified = true)
```

**Chi tiết từng yếu tố:**

| Yếu Tố | Weight | Công Thức | Giải Thích |
|---------|--------|-----------|-----------|
| **Cosine Similarity** | 0.60 | Trực tiếp từ ChromaDB (0-1) | Mức độ tương đồng ngữ nghĩa |
| **Popularity** | 0.20 | `log(1 + view_count) / log(1 + max_view_count)` | Log scale để trang phổ biến không dominate |
| **Recency** | 0.20 | `exp(-0.693 × days_since_update / 30)` | Exponential decay, half-life = 30 ngày |
| **Verified Bonus** | +0.05 | Boolean flag | Trang đã được expert verify |

**Ghi chú:** Trọng số và ngưỡng sẽ được tinh chỉnh sau khi có dữ liệu thực (PRD 3.3).

### 7.7 Duplicate Detection

Dùng cho UC-07 (Sync Review) — kiểm tra page sync có trùng với page đã có không:

```
POST /api/search/similar

Request:
{
  "content": "Nội dung trang wiki cần kiểm tra...",
  "hub_id": "hub-uuid",
  "threshold": 0.85
}

Response:
{
  "matches": [
    {
      "page_id": "existing-page-uuid",
      "page_title": "Phác đồ trị đau dạ dày (v2)",
      "similarity_score": 0.91,
      "hub_name": "Tâm Đạo Y Quán"
    }
  ]
}
```

Threshold mặc định = **0.85** (theo PRD 8.1). Nếu similarity >= 0.85 → cảnh báo duplicate trên frontend.

### 7.8 Search Cache Strategy

```
┌─────────────────────────────────────────────────────────┐
│                    CACHE LAYERS                          │
│                                                          │
│  Layer 1: Query Embedding Cache (Redis, TTL 1h)          │
│  Key:   "embed:{sha256(query_text)}"                     │
│  Value: []float32 embedding vector (serialized)          │
│  → Cùng 1 query text không cần gọi Embedding API lại    │
│                                                          │
│  Layer 2: Search Result Cache (Redis, TTL 5m)            │
│  Key:   "search:{sha256(query + hub_ids + filters)}"     │
│  Value: SearchResponse JSON                              │
│  → Cùng search query trả kết quả ngay từ cache          │
│                                                          │
│  Cache Invalidation:                                     │
│  → Document mới embed xong → DELETE "search:*{hub_code}*"│
│  → Page update/delete → DELETE "search:*{hub_code}*"     │
│  → Pattern-based invalidation per hub                    │
└─────────────────────────────────────────────────────────┘
```

### 7.9 Hiệu Năng Targets

| Metric | Target | Implementation |
|--------|--------|---------------|
| Single-hub search latency | < 200ms | Embedding cache + ChromaDB in-memory HNSW |
| Cross-hub search latency (3 hubs) | < 1s | Goroutine fan-out + 5s timeout |
| Cross-hub search latency (10 hubs) | < 3s | Parallel query + early termination |
| Search cache hit ratio | > 60% | Redis TTL 5min cho popular queries |
| Embedding API calls saved | > 50% | Query embedding cache TTL 1h |
| Result relevance threshold | cosine > 0.3 | Drop results below threshold |

### 7.10 Deliverables Phase 3

- [x] Search engine core (single-hub vector search via ChromaDB)
- [x] Cross-hub search (goroutine fan-out, 5s timeout, parallel per hub)
- [x] ALG-001 scoring algorithm (0.60×Similarity + 0.20×Popularity + 0.20×Recency + 0.05×Verified)
- [ ] Hybrid search: vector + keyword PostgreSQL FTS (chỉ vector, chưa hybrid)
- [x] Duplicate detection endpoint (`POST /api/search/similar`, threshold 0.85)
- [x] Query embedding cache (in-memory + Redis optional, TTL 1h)
- [x] Search result cache (in-memory + Redis optional, TTL 5m)
- [x] Cache invalidation helper (per hub)
- [x] Search API: `/api/search` + `/api/search/cross-hub` + `/api/search/similar`
- [ ] Integration test: cần OpenAI key thật để test end-to-end
- [ ] Load test: concurrent search queries
- [x] FE kết nối: CrossHubSearch (real-time search, hub filter, score display)

> **Ghi chú:** Search cần embedding API key thật (OpenAI/Gemini) để hoạt động. Hybrid search (vector + keyword FTS) chưa implement — hiện chỉ vector search.

---

## 8. PHASE 4 — Wiki Pages & Sync Workflow

### 8.1 Mục Tiêu

Hub Dự Án CRUD wiki pages với version history. Sync 1 chiều Hub Dự Án → Hub Tổng.
Mọi page thay đổi tự động trigger re-embed (hook vào Phase 2 worker).

### 8.2 Per-Hub Database Schema

Mỗi Hub DB có schema giống nhau, chạy migration riêng:

```sql
-- ================================================================
-- Migration: hub_001_wiki.up.sql (chạy trên MỖI Hub DB)
-- ================================================================

-- ─────────────── Categories (Tree Structure) ───────────────
CREATE TABLE categories (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name       VARCHAR(100) NOT NULL,
    slug       VARCHAR(100) UNIQUE NOT NULL,
    parent_id  UUID REFERENCES categories(id),
    sort_order INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────── Tags ───────────────
CREATE TABLE tags (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name       VARCHAR(50) UNIQUE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────── Wiki Pages ───────────────
CREATE TABLE pages (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title         VARCHAR(500) NOT NULL,
    slug          VARCHAR(500) UNIQUE NOT NULL,
    content       TEXT NOT NULL,                     -- Markdown content
    content_html  TEXT,                              -- Pre-rendered HTML cache
    category_id   UUID REFERENCES categories(id),
    author_id     UUID NOT NULL,                     -- User UUID from central DB
    status        VARCHAR(20) DEFAULT 'published'
                  CHECK (status IN ('draft','pending_review','published','archived')),
    view_count    INT DEFAULT 0,
    is_verified   BOOLEAN DEFAULT FALSE,
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    updated_at    TIMESTAMPTZ DEFAULT NOW(),
    deleted_at    TIMESTAMPTZ                        -- Soft delete
);

-- ─────────────── Page-Tag Junction ───────────────
CREATE TABLE page_tags (
    page_id UUID REFERENCES pages(id) ON DELETE CASCADE,
    tag_id  UUID REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (page_id, tag_id)
);

-- ─────────────── Page Version History ───────────────
CREATE TABLE page_versions (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    page_id        UUID REFERENCES pages(id) ON DELETE CASCADE,
    version        INT NOT NULL,
    title          VARCHAR(500) NOT NULL,
    content        TEXT NOT NULL,
    changed_by     UUID NOT NULL,
    change_summary VARCHAR(500),
    created_at     TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(page_id, version)
);

-- ─────────────── Indexes ───────────────

-- Full-text search (BM25-like keyword search)
CREATE INDEX idx_pages_fts ON pages
    USING GIN(to_tsvector('simple', coalesce(title,'') || ' ' || coalesce(content,'')));

CREATE INDEX idx_pages_category ON pages(category_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_pages_status ON pages(status) WHERE deleted_at IS NULL;
CREATE INDEX idx_pages_updated ON pages(updated_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX idx_page_versions_page ON page_versions(page_id, version DESC);
```

### 8.3 Wiki Pages API

| Endpoint | Method | Mô Tả | Auth |
|----------|--------|--------|------|
| `/api/pages` | GET | List pages (search, filter, cursor pagination) | JWT |
| `/api/pages` | POST | Create page → auto version 1 → trigger re-embed | admin_hub_du_an |
| `/api/pages/:id` | GET | Page detail (increment view_count) | JWT |
| `/api/pages/:id` | PUT | Update page → auto new version → trigger re-embed | admin_hub_du_an |
| `/api/pages/:id` | DELETE | Soft delete → remove vectors from ChromaDB | admin_hub_du_an |
| `/api/pages/:id/versions` | GET | Version history | JWT |
| `/api/pages/:id/restore/:version` | POST | Restore to version → new version → re-embed | admin_hub_du_an |

**Create/Update Page → Auto Re-embed Hook:**

```
Page CREATE/UPDATE
    │
    ├─► 1. Save to Hub DB (pages table)
    ├─► 2. Create page_versions record
    ├─► 3. Re-render content_html cache
    └─► 4. Enqueue "rag:reembed" job
             │
             └─► Worker (from Phase 2):
                 Chunk page content → Embed → Upsert ChromaDB
                 (replace old vectors for this page_id)
```

**Cursor-based Pagination (không dùng OFFSET):**

```json
// Request
GET /api/pages?limit=10&cursor=eyJ1cGRhdGVkX2F0IjoiMjAyNi0wNC0wN...

// Response
{
  "data": [...],
  "pagination": {
    "has_next": true,
    "next_cursor": "eyJ1cGRhdGVkX2F0IjoiMjAyNi0wNC0wNi..."
  }
}
```

### 8.4 Categories & Tags API

| Endpoint | Method | Mô Tả | Auth |
|----------|--------|--------|------|
| `/api/categories` | GET | Category tree (nested structure) | JWT |
| `/api/categories` | POST | Create category | admin_hub_du_an |
| `/api/categories/:id` | PUT | Update category | admin_hub_du_an |
| `/api/categories/:id` | DELETE | Delete (only if no pages attached) | admin_hub_du_an |
| `/api/tags` | GET | List all tags | JWT |
| `/api/tags` | POST | Create tag | admin_hub_du_an |

### 8.5 Sync Workflow — Hub Dự Án → Hub Tổng

**Central DB Schema (Sync tables):**

```sql
-- ================================================================
-- Migration: 003_sync.up.sql (Central DB)
-- ================================================================

CREATE TABLE sync_batches (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hub_id          UUID REFERENCES hubs(id) NOT NULL,
    hub_name        VARCHAR(100) NOT NULL,
    page_count      INT NOT NULL,
    -- Tổng hợp số lượng tệp theo loại (FE hiển thị badges file type)
    -- VD: {"pdf": 3, "docx": 2, "xlsx": 1, "jpg": 1}
    files_summary   JSONB DEFAULT '{}',
    -- Tổng dung lượng tất cả tệp trong batch (bytes)
    total_size      BIGINT DEFAULT 0,
    submitted_by    UUID REFERENCES users(id) NOT NULL,
    submitted_by_name VARCHAR(100) NOT NULL,
    status          VARCHAR(20) DEFAULT 'pending'
                    CHECK (status IN ('pending','processing','completed')),
    approved_count  INT DEFAULT 0,
    rejected_count  INT DEFAULT 0,
    submitted_at    TIMESTAMPTZ DEFAULT NOW(),
    completed_at    TIMESTAMPTZ
);

CREATE TABLE sync_pages (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id           UUID REFERENCES sync_batches(id) ON DELETE CASCADE,
    title              VARCHAR(500) NOT NULL,
    -- Thông tin file gốc (FE hiển thị icon + tên file + dung lượng)
    file_name          VARCHAR(500) NOT NULL,
    file_type          VARCHAR(10) NOT NULL
                       CHECK (file_type IN ('pdf','docx','txt','md','xlsx','pptx','jpg','png','csv','html')),
    file_size          BIGINT DEFAULT 0,
    content            TEXT NOT NULL,
    category           VARCHAR(100),
    tags               TEXT[],
    author             VARCHAR(100),
    status             VARCHAR(20) DEFAULT 'pending'
                       CHECK (status IN ('pending','approved','rejected')),
    rejection_reason   TEXT,
    similarity_score   FLOAT,
    similar_page_id    UUID,
    similar_page_title VARCHAR(500),
    reviewed_by        UUID REFERENCES users(id),
    reviewed_at        TIMESTAMPTZ,
    created_at         TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_sync_batches_status ON sync_batches(status);
CREATE INDEX idx_sync_batches_hub ON sync_batches(hub_id);
CREATE INDEX idx_sync_pages_batch ON sync_pages(batch_id);
CREATE INDEX idx_sync_pages_status ON sync_pages(status);
```

**Sync API:**

| Endpoint | Method | Mô Tả | Auth |
|----------|--------|--------|------|
| `/api/sync/batches` | POST | Hub Dự Án submit sync batch (UC-19) | admin_hub_du_an |
| `/api/sync/batches` | GET | List batches (filter: status, hub) | admin_hub_tong |
| `/api/sync/batches/:id` | GET | Batch detail + all pages | admin_hub_tong |
| `/api/sync/batches/:id/pages/:pid/approve` | POST | Approve page → copy to Hub Tổng + embed | admin_hub_tong |
| `/api/sync/batches/:id/pages/:pid/reject` | POST | Reject with reason (min 10 chars) | admin_hub_tong |
| `/api/sync/stats` | GET | Pending batch/page count (for sidebar badge) | admin_hub_tong |

**Approve Flow:**

```
Admin Hub Tổng clicks "Approve" on sync page
    │
    ├─► 1. Update sync_pages.status = 'approved'
    ├─► 2. Insert page into Hub Tổng wiki DB (pages table)
    ├─► 3. Enqueue "rag:reembed" (hub_code = "central")
    │       → Worker embeds page into medinet_central collection
    ├─► 4. Check if batch completed (all pages reviewed)
    │       → If yes: sync_batches.status = 'completed'
    └─► 5. Audit log: APPROVE_SYNC action
```

**Submit Sync Flow (UC-19):**

```
Admin Hub Dự Án clicks "Sync lên Hub Tổng"
    │
    ├─► 1. Select pages to sync (multiple selection)
    ├─► 2. POST /api/sync/batches
    │       { hub_id, page_ids: [...] }
    ├─► 3. Server: fetch pages from Hub DB → create sync_batch + sync_pages
    │       → Tính files_summary (count per file_type) + total_size cho batch
    ├─► 4. Auto-run duplicate detection (Phase 3):
    │       For each page: POST /api/search/similar → populate similarity_score
    └─► 5. Return batch_id
            Admin Hub Tổng sees new batch in Sync Queue
```

### 8.6 Deliverables Phase 4

- [x] DB schema: categories, tags, pages, page_tags, page_versions (migration 002_wiki)
- [x] DB schema: sync_batches, sync_pages (migration 003_sync)
- [ ] Per-Hub DB migration setup (hiện dùng central DB cho tất cả, chưa per-hub)
- [ ] Wiki pages CRUD API (schema ready, handler chưa implement)
- [ ] Page version history (schema ready)
- [ ] Page restore to specific version
- [ ] Categories CRUD (schema ready)
- [ ] Tags CRUD (schema ready)
- [ ] Cursor-based pagination
- [ ] Pre-rendered HTML cache
- [ ] Hook page CRUD → auto re-embed worker
- [x] Sync batch submit API (`POST /api/sync/batches`)
- [x] Sync review API (approve/reject with reason min 10 chars, auto-complete batch)
- [ ] Auto duplicate detection on sync submit (Phase 3 search/similar ready nhưng chưa hook)
- [x] Sync stats endpoint (`GET /api/sync/stats` — pending count for sidebar badge)
- [ ] PostgreSQL full-text search (GIN index created, chưa implement query)
- [x] FE kết nối: SyncQueue (list, filter, pagination), SyncReview (approve/reject real-time)

> **Ghi chú:** Wiki Pages CRUD chưa implement handler/service — chỉ có schema + models. Sync workflow hoạt động đầy đủ. Tất cả tables đặt trong central DB (chưa per-hub DB).

---

## 9. PHASE 5 — User Management, Audit & API Keys

### 9.1 Mục Tiêu

Full user CRUD, audit log toàn hệ thống, API key management — hoàn thiện admin features.

### 9.2 User Management API

| Endpoint | Method | Mô Tả | Auth |
|----------|--------|--------|------|
| `/api/users` | GET | List users (filter: hub, role, status, search) | admin_hub_tong |
| `/api/users` | POST | Create user + assign hub role | admin_hub_tong |
| `/api/users/:id` | GET | User detail + all hub roles | admin_hub_tong |
| `/api/users/:id` | PUT | Update user info | admin_hub_tong |
| `/api/users/:id/role` | PATCH | Change role in specific hub | admin_hub_tong |
| `/api/users/:id/status` | PATCH | Enable/Disable user | admin_hub_tong |
| `/api/users/:id/invite` | POST | Send invitation email (async) | admin_hub_tong |

### 9.3 Profile API

| Endpoint | Method | Mô Tả | Auth |
|----------|--------|--------|------|
| `/api/profile` | GET | Current user profile | JWT |
| `/api/profile` | PUT | Update own info (name, phone, department) | JWT |
| `/api/profile/password` | POST | Change password (verify old → set new) | JWT |
| `/api/profile/avatar` | POST | Upload avatar image | JWT |

**Password Change Rules:**
- Verify old password trước khi cho đổi
- New password: min 8 chars, must contain uppercase + lowercase + number + special char
- Không được trùng 5 password gần nhất (optional, Phase 6)

### 9.4 Audit Log System

**Database Schema (Partitioned by Month):**

```sql
-- ================================================================
-- Migration: 004_audit.up.sql (Central DB)
-- ================================================================

CREATE TABLE audit_logs (
    id          UUID DEFAULT gen_random_uuid(),
    timestamp   TIMESTAMPTZ DEFAULT NOW(),
    user_id     UUID,
    user_name   VARCHAR(100),
    is_ai       BOOLEAN DEFAULT FALSE,
    action      VARCHAR(50) NOT NULL,
    target      VARCHAR(255),
    hub_id      UUID,
    hub_name    VARCHAR(100),
    ip_address  INET,
    user_agent  TEXT,
    request_id  UUID,
    duration_ms INT,
    payload     JSONB,
    PRIMARY KEY (id, timestamp)
) PARTITION BY RANGE (timestamp);

-- Auto-create monthly partitions (cronjob hoặc pg_partman)
-- Example:
CREATE TABLE audit_logs_2026_04 PARTITION OF audit_logs
    FOR VALUES FROM ('2026-04-01') TO ('2026-05-01');

CREATE TABLE audit_logs_2026_05 PARTITION OF audit_logs
    FOR VALUES FROM ('2026-05-01') TO ('2026-06-01');

CREATE INDEX idx_audit_timestamp ON audit_logs(timestamp DESC);
CREATE INDEX idx_audit_action ON audit_logs(action);
CREATE INDEX idx_audit_hub ON audit_logs(hub_id);
CREATE INDEX idx_audit_user ON audit_logs(user_id);
```

**Action Types:**

| Action | Mô Tả | Triggered By |
|--------|--------|-------------|
| `LOGIN` | User đăng nhập | Auth handler |
| `LOGOUT` | User đăng xuất | Auth handler |
| `CREATE` | Tạo page/category/tag/user/hub | CRUD handlers |
| `UPDATE` | Cập nhật page/user/settings | CRUD handlers |
| `DELETE` | Xóa page/category/document | CRUD handlers |
| `SYNC` | Submit sync batch | Sync handler |
| `APPROVE_SYNC` | Approve sync page | Sync handler |
| `REJECT_SYNC` | Reject sync page | Sync handler |
| `MCP_READ` | AI Agent đọc data | MCP handler |
| `MCP_WRITE` | AI Agent tạo/sửa page | MCP handler |
| `API_KEY_CREATE` | Tạo API key | API key handler |
| `API_KEY_REVOKE` | Thu hồi API key | API key handler |
| `UPLOAD_DOC` | Upload tài liệu | Document handler |
| `EMBED_COMPLETE` | Vector hóa hoàn tất | Worker |

**Audit API:**

| Endpoint | Method | Mô Tả | Auth |
|----------|--------|--------|------|
| `/api/audit-logs` | GET | Query with filters + pagination | admin_hub_tong |
| `/api/audit-logs/export` | GET | CSV streaming export | admin_hub_tong |

**Query Parameters:**

```
GET /api/audit-logs?
    date_from=2026-04-01&
    date_to=2026-04-07&
    actor_type=user|ai&        # filter user vs AI actions
    action=CREATE,UPDATE&      # comma-separated action types
    hub_id=hub-uuid&
    page=1&
    limit=10
```

**Audit Middleware (Auto-logging):**

```go
// internal/middleware/audit.go
// Wrap mọi mutating request → ghi audit log qua Redis queue → async persist

func AuditMiddleware(auditQueue *redis.Client) gin.HandlerFunc {
    return func(c *gin.Context) {
        // Skip GET requests
        if c.Request.Method == "GET" {
            c.Next()
            return
        }
        
        start := time.Now()
        c.Next() // Execute handler
        duration := time.Since(start)
        
        // Only log successful mutations
        if c.Writer.Status() < 400 {
            entry := AuditEntry{
                UserID:    getUserID(c),
                Action:    inferAction(c),
                Target:    c.Request.URL.Path,
                HubID:     getHubID(c),
                IP:        c.ClientIP(),
                UserAgent: c.Request.UserAgent(),
                RequestID: getRequestID(c),
                Duration:  duration.Milliseconds(),
            }
            // Async write via Redis queue
            auditQueue.RPush(ctx, "audit:write", marshal(entry))
        }
    }
}
```

**CSV Export (Streaming):**

```go
// Streaming response — không load toàn bộ vào memory
func ExportAuditCSV(c *gin.Context) {
    c.Header("Content-Type", "text/csv")
    c.Header("Content-Disposition", "attachment; filename=audit_log.csv")
    
    writer := csv.NewWriter(c.Writer)
    writer.Write([]string{"Timestamp", "User", "Action", "Target", "Hub", "IP"})
    
    // Stream rows from DB
    rows, _ := repo.StreamAuditLogs(ctx, filters)
    defer rows.Close()
    
    for rows.Next() {
        entry := scanRow(rows)
        writer.Write(entry.ToCSV())
        writer.Flush() // Flush each row to client
    }
}
```

### 9.5 API Key Management

API Key tables đã tạo ở Phase 1. Phase 5 implement đầy đủ CRUD + rate limiting.

| Endpoint | Method | Mô Tả | Auth |
|----------|--------|--------|------|
| `/api/api-keys` | GET | List API keys | admin_hub_tong |
| `/api/api-keys` | POST | Create key → return plaintext ONCE | admin_hub_tong |
| `/api/api-keys/:id` | GET | Key detail (không hiện plaintext) | admin_hub_tong |
| `/api/api-keys/:id` | PUT | Update permissions, rate limit, hub access | admin_hub_tong |
| `/api/api-keys/:id/revoke` | POST | Revoke key | admin_hub_tong |
| `/api/api-keys/:id/usage` | GET | Usage metrics (today, 7d, bandwidth) | admin_hub_tong |

**API Key Format:** `mk_` prefix + 32 random bytes (base62 encoded)

```
Example: mk_7Kx9mPqR2sT4vW6yA8bC0dE3fG5hJ1k
```

**Key Security:**
- Plaintext chỉ hiển thị **1 lần** khi tạo
- Server lưu **SHA-256 hash** — không thể reverse
- Rate limiting: Token bucket algorithm via Redis (per key)
- Có thể set expiration date

### 9.6 Email Worker (Async)

```
User invitation / notification
         │
         ▼
  Redis Queue: "email:send"
  {
    "to": "newuser@medinet.vn",
    "template": "invitation",
    "data": {
      "hub_name": "Tâm Đạo Y Quán",
      "inviter_name": "Admin",
      "login_url": "https://tamdao.medinet.vn/login"
    }
  }
         │
         ▼
  Email Worker → SMTP / SendGrid API
```

### 9.7 Deliverables Phase 5

- [x] User CRUD API (list with hub/role/status/search filter, create, update, change role, change status)
- [x] Profile API (view, update name/phone/department, change password with old verify)
- [ ] Profile avatar upload (chưa implement)
- [ ] User invitation email (chưa implement — cần SMTP config)
- [x] Audit log table with monthly partitioning (migration 004_audit, 3 partitions + default)
- [ ] Audit middleware auto-log mutations (chưa implement — audit_service.Log() sẵn sàng)
- [x] Audit query API with filters + pagination (`GET /api/audit-logs`)
- [x] Audit CSV export streaming (`GET /api/audit-logs/export`)
- [x] API key CRUD API (list, get, create with `mk_` prefix + SHA-256 hash, update, revoke)
- [ ] API key rate limiting Redis token bucket (chưa implement)
- [ ] API key usage metrics tracking (schema có, chưa increment)
- [ ] Email worker SMTP integration (chưa implement)
- [ ] Audit worker async persist (hiện insert đồng bộ qua goroutine)
- [x] FE kết nối: UserManagement (CRUD, role, status), AuditLog (filters), APIKeyManagement (create/revoke), Dashboard (audit + sync stats), Profile

> **Ghi chú:** API key plaintext trả về qua field `plain_key` (không phải `plaintext_key`). Meta response luôn trả `total`/`total_pages` kể cả khi = 0.

---

## 10. PHASE 6 — MCP Server & Production Hardening

### 10.1 Mục Tiêu

AI Agent (Claude, ChatGPT) kết nối qua MCP protocol.
Hệ thống sẵn sàng deploy production.

### 10.2 MCP Server

MCP (Model Context Protocol) endpoint tại `wiki.medinet.vn/mcp`.
Reuse RAG search engine (Phase 3) + Wiki CRUD (Phase 4). Chỉ thêm MCP protocol adapter + API key auth.

| Endpoint | Method | Mô Tả | Auth |
|----------|--------|--------|------|
| `/mcp/tools` | GET | List available MCP tools | API Key |
| `/mcp/tools/wiki_search` | POST | Tìm kiếm tri thức trong 1 Hub (UC-26) | API Key (read) |
| `/mcp/tools/wiki_cross_search` | POST | Tìm kiếm xuyên Hub (UC-29) | API Key (cross-hub-search) |
| `/mcp/tools/wiki_create_page` | POST | Tạo trang wiki mới (UC-27) | API Key (write) |
| `/mcp/tools/wiki_update_page` | POST | Cập nhật trang wiki (UC-28) | API Key (write) |
| `/mcp/tools/wiki_suggest_page` | POST | Kiểm tra duplicate trước khi tạo | API Key (read) |

**MCP Auth Flow:**

```
AI Agent (Claude Desktop)
    │
    │ Header: Authorization: Bearer mk_7Kx9mPqR2sT4vW6yA8bC0dE3fG5hJ1k
    │
    ▼
MCP Middleware:
    1. Extract key from header
    2. SHA-256 hash → lookup in api_keys table
    3. Check status == 'active' && !expired
    4. Check rate limit (Redis token bucket)
    5. Check permissions (read/write/cross-hub-search)
    6. Check allowed_hub_ids
    7. Inject context → Handler
    │
    ▼
MCP Handler → Reuse existing Service layer
    - wiki_search      → rag.Searcher.Search()
    - wiki_cross_search → rag.Searcher.CrossHubSearch()
    - wiki_create_page → page.Service.Create()
    - wiki_update_page → page.Service.Update()
```

**MCP Tool Definition (cho AI client):**

```json
{
  "tools": [
    {
      "name": "wiki_search",
      "description": "Tìm kiếm tri thức trong Medinet Wiki bằng semantic search",
      "parameters": {
        "query": { "type": "string", "description": "Câu truy vấn tìm kiếm" },
        "hub_code": { "type": "string", "description": "Mã Hub (tamdao/dmd/hcns)" },
        "top_k": { "type": "integer", "default": 5 }
      }
    },
    {
      "name": "wiki_create_page",
      "description": "Tạo trang wiki mới trong Hub",
      "parameters": {
        "hub_code": { "type": "string" },
        "title": { "type": "string" },
        "content": { "type": "string", "description": "Nội dung Markdown" },
        "category": { "type": "string" },
        "tags": { "type": "array", "items": { "type": "string" } }
      }
    }
  ]
}
```

### 10.3 Settings API

```sql
-- ================================================================
-- Migration: 005_settings.up.sql (Central DB)
-- ================================================================

CREATE TABLE settings (
    key         VARCHAR(100) PRIMARY KEY,
    value       JSONB NOT NULL,
    category    VARCHAR(50) NOT NULL,    -- general, security, notifications, rag
    updated_by  UUID REFERENCES users(id),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Seed default settings
INSERT INTO settings (key, value, category) VALUES
    ('system_name', '"Medinet Wiki"', 'general'),
    ('system_url', '"https://wiki.medinet.vn"', 'general'),
    ('admin_email', '"admin@medinet.vn"', 'general'),
    ('language', '"vi"', 'general'),
    -- Dark mode giờ được quản lý client-side (localStorage key: medinet-theme)
    -- Tự detect prefers-color-scheme của OS, user toggle qua nút Moon/Sun ở header
    ('dark_mode', 'false', 'general'),
    ('two_factor_enabled', 'false', 'security'),
    ('session_timeout_minutes', '30', 'security'),
    ('ip_whitelist', '[]', 'security'),
    ('email_notifications', 'true', 'notifications'),
    ('telegram_notifications', 'false', 'notifications'),
    ('telegram_bot_token', '""', 'notifications'),
    ('telegram_chat_id', '""', 'notifications'),
    ('rag_embedding_model', '"text-embedding-3-small"', 'rag'),
    ('rag_chunk_size', '512', 'rag'),
    ('rag_chunk_overlap', '50', 'rag'),
    ('rag_batch_size', '100', 'rag');
```

| Endpoint | Method | Mô Tả | Auth |
|----------|--------|--------|------|
| `/api/settings` | GET | Get all settings (grouped by category) | admin_hub_tong |
| `/api/settings` | PUT | Update settings (partial update) | admin_hub_tong |

### 10.4 Notification Channels

| Channel | Implementation | Config |
|---------|---------------|--------|
| Email (SMTP) | Async via Redis queue → SMTP/SendGrid | `notifications.email_*` settings |
| Telegram Bot | Async via Redis queue → Telegram Bot API | `notifications.telegram_*` settings |
| In-app | SSE (Server-Sent Events) endpoint | Real-time, no config needed |

```
Events that trigger notifications:
- Sync batch submitted (→ Admin Hub Tổng)
- Sync page approved/rejected (→ Admin Hub Dự Án)
- AI Post pending review (→ Admin Hub Dự Án)
- Document processing completed/failed (→ uploader)
- New user invitation sent
```

### 10.5 Production Hardening

**Logging:**

```go
// Structured JSON logs using Go 1.22 slog
import "log/slog"

logger := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{
    Level: slog.LevelInfo,
}))

// Every request gets a unique request_id for tracing
logger.Info("search completed",
    slog.String("request_id", reqID),
    slog.String("query", query),
    slog.Int("results", len(results)),
    slog.Duration("duration", elapsed),
)
```

**Health Check:**

```
GET /health

Response:
{
  "status": "healthy",
  "services": {
    "postgres": { "status": "up", "latency_ms": 2 },
    "redis": { "status": "up", "latency_ms": 1 },
    "chromadb": { "status": "up", "latency_ms": 5 }
  },
  "version": "1.0.0",
  "uptime_seconds": 86400
}
```

**Monitoring (Prometheus + Grafana):**

```
Metrics exported at GET /metrics:

# API
http_requests_total{method, path, status}
http_request_duration_seconds{method, path}

# RAG Pipeline
rag_documents_processed_total{hub, status}
rag_embedding_duration_seconds{model}
rag_chunks_embedded_total{hub}

# Search
search_queries_total{type, hub}
search_query_duration_seconds{type}
search_cache_hits_total
search_cache_misses_total

# ChromaDB
chromadb_vectors_total{collection}
chromadb_query_duration_seconds{collection}

# Workers
worker_jobs_processed_total{queue, status}
worker_jobs_pending{queue}
```

**Dockerfile (Multi-stage):**

```dockerfile
# Build stage
FROM golang:1.22-alpine AS builder
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -o /server ./cmd/server

# Runtime stage
FROM gcr.io/distroless/static-debian12:nonroot
COPY --from=builder /server /server
COPY --from=builder /app/internal/database/migrations /migrations
USER nonroot:nonroot
EXPOSE 8080
ENTRYPOINT ["/server"]
```

**Graceful Shutdown:**

```go
// cmd/server/main.go
quit := make(chan os.Signal, 1)
signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
<-quit

ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
defer cancel()

// 1. Stop accepting new requests
server.Shutdown(ctx)
// 2. Wait for in-flight requests to complete
// 3. Drain worker queues
workerManager.Shutdown(ctx)
// 4. Close DB connections
db.Close()
redis.Close()
```

**Security Checklist (Production):**

| # | Item | Implementation |
|---|------|---------------|
| 1 | HTTPS only | Nginx terminates SSL (wildcard `*.medinet.vn`) |
| 2 | HSTS header | `Strict-Transport-Security: max-age=31536000; includeSubDomains` |
| 3 | X-Frame-Options | `DENY` — prevent clickjacking |
| 4 | X-Content-Type-Options | `nosniff` — prevent MIME sniffing |
| 5 | Content-Security-Policy | Restrict script sources |
| 6 | Rate limiting | 3 layers: global (1000 req/s) + per-IP (100 req/min) + per-user (60 req/min) |
| 7 | SQL injection | Parameterized queries only (sqlc) |
| 8 | XSS prevention | HTML sanitize wiki content (bluemonday library) |
| 9 | CORS | Strict whitelist: `*.medinet.vn` only |
| 10 | Secrets | Env vars / HashiCorp Vault — never hardcode |
| 11 | Audit trail | All mutations logged with user, IP, timestamp |
| 12 | Backup | PostgreSQL pg_dump daily + WAL archiving (point-in-time recovery) |
| 13 | Token rotation | Short-lived access tokens (15m) + refresh tokens (7d) |
| 14 | Dependency scan | `govulncheck` in CI pipeline |

### 10.6 Deliverables Phase 6

- [ ] MCP server with 5 tools (search, cross-search, create, update, suggest)
- [ ] MCP authentication via API key
- [ ] Settings CRUD API
- [ ] Email notification worker (SMTP/SendGrid)
- [ ] Telegram notification worker
- [ ] In-app notifications (SSE endpoint)
- [ ] Prometheus metrics endpoint
- [ ] Health check endpoint (all services)
- [ ] Structured logging (slog JSON)
- [ ] Graceful shutdown
- [ ] Dockerfile (multi-stage, distroless, non-root)
- [ ] Docker Compose production profile
- [ ] Security headers middleware
- [ ] Nginx configuration (subdomain routing + SSL)
- [ ] Backup script (pg_dump + WAL)
- [ ] CI/CD pipeline (build, test, lint, vulnerability scan)
- [ ] Load testing scripts (search, upload, concurrent users)

---

## 11. Tổng Kết & Roadmap

### 11.1 Phase Timeline

```
Phase 1  ████░░░░░░░░░░░░░░░░░░░░░░  Minimal Foundation
Phase 2  ░░░░████████░░░░░░░░░░░░░░░  RAG Pipeline & Vector Hóa (TRỌNG TÂM)
Phase 3  ░░░░░░░░░░░░████░░░░░░░░░░░  Semantic Search & Cross-Hub
Phase 4  ░░░░░░░░░░░░░░░░████░░░░░░░  Wiki Pages & Sync Workflow
Phase 5  ░░░░░░░░░░░░░░░░░░░░███░░░░  User Management, Audit & API Keys
Phase 6  ░░░░░░░░░░░░░░░░░░░░░░░████  MCP Server & Production
```

### 11.2 Phase Summary (Implementation Status: 2026-04-08)

| Phase | Focus | Status | BE | FE |
|-------|-------|--------|----|----|
| **Phase 1** | Minimal Foundation | **DONE** | 11 endpoints, 7 tables | Login, Dashboard, HubRegistry |
| **Phase 2** | **RAG Pipeline** | **DONE** | 6 endpoints, pipeline+worker | DocumentIngestion (upload/compose/list) |
| **Phase 3** | **Semantic Search** | **DONE** | 3 endpoints, scorer+cache | CrossHubSearch |
| **Phase 4** | Sync Workflow | **PARTIAL** | 6 sync endpoints, schema wiki | SyncQueue, SyncReview |
| **Phase 5** | Quản Trị | **DONE** | 16 endpoints | UserMgmt, AuditLog, APIKeys, Profile |
| **Phase 6** | MCP + Production | **NOT STARTED** | — | — |

**Tổng: 42 API endpoints hoạt động, 11 DB tables, 0 mock imports còn lại trên FE.**

**Chưa hoàn thành:**
- Phase 3: Hybrid search (vector + keyword FTS) — chỉ có vector search
- Phase 4: Wiki Pages CRUD (schema ready, handler chưa implement)
- Phase 4: Categories/Tags CRUD (schema ready)
- Phase 5: Avatar upload, email worker, audit middleware, API key rate limiting
- Phase 6: Toàn bộ (MCP, settings, notifications, monitoring, Docker, Nginx)

### 11.3 API Endpoint Summary

| Phase | Endpoints | Count |
|-------|-----------|-------|
| Phase 1 | Auth (3) + Hub (5) + Health (1) | 9 |
| Phase 2 | Documents (6) | 6 |
| Phase 3 | Search (3) | 3 |
| Phase 4 | Pages (7) + Categories (4) + Tags (2) + Sync (6) | 19 |
| Phase 5 | Users (7) + Profile (4) + Audit (2) + API Keys (5) | 18 |
| Phase 6 | MCP (6) + Settings (2) + Notifications (1) | 9 |
| **Total** | | **64** |

### 11.4 Database Tables Summary

| Database | Table | Phase | Purpose |
|----------|-------|-------|---------|
| Central | `hubs` | 1 | Hub registry |
| Central | `users` | 1 | User accounts |
| Central | `user_hub_roles` | 1 | RBAC per Hub |
| Central | `api_keys` | 1 | MCP/external API keys |
| Central | `revoked_tokens` | 1 | JWT blacklist |
| Central | `documents` | 1 | Document metadata |
| Central | `document_chunks` | 1 | Chunk tracking |
| Central | `sync_batches` | 4 | Sync batch queue |
| Central | `sync_pages` | 4 | Individual sync pages |
| Central | `audit_logs` (partitioned) | 5 | System audit trail |
| Central | `settings` | 6 | System configuration |
| Per-Hub | `categories` | 4 | Wiki categories (tree) |
| Per-Hub | `tags` | 4 | Wiki tags |
| Per-Hub | `pages` | 4 | Wiki pages |
| Per-Hub | `page_tags` | 4 | Page-tag junction |
| Per-Hub | `page_versions` | 4 | Version history |

---

## 12. Phụ Lục — Bảo Mật & Hiệu Năng

### 12.1 Bảo Mật Tổng Thể

| Layer | Threat | Mitigation |
|-------|--------|-----------|
| **Auth** | Brute force login | Argon2id + rate limit 5 attempts → lock 15m |
| **Auth** | Token theft | RS256 JWT, 15m expiry, refresh rotation, blacklist on logout |
| **Auth** | Cross-hub access | JWT payload contains hub_id, RBAC middleware enforces |
| **API** | SQL injection | Parameterized queries (sqlc generated) |
| **API** | XSS | HTML sanitize wiki content (bluemonday) |
| **API** | CSRF | SameSite cookie + CORS whitelist |
| **API** | Rate abuse | 3-layer: global + per-IP + per-user/key (Redis) |
| **Upload** | Malicious files | MIME validation, type whitelist (pdf,docx,txt,md,xlsx,pptx,jpg,png,csv,html), size limit, sandboxed extract |
| **Upload** | Path traversal | UUID-based paths, no user-controlled filenames |
| **Data** | DB credential leak | AES-256-GCM encryption at rest for Hub DB passwords |
| **Data** | API key leak | SHA-256 hash stored, plaintext shown once only |
| **Data** | Sensitive data access | RBAC per Hub, audit log all reads on sensitive data |
| **Network** | MITM | HTTPS only (wildcard SSL), HSTS header |
| **Network** | Clickjacking | X-Frame-Options: DENY |
| **Infra** | Container escape | Distroless image, non-root user, read-only filesystem |
| **Infra** | Dependency vulns | govulncheck in CI, automated dependency updates |

### 12.2 Hiệu Năng Tổng Thể

| Component | Optimization | Target |
|-----------|-------------|--------|
| **DB Connection** | Pool per Hub: MaxOpen=25, MaxIdle=10, MaxLifetime=5m | < 5ms query |
| **DB Query** | Cursor pagination (no OFFSET) | Constant time regardless of page |
| **DB Index** | GIN for FTS, B-tree for filters, partial indexes | < 10ms lookup |
| **DB Partition** | Audit logs monthly partition | Scan only relevant month |
| **Cache** | Redis: query embedding (1h), search results (5m) | > 60% hit rate |
| **Search** | Fan-out goroutines + 5s timeout per Hub | < 1s (3 hubs) |
| **Embedding** | Batch 100 chunks/call | 100x fewer API roundtrips |
| **Upload** | Async processing (Redis queue) | API returns in < 100ms |
| **Workers** | Configurable pool size (default 3) | Parallel document processing |
| **Content** | Pre-rendered HTML cache for wiki pages | Skip markdown rendering |
| **ChromaDB** | Per-Hub collection (smaller index) | Faster HNSW search |
| **Export** | CSV streaming (not buffer-all) | Constant memory usage |

### 12.3 Environment Variables

```bash
# .env.example

# ─────────────── Application ───────────────
APP_ENV=development                    # development | staging | production
APP_PORT=8080
APP_LOG_LEVEL=info                     # debug | info | warn | error

# ─────────────── PostgreSQL (Central) ───────────────
DB_HOST=localhost
DB_PORT=5432
DB_NAME=medinet_central
DB_USER=medinet
DB_PASSWORD=your_secure_password
DB_MAX_OPEN_CONNS=25
DB_MAX_IDLE_CONNS=10
DB_CONN_MAX_LIFETIME=5m

# ─────────────── Redis ───────────────
REDIS_URL=redis://:your_redis_password@localhost:6379/0

# ─────────────── ChromaDB ───────────────
CHROMA_URL=http://localhost:8000
CHROMA_TOKEN=your_chroma_auth_token

# ─────────────── JWT ───────────────
JWT_PRIVATE_KEY_PATH=./keys/private.pem
JWT_PUBLIC_KEY_PATH=./keys/public.pem
JWT_ACCESS_TOKEN_EXPIRY=15m
JWT_REFRESH_TOKEN_EXPIRY=168h          # 7 days

# ─────────────── Embedding ───────────────
OPENAI_API_KEY=sk-...
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_BATCH_SIZE=100

# ─────────────── RAG ───────────────
RAG_CHUNK_SIZE=512
RAG_CHUNK_OVERLAP=50
RAG_WORKER_COUNT=3
RAG_MAX_FILE_SIZE_MB=50

# ─────────────── Email (SMTP) ───────────────
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=noreply@medinet.vn
SMTP_PASSWORD=your_smtp_password
SMTP_FROM=Medinet Wiki <noreply@medinet.vn>

# ─────────────── Encryption ───────────────
AES_ENCRYPTION_KEY=32-byte-hex-key    # For Hub DB password encryption

# ─────────────── CORS ───────────────
CORS_ALLOWED_ORIGINS=https://wiki.medinet.vn,https://tamdao.medinet.vn,https://dmd.medinet.vn,https://hcns.medinet.vn
```

---

*Medinet Wiki Backend Development Plan v1.1 — Vector-First Architecture*
*Tài liệu nội bộ Medinet | 2026-04-07*
