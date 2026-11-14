# Install this portable copy for the current user.
#
# Normally run by double-clicking "Install shortcuts.cmd", which calls this.
#
#   powershell -ExecutionPolicy Bypass -File install-local.ps1 -Launch
#   powershell -ExecutionPolicy Bypass -File install-local.ps1 -Uninstall

param(
    [switch]$Launch,
    [switch]$Uninstall
)

$ErrorActionPreference = 'Stop'
$source = (Resolve-Path $PSScriptRoot).Path
$target = Join-Path $env:LOCALAPPDATA 'Programs\GhostHand'
$exeName = 'GhostHand.exe'
$shortcutName = 'Ghost Hand.lnk'
$startMenu = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs'
$desktop = [Environment]::GetFolderPath('Desktop')
$runKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'

function Remove-Shortcut([string]$path) {
    if (Test-Path $path) { Remove-Item $path -Force -ErrorAction SilentlyContinue }
}

if ($Uninstall) {
    Remove-Shortcut (Join-Path $startMenu $shortcutName)
    Remove-Shortcut (Join-Path $desktop $shortcutName)
    Remove-ItemProperty -Path $runKey -Name 'GhostHand' -ErrorAction SilentlyContinue
    Remove-ItemProperty -Path $runKey -Name 'RealSenseGestureControl' -ErrorAction SilentlyContinue
    Get-Process -Name 'GhostHand' -ErrorAction SilentlyContinue | Stop-Process -Force
    if (Test-Path $target) { Remove-Item -Recurse -Force $target -ErrorAction SilentlyContinue }
    Write-Host "Removed $target" -ForegroundColor Green
    exit 0
}

if (-not (Test-Path (Join-Path $source $exeName))) {
    throw "$exeName not found next to this script"
}

if ($source.TrimEnd('\') -eq $target.TrimEnd('\')) {
    Write-Host 'Already installed in this folder - nothing to copy.' -ForegroundColor Green
    if ($Launch) { Start-Process -FilePath (Join-Path $target $exeName) }
    exit 0
}

Get-Process -Name 'GhostHand' -ErrorAction SilentlyContinue | Stop-Process -Force
New-Item -ItemType Directory -Force -Path $target | Out-Null
Copy-Item -Path (Join-Path $source '*') -Destination $target -Recurse -Force

$exe = Join-Path $target $exeName
$shell = New-Object -ComObject WScript.Shell
foreach ($dir in @($startMenu, $desktop)) {
    $link = $shell.CreateShortcut((Join-Path $dir $shortcutName))
    $link.TargetPath = $exe
    $link.WorkingDirectory = $target
    $link.IconLocation = $exe
    $link.Save()
}

Write-Host "Installed to $target" -ForegroundColor Green
Write-Host 'Shortcuts added to the Start menu and desktop.'
Write-Host 'Autostart is a tray-menu toggle, not forced here.'

if ($Launch) { Start-Process -FilePath $exe }
