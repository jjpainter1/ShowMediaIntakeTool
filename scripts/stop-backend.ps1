param(
    [switch]$Quiet
)

$ErrorActionPreference = "SilentlyContinue"
. (Join-Path $PSScriptRoot "packaging-common.ps1")

$installRoot = Get-InstallRoot
$port = Get-BackendPort -InstallRoot $installRoot
$stoppedCurrent = Stop-PortListeners -Port $port -Quiet:$Quiet
# Clean up legacy installs that used port 8000.
$stoppedLegacy = Stop-PortListeners -Port 8000 -Quiet:$Quiet

if ($stoppedCurrent -and $stoppedLegacy) {
    exit 0
}
exit 1
