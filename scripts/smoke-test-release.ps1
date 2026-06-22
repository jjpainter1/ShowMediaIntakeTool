# Smoke test for a staged or installed release folder.
# Usage: .\scripts\smoke-test-release.ps1 [install_root]

param(
    [string]$InstallRoot = ""
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "packaging-common.ps1")

if (-not $InstallRoot) {
    $InstallRoot = Get-InstallRoot
}
Set-Location $InstallRoot

$failures = 0

function Assert-Check {
    param(
        [string]$Name,
        [bool]$Condition
    )
    if ($Condition) {
        Write-Host "PASS  $Name"
    } else {
        Write-Host "FAIL  $Name"
        $script:failures++
    }
}

Write-Host ""
Write-Host "======================================================================"
Write-Host "  RELEASE SMOKE TEST"
Write-Host "  $InstallRoot"
Write-Host "======================================================================"
Write-Host ""

Assert-Check "Install integrity" ((Test-InstallIntegrity -InstallRoot $InstallRoot).Count -eq 0)
Assert-Check "setup-complete marker" (Test-Path (Join-Path $InstallRoot ".setup-complete"))
Assert-Check "python-home.txt" (Test-Path (Join-Path $InstallRoot "python-home.txt"))
Assert-Check "No .venv python copy" (-not (Test-Path (Join-Path $InstallRoot ".venv\Scripts\python.exe")))
Assert-Check "python-packages folder" (Test-Path (Get-PythonPackagesDir -InstallRoot $InstallRoot))
Assert-Check "Runtime imports (fastapi, docx)" (Test-RuntimeReady -InstallRoot $InstallRoot)
Assert-Check "Bundled ffprobe" (Test-FfprobeBundled -InstallRoot $InstallRoot)
Assert-Check "Tauri desktop exe" (Test-Path (Join-Path $InstallRoot "Show Media Intake Tool.exe"))

$pythonExe = Get-RuntimePythonExecutable -InstallRoot $InstallRoot
Write-Host "INFO  Python runtime: $pythonExe"

& (Join-Path $InstallRoot "scripts\stop-backend.ps1") | Out-Null
$env:PYTHONPATH = Get-PythonPackagesDir -InstallRoot $InstallRoot
$env:PYTHONNOUSERSITE = "1"
Add-FfmpegToPath -InstallRoot $InstallRoot

$backend = Start-Process -FilePath $pythonExe `
    -ArgumentList "-m uvicorn backend.main:app --host 127.0.0.1 --port 8000" `
    -WorkingDirectory $InstallRoot `
    -WindowStyle Hidden `
    -PassThru

$health = Wait-BackendHealth -TimeoutSeconds 30
Stop-BackendProcess -BackendProcess $backend
& (Join-Path $InstallRoot "scripts\stop-backend.ps1") | Out-Null

Assert-Check "Backend /api/health reachable" ($null -ne $health)
if ($health) {
    Assert-Check "Health status is ok" ($health.status -eq "ok")
    Assert-Check "ffprobe_available true" ($health.ffprobe_available -eq $true)
    Assert-Check "API phase 6" ($health.phase -eq 6)
    Assert-Check "spec_generator feature" ($health.api_features -contains "spec_generator")
}

Write-Host ""
if ($failures -eq 0) {
    Write-Host "SMOKE TEST PASSED - release looks ready to ship."
    exit 0
}

Write-Host "SMOKE TEST FAILED - $failures check(s) failed."
exit 1
