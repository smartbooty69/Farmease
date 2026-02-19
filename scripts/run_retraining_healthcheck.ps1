param(
    [switch]$StrictRelayQuality,
    [int]$WalkForwardSplits = 6,
    [switch]$FailOnHealthIssue,
    [double]$MaxTrainingAgeHours = 48,
    [int]$MinRowsUsed = 500,
    [int]$MinWalkForwardFolds = 3,
    [double]$MinClassificationF1 = 0.40,
    [double]$MaxRegressionMae = 1000
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$PythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $PythonExe)) {
    throw "Python environment not found at $PythonExe. Create .venv and install dependencies first."
}

Push-Location $ProjectRoot
try {
    $trainArgs = @("train_models.py", "--walk-forward-splits", "$WalkForwardSplits")
    if ($StrictRelayQuality) {
        $trainArgs += "--strict-relay-quality"
    }

    Write-Host "[1/4] Retraining models..." -ForegroundColor Cyan
    & $PythonExe @trainArgs

    Write-Host "[2/4] Running prediction smoke check..." -ForegroundColor Cyan
    & $PythonExe "predict_next.py"

    Write-Host "[3/4] Generating event evidence..." -ForegroundColor Cyan
    & $PythonExe "scripts\generate_event_evidence.py"

    Write-Host "[4/4] Generating health check report..." -ForegroundColor Cyan
    $healthArgs = @(
        "scripts\generate_health_report.py",
        "--max-training-age-hours", "$MaxTrainingAgeHours",
        "--min-rows-used", "$MinRowsUsed",
        "--min-walk-forward-folds", "$MinWalkForwardFolds",
        "--min-classification-f1", "$MinClassificationF1",
        "--max-regression-mae", "$MaxRegressionMae"
    )
    if ($FailOnHealthIssue) {
        $healthArgs += "--fail-on-health-issue"
    }
    & $PythonExe @healthArgs

    Write-Host "Scheduled retraining healthcheck workflow completed." -ForegroundColor Green
}
finally {
    Pop-Location
}
