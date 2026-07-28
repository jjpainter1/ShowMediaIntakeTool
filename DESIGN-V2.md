# Show Media Intake Tool — Design Document v2

**Version:** 2.0
**Status:** Specification (ready for implementation)
**Target platform:** Windows (Python 3.10+)
**Predecessors:** v1 CLI tool (preserved alongside v2 GUI)
**Companion documents:** v2_scope_decisions.md (Phase 0), v2_gap_analysis.md (Phase 1)

---

## How to use this document

This is the comprehensive design specification for v2 of the tool. The companion `PLAN-V2.md` breaks the implementation into phases the coding agent can execute against.

**Read this document end-to-end before writing any code.** The earlier sections establish principles and architecture that later sections rely on.

When this document conflicts with v1's `DESIGN.md`, this document wins. v1's design doc is preserved for reference but is no longer authoritative.

---

## 1. Purpose and Scope

### 1.1 What v2 is

v2 is a GUI replacement for the v1 CLI tool, generalized from "Pixera-specific" to "multi-playback-system." It uses CustomTkinter for the GUI layer, preserves all v1 modules (with non-breaking schema additions), and introduces a preset system to support multiple playback systems via a single tool.

### 1.2 What v2 solves that v1 didn't

- **Non-technical users:** Producers and operators uncomfortable with terminals or JSON editing now have a forms-based, visual interface.
- **Multi-system support:** Operators of PlayBack Pro, Mitti, and other systems can use the tool by selecting an appropriate preset.
- **At-a-glance show state:** The dashboard shows show health (file counts, version conflicts, stale folders, days until show) in one view.

### 1.3 What v2 deliberately does not change

The v1 architecture, data model, validation logic, and file system conventions all remain. v2 is fundamentally a presentation-layer change with targeted schema additions.

### 1.4 Tool name and branding

- **Name:** Show Media Intake Tool
- **Window title:** "Show Media Intake Tool v2.0"
- **Install location:** `C:\Tools\ShowMediaIntakeTool\`
- **Module package:** `gui/` (new), `modules/` (existing, preserved)
- **Entry point (GUI):** `show_media_intake.py`
- **Entry point (CLI, preserved):** `cli_intake.py` (renamed from `pixera_intake.py`)

---

## 2. Design Principles

These take precedence when implementation tradeoffs arise:

1. **Content identity is durable; cue position is not.** Filenames describe what content *is*, not where it lives in the show.
2. **The intake gate is the enforcement layer.** Validation happens at receiving time, not later.
3. **Never delete files; never move active files.** Both old and new versions coexist.
4. **The show config is the single source of truth.** Presets are starting points, not runtime configuration sources.
5. **Two-phase execution always.** Plan first, prompt for confirmation, then execute.
6. **Strict validation, transparent reporting.** Validation rules are configurable per show.
7. **Atomic file operations.** Files copy to temp names, rename to final on success.
8. **The GUI is a presentation layer over the existing modules.** No business logic lives in `gui/`.
9. **Long operations don't block the UI.** Threading for ffprobe scans and file copies.

---

## 3. Architecture

### 3.1 File and directory layout

The complete v2 install:

```
C:\Tools\ShowMediaIntakeTool\
├── show_media_intake.py          # GUI entry point
├── cli_intake.py                  # CLI entry point (renamed from pixera_intake.py)
├── requirements.txt
├── README.md
├── modules/                       # Preserved from v1, with schema additions
│   ├── __init__.py
│   ├── config.py                  # Schema v2 support added
│   ├── intake.py                  # 'ignore' strictness handling added
│   ├── spec_generator.py          # Pixera template only for v2.0
│   ├── show_report.py             # Removed in v2 (dashboard absorbs it)
│   ├── ffprobe_wrapper.py         # Codec map expanded
│   ├── filename_parser.py         # Unchanged
│   ├── recent_shows.py            # Unchanged
│   ├── console_ui.py              # Used only by CLI
│   └── setup.py                   # Setup helpers, used by both CLI and GUI
├── gui/                           # New for v2
│   ├── __init__.py
│   ├── app.py                     # Root application class
│   ├── state.py                   # AppState shared across screens
│   ├── theming.py                 # Colors, fonts, common styles
│   ├── screens/
│   │   ├── __init__.py
│   │   ├── launch.py              # Launch screen (recent shows + browse + new)
│   │   ├── dashboard.py           # Main per-show dashboard
│   │   ├── intake.py              # Intake delivery view
│   │   ├── spec_generator.py      # Generate spec doc view
│   │   └── config_editor.py       # CTkToplevel config editor
│   ├── widgets/
│   │   ├── __init__.py
│   │   ├── show_card.py           # Sidebar show info card
│   │   ├── nav_button.py          # Sidebar nav button
│   │   ├── screen_card.py         # Dashboard screen card
│   │   ├── stat_card.py           # Dashboard stat cards
│   │   ├── plan_table.py          # Intake plan table
│   │   ├── results_section.py     # Intake results collapsible section
│   │   ├── progress_panel.py      # Copying progress display
│   │   ├── tag_list.py            # Codec tag list with add/remove
│   │   ├── screen_table.py        # Config editor screens tab table
│   │   ├── strictness_grid.py     # Config editor validation tab grid
│   │   ├── status_badge.py        # COPY/REVIEW/DONE colored badges
│   │   ├── confirm_modal.py       # Reusable confirmation modals
│   │   └── toast.py               # Transient success/error messages
│   └── workers/                   # Background thread helpers
│       ├── __init__.py
│       ├── scan_worker.py         # Threaded ffprobe scan
│       ├── copy_worker.py         # Threaded file copy with progress
│       └── refresh_worker.py      # Threaded dashboard refresh
└── templates/
    ├── show_config_starter.json   # Updated to v2 schema
    ├── spec_template.docx         # Pixera-flavored, single template for v2.0
    └── presets/                   # New for v2
        ├── pixera.json
        ├── playbackpro.json       # Identical to pixera.json content for v2.0
        └── mitti.json             # Identical to pixera.json content for v2.0

User-writable storage (separate from install):
%LOCALAPPDATA%\ShowMediaIntakeTool\
├── .recent_shows.json             # Moved from install dir to user-writable location
└── custom_presets/                # User-saved presets, one file per preset
    └── <PresetName>.json
```

### 3.2 Show project structure (operator-managed)

Unchanged from v1:

```
D:\Shows\<ShowName>_<YYYYMMDD>\
├── show_config.json               # Tool-managed; edited via Config Editor
├── <ShowName>.avp                 # Pixera project (tool does not touch)
├── <ShowName>_DeliverySpec.docx   # Generated by tool
└── Media\
    ├── _LOGS\                     # DeliveryLog.txt + per-intake transcripts
    ├── _REVIEW\                   # Files that failed validation
    ├── _REFERENCE\                # Operator-placed reference materials
    ├── SCR01\
    ├── SCR02\
    ├── SCR03\
    └── ...
