# CLI launcher for power users (desktop shortcut target).

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "packaging-common.ps1")

$InstallRoot = Get-InstallRoot
Set-Location $InstallRoot

if (-not (Test-RuntimeReady -InstallRoot $InstallRoot)) {
    Write-Host "ERROR: Run scripts\setup.cmd first."
    exit 1
}

Add-FfmpegToPath -InstallRoot $InstallRoot
exit (Invoke-AppPython -InstallRoot $InstallRoot (Join-Path $InstallRoot "cli_intake.py"))
