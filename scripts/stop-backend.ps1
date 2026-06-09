$ErrorActionPreference = "SilentlyContinue"
$port = 8000

$listeners = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty OwningProcess -Unique

if (-not $listeners) {
    Write-Host "No process is listening on port $port."
    exit 0
}

foreach ($procId in $listeners) {
    Write-Host "Stopping PID $procId (and child processes)..."
    taskkill /F /T /PID $procId | Out-Null
}

Start-Sleep -Seconds 2

$remaining = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
if ($remaining) {
    Write-Warning "Port $port may still be in use. Close other terminals running uvicorn, or restart your PC if needed."
    exit 1
}

Write-Host "Port $port is free."
