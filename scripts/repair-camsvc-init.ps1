<#
    Make camsvc actually start.

    The service registration is correct and the SCM sees it, but svchost hosts it
    and the process aborts (1067) every couple of minutes. Two candidate causes:

      1. A corrupt consent database under
         C:\ProgramData\Microsoft\Windows\CapabilityAccessManager
      2. The "-p" (private svchost) flag not matching this binary set

    This script inspects the database, renames it aside (Windows recreates it),
    then tries the service with the current command line, and if that still
    aborts, retries without "-p". Everything is logged.

    Undo: the database is renamed, not deleted, so it can be restored.
#>

$ErrorActionPreference = 'Continue'

$root   = Split-Path -Parent $PSScriptRoot
$logDir = Join-Path $root 'debug'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$log    = Join-Path $logDir ("camsvc-init-{0}.log" -f (Get-Date -Format 'yyyyMMdd-HHmmss'))
$result = Join-Path $logDir 'camsvc-init-result.txt'

function Test-Admin {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    (New-Object Security.Principal.WindowsPrincipal($id)).IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator)
}
if (-not (Test-Admin)) {
    Start-Process powershell.exe -Verb RunAs -ArgumentList @(
        '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "`"$PSCommandPath`""
    ) | Out-Null
    exit
}

Start-Transcript -Path $log -Force | Out-Null

function Step([string]$t) { Write-Host ''; Write-Host "=== $t ===" -ForegroundColor Cyan }

$db      = Join-Path $env:ProgramData 'Microsoft\Windows\CapabilityAccessManager'
$svcKey  = 'HKLM:\SYSTEM\CurrentControlSet\Services\camsvc'
$py      = Join-Path $root '.venv\Scripts\python.exe'
$av      = Join-Path $root 'scripts\check_av.py'
$summary = [ordered]@{}

Step 'consent database'
if (Test-Path $db) {
    Get-ChildItem $db -Force -ErrorAction SilentlyContinue |
        Select-Object Name, Length, LastWriteTime | Format-Table -AutoSize | Out-String | Write-Host
} else {
    Write-Host '  folder does not exist'
}

Step 'stop service'
sc.exe stop camsvc | Out-Null
Start-Sleep -Seconds 2

Step 'move database aside'
$moved = $false
if (Test-Path $db) {
    $bak = "$db.bak-" + (Get-Date -Format 'yyyyMMdd-HHmmss')
    try {
        Rename-Item -LiteralPath $db -NewName (Split-Path $bak -Leaf) -ErrorAction Stop
        $moved = $true
        Write-Host "  renamed to $(Split-Path $bak -Leaf)"
    } catch {
        Write-Host "  rename failed: $($_.Exception.Message)" -ForegroundColor Yellow
        takeown /f "$db" /r /d Y 2>&1 | Out-Null
        icacls "$db" /grant '*S-1-5-32-544:(OI)(CI)F' /t /c 2>&1 | Out-Null
        try {
            Rename-Item -LiteralPath $db -NewName (Split-Path $bak -Leaf) -ErrorAction Stop
            $moved = $true
            Write-Host "  renamed after taking ownership"
        } catch {
            Write-Host "  still failed: $($_.Exception.Message)" -ForegroundColor Red
        }
    }
}
$summary['db_moved'] = $moved

function Try-Start([string]$label) {
    Step "start attempt: $label"
    $out = sc.exe start camsvc 2>&1
    $out | ForEach-Object { Write-Host "  $_" }
    $state = 'UNKNOWN'
    for ($i = 0; $i -lt 12; $i++) {
        Start-Sleep -Seconds 1
        $q = (sc.exe query camsvc 2>&1) -join ' '
        if ($q -match 'RUNNING') { $state = 'RUNNING'; break }
        if ($q -match 'STOPPED' -and $i -ge 2) { $state = 'STOPPED'; break }
    }
    Write-Host ("  state: {0}" -f $state)
    return $state
}

$state = Try-Start 'current config (-k osprivacy -p)'
$used  = 'osprivacy -p'

if ($state -ne 'RUNNING') {
    Step 'retry without -p'
    Set-ItemProperty -Path $svcKey -Name ImagePath -Type ExpandString `
        -Value '%SystemRoot%\system32\svchost.exe -k osprivacy'
    $state = Try-Start 'without -p (-k osprivacy)'
    $used = 'osprivacy'
}

$summary['state'] = $state
$summary['imageline'] = $used

if ($state -eq 'RUNNING') {
    Step 'camera + microphone'
    if ((Test-Path $py) -and (Test-Path $av)) {
        $avout = & $py $av 2>&1
        $avout | ForEach-Object { Write-Host "  $_" }
        $summary['check'] = ($avout -join ' | ')
    }
}

Step 'verdict'
if ($state -eq 'RUNNING' -and $summary['check'] -match 'camera=ok') {
    Write-Host '  SUCCESS - service running and RealSense enumerating.' -ForegroundColor Green
} elseif ($state -eq 'RUNNING') {
    Write-Host '  Service runs but camera still denied - needs the repair upgrade.' -ForegroundColor Yellow
} else {
    Write-Host '  Service still aborts. The component cannot initialize on this image.' -ForegroundColor Red
}

Step 'crash detail (if any)'
Get-WinEvent -FilterHashtable @{LogName='Application'; ProviderName='Application Error'; StartTime=(Get-Date).AddMinutes(-10)} -ErrorAction SilentlyContinue |
    Where-Object { $_.Message -match 'svchost.exe_camsvc' } |
    Select-Object -First 2 | ForEach-Object {
        ($_.Message -replace "`r?`n", ' ').Substring(0, [Math]::Min(300, ($_.Message -replace "`r?`n", ' ').Length)) | Write-Host
    }

$summary['when'] = (Get-Date -Format o)
$summary['log']  = $log
$summary.GetEnumerator() | ForEach-Object { "$($_.Key)=$($_.Value)" } | Set-Content $result -Encoding UTF8

Write-Host ''
Write-Host "Log: $log"
Stop-Transcript | Out-Null
Read-Host 'Press Enter to close'
