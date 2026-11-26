# Put "SportsAnalyzer" start/stop shortcuts on the Windows desktop. Run once:
#   powershell -ExecutionPolicy Bypass -File scripts\create-desktop-shortcut.ps1
$root = Split-Path $PSScriptRoot -Parent
$desktop = [Environment]::GetFolderPath('Desktop')
$shell = New-Object -ComObject WScript.Shell

foreach ($item in @(
    @{ Name = 'SportsAnalyzer'; Target = 'Start SportsAnalyzer.cmd'; Icon = 'imageres.dll,1'; About = 'Start the database, API and dashboard' },
    @{ Name = 'Stop SportsAnalyzer'; Target = 'Stop SportsAnalyzer.cmd'; Icon = 'imageres.dll,93'; About = 'Stop the API and dashboard' }
)) {
    $link = $shell.CreateShortcut((Join-Path $desktop "$($item.Name).lnk"))
    $link.TargetPath = Join-Path $root $item.Target
    $link.WorkingDirectory = $root
    $link.IconLocation = "$env:SystemRoot\System32\$($item.Icon)"
    $link.Description = $item.About
    $link.Save()
    Write-Host "Created desktop shortcut '$($item.Name)' -> $($link.TargetPath)"
}
