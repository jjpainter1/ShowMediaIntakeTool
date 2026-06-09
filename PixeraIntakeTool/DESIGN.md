# Pixera Intake Tool — Design Document

**Version:** 1.0
**Status:** Specification (ready for implementation)
**Target platform:** Windows (Python 3.10+)

---

## 1. Purpose

The Pixera Intake Tool is a Python-based command-line application that automates the receiving, validation, and filing of show content for Pixera media servers. It enforces a standardized content delivery specification, generates per-show specification documents, and reports on show content state.

The tool exists to solve four specific recurring problems in show production:

1. **Inconsistent file naming** between run-of-show references and delivered files.
2. **Confusing version management** (files named "final" then "final2" then "REAL_FINAL").
3. **Unclear screen identification** in delivered content.
4. **Disorganized content** within Pixera projects due to chaotic delivery.

The tool is an **early warning system, not a bouncer**. It surfaces problems clearly so the operator can decide how to handle them. It does not block deliveries arbitrarily, except in cases where files cannot be safely placed in active folders without manual review.

---

## 2. Design Principles

These principles take precedence when implementation tradeoffs arise:

1. **Content identity is durable; cue position is not.** Filenames describe what the content *is*, not where it currently lives in the show. Cue numbers can shift during tech without anything in the media folder needing to change.

2. **The intake gate is the enforcement layer.** The delivery specification is upstream; the tool is the active enforcement of that specification at receiving time.

3. **Never delete files; never move active files.** Both old and new versions coexist. Supersession is detected and reported, but no file movement happens automatically. The operator handles version swaps inside Pixera, where resource paths can be updated safely.

4. **One source of truth: the show config file.** All show-specific specifications (resolution, framerate, codec expectations, screen list, operator contact) live in a single JSON file per show. Validation rules and document generation both read from this file.

5. **Two-phase execution always.** Plan first, prompt for confirmation, then execute. No silent operations on the file system.

6. **Strict validation, transparent reporting.** Validation rules are configurable per show. Failures are clearly distinguished from warnings, and warnings from informational notes.

7. **Atomic file operations.** Files copy to temporary names and only become visible at their final names after the copy completes successfully. Crashes mid-copy never leave broken files in active folders.

---

## 3. Architecture Overview

### 3.1 Components

The tool consists of the following Python files, all living in `C:\Tools\PixeraIntake\`:

```
C:\Tools\PixeraIntake\
├── pixera_intake.py              # Main launcher with menu system
├── modules\
│   ├── __init__.py
│   ├── config.py                 # Config loading and validation
│   ├── intake.py                 # Intake mode logic (plan + execute)
│   ├── spec_generator.py         # Spec docx generation
│   ├── show_report.py            # "What's in my show" mode
│   ├── ffprobe_wrapper.py        # ffprobe integration for tech specs
│   ├── filename_parser.py        # Filename convention parsing/validation
│   ├── recent_shows.py           # Recent shows menu/memory
│   └── console_ui.py             # Console output formatting (colors, tables)
├── templates\
│   ├── show_config_starter.json  # Template config copied to new shows
│   └── spec_template.docx        # Template for generated spec documents
├── .recent_shows.json            # Tool-local memory of recently used shows
└── README.md                     # User documentation
```

### 3.2 External Dependencies

- **Python 3.10+** (standard library + the packages below)
- **ffmpeg/ffprobe** (already installed on Pixera servers; the tool calls `ffprobe` as a subprocess)
- **Python packages:**
  - `python-docx` — for spec document generation
  - `colorama` — for console color output on Windows

The tool does not require any GUI framework for v1. It uses `tkinter` (Python standard library) only for the folder picker dialogs.

### 3.3 Data Flow

```
[Operator launches tool]
         ↓
[Recent shows menu]
         ↓
[Show project root selected/entered]
         ↓
[Config loaded and validated]  ──→ [Invalid: report and exit]
         ↓
[Main menu: Intake / Spec / Report / Switch / Quit]
         ↓
[Selected mode runs]
         ↓
