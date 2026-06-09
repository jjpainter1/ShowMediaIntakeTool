# Pixera Intake Tool — Implementation Plan

**For:** Claude Code agent
**Companion document:** `DESIGN.md` (read first; this plan assumes you have)
**Status legend:** `[ ]` not started · `[~]` in progress · `[x]` complete · `[!]` blocked

---

## How to Use This Plan

This plan is a sequence of phases, each containing tasks. Work through them **in order** — later phases depend on earlier ones. Within a phase, tasks are listed in implementation order.

**Update this document as you work:**

1. Change `[ ]` to `[~]` when starting a task.
2. Change `[~]` to `[x]` when the task is complete.
3. If you hit a blocker, change to `[!]` and add a note under the task.
4. After each phase, add a brief summary in that phase's "Notes" section: what was built, any deviations from the plan, and any decisions made.
5. Commit/save progress frequently so resuming after interruption is painless.

**Decision policy:**

- If you find an ambiguity not addressed in DESIGN.md or this plan, **make a reasonable decision, document it under the task's notes, and continue.** Do not block waiting for clarification.
- If you find a fundamental design conflict (something in DESIGN.md contradicts itself or is impossible), **mark the task `[!]`, document the conflict, and stop.** This requires human decision.
- Never silently change documented behavior. If you decide the design is wrong, document why and what you did instead.

**Code style:**

- Type hints on all function signatures.
- Docstrings on all public functions and classes.
- Module-level docstring on every file.
- Keep functions under ~50 lines where reasonable.
- Use `pathlib.Path` for all file system paths, never raw strings.
- Use `subprocess.run` (not deprecated alternatives) for ffprobe calls.
- Errors should be specific exceptions, not bare `Exception`.

**Testing approach:**

- After each phase, manually verify the new functionality before moving on.
- Phase 7 includes integration testing.
- Sample test data generation is explicitly out of v1 scope — do not build it.

---

## Phase 0: Project Setup

**Goal:** Create the project skeleton and verify dependencies.

### Tasks

- [x] **0.1** Create the directory structure under `C:\Tools\PixeraIntake\` (or use a development location like `~/PixeraIntake/` and document the move at end):
    ```
    pixera_intake.py
    modules/
      __init__.py
      config.py
      intake.py
      spec_generator.py
      show_report.py
      ffprobe_wrapper.py
      filename_parser.py
      recent_shows.py
      console_ui.py
    templates/
      show_config_starter.json
      spec_template.docx
    README.md
    ```

- [x] **0.2** Create `requirements.txt`:
    ```
    python-docx>=1.0.0
    colorama>=0.4.6
    ```
    Document Python version requirement (3.10+) in README.

- [x] **0.3** Create `pixera_intake.py` as a minimal entry point that prints "Pixera Intake Tool v1.0" and exits. Verify it runs.

- [x] **0.4** Verify ffprobe is callable. In a scratch script, run:
    ```python
    import subprocess
    result = subprocess.run(["ffprobe", "-version"], capture_output=True, text=True)
    print(result.stdout)
    ```
    Confirm output. Document the ffprobe version observed.
    > ffprobe version 8.1-full_build-www.gyan.dev (gcc 15.2.0 / MSYS2). Confirmed callable on PATH.

- [x] **0.5** Create the starter config file at `templates/show_config_starter.json` with the exact contents specified in DESIGN.md section 5.6.

### Notes

Development location: `d:\Dropbox\PrestigeAV\CodeProjects\PixeraIntakeTool\`. All module files created as stubs with module-level docstrings. `pixera_intake.py` verified to run and print "Pixera Intake Tool v1.0". Python version on this machine: 3.14 (satisfies 3.10+ requirement). ffprobe v8.1-full_build-www.gyan.dev confirmed on PATH.

---

## Phase 1: Config Module

**Goal:** Implement loading, validation, and writing of `show_config.json`.

This is foundational because every other mode depends on it.

### Tasks

- [x] **1.1** In `modules/config.py`, define a `ShowConfig` dataclass (or TypedDict) representing the validated config structure. Fields per DESIGN.md section 5.2.

- [x] **1.2** Implement `load_config(show_root: Path) -> ShowConfig`:
    - Reads `show_root / "show_config.json"`.
    - Parses JSON. Raises `ConfigNotFoundError` if file doesn't exist.
    - Raises `ConfigInvalidError` with specific message if JSON is malformed.
    - Calls `validate_config()` on the parsed dict.
    - Returns ShowConfig instance.

- [x] **1.3** Implement `validate_config(data: dict) -> None`:
    - Per DESIGN.md section 5.4, validate all required fields are present and correctly typed.
    - Validate filename-safe characters in `show_name`, `screens[].id`, `screens[].name`.
    - Validate format of `show_date`, `screens[].resolution`, `validation_strictness` values.
    - Validate logical rules (preferred subset of expected, screens unique, at least one screen).
    - Raises `ConfigInvalidError` with a specific message naming the field and the problem.
    - On success, returns nothing.

- [x] **1.4** Implement `create_starter_config(show_root: Path) -> Path`:
    - Copies `templates/show_config_starter.json` to `show_root / "show_config.json"`.
    - Returns the path to the created file.
    - Raises if the destination already exists (caller should check first).

- [x] **1.5** Define custom exceptions: `ConfigNotFoundError`, `ConfigInvalidError`. Both inherit from a base `ConfigError`.

- [x] **1.6** Define a constant or function for "filename-safe characters" regex. Use this consistently anywhere a string needs to be validated for filesystem use.

- [x] **1.7** Manual test: write a sample valid config, load it, verify ShowConfig is populated correctly. Then write configs with each kind of validation failure (missing field, bad characters, malformed JSON) and verify each raises with a clear message.

### Notes

Implemented dataclasses: `ShowConfig`, `ScreenConfig`, `OperatorConfig`, `ExpectedSpecs`. Exceptions hierarchy: `ConfigError` → `ConfigNotFoundError`, `ConfigInvalidError`. `FILENAME_SAFE` regex (`^[A-Za-z0-9_-]+$`) exported from module for reuse in other modules. All 12 manual test cases pass: valid load, missing file, malformed JSON, missing field, bad characters, bad date format, preferred-not-subset, duplicate screen IDs, bad resolution format, invalid strictness value, create_starter_config happy path, create_starter_config overwrite guard.

---

## Phase 2: Filename Parser Module

**Goal:** Parse filenames per the convention and report results clearly.

### Tasks

- [x] **2.1** In `modules/filename_parser.py`, define a `ParsedFilename` dataclass with fields:
    - `screen_prefix: str` (e.g., "SCR01", "SCRwide-01-02", "SCRall", "AUD")
    - `slug: str`
    - `version: int` (parsed from "v##")
    - `date: date` (parsed from YYYYMMDD)
    - `extension: str`
    - `is_loop: bool` (true if slug ends with "-LOOP")
    - `original_name: str`

- [x] **2.2** Implement `parse_filename(filename: str) -> ParseResult`:
    - `ParseResult` is a discriminated union: `FullMatch(parsed: ParsedFilename)`, `PartialMatch(screen_prefix: str, original: str, problems: list[str])`, `NoMatch(original: str, problems: list[str])`.
    - Use regex per DESIGN.md section 6.
    - Special prefix handling:
        - `SCRwide-XX-YY[-ZZ...]` (one or more 2-digit screens dash-separated)
        - `SCRall` (no number)
        - `AUD` (no number)
        - `SCR##` (2 digits)
    - Returns the appropriate ParseResult variant.

