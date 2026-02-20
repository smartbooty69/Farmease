param(
    [string]$ListenHost = "127.0.0.1",
    [int]$Port = 8080
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$PythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $PythonExe)) {
    throw "Python environment not found at $PythonExe. Create .venv and install dependencies first."
}

Write-Host "Starting FarmEase web frontend on $ListenHost`:$Port" -ForegroundColor Green
& $PythonExe -m uvicorn cloud_backend.frontend_server:app --host $ListenHost --port $Port
