Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$PythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $PythonExe)) {
    throw "Python environment not found at $PythonExe. Create .venv and install dependencies first."
}

Push-Location $ProjectRoot
try {
    Write-Host "[1/4] Syntax check" -ForegroundColor Cyan
    & $PythonExe -m py_compile dashboard.py telegram_notifier.py

    Write-Host "[2/4] Unit tests" -ForegroundColor Cyan
    & $PythonExe -m unittest discover -s tests -p "test_*.py"

    Write-Host "[3/4] Retrain + smoke prediction" -ForegroundColor Cyan
    & (Join-Path $ProjectRoot "scripts\retrain_models.ps1")

    Write-Host "[4/4] Generate event evidence" -ForegroundColor Cyan
    & $PythonExe (Join-Path $ProjectRoot "scripts\generate_event_evidence.py")

    Write-Host "Event rehearsal completed successfully." -ForegroundColor Green
    Write-Host "Review docs/EVENT_EVIDENCE.md before presenting." -ForegroundColor Green
}
finally {
    Pop-Location
}
