# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Status

This is a **specification-phase project** — design and planning documents are complete but no Python code has been written yet. Implementation follows the 12-phase roadmap in [PLAN.md](PLAN.md). Read [DESIGN.md](DESIGN.md) before working on any phase (PLAN.md assumes you have). Update PLAN.md task statuses (`[ ]` → `[~]` → `[x]`) as you work.

## Purpose

Windows Python CLI tool (3.10+) that automates content intake and management for Pixera media servers used in live event production. It validates video file naming conventions and technical specs (via ffprobe), organizes files into per-screen folders, and generates delivery specification Word documents.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Verify external dependency
ffprobe -version

# Run the tool (once Phase 0 is complete)
python pixera_intake.py
```

The project installs to `C:\Tools\PixeraIntake\` for production use; develop in a working directory and document the move at end.

## Architecture

### Planned layout (created during Phase 0)

```
pixera_intake.py          # Entry point: menu loop, mode dispatch
modules/
  config.py               # Load and validate show_config.json
  intake.py               # Core two-phase intake workflow
  spec_generator.py       # Generate .docx delivery spec from config
  show_report.py          # "What's in my show" catalog report
  ffprobe_wrapper.py      # subprocess ffprobe calls → typed dicts
  filename_parser.py      # Parse/validate naming convention
  recent_shows.py         # .recent_shows.json (max 5 entries)
  console_ui.py           # colorama-based output formatting
templates/
  show_config_starter.json
  spec_template.docx      # Source: Pixera_Playback_Spec_Template_v1_JJ.docx
```

### Runtime show project structure (operator-created per event)

```
D:\Shows\ShowName_YYYYMMDD\
  show_config.json        # Tool manages; operator edits in Notepad++
  ShowName.avp            # Pixera project (tool does not touch this)
  Media\
    _LOGS\                # DeliveryLog.txt + per-intake transcripts
    _REVIEW\              # Files that failed validation
    _REFERENCE\           # Operator reference materials
    SCR01\  SCR02\  ...   # One folder per screen (from config)
```

### Data flow

```
Launch → recent shows menu → load show root → validate show_config.json
  → main menu → [Intake | Spec | Report | Switch Show | Quit]
```

**Intake mode is always two-phase:** plan (walk source, parse filenames, run ffprobe, compare specs, build destination map, display report) → operator confirmation → execute (atomic copy: write `.tmp`, rename on success, delete on failure).

### Key design constraints

- **Never delete or move files already in active screen folders.** Both old and new versions coexist; operator handles swaps inside Pixera.
- **show_config.json is the single source of truth** for all show specs, screen IDs, and validation strictness levels.
- **Validation strictness is per-field:** `strict` routes to `_REVIEW/`, `warn` copies but flags, `info` copies and mentions only.
- **Resolution checking is screen-specific** — `SCRwide`, `SCRall`, and `AUD` prefixes skip resolution validation.
- **Codec identification uses ffprobe's `codec_tag`** (e.g., `"apch"` = ProRes 422 HQ), not `codec_name` alone.
- If Notepad++ is at `C:\Program Files\Notepad++\notepad++.exe`, open config files there; otherwise fall back to OS handler.

## Filename Convention

Pattern: `<prefix>_<slug>_v##_YYYYMMDD.<ext>`

Prefixes: `SCR##` (screen-specific), `SCRwide-##-##-##` (multi-screen), `SCRall`, `AUD`. Optional `-LOOP` suffix on slug signals seamless loop (informational only). Routing: full match → active screen folder, partial match (recognizable prefix, malformed fields) → active folder with warning, no match → `_REVIEW/`.

## Code Style

- Type hints on all function signatures; docstrings on all public functions/classes; module-level docstring on every file.
- `pathlib.Path` everywhere — never raw string paths.
- `subprocess.run` for all ffprobe calls.
- Specific exceptions only — no bare `except Exception`.
- Keep functions under ~50 lines where reasonable.
- Decision policy: if DESIGN.md is ambiguous, make a reasonable call and document it under the task in PLAN.md. If DESIGN.md contradicts itself or something is impossible, mark task `[!]` and stop for human input.
