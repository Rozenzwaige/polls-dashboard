# setup_scheduler.ps1
# מגדיר שני משימות מתוזמנות ב-Windows Task Scheduler:
#   - כל יום ב-04:00 (בוקר)
#   - כל יום ב-18:00 (ערב)

$scriptDir  = Split-Path -Parent $MyInvocation.MyCommand.Definition
$pythonExe  = (Get-Command python).Source
$syncScript = Join-Path $scriptDir "local_auto_sync.py"
$logFile    = Join-Path $scriptDir "sync.log"

$action = New-ScheduledTaskAction `
    -Execute $pythonExe `
    -Argument "`"$syncScript`"" `
    -WorkingDirectory $scriptDir

$triggerMorning = New-ScheduledTaskTrigger -Daily -At "04:00"
$triggerEvening = New-ScheduledTaskTrigger -Daily -At "18:00"

$settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 10) `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable

# Remove existing tasks if they exist
foreach ($name in "RozaPolls-Morning", "RozaPolls-Evening") {
    if (Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $name -Confirm:$false
        Write-Host "Removed existing task: $name"
    }
}

# Register morning task (04:00)
Register-ScheduledTask `
    -TaskName "RozaPolls-Morning" `
    -Description "Sync Israeli election polls - 04:00" `
    -Action $action `
    -Trigger $triggerMorning `
    -Settings $settings `
    -RunLevel Highest `
    | Out-Null
Write-Host "Created: RozaPolls-Morning (04:00 daily)"

# Register evening task (18:00)
Register-ScheduledTask `
    -TaskName "RozaPolls-Evening" `
    -Description "Sync Israeli election polls - 18:00" `
    -Action $action `
    -Trigger $triggerEvening `
    -Settings $settings `
    -RunLevel Highest `
    | Out-Null
Write-Host "Created: RozaPolls-Evening (18:00 daily)"

Write-Host ""
Write-Host "Done! Tasks scheduled:" -ForegroundColor Green
Write-Host "  - RozaPolls-Morning: every day at 04:00"
Write-Host "  - RozaPolls-Evening: every day at 18:00"
Write-Host "  - Log file: $logFile"
Write-Host ""
Write-Host "To run manually now:" -ForegroundColor Cyan
Write-Host "  python `"$syncScript`""
