Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$PythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$EvidenceScript = Join-Path $PSScriptRoot "generate_event_evidence.py"

if (-not (Test-Path $PythonExe)) {
    throw "Python environment not found at $PythonExe. Create .venv and install dependencies first."
}

if (-not (Test-Path $EvidenceScript)) {
    throw "Evidence script not found at $EvidenceScript"
}

Push-Location $ProjectRoot
try {
    Write-Host "[1/4] Running syntax checks..." -ForegroundColor Cyan
    & $PythonExe -m py_compile dashboard.py telegram_notifier.py

    Write-Host "[2/4] Running unit tests..." -ForegroundColor Cyan
    & $PythonExe -m unittest discover -s tests -p "test_*.py"

    Write-Host "[3/4] Running retraining + prediction smoke test..." -ForegroundColor Cyan
    & $PythonExe train_models.py
    & $PythonExe predict_next.py

    Write-Host "[4/4] Generating event evidence..." -ForegroundColor Cyan
    & $PythonExe $EvidenceScript

    Write-Host "Event rehearsal completed successfully." -ForegroundColor Green
}
finally {
    Pop-Location
}
