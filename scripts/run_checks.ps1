# Run every headless check suite. Used by CI and by contributors.
#
#   .\scripts\run_checks.ps1

$ErrorActionPreference = 'Continue'
Set-Location (Join-Path $PSScriptRoot '..')

$py = if (Test-Path '.venv\Scripts\python.exe') { '.venv\Scripts\python.exe' } else { 'python' }

$suites = Get-ChildItem scripts -Filter '*_check.py' |
    Where-Object { $_.Name -ne 'pose_check.py' } |
    Sort-Object Name
$suites += Get-Item scripts\pose_regression.py

$failed = @()
foreach ($suite in $suites) {
    Write-Host "== $($suite.Name) ==" -ForegroundColor Cyan
    & $py $suite.FullName
    if ($LASTEXITCODE -ne 0) { $failed += $suite.Name }
}

Write-Host ''
if ($failed.Count -gt 0) {
    Write-Host "Failed: $($failed -join ', ')" -ForegroundColor Red
    exit 1
}
Write-Host "All $($suites.Count) suites passed." -ForegroundColor Green
