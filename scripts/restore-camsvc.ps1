<#
    Restore the deleted camsvc service registration.

    Camera AND microphone are denied system-wide, and Settings crashes on
    Privacy > Camera, because the Capability Access Manager Service ("camsvc")
    registration is missing. The implementation DLL is still present, and the
    "osprivacy" svchost group still lists the service - only
    HKLM\SYSTEM\CurrentControlSet\Services\camsvc was deleted (a common
    "privacy tweak").

    Recreates the service with Windows 11 defaults:
      path   : %SystemRoot%\system32\svchost.exe -k osprivacy -p
      binary : %SystemRoot%\system32\CapabilityAccessManager.dll
      type   : share (svchost), LocalSystem, demand start

    Undo with:  .\restore-camsvc.ps1 -Revert
#>

param([switch]$Revert)

$ErrorActionPreference = 'Continue'

$root   = Split-Path -Parent $PSScriptRoot
$logDir = Join-Path $root 'debug'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$log    = Join-Path $logDir ("restore-camsvc-{0}.log" -f (Get-Date -Format 'yyyyMMdd-HHmmss'))
$result = Join-Path $logDir 'restore-camsvc-result.txt'

function Test-Admin {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    (New-Object Security.Principal.WindowsPrincipal($id)).IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator)
}

