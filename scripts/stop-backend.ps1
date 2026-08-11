param(
    [switch]$Quiet
)

$ErrorActionPreference = "SilentlyContinue"
. (Join-Path $PSScriptRoot "packaging-common.ps1")

$installRoot = Get-InstallRoot
$port = Get-BackendPort -InstallRoot $installRoot

if (Stop-PortListeners -Port $port -Quiet:$Quiet) {
    exit 0
}
exit 1
