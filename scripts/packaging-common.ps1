# Shared helpers for setup.ps1 and Launch Show Media Intake Tool.ps1

function Get-InstallRoot {
    return (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

function Get-VersionManifest {
    param([string]$InstallRoot = (Get-InstallRoot))
    $path = Join-Path $InstallRoot "version.json"
    if (-not (Test-Path $path)) {
        throw "version.json not found in $InstallRoot"
    }
    return Get-Content $path -Raw | ConvertFrom-Json
}

function Update-SessionPath {
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    $machinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $env:PATH = "$userPath;$machinePath"
}

function Test-IsWindowsAppsPythonStub {
    param([string]$PythonExe)
    if (-not $PythonExe) { return $true }
    return ($PythonExe -match '\\Microsoft\\WindowsApps\\')
}

function Unblock-InstallFolder {
    param([string]$InstallRoot)
    Write-Host "Removing downloaded-file security blocks from install folder..."
    Get-ChildItem -Path $InstallRoot -Recurse -ErrorAction SilentlyContinue |
        ForEach-Object {
            try {
                Unblock-File -LiteralPath $_.FullName -ErrorAction SilentlyContinue
            } catch {
                # Best effort only.
            }
        }
}

function Get-PythonPackagesDir {
    param([string]$InstallRoot)
    return Join-Path $InstallRoot "python-packages"
}

function Get-DevPythonExecutable {
    param([string]$InstallRoot)
    $venvPython = Join-Path $InstallRoot ".venv\Scripts\python.exe"
    if ((Test-Path $venvPython) -and (Test-Python310 -PythonExe $venvPython)) {
        return $venvPython
    }
    return $null
}

function Test-DevRuntimeReady {
    param([string]$InstallRoot)

    $pythonExe = Get-DevPythonExecutable -InstallRoot $InstallRoot
    if (-not $pythonExe) { return $false }

    & $pythonExe -c "import fastapi, docx" 2>$null
    return $LASTEXITCODE -eq 0
}

function Get-PythonHomeFile {
    param([string]$InstallRoot)
    return Join-Path $InstallRoot "python-home.txt"
}

function Save-PythonHome {
    param(
        [string]$InstallRoot,
        [string]$PythonExe
    )
    Set-Content -Path (Get-PythonHomeFile -InstallRoot $InstallRoot) -Value $PythonExe -Encoding ASCII
}

function Get-RuntimePythonExecutable {
    param([string]$InstallRoot)

    $homeFile = Get-PythonHomeFile -InstallRoot $InstallRoot
    if (Test-Path $homeFile) {
        $saved = (Get-Content $homeFile -Raw).Trim()
        if ($saved -and (Test-Path $saved) -and (Test-Python310 -PythonExe $saved)) {
            return $saved
        }
    }
    return Resolve-PythonExecutable -InstallRoot $InstallRoot
}

function Set-PythonRuntimeEnvironment {
    param([string]$InstallRoot)

    $packagesDir = Get-PythonPackagesDir -InstallRoot $InstallRoot
    if (Test-Path $packagesDir) {
        $env:PYTHONPATH = $packagesDir
    } else {
        Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
    }
    $env:PYTHONNOUSERSITE = "1"
}

function Test-RuntimeReady {
    param([string]$InstallRoot)

    $pythonExe = Get-RuntimePythonExecutable -InstallRoot $InstallRoot
    if (-not $pythonExe) { return $false }

    $packagesDir = Get-PythonPackagesDir -InstallRoot $InstallRoot
    if (-not (Test-Path $packagesDir)) { return $false }

    Set-PythonRuntimeEnvironment -InstallRoot $InstallRoot
    & $pythonExe -c "import fastapi, docx" 2>$null
    return $LASTEXITCODE -eq 0
}

function Install-PythonPackages {
    param(
        [string]$InstallRoot,
        [string]$PythonExe
    )

    $packagesDir = Get-PythonPackagesDir -InstallRoot $InstallRoot
    New-Item -ItemType Directory -Path $packagesDir -Force | Out-Null

    & $PythonExe -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) { return $false }

    & $PythonExe -m pip install --target $packagesDir -r (Join-Path $InstallRoot "requirements.txt")
    return $LASTEXITCODE -eq 0
}

function Invoke-AppPython {
    param(
        [string]$InstallRoot,
        [Parameter(ValueFromRemainingArguments = $true)]
        [string[]]$ArgumentList
    )

    $pythonExe = Get-RuntimePythonExecutable -InstallRoot $InstallRoot
    if (-not $pythonExe) {
        throw "Python runtime not configured. Run scripts\setup.cmd first."
    }
    Set-PythonRuntimeEnvironment -InstallRoot $InstallRoot
    & $pythonExe @ArgumentList
    return $LASTEXITCODE
}

function Get-PythonCandidatePaths {
  param([string]$InstallRoot)

  $paths = New-Object System.Collections.Generic.List[string]

  $pythonRoot = Join-Path $env:LOCALAPPDATA "Programs\Python"
  if (Test-Path $pythonRoot) {
    Get-ChildItem $pythonRoot -Directory -ErrorAction SilentlyContinue |
      ForEach-Object {
        $exe = Join-Path $_.FullName "python.exe"
        if (Test-Path $exe) { $paths.Add($exe) }
      }
  }

  $manifest = Get-VersionManifest -InstallRoot $InstallRoot
  if ($manifest.python_recommended -match '^(\d+)\.(\d+)') {
    $pinned = Join-Path $env:LOCALAPPDATA "Programs\Python\Python$($Matches[1])$($Matches[2])\python.exe"
    if (Test-Path $pinned) { $paths.Add($pinned) }
  }

  $pyLauncher = Get-Command py -ErrorAction SilentlyContinue
  if ($pyLauncher) {
    foreach ($versionFlag in @("-3.12", "-3.13", "-3.11", "-3.10")) {
      try {
        $resolved = & py $versionFlag -c "import sys; print(sys.executable)" 2>$null
        $resolved = ($resolved | Out-String).Trim()
        if ($resolved -and (Test-Path $resolved)) {
          $paths.Add($resolved)
        }
      } catch {
        # Try the next Python version flag.
      }
    }
  }

  $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
  if ($pythonCmd -and -not (Test-IsWindowsAppsPythonStub $pythonCmd.Source)) {
    $paths.Add($pythonCmd.Source)
  }

  $python3Cmd = Get-Command python3 -ErrorAction SilentlyContinue
  if ($python3Cmd -and -not (Test-IsWindowsAppsPythonStub $python3Cmd.Source)) {
    $paths.Add($python3Cmd.Source)
  }

  return $paths | Select-Object -Unique
}

function Resolve-PythonExecutable {
    param([string]$InstallRoot)

    foreach ($candidate in (Get-PythonCandidatePaths -InstallRoot $InstallRoot)) {
        if (Test-IsWindowsAppsPythonStub $candidate) { continue }
        if (Test-Python310 -PythonExe $candidate) {
            return $candidate
        }
    }
    return $null
}

function Wait-ResolvePythonExecutable {
    param(
        [string]$InstallRoot,
        [int]$TimeoutSeconds = 90,
        [int]$IntervalSeconds = 3
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        Update-SessionPath
        $pythonExe = Resolve-PythonExecutable -InstallRoot $InstallRoot
        if ($pythonExe) {
            return $pythonExe
        }
        Write-Host "Waiting for Python install to finish..."
        Start-Sleep -Seconds $IntervalSeconds
    }
    return $null
}

function Install-PythonPerUser {
    param($Manifest)

    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

    Write-Host ""
    Write-Host "Downloading Python installer..."
    $installerPath = Join-Path $env:TEMP "ShowMediaIntakeTool-python-installer.exe"
    Invoke-WebRequest -Uri $Manifest.python_installer_url -OutFile $installerPath -UseBasicParsing

    $targetDir = Join-Path $env:LOCALAPPDATA "Programs\Python\Python312"
    Write-Host "Running Python installer (per-user, silent)..."
    $installArgs = @(
        "/quiet"
        "InstallAllUsers=0"
        "PrependPath=1"
        "Include_test=0"
        "Include_pip=1"
        "TargetDir=$targetDir"
    )
    $process = Start-Process -FilePath $installerPath -ArgumentList $installArgs -Wait -PassThru
    if ($process.ExitCode -ne 0) {
        throw "Python installer failed with exit code $($process.ExitCode)."
    }

    $installedExe = Join-Path $targetDir "python.exe"
    if (Test-Path $installedExe) {
        return $installedExe
    }
    return $null
}

function Install-PythonViaWinget {
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if (-not $winget) { return $false }

    Write-Host ""
    Write-Host "Trying Python install via winget (per-user)..."
    & winget install --id Python.Python.3.12 -e --scope user `
        --accept-package-agreements --accept-source-agreements
    return $LASTEXITCODE -eq 0
}

function Get-PythonExecutable {
    param([string]$InstallRoot)
    return Resolve-PythonExecutable -InstallRoot $InstallRoot
}

function Add-FfmpegToPath {
    param([string]$InstallRoot)
    $ffmpegBin = Join-Path $InstallRoot "tools\ffmpeg\bin"
    if (Test-Path $ffmpegBin) {
        $env:PATH = "$ffmpegBin;$env:PATH"
    }
}

function Test-Python310 {
    param([string]$PythonExe)
    if (-not $PythonExe) { return $false }
    & $PythonExe -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" 2>$null
    return $LASTEXITCODE -eq 0
}

function Get-PythonVersionLabel {
    param([string]$PythonExe)
    if (-not $PythonExe) { return "not found" }
    $output = & $PythonExe --version 2>&1
    return ($output | Out-String).Trim()
}

function Test-FfprobeBundled {
    param([string]$InstallRoot)
    $ffprobe = Join-Path $InstallRoot "tools\ffmpeg\bin\ffprobe.exe"
    if (-not (Test-Path $ffprobe)) { return $false }
    Add-FfmpegToPath -InstallRoot $InstallRoot
    & $ffprobe -version 2>$null | Out-Null
    return $LASTEXITCODE -eq 0
}

function Wait-BackendHealth {
    param(
        [int]$TimeoutSeconds = 30,
        [int]$IntervalMs = 500
    )
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    $healthUrl = "http://127.0.0.1:8000/api/health"
    while ((Get-Date) -lt $deadline) {
        try {
            $health = Invoke-RestMethod -Uri $healthUrl -TimeoutSec 2
            if ($health.status -eq "ok") {
                return $health
            }
        } catch {
            # Backend not ready yet.
        }
        Start-Sleep -Milliseconds $IntervalMs
    }
    return $null
}

function Stop-BackendProcess {
    param([System.Diagnostics.Process]$BackendProcess)
    if ($BackendProcess -and -not $BackendProcess.HasExited) {
        Stop-Process -Id $BackendProcess.Id -Force -ErrorAction SilentlyContinue
    }
}

function Stop-PortListeners {
    param(
        [int]$Port,
        [switch]$Quiet
    )

    $prevErrorAction = $ErrorActionPreference
    $ErrorActionPreference = "SilentlyContinue"

    $listeners = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique

    if (-not $listeners) {
        if (-not $Quiet) {
            Write-Host "No process is listening on port $Port."
        }
        $ErrorActionPreference = $prevErrorAction
        return $true
    }

    foreach ($procId in $listeners) {
        if (-not $Quiet) {
            Write-Host "Stopping PID $procId on port $Port (and child processes)..."
        }
        taskkill /F /T /PID $procId | Out-Null
    }

    Start-Sleep -Seconds 1

    $remaining = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    $ErrorActionPreference = $prevErrorAction

    if ($remaining) {
        if (-not $Quiet) {
            Write-Warning "Port $Port may still be in use."
        }
        return $false
    }

    if (-not $Quiet) {
        Write-Host "Port $Port is free."
    }
    return $true
}

function New-DesktopShortcut {
    param(
        [string]$Name,
        [string]$Arguments,
        [string]$WorkingDirectory,
        [string]$IconLocation
    )
    $desktop = [Environment]::GetFolderPath("Desktop")
    $shortcutPath = Join-Path $desktop "$Name.lnk"
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = "powershell.exe"
    $shortcut.Arguments = $Arguments
    $shortcut.WorkingDirectory = $WorkingDirectory
    if ($IconLocation) {
        $shortcut.IconLocation = "$IconLocation,0"
    }
    $shortcut.Save()
    return $shortcutPath
}

function Test-InstallIntegrity {
    param([string]$InstallRoot)
    $required = @(
        "requirements.txt"
        "backend\main.py"
        "Show Media Intake Tool.exe"
        "tools\ffmpeg\bin\ffprobe.exe"
    )
    $missing = @()
    foreach ($relative in $required) {
        if (-not (Test-Path (Join-Path $InstallRoot $relative))) {
            $missing += $relative
        }
    }
    return $missing
}
