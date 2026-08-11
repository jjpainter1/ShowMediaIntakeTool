# Start backend + frontend for local browser testing (one command).

param(
    [switch]$NoBrowser,
    [switch]$SkipNpmInstall
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "packaging-common.ps1")

$InstallRoot = Get-InstallRoot
$FrontendDir = Join-Path $InstallRoot "frontend"
$DevUrl = "http://localhost:1420"

Set-Location $InstallRoot
$Host.UI.RawUI.WindowTitle = "Show Media Intake Tool - Dev"

Write-Host ""
Write-Host "======================================================================"
Write-Host "  SHOW MEDIA INTAKE TOOL  |  Dev (browser)"
Write-Host "======================================================================"
Write-Host ""

if (-not (Test-DevRuntimeReady -InstallRoot $InstallRoot)) {
    Write-Host "Dev Python environment not ready. Running setup-dev ..."
    Write-Host ""
    & (Join-Path $PSScriptRoot "setup-dev.ps1")
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
    Write-Host ""
}

if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: Node.js not found on PATH. Install Node 20+ and try again."
    exit 1
}

if (-not (Test-Path $FrontendDir)) {
    Write-Host "ERROR: frontend folder not found at $FrontendDir"
    exit 1
}

$frontendPackage = Join-Path $FrontendDir "package.json"
if (-not (Test-Path $frontendPackage)) {
    Write-Host "ERROR: frontend\package.json not found."
    Write-Host "Run npm from the frontend folder, or use: scripts\npm-dev.cmd"
    exit 1
}

$nodeModules = Join-Path $FrontendDir "node_modules"
if (-not $SkipNpmInstall -and -not (Test-Path $nodeModules)) {
    Write-Host "Installing frontend dependencies (first run) ..."
    Push-Location $FrontendDir
    try {
        npm install
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    } finally {
        Pop-Location
    }
    Write-Host ""
}

$stopBackendScript = Join-Path $InstallRoot "scripts\stop-backend.ps1"
$stopFrontendScript = Join-Path $InstallRoot "scripts\stop-frontend.ps1"
& $stopBackendScript -Quiet | Out-Null
& $stopFrontendScript -Quiet | Out-Null

$startBackendScript = Join-Path $InstallRoot "scripts\start-backend.ps1"
Write-Host "Starting backend in a new window ..."
Start-Process -FilePath "powershell.exe" `
    -ArgumentList "-NoProfile", "-ExecutionPolicy", "Bypass", "-NoExit", "-File", "`"$startBackendScript`"" `
    -WorkingDirectory $InstallRoot `
    -WindowStyle Normal | Out-Null

Write-Host "Waiting for backend on $(Get-BackendBaseUrl -InstallRoot $InstallRoot) ..."
$health = Wait-BackendHealth -TimeoutSeconds 45
if (-not $health) {
    Write-Host ""
    Write-Host "ERROR: Backend did not become ready. Check the backend window for errors."
    & $stopBackendScript -Quiet | Out-Null
    exit 1
}
Write-Host "OK  Backend ready"
Write-Host ""

if (-not $NoBrowser) {
    $openUrl = $DevUrl
    Start-Process powershell.exe `
        -ArgumentList "-NoProfile", "-WindowStyle", "Hidden", "-Command", "Start-Sleep -Seconds 3; Start-Process '$openUrl'" `
        -WindowStyle Hidden | Out-Null
}

Write-Host "Starting frontend at $DevUrl"
Write-Host "Press Ctrl+C here to stop the frontend and shut down the backend."
Write-Host ""

Push-Location $FrontendDir
try {
    npm run dev
} finally {
    Pop-Location
    Write-Host ""
    Write-Host "Stopping dev servers ..."
    & $stopBackendScript -Quiet | Out-Null
    & $stopFrontendScript -Quiet | Out-Null
    Write-Host "Done."
}

exit 0
