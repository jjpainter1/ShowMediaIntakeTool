@echo off
setlocal enabledelayedexpansion
title Pixera Intake Tool - Setup Check

set PYTHON_OK=0
set ERRORS=0
set WARNINGS=0

echo.
echo ======================================================================
echo   PIXERA INTAKE TOOL  ^|  Setup Check
echo ======================================================================
echo.
echo   This script checks required software and installs Python packages.
echo   Python, ffmpeg, and Notepad++ must be installed manually if missing.
echo.
echo   Run this script from the folder that contains pixera_intake.py.
echo.
pause
echo.

REM -----------------------------------------------------------------------
REM  Check: requirements.txt is present (confirms script is in right folder)
REM -----------------------------------------------------------------------
if not exist "requirements.txt" (
    echo   ERROR: requirements.txt not found.
    echo.
    echo   Please run this script from the Pixera Intake Tool folder,
    echo   the same folder that contains pixera_intake.py.
    echo.
    goto :done
)

REM -----------------------------------------------------------------------
REM  1. Python 3.10+
REM -----------------------------------------------------------------------
echo   [1 of 3]  Python 3.10+
echo.

where python >nul 2>&1
if errorlevel 1 (
    echo     FAIL  Python is not installed or not on PATH.
    echo.
    echo           Download: https://www.python.org/downloads/
    echo           During installation, check "Add Python to PATH".
    set /a ERRORS+=1
    goto :check_ffprobe
)

python -c "import sys; sys.exit(0 if sys.version_info>=(3,10) else 1)" 2>nul
if errorlevel 1 (
    for /f "tokens=*" %%V in ('python --version 2^>^&1') do (
        echo     FAIL  %%V is too old. Python 3.10 or newer is required.
    )
    echo.
    echo           Download: https://www.python.org/downloads/
    set /a ERRORS+=1
    goto :check_ffprobe
)

for /f "tokens=*" %%V in ('python --version 2^>^&1') do (
    echo       OK  %%V
)
set PYTHON_OK=1

REM -----------------------------------------------------------------------
REM  2. ffprobe (part of ffmpeg)
REM -----------------------------------------------------------------------
:check_ffprobe
echo.
echo   [2 of 3]  ffprobe (part of ffmpeg)
echo.

where ffprobe >nul 2>&1
if errorlevel 1 (
    echo     FAIL  ffprobe is not installed or not on PATH.
    echo.
    echo           Download ffmpeg: https://ffmpeg.org/download.html
    echo           After extracting, add the bin\ folder to your system PATH:
    echo             System Properties ^> Environment Variables ^> Path ^> Edit
    set /a ERRORS+=1
) else (
    echo       OK  ffprobe found.
)
echo.

REM -----------------------------------------------------------------------
REM  3. Notepad++ (optional)
REM -----------------------------------------------------------------------
echo   [3 of 3]  Notepad++ (optional)
echo.

if exist "C:\Program Files\Notepad++\notepad++.exe" (
    echo       OK  Notepad++ found.
) else (
    echo     WARN  Notepad++ not found at C:\Program Files\Notepad++\
    echo.
    echo           This is optional. The tool will open config files in your
    echo           default text editor instead.
    echo           Download: https://notepad-plus-plus.org/downloads/
    set /a WARNINGS+=1
)
echo.

REM -----------------------------------------------------------------------
REM  4. Python packages (automatic)
REM -----------------------------------------------------------------------
echo ======================================================================
echo   Installing Python packages
echo ======================================================================
echo.

if !PYTHON_OK! equ 0 (
    echo     SKIP  Python is not available. Fix the Python error above,
    echo           then run this script again.
    goto :summary
)

echo   Running: pip install -r requirements.txt
echo.
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo     FAIL  pip install failed. See the errors above for details.
    set /a ERRORS+=1
) else (
    echo.
    echo       OK  Python packages installed successfully.
)

REM -----------------------------------------------------------------------
REM  Summary
REM -----------------------------------------------------------------------
:summary
echo.
echo ======================================================================
echo   RESULT
echo ======================================================================
echo.

if !ERRORS! neq 0 goto :show_errors

if !WARNINGS! equ 0 (
    echo   All checks passed. The tool is ready to use.
) else (
    echo   Ready ^(Notepad++ is optional and not installed^).
)
echo.
echo   To start the tool:
echo.
echo     python pixera_intake.py
goto :done

:show_errors
echo   !ERRORS! problem^(s^) found.
echo.
echo   Install the items marked FAIL above, then run this script again.

:done
echo.
echo ======================================================================
echo.
pause
endlocal
