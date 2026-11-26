# Stop the SportsAnalyzer API and dashboard (and any scrape/training they started).
# The database keeps running in Docker; add -Database to stop it too.
# Ports come from [startup] in config/settings.toml.
param([switch]$Database)

$root = $PSScriptRoot
Set-Location $root
$python = Join-Path $root '.venv\Scripts\python.exe'
$s = (& $python -c "import json; from backend.core.settings import cfg; print(json.dumps(cfg('startup')))") | ConvertFrom-Json

foreach ($port in $s.api_port, $s.dashboard_port) {
    $owners = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($id in $owners) {
        taskkill /PID $id /T /F *> $null
        Write-Host "Stopped the process on port $port"
    }
}
# uvicorn's parent process and the PowerShell windows the start script opened
Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='powershell.exe'" |
    Where-Object { $_.CommandLine -match 'backend\.api\.main|backend\.scraping\.run|backend\.training|SportsAnalyzer (API|dashboard)' } |
    ForEach-Object { taskkill /PID $_.ProcessId /T /F *> $null }

if ($Database) {
    docker compose stop db
    Write-Host "Stopped the database"
}
Write-Host "Done. A running scrape resumes by itself next time (pages are cached)."
Start-Sleep -Seconds $s.poll_seconds
