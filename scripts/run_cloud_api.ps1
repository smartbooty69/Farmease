Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$PythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $PythonExe)) {
    throw "Python environment not found at $PythonExe. Create .venv and install dependencies first."
}

Push-Location $ProjectRoot
try {
    Write-Host "Starting FarmEase cloud ingest API on http://127.0.0.1:8000 ..." -ForegroundColor Green
    & $PythonExe -m uvicorn cloud_backend.app:app --host 127.0.0.1 --port 8000
}
finally {
    Pop-Location
}
