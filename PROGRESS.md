# Show Media Intake Tool v2 - Progress Log

Last updated: 2026-07-28

## Current status

- Phase 6 **Generate Spec Doc** screen implemented (backend API + GUI).
- Phase 5 implemented and usable end-to-end (launch -> dashboard -> intake -> config editor).
- **Flat intake mode**, **per-screen spec overrides**, **configurable filename convention**, **still images / sequences**, and **spec generator v2 mapping** added (see `CHANGELOG.md`).
- Backend health reports `phase: 5` and `api_features: ["pick_delivery_source", "config_editor"]`.
- Browser dev and local backend communication are working with `/api` proxy and WebSocket support.
- CLI spec generation (`modules/spec_generator.py`) populates all template placeholders from `show_config.json` except the manual **Delivery Target** date.

## Completed work

### Phase 0 - Project scaffold

- Created Tauri + React frontend scaffold in `frontend/`.
- Created FastAPI backend scaffold in `backend/`.
- Promoted `modules/`, `templates/`, and `cli_intake.py` into v2 workspace.
- Added root `README.md`, `requirements.txt`, and startup scripts.

### Phase 1 - Backend foundations

- Implemented core show/config routes in `backend/routes/shows.py`:
  - recent shows, show load, migration, create show, config read/save.
- Added dashboard snapshot and delivery log API support.
- Added config write helpers in `modules/config.py` and show creation helpers in `modules/setup.py`.
- Added `build_intake_plan()` and progress-capable execution path in intake flow.

### Phase 2 - Launch and shell UI

- Implemented launch screen and show loading flow (`frontend/src/screens/LaunchScreen.tsx`).
- Added migration and new-show modal flows.
- Implemented sidebar show layout shell (`frontend/src/screens/ShowLayout.tsx`).
- Added backend phase guard in frontend startup.

### Phase 3 - Dashboard

- Implemented dashboard view (`frontend/src/screens/DashboardView.tsx`) with:
  - stat cards, warning banners, screen cards/compact mode, sortable file panel.
- Added persisted dashboard view preference (`PATCH /api/recent-shows/dashboard-view`).
- Added delivery log modal support.
- Added dashboard refresh and stale-backend error messaging.

### Phase 4 - Intake Delivery wizard

- Implemented 5-phase intake UI (`frontend/src/screens/IntakeView.tsx`):
  - folder select, scanning, plan table, copying, completion.
- Implemented intake API routes (`backend/routes/intake.py`):
  - scan/execute sync endpoints and WS endpoints.
- Wired execution logging and delivery log updates through `modules/intake.py`.
- Added robust intake error formatting and fallback behavior when WS cannot connect.
- Sidebar is disabled during active scan/copy operations.

### Phase 5 - Config Editor

- Enabled `Edit Config` sidebar navigation (`frontend/src/screens/ShowLayout.tsx`).
- Implemented tabbed config editor (`frontend/src/screens/ConfigView.tsx`):
  - Show Info, Expected Specs (presets/codecs), Screens, Validation tabs.
- Added client-side validation helpers (`frontend/src/lib/configValidation.ts`).
- Added preset/codec/config API routes:
  - `backend/routes/presets.py`, `backend/routes/codecs.py`
  - `GET/PUT /api/shows/config`, `POST /api/shows/open-config`
  - `GET /api/system/pick-file` for preset import.
- Config save refreshes dashboard and sidebar show name; dirty-state prompts on navigate away.

### Output spec mode uniform / per-screen (2026-06-18)

- Added `output_specs.mode` (`uniform` | `per_screen`) to config schema and starter template.
- Expected Specs tab: toggle for same vs varying video specs; conditional show-level fields.
- Screens tab: per-screen framerate, color space, color range when mode is `per_screen`.
- Fixed Custom framerate on screens (reuses `SpecSelect` with `pendingCustom` state).
- `effective_specs_for_screen()` updated for per-screen mode (no show-level inheritance).

### Flat intake and per-screen specs (2026-06-18)

- Extended `show_config.json` schema (backward compatible with v2):
  - `intake.mode`: `"routed"` (default) or `"flat"`.
  - `screens[].expected_specs`: optional per-screen overrides inheriting from show defaults.