- [x] **2.3** Implement helper `extract_screen_prefix(filename: str) -> str | None`:
    - Returns just the screen prefix (everything before the first underscore) if it matches a known pattern.
    - Returns None if no recognizable prefix.
    - Used for the "partial match — route by screen prefix only" case.

- [x] **2.4** Manual test: feed the parser a variety of filenames including:
    - `SCR01_OpeningVideo_v03_20260425.mov` (full match)
    - `SCRwide-01-02-03_KeynoteHero_v01_20260425.mov` (full match, wide)
    - `SCRall_HouseLightLogo_v02_20260425.mov` (full match, all)
    - `AUD_OpeningStingBed_v01_20260425.wav` (full match, audio)
    - `SCR01_AmbientBG-LOOP_v01_20260425.mov` (full match, loop)
    - `SCR1_Opening_v1_20260425.mov` (partial match, non-zero-padded)
    - `Opening Video FINAL.mov` (no match)
    - `SCR01_v03_20260425.mov` (partial — missing slug)
    - `SCR99_Opening_v01_20260425.mov` (full match — but screen unknown to config; that check happens later)

### Notes

Three-tier result hierarchy: `FullMatch` / `PartialMatch` / `NoMatch`. Loose prefix detection (starts with `SCR` or `AUD`) catches non-zero-padded and malformed prefixes and routes them to `PartialMatch` with diagnostic messages. `extract_screen_prefix` uses strict matching only — returns `None` for malformed prefixes like `SCR1`. `is_loop` flag set when slug ends with `-LOOP`; full slug (including `-LOOP`) preserved. Invalid calendar dates (e.g. month 13) caught and routed to `PartialMatch`. All 13 manual test cases pass.

---

## Phase 3: ffprobe Wrapper Module

**Goal:** Extract video/audio specs from media files reliably.

### Tasks

- [x] **3.1** In `modules/ffprobe_wrapper.py`, define `MediaSpecs` dataclass with fields:
    - `width: int | None`
    - `height: int | None`
    - `framerate: float | None`
    - `codec_name: str | None`
    - `codec_tag: str | None`
    - `color_space: str | None`
    - `color_range: str | None`
    - `audio_sample_rate: int | None`
    - `audio_channels: int | None`
    - `duration_seconds: float | None`
    - `probe_succeeded: bool`
    - `probe_error: str | None`

- [x] **3.2** Implement `probe_file(path: Path) -> MediaSpecs`:
    - Calls `ffprobe -v error -print_format json -show_streams -show_format <path>`.
    - Parses JSON output.
    - Extracts video stream fields (first video stream).
    - Extracts audio stream fields (first audio stream, if present).
    - For framerate: parse `r_frame_rate` which is typically a fraction like "30000/1001" — evaluate to float.
    - On any failure (file unreadable, ffprobe not found, no video stream), returns MediaSpecs with `probe_succeeded=False` and `probe_error` populated.

