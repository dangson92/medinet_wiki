@echo off
chcp 65001 >nul
echo ============================================
echo   Medinet Wiki Backend — Windows Setup
echo ============================================
echo.

:: ─── Check Go ───
echo [1/6] Checking Go...
where go >nul 2>&1
if %errorlevel% neq 0 (
    echo   FAIL: Go is not installed. Download from https://go.dev/dl/
    echo   Install Go 1.22+ and restart this script.
    pause
    exit /b 1
)
for /f "tokens=3" %%v in ('go version') do echo   OK: %%v
echo.

:: ─── Check PostgreSQL ───
echo [2/6] Checking PostgreSQL...
where psql >nul 2>&1
if %errorlevel% neq 0 (
    echo   FAIL: psql not found. Install PostgreSQL 16 from https://www.postgresql.org/download/windows/
    echo   Make sure to add PostgreSQL bin directory to PATH.
    pause
    exit /b 1
)
pg_isready -h localhost -p 5432 >nul 2>&1
if %errorlevel% neq 0 (
    echo   FAIL: PostgreSQL is not running on localhost:5432
    echo   Start PostgreSQL service from Windows Services.
    pause
    exit /b 1
)
echo   OK: PostgreSQL is running
echo.

:: ─── Check Redis ───
echo [3/6] Checking Redis...
where redis-cli >nul 2>&1 || where memurai-cli >nul 2>&1
if %errorlevel% neq 0 (
    echo   WARNING: Redis/Memurai CLI not found.
    echo   Install Memurai from https://www.memurai.com/get-memurai
    echo   Or use Redis via WSL2.
    echo   Continuing anyway...
) else (
    echo   OK: Redis CLI found
)
echo.

:: ─── Check ChromaDB ───
echo [4/6] Checking ChromaDB...
curl -sf http://localhost:8000/api/v1/heartbeat >nul 2>&1
if %errorlevel% neq 0 (
    echo   WARNING: ChromaDB is not running on localhost:8000
    echo   Install: pip install chromadb
    echo   Run:     chroma run --host localhost --port 8000
    echo   Continuing anyway (needed for Phase 2)...
) else (
    echo   OK: ChromaDB is running
)
echo.

:: ─── Create Database ───
echo [5/6] Creating database...
set /p PG_PASSWORD="Enter PostgreSQL superuser (postgres) password: "

:: Create user medinet
psql -h localhost -U postgres -c "CREATE USER medinet WITH PASSWORD 'change_me_in_production';" 2>nul
if %errorlevel% equ 0 (
    echo   Created user: medinet
) else (
    echo   User 'medinet' may already exist — skipping
)

:: Create database
psql -h localhost -U postgres -c "CREATE DATABASE medinet_central OWNER medinet;" 2>nul
if %errorlevel% equ 0 (
    echo   Created database: medinet_central
) else (
    echo   Database 'medinet_central' may already exist — skipping
)

:: Grant privileges
psql -h localhost -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE medinet_central TO medinet;" 2>nul
echo   Privileges granted
echo.

:: ─── Generate JWT Keys ───
echo [6/6] Generating JWT keys...
if not exist "keys" mkdir keys
if exist "keys\private.pem" (
    echo   Keys already exist in keys/ — skipping
) else (
    where openssl >nul 2>&1
    if %errorlevel% neq 0 (
        echo   WARNING: openssl not found. Use Git Bash to run:
        echo     bash scripts/generate_keys.sh
    ) else (
        openssl genrsa -out keys\private.pem 2048
        openssl rsa -in keys\private.pem -pubout -out keys\public.pem
        echo   OK: JWT keys generated in keys/
    )
)
echo.

:: ─── Install Go Dependencies ───
echo Installing Go dependencies...
cd /d "%~dp0.."
go mod tidy
echo.

:: ─── Done ───
echo ============================================
echo   Setup complete!
echo ============================================
echo.
echo Next steps:
echo   1. Copy .env.example to .env and fill in passwords
echo   2. Start Redis (Memurai) if not running
echo   3. Start ChromaDB: chroma run --host localhost --port 8000
echo   4. Run: make seed  (seed initial data)
echo   5. Run: make dev   (start the server)
echo   6. Test: curl http://localhost:8080/health
echo.
pause
