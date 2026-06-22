param(
    [switch]$Quiet
)

$ErrorActionPreference = "SilentlyContinue"
. (Join-Path $PSScriptRoot "packaging-common.ps1")

if (Stop-PortListeners -Port 8000 -Quiet:$Quiet) {
    exit 0
}
exit 1