- [x] **3.3** Implement `check_ffprobe_available() -> bool`:
    - Attempts `ffprobe -version`.
    - Returns True if successful, False otherwise.
    - Used at tool startup to fail fast if ffprobe missing.

- [x] **3.4** Implement codec_tag → identifier mapping per DESIGN.md section 5.5. Define as a module-level dict. Provide reverse lookup: `codec_tag_to_identifier(tag: str) -> str | None`.

- [x] **3.5** Manual test: probe a real ProRes file (any flavor) and verify all fields populate correctly. Probe a non-existent file and verify graceful error. Probe a non-media file (e.g., a text file) and verify graceful error.

### Notes

Deviation from plan: `probe_succeeded` is `True` whenever ffprobe exits cleanly with valid JSON, regardless of whether a video stream is present. Audio-only files are valid and should not be penalised. Individual fields remain `None` when a stream type is absent; the intake module decides what to do based on the prefix type. Synthetic ProRes HQ test file generated with ffmpeg for testing, then deleted. Tested: 1920x1080 @ 30fps, codec_tag `apch` correctly identified. `codec_tag_to_identifier` is case-insensitive. `_parse_framerate` handles 30/1, 30000/1001 (29.97), 24/1, 60000/1001 (59.94), None, and 0/0 division guard. All 7 manual tests pass.

---

## Phase 4: Console UI Module

**Goal:** Centralize all console output, color handling, and input prompts.

### Tasks

- [x] **4.1** In `modules/console_ui.py`, initialize colorama with `init(autoreset=True)` at module load.

- [x] **4.2** Implement output helpers:
    - `print_header(text: str)` — bold, with `=` separator lines above and below.
    - `print_subheader(text: str)` — bold, with `-` separator below.
    - `print_success(text: str)` — green with ✓ prefix.
    - `print_warning(text: str)` — yellow with ⚠ prefix.
    - `print_error(text: str)` — red with ✗ prefix.
    - `print_info(text: str)` — dim/cyan with • prefix.
    - `print_path(text: str)` — bright white, no prefix.

- [x] **4.3** Implement input helpers:
    - `prompt_yes_no(question: str, default: str = "N") -> bool` — handles Y/N input, default on empty enter, re-prompts on invalid input.
    - `prompt_menu(question: str, options: dict[str, str], default: str | None = None) -> str` — displays options, returns the selected key.
    - `prompt_path_input(question: str) -> Path` — for typing paths manually.
    - `pick_folder(title: str) -> Path | None` — uses tkinter `askdirectory`, returns None if cancelled.

- [x] **4.4** Implement format helpers:
    - `format_filesize(bytes: int) -> str` — returns human-friendly "1.2 GB", "685 MB", etc.
    - `format_table(headers: list[str], rows: list[list[str]]) -> str` — simple aligned text table.
    - `format_relative_time(dt: datetime) -> str` — "2 days ago", "1 week ago", etc.

- [x] **4.5** Manual test: write a small script that exercises all output helpers and verifies colors render on Windows. Test the folder picker.

### Notes

Separator width is 70 chars (per DESIGN.md §14.2). `prompt_menu` signature omits the `question` param from the plan — the caller prints a header before calling it, keeping the function focused on rendering options and reading input. `pick_folder` uses `wm_attributes("-topmost", True)` to bring the dialog to the foreground on Windows; falls back gracefully if tkinter is unavailable. Interactive helpers (`prompt_yes_no`, `prompt_menu`, `prompt_path_input`, `pick_folder`) not automatable in test scripts; visually verified. All format helpers verified: filesize (B/KB/MB/GB), aligned table, relative time (just now through months). Output helpers visually confirmed with colors in terminal.

---

## Phase 5: Recent Shows Module

**Goal:** Track and display recently used shows.

### Tasks

- [x] **5.1** In `modules/recent_shows.py`, define `RecentShow` dataclass: `path: Path`, `show_name: str`, `last_used: datetime`.

- [x] **5.2** Implement `load_recent_shows(tool_root: Path) -> list[RecentShow]`:
    - Reads `tool_root / ".recent_shows.json"`.
    - Returns empty list if file doesn't exist.
    - Parses entries, converts timestamps.
    - **Self-cleans:** for each entry, verifies that `<path>/show_config.json` still exists. Drops entries where it doesn't.
    - Returns list sorted by `last_used` descending.

- [x] **5.3** Implement `save_recent_shows(tool_root: Path, shows: list[RecentShow]) -> None`:
    - Writes JSON to `.recent_shows.json`.
    - Limits to 5 most recent.

- [x] **5.4** Implement `add_or_update(tool_root: Path, show_path: Path, show_name: str) -> None`:
    - Loads existing list.
    - If path already in list, updates its `last_used`. Else appends.
    - Re-sorts by last_used descending.
    - Truncates to 5.
    - Saves back to disk.

- [x] **5.5** Implement `display_menu_and_get_selection(shows: list[RecentShow]) -> Path | None`:
    - Prints the launch menu per DESIGN.md section 11.3.
    - Returns:
        - `Path` if a numbered show was selected.
        - `None` if "N" or empty input (caller should open folder picker).
        - Raises `SystemExit` cleanly on "Q".