- `modules/config.py`: `IntakeConfig`, `ScreenExpectedSpecs`, `effective_specs_for_screen()`, `find_screen()`.
- `modules/intake.py`: `plan_file_flat()`, `validate_file_specs_flat()`, union validation; copy to `Media/_INCOMING/`.
- `backend/routes/intake.py`: flat scan needs no `target_screen_id`.
- `frontend/src/screens/IntakeView.tsx`: flat intake scans source folder only (no screen picker).
- `frontend/src/screens/ConfigView.tsx`: intake mode toggle + per-screen framerate column.
- CLI `run_intake()` uses flat union validation without a batch screen prompt.
- See `CHANGELOG.md` for full release notes.

### Configurable filename convention (2026-06-18)

- Extended `show_config.json` with `filename_convention` (token order, version prefix, date format, loop suffix) and `delivery.show_token`.
- `modules/filename_parser.py`: config-aware `parse_filename()`, `build_example_filename()`, `build_filename_pattern()`, per-token diagnostics.
- `modules/config.py`: `FilenameConventionConfig`, `DeliveryConfig`, strictness for `filename_convention`, `filename_format`, `show_token`.
- Config Editor: drag-and-drop token builder, Default/Custom dropdown, live example filename on Expected Specs and Validation tabs.
- Intake validates filenames against convention strictness; partial matches now also run ffprobe spec checks.

### Intake UX and validation fixes (2026-06-18)

- Persist last intake source folder per show (`frontend/src/lib/intakeSourceStorage.ts`).
- Per-token filename error messages (not just underscore count); all filename + spec issues listed on partial matches.
- Fixed `validate_file_specs` early return that skipped codec/framerate when screen was unknown.

### Spec generator audit and v2 mapping (2026-06-18)

Audited `templates/spec_template.docx` (14 bracket placeholders). Enhanced `modules/spec_generator.py` to map all saved config fields:

| Template area | Config source |
|---|---|
| Project / show date / operator / screen count | `show_name`, `show_date`, `operator`, `screens` |
| Delivery Target `[YYYY-MM-DD]` | Left for manual entry (by design) |
| Screen table rows | `screens[].id`, `name`, `resolution`; Notes column shows per-screen video specs when `output_specs.mode` is `per_screen` |
| Frame rate row | `expected_specs.framerate` or per-screen note |
| Codec row | `preferred_codecs` + `expected_codecs` with human-readable labels |
| Color space row | `expected_specs.color_space` + `color_range`, or per-screen note |
| Audio row | `expected_specs.audio_sample_rate` + `audio_channels` |
| Filename pattern + example paragraphs | `filename_convention` + `delivery.show_token` via `build_filename_pattern()` / `build_example_filename()` |
| Folder root line | `{show_name}_{YYYYMMDD}/` from show date |
| Filename convention table | Rebuilt from configured token order (legacy 4-row table when convention disabled) |

Verified: only `[YYYY-MM-DD]` (delivery target) remains unreplaced after generation.

### Phase 6 — Generate Spec Doc GUI (2026-06-18)

- `backend/routes/spec.py`: `POST /api/spec/generate`, `POST /api/spec/open`.
- `frontend/src/screens/SpecView.tsx`: generate, success path display, open in default app, retry.
- Enabled **Spec Doc** sidebar nav and dashboard **Generate Spec** button.
- Health endpoint reports `phase: 6` with `spec_generator` feature flag.

### Spec generator content and formatting (2026-06-18)

- `operator.company_name` in config + Show Info field; populates `[Company Name]` in spec header.
- Codec row lists **preferred codecs only** via `[Codec]` placeholder.
- Filename pattern uses **raw token names** in saved order; example from `build_example_filename()`.
- Table row cloning + multi-run placeholder replacement preserves template fonts/colors (Calibri/Consolas).

### Config load vs save validation (2026-06-18)

- `load_config()` no longer runs save-time validation — existing shows open even with missing/invalid fields.
- `save_config()` still runs full `validate_config(for_save=True)` (company name, etc.).
- `delivery.vendor_notes` optional field for custom spec paragraphs.

### Spec supplemental sections (2026-06-18)