```

### 3.3 Data flow

**At launch:**
```
show_media_intake.py
  → Verify ffprobe available (modules.ffprobe_wrapper.check_ffprobe_available)
  → Initialize AppState (loads recent shows, theming)
  → Show launch screen
```

**On show selection:**
```
Launch screen → operator picks recent show or browses
  → AppState.load_show(path)
  → modules.config.load_config (raises if invalid; v2 detects schema_version)
  → If no config: trigger setup flow (modal)
  → If v1 config: trigger migration flow (modal with backup)
  → On success: ensure_media_structure, add to recent shows
  → Hide launch, show main app frame (sidebar + dashboard)
```

**During intake:**
```
Intake screen → operator picks source folder
  → Click Scan Folder
  → ScanWorker (background thread):
      walk source, parse_filename, probe_file, build FilePlan list
  → Plan rendered in UI as worker progresses
  → Operator clicks Proceed with Copy
  → CopyWorker (background thread):
      atomic copy each file, report progress, write logs
  → Results rendered when complete
```

### 3.4 Threading model

- **Main thread:** UI event loop. All CTk widget creation and updates happen here.
- **Worker threads:** ffprobe scan (one thread, runs all probes serially), file copy (one thread, runs all copies serially), refresh (one thread, recounts files in Media folder).
- **Communication:** workers post `queue.Queue` messages for progress updates; main thread polls the queue via `app.after()` callbacks.

Workers are one-shot: they're created, run to completion, and discarded. No persistent worker pool. This keeps cancellation logic simple — to cancel, set a flag on the worker that it checks between operations; in-flight ffprobe or copy completes, then worker exits.

For v2.0, **cancellation is not implemented for scan or copy.** The operator commits to the operation when starting it. v2.1+ may add cancellation if needed.

---

## 4. The preset system

### 4.1 Concept

Presets are operator-facing labels representing playback systems (Pixera, PlayBack Pro, Mitti, etc.). Each preset provides default values for tech specs, codec lists, and validation strictness. Presets are starting points only — once a config is created, all behavior is driven by the config file itself, not by the preset reference.

### 4.2 Built-in presets shipped in v2.0

Three preset files ship in `templates/presets/`:

- `pixera.json` — Pixera Standard preset with NotchLC + ProRes family codecs
- `playbackpro.json` — Identical contents to `pixera.json` at v2.0 launch
- `mitti.json` — Identical contents to `pixera.json` at v2.0 launch

The PlayBack Pro and Mitti files are placeholder duplicates intentionally. The operator (or future v2.1 work) modifies them to contain accurate codec lists for those systems. Until modified, they function but produce Pixera-flavored configs.

The dropdown in the Config Editor labels them by `preset_name` field within each file:

- "Pixera" (from `pixera.json`)
- "PlayBack Pro" (from `playbackpro.json`)
- "Mitti" (from `mitti.json`)

**Reinstall safety:** built-in preset files are part of the install. Reinstalling the tool overwrites them with original Pixera-equivalent contents. Operators who customize built-in presets should copy them to custom presets to preserve edits across reinstalls.

### 4.3 Custom presets

Custom presets live in `%LOCALAPPDATA%\ShowMediaIntakeTool\custom_presets\`, one file per preset. Filename matches the `preset_name` field with filename-safe characters only (e.g., "My Mitti Preset" → `My_Mitti_Preset.json`).

Custom presets are user-writable; the tool creates the directory if it doesn't exist on first save.

The Config Editor's preset dropdown shows built-in presets first (with a "Built-in" group header), then custom presets (with a "Custom" group header). Within each group, presets are sorted alphabetically.

### 4.4 Preset file schema

```json
{
  "preset_name": "Pixera",
  "preset_description": "For Pixera media servers with NotchLC playback and ProRes mezzanine delivery",
  "expected_specs": {
    "framerate": 30,
    "color_space": "bt709",
    "color_range": "tv",
    "audio_sample_rate": 48000,
    "audio_channels": 2
  },
  "expected_codecs": [
    "notchlc",
    "prores_422_proxy", "prores_422_lt", "prores_422",
    "prores_422_hq", "prores_4444", "prores_4444_xq"
  ],
  "preferred_codecs": [
    "notchlc", "prores_422_hq", "prores_4444"
  ],
  "validation_strictness": {
    "resolution": "strict",
    "framerate": "strict",
    "codec": "strict",
    "codec_flavor": "warn",
    "color_space": "warn",
    "color_range": "warn",
    "audio_sample_rate": "info",
    "audio_channels": "info",
    "screen_id": "strict"
  }
}
```

A preset file does **not** include show-specific fields (show_name, show_date, screens, operator). When a preset is applied to a config, only the fields it provides are populated; show-specific fields remain whatever was already in the config.

### 4.5 "Apply preset" behavior

When the operator selects a preset from the dropdown and clicks "Load":

1. The preset file is read.
2. Every field in the preset overrides the corresponding field in the active config (in memory, not yet saved).
3. The Config Editor UI refreshes to show the new values.
4. The operator can then modify any field and click "Save Configuration."
5. On save, the `preset` field in the saved config is set to the loaded preset's `preset_name`.

If the operator modifies fields after loading and saves without re-applying the preset, the `preset` field still records the last-loaded preset name. This is the "informational only" semantic — the preset name records lineage but doesn't constrain content.

### 4.6 "Save as Preset" behavior

In the Config Editor's Expected Specs tab, the "Save as Preset" button:

1. Prompts the operator for a preset name (free text, must be filename-safe).
2. Validates that the name doesn't conflict with a built-in preset.
3. Creates a preset file in the custom_presets folder containing the current Expected Specs values + codec lists + validation strictness.
4. Adds the new preset to the dropdown.
5. Shows a success toast.

If the name conflicts with an existing custom preset, the operator is prompted: overwrite, choose different name, cancel.

---

## 5. Schema v2

### 5.1 Schema additions

The `show_config.json` file gains two top-level fields in v2:

```json
{
  "schema_version": 2,
  "preset": "pixera",
  ... (existing v1 fields) ...
}
```

- **`schema_version`** (integer): Always `2` for v2-written configs. v1 configs have no `schema_version` field; the tool treats absence as `1`.
- **`preset`** (string): The preset name from which the config was last loaded. Default `"pixera"` for new configs; operators can change it via the Config Editor's preset selection. Special value `"custom"` means "no preset applied" (config built from scratch). The field is informational and does not affect runtime behavior.

### 5.2 New strictness level: "ignore"

The `validation_strictness` values now include `ignore` alongside `strict`, `warn`, and `info`:

| Level | Behavior on mismatch |
|---|---|
| `strict` | Route file to `_REVIEW/` |
| `warn` | Copy with warning |
| `info` | Copy, mention in report only |
| `ignore` | Skip the check entirely |

`ignore` is automatically set when the corresponding spec field is `null` (the GUI's "N/A" option). When a spec field is `null`, the strictness setting for that field is ignored anyway (there's nothing to compare against), but storing `ignore` makes the operator's intent explicit.

Code changes required in `modules/intake.py`:

- The validation function for each spec checks the strictness level *before* running the check.
- If strictness is `ignore`, the check is skipped (no warning, no failure).
- The plan report does not list ignored checks at all.

### 5.3 N/A handling for spec fields

In v2 configs, `expected_specs` fields can be `null`, indicating "no expected value":

```json
"expected_specs": {
  "framerate": 30,
  "color_space": null,
  "color_range": null,
  "audio_sample_rate": 48000,
  "audio_channels": 2
}
```

When a field is `null`:
- The Config Editor displays "N/A" in the dropdown.
- The corresponding `validation_strictness` entry is auto-set to `ignore` on save.
- The intake validation skips that check.

If the operator switches the field from N/A back to a value, the strictness reverts to whatever was previously selected (or to `strict` as the safe default if no previous value exists).

### 5.4 v1 → v2 migration

When v2 loads a config without `schema_version`:

1. The Launch screen detects the v1 format on show load.
2. A modal appears: "This show was created in v1. Migrate to v2? Adds preset='pixera' and schema_version=2 fields. A backup of the original will be saved."
3. The modal has three options: **Migrate**, **Cancel** (close modal, return to launch screen without loading the show), and **View What Changes** (expands a description of what migration does).
4. On Migrate:
   - Backup file written to `<show_root>/show_config.v1.bak.json` (alongside the original config, top-level).
   - The original config is updated in place with `schema_version: 2` and `preset: "pixera"` added at the top.
   - All other fields are preserved exactly.
   - Tool proceeds to load the show normally.

Migration is one-time per show. Once migrated, the backup file persists; the operator can delete it manually if desired.

### 5.5 Updated config schema

Full v2 schema:

```json
{
  "schema_version": 2,
  "preset": "pixera",
  "show_name": "TestShow",
  "show_date": "2026-06-15",
  "operator": {
    "name": "JJ Painter",
    "email": "jjpainter@prestigeav.com"
  },
  "expected_specs": {
    "framerate": 30,
    "color_space": "bt709",
    "color_range": "tv",
    "audio_sample_rate": 48000,
    "audio_channels": 2
  },
  "expected_codecs": [
    "notchlc", "prores_422_proxy", "prores_422_lt", "prores_422",
    "prores_422_hq", "prores_4444", "prores_4444_xq"
  ],
  "preferred_codecs": [
    "notchlc", "prores_422_hq", "prores_4444"
  ],
  "screens": [
    { "id": "SCR01", "name": "HouseLeft", "resolution": "1920x1080" },
    { "id": "SCR02", "name": "CenterLED", "resolution": "2688x1152" },
    { "id": "SCR03", "name": "HouseRight", "resolution": "1920x1080" }
  ],
  "validation_strictness": {
    "resolution": "strict",
    "framerate": "strict",
    "codec": "strict",
    "codec_flavor": "warn",
    "color_space": "warn",
    "color_range": "warn",
    "audio_sample_rate": "info",
    "audio_channels": "info",
    "screen_id": "strict"
  }
}
```

### 5.6 Codec map expansion

`modules/ffprobe_wrapper.py` `CODEC_TAG_MAP` is expanded to include common live-event playback codecs:

| codec_tag | identifier | Description |
|---|---|---|
| `apco` | `prores_422_proxy` | ProRes 422 Proxy (existing) |
| `apcs` | `prores_422_lt` | ProRes 422 LT (existing) |
| `apcn` | `prores_422` | ProRes 422 (existing) |
| `apch` | `prores_422_hq` | ProRes 422 HQ (existing) |
| `ap4h` | `prores_4444` | ProRes 4444 (existing) |
| `ap4x` | `prores_4444_xq` | ProRes 4444 XQ (existing) |
| `nclc` | `notchlc` | NotchLC (existing) |
| `avc1` | `h264` | H.264 / AVC |
| `hvc1` | `h265` | H.265 / HEVC (variant 1) |
| `hev1` | `h265` | H.265 / HEVC (variant 2) |
| `AVdh` | `dnxhd` | DNxHD/DNxHR |
| `AVd1` | `dnxhd` | DNxHD/DNxHR (variant) |
| `mp4v` | `mpeg4` | MPEG-4 |
| `WMV3` | `wmv3` | Windows Media Video 9 |

The Config Editor's "add codec" dropdown shows all unique identifiers from this map. Adding codec support in the future is purely a matter of adding entries to `CODEC_TAG_MAP`.

---

## 6. UI Architecture

### 6.1 Application window

- **Class:** subclass of `customtkinter.CTk`
- **Default size:** 1160 × 750
- **Minimum size:** 1000 × 680
- **Resizable:** yes
- **Title:** dynamic; "Show Media Intake Tool v2.0" when no show loaded, "Show Media Intake Tool v2.0 — <ShowName>" when loaded

### 6.2 Top-level layout

The window has two top-level layouts that swap based on app state:

**Launch layout** (no show loaded): Centered launch screen with title, recent shows, and action buttons. Sidebar hidden.

**Show layout** (show loaded): Two-column grid. Left: sidebar (210px fixed). Right: content area (flexible).

The transition between layouts is a full content swap — no animation. Sidebar is hidden in launch layout; content area expands to full width.

### 6.3 Theming

- **Appearance mode:** dark (set globally at startup, not user-configurable in v2.0)
- **Color theme:** blue (CustomTkinter built-in)
- **Custom colors** (defined in `gui/theming.py` for use across screens):

| Role | Value | Used for |
|---|---|---|
| Window BG | `#1c1c1c` | Main app background |
| Frame BG | `#2b2b2b` | Default frame backgrounds |
| Surface elevated | `#333333` | Cards, popups, inputs |
| Blue accent | `#1F6AA5` | Active buttons, selections |
| Blue hover | `#2d7fc0` | Hover states on accented elements |
| Text primary | `#dce4ee` | Main text |
| Text secondary | `#9a9d9f` | Dim labels, placeholders |
| Success green | `#5cb87a` | Success messages, ✓ DONE badges |
| Warning yellow | `#d4a040` | Warnings, ⚠ COPY badges |
| Error red | `#d95f5f` | Failures, ✗ REVIEW badges |
| Info cyan | `#5aacda` | File paths, log references |