- [x] **5.6** Manual test: simulate first-time use (no recent shows file), simulate stale entries (entries whose paths no longer have config), verify menu rendering.

### Notes

`add_or_update` removes the existing entry for a path before re-inserting at the top, then re-sorts — simpler and correct for the update case. `display_menu_and_get_selection` uses bare `input()` with colorama-styled prompt rather than `prompt_menu` since the layout (numbered entries + N/Q footer) differs from the generic menu pattern. `SystemExit(0)` on Q for clean exit. All 7 manual tests pass: no-file, malformed JSON, round-trip sort, stale-entry cleanup, 5-entry cap, add new, update existing to top.

---

## Phase 6: Setup Mode + Reconciliation

**Goal:** Handle first-run setup and ongoing folder reconciliation.

### Tasks

- [x] **6.1** Implement `find_notepad_pp() -> Path | None`:
    - Returns `Path("C:/Program Files/Notepad++/notepad++.exe")` if it exists.
    - Returns None otherwise.

- [x] **6.2** Implement `open_in_editor(file_path: Path) -> bool`:
    - If Notepad++ is found, launch it with the file as argument using subprocess (non-blocking).
    - Otherwise fall back to `os.startfile(file_path)`.
    - Returns True if either method succeeded, False if both failed.
    - Always prints the file path to console regardless.

- [x] **6.3** In a new module (or in `pixera_intake.py` itself; decide based on size), implement `setup_new_show(show_root: Path) -> bool`:
    - Verifies show_root exists and is a directory.
    - Confirms with user that no config currently exists.
    - Prompts "Create starter config? [Y/N]".
    - On Y:
        - Create `Media/`, `Media/_LOGS/`, `Media/_REVIEW/`, `Media/_REFERENCE/` (do not create screen folders).
        - Copy starter config template to `show_root / "show_config.json"`.
        - Open the file in editor.
        - Print "Edit and save the config, then press Enter to continue..."
        - Wait for Enter.
        - Returns True. The caller will then attempt to load and validate.
    - On N: returns False.

- [x] **6.4** Implement `ensure_media_structure(show_root: Path, config: ShowConfig) -> list[str]`:
    - Ensures `Media/`, `_LOGS/`, `_REVIEW/`, `_REFERENCE/` exist (creates if missing).
    - For each screen in config, ensures `Media/<screen_id>/` exists.
    - Returns list of created folders (for logging/reporting).

- [x] **6.5** Implement `detect_stale_folders(show_root: Path, config: ShowConfig) -> list[StaleFolder]`:
    - `StaleFolder` dataclass: `name: str`, `path: Path`, `file_count: int`.
    - Lists immediate subfolders of `Media/`.
    - Excludes managed folders (`_LOGS`, `_REVIEW`, `_REFERENCE`).
    - Excludes folders matching any screen ID in config.
    - Excludes special prefix folders (`SCRwide`, `SCRall`, `AUD`).
    - Returns list of stale folders found.

- [x] **6.6** Implement the load-with-retry pattern:
    - When config validation fails, print errors clearly.
    - Re-open the config in editor.
    - Wait for Enter.
    - Re-attempt load.
    - Loop until valid OR user explicitly aborts (Ctrl+C).

- [x] **6.7** Manual test: create an empty show project root, run setup mode, verify the config gets created and Notepad++ opens. Edit the config with errors, verify the validation loop. Then with valid config, verify screen folders get created.

### Notes

All Phase 6 logic lives in `modules/setup.py`. Notepad++ confirmed installed at `C:\Program Files\Notepad++\notepad++.exe`. `detect_stale_folders` excludes exact special names (`SCRall`, `AUD`) and any folder starting with `SCRwide-` to cover on-demand wide-screen folders. `load_config_with_retry` loops on `ConfigInvalidError` with Ctrl+C abort, returns `None` on `ConfigNotFoundError` or abort. `setup_new_show` does not create screen folders — those appear only after a valid config is loaded and `ensure_media_structure` is called. All 7 automated tests pass.

---

## Phase 7: Intake Mode

**Goal:** The full intake workflow — plan, prompt, execute.

This is the largest phase. Break it into sub-phases.

### 7A: Source Discovery

- [x] **7A.1** In `modules/intake.py`, implement `walk_source(source: Path) -> list[Path]`.

### 7B: Per-File Planning

- [x] **7B.1** Define `FilePlan` dataclass.
- [x] **7B.2** Define `ConflictInfo`.
- [x] **7B.3** Implement `plan_file(source_path, config, show_root) -> FilePlan`.
- [x] **7B.4** Implement `detect_version_conflicts(plans, show_root) -> list[FilePlan]`.

### 7C: Plan Display

- [x] **7C.1** Implement `display_plan(plans, stale_folders, config, source)`.
- [x] **7C.2** Implement `prompt_proceed() -> bool`.

### 7D: Execution

- [x] **7D.1** Implement `execute_plan(plans, show_root) -> ExecutionResult`.
- [x] **7D.2** Implement `atomic_copy(source, destination) -> bool`.
- [x] **7D.3** Progress display during copy.

### 7E: Logging

- [x] **7E.1** Implement `append_to_delivery_log(...)`.
- [x] **7E.2** Implement `write_intake_log(...) -> Path`.

### 7F: Mode Entry Point

