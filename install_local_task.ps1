param(
    [string]$TaskName = "Nikki Local Node Pool Refresh"
)
$ErrorActionPreference = "Stop"

$ScriptPath = Join-Path $PSScriptRoot "run_local_filter.ps1"
if(!(Test-Path $ScriptPath)){ throw "run_local_filter.ps1 not found: $ScriptPath" }

$Action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$ScriptPath`" -Publish"

$Trigger = New-ScheduledTaskTrigger `
    -Once `
    -At (Get-Date).Date.AddMinutes(45) `
    -RepetitionInterval (New-TimeSpan -Hours 4) `
    -RepetitionDuration (New-TimeSpan -Days 3650)

$Settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30) `
    -MultipleInstances IgnoreNew

try {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
} catch {}

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Description "Refresh and locally test Nikki general/GPT node pools, then publish small pools to GitHub main." `
    -User "$env:USERNAME" `
    -RunLevel Highest

Write-Host "Scheduled task installed: $TaskName"
Write-Host "Repeat: every 4 hours"
