Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$PythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$DashboardPath = Join-Path $ProjectRoot "dashboard.py"
$EnvPath = Join-Path $ProjectRoot ".env"

if (-not (Test-Path $PythonExe)) {
    throw "Python environment not found at $PythonExe. Create .venv and install dependencies first."
}

if (-not (Test-Path $DashboardPath)) {
    throw "dashboard.py not found at $DashboardPath"
}

if (-not (Test-Path $EnvPath)) {
    Write-Warning ".env not found at project root. Telegram features may be disabled."
}

Write-Host "Starting FarmEase dashboard..." -ForegroundColor Green
& $PythonExe $DashboardPath