### 6.4 Fonts

- **Primary:** Segoe UI (Windows default)
- **Monospace:** Consolas (for filenames, paths, codec tags)
- **Sizes:** 26 (page titles), 17 (section headers), 13 (labels), 11 (small text)

### 6.5 Sidebar (visible when show loaded)

Fixed width 210px. Contains, top to bottom:

1. **Show Info Card** — frame with rounded corners, slightly elevated background. Three labels stacked:
   - Show name (bold, 13pt)
   - Show date (gray, 11pt)
   - Show path (gray, 10pt, truncated with ellipsis if too long)

2. **Navigation Buttons** — vertical stack:
   - ⊞ Dashboard
   - ↓ Intake Delivery
   - ⎘ Generate Spec Doc
   - (separator)
   - ⚙ Edit Config (opens CTkToplevel)

3. **Bottom area** (anchored to sidebar bottom):
   - ⇄ Switch Show

**Button states:**
- Inactive: transparent background, gray text, left-aligned
- Active: blue accent background, white text
- Hover (inactive): subtle background tint
- Disabled (during long operations): grayed out, not clickable

The active button reflects which screen is currently shown in the content area. Edit Config does not have an "active" state because it opens a popup, not an in-window screen.

---

## 7. Launch Screen

### 7.1 Layout

