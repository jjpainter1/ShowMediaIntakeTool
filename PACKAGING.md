# Packaging specification — Enhanced Option A

Operator-facing distribution for **Show Media Intake Tool v2** on Windows 10/11 (x64).

**Policy choices (locked for v1 release):**

| Decision | Choice |
|----------|--------|
| Distribution format | Versioned `.zip` (no MSI for v1) |
| Python install scope | **Per-user** (no admin required) |
| FFmpeg | **Bundled portable** in install folder |
| Recommended install path | `C:\Tools\ShowMediaIntakeTool\` (portable elsewhere OK) |
| Target audience | Internal team + free public release |

This document specs three operator-facing files:

1. `scripts\setup.ps1`
2. `scripts\Launch Show Media Intake Tool.ps1`
3. `README-INSTALL.txt` (install root, not `README.md`)

Implementation of these scripts and the release build pipeline is a follow-up task after this spec is approved.

---

## Release zip layout

Build output is assembled into a single folder before zipping:

```
ShowMediaIntakeTool-v2.1.1-win64/
├── Show Media Intake Tool.exe      # Tauri release build
├── backend/
├── modules/
├── templates/
├── cli_intake.py                   # optional CLI shortcut
├── requirements.txt
├── README-INSTALL.txt
├── LICENSE                         # project license (to be added)
├── THIRD-PARTY-NOTICES.txt         # bundled components (to be added)
├── version.json                    # machine-readable manifest (see below)
├── scripts/
│   ├── setup.ps1
│   ├── Launch Show Media Intake Tool.ps1
│   └── stop-backend.ps1            # reuse existing; no functional changes required
└── tools/
    └── ffmpeg/
        └── bin/
            ├── ffmpeg.exe
            └── ffprobe.exe
```

### `version.json` (new, small manifest)

```json
{
  "app_version": "2.1.1",
  "python_min": "3.10",
  "python_recommended": "3.12.8",
  "python_installer_url": "https://www.python.org/ftp/python/3.12.8/python-3.12.8-amd64.exe",
  "ffmpeg_version": "7.1-essentials",
  "ffmpeg_source": "https://www.gyan.dev/ffmpeg/builds/"
}
```

Pinned URLs are read by `setup.ps1` so public releases do not float to untested versions.

### Tauri build source path

After `npm run tauri:build` from `frontend/`:

- Executable: `frontend\src-tauri\target\release\Show Media Intake Tool.exe`
- Copy into release root as shown above.

### What is **not** in the zip

- `.venv` (created by setup on first run)
- `node_modules`, Rust `target/`, dev caches
- User data (`%LOCALAPPDATA%\ShowMediaIntakeTool\`) — created at runtime

---

## Shared conventions (both PowerShell scripts)

### Install root resolution

```powershell
$InstallRoot = Split-Path -Parent $PSScriptRoot   # when script lives in scripts\
Set-Location $InstallRoot
```

All relative paths (`backend\`, `tools\ffmpeg\`, `.venv\`) are from `$InstallRoot`.

### Session PATH for FFmpeg

Prepended at the start of **Launch** (and during setup verification):

```powershell
$env:PATH = (Join-Path $InstallRoot "tools\ffmpeg\bin") + ";" + $env:PATH
```

Do **not** modify the system PATH permanently. Bundled FFmpeg is sufficient.

### Python packages (no venv)

Production setup does **not** create `.venv`. Windows security policies often block the
copied `python.exe` inside a venv as "Unknown Publisher".

| Item | Value |
|------|-------|
| Packages | `$InstallRoot\python-packages\` via `pip install --target` |
| Python runtime | Signed `python.exe` from python.org (path in `python-home.txt`) |
| Launch env | `PYTHONPATH=python-packages`, `PYTHONNOUSERSITE=1` |

Use the saved system Python for all backend commands after setup completes.

### Backend (production)

| Item | Value |
|------|-------|
| Command | `python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000` |
| Reload | **Off** (no `--reload` in production) |
| Health URL | `http://127.0.0.1:8000/api/health` |
| Expected JSON | `{ "status": "ok", "ffprobe_available": true, ... }` |

### Setup-complete marker

After successful setup, write:

```
$InstallRoot\.setup-complete
```

Contents (plain text):

```
setup_version=1
app_version=2.1.1
completed_utc=2026-06-18T12:00:00Z
```

Launch may warn (not block) if this file is missing.

---