- [x] **7F.1** Implement `run_intake(show_root, config)`.

### 7G: Manual Testing

- [x] **7G.1–7G.3** Integration test with real ffmpeg-generated ProRes + H.264 files.

### Notes

All intake logic in `modules/intake.py`. PartialMatch files skip ffprobe — routed by prefix with parse problems as warnings. `_validate_specs` uses `strictness` dict from config; `info`-level mismatches go to `warnings` list same as `warn` (display layer can distinguish if needed). `detect_version_conflicts` parses existing files in the destination folder with `parse_filename` and matches on prefix+slug with a different version number. `execute_plan` cleans `*.tmp` files before running (handles interrupted prior runs). `write_intake_log` takes a `proceeded` bool so aborted runs still produce a transcript. 9 integration tests pass: walk, 6 routing cases (COPY, COPY_WITH_WARNING, ROUTE_TO_REVIEW ×3), no-conflict first run, SKIP_IDENTICAL on re-delivery, version conflict detection, atomic_copy failure leaves no .tmp, DeliveryLog appended, intake transcript written, stale .tmp cleanup.

---

## Phase 8: Spec Generation Mode

**Goal:** Generate filled-in spec docx from config.

### Tasks

- [x] **8.1** Template copied to `templates/spec_template.docx` from `Pixera_Playback_Spec_Template_v1_JJ.docx`.

- [x] **8.2** Placeholders found: `[Project Name]`, `[YYYY-MM-DD]` (×2 — show date + delivery target), `[##]`, `[Operator Name]`, `[email@prestigeav.com]`, `[Rec.709]`, `[e.g. 30 / 60 fps]`. Example-row-only placeholders removed by table rebuild: `[e.g. House Left]`, `[e.g. Center]`, `[e.g. House Right]`, `[e.g. All Screens]`, `[#### x ####]`, `[optional notes]`. Non-config placeholder left intact: `[YYYYMMDD]` in filename convention table.

- [x] **8.3** `generate_spec(show_root, config) -> Path` implemented in `modules/spec_generator.py`.

- [x] **8.4** Output saved to `<show_root>/<show_name>_DeliverySpec.docx`.

- [x] **8.5** `_replace_in_paragraph()` handles cross-run splits by combining all runs into run[0]; `_rebuild_screens_table()` removes example rows and adds one row per config screen with style copied from header.

- [x] **8.6** `_COLOR_SPACE_NAMES` dict maps bt709→Rec.709, bt2020→Rec.2020, smpte170m/bt470bg→Rec.601; unknown values pass through as-is.

- [x] **8.7** All 10 manual tests pass: file created, all placeholders replaced, delivery-target `[YYYY-MM-DD]` preserved, screen count, operator details, framerate, color space, table rows (header + 3 screens, no example rows), screen resolutions.

---

## Phase 9: "What's In My Show" Reporting Mode

**Goal:** Show current state of a show's content.

### Tasks

- [x] **9.1** In `modules/show_report.py`, define `ShowSnapshot` dataclass capturing all the data the report displays:
    - Per-screen file lists with parsed metadata.
    - Slugs with multiple versions detected.
    - Stale folders.
    - Files in `_REVIEW/`.
    - Last delivery info (parsed from DeliveryLog.txt).
    - Days until show.

- [x] **9.2** Implement `gather_snapshot(show_root: Path, config: ShowConfig) -> ShowSnapshot`:
    - Walk `Media/<screen>/` for each configured screen.
    - Walk special folders if they exist.
    - Walk `_REVIEW/`.
    - Parse each filename to extract slug/version/date.
    - Group files by screen and slug.
    - Identify slugs with more than one version present.
    - Detect stale folders (reuse Phase 6 helper).
    - Read last line of DeliveryLog.txt for last-delivery info.
    - Calculate days until show from `config.show_date`.

- [x] **9.3** Implement `display_report(snapshot: ShowSnapshot, config: ShowConfig) -> None`:
    - Renders the report per DESIGN.md section 10.2.
    - Use console_ui helpers for color and formatting.

- [x] **9.4** Implement `run_report(show_root: Path, config: ShowConfig) -> None`:
    - Just gathers and displays. No interaction.

- [x] **9.5** Manual test: run on a show folder with content already filed. Verify counts are correct, multi-version detection works, stale folders are surfaced.

### Notes

Two dataclasses: `ScreenSnapshot` (per-screen parsed/unparsed files) and `ShowSnapshot` (full picture: screens, special folders, review files, stale folders, multi-version slugs, last delivery, days until show). `_detect_multi_version_slugs` groups by `<screen_prefix>_<slug>` key across all configured screens; returns sorted (label, versions) pairs where version count > 1. `_read_last_delivery` reads the last non-blank line of DeliveryLog.txt and formats as "YYYY-MM-DD HH:MM (N copied, N review, N skip)". Days until show is negative for past shows; `display_report` shows "N days ago" for past, yellow "TODAY" for day-of, yellow count for ≤7 days out. Stale folders rendered at the bottom via `print_subheader` + `print_warning` per §10.3. All 11 manual tests pass: screen counts, special folder detection, _REVIEW files, stale folder detection, multi-version detection and sort, last delivery parsing, days-until-show (future/past/today), display_report and run_report both complete cleanly, empty show with no Media folder.