Centered vertical stack on a full-screen frame:

1. **Title block** (top, ~15% from top):
   - "Show Media Intake Tool" (large, bold, 26pt)
   - "v2.0 · by JJ Painter" (small, gray, 11pt)

2. **Recent Shows panel** (centered, below title):
   - Section label "RECENT SHOWS" (small caps, bold, 10pt)
   - Up to 5 recent show entries, each as a clickable row:
     - Show name (bold)
     - Show path (gray, smaller)
     - Last used relative time (right-aligned, gray)
   - If no recent shows: empty state message "No recent shows. Browse for one or create new."

3. **Action buttons row** (below recent shows):
   - 📁 Browse for Show Folder (primary blue, larger)
   - + New Show (secondary, smaller)

### 7.2 Recent shows behavior

- Loaded from `%LOCALAPPDATA%\ShowMediaIntakeTool\.recent_shows.json`
- Self-cleans on launch: any entry whose `show_config.json` no longer exists is silently removed
- Sorted by `last_used` descending
- Maximum 5 entries shown
- Each entry can carry an optional `dashboard_view` preference (see 12.1) — used to remember per-show UI choices like Cards vs Compact mode

### 7.3 Browse for Show Folder

1. Click → `tkinter.filedialog.askdirectory()` opens
2. On selection:
   - If config exists at `<path>/show_config.json`:
     - If schema_version is missing or 1: trigger v1 migration flow (modal)
     - If schema_version is 2: load normally
     - If invalid: show error, return to launch screen
   - If no config exists: trigger setup flow (modal)
3. On cancel: return to launch screen (no error)

### 7.4 + New Show

