$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not (Test-Path ".\.venv\Scripts\Activate.ps1")) {
    Write-Host "Creating virtual environment..."
    python -m venv .venv
    .\.venv\Scripts\Activate.ps1
    pip install -r requirements.txt
} else {
    .\.venv\Scripts\Activate.ps1
}

$port = 8000
& (Join-Path $PSScriptRoot "stop-backend.ps1")
if ($LASTEXITCODE -ne 0) {
    Write-Warning "Could not fully free port $port. Close other uvicorn terminals and try again."
}

Write-Host "Starting backend on http://127.0.0.1:$port (health phase should be 4)..."
python -m uvicorn backend.main:app --reload --port $port