[Returns to main menu, or recent shows on Switch]
```

---

## 4. Show Project Structure

The show project root is created **manually by the operator** before running the tool. The tool operates within this root.

### 4.1 Expected Structure

```
D:\Shows\StJude2025_20260615\          ← Show project root (created by operator)
├── show_config.json                    ← Created/managed by tool
├── StJude2025_v1_JJ.avp                ← Pixera project file (operator)
├── (other show paperwork: emails, contracts, etc.)
└── Media\                              ← Created by tool
    ├── _LOGS\                          ← Created by tool
    │   ├── DeliveryLog.txt             ← Appended to per intake
    │   └── intake_YYYYMMDD_HHMMSS.txt  ← One per intake run
    ├── _REVIEW\                        ← Created by tool
    ├── _REFERENCE\                     ← Created by tool (for operator-placed reference materials)
    ├── SCR01\                          ← Created by tool from config
    ├── SCR02\                          ← Created by tool from config
    └── SCR03\                          ← Created by tool from config
```

### 4.2 Folder Naming

Screen folder names come **directly from the `id` field** in the config's screens array. No numeric prefix is added. No descriptive name is appended. The tool copies the screen ID exactly as it appears in config.

Example config:
```json
"screens": [
  { "id": "SCR01", "name": "StageLeft", "resolution": "3840x2160" },
  { "id": "SCR02", "name": "CenterIMAG", "resolution": "1920x1080" }
]
```

Resulting folders: `Media/SCR01/` and `Media/SCR02/`.

The `name` field exists in config for human reference and is used in the generated spec document, but does not affect folder names.

### 4.3 Special Folders

When the config indicates use of special prefixes (typically the operator adds these manually as needed in the config):

- `SCRwide` content → `Media/SCRwide/`
- `SCRall` content → `Media/SCRall/`
- Audio files → `Media/AUD/`

These are created on-demand if files matching the prefix appear during intake. The operator can also add them explicitly to the config screens list.

---

## 5. Show Config File

### 5.1 Location and Format

`show_config.json` lives at the show project root. It is JSON formatted, hand-edited by the operator using Notepad++.

### 5.2 Schema

```json
{
  "show_name": "StJude2025",
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
    "prores_422_proxy",
    "prores_422_lt",
    "prores_422",
    "prores_422_hq",
    "prores_4444",
    "prores_4444_xq"
  ],
  "preferred_codecs": [
    "prores_422_hq",
    "prores_4444"
  ],
  "screens": [
    { "id": "SCR01", "name": "StageLeft",   "resolution": "3840x2160" },
    { "id": "SCR02", "name": "CenterIMAG",  "resolution": "1920x1080" },
    { "id": "SCR03", "name": "StageRight",  "resolution": "3840x2160" }
  ],
  "validation_strictness": {
    "resolution": "strict",
    "framerate": "strict",
    "codec": "strict",
    "codec_flavor": "warn",
    "color_space": "warn",
    "color_range": "warn",
    "audio_sample_rate": "info",
    "audio_channels": "info"
  }
}
```

### 5.3 Field Definitions

| Field | Type | Required | Notes |
|---|---|---|---|
| `show_name` | string | Yes | Used in spec doc and filenames. Validated for filename-safe characters. |
| `show_date` | string | Yes | YYYY-MM-DD format. Used in spec doc. |
| `operator.name` | string | Yes | Used in spec doc contact section. |
| `operator.email` | string | Yes | Used in spec doc contact section. |
| `expected_specs.framerate` | number | Yes | Numeric framerate (e.g., 30, 24, 59.94). |
| `expected_specs.color_space` | string | Yes | ffprobe color_space value (typically "bt709"). |
| `expected_specs.color_range` | string | Yes | "tv" (limited/legal range) or "pc" (full range). Default "tv". |
| `expected_specs.audio_sample_rate` | number | Yes | Hz (e.g., 48000). |
| `expected_specs.audio_channels` | number | Yes | Channel count (e.g., 2 for stereo). |
| `expected_codecs` | array | Yes | Array of acceptable codec identifiers. Files matching any pass codec validation. |
| `preferred_codecs` | array | Yes | Subset of `expected_codecs`. Files matching are preferred; non-preferred but acceptable trigger a warning per `codec_flavor` strictness. |
| `screens` | array | Yes | Array of screen objects. At minimum each must have `id`. `name` and `resolution` are recommended. |
| `validation_strictness` | object | Yes | Per-field strictness. See section 6.4. |

### 5.4 Validation Rules

The tool validates the config every time it loads (every mode). Validation failures produce a clear error and halt the tool.

**Required fields:** All fields marked Yes above must be present and non-empty.

**Filename-safe character validation:** The following fields must contain only letters, digits, dashes, and underscores. Spaces and other special characters are rejected:
- `show_name`
- `screens[].id`
- `screens[].name` (if present)

**Free-text fields** (no character restrictions):
- `operator.name`
- `operator.email`

**Format validation:**
- `show_date` must match `YYYY-MM-DD`
- `screens[].resolution` (if present) must match `####x####` (digits, lowercase x, digits)
- `validation_strictness` values must be one of: `strict`, `warn`, `info`

