param(
    [switch]$Quiet
)

$ErrorActionPreference = "SilentlyContinue"
. (Join-Path $PSScriptRoot "packaging-common.ps1")

$ok = $true
if (-not (Stop-PortListeners -Port 1420 -Quiet:$Quiet)) {
    $ok = $false
}
# Vite HMR may use 1421 when TAURI_DEV_HOST is set.
Stop-PortListeners -Port 1421 -Quiet:$Quiet | Out-Null

if ($ok) {
    exit 0
}
exit 1