1. Click → opens "Create New Show" modal (CTkToplevel):
   - **Parent folder:** path field with Browse button (defaults to last-used parent or `D:\Shows\`)
   - **Show name:** text field, validated for filename-safe characters
   - **Show date:** date field (YYYY-MM-DD), defaults to today
   - **Buttons:** Cancel, Create
2. On Create:
   - Construct path: `<parent>/<ShowName>_<YYYYMMDD>/`
   - **If folder already exists:** show error "A show folder with this name already exists at this location. Please choose a different name or location." Modal stays open.
   - Create folder + Media subfolder structure (no screen folders yet)
   - Copy starter config from `templates/show_config_starter.json`, populate show_name and show_date from form values
   - Open Config Editor with the new config loaded
   - Operator fills in remaining fields and clicks Save
   - Tool transitions to dashboard

### 7.5 Setup flow (existing folder, no config)

When the operator browses to an existing folder without a `show_config.json`:

Modal appears with three options:
- **Set up new show here** — create starter config, open Config Editor (same flow as + New Show step 2 onward)
- **Browse different folder** — close modal, reopen folder picker
- **Cancel** — close modal, return to launch screen

### 7.6 v1 migration flow

When loading a config without `schema_version`:

Modal appears: "This show was created in v1 of the tool. To open it in v2, the config file needs to be migrated. A backup of the original will be saved as `show_config.v1.bak.json`."

Three buttons:
- **Migrate and Open** — perform migration, load show
- **View What Changes** — expands inline section: "Migration adds two fields: `schema_version: 2` and `preset: 'pixera'`. No existing fields are modified. Original config preserved as backup."
- **Cancel** — close modal, return to launch screen

---

## 8. Dashboard

The default view when a show is loaded.

### 8.1 Layout

Vertical sections, top to bottom in the content area:

1. **Header row**
2. **Banners** (conditional — only shown when relevant)
3. **Screen card grid**
4. **Stat card row**

### 8.2 Header row

Single horizontal frame:

- **Left side:**
  - Show name (large, bold)
  - Show date and path (smaller, gray, on second line)
- **Right side (right-aligned):**
  - **View toggle** (CTkSegmentedButton): two options — "⊞ Cards" and "≣ Compact" — controls the screen card grid layout below (see 8.4)
  - ↻ Refresh button (ghost style)
  - ↓ Intake Delivery button (primary blue)
  - ⎘ Generate Spec button (secondary)

### 8.3 Banners

Conditional banners that appear between the header and screen cards when relevant:

**Multi-version slugs banner** (when any screen has slugs with multiple versions):
- Background: subtle yellow tint
- Icon: ⚠
- Text: "N slugs have multiple versions present"
- Action: clickable "View details" link → expands an inline section listing each multi-version slug and its versions, formatted as:
  ```
  SCR01_OpeningVideo:    v03 (2026-06-10), v04 (2026-06-12)
  SCR02_OpeningVideo:    v03 (2026-06-10), v04 (2026-06-12)
  SCR03_50thAnniversary: v01 (2026-06-08), v02 (2026-06-11)
  ```

**Stale folders banner** (when stale folders detected):
- Background: subtle yellow tint
- Icon: ⚠
- Text: "N unmanaged folders found in Media"
- Action: clickable "Review" link → expands an inline section listing each stale folder name and file count

If both banners are relevant, both show stacked. Banners can be collapsed/dismissed (per-session, not persisted).

### 8.4 Screen card grid

A grid of cards, one per configured screen. The layout has two modes controlled by the view toggle in the header (8.2): **Cards** mode and **Compact** mode.

#### Cards mode (default for shows with ≤12 screens)

**Card layout** (each card ~265px wide, fixed height):
- Screen ID (top, blue accent, small caps, bold)
- Screen name (below ID, bold, larger)
- Resolution (below name, monospace, dim)
- File count + slug count (two large stat numbers side-by-side)
- "▼ View files" toggle hint at bottom

**Card interaction:**
- Hover: subtle background change
- Click: expands an inline file panel below the card row (see 8.5)
- Clicking another card: collapses the previous panel, expands the new one

**Layout behavior:**
- Cards arranged in a horizontal grid
- Wrap to multiple rows when they don't fit (CTk grid_columnconfigure with weight management)

#### Compact mode (default for shows with >12 screens)

A list-row layout — one row per screen, narrow height, columns for ID, Name, Resolution, FileCount, SlugCount. Easy scanning, fits ~25 screens visible.

**Row interaction:**
- Hover: subtle background change
- Click: expands the same inline file panel as Cards mode (see 8.5)

#### View toggle behavior

The header's view toggle (8.2) lets the operator switch between modes at any time:

- **Default selection:** Cards mode for shows with ≤12 screens; Compact mode for shows with >12 screens.
- **Operator override:** Clicking the toggle immediately switches the layout for the current show. The choice persists per-show (stored in the recent shows entry as a `dashboard_view` field — see 12.1).
- **Choice persistence:** Once an operator explicitly chooses a view for a show, that choice is used every time the show is loaded thereafter, regardless of screen count. To revert to default behavior, the operator can clear the per-show preference (TBD by implementation — could be a "Reset View" action or simply by deleting and re-adding the show to recents).

This pattern keeps the dashboard adaptive (smart defaults based on show size) while giving the operator full control when those defaults aren't right.

### 8.5 Inline file panel

When a screen card is clicked, an expanded panel appears below the card row.

**Panel header:**
- Frame with blue accent top border
- Screen ID, name, resolution, file count

**File table** (CTkScrollableFrame containing a grid):
- Columns: Filename, Size, Resolution, Codec, FPS
- Filename: monospace, flexible width
- Size: 80px, dim gray
- Resolution: 95px, monospace
- Codec: 120px
- FPS: 55px

**Sorting:**
- Click column header to sort
- Active sort column shows ▲ or ▼ indicator
- Default sort: filename ascending

**Performance note:**
- For screens with <100 files, use grid of CTkLabel widgets
- For screens with 100+ files, use `ttk.Treeview` styled to match dark theme (better performance)

### 8.6 Stat card row

Three cards side-by-side, each ~330px wide:

**Total Content card:**
- Section title "TOTAL CONTENT" (small caps, bold)
- Two stat pairs:
  - Large number: total file count + label "total files"
  - Large number: unique slug count + label "unique slugs"

**Last Delivery card:**
- Section title "LAST DELIVERY"
- Most recent delivery summary (parsed from DeliveryLog.txt):
  ```
  ✓ 2026-04-29 09:02 · 7 copied, 5 review, 0 skip
  ```
- "Days until show: N" line (with color emphasis: red if today/past, yellow if ≤7 days, default otherwise)
- Subtle "View delivery history" link → opens modal showing full DeliveryLog.txt as scrollable list

**Review Queue card** (only shown if `_REVIEW/` has files):
- Section title "▲ REVIEW QUEUE (N)" (red tint)
- List of filenames in `_REVIEW/`, each in red, monospace

If `_REVIEW/` is empty, the card is replaced with an empty placeholder ("✓ No files in review") or omitted to give the other two cards more space (TBD by implementation).

### 8.7 Refresh button

The ↻ Refresh button in the header:

- Re-walks the Media folder structure
- Re-counts files per screen
- Re-detects multi-version slugs
- Re-detects stale folders
- Re-reads DeliveryLog.txt for last-delivery info
- **Does NOT** re-run ffprobe on existing files (that would be slow)
- **Does NOT** re-read the config (config changes only via Config Editor, which triggers refresh on save)

Refresh runs on a worker thread; UI shows brief loading indicator (subtle spinner near the Refresh button) while it runs.

---

## 9. Intake Delivery View

A multi-phase workflow within a single screen. The screen content changes based on the current phase but the operator stays in the Intake Delivery view throughout.

### 9.1 Phase 1: Folder Selection

**Layout:**
- Heading "Intake New Content Delivery"
- Description: "Select the source folder containing delivery files to scan and import into the show."
- **Source Folder field:** label + CTkEntry + Browse button
- **🔍 Scan Folder button** (primary blue, disabled until path entered)

**Browse button:** opens `filedialog.askdirectory()` to pick source.

**Scan Folder button:** kicks off Phase 2.

### 9.2 Phase 2: Scanning (transitional)

After Scan Folder is clicked but before the plan is rendered:

- Replace the action area with:
  - **Progress label:** "Scanning N of M files..." (updates as worker progresses)
  - **CTkProgressBar:** in indeterminate mode initially, switches to determinate once total file count is known after the initial walk
- Scan worker (background thread):
  1. Walks source folder recursively
  2. For each media file, calls `parse_filename` and `probe_file`
  3. Builds list of `FilePlan` objects
  4. Posts progress updates to main thread queue
  5. On completion, posts the full plan to main thread

### 9.3 Phase 3: Intake Plan

Rendered when scan completes.

**Header row:**
- "Intake Plan · <ShowName>" (large, bold)
- Source path and file count (smaller, gray)
- **← Back button** (secondary, returns to Phase 1 without proceeding)
- **Proceed with Copy → button** (primary blue, right-aligned)

**Filter chips** (above table):
- All / Copy / Warnings / Failures
- Active filter highlighted, others ghost
- Clicking changes the displayed rows

**File table:**
- Columns: Action badge, Filename, Size, Resolution, Codec, FPS, Destination
- Each file row may have warning sub-rows below it (indented, yellow text)
- Each file row may have failure sub-rows below it (indented, red text)
- Action badges:
  - `✓ COPY` — blue tint background, blue text
  - `⚠ COPY` — yellow tint, yellow text
  - `✗ REVIEW` — red tint, red text
  - `• SKIP` — gray, dim text
- Sortable by clicking column headers (default: filename ascending)
- Resolution/codec/FPS cell colors:
  - Red if that field caused a failure
  - Yellow if that field caused a warning
  - Default otherwise

**Version Conflicts section** (only shown if conflicts detected):
- Section header "VERSION CONFLICTS DETECTED"
- One row per conflict:
  ```
  SCR01_OpeningVideo: v03 (currently active) and v04 (incoming)
  SCR02_OpeningVideo: v03 (currently active) and v04 (incoming)
  ```

**Stale Folders section** (only shown if detected):
- Same pattern as in dashboard banner

**Summary bar** (bottom):
- Three stat pairs: "N files to copy (X.X GB)" · "N files to _REVIEW" · "N to skip"

### 9.4 Phase 4: Copying (transitional)

When Proceed with Copy is clicked:

- Replace the plan view with copy progress display:
  - "Copying Files..." heading
  - CTkProgressBar (determinate, 0-100%)
  - Percentage label
  - **Copy log:** CTkTextbox (read-only, monospace, auto-scrolling). Each completed file appended as a line: "Copying N of M: <filename> (X.X MB)... done"
  - Successfully copied files: line in green
  - Failed copies: line in red

Copy worker (background thread):
1. For each file in plan:
   a. Compute temp destination path (`<dest>.tmp`)
   b. Use `shutil.copy2` source → temp
   c. On success: rename temp → final
   d. On failure: delete temp, log error
   e. Post progress update to main thread
2. Update DeliveryLog.txt
3. Write detailed intake_YYYYMMDD_HHMMSS.txt log
4. Post completion to main thread

### 9.5 Phase 5: Intake Complete

When copy completes, replace the progress display with results.

**Header:**
- "Intake Complete" (large, bold)
- **↩ New Intake button** (primary, top-right) → returns to Phase 1

**Copied Files section:**
- Collapsible, green-tinted header showing "✓ N files copied · X.X GB total"
- Inside: full table of copied files
- Each file row may have warning sub-rows (yellow) for non-blocking issues encountered

**_REVIEW Files section** (only shown if any files routed):
- Collapsible, red-tinted header showing "▲ N files routed to _REVIEW · require manual inspection"
- Inside: full table of routed files
- Each file row has failure sub-rows (red) explaining why it was routed

**Skipped Files section** (only shown if any skipped):
- Collapsible, gray-tinted header showing "• N files skipped (already present)"
- Inside: list of skipped filenames

**Intake Log block** (bottom):
- Section label "INTAKE LOG"
- Path display (CTkTextbox, monospace, cyan, read-only): full path to the detailed log
- **📄 Open Log in Text Editor button** → uses `open_in_editor()` from setup.py

### 9.6 Threading and cancellation

- Both scan and copy run on background threads
- v2.0 does NOT support cancellation of in-progress scan or copy
- Sidebar nav buttons are disabled during scan and copy
- Operator must wait for completion or kill the application
- v2.1+ may add cancellation support if needed

### 9.7 Error handling

If the scan worker fails (e.g., source folder permission denied):
- Return to Phase 1
- Show error toast: "Scan failed: <reason>"
- Source folder field retains its value

If a copy operation fails for an individual file:
- Log the error in the copy log (red text)
- Continue with remaining files
- Show in results that one or more files failed
- The detailed intake log captures the specifics

If the entire copy operation fails (e.g., destination drive disconnected):
- Stop copy worker
- Return to Phase 3 (the plan)
- Show error toast: "Copy failed: <reason>. Files copied so far: N of M"

---

## 10. Generate Spec Document View

A simple, single-action view.

### 10.1 Layout

**Initial state (before generation):**
- Heading "Generate Spec Document"
- Description: "Generate a delivery specification document for vendors and content creators based on the current show configuration."
- **⎘ Generate Document button** (primary blue)

No output format dropdown — only .docx is supported in v2.0.

**After generation:**
- Heading + description (unchanged)
- **Success message** (green tinted frame): "✓ Spec document generated successfully"
- **Output file path** (CTkTextbox, monospace, cyan, read-only): full path to the generated docx
- **📂 Open File button** (primary blue) → opens docx in default handler
- **Generate Another button** (secondary) → resets the view to initial state

### 10.2 Generation behavior

1. Read current config (in-memory, already loaded)
2. Open `templates/spec_template.docx`
3. Replace placeholders with config values (logic identical to v1's `spec_generator.py`)
4. Rebuild the screens table from config
5. Save to `<show_root>/<show_name>_DeliverySpec.docx` (overwrites existing file with same name)
6. Display success state

The spec template is Pixera-flavored in v2.0 (preset-aware templates deferred to v2.1+).

### 10.3 Error handling

If generation fails (template missing, write error):
- Display error message in red-tinted frame
- Generate Document button remains visible for retry

---

## 11. Config Editor (CTkToplevel popup)

Opens via the sidebar's Edit Config button. A separate window that sits above the main window.

### 11.1 Window properties

- **Class:** subclass of `customtkinter.CTkToplevel`
- **Default size:** 760 × 620
- **Minimum size:** 700 × 580
- **Resizable:** yes
- **Title:** "Edit Show Configuration — <ShowName>"
- **Modal:** non-modal but always-on-top (transient to main window)

### 11.2 Layout

- **Tab bar** (CTkTabview) at top with four tabs: Show Info, Expected Specs, Screens, Validation
- **Tab content area** in the middle (varies by selected tab)
- **Footer row** at bottom:
  - Cancel button (secondary, left)
  - 💾 Save Configuration button (primary blue, right)

### 11.3 Dirty state tracking

The editor tracks whether any field has been modified since open. If dirty:

- **Cancel button** prompts: "You have unsaved changes. Discard / Keep Editing"
- **X (close) button** same prompt
- **Save button** writes the changes and closes (or stays open per user preference — TBD by implementation)

### 11.4 Validation behavior

**On field blur** (operator tabs away from a field): client-side validation runs for that field only. If invalid, the field is outlined in red and an inline error message appears beneath it.

**On Save Configuration click:**
1. Run all client-side validations across all tabs
2. If any tab has errors: switch to that tab, focus the first errored field, do not save
3. If all client-side validations pass, build the config dict
4. Run `validate_config()` from modules/config.py
5. If validation passes: write to disk, show success toast "✓ Configuration saved", trigger main window refresh, close editor
6. If validation fails: show error toast with the specific message, keep editor open with operator's edits intact

### 11.5 Tab 1: Show Info

Form fields:

- **Show Name** (CTkEntry, full width)
  - Validation: non-empty, filename-safe characters
- **Show Date** (CTkEntry with placeholder "YYYY-MM-DD")
  - Validation: matches YYYY-MM-DD format, valid calendar date
- **OPERATOR** section heading
- **Operator Name** (CTkEntry, half-width)
  - Validation: non-empty, no character restrictions
- **Operator Email** (CTkEntry, half-width)
  - Validation: non-empty, basic email format check (contains `@`)

Form is two-column where it makes sense (operator name and email side by side).

### 11.6 Tab 2: Expected Specs

#### Preset Bar

Top of tab, horizontal row:

- **"Preset:" label**
- **Preset selector** (CTkComboBox or CTkOptionMenu, populated from built-in + custom presets):
  - Built-in section (with header "— Built-in —"):
    - Pixera
    - PlayBack Pro
    - Mitti
  - Custom section (with header "— Custom —"):
    - Any user-saved presets
  - Always-present option: "— Select a preset —" (default placeholder)
- **Load button** (secondary): applies the selected preset to all fields below
- **💾 Save as Preset button** (ghost style): prompts for name, saves current values as custom preset
- **📁 Browse button** (ghost style): opens file picker to import an external preset JSON file

**Save as Preset inline behavior:**
When Save as Preset is clicked, an inline row appears below the preset bar:
- CTkEntry for preset name
- Confirm button
- Cancel button

On confirm: validate name, write file to custom_presets folder, refresh dropdown, show toast "✓ Preset '<name>' saved."

#### Technical Specifications

Three-column grid of dropdowns:

| Field | Widget | Options |
|---|---|---|
| Framerate (fps) | CTkOptionMenu | 23.976, 24, 25, 29.97, 30, 50, 59.94, 60, **N/A**, **Custom...** |
| Color Space | CTkOptionMenu | bt709, bt2020, smpte170m, gbr, **N/A**, **Custom...** |
| Color Range | CTkOptionMenu | tv, pc, **N/A**, **Custom...** |
| Audio Sample Rate | CTkOptionMenu | 44100, 48000, 96000, **N/A**, **Custom...** |
| Audio Channels | CTkOptionMenu | 1, 2, 4, 6, 8, **N/A**, **Custom...** |

**N/A behavior:** When the operator selects N/A:
- Field stored as `null` in the config
- A small label appears beneath the dropdown: "Validation will be ignored for this field"
- The corresponding field on the Validation tab is auto-set to "Ignore" and disabled (cannot be changed while spec is N/A)

**Custom... behavior:** When the operator selects Custom..., a CTkEntry replaces the dropdown for freeform input. A small "↺ Use dropdown" link appears below to revert to the dropdown.

#### Codecs Section

Section heading "CODECS".

**Expected Codecs:**
- Description: "file must use one of these"
- Tag list area: a frame containing one tag per codec, each as:
  - Codec identifier label (monospace)
  - Small ✕ button to remove the tag
- Below the tag list:
  - "Add codec..." dropdown (CTkOptionMenu, populated with codec identifiers from `CODEC_TAG_MAP` keys, filtered to exclude codecs already in the list, plus a "Custom..." option)
  - **+ Add button** (secondary)

**Preferred Codecs:**
- Description: "no warning issued when file uses one of these"
- Same tag-list pattern, but tags styled with blue tint
- Validation: every preferred codec must also be in expected codecs (auto-add to expected if needed, or show error)

**"Custom..." codec entry:**
When operator picks Custom..., an inline CTkEntry appears for freeform codec identifier. The custom codec is added to the list but won't be validated against the codec map (probe will report unknown tag as None, codec check fails). This is documented as an advanced feature.

### 11.7 Tab 3: Screens

**Description:** "Define output screens. IDs must be unique (e.g., SCR01). Screen additions update the Dashboard immediately after saving."

**+ Add Screen button** (top right, secondary)

**Screen table** (CTkScrollableFrame containing a grid):

| Column | Widget | Notes |
|---|---|---|
| SCREEN ID | CTkEntry | e.g., SCR01, must be unique, filename-safe |
| DISPLAY NAME | CTkEntry | e.g., HouseLeft, optional, filename-safe |
| RESOLUTION | CTkOptionMenu | 1280x720, 1920x1080, 2560x1440, 2688x1152, 3840x2160, **Custom...** |
| Delete | CTkButton | ✕ icon, danger style, removes row |

**Custom resolution:**
When Custom... is selected, an inline CTkEntry replaces the dropdown. The operator types a resolution like "3840x816" (must match `####x####` regex).

**Validation:**
- Each row's Screen ID must be non-empty and unique
- Display Name is optional but if present must be filename-safe
- Resolution can be empty (skipped) or must match `####x####`

**Dashboard sync:**
Adding/removing/renaming screens updates the dashboard's screen card grid immediately upon save (via the main window's refresh trigger).

