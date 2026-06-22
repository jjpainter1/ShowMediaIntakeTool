@echo off
REM Run Vite dev server from the frontend folder (not project root).
cd /d "%~dp0..\frontend"
if not exist package.json (
  echo ERROR: frontend\package.json not found.
  exit /b 1
)
npm run dev %*
