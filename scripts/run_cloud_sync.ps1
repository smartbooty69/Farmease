Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$PythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$WorkerScript = Join-Path $ProjectRoot "scripts\cloud_sync_worker.py"

if (-not (Test-Path $PythonExe)) {
    throw "Python environment not found at $PythonExe. Create .venv and install dependencies first."
}

if (-not (Test-Path $WorkerScript)) {
    throw "cloud_sync_worker.py not found at $WorkerScript"
}

Write-Host "Starting FarmEase cloud sync worker..." -ForegroundColor Green
& $PythonExe $WorkerScript
