# Changelog

All notable changes to Show Media Intake Tool v2 are documented here for GitHub releases and handoff notes.

## [2.1.1] — 2026-06-20

### Fixed

- **Config — filename pattern reorder** — custom token order now uses pointer-based drag instead of HTML5 drag-and-drop, which does not work in the Tauri WebView2 shell on Windows.

### Packaging

- Artifact: `dist/ShowMediaIntakeTool-v2.1.1-win64.zip` + `.sha256`

---

## [2.1.0] — 2026-06-19

First recommended public release zip after initial field testing.

### Added

- **Windows distribution** — versioned zip, `setup.cmd`, desktop launcher, bundled FFmpeg, per-user Python install (`PACKAGING.md`).
- **Output spec mode** (`output_specs.mode`: `uniform` | `per_screen`) for mixed LED/projector shows.
- **Flat intake mode** (`intake.mode: "flat"`) — union spec validation across all screens; passing files copy to `Media/_INCOMING/` with original filenames; strict failures go to `_REVIEW`.
- **Configurable filename convention** — token builder in Config; validation strictness per field.
- **Per-screen expected specs** (`screens[].expected_specs`) with merged validation on routed intake.
- **Project app icon** — `assets/branding/` → Tauri bundle, Windows `.exe`, browser favicon.
- **Dev workflow** — `scripts/dev.cmd`, `setup-dev.cmd`, `run-tests.ps1`, root `package.json` npm helpers.

### Changed

- **Filename parser** — detects tokens in any order (not only configured token order).
- **Flat intake** — removed per-batch target screen picker; auto-route validated files to `_INCOMING`.
- **Routed intake** — validates framerate, color, and audio against per-screen merged specs when filename targets `SCR##`.
- **Dashboard** — on-disk file validation uses the screen folder context.
- Removed legacy `PixeraIntakeTool/` v1 tree and unused prototype modules.

### Fixed

- **Production GUI** — backend CORS for Tauri `http://tauri.localhost`; `start-backend.ps1` no longer dies on uvicorn stderr logs.
- **Dev launcher** — frees ports 8000 and 1420 before start; supports `.venv` via `setup-dev`.

### Packaging

- Artifact: `dist/ShowMediaIntakeTool-v2.1.0-win64.zip` + `.sha256`
- Install: extract → `scripts\setup.cmd` → desktop shortcut (do not double-click `.exe` alone).

---

## [2.0.1] — 2026-06-18 (internal)

- Flat intake union validation and `_INCOMING` routing (superseded by 2.1.0 release bundle).

## [2.0.0] — 2026-06-18 (internal)

- Initial Tauri + FastAPI build; first zip smoke-tested on a clean Windows VM.