- **Screen diagram** paragraph lists screen count + per-screen native resolutions.
- **Intake mode note** inserted after folder structure (routed vs flat delivery instructions).
- **Vendor notes** section inserted before Key Rules when notes are set in config.

## Stability fixes completed

- Fixed Vite `EBUSY` issues in Dropbox by moving cache out of workspace.
- Added `scripts/start-backend.ps1` and `scripts/stop-backend.ps1` to reduce stale process/port conflicts.
- Added clearer stale-backend messages for missing routes.
- Fixed browse/scan 404 behaviors caused by stale backends.

## Known decisions and deferred items

- Intake browse currently uses the standard Windows folder dialog (no file preview in the native folder picker).
- Revisit media-preview picker in a later iteration (target: v2.1; needs drive switching).

## Planned updates (field testing — 2026-07-27)

Real-world show intake validated v2.1.x end-to-end. Three follow-ups surfaced from operator use. **Do not implement until scheduled** — details below for the next development pass.

### 1. Custom filename convention — truly optional tokens ✅ (shipped 2026-07-27)

**Problem:** Config → Expected Specs → Filename Convention → **Custom** lets operators remove tokens in the UI, but save fails unless all four default tokens (`screen`, `content`, `version`, `date`) remain in the pattern. Custom should allow any subset of available tokens (including none beyond routing requirements).

**Root cause (dual validation):**

- Frontend: `frontend/src/lib/configValidation.ts` — `REQUIRED_FILENAME_TOKENS` and `validateExpectedSpecs()` reject missing `screen`, `content`, `version`, `date` when custom convention is enabled.
- Backend: `modules/config.py` — `_validate_filename_convention()` hard-codes the same required set (`required = {"screen", "content", "version", "date"}`).

**Intended behavior:**

| Intake mode | Minimum tokens | Notes |
|---|---|---|
| Routed | `screen` only (when convention enabled) | Already enforced separately; keep this |
| Flat | None required | Operator may use e.g. `content` + `version` only, or `show_token` alone |

- Any combination of `show_token`, `initials`, `screen`, `content`, `version`, `date` is valid when custom is enabled.
- Pattern may be empty? **No** — keep “at least one token when `enabled: true`” (already enforced on backend).
- `show_token` in pattern still requires `delivery.show_token` in config (already enforced).
- Routed intake still requires `screen` in pattern (already enforced).
- Default (non-custom) convention unchanged: `SCR##_content_v##_YYYYMMDD`.

**Implementation checklist:**

1. **Frontend validation** (`configValidation.ts`):
   - Remove or narrow `REQUIRED_FILENAME_TOKENS` — only `screen` when `intake.mode === 'routed'`.
   - Update `FILENAME_TOKEN_META` optional flags: mark `content`, `version`, `date` as `optional: true` (UI hints only).
2. **Backend validation** (`modules/config.py` `_validate_filename_convention`):
   - Delete the `required = {"screen", "content", "version", "date"}` block; retain duplicate/unknown-token checks, non-empty tokens array, routed `screen` rule, and `show_token` coupling.
3. **Parser** (`modules/filename_parser.py`): Audit `parse_filename()` for patterns missing `version` or `date` — ensure `PartialMatch` / `FullMatch` logic does not assume all four tokens exist. Add unit cases in `scripts/test_filename_parser.py` (e.g. `SCR01_OpeningVideo.mov`, `OpeningVideo_v01.mov`).
4. **Examples / spec doc** (`build_example_filename`, `build_filename_pattern` in frontend + `modules/filename_parser.py` + `modules/spec_generator.py`): Confirm output reflects configured token subset only.
5. **Intake / dashboard**: Version conflict and slug detection may assume `version` token — review `modules/intake.py` conflict scanning when `version` is omitted from convention.
6. **Tests**: Mirror frontend rules in any config save tests; run `scripts/run-tests.ps1`.

### 2. Still images and image sequences ✅ (shipped 2026-07-27)

**Problem:** Tool is video-centric. Shows often deliver still frames and numbered image sequences (`.jpg`, `.png`, `.tga`, `.tiff` / `.tif`, `.exr`). These must be configurable expected formats and probeable via FFmpeg/ffprobe during intake and dashboard validation.

**Scope:**

