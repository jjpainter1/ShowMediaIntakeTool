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
    Also check Settings > Apps > App execution aliases and turn OFF
    python.exe and python3.exe (the Windows Store stub can block setup).

  "App says backend is not running"
    Run scripts\setup.cmd again.
    Make sure no other program is using port 18080.

  "ffprobe not available"
    Re-extract the zip - the tools\ffmpeg folder may be incomplete.

  Security warning about ".venv\Scripts\python.exe" or "Unknown Publisher"
    Use the latest zip. Setup no longer uses a virtual environment.
    Delete any old .venv folder in the install directory, then run setup.cmd again.

  Windows SmartScreen or "publisher has been blocked"
    Setup uses signed Python from python.org (Python Software Foundation), not a
    copied .venv binary. On work/school PCs, IT may need to allow that publisher.
    For setup.cmd itself: choose "More info" then "Run anyway" if you trust the source.

OPTIONAL: COMMAND-LINE MODE
  For advanced users, a CLI is included:
    cli_intake.py
  Run via the "Show Media Intake Tool (CLI)" desktop shortcut after setup.

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
  https://github.com/prestigeav/ShowMediaIntakeTool
  Version: 2.2.1

================================================================================
