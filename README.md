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

**First time only:**

```powershell
cd path\to\ShowMediaIntakeTool_v2
scripts\setup-dev.cmd
```

**Each dev session:**

```powershell
scripts\start-backend.ps1
```

`start-backend.ps1` uses `.venv` when developing from source. Packaged installs (extracted zip) use `scripts\setup.cmd` instead, which creates `python-packages\`.

Manual equivalent:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

### 2. React frontend (browser dev)

The Node project is in **`frontend/`** — `npm` commands must run there (or use the helpers below).

```powershell
cd frontend
npm install
npm run dev
```

From the **repo root** you can also run:

```powershell
npm run install:frontend   # first time only
npm run dev                # delegates to frontend/
```

Or without changing directory:

```powershell
scripts\npm-dev.cmd
```

Open http://localhost:1420 — Vite proxies `/api` (including WebSockets) to http://127.0.0.1:8000.

**One command (backend + frontend):**

```powershell
scripts\dev.cmd
```

Starts the backend (new window), waits until it is healthy, runs the frontend in this terminal, and opens your browser. Press **Ctrl+C** here to stop both. Stale processes on ports **8000** and **1420** are cleared automatically (e.g. a previous `npm run dev` left running).

> **Note:** `npm run dev` at the project root (without `package.json` helpers) will fail — there is no root Vite app, only `frontend\`.

**Run dev tests:**

```powershell
.\scripts\run-tests.ps1
```

**Manual (two terminals):**

```powershell
# Terminal 1 — backend
.\scripts\start-backend.ps1

# Terminal 2 — frontend (pick one)
cd frontend
npm run dev

# or from repo root:
npm run dev

# or:
scripts\npm-dev.cmd
```

**Browse folders in browser dev:** the **Browse** button calls `GET /api/system/pick-folder`, which opens the standard Windows folder dialog via the Python backend (same machine). Use `npm run tauri:dev` for the Tauri-native dialog in the desktop shell.

**Future (v2.1):** Revisit an intake folder browser that previews media files inside the folder (would need drive switching); standard folder pick is used for now.

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
├── scripts/           # Dev, packaging, and test utilities
├── assets/branding/   # Source app icon (icon_1024.png, AppIcon.ico)
├── cli_intake.py      # Power-user CLI fallback
└── DESIGN-V2.md       # Full UI/workflow specification
```

## CLI fallback

```powershell
python cli_intake.py
```

## Install target (production)

Recommended path: `C:\Tools\ShowMediaIntakeTool\`

**Operators:** see [`README-INSTALL.txt`](README-INSTALL.txt) — extract zip → run `scripts\setup.cmd` → use desktop shortcut.

**Developers building a release:**

```powershell
# Requires Rust + Node (see Prerequisites). Builds Tauri exe, bundles FFmpeg, creates dist\ zip.
.\scripts\build-release.ps1
```

See [`PACKAGING.md`](PACKAGING.md) for the full distribution spec.


## Troubleshooting

### Vite `EBUSY` when the repo is in Dropbox

Dropbox can lock files under `node_modules` while syncing. Vite pre-bundles dependencies by renaming folders under `.vite`, which fails with `EBUSY: resource busy or locked`.

This project sets Vite `cacheDir` to `%LOCALAPPDATA%\ShowMediaIntakeTool\vite-cache` (outside Dropbox). If you still see errors:

1. Stop dev servers (Ctrl+C) and close anything using `frontend/node_modules/.vite`.
2. Pause Dropbox sync briefly, then delete `frontend/node_modules/.vite` if it remains.
3. Retry `npm run dev` from `frontend`.