- **Still image** — single file, one frame (e.g. `SCR01_Backdrop_v01_20260727.png`).
- **Image sequence** — numbered series sharing a slug/prefix (e.g. `SCR01_Fire_0001.tga` … `SCR01_Fire_0120.tga`). Intake should recognize the sequence as one logical asset (group frames), validate resolution once, and copy/route consistently (operator expectation: either all frames or a defined representative — decide in implementation).

**Config additions (schema — backward compatible):**

```json
"expected_media": {
  "video_extensions": [".mov", ".mp4", ...],   // optional; default current implicit video set
  "image_extensions": [".jpg", ".jpeg", ".png", ".tga", ".tif", ".tiff", ".exr"],
  "allow_image_sequences": true
}
```

- Expected Specs tab: toggles / extension list for images; note that video codec fields do not apply to stills.
- Consider `media_type` on probed files: `video` | `image` | `image_sequence` | `audio` (future).

**FFprobe / FFmpeg (`modules/ffprobe_wrapper.py`):**

- ffprobe already returns `width` / `height` for many still formats when invoked with `-show_streams`.
- Add `media_kind` (or similar) on `MediaSpecs`: derive from `codec_type` (`video` stream on a single-frame file → `image`) and absence of time-based fields.
- Verify bundled FFmpeg build probes `.tga`, `.tiff`, `.exr` on Windows — document any format that fails and whether to accept resolution-only validation or route to `_REVIEW`.
- Image sequences: detect via shared stem + numeric suffix pattern in `walk_source` or a pre-pass grouper before `plan_file()`; avoid treating each frame as a separate conflicting version.

**Validation (`modules/intake.py`, `modules/dashboard_files.py`):**

- When `media_kind` is `image` or `image_sequence`:
  - Apply **resolution** strictness against screen config.
  - Skip or auto-ignore **framerate**, **codec**, **color_space** / **color_range** (unless EXR color metadata is required later), **audio** — mirror existing N/A spec handling.
- Filename convention: same token rules as video; extension is not part of convention tokens today (`.ext` placeholder only).

**Intake UX (`IntakeView.tsx`):**

- Plan table: show media type column or icon; group sequence rows or show “120 frames” summary.
- Copy: all sequence frames to destination folder; preserve original names.

**Spec generator (`modules/spec_generator.py`):**

- Add row or bullet for accepted still / sequence formats from config.
- Example filename for images: use configured extension (e.g. `.png`) in `build_example_filename` when image formats are enabled.

**Tests:**

- Fixture files or mocked `MediaSpecs` for image vs video validation paths.
- Sequence grouping tests in `scripts/test_intake_routing.py`.
- ffprobe integration smoke test for at least one format per family (jpg, png, exr) if small fixtures are added to `scripts/fixtures/`.

**Docs:** Update `README.md` operator section when shipped.

### 3. Hide launcher terminal window on startup

**Problem:** Launching from the desktop shortcut opens a black PowerShell/Terminal window showing `Starting backend...` and `OK Backend ready on http://127.0.0.1:18080`. It stays open for the entire session until the GUI is closed. Operators expect a normal desktop app with no console.

**What is actually visible:** The **launcher** PowerShell process (`scripts/Launch Show Media Intake Tool.ps1`), not the backend. The backend is already started with `-WindowStyle Hidden` (line 31–35 of Launch.ps1). The Tauri `.exe` already uses `windows_subsystem = "windows"` (no console). The launcher remains visible because:

1. Desktop shortcut (`setup.ps1` → `New-DesktopShortcut`) invokes `powershell.exe` **without** `-WindowStyle Hidden`.
2. `Launch Show Media Intake Tool.cmd` also starts PowerShell visibly.
3. Launch.ps1 calls `$app.WaitForExit()` — the launcher process must stay alive to stop the backend on exit, so the console window persists.

**Recommended fix (low risk — ship in next patch):**

Hide the launcher PowerShell window while keeping the same lifecycle (start backend → open GUI → wait → cleanup).