**Logical validation:**
- `preferred_codecs` must be a subset of `expected_codecs`
- `screens` must contain at least one entry
- Screen `id` values must be unique within the array

### 5.5 Codec Identifiers

The tool maps ffprobe's codec_tag values to human-friendly identifiers used in config:

| Identifier | ffprobe codec_tag | Description |
|---|---|---|
| `prores_422_proxy` | `apco` | ProRes 422 Proxy |
| `prores_422_lt` | `apcs` | ProRes 422 LT |
| `prores_422` | `apcn` | ProRes 422 (Standard) |
| `prores_422_hq` | `apch` | ProRes 422 HQ |
| `prores_4444` | `ap4h` | ProRes 4444 |
| `prores_4444_xq` | `ap4x` | ProRes 4444 XQ |

Additional codec identifiers can be added as needed but v1 supports the ProRes family.

### 5.6 Starter Config

When setup mode creates a new config, it writes `templates/show_config_starter.json` to the show project root with placeholder values:

```json
{
  "show_name": "REPLACE_WITH_SHOW_NAME",
  "show_date": "YYYY-MM-DD",
  "operator": {
    "name": "REPLACE_WITH_OPERATOR_NAME",
    "email": "REPLACE_WITH_OPERATOR_EMAIL"
  },
  "expected_specs": {
    "framerate": 30,
    "color_space": "bt709",
    "color_range": "tv",
    "audio_sample_rate": 48000,
    "audio_channels": 2
  },
  "expected_codecs": [
    "prores_422_proxy", "prores_422_lt", "prores_422",
    "prores_422_hq", "prores_4444", "prores_4444_xq"
  ],
  "preferred_codecs": [
    "prores_422_hq", "prores_4444"
  ],
  "screens": [
    { "id": "SCR01", "name": "REPLACE_OR_LEAVE_BLANK", "resolution": "REPLACE_WITH_RESOLUTION" }
  ],
  "validation_strictness": {
    "resolution": "strict",
    "framerate": "strict",
    "codec": "strict",
    "codec_flavor": "warn",
    "color_space": "warn",
    "color_range": "warn",
    "audio_sample_rate": "info",
    "audio_channels": "info"
  }
}
```

---

## 6. Filename Convention

### 6.1 Pattern

```
SCR##_ContentSlug_v##_YYYYMMDD.ext
```

### 6.2 Field Definitions

| Field | Format | Example | Validation |
|---|---|---|---|
| `SCR##` | `SCR` + 2-digit number | `SCR01`, `SCR12` | Must match a screen `id` in config, OR be one of the special prefixes |
| `ContentSlug` | PascalCase, alphanumerics + dashes | `OpeningVideo`, `50thAnniversary` | Must contain only letters, digits, and dashes |
| `v##` | `v` + 2-digit number | `v01`, `v12` | Must start with lowercase `v`, followed by 1 or more digits |
| `YYYYMMDD` | 8 digits | `20260425` | Must be a valid date |
| `ext` | File extension | `.mov`, `.wav` | Any extension accepted; tech spec validation determines suitability |

### 6.3 Special Prefixes

| Prefix | Format | Meaning |
|---|---|---|
| `SCRwide-XX-YY-ZZ` | `SCRwide` + dash-separated 2-digit screen numbers | Content spanning multiple specific screens |
| `SCRall` | `SCRall` (no number) | Content for all screens identically |
| `AUD` | `AUD` (no number) | Audio file (replaces SCR prefix) |

### 6.4 Looping Content Suffix

Content intended as a seamless loop should have `-LOOP` appended to the slug:

```
SCR01_AmbientBackground-LOOP_v01_20260425.mov
```

The tool does not enforce loop-suffix presence (it's a delivery convention, not a tool requirement). It is mentioned in the spec document.

### 6.5 Validation Behavior

The filename parser attempts to extract: screen prefix, slug, version, date, extension.

**Validation outcomes:**

| Outcome | Meaning | Action |
|---|---|---|
| Full match | All four fields parsed and valid | Route by screen prefix to active screen folder |
| Partial match (recognizable screen prefix only) | Filename starts with valid `SCR##`/`SCRwide`/`SCRall`/`AUD` but other fields malformed | Copy with warning to active screen folder |
| No match | No recognizable prefix | Copy to `_REVIEW/` |

This implements the "loose with warnings" filename validation philosophy.

---

## 7. Tech Spec Validation

### 7.1 Validation Process

For each source file, the tool calls `ffprobe` and extracts:

- Video stream: width, height, framerate, codec_name, codec_tag, color_space, color_range
- Audio stream (if present): sample_rate, channels

These are compared against expected values from config.

### 7.2 Strictness Levels

Each validation check has a strictness level configured in `validation_strictness`:

| Level | Behavior on mismatch |
|---|---|
| `strict` | File routed to `_REVIEW/`, intake report flags as failure |
| `warn` | File copied to active folder, intake report flags as warning |
| `info` | File copied to active folder, mentioned in report only (no warning flag) |

### 7.3 Resolution Validation

Resolution is validated **per screen**. The screen prefix in the filename determines which screen's resolution to check against.

- `SCR01_xxx_xxx_xxx.mov` is checked against the resolution of `SCR01` in config.
- If filename uses `SCRwide`, resolution validation is skipped (multi-screen content has no single expected resolution).
- If filename uses `SCRall`, resolution must match at least one of the configured screens (otherwise warn).
- If filename has no screen-specific prefix or uses `AUD`, resolution validation is skipped.
- If the screen ID in the filename is not in config, the validation is skipped and a separate warning is produced ("file targets unknown screen").

### 7.4 Codec Validation

Codec is validated as a **two-tier check**:

**Tier 1: Acceptance.** The file's codec_tag must match one of the entries in `expected_codecs`. Failure follows the `codec` strictness level.

**Tier 2: Preference.** If the file passes Tier 1, the codec_tag is checked against `preferred_codecs`. If not in the preferred list, a warning is produced per the `codec_flavor` strictness level.

This implements the "any ProRes acceptable, but warn if not 422 HQ or 4444" behavior.

### 7.5 Other Validations

- **Framerate:** strict by default. Compared as floating-point with small epsilon (0.01) to handle 29.97 vs 30 distinction.
- **Color space:** warn by default. ffprobe value compared to `expected_specs.color_space`.
- **Color range:** warn by default. ffprobe color_range value compared to `expected_specs.color_range`.
- **Audio sample rate:** info by default.
- **Audio channels:** info by default.

### 7.6 ffprobe Command

```
ffprobe -v error -print_format json -show_streams -show_format <filepath>
```

The tool parses the JSON output and extracts the relevant fields. ffprobe is expected to be on PATH; if not found, the tool produces a clear error at startup.

---

## 8. Intake Mode

### 8.1 Workflow

```
[Operator selects Intake from main menu]
         ↓
[Folder picker for source folder]
         ↓
[PHASE 1: PLAN]
  - Walk source recursively, find all media files
  - Parse each filename
  - Run ffprobe on each
  - Determine destination for each (active folder, _REVIEW, or skip)
  - Detect existing-file matches (name + size)
  - Detect version conflicts (same slug, different version)
  - Detect stale folders (folders in Media not in config)
         ↓
[Display plan report with color-coded statuses]
         ↓
[Prompt: "Proceed with copy? [Y/N]"]
         ↓
[If N: exit cleanly, no changes]
[If Y: PHASE 2: EXECUTE]
  - Copy each file to <destination>.tmp
  - On copy success, rename to final name
  - On copy failure, delete .tmp and continue
  - Update DeliveryLog.txt
  - Write detailed intake_YYYYMMDD_HHMMSS.txt log
  - Display summary
```

### 8.2 Source Folder Handling

The tool walks the source folder **recursively**. Files are routed by their parsed filename, not by their position in the source folder structure. This means:

- Properly organized deliveries (matching the spec's screen folder structure) work fine.
- Flat folders of correctly-named files work fine.
- Mixed/chaotic source structures work fine, as long as filenames identify their target.

Files that cannot be routed (no recognizable screen prefix) go to `_REVIEW/`.

### 8.3 Existing File Detection

For each source file with a determined destination:

1. Check if a file with the same name exists at the destination.
2. If not: proceed with copy.
3. If yes, compare file sizes.
4. If sizes match: skip silently. Note in report as "already present, skipped."
5. If sizes differ: route to `_REVIEW/` instead. Note in report as "name conflict, different content."

### 8.4 Version Conflict Detection

For each source file that parses successfully:

1. Extract the slug (e.g., `OpeningVideo` from `SCR01_OpeningVideo_v04_20260425.mov`).
2. Check the destination screen folder for any file matching the same `SCR##_<slug>_v*_*.ext` pattern.
3. If existing version found with different version number, flag as version conflict.
4. **Both files coexist** — the existing file is not moved or deleted. The new file is placed alongside it.
5. The intake report explicitly lists version conflicts so the operator can address them in Pixera.

### 8.5 Stale Folder Detection

Before the plan phase completes, the tool inspects the Media folder structure:

1. List all immediate subfolders of `Media/`.
2. Filter out tool-managed folders (`_LOGS`, `_REVIEW`, `_REFERENCE`).
3. Compare remaining folders against config screens.
4. Any folder not in config is flagged as "stale" with file count.
5. The report includes these warnings but processing continues normally.

Missing screen folders (in config but not on disk) are created during the plan phase before any operations.

### 8.6 Atomic Copy

For every file copied:

1. Determine final destination path (e.g., `Media/SCR01/SCR01_OpeningVideo_v04_20260425.mov`).
2. Create temp path with `.tmp` suffix (e.g., `<destination>.tmp`).
3. Use `shutil.copy2` (or equivalent that preserves metadata) to copy source → temp.
4. After copy completes successfully, rename temp → final.
5. If copy fails (exception), delete the temp file and log the failure. Continue to next file.
6. On next intake run, any leftover `.tmp` files at destinations are detected and removed automatically.

### 8.7 Plan Report Format

The plan report is shown to the console before the proceed prompt. It must be clear and scannable. Suggested format:

```
======================================================================
  PIXERA INTAKE — PLAN PHASE
======================================================================
  Show:    StJude2025 (2026-06-15)
  Source:  E:\AgencyDelivery_2026-06-12\
  Files:   24 files found in source

======================================================================
  PROPOSED ACTIONS
======================================================================

  ✓ COPY     SCR01_OpeningVideo_v04_20260425.mov         (1.2 GB) → Media\SCR01\
                Replaces v03 (currently active, will coexist)

  ✓ COPY     SCR02_OpeningVideo_v04_20260425.mov         (685 MB) → Media\SCR02\

  ⚠ COPY     SCR03_OpeningVideo_v04_20260425.mov         (1.1 GB) → Media\SCR03\
                WARN: framerate is 29.97, expected 30

  ⚠ COPY     SCR01_50thAnniversary_v01_20260424.mov      (820 MB) → Media\SCR01\
                WARN: codec is ProRes 422 LT (acceptable, not preferred)

  ✗ REVIEW   Opening Video FINAL.mov                     (1.4 GB) → Media\_REVIEW\
                FAIL: filename does not match convention

  ✗ REVIEW   SCR01_ClosingMontage_v02_20260425.mov       (980 MB) → Media\_REVIEW\
                FAIL: codec is H.264, expected ProRes

  • SKIP     SCR02_50thAnniversary_v01_20260424.mov      (already present, identical)

======================================================================
  WARNINGS
======================================================================
  Stale folder found: Media\SCR04_OldStaging\ (3 files)
    Not listed in config. Verify if needed.

  Version conflicts:
    SCR01_OpeningVideo: v03 (active) and v04 (incoming)
    SCR02_OpeningVideo: v03 (active) and v04 (incoming)
    SCR03_OpeningVideo: v03 (active) and v04 (incoming)

======================================================================
  SUMMARY
======================================================================
    5 files to copy (3.8 GB)
    2 files to route to _REVIEW
    1 file to skip (already present)
    3 version conflicts detected
    1 stale folder detected

  Proceed with copy? [Y/N]:
```

### 8.8 Color Coding

When `colorama` is available, status indicators use color:

- `✓ COPY` — green
- `⚠ COPY` — yellow
- `✗ REVIEW` — red
- `• SKIP` — cyan/dim
- Section headers — bold

### 8.9 Logs

Two logs are written per intake run:

**`Media/_LOGS/DeliveryLog.txt`** (appended to):
```
2026-06-12 14:30 | E:\AgencyDelivery_2026-06-12\ | 5 copied, 2 review, 1 skip | Notes: 3 version conflicts on OpeningVideo
```

**`Media/_LOGS/intake_YYYYMMDD_HHMMSS.txt`** (full transcript):
- Header with show, source, timestamp
- Complete plan report
- Operator decision (proceed Y/N)
- Per-file execution results (success/failure)
- Final summary

---

## 9. Spec Generation Mode

### 9.1 Workflow

```
[Operator selects Spec Generation from main menu]
         ↓
[Tool reads show_config.json from current show]
         ↓
[Tool loads templates/spec_template.docx]
         ↓
[Tool replaces all bracketed placeholders with config values]
         ↓
[Tool dynamically populates the screens table from config]
         ↓
[Tool saves output to <show_root>/<show_name>_DeliverySpec.docx]
         ↓
[Tool reports success and full path]
```

### 9.2 Template Placeholders

The template docx contains bracketed placeholders that map to config values:

| Placeholder in template | Config field |
|---|---|
| `[Project Name]` | `show_name` |
| `[YYYY-MM-DD]` (Show Date) | `show_date` |
| `[YYYY-MM-DD]` (Delivery Target) | Not in config; left as bracket for manual edit |
| `[##]` (Total screens) | `screens.length` |
| `[Rec.709]` (Color Space) | `expected_specs.color_space` mapped to friendly name |
| `[e.g. 30 / 60 fps]` (Frame Rate) | `expected_specs.framerate` |
| `[Operator Name]` | `operator.name` |
| `[email@example.com]` | `operator.email` |

The screens table is dynamically rebuilt from `screens` array, with one row per screen.

### 9.3 Template Modification

The existing `Pixera_Playback_Spec_Template.docx` (already created in conversation) needs to be adapted as the source template. Specifically:

- The hardcoded SCR01/SCR02/SCR03 example rows must be replaced with a single template row that gets duplicated per screen at generation time.
- All `[BRACKETED]` text becomes a recognizable replacement marker.
- Placeholders that have no config equivalent (e.g., delivery target date) remain as brackets in output for manual editing.

The implementation may use `python-docx`'s table row manipulation for the screens table.

---

## 10. "What's In My Show" Reporting Mode

### 10.1 Workflow

```
[Operator selects Report from main menu]
         ↓
[Tool walks Media folder]
         ↓
[Tool catalogs all files by screen and slug]
         ↓
[Tool reads DeliveryLog.txt for last delivery info]
         ↓
[Tool displays formatted report to console]
```

### 10.2 Report Format

```
======================================================================
  SHOW: StJude2025 (2026-06-15)
  Path: D:\Shows\StJude2025_20260615\
======================================================================

Screens configured: 3
  SCR01 StageLeft     (3840x2160) — 5 files, 4 unique slugs
  SCR02 CenterIMAG    (1920x1080) — 5 files, 4 unique slugs
  SCR03 StageRight    (3840x2160) — 4 files, 4 unique slugs

Special folders:
  SCRwide  — 1 file
  SCRall   — 2 files
  AUD      — 3 files

Total content: 20 files across 14 unique slugs

Slugs with multiple versions present:
  SCR01_OpeningVideo:    v03 (2026-06-10), v04 (2026-06-12)
  SCR02_OpeningVideo:    v03 (2026-06-10), v04 (2026-06-12)
  SCR03_50thAnniversary: v01 (2026-06-08), v02 (2026-06-11)

Files in _REVIEW: 2
  Opening Video FINAL.mov
  SCR01_ClosingMontage_v02_20260425.mov

Last delivery: 2026-06-12 14:30 (5 copied, 2 review)
Days until show: 3
```

### 10.3 Stale Folder Handling

The report also surfaces stale folder warnings (folders in Media not in config) similarly to the intake mode.

---

## 11. Recent Shows / Memory

### 11.1 Storage

Recent shows are stored in `C:\Tools\PixeraIntake\.recent_shows.json`:

```json
{
  "shows": [
    {
      "path": "D:\\Shows\\StJude2025_20260615",
      "show_name": "StJude2025",
      "last_used": "2026-06-12T14:30:00"
    },
    {
      "path": "D:\\Shows\\AnnualGala_20260801",
      "show_name": "AnnualGala",
      "last_used": "2026-06-05T10:15:00"
    }
  ]
}
```

### 11.2 Behavior

- Up to 5 recent shows are stored. Older entries fall off as new ones are added.
- On launch, the tool displays the recent shows menu.
- Default selection is **always "[N] Pick a different show folder"** — the operator must explicitly select a recent show by number to use it.
- Shows whose `show_config.json` no longer exists at the stored path are silently removed from the list at launch time.
- The path is added/refreshed when a show is successfully loaded (config validates).

### 11.3 Launch Menu

```
======================================================================
  PIXERA INTAKE TOOL v1.0
======================================================================

Recent shows:
  1) StJude2025_20260615    (last used 2 days ago)
  2) AnnualGala_20260801    (last used 1 week ago)

  N) Pick a different show folder
  Q) Quit

Selection [N]: _
```

Hitting Enter without input selects the default `[N]`. Pressing 1 or 2 loads that show. Pressing N opens the folder picker. Pressing Q exits.

---

## 12. Setup Mode (First Run on New Show)

### 12.1 Trigger

Setup mode triggers automatically when the operator selects a show project root and `show_config.json` does not exist there.

### 12.2 Workflow

```
[Operator selects path to existing show project root]
         ↓
[Tool checks for show_config.json]
         ↓
[Not found]
         ↓
[Tool prompts: "No config found. Create starter config? [Y/N]"]
         ↓
[On Y]
  - Create Media\ folder (no screen subfolders yet)
  - Create Media\_LOGS\
  - Create Media\_REVIEW\
  - Create Media\_REFERENCE\
  - Copy templates\show_config_starter.json to <show_root>\show_config.json
         ↓
[Tool prints message: "Starter config created at <path>"]
[Tool attempts to open the file in Notepad++]
[Tool waits: "Edit and save the config, then press Enter to continue..."]
         ↓
[Operator edits config, saves, returns to console, presses Enter]
         ↓
[Tool re-reads config, validates]
         ↓
[If valid: proceeds to ensure screen folders exist, then main menu]
[If invalid: reports specific errors, waits for re-edit, loops]
```

### 12.3 Notepad++ Path

The tool launches Notepad++ via:

```
"C:\Program Files\Notepad++\notepad++.exe" "<path_to_config>"
```

If Notepad++ is not found at this path, the tool falls back to `os.startfile(<path>)` which opens the file in the OS-registered handler. The tool prints the file path to console regardless, so the operator can navigate to it manually if both methods fail.

### 12.4 Reconciliation on Subsequent Runs

Every time the tool loads a show (any mode), it ensures Media folders match config:

1. Validate config.
2. Ensure `Media/`, `_LOGS/`, `_REVIEW/`, `_REFERENCE/` exist; create if missing.
3. For each screen in config, ensure the screen folder exists; create if missing.
4. Detect stale folders (in Media but not in config) and surface them as warnings.

This means adding a screen to config mid-show is supported: edit config, re-run tool, new folder appears.

---

## 13. Main Menu

After a show is successfully loaded, the main menu is displayed:

```
======================================================================
  SHOW: StJude2025 (2026-06-15)
  Path: D:\Shows\StJude2025_20260615\
======================================================================

  1) Intake new content delivery
  2) Generate spec document
  3) Show "what's in my show" report
  4) Switch to a different show
  Q) Quit

Selection: _
```

### 13.1 Behavior

- After completing any action (1, 2, or 3), the tool returns to the main menu.
- Selecting 4 returns to the recent shows menu without exiting.
- Selecting Q exits the tool entirely.
- Invalid input prompts for re-entry without exiting.

---

## 14. Console UI Details

### 14.1 Color Conventions

When `colorama` is available:

| Element | Color |
|---|---|
| Section headers | Bold white |
| Success indicators (✓) | Green |
| Warning indicators (⚠) | Yellow |
| Failure indicators (✗) | Red |
| Skip/info indicators (•) | Dim/cyan |
| Path strings | Bright white |
| Prompts | Bold |

### 14.2 Layout Conventions

- Section headers use `=` separators 70 characters wide.
- Subsections use `-` separators 70 characters wide.
- File listings have consistent column widths for scanability.
- File sizes are formatted human-friendly (KB/MB/GB).

### 14.3 Input Conventions

- All Y/N prompts default to N if Enter is pressed alone (safer default).
- Menu prompts default to whatever option is shown in `[brackets]` after the prompt, defaulting to safest option.
- Invalid input re-prompts without crashing.

---

## 15. Error Handling

### 15.1 Categories

**Configuration errors:** Invalid JSON, missing required fields, validation failures. Tool reports specifically and halts the current operation. User fixes config, retries.

**File system errors:** Permission denied, disk full, source not accessible. Tool reports the specific file and continues with remaining files where possible.

**ffprobe errors:** Cannot read file metadata (corrupt file, unsupported format). File is treated as having unknown specs; routed to `_REVIEW/` with explanation.

**Tool errors:** Bugs, unexpected exceptions. Tool catches at the top level, reports the error with traceback to console, exits cleanly. The intake log captures the error for debugging.

### 15.2 Critical Failures That Halt the Tool

- Cannot find ffprobe on PATH (reported at startup; tool exits)
- Cannot create required directories at show root (permission issue; tool exits with clear message)
- Config file is malformed JSON (tool exits with parse error details)

### 15.3 Recoverable Failures (Continue)

- Single file copy failure (logged, skipped, continue with rest)
- Single file ffprobe failure (treated as unknown specs, routed to review, continue)
- Notepad++ not found (fall back to os.startfile, continue)

---

## 16. Out of Scope for v1

These features are explicitly deferred to v1.5 or later:

- **GUI window beyond folder pickers** — no main window, all interaction is console-based.
- **File checksumming / hashing for content comparison** — name + size only.
- **Thumbnail generation for visual QC.**
- **Email notifications on intake completion.**
- **Pixera integration of any kind** — no API calls, no .avp manipulation.
- **Auto-archive of old versions** — old versions stay in active folders.
- **Cross-name content matching** — files with different names but identical content are not detected.
- **Run-of-show map (`_RunOfShow_Map.csv`) automation** — the script does not create or update it.
- **Desktop shortcut creation per show** — the recent shows menu replaces this.
- **Sample test data generator** — useful for testing but deferred.
- **`--quiet` mode or other verbosity controls.**
- **Auto-open of generated docx** — operator opens it manually.

---

## 17. Acceptance Criteria

The tool is considered v1-complete when:

1. All four modes (Setup, Intake, Spec Generation, Reporting) work end-to-end.
2. Recent shows menu correctly stores, displays, and self-cleans entries.
3. Config validation correctly accepts valid configs and rejects invalid ones with clear errors.
4. Filename parsing correctly handles all documented patterns including special prefixes.
5. ffprobe integration correctly extracts and validates tech specs for ProRes files.
6. Atomic copy via temp files works correctly, including cleanup of leftover temp files.
7. Existing-file detection (name + size match) correctly skips and reports.
8. Version conflict detection correctly identifies and reports without moving files.
9. Stale folder detection correctly identifies and reports folders not in config.
10. Generated spec documents correctly populate from config including dynamic screens table.
11. All log files are correctly written and human-readable.
12. The tool gracefully handles common error cases without crashing.
13. README documents all setup, configuration, and usage.

---

## 18. Future Considerations (v1.5+)

For reference; not for v1 implementation:

- Sample test data generator (mock deliveries with known issues for testing)
- Run-of-show map automation
- File checksumming as an optional flag
- Thumbnail extraction for video preview
- GUI wrapper around the existing console tool
- Pixera resource pool integration if/when an API becomes available
- Automated config migration for schema changes between versions
- Multi-operator support (operator field could be a list, with current operator selectable)
- Email notification hooks
- Integration with cloud delivery platforms (Frame.io API, etc.)