### 11.8 Tab 4: Validation

**Description:** "Control how strictly each property is validated during intake. Fields set to N/A in Expected Specs are automatically marked Ignore here."

**Color legend** (small text, formatted with color spans):
- **Strict** = reject to _REVIEW (red)
- **Warn** = copy with warning (yellow)
- **Info** = log only (cyan/info)
- **Ignore** = skip check (gray)

**Two-column grid of dropdowns:**

| Property | Options | Auto-Ignore when... |
|---|---|---|
| Resolution | Strict, Warn, Info, Ignore | (no auto-ignore — applies per-screen) |
| Framerate | Strict, Warn, Info, Ignore | Framerate is N/A |
| Codec | Strict, Warn, Info, Ignore | (no auto-ignore) |
| Codec Flavor | Strict, Warn, Info, Ignore | (no auto-ignore) |
| Color Space | Strict, Warn, Info, Ignore | Color Space is N/A |
| Color Range | Strict, Warn, Info, Ignore | Color Range is N/A |
| Audio Sample Rate | Strict, Warn, Info, Ignore | Audio Sample Rate is N/A |
| Audio Channels | Strict, Warn, Info, Ignore | Audio Channels is N/A |
| Screen ID | Strict, Warn, Info, Ignore | (no auto-ignore) |