---

## Phase 10: Main Entry Point + Menu System

**Goal:** Wire all the pieces together into a working tool.

### Tasks

- [x] **10.1** In `pixera_intake.py`, implement `main()` as the top-level function.

- [x] **10.2** Implement startup checks:
    - Verify ffprobe is available. If not, print clear error and exit.
    - Determine the tool root (the directory containing `pixera_intake.py`). Used for `.recent_shows.json`.

- [x] **10.3** Implement the launch loop:
    - Load and display recent shows menu.
    - Get selection (numbered show, N for new, Q for quit).
    - On Q: exit.
    - On N: open folder picker.
    - On numbered: load that show.
    - Either way, ends with a `show_root: Path` to load.

- [x] **10.4** Implement show loading:
    - Check for `show_config.json`.
    - If missing: run setup mode (Phase 6). After setup, attempt to load again.
    - If present: validate. On failure, run the edit-retry loop.
    - On success: ensure media structure, add to recent shows, proceed to main menu.

- [x] **10.5** Implement the main menu loop:
    - Display main menu per DESIGN.md section 13.
    - On 1: run intake.
    - On 2: run spec generation.
    - On 3: run report.
    - On 4: break out of main menu loop, return to launch loop.
    - On Q: exit tool.
    - After any action completes, re-display the main menu.

- [x] **10.6** Top-level exception handler:
    - Catch unexpected exceptions at the very top.
    - Print error and traceback to console.
    - Exit with non-zero status.
    - This ensures the tool never appears to crash silently.

- [x] **10.7** Manual test: full end-to-end runs through every mode. Verify navigation works (main menu → mode → main menu, switch shows, quit).

### Notes

All wiring lives in `pixera_intake.py`. Control flow: `main()` → `_run()` (outer while-True launch loop) → `_run_launch_menu()` → `_load_show()` → `ensure_media_structure` + `add_or_update` → `_run_main_menu()` (inner while-True). Selecting "4" returns from `_run_main_menu`, cycling the outer loop back to the launch menu. "Q" raises `SystemExit(0)` which propagates up through `main()`'s explicit `except SystemExit: raise`. `KeyboardInterrupt` caught separately and exits cleanly. Spec generation is a thin `_run_spec()` wrapper (calls `generate_spec`, prints path, catches all exceptions). The two-line show header (`SHOW:` + `Path:` inside === block) matches DESIGN.md §13 exactly. 14 automated tests pass covering all non-interactive paths: header render, spec success/failure, _load_show happy/declined, launch menu (numbered/N+picker/cancelled), SystemExit propagation, ffprobe missing, choice 4 return, choice Q, all three mode dispatches in sequence.

---

## Phase 11: README

**Goal:** Documentation that operators can use without referencing the design doc.

### Tasks

