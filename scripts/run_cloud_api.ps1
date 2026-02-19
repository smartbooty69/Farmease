param(
    [string]$Host = "127.0.0.1",
    [int]$Port = 8787,
    [string]$ApiKey = "demo-key"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$PythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$ApiScript = Join-Path $ProjectRoot "cloud_backend\api_server.py"

if (-not (Test-Path $PythonExe)) {
    throw "Python environment not found at $PythonExe. Create .venv and install dependencies first."
}

if (-not (Test-Path $ApiScript)) {
    throw "Cloud API script not found at $ApiScript"
}

Write-Host "Starting cloud ingest API on $Host`:$Port" -ForegroundColor Green
& $PythonExe $ApiScript --host $Host --port $Port --api-key $ApiKey
