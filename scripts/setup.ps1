# First-time setup: Python, local packages, smoke test, desktop shortcuts.

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "packaging-common.ps1")

$Host.UI.RawUI.WindowTitle = "Show Media Intake Tool - Setup"
$InstallRoot = Get-InstallRoot
Set-Location $InstallRoot

Write-Host ""
Write-Host "======================================================================"
Write-Host "  SHOW MEDIA INTAKE TOOL  |  First-time Setup"
Write-Host "======================================================================"
Write-Host ""

$missing = Test-InstallIntegrity -InstallRoot $InstallRoot
if ($missing.Count -gt 0) {
    Write-Host "ERROR: This does not look like a complete install folder. Re-extract the zip."
    Write-Host ""
    Write-Host "Missing:"
    foreach ($item in $missing) {
        Write-Host "  - $item"
    }
    exit 1
}

Unblock-InstallFolder -InstallRoot $InstallRoot

$manifest = Get-VersionManifest -InstallRoot $InstallRoot
Update-SessionPath

# --- Python ---
$pythonExe = Resolve-PythonExecutable -InstallRoot $InstallRoot
if (-not $pythonExe) {
    Write-Host "Python 3.10 or newer is required but was not found."
    Write-Host ""
    Write-Host "If Windows shows a Store prompt when you type python, disable the alias:"
    Write-Host "  Settings > Apps > Advanced app settings > App execution aliases"
    Write-Host "  Turn OFF python.exe and python3.exe"
    Write-Host ""
    Write-Host "Setup can install Python $($manifest.python_recommended) for your user account only."
    Write-Host "This does not require administrator rights."
    Write-Host ""
    $response = Read-Host "Install Python now? [Y/n]"
    if ($response -match '^[Nn]') {
        Write-Host ""
        Write-Host "Download Python manually: $($manifest.python_installer_url)"
        exit 1
    }

    try {
        Install-PythonPerUser -Manifest $manifest | Out-Null
    } catch {
        Write-Host ""
        Write-Host "Official installer failed: $($_.Exception.Message)"
        if (-not (Install-PythonViaWinget)) {
            Write-Host ""
            Write-Host "ERROR: Could not install Python automatically."
            Write-Host "Download and install manually: $($manifest.python_installer_url)"
            exit 1
        }
    }

    $pythonExe = Wait-ResolvePythonExecutable -InstallRoot $InstallRoot -TimeoutSeconds 90
    if (-not $pythonExe) {
        Write-Host ""
        Write-Host "ERROR: Python install finished but setup still cannot find python.exe."
        Write-Host "Try these steps:"
        Write-Host "  1. Close this window and run scripts\setup.cmd again"
        Write-Host "  2. If it still fails, restart Windows and run setup.cmd again"
        Write-Host "  3. Or install manually: $($manifest.python_installer_url)"
        Write-Host "     Check 'Add python.exe to PATH' during install."
        exit 1
    }
}

Write-Host "OK  $(Get-PythonVersionLabel -PythonExe $pythonExe) at $pythonExe"
Save-PythonHome -InstallRoot $InstallRoot -PythonExe $pythonExe

# --- FFmpeg ---
if (-not (Test-FfprobeBundled -InstallRoot $InstallRoot)) {
    Write-Host ""
    Write-Host "ERROR: Bundled ffprobe is missing or not working."
    Write-Host "Re-extract the zip - the tools\ffmpeg folder may be incomplete."
    exit 1
}
Write-Host "OK  ffprobe (bundled)"

# --- Python packages (no venv; avoids Unknown Publisher blocks on copied python.exe) ---
Write-Host ""
Write-Host "Installing Python packages to python-packages\ (internet required)..."
if (-not (Install-PythonPackages -InstallRoot $InstallRoot -PythonExe $pythonExe)) {
    Write-Host ""
    Write-Host "ERROR: pip install failed. Check your internet connection and try again."
    exit 1
}
Write-Host "OK  Python packages installed"

