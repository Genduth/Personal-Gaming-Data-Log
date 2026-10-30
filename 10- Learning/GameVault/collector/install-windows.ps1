param(
    [Parameter(Mandatory = $true)]
    [string]$ApiUrl,
    [Parameter(Mandatory = $true)]
    [string]$Token,
    [string]$DeviceName = $env:COMPUTERNAME
)

$ErrorActionPreference = "Stop"
$InstallDir = Join-Path $env:LOCALAPPDATA "GameVault"
New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
Copy-Item (Join-Path $PSScriptRoot "gamevault_collector.py") $InstallDir -Force

$EnvFile = Join-Path $InstallDir "collector.env.ps1"
@"
`$env:GAMEVAULT_API_URL = '$ApiUrl'
`$env:GAMEVAULT_TOKEN = '$Token'
`$env:GAMEVAULT_DEVICE_NAME = '$DeviceName'
python `"$InstallDir\gamevault_collector.py`"
"@ | Set-Content -Path $EnvFile -Encoding UTF8

$Action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$EnvFile`""
$Trigger = New-ScheduledTaskTrigger -AtLogOn
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
Register-ScheduledTask -TaskName "GameVault Collector" -Action $Action -Trigger $Trigger -Settings $Settings -Force | Out-Null
Start-ScheduledTask -TaskName "GameVault Collector"
Write-Host "GameVault collector installed and started."
