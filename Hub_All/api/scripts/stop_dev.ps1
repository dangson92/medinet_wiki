# stop_dev.ps1 — tat uvicorn dev server. Goi qua `npm run backend:down`.
# Windows-only.
#
# Vi sao khong chi loc 'app.main:app' trong command line: uvicorn --reload
# tren Windows spawn worker qua Python multiprocessing -> command line worker
# la boilerplate 'spawn_main ... --multiprocessing-fork', KHONG chua chuoi
# 'app.main:app'. Nhung worker moi la process THUC SU giu cong 8080/8180.
#
# Vi vay gom MUC TIEU tu 2 nguon:
#   1. Process co 'app.main:app' trong command line (uv / uvicorn / reloader).
#   2. Process giu cong dev (8080/8180) VA process con cua chu socket. Khi
#      reloader bi kill truoc, worker con ke thua socket nhung
#      Get-NetTCPConnection van bao OwningProcess = PID reloader DA CHET ->
#      phai tim process con cua PID do (worker orphan).
#
# Kill bang `taskkill /F /T` (diet ca cay con) -> kill reloader keo theo
# worker, khong tao orphan. Lap lai vai vong de bat respawn/orphan con sot.

$ErrorActionPreference = 'SilentlyContinue'
$ports = 8080, 8180

function Get-Targets {
    $ids = @()
    # (1) command line chua 'app.main:app' — CHI process python/uvicorn/uv.
    #     Loc theo Name de KHONG kill nham editor/terminal/script khac dang
    #     mo file co chuoi 'app.main:app' tren command line cua no.
    $ids += @(Get-CimInstance Win32_Process |
        Where-Object { $_.Name -match '^(python|uvicorn|uv)' -and
            $_.CommandLine -like '*app.main:app*' } |
        ForEach-Object { [int]$_.ProcessId })
    # (2) chu cong dev + process con cua no (bat worker --reload)
    foreach ($pt in $ports) {
        foreach ($conn in @(Get-NetTCPConnection -LocalPort $pt -State Listen)) {
            $op = [int]$conn.OwningProcess
            if ($op -le 4) { continue }
            if (Get-Process -Id $op) { $ids += $op }
            $ids += @(Get-CimInstance Win32_Process -Filter "ParentProcessId = $op" |
                Where-Object { $_.Name -match 'python|uvicorn' } |
                ForEach-Object { [int]$_.ProcessId })
        }
    }
    return @($ids | Sort-Object -Unique)
}

$found = $false
for ($i = 0; $i -lt 8; $i++) {
    $targets = Get-Targets
    if ($targets.Count -eq 0) { break }
    $found = $true
    foreach ($procId in $targets) {
        taskkill /F /T /PID $procId 2>$null | Out-Null
    }
    Start-Sleep -Milliseconds 350
}

$left = Get-Targets
if ($left.Count -gt 0) {
    Write-Host ('backend:down -CANH BAO: van con process ' + ($left -join ', ') +
        '. Chay lai `npm run backend:down` hoac kiem tra Task Manager.')
    exit 1
}
if ($found) {
    Write-Host 'backend:down -da tat backend.'
} else {
    Write-Host 'backend:down -khong co backend nao dang chay.'
}
exit 0