- [x] **11.1** Write `README.md` covering:
    - **Purpose:** one-paragraph summary of what the tool does.
    - **Requirements:** Python version, ffmpeg/ffprobe, Notepad++ recommended.
    - **Installation:**
        - Where to place the tool (`C:\Tools\PixeraIntake\`).
        - How to install Python dependencies (`pip install -r requirements.txt`).
        - How to verify ffprobe is on PATH.
    - **First-time use:**
        - Create show project root manually.
        - Run the tool, point at the show root, fill in the starter config.
    - **Configuration reference:**
        - Each field of `show_config.json` explained.
        - What each strictness level means.
        - List of supported codec identifiers.
    - **Workflow:**
        - Setup mode walkthrough.
        - Intake mode walkthrough (with example output).
        - Spec generation mode.
        - Reporting mode.
    - **Troubleshooting:**
        - "The tool says my config is invalid" — common errors.
        - "ffprobe not found" — how to fix PATH.
        - "Notepad++ doesn't open" — fallback behavior.
        - "Files going to _REVIEW" — common causes.
        - "File copied with warnings" — what warnings mean.
    - **What goes in `_REVIEW/`:**
        - Why files go there.
        - What to do with them.
    - **What's NOT supported (v1):**
        - List of things from DESIGN.md section 16 to set expectations.

- [x] **11.2** Include a quick-start section at the top: "Just want to use it? Here's the 5-step quick start."

- [x] **11.3** Manual review: read through README pretending to be a new operator. Note any confusing parts and revise.

### Notes

Full operator-facing README written. Sections: Quick Start (5 steps) → Requirements table → Installation (place files, pip install, PATH verification, optional .bat shortcut) → First-Time Use (with folder tree diagram) → Configuration Reference (full JSON example, field table, strictness table, codec identifier table — all verified against actual code) → Workflow (Setup/Intake with example plan output/Spec Gen/Reporting with example report output) → Troubleshooting (5 scenarios with specific fixes) → What Goes in _REVIEW → Not Supported in v1. Codec identifiers verified against `ffprobe_wrapper.py` and `show_config_starter.json` — all use `prores_422_hq` style (lowercase underscores) which is correct. Mental operator read-through: all steps actionable, no jargon left unexplained, error messages match what the tool actually produces.

---

## Phase 12: Final Integration & Polish

**Goal:** Catch the rough edges before declaring v1 done.

### Tasks

- [x] **12.1** Run through every mode on a realistic-looking show folder (not just toy test data). Check for unpolished output, awkward prompts, missing color, broken edge cases.

- [x] **12.2** Test on a fresh Windows environment if possible (or at least a fresh Python virtual environment) to verify the requirements.txt is complete.

- [x] **12.3** Verify all the acceptance criteria from DESIGN.md section 17 are met. Document any gaps.

- [x] **12.4** Add any missing docstrings, type hints, or error messages noticed during testing.

- [x] **12.5** Final pass on README accuracy after any behavior changes.

### Notes

**12.1:** All output helpers verified. No awkward prompts or missing color found. `print_blank()` got its missing docstring; the `—` em-dash renders correctly under UTF-8 terminal.

**12.2:** Third-party imports scanned via AST — only `docx` (python-docx) and `colorama` are used. Both are in requirements.txt. All stdlib imports confirmed against `sys.stdlib_module_names`.

**12.3:** All 13 acceptance criteria verified via automated test suite (15 individual checks). One real bug found and fixed: `atomic_copy` had `destination.parent.mkdir()` outside the try/except, so a mkdir failure (e.g. permission denied) would propagate uncaught rather than returning `False`. Fixed by moving mkdir inside the try block.

**12.4:** AST scan found 16 public classes missing docstrings across 6 modules (all dataclasses and the `Action` enum). All fixed. Zero issues remain.

**12.5:** README verified against actual codec identifiers in `ffprobe_wrapper.py` and `show_config_starter.json`. No inaccuracies found; no behavior changed in this phase that required README updates.

---

---

## Post-v1.0 Changes (field testing and operator feedback)

Changes made after Phase 12 sign-off, in the order they were applied.

---

### PCT-01 · NotchLC codec support
**Date:** 2026-04-29
**Files changed:** `modules/ffprobe_wrapper.py`, `templates/show_config_starter.json`, `README.md`

**Problem:** Operator encodes files to NotchLC on their own machine before transferring to Pixera for transcoding. ffprobe reports `codec_tag_string = "nclc"`, `codec_name = "notchlc"`. These were not in `CODEC_TAG_MAP` or the default codec lists, causing all NotchLC files to fail codec validation.

**Changes:**
- Added `"nclc": "notchlc"` to `CODEC_TAG_MAP` in `ffprobe_wrapper.py`.
- Added `"notchlc"` to both `expected_codecs` and `preferred_codecs` in `show_config_starter.json`. NotchLC is treated as a first-class preferred codec — no warning generated.
- Added `notchlc | NotchLC` row to the supported codec identifier table in `README.md`.

---

### PCT-02 · Windows setup script
**Date:** 2026-04-29
**Files changed:** `setup_check.bat` (new file)

**Problem:** Moving the tool to a new machine with no prerequisites required a manual checklist. Operators needed clear guidance and automatic pip install.

**Changes:**
- Created `setup_check.bat`. On double-click (or CMD run from the tool folder), it:
  1. Verifies `requirements.txt` is present (confirms correct folder).
  2. Checks Python 3.10+ is on PATH; prints download URL if missing.
  3. Checks `ffprobe` is on PATH; prints ffmpeg download URL and PATH instructions if missing.
  4. Checks for Notepad++ at `C:\Program Files\Notepad++\notepad++.exe` (WARN, not FAIL — optional).
  5. Runs `pip install -r requirements.txt` automatically if Python is available.
  6. Prints a RESULT summary and always ends with `pause` so the window stays open.
- Bug fixed during testing: original script used the em dash `—` in the `title` line (non-ASCII, crashes CMD in OEM encoding) and used nested `if/else` parenthesized blocks containing `)` in echo strings (causes ". was unexpected at this time." error). Fixed by replacing `—` with `-` and restructuring the summary block using `goto` labels.

---

### PCT-03 · Windows desktop shortcut
**Date:** 2026-04-29
**Files changed:** `Pixera Intake Tool.lnk` (new file)

**Problem:** Operators wanted a double-clickable shortcut to launch the tool.

**Changes:**
- Created `Pixera Intake Tool.lnk` using PowerShell `WScript.Shell` COM object.
- Target: `cmd.exe /k python C:\Tools\PixeraIntakeTool\pixera_intake.py` — `/k` keeps the CMD window open after the tool exits so output is readable.
- Working directory: `C:\Tools\PixeraIntakeTool\`.

---

### PCT-04 · Invalid (loose) prefix routes to `_REVIEW/` instead of creating a new folder
**Date:** 2026-04-29
**Files changed:** `modules/filename_parser.py`, `modules/intake.py`

**Problem:** A file named `Screens_WalkInLoop_v03_20260428.mov` was parsed as `PartialMatch` with `screen_prefix = "Screens"` (because "Screens" starts with "SCR" and matched `_PREFIX_LOOSE_RE`). `plan_file` then called `_dest_folder("Screens", show_root)` which resolved to `Media/Screens/`. `atomic_copy` created that folder on execution, producing a stale folder immediately after intake. The plan display showed it as `⚠ COPY → Media\Screens\` rather than routing to `_REVIEW/`.

**Root cause:** `plan_file` used `_dest_folder(screen_prefix, ...)` for all `PartialMatch` results without checking whether the prefix itself was valid. A loose match (malformed prefix) should behave like `NoMatch` for routing purposes.

**Changes:**
- Added `is_valid_prefix(token: str) -> bool` to `filename_parser.py` — returns `True` only for prefixes matching `_PREFIX_STRICT_RE` (`SCR##`, `SCRwide-##-##`, `SCRall`, `AUD`).
- In `plan_file`, for `PartialMatch`: if `not is_valid_prefix(screen_prefix)`, return a `ROUTE_TO_REVIEW` plan pointing to `Media/_REVIEW/` (calling `_apply_existing_file_check` — see PCT-05). Only valid-prefix partial matches continue to `_dest_folder`.

