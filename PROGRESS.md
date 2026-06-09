# Show Media Intake Tool v2 - Progress Log

Last updated: 2026-06-09

## Current status

- Phase 5 implemented and usable end-to-end (launch -> dashboard -> intake -> config editor).
- Backend health reports `phase: 5` and `api_features: ["pick_delivery_source", "config_editor"]`.
- Browser dev and local backend communication are working with `/api` proxy and WebSocket support.

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

## Stability fixes completed

- Fixed Vite `EBUSY` issues in Dropbox by moving cache out of workspace.
- Added `scripts/start-backend.ps1` and `scripts/stop-backend.ps1` to reduce stale process/port conflicts.
- Added clearer stale-backend messages for missing routes.
- Fixed browse/scan 404 behaviors caused by stale backends.

## Known decisions and deferred items

- Intake browse currently uses the standard Windows folder dialog (no file preview in the native folder picker).
- A prototype media-preview picker exists at `modules/delivery_folder_picker.py` but was reverted for now due to drive-navigation UX limitations.
- Revisit media-preview picker in a later iteration (target: v2.1).

## Remaining work

### Phase 6 - Generate Spec Doc and packaging (next recommended)

- Implement `Generate Spec Doc` screen.
- Add packaging/deployment workflow for `C:\Tools\ShowMediaIntakeTool\`.
- Final integration and acceptance testing against DESIGN-V2 checklist.

