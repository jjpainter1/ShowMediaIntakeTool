# Pixera Intake Tool

A Windows command-line tool for receiving, validating, and filing show content for Pixera media servers. It enforces a standardized delivery spec, organizes files into per-screen folders, catches naming and tech-spec problems before they cause issues in show, and generates delivery specification Word documents.

---

## Quick Start (5 steps)

1. Install Python 3.10+ and ffmpeg (see [Requirements](#requirements)).
2. Place the tool folder at `C:\Tools\PixeraIntake\` and run `pip install -r requirements.txt`.
3. Create your show project root folder manually, e.g. `D:\Shows\MyShow_20260615\`.
4. Run `python pixera_intake.py`, pick the show folder, and fill in the generated `show_config.json`.
5. Drop a content delivery into any folder, then select **Intake** from the menu.

---

## Contents

- [Requirements](#requirements)
- [Installation](#installation)
- [First-Time Use](#first-time-use)
- [Configuration Reference](#configuration-reference)
- [Workflow](#workflow)
  - [Setup Mode](#setup-mode)
  - [Intake Mode](#intake-mode)
  - [Spec Generation Mode](#spec-generation-mode)
  - [Reporting Mode](#reporting-mode)
- [Troubleshooting](#troubleshooting)
- [What Goes in \_REVIEW](#what-goes-in-_review)
- [Not Supported in v1](#not-supported-in-v1)

---

## Requirements

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.10 or later | [python.org](https://www.python.org/downloads/) |
| ffmpeg / ffprobe | Any recent build | Must be on PATH; [gyan.dev builds](https://www.gyan.dev/ffmpeg/builds/) recommended |
| Notepad++ | Any | Recommended for editing configs; tool falls back to default OS handler if absent |
| python-docx | ≥ 1.0.0 | Installed via `requirements.txt` |
| colorama | ≥ 0.4.6 | Installed via `requirements.txt` |

---

## Installation

### 1. Place the tool

Copy the tool folder to `C:\Tools\PixeraIntake\`. The folder should contain:

```
pixera_intake.py
modules\
templates\
requirements.txt
README.md
```

### 2. Install Python dependencies

Open a terminal in the tool folder and run:

```
pip install -r requirements.txt
```

### 3. Verify ffprobe is on PATH

```
ffprobe -version
```

If this prints version information, you're set. If you get "not recognized," ffmpeg is not on PATH. Fix this by:

1. Downloading a full ffmpeg build (e.g., from gyan.dev).
2. Extracting it, e.g. to `C:\Tools\ffmpeg\`.
3. Adding `C:\Tools\ffmpeg\bin\` to your system PATH.
4. Reopening your terminal and retrying `ffprobe -version`.

### 4. Create a desktop shortcut (optional)

Create a `.bat` file anywhere convenient:

```bat
@echo off
cd /d C:\Tools\PixeraIntake
python pixera_intake.py
pause
```

---

## First-Time Use

1. **Create the show project root folder manually** — the tool does not create this for you. Use a consistent naming convention, e.g.:
   ```
   D:\Shows\ShowName_YYYYMMDD\
   ```

2. **Run the tool:**
   ```
   python pixera_intake.py
   ```

3. **At the launch menu**, press `N` to pick a folder, then navigate to your show root.

4. **Setup mode runs automatically** when no `show_config.json` is found. The tool creates the Media folder structure and opens the starter config in Notepad++ (or your default editor).

5. **Edit `show_config.json`** — fill in the show name, date, operator details, screens, and validation settings. Save the file and press Enter in the terminal to continue.

6. **Config validation runs** on every load. If anything is wrong, the tool reports the specific problem and re-opens the file for you to fix.

The show project root will look like this after setup:

```
D:\Shows\MyShow_20260615\
  show_config.json         ← fill this in
  Media\
    _LOGS\                 ← delivery logs written here
    _REVIEW\               ← files that need review land here
    _REFERENCE\            ← drop reference materials here manually
    SCR01\                 ← one folder per configured screen
    SCR02\
    ...
```

---

## Configuration Reference

Each show has a `show_config.json` in its project root. Edit this file to define the show's screens, expected specs, and validation behavior.

### Full example

```json
{
  "show_name": "StJude2026",
  "show_date": "2026-06-15",
  "operator": {
    "name": "Jane Jones",
    "email": "jjones@prestigeav.com"
  },
  "expected_specs": {
    "framerate": 29.97,
    "color_space": "bt709",
    "color_range": "tv",
    "audio_sample_rate": 48000,
    "audio_channels": 2
  },
  "expected_codecs": ["prores_422_hq", "prores_422", "prores_4444"],
  "preferred_codecs": ["prores_422_hq", "prores_4444"],
  "screens": [
    { "id": "SCR01", "name": "StageLeft",  "resolution": "3840x2160" },
    { "id": "SCR02", "name": "CenterIMAG", "resolution": "1920x1080" },
    { "id": "SCR03", "name": "StageRight", "resolution": "3840x2160" }
  ],
  "validation_strictness": {
    "resolution":        "strict",
    "framerate":         "strict",
    "codec":             "strict",
    "codec_flavor":      "warn",
    "color_space":       "warn",
    "color_range":       "warn",
    "audio_sample_rate": "info",
    "audio_channels":    "info"
  }
}
```

### Field reference

| Field | Type | Required | Description |
|---|---|---|---|
| `show_name` | string | Yes | Used in filenames and the spec document. Letters, digits, hyphens, underscores only — no spaces. |
| `show_date` | string | Yes | Show date in `YYYY-MM-DD` format. Used in the spec document and the countdown display. |
| `operator.name` | string | Yes | Your name. Appears in the spec document. |
| `operator.email` | string | Yes | Your email. Appears in the spec document. |
| `expected_specs.framerate` | number | Yes | Expected framerate as a decimal (e.g. `29.97`, `30`, `60`). |
| `expected_specs.color_space` | string | Yes | ffprobe color space name. Use `"bt709"` for Rec.709 content. |
| `expected_specs.color_range` | string | Yes | `"tv"` for legal/limited range (standard), `"pc"` for full range. |
| `expected_specs.audio_sample_rate` | number | Yes | Expected audio sample rate in Hz (e.g. `48000`). |
| `expected_specs.audio_channels` | number | Yes | Expected channel count (e.g. `2` for stereo). |
| `expected_codecs` | array | Yes | Acceptable codec identifiers. Files matching any of these pass codec validation. |
| `preferred_codecs` | array | Yes | Must be a subset of `expected_codecs`. Files using a non-preferred but acceptable codec trigger a warning at the `codec_flavor` strictness level. |
| `screens` | array | Yes | One entry per screen. Each must have `id`; `name` and `resolution` are strongly recommended. |
| `screens[].id` | string | Yes | Used as the Media subfolder name and matched against filename prefixes. Letters, digits, hyphens, underscores only. |
| `screens[].name` | string | No | Human-readable label shown in reports and the spec document. |
| `screens[].resolution` | string | No | Expected resolution in `WIDTHxHEIGHT` format (e.g. `"3840x2160"`). Required for resolution validation. |
| `validation_strictness` | object | Yes | Per-field strictness levels. See below. |

### Strictness levels

Each field in `validation_strictness` can be set to one of three levels:

| Level | Effect on mismatch |
|---|---|
| `strict` | File is routed to `_REVIEW/` instead of its screen folder. Intake report marks it as a failure (red). |
| `warn` | File is copied to the screen folder, but the intake report flags a warning (yellow). |
| `info` | File is copied without any flag. Only mentioned if you look at the detailed log. |

**Validation fields you can configure:**

| Field | What it checks | Default recommendation |
|---|---|---|
| `resolution` | Width × height against the screen's expected resolution | `strict` |
| `framerate` | Frame rate within 0.01 fps of expected | `strict` |
| `codec` | Codec must be in `expected_codecs` | `strict` |
| `codec_flavor` | Codec must be in `preferred_codecs` (if it passed codec check) | `warn` |
| `color_space` | Color space matches expected (e.g. bt709) | `warn` |
| `color_range` | Color range matches expected (tv vs pc) | `warn` |
| `audio_sample_rate` | Audio sample rate matches expected | `info` |
| `audio_channels` | Audio channel count matches expected | `info` |

### Supported codec identifiers

Use these strings in `expected_codecs` and `preferred_codecs`:

| Identifier | Description |
|---|---|
| `prores_422_proxy` | ProRes 422 Proxy |
| `prores_422_lt` | ProRes 422 LT |
| `prores_422` | ProRes 422 (Standard) |
| `prores_422_hq` | ProRes 422 HQ |
| `prores_4444` | ProRes 4444 |
| `prores_4444_xq` | ProRes 4444 XQ |
| `notchlc` | NotchLC |

---

## Workflow

### Setup Mode

Runs automatically the first time you open a folder with no `show_config.json`.

1. Tool creates `Media/`, `Media/_LOGS/`, `Media/_REVIEW/`, and `Media/_REFERENCE/`.
2. Copies the starter config to `show_config.json` and opens it in Notepad++.
3. You fill it in and save.
4. Press Enter in the terminal — the tool validates and either proceeds or tells you what to fix.
5. Screen folders (e.g. `Media/SCR01/`) are created once the config validates successfully.

If you add or rename screens later, just update `show_config.json` — the tool creates any missing screen folders the next time it loads.

---

### Intake Mode

Select **1) Intake new content delivery** from the main menu.

**The tool always works in two phases:**

**Phase 1 — Plan:**
- A folder picker opens; navigate to the delivery folder (can be a USB drive, network share, or local folder).
- The tool walks it recursively, parsing every filename and running ffprobe on each file.
- It builds a proposed action for each file: copy, copy with warning, route to `_REVIEW/`, or skip.
- The full plan is displayed before anything is copied.

**Example plan output:**
```
======================================================================
  PIXERA INTAKE — PLAN PHASE
======================================================================
  Show:    StJude2026 (2026-06-15)
  Source:  D:\Deliveries\Del_20260610\
  Files:   8 files found in source

  PROPOSED ACTIONS

  ✓ COPY    SCR01_OpeningVideo_v04_20260612.mov       (2.1 GB)  Media\SCR01\
  ✓ COPY    SCR02_OpeningVideo_v04_20260612.mov       (840 MB)  Media\SCR02\
  ⚠ COPY    SCR01_Countdown_v01_20260612.mov          (650 MB)  Media\SCR01\
               WARN: Framerate is 30.000, expected 29.97
  ✗ REVIEW  OpeningVideo_FINAL.mov                   (1.8 GB)  Media\_REVIEW\
               FAIL: Filename does not match convention
  • SKIP    SCR03_ClosingMontage_v01_20260608.mov     (920 MB)  (already present)

  SUMMARY
    5 files to copy (4.3 GB)
    1 file to route to _REVIEW
    2 files to skip (already present)
    1 version conflict detected
```

**Phase 2 — Execute:**
- You review the plan and press Y to proceed (default is N — you must explicitly confirm).
- Files are copied atomically: each file copies to a `.tmp` file first, then renamed on success. A crash mid-copy never leaves a broken file in your active folders.
- A summary shows how many files were copied, routed, or skipped.
- Two logs are written to `Media/_LOGS/`:
  - `DeliveryLog.txt` — one-line summary appended to the running delivery history.
  - `intake_YYYYMMDD_HHMMSS.txt` — full transcript of the plan and execution.

**Filename convention:**

The tool expects files to be named:
```
<prefix>_<Slug>_v##_YYYYMMDD.ext
```

| Part | Format | Example |
|---|---|---|
| Prefix | `SCR##`, `SCRwide-##-##`, `SCRall`, or `AUD` | `SCR01`, `SCRwide-01-02`, `SCRall`, `AUD` |
| Slug | Letters, digits, dashes (PascalCase recommended) | `OpeningVideo`, `50thAnniversary` |
| Version | Lowercase `v` + digits, zero-padded | `v01`, `v12` |
| Date | 8 digits, YYYYMMDD | `20260612` |
| Extension | Any | `.mov`, `.wav`, `.mp4` |

To flag seamless-loop content, append `-LOOP` to the slug: `SCR01_AmbientBG-LOOP_v01_20260612.mov`.

**How files are routed:**

| Filename result | What happens |
|---|---|
| Full match (all fields valid) | Copied to `Media/<prefix>/` |
| Partial match (valid prefix, malformed fields) | Copied to `Media/<prefix>/` with a warning |
| No match (no recognizable prefix) | Routed to `Media/_REVIEW/` |

**Version conflicts:** If a different version of the same slug already exists in the destination folder (e.g. `v03` is present and `v04` is incoming), the tool flags this in the plan. **Both versions are left in place** — the operator handles the swap inside Pixera where resource paths can be updated safely.

**Existing files:** If the exact same filename already exists at the destination:
- Same size → skip silently.
- Different size → route to `_REVIEW/` with a "name conflict" warning.

---

### Spec Generation Mode

Select **2) Generate spec document** from the main menu.

Generates `<ShowName>_DeliverySpec.docx` in the show project root, populated from `show_config.json`. The document includes:

- Show name and date
- Operator name and contact
- Screens table (one row per configured screen, with resolution)
- Expected framerate and color space
- Delivery filename convention and codec requirements

Open the generated docx in Word, review, and send to the content vendor as the delivery specification.

---

### Reporting Mode

Select **3) Show "what's in my show" report** from the main menu.

