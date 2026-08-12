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
# Stage outside Dropbox — in-place overwrite under dist\ often leaves empty folders.
$StageDir = Join-Path $env:TEMP $ReleaseName
$DistStageDir = Join-Path $DistRoot $ReleaseName
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

function Copy-Tree {
    param([string]$Source, [string]$Dest)
    if (-not (Test-Path $Source)) {
        throw "Missing source path: $Source"
    }
    if (Test-Path $Dest) {
        Remove-Item $Dest -Recurse -Force
    }
    Copy-Item -Path $Source -Destination $Dest -Recurse -Force
    if (-not (Test-Path $Dest)) {
        throw "Copy failed: $Dest was not created from $Source"
    }
}

Write-Host ""
Write-Host "======================================================================"
Write-Host "  BUILD RELEASE  |  $ReleaseName"
Write-Host "======================================================================"
Write-Host ""

if (-not $SkipTauriBuild) {
    Write-Host "Building Tauri desktop app (npm run tauri:build)..."
    # Keep Cargo target outside Dropbox to avoid EBUSY / file-lock failures during sync.
    if (-not $env:CARGO_TARGET_DIR) {
        $env:CARGO_TARGET_DIR = Join-Path $env:LOCALAPPDATA "ShowMediaIntakeTool\cargo-target"
    }
    $TauriTargetDir = $env:CARGO_TARGET_DIR
    Push-Location (Join-Path $RepoRoot "frontend")
    try {
        npm run tauri:build
        if ($LASTEXITCODE -ne 0) {
            throw "Tauri build failed with exit code $LASTEXITCODE"
        }
    } finally {
        Pop-Location
    }
} else {
    if ($env:CARGO_TARGET_DIR) {
        $TauriTargetDir = $env:CARGO_TARGET_DIR
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
    Write-Host "Refreshing temp stage folder..."
    Remove-Item $StageDir -Recurse -Force
}
New-Item -ItemType Directory -Path $StageDir -Force | Out-Null

Write-Host "Staging application files to $StageDir ..."
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
    $ffmpegZipPath = Join-Path $env:TEMP "ShowMediaIntakeTool-ffmpeg.zip"
    $extractRoot = Join-Path $env:TEMP "ShowMediaIntakeTool-ffmpeg-extract"
    if (Test-Path $extractRoot) {
        Remove-Item $extractRoot -Recurse -Force
    }
    Invoke-WebRequest -Uri $zipUrl -OutFile $ffmpegZipPath -UseBasicParsing
    Expand-Archive -Path $ffmpegZipPath -DestinationPath $extractRoot -Force

    $binDir = Get-ChildItem -Path $extractRoot -Recurse -Directory |
        Where-Object { $_.Name -eq "bin" } |
        Select-Object -First 1
    if (-not $binDir) {
        throw "Could not find bin\ folder inside FFmpeg zip."
    }
    Copy-Item (Join-Path $binDir.FullName "ffmpeg.exe") -Destination $ffmpegBinDest
    Copy-Item (Join-Path $binDir.FullName "ffprobe.exe") -Destination $ffmpegBinDest
    Remove-Item $ffmpegZipPath -Force -ErrorAction SilentlyContinue
    Remove-Item $extractRoot -Recurse -Force -ErrorAction SilentlyContinue
}

if (-not (Test-Path (Join-Path $ffmpegBinDest "ffprobe.exe"))) {
    throw "ffprobe.exe missing from staged tools\ffmpeg\bin"
}
Write-Host "OK  ffprobe staged"

# Drop bytecode caches — not needed in distribution.
Get-ChildItem -Path $StageDir -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue |
    ForEach-Object { Remove-Item $_.FullName -Recurse -Force -ErrorAction SilentlyContinue }

$missing = Test-InstallIntegrity -InstallRoot $StageDir
if ($missing.Count -gt 0) {
    Write-Host "ERROR: Staged release is incomplete. Missing:"
    foreach ($item in $missing) {
        Write-Host "  - $item"
    }
    exit 1
}
$backendFiles = @(Get-ChildItem (Join-Path $StageDir "backend") -Recurse -File -Filter "*.py")
$moduleFiles = @(Get-ChildItem (Join-Path $StageDir "modules") -Recurse -File -Filter "*.py")
if ($backendFiles.Count -lt 3 -or $moduleFiles.Count -lt 5) {
    throw "Staged Python trees look incomplete (backend=$($backendFiles.Count), modules=$($moduleFiles.Count))."
}
Write-Host "OK  Stage integrity ($($backendFiles.Count) backend py, $($moduleFiles.Count) module py)"

# --- Zip from temp stage ---
New-Item -ItemType Directory -Path $DistRoot -Force | Out-Null
$zipPath = Join-Path $DistRoot "$ReleaseName.zip"
$tempZip = Join-Path $env:TEMP "$ReleaseName.zip"
if (Test-Path $tempZip) {
    Remove-Item $tempZip -Force
}
Write-Host "Creating zip..."
Compress-Archive -Path $StageDir -DestinationPath $tempZip -CompressionLevel Optimal
if (Test-Path $zipPath) {
    Remove-Item $zipPath -Force -ErrorAction SilentlyContinue
}
Copy-Item -Path $tempZip -Destination $zipPath -Force
Remove-Item $tempZip -Force -ErrorAction SilentlyContinue

# Best-effort mirror under dist\ for local inspection (Dropbox may lock; zip is the artifact).
try {
    if (Test-Path $DistStageDir) {
        Remove-Item $DistStageDir -Recurse -Force -ErrorAction Stop
    }
    Copy-Item -Path $StageDir -Destination $DistStageDir -Recurse -Force
} catch {
    Write-Host "WARNING: Could not mirror stage folder into dist\ (Dropbox lock). Zip is still valid."
}

$hash = Get-FileHash -Path $zipPath -Algorithm SHA256
$hashPath = "$zipPath.sha256"
"$($hash.Hash)  $ReleaseName.zip" | Set-Content -Path $hashPath -Encoding ASCII

$zipSizeMb = [math]::Round((Get-Item $zipPath).Length / 1MB, 1)
Write-Host ""
Write-Host "Release built successfully."
Write-Host "  Temp stage: $StageDir"
Write-Host "  Zip:        $zipPath ($zipSizeMb MB)"
Write-Host "  SHA256:     $hashPath"
Write-Host ""
Write-Host "Test on a clean machine: extract zip, run scripts\setup.cmd"
Write-Host ""
