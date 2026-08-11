# Development Guide — Show Media Intake Tool v2

This document is for **developers** modifying the tool from source. Operators installing the released zip should use [README.md](README.md) and [README-INSTALL.txt](README-INSTALL.txt) instead.

**Stack:** Tauri + React (desktop shell) · FastAPI (local API) · Python `modules/` (business logic)

Implementation status: [PROGRESS.md](PROGRESS.md) · Full spec: [DESIGN-V2.md](DESIGN-V2.md)

---

## Prerequisites

- Python 3.10+
- Node.js 20+
- [Rust](https://rustup.rs/) (for Tauri desktop builds)
- ffprobe on PATH for local dev (packaged releases bundle FFmpeg)

---

## Quick start

**First time:**

```powershell
cd path\to\ShowMediaIntakeTool_v2
scripts\setup-dev.cmd
```

**One command (backend + frontend in browser):**

```powershell
scripts\dev.cmd
```

Opens http://localhost:1420. Vite proxies `/api` (including WebSockets) to http://127.0.0.1:18080. Press **Ctrl+C** to stop both. Ports **18080** and **1420** are cleared automatically if still in use.

**Tauri desktop shell (optional):**

```powershell
cd frontend
npm run tauri:dev
```

---

## Development setup (detail)

### Python backend

`scripts\start-backend.ps1` uses `.venv` when developing from source. Packaged installs use `scripts\setup.cmd` and `python-packages\` instead.

```powershell
scripts\start-backend.ps1
```

Manual equivalent:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 18080
```

### React frontend

The Node project lives in **`frontend/`**.

```powershell
cd frontend
npm install
npm run dev
```

From the **repo root**:

```powershell
npm run install:frontend   # first time only
npm run dev                # delegates to frontend/
# or:
scripts\npm-dev.cmd
```

> **Note:** `npm run dev` at the repo root requires the root `package.json` helpers. There is no root Vite app—only `frontend\`.

**Folder picker in browser dev:** Browse calls `GET /api/system/pick-folder` (Windows dialog via Python). Use `npm run tauri:dev` for the native Tauri dialog.

### Tests

```powershell
.\scripts\run-tests.ps1
```

Runs `scripts\test_filename_parser.py` and `scripts\test_intake_routing.py`.

### Manual two-terminal workflow

```powershell
# Terminal 1
.\scripts\start-backend.ps1

# Terminal 2
cd frontend
npm run dev
```

---

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | ffprobe + user data readiness |
| GET | `/api/recent-shows` | Recent shows list (max 5) |
| GET | `/api/shows/load?path=` | Load show; 409 if v1 config needs migration |
| GET | `/api/shows/dashboard?path=` | Dashboard snapshot |
| GET | `/api/shows/config?path=` | Raw `show_config.json` |
| PUT | `/api/shows/config` | Save config (`{ path, config }`) |
| POST | `/api/shows/migrate?path=` | v1 → v2 migration with backup |
| POST | `/api/shows/create` | Create folder + starter config |
| POST | `/api/intake/scan` | Build intake plan (sync) |
| POST | `/api/intake/execute` | Execute intake plan (sync) |
| WS | `/api/intake/scan/ws` | Scan with live progress |
| WS | `/api/intake/execute/ws` | Execute with live progress |
| GET | `/api/system/pick-folder?title=` | Native folder picker |

CORS allows `http://localhost:1420` and Tauri origins (`http://tauri.localhost`).

---

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
├── version.json       # App version (read by packaging scripts)
└── DESIGN-V2.md       # Full UI/workflow specification
```

---

## Building a release

Recommended install path for operators: `C:\Tools\ShowMediaIntakeTool\`

```powershell
# Requires Rust + Node. Builds Tauri exe, bundles FFmpeg, creates dist\ zip.
.\scripts\build-release.ps1
```

Output: `dist\ShowMediaIntakeTool-v{version}-win64.zip` + `.sha256`

See [PACKAGING.md](PACKAGING.md) for the full distribution spec.

---

## CLI fallback

```powershell
python cli_intake.py
```

---

## Troubleshooting

### Vite `EBUSY` when the repo is in Dropbox

Dropbox can lock files under `node_modules` while syncing. This project sets Vite `cacheDir` to `%LOCALAPPDATA%\ShowMediaIntakeTool\vite-cache` (outside Dropbox). If errors persist:

1. Stop dev servers (Ctrl+C).
2. Pause Dropbox sync briefly; delete `frontend/node_modules/.vite` if it remains.
3. Retry `npm run dev` from `frontend`.

### Backend not reachable in dev

- Confirm `scripts\start-backend.ps1` is running (or use `scripts\dev.cmd`).
- Check nothing else is bound to port **18080**.

---

## Related docs

- [README.md](README.md) — operator-facing overview
- [PACKAGING.md](PACKAGING.md) — zip contents and setup scripts
- [CHANGELOG.md](CHANGELOG.md) — release notes
- [AGENT-INTEGRATION.md](AGENT-INTEGRATION.md) — future headless agent goals
