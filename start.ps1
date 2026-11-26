# Start everything SportsAnalyzer needs, then open the dashboard.
#   Double-click "Start SportsAnalyzer.cmd" (or the desktop shortcut) to run this.
# Safe to run again: anything already running is left alone.
# Waits and ports come from [startup] in config/settings.toml.

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$venv = Join-Path $root '.venv\Scripts'
Set-Location $root

function Step($text) { Write-Host "`n> $text" -ForegroundColor Cyan }
function Done($text) { Write-Host "  $text" -ForegroundColor Green }
function Listening($port) { [bool](Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue) }
function Fail($text) {
    Write-Host "`n  $text" -ForegroundColor Red
    Read-Host "`nPress Enter to close"
    exit 1
}

Write-Host "SportsAnalyzer start-up" -ForegroundColor White

# 0. One-time setup checks
if (-not (Test-Path (Join-Path $venv 'python.exe'))) { Fail "No Python environment (.venv) here. See README > Easy guide > One-time setup." }
if (-not (Test-Path (Join-Path $root '.env'))) { Fail "No .env file here. Copy .env.example to .env and fill it in." }
if (-not (Test-Path (Join-Path $root 'frontend\node_modules'))) {
    Step "Installing dashboard packages (first run only)"
    npm --prefix frontend ci
}

# Settings (single source: config/settings.toml + your Settings-page changes)
$json = & (Join-Path $venv 'python.exe') -c "import json; from backend.core.settings import cfg; print(json.dumps(cfg('startup')))"
if ($LASTEXITCODE -ne 0) { Fail "Could not read config/settings.toml (see the error above)." }
$s = $json | ConvertFrom-Json
$apiPort = [int]$s.api_port
$webPort = [int]$s.dashboard_port

function WaitFor([scriptblock]$ready, [int]$seconds) {
    $deadline = (Get-Date).AddSeconds($seconds)
    while (-not (& $ready) -and (Get-Date) -lt $deadline) { Start-Sleep -Seconds $s.poll_seconds }
    return (& $ready)
}

function StartDashboard($style) {
    $web = "`$host.UI.RawUI.WindowTitle = 'SportsAnalyzer dashboard'; Set-Location '$root'; `$env:SA_DASHBOARD_PORT = '$webPort'; `$env:SA_API_PORT = '$apiPort'; npm --prefix frontend run dev"
    Start-Process powershell -ArgumentList '-NoExit', '-Command', $web -WindowStyle $style
}

# 1. Docker Desktop (runs the database)
Step "Docker Desktop"
docker info *> $null
if ($LASTEXITCODE -ne 0) {
    $docker = Join-Path $env:ProgramFiles 'Docker\Docker\Docker Desktop.exe'
    if (-not (Test-Path $docker)) { Fail "Docker Desktop is not installed." }
    Start-Process $docker
    Write-Host "  Starting Docker Desktop (this can take a minute)..."
    $up = WaitFor { docker info *> $null; $LASTEXITCODE -eq 0 } $s.docker_wait_seconds
    if (-not $up) { Fail "Docker Desktop did not start. Open it by hand, then run this again." }
}
Done "running"

# 2. Database
Step "Database (Postgres in Docker)"
docker compose up -d --wait db
if ($LASTEXITCODE -ne 0) { Fail "The database container did not start. Check Docker Desktop." }
Done "running"

# 3. Database migrations (adds any new tables)
Step "Database migrations"
& (Join-Path $venv 'alembic.exe') upgrade head
if ($LASTEXITCODE -ne 0) { Fail "Migrations failed (see above)." }
Done "up to date"

# 4. API server (also runs automation, the collector and the always-on scraper)
Step "API server"
if (Listening $apiPort) {
    Done "already running on port $apiPort"
} else {
    $api = "`$host.UI.RawUI.WindowTitle = 'SportsAnalyzer API'; Set-Location '$root'; & '$venv\uvicorn.exe' backend.api.main:app --port $apiPort"
    Start-Process powershell -ArgumentList '-NoExit', '-Command', $api -WindowStyle Minimized
    Done "starting (minimised window 'SportsAnalyzer API')"
}

# 5. Dashboard
Step "Dashboard"
if (Listening $webPort) {
    Done "already running on port $webPort"
} else {
    StartDashboard 'Minimized'
    Done "starting (minimised window 'SportsAnalyzer dashboard')"
}

# 6. Wait until both answer (retry the dashboard in a visible window if needed), then open the browser
Step "Waiting for everything to answer"
if (-not (WaitFor { Listening $apiPort } $s.services_wait_seconds)) {
    Fail "The API did not start. Open the 'SportsAnalyzer API' window to see why."
}
$tries = 0
while (-not (WaitFor { Listening $webPort } $s.services_wait_seconds)) {
    if ($tries -ge $s.dashboard_retries) { Fail "The dashboard did not start. Look at the 'SportsAnalyzer dashboard' window for the error." }
    $tries++
    Write-Host "  The dashboard didn't answer; starting it again in a visible window..." -ForegroundColor Yellow
    Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" |
        Where-Object { $_.CommandLine -match 'SportsAnalyzer dashboard' } |
        ForEach-Object { taskkill /PID $_.ProcessId /T /F *> $null }
    StartDashboard 'Normal'
}
Done "ready"

Start-Process "http://localhost:$webPort"
Write-Host "`nAll running. The dashboard is open in your browser." -ForegroundColor Green
Write-Host "For Stake: open Chrome with the SportsAnalyzer Stake Helper extension and a logged-in stake.com tab."
Write-Host "To stop everything: double-click 'Stop SportsAnalyzer'."
Start-Sleep -Seconds $s.close_after_seconds
