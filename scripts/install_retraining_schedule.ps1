param(
    [string]$TaskName = "FarmEase-RetrainingHealthcheck",
    [string]$DailyAt = "02:00",
    [switch]$StrictRelayQuality,
    [switch]$FailOnHealthIssue,
    [switch]$Force
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$RunnerScript = Join-Path $PSScriptRoot "run_retraining_healthcheck.ps1"

if (-not (Test-Path $RunnerScript)) {
    throw "Runner script not found at $RunnerScript"
}

try {
    $existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction Stop
    if (-not $Force) {
        throw "Task '$TaskName' already exists. Re-run with -Force to replace it."
    }
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}
catch {
    if ($_.Exception.Message -notlike "*cannot find the file specified*") {
        if (-not $Force) {
            throw
        }
    }
}

$argumentParts = @(
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-File", "`"$RunnerScript`""
)

if ($StrictRelayQuality) {
    $argumentParts += "-StrictRelayQuality"
}
if ($FailOnHealthIssue) {
    $argumentParts += "-FailOnHealthIssue"
}

$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument ($argumentParts -join " ") -WorkingDirectory $ProjectRoot
$trigger = New-ScheduledTaskTrigger -Daily -At ([datetime]::ParseExact($DailyAt, "HH:mm", $null))
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Description "FarmEase scheduled retraining + health check"

Write-Host "Scheduled task '$TaskName' created for daily run at $DailyAt." -ForegroundColor Green
Write-Host "To run immediately: Start-ScheduledTask -TaskName '$TaskName'" -ForegroundColor Cyan
