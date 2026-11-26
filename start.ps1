# Start everything SportsAnalyzer needs, then open the dashboard.
#   Double-click "Start SportsAnalyzer.cmd" (or the desktop shortcut) to run this.
# Safe to run again: anything already running is left alone.

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
if (-not (Test-Path (Join-Path $venv 'python.exe'))) { Fail "No Python environment (.venv) here. See README > Running it locally > One-time setup." }
if (-not (Test-Path (Join-Path $root '.env'))) { Fail "No .env file here. Copy .env.example to .env and fill it in." }
if (-not (Test-Path (Join-Path $root 'frontend\node_modules'))) {
    Step "Installing dashboard packages (first run only)"
    npm --prefix frontend ci
}

# 1. Docker Desktop (runs the database)
Step "Docker Desktop"
docker info *> $null
if ($LASTEXITCODE -ne 0) {
    $docker = Join-Path $env:ProgramFiles 'Docker\Docker\Docker Desktop.exe'
    if (-not (Test-Path $docker)) { Fail "Docker Desktop is not installed." }
    Start-Process $docker
    Write-Host "  Starting Docker Desktop (this can take a minute)..."
    $deadline = (Get-Date).AddMinutes(4)
    do {
        Start-Sleep -Seconds 3
        docker info *> $null
    } until ($LASTEXITCODE -eq 0 -or (Get-Date) -gt $deadline)
    if ($LASTEXITCODE -ne 0) { Fail "Docker Desktop did not start. Open it by hand, then run this again." }
}
Done "running"

# 2. Database
Step "Database (Postgres in Docker)"
docker compose up -d --wait db
if ($LASTEXITCODE -ne 0) { Fail "The database container did not start. Check Docker Desktop." }
Done "running on localhost:5433"

# 3. Database migrations (adds any new tables)
Step "Database migrations"
& (Join-Path $venv 'alembic.exe') upgrade head
if ($LASTEXITCODE -ne 0) { Fail "Migrations failed (see above)." }
Done "up to date"

# 4. API server (also runs automation, the collector and the always-on scraper)
Step "API server"
if (Listening 8000) {
    Done "already running on port 8000"
} else {
    $api = "`$host.UI.RawUI.WindowTitle = 'SportsAnalyzer API'; Set-Location '$root'; & '$venv\uvicorn.exe' backend.api.main:app --port 8000"
    Start-Process powershell -ArgumentList '-NoExit', '-Command', $api -WindowStyle Minimized
    Done "starting (minimised window 'SportsAnalyzer API')"
}

# 5. Dashboard
Step "Dashboard"
if (Listening 5173) {
    Done "already running on port 5173"
} else {
    $web = "`$host.UI.RawUI.WindowTitle = 'SportsAnalyzer dashboard'; Set-Location '$root'; npm --prefix frontend run dev"
    Start-Process powershell -ArgumentList '-NoExit', '-Command', $web -WindowStyle Minimized
    Done "starting (minimised window 'SportsAnalyzer dashboard')"
}

# 6. Wait until both answer, then open the browser
Step "Waiting for everything to answer"
$deadline = (Get-Date).AddSeconds(90)
while (-not ((Listening 8000) -and (Listening 5173)) -and (Get-Date) -lt $deadline) { Start-Sleep -Seconds 1 }
if (-not (Listening 8000)) { Fail "The API did not start. Open the 'SportsAnalyzer API' window to see why." }
if (-not (Listening 5173)) { Fail "The dashboard did not start. Open the 'SportsAnalyzer dashboard' window to see why." }
Done "ready"

Start-Process 'http://localhost:5173'
Write-Host "`nAll running. The dashboard is open in your browser." -ForegroundColor Green
Write-Host "For Stake: open Chrome with the SportsAnalyzer Stake Helper extension and a logged-in stake.com tab."
Write-Host "To stop everything: double-click 'Stop SportsAnalyzer.cmd'."
Start-Sleep -Seconds 6