---

### PCT-05 · `screen_id` validation strictness — unknown screen IDs route to `_REVIEW/`
**Date:** 2026-04-29
**Files changed:** `modules/config.py`, `modules/intake.py`, `templates/show_config_starter.json`

**Problem:** A file with a valid but unconfigured screen prefix (e.g. `SCR03_WrongRes_v01_20260428.mov` in a show with only SCR01 and SCR02) was copied into a new `Media/SCR03/` folder with only a warning: "Screen 'SCR03' is not in config — resolution not checked". The folder was created by `atomic_copy`, immediately becoming a stale folder.

**Root cause:** The "screen not in config" check in `_validate_specs` appended to `warnings` instead of `failures`. Only items in `failures` trigger `ROUTE_TO_REVIEW`.

**Changes:**
- Added `screen_id` to `_STRICTNESS_OPTIONAL` in `config.py` (default: `"strict"`). Fields in `_STRICTNESS_OPTIONAL` are validated if present in the config but silently defaulted if absent — existing show configs without the field continue to load without error.
- `load_config` now merges `_STRICTNESS_OPTIONAL` defaults under any explicit values, so `strictness["screen_id"]` is always safe to read.
- In `_validate_specs`, replaced `warnings.append(...)` for the "screen not in config" case with `_apply(strictness["screen_id"], ...)`. With the default of `"strict"`, this appends to `failures`, triggering `ROUTE_TO_REVIEW` and no folder creation.
- Added `"screen_id": "strict"` to `validation_strictness` in `show_config_starter.json` so new show configs are explicit.

---

### PCT-06 · `_REVIEW/` overwrite prevention and duplicate detection
**Date:** 2026-04-29
**Files changed:** `modules/intake.py`

**Problem (A — overwrite on re-run):** On a second intake run with the same source folder, files previously routed to `_REVIEW/` (e.g. `Screens_WalkInLoop_v03_20260428.mov`) were silently overwritten. `NoMatch` and invalid-prefix `PartialMatch` code paths returned a `FilePlan` immediately without calling `_apply_existing_file_check`, so no duplicate check was performed.

**Problem (B — unconditional rename):** The initial fix applied `_unique_review_path` to all `_REVIEW/` destinations regardless of whether a conflict existed, renaming files even on first run.

**Changes:**
- Added `_unique_review_path(dest: Path) -> Path` helper: if `dest` does not exist, returns it unchanged; otherwise appends `_2`, `_3`, … to the stem until a non-conflicting name is found.
- Updated `_apply_existing_file_check` to include a dedicated `_REVIEW/` branch:
  - If destination does not exist → copy as-is (no rename).
  - If destination exists and sizes match → `SKIP_IDENTICAL` (already delivered).
  - If destination exists and sizes differ → rename to `_unique_review_path` and add `WARN: Renamed to avoid overwrite: <new_name>` to the plan so the operator sees it in the plan display.
- `NoMatch` and invalid-prefix `PartialMatch` now both call `_apply_existing_file_check` before returning (previously they returned immediately without any duplicate check).

---

### PCT-07 · Starter config defaults to two screens
**Date:** 2026-04-29
**Files changed:** `templates/show_config_starter.json`

**Problem:** The starter config only had one screen (SCR01), requiring every new show to manually add SCR02.

**Change:** Added a second screen entry to the `screens` array:
```json
{ "id": "SCR02", "name": "REPLACE_OR_LEAVE_BLANK", "resolution": "REPLACE_WITH_RESOLUTION" }
```

---

## Open Questions / Decisions Made During Implementation

Use this section to record any decisions made during implementation that weren't fully specified in DESIGN.md. Each entry should have:

- **Question/issue:**
- **Decision:**
- **Rationale:**
- **Date:**

(Empty initially. Add as you encounter ambiguities.)

---

## Final Status

Update at the end:

- **All phases complete?** [x] Yes
- **Acceptance criteria met?** [x] Yes — all 13 criteria verified, 15/15 automated checks pass
- **Known issues at v1.0:**
  - The `⚠` and `—` characters in colorama output require a UTF-8 terminal (`python -X utf8` or Windows Terminal). The legacy `cmd.exe` console with cp1252 encoding will crash on those characters. Workaround: run via Windows Terminal or add `PYTHONUTF8=1` to the environment.
- **Recommended v1.5 priorities:**
  - UTF-8 terminal enforcement at startup (detect encoding and warn or force UTF-8)
  - File checksumming (SHA-256) as an optional more-reliable duplicate check
  - A `--dry-run` / `--quiet` flag for scripted use
  - Auto-open of generated spec docx after generation
