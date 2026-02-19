param(
    [switch]$Once,
    [switch]$Enabled
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$PythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$WorkerScript = Join-Path $PSScriptRoot "cloud_sync_worker.py"

if (-not (Test-Path $PythonExe)) {
    throw "Python environment not found at $PythonExe. Create .venv and install dependencies first."
}

if (-not (Test-Path $WorkerScript)) {
    throw "Cloud sync worker script not found at $WorkerScript"
}

$argsList = @($WorkerScript)
if ($Once) {
    $argsList += "--once"
}
if ($Enabled) {
    $argsList += "--enabled"
}

Write-Host "Starting cloud sync worker..." -ForegroundColor Green
& $PythonExe @argsList
