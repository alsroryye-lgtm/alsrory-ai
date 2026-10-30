$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$nodeDir = Join-Path $Root "tools\node"
$env:PATH = "$nodeDir;$env:PATH"
$venvPy = Join-Path $Root ".venv\Scripts\python.exe"

if (-not (Test-Path $venvPy)) {
    Write-Host "Run .\scripts\setup.ps1 first." -ForegroundColor Red
    exit 1
}

New-Item -ItemType Directory -Force -Path "data" | Out-Null
$outLog = Join-Path $Root "data\api.log"
$errLog = Join-Path $Root "data\api.err.log"

Write-Host "Starting API on http://127.0.0.1:8787 ..." -ForegroundColor Cyan
$api = Start-Process -FilePath $venvPy `
    -ArgumentList "-m","uvicorn","app.main:app","--host","127.0.0.1","--port","8787","--app-dir","services/api" `
    -WorkingDirectory $Root `
    -RedirectStandardOutput $outLog `
    -RedirectStandardError $errLog `
    -PassThru `
    -WindowStyle Hidden

$api.Id | Out-File -Encoding ascii "data\api.pid"

$ready = $false
for ($i = 0; $i -lt 40; $i++) {
    Start-Sleep -Milliseconds 500
    try {
        $health = Invoke-RestMethod "http://127.0.0.1:8787/api/health" -TimeoutSec 2
        if ($health.ok) { $ready = $true; break }
    } catch { }
}
if ($ready) {
    Write-Host "API ready. Engine: $($health.default_engine)" -ForegroundColor Green
} else {
    Write-Host "API did not answer. Check data\api.err.log" -ForegroundColor Red
    Get-Content $errLog -Tail 20
}

Start-Job -ScriptBlock {
    Start-Sleep -Seconds 10
    Start-Process "http://localhost:3000"
} | Out-Null

Push-Location "apps\web"
Write-Host "Starting web on http://localhost:3000 ..." -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop both." -ForegroundColor DarkGray
try {
    & (Join-Path $nodeDir "npm.cmd") run dev
} finally {
    Pop-Location
    if (-not $api.HasExited) {
        Stop-Process -Id $api.Id -Force -ErrorAction SilentlyContinue
    }
    Remove-Item "data\api.pid" -ErrorAction SilentlyContinue
    Write-Host "Stopped." -ForegroundColor DarkGray
}
