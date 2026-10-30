$Root = Split-Path -Parent $PSScriptRoot
$pidFile = Join-Path $Root "data\api.pid"

if (Test-Path $pidFile) {
    $apiPid = Get-Content $pidFile | Select-Object -First 1
    if ($apiPid) {
        Stop-Process -Id ([int]$apiPid) -Force -ErrorAction SilentlyContinue
        Write-Host "Stopped API (PID $apiPid)" -ForegroundColor DarkGray
    }
    Remove-Item $pidFile -ErrorAction SilentlyContinue
}

foreach ($port in @(3000, 8787)) {
    $connections = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    foreach ($connection in $connections) {
        Stop-Process -Id $connection.OwningProcess -Force -ErrorAction SilentlyContinue
        Write-Host "Freed port $port" -ForegroundColor DarkGray
    }
}
Write-Host "Done." -ForegroundColor Green
