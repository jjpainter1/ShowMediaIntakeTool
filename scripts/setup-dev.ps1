# One-time development setup: Python venv + pip dependencies (source repo workflow).

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "packaging-common.ps1")

$InstallRoot = Get-InstallRoot
Set-Location $InstallRoot

Write-Host ""
Write-Host "======================================================================"
Write-Host "  SHOW MEDIA INTAKE TOOL  |  Development Setup"
Write-Host "======================================================================"
Write-Host ""

Update-SessionPath

$pythonExe = Resolve-PythonExecutable -InstallRoot $InstallRoot
if (-not $pythonExe) {
    Write-Host "ERROR: Python 3.10+ not found on PATH."
    Write-Host "Install from https://www.python.org/downloads/ and check 'Add python.exe to PATH'."
    exit 1
}

Write-Host "OK  $(Get-PythonVersionLabel -PythonExe $pythonExe)"
$venvPython = Join-Path $InstallRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
    Write-Host "Creating .venv ..."
    & $pythonExe -m venv (Join-Path $InstallRoot ".venv")
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Could not create virtual environment."
        exit 1
    }
    $venvPython = Join-Path $InstallRoot ".venv\Scripts\python.exe"
}

Write-Host "Installing Python dependencies into .venv ..."
& $venvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { exit 1 }
& $venvPython -m pip install -r (Join-Path $InstallRoot "requirements.txt")
if ($LASTEXITCODE -ne 0) { exit 1 }

if (-not (Test-DevRuntimeReady -InstallRoot $InstallRoot)) {
    Write-Host "ERROR: Dev runtime check failed after install."
    exit 1
}

Write-Host ""
Write-Host "Development setup complete."
Write-Host ""
Write-Host "Next:"
Write-Host "  Terminal 1: scripts\start-backend.ps1"
Write-Host "  Terminal 2: cd frontend && npm run dev"
Write-Host "  Browser:    http://localhost:1420"
Write-Host ""
exit 0
