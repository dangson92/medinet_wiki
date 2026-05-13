Write-Host "================================" -ForegroundColor Cyan
Write-Host "  Medinet Wiki Backend Server"   -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
Write-Host ""

# Ensure Go + Python Scripts in PATH
$chromaScripts = Join-Path $env:APPDATA "Python\Python313\Scripts"
$env:Path += ";C:\Program Files\Go\bin;C:\Program Files\PostgreSQL\18\bin;$chromaScripts"

# Load .env file — robust parsing
$envFile = Join-Path $PSScriptRoot ".env"
if (Test-Path $envFile) {
    $envCount = 0
    foreach ($line in (Get-Content $envFile -Encoding UTF8)) {
        $line = $line.Trim()
        if ($line -eq "" -or $line.StartsWith("#")) { continue }
        $eqIdx = $line.IndexOf("=")
        if ($eqIdx -gt 0) {
            $key = $line.Substring(0, $eqIdx).Trim()
            $val = $line.Substring($eqIdx + 1).Trim()
            [System.Environment]::SetEnvironmentVariable($key, $val, "Process")
            $envCount++
        }
    }
    Write-Host "Loaded .env file ($envCount vars)" -ForegroundColor Green
} else {
    Write-Host "WARNING: .env file not found!" -ForegroundColor Yellow
    exit 1
}

# Override CORS for dev
$env:CORS_ALLOWED_ORIGINS = "http://localhost:5173,http://localhost:5174,http://localhost:3000,http://192.168.0.113:3000,http://192.168.0.113:5173"

# Kill process on same port if exists
$port = $env:APP_PORT
$conn = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
if ($conn) {
    Write-Host "Port $port is busy - killing old process..." -ForegroundColor Yellow
    $conn | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
    Start-Sleep -Seconds 1
}

# Start ChromaDB if not running
$chromaRunning = $false
try {
    $null = Invoke-WebRequest -Uri "http://localhost:8000/api/v2/heartbeat" -TimeoutSec 2 -ErrorAction Stop
    $chromaRunning = $true
} catch {}

if (-not $chromaRunning) {
    Write-Host "Starting ChromaDB..." -ForegroundColor Yellow
    $chromaExe = Join-Path $chromaScripts "chroma.exe"
    if (Test-Path $chromaExe) {
        Start-Process -FilePath $chromaExe -ArgumentList "run","--host","localhost","--port","8000","--path","./chroma_data" -WindowStyle Hidden
        Start-Sleep -Seconds 4
        Write-Host "ChromaDB started on http://localhost:8000" -ForegroundColor Green
    } else {
        Write-Host "ChromaDB not found at $chromaExe - skipping" -ForegroundColor Yellow
    }
} else {
    Write-Host "ChromaDB already running" -ForegroundColor Green
}

# Show config summary
Write-Host ""
Write-Host ("Environment: " + $env:APP_ENV)
Write-Host ("Server:      http://localhost:" + $port)
Write-Host ("Database:    " + $env:DB_NAME + "@" + $env:DB_HOST + ":" + $env:DB_PORT)
Write-Host ("ChromaDB:    " + $env:CHROMA_URL)
Write-Host ("Embedding:   " + $env:RAG_EMBEDDING_PROVIDER + " / " + $env:RAG_EMBEDDING_MODEL)
Write-Host ("Storage:     " + $env:STORAGE_PROVIDER)
Write-Host ""

go run ./cmd/server