Displays the current state of the show's content at a glance:

```
======================================================================
  SHOW: StJude2026  (2026-06-15)
  Path: D:\Shows\StJude2026_20260615\
======================================================================

Screens configured: 3
  SCR01  StageLeft       (3840x2160)  — 5 files, 4 unique slugs
  SCR02  CenterIMAG      (1920x1080)  — 5 files, 4 unique slugs
  SCR03  StageRight      (3840x2160)  — 4 files, 4 unique slugs

Special folders:
  AUD         — 3 files
  SCRall      — 2 files

Total content: 19 files across 7 unique slugs

Slugs with multiple versions present:
  SCR01_OpeningVideo:  v03 (2026-06-10), v04 (2026-06-12)
  SCR02_OpeningVideo:  v03 (2026-06-10), v04 (2026-06-12)

Files in _REVIEW: 2
  Opening Video FINAL.mov
  SCR01_ClosingMontage_v02_20260425.mov

Last delivery: 2026-06-12 14:30 (5 copied, 2 review, 1 skip)
Days until show: 49
```

Any folders inside `Media/` that are not in your config and not one of the special prefixes are flagged as stale at the bottom of the report.

---

## Troubleshooting

### "The tool says my config is invalid"

The error message names the specific field and problem, e.g.:

```
✗ Config validation failed: Field 'show_name' contains invalid characters: 'St Jude 2026'.
  Only letters, digits, hyphens, and underscores are allowed.
```

