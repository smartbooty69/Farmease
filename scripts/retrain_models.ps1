param(
    [switch]$StrictRelayQuality,
    [int]$WalkForwardSplits = 6
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$PythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$TrainScript = Join-Path $ProjectRoot "train_models.py"
$PredictScript = Join-Path $ProjectRoot "predict_next.py"

if (-not (Test-Path $PythonExe)) {
    throw "Python environment not found at $PythonExe. Create .venv and install dependencies first."
}

if (-not (Test-Path $TrainScript)) {
    throw "train_models.py not found at $TrainScript"
}

$trainArgs = @($TrainScript, "--walk-forward-splits", "$WalkForwardSplits")
if ($StrictRelayQuality) {
    $trainArgs += "--strict-relay-quality"
}

Write-Host "Running model retraining..." -ForegroundColor Cyan
& $PythonExe @trainArgs

Write-Host "Running prediction smoke check..." -ForegroundColor Cyan
& $PythonExe $PredictScript

Write-Host "Retraining workflow completed successfully." -ForegroundColor Green
