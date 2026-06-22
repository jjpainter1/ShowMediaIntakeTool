# Start the FastAPI backend (dev .venv or production python-packages layout).

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "packaging-common.ps1")

$InstallRoot = Get-InstallRoot
Set-Location $InstallRoot

$devPython = Get-DevPythonExecutable -InstallRoot $InstallRoot
$useDev = $false
$pythonExe = $null

if ($devPython -and (Test-DevRuntimeReady -InstallRoot $InstallRoot)) {
    $useDev = $true
    $pythonExe = $devPython
} elseif (Test-RuntimeReady -InstallRoot $InstallRoot) {
    $pythonExe = Get-RuntimePythonExecutable -InstallRoot $InstallRoot
    $packagesDir = Get-PythonPackagesDir -InstallRoot $InstallRoot
    $env:PYTHONPATH = $packagesDir
    $env:PYTHONNOUSERSITE = "1"
} else {
    Write-Host ""
    Write-Host "Python backend is not ready."
    Write-Host ""
    if ($devPython) {
        Write-Host "Dev .venv found but dependencies are missing. Run:"
        Write-Host "  scripts\setup-dev.cmd"
    } else {
        Write-Host "For local development from source, run:"
        Write-Host "  scripts\setup-dev.cmd"
        Write-Host ""
        Write-Host "For a packaged install (extracted zip), run:"
        Write-Host "  scripts\setup.cmd"
    }
    Write-Host ""
    exit 1
}

Add-FfmpegToPath -InstallRoot $InstallRoot

if ($useDev) {
    Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
    Remove-Item Env:PYTHONNOUSERSITE -ErrorAction SilentlyContinue
    $Host.UI.RawUI.WindowTitle = "Show Media Intake - Backend (dev)"
    Write-Host "Starting backend (dev) on http://127.0.0.1:8000 ..."
    Write-Host "Press Ctrl+C to stop."
    $ErrorActionPreference = "Continue"
    & $pythonExe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
    exit $LASTEXITCODE
}

$logFile = Join-Path $InstallRoot "backend.log"
# uvicorn logs INFO to stderr; with $ErrorActionPreference Stop that kills the server immediately.
$ErrorActionPreference = "Continue"
& $pythonExe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 2>&1 | Out-File -FilePath $logFile -Encoding UTF8
exit $LASTEXITCODE
