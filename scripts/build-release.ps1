# Assemble ShowMediaIntakeTool-v{version}-win64.zip for distribution.
#
# Usage (from repo root):
#   .\scripts\build-release.ps1
#   .\scripts\build-release.ps1 -SkipTauriBuild    # if exe already built
#   .\scripts\build-release.ps1 -SkipFfmpegDownload  # if tools\ffmpeg already populated locally

param(
    [switch]$SkipTauriBuild,
    [switch]$SkipFfmpegDownload
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "packaging-common.ps1")

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Manifest = Get-VersionManifest -InstallRoot $RepoRoot
$Version = $Manifest.app_version
$DistRoot = Join-Path $RepoRoot "dist"
$ReleaseName = "ShowMediaIntakeTool-v$Version-win64"
$StageDir = Join-Path $DistRoot $ReleaseName
$TauriTargetDir = Join-Path $RepoRoot "frontend\src-tauri\target"
$StagedAppExeName = "Show Media Intake Tool.exe"

function Find-TauriReleaseExe {
    param([string]$TargetDir)
    $candidates = @(
        (Join-Path $TargetDir "release\Show Media Intake Tool.exe")
        (Join-Path $TargetDir "release\show-media-intake-tool.exe")
    )
    foreach ($path in $candidates) {
        if (Test-Path $path) { return $path }
    }
    return $null
}

Write-Host ""
Write-Host "======================================================================"
Write-Host "  BUILD RELEASE  |  $ReleaseName"
Write-Host "======================================================================"
Write-Host ""

if (-not $SkipTauriBuild) {
    Write-Host "Building Tauri desktop app (npm run tauri:build)..."
    $env:CARGO_TARGET_DIR = $TauriTargetDir
    Push-Location (Join-Path $RepoRoot "frontend")
    try {
        npm run tauri:build
        if ($LASTEXITCODE -ne 0) {
            throw "Tauri build failed with exit code $LASTEXITCODE"
        }
    } finally {
        Pop-Location
    }
}

$TauriExe = Find-TauriReleaseExe -TargetDir $TauriTargetDir
if (-not $TauriExe) {
    Write-Host "ERROR: Tauri executable not found under:"
    Write-Host "  $TauriTargetDir\release\"
    Write-Host "Expected Show Media Intake Tool.exe or show-media-intake-tool.exe"
    Write-Host "Run without -SkipTauriBuild, or build manually from frontend\."
    exit 1
}
Write-Host "OK  Tauri build: $TauriExe"

if (Test-Path $StageDir) {
    Write-Host "Refreshing stage folder..."
    try {
        Remove-Item $StageDir -Recurse -Force -ErrorAction Stop
    } catch {
        Write-Host "WARNING: Could not fully clear stage folder (files may be in use). Overwriting in place."
    }
}
New-Item -ItemType Directory -Path $StageDir -Force | Out-Null

function Copy-Tree {
    param([string]$Source, [string]$Dest)
    if (-not (Test-Path $Source)) {
        throw "Missing source path: $Source"
    }
    Copy-Item -Path $Source -Destination $Dest -Recurse -Force
}

Write-Host "Staging application files..."
Copy-Item $TauriExe -Destination (Join-Path $StageDir $StagedAppExeName)
Copy-Tree (Join-Path $RepoRoot "backend") (Join-Path $StageDir "backend")
Copy-Tree (Join-Path $RepoRoot "modules") (Join-Path $StageDir "modules")
Copy-Tree (Join-Path $RepoRoot "templates") (Join-Path $StageDir "templates")
Copy-Item (Join-Path $RepoRoot "cli_intake.py") -Destination $StageDir
Copy-Item (Join-Path $RepoRoot "requirements.txt") -Destination $StageDir
Copy-Item (Join-Path $RepoRoot "version.json") -Destination $StageDir
Copy-Item (Join-Path $RepoRoot "README-INSTALL.txt") -Destination $StageDir
Copy-Item (Join-Path $RepoRoot "LICENSE") -Destination $StageDir
Copy-Item (Join-Path $RepoRoot "THIRD-PARTY-NOTICES.txt") -Destination $StageDir