# --- Smoke test ---
Write-Host ""
Write-Host "Running smoke test..."
Add-FfmpegToPath -InstallRoot $InstallRoot
if (-not (Test-RuntimeReady -InstallRoot $InstallRoot)) {
    Write-Host "ERROR: Package import check failed."
    exit 1
}
Write-Host "imports ok"

& (Join-Path $InstallRoot "scripts\stop-backend.ps1") | Out-Null

$packagesDir = Get-PythonPackagesDir -InstallRoot $InstallRoot
$env:PYTHONPATH = $packagesDir
$env:PYTHONNOUSERSITE = "1"

$backendPort = Get-BackendPort -InstallRoot $InstallRoot
$backendUrl = Get-BackendBaseUrl -InstallRoot $InstallRoot
$setupLog = Join-Path $InstallRoot "setup-backend-test.log"
if (Test-Path $setupLog) {
    Remove-Item $setupLog -Force
}

$backend = Start-Process -FilePath $pythonExe `
    -ArgumentList "-m uvicorn backend.main:app --host 127.0.0.1 --port $backendPort" `
    -WorkingDirectory $InstallRoot `
    -WindowStyle Hidden `
    -PassThru `
    -RedirectStandardOutput $setupLog `
    -RedirectStandardError $setupLog

$health = Wait-BackendHealth -InstallRoot $InstallRoot -TimeoutSeconds 30
Stop-BackendProcess -BackendProcess $backend
& (Join-Path $InstallRoot "scripts\stop-backend.ps1") | Out-Null

if (-not $health) {
    Write-Host ""
    Write-Host "ERROR: Backend did not become ready on $backendUrl"
    Write-Host "Port $backendPort may be in use, or Python failed to start uvicorn."
    Show-BackendLogTail -InstallRoot $InstallRoot
    exit 1
}
if (-not $health.ffprobe_available) {
    Write-Host ""
    Write-Host "ERROR: Backend started but ffprobe is not available. Re-extract the zip."
    exit 1
}
Write-Host "OK  Backend health check passed"

# --- Desktop shortcuts ---
Write-Host ""
Write-Host "Creating desktop shortcuts..."
$launchScript = Join-Path $InstallRoot "scripts\Launch Show Media Intake Tool.ps1"
$appExe = Join-Path $InstallRoot "Show Media Intake Tool.exe"
$launchArgs = "-NoProfile -ExecutionPolicy Bypass -File `"$launchScript`""

$mainShortcut = New-DesktopShortcut `
    -Name "Show Media Intake Tool" `
    -Arguments $launchArgs `
    -WorkingDirectory $InstallRoot `
    -IconLocation $appExe
Write-Host "OK  $mainShortcut"

$cliScript = Join-Path $InstallRoot "scripts\Launch Show Media Intake Tool (CLI).ps1"
$cliArgs = "-NoProfile -ExecutionPolicy Bypass -File `"$cliScript`""
$cliShortcut = New-DesktopShortcut `
    -Name "Show Media Intake Tool (CLI)" `
    -Arguments $cliArgs `
    -WorkingDirectory $InstallRoot `
    -IconLocation $appExe
Write-Host "OK  $cliShortcut"

# --- v1 detection ---
$legacyV1 = "C:\Tools\PixeraIntake\pixera_intake.py"
if (Test-Path $legacyV1) {
    Write-Host ""
    Write-Host "NOTE: An older v1 install was found at C:\Tools\PixeraIntake\."
    Write-Host "After you verify v2 works, you may delete the old folder."
    Write-Host "Recent shows are not migrated automatically."
}

# --- Complete ---
$setupMarker = Join-Path $InstallRoot ".setup-complete"
$utc = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
@(
    "setup_version=2"
    "app_version=$($manifest.app_version)"
    "completed_utc=$utc"
    "python_home=$pythonExe"
) | Set-Content -Path $setupMarker -Encoding UTF8

Write-Host ""
Write-Host "Setup complete."
Write-Host ""
Write-Host 'Use the desktop shortcut "Show Media Intake Tool" to launch the app.'
Write-Host "To run setup again (e.g. after an update), run scripts\setup.cmd."
Write-Host ""

exit 0