## File 1: `scripts\setup.ps1`

### Purpose

First-time (or repair) bootstrap:

1. Validate install folder integrity
2. Ensure Python 3.10+ (install per-user if missing, with consent)
3. Verify bundled FFmpeg
4. Create `.venv` and install pip dependencies
5. Smoke-test backend + ffprobe
6. Create desktop shortcut to Launch script
7. Write `.setup-complete`

### Invocation

- **Double-click:** wrap in `setup.cmd` that calls PowerShell with bypass (see below)
- **Manual:** `powershell -ExecutionPolicy Bypass -File ".\scripts\setup.ps1"`

### `setup.cmd` companion (thin wrapper)

```bat
@echo off
cd /d "%~dp0.."
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1"
pause
```

Place `setup.cmd` in `scripts\` so double-click works without execution-policy friction.

### UI / logging

- Console title: `Show Media Intake Tool - Setup`
- Use plain English; no jargon
- **PowerShell scripts must use ASCII-only characters** (no em dashes or smart quotes) so `setup.cmd` works on all Windows locales and code pages
- Color optional; not required for v1
- Exit codes: `0` = success, `1` = failure (missing deps user declined, pip fail, etc.)

### Step-by-step flow

#### Step 0 — Banner and install-root check

Print:

```
======================================================================
  SHOW MEDIA INTAKE TOOL  |  First-time Setup
======================================================================
```

**Fail fast** if any missing:

- `requirements.txt`
- `backend\main.py`
- `Show Media Intake Tool.exe`
- `tools\ffmpeg\bin\ffprobe.exe`

Error message: *"This does not look like a complete install folder. Re-extract the zip."*

#### Step 1 — Python detection

```powershell
function Test-Python310 {
    # return $true if `python -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)"` succeeds
}
```

If OK → print `OK  Python {version}` and skip to Step 3.

#### Step 2 — Python install (per-user, with consent)

Print:

```
Python 3.10 or newer is required but was not found.

Setup can install Python {python_recommended} for your user account only.
This does not require administrator rights.

Install Python now? [Y/n]
```

- Default: **Y** on Enter
- **n** → print manual link from `version.json`, exit `1`

**Install order:**

1. **winget** (if `winget --version` succeeds):

   ```
   winget install --id Python.Python.3.12 -e --scope user
        --accept-package-agreements --accept-source-agreements
   ```

   On success, refresh PATH in-process (see below) and re-test.

2. **Fallback — official installer download:**

   - Download `python_installer_url` from `version.json` to `%TEMP%\ShowMediaIntakeTool-python-installer.exe`
   - Run silent **per-user** install:

     ```
     /quiet InstallAllUsers=0 PrependPath=1 Include_test=0 Include_pip=1
     ```

   - Wait for exit code `0`

**PATH refresh after install** (required — same session otherwise won't see `python`):

```powershell
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
$machinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
$env:PATH = "$userPath;$machinePath"
```

Also check common per-user install location:

```
$env:LOCALAPPDATA\Programs\Python\Python312\python.exe
```

If still not found after install → exit `1` with *"Python was installed but not found. Restart this setup script or log off and back on."*

#### Step 3 — FFmpeg verification

Bundled path: `tools\ffmpeg\bin\ffprobe.exe`

Run: `ffprobe -version` (with session PATH prepend)

- OK → `OK  ffprobe (bundled)`
- Missing/corrupt → offer re-extract zip (setup does **not** auto-download FFmpeg in v1; it is always bundled)

#### Step 4 — Virtual environment + pip

If `.venv` missing → create.

Then:

```
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

On pip failure → exit `1`, suggest checking internet connection.

#### Step 5 — Smoke test

1. Prepend FFmpeg to PATH
2. Activate `.venv`
3. Run `python -c "import fastapi, docx; print('imports ok')"`
4. Start uvicorn in background (same as Launch, no reload)
5. Poll `/api/health` up to **30 seconds**
6. Require `status == "ok"` and `ffprobe_available == true`
7. Call `stop-backend.ps1`

On failure, print actionable message (port in use, ffprobe, import error).

#### Step 6 — Desktop shortcut

Create on the user's desktop:

| Property | Value |
|----------|-------|
| Name | `Show Media Intake Tool.lnk` |
| Target | `powershell.exe` |
| Arguments | `-NoProfile -ExecutionPolicy Bypass -File "{InstallRoot}\scripts\Launch Show Media Intake Tool.ps1"` |
| Working directory | `$InstallRoot` |
| Icon | `{InstallRoot}\Show Media Intake Tool.exe` (index 0) |

