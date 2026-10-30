$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host ""
Write-Host "  alsrory.AI - setup" -ForegroundColor Magenta
Write-Host "  ------------------" -ForegroundColor DarkGray

# ---------------------------------------------------------------- Python 3.10
$pyExe = $null
try {
    $pyExe = (& py -3.10 -c "import sys; print(sys.executable)") 2>$null
} catch { $pyExe = $null }

if (-not $pyExe -or -not (Test-Path $pyExe)) {
    $fallback = "C:\Users\$env:USERNAME\AppData\Local\Programs\Python\Python310\python.exe"
    if (Test-Path $fallback) { $pyExe = $fallback }
}

if (-not $pyExe -or -not (Test-Path $pyExe)) {
    Write-Host "Python 3.10 not found." -ForegroundColor Red
    Write-Host "Install it from https://www.python.org/downloads/release/python-31011/ (check 'Add to PATH')."
    exit 1
}

Write-Host "[1/5] Python: $pyExe" -ForegroundColor Cyan
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    & $pyExe -m venv .venv
}
$venvPy = Join-Path $Root ".venv\Scripts\python.exe"
& $venvPy -m pip install --upgrade pip --quiet
& $venvPy -m pip install -r "services\api\requirements.txt" --quiet
if ($LASTEXITCODE -ne 0) { throw "pip install failed" }
Write-Host "      dependencies installed" -ForegroundColor DarkGray

# ---------------------------------------------------------------- Node portable
$nodeDir = Join-Path $Root "tools\node"
$nodeExe = Join-Path $nodeDir "node.exe"
if (-not (Test-Path $nodeExe)) {
    Write-Host "[2/5] Downloading portable Node.js..." -ForegroundColor Cyan
    New-Item -ItemType Directory -Force -Path (Join-Path $Root "tools") | Out-Null
    $index = Invoke-RestMethod "https://nodejs.org/dist/index.json"
    $lts = $index | Where-Object { $_.lts -ne $false } | Select-Object -First 1
    if (-not $lts) { throw "Could not resolve the latest Node.js LTS" }
    $zipUrl = "https://nodejs.org/dist/$($lts.version)/node-$($lts.version)-win-x64.zip"
    $zipPath = Join-Path $env:TEMP "alsrory-node.zip"
    Write-Host "      $($lts.version)  $zipUrl" -ForegroundColor DarkGray
    Invoke-WebRequest $zipUrl -OutFile $zipPath
    $extract = Join-Path $env:TEMP "alsrory-node"
    if (Test-Path $extract) { Remove-Item $extract -Recurse -Force }
    Expand-Archive $zipPath -DestinationPath $extract -Force
    $inner = Get-ChildItem $extract -Directory | Select-Object -First 1
    Move-Item $inner.FullName $nodeDir
    Remove-Item $zipPath -Force
}
$env:PATH = "$nodeDir;$env:PATH"
Write-Host "[2/5] Node: $(& node --version)" -ForegroundColor Cyan

# ---------------------------------------------------------------- Web deps
Write-Host "[3/5] Installing web dependencies (npm)..." -ForegroundColor Cyan
Push-Location "apps\web"
if (-not (Test-Path "node_modules")) {
    & (Join-Path $nodeDir "npm.cmd") install --no-audit --no-fund
    if ($LASTEXITCODE -ne 0) { Pop-Location; throw "npm install failed" }
} else {
    Write-Host "      node_modules already present" -ForegroundColor DarkGray
}
Pop-Location

# ---------------------------------------------------------------- Env + data
Write-Host "[4/5] Preparing .env and data folders..." -ForegroundColor Cyan
$envFile = "services\api\.env"
if (-not (Test-Path $envFile)) {
    Copy-Item "services\api\.env.example" $envFile
    Write-Host "      created services\api\.env" -ForegroundColor DarkGray
}
New-Item -ItemType Directory -Force -Path "data\assets", "data\thumbnails", "data\exports" | Out-Null

# ---------------------------------------------------------------- Self check
Write-Host "[5/5] Self check..." -ForegroundColor Cyan
& $venvPy -c "import fastapi, uvicorn, PIL, imageio_ffmpeg; import sys; sys.path.insert(0, 'services/api'); import app.main; print('      API module OK')"

Write-Host ""
Write-Host "  Setup complete." -ForegroundColor Green
Write-Host "  Run:  .\scripts\run.ps1" -ForegroundColor White
Write-Host "  Open: http://localhost:3000" -ForegroundColor White
Write-Host ""