if (-not (Test-Admin)) {
    $fwd = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "`"$PSCommandPath`"")
    if ($Revert) { $fwd += '-Revert' }
    Start-Process -FilePath 'powershell.exe' -Verb RunAs -ArgumentList $fwd | Out-Null
    exit
}

Start-Transcript -Path $log -Force | Out-Null

function Step([string]$t) { Write-Host ''; Write-Host "=== $t ===" -ForegroundColor Cyan }

$svcKey  = 'HKLM:\SYSTEM\CurrentControlSet\Services\camsvc'
$svcHost = 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Svchost'
$dll     = Join-Path $env:SystemRoot 'System32\CapabilityAccessManager.dll'

# ------------------------------------------------------------------ revert
if ($Revert) {
    Step 'revert'
    sc.exe stop camsvc | Out-Null
    Start-Sleep -Seconds 1
    sc.exe delete camsvc | Out-Null
    Write-Host 'camsvc registration removed.'
    @("when=$(Get-Date -Format o)", 'action=revert', 'ok=True') | Set-Content $result -Encoding UTF8
    Stop-Transcript | Out-Null
    Read-Host 'Press Enter to close'
    exit
}

# ------------------------------------------------------------------ preflight
Step 'preflight'
if (-not (Test-Path $dll)) {
    Write-Host "  MISSING: $dll" -ForegroundColor Red
    Write-Host '  Implementation DLL is gone too - needs an in-place repair upgrade.'
    @("when=$(Get-Date -Format o)", 'action=restore', 'ok=False', 'reason=dll_missing') |
        Set-Content $result -Encoding UTF8
    Stop-Transcript | Out-Null
    Read-Host 'Press Enter to close'
    exit
}
$ver = (Get-Item $dll).VersionInfo
Write-Host ("  dll ok      : {0}" -f $ver.FileVersion)
Write-Host ("  service key : {0}" -f (Test-Path $svcKey))
Write-Host ("  svchost -k  : osprivacy")

# ------------------------------------------------------------------ group
Step 'svchost group'
$group = (Get-ItemProperty $svcHost -ErrorAction SilentlyContinue).osprivacy
if (-not $group) {
    New-ItemProperty -Path $svcHost -Name osprivacy -Value @('camsvc') -PropertyType MultiString -Force | Out-Null
    Write-Host '  created osprivacy group with camsvc'
} elseif ($group -notcontains 'camsvc') {
    New-ItemProperty -Path $svcHost -Name osprivacy -Value ($group + 'camsvc') -PropertyType MultiString -Force | Out-Null
    Write-Host '  added camsvc to osprivacy group'
} else {
    Write-Host '  osprivacy already lists camsvc'
}

# ------------------------------------------------------------------ service
Step 'write service registration'
New-Item -Path $svcKey -Force | Out-Null

New-ItemProperty -Path $svcKey -Name Type -PropertyType DWord -Force -Value 0x20 | Out-Null
New-ItemProperty -Path $svcKey -Name Start -PropertyType DWord -Force -Value 3 | Out-Null
New-ItemProperty -Path $svcKey -Name ErrorControl -PropertyType DWord -Force -Value 1 | Out-Null
New-ItemProperty -Path $svcKey -Name ImagePath -PropertyType ExpandString -Force `
    -Value '%SystemRoot%\system32\svchost.exe -k osprivacy -p' | Out-Null
New-ItemProperty -Path $svcKey -Name DisplayName -PropertyType String -Force `
    -Value 'Capability Access Manager Service' | Out-Null
New-ItemProperty -Path $svcKey -Name ObjectName -PropertyType String -Force -Value 'LocalSystem' | Out-Null
New-ItemProperty -Path $svcKey -Name Description -PropertyType String -Force -Value `
    "Provides facilities for managing UWP apps access to app capabilities as well as checking an app's access to specific app capabilities." | Out-Null
New-ItemProperty -Path $svcKey -Name RequiredPrivileges -PropertyType MultiString -Force `
    -Value @('SeImpersonatePrivilege', 'SeDebugPrivilege', 'SeTcbPrivilege') | Out-Null
New-ItemProperty -Path $svcKey -Name ServiceSidType -PropertyType DWord -Force -Value 1 | Out-Null

$deps = @('RPCSS', 'StateRepository', 'CoreMessagingRegistrar') |
    Where-Object { Test-Path "HKLM:\SYSTEM\CurrentControlSet\Services\$_" }
New-ItemProperty -Path $svcKey -Name DependOnService -PropertyType MultiString -Force -Value $deps | Out-Null
Write-Host ("  dependencies: " + ($deps -join ', '))

New-Item -Path "$svcKey\Parameters" -Force | Out-Null
New-ItemProperty -Path "$svcKey\Parameters" -Name ServiceDll -PropertyType ExpandString -Force `
    -Value '%SystemRoot%\system32\CapabilityAccessManager.dll' | Out-Null
New-ItemProperty -Path "$svcKey\Parameters" -Name ServiceDllUnloadOnStop -PropertyType DWord -Force -Value 1 | Out-Null

Write-Host '  Type=share Start=demand ObjectName=LocalSystem'
Write-Host '  ServiceDll=%SystemRoot%\system32\CapabilityAccessManager.dll'

# ------------------------------------------------------------------ start
Step 'start service'
$startOut = sc.exe start camsvc 2>&1
$startOut | ForEach-Object { Write-Host "  $_" }

$running = $false
for ($i = 0; $i -lt 10; $i++) {
    Start-Sleep -Seconds 1
    $q = (sc.exe query camsvc 2>&1) -join ' '
    if ($q -match 'RUNNING') { $running = $true; break }
}
Write-Host ("  running: {0}" -f $running)

# ------------------------------------------------------------------ verify
Step 'camera + microphone'
$py   = Join-Path $root '.venv\Scripts\python.exe'
$av   = Join-Path $root 'scripts\check_av.py'
$out  = 'not tested'
if ((Test-Path $py) -and (Test-Path $av)) {
    $out = (& $py $av 2>&1) | ForEach-Object { Write-Host "  $_"; $_ }
    $out = ($out -join ' | ') -replace "`r?`n", ' '
} else {
    Write-Host '  venv or check_av.py missing, skipping'
}

Step 'verdict'
if ($running -and $out -match 'camera=ok') {
    Write-Host '  SUCCESS - consent broker running, RealSense enumerating.' -ForegroundColor Green
    Write-Host '  Reboot, then start the app with run.bat.'
} elseif ($running) {
    Write-Host '  Service running, but the camera still is not enumerating.' -ForegroundColor Yellow
    Write-Host '  Check the USB port / close other camera apps, then run scripts\doctor.py.'
} else {
    Write-Host '  Service did not reach RUNNING - see the transcript above.' -ForegroundColor Red
}

@(
    "when=$(Get-Date -Format o)"
    'action=restore'
    "ok=$($running -and $out -match 'camera=ok')"
    "service_running=$running"
    "check=$out"
    "log=$log"
) | Set-Content $result -Encoding UTF8

Write-Host ''
Write-Host "Log: $log"
Stop-Transcript | Out-Null
Read-Host 'Press Enter to close'