Use `WScript.Shell` COM object or `New-Object -ComObject WScript.Shell`.

Optional second shortcut (lower priority):

- Name: `Show Media Intake Tool (CLI).lnk`
- Target: `powershell.exe -NoProfile -ExecutionPolicy Bypass -File ...` running `cli_intake.py` via venv python

#### Step 7 — v1 detection (informational only)

If `C:\Tools\PixeraIntake\pixera_intake.py` exists:

```
NOTE: An older v1 install was found at C:\Tools\PixeraIntake\.
After you verify v2 works, you may delete the old folder.
Recent shows are not migrated automatically.
```

#### Step 8 — Complete

Write `.setup-complete`, print:

```
Setup complete.

Use the desktop shortcut "Show Media Intake Tool" to launch the app.
To run setup again (e.g. after an update), run scripts\setup.ps1.
```

Pause if launched via `setup.cmd`.

---

## File 2: `scripts\Launch Show Media Intake Tool.ps1`

### Purpose

Daily launcher:

1. Ensure environment (venv, FFmpeg PATH)
2. Stop any stale backend on port 8000
3. Start backend
4. Wait for health
5. Open Tauri desktop app
6. When app exits, stop backend

### Invocation

- Desktop shortcut (primary)
- Double-click `Launch Show Media Intake Tool.cmd` (optional thin wrapper, same pattern as setup)

### Step-by-step flow

#### Step 0 — Preflight

- Set `$InstallRoot`, `Set-Location`
- If `.setup-complete` missing → warn:

  ```
  Setup has not been run. Launching anyway, but if the app fails,
  run scripts\setup.ps1 first.
  ```

- If `.venv` missing → error exit `1`: *"Run scripts\setup.ps1 first."*

#### Step 1 — Environment

```powershell
$env:PATH = (Join-Path $InstallRoot "tools\ffmpeg\bin") + ";" + $env:PATH
.\.venv\Scripts\Activate.ps1
```

#### Step 2 — Stop stale backend

```powershell
& (Join-Path $InstallRoot "scripts\stop-backend.ps1")
```

Non-zero exit → warning only (port may still be stuck; show message from stop script).

#### Step 3 — Start backend (hidden)

Start as background process **without** a visible console:

```powershell
$backend = Start-Process -FilePath "python" `
    -ArgumentList "-m uvicorn backend.main:app --host 127.0.0.1 --port 8000" `
    -WorkingDirectory $InstallRoot `
    -WindowStyle Hidden `
    -PassThru
```

Record `$backend.Id` for cleanup.

#### Step 4 — Wait for health

Poll `Invoke-RestMethod http://127.0.0.1:8000/api/health` every 500ms, max 30s.

| Outcome | Action |
|---------|--------|
| `status -eq "ok"` | Continue |
| Timeout | Kill backend, exit `1` with troubleshooting hints |
| `ffprobe_available -eq $false` | Kill backend, exit `1`: *"ffprobe not found. Re-run setup."* |

#### Step 5 — Start Tauri app

```powershell
$app = Start-Process -FilePath (Join-Path $InstallRoot "Show Media Intake Tool.exe") `
    -WorkingDirectory $InstallRoot `
    -PassThru
$app.WaitForExit()
```

Block until the operator closes the app.

#### Step 6 — Cleanup

```powershell
# Stop backend process tree
if ($backend -and -not $backend.HasExited) {
    Stop-Process -Id $backend.Id -Force -ErrorAction SilentlyContinue
}
& (Join-Path $InstallRoot "scripts\stop-backend.ps1")
```

Exit `0`.

### Error messages (operator-facing)

| Condition | Message |
|-----------|---------|
| Port 8000 busy | *"Another copy may already be running, or another app is using port 8000. Close it and try again."* |
| Backend won't start | *"Backend failed to start. Run scripts\setup.ps1 or check .venv exists."* |
| Health timeout | *"Backend did not become ready in 30 seconds. Check Windows Firewall is not blocking localhost."* |

### Future enhancement (out of scope for v1 script spec)

Wire the same lifecycle inside Tauri (spawn sidecar) so Launch.ps1 is only a thin fallback. v1 ships with PowerShell orchestration.

---

## File 3: `README-INSTALL.txt`