$ScriptsDest = Join-Path $StageDir "scripts"
New-Item -ItemType Directory -Path $ScriptsDest -Force | Out-Null
$scriptFiles = @(
    "packaging-common.ps1"
    "setup.ps1"
    "setup.cmd"
    "start-backend.ps1"
    "Launch Show Media Intake Tool.ps1"
    "Launch Show Media Intake Tool.cmd"
    "Launch Show Media Intake Tool (CLI).ps1"
    "stop-backend.ps1"
)
foreach ($name in $scriptFiles) {
    Copy-Item (Join-Path $RepoRoot "scripts\$name") -Destination $ScriptsDest
}

# --- FFmpeg ---
$ffmpegBinDest = Join-Path $StageDir "tools\ffmpeg\bin"
New-Item -ItemType Directory -Path $ffmpegBinDest -Force | Out-Null

$localFfmpegBin = Join-Path $RepoRoot "tools\ffmpeg\bin"
$hasLocalFfmpeg = (Test-Path (Join-Path $localFfmpegBin "ffprobe.exe"))

if ($SkipFfmpegDownload -and $hasLocalFfmpeg) {
    Write-Host "Copying bundled FFmpeg from repo tools\ffmpeg\bin..."
    Copy-Item (Join-Path $localFfmpegBin "*") -Destination $ffmpegBinDest
} else {
    Write-Host "Downloading FFmpeg ($($Manifest.ffmpeg_version))..."
    $zipUrl = $Manifest.ffmpeg_download_url
    $zipPath = Join-Path $env:TEMP "ShowMediaIntakeTool-ffmpeg.zip"
    $extractRoot = Join-Path $env:TEMP "ShowMediaIntakeTool-ffmpeg-extract"
    if (Test-Path $extractRoot) {
        Remove-Item $extractRoot -Recurse -Force
    }
    Invoke-WebRequest -Uri $zipUrl -OutFile $zipPath -UseBasicParsing
    Expand-Archive -Path $zipPath -DestinationPath $extractRoot -Force

    $binDir = Get-ChildItem -Path $extractRoot -Recurse -Directory |
        Where-Object { $_.Name -eq "bin" } |
        Select-Object -First 1
    if (-not $binDir) {
        throw "Could not find bin\ folder inside FFmpeg zip."
    }
    Copy-Item (Join-Path $binDir.FullName "ffmpeg.exe") -Destination $ffmpegBinDest
    Copy-Item (Join-Path $binDir.FullName "ffprobe.exe") -Destination $ffmpegBinDest
    Remove-Item $zipPath -Force -ErrorAction SilentlyContinue
    Remove-Item $extractRoot -Recurse -Force -ErrorAction SilentlyContinue
}

if (-not (Test-Path (Join-Path $ffmpegBinDest "ffprobe.exe"))) {
    throw "ffprobe.exe missing from staged tools\ffmpeg\bin"
}
Write-Host "OK  ffprobe staged"

# Drop bytecode caches — not needed in distribution and can lock under Dropbox/antivirus.
Get-ChildItem -Path $StageDir -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue |
    ForEach-Object { Remove-Item $_.FullName -Recurse -Force -ErrorAction SilentlyContinue }

# --- Zip ---
New-Item -ItemType Directory -Path $DistRoot -Force | Out-Null
$zipPath = Join-Path $DistRoot "$ReleaseName.zip"
if (Test-Path $zipPath) {
    Remove-Item $zipPath -Force
}

Write-Host "Creating zip..."
Compress-Archive -Path $StageDir -DestinationPath $zipPath -CompressionLevel Optimal

$hash = Get-FileHash -Path $zipPath -Algorithm SHA256
$hashPath = "$zipPath.sha256"
"$($hash.Hash)  $ReleaseName.zip" | Set-Content -Path $hashPath -Encoding ASCII

$zipSizeMb = [math]::Round((Get-Item $zipPath).Length / 1MB, 1)
Write-Host ""
Write-Host "Release built successfully."
Write-Host "  Folder: $StageDir"
Write-Host "  Zip:    $zipPath ($zipSizeMb MB)"
Write-Host "  SHA256: $hashPath"
Write-Host ""
Write-Host "Test on a clean machine: extract zip, run scripts\setup.cmd"
Write-Host ""
