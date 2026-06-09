# Show Media Intake Tool v2

GUI desktop app for accepting media files at live events. v2 uses **Tauri + React** for the shell and **FastAPI + Python `modules/`** for business logic.

Current implementation status is tracked in `PROGRESS.md`.

## Prerequisites

- Python 3.10+
- Node.js 20+
- [Rust](https://rustup.rs/) (for Tauri desktop builds)
- ffprobe on PATH (ffmpeg)

## Development setup

### 1. Python backend

```powershell
cd path\to\ShowMediaIntakeTool_v2
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m uvicorn backend.main:app --reload --port 8000
```

### 2. React frontend (browser dev)

```powershell
cd frontend
npm install
npm run dev
```

Open http://localhost:1420 — Vite proxies `/api` (including WebSockets) to http://127.0.0.1:8000.

**Quick start (two terminals):**

```powershell
# Terminal 1 — backend
.\scripts\start-backend.ps1

# Terminal 2 — frontend
cd frontend
npm install
npm run dev
```

**Browse folders in browser dev:** the **Browse** button calls `GET /api/system/pick-folder`, which opens the standard Windows folder dialog via the Python backend (same machine). Use `npm run tauri:dev` for the Tauri-native dialog in the desktop shell.

**Future (v2.1):** Revisit an intake folder browser that previews media files inside the folder. A prototype (`modules/delivery_folder_picker.py`) was tried but lacked drive switching; standard folder pick is used for now.

## API endpoints (Phase 1–2)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | ffprobe + user data readiness |
| GET | `/api/recent-shows` | Recent shows list (max 5) |
| GET | `/api/shows/load?path=` | Load show; 409 if v1 config needs migration |
| GET | `/api/shows/dashboard?path=` | Dashboard snapshot via `gather_snapshot()` |
| GET | `/api/shows/config?path=` | Raw `show_config.json` |
| PUT | `/api/shows/config` | Save config (`{ path, config }`) |
| POST | `/api/shows/migrate?path=` | v1 → v2 migration with backup |
| POST | `/api/shows/create` | Create folder + starter config (`{ parent_path, folder_name }`) |
| POST | `/api/intake/scan` | Build intake plan (sync fallback) |
| POST | `/api/intake/execute` | Execute intake plan (sync fallback) |
| WS | `/api/intake/scan/ws` | Scan with live progress |
| WS | `/api/intake/execute/ws` | Execute with live progress |
| GET | `/api/system/pick-folder?title=` | Native folder picker (local backend) |

CORS allows `http://localhost:1420` and Tauri origins.

### 3. Tauri desktop (optional)

Requires Rust toolchain:

```powershell
cd frontend
npm run tauri:dev
```

## Project layout

```
ShowMediaIntakeTool_v2/
├── backend/           # FastAPI routes → modules/
├── modules/           # Business logic (intake, config, presets, …)
├── templates/         # Starter config, presets, spec template
├── frontend/          # React + Tauri shell
├── cli_intake.py      # Power-user CLI fallback
├── PixeraIntakeTool/  # Legacy v1 reference (archive when done)
└── DESIGN-V2.md       # Full UI/workflow specification
```

## CLI fallback

```powershell
python cli_intake.py
```

## Install target (production)

`C:\Tools\ShowMediaIntakeTool\` — packaging (Python sidecar + Tauri installer) is Phase 6.


## Troubleshooting

### Vite `EBUSY` when the repo is in Dropbox

Dropbox can lock files under `node_modules` while syncing. Vite pre-bundles dependencies by renaming folders under `.vite`, which fails with `EBUSY: resource busy or locked`.

This project sets Vite `cacheDir` to `%LOCALAPPDATA%\ShowMediaIntakeTool\vite-cache` (outside Dropbox). If you still see errors:

1. Stop dev servers (Ctrl+C) and close anything using `frontend/node_modules/.vite`.
2. Pause Dropbox sync briefly, then delete `frontend/node_modules/.vite` if it remains.
3. Retry `npm run dev` from `frontend`.