1. **`scripts/Launch Show Media Intake Tool.cmd`** — add `-WindowStyle Hidden` to the `powershell` invocation.
2. **`scripts/setup.ps1`** — desktop shortcut arguments: prepend `-WindowStyle Hidden` to the `-NoProfile -ExecutionPolicy Bypass -File ...` string so new shortcuts are correct.
3. **`scripts/Launch Show Media Intake Tool.ps1`** — on every **error exit** path (setup not run, backend timeout, ffprobe missing, exe missing), show a **Win32 message box** instead of relying on `Write-Host` in a hidden window. Add helper in `packaging-common.ps1`, e.g. `Show-OperatorError -Message "..."` using `[System.Windows.Forms.MessageBox]` or `WScript.Shell.Popup`. Keep writing details to `backend.log` where applicable.
4. **Optional:** Remove or gate success `Write-Host` lines when running hidden (no visible benefit).
5. **Dev workflow unchanged:** `scripts/dev.ps1`, `scripts/start-backend.ps1` (dev `.venv` path), and `scripts/setup-dev.ps1` keep a visible console for developers.

**Operator upgrade path:** Existing desktop shortcuts created before this fix will still show a console until the operator re-runs `scripts\setup.cmd` (recreates shortcuts) or manually edits the shortcut to add `-WindowStyle Hidden`.

**Verification:**

- Launch from desktop shortcut → only the GUI appears; no terminal flash or persistent window.
- Close GUI → backend stops (port 18080 free); confirm with `scripts\stop-backend.ps1` or health poll.
- Force failure (stop setup / kill python) → message box with actionable text, not a silent exit.
- Re-run `scripts\smoke-test-release.ps1` if it covers launch lifecycle.

**Long-term option (larger — optional v2.3+):**

Wire backend spawn/cleanup inside Tauri (`tauri-plugin-shell` or Rust `std::process::Command` with `CREATE_NO_WINDOW` on Windows) so the desktop shortcut can target `Show Media Intake Tool.exe` directly. `Launch.ps1` becomes dev/fallback only. See `PACKAGING.md` § Launch future enhancement.

### 4. Dashboard Explorer — open folder on top (planned)

**Problem:** On the dashboard, clicking the folder icon (screen folder or per-file **Show in File Explorer**) opens Windows Explorer **behind** the main application window. Operators must hunt for the Explorer window.

**Intended behavior:** Explorer should open **in front of all windows** (or at least in front of the app) so the target folder is immediately visible.

**Likely touch points:**

- `modules/setup.py` — `open_in_explorer()` uses `os.startfile()` and `explorer /select,` without foreground flags.
- `backend/routes/system.py` — `POST /api/system/open-path` delegates to `open_in_explorer`.
- Windows options to investigate: `explorer` with focus tricks, `Shell.Application` COM `Explore()` + `BringToFront`, or spawning Explorer then `SetForegroundWindow` on the new process window.

**Verification:** From dashboard with app focused, click folder icon on SCR03 file row → Explorer appears on top showing `Media\SCR03\`.

---

## Remaining work

### Packaging and acceptance

- [x] Packaging scripts (`setup.ps1`, Launch script, `build-release.ps1`) — see `PACKAGING.md`
- [x] Initial release zip built: `dist\ShowMediaIntakeTool-v2.0.0-win64.zip` (2026-06-18)
- [x] Version sync + changelog for **2.1.0** (2026-06-19)
- [x] Build `dist\ShowMediaIntakeTool-v2.1.0-win64.zip` (2026-06-19)
- [x] Fix filename pattern drag reorder (pointer-based; WebView2)
- [x] Build `dist\ShowMediaIntakeTool-v2.1.1-win64.zip` (2026-06-20)
- [x] Test on a clean Windows VM (no Python on PATH) — v2.1.1 verified 2026-06-20
- [x] Build `dist\ShowMediaIntakeTool-v2.2.0-win64.zip` (2026-07-28)
- [ ] Final integration and acceptance testing against DESIGN-V2 checklist
- [x] **Custom filename convention** — optional tokens (see Planned updates §1)
- [x] **Still images and image sequences** — config, ffprobe, validation (see Planned updates §2)
- [ ] **Hide launcher terminal window** — hidden PowerShell + error dialogs (see Planned updates §3)
- [ ] **Dashboard Explorer on top** — foreground Explorer when opening paths from dashboard (see Planned updates §4)

