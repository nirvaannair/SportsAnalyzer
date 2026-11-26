# Start SportsAnalyzer automatically when you log in to Windows (a Task Scheduler task).
#   Install:  powershell -ExecutionPolicy Bypass -File scripts\install-autostart.ps1
#   Remove:   powershell -ExecutionPolicy Bypass -File scripts\install-autostart.ps1 -Remove
# The task runs "Start SportsAnalyzer.cmd" for your user only, at log-on, with a short delay so
# Windows and Docker Desktop can settle. It never needs administrator rights.
param([switch]$Remove)

$name = 'SportsAnalyzer'
$root = Split-Path $PSScriptRoot -Parent
if ($Remove) {
    Unregister-ScheduledTask -TaskName $name -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "Removed the '$name' log-on task."
    return
}
$python = Join-Path $root '.venv\Scripts\python.exe'
$delay = & $python -c "from backend.core.settings import cfg; print(cfg('startup.autostart_delay_seconds'))"
$action = New-ScheduledTaskAction -Execute (Join-Path $root 'Start SportsAnalyzer.cmd') -WorkingDirectory $root
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$trigger.Delay = "PT$([int]$delay)S"
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger -Settings $settings `
    -Description 'Starts the SportsAnalyzer database, API and dashboard at log-on.' -Force | Out-Null
Write-Host "Installed: SportsAnalyzer will start $delay seconds after you log in. Remove with -Remove."
