# Changelog

All notable changes to Show Media Intake Tool v2 are documented here for GitHub releases and handoff notes.

## [Unreleased]

---

## [2.2.1] — 2026-08-12

VM-verified patch release. Fixes first-time setup and backend startup on clean Windows machines.

### Fixed

- **Backend port changed to 18080** — avoids conflict with Pixera Companion and other tools on port 8000. Port is centralized in `version.json` (`backend_port`) and used by launcher scripts, dev proxy, and the packaged desktop app. Legacy port 8000 checks removed.
- **Setup crash on Windows** — `setup.cmd` smoke test no longer redirects stdout and stderr to the same file (`Start-Process` limitation).
- **Backend failed to start** — `ShowConfig` `NameError` in `ffprobe_wrapper.py` on Python 3.12 (added `from __future__ import annotations`).
- **Incomplete release zip** — packaging now stages outside Dropbox, verifies required files (including `backend\main.py`) before zipping, and avoids empty `backend\` folders from file-lock failures.
- **Setup diagnostics** — failed backend health check prints log tails (`setup-backend-test.log`, `backend.log`) and shows version/port in the setup banner.

### Changed since v2.2.0

v2.2.0 introduced still images, dashboard sequence grouping, and copy progress but had install issues on clean VMs (port conflict, missing backend files, Python import error). **Use v2.2.1 for production installs.**

### Packaging

- Artifact: `dist/ShowMediaIntakeTool-v2.2.1-win64.zip` + `.sha256`
- Verified: clean VM `setup.cmd` + desktop launch (2026-08-12)

---

## [2.2.0] — 2026-07-28

> **Do not use this release.** First-time setup and backend startup fail on clean Windows installs. Use **[v2.2.1](https://github.com/jjpainter1/ShowMediaIntakeTool/releases/tag/v2.2.1)** instead.

Field-test release: still delivery formats, dashboard sequence grouping, and live copy progress.

### Added

- **Still images and image sequences** — Config → Expected Specs: accept still delivery formats (`.jpg`, `.png`, `.tga`, `.tiff`, `.exr`, …) and numbered sequences. ffprobe reads resolution; codec/framerate/audio checks are skipped for stills. Intake groups sequence frames, validates once, and copies all frames. Sequences are always detected as one asset during scan (fast), even when stills or a format are disabled.
- **Dashboard — image sequence grouping** — Screen file panel and card counts treat numbered still sequences as one logical asset (one row, aggregated size, frame count badge). Probes first frame only for fast load.
- **Intake copy progress** — Per-file/frame progress during multi-frame copies. Byte-level progress with live percent and transferred size for large files (chunked copy with throttled WebSocket updates).

### Fixed

- **Config — custom filename convention** — Custom patterns can include any subset of tokens (not all four defaults). Routed intake still requires the `screen` token for folder routing.
- **Intake execute** — `sequence_paths` preserved through API round-trip so all sequence frames copy on execute.
- **Dashboard** — FPS shows N/A for still images and sequences.
- **Frontend** — Fixed white screen on dev load (`copyProgressPercent` export).

### Packaging

- Artifact: `dist/ShowMediaIntakeTool-v2.2.0-win64.zip` + `.sha256`

---

## [2.1.1] — 2026-06-20

### Fixed

- **Config — filename pattern reorder** — custom token order now uses pointer-based drag instead of HTML5 drag-and-drop, which does not work in the Tauri WebView2 shell on Windows.

### Packaging

- Artifact: `dist/ShowMediaIntakeTool-v2.1.1-win64.zip` + `.sha256`

---

## [2.1.0] — 2026-06-19

### Added

- **Phase 6 — Generate Spec Doc** GUI screen (backend API + frontend).
- **Flat intake mode** — scan delivery folder; valid files copy to `Media\_INCOMING` with original names.
- **Per-screen spec overrides** when `output_specs.mode` is `per_screen`.
- **Configurable filename convention** — token order, version prefix, date format, loop suffix, show token.
- **Windows distribution** — versioned zip, `setup.cmd`, desktop launcher, bundled FFmpeg, per-user Python install (`PACKAGING.md`).

### Fixed

- Config load vs save validation split (open shows with incomplete fields; save still validates).
- Spec generator maps all template placeholders from saved config except manual Delivery Target date.

### Packaging

- Artifact: `dist/ShowMediaIntakeTool-v2.1.0-win64.zip` + `.sha256`

---

## [2.0.0] — 2026-06-18

- Initial Tauri + React + FastAPI v2 desktop app.
- Launch screen, dashboard, intake wizard, config editor.
- Flat intake union validation and `_INCOMING` routing (superseded by 2.1.0 release bundle).
