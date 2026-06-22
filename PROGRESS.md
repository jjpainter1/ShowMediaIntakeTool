# Show Media Intake Tool v2 - Progress Log

Last updated: 2026-06-18

## Current status

- Phase 6 **Generate Spec Doc** screen implemented (backend API + GUI).
- Phase 5 implemented and usable end-to-end (launch -> dashboard -> intake -> config editor).
- **Flat intake mode**, **per-screen spec overrides**, **configurable filename convention**, and **spec generator v2 mapping** added (see `CHANGELOG.md`).
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

## Remaining work

### Packaging and acceptance

- [x] Packaging scripts (`setup.ps1`, Launch script, `build-release.ps1`) — see `PACKAGING.md`
- [x] Initial release zip built: `dist\ShowMediaIntakeTool-v2.0.0-win64.zip` (2026-06-18)
- [x] Version sync + changelog for **2.1.0** (2026-06-19)
- [x] Build `dist\ShowMediaIntakeTool-v2.1.0-win64.zip` (2026-06-19)
- [x] Fix filename pattern drag reorder (pointer-based; WebView2)
- [x] Build `dist\ShowMediaIntakeTool-v2.1.1-win64.zip` (2026-06-20)
- [x] Test on a clean Windows VM (no Python on PATH) — v2.1.1 verified 2026-06-20
- [ ] Final integration and acceptance testing against DESIGN-V2 checklist

