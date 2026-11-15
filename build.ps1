# Build a distributable folder.
#
#   .\build.ps1              build
#   .\build.ps1 -Clean       wipe build/ and dist/ first
#   .\build.ps1 -NoTest      skip the smoke test
#
# Works with the project venv or, in CI, with whatever python is on PATH.

param([switch]$Clean, [switch]$NoTest)

$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

$py = if (Test-Path '.venv\Scripts\python.exe') { '.venv\Scripts\python.exe' } else { 'python' }

& $py -c "import PyInstaller" 2>$null
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller missing: $py -m pip install pyinstaller"
}

if ($Clean) {
    Remove-Item -Recurse -Force build, dist -ErrorAction SilentlyContinue
}

Write-Host '== icon ==' -ForegroundColor Cyan
& $py scripts\make_icon.py

Write-Host '== pyinstaller ==' -ForegroundColor Cyan
& $py -m PyInstaller --noconfirm GhostHand.spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed ($LASTEXITCODE)" }

$exe = Join-Path $PSScriptRoot 'dist\GhostHand\GhostHand.exe'
if (-not (Test-Path $exe)) { throw "Build produced no exe at $exe" }

$size = [math]::Round((Get-ChildItem 'dist\GhostHand' -Recurse -File |
    Measure-Object Length -Sum).Sum / 1MB)
Write-Host "== built: $exe  ($size MB) ==" -ForegroundColor Green

if (-not $NoTest) {
    Write-Host '== smoke test (demo source, 8s) ==' -ForegroundColor Cyan
    $p = Start-Process -FilePath $exe -ArgumentList '--demo', '--quit-after', '8000' -PassThru
    if (-not $p.WaitForExit(40000)) {
        $p.Kill()
        throw 'Built exe did not exit cleanly'
    }
    Write-Host "== smoke test exit code: $($p.ExitCode) ==" -ForegroundColor Green
}

# The smoke test writes user state (settings, the "guide seen" flag). Never
# ship that: a fresh install must get a first-run experience.
foreach ($folder in @('config', 'debug')) {
    $path = Join-Path 'dist\GhostHand' $folder
    Remove-Item $path -Recurse -Force -ErrorAction SilentlyContinue
}