Plain-text, not Markdown — opens in Notepad by default. Target reading level: show operator, not developer.

### Specified content (sections and exact intent)

```
================================================================================
  SHOW MEDIA INTAKE TOOL v2  —  Installation Guide
================================================================================

WHAT THIS IS
  A desktop tool for validating and organizing media files for live events
  (Pixera and similar servers). Free to use.

REQUIREMENTS
  - Windows 10 or 11 (64-bit)
  - Internet connection (first-time setup only — to install Python)
  - About 500 MB free disk space
  - FFmpeg is included; Python will be installed for you if needed

QUICK START (3 steps)

  1. EXTRACT
     Unzip the download to a permanent folder, for example:
       C:\Tools\ShowMediaIntakeTool\
     Do not run the app directly from inside the zip file.

  2. SETUP (first time only)
     Open the "scripts" folder and double-click:
       setup.cmd
     Follow the prompts. Setup will:
       - Install Python for your user account (no admin required)
       - Install the app's Python libraries
       - Create a desktop shortcut

  3. LAUNCH
     Double-click the desktop shortcut:
       Show Media Intake Tool

UPDATES
  Extract the new zip over your existing folder (or to a new folder).
  Run setup.cmd again after updating.

TROUBLESHOOTING

  "Setup says Python was not found after install"
    Close setup, open a new Command Prompt, run setup.cmd again.
    If it still fails, restart Windows and retry.

  "App says backend is not running"
    Run scripts\setup.cmd again.
    Make sure no other program is using port 8000.

  "ffprobe not available"
    Re-extract the zip — the tools\ffmpeg folder may be missing or incomplete.

  Windows SmartScreen warning
    This app is distributed as an open zip without a commercial certificate.
    If you trust the source, choose "More info" → "Run anyway" for setup.cmd.

OPTIONAL: COMMAND-LINE MODE
  For advanced users, a CLI is included:
    cli_intake.py
  Run via the optional "Show Media Intake Tool (CLI)" desktop shortcut
  after setup.

DATA LOCATIONS
  Your settings and recent shows are stored at:
    %LOCALAPPDATA%\ShowMediaIntakeTool\
  Show project folders (e.g. D:\Shows\...) are not modified except when
  you run intake on a show.

UNINSTALL
  1. Delete the install folder (e.g. C:\Tools\ShowMediaIntakeTool\)
  2. Delete the desktop shortcut
  3. Optional: delete %LOCALAPPDATA%\ShowMediaIntakeTool\
  4. Optional: uninstall Python via Windows Settings if you no longer need it

LICENSE AND THIRD-PARTY SOFTWARE
  See LICENSE and THIRD-PARTY-NOTICES.txt in this folder.

SUPPORT
  {PROJECT_URL — e.g. GitHub releases page}
  Version: 2.1.1

================================================================================
```

Replace `{PROJECT_URL}` at release time.

---

## Public release checklist (companion to these files)

Before publishing the zip:

- [ ] Run `setup.ps1` on a clean Windows VM (no Python, no ffmpeg on PATH)
- [ ] Run Launch via shortcut; complete one intake smoke test
- [ ] Verify `GET /api/health` reports `ffprobe_available: true`
- [ ] Add `LICENSE` and `THIRD-PARTY-NOTICES.txt`
- [ ] Publish SHA256 checksum alongside the zip
- [ ] Pin versions in `version.json`; do not use floating "latest" URLs in setup

---

## Implementation order (after spec approval)

1. Add `version.json` and `PACKAGING.md` (this file) — **done**
2. Implement `scripts\setup.ps1` + `scripts\setup.cmd` — **done**
3. Implement `scripts\Launch Show Media Intake Tool.ps1` + `.cmd` wrapper — **done**
4. Add `README-INSTALL.txt` to repo root (copied into release zip by build script) — **done**
5. Add `scripts\build-release.ps1` — assembles zip from Tauri build + tree above — **done**
6. Test on clean VM
7. Update `README.md` with link to `README-INSTALL.txt` for operators — **done**

---

## Open items for approval

| Item | Proposed default |
|------|------------------|
| Python pin | 3.12.8 amd64 |
| FFmpeg bundle | gyan.dev `ffmpeg-release-essentials.zip` (7.x), extract `bin\` only |
| Default install path in docs | `C:\Tools\ShowMediaIntakeTool\` |
| CLI shortcut | Create during setup (yes) |
| Setup re-run on update | Recommended in README; not forced |
