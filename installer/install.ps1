# Install the built folder to the current user's profile.
#
#   .\installer\install.ps1                 install from ..\dist\GhostHand
#   .\installer\install.ps1 -Launch         install and start it
#   .\installer\install.ps1 -Uninstall      remove it again
#
# No admin rights needed: everything lives under %LOCALAPPDATA%.

param(
    [string]$Source = (Join-Path $PSScriptRoot '..\dist\GhostHand'),
    [string]$Target = (Join-Path $env:LOCALAPPDATA 'Programs\GhostHand'),
    [switch]$Launch,
    [switch]$Uninstall
)

$ErrorActionPreference = 'Stop'
$exeName = 'GhostHand.exe'
$shortcutName = 'Ghost Hand.lnk'
$startMenu = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs'
$runKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'
$runValues = @('GhostHand', 'RealSenseGestureControl')

function Remove-Shortcut([string]$path) {
    if (Test-Path $path) { Remove-Item $path -Force }
}

if ($Uninstall) {
    Remove-Shortcut (Join-Path $startMenu $shortcutName)
    Remove-Shortcut (Join-Path $startMenu 'Gesture Control.lnk')
    Remove-Shortcut (Join-Path ([Environment]::GetFolderPath('Desktop')) $shortcutName)
    Remove-Shortcut (Join-Path ([Environment]::GetFolderPath('Desktop')) 'Gesture Control.lnk')
    foreach ($value in $runValues) {
        Remove-ItemProperty -Path $runKey -Name $value -ErrorAction SilentlyContinue
    }
    Get-Process -Name 'GhostHand', 'GestureControl' -ErrorAction SilentlyContinue | Stop-Process -Force
    if (Test-Path $Target) { Remove-Item -Recurse -Force $Target }
    Write-Host "Uninstalled from $Target" -ForegroundColor Green
    exit 0
}

$Source = (Resolve-Path $Source).Path
if (-not (Test-Path (Join-Path $Source $exeName))) {
    throw "No $exeName in $Source - run build.ps1 first"
}

Get-Process -Name 'GhostHand', 'GestureControl' -ErrorAction SilentlyContinue | Stop-Process -Force
New-Item -ItemType Directory -Force -Path $Target | Out-Null
# Copy the program, never the runtime state: an upgraded install keeps the
# config it already has, and a fresh one starts clean.
Get-ChildItem (Join-Path $Source '*') -Force |
    Where-Object { $_.Name -notin @('config', 'debug') } |
    ForEach-Object { Copy-Item $_.FullName $Target -Recurse -Force }

$exe = Join-Path $Target $exeName
$shell = New-Object -ComObject WScript.Shell
foreach ($dir in @($startMenu, [Environment]::GetFolderPath('Desktop'))) {
    $link = $shell.CreateShortcut((Join-Path $dir $shortcutName))
    $link.TargetPath = $exe
    $link.WorkingDirectory = $Target
    $link.IconLocation = $exe
    $link.Save()
}

$bytes = [math]::Round((Get-ChildItem $Target -Recurse -File | Measure-Object Length -Sum).Sum / 1MB)
Write-Host "Installed to $Target ($bytes MB)" -ForegroundColor Green
Write-Host 'Start menu and desktop shortcuts created.'
Write-Host 'Autostart is a toggle in the tray menu, not forced by the installer.'

if ($Launch) { Start-Process -FilePath $exe }
