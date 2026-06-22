# Daily launcher: backend + Tauri desktop app.

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "packaging-common.ps1")

$Host.UI.RawUI.WindowTitle = "Show Media Intake Tool"
$InstallRoot = Get-InstallRoot
Set-Location $InstallRoot

$setupMarker = Join-Path $InstallRoot ".setup-complete"
if (-not (Test-Path $setupMarker)) {
    Write-Host ""
    Write-Host "WARNING: Setup has not been run. Launching anyway, but if the app fails,"
    Write-Host "run scripts\setup.cmd first."
    Write-Host ""
}

if (-not (Test-RuntimeReady -InstallRoot $InstallRoot)) {
    Write-Host ""
    Write-Host "ERROR: Run scripts\setup.cmd first."
    exit 1
}

$stopScript = Join-Path $InstallRoot "scripts\stop-backend.ps1"
& $stopScript -Quiet
if ($LASTEXITCODE -ne 0) {
    Write-Host "WARNING: Port 8000 may still be in use. Close other copies of the app and try again."
}

$startBackendScript = Join-Path $InstallRoot "scripts\start-backend.ps1"
$backend = Start-Process -FilePath "powershell.exe" `
    -ArgumentList "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$startBackendScript`"" `
    -WorkingDirectory $InstallRoot `
    -WindowStyle Hidden `
    -PassThru

if (-not $backend) {
    Write-Host ""
    Write-Host "ERROR: Backend failed to start. Run scripts\setup.cmd again."
    exit 1
}

Write-Host "Starting backend..."
$health = Wait-BackendHealth -TimeoutSeconds 45
if (-not $health) {
    Stop-BackendProcess -BackendProcess $backend
    & $stopScript -Quiet | Out-Null
    Write-Host ""
    Write-Host "ERROR: Backend did not become ready in 45 seconds."
    Write-Host "Check backend.log in the install folder for details."
    Write-Host "Another copy may already be running, or another app is using port 8000."
    exit 1
}

Write-Host "OK  Backend ready on http://127.0.0.1:8000"

if (-not $health.ffprobe_available) {
    Stop-BackendProcess -BackendProcess $backend
    & $stopScript -Quiet | Out-Null
    Write-Host ""
    Write-Host "ERROR: ffprobe not found. Re-run scripts\setup.cmd."
    exit 1
}

$appExe = Join-Path $InstallRoot "Show Media Intake Tool.exe"
if (-not (Test-Path $appExe)) {
    Stop-BackendProcess -BackendProcess $backend
    & $stopScript -Quiet | Out-Null
    Write-Host ""
    Write-Host "ERROR: Show Media Intake Tool.exe not found in install folder."
    exit 1
}

$app = Start-Process -FilePath $appExe -WorkingDirectory $InstallRoot -PassThru
$app.WaitForExit()

Stop-BackendProcess -BackendProcess $backend
& $stopScript | Out-Null

exit 0
