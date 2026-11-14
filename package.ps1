# Build the distributable zip that gets attached to a GitHub release.
#
#   .\package.ps1               build, then package
#   .\package.ps1 -SkipBuild    package the existing dist\ folder
#
# Output: release\GhostHand-<version>-win64.zip
#
# The zip is portable: extract anywhere, double-click GhostHand.exe. It also
# contains "Install shortcuts.cmd" for people who want Start-menu shortcuts.

param([switch]$SkipBuild)

$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

$version = (Get-Content VERSION -Raw).Trim()
$name = "GhostHand-$version-win64"
$stage = Join-Path 'release' $name

if (-not $SkipBuild) {
    & .\build.ps1 -NoTest
    if ($LASTEXITCODE -ne 0) { throw 'build.ps1 failed' }
}

$source = Join-Path $PSScriptRoot 'dist\GhostHand'
if (-not (Test-Path (Join-Path $source 'GhostHand.exe'))) {
    throw "No build at $source - run build.ps1 first"
}

Write-Host "== staging $name ==" -ForegroundColor Cyan
Remove-Item 'release' -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $stage | Out-Null
Copy-Item (Join-Path $source '*') $stage -Recurse -Force
Copy-Item 'installer\install-local.ps1' $stage
Copy-Item 'installer\Install shortcuts.cmd' $stage
Copy-Item 'LICENSE' $stage
if (Test-Path 'assets\app.ico') { Copy-Item 'assets\app.ico' $stage }

@"
Ghost Hand $version
====================

Portable build - no installer, no admin rights.

  1. Extract this folder anywhere you like.
  2. Double-click GhostHand.exe.

That's it. The first launch opens a short guide, then the camera preview.
Settings and debug clips are written next to the exe, so the folder is
self-contained (copy it to a USB stick if you want).

Optional: double-click "Install shortcuts.cmd" to copy the app to
%LOCALAPPDATA%\Programs\GhostHand and add Start-menu and desktop shortcuts.
Remove it again with:

  powershell -ExecutionPolicy Bypass -File install-local.ps1 -Uninstall

Windows may show "Windows protected your PC" because the exe is not
code-signed. Click "More info" -> "Run anyway".

Autostart is off by default; enable it from the tray menu.

Requirements: Windows 10/11, an Intel RealSense D435 (or another webcam for
pose-only testing). The depth features need a depth camera.
"@ | Set-Content (Join-Path $stage 'README.txt') -Encoding UTF8

Write-Host '== compressing ==' -ForegroundColor Cyan
$zip = Join-Path 'release' "$name.zip"
Compress-Archive -Path (Join-Path $stage '*') -DestinationPath $zip -CompressionLevel Optimal -Force

$size = [math]::Round((Get-Item $zip).Length / 1MB)
Write-Host "== packaged: $zip ($size MB) ==" -ForegroundColor Green

# Prove the portable copy actually runs before it is published.
$exe = Join-Path $stage 'GhostHand.exe'
$proc = Start-Process -FilePath $exe -ArgumentList '--demo', '--quit-after', '6000' -PassThru
if (-not $proc.WaitForExit(45000)) {
    $proc.Kill()
    throw 'Packaged exe did not exit cleanly'
}
Write-Host "== packaged exe exit code: $($proc.ExitCode) ==" -ForegroundColor Green
