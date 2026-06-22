# Run manual dev test scripts (filename parser, intake routing).

$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
Set-Location $Root

$python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Host "ERROR: .venv not found. Run scripts\setup-dev.cmd first."
    exit 1
}

$tests = @(
    "scripts\test_filename_parser.py",
    "scripts\test_intake_routing.py"
)

$failures = 0
foreach ($test in $tests) {
    Write-Host ""
    Write-Host "=== $test ==="
    & $python $test
    if ($LASTEXITCODE -ne 0) { $failures++ }
}

Write-Host ""
if ($failures -eq 0) {
    Write-Host "All dev tests passed."
    exit 0
}

Write-Host "$failures test script(s) failed."
exit 1