When a Validation field is auto-set to Ignore due to N/A in Expected Specs, the dropdown is disabled (grayed out) with a tooltip explaining why.

### 11.9 Footer

- **Cancel** (secondary, left): close without saving (with dirty-state prompt if dirty)
- **💾 Save Configuration** (primary blue, right): validate and save

After save:
- Success toast appears briefly to the left of the buttons: "✓ Configuration saved"
- Editor closes
- Main window refreshes to reflect changes (sidebar show info card, dashboard, etc.)

### 11.10 "Open Raw Config" advanced action

A small "📝 Open raw config in text editor" link in the footer (left of Cancel button). Opens the JSON file in Notepad++ (or OS default if Notepad++ not installed) for advanced users. Useful for inspecting the file format or debugging.

This does not bypass the editor — saving via the editor and editing the raw file are separate operations. Operator should not have both open simultaneously (no file lock check in v2.0; just operator awareness).

---

## 12. AppState and screen coordination

### 12.1 AppState

A single `AppState` dataclass holds all app-level state, owned by the root `App` class:

- `tool_root: Path` — install directory
- `user_data_root: Path` — `%LOCALAPPDATA%\ShowMediaIntakeTool\`
- `recent_shows: list[RecentShow]` — loaded at startup, mutated as shows are loaded
- `current_show_root: Path | None` — path of currently loaded show
- `current_config: ShowConfig | None` — currently loaded config dict
- `current_screen: str` — name of currently active screen ("dashboard", "intake", "spec", or "launch")

Screens read from AppState; they do not own state. When a screen needs to change app-level state, it calls a method on the App object which updates AppState and triggers any necessary UI refreshes.

#### Per-show UI preferences

Each `RecentShow` entry can carry a `dashboard_view` field with values `"cards"`, `"compact"`, or `null`:

- `null` (or field absent): use default-by-screen-count behavior
- `"cards"`: operator explicitly chose Cards mode for this show
- `"compact"`: operator explicitly chose Compact mode for this show

When the operator toggles view mode on the dashboard, the corresponding RecentShow entry's `dashboard_view` is updated and `.recent_shows.json` is rewritten. v1 entries (and v2 entries before any explicit toggle) have no `dashboard_view` field, which the loader handles as `null`.

### 12.2 Screen lifecycle

Each screen module defines a class with these methods:

- `__init__(parent_frame, app, app_state)` — build widgets
- `on_show()` — called when this screen becomes active; refresh UI with latest state
- `on_hide()` — called when leaving this screen; opportunity to save in-progress state if needed
- `destroy()` — cleanup

The App class manages screen switching: hide current screen, swap content frame, instantiate or re-show new screen.

### 12.3 Refresh semantics

After certain operations, the UI needs to refresh. The App class exposes a `refresh()` method that:

- Reloads the current config from disk
- Updates the sidebar show info card
- Calls `on_show()` on the current screen to re-render with latest state

Operations that trigger refresh:
- Config Editor save
- Intake completion
- Manual Refresh button click on dashboard

---

## 13. CLI tool changes

The v1 CLI (renamed `cli_intake.py`) is preserved with the following changes for v2:

- **Schema migration** logic added: detects v1 configs, prompts to migrate, writes backup
- **Strictness level "ignore"** supported in config validation and intake
- **N/A handling** in expected_specs (null values)
- **Codec map expansion** (matches GUI version)
- **Report mode removed** from main menu (matches GUI removing standalone report)
- **Tool name** updated in title and prompts to "Show Media Intake Tool"

The CLI is not actively maintained beyond these changes. It remains functional but is positioned as a power-user fallback. Future feature additions go to the GUI only.

---

## 14. Dependencies

### 14.1 Python packages

```
customtkinter>=5.2.0
python-docx>=1.0.0
colorama>=0.4.6  # CLI only, but kept in requirements for the unified install
```

### 14.2 External dependencies

- **ffprobe** (from ffmpeg) on PATH — required, same as v1
- **Notepad++** at `C:\Program Files\Notepad++\notepad++.exe` — optional, used for opening logs and raw config; falls back to OS default

### 14.3 Python version

Python 3.10+ (matching v1).

---

## 15. Distribution

### 15.1 Install location

`C:\Tools\ShowMediaIntakeTool\` — renamed from v1's `C:\Tools\PixeraIntake\`.

### 15.2 setup_check.bat

Updated from v1 to:
- Verify Python 3.10+ installed
- Verify ffprobe on PATH
- Install Python dependencies including customtkinter
- Verify the install location is correct
- Check for v1 install at old location and prompt operator to clean up if found

### 15.3 Desktop shortcut

Created during initial setup (or by `setup_check.bat`):
- Name: "Show Media Intake Tool"
- Target: `python C:\Tools\ShowMediaIntakeTool\show_media_intake.py`
- Icon: TBD (could use a custom icon if provided)
- Working directory: `C:\Tools\ShowMediaIntakeTool\`

A second optional shortcut for the CLI:
- Name: "Show Media Intake Tool (CLI)"
- Target: `python C:\Tools\ShowMediaIntakeTool\cli_intake.py`

### 15.4 Migration from v1 install

If a v1 install exists at `C:\Tools\PixeraIntake\`:
- v2 install does not auto-migrate
- `setup_check.bat` detects the old install and shows a message: "An older version of this tool exists at C:\Tools\PixeraIntake\. After verifying v2 works, you may delete the old install."
- The old `.recent_shows.json` is not auto-imported (different location, different scope)

---

## 16. Error handling

### 16.1 Categories

**Configuration errors:** Invalid JSON, missing required fields, validation failures. The launch screen or Config Editor reports specifics.

**File system errors:** Permission denied, disk full, source not accessible. Reported via toast notifications and detailed in logs.

**ffprobe errors:** Cannot read file metadata. File treated as unknown specs, routed to `_REVIEW/`.

**Threading errors:** Background worker exceptions. Caught by worker, posted to main thread queue, displayed to operator.

**GUI errors:** Unexpected widget exceptions. Caught at the App level top exception handler, logged, displayed in error modal.

### 16.2 Critical failures

These halt the tool with a clear message:

- ffprobe not on PATH (detected at startup)
- Cannot create user data directory (`%LOCALAPPDATA%\ShowMediaIntakeTool\` write failure)
- Cannot read `templates/` folder (broken install)

### 16.3 Recoverable failures

These show user-friendly errors and let the operator retry:

- Single file copy failure (logged, skipped, continues)
- Single file probe failure (treated as unknown, routed to review)
- Config validation failure (Config Editor stays open, error displayed)
- Spec generation failure (Spec view stays open, error displayed)

---

## 17. Out of scope for v2.0

These features are explicitly deferred to v2.1+:

- **Additional built-in presets with verified content** (PlayBack Pro and Mitti currently ship as Pixera duplicates; v2.1 adds verified codec lists)
- **Preset-aware spec templates** (each preset getting its own .docx template; v2.0 uses single Pixera-flavored template)
- **PDF and plain text spec output formats**
- **Drag-and-drop folder selection** in source folder picker
- **Cancellation of in-progress scan or copy operations**
- **Light theme toggle / theme customization**
- **In-app help / tutorial overlay**
- **Auto-update mechanism**
- **Multi-language support**
- **Cloud sync of recent shows or presets**
- **File preview / thumbnail generation**
- **Network share scanning / cloud platform integration**
- **Email notifications on intake completion**
- **Pixera or other playback system API integration**
- **File checksumming / hash-based content comparison**
- **Auto-archive of old versions** (existing v1 design — not changing)
- **Multi-operator support per installation**
- **Run-of-show map automation**
- **Sample test data generator**
- **Custom filename convention with optional tokens** — custom patterns must not require all default tokens; see `PROGRESS.md` § Planned updates (2026-07-27)
- **Still images and image sequences** (`.jpg`, `.png`, `.tga`, `.tiff`, `.exr`, etc.) — config, ffprobe probing, and type-aware validation; see `PROGRESS.md` § Planned updates (2026-07-27)

---

## 18. Acceptance criteria for v2.0

The release is considered complete when:

1. Launch screen, dashboard, intake, spec generation, and config editor all work end-to-end
2. v1 configs can be migrated to v2 successfully with backup
3. Three built-in presets (Pixera, PlayBack Pro, Mitti) load correctly (even though contents are identical)
4. Custom preset save/load works
5. The "ignore" strictness level and N/A spec field handling work correctly
6. Background scan and copy operations don't freeze the UI
7. Filter chips and column sorting work in tables
8. Multi-version slug detection and stale folder warnings appear in dashboard banners and intake plan
9. Version conflict detection appears in intake plan
10. Generated spec docx is identical in content to v1's output
11. CLI version still works for power users with all the schema additions
12. README and PLAN-V2.md documents are complete and accurate

---

## 19. Future roadmap signals

For reference; not for v2.0 implementation:

**v2.1 priorities** (likely targets based on this conversation):
- Verified PlayBack Pro and Mitti preset contents
- Preset-aware spec docx templates
- Drag-and-drop folder selection

**v2.2 priorities** (field testing feedback, 2026-07-27):
- **Truly custom filename convention** — allow any subset of tokens when Custom is enabled; only routed intake requires `screen` (implementation notes in `PROGRESS.md`)
- **Still images and image sequences** — common show delivery formats; config + ffprobe + validation split by media type (implementation notes in `PROGRESS.md`)
- **Hide launcher terminal window** — desktop shortcut should not show a persistent PowerShell console; hidden launcher + error dialogs (implementation notes in `PROGRESS.md`)

**v2.2+ wishlist:**
- PDF spec output
- Cancellation of long operations
- Light theme support
- In-app help

These are signals, not commitments. Real prioritization happens after v2.0 ships and operators provide feedback.
