<#
    Repair the Windows camera privacy stack.

    Symptom this fixes: every app gets "Access is denied" on the camera, the
    Windows Camera app asks for permission it cannot be granted, and
    SystemSettings.exe crashes when opening Privacy > Camera.

    Cause: camsvc (Capability Access Manager Service) is missing - both
    C:\Windows\System32\camsvc.dll and its service registration.

    This script self-elevates, then runs DISM RestoreHealth and SFC /scannow so
    Windows can restore the missing component from its servicing store or
    Windows Update. Everything is logged to debug\repair-camera-*.log.
#>

$ErrorActionPreference = 'Continue'

$root   = Split-Path -Parent $PSScriptRoot
$logDir = Join-Path $root 'debug'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$log = Join-Path $logDir ("repair-camera-{0}.log" -f (Get-Date -Format 'yyyyMMdd-HHmmss'))

function Test-Admin {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    (New-Object Security.Principal.WindowsPrincipal($id)).IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator)
}

if (-not (Test-Admin)) {
    Write-Host 'Requesting administrator rights (a UAC prompt will appear)...'
    Start-Process -FilePath 'powershell.exe' -Verb RunAs -ArgumentList @(
        '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "`"$PSCommandPath`""
    ) | Out-Null
    exit
}

Start-Transcript -Path $log -Force | Out-Null

function Step([string]$text) {
    Write-Host ''
    Write-Host "=== $text ===" -ForegroundColor Cyan
}

function Report-State([string]$when) {
    Step "state: $when"
    $svc = Get-Service camsvc -ErrorAction SilentlyContinue
    Write-Host ("  camsvc service : " + $(if ($svc) { $svc.Status } else { 'MISSING' }))
    Write-Host ("  camsvc.dll     : " + (Test-Path "$env:SystemRoot\System32\camsvc.dll"))
}

Step 'environment'
Write-Host ("  windows build  : " + (Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion').CurrentBuild)
Write-Host ("  free space C:  : {0:N1} GB" -f ((Get-PSDrive C).Free / 1GB))
Report-State 'before'

Step 'DISM CheckHealth'
DISM /Online /Cleanup-Image /CheckHealth

Step 'DISM RestoreHealth (this can take 10-30 minutes, do not close the window)'
DISM /Online /Cleanup-Image /RestoreHealth

Step 'SFC scannow'
sfc /scannow

Report-State 'after DISM + SFC'

$svc = Get-Service camsvc -ErrorAction SilentlyContinue
if ($svc) {
    Step 'starting camsvc'
    try { Start-Service camsvc -ErrorAction Stop } catch { Write-Host "  start failed: $_" }
}

Step 'camera enumeration test'
$py = Join-Path $root '.venv\Scripts\python.exe'
$cameraDevices = 'not tested'
if (Test-Path $py) {
    $camOut = & $py -c "import pyrealsense2 as rs; d=list(rs.context().query_devices()); print('DEVICES', len(d)); [print(' ', x.get_info(rs.camera_info.name)) for x in d]" 2>&1
    $camOut | ForEach-Object { Write-Host "  $_" }
    $cameraDevices = ($camOut | Select-Object -First 1)
} else {
    Write-Host '  venv python not found, skipping'
}

Step 'verdict'
if (Test-Path "$env:SystemRoot\System32\camsvc.dll") {
    Write-Host '  camsvc.dll is back on disk.' -ForegroundColor Green
    if (-not (Get-Service camsvc -ErrorAction SilentlyContinue)) {
        Write-Host '  ...but the service is still not registered.' -ForegroundColor Yellow
        Write-Host '  Reinstalling the latest cumulative update or an in-place repair upgrade'
        Write-Host '  is the reliable way to recreate the service entry.'
    }
} else {
    Write-Host '  camsvc.dll is still missing.' -ForegroundColor Red
    Write-Host '  Windows could not restore the component. Next step is an in-place repair'
    Write-Host '  upgrade with a matching build ISO (keeps apps and files).'
}

Step 'done'
Write-Host "Log: $log"

$resultPath = Join-Path $logDir 'repair-camera-result.txt'
@(
    "when=$(Get-Date -Format o)"
    "log=$log"
    "camsvc_dll=$(Test-Path "$env:SystemRoot\System32\camsvc.dll")"
    "camsvc_service=$([bool](Get-Service camsvc -ErrorAction SilentlyContinue))"
    "camera=$cameraDevices"
) | Set-Content -Path $resultPath -Encoding UTF8

Stop-Transcript | Out-Null
Read-Host 'Press Enter to close'