Common fixes:

| Error | Fix |
|---|---|
| Invalid characters in `show_name` | Remove spaces and special characters — use `StJude2026` not `St Jude 2026` |
| `show_date` format wrong | Must be `YYYY-MM-DD` with dashes, e.g. `"2026-06-15"` |
| `preferred_codecs` not subset of `expected_codecs` | Every entry in `preferred_codecs` must also appear in `expected_codecs` |
| Missing required field | All fields in the reference above marked "Required: Yes" must be present and non-empty |
| Duplicate screen ID | Each `id` in the `screens` array must be unique |
| Bad resolution format | Must be `WIDTHxHEIGHT` with lowercase x, e.g. `"3840x2160"` |

After fixing, save the file. The tool re-validates automatically when you press Enter.

### "ffprobe not found on PATH"

The tool checks for ffprobe at startup and exits immediately if it is missing.

1. Download ffmpeg from [gyan.dev](https://www.gyan.dev/ffmpeg/builds/) (the "full" build includes ffprobe).
2. Extract to a permanent location such as `C:\Tools\ffmpeg\`.
3. Open **System Properties → Environment Variables → System variables → Path → Edit**.
4. Add `C:\Tools\ffmpeg\bin\` to the list.
5. Restart any open terminals and re-run `ffprobe -version` to confirm.

### "Notepad++ doesn't open"

If Notepad++ is not installed at `C:\Program Files\Notepad++\notepad++.exe`, the tool falls back to `os.startfile`, which opens the file in whatever your system associates with `.json` files (often Notepad). This is fine — edit and save the file as normal, then return to the terminal and press Enter.

To use Notepad++, install it from [notepad-plus-plus.org](https://notepad-plus-plus.org/) to the default location.

### Files are going to \_REVIEW instead of screen folders

Check the intake report for the reason. Common causes:

- **No recognizable prefix** — filename does not start with `SCR##`, `SCRwide-##-##`, `SCRall`, or `AUD`.
- **Resolution mismatch at `strict` level** — the file's resolution does not match the screen's configured resolution. Lower the strictness to `warn` if intentional.
- **Codec not in `expected_codecs`** — the file uses a codec not listed in your config. Add it to `expected_codecs` if acceptable, or ask the vendor to re-export.
- **ffprobe could not read the file** — the file may be corrupt or in an unsupported container.

### A file was copied but with warnings — is that a problem?

A warning means the file is in the active screen folder and Pixera can use it, but something about it doesn't match your spec. Decide case by case:

- **Framerate warning** at `warn` level — the file plays, but confirm the show's timeline framerate matches before tech.
- **Codec warning** (`codec_flavor`) — the file is an acceptable ProRes variant, just not the preferred flavor. Usually fine.
- **Color space warning** — worth asking the vendor to re-export if you're doing critical color work.

---

## What Goes in \_REVIEW

`Media/_REVIEW/` collects files the tool cannot safely place in an active screen folder automatically:

- Files with no recognizable screen prefix (the tool doesn't know where they belong).
- Files with a name conflict — same filename already exists in the destination with a different size.
- Files with a `strict`-level spec failure (wrong resolution, unknown codec, etc.).

**What to do with them:**

1. Open the intake log in `Media/_LOGS/` to see exactly why each file landed in `_REVIEW/`.
2. If the file is a name collision with different content, determine which version is correct and file it manually.
3. If the filename is wrong, rename it to the correct convention and run intake again (or copy it manually).
4. If the spec is wrong, ask the vendor to re-export and deliver again.

The tool never moves or deletes files from `_REVIEW/` — clearing it out is a manual step.

---

## Not Supported in v1

These are explicitly out of scope for this version:

- GUI window — all interaction is console-based (folder pickers use a native OS dialog).
- File hashing / checksumming — duplicate detection uses filename + size only.
- Auto-archive of old versions — both old and new versions coexist; you swap inside Pixera.
- Pixera API integration — the tool does not communicate with Pixera directly.
- Cross-name content matching — files with different names but identical content are not detected.
- Thumbnail or waveform generation for visual QC.
- Email notifications on intake completion.
- Run-of-show map automation.
- `--quiet` mode or verbosity controls.
- Auto-opening of generated docx.
