.PHONY: dev build run test migrate seed keys clean lint deps setup-check db-create help

# ─── Development ───
dev:
	@echo "Starting development server..."
	go run ./cmd/server

build:
	@echo "Building binary..."
	CGO_ENABLED=0 go build -ldflags="-s -w" -o bin/server.exe ./cmd/server

run: build
	./bin/server.exe

# ─── Database ───
migrate:
	@echo "Running migrations..."
	go run ./cmd/server migrate

seed:
	@echo "Seeding database..."
	@echo "Using DB_HOST=$(DB_HOST) DB_NAME=$(DB_NAME) DB_USER=$(DB_USER)"
	set PGPASSWORD=$(DB_PASSWORD) && psql -h $(DB_HOST) -U $(DB_USER) -d $(DB_NAME) -f scripts/seed.sql

db-create:
	@echo "Creating database and user..."
	psql -h localhost -U postgres -c "CREATE USER medinet WITH PASSWORD 'change_me_in_production';" || echo "User may already exist"
	psql -h localhost -U postgres -c "CREATE DATABASE medinet_central OWNER medinet;" || echo "Database may already exist"
	psql -h localhost -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE medinet_central TO medinet;"
	@echo "Database created successfully!"

# ─── Setup ───
setup-check:
	@echo "=== Checking services ==="
	@echo "--- PostgreSQL ---"
	@pg_isready -h localhost -p 5432 && echo "  OK: PostgreSQL is running" || echo "  FAIL: PostgreSQL is not running"
	@echo "--- Redis ---"
	@redis-cli -h localhost ping 2>NUL && echo "  OK: Redis is running" || echo "  FAIL: Redis is not running (try Memurai or WSL)"
	@echo "--- ChromaDB ---"
	@curl -sf http://localhost:8000/api/v1/heartbeat >NUL 2>&1 && echo "  OK: ChromaDB is running" || echo "  FAIL: ChromaDB is not running (pip install chromadb && chroma run)"
	@echo "--- Go ---"
	@go version 2>NUL && echo "  OK: Go is installed" || echo "  FAIL: Go is not installed"
	@echo "=== Done ==="

# ─── Keys ───
keys:
	@echo "Generating RSA keypair..."
	bash scripts/generate_keys.sh

# ─── Testing ───
test:
	go test ./... -v -count=1

test-coverage:
	go test ./... -coverprofile=coverage.out
	go tool cover -html=coverage.out

# ─── Linting ───
lint:
	golangci-lint run ./...

# ─── Cleanup ───
clean:
	rm -rf bin/
	rm -f coverage.out

# ─── Dependencies ───
deps:
	go mod tidy
	go mod download

# ─── Help ───
help:
	@echo "Available targets:"
	@echo "  dev           - Run development server"
	@echo "  build         - Build binary (bin/server.exe)"
	@echo "  run           - Build and run binary"
	@echo "  setup-check   - Check if PostgreSQL, Redis, ChromaDB are running"
	@echo "  db-create     - Create medinet_central database and user"
	@echo "  migrate       - Run database migrations"
	@echo "  seed          - Seed database with initial data"
	@echo "  keys          - Generate RSA keypair for JWT"
	@echo "  test          - Run all tests"
	@echo "  test-coverage - Run tests with coverage report"
	@echo "  lint          - Run linter"
	@echo "  clean         - Clean build artifacts"
	@echo "  deps          - Tidy and download Go dependencies"
